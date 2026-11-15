# ADR-0034: Production orders and shop floor

Status: accepted (2026-11-14) under ADR-0005, reviewed by Claude Fable 5.2 (builder Claude Opus 5.5). Design item: DS-52 (new). Related decisions: D6. Principles 2, 3, 6, 8, 12, 13. ADR-0005, ADR-0007, ADR-0008, ADR-0009, ADR-0012, ADR-0013, ADR-0017, ADR-0020, ADR-0022, ADR-0023, ADR-0024, ADR-0025, ADR-0027, ADR-0028, ADR-0029, ADR-0030, ADR-0031, ADR-0032, ADR-0033. Research: [reference systems](../research/2026-11-14-production/01-reference-systems.md), [Vietnamese rules](../research/2026-11-14-production/02-vietnam-rules.md).

## Decision

A production order says: make this good quantity of this item, by this production version, starting on this date. Its execution is recorded by three internal posting documents:
- the issue (and return) of components;
- the confirmation of operations, which can also backflush components;
- the receipt of output.

The order is a non-posting document of module `production` (ADR-0033 rule 1). It reuses what exists:
- the document lifecycle;
- change orders;
- reservations, warehouse tasks and bins;
- the demand and supply read model.

It adds only what production needs:
- an execution state;
- a cost object per order;
- assigned output serials;
- traceability from components to outputs.

| Concept | Decision |
| --- | --- |
| Order types | `standard` (make), `rework` (an item back into itself) and `disassembly` (an item into its components). Discrete and batch work are the same model (ADR-0033) |
| Lifecycle | ADR-0009 non-posting states. Approval releases the order. An execution state runs `not_started` → `in_progress` → `technically_complete`. A system job closes the order once its period is settled and locked |
| Content | Components, outputs and operations are copied from the production version's revisions at the explosion date (ADR-0033 rule 5) and may be edited per order |
| Changes after release | Change orders with a pending version (ADR-0028 rule 4) |
| Postings | `production_issue`, `operation_confirmation`, `production_receipt`: internal, reversible posting documents. Values are DS-53's |
| Warehouse | Components are reserved, then staged by pick tasks to the work center's supply bin, a new non-pickable bin type `production`. Output is received to the output bin, then put away |
| Traceability | Output lots and serials link to the component lots and serials consumed on the order. As built, per unit, through output serials assigned to the order |

### Rules

**The order**

1. `production_order` is a non-posting document type (ADR-0009 rule 6) owned by `production`, registered with `is_change_order_allowed: true` (ADR-0028 rule 4).
   - **Header fields.**
     - `order_type`;
     - `item_id` and `production_warehouse_id`;
     - `document_date`, which sets the numbering year (ADR-0009 rule 8);
     - `production_version_id`, plus `bill_of_materials_revision_id` and `routing_revision_id`, copied as a snapshot;
     - `good_quantity` (G) and `planned_output_quantity` (Q = G / (1 − assembly scrap), ADR-0033 rule 6), in the item's inventory unit;
     - `planned_start_date` (the `explosion_date`) and `planned_end_date`, both dates (ADR-0007);
     - `scheduling_direction`: `forward` or `backward`;
     - `cost_object_id` (rule 15);
     - optional `origin_planned_order_id` (DS-54) and `for_demand_supply_line_id` (make to order, rule 14);
     - `overdelivery_tolerance_percent`.
   - **Lines.** Each line table uses `line_number` as identity (ADR-0028 rule 1).
     - **`production_order_component`:**
       - component item and required quantity;
       - issue warehouse (default: the production warehouse);
       - `operation_number`, `consumption_method`, `is_fixed_quantity`;
       - `phantom_path` (the phantom lines it came through);
       - `requested_date`: the scheduled start of its operation, or the order's start.
     - **`production_order_output`:** main output, co-products and by-products, with planned quantity, `output_type` and `cost_coefficient`. The main output's planned quantity is G. That quantity is the supply for planning and the base for tolerance and completion. Its `requested_date` is the order's end. Output supply rows carry `for_demand_supply_line_id` from the header ([ADR-0036](0036-multi-level-mrp.md) rule 9).
     - **`production_order_operation`:** copied from the routing:
       - work center, control and `is_milestone`;
       - durations, activity standards and scrap rate;
       - `expected_quantity`: Q reduced by the scrap rates of the earlier operations, for information;
       - scheduled start and end dates.
     - **`production_order_output_serial`:** for serial-tracked output, the serials assigned to the order (rule 16). Not version content: it changes after release without a change order.
   - **Version content.** Content excludes `execution_state` and `is_content_edited` (ADR-0009 rule 9).

   An order of a configured item keeps the configuration's ID and the selected, sized lines as its snapshot ([ADR-0046](0046-product-configuration.md) rule 13).
2. Creating and editing:
   - **Explosion.** `CreateProductionOrder` selects the production version (ADR-0033 rule 13), unless the client names one, under a share lock on `production_structure` (ADR-0027 rule 10, class 3), so a revision cannot be withdrawn meanwhile. It copies the components, outputs and operations of the revisions valid on `planned_start_date`. Components are exploded through phantoms, with quantities by ADR-0033 rule 6. Conversion from a planned order uses the shared planning function ([ADR-0036](0036-multi-level-mrp.md) rule 3).
   - **Backward scheduling.** Select the version and the routing revision valid on `planned_end_date`, schedule backward to obtain `planned_start_date`, then explode at that date. If the routing revision valid there differs, schedule once more with it. The response shows both dates.
   - **Re-explosion.** While the order is in `draft`, changing `planned_start_date`, `good_quantity` or the version explodes again, unless lines were edited by hand (`is_content_edited`). In that case quantities scale by the new Q, fixed-quantity lines do not scale, and the snapshot revisions stay. The response says which happened.
   - **Editing.** Lines may be added, removed or changed per order. The edits are version content, so an approval binds them.
   - **Rejected at `Create` and at each update.**
     - An item that is both a component and an output, except in a `rework` order (ADR-0033 rule 7 gets a note).
     - A backflush setting on a serial-tracked component (`serial_component_backflush`).
     - A backflush setting on any lot or serial-tracked component when the version has `is_as_built_required` (rule 16).
   - **Backflush without an operation.** A `backflush_at_operation` component without an operation number, or on an order without operations, is treated as `backflush_at_receipt`.
   - **Backflush warehouse.** A backflush component must be issued from the production warehouse (`backflush_outside_production_warehouse`). Exception: components of an external operation are consumed at the processor location by the service receipt ([ADR-0037](0037-subcontracting.md) rule 5).

   For a configured item, the explosion selects and sizes the product-level structures with the item's item-defining values ([ADR-0046](0046-product-configuration.md) rule 13).

   Note: backward scheduling selects the version on `planned_end_date` and requires it to be valid on the resulting start, else the next version in order, else `production_version_missing` ([ADR-0033](0033-production-master-data.md) rule 5's note) (holistic review 2026-11-15, item P3).
3. Scheduling:
   - **The rule.** Operation dates come from `setup_duration`, `run_duration` × expected quantity / base quantity, `queue_time` and `move_time`, on the work centers' calendars (ADR-0033 rules 10, 11), at infinite capacity. An order without operations uses the version's fixed lead time. External operations use the supplier lead time and route transit of [ADR-0037](0037-subcontracting.md) rule 3.
   - **Load view.** `ListWorkCenterLoad` (work center, day or week buckets) adds up the remaining scheduled hours of draft and approved orders that are not technically complete, against available hours. Real orders only; planned orders are added by planning's `ListCapacityLoad` ([ADR-0036](0036-multi-level-mrp.md) rule 11).
   - **Later.** Finite sequencing and levelling are DS-54's capacity check, proposed by the planning agent, never applied without approval.
4. Rework and disassembly:
   - **`rework`.** No explosion. The client enters the components, usually the item itself, which may be issued from `quality_inspection` (rule 11), and the operations. The main output is the same item or another named item. The cycle this creates is a production order fact, which the costing solver handles (ADR-0025 rule 6), never a bill of materials.
   - **`disassembly`.**
     - **Input.** The item, issued as the single component, quantity G, with movement type `disassembly_issue`.
     - **Outputs.** The components of the version's bill of materials revision, one level with phantoms exploded, scaled to G, received with `disassembly_receipt`. The bill of materials outputs are left out, and so is the routing unless the client adds operations.
     - **Limits.** Cumulative net issues of the input may not exceed G × (1 + tolerance). The outputs are `co_product` lines; how cost splits over them is DS-53's. Technical completion is manual, and INV-104 does not apply.

**Lifecycle and execution state**

5. Document states follow ADR-0009 rule 6: Release is `submit` of type `production_order` for policy ([ADR-0043](0043-policy-and-approval.md) rule 17).
   - **Release.** `SubmitProductionOrder` is a policy point (ADR-0029 rule 6). An `approved` order is "released": execution may start, it gets its number and its cost object, and its components are reserved (rule 9). An agent releases only by `Submit` under policy; a tainted run cannot (ADR-0029 rule 11).
   - **`Cancel`.** Allowed only while no posting document of the order exists, reversed or not. Canceling:
     - cancels open warehouse tasks and reservations;
     - closes the order's demand and supply lines as `canceled`;
     - leaves staged stock in the supply bin, with move tasks back proposed by the putaway rules.

   In Phase 1 no agent tool list holds `Submit`, so people release production orders ([ADR-0050](0050-agent-runtime-and-query-layer.md) rule 30).

   Note: `policy_input` ([ADR-0043](0043-policy-and-approval.md) rule 4) (holistic review 2026-11-15, item P13).
   - **`production_order`:** `amount` is the unit cost of the released estimate valid for the order's version on `planned_start_date` ([ADR-0035](0035-production-costing.md) rule 14's note) times G or, without one, the components' required quantities at their preliminary prices. Booleans: `has_component_shortage` (available to promise below a component's open requirement at `Submit`), `is_content_edited`, and `is_rework` (`order_type` `rework`).
   - **`production_issue`:** `amount` is the lines' quantities at preliminary prices. Boolean: `is_above_requirement` (a line above its component line's open requirement, rule 11).
6. Execution state, `production_order.execution_state`:
   - **`not_started`:** approved, nothing posted.
   - **`in_progress`:** from the first posting. It stays so when every posting has been reversed.
   - **`technically_complete`:** logistics are finished.
     - **How.** By `CompleteProductionOrder`, or automatically when the version sets `is_complete_on_full_receipt` and the main output's cumulative net receipts reach G.
     - **What it closes.** Open tasks and reservations are canceled, and the order's open demand and supply lines close as `canceled` for the unfulfilled rest. Staged stock is handled as at `Cancel`. Assigned serials not received are freed. Planning ignores the order.
     - **Rejected while a change is pending** (`change_pending`).

   `ReopenProductionOrder` returns a technically complete order to `in_progress` while it is not closed. It reopens its demand and supply lines (ADR-0024 rule 8 gets a note: reopening clears `closed_reason` and restores open quantity) and reserves again.

   **What each state allows:**

   | State | Issues, returns, confirmations, receipts | Reversals | Close-job cost postings (DS-53) |
   | --- | --- | --- | --- |
   | `draft`, `pending_approval` | No | — | No |
   | `approved`, `not_started` or `in_progress` | Yes | Yes | Yes |
   | `approved`, `technically_complete` | No (`production_order_complete`) | Yes | Yes |
   | `closed` | No | No | Yes, when a period is reopened and solved again |

7. Closing:
   - **Settlement task.** The period-end actual costing job ([ADR-0035](0035-production-costing.md) rule 5).
   - **When.** A daily system job with an explicit business date (ADR-0007 rule 17), also started by the period-lock event, closes, as actor `system`, every technically complete order whose last posting lies in a period whose settlement task (DS-53) is done and whose area for production cost is locked. That area is `inventory` ([ADR-0035](0035-production-costing.md) rule 3). A technically complete order without postings closes at the next run. Orders with a pending change are skipped. It runs the generated `CloseProductionOrder`, effect class `other`.
   - **Effect.** A closed order allows no logistics postings and no reversals. Close jobs may still post to its cost object.
   - **Close task.** No close task requires orders to be closed before a lock. Whether completed orders must be closed before a period lock is a question for the author (open question).

**Changes after release**

8. Changes to a released order follow ADR-0028 rules 3–5:
   - **How.** A pending version is drafted and approved (policy usually allows without approval) while the version in force keeps executing.
   - **What is fixed.** The production version and the snapshot revisions do not change after release.
   - **A change of G** rescales the components, outputs and operation quantities by the new Q. Fixed quantities do not scale, and no line goes below what is already posted (`quantity_below_fulfilled`).
   - **Posted lines.** Lines with postings keep item, unit and warehouse (`referenced_line_immutable`).
   - **Operations.** Operations with confirmations cannot be removed or change work center.
   - **When it takes force.** Reservations and demand and supply lines are adjusted.

**Components: reservation, staging, issue and return**

9. Reservation:
   - **Demand and supply lines.** Component lines are demand lines and output lines supply lines (`demand_supply_line`) from `Create`. This is interim and flagged, as ADR-0024 rule 8's list is. Their typed columns `production_order_component_id` and `production_order_output_id` are added to `demand_supply_line` before step 3. ADR-0028 rule 2 left these columns to the author under B3, so they are flagged too (open question). The output supply rows also carry `for_demand_supply_line_id`, flagged with these columns ([ADR-0036](0036-multi-level-mrp.md) rule 9). Components of external operations are demand lines at the processor location ([ADR-0037](0037-subcontracting.md) rule 2).
   - **Open quantity.** It never goes below 0, even after over-issue.
   - **At release.** Components are reserved through `inventory.contract.create_stock_reservation` (ADR-0023 rule 13) up to available to promise. `production` passes the reservation's `destination_bin_id` (the supply bin) and `release_sequence` (operation order), so inventory never reads production tables.
   - **Shortages.** The rest is a shortage, with the check result `component_shortage`. `ReserveProductionOrderComponent` (effect class `other`) reserves again later; humans and the production agent run it directly.
   - **Destination.** `destination_bin_id` is passed only for components issued from the production warehouse.
   - **Interim, flagged:** release with shortages is allowed. Reserving at release can hold stock for an order that starts months later (open question).
10. Staging:
    - **New bin type.** ADR-0023 rule 2 gains bin type `production`, which pick removal never reads. A work center's `supply_bin_id` and `output_bin_id` must be of that type (ADR-0033 rule 11 gets a note). A work center without a supply bin stages to the production warehouse's default bin.
    - **Pick tasks.** `RunPickRelease` (ADR-0023 rule 14) also serves production orders. Its pick tasks move reserved components to the reservation's `destination_bin_id`, released by `release_sequence`.
    - **Plain warehouses.** They have no tasks, and issues take stock from the default bin.
    - **Value.** Staging moves quantity only (ADR-0023 rule 8).
11. `production_issue` is an internal posting document (ADR-0009 rule 19, reversible):
    - **Lines.**
      - order component line, item, quantity, lot or serial;
      - bin, handling unit and `stock_status` (`available`, or `quality_inspection` for rework);
      - `is_return`;
      - optional `output_serial_number_id` (rule 16) and `reason_code` (company data, for over-issue).
    - **Movement types.** `production_issue` from any bin of the issue warehouse, or `production_return` back to the bin the putaway rules give.
    - **Cost object.** Every line carries the order's `cost_object_id` (ADR-0025 rule 1).
    - **Value.** The movement-type rows and the values are DS-53's. ADR-0023 rule 7 gets a pointer to these rules.
    - **Returns.** A return may not exceed the net issued quantity of its component line and lot or serial (`return_above_issued`). It restores the line's open quantity, not its reservation.
    - **Over-issue.** Issuing above the line's open requirement is allowed with the check result `issue_above_requirement`. How consumption above norms is treated is DS-53's (interim, flagged).
    - **Components not on the order.** They are first added through the order or a change order.
    - **Other reservations.** An issue that would cut into other demands' reservations is rejected with `stock_reserved` (ADR-0023 rule 13).

**Operations: confirmation and backflush**

12. `operation_confirmation` is an internal posting document (reversible):
    - **Fields.**
      - order and `operation_number` (an `internal` operation of the order, otherwise `operation_not_confirmable`);
      - `yield_quantity` and `scrap_quantity`, with an optional scrap `reason_code`, and `is_final`;
      - actual activity quantities, defaulting to the standards: `per_base_quantity` activities scaled by yield + scrap, and `per_order` activities only on the first confirmation of the operation;
      - `posting_date` and optional people or teams.
    - **Previous operation.** Cumulative yield + scrap above the previous internal operation's cumulative yield gives the check result `yield_above_previous_operation`.
    - **Milestones.** Confirming a milestone raises each earlier internal, non-milestone operation, back to the previous milestone, to the milestone's cumulative yield + scrap. Their activities and backflush are included in the same document, and external operations are skipped.
    - **Backflush.** For each `backflush_at_operation` component of a confirmed operation:
      - quantity = max(0, round_up(requirement × cumulative (yield + scrap) / Q) − the quantity already backflushed for that line);
      - fixed-quantity components are backflushed whole at the first confirmation;
      - stock comes from the supply bin, with lots in the order of ADR-0023 rule 14 applied inside that bin;
      - missing stock rejects the confirmation with `negative_stock`, naming the component.
    - **Generated lines.** Backflushed lines are generated at `Post` into `operation_confirmation_component` (order component line, material document line). They appear in `plan.stock_movements`, not in approved version content.
    - **Progress interface.** Confirmations write progress through `production.contract.record_operation_progress`. DS-55's service receipts for external operations use the same interface. Their backflush lines go to the production-owned `operation_progress_component`, keyed by the calling document ([ADR-0037](0037-subcontracting.md) rule 5).
    - **Agents.** The capture agent drafts confirmations from messages, photos or voice. Its runs are tainted, so a human posts them (ADR-0029 rule 11).
    - **Activities.** Recorded for costing; DS-53 values them.

    Note: one table holds every generated backflush line: the production-owned `operation_progress_component` (calling document type and ID, order component line, material document line). Confirmations, service receipts and backflush at receipt (rule 13) all write it. `operation_confirmation_component` and `production_receipt_component` are dropped; plans and traceability read the one table, and INV-112 covers every calling document (holistic review 2026-11-15, item P11).

**Output: receipt, inspection and make to order**

13. `production_receipt` is an internal posting document (reversible):
    - **Lines.** Output line, quantity, lot (created at receipt when lot-tracked) or serials, bin and handling unit.
    - **Posting.** It posts a material document with movement type `production_receipt`, `co_product_receipt`, `by_product_receipt` or `disassembly_receipt`, and the cost object.
    - **Bins and putaway.** Output posts to the `output_bin_id` of the last internal operation's work center. Without one, or without a routing, it posts to the bin the putaway rules give (ADR-0023 rules 7, 11). A putaway task from a production bin is created by the putaway rules.
    - **Status.** `quality_inspection` when the product requires inspection, otherwise `available`.
    - **Value.** The receipt's value is DS-53's (a provisional value settled by the period solve).
    - **Tolerance.** Cumulative net receipts of the main output above G × (1 + `overdelivery_tolerance_percent` / 100) are rejected (`receipt_above_tolerance`). By-products and co-products are not capped. The tolerance is business behavior, flagged, default 0.
    - **Backflush at receipt.** `backflush_at_receipt` components are backflushed as in rule 12, with G as the denominator and cumulative net main-output receipts as the progress, generated into `production_receipt_component`.
    - **Automatic receipt.** When the version sets `is_receipt_on_final_confirmation`, the final progress record of the order's last operation (a confirmation when it is internal, a service receipt when it is external, [ADR-0037](0037-subcontracting.md) rule 5) also creates and posts the receipt of that operation's cumulative yield minus the net receipts so far, for untracked or lot-tracked output:
      - the confirmation names the lot;
      - the confirmation's policy decision covers both documents;
      - reversing the confirmation reverses its receipt first, in the same command;
      - a tolerance failure rejects the confirmation.

      Serial-tracked output is never received automatically.

    Note: backflush at receipt writes its lines to `operation_progress_component`, keyed by the receipt, not to `production_receipt_component` (rule 12's note) (holistic review 2026-11-15, item P11).
14. Make to order:
    - **The rule.** When `for_demand_supply_line_id` is set and that demand is in the same warehouse, `available` output is reserved for it, up to that demand's unreserved open quantity. Output in inspection is reserved when it is released: a `production` consumer of `WarehouseTaskConfirmed` runs the reservation (effect class `other`). Planning nets the line against this order through the supply link ([ADR-0036](0036-multi-level-mrp.md) rule 9).
    - **Status.** Interim, flagged: this automatic reservation is business behavior (open question).

**Cost object and traceability**

15. Cost object:
    - **Ownership.** With production in Phase 1, `cost_object` is owned by `production` (ADR-0025 rule 2 gets a note). DS-53 adds its `kind` column and kinds, `production_order` being one.
    - **At release.** The order gets a cost object of kind `production_order`. Its lines (issues, returns, receipts, activities, settlement) carry it.
    - **Subledger activation.** Whether the `cost_object` subledger must be activated (ADR-0025 rule 4) before the first release is an accounting gate. Interim, flagged for DS-53 and the author: required, otherwise `subledger_not_active`.
16. Serials and traceability:
    - **Assigned serials.** For serial-tracked output, the client supplies serial codes at release, up to G, or later by `AssignProductionOrderOutputSerial`. A serial assigned to a `standard` order must have no stock and no other open assignment; a `rework` order assigns the input serial. An issue line's `output_serial_number_id`, and a receipt's serials, must be assigned serials of the same order. Serials not received are freed at technical completion or `Cancel`.
    - **Order level.** Every output lot or serial links to every component lot or serial issued, backflushed or returned on the order.
    - **Unit level (as built).** An issue line that names an output serial links its component to that serial only. When the version sets `is_as_built_required`, every serial or lot-tracked component issue must name one (`as_built_serial_missing`).
    - **Query.** `GetTraceability` (item and lot or serial, `backward` or `forward`) walks these links across orders, receipts and deliveries, excluding reversed lines.
    - **Storage.** Links are derived from issue, generated and receipt lines, never stored separately.

**Commands, events, permissions and agents**

17. Effect classes (ADR-0027 rule 17) and agents:
    - **`other`:** create, update, submit, approve, reject and cancel the order; `ReserveProductionOrderComponent`; `AssignProductionOrderOutputSerial`.
    - **`posting`:** `Post` of the three shop-floor documents.
    - **Proposal-bound** (ADR-0029 rule 2): `CompleteProductionOrder` and `ReopenProductionOrder` are `other` and `is_proposal_bound`, with the order's version as `expected_version`. Agents reach them only through change proposals. ADR-0029 rule 5 gets a note.
    - **The close job** runs as `system`.
    - **Rescheduling by an agent** is a drafted update or change order.

    The production and capture agents are later agents ([ADR-0051](0051-agent-workflows.md) rule 29).

    Note: registry flags. `production_order` and `production_issue` have `is_approval_hold_allowed: true`. `operation_confirmation` and `production_receipt` record facts on the floor and have `is_approval_hold_allowed: false`, so they never wait in a pool and a rank becomes `human_post` ([ADR-0043](0043-policy-and-approval.md) rule 10). Pools: `production_order` in `mo`, `production_issue` in `consumption` ([ADR-0055](0055-approval-pools-and-stages.md) rule 2's note) (holistic review 2026-11-15, item P12).
18. Events, permissions and queries:
    - **Events.** Beyond ADR-0009 rule 22's document events: `ProductionOrderCompleted` and `ProductionOrderReopened`. Reservations emit ADR-0023's events.
    - **Permissions.** Record scope for production documents uses `production_warehouse_id` as the warehouse dimension (ADR-0017 rule 9 gets a note). DS-15 adds a shop-floor role template. It is `shop_floor_lead` ([ADR-0054](0054-users-roles-and-authorizations.md) rule 11).
    - **Planning interfaces.** `production.contract` also exposes `plan_production`, `create_production_order_from_plan` and `get_order_inspection_quantities` ([ADR-0036](0036-multi-level-mrp.md) rules 3, 8, 9).
    - **Queries.**
      - `GetProductionOrderStatus`: progress per operation and output; components required, reserved, staged, issued and backflushed; shortages; postings; cost object.
      - `ListProductionOrder`.
      - `ListWorkCenterLoad`.
      - `GetTraceability`.

**Locks, checks and later features**

19. Locks (ADR-0027 rule 10):
    - **Class 1:** the shop-floor document, the production order and a make-to-order sales order, as referenced documents.
    - **Class 3:** a share lock on `production_structure` at `Create` and re-explosion.
    - **Then:** period state, warehouse tasks, handling units, `stock_value`, `stock_quantity` and bins, then numbering.
    - **Concurrency.** Two confirmations of one order serialize on the order row.
20. Catalog rows reserved in the production range (ADR-0033 rule 16), added when the production core step is numbered:
    - **INV-103:** every material line of a production document carries its order's `cost_object_id`.
    - **INV-104:** per order, cumulative net receipts of the main output never exceed G × (1 + tolerance).
    - **INV-105:** every `output_serial_number_id` on an issue line is a serial assigned to an output of the same order.
    - **Edge cases:**
      - a backflush with too little stock in the supply bin;
      - a milestone over partly confirmed operations;
      - an over-receipt;
      - a change order with partial issues;
      - a posting attempted on a closed order;
      - a rework order from inspection;
      - a disassembly order;
      - as-built serials;
      - a technical completion with open reservations and staged stock;
      - a reopen.
    - **Parallel test:** PAR-13, two confirmations of one order at once.
21. Later than Phase 1, unless the author decides otherwise (open question):
    - finite scheduling inside orders;
    - repetitive manufacturing with period cost collectors;
    - order splitting;
    - co-product planning items;
    - labor time by clock events.

## Context

ADR-0032 targets assembly-type manufacturing in Phase 1, with a general core that learns from SAP. This ADR keeps SAP's production order concepts on ERPMe's machinery:
- statuses, issue and backflush, confirmations with milestones, goods receipt, technical completion;
- document lifecycle and approval as release;
- change orders for changes in flight;
- reservations, pick tasks and bins for staging;
- demand and supply lines for planning;
- internal reversible documents for corrections.

Assigned output serials make as-built traceability possible before the unit is received, which assembly manufacturers need. Closing by a job after settlement avoids a deadlock between a close task and the period lock.

## Options considered

| Option | For | Against |
| --- | --- | --- |
| Order as a non-posting document with internal posting documents (chosen) | Reuses lifecycle, approval, reversal, audit, numbering | More documents |
| Postings as commands on the order | Fewer objects | No reversal, approval or trail per posting |
| A production-specific state machine | Mirrors SAP statuses | Duplicates ADR-0009; an execution state is enough |
| Close by a required close task | Visible in the checklist | Deadlocks with the lock it waits for |
| Close by a job after settlement (chosen) | No deadlock; deterministic | Completed orders may stay open across periods |
| Serials assigned at release (chosen) | As built before receipt | Serials reserved early |

## Constraints that come with the decision

- **ADR notes:**
  - ADR-0009 rule 19: three reversible internal types;
  - ADR-0017 rule 9: production warehouse as scope dimension;
  - ADR-0020 rule 4: production movement types;
  - ADR-0023 rules 2, 7, 13 and 14: bin type `production`, movement-type rows, destination bin and release sequence, pick release for orders;
  - ADR-0024 rule 8: production orders count from `Create`; reopening lines; typed columns;
  - ADR-0025 rule 2: `cost_object` owned by `production`;
  - ADR-0027 rules 7 and 10: types owned by `production`; locks;
  - ADR-0028 rules 2 and 4: production line columns; production orders allow change orders;
  - ADR-0029 rule 5: Complete and Reopen;
  - ADR-0031 rule 6: INV-58 counts production issues;
  - ADR-0033 rules 7, 11 and 13: rework exception; production bins; `overdelivery_tolerance_percent`, `is_receipt_on_final_confirmation`, `is_complete_on_full_receipt`, `is_as_built_required`.
- **DS-04:**
  - errors `production_order_complete`, `receipt_above_tolerance`, `serial_component_backflush`, `as_built_serial_missing`, `subledger_not_active`, `operation_not_confirmable`, `return_above_issued`, `backflush_outside_production_warehouse`;
  - check results `component_shortage`, `issue_above_requirement`, `yield_above_previous_operation`.
- **Movement types:** `production_issue`, `production_return`, `production_receipt`, `co_product_receipt`, `by_product_receipt`, `disassembly_issue`, `disassembly_receipt`. DS-53 adds the catalog rows.
- **Glossary:** order fields and line tables, released, execution state, technical completion, the three documents, backflush, as built, assigned serials; widened verbs Complete, Reopen and Assign; the verb Reserve.
- **Other design items:**
  - DS-53: values, cost object kinds, WIP, settlement, consumption above norms, the settlement task and area.
  - DS-54: planned orders and conversion, capacity check.
  - DS-55: external operations through `record_operation_progress`.
  - DS-34: production and capture agents.
  - DS-31: shop-floor flows.
  - DS-15: shop-floor role.
- **Open questions:**
  - release with shortages, and reservation timing;
  - over-issue;
  - receipt tolerance;
  - make-to-order reservation;
  - closing before a lock;
  - subledger activation before release;
  - the `demand_supply_line` columns;
  - later features.

## Revisit when

- A target customer needs finite scheduling inside orders or repetitive manufacturing in Phase 1.
- The period solve (DS-53) needs a posting this ADR does not record.

## Documents updated

- **ADRs:** [docs/adr/0009-document-lifecycle.md](0009-document-lifecycle.md), [docs/adr/0017-permission-envelope.md](0017-permission-envelope.md), [docs/adr/0020-inventory-and-costing-model.md](0020-inventory-and-costing-model.md), [docs/adr/0023-warehouse-management.md](0023-warehouse-management.md), [docs/adr/0024-planning.md](0024-planning.md), [docs/adr/0025-later-phase-seams.md](0025-later-phase-seams.md), [docs/adr/0027-cross-cutting-ownership.md](0027-cross-cutting-ownership.md), [docs/adr/0028-document-lifecycle-hardening.md](0028-document-lifecycle-hardening.md), [docs/adr/0029-proposals-and-agent-safety.md](0029-proposals-and-agent-safety.md), [docs/adr/0033-production-master-data.md](0033-production-master-data.md): notes.
- **Design:** [docs/design/DS-04-command-envelope.md](../design/DS-04-command-envelope.md), [docs/design/backlog.md](../design/backlog.md).
- **Glossary:** [docs/spec/00-reading-guide.md](../spec/00-reading-guide.md).
- **Open questions:** [docs/open-questions.md](../open-questions.md).
- **Index and log:** [docs/adr/README.md](README.md); [docs/runbook/step-log.md](../runbook/step-log.md) at acceptance.
