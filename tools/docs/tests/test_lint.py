"""doc_lint: a generated compiled spec passes; one mutation per check makes exactly that check fire (S3 brief, S3 review
round 1: B1, B2, S3, S4, S5, S10, N4, N5; round 2: R2-B1, R2-B2, R2-S1 to R2-S4, R2-S6)."""

import contextlib
import csv
import io
import os
import shutil
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import nfdocs  # noqa: E402
import build_index  # noqa: E402
import doc_lint  # noqa: E402

MODULE = "outbox"   # small module: owned tables, catalog rows, a flagged note, supersedes notes, superseded rules
SHA = "0123456789abcdef0123456789abcdef01234567"


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


def make_spec(rows, owners, cats, module):
    """A compiled spec that satisfies every check: front matter, the eleven sections, one real R-number statement per
    source rule, every ID traced, owned tables and rows and the referenced settings backticked; supersessions as
    CONFLICT naming the governing text, flagged notes as FALSE-POSITIVE with their own reasons. Rows the module does
    not own are left out on purpose."""
    scope = nfdocs.module_scope(rows, owners, cats, module)
    units, tables = scope["units"], scope["tables"]
    keys = sorted({c.split(":", 1)[1] for c in scope["owned_rows"] + scope["settings"]})
    rules = [r for r in units if r["kind"] == "rule"]
    rnum = {r["id"]: f"R{i}" for i, r in enumerate(rules, start=1)}
    entries = []
    for k, r in enumerate(units):
        if r["conflict_markers"] not in ("", "0", 0):
            entries.append(f"CONFLICT {r['id']}: resolved by the later accepted source, stated in R1.")
        elif superseding(r):
            gov = r["superseded_by"][0] if r["kind"] == "rule" and r["superseded_by"] else r["id"]
            entries.append(f"CONFLICT {r['id']}: {gov} governs; the spec states the current text only.")
        elif flagged_only(r):
            entries.append(f"FALSE-POSITIVE {r['id']}: reason number {k} written for this one note alone")

    def where(r):
        if r["id"] in rnum:
            return rnum[r["id"]]
        if r["kind"] == "note" and r["parent"] in rnum:
            return rnum[r["parent"]]
        return "Purpose"

    out = [f"Module: {module}    Chunk: whole    Source ADRs: ADR-0013",
           f"Build step(s): 0    Generated from index: {SHA[:9]}    Compiled by: test, 2026-11-21", "",
           f"# Compiled spec: `{module}`", "",
           "## Purpose", "", f"The module owns <!-- count:tables -->{len(tables)}<!-- /count --> tables.", "",
           "## Entities and tables", ""] + [f"- `{t}`" for t in tables] + [
           "", "## Commands and queries", "", "None.", "", "## Rules", "", "### Topic", ""] + [
           f"{rnum[r['id']]}. Statement {i} restates the law of {r['id']} in plain words. Source: `{r['id']}`"
           for i, r in enumerate(rules, start=1)] + [
           "", "## Invariants", "", "None.", "", "## Edge cases", "", "None.", "",
           "## Settings", ""] + [f"- `{k}`" for k in keys] + [
           "", "## UI annotations", "", "None (headless step).", "", "## Conflicts", ""] + entries + [
           "", "## Proposed (not law)", "", "None.", "", "## Trace", "", "| Source | Where |", "| --- | --- |"] + [
           f"| `{r['id']}` | {where(r)} |" for r in units] + [""]
    return "\n".join(out)


class LintMutations(unittest.TestCase):
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
        cls.scope = nfdocs.module_scope(cls.rows, cls.owners, cls.cats, MODULE)
        cls.units, cls.tables, cls.cat_rows = cls.scope["units"], cls.scope["tables"], cls.scope["owned_rows"]
        cls.rules = [r for r in cls.units if r["kind"] == "rule"]
        cls.spec = make_spec(cls.rows, cls.owners, cls.cats, MODULE)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp)

    def run_lint(self, text, index=None, name="spec.md", module=MODULE, with_info=False, sha=SHA):
        path = os.path.join(self.tmp, name)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)
        findings, info = doc_lint.lint([path], module, index or self.index, nfdocs.DEFAULT_DOCS, sha)
        return (findings, info) if with_info else findings

    def edited_index(self, name, change):
        raw = [dict(r) for r in self.raw]
        for r in raw:
            change(r)
        idx = os.path.join(self.tmp, name)
        write_index(idx, raw)
        return idx

    def checks(self, findings):
        return sorted({f["check"] for f in findings})

    def sub(self, old, new, text=None):
        text = text or self.spec
        self.assertIn(old, text)
        return text.replace(old, new, 1)

    def row_of(self, uid, text=None):
        return next(l for l in (text or self.spec).split("\n") if l.startswith(f"| `{uid}` |"))

    def rdef(self, n, text=None):
        return next(l for l in (text or self.spec).split("\n") if l.startswith(f"R{n}. "))

    # ---------------------------------------------------------------- baseline

    def test_preconditions(self):
        self.assertTrue(self.tables and self.cat_rows and len(self.rules) > 5)
        self.assertTrue(any(flagged_only(r) for r in self.units))
        self.assertTrue(any(r["kind"] == "note" and superseding(r) for r in self.units))
        self.assertTrue(any(r["kind"] == "rule" and superseding(r) for r in self.units))
        self.assertTrue(any(MODULE not in r["primary_module"] for r in self.rules))

    def test_baseline_passes(self):
        self.assertEqual(self.run_lint(self.spec), [])

    # ---------------------------------------------------------------- L0

    def test_l0_front_matter(self):
        self.assertEqual(self.checks(self.run_lint(self.sub("Compiled by: test, 2026-11-21", ""))), ["L0"])
        self.assertEqual(self.checks(self.run_lint(self.sub(f"Module: {MODULE}", "Module: ledger"))), ["L0"])
        self.assertEqual(self.checks(self.run_lint(self.sub("Chunk: whole", "Chunk: all"))), ["L0"])
        self.assertEqual(self.checks(self.run_lint(self.spec, sha="fedcba9876543210")), ["L0"])

    def test_l0_sections(self):
        self.assertEqual(self.checks(self.run_lint(self.sub("## Invariants", "## Invariant list"))), ["L0"])
        self.assertEqual(self.checks(self.run_lint(self.sub("## Edge cases\n\nNone.\n\n", ""))), ["L0"])
        swapped = self.sub("## Invariants", "## TMP").replace("## Edge cases", "## Invariants").replace(
            "## TMP", "## Edge cases")
        self.assertEqual(self.checks(self.run_lint(swapped)), ["L0"])

    def test_l0_chunks_share_sections(self):
        head, tail = self.spec.split("## Invariants", 1)
        front = "\n".join(self.spec.split("\n")[:3])
        trace_head = "## Trace\n\n| Source | Where |\n| --- | --- |\n"
        chunk1 = head.replace("Chunk: whole", "Chunk: 1 of 2") + trace_head
        chunk2 = (front + "\n## Purpose\n\nChunk two.\n\n## Invariants" + tail).replace("Chunk: whole", "Chunk: 2 of 2")
        p1, p2 = os.path.join(self.tmp, "c1.md"), os.path.join(self.tmp, "c2.md")
        for p, t in ((p1, chunk1), (p2, chunk2)):
            with open(p, "w", encoding="utf-8") as fh:
                fh.write(t)
        findings, _ = doc_lint.lint([p1, p2], MODULE, self.index, nfdocs.DEFAULT_DOCS, SHA)
        self.assertEqual(findings, [])

    # ---------------------------------------------------------------- L1

    def test_l1_missing_trace_row(self):
        victim = self.units[3]["id"]
        lines = [l for l in self.spec.split("\n") if not l.startswith(f"| `{victim}` |")]
        f = self.run_lint("\n".join(lines))
        self.assertEqual(self.checks(f), ["L1"])
        self.assertIn(victim, f[0]["message"])

    def test_l1_rule_where_values(self):
        r = next(x for x in self.rules if MODULE in x["primary_module"])
        row = self.row_of(r["id"])
        for bad in ("", "not applicable: history", "R999", "Reads", "Rules", "Purpose", "ref: inventory R-12"):
            self.assertEqual(self.checks(self.run_lint(self.sub(row, f"| `{r['id']}` | {bad} |"))), ["L1"], bad)
        for ok in ("R1, R3", "R1-R3", "R2, Topic"):
            self.assertEqual(self.run_lint(self.sub(row, f"| `{r['id']}` | {ok} |")), [], ok)
        f, info = self.run_lint(self.sub(row, f"| `{r['id']}` | R2, somewhere |"), with_info=True)
        self.assertEqual((f, len([w for w in info["warnings"] if w.startswith("W1")])), ([], 1))

    def test_l1_ref_for_another_modules_rule(self):
        r = next(x for x in self.rules if MODULE not in x["primary_module"] and not superseding(x))
        row = self.row_of(r["id"])
        self.assertEqual(self.run_lint(self.sub(row, f"| `{r['id']}` | ref: inventory R-12 |")), [])
        self.assertEqual(self.run_lint(self.sub(row, f"| `{r['id']}` | ref: {r['id']} |")), [])
        self.assertEqual(self.checks(self.run_lint(self.sub(row, f"| `{r['id']}` | ref: nosuch R-12 |"))), ["L8"])
        self.assertEqual(self.checks(self.run_lint(self.sub(row, f"| `{r['id']}` | ref: ADR-0999.R1 |"))), ["L7"])

    def test_l1_note_may_be_not_applicable_within_the_cap(self):
        note = next(r for r in self.units if r["kind"] == "note" and not superseding(r) and not r["conflict_flag"])
        row = self.row_of(note["id"])
        self.assertEqual(self.run_lint(self.sub(row, f"| `{note['id']}` | not applicable: review credit |")), [])
        self.assertEqual(self.checks(self.run_lint(self.sub(row, f"| `{note['id']}` | not applicable |"))), ["L1"])
        notes = [r for r in self.units if r["kind"] == "note" and not superseding(r)]
        text = self.spec
        for n in notes:
            text = self.sub(self.row_of(n["id"], text), f"| `{n['id']}` | not applicable: history only |", text)
        f = self.run_lint(text)
        self.assertEqual(self.checks(f), ["L1"])
        self.assertIn("not applicable", f[0]["message"])

    def test_l1_definitions_need_visible_real_text(self):
        line = self.rdef(2)
        for bad in (f"```\n{line}\n```", f"<!--\n{line}\n-->", "R2. Short. Source: x", "Reads: " + line,
                    "R2. " + self.rdef(3)[4:]):
            f = self.run_lint(self.sub(line, bad))
            self.assertEqual(self.checks(f), ["L1"], bad)

    def test_l1_coverage(self):
        # every rule row points to R1: at most 4 IDs count for one R-number
        text = self.spec
        for r in self.rules:
            text = self.sub(self.row_of(r["id"], text), f"| `{r['id']}` | R1 |", text)
        f = self.run_lint(text)
        self.assertEqual(self.checks(f), ["L1"])
        self.assertIn("map to R-numbers", f[0]["message"])

    def test_l1_stable_key(self):
        note = next(r for r in self.units if r["kind"] == "note")
        row = self.row_of(note["id"])
        key = self.by[note["id"]]["stable_key"]
        good = row.replace(f"`{note['id']}`", f"`{note['id']}` #{key}")
        f, info = self.run_lint(self.sub(row, good), with_info=True)
        self.assertEqual((f, [w for w in info["warnings"] if w.startswith("W2")]), ([], []))
        bad = row.replace(f"`{note['id']}`", f"`{note['id']}` #000000000000")
        f, info = self.run_lint(self.sub(row, bad), with_info=True)
        self.assertEqual((f, len([w for w in info["warnings"] if w.startswith("W2")])), ([], 1))

    # ---------------------------------------------------------------- L2, L9

    def test_l2_table_not_mentioned(self):
        self.assertEqual(self.checks(self.run_lint(self.sub(f"- `{self.tables[0]}`\n", ""))), ["L2"])

    def test_l2_rows_of_other_modules_not_required(self):
        not_owned = [c for c in self.scope["catalog_rows"] if c not in self.scope["owned_rows"]]
        self.assertTrue(not_owned, "precondition: the module references rows it does not own")
        self.assertNotIn(f"`{not_owned[0].split(':', 1)[1]}`", self.spec)
        self.assertEqual(self.run_lint(self.spec), [])

    def test_l2_catalog_row_not_mentioned(self):
        key = next(c.split(":", 1)[1] for c in self.cat_rows if not c.startswith("settings:"))
        self.assertEqual(self.checks(self.run_lint(self.sub(f"- `{key}`\n", ""))), ["L2"])

    def test_l9_setting_of_a_shared_rule(self):
        module = "periods"
        scope = nfdocs.module_scope(self.rows, self.owners, self.cats, module)
        extra = [c for c in scope["settings"] if c not in scope["owned_rows"]]
        self.assertTrue(extra, "precondition: a setting referenced only by a shared unit")
        spec = make_spec(self.rows, self.owners, self.cats, module)
        self.assertEqual(self.run_lint(spec, module=module), [])
        key = extra[0].split(":", 1)[1]
        self.assertEqual(self.checks(self.run_lint(self.sub(f"- `{key}`\n", "", spec), module=module)), ["L9"])

    # ---------------------------------------------------------------- L3

    def test_l3_proposed_rule_stated_as_law(self):
        victim = next(r["id"] for r in self.rules if not superseding(r))
        n = next(l for l in self.spec.split("\n") if l.startswith(f"| `{victim}` |")).split("|")[2].strip()
        idx = self.edited_index("index-proposed.csv",
                                lambda r: r.update(status="proposed") if r["id"] == victim else None)
        self.assertEqual(self.checks(self.run_lint(self.spec, index=idx)), ["L3"])
        line = self.rdef(n[1:])
        fixed = self.sub(line, line.replace(f"{n}. ", f"{n}. [proposed] ", 1))
        self.assertEqual(self.run_lint(fixed, index=idx), [])
        adr, k = victim.split(".R")
        other = self.rdef(1 if n != "R1" else 2, fixed)
        for form in (f"{adr} rule {k}", f"{adr}, rule {k}", f"rule {k} of {adr}"):
            prose = self.sub(other, other.replace(" in plain words", f" as {form} says"), fixed)
            self.assertEqual(self.checks(self.run_lint(prose, index=idx)), ["L3"], form)

    def test_l3_accepted_rule_marked_proposed(self):
        line = self.rdef(1)
        self.assertEqual(self.checks(self.run_lint(self.sub(line, line.replace("R1. ", "R1. [proposed] ")))), ["L3"])

    # ---------------------------------------------------------------- L4

    def test_l4_typed_counts(self):
        for bad in ("The module writes 4 tables.", "It owns ten tables.", "Tables owned: 10.", "It holds `12 tables`.",
                    "It owns 10 inspection database tables.", "It owns exactly 16 tables.", "Only 99 rules apply.",
                    "It has twenty-one commands.", "A dozen settings exist.", "It has 3 big new owned tables.",
                    "It has 16&nbsp;tables."):
            self.assertEqual(self.checks(self.run_lint(self.sub("in plain words.", bad))), ["L4"], bad)
        self.assertEqual(self.checks(self.run_lint(self.sub("## Invariants", "| Owned tables | 16 |\n\n## Invariants"))),
                         ["L4"])

    def test_l4_citations_and_thresholds_pass(self):
        for ok in ("As rule 15 note says.", "From step 7 events.", "See INV-12 tables.", "In layer 3 modules.",
                   "At most 12 columns per key.", "One table holds them.", "Item 7 of rule 3 holds.",
                   "Note: two values differ."):
            self.assertEqual(self.run_lint(self.sub("in plain words.", ok)), [], ok)

    def test_l4_wrong_generated_count(self):
        n = len(self.tables)
        self.assertEqual(self.checks(self.run_lint(self.sub(f"count:tables -->{n}<", f"count:tables -->{n + 1}<"))),
                         ["L4"])

    # ---------------------------------------------------------------- L5, L10, review list

    def test_l5_conflict_marker_unlisted(self):
        victim = next(r["id"] for r in self.rules if not superseding(r))
        idx = self.edited_index("index-marker.csv",
                                lambda r: r.update(conflict_markers="1") if r["id"] == victim else None)
        f = self.run_lint(self.spec, index=idx)
        self.assertEqual(self.checks(f), ["L5"])
        self.assertIn(victim, f[0]["message"])
        rows = build_index.read_index(idx)
        self.assertEqual(self.run_lint(make_spec(rows, self.owners, self.cats, MODULE), index=idx), [])

    def test_l5_flagged_note_unlisted(self):
        flagged = next(r for r in self.units if flagged_only(r))
        lines = [l for l in self.spec.split("\n") if not l.startswith(f"FALSE-POSITIVE {flagged['id']}:")]
        self.assertEqual(self.checks(self.run_lint("\n".join(lines))), ["L5"])

    def test_l5_supersedes_note_needs_a_governing_conflict(self):
        note = next(r for r in self.units if r["kind"] == "note" and superseding(r))
        line = next(l for l in self.spec.split("\n") if l.startswith(f"CONFLICT {note['id']}:"))
        for bad in (f"FALSE-POSITIVE {note['id']}: the note only renames a term, nothing more",
                    f"CONFLICT {note['id']}: kept as it is written in the source text", ""):
            self.assertEqual(self.checks(self.run_lint(self.sub(line, bad))), ["L5"], bad)
        self.assertEqual(self.run_lint(self.sub(line, f"OPEN {note['id']}: see OQ-123 for the question")), [])
        row = self.row_of(note["id"])
        ref_ok = self.sub(row, f"| `{note['id']}` | ref: ledger R-3 |", self.sub(line, ""))
        if MODULE not in note["primary_module"]:
            self.assertEqual(self.run_lint(ref_ok), [])

    def test_l5_unflagged_supersedes_note_must_be_listed(self):
        note = next(r for r in self.units if r["kind"] == "note" and not superseding(r) and not r["conflict_flag"])
        idx = self.edited_index("index-supersedes.csv",
                                lambda r: r.update(relation="supersedes") if r["id"] == note["id"] else None)
        self.assertEqual(self.checks(self.run_lint(self.spec, index=idx)), ["L5"])

    def test_l5_entry_forms(self):
        flagged = next(r for r in self.units if flagged_only(r))
        line = next(l for l in self.spec.split("\n") if l.startswith(f"FALSE-POSITIVE {flagged['id']}:"))
        for bad in (f"FALSE-POSITIVE {flagged['id']}", f"FALSE-POSITIVE {flagged['id']}: fine",
                    f"CONFLICT {flagged['id']}: .", f"OPEN {flagged['id']}: asked the author",
                    f"{line}\nCONFLICT ADR-0999.R1: resolved by the later accepted source, R1."):
            self.assertEqual(self.checks(self.run_lint(self.sub(line, bad))), ["L5"], bad)

    def test_l5_reused_reason(self):
        notes = [r["id"] for r in self.units if r["kind"] == "note" and not superseding(r)][:4]
        extra = "\n".join(f"FALSE-POSITIVE {n}: the same filler reason for every entry" for n in notes)
        self.assertEqual(self.checks(self.run_lint(self.sub("## Proposed (not law)", extra + "\n\n## Proposed (not law)"))),
                         ["L5"])
        three = "\n".join(f"FALSE-POSITIVE {n}: the same filler reason for every entry" for n in notes[:3])
        self.assertEqual(self.run_lint(self.sub("## Proposed (not law)", three + "\n\n## Proposed (not law)")), [])

    def test_l10_superseded_rule(self):
        sup = next(r for r in self.rules if superseding(r) and MODULE in r["primary_module"])
        line = next(l for l in self.spec.split("\n") if l.startswith(f"CONFLICT {sup['id']}:"))
        for bad in ("", f"FALSE-POSITIVE {sup['id']}: harmless, the rule text is unchanged here"):
            f = self.run_lint(self.sub(line, bad))
            self.assertEqual(self.checks(f), ["L10"], bad)
            self.assertIn(sup["id"], f[0]["message"])

    def test_w3_superseded_rule_text(self):
        sup = next(r for r in self.rules if r["superseded_by"])
        f, info = self.run_lint(self.spec, with_info=True)
        self.assertTrue(any(w.startswith(f"W3 {sup['id']}") for w in info["warnings"]))
        n = self.row_of(sup["id"]).split("|")[2].strip()
        line = self.rdef(n[1:])
        fixed = self.sub(line, line.replace(" in plain words", f" as {sup['superseded_by'][0]} now states it"))
        f, info = self.run_lint(fixed, with_info=True)
        self.assertFalse(any(w.startswith(f"W3 {sup['id']}") for w in info["warnings"]))

    def test_review_list(self):
        path = os.path.join(self.tmp, "review.md")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(self.spec)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            doc_lint.main([path, "--module", MODULE, "--index", self.index, "--index-commit", SHA])
        out = buf.getvalue()
        self.assertIn("REVIEW LIST", out)
        for l in self.spec.split("\n"):
            if l.startswith(("CONFLICT ", "FALSE-POSITIVE ", "OPEN ")):
                self.assertIn("  " + l, out)

    # ---------------------------------------------------------------- L6, L7, L8

    def test_l6_over_budget(self):
        pad = "\n".join("Plain filler sentence for the size check." for _ in range(1500))
        self.assertEqual(self.checks(self.run_lint(self.sub("## Settings", pad + "\n\n## Settings"))), ["L6"])

    def test_l7_unknown_trace_id(self):
        f = self.run_lint(self.sub("| Source | Where |\n| --- | --- |\n",
                                   "| Source | Where |\n| --- | --- |\n| `ADR-0999.R1` | R1 |\n"))
        self.assertEqual(self.checks(f), ["L7"])

    def test_l8_cross_module_references(self):
        self.assertEqual(self.run_lint(self.sub("in plain words.", "as `inventory R-12` says.")), [])
        for bad in ("`inventory R-scrap`", "nosuchmodule R-12", "`nosuchmodule ADR-0070.R2`", "see R-3"):
            self.assertEqual(self.checks(self.run_lint(self.sub("in plain words.", f"as {bad} says."))), ["L8"], bad)

    def test_cli_first_line(self):
        path = os.path.join(self.tmp, "cli.md")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(self.spec)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = doc_lint.main([path, "--module", MODULE, "--index", self.index, "--index-commit", SHA])
        self.assertEqual((rc, buf.getvalue().split("\n")[0]), (0, "LINT PASS findings=0"))
        with open(path, "a", encoding="utf-8") as fh:
            fh.write("| `ADR-0999.R1` | R1 |\n")
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = doc_lint.main([path, "--module", MODULE, "--index", self.index, "--index-commit", SHA, "--json"])
        self.assertEqual((rc, buf.getvalue().split("\n")[0]), (1, "LINT FAIL findings=1"))


class ReviewProbes(unittest.TestCase):
    """The S3 review's probe specs (rounds 1 and 2) passed earlier lints; each must fail now apart from front matter."""

    ROOT = os.path.expanduser("~/Projects/NativeFlows-lab/fable/s3-out")

    def test_probes_fail(self):
        r1, r2 = os.path.join(self.ROOT, "review-s3-lint-probes"), os.path.join(self.ROOT, "review-s3-lint-probes-r2")
        if not (os.path.isdir(r1) and os.path.isdir(r2)):
            self.skipTest("review probes not present on this machine")
        cases = {
            (r1, "A2_missing_rules_reads.md"): ("quality", None), (r1, "B_all_na.md"): ("quality", None),
            (r1, "C_one_row.md"): ("quality", None), (r1, "D_counts.md"): ("quality", None),
            (r1, "E_policy_empty.md"): ("policy", None), (r1, "F2_prop_as_law.md"): ("quality", "idx-prop.csv"),
            (r2, "G1_filler_heading_quality.md"): ("quality", None), (r2, "G2_filler_R1_quality.md"): ("quality", None),
            (r2, "G3_filler_heading_policy.md"): ("policy", None), (r2, "H_policy_fp_filler.md"): ("policy", None),
            (r2, "I_policy_every_id.md"): ("policy", None), (r2, "J_prop_heading.md"): ("quality", "idx-prop2.csv"),
            (r2, "K_counts.md"): ("quality", None), (r2, "L1_fence_defs.md"): ("quality", None),
            (r2, "L2_comment_defs.md"): ("quality", None), (r2, "F2.md"): ("quality", "idx-prop2.csv")}
        for (d, name), (module, idx) in cases.items():
            index = os.path.join(d, idx) if idx else nfdocs.DEFAULT_INDEX
            findings, _ = doc_lint.lint([os.path.join(d, name)], module, index, nfdocs.DEFAULT_DOCS)
            body = [f for f in findings if f["check"] != "L0"]
            self.assertTrue(body, f"{name} passes the lint apart from front matter")


if __name__ == "__main__":
    unittest.main()
