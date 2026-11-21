"""doc_lint: a generated compiled spec passes; one mutation per check makes exactly that check fire (S3 brief, S3 review
round 1: B1, B2, S3, S4, S5, S10, N4, N5; round 2: R2-B1, R2-B2, R2-S1 to R2-S4, R2-S6). The round 3 checks are in
test_lint_r3.py; the generated spec and the helpers are in lint_support.py."""

import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))
import nfdocs  # noqa: E402
import build_index  # noqa: E402
import doc_lint  # noqa: E402
from lint_support import LintBase, MODULE, SHA, flagged_only, make_spec, superseding  # noqa: E402


class LintMutations(LintBase):
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
        edge = "## Edge cases\n\nNone (stated with the owned rows under Settings).\n\n"
        self.assertEqual(self.checks(self.run_lint(self.sub(edge, ""))), ["L0"])
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
        n = self.rnum_of(r["id"])
        for ok in (f"{n}-{n}", f"{n}, Topic", f"{n}; Purpose"):
            self.assertEqual(self.run_lint(self.sub(row, f"| `{r['id']}` | {ok} |")), [], ok)
        # an unknown Where part was warning W1 until round 3; it is a finding now
        self.assertEqual(self.checks(self.run_lint(self.sub(row, f"| `{r['id']}` | {n}, somewhere |"))), ["L1"])

    def test_l1_ref_for_another_modules_rule(self):
        r = next(x for x in self.rules if MODULE not in x["primary_module"] and not superseding(x))
        self.assertEqual(self.run_lint(self.as_ref(r, f"ref: {r['primary_module'][0]} R-12")), [])
        self.assertEqual(self.run_lint(self.as_ref(r, f"ref: {r['id']}")), [])
        self.assertEqual(self.checks(self.run_lint(self.as_ref(r, "ref: nosuch R-12"))), ["L8"])
        self.assertEqual(self.checks(self.run_lint(self.as_ref(r, "ref: ADR-0999.R1"))), ["L7"])

    def test_l1_note_may_be_not_applicable_within_the_cap(self):
        note = next(r for r in self.units if r["kind"] == "note" and not superseding(r) and not r["conflict_flag"])
        dropped = self.drop_source(note["id"])
        self.assertEqual(self.run_lint(self.set_where(note["id"], "not applicable: review credit, history", dropped)),
                         [])
        self.assertEqual(self.checks(self.run_lint(self.set_where(note["id"], "not applicable", dropped))), ["L1"])
        notes = [r for r in self.units if r["kind"] == "note" and not superseding(r)]
        text = self.spec
        for n in notes:
            text = self.set_where(n["id"], "not applicable: history only", self.drop_source(n["id"], text))
        f = self.run_lint(text)
        self.assertEqual(self.checks(f), ["L1"])
        self.assertIn("units are 'not applicable'", self.messages(f))

    def test_l1_definitions_need_visible_real_text(self):
        line = self.rdef(2)
        for bad in (f"```\n{line}\n```", f"<!--\n{line}\n-->", "R2. Short. Source: x", "Reads: " + line,
                    "R2. " + self.rdef(3)[4:]):
            f = self.run_lint(self.sub(line, bad))   # L11 joins when the statement loses the rule's identifiers
            self.assertIn(self.checks(f), (["L1"], ["L1", "L11"]), bad)

    def test_l1_coverage(self):
        # every rule row points to R1: at most 4 IDs count for one R-number
        text = self.spec
        for r in self.rules:
            text = self.sub(self.row_of(r["id"], text), f"| `{r['id']}` | R1 |", text)
        f = self.run_lint(text)
        self.assertIn("L1", self.checks(f))
        self.assertIn("map to R-numbers", self.messages(f))

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
        spec = make_spec(self.rows, self.owners, self.cats, module, self.texts)
        self.assertEqual(self.run_lint(spec, module=module), [])
        key = extra[0].split(":", 1)[1]
        self.assertEqual(self.checks(self.run_lint(self.sub(f"- `{key}`\n", "", spec), module=module)), ["L9"])

    # ---------------------------------------------------------------- L3

    def test_l3_proposed_rule_stated_as_law(self):
        victim = next(r["id"] for r in self.rules[1:] if not superseding(r))   # R1 also holds notes of other rules
        n = self.rnum_of(victim)
        idx = self.edited_index("index-proposed.csv",   # the rule and its notes: one R-number is law or proposed
                                lambda r: r.update(status="proposed") if victim in (r["id"], r["parent"]) else None)
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
        self.assertEqual(self.run_lint(make_spec(rows, self.owners, self.cats, MODULE, self.texts), index=idx), [])

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
        question = doc_lint.docs_model(nfdocs.DEFAULT_DOCS)["questions"]["open"][0][:60]
        self.assertEqual(self.run_lint(self.sub(line, f'OPEN {note["id"]}: asked as "{question}"')), [])
        if MODULE not in note["primary_module"]:
            ref_ok = self.set_where(note["id"], f"ref: {note['parent']}", self.drop_source(note["id"],
                                                                                           self.sub(line, "")))
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
        notes = [r["id"] for r in self.units if r["kind"] == "note" and not superseding(r)
                 and not r["conflict_flag"]][:4]
        self.assertEqual(len(notes), 4)
        extra = "\n".join(f"CONFLICT {n}: the same filler reason for every entry" for n in notes)
        self.assertEqual(self.checks(self.run_lint(self.sub("## Proposed (not law)", extra + "\n\n## Proposed (not law)"))),
                         ["L5"])
        three = "\n".join(f"CONFLICT {n}: the same filler reason for every entry" for n in notes[:3])
        self.assertEqual(self.run_lint(self.sub("## Proposed (not law)", three + "\n\n## Proposed (not law)")), [])

    def test_l10_superseded_rule(self):
        sup = next(r for r in self.rules if superseding(r) and MODULE in r["primary_module"])
        line = next(l for l in self.spec.split("\n") if l.startswith(f"CONFLICT {sup['id']}:"))
        f = self.run_lint(self.sub(line, ""))
        self.assertEqual(self.checks(f), ["L10"])
        self.assertIn(sup["id"], f[0]["message"])
        # FALSE-POSITIVE is refused for it (L10) and for any unit without a conflict flag (L5, round 3)
        f = self.run_lint(self.sub(line, f"FALSE-POSITIVE {sup['id']}: harmless, the rule text is unchanged here"))
        self.assertEqual(self.checks(f), ["L10", "L5"])

    def test_review_list(self):
        path = self.write(self.spec, "review.md")
        _rc, out, _err = self.run_cli([path, "--module", MODULE, "--index", self.index, "--index-commit", SHA])
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
        path = self.write(self.spec, "cli.md")
        rc, out, _err = self.run_cli([path, "--module", MODULE, "--index", self.index, "--index-commit", SHA])
        self.assertEqual((rc, out.split("\n")[0]), (0, "LINT PASS findings=0"))
        with open(path, "a", encoding="utf-8") as fh:
            fh.write("| `ADR-0999.R1` | R1 |\n")
        rc, out, _err = self.run_cli([path, "--module", MODULE, "--index", self.index, "--index-commit", SHA, "--json"])
        self.assertEqual((rc, out.split("\n")[0]), (1, "LINT FAIL findings=1"))


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
