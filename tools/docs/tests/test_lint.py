"""doc_lint: a generated compiled spec passes; one mutation per check makes exactly that check fire (S3 brief)."""

import csv
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

MODULE = "outbox"   # small module with owned tables, catalog rows and a conflict-flagged note


def write_index(path, rows):
    with open(path, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=build_index.INDEX_FIELDS, lineterminator="\n")
        w.writeheader()
        for r in rows:
            w.writerow(r)


def make_spec(rows, owners, cats, module, extra_rules=""):
    """A compiled spec that satisfies every check: all IDs traced, owned tables, owned catalog rows and the
    referenced settings backticked. Rows the module does not own are left out on purpose (L2 must not ask for them)."""
    scope = nfdocs.module_scope(rows, owners, cats, module)
    units, tables = scope["units"], scope["tables"]
    keys = sorted({c.split(":", 1)[1] for c in scope["owned_rows"] + scope["settings"]})
    flagged = [r for r in units if r["kind"] == "note" and r["conflict_flag"]]
    marked = [r for r in units if r["conflict_markers"] not in ("", "0", 0)]
    out = [f"# Compiled spec: `{module}`", "",
           f"Module: {module}    Chunk: whole    Source ADRs: none", "",
           "## Purpose", "", f"The module owns <!-- count:tables -->{len(tables)}<!-- /count --> tables.", "",
           "## Entities and tables", ""] + [f"- `{t}`" for t in tables] + [
           "", "## Rules", "", "### Topic", "", "R1. A statement. Source: `" + units[0]["id"] + "`", extra_rules, "",
           "## Settings", ""] + [f"- `{k}`" for k in keys] + ["", "## Conflicts", ""] + [
           f"FALSE-POSITIVE {r['id']}" for r in flagged] + [f"CONFLICT {r['id']}: resolved." for r in marked] + [
           "", "## Proposed (not law)", "", "None.", "", "## Trace", "", "| Source | Where |", "| --- | --- |"] + [
           f"| `{r['id']}` | R1 |" for r in units] + [""]
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
        cls.spec = make_spec(cls.rows, cls.owners, cls.cats, MODULE)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp)

    def run_lint(self, text, index=None, name="spec.md", module=MODULE, with_info=False):
        path = os.path.join(self.tmp, name)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)
        findings, info = doc_lint.lint([path], module, index or self.index, nfdocs.DEFAULT_DOCS)
        return (findings, info) if with_info else findings

    def checks(self, findings):
        return sorted({f["check"] for f in findings})

    def test_preconditions(self):
        self.assertTrue(self.tables and self.cat_rows and len(self.units) > 5)

    def test_baseline_passes(self):
        self.assertEqual(self.run_lint(self.spec), [])

    def test_l1_missing_trace_row(self):
        victim = self.units[3]["id"]
        f = self.run_lint(self.spec.replace(f"| `{victim}` | R1 |\n", ""))
        self.assertEqual(self.checks(f), ["L1"])
        self.assertIn(victim, f[0]["message"])

    def test_l2_table_not_mentioned(self):
        f = self.run_lint(self.spec.replace(f"- `{self.tables[0]}`\n", ""))
        self.assertEqual(self.checks(f), ["L2"])

    def test_l2_rows_of_other_modules_not_required(self):
        not_owned = [c for c in self.scope["catalog_rows"] if c not in self.scope["owned_rows"]]
        self.assertTrue(not_owned, "precondition: the module references rows it does not own")
        key = not_owned[0].split(":", 1)[1]
        self.assertNotIn(f"`{key}`", self.spec)
        self.assertEqual(self.run_lint(self.spec), [])

    def test_l2_catalog_row_not_mentioned(self):
        key = self.cat_rows[0].split(":", 1)[1]
        f = self.run_lint(self.spec.replace(f"- `{key}`\n", ""))
        self.assertEqual(self.checks(f), ["L2"])

    def test_l3_proposed_rule_stated_as_law(self):
        victim = self.units[0]["id"]
        raw = [dict(r) for r in self.raw]
        for r in raw:
            if r["id"] == victim:
                r["status"] = "proposed"
        idx = os.path.join(self.tmp, "index-proposed.csv")
        write_index(idx, raw)
        self.assertEqual(self.checks(self.run_lint(self.spec, index=idx)), ["L3"])
        fixed = self.spec.replace("R1. A statement.", "R1. [proposed] A statement.")
        self.assertEqual(self.run_lint(fixed, index=idx), [])

    def test_l3_accepted_rule_marked_proposed(self):
        f = self.run_lint(self.spec.replace("R1. A statement.", "R1. [proposed] A statement."))
        self.assertEqual(self.checks(f), ["L3"])

    def test_l4_bare_count(self):
        f = self.run_lint(self.spec.replace("R1. A statement.", "R1. The module writes 4 tables."))
        self.assertEqual(self.checks(f), ["L4"])

    def test_l4_wrong_generated_count(self):
        n = len(self.tables)
        f = self.run_lint(self.spec.replace(f"count:tables -->{n}<", f"count:tables -->{n + 1}<"))
        self.assertEqual(self.checks(f), ["L4"])

    def test_l5_conflict_marker_unlisted(self):
        victim = self.units[1]["id"]
        raw = [dict(r) for r in self.raw]
        for r in raw:
            if r["id"] == victim:
                r["conflict_markers"] = "1"
        idx = os.path.join(self.tmp, "index-marker.csv")
        write_index(idx, raw)
        f = self.run_lint(self.spec, index=idx)
        self.assertEqual(self.checks(f), ["L5"])
        self.assertIn(victim, f[0]["message"])
        rows = build_index.read_index(idx)
        self.assertEqual(self.run_lint(make_spec(rows, self.owners, self.cats, MODULE), index=idx), [])

    def test_l5_flagged_note_unlisted(self):
        flagged = [r for r in self.units if r["kind"] == "note" and r["conflict_flag"]]
        self.assertTrue(flagged, "precondition: the module has a conflict-flagged note")
        f = self.run_lint(self.spec.replace(f"FALSE-POSITIVE {flagged[0]['id']}\n", ""))
        self.assertEqual(self.checks(f), ["L5"])

    def test_l6_over_budget(self):
        pad = "\n".join("Plain filler sentence for the size check." for _ in range(1500))
        f = self.run_lint(self.spec.replace("## Settings", pad + "\n\n## Settings"))
        self.assertEqual(self.checks(f), ["L6"])

    def test_l7_unknown_trace_id(self):
        f = self.run_lint(self.spec.replace("| Source | Where |\n| --- | --- |\n",
                                            "| Source | Where |\n| --- | --- |\n| `ADR-0999.R1` | R1 |\n"))
        self.assertEqual(self.checks(f), ["L7"])

    def test_l8_cross_module_references(self):
        self.assertEqual(self.run_lint(self.spec.replace("R1. A statement.", "R1. As `inventory R-12` says.")), [])
        for bad in ("`inventory R-scrap`", "nosuchmodule R-12", "`nosuchmodule ADR-0070.R2`", "see R-3"):
            f = self.run_lint(self.spec.replace("R1. A statement.", f"R1. As {bad} says."))
            self.assertEqual(self.checks(f), ["L8"], bad)

    def test_l9_setting_of_a_shared_rule(self):
        module = "periods"
        scope = nfdocs.module_scope(self.rows, self.owners, self.cats, module)
        extra = [c for c in scope["settings"] if c not in scope["owned_rows"]]
        self.assertTrue(extra, "precondition: a setting referenced only by a shared unit")
        spec = make_spec(self.rows, self.owners, self.cats, module)
        self.assertEqual(self.run_lint(spec, module=module), [])
        key = extra[0].split(":", 1)[1]
        f = self.run_lint(spec.replace(f"- `{key}`\n", ""), module=module)
        self.assertEqual(self.checks(f), ["L9"])

    def test_where_cells(self):
        victim = self.units[2]["id"]
        row = f"| `{victim}` | R1 |"
        self.assertEqual(self.checks(self.run_lint(self.spec.replace(row, f"| `{victim}` |  |"))), ["L1"])
        self.assertEqual(self.checks(self.run_lint(self.spec.replace(row, f"| `{victim}` | not applicable |"))),
                         ["L1"])
        for ok in ("not applicable: review credit", "Settings", "R1, R3", "Topic"):
            self.assertEqual(self.run_lint(self.spec.replace(row, f"| `{victim}` | {ok} |")), [], ok)
        f, info = self.run_lint(self.spec.replace(row, f"| `{victim}` | somewhere |"), with_info=True)
        self.assertEqual(f, [])
        self.assertEqual(len(info["warnings"]), 1)

    def test_cli_first_line(self):
        path = os.path.join(self.tmp, "cli.md")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(self.spec)
        import contextlib
        import io
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = doc_lint.main([path, "--module", MODULE, "--index", self.index])
        self.assertEqual((rc, buf.getvalue().split("\n")[0]), (0, "LINT PASS findings=0"))
        with open(path, "a", encoding="utf-8") as fh:
            fh.write("| `ADR-0999.R1` | R1 |\n")
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = doc_lint.main([path, "--module", MODULE, "--index", self.index, "--json"])
        self.assertEqual((rc, buf.getvalue().split("\n")[0]), (1, "LINT FAIL findings=1"))


if __name__ == "__main__":
    unittest.main()
