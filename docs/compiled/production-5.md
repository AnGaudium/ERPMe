Module: production    Chunk: 5 of 7    Source ADRs: ADR-0046, ADR-0056, ADR-0060, ADR-0062, ADR-0064
Build step(s): 3, 4, 5    Generated from index: 30d5706    Compiled by: Claude Opus 5.5, 2026-11-21

# Compiled spec: `production`, chunk 5

## Purpose

`production` owns production master data, production orders, their execution and production costing, in layer 3
(ADR-0022.R2). This chunk states the configured explosion and the valuation of configured items, units on bills of
materials and production lines, the stored production variance split, the `production` side of the product engineering
workflow (readiness check, draft estimates with gaps, pending proposal items, engineering change, its data and catalog
rows), and the production order queries, rankings and daily check of ADR-0064. The agent types, the pegging query and the
shortage resolution belong to `agents` and `planning`; their units are traced `ref:` and not restated.

## Entities and tables

DDL: `docs/design/DS-43-54-planning-production.sql`.

| Table | Meaning | Key | Parent | Owner |
| --- | --- | --- | --- | --- |
| `cost_estimate_gap` | What a draft estimate could not price, one row per gap, with its `gap_kind` and subject (R828, R844) | `id`; unique (`cost_estimate_id`, `gap_number`) | `cost_estimate` | `production` |

Named here, defined by rule without DDL in chunk 4: `production_order_variance` (R820, R864).

The rules of this chunk add to tables whose rows stand in other chunks: `bill_of_materials` and `bill_of_materials_component` (`proposed_change_proposal_item_id`, R832, R844), `bill_of_materials_output` (unit snapshot, R815), `routing_operation` (`is_setup_duration_stated`, `is_run_duration_stated`, R844), `cost_estimate` (`production_version_id` optional for drafts, `previous_cost_estimate_id`, `item_id`, R809, R827, R830), `production_order`, `production_order_component` and `production_version` (R853-R870).

Reads: `item`, `product`, `preliminary_price`, `change_proposal_item`, `change_proposal_execution_item`, `audit_record`, `product_category_requirement`, `item_manufacturer_part`, `code_series`, `stock_reservation`, `demand_supply_line`, `agent_run`, `costing_sheet`.

## Commands and queries

| Name | Actor and authorization | Input | Effect | Events | Error codes |
| --- | --- | --- | --- | --- | --- |
| `GetConfigurationEstimate` (query) | not stated | Product, item-defining values, date | Returns `production.contract.estimate_configuration` (R806) | None | Check result `preliminary_price_missing` (R808) |
| `GetProductReadinessCheck` (computed query) | `production_structure` at `read` | Item or proposal item, date | Returns the readiness check (R825, R826) | None | Check result `readiness_requirement_missing` |
| `BindProposedItems` (consumer only, effect class `other`) | Verb Bind at `edit` on `production_structure`; run by the consumer `proposed_item_binding` | The executed item proposal | Binds draft references to created items and recomputes snapshots (R835, R836) | Raises the work item `product_release_ready` | not stated |
| `ListComponentShortage` (computed query) | `production_order` at `read` | Filters: item, warehouse, order, requested date range, `is_short_only` | One row per open component line with short and uncovered quantities (R853-R856) | None | not stated |
| `EvaluateProductionOrderRelease` (`Evaluate` query) | `production_order` at `read` | Order, business date | Returns reasons and a verdict (R857-R859) | None | not stated |
| `GetProductionOrderUsageVariance` (computed query) | `report_production` at `read` | Order, optional posting-date range | Quantity variances of components and operations (R861, R862) | None | not stated |
| `ListProductionOrderVarianceDriver` (computed query) | `report_production` at `read`; field class `cost` on amounts | Settled order and period | Document lines behind each variance category (R863, R864) | None | not stated |
| `RunProductionOrderCheck` (internal system job, verb Run, effect class `other`) | System, on `production_order` | Explicit business date | Raises and closes production order work items (R866-R870) | Work items of R867-R870 | not stated |

Not commands: the pure functions `production.contract.estimate_configuration` (R806), the configured explosion of
`production.contract` (R801-R804), `production.rank_reservation_demand` (R860) and `production.rank_variances` (R865);
the consumer of `ConfiguredItemCreated` (R809) and the consumer `proposed_item_binding` (R835).

Codes raised by the rules of this chunk without a command row here: `bill_of_materials_item_pending` (refused by
`ReleaseBillOfMaterialsRevision` and by the creation of a release proposal, R834), `proposed_item_not_creating` (R832),
`proposal_item_referenced` (R833), `cost_estimate_incomplete` (R829), `routing_duration_unstated` and `item_unresolved`
(R846); check results `configured_explosion_empty` (R804), `configured_stock_available` (R813), `cost_estimate_gap`
(R828) and `item_duplicate_suspected` (R847).

## Rules

### Configured explosion

R801. `production.contract`'s explosion (ADR-0033.R5, ADR-0033.R6; ADR-0036.R3) takes the item-defining values. It keeps the components and operations whose condition is true, and sizes them, before the requirement formula of ADR-0033.R6. Quantities stay exact rationals and are rounded once per order line.
Source: ADR-0046.R13

R802. The explosion is one function: MRP, `CreateProductionOrder`, cost estimates, `estimate_configuration` and the explosion query all use it, so a planned order, the real order and the estimate agree.
Source: ADR-0046.R13

R803. A production order copies the selected, sized lines and keeps the configuration's ID, so it never re-reads the model.
Source: ADR-0046.R13

R804. A configured explosion with no component returns the check result `configured_explosion_empty`. Unknown values cannot occur, because explosions run only for complete configurations.
Source: ADR-0046.R13

### Valuation of configured items

R805. Configured items are valued by periodic average per item (ADR-0020.R11), so each configuration keeps its own cost.
Source: ADR-0046.R14

R806. `production.contract.estimate_configuration(product, item-defining values, date, purpose)` is a pure function with no table: the configured explosion of the product-level version valid on the date, priced as ADR-0035.R14 does, applying the costing sheet of the product-level version, else of its site. `purpose` is a parameter of the function, default `production`. The query `GetConfigurationEstimate` exposes it.
Source: ADR-0046.R14, ADR-0046.R14.N4, ADR-0046.R14.N5

R807. The cost checks of ADR-0043.R3 and ADR-0045.R5 ("below cost", margin) use `estimate_configuration` whenever the line's item or the item's preliminary price is missing, so a first-time configuration is checked at a quotation's or order's `Submit` like any other. These checks keep the production cost; `GetSellingPriceCosting` adds the administration and selling rows for cost-plus quotes (ADR-0072.R9, ADR-0072.R10).
Source: ADR-0046.R14, ADR-0046.R14.N4

R808. When the estimate cannot be computed (a component without a price), the check returns `preliminary_price_missing` as a check result. The unknown cost sets the policy condition `is_cost_unknown`, and the seeded rule requires approval (ADR-0043.R3, ADR-0043.R15; ADR-0047.R22). Treating the unknown cost as needing human confirmation is flagged.
Source: ADR-0046.R14, ADR-0046.R14.N2

R809. The consumer of `ConfiguredItemCreated` releases the item's cost estimate, a `cost_estimate` (ADR-0035.R14) with `item_id`, as derived data from released structures, with no approval (flagged). It writes no `preliminary_price` row, so `UpdatePreliminaryPrice` (`human_only`) is not involved. If the consumer fails, it creates a work item `configured_estimate_failed` for the accountant.
Source: ADR-0046.R14, ADR-0046.R14.N3

R810. Where an item's estimate is read (ADR-0020.R11; ADR-0035.R4 reads it as the fallback for an item without history), it is the latest released estimate for the item whose costing date is on or before the posting date, preferring one whose version's production warehouse is in the line's valuation area. Its price basis is ADR-0035.R14's default, set by `production.estimate_price_basis`, whose interim value the regime package seeds (flagged, ADR-0035.R18) is `actual_average`.
Source: ADR-0046.R14, ADR-0046.R14.N3

R811. When the consumer fails, the item stays usable on quotations and orders, whose cost checks use `estimate_configuration`. A production receipt of the item, which has no history and no released estimate, is rejected with `preliminary_price_missing` until an estimate is released or a person sets a preliminary price (ADR-0035.R4).
Source: ADR-0046.R14, ADR-0046.R14.N3

R812. Strategy `make_to_order` reserves the output to the sales line (ADR-0034.R14), so a configured unit is never delivered to another customer by accident. A returned unit returns to its own item's stock.
Source: ADR-0046.R14

R813. Free stock of a configured item (a return, a cancelled order) is not netted by make-to-order planning (ADR-0036.R9). A planning run that plans an order for a line while free stock of the same item exists returns the check result `configured_stock_available`, naming the stock, and a person may reserve it. `configured_stock_available` is side information of a planning run, so it is unhashed like `planning_parameter_missing` (ADR-0040.R10; DS-04 `checks`).
Source: ADR-0046.R14, ADR-0046.R14.N1

R814. Line options carry no cost (ADR-0046.R12): their price extras are pure price. This split closes ADR-0045.R15's open point on the cost and stock of options.
Source: ADR-0046.R14

### Units on bills of materials and production lines

R815. Bill of materials component and output lines may use any allowed unit of their item, stored with the snapshot (`uom_numerator`, `uom_denominator`, `uom_factor_source`). There is no default factor. The quantity in the inventory unit is `quantity × uom_numerator / uom_denominator`, an exact rational, not stored.
Source: ADR-0056.R17

R816. An optional `issue_multiple` on a component, in the component line's own unit, rounds each order-line requirement up to whole multiples (whole cans, rolls or reels). The order is: the exact requirement with scrap; then up to a whole multiple of `issue_multiple × factor`; then up to the inventory unit's decimals. The difference above the theoretical requirement is planned consumption, visible in costing.
Source: ADR-0056.R17

R817. Production issue, production receipt, generated backflush, transfer and count lines carry the line unit block of ADR-0056.R9. Posted production lines keep their item, unit and snapshot (ADR-0034.R8).
Source: ADR-0056.R17

R818. `quantity_per_value` stays `types.quantity` (ADR-0006 quantity scale, 6 decimals). A finer rate uses a smaller unit on the line (millimetres instead of metres).
Source: ADR-0056.R17

### Stored production variances

R819. Production variances are ADR-0035.R15's split (input price, input quantity, resource usage, scrap, lot size, remaining), computed by `production`'s variance function, the function behind `GetProductionOrderVariance`. The analysis layer never remodels them.
Source: ADR-0060.R19

R820. When the period's costing run settles a production order's period cost (ADR-0035), `production` writes the split per order, period and variance category to its read model `production_order_variance`, with the order's output item, warehouse and branch. Its DDL comes with the costing tables of DS-53. `production_variance_overview` reads those rows only (ADR-0050.R52: a view never re-implements a module's figure).
Source: ADR-0060.R19

R821. Under actual costing variances are not posted (ADR-0035.R15). If the author chooses standard cost valuation, the posted variance lines become the source and the measure keeps its code. Reading the stored split instead of posted variance lines deviates from the architect's decision 6 and is stated for review.
Source: ADR-0060.R19

### Product engineering workflow

R822. The `product_engineering` workflow chains the existing commands, checks and proposal carrier for products, items, bills of materials, routings and cost estimates (ADR-0033, ADR-0035, ADR-0045, ADR-0029), so that a person's note, a person's own spreadsheet loaded as an import batch, or a verified outside document becomes released master data without a model ever choosing a number. Outside content never starts a drafting run directly in Phase 1: a person verifies its extraction (ADR-0057), then starts the run on their own note that refers to the verified extraction. The agent type `product_engineering` is Phase 2, registered with mode `off`; the work item kinds it would wake on are raised and handled by people (ADR-0078.R2).
Source: ADR-0062.D0

R823. Each component is resolved by exact code, barcode, the named supplier's code, the named manufacturer's part number, then a deterministic ranking with blocking; each step must find exactly one item, and several hits go to the model or a person, never to an automatic pick. The model sees at most five candidates and picks one or says `new_item_needed` with evidence; it drafts quantity structure, never a cost, code, standard time, rate or price unless it stands in its source. Release runs only through an approved change proposal whose approver is not the person whose request started the run.
Source: ADR-0062.D0

R824. D6 `check` runs `GetBillOfMaterialsRevisionCheck` on the draft (ADR-0033.R15), plus the pending-item check of `bill_of_materials_item_pending` (R834).
Source: ADR-0062.R11

R825. `GetProductReadinessCheck` (module `production`, computed query at `read` on `production_structure`; item or proposal item, date) checks: the category's requirements (`product_category_requirement`: attributes, dimensions, weights, barcode, supplier item, bill of materials, routing, production version, cost estimate, classification); every make item has a bill of materials and a routing; every internal operation's work center has activity rates for the date; every component has a price on the estimate's price basis or a released estimate; units convert.
Source: ADR-0062.R11

R826. Each missing readiness requirement is a check result `readiness_requirement_missing` with its code.
Source: ADR-0062.R11

R827. D7 `estimate`: `CreateCostEstimate` computes on the draft revisions (ADR-0035.R14 note). `production_version_id` may be empty for a draft estimate, which names the draft bill of materials and routing revisions and the costing lot quantity.
Source: ADR-0062.R12

R828. A gap is never priced as zero. Each of these is a `cost_estimate_gap` row of its `gap_kind`, left out of the total, which the response states as incomplete with the check result `cost_estimate_gap`:
   - `material_price_missing`: a missing purchase price;
   - `activity_rate_missing`: a missing activity rate;
   - `activity_quantity_missing`: a missing activity quantity;
   - `component_item_pending`: a pending item;
   - `setup_duration_unstated`, `run_duration_unstated`: an unstated setup or run time;
   - `routing_missing`: a missing routing;
   - `costing_rate_missing`: a costing sheet row without a valid rate, naming the sheet and row (ADR-0072.R7);
   - `costing_sheet_missing`: no sheet while `production.costing_sheet.required` is true (ADR-0072.R9).
   Source: ADR-0062.R12, ADR-0062.R12.N1

R829. A released estimate has no gap and has a production version; releasing one that does not is refused with `cost_estimate_incomplete`.
Source: ADR-0062.R12

R830. When the output item has a released estimate valid on the costing date, the new estimate names it in `previous_cost_estimate_id`, and the response gives the difference per cost component and per line.
Source: ADR-0062.R12

R831. The estimate is never computed or adjusted by the model and never sent to it. Like costs, rates are never written by the model (ADR-0072.R18).
Source: ADR-0062.R12, ADR-0062.R12.N1

### Pending proposal items

R832. `bill_of_materials` and `bill_of_materials_component` may name a proposal item (`proposed_change_proposal_item_id`, the stable `change_proposal_item.id`, with a company key) instead of an item, only while every revision of that bill of materials is a draft and only for a `CreateProduct` or `CreateItem` item of an open proposal (`proposed_item_not_creating`).
Source: ADR-0062.R14

R833. Reordering a proposal's items keeps their IDs. An update of the proposal that would remove or replace an item a draft refers to is refused (`proposal_item_referenced`).
Source: ADR-0062.R14

R834. `ReleaseBillOfMaterialsRevision`, and the creation of a release proposal, refuse a revision with a pending reference (`bill_of_materials_item_pending`). The database refuses it too: a revision becoming released, or inserted as released, while its header or a component refers to a proposal item; and a header given a proposal reference while any of its revisions is released.
Source: ADR-0062.R14

R835. When the item proposal is executed, the `production` consumer `proposed_item_binding` runs `BindProposedItems` (module `production`, effect class `other`, consumer only, verb Bind at `edit` on `production_structure`). It reads each created item's ID from the audit record of its proposal item's execution (`change_proposal_execution_item.audit_record_id`, ADR-0029.R3), sets each draft reference to that item, clears the proposal reference, and recomputes each bound line's conversion snapshot with `convert_quantity` (ADR-0056.R6).
Source: ADR-0062.R14

R836. A line whose unit has no factor to the created item's inventory unit keeps its reference and is named in a note. `BindProposedItems` raises `product_release_ready` for the run's human, whose wake-up starts the continuation (ADR-0062.R3).
Source: ADR-0062.R14

R837. When the item proposal is rejected, canceled or expires, the consumer raises `product_item_proposal_ended` for the run's human; the drafts stay unreleasable until a person chooses an existing item or proposes again. A rejected proposal returns to draft (ADR-0029.R3); when it is submitted again, or approved and executed, the item is resolved.
Source: ADR-0062.R14

R838. The release proposal is drafted after binding, so its `expected_version` is the bound draft's content hash (ADR-0033.R2).
Source: ADR-0062.R14

### Engineering change

R839. In Phase 1 a change to a released structure is a new draft revision (`copy_from_revision_id`) and a change proposal for its release, as in ADR-0062.R13. There is no separate change-order object in Phase 1.
Source: ADR-0062.R15

R840. The impact evidence of an engineering change is: `ListWhereUsed` for the output and the changed components; open production orders and purchase orders that name the superseded components; on-hand stock of superseded components with a disposition per item (`use_up`, `scrap`, `rework`, `return`) chosen by a person in the proposal's evidence; the cost delta (R830); the effectivity date. Dispositions are carried out by ordinary documents, never by the proposal.
Source: ADR-0062.R15

### Product engineering data

R841. `item_manufacturer_part` (DS-20, `master_data`): item, manufacturer name and its normalized form, part number and its normalized form (upper-cased, separators removed, any script); unique per company, normalized manufacturer and normalized part number. Commands `CreateItemManufacturerPart` and `UpdateItemManufacturerPart` are `master_data_change` at `edit` on `product` (proposals for agents).
Source: ADR-0062.R19

R842. `code_series` (DS-20, `master_data`): company, record kind (`product`), optional category, prefix, `next_value`, format; the product code sequence of ADR-0062.R9.
Source: ADR-0062.R19

R843. `product_category_requirement` (DS-20, `master_data`): category, requirement code, optional variant attribute or classification scheme, `is_active`, with company keys; command `SetProductCategoryRequirements` (`master_data_change`, at `edit` on `master_data_group`).
Source: ADR-0062.R19

R844. DS-43-54 holds: the proposal references on `bill_of_materials` and `bill_of_materials_component` with their checks and company keys; `routing_operation.is_setup_duration_stated` and `is_run_duration_stated` with the check that an unstated time is 0; `cost_estimate.production_version_id` optional for drafts and `previous_cost_estimate_id`; `cost_estimate_gap`; the release guards (`production_release_readiness_guard` on update and insert, `bill_of_materials_proposal_guard` on the header).
Source: ADR-0062.R19

R845. The keys from the proposal references to `change_proposal_item` (company, ID) are closed in `DS-36-document-intake.sql`, which loads after both files and adds the key `UNIQUE (company_id, id)` to `change_proposal_item`.
Source: ADR-0062.R19

### Product engineering catalog rows

R846. Errors (DS-04) of the product engineering workflow:
   - `bill_of_materials_item_pending` (precondition);
   - `routing_duration_unstated` (precondition);
   - `cost_estimate_incomplete` (precondition);
   - `proposed_item_not_creating` (validation);
   - `proposal_item_referenced` (conflict);
   - `item_unresolved` (validation).
   Source: ADR-0062.R22

R847. Check results of the workflow: `cost_estimate_gap`, `readiness_requirement_missing`, `item_duplicate_suspected`.
Source: ADR-0062.R22

R848. Work item kinds `product_release_ready` and `product_item_proposal_ended`: module `production`, subject `agent_run`, owner `run_on_behalf_of`, due `days:2`, resolved by a person, declared by `product_engineering`.
Source: ADR-0062.R22

R849. Registered commands and queries of the workflow: `BindProposedItems` (`production`, `other`, consumer only, `production_structure` at `edit`); `GetProductReadinessCheck` (`production`, computed query, `production_structure` at `read`); `CreateItemManufacturerPart`, `UpdateItemManufacturerPart` (`master_data`, `master_data_change`, `product` at `edit`); `SetProductCategoryRequirements` (`master_data`, `master_data_change`, `master_data_group` at `edit`). The verb Bind (`edit`) is in the glossary and the verb catalog; the leaf is `agent_product_engineering`.
Source: ADR-0062.R22

R850. The workflow's invariants take the block `INV-640` to `INV-669`. `INV-650`, `INV-651`, `INV-652`, `INV-653`, `INV-654` and `INV-655` are of areas `production` and `safety`, first step the production core step, and stand under Invariants. Its edge cases (DS-17) are `EC-140`, `EC-141`, `EC-142`, `EC-143` and `EC-144`, under Edge cases.
Source: ADR-0062.R22

### Production order queries

R853. `ListComponentShortage` (module `production`, computed query, `production_order` at `read`) returns one row per component line of orders in `draft`, `pending_approval` or `approved` and not technically complete, rework and disassembly orders included.
Source: ADR-0064.R5

R854. Its quantities, in the inventory unit, are: required; open requirement = max(0, required − net issued − backflushed); reserved (open and picked reservations of the line's demand line); staged (picked to the supply bin); available to promise in the issue warehouse (`GetAvailableToPromise`); short = max(0, open requirement − reserved − available to promise), the order's own view, as `has_component_shortage` uses it.
Source: ADR-0064.R5

R855. Uncovered is the cross-order view the sweep acts on, computed before any filter of the call: per (item, issue warehouse), available to promise is allocated to the unreserved open requirements of every component line of the company's approved, not technically complete orders in the reservation priority (R860); lines of `draft` and `pending_approval` orders then take what is left, in the same priority. Uncovered = the unreserved open requirement the allocation does not cover. A filtered call returns the same values as the unfiltered one for the rows it returns.
Source: ADR-0064.R5

R856. Each row also gives the line's `requested_date`; the earliest date the projection covers the short quantity, from `GetProjectedAvailability`, or none; the pegged end demand and its due date (ADR-0064.R8). Filters: item, warehouse, order, requested date range, `is_short_only` (default true: short or uncovered above 0). Rows are ordered by the reservation priority (R860).
Source: ADR-0064.R5

R857. `EvaluateProductionOrderRelease` (module `production`, `Evaluate` query, `production_order` at `read`) returns one verdict for an order and business date. Its reasons form a closed list, each with its class:
   - `component_short` (material): a line of the order with short above 0 (R854);
   - `work_center_overloaded` (capacity): `ListWorkCenterLoad` above available hours in a bucket of the order's operations;
   - `production_version_invalid`, `revision_invalid` (master data): version and revisions not valid on the order's dates (ADR-0033.R5);
   - `subledger_not_active` (accounting gate): ADR-0034.R15;
   - `output_serial_missing` (master data): serial-tracked output with fewer assigned serials than G when the version requires them at release (ADR-0034.R16);
   - `external_supplier_missing`, `processor_route_missing` (master data): external operations (ADR-0037.R2, ADR-0037.R3).
   Source: ADR-0064.R6

R858. The verdict is `blocked` when any reason of class master data or accounting gate is present; else `ready_with_shortage` when material or capacity reasons are present; else `ready`.
Source: ADR-0064.R6

R859. The `has_component_shortage` policy input at `Submit` (ADR-0034.R5 note) is true exactly when this evaluation returns `component_short` for the submitted version. No release-with-shortage setting exists: a company ranks such releases through its policy table.
Source: ADR-0064.R6

R860. The reservation priority, `production.rank_reservation_demand` (a pure function of `production`), orders component lines by `requested_date`, then the due date of the make-to-order demand the order serves (ADR-0064.R8; lines without one last), then the order's document number, then line number. The sweep (ADR-0064.R15) and the shortage candidates (ADR-0064.R16) use it. Production keeps this order as a demand class of its own beside first come, first served (ADR-0023.R13).
Source: ADR-0064.R7, ADR-0064.R7.N1

R861. `GetProductionOrderUsageVariance` (module `production`, computed query, `report_production` at `read`) gives quantities only, at any time, for an order and an optional posting-date range (the in-period variance). For components: target at progress = required × progress / Q, progress being the cumulative yield + scrap of the component's operation, or the net main-output receipts over G for `backflush_at_receipt` and lines without an operation (the backflush rule of ADR-0034.R12); against net issued + backflushed.
Source: ADR-0064.R9

R862. For operations it compares actual activity quantities against the standards at the confirmed quantity, and actual scrap against the operation's scrap rate, by scrap reason (`scrap_reason_id`, ADR-0074.R14). Each line names the ADR-0035.R15 category it feeds: `input_quantity`, `resource_usage` or `scrap`.
Source: ADR-0064.R9

R863. `ListProductionOrderVarianceDriver` (module `production`, computed query, `report_production` at `read`; field class `cost` on amounts) lists the document lines behind each variance category of a settled order and period, by category and cost component: issue lines above requirement with their `scrap_reason_id` (ADR-0074.R14) (`input_quantity`); confirmations with scrap and reason, and receipts with scrap and their reason (ADR-0071.R4) (`scrap`); activity lines (`resource_usage`); price differences per component from the settlement lines (`input_price`); fixed quantities and setup over the received quantity (`lot_size`); and the rest (`remaining`).
Source: ADR-0064.R10, ADR-0064.R10.N1

R864. The contributions of a category sum to that category's row of `production_order_variance` (`INV-739`). Agent runs get the numeric projection of ADR-0064.R13.
Source: ADR-0064.R10

R865. Variance ranking, `production.rank_variances` (a pure function of `production`): an order ranks when its absolute variance reaches `production.variance.rank_threshold_percent` of its target cost or, when it is not 0, `production.variance.rank_threshold_amount`; the first `production.variance.top_n` by absolute amount rank, ties by document number.
Source: ADR-0064.R11

### Daily production order check

R866. `RunProductionOrderCheck` (module `production`, verb Run, effect class `other`) is an internal system job on `production_order`, run daily with an explicit business date and after each sweep (ADR-0007.R17). For approved orders that are not technically complete it raises and closes work items, one open item per order and kind, as R867 to R870 state.
Source: ADR-0064.R12

R867. `production_component_shortage` is open while a line of the order has short or uncovered above 0 (R854, R855) and its requested date lies within `production.agent.readiness_horizon_days`, in every reservation mode, including lines beyond the window in mode `scheduled`.
Source: ADR-0064.R12

R868. `production_completion_candidate` is raised when net main-output receipts reach `production.completion.propose_at_percent` of G (for a disassembly order, every co-product line reaches that share of its planned quantity) and every internal operation has a final confirmation or a cumulative yield + scrap at its expected quantity.
Source: ADR-0064.R12

R869. `production_order_stalled` is raised when the order is `in_progress` and has no posting for `production.order.stalled_days` working days of the production warehouse's calendar.
Source: ADR-0064.R12

R870. `production_standard_review` (subject the production version) is open while the same driver (component, operation or scrap reason) ranks on at least `production.feedback.min_orders` orders or in `production.feedback.min_periods` consecutive periods and `production.feedback.enabled` is true; it closes when the driver no longer qualifies.
Source: ADR-0064.R12

## Invariants

Statements are those of `invariants.csv`. This chunk holds the rows whose catalog source is a rule of this chunk, and the product engineering rows that R850 names.

| ID | Name | Check point | Statement | Protects |
| --- | --- | --- | --- | --- |
| `INV-650` | `released_structure_items_bound` | day | No released bill of materials revision has a component or a main output without its item (or configurable product), or with a proposal-item reference. | R834 |
| `INV-651` | `released_routing_durations_stated` | day | No released routing revision has an operation with `is_setup_duration_stated` or `is_run_duration_stated` false. | R844; ADR-0062.R10 |
| `INV-652` | `released_estimate_complete` | day | No released cost estimate has a gap row or lacks a production version. | R829 |
| `INV-653` | `proposal_references_creating` | day | Every proposal-item reference names a `CreateProduct` or `CreateItem` item of a change proposal of the same company, and no reference remains once that proposal's execution has been delivered to the binding consumer, except a line whose unit had no factor, which a note names. | R832, R835, R836 |
| `INV-654` | `release_approver_not_requester` | day | Every executed release proposal drafted by a `product_engineering` run was approved by a person other than the human the run acted for. | R823; ADR-0062.R13 |
| `INV-655` | `drafted_values_from_sources` | day | Every quantity, time and code on a draft revision written by a `product_engineering` run equals a value of a source span recorded in its run's steps, or of an extraction field its evidence links name. | R823; ADR-0062.R5, ADR-0062.R16 |
| `INV-735` | `component_reservations_within_requirement` | day | Per production order component line, open and picked reservations never exceed the open requirement. | R854; ADR-0064.R15 |
| `INV-736` | `shortage_policy_input_matches_check` | day | Every `has_component_shortage` policy input recorded at Submit of a production order equals whether `EvaluateProductionOrderRelease` returned `component_short` for that version on that business date. | R859 |
| `INV-739` | `variance_drivers_sum` | day | For every settled order, period and variance category, the contributions of `ListProductionOrderVarianceDriver` sum to the category's row of `production_order_variance`. | R864 |

## Edge cases

| ID | Name | Case | Outcome | Protects |
| --- | --- | --- | --- | --- |
| `EC-140` | `product_from_note_new_component` | A note asks for a new assembly with one new component; the item proposal and drafts are made, release is refused until the item is approved and bound, then another person approves the release proposal. | `must_reject:bill_of_materials_item_pending`, then `must_succeed` | R834-R836; ADR-0062.R13 |
| `EC-141` | `draft_estimate_missing_rate` | A draft estimate on a work center without an activity rate lists the gap, totals without it, and cannot be released until the rate exists. | `must_reject:cost_estimate_incomplete`, then `must_succeed` | R828, R829 |
| `EC-142` | `component_by_manufacturer_part` | A component named by a manufacturer part number with its manufacturer, written with other separators, resolves to exactly one item without an LLM. | `must_succeed` | R823, R841; ADR-0062.R7 |
| `EC-143` | `engineering_change_with_stock` | An engineering change replaces a component with stock and open purchase orders; the release proposal carries where-used, the orders, a disposition and the cost delta. | `must_succeed` | R840 |
| `EC-144` | `drawing_with_instructions` | A customer drawing says to use supplier X at price Y; it never starts a run, and the person's note names only the verified quantities. | `must_succeed` | R822; ADR-0062.R2, ADR-0057.R17 |
| `EC-200` | `shortage_cleared_while_transfer_pending` | A goods receipt covers the target's shortage while a `transfer_reservation` proposal waits; at execution the target's short quantity (unreserved requirement minus available to promise) is 0, so the transfer fails with `reservation_transfer_invalid` although nothing reserved the receipt, and the next `RunProductionOrderCheck` closes the shortage item. | `must_reject:reservation_transfer_invalid`, then `must_succeed` | R867; ADR-0064.R16, ADR-0064.R24 |
| `EC-212` | `completion_proposal_then_late_receipt` | An order at 97% received under a 95% setting gets a completion proposal; after a late receipt a person reopens it. | `must_succeed` | R868; ADR-0064.R18 |
| `EC-214` | `rework_and_disassembly_in_agent_queries` | Rework and disassembly orders appear correctly in the shortage list, completion candidates and usage variance. | `must_succeed` | R853, R861, R868 |

Named by rules of this chunk, with their rows in another chunk: `EC-302` (R828; catalog source ADR-0072.R7). `EC-108`
(area `planning`, catalog source ADR-0056.R17) tests the issue multiple of R816 and is stated by `planning`.

## Settings

None: the settings of R865 to R870 (`production.agent.readiness_horizon_days`, `production.completion.propose_at_percent`, `production.order.stalled_days`, `production.feedback.enabled`, `production.feedback.min_orders`, `production.feedback.min_periods`, `production.variance.rank_threshold_percent`, `production.variance.rank_threshold_amount`, `production.variance.top_n`) and `production.reservation.mode` (R867) have their rows in chunk 6 (ADR-0064.R23); `production.costing_sheet.required` (R828) in chunk 7.

## UI annotations

The sources state no floorplan, title, facet, field annotation or tile for the units of this chunk. Work item kinds of `production` raised by its rules:

| Kind | Subject table | Owner | Due | Resolution | Rule |
| --- | --- | --- | --- | --- | --- |
| `configured_estimate_failed` | `item` | `role:accountant` | `days:1` | `system`: closed when an estimate for the item is released | R809 |
| `product_release_ready` | `agent_run` | `run_on_behalf_of` | `days:2` | `person` | R836, R848 |
| `product_item_proposal_ended` | `agent_run` | `run_on_behalf_of` | `days:2` | `person` | R837, R848 |
| `production_component_shortage` | `production_order` | `planning_owner` | `days:1` | `system`: raised and closed by `RunProductionOrderCheck` | R867 |
| `production_completion_candidate` | `production_order` | `role:shop_floor_lead` | `days:2` | `system`: closed when the order is technically complete or stops qualifying | R868 |
| `production_order_stalled` | `production_order` | `role:shop_floor_lead` | `days:2` | `system`: closed when a posting arrives or the order completes | R869 |
| `production_standard_review` | `production_version` | `role:production_planner` | `days:5` | `system`: closed when the driver no longer qualifies | R870 |

## Conflicts

CONFLICT ADR-0046.R14: its notes are folded in: `ADR-0046.R14.N1` makes `configured_stock_available` unhashed (R813), `ADR-0046.R14.N2` names the policy condition `is_cost_unknown` (R808), `ADR-0046.R14.N3` defines the item estimate read and the rejection of a production receipt (R810, R811), `ADR-0046.R14.N4` and `ADR-0046.R14.N5` add the costing sheet and the `purpose` parameter (R806, R807).
CONFLICT ADR-0062.R12: `ADR-0062.R12.N1` (ADR-0072) adds the gap kinds `costing_rate_missing` and `costing_sheet_missing` and forbids model-written rates; stated in R828 and R831, matching the DDL of `cost_estimate_gap`.
CONFLICT ADR-0064.R10: `ADR-0064.R10.N1` (ADR-0071) adds receipts with scrap and their reason to the `scrap` driver, and ADR-0074.R14 replaces the text `reason_code` of issue lines by `scrap_reason_id`; stated in R863.
CONFLICT ADR-0064.R9: ADR-0074.R14 replaces text scrap reason codes by `scrap_reason_id`, so scrap is compared by scrap reason (R862).
CONFLICT ADR-0062.D0: ADR-0078.R2 makes `product_engineering` a Phase 2 agent type with mode `off` (R822).

## Proposed (not law)

None

## Trace

| Source | Where |
| --- | --- |
| ADR-0046.R13 | R801-R804 |
| ADR-0046.R14 | R805-R814 |
| ADR-0046.R14.N1 | R813 |
| ADR-0046.R14.N2 | R808 |
| ADR-0046.R14.N3 | R809-R811 |
| ADR-0046.R14.N4 | R806, R807 |
| ADR-0046.R14.N5 | R806 |
| ADR-0047.R1 | ref: ADR-0047.R1 |
| ADR-0047.R1.N1 | ref: ADR-0047.R1.N1 |
| ADR-0047.R1.N2 | ref: ADR-0047.R1.N2 |
| ADR-0047.R1.N3 | ref: ADR-0047.R1.N3 |
| ADR-0047.R1.N4 | ref: ADR-0047.R1.N4 |
| ADR-0049.R10 | ref: ADR-0049.R10 |
| ADR-0049.R22 | ref: ADR-0049.R22 |
| ADR-0050.R2 | ref: ADR-0050.R2 |
| ADR-0051.R6.N1 | ref: ADR-0051.R6.N1 |
| ADR-0055.R5.N1 | ref: ADR-0055.R5.N1 |
| ADR-0056.R9 | ref: ADR-0056.R9 |
| ADR-0056.R17 | R815-R818 |
| ADR-0060.R19 | R819-R821 |
| ADR-0062.D0 | R822, R823 |
| ADR-0062.R3 | ref: ADR-0062.R3 |
| ADR-0062.R11 | R824-R826 |
| ADR-0062.R12 | R827-R831 |
| ADR-0062.R12.N1 | R828, R831 |
| ADR-0062.R14 | R832-R838 |
| ADR-0062.R15 | R839, R840 |
| ADR-0062.R19 | R841-R845 |
| ADR-0062.R22 | R846-R850 |
| ADR-0062.W | not applicable: worked example of the workflow; its steps restate R822 to R838 and the codes it shows are not catalog rows |
| ADR-0064.R1 | ref: ADR-0064.R1 |
| ADR-0064.R1.N1 | ref: ADR-0064.R1.N1 |
| ADR-0064.R1.N2 | ref: ADR-0064.R1.N2 |
| ADR-0064.R5 | R853-R856 |
| ADR-0064.R6 | R857-R859 |
| ADR-0064.R7 | R860 |
| ADR-0064.R7.N1 | R860 |
| ADR-0064.R8 | ref: ADR-0064.R8 |
| ADR-0064.R9 | R861, R862 |
| ADR-0064.R10 | R863, R864 |
| ADR-0064.R10.N1 | R863 |
| ADR-0064.R11 | R865 |
| ADR-0064.R12 | R866-R870 |
| ADR-0064.R16 | ref: ADR-0064.R16 |
