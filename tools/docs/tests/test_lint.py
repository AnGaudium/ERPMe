"""doc_lint: a generated compiled spec passes; one mutation per check makes exactly that check fire (S3 brief and the
S3 review: B1, B2, S3, S4, S5, S10, N4, N5)."""

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

MODULE = "outbox"   # small module with owned tables, catalog rows, flagged notes and a superseded rule
SHA = "0123456789abcdef0123456789abcdef01234567"
REASON = "harmless: the note only renames a term, checked"


def write_index(path, rows):
    with open(path, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=build_index.INDEX_FIELDS, lineterminator="\n")
        w.writeheader()
        for r in rows:
            w.writerow(r)


def needs_entry(r):
    return ((r["kind"] == "note" and (r["conflict_flag"] or r["relation"] in ("supersedes", "superseded-by")))
            or (r["kind"] == "rule" and (r["superseded_by"] or r["relation"] == "superseded-by")))


def make_spec(rows, owners, cats, module):
    """A compiled spec that satisfies every check: front matter, the eleven sections, one R-number per source rule,
    every ID traced, owned tables and rows and the referenced settings backticked, every flagged, superseding and
    superseded unit listed under Conflicts with a reason. Rows the module does not own are left out on purpose."""
    scope = nfdocs.module_scope(rows, owners, cats, module)
    units, tables = scope["units"], scope["tables"]
    keys = sorted({c.split(":", 1)[1] for c in scope["owned_rows"] + scope["settings"]})
    rules = [r for r in units if r["kind"] == "rule"]
    rnum = {r["id"]: f"R{i}" for i, r in enumerate(rules, start=1)}
    entries = []
    for r in units:
        if r["conflict_markers"] not in ("", "0", 0):
            entries.append(f"CONFLICT {r['id']}: resolved by the later accepted source, by date.")
        elif needs_entry(r):
            entries.append(f"FALSE-POSITIVE {r['id']}: {REASON}")

    def where(r):
        if r["id"] in rnum:
            return rnum[r["id"]]
        if r["kind"] == "note" and r["parent"] in rnum:
            return rnum[r["parent"]]
        return "Purpose" if r["kind"] == "section" else "not applicable: review credit only"

    out = [f"Module: {module}    Chunk: whole    Source ADRs: ADR-0013",
           f"Build step(s): 0    Generated from index: {SHA[:9]}    Compiled by: test, 2026-11-21", "",
           f"# Compiled spec: `{module}`", "",
           "## Purpose", "", f"The module owns <!-- count:tables -->{len(tables)}<!-- /count --> tables.", "",
           "## Entities and tables", ""] + [f"- `{t}`" for t in tables] + [
           "", "## Commands and queries", "", "None.", "", "## Rules", "", "### Topic", ""] + [
           f"{rnum[r['id']]}. Statement {i}. Source: `{r['id']}`" for i, r in enumerate(rules, start=1)] + [
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

    # ---------------------------------------------------------------- baseline

    def test_preconditions(self):
        self.assertTrue(self.tables and self.cat_rows and len(self.rules) > 5)
        self.assertTrue(any(r["kind"] == "note" and r["conflict_flag"] for r in self.units))
        self.assertTrue(any(r["kind"] == "rule" and (r["superseded_by"] or r["relation"] == "superseded-by")
                            for r in self.units))

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

    def test_l1_where_values(self):
        r = self.rules[1]
        row = f"| `{r['id']}` | R2 |"
        for bad in ("", "not applicable: history", "R999", "Reads"):
            self.assertEqual(self.checks(self.run_lint(self.sub(row, f"| `{r['id']}` | {bad} |"))), ["L1"], bad)
        for ok in ("R1, R3", "R1-R3", "Settings", "Topic"):
            self.assertEqual(self.run_lint(self.sub(row, f"| `{r['id']}` | {ok} |")), [], ok)
        f, info = self.run_lint(self.sub(row, f"| `{r['id']}` | somewhere |"), with_info=True)
        self.assertEqual((f, len(info["warnings"])), ([], 1))

    def test_l1_not_applicable_on_a_note(self):
        note = next(r for r in self.units if r["kind"] == "note" and not needs_entry(r))
        line = next(l for l in self.spec.split("\n") if l.startswith(f"| `{note['id']}` |"))
        self.assertEqual(self.run_lint(self.sub(line, f"| `{note['id']}` | not applicable: review credit |")), [])
        self.assertEqual(self.checks(self.run_lint(self.sub(line, f"| `{note['id']}` | not applicable |"))), ["L1"])

    def test_l1_r_number_on_a_reads_line_is_not_defined(self):
        text = self.sub("R2. Statement 2.", "Reads: R2. Statement 2.")
        self.assertEqual(self.checks(self.run_lint(text)), ["L1"])

    def test_l1_coverage(self):
        # collapse every rule onto R1: all rule and note trace rows point to R1, the other R-numbers are gone
        lines = []
        for l in self.spec.split("\n"):
            if l[:1] == "R" and l[1:2].isdigit() and not l.startswith("R1."):
                continue
            if l.startswith("| `ADR-") and not l.endswith("not applicable: review credit only |") \
                    and not l.endswith("| Purpose |"):
                l = l.rsplit("|", 2)[0] + "| R1 |"
            lines.append(l)
        f = self.run_lint("\n".join(lines))
        self.assertEqual(self.checks(f), ["L1"])
        self.assertIn("R-numbers for", f[0]["message"])

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
        victim = self.rules[0]["id"]
        idx = self.edited_index("index-proposed.csv",
                                lambda r: r.update(status="proposed") if r["id"] == victim else None)
        self.assertEqual(self.checks(self.run_lint(self.spec, index=idx)), ["L3"])
        fixed = self.sub("R1. Statement 1.", "R1. [proposed] Statement 1.")
        self.assertEqual(self.run_lint(fixed, index=idx), [])
        # the 'ADR-nnnn rule n' form is recognised too (S4)
        adr, n = victim.split(".R")
        prose = self.sub("R2. Statement 2.", f"R2. As {adr} rule {n} says.", fixed)
        self.assertEqual(self.checks(self.run_lint(prose, index=idx)), ["L3"])

    def test_l3_accepted_rule_marked_proposed(self):
        self.assertEqual(self.checks(self.run_lint(self.sub("R1. Statement 1.", "R1. [proposed] Statement 1."))),
                         ["L3"])

    # ---------------------------------------------------------------- L4

    def test_l4_typed_counts(self):
        for bad in ("The module writes 4 tables.", "It owns ten tables.", "Tables owned: 10.",
                    "It holds `12 tables`.", "It owns 10 inspection database tables."):
            self.assertEqual(self.checks(self.run_lint(self.sub("Statement 1.", bad))), ["L4"], bad)

    def test_l4_citations_and_thresholds_pass(self):
        for ok in ("As rule 15 note says.", "From step 7 events.", "See INV-12 tables.", "In layer 3 modules.",
                   "At most 12 columns per key."):
            self.assertEqual(self.run_lint(self.sub("Statement 1.", ok)), [], ok)

    def test_l4_wrong_generated_count(self):
        n = len(self.tables)
        self.assertEqual(self.checks(self.run_lint(self.sub(f"count:tables -->{n}<", f"count:tables -->{n + 1}<"))),
                         ["L4"])

    # ---------------------------------------------------------------- L5, L10

    def test_l5_conflict_marker_unlisted(self):
        victim = self.rules[1]["id"]
        idx = self.edited_index("index-marker.csv",
                                lambda r: r.update(conflict_markers="1") if r["id"] == victim else None)
        f = self.run_lint(self.spec, index=idx)
        self.assertEqual(self.checks(f), ["L5"])
        self.assertIn(victim, f[0]["message"])
        rows = build_index.read_index(idx)
        self.assertEqual(self.run_lint(make_spec(rows, self.owners, self.cats, MODULE), index=idx), [])

    def test_l5_flagged_note_unlisted(self):
        flagged = next(r for r in self.units if r["kind"] == "note" and r["conflict_flag"])
        lines = [l for l in self.spec.split("\n") if not l.startswith(f"FALSE-POSITIVE {flagged['id']}:")]
        self.assertEqual(self.checks(self.run_lint("\n".join(lines))), ["L5"])

    def test_l5_unflagged_supersedes_note_must_be_listed(self):
        note = next(r for r in self.units if r["kind"] == "note" and not needs_entry(r))
        idx = self.edited_index("index-supersedes.csv",
                                lambda r: r.update(relation="supersedes") if r["id"] == note["id"] else None)
        self.assertEqual(self.checks(self.run_lint(self.spec, index=idx)), ["L5"])

    def test_l5_entry_forms(self):
        flagged = next(r for r in self.units if r["kind"] == "note" and r["conflict_flag"])
        line = f"FALSE-POSITIVE {flagged['id']}: {REASON}"
        for bad in (f"FALSE-POSITIVE {flagged['id']}", f"FALSE-POSITIVE {flagged['id']}: fine",
                    f"CONFLICT {flagged['id']}: .", f"OPEN {flagged['id']}: asked the author",
                    f"{line}\nCONFLICT ADR-0999.R1: resolved by the later accepted source."):
            self.assertEqual(self.checks(self.run_lint(self.sub(line, bad))), ["L5"], bad)
        self.assertEqual(self.run_lint(self.sub(line, f"OPEN {flagged['id']}: see OQ-123 for the question")), [])

    def test_l10_superseded_rule_unlisted(self):
        sup = next(r for r in self.units if r["kind"] == "rule" and (r["superseded_by"] or r["relation"]))
        lines = [l for l in self.spec.split("\n") if not l.startswith(f"FALSE-POSITIVE {sup['id']}:")]
        f = self.run_lint("\n".join(lines))
        self.assertEqual(self.checks(f), ["L10"])
        self.assertIn(sup["id"], f[0]["message"])

    # ---------------------------------------------------------------- L6, L7, L8

    def test_l6_over_budget(self):
        pad = "\n".join("Plain filler sentence for the size check." for _ in range(1500))
        self.assertEqual(self.checks(self.run_lint(self.sub("## Settings", pad + "\n\n## Settings"))), ["L6"])

    def test_l7_unknown_trace_id(self):
        f = self.run_lint(self.sub("| Source | Where |\n| --- | --- |\n",
                                   "| Source | Where |\n| --- | --- |\n| `ADR-0999.R1` | R1 |\n"))
        self.assertEqual(self.checks(f), ["L7"])

    def test_l8_cross_module_references(self):
        self.assertEqual(self.run_lint(self.sub("Statement 1.", "As `inventory R-12` says.")), [])
        for bad in ("`inventory R-scrap`", "nosuchmodule R-12", "`nosuchmodule ADR-0070.R2`", "see R-3"):
            self.assertEqual(self.checks(self.run_lint(self.sub("Statement 1.", f"As {bad} says."))), ["L8"], bad)

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
    """The S3 review's probe specs passed the old lint; each must fail now apart from front matter (red evidence
    for B1, B2, S4, S5)."""

    PROBES = os.path.expanduser("~/Projects/NativeFlows-lab/fable/s3-out/review-s3-lint-probes")

    def test_probes_fail(self):
        if not os.path.isdir(self.PROBES):
            self.skipTest("review probes not present on this machine")
        cases = {"A2_missing_rules_reads.md": ("quality", None), "B_all_na.md": ("quality", None),
                 "C_one_row.md": ("quality", None), "D_counts.md": ("quality", None),
                 "E_policy_empty.md": ("policy", None), "F2_prop_as_law.md": ("quality", "idx-prop.csv")}
        for name, (module, idx) in cases.items():
            index = os.path.join(self.PROBES, idx) if idx else nfdocs.DEFAULT_INDEX
            findings, _ = doc_lint.lint([os.path.join(self.PROBES, name)], module, index, nfdocs.DEFAULT_DOCS)
            body = [f for f in findings if f["check"] != "L0"]
            self.assertTrue(body, f"{name} passes the lint apart from front matter")


if __name__ == "__main__":
    unittest.main()
