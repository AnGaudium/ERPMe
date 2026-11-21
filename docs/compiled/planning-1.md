Module: planning    Chunk: 1 of 2    Source ADRs: ADR-0024
Build step(s): 2, 5    Generated from index: 30d5706    Compiled by: Claude Fable 5.2, 2026-11-21

# `planning` compiled spec, chunk 1: parameters, read model, forecast, netting, runs, planned orders, exceptions, conversion

## Purpose

`planning` answers, per item and warehouse, what to buy or move, how much, and by when. This chunk states the law of ADR-0024 rules 1 to 22: planning parameters and supplier data, the demand and supply read model it reads, demand history and forecast, netting, lot sizing, the planning graph, the run, planned orders, pegging, action messages, exceptions and conversion. `planning` is in layer 4 and reads documents only through `inventory.contract`; it never imports `purchasing` or `sales`, and it sends and posts nothing (R1, R13). The planning agent, events, queries, performance, build placement and multi-level MRP (ADR-0036) are in chunk 2.

## Entities and tables

DDL: `docs/design/DS-43-54-planning-production.sql`.

| Table | Meaning | Key | Parent | Owner |
| --- | --- | --- | --- | --- |
| `item_warehouse_planning` | Planning parameters of one item in one warehouse (R4) | `id`; (`company_id`, `item_id`, `warehouse_id`) unique | `item`, `warehouse` | `planning` |
| `supplier_item` | Supplier terms per supplier and item (R6) | `id`; no overlap of validity per (`company_id`, `supplier_partner_id`, `item_id`) | `partner`, `item` | `planning` |
| `supplier_purchasing_term` | Terms per supplier partner (R7) | `id`; (`company_id`, `supplier_partner_id`) unique | `partner` | `planning` |
| `supplier_item_lead_time` | Measured lead times per supplier and item (R8) | `id`; (`company_id`, `supplier_partner_id`, `item_id`) unique | `partner`, `item` | `planning` |
| `transfer_route` | Route between two warehouses (R9) | `id`; (`company_id`, `source_warehouse_id`, `destination_warehouse_id`) unique | `company`, `warehouse` | `planning` |
| `planning_setting` | Planning settings of a company (R12) | `id`; `company_id` unique | `company` | `planning` |
| `planning_state` | The company's lock row of a run (R41) | `id`; `company_id` unique | `company` | `planning` |
| `planning_run` | One row per run (R52) | `id`; (`company_id`, `id`) | `company` | `planning` |
| `sales_history` | Imported weekly sales before the first posting (R24) | `id`; (`company_id`, `item_id`, `warehouse_id`, `iso_week`) unique | `item`, `warehouse` | `planning` |
| `demand_event` | Demand event of a company (R25) | `id`; (`company_id`, `code`) unique | `company` | `planning` |
| `demand_event_window` | An event's window of dates in one year (R25) | `id`; (`demand_event_id`, `start_date`) unique, no overlap per event | `demand_event` | `planning` |
| `forecast_run` | One row per `RunForecast` (R52) | `id`; (`company_id`, `id`) | `company` | `planning` |
| `forecast_line` | Statistical forecast per day (R52) | `id`; (`forecast_run_id`, `item_id`, `warehouse_id`, `forecast_date`) unique | `forecast_run` | `planning` |
| `forecast_adjustment` | Adjustment of the forecast over a date range (R32) | `id`; (`company_id`, `id`) | `item`, `warehouse` | `planning` |
| `planned_order` | Proposal to buy, move or make (R44) | `id`; business key of R44 unique | `item`, `warehouse`, `planning_run` | `planning` |
| `planned_order_pegging` | What a planned order covers (R48) | `id` | `planned_order` | `planning` |
| `planning_action_message` | Message on existing supply (R52) | `id` | `planning_run`, `demand_supply_line` | `planning` |
| `planning_exception` | Exception of a run (R52) | `id`; (`company_id`, `id`) | `planning_run` | `planning` |

`planned_order_component` and `planned_order_operation` are owned by `planning` too (R52); ADR-0036.R4 and ADR-0036.R5 define them, so their rows are in chunk 2. Chunk 2 lists the columns its rules add to the tables above.

Reads: `demand_supply_line`, `replenishment_request`, `transfer_order_line`, `preliminary_price` (`inventory`); `partner_item`, `item`, `warehouse`, `partner`, `uom`, `uom_conversion`, `company`, `currency` (`master_data`); `user_account`; `production_version`, `work_center`, `production_order` (`production`).

## Commands and queries

Authorization leaves of the area `planning` (catalog `authorization-areas.csv`): `planning_run`, `planned_order`, `forecast` and `supplier_item`. The level of a verb is the catalog's (`Run`: `post`; `Firm`, `Convert`, `Update`, `Cancel`, `Create`, `Import`: `edit`; `Get`: `read`). The supplier item commands, `CreateTransferRoute`, the list queries and the events of the module are in chunk 2 (ADR-0024.R23.N1, ADR-0024.R24); rules of chunk 2 extend `RunPlanning`, `UpdatePlannedOrder`, `FirmPlannedOrder` and `ConvertPlannedOrder` for production planned orders (ADR-0036).

| Name | Actor and authorization | Input | Effect | Events | Error codes |
| --- | --- | --- | --- | --- | --- |
| `RunPlanning` | a human, or the schedule on behalf of `planning_owner_id`; long job on the `jobs` queue; leaf `planning_run` | `planning_date`, `scope` | Nets demand and supply and writes planned orders, pegging, messages and exceptions (R40-R43) | `PlanningCompleted` | `planning_run_in_progress` |
| `RunForecast` | long job, as `RunPlanning`; area not stated | `planning_date` | Writes `forecast_run` and `forecast_line` and refreshes `supplier_item_lead_time` (R8, R28) | not stated | none stated |
| `ImportSalesHistory` | import batch in the DS-21 format; area not stated | item, warehouse, ISO week, quantity | Writes `sales_history` (R24) | not stated | none stated |
| `FirmPlannedOrder` | leaf `planned_order`; proposal-bound for agents | planned order | Sets `firmed` (R47) | not stated | `invalid_state_transition` |
| `UpdatePlannedOrder` | leaf `planned_order`; proposal-bound for agents | planned order, quantity or dates | Sets quantity or dates and firms (R47) | not stated | `invalid_state_transition` |
| `CancelPlannedOrder` | area not stated | planned order | Cancels a proposed or firmed order (R47) | not stated | `invalid_state_transition` |
| `ConvertPlannedOrder` | leaf `planned_order`; proposal-bound for agents | firmed or proposed planned orders | Sets `converted` and hands over a `replenishment_request` (R60, R61) | `ReplenishmentRequested`, from `inventory` | `invalid_state_transition` |
| `CreateForecastAdjustment` | leaf `forecast`; effect class `master_data_change` | item, warehouse, `start_date`, `end_date`, quantity or factor, reason | Writes `forecast_adjustment` (R32, R53) | not stated | none stated |
| `CancelForecastAdjustment` | leaf `forecast`; effect class `master_data_change` | adjustment | Cancels the adjustment (R53) | not stated | none stated |
| `GetProjectedAvailability` | query; area not stated | item, warehouse | Runs the netting read-only, without a plan (R23) | none | none stated |

Not registered commands: the posting interface `inventory.contract.request_replenishment` (R61); the consumer `planning_work_items` of `PlanningCompleted` (R49); the `purchasing` consumer of `ReplenishmentRequested` (R62). Writing planning parameters that form a cycle of transfer sources returns `planning_network_cycle` (R9). Check results of a run, not errors: `planning_parameter_missing`, `forecast_history_insufficient` (R42). A run never fails on `plan_hash_mismatch` (R42). `preliminary_price_missing` belongs to `inventory` (ADR-0020.R11.N2).

## Rules

### Scope and slices

R1. Planning is in Phase 1; multi-level MRP is designed in DS-54, and production, planned production orders, phantoms, scrap factors and co-products are Phase 1 too, designed in DS-51 and DS-54 (ADR-0032). One deterministic job nets open demand against supply over a graph of (item, warehouse) nodes linked by transfer routes and bills of materials. It writes planned orders with stable business keys. Each is pegged to the demand, safety stock or stock level it covers, which is its derivation trace (Principle 6). Exceptions become work items (R49). People, or policy, firm planned orders and convert them. Conversion emits an event, and the `purchasing` and `inventory` modules turn it into draft documents. Planning itself sends and posts nothing (Principle 12).
Source: ADR-0024.D0, ADR-0024.H.N1

R2. Agents explain proposals, consolidate them against supplier terms held as data, and draft parameter changes and forecast adjustments. Changes to master data need approval.
Source: ADR-0024.D0

R3. The slices of the module:
- First slice (step 5): reorder point and min/max; time-phased netting of real demand; transfer routes; the action messages `expedite` and `cancel`; a weekly forecast by moving average with seasonal and event indices.
- Later slice (step 5b, ADR-0024.R26.N2), once forecast accuracy is measured: exponential smoothing and Croston's method, chosen by backtest; service-level safety stock; the `postpone` and `reduce` messages.
- Bills of materials on the same graph are Phase 1, built with multi-level MRP in step 5b (ADR-0024.R26.N2).
Source: ADR-0024.D0, ADR-0024.H.N1

### Planning parameters and supplier data

R4. `item_warehouse_planning` holds the planning parameters for one item in one warehouse. An item without a row in a warehouse is not planned there; open demand on a node without a row raises `planning_parameter_missing` with reason `planning_row_missing` (R56). Its fields:
- Method: `planning_method`: `reorder_point`, `min_max` or `net_requirements`.
- Replenishment source: `replenishment_source`: `purchase`, `transfer` or `production` (ADR-0033.R14; phantoms are a production setting, not a source).
- Levels: `reorder_point`, `minimum_quantity`, `maximum_quantity`.
- Safety stock: `safety_stock_method` (`fixed`, or `service_level` in the later slice), `safety_stock_quantity`, `service_level_percent`.
- Lot size: `lot_size_method` (`exact`, `fixed` with `fixed_lot_quantity`, `supply_period` with `supply_period_days`).
- Fence and receiving: `firm_horizon_days`, `receiving_days` (receiving and inspection, on the warehouse's calendar).
- Strategy: `planning_strategy`: `make_to_stock` (default) or `make_to_order` (ADR-0036.R9).
Source: ADR-0024.R1, .N1

R5. `item_warehouse_planning` is master data. People with the permission change it directly. Changes proposed by agents are change proposals (ADR-0029.R5): they await approval (spec 14: an agent's change of master data requires approval) and carry their evidence. The table replaces the entry for it in the "deliberately elsewhere" list of ADR-0018.
Source: ADR-0024.R1

R6. `supplier_item` is keyed by (company, supplier partner, item), one row valid on any date. It is the only home of supplier minimums, multiples and preference. It may refer to the partner's own item code in `partner_item` (ADR-0019.R6). It holds:
- `supplier_processing_days` (counted on the supplier's calendar);
- `transit_days` (calendar days, because ships sail through holidays);
- `order_uom_id` (NOT NULL; the inventory unit or an active product unit; proposed from the product's purchase unit); a supplier with another pack size gets its own product unit, never a supplier factor (ADR-0056.R14, ADR-0056.R23);
- `minimum_order_quantity` and `order_multiple`, in `order_uom_id`;
- `is_preferred`: exactly one valid `supplier_item` per item may be preferred at a release date; none or several gives `planning_parameter_missing`;
- `start_date` and `end_date`.
Source: ADR-0024.R2, .N1

R7. `supplier_purchasing_term` (one row per supplier partner) holds `minimum_order_amount` with its `currency`, an optional `container_volume` and `container_weight`, and an optional `order_cycle_days`. Its `volume_uom_id` and `weight_uom_id` stay interim; item dimensions and weights convert to them through `uom_conversion` only (ADR-0056.R14, ADR-0056.R23).
Source: ADR-0024.R2, .N1

R8. `supplier_item_lead_time` stores measured lead times per (supplier, item), refreshed by the forecast job: mean and standard deviation (square root through `nativeflows.numeric`) of the days from the supply line's `ordered_date` to receipt, read from `demand_supply_line` (R14). They are visible data (spec 03 rule 9) and are never applied without approval.
Source: ADR-0024.R2

R9. `transfer_route` holds the source warehouse, the destination warehouse and `lead_time_days` (calendar days); the destination warehouse's `receiving_days` and calendar then apply, as for purchases. Between two warehouses of one site, `lead_time_days` may be omitted and is then 0. A `transfer` replenishment source names a route (`item_warehouse_planning.transfer_route_id`, a route that ends in the row's warehouse). Writing parameters that would form a cycle of transfer sources is rejected with `planning_network_cycle`. Planning stays per (item, warehouse); site-level pooled planning is an open question for after Phase 1.
Source: ADR-0024.R3, .N1

R10. Lead time and dates. The lead time of a purchase is `supplier_processing_days` on the supplier's calendar, then `transit_days` as calendar days, then `receiving_days` on the warehouse's calendar. The release date is the latest working day of the supplier's calendar from which the order still arrives by its `need_date`.
Source: ADR-0024.R5

R11. Every planning quantity is in the item's inventory unit (ADR-0018.R9). The supplier's minimum and multiple are applied in the supplier item's `order_uom_id`: the run converts the shortfall exactly into it, applies the minimum and the multiple rounding up, and converts the order quantity back half up, as the purchase order line will. The planned order stores `order_quantity`, `order_uom_id` and the snapshot beside `quantity` in the inventory unit (ADR-0056.R14). Rounding excess is shown on the proposal (`planned_order.rounding_excess_quantity`).
Source: ADR-0024.R6, .N1

R12. `planning_setting`, one row per company, holds:
- `planning_owner_id`: the human accountable for scheduled runs (spec 03 rule 3);
- `planning_horizon_days`;
- `forecast_consumption_days`;
- `conversion_window_days`;
- `backtest_weeks`;
- `conversion_lead_days` and `capacity_bucket` (ADR-0036.R4, ADR-0036.R11).
Source: ADR-0024.R7

### Demand and supply read model

R13. Open demand and supply lines are a read model owned by `inventory`, so planning in layer 4 can read it through `inventory.contract` (ADR-0022.R2, ADR-0022.R4). Its rows are never deleted or rebuilt, are unique per source line and direction, and are closed with `closed_reason`; execution tables refer to them (ADR-0028.R2). Planning reads only `inventory.contract`; it never imports `purchasing` or `sales`.
Source: ADR-0024.R8

R14. `demand_supply_line` holds item, warehouse, `direction` (demand or supply), open quantity in the inventory unit, `requested_date`, `ordered_date` (supply), `source_kind`, the source document line, `origin_planned_order_id` and `closed_reason` (`fulfilled`, `canceled`). DS-22 documents write it through posting interfaces in their own transactions, as they do reservations (ADR-0023.R13). A purchase request line's open quantity falls by what is ordered from it (a requirement on DS-22), so a request and its order are never counted twice. Transfer order lines exist (`transfer_order_line`), so `demand_supply_line.transfer_order_line_id` has its foreign key.
Source: ADR-0024.R8, .N2

R15. Which document types and states count as demand and supply is business behavior (open question). Interim, flagged:
- demand: sales order lines in states after `draft` (confirmed orders, not quotations), and transfer order lines at the source;
- supply: purchase order lines in any state but `canceled`, drafts included; purchase request lines; transfer order lines at the destination, including goods in a `transit` warehouse.
A transfer order line is demand at the source and supply at the destination, and stock transfers fulfil it (ADR-0075.R14).
Source: ADR-0024.R8, .N2

R16. Production orders count from `Create`: components as demand, outputs as supply, through the typed columns `production_order_component_id` and `production_order_output_id`. Reopening an order clears `closed_reason` and restores open quantity (ADR-0034.R6, ADR-0034.R9). The rows of a production order's components and outputs carry the hold reason `not_approved` until the order is approved (released), like sales and purchase rows (ADR-0047.R18). Make-to-order netting and planning count only released rows as demand; supply rows count once planned, held or not.
Source: ADR-0024.R8, .N1

R17. Planned orders as supply. Converted planned orders count as supply for the quantity not yet matched by open supply lines carrying their `origin_planned_order_id`; converted production planned orders count nothing (ADR-0036.R8). Firmed planned orders, and proposed ones frozen inside the firm fence (R46), count as supply at their `need_date`. For `reorder_point` and `min_max` they are part of the inventory position.
Source: ADR-0024.R8

R18. Overdue lines: demand or supply dated before the planning date counts at the planning date (interim, flagged).
Source: ADR-0024.R8

R19. Supply rows of draft purchase lines without `origin_planned_order_id` or pegging are deleted with the line; all others are closed, never deleted (ADR-0047.R10).
Source: ADR-0024.R8

### Stock on hand

R20. Stock on hand counts stock in status `available` in the warehouse, in any bin. `quality_inspection` and `blocked` stock do not count (interim, flagged). Stock in `goods_sent` warehouses is never counted.
Source: ADR-0024.R9

R21. Reservations (ADR-0023.R13) are ignored by netting. Demand counts in full and stock counts in full, so reserved stock is never counted twice. Reservations remain an allocation matter. Exception: make-to-order netting reads reservations for its own demand line (ADR-0036.R9).
Source: ADR-0024.R9

R22. A lot that expires before the projection consumes it (oldest expiry first) raises the exception `stock_expiring`. The quantity still counts, because availability is not lot-aware.
Source: ADR-0024.R9

R23. `GetProjectedAvailability` runs the netting of R35 and R36 read-only for one item and warehouse, without a plan. `GetAvailableToPromise` (ADR-0023) is on hand minus reservations, today.
Source: ADR-0024.R9

### Demand history and forecast

R24. Demand history is weekly buckets per item and warehouse of posted `sales_issue` quantities, minus `sales_return_receipt` quantities of the same week. History of goods sold from `goods_sent` warehouses is attributed to their valuation warehouse (ADR-0027.R15). For weeks before the company's first posting, rows of `sales_history` (item, warehouse, `iso_week`, quantity) are used instead; they are written by `ImportSalesHistory`, an import batch in the DS-21 format. Transfers are dependent demand and are excluded. Stock-outs are not inferred in Phase 1.
Source: ADR-0024.R10

R25. `demand_event` is company data: a `code` and, in `demand_event_window`, its window of dates per year, so a moving holiday stays aligned.
Source: ADR-0024.R10

R26. Indices. The seasonal index of ISO week w is the mean, over the years of history, of (demand in week w ÷ that year's mean weekly demand), computed without event weeks and normalized so the 52 indices average 1. Week 53 uses week 52's index. The event index of an event is the mean, over its past occurrences, of (demand in the event window ÷ the moving-average baseline of the 8 weeks before it). It replaces the seasonal index in event weeks. An event week of an event with no past occurrence in the history uses the week's seasonal index, or 1 where no index exists.
Source: ADR-0024.R10, ADR-0024.R11.N1

R27. Daily spread and rounding. The weekday profile is each weekday's share of demand over the last 26 weeks, uniform with less than 8 weeks of history. Each day carries the remainder forward, so no quantity is lost to the unit's decimal places (ADR-0006). All arithmetic uses `nativeflows.numeric`.
Source: ADR-0024.R10

R28. `RunForecast` (first slice) forecasts per (item, warehouse) by tier. n is the number of non-event weeks from the first week with history (posted or imported, R24) to the last complete week; weeks without sales count as zero.
- n = 0: no forecast and no `forecast_line` rows; the check result `forecast_history_insufficient` with `details.tier` `none`.
- 1 ≤ n < 8: the mean of those n weeks, unindexed; check result `forecast_history_insufficient` with tier `short_mean`.
- 8 ≤ n < 52: the 8-week moving average over the latest non-event weeks, unindexed; check result `forecast_history_insufficient` with tier `unindexed`.
- n ≥ 52: the same 8-week moving average, multiplied by the seasonal or event index (tier `indexed`, no check result).
The tier is stored on each `forecast_line` that exists: `forecast_line.forecast_tier` holds only `short_mean`, `unindexed` or `indexed`. The check results stay unhashed (R42).
Source: ADR-0024.R11, .N1, .N2

R29. Forecast inputs. History older than the simulated calendar is imported as `sales_history_recorded` events (DS-21 format), so the medium dataset covers indices. Whether the small dataset seeds a prior year is left with the open question on simulator coverage. Phase-in items may use a reference item's forecast, set by a person, or by an agent's proposal after approval. A planning run records the forecast run it used (`planning_run.forecast_run_id`).
Source: ADR-0024.R11

R30. Forecast methods of the later slice:
- simple and seasonal exponential smoothing, with parameters from the fixed grid {0.1, 0.2, 0.3, 0.5};
- Croston's method for intermittent items (at least 8 weeks with 2 or more non-zero);
- choice by the lowest mean absolute scaled error over `backtest_weeks`, with mean absolute error when the naive error is zero; ties go to the simpler method.
Source: ADR-0024.R11

R31. Forecast adjustments (`forecast_adjustment`) record item, warehouse, `start_date`, `end_date`, quantity or factor, author and reason. They never overwrite the statistical forecast, so accuracy stays measurable (DS-33). Forecast accuracy is the view `forecast_accuracy` (ADR-0050.R51).
Source: ADR-0024.R12

R32. Agent-proposed forecast adjustments are change proposals, and taint is read from document versions (ADR-0029.R5, ADR-0029.R11). Approval is human, and an adjustment proposed by a tainted agent run is never approved by policy (spec 03 rule 1; ADR-0013.R11). An e-mail therefore cannot move purchase quantities. Whether policy may approve untainted adjustments is an open question.
Source: ADR-0024.R12

R33. Forecast consumption:
- Open sales order demand consumes forecast of the same item and warehouse within `forecast_consumption_days`: backward first, then forward. Lines are processed in date, document number and `line_number` order.
- Shipped quantities are history, not demand.
- Forecast dated before the planning date is dropped.
- Remaining forecast is demand. The default window (7 days) is flagged as business behavior.
Source: ADR-0024.R13

### Netting and lot sizing

R35. Netting per method, at the planning date, given as trigger, then shortfall:
- `reorder_point`: inventory position < `reorder_point`; `reorder_point` − inventory position.
- `min_max`: inventory position < `minimum_quantity`; `maximum_quantity` − inventory position.
- `net_requirements`: projected available on day d < safety stock; safety stock − projected available on day d.
Safety stock (`net_requirements` only) is a floor in the trigger, never a demand. Levels of the other methods include whatever safety the user sets. Across bill of materials levels: ADR-0036.R10.
Source: ADR-0024.R14

R36. Terms of netting:
- Inventory position: stock on hand + open supply − open demand within the horizon. On `reorder_point` and `min_max` nodes it counts document demand only: open demand lines within the horizon, and dependent demand as ADR-0036.R10 says. Forecast never enters it, because those levels already stand for expected demand.
- Projection: for `net_requirements`, projected available is stock plus supply minus demand (including forecast), day by day over the horizon. Forecast is demand only for `net_requirements` nodes. Each shortfall becomes a proposal with `need_date` d, and the projection continues with it.
- Dates for the other methods: for `reorder_point` and `min_max`, `need_date` is the planning date plus lead time, and `release_date` is the planning date.
Source: ADR-0024.R14, .N1

R37. Lot sizing, in this order:
- first, the lot size method: exact shortfall, fixed lot (as many as needed), or demand of the next `supply_period_days`;
- then the supplier's minimum, in the supplier item's order unit;
- then the supplier's multiple, rounding up, in the supplier item's order unit;
- last, for `min_max`, the cap at `maximum_quantity`.
When the minimum or the multiple forces a quantity above the cap, the forced quantity wins. The excess is shown, and the exception `supplier_minimum_excess` is raised. Every proposal quantity, purchase, transfer or production, rounds up (ADR-0056.R8, ADR-0056.R14). For a production planned order the lot size method applies, the supplier's minimum and multiple do not, and the version's lot limits apply (ADR-0036.R4).
Source: ADR-0024.R15, .N1

### The planning graph

R38. Nodes of the planning graph are (item, warehouse). Edges are typed: `transfer` (ratio 1, offset = the route's lead time) and `bill_of_materials` (ratio = component quantity, offset = production lead time); bills of materials, phantom items, scrap factors and co-products are stated by ADR-0036.R1 to ADR-0036.R7. The run plans nodes downstream first, in the unique order of ADR-0036.R2: `item_low_level_code` ascending (0 for items without a row), then transfer depth within the item with destinations first, then item code, then warehouse code, never by IDs (ADR-0006.R6).
Source: ADR-0024.R16

R39. A planned transfer creates demand at the source on its release date, pegged to the transfer. When a source cannot cover all destinations, which destination goes first is business behavior (open question); interim, flagged: by `need_date`, then destination warehouse code. Costing uses the same item and warehouse identities over the period's actual flows, with its own solver graph (ADR-0025.R6).
Source: ADR-0024.R16

### Runs

R40. `RunPlanning` and `RunForecast` are long jobs. Triggers: a daily schedule, or a human's `RunPlanning` command, which records the request; the job is enqueued after commit (ADR-0013.R13) and runs as the same command type. They run on the `jobs` queue as internal callers (ADR-0013.R9), on behalf of the requester, or of the company's `planning_owner_id` for scheduled runs (ADR-0027.R15), with an explicit `planning_date` (ADR-0007.R17). Their `transaction_timeout` is the long-job 15 minutes (ADR-0022.R9).
Source: ADR-0024.R17

R41. One run per company at a time: a second run is rejected with `planning_run_in_progress`, through a lock on the company's planning state row (`planning_state`). Phase 1 runs regeneratively only.
Source: ADR-0024.R17

R42. The result of a run is counts per output kind, `input_hash` (canonical JSON of every input row, ADR-0008.R12 forms) and `output_hash`. These and the planned orders, messages and exceptions are listed like events and excluded from `plan_hash` (as ADR-0023.R11), so a run never fails on `plan_hash_mismatch`. `input_hash` also covers production inputs (ADR-0036.R13). Planning check results (`planning_parameter_missing`, `forecast_history_insufficient`) are not hashed either (ADR-0040.R10).
Source: ADR-0024.R17

R43. Simulation runs the real handler and rolls back (ADR-0008.R9). A client-facing simulation must limit `scope` to at most 50 items, to stay within the command timeout of 30 s.
Source: ADR-0024.R17

### Planned orders, fence and pegging

R44. A `planned_order` holds:
- a business key: item, warehouse, `order_type` (`purchase`, `transfer`, `production`), source (supplier or route: `supplier_partner_id`, `transfer_route_id`), `need_date` (only for `net_requirements`; `reorder_point` and `min_max` keep one open proposal per key without it), `sequence`; for `production` planned orders ADR-0036.R4 and ADR-0036.R5 apply: the key is item, warehouse, `need_date` and `sequence`, plus `for_demand_supply_line_id` (the demand line, set only on a `make_to_order` node), and the version is an attribute outside the key;
- `quantity`, in the inventory unit, and `release_date`;
- its order unit block: `order_quantity`, `order_uom_id`, `uom_numerator`, `uom_denominator` and `uom_factor_source` (identity for transfer and production proposals) (ADR-0056.R9, ADR-0056.R14);
- `state`: `proposed`, `firmed`, `converted` or `canceled`;
- pegging rows (R48).
Source: ADR-0024.R18, .N1

R45. A run matches proposals to existing ones by business key and updates them in place. It creates new ones, and cancels proposals no longer needed. A canceled row never blocks a new proposal: the new one takes the next `sequence`. Firmed and converted orders are never changed by a run; for a frozen or firmed production planned order the run still rewrites the `planned_order_component` rows, from the stored version and start, which stay unchanged (ADR-0036.R5). A firmed order whose release date has passed raises `firmed_order_overdue`.
Source: ADR-0024.R18

R46. The firm fence covers release dates strictly before planning date + `firm_horizon_days` (default 0, so no fence). Inside it a run changes no existing proposal. A frozen planned order is a `proposed` one whose release date lies inside the firm fence: a run changes nothing about it and counts it as supply (R17; ADR-0036.R5). A new shortage inside the fence is proposed with its release date moved to the first date outside the fence, and raises `shortage_inside_lead_time`; the projection continues with it. Production planned orders start no earlier than `earliest_start` = max(planning date, fence end) + `conversion_lead_days` (ADR-0036.R4).
Source: ADR-0024.R19, .N1

R47. Commands on planned orders: `FirmPlannedOrder`; `UpdatePlannedOrder`, which sets quantity or dates and implies firming (on a production planned order it may change quantity and planned start while `need_date` stays, and it calls `plan_production` once in mode `forward` and stores the selected version and dates: ADR-0036.R12, ADR-0036.R3.N1); `CancelPlannedOrder`, which cancels a proposed or firmed order, after which a later run may propose again if the need remains. Wrong states return `invalid_state_transition`.
Source: ADR-0024.R19

R48. Pegging rows (`planned_order_pegging`) hold planned order, `pegging_target_kind` (`demand_line`, `forecast`, `safety_stock`, `stock_level`, `lot_size_excess`, `planned_order`), target reference and quantity. A planned order's pegging sums exactly to its quantity (DS-16; `INV-60`). Through a route, the destination's planned transfer pegs destination demand, and the source's dependent demand pegs that transfer. Demand-line targets are `demand_supply_line_id` (ADR-0028.R2). Dependent demand pegs with target kind `planned_order` (ADR-0036.R5).
Source: ADR-0024.R20

### Action messages and exceptions

R49. Action messages and exceptions of a run:
- Action messages on existing supply: `expedite` and `cancel` in the first slice; `postpone` and `reduce` later (for production-order supply: R58). Each carries its projected effect.
- Exceptions (`planning_exception_kind`, the column `planning_exception.kind`): `shortage_inside_lead_time`, `below_safety_stock`, `above_maximum`, `supplier_minimum_excess`, `below_supplier_minimum_amount`, `container_underfilled`, `stock_expiring`, `firmed_order_overdue`, `planning_parameter_missing` (no supplier, no route, no lead time; the run skips the item and continues), `capacity_overload` (per work center and overloaded range; ADR-0036.R11), `production_order_start_overdue` and `production_order_overdue` (R58).
- Work item kinds: `planning_exception` and `capacity_overload` (ADR-0042.R18).
- Work items: the consumer `planning_work_items` of `PlanningCompleted` keeps one work item per open planning exception, not per buyer, and closes those that a run no longer raises (ADR-0031.R17). The per-buyer list (`buyer_id`, ADR-0018.R3) is a query.
Source: ADR-0024.R21, ADR-0024.R21.N2, ADR-0031.R17

R52. Storage, owned by `planning`:
- `planning_run`: one per run, with `planning_date`, scope (`scope_item_ids`), requester (`requested_by_user_id`), the forecast run used, counts (`output_counts`), `input_hash` and `output_hash` (R42);
- `planned_order`, `planned_order_pegging` (R48), `planned_order_component` and `planned_order_operation` (ADR-0036.R4, ADR-0036.R5);
- `planning_action_message`: run, supply line (`demand_supply_line_id`), `kind`, `proposed_date` or `proposed_quantity`, `projected_effect`;
- `planning_exception`: run, `kind`, node or work center, date range, `evidence` and `state` (`open`, `closed`); the subject of both work item kinds of R49;
- `forecast_run`: one per `RunForecast`, with `planning_date`, `method` and `check_results`;
- `forecast_line`: run, item, warehouse, `forecast_date` (one row per day after the weekday spread of R27), statistical `quantity`, `forecast_tier` (R28) and the index applied (`index_factor`);
- `forecast_adjustment` (R31);
- `planning_state`: the company's lock row (R41).
Source: ADR-0024.R21.N1

R53. Adjustment commands on the authorization leaf `forecast`: `CreateForecastAdjustment` and `CancelForecastAdjustment`, effect class `master_data_change`, so agents reach them only through change proposals (R32; ADR-0029.R2). An adjustment is never edited: a change is a cancellation and a new adjustment.
Source: ADR-0024.R21.N1

R54. Triggers are evaluated per node after netting; each is raised at most once per run and key. Message triggers, with their key:
- `expedite`: on a `net_requirements` node, an open supply line (not a planned order) is dated after the first day d on which projected available falls below safety stock, and moving it to d would cover the shortfall. Effect: days earlier and quantity covered. Key: supply line.
- `cancel`: an open purchase or transfer supply line without receipts that the projection never needs within the horizon: without it, projected available stays at or above safety stock, or the inventory position at or above the reorder point or minimum. Effect: quantity freed. Key: supply line. The horizon is the company setting `planning.cancel_horizon_days` (default 0: the node's planning horizon; a larger value looks further ahead), bounded by ADR-0063.
Source: ADR-0024.R21.N1, ADR-0024.R21.N3

R55. Exception triggers, with their key:
- `shortage_inside_lead_time`: a proposal's release date would fall before the planning date or inside the fence, so it is moved (R46), or a production plan is late (ADR-0036.R4). Evidence: days late. Key: node, need date.
- `below_safety_stock`: with every supply at its real availability date, proposals included, projected available is below safety stock but not below zero; once per contiguous range. Key: node, first date.
- `above_maximum`: a `min_max` node whose inventory position with firmed and converted supply exceeds `maximum_quantity`. Key: node.
- `supplier_minimum_excess`: a supplier minimum or multiple forces a quantity above the cap or the shortfall (R37). Key: planned order.
- `below_supplier_minimum_amount`: the proposals that conversion would group into one purchase (R60) total, at preliminary prices, less than the supplier's `minimum_order_amount`. Key: supplier, warehouse, release window.
- `container_underfilled`: the same group fills its last container below `planning.container_underfilled_pct` percent (a company setting, default 50, bounded by ADR-0063) of both volume and weight. Key: supplier, warehouse, release window.
- `stock_expiring`: R22. Key: lot.
- `firmed_order_overdue`: R45. Key: planned order.
- `capacity_overload`: ADR-0036.R11. Key: work center, first bucket.
Source: ADR-0024.R21.N1, ADR-0024.R21.N3

R56. `planning_parameter_missing` is raised when a node or firmed order cannot be planned from its parameters. Key: node, reason. `details.reason` is `planning_row_missing` (open demand on a node without a row), `supplier_missing`, `route_missing`, `lead_time_missing`, `phantom_demand`, `production_version_missing`, `production_version_invalid`, `processor_route_missing` or `processor_location_missing`. The note's values govern. The interim DDL check on `planning_exception.reason` lists `preferred_supplier_ambiguous` and `phantom_with_demand` instead of `phantom_demand`, `processor_route_missing` and `processor_location_missing`, and is to be corrected.
Source: ADR-0024.R21.N1

R57. `capacity_overload` is stored in `planning_exception` like the others, with the work center as subject, but its work item kind is `capacity_overload`, owned by `planning_owner`; it is never a `planning_exception` work item. Work items of kind `planning_exception` are owned by the kind rule `planning_node_owner`: the company's `planning_owner_id` when the node's replenishment source is `production`, otherwise the item's buyer (ADR-0042.R7).
Source: ADR-0024.R21.N1

R58. Production orders get exceptions and messages: the exceptions `production_order_start_overdue` and `production_order_overdue` (with `production_order_id`), and `expedite`, `postpone`, `cancel` and `reduce` on a production order's main-output supply line, under `planning.production_reschedule_in_tolerance_days` (default 0), `planning.production_reschedule_out_tolerance_days` (default 3), `planning.production_rescheduling_horizon_days` (default 60), `production.order.start_grace_days` (default 1) and `production.order.overdue_grace_days` (default 0), which are company settings. `postpone` and `reduce` are in Phase 1 for production-order supply. One work item `production_order_exception` per order (owner `planning_owner`) lists them; these kinds get no `planning_exception` item, as `capacity_overload` has its own kind (ADR-0064.R17).
Source: ADR-0024.R21.N2

### Conversion

R60. `ConvertPlannedOrder` takes firmed or proposed planned orders. Purchase orders are grouped by supplier, warehouse, and release date within `conversion_window_days`; transfer orders by route. Production planned orders convert through `production.contract` (ADR-0036.R8). A planned order converts whole; a split is two `UpdatePlannedOrder` calls in Phase 1.
Source: ADR-0024.R22

R61. Hand-over. The command sets `converted` and calls the posting interface `inventory.contract.request_replenishment`, which writes one `replenishment_request` with a line per planned order (carrying `origin_planned_order_id`) and emits `ReplenishmentRequested` from `inventory`, so every importer imports downward (ADR-0022.R2). The replenishment request line carries the planned order's order unit and snapshot (ADR-0056.R14).
Source: ADR-0024.R22, .N1

R62. Drafts. The `purchasing` consumer of `ReplenishmentRequested` groups the request's purchase lines by supplier, warehouse and release window into draft purchase requests (interim, flagged: the default target, following spec 09's request → order chain). `inventory` creates the draft transfer orders itself. Drafts are created as actor `system` on behalf of the converter, follow their own approval (DS-28), and carry `origin_planned_order_id`. The drafted purchase request line carries the planned order's order unit and snapshot; a purchase order copied from a request keeps the request's unit unless the person changes it (ADR-0056.R14). Service lines for external operations are drafted the same way, from the production order's approval event (ADR-0037.R4).
Source: ADR-0024.R22, .N1

R63. When the document lines of a converted order close with `closed_reason` `canceled` (R14), the next run sets it `canceled` and may propose again.
Source: ADR-0024.R22

R64. Converting under a value threshold by policy is an open question (DS-28). Sending to a supplier always stays a separate approved step. For agents, `UpdatePlannedOrder`, `FirmPlannedOrder` and `ConvertPlannedOrder` are proposal-bound for every order type (ADR-0036.R12).
Source: ADR-0024.R22

## Invariants

Statements are those of `invariants.csv`. Each row stands once in the module, in the chunk that states the rule its catalog source names.

| Invariant | Name | Check point | Statement | Protects |
| --- | --- | --- | --- | --- |
| `INV-60` | `pegging_sums_to_quantity` | day | Every proposed or firmed planned order has pegging rows that sum exactly to its quantity. | R48 |
| `INV-61` | `planning_run_reproducible` | day | Two simulated planning runs at a check point give equal `output_hash`, and a stored run with the same `input_hash` has that `output_hash`; `not_evaluated` from `nativeflows-check`. | R42, R43 |
| `INV-62` | `converted_order_keeps_origin` | day | Every document line created from a converted planned order carries its `origin_planned_order_id`, and every converted planned order has such a line or is canceled. | R61-R63 |
| `INV-63` | `demand_supply_matches_source` | day | Each `demand_supply_line` open quantity equals its source line's quantity minus fulfilled and closed quantities, recomputed from the referring documents. | R13, R14; ADR-0027.R17 |

## Edge cases

The catalog source of these rows is ADR-0024 as a whole (for `EC-41` also ADR-0053); they stand here with the rules they exercise. The other edge cases of area `planning` are in chunk 2.

| Edge case | Name | Case | Outcome | Rule |
| --- | --- | --- | --- | --- |
| `EC-41` | `import_across_holiday` | An import whose supplier processing and transit span a multi-day holiday from the package calendar; release date and need date follow the calendars. | `must_succeed` | R10; ADR-0053 |
| `EC-42` | `intermittent_item` | An item sold rarely in large lots: planned orders cover its open orders and the moving-average forecast, and no proposal is created for a past spike alone. | `must_succeed` | R28, R36 |
| `EC-43` | `supplier_minimum_excess` | A supplier minimum forces a quantity above the maximum; the excess is shown with an exception. | `must_succeed` | R37 |
| `EC-44` | `transfer_network` | A destination warehouse replenished by transfer from a central warehouse, with dependent demand at the source. | `must_succeed` | R38, R39 |
| `EC-45` | `promotion_adjustment` | A forecast adjustment for a promotion, approved by a human, raises planned quantities. | `must_succeed` | R31, R32 |

## Settings

| Key | Value type | Scope | Core default | Bounds | Leaf | Rule |
| --- | --- | --- | --- | --- | --- | --- |
| `planning.cancel_horizon_days` | integer | company | 0 | 0..365 | `planning_run` | R54 |
| `planning.container_underfilled_pct` | integer | company | 50 | 1..100 | `planning_run` | R55 |

Both have storage `setting_value`, direction `neutral`, effect `immediate` and outdates `none`.

Named by R58, with their rows in chunk 2 (catalog source ADR-0064.R17): `planning.production_reschedule_in_tolerance_days`, `planning.production_reschedule_out_tolerance_days`, `planning.production_rescheduling_horizon_days`. The company values of R12 are columns of `planning_setting`, not rows of `settings.csv`.

Reads: `production.order.start_grace_days`, `production.order.overdue_grace_days` (`production`).

## UI annotations

The sources hold no floorplan, title, facet, field annotation or tile of ADR-0077 for this module. Work item kinds of `planning` (catalog `work-item-kinds.csv`); the row of `production_order_exception` (R58) is in chunk 2:

| Kind | Subject table | Owner | Due | Resolution | Rule |
| --- | --- | --- | --- | --- | --- |
| `planning_exception` | `planning_exception` | `planning_node_owner` (ADR-0042.R7.N2) | `required_date` | `system`: closed when a run no longer raises it | R49, R57 |
| `capacity_overload` | `work_center` | `planning_owner` | `required_date` | `system`; one item per work center and contiguous range, buckets as evidence | R49, R57; ADR-0036.R11 |

Neither is agent-resolvable.

## Conflicts

CONFLICT ADR-0024.H.N1: this note with ADR-0032 governs every "Phase 2" label of ADR-0024; planning, production, planned production orders, phantoms, scrap factors and co-products are Phase 1 (R1, R3).
CONFLICT ADR-0024.D0: ADR-0024.H.N1 answers the phase question, ADR-0024.R26.N2 places the later slice in build step 5b, so R3 states the slices as decided, the later slice and bills of materials in step 5b; ADR-0031.R17 governs work items per exception instead of "grouped per buyer" (R1, R49).
CONFLICT ADR-0024.R1: the rule's own amendment citing ADR-0033.R14 governs; `production` is a Phase 1 value of `replenishment_source` (R4).
CONFLICT ADR-0024.R2: ADR-0024.R2.N1 governs the unit; the minimum and the multiple are in `order_uom_id`, not in "the purchase unit" (R6), and the DDL adds `currency`, `volume_uom_id` and `weight_uom_id` to the term (R7).
CONFLICT ADR-0024.R6: ADR-0024.R6.N1 governs; "the purchase unit" is the supplier item's `order_uom_id`, with the stated rounding (R11).
CONFLICT ADR-0024.R8: the rule's own amendments citing ADR-0028.R2, ADR-0034.R6, ADR-0036.R8 and ADR-0047.R10 are stated as the current text (R13, R16, R17, R19); ADR-0024.R8.N2 governs transfer order lines, which exist with their foreign key (R14, R15).
CONFLICT ADR-0024.R11: ADR-0024.R11.N1 and ADR-0024.R11.N2 govern the forecast with less than 52 weeks of history; the tiers of R28 stand instead of one check result without a forecast method.
CONFLICT ADR-0024.R14: ADR-0024.R14.N1 governs; forecast is demand only on `net_requirements` nodes and never enters the inventory position (R36).
CONFLICT ADR-0024.R16: the rule's own amendment citing ADR-0036.R1 to ADR-0036.R7 governs; `bill_of_materials` edges are Phase 1, and phantom items, scrap factors and co-products are no longer outside the design; ADR-0036.R2 governs the order in which the run plans nodes, by `item_low_level_code` first, instead of ties by item code and warehouse code alone (R38).
CONFLICT ADR-0024.R18: ADR-0024.H.N1 makes `production` a Phase 1 order type; ADR-0024.R18.N1 adds the order unit block; the DDL, citing ADR-0036.R4, adds `for_demand_supply_line_id` to the business key (R44); ADR-0036.R5 governs over "never changed by a run" for the component rows of frozen and firmed production planned orders, which every run rewrites (R45).
CONFLICT ADR-0024.R19: ADR-0024.R19.N1 governs the reading; the sentence on `earliest_start` belongs to the fence paragraph and not to the command list (R46, R47); ADR-0036.R12 and ADR-0036.R3.N1 govern `UpdatePlannedOrder` on a production planned order: quantity and planned start only, `need_date` stays, one call of `plan_production` in mode `forward` (R47).
CONFLICT ADR-0024.R20: the rule's own amendment citing ADR-0036.R5 adds the target kind `planned_order`, which the DDL check holds (R48).
CONFLICT ADR-0024.R21: ADR-0031.R17 governs the work items: one per open planning exception, not one per buyer (R49). The DDL governs the columns of `forecast_run` and `forecast_line` that the rule's storage note names: `planning_date` and `check_results` instead of forecast date and history weeks, one `forecast_line` row per day instead of per ISO week with a daily spread (R52).
CONFLICT ADR-0024.R21.N3: this note governs the thresholds of ADR-0024.R21.N1; they are company settings with the interim values as defaults, so the mark "interim, flagged for the author" is not restated (R54, R55).
CONFLICT ADR-0024.R21.N1: the value list of this note governs the reasons of `planning_parameter_missing` (chief architect, 2026-11-21: the ADRs are law). The DDL check on `planning_exception.reason` is marked interim, holds `preferred_supplier_ambiguous` and `phantom_with_demand`, which no ADR names, and lacks `phantom_demand`, `processor_route_missing` and `processor_location_missing`, which the note, ADR-0037 and DS-04 use; R56 states the note's values and the DDL check is to be corrected.

## Proposed (not law)

None

## Trace

| Source | Where |
| --- | --- |
| ADR-0018.R12.N1 | ref: ADR-0018.R12.N1 |
| ADR-0019.R6 | ref: ADR-0019.R6 |
| ADR-0019.R6.N1 | ref: ADR-0019.R6.N1 |
| ADR-0020.R11.N2 | ref: ADR-0020.R11.N2 |
| ADR-0024.H.N1 | R1, R3 |
| ADR-0024.D0 | R1-R3 |
| ADR-0024.R1 | R4, R5 |
| ADR-0024.R1.N1 | R4 |
| ADR-0024.R2 | R6-R8 |
| ADR-0024.R2.N1 | R6, R7 |
| ADR-0024.R3 | R9 |
| ADR-0024.R3.N1 | R9 |
| ADR-0024.R5 | R10 |
| ADR-0024.R6 | R11 |
| ADR-0024.R6.N1 | R11 |
| ADR-0024.R7 | R12 |
| ADR-0024.R8 | R13-R19 |
| ADR-0024.R8.N1 | R16 |
| ADR-0024.R8.N2 | R14, R15 |
| ADR-0024.R9 | R20-R23 |
| ADR-0024.R10 | R24-R27 |
| ADR-0024.R11 | R28-R30 |
| ADR-0024.R11.N1 | R26, R28 |
| ADR-0024.R11.N2 | R28 |
| ADR-0024.R12 | R31, R32 |
| ADR-0024.R13 | R33 |
| ADR-0024.R14 | R35, R36 |
| ADR-0024.R14.N1 | R36 |
| ADR-0024.R15 | R37 |
| ADR-0024.R15.N1 | R37 |
| ADR-0024.R16 | R38, R39 |
| ADR-0024.R17 | R40-R43 |
| ADR-0024.R18 | R44, R45 |
| ADR-0024.R18.N1 | R44 |
| ADR-0024.R19 | R46, R47 |
| ADR-0024.R19.N1 | R46 |
| ADR-0024.R20 | R48 |
| ADR-0024.R21 | R49 |
| ADR-0024.R21.N1 | R52-R57 |
| ADR-0024.R21.N2 | R49, R58 |
| ADR-0024.R21.N3 | R54, R55 |
| ADR-0024.R22 | R60-R64 |
| ADR-0024.R22.N1 | R61, R62 |
