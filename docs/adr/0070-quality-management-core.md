# ADR-0070: Quality management core

Status: proposed (2026-11-17) under ADR-0005 (builder Claude Opus 5.5).
Design items: DS-58 (new: quality management), DS-20 (master data), DS-22 (inventory documents), DS-52 (shop floor), DS-36 (document intake), DS-29 (work queue), DS-15 (access), DS-28 (settings and policy), DS-04 (errors), DS-16 and DS-17. Related decisions: Principles 2, 3, 12. ADR-0004, ADR-0006, ADR-0007, ADR-0008, ADR-0009, ADR-0013, ADR-0018, ADR-0020, ADR-0022, ADR-0023, ADR-0027, ADR-0029, ADR-0032, ADR-0033, ADR-0034, ADR-0043, ADR-0047, ADR-0054, ADR-0055, ADR-0057, ADR-0063, ADR-0066, ADR-0068.

## Decision

The author's decision of 2026-11-17 gives Phase 1 a thin but complete quality core. This ADR designs it. Until now the design had only the seam: the stock statuses `quality_inspection` and `blocked`, quality bins, status-change tasks, and rework from inspection stock (ADR-0023, ADR-0034). Nothing recorded what a lot was inspected against, what was found, who released it, or on what evidence.

**A new layer-4 module that nobody imports.** `quality` sits in layer 4 beside `sales` and `purchasing`, and imports only the contracts of layers 1 to 3. `inventory`, `purchasing` and `production` never import it. It learns about stock through the posting events of those modules, and it changes stock only by dispatching their existing commands. Stock placed in `quality_inspection` at receipt or output stays where it is. The inspection lot names that stock by its key and claims it; it adds no column to the stock key.

**Master data with immutable revisions.** Inspection plans are selected by item or item group, inspection point and, optionally, site. Their revisions hold the characteristics and a sampling procedure, and they are released like bills of materials. Whether an item is inspected at a point is item data: `product.inspection_points` replaces the boolean `is_inspection_required`.

**The lot is a non-posting document.** An inspection lot gets the lifecycle, versions, numbering, policy and approval of ADR-0009 for free. Results are append-only rows beside it. The usage decision is the lot's content, and `Submit` puts it in force. A `quality` consumer then carries out the decision through status-change tasks and draft scrap, return, consumption and rework documents.

**People decide by default.** Agents and supplier certificates only draft results, and a person confirms them. Auto-acceptance is off until the company turns it on, allows it per plan, and writes a policy rule for it.

**No second workflow engine.** Nonconformances are records with a `defect_code`. Their containment and corrective actions are work items in an ADR-0066 work case.

### Rules

**Module and dependencies**

1. Module `quality` (layer 4, ADR-0022 rule 2) owns the ten tables of [DS-58-quality.sql](../design/DS-58-quality.sql) and the document type `inspection_lot`.
   - **Imports.** It imports the contracts of `inventory`, `production` and `master_data` (layer 3), and of `documents`, `work`, `attachments` and `policy` (layer 2). It imports no layer-4 peer.
   - **Nothing imports it.** `inventory`, `purchasing`, `production`, `sales` and `crm` never import `quality`. An import-linter contract enforces this.
   - **Purchasing is not needed.** The supplier and the order line of a receipt are read from `inventory`'s goods receipt, and a return to the supplier is `inventory`'s `return_to_supplier` (ADR-0047 rule 15).
   - **Stock changes go through the dispatcher.** `quality` changes stock or production data only through commands that its consumers dispatch through `registry` (ADR-0013 rule 9). It calls no write function of another module.
   - **Deployment profiles.** `quality` is not part of the CRM-only profile. `crm` refers to nothing in it. A nonconformance may name a complaint by its ID only.

   Reason: one direction of dependency keeps the stock core unchanged and lets a company run without quality.
2. Inspection points are a closed set: `goods_receipt`, `in_process` (after a routing operation), `production_output`, `customer_return` and `stock_recheck`.
   - **Item data.** `product.inspection_points` (`text[]`, default empty, a subset of the set) replaces `is_inspection_required` (ADR-0023 rule 3), with the same meaning per point.
   - **Who reads it.** `master_data.contract` exposes the set.
     - `inventory` posts `purchase_receipt` and `other_receipt` lines to `quality_inspection` when the set contains `goods_receipt` (ADR-0023 rule 7).
     - `production` posts output to `quality_inspection` when it contains `production_output` (ADR-0034 rule 13).
     - Returns still arrive `blocked` (ADR-0023 rule 19).
     - `quality`'s lot creator reads the set for every point.
   - **Migration.** The upgrade sets the array to `{goods_receipt, production_output}` where the boolean was true.

   Reason: inventory and production must decide the stock status at posting without reading `quality`, so the flag stays in `master_data`. One set per product says it per point.

**Master data**

3. `sampling_procedure` (company data, `master_data_change`): `code`, `name`, `kind` and its parameter, `is_active`. The kinds are:
   - `fixed_quantity`: n, capped at the lot quantity;
   - `percent`: rounded up to a whole inventory unit, at least 1;
   - `full`: the whole lot.

   The sample quantity is computed once, when the lot is created, and stored on the lot. Later kinds (`iso_2859`, `skip_lot`) add values of `kind` and their own parameter columns.
4. Inspection plans:
   - **The plan.** `inspection_plan` holds `code`, `name`, exactly one of `item_id` and `item_group_id`, `inspection_point`, an optional `site_id` (ADR-0068), and, for `in_process` plans of an item, an optional `operation_number`. The tuple is unique.
   - **Selection.** For a lot, the first plan that matches wins: item and site, then item, then item group and site, then item group. The site is that of the lot's warehouse. For `in_process`, the plan must name the confirmation's `operation_number` or have no `operation_number` (it then applies to every operation); a plan with the exact operation wins over one without. (review note, 2026-11-21) Within the plan, the revision used is the highest released one with `start_date` on or before the lot's business date.
   - **Revisions.** `inspection_plan_revision` holds `revision`, `state` (`draft` or `released`), `start_date`, `sampling_procedure_id`, `is_auto_accept_allowed`, `is_sample_destroyed`, `content_hash` and `released_at`.
     - A released revision and its characteristics are immutable, by trigger, as in ADR-0033 rules 3 and 4. A plan has at most one draft.
     - The draft commands are `other` and `is_draft_only`. `ReleaseInspectionPlanRevision` is `master_data_change`, so an agent's draft is released only through a change proposal whose `expected_version` is the draft's `content_hash` (ADR-0033 rule 2; ADR-0029 rule 5).
   - **Check result.** Releasing a plan for a point that the item's product lacks gives the check result `inspection_point_not_on_item`.
5. `inspection_characteristic` (lines of a revision): `position`, `code`, `name`, `kind`, `is_required` and `is_recorded_per_unit`. The kinds are:
   - `quantitative`, with `uom_id`, an optional `target_value`, and `lower_limit` and/or `upper_limit` (`types.quantity`, limits inclusive);
   - `qualitative`, with `allowed_result_codes` and `passing_result_codes` (a non-empty subset).

   A characteristic recorded per unit needs a result for each sample unit, 1 to the lot's sample quantity. Any other characteristic needs one summary result.
6. `defect_code` (company data, `master_data_change`): `code`, `name`, `severity` (`critical`, `major`, `minor`), `is_active`. Results and nonconformances may name one. Codes are company data with no core seed.

**Inspection lots and the stock they hold**

7. `inspection_lot` is a non-posting document type (ADR-0009 rule 6) owned by `quality`. Its header holds:
   - **Item and point:** `inspection_point`, `item_id`, `warehouse_id`, and `lot_id` or `serial_number_id` where tracked.
   - **Stock:** `held_stock_status`: `quality_inspection` or `blocked`, null for `in_process`.
   - **Quantities:** `quantity` (inventory unit) and `sample_quantity`.
   - **Plan:** `inspection_plan_revision_id`, null when no plan matched.
   - **Source:** `source_document_id` and `source_line_number` (the posting document and its line), `partner_id` (the supplier or customer), and `production_order_id` and `operation_number` for `in_process`.
   - **Decision:** `outcome` and `deviation_reason`. Its lines are the usage decision (rule 12).

   The registry flags are `is_approval_hold_allowed: true` and `is_reversible: false`. Record scope uses `warehouse_id` (ADR-0017 rule 9). A lot is identified by its document barcode (ADR-0061) until it is numbered.
8. Creation:
   - **The consumer.** The transactional consumer `inspection_lot_creator` (queue `events`) handles `GoodsReceiptPosted`, `OtherReceiptPosted`, `ProductionReceiptPosted`, `ReturnFromCustomerPosted` and `OperationConfirmationPosted`. It reads the posted lines through the owners' contracts.
   - **When it creates a lot.** It runs `CreateInspectionLot` as `system` for each line whose product's `inspection_points` contains the point and, except at `in_process`, whose stock was posted in `quality_inspection` or, for returns, `blocked`.
     - At `in_process`, a lot is created only when rule 4 selects a released plan for that item and operation. (review note, 2026-11-21) Its quantity is the confirmation's yield. No `in_process` lot is created for a confirmation whose yield is 0 (time-only or scrap-only confirmations, ADR-0071 rule 2): the lot quantity must be above 0. (review note, 2026-11-21)
     - The command key is `inspection_lot_creator:<event id>:<line number>`.
   - **What it raises.** Each lot raises `inspection_lot_open` (owner `role:quality_inspector`).
   - **No plan.** A lot without a matching plan is created anyway, with no characteristics, and a person decides it.
   - **Reversed sources.** On `ProductionReceiptReversed` and `OperationConfirmationReversed` the creator cancels the source's draft lots (`CancelInspectionLot` as `system`); a lot already decided raises `usage_decision_execution_failed`.
   - **By hand.** A person runs `CreateInspectionLot`, the only way to create a `stock_recheck` lot, for stock already in `quality_inspection` or `blocked`. To recheck available stock, the client sends a command batch (ADR-0008 rule 20): `CreateWarehouseTask` (`status_change` to `quality_inspection`), then `CreateInspectionLot`.
9. The stock link:
   - **No new stock axis.** A lot claims the stock of its key (item, warehouse, lot or serial, `held_stock_status`) over all bins and handling units. `stock_quantity` gains no `inspection_lot_id`, because putaway and quality-bin moves would have to carry it.
   - **Checked at Submit.** `SubmitInspectionLot` checks, under the `stock_value` lock of (item, warehouse) taken through `inventory.contract` (ADR-0023 rule 10), that the key's stock in the held status covers the lines that move stock, after the not-yet-executed quantities of other approved lots of the key. Otherwise it returns `inspection_stock_short`.
   - **Stock nobody claims.** `ListUninspectedStock` lists stock in `quality_inspection` that no open lot claims, for example after a manual status change, so a person can create a lot for it.

**Results**

10. `inspection_result` is append-only.
    - **Commands.** `RecordInspectionResult` takes a list of results for one lot in `draft`. Each holds the characteristic (from the lot's revision, otherwise `characteristic_not_in_plan`), an optional `sample_number` and `serial_number_id`, and a `value` (quantitative) or a `result_code` (qualitative, from the allowed codes, otherwise `result_code_not_allowed`), plus an optional `defect_code_id` and note.
    - **Pass or fail.** The handler computes `is_passed` from the immutable revision and stores it.
    - **Corrections.** A correction is a new row with `supersedes_result_id`. The result in force is the one nobody supersedes.
    - **Who recorded it.** `entry_source` is `person`, `integration` (a measuring device or LIMS through an integration actor), `certificate` (rule 11) or `agent`.
      - Rows of a person or an integration are confirmed when written.
      - `certificate` and `agent` rows are drafts until `ConfirmInspectionResult` (`human_only`) sets `confirmed_by_user_id` and `confirmed_at` once.
    - **Attachments.** Photos and certificates are attachments (ADR-0038 rule 14) linked to the lot.
    - **Seams.** Values are typed numbers (`types.quantity`), for SPC later. `test_equipment_id` is reserved and stays null until calibration exists.
11. Supplier certificates, through document intake (ADR-0057):
    - **The purpose.** Purpose `certificate_of_analysis` (leaf `inspection_lot`, consumer `quality`) reads the supplier lot code, the item code (type `code`) and, per `lines[n]`, the characteristic (type `code`, resolved to a characteristic code of the plan through the partner's mapping rules, ADR-0057 rule 24), the value (`quantity`), the unit (`unit`) and the stated pass or fail (`text`, untrusted).
    - **The drafter.** The consumer `certificate_result_drafter` handles `DocumentExtractionRecorded` and `DocumentExtractionVerified` for this purpose. It matches the extraction's partner, item and lot code to exactly one open lot, otherwise it raises `certificate_unmatched`. It then runs `RecordInspectionResult` as `system` with `entry_source` `certificate`, `document_extraction_id` and the field IDs. It also links the result rows in `extraction_result_link`.
    - **Drafts only.** Every certificate row is an unconfirmed draft, whatever the extraction's trust, so a supplier's document never decides a lot by itself (ADR-0029 rules 10–12; ADR-0013 rule 11). Values that are trusted (ADR-0057 rule 17) are shown as such on the confirmation screen.
    - **No new agent type.** The only model in the path is the existing vision step `document_reader`, where its seat is enabled. Matching and drafting are code.

**Usage decision**

12. The decision is lot content, written by `UpdateInspectionLot` (on no agent tool list in Phase 1; the auto-drafter of rule 14 runs it as `system`). (review note, 2026-11-21)
    - **Outcome:**
      - `accepted`: every required characteristic passed;
      - `accepted_with_deviation`: released despite a failure or a missing plan, with a required `deviation_reason`;
      - `rejected`: any quantity is not released.
    - **Lines** (`inspection_lot_line`): `disposition`, `quantity`, an optional `serial_number_id` and, for the dispositions `scrap` (reason kind `scrap`) and `return_to_supplier` (reason kind `return`) only, a `reason_id`. The reason is required while the matching `documents.reason_required.scrap` or `documents.reason_required.return` setting is true (ADR-0074 rule 22), so the executor's drafts are not refused with `reason_required`. (review note, 2026-11-21) Lines exist only for lots that hold stock, and their quantities sum to the lot quantity (`usage_decision_quantity_mismatch`).

      | Disposition | Allowed at | Carried out by (rule 15) |
      | --- | --- | --- |
      | `release` | every stock-holding point | `CreateWarehouseTask`, `status_change` to `available` |
      | `block` | every stock-holding point | `status_change` to `blocked`, none when already blocked |
      | `return_to_supplier` | `goods_receipt` | draft `return_to_supplier` against the receipt line |
      | `scrap` | every stock-holding point | draft `scrap` |
      | `rework` | `production_output`, `customer_return`, `stock_recheck`, for produced items | draft `production_order` of type `rework`, issuing from `quality_inspection`, after a status change from `blocked` where held so (ADR-0034 rules 4, 11) |
      | `sample_consumption` | every stock-holding point, at most `sample_quantity` | draft `internal_consumption` with movement type `quality_sample` |

      Any other combination returns `disposition_not_allowed`. `accepted` allows only `release` and `sample_consumption`.
    - **Checks at Submit.** Every result in force is confirmed (`inspection_result_unconfirmed`). `accepted` needs a passing result in force for every required characteristic and unit (`inspection_results_incomplete`). Rule 9's stock check runs.
13. Who decides is configurable, not hard-locked:
    - **Leaf.** `SubmitInspectionLot` needs the leaf `usage_decision` at `post`, a declared minimum above the verb's (ADR-0054 rule 8). Recording results needs `inspection_lot` at `post` (rule 17). (review note, 2026-11-21)
    - **Policy input** (ADR-0043 rule 4): the outcome, the item and its group, the partner, the point, and the amount: the held quantity at the preliminary price in company currency. Two new flags: `is_all_passed` and `is_quality_deviation` (`accepted_with_deviation`).
    - **Seeded rule** (ADR-0043 rule 15): `quality.deviation`, at `submit` of `inspection_lot`, actor `human`, `require_approval` with `standard` when `is_quality_deviation`. Companies add rules as usual, for example approval of rejections above an amount.
    - **Setting** `quality.usage_decision.separate_from_results` (company, boolean, default false, `true_tighter`): when true, a person who recorded or confirmed a result in force of the lot cannot submit its decision (`segregation_of_duties`).
    - **Approval.** `ApproveInspectionLot` and `RejectInspectionLot` follow ADR-0055. The pool is `quality`.
14. Auto-acceptance, off by default, takes three explicit choices of the customer:
    - **The setting** `quality.usage_decision.auto_accept` (company, boolean, default false, `false_tighter`). Turning it on is a loosening (ADR-0063 rule 3).
    - **The plan.** The plan revision's `is_auto_accept_allowed`, item data released by its own path.
    - **The policy rule.** An `allow` rule for actor `system` at `submit` of `inspection_lot` with `is_all_passed`, without which ADR-0043 rule 9 floor 8 gives the lowest rank, so a person still approves.

    The consumer `usage_decision_auto_drafter` handles `InspectionResultRecorded` and `InspectionResultConfirmed` whose payload says the lot is complete and all passed. When the first two choices hold and the lot is a draft without an outcome, it runs a batch as `system`: `UpdateInspectionLot` (`accepted`; `release` for the quantity, and `sample_consumption` for the sample when `is_sample_destroyed`), then `SubmitInspectionLot`. An unconfirmed result, a lot without a plan, and any failure stop it. No preset may seed the `allow` rule (ADR-0067 rule 3).
15. Execution after the decision is in force:
    - **The executor.** The consumer `usage_decision_executor` handles `InspectionLotApproved`, an approval or a direct `Submit`. Per line, in one batch as `system` on behalf of the decider, it dispatches the owner's create command of rule 12 with a client ID (for `scrap` and `return_to_supplier` it copies the line's `reason_id` to the draft it creates, review note, 2026-11-21), then `RecordInspectionLotExecution` (`created`, the target table and ID).
    - **Bins.** For status changes it reads the key's held stock by bin through `inventory.contract` and creates one task per bin and handling unit, in bin code order.
    - **Nothing posts.** The executor never posts: a warehouse keeper confirms tasks and posts the drafts, and a planner releases the rework order, under their own permissions and policy.
    - **Samples.** Destroyed samples are issued by `internal_consumption` lines with the new movement type `quality_sample` (offset `consumption`, SAP 331).
    - **Issuing lines name the status.** Issuing lines name the held status, so `return_to_supplier_line` gains `stock_status`. The draft `scrap` and `internal_consumption` lines carry it as ADR-0023 rule 7 allows.
    - **The tracker.** `usage_decision_tracker` handles `WarehouseTaskConfirmed`, `WarehouseTaskCanceled`, the `Posted` and `Canceled` events of the three drafts, and `ProductionOrderApproved` and `ProductionOrderCanceled`. It records `done` (with the done quantity) or `canceled` through `RecordInspectionLotExecution`.
      - A short or canceled execution raises `usage_decision_execution_failed` (owner `role:warehouse_keeper`).
      - When every line is done, it runs `CloseInspectionLot`. A line whose disposition needs no execution (for example `block` on stock already blocked) counts as done, so `CloseInspectionLot` runs at once when no line has an execution row. (review note, 2026-11-21)
    - **Make to order.** Released output still reaches its sales demand through ADR-0034 rule 14's consumer of `WarehouseTaskConfirmed`.

    Note ([ADR-0075](0075-stock-documents.md), proposed 2026-11-19): the tables `scrap`, `scrap_line`, `internal_consumption` and `internal_consumption_line` exist; their lines carry the held `stock_status`, a quality sample is a line with `consumption_kind` `quality_sample`, and `inspection_lot_execution.target_table` names these rows (ADR-0075 rules 4, 5).

**Nonconformance**

16. `nonconformance` (company data; not a document type, like `complaint`, ADR-0052 rule 20):
    - **Columns:** `kind` (`supplier`, `internal`, `customer`), `state` (`open`, `closed`, `canceled`), `defect_code_id`, item, lot or serial, `quantity`, `partner_id`, `inspection_lot_id`, the source (`source_table` and `source_id`: a document or a complaint), `description`, `root_cause`, the containment and corrective actions (text, owner user and due date each), `opened_at`, `closed_at`, `close_note` and `version`.
    - **Creation.** The executor creates one with `CreateNonconformance` for every `rejected` lot: `supplier` at `goods_receipt`, `customer` at `customer_return`, otherwise `internal`. People create the others, for a deviation or a complaint.
    - **Actions as work items.** Creating an NC raises `nonconformance_open`, the trigger of the work case kind `nonconformance` (ADR-0066 rule 3). Naming an action owner in `UpdateNonconformance` raises `nonconformance_action` for that owner (owner and due `named_by_raiser`; open key: the NC and the action kind), in the NC's open case. Containment and corrective actions are therefore work items in a case, not a second workflow engine.
    - **Closing.** `CloseNonconformance` takes a close note and resolves `nonconformance_open`. `CancelNonconformance` takes a reason and also resolves `nonconformance_open`. (review note, 2026-11-21)
    - **Supplier quality.** `ListSupplierQualityRate` gives, per supplier and period, lots, inspected and rejected quantities and the reject rate. It is the only scorecard in Phase 1.

**Commands, events and queries**

17. Commands (`other` unless noted; none posts):

    | Command | Leaf and level | Notes |
    | --- | --- | --- |
    | `CreateSamplingProcedure`, `UpdateSamplingProcedure`, `CreateDefectCode`, `UpdateDefectCode`, `UpdateInspectionPlan` | `inspection_plan` at `edit` | `master_data_change` |
    | `CreateInspectionPlan`, `CreateInspectionPlanRevision`, `UpdateInspectionPlanRevision` | `inspection_plan` at `edit` | `is_draft_only` |
    | `ReleaseInspectionPlanRevision` | `inspection_plan` at `post` | `master_data_change` |
    | `CreateInspectionLot`, `UpdateInspectionLot`, `CancelInspectionLot` | `inspection_lot` at `edit` | Generated document verbs |
    | `SubmitInspectionLot` | `usage_decision` at `post` | Policy point (rule 13) |
    | `ApproveInspectionLot`, `RejectInspectionLot` | approval flag | ADR-0055 |
    | `CloseInspectionLot`, `RecordInspectionLotExecution` | `inspection_lot` at `post` | Run by `quality`'s consumers as `system` only |
    | `RecordInspectionResult` | `inspection_lot` at `post` | Non-human or certificate rows are drafts |
    | `ConfirmInspectionResult` | `inspection_lot` at `post` | `human_only` |
    | `CreateNonconformance`, `UpdateNonconformance`, `CloseNonconformance`, `CancelNonconformance` | `nonconformance` at `edit` (Close at `post`) | |

18. Events: ADR-0009 rule 22's document events of `inspection_lot`, `InspectionPlanRevisionReleased`, `InspectionResultRecorded` and `InspectionResultConfirmed` (with `is_lot_complete` and `is_all_passed`), `InspectionLotExecutionRecorded`, and `NonconformanceCreated`, `NonconformanceUpdated`, `NonconformanceClosed` and `NonconformanceCanceled`. The consumers of rules 8, 11, 14 and 15 are `quality`'s and are registered paused (ADR-0013 rule 6).
19. Queries: `GetInspectionLot` (results in force per characteristic and unit, the decision, executions), `ListInspectionLot`, `ListInspectionPlan`, `ListUninspectedStock`, `ListNonconformance` and `ListSupplierQualityRate`. A print subject for the lot and its results serves inspection sheets (ADR-0049 rule 25).
20. The catalog rows, settings, leaves, the role template `quality_inspector`, work item and case kinds, errors, invariants and edge cases are listed in "Documents updated" and the section below.
    - **Role templates.** Besides `quality_inspector`, the template `shop_floor_lead` holds `inspection_lot` at `post`, because the shop-floor lead records and confirms in-process results at the work center (operator self-inspection). `warehouse_keeper` and `production_planner` hold `read`, to see held stock. (review note, 2026-11-21)

**Later, on seams that exist now**

21. Not in Phase 1:
    - SPC and control charts read the typed values;
    - ISO 2859 dynamic sampling and skip-lot add `sampling_procedure.kind` values;
    - test-equipment calibration fills `inspection_result.test_equipment_id`;
    - full CAPA and 8D, audits and supplier scorecards beyond the reject rate grow on work cases and `nonconformance`;
    - outgoing certificates of analysis are a print template over structured results;
    - quality costs read `quality_sample`, scrap and rework movements by lot;
    - blocking the next operation while an in-process lot is open would be a `production` hook that `quality` registers (ADR-0022 rule 2, hooks);
    - a quality agent that drafts nonconformances from complaints.

## Context

- **The author's decision of 2026-11-17** set the scope; this ADR makes the technical choices the author delegated.
- **Existing seam.** ADR-0023 has `stock_status` with `quality_inspection` and `blocked`, `quality` bins, status-change tasks for release, and return disposition. ADR-0034 posts output to inspection and reworks from it. ADR-0032 lists "quality inspection on output" in DS-52.
- **Practice studied, concepts only.**
  - SAP QM: inspection types per material, task lists with characteristics and sampling procedures, inspection lots from goods movements, the usage decision with stock postings from quality inspection stock, quality notifications.
  - Dynamics 365: quality associations, quality orders, nonconformances.
  - Odoo: quality points and checks.
  - Every one of these keeps the stock in a special status and links the lot to the movement that created it.

## Options considered

| Option | For | Against |
| --- | --- | --- |
| `quality` in layer 4, executing through the dispatcher (chosen) | Stock core unchanged; one dependency direction; module optional | Execution is asynchronous |
| `quality` in layer 3 beside `inventory` | Direct calls | Sideways imports in the core; inventory would learn about lots |
| Lot claims stock by key, checked at Submit (chosen) | No change to the stock key, putaway or tasks | Two lots on one untracked key share stock until decided |
| `inspection_lot_id` in the stock key | Exact link per bin | Every move, task and count carries it; a sixth key part |
| Lot as a non-posting document (chosen) | Lifecycle, policy, approval, versions and numbering reused | Results kept outside the version content |
| Lot as a plain table with its own states | Lighter | Decision authority would need a second approval mechanism |
| Per-point set on the product (chosen) | One flag generalized; inventory and production read it without `quality` | Array column |
| Plan existence decides inspection | No item flag | Inventory would need to read `quality` at posting |
| Nonconformance as a record with work-case actions (chosen) | No second workflow engine | No numbered NC document in Phase 1 |
| A dedicated quality agent drafting results | Reads any certificate | An LLM between a supplier's text and a release; code and intake suffice |

## Consequences

- **For companies without inspection:** nothing changes. With an empty set no lot is created, and every stock flow stays as today.
- **For inspected items:** stock is held as before. A lot opens by itself, an inspector records or confirms results, a person decides, and tasks and drafts follow. Every release names its lot, its results and its decider.
- **For agents:** they draft plan revisions (released by proposal) and, through intake, results that a person confirms. They never decide a lot.
- **For the build:** ten tables and three deterministic consumers, step 5 with the warehouse documents, and the production core step for output and in-process lots. All of it is small-model friendly: the pass rule, sampling and plan selection are pure functions.
- **Revisit when:**
  - a customer needs lot-exact stock per bin, which would bring the lot into the stock key;
  - in-process lots must block the next operation;
  - auto-acceptance is used without its policy rule being reviewed;
  - a regulated customer (food, pharmaceuticals) needs electronic signatures on decisions.

## Documents updated

- **ADR notes**, tagged "ADR-0070, proposed 2026-11-17":
  - [ADR-0018](0018-product-and-item-model.md) rule 3;
  - [ADR-0020](0020-inventory-and-costing-model.md) rule 4;
  - [ADR-0022](0022-repository-and-engineering-conventions.md) rule 2;
  - [ADR-0023](0023-warehouse-management.md) rules 3, 7, 11, 19;
  - [ADR-0027](0027-cross-cutting-ownership.md) rule 7;
  - [ADR-0032](0032-phase-1-scope-with-production.md) rule 5;
  - [ADR-0034](0034-production-orders-and-shop-floor.md) rules 4, 13;
  - [ADR-0043](0043-policy-and-approval.md) rules 4, 15;
  - [ADR-0054](0054-users-roles-and-authorizations.md) rule 11;
  - [ADR-0055](0055-approval-pools-and-stages.md) rule 2;
  - [ADR-0057](0057-document-intake-and-extraction.md) rule 2;
  - [ADR-0063](0063-configurable-policy-settings.md) rule 29;
  - [ADR-0066](0066-work-cases.md) rule 3.
- **Catalogs:**
  - [movement-types.csv](../catalogs/movement-types.csv) (`quality_sample`);
  - [settings.csv](../catalogs/settings.csv) (2);
  - [authorization-areas.csv](../catalogs/authorization-areas.csv) (6);
  - role templates and levels (`quality_inspector`);
  - [work-item-kinds.csv](../catalogs/work-item-kinds.csv) (5);
  - [work-case-kinds.csv](../catalogs/work-case-kinds.csv) (1);
  - [invariants.csv](../catalogs/invariants.csv);
  - [edge-cases.csv](../catalogs/edge-cases.csv);
  - no analysis dimension.
- **Design files:**
  - [DS-58-quality.sql](../design/DS-58-quality.sql) (new);
  - [DS-20-master-data.sql](../design/DS-20-master-data.sql) (`product.inspection_points`);
  - [DS-22-09-42-commercial-inventory.sql](../design/DS-22-09-42-commercial-inventory.sql) (`return_to_supplier_line.stock_status`);
  - [DS-36-document-intake.sql](../design/DS-36-document-intake.sql) (purpose and result-link target);
  - DS-04 errors: `inspection_stock_short`, `inspection_result_unconfirmed`, `inspection_results_incomplete`, `usage_decision_quantity_mismatch`, `disposition_not_allowed`, `characteristic_not_in_plan`, `result_code_not_allowed`;
  - [backlog.md](../design/backlog.md) (DS-58).
- **Glossary** ([00-reading-guide.md](../spec/00-reading-guide.md)): inspection point, inspection plan, inspection characteristic (the term characteristic is taken by product configuration), sampling procedure, inspection lot, inspection result, usage decision, disposition, nonconformance, defect code, quality sample. A measured result as an example of the verb Record is left to the author, who owns the existing rows.

## Edge cases and invariants

**Invariants** (DS-16; block INV-830 to INV-839, INV-830 to INV-834 taken; first step 5):

- **INV-830** `inspection_plan_revision_immutable` (area `master_data`): no released `inspection_plan_revision` or its characteristics changed after `released_at`; at most one draft per plan; each quantitative characteristic has a unit and at least one limit, with lower ≤ target ≤ upper where set; each qualitative one has passing codes within its allowed codes.
- **INV-831** `usage_decision_split` (area `warehouse`): every approved or closed lot that holds stock has lines whose quantities sum to its quantity, with dispositions allowed at its point and `sample_consumption` at most its sample quantity; an `in_process` lot has no lines; `accepted` has only `release` and `sample_consumption`; `accepted_with_deviation` has a reason.
- **INV-832** `decision_on_confirmed_results` (area `safety`): every lot that reached `approved` had, at its Submit, every result in force confirmed; and for `accepted`, a passing result in force for every required characteristic and unit of its revision.
- **INV-833** `auto_accept_bounded` (area `safety`): every lot submitted by actor `system` has outcome `accepted`, a revision with `is_auto_accept_allowed`, `quality.usage_decision.auto_accept` true on its business date, and a policy decision that either matched an `allow` rule for `system` or required approval.
- **INV-834** `execution_matches_line` (area `warehouse`): every `inspection_lot_execution` belongs to a line of an approved or closed lot, its target is of the line's disposition kind, and a closed lot has every line's executions `done` or a resolved `usage_decision_execution_failed` item, except a line whose disposition needed no execution (rule 15). (review note, 2026-11-21)

**Edge cases** (DS-17; block EC-280 to EC-289, EC-280 to EC-287 taken; first step 5):

- **EC-280** `receipt_inspected_and_released`: a receipt of 100 posts to `quality_inspection`; a lot with sample 5 opens; results pass; the inspector accepts; a status-change task releases 100; on its confirmation the lot closes.
- **EC-281** `partial_rejection_to_supplier`: a lot of 100 is rejected: 88 released, 10 returned, 2 destroyed samples; a draft return issues from `quality_inspection`, a draft internal consumption posts `quality_sample`, and a supplier nonconformance opens a work case.
- **EC-282** `auto_accept_with_and_without_rule`: with the setting and plan flag on, complete passing results submit an `accepted` decision as `system`; without an `allow` rule it waits for approval; with one it is approved; one failing result stops it.
- **EC-283** `certificate_results_need_confirmation`: a certificate extraction drafts results; `SubmitInspectionLot` returns `inspection_result_unconfirmed`; after `ConfirmInspectionResult` it succeeds; an unmatched certificate raises `certificate_unmatched`.
- **EC-284** `output_rework_and_make_to_order`: rejected make-to-order output gets a draft rework order issuing from `quality_inspection`; the reworked output's lot is accepted, and its release reserves it for the sales line.
- **EC-285** `held_stock_moved_outside_lot`: while a lot is open, 10 of its 100 units are scrapped directly; a decision over 100 returns `inspection_stock_short`; a decision over 90 with a deviation succeeds.
- **EC-286** `source_reversed`: a production receipt is reversed while its lot is a draft; the lot is canceled by `system`; once the lot is approved, the reversal is refused with `negative_stock` until the stock is moved back.
- **EC-287** `in_process_rejection`: an operation confirmation opens an in-process lot with no stock; its rejection has no lines and opens an internal nonconformance.
