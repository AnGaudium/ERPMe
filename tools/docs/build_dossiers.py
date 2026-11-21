#!/usr/bin/env python3
"""Tool 3 (S3): write one Markdown dossier per module, plus cross.md and MODULES.csv.

Usage: build_dossiers.py --out DIR [--docs DIR] [--quiet]

A dossier holds, for one module: a header with counts and bytes; every rule, note and Decision text unit of the module
in the rule index, verbatim, with ID and source lines, marked `primary` (its ADR's primary module is this module,
tools/docs/adr-primary-module.csv) or `shared` (it names a table this module owns); the `.E` (edge cases) and `.U`
(documents updated) sections of the module's primary ADRs; the DDL of the tables the module owns; the catalog rows its
units reference (CSV lines); the full rows of every invariant and edge case referenced by its units or by those
sections, or whose area is the module; and the IDs of `cross` units that name it. A unit of more than
nfdocs.CROSS_LIMIT other modules is in its primary module and in cross.md. `process` is a non-code module.
Tokens are estimated as bytes / 3.5. Deterministic; no timestamps.
"""

import argparse
import csv
import io
import math
import os
import re
import sys
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import nfdocs  # noqa: E402
import build_index  # noqa: E402

MODULE_FIELDS = ["module", "rules", "primary_rules", "notes", "sections", "tables", "catalog_rows", "bytes",
                 "est_tokens", "conflict_flagged_notes", "supersedes_notes", "status_mix", "chunks_needed",
                 "spec_chunks_est"]
SPEC_RATIO = 0.55          # compiled spec / dossier (template "Size budget"; pilot quality 56%)
SPEC_SOFT_TOKENS = 12000   # compiled-spec soft target per chunk (template)
SECTION_SUFFIX = re.compile(r"\.(E|U)\d*(\.N\d+)?$")


def adr_sections(info, module):
    """The .E and .U sections (and their notes) of the ADRs whose primary module is `module`."""
    prim = {a for a, m in info["primary"].items() if m == module}
    return [u for u in info["units"] if u["adr"] in prim and SECTION_SUFFIX.search(u["id"])]


def render(module, rows, info, docs):
    owners, files, cats = info["owners"], info["files"], info["cats"]
    text_of = {u["id"]: u["text"] for u in info["units"]}
    scope = nfdocs.module_scope(rows, owners, cats, module)
    units, owned = scope["units"], scope["tables"]
    sections = adr_sections(info, module) if module != "cross" else []
    refs = set(scope["catalog_rows"])
    for u in sections:
        refs.update(c for c in info["matcher"].find(u["text"])[1] if c.startswith(("invariants:", "edge-cases:")))
    cat_rows = sorted(refs)
    inv_ec = [c for c in cat_rows if c.startswith(("invariants:", "edge-cases:"))]
    other_rows = [c for c in cat_rows if c not in inv_ec]
    body = ["## Rules and notes\n"]
    for r in units:
        mods = r["modules_all"].split(";")
        prims = r["primary_module"].split(";")
        if module == "cross":
            tag = f"{r['kind']}, primary {', '.join(prims)}, modules: " + ", ".join(mods)
        elif module in prims:
            tag = f"{r['kind']}, primary" + (", shared with: " + ", ".join(m for m in mods if m != module)
                                             if len(mods) > 1 else "")
        else:
            tag = f"{r['kind']}, shared, primary {', '.join(prims)}"
        if r["superseded_by"]:
            tag += ", SUPERSEDED by " + r["superseded_by"].replace(";", ", ")
        elif r["relation"] == "superseded-by" and r["kind"] == "rule":
            tag += ", SUPERSEDED (its text says so)"
        if r["status"] != "accepted":
            tag += f", {r['status']}"
        if r["relation"] and r["kind"] == "note":
            tag += f", {r['relation']}"
        if r["conflict_flag"]:
            tag += ", conflict flag: " + r["conflict_phrases"]
        if r["conflict_markers"]:
            tag += ", CONFLICT marker"
        if r["kind"] == "note" and r["parent"]:
            tag += f", amends {r['parent']}"
        body.append(f"### {r['id']} ({tag})\n")
        body.append(f"Source: {r['source_file']}:{r['line_start']}-{r['line_end']}\n")
        body.append(text_of[r["id"]] + "\n")
    if sections:
        body.append("## Edge-case and documents-updated sections of the primary ADRs\n")
        for u in sections:
            body.append(f"### {u['id']} ({u['kind']}, {u['section']})\n")
            body.append(f"Source: {u['source_file']}:{u['line_start']}-{u['line_end']}\n")
            body.append(u["text"] + "\n")
    if owned:
        body.append("## DDL of owned tables\n")
        for t in owned:
            path, line = files[t]
            body.append(f"### {t}\n\nSource: {path}:{line}\n\n```sql\n{nfdocs.table_ddl(docs, path, line)}\n```\n")
    for title, picked in (("Catalog rows referenced", other_rows), ("Invariants and edge cases", inv_ec)):
        if picked:
            body.append(f"## {title}\n")
            for cat, keys in group_rows(picked).items():
                body.append(f"### {cat}.csv\n\n```csv\n{header_line(docs, cat)}\n" +
                            "\n".join(cats[cat][k][0] for k in keys) + "\n```\n")
    cross_ids = [r["id"] for r in rows if "cross" in r["modules"].split(";") and module in r["modules_all"].split(";")
                 and module not in r["modules"].split(";")] if module != "cross" else []
    if cross_ids:
        body.append("## Cross units that name this module (full text in cross.md)\n")
        body.append(", ".join(cross_ids) + "\n")
    body_text = "\n".join(body)
    kinds = Counter(r["kind"] for r in units)
    status = Counter(r["status"] for r in units)
    stats = {
        "module": module, "rules": kinds["rule"],
        "primary_rules": sum(1 for r in units if r["kind"] == "rule" and module in r["primary_module"].split(";")),
        "notes": kinds["note"], "sections": kinds["section"], "tables": len(owned), "catalog_rows": len(cat_rows),
        "conflict_flagged_notes": sum(1 for r in units if r["kind"] == "note" and r["conflict_flag"]),
        "supersedes_notes": sum(1 for r in units if r["kind"] == "note" and r["relation"] == "supersedes"),
        "status_mix": ";".join(f"{k}:{v}" for k, v in sorted(status.items())),
    }
    prim_adrs = sorted(a for a, m in info["primary"].items() if m == module)
    sec_adrs = sorted(a for a, ms in info["secondary"].items() if module in ms)
    flag = (" Non-code module: process law (how the project works), no code is generated from it."
            if module in nfdocs.NON_CODE_MODULES else "")
    head = (f"# Dossier: `{module}`\n\nGenerated by tools/docs/build_dossiers.py from the rule index; do not edit."
            f"{flag}\n\nPrimary ADRs: {', '.join(prim_adrs) or 'none'}. Secondary in: {', '.join(sec_adrs) or 'none'}.\n\n"
            f"Rules {stats['rules']} (primary {stats['primary_rules']}), notes {stats['notes']}, Decision text units "
            f"{stats['sections']}, owned tables {stats['tables']}, catalog rows {stats['catalog_rows']}, "
            f"conflict-flagged notes {stats['conflict_flagged_notes']}, supersedes notes {stats['supersedes_notes']}, "
            f"status {stats['status_mix'] or 'none'}. Body {len(body_text.encode('utf-8'))} bytes, about "
            f"{round(len(body_text.encode('utf-8')) / nfdocs.TOKEN_BYTES)} tokens (bytes / 3.5).\n\n")
    content = head + body_text
    size = len(content.encode("utf-8"))
    stats["bytes"] = size
    stats["est_tokens"] = round(size / nfdocs.TOKEN_BYTES)
    stats["chunks_needed"] = max(1, math.ceil(stats["est_tokens"] / nfdocs.CHUNK_TOKENS))
    # planning figure of the compiled spec: 55% of the dossier, cut at the 12,000-token soft target (template)
    stats["spec_chunks_est"] = max(1, math.ceil(SPEC_RATIO * stats["est_tokens"] / SPEC_SOFT_TOKENS))
    return content, stats


def group_rows(rows):
    out = defaultdict(list)
    for c in sorted(rows):
        cat, key = c.split(":", 1)
        out[cat].append(key)
    return dict(sorted(out.items()))


_HEADERS = {}


def header_line(docs, cat):
    if cat not in _HEADERS:
        with open(os.path.join(docs, "catalogs", cat + ".csv"), encoding="utf-8", newline="") as fh:
            _HEADERS[cat] = nfdocs.csv_line(next(csv.reader(fh)))
    return _HEADERS[cat]


def build_all(docs, out_dir):
    rows, info = build_index.build(docs)
    names = sorted(set(info["modules"]) | set(info["primary"].values()) |
                   {m for r in rows for m in r["modules"].split(";")})
    files, stats = {}, []
    for m in names:
        content, st = render(m, rows, info, docs)
        files[f"{m}.md"] = content
        stats.append(st)
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=MODULE_FIELDS, lineterminator="\n")
    w.writeheader()
    for st in stats:
        w.writerow({k: st[k] for k in MODULE_FIELDS})
    files["MODULES.csv"] = buf.getvalue()
    os.makedirs(out_dir, exist_ok=True)
    for name in os.listdir(out_dir):   # drop dossiers of modules that no longer exist (e.g. unassigned.md)
        if name.endswith(".md") and name not in files:
            os.remove(os.path.join(out_dir, name))
    for name, content in sorted(files.items()):
        with open(os.path.join(out_dir, name), "w", encoding="utf-8", newline="") as fh:
            fh.write(content)
    return files, stats


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", required=True)
    ap.add_argument("--docs", default=nfdocs.DEFAULT_DOCS)
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args(argv)
    files, stats = build_all(args.docs, args.out)
    if not stats:
        print("FAIL: no modules", file=sys.stderr)
        return 1
    if not args.quiet:
        print(f"wrote {len(files)} files to {args.out}")
        print(files["MODULES.csv"], end="")
    return 0


if __name__ == "__main__":
    sys.exit(main())
