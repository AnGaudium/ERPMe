# ADR-0023: Warehouse management

Status: accepted (2026-11-14) under ADR-0005, reviewed by Claude Fable 5.2 (builder Claude Opus 5.5). Design item: DS-42 (new). Related decisions: D2, D5, D14. Principles 2, 5, 6, 8, 9, 10, 12, 13. Build principles B1, B3, B7. ADR-0004, ADR-0005, ADR-0006, ADR-0007, ADR-0008, ADR-0009, ADR-0013, ADR-0016, ADR-0017, ADR-0018, ADR-0019, ADR-0020, ADR-0022, DS-16, DS-17, DS-29.

Note: the author keeps the full warehouse list in Phase 1, with no cut ([ADR-0032](0032-phase-1-scope-with-production.md)).

## Decision

On 2026-11-14 the author decided that warehouse management is part of Phase 1: for a trading business it decides whether orders ship on time and stock can be trusted. Earlier scope had bins after Phase 1. The feature list below is the agent's proposal, pending the author's confirmation (open question).

**Two levels on one stock table.** Both levels change `stock_quantity`, whose key gains bin, stock status and handling unit, so they cannot drift apart:
- **Inventory level:** what the books see. Material documents (ADR-0020) move quantity and value per item, warehouse, lot or serial and status.
- **Warehouse level:** where the goods physically are. Warehouse movements move quantity between bins, statuses and handling units inside one warehouse. They carry no value and post no journal.

Each level keeps its own rule for time:
- the books check stock per (item, warehouse, lot or serial) at the end of every date from the posting date on (ADR-0020 rule 10);
- physical places are checked on their current balance only, because where goods are is a fact of now.

**Data-driven, deterministic execution.**
- Putaway and removal strategies are rule tables.
- Tasks are written by code in the same transaction as the document that causes them.
- Every scan is an ordinary command with an idempotency key.
- Agents propose rule changes, count plans and exception resolutions as drafts; code executes them (Principles 2, 12).
- Exceptions become work items (Principle 8). Routine tasks stay in their own high-volume table.

**Two operating modes.**
- A warehouse without bins keeps working as in ADR-0020.
- A warehouse with bins chooses its flow: direct (receive to a shelf, pick straight into the goods issue) or staged (receiving bin, putaway, staging, packing).

A small shop and a managed distribution warehouse run on the same model.

**Phase 1, proposed:**
- core at step 3: bins and zones, stock statuses, handling units (one nesting level), putaway (`fixed_bin`, `nearest_free`), reservations and available to promise, removal by FEFO or FIFO, counts by bin, returns disposition, transfers with bins;
- pick release from demand lines at step 3; documents at step 5: partial deliveries from confirmed picks, packing, printing of labels and lists; a second slice after the first is proven: pick batches and waves, the replenishment job, cycle-count plans, the `consolidate` and `empty_bin` putaway methods, and the `staged` flow with `staging` and `packing` bins.

**Later:**
- slotting optimization by an agent;
- cross-docking;
- dock and yard appointments;
- labor management;
- value-added services and kitting (Phase 2; kits as bills of materials are now Phase 1 in DS-51, [ADR-0032](0032-phase-1-scope-with-production.md));
- SSCC labels with carrier integration;
- deeper nesting of handling units.

### Rules

**Structure**

1. A warehouse (ADR-0020 rule 1) gets:
   - `is_bin_managed`, default false, set before its first posting;
   - for bin-managed warehouses, `outbound_flow` (`direct`; `staged` in the second slice), `default_receiving_bin_id` and `default_shipping_bin_id`;
   - `is_handling_unit_managed`.

   A plain warehouse may become bin-managed once, by `ConvertWarehouse` with `is_bin_managed: true` (`human_only`). It moves every stock row to a chosen bin by warehouse movements in one transaction. The reverse is not supported. Superseded: every warehouse has a default bin, `UpdateWarehouse` sets `is_bin_managed` on physical warehouses, and `ConvertWarehouse` is removed ([ADR-0031](0031-design-simplifications.md) rules 7–9).

   Only `physical` warehouses manage bins. In `transit` and `goods_sent` warehouses stock rows have no bin, and handling units travel with their content and a null bin (rule 6). Stock there is always `available`. Superseded: such warehouses use their default bin, never a null one ([ADR-0031](0031-design-simplifications.md) rule 8).

   | Feature | Plain warehouse | Bin-managed warehouse |
   | --- | --- | --- |
   | Stock status and `is_inspection_required` | Yes | Yes |
   | Reservations; `status_change` and `count` tasks (in plain warehouses count tasks cover items and `status_change` uses the default bin, [ADR-0031](0031-design-simplifications.md)) | Yes | Yes |
   | Handling units | Yes | Yes |
   | Bins, putaway and removal strategies, putaway, pick, move and replenishment tasks | No | Yes |

2. Zones and bins:
   - A `zone` (`warehouse_id`, `code`, `name`) groups bins.
   - A `bin` holds:

     | Field | Content |
     | --- | --- |
     | `warehouse_id`, `zone_id` | Where it is |
     | `code` | Unique in the warehouse; its segments are informational |
     | `barcode` | Unique in the company, so a scan resolves without the warehouse; default: the code |
     | `bin_type` | `receiving`, `storage`, `picking`, `shipping`, `quality`, `returns`, `damage`; `production` (work-center supply and output bins, never read by pick removal, [ADR-0034](0034-production-orders-and-shop-floor.md) rule 10); `staging` and `packing` in the second slice |
     | `pick_sequence` | |
     | Capacity | Optional `maximum_weight` (kg, gross), `maximum_volume` (m³), `maximum_handling_units` |
     | Booleans | `is_mixed_item_allowed`, `is_mixed_lot_allowed`, `is_blocked_for_putaway`, `is_blocked_for_picking` (manual blocks only), `is_active` |

   - Bins are created and changed in batches (ADR-0008). A bin with stock cannot be deactivated (`bin_not_empty`). Every warehouse also has a default zone and a default bin (code `DEFAULT`, barcode `<warehouse code>-DEFAULT`), which cannot be deactivated while the warehouse is not bin-managed ([ADR-0031](0031-design-simplifications.md) rule 7).
3. Product and partner fields:
   - The product (ADR-0018 rule 3) gets:
     - `is_inspection_required`;
     - `removal_strategy` (`fefo`, `fifo`, or none for the warehouse default);
     - `storage_condition_id` (company data: ambient, cold, hazardous);
     - `default_handling_unit_type_id`.
   - The customer profile (ADR-0019) gets `minimum_remaining_shelf_life_days`.

   Whether shelf life may instead be a share of total shelf life, and whether expired lots may ever be picked, are open questions. The interim rules, flagged: days; expired lots are never picked.

**Stock key, statuses, handling units**

4. The stock key:
   - **Key.** `stock_quantity`'s key is (company, item, warehouse, bin, lot or serial, `stock_status`, `handling_unit_id`), plus the reserved `owner_partner_id` ([ADR-0030](0030-commercial-seams-and-imports.md) rule 8).
   - **Bin.** Every row of a bin-managed warehouse has a bin; no row of another warehouse has one. Superseded: every row has a bin, the default bin outside bin-managed warehouses ([ADR-0031](0031-design-simplifications.md) rule 8).
   - **Stock status.** `stock_status` is a classification, not a lifecycle state: `available`, `quality_inspection` or `blocked`.
   - **No value.** Statuses, bins and handling units carry no value. `stock_value` stays per (item, warehouse), and inventory accounts are unchanged (ADR-0020 rule 8).
   - **Presentation.** Whether a regime wants quality or blocked stock presented apart is an open question; none is known for TT99.
   - **Status axis.** This axis replaces the "stock types" option that ADR-0020 rejected. ADR-0020's objection, a second axis in every stock query, is answered by queries that group by (item, warehouse) unless they ask for more.
5. Negative stock:
   - The dated end-of-day check of ADR-0020 rule 10 stays at (item, warehouse, lot or serial), summed over bins, statuses and handling units, unchanged.
   - Every full key is checked on its current balance only: no bin, status or handling unit goes below zero now.
   - A backdated document names where the goods are now. Its dated check still runs at the inventory level.
   - Bin-level `GetStockBalance` has no `as_of`.
   - The negative-stock open question is extended to this split. The dated check uses the algorithm of [ADR-0031](0031-design-simplifications.md) rule 14.
6. Handling units:
   - **Fields.** A `handling_unit` holds `code` and `barcode` (unique in the company), `handling_unit_type_id` (company data: pallet, carton or tote, with tare weight and dimensions), `parent_handling_unit_id` (one level in Phase 1: a carton on a pallet), `warehouse_id`, `bin_id` (the default bin in `transit` and `goods_sent`, [ADR-0031](0031-design-simplifications.md) rule 8) and `state`.
   - **States.** `open`: content may change. `closed`: content changes only by `UnpackHandlingUnit`. `shipped`: set by the goods issue.
   - **Location.** The unit's row is authoritative for an empty unit. For a unit with content, the unit, its stock rows and its children are in one bin (DS-16).
   - **Moves.** Scanning a unit moves all its content in one task.
   - **Partial picks.** A partial pick from a unit takes the quantity out into no unit or into a new one.
   - **Statuses.** Content may mix statuses.
   - **Returns.** A returned unit is received as a new unit.
   - **Packing.** `PackHandlingUnit` and `UnpackHandlingUnit` are warehouse movements.

**Movements**

7. Inventory-level movements are material documents (ADR-0020), with `bin_id`, `stock_status` and `handling_unit_id` filled in on their lines where managed. Per movement type (the production types: [ADR-0034](0034-production-orders-and-shop-floor.md) rules 11 and 13):

   | Movement types | Source or target bin | Allowed statuses | Task created |
   | --- | --- | --- | --- |
   | `purchase_receipt`, `other_receipt` | The line's bin, or the default receiving bin | `quality_inspection` if required, else `available` | Putaway, unless the line names a `storage` or `picking` bin |
   | `sales_return_receipt` | A `returns` bin | `blocked` | Disposition (rule 19), then putaway if restocked |
   | `opening_balance` | The final bin named in the import (DS-21) | Any | None |
   | `sales_issue`, `transfer_out` | The non-pickable bin the confirmed picks moved the goods to: the default shipping bin (direct flow) or a `staging` or `shipping` bin (staged flow); in a plain warehouse, its default bin ([ADR-0031](0031-design-simplifications.md)) | `available` | Pick tasks precede it (rules 14–15) in bin-managed warehouses |
   | `purchase_return`, `scrap`, `other_issue`, `internal_consumption` | The line's bin | Any (rejected goods are mostly `blocked`) | None |
   | `transfer_in` | Default receiving bin | `available` | Putaway |
   | `stock_count_shortage`, `stock_count_surplus` | The counted bin | The counted status | None |

   Transfers have two forms:
   - between two bin-managed warehouses: a source bin on `transfer_out` and a receiving bin on `transfer_in`;
   - through a `transit` warehouse: two steps, with the handling unit keeping its identity.

   Dispatch to a customer may be a `sales_issue`, or a `transfer_out` to a `goods_sent` warehouse (ADR-0020 rule 4).
8. Warehouse movements:
   - **Lines.** `warehouse_movement` lines are written by confirmed tasks and by the pack and unpack commands. Each line holds item, lot or serial, quantity in the inventory unit, from and to bin, status and handling unit (inside one warehouse), `business_date` (`clock.today`, for history only), and its source: `warehouse_task_id`, or the pack, unpack or count-correction command that wrote it. They also carry the reserved `owner_partner_id` ([ADR-0030](0030-commercial-seams-and-imports.md) rule 8).
   - **Properties.** They are append-only and post no journal. Per (item, warehouse, lot or serial) their quantities net to zero (DS-16).
   - **Stock.** `stock_quantity` per full key equals material lines plus warehouse movements. Both are written through the stock lock helper.
   - **In the plan.** Warehouse movements are stock movements in a plan (ADR-0008 rule 12).
9. Reversal of a material document with bins (ADR-0020 rule 7; ADR-0009 rule 18):
   - It posts to the original lines' bins, statuses and handling units. It is refused with `negative_stock` when the stock is no longer there; the error's fix says to move it back with a move task first.
   - It cancels the original's open tasks in the same transaction.
   - It is refused with `invalid_state_transition` while a task of the original is `in_progress`.
   - A reversal that takes stock out counts as a voluntary issue for `stock_reserved` (rule 13).
10. Lock order (superseded by the complete order of [ADR-0027](0027-cross-cutting-ownership.md) rule 10; partner and open item rows follow bin rows, [ADR-0026](0026-open-item-core.md) rule 14). This extends ADR-0022 rule 10 (its full order with warehouse management), per command:
    1. period area state rows, share lock;
    2. the warehouse task row;
    3. handling unit rows, parent first, ascending ID;
    4. `stock_value` rows, ascending by item and warehouse ID;
    5. `stock_quantity` rows;
    6. bin rows, ascending ID, for capacity, mix and count checks;
    7. numbering counters;
    8. `event_subject` rows.

    Reservation writes take the `stock_value` row like postings, so reservations are serialized with the stock they hold. The cost is that moves of one item in one warehouse are serialized. PAR tests are added (DS-16):
    - two putaways of different items into the last free bin;
    - a handling-unit move against a pick from that unit;
    - two confirmations of one task.

    Expected outcomes: PAR-06, the second putaway proposal is computed under the bin lock and goes to another bin or none; PAR-07, one command succeeds and the other fails with `handling_unit_mismatch`; PAR-08, exactly one confirmation writes movements and the other is a replay or `invalid_state_transition`. Throughput: PAR-09 (long profile) runs 8 concurrent confirmations of one item in different bins; a p95 above 1 s triggers the revisit line.

**Inbound**

11. Receipts:
    - A receipt posts to the bin rule 7 gives.
    - Tasks are written by the posting's own transaction through `inventory.contract.create_warehouse_task` (ADR-0022 rule 4): one task per (item, lot, handling unit, source bin) with quantity N. A handling unit is one task.
    - Every task proposal (putaway targets here, pick sources in rule 14) is listed in the plan like events, never in `plan_hash` (ADR-0013 rule 5), so concurrent warehouse work never causes `plan_hash_mismatch`. Check results that follow from proposals are not hashed either ([ADR-0040](0040-ui-architecture.md) rule 10).
    - Releasing from inspection is a `status_change` task to `available` or `blocked`.
12. Putaway rules are rows per warehouse, each with a unique `position`:
    - **Match** on item, product category, storage condition, status and handling unit type.
    - **Target** a zone or bin type, with a method:
      - `fixed_bin`: the item's `bin_item`;
      - `nearest_free`;
      - `consolidate` and `empty_bin`, in the second slice.
    - **Winner.** Each method picks the lowest `pick_sequence`, then bin code, among bins that pass:
      - not blocked;
      - no open count;
      - mix rules;
      - capacity, counting the open tasks arriving at the bin.
    - **Capacity data.** Capacity uses the handling unit type's dimensions for a whole unit, or the item's gross weight and dimensions (ADR-0018 rule 4). When data is missing, the bin is accepted with the check result `capacity_not_checked`.
    - **Hard and soft limits.** Capacity and mix rules are hard when the system proposes a bin. At confirmation, a worker's different target bin that breaks them gives the check results `bin_capacity_exceeded` or `mixed_stock_not_allowed` and still records the fact.
    - **No bin found.** The task is created without a target and becomes an exception (rule 21).
    - **Preview.** The query `GetPutawayPreview` shows the targets a draft rule set would choose for given stock.

**Reservations and availability**

13. Reservations:
    - **Rows.** A `stock_reservation` holds stock for a demand line (a sales order or transfer order line; production later): item, warehouse, quantity, optional lot (by agreement), `picked_quantity`, `fulfilled_quantity` and `state` (`open`, `picked`, `fulfilled` when fulfilled equals quantity, `canceled`). Its reserved amount is quantity minus `fulfilled_quantity`. It never names a serial. The demand line is referred to by `demand_supply_line_id` ([ADR-0028](0028-document-lifecycle-hardening.md) rule 2). Reservations and tasks also carry the reserved `owner_partner_id` ([ADR-0030](0030-commercial-seams-and-imports.md) rule 8).
    - **Interfaces.** `inventory.contract.create_stock_reservation` and `cancel_stock_reservation` are posting interfaces called by document commands (DS-22), which emit the reservation events; they are not user commands. Available to promise per (item, warehouse) is `available` quantity minus the reserved amounts of reservations in `open` or `picked`. `GetAvailableToPromise` answers it from on-hand stock only in Phase 1. Available stock still in a receiving bin counts, so a pick release before putaway may be short; that is expected.
    - **Limits.** A reservation never exceeds available to promise (`reservation_exceeds_available`); the unreserved rest of a demand line is a backorder.
    - **Voluntary issues.** Scrap, internal consumption, other issues, purchase returns, transfers, reversals and `status_change` to `blocked` are rejected with `stock_reserved` when they would cut into reservations.
    - **Physical facts.** Count shortages and blocking found damage always post, then cancel reservations deterministically, by the demand document's date, number and `line_number` descending, until the limit holds, and raise an exception.
    - **Author questions.** Which reservation loses, whether overbooking is allowed, and the priority among demands are open questions. Interim, flagged: newest loses, no overbooking, first come first served.
    - **Lots.** Availability is not lot-aware. A reservation whose lots fail shelf-life rules at pick time gives a short pick. Planning ignores reservations in netting and counts demand in full ([ADR-0024](0024-planning.md) rule 9).
    - **Build step.** Reservations, the check and the posting interfaces are step 3 core; documents call them at step 5. Production orders reserve components at release, passing `destination_bin_id` and `release_sequence` ([ADR-0034](0034-production-orders-and-shop-floor.md) rule 9). Picked and fulfilled quantities stay stored here, checked by INV-58; the open quantity of the demand line is stored in `demand_supply_line` ([ADR-0031](0031-design-simplifications.md) rules 5, 6).

**Picking and outbound**

14. Pick tasks:
    - **Creation.** Pick tasks serve demand lines, not deliveries. `RunPickRelease` (a deterministic job, per demand document, step 3) turns reservations into pick tasks. Each task carries the demand line's unit and the inventory quantity (ADR-0018 rule 11); the client derives a breakdown such as "2 cartons and 3 bottles" from `product_uom`. Tasks refer to `demand_supply_line_id` ([ADR-0028](0028-document-lifecycle-hardening.md) rule 2). `RunPickRelease` also serves production orders, moving components to the reservation's destination bin ([ADR-0034](0034-production-orders-and-shop-floor.md) rule 10). Creation takes the `stock_value` lock of each item and warehouse before reading available bin stock ([ADR-0030](0030-commercial-seams-and-imports.md) rule 12).
    - **Serial items.** Tasks name the bin, not the serial. The serials are scanned at confirmation and checked against bin and status (`serial_not_in_bin`).
    - **Removal order.** Removal reads only `storage` and `picking` bins with status `available`, minus the quantity of open tasks leaving each key. It orders by:
      1. lot: `fefo` by `expiry_date` (lots without one last), skipping lots below the customer's minimum remaining shelf life, with the planned delivery date as reference, or the business date when the line has none; `fifo` by the lot's earliest receipt posting date (FIFO needs lot tracking; untracked items use bin order);
      2. lot code;
      3. bin: `picking` before `storage`, and a whole handling unit when the quantity matches;
      4. `pick_sequence`;
      5. bin code;
      6. handling unit code.

      No database ID takes part (ADR-0006 rule 6).
    - **No stock.** When no eligible stock exists, the line is short: the command succeeds with the check result `no_pickable_stock`, and the shortage becomes an exception.
15. Confirming a task:
    - `ConfirmWarehouseTask` records the scanned source and target bins, the handling units, lot or serials, and the actual quantity, which may not exceed the task's (`task_quantity_exceeded`). A smaller quantity requires a `shortage_reason`. The scanned target may differ from the proposal (rule 12).
    - Every confirmed pick moves the goods to a non-pickable bin (rule 7), so no later release allocates them again.
    - A short confirmation creates a count task for the source bin, which blocks it until counted (rule 18), and an exception. The demand line keeps the unpicked rest, which the next `RunPickRelease` takes up.
    - What happens to the order after a short pick is an open question. Interim, flagged: ship what is picked, and leave the rest as backorder on the demand line.
    - Every scan carries a device idempotency key (ADR-0008); the PWA chains simulate and execute in one call sequence.
16. Deliveries are created from confirmed picks:
    - `CreateDelivery` takes the picked stock (lots, serials, bins, handling units) of one or more demand lines. The delivery never needs updating after approval (ADR-0009 rule 9), and a short pick simply yields a partial delivery.
    - In the `staged` flow, picks go to `staging`; packing closes handling units in `packing`; `PostDelivery` posts the goods issue from the `shipping` bin.
    - In the `direct` flow, `PostDelivery` issues from the default shipping bin the picks moved to.
    - In a plain warehouse there are no tasks: `CreateDelivery` takes stock from the warehouse's default bin ([ADR-0031](0031-design-simplifications.md)), and the reservation goes straight to `fulfilled` at `PostDelivery`.
    - Value and ownership change only at `PostDelivery` (ADR-0020).
    - Pick batches and waves (second slice) group the pick tasks of several demand documents, sorted by zone and `pick_sequence`. Each document is released as its own internal command, so locks stay small.
17. Replenishment uses `bin_item`: one pick face per item per warehouse, with `minimum_quantity` and `maximum_quantity`. A replenishment task is created when a pick task's creation would take the face below its minimum, and by the daily job in the second slice, with at most one open task per `bin_item`.

**Counting and returns**

18. Counting:
    - **Tasks.** A count task covers bins or items. While a count task is open, its bins are blocked for putaway, picking and replenishment. The block is derived from the open task, never written into the manual block flags. In a warehouse that is not bin-managed, count tasks cover items and no bin block applies ([ADR-0031](0031-design-simplifications.md) rule 10).
    - **Counting.** Counts are blind by default. Serial items are counted by scanning serials.
    - **Confirmation.** Confirming the task creates a `draft` `stock_count` (ADR-0020 rule 18) per bin, lot or serial and status, which stores the book quantity at confirmation beside the counted quantity, and the block lifts. Posting posts counted minus that stored book quantity, so picks and putaways after confirmation never become count differences. It posts through its normal lifecycle, with policy and approval (ADR-0009 rules 11, 13); a scan never posts a count difference.
    - **Bin differences.** A shortage in one bin and a surplus of the same item and lot in another are either netted per (item, warehouse, lot), with the bins corrected by warehouse movements, or posted gross. This is a required regime setting (`stock_count.bin_difference_method`), seeded unverified as `net` (open question).
    - **Plans.** Cycle-count plans (second slice) are company data; an agent proposes them.
19. Returns:
    - Returns arrive in a `returns` bin as `blocked` (rule 7).
    - A disposition creates a `status_change` task to restock (then putaway) or to quality, or a draft scrap document.
    - The return's value follows ADR-0020 rule 5.

**Commands, events, agents, printing**

20. Commands:
    - **Created by the system:** putaway, pick and replenishment tasks, through `inventory.contract.create_warehouse_task`.
    - **Created by a person or an agent draft:** the command `CreateWarehouseTask` for `move`, `status_change` and `count`.
    - **Task handling:** `AssignWarehouseTask` (the Assign verb is widened to warehouse tasks); `StartWarehouseTask`, which sets `in_progress`; `ConfirmWarehouseTask`; `CancelWarehouseTask`.
    - **Other commands:** `PackHandlingUnit`, `UnpackHandlingUnit`, `RunPickRelease`, `CreateDelivery`, `PostDelivery` (`ConvertWarehouse` removed, [ADR-0031](0031-design-simplifications.md)). The verbs Pack, Unpack, Start and Convert are added to the glossary, and Cancel is widened to tasks.
    - **Events:** `WarehouseTaskCreated`, `WarehouseTaskConfirmed` (with a shortage flag), `WarehouseTaskCanceled`, `StockReservationCreated`, `StockReservationCanceled`.
21. Exceptions become work items (DS-29) from step 5: a short pick, a putaway without a target, or a reservation canceled by a physical fact. Before step 5 they are tasks without assignee and are listed by `ListWarehouseTask`. Agents read through the query layer (DS-33) and act only through draft commands: putaway rules, minimums and maximums, count plans, exception resolution. Slotting proposals come after Phase 1. Agent changes to putaway rules, pick-face levels and count plans go through change proposals ([ADR-0029](0029-proposals-and-agent-safety.md) rule 5). From step 5, one work item per exception ([ADR-0031](0031-design-simplifications.md) rule 16). Kinds `short_pick`, `putaway_without_target`, `reservation_canceled` ([ADR-0042](0042-work-queue.md) rule 18).

    The warehouse agent is a later agent ([ADR-0051](0051-agent-workflows.md) rule 29).
22. Printing (DS-27) covers bin labels, handling-unit labels, putaway and pick lists on paper, and confirmation from a desktop screen, so warehouses without phones work from step 5. The PWA (DS-31) comes at step 9; offline scanning after Phase 1.
23. Queries and reports (DS-33):
    - `GetStockBalance`, extended by bin, status and handling unit;
    - `GetAvailableToPromise`;
    - `ListWarehouseTask`;
    - `GetHandlingUnit`;
    - `GetPutawayPreview`;
    - stock by bin and status, near-expiry stock, open tasks, count accuracy.

    Stock by bin and status and near-expiry stock read the view `stock_overview`; `warehouse_task_overview` and `count_accuracy` are added with the warehouse step ([ADR-0050](0050-agent-runtime-and-query-layer.md) rule 51).

**Build order**

24. Proposed placement in existing steps. The runbook and spec 11 are the author's documents to amend:

    | Step | Work |
    | --- | --- |
    | 2 | Zones, bins, handling unit types, storage conditions, product and customer fields, putaway rules, `bin_item` |
    | 3 | Stock key, statuses, handling units, warehouse movements and tasks (putaway, pick, move, status change, count), removal strategies, reservations and available to promise, pick release, the replenishment trigger, counts by bin, transfers with bins, returns disposition |
    | 5 | Deliveries from picks, packing, printing; then the second slice: pick batches and waves, the replenishment job, cycle-count plans, staged flow |
    | 9 | PWA flows |

    Whether the step 3 and step 4 gates and DS-17's simulator cover warehouse work is an open question.

## Context

- **Earlier scope.** "After Phase 1: bins" and "not doing: wave picking, slotting optimization" ([09](../spec/09-mvp-scope.md)). The author's decision of 2026-11-14 moves warehouse management into Phase 1.
- **ADR-0020.** It reserved `bin_id` and set one lock order and the dated negative-stock rule; ADR-0009 fixes what an approved document may change.
- **Practice studied, concepts only.** SAP EWM (warehouse tasks, bins, handling units, stock types, strategies), Business One (bins per warehouse, pick lists from orders), D365 (location directives, license plates, waves) and Odoo (putaway rules, packages, batch transfers).
- **ERPMe's own choices:**
  - one stock table with a dated book check and current physical checks;
  - picks from demand lines, so approved deliveries never change;
  - strategies as rule tables that agents can read and propose;
  - waves as scheduled batches;
  - every scan an idempotent command.

## Options considered

| Option | For | Against |
| --- | --- | --- |
| One stock table with bin, status and handling unit (chosen) | No reconciliation; one helper | Larger key; moves serialize per (item, warehouse) |
| Separate warehouse-level stock (SAP EWM) | Independent throughput | A second ledger to reconcile |
| Dated negative-stock check per bin | One rule | Backdating becomes impossible; places have no history worth checking |
| Picks from deliveries | Familiar | Writing picked lots onto an approved delivery voids its approval |
| Statuses as separate warehouses | No new axis | Transfers for every inspection; reports split |
| Bins mandatory everywhere | One mode | Burdens small shops |

## Constraints that come with the decision

- **Notes in other ADRs:**
  - ADR-0020: Decision paragraph; rules 3, 7, 8, 9, 10, 17, 18 (with the stored book quantity), 19; the rejected option.
  - ADR-0022: rule 10 (lock order, after its list) and rule 2 (warehouse tables live in `inventory`, with the stock helper).
  - ADR-0008 rule 12 (task proposals outside the plan hash).
  - ADR-0018 rule 3, ADR-0019.
  - The glossary verb table: Assign widened.
- **DS-04:**
  - errors `bin_required`, `bin_not_in_warehouse`, `warehouse_not_bin_managed`, `bin_blocked`, `bin_not_empty`, `bin_management_locked` (removed by [ADR-0031](0031-design-simplifications.md)), `stock_status_not_available`, `stock_reserved`, `reservation_exceeds_available`, `handling_unit_mismatch`, `handling_unit_closed`, `handling_unit_nesting_exceeded`, `task_quantity_exceeded`, `lot_shelf_life_too_short`, `serial_not_in_bin`;
  - check results `capacity_not_checked`, `bin_capacity_exceeded`, `mixed_stock_not_allowed`, `no_pickable_stock`;
  - `negative_stock` worded for both levels; `invalid_state_transition` covering tasks;
  - the canonical plan section: task proposals are never hashed (also ADR-0008 rule 12).
- **DS-16:**
  - INV-50 to INV-56 in a new warehouse group;
  - DS-16 rule 4 lists the group;
  - PAR-06 to PAR-09;
  - `warehouse` added to the `area` values of DS-16 rule 4.
- **DS-17:** edge cases EC-32 to EC-40 (short pick, putaway without a free bin, FEFO below a customer's minimum, handling unit split, count during picking, quality release, replenishment, returns disposition, transfer with bins).
- **Other design items:** DS-21 (opening balances per bin), DS-22, DS-27, DS-29, DS-31, DS-33.
- **Specs and the backlog:** spec 07, 09, 10 and 11 notes; backlog rows DS-20, DS-21, DS-31, DS-42.

## Revisit when

- p95 task-confirmation latency in the medium replay exceeds 1 s: give quantity-only moves their own lock level.
- A customer needs cross-docking, dock appointments or labor management.

## Documents updated

- **ADRs:** [docs/adr/0020-inventory-and-costing-model.md](0020-inventory-and-costing-model.md), [docs/adr/0022-repository-and-engineering-conventions.md](0022-repository-and-engineering-conventions.md), [docs/adr/0018-product-and-item-model.md](0018-product-and-item-model.md) and [docs/adr/0019-partners-and-crm-foundation.md](0019-partners-and-crm-foundation.md), with notes; [docs/adr/0014-universal-journal.md](0014-universal-journal.md), stale line.
- **Spec:**
  - [docs/spec/07-shared-foundation.md](../spec/07-shared-foundation.md), [docs/spec/09-mvp-scope.md](../spec/09-mvp-scope.md), [docs/spec/10-roadmap.md](../spec/10-roadmap.md) and [docs/spec/11-build-order.md](../spec/11-build-order.md): scope notes.
  - [docs/spec/00-reading-guide.md](../spec/00-reading-guide.md): glossary rows, the Assign verb, and `fefo` and `fifo` as abbreviations.
- **Design:**
  - [docs/design/DS-04-command-envelope.md](../design/DS-04-command-envelope.md): codes.
  - [docs/design/DS-16-invariants-and-harness.md](../design/DS-16-invariants-and-harness.md) and [docs/catalogs/invariants.csv](../catalogs/invariants.csv): new rows.
  - [docs/design/backlog.md](../design/backlog.md): rows.
- **Index:** [docs/adr/README.md](README.md).
- **Open questions** ([docs/open-questions.md](../open-questions.md)):
  - scope confirmation;
  - overbooking and priority;
  - which reservation loses;
  - short pick outcome;
  - netting count differences across bins;
  - expired lots and shelf-life basis;
  - presentation of quality and blocked stock;
  - gates and simulator coverage.
- **For the author:** runbook steps-0-4 line 104 and steps-5-9 line 147.
- [docs/runbook/step-log.md](../runbook/step-log.md): entry at acceptance.
