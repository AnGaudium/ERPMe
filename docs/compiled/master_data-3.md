Module: master_data    Chunk: 3 of 8    Source ADRs: ADR-0045, ADR-0046
Build step(s): not stated in the index    Generated from index: 30d5706    Compiled by: Claude Opus 5.5, 2026-11-21

# `master_data` compiled spec, chunk 3: calendars, employees, groups, command checks, line options, items on order, option prices, product configuration

## Purpose

This chunk states the part of `master_data` law on: working calendars, employee profiles, the groups, the checks of master data commands and the partner commands, the master data lab, attribute modes and line options, items created on order, option prices, and the product configuration model with its evaluation, its stored configurations and the creation of configured items. `master_data` is a layer-3 module (ADR-0022 rule 2); `production` owns the selection conditions, sizing and estimate of configured products. Price lookup, units, partners and the other master data are in the other chunks.

## Entities and tables

DDL: `docs/design/DS-20-master-data.sql` and `docs/design/DS-56-product-configuration.sql`.

| Table | Meaning | Key | Parent | Owner |
| --- | --- | --- | --- | --- |
| `working_calendar_holiday` | A dated holiday of a calendar with its basis (R401) | `id`; (`working_calendar_id`, `holiday_date`) unique | `working_calendar` | `master_data` |
| `partner_group` | Partner group, copied from a package template (R404) | `id`; (`company_id`, `code`) unique | `company` | `master_data` |
| `product_attribute_value` | A value a product allows for an attribute of either mode (R417) | `id`; (`product_id`, `variant_attribute_id`, `variant_attribute_value_id`) unique | `product_variant_attribute` | `master_data` |
| `price_list_option_extra` | Extra per inventory unit for a chosen value (R427-R429) | `id`; exclusion on list, product, value and dates | `price_list` | `master_data` |
| `configuration_model` | The configuration model of a product (R437) | `id`; (`company_id`, `code`) unique | `product` | `master_data` |
| `configuration_model_revision` | A revision of a model, `draft` or `released` (R437) | `id`; (`configuration_model_id`, `revision`) unique | `configuration_model` | `master_data` |
| `configuration_rule` | A `restrict`, `set`, `require` or `forbid` rule of a revision (R440) | `id`; (`configuration_model_revision_id`, `position`) unique | `configuration_model_revision` | `master_data` |
| `configuration_table` | A table of allowed combinations (R441) | `id`; (`configuration_model_revision_id`, `code`) unique | `configuration_model_revision` | `master_data` |
| `configuration_table_column` | An ordered characteristic column of a table (R441) | `id`; (`configuration_table_id`, `column_number`) unique | `configuration_table` | `master_data` |
| `configuration_table_row` | A row of cells of a table (R441) | `id`; (`configuration_table_id`, `row_number`) unique | `configuration_table` | `master_data` |
| `configuration_default` | A default value of a characteristic, with a condition (R437, R444) | `id`; (`configuration_model_revision_id`, `position`) unique | `configuration_model_revision` | `master_data` |
| `product_configuration` | Immutable, content-addressed record of complete chosen values (R447) | `id`; (`company_id`, `product_id`, `content_hash`) unique | `product` | `master_data` |
| `product_configuration_value` | One characteristic's value in a configuration (R447) | `id`; (`product_configuration_id`, `variant_attribute_id`) unique | `product_configuration` | `master_data` |

Named by the rules of this chunk, with rows in chunk 1: `item_group`, `valuation_class`, `item_tax_group`, `product_category`.

Reads: `working_calendar`, `employee_profile`, `partner`, `variant_attribute`, `variant_attribute_value`, `product_variant_attribute`, `product`, `item`, `uom_conversion`, `price_list_entry`, `price_list_characteristic_rate`, `partner_tax_status`, `tax_treatment` (`master_data`, other chunks); `document_line_custom_text` (`documents`); `item_warehouse_planning` (`planning`); `production_structure` (`production`); `user_account`.

## Commands and queries

Authorization areas (catalog `authorization-areas.csv`, under `master_data`): `partner` (partners, roles, profiles, addresses, contacts and partner item codes), `partner_bank_account` (changed only through change proposals), `organization` (working calendars; `UpdateEmployeeOrganization` needs `full`), `master_data_group` (the groups and product categories), `product`. The level of a verb is the catalog's (`Create`, `Update`, `Set`: `edit`; `Evaluate`: `read`).

| Name | Actor and authorization | Input | Effect | Events | Error codes |
| --- | --- | --- | --- | --- | --- |
| `CreatePartner` | `master_data_change`, change-tracked; area `partner`, verb level `edit` | partner fields, `roles`, optional profiles, `addresses`, `email_domains` (R413) | Creates the partner with its roles, profiles and addresses; fills defaults (R414); checks the partner's accounts against ADR-0015.R4 (R6, R7) | not stated | `account_determination_missing`, `employee_organization_command_required` (R637); check result `partner_duplicate_suspected` (R40) |
| `UpdatePartner` | `master_data_change`, change-tracked; area `partner`, verb level `edit` | `partner_id` and the fields to change | Changes the partner; profiles merged (R413); checks the partner's accounts as `CreatePartner` (R6, R7) | not stated | `account_determination_missing`, `employee_organization_command_required` (R637) |
| `SetPartnerRole` | `master_data_change`, change-tracked; area `partner` | `partner_id`, `role`, `is_active`, the role's profile when added | Adds, activates or deactivates a role (R413) | not stated | not stated |
| `CreatePartnerAddress`, `UpdatePartnerAddress` | `master_data_change`, change-tracked; area `partner` | not stated | Maintains addresses (R413) | not stated | not stated |
| `CreatePartnerBankAccount`, `UpdatePartnerBankAccount` | `master_data_change`, change-tracked, always through a proposal; area `partner_bank_account` | not stated | Maintains bank accounts (R413) | not stated | not stated |
| `CreatePartnerItem`, `UpdatePartnerItem` | `master_data_change`, change-tracked; area `partner` | not stated | Maintains partner item codes (R413) | not stated | not stated |
| `EvaluateConfiguration` | computed query, verb `Evaluate`; area not stated | product, date or model revision, values | Runs `master_data.contract.evaluate_configuration` (R442-R446) | none | violation codes in the result (R445) |

`UpdateEmployeeOrganization` (R402), the only writer of `department_id`, `manager_partner_id` and `user_account_id` of `employee_profile`, has its row in chunk 4.

Contract functions, not registry commands: `master_data.contract.evaluate_configuration` and `master_data.contract.evaluate_condition` (R431, R442). Event `ConfiguredItemCreated` is emitted when a configured item is created (R450). `CreateContact` and `UpdateContact` are ADR-0052.R3's. Errors of master data commands bound to no single command above: `partner_not_employee` (R403), the unit, barcode and engineering checks of R406, R411 and R412, `line_option_required` and `line_option_value_not_allowed` (R419, R449), `proposal_required` and `price_missing` (R424, R426), `negative_price` and `option_extra_not_allowed` (R428, R429), `item_configurable_product` and `configuration_model_missing` (R432), `configuration_value_out_of_range` and `characteristic_in_use` (R434, R436), `configuration_rule_invalid` (R438), `planning_parameter_missing` (R451); database errors `revision_released` (R437) and `configuration_immutable` (R447).

## Rules

### Working calendars and employees

R401. Working calendars have working weekdays and dated holidays (ADR-0024 rule 4). Warehouses and suppliers name theirs. Holidays come from a package template entry with its basis, or are added by the company with basis `company_decision`; every `working_calendar_holiday` row carries its `basis`.
Source: ADR-0045.R10

R402. `employee_profile` has `branch_id`, `cost_center_id`, `job_title`, `department_id` and `manager_partner_id`. Its `user_account_id` is unique per company, so one user can be an employee of several companies. The profile is `personal` data (ADR-0019 rule 7). `department_id`, `manager_partner_id` and `user_account_id` change only through `UpdateEmployeeOrganization`, never through `CreatePartner`, `UpdatePartner` or a change proposal (ADR-0054 rule 6).
Source: ADR-0045.R11, ADR-0045.R11.N1

R403. A `buyer_id` or `salesperson_id` must be a partner with the active `employee` role, else `partner_not_employee`. A buyer without a user account cannot own work items; the fallback of ADR-0042 rule 7 then applies.
Source: ADR-0045.R11, ADR-0045.R5.N3

### Groups

R404. The groups are partner groups (`partner_group`), item groups (`item_group`), valuation classes (`valuation_class`), item tax groups (`item_tax_group`) and product categories (`product_category`); partner tax statuses and tax treatments (with the directions they apply to) replace partner tax groups, which no longer exist (ADR-0080.R1). They are `master_data` tables, copied from package templates with their basis (ADR-0016 rule 7). `basis` has no default: the command sets the template entry's basis, or `company_decision` (ADR-0016 rule 12). The tax matrix of ADR-0041, owned by `tax`, reads the item tax groups and tax treatments.
Source: ADR-0045.R12

R405. Product categories carry the defaults a new product takes: item group, valuation class, item tax group and inventory unit (`default_item_group_id`, `default_valuation_class_id`, `default_item_tax_group_id`, `default_inventory_uom_id`).
Source: ADR-0045.R12

### Checks of master data commands

R406. Besides ADR-0045.R2, ADR-0045.R3 and R403, commands check units: dimensions use a length unit and weights a mass unit; a serial-tracked product's inventory unit is a count unit with 0 decimals (ADR-0018 rule 9); every unit of a serial-tracked product is exact (`serial_unit_not_exact`); a product unit names a catalog-convertible unit only with the catalog's factor (`uom_conversion_conflict`); its `contains` relation matches the factors, also across a replacement (`uom_packaging_inconsistent`); a used row is immutable (`uom_conversion_in_use`); `is_exact` is computed, never entered; a unit field that needs a kind gets one (`uom_kind_mismatch`). A product's purchase and sales units may be any unit the item resolves.
Source: ADR-0045.R13, ADR-0045.R13.N3

R407. Commands check variants: an item's `variant_key` equals its variant value rows, which cover every variant-mode attribute of its product and only those.
Source: ADR-0045.R13

R408. Commands check, within the company: a cost center's parent, a partner's parent, a product category's parent, a classification value's parent, and the groups, units and accounts a row names (the composite keys of ADR-0045.R1 cover the rest); no `uom_conversion` row names a company unit (ADR-0018 rule 8; `INV-606`).
Source: ADR-0045.R13

R409. Commands check warehouses: a new warehouse gets its default zone and bin in the same command (ADR-0031 rule 8), and a valuation warehouse is physical. Option extras are allowed only on `sale` and `purchase` lists.
Source: ADR-0045.R13

R410. The database holds the rest: unique codes, kinds, positive dimensions and conversion factors, a gross weight not below the net, a stock product's valuation class, tracking only for stock, one default list per kind, one active by-product list, a list's kind on profiles, non-overlapping price entries and extras, a declaring branch's tax ID, a default bin in every warehouse, bins and zones of the same warehouse, a bin-managed warehouse's receiving and shipping bins, one processor warehouse per processor, the attribute modes, the composite keys of ADR-0045.R1, that a product unit is not the inventory unit, the item of an item-level row, and one active row per unit (ADR-0056 rules 4, 5, 15, 20).
Source: ADR-0045.R13, ADR-0045.R13.N3

R411. Barcode checks of master data commands (ADR-0061 rules 7-11): a barcode is unique in the company across item units, bins, handling units, lots, serials, barcoded documents and reserved codes, and numeric codes also on their digits padded to 14 (`barcode_taken`, held by the registry's keys); internal codes fit the format and GTINs and SSCCs carry valid check digits (`barcode_format_invalid`); values are stored normalized (`barcode_not_normalized`); a barcode does not start with a barcoded document type's reserved prefix (`barcode_prefix_reserved`); GS1 company prefixes are 4 to 12 digits and do not overlap (`gs1_prefix_invalid`, held by an exclusion constraint); a prefix with registry codes under it is deactivated, never deleted (`gs1_prefix_in_use`).
Source: ADR-0045.R13.N4

R412. Commands also check manufacturer part numbers unique per company on the normalized manufacturer and number (`item_manufacturer_part`), and category requirements naming their attribute or scheme (`product_category_requirement`); both are `master_data_change` (ADR-0062 rule 19).
Source: ADR-0045.R13.N5

R413. Partner commands (DS-20) are all `master_data_change` and change-tracked, with the optional `expected_version` of ADR-0029 rule 2:
- `CreatePartner`: `code`, `name`, `legal_name`, `partner_kind`, `tax_id`, `country`, `preferred_language`, `parent_partner_id`, `partner_group_id`, `partner_tax_status_id` (in place of the removed `partner_tax_group_id`, ADR-0080.R1), `roles` (a list of `customer`, `supplier`, `employee`), optional `customer_profile`, `supplier_profile` and `employee_profile` objects with their DS-20 columns (not the organization columns of R402), `addresses` (kind, address lines, subdivision code, postal code, country), and `email_domains` through `crm`'s hook;
- `UpdatePartner`: `partner_id` and the fields to change, profiles merged;
- `SetPartnerRole`: `partner_id`, `role`, `is_active`, and the role's profile when it is added;
- further: `CreatePartnerAddress` and `UpdatePartnerAddress`; `CreatePartnerBankAccount` and `UpdatePartnerBankAccount` (always through a proposal, ADR-0029 rule 4); `CreateContact` and `UpdateContact` (ADR-0052 rule 3); `CreatePartnerItem` and `UpdatePartnerItem` (ADR-0019 rule 6); `UpdateEmployeeOrganization` (ADR-0054 rule 6).
Source: ADR-0045.R13.N1

R414. Defaults `CreatePartner` fills for empty fields: `partner_group_id` from the company settings `master_data.default_partner_group.customer`, `master_data.default_partner_group.supplier` and `master_data.default_partner_group.employee` (an active partner group, or empty), taking the first role of the payload whose setting is set; a customer or supplier profile's `receivable_account_id` or `payable_account_id` from the determination rows of `receivable_reconciliation` or `payable_reconciliation` for that group (ADR-0015 rule 11), else `account_determination_missing`. The profile's list, payment term and currency stay empty, so documents take the company's defaults (ADR-0047 rules 4, 10). There is no default credit limit: an empty `credit_limit` means no credit check (ADR-0047 rule 18 note).
Source: ADR-0045.R13.N1, ADR-0045.R13.N2

### Master data lab

R415. Lab check `t05_master_data.py` covers what the database holds, not the command checks of R406 to R409:
- constraints: forty-one scenarios, each matched to the constraint that must refuse it, and a check that every DS-20 table outside the global catalogs and `incoterm` has `company_id`;
- the lookup: twenty cases on real rows, with exact fractions: breaks and dates; a carton from the each price; the entered unit's entry winning; fallback when no break qualifies; a 7/3 product unit with rounding; a unit through `uom_conversion`; a unit that is not allowed; option extras, with a product-specific extra winning, an expired extra, an extra on a 7/3 unit, and a negative total;
- earlier tests: the journal, subledger, cost object and opening tests pass on the real master data tables in place of the old stubs (L-13).
Source: ADR-0045.R14, ADR-0045.R14.N1

### Attribute modes and line options

R416. `variant_attribute.variant_mode` (the value's `variant_mode`) is `variant` (ADR-0018 rules 6-7: each combination of values is an item, with its own stock, cost and prices) or `line_option`. Each value carries its attribute's mode through a composite key, so the database refuses a line option as an item's variant value and refuses to change an attribute's mode once it has values; which modes an option extra may name is R429.
Source: ADR-0045.R15

R417. A line option is chosen on a document line and creates no item, such as a finish, an engraving, a fabric for goods made to order or a delivery packing. A product names its attributes of both modes in `product_variant_attribute`. A line option may be `is_required`, and `product_attribute_value` may limit the values a product allows for an attribute of either mode (none listed means every value).
Source: ADR-0045.R15

R418. A value marked `is_custom` (line options only; the database holds it) asks the line for free text, such as an engraving's words. The text is `personal` and `is_untrusted` (ADR-0019 rule 7, ADR-0029 rule 10) and stays on the line (R448). Whether it prints on the e-invoice line is the e-invoice add-on's (DS-24).
Source: ADR-0045.R15

R419. A line's choices on DS-22 and production documents are a `product_configuration` whose values are the chosen option values (R447-R449), one value per attribute per line, part of the line's content and of the plan; custom text stays on the line. The commands check required options and allowed values (`line_option_required`, `line_option_value_not_allowed`). Options are copied to deliveries, returns and credit notes. A price extra is folded into the line's unit price, not a separate invoice line. Purchase and subcontracting lines may carry options too, as information for the supplier.
Source: ADR-0045.R15

R420. Line options are not part of the stock key: two lines of one item with different options draw on the same stock. An option that must be kept apart in stock, costed apart or taxed apart is a variant attribute instead. Options travel to the delivery, the pick list and, for goods made to order, the production order.
Source: ADR-0045.R15

R421. An option with a price extra has no cost of its own: extra material or labor averages into the item's periodic cost, and "below cost" and margin ignore it. The cost and stock of options are settled by the split between item-defining characteristics and line options: configured units that change the goods are made to order (ADR-0036 rule 9) or made into their own items (R422), and line options carry no cost (ADR-0046.R12, ADR-0046.R14).
Source: ADR-0045.R15

### Items created on order

R422. A product with `is_item_created_on_order` lets a document line name a combination of its variant values that has no item yet. On the draft the line holds the product and the chosen variant values, with no item. Simulation and drafts create nothing; the plan lists the item that would be created.
Source: ADR-0045.R16

R423. Only document types with the registry flag `is_item_creating` (sales orders, and production orders) create items when they leave draft; quotations never do (ADR-0047 rule 1). The item is created when the document leaves draft (its first `Submit`, `Issue` or `Post`), in that command's transaction, as `CreateItem` would (ADR-0018 rule 7). An abandoned draft leaves no item. An existing item with the same `variant_key` is reused.
Source: ADR-0045.R16

R424. `system` creates the item on behalf of the human whose command takes the document out of draft, as a consequence of that command, so that person needs the command's own permission (such as `SubmitSalesOrder`), not `CreateItem`; a person who may submit orders thus creates only the combinations the product allows. `proposal_required` applies only where an item would be created: at the command that takes a document of an `is_item_creating` type out of draft, when an agent, or a command carrying an origin agent run, runs it; the agent proposes the item through a change proposal first (ADR-0029 rule 4). An agent's draft (a quotation, or a sales order draft) may hold the product with its variant values or configuration and no item; the item is created when a person's command takes the order out of draft (R450).
Source: ADR-0045.R16, ADR-0045.R16.N1, ADR-0045.R16.N2

R425. The combination respects `product_attribute_value` and covers every variant-mode attribute of the product. The item's code is the product's code, a hyphen and the next number of `product.last_item_number`, incremented under the product row's lock (gaps allowed; it is not a legal series).
Source: ADR-0045.R16

R426. The new item has no price entry, preliminary price, planning parameters or production version. `find_price` returns none, so the line's price is entered (outside the list, `price_missing`) or comes from DS-56's configured price (ADR-0046.R15), and a made item cannot be released (ADR-0033 rule 16) until DS-56 supplies its production version. Every item still exists before stock or cost touches it.
Source: ADR-0045.R16

### Option prices

R427. `price_list_option_extra` (list, optional product, option value, `variant_mode`, dates, `unit_price_extra` per inventory unit, which may be negative) adds to the price of ADR-0045.R4. For each chosen value, the extra valid on the date for that product wins; else the extra for all products. Extras of one list, product (or all products) and value never overlap in dates (an exclusion constraint).
Source: ADR-0045.R17

R428. The extras of all chosen values are summed per inventory unit, multiplied by the factor of ADR-0045.R4, rounded half up once to the unit-price scale, and added to the base price. A negative total gives no price (`negative_price`). The lab checks each of these, including a carton and a 7/3 unit.
Source: ADR-0045.R17

R429. For a configurable product, extras apply to values of both modes, a product-level entry gives the base price, and `price_list_characteristic_rate` prices numbers. For other products an extra names only a line-option value; the database holds that the extra's `variant_mode` matches its value's mode, and the command check `option_extra_not_allowed` refuses a variant-mode extra for a product that is not configurable. `find_price` takes the chosen values, and an item entry of a configured item replaces its item-defining extras and rates (ADR-0046.R15).
Source: ADR-0045.R17

### Product configuration: scope and modules

R430. Product configuration is in Phase 1 for assembly manufacturers (2026-11-15). A configurable product is sold by choosing values for its characteristics, which are the attributes of R416 in the same modes: item-defining characteristics are variant-mode attributes, each distinct combination of their values one configured item with its own stock and periodic average cost; line options change the price and the documents, never the item, the bill of materials or the cost. The configuration travels with the unit to production, delivery, its serial number and service. Configured items are planned make to order.
Source: ADR-0046.D0

R431. Modules (ADR-0022 rule 2):
- `master_data` owns the characteristics (columns on `variant_attribute`), configuration models and their revisions, rules, tables and defaults, `product_configuration` and its values, and the price tables. It publishes `master_data.contract.evaluate_configuration` and `master_data.contract.evaluate_condition`.
- `production` owns the selection conditions and sizing on bill of materials components and routing operations, product-level production versions, and `production.contract.estimate_configuration`. It calls `evaluate_condition`.
- Commercial modules (`sales`, `purchasing`) and `production` carry a configuration on their lines.
- Model maintenance is `master_data_change`, change-tracked (ADR-0038 rule 3) and `is_proposal_bound` (ADR-0029 rule 5). Finding or creating a configuration record is part of the line's command.
Source: ADR-0046.R1

R432. A configurable product (`product.is_configurable`) is a `stock` product with `is_item_created_on_order` (R422; the database holds both), at least one item-defining characteristic, a released configuration model revision valid on the document date (`configuration_model_missing`), and a product-level production version (ADR-0046.R12). Its items are configured items, one per distinct combination of item-defining values, created only by R450. A manual `CreateItem` for a configurable product is rejected with `item_configurable_product`. No item exists for the product itself.
Source: ADR-0046.R2

R433. Every item-defining characteristic is required, since the item needs its value. A line option is required when `product_variant_attribute.is_required` is set or a `require` rule holds. Phase 1 limit: configurable products are made, not bought (flagged). Purchased configurable goods, and configurations passed down to configurable subassemblies, come later (open question).
Source: ADR-0046.R2

### Characteristics

R434. The column `value_type` of `variant_attribute` is `list` (values are `variant_attribute_value` rows) or `number`. For numbers `uom_id`, `minimum_value`, `maximum_value`, `step_value` and `decimal_places` are all set, and for a list all empty; the database holds this (`ck_variant_attribute_number`), except that it does not require `uom_id` for a number. A value must lie in the range and equal `minimum_value` plus a whole number of steps (`configuration_value_out_of_range`). Values are exact decimals, never floats.
Source: ADR-0046.R3

R435. When R450 creates an item, each item-defining number becomes a `variant_attribute_value` row with `numeric_value` and a canonical code (the decimal without trailing zeros, such as `37.5`), unique per attribute and number. The item's `variant_key` (ADR-0018 rule 7) therefore works unchanged. Configurations store numbers as numbers (R447), so drafts and quotations create no value rows.
Source: ADR-0046.R3

R436. Once a characteristic is named by a model revision, a configuration, a structure or an item, its mode, value type, unit, range, step and code, and the codes of its values, never change (`characteristic_in_use`); rules and tables refer to codes. `product_variant_attribute` (R417) lists the product's characteristics, with `position`, `is_required`, and the allowed list values of `product_attribute_value`.
Source: ADR-0046.R3

### Configuration models and revisions

R437. `configuration_model` (company, product, `code`, `name`, `is_active`; one active model per product) has `configuration_model_revision` rows. Revisions follow ADR-0033 rules 3-4: `revision`, `state` (`draft`, `released`), `start_date`, `content_hash` (set with `released_at` at release), immutability after release (a database trigger rejects changes to a released revision and to its rules, tables, columns, rows and defaults: `revision_released`), validity by the highest released revision started on the date, no retroactive or out-of-order release, and withdrawal of a mistaken release. A revision's content is its `configuration_rule` rows (R440), its `configuration_table` rows with their `configuration_table_column` and `configuration_table_row` rows (R441), and its `configuration_default` rows (characteristic, value or number, optional condition, `position`). Each row carries the product, and its characteristics are keyed to the product's `product_variant_attribute` rows.
Source: ADR-0046.R4

R438. Release checks (`configuration_rule_invalid`, with the rule and the reason): conditions and effects follow the grammar of R439 to R441; list values belong to their attribute and are allowed for the product; numbers are in the characteristic's range and step; the product's bills of materials and routings of every product-level version valid from the revision's `start_date` name only item-defining characteristics in their conditions and sizing (ADR-0046.R12). Releases lock the company's `production_structure` row (ADR-0033 rule 8), so a model and a bill of materials cannot be released inconsistently at the same time.
Source: ADR-0046.R4

### Conditions, rules and tables

R439. Conditions have one grammar, stored as canonical JSON (ADR-0008 rule 12):
- a term: `{"c": <characteristic code>, "op": <op>, "v": <value>}`; operators `eq`, `ne`, `in`, `not_in` (list values or numbers); `lt`, `le`, `gt`, `ge`, `between` (numbers); `set`, `unset` (no value);
- combinations: `{"all": [...]}`, `{"any": [...]}` and `{"not": ...}`, nested at most three deep; an empty condition is true;
- unknown values: a term on a characteristic with no value yet is unknown, under three-valued logic (`all` is false if any part is false, else unknown if any part is unknown; `not` keeps unknown); a rule acts only when its condition is true;
- monotone by construction: values are only added during evaluation, and every operator except `set` and `unset` keeps its truth once known, so a condition that has become true stays true; `set` and `unset` may appear only in the conditions of `require` and `forbid` rules, which are checked once on the final state (R444);
- no arithmetic in conditions, no references to other records, no functions; evaluation is pure, total and deterministic.
Source: ADR-0046.R5

R440. A `configuration_rule` has `position` (for display only), a `condition` (R439), a `kind`, a target characteristic, an `effect` and a `message_code`:
- `restrict`: while the condition is true, the target's allowed values become their intersection with the given list or numeric range;
- `set`: while the condition is true, the target takes the given value;
- `require`: if the condition is true on the final state, the target must have a value;
- `forbid`: the condition must not be true on the final state; when it is, it is a violation with the rule's message code; it names no target.
Source: ADR-0046.R6

R441. A `configuration_table` has ordered `configuration_table_column` rows (characteristics) and `configuration_table_row` rows giving allowed combinations. A cell holds a list value's code, a number, `*` (any), or for a number column an inclusive range `{"min": n, "max": n}`. The values set in the table's columns must match at least one row; a row matches when every cell is `*`, equals the value (numbers compared exactly), contains it (ranges), or names a column with no value yet. Each list column without a value narrows to the cells of the matching rows, unless one of them is `*`; number columns take part only once they have a value. Tables are for compatibility (which components fit together) and for deriving one characteristic from others, such as a size class from width bands: the class narrows to one value and is then taken (R442).
Source: ADR-0046.R7

### Evaluation

R442. `master_data.contract.evaluate_configuration(model_revision, values)` is pure and order-independent. Each characteristic starts from its list values limited by `product_attribute_value`, or its numeric range with step. Evaluation runs in rounds; each round evaluates every `restrict` and `set` rule and every table against the state at the start of the round, then applies their effects together:
- restrictions intersect;
- a characteristic without a value takes one when every true `set` rule for it proposes the same allowed value, or, for a required characteristic (R433), when its allowed list values, or the step values of its numeric range, are exactly one (an optional line option is never chosen for the user);
- tables narrow list columns.
The effects combine commutatively and conditions only gain truth (R439), so rule positions never change the result and nothing needs undoing.
Source: ADR-0046.R8

R443. Rounds stop when a round gives no value. Domains are recomputed each round from the initial domains, the true restrictions and the tables, so a round changes the state only by giving values: there are at most the number of characteristics + 1 rounds. Exceeding the bound is an internal error.
Source: ADR-0046.R8

R444. After the fixed point, `configuration_default` rows apply one at a time in position order, each to a characteristic still without a value where its condition is true and its value is allowed, and each followed by rounds to a new fixed point. The final checks on the final state are the `require` and `forbid` rules, the required characteristics (R433) and the violations.
Source: ADR-0046.R8

R445. Violations, each with a stable code, the rules or table involved and the characteristics:
- `configuration_value_out_of_range`: a value outside the final allowed values, whatever its source: a user value, or a value taken in an earlier round or from a default that later restrictions excluded (with the message codes of the restricting rules);
- `configuration_set_conflict`: a `set` rule whose value is outside the target's allowed values, differs from the user's value, or differs from another true `set` rule;
- `configuration_domain_empty`: a list domain narrowed to nothing, or a numeric range that holds no step value;
- the rule's own message code: a true `forbid`;
- `configuration_table_no_match`: a table with no row matching the values set.
Source: ADR-0046.R8

R446. The result gives, for each characteristic, its value, the value's source (`user`, `rule`, `default`), its allowed values or range as they stood before defaults, and whether it is required; the violations, the missing required characteristics, `is_complete` (nothing missing and no violation), and a result hash. For each allowed list value of a characteristic without a user or rule value, including one that took a default (whose default the tried value replaces), `leads_to_violation` is true only when evaluating with that value adds a violation (code, rule or table, and characteristics) that the result without it does not have; violations already present never mark a value. Allowed values are necessary, not sufficient: a combination of allowed values can still meet a `forbid` or a table several steps later, and the lookahead flags the direct cases; a configuration is accepted only when it is complete. The query `EvaluateConfiguration` (product, date or model revision, values) exposes the function to people and agents; it is computed, an exception to ADR-0004 rule 21 like `GetPrice`, and a screen and an agent see the same remaining choices. The quotation agent's configuring loop is ADR-0051 rule 15.
Source: ADR-0046.R8, ADR-0046.R8.N1

### Stored configurations

R447. A `product_configuration` has company, product, `content_hash` and `created_at`. The hash is the SHA-256 of the canonical JSON of the product ID and the sorted pairs of attribute ID and value (a list value's ID, or a number as a decimal without trailing zeros, so `37.50` and `37.5` hash alike). The record is unique per company, product and hash, so the same choices are stored once and reused across quotations, orders and production. `product_configuration_value` rows give the characteristic, its `value_type`, and either `variant_attribute_value_id` (list values) or `numeric_value` (numbers, in both modes); a composite key on the value type holds this in the database. A trigger rejects updates and deletes, and value rows added to a configuration created by an earlier transaction (`configuration_immutable`). The record stores its top-level transaction (`created_xact_id`), so a configuration saved inside a savepoint of a command batch (ADR-0029 rule 3) still takes its values.
Source: ADR-0046.R9

R448. The record holds no model revision and no sources: they belong to the evaluation. A line keeps the revision it was evaluated under and the sources in its own content. Every find-or-create, and every line leaving draft, evaluates the values under the revision valid on the document date. Only complete, valid configurations are stored: a draft line holds its chosen values as canonical JSON in its content, each save evaluates them and returns the result, and when they are complete the line references the configuration found or created. Free text for `is_custom` values (R418) stays on the line, in `document_line_custom_text` (line, attribute, text), labeled `personal` and `is_untrusted`, so the shared record never needs erasure.
Source: ADR-0046.R9

R449. A line's choices are a configuration for any product with line options, and for every configurable product (R419). A product with line options and no configuration model (not configurable) is evaluated by an implicit model: its line options' domains limited by `product_attribute_value`, the `is_required` options required, and no rules, tables or defaults. Missing options and values not allowed are reported as `line_option_required` and `line_option_value_not_allowed`, and a complete set of choices is stored as a `product_configuration` like any other. The line keeps no model revision, and a copy re-checks only allowed values and required options.
Source: ADR-0046.R9, ADR-0046.R9.N1

### Creation of configured items

R450. When a sales order or a production order (registry flag `is_item_creating`, ADR-0047 rule 1) leaves draft (R423), each configurable line gets its configured item: the item whose `variant_key` equals the configuration's item-defining values; if it does not exist, the number value rows are found or created (R435) and the item is created. Two configurations that differ only in line options share the item. The configured item, its number value rows and its `item_warehouse_planning` rows are created by `system` on behalf of the human whose command takes the order out of draft, as a consequence of that command (one of the ADRs that ADR-0027 rule 12 requires for a system job acting for a human); that person needs the command's own permission (`SubmitSalesOrder`, or the command that takes a production order out of draft), not `CreateItem`. `proposal_required` applies to an agent, or a command carrying an origin agent run. The code uses `product.last_item_number` as in R425; quotations and drafts create nothing. The name is the product's name followed by the item-defining values in position order, such as `Unit 1200 × 800 / steel / wall`, translated like the product's name. Created with it, in the same transaction: an `item_warehouse_planning` row for each production warehouse of the product's product-level versions, with source `production`, method `net_requirements`, lot size `exact` and strategy `make_to_order` (ADR-0036 rule 9), and an event `ConfiguredItemCreated`. A system consumer of `ConfiguredItemCreated` computes and releases the item's cost estimate (ADR-0046.R14).
Source: ADR-0046.R11, ADR-0046.R11.N2

R451. A sales line of a configured item in a warehouse without its `make_to_order` row is rejected, and open demand on a node without a planning row raises `planning_parameter_missing` (reason `planning_row_missing`) (ADR-0036 rule 9 note).
Source: ADR-0046.R11.N1

R452. Writing the configured item onto each line changes the order's content, so the same transaction writes a new document version (actor `system`, `on_behalf_of` the submitter) whose content equals the typed rows (`INV-10`; ADR-0009 rule 9). It is written before the `Submit`'s policy evaluation, so the policy decision and any approval bind to the version that names the items; it is not an `Update` and voids nothing. The submitter is thereby a writer of the order and cannot approve it (ADR-0055 rule 7, condition 5).
Source: ADR-0046.R11.N3

## Settings

None: no setting key used by this chunk's rules has a row in `settings.csv`. The company settings `master_data.default_partner_group.customer`, `master_data.default_partner_group.supplier` and `master_data.default_partner_group.employee` (R414) are named by ADR-0045.R13.N1 but absent from `settings.csv`.

## Conflicts

CONFLICT ADR-0045.R11: ADR-0045.R11.N1 governs; `user_account_id` is unique per company, not across companies, and the profile gains `department_id` and `manager_partner_id` (R402), as the DDL holds; ADR-0045.R5.N3 confirms the interim choice that a buyer needs a user account to own work items (R403).
CONFLICT ADR-0045.R12: ADR-0080.R1 governs; partner tax groups no longer exist and are replaced by `partner_tax_status` and `tax_treatment`, which carries the directions; the tax matrix reads tax treatments and item tax groups (R404).
CONFLICT ADR-0045.R13.N1: ADR-0080.R1 governs; the partner field `partner_tax_group_id` no longer exists, the partner carries `partner_tax_status_id` per the DDL, so `CreatePartner` takes that field (R413).
CONFLICT ADR-0045.R13: ADR-0045.R13.N3 governs; purchase and sales units may be any unit the item resolves, and the database, not a command, holds that a product unit is not the inventory unit (R406, R410).
CONFLICT ADR-0045.R15: the rule's closing paragraph and ADR-0046.R9 govern; a line's choices are stored as `product_configuration` values, not as `document_line_option` rows, which have no DDL, and custom text stays in `document_line_custom_text` (R419, R448); ADR-0046.R14 closes the open point on the cost and stock of options (R421); ADR-0046.R15 turns the database refusal of variant-mode extras into the command check `option_extra_not_allowed` (R416, R429).
CONFLICT ADR-0045.R16: ADR-0045.R16.N2 governs who creates an item on order: `system` for the submitting person, who needs the command's own permission and not `CreateItem`; ADR-0045.R16.N1 limits `proposal_required` to the command leaving draft (R424).
CONFLICT ADR-0045.R17: the rule's closing paragraph citing ADR-0046.R15 governs; extras of configurable products may name variant-mode values, and the mode limit for other products is the command check `option_extra_not_allowed` (R429).
CONFLICT ADR-0046.R8.N1: the note replaces the lookahead definition; `leads_to_violation` marks a value only when it adds a violation absent from the result without it, and covers characteristics that took a default (R446).
CONFLICT ADR-0046.R11.N2: the note replaces "the actor's `CreateItem` permission" under the rule's who, when and code; `system` creates configured items for the person leaving draft, who needs the command's own permission (R450).

## Trace

| Source | Where |
| --- | --- |
| ADR-0045.R10 | R401 |
| ADR-0045.R11 | R402, R403 |
| ADR-0045.R11.N1 | R402 |
| ADR-0045.R12 | R404, R405 |
| ADR-0045.R13 | R406-R410 |
| ADR-0045.R13.N1 | R413, R414 |
| ADR-0045.R13.N2 | R414 |
| ADR-0045.R13.N3 | R406, R410 |
| ADR-0045.R13.N4 | R411 |
| ADR-0045.R13.N5 | R412 |
| ADR-0045.R14 | R415 |
| ADR-0045.R14.N1 | R415 |
| ADR-0045.R15 | R416-R421 |
| ADR-0045.R16 | R422-R426 |
| ADR-0045.R16.N1 | R424 |
| ADR-0045.R16.N2 | R424 |
| ADR-0045.R17 | R427-R429 |
| ADR-0046.D0 | R430 |
| ADR-0046.R1 | R431 |
| ADR-0046.R2 | R432, R433 |
| ADR-0046.R3 | R434-R436 |
| ADR-0046.R4 | R437, R438 |
| ADR-0046.R5 | R439 |
| ADR-0046.R6 | R440 |
| ADR-0046.R7 | R441 |
| ADR-0046.R8 | R442-R446 |
| ADR-0046.R8.N1 | R446 |
| ADR-0046.R9 | R447-R449 |
| ADR-0046.R9.N1 | R449 |
| ADR-0046.R11 | R450 |
| ADR-0046.R11.N1 | R451 |
| ADR-0046.R11.N2 | R450 |
| ADR-0046.R11.N3 | R452 |
