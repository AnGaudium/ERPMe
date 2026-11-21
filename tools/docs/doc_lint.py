#!/usr/bin/env python3
"""Tool 4 (S3): lint a compiled spec (docs/design/compiled-spec-template.md) against the rule index and the module
scope of nfdocs.module_scope.

Usage: doc_lint.py SPEC.md [SPEC-2.md ...] --module M [--index CSV] [--index-commit SHA] [--docs DIR] [--json]

Stance: the lint is a completeness and trace backstop against cooperative compilers. Whether a statement says what
its sources say is the different-model spot check of the template; the lint closes the known shortcuts and prints a
REVIEW LIST of every Conflicts entry for the chief architect.

Several files are the chunks of one module: L1, L2, L5, L9, L10 and the section list of L0 are checked over all of
them together, the rest per file. First output line: `LINT PASS findings=0` or `LINT FAIL findings=N`; then one
finding per line (`L<n> <file>:<line>: <message>`), warnings (`W<n>`) and the REVIEW LIST; or with --json one line of
JSON. Exit 0 on PASS, 1 on FAIL, 2 on bad input.

Checks:
  L0  front matter: `Module:` (equal to --module), `Chunk:` (`whole` or `n of m`), `Source ADRs:`, `Build step(s):`,
      `Generated from index:` (must be the last commit of the index file in HEAD; note IDs are positional, so a spec
      is compiled against one index commit) and `Compiled by:`; the `##` sections are the template's eleven, in its
      order, no others; every file has `## Purpose` and `## Trace`, and all eleven appear across the chunks;
  L1  every rule, note and Decision text ID of the module appears in the `## Trace` table.
      - An R-number is defined by `R<n>.` in `## Rules` or `## Proposed (not law)`, outside code fences, HTML comments
        and `Reads` lines, with a statement of 40 characters or more (without its `Source:`) that repeats no other.
      - A rule's `Where` is one or more defined R-numbers (ranges `R3-R7`), or `ref: <module> R-<n>` /
        `ref: ADR-nnnn.Rk` when the module is not primary for the rule (template rule 6); a heading alone is refused.
      - A note's or section's `Where` may also be a heading of the spec or `not applicable: <reason>`; at most 15% of
        the module's units may be `not applicable`.
      - Coverage: the rule units mapped to R-numbers, counting at most 4 IDs per R-number, are 60% or more of the
        rule units not traced as `ref:`.
      - `Reads` and empty cells are refused; other values are warnings. A Source cell may carry the unit's
        `#<stable_key>` (index column); a mismatch is a warning (the text changed or the note was renumbered);
  L2  every table the module owns and every catalog row it owns (module_scope `owned_rows`) is backticked in the
      body; other modules' rows may stand in a `Reads` list and are not required;
  L3  a line citing a rule of a proposed ADR (`ADR-0070.R12`, `ADR-0070 rule 12`, `ADR-0070, rule 12`,
      `rule 12 of ADR-0070`) is under `## Proposed (not law)` or carries `[proposed]`; a line citing only accepted
      rules carries neither; a proposed ID's trace R-numbers are defined under `## Proposed (not law)` or `[proposed]`;
  L4  no typed count: a number (digits, number words from two, `twenty-one`, `a dozen`) before a counted noun, up to
      three words between, or after it (`Tables owned: 10`), or a table row `| ... tables | 16 |`, also in backticks
      and with `&nbsp;`, is a finding. `one` is not a count; citations (`rule 15 note`, `7 of rule`, `INV-12`) and
      `at most|at least|up to|more than|fewer than|less than` thresholds pass; `exactly` and `only` do not.
      `<!-- count:KIND -->N<!-- /count -->` is recomputed (tables, rules, catalog-rows, settings; also notes,
      sections, columns, invariants, edge-cases);
  L5  `## Conflicts`: `CONFLICT <id>: <reason>`, `FALSE-POSITIVE <id>: <reason>` (25 characters or more; one reason,
      or one more than 0.8 similar, may serve at most 3 entries), `OPEN <id>: ...` with an `OQ-nnn` or an
      open-questions anchor; every ID exists in the index. Required: every unit with a CONFLICT marker (CONFLICT or
      OPEN); every conflict-flagged note (any entry); every note whose relation is `supersedes` or `superseded-by`
      (CONFLICT naming the governing text, an ADR unit ID or R-number, or OPEN; FALSE-POSITIVE is refused) unless its
      Where is `ref:`;
  L6  each file is within the hard budget (16,000 tokens, bytes / 3.5); sizes per `## ` section are reported;
  L7  every ID in the trace table exists in the index;
  L8  a cross-module reference `<module> R-<n>` (template rule 6) names a module and a numeric rule; `R-scrap`, a bare
      `R-3` and `nosuch R-1` are findings; a backticked `<word> ADR-nnnn` must name a module;
  L9  every setting key referenced by the module's units is backticked in the body (or in `Reads`);
  L10 every rule of the module that another unit supersedes (index `superseded_by`) or whose text says it is
      superseded has a CONFLICT naming the governing text, or OPEN, unless its Where is `ref:`. A superseded rule
      traced to an R-number whose text names none of its superseding IDs is a warning (W3).
"""

import argparse
import difflib
import json
import os
import re
import subprocess
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import nfdocs  # noqa: E402
import build_index  # noqa: E402

SECTIONS = ["Purpose", "Entities and tables", "Commands and queries", "Rules", "Invariants", "Edge cases", "Settings",
            "UI annotations", "Conflicts", "Proposed (not law)", "Trace"]
PER_FILE_SECTIONS = ("Purpose", "Trace")
PROPOSED_HEADING = "Proposed (not law)"
FRONT_FIELDS = ["Module", "Chunk", "Source ADRs", "Build step(s)", "Generated from index", "Compiled by"]
MIN_REASON = 25
MIN_RULE_TEXT = 30
MAX_REASON_REUSE = 3
REASON_SIMILARITY = 0.8
MIN_COVERAGE = 0.60
MAX_IDS_PER_R = 4
MAX_NA_SHARE = 0.15

UNIT_ID_RE = re.compile(r"ADR-\d{4}\.(?:L\d+\.)?(?:R\d+[a-z]?|D\d+|W\d*|[A-Z]\d*)(?:\.N\d+)?")
COUNT_RE = re.compile(r"<!--\s*count:([\w-]+)\s*-->\s*(\d+)\s*<!--\s*/count\s*-->")
TENS = "twenty thirty forty fifty sixty seventy eighty ninety".split()
UNITS = "two three four five six seven eight nine".split()
NUMBER_WORDS = UNITS + ("ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen hundred "
                        "dozen").split() + TENS
NUM = (r"(?:\d[\d,]*|(?:" + "|".join(TENS) + r")-(?:one|" + "|".join(UNITS) + r")|(?:a\s+)?(?:" +
       "|".join(NUMBER_WORDS) + r"))")
NOUNS = r"(?:tables?|rules?|columns?|settings?|commands?|queries|query|notes?|invariants?|edge cases?|modules?|" \
        r"catalog rows?|events?|chunks?)"
COUNT_BEFORE_RE = re.compile(r"(?<![\w.\-/])(" + NUM + r")\s+(?!of\b|to\b)(?:[^\s|:;.()]+\s+){0,3}?" + NOUNS +
                             r"\b(?!\s*\(?\d)", re.I)   # 'rule 3', 'note (2)': a citation, not a count
COUNT_AFTER_RE = re.compile(r"\b(?!notes?\b)" + NOUNS + r"(?:\s+\w+)?\s*[:=]\s*(" + NUM + r")\b", re.I)   # not 'Note: two' 
COUNT_CELL_RE = re.compile(r"\|[^|]*\b" + NOUNS + r"\b[^|]*\|\s*(" + NUM + r")\s*\|", re.I)
CITATION_WORDS = {"rule", "rules", "step", "steps", "phase", "layer", "layers", "section", "sections", "class", "level",
                  "floor", "round", "pass", "finding", "item", "items", "note", "notes", "chunk", "part", "version",
                  "wave", "principle", "spec", "stage", "page", "line", "lines", "s"}
THRESHOLD_RE = re.compile(r"(?:at most|at least|up to|more than|fewer than|less than)\s*$", re.I)
XREF_R_RE = re.compile(r"(?:(?<![\w-])([A-Za-z_][\w]*)\s+)?(?<![\w-])R-([\w-]*)")
XREF_ADR_RE = re.compile(r"`([a-z][a-z0-9_]*)`?\s+`?ADR-\d{4}")
WHERE_R_RE = re.compile(r"^R(\d+)([a-z]?)(?:\s*[-–]\s*R?(\d+)([a-z]?))?$")
REF_RE = re.compile(r"^ref:\s*(?:([a-z][a-z0-9_]*)\s+R-(\d+[a-z]?)|(" + UNIT_ID_RE.pattern + r"))$")
RULE_DEF_RE = re.compile(r"^\s*(?:[-*]\s+)?\**R(\d+[a-z]?)\**\.\s?(.*)$")
ENTRY_RE = re.compile(r"\b(CONFLICT|FALSE-POSITIVE|OPEN)\s+`?(" + UNIT_ID_RE.pattern + r")`?\s*[:\-–—]?\s*(.*)$")
KEY_IN_CELL_RE = re.compile(r"#([0-9a-f]{12})\b")
GOVERNING_RE = re.compile(r"ADR-\d{4}\.|\bR\d+[a-z]?\b")


def unit_ids_in(text):
    """IDs written as `ADR-0070.R12`, `ADR-0070 rule 12`, `ADR-0070, rule 12` and `rule 12 of ADR-0070`."""
    ids = set(UNIT_ID_RE.findall(text))
    ids.update(nfdocs.find_refs(text)[1])
    return ids


def mask(lines):
    """Blank out code fences and HTML comments (count markers kept), keeping line numbers."""
    out, fence, comment = [], False, False
    for l in lines:
        if l.lstrip().startswith("```"):
            fence = not fence
            out.append("")
            continue
        if fence:
            out.append("")
            continue
        s, buf, i = l, "", 0
        while i < len(s):
            if comment:
                j = s.find("-->", i)
                if j < 0:
                    i = len(s)
                    break
                comment, i = False, j + 3
            else:
                j = s.find("<!--", i)
                if j < 0:
                    buf += s[i:]
                    break
                m = COUNT_RE.match(s, j)
                if m:
                    buf += s[i:m.end()]
                    i = m.end()
                    continue
                buf += s[i:j]
                comment, i = True, j + 4
        out.append(buf)
    return out


class Spec:
    def __init__(self, path):
        self.path = path
        self.text = nfdocs.read(path)
        self.lines = self.text.split("\n")
        self.vis = mask(self.lines)          # what a reader sees: no fences, no comments
        self.sections = []   # (heading, start index, end index)
        heads = [(i, l[3:].strip()) for i, l in enumerate(self.vis) if l.startswith("## ")]
        for k, (i, h) in enumerate(heads):
            self.sections.append((h, i, heads[k + 1][0] if k + 1 < len(heads) else len(self.lines)))
        self.first_heading = heads[0][0] if heads else len(self.lines)
        self.headings = {re.sub(r"[`#]", "", l).strip().lower() for l in self.vis if re.match(r"^#{2,3} ", l)}
        self.defined, self.bad_defs = {}, []    # R-number -> (section, line, proposed, text)
        self._find_defs()

    def _find_defs(self):
        seen = {}
        i = 0
        while i < len(self.vis):
            m = RULE_DEF_RE.match(self.vis[i])
            sec = self.section_of(i)
            if not (m and sec in ("Rules", PROPOSED_HEADING) and not self.vis[i].lstrip().lower().startswith("reads")):
                i += 1
                continue
            parts, j = [m.group(2)], i + 1
            while j < len(self.vis) and self.vis[j].strip() and not RULE_DEF_RE.match(self.vis[j]) \
                    and not self.vis[j].startswith("#"):
                parts.append(self.vis[j].strip())
                j += 1
            text = " ".join(parts)
            statement = re.sub(r"\bSource:.*$", "", text).strip()
            norm = re.sub(r"\W+", " ", statement.lower()).strip()
            n = m.group(1)
            if len(statement) < MIN_RULE_TEXT:
                self.bad_defs.append((i, n, f"R{n} has no real statement (under {MIN_RULE_TEXT} characters)"))
            elif norm in seen:
                self.bad_defs.append((i, n, f"R{n} repeats the statement of R{seen[norm]}"))
            elif n not in self.defined:
                seen[norm] = n
                self.defined[n] = (sec, i, "[proposed]" in text, text)
            i = j

    def section_of(self, i):
        for h, a, b in self.sections:
            if a <= i < b:
                return h
        return None

    def section_lines(self, name, visible=True):
        src = self.vis if visible else self.lines
        for h, a, b in self.sections:
            if h == name:
                return [(i, src[i]) for i in range(a + 1, b)]
        return None

    def body_lines(self):
        """Visible lines after the front matter and outside the Trace section."""
        return [(i, l) for i, l in enumerate(self.vis)
                if i >= self.first_heading and self.section_of(i) != "Trace"]

    def front(self):
        text = "\n".join(self.lines[:self.first_heading])
        out = {}
        for name in FRONT_FIELDS:
            others = "|".join(re.escape(n) for n in FRONT_FIELDS if n != name)
            m = re.search(re.escape(name) + r":\s*(.*?)\s*(?=(?:" + others + r"):|$)", text, re.M)
            if m:
                out[name] = (m.group(1).strip(), text[:m.start()].count("\n"))
        return out

    def trace(self):
        rows = []
        lines = self.section_lines("Trace")
        if lines is None:
            return None
        for i, l in lines:
            s = l.strip()
            if not s.startswith("|") or re.match(r"^\|[\s:|-]+\|$", s):
                continue
            cells = [c.strip() for c in s.strip("|").split("|")]
            if cells and cells[0].strip("` ").lower() == "source":
                continue
            key = KEY_IN_CELL_RE.search(cells[0])
            ids = sorted(unit_ids_in(cells[0].replace("`", ""))) or [cells[0].strip("` ")]
            for uid in ids:
                rows.append((i, uid, cells[1] if len(cells) > 1 else "", key.group(1) if key else None))
        return rows


def where_parts(where):
    w = re.sub(r"`", "", where).strip()
    return [p.strip() for p in re.split(r"[;,]", w) if p.strip()]


def expand_where_r(part):
    m = WHERE_R_RE.match(part)
    if not m:
        return None
    if not m.group(3):
        return [m.group(1) + m.group(2)]
    lo, hi = int(m.group(1)), int(m.group(3))
    if hi < lo or hi - lo > 200:
        return [m.group(1) + m.group(2), m.group(3) + m.group(4)]
    return [str(n) for n in range(lo, hi + 1)]


def git(args, cwd):
    try:
        out = subprocess.run(["git"] + args, cwd=cwd, capture_output=True, text=True, timeout=20)
    except (OSError, subprocess.SubprocessError):
        return None, None
    return out.returncode, out.stdout.strip()


def index_commit(index_path):
    rc, out = git(["log", "-1", "--format=%H", "--", os.path.abspath(index_path)], os.path.dirname(os.path.abspath(index_path)))
    return (out or None) if rc == 0 else None


def lint(paths, module, index_path, docs, index_sha=None):
    findings, warnings, review, info = [], [], [], {"files": {}}

    def f(check, path, line, msg):
        findings.append({"check": check, "file": path, "line": line, "message": msg})

    rows = build_index.read_index(index_path)
    by_id = {r["id"]: r for r in rows}
    modules, owners, _declared, _files = nfdocs.module_model(docs)
    known_modules = set(modules) | nfdocs.NON_CODE_MODULES | {"cross"}
    cats, _skipped = nfdocs.load_catalogs(docs)
    scope = nfdocs.module_scope(rows, owners, cats, module)
    units, tables = scope["units"], scope["tables"]
    if not units and not tables:
        raise SystemExit(f"doc_lint: module '{module}' has no units and no tables in the index")
    specs = [Spec(p) for p in paths]
    unit_ids = {r["id"] for r in units}
    headings = set().union(*(s.headings for s in specs))
    defined = {}
    for s in specs:
        for k, v in s.defined.items():
            defined.setdefault(k, v)
        for i, n, msg in s.bad_defs:
            f("L1", s.path, i + 1, msg)

    def resolve_r(n):
        if n in defined:
            return n
        sub = sorted(k for k in defined if re.fullmatch(re.escape(n) + r"[a-z]", k))   # R50 when R50a. exists
        return sub[0] if sub else None

    # L0: front matter and sections
    sha = index_sha or index_commit(index_path)
    if index_sha is None and sha:
        rc, _ = git(["diff", "--quiet", "HEAD", "--", os.path.abspath(index_path)],
                    os.path.dirname(os.path.abspath(index_path)))
        if rc == 1:
            warnings.append(f"W0 {index_path}: the index differs from its committed version; commit it before "
                            f"compiling against it")
    for s in specs:
        fm = s.front()
        for name in FRONT_FIELDS:
            if name not in fm or not fm[name][0]:
                f("L0", s.path, 1, f"front matter field '{name}:' is missing or empty")
        if "Module" in fm and fm["Module"][0] != module:
            f("L0", s.path, fm["Module"][1] + 1, f"front matter Module '{fm['Module'][0]}' is not --module '{module}'")
        if "Chunk" in fm and fm["Chunk"][0] and not re.fullmatch(r"whole|\d+ of \d+", fm["Chunk"][0]):
            f("L0", s.path, fm["Chunk"][1] + 1, f"Chunk '{fm['Chunk'][0]}' is not 'whole' or 'n of m'")
        if fm.get("Generated from index", ("",))[0]:
            given = fm["Generated from index"][0]
            if sha is None:
                warnings.append(f"W0 {s.path}: cannot read the index commit; 'Generated from index' not compared")
            elif not (len(given) >= 7 and sha.startswith(given)):
                f("L0", s.path, fm["Generated from index"][1] + 1,
                  f"Generated from index '{given}' is not the committed index {sha[:12]}; note IDs may have moved, "
                  f"re-lint against the current index")
        names = [h for h, _a, _b in s.sections]
        for h, a, _b in s.sections:
            if h not in SECTIONS:
                f("L0", s.path, a + 1, f"section '## {h}' is not one of the template's sections")
        order = [SECTIONS.index(h) for h in names if h in SECTIONS]
        if order != sorted(order) or len(order) != len(set(order)):
            f("L0", s.path, 1, "sections are out of the template's order or repeated")
        for h in PER_FILE_SECTIONS:
            if h not in names:
                f("L0", s.path, 1, f"section '## {h}' is required in every file")
    present = {h for s in specs for h, _a, _b in s.sections}
    for h in SECTIONS:
        if h not in present:
            f("L0", specs[0].path, 1, f"section '## {h}' is missing")

    # L7 and L1
    traced, refs_of, rs_of, na_ids = {}, set(), {}, set()
    for s in specs:
        tr = s.trace()
        if tr is None:
            continue
        for i, uid, where, key in tr:
            traced.setdefault(uid, (s.path, i + 1))
            if uid not in by_id:
                f("L7", s.path, i + 1, f"trace ID {uid} is not in the rule index")
                continue
            row = by_id[uid]
            if key and key != row.get("stable_key"):
                same = [r["id"] for r in rows if r.get("stable_key") == key]
                warnings.append(f"W2 {s.path}:{i + 1}: {uid} #{key} does not match the index ({row.get('stable_key')})"
                                + (f"; that text is now {', '.join(same)}" if same else "; the text changed"))
            kind, primary = row["kind"], row["primary_module"]
            parts = where_parts(where)
            if not parts:
                f("L1", s.path, i + 1, f"trace row {uid} has an empty 'Where'")
                continue
            has_r = has_ref = False
            for p in parts:
                na = re.match(r"(?i)^not applicable\s*:?\s*(.*)$", p)
                ref = REF_RE.match(p)
                rs = expand_where_r(p)
                if na:
                    na_ids.add(uid)
                    if kind == "rule":
                        f("L1", s.path, i + 1, f"trace row {uid}: 'not applicable' is refused for a rule")
                    elif not na.group(1).strip():
                        f("L1", s.path, i + 1, f"trace row {uid}: 'not applicable' needs a reason")
                elif ref:
                    has_ref = True
                    refs_of.add(uid)
                    if module in primary:
                        f("L1", s.path, i + 1, f"trace row {uid}: 'ref:' is for other modules' law; {module} is "
                                               f"primary for it, state it")
                    elif ref.group(1) and (ref.group(1) not in known_modules or ref.group(1) == module):
                        f("L8", s.path, i + 1, f"trace row {uid}: 'ref: {ref.group(1)} R-…' names no other module")
                    elif ref.group(3) and ref.group(3) not in by_id:
                        f("L7", s.path, i + 1, f"trace row {uid}: 'ref: {ref.group(3)}' is not in the rule index")
                elif p.lower().startswith("reads"):
                    f("L1", s.path, i + 1, f"trace row {uid}: a 'Reads' list does not state a rule")
                elif rs is not None:
                    for n in rs:
                        got = resolve_r(n)
                        if got is None:
                            f("L1", s.path, i + 1, f"trace row {uid}: R{n} is not defined in the spec")
                            continue
                        has_r = True
                        rs_of.setdefault(uid, set()).add(got)
                        if row["status"] == "proposed" and not (
                                defined[got][0] == PROPOSED_HEADING or defined[got][2]):
                            f("L3", s.path, i + 1, f"trace row {uid} (proposed) points to R{got}, stated as law")
                elif re.sub(r"#", "", p).strip().lower() in headings:
                    pass
                else:
                    warnings.append(f"W1 {s.path}:{i + 1}: trace row {uid}: 'Where' part '{p}' is not an R-number, "
                                    f"ref:, a heading or 'not applicable: <reason>'")
            if kind == "rule" and not has_r and not has_ref:
                f("L1", s.path, i + 1, f"trace row {uid}: a rule must point to a defined R-number (or ref: when "
                                       f"another module is primary)")
    for uid in sorted(unit_ids - set(traced), key=nfdocs.rule_sort_key):
        f("L1", specs[0].path, 0, f"{uid} ({by_id[uid]['kind']}) is missing from the trace table")
    rule_units = [r["id"] for r in units if r["kind"] == "rule" and r["id"] not in refs_of]
    load = Counter()
    mapped = 0
    for uid in rule_units:
        for n in sorted(rs_of.get(uid, ())):
            if load[n] < MAX_IDS_PER_R:
                load[n] += 1
                mapped += 1
                break
    if rule_units and mapped < MIN_COVERAGE * len(rule_units):
        f("L1", specs[0].path, 0, f"{mapped} of {len(rule_units)} source rules map to R-numbers (counting at most "
                                  f"{MAX_IDS_PER_R} per R-number); {int(MIN_COVERAGE * 100)}% is required")
    if units and len(na_ids & unit_ids) > MAX_NA_SHARE * len(units):
        f("L1", specs[0].path, 0, f"{len(na_ids & unit_ids)} of {len(units)} units are 'not applicable' (more than "
                                  f"{int(MAX_NA_SHARE * 100)}%)")

    # L2 and L9
    spans = []
    for s in specs:
        spans += nfdocs.code_spans("\n".join(l for i, l in enumerate(s.lines)
                                             if i >= s.first_heading and s.section_of(i) != "Trace"))
    joined = "\n".join(spans)
    for t in tables:
        if not nfdocs.key_regex(t).search(joined):
            f("L2", specs[0].path, 0, f"owned table `{t}` is not mentioned in backticks")
    for c in scope["owned_rows"]:
        if not nfdocs.key_regex(c.split(":", 1)[1]).search(joined):
            f("L2", specs[0].path, 0, f"owned catalog row {c} is not mentioned in backticks")
    for c in scope["settings"]:
        key = c.split(":", 1)[1]
        if c not in scope["owned_rows"] and not nfdocs.key_regex(key).search(joined):
            f("L9", specs[0].path, 0, f"setting `{key}` is referenced by the module's rules but not in the body "
                                      f"or `Reads`")

    # L3, L4, L8 per file
    columns = None
    for s in specs:
        for i, line in s.body_lines():
            sec = s.section_of(i)
            for m in XREF_R_RE.finditer(line):
                word, num = m.group(1), m.group(2)
                if word == "ref" or (line[:m.start()].rstrip().endswith("ref:")):
                    continue
                if not re.fullmatch(r"\d+[a-z]?", num or ""):
                    f("L8", s.path, i + 1, f"cross-module reference 'R-{num}' is not a rule number")
                elif word not in known_modules:
                    f("L8", s.path, i + 1, f"cross-module reference '{(word or '') + ' '}R-{num}' does not start "
                                           f"with a module name")
            for m in XREF_ADR_RE.finditer(line):
                if m.group(1) not in known_modules:
                    f("L8", s.path, i + 1, f"cross-module reference '{m.group(1)} ADR-…' names no module")
            for kind, n in count_findings(line):
                if kind is None:
                    f("L4", s.path, i + 1, f"typed count '{n}'; write <!-- count:KIND -->N<!-- /count --> or list it")
                    continue
                if kind == "columns" and columns is None:
                    columns = nfdocs.table_columns(docs)
                want = expected_count(kind, scope, columns)
                if want is None:
                    f("L4", s.path, i + 1, f"count kind '{kind}' cannot be computed from the index")
                elif want != n:
                    f("L4", s.path, i + 1, f"count:{kind} says {n}, the index gives {want}")
            if sec == "Conflicts":
                continue
            cited = [u for u in unit_ids_in(line) if u in by_id]
            prop = sorted(u for u in cited if by_id[u]["status"] == "proposed")
            marked = "[proposed]" in line
            in_prop = sec == PROPOSED_HEADING
            if prop and not (marked or in_prop):
                f("L3", s.path, i + 1, f"cites proposed {', '.join(prop)} outside '## {PROPOSED_HEADING}' "
                                        f"without [proposed]")
            if cited and not prop and (marked or in_prop):
                f("L3", s.path, i + 1, "accepted rule marked as proposed: " + ", ".join(sorted(cited)))

    # L5 and L10
    entries = {"CONFLICT": {}, "FALSE-POSITIVE": {}, "OPEN": {}}
    fp_reasons = []
    for s in specs:
        for i, l in s.section_lines("Conflicts") or []:
            m = ENTRY_RE.search(l)
            if not m:
                continue
            word, uid, reason = m.group(1), m.group(2), m.group(3).strip()
            entries[word][uid] = reason
            review.append(f"{word} {uid}: {reason}")
            if uid not in by_id:
                f("L5", s.path, i + 1, f"{word} {uid}: not in the rule index")
            if word in ("CONFLICT", "FALSE-POSITIVE") and len(reason) < MIN_REASON:
                f("L5", s.path, i + 1, f"{word} {uid}: the reason needs {MIN_REASON} characters or more")
            if word == "OPEN" and not re.search(r"\bOQ-\d+\b|open-questions(?:\.md)?#", reason):
                f("L5", s.path, i + 1, f"OPEN {uid}: name its OQ-nnn or open-questions anchor")
            if word == "FALSE-POSITIVE":
                fp_reasons.append((s.path, i + 1, uid, re.sub(r"\s+", " ", reason.lower())))
    reported = set()
    for k, (path, line, uid, text) in enumerate(fp_reasons):
        same = [u for (_p, _l, u, t) in fp_reasons
                if t == text or difflib.SequenceMatcher(None, t, text).ratio() > REASON_SIMILARITY]
        if len(same) > MAX_REASON_REUSE and text not in reported:
            reported.add(text)
            f("L5", path, line, f"one FALSE-POSITIVE reason (or a near copy) serves {len(same)} entries "
                                f"({', '.join(same[:5])}{'…' if len(same) > 5 else ''}); give each its own reason")
    any_entry = set(entries["CONFLICT"]) | set(entries["FALSE-POSITIVE"]) | set(entries["OPEN"])

    def governs(uid):
        """CONFLICT naming the governing text (an ADR unit ID or an R-number), or OPEN."""
        return uid in entries["OPEN"] or (uid in entries["CONFLICT"] and GOVERNING_RE.search(entries["CONFLICT"][uid]))

    for r in units:
        uid = r["id"]
        if r["conflict_markers"] and not (uid in entries["CONFLICT"] or uid in entries["OPEN"]):
            f("L5", specs[0].path, 0, f"{uid} carries a CONFLICT marker; list 'CONFLICT {uid}: <resolution>'")
        if r["kind"] == "note" and r["relation"] in ("supersedes", "superseded-by") and uid not in refs_of:
            if not (governs(uid) or governs(r["parent"])):
                how = "FALSE-POSITIVE is refused for it; " if uid in entries["FALSE-POSITIVE"] else ""
                f("L5", specs[0].path, 0, f"{uid} (relation {r['relation']}): {how}list 'CONFLICT {uid}: <which "
                                          f"text governs, an ADR unit ID or R-number>' or OPEN")
        elif r["kind"] == "note" and r["conflict_flag"] and not (uid in any_entry or r["parent"] in any_entry):
            f("L5", specs[0].path, 0, f"{uid} (conflict flag {';'.join(r['conflict_phrases'])}) is not listed under "
                                      f"'## Conflicts'")
        if r["kind"] == "rule" and (r["superseded_by"] or r["relation"] == "superseded-by") and uid not in refs_of:
            by = ", ".join(r["superseded_by"]) or "its own text"
            if not governs(uid):
                how = "FALSE-POSITIVE is refused for it; " if uid in entries["FALSE-POSITIVE"] else ""
                f("L10", specs[0].path, 0, f"{uid} is superseded ({by}); {how}list 'CONFLICT {uid}: <which text "
                                           f"governs>' or OPEN")
            for n in rs_of.get(uid, ()):
                if r["superseded_by"] and not any(x in defined[n][3] for x in r["superseded_by"]):
                    warnings.append(f"W3 {uid} is superseded by {by} but R{n} names none of them; check that R{n} "
                                    f"states the governing text")

    # L6
    for s in specs:
        size = len(s.text.encode("utf-8"))
        tokens = round(size / nfdocs.TOKEN_BYTES)
        per = {h: round(len("\n".join(s.lines[a:b]).encode("utf-8")) / nfdocs.TOKEN_BYTES) for h, a, b in s.sections}
        info["files"][s.path] = {"bytes": size, "est_tokens": tokens, "sections": per}
        if tokens > nfdocs.SPEC_HARD_TOKENS:
            f("L6", s.path, 0, f"{tokens} tokens (bytes / 3.5) over the hard limit {nfdocs.SPEC_HARD_TOKENS}; "
                               f"split into chunks at '###' topics")
    info.update(module=module, module_ids=len(unit_ids), tables=len(tables), owned_rows=len(scope["owned_rows"]),
                settings=len(scope["settings"]), defined_r=len(defined), mapped_rules=mapped,
                not_applicable=len(na_ids & unit_ids), warnings=warnings, review=review)
    findings.sort(key=lambda x: (x["check"], x["file"], x["line"], x["message"]))
    return findings, info


def count_findings(line):
    """-> [(kind, n)] for count markers and [(None, text)] for typed counts in one line."""
    out = [(m.group(1), int(m.group(2))) for m in COUNT_RE.finditer(line)]
    text = COUNT_RE.sub(" ", line).replace("&nbsp;", " ").replace(" ", " ")
    text = re.sub(r"ADR-\d{4}(?:\.[\w.]+)?|\b(?:INV|EC|DS|OQ)-\d+|\bR-?\d+[a-z]?\b", " ", text)
    for m in COUNT_BEFORE_RE.finditer(text):
        before = text[:m.start()]
        prev = re.findall(r"[\w-]+", before[-40:])
        if prev and prev[-1].lower() in CITATION_WORDS:
            continue
        if THRESHOLD_RE.search(before):
            continue
        out.append((None, m.group(0).strip()))
    for rx in (COUNT_AFTER_RE, COUNT_CELL_RE):
        for m in rx.finditer(text):
            out.append((None, m.group(0).strip()))
    return out


def expected_count(kind, scope, columns):
    units, tables, cat_rows = scope["units"], scope["tables"], scope["catalog_rows"]
    k = {"rule": "rules", "note": "notes", "table": "tables", "setting": "settings", "invariant": "invariants",
         "edge-case": "edge-cases", "catalog-row": "catalog-rows", "column": "columns",
         "section": "sections"}.get(kind, kind)
    if k == "rules":
        return sum(1 for r in units if r["kind"] == "rule")
    if k == "notes":
        return sum(1 for r in units if r["kind"] == "note")
    if k == "sections":
        return sum(1 for r in units if r["kind"] == "section")
    if k == "tables":
        return len(tables)
    if k == "columns":
        return sum(len(columns.get(t, [])) for t in tables)
    if k == "settings":
        return len(scope["settings"])
    if k == "invariants":
        return sum(1 for c in cat_rows if c.startswith("invariants:"))
    if k == "edge-cases":
        return sum(1 for c in cat_rows if c.startswith("edge-cases:"))
    if k == "catalog-rows":
        return len(cat_rows)
    return None


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("specs", nargs="+")
    ap.add_argument("--module", required=True)
    ap.add_argument("--index", default=nfdocs.DEFAULT_INDEX)
    ap.add_argument("--index-commit", help="commit to compare 'Generated from index' with (default: git log of the index)")
    ap.add_argument("--docs", default=nfdocs.DEFAULT_DOCS)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    for p in args.specs:
        if not os.path.isfile(p):
            print(f"doc_lint: no file {p}", file=sys.stderr)
            return 2
    try:
        findings, info = lint(args.specs, args.module, args.index, args.docs, args.index_commit)
    except SystemExit as e:
        print(str(e), file=sys.stderr)
        return 2
    head = f"LINT {'PASS' if not findings else 'FAIL'} findings={len(findings)}"
    print(head)
    if args.json:
        print(json.dumps({"result": head, "findings": findings, "info": info}, sort_keys=True))
    else:
        for x in findings:
            print(f"{x['check']} {x['file']}:{x['line']}: {x['message']}")
        for w in info["warnings"]:
            print(w)
        for p, st in info["files"].items():
            print(f"size {p}: {st['bytes']} bytes, ~{st['est_tokens']} tokens; " +
                  ", ".join(f"{h} ~{t}" for h, t in st["sections"].items()))
        print(f"REVIEW LIST ({len(info['review'])} entries for the chief architect; template acceptance step 3):")
        for e in info["review"]:
            print(f"  {e}")
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
