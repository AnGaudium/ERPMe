"""Primary modules (tools/docs/adr-primary-module.csv) and dossier content (S3 pilot findings 1 and 2)."""

import os
import shutil
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import nfdocs  # noqa: E402
import build_index  # noqa: E402
import build_dossiers  # noqa: E402


class Primary(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows, cls.info = build_index.build(nfdocs.DEFAULT_DOCS)
        cls.by = {r["id"]: r for r in cls.rows}

    def test_every_adr_has_one_primary(self):
        adrs = {a["adr"] for a in self.info["parsed"]}
        self.assertEqual(set(self.info["primary"]), adrs)

    def test_bad_csv_is_refused(self):
        tmp = tempfile.mkdtemp()
        try:
            path = os.path.join(tmp, "p.csv")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write("adr,module,role\nADR-0001,process,primary\nADR-0001,ledger,primary\n"
                         "ADR-0002,nosuch,primary\n")
            with self.assertRaises(ValueError) as cm:
                nfdocs.load_primary(self.info["modules"], path, adrs=["ADR-0001", "ADR-0002", "ADR-0003"])
            msg = str(cm.exception)
            for part in ("two primary", "unknown module nosuch", "ADR-0003: no primary"):
                self.assertIn(part, msg)
        finally:
            shutil.rmtree(tmp)

    def test_no_unassigned(self):
        self.assertEqual([r["id"] for r in self.rows if "unassigned" in r["modules"].split(";")], [])

    def test_rules_in_their_primary_module(self):
        for uid in ("ADR-0070.R2", "ADR-0070.R8", "ADR-0070.R9", "ADR-0070.R15"):
            self.assertIn("quality", self.by[uid]["modules"].split(";"), uid)
        for r in self.rows:
            self.assertIn(r["primary_module"], r["modules"].split(";"), r["id"])
        self.assertEqual(self.by["ADR-0073.R1"]["primary_module"], "process")
        self.assertEqual(self.by["ADR-0021.R1"]["primary_module"], "inventory")


class Dossier(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="dossier-")
        cls.files, cls.stats = build_dossiers.build_all(nfdocs.DEFAULT_DOCS, cls.tmp)
        cls.cats, _ = nfdocs.load_catalogs(nfdocs.DEFAULT_DOCS)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp)

    def test_quality_dossier_has_sections_and_catalog_text(self):
        text = self.files["quality.md"]
        self.assertIn("### ADR-0070.R2 (rule, primary", text)
        self.assertIn("### ADR-0070.U (section, Documents updated)", text)
        units, _p, _d = nfdocs.extract(nfdocs.DEFAULT_DOCS)
        sec = "\n".join(u["text"] for u in units if u["id"] in ("ADR-0070.E", "ADR-0070.U"))
        found = 0
        for cat, kind in (("edge-cases", "ec"), ("invariants", "inv")):
            for n in nfdocs.OTHER_REFS[kind].findall(sec):
                key = next((k for k in self.cats[cat] if int(k.split("-")[1]) == int(n)), None)
                if key:
                    found += 1
                    self.assertIn(self.cats[cat][key][0], text, key)
        self.assertGreater(found, 0, "precondition: ADR-0070 .E/.U name a catalogued EC or INV")

    def test_process_dossier_flagged_and_no_unassigned(self):
        self.assertIn("Non-code module", self.files["process.md"])
        self.assertNotIn("unassigned.md", self.files)

    def test_primary_rules_counted(self):
        st = {s["module"]: s for s in self.stats}
        rows, _info = build_index.build(nfdocs.DEFAULT_DOCS)
        prim = sum(1 for r in rows if r["kind"] == "rule" and r["primary_module"] == "quality")
        self.assertEqual(st["quality"]["primary_rules"], prim)


if __name__ == "__main__":
    unittest.main()
