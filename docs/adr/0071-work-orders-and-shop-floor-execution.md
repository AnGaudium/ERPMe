# ADR-0071: Work orders and shop-floor execution

Status: proposed (2026-11-17) under ADR-0005 (builder Claude Opus 5.5).
Design items: DS-52 (production orders and shop floor), DS-31 (shop-floor flows), DS-53 (costing), DS-34 (agents), DS-15 (roles). Related decisions: D6. Principles 2, 3, 12. ADR-0004, ADR-0006, ADR-0007, ADR-0008, ADR-0009, ADR-0013, ADR-0022, ADR-0023, ADR-0024, ADR-0027, ADR-0028, ADR-0029, ADR-0033, ADR-0034, ADR-0035, ADR-0040, ADR-0042, ADR-0063, ADR-0064, ADR-0066, ADR-0068, ADR-0070.

## Decision

The author's decision of 2026-11-17: production execution should feel like Odoo's manufacturing and work orders, and keep SAP-grade data semantics. This ADR adds a thin execution layer on top of ADR-0034 and changes none of its postings.

**What stays (SAP and ADR-0034).** One production order per run, with partial and repeated postings; no backorder orders and no order splitting; corrections by reversible posting documents, never by unlocking a done order; cost only from issues, receipts and confirmations (ADR-0035).

**What is added.**
- **Vocabulary.** People see a production order as an **MO** and each internal operation as a **WO**. No new document type.
- **Execution state per WO.** `waiting`, `ready`, `in_progress`, `paused`, `blocked`, `done`. Three are stored declarations; three are derived from facts that already exist.
- **Time log.** Start, pause and block write clock records per person, team or machine, with stop reasons grouped by OEE loss class. A confirmation proposes its activity quantities from them; costing still reads only the confirmation.
- **Queue and tablet.** A work-center queue (kanban by state) and a WO workspace, specified as queries and commands only.
- **MO tree, WO transfer inside a resource group, receipt scrap for orders without operations.**

| Requirement | Today (ADR-0034) | Decision |
| --- | --- | --- |
| Output receipts, many times | Allowed: rule 13, cumulative tolerance | Unchanged |
| Component issues, many times | Allowed: rule 11, with returns and over-issue | Unchanged; an unplanned component is a change order and an issue in one batch (rule 3) |
| Labor and activity time, many times | Allowed: each confirmation carries activities | Time-only confirmations stated; activities proposed from time logs (rules 2, 11) |
| Scrap, many times | Only on confirmations, so impossible without operations | Receipt scrap on orders without internal operations (rule 4) |

### Rules

**Vocabulary**

1. UI labels, not new nouns:
   - **MO** is the UI label of `production_order`; **WO** is the UI label of an internal `production_order_operation`. External operations show as subcontracting steps (ADR-0037), not WOs.
   - **Code names.** Code keeps one noun per thing (ADR-0004): new tables and commands use `operation`, as `operation_confirmation` already does. The author's `work_order_time_log` is therefore `operation_time_log`; its UI label is "WO time log".
   - **No backorders.** Receiving less than G leaves the rest open on the same MO; technical completion closes it (ADR-0034 rule 6). The UI never offers a split.

**Recording many times**

2. Each of the four records may be posted any number of times per MO, each one a reversible internal document:
   - **Receipts** (ADR-0034 rule 13) and **issues and returns** (rule 11): unchanged.
   - **Time.** A confirmation with yield and scrap 0 and only activity quantities is valid (a time-only confirmation, for setup or a shift without finished parts). Rule 12 never forbade it; this rule states it. ADR-0064 rule 22's duplicate check treats two time-only confirmations as duplicates only when their activity quantities are equal too.
   - **Scrap.** A confirmation with yield 0 and scrap above 0 records scrap alone. Component scrap is an issue line with a scrap `reason_code` (rule 11's column). Receipt scrap: rule 4.
3. Issuing a component that is not on the MO, from the tablet's "issue extra component":
   - **On the order.** An issue above the open requirement keeps `issue_above_requirement` (ADR-0034 rule 11).
   - **Not on the order.** The client sends one command batch (ADR-0008 rule 20): the change order that adds the component line (ADR-0028 rule 4; ADR-0034 rule 8), then `CreateProductionIssue` and `PostProductionIssue`. The line's required quantity is 0 unless the person states one, so ADR-0035 rule 10 treats the consumption as above norms. When policy requires approval of the change, the batch fails as a whole and the issue waits for it.
4. Receipt scrap, for an MO without internal operations:
   - **Fields.** `production_receipt` gains `scrap_quantity` (main output, inventory unit, default 0) and `scrap_reason_code`. A receipt may hold only scrap and no lines; it then posts no material document, like a confirmation.
   - **Scope.** Refused with `receipt_scrap_not_allowed` when the MO has an internal operation (scrap belongs on the WO's confirmation, so it is never counted twice) or has no main output (disassembly).
   - **Backflush at receipt.** The progress share becomes max(R / G, (R + S) / Q), where R is cumulative net receipts of the main output and S cumulative net receipt scrap. With S = 0 this equals today's rule; planned assembly scrap is never consumed twice.
   - **Value.** Receipt scrap carries no value. Tolerance, completion and abnormal cost read receipts only, as today; the scrap variance reads it (ADR-0035; ADR-0064 rule 10).

**Orders without operations**

5. Already allowed, confirmed here:
   - **Master data.** A production version's routing is optional and a routing may have no operations (ADR-0033 rules 10, 13). ADR-0034 handles the case: backflush at operation becomes backflush at receipt (rule 2), scheduling uses the fixed lead time (rule 3), receipts go to the putaway bin (rule 13).
   - **The flow.** Issue, receive and record receipt scrap, each any number of times, with no WO. The MO screen offers these three buttons.
   - **Labor.** Such an MO records no activity; conversion cost reaches it through pools with a constant basis (ADR-0035 rule 7). A workshop that wants labor time adds one internal operation on the MO (ADR-0034 rule 2), which makes it a one-WO order.

**WO execution state**

6. Stored, in `operation_execution` (one row per internal operation, written by `production` at release and when a change order adds an internal operation; not version content, ADR-0009 rule 9):
   - `run_state`: `not_started`, `in_progress`, `paused` or `blocked`, with `block_stop_reason_id` and `block_note` while blocked;
   - `work_center_id`: the execution work center, initially the planned one (rule 16).

   **Why stored.** A start, pause or block is a declaration by a person or machine that no other data reveals.
7. Derived, by the pure function `production.derive_operation_state`, in this order:
   - **`done`:** a posted, not reversed confirmation with `is_final` exists. A reversal reopens the WO without any write.
   - **The stored state** when it is `in_progress`, `paused` or `blocked`.
   - **`waiting`**, with every reason that applies:
     - `previous_operation`: the previous operation is not done and its cumulative yield is not above this WO's cumulative yield + scrap, so no parts wait here;
     - `components`: a component line of this WO (lines without an operation number belong to the first internal operation) has a remaining requirement (required − net issued − backflushed) above the quantity ready for it: picked to the supply bin in a warehouse with tasks, reserved in one without, read through `inventory.contract`.
     - An open in-process inspection lot does not hold the next operation in Phase 1 ([ADR-0070](0070-quality-management-core.md) rule 21); the tablet shows it under Inspection due (rule 14). If that changes, its reason `inspection` joins this list.
   - **`ready`** otherwise.

   **Why derived.** These facts belong to other documents and modules (confirmations, reversals, reservations, pick tasks). A stored copy would need consumers to keep it right and would go stale; a function at read time is always right and tests as a pure function.
8. Commands (module `production`, effect class `other`, leaf `shop_floor_execution`, not `human_only`, not proposal-bound):

   | Command | From | To | Time log effect |
   | --- | --- | --- | --- |
   | `StartOperation` (kind `setup` or `run`, default `run`; people or team, default the actor's employee partner) | `not_started`, `paused`, `blocked`, `in_progress` | `in_progress` | Closes an open stop log; opens a log per named person or team, or one machine log for an integration; in `in_progress` it adds people or switches their kind |
   | `PauseOperation` (optional people, optional stop reason) | `in_progress` | `paused` when no setup or run log stays open | Closes the named people's logs, or all; with a stop reason, opens one stop log once the WO is paused |
   | `BlockOperation` (stop reason required, note) | any but `done` | `blocked` | Closes every open log and opens a stop log; raises `operation_blocked` (rule 18) |

   - **Start also resumes.** No `ResumeOperation`: the verb Resume means continuing a stopped job at level `post`, and an operator resumes at `edit`.
   - **Waiting.** Starting a `waiting` WO gives the check result `operation_waiting` with its reasons, or the error `operation_not_ready` when `production.operation.start_when_waiting` is `reject`.
   - **Done.** `StartOperation` or `BlockOperation` on a done WO is refused with `operation_done`.
   - **Stop reason on pause.** Required when `production.operation.stop_reason_on_pause` is true (`stop_reason_required`).
   - **Confirm without start.** A confirmation never requires a start: a lean workshop may only confirm.
   - **Concurrency.** Each command locks the `operation_execution` row; a confirmation still serializes on the order row (ADR-0034 rule 19).
   - **Events:** `OperationStarted`, `OperationPaused`, `OperationBlocked`, for live queues (ADR-0040 rule 13).

**Time log**

9. `operation_time_log` (module `production`) holds one clock interval:
   - **Who.** `employee_partner_id`, or `team_id` with `head_count` (people working, at least 1), or neither for a machine log (`head_count` 0). At most one open log per operation and person, team or machine.
   - **When.** `started_at` and `ended_at` are instants (ADR-0007), never business dates; `ended_at` is null while open.
   - **What.** `log_kind`: `setup`, `run` or `stop`; `stop_reason_id` only on stop logs; the execution `work_center_id`.
   - **State.** `draft` (written by an agent run), `recorded`, or `canceled`; `entry_source` `person`, `agent` or `integration`.
   - **Commands.** `CreateOperationTimeLog` and `UpdateOperationTimeLog` (`is_draft_only`: an agent run's log is always `draft`, anyone else's is `recorded`), `CancelOperationTimeLog` with a reason, and `ConfirmOperationTimeLog`, `human_only`, which turns an agent's draft into `recorded`. Only the state commands of rule 8 open logs; a created log has both instants. A log linked to a posted, not reversed confirmation cannot change (`time_log_already_confirmed`); reverse the confirmation first.
10. Stop reasons. `stop_reason` is company data (code, name, `loss_class` `availability`, `performance` or `quality`, `is_planned` for planned stops that OEE leaves out of availability, `is_active`), with `CreateStopReason` and `UpdateStopReason` (`master_data_change`, leaf `production_structure`). OEE reporting comes later; this captures its data now.
11. A confirmation proposes its activities from the time log:
    - **Which logs.** At create or update, the confirmation links the WO's `recorded`, closed logs not linked to another posted, not reversed confirmation (`operation_confirmation_time_log`). The person may remove or add such logs.
    - **The mapping.** `activity_type.time_log_basis`: `none` (default: today's standards), `labor` (sum of duration × `head_count`) or `machine` (length of the union of the intervals). A `per_order` activity reads `setup` logs, a `per_base_quantity` activity reads `run` logs; stop logs are never proposed. The result is converted to the activity type's time unit and rounded half up (ADR-0006 rule 17).
    - **Adjustable.** The proposal is stored as `proposed_quantity` beside the person's `quantity`; ADR-0064 rule 22's activity check applies to the quantity. Costing reads only the posted quantity (ADR-0035 rule 7).
    - **Final confirmation.** Refused while a setup or run log of the WO is open (`operation_time_log_open`); the tablet sends `PauseOperation` first in the same batch. An open stop log is closed at its posting.
    - **Reversal.** Reversing a confirmation leaves its links, so its logs count as unconfirmed again and the next confirmation proposes them.
    - **Phase 1.** This is the minimal form of "labor time by clock events", moved from ADR-0034 rule 21 into Phase 1.

**Assignment, queue and tablet**

12. `AssignOperation` (leaf `shop_floor_execution` at `edit`) sets a WO's people and teams as a whole list in `operation_assignment`; replaced rows get `ended_at`, so the history stays. Assignment grants no right and gates no command. Event `OperationAssigned`.
13. `ListWorkCenterQueue` (module `production`, computed query, `production_order` at `read`; record scope on `production_warehouse_id`): approved MOs not technically complete, one row per WO of the given work center or resource group, with:
    - the derived state and reasons (kanban columns `waiting`, `ready`, `in_progress`, `paused`, `blocked`, `done`, the last for a chosen date range);
    - MO number, item, operation number and description, scheduled dates, expected, confirmed and open quantities;
    - assigned people and teams, open logs, and `is_assigned_to_me`;
    - order: scheduled start, then MO number, then operation number.
14. `GetOperationWorkspace` (module `query`, layer 5, as ADR-0066 rule 17, because it composes four modules; `production_order` at `read`) returns what the tablet shows for one WO:
    - **Instructions:** attachments linked to the routing operation of the MO's snapshot revision (found by `routing_revision_id` and `operation_number`, no new column) and to the WO itself;
    - **Components** of this WO: required, issued, backflushed, ready and remaining;
    - **Inspection due:** open `in_process` inspection lots of ADR-0070 for this MO and operation number, read through `quality.contract`;
    - **Actions** from `ListAllowedCommand` (ADR-0040 rule 8): Start, Pause, Block, Confirm quantity (`CreateOperationConfirmation` and `PostOperationConfirmation` in a batch, with the proposed activities), Record scrap (a confirmation with yield 0), Issue extra component (rule 3).

    The tablet is a hand-built PWA screen (ADR-0040 rule 6); the client computes nothing (rule 2).

**MO tree**

15. `GetProductionOrderTree` (module `planning`, computed query, `production_order` at `read`) returns the sub-assembly tree below an MO: for each component line, the production orders whose output supply is pegged to it, by the make-to-order link first, then the projection's allocation (ADR-0024 rule 20; ADR-0064 rule 8), level by level. Each node shows the MO, pegged quantity, need date, execution state, WOs done of total and any blocked WO. No data is stored; upward pegging stays `GetProductionOrderPegging`.

**Resource group**

16. `TransferOperation` (module `production`, `other`, leaf `shop_floor_execution` at `post`) moves a WO to another work center before work on it starts:
    - **Allowed when** the WO's `run_state` is `not_started` or `blocked` (a machine down before start), it has no setup or run log and no confirmation (`operation_already_started`); the target is active, in the same resource group as the planned work center (ADR-0068 rule 12) and in the MO's production warehouse (`work_center_not_in_resource_group`).
    - **Effect.** It sets `operation_execution.work_center_id`; the planned work center stays in the version, so no change order is needed and the estimate keeps its basis. The open reservations of the WO's components get the new supply bin as destination through `inventory.contract`; stock already staged gets a move task to it.
    - **Who reads the execution work center:** the queue, the load view (ADR-0034 rule 3), the output bin of the last operation (ADR-0034 rule 13), and the confirmation, which copies it into `operation_confirmation.work_center_id`, so pools allocated by activity type count the work center that did the work (ADR-0035 rule 7).
    - **Beside ADR-0068 rule 14.** A change order still moves the planned work center (replanning, with the target's calendar and new dates); while the WO has not started it also sets the execution work center to the new planned one. `TransferOperation` is the floor's quick dispatch inside the group: no new version and no new dates. Either way, cost follows the work center on the confirmation.
    - **Event:** `OperationTransferred`.

**Agents, integrations and blocked WOs**

17. Effect class and actors:
    - **Class `other`.** The state, assignment, transfer and time-log commands change no stock, value or books and send nothing out, so they are `other`. They are not proposal-bound: a wrong start or pause costs nothing until a person posts a confirmation.
    - **Integrations** (machine signals) run `StartOperation` and `PauseOperation` as actor `integration` with a credential holding `shop_floor_execution` at `edit`; their logs are `recorded` with `entry_source` `integration`, and still only propose.
    - **Agents.** A tainted run may run only `CreateOperationTimeLog` and `UpdateOperationTimeLog` (drafts) and the confirmation drafts of ADR-0064 rule 19; a person confirms the logs and posts the confirmation. An untainted agent may start and pause by class, but no Phase 1 tool list holds these commands (ADR-0050 rule 30).
18. Blocked WOs: `BlockOperation` raises the work item `operation_blocked` (subject the operation, owner `role:shop_floor_lead`, due one day, resolution `system`), closed when the WO leaves `blocked`. The work case kind `production_disruption` (ADR-0066 rule 3) has it as trigger, so `work_case.production_disruption.mode` `auto` opens a case that groups the WO, its stop logs, the work items and the documents made about it.

**Settings and catalogs**

19. Settings (ADR-0063; leaf `production_structure`, company scope, change immediate, outdates none):
    - **`production.operation.start_when_waiting`:** `warn` (default) or `reject`.
    - **`production.operation.stop_reason_on_pause`:** boolean, default false; true is tighter.
20. Catalog rows and DDL ([DS-43-54-planning-production.sql](../design/DS-43-54-planning-production.sql), owner `production`):
    - **Tables:** `stop_reason`, `operation_execution`, `operation_assignment`, `operation_time_log`, `operation_confirmation_time_log`. **Columns:** `activity_type.time_log_basis`; `operation_confirmation.work_center_id`; `operation_confirmation_activity.proposed_quantity`; `production_receipt.scrap_quantity` and `scrap_reason_code`.
    - **Verbs:** Pause and Block are new (level `edit`); Start, Assign and Transfer widen their intent.
    - **Errors:** `operation_not_ready`, `operation_done`, `operation_already_started`, `work_center_not_in_resource_group`, `operation_time_log_open`, `time_log_already_confirmed`, `stop_reason_required`, `receipt_scrap_not_allowed`. **Check result:** `operation_waiting`.
    - **Leaf** `shop_floor_execution` (function, area `production`); `shop_floor_lead` at `post`, `production_planner` at `read`.
    - **Work item kind** `operation_blocked`; **work case kind** `production_disruption`.
    - **Invariants** INV-840 to INV-845 and **edge cases** EC-290 to EC-297, below.

## Context

- **The ask.** Shop-floor people think in work orders on a board: start, pause, report, next. SAP's confirmation-only model is exact but abstract; Odoo's MO and WO screens are easy but split orders into backorders and unlock done orders to correct them.
- **What exists.** ADR-0034 already records the four facts many times, with reversal and costing from confirmations. Missing were: a visible state per operation, clock events, a queue, scrap without operations, and a move inside a resource group (ADR-0068).
- **Constraints.** No new posting document, no change to costing (ADR-0035), agents only draft (spec 14; ADR-0029), one noun per thing (ADR-0004), configurable over hard locks.

## Options considered

| Option | For | Against |
| --- | --- | --- |
| WO as a label of the operation line, execution in a side table (chosen) | No new document; postings unchanged; not version content | Two tables per operation |
| WO as its own document type | Odoo-like | Duplicates the order's lifecycle; versioning and approval of something that is not a commitment |
| Store every state, kept by consumers | One column to read | Stale after reversals and stock moves; consumers to maintain |
| Derive `waiting`, `ready` and `done`, store the rest (chosen) | Always right; pure and testable | A computed query per read |
| Costing from time logs | Fewer steps | Two cost sources; a pause by a machine would move value |
| Time logs propose, confirmations cost (chosen) | One cost source; adjustable; audit shows proposal and decision | A link table |
| Scrap at receipt for every order | One place | Double counting with confirmation scrap |
| Receipt scrap only without internal operations (chosen) | No double count; lean workshops can record scrap | Two places in the product, never on one order |
| Transfer as a change order | Uses ADR-0028 | Approval and a new version for a dispatching choice |
| Execution work center beside the planned one (chosen) | No version churn; costing sees who did the work | One more column read by the load view |
| A new effect class for operational commands | Explicit | `other` already means no stock, value, books or send |

## Consequences

- **Shop floor:** a board per work center, a tablet per WO, one-tap start and pause, and a confirmation pre-filled with the time worked.
- **Lean workshops:** an MO without operations still issues, receives and records scrap, with no WO.
- **Accounting and audit:** nothing new is valued; every activity quantity has its proposal and its source logs; scrap at receipt never doubles confirmation scrap; reversals stay the only correction of postings.
- **Agents:** the capture agent drafts logs and confirmations; machines start and pause; a person posts.
- **Build:** one pure state function, one pure proposal function, five small tables, two queries in `production`, one in `planning`, one in `query`. Small-model friendly.
- **Revisit when:**
  - OEE reporting is designed and needs more than the loss class and planned flag;
  - customers need a WO transfer after start, or across production warehouses;
  - the full-kit `components` reason keeps ready WOs waiting in practice (a partial-kit reading would follow).

## Documents updated

- **ADRs** (notes tagged "ADR-0071, proposed 2026-11-17"): ADR-0033 rules 10, 12; ADR-0034 rules 1, 2, 3, 12, 13, 21; ADR-0035 rules 7, 10; ADR-0064 rules 10, 19, 22; ADR-0023 rule 13 (destination change); ADR-0040 rule 6; ADR-0063 rule 29; ADR-0066 rule 3; ADR-0068 rule 14 (execution work center).
- **Catalogs:** settings.csv (2), authorization-areas.csv (1), role-template-levels.csv (2), work-item-kinds.csv (1), work-case-kinds.csv (1), invariants.csv (6), edge-cases.csv (8).
- **Design:** DS-43-54-planning-production.sql; DS-04 (errors, check result); DS-17 (event types `operation_clocked` and `operation_dispatched`); the glossary (MO, WO, operation execution, WO execution state, WO time log, stop reason, receipt scrap, execution work center, verbs Pause and Block). The wider intents of the existing verbs Start, Assign, Transfer, Cancel and Confirm are left to the author, who owns those rows.
- **Index and log:** docs/adr/README.md; docs/runbook/step-log.md.

## Edge cases and invariants

**Invariants** (DS-16; block INV-840 to INV-849, INV-840 to INV-845 taken; first step with the production core):

- **INV-840** `time_log_confirmed_once` (area `production`): every operation time log is linked to at most one posted, not reversed confirmation, of the same operation, and every such log is `recorded` and closed.
- **INV-841** `operation_run_state_matches_logs` (area `production`): an operation has an open setup or run log exactly when its `run_state` is `in_progress`; a `blocked` operation that is not done has a stop reason and one open stop log; at most one log is open per operation and person, team or machine.
- **INV-842** `operation_transfer_in_group` (area `production`): every `operation_execution.work_center_id` other than the planned one is a member of the planned one's resource group in the order's production warehouse, and the transfer preceded every setup or run log and every confirmation of the operation.
- **INV-843** `confirmation_execution_work_center` (area `production`): every operation confirmation's `work_center_id` equals its operation's execution work center.
- **INV-844** `receipt_scrap_scope` (area `production`): every production receipt with scrap above 0 belongs to an order with a main output and no internal operation.
- **INV-845** `agent_time_logs_drafted` (area `safety`): every time log written by an agent run was `draft` until a human confirmed it, and no confirmation links a `draft` or `canceled` log.

**Edge cases** (DS-17; block EC-290 to EC-299, EC-290 to EC-297 taken):

- **EC-290** `wo_many_postings`: an MO of 100 with two WOs; op 10 is started, paused with a stop reason, restarted, confirmed for 40 with activities proposed from the logs and one adjusted, then scrap 2, then 58 final; three receipts of 40, 30 and 28; an issue above requirement; costing reads only the confirmations.
- **EC-291** `mo_without_operations_scrap`: an MO without routing gets two issues, three receipts and receipt scrap of 4 with a reason; backflush at receipt follows max(R / G, (R + S) / Q); receipt scrap on an MO with an internal operation is refused with `receipt_scrap_not_allowed`.
- **EC-292** `wo_transfer_in_resource_group`: a WO moves to a sibling work center before start; the reservations point to the new supply bin; the confirmation carries the new work center and the pool allocation counts it; a transfer after start is refused with `operation_already_started`, one outside the group with `work_center_not_in_resource_group`.
- **EC-293** `capture_agent_time_logs`: the capture agent drafts time logs and a confirmation from a shift sheet; the logs are not proposed until a person confirms them; the tainted run's `StartOperation` is refused with `tool_not_allowed`.
- **EC-294** `machine_signal_start_pause`: an integration starts and pauses a WO from machine signals; machine time is the union of intervals, labor time the person logs × head count.
- **EC-295** `blocked_wo_case`: a WO is blocked for a breakdown; `operation_blocked` is raised and, in mode `auto`, a `production_disruption` case opens; a start closes the item.
- **EC-296** `final_with_open_log`: a final confirmation while a run log is open is refused with `operation_time_log_open`; the tablet's batch pauses first and succeeds.
- **EC-297** `reversal_reopens_logs`: reversing a confirmation makes its logs unconfirmed and the WO no longer `done`; the next confirmation proposes the logs again.
