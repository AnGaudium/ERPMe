Module: production    Chunk: 1 of 7    Source ADRs: ADR-0025, ADR-0032, ADR-0033
Build step(s): 0, 3, 4, 5, 5b    Generated from index: 30d5706    Compiled by: Claude Opus 5.5, 2026-11-21

# Compiled spec: `production`, chunk 1

## Purpose

`production` (layer 3, ADR-0022.R2) owns production master data, production orders and shop floor, production costing,
subcontracting and the cost collector `cost_object`. This chunk states the Phase 1 scope decision for production
(ADR-0032), the later-phase seams of ADR-0025 that production builds on, and the bill of materials and routing part of
production master data (ADR-0033 rules 1 to 10). Ledger, periods, inventory, planning and documents law that only names
production is traced `ref:` and not restated.

## Entities and tables

DDL: `docs/design/DS-43-54-planning-production.sql`; `cost_object` in `docs/design/DS-06-universal-journal.sql`.

| Table | Meaning | Key | Parent | Owner |
| --- | --- | --- | --- | --- |
| `bill_of_materials` | What an item (or a configurable product, or a proposal item while drafts refer to it) is made from; per usage and alternative (R25) | `id`; unique (`company_id`, `item_id`, `product_id`, `proposed_change_proposal_item_id`, `usage`, `alternative`) | none | `production` |
| `bill_of_materials_revision` | Dated content of a bill of materials, immutable once released (R26-R32) | `id`; unique (`bill_of_materials_id`, `revision`) | `bill_of_materials` | `production` |
| `bill_of_materials_component` | A component line of a revision (R36-R41) | `id`; unique (`bill_of_materials_revision_id`, `position`) | `bill_of_materials_revision` | `production` |
| `bill_of_materials_output` | A co-product or by-product of a revision (R42-R44) | `id`; unique (`bill_of_materials_revision_id`, `position`) | `bill_of_materials_revision` | `production` |
| `routing` | Operations that make items; may serve several items (R51) | `id`; unique (`company_id`, `code`) | none | `production` |
| `routing_revision` | Dated content of a routing, immutable once released (R51) | `id`; unique (`routing_id`, `revision`) | `routing` | `production` |
| `routing_operation` | One operation of the linear sequence of a revision (R55-R59) | `id`; unique (`routing_revision_id`, `operation_number`) | `routing_revision` | `production` |
| `routing_operation_activity` | Standard activity quantity of an operation (R58) | `id`; unique (`routing_operation_id`, `activity_type_id`) | `routing_operation` | `production` |
| `item_low_level_code` | Read model: low-level code per item or configurable product (R47) | `id`; item or product, exactly one | none | `production` |
| `production_structure` | One row per company, locked by structure changes (R50) | `id`; unique `company_id` | `company` | `production` |

Named here, row in chunk 3: `cost_object` (R16, R17).

Reads: `item`, `product`, `uom`, `warehouse`, `work_center`, `activity_type`, `partner`, `variant_attribute`, `cost_center`, `fixed_asset`, `production_version`, `item_production_setting`, `change_proposal`; the setting `journal.manual_posting_to_control_accounts` (ADR-0014.R10).

## Commands and queries

| Name | Actor and authorization | Input | Effect | Events | Error codes |
| --- | --- | --- | --- | --- | --- |
| `CreateBillOfMaterials` | Effect class `other`, `is_draft_only`; agents run it directly; area `production_structure`, verb `Create` (edit) | Item, product or proposal item, `usage`, `alternative`, `name` | Creates a header and its first draft revision | not stated | not stated |
| `CreateBillOfMaterialsRevision` | As above; verb `Create` (edit) | The bill of materials, optional `copy_from_revision_id` | Creates a draft revision | not stated | `draft_revision_exists` |
| `UpdateBillOfMaterialsRevision` | As above; verb `Update` (edit) | A draft revision, header fields, components and outputs | Edits the draft | not stated | `revision_released`, `item_both_component_and_output`, `phantom_with_outputs` |
| `ReleaseBillOfMaterialsRevision` | Effect class `master_data_change`; agents only through a change proposal; area `production_structure`, verb `Release` (post) | The draft revision; the proposal's `expected_version` is its `content_hash` | Releases the revision, recomputes `item_low_level_code` | not stated | `revision_retroactive`, `revision_start_date_order`, `revision_in_use`, `bill_of_materials_cycle`, `operation_not_in_routing`, `bill_of_materials_item_pending`, `item_both_component_and_output`, `phantom_with_outputs` |
| `ReleaseRoutingRevision` | As `ReleaseBillOfMaterialsRevision` | The draft routing revision | Releases the revision | not stated | `operation_not_in_routing`, `work_center_outside_warehouse`, `routing_duration_unstated`, `revision_retroactive`, `revision_start_date_order`, `revision_in_use` |

The draft commands for routings are "the same" three as for bills of materials (R22); the sources register no names for
them, nor for the deactivation of a bill of materials or routing (effect class `master_data_change`, error
`in_use_by_production_version`, R53). `production_version_missing` is raised by version selection (R35), bound to no
command of this chunk.

## Rules

### Phase 1 scope and the production design principle

R1. A capability belongs in Phase 1 when a customer in the target segments cannot run their business without it. The target segments are trading companies and manufacturers. Inside Phase 1, "built thin" (spec 10) still applies to features whose thin form does not block operation, such as the policy rule language or a single LLM provider. It does not apply to production.
Source: ADR-0032.R1

R2. Production (multi-level BOM, production orders, production costing, disassembly) is Phase 1 and designed in full, not in Phase 2. Multi-level MRP is Phase 1, as part of planning, and planning (ADR-0024) is Phase 1. Warehouse management and planning lists (ADR-0023, ADR-0024) are not cut. Subcontracting is Phase 1, with production. Fixed assets, loans and the other candidates stay Phase 3 until the author decides each one (open question).
Source: ADR-0032.D0

R3. The production core is general, not built for one industry. Its concepts come from SAP's production planning and product costing: bills of materials, routings and work centers; production orders and order types for discrete and batch manufacturing; cost estimates, actual costs, work in process, variances and settlement. Each concept is simplified to what a mid-size manufacturer needs. Each workflow is agentic-native: deterministic commands, simulation before execution, agents that propose plans, shortages and variances for humans to approve. Industry features, such as product configuration for made-to-measure products, are added as data and configuration on this core, never as a separate core.
Source: ADR-0032.R2

R4. Production costing follows best practice, and regimes configure it (ADR-0053.R13): a planned cost estimate per product; actual costs collected per cost collector; work in process valued at period end; variances analysed by category; actual cost settled to stock and to cost of goods sold through the existing exact solver (ADR-0025.R6). The cost estimate is a benchmark for variances. Methods, normal capacity, overhead allocation and WIP valuation are accounting choices; DS-53 proposes them as flagged interims (ADR-0005 item 1).
Source: ADR-0032.R3

R5. Stock stays valued at periodic actual cost (ADR-0020.R12), which is the default (D6). Valuation at a standard price is decided as a later price-control option beside periodic actual costing, as in SAP; the released cost estimate gives the standard price, and its granularity is the one the ADR-0018.R3 note states. A later ADR, after step 5 and on the seam of ADR-0072.R21, designs it, chooses between standard price with variance postings and no actual costing or standard price with actual costing, and states its phase: after Phase 1 unless the author moves it (ADR-0018.R3, spec 09). Whether TT99 permits it is the Vietnam package's rule.
Source: ADR-0032.R3, ADR-0032.R3.N1

R6. ADR-0025 is superseded in part: its opening sentence, its rule 2 "kinds and lifecycle are designed in Phase 2", its rule 8 "Phase 2 production adds", and the revisit trigger on an assembly customer. Production no longer waits for Phase 2 or for "design when built". The seams stay and are the base of the production design: `cost_object`, the `cost_object` control kind with activation, the production cost accounts and the typed costing solver. The fixed asset and loan parts are unchanged (Phase 3).
Source: ADR-0032.R4

R7. Production is designed completely before the build step that implements it, by design items reviewed like the others: DS-51 production master data (multi-level bills of materials, alternatives, phantoms, by-products and co-products, routings, work centers, production versions, capacity calendars); DS-52 production orders and shop floor (order types for discrete and batch work, lifecycle, staging and issue or backflush, operation confirmations, receipts, scrap, rework, disassembly, reservations and warehouse tasks for components); DS-53 production costing (cost estimates, cost collectors, WIP at period end, overhead allocation at normal capacity, abnormal costs, variances, solver nodes, activation of the `cost_object` subledger); DS-54 multi-level MRP inside planning (BOM explosion with low-level codes, dependent demand, lead-time offsetting, planned production orders, a capacity check, conversion); DS-55 subcontracting (gia công: materials sent to a processor, the processing fee, receipt of finished goods, customs reporting of processing types where they apply). DS-52's quality inspection on output is widened into a Phase 1 quality core, design item DS-58: inspection plans, inspection lots, results, usage decisions and nonconformances (ADR-0070). The feature lists are the agent's proposal under R3 and R4; the author confirms them (open question).
Source: ADR-0032.R5, ADR-0032.R5.N1

R8. The production agent workflow is added to DS-34; the production agent is design item DS-57, designed before the production core step (ADR-0051.R29); its agent types `production`, `production_capture` and `production_variance` are Phase 2, registered with mode `off` while the production core and its manual capture stay in Phase 1 (ADR-0078.R2). When the production design is done, agents run design assessment 2 of the production flow (demand, MRP, production order, material issue, output, costing, cost of goods sold) as the first assessment was run, with reports in `docs/reviews/<date>-production-assessment/`.
Source: ADR-0032.R5

R9. DS-17 adds a fictional Vietnamese manufacturing company with multi-level bills of materials, production, subcontracting and production cost closing, due at the gate of the production core step. The production design items add their edge cases.
Source: ADR-0032.R6

### Build placement and the author's documents

R10. The production core is the Phase 1 build step 4b: it starts after step 4's gate and may run beside step 5. Its gate includes the synthetic manufacturing company and, for a manufacturing customer, production cost closed for at least one period that matches the independent naive recomputation, not a manual spreadsheet.
Source: ADR-0032.R7, ADR-0032.R7.N1

R11. The build carries no calendar dates and no customer commitment: the build order and the gates are the only schedule, and no dated plan is set. Spec 10 and spec 11 record step 4b without dates.
Source: ADR-0032.R7, ADR-0032.R7.N1

R12. The planning slice with multi-level MRP and subcontracting (ADR-0037, DS-55) are build step 5b, after the gates of steps 4b and 5. The planning agent stays in the list of agents done before platform completion: a Phase 1 agent type that starts after the step 5b gate (ADR-0078.R1). The production agent types are Phase 2 (ADR-0078.R2).
Source: ADR-0032.R7, ADR-0032.R7.N2, ADR-0032.R7.N3, ADR-0032.R7.N4

R13. The roadmap, build order, MVP scope, vision, specs and runbook are the author's documents. Standard cost is decided as R5 states. The phase labels and the production-in-Phase-1 statement of spec 01, spec 05, spec 08, the README and the risks file follow this rule's draft wording; spec 00 rule 2 needed no change. The rest of the draft wording is this rule's proposal for those documents:
   - spec 09: production rows, including MRP, routings, operations, shop floor and quality, move to Phase 1, and "MVP is Phases 1 and 2" becomes "MVP is Phase 1";
   - spec 10: Phase 1 adds production, multi-level MRP and subcontracting, Phase 2 "Assembly" is removed, the pilot criteria allow a manufacturing pilot, the lean-scope sentence covers manufacturers, and the planning-phase line and "assembly (Phase 2)" are removed;
   - spec 11: step 3's "BOM levels in Phase 2" points to the production core step, the step 10 large dataset includes the manufacturing company, and the step-to-phase mapping is updated;
   - runbook: steps 0–4 (DS-09 "BOM levels left for Phase 2") and go-live's list of done design items (through DS-55).
   Source: ADR-0032.R7, ADR-0032.R7.N4

R14. This decision answers: planning's phase (DS-43) is Phase 1; the proposed cuts of warehouse and first-slice planning features (OPT-12) are not made, and confirming the items left for later stays open; production cost collection and WIP under TT99 and TT133 (DS-41) stays open, but is needed before DS-53.
Source: ADR-0032.R8

R15. The author decides, one by one, whether these other candidates are core for Phase 1 (open): group-currency logic (OPT-13); derivation traces beyond costing (DS-45); fixed assets and loans (Phase 3); payroll. Multi-level approval is answered by approval pools with several stages, designed in ADR-0055 (accepted 2026-11-15).
Source: ADR-0032.R9, ADR-0032.R9.N1, ADR-0032.R9.N2, ADR-0032.R9.N3

### Later-phase seams that production builds on

R16. `fixed_asset` is a stub table with `id`, `company_id`, `code`, `name` and `recorded_at`, unique on (`company_id`, `code`), with RLS, owned by `ledger` until the `assets` module (layer 3, Phase 3; ADR-0022.R2) exists, and designed in Phase 3. `cost_object` exists from the first migration too, so the foreign keys to both tables exist from then. `cost_object` is a cost collector owned by `production`, which is in Phase 1 and designed in full on these seams (ADR-0032.R4). It has `id`, `company_id`, `code` and `name`, unique on (`company_id`, `code`), with RLS, and the columns of ADR-0035.R1: `kind`, `production_order` (one per production order, ADR-0034.R15) or `cost_pool`; `production_order_id` or `cost_center_id`, matching the kind; `state` (`open`, `closed`); and `recorded_at`. How regimes collect production cost and value WIP at period end is an author question.
Source: ADR-0025.R2, ADR-0032.R4

R17. Production adds, without touching the core: the tables `bill_of_materials` and the full `cost_object`; the catalog entries for movement types (issue to cost collector, receipt from it, by-product, disassembly), the costing roles `production_input` and `production_output`, and WIP and settlement transaction keys; and the module `production` (Phase 1, ADR-0032.R4). Reservations (ADR-0023.R11) already treat production demand lines generically. A late landed cost is booked in the period of the cost document's own posting date, which must be a period that is not locked, as a value-only `receipt_addition`, so it enters that period's actual average and production consumers need no special treatment there; the consumer split of ADR-0021.R7 is not used (ADR-0021.R6.N2, ADR-0021.R7.N1).
Source: ADR-0025.R8, ADR-0025.R8.N1, ADR-0032.R4

### Production master data: ownership and effect classes

R18. Production master data answers, per made item, how it is made, from what, where and in how long. It lives in `production` and leaves the product and item model of ADR-0018 unchanged. Its objects: the bill of materials (components, co-products and by-products, revised by immutable released revisions each valid from a date); the routing (operations at work centers with standard times and activity quantities, revised the same way); the work center (activities, capacity, calendar, cost center and bins); the production version (the one explicit way to make an item in a production warehouse: a bill of materials, a routing, a lot-size range and a date range; every made item needs one); the production setting (per item and production warehouse, whether the item is a phantom).
Source: ADR-0033.D0

R19. The Phase 1 target is assembly-type manufacturing; the structures also carry batch work with co-products and by-products, so process manufacturing later needs no structural change. The concepts follow SAP's production planning, simplified: one bill of materials model with a usage; a linear operation sequence; revisions instead of change-number management. The plant is the site of the production warehouse (ADR-0068.R10); production versions, work centers and orders name a production warehouse. Agents read the structures through deterministic queries, draft revisions freely, and reach a release or any other effective change only through a change proposal (ADR-0029).
Source: ADR-0033.D0

R20. `production` (layer 3) owns every table of ADR-0033. Planning (layer 4) and documents read production master data through `production.contract`. Bills of materials refer to items (ADR-0018.R2), never to products, except the product-level bill of materials of a configurable product (R25).
Source: ADR-0033.R1

R21. Components and outputs are items of `stock` products. Consumables of `non_stock` products are not components; they reach production cost as overhead (DS-53). Services enter through external operations (R56; DS-55).
Source: ADR-0033.R1

R22. The draft commands `CreateBillOfMaterials`, `CreateBillOfMaterialsRevision`, `UpdateBillOfMaterialsRevision`, and the same commands for routings, create and edit draft revisions. They have effect class `other` (ADR-0027.R17) and are registered `is_draft_only`, so agents, also a tainted run, run them directly; a header has no effect without a released revision and a production version.
Source: ADR-0033.R2, ADR-0033.R2.N1

R23. The effective commands have effect class `master_data_change`, so agents reach them only through change proposals (ADR-0029.R2): `ReleaseBillOfMaterialsRevision` and `ReleaseRoutingRevision`; the production version, work center, activity type and production setting commands; the deactivation of a bill of materials or routing.
Source: ADR-0033.R2

R24. The target record of a release proposal is the draft revision, and its `expected_version` is the draft's `content_hash` (R27), so the approved content is exactly what is released. A release proposal is created only for a draft without proposal-item references, after binding, so its `expected_version` is the bound draft's content hash (`bill_of_materials_item_pending`; ADR-0062.R10, ADR-0062.R13, ADR-0062.R14).
Source: ADR-0033.R2, ADR-0033.R2.N1

### Bills of materials and revisions

R25. A `bill_of_materials` has `item_id` (the main output), `usage` (`production`; `kit` is reserved for sales kits, whose rules DS-22 designs), `alternative` (a short code unique per item and usage), `name` and `is_active`. A configurable product has a product-level bill of materials with `product_id` instead of `item_id`, whose main output at explosion is the configured item (ADR-0046.R12). While every revision is a draft, the main output may be the `CreateProduct` or `CreateItem` item of a change proposal, named by `proposed_change_proposal_item_id`; exactly one of `item_id`, `product_id` and `proposed_change_proposal_item_id` is set.
Source: ADR-0033.R3, ADR-0033.R6.N2

R26. The content of a bill of materials lives in `bill_of_materials_revision` rows with `revision` (an integer, numbered at creation), `state` (`draft`, `released`), `start_date`, `base_quantity`, `assembly_scrap_percent`, `main_output_cost_coefficient`, `content_hash`, `released_at` and `copy_from_revision_id`. At most one draft exists per bill of materials at a time, otherwise `draft_revision_exists`.
Source: ADR-0033.R3

R27. `base_quantity` is in the main output's inventory unit, so small per-unit quantities stay exact. `content_hash` is the SHA-256 of the canonical JSON (ADR-0008.R12 forms) of the header fields and its components and outputs, ordered by position.
Source: ADR-0033.R3

R28. A database trigger rejects updates of released revisions (`revision_released`). A change is a new revision, created as a copy (`copy_from_revision_id`), edited in draft and released.
Source: ADR-0033.R3

R29. The valid released revision on a date is the one with the highest `revision` whose `start_date` is on or before that date. The end of validity is derived, never stored.
Source: ADR-0033.R4

R30. A release's `start_date` must be on or after the company's current date (ADR-0007), except for the first released revision of a bill of materials; otherwise the release is rejected with `revision_retroactive`.
Source: ADR-0033.R4

R31. A release's `start_date` must be on or after the latest released revision's, otherwise `revision_start_date_order`. It may be equal only under R32.
Source: ADR-0033.R4

R32. A revision released by mistake is withdrawn by a new revision with the same `start_date`, as long as no production order or cost estimate refers to it, otherwise `revision_in_use`.
Source: ADR-0033.R4

R33. Every explosion, version selection and revision selection uses one `explosion_date`: the planned start date of the order or planned order, in the company's time zone (ADR-0007). MRP (DS-54), order creation (DS-52), cost estimates (DS-53; their costing date acts as the `explosion_date`) and the explosion query (ADR-0033.R15) all use it.
Source: ADR-0033.R5

R34. A production order copies the revisions valid on its `explosion_date` and keeps their IDs. DS-52 states whether a change of the planned start date before release explodes the order again.
Source: ADR-0033.R5

R35. One version-selection rule serves every caller. Forward scheduling selects the version (ADR-0033.R13) on the start date. Backward scheduling selects it on the end date, schedules backward, and requires the selected version to be valid on the resulting start too: active, its dates and lot range covering it, and its bill of materials and routing each with a released revision valid there. Otherwise the next version in ADR-0033.R13's order that is valid on the end date is tried; when none is valid on both dates the result is `production_version_missing`. When a backward schedule is moved forward from `earliest_start` (ADR-0036.R3), the same check applies at the new start. The explosion uses the revisions valid on the resulting start.
Source: ADR-0033.R5.N1

### Components and outputs

R36. `bill_of_materials_component` rows of a revision have `position`, `component_item_id`, `quantity` per base quantity with its unit (`uom_id`), `component_scrap_percent`, `is_fixed_quantity` (the same quantity whatever the order size, e.g. setup material), `operation_number` (optional; the routing operation that consumes it), `consumption_method` and an optional `issue_multiple` in the line's unit. The conversion factor is a snapshot without a default (no DDL `DEFAULT 1`, ADR-0056.R17) (`uom_numerator`, `uom_denominator`, `uom_factor_source`); the quantity in the component's inventory unit is the exact rational `quantity × uom_numerator / uom_denominator` (exact by `numerator` and `denominator`, ADR-0018.R11), not a stored column.
Source: ADR-0033.R6, ADR-0033.R6.N1

R37. `consumption_method` is one of `manual` (issued by a goods issue), `backflush_at_operation` (issued when its operation is confirmed) or `backflush_at_receipt` (issued when output is received). DS-52 defines each.
Source: ADR-0033.R6

R38. The planned output quantity Q of an order for a good quantity G is `G / (1 − assembly_scrap_percent / 100)`, stored rounded up to the main output's inventory unit; requirements are computed from the stored Q. For Q, a component's requirement is `quantity × Q / base_quantity × (1 + component_scrap_percent / 100)`; a fixed-quantity component takes `quantity × (1 + component_scrap_percent / 100)`, not scaled by Q. Co-products and by-products scale as `quantity × Q / base_quantity`. Through phantoms, intermediate quantities stay exact rationals and are never rounded.
Source: ADR-0033.R6, ADR-0033.R6.N1

R39. Requirements are computed as exact rationals and rounded once per order line, up (away from zero): first to whole multiples of `issue_multiple` when it is set, then to the component's inventory unit. `round_quantity` takes an optional mode argument with ADR-0006.R17's modes; rounding half away from zero (ADR-0018.R11) would under-issue. `quantity_per_value` stays `types.quantity`; a finer rate uses a smaller unit (ADR-0056.R8, ADR-0056.R17).
Source: ADR-0033.R6, ADR-0033.R6.N1

R40. While every revision is a draft, a component may name the `CreateProduct` or `CreateItem` item of a change proposal by its stable ID (`proposed_change_proposal_item_id`) instead of an item; such a line is in the proposed inventory unit with the identity snapshot. `BindProposedItems` replaces the reference by the created item when the proposal is executed and recomputes the snapshot. Co-products and by-products are existing items (ADR-0062.R10, ADR-0062.R14).
Source: ADR-0033.R6.N2

R41. Components of a product-level bill of materials carry a `selection_condition` and `fixed` or `linear` sizing over item-defining characteristics, applied before the requirement formula (ADR-0046.R12, ADR-0046.R13).
Source: ADR-0033.R6

R42. `bill_of_materials_output` rows of a revision list outputs besides the main one: `output_item_id`, `quantity` per base quantity with its unit, `output_type` (`co_product` or `by_product`) and `cost_coefficient` (co-products only). Outputs carry the same conversion snapshot as components, without a default factor. Planned co-product and by-product quantities round half up, each in its own inventory unit.
Source: ADR-0033.R7, ADR-0033.R7.N1

R43. `cost_coefficient` and `main_output_cost_coefficient` hold equivalence coefficients as data only. Whether the coefficient method applies is the regime setting `production.co_product_split` (ADR-0035.R18). By-products are valued from the company's price list of kind `by_product`, standing for net realisable value, with value source `regime`; the seed and its legal basis are flagged package content of the localization package, `unverified` (ADR-0035.R13, ADR-0045.R2, ADR-0016).
Source: ADR-0033.R7

R44. An item may not be both a component and an output of one revision (`item_both_component_and_output`), except in rework orders (ADR-0034.R2); recycling loops are not modeled in Phase 1. A phantom's bill of materials may not have outputs (`phantom_with_outputs`). This is checked when `is_phantom` is set (ADR-0033.R14), and at release and production version save for an item that is a phantom in the version's warehouse.
Source: ADR-0033.R7

### Release checks, low-level codes and locking

R45. Releasing a revision checks, deterministically: components and outputs are active items of `stock` products, distinct from the main output; units are convertible; quantities and the base quantity are positive; scrap percentages are in [0, 100).
Source: ADR-0033.R8

R46. The release cycle check uses a graph with an edge from each main output to its components and to its co-products and by-products. The graph holds every released revision of every `production` bill of materials, superseded and future ones included, plus the revision being released. A configurable product with a product-level bill of materials is a node with edges to its components and outputs; an edge into a configured item is an edge into its product node. A cycle is rejected with `bill_of_materials_cycle`, naming the path. Rework that feeds an item back into its own production is a production order matter (DS-52), never a bill of materials. `INV-100` covers the graph, product nodes included.
Source: ADR-0033.R8, ADR-0033.R8.N1

R47. `item_low_level_code` (company, item, `low_level_code`) is a read model owned by `production`, recomputed downward for every item a release reaches: the longest path from an item that is never a component or an output, so 0 for top items. A code may fall when a component is removed. A configured item has no structure of its own; its `item_low_level_code` is its product's. MRP plans in that order (DS-54).
Source: ADR-0033.R8, ADR-0033.R8.N1

R48. For every production version that pairs the bill of materials with a routing on dates from the revision's `start_date`, each `operation_number` must exist in the routing revision valid on that date; otherwise the release is rejected with `operation_not_in_routing`.
Source: ADR-0033.R8

R49. Releasing also checks that no component or main output refers to a proposal item (`bill_of_materials_item_pending`) and, for a routing revision, that every operation's setup and run times were stated (`routing_duration_unstated`). The database refuses both too, also for a revision inserted as released, and refuses a proposal reference on a header with a released revision (ADR-0062.R10, ADR-0062.R14).
Source: ADR-0033.R8.N2

R50. Releases, production version saves, production setting saves and deactivations of bills of materials and routings lock the company's `production_structure` row (created with the company) at class 3 of ADR-0027.R10, beside the planning state row. Two concurrent changes therefore cannot create a cycle or break an operation reference together.
Source: ADR-0033.R8

### Routings and operations

R51. A `routing` (`code`, `name`, `is_active`) may serve several items. Its `routing_revision` rows (`revision`, `state`, `start_date`, `base_quantity` of output, `content_hash`, `released_at`, `copy_from_revision_id`) follow R26 to R32 and R34: numbering, content hash, immutability, validity, withdrawal and snapshot by orders.
Source: ADR-0033.R9

R52. A routing release runs the operation check of R48 against every bill of materials paired with it by a production version, checks that its work centers are active and belong to the production warehouse of every version that uses it (`work_center_outside_warehouse`), and takes the lock of R50.
Source: ADR-0033.R9

R53. Deactivating a bill of materials or routing is rejected while an active production version uses it (`in_use_by_production_version`).
Source: ADR-0033.R9

R54. Operations of a configurable product's routing carry a `selection_condition` and linear sizing of their durations (ADR-0046.R12).
Source: ADR-0033.R9

R55. `routing_operation` rows of a revision form one linear sequence, with `operation_number` (ascending, e.g. 10, 20, 30), `work_center_id`, `description`, `control`, `is_milestone` (confirming it confirms the earlier non-milestone operations), `setup_duration`, `run_duration`, `operation_scrap_percent`, `queue_time` and `move_time`. `operation_scrap_percent` is not used in requirements; DS-52 uses it for expected yield per operation and DS-53 for the scrap variance. `queue_time` and `move_time` are hours of calendar time before and after the operation.
Source: ADR-0033.R10

R56. `control` is `internal` (run at the work center, which is then required) or `external` (done by a subcontractor, DS-55: `service_item_id` and `default_supplier_id` are required and the work center is optional; the purchase may choose another supplier, so a revision does not depend on one processor). Subcontracting of `external` operations follows ADR-0037.R2 to ADR-0037.R6.
Source: ADR-0033.R10

R57. `setup_duration` (hours per order) and `run_duration` (hours per base quantity) are the elapsed time used for scheduling, lead times and the load view. `is_setup_duration_stated` and `is_run_duration_stated` (default true) mark, when false, a time no source stated; it is then 0, nothing reads it as real, and release refuses it. Agent workflows never write a time that is not in a source (ADR-0062.R10).
Source: ADR-0033.R10, ADR-0033.R10.N1

R58. `routing_operation_activity` rows, inside the revision and inside its hash, hold the standard quantity of each activity type for costing: `activity_type_id`, `quantity` and `basis` (`per_order` for setup, `per_base_quantity` for run). Labor and machine time can therefore differ from the duration.
Source: ADR-0033.R10

R59. A routing without operations is allowed: the item is then made in one step. Parallel and alternative sequences and overlapping operations come after Phase 1. A phantom's components take the operation number of the phantom's line in the parent.
Source: ADR-0033.R10

R60. The attachments of a routing operation are the work order's instructions on the tablet, found through the order's snapshot revision and operation number (ADR-0071.R14).
Source: ADR-0033.R10.N2

## Invariants

| ID | Name | Check point | Statement | Protects |
| --- | --- | --- | --- | --- |
| `INV-100` | `bom_acyclic_low_level_codes` | `day` | No cycle exists through released production bills of materials, counting outputs as children and a configurable product as the node of its configured items; every component's and output's low-level code is greater than each parent's, and a configured item's equals its product's. | R46, R47 |

## Edge cases

| ID | Name | Case | Outcome | Protects |
| --- | --- | --- | --- | --- |
| `EC-204` | `alternative_version_invalid_on_new_start` | An alternative version valid on the order's end date but not on the recomputed start is not offered as a candidate. | `must_succeed` | R35; ADR-0064.R16 |

## Conflicts

CONFLICT ADR-0033.D0: ADR-0068.R10 supersedes "the production warehouse in place of a plant": the plant is the site of the production warehouse (R19).
CONFLICT ADR-0033.R7: ADR-0035.R13, ADR-0035.R18.N2 and ADR-0045.R2 govern the open valuation points: the coefficient method is `production.co_product_split`, by-products are valued from the `by_product` price list as flagged package content (R43).
CONFLICT ADR-0032.R5: ADR-0078.R2 moves the production agent types to Phase 2 with mode `off`; the production core and manual capture stay Phase 1 (R8).
CONFLICT ADR-0025.R2: the closing note of the rule and ADR-0034.R15 make `production` the owner of `cost_object`; ADR-0035.R1 with the DS-06 DDL adds `kind`, `production_order_id` or `cost_center_id` and `state`; ADR-0032.R4 removes "designed in Phase 2" (R16).
CONFLICT ADR-0025.R8: ADR-0032.R4 governs the phase, production being built in Phase 1 rather than added in Phase 2, and ADR-0025.R8.N1 removes the landed cost consumer split in favour of `receipt_addition` in the period of the cost document's posting date (ADR-0021.R6.N2) (R17).
CONFLICT ADR-0032.R3: the note ADR-0032.R3.N1 turns the open standard cost question into a decision of the chief architect, a later price-control option with periodic actual cost kept until then (R5).
CONFLICT ADR-0032.R7: the notes ADR-0032.R7.N1, ADR-0032.R7.N2, ADR-0032.R7.N3 and ADR-0032.R7.N4 answer the author decisions of this rule: step 4b, no dates, step 5b for planning and subcontracting, production agents in Phase 2 (R10 to R13).
CONFLICT ADR-0032.R7.N2: superseded in its sentence that the runbook does not place the planning agent; ADR-0032.R7.N3 places it after the step 5b gate, and its move of production agent types to Phase 2 stands (R12).
CONFLICT ADR-0032.R7.N3: this note replaces the open placement of planning work in the earlier note; build step 5b after gates of steps 4b and 5 governs (R12).
CONFLICT ADR-0032.R9: its notes ADR-0032.R9.N1 to ADR-0032.R9.N3 take multi-level approval off the open list, since approval pools with stages are designed and accepted in ADR-0055 (R15).
CONFLICT ADR-0033.R4: the index marks the rule superseded only because its text speaks of a revision superseded by a new revision; no later unit replaces it, and R29 to R32 state it as written.
CONFLICT ADR-0033.R6: the note ADR-0033.R6.N2 governs the item reference of draft lines, which may name a proposal item instead of an item, and ADR-0033.R6.N1 makes the inventory-unit quantity a computed rational, not a stored column; ADR-0056.R17 drops the DDL `DEFAULT 1` of the factor and aligns this rule with the DDL (R36, R40).
CONFLICT ADR-0033.R6.N2: flagged for "instead of" and "replaces"; it amends drafts only, binding replaces the proposal reference by the created item, and release refuses any remaining reference (R40, R49).
CONFLICT ADR-0033.R3: the DS-43-54 DDL and ADR-0033.R6.N2 add `proposed_change_proposal_item_id` as a third possible main output of a header beside `item_id` and `product_id` (R25).

## Trace

| Source | Where |
| --- | --- |
| ADR-0009.R19 | ref: ADR-0009.R19 |
| ADR-0009.R19.N1 | ref: ADR-0009.R19 |
| ADR-0010.R5 | ref: ADR-0010.R5 |
| ADR-0012.R4 | ref: ADR-0012.R4 |
| ADR-0014.R10 | ref: ADR-0014.R10 |
| ADR-0014.R10.N1 | ref: ADR-0014.R10 |
| ADR-0014.R10.N2 | ref: ADR-0014.R10 |
| ADR-0020.R11.N1 | ref: ADR-0020.R11 |
| ADR-0024.R16 | ref: ADR-0024.R16 |
| ADR-0024.R26 | ref: ADR-0024.R26 |
| ADR-0024.R26.N1 | ref: ADR-0024.R26 |
| ADR-0024.R26.N2 | ref: ADR-0024.R26 |
| ADR-0025.D0 | ref: ADR-0025.D0 |
| ADR-0025.R2 | R16 |
| ADR-0025.R3 | ref: ADR-0025.R3 |
| ADR-0025.R4 | ref: ADR-0025.R4 |
| ADR-0025.R5 | ref: ADR-0025.R5 |
| ADR-0025.R8 | R17 |
| ADR-0025.R8.N1 | R17 |
| ADR-0027.R10 | ref: ADR-0027.R10 |
| ADR-0027.R10.N1 | ref: ADR-0027.R10 |
| ADR-0027.R10.N2 | ref: ADR-0027.R10 |
| ADR-0032.D0 | R2 |
| ADR-0032.R1 | R1 |
| ADR-0032.R2 | R3 |
| ADR-0032.R3 | R4, R5 |
| ADR-0032.R3.N1 | R5 |
| ADR-0032.R4 | R6, R16, R17 |
| ADR-0032.R5 | R7, R8 |
| ADR-0032.R5.N1 | R7 |
| ADR-0032.R6 | R9 |
| ADR-0032.R7 | R10-R13 |
| ADR-0032.R7.N1 | R10, R11 |
| ADR-0032.R7.N2 | R12 |
| ADR-0032.R7.N3 | R12 |
| ADR-0032.R7.N4 | R12, R13 |
| ADR-0032.R8 | R14 |
| ADR-0032.R9 | R15 |
| ADR-0032.R9.N1 | R15 |
| ADR-0032.R9.N2 | R15 |
| ADR-0032.R9.N3 | R15 |
| ADR-0033.D0 | R18, R19 |
| ADR-0033.R1 | R20, R21 |
| ADR-0033.R2 | R22-R24 |
| ADR-0033.R2.N1 | R22, R24 |
| ADR-0033.R3 | R25-R28 |
| ADR-0033.R4 | R29-R32 |
| ADR-0033.R5 | R33, R34 |
| ADR-0033.R5.N1 | R35 |
| ADR-0033.R6 | R36-R39, R41 |
| ADR-0033.R6.N1 | R36, R38, R39 |
| ADR-0033.R6.N2 | R25, R40 |
| ADR-0033.R7 | R42-R44 |
| ADR-0033.R7.N1 | R42 |
| ADR-0033.R8 | R45-R48, R50 |
| ADR-0033.R8.N1 | R46, R47 |
| ADR-0033.R8.N2 | R49 |
| ADR-0033.R9 | R51-R54 |
| ADR-0033.R10 | R55-R59 |
| ADR-0033.R10.N1 | R57 |
| ADR-0033.R10.N2 | R60 |
