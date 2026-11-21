# ADR-0012: Posting periods and closing

Status: accepted (2026-11-14) under ADR-0005, reviewed by Claude Fable 5.2. Amended (2026-11-14): rules 5, 6 and 18 decided by the agent under the author's delegation of these three questions. Design item: DS-12. Related decisions: D2, D5, D6, D15. Principles 2, 3, 5, 6, 12. ADR-0004, ADR-0005, ADR-0007, ADR-0008, ADR-0009, ADR-0010, ADR-0011.

## Decision

Each company's fiscal year (ADR-0007) contains regular posting periods and up to four special periods for year-end adjustments. A regular period has a state per posting area — the general ledger and the three subledger areas inventory, receivable and payable, derived from the system account's control kind — as SAP opens and closes periods per account type and keeps a separate materials period; special periods have the general area only. States are `open`, `soft_locked` (only the chief accountant, and close jobs run on a chief accountant's behalf, may post; agents never) and `locked` (nobody posts). Areas are soft-locked and locked strictly in period sequence, subledgers before the general ledger, and unlocked only with approval, from the latest locked period backwards. Locking an area needs its close tasks done and still current: a task goes back to pending when a later posting in its period and area makes it stale. Closing entries are posted by actor `system` on behalf of the human who started the close and carry a closing-entry marker. The checklist content and the regime's closing rules come from the localization package; points that are business rules are flagged with open questions.

### Rules

**Periods**

1. `CreateFiscalYear` (ADR-0007 rule 18) creates the fiscal year's regular `posting_period` rows by the company's period pattern (default: one per calendar month; the localization package may set another) and `special_period_count` special periods (0–4, default from the localization package). Each `posting_period` has `fiscal_year_id`, `number` (1, 2, … for regular periods; then regular count + 1 … for special ones), `kind` (`regular` or `special`), `start_date` and `end_date`. A special period has the fiscal year's last day as both dates; ADR-0007 rule 18's non-overlap applies to regular periods only. TT99 template: monthly periods and one special period, `close_checklist.yaml` ([ADR-0039](0039-vietnam-package-tt99.md) rule 9). A migration creates its own one-day fiscal year and period ([ADR-0044](0044-data-migration-and-export.md) rule 2).

    Note (S2 findings closure, 2026-11-21): a migration fiscal year is marked by `fiscal_year.is_migration`, which a check holds to one day; the code `M<year>` stays a convention ([ADR-0044](0044-data-migration-and-export.md) rule 2; chief architect's decision, 2026-11-17). The DDL of `fiscal_year`, `posting_period`, `posting_period_area_state` and `close_task` is in [DS-05-platform.sql](../design/DS-05-platform.sql), owner `periods`.
2. A posting's regular period is found from its `posting_date` (ADR-0007 rule 19). To post into a special period, a document names it in `posting_period_id`, which is a document field and part of the version content (ADR-0009 rule 9), and its `posting_date` must be the fiscal year's last day. A document that names no period posts into the regular period of its date. The journal entry stores its `posting_period_id` (DS-06).
3. A system job creates the next fiscal year `fiscal_year_lead_days` (company setting, default 30) before the current one ends, with the company's default pattern, unless one exists, on behalf of the company's `fiscal_calendar_owner` (a human set at company setup; [03-agent-safety.md](../spec/03-agent-safety.md) rule 3). A human may create it earlier with `CreateFiscalYear`.

**Posting areas and states**

4. Each regular period has one state per posting area in `posting_period_area_state` (`posting_period_id`, `area`, `state`); a special period has only `general`. Areas are `general`, `inventory`, `receivable` and `payable`; a journal line's area is its system account's control kind (ADR-0010 rule 5), with `none` and `gr_ir` in `general`; a material document line is in `inventory`. This is the meaning chosen for the spec's "open and close per account type" ([05](../spec/05-accounting-inventory-core.md)), following SAP's posting period variant per account type and its separate materials period ([SAP Learning](https://learning.sap.com/learning-journeys/outlining-the-record-to-report-process-in-sap-s-4hana/using-posting-period-variants-to-control-the-opening-and-closing-of-posting-periods_e7818699-66ac-451f-8687-981376d9b6aa)). The gated kinds `cost_object`, `fixed_asset` and `loan` are in `general`, using the effective control kind ([ADR-0025](0025-later-phase-seams.md) rule 4). Lines on accounts of control kind `cost_object` are in area `inventory`, so the inventory lock also waits for payroll, depreciation and other pool postings of the period ([ADR-0035](0035-production-costing.md) rule 3).
5. States are `open`, `soft_locked` and `locked` ([07](../spec/07-shared-foundation.md#document-lifecycle-numbering-and-posting-periods)). A posting is allowed only if every area its lines touch allows the actor:
    - `open`: any actor with the permission;
    - `soft_locked`: a human holding the capability `post_in_soft_locked_period`, which the `chief_accountant` role template carries (ADR-0017 rule 4), or actor `system` running a close task of that period or an earlier one (e.g. costing adjustments that reach later periods) on behalf of a human holding that capability; never an agent, an integration or a scheduled job outside the close;
    - `locked`: nobody.
    Otherwise the posting is rejected with `posting_period_not_open`, naming the period, area, state and who may post. Letting close jobs post in a soft-locked period applies the spec's "close postings by actor `system` on behalf of the human who triggered the close" (07) to the soft-lock rule; otherwise the period would have to be opened to everyone to run costing and revaluation.

   Note: in a `soft_locked` period, a command registered `is_consequence_posting` (ADR-0043 rule 5), such as a tax adjustment that a settlement triggers, is admitted when it runs on behalf of a person holding `post_in_soft_locked_period`. When the period is `locked`, or that person lacks the capability, a tax adjustment takes as its declaration and posting date the first day of the earliest later period that admits it, and raises a `tax_adjustment_redated` work item ([ADR-0041](0041-tax-engine.md) rule 13's note) (holistic review, 2026-11-15).
6. New regular periods start `open` and special periods start `soft_locked`. A posting whose posting date lies more than `future_posting_periods` regular periods after the period that contains the company's current business date (`clock.today`, ADR-0007 rule 15) is rejected with `posting_date_too_far_ahead`; the company setting defaults to 1, so only the current and the next period accept postings. Special periods are exempt; they are soft-locked anyway.
7. Commands, all `human_only` (ADR-0008 rule 2; [14-agent-workflows.md](../spec/14-agent-workflows.md)), per period and area or for all areas at once: Exception: `CompleteMigration` locks the migration period directly, and it cannot be unlocked ([ADR-0044](0044-data-migration-and-export.md) rule 2).

| Command | From | To | Condition |
| --- | --- | --- | --- |
| `RestrictPostingPeriod` | `open` | `soft_locked` | The previous period in the sequence (rule 8) is `soft_locked` or `locked` in that area |
| `OpenPostingPeriod` | `soft_locked` | `open` | The next regular period in the sequence is `open` in that area (special periods are not considered) |
| `LockPostingPeriod` | `soft_locked` | `locked` | The previous period is `locked` in that area; for `general`, the period's subledger areas are `locked`; the area's close tasks are complete and current (rule 12) |
| `UnlockPostingPeriod` | `locked` | `soft_locked` | It is the latest `locked` period in that area; for a subledger area, `general` of that period is not `locked`; approved through the policy engine (DS-28); a reason is required; approval through an approved `period_unlock_request`, closed by the unlock ([ADR-0043](0043-policy-and-approval.md) rule 16) |

8. The sequence is: the regular periods of a fiscal year in order, then its special periods in order; the first regular period of the next year follows the previous year's last regular period, not its special periods, so audit adjustments of a closed year do not hold up the new year. A condition that fails returns `period_sequence_violation`, naming the period that blocks.
9. Every state change is recorded with actor, time, reason and approval (audit, DS-36) and emits an event (`PostingPeriodRestricted`, `PostingPeriodOpened`, `PostingPeriodLocked`, `PostingPeriodUnlocked`). A posting takes a share lock on the area state rows it touches before any stock or numbering lock (ADR-0009 rule 15); a state change takes an exclusive lock, so no posting enters while a period is being locked. Audit columns `reason` and `policy_decision_id`: [ADR-0038](0038-audit-and-observability.md) rules 2, 9.
10. A backdated document re-costs its period and the later periods whose `inventory` area is not `locked` (07); the costing engine posts adjustment documents and never edits old lines (DS-09). Corrections of documents in locked periods post in a period that allows them (ADR-0009 rule 23).

    Note (the author, 2026-11-21): kept as written, with rule 16: any period whose `inventory` area is not locked accepts backdated postings, and costing reruns for it and every later unlocked period. This is a recorded deviation from SAP, kept by the author. Checked against SAP sources (point D of the verification section of [reviews/2026-11-21-costing-sap-comparison.md](../reviews/2026-11-21-costing-sap-comparison.md)): SAP accepts materials postings in at most three periods: the current period; the previous period while its "allow posting to previous period" indicator is set (set automatically at every period change, clearable by hand per company code to close the previous period early); and the last period of the previous fiscal year. Material Ledger closing also blocks the previous period, and nothing outside these periods can be posted or reversed. NativeFlows keeps a wider window: every period whose `inventory` area is not locked.

**Close tasks**

11. A `close_task` row belongs to a (company, posting period) and has `code`, `area`, `kind`, `is_required`, `is_sequential`, `depends_on` (task codes), `state` (`pending`, `running`, `done`, `failed`, `skipped`), `entry_count_at_done`, the actor who completed it, when, and evidence (a document, job run or report reference). Tasks are copied from the template when the period is first restricted (`RestrictPostingPeriod`), so template changes made before then apply; a special period's tasks are copied when the fiscal year's last regular period is first restricted in `general`.

    Note: template tasks also carry `applies_to`, which decides the periods that receive them, and `parameters`, copied into a new column `close_task.parameters` that the task's job reads ([ADR-0049](0049-statutory-reporting-and-printing.md) rule 23).

    Note (S2 findings closure, 2026-11-21): "the actor who completed it" is stored as the command envelope gives it, `actor_kind`, `actor_id` and `on_behalf_of_id`, because jobs and the system complete tasks too; a done task has them and `completed_at` (check `ck_close_task_done`; chief architect's decision, 2026-11-17).
12. `LockPostingPeriod` for an area is rejected with `close_checklist_incomplete` unless every required task of that area is `done` and current; for `general`, the required tasks of all areas. In the same transaction it re-evaluates every `check` task and confirms that each `job` and `check` task is current: the number of journal entries and material documents in that period and area, which only grows because both are append-only, still equals `entry_count_at_done`, where the count includes only entries posted outside any close task and entries posted by the tasks this one depends on, directly or through others (journal entries and material documents posted by a close task carry its `close_task_id`, DS-06). A task that is not current, and every task of the area after `UnlockPostingPeriod`, goes back to `pending`.

    Note: an entry whose `close_task_id` names a task of another period counts, for this period's tasks, as posted outside any close task. So when a close task of one period posts into another (costing adjustments that reach later periods), the receiving period's tasks become stale like after any other posting (holistic review, 2026-11-15).
13. Task kinds: `job` (a system job: period-end actual costing, FX revaluation, prepaid expense amortization, provisions, closing entries), `check` (a deterministic check that passes or fails: trial balance sums to zero; subledgers equal control accounts) and `manual` (a human confirms, e.g. bank statements reconciled). The check that every agent auto-post of the period is confirmed by its accountable human ([03-agent-safety.md](../spec/03-agent-safety.md) rule 6) is a core task on `general`, required for every company; no template or company can remove or skip it, and a company cannot make a task the regime marks required optional. A required core check blocks `LockPostingPeriod` while documents of the period are in `issuing` or accepted but unposted ([ADR-0028](0028-document-lifecycle-hardening.md) rule 11). "Agent auto-post" means an auto-post as defined in [ADR-0029](0029-proposals-and-agent-safety.md) rule 13; confirmations are `auto_post_confirmation` rows written by `ConfirmAutoPost`. A required core check also blocks the lock while an import batch posting into the period is `posting`, or is abandoned with unreversed documents ([ADR-0030](0030-commercial-seams-and-imports.md) rule 9). The period-end actual costing job also settles production ([ADR-0035](0035-production-costing.md) rules 5, 12). Closing entries run after it, because the production cost leaves are expense-type.
14. Commands: `RunCloseTask` starts a job or evaluates a check; `ConfirmCloseTask` marks a manual task done; `SkipCloseTask` skips an optional task with a reason. All three are `human_only`. Jobs run by actor `system` on behalf of the human who ran the task, with the period as an explicit parameter (ADR-0007 rule 17), can be simulated first (Principle 2), and every task can be done by hand with the LLM off (Principle 12).
15. A job run again posts only the difference since its last run and never edits earlier documents. Its documents are internal (ADR-0009 rule 19) and are reversed only by their own job when its method requires it (e.g. revaluation `reverse_and_repost`, ADR-0011 rule 20); humans do not reverse them.
16. A task with `is_sequential: true` (period-end actual costing, which must run in period order, 07) may run in period N only when the same task of the previous period is `done` or `skipped`, or does not exist; the company's first period has no previous one. When a sequential task of period N goes back to `pending` or runs again, the same task in every later period goes back to `pending`, because its input changed.
17. The checklist template comes from the accounting regime of the localization package (e.g. for Vietnam: bad-debt and inventory write-down provisions, prepaid expense amortization, FX revaluation, costing, closing to 911 and 421; [08](../spec/08-l10n-vn.md#minimum-processes-to-operate-for-real)); a company may add tasks. Task content and order are designed in step 8 (DS-26 and the regime); this ADR fixes the framework. The computations are owned by DS-25 (bad-debt provisions, prepaid amortization) and DS-09 (inventory write-down), not DS-26 ([ADR-0027](0027-cross-cutting-ownership.md) rule 8).

    Note: the template format, the core tasks and the tasks other ADRs name are in [ADR-0049](0049-statutory-reporting-and-printing.md) rule 23. The TT99 content stays package data for step 8.

**Closing entries and balances**

18. Closing entries are posted by a closing job, actor `system`, on behalf of the human who ran it (07); their journal entries carry `is_closing_entry = true` (DS-06), so period-range reports can exclude them. Whether a regime closes profit and loss by entries (e.g. to 911 and 421) or by computation without documents (as SAP carries profit and loss to retained earnings), which accounts, how often and in which period, are rules of the accounting regime. The Vietnam package closes by entries at the end of every period, regular and special, within that period: income and expense accounts to the account mapped to `income_summary` (911), which has no balance after closing, and its result to `retained_earnings` (421). Source: descriptions of TT99 accounts 911 and 421 by MISA and Kế toán Lê Ánh; flagged until verified against the TT99 text.

    Note: Phase 1 registers only `by: entries` as a value of `closing.method`; closing by computation without documents comes after Phase 1 (interim, open question) (holistic review, 2026-11-15).

    Note ([ADR-0069](0069-business-unit-dimension.md), 2026-11-21): closing entries close each profit-and-loss account per business unit, and each closing line takes the unit of the balance it closes (source `closing`).
19. Balance-sheet balances are cumulative at all times: the balance on any date is the sum of all lines up to that date, across fiscal years, so no opening entry is posted at year start. Stored period-closing balances (07) are a cache rebuilt from journal lines (DS-06).

## Context

DS-12 is needed by DS-06 (journal), DS-09 (costing), ADR-0011 (revaluation) and step 8. Constraints:

- States open, soft-locked (only the chief-accountant role posts; agents cannot), locked (nobody; reopening requires approval and leaves a trace); periods costed and closed strictly in sequence; backdated documents re-cost the open periods; close postings by actor `system` on behalf of the human who triggered the close ([07](../spec/07-shared-foundation.md#document-lifecycle-numbering-and-posting-periods)).
- Open and close per company and per account type; special periods for year-end adjustments ([05](../spec/05-accounting-inventory-core.md)); "per account type" was an open question.
- Close-checklist framework and closing entries with a marker (backlog DS-12); unconfirmed agent auto-posts block the period close ([03](../spec/03-agent-safety.md) rule 6); closing periods is human only ([14](../spec/14-agent-workflows.md)).
- SAP practice (D5): posting period variants per account type (+, A, D, K, M, S), a separate materials period for goods movements, special periods 13–16 for general-ledger year-end adjustments.
- ADR-0005: closing rules of a country and unstated business behavior are the author's; the mechanism is the agent's.

## Options considered

| Option | For | Against |
| --- | --- | --- |
| State per posting area from the control kind (chosen) | Subledgers close before the general ledger, as in SAP; areas come from data the core already has | Four states per period |
| One state per period | Simplest | No way to close inventory while posting accruals; the spec asks for per account type |
| State per operational account range (SAP's account intervals) | Very flexible | Ranges of a company's numbers are country-specific and error-prone for agents |
| Staleness by entry count (chosen) | Exact, because journal and material documents are append-only; no write on every posting | Counted at lock time |
| Staleness by a counter updated on every posting | Immediate | Every posting would write the same row and serialize |
| Unlock any locked period | Flexible | Breaks the strict sequence; later periods' costing would be stale |
| Opening entries at year start | Visible in the journal | A second copy of balances that can drift from the lines |

## Constraints that come with the decision

- DS-04: errors `posting_period_not_open`, `period_sequence_violation`, `close_checklist_incomplete`.
- DS-06: `posting_period_id` and `is_closing_entry` on journal entries; period balance cache.
- DS-09: re-costing of later periods; costing job sequential.
- DS-14, DS-19: period pattern, special period count, checklist template and closing rules per regime.
- DS-15: chief-accountant role; permission to change period states and run close tasks; `fiscal_calendar_owner`.
- DS-26 and step 8: content and order of close tasks.
- DS-28: approval of `UnlockPostingPeriod` through an approved `period_unlock_request` ([ADR-0043](0043-policy-and-approval.md) rule 16); a possible limit on future-dated postings.
- DS-29: work items cannot use the verb `Lock`, which now belongs to posting periods; they use `Claim` and `Unclaim`, because `Release` belongs to master data revisions ([ADR-0042](0042-work-queue.md) rule 9).
- DS-36: audit of state changes.

## Revisit when

- A company needs to close part of an area (one warehouse's inventory) or a fixed-asset area separately.
- A regime needs a closing rule that cannot be expressed as a close task.

## Documents updated

- [docs/spec/00-reading-guide.md](../spec/00-reading-guide.md): glossary rows for posting area, special period, close task, closing entry; verbs Restrict, Open, Lock, Unlock, Confirm, Skip.
- [docs/design/DS-04-command-envelope.md](../design/DS-04-command-envelope.md): three error codes.
- [docs/design/backlog.md](../design/backlog.md): DS-12 row links here.
- [docs/adr/README.md](README.md): index row.
- [docs/open-questions.md](../open-questions.md): "per account type" answered; TT99 closing rules; close jobs in soft-locked periods; start state of new periods and future-dated postings.
- [docs/runbook/step-log.md](../runbook/step-log.md): entry.
