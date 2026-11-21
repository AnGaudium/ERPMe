Module: periods    Chunk: whole    Source ADRs: ADR-0007, ADR-0012, ADR-0043, ADR-0044, ADR-0049
Build step(s): 4, 5, 8    Generated from index: 30d5706    Compiled by: Claude Fable 5.2, 2026-11-21

# Compiled spec: periods

## Purpose

`periods` owns each company's fiscal calendar (ADR-0007): fiscal years, their regular posting periods and up to four
special periods for year-end adjustments. It owns the state of each regular period per posting area (`general`,
`inventory`, `receivable`, `payable`; a special period has `general` only), the commands that restrict, open, lock and
unlock an area, the close checklist of a period (`close_task`) and the framework of closing entries. It also owns
`business_date_override`, which `clock` reads through a registered hook. It is a layer-2 platform module (ADR-0022.R2).
It does not own the journal, the costing engine, the computations of the close jobs, or the content of a regime's
checklist and closing rules: those come from `ledger`, `inventory`, the owning modules of each job and the
localization package.

## Entities and tables

DDL: `docs/design/DS-05-platform.sql`. The module owns <!-- count:tables -->6<!-- /count --> tables and the non-posting
document type `period_unlock_request`.

| Table | Meaning | Key | Parent | Owner |
| --- | --- | --- | --- | --- |
| `business_date_override` | The business date `clock.today(company)` returns outside `production`; updated in place | `id`; unique (`company_id`) | company | `periods` |
| `fiscal_year` | A fiscal year of a company, with `code`, dates and `is_migration` | `id`; unique (`company_id`, `code`) and (`company_id`, `id`) | company | `periods` |
| `posting_period` | A regular or special period of a fiscal year | `id`; unique (`fiscal_year_id`, `number`) and (`company_id`, `id`) | `fiscal_year` | `periods` |
| `posting_period_area_state` | State of a period in a posting area | `id`; unique (`posting_period_id`, `area`) | `posting_period` | `periods` |
| `close_task` | A task of the close checklist of a company and posting period | `id`; unique (`posting_period_id`, `code`) and (`company_id`, `id`) | `posting_period` | `periods` |
| `period_unlock_request` | Typed header of the non-posting document that approves an unlock: period, area, reason | `id`, the `document` ID | `document` | `periods` |

Reads: `company`, `user_account`; `document` (`documents`); `journal_entry` and its `close_task_id`,
`is_closing_entry` and `posting_period_id` (`ledger`, DS-06); material documents (`inventory`); `policy_decision`,
`auto_post_confirmation` (`policy`); `tax_return` (`tax`).

## Commands and queries

"Not stated" means the sources name nothing for the cell. Authorization leaves and levels are those of ADR-0054.R8 and
ADR-0054.R24.

| Name | Actor and authorization | Input | Effect | Events | Errors |
| --- | --- | --- | --- | --- | --- |
| `CreateFiscalYear` | a human, or the fiscal year job as `system` on behalf of the `fiscal_calendar_owner`; leaf not stated | the fiscal year | creates the `fiscal_year`, its regular and special `posting_period` rows (R19) | not stated | not stated |
| `RestrictPostingPeriod` | `human_only`; `posting_period` at `post` | period and area, or all areas | `open` to `soft_locked`; first use copies the close tasks (R59) | `PostingPeriodRestricted` | `period_sequence_violation` |
| `OpenPostingPeriod` | `human_only`; `posting_period` at `post` | period and area, or all areas | `soft_locked` to `open` | `PostingPeriodOpened` | `period_sequence_violation` |
| `LockPostingPeriod` | `human_only`; `posting_period` at `full` | period and area, or all areas | `soft_locked` to `locked` | `PostingPeriodLocked` | `period_sequence_violation`, `close_checklist_incomplete` |
| `UnlockPostingPeriod` | `human_only`; `posting_period` at `full` | period, area, reason, the ID of an approved `period_unlock_request` | `locked` to `soft_locked`; closes the request; the area's tasks go back to `pending` | `PostingPeriodUnlocked` | `period_sequence_violation`, `migration_period_locked`, `posting_period_unlock_invalid` |
| `Submit` of `period_unlock_request` | policy point (R47); level not stated | the request (period, area, reason) | sends the request to approval | not stated | not stated |
| `RunCloseTask` | `human_only`; close jobs are `Run` on `costing_run` and `close_checklist` | the task, with the period as an explicit parameter | starts a job or evaluates a check | not stated | not stated |
| `ConfirmCloseTask` | `human_only`; leaf not stated | a manual task | marks it `done` | not stated | not stated |
| `SkipCloseTask` | `human_only`; leaf not stated | an optional task, a reason | marks it `skipped` | not stated | not stated |

Not registered commands of this module: the hook through which `clock` reads `business_date_override` (R3); the system
job that creates the next fiscal year (R27); the command that writes `business_date_override`, which the sources do
not name (R4). Commands of other modules that change this module's rows: `CreateMigration` and `CompleteMigration`
(R21 to R24), `ActivateSubledger` (R24). Jobs of other modules that close tasks run: `RunBalanceCarryForward`
(`ledger`), `RunTaxReturnOffset` (`tax`, error `tax_return_not_filed`, R77).

Error codes bound to no named command of this module: `as_of_date_out_of_range` (dispatcher, R7),
`posting_period_not_open` (R33) and `posting_date_too_far_ahead` (R37) at posting, `posting_period_frozen` (R15) and
`posting_period_invalid` (R17) from database triggers.

## Rules

### Business date

R1. `clock.now()` returns the real transaction time and is never overridden, except frozen inside unit tests; such
tests do not compare it with database `now()` in triggers and defaults, which stays real.
Source: ADR-0007.R15

R2. `clock.today(company)` returns the company's current business date: the date of `clock.now()` in the company's time
zone, unless a row in `business_date_override` sets it for that company.
Source: ADR-0007.R15

R3. `business_date_override` is owned by `periods`, because layer 1 modules own no tables; it holds one row per company,
and `clock` reads it through a hook that `periods` registers and `app` wires (ADR-0022.R2).
Source: ADR-0007.R15, ADR-0007.R15.N2

R4. `business_date_override` is read by every process (servers, Procrastinate workers); the command that writes it is
refused unless the installation's `environment` setting is `test` or `simulation`; in `production` the clock ignores
the table.
Source: ADR-0007.R15

R5. The business simulator (DS-17) sets `business_date_override` to the simulated date, so a replay of the same seed
gives the same business dates; `recorded_at` stays real and is excluded from reference comparisons.
Source: ADR-0007.R15

R6. A command envelope may carry `as_of_date` (ADR-0008.R7 note): inside that command run every `clock.today(company)`
read returns it, in simulate and in execute, and the events the command emits carry it as `business_date`.
Source: ADR-0007.R15.N1

R7. The accepted range of `as_of_date` is the date `clock.today(company)` returns without it, or the day before that
date; the dispatcher refuses any other date, a later one included, with `as_of_date_out_of_range`. The past side is a
stated tolerance: for one day an actor may run under the previous day's settings.
Source: ADR-0007.R15.N1, ADR-0007.R15.N3

R8. Every simulation returns the `as_of_date` it used, so a client that executes after midnight sends that date and
gets the same plan; `posting_date` stays explicit (ADR-0007.R8) and is never taken from `as_of_date`.
Source: ADR-0007.R15.N1

R9. The range check of `as_of_date` applies only to envelopes received over a transport (REST, MCP, the UI). An
internal caller (ADR-0013.R9 consumers under the event's `business_date`, ADR-0007.R17 jobs under their enqueued date,
the ADR-0065 gateway job) pins the run's business date in process the same way, with no range check, so a retried or
released delivery does the same work on any later day.
Source: ADR-0007.R15.N1, ADR-0007.R15.N4

### Fiscal calendar

R10. A company's fiscal calendar is data: `fiscal_year` rows with `start_date`, `end_date` and a `code` (for example
`2026`), contiguous and non-overlapping per company, `end_date` not null.
Source: ADR-0007.R18

R11. Each fiscal year is split into regular `posting_period` rows, also with `end_date` not null, that are contiguous
and non-overlapping inside it. Special periods share dates with a regular period and are chosen explicitly (R28).
Source: ADR-0007.R18

R12. Non-overlap is enforced by an exclusion constraint on `daterange(start_date, end_date, '[]')` per company
(PostgreSQL extension `btree_gist`), for `posting_period` on regular periods only; contiguity is enforced by the
command that creates the rows.
Source: ADR-0007.R18, ADR-0012.R1

R13. The fiscal year and the regular posting period of a date are found by looking up the row whose range contains it,
never computed from a formula, so a short or long first fiscal year and non-calendar fiscal years need no code.
Source: ADR-0007.R19

R14. Once a posting exists in a fiscal year, its range and the ranges of its posting periods never change. A change of
fiscal year is made by creating a new, shorter or longer, fiscal year after the last used one.
Source: ADR-0007.R20

R15. The database holds R14 for periods in use: a `posting_period` that has an area row that is not `open`, or a
journal entry posted in it, never changes its dates, fiscal year, kind or number and is never deleted, and its
`fiscal_year` never changes its dates or code and is never deleted (`trg_posting_period_check_change`,
`trg_fiscal_year_check_change`; error `posting_period_frozen`, DS-04). A material document dated in a period puts it in
use as a journal entry does, and no area row of a period with a journal entry is deleted.
Source: ADR-0012.R1.N2

R16. The rest of R14, that no period of a fiscal year with a posting moves even without a posting of its own, stays a
command rule, as the DS-05 comment lists.
Source: ADR-0012.R1.N2

R17. The database holds the shape of new periods: a special period lies on its fiscal year's last day and a regular
period inside its fiscal year (`trg_posting_period_check_dates`, on insert and on a change of dates, year or kind), and
a special period has only the `general` area, never inserted `open` (`trg_posting_period_area_state_check_insert`);
both refuse with `posting_period_invalid` (DS-04), so no period can be inserted on a date of a locked month.
Source: ADR-0012.R1.N2

R18. The default fiscal year is the calendar year; a company may declare other fiscal years when it needs to.
`CreateFiscalYear` checks only contiguity (R10 to R12) and immutability (R14).
Source: ADR-0007.R21

R19. `CreateFiscalYear` creates the fiscal year's regular `posting_period` rows by the company's period pattern
(default: one per calendar month; the localization package may set another) and `special_period_count` special
periods; the count lies between 0 and 4 and its default comes from the localization package. The pattern and count of a
regime are package content of the localization package (`close_checklist.yaml`, ADR-0039.R9).
Source: ADR-0012.R1

R20. Each `posting_period` has `fiscal_year_id`, `number` (1, 2, … for regular periods; then regular count + 1 … for
special ones), `kind` (`regular` or `special`), `start_date` and `end_date`. A special period has the fiscal year's
last day as both dates.
Source: ADR-0012.R1

R21. The migration period is a declared exception to R10 to R12 and R19: `CreateMigration` creates a migration fiscal
year (code `M` and the opening year, for example `M2026`) of one regular period from `opening_date` to `opening_date`,
with no special period, before the first operating year. It is marked by `fiscal_year.is_migration`, which a check
holds to one day; the code `M<year>` is a convention.
Source: ADR-0007.R18, ADR-0012.R1, ADR-0012.R1.N1, ADR-0044.R2

R22. `CreateMigration` also creates the company's first operating fiscal year from `cut_over_date` if it does not
exist; at a mid-year cut-over that year is short (flagged).
Source: ADR-0044.R2

R23. Opening documents post only into the migration period, and only once `clock.today` is on or after `opening_date`,
so the period-ahead check of R37 has its reference period.
Source: ADR-0044.R2

R24. `CompleteMigration` locks the migration period directly in every area, subledger areas first, without the
soft-lock step or close tasks, as a declared exception to R38 to R42. It cannot be unlocked: `UnlockPostingPeriod` on
it is refused with `migration_period_locked`. `ActivateSubledger` later finds it locked like any earlier period
(ADR-0025.R4).
Source: ADR-0012.R7, ADR-0044.R2

R25. At posting, a `posting_date` outside every fiscal year of the company is rejected with an error that names
`CreateFiscalYear`. Drafts and documents that never post are not checked.
Source: ADR-0007.R22

R26. A human may create a fiscal year at any time with `CreateFiscalYear`, earlier than the job of R27.
Source: ADR-0012.R3

R27. A system job creates the next fiscal year `fiscal_year_lead_days` (company setting, default 30) before the
current one ends, with the company's default pattern, unless one exists, on behalf of the company's
`fiscal_calendar_owner` (a human set at company setup; spec 03-agent-safety rule 3).
Source: ADR-0012.R3

R28. A posting's regular period is found from its `posting_date` (R13). To post into a special period, a document
names it in `posting_period_id`, which is a document field and part of the version content (ADR-0009.R9), and its
`posting_date` must be the fiscal year's last day. A document that names no period posts into the regular period of
its date. The journal entry stores its `posting_period_id` (DS-06).
Source: ADR-0012.R2

### Posting areas and states

R29. Each regular period has one state per posting area in `posting_period_area_state` (`posting_period_id`, `area`,
`state`); a special period has only `general`.
Source: ADR-0012.R4

R30. Areas are `general`, `inventory`, `receivable` and `payable`. A journal line's area is its system account's
control kind (ADR-0010.R5), with `none` and `gr_ir` in `general`; a material document line is in `inventory`.
Source: ADR-0012.R4

R31. The gated kinds `fixed_asset` and `loan` are in `general`, using the effective control kind (ADR-0025.R4). Lines
on accounts of control kind `cost_object` are in area `inventory`, so the inventory lock also waits for payroll,
depreciation and other pool postings of the period (ADR-0035.R3).
Source: ADR-0012.R4

R32. States are `open`, `soft_locked` and `locked`. A posting is allowed only if every area its lines touch allows the
actor:
- `open`: any actor with the permission;
- `soft_locked`: a human holding the capability `post_in_soft_locked_period`, which the `chief_accountant` role
  template carries (ADR-0017.R4), or actor `system` running a close task of that period or an earlier one (for example
  costing adjustments that reach later periods) on behalf of a human holding that capability; never an agent, an
  integration or a scheduled job outside the close;
- `locked`: nobody.
Source: ADR-0012.R5

R33. A posting that R32 does not allow is rejected with `posting_period_not_open`, naming the period, area, state and
who may post.
Source: ADR-0012.R5

R34. In a `soft_locked` period, a command registered `is_consequence_posting` (ADR-0043.R5), such as a tax adjustment
that a settlement triggers, is admitted when it runs on behalf of a person holding `post_in_soft_locked_period`.
Source: ADR-0012.R5.N1

R35. When the period is `locked`, or that person lacks the capability, a tax adjustment takes as its declaration and
posting date the first day of the earliest later period that admits it, and raises a `tax_adjustment_redated` work
item (ADR-0041.R13 note).
Source: ADR-0012.R5.N1

R36. New regular periods start `open` and special periods start `soft_locked`.
Source: ADR-0012.R6

R37. A posting whose posting date lies more than `future_posting_periods` regular periods after the period that
contains the company's current business date (`clock.today`, R2) is rejected with `posting_date_too_far_ahead`; the
company setting defaults to 1, so only the current and the next period accept postings. Special periods are exempt;
they are soft-locked anyway.
Source: ADR-0012.R6

### State changes

R38. The state commands are all `human_only` (ADR-0008.R2) and act per period and area, or for all areas at once.
Source: ADR-0012.R7

R39. `RestrictPostingPeriod` changes `open` to `soft_locked` when the previous period in the sequence (R43) is
`soft_locked` or `locked` in that area.
Source: ADR-0012.R7

R40. `OpenPostingPeriod` changes `soft_locked` to `open` when the next regular period in the sequence is `open` in that
area; special periods are not considered.
Source: ADR-0012.R7

R41. `LockPostingPeriod` changes `soft_locked` to `locked` when the previous period is `locked` in that area; for
`general`, the period's subledger areas are `locked`; and the area's close tasks are complete and current (R62).
Source: ADR-0012.R7

R42. `UnlockPostingPeriod` changes `locked` to `soft_locked` when it is the latest `locked` period in that area; for a
subledger area, `general` of that period is not `locked`; a reason is given; and the unlock is approved through the
policy engine (DS-28) by an approved `period_unlock_request`, which the unlock closes (R48).
Source: ADR-0012.R7

R43. The sequence is: the regular periods of a fiscal year in order, then its special periods in order; the first
regular period of the next year follows the previous year's last regular period, not its special periods, so audit
adjustments of a closed year do not hold up the new year.
Source: ADR-0012.R8

R44. A sequence condition that fails returns `period_sequence_violation`, naming the period that blocks.
Source: ADR-0012.R8

R45. The database holds the part of R39 to R42 that one row can hold: `trg_posting_period_area_state_check_change`
refuses a change from `locked` to any state but `soft_locked` (so a plain UPDATE never reopens a locked period),
refuses `locked` to `soft_locked` unless an approved `period_unlock_request` of that period and area exists (its
document in state `approved`), refuses any unlock of the migration period, never deletes a locked area's row, and never
changes a row's company, period or area; the error is `posting_period_unlock_invalid` (DS-04).
Source: ADR-0012.R7.N1

R46. The rest of the `UnlockPostingPeriod` condition stays the command's: the period is the latest locked one in the
area, a subledger area unlocks only while `general` is not locked, and the request used is the one the unlock closes
in the same transaction. Because the trigger requires the request to be still `approved`, `UnlockPostingPeriod`
updates the area state first and closes the request after it, in the same transaction.
Source: ADR-0012.R7.N1

R47. `UnlockPostingPeriod` (`human_only`) takes the ID of an approved `period_unlock_request`. That is a non-posting
document (period, area, reason) whose `Submit` is a policy point, which always requires at least the lowest-rank
procedure.
Source: ADR-0043.R16

R48. The unlock closes the `period_unlock_request` in the same transaction, so one request unlocks once, and records
the request's `policy_decision_id` in its audit record (ADR-0038.R2).
Source: ADR-0043.R16

R49. Every state change is recorded with actor, time, reason and approval (audit, DS-36; the audit columns `reason`
and `policy_decision_id` are those of ADR-0038.R2 and ADR-0038.R9) and emits an event: `PostingPeriodRestricted`,
`PostingPeriodOpened`, `PostingPeriodLocked` or `PostingPeriodUnlocked`.
Source: ADR-0012.R9

R50. A posting takes a share lock on the area state rows it touches before any stock or numbering lock
(ADR-0009.R15); a state change takes an exclusive lock, so no posting enters while a period is being locked.
Source: ADR-0012.R9

### Backdated postings and corrections

R51. Any period whose `inventory` area is not `locked` accepts backdated postings; a backdated document re-costs its
period and every later period whose `inventory` area is not `locked`. This window is wider than SAP's and is a
recorded deviation from SAP, kept by the author.
Source: ADR-0012.R10, ADR-0012.R10.N1

R52. The costing engine posts adjustment documents and never edits old lines (DS-09).
Source: ADR-0012.R10

R53. Corrections of documents in locked periods post in a period that allows them (ADR-0009.R23).
Source: ADR-0012.R10

### Close tasks

R54. A `close_task` row belongs to a (company, posting period) and has `code`, `area`, `kind`, `is_required`,
`is_sequential`, `depends_on` (task codes), `state` (`pending`, `running`, `done`, `failed`, `skipped`),
`entry_count_at_done`, the actor who completed it, when, and evidence (a document, job run or report reference).
Source: ADR-0012.R11

R55. The actor who completed a task is stored as the command envelope gives it, in `actor_kind`, `actor_id` and
`on_behalf_of_id`, because jobs and the system complete tasks too; a done task has them and `completed_at` (check
`ck_close_task_done`).
Source: ADR-0012.R11.N2

R56. Template tasks also carry `applies_to`, which decides the periods that receive them, and `parameters`, copied
into the column `close_task.parameters` that the task's job reads.
Source: ADR-0012.R11.N1

R57. Format of a task in a regime's `close_checklist.yaml`: `code`; `area`; `kind` (`job`, `check`, `manual`); `runs`
(the registered job or check, empty for manual tasks); `is_required`; `is_sequential`; `depends_on`; `applies_to`
(`every_period`, `fiscal_year_end` for the last regular period and the special periods, `special_period`, or
`fiscal_year_first_period`); `parameters` (JSON validated by the job's schema, for example accounts); labels; and the
basis.
Source: ADR-0049.R23

R58. The regime's tasks are copied into the company's checklist template at setup (ADR-0016.R7).
Source: ADR-0049.R23

R59. Tasks are copied from the template into `close_task` when the period is first restricted
(`RestrictPostingPeriod`), so template changes made before then apply; a special period's tasks are copied when the
fiscal year's last regular period is first restricted in `general`. `applies_to` decides which periods get each task.
Source: ADR-0012.R11, ADR-0049.R23

R60. Task kinds are `job` (a system job: period-end actual costing, FX revaluation, prepaid expense amortization,
provisions, closing entries), `check` (a deterministic check that passes or fails: trial balance sums to zero;
subledgers equal control accounts) and `manual` (a human confirms, for example bank statements reconciled).
Source: ADR-0012.R13

R61. Core tasks that no template lists and no company removes or skips: every agent auto-post of the period is
confirmed by its accountable human (spec 03-agent-safety rule 6), a core `check` on `general`, required for every
company, where an auto-post is as ADR-0029.R13 defines it and confirmations are `auto_post_confirmation` rows written
by `ConfirmAutoPost`; no document of the period in `issuing` or accepted and unposted (ADR-0028.R11); no import batch
posting into the period in state `posting`, or abandoned with unreversed documents (ADR-0030.R9); the migration
completed (ADR-0044.R3). A required core check blocks `LockPostingPeriod` while its condition fails. A company cannot make a task the regime
marks required optional.
Source: ADR-0012.R13, ADR-0049.R23

R62. `LockPostingPeriod` for an area is rejected with `close_checklist_incomplete` unless every required task of that
area is `done` and current; for `general`, the required tasks of all areas.
Source: ADR-0012.R12

R63. In the same transaction `LockPostingPeriod` re-evaluates every `check` task and confirms that each `job` and
`check` task is current: the number of journal entries and material documents in that period and area, which only
grows because both are append-only, still equals `entry_count_at_done`. The count includes only entries posted
outside any close task and entries posted by the tasks this one depends on, directly or through others; journal
entries and material documents posted by a close task carry its `close_task_id` (DS-06).
Source: ADR-0012.R12

R64. An entry whose `close_task_id` names a task of another period counts, for this period's tasks, as posted outside
any close task; so when a close task of one period posts into another, the receiving period's tasks become stale like
after any other posting.
Source: ADR-0012.R12.N1

R65. A task that is not current, and every task of the area after `UnlockPostingPeriod`, goes back to `pending`.
Source: ADR-0012.R12

R66. `RunCloseTask` starts a job or evaluates a check; `ConfirmCloseTask` marks a manual task done; `SkipCloseTask`
skips an optional task with a reason. All are `human_only`.
Source: ADR-0012.R14

R67. Jobs run by actor `system` on behalf of the human who ran the task, with the period as an explicit parameter
(ADR-0007.R17), can be simulated first (Principle 2), and every task can be done by hand with the LLM off
(Principle 12).
Source: ADR-0012.R14

R68. A job run again posts only the difference since its last run and never edits earlier documents. Its documents
are internal (ADR-0009.R19) and are reversed only by their own job when its method requires it (for example
revaluation `reverse_and_repost`, ADR-0011.R20); humans do not reverse them.
Source: ADR-0012.R15

R69. A task with `is_sequential: true` (period-end actual costing, which must run in period order) may run in period N
only when the same task of the previous period is `done` or `skipped`, or does not exist; the company's first period
has no previous one.
Source: ADR-0012.R16

R70. When a sequential task of period N goes back to `pending` or runs again, the same task in every later period goes
back to `pending`, because its input changed.
Source: ADR-0012.R16

R71. The period-end actual costing job also settles production (ADR-0035.R5, ADR-0035.R12). Closing entries run after
it, because the production cost leaves are expense-type.
Source: ADR-0012.R13

R72. The checklist template comes from the accounting regime of the localization package; a company may add tasks.
This module fixes the framework; task content and order are designed in step 8 (DS-26 and the regime), and the
template format, the core tasks and the tasks other ADRs name are R57 to R61 and R74 to R76.
Source: ADR-0012.R17, ADR-0012.R17.N1

R73. The computations are owned by DS-25 (bad-debt provisions, prepaid amortization) and DS-09 (inventory write-down),
not DS-26 (ADR-0027.R8).
Source: ADR-0012.R17

R74. Job tasks other ADRs name, whose area and order the regime sets:
- `period_end_costing` (sequential; also settles production): DS-09 (ADR-0020.R12; ADR-0035.R5);
- `inventory_write_down`: DS-09 (ADR-0027.R8);
- `bad_debt_provision`, `prepaid_amortization`: DS-25 (ADR-0048.R14);
- `fx_revaluation`: DS-10 (ADR-0011.R17);
- `vat_apportionment` (yearly true-up at fiscal year end): DS-23 (ADR-0041.R16);
- `closing_entries` (after costing): DS-12 (R78);
- `balance_carry_forward`: `ledger`'s `RunBalanceCarryForward` (ADR-0049.R22); the accounts are package content.
Source: ADR-0049.R23

R75. Check and manual tasks other ADRs name, whose area and order the regime sets:
- `landed_cost_unallocated` (lists open cost sources), `check`: DS-11 (ADR-0021.R14);
- `gr_ir_closed_lines` (balances on closed order lines), `check`: DS-22 (ADR-0047.R13);
- `statutory_report_checks` (check lines and coverage of the regime's statements), `check`: ADR-0049.R9;
- `bank_reconciliation` (reads `GetBankReconciliation`), `manual`: DS-25 (ADR-0048.R8).
Source: ADR-0049.R23

R76. Which tasks a regime's checklist holds, their areas, order and whether required, is package data of the
localization package for step 8, `unverified` (DS-19), and flagged.
Source: ADR-0012.R17.N1, ADR-0049.R23

R77. A period-end tax offset task runs the job `RunTaxReturnOffset` of module `tax`, shaped like
`RunBalanceCarryForward`: it posts a `balance_transfer` through `ledger.contract.write_journal_entry`, dated the
period's last day, with the task's `close_task_id`. Its task parameters name the accounts and the return form and box
whose filed value is the amount (`{form, box, debit_account, credit_account}`). It reads the period's latest filed
`tax_return` (ADR-0041.R18), fails with `tax_return_not_filed` when there is none, and moves the box value less what
earlier runs for the period moved, so a supplementary return moves only the difference. It lives in `tax` because
`ledger` never imports `tax` (ADR-0022.R2). The regime's content (accounts, box, whether required) is flagged package
content of the localization package, the author's to decide (open question).
Source: ADR-0049.R23.N1

### Closing entries

R78. Closing entries are posted by a closing job, actor `system`, on behalf of the human who ran it; their journal
entries carry `is_closing_entry = true` (DS-06), so period-range reports can exclude them.
Source: ADR-0012.R18

R79. Whether a regime closes profit and loss by entries or by computation without documents, which accounts, how
often and in which period, are rules of the accounting regime. A regime that closes by entries moves income and
expense accounts to the account mapped to `income_summary`, which has no balance after closing, and its result to
`retained_earnings`; the mapped accounts, the frequency and the period are flagged package content of the localization
package, `unverified` until checked against the regime's text.
Source: ADR-0012.R18

R80. Phase 1 registers only `by: entries` as a value of `closing.method`; closing by computation without documents
comes after Phase 1 (interim, open question).
Source: ADR-0012.R18.N1

R81. Closing entries close each profit-and-loss account per business unit, and each closing line takes the unit of the
balance it closes (source `closing`) (ADR-0069).
Source: ADR-0012.R18.N2

## Invariants

No row of `invariants.csv` has the area `periods`. The catalog row that names ADR-0012 as its source:

- `INV-14` `postings_respect_period_state` (area `ledger`, check point `command`, first step 1): a posting into a
  locked period, or into a soft-locked period without the capability, is rejected and writes nothing; one into an open
  period is not rejected for its period. Protects R32, R33.

## Edge cases

No row of `edge-cases.csv` has the area `periods`. The catalog rows that name ADR-0012 as their source:

- `EC-02` `posting_in_soft_locked_period` (area `ledger`, first step 1): a posting into a soft-locked period by an
  actor with the capability, and by one without. Outcome: `must_succeed|must_reject:posting_period_not_open`.
- `EC-28` `year_end_close` (area `close`, first step 8): year-end close with closing entries. Outcome: `must_succeed`.

## Settings

None: `settings.csv` holds no key of `periods`.

The rules name these settings, which have no row in `settings.csv`: `fiscal_year_lead_days` (company, default 30, R27),
`future_posting_periods` (company, default 1, R37), `special_period_count` (0 to 4, default from the localization
package, R19), `closing.method` (Phase 1 value `by: entries`, R80), and the installation's `environment` (`test`,
`simulation`, `production`, R4).

Reads: `ui.post_review`, `permissions.segregation_assignment_mode`, `permissions.small_company_mode`,
`invitation_expiry_days` (named by units of other modules that this module's dossier shares; no rule here uses them).

## UI annotations

None: the sources hold no ADR-0077 annotation for this module. The work item kind `tax_adjustment_redated` (R35)
belongs to `tax`.

## Conflicts

CONFLICT ADR-0012.R4: the rule text puts the gated kind `cost_object` in area `general` (ADR-0025.R4) and, in its closing amendment, in area `inventory`; the later ADR-0035.R3 governs, so R31 states `inventory` and keeps `general` for `fixed_asset` and `loan`.
CONFLICT ADR-0007.R15.N1: its range of one day before or after the business date is narrowed by the later note ADR-0007.R15.N3 (2026-11-21), which governs: R7 accepts the business date or the day before and refuses a later date.
FALSE-POSITIVE ADR-0012.R10.N1: the word "reversed" describes SAP postings; the note keeps rule 10 as written and R51 states it with the recorded deviation.

## Proposed (not law)

None

## Trace

| Source | Where |
| --- | --- |
| ADR-0007.R15 | R1-R5 |
| ADR-0007.R15.N1 | R6-R9 |
| ADR-0007.R15.N2 | R3 |
| ADR-0007.R15.N3 | R7 |
| ADR-0007.R15.N4 | R9 |
| ADR-0007.R18 | R10-R12, R21 |
| ADR-0007.R19 | R13 |
| ADR-0007.R20 | R14 |
| ADR-0007.R21 | R18 |
| ADR-0007.R22 | R25 |
| ADR-0012.D0 | Purpose |
| ADR-0012.R1 | R12, R19-R21 |
| ADR-0012.R1.N1 | R21 |
| ADR-0012.R1.N2 | R15-R17 |
| ADR-0012.R2 | R28 |
| ADR-0012.R3 | R26, R27 |
| ADR-0012.R4 | R29-R31 |
| ADR-0012.R5 | R32, R33 |
| ADR-0012.R5.N1 | R34, R35 |
| ADR-0012.R6 | R36, R37 |
| ADR-0012.R7 | R24, R38-R42 |
| ADR-0012.R7.N1 | R45, R46 |
| ADR-0012.R8 | R43, R44 |
| ADR-0012.R9 | R49, R50 |
| ADR-0012.R10 | R51-R53 |
| ADR-0012.R10.N1 | R51 |
| ADR-0012.R11 | R54, R59 |
| ADR-0012.R11.N1 | R56 |
| ADR-0012.R11.N2 | R55 |
| ADR-0012.R12 | R62, R63, R65 |
| ADR-0012.R12.N1 | R64 |
| ADR-0012.R13 | R60, R61, R71 |
| ADR-0012.R14 | R66, R67 |
| ADR-0012.R15 | R68 |
| ADR-0012.R16 | R69, R70 |
| ADR-0012.R17 | R72, R73 |
| ADR-0012.R17.N1 | R72, R76 |
| ADR-0012.R18 | R78, R79 |
| ADR-0012.R18.N1 | R80 |
| ADR-0012.R18.N2 | R81 |
| ADR-0038.R2 | ref: ADR-0038.R2 |
| ADR-0038.R2.N1 | ref: ADR-0038.R2.N1 |
| ADR-0038.R2.N2 | ref: ADR-0038.R2.N2 |
| ADR-0038.R2.N3 | ref: ADR-0038.R2.N3 |
| ADR-0038.R2.N4 | ref: ADR-0038.R2.N4 |
| ADR-0043.R1 | ref: ADR-0043.R1 |
| ADR-0043.R1.N1 | ref: ADR-0043.R1.N1 |
| ADR-0043.R1.N2 | ref: ADR-0043.R1.N2 |
| ADR-0043.R16 | R47, R48 |
| ADR-0044.R2 | R21-R24 |
| ADR-0049.R23 | R57-R59, R61, R74-R76 |
| ADR-0049.R23.N1 | R77 |
| ADR-0054.R7 | ref: ADR-0054.R7 |
| ADR-0054.R7.N2 | ref: ADR-0054.R7.N2 |
| ADR-0054.R8 | ref: ADR-0054.R8 |
| ADR-0054.R8.N1 | ref: ADR-0054.R8.N1 |
| ADR-0054.R24 | ref: ADR-0054.R24 |
| ADR-0054.R24.N2 | ref: ADR-0054.R24.N2 |
| ADR-0054.R24.N3 | ref: ADR-0054.R24.N3 |
| ADR-0054.R25 | ref: ADR-0054.R25 |
| ADR-0054.R25.N1 | ref: ADR-0054.R25.N1 |
| ADR-0054.R25.N2 | ref: ADR-0054.R25.N2 |
| ADR-0054.R25.N3 | ref: ADR-0054.R25.N3 |
| ADR-0060.R3 | ref: ADR-0060.R3 |
| ADR-0060.R5 | ref: ADR-0060.R5 |
| ADR-0060.R8 | ref: ADR-0060.R8 |
| ADR-0060.R33 | ref: ADR-0060.R33 |
