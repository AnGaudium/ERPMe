Module: production    Chunk: 2 of 7    Source ADRs: ADR-0033, ADR-0034
Build step(s): 3    Generated from index: 30d5706    Compiled by: Claude Opus 5.5, 2026-11-21

# `production` compiled spec, chunk 2: work centers, production versions, structure queries, production orders, reservation, staging and issue

## Purpose

This chunk states the part of `production` law on: work centers and activity types, production versions and the phantom setting, the read-only structure queries and the reserved catalog codes, and the production order (content, creation and scheduling, rework and disassembly, release, execution state, closing, changes after release, reservation, staging and the `production_issue`). `production` is a layer 3 module (ADR-0022.R2) that owns these tables; planning and documents read them through `production.contract`. Bills of materials, routings and their releases are in chunk 1; confirmations, receipts and costing are in later chunks.

## Entities and tables

DDL: `docs/design/DS-43-54-planning-production.sql`.

| Table | Meaning | Key | Parent | Owner |
| --- | --- | --- | --- | --- |
| `work_center` | Where an operation runs: capacity, calendar, cost center, bins (R201-R203) | `id`; (`company_id`, `code`) unique | `company` | `production` |
| `activity_type` | Company data such as `setup`, `machine`, `labor`, with a time unit (R204) | `id`; (`company_id`, `code`) unique | `company` | `production` |
| `work_center_activity` | Activity types a work center records, with defaults for new operations (R205) | `id`; (`work_center_id`, `activity_type_id`) unique | `work_center` | `production` |
| `production_version` | The one explicit way to make an item in a production warehouse (R206-R209) | `id`; (`company_id`, `item_id`, `product_id`, `production_warehouse_id`, `code`) unique, nulls not distinct | `company` | `production` |
| `item_production_setting` | Per item and production warehouse: `is_phantom` (R210-R211) | `id`; (`item_id`, `production_warehouse_id`) unique | `item` | `production` |
| `production_order` | Typed header of the non-posting document type `production_order` (R218) | `id` (the `document` ID); (`company_id`, `id`, `cost_object_id`) unique; `origin_planned_order_id` unique when set | `document` | `production` |
| `production_order_component` | Component line of an order (R219) | `id`; (`production_order_id`, `line_number`) unique | `production_order` | `production` |
| `production_order_output` | Main output, co-product or by-product line (R220) | `id`; (`production_order_id`, `line_number`) unique | `production_order` | `production` |
| `production_order_operation` | Operation copied from the routing revision (R221) | `id`; (`production_order_id`, `line_number`) and (`production_order_id`, `operation_number`) unique | `production_order` | `production` |
| `production_order_output_serial` | Serial assigned to an order's output, not version content (R221) | `id`; (`production_order_id`, `serial_number_id`) unique | `production_order_output` | `production` |
| `production_issue` | Typed header of the internal posting document `production_issue` (R249) | `id` (the `document` ID) | `document`, `production_order` | `production` |
| `production_issue_line` | Issue or return line (R249-R251) | `id`; (`production_issue_id`, `line_number`) unique | `production_issue` | `production` |

Reads: `production_structure`, `bill_of_materials`, `bill_of_materials_revision`, `routing`, `routing_revision` (`production`, chunk 1); `operation_execution`, `operation_assignment`, `resource_group`, `stop_reason`, `operation_confirmation`, `production_receipt`, `cost_object` (`production`, other chunks); `working_calendar`, `warehouse`, `item`, `product`, `uom`, `cost_center`, `reason` (`master_data`); `bin`, `stock_reservation`, `lot`, `serial_number`, `material_document_line` (`inventory`); `demand_supply_line`, `item_warehouse_planning`, `planned_order` (`planning`); `product_configuration`; `document`.

## Commands and queries

Authorization areas (catalog `authorization-areas.csv`): the document types `production_order` and `production_issue` under area `production`; the leaf `production_structure` under `master_data` (bills of materials, routings, work centers, production versions and settings). The level of a verb is the catalog's (`Create`, `Submit`, `Cancel`, `Reserve`: `edit`; `Complete`, `Reopen`, `Close`: `post`; `Get`, `List`: `read`).

| Name | Actor and authorization | Input | Effect | Events | Error codes |
| --- | --- | --- | --- | --- | --- |
| `CreateProductionOrder` | area `production_order` | item, production warehouse, `good_quantity`, `planned_start_date` or `planned_end_date`, `scheduling_direction`, optional production version | Creates a draft order with exploded content (R222-R226) | not stated | `production_version_missing`, `serial_component_backflush`, `backflush_outside_production_warehouse` |
| `SubmitProductionOrder` | area `production_order`; policy point; people only in Phase 1 | order | Release: number, cost object, reservations (R232) | not stated | not stated |
| `CompleteProductionOrder` | area `production_order` | order | Sets `technically_complete` (R236) | not stated | `change_pending` |
| `ReopenProductionOrder` | area `production_order` | order | Returns the order to `in_progress` (R237) | not stated | not stated |
| `CloseProductionOrder` | generated; actor `system`, effect class `other` | order | Closes the order (R239) | not stated | not stated |
| `ReserveProductionOrderComponent` | effect class `other`; humans and the production agent; area `production_order` | order component lines | Reserves the shortfall again (R246) | not stated | not stated |
| `ListWorkCenterLoad` | query; area not stated | work center or resource group, day or week buckets | Remaining scheduled hours against available hours (R229) | none | not stated |
| `GetBillOfMaterialsExplosion` | query; area `production_structure` | item, warehouse, quantity, `explosion_date` | Multi-level structure (R212) | none | not stated |
| `ListWhereUsed` | query; area `production_structure` | item, date | Parent bills of materials and versions (R212) | none | not stated |
| `GetBillOfMaterialsRevisionCheck` | query; area `production_structure` | draft revision | The release checks without release (R213) | none | not stated |
| `GetProductionVersionSelection` | query; area `production_structure` | item, warehouse, quantity, date | Selected version and why others were not (R213) | none | not stated |

The lifecycle verb `Cancel` of a `production_order` (ADR-0009.R6) has the effects of R233. Updates of a draft order are rejected as at `CreateProductionOrder` (R225). Error codes bound to no command named here: `in_use_by_production_version` (work center deactivation, R202), `resource_group_activity_mismatch` (R205), `revision_validity_gap` and `work_center_outside_warehouse` (version save, R209), `production_order_complete` (R238), `quantity_below_fulfilled` and `referenced_line_immutable` (change orders, R241), `return_above_issued` and `stock_reserved` (issue posting, R251); check results `component_shortage` (R246) and `issue_above_requirement` (R251). Contract functions: `production.contract` (planning reads the phantom setting, R210); `inventory.contract.create_stock_reservation` (ADR-0023.R13, R244).

## Rules

### Work centers and activity types

R201. A `work_center` has the identity `code`, unique per company, `name` (not unique), and the `production_warehouse_id` it belongs to (a `physical` warehouse). The plant is the site of the production warehouse: `work_center` has no `site_id`, because the site is derived through `production_warehouse_id`. It has a nullable `resource_group_id`, and a site's calendar is the record default for its new work centers.
Source: ADR-0033.R11, .N1, .N2

R202. A `work_center` has `working_calendar_id`, `capacity_units` (parallel machines or people), `hours_per_day` per working day, `efficiency_percent` and `is_capacity_relevant`; `cost_center_id` (ADR-0027.R6), where its overhead is collected (DS-53); nullable `supply_bin_id` and `output_bin_id` in its warehouse, of bin type `production` (R247), as destinations and sources for the warehouse tasks of DS-52 (ADR-0023); and `is_active`. Deactivating a work center that a valid routing revision uses is rejected with `in_use_by_production_version`.
Source: ADR-0033.R11

R203. Available hours per working day = `capacity_units` × `hours_per_day` × `efficiency_percent` / 100, enough for an infinite load view and simple forward scheduling (DS-52, DS-54); shift patterns are later. `working_calendar` is owned by `master_data` (layer 3), so that production can read it (ADR-0024.R4).
Source: ADR-0033.R11

R204. `activity_type` is company data, for example `setup`, `machine` and `labor`, with a time unit (ADR-0018.R8, kind `time`). `activity_type.time_log_basis` (`none`, `labor`, `machine`; default `none`) says how a confirmation proposes the activity from time logs. `stop_reason` is company data under the same authorization leaf (ADR-0071.R10, ADR-0071.R11). Planned and actual activity rates are DS-53's.
Source: ADR-0033.R12, .N2

R205. `work_center_activity` rows list which activity types a work center records, with a default `quantity` and `basis` copied into new routing operations. The members of a resource group record equal sets of activity types (`resource_group_activity_mismatch`); to change a member's activity types, remove it from the group first.
Source: ADR-0033.R12, .N1

### Production versions and the phantom setting

R206. A `production_version` has the identity `item_id`, `production_warehouse_id` (a `physical` warehouse, where components are staged and output is received by default) and `code`, unique per item and warehouse; the recipe `bill_of_materials_id` (usage `production`) and `routing_id` (optional); and the selection fields `minimum_lot_quantity` and `maximum_lot_quantity`, `start_date` and `end_date` (open-ended allowed), `priority` and `is_active`. A version may name a configurable product (`product_id`, exclusive with `item_id`); it applies to every configured item of the product, after any item-level version (ADR-0046.R12).
Source: ADR-0033.R13

R207. A `production_version` has the execution settings `overdelivery_tolerance_percent` (default 0), `is_receipt_on_final_confirmation`, `is_complete_on_full_receipt` and `is_as_built_required`; the lead time `production_lead_time_method`, either `fixed` with `production_lead_time_days` (working days on the production warehouse's calendar) or `routing` (computed by DS-54); and `costing_sheet_id`, an optional override of its site's costing sheet (ADR-0072.R9).
Source: ADR-0033.R13, .N1

R208. Selection order: on the `explosion_date`, among active versions whose dates cover it and whose lot range covers the quantity, the lowest `priority`, then the lowest `code`. If none fits, the error is `production_version_missing`.
Source: ADR-0033.R13

R209. Saving a version checks that the bill of materials and the routing are active and each has a released revision valid at every date of the version's range (`revision_validity_gap`); that the routing's work centers belong to the production warehouse (`work_center_outside_warehouse`); and the operation check of ADR-0033.R8.
Source: ADR-0033.R13

R210. `item_production_setting` (company, item, production warehouse) holds `is_phantom`. A phantom is never planned or made on its own: it is exploded through its production version in that warehouse, selected with the exploded quantity and the `explosion_date`, routing ignored; a missing version gives `production_version_missing`. Planning reads the setting through `production.contract` and skips phantoms; a phantom needs no `item_warehouse_planning` row.
Source: ADR-0033.R14

R211. Whether stock of a phantom may exist and be used is business behavior; interim, flagged: it is allowed, and MRP does not net it (interim, ADR-0036.R7). `production` is a value of ADR-0024's `replenishment_source`, for items made in that warehouse. Several sources at once with quotas come after Phase 1.
Source: ADR-0033.R14

### Structure queries and reserved catalog codes

R212. Read-only queries (ADR-0008.R22; ADR-0004.R21): `GetBillOfMaterialsExplosion` (item, warehouse, quantity and `explosion_date`) returns the multi-level structure through the selected production versions and revisions, with phantoms exploded, scrap applied, fixed quantities, inventory-unit quantities as exact rationals and as rounded values, co-products and by-products, and the path to each line. `ListWhereUsed` (item and date) returns the parent bills of materials and production versions, recursively on request.
Source: ADR-0033.R15

R213. `GetBillOfMaterialsRevisionCheck` runs the checks of ADR-0033.R8 on a draft without releasing it; an agent attaches the result to its change proposal as evidence. `GetProductionVersionSelection` (item, warehouse, quantity and date) returns the selected version and why the others were not selected. Agents draft bills of materials and routings from spreadsheets or drawings, then propose the release (ADR-0029.R5). The master-data workflow is the agent type `product_engineering` (ADR-0062), a Phase 2 agent type registered with mode `off` (ADR-0078.R2); `GetProductReadinessCheck` adds the category's readiness requirements to `GetBillOfMaterialsRevisionCheck`.
Source: ADR-0033.R15, .N1

R214. Invariant codes get a production range of three digits, `INV-100` to `INV-199`; DS-16 widens its code format to `INV-nn` or `INV-nnn` and adds area `production`. The rows `INV-100` (no cycle through released `production` bills of materials, counting outputs as children, and low-level codes greater than each parent's), `INV-101` and `INV-102` are reserved and added to the catalogs with their first step when the author numbers the production core step (ADR-0032.R7); until then DS-16 rule 5 requires no check for them.
Source: ADR-0033.R16

R215. Reserved edge cases, coded by DS-17 when added: a release that would close a cycle, including one through a co-product; a three-level structure with a phantom; a bill of materials with a co-product and a by-product; a revision released between the creation of two orders with different explosion dates; a made item without a valid production version on its explosion date. Reserved parallel test: PAR-12, two releases that together would close a cycle.
Source: ADR-0033.R16

R216. Later than Phase 1, unless the author decides otherwise (open question): substitute components; parallel and alternative operation sequences; shift patterns; several sources with quotas; engineering change approval as a document type; recycling loops. Configured products (options chosen on the sales order, with the bill of materials and routing derived from rules) are in Phase 1, as DS-56. Line options (choices on a line that create no item) and items created on order exist in Phase 1 and are the base product configuration builds on (DS-56; ADR-0045.R15, ADR-0045.R16). The norms that customs reports need are actual consumption norms (research note 02, unverified); released revisions are planned norms and an input to DS-55.
Source: ADR-0033.R17

### Production orders: document and content

R217. A production order says: make this good quantity of this item, by this production version, starting on this date. Its execution is recorded by internal posting documents: the issue (and return) of components, the confirmation of operations (which can also backflush components) and the receipt of output (`production_issue`, `operation_confirmation`, `production_receipt`). It reuses the document lifecycle, change orders, reservations, warehouse tasks and bins, and the demand and supply read model, and adds an execution state, a cost object per order, assigned output serials and traceability from components to outputs. Discrete and batch work are the same model.
Source: ADR-0034.D0

R218. `production_order` is a non-posting document type (ADR-0009.R6) owned by `production`, registered with `is_change_order_allowed: true` (ADR-0028.R4). Header fields: `order_type` (`standard`, `rework`, `disassembly`); `item_id` and `production_warehouse_id`; `document_date`, which sets the numbering year (ADR-0009.R8); `production_version_id`, plus `bill_of_materials_revision_id` and `routing_revision_id`, copied as a snapshot; `good_quantity` (G) and `planned_output_quantity` (Q = G / (1 − assembly scrap), ADR-0033.R6), in the item's inventory unit; `planned_start_date` (the `explosion_date`) and `planned_end_date`, both dates (ADR-0007); `scheduling_direction`: `forward` or `backward`; `cost_object_id` (ADR-0034.R15); optional `origin_planned_order_id` (DS-54) and `for_demand_supply_line_id` (make to order, ADR-0034.R14); `overdelivery_tolerance_percent`. An order of a configured item keeps the configuration's ID (`product_configuration_id`) and the selected, sized lines as its snapshot (ADR-0046.R13).
Source: ADR-0034.R1

R219. Each line table uses `line_number` as identity (ADR-0028.R1). A `production_order_component` has the component item and required quantity; the issue warehouse (default: the production warehouse); `operation_number`, `consumption_method` (`manual`, `backflush_at_operation`, `backflush_at_receipt`), `is_fixed_quantity`; `phantom_path` (the phantom lines it came through); and `requested_date`: the scheduled start of its operation, or the order's start.
Source: ADR-0034.R1

R220. `production_order_output` holds the main output, co-products and by-products, with planned quantity, `output_type` (`main`, `co_product`, `by_product`) and `cost_coefficient`. The main output's planned quantity is G; that quantity is the supply for planning and the base for tolerance and completion. Its `requested_date` is the order's end. Output supply rows carry `for_demand_supply_line_id` from the header (ADR-0036.R9).
Source: ADR-0034.R1

R221. `production_order_operation` is copied from the routing: work center, control and `is_milestone`; durations, activity standards and scrap rate; `expected_quantity`, Q reduced by the scrap rates of the earlier operations, for information; scheduled start and end dates. `production_order_output_serial` holds, for serial-tracked output, the serials assigned to the order (ADR-0034.R16). Version content excludes `execution_state`, `is_content_edited` (ADR-0009.R9) and the output serials, which change after release without a change order. People see the order as an MO and each internal operation as a WO; `operation_execution` and `operation_assignment` hold the WO's run state, execution work center and people, outside version content like output serials (ADR-0071.R1, ADR-0071.R6, ADR-0071.R12).
Source: ADR-0034.R1, .N1

### Creating, editing and scheduling

R222. Explosion: `CreateProductionOrder` selects the production version (R208), unless the client names one, under a share lock on `production_structure` (ADR-0027.R10, class 3), so a revision cannot be withdrawn meanwhile. It copies the components, outputs and operations of the revisions valid on `planned_start_date`. Components are exploded through phantoms, with quantities by ADR-0033.R6. Conversion from a planned order uses the shared planning function (ADR-0036.R3). For a configured item, the explosion selects and sizes the product-level structures with the item's item-defining values (ADR-0046.R13).
Source: ADR-0034.R2

R223. Backward scheduling selects the version on `planned_end_date`, with the routing revision valid there, schedules backward to obtain `planned_start_date`, then explodes at that date. If the routing revision valid there differs, it schedules once more with it. The version must be valid on the resulting start, else the next version in selection order is taken, else `production_version_missing` (ADR-0033.R5.N1). The response shows both dates.
Source: ADR-0034.R2, .N1

R224. Re-explosion: while the order is in `draft`, changing `planned_start_date`, `good_quantity` or the version explodes again, unless lines were edited by hand (`is_content_edited`). In that case quantities scale by the new Q, fixed-quantity lines do not scale, and the snapshot revisions stay. The response says which happened. Lines may be added, removed or changed per order; the edits are version content, so an approval binds them.
Source: ADR-0034.R2

R225. Rejected at `Create` and at each update: an item that is both a component and an output, except in a `rework` order (ADR-0033.R7); a backflush setting on a serial-tracked component (`serial_component_backflush`); a backflush setting on any lot or serial-tracked component when the version has `is_as_built_required` (ADR-0034.R16).
Source: ADR-0034.R2

R226. A `backflush_at_operation` component without an operation number, or on an order without operations, is treated as `backflush_at_receipt`. A backflush component must be issued from the production warehouse (`backflush_outside_production_warehouse`), except components of an external operation, which are consumed at the processor location by the service receipt (ADR-0037.R5).
Source: ADR-0034.R2

R227. A component not on the order is issued from the shop floor as one command batch of the change order adding its line (required 0 unless stated) and the issue (ADR-0071.R3).
Source: ADR-0034.R2.N2

R228. Operation dates come from `setup_duration`, `run_duration` × expected quantity / base quantity, `queue_time` and `move_time`, on the work centers' calendars (ADR-0033.R10, R202), at infinite capacity. An order without operations uses the version's fixed lead time. External operations use the supplier lead time and route transit of ADR-0037.R3.
Source: ADR-0034.R3

R229. `ListWorkCenterLoad` (a work center or a resource group, day or week buckets) adds up the remaining scheduled hours of draft and approved orders that are not technically complete, against available hours; for a resource group it sums load and available hours over its members. It counts an operation at its execution work center (ADR-0071.R16). Real orders only; planned orders are added by planning's `ListCapacityLoad` (ADR-0036.R11). Finite sequencing and levelling are DS-54's capacity check, proposed by the planning agent, never applied without approval.
Source: ADR-0034.R3, .N1, .N2

### Rework and disassembly

R230. A `rework` order has no explosion and may have no production version. The client enters the components, usually the item itself, which may be issued from `quality_inspection` (ADR-0034.R11), and the operations. The main output is the same item or another named item. The cycle this creates is a production order fact, which the costing solver handles (ADR-0025.R6), never a bill of materials. A rework order may be drafted by `quality`'s usage-decision executor for a lot's `rework` line, issuing from `quality_inspection` (ADR-0070.R12, ADR-0070.R15).
Source: ADR-0034.R4, .N1, .N2

R231. A `disassembly` order issues the item as the single component, quantity G, with movement type `disassembly_issue`. Its outputs are the components of the version's bill of materials revision, one level with phantoms exploded, scaled to G, received with `disassembly_receipt`, all `co_product` lines; how cost splits over them is DS-53's. The bill of materials outputs are left out, and so is the routing unless the client adds operations. Cumulative net issues of the input may not exceed G × (1 + tolerance). Technical completion is manual, and `INV-104` does not apply. A production order has at most one output of type `main` (a unique index); a disassembly order has none.
Source: ADR-0034.R4, .N1

### Release, cancel, execution state and closing

R232. Document states follow ADR-0009.R6. Release is `submit` of type `production_order` for policy (ADR-0043.R17): `SubmitProductionOrder` is a policy point (ADR-0029.R6). An `approved` order is released: execution may start, it gets its number and its cost object, and its components are reserved (R244, R245). An agent releases only by `Submit` under policy; a tainted run cannot (ADR-0029.R11). In Phase 1 no agent tool list holds `Submit`, so people release production orders (ADR-0050.R30).
Source: ADR-0034.R5

R233. `Cancel` is allowed only while no posting document of the order exists, reversed or not. Canceling cancels open warehouse tasks and reservations, closes the order's demand and supply lines as `canceled`, and leaves staged stock in the supply bin, with move tasks back proposed by the putaway rules.
Source: ADR-0034.R5

R234. `policy_input` (ADR-0043.R4) of a `production_order`: `amount` is the unit cost of the released estimate valid for the order's version on `planned_start_date` (ADR-0035.R14.N1) times G or, without one, the components' required quantities at their preliminary prices. Booleans: `has_component_shortage` (available to promise below a component's open requirement at `Submit`), `is_content_edited`, and `is_rework` (`order_type` `rework`).
Source: ADR-0034.R5, .N1

R235. `policy_input` of a `production_issue`: `amount` is the lines' quantities at preliminary prices. Boolean: `is_above_requirement` (a line above its component line's open requirement, R251).
Source: ADR-0034.R5.N1

R236. `production_order.execution_state` is `not_started` (approved, nothing posted), `in_progress` (from the first posting; it stays so when every posting has been reversed) or `technically_complete` (logistics are finished). Technical completion comes by `CompleteProductionOrder`, or automatically when the version sets `is_complete_on_full_receipt` and the main output's cumulative net receipts reach G. It cancels open tasks and reservations, closes the order's open demand and supply lines as `canceled` for the unfulfilled rest, handles staged stock as at `Cancel`, frees assigned serials not received, and planning ignores the order. It is rejected while a change is pending (`change_pending`).
Source: ADR-0034.R6

R237. `ReopenProductionOrder` returns a technically complete order to `in_progress` while it is not closed. It reopens its demand and supply lines (reopening clears `closed_reason` and restores open quantity, ADR-0024.R8) and reserves again.
Source: ADR-0034.R6

R238. What each state allows (issues, returns, confirmations, receipts; reversals; close-job cost postings of DS-53):
- `draft`, `pending_approval`: no postings, no close-job cost postings;
- `approved` and `not_started` or `in_progress`: postings, reversals and close-job cost postings;
- `approved` and `technically_complete`: no postings (`production_order_complete`); reversals and close-job cost postings;
- `closed`: no postings and no reversals; close-job cost postings when a period is reopened and solved again.
Source: ADR-0034.R6

R239. Closing: the settlement task is the period-end actual costing job (ADR-0035.R5). A daily system job with an explicit business date (ADR-0007.R17), also started by the period-lock event, closes, as actor `system`, every technically complete order whose last posting lies in a period whose settlement task (DS-53) is done and whose area for production cost is locked; that area is `inventory` (ADR-0035.R3). A technically complete order without postings closes at the next run. Orders with a pending change are skipped. It runs the generated `CloseProductionOrder`, effect class `other`.
Source: ADR-0034.R7

R240. A closed order allows no logistics postings and no reversals; close jobs may still post to its cost object. No close task requires orders to be closed before a lock; whether completed orders must be closed before a period lock is a question for the author (open question).
Source: ADR-0034.R7

### Changes after release

R241. Changes to a released order follow ADR-0028.R3 to ADR-0028.R5: a pending version is drafted and approved (policy usually allows without approval) while the version in force keeps executing. The production version and the snapshot revisions do not change after release. A change of G rescales the components, outputs and operation quantities by the new Q; fixed quantities do not scale, and no line goes below what is already posted (`quantity_below_fulfilled`). Lines with postings keep item, unit (with the line's conversion snapshot, ADR-0056.R9) and warehouse (`referenced_line_immutable`). Operations with confirmations cannot be removed or change work center. When the change takes force, reservations and demand and supply lines are adjusted.
Source: ADR-0034.R8, .N1

R242. An unconfirmed internal operation may move to another active member of its work center's resource group in the order's production warehouse: in a draft this is an edit, after release a change order. Standard values carry over; the target's calendar, capacity and efficiency schedule it, and its cost center and rates cost the confirmation.
Source: ADR-0034.R8.N2

### Reservation and staging

R243. Component lines are demand lines and output lines supply lines (`demand_supply_line`) from `Create`; this is interim and flagged, as ADR-0024.R8's list is. Their typed columns `production_order_component_id` and `production_order_output_id` are added to `demand_supply_line` before step 3; ADR-0028.R2 left these columns to the author under B3, so they are flagged too (open question). The output supply rows also carry `for_demand_supply_line_id`, flagged with these columns (ADR-0036.R9). Components of external operations are demand lines at the processor location (ADR-0037.R2). The open quantity never goes below 0, even after over-issue.
Source: ADR-0034.R9

R244. Components are reserved through `inventory.contract.create_stock_reservation` (ADR-0023.R13) up to available to promise. `production` passes the reservation's `destination_bin_id` (the supply bin) and `release_sequence` (operation order), so inventory never reads production tables. `destination_bin_id` is passed only for components issued from the production warehouse.
Source: ADR-0034.R9

R245. Reservation timing is settled by `production.reservation.mode` (company: `off`, `on_release`, `scheduled`; default `on_release`, reserving at release) and `production.reservation.window_days` (14). The production agent's reservation sweep (the agent type `production` is Phase 2, ADR-0078.R2), a workflow without an LLM step, reserves shortfalls in the reservation priority and never takes stock reserved for another demand. A move between orders is `TransferStockReservation` from an approved change proposal (ADR-0064.R7, ADR-0064.R15, ADR-0064.R23, ADR-0064.R24).
Source: ADR-0034.R9.N1

R246. The unreserved rest is a shortage, with the check result `component_shortage`. `ReserveProductionOrderComponent` (effect class `other`) reserves again later; humans and the production agent run it directly. Interim, flagged: release with shortages is allowed. Reserving at release can hold stock for an order that starts months later (open question).
Source: ADR-0034.R9

R247. Bin type `production` (ADR-0023.R2) is never read by pick removal. A work center's `supply_bin_id` and `output_bin_id` must be of that type (ADR-0033.R11). A work center without a supply bin stages to the production warehouse's default bin.
Source: ADR-0034.R10

R248. `RunPickRelease` (ADR-0023.R14) also serves production orders: its pick tasks move reserved components to the reservation's `destination_bin_id`, released by `release_sequence`. Plain warehouses have no tasks, and issues take stock from the default bin. Staging moves quantity only (ADR-0023.R8).
Source: ADR-0034.R10

### Production issue

R249. `production_issue` is an internal posting document (ADR-0009.R19, reversible). A `production_issue_line` has the order component line, item, lot or serial; `quantity` as entered in any allowed unit of the component, `uom_id`, the conversion snapshot and `inventory_quantity`, which the stock movement and the order line's progress use (ADR-0056.R9, ADR-0056.R17); bin, handling unit and `stock_status` (`available`, or `quality_inspection` for rework); `is_return`; optional `output_serial_number_id` (ADR-0034.R16); and `scrap_reason_id`, a reason of kind `scrap`, for over-issue and component scrap (ADR-0074.R13, ADR-0074.R14).
Source: ADR-0034.R11, .N1, .N2

R250. A line moves stock with movement type `production_issue` from any bin of the issue warehouse, or `production_return` back to the bin the putaway rules give. Every line carries the order's `cost_object_id` (ADR-0025.R1). The movement-type rows and the values are DS-53's (ADR-0023.R7).
Source: ADR-0034.R11

R251. A return may not exceed the net issued quantity of its component line and lot or serial (`return_above_issued`); it restores the line's open quantity, not its reservation. Issuing above the line's open requirement is allowed with the check result `issue_above_requirement`; how consumption above norms is treated is DS-53's (interim, flagged). Components not on the order are first added through the order or a change order. An issue that would cut into other demands' reservations is rejected with `stock_reserved` (ADR-0023.R13).
Source: ADR-0034.R11

## Invariants

Statements are those of `invariants.csv`.

| ID | Name | Check point | Statement | Protects |
| --- | --- | --- | --- | --- |
| `INV-101` | `structure_content_hash_matches` | day | Every released bill of materials and routing revision's `content_hash` equals the hash of its stored rows. | R214 |
| `INV-102` | `production_version_covered` | day | At every date of an active production version's range, its active bill of materials and, if set, its active routing each have a valid released revision. | R209, R214 |

Both are flagged in the catalog: first step "ADR-0032 rule 7: production core step (number pending author)". Named by rules of this chunk, with their rows in other chunks: `INV-100` (R214; its catalog source names ADR-0033.R8 first), `INV-104` (R231).

## Settings

None: the settings `production.reservation.mode` and `production.reservation.window_days`, used by R245, have their rows in the chunk of ADR-0064.R23.

## Conflicts

CONFLICT ADR-0033.R11: ADR-0033.R11.N1 and the DDL govern uniqueness; only `code` is unique per company, `name` is not (R201).
CONFLICT ADR-0033.R11.N2: ADR-0068 governs the plant; the plant is the site of the production warehouse, superseding "the production warehouse in place of a plant", and `work_center` gains `resource_group_id` without `site_id` (R201).
CONFLICT ADR-0033.R14: the rule's closing sentence citing ADR-0036.R7 governs phantom stock; MRP does not net it, kept interim and flagged (R211).
CONFLICT ADR-0033.R15: ADR-0033.R15.N1 governs the master-data workflow; it is the agent type `product_engineering` of ADR-0062, replacing "a later agent" and DS-34 (R213).
CONFLICT ADR-0033.R17: the rule's own amendment of 2026-11-15 moves configured products into Phase 1 as DS-56, so they leave the later list (R216).
CONFLICT ADR-0034.R9: ADR-0034.R9.N1 governs reservation timing; reserving at release holds only in mode `on_release`, set by `production.reservation.mode` (R245).
CONFLICT ADR-0034.R9.N1: ADR-0078.R2 makes the agent type `production`, whose sweep the note names, a Phase 2 agent type (R245).
CONFLICT ADR-0033.R15.N1: ADR-0078.R2 makes `product_engineering` a Phase 2 agent type with mode `off` (R213).
CONFLICT ADR-0034.R11: ADR-0034.R11.N2 replaces the text `reason_code` of an issue line by `scrap_reason_id`, a reason of kind `scrap`, as the DDL holds (R249).

## Trace

| Source | Where |
| --- | --- |
| ADR-0033.R11 | R201-R203 |
| ADR-0033.R11.N1 | R201 |
| ADR-0033.R11.N2 | R201 |
| ADR-0033.R12 | R204-R205 |
| ADR-0033.R12.N1 | R205 |
| ADR-0033.R12.N2 | R204 |
| ADR-0033.R13 | R206-R209 |
| ADR-0033.R13.N1 | R207 |
| ADR-0033.R14 | R210-R211 |
| ADR-0033.R15 | R212-R213 |
| ADR-0033.R15.N1 | R213 |
| ADR-0033.R16 | R214-R215 |
| ADR-0033.R17 | R216 |
| ADR-0034.D0 | R217 |
| ADR-0034.R1 | R218-R221 |
| ADR-0034.R1.N1 | R221 |
| ADR-0034.R2 | R222-R226 |
| ADR-0034.R2.N1 | R223 |
| ADR-0034.R2.N2 | R227 |
| ADR-0034.R3 | R228-R229 |
| ADR-0034.R3.N1 | R229 |
| ADR-0034.R3.N2 | R229 |
| ADR-0034.R4 | R230-R231 |
| ADR-0034.R4.N1 | R230, R231 |
| ADR-0034.R4.N2 | R230 |
| ADR-0034.R5 | R232-R234 |
| ADR-0034.R5.N1 | R234-R235 |
| ADR-0034.R6 | R236-R238 |
| ADR-0034.R7 | R239-R240 |
| ADR-0034.R8 | R241 |
| ADR-0034.R8.N1 | R241 |
| ADR-0034.R8.N2 | R242 |
| ADR-0034.R9 | R243, R244, R246 |
| ADR-0034.R9.N1 | R245 |
| ADR-0034.R10 | R247-R248 |
| ADR-0034.R11 | R249-R251 |
| ADR-0034.R11.N1 | R249 |
| ADR-0034.R11.N2 | R249 |
