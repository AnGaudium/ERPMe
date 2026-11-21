Module: master_data    Chunk: 2 of 8    Source ADRs: ADR-0019, ADR-0020, ADR-0021, ADR-0023, ADR-0024, ADR-0027, ADR-0031, ADR-0037, ADR-0045
Build step(s): 0, 1, 2, 3, 4b, 5    Generated from index: 30d5706    Compiled by: Claude Opus 5.5, 2026-11-21

# `master_data` compiled spec, chunk 2: partner details, warehouses, organization, price lists and pricing

## Purpose

This chunk states the part of `master_data` law on partner addresses, bank accounts, partner item codes, field labels, contacts and duplicate detection; warehouses, default bins and processor locations; product fields for customs and warehousing; working calendars; company, branch, cost centers and projects; the DS-20 model and its company isolation; and price lists with the `find_price` lookup. `master_data` is a layer 3 module (ADR-0022.R2). Zones, bins, lots, serials and stock belong to `inventory`, pricing procedures to DS-22, and the other master data to the other chunks.

## Entities and tables

DDL: `docs/design/DS-20-master-data.sql`. Every table below carries `company_id` and row-level security (R242).

| Table | Meaning | Key | Parent | Owner |
| --- | --- | --- | --- | --- |
| `partner_address` | A partner's address of one kind (R201, R202) | `id`; (`company_id`, `partner_id`, `id`) unique | `partner` | `master_data` |
| `partner_bank_account` | A partner's bank account (R201) | `id`; (`partner_id`, `bank_code`, `account_number`) unique, nulls not distinct | `partner` | `master_data` |
| `partner_item` | A partner's own code, name and unit for an item (R203) | `id`; (`partner_id`, `partner_item_code`) unique; (`company_id`, `id`) | `partner`, `item` | `master_data` |
| `contact` | A person at a partner (R205) | `id`; (`company_id`, `id`); (`company_id`, `partner_id`, `id`) | `partner` | `master_data` |
| `warehouse` | A storage place of one kind (R210-R216) | `id`; (`company_id`, `code`) unique; (`company_id`, `id`) | `company`, `site` | `master_data` |
| `working_calendar` | Working weekdays and holidays (R225) | `id`; (`company_id`, `code`) unique; (`company_id`, `id`) | `company` | `master_data` |
| `company` | The legal entity (R231, R261) | `id`; `code` unique | none | `master_data` |
| `branch` | A unit of a company (R232, R262) | `id`; (`company_id`, `code`) unique; (`company_id`, `id`) | `company` | `master_data` |
| `cost_center` | A cost collector of a company (R232, R263) | `id`; (`company_id`, `code`) unique; (`company_id`, `id`) | `company` | `master_data` |
| `project` | A project dimension (R232, R264) | `id`; (`company_id`, `code`) unique; (`company_id`, `id`) | `company` | `master_data` |
| `price_list` | A list of prices of one kind and currency (R245, R246) | `id`; (`company_id`, `code`) unique; (`company_id`, `id`); (`company_id`, `id`, `kind`) | `company` | `master_data` |
| `price_list_entry` | A dated price per item or product, unit and break (R247, R248, R260) | `id`; exclusion `ex_price_list_entry_overlap` | `price_list` | `master_data` |

Reads: `partner`, `partner_relationship`, `partner_role`, `employee_profile`, `customer_profile`, `supplier_profile`, `product`, `item`, `product_uom`, `item_variant_value`, `uom`, `uom_conversion`, `currency`, `incoterm`, `site`, `business_unit`, `working_calendar_holiday`, `company_currency_activation` (`master_data`, other chunks); `supplier_item`, `demand_supply_line` (`planning`); `preliminary_price`, zones, bins, lots, serials (`inventory`); `partner_email_domain` (`crm`); `journal_line` (`ledger`); `attachment_link`; `delivery`.

## Commands and queries

Authorization areas (catalog `authorization-areas.csv`, under the area `master_data`): `price_list` for price lists; `warehouse` for warehouses, zones, bins, lots and serials; `partner` for partners, addresses, contacts and partner item codes; `partner_bank_account`, changed only through change proposals; `organization` for branches, cost centers, projects, business units and working calendars. Verb levels are the catalog's (`Create`, `Update`, `Set`: edit; `List`: read; computed queries need read).

| Name | Actor and authorization | Input | Effect | Events | Error codes |
| --- | --- | --- | --- | --- | --- |
| `CreatePriceList` | area `price_list`, edit | list columns | Creates a `price_list` (R245, R259) | none stated | not stated |
| `UpdatePriceList` | area `price_list`, edit | list columns | Changes a `price_list` (R259) | none stated | not stated |
| `SetPriceListEntries` | area `price_list`, edit | a set of entries for one list | Upserts and end-dates entries as one change (R260) | `PriceListEntriesSet` | `price_list_entry_overlap`, `uom_retired` |
| `SetPriceListOptionExtras` | area `price_list`, edit | not stated | Sets a list's option extras (R259) | none stated | not stated |
| `ListPriceList` | query; area `price_list`, read | not stated | Lists price lists (R259) | none | none stated |
| `ListPriceListEntry` | query; area `price_list`, read | not stated | Lists price list entries (R259) | none | none stated |
| `GetPrice` | computed query; area `price_list`, read | the inputs of `find_price` | Returns the price and every row used, or none with a reason (R249-R251) | none | none; reasons `price_missing`, `uom_not_allowed`, `negative_price` |
| `CreateWarehouse` | area `warehouse`, edit | not stated | Creates a warehouse with its default zone and default bin (R213) | none stated | not stated |
| `UpdateWarehouse` | `human_only`; area `warehouse`, edit | warehouse columns; `is_bin_managed: true` with `default_receiving_bin_id` and `default_shipping_bin_id` | Changes a warehouse; switches a physical warehouse to bin-managed (R214) | none stated | not stated |

Contract functions, not registry commands: `master_data.contract.find_price` (R249-R251) and `master_data.contract.convert_quantity` (R250). `CreatePartner` takes `email_domains` through `crm`'s hook (R244). Error codes bound to no named command: `warehouse_site_fixed` (R211), `movement_not_allowed_at_processor` (R216), `price_entry_starts_today` (R248), `price_list_currency_mismatch` (R246, R256), `price_required` (R256), `project_closed` (R264). Check results: `price_list_currency_differs` (R256), `purchase_price_missing` (R258).

## Rules

### Partners: addresses, bank accounts, item codes, labels, contacts, duplicates

R201. `partner_address` holds `kind` (`legal`, `billing`, `delivery`, `other`), `address_lines`, an optional `subdivision_code` from the localization package's list of administrative units, `postal_code`, `country` and `is_tax_zone` (the address lies in a zone the tax rules treat apart, a determinant of the tax treatment rule of ADR-0080.R3). `partner_bank_account` holds the bank (`bank_name`, optional `bank_code`), `account_number` and `holder_name`. The list of administrative units is flagged package data of the localization package, with its basis; its verification is the author's (ADR-0016). Documents copy the partner's name, address and tax ID at `Create` and `Update`, as version content (ADR-0028.R16; DS-22), so later edits of the partner do not change them.
Source: ADR-0019.R5

R202. Besides the sold-to partner's snapshot, a document may carry ship-to, bill-to and payer parties on the sales side and invoicing-party and payee parties on the purchase side, each with its own snapshot. A party not stated is the next one up, and defaults come from `partner_relationship` (ADR-0074.R1, ADR-0074.R2, ADR-0074.R3). `partner_address` has `UNIQUE (company_id, partner_id, id)` for the address key.
Source: ADR-0019.R5.N1

R203. `partner_item` (`partner_id`, `item_id`, `partner_item_code`, `partner_item_name`, `partner_uom_text`, `uom_id`; unique on partner and code) stores supplier and customer codes: the stored mappings the purchase invoice agent uses (spec 14). A mapping an agent proposes becomes a row only after approval; agent proposals are change proposals (ADR-0029.R1 to ADR-0029.R5). Supplier purchasing terms live in `supplier_item`, keyed by supplier and item, which may refer to a `partner_item` code (ADR-0024.R2). `partner_item.uom_id` proposes the unit of a line for that partner and item, after the source line and a scanned barcode (ADR-0056.R13).
Source: ADR-0019.R6, .N1

R204. Labels are declared per schema field (Principle 7, spec 17). The labels, categories and conditions of every field come from `personal-data-fields.csv`; the fields named here are an extract of it, and where they disagree the catalog wins (ADR-0079.R1, ADR-0079.R2). A field whose label depends on the record declares a registered condition: partner `name`, `legal_name`, `tax_id`, addresses, phones, emails and bank accounts are `personal` when `partner_kind` is `individual` or `sole_proprietorship` (the DDL values, ADR-0053.R7; the catalog condition `partner_is_person`), and `internal` or `public` otherwise. The LLM gateway (DS-32), event payload checks (ADR-0013.R4) and exports evaluate the condition per row; when the kind is unknown, the field is treated as personal. Contact fields and every field of `employee_profile` and of employee partners are always `personal`. The gateway evaluates the label per value and row when it renders a prompt, and removes personal values when the routing switch is on (ADR-0050.R8, ADR-0050.R9).
Source: ADR-0019.R7, .N1, .N2

R205. A `contact` is a person at a partner: `partner_id`, `name`, `job_title`, `email`, `phone`, `preferred_language`, `is_active`. A contact belongs to one partner; the same person at two partners is two contacts. Contact commands normalize `email` and `phone`, the database refuses an `email` that is not lowercase (`ck_contact_email_lower`), and `is_accounts_contact` marks the contacts that receive payment reminders (ADR-0052.R3, ADR-0052.R4, ADR-0052.R28).
Source: ADR-0019.R8

R206. Duplicate detection is deterministic: normalized tax ID, normalized email and phone, and name similarity by `pg_trgm` on names with diacritics removed, above a threshold set as company configuration (spec 14). A suspected duplicate creates a work item (`partner_duplicate_suspected`); it is never merged automatically. Interim, flagged: merging is allowed only while the duplicate has no posted documents; otherwise it is deactivated with `superseded_by_partner_id`. Normalized keys, the core fold table, the bounded query and the nightly scan are ADR-0052.R17.
Source: ADR-0019.R19

### Warehouses and processor locations

R210. A `warehouse` belongs to one company: `code`, `name`, `kind`, `branch_id`, `address`, `is_active`, and for `transit` and `goods_sent`, `valuation_warehouse_id`: the physical warehouse whose valuation area it belongs to (`ck_warehouse_valuation_warehouse`). `kind` is `physical`; `transit`, for goods the company owns on the way; or `goods_sent`, for goods delivered to customers or agents and still owned. The inventory key of a stock line follows the warehouse kind: `inventory_posting`, `inventory_in_transit_posting`, `inventory_goods_sent_posting` (ADR-0015). A `physical` warehouse may carry `processor_partner_id`; its stock uses the key `inventory_at_processor_posting` (ADR-0037.R1).
Source: ADR-0020.R1

R211. A `physical` warehouse carries `site_id`, required (`ck_warehouse_site`). `transit` and `goods_sent` warehouses take the site of their `valuation_warehouse_id`. A warehouse's site changes only while it has no material document line (`warehouse_site_fixed`).
Source: ADR-0020.R1.N1

R212. A warehouse has `is_bin_managed` (default false), `is_handling_unit_managed` and `outbound_flow` (`direct`; `staged` in the second slice); a bin-managed warehouse also has `default_receiving_bin_id` and `default_shipping_bin_id` (`ck_warehouse_bin_managed`). Only `physical` warehouses manage bins. A physical warehouse becomes bin-managed through `UpdateWarehouse` (ADR-0031.R9); the reverse is not supported. In `transit` and `goods_sent` warehouses stock rows and handling units use the default bin, never a null bin (ADR-0031.R8), and stock there is always `available`. Plain and bin-managed warehouses both have stock status and inspection, reservations, `status_change` and `count` tasks (in plain warehouses count tasks cover items and `status_change` uses the default bin) and handling units. Only bin-managed warehouses have bins, putaway and removal strategies, and putaway, pick, move and replenishment tasks.
Source: ADR-0023.R1, ADR-0031.R9

R213. Every warehouse, of every kind (`physical`, `transit`, `goods_sent`), has a default bin and a default zone, both created by `CreateWarehouse`, and `warehouse.default_bin_id` names the bin. The default bin has code `DEFAULT`, barcode `<warehouse code>-DEFAULT`, type `storage`, and no capacity or mix limits. It cannot be deactivated while the warehouse is not bin-managed.
Source: ADR-0031.R7

R214. `is_bin_managed` means that bins are visible and putaway, pick, move and replenishment tasks are used. A warehouse that is not bin-managed has exactly its default bin, which the UI hides. Only `physical` warehouses may switch: `UpdateWarehouse` (`human_only`) may set `is_bin_managed: true` at any time, together with the `default_receiving_bin_id` and `default_shipping_bin_id` that R212 requires. The default bin then becomes an ordinary storage bin, and stock leaves it by ordinary move tasks. Deliveries created before the switch issue from the default bin. The reverse is not supported. No `ConvertWarehouse` command and no `bin_management_locked` code exist.
Source: ADR-0031.R9

R215. A processor location is a `physical` warehouse with `processor_partner_id`, not bin-managed (`ck_warehouse_processor`). A company has at most one active location per processor. Stock there is the company's own and valued, in the area the company's valuation level gives (ADR-0020.R2). Its stock lines use the inventory key `inventory_at_processor_posting`, with the inventory leaves and determinants valuation class and warehouse, so a regime can show stock at processors on its own account; the accounts a localization package assigns to that key are its flagged package content (ADR-0039.R8).
Source: ADR-0037.R1

R216. Interim, flagged: materials sent to a processor stay inventory until the service receipt consumes them, as in SAP; recording them at sending is the author's open question and would need the transfer to post per order. Materials go to the processor by an ordinary transfer, moving quantity and value (ADR-0020.R6). Whether an invoice is issued for materials sent to a domestic processor is localization package content resting on a legal reference that is unverified; whether an internal transport document is needed is the regime's setting (DS-24). Only transfers in and out, production issues and returns, count differences and opening balances (stock at processors at cut-over) may post at a processor location; anything else is rejected with `movement_not_allowed_at_processor` (`INV-111`).
Source: ADR-0037.R1

### Product fields for customs and warehousing

R220. Products have `hs_code` and `country_of_origin` (`ck_product_country_of_origin`, two upper-case letters). They are proposed on declaration lines. The code's length and format are country data. `hs` (Harmonized System) is an allowed abbreviation.
Source: ADR-0021.R13

R221. The product (ADR-0018.R3) has `inspection_points`, the points at which it is inspected (`goods_receipt`, `in_process`, `production_output`, `customer_return`, `stock_recheck`; ADR-0070.R2); the upgrade maps a true `is_inspection_required` to `{goods_receipt, production_output}`. It also has `removal_strategy` (`fefo`, `fifo`, or none for the warehouse default), `storage_condition_id` (company data: ambient, cold, hazardous) and `default_handling_unit_type_id`. The customer profile (ADR-0019) has `minimum_remaining_shelf_life_days`. Whether shelf life may instead be a share of total shelf life, and whether expired lots may ever be picked, are open questions. Interim, flagged: days; expired lots are never picked.
Source: ADR-0023.R3, .N1

### Working calendars

R225. `working_calendar` is company data owned by `master_data`, so that production work centers can use it (ADR-0033.R11): working weekdays (`working_weekdays`, ISO weekdays) and holiday dates (`working_calendar_holiday`), assigned to warehouses and suppliers. The localization package may seed public holidays as a template entry with a basis (ADR-0016). Holiday dates are calendar data, not code.
Source: ADR-0024.R4

### Organization and cross-cutting ownership

R230. Every entity that several modules refer to has one owning module, in a layer that every module referring to it may import (ADR-0022.R2, ADR-0022.R7). `company`, `branch` and the `cost_center` and `project` tables are defined before step 1 code freezes the platform modules.
Source: ADR-0027.D0

R231. `company` holds `code`, `legal_name`, `tax_id`, `company_currency` (ADR-0011.R6), `time_zone` (ADR-0007), `localization_package` and `accounting_regime` (ADR-0016.R2), `legal_form` (null where the package declares none, ADR-0039.R5), `valuation_area_level` (ADR-0015.R8), `fiscal_calendar_owner_id` and `fiscal_year_lead_days` (ADR-0012.R3), `default_language` (R261) and `is_active`.
Source: ADR-0027.R5

R232. `branch` holds `company_id`, `code`, `name`, `tax_id` for dependent units where the regime uses one, `address` and `is_active`. `cost_center` and `project` exist from step 1 with `id`, `company_id`, `code` and `name`, because `journal_line` refers to them; DS-20 completes them by step 2 (R263, R264). Their DDL is in `docs/design/DS-20-master-data.sql` (ADR-0045.R1, ADR-0045.R8, ADR-0045.R9).
Source: ADR-0027.R5

R233. Employee references (`salesperson_id`, `buyer_id`) point to partners with the `employee` role (ADR-0019.R3).
Source: ADR-0027.R6

R234. Invariants of reservations, demand and agent safety and platform integrity (group 80 to 89):
- `INV-57`: per demand line, the reserved amounts of open and picked reservations never exceed the line's open quantity; first step 3, for transfer orders.
- `INV-63`: each `demand_supply_line` open quantity equals its source line's quantity minus fulfilled and closed quantities, recomputed from the referring documents; first step 3.
- `INV-80`: no outbox event that is tainted and whose command has effect class `posting`, `master_data_change` or `outbound_send` (a registry attribute of every command, ADR-0008.R1) has a non-human actor; first step 5, when agents start. Taint laundered through stored drafts stays a requirement on DS-32. Settled by ADR-0029.R8 to ADR-0029.R11.
- `INV-81`: no audit row of a command registered `human_only` has actor kind `agent`, or `integration` while the interim holds; first step 1, flagged.
- `INV-82`: every posted document that requires approval has the approvals its decision requires on the posted version, as the Invariants table states (ADR-0055.R8, ADR-0055.R18); documents under ADR-0009.R12's human-only posting store the outcome `human_only` and are outside this check; first step 5, flagged with ADR-0009.R12.
- `INV-83`: every `attachment_link` points to an existing row of its target table, within the attachment's company (area `platform`).
Source: ADR-0027.R17

### The DS-20 model and company isolation

R240. DS-20 is completed by the DDL draft `docs/design/DS-20-master-data.sql` of all master data: currencies and units; company, branches, cost centers, projects and working calendars; the groups copied from package templates; partners with roles, profiles, addresses, bank accounts, contacts and their own item codes; products, items, variants, units, barcodes and classifications; warehouses, zones, bins, lots and serials; price lists. It loads together with the DS-06 journal. Attributes come in a variant mode and a line-option mode: variant attributes create items (ADR-0018.R6); line options create no item, are chosen on each document line, may add a price extra, and travel with the line to delivery and production. A product may let a line name a new combination of variant values; the item is created when the document leaves draft, and never by an agent directly. Product configuration (DS-56, Phase 1) builds on both modes. Rules that need other rows (allowed units, employees as buyers, list currencies) are enforced by commands.
Source: ADR-0045.D0

R241. `docs/design/DS-20-master-data.sql` is the master data model; where it disagrees with an ADR, the ADR wins. Each table carries its owner module (ADR-0022.R2): `master_data` for currencies, units, organization, calendars, groups, partners, products, warehouses and price lists; `inventory` for zones, bins, lots and serials.
Source: ADR-0045.R1

R242. Every table carries `company_id`, `FORCE ROW LEVEL SECURITY` and the generated company policy (ADR-0017.R19, ADR-0022.R8), except the global catalogs `currency`, `uom` (core rows have no company), `uom_conversion` and `incoterm`, which have no `company_id` and no row-level security, and `company` itself, whose policy compares its own ID. Child tables such as `partner_role`, the profiles, `product_uom` and `item_variant_value` carry it too, because foreign key checks do not apply row-level security.
Source: ADR-0045.R1, .N1

R243. References between company tables are composite on (`company_id`, `id`), among them a child's partner, product or item; profiles' lists, salespeople, buyers and calendars; a price entry's list and item; an option extra's list, product and value; a warehouse's branch, valuation warehouse, processor and default bins; a zone's warehouse and a bin's zone, which must be in the bin's warehouse. The database refuses these cross-company references even before row-level security. Every foreign key from a company table to a company table follows this, groups, categories and accounts included (ADR-0017.R19.N3); a key to `uom` stays single-column, and the handler validates that the unit is a core unit or one of the row's company (ADR-0045.R13).
Source: ADR-0045.R1

R244. Company, branch, cost center and project are defined in DS-20. `partner_email_domain` (DS-35, `docs/design/DS-35-crm.sql`), `supplier_item` (ADR-0024.R2, `planning`) and `preliminary_price` (ADR-0020.R11, `inventory`) are defined with their owners. `contact` has the composite keys, the e-mail and phone indexes, the lowercase e-mail check and `is_accounts_contact`; the contact commands normalize e-mail and phone; `CreatePartner` takes `email_domains` through `crm`'s hook (ADR-0052.R3 to ADR-0052.R5).
Source: ADR-0045.R1

### Price lists

R245. `price_list` holds company, `code`, `name`, `kind` (`sale`, `purchase`, `by_product`), `currency`, `is_tax_included` (sale lists only, `ck_price_list_tax`; passed as `prices_include_tax` to ADR-0041.R9), `is_default` (one per kind and company, and only an active list, `ck_price_list_default_active`) and `is_active`.
Source: ADR-0045.R2

R246. The database holds the list's kind through a composite key on (`company_id`, `id`, `kind`): a customer's `customer_profile.price_list_id` points to a sale list, and a supplier's `supplier_profile.price_list_id` to a purchase list. The company's `by_product` list holds by-product prices, with entries per period, in the place of a `by_product_price` table (ADR-0035.R17); at most one is active per company. Commands require its currency to be the company currency, its entries to use the inventory unit and break 0, and no option extras. Commands require a profile's currency, when set, to equal its list's currency, else `price_list_currency_mismatch`.
Source: ADR-0045.R2

R247. `price_list_entry` holds the list, the item or a configurable product (exactly one, `ck_price_list_entry_target`; ADR-0046.R15), the unit, `minimum_quantity` (a quantity break in that unit, default 0), `start_date`, `end_date` (inclusive, ADR-0027.R12; empty is open) and `unit_price` (not negative; ADR-0006). Entries of the same list, item or product, unit and break never overlap in dates. The database holds this with the exclusion constraint `ex_price_list_entry_overlap` (`btree_gist`), so concurrent `SetPriceListEntries` cannot race; the command maps the violation to `price_list_entry_overlap`.
Source: ADR-0045.R3

R248. An entry's unit may be any unit the item resolves by `convert_quantity`, catalog units included; a unit whose product unit rows are all retired takes no new entries (`uom_retired`). A product's purchase and sales units, like a document line's unit, may be any unit the item resolves (ADR-0045.R13.N3, ADR-0018.R12.N1); a unit with no path to the inventory unit is `uom_not_allowed` (ADR-0056.R20). When a used product unit row is retired and replaced for the same unit, the same command covers the entries of the unit valid on or after the business date at the replaced level: an entry that started earlier is end-dated to the day before, one starting later is removed, and one starting on the business date refuses the replacement (`price_entry_starts_today`); the remedy is to run the replacement on the next business date (ADR-0056.R4, ADR-0056.R5, ADR-0056.R16).
Source: ADR-0045.R3, .N1

### The price lookup

R249. The lookup is `master_data.contract.find_price(price_list, item or product, unit, quantity, date, values)`: the line's item when it has one, else the configurable product of a draft or quotation line; `values` are the chosen values of both attribute modes (list value IDs and numbers). The lookup order, the item entry replacing item-defining extras and rates, and the result are ADR-0046.R15's; R250 and R251 state the lookup for an item's entries. The query `GetPrice` (computed, an exception to ADR-0004.R21 like ADR-0015.R14) exposes it to people and agents, with the same inputs.
Source: ADR-0045.R4, .N1

R250. The conversion factor from the line's unit to the inventory unit is `master_data.contract.convert_quantity`'s: 1 for the inventory unit; else the item's own unit row, then the product's, then a `uom_conversion` pair or its inverse; else none (`uom_not_allowed`). Retired rows give `uom_retired`. Ratios are exact fractions of two positive integers (ADR-0006.R11). Promotion quantities are in the inventory unit, and `amount_per_unit` is per inventory unit times the factor (ADR-0056.R6, ADR-0056.R16).
Source: ADR-0045.R4, .N2

R251. Among the entered unit's entries valid on the date, the highest break not above the quantity wins; the entered unit's entry always wins, even where the inventory unit's break would give a lower price per inventory unit. When the entered unit has no qualifying entry (none at all, or only breaks above the quantity), the quantity is converted exactly to the inventory unit, the inventory unit's entries are searched the same way, and the price is multiplied by the factor and rounded half up to the unit-price scale (ADR-0006.R15). Breaks apply per line, on the line's absolute quantity. Returns and credit notes take the origin line's price (DS-22), not `find_price`. Option extras are added as ADR-0045.R17 says. The result is the price with every row used (entry, extras, rates), as references for a derivation trace (ADR-0027.R3), or none with `price_missing`, `uom_not_allowed` or `negative_price`.
Source: ADR-0045.R4, .N1

### Pricing seams

R252. Pricing as a whole is DS-22's, which closes design assessment finding C-3: the list a document uses (its partner's profile list, else the default list of the kind), discounts, promotions, quotation validity, and the trace. `find_price` is the only computation of list price plus extras; DS-22 and the policy checks call it rather than reimplementing it.
Source: ADR-0045.R5

R253. A document takes `prices_include_tax` from its list. A line priced from a tax-inclusive list where ADR-0041.R9 forbids inclusive pricing (more than one percent code) is rejected by DS-22's check.
Source: ADR-0045.R5

R254. "Outside the list" (ADR-0043.R3): the line's unit price differs from `find_price` (with the line's options, on the document date, both on the same tax basis). When `find_price` returns none, the line is outside the list with reason `price_missing`.
Source: ADR-0045.R5

R255. "Below cost" is ADR-0047.R22's `is_price_below_cost`: a paid line's net amount after the document-discount allocation, per inventory unit, in company currency at the applied rate, against the item's preliminary price in its valuation area (ADR-0020.R11); free goods are excluded (`EC-22`). For a configurable line without an item or preliminary price, "below cost" and margin use the configuration estimate; an unknown cost needs human confirmation (ADR-0046.R14).
Source: ADR-0045.R5, .N1, .N3

R256. In Phase 1 the list a document would take (its partner's profile list, else the default list of the kind) is used only in the document's currency. When it is in another currency, the document carries no list instead of failing: every line's price is entered (`price_required` otherwise), `is_price_outside_list` is true for it, and the command returns the check result `price_list_currency_differs`. A list the client names explicitly in another currency is rejected with `price_list_currency_mismatch`.
Source: ADR-0045.R5, .N2, .N3

R257. Production uses of prices (ADR-0035): `relative_sales_value` reads the default sale list for the inventory unit, quantity 1 and no options, on the period's last day, and is net of tax: from a tax-inclusive list the price is reduced to net by ADR-0041.R9's inclusive split. The default sale list is the cost-split basis.
Source: ADR-0045.R6, ADR-0045.R5.N3

R258. The estimate's `purchase_price` is the preferred supplier's (ADR-0024.R2) purchase-list price for one purchase unit on the estimate date, converted to the inventory unit, and from a foreign currency at rate type `transaction` on that date (ADR-0011.R11). With none, the estimate uses the actual average and returns the check result `purchase_price_missing`. The `by_product` list gives by-product prices per inventory unit in company currency (R246).
Source: ADR-0045.R6, ADR-0045.R5.N3

### Price list commands

R259. The commands are `CreatePriceList`, `UpdatePriceList`, `SetPriceListEntries` (a set of entries for one list as one change) and `SetPriceListOptionExtras`. All have effect class `master_data_change` and are change-tracked (ADR-0038.R3). They are not registered `is_proposal_bound`: effect class `master_data_change` already makes them allowed targets of the carrier (ADR-0029.R2), so an agent's price change is a change proposal (ADR-0029.R5); the flag is kept for commands of other effect classes, and the same holds for the promotion commands (ADR-0047.R17). `SetPriceListEntries` emits `PriceListEntriesSet`, which is DS-17's `price_list_published`. The queries are `ListPriceList`, `ListPriceListEntry` and `GetPrice`.
Source: ADR-0045.R7, .N2

R260. `SetPriceListEntries` upserts each entry by its key: list, item or product, unit, `minimum_quantity` and `start_date`. A new entry end-dates, in the same command, the entry of the same list, item or product, unit and break that starts latest before it, to the day before its start, when that entry is open-ended or ends later; any other overlap is `price_list_entry_overlap`. An entry whose `start_date` is on or before the business date (it may already price documents) is only end-dated: its price, unit, break and start never change, and it is never removed. Later entries may be changed or removed.
Source: ADR-0045.R7.N1

### Company, branch, cost centers and projects

R261. `legal_form` (ADR-0039.R5) and `default_language` are columns of `company`; the language is set at company creation from the package, with no core default. The currencies a company uses are rows of `company_currency_activation` (ADR-0011.R7).
Source: ADR-0045.R8

R262. `branch.is_declaring_unit` marks a branch that declares VAT with its own tax ID, so it is a declaring unit of ADR-0041.R11, and the database requires its tax ID (`ck_branch_declaring_unit_tax_id`). Addresses of branches and warehouses are `jsonb` with the columns of `partner_address` as keys. Whether a dependent unit with its own tax ID is a branch or a company stays an open question.
Source: ADR-0045.R8

R263. A `cost_center` has `kind` (`production`, `production_service`, `selling`, `administration`, `other`), an optional parent and branch of the same company, a default `business_unit_id` and `is_active`. The kind tells production cost pools (ADR-0035.R7) from service centers, and gives the expense-function question a place to land. Business units are company data of `master_data` under the leaf `organization`.
Source: ADR-0045.R9, .N1, ADR-0045.R5.N3

R264. A `project` has an optional customer (`customer_partner_id`), dates (`start_date`, `end_date`), `state` (`open`, `closed`) and a default `business_unit_id`. A posting to a closed project is rejected with `project_closed`; drafts may still name it, so a document started before closing is corrected rather than lost. Projects are dimensions only in Phase 1 (spec 09).
Source: ADR-0045.R9, .N1, ADR-0045.R5.N3

## Invariants

| Invariant | Name | Check point | Statement | Protects |
| --- | --- | --- | --- | --- |
| `INV-57` | `reservations_match_demand` | day; first step 3 | Per demand line, the reserved amounts of open and picked reservations never exceed the line's open quantity. | R234 |
| `INV-63` | `demand_supply_matches_source` | day; first step 3 | Each `demand_supply_line` open quantity equals its source line's quantity minus fulfilled and closed quantities, recomputed from the referring documents. | R234 |
| `INV-80` | `tainted_never_acts` | day; first step 5 | No tainted outbox event whose command has effect class `posting`, `master_data_change` or `outbound_send` has a non-human actor. | R234 |
| `INV-81` | `human_only_never_by_agent` | day; first step 1; flagged (ADR-0008.R2: may integrations execute `human_only` commands) | No audit row of a command registered `human_only` has actor kind `agent`, or `integration` while the interim holds. | R234 |
| `INV-82` | `required_approval_present` | day; first step 5; flagged (ADR-0009.R12: approval required treated as human-only posting) | For every posted document whose policy decision on the posted version requires a rank, every stage of the approval plan of the decision its Post used (for an e-invoiced document, the decision of its Issue) has at least its required number of counted approved approvals on that version within the round that Post or Issue ended (ADR-0055.R8, ADR-0055.R18); documents whose outcome is `human_only` are excluded. | R234 |
| `INV-83` | `attachment_links_resolve` | day; first step 1 | Every `attachment_link` points to an existing row of its target table within the attachment's company. | R234 |

## Edge cases

| ID | Case | Outcome | Rule |
| --- | --- | --- | --- |
| `EC-22` | `price_below_cost`: a sales price below the item's current cost. Interim, flagged (ADR-0047.R22): `is_price_below_cost` feeds the policy; the outcome is the company's rules. | `must_succeed` | R255 |

## Settings

No setting key is used by the rules of this chunk. The duplicate-detection threshold of R206 is company configuration without a named key.

Reads: `tax.default_item_tax_group`, `ui.post_review` (named by notes of other modules' rules traced `ref:` in this chunk).

## Conflicts

CONFLICT ADR-0019.R5: the DDL and ADR-0080.R3 add `is_tax_zone` to `partner_address`, a determinant of the tax treatment rule; R201 states it.
CONFLICT ADR-0019.R7: the personal-label condition reads `partner_kind` `individual` or `sole_proprietorship`, the DDL values, as ADR-0019.R7.N2 and ADR-0053.R7 state; the old value household_business is not used (R204).
CONFLICT ADR-0019.R7.N1: the catalog personal-data-fields.csv governs labels and conditions where the extract in the rule differs, per ADR-0079.R1; stated in R204.
CONFLICT ADR-0023.R1: the rule's own superseded clauses are replaced by ADR-0031.R9 (no ConvertWarehouse, switching through UpdateWarehouse) and ADR-0031.R8 (default bin in transit and goods-sent warehouses); R212 states only these.
CONFLICT ADR-0023.R3.N1: the product boolean is_inspection_required gives way to product inspection_points under ADR-0070.R2; R221 states the list of points and the upgrade mapping.
CONFLICT ADR-0027.R17: the catalog statement of INV-82 now checks approval stages of the decision's plan per ADR-0055.R18 and ADR-0055.R8, not a single approved row; the Invariants table carries it.
CONFLICT ADR-0045.R1: handler validation of group, category and account references gives way to composite company keys on every company-to-company foreign key, per ADR-0017.R19.N3 and the DDL; unit keys stay single-column (R243).
CONFLICT ADR-0045.R3: price entries may target a configurable product instead of an item, per ADR-0046.R15 and the DDL check ck_price_list_entry_target (R247); the clause limiting a product's purchase and sales units to the inventory unit or a product unit is replaced by ADR-0045.R13.N3 and ADR-0018.R12.N1 (any unit the item resolves; R248).
CONFLICT ADR-0045.R3.N1: entry units widen from the inventory unit or a product unit to any unit that convert_quantity resolves, with retirement handling; governs R248.
CONFLICT ADR-0045.R4.N1: the final find_price signature takes item or product and values in the place of option_values; lookup order and result follow ADR-0046.R15 (R249, R251).
CONFLICT ADR-0045.R4.N2: the conversion factor follows the convert_quantity order (item row, product row, conversion pair) with uom_retired for retired rows; stated in R250.
CONFLICT ADR-0045.R5.N1: "below cost" uses the is_price_below_cost definition of ADR-0047.R22 (net after document discount, free goods excluded) rather than the line's net unit price (R255).
CONFLICT ADR-0045.R5.N2: a document whose would-be list has another currency carries no list instead of failing, with check result price_list_currency_differs; only an explicitly named list is rejected (R256).
CONFLICT ADR-0045.R5: the flagged marks on below cost and on list currency equal to document currency are dropped, because ADR-0045.R5.N3 confirms both interim choices (R255, R256).
CONFLICT ADR-0045.R6: the author's delegation note ADR-0045.R5.N3 confirms relative_sales_value from the default sale list net of tax and the actual-average fallback, so R257 and R258 carry no flag.
CONFLICT ADR-0045.R7: the price list commands are not registered is_proposal_bound, per ADR-0045.R7.N2; their master_data_change effect class already binds agents to the carrier (R259).
CONFLICT ADR-0045.R9: closed-project rejection with project_closed and the cost center kinds are confirmed by ADR-0045.R5.N3, so R263 and R264 drop the interim flag.

## Trace

| Source | Where |
| --- | --- |
| ADR-0019.R5 | R201 |
| ADR-0019.R5.N1 | R202 |
| ADR-0019.R6 | R203 |
| ADR-0019.R6.N1 | R203 |
| ADR-0019.R7 | R204 |
| ADR-0019.R7.N1 | R204 |
| ADR-0019.R7.N2 | R204 |
| ADR-0019.R8 | R205 |
| ADR-0019.R19 | R206 |
| ADR-0020.R1 | R210 |
| ADR-0020.R1.N1 | R211 |
| ADR-0020.R2 | ref: ADR-0020.R2 |
| ADR-0020.R2.N1 | ref: ADR-0020.R2.N1 |
| ADR-0020.R11.N3 | ref: ADR-0020.R11.N3 |
| ADR-0020.R11.N5 | ref: ADR-0020.R11.N5 |
| ADR-0020.R17.N1 | ref: ADR-0020.R17.N1 |
| ADR-0021.R4 | ref: ADR-0021.R4 |
| ADR-0021.R13 | R220 |
| ADR-0022.R13 | ref: ADR-0022.R13 |
| ADR-0022.R13.N1 | ref: ADR-0022.R13.N1 |
| ADR-0022.R13.N2 | ref: ADR-0022.R13.N2 |
| ADR-0022.R13.N3 | ref: ADR-0022.R13.N3 |
| ADR-0022.R13.N4 | ref: ADR-0022.R13.N4 |
| ADR-0022.R13.N5 | ref: ADR-0022.R13.N5 |
| ADR-0022.R13.N6 | ref: ADR-0022.R13.N6 |
| ADR-0022.R13.N7 | ref: ADR-0022.R13.N7 |
| ADR-0022.R13.N8 | ref: ADR-0022.R13.N8 |
| ADR-0022.R13.N9 | ref: ADR-0022.R13.N9 |
| ADR-0022.R13.N10 | ref: ADR-0022.R13.N10 |
| ADR-0022.R13.N11 | ref: ADR-0022.R13.N11 |
| ADR-0022.R13.N12 | ref: ADR-0022.R13.N12 |
| ADR-0022.R16.N1 | ref: ADR-0022.R16.N1 |
| ADR-0023.R1 | R212 |
| ADR-0023.R2 | ref: ADR-0023.R2 |
| ADR-0023.R2.N1 | ref: ADR-0023.R2.N1 |
| ADR-0023.R2.N2 | ref: ADR-0023.R2.N2 |
| ADR-0023.R3 | R221 |
| ADR-0023.R3.N1 | R221 |
| ADR-0023.R6 | ref: ADR-0023.R6 |
| ADR-0023.R6.N1 | ref: ADR-0023.R6.N1 |
| ADR-0023.R6.N2 | ref: ADR-0023.R6.N2 |
| ADR-0023.R14 | ref: ADR-0023.R14 |
| ADR-0023.R14.N1 | ref: ADR-0023.R14.N1 |
| ADR-0023.R14.N2 | ref: ADR-0023.R14.N2 |
| ADR-0023.R22.N2 | ref: ADR-0023.R22.N2 |
| ADR-0024.R2 | ref: ADR-0024.R2 |
| ADR-0024.R2.N1 | ref: ADR-0024.R2.N1 |
| ADR-0024.R4 | R225 |
| ADR-0024.R21.N1 | ref: ADR-0024.R21.N1 |
| ADR-0026.R15.N1 | ref: ADR-0026.R15.N1 |
| ADR-0027.D0 | R230 |
| ADR-0027.R5 | R231, R232 |
| ADR-0027.R6 | R233 |
| ADR-0027.R12 | ref: ADR-0027.R12 |
| ADR-0027.R12.N1 | ref: ADR-0027.R12.N1 |
| ADR-0027.R17 | R234 |
| ADR-0029.R1.N1 | ref: ADR-0029.R1.N1 |
| ADR-0029.R5 | ref: ADR-0029.R5 |
| ADR-0029.R5.N1 | ref: ADR-0029.R5.N1 |
| ADR-0029.R5.N2 | ref: ADR-0029.R5.N2 |
| ADR-0030.R9.N1 | ref: ADR-0030.R9.N1 |
| ADR-0031.R7 | R213 |
| ADR-0031.R9 | R212, R214 |
| ADR-0033.R11 | ref: ADR-0033.R11 |
| ADR-0033.R11.N1 | ref: ADR-0033.R11.N1 |
| ADR-0033.R11.N2 | ref: ADR-0033.R11.N2 |
| ADR-0037.R1 | R215, R216 |
| ADR-0038.R2 | ref: ADR-0038.R2 |
| ADR-0038.R2.N1 | ref: ADR-0038.R2.N1 |
| ADR-0038.R2.N2 | ref: ADR-0038.R2.N2 |
| ADR-0038.R2.N3 | ref: ADR-0038.R2.N3 |
| ADR-0038.R2.N4 | ref: ADR-0038.R2.N4 |
| ADR-0038.R4 | ref: ADR-0038.R4 |
| ADR-0038.R4.N1 | ref: ADR-0038.R4.N1 |
| ADR-0038.R4.N2 | ref: ADR-0038.R4.N2 |
| ADR-0038.R4.N3 | ref: ADR-0038.R4.N3 |
| ADR-0038.R4.N4 | ref: ADR-0038.R4.N4 |
| ADR-0038.R9 | ref: ADR-0038.R9 |
| ADR-0038.R9.N1 | ref: ADR-0038.R9.N1 |
| ADR-0039.R5 | ref: ADR-0039.R5 |
| ADR-0039.R7 | ref: ADR-0039.R7 |
| ADR-0041.R2.N1 | ref: ADR-0041.R2.N1 |
| ADR-0041.R3 | ref: ADR-0041.R3 |
| ADR-0041.R3.N1 | ref: ADR-0041.R3.N1 |
| ADR-0041.R3.N2 | ref: ADR-0041.R3.N2 |
| ADR-0041.R3.N3 | ref: ADR-0041.R3.N3 |
| ADR-0041.R4.N1 | ref: ADR-0041.R4.N1 |
| ADR-0041.R7.N1 | ref: ADR-0041.R7.N1 |
| ADR-0041.R9 | ref: ADR-0041.R9 |
| ADR-0041.R13 | ref: ADR-0041.R13 |
| ADR-0041.R13.N1 | ref: ADR-0041.R13.N1 |
| ADR-0041.R13.N2 | ref: ADR-0041.R13.N2 |
| ADR-0043.R2 | ref: ADR-0043.R2 |
| ADR-0043.R2.N1 | ref: ADR-0043.R2.N1 |
| ADR-0044.R3.N6 | ref: ADR-0044.R3.N6 |
| ADR-0044.R5.N1 | ref: ADR-0044.R5.N1 |
| ADR-0045.D0 | R240 |
| ADR-0045.R1 | R241, R242, R243, R244 |
| ADR-0045.R1.N1 | R242 |
| ADR-0045.R2 | R245, R246 |
| ADR-0045.R3 | R247, R248 |
| ADR-0045.R3.N1 | R248 |
| ADR-0045.R4 | R249, R250, R251 |
| ADR-0045.R4.N1 | R249, R251 |
| ADR-0045.R4.N2 | R250 |
| ADR-0045.R5 | R252, R253, R254, R255, R256 |
| ADR-0045.R5.N1 | R255 |
| ADR-0045.R5.N2 | R256 |
| ADR-0045.R5.N3 | R255, R256, R257, R258, R263, R264, R403 |
| ADR-0045.R6 | R257, R258 |
| ADR-0045.R7 | R259 |
| ADR-0045.R7.N1 | R260 |
| ADR-0045.R7.N2 | R259 |
| ADR-0045.R8 | R261, R262 |
| ADR-0045.R9 | R263, R264 |
| ADR-0045.R9.N1 | R263, R264 |
