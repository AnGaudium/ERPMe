#!/usr/bin/env python3
"""Tool 2 (S3): build the rule index docs/design/generated/rule-index.csv. Deterministic, standard library only.

Usage: build_index.py [--docs DIR] [--out CSV] [--check] [--quiet]

One row per rule, per note, and per Decision text unit (`.D0`, `.D1`..., `.W`; normative text outside the numbered
rules, e.g. the whole Decision of ADR-0001). Columns: see INDEX_FIELDS and tools/docs/README.md. --check exits 1 when
the committed CSV differs from what would be written.
"""

import argparse
import csv
import io
import os
import re
import sys
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import nfdocs  # noqa: E402

INDEX_FIELDS = ["id", "kind", "adr", "status", "primary_module", "modules", "modules_all", "tables", "catalog_rows", "xrefs_rules",
                "build_step", "relation", "conflict_flag", "conflict_phrases", "conflict_markers", "parent",
                "source_file", "line_start", "line_end"]


def is_indexed(u):
    if u["kind"] in ("rule", "note"):
        return True
    return bool(re.search(r"\.(D\d+|W\d*)$", u["id"]))


def build(docs):
    """-> (rows, info). rows: list of dicts (INDEX_FIELDS); info: module model and report data."""
    units, parsed, dangling = nfdocs.extract(docs)
    modules, owners, declared, files = nfdocs.module_model(docs)
    cats, skipped = nfdocs.load_catalogs(docs)
    matcher = nfdocs.Matcher(owners, cats)
    by_id = {u["id"]: u for u in units}
    adr_step = {}
    for a in parsed:
        head = "\n".join(u["text"] for u in a["units"] if u["id"] in (f"{a['adr']}.H", f"{a['adr']}.D0"))
        step = nfdocs.first_step(head)
        if not step:  # else the step the ADR names most often (ties: the earlier step)
            counts = Counter(m for u in a["units"] for m in nfdocs.STEP_RE.findall(u["text"]) if m in nfdocs.STEP_VOCAB)
            if counts:
                step = sorted(counts.items(), key=lambda x: (-x[1], nfdocs.STEP_ORDER.index(x[0])))[0][0]
        adr_step[a["adr"]] = step

    primary, secondary = nfdocs.load_primary(modules, adrs=[a["adr"] for a in parsed])
    mods_of = {}

    def unit_modules(u):
        """-> (modules column list, full list). Every unit is in its ADR's primary module, plus the owners of its
        tables; a note also in its owner's modules. More than CROSS_LIMIT other modules -> primary plus `cross`."""
        if u["id"] in mods_of:
            return mods_of[u["id"]]
        prim = primary[u["adr"]]
        full = {prim} | {owners[t] for t in u["_tables"] if owners.get(t)}
        if u["kind"] == "note" and u["parent"] in by_id:
            full |= set(unit_modules(by_id[u["parent"]])[1])
        others = full - {prim}
        col = [prim, "cross"] if len(others) > nfdocs.CROSS_LIMIT else sorted(full)
        mods_of[u["id"]] = (sorted(col), sorted(full))
        return mods_of[u["id"]]

    for u in units:
        u["_tables"], u["_rows"] = matcher.find(u["text"])
    rows = []
    for u in units:
        if not is_indexed(u):
            continue
        mods, full = unit_modules(u)
        step = nfdocs.first_step(u["text"])
        if not step and u["kind"] == "note" and u["parent"] in by_id:
            step = nfdocs.first_step(by_id[u["parent"]]["text"])
        rows.append({
            "id": u["id"], "kind": u["kind"], "adr": u["adr"], "status": u["adr_status"],
            "primary_module": primary[u["adr"]], "modules": ";".join(mods), "modules_all": ";".join(full),
            "tables": ";".join(u["_tables"]), "catalog_rows": ";".join(u["_rows"]),
            "xrefs_rules": ";".join(u["xrefs_rules"]), "build_step": step or adr_step.get(u["adr"], ""),
            "relation": u["relation"] or "", "conflict_flag": "1" if u["conflict"] else "",
            "conflict_phrases": ";".join(u["conflict_phrases"]), "conflict_markers": str(u["conflict_markers"] or ""),
            "parent": u["parent"] or "", "source_file": u["source_file"], "line_start": str(u["line_start"]),
            "line_end": str(u["line_end"])})
    rows.sort(key=lambda r: (r["adr"], int(r["line_start"]), nfdocs.rule_sort_key(r["id"])))
    info = {"units": units, "parsed": parsed, "dangling": dangling, "modules": modules, "owners": owners,
            "declared": declared, "files": files, "cats": cats, "skipped": skipped, "primary": primary,
            "secondary": secondary, "matcher": matcher}
    return rows, info


def to_csv(rows):
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=INDEX_FIELDS, lineterminator="\n")
    w.writeheader()
    for r in rows:
        w.writerow(r)
    return buf.getvalue()


def read_index(path):
    with open(path, encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))
    for r in rows:
        for k in ("modules", "modules_all", "tables", "catalog_rows", "xrefs_rules", "conflict_phrases"):
            r[k] = [x for x in r[k].split(";") if x]
    return rows


def ambiguous_names(owners, cats, modules):
    out = []
    keys = defaultdict(list)
    for cat, entries in cats.items():
        for k in entries:
            keys[k].append(cat)
    for t in sorted(owners):
        why = []
        if "_" not in t:
            why.append("one word")
        if t in keys:
            why.append("also a key of " + ",".join(sorted(keys[t])))
        if t in modules:
            why.append("also a module name")
        if len(t) < 4:
            why.append("shorter than 4, not matched")
        if why:
            out.append(f"table {t}: " + "; ".join(why))
    for k, cs in sorted(keys.items()):
        if len(cs) > 1 and k not in owners:
            out.append(f"key {k}: in " + ",".join(sorted(cs)))
    return out


def report(rows, info):
    lines = [f"rows: {len(rows)} (" + ", ".join(f"{k} {v}" for k, v in sorted(Counter(r['kind'] for r in rows).items()))
             + ")"]
    per = Counter()
    for r in rows:
        for m in r["modules"].split(";"):
            per[m] += 1
    lines.append("rows per module: " + ", ".join(f"{m} {n}" for m, n in sorted(per.items())))
    un = [r["id"] for r in rows if r["modules"] == "unassigned"]
    lines.append(f"unassigned units: {len(un)}" + (": " + ", ".join(un) if un else ""))
    lines.append(f"units in cross (besides their primary module): {sum(1 for r in rows if 'cross' in r['modules'].split(';'))}")
    lines.append(f"rules without a build step: {sum(1 for r in rows if r['kind'] == 'rule' and not r['build_step'])}")
    unowned = sorted(t for t, o in info["owners"].items() if not o)
    lines.append(f"tables: {len(info['owners'])}; without owner: {len(unowned)}" + (": " + ", ".join(unowned) if unowned else ""))
    lines.append("catalogs skipped (first column not a unique key): " + (", ".join(info["skipped"]) or "none"))
    amb = ambiguous_names(info["owners"], info["cats"], info["modules"])
    lines.append(f"ambiguous names: {len(amb)}" + "".join(f"\n  {a}" for a in amb))
    return "\n".join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--docs", default=nfdocs.DEFAULT_DOCS)
    ap.add_argument("--out")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args(argv)
    out = args.out or os.path.join(args.docs, "design", "generated", "rule-index.csv")
    rows, info = build(args.docs)
    if not rows:
        print("FAIL: no rows", file=sys.stderr)
        return 1
    ids = [r["id"] for r in rows]
    if len(ids) != len(set(ids)):
        print("FAIL: duplicate IDs", file=sys.stderr)
        return 1
    content = to_csv(rows)
    if args.check:
        current = nfdocs.read(out) if os.path.exists(out) else None
        if current != content:
            print(f"FAIL: {out} is stale (run build_index.py)", file=sys.stderr)
            return 1
        print(f"ok: {out} current, {len(rows)} rows")
        return 0
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    with open(out, "w", encoding="utf-8", newline="") as fh:
        fh.write(content)
    if not args.quiet:
        print(f"wrote {out}")
        print(report(rows, info))
    return 0


if __name__ == "__main__":
    sys.exit(main())
