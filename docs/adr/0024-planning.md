# ADR-0024: Planning

Status: accepted (2026-11-14) under ADR-0005, reviewed by Claude Fable 5.2 (builder Claude Opus 5.5). Design item: DS-43 (new). Related decisions: D2, D5. Principles 2, 6, 8, 9, 12, 13. Build principles B1, B3, B7. ADR-0004, ADR-0005, ADR-0006, ADR-0007, ADR-0008, ADR-0012, ADR-0013, ADR-0016, ADR-0017, ADR-0018, ADR-0019, ADR-0020, ADR-0022, ADR-0023, DS-16, DS-17, DS-29.

Note: planning is in Phase 1, which answers the phase question of the opening. Multi-level MRP is designed in DS-54. Every "Phase 2" label in this ADR (production, planned production orders, phantoms, scrap factors, co-products) now reads Phase 1, designed in DS-51 and DS-54 ([ADR-0032](0032-phase-1-scope-with-production.md)).

## Decision

On 2026-11-14 the author asked for planning to be designed now, after warehouse management. Two things are the author's decision, both open questions: which phase builds it, and the feature list proposed here.

Planning answers, per item and warehouse: what to buy or move, how much, and by when.

**How a run works.**
- **The run.** One deterministic job nets open demand against supply over a graph of (item, warehouse) nodes linked by transfer routes. Bills of materials join in Phase 2 as a second edge type.
- **Outputs.** It writes planned orders with stable business keys. Each is pegged to the demand, safety stock or stock level it covers, which is its derivation trace (Principle 6). Exceptions, grouped per buyer, become work items.
- **What happens next.** People, or policy, firm planned orders and convert them. Conversion emits an event, and the purchasing and inventory modules turn it into draft documents. Planning itself sends and posts nothing (Principle 12).

**Agents.** They explain proposals, consolidate them against supplier terms held as data, and draft parameter changes and forecast adjustments. Changes to master data need approval.

**Proposed slices.**
- **First slice** (step 5, if planning is in Phase 1):
  - reorder point and min/max;
  - time-phased netting of real demand;
  - transfer routes;
  - action messages `expedite` and `cancel`;
  - a weekly forecast by moving average with seasonal and event indices.
- **Later slice**, once forecast accuracy is measured:
  - exponential smoothing and Croston's method, chosen by backtest;
  - service-level safety stock;
  - `postpone` and `reduce` messages.
- **Phase 2:** bills of materials on the same graph.

### Rules

**Parameters and master data**

1. `item_warehouse_planning` holds the planning parameters for one item in one warehouse. An item without a row in a warehouse is not planned there. Agent changes go through change proposals ([ADR-0029](0029-proposals-and-agent-safety.md) rule 5).

   | Group | Fields |
   | --- | --- |
   | Method | `planning_method`: `reorder_point`, `min_max` or `net_requirements` |
   | Source | `replenishment_source`: `purchase` or `transfer` (`production` in Phase 2) |
   | Levels | `reorder_point`, `minimum_quantity`, `maximum_quantity` |
   | Safety stock | `safety_stock_method` (`fixed`, or `service_level` in the later slice), `safety_stock_quantity`, `service_level_percent` |
   | Lot size | `lot_size_method` (`exact`, `fixed` with `fixed_lot_quantity`, `supply_period` with `supply_period_days`) |
   | Fence and receiving | `firm_horizon_days`, `receiving_days` (receiving and inspection, on the warehouse's calendar) |

   It is master data. People with the permission change it directly; changes proposed by agents await approval (spec 14: an agent's change of master data requires approval) and carry their evidence. It replaces the entry for it in ADR-0018's "deliberately elsewhere" list.
2. Supplier data:
   - `supplier_item` is a new table keyed by (company, supplier partner, item). It holds:
     - `supplier_processing_days` (counted on the supplier's calendar);
     - `transit_days` (calendar days, because ships sail through holidays);
     - `minimum_order_quantity` and `order_multiple` in the purchase unit;
     - `is_preferred`: exactly one valid `supplier_item` per item may be preferred at a release date; none or several gives `planning_parameter_missing`;
     - `start_date` and `end_date`.

     It may refer to the partner's own item code in `partner_item` (ADR-0019 rule 6). It is the only home of supplier minimums, multiples and preference.
   - `supplier_purchasing_term` (one row per supplier partner) holds `minimum_order_amount` with its currency, an optional `container_volume` and `container_weight`, and an optional `order_cycle_days`.
   - `supplier_item_lead_time` stores measured lead times per (supplier, item), refreshed by the forecast job: mean and standard deviation (square root through `erpme.numeric`) of the days from the supply line's `ordered_date` to receipt, read from `demand_supply_line` (rule 8). They are visible data (spec 03 rule 9) and are never applied without approval.
3. `transfer_route` holds:
   - source warehouse, destination warehouse;
   - `lead_time_days` (calendar days); the destination warehouse's `receiving_days` and calendar then apply, as for purchases.

   A `transfer` replenishment source names a route. Writing parameters that would form a cycle of transfer sources is rejected with `planning_network_cycle`.
4. Working calendars:
   - `working_calendar` is company data: working weekdays and holiday dates, assigned to warehouses and suppliers.
   - The localization package may seed public holidays as a template entry with a basis (ADR-0016). Tết dates are calendar data, not code.
5. Lead time and dates:
   - **Lead time of a purchase:** `supplier_processing_days` on the supplier's calendar, then `transit_days` as calendar days, then `receiving_days` on the warehouse's calendar.
   - **Release date:** the latest working day of the supplier's calendar from which the order still arrives by its `need_date`.
6. Units: every planning quantity is in the item's inventory unit (ADR-0018 rule 9). The supplier's minimum and multiple are applied in the purchase unit, then converted exactly. Rounding excess is shown on the proposal.
7. `planning_setting` per company holds:
   - `planning_owner_id`: the human accountable for scheduled runs (spec 03 rule 3);
   - `planning_horizon_days`;
   - `forecast_consumption_days`;
   - `conversion_window_days`;
   - `backtest_weeks`.

**Demand and supply**

8. Open demand and supply lines are a read model owned by `inventory`, so planning in layer 4 can read it through `inventory.contract` (ADR-0022 rules 2, 4). Its rows are never deleted or rebuilt, unique per source line and direction, and closed with `closed_reason`; execution tables refer to them ([ADR-0028](0028-document-lifecycle-hardening.md) rule 2).
   - **Lines.** `demand_supply_line` holds item, warehouse, `direction` (demand or supply), open quantity in the inventory unit, `requested_date`, `ordered_date` (supply), `source_kind`, the source document line, `origin_planned_order_id` and `closed_reason` (`fulfilled`, `canceled`). DS-22 documents write it through posting interfaces in their own transactions, as they do reservations (ADR-0023 rule 13). A purchase request line's open quantity falls by what is ordered from it (a requirement on DS-22), so a request and its order are never counted twice. Planning reads only `inventory.contract`; it never imports `purchasing` or `sales`.
   - **What counts.** Which document types and states count as demand and supply is business behavior (open question). Interim, flagged:
     - **demand:** sales order lines in states after `draft` (confirmed orders, not quotations), and transfer order lines at the source;
     - **supply:** purchase order lines in any state but `canceled`, drafts included; purchase request lines; transfer order lines at the destination, including goods in a `transit` warehouse;
     - **converted planned orders** count as supply for the quantity not yet matched by open supply lines carrying their `origin_planned_order_id`;
     - **firmed planned orders**, and proposed ones frozen inside the firm fence, count as supply at their `need_date`. For `reorder_point` and `min_max` they are part of the inventory position.
   - **Overdue lines.** Demand or supply dated before the planning date counts at the planning date (interim, flagged).
9. Stock on hand:
   - **Counted:** stock in status `available` in the warehouse, in any bin. `quality_inspection` and `blocked` stock do not count (interim, flagged).
   - **Never counted:** stock in `goods_sent` warehouses.
   - **Reservations** (ADR-0023 rule 13) are ignored by netting. Demand counts in full and stock counts in full, so reserved stock is never counted twice. Reservations remain an allocation matter.
   - **Expiring lots:** a lot that expires before the projection consumes it (oldest expiry first) raises the exception `stock_expiring`. The quantity still counts, because availability is not lot-aware.
   - **Related queries.** `GetProjectedAvailability` runs this netting read-only for one item and warehouse, without a plan. `GetAvailableToPromise` (ADR-0023) is on hand minus reservations, today.

**Forecast**

10. Demand history (history of goods sold from `goods_sent` warehouses is attributed to their valuation warehouse, [ADR-0027](0027-cross-cutting-ownership.md) rule 15):
    - **Source.** Weekly buckets per item and warehouse of posted `sales_issue` quantities, minus `sales_return_receipt` quantities of the same week. For weeks before the company's first posting, rows of `sales_history` (item, warehouse, ISO week, quantity) are used instead; they are written by `ImportSalesHistory`, an import batch in the DS-21 format. Transfers are dependent demand and are excluded. Stock-outs are not inferred in Phase 1.
    - **Events.** `demand_event` is company data: a code (such as `tet`) and its window of dates per year, so a moving holiday stays aligned.
    - **Seasonal index** of ISO week w: the mean, over the years of history, of (demand in week w ÷ that year's mean weekly demand), computed without event weeks and normalized so the 52 indices average 1. Week 53 uses week 52's index.
    - **Event index** of an event: the mean, over its past occurrences, of (demand in the event window ÷ the moving-average baseline of the 8 weeks before it). It replaces the seasonal index in event weeks.
    - **Daily spread.** The weekday profile is each weekday's share of demand over the last 26 weeks, uniform with less than 8 weeks of history.
    - **Rounding.** Each day carries the remainder forward, so no quantity is lost to the unit's decimal places (ADR-0006). All arithmetic uses `erpme.numeric`.
11. `RunForecast` (first slice):
    - **Method.** A moving average over the last 8 weeks without event weeks, multiplied by the seasonal or event index where at least 52 weeks of history exist. With less history, the check result is `forecast_history_insufficient`.
    - **Datasets.** History older than the simulated calendar is imported as `sales_history_recorded` events (DS-21 format), so the medium dataset covers indices. Whether the small dataset seeds a prior year is left with the open question on simulator coverage.
    - **Phase-in items.** These may use a reference item's forecast, set by a person, or by an agent's proposal after approval.
    - **Later slice.**
      - Simple and seasonal exponential smoothing, with parameters from the fixed grid {0.1, 0.2, 0.3, 0.5}.
      - Croston's method for intermittent items (at least 8 weeks with 2 or more non-zero).
      - Choice by the lowest mean absolute scaled error over `backtest_weeks`, with mean absolute error when the naive error is zero. Ties go to the simpler method.
    - **Inputs.** A planning run records the forecast run it used.
12. Forecast adjustments record item, warehouse, `start_date`, `end_date`, quantity or factor, author and reason. They never overwrite the statistical forecast, so accuracy stays measurable (DS-33). Agent-proposed adjustments are change proposals, and taint is read from document versions ([ADR-0029](0029-proposals-and-agent-safety.md) rules 5, 11).
    - Approval is human, and an adjustment proposed by a tainted agent run is never approved by policy (spec 03 rule 1; ADR-0013 rule 11). An e-mail therefore cannot move purchase quantities.
    - Whether policy may approve untainted adjustments is an open question.
13. Forecast consumption:
    - Open sales order demand consumes forecast of the same item and warehouse within `forecast_consumption_days`: backward first, then forward. Lines are processed in date, document number and `line_number` order.
    - Shipped quantities are history, not demand.
    - Forecast dated before the planning date is dropped.
    - Remaining forecast is demand. The default window (7 days) is flagged as business behavior.

**Netting**

14. Netting per method, at the planning date. Safety stock (`net_requirements` only) is a floor in the trigger, never a demand. Levels of the other methods include whatever safety the user sets.

    | Method | Trigger | Shortfall |
    | --- | --- | --- |
    | `reorder_point` | inventory position < `reorder_point` | `reorder_point` − inventory position |
    | `min_max` | inventory position < `minimum_quantity` | `maximum_quantity` − inventory position |
    | `net_requirements` | projected available on day d < safety stock | safety stock − projected available on day d |

    - **Inventory position.** Stock on hand + open supply − open demand within the horizon.
    - **Projection.** For `net_requirements`, projected available is stock plus supply minus demand (including forecast), day by day over the horizon. Each shortfall becomes a proposal with `need_date` d, and the projection continues with it.
    - **Dates for the other methods.** For `reorder_point` and `min_max`, `need_date` is the planning date plus lead time, and `release_date` is the planning date.
15. Lot sizing, in this order:
    1. the lot size method: exact shortfall, fixed lot (as many as needed), or demand of the next `supply_period_days`;
    2. the supplier's minimum;
    3. the supplier's multiple, rounding up;
    4. for `min_max`, the cap at `maximum_quantity`.

    When the minimum or the multiple forces a quantity above the cap, the forced quantity wins. The excess is shown, and the exception `supplier_minimum_excess` is raised.

**The planning graph and the run**

16. The planning graph:
    - **Nodes and edges.** Nodes are (item, warehouse). Edges are typed: `transfer` (ratio 1, offset = the route's lead time) now; `bill_of_materials` (ratio = component quantity, offset = production lead time) in Phase 2. Phantom items, scrap factors and co-products are outside this ADR.
    - **Order.** The run plans nodes in topological order, downstream first. Ties are broken by item code, then warehouse code, never by IDs (ADR-0006 rule 6).
    - **Dependent demand.** A planned transfer creates demand at the source on its release date, pegged to the transfer.
    - **Short source.** When a source cannot cover all destinations, which destination goes first is business behavior (open question). Interim, flagged: by `need_date`, then destination warehouse code.
    - **Costing.** Costing uses the same item and warehouse identities over the period's actual flows, with its own solver graph ([ADR-0025](0025-later-phase-seams.md) rule 6).
17. `RunPlanning` and `RunForecast` are long jobs:
    - **Triggers.** A daily schedule, or a human's `RunPlanning` command, which records the request; the job is enqueued after commit (ADR-0013 rule 13) and runs as the same command type, on behalf of the requester (the `planning_owner_id` for scheduled runs).
    - **Running.** They run on the `jobs` queue as internal callers (ADR-0013 rule 9), on behalf of the requester, or of the company's `planning_owner_id` for scheduled runs ([ADR-0027](0027-cross-cutting-ownership.md) rule 15), with an explicit `planning_date` (ADR-0007 rule 17). Their `transaction_timeout` is the long-job 15 minutes (ADR-0022 rule 9).
    - **Concurrency.** One run per company at a time: a second run is rejected with `planning_run_in_progress`, through a lock on the company's planning state row.
    - **Mode.** Phase 1 runs regeneratively only.
    - **Result.** Counts per output kind, `input_hash` (canonical JSON of every input row, ADR-0008 rule 12 forms) and `output_hash`. These and the planned orders, messages and exceptions are listed like events and excluded from `plan_hash` (as ADR-0023 rule 11), so a run never fails on `plan_hash_mismatch`.
    - **Simulation.** Simulation runs the real handler and rolls back (ADR-0008 rule 9). A client-facing simulation must limit `scope` to at most 50 items, to stay within the 30 s command timeout.

**Planned orders**

18. A `planned_order` holds:
    - a business key: item, warehouse, `order_type` (`purchase`, `transfer`, `production` in Phase 2), source (supplier or route), `need_date` (only for `net_requirements`; `reorder_point` and `min_max` keep one open proposal per key without it), `sequence`;
    - quantity and `release_date`;
    - `state`: `proposed`, `firmed`, `converted` or `canceled`;
    - pegging rows.

    A run matches proposals to existing ones by business key and updates them in place. It creates new ones, and cancels proposals no longer needed. A canceled row never blocks a new proposal: the new one takes the next `sequence`. Firmed and converted orders are never changed by a run; a firmed order whose release date has passed raises `firmed_order_overdue`.
19. The firm fence covers release dates strictly before planning date + `firm_horizon_days` (default 0, so no fence). Inside it a run changes no existing proposal. A new shortage there is proposed with its release date moved to the first date outside the fence, and raises `shortage_inside_lead_time`; the projection continues with it. Commands:
    - `FirmPlannedOrder`;
    - `UpdatePlannedOrder`, which sets quantity or dates and implies firming;
    - `CancelPlannedOrder`, which cancels a proposed or firmed order; a later run may propose again if the need remains.

    Wrong states return `invalid_state_transition`.
20. Pegging rows hold planned order, `pegging_target_kind` (`demand_line`, `forecast`, `safety_stock`, `stock_level`, `lot_size_excess`), target reference and quantity. A planned order's pegging sums exactly to its quantity (DS-16). Through a route, the destination's planned transfer pegs destination demand, and the source's dependent demand pegs that transfer. Demand-line targets are `demand_supply_line_id` ([ADR-0028](0028-document-lifecycle-hardening.md) rule 2).
21. Action messages and exceptions:
    - **Action messages** on existing supply: `expedite` and `cancel` in the first slice; `postpone` and `reduce` later. Each carries its projected effect.
    - **Exceptions** (`planning_exception_kind`):
      - `shortage_inside_lead_time`;
      - `below_safety_stock`;
      - `above_maximum`;
      - `supplier_minimum_excess`;
      - `below_supplier_minimum_amount`;
      - `container_underfilled`;
      - `stock_expiring`;
      - `firmed_order_overdue`;
      - `planning_parameter_missing` (no supplier, no route, no lead time). The run skips the item and continues.
    - **Work items.** The consumer `planning_work_items` of `PlanningCompleted` keeps one work item per buyer (`buyer_id`, ADR-0018 rule 3) listing that buyer's open exceptions, and closes exceptions that a run no longer raises. Superseded: one work item per open exception, owned by the buyer; the per-buyer list is a query ([ADR-0031](0031-design-simplifications.md) rule 17).
22. Conversion:
    - **Grouping.** `ConvertPlannedOrder` takes firmed or proposed planned orders. Purchase orders are grouped by supplier, warehouse, and release date within `conversion_window_days`; transfer orders by route.
    - **Hand-over.** The command sets `converted` and calls the posting interface `inventory.contract.request_replenishment`, which writes one `replenishment_request` with a line per planned order (carrying `origin_planned_order_id`) and emits `ReplenishmentRequested` from `inventory`, so every importer imports downward (ADR-0022 rule 2).
    - **Drafts.** The `purchasing` consumer of `ReplenishmentRequested` groups the request's purchase lines by supplier, warehouse and release window into draft purchase requests (interim, flagged: the default target, following spec 09's request → order chain). `inventory` creates the draft transfer orders itself. Drafts are created as actor `system` on behalf of the converter, follow their own approval (DS-28), and carry `origin_planned_order_id`.
    - **Splits.** A planned order converts whole; a split is two `UpdatePlannedOrder` calls in Phase 1.
    - **Canceled drafts.** When the document lines of a converted order close with `closed_reason` `canceled` (rule 8), the next run sets it `canceled` and may propose again.
    - **Auto-conversion.** Converting under a value threshold by policy is an open question (DS-28). Sending to a supplier always stays a separate approved step.

**Agents, events, queries, performance**

23. The planning agent is the replenishment-suggestions workflow of spec 14; DS-34 designs it. It:
    - explains proposals from pegging and parameters;
    - consolidates proposals against supplier minimums and container capacity held as data;
    - proposes parameter and lead-time changes, with evidence, as approval-bound commands;
    - proposes forecast adjustments, under rule 12;
    - resolves exceptions by drafting.

    It never changes approved data directly. "Approval-bound commands" are change proposals ([ADR-0029](0029-proposals-and-agent-safety.md) rule 5).
24. Events: `ForecastCompleted`, `PlanningCompleted`, `PlannedOrderFirmed`, `PlannedOrderConverted` (from `planning`, for live screens and the audit trail, DS-30); `ReplenishmentRequested` (from `inventory`). Queries: `GetProjectedAvailability`, `ListPlannedOrder`, `ListPegging`, `ListForecast`.
25. Performance target: a regenerative run over 2,000 items × 4 warehouses × a 180-day horizon finishes in 2 minutes or less, using under 2 GB of memory, on the test server. The nightly report records the run time and node count (DS-16, DS-17).

**Build order**

26. Proposed placement, subject to the author's phase decision:

    | When | Work |
    | --- | --- |
    | Step 2 | Parameters, supplier terms, routes, calendars, settings |
    | Step 5 | The first slice: demand and supply read model, `RunPlanning` (reorder point, min/max, net requirements on real demand), planned orders, pegging, conversion, exceptions, weekly forecast |
    | Later in Phase 1 | The later slice: forecast methods by backtest, service-level safety stock, more action messages, the planning agent |
    | Phase 2 | `bill_of_materials` edges |

## Context

- The author's request (2026-11-14); spec 09 had MRP after the MVP, and spec 14 lists "replenishment suggestions" among the next agents.
- Constraints:
  - Principles 12 and 13.
  - ADR-0008's simulation and hashing.
  - ADR-0022's layers.
  - ADR-0023's available stock and reservations.
  - ADR-0007's explicit business dates.
  - Spec 03's accountable human and tainted runs.
- Practice studied, concepts only: SAP (MRP Live, lot sizing, planned orders, exception messages), Business One (MRP recommendations converted to documents), D365 (coverage and action messages) and Odoo (reorder rules).
- ERPMe's own choices:
  - a stable business key per proposal, so work items and explanations survive reruns;
  - exceptions per buyer as work items;
  - lead time split for imports, with transit in calendar days across Tết;
  - forecasts anchored to Tết events, not Gregorian weeks only;
  - conversion through events, so planning stays in layer 4.

## Options considered

| Option | For | Against |
| --- | --- | --- |
| One deterministic engine on an (item, warehouse) graph, with an agent on top (chosen) | Reproducible; trading and manufacturing on one engine; explainable | More design than reorder rules alone |
| Reorder rules only | Simple | No time phasing; poor with long import lead times |
| LLM-proposed quantities | Fluent | Not reproducible (Principle 13) |
| Daily buckets with yearly seasonality | Fine-grained | Needs two years of history; Tết moves |
| Weekly buckets with event indices (chosen) | Works with a year of history; Tết aligned | Coarser within a week |
| Planning above layer 4 | Direct calls | Breaks the layer rule |
| Conversion event owned by `planning`, consumed by `purchasing` and `inventory` | Simple | Consumers would import upward or sideways (ADR-0022 rule 2); grouping across planned orders impossible per event |
| Hand-over through `inventory.contract` (chosen) | Downward imports only; one request groups many orders | One more table |
| Net change in Phase 1 | Faster updates | Doubles the determinism surface; nightly runs suffice for SMEs |

## Constraints that come with the decision

- **Notes in other ADRs:**
  - ADR-0018: "deliberately elsewhere" list.
  - ADR-0019: `supplier_item` beside `partner_item`.
  - ADR-0022: `planning` in layer 4; the `demand_supply_line` read model in `inventory`.
  - ADR-0023: rule 13 cross-reference.
- **DS-04:**
  - Errors: `planning_network_cycle`, `planning_run_in_progress`, `planned_order_not_convertible`.
  - Check results: `planning_parameter_missing`, `forecast_history_insufficient`.
  - `invalid_state_transition` for planned orders.
- **DS-16:** INV-60 (pegging sums exactly), INV-61 (two simulated runs at a check point give equal `output_hash`, and a stored run with the same `input_hash` has that `output_hash`; `not_evaluated` from `erpme-check`), INV-62 (`origin_planned_order_id` kept).
- **DS-17:** business event types `replenishment_planned` (a planner runs planning and converts) and `forecast_adjusted`, from step 5, and `sales_history_recorded` (imported history).
- **ADR-0008 rule 12, DS-04 plan section:** planning results listed, not hashed. **ADR-0022 rule 9:** `RunPlanning` and `RunForecast` registered as long jobs.
- **DS-17:** edge cases EC-41 to EC-45 (import across Tết, intermittent item, supplier minimum excess, transfer network, promotion adjustment).
- **Other design items:**
  - DS-21: `ImportSalesHistory` batch format.
  - DS-22: `demand_supply_line` writes (with `ordered_date`, `closed_reason`), request lines reduced when ordered, `origin_planned_order_id`, the `purchasing` consumer of `ReplenishmentRequested`.
  - DS-28: auto-conversion.
  - DS-29: the buyer work item.
  - DS-33: forecast accuracy, projection.
  - DS-34: the planning agent.
- **Specs:** spec 09, 10 and 14 notes.

## Revisit when

- The regenerative run misses its target: add net change, with an invariant that it equals a regenerative run on the affected subgraph.
- Measured forecast accuracy justifies the later slice's methods, or a further family.

## Documents updated

- **ADRs:** [docs/adr/0018-product-and-item-model.md](0018-product-and-item-model.md), [docs/adr/0019-partners-and-crm-foundation.md](0019-partners-and-crm-foundation.md), [docs/adr/0022-repository-and-engineering-conventions.md](0022-repository-and-engineering-conventions.md), [docs/adr/0023-warehouse-management.md](0023-warehouse-management.md): notes.
- **Spec:**
  - [docs/spec/09-mvp-scope.md](../spec/09-mvp-scope.md), [docs/spec/10-roadmap.md](../spec/10-roadmap.md), [docs/spec/14-agent-workflows.md](../spec/14-agent-workflows.md): notes, marked proposed.
  - [docs/spec/00-reading-guide.md](../spec/00-reading-guide.md): glossary rows, the Firm verb, Convert widened.
- **Design and catalogs:**
  - [docs/design/DS-04-command-envelope.md](../design/DS-04-command-envelope.md): codes.
  - [docs/design/DS-16-invariants-and-harness.md](../design/DS-16-invariants-and-harness.md), [docs/catalogs/invariants.csv](../catalogs/invariants.csv): planning group.
  - [docs/catalogs/edge-cases.csv](../catalogs/edge-cases.csv): EC-41 to EC-45.
  - [docs/design/backlog.md](../design/backlog.md): DS-43 and DS-34 rows.
- **Index:** [docs/adr/README.md](README.md).
- **Open questions:**
  - the building phase and the feature list;
  - which documents count as demand and supply;
  - quality-inspection stock;
  - overdue lines;
  - short source allocation;
  - forecast adjustment approval;
  - the consumption window;
  - the conversion target;
  - service levels and auto-conversion.
- [docs/runbook/step-log.md](../runbook/step-log.md): entry at acceptance.
