"""doc_lint, review round 5 (S2 to S6 and the cheap notes). Each test pins one probe of
`review-lint-r5.md` and fails on the lint before the round 5 fix. B1, B2 and B3 are not fixed here (README, Blind
spots)."""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))
import doc_lint  # noqa: E402
from lint_support import LintBase  # noqa: E402

PURPOSE = "## Purpose\n\n"


class R5(LintBase):

    def in_purpose(self, line):
        return self.sub(PURPOSE, PURPOSE + line + "\n\n")

    def counts(self, line):
        return [f for f in self.run_lint(self.in_purpose(line)) if f["check"] == "L4"]

    def with_statement(self, add):
        """The first R-number with `add` at the end of its statement (before ` Source:`)."""
        line = self.rdef(1)
        head, src = line.split(" Source: ")
        return self.sub(line, f"{head} {add} Source: {src}")

    # ------------------------------------------------------------ S2: citations inside statements

    def test_s2_unknown_id_in_a_statement(self):
        f = self.run_lint(self.with_statement("(ADR-0004.R99)"))
        self.assertEqual(self.checks(f), ["L7"], self.messages(f))
        self.assertIn("ADR-0004.R99", self.messages(f))
        self.assertEqual(len(f), 1)

    def test_s2_unknown_note_id_and_prose_forms(self):
        for add in ("(ADR-0004.R13.N99)", "(rule 99 of ADR-0004)"):
            with self.subTest(add):
                f = self.run_lint(self.with_statement(add))
                self.assertIn("L7", self.checks(f), self.messages(f))

    def test_s2_unknown_id_in_a_conflict_reason(self):
        line = next(l for l in self.spec.split("\n") if l.startswith(("CONFLICT ", "FALSE-POSITIVE ")))
        f = self.run_lint(self.sub(line, line + " See also ADR-0004.R99."))
        self.assertEqual(self.checks(f), ["L7"], self.messages(f))

    def test_s2_real_ids_pass_and_source_is_not_reported_twice(self):
        real = next(r["id"] for r in self.rows if r["kind"] == "rule" and r["status"] != "proposed"
                    and r["id"] not in {u["id"] for u in self.units})
        self.assertEqual(self.run_lint(self.with_statement(f"({real})")), [])
        f = self.run_lint(self.sub(f"`{self.rules[0]['id']}`", "`ADR-0004.R99`", self.spec))   # in a Source
        self.assertEqual([x["check"] for x in f].count("L7"), 1, self.messages(f))   # reported once, by the Source check

    # ------------------------------------------------------------ S3: front matter against the units

    def test_s3_source_adrs_must_list_every_traced_adr(self):
        first = self.spec.split("\n")[0]
        adr = first.split("Source ADRs: ")[1].split(", ")[0]
        f = self.run_lint(self.sub(first, first.replace(adr + ", ", "")))
        self.assertEqual(self.checks(f), ["L0"], self.messages(f))
        self.assertIn(adr, self.messages(f))
        f = self.run_lint(self.sub(first, first.split("Source ADRs: ")[0] + "Source ADRs: ADR-0042"))
        self.assertEqual(self.checks(f), ["L0"], self.messages(f))

    def test_s3_extra_adr_and_other_forms_pass(self):
        first = self.spec.split("\n")[0]
        self.assertEqual(self.run_lint(self.sub(first, first + ", ADR-0042")), [])
        self.assertEqual(self.run_lint(self.sub(first, first.replace("ADR-", "ADR "))), [])

    def test_s3_build_steps(self):
        second = self.spec.split("\n")[1]
        for bad in ("99", "0, 99", "soon"):
            with self.subTest(bad):
                f = self.run_lint(self.sub(second, second.replace("0, 1, 2, 3, 5", bad)))
                self.assertEqual(self.checks(f), ["L0"], self.messages(f))
        for ok in ("not stated in the index", "0, 3", "5"):
            with self.subTest(ok):
                self.assertEqual(self.run_lint(self.sub(second, second.replace("0, 1, 2, 3, 5", ok))), [])

    # ------------------------------------------------------------ S4: content-free sections

    def test_s4_content_free_sections(self):
        count = "The module owns <!-- count:tables -->4<!-- /count --> tables."
        for text in ("---", "-", "Clock.", "***", "* * *"):
            with self.subTest(text):
                f = self.run_lint(self.sub(count, text))
                self.assertEqual(self.checks(f), ["L0"], self.messages(f))
                self.assertIn("no real content", self.messages(f))
        none = "None (the test module registers nothing)."
        for text in ("-", "---", "Done."):
            with self.subTest("commands " + text):
                self.assertEqual(self.checks(self.run_lint(self.sub(none, text))), ["L0"])

    def test_s4_none_needs_a_reason(self):
        none = "None (the test module registers nothing)."
        for text in ("None (n/a).", "None: none.", "None (none)", "None: N/A", "None (not applicable).", "None: -"):
            with self.subTest(text):
                f = self.run_lint(self.sub(none, text))
                self.assertEqual(self.checks(f), ["L0"], self.messages(f))
        for text in ("None (nothing registered).", "None: the module registers no command."):
            with self.subTest(text):
                self.assertEqual(self.run_lint(self.sub(none, text)), [])
        # a reason that is given must be real in a section where None may stand bare
        f = self.run_lint(self.sub("## Proposed (not law)\n\nNone.", "## Proposed (not law)\n\nNone (n/a)."))
        self.assertEqual(self.checks(f), ["L0"], self.messages(f))

    def test_s4_real_content_passes(self):
        count = "The module owns <!-- count:tables -->4<!-- /count --> tables."
        self.assertEqual(self.run_lint(self.sub(count, "It owns the outbox tables.")), [])
        self.assertEqual(self.run_lint(self.sub("None (the test module registers nothing).", "- `register`")), [])

    # ------------------------------------------------------------ S5: L4 forms

    def test_s5_ascii_forms(self):
        for line in ("It owns 12 (twelve) tables.", "It owns twelve (12) tables.", "Tables x12.", "Tables ×12.",
                     "x12 tables", "It defines 29 units.", "It has 11 sections.", "It owns 12 entities.",
                     "It owns 12 relations.", "It owns 12.0 tables.", "It owns 1.2e1 tables.",
                     "It owns 0x0C tables.", "The module owns 12\\ tables.", "It has a unit count of 29 units."):
            with self.subTest(line):
                self.assertTrue(self.counts(line), line)

    def test_s5_count_alone_on_a_line(self):
        for line in ("Owned tables:\n\n12", "Owned tables\n\n- 12", "Tables\n\n| Owned | 12 |", "Owned tables\n12.",
                     "### Owned tables\n\n12", "| Tables | Count |\n| --- | --- |\n| Owned | 12 |"):
            with self.subTest(line):
                self.assertTrue(self.counts(line), line)

    def test_s5_lone_numbers_that_are_not_counts(self):
        for line in ("Owned tables:\n\n- `outbox_event`", "The rules are listed below.\n\n12 July", "Tables\n\n| `x` | 12 |",
                     "Steps\n\n12", "Owned tables:\n\n<!-- count:tables -->4<!-- /count -->"):
            with self.subTest(line):
                self.assertEqual(self.counts(line), [], line)

    def test_s5_unicode_forms(self):
        for line in ("It owns 12 tаbles.",                      # Cyrillic a
                     "It owns Ⅻ tables.",                        # Roman numeral twelve
                     "It owns ¹² tables.",                  # superscript
                     "It owns 十二 tables.",                  # CJK
                     "It owns ⑧ tables.",                        # circled eight
                     "It owns １２ tables.",                  # fullwidth
                     "It owns ١٢ tables.",                  # Arabic-Indic
                     "It owns 12 t\u0430bl\u0435s.",                 # Cyrillic a, e
                     "It owns 12 tábles.", "It owns 12 ﬁxed tables.", "It owns 二十 tables."):
            with self.subTest(line):
                self.assertTrue(self.counts(line), line)

    def test_s5_confusable_placeholders(self):
        for add in ("ТBD", "ＴＢＤ", "TODО", "to be compilеd"):
            with self.subTest(add):
                f = self.run_lint(self.sub(self.rdef(1), self.rdef(1).replace(" Source:", f" {add} Source:")))
                self.assertIn("placeholder", self.messages(f), add)

    def test_s5_values_of_law_and_quotes_still_pass(self):
        law = {"quotes": ["an other receipt of 10 units valued 1,000 and a total of 1,000 for 3 units"],
               "own": {"tables": 4, "units": 40, "sections": 3}}
        self.assertEqual(doc_lint.count_matches("with a total of 1,000 for 3 units", law), [])
        self.assertEqual(doc_lint.count_matches("a timeout of 30 s and 5 days", {"quotes": [], "own": {}}), [])
        self.assertTrue(doc_lint.count_matches("The spec has 40 units.", law))          # the module's own count
        self.assertEqual(self.counts("`12` is a name here, and rule 12 note 3."), [])
        self.assertEqual(self.counts("It has two kinds of time: business dates and instants."), [])

    def test_s5_id_homoglyphs_are_still_not_folded(self):
        f = self.run_lint(self.sub(f"`{self.rules[0]['id']}`", f"`А{self.rules[0]['id'][1:]}`", self.spec))
        self.assertTrue(f, "an ID with a Cyrillic letter must stay a finding")

    # ------------------------------------------------------------ S6: marker kind and the noun after it

    def test_s6_marker_kind_and_noun(self):
        for text in ("It defines <!-- count:tables -->0<!-- /count --> rules.",
                     "It owns <!-- count:tables -->4<!-- /count --> commands.",
                     "It owns <!-- count:rules -->4<!-- /count --> owned tables.",
                     "It owns <!-- count:tables -->4<!-- /count --> settings"):
            with self.subTest(text):
                f = [x for x in self.run_lint(self.in_purpose(text)) if x["check"] == "L4"]
                self.assertTrue(any("followed by" in x["message"] for x in f), self.messages(f))

    def test_s6_matching_noun_passes(self):
        n = len(self.tables)
        rules = len([r for r in self.units if r["kind"] == "rule"])
        for text in (f"It owns <!-- count:tables -->{n}<!-- /count --> tables.",
                     f"It owns <!-- count:tables -->{n}<!-- /count --> owned tables and states "
                     f"<!-- count:rules -->{rules}<!-- /count --> rules.",
                     f"<!-- count:tables -->{n}<!-- /count --> of the owned tables are listed.",
                     f"<!-- count:tables -->{n}<!-- /count --> of the rules are not tables of its own."):
            with self.subTest(text):
                self.assertEqual(self.counts(text), [], text)
