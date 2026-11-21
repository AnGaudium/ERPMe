"""Note boundaries, the 'Note (...) adds ...:' head, inbound supersession and the widened relation phrases
(S3 review S1, S2, S3), on fixtures/docs2 (shapes of ADR-0047 lines 41-48, ADR-0077 lines 205-210, ADR-0063 line 258,
ADR-0027 rule 10, ADR-0054 rule 3, ADR-0042 rule 7 note 1, ADR-0074 rule 4 note 1)."""

import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import nfdocs  # noqa: E402

FIXTURE_DOCS = os.path.join(HERE, "fixtures", "docs2")


class Boundary(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.units, cls.parsed, cls.dangling = nfdocs.extract(FIXTURE_DOCS)
        cls.by = {u["id"]: u for u in cls.units}

    def test_table_after_an_introducing_note_belongs_to_the_note(self):
        n = self.by["ADR-0001.R1.N1"]
        self.assertEqual((n["line_start"], n["line_end"]), (11, 15))
        self.assertIn("| is_reversible | false |", n["text"])
        self.assertEqual(self.by["ADR-0001.R1"]["text"], "1. Rule one has document types.")

    def test_paragraph_at_the_content_column_returns_to_the_rule(self):
        self.assertEqual(self.by["ADR-0001.R2"]["text"],
                         "2. Rule two.\n\n   Rule two text resumes after the note.")
        self.assertEqual(self.by["ADR-0001.R2.N1"]["text"], "   Note: a plain note on rule two.")

    def test_two_digit_rule_uses_its_own_content_column(self):
        self.assertEqual(self.by["ADR-0001.R10"]["text"], "10. Rule ten.\n\n    Rule ten text resumes here.")
        self.assertEqual((self.by["ADR-0001.R10.N1"]["line_start"], self.by["ADR-0001.R10.N1"]["line_end"]), (23, 23))

    def test_note_head_with_a_verb_phrase(self):
        n = self.by["ADR-0001.R10.N2"]
        self.assertEqual((n["line_start"], n["note_author"], n["note_date"]),
                         (27, "author's delegation, 2026-11-19", "2026-11-19"))
        self.assertIsNone(nfdocs.note_head("Note (a, 2026-11-19) and then a long clause that is not a head at all: x"))

    def test_inbound_supersession(self):
        self.assertEqual(self.by["ADR-0001.R2"]["superseded_by"], ["ADR-0002.R1"])
        self.assertEqual(self.by["ADR-0001.R10"]["superseded_by"], ["ADR-0002.R1"])
        # a reference inside a parenthesis before the verb is a citation, not the subject
        self.assertEqual(self.by["ADR-0001.R1"]["superseded_by"], [])
        self.assertEqual(self.by["ADR-0002.R2"]["superseded_by"], [])

    def test_widened_supersedes_phrases(self):
        self.assertEqual(self.by["ADR-0002.R2.N1"]["relation"], "supersedes")
        self.assertEqual(self.by["ADR-0002.R2.N2"]["relation"], "supersedes")
        self.assertEqual(nfdocs.find_phrases("the line becomes the origin", nfdocs.SUPERSEDES_PHRASES), [])

    def test_rule_of_adr_forms(self):
        self.assertEqual(nfdocs.find_refs("rule 12 of ADR-0070; rules 3 and 4 of [ADR-0033](x); ADR-0070, rule 9")[1],
                         ["ADR-0033.R3", "ADR-0033.R4", "ADR-0070.R9", "ADR-0070.R12"])

    def test_stable_key(self):
        n = self.by["ADR-0001.R10.N2"]
        self.assertEqual(nfdocs.stable_key(n["text"]), nfdocs.stable_key("  " + n["text"].replace(" ", "  ")))
        self.assertRegex(nfdocs.stable_key(n["text"]), r"^[0-9a-f]{12}$")
        self.assertNotEqual(nfdocs.stable_key(n["text"]), nfdocs.stable_key(self.by["ADR-0001.R10.N1"]["text"]))

    def test_coverage(self):
        for a in self.parsed:
            self.assertEqual(a["coverage"]["uncovered"], [], a["file"])


if __name__ == "__main__":
    unittest.main()
