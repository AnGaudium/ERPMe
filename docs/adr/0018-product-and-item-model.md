# ADR-0018: Product and item model

Status: accepted (2026-11-14) under ADR-0005, reviewed by Claude Fable 5.2. Design item: DS-20 (item part; partners, warehouses and price lists follow in DS-20 for step 2). Related decisions: D5, D6, D10. Principles 6, 7. ADR-0004, ADR-0005, ADR-0006, ADR-0010, ADR-0014, ADR-0015, ADR-0016.

## Decision

Goods and services are modeled at two levels: a `product` holds everything that must be the same for all its variants — product category, buyer, item group, valuation class, units of measure, lot or serial tracking, item tax group, price control — and an `item` is one sellable, stockable variant: its code, variant values, barcodes, dimensions and weight. A product without variants has exactly one item; variants can be added later. Documents, stock and journal lines always refer to the item. Apart from `code` and `is_active`, a field lives on exactly one level; nothing is inherited or overridden. Each product has one inventory unit and its own exact conversions for other units, as SAP keeps alternative units per material; document lines keep both their own quantity and the converted inventory quantity. Products are classified by any number of company-defined classification schemes (product line is the first, seeded and protected) instead of a fixed set of numbered analytic fields. Taxes are proposed and checked by a matrix of the product's item tax group and the partner's tax group, per direction, designed in DS-23. The design takes what fits NativeFlows's command-based, AI-read data model from Dynamics 365, SAP, Business One and Odoo, not their legacy shapes.

### Rules

**Products and items**

1. A `product` belongs to one company and has a `code` unique in the company, a `product_type` (`stock`: kept and valued in stock; `non_stock`: bought or sold but not kept in stock; `service`), `is_active`, `is_sellable` and `is_purchasable`.
2. An `item` belongs to one product (`product_id`, never changed) and company, and has a `code` unique in the company (the SKU) and `is_active`. An item can be used on a document only if both it and its product are active. A product without variants has one item, created with it and coded like it. Documents, stock movements, journal lines (ADR-0014) and prices refer to `item_id`, never to `product_id`. A draft line of a product with `is_item_created_on_order` may hold the product and its variant values until the document leaves draft; every non-draft line has `item_id` ([ADR-0045](0045-master-data-and-price-lists.md) rule 16).

   Note: lines of document types without `is_item_creating` ([ADR-0047](0047-commercial-documents-and-pricing.md) rule 1), that is quotations, may leave draft without `item_id` when their variant values or configuration have no item yet. They hold the product with its variant values or its complete configuration, and name the item only when one already exists (found, never created). The item is created when the line is copied to a sales order and that order leaves draft ([ADR-0045](0045-master-data-and-price-lists.md) rule 16; [ADR-0046](0046-product-configuration.md) rule 11). Every non-draft line of an `is_item_creating` type, and every stock document line, has `item_id`.

   Note ([ADR-0062](0062-product-engineering-workflow.md), proposed 2026-11-15): a product or item proposed by an agent workflow carries no code in its proposal; the executing command issues it from the company's `code_series` row of record kind `product` (without fiscal year or branch), skipping codes in use. Its name is generated from its category and attributes ([ADR-0062](0062-product-engineering-workflow.md) rule 9).
3. Fields on the product (the same for every variant): `product_category_id`, `buyer_id` (the employee responsible for purchasing it; employees are defined in DS-20), `item_group_id` (ADR-0015), `valuation_class_id` (required for `stock`, empty otherwise; ADR-0015), `inventory_uom_id`, `purchase_uom_id`, `sales_uom_id` (rules 9–13), `tracking` (`none`, `lot`, `serial`), `item_tax_group_id` (rule 16), `price_control` (`periodic_average`, the only value in Phase 1, D6). `catch_weight_uom_id` is reserved for catch weight after Phase 1 ([07](../spec/07-shared-foundation.md#units-of-measure)) and stays out of command schemas until then. Warehouse fields on the product (`is_inspection_required`, `removal_strategy`, `storage_condition_id`, `default_handling_unit_type_id`): [ADR-0023](0023-warehouse-management.md) rule 3.
4. Fields on the item (may differ between variants): variant values (rule 7), barcodes (rule 14), and `length`, `width`, `height` with `dimension_uom_id`, `net_weight`, `gross_weight` with `weight_uom_id`, all optional and all for one inventory unit of the item, so landed cost can be allocated by weight ([ADR-0021](0021-landed-cost.md) rule 4). Volume is computed. Dimensions of packaging units (a carton's size) are not modeled in Phase 1.
5. An item's display name is its product's name followed by its variant values' names, in the language required (rule 17); items have no name of their own, so a name is kept in one place. A product's name in the company's language is its `name`; other languages are in `data_translation`.

**Variants**

6. A `variant_attribute` is company data (`code`, `name`, e.g. `color`, `size`) with `variant_attribute_value` rows. A product's attributes are rows of `product_variant_attribute` (`product_id`, `variant_attribute_id`, `position`); there is no limit on their number. An item's values are rows of `item_variant_value` (`item_id`, `variant_attribute_id`, `variant_attribute_value_id`), one per attribute of its product. Attributes have a mode: `variant` (this rule) or `line_option`, chosen on document lines without creating items ([ADR-0045](0045-master-data-and-price-lists.md) rule 15).

   Characteristics may also be numbers in a range with a step; a number chosen for an item-defining characteristic becomes a value row at first use, so `variant_key` works unchanged ([ADR-0046](0046-product-configuration.md) rule 3).
7. Each item stores `variant_key`, the sorted list of its value IDs, unique within its product, so two items never have the same combination. An attribute can be added to a product at any time if every existing item is given a value for it in the same command; it can be removed only while the product has one item. Items are created for the combinations the user chooses (`CreateItem`), never for every combination automatically. Stock, cost and prices are per item, so adding variants never changes how the existing item's books were kept. A product may also create an item when a document line names a new combination ([ADR-0045](0045-master-data-and-price-lists.md) rule 16).

**Units of measure**

8. `uom` is a core catalog (global; `id` by uuid5 from its code, ADR-0006 rule 4) of units with `code` (UN/ECE Recommendation 20 codes where one exists), `quantity_kind` (`count`, `mass`, `length`, `area`, `volume`, `time`) and `decimal_places` (at most 6). A company may add its own units (e.g. "thùng") as rows with its `company_id` (null for core units); their codes start with `x-`, which core codes never use, so a later core unit cannot collide. Company units convert to other units only through `product_uom`. `quantity_kind` and `decimal_places` never change once a unit is used. Names of core units are translated through the core catalogs; names of company units are user data (rule 17). `uom_conversion` holds exact global conversions within one kind: `from_uom_id`, `to_uom_id`, `numerator`, `denominator`, meaning one `from` unit equals `numerator / denominator` `to` units (ADR-0006 rule 11).

   Note ([ADR-0056](0056-multiple-units-of-measure.md), proposed 2026-11-15): `uom` gains `name` (core units: the English name in the core catalog `catalogs/units.csv`, seeded from UN/ECE Recommendation 20; company units: the company's text) and keeps `is_active`, which retires a unit for new uses. `uom_conversion` is the core catalog `catalogs/unit-conversions.csv`: direct pairs stored once from the larger unit, the inverse derived, never chained, immutable once used, with a surrogate `id` and `is_active`. Packaging units (carton, box, pallet) are company units. Vietnamese unit names are `l10n_vn` package data, and unit text from partners and old systems maps through `uom_alias` (rules 2, 3, 19).
9. Each product has one inventory unit (`inventory_uom_id`; the spec's "stock unit"): stock quantities and costs are always in it, and conversion happens in the command layer when a document line is taken in, so costing never sees another unit ([07](../spec/07-shared-foundation.md#units-of-measure)). A product with `serial` tracking has an inventory unit of kind `count` with 0 decimal places.

   Note ([ADR-0056](0056-multiple-units-of-measure.md), proposed 2026-11-15): every unit a serial-tracked product resolves (its product and item rows and catalog units) must be exact at its decimals (`serial_unit_not_exact`), so serial counts equal inventory quantities (rule 4).
10. `product_uom` lists the other units a product may be bought, sold or counted in, each with an exact conversion to its inventory unit (`numerator`, `denominator`: 1 carton = 24/1 bottles for one product, 12/1 for another). A document line may use the inventory unit, a unit in `product_uom`, or a unit of the same kind convertible through `uom_conversion`; a `product_uom` row wins over `uom_conversion` for the same pair. Together these are the spec's "UoM group per item".

    Note ([ADR-0056](0056-multiple-units-of-measure.md), proposed 2026-11-15): `product_uom` is the item master of conversions. It gains a surrogate `id`, an optional `item_id` for an item's own unit (a variant or configured item), `inventory_uom_id` (held through a key to the product, so the inventory unit itself is refused), `factor_source`, `is_exact`, packaging and warehouse flags, `is_active` and `retired_at`; at most one active row per (company, product, item, unit). A unit is resolved by `master_data.contract.convert_quantity`: the item's row, the product's row, then a `uom_conversion` pair or its inverse, never chained; a retired row stops the search. A product unit may name a unit that converts through `uom_conversion` only with the catalog's factor (`factor_source` `catalog`, else `uom_conversion_conflict`), so a product row and a global row never compete; such a row carries the unit's counting and pick flags. Rows are in force from `recorded_at` until `retired_at` (rules 4–6).
11. A document line stores its quantity and unit as entered, and its quantity in the inventory unit, computed as `round_quantity(quantity × numerator / denominator, inventory unit)` (half away from zero, ADR-0006 rules 15, 17). When the conversion is not exact, the response carries the check result `quantity_rounded` with both values, so the user sees it; a line whose inventory quantity rounds to zero is rejected with `quantity_rounds_to_zero`; the line's amount is computed from its own quantity and price, never from the rounded quantity (ADR-0006 rule 19). A company therefore chooses as inventory unit the smallest unit it sells or counts.

    Note ([ADR-0056](0056-multiple-units-of-measure.md), proposed 2026-11-15): the line also stores its conversion snapshot and never re-reads it. A part of a source line entered in the source's unit takes `round((C + q) × f) − P`, the difference of rounded cumulative quantities, so parts that complete the line sum exactly to its inventory quantity; parts in other units convert on their own. The rounding mode follows the use, and a line in an inexact or nominal unit returns the check result `unit_inexact`. `quantity_rounds_to_zero` now also refuses a forward part whose cumulative value computes to zero or less; a unit whose usual quantities fall below one inventory step is a master-data problem, settled as this rule says by keeping stock in the finer unit (rules 7, 8, 10, 22).
12. `purchase_uom_id` and `sales_uom_id` are the units proposed on purchase and sales documents; each is the inventory unit or a unit in `product_uom`. A line may choose another allowed unit.

    Note ([ADR-0056](0056-multiple-units-of-measure.md), proposed 2026-11-15): the proposed unit follows one order: the source line's unit, a scanned barcode's, the partner item's, the supplier item's order unit (purchasing), the product's purchase or sales unit, then the inventory unit; the response names its source in `proposed_uom_source`. `purchase_uom_id`, `sales_uom_id` and `supplier_item.order_uom_id` may be any unit the item resolves, catalog units included (rules 4, 13).
13. The inventory unit cannot change, and a `product_uom` row cannot be removed or have its conversion changed, once any document line, price list or stock posting uses it (as SAP and Business One fix units once transactions exist). Price list entries name their unit ([ADR-0045](0045-master-data-and-price-lists.md) rule 3).

    Note ([ADR-0056](0056-multiple-units-of-measure.md), proposed 2026-11-15): a used `product_uom` or `uom_conversion` row is never changed or removed (`uom_conversion_in_use`). To change a pack size, the company retires the row and adds a new row for the same unit in one command (the `x-carton` row of 24 retired, an `x-carton` row of 20 active): uniqueness holds among active rows only, existing lines keep their snapshots, new lines take the new factor, the unit's open price entries are end-dated, and supplier items and barcodes of the unit are listed for review (`product_uom_replaced`) (rule 5).
14. `item_barcode` (`item_id`, `uom_id`, `barcode`, unique per company) gives each packaging unit its own barcode; scanning a carton barcode enters one carton, converted to the inventory unit.

    Note ([ADR-0056](0056-multiple-units-of-measure.md), proposed 2026-11-15): a scanned barcode proposes its unit on the line. Packaging levels are product units with `contains_uom_id` and `contains_quantity`, checked against the factors (`uom_packaging_inconsistent`) (rules 13, 15).

    Note ([ADR-0061](0061-barcodes.md), proposed 2026-11-15): `item_barcode.barcode` holds the normalized form: a GTIN as 14 digits with a valid check digit, or an internal code (one upper-case letter, then up to 47 of `A-Z 0-9 - . / _`), or, from a migration import or a person, an old system's legacy code (`is_legacy_barcode`). A trigger registers it in the company's barcode registry `barcode` as type `item_unit`, so no bin, handling unit, lot, serial or document of the company may hold the same code (`barcode_taken`). A removed barcode stays reserved for its item, which may take it back. Commands: `CreateItemBarcode` (with `generate: gtin13` or `gtin14` when the company has a GS1 generation prefix), `UpdateItemBarcode` (moves a barcode to the right item or unit) and `DeleteItemBarcode`. A scan resolves through `EvaluateBarcode` (rules 4, 7, 8, 10, 12).

**Classification and analytics**

15. Products are grouped for reporting by classification schemes: `classification_scheme` (company data: `code`, `name`, `is_hierarchical`, `is_protected`) with `classification_value` rows (`code`, `name`, optional parent), and `product_classification` (`product_id`, `classification_scheme_id`, `classification_value_id`), one value per scheme per product. Every company starts with the protected scheme `product_line`, which cannot be deleted, as the author asked for product line to be predefined; it is a scheme rather than a column so that every analytic grouping — brand, manufacturer, origin, segment — works the same way for users, reports and agents, without a limit, as Dynamics 365's category hierarchies do. A product's classification is its current one: reclassifying a product changes how all its history is grouped. `product_category` is the one built-in hierarchy, used to propose defaults when a product is created (item group, valuation class, item tax group, units); the defaults are copied into the product's own fields. Free-form typed fields (numbers, dates, texts) are user-defined fields, after Phase 1 ([07](../spec/07-shared-foundation.md#extensibility-and-upgrades)); a list-type user-defined field must not duplicate a classification scheme.

**Tax**

16. Each product has an `item_tax_group_id` (company data seeded by the localization package and named by nature, not rate, e.g. standard, standard eligible for a temporary reduction, reduced-rate goods, zero-rated, not subject; the list is a package template whose basis the author verifies, DS-19, DS-23). Each partner, and each document where it differs, has a partner tax group (DS-20; the role of Odoo's fiscal position). The tax codes of a document line are proposed by the dated matrix (direction: sale or purchase) × partner tax group × item tax group in the localization package (DS-23), and the line is checked against it. Whether a line may carry a different tax code — e.g. a purchase line recording the rate on a supplier's e-invoice — is an open question for the author; interim, flagged: only lines taken from an external document may differ, and the difference is shown as a check result for review. Import duty and excise come from the customs declaration (DS-11), not from this matrix. The item tax group list is DS-23's ([ADR-0039](0039-vietnam-package-tt99.md) rule 10). Matrix, company rows and document taxes: [ADR-0041](0041-tax-engine.md) rules 3, 6–7. Import codes are entered on the customs declaration, not determined.

**Names and lifecycle**

17. Names that users enter for company data in more than one language — product names and descriptions, variant attribute values, company units, classification values — are rows of `data_translation` (`table_name`, `row_id`, `field`, `language`, `text`), one mechanism for all. Printed documents use the partner's language and fall back to the company's language (ADR-0016 rule 19). These are user data, entered, not translated by the system.

    Note: the full order for prints: the render request, the document's `print_language`, the partner, then the company ([ADR-0049](0049-statutory-reporting-and-printing.md) rule 27).
18. Fields that change how stock or books are kept (`product_type`, `tracking`, `valuation_class_id`, `price_control`) cannot be changed once the product has stock postings (the inventory unit follows rule 13); a change is made by creating a new product and moving stock by documents. Other fields can be updated at any time; posted documents keep what they recorded. A later ADR may allow a dated change of `price_control` at a period start after close; this rule is amended then ([ADR-0025](0025-later-phase-seams.md) rule 7).

**Deliberately elsewhere**

| Data | Where |
| --- | --- |
| HS code, country of origin | Product fields `hs_code`, `country_of_origin` ([ADR-0021](0021-landed-cost.md) rule 13) |
| Shelf life, lot expiry dates | DS-09 (lots) |
| Supplier's and customer's own item codes, names and units (`partner_item`; needed by the purchase invoice agent's stored mappings, [14](../spec/14-agent-workflows.md)) | DS-20 partner part |
| Prices | DS-20 price lists, per item |
| Reorder point, minimum order quantity, lead time, default warehouse | Planning parameters per item and warehouse and supplier terms ([ADR-0024](0024-planning.md) rules 1, 2); the building phase is the author's decision |
| Manufacturer, brand | Classification schemes |
| Images and documents | Attachments; owner to be assigned (no backlog item yet) |
| Kits and bills of materials | Phase 2; now Phase 1, designed in DS-51 ([ADR-0032](0032-phase-1-scope-with-production.md)): [ADR-0033](0033-production-master-data.md), which leaves products and items unchanged |

## Context

The item model is needed by DS-09 (inventory and costing), DS-08 (valuation class and item group), DS-11 (landed cost by weight), DS-22 (documents) and DS-23 (tax), and must leave room for bins and catch weight. Constraints:

- UoM group per item with stock, purchase and sales units and fixed item-specific factors; stock and cost always in the stock unit, conversion in the command layer; rounding never silently in cost; barcode per packaging unit; lots and serials with no cost of their own; price control per item, periodic weighted average in Phase 1 ([07](../spec/07-shared-foundation.md#units-of-measure), [05](../spec/05-accounting-inventory-core.md), D6). Catch weight and bins after Phase 1, reserved now. User-defined fields after Phase 1 (07).
- ADR-0006 rules 11, 14, 19 (exact conversions; rounding of converted quantities delegated to DS-20); ADR-0015 (valuation class and item group).
- The author asked for category, product line, buyer, tax, length, width, height and weight; an opinion on predefined analytic fields; product and variant structure; inventory, purchase and sales units; taxes always as a matrix of product tax and partner tax group; a design that fits NativeFlows's architecture and is agentic-first, not copied.
- Practice compared: Dynamics 365 product masters with product dimensions, released products per company, unit conversions per product with per-variant fallback, item sales tax group × sales tax group, category hierarchies ([Microsoft Learn: unit conversion per variant](https://learn.microsoft.com/en-us/dynamics365/supply-chain/pim/uom-conversion-per-product-variant); [variant-specific sales tax groups](https://learn.microsoft.com/en-us/training/modules/create-products-product-masters-dyn365-supply-chain-mgmt/variant-specific-sales-tax)); Business One unit-of-measure groups, fixed once transactions exist ([SAP Learning](https://learning.sap.com/courses/managing-logistics-in-sap-business-one/working-with-units-of-measure-uom-in-sap-business-one)); Odoo product templates and variants with fiscal positions ([Odoo: taxes](https://www.odoo.com/documentation/19.0/applications/finance/accounting/taxes.html)); SAP material master with alternative units per material, classification system and tax classifications.
- ADR-0005: among correct options, the one easiest for AI agents wins; tax and business rules not in the spec go to the author.

## Options considered

| Option | For | Against |
| --- | --- | --- |
| Product + item, each field on one level (chosen) | Variants without duplicating shared data; no inheritance to reason about | Two tables even for simple goods (one item per product) |
| One flat item table, variants as separate items | Simplest | Shared fields repeated per variant and drifting apart |
| Item fields that inherit from the product and can be overridden (D365 fallbacks) | Flexible | Every read resolves two levels; agents and reports misread effective values |
| Shared products released per company (D365) | One catalog for a group | A second scope level before it is needed; an open question for the author |
| Fixed numbered analytic fields with a naming table | Fast reports; familiar | Opaque names in schemas, an arbitrary limit, and a second mechanism beside user-defined fields |
| Classification schemes (chosen) | Any number of named groupings in the same tables; agents read names | Reports join one table per scheme used |
| Tax codes on the product (Odoo default taxes) | Direct | Rates change by date and partner; the matrix keeps rates off the product |
| Variant attributes in fixed numbered columns | Simple uniqueness | The opaque slots rejected in rule 15 |

## Constraints that come with the decision

- DS-04: error `quantity_rounds_to_zero`; check result `quantity_rounded`.
- DS-08 / ADR-0015: valuation class and item group are product fields read through the item.
- DS-09: stock, cost, lots and serials per item; shelf life and expiry.
- DS-11: HS code and country of origin on products; allocation by weight per inventory unit.
- DS-20 (rest): partners with partner tax groups; `partner_item`; employees (buyer, salesperson); warehouses; price lists per item.
- DS-22: document lines store entered and inventory quantities (rule 11).
- DS-23: the tax matrix and the override rule. DS-24: unit names on e-invoices.
- DS-14 / ADR-0016: packages seed item tax groups, product categories and classification schemes as templates.
- DS-31: barcodes per packaging unit.

## Revisit when

- A customer needs variants that differ in tax group, unit conversion or valuation class.
- A group of companies needs one shared product catalog (open question).
- Packaging-unit dimensions are needed (e.g. for freight by carton).

## Documents updated

- [docs/spec/00-reading-guide.md](../spec/00-reading-guide.md): glossary rows for product, item, product type, variant attribute, units, product unit, unit conversion, item barcode, classification, product category, item tax group, partner tax group, tracking, buyer, data translation; price control and unit conversion factor rows.
- [docs/spec/07-shared-foundation.md](../spec/07-shared-foundation.md): UoM group points here.
- [docs/adr/0015-account-determination.md](0015-account-determination.md): note that valuation class and item group are product fields.
- [docs/design/DS-04-command-envelope.md](../design/DS-04-command-envelope.md): error code.
- [docs/design/backlog.md](../design/backlog.md): DS-20 row links here for the item part.
- [docs/adr/README.md](README.md): index row.
- [docs/open-questions.md](../open-questions.md): tax code override on lines; shared catalog for companies of one owner.
- [docs/runbook/step-log.md](../runbook/step-log.md): entry.
