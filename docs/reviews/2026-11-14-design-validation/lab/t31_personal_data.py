"""Scenario: personal data protection in the core (ADR-0079). Not product code.

Run: python t31_personal_data.py [--load]
  Pure checks need no database. With --load, NATIVEFLOWS_LAB_DSN must name a throwaway database: load_all.py drops and
  rebuilds schemas nativeflows and types there with every DDL file of NATIVEFLOWS_DOCS/design (default ~/Projects/NativeFlows/docs).

P: the DDL parse: every design/*.sql file, its CREATE TABLE blocks, columns and trailing comments.
C: the catalog against the DDL (rule 2; INV-890): both files' headers and enum values; every catalog pair is a real column;
   no duplicate and no pair in both files; every column whose name matches the personal-name pattern (personal words, and the
   free-text words note, comment, remark, description, reason and every name column, except reference and code columns) is
   in exactly one file, an exclusion row with column * excluding a whole table that has no catalog row, and the exclusions
   hold only such columns; every column whose trailing comment says personal is in the catalog, except the
   allow-list below, each entry with its reason; every table with custom_values has a catalog row for it (ADR-0074 rule 8);
   frozen and append-only rows never rely on a partition drop; every keep row has a note; no blank action on a column of a
   primary key, UNIQUE constraint or unique index (rule 1); for every blank row, rule 1's result (NULL or the type's marker)
   passes the CHECKs that name the column and a marker result is named in the note; a * exclusion lists the matching columns
   it covers; the retention classes are the ten
   of rule 9, the same in the catalog, in DS-64's retention_rule CHECK and in the ADR.
S: self-tests: broken variants fed to the same checker (a DDL column with a personal name and no catalog row, a catalog row
   naming a missing column, a pair in both files, a table with custom_values and no row, a new customer_note and driver_name
   column, a blank action on a unique key column, a * exclusion of a table with catalog rows, a CHECK refusing both NULL and the
   marker, a column added to a * table), each caught.
K: the other catalogs and the field class (rules 5, 11, 15, 16): INV-890 to INV-894, EC-350 to EC-354, the work item kind
   personal_data_incident_suspected, the case kind personal_data_breach, the leaf blocked_personal_data at full for the owner
   template and none for every other, sensitive_personal suggested only to the owner template, sensitive_personal in the role
   assignment and custom field CHECKs and not in the agent type version CHECK, the processing log kind retention.
R: reference functions for the retention job (rule 9; EC-354): no verified rule, no destruction; blocking before destruction.
With --load: the five tables of DS-64-personal-data.sql exist with company_id, recorded_at, UNIQUE (company_id, id) and forced
row-level security; each CHECK and key refuses a bad row (released subjects, package and company rules, actor kinds of the read log
included); the append-only tables refuse UPDATE and DELETE; a simulated erasure of
a partner, its address and its contact, driven by the catalog, leaves blank or tokenized columns and custom_values without its
personal keys (clear_keys), one data_erasure_entry per rewritten row (INV-892 in SQL) and entries whose columns carry no values
(no jsonb, text only for codes and names); document_version has the nullable erased_at of rule 6.
E: the erasure exception of rule 7 in the DDL text: every refusing trigger that names erasure columns names exactly its
   table's frozen and append-only catalog columns; posted headers and lines, document_version and the journal take it; the
   only uncovered guarded tables are the five with guard functions of their own (a follow-up).
With --load, the exception (S2): a posted document and its version change only catalog columns (and erased_at), only under
the erasure marker, never by delete; the journal triggers pass note and description; journal_reject_change,
document_check_frozen and platform_reject_change behave so on a scratch table. The marker must name an erasure command's
idempotency record of this transaction and of the changed row's company (X55 to X62, X71 to X73, X84 to X87); a key list
forbids a whole blank (X81 to X83); recorded_at is the system's on insert (X88).
Y (with --load, S2 closure of 2026-11-21): the five entries the adversarial fixes left: (a) uom's shared-reference policies
   (Y01 to Y05), (d) the company table's policies on id (Y06), (b) a CHECK beside every composite key from a table whose
   company_id can be null (Y07 to Y11), (c) the setting_value tie-breaker by id (Y12, Y13), (e) only erasure_command_record()
   writes the two erasure scopes of idempotency_record (Y14 to Y19).
Z (with --load, S2 adversarial review S3, N1, N3, N4): the conventions on the catalog of the full load: recorded_at, the id key,
the set_recorded_at triggers, forced row-level security with both policies, TRUNCATE guards, pinned search_path.
Not covered: who may run an erasure (the command layer's permission check). Commands, the retention job, masking, the read
log writers, the erasure journal outside the database and ReapplyErasures are not covered either.
The blank check reads these CHECK forms only: nullness pairings "(x) = (col IS [NOT] NULL)", "col IS NOT NULL OR ...",
num_nonnulls, coalesce(length(col), 0) > 0, length(col) > 0 or BETWEEN 1, col <> '', col ~ 'pattern', jsonb_typeof,
jsonb_array_length or cardinality > 0, and the erasure flags erased_at and body_removed_at. Other forms (IN lists, comparisons
with other columns, conditions across tables, triggers) are not evaluated; a ~ pattern is assumed to refuse ''.
"""
import csv, glob, io, os, re, sys
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
LAB = os.environ.get("NATIVEFLOWS_LAB_DIR", HERE)
sys.path.insert(0, LAB)
from fx_adr74 import DOCS, RESULTS, build, check, conn, ins, new, reset_and_load, trial  # noqa: E402
from lab import erasure_marker  # noqa: E402

# The personal-name pattern of rule 2: a column whose name matches it is in the catalog or in the exclusions. Free-text names
# (note, comment, remark, description, reason) and every name column are in it (ADR-0079 rule 2, review fix G9).
# The free-text words do not match a reference or a code column (a name ending in _id, _ids, _kind or _code).
class _Pattern:
    BASE = re.compile(r"(email|phone|address|tax_id|account_number|holder_name|display_name|^login$|counterparty|sender_|recipient|partner_name"
                      r"|_name_text$|contact_name|custom_values|^body|body_text|request_text|question_text|signature)")
    TEXT = re.compile(r"(note|comment|remark|description|reason|_name$|^name$)")
    REF = re.compile(r"(_id|_ids|_kind|_code)$")

    def search(self, c):
        return bool(self.BASE.search(c) or (self.TEXT.search(c) and not self.REF.search(c)))


RX = _Pattern()
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
    "erasure_action": {"tokenize", "blank", "clear_keys", "delete_row", "drop_with_partition", "keep"},
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
def parse_ddl(files, uniques=None, details=None):
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
                code = re.sub(r"'[^']*'", lambda q: re.sub(r"[(),]", "_", q.group(0)), code)   # literals kept, without parens or commas
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
                if details is not None:
                    dt = details.setdefault(m.group(1), {"cols": {}, "checks": []})
                    if re.match(r"(CONSTRAINT\s+\w+\s+)?CHECK\b", s, re.I):
                        dt["checks"].append(re.sub(r"\s+", " ", s))
                    elif s and not SKIP.match(s):
                        cm = re.match(r'"?(\w+)"?\s+(.*)', s, re.S)
                        if cm:
                            dt["cols"].setdefault(cm.group(1), re.sub(r"\s+", " ", cm.group(2)))
                            ck = re.search(r"\bCHECK\s*\(.*", cm.group(2), re.S)
                            if ck:
                                dt["checks"].append(re.sub(r"\s+", " ", ck.group(0)))
                key = re.match(r"(?:CONSTRAINT\s+\w+\s+)?(?:UNIQUE(?:\s+NULLS\s+NOT\s+DISTINCT)?|PRIMARY\s+KEY)\s*\(([^)]*)\)", s, re.I)
                if key and uniques is not None:
                    uniques.setdefault(m.group(1), []).append({w.strip() for w in key.group(1).split(",")})
                if s and not SKIP.match(s):
                    mm = re.match(r'"?(\w+)"?\s+\S', s)
                    if mm:
                        cols.setdefault(mm.group(1), (name, ln, com.strip()))
                        if uniques is not None and re.search(r"\b(UNIQUE|PRIMARY\s+KEY)\b", re.sub(r"CHECK\s*\(.*", "", s), re.I):
                            uniques.setdefault(m.group(1), []).append({mm.group(1)})
            i = j
        if uniques is not None:
            for mi in re.finditer(r"CREATE UNIQUE INDEX (?:IF NOT EXISTS )?\w+ ON (\w+)\s*(?:USING \w+\s*)?\(", text):
                depth, k = 1, mi.end()
                while depth and k < len(text):
                    depth += {"(": 1, ")": -1}.get(text[k], 0)
                    k += 1
                uniques.setdefault(mi.group(1), []).append(set(re.findall(r"\b([a-z_][a-z0-9_]*)\b", text[mi.end():k - 1])))
    return tables


def parse_uniques(files):
    """{table: [set of column names]} of every PRIMARY KEY, UNIQUE constraint and unique index (expression words included)."""
    uniques = {}
    parse_ddl(files, uniques)
    return uniques


def read_rows(text):
    r = csv.reader(io.StringIO(text))
    head = next(r)
    return head, [(n, row) for n, row in enumerate(r, start=2) if row]


# Columns the destruction path sets in the same update as the blanking (rule 1): a CHECK disjunct "<flag> IS NOT NULL" holds
# after erasure, and a pairing with "<flag> IS NULL" asks for NULL.
ERASE_FLAGS = r"(erased_at|body_removed_at)"


def blank_result(col, coltext, checks):
    """Rule 1's result of blank for one column: ('null' | marker, reason) or (None, reason) when a CHECK refuses both.
    coltext: the column's definition after its name; checks: the CHECK texts of its table. Forms read: nullness pairings
    "(x) = (col IS [NOT] NULL)", "col IS NOT NULL OR ...", coalesce(length(col), 0) > 0, length(col) > 0 or BETWEEN 1,
    col <> '', col ~ 'pattern', jsonb_typeof(col) = '...', jsonb_array_length / cardinality > 0, and the erasure flags."""
    c = re.escape(col)
    typ = coltext.split()[0].lower() if coltext.split() else ""
    nullable = not re.search(r"\bNOT\s+NULL\b|\bPRIMARY\s+KEY\b", coltext, re.I)
    mine = [k for k in checks if re.search(rf"\b{c}\b", k)]
    null_refused, marker_refused, why = False, False, []
    jtype = None
    for k in mine:
        jt = re.search(rf"jsonb_typeof\(\s*{c}\s*\)\s*=\s*'(\w+)'", k)
        if jt:
            jtype = jt.group(1)
        if re.search(rf"\b{ERASE_FLAGS}\s+IS\s+NOT\s+NULL", k, re.I):
            continue                                                   # holds once the flag is set
        if re.search(rf"\(\s*{ERASE_FLAGS}\s+IS\s+NULL\s*\)\s*=\s*\(\s*{c}\s+IS\s+NOT\s+NULL\s*\)|{ERASE_FLAGS}\s+IS\s+NULL\s+OR\s+{c}\s+IS\s+NULL", k, re.I):
            marker_refused = True; why.append("NULL once erased")
            continue
        if (re.search(rf"=\s*\(\s*{c}\s+IS\s+(NOT\s+)?NULL\s*\)|\(\s*{c}\s+IS\s+(NOT\s+)?NULL\s*\)\s*=", k, re.I)
                or re.search(rf"\b{c}\s+IS\s+NOT\s+NULL\s+OR\b|\bOR\s+{c}\s+IS\s+NOT\s+NULL\b|CHECK\s*\(\s*{c}\s+IS\s+NOT\s+NULL\s*\)", k, re.I)
                or re.search(rf"num_nonnulls\([^)]*\b{c}\b", k, re.I)):
            null_refused = True; why.append("nullness tied")
        if re.search(rf"coalesce\(\s*(length|char_length)\(\s*(btrim\(\s*)?{c}\b", k, re.I):
            null_refused = marker_refused = True; why.append("non-empty when its condition holds")
        elif re.search(rf"(length|char_length)\(\s*(btrim\(\s*)?{c}\s*\)\s*\)?\s*(>\s*0|>=\s*1|BETWEEN\s+1)|\b{c}\s*<>\s*''|\b{c}\s*~\s*'"
                       rf"|(jsonb_array_length|cardinality)\(\s*{c}\s*\)\s*>\s*0", k, re.I):
            marker_refused = True; why.append("non-empty")
    if nullable and not null_refused:
        return "null", why
    if marker_refused:
        return None, why
    if typ == "jsonb":
        return ("[]" if jtype == "array" else "{}"), why
    if typ.endswith("[]"):
        return "{}", why
    return "''", why


def catalog_problems(tables, text1, text2, uniques=None, details=None):
    """The check of rule 2 over parsed DDL and the two catalog texts; returns (problems, file-1 keys, file-2 keys).
    An exclusion with column_name * excludes a whole table that describes no person (rule 2)."""
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
    whole = {t for t, c in s2 if c == "*"}
    for t, c in list(s1) + list(s2):
        if t not in tables or (c != "*" and c not in tables[t]):
            errors.append(f"not in DDL: {t}.{c}")
    for key in sorted(set(s1) & set(s2)):
        errors.append(f"in both files: {key}")
    for t, c in s1:
        if t in whole:
            errors.append(f"in both files: ({t!r}, '*') excludes a table with a catalog row {t}.{c}")
    for t in sorted(whole):
        cov = re.match(r"covers: ([a-z0-9_, ]+); \S", s2[(t, "*")])
        covered = {w.strip() for w in cov.group(1).split(",")} if cov else set()
        if not cov:
            errors.append(f"* exclusion without 'covers: <columns>; <reason>': {t}")
        for c in tables.get(t, {}):
            if (t, c) in s2:
                errors.append(f"in both files: ({t!r}, '*') and the exclusion {t}.{c}")
            if RX.search(c) and c not in covered:
                errors.append(f"personal name in neither file: {t}.{c} is not in the covers list of its * exclusion")
        for c in sorted(covered - set(tables.get(t, {}))):
            errors.append(f"not in DDL: {t}.{c} (covers list of a * exclusion)")
    if uniques is not None:
        for (t, c), d in s1.items():
            if d["erasure_action"] == "blank" and any(c in u for u in uniques.get(t, [])):
                errors.append(f"blank on a unique key column: {t}.{c}")
    if details is not None:
        for (t, c), d in s1.items():
            if d["erasure_action"] == "blank" and t in details and c in details[t]["cols"]:
                res, why = blank_result(c, details[t]["cols"][c], details[t]["checks"])
                if res is None:
                    errors.append(f"blank refused by a CHECK (NULL and the marker): {t}.{c} ({'; '.join(why)})")
                elif res != "null" and f"blank gives the marker {res}" not in d["note"]:
                    errors.append(f"blank row whose note does not name its marker {res}: {t}.{c}")
    for t, cols in tables.items():
        for c, (f, ln, com) in cols.items():
            key = (t, c)
            excluded = key in s2 or t in whole
            if RX.search(c) and key not in s1 and not excluded:
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
UNIQ = parse_uniques(FILES)
DET = {}
parse_ddl(FILES, None, DET)
ncols = sum(len(c) for c in TABLES.values())
check("P01 every design/*.sql file parses, DS-64-personal-data.sql among them, with the five tables of ADR-0079",
      len(FILES) >= 15 and "DS-64-personal-data.sql" in dict(FILES) and all(t in TABLES for t in DS64), f"{len(FILES)} files, {len(TABLES)} tables, {ncols} columns")
F1 = open(os.path.join(DOCS, "catalogs", "personal-data-fields.csv"), encoding="utf-8").read()
F2 = open(os.path.join(DOCS, "catalogs", "personal-data-exclusions.csv"), encoding="utf-8").read()
errs, S1, S2 = catalog_problems(TABLES, F1, F2, UNIQ, DET)


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

# ======================================================================= E: the erasure exception (rule 7), in the DDL text
# Every refusing trigger names the columns an erasure may rewrite as an argument: the catalog columns of its table. Which
# argument holds them depends on the function; the erasure flags and crm's content_salt (INV-504) are allowed beside them.
ERASE_ARG = {"journal_reject_change": 0, "platform_reject_change": 0, "document_check_row_change": 0, "document_version_check_change": 0,
             "document_check_frozen": 1, "platform_check_append_only": 2, "crm_check_append_only": 2}
FLAGS = {"erased_at", "body_removed_at", "content_salt"}
ALL_DDL = "\n".join(t for _, t in FILES)
TRIGGERS = [(t, fn, re.findall(r"'([^']*)'", args)) for t, fn, args in re.findall(
    r"CREATE TRIGGER \w+\s+BEFORE [A-Z ,]*UPDATE[A-Z ,]*\s+ON (\w+)\s+FOR EACH ROW\s+EXECUTE FUNCTION (\w+)\(([^)]*)\)", ALL_DDL)]
CATCOLS, FROZEN = {}, {}
for (t, col), d in S1.items():
    if d["erasure_action"] != "keep":
        CATCOLS.setdefault(t, set()).add(col)
        if d["store_class"] in ("frozen_document", "append_only"):
            FROZEN.setdefault(t, set()).add(col)
passed_cols, wrong = {}, []
for t, fn, args in TRIGGERS:
    if fn in ERASE_ARG and len(args) > ERASE_ARG[fn]:
        cols = {c for c in args[ERASE_ARG[fn]].strip("{}").split(",") if c} - FLAGS
        mutable = {c for c in args[0].strip("{}").split(",") if c} if fn in ("platform_check_append_only", "crm_check_append_only") else set()
        passed_cols[t] = cols
        if not cols <= CATCOLS.get(t, set()) or not CATCOLS.get(t, set()) <= cols | mutable:
            wrong.append((t, sorted(cols ^ (CATCOLS.get(t, set()) - mutable))))
check("E01 every trigger that names erasure columns names exactly its table's catalog columns (keep rows aside; erasure flags and columns the trigger leaves mutable allowed)",
      not wrong and len(passed_cols) >= 25, wrong or f"{len(passed_cols)} tables")
brief = {"document", "document_version", "payment", "payment_line", "tax_line", "journal_entry", "journal_line"}
check("E02 posted headers and lines, document_version, journal_entry.note and journal_line.description take the exception (ADR-0079 rule 7)",
      brief <= set(passed_cols) and passed_cols["journal_entry"] == {"note"} and passed_cols["journal_line"] == {"description"}
      and "content" in passed_cols["document_version"], sorted(brief - set(passed_cols)))
guarded = {t for t, fn, _ in TRIGGERS}
OWN_GUARDS = {"analysis_example", "company_setup_acknowledgement", "document_extraction", "posting_intent", "saved_analysis_version"}
uncovered = sorted(t for t in FROZEN if t in guarded and t not in passed_cols)
no_trigger = sorted(t for t in FROZEN if t not in guarded)
check("E03 the only frozen or append-only catalog tables whose refusing trigger takes no erasure columns are the five with guard functions of their own "
      "(a follow-up); tables with no trigger in the DDL are the DS-22 headers and lines of the generated document trigger and rows without a guard yet",
      set(uncovered) == OWN_GUARDS, {"uncovered": uncovered, "no trigger in the DDL": len(no_trigger)})

# ======================================================================= S: self-tests
F64 = dict(FILES)["DS-64-personal-data.sql"]
broken_ddl = [(n, t) for n, t in FILES if n != "DS-20-master-data.sql"] + [
    ("DS-20-master-data.sql", dict(FILES)["DS-20-master-data.sql"] + "\nCREATE TABLE lab_selftest (\n    id uuid PRIMARY KEY,\n    mobile_phone text\n);\n")]
e1, _, _ = catalog_problems(parse_ddl(broken_ddl), F1, F2)
check("S01 a DDL column with a personal name and no catalog row is caught", any("lab_selftest.mobile_phone" in e and "neither file" in e for e in e1), [e for e in e1 if "lab_selftest" in e])
broken_ddl2 = [(n, t) for n, t in FILES if n != "DS-20-master-data.sql"] + [
    ("DS-20-master-data.sql", dict(FILES)["DS-20-master-data.sql"].replace("CREATE TABLE contact (\n", "CREATE TABLE contact (\n    customer_note text,\n", 1)
     + "\nCREATE TABLE lab_selftest_trip (\n    id uuid PRIMARY KEY,\n    driver_name text,\n    vehicle_kind_code text\n);\n")]
e1b, _, _ = catalog_problems(parse_ddl(broken_ddl2), F1, F2)
check("S05 a new free-text column (contact.customer_note) and a new name column (driver_name) are caught; a code column is not",
      any("contact.customer_note" in e and "neither file" in e for e in e1b) and any("lab_selftest_trip.driver_name" in e and "neither file" in e for e in e1b)
      and not any("vehicle_kind_code" in e for e in e1b), [e for e in e1b if "customer_note" in e or "lab_selftest_trip" in e])
e1c, _, _ = catalog_problems(TABLES, F1.replace("partner_bank_account,account_number,partner,financial,personal,partner_is_person,master,tokenize,",
                                                "partner_bank_account,account_number,partner,financial,personal,partner_is_person,master,blank,", 1), F2, UNIQ)
check("S06 a blank action on a column of a unique key (partner_bank_account.account_number) is caught (rule 1)",
      "blank on a unique key column: partner_bank_account.account_number" in e1c, [e for e in e1c if "unique" in e])
bad_ck = [(n, t.replace("CONSTRAINT ck_open_item_collection_dispute CHECK (is_disputed = (dispute_reason IS NOT NULL))",
                         "CONSTRAINT ck_open_item_collection_dispute CHECK (is_disputed = (coalesce(length(btrim(dispute_reason)), 0) > 0))"))
          for n, t in FILES]
D2 = {}
parse_ddl(bad_ck, None, D2)
e1e, _, _ = catalog_problems(TABLES, F1, F2, UNIQ, D2)
check("S08 a blank column whose CHECK refuses both NULL and the marker is caught (open_item_collection.dispute_reason made non-empty); "
      "the forms read: nullness pairings, col IS NOT NULL OR ..., coalesce(length(col), 0) > 0, length > 0, <> '', ~ pattern, jsonb_typeof",
      any("blank refused by a CHECK" in e and "open_item_collection.dispute_reason" in e for e in e1e)
      and blank_result("x", "jsonb NOT NULL", ["CHECK (jsonb_typeof(x) = 'array')"])[0] == "[]"
      and blank_result("x", "text", ["CONSTRAINT k CHECK ((a IS NULL) = (x IS NULL))"])[0] == "''"
      and blank_result("x", "text", ["CONSTRAINT k CHECK ((erased_at IS NULL) = (x IS NOT NULL))"])[0] == "null",
      [e for e in e1e if "dispute_reason" in e])
e1d, _, _ = catalog_problems(TABLES, F1, F2.rstrip("\n") + "\ncontact,*,lab self-test\n")
check("S07 a whole-table exclusion (*) of a table that has catalog rows is caught", any("('contact', '*')" in e for e in e1d), [e for e in e1d if "'*'" in e][:2])
broken_ddl3 = [(n, re.sub(r"(CREATE TABLE fixed_asset \([^\n]*\n)", r"\1    custodian_name text,\n", t, count=1)) for n, t in FILES]   # the line may carry an owner comment
e1f, _, _ = catalog_problems(parse_ddl(broken_ddl3), F1, F2)
check("S09 a column added later to a table excluded with * (fixed_asset.custodian_name) is caught: a * row covers only the columns it lists",
      any("fixed_asset.custodian_name" in e for e in e1f) and any("CREATE TABLE fixed_asset (" in t for _, t in FILES), [e for e in e1f if "custodian" in e])
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
FC = {r["template"]: set(r["suggested_field_classes"].split(";")) for r in read_dicts("role-templates.csv")}
check("K04 capability read_blocked_personal_data sits on its own leaf blocked_personal_data: owner at full (so it can grant it, ADR-0017 rule 6), every other template at none; "
      "only the owner template suggests the field class sensitive_personal (rules 5, 11)",
      AREAS.get("blocked_personal_data", {}).get("parent_code") == "administration" and "read_blocked_personal_data" in AREAS["blocked_personal_data"]["meaning"]
      and LV.get(("owner", "blocked_personal_data")) == "full" and all(LV.get((t, "blocked_personal_data")) == "none" for t in TPL - {"owner"})
      and {t for t in FC if "sensitive_personal" in FC[t]} == {"owner"},
      sorted(t for t in TPL if LV.get((t, "blocked_personal_data")) != ("full" if t == "owner" else "none")))
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
    trial("X11 the request is a document of the subject's company (no key to crm's table, review fix G11)", lambda cx: state(cx, data_subject_request_id=new()), "data_subject_request_id_fkey")
    trial("X11a a released subject needs released_at", lambda cx: state(cx, state="released"), "ck_data_subject_state_released")
    trial("X11b a blocked subject has no released_at", lambda cx: state(cx, released_at=NOW), "ck_data_subject_state_released")
    trial("X11c released_at is never before blocked_at", lambda cx: state(cx, state="released", released_at="2026-11-20T10:00:00+00"), "ck_data_subject_state_dates")
    state(c, state="released", released_at="2026-11-22T10:00:00+00")
    check("X11d a subject released by ReleaseDataSubject is stored with released_at (rule 5; review fix G14)", True)

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
    # Rule 9 note of 2026-11-21 (author): a company's own rule needs no package rule and no adjustable mark, and counts as
    # verified (S2: X17 and X18 used to require a package reference and an adjustable mark for source company).
    trial("X17 a package rule names the package rule it comes from", lambda cx: rule(cx, retention_class="message", package_rule_ref=None), "ck_retention_rule_package_rule_ref")
    trial("X17a a company's own rule is verified: the person who records it confirms it", lambda cx: rule(cx, retention_class="message", source="company", package_rule_ref=None), "ck_retention_rule_company_verified")
    rule(c, retention_class="message", source="company", package_rule_ref=None, is_verified=True, is_adjustable=False, block_after_months=None, destroy_after_months=None)
    rule(c, retention_class="intake", source="company", is_verified=True, is_adjustable=False)
    check("X18 a company's own rule needs no package rule and no adjustable mark, keeps a package reference when it adjusts one, and both periods may be null",
          X("select count(*) from retention_rule where company_id=%s and source='company' and is_verified and not is_adjustable", (I["co"],)).fetchone()[0] == 2)

    def entry(cx, **o):
        v = dict(id=new(), company_id=I["co"], subject_table="partner", subject_id=I["sold"], target_table="partner", target_row_id=I["sold"],
                 column_names=["name"], action="tokenize", cause="request", command_id=new(), executed_at=NOW); v.update(o)
        return ins(cx, "data_erasure_entry", **v)
    trial("X19 an erasure entry names at least one column (empty column_names)", lambda cx: entry(cx, column_names=[]), "ck_data_erasure_entry_column_names")
    trial("X20 the action is tokenize, blank, clear_keys or delete_row", lambda cx: entry(cx, action="drop_with_partition"), "ck_data_erasure_entry_action")
    trial("X21 the cause is request or retention; a restore re-inserts the entry with its own id and cause (review fix G7)", lambda cx: entry(cx, cause="restore_replay"), "ck_data_erasure_entry_cause")
    trial("X22 a company row's entry needs company_id", lambda cx: entry(cx, company_id=None), "ck_data_erasure_entry_company")

    def read(cx, **o):
        v = dict(id=new(), company_id=I["co"], user_account_id=I["user"], actor_kind="human", query_name="ListPartner", read_kind="blocked_subject", row_count=1,
                 field_names=["partner.name"], read_at=NOW); v.update(o)
        return ins(cx, "personal_data_read_log", **v)
    rl = read(c, subject_table="partner", subject_id=I["sold"])
    trial("X23 a read log row's row count is never negative", lambda cx: read(cx, row_count=-1), "ck_personal_data_read_log_row_count")
    trial("X24 the read kind is sensitive_field, blocked_subject or export", lambda cx: read(cx, read_kind="ordinary"), "ck_personal_data_read_log_read_kind")
    trial("X25 subject table and subject ID come together", lambda cx: read(cx, subject_table="partner"), "ck_personal_data_read_log_subject")
    trial("X25a an integration read names its client", lambda cx: read(cx, actor_kind="integration"), "ck_personal_data_read_log_actor")
    trial("X25b an agent read names its run", lambda cx: read(cx, actor_kind="agent"), "ck_personal_data_read_log_actor")
    trial("X25c an unknown actor kind is refused", lambda cx: read(cx, actor_kind="robot"), "ck_personal_data_read_log_actor_kind")

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
    for code_, personal_ in (("nickname", True), ("region", False)):
        ins(c, "custom_field_definition", id=new(), company_id=I["co"], target_table="partner", code=code_, label=code_.title(), data_type="choice", is_personal_data=personal_)
    PERSONAL_KEYS = [r[0] for r in X("select code from custom_field_definition where company_id=%s and target_table='partner' and is_personal_data", (I["co"],)).fetchall()]
    X("insert into partner (id, company_id, code, name, legal_name, tax_id, partner_kind, country, custom_values) values (%s,%s,'P-ERASE','Sample Person','Sample Person','0000000001','individual','VN','{\"nickname\": \"x\", \"region\": \"north\"}')", (p, I["co"]))
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
                    elif action == "clear_keys":
                        assigns.append(f"{col} = {col} - %(keys)s::text[]")
                    elif dtype == "jsonb":
                        assigns.append(f"{col} = '{{}}'::jsonb")
                    elif nullable == "YES":
                        assigns.append(f"{col} = null")
                    elif dtype == "ARRAY":
                        assigns.append(f"{col} = '{{}}'")
                    else:
                        assigns.append(f"{col} = ''")
                X(f"update {t} set {', '.join(assigns)} where id = %(rid)s", {"rid": rid, "keys": PERSONAL_KEYS})
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
            if action == "clear_keys" and (v is None or any(f'"{k}"' in v for k in PERSONAL_KEYS) or '"region"' not in v):
                bad.append(f"{t}.{col}={v}")
        n_entries = X("select count(*) from data_erasure_entry where subject_id=%s and target_table=%s and target_row_id=%s", (p, t, rid)).fetchone()[0]
        if n_entries == 0:
            bad.append(f"no entry for {t}")
    check("X32 INV-892 in SQL: the destroyed partner's catalog columns in partner, partner_address and contact are blank or tokenized, custom_values lost only its personal keys (clear_keys), each row with its erasure entry",
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
    dv = X("select is_nullable, data_type from information_schema.columns where table_schema='nativeflows' and table_name='document_version' and column_name='erased_at'").fetchone()
    check("X40 document_version has a nullable erased_at: an erased version's stored hash is no longer compared with its content (rule 6; INV-10)",
          dv == ("YES", "timestamp with time zone"), dv)

    # ---- the erasure exception of rule 7 on a posted document, its version and the journal triggers
    from fx_adr74 import doc
    pd = doc(c, I, "sales_invoice", state="posted", partner="sold")
    cd = new()      # a canceled document whose cancel note names a person (catalog row document.canceled_note)
    ins(c, "document", id=cd, company_id=I["co"], document_type="sales_order", state="canceled", version=1, partner_id=I["sold"], document_date="2026-11-10",
        created_by_user_id=I["user"], canceled_note="Called Sample Person", recorded_at=NOW)
    ver = new()
    ins(c, "document_version", id=ver, company_id=I["co"], document_id=pd, version=1, content='{"partner_name": "Sample Person", "lines": []}',
        version_hash="0" * 64, actor_kind="human", actor_id=I["user"], is_tainted=False, recorded_at=NOW)

    def erasing(cx):        # a valid marker: an erasure command's idempotency record of this transaction (finding B1)
        erasure_marker(cx.execute, company_id=I["co"])
    trial("X41 a document in a final state refuses a change of its catalog column without the erasure marker",
          lambda cx: cx.execute("update document set canceled_note = null where id=%s", (cd,)), "immutable")
    trial("X42 under the erasure marker the final document's catalog column is blanked (rolled back afterwards)",
          lambda cx: (erasing(cx), cx.execute("update document set canceled_note = null where id=%s", (cd,)), cx.execute("select 1/0")), "division by zero")
    trial("X43 under the erasure marker a non-catalog column of the final document is still refused",
          lambda cx: (erasing(cx), cx.execute("update document set canceled_note = null, document_date = '2026-11-11' where id=%s", (cd,))), "immutable")
    trial("X44 under the erasure marker the version's catalog keys are cleared and erased_at is set; the stored hash stays (rule 6)",
          lambda cx: (erasing(cx), cx.execute("update document_version set content = content - 'partner_name', erased_at = now() where id=%s", (ver,)), cx.execute("select 1/0")), "division by zero")
    trial("X45 under the erasure marker the version's hash is still refused", lambda cx: (erasing(cx), cx.execute("update document_version set version_hash = %s where id=%s", ("1" * 64, ver))), "never updated")
    trial("X46 without the marker the version's content is refused", lambda cx: cx.execute("update document_version set content = '{}' where id=%s", (ver,)), "never updated")
    trial("X47 the erasure marker never allows a delete of a version", lambda cx: (erasing(cx), cx.execute("delete from document_version where id=%s", (ver,))), "never updated")
    jt = {r[0]: bytes(r[1]).split(b"\x00")[0].decode() for r in X("select c.relname, t.tgargs from pg_trigger t join pg_class c on c.oid = t.tgrelid "
                                                                    "where t.tgname in ('trg_journal_entry_append_only', 'trg_journal_line_append_only')").fetchall()}
    check("X48 the journal triggers pass note and description as their catalog columns", jt == {"journal_entry": "{note}", "journal_line": "{description}"}, jt)

    def scratch(cx, fn_args):
        cx.execute("create temp table lab_frozen (id uuid primary key, note text, amount numeric) on commit drop")
        cx.execute(f"create trigger lab_frozen_guard before update or delete on lab_frozen for each row execute function {fn_args}")
        cx.execute("insert into lab_frozen values (%s, 'Sample Person', 10)", (pd,))
    trial("X49 journal_reject_change: under the marker the catalog column is blanked (rolled back afterwards)",
          lambda cx: (scratch(cx, "journal_reject_change('{note}')"), erasing(cx), cx.execute("update lab_frozen set note = null"), cx.execute("select 1/0")), "division by zero")
    trial("X50 journal_reject_change: under the marker an amount is still refused", lambda cx: (scratch(cx, "journal_reject_change('{note}')"), erasing(cx), cx.execute("update lab_frozen set note = null, amount = 0")), "append-only")
    trial("X51 journal_reject_change: without the marker the catalog column is refused", lambda cx: (scratch(cx, "journal_reject_change('{note}')"), cx.execute("update lab_frozen set note = null")), "append-only")
    trial("X52 document_check_frozen: a posted document's line takes the erasure of its catalog column (rolled back afterwards)",
          lambda cx: (scratch(cx, "document_check_frozen('id', '{note}')"), erasing(cx), cx.execute("update lab_frozen set note = ''"), cx.execute("select 1/0")), "division by zero")
    trial("X53 document_check_frozen: without the marker the same change is refused", lambda cx: (scratch(cx, "document_check_frozen('id', '{note}')"), cx.execute("update lab_frozen set note = ''")), "immutable")
    trial("X54 platform_reject_change with no catalog columns refuses even under the marker", lambda cx: (scratch(cx, "platform_reject_change()"), erasing(cx), cx.execute("update lab_frozen set note = ''")), "never updated")

    # ---- S2 schema review B1: the marker must name an erasure command's idempotency record written in this transaction
    def forged(cx, marker):
        cx.execute("select set_config('nativeflows.erasure_command_id', %s, true)", (marker,))
    old_rec = new()     # an erasure command's record committed in an earlier transaction
    X("insert into idempotency_record (id, company_id, actor_kind, actor_id, scope, idempotency_key, request_hash) values (%s,%s,'human',%s,'EraseDataSubject',%s,%s)",
      (old_rec, I["co"], I["user"], "lab-old-" + I["t"], "0" * 64))
    jr = "journal_reject_change('{note}')"
    trial("X55 B1: a marker that names no idempotency record (a random uuid) is refused",
          lambda cx: (scratch(cx, jr), forged(cx, str(new())), cx.execute("update lab_frozen set note = null")), "append-only")
    trial("X56 B1: a marker that is not a uuid is refused", lambda cx: (scratch(cx, jr), forged(cx, "forged"), cx.execute("update lab_frozen set note = null")), "append-only")
    trial("X57 B1: a marker naming an erasure command's record of another, committed transaction is refused (same transaction only)",
          lambda cx: (scratch(cx, jr), forged(cx, str(old_rec)), cx.execute("update lab_frozen set note = null")), "append-only")
    trial("X58 B1: a marker naming a record of another command type in this transaction is refused",
          lambda cx: (scratch(cx, jr), erasure_marker(cx.execute, scope="PostSalesInvoice", company_id=I["co"]), cx.execute("update lab_frozen set note = null")), "append-only")

    def temp_stand_in(cx):
        rid = new()
        cx.execute("create temp table idempotency_record (id uuid, scope text, transaction_id xid8) on commit drop")
        cx.execute("insert into pg_temp.idempotency_record values (%s, 'EraseDataSubject', pg_current_xact_id())", (rid,))
        forged(cx, str(rid))
    trial("X59 B1: a temporary table named idempotency_record cannot stand in for the real one",
          lambda cx: (scratch(cx, jr), temp_stand_in(cx), cx.execute("update lab_frozen set note = null")), "append-only")
    trial("X60 B1: a DestroyRetainedPersonalData record of this transaction is a valid marker (rolled back afterwards)",
          lambda cx: (scratch(cx, jr), erasure_marker(cx.execute, scope="DestroyRetainedPersonalData", company_id=I["co"]), cx.execute("update lab_frozen set note = null"),
                      cx.execute("select 1/0")), "division by zero")
    trial("X61 B1: a forged marker does not open the erasure-only columns of platform_check_append_only (audit_record.reason)",
          lambda cx: (cx.execute("create temp table lab_ao (id uuid primary key, reason text) on commit drop"),
                      cx.execute("create trigger lab_ao_guard before update or delete on lab_ao for each row execute function platform_check_append_only('{}', '{}', '{reason}')"),
                      cx.execute("insert into lab_ao values (%s, 'Sample Person')", (new(),)), forged(cx, str(new())), cx.execute("update lab_ao set reason = null")), "append-only")
    trial("X62 B1: a valid marker opens them (rolled back afterwards)",
          lambda cx: (cx.execute("create temp table lab_ao (id uuid primary key, reason text) on commit drop"),
                      cx.execute("create trigger lab_ao_guard before update or delete on lab_ao for each row execute function platform_check_append_only('{}', '{}', '{reason}')"),
                      cx.execute("insert into lab_ao values (%s, 'Sample Person')", (new(),)), erasing(cx), cx.execute("update lab_ao set reason = null"), cx.execute("select 1/0")),
          "division by zero")

    # ---- S2 schema review S2: only an erasure result of rule 6, and an erased column is never rewritten
    trial("X63 S2: under a valid marker a catalog column cannot take another person's name", lambda cx: (scratch(cx, jr), erasing(cx), cx.execute("update lab_frozen set note = 'Mrs Y'")), "append-only")
    trial("X64 S2: the token form erased-<hex> is accepted (tokenize; rolled back afterwards)",
          lambda cx: (scratch(cx, jr), erasing(cx), cx.execute("update lab_frozen set note = 'erased-' || left(md5(id::text), 12)"), cx.execute("select 1/0")), "division by zero")
    trial("X65 S2: a blanked column is never rewritten, not even within the erasure",
          lambda cx: (scratch(cx, jr), erasing(cx), cx.execute("update lab_frozen set note = null"), cx.execute("update lab_frozen set note = 'again'")), "append-only")
    trial("X66 S2: a tokenized column is never tokenized again",
          lambda cx: (scratch(cx, jr), erasing(cx), cx.execute("update lab_frozen set note = 'erased-0123456789ab'"), cx.execute("update lab_frozen set note = 'erased-ba9876543210'")), "append-only")
    trial("X67 S2: clear_keys may remove keys from a JSON column but never add one",
          lambda cx: (erasing(cx), cx.execute("""update document_version set content = content || '{"partner_name": "Mrs Y"}' where id=%s""", (ver,))), "never updated")
    trial("X68 S2: an erasure flag already set is never set again",
          lambda cx: (erasing(cx), cx.execute("update document_version set content = content - 'partner_name', erased_at = now() where id=%s", (ver,)),
                      cx.execute("update document_version set erased_at = now() + interval '1 day' where id=%s", (ver,))), "never updated")

    # ---- S2 schema review S1: generated columns are skipped, so a posted payment's snapshot can be erased
    from lab import ins_account, ins_system_account
    sa, acc, mac, pay = new(), new(), new(), new()
    ins_system_account(X, sa, "lab_cash_" + I["t"])
    ins_account(X, acc, I["co"], "1111" + I["t"], sa, "VND")
    ins(c, "money_account", id=mac, company_id=I["co"], code="CASH" + I["t"], name="Cash", kind="cash", currency="VND", account_id=acc)
    ins(c, "document", id=pay, company_id=I["co"], document_type="cash_payment", state="draft", version=1, document_date="2026-11-10", created_by_user_id=I["user"], recorded_at=NOW)
    ins(c, "payment", id=pay, company_id=I["co"], document_type="cash_payment", money_account_id=mac, transaction_currency="VND", document_date="2026-11-10",
        posting_date="2026-11-10", counterparty_name="Sample Person")
    X("update document set state = 'posted', posted_at = now() where id=%s", (pay,))
    trial("X69 S1: under a valid marker a posted payment's counterparty name is blanked, money_account_kind (generated) untouched (rolled back afterwards)",
          lambda cx: (erasing(cx), cx.execute("update payment set counterparty_name = null where id=%s", (pay,)), cx.execute("select 1/0")), "division by zero")
    trial("X70 S1: without the marker the same change is refused", lambda cx: cx.execute("update payment set counterparty_name = null where id=%s", (pay,)), "immutable")
    trial("X71 B1: a load without idempotency_record refuses every marker (the table renamed away inside the transaction)",
          lambda cx: (scratch(cx, jr), erasing(cx), cx.execute("alter table idempotency_record rename to lab_idempotency_record_away"),
                      cx.execute("update lab_frozen set note = null")), "append-only")

    # ---- S2 schema review round 2
    def other_company(cx):
        cx.execute("select set_config('nativeflows.company_id', %s, true)", (str(new()),))
        cx.execute("select set_config('nativeflows.company_ids', %s, true)", (str(I["co"]) + "," + str(new()),))
    trial("X72 R2-N1: an erasure record of this company does not validate under another company, even when company_ids lists it",
          lambda cx: (scratch(cx, jr), erasing(cx), other_company(cx), cx.execute("update lab_frozen set note = null")), "append-only")
    trial("X73 R2-N2: an installation-scoped erasure record (no company) is not visible under a company setting",
          lambda cx: (scratch(cx, jr), erasure_marker(cx.execute, company_id=None),
                      cx.execute("select set_config('nativeflows.company_id', %s, true)", (str(I["co"]),)), cx.execute("update lab_frozen set note = null")), "append-only")

    def ao(cx, fn):
        cx.execute("create temp table lab_ao (id uuid primary key, reason text) on commit drop")
        cx.execute(f"create trigger lab_ao_guard before update or delete on lab_ao for each row execute function {fn}('{{}}', '{{}}', '{{reason}}')")
        cx.execute("insert into lab_ao values (%s, 'Sample Person')", (new(),))
    trial("X74 R2-N3: under a valid marker platform_check_append_only refuses another person's name in an erasure-only column",
          lambda cx: (ao(cx, "platform_check_append_only"), erasing(cx), cx.execute("update lab_ao set reason = 'Mrs Y'")), "append-only")
    trial("X75 R2-N3: under a valid marker crm_check_append_only refuses another person's name in an erasure-only column",
          lambda cx: (ao(cx, "crm_check_append_only"), erasing(cx), cx.execute("update lab_ao set reason = 'Mrs Y'")), "append-only")
    trial("X76 R2-N3: crm_check_append_only still takes the blank (rolled back afterwards)",
          lambda cx: (ao(cx, "crm_check_append_only"), erasing(cx), cx.execute("update lab_ao set reason = ''"), cx.execute("select 1/0")), "division by zero")
    trial("X77 R2-N4: clear_keys may not remove a key of content the trigger does not list (lines)",
          lambda cx: (erasing(cx), cx.execute("update document_version set content = content - 'lines' where id=%s", (ver,))), "never updated")
    trial("X78 R2-N4: a listed key may be blanked in place instead of removed (rolled back afterwards)",
          lambda cx: (erasing(cx), cx.execute("""update document_version set content = jsonb_set(content, '{partner_name}', '""') where id=%s""", (ver,)),
                      cx.execute("select 1/0")), "division by zero")
    want = sorted({r["column_name"] for r in read_dicts("personal-data-fields.csv")
                   if r["store_class"] == "frozen_document" and r["table_name"] not in ("document_version", "posting_intent") and r["column_name"] != "custom_values"})
    targs = bytes(X("select t.tgargs from pg_trigger t where t.tgname = 'trg_document_version_check_change'").fetchone()[0]).split(b"\x00")
    got = sorted(targs[1].decode().strip("{}").split(",")) if len(targs) > 1 and targs[1] else []
    check("X79 R2-N4: the version trigger lists as clearable keys exactly the catalog columns of store class frozen_document (custom_values aside)",
          got == want, (len(got), len(want), sorted(set(want) ^ set(got))[:5]))
    fns = ("erasure_marker_valid", "erasure_value_is_erased", "erasure_json_reduced", "erasure_column_change_allowed", "erasure_update_allowed",
           "platform_check_append_only", "crm_check_append_only", "journal_entry_check_period")
    unpinned = [r[0] for r in X("select p.proname from pg_proc p join pg_namespace n on n.oid = p.pronamespace where n.nspname = 'nativeflows' "
                               "and p.proname = any(%s) and not coalesce(p.proconfig, '{}') @> array['search_path=nativeflows, pg_temp']", (list(fns),)).fetchall()]
    nfound = X("select count(distinct p.proname) from pg_proc p join pg_namespace n on n.oid = p.pronamespace where n.nspname = 'nativeflows' and p.proname = any(%s)", (list(fns),)).fetchone()[0]
    check("X80 R2-N5: the erasure guard functions and journal_entry_check_period pin search_path to nativeflows, pg_temp", not unpinned and nfound == len(fns), (unpinned, nfound))

    # ---- S2 adversarial review B1: where the trigger gives a key list, only the listed keys may go; a whole blank is refused.
    # Every column of every trigger that passes a key list (today document_version.content) is tried with each whole blank.
    keyed = []
    for rel, args in X("select c.relname, t.tgargs from pg_trigger t join pg_class c on c.oid = t.tgrelid join pg_proc p on p.oid = t.tgfoid "
                       "where p.proname = 'document_version_check_change' and t.tgnargs > 1 and not t.tgisinternal").fetchall():
        keyed += [(rel, col) for col in bytes(args).split(b"\x00")[0].decode().strip("{}").split(",") if col]
    check("X81 B1 (adversarial): the columns with a key list are found (document_version.content)", ("document_version", "content") in keyed, keyed)
    for rel, col in keyed:
        for blank in ("'{}'::jsonb", "'[]'::jsonb", "'null'::jsonb"):
            trial(f"X82 B1 (adversarial): under a valid marker {rel}.{col} = {blank} (a whole blank of a posted version) is refused",
                  lambda cx, rel=rel, col=col, blank=blank: (erasing(cx), cx.execute(f"update {rel} set {col} = {blank} where id=%s", (ver,))), "never updated")
    trial("X83 B1 (adversarial): under a valid marker the listed key alone is removed, the unlisted ones stay (rolled back afterwards)",
          lambda cx: (erasing(cx), cx.execute("update document_version set content = content - 'partner_name' where id=%s", (ver,)),
                      cx.execute("select 1/0")), "division by zero")

    # ---- S2 adversarial review S1: the erasure record's company must be the changed row's company, not only the session's
    def erasing_other(cx):      # an erasure record of company 2, with the session set to company 2 (the lab role bypasses RLS)
        erasure_marker(cx.execute, company_id=I["co2"])
    trial("X84 S1 (adversarial): an erasure record of company 2 does not erase company 1's posted payment",
          lambda cx: (erasing_other(cx), cx.execute("update payment set counterparty_name = null where id=%s", (pay,))), "immutable")
    trial("X85 S1 (adversarial): an erasure record of company 2 does not open company 1's version content",
          lambda cx: (erasing_other(cx), cx.execute("update document_version set content = content - 'partner_name' where id=%s", (ver,))), "never updated")

    def ao_company(cx, fn):
        cx.execute("create temp table lab_ao_co (id uuid primary key, company_id uuid, reason text) on commit drop")
        cx.execute(f"create trigger lab_ao_co_guard before update or delete on lab_ao_co for each row execute function {fn}('{{}}', '{{}}', '{{reason}}')")
        cx.execute("insert into lab_ao_co values (%s, %s, 'Sample Person')", (new(), I["co"]))
    for fn in ("platform_check_append_only", "crm_check_append_only"):
        trial(f"X86 S1 (adversarial): {fn}: an erasure record of company 2 does not open company 1's erasure-only column",
              lambda cx, fn=fn: (ao_company(cx, fn), erasing_other(cx), cx.execute("update lab_ao_co set reason = null")), "append-only")
        trial(f"X87 S1 (adversarial): {fn}: the row's own company's record does (rolled back afterwards)",
              lambda cx, fn=fn: (ao_company(cx, fn), erasing(cx), cx.execute("update lab_ao_co set reason = null"), cx.execute("select 1/0")), "division by zero")

    # ---- S2 adversarial review S2: recorded_at is set by the system on INSERT too (ADR-0007 rule 9); a client value is not kept
    d_old, v_old = new(), new()
    ins(c, "document", id=d_old, company_id=I["co"], document_type="sales_order", state="draft", version=1, partner_id=I["sold"], document_date="2026-11-10",
        created_by_user_id=I["user"], recorded_at="2001-01-01T00:00:00+00")
    ins(c, "document_version", id=v_old, company_id=I["co"], document_id=d_old, version=1, content='{"lines": []}', version_hash="0" * 64,
        actor_kind="human", actor_id=I["user"], is_tainted=False, recorded_at="2001-01-01T00:00:00+00")
    got = X("select (select recorded_at > now() - interval '1 hour' from document where id=%s), (select recorded_at > now() - interval '1 hour' from document_version where id=%s)",
            (d_old, v_old)).fetchone()
    check("X88 S2 (adversarial): a document (in place) and a version (append-only) inserted with recorded_at 2001 store the system time", got == (True, True), got)

    # ---- Y: the five entries left by the adversarial fixes, closed in the S2 closure of 2026-11-21 (chief architect)
    ROLE = "nativeflows_lab_rls"
    if not X("select 1 from pg_roles where rolname=%s", (ROLE,)).fetchone():
        X(f"CREATE ROLE {ROLE} NOLOGIN NOSUPERUSER NOBYPASSRLS")
    X(f"GRANT USAGE ON SCHEMA nativeflows, types TO {ROLE}")
    X(f"GRANT SELECT, INSERT, UPDATE, DELETE ON uom, company, idempotency_record TO {ROLE}")
    u_core, u_own1, u_own2 = new(), new(), new()
    X("insert into uom (id, code, name, quantity_kind, decimal_places) values (%s,%s,'Core','count',0)", (u_core, "YC" + I["t"]))
    X("insert into uom (id, company_id, code, name, quantity_kind, decimal_places) values (%s,%s,%s,'Own 1','count',0)", (u_own1, I["co"], "x-y1" + I["t"]))
    X("insert into uom (id, company_id, code, name, quantity_kind, decimal_places) values (%s,%s,%s,'Own 2','count',0)", (u_own2, I["co2"], "x-y2" + I["t"]))

    def as_role(cx, company):
        cx.execute(f"set local role {ROLE}")
        cx.execute("select set_config('nativeflows.company_id', %s, true)", (company,))

    def seen(company, sql, params=()):
        cx = conn()
        try:
            with cx.transaction():
                as_role(cx, company)
                return cx.execute(sql, params).fetchall()
        finally:
            cx.close()
    ids = {r[0] for r in seen(str(I["co"]), "select id from uom where id = any(%s)", ([u_core, u_own1, u_own2],))}
    check("Y01 (a) uom, shared reference variant: under company 1 a role without BYPASSRLS reads the core unit and its own unit, not company 2's",
          ids == {u_core, u_own1}, ids)
    trial("Y02 (a) under company 1 a core unit (company_id null) cannot be inserted", lambda cx: (as_role(cx, str(I["co"])), cx.execute(
        "insert into uom (id, code, name, quantity_kind, decimal_places) values (%s,%s,'Forged','count',0)", (new(), "YF" + I["t"]))), "row-level security")
    upd = seen(str(I["co"]), "update uom set name = 'changed' where id = %s returning id", (u_core,))
    check("Y03 (a) under company 1 a core unit is not updated (no row passes the write policy)", upd == [], upd)
    trial("Y04 (a) under installation a core unit is inserted (rolled back afterwards)", lambda cx: (as_role(cx, "installation"), cx.execute(
        "insert into uom (id, code, name, quantity_kind, decimal_places) values (%s,%s,'Core 2','count',0)", (new(), "YD" + I["t"])), cx.execute("select 1/0")), "division by zero")
    pol = {r[0] for r in X("select tablename from pg_policies where schemaname = 'nativeflows' and policyname = 'shared_read_policy'").fetchall()}
    check("Y05 (a) shared_read_policy is on exactly uom, tax_code, tax_rate and tax_treatment_rule (ADR-0080), the reference catalogs with a nullable company_id",
          pol == {"uom", "tax_code", "tax_rate", "tax_treatment_rule"}, sorted(pol))
    cos = {r[0] for r in seen(str(I["co"]), "select id from company where id = any(%s)", ([I["co"], I["co2"]],))}
    cx_ = conn()
    with cx_.transaction():
        as_role(cx_, str(I["co"]))
        cx_.execute("select set_config('nativeflows.company_ids', %s, true)", (f"{I['co']},{I['co2']}",))
        both = {r[0] for r in cx_.execute("select id from company where id = any(%s)", ([I["co"], I["co2"]],)).fetchall()}
    cx_.close()
    check("Y06 (d) company: its policies compare its own id; a session sees its own company, a cross-company query the companies it lists",
          cos == {I["co"]} and both == {I["co"], I["co2"]}, (cos, both))
    # (b) composite keys from tables whose company_id can be null
    trial("Y07 (b) an installation erasure entry (user account subject) names no request: the composite key is unchecked while company_id is null",
          lambda cx: entry(cx, company_id=None, subject_table="user_account", subject_id=new(), target_table="user_account", data_subject_request_id=new()),
          "ck_data_erasure_entry_request_company")
    trial("Y08 (b) a data subject state naming a request carries the request's company", lambda cx: state(
        cx, company_id=None, subject_table="user_account", subject_id=new(), data_subject_request_id=new()), "ck_data_subject_state_request_company")
    X("""insert into setting_definition (id, setting_key, area, scopes, storage, value_type, default_kind, core_default, allowed_values, direction, leaf_code,
         change_effect, outdates, source, registry_version) values (%s,'lab.y_installation','lab','{installation}','setting_value','boolean','value','false',
         '{true,false}','neutral','operator','immediate','none','lab','0.1.0')""", (new(),))
    trial("Y09 (b) an installation setting value names no company proposal", lambda cx: cx.execute(
        """insert into setting_value (id, company_id, setting_key, scope_kind, value, reason, effective_from, changed_by_user_id, change_proposal_id, registry_version)
           values (%s,null,'lab.y_installation','installation','true','x','2026-11-21',%s,%s,'0.1.0')""", (new(), I["user"], new())), "ck_setting_value_company_keys")
    trial("Y10 (b) an installation audit record names no policy decision", lambda cx: cx.execute(
        """insert into audit_record (id, company_id, business_date, command_type, schema_version, effect_class, is_human_only, is_proposal_bound, is_draft_only,
           is_internal_only, actor_kind, actor_id, causation_chain_id, causation_depth, policy_decision_id) values (%s,null,'2026-11-21','CreateCompany',1,'other',
           false,false,false,false,'system',%s,%s,0,%s)""", (new(), new(), new(), new())), "ck_audit_record_policy_decision_company")
    fk_null = X("""select r.relname, k.conname, (select array_agg(a.attname::text) from pg_attribute a where a.attrelid = r.oid and a.attnum = any (k.conkey))
                   from pg_constraint k join pg_class r on r.oid = k.conrelid join pg_namespace n on n.oid = r.relnamespace
                   join pg_attribute ca on ca.attrelid = r.oid and ca.attname = 'company_id' and not ca.attnotnull
                  where n.nspname = 'nativeflows' and k.contype = 'f' and cardinality(k.conkey) > 1 and ca.attnum = any (k.conkey) and not r.relispartition""").fetchall()
    unguarded = []
    for rel, con, cols in fk_null:
        other = [x for x in cols if x != "company_id"]
        checks = [d for (d,) in X("""select pg_get_constraintdef(k.oid) from pg_constraint k join pg_class r on r.oid = k.conrelid
                                     where r.relname = %s and r.relnamespace = 'nativeflows'::regnamespace and k.contype = 'c'""", (rel,)).fetchall()]
        if not all(any(x in d and ("company_id IS NOT NULL" in d or f"(company_id IS NULL) = ({x} IS NULL)" in d) for d in checks) for x in other):
            unguarded.append((rel, con))
    check(f"Y11 (b) every one of the {len(fk_null)} composite keys from a table whose company_id can be null has a CHECK that sets company_id with its column",
          not unguarded and len(fk_null) >= 5, unguarded)
    # (c) the setting_value tie-breaker is the id, never recorded_at (ADR-0007 rule 10)
    X("""insert into setting_definition (id, setting_key, area, scopes, storage, value_type, default_kind, core_default, allowed_values, direction, leaf_code,
         change_effect, outdates, source, registry_version) values (%s,'lab.y_order','lab','{company}','setting_value','boolean','value','false','{true,false}',
         'neutral','company_setting','immediate','none','lab','0.1.0') on conflict do nothing""", (new(),))

    def sv(cx, vid, value):
        cx.execute("""insert into setting_value (id, company_id, setting_key, scope_kind, value, reason, effective_from, changed_by_user_id, registry_version)
                      values (%s,%s,'lab.y_order','company',%s,'lab','2026-11-21',%s,'0.1.0')""", (vid, I["co"], value, I["user"]))
    first, second = new(), new()
    with c.transaction():
        sv(c, first, "true")
        sv(c, second, "false")       # same transaction, so the same recorded_at
    got = X("""select value from setting_value where company_id = %s and setting_key = 'lab.y_order'
               order by effective_from desc, id desc limit 1""", (I["co"],)).fetchone()[0]
    src = open(os.path.join(DOCS, "design", "DS-28-settings.sql"), encoding="utf-8").read()
    check("Y12 (c) two values of one key and date written in one transaction: the later id is in force, and no lookup orders by recorded_at",
          got is False and "recorded_at DESC" not in src, got)
    trial("Y13 (c) a value whose id does not follow the ids already written for the key and date is refused", lambda cx: sv(cx, first.__class__(int=first.int - 1), "true"),
          "does not follow the ids")

    def sqlstate_of(fn):
        cx = conn()
        try:
            with cx.transaction():
                fn(cx)
                cx.execute("select 1/0")
        except Exception as e:  # noqa: BLE001
            return getattr(e, "sqlstate", None)
        finally:
            cx.close()
    st = sqlstate_of(lambda cx: sv(cx, first.__class__(int=first.int - 2), "true"))
    check("Y13a R6-N4: the refusal is serialization_failure (SQLSTATE 40001), so the ADR-0008 retry runs again with a fresh, greater id", st == "40001", st)
    # (e) only erasure_command_record() writes the two erasure scopes
    def idem(cx, scope):
        cx.execute("insert into idempotency_record (id, company_id, actor_kind, actor_id, scope, idempotency_key, request_hash) values (%s,%s,'human',%s,%s,%s,%s)",
                   (new(), I["co"], new(), scope, "y-" + str(new()), "0" * 64))
    trial("Y14 (e) a role without BYPASSRLS cannot insert an EraseDataSubject record directly", lambda cx: (as_role(cx, str(I["co"])), idem(cx, "EraseDataSubject")),
          "written only by erasure_command_record")
    trial("Y15 (e) ... nor a DestroyRetainedPersonalData record", lambda cx: (as_role(cx, str(I["co"])), idem(cx, "DestroyRetainedPersonalData")),
          "written only by erasure_command_record")
    trial("Y20 R6-N3: EXECUTE on erasure_command_record() is revoked from PUBLIC; a role without the grant cannot call it", lambda cx: (as_role(cx, str(I["co"])), cx.execute(
        "select erasure_command_record(%s, 'human', %s, 'EraseDataSubject', %s, %s)", (new(), new(), "y-" + str(new()), "0" * 64))), "permission denied")
    # the lab role stands in for the dispatcher's role, which DS-18 grants EXECUTE (design change R6-N3)
    X(f"GRANT EXECUTE ON FUNCTION erasure_command_record(uuid, text, uuid, text, text, text) TO {ROLE}")
    trial("Y16 (e) the same role writes it through erasure_command_record(), for its session's company, and the marker validates (rolled back afterwards)",
          lambda cx: (as_role(cx, str(I["co"])), cx.execute("select erasure_command_record(%s, 'human', %s, 'EraseDataSubject', %s, %s)",
                                                           (new(), new(), "y-" + str(new()), "0" * 64)),
                      cx.execute("select 1/0 where (select company_id from idempotency_record where scope = 'EraseDataSubject' and transaction_id = pg_current_xact_id()) = %s",
                                 (I["co"],))), "division by zero")
    trial("Y17 (e) erasure_command_record() writes no other scope", lambda cx: (as_role(cx, str(I["co"])), cx.execute(
        "select erasure_command_record(%s, 'human', %s, 'PostSalesInvoice', 'k', %s)", (new(), new(), "0" * 64))), "only the two erasure scopes")
    trial("Y18 (e) another scope is still inserted directly by the role (rolled back afterwards)", lambda cx: (as_role(cx, str(I["co"])), idem(cx, "PostSalesInvoice"),
                                                                                                        cx.execute("select 1/0")), "division by zero")
    trial("Y19 (e) a record's scope never changes into an erasure scope", lambda cx: (idem(cx, "PostSalesInvoice"), as_role(cx, str(I["co"])), cx.execute(
        "update idempotency_record set scope = 'EraseDataSubject' where scope = 'PostSalesInvoice' and transaction_id = pg_current_xact_id()")),
          "written only by erasure_command_record")
    # S2-1 (adversarial, second pass): a committed erasure record of an earlier transaction cannot be re-armed
    old_er = new()
    with c.transaction():
        X("select set_config('nativeflows.company_id', %s, true)", (str(I["co"]),))
        X("select erasure_command_record(%s, 'human', %s, 'EraseDataSubject', %s, %s)", (old_er, new(), "y-old-" + str(new()), "0" * 64))
    trial("Y21 S2-1: an old erasure record's transaction_id cannot be moved to the current transaction (re-arming the marker)", lambda cx: (as_role(cx, str(I["co"])), cx.execute(
        "update idempotency_record set transaction_id = pg_current_xact_id() where id = %s", (old_er,))), "never change")
    trial("Y22 S2-1: ... nor its id or company (any row, not only erasure rows)", lambda cx: (idem(cx, "PostSalesInvoice"), cx.execute(
        "update idempotency_record set id = %s where scope = 'PostSalesInvoice' and transaction_id = pg_current_xact_id()", (new(),))), "never change")
    trial("Y23 ... while response is still written before commit (rolled back afterwards)", lambda cx: (idem(cx, "PostSalesInvoice"), cx.execute(
        "update idempotency_record set response = '{}' where scope = 'PostSalesInvoice' and transaction_id = pg_current_xact_id()"), cx.execute("select 1/0")),
          "division by zero")

    # ---- Z: the conventions on the catalog of the full load, which no DDL syntax can evade (S2 adversarial review S3, N1,
    # N3, N4; the text guard of gen_overview.py reads the files, these read pg_catalog). Partitions follow their parent.
    from gen_overview import KEY_ALLOWLIST, RLS_ALLOWLIST
    rels = X("""select c.relname, c.relispartition, c.relrowsecurity, c.relforcerowsecurity,
                       (select a.attnotnull from pg_attribute a where a.attrelid = c.oid and a.attname = 'company_id' and not a.attisdropped),
                       (select p.relname from pg_inherits i join pg_class p on p.oid = i.inhparent where i.inhrelid = c.oid)
                  from pg_class c join pg_namespace n on n.oid = c.relnamespace
                 where n.nspname = 'nativeflows' and c.relkind in ('r', 'p') order by 1""").fetchall()
    tops = [r[0] for r in rels if not r[1]]
    bad = [r[0] for r in X("""select c.relname from pg_class c join pg_namespace n on n.oid = c.relnamespace
              left join pg_attribute a on a.attrelid = c.oid and a.attname = 'recorded_at' and not a.attisdropped
              left join pg_attrdef d on d.adrelid = c.oid and d.adnum = a.attnum
             where n.nspname = 'nativeflows' and c.relkind in ('r', 'p') and not c.relispartition
               and not (a.atttypid = 'timestamptz'::regtype and a.attnotnull and pg_get_expr(d.adbin, d.adrelid) = 'now()')""").fetchall()]
    check(f"Z01 every one of the {len(tops)} loaded tables has recorded_at timestamptz NOT NULL DEFAULT now() (ADR-0007 rule 9)", not bad and len(tops) > 390, bad)
    pk = dict(X("""select c.relname, (select array_agg(a.attname::text || ':' || format_type(a.atttypid, a.atttypmod)) from unnest(k.conkey) u(x)
                    join pg_attribute a on a.attrelid = c.oid and a.attnum = u.x)
                  from pg_class c join pg_namespace n on n.oid = c.relnamespace left join pg_constraint k on k.conrelid = c.oid and k.contype = 'p'
                 where n.nspname = 'nativeflows' and c.relkind in ('r', 'p') and not c.relispartition""").fetchall())
    bad = sorted(t for t in tops if (pk.get(t) == ["id:uuid"]) == (t in KEY_ALLOWLIST))
    check(f"Z02 every table has the single primary key id uuid, except the {len(KEY_ALLOWLIST)} of KEY_ALLOWLIST (ADR-0006 rule 1)", not bad, bad)
    trg = X("""select c.relname, t.tgname, t.tgtype, t.tgenabled, p.proname from pg_trigger t join pg_class c on c.oid = t.tgrelid
              join pg_namespace n on n.oid = c.relnamespace join pg_proc p on p.oid = t.tgfoid
              where n.nspname = 'nativeflows' and not t.tgisinternal""").fetchall()
    ROW, BEFORE, INS, DEL, UPD, TRUNC = 1, 2, 4, 8, 16, 32
    by, fn_of = {}, {}
    for rel, name, typ, enabled, fname in trg:
        by.setdefault(rel, []).append((name, typ))
        fn_of[(rel, name)] = (enabled, fname)
    bad = []
    for t in tops:
        mine = dict(by.get(t, []))
        typ = mine.get(f"trg_{t}_set_recorded_at")
        guarded = any(ty & ROW and ty & BEFORE and ty & UPD for n_, ty in mine.items() if n_ != f"trg_{t}_set_recorded_at")
        if typ is None or not (typ & ROW and typ & BEFORE and typ & INS) or not (typ & UPD or guarded) \
                or fn_of[(t, f"trg_{t}_set_recorded_at")] != ("O", "set_recorded_at"):
            bad.append(t)
    check("Z03 every table has trg_<table>_set_recorded_at BEFORE INSERT, also on UPDATE unless an append-only guard refuses updates, enabled and running "
          "set_recorded_at (S2 adversarial review S2; second pass N2)", not bad, bad[:8])
    off = sorted(f"{r}.{n_}" for (r, n_), (en, _) in fn_of.items() if en != "O")
    check(f"Z03a every one of the {len(fn_of)} triggers of the design is enabled for ordinary sessions (tgenabled O; second pass N2)", not off and len(fn_of) > 600, off[:8])
    rules = [r[0] for r in X("""select c.relname || '.' || w.rulename from pg_rewrite w join pg_class c on c.oid = w.ev_class
              join pg_namespace n on n.oid = c.relnamespace where n.nspname = 'nativeflows' and w.rulename <> '_RETURN'""").fetchall()]
    check("Z03b no rewrite rule on any table of the design (a DO INSTEAD rule would bypass triggers; second pass N2)", not rules, rules[:8])
    from gen_overview import RLS_SHARED_READ
    want_rls = [r for r in rels if r[4] is not None and (r[5] or r[0]) not in RLS_ALLOWLIST]
    # the expected predicates, as PostgreSQL deparses them: the policies of ADR-0017 rule 19 created on a scratch table (second pass N2)
    with c.transaction():
        X("create temp table lab_pol (company_id uuid)")
        X("create policy company_policy on lab_pol using (company_id::text = current_setting('nativeflows.company_id', true))")
        X("create policy company_policy_nullable on lab_pol using (company_id::text = current_setting('nativeflows.company_id', true)"
          " or (company_id is null and current_setting('nativeflows.company_id', true) = 'installation'))")
        X("create policy company_ids_policy on lab_pol for select using (company_id::text = any (string_to_array(current_setting('nativeflows.company_ids', true), ',')))")
        X("create policy shared_read_policy on lab_pol for select using (company_id is null)")
        ref = {n_: (cmd, q) for n_, cmd, q in X("select policyname, cmd, qual from pg_policies where tablename = 'lab_pol'").fetchall()}
        X("drop table lab_pol")
    pol = {}
    for rel, name, qual, cmd, perm, roles, wcheck in X("""select tablename, policyname, qual, cmd, permissive, roles::text, with_check
                                                           from pg_policies where schemaname = 'nativeflows'""").fetchall():
        pol.setdefault(rel, {})[name] = (cmd, qual, perm, roles, wcheck)
    bad = []
    for r in want_rls:
        mine = pol.get(r[0], {})
        expect = {"company_policy": ref["company_policy_nullable" if r[4] is False else "company_policy"], "company_ids_policy": ref["company_ids_policy"]}
        if (r[5] or r[0]) in RLS_SHARED_READ:
            expect["shared_read_policy"] = ref["shared_read_policy"]
        if not (r[2] and r[3]) or set(mine) != set(expect) or any(
                (mine[n_][0], mine[n_][1]) != expect[n_] or mine[n_][2] != "PERMISSIVE" or mine[n_][3] != "{public}" or mine[n_][4] is not None for n_ in expect):
            bad.append(r[0])
    check(f"Z04 every one of the {len(want_rls)} tables and partitions with company_id has forced row-level security and exactly its policies with the "
          f"expected predicates: company_policy (the installation variant exactly where company_id is nullable), company_ids_policy for SELECT, "
          f"shared_read_policy only on the shared reference catalogs, and no other permissive policy (second pass N2); exceptions only in RLS_ALLOWLIST "
          f"({', '.join(RLS_ALLOWLIST) or 'none'})", not bad and len(want_rls) > 370, bad[:8])
    need = {t for t in tops if any(ty & BEFORE and ty & DEL for n_, ty in by.get(t, []))
            or (dict(by.get(t, [])).get(f"trg_{t}_set_recorded_at", UPD) & UPD) == 0}
    need |= {r[0] for r in rels if r[4] is not None}          # every table with company_id (R6-N2; second pass N7)
    need |= {r[0] for r in rels if r[1] and r[5] in need}
    # the generated guard runs refuse_truncate; the three hand-written ones of DS-06 and DS-22 run their tables' reject functions
    truncate_fns = {"refuse_truncate", "journal_reject_change", "inventory_reject_change"}
    bad = sorted(t for t in need if not any(ty & BEFORE and ty & TRUNC and fn_of[(t, n_)][0] == "O" and fn_of[(t, n_)][1] in truncate_fns
                                            for n_, ty in by.get(t, [])))
    check(f"Z05 every one of the {len(need)} tables with company_id, append-only or delete-guarded tables (and their partitions) refuses TRUNCATE with an "
          "enabled BEFORE TRUNCATE trigger running refuse_truncate or a hand-written reject function (S2 adversarial review N4; R6-N2; second pass N2, N7)", not bad and len(need) > 380, bad[:8])
    bad = [r[0] for r in X("""select p.proname from pg_proc p join pg_namespace n on n.oid = p.pronamespace
              where n.nspname = 'nativeflows' and not exists (select 1 from pg_depend d where d.classid = 'pg_proc'::regclass and d.objid = p.oid and d.deptype = 'e')
                and not coalesce(p.proconfig, '{}') @> array['search_path=nativeflows, pg_temp']""").fetchall()]
    check("Z06 every function of the design pins search_path = nativeflows, pg_temp (S2 adversarial review N3; extension functions aside)", not bad, bad[:8])
    for t in ("audit_record", "document_version", "approval"):
        trial(f"Z07 TRUNCATE {t} is refused (S2 adversarial review N4)", lambda cx, t=t: cx.execute(f"truncate {t} cascade"), "never truncated")
    for t in ("stock_value", "stock_quantity", "idempotency_record", "posting_period_area_state", "uom_alias", "account_period_balance"):
        trial(f"Z08 TRUNCATE {t} is refused (R6-N2; second pass N7: tables updated in place)", lambda cx, t=t: cx.execute(f"truncate {t} cascade"), "never truncated")

    c.close()

passed = sum(1 for ok_, *_ in RESULTS if ok_)
print(f"{passed} / {len(RESULTS)} passed")
sys.exit(0 if passed == len(RESULTS) else 1)
