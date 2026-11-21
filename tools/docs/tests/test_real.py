"""Sanity on the real ADRs and the committed rule index (S3 brief, Tests)."""

import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import nfdocs  # noqa: E402
import build_index  # noqa: E402


class RealAdrs(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.units, cls.parsed, cls.dangling = nfdocs.extract(nfdocs.DEFAULT_DOCS)

    def test_all_adrs_parsed(self):
        files = nfdocs.adr_files(nfdocs.DEFAULT_DOCS)
        self.assertGreaterEqual(len(files), 80)
        self.assertEqual(len(self.parsed), len(files))

    def test_rule_count(self):
        self.assertGreater(sum(1 for u in self.units if u["kind"] == "rule"), 1000)

    def test_every_adr_has_a_status(self):
        for a in self.parsed:
            self.assertIn(a["status"], ("accepted", "proposed", "superseded"), a["file"])

    def test_decision_coverage(self):
        uncovered = [x for a in self.parsed for x in a["coverage"]["uncovered"]]
        if uncovered:
            print("uncovered Decision lines:", uncovered[:50])
        self.assertEqual(uncovered, [])

    def test_unique_ids_and_parents(self):
        ids = [u["id"] for u in self.units]
        self.assertEqual(len(ids), len(set(ids)))
        idset = set(ids)
        for u in self.units:
            if u["kind"] == "note":
                self.assertIn(u["parent"], idset)

    def test_every_note_line_is_a_unit(self):
        # each line that opens with 'Note:' or 'Note (...):' starts exactly one note unit
        starts = {(u["source_file"], u["line_start"]) for u in self.units if u["kind"] == "note"}
        for path in nfdocs.adr_files(nfdocs.DEFAULT_DOCS):
            relp = nfdocs.rel(nfdocs.DEFAULT_DOCS, path)
            for n, line in enumerate(nfdocs.read(path).split("\n"), start=1):
                if nfdocs.note_head(line):
                    self.assertIn((relp, n), starts)


class RealIndex(unittest.TestCase):
    def test_committed_index_is_current_and_deterministic(self):
        rows1, _ = build_index.build(nfdocs.DEFAULT_DOCS)
        rows2, _ = build_index.build(nfdocs.DEFAULT_DOCS)
        content = build_index.to_csv(rows1)
        self.assertEqual(content, build_index.to_csv(rows2))
        self.assertEqual(nfdocs.read(nfdocs.DEFAULT_INDEX), content,
                         "docs/design/generated/rule-index.csv is stale: run tools/docs/build_index.py")


if __name__ == "__main__":
    unittest.main()
