#!/usr/bin/env python3
"""Tool 4 (S3): lint a compiled spec (docs/design/compiled-spec-template.md) against the rule index.

Usage: doc_lint.py SPEC.md [SPEC-2.md ...] --module M [--index CSV] [--docs DIR] [--json]

Several files are the chunks of one module: L1, L2 and L5 are checked over all of them together, the others per file.
First output line: `LINT PASS findings=0` or `LINT FAIL findings=N`; then one finding per line
(`L<n> <file>:<line>: <message>`), or with --json one line of JSON. Exit 0 on PASS, 1 on FAIL, 2 on bad input.

Checks:
  L1  every rule, note and Decision text ID of the module in the index appears in the `## Trace` table;
  L2  every table the module owns and every catalog row of the module is mentioned in backticks in the body;
  L3  a line citing a rule of a proposed ADR is under `## Proposed (not law)` or carries `[proposed]`; a line citing
      only accepted rules carries no `[proposed]` and is not under that heading;
  L4  no bare number before a counted noun; `<!-- count:KIND -->N<!-- /count -->` is recomputed from the index
      (kinds: tables, columns, rules, notes, sections, settings, invariants, edge-cases, catalog-rows);
  L5  every unit of the module with a literal CONFLICT marker is listed under `## Conflicts` as
      `CONFLICT <id>: <resolution>`; every conflict-flagged note as `CONFLICT <note or rule id>: ...` or
      `FALSE-POSITIVE <note id>`;
  L6  each file is within the hard budget (16,000 tokens, bytes / 3.5); sizes per `## ` section are reported;
  L7  every ID in the trace table exists in the index.
"""

import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import nfdocs  # noqa: E402
import build_index  # noqa: E402

ID_RE = re.compile(r"ADR-\d{4}(?:\.(?:L\d+\.)?(?:R\d+[a-z]?|D\d+|W\d*|[A-Z]\d*)(?:\.N\d+)?)?")
UNIT_ID_RE = re.compile(r"ADR-\d{4}\.(?:L\d+\.)?(?:R\d+[a-z]?|D\d+|W\d*|[A-Z]\d*)(?:\.N\d+)?")
COUNT_RE = re.compile(r"<!--\s*count:([\w-]+)\s*-->\s*(\d+)\s*<!--\s*/count\s*-->")
NOUNS = r"(?:tables?|rules?|columns?|settings?|commands?|queries|query|notes?|invariants?|edge cases?|modules?|" \
        r"catalog rows?|events?|chunks?)"
BARE_RE = re.compile(r"(?<![\w.,-])(\d[\d,]*)\s+(?:[a-z-]+\s+)?" + NOUNS + r"\b", re.I)
PROPOSED_HEADING = "Proposed (not law)"


class Spec:
    def __init__(self, path):
        self.path = path
        self.text = nfdocs.read(path)
        self.lines = self.text.split("\n")
        self.sections = []   # (heading, start index, end index)
        heads = [(i, l[3:].strip()) for i, l in enumerate(self.lines) if l.startswith("## ")]
        for k, (i, h) in enumerate(heads):
            self.sections.append((h, i, heads[k + 1][0] if k + 1 < len(heads) else len(self.lines)))

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
        """Lines outside the Trace section, with code fences kept (L2 looks for backticks)."""
        return [(i, l) for i, l in enumerate(self.lines) if self.section_of(i) != "Trace"]

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
            for uid in UNIT_ID_RE.findall(cells[0].replace("`", "")) or [cells[0].strip("` ")]:
                rows.append((i, uid, cells[1] if len(cells) > 1 else ""))
        return rows


def lint(paths, module, index_path, docs):
    findings, info = [], {"files": {}}

    def f(check, path, line, msg):
        findings.append({"check": check, "file": path, "line": line, "message": msg})

    rows = build_index.read_index(index_path)
    by_id = {r["id"]: r for r in rows}
    _modules, owners, _declared, _files = nfdocs.module_model(docs)
    cats, _skipped = nfdocs.load_catalogs(docs)
    units, tables, cat_rows = nfdocs.module_scope(rows, owners, cats, module)
    if not units and not tables:
        raise SystemExit(f"doc_lint: module '{module}' has no units and no tables in the index")
    specs = [Spec(p) for p in paths]
    unit_ids = {r["id"] for r in units}

    # L7 and L1
    traced = {}
    for s in specs:
        tr = s.trace()
        if tr is None:
            f("L1", s.path, 0, "no '## Trace' section")
            continue
        for i, uid, where in tr:
            traced.setdefault(uid, (s.path, i + 1))
            if uid not in by_id:
                f("L7", s.path, i + 1, f"trace ID {uid} is not in the rule index")
            if not where.strip():
                f("L1", s.path, i + 1, f"trace row {uid} has an empty 'Where'")
    for uid in sorted(unit_ids - set(traced), key=nfdocs.rule_sort_key):
        f("L1", specs[0].path, 0, f"{uid} ({by_id[uid]['kind']}) is missing from the trace table")

    # L2
    spans = []
    for s in specs:
        spans += nfdocs.code_spans("\n".join(l for _i, l in s.body_lines()))
    joined = "\n".join(spans)
    for t in tables:
        if not nfdocs.key_regex(t).search(joined):
            f("L2", specs[0].path, 0, f"owned table `{t}` is not mentioned in backticks")
    for c in cat_rows:
        _cat, key = c.split(":", 1)
        if not (key in joined and re.search(r"(?<![\w.])" + re.escape(key) + r"(?![\w.])", joined)):
            f("L2", specs[0].path, 0, f"catalog row {c} is not mentioned in backticks (`{key}`)")

    # L3, L4 per file
    columns = None
    for s in specs:
        for i, line in s.body_lines():
            sec = s.section_of(i)
            if sec in ("Conflicts",):
                continue
            cited = [u for u in UNIT_ID_RE.findall(line) if u in by_id]
            prop = [u for u in cited if by_id[u]["status"] == "proposed"]
            marked = "[proposed]" in line
            in_prop = sec == PROPOSED_HEADING
            if prop and not (marked or in_prop):
                f("L3", s.path, i + 1, f"cites proposed {', '.join(prop)} outside '## {PROPOSED_HEADING}' "
                                        f"without [proposed]")
            if cited and not prop and (marked or in_prop):
                f("L3", s.path, i + 1, "accepted rule marked as proposed: " + ", ".join(cited))
            if s.lines[i].startswith(("Module:", "Build step(s):")):
                continue
            stripped = COUNT_RE.sub(" ", re.sub(r"`[^`]*`", " ", line))
            for m in BARE_RE.finditer(stripped):
                f("L4", s.path, i + 1, f"bare count '{m.group(0)}'; write <!-- count:KIND -->N<!-- /count -->")
            for m in COUNT_RE.finditer(line):
                kind, n = m.group(1), int(m.group(2))
                if kind == "columns" and columns is None:
                    columns = nfdocs.table_columns(docs)
                want = expected_count(kind, units, tables, cat_rows, columns)
                if want is None:
                    f("L4", s.path, i + 1, f"count kind '{kind}' cannot be computed from the index")
                elif want != n:
                    f("L4", s.path, i + 1, f"count:{kind} says {n}, the index gives {want}")

    # L5
    conflicts = []
    for s in specs:
        sec = s.section_lines("Conflicts")
        if sec:
            conflicts += [(s.path, i, l) for i, l in sec]
    listed_conflict, listed_fp = set(), set()
    for path, i, l in conflicts:
        for m in re.finditer(r"CONFLICT\s+(" + UNIT_ID_RE.pattern + r")\s*:\s*(\S.*)?", l):
            listed_conflict.add(m.group(1))
            if not m.group(2):
                f("L5", path, i + 1, f"CONFLICT {m.group(1)} has no resolution")
        for m in re.finditer(r"FALSE-POSITIVE\s+(" + UNIT_ID_RE.pattern + r")", l):
            listed_fp.add(m.group(1))
    for r in units:
        if r["conflict_markers"] and r["id"] not in listed_conflict:
            f("L5", specs[0].path, 0, f"{r['id']} carries a CONFLICT marker; list 'CONFLICT {r['id']}: <resolution>'")
        if r["kind"] == "note" and r["conflict_flag"] and not (
                r["id"] in listed_conflict or r["parent"] in listed_conflict or r["id"] in listed_fp):
            f("L5", specs[0].path, 0, f"{r['id']} has the conflict flag ({';'.join(r['conflict_phrases'])}); list "
                                      f"'CONFLICT {r['id']}: ...' or 'FALSE-POSITIVE {r['id']}'")

    # L6
    for s in specs:
        size = len(s.text.encode("utf-8"))
        tokens = round(size / nfdocs.TOKEN_BYTES)
        per = {h: round(len("\n".join(s.lines[a:b]).encode("utf-8")) / nfdocs.TOKEN_BYTES) for h, a, b in s.sections}
        info["files"][s.path] = {"bytes": size, "est_tokens": tokens, "sections": per}
        if tokens > nfdocs.SPEC_HARD_TOKENS:
            f("L6", s.path, 0, f"{tokens} tokens (bytes / 3.5) over the hard limit {nfdocs.SPEC_HARD_TOKENS}; "
                               f"split into chunks at '###' topics")
    info["module"] = module
    info["module_ids"] = len(unit_ids)
    info["tables"] = len(tables)
    info["catalog_rows"] = len(cat_rows)
    findings.sort(key=lambda x: (x["check"], x["file"], x["line"], x["message"]))
    return findings, info


def expected_count(kind, units, tables, cat_rows, columns):
    k = {"rule": "rules", "note": "notes", "table": "tables", "setting": "settings", "invariant": "invariants",
         "edge-case": "edge-cases", "catalog-row": "catalog-rows", "column": "columns", "section": "sections"}.get(kind,
                                                                                                                  kind)
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
        return sum(1 for c in cat_rows if c.startswith("settings:"))
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
    ap.add_argument("--docs", default=nfdocs.DEFAULT_DOCS)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    for p in args.specs:
        if not os.path.isfile(p):
            print(f"doc_lint: no file {p}", file=sys.stderr)
            return 2
    try:
        findings, info = lint(args.specs, args.module, args.index, args.docs)
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
        for p, st in info["files"].items():
            print(f"size {p}: {st['bytes']} bytes, ~{st['est_tokens']} tokens; " +
                  ", ".join(f"{h} ~{t}" for h, t in st["sections"].items()))
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
