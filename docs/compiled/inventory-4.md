Module: inventory    Chunk: 4 of 7    Source ADRs: ADR-0023, ADR-0024, ADR-0025, ADR-0027
Build step(s): 0, 1, 3, 5    Generated from index: 30d5706    Compiled by: Claude Opus 5.5, 2026-11-21

# Compiled spec: `inventory`, chunk 4

## Purpose

`inventory` owns material documents, stock, costing, landed cost and the warehouse management tables, and sits in layer 3 (ADR-0022.R2). This chunk states warehouse execution: receipts and putaway, reservations, pick release and removal, task confirmation, deliveries, replenishment, counting, returns, exceptions, printing and warehouse queries. It also states the demand and supply read model that `planning` reads, the hand-over of converted planned orders, the later-phase costing seams, the step 3 stock document types, the read models and the complete lock order. Stock keys, statuses, bins, handling units and warehouse movements are in other chunks.

## Entities and tables

| Table | Meaning | Key | Parent | Owner |
| --- | --- | --- | --- | --- |
| `warehouse_task` | A task of kind `putaway`, `pick`, `move`, `replenishment`, `status_change` or `count`, with `state` `open`, `in_progress`, `confirmed` or `canceled` (state names interim in the DDL), `confirmed_quantity` and `shortage_reason` (R601, R622, R638) | `id`; (`company_id`, `id`) | `warehouse` | `inventory` |
| `stock_reservation` | Stock held for a demand line (R607-R614) | `id`; (`company_id`, `id`) | `demand_supply_line` | `inventory` |
| `demand_supply_line` | Open demand or supply of one source line, the planning read model (R646-R652) | `id`; (`company_id`, `id`) | `company` | `inventory` |
| `replenishment_request` | Hand-over of converted planned orders, written by `inventory.contract.request_replenishment` (R654) | `id`; (`company_id`, `id`) | `company` | `inventory` |
| `replenishment_request_line` | One converted planned order with its order unit and snapshot (R654) | `id`; (`replenishment_request_id`, `line_number`) unique; `origin_planned_order_id` unique | `replenishment_request` | `inventory` |

DDL: `warehouse_task` and `stock_reservation` in `docs/design/DS-22-09-42-commercial-inventory.sql`; `demand_supply_line`, `replenishment_request` and `replenishment_request_line` in `docs/design/DS-43-54-planning-production.sql`. The DDL of `demand_supply_line` also carries `for_demand_supply_line_id` (ADR-0036.R9), `owner_partner_id` (ADR-0037.R7) and `hold_reasons` (`not_approved`, `credit_hold`; ADR-0047.R18).

Reads: `stock_count`, `stock_quantity`, `stock_value`, `material_document_line`, `handling_unit`, `bin`, `delivery`, `transfer_order`, `transfer_order_line`, `stock_transfer_line`, `goods_receipt_line`, `delivery_line`, `return_to_supplier_line`, `return_from_customer_line` (`inventory`, other chunks); `bin_item`, `product_uom`, `supplier_item`, `supplier_purchasing_term` (`master_data`, `planning`); `planned_order` (`planning`); `journal_line` (`ledger`); `production_structure` (`production`); `configuration_state` (`configuration`); `money_account_balance` (`cash`); `event_subject`.

## Commands and queries

Authorization areas (catalog `authorization-areas.csv`): the area `inventory` covers stock documents, warehouse tasks and reservations; the function `stock_reservation` (reservations); the document type `delivery`; the function `planned_order` (`planning`) covers converting planned orders. Verb levels are the catalog's (`Get`, `List`: `read`; `Create`, `Assign`, `Start`, `Cancel`, `Pack`, `Unpack`, `Convert`: `edit`; `Confirm`, `Run`, `Post`, `Transfer`: `post`).

| Name | Actor / authorization | Input | Effect | Events | Error codes |
| --- | --- | --- | --- | --- | --- |
| `CreateWarehouseTask` | person or agent draft; area `inventory` | `move`, `status_change` or `count` task | Creates the task (R638) | `WarehouseTaskCreated` | none stated |
| `AssignWarehouseTask` | area `inventory` | task, assignee | Assigns the task (R638) | none stated | none stated |
| `StartWarehouseTask` | area `inventory` | task | Sets `in_progress` (R638) | none stated | none stated |
| `ConfirmWarehouseTask` | area `inventory` | scanned bins, handling units, lot or serials, actual quantity, `shortage_reason` | Records the fact and moves the goods; confirms only what the step expects (R622-R626, R1037) | `WarehouseTaskConfirmed` (with a shortage flag) | `task_quantity_exceeded`, `serial_not_in_bin`, `scan_mismatch`, `scan_unresolved`, `serial_already_scanned` |
| `CancelWarehouseTask` | area `inventory` | task | Cancels the task (R638) | `WarehouseTaskCanceled` | none stated |
| `PackHandlingUnit`, `UnpackHandlingUnit` | area `inventory` (function `warehouse_task`) | handling unit and content | Write warehouse movements into or out of a unit; a `closed` unit's content changes only by unpacking (R447, R448, R456, R628, R638) | none stated | none stated |
| `RunPickRelease` | deterministic job, per demand document; area `inventory` | demand document, also of production orders | Reserves unreserved lines, creates pick tasks under the `stock_value` lock; for production, to the reservation's `destination_bin_id` by `release_sequence` (R616, R620, R830, R831) | `StockReservationCreated`, `WarehouseTaskCreated` | `demand_supply_not_released`, `demand_on_hold` |
| `CreateDelivery` | area `inventory`, leaf `delivery` | picked stock of demand lines | Creates the delivery (R627, R630) | none stated | `demand_supply_not_released`, `demand_on_hold` |
| `PostDelivery` | area `inventory`, leaf `delivery`; not `is_policy_in_handler` | delivery of sales order lines | Posts the goods issue, movement `sales_issue` or `free_goods_issue`, cost of goods sold at delivery (R628, R629, R833, R1020) | none stated | `quantity_exceeds_open`, `demand_on_hold`, `demand_supply_not_released` |
| `ConvertPlannedOrder` | proposal-bound for agents; area `planned_order` | firmed or proposed planned orders | Sets `converted`, calls `inventory.contract.request_replenishment` (R653-R654) | `ReplenishmentRequested` | none stated |
| `GetStockBalance` | query; area `inventory` | as-of date for item, warehouse and lot; bin, status and handling unit on the current balance only, no `as_of` | Quantity and value per item, warehouse and lot as of a date; current balance by bin, status and handling unit (R226, R446, R644) | none | none stated |
| `GetAvailableToPromise` | query; area `inventory` | item, warehouse | Available to promise (R608) | none | none stated |
| `ListWarehouseTask` | query; area `inventory` | not stated | Tasks, including exceptions before step 5 (R640) | none | none stated |
| `GetHandlingUnit` | query; area `inventory` | handling unit | The handling unit (R644) | none | none stated |
| `GetPutawayPreview` | query; area `inventory` | draft rule set, stock | Targets the rules would choose (R606) | none | none stated |
| `ListItemLabel`, `ListLotLabel`, `ListSerialLabel` | print subject queries; area not stated | not stated | Label data (R643) | none | none stated |

`TransferStockReservation` (R613) has its row in chunk 7. Contract interfaces, not registry commands: `inventory.contract.create_warehouse_task` (R601, R638); `inventory.contract.create_stock_reservation` and `cancel_stock_reservation`, called by document commands, which emit `StockReservationCreated` and `StockReservationCanceled` (R608); a change of a reservation's `destination_bin_id` (R614); `inventory.contract.request_replenishment`, which emits `ReplenishmentRequested` (R654). Error codes bound to no named command: `reservation_exceeds_available` (R609); `stock_reserved` for voluntary issues (R609). Check results, not errors: `capacity_not_checked`, `bin_capacity_exceeded`, `mixed_stock_not_allowed` (R605, R606), `no_pickable_stock` (R619), `part_quantity_recomputed` (R621), `inspection_stock_short` (R603).

## Rules

### Receipts and putaway

R601. A receipt posts to the bin ADR-0023.R7 gives. Its tasks are written by the posting's own transaction through `inventory.contract.create_warehouse_task` (ADR-0022.R4): one task per (item, lot, handling unit, source bin) with quantity N; a handling unit is one task.
Source: ADR-0023.R11

R602. Every task proposal (putaway targets, pick sources of R618) is listed in the plan like events, never in `plan_hash` (ADR-0013.R5), so concurrent warehouse work never causes `plan_hash_mismatch`. Check results that follow from proposals are not hashed either (ADR-0040.R10).
Source: ADR-0023.R11

R603. Releasing from inspection is a `status_change` task to `available` or `blocked`. For stock that an inspection lot claims, the `status_change` tasks that release or block it are created by `quality`'s usage-decision executor (ADR-0070.R15). A person's own status change stays possible, and a later decision is checked against the stock left (`inspection_stock_short`).
Source: ADR-0023.R11, ADR-0023.R11.N1

R604. Putaway rules are rows per warehouse, each with a unique `position`. A rule matches on item, product category, storage condition, status and handling unit type. It targets a zone or bin type with a method: `fixed_bin` (the item's `bin_item`); `nearest_free`; `consolidate` and `empty_bin` in the second slice.
Source: ADR-0023.R12

R605. Each method picks the lowest `pick_sequence`, then bin code, among bins that are not blocked, have no open count, pass the mix rules and pass capacity, counting the open tasks arriving at the bin. Capacity uses the handling unit type's dimensions for a whole unit, or the item's gross weight and dimensions (ADR-0018.R4); when data is missing, the bin is accepted with the check result `capacity_not_checked`.
Source: ADR-0023.R12

R606. Capacity and mix rules are hard when the system proposes a bin. At confirmation, a worker's different target bin that breaks them gives the check results `bin_capacity_exceeded` or `mixed_stock_not_allowed` and still records the fact. When no bin is found, the task is created without a target and becomes an exception (R640). The query `GetPutawayPreview` shows the targets a draft rule set would choose for given stock.
Source: ADR-0023.R12

### Reservations

R607. A `stock_reservation` holds stock for a demand line (a sales order or transfer order line; production order component lines too): item, warehouse, quantity, optional lot (by agreement), `picked_quantity`, `fulfilled_quantity` and `state` (`open`, `picked`, `fulfilled` when fulfilled equals quantity, `canceled`). Its reserved amount is quantity minus `fulfilled_quantity`. It never names a serial. The demand line is referred to by `demand_supply_line_id` (ADR-0028.R2). Reservations and tasks also carry the reserved `owner_partner_id` (ADR-0030.R8).
Source: ADR-0023.R13

R608. `inventory.contract.create_stock_reservation` and `cancel_stock_reservation` are posting interfaces called by document commands (DS-22), which emit the reservation events; they are not user commands. Available to promise per (item, warehouse) is `available` quantity minus the reserved amounts of reservations in `open` or `picked`. `GetAvailableToPromise` answers it from on-hand stock only in Phase 1. Available stock still in a receiving bin counts, so a pick release before putaway may be short; that is expected.
Source: ADR-0023.R13

R609. A reservation never exceeds available to promise (`reservation_exceeds_available`); there is no over-reservation, and the unreserved rest of a demand line is a backorder. Scrap, internal consumption, other issues, purchase returns, transfers, reversals and `status_change` to `blocked` are rejected with `stock_reserved` when they would cut into reservations (`EC-337`).
Source: ADR-0023.R13, ADR-0023.R13.N3

R610. Demands are served first come, first served; production keeps the order of ADR-0064.R7, ordering production demands by requested date. Count shortages and blocking found damage always post, then cancel reservations deterministically, by the demand document's date, number and `line_number` descending (the newest reservation is dropped), until the limit holds, and raise an exception (`EC-324`).
Source: ADR-0023.R13, ADR-0023.R13.N1, ADR-0023.R13.N3

R611. Availability is not lot-aware. A reservation whose lots fail shelf-life rules at pick time gives a short pick. Planning ignores reservations in netting and counts demand in full (ADR-0024.R9).
Source: ADR-0023.R13

R612. Reservations, the check and the posting interfaces are step 3 core; documents call them at step 5. Production orders reserve components at release, passing `destination_bin_id` and `release_sequence` (ADR-0034.R9). Picked and fulfilled quantities stay stored on the reservation, checked by `INV-58`; the open quantity of the demand line is stored in `demand_supply_line` (ADR-0031.R5, ADR-0031.R6).
Source: ADR-0023.R13

R613. `TransferStockReservation` (module `inventory`, verb Transfer, `is_proposal_bound`, `stock_reservation` at `post`) moves open, unpicked reserved quantity from one production order component line to another of the same item and warehouse, at most the target line's short quantity at execution, max(0, unreserved open requirement − available to promise of the item in the target's issue warehouse) (ADR-0064.R24), only from the execution of an approved change proposal; the new reservation carries `transferred_from_reservation_id` (ADR-0064.R24). Sales order reservations are not transferred in Phase 1.
Source: ADR-0023.R13.N1

R614. `inventory.contract` offers a change of a reservation's `destination_bin_id`, used when a WO moves to another work center; staged stock gets a move task to the new supply bin (ADR-0071.R16).
Source: ADR-0023.R13.N2

### Pick release and removal

R615. Pick tasks serve demand lines, not deliveries. `RunPickRelease` (a deterministic job, per demand document, step 3) turns reservations into pick tasks; it also serves production orders, moving components to the reservation's destination bin (ADR-0034.R10). Each task carries the demand line's unit and the inventory quantity (ADR-0018.R11) and refers to `demand_supply_line_id` (ADR-0028.R2). Creation takes the `stock_value` lock of each item and warehouse before reading available bin stock (ADR-0030.R12).
Source: ADR-0023.R14

R616. Pick tasks of serial items name the bin, not the serial. The serials are scanned at confirmation and checked against bin and status (`serial_not_in_bin`).
Source: ADR-0023.R14

R617. Removal reads only `storage` and `picking` bins with status `available`, minus the quantity of open tasks leaving each key.
Source: ADR-0023.R14

R618. Removal orders by: (1) lot: `fefo` by `expiry_date` (lots without one last), skipping lots below the customer's minimum remaining shelf life, with the planned delivery date as reference, or the business date when the line has none; `fifo` by the lot's earliest receipt posting date (FIFO needs lot tracking; untracked items use bin order); (2) lot code; (3) bin: `picking` before `storage`, and a whole handling unit when the quantity matches; (4) `pick_sequence`; (5) bin code; (6) handling unit code. No database ID takes part (ADR-0006.R6).
Source: ADR-0023.R14

R619. When no eligible stock exists, the line is short: the command succeeds with the check result `no_pickable_stock`, and the shortage becomes an exception.
Source: ADR-0023.R14

R620. A demand line without a reservation (with `sales.reserve_on_approval` false, or a backorder that stock now covers) is first reserved by `RunPickRelease`, up to available to promise by R608, in the same transaction and under the same `stock_value` locks; its tasks are then created from that reservation, and what cannot be reserved is short (`no_pickable_stock`). Rows not released or on hold are refused with `demand_supply_not_released` or `demand_on_hold` (ADR-0047.R18, ADR-0047.R19).
Source: ADR-0023.R14.N1

R621. The client derives a breakdown such as "2 cartons and 3 bottles" from `product_uom`, using the product's packaging hierarchy (`contains_uom_id`, `contains_quantity`), largest whole unit first; `is_default_pick_unit` marks the unit a pick list proposes for a demand line in the inventory unit. When a part's provisional quantity changes at Post, an open task is adjusted, and a task already confirmed gets a follow-up task (an extra pick, or a putaway back), with the check result `part_quantity_recomputed` (ADR-0056.R10, ADR-0056.R15).
Source: ADR-0023.R14, ADR-0023.R14.N2

### Confirming a task

R622. `ConfirmWarehouseTask` records the scanned source and target bins, the handling units, lot or serials, and the actual quantity, which may not exceed the task's (`task_quantity_exceeded`). A smaller quantity requires a `shortage_reason`. The scanned target may differ from the proposal (R606).
Source: ADR-0023.R15

R623. Every confirmed pick moves the goods to a non-pickable bin (ADR-0023.R7), so no later release allocates them again.
Source: ADR-0023.R15

R624. A short confirmation creates a count task for the source bin, which blocks it until counted (R632), and an exception. The demand line keeps the unpicked rest, which the next `RunPickRelease` takes up. What happens to the order after a short pick is an open question; interim, flagged: ship what is picked, and leave the rest as backorder on the demand line (`EC-32`).
Source: ADR-0023.R15

R625. Every scan carries a device idempotency key (ADR-0008); the PWA chains simulate and execute in one call sequence.
Source: ADR-0023.R15

R626. Every scanned field is confirmed: the handler evaluates the raw scan with `EvaluateBarcode` against what the step expects (the source bin, the handling unit, the task's item, a lot or serial of that item, the proposed or a changed target bin) and refuses anything else with `scan_mismatch`, or `scan_unresolved` when the scan has a typed issue; overrides are command fields with a reason. Serials are scanned per unit with a running count, a serial scanned twice is refused (`serial_already_scanned`), and scanning a closed handling unit that the task takes whole confirms all its serials (ADR-0061.R15, ADR-0061.R19).
Source: ADR-0023.R15.N1

### Deliveries

R627. Deliveries are created from confirmed picks. `CreateDelivery` takes the picked stock (lots, serials, bins, handling units) of one or more demand lines. The delivery never needs updating after approval (ADR-0009.R9), and a short pick simply yields a partial delivery.
Source: ADR-0023.R16

R628. In the `staged` flow, picks go to `staging`; packing closes handling units in `packing`; `PostDelivery` posts the goods issue from the `shipping` bin. In the `direct` flow, `PostDelivery` issues from the default shipping bin the picks moved to. In a plain warehouse there are no tasks: `CreateDelivery` takes stock from the warehouse's default bin (ADR-0031), and the reservation goes straight to `fulfilled` at `PostDelivery`.
Source: ADR-0023.R16

R629. Value and ownership change only at `PostDelivery` (ADR-0020). Pick batches and waves (second slice, step 5) group the pick tasks of several demand documents, sorted by zone and `pick_sequence`; each document is released as its own internal command, so locks stay small.
Source: ADR-0023.R16, ADR-0023.R13.N3

R630. `CreateDelivery`, and `inventory`'s other documents created from source lines (receipts and returns), set the new version's `is_tainted` as the OR of the effective taint of every source line's document version, on create and on every update that adds lines (ADR-0029.R8, ADR-0047.R2). A delivery also refuses rows not released (`demand_supply_not_released`) or on hold (`demand_on_hold`).
Source: ADR-0023.R16.N1

### Replenishment, counting and returns

R631. Replenishment uses `bin_item`: one pick face per item per warehouse, with `minimum_quantity` and `maximum_quantity`. A replenishment task is created when a pick task's creation would take the face below its minimum (`EC-38`), and by the daily job in the second slice, with at most one open task per `bin_item`.
Source: ADR-0023.R17

R632. A count task covers bins or items. While a count task is open, its bins are blocked for putaway, picking and replenishment. The block is derived from the open task, never written into the manual block flags. In a warehouse that is not bin-managed, count tasks cover items and no bin block applies (ADR-0031.R10).
Source: ADR-0023.R18

R633. Counts are blind by default. Serial items are counted by scanning serials. Counted quantities may be entered in the product's counting units, several lines per key, each converted and summed in the inventory unit (ADR-0056.R15).
Source: ADR-0023.R18, ADR-0023.R18.N1

R634. Confirming the count task creates a `draft` `stock_count` (ADR-0020.R18) with one line per counted entry (bin, lot or serial and status), and the block lifts. The book quantity at confirmation is stored on each line of a key beside the counted quantity, and a key with no line posts nothing (ADR-0075.R3). Posting posts counted minus that stored book quantity, so picks and putaways after confirmation never become count differences (`EC-36`). It posts through its normal lifecycle, with policy and approval (ADR-0009.R11, ADR-0009.R13); a scan never posts a count difference.
Source: ADR-0023.R18, ADR-0023.R18.N2

R635. A shortage in one bin and a surplus of the same item and lot in another are either netted per (item, warehouse, lot), with the bins corrected by warehouse movements, or posted gross. This is the required regime setting `stock_count.bin_difference_method` (bounds `net`, `gross`) with no core default (ADR-0075.R15).
Source: ADR-0023.R18, ADR-0023.R18.N3

R636. Cycle-count plans (second slice) are company data; an agent proposes them.
Source: ADR-0023.R18

R637. Returns arrive in a `returns` bin as `blocked` (ADR-0023.R7). A disposition creates a `status_change` task to restock (then putaway) or to quality, or a draft scrap document (`EC-39`). For products with the point `customer_return`, the disposition is the inspection lot's usage decision: `release` restocks, and `scrap` and `rework` create drafts (ADR-0070.R8, ADR-0070.R12). The return's value follows ADR-0020.R5.
Source: ADR-0023.R19, ADR-0023.R19.N1

### Warehouse commands, exceptions, printing and queries

R638. Putaway, pick and replenishment tasks are created by the system through `inventory.contract.create_warehouse_task`. A person or an agent draft creates `move`, `status_change` and `count` tasks with the command `CreateWarehouseTask`. Task handling: `AssignWarehouseTask` (the Assign verb is widened to warehouse tasks); `StartWarehouseTask`, which sets `in_progress`; `ConfirmWarehouseTask`; `CancelWarehouseTask`. Other commands: `PackHandlingUnit`, `UnpackHandlingUnit`, `RunPickRelease`, `CreateDelivery`, `PostDelivery`; there is no `ConvertWarehouse` (ADR-0031.R9). The verbs Pack, Unpack, Start and Convert are in the glossary, and Cancel is widened to tasks.
Source: ADR-0023.R20

R639. Warehouse events: `WarehouseTaskCreated`, `WarehouseTaskConfirmed` (with a shortage flag), `WarehouseTaskCanceled`, `StockReservationCreated`, `StockReservationCanceled`.
Source: ADR-0023.R20

R640. A short pick, a putaway without a target and a reservation canceled by a physical fact are exceptions. From step 5 each becomes one work item (DS-29; ADR-0031.R16) of kind `short_pick`, `putaway_without_target` or `reservation_canceled` (ADR-0042.R18). Before step 5 they are tasks without assignee and are listed by `ListWarehouseTask`.
Source: ADR-0023.R21

R641. Agents read through the query layer (DS-33) and act only through draft commands: putaway rules, minimums and maximums, count plans, exception resolution. Agent changes to putaway rules, pick-face levels and count plans go through change proposals (ADR-0029.R5). Slotting proposals come after Phase 1. The warehouse agent is a later agent (ADR-0051.R29).
Source: ADR-0023.R21

R642. Printing (DS-27) covers bin labels, handling-unit labels, putaway and pick lists on paper, and confirmation from a desktop screen, so warehouses without phones work from step 5. Labels and lists are print subjects over registered queries; the print contract, the worker and their templates come at step 5, interim until the author decides the build order (ADR-0049.R25, ADR-0049.R30). The PWA (DS-31) comes at step 9; offline scanning after Phase 1.
Source: ADR-0023.R22, ADR-0023.R22.N1

R643. Label subjects also cover item units, lots and serials (`ListItemLabel`, `ListLotLabel`, `ListSerialLabel`), with Code 128 for bins and documents, GS1-128 with (00) for handling units that carry an SSCC, and GS1 DataMatrix for item units, lots and serials that have a GTIN; barcoded document prints carry `document.barcode`. ZPL and a print agent come after Phase 1 (ADR-0061.R20, ADR-0061.R21, ADR-0061.R25).
Source: ADR-0023.R22.N2

R644. Warehouse queries and reports (DS-33): `GetStockBalance`, extended by bin, status and handling unit; `GetAvailableToPromise`; `ListWarehouseTask`; `GetHandlingUnit`; `GetPutawayPreview`; stock by bin and status, near-expiry stock, open tasks, count accuracy. Stock by bin and status and near-expiry stock read the view `stock_overview`; `warehouse_task_overview` and `count_accuracy` are added with the warehouse step (ADR-0050.R51).
Source: ADR-0023.R23

R645. Placement in the build steps (the runbook and spec 11 are the author's documents to amend): step 2: zones, bins, handling unit types, storage conditions, product and customer fields, putaway rules, `bin_item`; step 3: stock key, statuses, handling units, warehouse movements and tasks (putaway, pick, move, status change, count), removal strategies, reservations and available to promise, pick release, the replenishment trigger, counts by bin, transfers with bins, returns disposition; step 5: deliveries from picks, packing, printing, then the second slice: pick batches and waves, the replenishment job, cycle-count plans, staged flow; step 9: PWA flows. Slotting, cross-docking, dock appointments and labor management come later. Putaway, picking, short pick and count flows join the step 3 gate (the gate text in spec 11 and the runbook is the author's). Whether the step 4 gate and DS-17's simulator cover warehouse work is an open question.
Source: ADR-0023.R24, ADR-0023.R13.N3

### Demand and supply lines

R646. Open demand and supply lines are a read model owned by `inventory`, so planning in layer 4 reads it through `inventory.contract` (ADR-0022.R2, ADR-0022.R4). Its rows are never rebuilt, unique per source line and direction, and closed with `closed_reason`; execution tables refer to them (ADR-0028.R2). Supply rows of draft purchase lines without `origin_planned_order_id` or pegging are deleted with the line; all other rows are closed, never deleted (ADR-0047.R10).
Source: ADR-0024.R8

R647. `demand_supply_line` holds item, warehouse, `direction` (`demand` or `supply`), `open_quantity` in the inventory unit, `requested_date`, `ordered_date` (supply), `source_kind`, the source document line, `origin_planned_order_id` and `closed_reason` (`fulfilled`, `canceled`). `transfer_order_line` exists, so `demand_supply_line.transfer_order_line_id` has its foreign key; a transfer order line is demand at the source and supply at the destination, and stock transfers fulfil it (ADR-0075.R14).
Source: ADR-0024.R8, ADR-0024.R8.N2

R648. DS-22 documents write `demand_supply_line` through posting interfaces in their own transactions, as they do reservations (R608). A purchase request line's open quantity falls by what is ordered from it (a requirement on DS-22), so a request and its order are never counted twice. Planning reads only `inventory.contract`; it never imports `purchasing` or `sales`.
Source: ADR-0024.R8

R649. Which document types and states count as demand and supply is business behavior (open question). Interim, flagged: demand is sales order lines in states after `draft` (confirmed orders, not quotations) and transfer order lines at the source; supply is purchase order lines in any state but `canceled`, drafts included, purchase request lines, and transfer order lines at the destination, including goods in a `transit` warehouse.
Source: ADR-0024.R8

R650. Production orders count from `Create`: components as demand, outputs as supply, through typed columns `production_order_component_id` and `production_order_output_id`; reopening an order clears `closed_reason` and restores open quantity (ADR-0034.R6, ADR-0034.R9). The rows of a production order's components and outputs carry the hold reason `not_approved` until the order is approved (released), like sales and purchase rows (ADR-0047.R18). Make-to-order netting and planning count only released rows as demand; supply rows count once planned, held or not.
Source: ADR-0024.R8, ADR-0024.R8.N1

R651. Converted planned orders count as supply for the quantity not yet matched by open supply lines carrying their `origin_planned_order_id`; converted production planned orders count nothing (ADR-0036.R8). Firmed planned orders, and proposed ones frozen inside the firm fence, count as supply at their `need_date`; for `reorder_point` and `min_max` they are part of the inventory position.
Source: ADR-0024.R8

R652. Demand or supply dated before the planning date counts at the planning date (interim, flagged).
Source: ADR-0024.R8

### Conversion of planned orders

R653. `ConvertPlannedOrder` takes firmed or proposed planned orders. Purchase orders are grouped by supplier, warehouse, and release date within `conversion_window_days`; transfer orders by route. Production planned orders convert through `production.contract` (ADR-0036.R8). A planned order converts whole; a split is two `UpdatePlannedOrder` calls in Phase 1.
Source: ADR-0024.R22

R654. The command sets `converted` and calls the posting interface `inventory.contract.request_replenishment`, which writes one `replenishment_request` with a `replenishment_request_line` per planned order (carrying `origin_planned_order_id`) and emits `ReplenishmentRequested` from `inventory`, so every importer imports downward (ADR-0022.R2). The replenishment request line and the drafted purchase request line carry the planned order's order unit and snapshot; a purchase order copied from a request keeps the request's unit unless the person changes it (ADR-0056.R14).
Source: ADR-0024.R22, ADR-0024.R22.N1

R655. The `purchasing` consumer of `ReplenishmentRequested` groups the request's purchase lines by supplier, warehouse and release window into draft purchase requests (interim, flagged: the default target, following spec 09's request to order chain). `inventory` creates the draft transfer orders itself. Drafts are created as actor `system` on behalf of the converter, follow their own approval (DS-28), and carry `origin_planned_order_id` (`INV-62`). Service lines for external operations are drafted the same way, from the production order's approval event (ADR-0037.R4).
Source: ADR-0024.R22

R656. When the document lines of a converted order close with `closed_reason` `canceled` (R646), the next run sets it `canceled` and may propose again.
Source: ADR-0024.R22

R657. Converting under a value threshold by policy is an open question (DS-28). Sending to a supplier always stays a separate approved step. For agents, `UpdatePlannedOrder`, `FirmPlannedOrder` and `ConvertPlannedOrder` are proposal-bound for every order type (ADR-0036.R12).
Source: ADR-0024.R22

### Later-phase seams and the costing graph

R658. `journal_line` has the nullable dimensions `cost_object_id` and `fixed_asset_id` (a new dimension is a nullable column added by ADR, ADR-0014.R9). `material_document_line` has a nullable `cost_object_id`, for consumption into a cost collector and output from it. These columns stay empty and out of command schemas until their phase.
Source: ADR-0025.R1

R659. The exact solve of ADR-0020.R12 uses typed nodes and edges. Stock nodes are (item, valuation area) (ADR-0020.R2); cost-object nodes are production orders and cost pools (ADR-0035.R1, ADR-0035.R6). Edges are the period's value flows: transfers, and consumption into a cost object and output from it.
Source: ADR-0025.R6

R660. The solver works through the strongly connected components in topological order, each as one exact rational linear system. A singular component keeps the preliminary price for its nodes under ADR-0020.R13; other components are solved normally. Multi-level bills of materials, by-products and rework cycles use the same solver with their node and edge kinds. The step 3 algorithm spec implements this formulation, and the naive recomputation (DS-16 rule 29) uses the same nodes.
Source: ADR-0025.R6

R661. Planning (ADR-0024.R16) shares item and warehouse identities and the bill of materials with costing, but not a data structure: its graph is master-data routes and must be acyclic; the costing graph is actual flows and may have cycles. Costing adjustment lines that offset to WIP through the `consumption` key carry the original line's `cost_object_id`.
Source: ADR-0025.R6

R662. Enumeration values of price control are text with a check (ADR-0004.R14), so further methods are cheap to add. The list of methods (standard, moving average, FIFO, specific identification) stays open and is an accounting choice for later. `price_control` cannot change once a product has stock postings (ADR-0018.R18); a later ADR may allow a dated change at the start of a period after close, amending that rule.
Source: ADR-0025.R7

### Stock document types, read models and lock order

R663. The step 3 stock document types are owned by `inventory`; their fields and reversibility flags (ADR-0009.R19) are written in ADR-0075.R1 to ADR-0075.R6 and ADR-0075.R11 to ADR-0075.R14, with the link from `transfer_order` to `stock_transfer` as `stock_transfer_line.transfer_order_line_id` (one step, or two through transit). Posting types: `goods_receipt`, `delivery`, `stock_transfer`, `stock_count`; `internal_consumption`, `other_receipt`, `other_issue`, `scrap`; `return_to_supplier`, `return_from_customer`; `opening_balance`, matching the movement type of the same name. Non-posting demand document: `transfer_order`. The non-posting `inspection_lot` is owned by `quality` (ADR-0070.R7); production documents by `production` (ADR-0034). Account opening balances use `opening_balance_entry` and open items `opening_open_item_entry`, owned by `imports` (ADR-0044.R7, ADR-0044.R8).
Source: ADR-0027.R7, ADR-0027.R7.N1, ADR-0027.R7.N2

R664. Lines of `goods_receipt` and `delivery` have nullable order-line reference columns (`purchase_order_line_id`, `sales_order_line_id`; typed line references, ADR-0028.R2); commercial documents at step 5 fill them, and the core table does not change (B3). Before step 5, `needs_reference` is satisfied by a free-text reference. The return stock documents carry `correction_of_id` on their `document` row to the receipt or delivery they correct (ADR-0009.R23), and their lines name the receipt or delivery line (`return_to_supplier_line.goods_receipt_line_id`, `return_from_customer_line.delivery_line_id`; ADR-0047.R7). The commercial correction types `purchase_return` and `sales_return` refer to them.
Source: ADR-0027.R7

R665. Read models and when they update: `stock_quantity` and `stock_value` in the posting transaction, through the stock lock helper; the open item cache (ADR-0026) in the posting transaction; `stock_reservation` and `demand_supply_line` in the document's transaction, through posting interfaces; numbering counters in the posting or approval transaction; `account_period_balance` when a period's `general` area is locked, open periods being computed from lines (ADR-0014.R18); work items, notifications, e-invoice intents, timeline entries and search indexes asynchronously, by outbox consumers; semantic views (DS-33) are views over these tables.
Source: ADR-0027.R9

R666. The complete lock order per command; within each class rows are locked in ascending ID unless stated. (1) Documents: the command's own, and the documents it refers to (the order a delivery fulfills, the receipt a landed cost targets, the original of a reversal or correction, the production order of a shop-floor document; ADR-0034.R19). (2) Period area state rows, share lock. (3) The planning state row (planning runs only), or the company's `production_structure` row (releases of bills of materials and routings, production version and production setting saves, deactivations; ADR-0033.R8), or the company's `configuration_state` row, locked by every activation, enable, rollback and demotion of a configuration artifact, so parallel activations cannot together form a cycle in the rule graph (ADR-0058.R15). (4) Warehouse task rows. (5) Handling unit rows, parent first. (6) `stock_value` rows, ascending by item and warehouse ID. (7) `stock_quantity` rows. (8) Bin rows. (9) Partner rows (credit check, DS-22). Then `money_account_balance` rows (ADR-0048.R12), a class of their own in ascending ID. (10) Open item rows; the ledger locks all of an entry's items before inserting any line. (11) Numbering counters. (12) `event_subject` rows.
Source: ADR-0027.R10, ADR-0027.R10.N1, ADR-0027.R10.N2

R667. The idempotency record is taken first (ADR-0008.R16) and held to commit. Account rows locked by the first-posting trigger (ADR-0014.R12) are taken in line order after the open items and before numbering counters; they are outside the helper's assertion, because they are locked once per account in its life. Work item claims run in their own transactions. For a command of an agent run bound to a work item, that item row follows `FOR KEY SHARE` (claims, assignments and lease expiry take it `FOR UPDATE`); work item rows raised by a command are the last class, in (`kind`, `open_key`) order (ADR-0042.R5, ADR-0042.R9). Exception: credit hold updates on other orders' demand rows, made inside a `sales` command that holds the partner lock, take no class 1 lock of those orders; a hold is a single flag that does not conflict with their other changes (ADR-0047.R18).
Source: ADR-0027.R10

## Invariants

Statements are those of `invariants.csv`.

| Invariant | Name | Check point | Statement | Protects |
| --- | --- | --- | --- | --- |
| `INV-54` | `reservations_within_available` | day | Open and picked reservations never exceed the available-status quantity per item and warehouse. | R608, R609 |
| `INV-57` | `reservations_match_demand` | day | Per demand line, the reserved amounts of open and picked reservations never exceed the line's open quantity. | R607, R612 |
| `INV-62` | `converted_order_keeps_origin` | day | Every document line created from a converted planned order carries its `origin_planned_order_id`, and every converted planned order has such a line or is canceled. | R654, R655 |
| `INV-63` | `demand_supply_matches_source` | day | Each `demand_supply_line` open quantity equals its source line's quantity minus fulfilled and closed quantities, recomputed from the referring documents. | R646-R648 |

Named by rules of this chunk, with their rows in other chunks: `INV-58` (R612).

## Edge cases

| Edge case | Name | Case | Outcome | Protects |
| --- | --- | --- | --- | --- |
| `EC-32` | `short_pick` | A pick confirmed with less than the task quantity; the bin is counted and the rest backordered. | `must_succeed` | R624 |
| `EC-33` | `putaway_without_free_bin` | A receipt whose putaway rules find no bin with capacity; the task has no target. | `must_succeed` | R606 |
| `EC-34` | `fefo_below_customer_minimum` | FEFO skips a near-expiry lot below the customer's minimum remaining shelf life. | `must_succeed` | R618 |
| `EC-36` | `count_during_picking` | Picks after a count confirmation and before its posting do not become count differences. | `must_succeed` | R634 |
| `EC-37` | `quality_release` | Goods received into quality inspection, released or blocked. | `must_succeed` | R603 |
| `EC-38` | `pick_face_replenishment` | A pick that takes a pick face below its minimum creates a replenishment task. | `must_succeed` | R631 |
| `EC-39` | `returns_disposition` | A customer return received blocked and disposed to restock, quality or scrap. | `must_succeed` | R637 |

Named by rules of this chunk, with their rows in another chunk: `EC-324` (R610), `EC-337` (R609).

## Settings

None: the setting `stock_count.bin_difference_method`, used by R635, has its row in the chunk that states ADR-0075.R15.

Reads: `sales.reserve_on_approval` (`sales`; ADR-0047), used by R620. It has no row in `settings.csv`. `conversion_window_days` (R653) is a planning parameter (`planning`).

## UI annotations

The source units of this chunk carry no floorplan, title, facet, field annotation or tile of ADR-0077. Work item kinds of `inventory` (`work-item-kinds.csv`):

| Kind | Subject table | Owner rule | Due rule | Resolution | Rule |
| --- | --- | --- | --- | --- | --- |
| `short_pick` | `warehouse_task` | `warehouse_role` | `same_day` | person | R640 |
| `putaway_without_target` | `warehouse_task` | `warehouse_role` | `same_day` | person | R640 |
| `reservation_canceled` | `stock_reservation` | `warehouse_role` | `same_day` | person | R640 |

## Conflicts

CONFLICT ADR-0023.R13: ADR-0023.R13.N3 confirms the reservation interim (no over-reservation, first come first served, newest reservation dropped on a stock loss), so the open question and the mark "interim, flagged" are not restated (R609, R610); production keeps the order of ADR-0064.R7.
CONFLICT ADR-0023.R13.N1: its cap "at most the target's unreserved open requirement" (2026-11-15) yields to the later ADR-0064.R24, which caps the transfer at max(0, unreserved open requirement − available to promise of the item in the target's issue warehouse), computed under the target order's lock (R613).
CONFLICT ADR-0023.R15.N1: the note governs confirmation scans: every scanned field is evaluated with `EvaluateBarcode` and refused with `scan_mismatch` or `scan_unresolved`, overrides being command fields with a reason (R626).
CONFLICT ADR-0023.R18: ADR-0023.R18.N3 and ADR-0075.R15 govern; `stock_count.bin_difference_method` is a required regime setting with no core default, so the seed `net` and its open question are not restated (R635).
CONFLICT ADR-0023.R20: the rule's own amendment citing ADR-0031.R9 governs; `ConvertWarehouse` is removed and is not listed as a command (R638).
CONFLICT ADR-0023.R24: ADR-0023.R13.N3 accepts the proposed Phase 1 feature list and its placement, and puts putaway, picking, short pick and count flows into the step 3 gate; only the step 4 gate and the simulator question stay open (R645).
CONFLICT ADR-0024.R8: the rule's closing paragraph citing ADR-0047.R10 governs "never deleted"; supply rows of draft purchase lines without origin or pegging are deleted with the line (R646).
CONFLICT ADR-0025.R6: the rule's own bullet citing ADR-0035.R1 and ADR-0035.R6 governs; cost-object nodes and their edges exist in Phase 1, so "Phase 2" is not restated for nodes, edges or the shared bill of materials (R659, R661).
CONFLICT ADR-0027.R7: ADR-0027.R7.N2 governs; the fields and reversibility flags are written in ADR-0075 instead of a pending deliverable, and the DDL of ADR-0047.R7 decides the return references (R663, R664).

## Proposed (not law)

None

## Trace

| Source | Where |
| --- | --- |
| ADR-0023.R11 | R601, R602, R603 |
| ADR-0023.R11.N1 | R603 |
| ADR-0023.R12 | R604, R605, R606 |
| ADR-0023.R13 | R607, R608, R609, R610, R611, R612 |
| ADR-0023.R13.N1 | R610, R613 |
| ADR-0023.R13.N2 | R614 |
| ADR-0023.R13.N3 | R609, R610, R629, R645 |
| ADR-0023.R14 | R615, R616, R617, R618, R619, R621 |
| ADR-0023.R14.N1 | R620 |
| ADR-0023.R14.N2 | R621 |
| ADR-0023.R15 | R622, R623, R624, R625 |
| ADR-0023.R15.N1 | R626 |
| ADR-0023.R16 | R627, R628, R629 |
| ADR-0023.R16.N1 | R630 |
| ADR-0023.R17 | R631 |
| ADR-0023.R18 | R632, R633, R634, R635, R636 |
| ADR-0023.R18.N1 | R633 |
| ADR-0023.R18.N2 | R634 |
| ADR-0023.R18.N3 | R635 |
| ADR-0023.R19 | R637 |
| ADR-0023.R19.N1 | R637 |
| ADR-0023.R20 | R638, R639 |
| ADR-0023.R21 | R640, R641 |
| ADR-0023.R22 | R642 |
| ADR-0023.R22.N1 | R642 |
| ADR-0023.R22.N2 | R643 |
| ADR-0023.R23 | R644 |
| ADR-0023.R24 | R645 |
| ADR-0024.R2 | ref: ADR-0024.R2 |
| ADR-0024.R2.N1 | ref: ADR-0024.R2.N1 |
| ADR-0024.R8 | R646, R647, R648, R649, R650, R651, R652 |
| ADR-0024.R8.N1 | R650 |
| ADR-0024.R8.N2 | R647 |
| ADR-0024.R22 | R653, R654, R655, R656, R657 |
| ADR-0024.R22.N1 | R654 |
| ADR-0025.R1 | R658 |
| ADR-0025.R6 | R659, R660, R661 |
| ADR-0025.R7 | R662 |
| ADR-0027.R7 | R663, R664 |
| ADR-0027.R7.N1 | R663 |
| ADR-0027.R7.N2 | R663 |
| ADR-0027.R9 | R665 |
| ADR-0027.R10 | R666, R667 |
| ADR-0027.R10.N1 | R666 |
| ADR-0027.R10.N2 | R666 |
