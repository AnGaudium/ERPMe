# Review of doc_lint, round 3 (S4 compiled-spec gate)

Reviewer: Claude Opus 5.5 (review-only subagent), 2026-11-21. Nothing in the repository was edited, committed or pushed.

Subject: `~/Projects/NativeFlows-s4` at HEAD `0274b2b` (merge of PR #26). The index file was last committed in `c9d57fe`.
Files: `tools/docs/doc_lint.py`, `nfdocs.py`, `build_index.py`, `README.md`, `docs/design/compiled-spec-template.md`,
`docs/design/generated/rule-index.csv` and `tools/docs/rule-module-overrides.csv`.

**Working tree note.** During the review the worktree had uncommitted changes to `rule-module-overrides.csv` (13 new
rows: ADR-0047 R1, R2, R16 and R21-R23; ADR-0057.R20; ADR-0064.R6) and to the regenerated `rule-index.csv`. The files
were modified at 18:45, while the review ran, so the builder was presumably working in parallel. To get stable results,
every probe was linted against a snapshot of the **committed** index (`git show HEAD:docs/design/generated/rule-index.csv`
saved as `review-lint-probes-r3/idx-head.csv`), with `--index-commit c9d57fecc2d3b8fdce2fa4b68da9b7ab79aa3aa0`.

**Probes.** They are in `review-lint-probes-r3/`:
- `gen3.py` builds a "lazy compiler" baseline;
- `probes3.py` builds the variants;
- `lint.sh MODULE SPEC...` is the reproduction wrapper. It runs
  `python tools/docs/doc_lint.py SPEC --module MODULE --index idx-head.csv --index-commit c9d57fe…` from the worktree root.

Every command below is run from that folder.

## Verdict

The round-2 fixes close the exact probes of round 2. They do not close the class of attack. A 2.3 KB `quality` spec
(`P0_lazy_quality.md`) passes with `LINT PASS findings=0` and zero warnings:
- it has 5 filler rules that state nothing ("The behaviour here follows the source text echo charlie india delta 1.");
- their `Source:` names `ADR-0001.R1`, an ID that is not even in the index;
- every note is traced to the heading `Rules`;
- the only rule of another module points with `ref:` to an unrelated purchasing rule;
- all owned tables appear only in a `Reads:` line;
- 6 of the 11 sections are empty.

A 7 KB `policy` spec built the same way also passes (`P0_lazy_policy.md`: 154 units, 9 filler rules, 81 notes on a
heading). So does a `ledger` spec with 26 filler rules for 100 primary rules (`S6a`).

The underlying gap is still that the trace table and the rule bodies are never connected: an R-number is counted, its
`Source:` is never read.

Counts: **7 BLOCKING, 9 SHOULD-FIX, 6 NOTE.** Round-2 items: 0 closed, 6 partly closed, 2 open (R2-S6, and R2-S5 at HEAD,
which has an uncommitted fix in the working tree).

Unit tests: `python -m unittest discover tools/docs/tests` from the worktree root: **72 tests, OK, 46.4 s.**

## 1. Round-2 items

| Item | Status | What closed (verified) | What a fresh probe still gets through |
| --- | --- | --- | --- |
| R2-B1 empty rules | **partly** | `R1. .`, defs inside ```` ``` ```` fences or `<!-- -->`, `Reads` lines and repeated statements are refused. A heading-only Where for a rule is refused. Coverage is 60% with at most 4 IDs per R-number. `not applicable` is capped at 15%. | <ul><li>Filler or junk statements: `B1a` (32 dots, `&nbsp;`×6, `<br>`×8) and `B1b` (`TBD: to be compiled…`). Both `LINT PASS findings=0`.</li><li>The `Source:` of an R-number is never compared with the IDs traced to it, nor checked against the index (P0, R3-B1).</li><li>Defs in a `~~~` fence (`B1c`) or a 4-space indented code block (`B1d`): PASS.</li><li>Accepted law stated only under `## Proposed (not law)`: `B1e` PASS (R3-B2).</li><li>Notes on any heading, or on a heading that does not exist: `B1f` PASS with 85 W1 warnings (R3-B3).</li></ul> |
| R2-B2 hidden conflicts | **partly** | FALSE-POSITIVE is refused for `supersedes`/`superseded-by` notes (L5) and superseded rules (L10). One FP reason, or a near copy, may serve at most 3 entries. The REVIEW LIST now holds FP entries, and template step 3 says so. | <ul><li>Gibberish FP reasons: P0, `rudfuxjdxkxwqnq vgjjspqmsbphxzmnvflrwyvz`.</li><li>An entry for every ID: `B2a`, 154 review entries, PASS.</li><li>Malformed entries vanish from the REVIEW LIST: `B2b`, 4 real conflicts dropped (R3-B6).</li><li>An FP on the parent rule silences a flagged note, and `OPEN …: OQ-99999` (no such question) passes: `B2c` (R3-S6).</li><li>The CONFLICT reason "R1 governs this case as written in the spec" is reused 6 times: PASS.</li></ul> |
| R2-S1 proposed via heading | **partly** | A rule can no longer point to a heading. `rule 12 of ADR-0070`, `ADR-0070, R12` and `[ADR-0070](x) rule 12` are parsed. | <ul><li>With ADR-0070 set to proposed (`idx-prop3.csv`), its note `ADR-0070.R15.N1` and `ADR-0070.D0` traced to `Rules` raise no L3.</li><li>5 of 8 body forms are not parsed: `ADR-0070 (rule 12)`, `ADR 0070 rule 12`, `rule 12 in ADR-0070`, `ADR-0070 §12`, `ADR-0070 Rule 12`. `S1a` raises L3 at lines 22, 24 and 26 only (R3-S2). Latent: no ADR is proposed today.</li></ul> |
| R2-S2 counts | **partly** | All round-2 K_counts forms are now findings (`test_l4_typed_counts`). | 13 of 14 fresh forms pass (`S2a`, R3-S1). |
| R2-S3 ref: Where | **partly** | `ref: <module> R-<n>` and `ref: ADR-nnnn.Rk` exist and are refused when the module is primary. | The target is unchecked. `ref: ADR-0047.R14` for ADR-0075.R4 (`S3a`) and `ref: process R-1` for an inventory rule (`S3b`) both PASS (R3-B4). |
| R2-S4 positional note IDs | **partly** | L0 compares `Generated from index` with the index commit. The `#stable_key` mismatch is detected. | <ul><li>The key is optional and a mismatch is only W2: `S4a` PASS with 2 warnings, one saying "that text is now ADR-0047.R9".</li><li>An uncommitted index is only W0 (live run, see R3-S5).</li><li>`--index-commit` is not checked to be a real commit.</li></ul> |
| R2-S5 misroutes | **open at HEAD** | Not committed. The working tree adds overrides for ADR-0064.R6, ADR-0057.R20 and ADR-0047 R1, R2, R16, R21-R23. | The routing sample (section 3) finds more: the rest of the ADR-0064 `module production` family and ADR-0050's query-layer group. |
| R2-S6 supersession direction | **open** | W3 exists (warning only). | <ul><li>W3 is silenced by naming the superseder in `Source:` while the statement keeps the old text: `S6a` R1 states ADR-0026 rule 14's lock order with `Source: ADR-0026.R14, ADR-0027.R10` and `CONFLICT ADR-0026.R14: R1 governs…`. PASS, 0 warnings.</li><li>Template acceptance step 2 still does not say the spot-check includes every L10 rule.</li></ul> |

**Round-2 fixes with no unit test.** None is entirely untested. Gaps:
- the `MIN_RULE_TEXT` threshold is not pinned (and it differs from the docs, N1);
- W0 has no test;
- the 0.8 near-copy similarity of FP reasons is untested (`test_l5_reused_reason` uses identical text);
- `~~~` fences and indented code are untested;
- the R2-S5 overrides have no test (they are uncommitted);
- the R2-S6 template change was never made.

`ReviewProbes.test_probes_fail` reads the round-1 and round-2 probes from the lab folder, against the live default index.
It is skipped on a machine without that folder (N4).

## 2. Findings

### BLOCKING

**R3-B1. The trace is not connected to the rule bodies: a spec can state nothing and pass.**
`doc_lint.py:170-195` (`_find_defs`) and `:389-399` (the L1 R-number branch).
- An R-number counts as soon as it has 30 or more unique characters.
- Its `Source:` is never compared with the IDs whose rows point to it, never checked against the index, and never
  checked for the module.
- Junk survives the uniqueness check: 32 dots normalise to the empty string and the first such statement is accepted.
  `&nbsp;`×6 and `<br>`×8 pass too.
- Repro:
  - `./lint.sh quality P0_lazy_quality.md`: `LINT PASS findings=0`;
  - `./lint.sh policy P0_lazy_policy.md`: PASS;
  - `./lint.sh quality B1a_junk_statements.md`: PASS;
  - `./lint.sh quality B1b_placeholder_statements.md`: PASS.
- Expected: L1 findings such as "ADR-0070.R9 points to R3, whose Source does not cite it" and "Source ADR-0001.R1 is
  not in the index". Actual: PASS.
- Fix (round 2 asked for the first two items):
  1. every rule ID must appear in the `Source:` of at least one R-number in its Where;
  2. every `Source:` ID must exist in the index and be a unit of the module (or appear only as `ref:`);
  3. coverage counts a rule unit only through an R-number whose Source cites it;
  4. refuse a statement with fewer than about 6 alphabetic words after removing markup, and a closed placeholder list
     (`TBD`, `TODO`, `to be compiled`, `see source`, `as stated in the source`).

**R3-B2. Accepted law can be filed under "Proposed (not law)".**
`doc_lint.py:397-399`. The trace-side L3 check runs only from a proposed unit to a law R-number. The reverse is not
checked: an accepted unit that points to an R-number under `## Proposed (not law)` or marked `[proposed]`. The body-side
check (`:481`) fires only when the line cites an accepted ID, and R3-B1 lets the Source cite nothing real.
- Repro: `./lint.sh quality B1e_accepted_as_proposed.md`. `## Rules` holds only a `Reads:` line, and all R1-R5 sit under
  `## Proposed (not law)`.
- Expected: L3 "accepted ADR-0070.R1 points to R1, stated as proposed". Actual: `LINT PASS findings=0`.
- Fix: a symmetric check in the R-number branch. An accepted unit's R-numbers must lie in `## Rules` and carry no
  `[proposed]`.

**R3-B3. Notes, which carry amendments, can all be dropped by pointing them at a heading, even one that does not exist.**
`doc_lint.py:400-404`. Any heading is accepted silently. A heading that does not exist is only a W1 warning, and the
lint still prints `LINT PASS`. Template rule 1 says every note is folded into its rule. Only `supersedes` and flagged
notes reach L5, so the other notes (relation `amends`; 81 notes in policy, 250 in master_data) can be dropped.
- Repro:
  - `./lint.sh policy B1f_notes_to_missing_heading.md`: `LINT PASS findings=0`, 85 W1 lines ("'Settlement topic' is not
    an R-number…");
  - `P0_lazy_*`: every note on `Rules`, 0 warnings.
- Expected: a finding. Actual: PASS. (Round 2, R2-B1 fix 3.)
- Fix:
  - a note's Where must be an R-number, or `not applicable: <class>` from a closed list (`credit`, `history`, `pointer`,
    `duplicate`), still capped at 15%;
  - keep headings for kind `section` (`.D*`, `.W`) only;
  - make an unknown Where part a finding, not W1.

**R3-B4. `ref:` is not checked against the rule it replaces.**
`doc_lint.py:377-386`. `ref: ADR-nnnn.Rk` accepts any ID in the index, and `ref: <module> R-<n>` accepts any known
module, `process` and `cross` included. Neither has to be the unit itself or a primary module of the unit. A `ref:` row
also removes the unit from coverage (`:410`) and from L5 and L10 (`:521`, `:529`), so a wrong `ref:` both misattributes
the rule and exempts it.
- Repro:
  - `./lint.sh quality S3a_ref_unrelated.md`: line 72 `| ADR-0075.R4 | ref: ADR-0047.R14 |` (scrap, inventory → the
    purchasing three-way match), PASS;
  - `./lint.sh quality S3b_ref_wrong_module.md`: `| ADR-0075.R4 | ref: process R-1 |`, PASS.
- Expected: an L1 or L8 finding. Actual: `LINT PASS findings=0`.
- Fix:
  - `ref: ADR-…` must equal the unit (or, for a note, its parent rule);
  - `ref: <module> R-n` must name one of `row["primary_module"]`;
  - refuse `cross` and `process` as `ref:` targets for code modules.

**R3-B5. `--module cross` passes having measured nothing.**
`doc_lint.py:286-288` and `:419`. `cross` has 75 units, 19 rules and 0 primary rules, so every rule may be `ref:`. That
leaves `rule_units` empty and the coverage check is skipped. `build_dossiers.py` writes `cross.md` next to the module
dossiers, so a compile agent can pick it up.
- Repro: `./lint.sh cross F3b_cross_zero_rules.md`. The spec has no R-number at all.
- Expected: exit 2 ("cross is not a compile target"), or a finding when a module has primary units but 0 defined
  R-numbers. Actual: `LINT PASS findings=0`.
- Fix: refuse `cross` (and `process` unless asked) in `main`; fail when `defined` is empty while the module has any rule
  unit.

**R3-B6. A malformed CONFLICT or OPEN entry disappears from the REVIEW LIST without a finding.**
`doc_lint.py:488-491`: `ENTRY_RE.search` fails and the line is skipped. Only entries the lint itself requires are caught,
because they are then "missing". A conflict the compiler finds on its own, which is exactly what template rule 2 asks it
to record, vanishes when it is written in any other shape. Entries outside `## Conflicts` are ignored too.
- Repro: `./lint.sh policy B2b_unparsed_entries_dropped.md`. Its `## Conflicts` has 4 extra entries:
  - `CONFLICT: ADR-0043.R5 …`;
  - `**CONFLICT** ADR-0029.R14: …`;
  - `| CONFLICT | ADR-0042.R7 | … |`;
  - `Conflict ADR-0055.R2: …`.
- Expected: each is a finding, or appears in the review list. Actual: PASS, REVIEW LIST 10 entries, none of the 4.
- Fix: every non-blank visible line of `## Conflicts` must parse as an entry, or be the literal `None.`; otherwise L5.
  Also flag `CONFLICT|OPEN|FALSE-POSITIVE` followed by an ID anywhere outside `## Conflicts`.

**R3-B7. A superseded rule can be stated in its old form with a passing CONFLICT, and W3 cannot see it.**
`doc_lint.py:513-515` and `:535-538`. `governs()` accepts any CONFLICT reason that contains an R-number. W3 tests only
whether the R-number's text (Source included) contains the superseding ID, so citing it in `Source:` silences W3.
- Repro: `./lint.sh ledger S6a_superseded_old_text.md`. Line 18 is `R1. Locks are taken in the order of ADR-0026
  rule 14: period, then account, then document. Source: ADR-0026.R14, ADR-0027.R10`; line 65 is
  `CONFLICT ADR-0026.R14: R1 governs this case as written in the spec`.
- Expected: at least W3. Actual: `LINT PASS findings=0`, 0 warnings.
- Severity: this is R2-S6, raised to BLOCKING because the spec states superseded law as current. That case is in the
  BLOCKING definition, and nothing mechanical or procedural now catches it.
- Fix:
  - W3 should test the statement only (strip `Source:`) and become a finding;
  - the superseded ID must not be the only ID the R-number cites;
  - template acceptance step 2 must add "every L10 rule and every `supersedes` note is in the spot-check".

### SHOULD-FIX

**R3-S1. L4 counts: 13 of 14 fresh forms pass.**
`doc_lint.py:95-98` and `:556-572`.
- Repro: `./lint.sh quality S2a_counts.md`. The result is `LINT FAIL findings=1`, and that one finding is
  `sixteen tables` (line 28).
- These pass: `**16** tables`, `16 *tables*`, `16-table module`, `16 owned-tables`, `16`+U+200B+` tables`,
  `16 [tables](#…)`, `Owned tables (16)`, `Tables owned — 16`, `| 16 | owned tables |`, `XVI commands`,
  `` `16` tables ``, `16<br>tables`, `16`+U+2060+`tables`.
- Fix: before matching, strip markdown emphasis, links, backticks, `<br>` and zero-width characters (U+200B-U+200D,
  U+2060, U+FEFF), and treat `-` as a space. Add `(N)` after a noun, an em dash or en dash as a separator, and a number
  cell before a noun cell.

**R3-S2. L3: proposed notes and sections skip L3; 5 citation forms are not parsed.**
`doc_lint.py:400` (heading branch, no L3) and `nfdocs.py:72-76`.
- Repro: `S1a_prop_forms.md` linted with `--index idx-prop3.csv` (ADR-0070 set to proposed) gives 3 L3 findings (lines
  22, 24, 26).
- Not parsed:
  - line 14 `ADR-0070 (rule 12)`;
  - line 16 `ADR 0070 rule 12`;
  - line 18 `rule 12 in ADR-0070`;
  - line 20 `ADR-0070 §12`;
  - line 28 `ADR-0070 Rule 12`.

  `rules 12 through 14` yields only R12.
- `ADR-0070.R15.N1` and `ADR-0070.D0` traced to `Rules` raise nothing.
- Latent: all ADRs are accepted today.
- Fix: make `rule` case-insensitive; accept `(rule N)`, `in`, `through` and a missing hyphen. A proposed note or section
  needs an R-number under Proposed, or `[proposed]`.

**R3-S3. Duplicate R-numbers and chunk numbering are not checked.**
`doc_lint.py:192` (`elif n not in self.defined`: a second `R2.` in the same file is silently ignored), `:294-295`
(`setdefault` across chunks: the first chunk wins), and `:320` (`Chunk` is checked by regex only).
- Repro:
  - `./lint.sh quality B1g_duplicate_R_in_file.md`: R2 is defined twice, PASS;
  - `./lint.sh quality F2_chunk_a.md F2_chunk_b.md`: both chunks say `Chunk: 1 of 2`, R1-R5 have different texts in each,
    PASS;
  - `F2_chunk_a.md F2_chunk_c.md`: `3 of 2`, PASS;
  - `F2_chunk_a.md F2_chunk_a.md`: the same file twice, PASS.
- Effect: `quality R-2` becomes ambiguous for other specs (template rule 6). A trace row resolves to whichever chunk
  came first.
- Fix: a duplicate R-number in the module's files is an L1 finding. Chunks must be `1..m of m`, each once, with one `m`.
  Refuse duplicate paths.

**R3-S4. L2 and L9 accept names a reader never sees, and the template's content sections may be empty.**
`doc_lint.py:429` builds the code spans from `s.lines` (raw), not `s.vis`.
- Repro: `./lint.sh quality F7_reads_in_comment.md`. The only mention of the 10 owned tables, the rows and the settings
  is `<!-- Reads: … -->`. PASS.
- In P0 a `Reads:` line (a list meant for **other** modules' tables, template section 2) satisfies L2 for owned tables.
  `Entities and tables`, `Commands and queries`, `Invariants`, `Edge cases`, `Settings` and `UI annotations` are empty,
  and the spec still passes.
- Fix:
  - use the masked lines;
  - require owned tables in `## Entities and tables` outside `Reads`, owned INV and EC rows in their sections, and owned
    settings in `## Settings`;
  - a content section is non-empty or says `None (<reason>)`.

**R3-S5. The index commit check is soft.**
`doc_lint.py:306-312` and `:326`.
- At review time the worktree's index differed from its commit (builder edits, uncommitted). The live run
  `python tools/docs/doc_lint.py …/P0_lazy_quality.md --module quality` (no `--index-commit`) printed
  `LINT PASS findings=0` plus W0. The spec was linted against an index whose IDs or modules may differ from the commit
  it names.
- `--index-commit c9d57fe0000` (not a commit) also passes, because the check is `sha.startswith(given)` with the
  caller's string.
- The `#stable_key` is optional, and a mismatch is W2 only (`S4a_stale_key.md`: PASS, with "ADR-0043.R4.N2
  #a457f6031f06 … that text is now ADR-0047.R9").
- Fix:
  - W0 becomes an L0 finding;
  - resolve `--index-commit` with `git rev-parse --verify`;
  - make W2 a finding;
  - consider requiring the key on note rows, since note IDs are positional.

**R3-S6. Conflict entries: the parent covers notes; OPEN needs no real question; reasons can be noise; any ID can be
entered.**
`doc_lint.py:499`, `:504-511`, `:522` and `:526`.
- Repro: `./lint.sh policy B2c_open_fake_oq_parent_fp.md`:
  - `FALSE-POSITIVE ADR-0029.R14: <gibberish>` silences the flagged note `ADR-0029.R14.N5`, which says it "is recorded as
    a conflict for the author". The chief architect sees an FP on a rule, not on the note;
  - every `supersedes` note and superseded rule is `OPEN …: OQ-99999`, and no such question exists;
  - PASS.
- `./lint.sh policy B2a_flood_every_id.md`: 154 entries, all with distinct gibberish reasons, PASS.
- The CONFLICT reason reuse cap does not exist; it covers FP only.
- Fix:
  - the entry must name the unit itself (the parent only for `supersedes` notes, and only as CONFLICT);
  - `OQ-n` must exist in `docs/open-questions.md`;
  - entries only for IDs the lint requires (or flagged), the others a finding;
  - apply the reuse cap to CONFLICT too;
  - a reason must contain at least 4 dictionary words (or name an ID or R-number).

**R3-S7. A spec may trace another module's rules as its own law.**
`doc_lint.py:351-356`. Trace IDs outside the module's units are accepted.
- Repro: `./lint.sh quality F1_foreign_rules.md`: `| ADR-0047.R9 | R1 |` … R15 (purchasing only). PASS.
- Not blocking: the owner's spec must still trace them. The harm is two divergent statements, against template rule 6.
- Fix: L7 or L1 finding "not a unit of module quality; use ref: or drop it".

**R3-S8. `~~~` fences and indented code blocks are not masked.**
`doc_lint.py:120-152` and `:107`.
- Repro: `./lint.sh quality B1c_tilde_fence_defs.md` and `B1d_indented_code_defs.md`. All R-numbers sit in a `~~~` block
  or a 4-space indented block, which a reader sees as code. PASS.
- The same applies to `F6_trace_in_tilde_fence.md`, with the trace rows inside `~~~`.
- Fix: mask `~~~` fences, and indented blocks after a blank line. Anchor `RULE_DEF_RE` at column 0, or at most 3 spaces
  after a list marker.

**R3-S9. Module routing: further misroutes in the sample** (section 3). ADR-0050.R45 → `query`; ADR-0064.R25 (and
R5, R9, R10, R12) → `production`; ADR-0015.R7 → `master_data` (probable). Not in the known list being fixed.

### NOTE

- **N1.** `MIN_RULE_TEXT = 30` (`doc_lint.py:78`). The docstring (`:23`) and the README (line 135) say 40 characters.
- **N2.** Front matter is read from raw lines, so a front matter inside `<!-- -->` satisfies L0 (`F5_front_in_comment.md`:
  PASS). CRLF files lint the same as LF (`F8_crlf.md`: PASS, correct).
- **N3.** The working-tree overrides make ADR-0047 R1, R2, R16 and R21-R23 primary in 2 or 3 modules. `ref:` is refused
  wherever a module is primary, so each of those specs must restate the rule. That works against template rule 6
  ("never restated") and produces two or three copies to keep equal. Decide which module states it and let the others
  `ref:`, or document the duplication.
- **N4.** `ReviewProbes.test_probes_fail` depends on the lab folder and on the live default index. On another machine it
  is skipped, and on this one it moves with uncommitted index edits.
- **N5.** Warnings never affect the exit code or the first line. A compile agent that reads only `LINT PASS` ignores W1,
  W2 and W3 (85 W1 lines in `B1f`). Consider `--strict` (warnings are findings) for the S4 gate.
- **N6.** Empty file (`F4_empty.md`: 84 findings), wrong `--module` (L0) and an unknown module (exit 2) are all handled
  correctly.

## 3. Module routing sample

Seed `random.Random(4421).sample(sorted(rule IDs), 20)` over the 1,657 IDs of kind `rule` in the committed index
(`c9d57fe`). The sample:

ADR-0050.R45, ADR-0075.R4, ADR-0016.R2, ADR-0076.R6, ADR-0020.R3, ADR-0014.R11, ADR-0008.R15, ADR-0042.R19, ADR-0067.R19,
ADR-0015.R7, ADR-0033.R15, ADR-0012.R1, ADR-0041.R7, ADR-0061.R3, ADR-0064.R25, ADR-0022.R15, ADR-0023.R17, ADR-0046.R17,
ADR-0008.R3, ADR-0079.R4.

Right: 17 of 20. Misroutes:

| Rule | Index primary (modules) | Should be | Reason |
| --- | --- | --- | --- |
| ADR-0050.R45 | `agent_runs` (agent_runs) | `query` | It covers view declarations (columns, scope columns, `Get<View>`), and ADR-0050 rule 1's table gives `query` "the views, their declarations … `List<View>` and `Get<View>`". The `query` dossier does not even contain it. The same holds for the whole **Query layer** group, R42-R54 (lines 419-515). The **LLM gateway** group R2-R7 likewise belongs to `agents` by rule 1. All of ADR-0050 is `agent_runs`. |
| ADR-0064.R25 | `agents` (agents; production) | `production` | `ImportOperationConfirmation` is "(module `production` …; an integration, not an agent; on no tool list)". The same "module `production`" text is in R5, R9, R10 and R12. R9 and R10 do not reach `production` at all (modules agents; inventory). The working-tree override fixes R6 only. |
| ADR-0015.R7 | `ledger` (ledger; master_data) | `master_data` (or both) | It defines the entity `item_group` and "each item has one item group". The table is in DS-20-master-data.sql, owned by `master_data`. Probable: account determination reads it, but the definition belongs to the owner's spec. |

Judged right with a comment:
- ADR-0061.R3 (GS1 validation in `nativeflows.gs1`, a pure core library, has no module in ADR-0022 rule 2;
  `master_data` is acceptable);
- ADR-0076.R6 (`work`, which owns `notification`);
- ADR-0016.R2 (`localization`; `company` columns are shared to master_data).

## Not checked

- The semantic content of the uncommitted overrides beyond the three rule families above.
- Token measurement of bytes ÷ 3.5.
- `build_index` determinism (not re-run: the worktree's index was being changed by someone else).
- Whether the ADR-0064 family and ADR-0050 groups have more members outside the rules named above.
