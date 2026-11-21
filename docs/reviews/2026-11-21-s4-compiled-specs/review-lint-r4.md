# Review of doc_lint, round 4 (S4 compiled-spec gate)

Reviewer: Claude Opus 5.5 (review-only subagent), 2026-11-21. Nothing in the repository was edited, committed or pushed.

Subject: `~/Projects/NativeFlows-s4`, branch `s4-compiled-specs`, HEAD `344a02b` (worktree clean). The index file
`docs/design/generated/rule-index.csv` was last committed in `49ab52f`, so every probe is linted against the **live
committed index** with no `--index-commit` (the commit check runs for real).

**Probes** are in `review-lint-probes-r4/`:
- `honest/clock.md` and `honest/numeric.md` are hand-compiled honest specs (task 3). `honest/numeric-v1-as-written.md`
  is the numeric spec exactly as first written, before I fixed my own two mistakes.
- `base_<module>.md` are made by `gen4.py MODULE OUT`: the test suite's `make_spec` run over the live index.
- `probes4.py [substring]` writes `probes/<name>.md`. Each probe makes **one** change to a spec that passes. It lints
  the probe and prints line 1, the exit code and the findings.
- `lint.sh MODULE SPEC... [args]` is the plain wrapper.
- `ratio.py MODULE SPEC` prints, for each source rule, its statement bytes divided by its rule-plus-note bytes.
- `mutate.py TREE` is the mutation check of the tests (task 4). Its output is in `mutation.txt`.
- `unittest.txt` holds the unit-test run.

Every command below runs from `review-lint-probes-r4/`. `P=~/Projects/NativeFlows-lab/.venv/bin/python`.

Each round-3 probe is checked in isolation, which the builder's re-run of the old probes did not do. All the old probes
derive from `P0`, so each one still fails on about 100 shared defects, and that hides whether its own shortcut is
closed. Here every probe starts from a spec that passes, and the finding shown is the only one the probe gets.

## Verdict

The round-3 fix is substantial and well tested.
- The trace is now connected to the rule bodies: Source and trace agree in both directions, and Source IDs must exist
  and belong to the module.
- Junk and listed placeholders are refused.
- `ref:`, the Conflicts section, the chunk set, the index commit, fences and comments are all checked.
- 13 of the 16 round-3 items in scope are closed or nearly closed.
- 43 of 46 single-fix mutations turn a test red.

Two gaps still let a spec drop law and print `LINT PASS`:
1. **A statement still does not have to state anything.** It needs 12 letters, 2 words that occur in the ADRs, and one
   backticked identifier of the rule (only when the rule has 3 or more). That is enough to pass. The test suite's own
   passing baseline has exactly this form: `Statement 3 restates the law of ADR-0008.R5, naming `x`, in plain words.`
   It passes on `registry` with 89 rules, a size ratio of 0.07 and 11% identifier retention (R4-B1).
2. **`not applicable: <any text>` drops amending notes silently.** Every one of the 1,104 notes in the index is
   classified as law (relation `amends`, `supersedes` or `superseded-by`). Up to 15% of a module's units can be marked
   n/a, and nothing lists them for a reader (R4-B2).

The honest specs show that the lint is now strict but mostly fair:
- **`clock` passed on the first run**, 0 findings.
- **`numeric` got 13 findings.** Two were my own mistakes. The other 11 are false positives or traps, from 4 causes:
  - owned-catalog-row misattribution (6 findings);
  - a hard-wrapped `R18.` read as a new definition (5 findings);
  - `ISO 4217` read as a typed count (1 finding);
  - a rule whose content is a table (the trap appeared only in a variant).

Counts: **2 BLOCKING, 10 SHOULD-FIX, 6 NOTE.**

Unit tests: `python -m unittest discover tools/docs/tests`: **125 tests, OK, 18.9 s**.

## 1. Round-3 items (fresh probes)

| Item | Status | Probe and lint output |
| --- | --- | --- |
| R3-B1 trace not connected | **partly** | Closed: `b1a_source_mismatch` (L1 `R14 cites ADR-0007.R13 … does not point to R14` plus the reverse finding); `b1b_source_foreign_unknown` (L7 `Source ADR-0047.R14 is not a unit of module clock`, L7 `ADR-0007.R99 is not in the rule index`). Open: `b1c_filler_R15_one_identifier` and `b1d_filler_every_rule` pass, `b1e_placeholder_0..5` pass 6/6 (see R4-B1). |
| R3-B2 accepted under Proposed | **closed** | `b2a_accepted_under_proposed`: L3 `trace row ADR-0007.R14 (accepted) points to R14, stated as proposed`. `b2b_accepted_marked_proposed`: same finding. |
| R3-B3 notes on headings | **closed** for headings, **new channel** | `b3a_note_on_heading`: L1 `a note must point to an R-number…`. `b3b_note_on_missing_heading`: L1 `'Where' part 'As-of date' is not…`. But `b3c_amending_notes_not_applicable` passes (R4-B2). |
| R3-B4 `ref:` target | **closed** (residue NOTE) | `b4a_ref_unrelated_id`: L1 `'ref: ADR-0047.R14' is not ADR-0017.R18, its parent rule or a rule its text cites`. `b4b_ref_wrong_module`: L1 `'ref: process R-1', but the primary module of ADR-0017.R18 is permissions`. Residue: `b4d` (R4-N1). |
| R3-B5 cross measures nothing | **closed** | `b5a_cross`, `b5b_api` and `b5c_process`: exit 2 with a clear message. |
| R3-B6 malformed entries vanish | **mostly closed** | `b6_0` (`Conflict ADR-…`) gets L5 `looks like an entry`. `b6_3` (em dash form) parses into the REVIEW LIST. `b6_4` (entry in Rules) gets L5 `outside '## Conflicts'`. Residue: `b6_1` and `b6_2` (R4-S8). |
| R3-B7 superseded rule in old form | **closed** as far as mechanics go | `b7a_source_lacks_superseder`: L10 `R12 states ADR-0013.R12, which ADR-0040.R13 supersedes, but its Source does not cite ADR-0040.R13`. `b7b_conflict_names_own_r`: L10 `list 'CONFLICT ADR-0013.R12: <reason that names ADR-0040.R13>'`. Residue: `b7c` passes with an OPEN entry that quotes an unrelated question (R4-S9). |
| R3-S1 count forms | **partly** | `s1_0..s1_9`: 9 of 10 fresh forms pass. Only `sixteen distinct owned tables` gets L4. Not caught: `all 16 of its tables`, `The table count is 16`, `16`⏎`tables`, `tables, 16 in all`, `a couple of tables`. New false positives on law values: R4-S4. |
| R3-S2 proposed citation forms | **partly** (latent) | `probes/s2_proposed_forms.md` with `--index probes/propidx/…` (ADR-0047 set to proposed, committed in a scratch repository). L3 fires on lines 12, 14, 26, 28 and 30. Not parsed: line 16 `rule 9 (ADR-0047)`, line 18 `R9 of ADR-0047`, line 20 `ADR‑0047` (U+2011 hyphen), line 22 `ADR-0047/R9`, line 24 `ADR-0047 r. 9` (R4-N6). |
| R3-S3 duplicates and chunks | **closed** (residue NOTE) | `s3b_bold_dupe`: L1 `R17 is defined twice (first at line 115)`. Chunks are covered by the builder's tests (mutations red). Residue: `s3a_R02_and_R2` passes (R4-N2). |
| R3-S4 L2 visibility and section content | **partly** | Comments, invisible characters and empty sections are closed (tests red under mutation). `s4a_entities_without_tables` passes: the owned tables appear only in Purpose and Entities says "No entities…". `s4b_invariants_none_while_owned` passes: `INV-216` is owned and Invariants says `None` (R4-S7). |
| R3-S5 index commit | **closed** | `s5a_bogus_commit`: L0 `--index-commit 'deadbeef00' is not a commit`. `s5b_changed_snapshot`: L0 `the index differs from its version in commit 49ab52ff76d9`. `s5c_equal_snapshot`: PASS (correct). `s5d_old_index_commit`: 2× L0. The stable key stays a warning by decision (W2, `--strict` makes it a finding). |
| R3-S6 entries | **closed** (residue) | `s6a_open_quotes_answered_question`: L5 `names no open question`. `s6c_flood_near_copy_conflicts`: L5 `one CONFLICT reason (or a near copy) serves 8 entries`. Residue: `s6b` passes, because any unchecked question serves (R4-S9). |
| R3-S7 foreign trace row | **closed** | `s7a_foreign_trace_row`: L7 `trace ID ADR-0047.R14 is not a unit of module clock … drop the row`. |
| R3-S8 `~~~` and indented code | **closed** | `s8a_tilde4_fence`: L1 `R14 is not defined in the spec`. `s8b` (a `<details>` block) passes, which is correct because a reader sees it. |

## 2. Findings

### BLOCKING

**R4-B1. A content-free statement that keeps one identifier still states a rule.**

Where: `doc_lint.py:321-334` (`statement_problem`), `:994-1000` (L11 fires only when 0 identifiers are kept) and
`:1001-1008` (the size ratio is printed, never checked).

Repro:
- `$P probes4.py b1_filler_big`: R15 of `clock` is the rule plus 4 amending notes, 2,649 bytes of law
  (`as_of_date`, the override table, the `environment` guard). It becomes
  `R15. `business_date_override` behaves for every company as the time model of the ADR requires. Source: ADR-0007.R15,
  .N1, .N2, .N3, .N4`. Result: `LINT PASS findings=0`.
- `$P probes4.py b1_filler_all`: all 18 statements become `Statement n restates the law, naming `x`, in plain words.`
  Result: `LINT PASS`, retention 43%, size ratio 0.19.
- `./lint.sh registry $PWD/base_registry.md`: the test suite's own baseline. Result: `LINT PASS`, with 89 filler
  statements, retention 11% and size ratio 0.07. `test_baseline_passes` pins this form as passing.
- `$P probes4.py placeholder`: on a rule with fewer than 3 identifiers, these all pass:
  - `Content pending; refer to the ADR text…`;
  - `Placeholder for the rule…`;
  - `Same as the ADR…`;
  - `See ADR-0007 rule 14 for the full statement…`;
  - `Omitted for brevity…`;
  - `Rule text will be compiled in the next pass…`.

  441 of the 1,657 rules have fewer than 3 identifiers, so L11 can never fire on them.

Expected: the stance is "a backstop against cooperative but lazy compilers", and a lazy compiler that runs short of
context writes exactly these sentences for its last rules. The spot check draws 20 rules. If 3 of 89 rules are dropped
this way, the chance that the spot check sees none of them is C(86,20)/C(89,20) ≈ 0.46.

Actual: PASS. The measures that separate the two cases exist, but they are only printed.

Calibration with `$P ratio.py MODULE SPEC` (per source rule: statement bytes of its R-numbers ÷ bytes of the rule and
its notes):

| Spec | Lowest per-rule ratio | Rules below 0.15 | Module size ratio | Retention |
| --- | --- | --- | --- | --- |
| honest `clock` | 0.15 (R9) | 1 of 18 | 0.99 | 97% |
| honest `numeric` | 0.15 (R8) | 0 of 19 | n/a | n/a |
| pilot `quality` | 0.20 (R17) | 0 of 22 | 0.81 | 89% |
| filler `registry` | 0.01 | 73 of 89 | 0.07 | 11% |
| filler `clock` (b1d) | n/a | n/a | 0.19 | 43% |

Fix:
1. Per source rule whose rule-plus-note text is 500 bytes or more: its R-numbers' statements must be at least 0.10 of
   that size. Then filler fails on every large rule, and no honest rule measured falls under the floor.
2. Per module: a size ratio of 0.30 or more and retention of 40% or more. Both are findings, with the threshold
   printed.
3. Extend the placeholder list to `pending`, `placeholder`, `omitted`, `for brevity`, `same as the ADR`,
   `see ADR-nnnn`, `refer to`, `will be compiled|stated|written`.
4. Rebuild `make_spec` so that the test baseline is not itself a filler spec. For example, quote the first sentence of
   each source rule.

**R4-B2. `not applicable: <any reason>` drops amending notes, and no list shows them.**

Where: `doc_lint.py:842-848` (any reason is accepted for a note), `:964-966` (only a 15% cap) and template row 11.

Repro: `$P probes4.py b3`, probe `b3c_amending_notes_not_applicable`.
- `ADR-0007.R15.N1` (the `as_of_date` law), `.N3` (its accepted range) and `.N4` (transport-only range check) are
  traced as `not applicable: design-hardening history` or `not applicable: review history`.
- They are removed from R15's Source, and the `as_of_date` sentences are deleted.
- Result: `LINT PASS findings=0`. The REVIEW LIST and the SUPERSEDED RULES list are empty, and no line of output names
  the three notes.

Expected: a finding, or at least a list the spot check must read. The index classifies all 1,104 notes as law
(`amends` 1,018, `supersedes` 83, `superseded-by` 3). The template allows n/a for "non-normative text such as review
credits or history", but the lint cannot tell those apart and accepts any text. For `master_data` (250 notes), 15% of
units is dozens of droppable amendments. The 20-rule spot check draws rules, not n/a notes.

Fix:
- print `NOT APPLICABLE (read each; template acceptance step 2)` with each unit and its reason, and add these units to
  acceptance step 2;
- lower the cap for notes to about 5%;
- or refuse n/a for a note that adds identifiers its parent rule does not hold (`identifiers(note) - identifiers(rule)`
  is not empty), which is a mechanical sign of new law.

### SHOULD-FIX

**R4-S1. `--partial` exits 0, and a phantom chunk hides missing units.**

Where: `doc_lint.py:1296-1306`, README "Output" ("Exit 0 on PASS and PARTIAL").

Repro: `$P probes4.py partial`.
- `n1b_lone_chunk_partial`: the whole `clock` spec minus R14-R18 and its 11 units, declared `Chunk: 1 of 2`. With
  `--partial` the result is exit 0, `LINT PARTIAL findings=0 deferred=13`.
- `n1c_two_of_three_partial`: chunks 1 and 2 of 3 are given and no chunk 3 exists. Result: exit 0, PARTIAL. The 10
  missing units are deferred to a chunk that does not exist.
- Without `--partial`, `n1a` and `n1d` fail as they should.

Expected: the template (step 1) says PARTIAL is not a pass. Any orchestrator or agent that checks the exit status
accepts it. The lint cannot know the true n, so it can never detect the phantom chunk.

Fix: PARTIAL exits with a distinct code (3) and prints `NOT A PASS` on line 1. The compile brief should say that only
exit 0 together with `LINT PASS` passes, and the S4 gate script must never pass `--partial`.

**R4-S2. L2 makes honest specs name catalog rows they do not own, and `Reads` does not serve.**

Where: `nfdocs.module_scope` `owned_rows` (`nfdocs.py:802-826`), `doc_lint.py:1028-1030`.

Repro:
- `$P probes4.py honest_fp`, probe `fp1_numeric_as_written`, gets 6 L2 findings:
  - `authorization-areas:inventory` and `system-accounts:inventory`, from the example `"system_account:inventory"`
    in ADR-0006.R4;
  - `system-accounts:rounding_gain`, `rounding_loss` and `transaction-keys:rounding_gain`, `rounding_loss`, from the
    section unit `ADR-0006.D0`. The defining rule, ADR-0006.R20, is primary in `ledger`.
- `fp2_clock_production_unbackticked`: L2 `authorization-areas:production`. The word is the value of the `environment`
  setting in ADR-0007.R15, not the authorization area.
- `fp3_clock_no_invariant`: L2 `invariants:INV-88`. A note mentions it in passing; it is the taint invariant of ADR-0029.

Expected: none of these rows are owned. To pass, numeric must restate ledger's rounding-line law, which template rule 6
forbids, and clock must cite an authorization area that has nothing to do with it. Listing the rows under `Reads` does
not help, because owned rows are checked outside `Reads`.

Fix:
- derive owned rows from units of kind `rule` and `note` only, not `section`;
- match a code span to a catalog only when the span is qualified (`system_account:inventory` matches system-accounts
  only) or is the row's own code in a sentence that names the catalog;
- let `Reads` or a `Not owned:` line serve for a catalog row;
- or demote owned catalog rows to a printed list.

**R4-S3. A hard-wrapped `R<n>.` at the start of a line opens a new definition.**

Where: `doc_lint.py:191` (`RULE_DEF_RE`) and `:390` (a definition ends at the next line that matches it).

Repro:
- `fp1_numeric_as_written`: line 115 ends `Audit tables are partitioned by` and line 116 starts
  `R18. Source: ADR-0006.R23, .N1, .N2`. The lint reports `R19 has no 'Source:'`, `R18 is defined twice` and 3 trace
  disagreements: 5 findings that point away from the cause.
- `fp6_wrapped_r_reference` (clock): same effect, 5 findings.

Expected: none. The repository wraps prose at 120 characters, and references to rules by R-number are common.

Fix: inside a paragraph, a line that starts with `R<n>.` opens a new definition only when the open definition already
has its `Source:`. Otherwise it is a continuation. The alternative is to require a blank line between definitions.

**R4-S4. L4 flags law values and standard numbers, contradicting template rule 4.**

Where: `doc_lint.py:171-172` (`COUNT_BEFORE_RE` allows up to 3 words, commas and prepositions between the number and
the noun).

Repro:
- `fp1_numeric_as_written` line 83 `(ISO 4217, in the currency table)` gives L4 `typed count '4217, in the currency
  table'`.
- `$P -c 'import doc_lint; print(doc_lint.count_findings("The timeout is 30 s for commands and 10 s for queries."))'`
  from `tools/docs` gives 2 findings.
- The same happens for:
  - `300 ms per query`;
  - `90 days in outbox tables`;
  - `From 2027 credit notes`;
  - `five sample values per column`;
  - `8 weeks without event`.
- Over all unit texts, `count_findings` fires 177 times. Examples: ADR-0022.R9 `30 s for commands`, ADR-0040.R13
  `300 ms per query`, ADR-0041.R8 `2027 credit note`.

Expected: template rule 4 says "thresholds and defaults taken from a rule are quoted from it, not counted". An honest
compiler that restates ADR-0022.R9 must distort the value.

Fix: no count across a comma or a preposition (`in`, `for`, `per`, `without`, `of`). A number followed by a unit (`s`,
`ms`, `min`, `h`, `days`, `weeks`, `months`, `years`, `%`, `decimal places`), a 4-digit year, or a number after `ISO`,
`RFC` or `version` is a value. Re-measure on the ADR text and pin the cases in `test_s1_names_and_citations_are_not_counts`.

**R4-S5. L4 misses a count split by a hard wrap, plus other fresh forms (R3-S1 residue).**

Where: `doc_lint.py:1039` (counts are matched line by line).

Repro: `$P probes4.py s1`:
- `s1_3`: `It owns 16`⏎`tables.` passes;
- `s1_0`, `s1_1`, `s1_2`, `s1_4`, `s1_6` to `s1_9` pass too.

An honest compiler that wraps lines produces `s1_3` without meaning to.

Fix: match counts on paragraphs whose lines are joined. For the other forms, accept the residue and document it; the
count marker is the positive path. Do not keep chasing forms with more regular expressions.

**R4-S6. A rule whose content is a table cannot be written in normal markdown.**

Where: `doc_lint.py:390` (a definition ends at the first blank line). The template is silent on this.

Repro: `fp4_source_after_table`. Numeric R6 is written as `R6. Each kind of number has … :`, then a blank line, the
table of ADR-0006.R8, a blank line and `Source: ADR-0006.R8`. Result: L1 `R6 has no 'Source:'` and L1 `trace row
ADR-0006.R8 points to R6, whose Source does not cite it`. The table also never counts for L11 or the size ratio (the
honest R8 ratio of 0.15 is low for this reason). GFM needs a blank line before a table, or the line before becomes its
header row.

Fix: a table that follows the definition paragraph after one blank line belongs to the definition, and a `Source:` line
right after the table is read. At the least, template row 4 should say "put `Source:` before a table that belongs to
the rule".

**R4-S7. The front matter fails when written in a code fence, as the template shows it.**

Where: template lines 241-244 (the front matter is shown inside ```` ``` ````), `doc_lint.py:420` (front matter is read
from visible lines, fences blanked).

Repro: `fp9_front_matter_in_fence_as_template_shows`. Result: 6× L0 `front matter field 'Module:' is missing or empty`,
although the fields are there.

Fix: the template shows the front matter as plain lines and says "not in a fence". The lint could also say "front
matter is inside a code fence" when it finds the fields there.

**R4-S8. R3-S4 residue: owned tables and owned invariants need not sit in their sections.**

Where: `doc_lint.py:1011-1027` (L2 accepts a name anywhere in the body).

Repro: `$P probes4.py s4`:
- `s4a_entities_without_tables`: `## Entities and tables` says "No entities of its own are described here.", and the 4
  owned tables are named in Purpose. Result: PASS.
- `s4b_invariants_none_while_owned`: `## Invariants` says `None (…)`, while the module owns `INV-216`, which appears
  under Settings. Result: PASS.

Expected: template rows 2 and 5 put these in their sections, and a `None` that contradicts owned rows is a statement
that is false.

Fix: owned tables must be backticked inside `## Entities and tables`, owned `INV-`/`EC-` rows inside their sections,
and owned settings in `## Settings`. `None` in Invariants, Edge cases or Settings is refused while the module owns rows
of that kind.

**R4-S9. Any unchecked open question serves an OPEN entry, and OPEN exempts a superseded rule from L10.**

Where: `doc_lint.py:623-635` and `:1172`.

Repro:
- `b7c_open_with_unrelated_question`: superseded rule `ADR-0013.R12` gets `OPEN ADR-0013.R12: "Confirm TT133's status
  and the B03 requirement"`, and the superseder is dropped from R12's Source. Result: PASS. The rule is listed with
  `entry: OPEN`.
- `s6b_open_quotes_unrelated_open_question`: same for a flagged note.

The rule stays visible in the REVIEW LIST and the SUPERSEDED RULES list, so the chief architect can catch it. But the
quote itself is never checked against the unit, and OPEN is the cheapest way to make L10 go away.

Fix: the quoted entry must name the unit's ADR (`ADR-nnnn`, or its file `nnnn-…md`) or the superseding ADR. Otherwise
it is a finding.

**R4-S10. A continuation line swallows a second conflict.**

Where: `doc_lint.py:476-477`.

Repro: `$P probes4.py b6`:
- `b6_1`: the line `- CONFLICT (ADR-0013.R16): …`;
- `b6_2`: the line `Conflict on ADR-0013.R16 too: …`.

Each comes right after a valid entry and is appended to that entry's reason. Result: PASS, with no entry of its own
and no ID check. It is visible only inside the reason of `ADR-0013.R12`.

Fix: a line that starts with a list marker, or holds a unit ID next to `conflict`, `open` or `false positive` (any
case), is never a continuation; it parses or it is L5.

### NOTE

- **R4-N1.** `ref: ADR-…` accepts any rule the unit's text cites. In `b4d`, permissions rule ADR-0017.R19 traced as
  `ref: ADR-0013.R7`, an outbox rule it cites, raises no `ref:` finding. The template (row 11) allows only "the unit's
  own or its rule's". The harm is small, because the primary module still states the rule. Align the lint and the
  template.
- **R4-N2.** `R02.` and `R2.` are two R-numbers (`s3a_R02_and_R2`: PASS, the same rule stated twice). Strip leading
  zeros before the duplicate check.
- **R4-N3.** The reason test counts ADR words, not sense. The generated baseline's entries pass, for example
  `CONFLICT ADR-0013.R12: ADR-0040.R13 governs; handles holders implies informs integer invoiced`. The chief architect
  reads them (step 3); the builder accepted this as decision 5.
- **R4-N4.** `Source ADRs:` and `Build step(s):` are only checked to be non-empty. They could be compared with the
  module's primary ADRs and the units' steps.
- **R4-N5.** Template and lint, smaller gaps:
  - The template's `None` sentence (line 260) does not mention section 2, but the lint accepts a bare `None` for a
    module without tables.
  - Rule 6 says "cite its source ID (`ADR-0014.R12`)" while a foreign ID in `Source:` is L7. The template should say
    "in the statement, not in `Source:`".
  - Acceptance step 2 should include the n/a list of R4-B2.
- **R4-N6.** R3-S2 residue, latent while no ADR is proposed: 5 citation forms are not parsed (table above).

## 3. Honest specs (false positives)

`honest/clock.md`: 18 rules, 10 notes folded, Decision text traced to `Purpose`, no tables, about 8.8 KB.
`./lint.sh clock $PWD/honest/clock.md` gives **`LINT PASS findings=0`** on the first run, with retention 97% and size
ratio 0.99. The template and the lint agreed throughout. A first-time compiler needs to know three things:
- `None` needs a reason in sections 3 and 5-8;
- notes need their `.Nj` in the `Source:`;
- the Decision text unit may point to a heading.

The template says all three.

`honest/numeric-v1-as-written.md` (`$P probes4.py honest_fp`, `fp1`) gets 13 findings:

| Finding | Judgement |
| --- | --- |
| L5 OPEN names no open question | My mistake: the Procrastinate question is answered (`[x]`), so CONFLICT is right. The lint was correct. |
| L1 ×5, from `R18.` wrapped to the start of a line | **False positive**, R4-S3. |
| L2 ×6 for `inventory`, `rounding_gain`, `rounding_loss` | **False positive**, R4-S2. Fixing it means restating ledger's law. |
| L4 `4217, in the currency table` | **False positive**, R4-S4. |

`honest/numeric.md` (after rewrapping and the CONFLICT) still fails with the 7 false positives of R4-S2 and R4-S4.

Variants on the honest specs:
- `fp2`, `fp3`: clock must backtick `production` and `INV-88` (R4-S2);
- `fp4`: a table rule (R4-S6);
- `fp9`: front matter fenced as in the template (R4-S7);
- `fp5`: `two commands` is L4, which the template's rule 4 does ask for, so it is not counted as a false positive;
- `fp7` and `fp8` (`Reads` used as a word, `Reads and writes:`): no false positive.

## 4. Unit tests and mutation check

`unittest.txt`: 125 tests, OK, 18.9 s.

`$P mutate.py <copy of the repo>` disables one round-3 fix at a time in a copy of `doc_lint.py` and runs
`test_lint_r3` and `test_lint` (88 tests). Results are in `mutation.txt`. **43 of 46 mutations turn a test red.** Every
BLOCKING and SHOULD-FIX fix of round 3 has at least one test that fails without it, and the S5 tests use a real git
repository.

The 3 mutations that stay green:
- **"definition indent at most 3"** (`RULE_DEF_RE` `^ {0,3}` replaced by `^\s*`): part of R3-S8, untested. An R-number
  indented 4 or more spaces inside a list continuation would count as a definition.
- **"repeated statement"**: a round-2 check, untested.
- **"`not applicable` refused for a rule"**: an older check, untested.

13 mutations are red through `ReviewProbesR3.test_each_probe_fails_on_its_shortcut` as well. That class needs the lab
folder (R3 N4), but each of those 13 mutations also turns a self-contained test red.

Not covered by any test because the behaviour is wrong: R4-B1 (`test_baseline_passes` pins filler as passing), R4-B2
and R4-S1 (`test_s3_lone_chunk_is_partial` asserts exit 0 for PARTIAL).

## Not checked

- Routing (R3-S9, excluded by the brief).
- Token estimation.
- Specs larger than about 22 KB, and real multi-chunk honest specs.
