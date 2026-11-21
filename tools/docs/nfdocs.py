"""Shared parsing for the S3 document tools (tools/docs). Standard library only, deterministic, no LLM calls.

Reads the ADRs (docs/adr/00NN-*.md), the design DDL (docs/design/**/*.sql), the catalogs (docs/catalogs/*.csv) and the
module map of ADR-0022 rule 2. The table -> owner module mapping and the ADR -> declared modules mapping are imported
from docs/reviews/2026-11-14-design-validation/lab/gen_overview.py (module_map, parse_ddl, declared_by_module), not
copied, so the tools and the generated module cards cannot disagree.
"""

import csv
import glob
import importlib
import io
import os
import re
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, "..", ".."))
DEFAULT_DOCS = os.path.join(REPO, "docs")
DEFAULT_INDEX = os.path.join(DEFAULT_DOCS, "design", "generated", "rule-index.csv")
LAB = os.path.join("reviews", "2026-11-14-design-validation", "lab")

TOKEN_BYTES = 3.5          # tokens are estimated as bytes / 3.5 (compiled-spec template, "Size budget")
CHUNK_TOKENS = 30000       # context pack limit, ADR-0073 rule 6 (interim)
SPEC_HARD_TOKENS = 16000   # compiled-spec hard limit per file (compiled-spec template, "Size budget")
CROSS_LIMIT = 3            # a unit whose modules number more than this goes to module `cross`
STEP_ORDER = ["0", "1", "2", "3", "4", "4b", "5", "5b", "6", "7", "8", "9", "10", "11"]  # spec 11-build-order.md
STEP_VOCAB = set(STEP_ORDER)

# ------------------------------------------------------------------------------------------------ ADR line shapes

TITLE_RE = re.compile(r"^# ADR-(\d{4}): (.*)$")
H2_RE = re.compile(r"^## (.*?)\s*$")
H3_RE = re.compile(r"^### (.*?)\s*$")
RULE_RE = re.compile(r"^(\d+[a-z]?)\. ")
TABLE_RULE_RE = re.compile(r"^\|\s*R(\d+)\s*\|")          # ADR-0003: rules R1-R14 are rows of a table
GROUP_RE = re.compile(r"^\*\*([^*][^*]*?)\*\*\s*(\(.*\))?\s*[.:]?\s*$")
NOTE_HEAD_RE = re.compile(r"^( {0,4})Note(?=[ :])")
DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")

SECTION_CODES = [  # (heading prefix, unit code); first match wins
    ("Context", "C"),
    ("Options considered", "O"),
    ("Constraints", "K"),
    ("Consequences", "K"),
    ("Edge cases", "E"),
    ("Revisit when", "V"),
    ("Documents updated", "U"),
    ("Decisions for the author", "A"),   # extra section found in ADR-0057 and ADR-0062
]
WORKED_EXAMPLE_CODE = "W"                 # "### Worked example(s)" after the rules (ADR-0057, 0058, 0059, 0062)

# Relation phrases for notes (case-insensitive). Conservative on purpose; see README "Heuristics".
SUPERSEDED_BY_PHRASES = ["superseded by"]
SUPERSEDES_PHRASES = ["supersedes", "overrides", "replaces", "is replaced by", "are replaced by", "no longer applies",
                      "is withdrawn", "is dropped", "are dropped"]
# Conflict flag phrases for notes (case-insensitive), from the S3 brief. SQL `ON CONFLICT` is not a hit.
CONFLICT_PHRASES = ["conflict", "contradict", "no longer", "instead of", "replaces", "reversed", "overturn", "is wrong",
                    "corrected"]
PREFIX_PHRASES = {"conflict", "contradict", "overturn"}   # match as word prefixes (conflicts, contradicted, ...)
# A literal marker is the word CONFLICT in capitals, except SQL `ON CONFLICT`, the template's `CONFLICT <rule id>`
# and the word quoted in backticks.
MARKER_RE = re.compile(r"(?<!ON )(?<!`)\bCONFLICT\b(?! <)(?!`)")

_SEP = r"(?:\s*,\s*(?:and\s+)?|\s+and\s+|\s*[–-]\s*|\s+to\s+)"
ADR_REF_RE = re.compile(
    r"ADR-(\d{4})(?:\]\([^)]*\))?(?:'s)?,?"
    r"(?:\s+(?:rules?\s+(\d{1,3}[a-z]?\b(?:" + _SEP + r"\d{1,3}[a-z]?\b)*)"
    r"|(R\d+(?:" + _SEP + r"R\d+)*)\b))?")
OTHER_REFS = {"inv": re.compile(r"\bINV-(\d+)\b"), "ec": re.compile(r"\bEC-(\d+)\b"),
              "ds": re.compile(r"\bDS-(\d+)\b"), "oq": re.compile(r"\bOQ-(\d+)\b")}
STEP_RE = re.compile(r"\b(?:[Bb]uild )?[Ss]teps? (\d+[ab]?)\b")


def _phrase_re(phrase):
    tail = "" if phrase in PREFIX_PHRASES else r"(?![\w])"
    return re.compile(r"(?<![\w])" + re.escape(phrase) + tail, re.I)


PHRASE_RES = {p: _phrase_re(p) for p in set(SUPERSEDED_BY_PHRASES + SUPERSEDES_PHRASES + CONFLICT_PHRASES)}


def find_phrases(text, phrases):
    hits = []
    for p in phrases:
        for m in PHRASE_RES[p].finditer(text):
            if p == "conflict" and text[max(0, m.start() - 3):m.start()].upper() == "ON ":
                continue
            hits.append(p)
            break
    return hits


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def note_head(line):
    """'   Note ([ADR-0074](x.md), 2026-11-21): text' -> (indent, author or None, date or None); else None."""
    m = NOTE_HEAD_RE.match(line)
    if not m:
        return None
    rest = line[m.end():]
    if rest.startswith(":"):
        return len(m.group(1)), None, None
    if not rest.startswith(" ("):
        return None
    depth, i = 0, 1
    while i < len(rest):
        if rest[i] == "(":
            depth += 1
        elif rest[i] == ")":
            depth -= 1
            if depth == 0:
                break
        i += 1
    if depth != 0 or not rest[i + 1:].startswith(":"):
        return None
    author = rest[2:i]
    dm = DATE_RE.search(author)
    return len(m.group(1)), author, dm.group(0) if dm else None


def indent_of(line):
    return len(line) - len(line.lstrip(" "))


def adr_status(status_line):
    m = re.match(r"Status:\s*(\w+)", status_line or "")
    word = m.group(1).lower() if m else ""
    if word.startswith("supersed"):
        return "superseded"
    if word in ("accepted", "proposed"):
        return word
    return "unknown"


# ------------------------------------------------------------------------------------------------ ADR parser

class _Ctx:
    def __init__(self, lines, adr, title, status, rel_path):
        self.lines, self.adr, self.title, self.status, self.rel = lines, adr, title, status, rel_path
        self.units, self.assigned, self.structural, self.oddities = [], {}, set(), []
        self.d = 0          # Decision section units D1, D2, ...
        self.w = 0          # worked-example units
        self.lists = 1      # numbered list (a restart opens list 2, 3, ...)
        self.list_numbers = set()
        self.new_heading = False

    def unit(self, uid, kind, **kw):
        u = {"id": uid, "kind": kind, "adr": self.adr, "rule_no": kw.get("rule_no"), "group": kw.get("group"),
             "section": kw.get("section"), "parent": kw.get("parent"), "source_file": self.rel,
             "adr_status": self.status, "note_author": kw.get("note_author"), "note_date": kw.get("note_date"),
             "relation": None, "_lines": [], "_notes": 0}
        self.units.append(u)
        return u

    def add(self, u, i):
        u["_lines"].append(i)
        self.assigned[i] = u["id"]

    def next_d(self, section):
        self.d += 1
        return self.unit(f"{self.adr}.D{self.d}", "section", section=section)


def parse_adr(path, rel_path):
    """Parse one ADR into units (rules, notes, sections), its coverage and oddities. Every line belongs to one unit or is
    structural (a heading or a group line)."""
    lines = read(path).split("\n")
    if lines and lines[-1] == "":
        lines = lines[:-1]
    oddities = []
    tm = TITLE_RE.match(lines[0]) if lines else None
    if tm:
        num, title = tm.group(1), tm.group(2)
    else:
        oddities.append(f"{rel_path}:1 no '# ADR-NNNN: Title' line")
        num, title = re.search(r"(\d{4})", os.path.basename(path)).group(1), ""
    adr = f"ADR-{num}"
    status_line = next((l for l in lines[:8] if l.startswith("Status:")), None)
    if status_line is None:
        oddities.append(f"{rel_path}: no 'Status:' line in the first 8 lines")
    status = adr_status(status_line)
    if status == "unknown":
        oddities.append(f"{rel_path}: status word not accepted|proposed|superseded")
    c = _Ctx(lines, adr, title, status, rel_path)
    c.oddities = oddities

    h2 = [(i, H2_RE.match(l).group(1)) for i, l in enumerate(lines) if H2_RE.match(l)]
    first_h2 = h2[0][0] if h2 else len(lines)
    parse_block(c, 0, first_h2, c.unit(f"{adr}.H", "section", section="header"), rules_allowed=False)
    seen = defaultdict(int)
    decision_range = None
    for k, (start, name) in enumerate(h2):
        end = h2[k + 1][0] if k + 1 < len(h2) else len(lines)
        c.structural.add(start)
        if name == "Decision":
            decision_range = (start, end)
            parse_decision(c, start + 1, end)
            continue
        code = next((cd for p, cd in SECTION_CODES if name.startswith(p)), None)
        if code is None:
            code = "X"
            oddities.append(f"{rel_path}:{start + 1} unknown section '## {name}' recorded as .X")
        seen[code] += 1
        if seen[code] > 1:
            code = f"{code}{seen[code]}"
        parse_block(c, start + 1, end, c.unit(f"{adr}.{code}", "section", section=name), rules_allowed=False)
    if decision_range is None:
        oddities.append(f"{rel_path}: no '## Decision' section")

    out = []
    for u in c.units:
        idx = sorted(u.pop("_lines"))
        u.pop("_notes")
        if not idx:
            continue
        u["line_start"], u["line_end"] = idx[0] + 1, idx[-1] + 1
        parts, prev = [], None   # verbatim own lines; a gap (another unit's lines) is kept as one blank line
        for i in idx:
            if prev is not None and i != prev + 1 and parts and parts[-1] != "":
                parts.append("")
            parts.append(lines[i])
            prev = i
        while parts and not parts[-1].strip():
            parts.pop()
        u["text"] = "\n".join(parts)
        out.append(u)
    ids = [u["id"] for u in out]
    for d in sorted({x for x in ids if ids.count(x) > 1}):
        oddities.append(f"{rel_path}: duplicate unit id {d}")

    cov = {"decision_lines": 0, "rule_lines": 0, "note_lines": 0, "section_lines": 0, "structural_lines": 0,
           "uncovered": []}
    kinds = {u["id"]: u["kind"] for u in out}
    if decision_range:
        for i in range(decision_range[0], decision_range[1]):
            if not lines[i].strip():
                continue
            cov["decision_lines"] += 1
            if i in c.structural:
                cov["structural_lines"] += 1
            elif i in c.assigned:
                cov[kinds[c.assigned[i]] + "_lines"] += 1
            else:
                cov["uncovered"].append(f"{rel_path}:{i + 1}")
    return {"adr": adr, "num": num, "title": title, "status": status, "status_line": status_line or "",
            "file": rel_path, "units": out, "oddities": oddities, "coverage": cov}


def parse_decision(c, start, end):
    lines = c.lines
    h3 = [(i, H3_RE.match(lines[i]).group(1)) for i in range(start, end) if H3_RE.match(lines[i])]
    d0 = c.unit(f"{c.adr}.D0", "section", section="Decision")
    if any(n == "Rules" for _, n in h3):
        bounds = [start] + [i for i, _ in h3] + [end]
        names = ["Decision"] + [n for _, n in h3]
        for k in range(len(bounds) - 1):
            a, b = bounds[k], bounds[k + 1]
            if k > 0:
                c.structural.add(a)
                a += 1
            if names[k] == "Rules":
                parse_rules_zone(c, a, b, None)
            elif k == 0:
                parse_block(c, a, b, d0, rules_allowed=False)
            elif names[k].startswith("Worked example"):
                c.w += 1
                code = WORKED_EXAMPLE_CODE + ("" if c.w == 1 else str(c.w))
                parse_block(c, a, b, c.unit(f"{c.adr}.{code}", "section", section=f"Decision / {names[k]}"),
                            rules_allowed=False)
            else:
                parse_block(c, a, b, c.next_d(f"Decision / {names[k]}"), rules_allowed=False)
        return
    numbered = any(RULE_RE.match(lines[i]) for i in range(start, end))
    table_rows = not numbered and any(TABLE_RULE_RE.match(lines[i]) for i in range(start, end))
    if numbered:
        c.oddities.append(f"{c.rel}: no '### Rules'; numbered lists under '## Decision' read as rules, "
                          f"'###' headings as groups")
        parse_rules_zone(c, start, end, d0, h3_as_group=True)
    elif table_rows:
        c.oddities.append(f"{c.rel}: rules are table rows 'R<n>' under '## Decision' (ADR-0003 shape)")
        parse_table_rules(c, start, end, d0)
    else:
        c.oddities.append(f"{c.rel}: no rules; the Decision is one section unit .D0")
        parse_block(c, start, end, d0, rules_allowed=False)


def parse_table_rules(c, start, end, d0):
    owner, i = d0, start
    while i < end:
        m = TABLE_RULE_RE.match(c.lines[i])
        if m:
            c.add(c.unit(f"{c.adr}.R{m.group(1)}", "rule", rule_no=f"R{m.group(1)}"), i)
            owner = None
            i += 1
            continue
        if owner is None:
            if not c.lines[i].strip():
                i += 1
                continue
            owner = c.next_d("Decision (after the rule table)")
        i = parse_block(c, i, end, owner, rules_allowed=False, stop_at_table_rule=True)


def parse_rules_zone(c, start, end, d0, h3_as_group=False):
    group, owner, i = None, d0, start
    lines = c.lines
    while i < end:
        line = lines[i]
        if h3_as_group and H3_RE.match(line):
            group = H3_RE.match(line).group(1)
            c.structural.add(i)
            owner, c.new_heading = None, True
            i += 1
            continue
        gm = GROUP_RE.match(line)
        if gm:
            group = gm.group(1).strip()
            c.structural.add(i)
            owner = None
            i += 1
            continue
        rm = RULE_RE.match(line)
        if rm:
            no = rm.group(1)
            if no in c.list_numbers or (c.new_heading and no == "1" and c.list_numbers):
                c.lists += 1
                c.list_numbers = set()
                if not h3_as_group:
                    c.oddities.append(f"{c.rel}:{i + 1} rule number {no} repeats; read as list {c.lists}")
            c.new_heading = False
            c.list_numbers.add(no)
            uid = f"{c.adr}.R{no}" if c.lists == 1 else f"{c.adr}.L{c.lists}.R{no}"
            owner = c.unit(uid, "rule", rule_no=no, group=group)
            c.add(owner, i)
            i = parse_block(c, i + 1, end, owner, rules_allowed=True, h3_stop=h3_as_group)
            continue
        if owner is None:
            if not line.strip():
                i += 1
                continue
            owner = c.next_d("Decision / " + (group or "text between rules"))
        i = parse_block(c, i, end, owner, rules_allowed=True, h3_stop=h3_as_group)


def parse_block(c, start, end, owner, rules_allowed, h3_stop=False, stop_at_table_rule=False):
    """Assign lines start..end to owner and its notes; return where a new rule or group begins (rules_allowed), or end.
    A note runs for its paragraph. After a blank line, a block indented deeper than the note (or at 4 or more, for a
    note indented 4) continues the note; any other block returns to the owner."""
    lines = c.lines
    note, note_indent, i = None, 0, start
    while i < end:
        line = lines[i]
        if rules_allowed and (RULE_RE.match(line) or GROUP_RE.match(line) or (h3_stop and H3_RE.match(line))):
            return i
        if stop_at_table_rule and TABLE_RULE_RE.match(line):
            return i
        if H3_RE.match(line):
            c.structural.add(i)
            i += 1
            continue
        nh = note_head(line)
        if nh:
            owner["_notes"] += 1
            note = c.unit(f"{owner['id']}.N{owner['_notes']}", "note", parent=owner["id"], rule_no=owner.get("rule_no"),
                          group=owner.get("group"), section=owner.get("section"), note_author=nh[1], note_date=nh[2])
            note_indent = nh[0]
            c.add(note, i)
            i += 1
            continue
        if not line.strip():
            if note is not None:
                j = i
                while j < end and not lines[j].strip():
                    j += 1
                if j < end:
                    ind = indent_of(lines[j])
                    if note_head(lines[j]) or not (ind > note_indent or (note_indent == 4 and ind >= 4)):
                        note = None
            i += 1
            continue
        c.add(note if note is not None else owner, i)
        i += 1
    return end


# ------------------------------------------------------------------------------------------------ references

def expand_list(spec):
    """'3, 5–7 and 9' -> ['3', '5', '6', '7', '9']; 'R5, R6' -> ['R5', 'R6']."""
    out = []
    for p in re.split(r"\s*,\s*(?:and\s+)?|\s+and\s+", spec.strip()):
        rm = re.match(r"^(R?)(\d+)([a-z]?)\s*(?:[–-]|\s+to\s+)\s*R?(\d+)([a-z]?)$", p)
        if rm and not rm.group(3) and not rm.group(5) and 0 <= int(rm.group(4)) - int(rm.group(2)) < 60:
            out += [f"{rm.group(1)}{n}" for n in range(int(rm.group(2)), int(rm.group(4)) + 1)]
        elif rm:
            out += [f"{rm.group(1)}{rm.group(2)}{rm.group(3)}", f"{rm.group(1)}{rm.group(4)}{rm.group(5)}"]
        elif p:
            out.append(p)
    return out


def rule_sort_key(uid):
    return [int(p) if p.isdigit() else p for p in re.split(r"(\d+)", uid)]


def find_refs(text):
    """-> (ADR ids, rule ids, {inv, ec, ds, oq: ids}). 'ADR-0022 rule 4' -> ADR-0022.R4; 'ADR-0003 R6' -> ADR-0003.R6."""
    adrs, rules = set(), set()
    for m in ADR_REF_RE.finditer(text):
        adrs.add(f"ADR-{m.group(1)}")
        spec = m.group(2) or m.group(3)
        if spec:
            for r in expand_list(spec):
                rules.add(f"ADR-{m.group(1)}.R{r[1:] if r.startswith('R') else r}")
    other = {k: sorted({f"{k.upper()}-{n}" for n in rx.findall(text)}, key=rule_sort_key) for k, rx in OTHER_REFS.items()}
    return sorted(adrs), sorted(rules, key=rule_sort_key), other


# ------------------------------------------------------------------------------------------------ extraction

def adr_files(docs):
    return sorted(glob.glob(os.path.join(docs, "adr", "[0-9][0-9][0-9][0-9]-*.md")))


def rel(docs, path):
    return "docs/" + os.path.relpath(path, docs).replace(os.sep, "/")


def extract(docs):
    """All ADRs -> (units, parsed ADRs, dangling [(unit id, target)]). Units are in ADR then source order."""
    parsed = [parse_adr(p, rel(docs, p)) for p in adr_files(docs)]
    units = [u for a in parsed for u in a["units"]]
    ids = {u["id"] for u in units}
    adr_set = {a["adr"] for a in parsed}
    dangling = []
    for u in units:
        adrs, rules, other = find_refs(u["text"])
        u["xrefs_adrs"], u["xrefs_rules"] = adrs, rules
        u["xrefs_inv"], u["xrefs_ec"], u["xrefs_ds"], u["xrefs_oq"] = other["inv"], other["ec"], other["ds"], other["oq"]
        u["dangling"] = sorted({r for r in rules if r not in ids} | {a for a in adrs if a not in adr_set},
                               key=rule_sort_key)
        dangling += [(u["id"], d) for d in u["dangling"]]
        u["conflict_markers"] = len(MARKER_RE.findall(u["text"]))
        if u["kind"] == "note":
            if find_phrases(u["text"], SUPERSEDED_BY_PHRASES):
                u["relation"] = "superseded-by"
            elif find_phrases(u["text"], SUPERSEDES_PHRASES):
                u["relation"] = "supersedes"
            else:
                u["relation"] = "amends"
            u["conflict_phrases"] = find_phrases(u["text"], CONFLICT_PHRASES)
        else:
            u["relation"] = ("superseded-by" if u["kind"] == "rule" and find_phrases(u["text"], SUPERSEDED_BY_PHRASES)
                             else None)
            u["conflict_phrases"] = []
        u["conflict"] = bool(u["conflict_phrases"])
    return units, parsed, dangling


def conflict_markers(docs):
    """Literal CONFLICT markers in ADRs, spec and design documents: [(file, line, text)]."""
    out = []
    for sub in ("adr", "spec", "design"):
        for path in sorted(glob.glob(os.path.join(docs, sub, "**", "*"), recursive=True)):
            if not os.path.isfile(path) or not path.endswith((".md", ".sql", ".csv")):
                continue
            for n, line in enumerate(read(path).split("\n"), start=1):
                if MARKER_RE.search(line):
                    out.append((rel(docs, path), n, line.strip()))
    return out


UNIT_FIELDS = ["id", "kind", "adr", "rule_no", "group", "section", "parent", "text", "source_file", "line_start",
               "line_end", "adr_status", "note_author", "note_date", "relation", "conflict", "conflict_phrases",
               "conflict_markers", "xrefs_adrs", "xrefs_rules", "xrefs_inv", "xrefs_ec", "xrefs_ds", "xrefs_oq",
               "dangling"]


def unit_record(u):
    return {k: u.get(k) for k in UNIT_FIELDS}


# ------------------------------------------------------------------------------------------------ DDL, catalogs, modules

def load_gen_overview(docs):
    lab = os.path.join(docs, LAB)
    if lab not in sys.path:
        sys.path.insert(0, lab)
    return importlib.import_module("gen_overview")


def module_model(docs):
    """-> modules {name: (layer, note)}, owners {table: module or None}, declared {ADR number: set(modules)},
    table_files {table: (rel path, line)}."""
    g = load_gen_overview(docs)
    modules = g.module_map(docs)
    tables, _fks, _problems = g.parse_ddl(docs, modules)
    nums = {re.search(r"(\d{4})", os.path.basename(p)).group(1) for p in adr_files(docs)}
    declared = defaultdict(set)
    for mod, ns in g.declared_by_module(modules, tables, nums, docs).items():
        for n in ns:
            declared[n].add(mod)
    owners = {name: t.owner for name, t in tables.items()}
    files = {name: (t.path, t.line) for name, t in tables.items()}
    for path in sorted(glob.glob(os.path.join(docs, "design", "**", "*.sql"), recursive=True)):
        for n, line in enumerate(read(path).split("\n"), start=1):   # gen_overview reads design/*.sql only
            m = re.match(r"^CREATE TABLE (\w+)\s*\(", line)
            if m and m.group(1) not in owners:
                owners[m.group(1)], files[m.group(1)] = None, (rel(docs, path), n)
    return modules, owners, dict(declared), files


def table_ddl(docs, rel_path, line_no):
    """The CREATE TABLE statement from its line to the closing ')' line."""
    lines = read(os.path.join(docs, rel_path[len("docs/"):])).split("\n")
    out = []
    for i in range(line_no - 1, len(lines)):
        out.append(lines[i])
        if lines[i].startswith(")"):
            break
    return "\n".join(out)


def csv_line(row):
    buf = io.StringIO()
    csv.writer(buf, lineterminator="").writerow(row)
    return buf.getvalue()


def load_catalogs(docs):
    """-> ({catalog: {key: (csv line, row dict)}}, [catalogs skipped because their first column repeats])."""
    cats, skipped = {}, []
    for path in sorted(glob.glob(os.path.join(docs, "catalogs", "*.csv"))):
        name = os.path.basename(path)[:-4]
        with open(path, encoding="utf-8", newline="") as fh:
            rows = [r for r in csv.reader(fh) if r]
        if not rows:
            continue
        header, body = rows[0], rows[1:]
        keys = [r[0] for r in body]
        if len(keys) != len(set(keys)):
            skipped.append(name)
            continue
        cats[name] = {r[0]: (csv_line(r), dict(zip(header, r))) for r in body}
    return cats, skipped


CODE_SPAN_RE = re.compile(r"`([^`\n]+)`")


def code_spans(text):
    """Inline code spans plus the content of fenced code blocks."""
    spans = CODE_SPAN_RE.findall(re.sub(r"```.*?```", " ", text, flags=re.S))
    spans += re.findall(r"```(.*?)```", text, flags=re.S)
    return spans


def key_regex(key):
    """A key, with placeholders such as `agents.<agent_type>.drift_action` matching either form, as a whole word."""
    parts = re.split(r"(<[^>]+>)", key)
    rx = "".join(r"(?:<[^>]+>|\w+)" if p.startswith("<") else re.escape(p) for p in parts)
    edge = r"[\w.]" if "." in key else r"\w"
    return re.compile(r"(?<!" + edge + ")" + rx + r"(?!" + edge + ")")


class Matcher:
    """Finds DDL tables and catalog rows referenced in a text: names in backticks or code, whole word, length >= 4;
    INV-nn and EC-nn anywhere."""

    def __init__(self, owners, cats):
        self.cats = cats
        self.tables = [(t, key_regex(t)) for t in sorted(owners) if len(t) >= 4]
        self.table_names = set(owners)
        self.keys = []
        for cat, entries in sorted(cats.items()):
            if cat in ("invariants", "edge-cases"):
                continue
            for key in sorted(entries):
                if len(key) >= 4:
                    probe = key.split("<")[0] or key
                    self.keys.append((cat, key, key_regex(key), probe))
        self.id_width = {cat: sorted({len(k.split("-", 1)[1]) for k in cats.get(cat, {})})
                         for cat in ("invariants", "edge-cases")}

    def find(self, text):
        joined = "\n".join(code_spans(text))
        tables = [t for t, rx in self.tables if t in joined and rx.search(joined)]
        # a catalog key spelled like a DDL table is credited to the table only (listed as ambiguous by build_index)
        rows = [f"{cat}:{key}" for cat, key, rx, probe in self.keys
                if key not in self.table_names and probe in joined and rx.search(joined)]
        for cat, rx, prefix in (("invariants", OTHER_REFS["inv"], "INV"), ("edge-cases", OTHER_REFS["ec"], "EC")):
            for n in sorted({int(x) for x in rx.findall(text)}):
                for w in self.id_width[cat]:
                    key = f"{prefix}-{n:0{w}d}"
                    if key in self.cats.get(cat, {}):
                        rows.append(f"{cat}:{key}")
                        break
        return tables, sorted(set(rows))


def first_step(text):
    for m in STEP_RE.finditer(text):
        if m.group(1) in STEP_VOCAB:
            return m.group(1)
    return ""


# ------------------------------------------------------------------------------------------------ module scope

def module_scope(rows, owners, cats, module):
    """What belongs to one module, shared by build_dossiers and doc_lint (one definition):
    units: index rows of the module (rows whose `modules` is `cross` belong to module `cross` only);
    tables: tables the module owns (none for `cross` and `unassigned`);
    catalog_rows: rows its units reference, plus invariants and edge cases whose `area` is the module."""
    def mods(r):
        m = r["modules"]
        return m if isinstance(m, list) else [x for x in m.split(";") if x]
    units = [r for r in rows if module in mods(r)]
    tables = [] if module in ("cross", "unassigned") else sorted(t for t, o in owners.items() if o == module)
    refs = set()
    for r in units:
        cr = r["catalog_rows"]
        refs.update(cr if isinstance(cr, list) else [x for x in cr.split(";") if x])
    for cat in ("invariants", "edge-cases"):
        for key, (_line, row) in cats.get(cat, {}).items():
            if row.get("area") == module:
                refs.add(f"{cat}:{key}")
    return units, tables, sorted(refs)


def table_columns(docs):
    """{table: [column, ...]} as gen_overview.parse_ddl reads them."""
    g = load_gen_overview(docs)
    tables, _f, _p = g.parse_ddl(docs, g.module_map(docs))
    return {name: list(t.columns) for name, t in tables.items()}
