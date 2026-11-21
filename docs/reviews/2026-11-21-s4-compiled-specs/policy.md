# Review: compiled spec `policy` (S4)

Spec files: `specs/policy-1.md` (R1 to R37), `specs/policy-2.md` (R201 to R241), `specs/policy-3.md` (R401 to R453),
`specs/policy-4.md` (R601 to R661). Index 30d5706. Reviewer: Claude Opus 5.5 (a different model from the compiler, Claude
Fable 5.2), 2026-11-21. Brief: `review-brief.md`. Assignment: spot check N=20, seed 3102, plus the segregation-of-duties
tension between chunk 2 (R208, R209) and chunk 3 (R421, R447, `INV-225`).

## Verdict

**FAIL: 1 BLOCKING, 3 SHOULD-FIX, 5 NOTE.** The 20 sampled units are all faithful, and 31 of the 32 CONFLICT resolutions
are right. The module still fails on the tension the integrator left open. Chunk 3 restates ADR-0055.R7's "the agent-run
part of condition 5 is never lifted" as current law. The later ADR-0067.R16 narrowed that sentence, and chunk 2 states the
narrowing (R209), so the compiled spec contradicts itself. The bar is 0/0. The module passes once pol-B1 and pol-S1 to S3
are closed. Each needs one or two sentences.

## 1. Lint

`doc_lint.py specs/policy-1.md ... policy-4.md --module policy`: `LINT PASS findings=0`. The run measured 148 units, 76
rules, 68 notes, 188 R-numbers and 148 trace rows. Retention is 93%, 99%, 99% and 100%. Policy-1's lowest is ADR-0029.R16
(1/12): its INV/EC statements are moved to the catalog tables, which is expected. REVIEW LIST: CONFLICT 32,
FALSE-POSITIVE 0, OPEN 0. SUPERSEDED RULES: 1 (ADR-0009.R11 by ADR-0029.R6). STABLE-KEY MISMATCHES: 0.

## 2. Seeded spot check (N=20, seed 3102)

Population: the 127 source IDs whose trace `Where` holds R-numbers (`ref:` rows excluded).
`random.Random(3102).sample(sorted(ids), 20)`. For each ID I read the whole rule with all its notes, plus the later units that
its Conflicts entry or notes name.

| # | Source | R-numbers | Verdict |
| --- | --- | --- | --- |
| 1 | ADR-0043.R5.N1 | R27 | FAITHFUL |
| 2 | ADR-0065.R6 | R621, R622 | FAITHFUL |
| 3 | ADR-0055.R1 | R235-R237 | FAITHFUL |
| 4 | ADR-0043.R15.N4 | R220, R221 | FAITHFUL |
| 5 | ADR-0043.R10 | R201 | FAITHFUL (inline ADR-0053.R8 amendment folded) |
| 6 | ADR-0028.R14 | R11 | FAITHFUL (rank comparison replaced by stages, R14.N1) |
| 7 | ADR-0055.R7.N3 | R422 | FAITHFUL (open question closed by R7.N4) |
| 8 | ADR-0065.R16 | R651-R653 | FAITHFUL |
| 9 | ADR-0055.R5.N1 | R412 | FAITHFUL (interim flag kept) |
| 10 | ADR-0029.R4.N1 | R4 | FAITHFUL (editorial note; the sentence reads as the rule's end) |
| 11 | ADR-0055.R20 | R447 | FAITHFUL (see section 4: its cases have no agent draft) |
| 12 | ADR-0043.R18.N1 | R227 | FAITHFUL |
| 13 | ADR-0055.R4 | R406-R409 | FAITHFUL (`position` from R4.N1 in R407) |
| 14 | ADR-0065.R15 | R650 | FAITHFUL |
| 15 | ADR-0029.R11 | R12 | FAITHFUL (R11.N1 limit and the gateway exception of ADR-0043.R9.N2) |
| 16 | ADR-0043.R8 | R10 | FAITHFUL |
| 17 | ADR-0051.R18.N4 | R234 | FAITHFUL |
| 18 | ADR-0043.R12.N1 | R206 | FAITHFUL (ADR-0063.R3.N2 and ADR-0067.R9 setup path; `auto_post.*` excluded per ADR-0065.R8) |
| 19 | ADR-0065.R7 | R623-R627, R624a | FAITHFUL |
| 20 | ADR-0043.R6 | R29 | FAITHFUL |

**Error rate: 0 of 20 (0%).** The blocking defect, pol-B1, is in a unit the sample did not draw (ADR-0055.R7, stated in R421).

Reverse check: `random.Random(3102).sample(sorted(R-numbers, numeric), 10)` drew R438, R618, R407, R210, R1, R25, R653,
R416, R658 and R10. All ten are clean. Every clause has a source in the cited units, and nothing is imported from an uncited
rule. R1 joins ADR-0043.R1, its notes N1 and N2, and ADR-0029.K.N1, and all four are cited.

## 3. CONFLICT, SUPERSEDED and FALSE-POSITIVE entries

I read all 32 entries against their sources. 31 of them are right: the later source wins, and the statement holds the
superseding text. Highlights:

- **ADR-0009.R11 → ADR-0029.R6 (SUPERSEDED)**: right. R7 lists the policy points with R6.N1's actor-kind point and R6.N2's
  `Issue` from `draft`/`approved` split. The `approval` row content stays with `documents` (R1, ref).
- **ADR-0043.R2, R2.N1, D0; ADR-0043.R15; ADR-0055.R5**: right. The procedure keeps `code`, `name`, `rank`, `basis`,
  `is_active` (DDL: `rank > 0`, `basis` interim). The roles live on the stages (R16, R219, R411, R412).
- **ADR-0043.R13, R13.N1, R13.N2**: right as far as they go. The interim "a person may approve their own document" is
  gone, and `policy_no_eligible_approver` is retired (DS-04 marks it retired). The entries miss ADR-0067.R16 (pol-B1).
- **ADR-0043.R9 with N1, N2, N3; ADR-0029.R11; ADR-0029.R16; ADR-0065.R12**: right. R36 and R640 state the gateway
  exception to floors 3 and 5. Floor 10 is in R34, and the e-invoice completion `Post` is excluded (R35, R37). `INV-84` is in
  its restated form.
- **ADR-0029.R4 / ADR-0043.R12**: right. The bank-account rule is confirmed for every company by the 2026-11-19 note and
  ADR-0043.R9.N3. The "interim" mark is dropped (R5, R205).
- **ADR-0043.R14 and N1 to N5; ADR-0051.R18 and N3, N4; ADR-0063.R10 → ADR-0065.R16**: right. The evidence floor goes
  through `auto_post.max_error_rate`, the window through `auto_post.confirmation_cadence`, and the suspension widens to the
  document type for gateway postings (R608 keeps the rule-version scope for the rest).
- **ADR-0055.R2, R2.N1, R2.N3; ADR-0043.R17.N1; ADR-0043.R19.N1; ADR-0055.R7.N3; ADR-0065.R1.N1; ADR-0065.R5; R8**: right.
- **ADR-0029.R13**: not resolved, although the sources can be ordered (pol-S3).

**Missing Conflicts entries**: ADR-0055.R7 against ADR-0067.R16 (pol-B1), and ADR-0029.D0 against ADR-0029.R14.N6 (pol-S2).

## 4. The segregation-of-duties tension (R208, R209 against R421, R447, `INV-225`)

**What the sources say.**

- ADR-0055.R7 (accepted 2026-11-15), "Small companies": in the small-company mode, condition 5 is lifted for the human
  writers, with an exception row. "The agent-run part of condition 5 is a hard floor and is never lifted, and neither is
  condition 6." Its notes N1 to N4 do not touch this sentence. ADR-0055.R18 gives the same text for `INV-225`.
- ADR-0067.R16 (accepted 2026-11-21, later) reads spec 03 rule 5's "the person who triggers" as the human whose own act
  started the run. It calls the rest of ADR-0017.R16's check "stricter than the floor" and lets the small-company mode
  relax that stricter part. All of these must hold:
  - every agent run that wrote a version for the approver was started by an event or schedule;
  - the approved version has no effective taint (never tainted, or cleared by `ClearTaint`, self-clearance included,
    ADR-0054.R20.N4);
  - the approver holds the `owner` or `chief_accountant` role template and is eligible for the stage (ADR-0055.R7).

  The approval writes a `segregation_exception` of kind `own_agent_draft_approval` and joins the period review. A run the
  approver started by their own act is still refused.
- The same change is noted on ADR-0017.R16 (N1), on ADR-0054.R20 (N2, N4: "Under that reading the floor of 'what it never
  relaxes' stands") and on ADR-0043.R13 (N3). `INV-803` checks it. The DS-15 DDL accepts the kind `own_agent_draft_approval`.
  ADR-0055.R7, ADR-0055.R18, and the catalog rows `INV-225` and `INV-17` received no note.

**Which statement is right.** ADR-0067.R16 is the later accepted source, so it governs over ADR-0055.R7's sentence.

- **R209** is right. It follows ADR-0043.R13.N3, but leaves out some conditions (pol-N1).
- **R421** is wrong as written. "Never lifted" now holds only for the floor, meaning runs the approver started by their own
  act. Runs started by an event or schedule are lifted under the conditions above.
- **The `INV-225` row** copies a stale catalog statement ("the agent-run part has no exception"). The approvals that
  ADR-0067.R16 allows would break it.
- **R447** is right. ADR-0055.R20's walk-throughs involve no agent draft, so ADR-0017.R15 and R16 (with R16.N1) hold in all
  of them. The spec also, correctly, drops the source's absolute gloss "the human an agent run acted for never approves
  its drafts".
- **R208** keeps a clause of the interim that ADR-0043.R13.N1 replaced: segregation "applies to every company, with the
  recorded exception of R209". It leaves out the human-writer lift of R421 (pol-S1).

**Does the spec contradict itself?** Yes. R208 and R209 allow an owner or chief accountant to approve an agent draft written
for them. R421 and the `INV-225` row say that the agent-run part of condition 5 has no exception. No Conflicts entry
reconciles them.

**The law, in the small-company mode** (`permissions.small_company_mode` on, at most two posting or approving users):

1. Condition 5 is lifted for the document's human writers, with a recorded exception (ADR-0055.R7; ADR-0054.R20).
2. Condition 5 is also lifted for an agent run that acted for the approver, under these conditions:
   - every such run was started by an event or schedule;
   - the version has no effective taint (never tainted, or cleared by `ClearTaint`, self-clearance included);
   - the approver holds `owner` or `chief_accountant` and is stage-eligible;
   - the approval records `own_agent_draft_approval` and joins the period review (ADR-0067.R16; `INV-803`).
3. Never lifted: a run that the approver started by their own act (start command, note or message, handed work item),
   a tainted version, condition 6, `human_only`, and `approver_is_submitter` on promotions and setting loosenings.
4. Outside the mode nothing is lifted.

## 5. Findings

### BLOCKING

- **pol-B1**: `policy-3.md:132` (R421) and `policy-3.md:279` (`INV-225` row); source ADR-0055.R7 against ADR-0067.R16
  (with ADR-0017.R16.N1, ADR-0054.R20.N2/N4, `INV-803`). R421 says the agent-run part of condition 5 "is never lifted".
  The later ADR-0067.R16 lifts its stricter part (event- or schedule-started runs, untainted version, `owner` or
  `chief_accountant`, kind `own_agent_draft_approval`) and keeps only runs the approver started by their own act as the
  floor. This contradicts R209, and there is no Conflicts entry. **Fix:** reword R421 to "the agent-run part of condition 5
  is lifted only as ADR-0067.R16 states (R209); a run the approver started by their own act is never lifted, nor is
  condition 6". Then add `CONFLICT ADR-0055.R7: ADR-0067.R16 governs ...`, and under the `INV-225` row note that the
  catalog statement predates ADR-0067.R16, citing `INV-803` (SOURCE-1).

### SHOULD-FIX

- **pol-S1**: `policy-2.md:81` (R208); source ADR-0043.R13.N1 (replacing the interim of ADR-0043.R13). R208 keeps the
  replaced interim's "segregation of duties ... applies to every company, with the recorded exception of R209". The
  small-company mode also lifts the human-writer exclusion (R421) and turns segregation-pair refusals into exceptions
  (ADR-0054.R20). **Fix:** write "segregation of duties applies to every company; the small-company mode records the
  exceptions of ADR-0055.R7 (R421), ADR-0054.R20 and ADR-0067.R16 (R209)".
- **pol-S2**: `policy-1.md:53` (R2); source ADR-0029.D0 against ADR-0029.R14.N4 to N6 (2026-11-21) and open-questions
  lines 42, 43 and 366 (all checked). The spec says the tainted read floor "stays the literal spec 03 rule 1 until the author
  decides (open question)". The chief architect decided it under delegation: the scope is not widened, and extra reads come
  only as declared projections (ADR-0029.R14.N6). Spec 03 rule 1 was reworded on 2026-11-21. **Fix:** write "the tainted
  read scope stays as ADR-0029.R14 states it (decided, ADR-0029.R14.N6)" and add `CONFLICT ADR-0029.D0`.
- **pol-S3**: `policy-1.md:106` (R13 Definition) and `policy-1.md:269` (Conflicts entry); source ADR-0029.R13 against
  ADR-0043.R14, ADR-0043.R5.N2 and ADR-0065.R7. R13 defines an auto-post as a posting by `system` only. Its own
  Confirmation bullet, R211 and `INV-87` cover `system` and `integration`. The production import posts as `integration`
  through the gateway, and "every gateway posting is an auto-post" (ADR-0065.R7). The entry says "states both as written",
  but the sources can be ordered: ADR-0043 is later by number on the same date, and ADR-0065 is later by date. **Fix:**
  define an auto-post as a posting by `system` or `integration` whose decision is `allowed` with `is_confirmation_required`
  (ADR-0043.R14; ADR-0065.R7), and change the entry to say so. If the definition is meant to stay narrow, write an OPEN
  entry instead.

### NOTE

- **pol-N1**: `policy-2.md:84` (R209); ADR-0043.R13.N3 with ADR-0067.R16 and ADR-0054.R20.N4. R209 is faithful to its unit
  but omits: the kind `own_agent_draft_approval`, eligibility for the stage, that a version cleared by `ClearTaint`
  (self-clearance included) counts as untainted, that a run the approver started by their own act stays refused, and the
  period review. Add a cite of ADR-0067.R16 for each when fixing pol-B1.
- **pol-N2**: `policy-3.md:44` (R401); ADR-0055.R3. "The database allows exactly one" default row per document type. The DDL
  (`uq_approval_pool_document_type_key`, `ck_approval_pool_document_type_default`) enforces at most one, and R402 itself
  covers a type with no row (SOURCE-5).
- **pol-N3**: `policy-4.md:209` (R643); ADR-0065.R12. "ADR-0063.R8 keeps its conditions" drops "five". This is harmless
  because ADR-0063.R8 is cited.
- **pol-N4**: `policy-1.md:121`, `policy-2.md:158` (R16, R227). The "(open question)" marks of ADR-0043.R2 (higher rank
  stands in) and ADR-0043.R18 (one person changes policy alone) are kept. Open-questions line 100 answered them
  ("keep the interim", 2026-11-19), but the ADRs have no note, so keeping them follows the brief (SOURCE-4).
- **pol-N5**: `policy-1.md:19`. The `policy_decision` key cell omits the DDL's other unique keys (`company_id`, `id`,
  `document_version_id`) and (`company_id`, `id`, `approval_pool_id`), which the `approval` foreign keys target. The table is
  not wrong, only incomplete.

## 6. Consistency with design files

I checked the spec against `DS-05-platform.sql`, `DS-15-access.sql`, `settings.csv`, `invariants.csv`, `edge-cases.csv`,
`work-item-kinds.csv`, `authorization-areas.csv`, `authorization-verb-levels.csv` and the DS-04 error table. They match:

- Columns, enums and checks of `approval_procedure`, `policy_rule`, `policy_rule_version` (boolean conditions null or true;
  `is_confirmation_required` only with `allow`; `ck_policy_rule_version_loosening` equals R21; unique
  (`company_id`, `policy_rule_id`, `version`)).
- `policy_decision`: outcome and action enums, interim actor columns, plan columns, `ck_policy_decision_auto_post` equal to
  R617 to R622; `auto_post_confirmation`.
- `approval_pool`, `approval_pool_document_type`, `approval_stage` (`due_days` 1 to 90, default 2), and
  `approval_stage_member` (`member_kind`, `position`).
- All 15 settings rows of chunk 4: type, bounds, direction, leaf, outdates, default.
- `INV-17`, 80, 82, 84 to 88, 202 to 204, 224 to 226, 230, 760 to 764; `EC-56` to 58, 112 to 115, 117, 220 to 228.
- Work item kinds `consequence_posting_blocked`, `auto_post_unconfirmed`, `auto_post_suspended`, `auto_post_review`,
  `approval_pending`, `owner_suspended`, `segregation_review_due`.
- Verb levels (`Enable`/`Disable` `full`, `Confirm` `post`, `Approve` by flag), and every error code the spec names.

Sections 2, 3 and 5 to 8 hold no invented authorization area, event, error code or setting. The "not stated" cells are
honest. The only content problem is the stale `INV-225` (and `INV-17`) statement presented without comment (pol-B1).

## 7. SOURCE findings (do not count against the spec)

1. ADR-0055.R7 ("Small companies") and ADR-0055.R18 (`INV-225`) have no ADR-0067 note. The catalog row `INV-225` still says
   "the agent-run part has no exception". That contradicts ADR-0067.R16 and `INV-803`, while ADR-0017.R16 and ADR-0054.R20
   did get notes.
2. Catalog `INV-17` ("no approved document has a version whose `agent_run_id` or `origin_agent_run_id` belongs to a run on
   behalf of the approver") has no small-company exception. An approval that ADR-0067.R16 allows, and `INV-803` requires to
   be recorded, would break it.
3. ADR-0055.R20's lead-in gloss "the human an agent run acted for never approves its drafts" is absolute. ADR-0067.R16
   narrowed it, and the ADR has no note.
4. ADR-0043.R2 and R18 still mark "(open question)" items that open-questions line 100 answered on 2026-11-19 ("keep the
   interim"). The ADRs have no notes recording the answer.
5. ADR-0055.R3 says "the database allows exactly one" default selector row. The DS-15 DDL enforces at most one.
6. ADR-0029.R13's Definition bullet (actor `system`) disagrees with its own lead-in and with ADR-0043.R14 and `INV-87`
   (`system` and `integration`), and no note reconciles them.
7. `documents.issuance_without_delay` (ADR-0053.R8), which R201, R240 and R439 read, has no row in `settings.csv`.
8. ADR-0029.D0's closing sentence still calls the tainted read floor an open question. ADR-0029.R14.N6 decided it, and D0
   has no note.
