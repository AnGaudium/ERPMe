# ADR-0033: Production master data

Status: accepted (2026-11-14) under ADR-0005, reviewed by Claude Fable 5.2 (builder Claude Opus 5.5). Design item: DS-51 (new). Related decisions: D6. Principles 2, 6, 10, 13. ADR-0004, ADR-0005, ADR-0006, ADR-0007, ADR-0008, ADR-0013, ADR-0016, ADR-0018, ADR-0020, ADR-0022, ADR-0023, ADR-0024, ADR-0025, ADR-0027, ADR-0029, ADR-0030, ADR-0032. Research: [reference systems](../research/2026-11-14-production/01-reference-systems.md), [Vietnamese rules](../research/2026-11-14-production/02-vietnam-rules.md).

## Decision

Production master data answers one question per made item: how it is made, from what, where, and in how long. It lives in a new module, `production` (layer 3, ADR-0022 rule 2), and leaves the product and item model of ADR-0018 unchanged.

The Phase 1 target is assembly-type manufacturing (the author, 2026-11-14; ADR-0032). The structures also carry batch work with co-products and by-products, so process manufacturing later needs no structural change.

| Object | Role |
| --- | --- |
| Bill of materials | What an item is made from: components, and the co-products and by-products it also yields. Revised by immutable released revisions, each valid from a date |
| Routing | The operations that make it, at work centers, with standard times and activity quantities. Revised like bills of materials |
| Work center | Where an operation runs: its activities, capacity, calendar, cost center and bins |
| Production version | The one explicit way to make an item in a production warehouse: a bill of materials, a routing, a lot-size range and a date range. Every made item needs one |
| Production setting | Per item and production warehouse: whether the item is a phantom |

The concepts follow SAP's production planning (bills of materials, routings, work centers, production versions), simplified as ADR-0032 rule 2 requires:
- one bill of materials model with a usage;
- a linear operation sequence;
- revisions instead of change-number management;
- the production warehouse in place of a plant.

Agents read the structures through deterministic queries. They draft revisions freely, and a release or any other effective change reaches the books only through a change proposal (ADR-0029).

### Rules

**Module, ownership and effect classes**

1. `production` (layer 3) owns every table of this ADR.
   - **Readers.** Planning (layer 4) and documents read production master data through `production.contract`.
   - **References.** Bills of materials refer to items (ADR-0018 rule 2), never to products.
   - **Components and outputs.** They are items of `stock` products. Consumables of `non_stock` products are not components; they reach production cost as overhead (DS-53). Services enter through external operations (rule 9; DS-55).
2. Effect classes (ADR-0027 rule 17):
   - **Draft commands** create and edit draft revisions: `CreateBillOfMaterials`, `CreateBillOfMaterialsRevision`, `UpdateBillOfMaterialsRevision`, and the same for routings. They are `other`, because a draft has no effect until it is released, so agents run them directly.
   - **Effective commands** are `master_data_change`, so agents reach them only through change proposals (ADR-0029 rule 2):
     - `ReleaseBillOfMaterialsRevision`, `ReleaseRoutingRevision`;
     - production version, work center, activity type and production setting commands;
     - deactivation of a bill of materials or routing.
   - **Release proposals.** The proposal's target record for a release is the draft revision. Its `expected_version` is the draft's `content_hash` (rule 3), so the approved content is exactly what is released.

**Bills of materials**

3. A `bill_of_materials` has these fields:
   - `item_id`, the main output;
   - `usage`: `production`; `kit` is reserved for sales kits, whose rules DS-22 designs;
   - `alternative`, a short code unique per item and usage;
   - `name` and `is_active`.

   Its content lives in `bill_of_materials_revision` rows:
   - **Fields.** `revision` (an integer, numbered at creation; at most one draft per bill of materials at a time, otherwise `draft_revision_exists`), `state` (`draft`, `released`), `start_date`, `base_quantity`, `assembly_scrap_percent`, `main_output_cost_coefficient`, `content_hash` and `released_at`.
   - **Base quantity.** In the main output's inventory unit, so that small per-unit quantities stay exact, e.g. glue per 1,000 pieces.
   - **Content hash.** The SHA-256 of the canonical JSON (ADR-0008 rule 12 forms) of the header fields and its components and outputs, ordered by position.
   - **Immutability.** A database trigger rejects updates of released rows (`revision_released`). A change is a new revision, created as a copy (`copy_from_revision_id`), edited in draft and released.

   A configurable product has a product-level bill of materials (`product_id` instead of `item_id`) whose main output at explosion is the configured item ([ADR-0046](0046-product-configuration.md) rule 12).
4. Validity:
   - **Which revision is valid.** The valid released revision on a date is the one with the highest `revision` whose `start_date` is on or before that date. The end of validity is derived, never stored.
   - **Releases are not retroactive.** A release's `start_date` must be on or after the company's current date (ADR-0007), except for the first released revision of a bill of materials. Otherwise the release is rejected with `revision_retroactive`.
   - **Releases are in order.** A release's `start_date` must be on or after the latest released revision's, otherwise `revision_start_date_order`. It may be equal only under the withdrawal rule.
   - **Withdrawing a mistaken release.** A revision released by mistake is superseded by a new revision with the same `start_date`, as long as no production order or cost estimate refers to it, otherwise `revision_in_use`.
5. The explosion date:
   - **Definition.** Every explosion, version selection and revision selection uses one `explosion_date`: the planned start date of the order or planned order, in the company's time zone (ADR-0007).
   - **Users.** MRP (DS-54), order creation (DS-52), cost estimates (DS-53; their costing date acts as the `explosion_date`) and the explosion query (rule 15) all use it.
   - **Snapshot.** A production order copies the revisions valid on its `explosion_date` and keeps their IDs. DS-52 states whether a change of the planned start date before release explodes the order again.
6. `bill_of_materials_component` rows of a revision:
   - **Fields.**
     - `position`;
     - `component_item_id`;
     - `quantity` per base quantity, with its unit and the quantity in the component's inventory unit (ADR-0018 rule 11, exact by `numerator` and `denominator`);
     - `component_scrap_percent`;
     - `is_fixed_quantity` (the same quantity whatever the order size, e.g. setup material);
     - `operation_number` (optional; the routing operation that consumes it);
     - `consumption_method`.
   - **Consumption method.** One of:
     - `manual`: issued by a goods issue;
     - `backflush_at_operation`: issued when its operation is confirmed;
     - `backflush_at_receipt`: issued when output is received.

     DS-52 defines each.
   - **Requirement.**
     - For a planned output quantity Q, a component's requirement = `quantity` × Q / `base_quantity` × (1 + `component_scrap_percent` / 100). A fixed-quantity component takes `quantity` × (1 + `component_scrap_percent` / 100), not scaled by Q.
     - The planned output quantity of an order for a good quantity G is G / (1 − `assembly_scrap_percent` / 100). Co-products and by-products scale as `quantity` × Q / `base_quantity`.
     - Through phantoms, intermediate quantities stay exact rationals and are never rounded.
     - Requirements are computed as exact rationals and rounded once per order line, up (away from zero), to the component's inventory unit. `round_quantity` gains an optional mode argument taking ADR-0006 rule 17's modes. Rounding half away from zero (ADR-0018 rule 11) would under-issue.

   Components of a product-level bill of materials carry a `selection_condition` and `fixed` or `linear` sizing over item-defining characteristics, applied before the requirement formula ([ADR-0046](0046-product-configuration.md) rules 12–13).
7. `bill_of_materials_output` rows of a revision list outputs besides the main one:
   - **Fields.** `output_item_id`, `quantity` per base quantity with its unit, `output_type` (`co_product` or `by_product`) and `cost_coefficient` (co-products).
   - **Coefficients are data only.** `cost_coefficient` and `main_output_cost_coefficient` hold equivalence coefficients. Whether the coefficient method applies, and how by-products are valued, are the author's through DS-53. VAS 02 para 09 values by-products at net realisable value (unverified, ADR-0016).
   - **What is rejected.** An item may not be both a component and an output of one revision (`item_both_component_and_output`; rework orders are the exception, [ADR-0034](0034-production-orders-and-shop-floor.md) rule 2); recycling loops are not modeled in Phase 1. A phantom's bill of materials may not have outputs (`phantom_with_outputs`). This is checked when `is_phantom` is set (rule 14), and at release and production version save for an item that is a phantom in the version's warehouse.
8. Releasing a revision checks, deterministically:
   - **Items.** Components and outputs are active items of `stock` products, distinct from the main output.
   - **Units and quantities.** Units are convertible; quantities and the base quantity are positive; scrap percentages are in [0, 100).
   - **Cycles.**
     - The graph has an edge from each main output to its components and to its co-products and by-products.
     - The graph holds every released revision of every `production` bill of materials, superseded and future ones included, plus the revision being released. This is conservative and checkable from stored rows.
     - A cycle is rejected with `bill_of_materials_cycle`, naming the path.
     - Rework that feeds an item back into its own production is a production order matter (DS-52), never a bill of materials.
   - **Low-level codes.** `item_low_level_code` (company, item, `low_level_code`) is a read model owned by `production`. It is recomputed downward for every item the release reaches: the longest path from an item that is never a component or an output, so 0 for top items. A code may fall when a component is removed. MRP plans in that order (DS-54).
   - **Operations.** For every production version that pairs this bill of materials with a routing on dates from the revision's `start_date`, each `operation_number` must exist in the routing revision valid on that date. Otherwise the release is rejected with `operation_not_in_routing`.
   - **Locking.** Releases, production version saves, production setting saves and deactivations of bills of materials and routings lock the company's `production_structure` row (created with the company) at class 3 of ADR-0027 rule 10, beside the planning state row. Two concurrent changes therefore cannot create a cycle or break an operation reference together.

**Routings**

9. A `routing` (`code`, `name`, `is_active`) may serve several items. Its `routing_revision` rows follow rules 3 and 4: `revision`, `state`, `start_date`, `base_quantity` of output, `content_hash`, immutability, validity, withdrawal and snapshot by orders.
   - **Release checks.** A routing release runs the operation check of rule 8 against every bill of materials paired with it by a production version, and checks that its work centers are active and belong to the production warehouse of every version that uses it (`work_center_outside_warehouse`). It takes the same lock.
   - **Deactivation.** Deactivating a bill of materials or routing is rejected while an active production version uses it (`in_use_by_production_version`).

   Operations of a configurable product's routing carry a `selection_condition` and linear sizing of their durations ([ADR-0046](0046-product-configuration.md) rule 12).
10. `routing_operation` rows of a revision form one linear sequence:
    - **Fields.**
      - `operation_number` (ascending, e.g. 10, 20, 30);
      - `work_center_id`;
      - `description`;
      - `control`: `internal` (run at the work center, which is then required) or `external` (done by a subcontractor, DS-55: `service_item_id` and `default_supplier_id`, work center optional; the purchase may choose another supplier, so a revision does not depend on one processor);
      - **Subcontracting** of `external` operations: [ADR-0037](0037-subcontracting.md) rules 2–6.
      - `is_milestone`: confirming it confirms the earlier non-milestone operations;
      - `setup_duration` (hours per order) and `run_duration` (hours per base quantity): the elapsed time used for scheduling, lead times and the load view;
      - `operation_scrap_percent`: not used in requirements; DS-52 uses it for expected yield per operation and DS-53 for the scrap variance;
      - `queue_time` and `move_time` in hours (calendar time before and after the operation).
    - **Activities.** `routing_operation_activity` rows inside the revision, and inside its hash, hold the standard quantity of each activity type for costing: `activity_type_id`, `quantity` and `basis` (`per_order` for setup, `per_base_quantity` for run). Labor and machine time can therefore differ from the duration, e.g. two operators on one machine.
    - **Later.** Parallel and alternative sequences and overlapping operations come after Phase 1. A routing without operations is allowed: the item is then made in one step.
    - **Phantoms.** A phantom's components take the operation number of the phantom's line in the parent.

**Work centers and calendars**

11. A `work_center` has:
    - **Identity:** `code` and `name`, unique per company, and the `production_warehouse_id` it belongs to (a `physical` warehouse).
    - **Calendar and capacity:** `working_calendar_id`, `capacity_units` (parallel machines or people), `hours_per_day` per working day, `efficiency_percent` and `is_capacity_relevant`.
    - **Cost center:** `cost_center_id` (ADR-0027 rule 6), where its overhead is collected (DS-53).
    - **Bins:** nullable `supply_bin_id` and `output_bin_id` in its warehouse, of bin type `production` ([ADR-0034](0034-production-orders-and-shop-floor.md) rule 10), as destinations and sources for the warehouse tasks of DS-52 (ADR-0023).
    - **Lifetime:** `is_active`.

    **Deactivation.** Deactivating a work center that a valid routing revision uses is rejected with `in_use_by_production_version`.

    Available hours per working day = `capacity_units` × `hours_per_day` × `efficiency_percent` / 100. That is enough for an infinite load view and simple forward scheduling (DS-52, DS-54). Shift patterns are later.

    **Calendar ownership.** `working_calendar` moves from planning to `master_data` (layer 3), so that production can read it. ADR-0024 rule 4 gets a note.
12. `activity_type` is company data, for example `setup`, `machine` and `labor`, with a time unit (ADR-0018 rule 8, kind `time`). `work_center_activity` rows list which activity types a work center records, with a default `quantity` and `basis` copied into new routing operations. Planned and actual activity rates are DS-53's.

**Production versions and settings**

13. A `production_version` has:
    - **Identity:** `item_id`, `production_warehouse_id` (a `physical` warehouse, where components are staged and output is received by default), and `code`, unique per item and warehouse.
    - **Recipe:** `bill_of_materials_id` (usage `production`) and `routing_id` (optional).
    - **Selection:** `minimum_lot_quantity` and `maximum_lot_quantity`, `start_date` and `end_date` (open-ended allowed), `priority` and `is_active`.
    - **Execution settings** ([ADR-0034](0034-production-orders-and-shop-floor.md)): `overdelivery_tolerance_percent` (default 0), `is_receipt_on_final_confirmation`, `is_complete_on_full_receipt`, `is_as_built_required`.
    - **Lead time:** `production_lead_time_method`, either `fixed` with `production_lead_time_days` (working days on the production warehouse's calendar), or `routing` (computed by DS-54).
    - **Selection order.** On the `explosion_date`, among active versions whose dates cover it and whose lot range covers the quantity: the lowest `priority`, then the lowest `code`. If none fits, the error is `production_version_missing`.
    - **Save checks.**
      - The bill of materials and the routing are active, and each has a released revision valid at every date of the version's range, otherwise `revision_validity_gap`.
      - The routing's work centers belong to the production warehouse (`work_center_outside_warehouse`).
      - The operation check of rule 8.

    A version may name a configurable product (`product_id`, exclusive with `item_id`); it applies to every configured item of the product, after any item-level version ([ADR-0046](0046-product-configuration.md) rule 12).
14. `item_production_setting` (company, item, production warehouse) holds `is_phantom`.
    - **Explosion.** A phantom is never planned or made on its own. It is exploded through its production version in that warehouse, selected with the exploded quantity and the `explosion_date`, routing ignored. A missing version gives `production_version_missing`.
    - **Planning.** Planning reads the setting through `production.contract` and skips phantoms. A phantom needs no `item_warehouse_planning` row.
    - **Stock.** Whether stock of a phantom may exist and be used is business behavior. Interim, flagged: it is allowed, and DS-54 states whether MRP nets it. DS-54's interim: MRP does not net phantom stock ([ADR-0036](0036-multi-level-mrp.md) rule 7).
    - **Making as well as buying.** `production` becomes a value of ADR-0024's `replenishment_source`, for items made in that warehouse. Several sources at once with quotas come after Phase 1.

**Queries for agents and people**

15. Read-only queries (ADR-0008 rule 22; ADR-0004 rule 21):
    - **`GetBillOfMaterialsExplosion`:** item, warehouse, quantity and `explosion_date`. It returns the multi-level structure through the selected production versions and revisions, with:
      - phantoms exploded;
      - scrap applied;
      - fixed quantities;
      - inventory-unit quantities as exact rationals and as rounded values;
      - co-products and by-products;
      - the path to each line.
    - **`ListWhereUsed`:** item and date. It returns the parent bills of materials and production versions, recursively on request.
    - **`GetBillOfMaterialsRevisionCheck`:** runs rule 8's checks on a draft without releasing it. An agent attaches the result to its change proposal as evidence.
    - **`GetProductionVersionSelection`:** item, warehouse, quantity and date. It returns the selected version and why the others were not selected.

    Agents draft bills of materials and routings from spreadsheets or drawings, then propose the release (ADR-0029 rule 5). DS-34 designs the master-data workflow.

    The master-data workflow is a later agent ([ADR-0051](0051-agent-workflows.md) rule 29).

**Reserved checks and later features**

16. Catalog codes:
    - **New production range.** Invariant codes get a production range of three digits, INV-100 to INV-199. DS-16 widens its code format to `INV-nn` or `INV-nnn`, and adds area `production`.
    - **Reserved rows.** These rows are reserved and added to the catalogs, with their first step, when the author numbers the production core step (ADR-0032 rule 7). Until then, DS-16 rule 5 requires no check for them.
      - **INV-100:** no cycle exists through released `production` bills of materials, counting outputs as children, and every component's and output's low-level code is greater than each parent's.
      - **INV-101:** every released bill of materials and routing revision's `content_hash` equals the hash of its stored rows.
      - **INV-102:** at every date of an active production version's range, its active bill of materials and, if set, its active routing each have a valid released revision.
    - **Reserved edge cases**, coded by DS-17 when added:
      - a release that would close a cycle, including one through a co-product;
      - a three-level structure with a phantom;
      - a bill of materials with a co-product and a by-product;
      - a revision released between the creation of two orders with different explosion dates;
      - a made item without a valid production version on its explosion date.
    - **Reserved parallel test.** PAR-12: two releases that together would close a cycle.
17. Later than Phase 1, unless the author decides otherwise (open question):
    - configured products (options chosen on the sales order, with the bill of materials and routing derived from rules): now in Phase 1 by the author's decision of 2026-11-15, as DS-56;
    - substitute components;
    - parallel and alternative operation sequences;
    - shift patterns;
    - several sources with quotas;
    - engineering change approval as a document type;
    - recycling loops.

    The norms that customs reports need are actual consumption norms (research note 02, unverified). Released revisions are planned norms and an input to DS-55.

    Line options (choices on a line that create no item) and items created on order exist in Phase 1 and are the base product configuration builds on (DS-56; [ADR-0045](0045-master-data-and-price-lists.md) rules 15–16).

## Context

ADR-0032 put production in Phase 1 with a general core that learns from SAP, targeting assembly-type manufacturing. The research notes compare SAP, Odoo and Dynamics 365.

Key points of the design:
- **Production version.** S/4HANA made the production version mandatory because implicit selection confused planning. An explicit "way to make" is also what an agent can read and explain.
- **Revisions.** Immutable revisions keep orders, costing and norms reproducible without SAP's change-number machinery. One explosion date ties MRP and orders to the same revision.
- **Outputs.** Co-products count as children of the main output, as SAP's negative items do implicitly, so low-level codes and cycles cover them.
- **Odoo.** Its kit, manufacture and subcontract types map onto usage, production versions and external operations.
- **Customer-supplied components.** These and a "provision" flag on components are DS-55 questions. Both are additive (ADR-0030 rule 8).
- **Disassembly.** It reuses a `production` bill of materials in reverse (DS-52).

## Options considered

| Option | For | Against |
| --- | --- | --- |
| Production version mandatory (chosen) | Explicit, explainable choice; one place for lot range and dates | One more record per made item |
| Implicit selection by bill of materials and routing validity | Fewer records | Ambiguous when alternatives exist |
| Immutable revisions, valid from a date (chosen) | Reproducible orders, costs and norms | A copy for every change |
| Editable bills of materials with history | Simple editing | Orders and norms drift; harder to audit |
| Phantom as a planning source | One field | Layer 3 would read a layer 4 table |
| Phantom as a production setting (chosen) | Owned where it is used | One more small table |
| Drafts as master-data changes | Uniform | Agents could not draft or check before a proposal |

## Constraints that come with the decision

- **ADR notes:**
  - ADR-0006 rule 15 (`round_quantity` mode argument);
  - ADR-0018 deliberately-elsewhere row;
  - ADR-0022 rule 2 (`production` tables; `working_calendar` in `master_data`);
  - ADR-0024 rules 1 and 4 (`production` source; calendar ownership);
  - ADR-0027 rule 10 (`production_structure` at class 3);
  - ADR-0029 rule 5 (bills of materials, routings and production versions use the carrier).
- **DS-04:** errors `bill_of_materials_cycle`, `revision_released`, `revision_validity_gap`, `operation_not_in_routing`, `production_version_missing`, `draft_revision_exists`, `revision_retroactive`, `revision_start_date_order`, `revision_in_use`, `item_both_component_and_output`, `phantom_with_outputs`, `work_center_outside_warehouse`, `in_use_by_production_version`.
- **DS-16:** code format `INV-nnn`, group INV-100 to INV-199 and area `production`; reserved rows.
- **DS-17:** reserved production edge cases.
- **Glossary:**
  - production terms;
  - the verb Release;
  - the query noun where-used.
- **Other design items:**
  - DS-52: snapshot and re-explosion, consumption methods, milestones, rework, disassembly, bins.
  - DS-53: coefficients, by-product value, activity rates, cost centers.
  - DS-54: low-level codes, lead times, version selection, phantom stock.
  - DS-55: external operations, customer-supplied components, norms.
  - DS-34: the master-data workflow.
  - DS-22: kits.
- **Open questions:** configured products and the other later features (rule 17).

## Revisit when

- A target customer needs parallel operations, substitute components or several sources at once in Phase 1.
- The author moves configured products into Phase 1.

## Documents updated

- **ADRs:** [docs/adr/0006-id-and-numeric-model.md](0006-id-and-numeric-model.md), [docs/adr/0018-product-and-item-model.md](0018-product-and-item-model.md), [docs/adr/0022-repository-and-engineering-conventions.md](0022-repository-and-engineering-conventions.md), [docs/adr/0024-planning.md](0024-planning.md), [docs/adr/0027-cross-cutting-ownership.md](0027-cross-cutting-ownership.md), [docs/adr/0029-proposals-and-agent-safety.md](0029-proposals-and-agent-safety.md): notes.
- **Design:** [docs/design/DS-04-command-envelope.md](../design/DS-04-command-envelope.md), [docs/design/DS-16-invariants-and-harness.md](../design/DS-16-invariants-and-harness.md), [docs/design/DS-17-synthetic-dataset.md](../design/DS-17-synthetic-dataset.md), [docs/design/backlog.md](../design/backlog.md).
- **Glossary:** [docs/spec/00-reading-guide.md](../spec/00-reading-guide.md).
- **Open questions:** [docs/open-questions.md](../open-questions.md).
- **Index and log:** [docs/adr/README.md](README.md); [docs/runbook/step-log.md](../runbook/step-log.md) at acceptance.
