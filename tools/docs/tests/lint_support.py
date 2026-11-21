"""Shared base of the doc_lint tests: a temporary index built from the real ADRs, a generated compiled spec that
satisfies every check (make_spec), and helpers to mutate it. Not a test module."""

import csv
import os
import re
import shutil
import sys
import tempfile
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import nfdocs  # noqa: E402
import build_index  # noqa: E402
import doc_lint  # noqa: E402

MODULE = "outbox"   # small module: owned tables, catalog rows, a flagged note, supersedes notes, superseded rules
SHA = "0123456789abcdef0123456789abcdef01234567"
NAME_RE = re.compile(r"`([A-Za-z_][\w.]{3,})`")


def write_index(path, rows):
    with open(path, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=build_index.INDEX_FIELDS, lineterminator="\n")
        w.writeheader()
        for r in rows:
            w.writerow(r)


def superseding(r):
    return (r["kind"] == "note" and r["relation"] in ("supersedes", "superseded-by")) or \
        (r["kind"] == "rule" and (r["superseded_by"] or r["relation"] == "superseded-by"))


def flagged_only(r):
    return r["kind"] == "note" and r["conflict_flag"] and not superseding(r)


def word_pool(texts):
    words = sorted({w for t in texts.values() for w in re.findall(r"(?<![a-z])[a-z]{6,9}(?![a-z])", t.lower())})
    return words


def own_reason(k, pool):
    """Six words of the ADRs for entry k; no two entries share a word, so no reason is a near copy of another."""
    return " ".join(pool[((k * 6 + j) * 37) % len(pool)] for j in range(6))


def make_spec(rows, owners, cats, module, texts):
    """A compiled spec that satisfies every check: front matter, the eleven sections with content, one real
    R-number statement per source rule that keeps one identifier of the rule, a Source that lists exactly the units
    traced to it (the rule, its notes, and the superseding ID of a superseded rule), every ID traced, owned tables,
    rows and referenced settings backticked; supersessions as CONFLICT naming the governing text, flagged notes as
    FALSE-POSITIVE, each entry with its own reason. Rows the module does not own are left out on purpose."""
    scope = nfdocs.module_scope(rows, owners, cats, module)
    units, tables = scope["units"], scope["tables"]
    keys = sorted({c.split(":", 1)[1] for c in scope["owned_rows"] + scope["settings"]})
    rules = [r for r in units if r["kind"] == "rule"]
    rnum = {r["id"]: f"R{i}" for i, r in enumerate(rules, start=1)}
    pool = word_pool(texts)
    avoid = set(tables) | set(keys) | {c.split(":", 1)[1] for c in scope["catalog_rows"]}

    def where(r):
        if r["id"] in rnum:
            return rnum[r["id"]]
        if r["kind"] == "note":
            return rnum.get(r["parent"], "R1")
        return "Purpose"

    sources = {n: [] for n in rnum.values()}
    for r in units:
        if where(r) in sources:
            sources[where(r)].append(r["id"])
    for r in rules:
        if r["superseded_by"]:
            sources[rnum[r["id"]]].append(r["superseded_by"][0])
    entries = []
    for k, r in enumerate(units):
        if r["conflict_markers"] not in ("", "0", 0):
            entries.append(f"CONFLICT {r['id']}: {r['id']} is resolved by the later source; {own_reason(k, pool)}")
        elif superseding(r):
            gov = r["superseded_by"][0] if r["kind"] == "rule" and r["superseded_by"] else r["id"]
            entries.append(f"CONFLICT {r['id']}: {gov} governs; {own_reason(k, pool)}")
        elif flagged_only(r):
            entries.append(f"FALSE-POSITIVE {r['id']}: {own_reason(k, pool)}")

    def statement(i, r):
        names = sorted(set(NAME_RE.findall(texts.get(r["id"], ""))) - avoid)
        naming = f", naming `{names[0]}`," if names else ""
        return (f"{rnum[r['id']]}. Statement {i} restates the law of {r['id']}{naming} in plain words. Source: "
                + ", ".join(f"`{x}`" for x in sources[rnum[r['id']]]))

    out = [f"Module: {module}    Chunk: whole    Source ADRs: ADR-0013",
           f"Build step(s): 0    Generated from index: {SHA[:9]}    Compiled by: test, 2026-11-21", "",
           f"# Compiled spec: `{module}`", "",
           "## Purpose", "", f"The module owns <!-- count:tables -->{len(tables)}<!-- /count --> tables.", "",
           "## Entities and tables", ""] + [f"- `{t}`" for t in tables] + [
           "", "## Commands and queries", "", "None (the test module registers nothing).", "",
           "## Rules", "", "### Topic", ""] + [statement(i, r) for i, r in enumerate(rules, start=1)] + [
           "", "## Invariants", "", "None (stated with the owned rows under Settings).", "",
           "## Edge cases", "", "None (stated with the owned rows under Settings).", "",
           "## Settings", ""] + [f"- `{k}`" for k in keys] + [
           "", "## UI annotations", "", "None (headless step).", "", "## Conflicts", ""] + (entries or ["None."]) + [
           "", "## Proposed (not law)", "", "None.", "", "## Trace", "", "| Source | Where |", "| --- | --- |"] + [
           f"| `{r['id']}` | {where(r)} |" for r in units] + [""]
    return "\n".join(out)


class LintBase(unittest.TestCase):
    """setUpClass builds the index once; `index_state` (git) is stubbed so that the temporary index counts as
    committed in SHA. The git checks have their own tests with a real repository."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="doclint-")
        rows, info = build_index.build(nfdocs.DEFAULT_DOCS)
        cls.raw = rows
        cls.index = os.path.join(cls.tmp, "index.csv")
        write_index(cls.index, rows)
        cls.rows = build_index.read_index(cls.index)
        cls.by = {r["id"]: r for r in cls.rows}
        cls.owners, cls.cats = info["owners"], info["cats"]
        cls.texts = {u["id"]: u["text"] for u in info["units"]}
        cls.scope = nfdocs.module_scope(cls.rows, cls.owners, cls.cats, MODULE)
        cls.units, cls.tables, cls.cat_rows = cls.scope["units"], cls.scope["tables"], cls.scope["owned_rows"]
        cls.rules = [r for r in cls.units if r["kind"] == "rule"]
        cls.spec = make_spec(cls.rows, cls.owners, cls.cats, MODULE, cls.texts)
        cls.patch = None
        if hasattr(doc_lint, "index_state"):
            cls.patch = mock.patch.object(doc_lint, "index_state", lambda i, d, s=None: (s or SHA, []))
            cls.patch.start()

    @classmethod
    def tearDownClass(cls):
        if cls.patch:
            cls.patch.stop()
        shutil.rmtree(cls.tmp)

    def write(self, text, name="spec.md"):
        path = os.path.join(self.tmp, name)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)
        return path

    def run_lint(self, text, index=None, name="spec.md", module=MODULE, with_info=False, sha=SHA, **kw):
        path = self.write(text, name)
        findings, info = doc_lint.lint([path], module, index or self.index, nfdocs.DEFAULT_DOCS, sha, **kw)
        return (findings, info) if with_info else findings

    def run_cli(self, args):
        import contextlib
        import io
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            rc = doc_lint.main(args)
        return rc, out.getvalue(), err.getvalue()

    def edited_index(self, name, change):
        raw = [dict(r) for r in self.raw]
        for r in raw:
            change(r)
        idx = os.path.join(self.tmp, name)
        write_index(idx, raw)
        return idx

    def checks(self, findings):
        return sorted({f["check"] for f in findings})

    def messages(self, findings):
        return "\n".join(f"{f['check']} {f['line']} {f['message']}" for f in findings)

    def sub(self, old, new, text=None):
        text = text or self.spec
        self.assertIn(old, text)
        return text.replace(old, new, 1)

    def row_of(self, uid, text=None):
        return next(l for l in (text or self.spec).split("\n") if l.startswith(f"| `{uid}` |"))

    def rnum_of(self, uid, text=None):
        return self.row_of(uid, text).split("|")[2].strip()

    def rdef(self, n, text=None):
        n = str(n).lstrip("R")
        return next(l for l in (text or self.spec).split("\n") if l.startswith(f"R{n}. "))

    def set_where(self, uid, where, text=None):
        return self.sub(self.row_of(uid, text), f"| `{uid}` | {where} |", text)

    def drop_source(self, uid, text=None):
        """Remove a unit from the Source list of the R-number it is traced to."""
        text = text or self.spec
        line = self.rdef(self.rnum_of(uid, text), text)
        head, src = line.split(" Source: ")
        ids = [x for x in src.split(", ") if x != f"`{uid}`"]
        return self.sub(line, head + " Source: " + ", ".join(ids), text)

    def as_ref(self, rule, target, text=None):
        """Trace a rule (and its notes) of another module as `ref:` and drop its R-number."""
        text = text or self.spec
        line = self.rdef(self.rnum_of(rule["id"], text), text)
        for r in self.units:
            if r["kind"] == "note" and r["parent"] == rule["id"]:
                text = self.set_where(r["id"], f"ref: {rule['id']}", text)
        return self.set_where(rule["id"], target, text.replace(line + "\n", "", 1))
