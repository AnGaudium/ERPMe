"""doc_lint, S4 review round 3 (R3-B1 to R3-B7, R3-S1 to R3-S8, notes N1, N2, N5): each test pins one finding and
fails on the lint before the round 3 fix. The cases are the reviewer's probes rebuilt on the generated spec of
lint_support.py, plus variants; ReviewProbesR3 runs the probe files themselves where the lab folder exists."""

import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))
import nfdocs  # noqa: E402
import build_index  # noqa: E402
import doc_lint  # noqa: E402
from lint_support import LintBase, MODULE, SHA, flagged_only, make_spec, superseding, write_index  # noqa: E402

ZWSP, WJ = "\u200b", "\u2060"


class R3(LintBase):

    def primary_rule(self, plain=True):
        return next(r for r in self.rules[1:] if MODULE in r["primary_module"] and not (plain and superseding(r)))

    def foreign_rule(self):
        return next(r for r in self.rules[1:] if MODULE not in r["primary_module"] and not superseding(r))

    def plain_note(self):
        return next(r for r in self.units if r["kind"] == "note" and not superseding(r) and not r["conflict_flag"])

    def statement_of(self, n, text=None):
        line = self.rdef(n, text)
        return line, line.split(". ", 1)[1].split(" Source: ")[0]

    def test_baseline_passes(self):
        self.assertEqual(self.run_lint(self.spec), [])

    # ------------------------------------------------------------ R3-B1: Source and trace, substance

    def test_b1_source_id_must_be_in_the_index_and_of_the_module(self):
        line = self.rdef(2)
        head = line.split(" Source: ")[0]
        f = self.run_lint(self.sub(line, head + " Source: ADR-0001.R1"))      # P0: an ID that is in no index
        self.assertIn("L7", self.checks(f))
        self.assertIn("R2: Source ADR-0001.R1 is not in the rule index", self.messages(f))
        other = next(r["id"] for r in self.rows if r["kind"] == "rule" and MODULE not in r["modules"]
                     and not any(r["id"] in u["superseded_by"] for u in self.units))
        f = self.run_lint(self.sub(line, line + f", `{other}`"))
        self.assertEqual(self.checks(f), ["L7"])
        self.assertIn(f"Source {other} is not a unit of module {MODULE}", self.messages(f))

    def test_b1_source_and_trace_agree_in_both_directions(self):
        a, b = [r for r in self.rules[1:] if not superseding(r)][:2]
        na, nb = self.rnum_of(a["id"]), self.rnum_of(b["id"])
        f = self.run_lint(self.set_where(a["id"], nb))      # the row points to an R-number that does not cite it
        self.assertIn("L1", self.checks(f))
        msg = self.messages(f)
        self.assertIn(f"trace row {a['id']} points to {nb}, whose Source does not cite it", msg)
        self.assertIn(f"{na} cites {a['id']} in its Source, but the trace row of {a['id']} does not point to {na}", msg)
        line = self.rdef(nb)
        f = self.run_lint(self.sub(line, line + f", `{a['id']}`"))    # a Source cites more than the trace gives it
        self.assertEqual(self.checks(f), ["L1"])
        self.assertIn(f"{nb} cites {a['id']} in its Source", self.messages(f))
        both = self.set_where(a["id"], f"{na}, {nb}", self.sub(line, line + f", `{a['id']}`"))
        self.assertEqual(self.run_lint(both), [])

    def test_b1_r_number_without_source(self):
        line = self.rdef(2)
        for bad in (line.split(" Source: ")[0], line.split(" Source: ")[0] + " Source: the ADR"):
            f = self.run_lint(self.sub(line, bad))
            self.assertIn("R2 has no 'Source:' with a unit ID", self.messages(f), bad)

    def test_b1_source_note_shorthand(self):
        note = next(r for r in self.units if r["kind"] == "note" and r["parent"] in {x["id"] for x in self.rules[1:]})
        line = self.rdef(self.rnum_of(note["id"]))
        short = line.replace(f"`{note['id']}`", "." + note["id"].rsplit(".", 1)[1])
        self.assertNotEqual(short, line)
        self.assertEqual(self.run_lint(self.sub(line, short)), [])

    def test_b1_junk_and_placeholder_statements(self):
        line, _st = self.statement_of(2)
        src = " Source: " + line.split(" Source: ")[1]
        for junk in ("." * 32, "&nbsp;" * 6 + " &#160;&amp;", "<br>" * 8, "*** --- ___ ***", "1234 5678 9012 3456",
                     "xq zv kj qp wz xk vq jx zq",                       # no word of the ADRs
                     "TBD: to be compiled from the source rules later on.", "The rule is to be written by the owner.",
                     "The behaviour is as stated in the source for this module.", "See the source for the behaviour.",
                     "Lorem ipsum dolor sit amet, consectetur adipiscing elit."):
            f = self.run_lint(self.sub(line, "R2. " + junk + src))
            self.assertIn("L1", self.checks(f), junk)
            self.assertRegex(self.messages(f), r"R2 (has no real statement|holds the placeholder)", junk)

    def test_b1_short_real_statements_pass(self):
        r = self.rules[1]
        line, _st = self.statement_of(2)
        src = " Source: " + line.split(" Source: ")[1]
        kept = sorted(doc_lint.identifiers(self.texts[r["id"]]))
        name = f"`{kept[0]}`" if kept else "`event`"
        for ok in (f"{name} is append-only.", f"The factor of {name} is exact.", f"A `TODO` state of {name} exists."):
            self.assertEqual(self.run_lint(self.sub(line, "R2. " + ok + src)), [], ok)

    def test_b1_identifier_retention(self):
        rich = [r for r in self.rules[1:] if len(doc_lint.identifiers(self.texts[r["id"]])) >= 3
                and not superseding(r) and not any(superseding(n) for n in self.units if n["parent"] == r["id"])]
        self.assertTrue(rich, "precondition: a rule with 3 or more identifiers")
        r = rich[0]
        line, st = self.statement_of(self.rnum_of(r["id"]))
        self.assertIn("naming `", st)
        bare = re.sub(r", naming `[^`]+`,", "", line)
        f = self.run_lint(self.sub(line, bare))
        self.assertEqual(self.checks(f), ["L11"])
        self.assertIn(r["id"], f[0]["message"])
        unticked = line.replace("`", "", 2)          # the name without backticks is not kept
        self.assertEqual(self.checks(self.run_lint(self.sub(line, unticked))), ["L11"])
        f, info = self.run_lint(self.spec, with_info=True)
        rt = list(info["retention"].values())[0]
        self.assertGreater(rt["identifiers"], rt["kept"])
        self.assertGreater(rt["kept"], 0)
        self.assertGreater(rt["size_ratio"], 0)

    def test_b1_retention_spares_superseded_rules(self):
        sup = next(r for r in self.rules[1:] if superseding(r))
        line = self.rdef(self.rnum_of(sup["id"]))
        bare = re.sub(r", naming `[^`]+`,", "", line)
        self.assertNotIn("L11", self.checks(self.run_lint(self.sub(line, bare) if bare != line else self.spec)))

    def test_b1_lettered_r_numbers(self):
        defined = {k: None for k in ("49", "50a", "50b", "50c", "51", "52")}
        self.assertEqual(doc_lint.expand_where_r("R50a-R50c", defined), (["50a", "50b", "50c"], []))
        self.assertEqual(doc_lint.expand_where_r("R50", defined), (["50a", "50b", "50c"], []))
        self.assertEqual(doc_lint.expand_where_r("R49-R51", defined), (["49", "50a", "50b", "50c", "51"], []))
        self.assertEqual(doc_lint.expand_where_r("R50b-R51", defined), (["50b", "50c", "51"], []))
        self.assertEqual(doc_lint.expand_where_r("R50d", defined), ([], ["50d"]))
        self.assertEqual(doc_lint.expand_where_r("R52-R54", defined), (["52"], ["53", "54"]))
        self.assertIsNone(doc_lint.expand_where_r("Purpose", defined))

    def test_b1_coverage_counts_only_cited_rules(self):
        # every Source cites one unrelated unit of the module: the rows still point to R-numbers, nothing is covered
        text = self.spec
        note = self.plain_note()
        for r in self.rules:
            line = self.rdef(self.rnum_of(r["id"]), text)
            text = self.sub(line, line.split(" Source: ")[0] + f" Source: `{note['id']}`", text)
        self.assertIn("0 of ", self.messages(self.run_lint(text)))

    # ------------------------------------------------------------ R3-B2: accepted law under Proposed

    def test_b2_accepted_law_under_proposed(self):
        r = self.primary_rule()
        line = self.rdef(self.rnum_of(r["id"]))
        moved = self.sub(line + "\n", "").replace("## Proposed (not law)\n\nNone.", "## Proposed (not law)\n\n" + line)
        f = self.run_lint(moved)
        self.assertEqual(self.checks(f), ["L3"])
        self.assertIn(f"trace row {r['id']} (accepted) points to {self.rnum_of(r['id'])}, stated as proposed",
                      self.messages(f))

    # ------------------------------------------------------------ R3-B3: notes and headings

    def test_b3_note_on_a_heading(self):
        note = self.plain_note()
        dropped = self.drop_source(note["id"])
        for bad in ("Topic", "Rules", "Purpose", "Settlement topic", "Topic, Purpose"):
            f = self.run_lint(self.set_where(note["id"], bad, dropped))
            self.assertEqual(self.checks(f), ["L1"], bad)
        n = self.rnum_of(note["id"])
        self.assertEqual(self.run_lint(self.set_where(note["id"], f"{n}, Topic")), [])

    def test_b3_heading_must_exist_and_unknown_where_is_a_finding(self):
        section = next(r for r in self.units if r["kind"] == "section")
        self.assertEqual(self.rnum_of(section["id"]), "Purpose")
        self.assertEqual(self.run_lint(self.set_where(section["id"], "Topic")), [])
        for bad in ("Settlement topic", "see the rules above", "Purpose, somewhere"):
            f = self.run_lint(self.set_where(section["id"], bad))
            self.assertEqual(self.checks(f), ["L1"], bad)
            self.assertIn("is not an R-number, ref:, an existing heading", self.messages(f))

    # ------------------------------------------------------------ R3-B4: ref targets

    def test_b4_ref_must_name_the_unit_or_its_primary_module(self):
        r = self.foreign_rule()
        unrelated = next(x["id"] for x in self.rows if x["kind"] == "rule" and x["adr"] != r["adr"]
                         and x["id"] not in r["xrefs_rules"])
        wrong_module = next(m for m in ("purchasing", "ledger", "sales") if m not in r["primary_module"])
        for bad in (f"ref: {unrelated}", f"ref: {wrong_module} R-1", "ref: process R-1", "ref: cross R-1"):
            if bad.split()[1] in r["primary_module"]:
                continue
            f = self.run_lint(self.as_ref(r, bad))
            self.assertEqual(self.checks(f), ["L1"], bad)
            self.assertIn(f"trace row {r['id']}: '{bad}'", self.messages(f))
        self.assertEqual(self.run_lint(self.as_ref(r, f"ref: {r['id']}")), [])
        self.assertEqual(self.run_lint(self.as_ref(r, f"ref: {r['primary_module'][0]} R-1")), [])

    def test_b4_ref_is_checked_against_the_other_spec_beside(self):
        r = self.foreign_rule()
        mod = r["primary_module"][0]
        text = self.as_ref(r, f"ref: {mod} R-7")
        other = os.path.join(self.tmp, "beside", f"{mod}.md")
        for body, want in ((f"## Rules\n\nR7. The other module states this law here. Source: {r['id']}\n", None),
                           ("## Rules\n\nR7. The other module states another law. Source: ADR-0001.D0\n",
                            f"the Source of {mod} R7 does not cite {r['id']}"),
                           ("## Rules\n\nR8. Another rule. Source: ADR-0001.D0\n", f"defines no R7")):
            self.write(body, f"beside/{mod}.md")
            f = self.run_lint(text, name="beside/spec.md")
            if want is None:
                self.assertEqual(f, [])
            else:
                self.assertEqual(self.checks(f), ["L1"])
                self.assertIn(want, self.messages(f))
        os.remove(other)

    # ------------------------------------------------------------ R3-B5: nothing measured, no PASS

    def test_b5_cross_and_process_are_refused(self):
        path = self.write(self.spec, "b5.md")
        for module in ("cross", "process"):
            with self.assertRaises(SystemExit):
                doc_lint.lint([path], module, self.index, nfdocs.DEFAULT_DOCS, SHA)
            rc, out, err = self.run_cli([path, "--module", module, "--index", self.index, "--index-commit", SHA])
            self.assertEqual((rc, out), (2, ""))
            self.assertIn(module, err)
        rc, out, _err = self.run_cli([path, "--module", "process", "--allow-process", "--index", self.index,
                                      "--index-commit", SHA])
        self.assertEqual(rc, 1)             # linted (and it fails: the spec is the outbox one)
        self.assertTrue(out.startswith("LINT FAIL"))

    def test_b5_a_module_primary_for_no_rule_is_refused(self):
        idx = self.edited_index("index-noprimary.csv", lambda r: r.update(
            primary_module="ledger") if MODULE in r["primary_module"].split(";") else None)
        with self.assertRaises(SystemExit):
            self.run_lint(self.spec, index=idx)

    def test_b5_measured_counts_and_empty_measures(self):
        path = self.write(self.spec, "b5m.md")
        rc, out, _err = self.run_cli([path, "--module", MODULE, "--index", self.index, "--index-commit", SHA])
        lines = out.split("\n")
        self.assertEqual((rc, lines[0]), (0, "LINT PASS findings=0"))
        self.assertEqual(lines[1], f"measured: module={MODULE} files=1 units={len(self.units)} "
                                   f"rules={len(self.rules)} primary_rules="
                                   f"{sum(1 for r in self.rules if MODULE in r['primary_module'])} "
                                   f"notes={sum(1 for r in self.units if r['kind'] == 'note')} "
                                   f"sections={sum(1 for r in self.units if r['kind'] == 'section')} "
                                   f"tables={len(self.tables)} r_numbers={len(self.rules)} "
                                   f"trace_rows={len(self.units)} traced_units={len(self.units)}")
        head, _tail = self.spec.split("| --- | --- |\n")
        f = self.run_lint(head + "| --- | --- |\n")
        self.assertIn("the trace table is empty", self.messages(f))
        rules = "\n".join(l for l in self.spec.split("\n") if not l.startswith("R") or ". Statement" not in l)
        self.assertIn("no R-number is defined", self.messages(self.run_lint(rules)))

    # ------------------------------------------------------------ R3-B6: every Conflicts line is read

    def test_b6_every_conflicts_line_is_an_entry_or_a_finding(self):
        a, b, c, d = [r["id"] for r in self.units if r["kind"] == "note" and not superseding(r)
                      and not r["conflict_flag"]][:4]
        reasons = ["the later note names the period and that reading is kept",
                   "hard floor exception contradicts the rule text and the note applies",
                   "approver role against approval stage where the later note wins",
                   "values move to pools in the later note and the rule text is stale"]
        forms = [f"CONFLICT: {a} {reasons[0]}", f"**CONFLICT** {b}: {reasons[1]}", f"| CONFLICT | {c} | {reasons[2]} |",
                 f"- CONFLICT `{d}`: {reasons[3]}"]
        text = self.sub("\n\n## Proposed (not law)", "\n" + "\n".join(forms) + "\n\n## Proposed (not law)")
        f, info = self.run_lint(text, with_info=True)
        self.assertEqual(f, [])
        for uid, reason in zip((a, b, c, d), reasons):
            self.assertIn(f"CONFLICT {uid}: {reason}", info["review"])
        for bad in (f"Conflict {a}: {reasons[0]}", f"conflict: {a} {reasons[0]}", f"CONFLICT ADR-0013 rule 5: {reasons[0]}",
                    "The compiler found nothing else worth a line here.", f"| CONFLICT |\n| x | {a} | y |",
                    "None."):
            f = self.run_lint(self.sub("\n\n## Proposed (not law)", "\n\n" + bad + "\n\n## Proposed (not law)"))
            self.assertEqual(self.checks(f), ["L5"], bad)

    def test_b6_wrapped_entry_and_entry_outside_conflicts(self):
        a = self.plain_note()["id"]
        wrapped = f"CONFLICT {a}: the later note names the period\nand that reading is kept in the statement"
        f, info = self.run_lint(self.sub("\n\n## Proposed (not law)", "\n" + wrapped + "\n\n## Proposed (not law)"),
                                with_info=True)
        self.assertEqual(f, [])
        self.assertIn(f"CONFLICT {a}: the later note names the period and that reading is kept in the statement",
                      info["review"])
        outside = self.sub("## Invariants\n", f"## Invariants\n\nCONFLICT {a}: the later note names the period kept\n")
        self.assertEqual(self.checks(self.run_lint(outside)), ["L5"])

    def test_b6_none_alone_is_accepted(self):
        idx = self.edited_index("index-calm.csv", lambda r: r.update(
            relation="amends" if r["kind"] == "note" else "", superseded_by="", conflict_flag="", conflict_phrases="",
            conflict_markers=""))
        spec = make_spec(build_index.read_index(idx), self.owners, self.cats, MODULE, self.texts)
        self.assertIn("## Conflicts\n\nNone.\n", spec)
        self.assertEqual(self.run_lint(spec, index=idx), [])

    # ------------------------------------------------------------ R3-B7: superseded rules

    def test_b7_conflict_names_the_superseding_id_and_the_source_cites_it(self):
        sup = next(r for r in self.rules[1:] if r["superseded_by"])
        gov = sup["superseded_by"][0]
        n = self.rnum_of(sup["id"])
        entry = next(l for l in self.spec.split("\n") if l.startswith(f"CONFLICT {sup['id']}:"))
        # S6a: 'R1 governs' and the old text; the reason names no superseding ID
        f = self.run_lint(self.sub(entry, f"CONFLICT {sup['id']}: {n} governs this case as written in the spec"))
        self.assertEqual(self.checks(f), ["L10"])
        self.assertIn(f"names {gov}", f[0]["message"])
        # the reason names it, but the R-number's Source does not cite it
        line = self.rdef(n)
        f = self.run_lint(self.sub(line, line.replace(f", `{gov}`", "")))
        self.assertEqual(self.checks(f), ["L10"])
        self.assertIn(f"{n} states {sup['id']}, which {gov} supersedes, but its Source does not cite {gov}",
                      f[0]["message"])
        # the same form with the ADR written in prose is read
        adr, k = gov.split(".R")
        if "." not in k:
            prose = entry.replace(gov, f"{adr} rule {k}")
            self.assertEqual(self.run_lint(self.sub(entry, prose)), [])

    def test_b7_superseded_rules_are_listed_for_the_spot_check(self):
        path = self.write(self.spec, "b7.md")
        _rc, out, _err = self.run_cli([path, "--module", MODULE, "--index", self.index, "--index-commit", SHA])
        sups = [r for r in self.rules if superseding(r)]
        self.assertIn(f"SUPERSEDED RULES (read each; template acceptance step 2): {len(sups)}", out)
        for r in sups:
            self.assertRegex(out, rf"\n  {r['id']} superseded by .*; Where R\d+; entry: CONFLICT")
        template = nfdocs.read(os.path.join(nfdocs.DEFAULT_DOCS, "design", "compiled-spec-template.md"))
        self.assertIn("SUPERSEDED RULES", template)

    # ------------------------------------------------------------ R3-S1: typed counts

    def test_s1_fresh_count_forms(self):
        for bad in ("The module owns **16** tables.", "The module owns 16 *tables*.", "It is a 16-table module.",
                    "It has 16 owned-tables.", f"It has 16{ZWSP} tables.", "It has 16 [tables](#entities-and-tables).",
                    "Owned tables (16) are listed below.", "Tables owned — 16.", "It registers XVI commands.",
                    "It owns `16` tables.", "It has 16<br>tables.", f"It has 16{WJ}tables.", "It owns __16__ tables.",
                    "Commands - 12.", "Rules owned (twelve) follow.", "It has III settings."):
            self.assertEqual(self.checks(self.run_lint(self.sub("in plain words.", bad))), ["L4"], bad)
        row = self.sub("## Invariants", "| 16 | owned tables |\n\n## Invariants")
        self.assertEqual(self.checks(self.run_lint(row)), ["L4"])

    def test_s1_names_and_citations_are_not_counts(self):
        for ok in ("See rules 22–23 of that topic.", "The pack `xx_core_small@1`, which carries every edge case, runs.",
                   "Due `days:5`, resolved by the owner of all rules.", "Two rows are in setting-presets.csv here.",
                   "Phase II rules apply later.", "The `status_change` task (1) moves stock.",
                   "| 1 | `INV-830` | the released revision and its columns never change |"):
            self.assertEqual(self.run_lint(self.sub("in plain words.", ok)), [], ok)

    # ------------------------------------------------------------ R3-S2: proposed citation forms

    def test_s2_proposed_citation_forms(self):
        victim = next(r["id"] for r in self.rules[1:] if not superseding(r) and ".L" not in r["id"])
        n = self.rnum_of(victim)
        idx = self.edited_index("index-proposed-r3.csv",
                                lambda r: r.update(status="proposed") if victim in (r["id"], r["parent"]) else None)
        line = self.rdef(n)
        fixed = self.sub(line, line.replace(f"{n}. ", f"{n}. [proposed] ", 1))
        self.assertEqual(self.run_lint(fixed, index=idx), [])
        adr, k = victim.split(".R")
        other = self.rdef(1 if n != "R1" else 2, fixed)
        for form in (f"{adr} (rule {k})", f"{adr.replace('-', ' ')} rule {k}", f"rule {k} in {adr}", f"{adr} §{k}",
                     f"{adr} Rule {k}", f"Rule {k} of {adr}"):
            prose = self.sub(other, other.replace(" in plain words", f" as {form} says"), fixed)
            self.assertEqual(self.checks(self.run_lint(prose, index=idx)), ["L3"], form)
        self.assertEqual(doc_lint.unit_ids_in("ADR-0070 rules 12 through 14"),
                         {"ADR-0070.R12", "ADR-0070.R13", "ADR-0070.R14"})

    def test_s2_proposed_decision_text_on_a_law_heading(self):
        section = next(r for r in self.units if r["kind"] == "section")
        idx = self.edited_index("index-proposed-section.csv",
                                lambda r: r.update(status="proposed") if r["id"] == section["id"] else None)
        f = self.run_lint(self.spec, index=idx)
        self.assertEqual(self.checks(f), ["L3"])
        self.assertIn("points to heading 'Purpose' outside", f[0]["message"])
        self.assertEqual(self.run_lint(self.set_where(section["id"], "Proposed (not law)"), index=idx), [])

    # ------------------------------------------------------------ R3-S3: duplicate R-numbers, chunk sets

    def chunks(self, first="1 of 2", second="2 of 2"):
        head, tail = self.spec.split("## Invariants", 1)
        front = "\n".join(self.spec.split("\n")[:3])
        trace_head = "## Trace\n\n| Source | Where |\n| --- | --- |\n"
        c1 = head.replace("Chunk: whole", f"Chunk: {first}") + trace_head
        c2 = (front + "\n## Purpose\n\nChunk two.\n\n## Invariants" + tail).replace("Chunk: whole", f"Chunk: {second}")
        return self.write(c1, "c1.md"), self.write(c2, "c2.md")

    def lint_files(self, paths, **kw):
        return doc_lint.lint(paths, MODULE, self.index, nfdocs.DEFAULT_DOCS, SHA, **kw)

    def test_s3_duplicate_r_number(self):
        line = self.rdef(2)
        f = self.run_lint(self.sub(line, line + "\n\nR2. A second statement under the same number, by mistake."))
        self.assertEqual(self.checks(f), ["L1"])
        self.assertIn("R2 is defined twice", f[0]["message"])
        p1, p2 = self.chunks()
        with open(p2, encoding="utf-8") as fh:
            c2 = fh.read()
        self.write(c2.replace("## Invariants", "## Rules\n\n" + line + "\n\n## Invariants", 1), "c2.md")
        f, _ = self.lint_files([p1, p2])
        self.assertEqual(self.checks(f), ["L1"])
        self.assertIn("R2 is defined twice", f[0]["message"])

    def test_s3_chunk_numbering(self):
        self.assertEqual(self.lint_files(list(self.chunks()))[0], [])
        for first, second, want in (("1 of 2", "1 of 2", "is given by 2 files"), ("1 of 2", "3 of 2", "not within 1..n"),
                                    ("1 of 2", "2 of 3", "disagree on n"), ("1 of 2", "whole", "Chunk 'whole' in a set")):
            f, _ = self.lint_files(list(self.chunks(first, second)))
            self.assertIn("L0", self.checks(f), (first, second))
            self.assertIn(want, self.messages(f), (first, second))

    def natural_chunks(self):
        """Two chunks cut inside `## Rules`: each holds its rules, their trace rows and their Conflicts entries."""
        lines = self.spec.split("\n")
        front, k = lines[:3], len(self.rules) // 2
        first = {f"R{i}" for i in range(1, k + 1)}

        def sec(name):
            a = lines.index(f"## {name}")
            b = next((i for i in range(a + 1, len(lines)) if lines[i].startswith("## ")), len(lines))
            return lines[a:b]

        rows = [l for l in sec("Trace") if l.startswith("| `")]
        in_a = {l.split("`")[1] for l in rows if l.split("|")[2].strip() in first | {"Purpose"}}
        defs = [l for l in sec("Rules") if l.startswith("R")]
        entries = [l for l in sec("Conflicts") if l.startswith(("CONFLICT", "FALSE-POSITIVE"))]

        def chunk(n, a):
            mine = lambda uid: (uid in in_a) == a      # noqa: E731
            body = front + sec("Purpose")
            if a:
                body += sec("Entities and tables") + sec("Commands and queries")
            body += ["## Rules", "", "### Topic", ""] + [l for l in defs if (l.split(".")[0] in first) == a] + [""]
            if not a:
                body += sec("Invariants") + sec("Edge cases") + sec("Settings") + sec("UI annotations")
            body += ["## Conflicts", ""] + ([l for l in entries if mine(l.split()[1].rstrip(":"))] or ["None."]) + [""]
            if not a:
                body += sec("Proposed (not law)")
            body += ["## Trace", "", "| Source | Where |", "| --- | --- |"] + [l for l in rows if mine(l.split("`")[1])]
            return self.write("\n".join(body).replace("Chunk: whole", f"Chunk: {n} of 2") + "\n", f"n{n}.md")

        return chunk(1, True), chunk(2, False)

    def test_s3_lone_chunk_is_partial(self):
        p1, p2 = self.natural_chunks()
        self.assertEqual(self.lint_files([p1, p2])[0], [])
        f, info = self.lint_files([p1])
        self.assertEqual(self.checks(f), ["L0"])                 # one finding: the set is incomplete
        self.assertEqual(len(f), 1)
        self.assertIn("give --partial", f[0]["message"])
        self.assertIn("NOTICE", info["notice"])
        f, info = self.lint_files([p1], partial=True)
        self.assertEqual(f, [])
        self.assertGreater(info["deferred"]["units not traced in these chunks"], 0)
        rc, out, _err = self.run_cli([p1, "--module", MODULE, "--index", self.index, "--index-commit", SHA])
        self.assertEqual((rc, out.split("\n")[0]), (1, "LINT FAIL findings=1"))
        rc, out, _err = self.run_cli([p1, "--module", MODULE, "--index", self.index, "--index-commit", SHA, "--partial"])
        self.assertEqual(rc, 0)
        self.assertRegex(out.split("\n")[0], r"^LINT PARTIAL findings=0 deferred=\d+$")
        self.assertNotIn("LINT PASS", out)
        whole = self.write(self.spec, "whole.md")                # --partial on a complete file changes nothing
        rc, out, _err = self.run_cli([whole, "--module", MODULE, "--index", self.index, "--index-commit", SHA,
                                      "--partial"])
        self.assertEqual((rc, out.split("\n")[0]), (0, "LINT PASS findings=0"))

    def test_s3_partial_still_checks_the_chunk_itself(self):
        p1, p2 = self.natural_chunks()
        self.assertEqual(self.lint_files([p2], partial=True)[0], [])
        with open(p1, encoding="utf-8") as fh:
            c1 = fh.read()
        line = self.rdef(2)
        self.write(c1.replace(line, line.split(" Source: ")[0]), "n1.md")
        f, _ = self.lint_files([p1], partial=True)
        self.assertEqual(self.checks(f), ["L1"])
        self.assertIn("R2 has no 'Source:'", self.messages(f))

    def test_s3_same_file_twice(self):
        path = self.write(self.spec, "twice.md")
        rc, out, err = self.run_cli([path, path, "--module", MODULE, "--index", self.index, "--index-commit", SHA])
        self.assertEqual((rc, out), (2, ""))
        self.assertIn("twice", err)

    # ------------------------------------------------------------ R3-S4: what a reader sees; required content

    def test_s4_owned_names_only_in_reads_or_in_a_comment(self):
        t = self.tables[0]
        reads = self.sub(f"- `{t}`\n", "").replace("## Rules\n", f"## Rules\n\nReads: `{t}`, `ledger`\nand more.\n", 1)
        f = self.run_lint(reads)
        self.assertEqual(self.checks(f), ["L2"])
        self.assertIn(f"`{t}`", f[0]["message"])
        comment = self.sub(f"- `{t}`\n", f"<!-- `{t}` -->\n")
        self.assertEqual(self.checks(self.run_lint(comment)), ["L2"])
        key = next(c.split(":", 1)[1] for c in self.cat_rows)
        self.assertEqual(self.checks(self.run_lint(self.sub(f"- `{key}`\n", f"Reads: `{key}`\n"))), ["L2"])

    def test_s4_invisible_characters_do_not_hide_or_fake_text(self):
        t = self.tables[0]
        self.assertEqual(self.run_lint(self.sub(f"- `{t}`", f"- `{t[:3]}{ZWSP}{t[3:]}`")), [])
        line = self.rdef(2)
        hidden = line.replace("R2. ", f"R2.{ZWSP} ")
        self.assertEqual(self.run_lint(self.sub(line, hidden)), [])
        junk = "R2. " + (ZWSP + WJ + "\u00a0") * 20 + " Source: " + line.split(" Source: ")[1]
        self.assertIn("R2 has no real statement", self.messages(self.run_lint(self.sub(line, junk))))

    def test_s4_sections_have_content(self):
        for old, new in (("None (headless step).", ""), ("None (headless step).", "None."),
                         ("None (headless step).", "<!-- later -->"), ("None (headless step).", "### Later"),
                         ("None (the test module registers nothing).", "None")):
            f = self.run_lint(self.sub(old, new))
            self.assertEqual(self.checks(f), ["L0"], new)
        entities = "\n".join(f"- `{t}`" for t in self.tables)
        f = self.run_lint(self.sub(entities, "None (see the DDL file)."))
        self.assertIn("says None, but the module owns", self.messages(f))
        purpose = next(l for l in self.spec.split("\n") if l.startswith("The module owns"))
        f = self.run_lint(self.sub(purpose, "<!-- " + purpose.replace("<!--", "").replace("-->", "") + " -->"))
        self.assertEqual(self.checks(f), ["L0"])
        self.assertIn("section '## Purpose' is empty", f[0]["message"])
        for ok in ("None: headless step.", "None. The module is headless."):
            self.assertEqual(self.run_lint(self.sub("None (headless step).", ok)), [], ok)

    def test_n2_front_matter_in_a_comment(self):
        lines = self.spec.split("\n")
        hidden = "\n".join(["<!--"] + lines[:2] + ["-->"] + lines[2:])
        f = self.run_lint(hidden)
        self.assertEqual(self.checks(f), ["L0"])
        self.assertIn("front matter field 'Module:' is missing", self.messages(f))

    # ------------------------------------------------------------ R3-S5: the index commit

    def test_s5_index_commit_is_verified(self):
        repo = tempfile.mkdtemp(prefix="doclint-git-")
        try:
            def git(*args):
                return subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@example.invalid"] + list(args),
                                      cwd=repo, capture_output=True, text=True, check=True).stdout.strip()
            idx = os.path.join(repo, "rule-index.csv")
            write_index(idx, self.raw)
            git("init", "-q")
            git("add", "-A")
            git("commit", "-qm", "index")
            sha = git("log", "-1", "--format=%H")
            self.patch.stop()
            try:
                self.assertEqual(doc_lint.index_state(idx, nfdocs.DEFAULT_DOCS), (sha, []))
                self.assertEqual(doc_lint.index_state(idx, nfdocs.DEFAULT_DOCS, sha[:10]), (sha, []))
                spec = self.spec.replace(SHA[:9], sha[:9])
                path = self.write(spec, "s5.md")
                self.assertEqual(doc_lint.lint([path], MODULE, idx, nfdocs.DEFAULT_DOCS)[0], [])
                # a string that is no commit
                f, _ = doc_lint.lint([path], MODULE, idx, nfdocs.DEFAULT_DOCS, sha[:7] + "0000")
                self.assertEqual(self.checks(f), ["L0"])
                self.assertIn("is not a commit", f[0]["message"])
                rc, out, _err = self.run_cli([path, "--module", MODULE, "--index", idx, "--index-commit", "c9d57fe0000"])
                self.assertEqual((rc, out.split("\n")[0]), (1, "LINT FAIL findings=1"))
                # the front matter names another commit
                f, _ = doc_lint.lint([self.write(self.spec, "s5b.md")], MODULE, idx, nfdocs.DEFAULT_DOCS)
                self.assertEqual(self.checks(f), ["L0"])
                # the index differs from its committed version
                with open(idx, "a", encoding="utf-8") as fh:
                    fh.write("\n")
                f, _ = doc_lint.lint([path], MODULE, idx, nfdocs.DEFAULT_DOCS)
                self.assertEqual(self.checks(f), ["L0"])
                self.assertIn("the index differs from its version in commit", f[0]["message"])
                rc, out, _err = self.run_cli([path, "--module", MODULE, "--index", idx])
                self.assertEqual((rc, out.split("\n")[0]), (1, "LINT FAIL findings=1"))
            finally:
                self.patch.start()
        finally:
            shutil.rmtree(repo)

    def test_s5_stable_key_mismatch_is_listed_and_strict_fails(self):
        note = next(r for r in self.units if r["kind"] == "note")
        row = self.row_of(note["id"])
        bad = self.sub(row, row.replace(f"`{note['id']}`", f"`{note['id']}` #000000000000"))
        f, info = self.run_lint(bad, with_info=True)
        self.assertEqual(f, [])
        self.assertEqual(len(info["key_mismatches"]), 1)
        path = self.write(bad, "s5k.md")
        args = [path, "--module", MODULE, "--index", self.index, "--index-commit", SHA]
        rc, out, _err = self.run_cli(args)
        self.assertEqual(rc, 0)
        self.assertIn("STABLE-KEY MISMATCHES (the text behind a trace row changed or moved): 1", out)
        rc, out, _err = self.run_cli(args + ["--strict"])
        self.assertEqual((rc, out.split("\n")[0]), (1, "LINT FAIL findings=1"))

    # ------------------------------------------------------------ R3-S6: conflict entries

    def test_s6_a_flagged_note_needs_its_own_entry(self):
        flagged = next(r for r in self.units if flagged_only(r))
        entry = next(l for l in self.spec.split("\n") if l.startswith(f"FALSE-POSITIVE {flagged['id']}:"))
        on_parent = f"CONFLICT {flagged['parent']}: the later note of the rule governs and the statement follows it"
        f = self.run_lint(self.sub(entry, on_parent))
        self.assertEqual(self.checks(f), ["L5"])
        self.assertIn(f"{flagged['id']} (conflict flag", f[0]["message"])

    def test_s6_open_needs_a_real_open_question(self):
        note = next(r for r in self.units if r["kind"] == "note" and superseding(r))
        entry = next(l for l in self.spec.split("\n") if l.startswith(f"CONFLICT {note['id']}:"))
        questions = doc_lint.docs_model(nfdocs.DEFAULT_DOCS)["questions"]
        self.assertGreater(len(questions["open"]), 10)
        q = questions["open"][0]
        for bad in ("OQ-99999", "see OQ-123 for the question", "open-questions.md#no-such-heading-anywhere",
                    'the author is asked "whether this text exists nowhere in the file at all"',
                    f'"{q[:12]}"'):
            f = self.run_lint(self.sub(entry, f"OPEN {note['id']}: {bad}"))
            self.assertEqual(self.checks(f), ["L5"], bad)
        anchor = sorted(questions["anchors"])[1]
        for ok in (f'"{q[:40]}"', f'asked in open-questions.md#{anchor}: "{q[5:60]}"', f"“{q[:30]}”"):
            self.assertEqual(self.run_lint(self.sub(entry, f"OPEN {note['id']}: {ok}")), [], ok)

    def test_s6_reason_quality_and_reuse(self):
        flagged = next(r for r in self.units if flagged_only(r))
        entry = next(l for l in self.spec.split("\n") if l.startswith(f"FALSE-POSITIVE {flagged['id']}:"))
        for bad in ("rudfuxjdxkxwqnq vgjjspqmsbphxzmnvflrwyvz", "xlcovqdyfq mlpxapbjwtssmuffqhaygrrhmqlslz ok ok",
                    "........................................", "the the the the the the the the the"):
            f = self.run_lint(self.sub(entry, f"FALSE-POSITIVE {flagged['id']}: {bad}"))
            self.assertEqual(self.checks(f), ["L5"], bad)
        notes = [r["id"] for r in self.units if r["kind"] == "note" and not superseding(r)
                 and not r["conflict_flag"]][:4]
        near = "\n".join(f"CONFLICT {n}: R{k} governs this case as written in the spec" for k, n in enumerate(notes, 1))
        f = self.run_lint(self.sub("\n\n## Proposed (not law)", "\n" + near + "\n\n## Proposed (not law)"))
        self.assertEqual(self.checks(f), ["L5"])
        self.assertIn("one CONFLICT reason (or a near copy) serves 4 entries", f[0]["message"])

    def test_s6_false_positive_only_for_flagged_notes(self):
        note = self.plain_note()
        extra = f"FALSE-POSITIVE {note['id']}: the note adds a column name and contradicts nothing"
        f = self.run_lint(self.sub("\n\n## Proposed (not law)", "\n" + extra + "\n\n## Proposed (not law)"))
        self.assertEqual(self.checks(f), ["L5"])
        self.assertIn("carries no conflict flag", f[0]["message"])
        ok = extra.replace("FALSE-POSITIVE", "CONFLICT")       # a conflict the compiler found itself
        self.assertEqual(self.run_lint(self.sub("\n\n## Proposed (not law)", "\n" + ok + "\n\n## Proposed (not law)")), [])
        foreign = next(r["id"] for r in self.rows if MODULE not in r["modules"])
        bad = f"CONFLICT {foreign}: the later note of that rule governs and nothing is stated here"
        f = self.run_lint(self.sub("\n\n## Proposed (not law)", "\n" + bad + "\n\n## Proposed (not law)"))
        self.assertEqual(self.checks(f), ["L5"])
        self.assertIn("not a unit of module", f[0]["message"])

    def test_s6_review_list_counts(self):
        path = self.write(self.spec, "s6.md")
        _rc, out, _err = self.run_cli([path, "--module", MODULE, "--index", self.index, "--index-commit", SHA])
        entries = [l for l in self.spec.split("\n") if l.startswith(("CONFLICT ", "FALSE-POSITIVE ", "OPEN "))]
        c = sum(1 for l in entries if l.startswith("CONFLICT "))
        fp = sum(1 for l in entries if l.startswith("FALSE-POSITIVE "))
        self.assertIn(f"REVIEW LIST ({len(entries)} entries for the chief architect; template acceptance step 3): "
                      f"CONFLICT={c} FALSE-POSITIVE={fp} OPEN=0", out)

    # ------------------------------------------------------------ R3-S7: foreign units

    def test_s7_trace_row_of_another_module(self):
        foreign = next(r["id"] for r in self.rows if r["kind"] == "rule" and MODULE not in r["modules"])
        f = self.run_lint(self.sub("| --- | --- |\n", f"| --- | --- |\n| `{foreign}` | R1 |\n"))
        self.assertEqual(self.checks(f), ["L7"])
        self.assertIn(f"trace ID {foreign} is not a unit of module {MODULE}", f[0]["message"])

    # ------------------------------------------------------------ R3-S8: code is not prose

    def test_s8_tilde_fences_and_indented_code(self):
        line = self.rdef(2)
        for bad in (f"~~~\n{line}\n~~~", f"~~~~text\n{line}\n~~~~", f"\n    {line}", f"\n\t{line}",
                    f"````\n```\n{line}\n```\n````"):
            f = self.run_lint(self.sub(line, bad))
            self.assertIn("R2 is not defined in the spec", self.messages(f), bad)
        head, tail = self.spec.split("| --- | --- |\n")
        f = self.run_lint(head + "~~~\n| --- | --- |\n" + tail + "~~~\n")
        self.assertIn("the trace table is empty", self.messages(f))

    def test_s8_list_continuations_and_wrapped_lines_are_prose(self):
        vis = doc_lint.mask(["- item", "", "    continued in the list", "", "Paragraph", "    wrapped line", "",
                             "    code block", "", "    still code", "after"])
        self.assertEqual(vis, ["- item", "", "    continued in the list", "", "Paragraph", "    wrapped line", "",
                               "", "", "", "after"])
        line = self.rdef(2)
        self.assertEqual(self.run_lint(self.sub(line, "  " + line)), [])     # up to 3 spaces is not code

    # ------------------------------------------------------------ notes N1, N5

    def test_n1_documented_thresholds_are_the_code_s(self):
        readme = nfdocs.read(os.path.join(os.path.dirname(HERE), "README.md"))
        for text in (doc_lint.__doc__, readme):
            flat = " ".join(text.split())
            for want in (f"{doc_lint.MIN_STATEMENT_CHARS} or more letters and digits",
                         f"{doc_lint.MIN_STATEMENT_WORDS} or more distinct words",
                         f"{doc_lint.MIN_REASON} characters or more and {doc_lint.MIN_REASON_WORDS} or more distinct words",
                         f"{int(doc_lint.MAX_NA_SHARE * 100)}%", f"{int(doc_lint.MIN_COVERAGE * 100)}% or more",
                         f"at most {doc_lint.MAX_IDS_PER_R} IDs per R-number",
                         f"at most {doc_lint.MAX_REASON_REUSE} entries",
                         f"{doc_lint.MIN_QUOTE} or more characters of an unchecked entry",
                         f"{doc_lint.RETENTION_MIN_IDS} or more distinct identifiers"):
                self.assertIn(want, flat)
        line = self.rdef(2)
        src = " Source: " + line.split(" Source: ")[1]
        short = "x" * (doc_lint.MIN_STATEMENT_CHARS - 1)
        self.assertIn("R2 has no real statement", self.messages(self.run_lint(self.sub(line, f"R2. {short}." + src))))


class ReviewProbesR3(unittest.TestCase):
    """The round 3 probe files, linted against the reviewer's snapshot of the committed index. Each must fail, and
    with the finding that names its shortcut. Skipped where the lab folder is absent (the cases above do not need
    it)."""

    ROOT = os.path.expanduser("~/Projects/NativeFlows-lab/fable/s4-out/review-lint-probes-r3")
    COMMIT = "c9d57fecc2d3b8fdce2fa4b68da9b7ab79aa3aa0"      # the probes' 'Generated from index'
    CASES = [
        ("quality", ["P0_lazy_quality.md"], "whose Source does not cite it"),
        ("quality", ["P0_lazy_quality.md"], "Source ADR-0001.R1 is not in the rule index"),
        ("quality", ["P0_lazy_quality.md"], "a note must point to an R-number"),
        ("quality", ["P0_lazy_quality.md"], "is not mentioned in backticks outside 'Reads'"),
        ("quality", ["P0_lazy_quality.md"], "section '## Invariants' is empty"),
        ("policy", ["P0_lazy_policy.md"], "whose Source does not cite it"),
        ("quality", ["B1a_junk_statements.md"], "R1 has no real statement"),
        ("quality", ["B1b_placeholder_statements.md"], "R1 holds the placeholder 'TBD'"),
        ("quality", ["B1c_tilde_fence_defs.md"], "no R-number is defined"),
        ("quality", ["B1d_indented_code_defs.md"], "no R-number is defined"),
        ("quality", ["B1e_accepted_as_proposed.md"], "(accepted) points to R1, stated as proposed"),
        ("policy", ["B1f_notes_to_missing_heading.md"], "'Settlement topic' is not an R-number, ref:, an existing"),
        ("quality", ["B1g_duplicate_R_in_file.md"], "R2 is defined twice"),
        ("policy", ["B2a_flood_every_id.md"], "carries no conflict flag"),
        ("policy", ["B2b_unparsed_entries_dropped.md"], "looks like an entry but is not"),
        ("policy", ["B2c_open_fake_oq_parent_fp.md"], "names no open question"),
        ("policy", ["B2c_open_fake_oq_parent_fp.md"], "an entry of its parent rule does not serve"),
        ("quality", ["F1_foreign_rules.md"], "trace ID ADR-0047.R9 is not a unit of module quality"),
        ("quality", ["F2_chunk_a.md", "F2_chunk_b.md"], "Chunk 1 of 2 is given by 2 files"),
        ("quality", ["F2_chunk_a.md", "F2_chunk_b.md"], "R1 is defined twice"),
        ("quality", ["F2_chunk_a.md", "F2_chunk_c.md"], "k is not within 1..n"),
        ("quality", ["F5_front_in_comment.md"], "front matter field 'Module:' is missing"),
        ("quality", ["F6_trace_in_tilde_fence.md"], "the trace table is empty"),
        ("quality", ["F7_reads_in_comment.md"], "owned table `inspection_lot` is not mentioned"),
        ("quality", ["S3a_ref_unrelated.md"], "'ref: ADR-0047.R14' is not ADR-0075.R4"),
        ("quality", ["S3b_ref_wrong_module.md"], "'ref: process R-1', but the primary module of ADR-0075.R4"),
        ("ledger", ["S6a_superseded_old_text.md"], "ADR-0026.R14 is superseded (ADR-0027.R10); list 'CONFLICT"),
    ]

    @classmethod
    def setUpClass(cls):
        if not os.path.isdir(cls.ROOT):
            raise unittest.SkipTest("review probes not present on this machine")
        cls.stub = None
        if hasattr(doc_lint, "index_state"):      # the snapshot is not in a repository: take it as that commit
            cls.stub = mock.patch.object(doc_lint, "index_state", lambda i, d, s=None: (s or cls.COMMIT, []))
            cls.stub.start()

    @classmethod
    def tearDownClass(cls):
        if cls.stub:
            cls.stub.stop()

    def lint(self, module, names, index="idx-head.csv"):
        paths = [os.path.join(self.ROOT, n) for n in names]
        findings, info = doc_lint.lint(paths, module, os.path.join(self.ROOT, index), nfdocs.DEFAULT_DOCS, self.COMMIT)
        return findings, info

    def test_each_probe_fails_on_its_shortcut(self):
        for module, names, want in self.CASES:
            findings, _info = self.lint(module, names)
            text = "\n".join(f["message"] for f in findings)
            self.assertIn(want, text, names)

    def test_cross_is_no_compile_target(self):
        for name in ("F3_cross_zero_rules.md", "F3b_cross_zero_rules.md"):
            with self.assertRaises(SystemExit):
                self.lint("cross", [name])

    def test_count_forms(self):
        findings, _ = self.lint("quality", ["S2a_counts.md"])
        self.assertEqual(sorted(f["line"] for f in findings if f["check"] == "L4"), list(range(8, 35, 2)))

    def test_proposed_forms(self):
        findings, _ = self.lint("quality", ["S1a_prop_forms.md"], index="idx-prop3.csv")
        lines = sorted(f["line"] for f in findings if f["check"] == "L3")
        self.assertEqual(lines[:8], list(range(14, 29, 2)))
        self.assertIn("trace row ADR-0070.R15.N1 (proposed) points to heading 'Rules'",
                      "\n".join(f["message"] for f in findings))

    def test_unparsed_entries_reach_the_review_list(self):
        _f, info = self.lint("policy", ["B2b_unparsed_entries_dropped.md"])
        review = "\n".join(info["review"])
        for uid in ("ADR-0043.R5:", "ADR-0029.R14:", "ADR-0042.R7:"):
            self.assertIn(f"CONFLICT {uid}", review)

    def test_stale_key_is_listed(self):
        _f, info = self.lint("quality", ["S4a_stale_key.md"])
        self.assertEqual(len(info["key_mismatches"]), 2)


if __name__ == "__main__":
    unittest.main()
