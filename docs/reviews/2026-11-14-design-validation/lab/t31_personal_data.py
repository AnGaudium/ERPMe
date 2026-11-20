"""Scenario: personal data protection in the core (ADR-0079). Not product code.

Run: python t31_personal_data.py [--load]
  Pure checks need no database. With --load, NATIVEFLOWS_LAB_DSN must name a throwaway database: load_all.py drops and
  rebuilds schemas nativeflows and types there with every DDL file of NATIVEFLOWS_DOCS/design (default ~/Projects/NativeFlows/docs).

P: the DDL parse: every design/*.sql file, its CREATE TABLE blocks, columns and trailing comments.
C: the catalog against the DDL (rule 2; INV-890): both files' headers and enum values; every catalog pair is a real column;
   no duplicate and no pair in both files; every column whose name matches the personal-name pattern is in exactly one file,
   and the exclusions hold only such columns; every column whose trailing comment says personal is in the catalog, except the
   allow-list below, each entry with its reason; every table with custom_values has a catalog row for it (ADR-0074 rule 8);
   frozen and append-only rows never rely on a partition drop; every keep row has a note; the retention classes are the ten
   of rule 9, the same in the catalog, in DS-64's retention_rule CHECK and in the ADR.
S: self-tests: three broken variants fed to the same checker (a DDL column with a personal name and no catalog row, a catalog
   row naming a missing column, a pair in both files), each caught.
K: the other catalogs and the field class (rules 5, 11, 15, 16): INV-890 to INV-894, EC-350 to EC-354, the work item kind
   personal_data_incident_suspected, the case kind personal_data_breach, the leaf blocked_personal_data at none in every role
   template, sensitive_personal in the role assignment and custom field CHECKs and not in the agent type version CHECK, the
   processing log kind retention.
R: reference functions for the retention job (rule 9; EC-354): no verified rule, no destruction; blocking before destruction.
With --load: the five tables of DS-64-personal-data.sql exist with company_id, recorded_at, UNIQUE (company_id, id) and forced
row-level security; each CHECK and key refuses a bad row; the append-only tables refuse UPDATE and DELETE; a simulated erasure of
a partner, its address and its contact, driven by the catalog, leaves blank or tokenized columns, one data_erasure_entry per
rewritten row (INV-892 in SQL) and entries whose columns carry no values (no jsonb, text only for codes and names).
Not covered: the trigger exception that lets the erasure command rewrite posted documents, versions and journal text columns
(ADR-0079 rule 7): its DDL is written with the ledger and document DDL in session S2 (open question). Commands, the retention
job, masking, the read log writers, the erasure journal outside the database and ReapplyErasures are not covered either.
"""
import csv, glob, io, os, re, sys
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
LAB = os.environ.get("NATIVEFLOWS_LAB_DIR", HERE)
sys.path.insert(0, LAB)
from fx_adr74 import DOCS, RESULTS, build, check, conn, ins, new, reset_and_load, trial  # noqa: E402

# The personal-name pattern of rule 2: a column whose name matches it is in the catalog or in the exclusions.
RX = re.compile(r"(email|phone|address|tax_id|account_number|holder_name|display_name|^login$|counterparty|sender_|recipient|partner_name"
                r"|_name_text$|contact_name|custom_values|^body|body_text|request_text|question_text|signature)")
H1 = "table_name,column_name,subject_kind,category,label,condition,store_class,erasure_action,retention_class,note".split(",")
H2 = "table_name,column_name,reason".split(",")
CLASSES = {"master_data", "accounting_document", "crm_interaction", "message", "agent_log", "intake", "audit", "access_account",
           "analysis_text", "data_subject_request"}
ENUM = {
    "subject_kind": {"partner", "contact", "user", "employee", "requester", "other"},
    "category": {"identity", "contact", "financial", "online_identifier", "credential", "free_text", "snapshot"},
    "label": {"personal", "sensitive_personal"},
    "condition": {"always", "partner_is_person", "may_contain"},
    "store_class": {"master", "frozen_document", "append_only", "expiring"},
    "erasure_action": {"tokenize", "blank", "delete_row", "drop_with_partition", "keep"},
    "retention_class": CLASSES,
}
# Columns whose trailing comment contains the word "personal" but hold no personal data about a natural person.
COMMENT_ALLOW = {
    ("work_item", "details"): 'comment says "never personal free text" (negation)',
    ("user_account", "erased_at"): "erasure timestamp; the comment describes what erasure does",
    ("partner_email_domain", "erased_at"): "erasure timestamp; the comment says the domain column is personal",
    ("custom_field_definition", "is_personal_data"): "the marker flag itself, not a value",
    ("list_variant", "owner_user_id"): '"personal variant" means owned by one user, not personal data',
    ("list_variant", "shared_role_id"): '"personal" means not shared',
    ("list_variant", "is_default"): '"personal" means not shared',
    ("data_processing_permission", "data_class"): 'names the class "sensitive personal"; a configuration value',
}
DS64 = ("data_subject_state", "retention_rule", "data_erasure_entry", "personal_data_read_log", "personal_data_breach")
SKIP = re.compile(r"^(CONSTRAINT|PRIMARY|UNIQUE|FOREIGN|CHECK|EXCLUDE|LIKE)\b", re.I)


# ======================================================================= the DDL parse
def parse_ddl(files):
    """files: [(name, text)]. Returns {table: {column: (file, line, trailing comment)}} from the CREATE TABLE blocks.
    A trailing -- comment belongs to the item whose text ends on that line, or to the item that starts on it."""
    tables = {}
    for name, text in files:
        lines = text.split("\n")
        i = 0
        while i < len(lines):
            m = re.match(r"\s*CREATE TABLE (?:IF NOT EXISTS )?(\w+)\s*\(", lines[i])
            if not m:
                i += 1
                continue
            cols = tables.setdefault(m.group(1), {})
            items, cur, depth, j, first, done = [], ["", i + 1, ""], 1, i, True, False
            while j < len(lines) and not done:
                code, _, com = lines[j].partition("--")
                code = re.sub(r"'[^']*'", "''", code)
                pos = code.index("(") + 1 if first else 0
                first = False
                flushed_here, tail_started = None, False
                for ch in code[pos:]:
                    if ch == "(":
                        depth += 1
                        cur[0] += ch
                    elif ch == ")":
                        depth -= 1
                        if depth == 0:
                            items.append(cur); flushed_here = cur; done = True
                            break
                        cur[0] += ch
                    elif ch == "," and depth == 1:
                        items.append(cur); flushed_here = cur
                        cur = ["", j + 1, ""]
                        tail_started = False
                    else:
                        if not ch.isspace():
                            tail_started = True
                            if not cur[0].strip():
                                cur[1] = j + 1
                        cur[0] += ch
                if j > i and com:
                    target = cur if (tail_started and not done) else (flushed_here or cur)
                    target[2] += " " + com
                cur[0] += " "
                j += 1
            for item, ln, com in items:
                s = item.strip()
                if s and not SKIP.match(s):
                    mm = re.match(r'"?(\w+)"?\s+\S', s)
                    if mm:
                        cols.setdefault(mm.group(1), (name, ln, com.strip()))
            i = j
    return tables


def read_rows(text):
    r = csv.reader(io.StringIO(text))
    head = next(r)
    return head, [(n, row) for n, row in enumerate(r, start=2) if row]


def catalog_problems(tables, text1, text2):
    """The check of rule 2 over parsed DDL and the two catalog texts; returns (problems, file-1 keys, file-2 keys)."""
    errors = []
    h1, rows1 = read_rows(text1)
    h2, rows2 = read_rows(text2)
    if h1 != H1:
        errors.append(f"file 1 header is {h1}")
    if h2 != H2:
        errors.append(f"file 2 header is {h2}")
    s1, s2 = {}, {}
    for n, row in rows1:
        if len(row) != len(H1):
            errors.append(f"file 1 line {n}: {len(row)} fields")
            continue
        d = dict(zip(H1, row))
        key = (d["table_name"], d["column_name"])
        if key in s1:
            errors.append(f"file 1 line {n}: duplicate {key}")
        s1[key] = d
        for k, allowed in ENUM.items():
            if d[k] not in allowed:
                errors.append(f"file 1 line {n}: {k}={d[k]!r} not allowed")
        if d["erasure_action"] == "keep" and not d["note"].strip():
            errors.append(f"file 1 line {n}: keep without note")
        if d["store_class"] in ("frozen_document", "append_only") and d["erasure_action"] == "drop_with_partition":
            errors.append(f"file 1 line {n}: {d['store_class']} row erased by a partition drop")
    for n, row in rows2:
        if len(row) != len(H2):
            errors.append(f"file 2 line {n}: {len(row)} fields")
            continue
        key = (row[0], row[1])
        if key in s2:
            errors.append(f"file 2 line {n}: duplicate {key}")
        s2[key] = row[2]
        if not row[2].strip():
            errors.append(f"file 2 line {n}: empty reason")
    for t, c in list(s1) + list(s2):
        if t not in tables or c not in tables[t]:
            errors.append(f"not in DDL: {t}.{c}")
    for key in sorted(set(s1) & set(s2)):
        errors.append(f"in both files: {key}")
    for t, cols in tables.items():
        for c, (f, ln, com) in cols.items():
            key = (t, c)
            if RX.search(c) and key not in s1 and key not in s2:
                errors.append(f"personal name in neither file: {f}:{ln} {t}.{c}")
            if not RX.search(c) and key in s2:
                errors.append(f"exclusion of a column the pattern does not match: {t}.{c}")
            low = re.sub(r"not personal", "", com, flags=re.I)
            if re.search(r"\bpersonal\b", low, re.I) and key not in s1 and key not in COMMENT_ALLOW:
                errors.append(f"comment says personal, not in the catalog: {f}:{ln} {t}.{c}")
        if "custom_values" in cols and (t, "custom_values") not in s1:
            errors.append(f"custom_values without a catalog row: {t}")
    for (t, c) in COMMENT_ALLOW:
        if t not in tables or c not in tables[t]:
            errors.append(f"allow-list entry not in DDL: {t}.{c}")
        elif (t, c) in s1:
            errors.append(f"allow-listed and in the catalog: {t}.{c}")
    return errors, s1, s2


def ddl_files(docs):
    return [(os.path.basename(p), open(p, encoding="utf-8").read()) for p in sorted(glob.glob(os.path.join(docs, "design", "*.sql")))]


def read_dicts(name):
    return list(csv.DictReader(open(os.path.join(DOCS, "catalogs", name), encoding="utf-8")))


# ======================================================================= reference functions (rule 9)
def add_months(d, n):
    y, m = divmod(d.month - 1 + n, 12)
    return date(d.year + y, m + 1, min(d.day, 28))


def retention_action(rule, start, today, has_open_item=False):
    """rule: None or {is_verified, block_after_months, destroy_after_months}. Returns 'keep', 'block' or 'destroy'."""
    if rule is None or not rule["is_verified"] or has_open_item:
        return "keep"
    if rule["destroy_after_months"] is not None and today >= add_months(start, rule["destroy_after_months"]):
        return "destroy"
    if rule["block_after_months"] is not None and today >= add_months(start, rule["block_after_months"]):
        return "block"
    return "keep"


# ======================================================================= P, C
FILES = ddl_files(DOCS)
TABLES = parse_ddl(FILES)
ncols = sum(len(c) for c in TABLES.values())
check("P01 every design/*.sql file parses, DS-64-personal-data.sql among them, with the five tables of ADR-0079",
      len(FILES) >= 15 and "DS-64-personal-data.sql" in dict(FILES) and all(t in TABLES for t in DS64), f"{len(FILES)} files, {len(TABLES)} tables, {ncols} columns")
F1 = open(os.path.join(DOCS, "catalogs", "personal-data-fields.csv"), encoding="utf-8").read()
F2 = open(os.path.join(DOCS, "catalogs", "personal-data-exclusions.csv"), encoding="utf-8").read()
errs, S1, S2 = catalog_problems(TABLES, F1, F2)


def errs_of(prefixes):
    return [e for e in errs if e.startswith(prefixes)]


check("C01 both catalog files have their headers and only the enum values of rule 1", not errs_of(("file 1 header", "file 2 header")) and not [e for e in errs if "not allowed" in e or "fields" in e],
      f"{len(S1)} catalog rows, {len(S2)} exclusions")
check("C02 every catalog and exclusion row names a real DDL column", not errs_of(("not in DDL",)), errs_of(("not in DDL",))[:5])
check("C03 no duplicate row in either file and no pair in both files", not [e for e in errs if "duplicate" in e] and not errs_of(("in both files",)))
pattern_hits = sum(1 for t, cols in TABLES.items() for c in cols if RX.search(c))
check("C04 every column whose name matches the personal-name pattern is in exactly one file; the exclusions hold only such columns",
      not errs_of(("personal name in neither file", "exclusion of a column")), errs_of(("personal name in neither file", "exclusion of a column"))[:5] or f"{pattern_hits} matching columns")
check(f"C05 every column whose trailing comment says personal is in the catalog, except the {len(COMMENT_ALLOW)} allow-listed columns, each with a reason",
      not errs_of(("comment says personal", "allow-list", "allow-listed")) and all(COMMENT_ALLOW.values()), errs_of(("comment says personal", "allow-list", "allow-listed"))[:5])
cv_tables = sorted(t for t, cols in TABLES.items() if "custom_values" in cols)
check("C06 every table with custom_values has a catalog row for it (ADR-0074 rule 8)", cv_tables and not errs_of(("custom_values without",)), cv_tables)
check("C07 frozen-document and append-only rows never rely on a partition drop; every keep row has its reason", not [e for e in errs if "partition drop" in e or "keep without" in e])
used = {d["retention_class"] for d in S1.values()}
m64 = re.search(r"ck_retention_rule_retention_class CHECK \(retention_class IN \(([^)]*)\)", re.sub(r"\s+", " ", dict(FILES)["DS-64-personal-data.sql"]))
ddl_classes = set(re.findall(r"'(\w+)'", m64.group(1))) if m64 else set()
adr = open(os.path.join(DOCS, "adr", "0079-personal-data-protection.md"), encoding="utf-8").read()
m_adr = re.search(r"The classes are (.*?)\.\n", adr)
adr_classes = set(re.findall(r"`(\w+)`", m_adr.group(1))) if m_adr else set()
check("C08 the retention classes are the ten of rule 9: the catalog uses only them, and the ADR and DS-64's CHECK list the same ten",
      len(CLASSES) == 10 and used <= CLASSES and ddl_classes == CLASSES and adr_classes == CLASSES, sorted(used))
check("C09 the catalog checker passes as a whole", not errs, errs[:8])

# ======================================================================= S: self-tests
F64 = dict(FILES)["DS-64-personal-data.sql"]
broken_ddl = [(n, t) for n, t in FILES if n != "DS-20-master-data.sql"] + [
    ("DS-20-master-data.sql", dict(FILES)["DS-20-master-data.sql"] + "\nCREATE TABLE lab_selftest (\n    id uuid PRIMARY KEY,\n    mobile_phone text\n);\n")]
e1, _, _ = catalog_problems(parse_ddl(broken_ddl), F1, F2)
check("S01 a DDL column with a personal name and no catalog row is caught", any("lab_selftest.mobile_phone" in e and "neither file" in e for e in e1), [e for e in e1 if "lab_selftest" in e])
e2, _, _ = catalog_problems(TABLES, F1.rstrip("\n") + "\npartner,nickname,partner,identity,personal,partner_is_person,master,tokenize,master_data,\n", F2)
check("S02 a catalog row naming a missing column is caught", "not in DDL: partner.nickname" in e2, [e for e in e2 if "nickname" in e])
e3, _, _ = catalog_problems(TABLES, F1, F2.rstrip("\n") + "\npartner,tax_id,lab self-test\n")
check("S03 a pair in both files is caught", "in both files: ('partner', 'tax_id')" in e3, [e for e in e3 if "both" in e])
e4, _, _ = catalog_problems(TABLES, F1.replace("partner,custom_values,", "partner,custom_values_x,", 1), F2)
check("S04 a table with custom_values but no catalog row for it is caught", "custom_values without a catalog row: partner" in e4)

# ======================================================================= K: the other catalogs
INV = {r["code"]: r for r in read_dicts("invariants.csv")}
EC = {r["code"]: r for r in read_dicts("edge-cases.csv")}
WIK = {r["code"]: r for r in read_dicts("work-item-kinds.csv")}
WCK = {r["code"]: r for r in read_dicts("work-case-kinds.csv")}
want_inv = {"INV-890": "personal_data_catalog_complete", "INV-891": "blocked_subject_not_processed", "INV-892": "destroyed_subject_is_blank",
            "INV-893": "erasure_changes_catalog_columns_only", "INV-894": "no_destruction_without_rule"}
want_ec = {"EC-350": "erasure_request_during_retention", "EC-351": "destruction_after_retention", "EC-352": "restore_before_erasure",
           "EC-353": "blocked_subject_refused", "EC-354": "class_without_rule"}
check("K01 INV-890 to INV-894 are in the catalog with the ADR's names, source ADR-0079",
      all(INV.get(k, {}).get("name") == v and INV[k]["source"].startswith("ADR-0079") for k, v in want_inv.items()))
check("K02 EC-350 to EC-354 are in the catalog with the ADR's names, first executable step 5; EC-353 expects data_subject_blocked",
      all(EC.get(k, {}).get("name") == v and EC[k]["first_executable_step"] == "5" for k, v in want_ec.items())
      and "must_reject:data_subject_blocked" in EC.get("EC-353", {}).get("expected_outcome", ""))
check("K03 work item kind personal_data_incident_suspected (audit, person) and case kind personal_data_breach (audit, no trigger, resolved by a person)",
      WIK.get("personal_data_incident_suspected", {}).get("resolution") == "person" and WIK["personal_data_incident_suspected"]["module"] == "audit"
      and WCK.get("personal_data_breach", {}).get("trigger_work_item_kind") == "" and WCK["personal_data_breach"]["resolution"] == "person"
      and WCK["personal_data_breach"]["module"] == "audit")
AREAS = {r["code"]: r for r in read_dicts("authorization-areas.csv")}
TPL = {r["template"] for r in read_dicts("role-templates.csv")}
LV = {(r["template"], r["node"]): r["level"] for r in read_dicts("role-template-levels.csv")}
check("K04 capability read_blocked_personal_data sits on its own leaf blocked_personal_data, which every role template sets to none, the owner included",
      AREAS.get("blocked_personal_data", {}).get("parent_code") == "administration" and "read_blocked_personal_data" in AREAS["blocked_personal_data"]["meaning"]
      and all(LV.get((t, "blocked_personal_data")) == "none" for t in TPL), sorted(t for t in TPL if LV.get((t, "blocked_personal_data")) != "none"))
flat = {n: re.sub(r"\s+", " ", t) for n, t in FILES}
check("K05 sensitive_personal is a field class of role assignments and custom fields; no agent type version may hold it",
      "ck_role_assignment_field_classes CHECK (field_classes <@ ARRAY['cost', 'margin', 'sensitive_personal']" in flat["DS-15-access.sql"]
      and "ck_custom_field_definition_field_class CHECK (field_class IN ('cost', 'margin', 'sensitive_personal'))" in flat["DS-20-master-data.sql"]
      and "ck_agent_type_version_field_classes CHECK (field_classes <@ ARRAY['cost', 'margin']::text[])" in flat["DS-05-platform.sql"])
check("K06 the processing log takes the kind retention, one entry per subject and run of the retention job (rule 9)",
      "'erasure', 'retention')" in flat["DS-35-crm.sql"])

# ======================================================================= R: reference functions
verified = {"is_verified": True, "block_after_months": 12, "destroy_after_months": 120}
start = date(2016, 1, 31)
check("R01 no rule or an unverified rule: the job neither blocks nor destroys (EC-354)",
      retention_action(None, start, date(2030, 1, 1)) == "keep" and retention_action(dict(verified, is_verified=False), start, date(2030, 1, 1)) == "keep")
check("R02 a verified rule blocks after its block period and destroys after its destruction period; an open item keeps the subject",
      retention_action(verified, start, date(2016, 6, 1)) == "keep" and retention_action(verified, start, date(2017, 2, 1)) == "block"
      and retention_action(verified, start, date(2026, 2, 1)) == "destroy" and retention_action(verified, start, date(2026, 2, 1), has_open_item=True) == "keep")

# ======================================================================= X: the DDL (--load)
if "--load" in sys.argv:
    raw_dsn = os.environ.get("NATIVEFLOWS_LAB_DSN", "host=127.0.0.1 port=5561 dbname=nativeflows_lab user=lab")
    n_tables = reset_and_load(raw_dsn, DOCS)
    check("X00 load_all.py loads every DDL file with DS-64-personal-data.sql", n_tables > 0, f"{n_tables} tables")
    c = conn()
    c.autocommit = True
    X = c.execute
    shape = {}
    for t in DS64:
        cols = {r[0]: r[1] for r in X("select column_name, is_nullable from information_schema.columns where table_schema='nativeflows' and table_name=%s", (t,)).fetchall()}
        uq = X("""select count(*) from pg_constraint k join pg_class r on r.oid = k.conrelid where r.relname = %s and k.contype = 'u'
                  and (select array_agg(a.attname::text order by a.attname) from pg_attribute a where a.attrelid = r.oid and a.attnum = any (k.conkey)) = array['company_id', 'id']""", (t,)).fetchone()[0]
        forced = X("select relrowsecurity and relforcerowsecurity from pg_class where relname=%s and relnamespace='nativeflows'::regnamespace", (t,)).fetchone()
        shape[t] = ("company_id" in cols, cols.get("recorded_at") == "NO", uq == 1, bool(forced and forced[0]))
    check("X01 the five tables exist with company_id, recorded_at NOT NULL, UNIQUE (company_id, id) and forced row-level security",
          all(v == (True, True, True, True) for v in shape.values()) and len(shape) == 5, shape)
    nullable = {t for t in DS64 if X("select is_nullable from information_schema.columns where table_schema='nativeflows' and table_name=%s and column_name='company_id'", (t,)).fetchone()[0] == "YES"}
    check("X02 company_id is nullable only in data_subject_state and data_erasure_entry (user account subjects)", nullable == {"data_subject_state", "data_erasure_entry"}, sorted(nullable))

    I = build(c)
    NOW = "2026-11-21T10:00:00+00"

    def state(cx, **o):
        v = dict(id=new(), company_id=I["co"], subject_table="partner", subject_id=new(), state="blocked", cause="request", blocked_at=NOW); v.update(o)
        return ins(cx, "data_subject_state", **v)
    u_subject = new()
    state(c, company_id=None, subject_table="user_account", subject_id=u_subject, cause="retention")
    check("X03 a user account subject is stored without company_id", X("select count(*) from data_subject_state where subject_id=%s and company_id is null", (u_subject,)).fetchone()[0] == 1)
    trial("X04 a partner subject needs company_id", lambda cx: state(cx, company_id=None), "ck_data_subject_state_company")
    trial("X05 a destroyed subject needs destroyed_at (state without dates)", lambda cx: state(cx, state="destroyed"), "ck_data_subject_state_destroyed")
    trial("X06 blocked_at is always set", lambda cx: state(cx, blocked_at=None), "blocked_at")
    trial("X07 destroyed_at is never before blocked_at", lambda cx: state(cx, state="destroyed", destroyed_at="2026-11-20T10:00:00+00"), "ck_data_subject_state_dates")
    trial("X08 a blocked subject has no destroyed_at", lambda cx: state(cx, destroyed_at=NOW), "ck_data_subject_state_destroyed")
    trial("X09 the subject is a partner, a contact or a user account", lambda cx: state(cx, subject_table="employee_profile"), "ck_data_subject_state_subject_table")
    trial("X10 one row per subject", lambda cx: state(cx, company_id=None, subject_table="user_account", subject_id=u_subject, cause="retention"),
          "data_subject_state_subject_table_subject_id_key")
    trial("X11 the request is a real data subject request", lambda cx: state(cx, data_subject_request_id=new()), "data_subject_request_id_fkey")

    def rule(cx, **o):
        v = dict(id=new(), company_id=I["co"], retention_class="crm_interaction", start_event="relationship_ended", block_after_months=12,
                 destroy_after_months=60, source="package", package_rule_ref="lab.crm_interaction", is_verified=False); v.update(o)
        return ins(cx, "retention_rule", **v)
    rule(c)
    trial("X12 destruction never comes before blocking (destroy before block)", lambda cx: rule(cx, retention_class="message", block_after_months=24, destroy_after_months=12), "ck_retention_rule_order")
    trial("X13 a period is never negative", lambda cx: rule(cx, retention_class="message", block_after_months=-1), "ck_retention_rule_block_after_months")
    trial("X14 an unknown retention class is refused", lambda cx: rule(cx, retention_class="payroll"), "ck_retention_rule_retention_class")
    trial("X15 an unknown start event is refused", lambda cx: rule(cx, retention_class="message", start_event="contract_signed"), "ck_retention_rule_start_event")
    trial("X16 two rules for one class in a company are refused", lambda cx: rule(cx), "retention_rule_company_id_retention_class_key")
    trial("X17 a package rule names the package rule it comes from", lambda cx: rule(cx, retention_class="message", package_rule_ref=None), "ck_retention_rule_package_ref")
    rule(c, retention_class="message", source="company", package_rule_ref=None, block_after_months=None, destroy_after_months=None)
    check("X18 a company rule needs no package reference, and both periods may be null", True)

    def entry(cx, **o):
        v = dict(id=new(), company_id=I["co"], subject_table="partner", subject_id=I["sold"], target_table="partner", target_row_id=I["sold"],
                 column_names=["name"], action="tokenize", cause="request", command_id=new(), executed_at=NOW); v.update(o)
        return ins(cx, "data_erasure_entry", **v)
    trial("X19 an erasure entry names at least one column (empty column_names)", lambda cx: entry(cx, column_names=[]), "ck_data_erasure_entry_column_names")
    trial("X20 the action is tokenize, blank or delete_row", lambda cx: entry(cx, action="drop_with_partition"), "ck_data_erasure_entry_action")
    trial("X21 the cause is request, retention or restore_replay", lambda cx: entry(cx, cause="manual"), "ck_data_erasure_entry_cause")
    trial("X22 a company row's entry needs company_id", lambda cx: entry(cx, company_id=None), "ck_data_erasure_entry_company")

    def read(cx, **o):
        v = dict(id=new(), company_id=I["co"], user_account_id=I["user"], query_name="ListPartner", read_kind="blocked_subject", row_count=1,
                 field_names=["partner.name"], read_at=NOW); v.update(o)
        return ins(cx, "personal_data_read_log", **v)
    rl = read(c, subject_table="partner", subject_id=I["sold"])
    trial("X23 a read log row's row count is never negative", lambda cx: read(cx, row_count=-1), "ck_personal_data_read_log_row_count")
    trial("X24 the read kind is sensitive_field, blocked_subject or export", lambda cx: read(cx, read_kind="ordinary"), "ck_personal_data_read_log_read_kind")
    trial("X25 subject table and subject ID come together", lambda cx: read(cx, subject_table="partner"), "ck_personal_data_read_log_subject")

    wc = new()
    ins(c, "work_case", id=wc, company_id=I["co"], kind="personal_data_breach", open_key=str(wc), state="open", owner_kind="role", owner_role="company_owner",
        due_date="2026-11-22", title_key="work_case.personal_data_breach.title", version=1, recorded_at=NOW)

    def breach(cx, **o):
        v = dict(id=new(), company_id=I["co"], work_case_id=wc, discovered_at=NOW, categories=["contact", "identity"], subject_kinds=["contact"],
                 subject_count_estimate=40, containment="Token revoked; integration disabled."); v.update(o)
        return ins(cx, "personal_data_breach", **v)
    breach(c)
    trial("X26 one breach per work case (two breaches for one case)", lambda cx: breach(cx), "personal_data_breach_work_case_id_key")
    wc2 = new()
    ins(c, "work_case", id=wc2, company_id=I["co"], kind="personal_data_breach", open_key=str(wc2), state="open", owner_kind="role", owner_role="company_owner",
        due_date="2026-11-22", title_key="work_case.personal_data_breach.title", version=1, recorded_at=NOW)
    trial("X27 categories are the catalog's seven", lambda cx: breach(cx, work_case_id=wc2, categories=["health"]), "ck_personal_data_breach_categories")
    trial("X28 subject kinds are the catalog's six", lambda cx: breach(cx, work_case_id=wc2, subject_kinds=["visitor"]), "ck_personal_data_breach_subject_kinds")
    trial("X29 a closed breach needs closed_at, and an open one has none", lambda cx: breach(cx, work_case_id=wc2, state="closed"), "ck_personal_data_breach_closed")
    trial("X30 the breach ends no earlier than it began", lambda cx: breach(cx, work_case_id=wc2, occurred_from=NOW, occurred_to="2026-11-01T00:00:00+00"), "ck_personal_data_breach_occurred")
    trial("X31 the work case is of the breach's company (company-composite key)", lambda cx: breach(cx, company_id=I["co2"], work_case_id=wc2), "personal_data_breach_company_id_work_case_id_fkey")

    # ---- a simulated erasure, driven by the catalog: an individual partner, its address and its contact
    p, adr_id, ct = new(), new(), new()
    X("insert into partner (id, company_id, code, name, legal_name, tax_id, partner_kind, country, custom_values) values (%s,%s,'P-ERASE','Sample Person','Sample Person','0000000001','individual','VN','{\"nickname\": \"x\"}')", (p, I["co"]))
    X("insert into partner_address (id, company_id, partner_id, kind, address_lines, postal_code, country) values (%s,%s,%s,'billing',%s,'00000','VN')", (adr_id, I["co"], p, ["1 Sample Street"]))
    X("insert into contact (id, company_id, partner_id, name, email, phone) values (%s,%s,%s,'Sample Contact','sample@example.invalid','+0000000000')", (ct, I["co"], p))
    CAT = {}
    for (t, col), d in S1.items():
        CAT.setdefault(t, []).append((col, d["erasure_action"]))
    cmd = new()
    targets = (("partner", p), ("partner_address", adr_id), ("contact", ct))
    sets_done = {}
    with c.transaction():
        for t, rid in targets:
            info = {r[0]: (r[1], r[2]) for r in X("select column_name, is_nullable, data_type from information_schema.columns where table_schema='nativeflows' and table_name=%s", (t,)).fetchall()}
            by_action = {}
            for col, action in CAT.get(t, []):
                by_action.setdefault(action, []).append(col)
            for action, cols in sorted(by_action.items()):
                assigns = []
                for col in cols:
                    nullable, dtype = info[col]
                    if action == "tokenize":
                        assigns.append(f"{col} = 'erased-' || left(md5(id::text), 12)")
                    elif dtype == "jsonb":
                        assigns.append(f"{col} = '{{}}'::jsonb")
                    elif nullable == "YES":
                        assigns.append(f"{col} = null")
                    elif dtype == "ARRAY":
                        assigns.append(f"{col} = '{{}}'")
                    else:
                        assigns.append(f"{col} = ''")
                X(f"update {t} set {', '.join(assigns)} where id = %s", (rid,))
                entry(c, subject_table="partner", subject_id=p, target_table=t, target_row_id=rid, column_names=sorted(cols), action=action, command_id=cmd)
                sets_done[(t, action)] = sorted(cols)
        X("insert into data_subject_state (id, company_id, subject_table, subject_id, state, cause, blocked_at, destroyed_at) values (%s,%s,'partner',%s,'destroyed','retention',%s,%s)",
          (new(), I["co"], p, "2025-01-01T00:00:00+00", NOW))
    # INV-892 in SQL: for the destroyed subject, every catalog column of its rows holds its action's result, with an entry per rewritten row
    bad = []
    for t, rid in targets:
        for col, action in CAT.get(t, []):
            v = X(f"select {col}::text from {t} where id=%s", (rid,)).fetchone()[0]
            if action == "tokenize" and not (v or "").startswith("erased-"):
                bad.append(f"{t}.{col}={v}")
            if action == "blank" and v not in (None, "", "{}"):
                bad.append(f"{t}.{col}={v}")
        n_entries = X("select count(*) from data_erasure_entry where subject_id=%s and target_table=%s and target_row_id=%s", (p, t, rid)).fetchone()[0]
        if n_entries == 0:
            bad.append(f"no entry for {t}")
    check("X32 INV-892 in SQL: the destroyed partner's catalog columns in partner, partner_address and contact are blank or tokenized, each row with its erasure entry",
          not bad and len(sets_done) >= 4, bad or sets_done)
    cov = X("""select count(*) from data_erasure_entry e where e.subject_id = %s
               and exists (select 1 from data_subject_state s where s.subject_table = e.subject_table and s.subject_id = e.subject_id and s.state = 'destroyed')""", (p,)).fetchone()[0]
    check("X33 every erasure entry of the partner belongs to a subject in state destroyed", cov == len(sets_done), cov)
    cols = X("select column_name, data_type, udt_name from information_schema.columns where table_schema='nativeflows' and table_name='data_erasure_entry'").fetchall()
    codes = {"subject_table", "target_table", "action", "cause"}
    arrays = {"column_names": "_text", "target_row_key": "_text"}
    payload = [n for n, dt, udt in cols if dt in ("jsonb", "json", "bytea") or (dt == "text" and n not in codes) or (dt == "ARRAY" and arrays.get(n) != udt)]
    check("X34 erasure entries carry no values: no jsonb, json or bytea column, text only for the four code columns, arrays only of column names and key parts",
          not payload and len(cols) >= 14, payload or f"{len(cols)} columns")
    trial("X35 data_erasure_entry refuses UPDATE", lambda cx: cx.execute("update data_erasure_entry set column_names='{tax_id}' where subject_id=%s", (p,)), "never updated or deleted")
    trial("X36 data_erasure_entry refuses DELETE", lambda cx: cx.execute("delete from data_erasure_entry where subject_id=%s", (p,)), "never updated or deleted")
    trial("X37 personal_data_read_log refuses UPDATE", lambda cx: cx.execute("update personal_data_read_log set row_count=0 where id=%s", (rl,)), "never updated or deleted")
    trial("X38 personal_data_read_log refuses DELETE", lambda cx: cx.execute("delete from personal_data_read_log where id=%s", (rl,)), "never updated or deleted")
    ins(c, "personal_data_processing_log", id=new(), company_id=I["co"], processing_kind="retention", subject_table="partner", subject_id=p, recorded_at=NOW)
    check("X39 the processing log takes one retention entry for the subject (rule 9)",
          X("select count(*) from personal_data_processing_log where subject_id=%s and processing_kind='retention'", (p,)).fetchone()[0] == 1)
    c.close()

passed = sum(1 for ok_, *_ in RESULTS if ok_)
print(f"{passed} / {len(RESULTS)} passed")
sys.exit(0 if passed == len(RESULTS) else 1)
