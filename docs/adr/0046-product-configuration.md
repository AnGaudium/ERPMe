# ADR-0046: Product configuration

Status: accepted (2026-11-15) under ADR-0005, reviewed by Claude Fable 5.2 (builder Claude Opus 5.5). Design item: DS-56. Related decisions: D5, D6. Principles 1, 3, 6, 7. ADR-0004, ADR-0006, ADR-0008, ADR-0009, ADR-0016, ADR-0018, ADR-0020, ADR-0022, ADR-0024, ADR-0027, ADR-0028, ADR-0029, ADR-0032, ADR-0033, ADR-0034, ADR-0035, ADR-0036, ADR-0038, ADR-0042, ADR-0043, ADR-0045.

## Decision

The author put product configuration into Phase 1 for assembly manufacturers (2026-11-15). A configurable product is sold by choosing values for its characteristics. The choices are checked against rules, priced, and turned into a configured item whose bill of materials and routing are selected and sized from the same choices. The configuration then travels with the unit to production, delivery, its serial number and service.

**Built on ADR-0045.** Characteristics are the attributes of ADR-0045 rule 15, in the same two modes:
- **Item-defining characteristics** are variant-mode attributes. Each distinct combination of their values is one configured item, with its own stock and its own periodic average cost.
- **Line options** are line-option attributes. They change the price and the documents, never the item, the bill of materials or the cost.

Numbers join lists: a characteristic may take a number in a range with a step, such as a width or a length.

**Four parts:**
- **The model.** A configuration model per product holds its rules, tables and defaults, in released revisions like bills of materials.
- **The configuration.** An immutable, content-addressed record of the chosen values, evaluated by one pure function that people, agents and every document call.
- **Production.** Bill of materials components and routing operations of the product carry selection conditions and linear sizing over item-defining characteristics. The one explosion function of ADR-0033 evaluates them for MRP, orders and cost estimates alike.
- **Price.** The price is a product-level list entry plus extras per chosen value and rates per unit of a numeric characteristic, through the one lookup of ADR-0045 rule 4.

**Valuation follows the item.** Because a cost-relevant choice always makes another item, a configured unit's cost never averages with a different configuration's. Configured items are planned make to order, so their output is reserved to the sales line that caused it. Before an item exists, its cost comes from an estimate computed from the values alone.

**Agent-first.** The rule language is a small declarative grammar with no code and no arithmetic beyond linear sizing. Evaluation is order-independent by construction. `EvaluateConfiguration` returns, for every characteristic, the remaining allowed values and which of them lead directly to a violation, so an agent can lead a customer through a configuration with the same answers a screen shows.

### Rules

**Ownership**

1. Modules (ADR-0022 rule 2):
   - **`master_data`** owns the characteristics (columns on `variant_attribute`), configuration models and their revisions, rules, tables and defaults, `product_configuration` and its values, and the price tables. It publishes `master_data.contract.evaluate_configuration` and `master_data.contract.evaluate_condition`.
   - **`production`** owns the selection conditions and sizing on bill of materials components and routing operations, product-level production versions, and `production.contract.estimate_configuration`. It calls `evaluate_condition`.
   - **Commercial modules** (`sales`, `purchasing`) and `production` carry a configuration on their lines.
   - **Effect classes.** Model maintenance is `master_data_change`, change-tracked (ADR-0038 rule 3) and `is_proposal_bound` (ADR-0029 rule 5). Finding or creating a configuration record is part of the line's command.

**Configurable products and characteristics**

2. `product.is_configurable`:
   - **What it requires.** A configurable product is a `stock` product with `is_item_created_on_order` (ADR-0045 rule 16; the database holds both), at least one item-defining characteristic, a released configuration model revision valid on the document date (`configuration_model_missing`), and a product-level production version (rule 12).
   - **Its items are configured items**, one per distinct combination of item-defining values, created only by rule 11. A manual `CreateItem` for a configurable product is rejected with `item_configurable_product`. No item exists for the product itself.
   - **Required characteristics.** Every item-defining characteristic is required, since the item needs its value. A line option is required when `product_variant_attribute.is_required` is set or a `require` rule holds.
   - **Phase 1 limit.** Configurable products are made, not bought (flagged). Purchased configurable goods, and configurations passed down to configurable subassemblies, come later (open question).
3. Characteristics. `variant_attribute` gains:
   - **`value_type`:** `list` (values are `variant_attribute_value` rows, as before) or `number`.
   - **For numbers:** `uom_id`, `minimum_value`, `maximum_value`, `step_value` and `decimal_places`, all set for a number and all empty for a list (the database holds this). A value must lie in the range and equal `minimum_value` plus a whole number of steps (`configuration_value_out_of_range`). Values are exact decimals, never floats.
   - **Numbers that define an item.** When rule 11 creates an item, each item-defining number becomes a `variant_attribute_value` row with `numeric_value` and a canonical code (the decimal without trailing zeros, such as `37.5`), unique per attribute and number. The item's `variant_key` (ADR-0018 rule 7) therefore works unchanged. Configurations store numbers as numbers (rule 9), so drafts and quotations create no value rows.
   - **Stability.** Once a characteristic is named by a model revision, a configuration, a structure or an item, its mode, value type, unit, range, step and code, and the codes of its values, never change (`characteristic_in_use`). Rules and tables refer to codes, so codes must stay stable.
   - **The product's view.** `product_variant_attribute` (ADR-0045 rule 15) lists the product's characteristics, with `position`, `is_required`, and the allowed list values of `product_attribute_value`.

**The configuration model**

4. `configuration_model` (company, product, `code`, `name`, `is_active`; one active model per product) and `configuration_model_revision`:
   - **Revisions** follow ADR-0033 rules 3–4: `revision`, `state` (`draft`, `released`), `start_date`, `content_hash`, immutability after release (a database trigger rejects changes to a released revision and to its rules, tables, columns, rows and defaults: `revision_released`), validity by the highest released revision started on the date, no retroactive or out-of-order release, and withdrawal of a mistaken release.
   - **Content:**
     - `configuration_rule` rows (rule 6);
     - `configuration_table` rows with their `configuration_table_column` and `configuration_table_row` rows (rule 7);
     - `configuration_default` rows (characteristic, value or number, optional condition).

     Each row carries the product, and its characteristics are keyed to the product's `product_variant_attribute` rows.
   - **Release checks** (`configuration_rule_invalid`, with the rule and the reason):
     - conditions and effects follow the grammar of rules 5–7;
     - list values belong to their attribute and are allowed for the product;
     - numbers are in the characteristic's range and step;
     - the product's bills of materials and routings of every product-level version valid from the revision's `start_date` name only item-defining characteristics in their conditions and sizing (rule 12).
   - **Locking.** Releases lock the company's `production_structure` row (ADR-0033 rule 8), so a model and a bill of materials cannot be released inconsistently at the same time.
5. Conditions. One grammar, stored as canonical JSON (ADR-0008 rule 12):
   - **A term:** `{"c": <characteristic code>, "op": <op>, "v": <value>}`. Operators: `eq`, `ne`, `in`, `not_in` (list values or numbers); `lt`, `le`, `gt`, `ge`, `between` (numbers); `set`, `unset` (no value).
   - **Combinations:** `{"all": [...]}`, `{"any": [...]}` and `{"not": ...}`, nested at most three deep. An empty condition is true.
   - **Unknown values.** A term on a characteristic with no value yet is unknown, under three-valued logic (`all` is false if any part is false, else unknown if any part is unknown; `not` keeps unknown). A rule acts only when its condition is true.
   - **Monotone by construction.** Values are only added during evaluation, and every operator except `set` and `unset` keeps its truth once known. So a condition that has become true stays true. `set` and `unset` may appear only in the conditions of `require` and `forbid` rules, which are checked once on the final state (rule 8).
   - **No arithmetic** in conditions, no references to other records, no functions. Evaluation is pure, total and deterministic.
6. Rules. A `configuration_rule` has `position` (for display only), a condition (rule 5), a `kind`, a target characteristic, and a message code:
   - **`restrict`:** while the condition is true, the target's allowed values become their intersection with the given list or numeric range.
   - **`set`:** while the condition is true, the target takes the given value.
   - **`require`:** if the condition is true on the final state, the target must have a value.
   - **`forbid`:** the condition must not be true on the final state. When it is, it is a violation with the rule's message code. It names no target.
7. Tables. A `configuration_table` has ordered `configuration_table_column` rows (characteristics) and `configuration_table_row` rows giving allowed combinations. A cell holds a list value's code, a number, `*` (any), or for a number column an inclusive range `{"min": n, "max": n}`.
   - **The constraint.** The values set in the table's columns must match at least one row. A row matches when every cell is `*`, equals the value (numbers compared exactly), contains it (ranges), or names a column with no value yet.
   - **Narrowing.** Each list column without a value narrows to the cells of the matching rows, unless one of them is `*`. Number columns take part only once they have a value.
   - **Use.** Tables are for compatibility (which components fit together) and for deriving one characteristic from others, such as a size class from width bands: the class narrows to one value and is then taken (rule 8).
8. Evaluation. `master_data.contract.evaluate_configuration(model_revision, values)` is pure and order-independent:
   - **Domains.** Each characteristic starts from its list values limited by `product_attribute_value`, or its numeric range with step.
   - **Rounds.** Evaluation runs in rounds. Each round evaluates every `restrict` and `set` rule and every table against the state at the start of the round, then applies their effects together:
     - restrictions intersect;
     - a characteristic without a value takes one when every true `set` rule for it proposes the same allowed value, or, for a required characteristic (rule 2), when its allowed list values, or the step values of its numeric range, are exactly one (an optional line option is never chosen for the user);
     - tables narrow list columns.

     The effects combine commutatively and conditions only gain truth (rule 5), so rule positions never change the result and nothing needs undoing.
   - **Bound.** Rounds stop when a round gives no value. Domains are recomputed each round from the initial domains, the true restrictions and the tables, so a round changes the state only by giving values: there are at most the number of characteristics + 1 rounds. Exceeding the bound is an internal error.
   - **Defaults.** After the fixed point, `configuration_default` rows apply one at a time in position order, each to a characteristic still without a value where its condition is true and its value is allowed, and each followed by rounds to a new fixed point.
   - **Final checks** on the final state: `require` and `forbid` rules, required characteristics (rule 2), and the violations.
   - **Violations**, each with a stable code, the rules or table involved and the characteristics:
     - `configuration_value_out_of_range`: a value outside the final allowed values, whatever its source: a user value, or a value taken in an earlier round or from a default that later restrictions excluded (with the message codes of the restricting rules);
     - `configuration_set_conflict`: a `set` rule whose value is outside the target's allowed values, differs from the user's value, or differs from another true `set` rule;
     - `configuration_domain_empty`: a list domain narrowed to nothing, or a numeric range that holds no step value;
     - the rule's own message code: a true `forbid`;
     - `configuration_table_no_match`: a table with no row matching the values set.
   - **Result.**
     - For each characteristic: its value, the value's source (`user`, `rule`, `default`), its allowed values or range as they stood before defaults, and whether it is required.
     - For each allowed list value of a characteristic without a value, `leads_to_violation` (a one-step lookahead: evaluating with that value added gives a violation).
     - The violations, the missing required characteristics, `is_complete` (nothing missing and no violation), and a result hash.
   - **Necessary, not sufficient.** Allowed values are necessary: a combination of allowed values can still meet a `forbid` or a table several steps later. The lookahead flags the direct cases. A configuration is accepted only when it is complete.
   - **The query.** `EvaluateConfiguration` (product, date or model revision, values) exposes it to people and agents. It is computed, an exception to ADR-0004 rule 21 like `GetPrice`. A screen and an agent see the same remaining choices.

   The quotation agent's configuring loop: [ADR-0051](0051-agent-workflows.md) rule 15.

   Note: `leads_to_violation` is true only when evaluating with that value adds a violation (code, rule or table, and characteristics) that the result without it does not have; violations already present never mark a value. The lookahead covers every characteristic without a user or rule value, including one that took a default, whose default the tried value replaces.

**Configurations**

9. `product_configuration`:
   - **The record.** Company, product, `content_hash` and `created_at`. The hash is the SHA-256 of the canonical JSON of the product ID and the sorted pairs of attribute ID and value (a list value's ID, or a number as a decimal without trailing zeros, so `37.50` and `37.5` hash alike). The record is immutable and unique per company, product and hash, so the same choices are stored once and reused across quotations, orders and production.
   - **Values.** `product_configuration_value` rows give the characteristic, its `value_type`, and either `variant_attribute_value_id` (list values) or `numeric_value` (numbers, in both modes). A composite key on the value type holds this in the database.
   - **Immutability.** A trigger rejects updates and deletes, and value rows added to a configuration created by an earlier transaction (`configuration_immutable`). The record stores its top-level transaction (`created_xact_id`), so a configuration saved inside a savepoint of a command batch (ADR-0029 rule 3) still takes its values.
   - **What the record does not hold.** It has no model revision and no sources: they belong to the evaluation, not to the choices. A line keeps the revision it was evaluated under and the sources in its own content. Every find-or-create, and every line leaving draft, evaluates the values under the revision valid on the document date.
   - **Completeness.** Only complete, valid configurations are stored. A draft line holds its chosen values as canonical JSON in its content. Each save evaluates them and returns the result. When they are complete, the line references the configuration found or created.
   - **No personal data.** Free text for `is_custom` values (ADR-0045 rule 15) stays on the line, in `document_line_custom_text` (line, attribute, text), labeled `personal` and `is_untrusted`, so the shared record never needs erasure.
   - **Lines of any product.** A line's choices are a configuration for any product with line options, and for every configurable product. ADR-0045 rule 15's `document_line_option` rows become the configuration's values (a note there).

   Note: a product with line options and no configuration model (not configurable) is evaluated by an implicit model: its line options' domains limited by `product_attribute_value`, the `is_required` options required, and no rules, tables or defaults. Missing options and values not allowed are reported as `line_option_required` and `line_option_value_not_allowed` ([ADR-0045](0045-master-data-and-price-lists.md) rule 15), and a complete set of choices is stored as a `product_configuration` like any other. The line keeps no model revision, and a copy re-checks only allowed values and required options.
10. Configurations on documents:
    - **Leaving draft.** A line of a configurable product may leave draft only with a complete configuration (`configuration_incomplete`, listing the missing characteristics and the violations).
    - **Warehouse.** The line's warehouse must be the production warehouse of one of the product's product-level versions (`configuration_warehouse_not_produced`), so make-to-order supply and reservation meet it (ADR-0034 rule 14). Transfers of configured units are later.
    - **Copying.** Copying a line to a new document (quotation to order, order to delivery) evaluates the configuration under the model revision valid on the new document's date. If it is no longer valid, the copy is rejected with `configuration_invalid` and the violations, and the user reconfigures. An existing document keeps its configuration.
    - **Downstream copies.** Deliveries, returns, credit notes and production orders copy the configuration from their source line without re-evaluation.
    - **Production orders without a sales line** carry the configuration entered on them; their line options are information.
    - **Change orders** (ADR-0028 rule 4). A change that alters a line's configuration is rejected with `configuration_in_production` while any production order linked to that line is open (not closed or cancelled). Planned orders need nothing: the next planning run replans them for the new item.

**Configured items**

11. Creation. When a sales order or a production order leaves draft (ADR-0045 rule 16), each configurable line gets its configured item:
    - **Which item.** The item whose `variant_key` equals the configuration's item-defining values. If it does not exist, the number value rows are found or created (rule 3) and the item is created. Two configurations that differ only in line options share the item.
    - **Who, when and code** follow ADR-0045 rule 16: the actor's `CreateItem` permission; `proposal_required` for agent-origin lines; the product code with `product.last_item_number`; quotations and drafts create nothing.
    - **Name.** The product's name followed by the item-defining values in position order, such as `Unit 1200 × 800 / steel / wall`. It is translated like the product's name.
    - **Created with it, in the same transaction:**
      - an `item_warehouse_planning` row for each production warehouse of the product's product-level versions, with source `production`, method `net_requirements`, lot size `exact` and strategy `make_to_order` (ADR-0036 rule 9);
      - an event `ConfiguredItemCreated`.
    - **The cost estimate.** A system consumer of `ConfiguredItemCreated` computes and releases the item's cost estimate (rule 14).

    Sales and production orders carry the registry flag `is_item_creating` ([ADR-0047](0047-commercial-documents-and-pricing.md) rule 1).

    Note: a sales line of a configured item in a warehouse without its `make_to_order` row is rejected, and open demand on a node without a planning row raises `planning_parameter_missing` (reason `planning_row_missing`) ([ADR-0036](0036-multi-level-mrp.md) rule 9's note) (holistic review 2026-11-15, item P5).

    Note (simulation review, 2026-11-15): who creates. The configured item, its number value rows and its `item_warehouse_planning` rows are created by `system` on behalf of the human whose command takes the order out of draft, as a consequence of that command; this ADR is one of those that [ADR-0027](0027-cross-cutting-ownership.md) rule 12 requires for a system job acting for a human. That person needs the command's own permission (`SubmitSalesOrder`, or the command that takes a production order out of draft), not `CreateItem`, which replaces "the actor's `CreateItem` permission" under **Who, when and code**. `proposal_required` for an agent, or a command carrying an origin agent run, is unchanged ([ADR-0045](0045-master-data-and-price-lists.md) rule 16 note).

    Note (simulation review, 2026-11-15): writing the configured item onto each line changes the order's content, so the same transaction writes a new document version (actor `system`, `on_behalf_of` the submitter) whose content equals the typed rows (INV-10; [ADR-0009](0009-document-lifecycle.md) rule 9). It is written before the `Submit`'s policy evaluation, so the policy decision and any approval bind to the version that names the items; it is not an `Update` and voids nothing. The submitter is thereby a writer of the order and cannot approve it ([ADR-0055](0055-approval-pools-and-stages.md) rule 7, condition 5).
12. Production structures of a configurable product:
    - **Product-level versions.** `production_version` gains `product_id`, exclusive with `item_id`: a version of a configurable product applies to every configured item of it. Version selection for a configured item looks for an item-level version first, then a product-level one (ADR-0033 rule 13).
    - **The super bill of materials.** `bill_of_materials` gains `product_id`, exclusive with `item_id`, for the product-level bill of materials, whose main output at explosion is the configured item.
    - **Components** gain `selection_condition` (rule 5, without `set` or `unset`; empty means always) and a sizing:
      - `fixed`: the stored quantity, as today;
      - `linear`: quantity = `quantity` + `quantity_per_value` × the value of a numeric item-defining characteristic, with `quantity_per_value` in the component's unit per unit of the characteristic.

      A result of zero drops the line. A result that could be negative is rejected at release (`configured_quantity_negative`): sizing is linear, so the check at the characteristic's minimum and maximum covers every value. Alternatives are separate component rows with exclusive conditions.
    - **Routing operations** gain `selection_condition` and the same linear sizing of their durations. A routing with conditions serves one configurable product (`routing_conditions_shared`), an exception to ADR-0033 rule 9's sharing.
    - **Only item-defining characteristics.** Conditions and sizing may name only item-defining characteristics of the product (`configuration_characteristic_not_item_defining`), checked at bill of materials and routing release and at model release (rule 4). This keeps one item, one structure, one cost: a line option can never change what is built.
    - **Revisions after an item exists.** A configured item's structure is the product-level revision valid on the explosion date, like any item's (ADR-0033 rules 4–5). A new revision changes what later orders of an existing configured item use, as it does for any item. Because estimates are made at once for new configured items, they pin revisions early, and the withdrawal rule (`revision_in_use`) rarely applies.
    - **Phase 1 limit.** Values are not passed to subassemblies. A component that varies is chosen among fixed items by conditions; a phantom component is exploded with its own structure.

    Note: the product is a node of the cycle check and of low-level codes, and its configured items inherit its low-level code ([ADR-0033](0033-production-master-data.md) rule 8's note) (holistic review 2026-11-15, item P6).

    Note (simulation review, 2026-11-15): the base `quantity` of a linear component may be negative, as in −0.4 + 0.001 × width for a rail shorter than the opening by a fixed length. The database requires a positive quantity for fixed sizing only (DS-43's `ck_bill_of_materials_component_quantity`, relaxed). For linear sizing, the result at the characteristic's `minimum_value` and `maximum_value` is the release check above (`configured_quantity_negative`), and a zero result still drops the line. Lab check `t16_planning_production_ddl.py` N07b.
13. Explosion. `production.contract`'s explosion (ADR-0033 rules 5–6; [ADR-0036](0036-multi-level-mrp.md) rule 3) takes the item-defining values:
    - **Selection and sizing.** It keeps the components and operations whose condition is true, and sizes them, before the requirement formula of ADR-0033 rule 6. Quantities stay exact rationals and are rounded once per order line.
    - **One function.** MRP, `CreateProductionOrder`, cost estimates, `estimate_configuration` and the explosion query all use it, so a planned order, the real order and the estimate agree.
    - **The order's snapshot.** A production order copies the selected, sized lines and keeps the configuration's ID, so it never re-reads the model.
    - **Checks.** A configured explosion with no component returns the check result `configured_explosion_empty`. Unknown values cannot occur, because explosions run only for complete configurations.

**Cost and valuation**

14. Valuation:
    - **Per configured item.** Configured items are valued by periodic average per item (ADR-0020 rule 11), so each configuration keeps its own cost.
    - **Cost before the item exists.** `production.contract.estimate_configuration(product, item-defining values, date)` is a pure function: the configured explosion of the product-level version valid on the date, priced as ADR-0035 rule 14 does. The query `GetConfigurationEstimate` exposes it. The cost checks of ADR-0043 rule 3 and ADR-0045 rule 5 ("below cost", margin) use it whenever the line's item or the item's preliminary price is missing, so a first-time configuration is checked at a quotation's or order's `Submit` like any other.
    - **Unknown cost.** When the estimate cannot be computed (a component without a price), the check returns `preliminary_price_missing` as a check result, and the policy treats the unknown cost as needing human confirmation (flagged).
    - **The item's estimate.** The consumer of `ConfiguredItemCreated` releases the item's cost estimate (ADR-0035 rule 14, which gains `item_id` for this case) as derived data from released structures, with no approval (flagged). It writes no `preliminary_price` row: ADR-0035 rule 4 reads the released estimate as the fallback for an item without history, so `UpdatePreliminaryPrice` (`human_only`) is not involved. If the consumer fails, it creates a work item `configured_estimate_failed` for the accountant. The item stays usable, and production receipts take their provisional value as ADR-0035 rule 4 says.
    - **Make to order.** Strategy `make_to_order` reserves the output to the sales line (ADR-0034 rule 14), so a configured unit is never delivered to another customer by accident. A returned unit returns to its own item's stock.
    - **Free stock.** Free stock of a configured item (a return, a cancelled order) is not netted by make-to-order planning (ADR-0036 rule 9). A planning run that plans an order for a line while free stock of the same item exists returns the check result `configured_stock_available`, naming the stock, and a person may reserve it.
    - **Line options carry no cost** (rule 12). Their price extras are pure price. ADR-0045 rule 15's open point on the cost and stock of options is closed by this split.

    Note: `configured_stock_available` is side information of a planning run, so it is unhashed like `planning_parameter_missing` ([ADR-0040](0040-ui-architecture.md) rule 10; DS-04 `checks`) (holistic review 2026-11-15, item P26).

    Note: an unknown cost sets the policy condition `is_cost_unknown`, and the seeded rule requires approval ([ADR-0043](0043-policy-and-approval.md) rules 3, 15; [ADR-0047](0047-commercial-documents-and-pricing.md) rule 22).

    Note: the item's estimate is a `cost_estimate` ([ADR-0035](0035-production-costing.md) rule 14) with `item_id`. Where an estimate is read ([ADR-0020](0020-inventory-and-costing-model.md) rule 11, ADR-0035 rule 4), it is the latest released estimate for the item whose costing date is on or before the posting date, preferring one whose version's production warehouse is in the line's valuation area; its price basis is ADR-0035 rule 14's default, `actual_average` (flagged). When the consumer fails, the item stays usable on quotations and orders, whose cost checks use `estimate_configuration`; a production receipt of the item, which has no history and no released estimate, is rejected with `preliminary_price_missing` until an estimate is released or a person sets a preliminary price, as ADR-0035 rule 4 says. "Take their provisional value" above means exactly this.

**Price**

15. Configured prices, through ADR-0045 rule 4. `find_price` takes the chosen values (so an incomplete draft can be priced) instead of a list of option values:
    - **Lookup order.** The item's entry in the entered unit, then the item's entry in the inventory unit, then the product's entry in the entered unit, then the product's entry in the inventory unit, each by ADR-0045 rule 4.
    - **Product entries.** `price_list_entry` gains `product_id`, exclusive with `item_id`, allowed only for configurable products: the base price of every configured item of the product.
    - **Item entry replaces the item-defining part.** An entry for the configured item, which a configuration sold often can get, is that item's whole price before line options. Item-defining extras and rates are then not added. Line-option extras and rates are always added.
    - **Value extras.** `price_list_option_extra` applies to the values of both modes of a configurable product. For other products it stays limited to line options; the database's mode check becomes the command check `option_extra_not_allowed`.
    - **Number rates.** `price_list_characteristic_rate` (list, product, numeric characteristic, dates, `rate_per_value`) adds `rate_per_value` × the chosen number, per inventory unit. The database keys it to number characteristics. Rates of one list, product and characteristic never overlap in dates.
    - **The sum.** Base + extras + rates, multiplied by the factor and rounded once, exactly as ADR-0045 rule 17. The result lists every row used.

    Note ([ADR-0056](0056-multiple-units-of-measure.md), proposed 2026-11-15): for a configured item, its own product units (item-level `product_uom` rows, added by a person) come first in the conversion factor, then the product's (rules 4, 6).

**Serials and service**

16. The configuration after delivery:
    - **The configured unit.** A serial of a configured item knows its item-defining values through its item. Its line options come from the configuration of the delivery line that shipped it. Its as-built components come from `GetTraceability` (ADR-0034 rule 16).
    - **The query.** `GetSerialConfiguration` (serial) returns the three together, for service and for an agent answering a customer.
    - **As built.** Product-level versions default `is_as_built_required` to true for serial-tracked configurable products, because service needs the actual components of each unit (flagged).

**Commands, events and checks**

17. Commands, queries and events:
    - **Commands** (`master_data_change`): `CreateConfigurationModel`, `CreateConfigurationModelRevision` (copied from a revision or empty), `UpdateConfigurationModelRevision`, `ReleaseConfigurationModelRevision`, `SetPriceListCharacteristicRates`.
    - **Queries:** `EvaluateConfiguration`, `GetConfigurationEstimate`, `GetProductConfiguration`, `ListConfigurationModel`, `ListConfiguredItem` (product, values), `GetSerialConfiguration`.
    - **Events:** `ConfigurationModelRevisionReleased`, `ConfiguredItemCreated`.
    - **Agents.** An agent may evaluate, estimate, draft lines with configurations, and propose model revisions. Releases are change proposals, and new configured items are created only by a human leaving draft (rule 11).
18. Catalog rows:
    - **Errors:** `configuration_model_missing`, `configuration_value_out_of_range`, `configuration_rule_invalid`, `configuration_incomplete`, `configuration_invalid`, `configuration_in_production`, `configuration_warehouse_not_produced`, `configuration_characteristic_not_item_defining`, `configured_quantity_negative`, `routing_conditions_shared`, `characteristic_in_use`, `item_configurable_product`, `option_extra_not_allowed`; database errors `revision_released` and `configuration_immutable`.
    - **Violation codes**, returned by `EvaluateConfiguration` and in the details of `configuration_incomplete` and `configuration_invalid`: `configuration_value_out_of_range`, `configuration_set_conflict`, `configuration_domain_empty`, `configuration_table_no_match`, and each `forbid` rule's message code.
    - **Check results:** `configured_explosion_empty`, `configured_stock_available`.
    - **Work item kind:** `configured_estimate_failed` ([work-item-kinds.csv](../catalogs/work-item-kinds.csv)).
    - **Invariants**, reserved in the production range and added when the production core step is numbered (ADR-0033 rule 16):
      - **INV-113:** every non-draft line of a configurable product names a complete configuration and an item whose variant values equal the configuration's item-defining values;
      - **INV-114:** every `product_configuration`'s `content_hash` equals the hash of its stored values;
      - **INV-115:** every component and operation condition and sizing of a product-level structure names only item-defining characteristics of its product.
    - **Edge cases** (DS-17 codes them when the manufacturing company's dataset is built):
      - a quotation copied to an order after a model revision forbids its configuration;
      - two orders with the same item-defining values and different line options share one item;
      - a number off the step;
      - a table narrowing that leaves one value;
      - a change order on a configured line with an open production order;
      - free stock of a configured item when a new line asks for it.

    Note: INV-113 reads: every non-draft line of a configurable product on a document of an `is_item_creating` type, and every stock document line of one, names a complete configuration and an item whose variant values equal the configuration's item-defining values; a non-draft quotation line names a complete configuration, and an item only when one with those values exists ([ADR-0018](0018-product-and-item-model.md) rule 2).
19. Lab check `t06_configuration.py` ([validation lab](../reviews/2026-11-14-design-validation/README.md)). The DDL loads with DS-20 and DS-06. On a neutral configurable product with numeric and list characteristics, rules, a table with ranges, and defaults, it checks:
    - evaluation: narrowing, derived values, defaults, each kind of violation with its message codes, completeness, step and range, the lookahead;
    - order independence and idempotence on 300 random models, with the bound never reached;
    - re-evaluation under a later revision that forbids a configuration;
    - content-addressed reuse of configurations, the recomputed hash, and numbers stored as numbers;
    - configured items shared across line options and distinct across item-defining values, with number value rows created only then;
    - the super bill of materials explosion with conditions and linear sizing, and the release checks;
    - configured prices, including an item entry replacing the item-defining part;
    - that estimates of two configurations differ;
    - the immutability triggers, including a row moved out of a released revision and a configuration saved inside a savepoint, and `company_id` on every DS-56 table.

    Note: the lab also checks that the lookahead marks only values that add a violation absent from the result without them (rule 8).

## Context

Assembly manufacturers sell products whose size and equipment are chosen per order: dimensions, materials, mounting, lengths, accessories. Fixed variants (ADR-0018) multiply items before anyone orders them. Line options (ADR-0045) price choices but cannot change what is built.

The reference systems solve this differently:
- **SAP variant configuration:** characteristics and classes; dependencies (preconditions, selection conditions, procedures, constraints) in a dependency language; variant tables; a super bill of materials and routing; valuation in sales order stock, or material variants for frequent configurations.
- **D365 product configuration:** models with attributes, expression constraints solved by a constraint solver, table constraints, calculations, conditional bill of materials lines and route operations, and a new variant created for each configuration.
- **Odoo configurator:** attributes that create variants always, dynamically or never; exclusions; custom values; price extras. No conditional sizing of bills of materials beyond lines that apply to some variants.

ERPMe takes SAP's super structure with selection conditions and D365's configured variant per configuration, and keeps the rule language as small as Odoo's spirit. That way an agent can read, explain and propose every rule. The first review of this ADR found that sequential rule application made results depend on rule order, that first-time configurations had no cost at the checks, and that numbers created value rows from quotations. Rounds, the configuration estimate and numbers stored as numbers fix them.

## Options considered

| Option | For | Against |
| --- | --- | --- |
| A configured item per distinct item-defining combination (chosen) | Cost and stock per configuration with the existing periodic average; no new stock key | Many items; a counter and names to manage |
| One item, configurations as information (Odoo "never") | Few items | Different configurations average into one cost; customized stock mixes |
| Sales order stock valued per order line (SAP) | No item per configuration | A new stock segment in the stock key, valuation area and every query |
| Small declarative grammar evaluated in rounds (chosen) | Deterministic and order-independent; explainable; agent-readable | Less expressive than a solver; allowed values are necessary, not sufficient |
| Rules applied one by one in position order | Simple | Results depend on rule order |
| General expression language or constraint solver (SAP, D365) | Very expressive; complete propagation | Hard to review, to explain and to bound; a new runtime |
| Only item-defining characteristics drive structures (chosen) | One item, one structure, one cost | A choice that changes what is built must be item-defining, even if rare |
| Linear sizing only (chosen) | Covers lengths, per-unit counts and scaled times; exact; negative results checkable at release | Non-linear sizing needs a table-derived characteristic |
| Content-addressed configuration records (chosen) | Reuse, cheap comparison, no duplicates | Incomplete choices live in draft content, not as records |

## Constraints that come with the decision

- **ADR notes:**
  - ADR-0045 rules 15–17: lines carry a `product_configuration`; option extras of configurable products; the mode check of option extras becomes a command check; `find_price` takes values;
  - ADR-0018 rule 6: numeric characteristics;
  - ADR-0033 rules 3, 6, 9, 13, 17: product-level bills of materials and versions, selection conditions and sizing; configured products are no longer later;
  - ADR-0034 rules 1, 2: the order keeps the configuration;
  - ADR-0035 rule 14: estimates per configured item;
  - ADR-0036 rule 9: configured items plan make to order.
- **DDL:** `variant_attribute`, `variant_attribute_value`, `product`, `price_list_entry` and `price_list_option_extra` change in [DS-20-master-data.sql](../design/DS-20-master-data.sql); new tables and triggers in [DS-56-product-configuration.sql](../design/DS-56-product-configuration.sql).
- **DS-04:** the errors and check results of rule 18.
- **Catalogs:** work item kind `configured_estimate_failed`; INV-113 to INV-115 reserved; edge cases at DS-17's manufacturing dataset.
- **Other design items:**
  - DS-22: draft lines with configuration values, copying with re-evaluation, custom text on lines, the line warehouse check, cost checks through `estimate_configuration`;
  - DS-30: the configuration screen is generated from `EvaluateConfiguration`;
  - DS-34: a quotation agent that configures through `EvaluateConfiguration`.
- **Open questions:**
  - purchased configurable products;
  - multi-level configuration;
  - automatic release of configured items' cost estimates;
  - unknown cost needing human confirmation;
  - as-built required by default.

## Revisit when

- Sizing needs formulas beyond linear, or rules need a solver.
- Configurations must pass values to configurable subassemblies.
- Configurable goods are bought rather than made, or configured units move between warehouses.

## Documents updated

- **DDL:** [docs/design/DS-56-product-configuration.sql](../design/DS-56-product-configuration.sql) (new); [docs/design/DS-20-master-data.sql](../design/DS-20-master-data.sql) (columns).
- **The lab:** [docs/reviews/2026-11-14-design-validation/](../reviews/2026-11-14-design-validation/README.md): `lab/t06_configuration.py`, finding L-14.
- **ADRs:** notes in ADR-0018, ADR-0033, ADR-0034, ADR-0035, ADR-0036 and ADR-0045.
- **Design files:** [docs/design/DS-04-command-envelope.md](../design/DS-04-command-envelope.md), [docs/design/backlog.md](../design/backlog.md).
- **Catalogs:** [docs/catalogs/work-item-kinds.csv](../catalogs/work-item-kinds.csv).
- **Glossary:** [docs/spec/00-reading-guide.md](../spec/00-reading-guide.md).
- **Open questions:** [docs/open-questions.md](../open-questions.md).
- **Index and log:** [docs/adr/README.md](README.md); [docs/runbook/step-log.md](../runbook/step-log.md) at acceptance.
