Module: production    Chunk: 3 of 7    Source ADRs: ADR-0034, ADR-0035
Build step(s): 3, 5    Generated from index: 30d5706    Compiled by: Claude Opus 5.5, 2026-11-21

# `production` compiled spec, chunk 3: confirmations, receipts, serials, effect classes, and production costing

## Purpose

This chunk states the part of `production` law on: the shop-floor documents `operation_confirmation` and `production_receipt` with backflush, make to order, the cost object, serials and traceability, effect classes, events, locks and the reserved catalog rows of ADR-0034, and the periodic actual costing of ADR-0035 rules 1 to 14 (collection, pools, WIP, abnormal and residual cost, outputs, the job's postings, splits and the cost estimate). Production orders, issues and master data are in the other chunks; account determination rows are `ledger` law, read here.

## Entities and tables

DDL: `docs/design/DS-43-54-planning-production.sql`; `cost_object` is in `docs/design/DS-06-universal-journal.sql`.

| Table | Meaning | Key | Parent | Owner |
| --- | --- | --- | --- | --- |
| `operation_confirmation` | Posting document confirming yield, scrap and activities of an internal operation (R401-R409) | `id` = document; unique (`company_id`, `id`, `production_order_operation_id`) | `production_order` | `production` |
| `operation_confirmation_activity` | Actual and proposed activity quantity per activity type of a confirmation (R402) | `id`; unique (`operation_confirmation_id`, `activity_type_id`) | `operation_confirmation` | `production` |
| `operation_progress_component` | Every generated backflush line, keyed by its calling document: a confirmation, a receipt or a service receipt (R407) | `id`; exactly one of `operation_confirmation_id`, `production_receipt_id`, `service_receipt_id` | `production_order` | `production` |
| `production_receipt` | Posting document receiving outputs, with optional receipt scrap (R410-R417) | `id` = document; unique (`company_id`, `id`, `production_order_id`) | `production_order` | `production` |
| `production_receipt_line` | Output line with quantity in the line unit block, lot or serial, bin, handling unit, `stock_status` (`available`, `quality_inspection`) and movement type (R410) | `id`; unique (`production_receipt_id`, `line_number`) | `production_receipt` | `production` |
| `cost_object` | Cost collector of kind `production_order` (one per order, naming `production_order_id`) or `cost_pool` (one per cost center, naming `cost_center_id`), `state` `open` or `closed` (R419, R421) | `id`; unique (`company_id`, `code`); unique (`company_id`, `id`, `production_order_id`) | `company` | `production` |
| `pool_allocation_rule` | How one pool group (`labor`, `overhead`, `other`) of a cost center is allocated, by `driver` (`activity_type`, `output_quantity`, `standard_material_quantity`, `preliminary_material_amount`); `activity_type_id` is set exactly when the driver is `activity_type` (R443) | `id`; unique (`cost_center_id`, `pool_group`) | `cost_center` | `production` |
| `normal_capacity` | Normal capacity per cost center, driver (as `pool_allocation_rule`) and posting period, in the driver's unit; `activity_type_id` is set exactly when the driver is `activity_type` (R444) | `id`; unique (`cost_center_id`, `driver`, `activity_type_id`, `posting_period_id`), nulls not distinct | `cost_center` | `production` |
| `production_cost_settlement` | One internal document per run of the period-end costing job (R440, R441) | `id` = document | `posting_period` | `production` |
| `production_cost_settlement_line` | Settlement amount keyed by cost object, cost component and step (`issue_revaluation`, `pool_allocation`, `unabsorbed_overhead`, `abnormal_cost`, `residual_cost`, `wip_transfer`, `receipt_revaluation`) (R440) | `id`; unique (`production_cost_settlement_id`, `cost_object_id`, `cost_component`, `step`) | `production_cost_settlement` | `production` |
| `production_order_period_cost` | Per order, period and component: opening, incurred, abnormal, residual, to-output and closing amounts, written only by the job (R454) | `id`; unique (`production_order_id`, `posting_period_id`, `cost_component`) | `production_order` | `production` |
| `cost_estimate` | Cost estimate header per production version (or configured item), `state` `draft` or `released`, price basis, costing lot quantity (R457-R463) | `id`; (`company_id`, `id`); one released estimate per (`company_id`, `production_version_id`, costing date) | `production_version` | `production` |
| `cost_estimate_line` | Estimate line per cost component, component item, activity type or surcharge row, rolled up by level (R457, R459) | `id`; unique (`cost_estimate_id`, `line_number`) | `cost_estimate` | `production` |
| `activity_rate` | Planned rate per work center, activity type and period (R459) | `id`; unique (`work_center_id`, `activity_type_id`, `posting_period_id`) | `work_center` | `production` |

Named here, rows in other chunks: `cost_estimate_gap`, `cost_estimate_sheet_row`, `operation_confirmation_time_log`, `production_order_output_serial`, `production_issue`, `production_order`, `production_structure`, `production_version`.

Reads: `stock_value`, `stock_quantity`, `material_document_line`, `lot`, `serial_number`, `bin` (`inventory`); `cost_center`, `posting_period`; `reason` (kind `scrap`); `document`.

## Commands and queries

Authorization leaves (catalog `authorization-areas.csv`): the document types `operation_confirmation` and `production_receipt` under area `production`; `production_cost_settlement` under `finance`. The verb levels are the catalog's (`Create`: edit; `Post`: post; `Cancel`: edit). Role template `shop_floor_lead` posts confirmations and receipts.

| Name | Actor and authorization | Input | Effect | Events | Error codes |
| --- | --- | --- | --- | --- | --- |
| `Post` (`operation_confirmation`) | `posting`; leaf `operation_confirmation` at post; agents only draft | order, `operation_number`, yield, scrap, reason, `is_final`, activities, `posting_date`, people or teams | Records progress, backflushes components, may create the automatic receipt (R401-R409, R417) | document events of ADR-0009.R22 | `operation_not_confirmable`, `negative_stock`, `operation_time_log_open`, `receipt_above_tolerance`; check result `yield_above_previous_operation` |
| `Post` (`production_receipt`) | `posting`; leaf `production_receipt` at post | order, output lines, receipt scrap and reason | Posts the receipt material document and backflush at receipt (R410-R416) | document events of ADR-0009.R22 | `receipt_above_tolerance`, `receipt_scrap_not_allowed`, `negative_stock`, `by_product_price_missing`, `preliminary_price_missing` |
| `AssignProductionOrderOutputSerial` | `other`; area not stated | order, output, serial codes | Assigns serials to a serial-tracked output (R422) | not stated | none stated |
| `GetTraceability` | query; area not stated | item and lot or serial, `backward` or `forward` | Walks the trace links (R425) | none | none stated |
| `GetProductionOrderStatus` | query; area not stated | order | Progress, components, shortages, postings and cost object (R430) | none | none stated |
| `ListProductionOrder` | query; area not stated | not stated | Lists production orders (R430) | none | none stated |
| `CreateCostEstimate` | `other`, `is_draft_only`; area not stated | production version or configured item, costing date, price basis, `costing_lot_quantity` | Computes the estimate on the server (R460) | not stated | `preliminary_price_missing` |
| `ReleaseCostEstimate` | `master_data_change`, proposal-bound for agents; area not stated | estimate | Freezes it as the version's benchmark (R460) | not stated | `cost_estimate_incomplete` |

Contract functions and jobs, not registry commands: `production.contract.record_operation_progress` (R408); `plan_production`, `create_production_order_from_plan`, `get_order_inspection_quantities` (R430); the period-end costing job writing `production_cost_settlement` as `system` (R440, R441), which fails with `pool_allocation_rule_missing` or `production_cost_not_balanced` and gives the check results `normal_capacity_missing` and `planned_wip_capped`. Error codes bound to no command of this chunk: `as_built_serial_missing` (issue lines, R424), `subledger_not_active` and `co_product_weights_zero` (order release, R420, R456), `cost_object_closed`, `control_dimension_missing` and `material_on_cost_pool` (posting handlers, R421, R435, R445).

## Rules

### Operation confirmation

R401. `operation_confirmation` is an internal posting document (reversible). It names the order and `operation_number`, an `internal` operation of the order (`production_order_operation_id`), otherwise `operation_not_confirmable`. It carries the execution `work_center_id`, `yield_quantity`, `scrap_quantity`, an optional `scrap_reason_id` (a reason of kind `scrap`, which needs a scrap quantity above 0; whether a scrap needs a reason is the setting `documents.reason_required.scrap` of ADR-0074.R22), `is_final`, `posting_date`, optional people or teams, and `entry_source` (`person`, `capture_agent`, `production_import`).
Source: ADR-0034.R12, ADR-0034.R12.N3, ADR-0034.R12.N4, ADR-0034.R12.N5

R402. Actual activity quantities (`operation_confirmation_activity`) default to the standards: `per_base_quantity` activities scaled by yield + scrap, and `per_order` activities only on the first confirmation of the operation. Each activity stores its `proposed_quantity`, taken from the time logs the confirmation links (`operation_confirmation_time_log`, ADR-0071.R11). A confirmation with yield and scrap 0 records time only. Activities are recorded for costing and DS-53 values them; costing reads only confirmations, never time logs.
Source: ADR-0034.R12, ADR-0034.R12.N4

R403. A final confirmation is refused while a setup or run log of the operation is open (`operation_time_log_open`) (ADR-0071.R2, ADR-0071.R11, ADR-0071.R16).
Source: ADR-0034.R12.N4

R404. Previous operation: a cumulative yield + scrap above the previous internal operation's cumulative yield gives the check result `yield_above_previous_operation`.
Source: ADR-0034.R12

R405. Milestones: confirming a milestone raises each earlier internal, non-milestone operation, back to the previous milestone, to the milestone's cumulative yield + scrap. Their activities and backflush are included in the same document, and external operations are skipped.
Source: ADR-0034.R12

R406. Backflush: for each `backflush_at_operation` component of a confirmed operation, quantity = max(0, round_up(requirement × cumulative (yield + scrap) / Q) − the quantity already backflushed for that line). Fixed-quantity components are backflushed whole at the first confirmation. Stock comes from the supply bin, with lots in the order of ADR-0023.R14 applied inside that bin. Missing stock rejects the confirmation with `negative_stock`, naming the component. Generated backflush lines carry the line unit block in the inventory unit (source `identity`), rounded up (ADR-0056.R8, ADR-0056.R9).
Source: ADR-0034.R12, ADR-0034.R12.N2

R407. One table, the production-owned `operation_progress_component`, holds every generated backflush line: calling document type and ID, order component line, material document line. Confirmations, service receipts and backflush at receipt all write it, at `Post`. The lines appear in `plan.stock_movements`, not in approved version content. Plans and traceability read this one table, and `INV-112` covers every calling document.
Source: ADR-0034.R12, ADR-0034.R12.N1

R408. Progress interface: confirmations write progress through `production.contract.record_operation_progress`. DS-55's service receipts for external operations use the same interface, and their backflush lines go to `operation_progress_component`, keyed by the calling document (ADR-0037.R5).
Source: ADR-0034.R12

R409. The capture agent is the agent type `production_capture`: tainted, scope `subject` on one production order resolved from a trusted order number of an extraction of purpose `shop_floor_report`, quantities copied as stated, drafts only; a human posts (ADR-0029.R11). The agent type `production_capture` is Phase 2, registered with mode `off`; manual capture stays in Phase 1 (ADR-0078.R2). Confirmations get the yield, activity and duplicate checks of ADR-0064.R22. A deterministic production import may post them as `integration` only behind `production.mes_import.auto_post` and the evidence of ADR-0043.R14 (ADR-0064.R19, ADR-0064.R25).
Source: ADR-0034.R12, ADR-0034.R12.N3

### Production receipt

R410. `production_receipt` is an internal posting document (reversible). Its lines name the output line, the quantity in the line unit block (ADR-0056.R9), the lot (created at receipt when lot-tracked) or serials, the bin and the handling unit. It posts a material document with movement type `production_receipt`, `co_product_receipt`, `by_product_receipt` or `disassembly_receipt`, and the cost object.
Source: ADR-0034.R13, ADR-0034.R13.N2

R411. Bins and putaway: output posts to the `output_bin_id` of the execution work center of the order's last internal operation. Without one, or without a routing, it posts to the bin the putaway rules give (ADR-0023.R7, ADR-0023.R11). A putaway task from a production bin is created by the putaway rules.
Source: ADR-0034.R13, ADR-0034.R13.N4

R412. Status: `quality_inspection` when the product requires inspection, that is when its `inspection_points` contains `production_output`; otherwise `available`. In-process inspection lots come from operation confirmations of operations a released `in_process` plan names (ADR-0070.R2, ADR-0070.R8).
Source: ADR-0034.R13, ADR-0034.R13.N3

R413. The receipt's value is DS-53's: a provisional value settled by the period solve.
Source: ADR-0034.R13

R414. Tolerance: cumulative net receipts of the main output above G × (1 + `overdelivery_tolerance_percent` / 100) are rejected (`receipt_above_tolerance`). The check compares inventory quantities. By-products and co-products are not capped. The tolerance is business behavior, flagged, default 0.
Source: ADR-0034.R13, ADR-0034.R13.N2

R415. Backflush at receipt: `backflush_at_receipt` components are backflushed as in the confirmation backflush, with G as the denominator and cumulative net main-output receipts as the progress, and their lines are written to `operation_progress_component`, keyed by the receipt. On an order with receipt scrap S, the share is max(R / G, (R + S) / Q), which is R / G when S = 0.
Source: ADR-0034.R13, ADR-0034.R13.N1, ADR-0034.R13.N4

R416. Receipt scrap: on an order without internal operations, a receipt may record `scrap_quantity` with `scrap_reason_id`, alone or with lines; otherwise `receipt_scrap_not_allowed` (`INV-844`; ADR-0071.R4).
Source: ADR-0034.R13.N4

R417. Automatic receipt: when the version sets `is_receipt_on_final_confirmation`, the final progress record of the order's last operation (a confirmation when it is internal, a service receipt when it is external, ADR-0037.R5) also creates and posts the receipt of that operation's cumulative yield minus the net receipts so far, for untracked or lot-tracked output:
- the confirmation names the lot;
- the confirmation's policy decision covers both documents;
- reversing the confirmation reverses its receipt first, in the same command;
- a tolerance failure rejects the confirmation;
- serial-tracked output is never received automatically.
Source: ADR-0034.R13

### Make to order and the cost object

R418. Make to order: when `for_demand_supply_line_id` is set and that demand is in the same warehouse, `available` output is reserved for it, up to that demand's unreserved open quantity. Output in inspection is reserved when it is released: a `production` consumer of `WarehouseTaskConfirmed` runs the reservation (effect class `other`). Planning nets the line against this order through the supply link (ADR-0036.R9). This automatic reservation is interim, flagged business behavior (open question).
Source: ADR-0034.R14

R419. `cost_object` is owned by `production`. It has `kind`, which is `production_order` (one per order) or `cost_pool` (one per cost center that collects production cost); `production_order_id` or `cost_center_id`, matching the kind; and `state` (`open`, `closed`). At release the order gets a cost object of kind `production_order`, and its lines (issues, returns, receipts, activities, settlement) carry it.
Source: ADR-0034.R15, ADR-0035.R1

R420. Whether the `cost_object` subledger must be activated (ADR-0025.R4) before the first release is an accounting gate. Interim, flagged for DS-53 and the author: required, otherwise `subledger_not_active`.
Source: ADR-0034.R15

R421. A `production_order` cost object becomes `closed` when its order is closed (ADR-0034.R7). A `cost_pool` cost object becomes `closed` when its cost center is deactivated and the period's job has left its balance at zero. A line naming a closed cost object is rejected with `cost_object_closed`, except the lines of `production_cost_settlement`, which may still post to it when a period is reopened and solved again (ADR-0034.R6).
Source: ADR-0035.R1.N1

### Serials and traceability

R422. Assigned serials: for serial-tracked output, the client supplies serial codes at release, up to G, or later by `AssignProductionOrderOutputSerial` (rows of `production_order_output_serial`). A serial assigned to a `standard` order must have no stock and no other open assignment; a `rework` order assigns the input serial. An issue line's `output_serial_number_id`, and a receipt's serials, must be assigned serials of the same order. Serials not received are freed at technical completion or `Cancel`.
Source: ADR-0034.R16

R423. Order level: every output lot or serial links to every component lot or serial issued, backflushed or returned on the order.
Source: ADR-0034.R16

R424. Unit level (as built): an issue line that names an output serial links its component to that serial only. When the version sets `is_as_built_required`, every serial or lot-tracked component issue must name one (`as_built_serial_missing`).
Source: ADR-0034.R16

R425. `GetTraceability` (item and lot or serial, `backward` or `forward`) walks these links across orders, receipts and deliveries, excluding reversed lines. Links are derived from issue, generated and receipt lines, never stored separately.
Source: ADR-0034.R16

### Effect classes, agents, events and locks

R426. Effect classes (ADR-0027.R17): `other` for create, update, submit, approve, reject and cancel of the order, `ReserveProductionOrderComponent` and `AssignProductionOrderOutputSerial`; `posting` for `Post` of the three shop-floor documents. `CompleteProductionOrder` and `ReopenProductionOrder` are `other` and `is_proposal_bound` (ADR-0029.R2), with the order's version as `expected_version`; agents reach them only through change proposals. The close job runs as `system`. Rescheduling by an agent is a drafted update or change order.
Source: ADR-0034.R17

R427. Registry flags: `production_order` and `production_issue` have `is_approval_hold_allowed: true`. `operation_confirmation` and `production_receipt` record facts on the floor and have `is_approval_hold_allowed: false`, so they never wait in a pool and a rank becomes `human_post` (ADR-0043.R10). Pools: `production_order` in `mo`, `production_issue` in `consumption` (ADR-0055.R2).
Source: ADR-0034.R17.N1

R428. The production and capture agents are designed: agent types `production`, `production_capture` and `production_variance` (ADR-0064.R1), Phase 2 agent types registered with mode `off` in Phase 1 (ADR-0078.R2).
Source: ADR-0034.R17, ADR-0034.R17.N2

R429. Events and permissions: beyond ADR-0009.R22's document events, `ProductionOrderCompleted` and `ProductionOrderReopened`; reservations emit ADR-0023's events. Record scope for production documents uses `production_warehouse_id` as the warehouse dimension. The shop-floor role template is `shop_floor_lead` (ADR-0054.R11).
Source: ADR-0034.R18

R430. Interfaces and queries: `production.contract` also exposes `plan_production`, `create_production_order_from_plan` and `get_order_inspection_quantities` (ADR-0036.R3, ADR-0036.R8, ADR-0036.R9). Queries:
- `GetProductionOrderStatus`: progress per operation and output; components required, reserved, staged, issued and backflushed; shortages; postings; cost object;
- `ListProductionOrder`, `ListWorkCenterLoad`, `GetTraceability`;
- for the agent: `ListComponentShortage`, `EvaluateProductionOrderRelease`, `GetProductionOrderUsageVariance`, `ListProductionOrderVarianceDriver` (`production`), `GetProductionOrderPegging` and `ListShortageResolutionCandidate` (`planning`);
- the daily job `RunProductionOrderCheck` raises the shortage, completion-candidate, stalled-order and standards items (ADR-0064.R5 to ADR-0064.R12).
Source: ADR-0034.R18, ADR-0034.R18.N1

R431. Locks (ADR-0027.R10): class 1, the shop-floor document, the production order and a make-to-order sales order, as referenced documents; class 3, a share lock on `production_structure` at `Create` and re-explosion; then period state, warehouse tasks, handling units, `stock_value`, `stock_quantity` and bins, then numbering. Two confirmations of one order serialize on the order row.
Source: ADR-0034.R19

R432. Catalog rows reserved in the production range: `INV-103`, `INV-104`, `INV-105`; the edge cases a backflush with too little stock in the supply bin, a milestone over partly confirmed operations, an over-receipt, a change order with partial issues, a posting attempted on a closed order, a rework order from inspection, a disassembly order, as-built serials, a technical completion with open reservations and staged stock, and a reopen; the parallel test PAR-13, two confirmations of one order at once.
Source: ADR-0034.R20

R433. Later than Phase 1, unless the author decides otherwise (open question): finite scheduling inside orders; repetitive manufacturing with period cost collectors; order splitting; co-product planning items. Labor time by clock events is in Phase 1 in a minimal form: time logs that propose confirmation activities, while costing reads only confirmations (ADR-0071.R9 to ADR-0071.R11).
Source: ADR-0034.R21, ADR-0034.R21.N1

### Costing model and collection

R434. Production cost is periodic actual cost, solved exactly per period, extending the period-end costing of ADR-0020.R12 with cost-object nodes (ADR-0025.R6): one solve values stock, transfers, production orders, rework cycles, co-products, WIP by cost component across periods, and the overhead pools production consumes. During the period issues and receipts post at preliminary prices; at period end the job allocates pools, takes out unabsorbed and abnormal cost, moves collected cost into WIP, revalues issues and receipts to actual, and records each order's period cost by component. A released cost estimate per production version is the benchmark for target cost and variance analysis and never values stock unless the author chooses standard cost valuation (ADR-0032.R3). Linearity rests on three restrictions: allocation weights are quantities or constants, never solved values; units in process and completion shares are constants; abnormal cost is assessed when an order completes. Each accounting choice is a regime or company setting with a flagged interim (ADR-0035.R18).
Source: ADR-0035.D0

R435. Collection: material reaches orders through issues. Labor and overhead reach the cost center's pool through their own documents: payroll journals, depreciation, service invoices, and internal `consumption` to a factory cost center. A posting handler fills the pool of the line's cost center when a line on a production cost leaf names a cost center and no cost object; with neither, the line is rejected (`control_dimension_missing`).
Source: ADR-0035.R2

R436. External operations (DS-55) post the service cost directly to the order's `production_cost_other`. The cost components are `material`, `labor`, `overhead` and `other`; each matches a production cost leaf (`production_cost_material`, `production_cost_labor`, `production_cost_overhead`, `production_cost_other`) and a pool group of the same name, and `other` holds external services. The order is the cost object; per-product or per-process views are reports (ADR-0035.R16), which answers part of the DS-41 question on cost collection (open question).
Source: ADR-0035.R2

R437. Lines on accounts with control kind `cost_object` are in area `inventory`, because they are inventory valuation: pool and WIP postings into a period whose inventory area is locked are rejected like any stock posting, and any such posting after the costing job makes the job stale (ADR-0012.R12). Fixed assets and loans stay in `general`.
Source: ADR-0035.R3

R438. Shop-floor documents post at preliminary prices (ADR-0020.R11):
- `production_issue`, `disassembly_issue`: debit `production_cost_material` (order), credit `inventory`; preliminary price, revalued at period end;
- `production_return`: debit `inventory`, credit `production_cost_material` (order); like an issue with the opposite sign, the period's preliminary price revalued to the period's actual; a return in a later period is valued in that period;
- `production_receipt`, `co_product_receipt`, `disassembly_receipt`: debit `inventory`, credit `inventory_work_in_process` (order); preliminary price, revalued at period end;
- `by_product_receipt`: debit `inventory`, credit `inventory_work_in_process` (order); the regime's by-product value, final.
Source: ADR-0035.R4

R439. Confirmations post no journal; their activity quantities drive allocation. Preliminary price of a produced item: ADR-0020.R11's fallback also reads receipts with costing role `production_output`; an item with no history takes the unit cost of the valid released estimate of the version ADR-0033.R13 selects on the posting date for the line's warehouse and quantity (for a production receipt, the order's own version); without one, `preliminary_price_missing`.
Source: ADR-0035.R4, ADR-0035.R14.N1

### The period-end job

R440. The production part runs inside the period-end actual costing job (ADR-0020.R12; sequential, ADR-0012.R16), as one solve per period; that job is the settlement task of ADR-0034.R7. The job writes one internal document per run, `production_cost_settlement`, with lines keyed by (cost object, cost component, step). Reruns post only the differences per key (ADR-0012.R15). The job can be simulated like any command (ADR-0008.R9); its plan lists the journal lines and the period cost records, and the document version follows ADR-0031.R1.
Source: ADR-0035.R5

R441. Registry flags of `production_cost_settlement`: module `production`; posting; internal; no change orders; not e-invoice capable; `is_approval_hold_allowed: false`, because the job writes it as actor `system`; not reversible, because a rerun posts the differences; not item-creating; no demand or supply. Its authorization leaf `production_cost_settlement` sits under Finance beside `costing_adjustment`, and its commands are the job's (`full`, ADR-0054.R8).
Source: ADR-0035.R5.N1

R442. Unknowns and linearity: one price per stock node (item, valuation area). Pool values (constants plus indirect issues at those prices), allocations, order pools, WIP, outputs and abnormal cost are linear forms in those prices; allocation weights, units in process, completion shares and normal capacities are quantities or constants. The system is solved per strongly connected component in topological order, in exact rationals (ADR-0025.R6). A singular component keeps the preliminary prices of its nodes (ADR-0020.R13).
Source: ADR-0035.R6

R443. Pools: each pool's period value is split by account into groups (`labor`, `overhead`, `other`), and each group into variable and fixed parts by the account's `cost_behavior` (ADR-0035.R18). One `pool_allocation_rule` per (cost center, group), company data, says how the group is allocated: by one activity type recorded on the cost center's work centers (actual quantities from confirmations, each counted at its `work_center_id`, the execution work center; time logs never enter the solve), or by a constant basis: output quantity, standard material quantity, or material at preliminary prices (`driver` `activity_type`, `output_quantity`, `standard_material_quantity`, `preliminary_material_amount`).
Source: ADR-0035.R7, ADR-0035.R7.N1

R444. The variable part is allocated in proportion to the driver. The fixed part is allocated at fixed value ÷ max(actual driver quantity, normal capacity); normal capacity (`normal_capacity`) is set per (cost center, activity type or basis, period) in the driver's unit; the unabsorbed rest goes to cost of goods sold (key `production_unabsorbed_overhead`). Without a normal capacity all of it is absorbed, with the close check result `normal_capacity_missing`.
Source: ADR-0035.R7

R445. A pool with no driver quantity in the period goes wholly to cost of goods sold, flagged. A pool group with cost but no `pool_allocation_rule` fails the job with `pool_allocation_rule_missing`. A line on `production_cost_material` whose cost object is a pool is rejected (`material_on_cost_pool`); indirect materials go to `production_cost_overhead`. Allocation lines debit the order and credit the pool on the source line's own account; such mirror lines carry no transaction key (ADR-0015.R5). Pools end the period at zero.
Source: ADR-0035.R7

R446. Order pools, per order and cost component (`material`, `labor`, `overhead`, `other`): pool = opening WIP + the period's incurred cost. Incurred cost is material issued net of returns at actual prices, allocations and external service costs (`other`). A late landed cost reaches the order only through the stock price of its posting period; no consumer-split share lands on the order (ADR-0021.R7.N1, ADR-0025.R8.N1).
Source: ADR-0035.R8

### WIP, abnormal cost and outputs

R447. WIP at period end, for orders that are not technically complete: R = main output received in the period; U = units in process = max(0, E − cumulative main output received), a constant, flagged. E is the smallest, over non-fixed `manual` component lines, of net issued quantity × G ÷ required quantity; backflushed lines follow progress and are left out. When no such line qualifies: if the order has operations and a `backflush_at_operation` component, E = cumulative (yield + scrap) of the order's first operation × G ÷ Q; otherwise (every component `backflush_at_receipt`, no component, or no routing) E = cumulative main output received, so U = 0. This reading of units in process stays flagged for the author with the units-in-process definition (ADR-0035.R18). With no receipt in the period, every component stays WIP.
Source: ADR-0035.R9, ADR-0035.R9.N1

R448. For a `disassembly` order progress is the net input issued: E = the net issued quantity of the header item; D = the smallest, over output lines, of cumulative net received × G ÷ the line's planned quantity; U = max(0, E − D), and R is the period's increase of D.
Source: ADR-0035.R9.N2

R449. WIP methods, chosen by `production.wip_method`, whose interim value the regime package seeds (flagged, ADR-0035.R18) is `direct_material`:
- `direct_material`: material WIP = material pool × U ÷ (R + U); conversion goes wholly to the outputs;
- `equivalent_units`: per component, WIP = pool × U·s ÷ (R + U·s); the share s is 1 for material and, for conversion, the share of routing hours confirmed, or the company's `wip_completion_percent` when set;
- `planned_cost`: WIP = U × the released estimate's cost up to the last confirmed operation, a constant. If the solve gives the order's outputs a negative value, its WIP is capped at its pool and the system is solved again, at most once per order; the order gets the check result `planned_wip_capped` and its outputs are valued at zero, as a degenerate case of ADR-0020.R13.
Source: ADR-0035.R9

R450. Technically complete orders keep no WIP. Abnormal cost is assessed once, at completion, over the whole order: per component line, the excess is the net issued quantity minus required × (cumulative received ÷ G) × (1 + tolerance), floored at 0, valued at the period's actual price and posted to cost of goods sold (key `production_abnormal_cost`). The same applies to activity quantities against standards. A reopen reverses it, and the next completion assesses it again.
Source: ADR-0035.R10

R451. A completed order whose pool is not zero but which received no output in the period sends that cost to cost of goods sold as a residual (key `production_residual_cost`), flagged; so does a completed order with no good output at all, with its whole cost. A residual may be negative: when completion falls in a period without receipts, an abnormal debit can be offset by a negative residual on the same order, earlier outputs keep the abnormal cost, and net cost of goods sold is unchanged. This limitation is flagged (ADR-0035.R18).
Source: ADR-0035.R10

R452. Receipt scrap carries no value and does not change abnormal cost, which reads receipts; the scrap variance (`GetProductionOrderVariance`) counts it with confirmation scrap (ADR-0071.R4).
Source: ADR-0035.R10.N1

R453. Outputs: the value to outputs is the sum of the component pools, minus WIP, minus abnormal cost, minus the by-product value. Co-products share it by `cost_coefficient` × quantity. A negative value (for example a by-product worth more than the order's cost) sends the shortfall to cost of goods sold as a negative residual and the outputs get zero, flagged; like the planned-cost cap, it is applied by solving again, at most once per order. Outputs sum exactly to the value per order, by largest remainder; node residuals follow ADR-0020.R13.
Source: ADR-0035.R11

R454. Postings of the job, in this order: (1) revaluation of issues and returns, against the order's or pool's leaf; (2) pool allocations and unabsorbed fixed cost; (3) abnormal and residual cost; (4) transfer of each order's collected leaves to `inventory_work_in_process` (key `production_wip_transfer`), always, whatever the regime (ADR-0035.R18); (5) revaluation of receipts. The job writes `production_order_period_cost` per order, period and component, with opening, incurred, abnormal, to-output and closing amounts. After the postings each order's WIP balance must equal its closing amounts, otherwise the job fails with `production_cost_not_balanced`.
Source: ADR-0035.R12

### Splits

R455. By-product value: `by_product_receipt` has value source `regime` (ADR-0020.R5). The localization package seeds it as the company's price list of kind `by_product` per item and period (ADR-0045.R2), standing for net realisable value; the seed and its legal basis are flagged package content, `unverified`. A missing price rejects the receipt (`by_product_price_missing`).
Source: ADR-0035.R13

R456. Co-products share by coefficients; `relative_sales_value` from a price list is an option, the list being the default sale list (ADR-0045.R6). Coefficients that sum to zero are rejected when the order is released (`co_product_weights_zero`). Disassembly outputs share by the unit costs in their own released estimates, then by preliminary prices, then by quantity, flagged.
Source: ADR-0035.R13

### Cost estimate

R457. `cost_estimate` has a header (production version, costing date, `state` `draft` or `released`, price basis, `costing_lot_quantity`) and `cost_estimate_line` rows (cost component, component item or activity type, quantity, price, amount, level, `cost_component_detail_id`), rolled up level by level from the released estimates of made components. `costing_lot_quantity` is the quantity the estimate is computed for: fixed quantities and setup are spread over it, and the versions of made components are selected for it; it lies in the version's lot range and defaults to the version's `minimum_lot_quantity`, or one inventory unit when that is zero.
Source: ADR-0035.R14, ADR-0035.R14.N1, ADR-0035.R14.N4

R458. Price basis, defaulted by `production.estimate_price_basis`, whose interim value the regime package seeds (flagged, ADR-0035.R18) is `actual_average`: `actual_average` (the last closed period's actual price), `preliminary_price` or `purchase_price`, the preferred supplier's purchase-list price (ADR-0045.R6). Under `preliminary_price`, a purchased component with no receipt yet is priced at the preliminary price of ADR-0020.R11: the supplier purchase list price (`find_price` in the inventory unit), else the last purchase invoice price, else a manual preliminary price; without any, the estimate returns `preliminary_price_missing` naming it. Made components roll up their released estimates, and their preliminary price stays the produced-item chain (receipts with costing role `production_output`, else the released estimate's unit cost, else `preliminary_price_missing`).
Source: ADR-0035.R14, ADR-0035.R14.N2

R459. Rates: `activity_rate` (work center, activity type, period, rate) holds planned rates. Overhead in an estimate comes from the costing sheet of the production version, else of its site (ADR-0072.R6 to ADR-0072.R9). Surcharge lines of `cost_estimate_line` carry `costing_sheet_row_number` and `credited_cost_center_id`, and only they do; `cost_estimate_sheet_row` keeps the sheet as costed. A missing rate is the gap `costing_rate_missing`, never zero. Administration and selling rows never enter an estimate (ADR-0072.R10).
Source: ADR-0035.R14, ADR-0035.R14.N4

R460. `CreateCostEstimate` computes the estimate on the server; it is effect class `other` and also registered `is_draft_only`, computing on draft revisions, where a draft estimate may have no production version. `ReleaseCostEstimate` freezes it as the version's benchmark; it is effect class `master_data_change`, so it is proposal-bound for agents, because a released estimate feeds the preliminary price. An estimate with a gap or without a version is never released (`cost_estimate_incomplete`).
Source: ADR-0035.R14, ADR-0035.R14.N3, ADR-0035.R14.N5

R461. An estimate for a configured item names the item (`item_id`) with the product-level version, and is computed and released by the system when the item is created (ADR-0046.R11, ADR-0046.R14).
Source: ADR-0035.R14

R462. The estimate valid for a version on a date is the latest released one, by costing date and then release time, whose costing date is on or before that date; target cost (ADR-0035.R15) and the order's `policy_input` use it.
Source: ADR-0035.R14.N1

R463. What a draft estimate cannot price (a missing purchase price, activity rate or activity quantity, a pending item, an unstated setup or run time, a missing routing) is a `cost_estimate_gap` row, left out of the total and never zero. `previous_cost_estimate_id` names the estimate a delta compares with (ADR-0062.R12).
Source: ADR-0035.R14.N3

## Invariants

| ID | Name | Check point | Statement | Protects |
| --- | --- | --- | --- | --- |
| `INV-103` | `production_lines_carry_cost_object` | day | Every material line of a production document carries its order's `cost_object_id`. | R419, R432 |
| `INV-104` | `receipts_within_tolerance` | day | Per production order other than disassembly, cumulative net receipts of the main output never exceed G × (1 + `overdelivery_tolerance_percent` / 100). | R414, R432 |
| `INV-105` | `as_built_serial_assigned` | day | Every `output_serial_number_id` on a production issue line is a serial assigned to an output of the same order. | R422, R432 |

## Settings

None: no setting row belongs to this chunk. `production.mes_import.auto_post` (R409) has its row in the chunk of ADR-0064.R25. The company value `wip_completion_percent` named by R449 is absent from `settings.csv`.

## Conflicts

CONFLICT ADR-0034.R12: later notes govern the confirmation; one table `operation_progress_component` holds generated lines (ADR-0034.R12.N1), execution work center, time-only confirmations and `operation_time_log_open` (ADR-0034.R12.N4); stated in R401-R407.
CONFLICT ADR-0034.R12.N1: supersedes the separate `operation_confirmation_component` and `production_receipt_component` tables of ADR-0034.R12 and ADR-0034.R13; R407 and R415 state the one table.
CONFLICT ADR-0034.R12.N5: `scrap_reason_id` of kind `scrap` replaces the text scrap reason code of confirmations and receipts per ADR-0074.R14; R401 states the reason column.
CONFLICT ADR-0034.R13: notes amend the receipt; backflush at receipt writes `operation_progress_component` (ADR-0034.R13.N1), output bin of the execution work center and receipt scrap (ADR-0034.R13.N4); stated in R411, R415, R416.
CONFLICT ADR-0034.R17: the later note ADR-0034.R17.N2 makes the production and capture agents designed agent types instead of later agents, and ADR-0078.R2 puts them in Phase 2; R428 states it.
CONFLICT ADR-0034.R12.N3: ADR-0078.R2 makes the capture agent `production_capture` a Phase 2 agent type with mode `off` (R409).
CONFLICT ADR-0035.R8: ADR-0021.R7.N1 and ADR-0025.R8.N1 supersede the landed cost consumer split; no consumer-split share enters an order pool (R446).
CONFLICT ADR-0034.R21: labor time by clock events moved into Phase 1 in minimal form by ADR-0034.R21.N1 (ADR-0071); R433 drops it from the later list.
CONFLICT ADR-0035.R9.N1: replaces the old fallback of units in process when no manual line qualifies; R447 states the new fallback and keeps the author flag.
CONFLICT ADR-0035.R14: release of an estimate is effect class `master_data_change` by ADR-0035.R14.N5, no longer `other`; R460 states both command classes.
CONFLICT ADR-0035.R14.N4: overhead in an estimate comes from the costing sheet of ADR-0072, which replaces the planned surcharge per cost center; R459 states it.

## Trace

| Source | Where |
| --- | --- |
| ADR-0034.R12 | R401, R402, R404, R405, R406, R407, R408, R409 |
| ADR-0034.R12.N1 | R407 |
| ADR-0034.R12.N2 | R406 |
| ADR-0034.R12.N3 | R401, R409 |
| ADR-0034.R12.N4 | R401, R402, R403 |
| ADR-0034.R12.N5 | R401 |
| ADR-0034.R13 | R410, R411, R412, R413, R414, R415, R417 |
| ADR-0034.R13.N1 | R415 |
| ADR-0034.R13.N2 | R410, R414 |
| ADR-0034.R13.N3 | R412 |
| ADR-0034.R13.N4 | R411, R415, R416 |
| ADR-0034.R14 | R418 |
| ADR-0034.R15 | R419, R420 |
| ADR-0034.R16 | R422, R423, R424, R425 |
| ADR-0034.R17 | R426, R428 |
| ADR-0034.R17.N1 | R427 |
| ADR-0034.R17.N2 | R428 |
| ADR-0034.R18 | R429, R430 |
| ADR-0034.R18.N1 | R430 |
| ADR-0034.R19 | R431 |
| ADR-0034.R20 | R432 |
| ADR-0034.R21 | R433 |
| ADR-0034.R21.N1 | R433 |
| ADR-0035.D0 | R434 |
| ADR-0035.R1 | R419 |
| ADR-0035.R1.N1 | R421 |
| ADR-0035.R2 | R435, R436 |
| ADR-0035.R3 | R437 |
| ADR-0035.R4 | R438, R439 |
| ADR-0035.R5 | R440 |
| ADR-0035.R5.N1 | R441 |
| ADR-0035.R6 | R442 |
| ADR-0035.R7 | R443, R444, R445 |
| ADR-0035.R7.N1 | R443 |
| ADR-0035.R8 | R446 |
| ADR-0035.R9 | R447, R449 |
| ADR-0035.R9.N1 | R447 |
| ADR-0035.R9.N2 | R448 |
| ADR-0035.R10 | R450, R451 |
| ADR-0035.R10.N1 | R452 |
| ADR-0035.R11 | R453 |
| ADR-0035.R12 | R454 |
| ADR-0035.R13 | R455, R456 |
| ADR-0035.R14 | R457, R458, R459, R460, R461 |
| ADR-0035.R14.N1 | R439, R457, R462 |
| ADR-0035.R14.N2 | R458 |
| ADR-0035.R14.N3 | R460, R463 |
| ADR-0035.R14.N4 | R457, R459 |
| ADR-0035.R14.N5 | R460 |
