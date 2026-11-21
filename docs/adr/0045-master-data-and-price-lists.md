# ADR-0045: Master data model and price lists

Status: accepted (2026-11-15) under ADR-0005, reviewed by Claude Fable 5.2 (builder Claude Opus 5.5). Design item: DS-20 (the rest after ADR-0018 and ADR-0019). Related decisions: D5, D6. Principles 6, 7. ADR-0004, ADR-0006, ADR-0007, ADR-0011, ADR-0015, ADR-0016, ADR-0017, ADR-0018, ADR-0019, ADR-0020, ADR-0021, ADR-0022, ADR-0023, ADR-0024, ADR-0027, ADR-0029, ADR-0031, ADR-0033, ADR-0035, ADR-0036, ADR-0037, ADR-0038, ADR-0039, ADR-0041, ADR-0042, ADR-0043, ADR-0044.

## Decision

**The DDL draft.** DS-20 is completed by a DDL draft of all master data, [DS-20-master-data.sql](../design/DS-20-master-data.sql):
- currencies and units;
- company, branches, cost centers, projects and working calendars;
- the groups copied from package templates;
- partners with roles, profiles, addresses, bank accounts, contacts and their own item codes;
- products, items, variants, units, barcodes and classifications;
- warehouses, zones, bins, lots and serials;
- price lists.

It loads together with the DS-06 journal in the design lab, and the earlier journal tests pass on it. Company, branch, cost center and project move there from DS-06. Every table except four global catalogs carries `company_id` and row-level security.

**Price lists.** They are per company, of kind `sale`, `purchase` or `by_product`, in one currency. Entries are per item and unit, with quantity breaks and dated validity.
- **One lookup rule.** It gives the price for an item, unit, quantity, date and chosen line options.
- **Pricing procedure.** Choosing the list, discounts, promotions and the policy checks belong to DS-22, which now owns pricing as a whole.

**Line options.** As the author asked, attributes come in two modes, as in Odoo:
- **Variant attributes** create items, as ADR-0018 rule 6 says.
- **Line options** create no item. They are chosen on each document line, may add a price extra, and travel with the line to delivery and production.
- **Items on order.** A product may also let a line name a new combination of variant values; the item is created when the document leaves draft, and never by an agent directly.
- **Product configuration** (DS-56, Phase 1 by the author's decision of 2026-11-15) builds on both: it selects and sizes bills of materials and routings, prices configured units and values them.

**Rules in commands.** Rules that need other rows (allowed units, employees as buyers, list currencies) are enforced by commands and named here.

### Rules

**The model**

1. [DS-20-master-data.sql](../design/DS-20-master-data.sql) is the master data model.
   - **Precedence.** ADRs win if it disagrees.
   - **Annotations.** Each table carries its owner module (ADR-0022 rule 2): `master_data` for currencies, units, organization, calendars, groups, partners, products, warehouses and price lists; `inventory` for zones, bins, lots and serials.
   - **Row-level security.** Every table carries `company_id`, `FORCE ROW LEVEL SECURITY` and the generated company policy (ADR-0017 rule 19, ADR-0022 rule 8), except the global catalogs `currency`, `uom` (core rows have no company), `uom_conversion`, and `company` itself, whose policy compares its own ID. Child tables such as `partner_role`, the profiles, `product_uom` and `item_variant_value` carry it too, because foreign key checks do not apply row-level security.
   - **Integrity within a company.** References between company tables are composite on `(company_id, id)` wherever the parent has that key: a child's partner, product or item; profiles' lists, salespeople, buyers and calendars; a price entry's list and item; an option extra's list, product and value; a warehouse's branch, valuation warehouse, processor and default bins; a zone's warehouse and a bin's zone, which must be in the bin's warehouse. The database refuses these cross-company references even before row-level security (lab finding L-13). Every other reference (groups, units, categories, accounts) is validated by the handler, which loads the row under row-level security.
   - **Moved tables.** Company, branch, cost center and project are defined there; DS-06 keeps a note.
   - **Deferred to other items.** `partner_email_domain` (DS-35), `supplier_item` (ADR-0024 rule 2, planning) and `preliminary_price` (ADR-0020 rule 11, inventory) are defined with their owners, not here. `partner_email_domain` is in [DS-35-crm.sql](../design/DS-35-crm.sql). `contact` gains the composite keys, the e-mail and phone indexes, the lowercase e-mail check and `is_accounts_contact`; the contact commands normalize e-mail and phone; `CreatePartner` takes `email_domains` through `crm`'s hook ([ADR-0052](0052-minimal-crm.md) rules 3–5).

   Note ([ADR-0068](0068-sites-and-core-logistics-payment-master-data.md), 2026-11-21): `incoterm` is a fifth global catalog without `company_id` or row-level security.

**Price lists**

2. `price_list`:
   - **Columns:** company, `code`, `name`, `kind` (`sale`, `purchase`, `by_product`), `currency`, `is_tax_included` (sale lists only; passed as `prices_include_tax` to ADR-0041 rule 9), `is_default` (one per kind and company, and only an active list), `is_active`.
   - **Who uses which list.** The database holds the kind through a composite key on `(company_id, id, kind)`:
     - a customer's `customer_profile.price_list_id` points to a sale list;
     - a supplier's new `supplier_profile.price_list_id` points to a purchase list;
     - the company's `by_product` list replaces the `by_product_price` table of ADR-0035 rule 17, with entries per period (a note there). At most one is active per company. Commands require its currency to be the company currency, its entries to use the inventory unit and break 0, and no option extras.
   - **Profile checks by commands:** a profile's currency, when set, equals its list's currency (otherwise every document would fail rule 5's currency check), else `price_list_currency_mismatch`.
3. `price_list_entry`:
   - **Columns:** list, item, unit, `minimum_quantity` (a quantity break, in that unit), `start_date`, `end_date` (inclusive, ADR-0027 rule 12; empty is open), `unit_price` (ADR-0006).
   - **Overlap.** Entries of the same list, item, unit and break never overlap in dates. The database holds this with an exclusion constraint (`btree_gist`), so concurrent `SetPriceListEntries` cannot race; the command maps the violation to `price_list_entry_overlap`.
   - **Unit, by commands:** the entry's unit is the product's inventory unit or one of its product units (ADR-0018 rules 10, 13), else `uom_not_allowed`. The error applies to price entries and to a product's purchase and sales units; a document line may also use a unit reached through `uom_conversion` (ADR-0018 rule 10).

   Note ([ADR-0056](0056-multiple-units-of-measure.md), 2026-11-15): an entry's unit may be any unit the item resolves by `convert_quantity`, catalog units included, not only the inventory unit or a product unit; a unit whose product unit rows are all retired takes no new entries (`uom_retired`). When a used product unit row is retired and replaced for the same unit, the same command covers the entries of the unit valid on or after the business date at the replaced level: an entry that started earlier is end-dated to the day before, one starting later is removed, and one starting on the business date refuses the replacement (`price_entry_starts_today`); since a started entry can be neither removed nor ended before its start, the remedy is to run the replacement on the next business date (rules 4, 5, 16).
4. The lookup rule, `master_data.contract.find_price(list, item, unit, quantity, date, option_values)`:
   - **The conversion factor** from the line's unit to the inventory unit is 1 for the inventory unit, else the product unit's ratio, else the `uom_conversion` ratio between the line's unit and the inventory unit (a row in either direction, inverted when reversed), else none (`uom_not_allowed`). Ratios are exact fractions of two positive integers (ADR-0006 rule 11).
   - **Entered unit first.** Among that unit's entries valid on the date, the highest break not above the quantity wins. The entered unit's entry always wins, even where the inventory unit's break would give a lower price per inventory unit.
   - **Else the inventory unit.** When the entered unit has no qualifying entry (none at all, or only breaks above the quantity), the quantity is converted exactly to the inventory unit, the inventory unit's entries are searched the same way, and the price is multiplied by the factor and rounded half up to the unit-price scale (ADR-0006 rule 15).
   - **Breaks** apply per line, on the line's absolute quantity. Returns and credit notes take the origin line's price (DS-22), not `find_price`.
   - **Option extras** are added as rule 17 says.
   - **The result:** the price with every row used (the entry and each extra), as references for a derivation trace (ADR-0027 rule 3), or none with a reason (`price_missing`, `uom_not_allowed`, `negative_price`).
   - **Query.** `GetPrice` (computed, an exception to ADR-0004 rule 21 like ADR-0015 rule 14) exposes it to people and agents, with the same inputs.

   Note: the final signature, after [ADR-0046](0046-product-configuration.md) rule 15, is `master_data.contract.find_price(price_list, item or product, unit, quantity, date, values)`: the line's item when it has one, else the configurable product of a draft or quotation line; `values` are the chosen values of both modes (list value IDs and numbers) and replace `option_values`. The lookup order, the item entry replacing item-defining extras and rates, and the result (the price with every row used: entry, extras, rates; or none with `price_missing`, `uom_not_allowed` or `negative_price`) are ADR-0046 rule 15's. `GetPrice` takes the same inputs.

   Note ([ADR-0056](0056-multiple-units-of-measure.md), 2026-11-15): the conversion factor is `master_data.contract.convert_quantity`'s: the item's own row first, then the product's, then a `uom_conversion` pair or its inverse; retired rows give `uom_retired`. Worked example: with pieces at 10,000 from 0 and at 9,000 from 100, and cartons of 24 at 230,000 from 0, 5 cartons price at 230,000, not 9,000 × 24; with a carton entry only from 10 cartons, 5 cartons fall back to 216,000 and 2 cartons to 240,000. Promotion quantities are in the inventory unit, and `amount_per_unit` is per inventory unit times the factor (rules 6, 16).
5. Pricing as a whole is DS-22's, which closes design assessment finding C-3:
   - **The procedure:** the list a document uses (its partner's profile list, else the default list of the kind), discounts, promotions, quotation validity, and the trace. `find_price` is the only computation of list price plus extras; DS-22 and the policy checks call it rather than reimplementing it.
   - **Tax inclusion.** A document takes `prices_include_tax` from its list. A line priced from a tax-inclusive list where ADR-0041 rule 9 forbids inclusive pricing (more than one percent code) is rejected by DS-22's check.
   - **"Outside the list"** (ADR-0043 rule 3): the line's unit price differs from `find_price` (with the line's options, on the document date, both on the same tax basis). When `find_price` returns none, the line is outside the list with reason `price_missing`.
   - **"Below cost":** the line's net unit price, in company currency per inventory unit, is below the item's preliminary price in its valuation area (ADR-0020 rule 11). Flagged, because the cost used is the author's choice (EC-22).
   - **Currency.** In Phase 1 a list's currency must equal the document's, else `price_list_currency_mismatch` (flagged).

   For a configurable line without an item or preliminary price, "below cost" and margin use the configuration estimate; an unknown cost needs human confirmation ([ADR-0046](0046-product-configuration.md) rule 14).

   Note: "below cost" is [ADR-0047](0047-commercial-documents-and-pricing.md) rule 22's `is_price_below_cost`: a paid line's net amount after the document-discount allocation, per inventory unit, in company currency at the applied rate, against its cost; free goods are excluded. The "net unit price" above gives way to it.

   Note: when the list a document would take (its partner's profile list, else the default list of the kind) is in another currency than the document, the document carries no list instead of failing: every line's price is entered (`price_required` otherwise), `is_price_outside_list` is true for it, and the command returns the check result `price_list_currency_differs`. A list the client names explicitly in another currency is still rejected with `price_list_currency_mismatch`.

   Note (author's delegation, 2026-11-19): all interim choices of this ADR are confirmed (below cost against the preliminary price per inventory unit; list currency equal to the document currency in Phase 1; postings to a closed project rejected; the five cost center kinds; a buyer needs a user account; `relative_sales_value` from the default sale list, net of tax; the actual-average fallback of rule 6).
6. Production uses of prices (ADR-0035):
   - **`relative_sales_value`** reads the default sale list for the inventory unit, quantity 1 and no options, on the period's last day. From a tax-inclusive list the price is reduced to net by ADR-0041 rule 9's inclusive split. Which list is the cost-split basis is flagged.
   - **The estimate's `purchase_price`** is the preferred supplier's (ADR-0024 rule 2) purchase-list price for one purchase unit on the estimate date, converted to the inventory unit, and from a foreign currency at rate type `transaction` on that date (ADR-0011 rule 11). With none, the estimate uses the actual average and returns the check result `purchase_price_missing`. The fallback is flagged.
   - **The `by_product` list** gives by-product prices per inventory unit in company currency (rule 2).
7. Commands and events:
   - **Commands:** `CreatePriceList`, `UpdatePriceList`, `SetPriceListEntries` (a set of entries for one list as one change) and `SetPriceListOptionExtras`.
   - **Registration.** All are `master_data_change`, change-tracked (ADR-0038 rule 3), and `is_proposal_bound`, so an agent's price change is a change proposal (ADR-0029 rule 5).
   - **Event.** `SetPriceListEntries` emits `PriceListEntriesSet`, which is DS-17's `price_list_published`.
   - **Queries:** `ListPriceList`, `ListPriceListEntry`, `GetPrice`.

   Note: `SetPriceListEntries` semantics. Each entry is an upsert by its key: list, item or product, unit, `minimum_quantity` and `start_date`. A new entry end-dates, in the same command, the entry of the same list, item or product, unit and break that starts latest before it, to the day before its start, when that entry is open-ended or ends later; any other overlap is still `price_list_entry_overlap`. An entry whose `start_date` is on or before the business date (it may already price documents) is only end-dated: its price, unit, break and start never change, and it is never removed. Later entries may be changed or removed.

   Note: these commands are not registered `is_proposal_bound`: effect class `master_data_change` already makes them allowed targets of the carrier (ADR-0029 rule 2), and the flag is kept for commands of other effect classes. The same holds for the promotion commands ([ADR-0047](0047-commercial-documents-and-pricing.md) rule 17).

**Organization**

8. Company and branch:
   - **Company:** `legal_form` (ADR-0039 rule 5) and `default_language` join the company; the language is set at company creation from the package, with no core default. Currencies a company uses are rows of `company_currency_activation` (ADR-0011 rule 7).
   - **Branch.** `is_declaring_unit` marks a branch that declares VAT with its own tax ID, so it is a declaring unit of ADR-0041 rule 11, and the database requires its tax ID. Addresses of branches and warehouses are `jsonb` with the columns of `partner_address` as keys.
   - **Dependent units.** Whether a dependent unit with its own tax ID is a branch or a company stays the open question it is.
9. Cost centers and projects:
   - **Cost centers** have `kind` (`production`, `production_service`, `selling`, `administration`, `other`), an optional parent and branch of the same company, and `is_active`. The kind tells production cost pools (ADR-0035 rule 7) from service centers, and gives the expense-function question (641 or 642) a place to land.
   - **Projects** have an optional customer, dates and `state` (`open`, `closed`). A posting to a closed project is rejected with `project_closed` (flagged); drafts may still name it, so a document started before closing is corrected rather than lost. Projects are dimensions only in Phase 1 (spec 09).

   Note ([ADR-0069](0069-business-unit-dimension.md), 2026-11-21): cost centers and projects gain a default `business_unit_id`. Business units themselves are company data of `master_data` under the leaf `organization`.
10. Working calendars:
    - **Structure:** working weekdays and dated holidays (ADR-0024 rule 4).
    - **Who uses them:** warehouses and suppliers name theirs. Holidays come from a package template entry with its basis, or are added by the company with basis `company_decision`; every holiday row carries its basis.

**Employees and groups**

11. Employees:
    - **Profile.** `employee_profile` gains `branch_id`, `cost_center_id` and `job_title`. Its `user_account_id` is unique. The profile is `personal` data (ADR-0019 rule 7).
    - **Buyers and salespeople.** A `buyer_id` or `salesperson_id` must be a partner with the active `employee` role, else `partner_not_employee`.
    - **Work items.** A buyer without a user account cannot own work items; the fallback of ADR-0042 rule 7 then applies.

    Note: `employee_profile` gains `department_id` and `manager_partner_id`, and `user_account_id` becomes unique per company, so one user can be an employee of several companies. The three columns change only through `UpdateEmployeeOrganization`, never through `CreatePartner`, `UpdatePartner` or a change proposal ([ADR-0054](0054-users-roles-and-authorizations.md) rule 6).
12. Groups:
    - **Which:** partner groups, partner tax groups (with the directions they apply to), item groups, valuation classes, item tax groups and product categories.
    - **Ownership.** They are `master_data` tables, copied from package templates with their basis (ADR-0016 rule 7). `basis` has no default: the command sets the template entry's basis, or `company_decision` (ADR-0016 rule 12). The tax matrix of ADR-0041, owned by `tax`, reads the tax groups.
    - **Product categories** carry the defaults a new product takes: item group, valuation class, item tax group, inventory unit.

**Rules held by commands**

13. Besides rules 2, 3 and 11, commands check:
    - **Units:** a product's purchase and sales units are its inventory unit or one of its product units, and a product unit is not the inventory unit; dimensions use a length unit and weights a mass unit; a serial-tracked product's inventory unit is a count unit with 0 decimals (ADR-0018 rule 9).
    - **Variants:** an item's `variant_key` equals its variant value rows, which cover every variant-mode attribute of its product and only those.
    - **Within the company:** a cost center's parent, a partner's parent, a product category's parent, a classification value's parent, the groups, units and accounts a row names (the composite keys of rule 1 cover the rest); no `uom_conversion` row names a company unit (ADR-0018 rule 8).
    - **Warehouses:** a new warehouse gets its default zone and bin in the same command (ADR-0031 rule 8); a valuation warehouse is physical.
    - **Option extras:** only on `sale` and `purchase` lists.

    The database holds the rest: unique codes, kinds, positive dimensions and conversion factors, a gross weight not below the net, a stock product's valuation class, tracking only for stock, one default list per kind, one active by-product list, a list's kind on profiles, non-overlapping price entries and extras, a declaring branch's tax ID, a default bin in every warehouse, bins and zones of the same warehouse, a bin-managed warehouse's receiving and shipping bins, one processor warehouse per processor, the attribute modes, and the composite keys of rule 1.

    Note: partner commands (DS-20), all `master_data_change` and change-tracked, with the optional `expected_version` of ADR-0029 rule 2. `CreatePartner`: `code`, `name`, `legal_name`, `partner_kind`, `tax_id`, `country`, `preferred_language`, `parent_partner_id`, `partner_group_id`, `partner_tax_group_id`, `roles` (a list of `customer`, `supplier`, `employee`), optional `customer_profile`, `supplier_profile` and `employee_profile` objects with their DS-20 columns (not the organization columns of rule 11's note), `addresses` (kind, address lines, subdivision code, postal code, country), and `email_domains` through `crm`'s hook. `UpdatePartner`: `partner_id` and the fields to change, profiles merged. `SetPartnerRole`: `partner_id`, `role`, `is_active`, and the role's profile when it is added. Further: `CreatePartnerAddress` and `UpdatePartnerAddress`; `CreatePartnerBankAccount` and `UpdatePartnerBankAccount` (always through a proposal, ADR-0029 rule 4); `CreateContact` and `UpdateContact` ([ADR-0052](0052-minimal-crm.md) rule 3); `CreatePartnerItem` and `UpdatePartnerItem` (ADR-0019 rule 6); `UpdateEmployeeOrganization` ([ADR-0054](0054-users-roles-and-authorizations.md) rule 6). Defaults for empty fields: `partner_group_id` from the company settings `master_data.default_partner_group.customer`, `master_data.default_partner_group.supplier` and `master_data.default_partner_group.employee` (an active partner group, or empty), taking the first role of the payload whose setting is set; a customer or supplier profile's `receivable_account_id` or `payable_account_id` from the determination rows of `receivable_reconciliation` or `payable_reconciliation` for that group (ADR-0015 rule 11), else `account_determination_missing`; the profile's list, payment term and currency stay empty, so documents take the company's defaults ([ADR-0047](0047-commercial-documents-and-pricing.md) rules 4, 10).

    Note (simulation review, 2026-11-15): the defaults `CreatePartner` needs are those of the previous note: the partner group by role, the receivable and payable accounts by determination, and an empty list, payment term and currency, so documents take the company's defaults. There is no default credit limit: an empty `credit_limit` means no credit check ([ADR-0047](0047-commercial-documents-and-pricing.md) rule 18 note).

    Note ([ADR-0056](0056-multiple-units-of-measure.md), 2026-11-15): unit checks also: every unit of a serial-tracked product is exact (`serial_unit_not_exact`); a product unit names a catalog-convertible unit only with the catalog's factor (`uom_conversion_conflict`); its `contains` relation matches the factors, also across a replacement (`uom_packaging_inconsistent`); a used row is immutable (`uom_conversion_in_use`); `is_exact` is computed, never entered; a unit field that needs a kind gets one (`uom_kind_mismatch`). A product's purchase and sales units may be any unit the item resolves. The database now holds that a product unit is not the inventory unit, the item of an item-level row, and one active row per unit (rules 4, 5, 15, 20).

    Note ([ADR-0061](0061-barcodes.md), 2026-11-15): barcode checks also: a barcode is unique in the company across item units, bins, handling units, lots, serials, barcoded documents and reserved codes, and numeric codes also on their digits padded to 14 (`barcode_taken`, held by the registry's keys); internal codes fit the format and GTINs and SSCCs carry valid check digits (`barcode_format_invalid`); values are stored normalized (`barcode_not_normalized`); a barcode does not start with a barcoded document type's reserved prefix (`barcode_prefix_reserved`); GS1 company prefixes are 4 to 12 digits and do not overlap (`gs1_prefix_invalid`, held by an exclusion constraint); a prefix with registry codes under it is deactivated, never deleted (`gs1_prefix_in_use`) (rules 7-11).

    Note ([ADR-0062](0062-product-engineering-workflow.md), 2026-11-15): commands also check: manufacturer part numbers unique per company, normalized manufacturer and number (`item_manufacturer_part`); category requirements naming their attribute or scheme (`product_category_requirement`); both are `master_data_change` ([ADR-0062](0062-product-engineering-workflow.md) rule 19).
14. Lab check `t05_master_data.py` (it covers what the database holds, not the command rules of rule 13):
    - **Constraints:** forty-one scenarios, each matched to the constraint that must refuse it, and a check that every DS-20 table outside the four global catalogs has `company_id`.
    - **The lookup:** twenty cases on real rows, with exact fractions: breaks and dates; a carton from the each price; the entered unit's entry winning; fallback when no break qualifies; a 7/3 product unit with rounding; a unit through `uom_conversion`; a unit that is not allowed; option extras, with a product-specific extra winning, an expired extra, an extra on a 7/3 unit, and a negative total.
    - **Earlier tests.** The journal, subledger, cost object and opening tests pass on the real master data tables in place of the old stubs (L-13).

    Note ([ADR-0068](0068-sites-and-core-logistics-payment-master-data.md), 2026-11-21): the lab's list of tables without `company_id` gains `incoterm`.

**Attributes that do not create variants**

15. Two attribute modes:
    - **The mode.** `variant_attribute.variant_mode` is `variant` (ADR-0018 rules 6–7: each combination of values is an item, with its own stock, cost and prices) or `line_option`. Each value carries its attribute's mode through a composite key, so the database refuses a line option as an item's variant value, refuses a variant-mode value in an option extra, and refuses to change an attribute's mode once it has values.
    - **Line options.** A line option is chosen on a document line and creates no item. Examples: a finish, an engraving, a fabric for goods made to order, a delivery packing. A product names its attributes of both modes in `product_variant_attribute`. A line option may be `is_required`, and `product_attribute_value` may limit the values a product allows for an attribute of either mode (none listed means every value).
    - **Custom values.** A value marked `is_custom` (line options only; the database holds it) asks the line for free text, such as an engraving's words. The text is `personal` and `is_untrusted` (ADR-0019 rule 7, ADR-0029 rule 10). Whether it prints on the e-invoice line is the e-invoice add-on's (DS-24).
    - **Lines.** DS-22 and production documents carry the line's choices as `document_line_option` rows (line, attribute, value, custom text), one value per attribute per line, part of the line's content and of the plan. The commands check required options and allowed values (`line_option_required`, `line_option_value_not_allowed`). Options are copied to deliveries, returns and credit notes. A price extra is folded into the line's unit price, not a separate invoice line. Purchase and subcontracting lines may carry options too, as information for the supplier.
    - **What options do not change.** They are not part of the stock key: two lines of one item with different options draw on the same stock. An option that must be kept apart in stock, costed apart or taxed apart is a variant attribute instead.
    - **Downstream.** Options travel to the delivery, the pick list and, for goods made to order, the production order.
    - **Cost and stock of options.** An option with a price extra has no cost of its own: extra material or labor averages into the item's periodic cost, and "below cost" and margin ignore it. Customized units would return to, or be received into, the same stock as standard units. Both are DS-56's: configured units that change the goods are made to order (ADR-0036 rule 9) or made into their own items (rule 16), and DS-56 decides their valuation.

    A line's choices are a `product_configuration` (the `document_line_option` rows become its values; custom text stays on the line), and the cost and stock of options are settled by the split between item-defining characteristics and line options ([ADR-0046](0046-product-configuration.md) rules 9, 12, 14).
16. Items on order. A product with `is_item_created_on_order` lets a document line name a combination of its variant values that has no item yet.
    - **On the draft.** The line holds the product and the chosen variant values, with no item. Simulation and drafts create nothing; the plan lists the item that would be created.
    - **When.** The item is created when the document leaves draft (its first `Submit`, `Issue` or `Post`), in that command's transaction, as `CreateItem` would (ADR-0018 rule 7). An abandoned draft leaves no item. An existing item with the same `variant_key` is reused.
    - **Who.** The actor needs the `CreateItem` permission. A line of an agent, or of a command carrying an origin agent run, that names a combination without an item is rejected with `proposal_required`: the agent proposes the item through a change proposal first (ADR-0029 rule 4).
    - **Checks.** The combination respects `product_attribute_value` and covers every variant-mode attribute of the product.
    - **Code.** The item's code is the product's code, a hyphen and the next number of `product.last_item_number`, incremented under the product row's lock (gaps allowed; it is not a legal series).
    - **What it lacks.** The new item has no price entry, preliminary price, planning parameters or production version. `find_price` returns none, so the line's price is entered (outside the list, `price_missing`) or comes from DS-56's configured price, and a made item cannot be released (ADR-0033 rule 16) until DS-56 supplies its production version.
    - Every item still exists before stock or cost touches it. This is Odoo's "dynamic" mode, with NativeFlows's agent safety.

    Only document types with the registry flag `is_item_creating` (sales orders, and production orders by ADR-0046) create items when they leave draft; quotations never do ([ADR-0047](0047-commercial-documents-and-pricing.md) rule 1).

    Note: `proposal_required` applies only where an item would be created: at the command that takes a document of an `is_item_creating` type out of draft, when an agent, or a command carrying an origin agent run, runs it. An agent's draft (a quotation, or a sales order draft) may hold the product with its variant values or configuration and no item; the item is created when a person's command takes the order out of draft ([ADR-0046](0046-product-configuration.md) rules 11, 17).

    Note (simulation review, 2026-11-15): **Who** changes for items created when a document leaves draft: `system` creates the item on behalf of the human whose command takes the document out of draft, as a consequence of that command, so that person needs the command's own permission (such as `SubmitSalesOrder`), not `CreateItem`. A person who may submit orders thus creates only the combinations the product allows (the checks above). `proposal_required` for agents is unchanged ([ADR-0046](0046-product-configuration.md) rule 11 notes).
17. Option prices. `price_list_option_extra` (list, optional product, option value, dates, `unit_price_extra` per inventory unit, which may be negative) adds to the price of rule 4:
    - **Which extra.** For each chosen value, the extra valid on the date for that product wins; else the extra for all products. Extras of one list, product (or all products) and value never overlap in dates (an exclusion constraint).
    - **The amount.** The extras of all chosen values are summed per inventory unit, multiplied by the factor of rule 4, rounded half up once to the unit-price scale, and added to the base price.
    - **A negative total** gives no price (`negative_price`).
    - The lab checks each of these, including a carton and a 7/3 unit.

    For a configurable product, extras apply to values of both modes, a product-level entry gives the base price, and `price_list_characteristic_rate` prices numbers; the database's mode check on extras becomes the command check `option_extra_not_allowed`. `find_price` takes the chosen values, and an item entry of a configured item replaces its item-defining extras and rates ([ADR-0046](0046-product-configuration.md) rule 15).

## Context

ADR-0018 (items) and ADR-0019 (partners) settled the shape of most master data, and ADR-0020, ADR-0023, ADR-0024 and ADR-0027 added warehouses, bins, planning data and the organization stubs. What DS-20 still lacked:
- a price model;
- complete cost center, project and employee tables;
- tax group ownership;
- DDL for any master table.

The design assessment (finding C-3) found that pricing had no single owner. SAP keeps prices in condition records with access sequences, and Odoo in pricelists with rules. NativeFlows keeps price data simple (dated entries per item, unit and break) and leaves the procedure to DS-22, so agents read one table and one lookup.

The review of this ADR found child tables without `company_id` (so without row-level security), decimal conversion factors against ADR-0006 rule 11, and items created by a document line outside agent safety. All three are fixed here, and the lab checks the first two.

## Options considered

| Option | For | Against |
| --- | --- | --- |
| Dated entries per item, unit and break, with one lookup (chosen) | Simple for people and agents; exact unit handling | Discounts and promotions live elsewhere (DS-22) |
| Condition records with access sequences (SAP) | Very flexible | A rule language before it is needed |
| Rule-based pricelists (formula on cost or another list, Odoo) | Few rows | Prices are computed, harder to read and audit |
| Composite foreign keys within a company (chosen) | Cross-company references refused by the database | Extra unique keys and a `company_id` on child tables |
| Overlap held by an exclusion constraint (chosen) | No race between concurrent writers | Needs `btree_gist`, already installed |
| Overlap checked by commands | No extension | Two concurrent commands can both pass |
| By-product prices as a price list kind (chosen) | One mechanism | One more kind |
| Attributes in two modes, variant or line option (chosen) | Options without an explosion of items; stock stays per real variant | Options are not stock dimensions; a kept-apart option must be a variant |
| Every attribute creates variants (ADR-0018 as it was) | One concept | Made-to-order options would multiply items |
| Items on order created at draft save | Simpler | Orphan items from abandoned drafts; agents create master data as a side effect |

## Constraints that come with the decision

- **ADR notes:**
  - ADR-0018 rules 2, 6, 7, 13: draft lines of items created on order; the two attribute modes and items on order; price list entries fix units;
  - ADR-0033 rule 17: line options and items on order are the base of product configuration, DS-56 (Phase 1);
  - ADR-0019 rules 3, 6: `supplier_profile.price_list_id`, employee profile columns, the `partner_item` table;
  - ADR-0027 rule 5: the DDL location and completed tables;
  - ADR-0035 rules 13, 17: the by-product list, `relative_sales_value`, `purchase_price`;
  - ADR-0041 rule 11: `is_declaring_unit`.
- **DS-04:**
  - errors `uom_not_allowed`, `price_list_entry_overlap`, `price_list_currency_mismatch`, `project_closed`, `partner_not_employee`, `line_option_required`, `line_option_value_not_allowed`, `negative_price`;
  - check results `purchase_price_missing`, `price_missing`.
- **DS-06:** organization tables moved to DS-20.
- **Other design items:**
  - DS-22: pricing procedure through `find_price`, outside-list and below-cost checks, tax inclusion; `document_line_option` on lines and its copying; draft lines with variant values and no item; returns at the origin price;
  - DS-56: cost and stock of options, configured prices, production versions of items created on order;
  - DS-17: `price_list_published` maps to `SetPriceListEntries`.
- **Open questions:**
  - the cost behind "below cost";
  - list and document currency;
  - closed projects;
  - cost center kinds;
  - buyers without users;
  - the list used for `relative_sales_value`, and the fallback when `purchase_price` has no price.

## Revisit when

- Pricing needs rules (a list derived from another, cost-plus), customer-specific entries beyond a list per customer, or conversion between currencies.

## Documents updated

- **The DDL draft:** [docs/design/DS-20-master-data.sql](../design/DS-20-master-data.sql) (new) and [docs/design/DS-06-universal-journal.sql](../design/DS-06-universal-journal.sql) (tables moved).
- **The lab:** [docs/reviews/2026-11-14-design-validation/](../reviews/2026-11-14-design-validation/README.md): `lab/t05_master_data.py`, stubs reduced and `btree_gist` added, t01 to t04 fixtures on the real tables, finding L-13.
- **ADRs:** [docs/adr/0018-product-and-item-model.md](0018-product-and-item-model.md), [docs/adr/0019-partners-and-crm-foundation.md](0019-partners-and-crm-foundation.md), [docs/adr/0027-cross-cutting-ownership.md](0027-cross-cutting-ownership.md), [docs/adr/0033-production-master-data.md](0033-production-master-data.md), [docs/adr/0035-production-costing.md](0035-production-costing.md), [docs/adr/0041-tax-engine.md](0041-tax-engine.md): notes.
- **Design files:** [docs/design/DS-04-command-envelope.md](../design/DS-04-command-envelope.md), [docs/design/backlog.md](../design/backlog.md).
- **Glossary:** [docs/spec/00-reading-guide.md](../spec/00-reading-guide.md).
- **Open questions:** [docs/open-questions.md](../open-questions.md).
- **Index and log:** [docs/adr/README.md](README.md); [docs/runbook/step-log.md](../runbook/step-log.md) at acceptance.
