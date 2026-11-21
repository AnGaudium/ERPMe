Module: master_data    Chunk: 1 of 8    Source ADRs: ADR-0007, ADR-0011, ADR-0015, ADR-0016, ADR-0018, ADR-0019
Build step(s): 0, 1, 2, 6    Generated from index: 30d5706    Compiled by: Claude Opus 5.5, 2026-11-21

# Compiled spec: `master_data`, chunk 1

## Purpose

`master_data` owns the company data that documents, stock and journal lines refer to: companies, currencies, groups,
products and items, units of measure, barcodes, classifications, translations and partners with their roles and profiles
(ADR-0022.R2). It sits in layer 3 and owns no balances or postings. This chunk states the company's time zone and
localization package, the currency catalog, valuation classes and item groups, the partner reconciliation accounts, the
product and item model (ADR-0018) and the partner core (ADR-0019 rules 1 to 4). Units of other modules met in this part of
the dossier are traced `ref:` and not restated.

## Entities and tables

DDL: `docs/design/DS-20-master-data.sql`.

| Table | Meaning | Key | Parent | Owner |
| --- | --- | --- | --- | --- |
| `currency` | ISO 4217 currencies, global (R3) | `code` | none | `master_data` |
| `company_currency_activation` | The currencies a company activates (R3) | `id`; unique (`company_id`, `currency`) | `company` | `master_data` |
| `valuation_class` | Groups stock items for inventory accounts (R4) | `id`; unique (`company_id`, `code`) | `company` | `master_data` |
| `item_group` | Groups items for revenue, cost of goods sold and consumption accounts (R5) | `id`; unique (`company_id`, `code`) | `company` | `master_data` |
| `item_tax_group` | Tax nature of products, read by the tax matrix (R31) | `id`; unique (`company_id`, `code`) | `company` | `master_data` |
| `partner_tax_status` | What a partner is for tax (R31, R36) | `id`; unique (`company_id`, `code`) | `company` | `master_data` |
| `product` | Fields shared by all variants (R11, R14) | `id`; unique (`company_id`, `code`) | `company` | `master_data` |
| `item` | One sellable, stockable variant, the SKU (R12, R17) | `id`; unique (`company_id`, `code`); unique (`product_id`, `variant_key`) | `product` | `master_data` |
| `variant_attribute` | Company attributes such as color or size, mode `variant` or `line_option` (R19) | `id`; unique (`company_id`, `code`) | `company` | `master_data` |
| `variant_attribute_value` | Values of an attribute (R19) | `id`; unique (`variant_attribute_id`, `code`) | `variant_attribute` | `master_data` |
| `product_variant_attribute` | The attributes of a product, with `position` (R19) | `id`; unique (`product_id`, `variant_attribute_id`) | `product` | `master_data` |
| `item_variant_value` | An item's value per variant attribute of its product (R19) | `id`; unique (`item_id`, `variant_attribute_id`) | `item` | `master_data` |
| `uom` | Units: core rows (`company_id` null) and company units (R22) | `id` | `company` (company units) | `master_data` |
| `item_barcode` | One barcode per packaging unit of an item (R28, R29) | `id`; unique (`company_id`, `barcode`) | `item` | `master_data` |
| `handling_unit_type` | Physical container types of a company, with tare weight and dimensions (ADR-0023.R6) | `id`; unique (`company_id`, `code`) | `company` | `master_data` |
| `classification_scheme` | Company classification schemes, `product_line` protected (R30) | `id`; unique (`company_id`, `code`) | `company` | `master_data` |
| `classification_value` | Values of a scheme, optional parent (R30) | `id`; unique (`classification_scheme_id`, `code`) | `classification_scheme` | `master_data` |
| `product_classification` | One value per scheme per product (R30) | `id`; unique (`product_id`, `classification_scheme_id`) | `product` | `master_data` |
| `product_category` | The built-in hierarchy that proposes product defaults, with the defaults a new product takes (R30, R405) | `id`; unique (`company_id`, `code`) | `company`; `product_category` (parent) | `master_data` |
| `data_translation` | Names of company data in other languages (R33) | `id`; unique (`company_id`, `table_name`, `row_id`, `field`, `language`) | `company` | `master_data` |
| `partner` | Every party the company deals with (R36) | `id`; unique (`company_id`, `code`) | `company`; `parent_partner_id` | `master_data` |
| `partner_role` | A partner's roles (R38) | `id`; unique (`partner_id`, `role`) | `partner` | `master_data` |
| `customer_profile` | Data of the `customer` role (R39) | `id`; `partner_id` unique | `partner` | `master_data` |
| `supplier_profile` | Data of the `supplier` role (R39) | `id`; `partner_id` unique | `partner` | `master_data` |
| `employee_profile` | Data of the `employee` role (R39) | `id`; `partner_id` unique | `partner` | `master_data` |

Named by the rules of this chunk, with rows in other chunks: `company`, `uom_conversion`, `product_uom`, `partner_group`,
`barcode` (the company's barcode registry), `external_id_map`, `tax_treatment`, `partner_item`, `custom_field_definition`.

Reads: `account` (ledger), `account_determination` (ledger), `module_activation` (registry), `open_item`, `document_line_tax` (tax), `setting_value`.

## Commands and queries

| Name | Actor and authorization | Input | Effect | Events | Error codes |
| --- | --- | --- | --- | --- | --- |
| `CreateCompany` | not stated | The company with its localization package and regime | Records `company.localization_package` and `company.accounting_regime` (R2) | not stated | not stated |
| `CreateItem` | leaf `product` (catalog), verb level edit | A product and a chosen combination of variant values | Creates an item for that combination (R20) | not stated | not stated |
| `EvaluateBarcode` | leaf `general_access` at read (catalog) | A scan | Resolves the scan (R29) | not stated | not stated |

Commands of these rules with rows in other chunks: `CreatePartner` and `UpdatePartner` (chunk 3; R6, R7, R40), and
`CreateItemBarcode`, `UpdateItemBarcode` and `DeleteItemBarcode` (chunk 7; R29).

Commands of other modules that these rules name: `TransferPartnerOpenItems` (ADR-0026.R12), `ActivateModule` for `ledger`
(R7), `UpdateCompanyRegimeOption` (ADR-0016.R11.N1).

Contract function, not a command: `master_data.contract.convert_quantity` resolves a unit (R24).

Codes of this chunk bound to no named command: `quantity_rounds_to_zero` (R25), `serial_unit_not_exact` (R23),
`uom_conversion_conflict` (R24), `uom_conversion_in_use` (R27), `uom_packaging_inconsistent` (R28); check results
`quantity_rounded` and `unit_inexact` (R25), `product_uom_replaced` (R27); response field `proposed_uom_source` (R26).

Authorization leaves owned by `master_data` that name this chunk's data: `partner`, `product`, `product_unit`,
`master_data_group`, `organization` (catalog `authorization-areas.csv`).

## Rules

### Company and currency

R1. Each company has `time_zone`, an IANA name such as `Asia/Ho_Chi_Minh`, validated against `zoneinfo.available_timezones()`. Aliases such as `Asia/Saigon` are valid; code compares time zones only by converting, never by name. It is used only to turn an instant into that company's business date. Branches use their company's time zone.
Source: ADR-0007.R12

R2. A company uses exactly one localization package and one of its regimes, chosen when the company is created (`CreateCompany`); `company.localization_package` and `company.accounting_regime` record them. Changing regime later is out of scope for Phase 1.
Source: ADR-0016.R2

R3. `currency` is a global table loaded from ISO 4217: `code`, `minor_unit`, `rounding_mode` (ADR-0006.R14, ADR-0006.R17) and `is_active`. A company activates the currencies it uses, as rows of `company_currency_activation`.
Source: ADR-0011.R7

### Groups for account determination

R4. A `valuation_class` is company data (`company_id`, `code`, `name`, `is_active`, and `basis` of ADR-0045.R12) that groups stock items for inventory accounts (merchandise, raw materials, finished goods), seeded from the regime template (DS-19). Each stock item has one valuation class (DS-20); an item without stock has none.
Source: ADR-0015.R6

R5. An `item_group` is company data that groups items for revenue, cost of goods sold and consumption accounts (spec 05: "item group"), seeded from the regime template the same way. Each item has one item group (DS-20).
Source: ADR-0015.R7

R6. The partner keys `receivable_reconciliation` and `payable_reconciliation` read the partner's own `receivable_account_id` or `payable_account_id` at posting (DS-20), as SAP stores the reconciliation account on the business partner. Their `account_determination` rows, by `partner_group_id`, only give new partners their default; `CreatePartner` and `UpdatePartner` check the partner's accounts against ADR-0015.R4. Changing the account of a partner with open items moves the items by `TransferPartnerOpenItems` (ADR-0026.R12). Customer and supplier advances use the same account and are told apart per open item (ADR-0010.R15).
Source: ADR-0015.R11

R7. In the CRM-only deployment profile (ADR-0052.R1) `customer_profile.receivable_account_id` and `supplier_profile.payable_account_id` are nullable, so that profile holds customers and suppliers without accounts. They are required while module `ledger` is activated for the company (`module_activation`): the partner commands fill an empty account from the defaults of R6 or fail with `account_determination_missing`, `ActivateModule` for `ledger` does the same for existing profiles, and `INV-38` checks the result; the database does not hold it.
Source: ADR-0015.R11.N1, ADR-0019.R3.N2

### Product and item model

R10. Goods and services are modeled at a product level and an item level. A `product` holds everything that must be the same for all its variants (product category, buyer, item group, valuation class, units of measure, lot or serial tracking, item tax group, price control); an `item` is one sellable, stockable variant: its code, variant values, barcodes, dimensions and weight. A product without variants has exactly one item; variants can be added later. Documents, stock and journal lines always refer to the item. Apart from `code` and `is_active`, a field lives on exactly one of the levels; nothing is inherited or overridden between them. Each product has one inventory unit and its own exact conversions for other units; document lines keep both their own quantity and the converted inventory quantity. Products are classified by company-defined classification schemes (product line is the first, seeded and protected), not by numbered analytic fields.
Source: ADR-0018.D0

R11. A `product` belongs to one company and has a `code` unique in the company, a `product_type` (`stock`: kept and valued in stock; `non_stock`: bought or sold but not kept in stock; `service`), `is_active`, `is_sellable` and `is_purchasable`.
Source: ADR-0018.R1

R12. An `item` belongs to one product (`product_id`, never changed) and company, and has a `code` unique in the company (the SKU) and `is_active`. An item can be used on a document only if both it and its product are active. A product without variants has one item, created with it and coded like it. Documents, stock movements, journal lines (ADR-0014) and prices refer to `item_id`, never to `product_id`. A draft line of a product with `is_item_created_on_order` may hold the product and its variant values until the document leaves draft (ADR-0045.R16). Lines of document types without `is_item_creating` (ADR-0047.R1), that is quotations, may leave draft without `item_id` when their variant values or configuration have no item yet: they hold the product with its variant values or its complete configuration, and name the item only when one already exists (found, never created). The item is created when the line is copied to a sales order and that order leaves draft (ADR-0045.R16; ADR-0046.R11). Every non-draft line of an `is_item_creating` type, and every stock document line, has `item_id`.
Source: ADR-0018.R2, ADR-0018.R2.N1

R13. A product or item proposed by an agent workflow carries no code in its proposal; the executing command issues it from the company's `code_series` row of record kind `product` (without fiscal year or branch), skipping codes in use. Its name is generated from its category and attributes (ADR-0062.R9).
Source: ADR-0018.R2.N2

R14. Fields on the product (the same for every variant): `product_category_id`, `buyer_id` (the employee responsible for purchasing it, a partner with the `employee` role), `item_group_id` (ADR-0015), `valuation_class_id` (required for `stock`, empty otherwise; ADR-0015), `inventory_uom_id`, `purchase_uom_id`, `sales_uom_id` (R23 to R27), `tracking` (`none`, `lot`, `serial`), `item_tax_group_id` (R16, R31), `price_control` (R15), and `business_unit_id`, the default business unit of its items' profit-and-loss lines (ADR-0069). `catch_weight_uom_id` is reserved for catch weight after Phase 1 (spec 07) and stays out of command schemas until then. Warehouse fields on the product (`removal_strategy`, `storage_condition_id`, `default_handling_unit_type_id`) are ADR-0023.R3; `inspection_points` is the set of inspection points at which the product is inspected (ADR-0070.R2); the product has no field `is_inspection_required`.
Source: ADR-0018.R3, ADR-0018.R3.N1, ADR-0018.R3.N2

R15. `price_control` stays a product field with the one value `periodic_average` in Phase 1 (D6). The ADR written after Phase 1 for the standard-price option keys price control by item and valuation area (with the reserved `valuation_type`) and amends R14 and R34; this is the one statement of that granularity, to which the ADR-0020.R11 note and the DS-53 entries point. That ADR also decides between standard price with variance postings and no actual costing, and standard price with actual costing; a moving-average option stays outside periodic actual costing. No posted row stores price control, so that change is no migration of posted data.
Source: ADR-0018.R3.N3

R16. `item_tax_group_id` is optional on the product: empty means inherited from the product category chain and then the company default `tax.default_item_tax_group`, resolved live by `tax_effective_item_tax_group` (ADR-0041.R7). A product category's `default_item_tax_group_id` empty inherits from the parent category. Posted and drafted documents keep the group they used (R34), on `document_line_tax`.
Source: ADR-0018.R3.N4

R17. Fields on the item (may differ between variants): variant values (R20), barcodes (R28), and `length`, `width`, `height` with `dimension_uom_id`, `net_weight`, `gross_weight` with `weight_uom_id`, all optional and all for one inventory unit of the item, so landed cost can be allocated by weight (ADR-0021.R4). Volume is computed. Dimensions of packaging units (a carton's size) are not modeled in Phase 1.
Source: ADR-0018.R4

R18. An item's display name is its product's name followed by its variant values' names, in the language required (R33); items have no name of their own. A product's name in the company's language is its `name`; other languages are in `data_translation`.
Source: ADR-0018.R5

R19. A `variant_attribute` is company data (`code`, `name`, for example `color`, `size`) with `variant_attribute_value` rows. A product's attributes are rows of `product_variant_attribute` (`product_id`, `variant_attribute_id`, `position`); there is no limit on their number. An item's values are rows of `item_variant_value` (`item_id`, `variant_attribute_id`, `variant_attribute_value_id`), one per attribute of its product. Attributes have a mode: `variant` (this rule) or `line_option`, chosen on document lines without creating items (ADR-0045.R15). Characteristics may also be numbers in a range with a step; a number chosen for an item-defining characteristic becomes a value row at first use, so `variant_key` works unchanged (ADR-0046.R3).
Source: ADR-0018.R6

R20. Each item stores `variant_key`, the sorted list of its value IDs, unique within its product, so no two items have the same combination. An attribute can be added to a product at any time if every existing item is given a value for it in the same command; it can be removed only while the product has one item. Items are created for the combinations the user chooses (`CreateItem`), never for every combination automatically. Stock, cost and prices are per item, so adding variants never changes how the existing item's books were kept. A product may also create an item when a document line names a new combination (ADR-0045.R16).
Source: ADR-0018.R7

R21. Where other product data lives: HS code and country of origin are product fields `hs_code` and `country_of_origin` (ADR-0021.R13); shelf life and lot expiry dates are DS-09 (lots); supplier's and customer's own item codes, names and units are `partner_item` (DS-20 partner part); prices are DS-20 price lists, per item; reorder point, minimum order quantity, lead time and default warehouse are planning parameters per item and warehouse and supplier terms (ADR-0024.R1, ADR-0024.R2); manufacturer and brand are classification schemes; images and documents are attachments; kits and bills of materials are ADR-0033, which leaves products and items unchanged.
Source: ADR-0018.D1

### Units of measure

R22. `uom` is a core catalog (global; `id` by uuid5 from its code, ADR-0006.R4) of units with `code` (UN/ECE Recommendation 20 codes where one exists), `name`, `quantity_kind` (`count`, `mass`, `length`, `area`, `volume`, `time`), `decimal_places` (at most 6) and `is_active`, which retires a unit for new uses. A core unit's `name` is the English name in the core catalog `catalogs/units.csv`, seeded from UN/ECE Recommendation 20; names of core units are translated through the core catalogs. A company may add its own units as rows with its `company_id` (null for core units); their codes start with `x-`, which core codes never use, and their names are the company's text (user data, R33). Packaging units (carton, box, pallet) are company units, and company units convert to other units only through `product_uom`. `quantity_kind` and `decimal_places` never change once a unit is used. `uom_conversion` is the core catalog `catalogs/unit-conversions.csv` of exact conversions within one kind: surrogate `id`, `from_uom_id`, `to_uom_id`, `numerator`, `denominator` (one `from` unit equals `numerator / denominator` `to` units, ADR-0006.R11) and `is_active`; direct pairs are stored once from the larger unit, the inverse is derived, never chained, and a used row is immutable. Unit names in a national language are package data of the localization package, and unit text from partners and old systems maps through `uom_alias`.
Source: ADR-0018.R8, ADR-0018.R8.N1

R23. Each product has one inventory unit (`inventory_uom_id`; the spec's "stock unit"): stock quantities and costs are always in it, and conversion happens in the command layer when a document line is taken in, so costing never sees another unit. A product with `serial` tracking has an inventory unit of kind `count` with 0 decimal places, and every unit it resolves (its product and item rows and catalog units) must be exact at its decimals (`serial_unit_not_exact`), so serial counts equal inventory quantities.
Source: ADR-0018.R9, ADR-0018.R9.N1

R24. `product_uom` is the item master of conversions: the other units a product, or one item, may be bought, sold or counted in, each with an exact conversion to the inventory unit (`numerator`, `denominator`: 1 carton = 24/1 bottles for one product, 12/1 for another). It has a surrogate `id`, an optional `item_id` for an item's own unit (a variant or configured item), `inventory_uom_id` (held through a key to the product, so the inventory unit itself is refused), `factor_source`, `is_exact`, packaging and warehouse flags, `is_active` and `retired_at`; at most one active row per (company, product, item, unit). A document line may use the inventory unit or any unit the item resolves. `master_data.contract.convert_quantity` resolves a unit: the item's row, the product's row, then a `uom_conversion` pair or its inverse, never chained; a retired row stops the search. A product unit may name a unit that converts through `uom_conversion` only with the catalog's factor (`factor_source` `catalog`, else `uom_conversion_conflict`), so a product row and a global row never compete; such a row carries the unit's counting and pick flags. Rows are in force from `created_at` until `retired_at`.
Source: ADR-0018.R10, ADR-0018.R10.N1

R25. A document line stores its quantity and unit as entered, its quantity in the inventory unit, computed as `round_quantity(quantity × numerator / denominator, inventory unit)` (ADR-0006.R15), and its conversion snapshot, which it never re-reads. The rounding mode follows the use (ADR-0006.R15). A part of a source line entered in the source's unit takes `round((C + q) × f) − P`, the difference of rounded cumulative quantities, so parts that complete the line sum exactly to its inventory quantity; parts in other units convert on their own. When the conversion is not exact, the response carries the check result `quantity_rounded` with both values, and a line in an inexact or nominal unit returns the check result `unit_inexact`. A line whose inventory quantity rounds to zero, and a forward part whose cumulative value computes to zero or less, is rejected with `quantity_rounds_to_zero`. The line's amount is computed from its own quantity and price, never from the rounded quantity (ADR-0006.R19). A company therefore keeps stock in the smallest unit it sells or counts; a unit whose usual quantities fall below one inventory step is a master-data problem settled that way.
Source: ADR-0018.R11, ADR-0018.R11.N1

R26. `purchase_uom_id` and `sales_uom_id` are the units proposed on purchase and sales documents. They, and `supplier_item.order_uom_id`, may be any unit the item resolves, catalog units included. The proposed unit follows one order: the source line's unit, a scanned barcode's (for a GS1 variable-measure scan, the measure's unit, ADR-0056.R13.N1), the partner item's, the supplier item's order unit (purchasing), the product's purchase or sales unit, then the inventory unit; the response names its source in `proposed_uom_source`. A line may choose another allowed unit.
Source: ADR-0018.R12, ADR-0018.R12.N1

R27. The inventory unit cannot change once any document line, price list or stock posting uses it. A used `product_uom` or `uom_conversion` row is never changed or removed (`uom_conversion_in_use`). To change a pack size, the company retires the row and adds a new row for the same unit in one command: uniqueness holds among active rows only, existing lines keep their snapshots, new lines take the new factor, the unit's open price entries are end-dated, and supplier items and barcodes of the unit are listed for review (`product_uom_replaced`). Price list entries name their unit (ADR-0045.R3).
Source: ADR-0018.R13, ADR-0018.R13.N1

R28. `item_barcode` (`item_id`, `uom_id`, `barcode`, unique per company) gives each packaging unit its own barcode; a scanned barcode proposes its unit on the line, so scanning a carton barcode enters one carton, converted to the inventory unit. Packaging levels are product units with `contains_uom_id` and `contains_quantity`, checked against the factors (`uom_packaging_inconsistent`).
Source: ADR-0018.R14, ADR-0018.R14.N1

R29. `item_barcode.barcode` holds the normalized form: a GTIN as 14 digits with a valid check digit, or an internal code (one upper-case letter, then up to 47 of `A-Z 0-9 - . / _`), or, from a migration import or a person, an old system's legacy code (`is_legacy_barcode`). A trigger registers it in the company's barcode registry `barcode` as type `item_unit`, so no bin, handling unit, lot, serial or document of the company may hold the same code (`barcode_taken`). A removed barcode stays reserved for its item, which may take it back. Commands: `CreateItemBarcode` (with `generate: gtin13` or `gtin14` when the company has a GS1 generation prefix), `UpdateItemBarcode` (moves a barcode to the right item or unit) and `DeleteItemBarcode`. A scan resolves through `EvaluateBarcode`.
Source: ADR-0018.R14.N2

### Classification, tax groups, translations and changes

R30. Products are grouped for reporting by classification schemes: `classification_scheme` (company data: `code`, `name`, `is_hierarchical`, `is_protected`) with `classification_value` rows (`code`, `name`, optional parent), and `product_classification` (`product_id`, `classification_scheme_id`, `classification_value_id`), one value per scheme per product. Every company starts with the protected scheme `product_line`, which cannot be deleted. Every analytic grouping (brand, manufacturer, origin, segment) is a scheme, without a limit. A product's classification is its current one: reclassifying a product changes how all its history is grouped. `product_category` is the one built-in hierarchy, used to propose defaults when a product is created (item group, valuation class, item tax group, units); the defaults are copied into the product's own fields. Free-form typed fields (numbers, dates, texts) are user-defined fields, in Phase 1 as the custom fields of ADR-0074.R8 to ADR-0074.R12 (`custom_field_definition`, `custom_values` on `product` and `item`); a list-type user-defined field must not duplicate a classification scheme.
Source: ADR-0018.R15

R31. Each product has an effective item tax group: its own `item_tax_group_id`, or one inherited from its category chain or the company default (R16; ADR-0041.R7). Item tax groups are company data seeded by the localization package and named by nature, not rate; the list is a package template whose basis the author verifies (DS-19, DS-23). A company may also add its own tax codes, dated rates and matrix rows for its own groups through an approved change proposal (ADR-0041.R4). A partner has a `partner_tax_status` (what it is); a document's header and each line have a `tax_treatment` (what the transaction is), derived by rules and overridable by a person as a check result; no partner tax group exists on a document. The tax codes of a document line are proposed by the dated matrix of direction (sale or purchase) × treatment × item tax group in the localization package (ADR-0080.R1 to ADR-0080.R4), and the line is checked against it. Whether a line may carry a different tax code (a purchase line recording the rate on a supplier's e-invoice) is an open question for the author; interim, flagged: only lines taken from an external document may differ, and the difference is shown as a check result for review. Import duty and excise come from the customs declaration (DS-11), not from this matrix; import codes are entered on the customs declaration, not determined. Matrix, company rows and document taxes: ADR-0041.R3, ADR-0041.R6, ADR-0041.R7.
Source: ADR-0018.R16, ADR-0018.R16.N1, ADR-0018.R16.N2

R33. Names that users enter for company data in more than one language (product names and descriptions, variant attribute values, company units, classification values, `reason.name` and `custom_field_definition.label`) are rows of `data_translation` (`table_name`, `row_id`, `field`, `language`, `text`), one mechanism for all. These are user data, entered, not translated by the system. A print takes its language in this order: the render request, the document's `print_language`, the partner, then the company (ADR-0049.R27; ADR-0016.R19).
Source: ADR-0018.R17, ADR-0018.R17.N1, ADR-0018.R17.N2

R34. Fields that change how stock or books are kept (`product_type`, `tracking`, `valuation_class_id`, `price_control`) cannot be changed once the product has stock postings (the inventory unit follows R27); a change is made by creating a new product and moving stock by documents. Other fields can be updated at any time; posted documents keep what they recorded. A later ADR may allow a dated change of `price_control` at a period start after close; this rule is amended then (ADR-0025.R7).
Source: ADR-0018.R18

### Partners

R35. A partner is one record per company for every party the company deals with (customer, supplier, employee, lead later), with roles added over time, never converted, so history is never broken. Data that only one role needs lives in a profile per role. People are contacts of a partner. Personal data is labeled at field level, with labels that depend on the partner's kind where the law does, and anything unknown is treated as personal. Incoming email and notes become append-only interactions; business documents appear on the partner's timeline through a query, never copied; deterministic code matches emails and detects duplicates before any LLM is asked, and outside content never chooses whose data an agent may read; whatever an agent learns is visible, editable data with its run, never hidden memory; nothing leaves the company without a human or an explicit permission; the lawful basis of processing and data-subject requests are records. Rules that depend on law (tax ID formats, consent purposes, deadlines) are package rules, flagged until verified. Pipelines, opportunities and semantic search come after Phase 1.
Source: ADR-0019.D0

R36. A `partner` belongs to one company and has `code` (unique in the company), `name`, `legal_name`, `partner_kind` (`organization`, `sole_proprietorship`, `individual`; `ck_partner_kind`), `tax_id` (normalized, optional), `parent_partner_id` (for a dependent unit, such as a supplier's branch), `represents_company_id` (set when the partner is another company of the same installation, for intercompany open items, ADR-0010.R14), `country`, `partner_group_id` (ADR-0015 defaults), `partner_tax_status_id` (R31), `preferred_language` and `is_active`. `sole_proprietorship` is an unincorporated business not registered as an enterprise, whose identifiers are its owner's (ADR-0053.R7); the localization package maps its national legal forms and terms to these values. A partner referred to by a document is never deleted; it is deactivated.
Source: ADR-0019.R1, ADR-0019.R1.N2, ADR-0018.R16.N2

R37. A partner belongs to one company in Phase 1, and so do items and products. The seam for a group is distribution, not shared rows: a group key per record through `external_id_map` with the reserved source system `group` (ADR-0074.R7), and a later command that copies a master and keeps it in step across the companies of one installation.
Source: ADR-0019.R1.N1

R38. Roles are rows of `partner_role` (`partner_id`, `role`, `is_active`), with `role` one of `customer`, `supplier`, `employee` in Phase 1 (`lead` and `prospect` after Phase 1, spec 13). A partner may have no role yet (a contact's organization). Carriers, customs brokers and banks that invoice the company are suppliers; the tax authority is not a partner (tax payables carry no partner, ADR-0014.R10). A role is deactivated, never deleted, once used. Being a customer and a supplier at once is normal and allows netting.
Source: ADR-0019.R2

R39. Profiles hold the data of one role; the role of the document (sales, purchase, employee advance) selects the profile whose accounts and terms it uses:
- `customer_profile`: `receivable_account_id` (R6, R7), `payment_term_id` (ADR-0026.R5), `credit_limit` and its currency `credit_limit_currency`, `price_list_id`, `salesperson_id`, default `currency`, `minimum_remaining_shelf_life_days` (ADR-0023.R3); rules of DS-22 (credit limit) and DS-25 (terms).
- `supplier_profile`: `payable_account_id` (R7), `payment_term_id` (ADR-0026.R5), `buyer_id`, default `currency`, `price_list_id` and a working calendar `working_calendar_id` (ADR-0045.R2); rules of DS-22 and DS-25.
- Both customer and supplier profiles carry the defaults `payment_method_id`, `delivery_method_id`, `incoterm_code` and `incoterm_place`, all `master_data` references, so the profiles stay free of `cash` and `inventory`.
- `employee_profile`: `user_account_id` (optional), `receivable_account_id` for advances (`receivable_employee_advance`), `branch_id`, `cost_center_id` and `job_title` (ADR-0045.R11); rules of DS-25.
- Employees are partners so that advances to them are open items per person, and so that `salesperson_id` and `buyer_id` refer to partners with the `employee` role. Payroll is not in scope; whether salaries payable are tracked per employee is an open question.
Source: ADR-0019.R3, ADR-0019.R3.N1

R40. Tax IDs are normalized and validated by a rule of the localization package (format, check digit, the forms used by organizations, dependent units, sole proprietorships and individuals), flagged `unverified` until the author verifies it (ADR-0016). A second partner with a tax ID that another partner of the company already has is accepted with the warning `partner_duplicate_suspected` and a work item of kind `partner_duplicate_suspected` (ADR-0019.R19); head offices and their dependent units are exempt.
Source: ADR-0019.R4, ADR-0019.R4.N1

## Invariants

Statements are those of `invariants.csv`; this chunk holds the rows whose catalog source is a rule of this chunk.

| Invariant | Name | Check point | Statement | Protects |
| --- | --- | --- | --- | --- |
| `INV-38` | `partner_accounts_while_ledger_active` | day | While `module_activation` shows `ledger` active for a company, every `customer_profile` of the company has `receivable_account_id` and every `supplier_profile` has `payable_account_id`. | R7 |
| `INV-606` | `unit_of_own_company` | day | Every row that names a unit names a core unit (`company_id` null) or a unit of the row's own company. Query, empty when it holds, run for each single-column key to `uom` from a table with `company_id` (`pg_constraint`, `confrelid = uom`; `uom_conversion`, an installation table, aside): `SELECT t.id FROM <table> t JOIN uom u ON u.id = t.<column> WHERE u.company_id IS NOT NULL AND u.company_id IS DISTINCT FROM t.company_id`. The keys stay single-column because core units have no company (`gen_overview.COMPANY_KEY_ALLOWLIST`). | R22; ADR-0045.R13 |

## Conflicts

CONFLICT ADR-0018.R2: the later note ADR-0018.R2.N1 lets quotation lines of types without `is_item_creating` leave draft without `item_id`; R12 states that narrower requirement.
CONFLICT ADR-0018.R3.N2: ADR-0070.R2 replaces the warehouse field `is_inspection_required` with `inspection_points`; R14 states the current field set.
CONFLICT ADR-0018.R10: ADR-0018.R10.N1 (ADR-0056) removes the precedence of a product row over a global conversion; a product unit takes only the catalog factor, so R24 states that both never compete.
CONFLICT ADR-0018.R11: the fixed half away from zero mode is replaced by a rounding mode that follows the use, per ADR-0018.R11.N1 and ADR-0006.R15.N1; R25 states it.
CONFLICT ADR-0018.R12: ADR-0018.R12.N1 widens the proposed purchase and sales units to any unit the item resolves, catalog units included, and ADR-0056.R13.N1 makes a GS1 variable-measure scan propose the measure's unit instead of the barcode's; R26 states the later text.
CONFLICT ADR-0018.R15: user-defined fields (without custom tables) are no longer after Phase 1; ADR-0074.R8 to ADR-0074.R12 give them as custom fields (the ADR-0074 note on ADR-0058); R30 states it.
CONFLICT ADR-0018.R16: ADR-0080.R1 governs (folded in by ADR-0018.R16.N2): partner tax groups no longer exist; a partner has `partner_tax_status` (column `partner_tax_status_id`), a document and its lines a `tax_treatment`, and the matrix is direction × treatment × item tax group; the item tax group is the effective group of ADR-0018.R16.N1; R31 and R36 state it.
CONFLICT ADR-0018.R16.N1: the product's own `item_tax_group_id` becomes an effective group inherited from the category chain or company default (ADR-0041.R7); R31 and R16 state it.
CONFLICT ADR-0018.R16.N2: the partner tax group of partners and documents no longer holds; ADR-0080 rules 1 to 4 give `partner_tax_status` and `tax_treatment`, stated in R31 and R36.
CONFLICT ADR-0018.R17: the print language order of the rule is extended by ADR-0018.R17.N1 (ADR-0049.R27) to render request, document, partner, company; R33 states it.
CONFLICT ADR-0019.R1: column `partner_tax_group_id` is replaced by `partner_tax_status_id` under ADR-0080.R1 (folded in by ADR-0018.R16.N2), and `household_business` is renamed `sole_proprietorship` under ADR-0053.R7; R36 states the DDL values.
CONFLICT ADR-0019.R1.N2: the note confirms that the DDL check `ck_partner_kind` governs the partner kind values; R36 lists `organization`, `sole_proprietorship`, `individual`.
CONFLICT ADR-0019.R4: the open question whether duplicate tax IDs are refused is closed by the author's decision in ADR-0019.R4.N1 (accepted with a warning); R40 drops the open mark.
CONFLICT ADR-0019.R4.N1: this note turns the rule's open question into a decision (accept with warning and work item, head offices exempt), stated in R40.

## Trace

| Source | Where |
| --- | --- |
| ADR-0004.R12.N1 | ref: ADR-0004.R12.N1 |
| ADR-0004.R13 | ref: ADR-0004.R13 |
| ADR-0006.R1.N1 | ref: ADR-0006.R1.N1 |
| ADR-0006.R15 | ref: ADR-0006.R15 |
| ADR-0006.R15.N1 | ref: ADR-0006.R15.N1 |
| ADR-0006.R18 | ref: ADR-0006.R18 |
| ADR-0007.R9.N2 | ref: ADR-0007.R9.N2 |
| ADR-0007.R12 | R1 |
| ADR-0007.R15 | ref: ADR-0007.R15 |
| ADR-0007.R15.N1 | ref: ADR-0007.R15.N1 |
| ADR-0007.R15.N2 | ref: ADR-0007.R15.N2 |
| ADR-0007.R15.N3 | ref: ADR-0007.R15.N3 |
| ADR-0007.R15.N4 | ref: ADR-0007.R15.N4 |
| ADR-0007.R16 | ref: ADR-0007.R16 |
| ADR-0007.R16.N1 | ref: ADR-0007.R16.N1 |
| ADR-0007.R16.N2 | ref: ADR-0007.R16.N2 |
| ADR-0008.R1 | ref: ADR-0008.R1 |
| ADR-0008.R1.N1 | ref: ADR-0008.R1.N1 |
| ADR-0008.R1.N2 | ref: ADR-0008.R1.N2 |
| ADR-0008.R1.N3 | ref: ADR-0008.R1.N3 |
| ADR-0008.R1.N4 | ref: ADR-0008.R1.N4 |
| ADR-0008.R1.N5 | ref: ADR-0008.R1.N5 |
| ADR-0008.R7.N1 | ref: ADR-0008.R7.N1 |
| ADR-0009.R11 | ref: ADR-0009.R11 |
| ADR-0009.R11.N1 | ref: ADR-0009.R11.N1 |
| ADR-0010.R10 | ref: ADR-0010.R10 |
| ADR-0010.R12 | ref: ADR-0010.R12 |
| ADR-0010.R15.N1 | ref: ADR-0010.R15.N1 |
| ADR-0011.R7 | R3 |
| ADR-0012.R9 | ref: ADR-0012.R9 |
| ADR-0014.R5 | ref: ADR-0014.R5 |
| ADR-0014.R5.N1 | ref: ADR-0014.R5.N1 |
| ADR-0014.R5.N2 | ref: ADR-0014.R5.N2 |
| ADR-0015.R3 | ref: ADR-0015.R3 |
| ADR-0015.R3.N1 | ref: ADR-0015.R3.N1 |
| ADR-0015.R6 | R4 |
| ADR-0015.R7 | R5 |
| ADR-0015.R8 | ref: ADR-0015.R8 |
| ADR-0015.R8.N1 | ref: ADR-0015.R8.N1 |
| ADR-0015.R9 | ref: ADR-0015.R9 |
| ADR-0015.R11 | R6 |
| ADR-0015.R11.N1 | R7 |
| ADR-0016.R2 | R2 |
| ADR-0016.R8 | ref: ADR-0016.R8 |
| ADR-0016.R10 | ref: ADR-0016.R10 |
| ADR-0016.R10.N1 | ref: ADR-0016.R10.N1 |
| ADR-0016.R10.N2 | ref: ADR-0016.R10.N2 |
| ADR-0016.R11.N1 | ref: ADR-0016.R11.N1 |
| ADR-0016.R17.N1 | ref: ADR-0016.R17.N1 |
| ADR-0016.R17.N2 | ref: ADR-0016.R17.N2 |
| ADR-0017.R9.N2 | ref: ADR-0017.R9.N2 |
| ADR-0018.D0 | R10 |
| ADR-0018.R1 | R11 |
| ADR-0018.R2 | R12 |
| ADR-0018.R2.N1 | R12 |
| ADR-0018.R2.N2 | R13 |
| ADR-0018.R3 | R14 |
| ADR-0018.R3.N1 | R14 |
| ADR-0018.R3.N2 | R14 |
| ADR-0018.R3.N3 | R15 |
| ADR-0018.R3.N4 | R16 |
| ADR-0018.R4 | R17 |
| ADR-0018.R5 | R18 |
| ADR-0018.R6 | R19 |
| ADR-0018.R7 | R20 |
| ADR-0018.R8 | R22 |
| ADR-0018.R8.N1 | R22 |
| ADR-0018.R9 | R23 |
| ADR-0018.R9.N1 | R23 |
| ADR-0018.R10 | R24 |
| ADR-0018.R10.N1 | R24 |
| ADR-0018.R11 | R25 |
| ADR-0018.R11.N1 | R25 |
| ADR-0018.R12 | R26 |
| ADR-0018.R12.N1 | R26 |
| ADR-0018.R13 | R27 |
| ADR-0018.R13.N1 | R27 |
| ADR-0018.R14 | R28 |
| ADR-0018.R14.N1 | R28 |
| ADR-0018.R14.N2 | R29 |
| ADR-0018.R15 | R30 |
| ADR-0018.R16 | R31 |
| ADR-0018.R16.N1 | R31 |
| ADR-0018.R16.N2 | R31, R36 |
| ADR-0018.R17 | R33 |
| ADR-0018.R17.N1 | R33 |
| ADR-0018.R17.N2 | R33 |
| ADR-0018.R18 | R34 |
| ADR-0018.D1 | R21 |
| ADR-0019.D0 | R35 |
| ADR-0019.R1 | R36 |
| ADR-0019.R1.N1 | R37 |
| ADR-0019.R1.N2 | R36 |
| ADR-0019.R2 | R38 |
| ADR-0019.R3 | R39 |
| ADR-0019.R3.N1 | R39 |
| ADR-0019.R3.N2 | R7 |
| ADR-0019.R4 | R40 |
| ADR-0019.R4.N1 | R40 |
