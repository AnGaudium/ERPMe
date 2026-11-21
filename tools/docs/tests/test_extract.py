"""Extraction on mini-ADR fixtures, with exact asserts (S3 brief, Tests)."""

import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import nfdocs  # noqa: E402

FIXTURE_DOCS = os.path.join(HERE, "fixtures", "docs")


class ExtractFixtures(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.units, cls.parsed, cls.dangling = nfdocs.extract(FIXTURE_DOCS)
        cls.by = {u["id"]: u for u in cls.units}

    def test_ids_in_order(self):
        self.assertEqual([u["id"] for u in self.units], [
            "ADR-0001.H", "ADR-0001.D0", "ADR-0001.R1", "ADR-0001.R1.N1", "ADR-0001.R1.N2", "ADR-0001.R2",
            "ADR-0001.R2.N1", "ADR-0001.R3", "ADR-0001.C", "ADR-0001.C.N1", "ADR-0001.V", "ADR-0001.U",
            "ADR-0002.H", "ADR-0002.R1", "ADR-0002.U",
            "ADR-0003.H", "ADR-0003.D0", "ADR-0003.R1", "ADR-0003.R2", "ADR-0003.L2.R1", "ADR-0003.U"])

    def test_status(self):
        self.assertEqual([a["status"] for a in self.parsed], ["accepted", "proposed", "superseded"])
        self.assertEqual(self.by["ADR-0002.R1"]["adr_status"], "proposed")

    def test_rule_body_and_groups(self):
        r1 = self.by["ADR-0001.R1"]
        self.assertEqual(r1["text"], "1. Rule one uses `alpha_table`. See [ADR-0002](0002-beta.md) rule 1 and INV-07.")
        self.assertEqual((r1["group"], r1["line_start"], r1["line_end"]), ("First group", 13, 13))
        r2 = self.by["ADR-0001.R2"]
        self.assertEqual(r2["text"], "2. Rule two. ADR-0002 rules 1–2 and ADR-0001 rule 9 point further.\n\n"
                                     "   Body text after rule two.\n\n   Back in rule two body.")
        self.assertEqual((r2["line_start"], r2["line_end"]), (20, 26))
        self.assertEqual(self.by["ADR-0001.R3"]["group"], "Second group")

    def test_notes(self):
        n1 = self.by["ADR-0001.R1.N1"]
        self.assertEqual((n1["note_author"], n1["note_date"], n1["relation"], n1["conflict"]),
                         (None, None, "amends", False))
        self.assertEqual(n1["parent"], "ADR-0001.R1")
        n2 = self.by["ADR-0001.R1.N2"]
        self.assertEqual(n2["note_author"], "[ADR-0003](0003-gamma.md), 2026-11-05")
        self.assertEqual(n2["note_date"], "2026-11-05")
        self.assertEqual((n2["line_start"], n2["line_end"]), (17, 19))
        self.assertTrue(n2["text"].endswith("Continuation of the indented note."))
        self.assertEqual(n2["relation"], "supersedes")
        self.assertEqual(n2["conflict_phrases"], ["no longer", "replaces"])
        n3 = self.by["ADR-0001.R2.N1"]
        self.assertEqual((n3["relation"], n3["note_date"]), ("superseded-by", "2026-11-10"))
        self.assertEqual(n3["note_author"], "chief architect, 2026-11-10, under the delegation")
        self.assertEqual(self.by["ADR-0001.C.N1"]["text"], "Note: context note.")

    def test_xrefs_and_dangling(self):
        self.assertEqual(self.by["ADR-0001.R1"]["xrefs_rules"], ["ADR-0002.R1"])
        self.assertEqual(self.by["ADR-0001.R1"]["xrefs_inv"], ["INV-07"])
        self.assertEqual(self.by["ADR-0001.R2"]["xrefs_rules"], ["ADR-0001.R9", "ADR-0002.R1", "ADR-0002.R2"])
        self.assertEqual(self.by["ADR-0001.R2"]["dangling"], ["ADR-0001.R9", "ADR-0002.R2"])
        self.assertEqual(sorted(self.dangling), [("ADR-0001.R2", "ADR-0001.R9"), ("ADR-0001.R2", "ADR-0002.R2")])
        r3 = self.by["ADR-0001.R3"]
        self.assertEqual((r3["xrefs_oq"], r3["xrefs_ec"], r3["xrefs_ds"]), (["OQ-12"], ["EC-03"], ["DS-05"]))
        self.assertEqual(r3["conflict_markers"], 1)
        self.assertEqual(self.by["ADR-0003.L2.R1"]["xrefs_rules"], ["ADR-0003.R2"])

    def test_restarted_lists_and_coverage(self):
        self.assertEqual(self.by["ADR-0003.L2.R1"]["group"], "Part B")
        for a in self.parsed:
            self.assertEqual(a["coverage"]["uncovered"], [], a["file"])
        self.assertIn("docs/adr/0003-gamma.md: no '### Rules'; numbered lists under '## Decision' read as rules, "
                      "'###' headings as groups", self.parsed[2]["oddities"])

    def test_first_step_and_refs(self):
        self.assertEqual(nfdocs.first_step(self.by["ADR-0001.R3"]["text"]), "5b")
        self.assertEqual(nfdocs.expand_list("3, 5–7 and 9"), ["3", "5", "6", "7", "9"])
        self.assertEqual(nfdocs.find_refs("ADR-0003 R6 and R8; ADR-0022 rule 4, 2026-11-21")[1],
                         ["ADR-0003.R6", "ADR-0003.R8", "ADR-0022.R4"])
        self.assertEqual(nfdocs.find_phrases("INSERT ... ON CONFLICT DO NOTHING", nfdocs.CONFLICT_PHRASES), [])

    def test_deterministic(self):
        again, _p, _d = nfdocs.extract(FIXTURE_DOCS)
        self.assertEqual([nfdocs.unit_record(u) for u in again], [nfdocs.unit_record(u) for u in self.units])


if __name__ == "__main__":
    unittest.main()
