Module: agents    Chunk: 7 of 8    Source ADRs: ADR-0064, ADR-0065, ADR-0072
Build step(s): 5, 6    Generated from index: 30d5706    Compiled by: Claude Opus 5.5, 2026-11-21

# Compiled spec: `agents`, chunk 7

## Purpose

`agents` owns the agent types, their workflows, settings and promotion (ADR-0022.R2). This chunk states the production
agent's workflows C1 to C8 and the reservation sweep, the production agent settings of ADR-0064, its quality, budget and
catalog rules, the agent mode `active` and the `auto_post_advisor` agent type of ADR-0065, and the agent rule on costing
sheets. The production agent types and the advisor are Phase 2 types (ADR-0078.R2). The agent runtime belongs to
`agent_runs`; production, planning and inventory commands belong to their modules and are cited, not restated.

## Entities and tables

The rules of this chunk define no table; the owned table `assist_request` has its row in chunk 8.

Reads: `production_order`, `production_order_component`, `stock_reservation`, `stock_transfer`, `planning_exception`,
`planning_action_message`, `production_order_variance`, `costing_sheet`, `document_extraction`, `setting_value`,
`agent_type`, `agent_type_setting` (`active_document_types`), `agent_promotion_evidence`, `agent_run`, `purchase_invoice`.

## Commands and queries

The commands these rules constrain have their rows in chunk 1: `UpdateAgentTypeSetting` to mode `active` (R1257; errors
`agent_mode_not_declared`, `shadow_evidence_insufficient`, `approver_is_submitter`), `CreateAgentPromotionEvidence` with
target mode `active` and `GetAgentDraftAcceptance` (R1257).

Not registered commands: the agent types `production` (workflows C1 to C5 and C8), `production_capture` (C6),
`production_variance` (C7) and `auto_post_advisor`, all Phase 2; the reservation sweep C2, a workflow of
`production` with no LLM step; the capture scope resolver; the lab check `t25_production_agent.py`.

Codes raised by the rules of this chunk and bound to no registered command: `agent_scope_unresolved` (capture scope, R1226),
`setting_out_of_bounds` (code lists, R1239); the catalog rows `yield_tolerance_exceeded` and `reservation_transfer_invalid`
(R1247) belong to production commands.

Commands of other modules these rules use: `EvaluateProductionOrderRelease`, `ListComponentShortage`,
`GetProductionOrderPegging`, `ListWorkCenterLoad`, `ReserveProductionOrderComponent`, `ListShortageResolutionCandidate`,
`TransferStockReservation`, `CompleteProductionOrder`, `ReopenProductionOrder`, `CancelProductionOrder`,
`CreateOperationConfirmation`, `CreateProductionIssue`, `CreateProductionReceipt`, `CreateOperationTimeLog`,
`ConfirmOperationTimeLog`, `GetProductionOrderUsageVariance`, `ListProductionOrderVarianceDriver`,
`GetProjectedAvailability`, `GetCostingRateSuggestion`, `GetCostCenterAbsorption`, `UpdateCompanySetting`,
`CreateChangeProposal`, `CreateDecisionTableVersion`, `EvaluateAutoPostBacktest`, `CreateArtifactEvidence`.

## Rules

### C1 release readiness and triage (Phase 2)

R1201. The workflows C1 to C8 belong to the production agent types, which are Phase 2 types registered with mode `off` and no workflow code in Phase 1; their work item kinds are raised and handled by people until a type is brought forward (ADR-0078.R2). C1 release readiness and triage is triggered by `ProductionOrderSubmitted`; by a daily schedule over approved and draft orders whose `planned_start_date` lies within `production.agent.readiness_horizon_days`; and by a planner's run on an order.
Source: ADR-0064.R14

R1202. C1 steps:
- D1 `gather`: `EvaluateProductionOrderRelease`, `ListComponentShortage`, `GetProductionOrderPegging`, `ListWorkCenterLoad`.
- D2 `rank`: code orders the orders by the pegged demand's due date, then days late, then the reservation priority.
- L1 `explain` (seat analysis): input the verdicts, reasons and ranked facts; output `ProductionExplainOutput`: `explanation` (at most 1,200 characters), `root_cause` (a reason handle offered, or `none`). Checks: the handle was offered; every number appears in the input. The model never sets or changes a verdict.
Source: ADR-0064.R14

R1203. C1 output is a note on the order's work item (or an `agent_task` note) with the code's verdict beside the explanation. C1 runs no command.
Source: ADR-0064.R14

### C2 reservation sweep (Phase 2)

R1204. C2 reservation sweep is a workflow of `production` with no LLM step; it carries budgets, run records and modes. Triggers: `GoodsReceiptPosted`, `StockReservationCanceled`, `ProductionOrderCompleted`, `ProductionOrderApproved`, the receipt events of stock transfers, and a daily schedule. It runs only while `production.reservation.mode` is not `off`.
Source: ADR-0064.R15

R1205. C2 steps: `ListComponentShortage` for approved orders (in mode `scheduled`, only lines whose requested date lies within `production.reservation.window_days` of the business date); then, in the order of ADR-0064.R7, `ReserveProductionOrderComponent` per order for its unreserved open requirement, simulated then executed; the reservation contract caps each at available to promise.
Source: ADR-0064.R15

R1206. The sweep may take available to promise only. The reservation contract never takes stock reserved for another order or demand (`stock_reserved`, ADR-0023.R13), so a sweep never moves a shortage onto someone else. Moving a reservation is the proposal of ADR-0064.R24.
Source: ADR-0064.R15

R1207. Concurrency: `ReserveProductionOrderComponent` locks the order row (ADR-0034.R19) and computes each line's unreserved requirement under that lock, and the reservation contract locks the stock rows it reserves from (ADR-0027.R10). Two sweeps racing for one receipt never reserve more than the stock or a line's open requirement (`INV-735`; a parallel test).
Source: ADR-0064.R15

R1208. Scope and budget: orders outside the workflow owner's record scope are skipped and counted in the run's note. A run that ends on its tool-call or row budget leaves the rest to the next trigger, which starts again in the same priority.
Source: ADR-0064.R15

R1209. C2 output is one note per order: reserved and still short, per line. No person approves a run; the run is accountable to the workflow owner.
Source: ADR-0064.R15

### C3 shortage resolution (Phase 2)

R1210. C3 shortage resolution is triggered by `production_component_shortage` and by a planner's run on an order.
Source: ADR-0064.R16

R1211. D1 `candidates`: `ListShortageResolutionCandidate` (module `planning`, computed query, `production_order` at `read`) computes candidates of the kinds enabled in `production.agent.shortage_candidate_kinds`, each with its computed effect on the order's start date and on pegged demand. The kinds, in this order, with the candidate and the output when chosen:
- `expedite_supply`: an open supply line whose `expedite` message would cover the shortage; a note to the buyer on the planning exception, and the buyer acts.
- `stock_transfer`: a warehouse whose available to promise covers the shortage; a draft stock transfer.
- `alternative_version`: a production version valid on the order's dates whose structure does not use the short component, orders in `draft` or `pending_approval` only; a draft update of the order (re-explosion).
- `reschedule`: the earliest start the projection covers, dated by `plan_production` in mode `fixed`; a draft update, or a drafted change order of the dates.
- `partial_staging`: release with the covered operations staged, the policy's shortage rank applying; a note to the releaser.
- `transfer_reservation`: reservations of an order of lower priority (ADR-0064.R7); a change proposal with `TransferStockReservation` (ADR-0064.R24).
- `split_order`: a change order reducing G to the covered quantity, plus a new draft order for the rest (decision 6); the drafted change order and the new draft.
Source: ADR-0064.R16

R1212. Selection per kind is deterministic (S = the line's uncovered quantity, d0 = the order's planned start):
- `expedite_supply`: open purchase or transfer supply lines of the item and warehouse with an `expedite` message of the latest completed planning run whose proposed date is on or before d0; one candidate per line, covering min(S, its open quantity); a message of an older run is not used.
- `stock_transfer`: per other warehouse of the company with a transfer route to the issue warehouse and available to promise above 0; covering min(S, that available to promise); effect date = business date + the route's lead time.
- `alternative_version`: per valid version (ADR-0033.R13) that does not use the item, on orders in `draft` or `pending_approval`; covers S; effect date from `plan_production` with the version.
- `reschedule`: one candidate, the first date on which `GetProjectedAvailability` covers the open requirement, scheduled by `plan_production` in mode `fixed`; none when the projection never covers it within the horizon.
- `partial_staging`: one candidate when the order still has an uncovered line and at least one operation has every component line uncovered 0; it names those operations, covers 0 of S and keeps d0.
Source: ADR-0064.R16

R1213. Selection of `transfer_reservation`: donor reservations, open and unpicked, of approved orders later in the reservation priority; one candidate per donor, covering min(S, its unpicked quantity, the target's short quantity of ADR-0064.R24), that short quantity as of the query; execution recomputes it under the lock (ADR-0064.R24), so the two may differ; the candidate states the donor's resulting short quantity and its pegged demand.
Source: ADR-0064.R16

R1214. Selection of `split_order`: one candidate when 0 < covered G < G, where covered G is the largest quantity the covered components support: the minimum over the order's lines with required above 0 of (required − uncovered) × G / required, rounded down to the item's unit's decimal places. A fixed-quantity line does not scale with G, so it allows a split only when it is fully covered (uncovered 0), and otherwise no split is offered. Lines with required 0 are skipped. The new draft takes G − covered G.
Source: ADR-0064.R16

R1215. Each candidate carries its covered quantity, the resulting start date and the days late of each pegged demand before and after. The total order is: kind in the order of the kinds list; within `transfer_reservation`, the donor's reservation priority, latest donor first; then the resulting start date, the larger covered quantity, document number and line.
Source: ADR-0064.R16

R1216. The returned list holds at most 7 candidates: first the best candidate of each enabled kind that has one, in kind order, so no kind is crowded out; then the remaining places filled from the other candidates in the total order. Partial cover is offered and marked.
Source: ADR-0064.R16

R1217. L1 `choose` (seat analysis) outputs `ProductionChooseOutput`: `candidate` (a handle offered, or `none`), `reason_codes`, `explanation`. It never writes a quantity or date.
Source: ADR-0064.R16

R1218. A person submits every C3 draft; change orders and proposals follow their pools (ADR-0055); a new draft order is released by a person's `Submit`. Alternative versions come only from the version selection function's valid set (ADR-0033.R13). Substitute components stay after Phase 1 (decision 5; ADR-0033.R17).
Source: ADR-0064.R16

### C4 order exceptions and rescheduling (Phase 2)

R1219. The planning run (ADR-0024.R21) raises these production order exceptions and messages, stored in `planning_exception` and `planning_action_message`:
- `production_order_start_overdue` (exception, key order): approved, `not_started`, and `planned_start_date` + `production.order.start_grace_days` is before the planning date.
- `production_order_overdue` (exception, key order): approved, not technically complete, and `planned_end_date` + `production.order.overdue_grace_days` is before the planning date.
- `expedite` (message, key supply line) on the order's main-output supply line: the first need date d the order serves is earlier than its supply date by more than `planning.production_reschedule_in_tolerance_days`.
- `postpone` (message, key supply line): the supply date is earlier than its first need by more than `planning.production_reschedule_out_tolerance_days`, within `planning.production_rescheduling_horizon_days`.
- `cancel` (message, key supply line): a `not_started` order whose supply the projection never needs within the horizon, including a make-to-order order whose sales line was canceled.
- `reduce` (message, key supply line): a `not_started` order whose needed quantity is below G; proposed quantity the needed quantity, never below what is posted.
Source: ADR-0064.R17

R1220. One `production_order_exception` work item per order (module `planning`, owner `planning_owner`) lists the order's open exceptions and messages of the latest run; the consumer `planning_work_items` closes it when a run raises none. These exceptions get no `planning_exception` work item, as `capacity_overload` gets its own kind.
Source: ADR-0064.R17

R1221. C4 steps: D1 gathers the messages, pegging and the order's status; D2 computes new dates with `plan_production` in mode `fixed`, groups related messages by pegging, and orders them bottom-up by low-level code, so a component's order is proposed before its parent's; L1 `explain` picks a candidate handle or `none`; D3 drafts the update (draft order) or change order (released order).
Source: ADR-0064.R17

R1222. A cancel is never drafted: the note recommends it and a person runs `CancelProductionOrder`, which ADR-0034.R5 allows only before the first posting.
Source: ADR-0064.R17

### C5 technical completion and stalled orders (Phase 2)

R1223. C5 is triggered by `production_completion_candidate` and `production_order_stalled` (ADR-0064.R12). L1 `classify` (seat classification) gives the likely state from codes and posting gaps, one of `finished`, `waiting_material`, `waiting_capacity`, `abandoned`, `unknown`, with a summary.
Source: ADR-0064.R18

R1224. C5 D3: for `finished`, a change proposal with `CompleteProductionOrder` and the order's version as `expected_version` (ADR-0034.R17), with open reservations, staged stock and the usage variance as evidence; otherwise a note to the shop-floor lead. A late receipt after completion goes through the person's `ReopenProductionOrder`.
Source: ADR-0064.R18

### C6 shop-floor capture (Phase 2)

R1225. C6 shop-floor capture (decision 7) is the agent type `production_capture`. Trigger: `shop_floor_report_extracted`, raised when an extraction of purpose `shop_floor_report` (ADR-0064.R26) from an enabled source reaches `extracted` or `verified`. A person on NativeFlows's own shop-floor screen or scanner needs no agent (ADR-0061.R9).
Source: ADR-0064.R19

R1226. Scope resolver: the extraction's `production_order_number` field must be trusted (ADR-0057.R17: closed shape, resolved to exactly one production order) and the order must be in the record scope of the human the run acts for; then the run's subject is that order. Otherwise `agent_scope_unresolved`: the item stays with a person, and the response does not say whether such an order exists elsewhere.
Source: ADR-0064.R19

R1227. Taint: the run starts tainted (outside content). It reads its order and the order's lines (ADR-0064.R13), its work item with the extraction as evidence, its own drafts and reference data. The company's scrap reason codes, the active reasons of kind `scrap` (ADR-0074.R14), are passed as the closed list of the mapping step, a reading added to the same grouped question.
Source: ADR-0064.R19, ADR-0064.R19.N2

R1228. D1 `resolve` finds the operation by a scanned order-and-operation barcode first, then by a trusted operation number of the order.
Source: ADR-0064.R19

R1229. L1 `map_report` (seat classification) runs only when the operation is ambiguous, choosing one of at most five candidate operations; it maps free-text reasons to a reason code of the closed list or `none` and writes the note. Output `ProductionCaptureMapReportOutput`. It writes no quantity, lot or date.
Source: ADR-0064.R19

R1230. D2 `draft`: quantities, lot and posting date are copied from the extraction's normalized values as stated, with the field IDs as evidence (`INV-733`). It drafts `CreateOperationConfirmation`, `CreateProductionIssue` or `CreateProductionReceipt` (`is_draft_only`) with `entry_source` `capture_agent`; the plan shows the checks of ADR-0064.R22, the milestone's generated confirmations and the backflush lines (ADR-0034.R12), none chosen by the model.
Source: ADR-0064.R19

R1231. The capture agent may also draft time logs (`CreateOperationTimeLog`, `is_draft_only`; state `draft`) for its order; a person confirms them with `ConfirmOperationTimeLog`; it never starts, pauses or blocks a WO (ADR-0071.R9, ADR-0071.R17).
Source: ADR-0064.R19.N1

R1232. Gate: a person posts every capture draft (hard lock 3). Text in a report that says to post or names another order changes nothing: a tainted run may run only `is_draft_only` commands and read only its order.
Source: ADR-0064.R19

### C7 variance and C8 standards feedback (Phase 2)

R1233. C7 `production_variance` is a workflow on the analysis layer (ADR-0060.R18, ADR-0060.R19, ADR-0060.R23). Triggers: `ProductionCostSettlementPosted` for valued variances; a weekly schedule for in-flight usage variances (ADR-0064.R9); a controller's question. Facts: `production_variance_overview`, `GetProductionOrderUsageVariance`, `ListProductionOrderVarianceDriver`, ranked by ADR-0064.R11.
Source: ADR-0064.R20

R1234. C7 L1 writes a narrative plan of claim template codes with fact handles; code checks and renders every number. Templates carry preconditions computed by code: a favorable claim is not offered for the `remaining` category of an order completed in a period without receipts, so a negative residual (ADR-0035.R10) is never called a saving. Output: an explanation linked to orders and documents; information only; nothing posts.
Source: ADR-0064.R20

R1235. C8 standards feedback runs on `production_standard_review` (ADR-0064.R12). D1: code computes, per production version, the median and spread of actual scrap percent per operation, run time per unit and lead time over the qualifying orders. L1 `choose_standard` (seat analysis): which standard the evidence concerns, from candidate handles, with an explanation.
Source: ADR-0064.R21

R1236. C8 output is a note with the statistics. A change to a released revision is a new revision through ADR-0062, started by a person (no agent starts an agent, ADR-0050.R30); a fixed lead time of the version is a change proposal.
Source: ADR-0064.R21

### Production agent settings (Phase 2 agent types)

These settings serve only Phase 2 agent types (ADR-0078.R2); the reservation and `production.mes_import.*` settings belong to the Phase 1 production core.

R1237. The settings of the Settings section are definitions of ADR-0063's settings registry, in its vocabulary: storage `setting_value`, change effect `immediate`, and area `production`, `planning` or `agents` by the key's first segment.
Source: ADR-0064.R23

R1238. Tightening is immediate by one person with `edit` on the leaf; loosening is accepted only from an approved change proposal; a `neutral` row is changed directly with a reason (ADR-0063's asymmetric path). A loosening of a row with `outdates` `auto_post` marks the production import's auto-post evidence outdated; `promotion` means the agent type's stored promotion evidence does not cover the looser value.
Source: ADR-0064.R23

R1239. Code lists: ADR-0063's `code_list` bounds are `codes`; the allowed codes are closed lists: `expedite_supply`, `stock_transfer`, `alternative_version`, `reschedule`, `partial_staging`, `transfer_reservation`, `split_order` for `production.agent.shortage_candidate_kinds`, and `spreadsheet`, `photo`, `message_text` for `production.capture.enabled_sources`. A value outside them is `setting_out_of_bounds`.
Source: ADR-0064.R23

R1240. A `product_category` value applies to the category of the order's main output product (for a disassembly order, of the order's item).
Source: ADR-0064.R23

R1241. Import evidence, rule of three: `production.mes_import.min_evidence_drafts` is at least ⌈3 / `auto_post.max_error_rate`⌉ (ADR-0063's error ceiling: 300 at its default 1%), a declared order between `production.mes_import.min_evidence_drafts` and `auto_post.max_error_rate`; `production.mes_import.min_unchanged_percent` is at least 100 − that rate.
Source: ADR-0064.R23

R1242. The defaults reproduce ADR-0034: reservation at release, yield deviations as check results only, no automatic posting of shop-floor documents. `production.variance.rank_threshold_amount` 0 means off.
Source: ADR-0064.R23

R1243. Reservation modes of `production.reservation.mode`:
- `off`: neither release nor the sweep reserves; people run `ReserveProductionOrderComponent`.
- `on_release`: release reserves up to available to promise (ADR-0034.R9) and the sweep fills shortfalls of released orders.
- `scheduled`: release reserves only lines whose requested date lies within the window, with the check result `reservation_deferred` for the others, and the sweep reserves each line as it enters the window.
Source: ADR-0064.R23

R1244. The registry, `setting_value`, `UpdateCompanySetting`, the asymmetric path, the evidence marker and the catalog `settings.csv` are ADR-0063's. The rows of these settings are appended to that catalog with `source` naming ADR-0064; a note on ADR-0063.R29 records the new count, and its lab reads the catalog's own rows instead of a fixed list.
Source: ADR-0064.R23

### Production agent quality, budgets and catalog rows (Phase 2 agent types)

R1245. Quality and promotion values per agent type, proposed and flagged with ADR-0051.R9's budgets (ADR-0051.R7, ADR-0051.R9), for when the types are brought forward; the shadow agreement and shadow comparators serve live shadow, which returns in Phase 2 (ADR-0078.R6):
- `production`: golden set 90%, shadow agreement 90%, minimum cases 30 exceptions; shadow comparator: the chosen candidate (kind, target order, document) against what the planner did before the item closed.
- `production_capture`: golden set 95%, shadow agreement 95%, minimum cases 50 reports per source; shadow comparator: per field, the draft's value against the value the person posted.
- `production_variance`: golden set, shadow agreement, minimum cases and comparator as ADR-0060.R29 sets them.
Source: ADR-0064.R28

R1246. Per-run ceilings per agent type, proposed and flagged (LLM calls, tool calls, input tokens, output tokens, cost USD, seconds, rows read):
- `production`: 10, 120, 200,000, 10,000, 1.00, 600, 10,000.
- `production_capture`: 6, 30, 80,000, 5,000, 0.40, 180, 500.
- `production_variance`: 14, 40, 140,000, 12,000, 0.95, 180, 2,000.
Sweep runs make no LLM call and consume only tool-call and row budgets. The types have no daily budget of their own: the company's daily cap is the only daily tier (ADR-0078.R7).
Source: ADR-0064.R28

R1247. Catalog rows of the production agent: errors (DS-04) `yield_tolerance_exceeded` (validation) and `reservation_transfer_invalid` (validation); check results `yield_above_tolerance`, `activity_above_standard`, `operation_confirmation_duplicate_suspected`, `reservation_deferred`.
Source: ADR-0064.R29

R1248. Work item kinds: `production_order_exception` (planning); `production_component_shortage`, `production_completion_candidate`, `production_order_stalled`, `production_standard_review`, `shop_floor_report_extracted`, `production_import_review` (production).
Source: ADR-0064.R29

R1249. Commands and queries: `ListComponentShortage`, `EvaluateProductionOrderRelease`, `GetProductionOrderUsageVariance`, `ListProductionOrderVarianceDriver`, `RunProductionOrderCheck`, `ImportOperationConfirmation` (`production`); `GetProductionOrderPegging`, `ListShortageResolutionCandidate` (`planning`); `TransferStockReservation` (`inventory`). No new verb.
Source: ADR-0064.R29

R1250. Leaves: `agent_production`, `agent_production_capture`, `agent_production_variance`; template levels of ADR-0064.R1, and `production_planner` at `post` on `stock_reservation` so the planner can approve transfers.
Source: ADR-0064.R29

R1251. Invariants `INV-730` to `INV-741` of the block `INV-730` to `INV-759` (`INV-730`, `INV-731`, `INV-732`, `INV-733`, `INV-734`, `INV-735`, `INV-736`, `INV-737`, `INV-738`, `INV-739`, `INV-740`, `INV-741`) and edge cases `EC-200` to `EC-219` (`EC-200`, `EC-201`, `EC-202`, `EC-203`, `EC-204`, `EC-205`, `EC-206`, `EC-207`, `EC-208`, `EC-209`, `EC-210`, `EC-211`, `EC-212`, `EC-213`, `EC-214`, `EC-215`, `EC-216`, `EC-217`, `EC-218`, `EC-219`). Production rows have no first step until the production core step is numbered. DS-17 business event types: `shop_floor_report_received` and `production_performance_imported`.
Source: ADR-0064.R29

R1252. Decided by the architect (decision 9), each in the configurable direction with a safe default: the owner of scheduled runs is the agent type setting's workflow owner (ADR-0064.R3); the sweep is a workflow without an LLM step; cancellation is never drafted; completion candidates for disassembly orders (ADR-0064.R12); the scrap reason list as the closed list of a tainted step; the duplicate window's lower bound (ADR-0064.R22); reservation modes and window; transfers between production orders only, capped at the target's unreserved requirement (ADR-0064.R24); the reservation priority by requested date (ADR-0064.R7), which differs from ADR-0023.R13's first-come interim and is recorded with that question; the shortage candidates' selection and cap of 7; the numeric projection of posted capture rows (ADR-0064.R13); the import's evidence figures sized by the rule of three; the import's auto-post behind ADR-0043.R14's evidence (ADR-0064.R25); the purpose's fields and sources (ADR-0064.R26); budgets.
Source: ADR-0064.R30

R1253. Recorded as decided, not open: alternative production versions are the Phase 1 substitution path (decision 5); a split is a change order plus a new draft order (decision 6).
Source: ADR-0064.R30

R1254. Lab check `t25_production_agent.py`: pure functions for the settings registry, its bounds and change path, the shortage list, the release verdict, the reservation priority, the sweep with racing receipts and others' reservations, reservation modes, upward pegging, exceptions and action messages with tolerances and the bottom-up order, alternative versions on recomputed dates, completion candidates, the confirmation checks, capture scope and stated quantities, the import gate, reservation transfers, variance drivers and ranking, the global halt and the tool lists; with `--load`, on the schema of `load_all.py`: the new columns, kinds and purpose values with their checks and keys.
Source: ADR-0064.R31

### Agent mode `active`

R1255. Agent mode `active` (ADR-0050.R14) is the last state of the ADR-0059 lifecycle for agent types. `active` is `assisted` plus one thing: the type's drafts of the document types named at promotion may pass the gateway as tainted drafts. The agent still only drafts; floor 4 of ADR-0043.R9 and the tool list rules are unchanged.
Source: ADR-0065.R11

R1256. An agent type version names the document types it may draft for the gateway (`auto_post_document_types`). Setting `active` for a version that names none returns `agent_mode_not_declared`. The next version of the `purchase_invoice` agent type names `purchase_invoice`.
Source: ADR-0065.R11

R1257. Phase 1 has no live agent shadow: `assisted` comes from the evaluation (ADR-0078.R6), and `active` from the in-use draft acceptance. `UpdateAgentTypeSetting` to `active` runs only from an approved change proposal that another person approves (`approver_is_submitter`, also in the small-company mode), from a type already at `assisted` with the same behavior hash and seat models. It names one `agent_promotion_evidence` row per document type, with target mode `active`, computed by `CreateAgentPromotionEvidence` from `GetAgentDraftAcceptance`: the type's `assisted` drafts of that document type under the promoted behavior hash and seat models over at least two calendar months, at least N = ceil(3 / `auto_post.max_error_rate`) of them, at least (1 − rate) posted unchanged by people (the version the run wrote was posted with no later version), and none posted to another partner. Otherwise `shadow_evidence_insufficient` (a historical code name; Phase 1 has no live shadow). The executing transaction records the document types in `agent_type_setting.active_document_types`.
Source: ADR-0065.R11, ADR-0065.R11.N1

R1258. The effective mode is computed as ADR-0050.R14 states. `active` does not carry over a change of the behavior hash: until the type is promoted again on drafts of the new behavior, it counts as `assisted` for the gateway. Draft acceptance counts only drafts written under the current behavior hash. While an `agent_quality_below_threshold` item is open for the type, an `active` type counts as `assisted` for the gateway, whatever `agents.<agent_type>.drift_action` says, because drift that touches an acting path always suspends it (ADR-0063.R12; ADR-0078.R5, ADR-0078.R15).
Source: ADR-0065.R11, ADR-0065.R11.N1

R1259. Lowering `active` to `assisted` or below is direct, by one person, at once.
Source: ADR-0065.R11

### The `auto_post_advisor` agent type (Phase 2)

R1260. The `auto_post_advisor` agent type (D8) is a Phase 2 agent type: it reads months of gateway outcomes that do not exist before go-live. Until then people propose gateway settings and decision tables, and the assistant in `act` mode may draft them on request (ADR-0078.R2). The rules below state the advisor once it exists.
Source: ADR-0065.R18, ADR-0065.R18.N1

R1261. The advisor is a drafting agent type on the runtime of ADR-0050. A person starts it for a document type. It reads the tools of ADR-0065.R17, chooses among the threshold candidates code gave it and writes the explanation. It drafts a decision table version for the decision point (`CreateDecisionTableVersion`) and a change proposal with `UpdateCompanySetting` items (`CreateChangeProposal`), both drafts, with the backtest attached as evidence.
Source: ADR-0065.R18

R1262. The advisor never submits, approves, enables or changes a setting, a table state, a policy rule or an agent mode; those commands are on no agent tool list (ADR-0050.R30). Its tool list holds only held-out filtered queries (ADR-0059.R16).
Source: ADR-0065.R18

R1263. The advisor's lifecycle is ADR-0059's: a person reviews the drafts; the table version moves draft, backtested (evidence from `EvaluateAutoPostBacktest`, stored by `CreateArtifactEvidence`), shadow, active through an approved change proposal; the settings change through another person's approval; the gateway then runs in shadow (ADR-0065.R15), and a person enables. The table's monitoring and demotion follow ADR-0059.R21, and the gateway's demotion follows ADR-0065.R16.
Source: ADR-0065.R18

R1264. Advisor taint: posted invoices drafted by agents are tainted versions, so its runs become tainted; it only drafts, and its drafts are written tainted and submitted by a person (ADR-0059.R13). It is an agent type that may read outside content for the budget pool (ADR-0050.R22 note). Its declared values (budgets, seats, evaluation suite) come with its first agent type version (DS-34), within the company's settings. Leaf `agent_auto_post_advisor` (ADR-0054.R24).
Source: ADR-0065.R18

### Agents and costing sheets (Phase 2 agent types)

The rules of this section concern the `production` and `production_variance` agent types, which are Phase 2 types (ADR-0078.R2).

R1265. No costing agent type exists; ADR-0051 leaves a period-close assistant for later, and it will inherit this rule. The `production` agent type (ADR-0064.R1) gains the subject table `costing_sheet`. `product_engineering` estimates with the sheet unchanged (ADR-0062.R12).
Source: ADR-0072.R18

R1266. The agent drafts sheets, rows, assignments, details and mappings as change proposals (ADR-0029.R2, ADR-0029.R4); a person submits, and a person other than the human the run acted for approves.
Source: ADR-0072.R18

R1267. A rate enters a proposal only from a person's import batch or note, copied as a stated value with its source (ADR-0051.R1; ADR-0062.R16), or from `GetCostingRateSuggestion` (module `production`, computed query, `costing_structure` at `read`, field class `cost`): for a surcharge row, the actual pool cost of the credited cost center over the last N closed periods (default 3) ÷ the row's actual base, with its inputs. The model never chooses, sees or writes a rate (the type's field classes stay none).
Source: ADR-0072.R18

R1268. The variance agent (`production_variance`, field class `cost`) may read `GetCostCenterAbsorption` to explain absorption gaps.
Source: ADR-0072.R18

## Invariants

`INV-731` and `INV-733` belong to Phase 2 agent types (`production_capture`), which cannot run in Phase 1 (ADR-0078.R2).

Statements are those of `invariants.csv`. This chunk holds the rows whose catalog source is a rule of this chunk, or a
rule of ADR-0064 stated in no chunk of `agents` and named only by R1251. `INV-730`, `INV-732` and `INV-737` (source
ADR-0064.R4 first) stand in chunk 6. All check point `day`; first step: the production core step (number pending author).

| Invariant | Name | Check point | Statement | Protects |
| --- | --- | --- | --- | --- |
| `INV-731` | `capture_runs_scoped` | day | Every `production_capture` run was tainted from its start, has scope kind `subject` on a production order, and every row reference in its steps is that order or its lines, its work item and evidence, its own drafts or reference data. | R1226, R1227 |
| `INV-733` | `capture_quantities_as_stated` | day | Every quantity, lot and posting date on a draft written by a `production_capture` run equals the normalized value of an extraction field named in its evidence. | R1230 |
| `INV-734` | `reservation_transfers_by_proposal` | day | Every reservation with `transferred_from_reservation_id` has the company, item, warehouse and lot of its source, was created by a `TransferStockReservation` executed from an approved change proposal, in the transaction that reduced its source by the same quantity, and did not take the target line above its open requirement; no reservation command of a production agent run reduced another demand line's reservation. | R1206; ADR-0064.R24 |
| `INV-735` | `component_reservations_within_requirement` | day | Per production order component line, open and picked reservations never exceed the open requirement. | R1207; ADR-0064.R5 |
| `INV-736` | `shortage_policy_input_matches_check` | day | Every `has_component_shortage` policy input recorded at `Submit` of a production order equals whether `EvaluateProductionOrderRelease` returned `component_short` for that version on that business date. | ADR-0064.R6 |
| `INV-738` | `production_exceptions_on_live_orders` | day | Every `planning_exception` of kind `production_order_start_overdue` or `production_order_overdue` names an order that was approved and not technically complete on the run's planning date, and whose date plus the grace setting was before that date. | R1219 |
| `INV-739` | `variance_drivers_sum` | day | For every settled order, period and variance category, the contributions of `ListProductionOrderVarianceDriver` sum to the category's row of `production_order_variance`. | ADR-0064.R10 |
| `INV-740` | `import_postings_gated` | day | Every operation confirmation posted by an `integration` actor has `entry_source` `production_import` and an `external_reference`, was posted while `production.mes_import.auto_post` was true under a policy rule enabled with evidence that met the import evidence settings in force, by a credential holding `post` on `operation_confirmation`, and had no check result in its plan at posting. | R1241; ADR-0064.R25 |
| `INV-741` | `scheduled_reservations_within_window` | day | In reservation mode `scheduled`, no reservation made by a release or a sweep is for a component line whose requested date lay beyond the window on that business date. | R1205, R1243 |

## Edge cases

`EC-200`, `EC-201`, `EC-202` and `EC-206` to `EC-211` belong to Phase 2 agent types, which cannot run in Phase 1 (ADR-0078.R2).

Rows of `edge-cases.csv` whose source is a rule of this chunk, or a rule of ADR-0064 stated in no chunk of `agents` and
named only by R1251. `EC-216` and `EC-217` (sources ADR-0064.R4, ADR-0064.R3) stand in chunk 6.

| Edge case | Name | Case | Outcome | Protects |
| --- | --- | --- | --- | --- |
| `EC-200` | `shortage_cleared_while_transfer_pending` | A goods receipt covers the target's shortage while a `transfer_reservation` proposal waits; at execution the target's short quantity (unreserved requirement minus available to promise) is 0, so the transfer fails with `reservation_transfer_invalid` although nothing reserved the receipt, and the next `RunProductionOrderCheck` closes the shortage item. | `must_reject:reservation_transfer_invalid`, `must_succeed` | R1213; ADR-0064.R24 |
| `EC-201` | `reservation_sweeps_race` | Two sweeps start on one goods receipt; together they never reserve more than the receipt or a line's open requirement (a parallel test). | `must_succeed` | R1207 |
| `EC-202` | `sweep_respects_sales_reservation` | Available stock is reserved for a sales order; the sweep reserves nothing from it and the shortage stays listed. | `must_succeed` | R1206 |
| `EC-203` | `multi_level_lateness_bottom_up` | A late component order delays its parent; the component order's reschedule is proposed before the parent's, and the dates are consistent. | `must_succeed` | R1221 |
| `EC-204` | `alternative_version_invalid_on_new_start` | An alternative version valid on the order's end date but not on the recomputed start is not offered as a candidate. | `must_succeed` | R1212 |
| `EC-205` | `reschedule_tolerances` | With an out-tolerance of 3 days a 2-day postponement raises no message, while with the in-tolerance at 0 a 1-day lateness is raised. | `must_succeed` | R1219 |
| `EC-206` | `capture_order_outside_scope` | A capture report names an order of a branch outside the human's record scope; the run is refused unresolved and the response does not reveal the order. | `must_reject:agent_scope_unresolved` | R1226 |
| `EC-207` | `capture_yield_tolerance` | A capture report with yield above the previous operation inside the tolerance drafts with a check result; outside it the draft carries `yield_above_tolerance` under `warn` and is refused under `reject`. | `must_reject:yield_tolerance_exceeded`, `must_succeed` | ADR-0064.R22 |
| `EC-208` | `capture_duplicate_report` | The same photo sent twice is one extraction; the same numbers typed again within the window give `operation_confirmation_duplicate_suspected`. | `must_reject:extraction_purpose_exists`, `must_succeed` | ADR-0064.R22 |
| `EC-209` | `capture_text_instructions` | A report's text says to post now and names another order; the run stays draft-only and reads only its order. | `must_succeed` | R1232; ADR-0064.R4 |
| `EC-210` | `capture_milestone_confirmation` | A report for a milestone operation; the earlier operations' generated confirmations appear in the draft's plan, not chosen by the model. | `must_succeed` | R1230 |
| `EC-211` | `capture_backflush_missing_stock` | A drafted confirmation would backflush more than the supply bin holds; its simulation shows `negative_stock` and the readiness note explains it. | `must_reject:negative_stock` | R1202, R1230 |
| `EC-212` | `completion_proposal_then_late_receipt` | An order at 97% received under a 95% setting gets a completion proposal; after a late receipt a person reopens it. | `must_succeed` | R1224 |
| `EC-213` | `variance_negative_residual` | An order completed in a period without receipts; the explanation never calls the negative residual a saving. | `must_succeed` | R1234 |
| `EC-214` | `rework_and_disassembly_in_agent_queries` | Rework and disassembly orders appear correctly in the shortage list, completion candidates and usage variance. | `must_succeed` | ADR-0064.R5, ADR-0064.R12 |
| `EC-215` | `make_to_order_sales_line_canceled` | The sales line of a not-started make-to-order order is canceled; a cancel message is raised and recommended in a note; the agent never cancels the order. | `must_succeed` | R1219, R1222 |
| `EC-218` | `production_import_auto_post_gate` | A production import with auto-post enabled posts a row whose plan has no check result as `integration` only once the policy rule is enabled with evidence (300 drafts over 2 months, 99% posted unchanged); a row with any check result stays a draft; a repeated reference is refused. | `must_reject:duplicate_external_document`, `must_succeed` | R1241; ADR-0064.R25 |
| `EC-219` | `reservation_transfer_only_by_proposal` | A reservation transfer outside an approved proposal is refused; through one, the source is reduced and the target gains the same quantity. | `must_reject:proposal_required`, `must_succeed` | ADR-0064.R24 |
| `EC-227` | `advisor_drafts_only` | The advisor proposes thresholds and a table from six months of invoices; it drafts a table version and a change proposal and cannot submit, approve or enable them; its tool list excludes held-out cases. Phase 2 case: it starts from the deferred `auto_post_advisor` and cannot run in Phase 1 (ADR-0078.R9a). | `must_succeed` | R1261, R1262 |

## Settings

The `production.agent.*`, `production.capture.*`, `production.feedback.*` and `production.variance.*` rows serve only Phase 2 agent types (ADR-0078.R2); `production.reservation.*` and `production.mes_import.*` belong to the Phase 1 production core.

All rows: storage `setting_value`, change effect `immediate`. Bounds, direction, leaf and outdates as R1237 and R1238 use them.

| Key | Value type | Scopes | Core default | Bounds | Direction | Leaf | Outdates | Rule |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `production.reservation.mode` | `enum` | `company` | `on_release` | `off\|on_release\|scheduled` | `neutral` | `production_structure` | `none` | R1204, R1243 |
| `production.reservation.window_days` | `integer` | `company` | `14` | `0..180` | `neutral` | `production_structure` | `none` | R1205, R1243 |
| `production.agent.readiness_horizon_days` | `integer` | `company` | `14` | `0..90` | `neutral` | `agent_production` | `none` | R1201 |
| `production.agent.shortage_candidate_kinds` | `code_list` | `company` | `["expedite_supply", "stock_transfer", "alternative_version", "reschedule"]` | `codes` | `subset_tighter` | `agent_production` | `promotion` | R1211, R1239 |
| `planning.production_reschedule_in_tolerance_days` | `integer` | `company` | `0` | `0..30` | `lower_tighter` | `planning_run` | `none` | R1219 |
| `planning.production_reschedule_out_tolerance_days` | `integer` | `company` | `3` | `0..60` | `lower_tighter` | `planning_run` | `none` | R1219 |
| `planning.production_rescheduling_horizon_days` | `integer` | `company` | `60` | `1..365` | `neutral` | `planning_run` | `none` | R1219 |
| `production.order.start_grace_days` | `integer` | `company` | `1` | `0..30` | `neutral` | `production_structure` | `none` | R1219 |
| `production.order.overdue_grace_days` | `integer` | `company` | `0` | `0..30` | `neutral` | `production_structure` | `none` | R1219 |
| `production.order.stalled_days` | `integer` | `company` | `5` | `1..60` | `neutral` | `production_structure` | `none` | R1223; ADR-0064.R12 |
| `production.completion.propose_at_percent` | `percent` | `company;product_category` | `100` | `80..100` | `higher_tighter` | `production_structure` | `none` | R1223, R1240 |
| `production.confirmation.yield_tolerance_percent` | `percent` | `company;product_category` | `0` | `0..100` | `lower_tighter` | `operation_confirmation` | `auto_post` | R1240; ADR-0064.R22 |
| `production.confirmation.over_tolerance_action` | `enum` | `company` | `warn` | `warn\|reject` | `order:warn<reject` | `operation_confirmation` | `auto_post` | R1238; ADR-0064.R22 |
| `production.confirmation.activity_tolerance_percent` | `percent` | `company;product_category` | `25` | `0..500` | `lower_tighter` | `operation_confirmation` | `auto_post` | R1240; ADR-0064.R22 |
| `production.confirmation.duplicate_window_minutes` | `integer` | `company` | `120` | `10..1440` | `higher_tighter` | `operation_confirmation` | `auto_post` | R1252; ADR-0064.R22 |
| `production.capture.enabled_sources` | `code_list` | `company` | `["spreadsheet"]` | `codes` | `subset_tighter` | `agent_production_capture` | `promotion` | R1225, R1239 |
| `production.mes_import.auto_post` | `boolean` | `company` | `false` | `true\|false` | `false_tighter` | `operation_confirmation` | `none` | R1242; ADR-0064.R25 |
| `production.mes_import.min_evidence_drafts` | `integer` | `company` | `300` | `150..3000` | `higher_tighter` | `operation_confirmation` | `auto_post` | R1241 |
| `production.mes_import.min_unchanged_percent` | `percent` | `company` | `99` | `98..100` | `higher_tighter` | `operation_confirmation` | `auto_post` | R1241 |
| `production.mes_import.min_evidence_months` | `integer` | `company` | `2` | `1..12` | `higher_tighter` | `operation_confirmation` | `auto_post` | R1241 |
| `production.variance.rank_threshold_percent` | `percent` | `company;product_category` | `5` | `0..100` | `neutral` | `report_production` | `none` | R1233 |
| `production.variance.rank_threshold_amount` | `decimal` | `company` | `0` | `0..` | `neutral` | `report_production` | `none` | R1242 |
| `production.variance.top_n` | `integer` | `company` | `20` | `1..200` | `neutral` | `report_production` | `none` | R1233 |
| `production.feedback.enabled` | `boolean` | `company` | `false` | `true\|false` | `neutral` | `agent_production` | `none` | R1235 |
| `production.feedback.min_orders` | `integer` | `company` | `5` | `3..100` | `neutral` | `agent_production` | `none` | R1235 |
| `production.feedback.min_periods` | `integer` | `company` | `2` | `1..12` | `neutral` | `agent_production` | `none` | R1235 |

`settings.csv` gives area `agents` for `production.agent.readiness_horizon_days` and
`production.agent.shortage_candidate_kinds`, not the area of the first segment that R1237 states.

Reads: `auto_post.max_error_rate` (R1241, R1257) and `agents.<agent_type>.drift_action` (R1258), whose rows stand elsewhere.

## Conflicts

CONFLICT ADR-0064.R19: ADR-0064.R19.N1 (ADR-0071) adds draft time logs to the capture agent and ADR-0064.R19.N2 (ADR-0074) fixes the scrap reason list as active reasons of kind scrap; applied in R1227 and R1231.
CONFLICT ADR-0065.R11: ADR-0065.R11.N1 (ADR-0078) removes the live agent shadow; assisted comes from the evaluation and a behavior hash change makes an active type count as assisted until promoted again; applied in R1257 and R1258.
CONFLICT ADR-0065.R18: ADR-0065.R18.N1 (ADR-0078) makes the advisor a Phase 2 agent type; until then people, or the assistant in act mode, draft gateway settings and decision tables; applied in R1260.
CONFLICT ADR-0064.R28: the shadow agreement and shadow comparators serve live shadow, which returns in Phase 2 (ADR-0078.R6), and the daily cost and run values per type are dropped, the company's daily cap being the only daily tier (ADR-0078.R7); applied in R1245 and R1246.
CONFLICT ADR-0064.R14: C1 to C8 are workflows of Phase 2 agent types, governed by ADR-0064.R1.N2 and ADR-0078.R2 (R1201).

## Trace

| Source | Where |
| --- | --- |
| ADR-0064.R14 | R1201-R1203 |
| ADR-0064.R15 | R1204-R1209 |
| ADR-0064.R16 | R1210-R1218 |
| ADR-0064.R17 | R1219-R1222 |
| ADR-0064.R18 | R1223, R1224 |
| ADR-0064.R19 | R1225-R1230, R1232 |
| ADR-0064.R19.N1 | R1231 |
| ADR-0064.R19.N2 | R1227 |
| ADR-0064.R20 | R1233, R1234 |
| ADR-0064.R21 | R1235, R1236 |
| ADR-0064.R23 | R1237-R1244 |
| ADR-0064.R28 | R1245, R1246 |
| ADR-0064.R29 | R1247-R1251 |
| ADR-0064.R30 | R1252, R1253 |
| ADR-0064.R31 | R1254 |
| ADR-0065.R11 | R1255-R1259 |
| ADR-0065.R11.N1 | R1257, R1258 |
| ADR-0065.R18 | R1260-R1264 |
| ADR-0065.R18.N1 | R1260 |
| ADR-0072.R18 | R1265-R1268 |
