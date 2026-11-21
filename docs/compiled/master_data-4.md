Module: master_data    Chunk: 4 of 8    Source ADRs: ADR-0046, ADR-0049, ADR-0052, ADR-0053, ADR-0054, ADR-0056
Build step(s): 0, 4, 5, 8    Generated from index: 30d5706    Compiled by: Claude Opus 5.5, 2026-11-21

# Compiled spec: `master_data`, chunk 4

## Purpose

`master_data` owns partners, products, items, units, prices and the organization's master records (ADR-0022.R2); it sits
in layer 3. This chunk states configured prices and the configuration catalog of ADR-0046, the print profile, contact
normalization, the partner kind `sole_proprietorship`, departments and teams, and the core of multi-UoM: the inventory
unit, units, global conversions, product units, retire-and-replace and `convert_quantity`. Rules of this part's units for
which another module is primary (production, purchasing, sales, reporting, agents, query, tax, permissions, policy,
documents, crm, cash) are traced `ref:` and not restated.

## Entities and tables

| Table | Meaning | Key | Parent | Owner |
| --- | --- | --- | --- | --- |
| `price_list_characteristic_rate` | Rate per value of a number characteristic of a configurable product on a price list (R605) | `id` | `price_list` | `master_data` |
| `print_profile` | Print header of the company (`branch_id` null) or of a branch (R622) | `id`; unique (`company_id`, `branch_id`) | `company` | `master_data` |
| `department` | Department tree of a company (R633) | `id`; unique (`company_id`, `code`) | `company` | `master_data` |
| `team` | Optional team, for example a sales team across departments (R634) | `id`; unique (`company_id`, `code`) | `company` | `master_data` |
| `team_member` | Employee partner in a team (R634) | `id`; unique (`team_id`, `partner_id`) | `team` | `master_data` |
| `uom_conversion` | Core catalog of direct pairs between core units of one kind (R647-R650) | `id`, uuid5 of `uom_conversion:<from code>:<to code>` | none (installation table) | `master_data` |
| `product_uom` | Other units of a product, or of one item, with factor and packaging (R651-R660) | `id`; one active row per (`company_id`, `product_id`, `item_id`, `uom_id`) | `product`, `item` | `master_data` |

DDL: `docs/design/DS-20-master-data.sql` (`print_profile`, `uom_conversion`, `product_uom`, `uom`, `price_list_entry`,
`price_list_option_extra`, `employee_profile`, `contact`), `docs/design/DS-56-product-configuration.sql`
(`price_list_characteristic_rate`, `product_configuration`), `docs/design/DS-15-access.sql` (`department`, `team`,
`team_member`).

Tables of other chunks of this module that these rules extend: `uom` (gains `name`, R642), `price_list_entry` (gains
`product_id`, R602), `price_list_option_extra` (R604), `employee_profile` (gains `department_id`, `manager_partner_id`,
R635), `contact` (R627), `supplier_item` (`order_uom_id`, R659), `partner_item`, `item`, `product`, `branch`, `company`,
`partner_address`, `data_translation`, `product_configuration`.

## Commands and queries

| Name | Actor and authorization | Input | Effect | Events | Error codes |
| --- | --- | --- | --- | --- | --- |
| `CreateConfigurationModel`, `CreateConfigurationModelRevision`, `UpdateConfigurationModelRevision`, `ReleaseConfigurationModelRevision` | `master_data_change`; catalog leaf `configuration_model` (module `production`); releases by an agent are change proposals (R614) | A model; a revision copied from a revision or empty | Maintain configuration models and revisions | `ConfigurationModelRevisionReleased` declared (R613) | R615 |
| `SetPriceListCharacteristicRates` | `master_data_change`; area not stated | List, product, number characteristic, dates, `rate_per_value` | Writes `price_list_characteristic_rate` rows | None stated | None stated |
| `GetConfigurationEstimate`, `GetProductConfiguration`, `ListConfigurationModel`, `ListConfiguredItem` (product, values), `GetSerialConfiguration` (serial) | Queries; verb `Evaluate` is level `read` (catalog); area not stated | As named | Read only | None | None stated |
| `CreatePrintProfile`, `UpdatePrintProfile` | `master_data_change`; leaf `print_profile`; only the `owner` role template holds `UpdatePrintProfile` | The company's or a branch's print profile | Writes `print_profile` (R622) | None stated | None stated |
| `CreateDepartment`, `UpdateDepartment`, `CreateTeam`, `UpdateTeam` (with members), `UpdateEmployeeOrganization` | `master_data_change`, `human_only`; leaf `organization` at `full` | Department, team, or an employee's `department_id`, `manager_partner_id`, `user_account_id` | Writes `department`, `team`, `team_member`, `employee_profile` (R633-R639) | None stated | `department_cycle`, `employee_manager_cycle`, `organization_self_change` |
| `ListDepartment`, `ListTeam` | Queries; leaf `organization` | None stated | Read only | None | None stated |

`EvaluateConfiguration` (R612, R616) has its row in chunk 3; `CreateProductUom` and `UpdateProductUom` (R661-R668) have
theirs in chunk 5.

Not commands: the pure function `master_data.contract.convert_quantity` (R669), which raises `uom_not_allowed` and
`uom_retired`; `master_data.contract.find_price` (R601). The event `ConfiguredItemCreated` is declared (R613) without an
emitting command in these rules. `CreatePartner` and `UpdatePartner` raise `employee_organization_command_required`
(R637). `CreateContact` and `UpdateContact` normalize addresses and phones (R627, R628) and raise `validation_failed`.
Check result: `product_uom_replaced` (R666). The catalog error and check codes of ADR-0046 are listed in R615-R617.

## Rules

### Configured prices

R601. Configured prices go through ADR-0045.R4. `find_price` takes the chosen values (so an incomplete draft can be priced) instead of a list of option values. Lookup order: the item's entry in the entered unit, then the item's entry in the inventory unit, then the product's entry in the entered unit, then the product's entry in the inventory unit, each by ADR-0045.R4.
Source: ADR-0046.R15

R602. `price_list_entry` has `product_id`, exclusive with `item_id`, allowed only for configurable products: the base price of every configured item of the product.
Source: ADR-0046.R15

R603. An entry for the configured item, which a configuration sold often can get, is that item's whole price before line options; item-defining extras and rates are then not added. Line-option extras and rates are always added.
Source: ADR-0046.R15

R604. `price_list_option_extra` applies to the values of both modes of a configurable product. For other products it stays limited to line options; the mode check is the command check `option_extra_not_allowed`.
Source: ADR-0046.R15

R605. `price_list_characteristic_rate` (list, product, numeric characteristic, dates, `rate_per_value`) adds `rate_per_value` × the chosen number, per inventory unit. The database keys it to number characteristics. Rates of one list, product and characteristic never overlap in dates.
Source: ADR-0046.R15

R606. The configured price is base + extras + rates, multiplied by the factor and rounded once, exactly as ADR-0045.R17. The result lists every row used.
Source: ADR-0046.R15

R607. For a configured item, its own product units (item-level `product_uom` rows, added by a person) come first in the conversion factor, then the product's (R651, R669).
Source: ADR-0046.R15.N1

### The configuration after delivery

R608. A serial of a configured item knows its item-defining values through its item. Its line options come from the configuration of the delivery line that shipped it. Its as-built components come from `GetTraceability` (ADR-0034.R16).
Source: ADR-0046.R16

R609. `GetSerialConfiguration` (serial) returns item-defining values, line options and as-built components together, for service and for an agent answering a customer.
Source: ADR-0046.R16

R610. Product-level versions default `is_as_built_required` to true for serial-tracked configurable products, because service needs the actual components of each unit (flagged).
Source: ADR-0046.R16

### Configuration commands, queries, events and catalog rows

R611. Commands (`master_data_change`): `CreateConfigurationModel`, `CreateConfigurationModelRevision` (copied from a revision or empty), `UpdateConfigurationModelRevision`, `ReleaseConfigurationModelRevision`, `SetPriceListCharacteristicRates`.
Source: ADR-0046.R17

R612. Queries: `EvaluateConfiguration`, `GetConfigurationEstimate`, `GetProductConfiguration`, `ListConfigurationModel`, `ListConfiguredItem` (product, values), `GetSerialConfiguration`.
Source: ADR-0046.R17

R613. Events: `ConfigurationModelRevisionReleased`, `ConfiguredItemCreated`.
Source: ADR-0046.R17

R614. An agent may evaluate, estimate, draft lines with configurations, and propose model revisions. Releases are change proposals, and new configured items are created only by a human leaving draft (ADR-0046.R11).
Source: ADR-0046.R17

R615. Errors: `configuration_model_missing`, `configuration_value_out_of_range`, `configuration_rule_invalid`, `configuration_incomplete`, `configuration_invalid`, `configuration_in_production`, `configuration_warehouse_not_produced`, `configuration_characteristic_not_item_defining`, `configured_quantity_negative`, `routing_conditions_shared`, `characteristic_in_use`, `item_configurable_product`, `option_extra_not_allowed`; database errors `revision_released` and `configuration_immutable`.
Source: ADR-0046.R18

R616. Violation codes, returned by `EvaluateConfiguration` and in the details of `configuration_incomplete` and `configuration_invalid`: `configuration_value_out_of_range`, `configuration_set_conflict`, `configuration_domain_empty`, `configuration_table_no_match`, and each `forbid` rule's message code.
Source: ADR-0046.R18

R617. Check results: `configured_explosion_empty`, `configured_stock_available`. Work item kind: `configured_estimate_failed` (`work-item-kinds.csv`).
Source: ADR-0046.R18

R618. The invariants `INV-113`, `INV-114` and `INV-115` are reserved in the production range and added when the production core step is numbered (ADR-0033.R16). `INV-114`: every `product_configuration`'s `content_hash` equals the hash of its stored values. `INV-115`: every component and operation condition and sizing of a product-level structure names only item-defining characteristics of its product.
Source: ADR-0046.R18

R619. `INV-113`: every non-draft line of a configurable product on a document of an `is_item_creating` type, and every stock document line of one, names a complete configuration and an item whose variant values equal the configuration's item-defining values; a non-draft quotation line names a complete configuration, and an item only when one with those values exists (ADR-0018.R2).
Source: ADR-0046.R18, ADR-0046.R18.N1

R620. Edge cases, coded by DS-17 when the manufacturing company's dataset is built:
   - a quotation copied to an order after a model revision forbids its configuration;
   - two orders with the same item-defining values and different line options share one item;
   - a number off the step;
   - a table narrowing that leaves one value;
   - a change order on a configured line with an open production order;
   - free stock of a configured item when a new line asks for it.
   Source: ADR-0046.R18

R621. Lab check `t06_configuration.py` loads the DDL with DS-20 and DS-06 and, on a neutral configurable product with numeric and list characteristics, rules, a table with ranges, and defaults, checks:
   - evaluation: narrowing, derived values, defaults, each kind of violation with its message codes, completeness, step and range, the lookahead, and that the lookahead marks only values that add a violation absent from the result without them (ADR-0046.R8);
   - order independence and idempotence on 300 random models, with the bound never reached;
   - re-evaluation under a later revision that forbids a configuration;
   - content-addressed reuse of configurations, the recomputed hash, and numbers stored as numbers;
   - configured items shared across line options and distinct across item-defining values, with number value rows created only then;
   - the super bill of materials explosion with conditions and linear sizing, and the release checks;
   - configured prices, including an item entry replacing the item-defining part;
   - that estimates of two configurations differ;
   - the immutability triggers, including a row moved out of a released revision and a configuration saved inside a savepoint, and `company_id` on every DS-56 table.
   Source: ADR-0046.R19, ADR-0046.R19.N1

### Print profile

R622. `print_profile` (module `master_data`, DS-20; change-tracked; `CreatePrintProfile` and `UpdatePrintProfile`, effect class `master_data_change`) has one row for the company and optionally one per branch; a branch row's non-empty fields win over the company's. Columns: address (the keys of `partner_address`, ADR-0045.R8), phone, email, website, legal representative's name and title, chief accountant's name (both names labeled `personal`, spec 17), bank details printed as text, and the attachment IDs of a logo, a seal image and a signature image. `company` holds legal name, tax ID and language; `branch` holds name, tax ID and address.
Source: ADR-0049.R26

R623. Print profile images are PNG or JPEG attachments labeled `internal`. Only the `owner` role template holds `UpdatePrintProfile` (DS-15), on the leaf `print_profile` under area `master_data`. The contract leaves the seal and signature images empty when the subject has a marker (ADR-0049.R28), so a draft never carries them.
Source: ADR-0049.R26

R624. Prints show the printed names of the preparer and approver (ADR-0049.R25), as accounting law asks for a preparer and an approver (spec 03 rule 6).
Source: ADR-0049.R26

R625. Digital signatures on PDFs come later (open question).
Source: ADR-0049.R26

R626. The print of an e-invoiced document is not the legal e-invoice, which the provider issues (DS-24). The print shows the e-invoice data from ADR-0049.R25 once accepted.
Source: ADR-0049.R26

### Contact normalization

R627. DS-20's contact commands (`CreateContact`, `UpdateContact`; ADR-0019.R8; ADR-0045) and the commands of ADR-0052 normalize what matching compares. E-mail addresses are trimmed and lowercased, with the domain in IDNA ASCII form. An address that does not parse fails with `validation_failed`. DS-20's check on `contact.email` (`ck_contact_email_lower`) refuses an address that is not lowercase.
Source: ADR-0052.R4

R628. Phones are normalized to E.164 by the package's phone rule, with the company's country as default. Like tax ID rules, the phone rule is flagged until verified (ADR-0019.R4; ADR-0016.R5). Without a package rule, the core accepts only numbers already in E.164 form.
Source: ADR-0052.R4

R629. Names are normalized for search as ADR-0052.R17 says.
Source: ADR-0052.R4

### Partner kind

R630. The `partner_kind` value for an unincorporated business that is not registered as an enterprise, whose identifiers (tax ID, address) are its owner's, is `sole_proprietorship`; DS-20's `ck_partner_kind` allows it, and ADR-0019's rules use the term.
Source: ADR-0053.R7

R631. Labels are `personal` when `partner_kind` is `individual` or `sole_proprietorship`.
Source: ADR-0053.R7

R632. A localization package maps its national partner forms to `partner_kind` (a registered enterprise maps to `organization`) and names the value through its terminology key `enum.partner_kind.sole_proprietorship` (ADR-0040.R15). `l10n_vn`'s mapping, its legal form `private_enterprise` and its name are flagged package content of the localization package.
Source: ADR-0053.R7

### Departments, teams and employees

R633. Departments, teams and employees are `master_data`, `master_data_change`, change-tracked and `human_only`, because they change access. `department`: `code`, `name`, optional `parent_id` (a tree; a cycle is refused with `department_cycle`), optional `manager_partner_id` (an active employee), `is_active`.
Source: ADR-0054.R6

R634. `team`: `code`, `name`, optional `department_id`, and members in `team_member` (employee partners). Teams are optional, for example a sales team across departments.
Source: ADR-0054.R6

R635. `employee_profile` has `department_id` and `manager_partner_id`, the employee's manager. The chain of managers must not loop (`employee_manager_cycle`). A user's position in a company is the employee profile whose `user_account_id` is that user. `user_account_id` is unique per company, so a user who works for two companies can be an employee of both. A user without an employee profile can own documents only as their creator (ADR-0054.R14).
Source: ADR-0054.R6

R636. Commands `CreateDepartment`, `UpdateDepartment`, `CreateTeam`, `UpdateTeam` (with its members) and `UpdateEmployeeOrganization` (an employee's `department_id`, `manager_partner_id` and `user_account_id`) are on the leaf `organization` and need level `full` (ADR-0054.R8's minimum level), because each can widen someone's owner scope. Queries: `ListDepartment`, `ListTeam`.
Source: ADR-0054.R6

R637. `UpdateEmployeeOrganization` is the only command that changes these `employee_profile` columns. `CreatePartner` and `UpdatePartner` (DS-20) leave them unchanged and refuse a payload that names them, and so does a change proposal that targets them (ADR-0029), with `employee_organization_command_required`. `INV-228` checks it.
Source: ADR-0054.R6

R638. Each of these commands computes the caller's organization resolver result (ADR-0054.R2: their employee, their teams' employees and the employees under them) before and after the change, in its own transaction. If it differs, the command is refused with `organization_self_change` (ADR-0017.R6). This catches every route: naming the caller as someone's manager, moving employees into the caller's department, reparenting a department under one the caller manages, joining a team, or linking a profile.
Source: ADR-0054.R6

R639. A caller whose assignments in force all have owner scope `company` is exempt from `organization_self_change`, since nothing can widen for them; so a sole owner can link their own employee profile.
Source: ADR-0054.R6

### Multi-UoM scope and the inventory unit

R640. Multi-UoM keeps ADR-0018's inventory unit and exact conversions and extends them to inexact factors, units that differ along a document chain, and variants that convert differently; conversions are defined on the item master (`product_uom`, resolved item, then product, then `uom_conversion`). Catch weight, batch-specific factors, an order price unit, handling-unit quantities, packaging dimensions, sales multiples and quantity-based taxes come after Phase 1.
Source: ADR-0056.D0

R641. A product's inventory unit (ADR-0018.R9) is the only unit of:
   - stock quantities, material document lines, stock values and costing layers;
   - preliminary and actual prices per unit;
   - reservations, warehouse task quantities, demand and supply rows and their open quantities;
   - MRP netting, planned order quantities, planned order components and pegging;
   - GR/IR positions, receipt and match tolerances, and correction limits.
   Every conversion from another unit happens in the command layer, when a line is taken in. Costing, planning and GR/IR never see another unit.
   Source: ADR-0056.R1

### Units

R642. `uom` has `name` and `is_active`. Core units are the catalog `catalogs/units.csv` (owner DS-20), seeded from UN/ECE Recommendation 20: piece (`H87`), set (`SET`), kilogram (`KGM`), gram (`GRM`), tonne (`TNE`), metre (`MTR`), centimetre (`CMT`), millimetre (`MMT`), square metre (`MTK`), cubic metre (`MTQ`), litre (`LTR`), millilitre (`MLT`), hour (`HUR`), minute (`MIN`) and day (`DAY`). Their `id` is uuid5 of `uom:<code>` (ADR-0006.R4). Their `name` is the English name; the core i18n catalog translates it (`uom.<code>.name`), the Vietnamese UI translation included, as for other UI strings (ADR-0016.R18; ADR-0053.R16).
Source: ADR-0056.R2

R643. Packaging and trade units (box, carton, pallet, bag, roll, can) are company units, coded `x-` (for example `x-carton`), because their size differs per product. Their name is the company's text, translated through `data_translation` (ADR-0018.R17).
Source: ADR-0056.R2

R644. Decimal places stay one value per unit, global, at most 6, and never change once the unit is used (ADR-0018.R8). The catalog gives kilogram, metre, square metre and litre 3 decimals, tonne and cubic metre 6, gram, millimetre and millilitre 0, centimetre 1; the mass, length and volume pairs are then exact in both directions (ADR-0056.R7). Of the time pairs only day to hour is exact (toward the smaller unit); hour and minute, and day and minute, are inexact both ways.
Source: ADR-0056.R2

R645. A localization package may supply statutory names of the core units for its regime's statutory outputs (e-invoice lines, statutory prints), as terminology keys `uom.<code>.name` read from its file `i18n/<language>/unit_names.csv`, one row per core unit with its basis (ADR-0016.R5, ADR-0016.R6, ADR-0016.R18). Statutory outputs take the package's name when present, else the core translation, as the regime setting `documents.unit_name_source` (`statutory_then_translation`, the default, or `translation`) chooses (ADR-0056.R18, ADR-0063.R23). The core holds no country's statutory unit names; `l10n_vn`'s draft file is DS-19's. The regime settings `documents.e_invoice_unit_code_scheme` (`unece_rec20_21`, the default, or `none`) and `documents.unit_name_max_length` (unset: no limit) complete it (ADR-0063.R23).
Source: ADR-0056.R2, ADR-0056.R2.N1

R646. `is_active` false retires a unit: no new product unit, price entry, supplier order unit, product default unit or source line may name it. History keeps it.
Source: ADR-0056.R2

### Global conversions

R647. `uom_conversion` is a core catalog, `catalogs/unit-conversions.csv` (owner DS-20), between core units of one kind. Each pair is stored once, from the larger unit, so its factor is at least 1 (1 `KGM` = 1000/1 `GRM`). The inverse is derived, never stored. The database refuses a second row for the same pair in either direction.
Source: ADR-0056.R3

R648. A global conversion is found only as a stored pair or its inverse, never through a third unit; gram to tonne needs its own row.
Source: ADR-0056.R3

R649. Each `uom_conversion` row has a surrogate `id`, uuid5 of `uom_conversion:<from code>:<to code>`, so a line's trace can name it (ADR-0006.R1). Rows are immutable once used. `is_active` false retires one; a retirement is a catalog version. A retired pair is never replaced by another factor: uniqueness holds over all rows of a pair, and its deterministic `id` stays unique. Only product units retire and replace on the same unit (R661).
Source: ADR-0056.R3

R650. Company units never appear in `uom_conversion` (ADR-0018.R8).
Source: ADR-0056.R3

### Product units

R651. `product_uom` lists every other unit of a product: a surrogate `id` (ADR-0006.R1), `company_id`, `product_id`, optional `item_id`, `uom_id`, with at most one active row per (company, product, item, unit), a null item counting as one value; retired rows of the same unit stay for history.
Source: ADR-0056.R4

R652. A `product_uom` row with `item_id` set is an item's own unit for one variant or configured item. The item must be one of the product's items; the database holds it. Configured items created on order (ADR-0046.R11) get no item rows automatically; a person adds them.
Source: ADR-0056.R4

R653. The factor is `numerator` and `denominator`, positive integers: 1 unit = numerator / denominator inventory units (ADR-0006.R11). `inventory_uom_id` repeats the product's inventory unit through a key to the product, so the database refuses a product unit that is the inventory unit itself.
Source: ADR-0056.R4

R654. `factor_source` is `stated` (a fixed conversion the company states, such as a carton of 24), `packaging` (computed at creation from the `contains` relation of ADR-0056.R15), `catalog` (the factor of a `uom_conversion` pair), or `nominal` (an approximation of a variable relation, the Phase 1 workaround of ADR-0056.R22).
Source: ADR-0056.R4

R655. `is_exact` is computed by the command at creation by ADR-0056.R7 and never entered.
Source: ADR-0056.R4

R656. Packaging and warehouse flags: `contains_uom_id`, `contains_quantity`, `is_counting_unit`, `is_default_pick_unit` (ADR-0056.R15).
Source: ADR-0056.R4

R657. Lifecycle: `created_at` (set once at insert), `recorded_at` (the last write, retirement included; ADR-0007.R9), `is_active` and `retired_at`. A row is in force from `created_at` until `retired_at` (R661; `INV-603`).
Source: ADR-0056.R4, ADR-0056.R4.N1

R658. A product unit may name a unit that converts to the inventory unit through `uom_conversion` only with the catalog's factor (`factor_source` `catalog`), else `uom_conversion_conflict`. Such a row never competes with the catalog; it holds the counting and pick flags of those units. Retiring a `catalog` row without a replacement blocks that catalog unit for the product (R670); this is how a company stops a catalog unit for one product.
Source: ADR-0056.R4

R659. Price entries, the product's `purchase_uom_id` and `sales_uom_id`, and `supplier_item.order_uom_id` may use any unit the item resolves by R669, catalog units included.
Source: ADR-0056.R4

R660. Every unit allowed for a serial-tracked product (its product and item rows and the catalog units it resolves) must be exact (ADR-0056.R7), else `serial_unit_not_exact`. With the inventory unit at 0 decimals this means a whole factor from a unit with 0 decimals.
Source: ADR-0056.R4

### Immutable once used; retire and replace

R661. A `product_uom` or `uom_conversion` row is immutable once any line, price entry, supplier item, barcode or bill of materials refers to it (`uom_conversion_in_use`). A row nothing refers to may still be corrected or deleted. To change a used conversion, the company retires the row (`is_active` false, `retired_at` set) and adds a new row for the same product, item and unit, in one command (`UpdateProductUom` with the replacement factor). Uniqueness holds among active rows only (R651).
Source: ADR-0056.R5

R662. `CreateProductUom` with `item_id`, for a unit the item already resolves at product level, supersedes the product row for that item only, with the same price-entry handling (for that item's entries), the same review list and the same `INV-603` handling.
Source: ADR-0056.R5

R663. Every line carries its own snapshot (ADR-0056.R9): existing lines keep the old factor, new lines resolve to the new one (R669), and a follow-on line of an open document in the source line's unit keeps the source's factor (ADR-0056.R11).
Source: ADR-0056.R5

R664. The replacement covers every price entry of the unit valid on or after the business date, at the replaced level: for a product-level row, the entries keyed to the product (configurable products) and those of its items, except items with their own active row for the unit; for an item-level row, that item's entries. An entry that started earlier is end-dated to the day before the business date; one that starts later is removed; one that starts on the business date refuses the command with `price_entry_starts_today` (ADR-0045.R7), so the remedy is to run the replacement on the next business date. Until new entries exist, the lookup falls back to the inventory unit's price × the new factor (ADR-0056.R16). There is no effective dating: the replacement takes effect when the command runs.
Source: ADR-0056.R5

R665. Active packaging rows of the same level whose `contains_uom_id` is the replaced unit, and the rows that contain those, up the hierarchy (pack, carton, pallet), are retired and replaced in the same command, each factor recomputed; otherwise the command is refused with `uom_packaging_inconsistent` (ADR-0056.R15).
Source: ADR-0056.R5

R666. The check result `product_uom_replaced` lists what names the unit but is kept: supplier items whose order unit it is, barcodes of the unit, active bill of materials component and output lines in the unit (their snapshot keeps the old factor until a new revision), `partner_item` rows with that unit, and product defaults in it, besides the price entries ended or removed.
Source: ADR-0056.R5

R667. A retired row never returns. No line needs the old factor from master data. The inventory unit never changes once used; the way out is a new product (ADR-0018.R13).
Source: ADR-0056.R5

R668. Retirement without replacement leaves the level with no active row, so new lines in that unit get `uom_retired` (R670). A retired row or unit takes no new uses (R646); a follow-on line that takes its source line's unit and snapshot (ADR-0056.R11) is not a new use, so open documents can be finished at the retired factor.
Source: ADR-0056.R5

### Resolution: `convert_quantity`

R669. `master_data.contract.convert_quantity(item, from_uom, to_uom)` is one pure function, used by every command, by `find_price` and by the queries. To the inventory unit, for a unit U of an item:
   - U is the inventory unit: factor 1/1, source `identity`;
   - else the item's active row for U (at most one exists): source `item`;
   - else the product's active row for U (item null): source `product`;
   - else a `uom_conversion` row (U, inventory unit), or (inventory unit, U) inverted, between core units of the same kind: source `global`;
   - else `uom_not_allowed`.
   Source: ADR-0056.R6

R670. A level that has rows for U but no active one stops the search with `uom_retired`. It never uncovers the level below, so retiring an item's own carton without a replacement does not switch that item to the product's carton. A level with a replacement resolves to its active row.
Source: ADR-0056.R6

R671. Between two units, the factor is the quotient of the two factors to the inventory unit, each resolved as in R669. The inventory unit is the item's own pivot, not a chain through the catalog.
Source: ADR-0056.R6

R672. The result of `convert_quantity` is the factor as a reduced fraction, its source (or the two sources), `is_exact` for the pair by ADR-0056.R7, and the row used (`product_uom.id` or `uom_conversion.id`) for the derivation trace (ADR-0027.R3).
Source: ADR-0056.R6

R673. Company units convert only through `product_uom` rows (ADR-0018.R8).
Source: ADR-0056.R6

## Invariants

| Invariant | Name | Check point | Statement | Protects |
| --- | --- | --- | --- | --- |
| `INV-113` | `configured_lines_complete` | `day`; first step pending (production core step) | Every non-draft line of a configurable product on a document of an `is_item_creating` type, and every stock document line of one, names a complete configuration and an item whose variant values equal the configuration's item-defining values; a non-draft quotation line names a complete configuration, and an item only when one with those values exists. | R619 |
| `INV-114` | `configuration_hash_matches` | `day`; first step pending | Every `product_configuration`'s `content_hash` equals the hash of its stored values. | R618 |
| `INV-115` | `structure_conditions_item_defining` | `day`; first step pending | Every component and operation condition and sizing of a product-level structure names only item-defining characteristics of its product. | R618 |
| `INV-228` | `employee_organization_by_own_command` | `day`; step 5 | Every recorded change of `employee_profile.department_id`, `manager_partner_id` or `user_account_id` belongs to an `UpdateEmployeeOrganization` audit record. | R637 |
| `INV-600` | `line_unit_snapshot_consistent` | `day`; step 5 | Every quantity line carries its unit block; its snapshot equals `convert_quantity` for its item and unit when the unit was set (the item row, the product row or the global pair then in force), or its source line's snapshot for a line in the source's unit; its inventory quantity is `round_quantity`(quantity x factor) in the line's mode, or the cumulative value of `INV-601`. | R669 |
| `INV-602` | `stock_only_in_inventory_unit` | `day`; step 3 | Every material document line's quantity equals its source document line's inventory quantity, and every stock, reservation, demand, supply and planned quantity is at its item's inventory unit decimals. | R641 |
| `INV-603` | `line_factor_in_force` | `day`; step 5 | Every line whose snapshot source is item or product carries the factor of the row in force for its item and unit when its snapshot was taken, at the level it names (an item row before the product row; a level with rows but none in force uncovers nothing; a row is in force from `created_at` until `retired_at`), unless it is a follow-on line keeping its source line's snapshot; no line, price entry, supplier item or product default names a retired company unit or global conversion after its retirement, with the same exemption. | R646, R657, R661, R670 |
| `INV-604` | `serial_units_exact` | `day`; step 2 | Every unit a serial-tracked product resolves (its product and item rows and catalog units) is exact, and every line of such a product has an exact snapshot. | R660 |
| `INV-605` | `product_units_classified` | `day`; step 2 | Every product unit's `is_exact` equals numerator x 10^dI divisible by denominator x 10^dE; a row names a catalog-convertible unit only with `factor_source` `catalog` and the catalog's factor; at most one row per product, item and unit is active; and every packaging row's factor equals `contains_quantity` times its contained unit's factor. | R651, R655, R658 |

## Edge cases

| ID | Case | Outcome | Rule |
| --- | --- | --- | --- |
| `EC-103` | `grams_through_catalog`: A product kept in kilograms is sold and delivered in grams through the core conversion, with no product unit; the lines snapshot source `global`. | `must_succeed` | R647, R669 |
| `EC-104` | `item_level_unit`: Two variants of one product have cartons of 24 and of 12; an order of the second variant in cartons converts by its item-level row. | `must_succeed` | R652, R669 |
| `EC-105` | `retired_unit`: A supplier changes its carton from 24 to 20: the carton row of 24 is retired and a carton row of 20 added on the same unit code; carton price entries are end-dated; a new order line in cartons converts at 20, while the receipt of an open order in cartons keeps its snapshot of 24. | `must_succeed` | R661, R663, R664 |

## Settings

None: the rules of this chunk own no setting key. They read the regime settings `documents.unit_name_source`,
`documents.e_invoice_unit_code_scheme` and `documents.unit_name_max_length` of `documents` (R645).

## Conflicts

CONFLICT ADR-0056.R4: a product unit row is in force from `created_at` until `retired_at`, not from `recorded_at`; the DDL carries both columns; governed by ADR-0056.R4.N1 (R657).
CONFLICT ADR-0056.R4.N1: the S2 closure note replaces the start of validity in the rule, in `INV-603` and in invariants.csv with `created_at`, since `recorded_at` moves on retirement (ADR-0007.R9); applied in R657.
CONFLICT ADR-0056.R2: the note confirms the statutory unit name design as standing and adds the regime settings of ADR-0063.R23; stated as decided in R645 per ADR-0056.R2.N1.
CONFLICT ADR-0046.R18: the note narrows the text of `INV-113` to item-creating document types and stock lines, with quotation lines naming an item only when one exists; R619 states the narrowed text per ADR-0046.R18.N1.

## Trace

| Source | Where |
| --- | --- |
| ADR-0046.R14 | ref: ADR-0046.R14 |
| ADR-0046.R14.N1 | ref: ADR-0046.R14.N1 |
| ADR-0046.R14.N2 | ref: ADR-0046.R14.N2 |
| ADR-0046.R14.N3 | ref: ADR-0046.R14.N3 |
| ADR-0046.R14.N4 | ref: ADR-0046.R14.N4 |
| ADR-0046.R14.N5 | ref: ADR-0046.R14.N5 |
| ADR-0046.R15 | R601-R606 |
| ADR-0046.R15.N1 | R607 |
| ADR-0046.R16 | R608-R610 |
| ADR-0046.R17 | R611-R614 |
| ADR-0046.R18 | R615-R620 |
| ADR-0046.R18.N1 | R619 |
| ADR-0046.R19 | R621 |
| ADR-0046.R19.N1 | R621 |
| ADR-0047.R2 | ref: ADR-0047.R2 |
| ADR-0047.R2.N1 | ref: ADR-0047.R2.N1 |
| ADR-0047.R2.N2 | ref: ADR-0047.R2.N2 |
| ADR-0047.R2.N3 | ref: ADR-0047.R2.N3 |
| ADR-0047.R2.N4 | ref: ADR-0047.R2.N4 |
| ADR-0047.R2.N5 | ref: ADR-0047.R2.N5 |
| ADR-0047.R2.N6 | ref: ADR-0047.R2.N6 |
| ADR-0047.R2.N7 | ref: ADR-0047.R2.N7 |
| ADR-0047.R8.N2 | ref: ADR-0047.R8.N2 |
| ADR-0047.R18 | ref: ADR-0047.R18 |
| ADR-0047.R18.N1 | ref: ADR-0047.R18.N1 |
| ADR-0047.R18.N2 | ref: ADR-0047.R18.N2 |
| ADR-0047.R18.N3 | ref: ADR-0047.R18.N3 |
| ADR-0047.R18.N4 | ref: ADR-0047.R18.N4 |
| ADR-0047.R18.N5 | ref: ADR-0047.R18.N5 |
| ADR-0048.R2 | ref: ADR-0048.R2 |
| ADR-0049.R7 | ref: ADR-0049.R7 |
| ADR-0049.R17.N1 | ref: ADR-0049.R17.N1 |
| ADR-0049.R24.N1 | ref: ADR-0049.R24.N1 |
| ADR-0049.R25 | ref: ADR-0049.R25 |
| ADR-0049.R25.N1 | ref: ADR-0049.R25.N1 |
| ADR-0049.R25.N2 | ref: ADR-0049.R25.N2 |
| ADR-0049.R26 | R622-R626 |
| ADR-0050.R12 | ref: ADR-0050.R12 |
| ADR-0050.R12.N1 | ref: ADR-0050.R12.N1 |
| ADR-0050.R12.N2 | ref: ADR-0050.R12.N2 |
| ADR-0050.R12.N4 | ref: ADR-0050.R12.N4 |
| ADR-0050.R24.N2 | ref: ADR-0050.R24.N2 |
| ADR-0050.R25 | ref: ADR-0050.R25 |
| ADR-0050.R25.N1 | ref: ADR-0050.R25.N1 |
| ADR-0050.R27 | ref: ADR-0050.R27 |
| ADR-0050.R27.N1 | ref: ADR-0050.R27.N1 |
| ADR-0050.R27.N2 | ref: ADR-0050.R27.N2 |
| ADR-0050.R27.N3 | ref: ADR-0050.R27.N3 |
| ADR-0050.R27.N4 | ref: ADR-0050.R27.N4 |
| ADR-0050.R27.N5 | ref: ADR-0050.R27.N5 |
| ADR-0050.R51 | ref: ADR-0050.R51 |
| ADR-0050.R51.N1 | ref: ADR-0050.R51.N1 |
| ADR-0050.R51.N2 | ref: ADR-0050.R51.N2 |
| ADR-0050.R51.N4 | ref: ADR-0050.R51.N4 |
| ADR-0050.R55.N1 | ref: ADR-0050.R55.N1 |
| ADR-0051.R2 | ref: ADR-0051.R2 |
| ADR-0051.R8.N1 | ref: ADR-0051.R8.N1 |
| ADR-0051.R14 | ref: ADR-0051.R14 |
| ADR-0051.R14.N1 | ref: ADR-0051.R14.N1 |
| ADR-0051.R14.N2 | ref: ADR-0051.R14.N2 |
| ADR-0051.R15 | ref: ADR-0051.R15 |
| ADR-0051.R15.N1 | ref: ADR-0051.R15.N1 |
| ADR-0051.R15.N2 | ref: ADR-0051.R15.N2 |
| ADR-0051.R15.N3 | ref: ADR-0051.R15.N3 |
| ADR-0051.R15.N4 | ref: ADR-0051.R15.N4 |
| ADR-0051.R15.N5 | ref: ADR-0051.R15.N5 |
| ADR-0051.R20 | ref: ADR-0051.R20 |
| ADR-0051.R20.N1 | ref: ADR-0051.R20.N1 |
| ADR-0051.R20.N2 | ref: ADR-0051.R20.N2 |
| ADR-0051.R21 | ref: ADR-0051.R21 |
| ADR-0051.R21.N1 | ref: ADR-0051.R21.N1 |
| ADR-0052.R3 | ref: ADR-0052.R3 |
| ADR-0052.R4 | R627-R629 |
| ADR-0052.R15 | ref: ADR-0052.R15 |
| ADR-0052.R15.N1 | ref: ADR-0052.R15.N1 |
| ADR-0052.R15.N2 | ref: ADR-0052.R15.N2 |
| ADR-0052.R27 | ref: ADR-0052.R27 |
| ADR-0053.R3 | ref: ADR-0053.R3 |
| ADR-0053.R3.N1 | ref: ADR-0053.R3.N1 |
| ADR-0053.R3.N2 | ref: ADR-0053.R3.N2 |
| ADR-0053.R3.N3 | ref: ADR-0053.R3.N3 |
| ADR-0053.R4 | ref: ADR-0053.R4 |
| ADR-0053.R7 | R630-R632 |
| ADR-0053.R8 | ref: ADR-0053.R8 |
| ADR-0053.R8.N1 | ref: ADR-0053.R8.N1 |
| ADR-0053.R14 | ref: ADR-0053.R14 |
| ADR-0054.D0 | ref: ADR-0054.D0 |
| ADR-0054.R1 | ref: ADR-0054.R1 |
| ADR-0054.R6 | R633-R639 |
| ADR-0054.R7 | ref: ADR-0054.R7 |
| ADR-0054.R7.N2 | ref: ADR-0054.R7.N2 |
| ADR-0054.R9 | ref: ADR-0054.R9 |
| ADR-0054.R11 | ref: ADR-0054.R11 |
| ADR-0054.R11.N4 | ref: ADR-0054.R11.N4 |
| ADR-0054.R11.N6 | ref: ADR-0054.R11.N6 |
| ADR-0054.R11.N7 | ref: ADR-0054.R11.N7 |
| ADR-0054.R11.N8 | ref: ADR-0054.R11.N8 |
| ADR-0054.R11.N9 | ref: ADR-0054.R11.N9 |
| ADR-0054.R11.N10 | ref: ADR-0054.R11.N10 |
| ADR-0054.R13 | ref: ADR-0054.R13 |
| ADR-0054.R14 | ref: ADR-0054.R14 |
| ADR-0054.R14.N1 | ref: ADR-0054.R14.N1 |
| ADR-0054.R15 | ref: ADR-0054.R15 |
| ADR-0054.R15.N1 | ref: ADR-0054.R15.N1 |
| ADR-0054.R21 | ref: ADR-0054.R21 |
| ADR-0054.R21.N1 | ref: ADR-0054.R21.N1 |
| ADR-0054.R24 | ref: ADR-0054.R24 |
| ADR-0054.R24.N2 | ref: ADR-0054.R24.N2 |
| ADR-0054.R24.N3 | ref: ADR-0054.R24.N3 |
| ADR-0054.R25 | ref: ADR-0054.R25 |
| ADR-0054.R25.N1 | ref: ADR-0054.R25.N1 |
| ADR-0054.R25.N2 | ref: ADR-0054.R25.N2 |
| ADR-0054.R25.N3 | ref: ADR-0054.R25.N3 |
| ADR-0054.R26 | ref: ADR-0054.R26 |
| ADR-0054.R26.N1 | ref: ADR-0054.R26.N1 |
| ADR-0055.R4 | ref: ADR-0055.R4 |
| ADR-0055.R4.N1 | ref: ADR-0055.R4.N1 |
| ADR-0055.R7 | ref: ADR-0055.R7 |
| ADR-0055.R7.N1 | ref: ADR-0055.R7.N1 |
| ADR-0055.R7.N2 | ref: ADR-0055.R7.N2 |
| ADR-0055.R7.N3 | ref: ADR-0055.R7.N3 |
| ADR-0055.R7.N4 | ref: ADR-0055.R7.N4 |
| ADR-0055.R9 | ref: ADR-0055.R9 |
| ADR-0056.D0 | R640 |
| ADR-0056.R1 | R641 |
| ADR-0056.R2 | R642-R646 |
| ADR-0056.R2.N1 | R645 |
| ADR-0056.R3 | R647-R650 |
| ADR-0056.R4 | R651-R660 |
| ADR-0056.R4.N1 | R657 |
| ADR-0056.R5 | R661-R668 |
| ADR-0056.R6 | R669-R673 |
