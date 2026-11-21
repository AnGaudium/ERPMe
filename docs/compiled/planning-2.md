Module: planning    Chunk: 2 of 2    Source ADRs: ADR-0024, ADR-0025, ADR-0027, ADR-0031, ADR-0036, ADR-0056, ADR-0064, ADR-0068, ADR-0071
Build step(s): 0, 1, 2, 4, 5, 5b    Generated from index: 30d5706    Compiled by: Claude Fable 5.2, 2026-11-21

# Compiled spec: `planning`, chunk 2

## Purpose

`planning` owns planning parameters, supplier terms, forecasts, planning runs, planned orders, pegging and planning
exceptions (ADR-0024). Chunk 1 states the single-level run. This chunk states multi-level MRP (ADR-0036): the same
deterministic, regenerative run plans made items too. It explodes planned production orders into dependent demand, level
by level, schedules them on work-center calendars and pegs every requirement to its source. One pure function of
`production` turns (item, warehouse, good quantity, date) into a version, a schedule and components; the run and the
conversion into production orders both use it, so a converted order equals its plan. A leveling proposal shows how to fit
overloaded work centers and never applies itself. The chunk also states the planning agent's frame, the events and
queries, the supplier item commands and order unit, capacity load, the exceptions on real production orders and the
build placement. Production orders, structures and the agent runtime belong to `production` and `agents`; their units
are traced `ref:` and not restated.

## Entities and tables

DDL: `docs/design/DS-43-54-planning-production.sql`.

| Table | Meaning | Key | Parent | Owner |
| --- | --- | --- | --- | --- |
| `planned_order_component` | Dependent demand of a production planned order: one row per component line, rewritten by each run and by `UpdatePlannedOrder` (R230) | `id`; unique (`planned_order_id`, `line_number`) | `planned_order` | `planning` |
| `planned_order_operation` | The operation schedule that `plan_production` returns for a production planned order (R226); `work_center_id` is null for an `external` operation | `id`; unique (`planned_order_id`, `operation_number`) | `planned_order` | `planning` |

Rules of this chunk add to, or constrain, tables whose rows stand in chunk 1:

- `planned_order`: `production_version_id`, `planned_start_date`, `planned_end_date`, `availability_date`, `for_demand_supply_line_id` and `release_date` for `order_type` `production` (R225-R227); `order_quantity`, `order_uom_id`, the unit snapshot and `rounding_excess_quantity` (R209).
- `item_warehouse_planning`: `planning_strategy` (R237); `receiving_days` (R226, R232).
- `supplier_item`: `order_uom_id` (R208); the fields `UpdateSupplierItem` changes (R206).
- `supplier_item_lead_time`: read by the planning agent's lead-time comparison (ADR-0051.R24.N1).
- `planning_setting`: `conversion_lead_days` (R227), `capacity_bucket` (R243), `planning_owner_id` (R204, R244).
- `planning_exception`: the kinds `capacity_overload`, `production_order_start_overdue` and `production_order_overdue`, the reasons of `planning_parameter_missing` and the column `production_order_id` (R217, R244, R258, R262).
- `planning_action_message`: messages on a production order's main-output supply line (R258).
- `planned_order_pegging`: target kind `planned_order` with the component line (R231).
- `transfer_route`: `lead_time_days` inside one site (R205); also the return route from a processor location (ADR-0037.R3.N1).

Reads: `demand_supply_line` (`for_demand_supply_line_id`, `origin_planned_order_id`), `production_order`, `production_version`, `production_structure`, `work_center`, `item_production_setting`, `item_low_level_code`, `stock_reservation`, `operation_confirmation`, `product_uom`, `uom`, `partner_item`, `warehouse`, `item`.

## Commands and queries

| Name | Actor and authorization | Input | Effect | Events | Error codes |
| --- | --- | --- | --- | --- | --- |
| `UpdateSupplierItem` | Leaf `supplier_item` under the area `planning`, level `edit`; an allowed target of change proposals | `supplier_item_id`, the fields to change, optional `expected_version` | Effect class `master_data_change`, change-tracked (R206) | not stated | not stated |
| `CreateSupplierItem` | Leaf `supplier_item` under `planning`, level `edit` | The columns of `supplier_item` that `UpdateSupplierItem` does not take (R207) | Effect class `master_data_change` | not stated | not stated |
| `CreateTransferRoute` | not stated | `lead_time_days` may be omitted inside one site (R205) | Creates a `transfer_route` | not stated | not stated |
| `ListPlannedOrder` (query) | area not stated | not stated | not stated (R213) | none | not stated |
| `ListPegging` (query) | area not stated | `depth`; otherwise not stated | Resolves a converted parent through `origin_planned_order_id` (R231, R235) | none | not stated |
| `ListForecast` (query) | area not stated | not stated | not stated (R213) | none | not stated |
| `ListCapacityLoad` (query) | not stated | Work center or resource group, bucket, horizon | Load of real orders plus proposed and firmed planned production orders, and available hours (R243, R245) | none | not stated |
| `GetCapacityLevelingProposal` (query) | not stated | Work center, horizon | A forward schedule per order; changes nothing (R246) | none | not stated |
| `GetProductionOrderPegging` (computed query) | `production_order` at `read` | A production order or one of its component lines | Upward pegging to end demand (R253) | none | not stated |
| `ListShortageResolutionCandidate` (computed query) | `production_order` at `read` | A production order with a component shortage | At most 7 candidates of the enabled kinds (R254-R256) | none | not stated |
| `GetProductionOrderTree` (computed query) | `production_order` at `read` | A production order | The sub-assembly tree below it; nothing is stored (R263) | none | not stated |

Commands whose rows stand in chunk 1 and which rules of this chunk extend: `RunPlanning` (R219, R250, R251), `UpdatePlannedOrder` (R221, R247), `FirmPlannedOrder` (R248) and `ConvertPlannedOrder` (R234-R236). `UpdatePlannedOrder`, `FirmPlannedOrder` and `ConvertPlannedOrder` are `is_proposal_bound` (R248); their leaf is `planned_order` under `planning`.

The query `GetProjectedAvailability`, named by R213, has its row in chunk 1.

Events (R212): `ForecastCompleted`, `PlanningCompleted`, `PlannedOrderFirmed`, `PlannedOrderConverted` from `planning`; `ReplenishmentRequested` from `inventory`.

Not commands: the pure function `production.contract.plan_production` (R220-R224), the interfaces `production.contract.create_production_order_from_plan` (R234) and `production.contract.get_order_inspection_quantities` (R238), all declared by `production`; the consumer `planning_work_items` (R215, R259).

Codes bound to no command of this chunk: `make_to_order_not_allowed` (saving a planning row, R237), `make_to_order_warehouse_mismatch` (a sales order line, R240), `production_version_missing` (R220).

Authorization areas of the module (`authorization-areas.csv`): the area `planning` with the leaves `planning_run`, `planned_order`, `forecast` and `supplier_item`. The role templates with a Planning level that reaches `edit` are `buyer`, `purchasing_manager`, `production_planner` and `owner` (R207).

## Rules

### Placement and ownership

R201. Build placement of planning:
   - Step 2: parameters, supplier terms, routes, calendars, settings.
   - Step 5, the first slice: the demand and supply read model, `RunPlanning` (reorder point, min/max, net requirements on real demand), planned orders, pegging, conversion, exceptions, the weekly forecast.
   - Step 5b, Planning and multi-level MRP: the later slice (forecast methods by backtest, service-level safety stock, more action messages) and multi-level MRP with `bill_of_materials` edges (ADR-0036). It starts after the gates of steps 5 and 4b and may run beside steps 6 and 7.
   Source: ADR-0024.R26, ADR-0024.R26.N2

R202. The planning agent is a Phase 1 agent type (ADR-0078.R1). It starts after the step 5b gate, that is after the manual path of planning with multi-level MRP is built and has passed its gate.
Source: ADR-0024.R26.N1, ADR-0024.R26.N2

R203. Planning's design is ADR-0024. Bills of materials are one more edge type of the planning graph, and one more node and edge kind in the later-phase seams of ADR-0025.
Source: ADR-0025.R9

R204. Requested planning runs act on behalf of the requester, scheduled runs on behalf of `planning_owner_id`. Forecast history of goods sold from `goods_sent` warehouses is attributed to their valuation warehouse. The transfer into the `goods_sent` warehouse stays excluded as dependent demand, so nothing is counted twice.
Source: ADR-0027.R15

R205. Planning runs per (item, warehouse). `CreateTransferRoute` may omit `lead_time_days` only when both warehouses lie in the same site, and the route then gets 0. Between sites the value stays required. Site-level pooled planning is an open question for after Phase 1.
Source: ADR-0068.R11

### Supplier items

R206. `UpdateSupplierItem` (module `planning`, effect class `master_data_change`, change-tracked, with the optional `expected_version` of ADR-0029.R2) updates a supplier item, lead times included. It takes `supplier_item_id` and the fields to change among `supplier_processing_days`, `transit_days`, `minimum_order_quantity`, `order_multiple`, `is_preferred` and `end_date`. Its effect class makes it an allowed target of change proposals, so the planning agent proposes it and a person approves it: measured lead times are never applied without approval.
Source: ADR-0024.R23.N1

R207. `CreateSupplierItem` takes the other columns of `supplier_item`, with the same module and effect class. `CreateSupplierItem` and `UpdateSupplierItem` need `edit` on the leaf `supplier_item` under the Planning area (`authorization-areas.csv`), so a role's Planning level applies: the templates `buyer`, `purchasing_manager`, `production_planner` and `owner`.
Source: ADR-0024.R23.N1

R208. `supplier_item.order_uom_id`, NOT NULL, is the supplier's order unit: any unit the item resolves (ADR-0056.R6). The command proposes the product's purchase unit when the row is created. `minimum_order_quantity` and `order_multiple` are in that unit. There are no supplier-specific factors: a supplier whose carton holds 20 instead of 24 gets its own product unit (`x-carton-20`), so one item and unit always have one factor.
Source: ADR-0056.R14

R209. Planning nets in inventory units. For a purchase proposal it converts the shortfall exactly into the order unit, rounds up to the minimum and the multiple there (ADR-0024.R15), and converts the order quantity back with `half_up`, as the purchase order line will (ADR-0056.R9). It stores `order_quantity`, `order_uom_id` and the snapshot on the planned order, with `quantity` (the inventory unit) and `rounding_excess_quantity`.
Source: ADR-0056.R14

R210. The replenishment request line and the purchase request line carry the order unit and its snapshot. A purchase order copied from a request keeps the request's unit unless the person changes it.
Source: ADR-0056.R14

### Planning agent, events, queries, performance

R211. The planning agent is the replenishment-suggestions workflow of spec 14, designed in ADR-0051.R23 to ADR-0051.R25. It explains proposals from pegging and parameters; consolidates proposals against supplier minimums and container capacity held as data; proposes parameter and lead-time changes, with evidence, as change proposals (ADR-0029.R5); proposes forecast adjustments under ADR-0024.R12; and resolves exceptions by drafting. Its planned order changes are change proposals (R248). It never changes approved data directly.
Source: ADR-0024.R23

R212. Events from `planning`, for live screens and the audit trail: `ForecastCompleted`, `PlanningCompleted`, `PlannedOrderFirmed`, `PlannedOrderConverted`. `ReplenishmentRequested` comes from `inventory`.
Source: ADR-0024.R24

R213. Planning queries: `GetProjectedAvailability`, `ListPlannedOrder`, `ListPegging` (with `depth`), `ListForecast`, `ListCapacityLoad` and `GetCapacityLevelingProposal`.
Source: ADR-0024.R24

R214. Performance target without bills of materials: a regenerative run over 2,000 items × 4 warehouses × a 180-day horizon finishes in 2 minutes or less, using under 2 GB of memory, on the test server. The nightly report records the run time and node count (DS-16, DS-17). With bills of materials R250 holds.
Source: ADR-0024.R25

R215. The consumer `planning_work_items` keeps one work item per open planning exception, not per buyer, and closes those that a run no longer raises (ADR-0024.R21). The interim of ADR-0023.R21 before step 5 stands.
Source: ADR-0031.R17

### Planning graph with bills of materials

R216. The planning graph (ADR-0024.R16) has `bill_of_materials` edges: from a made node (item, production warehouse) to each component node (component, issue warehouse; in planning this is the production warehouse), for each planned production order, through the version and revisions that `plan_production` selects. Phantoms are collapsed: their components become edges of the parent at the phantom line's operation. Co-products and by-products are supply edges. Components at a processor location are supplied through a transfer route from the production warehouse (ADR-0037.R2).
Source: ADR-0036.R1

R217. A component node without an `item_warehouse_planning` row raises `planning_parameter_missing` with the demand that hit it (ADR-0024.R21), and so does a phantom item with sales demand or a planning row.
Source: ADR-0036.R1

R218. The combined network is acyclic by construction and needs no new check. Transfer edges keep the item. Bill of materials edges strictly raise the item's low-level code, which ADR-0033.R8 computes over all released revisions, outputs included. So a cycle can only be a transfer cycle, which ADR-0024.R3 rejects.
Source: ADR-0036.R2

R219. The run plans nodes sorted by (`item_low_level_code` ascending, 0 for items without a row; transfer depth within the item with destinations first; item code; warehouse code). That order is unique and puts every consumer, co-product producers included, before the nodes it feeds.
Source: ADR-0036.R2

### The function `plan_production`

R220. `production.contract.plan_production` is a pure function. Planning calls it in-process, on structures it has loaded in bulk. Mode `backward` (item, warehouse, good quantity, `required_date`, `earliest_start`) serves new proposals. It selects the version on `required_date` for the quantity (ADR-0033.R13), as ADR-0034.R2 does, and requires the version to be valid on the resulting start, else the next version in order, else `production_version_missing` (ADR-0033.R5). It schedules backward; when the start would fall before `earliest_start`, it schedules forward from `earliest_start` and reports the lateness.
Source: ADR-0036.R3, ADR-0036.R3.N1

R221. Mode `forward` (item, warehouse, good quantity, start) selects the version valid on the start. It serves R242, and `UpdatePlannedOrder`, which calls the function once, in mode `forward` from the order's start (the new one when it sets one), and stores the selected version and dates.
Source: ADR-0036.R3, ADR-0036.R3.N1

R222. Mode `fixed` (`production_version_id`, good quantity, start) keeps the version and the start. It serves firmed and updated orders in every later run, conversion and `INV-109`.
Source: ADR-0036.R3, ADR-0036.R3.N1

R223. In every mode `plan_production` explodes at the resulting start (ADR-0033.R5, ADR-0033.R6) and returns the version and revisions; the planned start, end and availability dates; the operation schedule; and the components with quantities and dates. A version with lead time method `fixed` has no operation schedule: its components are due at the start, and it loads no work center.
Source: ADR-0036.R3

R224. External operations take their lead times from `supplier_item` and the routes (ADR-0037.R3).
Source: ADR-0036.R3

### Production planned orders

R225. A planned order with `order_type` `production` has the business key item, warehouse, `need_date` and `sequence` (ADR-0024.R18), plus the demand line for `make_to_order` (R238). The version is an attribute, not part of the key, so a quantity change keeps the order's identity.
Source: ADR-0036.R4

R226. A production planned order carries `production_version_id`, `planned_start_date`, `planned_end_date`, `availability_date` (planned end + the node's `receiving_days`), and `planned_order_operation` rows.
Source: ADR-0036.R4

R227. Dates of a production planned order:
   - `earliest_start` is max(planning date, the end of the firm fence) + `conversion_lead_days`, in working days of the production warehouse's calendar.
   - A late plan raises `shortage_inside_lead_time` with the days late, and counts supply at its real `availability_date`.
   - `release_date` = planned start − `conversion_lead_days`, a company planning setting for conversion, approval and staging (default 0, flagged).
   Source: ADR-0036.R4

R228. Lot size of a production planned order:
   - The lot-size method of ADR-0024.R15 applies. Supplier minimums and multiples do not.
   - A quantity above the largest `maximum_lot_quantity` among valid versions is split at that maximum, and each piece selects its own version.
   - A quantity below the smallest minimum is raised to it, and the excess is pegged as `lot_size_excess`.
   - When no version fits at all, the node is skipped from that date on, with one `planning_parameter_missing` exception (reason `production_version_missing`).
   Source: ADR-0036.R4

R229. Dependent demand is derived from the components `plan_production` returns. Every run computes it: for proposed orders in mode `backward`; for frozen, firmed and updated orders in mode `fixed`, with their stored version and start unchanged. `UpdatePlannedOrder` computes it again, through its one call in mode `forward` (R221). A firmed order whose version is no longer valid raises `planning_parameter_missing` with reason `production_version_invalid`; it takes its components from the last revision valid at its start, or none.
Source: ADR-0036.R5, ADR-0036.R3.N1

R230. Dependent demand is stored as `planned_order_component` rows, rewritten by each run. Each component is due at the scheduled start of its consuming operation.
Source: ADR-0036.R5

R231. Dependent demand pegs to its planned order and component line, through target kind `planned_order` (ADR-0024.R20). `ListPegging` has the parameter `depth`.
Source: ADR-0036.R5

R232. Supply that counts:
   - Planned production orders count at `availability_date`. Their co-products and by-products count at the planned end + their own node's `receiving_days` (interim, flagged).
   - Real production orders count through their demand and supply lines (ADR-0034.R9). Planning adds the node's `receiving_days` to an output supply line's `requested_date` (the order's end), so planned and real supply share one basis.
   Source: ADR-0036.R6

R233. Phantom stock is not netted (interim, flagged; the interim answer to the question of ADR-0033.R14).
Source: ADR-0036.R7

### Conversion into production orders

R234. `ConvertPlannedOrder` for a production planned order runs in one transaction. It calls `production.contract.create_production_order_from_plan`, passing the stored version and planned start. That interface uses `plan_production` in mode `fixed` and writes the draft production order (ADR-0034) as actor `system` on behalf of the converter, with `origin_planned_order_id`. The draft's output supply line carries `origin_planned_order_id` and its component lines are demand lines.
Source: ADR-0036.R8

R235. A converted production planned order contributes neither supply nor dependent demand (`INV-110`). The "quantity not yet matched" rule of ADR-0024.R8 does not apply to production orders. Pegging is never rewritten: `ListPegging` resolves a converted parent through `origin_planned_order_id`.
Source: ADR-0036.R8

R236. If the draft's explosion differs from the plan because a revision changed meanwhile, the draft wins and the next run nets again. Release follows ADR-0034.R5. Auto-conversion and auto-release are DS-28's (open question).
Source: ADR-0036.R8

### Planning strategy

R237. `item_warehouse_planning.planning_strategy` is `make_to_stock` (default) or `make_to_order`. `make_to_order` is allowed only with source `production`, method `net_requirements` and lot size `exact`; saving another combination is rejected with `make_to_order_not_allowed`. Configured items get `make_to_order` rows when they are created (ADR-0046.R11). The strategies and their defaults are the author's (open question).
Source: ADR-0036.R9

R238. On a `make_to_order` node, each open sales order demand line is planned on its own. It is netted only against supply linked to that line:
   - production orders whose output supply row carries `for_demand_supply_line_id`, a column of `demand_supply_line` written from the production order header (ADR-0034.R14), flagged for the author with the other production columns (ADR-0028.R2);
   - planned orders whose key names the line;
   - stock reserved for the line;
   - the linked orders' output still in inspection, read through `production.contract.get_order_inspection_quantities`.
   Source: ADR-0036.R9

R239. Make-to-order netting reads reservations for its own line only (ADR-0024.R9). Make-to-stock netting on the node leaves out the stock reserved for make-to-order lines, their inspection stock and their linked supply, so nothing counts twice. Dependent demand, transfer demand and safety stock on a `make_to_order` node are netted together as `make_to_stock` (interim, flagged); a make-to-order subassembly therefore behaves as make-to-stock unless it has sales lines of its own. In assemble to order, components follow their own nodes' strategy.
Source: ADR-0036.R9

R240. A sales order line whose item has no planning row in the line's warehouse, while the item has a `make_to_order` row in another warehouse, is rejected with `make_to_order_warehouse_mismatch`; configurable lines get `configuration_warehouse_not_produced` (ADR-0046.R10).
Source: ADR-0036.R9.N1

R241. A run raises `planning_parameter_missing` with reason `planning_row_missing` for every node that has open demand lines and no `item_warehouse_planning` row, whatever the item, so no demand stays unplanned silently. Phantoms keep R217.
Source: ADR-0036.R9.N1

R242. For nodes on `reorder_point` or `min_max` (ADR-0024.R14), dependent demand counts in the inventory position only inside the node's replenishment lead time (interim, flagged). For a made node, that lead time is its fixed days, or its schedule with the lot quantity. Made nodes on these methods are scheduled forward from the planning date with the lot quantity through `plan_production`; `need_date` is the resulting availability date.
Source: ADR-0036.R10

### Capacity load and leveling

R243. `ListWorkCenterLoad` (ADR-0034.R3, layer 3) stays limited to real orders. Planning adds `ListCapacityLoad` (work center, bucket, horizon), which combines that load with the hours of proposed and firmed planned production orders that have an operation schedule. The bucket size is the company planning setting `capacity_bucket` (`day` or `week`, default `week`). Only `is_capacity_relevant` work centers count.
Source: ADR-0036.R11

R244. The exception `capacity_overload` is raised once per work center and contiguous range of overloaded buckets, with the buckets as evidence. It becomes one work item owned by `planning_owner_id` (R215). It stays per work center when a resource group is used, and its evidence adds the group's spare hours.
Source: ADR-0036.R11, ADR-0036.R11.N1, ADR-0068.R13

R245. Routing operations keep their primary work center (ADR-0033.R10). `ListWorkCenterLoad` and `ListCapacityLoad` accept a resource group in place of a work center. They return the load and the available hours, each summed over the members, with each member's hours computed by ADR-0033.R11.
Source: ADR-0068.R13, ADR-0036.R11.N1

R246. `GetCapacityLevelingProposal` (work center, horizon) is a planning query and changes nothing. It schedules the remaining operations forward on available hours in a total order: in progress, released, firmed planned, draft, proposed; then need date; then order number or business key (interim, flagged). For each order it returns a new start date, the resulting end date and the lateness. It may propose moving operations to a member of the same resource group with spare hours. A proposal is never applied without approval.
Source: ADR-0036.R12, ADR-0036.R12.N1, ADR-0068.R13

R247. A planner applies a leveling proposal by `UpdatePlannedOrder`, or by an update or change order of a real production order (ADR-0034.R8). On a production planned order `UpdatePlannedOrder` may change quantity and planned start; `need_date` stays, and the change implies firming.
Source: ADR-0036.R12

R248. The planning agent drafts the application of a leveling proposal as a change proposal (ADR-0051.R24) and never applies directly. `UpdatePlannedOrder`, `FirmPlannedOrder` and `ConvertPlannedOrder` are `is_proposal_bound` for all planned order types (ADR-0029.R2, ADR-0029.R5). A planned order's `expected_version` is the SHA-256 of its canonical key, quantity, dates, version and state.
Source: ADR-0036.R12

R249. Finite scheduling inside the run, and rough-cut planning, come after Phase 1 (open question).
Source: ADR-0036.R12

### Performance and inputs of the multi-level run

R250. Target: a regenerative run for 20,000 nodes, five levels and two years of daily buckets finishes within 10 minutes and 4 GB of memory, leaving headroom under the 15-minute long-job limit (ADR-0022.R9). DS-16's long profile measures it on the large synthetic dataset, including the manufacturing company (ADR-0032.R6). Structures are loaded once in bulk, and the run calls pure functions in-process, never one contract call per order.
Source: ADR-0036.R13

R251. `input_hash` (ADR-0024.R17) also covers versions, revision `content_hash`, work centers, calendars and planning settings. A run limited to `scope` items includes their component closure; out-of-scope planned orders' stored `planned_order_component` rows count unchanged. The run reads all structures at one snapshot (repeatable read) and takes no lock on `production_structure`, so releases never wait for it; `input_hash` records what it read.
Source: ADR-0036.R13

R252. Catalog rows reserved in the production range (ADR-0033.R16): `INV-109` and `INV-110`. Edge cases of multi-level MRP: a three-level make-to-stock structure with a phantom; a make-to-order assembly with make-to-stock components; a conversion followed by a run, with no double counting; a start in the past, scheduled forward; a lot above the largest version, split; a co-product counted as supply; an overload and its leveling proposal; a reorder-point component under a made parent. Parallel test PAR-14: a run against a concurrent bill of materials release and a conversion.
Source: ADR-0036.R14

### Pegging and shortage candidates of real production orders

R253. `GetProductionOrderPegging` (module `planning`, computed query, `production_order` at `read`, since its subject is a production order) gives upward pegging from a production order, or one of its component lines, to end demand.
   - Allocation: the make-to-order link first (`for_demand_supply_line_id`, ADR-0034.R14); then the projection's allocation of supply to demand by date, the rule `ListPegging` uses for planned orders (ADR-0024.R20), level by level through parent orders' component lines.
   - Rows: level, order or demand line, quantity pegged, need date and the days late of the order's planned end against it. The pegged quantities of a level sum to the supply they peg.
   - Agent runs get the numeric projection of ADR-0050.R28, as for `ListPegging`.
   Source: ADR-0064.R8

R254. C3 shortage resolution has the triggers `production_component_shortage` and a planner's run on an order. Its step D1 `candidates` is `ListShortageResolutionCandidate` (module `planning`, computed query, `production_order` at `read`). It computes candidates of the kinds enabled in `production.agent.shortage_candidate_kinds`, each with its computed effect on the order's start date and on pegged demand. Kind, candidate and output when chosen, in kind order:
   - `expedite_supply`: an open supply line whose `expedite` message would cover the shortage; a note to the buyer on the planning exception, and the buyer acts.
   - `stock_transfer`: a warehouse whose available to promise covers the shortage; a draft stock transfer.
   - `alternative_version`: a production version valid on the order's dates whose structure does not use the short component, for orders in `draft` or `pending_approval` only; a draft update of the order (re-explosion).
   - `reschedule`: the earliest start the projection covers, dated by `plan_production` in mode `fixed`; a draft update, or a drafted change order of the dates.
   - `partial_staging`: release with the covered operations staged, where the policy's shortage rank applies; a note to the releaser.
   - `transfer_reservation`: reservations of an order of lower priority (ADR-0064.R7); a change proposal with `TransferStockReservation` (ADR-0064.R24).
   - `split_order`: a change order reducing G to the covered quantity, plus a new draft order for the rest (ADR-0064 decision 6); the drafted change order and the new draft.
   Source: ADR-0064.R16

R255. Selection per candidate kind is deterministic (S = the line's uncovered quantity, d0 = the order's planned start):
   - `expedite_supply`: open purchase or transfer supply lines of the item and warehouse with an `expedite` message of the latest completed planning run whose proposed date is on or before d0; one candidate per line, covering min(S, its open quantity); a message of an older run is not used.
   - `stock_transfer`: per other warehouse of the company with a transfer route to the issue warehouse and available to promise above 0; covering min(S, that available to promise); effect date = business date + the route's lead time.
   - `alternative_version`: per valid version (ADR-0033.R13) that does not use the item, on orders in `draft` or `pending_approval`; covers S; effect date from `plan_production` with the version.
   - `reschedule`: one candidate, the first date on which `GetProjectedAvailability` covers the open requirement, scheduled by `plan_production` in mode `fixed`; none when the projection never covers it within the horizon.
   - `partial_staging`: one candidate when the order still has an uncovered line and at least one operation has every component line uncovered 0; it names those operations, covers 0 of S and keeps d0.
   - `transfer_reservation`: donor reservations, open and unpicked, of approved orders later in the reservation priority; one candidate per donor, covering min(S, its unpicked quantity, the target's short quantity of ADR-0064.R24), that short quantity as of the query; execution recomputes it under the lock (ADR-0064.R24), so the two may differ; the candidate states the donor's resulting short quantity and its pegged demand.
   - `split_order`: one candidate when 0 < covered G < G, covered G = the largest quantity the covered components support (the minimum over the order's lines with required above 0 of (required − uncovered) × G / required, rounded down to the item's unit's decimal places); a fixed-quantity line does not scale with G, so it allows a split only when it is fully covered (uncovered 0), and otherwise no split is offered; lines with required 0 are skipped; the new draft takes G − covered G.
   Source: ADR-0064.R16

R256. Each candidate carries its covered quantity, the resulting start date and the days late of each pegged demand before and after. The total order is: kind in the order of R254; within `transfer_reservation`, the donor's reservation priority, latest donor first; then the resulting start date, the larger covered quantity, document number and line. The returned list holds at most 7: first the best candidate of each enabled kind that has one, in kind order, so no kind is crowded out; then the remaining places filled from the other candidates in the total order. Partial cover is offered and marked.
Source: ADR-0064.R16

R257. Step L1 `choose` (seat analysis) outputs `ProductionChooseOutput`: `candidate` (a handle offered, or `none`), `reason_codes`, `explanation`. It never writes a quantity or date. A person submits every draft; change orders and proposals follow their pools (ADR-0055); a new draft order is released by a person's `Submit`. Alternative versions come only from the version selection function's valid set (ADR-0033.R13). Substitute components stay after Phase 1 (ADR-0064 decision 5; ADR-0033.R17).
Source: ADR-0064.R16

### Exceptions and rescheduling of real production orders

R258. C4 order exceptions and rescheduling. The planning run (ADR-0024.R21) raises these on real production orders and stores them in `planning_exception` and `planning_action_message`:
   - `production_order_start_overdue` (exception, key the order): approved, `not_started`, and `planned_start_date` + `production.order.start_grace_days` is before the planning date.
   - `production_order_overdue` (exception, key the order): approved, not technically complete, and `planned_end_date` + `production.order.overdue_grace_days` is before the planning date.
   - `expedite` (message on the order's main-output supply line, key the supply line): the first need date d the order serves is earlier than its supply date by more than `planning.production_reschedule_in_tolerance_days`.
   - `postpone` (message, key the supply line): the supply date is earlier than its first need by more than `planning.production_reschedule_out_tolerance_days`, within `planning.production_rescheduling_horizon_days`.
   - `cancel` (message, key the supply line): a `not_started` order whose supply the projection never needs within the horizon, including a make-to-order order whose sales line was canceled.
   - `reduce` (message, key the supply line): a `not_started` order whose needed quantity is below G; the proposed quantity is the needed quantity, never below what is posted.
   Source: ADR-0064.R17

R259. One work item `production_order_exception` per order (module `planning`, owner `planning_owner`) lists the order's open exceptions and messages of the latest run; the consumer `planning_work_items` closes it when a run raises none. These exceptions get no `planning_exception` work item, as `capacity_overload` gets its own kind.
Source: ADR-0064.R17

R260. Steps of C4: D1 gathers the messages, pegging and the order's status. D2 computes new dates with `plan_production` in mode `fixed`, groups related messages by pegging, and orders them bottom-up by low-level code, so a component's order is proposed before its parent's. L1 `explain` picks a candidate handle or `none`. D3 drafts the update (draft order) or change order (released order).
Source: ADR-0064.R17

R261. A cancel is never drafted: the note recommends it and a person runs `CancelProductionOrder`, which ADR-0034.R5 allows only before the first posting.
Source: ADR-0064.R17

R262. DDL of ADR-0064 (`DS-43-54-planning-production.sql`, `DS-22-09-42-commercial-inventory.sql`, `DS-36-document-intake.sql`, `DS-35-crm.sql`):
   - `planning_exception`: kinds `production_order_start_overdue` and `production_order_overdue`; column `production_order_id` with its company key, set exactly for those kinds.
   - `operation_confirmation`: `entry_source` (`person`, `capture_agent`, `production_import`; default `person`) and `external_reference`, set exactly for `production_import`, not blank, and unique per company.
   - `stock_reservation`: `transferred_from_reservation_id`, a company key to `stock_reservation`, never the row itself, with the trigger of ADR-0064.R24.
   - The purpose value `shop_floor_report` in `document_reader.purposes`, `document_extraction.purpose`, `extraction_mapping_rule.purpose` and `mailbox.document_intake_purpose`.
   Source: ADR-0064.R27

R263. `GetProductionOrderTree` (module `planning`, computed query, `production_order` at `read`) returns the sub-assembly tree below an MO: for each component line, the production orders whose output supply is pegged to it, by the make-to-order link first, then the projection's allocation (ADR-0024.R20; R253), level by level. Each node shows the MO, pegged quantity, need date, execution state, WOs done of total and any blocked WO. No data is stored; upward pegging stays `GetProductionOrderPegging`.
Source: ADR-0071.R15

## Invariants

Statements are those of `invariants.csv`. This chunk holds the rows whose catalog source is a rule of this chunk; `INV-60` to `INV-63` stand in chunk 1.

| Invariant | Name | Check point | Statement | Protects |
| --- | --- | --- | --- | --- |
| `INV-109` | `planned_components_match_function` | day | Each proposed, frozen or firmed planned production order's `planned_order_component` rows equal `plan_production` at its stored version, dates and quantity. Area `production`; first step pending (ADR-0032.R7: production core step). | R222, R229, R230, R252 |
| `INV-110` | `converted_planned_order_inert` | day | A converted production planned order contributes no supply or dependent demand to the latest run. Area `production`; first step pending (ADR-0032.R7). | R235, R252 |
| `INV-738` | `production_exceptions_on_live_orders` | day | Every `planning_exception` of kind `production_order_start_overdue` or `production_order_overdue` names an order that was approved and not technically complete on the run's planning date, and whose date plus the grace setting was before that date. First step pending (ADR-0032.R7). | R258, R262 |

Named by `ref:` units of this chunk and stated by their own modules: `INV-10`, `INV-603`.

## Edge cases

This chunk holds the rows of area `planning` whose catalog source is a rule of this chunk, and `EC-108`, whose source is a rule of another module; `EC-41` to `EC-45` stand in chunk 1.

| Edge case | Name | Case | Outcome | Rule |
| --- | --- | --- | --- | --- |
| `EC-108` | `bill_of_materials_in_cans` | A component stated in cans of 5 litres with issue multiple 1 can: a requirement of 2.5 cans plans 3 cans, 15 litres, and the difference shows as planned consumption. | `must_succeed` | ADR-0056.R17 |
| `EC-109` | `supplier_order_unit` | A need of 100 pieces from a supplier selling cartons of 24 with minimum 2 and multiple 1 proposes 5 cartons, 120 pieces, with 20 pieces of rounding excess; the request and order keep cartons. | `must_succeed` | R208-R210 |
| `EC-203` | `multi_level_lateness_bottom_up` | A late component order delays its parent; the component order's reschedule is proposed before the parent's, and the dates are consistent. | `must_succeed` | R260 |
| `EC-205` | `reschedule_tolerances` | With an out-tolerance of 3 days a 2-day postponement raises no message, while with the in-tolerance at 0 a 1-day lateness is raised. | `must_succeed` | R258; ADR-0064.R23 |
| `EC-215` | `make_to_order_sales_line_canceled` | The sales line of a not-started make-to-order order is canceled; a cancel message is raised and recommended in a note; the agent never cancels the order. | `must_succeed` | R258, R261 |

## Settings

Rows of `settings.csv` with area `planning` whose source is a rule of this chunk; `planning.cancel_horizon_days` and `planning.container_underfilled_pct` stand in chunk 1. All have storage `setting_value`, effect `immediate` and outdates `none`; the direction is `lower_tighter` for the two tolerances and `neutral` for the horizon.

| Key | Value type | Scope | Core default | Bounds | Leaf | Rule |
| --- | --- | --- | --- | --- | --- | --- |
| `planning.production_reschedule_in_tolerance_days` | integer | company | 0 | 0..30 | `planning_run` | R258 |
| `planning.production_reschedule_out_tolerance_days` | integer | company | 3 | 0..60 | `planning_run` | R258 |
| `planning.production_rescheduling_horizon_days` | integer | company | 60 | 1..365 | `planning_run` | R258 |

The company planning settings `conversion_lead_days` (default 0, flagged; R227) and `capacity_bucket` (`day` or `week`, default `week`; R243) are columns of `planning_setting` and have no row in `settings.csv`.

Reads: `production.order.start_grace_days`, `production.order.overdue_grace_days` (R258), `production.agent.shortage_candidate_kinds` (R254), and, in `ref:` units only, `auto_post.purchase_invoice.min_supplier_invoices`, `auto_post.purchase_invoice.price_tolerance_percent`, `auto_post.purchase_invoice.quantity_tolerance_percent`, `auto_post.purchase_invoice.require_full_receipt`.

## UI annotations

The sources hold no floorplan, title, facet, field annotation or tile of ADR-0077 for this module. Work item kinds of `planning` (`work-item-kinds.csv`):

| Kind | Subject table | Owner | Due | Resolution | Rule |
| --- | --- | --- | --- | --- | --- |
| `production_order_exception` | `production_order` | `planning_owner` | `days:1` | `system`: one per order, closed when a run raises none | R259 |

It is not agent-resolvable. The rows of `planning_exception` (R215) and `capacity_overload` (R244) stand in chunk 1. The planning agent declares `planning_exception` and `capacity_overload` as triggers (ADR-0051.R23).

## Conflicts

CONFLICT ADR-0024.R26: the placement is no longer a proposal subject to the author's phase decision, and `bill_of_materials` edges are no longer Phase 2; ADR-0024.R26.N2 decides step 5b for the later slice and multi-level MRP (R201).
CONFLICT ADR-0024.R26.N1: its sentence that the runbook does not place the planning agent's work yet is replaced; by ADR-0024.R26.N2 the agent starts after the step 5b gate (R202).
CONFLICT ADR-0024.R26.N2: this note governs over the table of rule 26 and over the note before it; build step 5b holds the later slice and multi-level MRP (R201, R202).
CONFLICT ADR-0036.R3: mode `backward` also requires the selected version to be valid on the resulting start, and `UpdatePlannedOrder` always calls mode `forward` once; ADR-0036.R3.N1 governs (R220, R221, R222).
CONFLICT ADR-0036.R5: inside `UpdatePlannedOrder` the components come from one call in mode `forward`, not from mode `fixed`; later runs use mode `fixed` with the stored version and dates; ADR-0036.R3.N1 governs (R229).
CONFLICT ADR-0036.R11: `ListCapacityLoad` also accepts a resource group and the overload evidence adds the group's spare hours; ADR-0036.R11.N1 and ADR-0068.R13 govern (R244, R245).
CONFLICT ADR-0036.R12: the leveling proposal may also move operations to a member of the same resource group; ADR-0036.R12.N1 and ADR-0068.R13 govern (R246).

## Proposed (not law)

None

## Trace

| Source | Where |
| --- | --- |
| ADR-0024.R23 | R211 |
| ADR-0024.R23.N1 | R206, R207 |
| ADR-0024.R24 | R212, R213 |
| ADR-0024.R25 | R214 |
| ADR-0024.R26 | R201 |
| ADR-0024.R26.N1 | R202 |
| ADR-0024.R26.N2 | R201, R202 |
| ADR-0025.R9 | R203 |
| ADR-0027.R15 | R204 |
| ADR-0031.R17 | R49, R215 |
| ADR-0033.R14 | ref: ADR-0033.R14 |
| ADR-0036.D0 | Purpose |
| ADR-0036.R1 | R216, R217 |
| ADR-0036.R2 | R218, R219 |
| ADR-0036.R3 | R220-R224 |
| ADR-0036.R3.N1 | R220, R221, R222, R229 |
| ADR-0036.R4 | R225-R228 |
| ADR-0036.R5 | R229-R231 |
| ADR-0036.R6 | R232 |
| ADR-0036.R7 | R233 |
| ADR-0036.R8 | R234-R236 |
| ADR-0036.R9 | R237-R239 |
| ADR-0036.R9.N1 | R240, R241 |
| ADR-0036.R10 | R242 |
| ADR-0036.R11 | R243, R244 |
| ADR-0036.R11.N1 | R244, R245 |
| ADR-0036.R12 | R246-R249 |
| ADR-0036.R12.N1 | R246 |
| ADR-0036.R13 | R250, R251 |
| ADR-0036.R14 | R252 |
| ADR-0037.R3 | ref: ADR-0037.R3 |
| ADR-0037.R3.N1 | ref: ADR-0037.R3.N1 |
| ADR-0042.R7.N2 | ref: ADR-0042.R7.N2 |
| ADR-0045.R1 | ref: ADR-0045.R1 |
| ADR-0045.R1.N1 | ref: ADR-0045.R1.N1 |
| ADR-0046.R11 | ref: ADR-0046.R11 |
| ADR-0046.R11.N1 | ref: ADR-0046.R11.N1 |
| ADR-0046.R11.N2 | ref: ADR-0046.R11.N2 |
| ADR-0046.R11.N3 | ref: ADR-0046.R11.N3 |
| ADR-0047.R9.N2 | ref: ADR-0047.R9.N2 |
| ADR-0050.R51 | ref: ADR-0050.R51 |
| ADR-0050.R51.N1 | ref: ADR-0050.R51.N1 |
| ADR-0050.R51.N2 | ref: ADR-0050.R51.N2 |
| ADR-0050.R51.N4 | ref: ADR-0050.R51.N4 |
| ADR-0051.R20 | ref: ADR-0051.R20 |
| ADR-0051.R20.N1 | ref: ADR-0051.R20.N1 |
| ADR-0051.R20.N2 | ref: ADR-0051.R20.N2 |
| ADR-0051.R21 | ref: ADR-0051.R21 |
| ADR-0051.R21.N1 | ref: ADR-0051.R21.N1 |
| ADR-0051.R23 | ref: ADR-0051.R23 |
| ADR-0051.R24.N1 | ref: ADR-0051.R24.N1 |
| ADR-0051.R25.N1 | ref: ADR-0051.R25.N1 |
| ADR-0056.D0 | ref: ADR-0056.D0 |
| ADR-0056.R4 | ref: ADR-0056.R4 |
| ADR-0056.R4.N1 | ref: ADR-0056.R4.N1 |
| ADR-0056.R13 | ref: ADR-0056.R13 |
| ADR-0056.R13.N1 | ref: ADR-0056.R13.N1 |
| ADR-0056.R14 | R208-R210 |
| ADR-0056.R23 | ref: ADR-0056.R23 |
| ADR-0064.R8 | R253 |
| ADR-0064.R16 | R254-R257 |
| ADR-0064.R17 | R258-R261 |
| ADR-0064.R27 | R262 |
| ADR-0065.R19 | ref: ADR-0065.R19 |
| ADR-0068.R11 | R205 |
| ADR-0068.R13 | R244, R245, R246 |
| ADR-0071.R15 | R263 |
