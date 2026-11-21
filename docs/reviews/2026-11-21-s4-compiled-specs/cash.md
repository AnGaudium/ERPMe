# Review: compiled spec `cash` (S4)

Spec files: `specs/cash-1.md` (R1 to R31), `specs/cash-2.md` (R201 to R260). Index 30d5706. Reviewer: Claude Opus 5.5
(a different model from the compiler, Claude Fable 5.2), 2026-11-21. Brief: `review-brief.md`. Spot check N=20, seed 3101.

## Verdict

**FAIL: 0 BLOCKING, 3 SHOULD-FIX, 5 NOTE.** The law is stated correctly. All 20 sampled units are faithful, all 13
CONFLICT resolutions pick the right governing text, and the DDL and catalogs agree with what the spec presents as
existing. The bar is 0/0, so the module does not pass until the three SHOULD-FIX items are closed. Each takes a
one-sentence edit; none changes behavior.

## 1. Lint

`doc_lint.py specs/cash-1.md specs/cash-2.md --module cash`: `LINT FAIL findings=1`. The only finding is
`L2 cash-1.md:0: owned catalog row invariants:INV-101`. This is the known false positive: the example token
`INV-0101-2` in ADR-0048.R9.N3 makes the lint treat `INV-101` (area `production`, ADR-0033.R16) as owned by `cash`.
It is harmless: no `cash` rule concerns INV-101, and the spec rightly does not mention it. Counts: units 77, rules 40,
notes 36, R-numbers 91, trace rows 77, all units traced. Sizes ~11,852 and ~12,549 tokens (under 16,000). Retention 99%
and 98%. REVIEW LIST: CONFLICT 13, FALSE-POSITIVE 0, OPEN 0. SUPERSEDED RULES: 0. STABLE-KEY MISMATCHES: 0.

## 2. Seeded spot check (N=20, seed 3101)

Population: 63 source IDs whose trace `Where` holds R-numbers (both chunks; `ref:` rows excluded).
`random.Random(3101).sample(sorted(ids), 20)`. For each I read the rule with all its notes and any rule a note or
Conflicts entry names (ADR-0063.R10, ADR-0065.R12, ADR-0028.R16, ADR-0069.R8, ADR-0074.R4, the DDL).

| # | Source | R-numbers | Verdict |
| --- | --- | --- | --- |
| 1 | ADR-0052.R21 | R209, R210 | FAITHFUL |
| 2 | ADR-0059.R10 | R240-R245 | FAITHFUL (the open question on bank fees is answered per R10.N1; "among its 300" goes through the setting, ADR-0063.R10) |
| 3 | ADR-0048.R4 | R10 | FAITHFUL (TT99 3381/1381 neutralized to flagged package content) |
| 4 | ADR-0048.R1 | R1, R2 | FAITHFUL |
| 5 | ADR-0059.R6.N1 | R239 | FAITHFUL |
| 6 | ADR-0051.R19 | R230-R233 | FAITHFUL ("a person submits it" correctly dropped per R19.N1) |
| 7 | ADR-0048.R8.N2 | R17 | FAITHFUL |
| 8 | ADR-0048.R3 | R5, R7, R8, R9 | FAITHFUL (DDL columns and ADR-0028.R16 snapshot cited) |
| 9 | ADR-0048.R12.N1 | R30 | FAITHFUL |
| 10 | ADR-0048.R17.N1 | R206-R208 | FAITHFUL (one minor drop, cash-N1) |
| 11 | ADR-0059.R6 | R236-R238 | FAITHFUL |
| 12 | ADR-0048.R13.N1 | R31 | FAITHFUL |
| 13 | ADR-0048.R9.N4 | R7 | FAITHFUL |
| 14 | ADR-0051.R18.N3 | R227, R228 | FAITHFUL (300 at 99% is the default of `auto_post.max_error_rate`, confirmed in ADR-0063.R10 and `settings.csv`) |
| 15 | ADR-0048.R13 | R31 | FAITHFUL |
| 16 | ADR-0059.R10.N1 | R243, R245 | FAITHFUL |
| 17 | ADR-0063.R9 | R250-R252 | FAITHFUL |
| 18 | ADR-0048.R2 | R4 | FAITHFUL |
| 19 | ADR-0048.R9 | R17-R22 | FAITHFUL (scores and caps per R9.N2 and R9.N3; outcome per R9.N1) |
| 20 | ADR-0048.R6 | R12, R13 | FAITHFUL |

**Error rate: 0 of 20 (0%).**

Reverse check: `random.Random(3101).sample(sorted(R-numbers, numeric), 10)` gave R223, R5, R234, R216, R20, R204,
R28, R245, R26, R207. Every clause has a source in the cited units or carries its own citation (R5's
`bank_statement_line_id` is cited as an interim DDL column, the snapshot as ADR-0028.R16). One finding: R216 is
sourced, but its exhaustive "are" is incomplete as current law (cash-S1).

## 3. Superseded rules, conflicts, false positives

SUPERSEDED RULES: none listed. FALSE-POSITIVE entries: none. The 13 CONFLICT entries:

| Conflict | Resolution right? |
| --- | --- |
| ADR-0048.R1 | Yes. `money_transfer` added (R1.N3); neutral type names (R1.N1). |
| ADR-0048.R3 | Yes. Optional settlement rate (R3.N1) stated in R5, R9, R26. |
| ADR-0048.R8 | The resolution is right on substance. The wording ranks the DDL as "later" than the ADR, which is not a rule of precedence (cash-N2, SOURCE-1, SOURCE-2). |
| ADR-0048.R9 | Yes. Each note checked against R18, R20 to R23. |
| ADR-0048.R12 | Yes. |
| ADR-0048.R13 | Yes. |
| ADR-0048.R20 | Yes. Regime alternatives (R20.N1) in R214. |
| ADR-0051.R18 | Yes. |
| ADR-0051.R18.N4 | Yes. |
| ADR-0051.R19 | Yes. |
| ADR-0051.R19.N1 | Yes. |
| ADR-0059.R10 | Yes. |
| ADR-0063.R8 | The bound resolution is right. The entry misstates the catalog: `EC-183` already expects `must_reject:setting_out_of_bounds\|must_succeed` (cash-S3). R247 keeps a stale open question (cash-S2). |

## 4. Consistency with design files

DDL (`DS-05-platform.sql`): every column, key and check value the spec names for `money_account`, `payment`,
`payment_line`, `bank_statement`, `bank_statement_line`, `open_item_collection` and `payment_method_money_account`
exists as stated (including `proposal_score`, `match_*`, `suggested_*`, `bank_transaction_code`, the `match_basis`
and `match_parameter_state` checks, `NULLS NOT DISTINCT`, `trg_payment_line_payment_block`'s function). The two
ADR/DDL differences (`score` against `proposal_score`; `company_rule_account` missing from the `match_basis` check) are
disclosed in R15, R243 and Conflicts, not hidden: SOURCE-1, SOURCE-2.

Catalogs: the authorization leaves (`authorization-areas.csv`), INV-94 to INV-98, INV-501, INV-705
(`invariants.csv`), EC-52, EC-72 to EC-78, EC-82, EC-163, EC-165, EC-168, EC-182 to EC-184, EC-263
(`edge-cases.csv`), `bank_line_unmatched` (`work-item-kinds.csv`) and the five `cash.*` setting rows plus
`auto_post.max_error_rate` (`settings.csv`) match. The spec's claim that `cash.bank_account_cooling_days`,
`cash.small_difference_limit`, `cash.netting_requires_agreement`, `cash.dunning.levels`,
`cash.bad_debt_provision.buckets` and `fx.document_rate.allowed` have no row is true. Every error code and check
result the spec names exists in `DS-04-command-envelope.md`.

## 5. Sections 2, 3, 5 to 8

No invented authorization area, event, error code or setting. The leaves assigned to `ImportBankStatement`,
`MatchBankLine`, `UnmatchBankLine` and `RunDunning` come from the catalog meanings ("Statement import, matching",
"Dunning and collections"), and the verb levels are honestly "not stated". The chunk 2 "Reads" line under Settings
lists settings that no `cash` rule reads (cash-N3).

## Findings

### BLOCKING

None.

### SHOULD-FIX

- **cash-S1**, `cash-2.md:121`, R216; source ADR-0048.R20 with ADR-0048.R12.N1 and ADR-0048.R17.N1. The source's
  catalog bullet lists eight errors. Its later notes add `money_transfer_currency_mismatch`,
  `money_account_line_not_allowed` (R12.N1) and `open_item_payment_blocked` (R17.N1). The spec says "The error codes
  of ADR-0048 are" the eight, which reads as the full current list and leaves out three codes the spec itself uses in
  R7, R30 and R208. Fix: add the three note codes to R216 with their source notes, or reword it to "ADR-0048.R20's
  catalog lists".
- **cash-S2**, `cash-2.md:239`, R247; source ADR-0063.R8.N1 against ADR-0065.R12 (review note, 2026-11-21). R247
  says "The new wording of spec 03 rule 1 is the author's (open question)". ADR-0065.R12, which R247 cites, says spec
  03 rule 1 was reworded and applied on 2026-11-21. `docs/open-questions.md` marks both entries answered, and
  `spec/03-agent-safety.md` has the new lead-in. Fix: replace the parenthesis with "spec 03 rule 1 was reworded on
  2026-11-21 (ADR-0065.R12)" and add a Conflicts entry for ADR-0063.R8.N1 naming ADR-0065.R12.
- **cash-S3**, `cash-2.md:344`, Conflicts entry ADR-0063.R8; source `edge-cases.csv` EC-183. The entry says the
  catalog row "still expects `must_reject:setting_out_of_bounds`". The catalog's `expected_outcome` is
  `must_reject:setting_out_of_bounds|must_succeed`, as the spec's own EC-183 row (line 309) shows. Only the
  description text is stale (SOURCE-4). Fix: say that the row's description still describes the refusal under the
  false bound, and that its outcome already allows `must_succeed`.

### NOTE

- **cash-N1**, `cash-2.md:79-86`, R206 to R208; source ADR-0048.R17.N1. The lab check reference
  `t15_platform_ddl.py` L01 to L05 is dropped. It is not behavior, but it is an identifier R220 does not cover.
  Fix: add it to R208 after `INV-98`.
- **cash-N2**, `cash-1.md:324`, Conflicts ADR-0048.R8. "the DDL, which is later" ranks a design file over an ADR,
  which the compile rules do not allow. The result is disclosed, so nothing is hidden. Fix: say that the ADR's `score`
  is the DDL column `proposal_score` (SOURCE-1) instead of calling the DDL later.
- **cash-N3**, `cash-2.md:329`, Settings "Reads". `data_processing.policy`, `data_processing.never_send_fields`,
  `extensions.wasm_enabled` and the four `intake.duplicate.*` keys come from the units traced `ref:`
  (ADR-0050.R9, ADR-0063.R27, ADR-0063.R8's dropped comparison). No `cash` rule reads them. Fix: label them "named by
  the shared units traced `ref:`", or drop them if the lint allows.
- **cash-N4**, `cash-1.md:206`, R23; source ADR-0048.R9.N5. The list "the scores 95, 100, 80, 90, 60 and 70" copies
  the source exactly, but after R9.N3 the value 90 is both step 3's score and step 2's single-item score. ADR-0059.R5
  has a parameter only for the first (SOURCE-5). The copy is faithful, so this is only a pointer.
- **cash-N5**, `cash-1.md:37`. `IgnoreBankLine` says "area not stated" while `MatchBankLine` and `UnmatchBankLine`
  take the leaf `bank_statement` from the catalog meaning. Fix: treat the three the same way.

## SOURCE findings (do not count against the spec)

- **SOURCE-1**: ADR-0048.R8.N1 names the proposal's score `score`. DDL `bank_statement_line` names it
  `proposal_score`.
- **SOURCE-2**: ADR-0059.R10 (and R243) names the match basis `company_rule_account`. The DDL check
  `ck_bank_statement_line_match_basis` does not list it.
- **SOURCE-3**: ADR-0063.R8.N1 still calls the rewording of spec 03 rule 1 an open question. ADR-0065.R12 (review note,
  2026-11-21) and `open-questions.md` say it was applied on 2026-11-21.
- **SOURCE-4**: The EC-183 description in `edge-cases.csv` still says a proposal to enable
  `cash.auto_post.accept_llm_originated_rules` is refused with `setting_out_of_bounds` while bounded false. ADR-0065.R12
  lifted the bound. Its `source` column names only ADR-0063 rule 8.
- **SOURCE-5**: ADR-0048.R9.N3 adds a step 2 single-referenced-item score of 90. ADR-0059.R5 declares no parameter for
  it (`score_account_amount` is step 3), so that score cannot be tuned and is not covered by the order constraints.
- **Tool**: lint L2 reads the example token `INV-0101-2` in ADR-0048.R9.N3 as `INV-101`, which makes the joint lint
  `LINT FAIL findings=1`.
