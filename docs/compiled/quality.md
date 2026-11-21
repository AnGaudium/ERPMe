Module: quality    Chunk: whole    Source ADRs: ADR-0070, ADR-0027, ADR-0043, ADR-0075
Build step(s): 5    Generated from index: 30d5706    Compiled by: Claude Fable 5.2, 2026-11-21

# Compiled spec: quality

## Purpose

`quality` owns inspection plans, sampling procedures, defect codes, inspection lots, inspection results, usage decisions
and nonconformances. It is a layer-4 module (ADR-0022.R2) that nobody imports: it learns about stock through the posting
events of `inventory` and `production`, and changes stock only by dispatching their existing commands. The inspection lot
is a non-posting document that claims held stock by its key and adds no column to the stock key. People decide by default:
agents and supplier certificates only draft results, and auto-acceptance is off until the company turns it on. It owns no
stock, no stock document and no second workflow engine: containment and corrective actions are work items in an ADR-0066
work case.

## Entities and tables

DDL: `docs/design/DS-58-quality.sql`. The module owns <!-- count:tables -->10<!-- /count --> tables and the document type
`inspection_lot`. Every table has the key `id` and is unique on (`company_id`, `id`).

| Table | Meaning | Key | Parent | Owner |
| --- | --- | --- | --- | --- |
| `sampling_procedure` | How the sample quantity of a lot is computed | `id`; unique (`company_id`, `code`) | company | `quality` |
| `defect_code` | Company list of defects with a severity | `id`; unique (`company_id`, `code`) | company | `quality` |
| `inspection_plan` | Selects a plan by item or item group, point, site and operation | `id`; unique (`company_id`, `code`) and the selection tuple | company | `quality` |
| `inspection_plan_revision` | Dated revision of a plan, immutable once released | `id`; unique (`inspection_plan_id`, `revision`) | `inspection_plan` | `quality` |
| `inspection_characteristic` | Line of a revision: what is measured or judged | `id`; unique (`inspection_plan_revision_id`, `position`) and (`inspection_plan_revision_id`, `code`) | `inspection_plan_revision` | `quality` |
| `inspection_lot` | Non-posting document: held stock or progress, sample, outcome | `id`, the `document` ID | `document` | `quality` |
| `inspection_lot_line` | Usage decision line: disposition and quantity | `id`; unique (`inspection_lot_id`, `line_number`) | `inspection_lot` | `quality` |
| `inspection_lot_execution` | Task or draft created for a decision line, and its state | `id`; unique (`target_table`, `target_id`) | `inspection_lot_line` | `quality` |
| `inspection_result` | Append-only result of a characteristic of a lot | `id` | `inspection_lot` | `quality` |
| `nonconformance` | Company-data record of a defect and its actions | `id` | company | `quality` |

Reads: `product` (`inspection_points`), `item`, `item_group`, `site`, `warehouse`, `partner`, `lot`, `serial_number`, `uom`,
`reason` (`master_data`); `document` (`documents`); `stock_quantity`, `stock_value`, `warehouse_task`, `return_to_supplier`,
`return_to_supplier_line`, `scrap`, `scrap_line`, `internal_consumption`, `internal_consumption_line` (`inventory`);
`production_order` (`production`); `document_extraction`, `extraction_result_link` (`attachments`); `agent_run`
(`agents`); `user_account`, `company`.

## Commands and queries

Every command is `other` unless the row says otherwise, and none posts (R87). "None named" means the sources name no
event or error code for the row.

| Name | Actor and authorization | Input | Effect | Events | Errors |
| --- | --- | --- | --- | --- | --- |
| `CreateSamplingProcedure`, `UpdateSamplingProcedure`, `CreateDefectCode`, `UpdateDefectCode`, `UpdateInspectionPlan` | `inspection_plan` at `edit`; `master_data_change` | the row's columns | writes company data | none named | none named |
| `CreateInspectionPlan`, `CreateInspectionPlanRevision`, `UpdateInspectionPlanRevision` | `inspection_plan` at `edit`; `is_draft_only` | plan header, or a draft revision with its characteristics | writes a plan or its draft revision | none named | none named |
| `ReleaseInspectionPlanRevision` | `inspection_plan` at `post`; `master_data_change` | the draft revision; for an agent's draft a change proposal with `expected_version` | releases the revision | `InspectionPlanRevisionReleased` | check result `inspection_point_not_on_item` |
| `CreateInspectionLot` | `inspection_lot` at `edit`; `inspection_lot_creator` as `system`, or a person | header of R29 | creates a draft lot, raises `inspection_lot_open` | document events (ADR-0009.R22) | none named |
| `UpdateInspectionLot` | `inspection_lot` at `edit`; on no agent tool list | outcome, `deviation_reason`, lines | writes the usage decision | document events (ADR-0009.R22) | none named |
| `CancelInspectionLot` | `inspection_lot` at `edit`; `inspection_lot_creator` as `system`, or a person | the lot | cancels a draft lot | document events (ADR-0009.R22) | none named |
| `SubmitInspectionLot` | `usage_decision` at `post`; policy point | the lot | puts the decision in force or sends it to approval | document events (ADR-0009.R22), among them `InspectionLotApproved` | `inspection_result_unconfirmed`, `inspection_results_incomplete`, `inspection_stock_short`, `segregation_of_duties` |
| `ApproveInspectionLot`, `RejectInspectionLot` | approval flag, pool `quality` (ADR-0055) | the lot | approves or rejects the decision | document events (ADR-0009.R22), among them `InspectionLotApproved` | none named |
| `RecordInspectionLotExecution` | `inspection_lot` at `post`; consumers of `quality` as `system` only | line, state, target table and ID, done quantity | writes an `inspection_lot_execution` row or its state | `InspectionLotExecutionRecorded` | none named |
| `CloseInspectionLot` | `inspection_lot` at `post`; consumers of `quality` as `system` only | the lot | closes the lot | document events (ADR-0009.R22) | none named |
| `RecordInspectionResult` | `inspection_lot` at `post`; a person, an integration actor, an agent, or `certificate_result_drafter` as `system` | list of results for one lot in `draft` | appends `inspection_result` rows | `InspectionResultRecorded` | `characteristic_not_in_plan`, `result_code_not_allowed` |
| `ConfirmInspectionResult` | `inspection_lot` at `post`; `human_only` | a draft result | sets `confirmed_by_user_id` and `confirmed_at` once | `InspectionResultConfirmed` | none named |
| `CreateNonconformance` | `nonconformance` at `edit`; `usage_decision_executor` or a person | columns of R81 | creates the record, raises `nonconformance_open` | `NonconformanceCreated` | none named |
| `UpdateNonconformance` | `nonconformance` at `edit` | columns of R81 | updates; raises `nonconformance_action` for a named action owner | `NonconformanceUpdated` | none named |
| `CloseNonconformance` | `nonconformance` at `post` | close note | closes, resolves `nonconformance_open` | `NonconformanceClosed` | none named |
| `CancelNonconformance` | `nonconformance` at `edit` | reason | cancels, resolves `nonconformance_open` | `NonconformanceCanceled` | none named |
| `GetInspectionLot` (query) | none named | the lot | results in force per characteristic and unit, the decision, executions | none | none named |
| `ListInspectionLot`, `ListInspectionPlan`, `ListNonconformance` (queries) | none named | none named | list | none | none named |
| `ListUninspectedStock` (query) | none named | none named | stock in `quality_inspection` that no open lot claims | none | none named |
| `ListSupplierQualityRate` (query) | none named | supplier and period | lots, inspected and rejected quantities, reject rate | none | none named |

The sources name no returning command for `usage_decision_quantity_mismatch` (R58) and `disposition_not_allowed` (R59);
both are checks on the decision content.

## Rules

### Module and dependencies

R1. `quality` is a layer-4 module (ADR-0022.R2) that owns the tables of `docs/design/DS-58-quality.sql` and the document
type `inspection_lot`.
Source: ADR-0070.R1

R2. `quality` imports the contracts of `inventory`, `production` and `master_data` (layer 3) and of `documents`, `work`,
`attachments` and `policy` (layer 2); it imports no layer-4 peer.
Source: ADR-0070.R1

R3. `inventory`, `purchasing`, `production`, `sales` and `crm` never import `quality`; an import-linter contract enforces
this.
Source: ADR-0070.R1

R4. The supplier and the order line of a receipt are read from `inventory`'s goods receipt, and a return to the supplier
is `inventory`'s `return_to_supplier` (ADR-0047.R15), so `quality` does not need `purchasing`.
Source: ADR-0070.R1

R5. `quality` changes stock or production data only through commands that its consumers dispatch through `registry`
(ADR-0013.R9); it calls no write function of another module.
Source: ADR-0070.R1

R6. `quality` is not part of the CRM-only deployment profile; `crm` refers to nothing in it, and a nonconformance may name
a complaint by its ID only.
Source: ADR-0070.R1

### Inspection points

R7. Inspection points are a closed set: `goods_receipt`, `in_process` (after a routing operation), `production_output`,
`customer_return` and `stock_recheck`.
Source: ADR-0070.R2

R8. `product.inspection_points` (`text[]`, default empty, a subset of the set) says per point whether the item is
inspected; it stands in place of the boolean `is_inspection_required` (ADR-0023.R3), and `master_data.contract` exposes it.
Source: ADR-0070.R2

R9. `inventory` posts `purchase_receipt` and `other_receipt` lines to `quality_inspection` when the set contains
`goods_receipt` (ADR-0023.R7); `production` posts output to `quality_inspection` when it contains `production_output`
(ADR-0034.R13); returns arrive `blocked` (ADR-0023.R19).
Source: ADR-0070.R2

R10. The lot creator of `quality` reads `product.inspection_points` for every point.
Source: ADR-0070.R2

R11. The upgrade sets the array to `{goods_receipt, production_output}` where `is_inspection_required` was true.
Source: ADR-0070.R2

### Master data

R12. `sampling_procedure` is company data changed by `master_data_change`; it holds `code`, `name`, `kind` and its
parameter, and `is_active`.
Source: ADR-0070.R3

R13. The sampling kinds are `fixed_quantity` (n, capped at the lot quantity), `percent` (rounded up to a whole inventory
unit, at least 1) and `full` (the whole lot).
Source: ADR-0070.R3

R14. The sample quantity is computed once, when the lot is created, and stored on the lot.
Source: ADR-0070.R3

R15. `defect_code` is company data changed by `master_data_change`, with `code`, `name`, `severity` (`critical`, `major`,
`minor`) and `is_active`; it has no core seed, and results and nonconformances may name one.
Source: ADR-0070.R6

R16. `inspection_plan` holds `code`, `name`, exactly one of `item_id` and `item_group_id`, `inspection_point`, an optional
`site_id` (ADR-0068) and, for `in_process` plans of an item, an optional `operation_number`; the tuple is unique.
Source: ADR-0070.R4

R17. For a lot, the first plan that matches wins, in this order: item and site, item, item group and site, item group;
the site is that of the lot's warehouse.
Source: ADR-0070.R4

R18. For `in_process`, the plan must name the confirmation's `operation_number` or have no `operation_number` (it then
applies to every operation); a plan with the exact operation wins over one without.
Source: ADR-0070.R4

R19. Within the selected plan, the revision used is the highest released one with `start_date` on or before the lot's
business date.
Source: ADR-0070.R4

R20. `inspection_plan_revision` holds `revision`, `state` (`draft` or `released`), `start_date`, `sampling_procedure_id`,
`is_auto_accept_allowed`, `is_sample_destroyed`, `content_hash` and `released_at`.
Source: ADR-0070.R4

R21. A released revision and its characteristics are immutable, by trigger, as in ADR-0033.R3 and ADR-0033.R4; a plan has
at most one draft.
Source: ADR-0070.R4

R22. The draft commands of a plan are `other` and `is_draft_only`; `ReleaseInspectionPlanRevision` is
`master_data_change`, so an agent's draft is released only through a change proposal whose `expected_version` is the
draft's `content_hash` (ADR-0033.R2; ADR-0029.R5).
Source: ADR-0070.R4

R23. Releasing a plan for a point that the item's product lacks gives the check result `inspection_point_not_on_item`.
Source: ADR-0070.R4

R24. `inspection_characteristic` is a line of a revision with `position`, `code`, `name`, `kind`, `is_required` and
`is_recorded_per_unit`.
Source: ADR-0070.R5

R25. A `quantitative` characteristic has `uom_id`, an optional `target_value`, and `lower_limit` and/or `upper_limit`
(`types.quantity`, limits inclusive).
Source: ADR-0070.R5

R26. A `qualitative` characteristic has `allowed_result_codes` and `passing_result_codes` (a non-empty subset).
Source: ADR-0070.R5

R27. A characteristic recorded per unit needs a result for each sample unit, 1 to the lot's sample quantity; any other
characteristic needs one summary result.
Source: ADR-0070.R5

### The inspection lot

R28. `inspection_lot` is a non-posting document type (ADR-0009.R6) owned by `quality`, with the registry flags
`is_approval_hold_allowed: true` and `is_reversible: false`.
Source: ADR-0070.R7

R29. The lot header holds: `inspection_point`, `item_id`, `warehouse_id`, and `lot_id` or `serial_number_id` where
tracked; `held_stock_status` (`quality_inspection` or `blocked`, null for `in_process`); `quantity` (inventory unit) and
`sample_quantity`; `inspection_plan_revision_id` (null when no plan matched); `source_document_id` and
`source_line_number` (the posting document and its line), `partner_id` (the supplier or customer), and
`production_order_id` and `operation_number` for `in_process`; `outcome` and `deviation_reason`.
Source: ADR-0070.R7

R30. Record scope of a lot uses `warehouse_id` (ADR-0017.R9).
Source: ADR-0070.R7

R31. A lot is identified by its document barcode (ADR-0061) until it is numbered.
Source: ADR-0070.R7

### Lot creation

R32. The transactional consumer `inspection_lot_creator` (queue `events`) handles `GoodsReceiptPosted`,
`OtherReceiptPosted`, `ProductionReceiptPosted`, `ReturnFromCustomerPosted` and `OperationConfirmationPosted`, and reads
the posted lines through the owners' contracts.
Source: ADR-0070.R8

R33. The creator runs `CreateInspectionLot` as `system`, with the command key
`inspection_lot_creator:<event id>:<line number>`, for each line whose product's `inspection_points` contains the point
and, except at `in_process`, whose stock was posted in `quality_inspection` or, for returns, `blocked`.
Source: ADR-0070.R8

R34. At `in_process`, a lot is created only when R17 to R19 select a released plan for that item and operation; its
quantity is the confirmation's yield, and no lot is created for a confirmation whose yield is 0 (time-only or scrap-only
confirmations, ADR-0071.R2), because the lot quantity must be above 0.
Source: ADR-0070.R8

R35. Each created lot raises `inspection_lot_open` (owner `role:quality_inspector`).
Source: ADR-0070.R8

R36. A lot without a matching plan is created anyway, with no characteristics, and a person decides it.
Source: ADR-0070.R8

R37. On `ProductionReceiptReversed` and `OperationConfirmationReversed` the creator cancels the source's draft lots
(`CancelInspectionLot` as `system`); a lot already decided raises `usage_decision_execution_failed`.
Source: ADR-0070.R8

R38. A person runs `CreateInspectionLot`, the only way to create a `stock_recheck` lot, for stock already in
`quality_inspection` or `blocked`; to recheck available stock, the client sends a command batch (ADR-0008.R20):
`CreateWarehouseTask` (`status_change` to `quality_inspection`), then `CreateInspectionLot`.
Source: ADR-0070.R8

### The stock link

R39. A lot claims the stock of its key (item, warehouse, lot or serial, `held_stock_status`) over all bins and handling
units; `stock_quantity` has no `inspection_lot_id`.
Source: ADR-0070.R9

R40. `SubmitInspectionLot` checks, under the `stock_value` lock of (item, warehouse) taken through `inventory.contract`
(ADR-0023.R10), that the key's stock in the held status covers the lines that move stock, after the not-yet-executed
quantities of other approved lots of the key; otherwise it returns `inspection_stock_short`.
Source: ADR-0070.R9

R41. `ListUninspectedStock` lists stock in `quality_inspection` that no open lot claims, for example after a manual
status change, so a person can create a lot for it.
Source: ADR-0070.R9

### Results

R42. `inspection_result` is append-only.
Source: ADR-0070.R10

R43. `RecordInspectionResult` takes a list of results for one lot in `draft`; each holds the characteristic (from the
lot's revision, otherwise `characteristic_not_in_plan`), an optional `sample_number` and `serial_number_id`, a `value`
(quantitative) or a `result_code` (qualitative, from the allowed codes, otherwise `result_code_not_allowed`), and an
optional `defect_code_id` and note.
Source: ADR-0070.R10

R44. The handler computes `is_passed` from the immutable revision and stores it.
Source: ADR-0070.R10

R45. A correction is a new row with `supersedes_result_id`; the result in force is the one nobody supersedes.
Source: ADR-0070.R10

R46. `entry_source` is `person`, `integration` (a measuring device or LIMS through an integration actor), `certificate`
or `agent`; rows of a person or an integration are confirmed when written, and `certificate` and `agent` rows are drafts
until `ConfirmInspectionResult` (`human_only`) sets `confirmed_by_user_id` and `confirmed_at` once.
Source: ADR-0070.R10

R47. Photos and certificates are attachments (ADR-0038.R14) linked to the lot.
Source: ADR-0070.R10

R48. Result values are typed numbers (`types.quantity`); `test_equipment_id` is reserved and stays null until calibration
exists.
Source: ADR-0070.R10

### Supplier certificates

R49. The document intake purpose `certificate_of_analysis` (ADR-0057; leaf `inspection_lot`, consumer `quality`) reads the
supplier lot code, the item code (type `code`) and, per `lines[n]`, the characteristic (type `code`, resolved to a
characteristic code of the plan through the partner's mapping rules, ADR-0057.R24), the value (`quantity`), the unit
(`unit`) and the stated pass or fail (`text`, untrusted).
Source: ADR-0070.R11

R50. The consumer `certificate_result_drafter` handles `DocumentExtractionRecorded` and `DocumentExtractionVerified` for
this purpose and matches the extraction's partner, item and lot code to exactly one open lot; otherwise it raises
`certificate_unmatched`.
Source: ADR-0070.R11

R51. On a match the drafter runs `RecordInspectionResult` as `system` with `entry_source` `certificate`,
`document_extraction_id` and the field IDs, and links the result rows in `extraction_result_link`.
Source: ADR-0070.R11

R52. Every certificate row is an unconfirmed draft, whatever the extraction's trust, so a supplier's document never
decides a lot by itself (ADR-0029.R10 to ADR-0029.R12; ADR-0013.R11); values that are trusted (ADR-0057.R17) are shown as
such on the confirmation screen.
Source: ADR-0070.R11

R53. The certificate path adds no agent type: its only model is the existing vision step `document_reader`, where its
seat is enabled, and matching and drafting are code.
Source: ADR-0070.R11

### The usage decision

R54. The usage decision is lot content written by `UpdateInspectionLot`, which is on no agent tool list in Phase 1; the
auto-drafter of R68 runs it as `system`.
Source: ADR-0070.R12

R55. The outcome is `accepted` (every required characteristic passed), `accepted_with_deviation` (released despite a
failure or a missing plan, with a required `deviation_reason`) or `rejected` (any quantity is not released).
Source: ADR-0070.R12

R56. A line (`inspection_lot_line`) holds `disposition`, `quantity`, an optional `serial_number_id` and, for the
dispositions `scrap` (reason kind `scrap`) and `return_to_supplier` (reason kind `return`) only, a `reason_id`.
Source: ADR-0070.R12

R57. The line's reason is required while the matching setting `documents.reason_required.scrap` or
`documents.reason_required.return` is true (ADR-0074.R22), so the executor's drafts are not refused with
`reason_required`.
Source: ADR-0070.R12

R58. Lines exist only for lots that hold stock, and their quantities sum to the lot quantity
(`usage_decision_quantity_mismatch`).
Source: ADR-0070.R12

R59. Each disposition is allowed at the points and carried out by the executor (R71) as listed; any other combination
returns `disposition_not_allowed`:
- `release`: every stock-holding point; `CreateWarehouseTask`, `status_change` to `available`.
- `block`: every stock-holding point; `status_change` to `blocked`, none when already blocked.
- `return_to_supplier`: `goods_receipt`; draft `return_to_supplier` against the receipt line.
- `scrap`: every stock-holding point; draft `scrap`.
- `rework`: `production_output`, `customer_return`, `stock_recheck`, for produced items; draft `production_order` of type
  `rework`, issuing from `quality_inspection`, after a status change from `blocked` where held so (ADR-0034.R4,
  ADR-0034.R11).
- `sample_consumption`: every stock-holding point, at most `sample_quantity`; draft `internal_consumption` with movement
  type `quality_sample`.
Source: ADR-0070.R12

R60. The outcome `accepted` allows only the dispositions `release` and `sample_consumption`.
Source: ADR-0070.R12

R61. At `Submit`, every result in force is confirmed (`inspection_result_unconfirmed`), `accepted` needs a passing result
in force for every required characteristic and unit (`inspection_results_incomplete`), and the stock check of R40 runs.
Source: ADR-0070.R12

### Who decides

R62. `SubmitInspectionLot` needs the leaf `usage_decision` at `post`, a declared minimum above the verb's (ADR-0054.R8);
recording results needs `inspection_lot` at `post`.
Source: ADR-0070.R13

R63. The policy input of the lot (ADR-0043.R4) is the outcome, the item and its group, the partner, the point, and as
amount the held quantity at the preliminary price in company currency, with the flags `is_all_passed` and
`is_quality_deviation` (`accepted_with_deviation`).
Source: ADR-0070.R13

R64. The core seeds the policy rule `quality.deviation` (ADR-0043.R15): at `submit` of `inspection_lot`, actor `human`,
`require_approval` with `standard` when `is_quality_deviation`; companies add rules as usual.
Source: ADR-0070.R13

R65. While the setting `quality.usage_decision.separate_from_results` (company, boolean, default false, `true_tighter`)
is true, a person who recorded or confirmed a result in force of the lot cannot submit its decision
(`segregation_of_duties`).
Source: ADR-0070.R13

R66. `ApproveInspectionLot` and `RejectInspectionLot` follow ADR-0055; the approval pool is `quality`.
Source: ADR-0070.R13

### Auto-acceptance

R67. Auto-acceptance is off by default and needs all of: the setting `quality.usage_decision.auto_accept` (company, boolean,
default false, `false_tighter`) true (turning it on is a loosening, ADR-0063.R3); the plan revision's `is_auto_accept_allowed`; and an `allow` policy rule for actor
`system` at `submit` of `inspection_lot` with `is_all_passed`, without which ADR-0043.R9 floor 8 gives the lowest rank,
so a person still approves.
Source: ADR-0070.R14

R68. The consumer `usage_decision_auto_drafter` handles `InspectionResultRecorded` and `InspectionResultConfirmed` whose
payload says the lot is complete and all passed; when the setting and the plan flag hold and the lot is a draft without
an outcome, it runs a batch as `system`: `UpdateInspectionLot` (`accepted`; `release` for the quantity, and
`sample_consumption` for the sample when `is_sample_destroyed`), then `SubmitInspectionLot`.
Source: ADR-0070.R14

R69. An unconfirmed result, a lot without a plan, and any failure stop the auto-drafter.
Source: ADR-0070.R14

R70. No preset may seed the `allow` rule for `system` (ADR-0067.R3).
Source: ADR-0070.R14

### Execution of the decision

R71. The consumer `usage_decision_executor` handles `InspectionLotApproved` (an approval or a direct `Submit`); per line,
in one batch as `system` on behalf of the decider, it dispatches the owner's create command of R59 with a client ID, then
`RecordInspectionLotExecution` (`created`, the target table and ID).
Source: ADR-0070.R15

R72. For `scrap` and `return_to_supplier` the executor copies the line's `reason_id` to the draft it creates.
Source: ADR-0070.R15

R73. For status changes the executor reads the key's held stock by bin through `inventory.contract` and creates one task
per bin and handling unit, in bin code order.
Source: ADR-0070.R15

R74. The executor never posts: a warehouse keeper confirms tasks and posts the drafts, and a planner releases the rework
order, under their own permissions and policy.
Source: ADR-0070.R15

R75. Destroyed samples are issued by `internal_consumption_line` rows with `consumption_kind` `quality_sample`, which
post the movement type `quality_sample` (offset `consumption`, SAP 331).
Source: ADR-0070.R15, ADR-0070.R15.N1

R76. Issuing lines name the held status: `return_to_supplier_line`, `scrap_line` and `internal_consumption_line` carry
`stock_status` (ADR-0023.R7; ADR-0075.R4, ADR-0075.R5), and `inspection_lot_execution.target_table` names the `scrap` and
`internal_consumption` rows.
Source: ADR-0070.R15, ADR-0070.R15.N1

R77. The consumer `usage_decision_tracker` handles `WarehouseTaskConfirmed`, `WarehouseTaskCanceled`, the `Posted` and
`Canceled` events of the draft `return_to_supplier`, `scrap` and `internal_consumption` documents, and
`ProductionOrderApproved` and `ProductionOrderCanceled`; it records `done` (with the done quantity) or `canceled` through
`RecordInspectionLotExecution`.
Source: ADR-0070.R15

R78. A short or canceled execution raises `usage_decision_execution_failed` (owner `role:warehouse_keeper`).
Source: ADR-0070.R15

R79. When every line is done the tracker runs `CloseInspectionLot`; a line whose disposition needs no execution (for
example `block` on stock already blocked) counts as done, so `CloseInspectionLot` runs at once when no line has an
execution row.
Source: ADR-0070.R15

R80. Released make-to-order output reaches its sales demand through ADR-0034.R14's consumer of `WarehouseTaskConfirmed`.
Source: ADR-0070.R15

### Nonconformance

R81. `nonconformance` is company data, not a document type (like `complaint`, ADR-0052.R20), with `kind` (`supplier`,
`internal`, `customer`), `state` (`open`, `closed`, `canceled`), `defect_code_id`, item, lot or serial, `quantity`,
`partner_id`, `inspection_lot_id`, the source (`source_table` and `source_id`: a document or a complaint), `description`,
`root_cause`, the containment and corrective actions (text, owner user and due date each), `opened_at`, `closed_at`,
`close_note` and `version`.
Source: ADR-0070.R16

R82. The executor creates a nonconformance with `CreateNonconformance` for every `rejected` lot: `supplier` at
`goods_receipt`, `customer` at `customer_return`, otherwise `internal`; people create the others, for a deviation or a
complaint.
Source: ADR-0070.R16

R83. Creating a nonconformance raises `nonconformance_open`, the trigger of the work case kind `nonconformance`
(ADR-0066.R3).
Source: ADR-0070.R16

R84. Naming an action owner in `UpdateNonconformance` raises `nonconformance_action` for that owner (owner and due
`named_by_raiser`; open key: the nonconformance and the action kind) in the nonconformance's open case; containment and
corrective actions are work items in a case, not a second workflow engine.
Source: ADR-0070.R16

R85. `CloseNonconformance` takes a close note and `CancelNonconformance` takes a reason; each resolves
`nonconformance_open`.
Source: ADR-0070.R16

R86. `ListSupplierQualityRate` gives, per supplier and period, lots, inspected and rejected quantities and the reject
rate; it is the only scorecard in Phase 1.
Source: ADR-0070.R16

### Commands, events, queries and roles

R87. Every command of `quality` is `other` unless R88 says `master_data_change`, and none posts.
Source: ADR-0070.R17

R88. `CreateSamplingProcedure`, `UpdateSamplingProcedure`, `CreateDefectCode`, `UpdateDefectCode` and
`UpdateInspectionPlan` need `inspection_plan` at `edit` and are `master_data_change`; `CreateInspectionPlan`,
`CreateInspectionPlanRevision` and `UpdateInspectionPlanRevision` need `inspection_plan` at `edit` and are
`is_draft_only`; `ReleaseInspectionPlanRevision` needs `inspection_plan` at `post` and is `master_data_change`.
Source: ADR-0070.R17

R89. `CreateInspectionLot`, `UpdateInspectionLot` and `CancelInspectionLot` are generated document verbs that need
`inspection_lot` at `edit`; `SubmitInspectionLot` needs `usage_decision` at `post` and is the policy point (R62 to R65);
`ApproveInspectionLot` and `RejectInspectionLot` need the approval flag (ADR-0055).
Source: ADR-0070.R17

R90. `CloseInspectionLot` and `RecordInspectionLotExecution` need `inspection_lot` at `post` and are run by `quality`'s
consumers as `system` only.
Source: ADR-0070.R17

R91. `RecordInspectionResult` and `ConfirmInspectionResult` need `inspection_lot` at `post`; `ConfirmInspectionResult` is
`human_only`.
Source: ADR-0070.R17

R92. `CreateNonconformance`, `UpdateNonconformance` and `CancelNonconformance` need `nonconformance` at `edit`;
`CloseNonconformance` needs it at `post`.
Source: ADR-0070.R17

R93. The events of `quality` are the document events of `inspection_lot` (ADR-0009.R22), `InspectionPlanRevisionReleased`,
`InspectionResultRecorded` and `InspectionResultConfirmed` (with `is_lot_complete` and `is_all_passed`),
`InspectionLotExecutionRecorded`, and `NonconformanceCreated`, `NonconformanceUpdated`, `NonconformanceClosed` and
`NonconformanceCanceled`.
Source: ADR-0070.R18

R94. The consumers `inspection_lot_creator`, `certificate_result_drafter`, `usage_decision_auto_drafter`,
`usage_decision_executor` and `usage_decision_tracker` are `quality`'s and are registered paused (ADR-0013.R6).
Source: ADR-0070.R18

R95. The queries are `GetInspectionLot` (results in force per characteristic and unit, the decision, executions),
`ListInspectionLot`, `ListInspectionPlan`, `ListUninspectedStock`, `ListNonconformance` and `ListSupplierQualityRate`.
Source: ADR-0070.R19

R96. A print subject for the lot and its results serves inspection sheets (ADR-0049.R25).
Source: ADR-0070.R19

R97. The role template `quality_inspector` is the module's; besides it, `shop_floor_lead` holds `inspection_lot` at
`post`, because the shop-floor lead records and confirms in-process results at the work center, and `warehouse_keeper`
and `production_planner` hold `read`, to see held stock.
Source: ADR-0070.R20

### Not in Phase 1

R98. Phase 1 leaves out, each with its seam: SPC and control charts (they read the typed values); ISO 2859 dynamic
sampling and skip-lot (the values `iso_2859` and `skip_lot` of `sampling_procedure.kind`, with their own parameter
columns); test-equipment calibration (it fills `inspection_result.test_equipment_id`); full CAPA and 8D, audits and
supplier scorecards beyond the reject rate (they grow on work cases and `nonconformance`); outgoing certificates of
analysis (a print template over structured results); quality costs (they read `quality_sample`, scrap and rework
movements by lot); blocking the next operation while an in-process lot is open (a `production` hook that `quality`
registers, ADR-0022.R2); a quality agent that drafts nonconformances from complaints.
Source: ADR-0070.R3, ADR-0070.R21

## Invariants

Check point of each: `day`; first step 5.

- `INV-830` `inspection_plan_revision_immutable` (area `master_data`): no released `inspection_plan_revision` or its
  characteristics changed after `released_at`; at most one draft per plan; each quantitative characteristic has a unit and
  at least one limit, with lower <= target <= upper where set; each qualitative one has passing codes within its allowed
  codes. Protects R21, R25, R26.
- `INV-831` `usage_decision_split` (area `warehouse`): every approved or closed lot that holds stock has lines whose
  quantities sum to its quantity, with dispositions allowed at its point and `sample_consumption` at most its sample
  quantity; an `in_process` lot has no lines; `accepted` has only `release` and `sample_consumption`;
  `accepted_with_deviation` has a reason. Protects R55, R58, R59, R60.
- `INV-832` `decision_on_confirmed_results` (area `safety`): every lot that reached `approved` had, at its `Submit`, every
  result in force confirmed (entry source `person` or `integration`, or `confirmed_at` set), and for `accepted` a passing
  result in force for every required characteristic and sample unit of its revision. Protects R46, R61.
- `INV-833` `auto_accept_bounded` (area `safety`): every lot submitted by actor `system` has outcome `accepted`, a plan
  revision with `is_auto_accept_allowed`, `quality.usage_decision.auto_accept` true on its business date, and a policy
  decision that matched an `allow` rule for `system` or required approval. Protects R67, R68.
- `INV-834` `execution_matches_line` (area `warehouse`): every `inspection_lot_execution` belongs to a line of an approved
  or closed lot and targets a record of the line's disposition kind; a closed lot has every line's executions `done`, or
  a resolved `usage_decision_execution_failed` item; a line with no execution row counts as done. Protects R71, R77, R79.

## Edge cases

- `EC-280` `receipt_inspected_and_released`: a receipt of 100 of an item with point `goods_receipt` posts to
  `quality_inspection`; a lot with sample 5 opens; the results pass and the inspector accepts; a status-change task
  releases 100, and on its confirmation the lot closes. Outcome: `must_succeed`.
- `EC-281` `partial_rejection_to_supplier`: a lot of 100 is rejected with 88 released, 10 returned and 2 destroyed as
  samples; a draft return to supplier issues from `quality_inspection`, a draft internal consumption posts
  `quality_sample`, and a supplier nonconformance opens a work case. Outcome: `must_succeed`.
- `EC-282` `auto_accept_with_and_without_rule`: with the `auto_accept` setting and the plan flag on, complete passing
  results lead `system` to submit an `accepted` decision; without an `allow` rule for `system` it waits for approval; with
  one it is approved; one failing result stops the draft. Outcome: `must_succeed`.
- `EC-283` `certificate_results_need_confirmation`: a supplier certificate extraction drafts results for the matching
  lot; `SubmitInspectionLot` returns `inspection_result_unconfirmed`; after `ConfirmInspectionResult` it succeeds; a
  certificate matching no single open lot raises `certificate_unmatched`. Outcome:
  `must_reject:inspection_result_unconfirmed|must_succeed`.
- `EC-284` `output_rework_and_make_to_order`: rejected make-to-order output gets a draft rework order issuing from
  `quality_inspection`; the reworked output's lot is accepted, and its release reserves the output for the sales line.
  Outcome: `must_succeed`.
- `EC-285` `held_stock_moved_outside_lot`: while a lot of 100 is open, 10 units of its key are scrapped directly; a
  decision over 100 returns `inspection_stock_short`; a decision over 90 with a deviation reason succeeds. Outcome:
  `must_reject:inspection_stock_short|must_succeed`.
- `EC-286` `source_reversed`: a production receipt is reversed while its lot is a draft and the lot is canceled by
  `system`; after the lot is approved and released, the reversal is refused with `negative_stock` until the stock is
  moved back. Outcome: `must_succeed|must_reject:negative_stock`.
- `EC-287` `in_process_rejection`: an operation confirmation of an operation named by a released `in_process` plan opens
  a lot without stock; its rejection has no lines and opens an internal nonconformance. Outcome: `must_succeed`.

## Settings

| Key | Value type | Scope | Core default | Direction | Rule |
| --- | --- | --- | --- | --- | --- |
| `quality.usage_decision.auto_accept` | boolean | company | false | `false_tighter` | R67 |
| `quality.usage_decision.separate_from_results` | boolean | company | false | `true_tighter` | R65 |

Reads: `documents.reason_required.scrap`, `documents.reason_required.return` (ADR-0074.R22; company, boolean, core
default true), used by R57.

## UI annotations

The sources state no floorplan, title, facet, field annotation or tile for the module. Work item kinds of `quality`:

| Kind | Subject table | Owner | Due | Resolution | Rule |
| --- | --- | --- | --- | --- | --- |
| `inspection_lot_open` | `document` | `role:quality_inspector` | `days:2` | `system`: when the lot is submitted or canceled | R35 |
| `certificate_unmatched` | `document_extraction` | `role:quality_inspector` | `days:1` | `person` | R50 |
| `usage_decision_execution_failed` | `document` | `role:warehouse_keeper` | `days:1` | `person` | R37, R78 |
| `nonconformance_open` | `nonconformance` | `role:quality_inspector` | `days:5` | `command`: `CloseNonconformance` or `CancelNonconformance` | R83, R85 |
| `nonconformance_action` | `nonconformance` | `named_by_raiser` | `named_by_raiser` | `person` | R84 |

None of them is agent-resolvable. `nonconformance_open` is the trigger of the work case kind `nonconformance` (R83).

## Conflicts

None

## Proposed (not law)

None

## Trace

| Source | Where |
| --- | --- |
| ADR-0027.R7.N1 | ref: ADR-0027.R7 |
| ADR-0043.R4.N2 | ref: ADR-0043.R4 |
| ADR-0043.R15.N4 | ref: ADR-0043.R15 |
| ADR-0070.D0 | Purpose |
| ADR-0070.R1 | R1-R6 |
| ADR-0070.R2 | R7-R11 |
| ADR-0070.R3 | R12-R14, R98 |
| ADR-0070.R4 | R16-R23 |
| ADR-0070.R5 | R24-R27 |
| ADR-0070.R6 | R15 |
| ADR-0070.R7 | R28-R31 |
| ADR-0070.R8 | R32-R38 |
| ADR-0070.R9 | R39-R41 |
| ADR-0070.R10 | R42-R48 |
| ADR-0070.R11 | R49-R53 |
| ADR-0070.R12 | R54-R61 |
| ADR-0070.R13 | R62-R66 |
| ADR-0070.R14 | R67-R70 |
| ADR-0070.R15 | R71-R80 |
| ADR-0070.R15.N1 | R75, R76 |
| ADR-0070.R16 | R81-R86 |
| ADR-0070.R17 | R87-R92 |
| ADR-0070.R18 | R93, R94 |
| ADR-0070.R19 | R95, R96 |
| ADR-0070.R20 | R97 |
| ADR-0070.R21 | R98 |
| ADR-0075.D0 | ref: ADR-0075.D0 |
| ADR-0075.R4 | ref: ADR-0075.R4 |
