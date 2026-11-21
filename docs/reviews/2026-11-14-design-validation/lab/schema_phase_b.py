"""Lab: S2 schema phase B, the mechanical conversion of docs/design/*.sql (findings 1 and 2 of architecture-overview.md).
Not product code. Idempotent: a second run changes nothing.

    python3 schema_phase_b.py [--docs DIR] [--dry-run]

What it does to every CREATE TABLE of docs/design/*.sql (partitions inherit from their parent and are skipped):

1. recorded_at (ADR-0007 rule 9; the ADR-0007 rule 16 note): a table without the column gets
   `recorded_at timestamptz NOT NULL DEFAULT now()`; an existing `recorded_at ... NOT NULL` without a default gains
   `DEFAULT now()`.
2. Keys (ADR-0006 rule 1 and its note of 2026-11-21): a table whose primary key is not the single column `id`
   gets `id uuid PRIMARY KEY` as its first column, and the old key becomes the named unique constraint
   `uq_<table>_<columns>` (`uq_<table>_key` where that name would exceed 63 bytes, ADR-0004 rule 6); a key column that was
   nullable gains NOT NULL, as the primary key implied. Foreign keys that target the old key keep working against the
   unique constraint. Exception class E1 (gen_overview.KEY_ALLOWLIST) keeps its natural key. E2 registries get a comment that the
   loader computes the id as uuid5; E3 (one row per company) is the general case with the old key UNIQUE (company_id).
   `id` has no default (ADR-0006 rule 2) except on DB_WRITTEN tables, whose rows database code inserts.
3. Company keys (S06 of lab t16; S2 schema review finding S4): a single-column foreign key to account, posting_period,
   fiscal_year or any table whose CREATE TABLE declares UNIQUE (company_id, id) (except COMPANY_KEYED_EXCEPT), in a table
   with `company_id ... NOT NULL`, becomes `FOREIGN KEY (company_id, <column>) REFERENCES <table> (company_id, id)`.
4. The recorded_at trigger: each file ends with one section that defines set_recorded_at() and runs one DO block, which
   attaches `trg_<table>_set_recorded_at` (BEFORE UPDATE) to every table of the file except its append-only tables. The
   phase A CREATE TRIGGER ... set_recorded_at statements and the function definitions at the top of the files are
   removed. Append-only: tables whose guard trigger refuses every update outside an erasure (ALWAYS_REFUSE, or
   platform_check_append_only / crm_check_append_only with no mutable column but recorded_at and no set-once column),
   and the pure logs in gen_overview.PURE_LOGS.

gen_overview.py --check verifies the result (check_keys_and_recorded_at); this script only writes.
"""
import argparse
import glob
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from gen_overview import KEY_ALLOWLIST, PURE_LOGS, RECORDED_AT_END as SECTION_END, RECORDED_AT_SECTION as SECTION_START  # noqa: E402
from gen_overview import classify, mask_sql as mask, table_spans  # noqa: E402

REGISTRIES = {"setting_definition", "setting_preset", "setting_preset_item", "extension_point", "event_consumer",
              "public_mail_domain"}   # E2 (ADR-0006 rule 1 note)
DB_WRITTEN = {"barcode": "barcode_register inserts the rows"}   # id DEFAULT uuidv7() (ADR-0006 rule 2)
COMPANY_KEYED = ("account", "posting_period", "fiscal_year")
# Rule 3 extension (S2 schema review finding S4): every target whose CREATE TABLE has UNIQUE (company_id, id) is company
# keyed too, except these, whose lab stub (00_stubs.sql, the standard load of DS-06 without DS-22) has no company_id; the
# file that defines the target adds the composite keys to it by ALTER TABLE.
COMPANY_KEYED_EXCEPT = {"material_document_line": "DS-22-09-42-commercial-inventory.sql adds the composite keys"}


def line_start(text, pos):
    return text.rfind("\n", 0, pos) + 1


def company_keyed_targets(files):
    """COMPANY_KEYED plus every table whose CREATE TABLE declares UNIQUE (company_id, id), minus COMPANY_KEYED_EXCEPT."""
    out = set(COMPANY_KEYED)
    for p in files:
        text = open(p, encoding="utf-8").read()
        masked = mask(text)
        for table, _, _, spans in table_spans(text, masked):
            if any(re.fullmatch(r"(?:CONSTRAINT \w+ )?UNIQUE \(company_id, id\)", " ".join(masked[a:b].split())) for a, b in spans):
                out.add(table)
    return sorted(out - set(COMPANY_KEYED_EXCEPT))


def convert_file(path, append_only, keyed=COMPANY_KEYED):
    text = open(path, encoding="utf-8").read()
    name = os.path.basename(path)
    # drop the phase A trigger statements and the function definitions; the end section replaces them
    text = re.sub(r"^CREATE TRIGGER trg_\w+_set_recorded_at BEFORE UPDATE ON \w+\n\s+FOR EACH ROW EXECUTE FUNCTION set_recorded_at\(\);\n",
                  "", text, flags=re.M)
    if SECTION_START in text:
        text = text[:text.index(SECTION_START)].rstrip("\n") + "\n"
    text = re.sub(r"^CREATE OR REPLACE FUNCTION set_recorded_at\(\) RETURNS trigger .*?\nEND \$\$;\n", "", text, flags=re.M | re.S)
    masked = mask(text)
    edits, report, tables = [], [], []
    for table, open_i, close_i, spans in table_spans(text, masked):
        tables.append(table)
        codes = [" ".join(masked[s:e].split()) for s, e in spans]
        cols = {}
        for k, c in enumerate(codes):
            if not re.match(r"(CONSTRAINT|UNIQUE|CHECK|EXCLUDE|PRIMARY|FOREIGN)\b", c):
                cols[c.split()[0]] = k
        first_s = spans[0][0]
        if masked[line_start(masked, first_s):first_s].strip():
            raise SystemExit(f"{name} {table}: first column not on its own line")
        indent = masked[line_start(masked, first_s):first_s]
        m0 = re.match(r"(\w+\s+)", masked[first_s:])
        width = len(m0.group(1))
        appended = []          # table-level elements added at the end: (code, comment)
        # --- primary key
        pk_cols, pk_where = None, None
        for k, c in enumerate(codes):
            tm = re.match(r"(?:CONSTRAINT \w+ )?PRIMARY KEY \(([^)]*)\)", c)
            if tm:
                pk_cols, pk_where = [x.strip() for x in tm.group(1).split(",")], ("table", k)
            elif k in cols.values() and re.search(r"\bPRIMARY KEY\b", c):
                pk_cols, pk_where = [c.split()[0]], ("inline", k)
        if pk_cols != ["id"] and table not in KEY_ALLOWLIST:
            if "id" in cols:
                raise SystemExit(f"{name} {table}: has a column id that is not the primary key")
            uq = f"uq_{table}_{'_'.join(pk_cols)}" if pk_cols else None
            hand = False
            if uq and len(uq.encode()) > 63:
                uq, hand = f"uq_{table}_key", True
            if pk_where and pk_where[0] == "inline":
                s, e = spans[pk_where[1]]
                pm = re.search(r"\bPRIMARY KEY\b", masked[s:e])
                has_nn = "NOT NULL" in codes[pk_where[1]]
                edits.append((s + pm.start(), s + pm.end(), ("" if has_nn else "NOT NULL ") + f"CONSTRAINT {uq} UNIQUE"))
            elif pk_where:
                s, e = spans[pk_where[1]]
                pm = re.search(r"(?:CONSTRAINT \w+ )?PRIMARY KEY \(([^)]*)\)", masked[s:e], re.S)
                edits.append((s + pm.start(), s + pm.end(), f"CONSTRAINT {uq} UNIQUE ({', '.join(pk_cols)})"))
                for col in pk_cols:
                    k = cols[col]
                    if "NOT NULL" not in codes[k]:
                        cs, ce = spans[k]
                        tmatch = re.match(r"\w+\s+[\w.]+(?:\[\])?(?:\([^)]*\))?", masked[cs:ce])
                        edits.append((cs + tmatch.end(), cs + tmatch.end(), " NOT NULL"))
            comment = ""
            if table in REGISTRIES:
                key = ":".join(f"<{c}>" for c in pk_cols)
                comment = (f"   -- uuid5(f244ce09-3c6c-4c82-af14-918bdeca6be3, '{table}:{key}'), computed by the loader "
                           f"(registry E2, ADR-0006 rule 1 note)")
            elif pk_cols == ["company_id"]:
                comment = "   -- one row per company (E3, ADR-0006 rule 1 note)"
            if hand:
                comment += ("; " if comment else "   -- ") + f"{uq} named by hand: the convention name would exceed 63 bytes (ADR-0004 rule 6)"
            default = " DEFAULT uuidv7()" if table in DB_WRITTEN else ""
            if default:
                comment = f"   -- {DB_WRITTEN[table]} (ADR-0006 rule 2)" + comment.replace("   --", ";", 1)
            line = f"{indent}{'id'.ljust(width)}uuid PRIMARY KEY{default},{comment}\n"
            edits.append((line_start(text, first_s), line_start(text, first_s), line))
            report.append(f"key {table}: {pk_cols or 'none'} -> id; {uq or ''}")
        # --- recorded_at
        if "recorded_at" not in cols:
            first_con = next((k for k, c in enumerate(codes) if k not in cols.values()), None)
            new_col = f"{'recorded_at'.ljust(max(width, 12))}timestamptz NOT NULL DEFAULT now()"
            if first_con is not None and not masked[line_start(masked, spans[first_con][0]):spans[first_con][0]].strip():
                pos = line_start(text, spans[first_con][0])
                edits.append((pos, pos, f"{indent}{new_col},\n"))
            else:
                appended.append((new_col, ""))
            report.append(f"recorded_at {table}: added")
        else:
            k = cols["recorded_at"]
            s, e = spans[k]
            if "DEFAULT" not in codes[k]:
                nm = re.search(r"NOT NULL", masked[s:e])
                if not nm:
                    raise SystemExit(f"{name} {table}: recorded_at is nullable")
                edits.append((s + nm.end(), s + nm.end(), " DEFAULT now()"))
                report.append(f"recorded_at {table}: default added")
        # --- company keys
        if "company_id" in cols and "NOT NULL" in codes[cols["company_id"]]:
            for col, k in cols.items():
                s, e = spans[k]
                rm = re.search(r"\s+REFERENCES (" + "|".join(keyed) + r") \(id\)", masked[s:e])
                if rm:
                    edits.append((s + rm.start(), s + rm.end(), ""))
                    why = "S2 schema phase B" if rm.group(1) in COMPANY_KEYED else "S2 schema review S4"
                    appended.append((f"FOREIGN KEY (company_id, {col}) REFERENCES {rm.group(1)} (company_id, id)",
                                     f"   -- company key ({why})"))
                    report.append(f"company key {table}.{col} -> {rm.group(1)}")
        else:
            for col, k in cols.items():
                s, e = spans[k]
                if re.search(r"\s+REFERENCES (" + "|".join(keyed) + r") \(id\)", masked[s:e]):
                    report.append(f"company key {table}.{col}: kept single-column (company_id nullable or absent)")
        if appended:
            ls, le = spans[-1]
            after = masked[le:text.find("\n", le)]
            if ")" in after:
                raise SystemExit(f"{name} {table}: closing parenthesis on the last element's line")
            eol = text.find("\n", le)
            parts = []
            for j, (code, cm) in enumerate(appended):
                sep = "," if j < len(appended) - 1 else ""
                parts.append(f"\n{indent}{code}{sep}{cm}")
            if eol == le:
                edits.append((le, le, "," + "".join(parts)))
            else:
                edits.append((le, le, ","))
                edits.append((eol, eol, "".join(parts)))
    edits.sort(key=lambda x: (x[0], x[1]), reverse=True)
    last = None
    for s, e, new in edits:
        if last is not None and e > last:
            raise SystemExit(f"{name}: overlapping edits at {s}")
        text = text[:s] + new + text[e:]
        last = s
    # --- the end section
    ao = sorted(t for t in tables if t in append_only)
    text = text.rstrip("\n") + "\n\n" + section(tables, ao, append_only) + "\n"
    return text, report, tables, ao


def wrap_array(names, indent):
    lines, cur = [], ""
    for n in names:
        item = f"'{n}', "
        if len(indent) + len(cur) + len(item) > 124:
            lines.append(cur.rstrip()); cur = ""
        cur += item
    lines.append(cur.rstrip().rstrip(","))
    return ("\n" + indent).join(lines)


def section(tables, ao, append_only):
    pad = " " * 8
    reasons = sorted({append_only[t] for t in ao})
    return "\n".join([
        SECTION_START,
        "-- Every table of this file has recorded_at timestamptz NOT NULL DEFAULT now(). The DO block attaches the trigger",
        "-- trg_<table>_set_recorded_at (BEFORE UPDATE, function set_recorded_at) to every table of v_tables except v_append_only,",
        "-- so recorded_at is the instant of the last write (ADR-0007 rule 9 note). Append-only tables are those whose guard",
        "-- trigger refuses every update outside an erasure, and pure logs; they need no trigger"
        + (f" (here: {', '.join(reasons)})." if reasons else "."),
        "-- Row guards without UPDATE OF on in-place tables sort before set_recorded_at, so they compare rows before it runs.",
        "-- v_tables lists the file's tables in file order; lab gen_overview.py --check verifies both lists against the table",
        "-- definitions of the file, and schema_phase_b.py writes the section. The function is defined in every file because the",
        "-- labs load subsets.",
        "CREATE OR REPLACE FUNCTION set_recorded_at() RETURNS trigger LANGUAGE plpgsql SET search_path = nativeflows, pg_temp AS $$",
        "BEGIN",
        "    NEW.recorded_at := now();",
        "    RETURN NEW;",
        "END $$;",
        "DO $$",
        "DECLARE",
        f"    v_tables       text[] := ARRAY[{wrap_array(tables, pad)}];",
        f"    v_append_only  text[] := ARRAY[{wrap_array(ao, pad)}]::text[];",
        "    v_table        text;",
        "BEGIN",
        "    FOREACH v_table IN ARRAY v_tables LOOP",
        "        CONTINUE WHEN v_table = ANY (v_append_only) OR to_regclass(v_table) IS NULL;",
        "        EXECUTE format('CREATE OR REPLACE TRIGGER %I BEFORE UPDATE ON %I FOR EACH ROW EXECUTE FUNCTION set_recorded_at()',",
        "                       'trg_' || v_table || '_set_recorded_at', v_table);",
        "    END LOOP;",
        "END $$;",
        SECTION_END,
    ])


def main():
    from load_all import split_statements
    ap = argparse.ArgumentParser()
    ap.add_argument("--docs", default=os.path.join(HERE, "..", "..", ".."))
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    files = sorted(glob.glob(os.path.join(os.path.abspath(a.docs), "design", "*.sql")))
    stmts = []
    for p in files:
        stmts += [re.sub(r"--[^\n]*", "", s) for s, _ in split_statements(open(p, encoding="utf-8").read(), os.path.basename(p))[0]]
    append_only = classify(stmts)
    keyed = company_keyed_targets(files)
    n_tables = n_ao = 0
    for p in files:
        new, report, tables, ao = convert_file(p, append_only, keyed)
        n_tables += len(tables); n_ao += len(ao)
        for r in report:
            print(f"{os.path.basename(p)}: {r}")
        if not a.dry_run:
            open(p, "w", encoding="utf-8").write(new)
    print(f"{n_tables} tables, {n_ao} append-only, {n_tables - n_ao} with the trigger")


if __name__ == "__main__":
    main()
