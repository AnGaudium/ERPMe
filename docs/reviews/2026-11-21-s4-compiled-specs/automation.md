# Review: compiled spec `automation` (chunks 1 and 2)

Reviewer: Claude Opus 5.5 (compiler: Claude Fable 5.2). Date: 2026-11-21. Index: 30d5706.
Files: `OUT/specs/automation-1.md` (370 lines), `OUT/specs/automation-2.md` (364 lines).
Assignment: spot check N=20, seed 3104; plus the R213 question.

**Verdict: FAIL.** 0 blocking, 2 should-fix, 2 notes. The bar is 0 blocking and 0 should-fix. The statements that
were checked are faithful, with one exception (R213). Both should-fix items are scope and cross-reference defects,
not wrong law in the sampled units.

## 1. Lint

`doc_lint.py automation-1.md automation-2.md --module automation`: **LINT PASS findings=0**. 36 units, 29 rules,
6 notes, 116 R-numbers, 36 trace rows, all traced. Identifier retention is 100% in both files. Size ratio is 0.98 and 1.01.

- REVIEW LIST: 5 CONFLICT entries, 0 FALSE-POSITIVE, 0 OPEN.
- SUPERSEDED RULES: 0.
- STABLE-KEY MISMATCHES: 0.

## 2. Seeded spot check (N=20, seed 3104, from 36 traced source IDs)

| # | Source | R-numbers | Verdict |
| --- | --- | --- | --- |
| 1 | ADR-0058.R9 | R1-R11 | FAITHFUL |
| 2 | ADR-0065.R3 | R233-R237 | FAITHFUL |
| 3 | ADR-0065.D0 | R230 | FAITHFUL |
| 4 | ADR-0065.R1 | R231 | FAITHFUL |
| 5 | ADR-0058.R25 | R37-R40 | FAITHFUL |
| 6 | ADR-0065.R1.N1 | R232 | FAITHFUL |
| 7 | ADR-0059.R13 | R47-R52 | FAITHFUL |
| 8 | ADR-0065.R17 | R250-R252 | FAITHFUL |
| 9 | ADR-0063.R10 | R210-R213 | R210-R212 FAITHFUL. **R213: defect** (states the rule-scoped text that ADR-0065.R16 extended; see S1 and section 7) |
| 10 | ADR-0063.R11 | R214-R217 | FAITHFUL |
| 11 | ADR-0063.R20 | R220-R222 | FAITHFUL |
| 12 | ADR-0063.R21 | R223-R225 | FAITHFUL |
| 13 | ADR-0059.R27 | R201 | FAITHFUL |
| 14 | ADR-0058.R9.N1 | R10, R28, R29 | FAITHFUL |
| 15 | ADR-0059.R15 | R53-R57 | FAITHFUL |
| 16 | ADR-0058.R16.N1 | R29, R30 | FAITHFUL ("runs no action" is cited inline to ADR-0063.R21) |
| 17 | ADR-0066.R6 | R260, R261 | FAITHFUL |
| 18 | ADR-0059.R21 | R64-R66 | FAITHFUL |
| 19 | ADR-0065.R13 | R244 | FAITHFUL |
| 20 | ADR-0059.R21.N1 | R65, R66 | FAITHFUL (the window widening comes from ADR-0063.R10, cited inline) |

Error rate: 1 defective unit out of 20 (5%).

## 3. Conflicts and superseded rules

There are no superseded rules. All five CONFLICT entries are resolved correctly. ADR-0058, ADR-0059 and ADR-0063
were all accepted on 2026-11-15, so the higher ADR number wins, and each statement holds the later text:

- ADR-0058.R9: the "(flagged)" mark is dropped because R9.N1 confirms the ADR-0076 notification path and accepts the
  other choices "as written". R10 states it. Correct.
- ADR-0058.R10: `rate_limited` (ADR-0063.R21) is in R16, and `automation.dispatch_paused` (ADR-0063.R20) is in R12. Correct.
- ADR-0058.R16: the bounded settings are in R29 without the flag, and the hard rules of ADR-0063.R21 are there too. Correct.
- ADR-0058.R23: `automation.replay_window_days` and `automation.replay_min_events` are in R33 and R36. Correct.
- ADR-0059.R21: drift_action and the minimum of 30 decisions are in R65 and R66. Correct.

**Missing entry:** ADR-0063.R10 against ADR-0065.R16, which was accepted later (2026-11-21) and says it extends rule 10
"from the rule to the document type". There is no CONFLICT entry for it, and R213 does not mention it (S1).

## 4. Reverse check (10 R-numbers, seed 3104)

R15, R237, R64, R232, R48, R50, R14, R247, R38, R264: every clause has a source in the cited units. Nothing is
invented, and nothing is imported without a citation. 0 defects.

## 5. Consistency with DDL and catalogs

The following match `DS-28-34-configuration-artifacts.sql`, `DS-05-platform.sql`, `DS-04-command-envelope.md` and the CSVs:

- **Tables and columns:** `automation_scope_skip`, `automation_rule.owner_scope`, `owner_confirmed_*`,
  `automation_execution` (outcome enum including `rate_limited` and `would_act`, `action_results`, depth check 0..3),
  `outbox_event` and `audit_record` causation columns with the depth check, `artifact_transition.move` enum (all 9
  values), `window_reuse_count`, `drafted_by_filtered_run`, `drafting_reads_hash`, `is_held_out`,
  `previous_current_version_id`, `shadow_evidence_outdated_by`, the `policy_decision.auto_post_*` columns,
  `active_document_types`, `target_mode` and `evidence_setting_keys`.
- **Error codes:** all 28 codes and check results the spec names are in DS-04.
- **Settings:** the 16 rows of the chunk 2 table match `settings.csv` (scope, default, bounds, direction).
- **Work item kinds:** all 8 `automation` kinds match `work-item-kinds.csv`.
- **Invariants and edge cases:** the INV and EC rows that are present match the catalogs, including area and first step.

`is_class_filtered` and the HMAC key version are response or JSON content, and the spec does not present them as
columns. Both are fine.

## 6. Sections 2, 3, 5 to 8

The spot read found no invented authorization area, event, error code or setting. The authorization area
`automation` matches `authorization-areas.csv`. The Invariants and Edge cases sections are incomplete (S2).

## 7. The R213 question: `human_post` or `require_human`?

**Current law: ADR-0065.R16, read together with the ADR-0063.R10 bullet it extends.**

- **Precedence.** ADR-0063 (accepted 2026-11-15) says that one reversed or wrong-confirmed auto-post outdates "its
  rule version's evidence", raises `auto_post_suspended` "for the rule's owner", and that "the rule's later postings get
  `human_post`". ADR-0065 (accepted 2026-11-21) is later. Its rule 16 says it extends this "from the rule to the
  document type".
- **Wider scope.** Under ADR-0065.R16 the evidence of every enabled rule version that allows `system` or `integration`
  to post that document type is outdated in the same transaction. `auto_post_suspended` is raised for each such rule's
  owner.
- **Later candidates.** They get the gateway decision `require_human` with reason `auto_post_evidence_mismatch` (rule 5,
  item 7) until a new rule version is enabled on new evidence.
- **Applies to every auto-post path.** ADR-0065.R20 makes the bank cascade (including `bank_charge`) and the production
  import gateway instances that "share ... the document-type suspension of rule 16". So the rule-scoped reading no
  longer governs any path on its own.
- **The same notes elsewhere.** ADR-0063.R6.N1 ("a confirmed wrong auto-post suspends the whole document type") and
  ADR-0043.R14.N5 say the same.
- **The two terms do not contradict each other.** They name the same outcome at two layers. A live gateway decision
  `require_human` is stored as `policy_decision.outcome = 'human_only'` (DS-05 `ck_policy_decision_auto_post`, line
  649). `human_only` requires `human_post` true (`ck_policy_decision_human_post`, line 627). So "later postings get
  `human_post`" is still true. It is the policy-layer name, and it is incomplete in scope.
- **The catalog row is right.** The `auto_post_suspended` row ("later candidates get require_human
  (auto_post_evidence_mismatch) ... ADR-0063 rule 10; ADR-0065 rule 16") states the current law.
- **What R213 gets wrong.** It keeps the superseded scope (one rule, one owner) and the older vocabulary. Inside the
  spec it also contradicts `INV-763` and `EC-225`, which are document-scoped and cite R213.

## Findings

### BLOCKING

None.

### SHOULD-FIX

**automation-S1**: `automation-2.md:93`, R213; sources ADR-0063.R10 and ADR-0065.R16.

- **Source:** ADR-0065.R16 extends ADR-0063.R10 from one rule to the document type. Every enabled rule version for the
  document type is outdated, each rule owner gets `auto_post_suspended`, and later candidates get `require_human`
  (`auto_post_evidence_mismatch`). ADR-0065.R20 applies this to the cascade and the import as well.
- **Spec:** R213 states only the rule-scoped text with "`human_post`". It has no CONFLICT entry and no reference to
  ADR-0065.R16, and it disagrees with the spec's own `INV-763` and `EC-225`.
- **Fix:** add to R213 "for every gateway posting (all auto-post paths, ADR-0065.R20) the marking and the item extend
  to every enabled rule version of the document type, and later candidates get `require_human`
  (`auto_post_evidence_mismatch`), stored as `human_only` with `human_post` (ADR-0065.R16)", and add a CONFLICT entry
  for ADR-0063.R10. The compiled `policy-4.md` R608 already does this.

**automation-S2**: `automation-1.md:290-307` (Invariants and Edge cases intro and tables); sources ADR-0058.R9, R10,
R11, R12, R16 and R25 (catalog rows).

- **Source:** `invariants.csv` and `edge-cases.csv` hold rows whose catalog source is a rule of this chunk:
  - `INV-670` (rules 5, 9), `INV-671` (rule 12), `INV-673` (rules 8, 9), `INV-674` (rule 9), `INV-686` (rule 9),
    `INV-687` (rule 9);
  - `EC-156` (rules 8, 10, 13), `EC-158` (rules 12, 15), `EC-159` (rules 9, 16), `EC-160` (rule 9), `EC-162`
    (rule 25), `EC-167` (rules 9 and 11).

  `configuration-1.md:288` itself calls ADR-0058.R12 "a rule of `automation`".
- **Spec:** the intro says it lists "the invariants whose catalog source names a rule of this chunk", but it lists only
  INV-679, 680, 684 and 685 and EC-163 and 166. The rows above are only in the `configuration` spec, and nothing here
  points to them. A builder of `automation_dispatch` would miss the checks of owner scope, taint, the depth bound and
  draft writers.
- **Fix:** list these IDs, with the R-numbers they protect, as citations to their rows in `configuration-1..3`, and
  correct the intro sentence.

### NOTES

- **automation-N1**: `automation-1.md:319`. `change_proposal_ttl_days` (ADR-0029.R5) is listed as a read with no
  remark, but `settings.csv` has no row for it. For `artifacts.proposal_ttl_days` the spec does say there is no row. Add
  the same remark here.
- **automation-N2**: `automation-1.md:211`, R44 (ADR-0059.R2). It states the `auto_post_eligibility` hook, which
  ADR-0065.R20 now treats as the cascade checkers' rules. This is faithful to its unit, and ADR-0065 left ADR-0059.R2
  without a note. A one-line cross-reference to R230 and R231 would help a reader.

## SOURCE findings (do not count against the spec)

- **SRC-1:** ADR-0063.R10 (the "Hard:" bullet) has no note pointing to ADR-0065.R16. ADR-0065's "Documents updated"
  annotated ADR-0063 rules 6, 8 and 29 but not rule 10, which is the rule it extends.
- **SRC-2:** `edge-cases.csv` EC-184 (source ADR-0063 rule 10) is still rule-scoped: "the rule version's evidence is
  marked outdated ... the next match gets human_post". Under ADR-0065.R16 and R20 the cascade suspension is
  document-scoped, and the decision is `require_human` (`auto_post_evidence_mismatch`).
- **SRC-3:** `settings.csv` has no rows for `change_proposal_ttl_days` (ADR-0029.R5, interim default 14) or
  `artifacts.proposal_ttl_days` (ADR-0059.R13 and R28, default 30).
