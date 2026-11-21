#!/usr/bin/env python3
"""Tool 1 (S3): extract the ADRs into rule units as JSON Lines. Deterministic, standard library only.

Usage: extract_rules.py --out UNITS.jsonl [--markers-out MARKERS.jsonl] [--docs DIR] [--strict] [--quiet]

Each line of --out is one unit: a rule (`ADR-0026.R6`), a note (`ADR-0026.R6.N2`) or a section (`ADR-0026.C`,
`.O`, `.K`, `.E`, `.V`, `.U`, `.A`, `.W`, header `.H`, Decision text `.D0`, `.D1`...). Fields: see nfdocs.UNIT_FIELDS
and tools/docs/README.md. --markers-out lists literal CONFLICT markers in docs/adr, docs/spec and docs/design.

Exit 1 when an ADR has no status, a unit ID repeats, or a line of a Decision section is not covered by a unit; with
--strict also on a dangling cross-reference. The summary goes to stdout.
"""

import argparse
import json
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import nfdocs  # noqa: E402


def write_jsonl(path, records):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        for r in records:
            fh.write(json.dumps(r, ensure_ascii=False, sort_keys=False) + "\n")


def summary(units, parsed, dangling, markers):
    kinds = Counter(u["kind"] for u in units)
    notes = [u for u in units if u["kind"] == "note"]
    out = [f"ADRs: {len(parsed)}; status: " + ", ".join(f"{k} {v}" for k, v in
                                                       sorted(Counter(a['status'] for a in parsed).items())),
           f"units: {len(units)} (rules {kinds['rule']}, notes {kinds['note']}, sections {kinds['section']})",
           "notes by relation: " + ", ".join(f"{k} {v}" for k, v in sorted(Counter(u['relation'] for u in notes).items())),
           f"notes with the conflict flag: {sum(u['conflict'] for u in notes)}; by phrase: " +
           ", ".join(f"'{p}' {n}" for p, n in sorted(Counter(p for u in notes for p in u['conflict_phrases']).items(),
                                                     key=lambda x: (-x[1], x[0]))),
           "rules saying 'superseded by': " + (", ".join(u["id"] for u in units
                                                       if u["kind"] == "rule" and u["relation"]) or "none")]
    cov = Counter()
    unc = []
    for a in parsed:
        for k in ("decision_lines", "rule_lines", "note_lines", "section_lines", "structural_lines"):
            cov[k] += a["coverage"][k]
        unc += a["coverage"]["uncovered"]
    out.append(f"Decision lines: {cov['decision_lines']} (rules {cov['rule_lines']}, notes {cov['note_lines']}, "
               f"section text {cov['section_lines']}, headings and groups {cov['structural_lines']}); "
               f"uncovered {len(unc)}" + (": " + ", ".join(unc[:20]) if unc else ""))
    out.append(f"cross-references to rules: {sum(len(u['xrefs_rules']) for u in units)}; dangling {len(dangling)}" +
               ("".join(f"\n  {s} -> {t}" for s, t in dangling)))
    out.append(f"literal CONFLICT markers: {len(markers)}" + "".join(f"\n  {f}:{n}: {t[:100]}" for f, n, t in markers))
    odd = [o for a in parsed for o in a["oddities"]]
    out.append(f"oddities: {len(odd)}" + "".join(f"\n  {o}" for o in odd))
    return "\n".join(out), unc, odd


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", required=True)
    ap.add_argument("--markers-out")
    ap.add_argument("--docs", default=nfdocs.DEFAULT_DOCS)
    ap.add_argument("--strict", action="store_true")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args(argv)
    units, parsed, dangling = nfdocs.extract(args.docs)
    markers = nfdocs.conflict_markers(args.docs)
    write_jsonl(args.out, [nfdocs.unit_record(u) for u in units])
    if args.markers_out:
        write_jsonl(args.markers_out, [{"file": f, "line": n, "text": t} for f, n, t in markers])
    text, unc, _odd = summary(units, parsed, dangling, markers)
    if not args.quiet:
        print(text)
    failed = []
    if any(a["status"] == "unknown" for a in parsed):
        failed.append("an ADR has no recognised status")
    ids = [u["id"] for u in units]
    if len(ids) != len(set(ids)):
        failed.append("duplicate unit IDs")
    if unc:
        failed.append(f"{len(unc)} uncovered Decision lines")
    if args.strict and dangling:
        failed.append(f"{len(dangling)} dangling cross-references")
    if failed:
        print("FAIL: " + "; ".join(failed), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
