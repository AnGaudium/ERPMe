# ADR-0036: Multi-level MRP

Status: accepted (2026-11-14) under ADR-0005, reviewed by Claude Fable 5.2 (builder Claude Opus 5.5). Design item: DS-54 (new). Related decisions: D6. Principles 2, 6, 12, 13. ADR-0005, ADR-0007, ADR-0008, ADR-0022, ADR-0023, ADR-0024, ADR-0029, ADR-0031, ADR-0032, ADR-0033, ADR-0034, ADR-0035. Research: [reference systems](../research/2026-11-14-production/01-reference-systems.md) ("Multi-level MRP"). Lab: [design validation](../reviews/2026-11-14-design-validation/README.md), finding L-08.

## Decision

Planning (ADR-0024) gains bills of materials. The same deterministic, regenerative run now plans made items too:
- it explodes planned production orders into dependent demand, level by level;
- it schedules them on work-center calendars;
- it pegs every requirement to its source.

One pure function of `production` turns (item, warehouse, good quantity, date) into a version, a schedule and components. The run and the conversion into production orders both use it, so a converted order equals its plan.

A leveling proposal shows how to fit overloaded work centers; it never applies itself. The lab prototype checked these properties (finding L-08):
- determinism;
- pegging sums;
- phantom collapse;
- co-product supply;
- make-to-order isolation;
- that converting a planned order does not count component demand twice.

That last check failed until make-to-order supply carried its demand line, a requirement now in rule 9.

### Rules

**The network and the planning order**

1. The planning graph (ADR-0024 rule 16) gets `bill_of_materials` edges.
   - **The edge.** From a made node (item, production warehouse) to each component node (component, issue warehouse; in planning this is the production warehouse), for each planned production order, through the version and revisions rule 3's function selects.
   - **Phantoms.** They are collapsed: their components become edges of the parent at the phantom line's operation.
   - **Co-products and by-products.** They are supply edges.
   - **Exceptions.** A component node without an `item_warehouse_planning` row raises `planning_parameter_missing` with the demand that hit it (ADR-0024 rule 21), and so does a phantom item with sales demand or a planning row. Components at a processor location are supplied through a transfer route from the production warehouse ([ADR-0037](0037-subcontracting.md) rule 2).
2. Acyclic by construction:
   - **No new check needed.** Transfer edges keep the item. Bill of materials edges strictly raise the item's low-level code, which ADR-0033 rule 8 computes over all released revisions, outputs included. So a cycle of the combined network can only be a transfer cycle, which ADR-0024 rule 3 already rejects.
   - **Planning order.** The run plans nodes sorted by (`item_low_level_code` ascending, 0 for items without a row, transfer depth within the item with destinations first, item code, warehouse code). That order is unique and puts every consumer, co-product producers included, before the nodes it feeds.

**Planned production orders**

3. `production.contract.plan_production` is a pure function. Planning calls it in-process, on structures it has loaded in bulk. It has three modes:
   - **`backward`** (item, warehouse, good quantity, `required_date`, `earliest_start`), for new proposals. It selects the version valid on `required_date` for the quantity (ADR-0033 rule 13), as ADR-0034 rule 2 does, and schedules backward. When the start would fall before `earliest_start`, it schedules forward from `earliest_start` and reports the lateness.
   - **`forward`** (item, warehouse, good quantity, start). It selects the version valid on the start, for rule 10 and after `UpdatePlannedOrder` sets a start.
   - **`fixed`** (`production_version_id`, good quantity, start), for firmed and updated orders, conversion and INV-109. It keeps the version and the start.

   **External operations** take their lead times from `supplier_item` and the routes ([ADR-0037](0037-subcontracting.md) rule 3).

   **Explosion.** In every mode it explodes at the resulting start (ADR-0033 rules 5, 6) and returns:
     - the version and revisions;
     - planned start, end and availability dates;
     - the operation schedule;
     - the components with quantities and dates.
   - **Fixed lead time.** A version with lead time method `fixed` has no operation schedule. Its components are due at the start, and it loads no work center.

   Note: mode `backward` selects on `required_date` and requires the version to be valid on the resulting start, else the next version in order, else `production_version_missing` ([ADR-0033](0033-production-master-data.md) rule 5's note) (holistic review 2026-11-15, item P3). `UpdatePlannedOrder` calls the function once, in mode `forward` from the order's start (the new one when it sets one), and stores the selected version and dates; every later run, and conversion, use mode `fixed` with them (holistic review 2026-11-15, item P4).
4. A planned order with `order_type` `production`:
   - **Business key.** Item, warehouse, `need_date` and `sequence` (ADR-0024 rule 18), plus the demand line for `make_to_order` (rule 9). The version is an attribute, not part of the key, so a quantity change keeps the order's identity.
   - **New columns.** `production_version_id`, `planned_start_date`, `planned_end_date`, `availability_date` (planned end + the node's `receiving_days`), and `planned_order_operation` rows.
   - **Dates.**
     - `earliest_start` is max(planning date, the end of the firm fence) + `conversion_lead_days`, in working days of the production warehouse's calendar.
     - A late plan raises `shortage_inside_lead_time` with the days late, and counts supply at its real `availability_date`.
     - `release_date` = planned start − `conversion_lead_days`, a company planning setting for conversion, approval and staging (default 0, flagged).
   - **Lot size.**
     - ADR-0024 rule 15's method applies. Supplier minimums and multiples do not.
     - A quantity above the largest `maximum_lot_quantity` among valid versions is split at that maximum, and each piece selects its own version.
     - A quantity below the smallest minimum is raised to it, and the excess is pegged as `lot_size_excess`.
     - When no version fits at all, the node is skipped from that date on, with one `planning_parameter_missing` exception (reason `production_version_missing`).
5. Dependent demand:
   - **Derived.** It is computed in every run, and again inside `UpdatePlannedOrder`, from rule 3's components:
     - for proposed orders in mode `backward`;
     - for frozen, firmed and updated orders in mode `fixed`, with their stored version and start unchanged.

     A firmed order whose version is no longer valid raises `planning_parameter_missing` with reason `production_version_invalid`. It takes its components from the last revision valid at its start, or none.
   - **Storage.** It is stored as `planned_order_component` rows, rewritten by each run.
   - **Dates.** Each component is due at the scheduled start of its consuming operation.
   - **Pegging.** It pegs to its planned order and component line, through target kind `planned_order` (ADR-0024 rule 20). `ListPegging` gains `depth`.
6. Supply that counts:
   - **Planned production orders** count at `availability_date`. Their co-products and by-products count at the planned end + their own node's `receiving_days` (interim, flagged).
   - **Real production orders** count through their demand and supply lines (ADR-0034 rule 9). Planning adds the node's `receiving_days` to an output supply line's `requested_date` (the order's end), so planned and real supply share one basis.
7. Phantom stock is not netted (interim, flagged; it answers ADR-0033 rule 14's question with an interim).

**Conversion**

8. `ConvertPlannedOrder` for a production planned order runs in one transaction.
   - **The draft.** It calls `production.contract.create_production_order_from_plan`, passing the stored version and planned start. That interface uses rule 3's function in mode `fixed` and writes the draft production order (ADR-0034) as actor `system` on behalf of the converter, with `origin_planned_order_id`. Its output supply line carries `origin_planned_order_id` and its component lines are demand lines.
   - **After conversion.** A converted production planned order contributes neither supply nor dependent demand. ADR-0024 rule 8's "quantity not yet matched" rule does not apply to production orders.
   - **Pegging is never rewritten.** `ListPegging` resolves a converted parent through `origin_planned_order_id`.
   - **Differences.** If the draft's explosion differs from the plan (a revision changed meanwhile), the draft wins and the next run nets again.
   - **Release** follows ADR-0034 rule 5. Auto-conversion and auto-release are DS-28's (open question).

**Strategy**

9. `item_warehouse_planning.planning_strategy`:
   - **Values.** `make_to_stock` (default) or `make_to_order`. `make_to_order` is allowed only with source `production`, method `net_requirements` and lot size `exact`.
   - **Sales lines.** On a `make_to_order` node, each open sales order demand line is planned on its own. It is netted only against supply linked to that line:
     - production orders whose output supply row carries `for_demand_supply_line_id`, a new column of `demand_supply_line` written from the production order header (ADR-0034 rule 14). It is flagged for the author with the other production columns (ADR-0028 rule 2);
     - planned orders whose key names the line;
     - stock reserved for the line;
     - the linked orders' output still in inspection, read through `production.contract.get_order_inspection_quantities`.

     ADR-0024 rule 9 gets a note: make-to-order netting reads reservations for its own line only. Make-to-stock netting on the node leaves out the stock reserved for make-to-order lines, their inspection stock and their linked supply, so nothing counts twice.

     Saving another combination is rejected with `make_to_order_not_allowed`.
   - **Other demand.** Dependent demand, transfer demand and safety stock on a `make_to_order` node are netted together as `make_to_stock` (interim, flagged). A make-to-order subassembly therefore behaves as make-to-stock unless it has sales lines of its own.
   - **Assemble to order.** Components follow their own nodes' strategy.
   - **Status.** The strategies and their defaults are the author's (open question).

   Configured items get `make_to_order` rows when they are created ([ADR-0046](0046-product-configuration.md) rule 11).

   Note: a sales order line whose item has no planning row in the line's warehouse, while the item has a `make_to_order` row in another warehouse, is rejected with `make_to_order_warehouse_mismatch`; configurable lines already get `configuration_warehouse_not_produced` ([ADR-0046](0046-product-configuration.md) rule 10). Independently, a run raises `planning_parameter_missing` with reason `planning_row_missing` for every node that has open demand lines and no `item_warehouse_planning` row, whatever the item, so no demand stays unplanned silently. Phantoms keep rule 1 (holistic review 2026-11-15, item P5).

**Reorder point and min-max across levels**

10. For nodes on `reorder_point` or `min_max` (ADR-0024 rule 14):
    - **Inventory position.** Dependent demand counts only inside the node's replenishment lead time (interim, flagged). For a made node, that lead time is its fixed days, or its schedule with the lot quantity.
    - **Made nodes on these methods.** Scheduled forward from the planning date with the lot quantity through rule 3's function. `need_date` is the resulting availability date.

**Capacity**

11. Load:
    - **Real orders.** `ListWorkCenterLoad` (ADR-0034 rule 3, layer 3) stays limited to real orders.
    - **With planned orders.** Planning adds `ListCapacityLoad` (work center, bucket, horizon), combining it with the hours of proposed and firmed planned production orders that have an operation schedule.
    - **Buckets.** The size is the company planning setting `capacity_bucket` (`day` or `week`, default `week`). Only `is_capacity_relevant` work centers count.
    - **Overload.** `capacity_overload` is raised once per work center and contiguous range of overloaded buckets, with the buckets as evidence. It becomes one work item owned by `planning_owner_id` (ADR-0031 rule 17).

    Note ([ADR-0068](0068-sites-and-core-logistics-payment-master-data.md), 2026-11-21): `ListCapacityLoad` also accepts a resource group. `capacity_overload` stays per work center, and its evidence adds the group's spare hours.
12. `GetCapacityLevelingProposal` (work center, horizon) is a planning query.
    - **The schedule.** It schedules the remaining operations forward on available hours in a total order: in progress, released, firmed planned, draft, proposed; then need date; then order number or business key (interim, flagged).
    - **Output.** For each order, a new start date, the resulting end date and the lateness.
    - **Effect.** It changes nothing.
    - **Applying it.** A planner applies it by `UpdatePlannedOrder` (production planned orders may change quantity and planned start; `need_date` stays, and the change implies firming), or by an update or change order (ADR-0034 rule 8).
    - **Agents.** The planning agent drafts the application as a change proposal. `UpdatePlannedOrder`, `FirmPlannedOrder` and `ConvertPlannedOrder` are `is_proposal_bound` for all planned order types (ADR-0029 rules 2 and 5). A planned order's `expected_version` is the SHA-256 of its canonical key, quantity, dates, version and state. The agent never applies directly.
    - **Later.** Finite scheduling inside the run, and rough-cut planning, come after Phase 1 (open question).

    The planning agent's proposals: [ADR-0051](0051-agent-workflows.md) rule 24.

    Note ([ADR-0068](0068-sites-and-core-logistics-payment-master-data.md), 2026-11-21): the leveling proposal may move operations to a member of the same resource group with spare hours. A proposal is never applied without approval.

**Performance, inputs and checks**

13. Performance and inputs:
    - **Target.** A regenerative run for 20,000 nodes, five levels and two years of daily buckets finishes within 10 minutes and 4 GB of memory, leaving headroom under the 15-minute long-job limit (ADR-0022 rule 9). DS-16's long profile measures it on the large synthetic dataset, including the manufacturing company (ADR-0032 rule 6). ADR-0024 rule 25 gets a note.
    - **Loading.** Structures are loaded once in bulk, and the run calls pure functions in-process, never one contract call per order.
    - **Input hash.** `input_hash` (ADR-0024 rule 17) also covers versions, revision `content_hash`, work centers, calendars and planning settings.
    - **Partial scope.** A run limited to `scope` items includes their component closure. Out-of-scope planned orders' stored `planned_order_component` rows count unchanged.
    - **Snapshot.** The run reads all structures at one snapshot (repeatable read) and takes no lock on `production_structure`, so releases never wait for it. `input_hash` records what it read.
14. Catalog rows reserved in the production range (ADR-0033 rule 16):
    - **INV-109:** each proposed, frozen or firmed planned production order's `planned_order_component` rows equal rule 3's function at its stored dates and quantity.
    - **INV-110:** a converted production planned order contributes no supply or dependent demand to the latest run.
    - **Edge cases:**
      - a three-level make-to-stock structure with a phantom;
      - a make-to-order assembly with make-to-stock components;
      - a conversion followed by a run, with no double counting;
      - a start in the past, scheduled forward;
      - a lot above the largest version, split;
      - a co-product counted as supply;
      - an overload and its leveling proposal;
      - a reorder-point component under a made parent.
    - **Parallel test:** PAR-14, a run against a concurrent bill of materials release and a conversion.

## Context

ADR-0024 designed planning per (item, warehouse) and left bills of materials for later. ADR-0032 moved production into Phase 1. The research notes give the mechanics:
- low-level codes;
- gross-to-net;
- lot sizing;
- lead-time offsetting;
- pegging;
- firm fences;
- an SME capacity minimum.

NativeFlows keeps one deterministic run over one network, so the planning agent explains every number from pegging. The lab prototype showed that make-to-order breaks on conversion unless the real order's supply is linked to its demand line, which rule 9 now requires. The review showed that the cross-kind cycle check is redundant (rule 2), and that the run and the conversion must share one planning function (rule 3).

## Options considered

| Option | For | Against |
| --- | --- | --- |
| One run over transfer and bill of materials edges (chosen) | One engine, one order, explainable pegging | Bulk loading and pure functions are needed for speed |
| Separate MRP per level | Simple to describe | Inconsistent with transfers; no single pegging |
| One shared planning function for runs and conversion (chosen) | Converted orders equal their plans | Production exposes a pure planning interface |
| Make to order through order-specific stock | SAP's sales order stock | A new stock axis; the demand line link is enough |
| Finite scheduling in the run | Feasible plans | Heavy; leveling proposals suffice in Phase 1 |

## Constraints that come with the decision

- **ADR notes:**
  - ADR-0022 rule 2 (planning imports `production.contract`);
  - ADR-0024 rules 1, 8, 9, 14, 16, 17, 18, 20, 21, 22, 24, 25;
  - ADR-0029 rule 5 (agents propose planned order changes);
  - ADR-0033 rule 14 (phantom stock interim);
  - ADR-0034 rules 2, 3, 9, 14 and 18 (the shared planning function, real-order load only, the supply link, the contract interfaces);
  - ADR-0024 rules 7, 19, 22, 23 (settings, `earliest_start`, proposal-bound planned order commands);
  - ADR-0028 rule 2 (the `for_demand_supply_line_id` column).
- **DS-04:** `planned_order_not_convertible` widened (the version is missing or inactive); `make_to_order_not_allowed`.
- **Glossary:** planning strategy, make to order, dependent demand, capacity overload, leveling proposal, availability date.
- **Other design items:** DS-34 (planning agent), DS-16 (long profile), DS-17 (planning data of the manufacturing company).
- **Open questions:**
  - co-product supply;
  - phantom stock;
  - strategies and their defaults;
  - other demand on make-to-order nodes;
  - dependent demand under reorder point;
  - `conversion_lead_days`;
  - the leveling priority;
  - finite scheduling and rough-cut planning;
  - auto-conversion and auto-release.

## Revisit when

- The run misses the performance target.
- A target customer needs finite scheduling or rough-cut planning in Phase 1.

## Documents updated

- **ADRs:** [docs/adr/0022-repository-and-engineering-conventions.md](0022-repository-and-engineering-conventions.md), [docs/adr/0024-planning.md](0024-planning.md), [docs/adr/0029-proposals-and-agent-safety.md](0029-proposals-and-agent-safety.md), [docs/adr/0033-production-master-data.md](0033-production-master-data.md), [docs/adr/0034-production-orders-and-shop-floor.md](0034-production-orders-and-shop-floor.md): notes.
- **Design:** [docs/design/DS-04-command-envelope.md](../design/DS-04-command-envelope.md), [docs/design/backlog.md](../design/backlog.md).
- **Validation:** [docs/reviews/2026-11-14-design-validation/README.md](../reviews/2026-11-14-design-validation/README.md).
- **Glossary:** [docs/spec/00-reading-guide.md](../spec/00-reading-guide.md).
- **Open questions:** [docs/open-questions.md](../open-questions.md).
- **Index and log:** [docs/adr/README.md](README.md); [docs/runbook/step-log.md](../runbook/step-log.md) at acceptance.
