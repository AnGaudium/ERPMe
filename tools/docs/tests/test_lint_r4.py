"""doc_lint, S4 review round 4 (R4-B1, R4-B2, R4-S1 to R4-S10, notes N2, N5, N6, the one-row-per-chunk-set rule and
the three round 3 behaviours the reviewer's mutation run found untested). Each test pins one finding and fails on the
lint before the round 4 fix. The cases are the reviewer's probes rebuilt on the generated spec of lint_support.py."""

import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))
import nfdocs  # noqa: E402
import doc_lint  # noqa: E402
from lint_support import LintBase, MODULE, SHA, flagged_only, make_spec, superseding  # noqa: E402

FILLER = ("Content pending; refer to the ADR text for this behaviour.", "Placeholder for the rule of the time model.",
          "Same as the ADR says about the event.", "See ADR-0007 rule 14 for the full statement of the event.",
          "Omitted for brevity in this chunk of the module.", "Rule text will be compiled in the next pass of the event.")


class R4(LintBase):

    def law_bytes(self, r):
        return len(self.texts[r["id"]].encode()) + sum(len(self.texts[n["id"]].encode()) for n in self.units
                                                       if n["kind"] == "note" and n["parent"] == r["id"])

    def large_rule(self):
        return next(r for r in self.rules[1:] if not superseding(r) and self.law_bytes(r) >= 1500
                    and doc_lint.identifiers(self.texts[r["id"]]))

    def small_rule(self):
        return next(r for r in self.rules[1:] if not superseding(r) and self.law_bytes(r) < 500)

    def parts(self, r, text=None):
        """-> (line, R-number, statement, ' Source: ...') of the rule's definition."""
        n = self.rnum_of(r["id"], text)
        line = self.rdef(n, text)
        head, src = line.split(" Source: ")
        return line, n, head.split(". ", 1)[1], " Source: " + src

    def two_chunks(self, extra1="", n=2, change2=None):
        """The baseline cut before `## Invariants`: chunk 1 holds the rules, chunk 2 the rows and the trace."""
        head, tail = self.spec.split("## Invariants", 1)
        front = "\n".join(self.spec.split("\n")[:3])
        c1 = head.replace("Chunk: whole", f"Chunk: 1 of {n}") + extra1 + "## Trace\n\n| Source | Where |\n| --- | --- |\n"
        c2 = (front + "\n## Purpose\n\nChunk two holds the rows.\n\n## Invariants" + tail).replace("Chunk: whole", f"Chunk: 2 of {n}")
        return self.write(c1, "r4-1.md"), self.write(change2(c2) if change2 else c2, "r4-2.md")

    def cli(self, paths, *extra):
        rc, out, _err = self.run_cli(list(paths) + ["--module", MODULE, "--index", self.index, "--index-commit", SHA]
                                     + list(extra))
        return rc, out

    # ------------------------------------------------------------ R4-B1: substance

    def test_b1_baseline_is_not_filler(self):
        f, info = self.run_lint(self.spec, with_info=True)
        self.assertEqual(f, [])
        sub = info["substance"]
        self.assertGreaterEqual(sub["size_ratio"], doc_lint.MIN_SIZE_RATIO)
        self.assertGreaterEqual(sub["share"], doc_lint.MIN_RETENTION)
        self.assertGreater(sub["rules_measured"], 3)

    def test_b1_filler_on_a_large_rule_that_keeps_one_identifier(self):
        r = self.large_rule()
        line, n, _st, src = self.parts(r)
        name = sorted(doc_lint.identifiers(self.texts[r["id"]]))[0]
        filler = f"{n}. `{name}` behaves for every company as the model of the ADR requires.{src}"
        f = self.run_lint(self.sub(line, filler))
        self.assertEqual(self.checks(f), ["L11"])
        self.assertIn(f"{r['id']} and its notes are {self.law_bytes(r)} bytes", f[0]["message"])
        self.assertIn(f"{doc_lint.MIN_RULE_RATIO:.2f} or more is required", f[0]["message"])

    def test_b1_small_rules_have_no_size_floor_but_no_placeholder(self):
        r = self.small_rule()
        line, n, _st, src = self.parts(r)
        name = sorted(doc_lint.identifiers(self.texts[r["id"]]) or {"event"})[0]
        self.assertEqual(self.run_lint(self.sub(line, f"{n}. `{name}` is delivered in order.{src}")), [])
        for bad in FILLER:
            f = self.run_lint(self.sub(line, f"{n}. {bad}{src}"))
            self.assertIn(f"{n} holds the placeholder", self.messages(f), bad)
        for ok in ("A pending event is retried by the dispatcher.", "The placeholder `<provider>` is replaced by a name.",
                   "The lines refer to the source document of the event.", "An omitted field is read as null."):
            self.assertEqual(self.run_lint(self.sub(line, f"{n}. {ok} It names `{name}`.{src}")), [], ok)

    def test_b1_module_floors(self):
        text = self.spec
        for i, r in enumerate(self.rules, start=1):
            line, n, _st, src = self.parts(r, text)
            name = sorted(doc_lint.identifiers(self.texts[r["id"]]) or {"event"})[0]
            text = self.sub(line, f"{n}. Statement {i} restates the law, naming `{name}`, in plain words.{src}", text)
        msg = self.messages(self.run_lint(text))
        self.assertIn(f"size ratio 0.", msg)
        self.assertIn(f"{doc_lint.MIN_SIZE_RATIO:.2f} or more is required", msg)
        self.assertIn("identifier retention", msg)
        self.assertIn(f"{doc_lint.MIN_RETENTION:.0%} or more is required", msg)
        # full-size statements without backticks: the size passes, the retention does not
        text = self.spec
        for r in self.rules:
            line, n, st, src = self.parts(r, text)
            text = self.sub(line, f"{n}. {st.replace('`', '')}{src}", text)
        msg = self.messages(self.run_lint(text))
        self.assertIn("identifier retention 0%", msg)
        self.assertNotIn("size ratio", msg)

    def test_b1_floors_are_documented(self):
        readme = " ".join(nfdocs.read(os.path.join(os.path.dirname(HERE), "README.md")).split())
        doc = " ".join(doc_lint.__doc__.split())
        for text in (doc, readme):
            for want in (f"{doc_lint.SUBSTANCE_MIN_BYTES} bytes or more", f"{doc_lint.MIN_RULE_RATIO:.2f} or more",
                         f"{doc_lint.MIN_SIZE_RATIO:.2f} or more", f"{doc_lint.MIN_RETENTION:.0%} or more",
                         f"exit {doc_lint.EXIT_PARTIAL}"):
                self.assertIn(want.lower(), text.lower())

    # ------------------------------------------------------------ R4-B2: not applicable

    def test_b2_not_applicable_rows_are_listed(self):
        note = self.quiet_note()
        text = self.set_where(note["id"], "not applicable: review credit, history", self.drop_source(note["id"]))
        f, info = self.run_lint(text, with_info=True)
        self.assertEqual(f, [])
        self.assertEqual(info["not_applicable_list"], [f"{note['id']} (note): review credit, history"])
        rc, out = self.cli([self.write(text, "na.md")])
        self.assertEqual(rc, 0)
        self.assertIn("NOT APPLICABLE (read each; template acceptance steps 2 and 3): 1\n"
                      f"  {note['id']} (note): review credit, history", out)

    def test_b2_not_applicable_is_refused_for_a_note_that_is_law(self):
        sup = next(r for r in self.units if r["kind"] == "note" and superseding(r))
        flagged = next(r for r in self.units if flagged_only(r))
        adds = next(r for r in self.units if r["kind"] == "note" and not superseding(r) and not r["conflict_flag"]
                    and any(x not in self.texts.get(r["parent"], "") for x in doc_lint.identifiers(self.texts[r["id"]])))
        for note, why in ((sup, "its relation is"), (flagged, "it carries a conflict flag"), (adds, "it introduces `")):
            text = self.set_where(note["id"], "not applicable: design-hardening history",
                                  self.drop_source(note["id"]))
            msg = self.messages(self.run_lint(text))
            self.assertIn(f"trace row {note['id']}: 'not applicable' is refused for this note: {why}", msg)

    def test_not_applicable_is_refused_for_a_rule(self):          # round 3 behaviour, untested until round 4
        r = self.small_rule()
        f = self.run_lint(self.set_where(r["id"], "not applicable: history only"))
        self.assertIn(f"trace row {r['id']}: 'not applicable' is refused for a rule", self.messages(f))

    # ------------------------------------------------------------ R4-S1: PARTIAL is not a pass

    def test_s1_partial_exits_3(self):
        p1, p2 = self.two_chunks()
        self.assertEqual(self.cli([p1, p2])[0], 0)
        rc, out = self.cli([p2], "--partial")
        self.assertEqual(rc, doc_lint.EXIT_PARTIAL)
        self.assertRegex(out.split("\n")[0], r"^LINT PARTIAL findings=0 deferred=\d+ \(NOT A PASS\)$")
        rc, out = self.cli([p2], "--partial", "--json")
        self.assertEqual(rc, doc_lint.EXIT_PARTIAL)
        p1, p2 = self.two_chunks(n=3)                       # chunks 1 and 2 of 3: chunk 3 does not exist
        rc, out = self.cli([p1, p2])
        self.assertEqual((rc, out.split("\n")[0]), (1, "LINT FAIL findings=1"))
        rc, out = self.cli([p1, p2], "--partial")
        self.assertEqual(rc, doc_lint.EXIT_PARTIAL)
        self.assertNotIn("LINT PASS", out)

    # ------------------------------------------------------------ R4-S2: owned catalog rows

    def owned(self, module):
        scope = nfdocs.module_scope(self.rows, self.owners, self.cats, module)
        return scope, doc_lint.owned_catalog_rows(scope, doc_lint.docs_model(nfdocs.DEFAULT_DOCS), module)

    def test_s2_one_word_matches_are_not_owned(self):
        scope, own = self.owned("clock")
        for c in ("authorization-areas:production", "invariants:INV-88"):
            self.assertIn(c, scope["owned_rows"])           # the index still credits them (its content is unchanged)
            self.assertNotIn(c, own)
        scope, own = self.owned("numeric")
        for c in ("authorization-areas:inventory", "system-accounts:inventory", "system-accounts:rounding_gain",
                  "transaction-keys:rounding_loss"):
            self.assertIn(c, scope["owned_rows"])
            self.assertNotIn(c, own)
        self.assertEqual(self.run_lint(make_spec(self.rows, self.owners, self.cats, "clock", self.texts),
                                       module="clock"), [])

    def test_s2_real_owned_rows_are_still_demanded(self):
        _scope, own = self.owned("quality")
        for c in ("authorization-areas:usage_decision", "settings:quality.usage_decision.auto_accept",
                  "work-item-kinds:inspection_lot_open", "movement-types:quality_sample"):
            self.assertIn(c, own)
        self.assertNotIn("authorization-verb-levels:Submit", own)
        _scope, own = self.owned("ledger")
        self.assertIn("invariants:INV-01", own)             # by `area`
        self.assertNotIn("invariants:INV-33", own)          # mentioned by a ledger rule, area of another module
        key = next(c.split(":", 1)[1] for c in self.cat_rows)
        f = self.run_lint(self.sub(f"- `{key}`\n", "- a row\n"))
        self.assertEqual(self.checks(f), ["L2"])
        self.assertIn(key, f[0]["message"])

    # ------------------------------------------------------------ R4-S3, S6: where a definition starts and ends

    def test_s3_a_wrapped_line_starting_with_an_r_number_is_text(self):
        r = self.small_rule()
        line, n, st, src = self.parts(r)
        wrapped = f"{n}. {st} The detail is in\nR3. This sentence is prose of the paragraph.{src}"
        f = self.run_lint(self.sub(line, wrapped))
        self.assertEqual(f, [])
        wrapped = f"{n}. {st} The rule extends\nR3.{src}"         # `R3. Source: ...` at the start of a line
        self.assertEqual(self.run_lint(self.sub(line, wrapped)), [])
        prose = "### Topic\n\nThis topic of the outbox is read with the rule cited as\nR3. in a hard-wrapped line of prose.\n"
        self.assertEqual(self.run_lint(self.sub("### Topic\n", prose)), [])     # a wrapped line of a prose paragraph

    def test_s3_rules_on_consecutive_lines_and_the_missing_source_hint(self):
        text = re.sub(r"\n\n(R\d+\. )", r"\n\1", self.spec)       # one rule per line, no blank line between
        self.assertEqual(self.run_lint(text), [])
        line = self.rdef(2, text)
        msg = self.messages(self.run_lint(self.sub(line, line.split(" Source: ")[0], text)))
        self.assertIn("is read as text of R2: a definition starts after a blank line", msg)

    def test_s6_a_table_and_a_list_inside_a_rule(self):
        r = self.small_rule()
        line, n, st, src = self.parts(r)
        body = (f"{n}. {st} The kinds are:\n\n| Kind | Meaning |\n| --- | --- |\n| `alpha_kind` | first |\n"
                f"| `beta_kind` | second |\n\n- `gamma_kind`: a list item of the rule\n\n{src.strip()}")
        path = self.write(self.sub(line, body), "table-rule.md")
        f, _info = doc_lint.lint([path], MODULE, self.index, nfdocs.DEFAULT_DOCS, SHA)
        self.assertEqual(f, [])
        d = next(d for d in doc_lint.Spec(path).defs if d["n"] == n[1:])
        for name in ("alpha_kind", "beta_kind", "gamma_kind"):
            self.assertIn(name, d["statement"])
        self.assertEqual(d["sources"], [x.strip("` ") for x in src.split("Source: ")[1].split(", ")])
        nosrc = self.sub(line, body.replace(src.strip(), "The paragraph after the table."))
        self.assertIn(f"{n} has no 'Source:' with a unit ID", self.messages(self.run_lint(nosrc)))

    def test_definition_indent_is_at_most_three_spaces(self):     # round 3 behaviour, untested until round 4
        line = self.rdef(2)
        listed = ("### Topic\n\n- A list item of the topic.\n\n    R2. This continuation of the list item is prose. "
                  "Source: `" + self.rules[1]["id"] + "`\n")
        self.assertEqual(self.run_lint(self.sub("### Topic\n", listed)), [])
        f = self.run_lint(self.sub("### Topic\n", listed.replace("    R2.", "   R2.")))
        self.assertIn("R2 is defined twice", self.messages(f))
        self.assertTrue(line)

    def test_a_repeated_statement_is_a_finding(self):             # round 2 behaviour, untested until round 4
        a, b = [r for r in self.rules[1:] if not superseding(r) and self.law_bytes(r) < 500][:2]
        _la, na, sta, _sa = self.parts(a)
        lb, nb, _stb, sb = self.parts(b)
        f = self.run_lint(self.sub(lb, f"{nb}. {sta}{sb}"))
        self.assertIn(f"{nb} repeats the statement of {na}", self.messages(f))

    def test_n2_leading_zeros_name_the_same_r_number(self):
        line = self.rdef(2)
        dupe = line.replace("R2. Statement 2", "R02. Statement two again", 1)
        f = self.run_lint(self.sub(line, line + "\n\n" + dupe))
        self.assertEqual(self.checks(f), ["L1"])
        self.assertIn("R2 is defined twice", f[0]["message"])

    # ------------------------------------------------------------ R4-S4, S5: values of law, wrapped counts

    def test_s4_values_of_law_are_not_counts(self):
        law = {"quotes": [], "own": {}}
        for ok in ("The timeout is 30 s for commands and 10 s for queries.", "It allows 300 ms per query.",
                   "Rows stay 90 days in outbox tables.", "After 8 weeks without event it is closed.",
                   "The code (ISO 4217, in the currency table) is stored.", "It takes 20 % in all rules.",
                   "A name has 60 characters in all tables.", "It rounds to 4 decimals in tables."):
            self.assertEqual(doc_lint.count_matches(ok, law), [], ok)
            self.assertTrue(doc_lint.count_findings(ok), ok)        # outside a rule the old strictness stays
        for bad in ("It owns 16 tables.", "The module has ten settings.", "Tables owned: 10."):
            self.assertTrue(doc_lint.count_matches(bad, law), bad)

    def test_s4_a_quote_of_the_source_is_not_a_count(self):
        source = "the profile keeps five sample values per column and two rules decide; the module owns ten tables"
        law = {"quotes": [source], "own": {"tables": 10, "rules": 40}}
        self.assertEqual(doc_lint.count_matches("The profile keeps five sample values per column.", law), [])
        self.assertEqual(doc_lint.count_matches("Here two rules decide the order.", law), [])
        self.assertTrue(doc_lint.count_matches("The profile keeps six sample values per column.", law))
        self.assertTrue(doc_lint.count_matches("It owns ten tables.", law))            # the module's own count
        self.assertTrue(doc_lint.count_matches("The module has two rules.", law))      # reads as an inventory
        self.assertTrue(doc_lint.count_matches("The profile keeps five sample values per column.",
                                               {"quotes": [], "own": {}}))

    def test_s4_in_a_spec_only_rule_definitions_read_values_of_law(self):
        r = self.small_rule()
        line, n, st, src = self.parts(r)
        value = "The timeout is 30 s for commands."
        self.assertEqual(self.run_lint(self.sub(line, f"{n}. {st} {value}{src}")), [])
        f = self.run_lint(self.sub("## Entities and tables\n", f"{value}\n\n## Entities and tables\n"))
        self.assertEqual(self.checks(f), ["L4"])
        phrase = next(m.group(0) for t in self.texts.values()
                      for m in [re.search(r"\b(?:two|three|four|five) [a-z]+ (?:columns|commands|events)\b", t)] if m)
        owner = next(u for u in self.units if u["kind"] == "rule" and phrase in self.texts[u["id"]]) \
            if any(phrase in self.texts[u["id"]] for u in self.units if u["kind"] == "rule") else None
        if owner:                                                   # a quote passes in the rule that cites its source
            ol, on, ost, osrc = self.parts(owner)
            self.assertEqual(self.run_lint(self.sub(ol, f"{on}. {ost} It has {phrase}.{osrc}")), [])

    def test_s4_a_row_quoting_its_catalog_row_is_not_a_count(self):
        # INV-672 says "two executions of one event", EC-168 "two rules": a row that quotes them states law
        inv = "| `INV-672` | day | no rule version has two executions of one event in one mode |"
        ec = "- `EC-168`: a token rule drafts to the account; an outflow under two rules never posts."
        text = self.sub("## Invariants\n\nNone (the module owns no invariant).", f"## Invariants\n\n{inv}")
        text = self.sub("## Edge cases\n\nNone (the module owns no edge case).", f"## Edge cases\n\n{ec}", text)
        self.assertEqual(self.run_lint(text), [])
        for other in (inv.replace("INV-672", "INV-01"), ec.replace("EC-168", "EC-01")):   # not their catalog rows
            if other.startswith("|"):
                bad = self.sub("## Invariants\n\nNone (the module owns no invariant).", f"## Invariants\n\n{other}")
            else:
                bad = self.sub("## Edge cases\n\nNone (the module owns no edge case).", f"## Edge cases\n\n{other}")
            self.assertEqual(self.checks(self.run_lint(bad)), ["L4"], other)
        moved = self.sub("## Entities and tables\n", f"{ec}\n\n## Entities and tables\n")   # outside: strict
        self.assertEqual(self.checks(self.run_lint(moved)), ["L4"])

    def test_n1_ref_names_the_unit_or_its_parent_rule(self):
        r = next((x for x in self.rules if MODULE not in x["primary_module"] and not superseding(x)
                  and any(t in self.texts for t in x["xrefs_rules"])), None)
        self.assertIsNotNone(r, "precondition: a foreign rule of the module that cites another rule")
        cited = next(t for t in r["xrefs_rules"] if t in self.texts)
        f = self.run_lint(self.as_ref(r, f"ref: {cited}"))
        self.assertIn(f"trace row {r['id']}: 'ref: {cited}' is not {r['id']} or its parent rule", self.messages(f))
        self.assertEqual(self.run_lint(self.as_ref(r, f"ref: {r['id']}")), [])

    def test_s5_a_count_split_by_a_line_wrap_and_two_more_forms(self):
        for bad in ("It owns 16\ntables.", "It has all 16 of its tables here.", "The table count is 16.",
                    "The number of owned tables is 16.", "It owns tables, 16 in all.", "Its commands number 12.",
                    "It owns a couple of tables.",
                    "Tables owned (sixteen in all): see the list."):
            f = self.run_lint(self.sub("## Entities and tables\n", f"{bad}\n\n## Entities and tables\n"))
            self.assertEqual(self.checks(f), ["L4"], bad)
        f = self.run_lint(self.sub("## Entities and tables\n", "It owns 16\ntables.\n\n## Entities and tables\n"))
        self.assertEqual(f[0]["line"], self.spec.split("\n").index("## Entities and tables") + 1)
        for ok in ("- It has 16\n- tables of other modules are read", "The key has 16 values.\n\nTables follow.",
                   "The rule code is set only for a pair of segregation rules."):
            self.assertEqual(self.run_lint(self.sub("## Entities and tables\n", f"{ok}\n\n## Entities and tables\n")),
                             [], ok)

    # ------------------------------------------------------------ R4-S7: front matter

    def test_s7_front_matter_in_one_leading_code_fence(self):
        lines = self.spec.split("\n")
        fenced = "\n".join(["```"] + lines[:2] + ["```"] + lines[2:])
        self.assertEqual(self.run_lint(fenced), [])
        self.assertEqual(self.run_lint("\n" + fenced.replace("```", "~~~")), [])
        later = "\n".join(["A line before the fence.", "", "```"] + lines[:2] + ["```"] + lines[2:])
        self.assertEqual(self.checks(self.run_lint(later)), ["L0"])
        wrong = fenced.replace(f"Module: {MODULE}", "Module: ledger")
        self.assertIn("is not --module", self.messages(self.run_lint(wrong)))

    # ------------------------------------------------------------ R4-S8: names in their sections

    def test_s8_owned_tables_are_named_under_entities(self):
        t = self.tables[0]
        moved = self.sub(f"- `{t}`\n", "").replace("## Entities and tables\n", f"It also owns `{t}`.\n\n"
                                                                             "## Entities and tables\n", 1)
        f = self.run_lint(moved)
        self.assertEqual(self.checks(f), ["L2"])
        self.assertIn(f"owned table `{t}` is not mentioned in backticks under '## Entities and tables'", f[0]["message"])
        self.assertNotIn("nor anywhere", f[0]["message"])
        by_rule = self.sub(f"- `{t}`\n", f"\nDefined by rule, without DDL: `{t}` (R2).\n")
        self.assertEqual(self.run_lint(by_rule), [])

    def test_s8_none_while_the_module_owns_rows(self):
        keys = [c.split(":", 1)[1] for c in self.cat_rows]
        a = self.spec.index("## Settings\n")
        b = self.spec.index("## UI annotations")
        none = (self.spec[:a] + "## Settings\n\nNone (stated in the rules).\n\n" + self.spec[b:]).replace(
            "## Entities and tables\n", "Names: " + ", ".join(f"`{k}`" for k in keys) + ".\n\n## Entities and tables\n", 1)
        own = [c for c in self.cat_rows if c.startswith("settings:")]
        self.assertTrue(own, "precondition: the module owns a setting")
        f = self.run_lint(none)
        self.assertIn("section '## Settings' says None, but the module owns", self.messages(f))
        module = "tax"                                              # owns invariants and edge cases by `area`
        spec = make_spec(self.rows, self.owners, self.cats, module, self.texts)
        self.assertEqual(self.run_lint(spec, module=module), [])
        a, b = spec.index("## Invariants\n"), spec.index("## Edge cases")
        ids = re.findall(r"INV-\d+", spec[a:b])
        self.assertTrue(ids)
        none = spec[:a] + "## Invariants\n\nNone (see the rules).\n\n" + spec[b:].replace(
            "## Settings\n\n", "## Settings\n\n" + "".join(f"- the check `{i}`\n" for i in ids), 1)
        f = self.run_lint(none, module=module)
        self.assertEqual(self.checks(f), ["L2"])
        self.assertIn("section '## Invariants' says None, but the module owns", f[0]["message"])

    # ------------------------------------------------------------ one row per ID in the chunks of a module

    def test_a_row_defined_in_two_chunks(self):
        key = next(c.split(":", 1)[1] for c in self.cat_rows if c.startswith("settings:"))
        self.assertEqual(doc_lint.lint(list(self.two_chunks()), MODULE, self.index, nfdocs.DEFAULT_DOCS, SHA)[0], [])
        for row in (f"- `{key}`: the same row again", f"| `{key}` | integer | the same row again |",
                    f"1. **`{key}`** again"):
            paths = self.two_chunks(extra1=f"## Settings\n\n{row}\n\n")
            f, _ = doc_lint.lint(list(paths), MODULE, self.index, nfdocs.DEFAULT_DOCS, SHA)
            self.assertEqual(self.checks(f), ["L2"], row)
            self.assertIn(f"`{key}` has a row in this chunk and in {paths[0]}", f[0]["message"])
            self.assertEqual(f[0]["file"], paths[1])
        cited = f"## Settings\n\n- Chunk 2 defines `{key}`; rule R2 reads it.\n\n"        # a citation, not a row
        f, _ = doc_lint.lint(list(self.two_chunks(extra1=cited)), MODULE, self.index, nfdocs.DEFAULT_DOCS, SHA)
        self.assertEqual(f, [])
        both = "## Invariants\n\n| `INV-01` | commit | a check |\n\n## Edge cases\n\n- `EC-03`: a case\n\n"
        paths = self.two_chunks(extra1=both, change2=lambda t: t.replace(
            "None (the module owns no invariant).", "| `INV-01` | commit | the same check; see `EC-03` |").replace(
            "None (the module owns no edge case).", "- `EC-03`: the same case, with `INV-01`"))
        f, _ = doc_lint.lint(list(paths), MODULE, self.index, nfdocs.DEFAULT_DOCS, SHA)
        self.assertEqual(sorted(re.findall(r"`((?:INV|EC)-\d+)` has a row", self.messages(f))), ["EC-03", "INV-01"])
        self.assertEqual(len(f), 2)

    # ------------------------------------------------------------ R4-S9: OPEN names the unit's ADR

    def test_s9_the_quoted_open_question_names_the_units_adr(self):
        note = next(r for r in self.units if r["kind"] == "note" and superseding(r))
        entry = next(l for l in self.spec.split("\n") if l.startswith(f"CONFLICT {note['id']}:"))
        adr = note["id"][:8]
        other = "ADR-0041" if adr != "ADR-0041" else "ADR-0039"
        mine = self.open_question(f"Decide for {adr} whether the rule text or its later note governs the retention.")
        theirs = self.open_question(f"Confirm for {other} the status of the circular and the report it requires.")
        bare = self.open_question("Confirm the status of the second circular and the report that it requires.")
        self.assertEqual(self.run_lint(self.sub(entry, f'OPEN {note["id"]}: "{mine[:50]}"')), [])
        for q in (theirs, bare):
            f = self.run_lint(self.sub(entry, f'OPEN {note["id"]}: "{q[:50]}"'))
            self.assertEqual(self.checks(f), ["L5"], q)
            self.assertIn(f"quotes an open question that does not name {adr}", f[0]["message"])

    # ------------------------------------------------------------ R4-S10: no line hides in a continuation

    def test_s10_a_conflicts_line_is_an_entry_or_an_indented_continuation(self):
        a = next(r for r in self.units if r["kind"] == "note" and not superseding(r) and not r["conflict_flag"])["id"]
        b = self.rules[1]["id"]
        first = f"CONFLICT {a}: the later note names the period and that reading is kept"
        for bad in (f"- CONFLICT ({b}): the rule text on stored events is stale against the note",
                    f"Conflict on {b} too: the rule text on stored events is stale against the note",
                    "and that reading of the period is kept in the statement of the rule",
                    f"  - CONFLICT ({b}): an indented list item is no continuation of the entry",
                    f"  Conflict on {b} too: an indented entry-like line is no continuation"):
            text = self.sub("\n\n## Proposed (not law)", f"\n{first}\n{bad}\n\n## Proposed (not law)")
            f, info = self.run_lint(text, with_info=True)
            self.assertEqual(self.checks(f), ["L5"], bad)
            self.assertIn(f"{first.split(': ', 1)[0]}: {first.split(': ', 1)[1]}", info["review"])
        text = self.sub("\n\n## Proposed (not law)", f"\n{first}\n  in the statement of the rule\n\n## Proposed (not law)")
        f, info = self.run_lint(text, with_info=True)
        self.assertEqual(f, [])
        self.assertIn(first + " in the statement of the rule", info["review"])

    # ------------------------------------------------------------ R4-N6: citation forms

    def test_n6_five_more_citation_forms(self):
        for form in ("rule 9 (ADR-0047)", "R9 of ADR-0047", "ADR‑0047 rule 9", "ADR-0047/R9", "ADR-0047 r. 9"):
            self.assertIn("ADR-0047.R9", doc_lint.unit_ids_in(doc_lint.clean(form)), form)
        self.assertEqual(doc_lint.unit_ids_in("R9 of the list and rule 9 (see above)"), set())
