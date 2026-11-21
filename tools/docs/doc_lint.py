#!/usr/bin/env python3
"""Tool 4 (S3): lint a compiled spec (docs/design/compiled-spec-template.md) against the rule index and the module
scope of nfdocs.module_scope.

Usage: doc_lint.py SPEC.md [SPEC-2.md ...] --module M [--index CSV] [--index-commit SHA] [--docs DIR] [--json]

Several files are the chunks of one module: L1, L2, L5, L9 and L10 and the section list of L0 are checked over all of
them together, the rest per file. First output line: `LINT PASS findings=0` or `LINT FAIL findings=N`; then one
finding per line (`L<n> <file>:<line>: <message>`) and warnings, or with --json one line of JSON. Exit 0 on PASS, 1 on
FAIL, 2 on bad input.

Checks:
  L0  front matter: `Module:` (equal to --module), `Chunk:` (`whole` or `n of m`), `Source ADRs:`, `Build step(s):`,
      `Generated from index:` (a commit; compared with the last commit of the index file when it can be read, else a
      warning) and `Compiled by:`; the `##` sections are the template's eleven, in its order, no others; every file
      has `## Purpose` and `## Trace`, and all eleven appear across the chunks;
  L1  every rule, note and Decision text ID of the module appears in the `## Trace` table. Each `Where` is one or more
      of the spec's R-numbers (ranges `R3-R7` allowed), a heading of the spec, or `not applicable: <reason>`;
      an R-number must be defined as `R<n>.` in `## Rules` or `## Proposed (not law)`, not on a `Reads` line;
      `not applicable` is refused for a rule; a `Where` of `Reads` is refused; an empty `Where` is refused; any other
      value is a warning (template section 11). Coverage: fewer defined R-numbers than 25% of the module's rule IDs
      is a finding;
  L2  every table the module owns and every catalog row it owns (module_scope `owned_rows`) is backticked in the
      body; other modules' rows may stand in a `Reads` list and are not required;
  L3  a line citing a rule of a proposed ADR (forms `ADR-0070.R12` and `ADR-0070 rule 12`) is under
      `## Proposed (not law)` or carries `[proposed]`; a line citing only accepted rules carries neither; a proposed
      ID's trace `Where` R-numbers are defined under `## Proposed (not law)` or on a `[proposed]` line;
  L4  no typed count: a number (digits or a number word) before a counted noun, up to two words between, or after it
      (`Tables owned: 10`), also in backticks, is a finding; citations (`rule 15 note`, `step 7 events`, `INV-12`)
      and quoted thresholds (`at most 12 columns`) are not; `<!-- count:KIND -->N<!-- /count -->` is recomputed
      (tables, rules, catalog-rows, settings; also notes, sections, columns, invariants, edge-cases);
  L5  `## Conflicts`: `CONFLICT <id>: <reason>`, `FALSE-POSITIVE <id>: <reason>` (reason of 25 characters or more),
      `OPEN <id>: ...` with an `OQ-nnn` or an open-questions anchor; every ID exists in the index; listed are every unit
      with a CONFLICT marker (as CONFLICT or OPEN), every conflict-flagged note and every note whose relation is
      `supersedes` or `superseded-by` (any entry; CONFLICT or OPEN may name the note's rule);
  L6  each file is within the hard budget (16,000 tokens, bytes / 3.5); sizes per `## ` section are reported;
  L7  every ID in the trace table exists in the index;
  L8  a cross-module reference `<module> R-<n>` (template rule 6) names a module and a numeric rule; `R-scrap`, a bare
      `R-3` and `nosuch R-1` are findings; a backticked `<word> ADR-nnnn` must name a module;
  L9  every setting key referenced by the module's units is backticked in the body (or in `Reads`);
  L10 every rule of the module that another unit supersedes (index `superseded_by`) or whose text says it is
      superseded has an entry under `## Conflicts`.
"""

import argparse
import json
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import nfdocs  # noqa: E402
import build_index  # noqa: E402

SECTIONS = ["Purpose", "Entities and tables", "Commands and queries", "Rules", "Invariants", "Edge cases", "Settings",
            "UI annotations", "Conflicts", "Proposed (not law)", "Trace"]
PER_FILE_SECTIONS = ("Purpose", "Trace")
PROPOSED_HEADING = "Proposed (not law)"
FRONT_FIELDS = ["Module", "Chunk", "Source ADRs", "Build step(s)", "Generated from index", "Compiled by"]
MIN_REASON = 25
MIN_COVERAGE = 0.25

UNIT_ID_RE = re.compile(r"ADR-\d{4}\.(?:L\d+\.)?(?:R\d+[a-z]?|D\d+|W\d*|[A-Z]\d*)(?:\.N\d+)?")
COUNT_RE = re.compile(r"<!--\s*count:([\w-]+)\s*-->\s*(\d+)\s*<!--\s*/count\s*-->")
NUMBER_WORDS = ("one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen "
                "seventeen eighteen nineteen twenty thirty forty fifty sixty seventy eighty ninety hundred").split()
NUM = r"(?:\d[\d,]*|" + "|".join(NUMBER_WORDS) + r")"
NOUNS = r"(?:tables?|rules?|columns?|settings?|commands?|queries|query|notes?|invariants?|edge cases?|modules?|" \
        r"catalog rows?|events?|chunks?)"
COUNT_BEFORE_RE = re.compile(r"(?<![\w.\-/])(" + NUM + r")\s+(?:[^\s|:;.]+\s+){0,2}?" + NOUNS + r"\b", re.I)
COUNT_AFTER_RE = re.compile(r"\b" + NOUNS + r"(?:\s+\w+)?\s*[:=]\s*(" + NUM + r")\b", re.I)
CITATION_WORDS = {"rule", "rules", "step", "steps", "phase", "layer", "layers", "section", "sections", "class", "level",
                  "floor", "round", "pass", "finding", "item", "items", "note", "notes", "chunk", "part", "version",
                  "wave", "principle", "spec", "stage", "page", "line", "lines", "s"}
THRESHOLD_RE = re.compile(r"(?:at most|at least|up to|more than|fewer than|less than|over|under|maximum|minimum|max|"
                          r"min|exactly|only)\s*$", re.I)
XREF_R_RE = re.compile(r"(?:(?<![\w-])([A-Za-z_][\w]*)\s+)?(?<![\w-])R-([\w-]*)")
XREF_ADR_RE = re.compile(r"`([a-z][a-z0-9_]*)`?\s+`?ADR-\d{4}")
WHERE_R_RE = re.compile(r"^R(\d+)([a-z]?)(?:\s*[-–]\s*R?(\d+)([a-z]?))?$")
RULE_DEF_RE = re.compile(r"^\s*(?:[-*]\s+)?\**R(\d+[a-z]?)\**\.\s")
ENTRY_RE = re.compile(r"\b(CONFLICT|FALSE-POSITIVE|OPEN)\s+`?(" + UNIT_ID_RE.pattern + r")`?\s*[:\-–—]?\s*(.*)$")


def unit_ids_in(text):
    """IDs written as `ADR-0070.R12` and as `ADR-0070 rule 12` (S3 review S4)."""
    ids = set(UNIT_ID_RE.findall(text))
    ids.update(nfdocs.find_refs(text)[1])
    return ids


class Spec:
    def __init__(self, path):
        self.path = path
        self.text = nfdocs.read(path)
        self.lines = self.text.split("\n")
        self.sections = []   # (heading, start index, end index)
        heads = [(i, l[3:].strip()) for i, l in enumerate(self.lines) if l.startswith("## ")]
        for k, (i, h) in enumerate(heads):
            self.sections.append((h, i, heads[k + 1][0] if k + 1 < len(heads) else len(self.lines)))
        self.first_heading = heads[0][0] if heads else len(self.lines)
        self.headings = {re.sub(r"[`#]", "", l).strip().lower() for l in self.lines if re.match(r"^#{2,3} ", l)}
        self.defined = {}    # R-number -> (section, line index); not on Reads lines
        for i, l in enumerate(self.lines):
            m = RULE_DEF_RE.match(l)
            sec = self.section_of(i)
            if m and sec in ("Rules", PROPOSED_HEADING) and not l.lstrip().lower().startswith("reads"):
                self.defined.setdefault(m.group(1), (sec, i, "[proposed]" in l))

    def section_of(self, i):
        for h, a, b in self.sections:
            if a <= i < b:
                return h
        return None

    def section_lines(self, name):
        for h, a, b in self.sections:
            if h == name:
                return [(i, self.lines[i]) for i in range(a + 1, b)]
        return None

    def body_lines(self):
        """Lines after the front matter and outside the Trace section."""
        return [(i, l) for i, l in enumerate(self.lines)
                if i >= self.first_heading and self.section_of(i) != "Trace"]

    def front(self):
        text = "\n".join(self.lines[:self.first_heading])
        out = {}
        for k, name in enumerate(FRONT_FIELDS):
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
            ids = sorted(unit_ids_in(cells[0].replace("`", ""))) or [cells[0].strip("` ")]
            for uid in ids:
                rows.append((i, uid, cells[1] if len(cells) > 1 else ""))
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


def index_commit(index_path):
    try:
        out = subprocess.run(["git", "log", "-1", "--format=%H", "--", os.path.abspath(index_path)],
                             cwd=os.path.dirname(os.path.abspath(index_path)), capture_output=True, text=True,
                             timeout=20)
    except (OSError, subprocess.SubprocessError):
        return None
    return out.stdout.strip() or None


def lint(paths, module, index_path, docs, index_sha=None):
    findings, warnings, info = [], [], {"files": {}}

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

    # L0: front matter and sections
    sha = index_sha or index_commit(index_path)
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
                  f"Generated from index '{given}' is not the index commit {sha[:12]}")
        names = [h for h, _a, _b in s.sections]
        for i, (h, a, _b) in enumerate(s.sections):
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
    traced = {}
    for s in specs:
        tr = s.trace()
        if tr is None:
            continue
        for i, uid, where in tr:
            traced.setdefault(uid, (s.path, i + 1))
            if uid not in by_id:
                f("L7", s.path, i + 1, f"trace ID {uid} is not in the rule index")
                continue
            kind = by_id[uid]["kind"]
            parts = where_parts(where)
            if not parts:
                f("L1", s.path, i + 1, f"trace row {uid} has an empty 'Where'")
                continue
            for p in parts:
                na = re.match(r"(?i)^not applicable\s*:?\s*(.*)$", p)
                rs = expand_where_r(p)
                if na:
                    if kind == "rule":
                        f("L1", s.path, i + 1, f"trace row {uid}: 'not applicable' is refused for a rule")
                    elif not na.group(1).strip():
                        f("L1", s.path, i + 1, f"trace row {uid}: 'not applicable' needs a reason")
                elif p.lower().startswith("reads"):
                    f("L1", s.path, i + 1, f"trace row {uid}: a 'Reads' list does not state a rule")
                elif rs is not None:
                    for n in rs:
                        if n not in defined:   # `R50` is defined when the spec has `R50a.`, `R50b.` ...
                            sub = sorted(k for k in defined if re.fullmatch(re.escape(n) + r"[a-z]", k))
                            if sub:
                                n = sub[0]
                        if n not in defined:
                            f("L1", s.path, i + 1, f"trace row {uid}: R{n} is not defined in the spec")
                        elif by_id[uid]["status"] == "proposed" and not (
                                defined[n][0] == PROPOSED_HEADING or defined[n][2]):
                            f("L3", s.path, i + 1, f"trace row {uid} (proposed) points to R{n}, stated as law")
                elif re.sub(r"#", "", p).strip().lower() not in headings:
                    warnings.append(f"W1 {s.path}:{i + 1}: trace row {uid}: 'Where' part '{p}' is not an R-number, "
                                    f"a heading or 'not applicable: <reason>'")
    for uid in sorted(unit_ids - set(traced), key=nfdocs.rule_sort_key):
        f("L1", specs[0].path, 0, f"{uid} ({by_id[uid]['kind']}) is missing from the trace table")
    n_rules = sum(1 for r in units if r["kind"] == "rule")
    if n_rules and len(defined) < MIN_COVERAGE * n_rules:
        f("L1", specs[0].path, 0, f"the spec defines {len(defined)} R-numbers for {n_rules} source rules of the module "
                                  f"(under {int(MIN_COVERAGE * 100)}%)")

    # L2 and L9
    spans = []
    for s in specs:
        spans += nfdocs.code_spans("\n".join(l for _i, l in s.body_lines()))
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
    entries = {"CONFLICT": set(), "FALSE-POSITIVE": set(), "OPEN": set()}
    for s in specs:
        for i, l in s.section_lines("Conflicts") or []:
            m = ENTRY_RE.search(l)
            if not m:
                continue
            word, uid, reason = m.group(1), m.group(2), m.group(3).strip()
            entries[word].add(uid)
            if uid not in by_id:
                f("L5", s.path, i + 1, f"{word} {uid}: not in the rule index")
            if word in ("CONFLICT", "FALSE-POSITIVE") and len(reason) < MIN_REASON:
                f("L5", s.path, i + 1, f"{word} {uid}: the reason needs {MIN_REASON} characters or more")
            if word == "OPEN" and not re.search(r"\bOQ-\d+\b|open-questions(?:\.md)?#", reason):
                f("L5", s.path, i + 1, f"OPEN {uid}: name its OQ-nnn or open-questions anchor")
    any_entry = entries["CONFLICT"] | entries["FALSE-POSITIVE"] | entries["OPEN"]
    decided = entries["CONFLICT"] | entries["OPEN"]
    for r in units:
        if r["conflict_markers"] and r["id"] not in decided:
            f("L5", specs[0].path, 0, f"{r['id']} carries a CONFLICT marker; list 'CONFLICT {r['id']}: <resolution>'")
        if r["kind"] == "note" and (r["conflict_flag"] or r["relation"] in ("supersedes", "superseded-by")) and not (
                r["id"] in any_entry or r["parent"] in decided):
            why = f"conflict flag {';'.join(r['conflict_phrases'])}" if r["conflict_flag"] else f"relation {r['relation']}"
            f("L5", specs[0].path, 0, f"{r['id']} ({why}) is not listed under '## Conflicts'")
        if r["kind"] == "rule" and (r["superseded_by"] or r["relation"] == "superseded-by") and r["id"] not in any_entry:
            by = ", ".join(r["superseded_by"]) or "its own text"
            f("L10", specs[0].path, 0, f"{r['id']} is superseded ({by}); list it under '## Conflicts'")

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
                settings=len(scope["settings"]), defined_r=len(defined), warnings=warnings)
    findings.sort(key=lambda x: (x["check"], x["file"], x["line"], x["message"]))
    return findings, info


def count_findings(line):
    """-> [(kind, n)] for count markers and [(None, text)] for typed counts in one line."""
    out = [(m.group(1), int(m.group(2))) for m in COUNT_RE.finditer(line)]
    text = COUNT_RE.sub(" ", line)
    text = re.sub(r"ADR-\d{4}(?:\.[\w.]+)?|\b(?:INV|EC|DS|OQ)-\d+|\bR-?\d+[a-z]?\b", " ", text)
    for m in COUNT_BEFORE_RE.finditer(text):
        before = text[:m.start()]
        prev = re.findall(r"[\w-]+", before[-40:])
        if prev and prev[-1].lower() in CITATION_WORDS:
            continue
        if THRESHOLD_RE.search(before):
            continue
        out.append((None, m.group(0).strip()))
    for m in COUNT_AFTER_RE.finditer(text):
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
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
