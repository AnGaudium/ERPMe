Module: inventory    Chunk: 1 of 7    Source ADRs: ADR-0006, ADR-0020
Build step(s): 0    Generated from index: 30d5706    Compiled by: Claude Opus 5.5, 2026-11-21

# Compiled spec: `inventory`, chunk 1 (inventory model, warehouses, material documents, movement types, stock tables, preliminary price)

## Purpose

`inventory` is a layer 3 (core business) module (`ADR-0022.R2`). It owns material documents, the movement type catalog, stock quantity and stock value, the stock lock helper, preliminary prices, period-end actual costing, landed cost, warehouse management and the stock documents. This chunk states the inventory model of ADR-0020 (warehouses, valuation areas, material documents, movement types, transfers, reversals, stock tables, negative stock and the preliminary price) and the rounding rule of ADR-0006 for inventory. Actual costing, landed cost, warehouse management, stock documents and the later rules are in the other chunks. `inventory` does not own warehouses, sites, items, products, documents or journal lines; it reads them.

## Entities and tables

DDL: `docs/design/DS-22-09-42-commercial-inventory.sql`.

| Table | Meaning | Key | Parent | Owner |
| --- | --- | --- | --- | --- |
| `movement_type` | Global catalog row of a movement type (R7) | `id` (uuid5), unique `code` | none | inventory |
| `material_document` | Quantity side of one posting document (R5) | `id`, unique `document_id` | `document` | inventory |
| `material_document_line` | One stock movement with quantity and value (R5, R6) | `id`, unique (`material_document_id`, `line_number`) | `material_document` | inventory |
| `stock_quantity` | Quantity on hand per stock key (R20) | `id`, unique key of R20 (NULLS NOT DISTINCT) | `item`, `warehouse`, `bin` | inventory |
| `stock_value` | Value per item and warehouse; the lock row of the helper (R20, R21) | `id`, unique (`company_id`, `item_id`, `warehouse_id`, `valuation_type`) | `item`, `warehouse` | inventory |
| `preliminary_price` | Price issues use per item, valuation area and posting period (R23) | `id`, unique (`company_id`, `item_id`, `valuation_site_id`, `valuation_warehouse_id`, `posting_period_id`) | `item`, `posting_period` | inventory |

Named by rules of this chunk, with their rows in other chunks: `bin`, `lot`, `serial_number`, `handling_unit`, `return_from_customer_line`.

Reads: `company` (`valuation_area_level`), `warehouse`, `site`, `branch`, `partner`, `item`, `product`, `supplier_item`, `document`, `journal_line`, `posting_period`, `derivation_trace`, `cost_object`, `cost_estimate`.

## Commands and queries

Authorization, input details and events are given only where the sources of this chunk state them.

| Name | Actor / authorization | Input | Effect | Events | Error codes |
| --- | --- | --- | --- | --- | --- |
| `UpdatePreliminaryPrice` | `human_only`, audited; area not stated | a preliminary price for an item and valuation area (R24) | sets a manual `preliminary_price` row with `price_source` `manual` (R23, R24, R25) | not stated | not stated |

Not registered commands: the stock lock helper (R20, R21, R22) and its functions and views, through which every stock posting and every read of `stock_quantity` and `stock_value` goes.

Error codes raised on the posting path: `negative_stock` (R17, R22), `preliminary_price_missing` (R24), `regime_configuration_missing` (R10), `warehouse_site_fixed` (R3).

## Rules

### Inventory model

R1. Quantities move in material documents and values move in journal entries; both belong to the same posting document and are written in the same transaction. Every material document line has a movement type from a core catalog that gives its direction, how its value is found, its role in costing and which transaction key offsets it; where these are accounting rules (returns, count differences) the catalog leaves them to a required regime setting (R10). Stock quantity is kept per item, warehouse and lot or serial, and stock value per item and warehouse, both changed only through the stock lock helper, serialized per (item, warehouse), so stock never goes negative (Principle 9). Phase 1 uses periodic weighted average (D6): issues carry a deterministic preliminary price, and period-end actual costing computes each item's actual average per valuation area by an exact solve over all areas linked by transfers, then posts value-only adjustments with a derivation trace, never editing earlier lines (`ADR-0020.R12`). Goods in transit and goods sent are warehouses of their own kinds, attached to the valuation area of a physical warehouse, so transfers through them keep the issuing warehouse's average and their own accounts stay equal to the stock report. Lots and serials carry no cost. Bills of materials are Phase 1 (`ADR-0032`); catch weight comes after Phase 1; bins and warehouse management are Phase 1 (`ADR-0023`).
Source: ADR-0020.D0

R2. No rounding difference is absorbed into inventory value or cost without its own line and derivation trace (Principle 6). Costing residuals are posted as explicit lines as DS-09 defines.
Source: ADR-0006.R21

### Warehouses and valuation areas

R3. A `warehouse` belongs to one company and carries `code`, `name`, `kind`, `branch_id`, address and `is_active`. `kind` is `physical`, `transit` (goods the company owns on the way) or `goods_sent` (goods delivered to customers or agents and still owned). A `transit` or `goods_sent` warehouse carries `valuation_warehouse_id`, the physical warehouse whose valuation area it belongs to, and takes the site of that warehouse. A `physical` warehouse carries `site_id` (required) and may carry `processor_partner_id` (`ADR-0037.R1`). A warehouse's site changes only while it has no material document line (`warehouse_site_fixed`). The inventory key of a stock line follows the warehouse kind: `inventory_posting`, `inventory_in_transit_posting`, `inventory_goods_sent_posting` (`ADR-0015`); stock of a physical warehouse with `processor_partner_id` uses `inventory_at_processor_posting`.
Source: ADR-0020.R1, ADR-0020.R1.N1

R4. The company's `valuation_area_level` decides the valuation areas. At `company`, all warehouses of the company form one valuation area. At `site`, all physical warehouses of a site, with their attached transit and goods-sent warehouses, form one area. At `warehouse`, each physical warehouse is an area, together with the transit and goods-sent warehouses attached to it. A line records its area as `valuation_site_id` at level `site`, as `valuation_warehouse_id` at level `warehouse`, and as neither at level `company`; at most one is set. Transfers inside one area are value-neutral, and at level `site` the exact solve of `ADR-0020.R12` runs over sites.
Source: ADR-0020.R2, ADR-0020.R2.N1

### Material documents

R5. A `material_document` belongs to one posting document (`document_id`, unique; `ADR-0014.R2`) and carries `company_id`, `posting_date` and `recorded_at`. Its lines (`material_document_line`) carry `line_number` (unique within the material document), `item_id`, `warehouse_id`, `movement_type_id`, `direction` (`in` or `out`, from the movement type, flipped when `is_reversal` is true), `is_reversal`, `quantity`, `lot_id` or `serial_number_id` when the product is tracked (never both; a serial line has quantity 1), `company_amount` (the value moved, never negative), `valuation_warehouse_id` and `valuation_site_id` (both set by the stock lock helper, `INV-810`), `derivation_trace_id`, `bin_id`, `stock_status` (`available`, `quality_inspection`, `blocked`), `handling_unit_id`, the nullable `cost_object_id` (`ADR-0025.R1`), the reserved `owner_partner_id` (null for own stock; `ADR-0030.R8`), the reserved `catch_weight_quantity` (empty until after Phase 1), the reserved `valuation_type` (never set in Phase 1; `ADR-0020.R17`) and `posting_date` (`ADR-0031.R12`). The DDL also holds `source_line_number` (interim: the posting document's line that caused it). `quantity` is positive, in the item's inventory unit (`ADR-0018.R11`), and is the source document line's `inventory_quantity`; the entered unit and its snapshot stay on the document line (`ADR-0056.R1`, `ADR-0056.R9`). `company_amount` is in company currency only (`ADR-0011.R6.N2`).
Source: ADR-0020.R3, ADR-0020.R3.N1, ADR-0020.R3.N2

R6. Material document lines are append-only, protected by triggers like journal rows (`ADR-0014.R13`); the journal line that posts each value refers to its material line. `bin_id` is NOT NULL: a warehouse that is not bin-managed uses its default bin (`ADR-0031.R8`). With warehouse management, `bin_id`, `stock_status` and `handling_unit_id` are active and filled where managed, and moves inside a warehouse are warehouse movements, not material lines (`ADR-0023.R4`, `ADR-0023.R7`, `ADR-0023.R8`).
Source: ADR-0020.R3

### Movement types

R7. The movement type catalog is `docs/catalogs/movement-types.csv`: a core catalog with uuid5 IDs, versioned like the system chart, 0.x until the step 0 gate (`ADR-0010.R9`), loaded into `movement_type`. Each type declares `code`, `name`, `direction`, `value_source`, `costing_role`, `offset_transaction_key` (empty for transfers), `needs_reference` and its nearest SAP analog (`sap_analog`). The catalog file is the authority for the number of types. `value_source` is `document` (from the document), `preliminary_price`, `issuing_value` (the value that left, for the receiving side of a transfer) or `regime` (R10).
Source: ADR-0020.R4, ADR-0020.R4.N1

R8. `costing_role` is one of: `receipt` (enters the period's receipts, negative when the direction is out); `revalued_issue` (valued at the preliminary price and revalued at period end); `issue_return` (a negative issue that names the original issue line it returns: for a sales return receipt, the delivery's material line, through `return_from_customer_line.delivery_line_id`; its movement type has `needs_reference` true, and its value source stays `document`); `transfer`; `regime` (R10); `production_input` and `production_output` (`ADR-0035.R19`). No catalog type carries `issue_return` fixed; a regime selects it for `sales_return_receipt` (R14). How it takes part in costing: `ADR-0020.R12`.
Source: ADR-0020.R4, ADR-0020.R4.N3

R9. The catalog types are `purchase_receipt`, `purchase_return`, `sales_issue`, `sales_return_receipt`, `transfer_out`, `transfer_in`, `stock_count_shortage`, `stock_count_surplus`, `internal_consumption`, `other_receipt`, `other_issue`, `scrap` and `opening_balance`; the production types `production_issue`, `production_return`, `production_receipt`, `co_product_receipt`, `by_product_receipt`, `disassembly_issue` and `disassembly_receipt`, Phase 1 (`ADR-0034`; rows by DS-53); `free_goods_issue` (`ADR-0047.R17`); and `quality_sample` (out, preliminary price, offset `consumption`), used by `internal_consumption` lines for samples destroyed by testing (`ADR-0070.R15`). Moving goods into or out of transit or goods-sent warehouses is a transfer; selling goods sent is a sales issue from the goods-sent warehouse. The transaction key catalog holds the keys `other_receipt_offset`, `other_issue_offset` and `scrap` for these types.
Source: ADR-0020.R4, ADR-0020.R4.N2

### Regime-valued movement types

R10. The value source and costing role of `purchase_return`, `sales_return_receipt`, `stock_count_shortage` and `stock_count_surplus` are accounting rules, so the catalog marks them `regime` and the core reads them only from the required regime settings `movement_type.<code>.value_source` and `movement_type.<code>.costing_role` (`ADR-0016.R10`). A posting without them fails with `regime_configuration_missing`, and an `unverified` value is refused in production (`ADR-0016.R12`). The keys are rows of `settings.csv` with no core default: `movement_type.purchase_return.value_source`, `movement_type.purchase_return.costing_role`, `movement_type.sales_return_receipt.value_source`, `movement_type.sales_return_receipt.costing_role`, `movement_type.stock_count_shortage.value_source`, `movement_type.stock_count_shortage.costing_role`, `movement_type.stock_count_surplus.value_source` and `movement_type.stock_count_surplus.costing_role`. `by_product_receipt` is valued by the regime too (`ADR-0035.R13`). The values a localization package seeds for these keys (DS-19; TT99 seeds: `ADR-0039.R9`) are flagged package content of that package, with basis `unverified`; the core states none of them.
Source: ADR-0020.R5, ADR-0020.R5.N3

R11. A regime may open the `purchase_return` keys as company options with the pairs (`document`, `receipt`) and (`preliminary_price`, `revalued_issue`), changed only from a period start. The optional key `movement_type.purchase_return.include_landed_cost` (core default true) makes a return carry its receipt's proportional share of allocated landed cost; a return posted after a late landed cost carries its share the same way (`ADR-0021.R6.N2`). Each return stamps the options in force on its posting date (`ADR-0063.R24`; `INV-715`).
Source: ADR-0020.R5.N2, ADR-0020.R5.N1

R12. Under the catalog's interim seed a `purchase_return` has value source `document` and costing role `receipt`: a negative receipt. For a return of goods received against a purchase order line, the document value is the GR/IR debit of the positions the return debits, round(V(R)) − round(V(R − q)) at the line's latest received positions (`ADR-0047.R13`; `ADR-0056.R10`). That value leaves stock and reduces the period's receipts, and the return posts no price difference. While the order line has one GR/IR price this equals the value of the receipt the return names; after a change order it may not. A regime that sets another value source, such as the current average, posts the difference from the GR/IR debit as a price difference on the return (`ADR-0047.R13`).
Source: ADR-0020.R5.N1

R13. Count differences (author's delegation, 2026-11-19): regime packages seed `stock_count_shortage` and `stock_count_surplus` at the preliminary price, the shortage revalued at period end (`revalued_issue`) and the surplus joining the receipts (`receipt`). The keys stay required regime settings with no core default (`ADR-0075.R15`).
Source: ADR-0020.R5.N4

R14. A sales return takes the original delivery line's issue cost (the author, 2026-11-21; a deliberate deviation from SAP). The core mechanism is the costing role `issue_return`, built in Phase 1: with it the document value of a `sales_return_receipt` is the original delivery line's issue cost for the returned quantity, a negative issue outside the period's receipt average. The allowed pairs of `movement_type.sales_return_receipt.value_source` and `movement_type.sales_return_receipt.costing_role` are (`document`, `receipt`), (`preliminary_price`, `revalued_issue`) and (`document`, `issue_return`); which pair a regime uses stays a required regime setting with no core default. The catalog's interim seed for `sales_return_receipt` is (`document`, `issue_return`). The Vietnam package's own seed is flagged package content and changes in its rework (DS-19).
Source: ADR-0020.R5.N4, ADR-0020.R5.N5, ADR-0020.R5.N6

### Transfers

R15. A transfer posts both stock lines at the issuing value, and each stock line always has its journal line (credit on the issuing warehouse, debit on the receiving one, carrying their `warehouse_id`), even when both determine the same operational account. So material line values equal their journal lines, inventory value per warehouse as a view over `journal_line` (`ADR-0014.R17`) equals `stock_value`, and every inventory account equals the stock value of its warehouses. A transfer between valuation areas moves at the issuing area's average: preliminary during the period, actual after costing.
Source: ADR-0020.R6

### Reversal of stock documents

R16. Reversible stock document types are transfers, stock counts, internal consumption, other receipts and issues, scrap and opening balances, as internal documents (`ADR-0009.R19`). Their typed headers and lines: the stock transfer, the stock count, scrap and internal consumption (`ADR-0075.R1` to `ADR-0075.R6`), other receipts and other issues (`ADR-0075.R11`, `ADR-0075.R12`) and the opening balance (`ADR-0075.R13`); the non-posting transfer order is `ADR-0075.R14`. `goods_receipt` and `delivery` follow the flagged interim of `ADR-0009.R19` (reversible while no document that is not reversed or canceled refers to them; `ADR-0027.R13`), with their flags set by the DS-09 stock documents deliverable; otherwise they are corrected by return documents (`ADR-0009.R23`).
Source: ADR-0020.R7, ADR-0020.R7.N1

R17. A reversal repeats the lines with `is_reversal` true and the opposite direction; each line keeps its type's costing role with the opposite sign (a negative receipt, a negative issue). Its value is the original line's value, a core rule following SAP (the author, 2026-11-21; `ADR-0009.R20` note): the value the original line carries when the reversal posts, its posted amount plus every value-only revaluation posted for it (`ADR-0020.R12`). A reversal is refused when the stock it returns has been consumed, by the check of R22 (`negative_stock`; `ADR-0009.R18`), and the degenerate cases of `ADR-0020.R13` apply to it. Reversal with bins: `ADR-0023.R9`. `settings.csv` holds no key for the reversal value; the `l10n_vn` package's `reversal.material_document_value` goes in its rework.
Source: ADR-0020.R7, ADR-0020.R7.N3

R18. In the period solve a reversal line behaves like an `issue_return` line turned around (chief architect, interim, 2026-11-21):
- in the same period and valuation area as the original, the pair is revalued together at the period's price and nets to zero (a reversed receipt nets out of the receipts, a reversed issue out of the revalued issues);
- in a later period it is a fixed-value line, counted neither in the receipts nor among the revalued issues; its difference from the period's average times its quantity stays in the area's closing value, or goes to the `ADR-0020.R13` residual when the closing quantity is zero;
- when a later rerun revalues the original (`ADR-0020.R14`), the reversal follows by a value-only adjustment posted by the costing of the reversal's own period.
The costing role of R17 only says which side of the solve the line sits on, and this holds for the reversal of an `issue_return` line too.
Source: ADR-0020.R7.N3

R19. Where a return document is reversed, the reversal of an `issue_return` line is an `issue_return` line of the opposite sign that names the same original line, valued at the reversed line's value (R17). The solve treats it with the line it reverses (`ADR-0020.R12`): revalued with the original when the original is in the period being costed, otherwise kept at its value, so the two net to zero.
Source: ADR-0020.R7.N2

### Stock tables and the stock lock helper

R20. `stock_quantity` holds quantity per (`company_id`, `item_id`, `warehouse_id`, `bin_id`, `lot_id`, `serial_number_id`, `stock_status`, `handling_unit_id`, `owner_partner_id`), a null lot, serial, handling unit or owner counting as one value. `owner_partner_id` is null for own stock, and non-owned stock has no value (`ADR-0030.R8`). Every warehouse has a default bin, so the bin is never null (`ADR-0031.R7`, `ADR-0031.R8`); warehouse movements also change the quantity key (`ADR-0023.R4`, `ADR-0023.R8`). `stock_value` holds value per (`company_id`, `item_id`, `warehouse_id`, `valuation_type`), unique with NULLS NOT DISTINCT; `valuation_type` is reserved, nullable and never set in Phase 1 (`ADR-0020.R17`). A split-valued item is lot-tracked and each lot carries one valuation type, so the quantity key keeps its lot axis and does not change. The stock valuation report sums `stock_value` per item, valuation area and inventory account; the inventory-control accounts equal it (DS-16). Both tables are written only through the stock lock helper in the posting transaction and read only through its functions and views (`ADR-0008.R10`); no other SQL or trigger writes them.
Source: ADR-0020.R8, ADR-0020.R8.N1

R21. The stock lock helper locks, for every (item, warehouse) a document touches, its `stock_value` row (created on first use), in ascending order of item and warehouse IDs, before any numbering lock; quantity rows of lots and serials are reached only under that lock. Value-only inventory journal lines (landed cost added to stock, price differences to stock, costing adjustments) carry item and warehouse (`ADR-0014.R10`) and go through the same helper, which updates `stock_value`; `ADR-0010.R5` counts them as postings through the inventory module. A late landed cost, price difference or exchange-rate difference sent to stock is such a line: a value-only `receipt_addition` in the period of the cost document's own posting date, a period that is not locked; it enters that period's actual average, no locked period is recomputed and nothing is allocated to past consumers (`ADR-0021.R6.N2`). Warehouse movements and reservations use the same helper; the complete lock order, per command, is `ADR-0027.R10`.
Source: ADR-0020.R9

### Negative stock

R22. No stock quantity may be negative, and a serial number never has more than one unit on hand. Under the helper's lock, a posting is rejected with `negative_stock` if, for any (item, warehouse, lot or serial) it touches, the closing quantity of its posting date or of any later date would fall below zero; quantities within one day are not ordered (`ADR-0007.R10`). This end-of-day rule is the answer for backdated postings, not a flagged interim. The dated check stays per (item, warehouse, lot or serial); bins, statuses and handling units are checked on their current balance (`ADR-0023.R5`). The check reads `material_document_line.posting_date` through its index, per key on the document's net change, by the algorithm of `ADR-0031.R14`.
Source: ADR-0020.R10, ADR-0020.R10.N1

### Price control and preliminary price

R23. Price control is `periodic_average` (`ADR-0018.R3`; D6). `preliminary_price` rows hold, per (item, valuation area, posting period), the price issues use. The area is the pair (`valuation_site_id`, `valuation_warehouse_id`), at most one set, and the row is unique per (`company_id`, `item_id`, `valuation_site_id`, `valuation_warehouse_id`, `posting_period_id`) with NULLS NOT DISTINCT. A row carries `unit_price` (company currency per inventory unit, never negative), `price_source`, `derivation_trace_id` and `set_by_user_id`, which is set when and only when `price_source` is `manual`. `price_source` is one of `prior_actual`, `area_receipt`, `company_receipt`, `cost_estimate`, `purchase_list`, `last_purchase_invoice`, `opening`, `manual`; a rule states `purchase_list` and `last_purchase_invoice` (R24), and the other values are interim in the DDL.
Source: ADR-0020.R11, ADR-0020.R11.N3

R24. The preliminary price of an item, valuation area and period N is the first of:
1. when period N−1 has an actual average for the item and area, that average;
2. the unit value of the latest movement with costing role `receipt`, `production_output` or a `transfer_in`, in that area (at level `site`, the site), on or before the line's posting date, ordered by posting date, document type code, document number and `line_number`;
3. the item's latest such price in any area of the company;
4. for an item that is not produced, its supplier purchase list price: `find_price` on the purchase list of the item's preferred `supplier_item` supplier (that supplier profile's purchase list, else the company's default purchase list), or on the company's default purchase list when the item has no preferred supplier item, for one inventory unit in the inventory unit, on the line's posting date, in company currency at the applied rate of that date; only entries in the inventory unit qualify, since `find_price` never converts another unit's price down (`ADR-0056.R16`);
5. for an item that is not produced, its last purchase invoice price: the net amount after the document discount divided by the inventory quantity (`ADR-0056.R12`) of the item's latest posted purchase invoice line with a quantity in the company, on or before the posting date (by posting date, document number and `line_number`), in company currency at that invoice's applied rate;
6. for a produced item (one with an active production version of its own or of its configurable product, `ADR-0033.R13`), its released cost estimate's unit cost (`ADR-0035.R4`): the latest released `cost_estimate` (`ADR-0035.R14`) for the item with costing date on or before the line's posting date, preferring the version whose production warehouse is in the line's valuation area (`ADR-0046.R14` note), price basis the flagged default of `ADR-0035.R14`; a purchase list or invoice never prices a produced item;
7. a manual price set with `UpdatePreliminaryPrice`;
8. else a line that needs the preliminary price (an issue, or a count surplus valued at it) is rejected with `preliminary_price_missing`, naming the item, until a receipt exists or a human sets a price.
`price_source` records `purchase_list` or `last_purchase_invoice` for steps 4 and 5 (DS-22-09-42), with a derivation trace naming the list entry or the invoice line.
Source: ADR-0020.R11, ADR-0020.R11.N1, ADR-0020.R11.N2, ADR-0020.R11.N3

R25. A line valued at the preliminary price takes `round_amount(quantity × preliminary price)` (`ADR-0006.R18`). `UpdatePreliminaryPrice` is `human_only` and audited, since under `ADR-0020.R13` a manual price can become the final cost. At migration, the opening value per item and valuation area divided by its quantity is the first preliminary price (`ADR-0044.R9`). Purchase receipts post at document value and issues at the preliminary price, which the fallbacks can change inside a period; the author keeps this as a recorded deviation from SAP (2026-11-21).
Source: ADR-0020.R11, ADR-0020.R11.N4

R26. `periodic_average` corresponds to SAP's standard price with actual costing, with the preliminary price in the place of the period's standard price, except the in-period valuation of R25. Phase 1 keeps the single value on the product (`ADR-0018.R3`, `ADR-0018.R18`). No posted row stores price control (no column on `material_document_line`, `stock_value`, `journal_line` or `preliminary_price`; only `product.price_control` in DS-20), so no seam is added now. The ADR written after Phase 1 for the standard-price option decides between standard price with variance postings and no actual costing, and standard price with actual costing, where the standard price only takes the place of the preliminary price; its granularity is item and valuation area with the reserved `valuation_type` (`ADR-0018.R3` note), and it adds a `price_source` value. A moving-average option, if ever added, stays outside periodic actual costing: its items are not revalued by `ADR-0020.R12`.
Source: ADR-0020.R11.N5

## Invariants

Statements are those of `invariants.csv`. Each row stands once in the module, in the chunk that states the rule its catalog source names.

| Invariant | Name | Check point | Statement | Protects |
| --- | --- | --- | --- | --- |
| `INV-20` | `inventory_accounts_equal_valuation` | day | The balance of every account with control kind inventory equals the stock valuation report for that account, per warehouse. | R15, R20 |
| `INV-21` | `no_negative_stock` | day | No closing quantity per item, warehouse and lot or serial is negative at the end of any date. The catalog's flag (negative-stock time point) is answered by R22. | R22 |
| `INV-22` | `serial_at_most_one` | day | No serial number has more than one unit on hand on any date. | R22 |
| `INV-23` | `material_lines_equal_journal` | day | Every material document line's `company_amount` equals the journal lines that refer to it. | R6, R15 |
| `INV-24` | `stock_tables_equal_movements` | day | `stock_quantity` equals the sum of material line quantities, and `stock_value` the sum of inventory journal amounts, per their keys. | R20, R21 |
| `INV-25` | `transfer_value_conserved` | day | On every transfer document, the value received equals the value issued per item. | R15 |
| `INV-29` | `stock_reversal_returns_quantities` | day | A reversed stock document's reversal lines return exactly the original quantities per item, warehouse and lot, with `is_reversal` true. | R17 |
| `INV-715` | `purchase_return_option_stamped` | day | Every purchase return movement records the value source, costing role and landed-cost choice in force on its posting date, and those options change only at period starts. | R11 |

Named by rules of this chunk, with their rows in other chunks: `INV-810` (R5).

## Edge cases

| Edge case | Name | Case | Outcome | Protects |
| --- | --- | --- | --- | --- |
| `EC-07` | `negative_stock_attempt` | An issue or backdated transfer that would make stock negative on its date or a later date. | `must_reject:negative_stock` | R22 |
| `EC-09` | `transfer_different_average` | A transfer between warehouses whose averages differ, under warehouse-level valuation. | `must_succeed` | R15 |
| `EC-10` | `transfer_through_transit` | Goods moved to a transit warehouse and received days later, across a month end once. | `must_succeed` | R3, R15 |
| `EC-17` | `preliminary_price_missing` | A count surplus of an item that has never had a receipt or price. | `must_reject:preliminary_price_missing` | R24 |

Named by rules of this chunk, with their rows in other chunks: `EC-338` (R13).

## Settings

| Key | Value type | Scopes | Core default | Used by |
| --- | --- | --- | --- | --- |
| `movement_type.purchase_return.value_source` | enum: `document`, `preliminary_price` | `regime`, `company` | none (fails closed) | R10, R11, R12 |
| `movement_type.purchase_return.costing_role` | enum: `receipt`, `revalued_issue` | `regime`, `company` | none (fails closed) | R10, R11, R12 |
| `movement_type.sales_return_receipt.value_source` | enum: `document`, `preliminary_price` | `regime`, `company` | none (fails closed) | R10, R14 |
| `movement_type.sales_return_receipt.costing_role` | enum: `receipt`, `revalued_issue`, `issue_return` | `regime`, `company` | none (fails closed) | R10, R14 |

Named by rules of this chunk, with their rows in other chunks: `movement_type.purchase_return.include_landed_cost` (R11), `movement_type.stock_count_shortage.value_source`, `movement_type.stock_count_shortage.costing_role`, `movement_type.stock_count_surplus.value_source` and `movement_type.stock_count_surplus.costing_role` (R10, R13), and `costing.exchange_rate_difference_to_stock` (named by `ADR-0011.R6.N2`).

## Conflicts

CONFLICT ADR-0020.D0: bills of materials moved from Phase 2 into Phase 1 by ADR-0032, as the closing sentences of ADR-0020.R4 and ADR-0020.R12 say, so R1 states them as Phase 1.
CONFLICT ADR-0020.R3: closing sentences citing ADR-0031.R8, ADR-0023.R4 and ADR-0030.R8 make `bin_id` mandatory and active and add status, handling unit, owner and posting date; the DDL column list governs R5 and R6.
CONFLICT ADR-0020.R4: the type totals of catalog version 0.1.0 are historical; ADR-0020.R4.N1 makes the catalog file the authority, and the rule's own closing sentence citing ADR-0034 moves production types into Phase 1 (R7, R9).
CONFLICT ADR-0020.R5: the open questions on sales return cost and count difference valuation are answered by ADR-0020.R5.N4, ADR-0020.R5.N5 and ADR-0020.R5.N6 (R13, R14); package seed values are not restated under the country-values rule.
CONFLICT ADR-0020.R5.N1: whether a purchase return carries landed cost allocated to its receipt is no longer open; ADR-0020.R5.N2 and case (c) of ADR-0021.R6.N2 (late cost booked in the cost document's period) govern, stated in R11.
CONFLICT ADR-0020.R5.N3: its remark that the interim seed of the sales return pair remains open is settled by the author's confirmation in ADR-0020.R5.N6, seed (`document`, `issue_return`), stated in R14.
CONFLICT ADR-0020.R5.N4: its sentence keeping the sales return question open until a costing role exists is superseded by ADR-0020.R5.N5, which adds `issue_return`, and the author's ADR-0020.R5.N6 (R14).
CONFLICT ADR-0020.R7: the flagged regime setting for a reversed material document's value is replaced by the core rule of ADR-0020.R7.N3, and ADR-0027.R13 aligns goods receipts and deliveries with the flagged interim of ADR-0009.R19 (R16, R17).
CONFLICT ADR-0020.R7.N2: the interim mark on the value of a reversed `issue_return` line is dropped, because the author's ADR-0020.R7.N3 makes the original line's value a core rule (R19).
CONFLICT ADR-0020.R7.N3: this author note of 2026-11-21 governs ADR-0020.R7; the reversal value is no longer a flagged regime setting but the original line's current value, with the solve cases of R18.
CONFLICT ADR-0020.R8: the stock keys grew through ADR-0023.R4, ADR-0023.R8, ADR-0030.R8, ADR-0031.R8 and ADR-0020.R8.N1; the DDL unique keys are stated in R20.
CONFLICT ADR-0020.R10: the flagged interim end-of-day check for backdated documents is confirmed as the answer by ADR-0020.R10.N1, so R22 states it without the flag.
CONFLICT ADR-0020.R10.N1: the S2 open-questions note confirms the dated negative-stock check and governs ADR-0020.R10 and the flag column of `INV-21` (R22).

## Trace

| Source | Where |
| --- | --- |
| ADR-0004.R9 | ref: ADR-0004.R9 |
| ADR-0006.R21 | R2 |
| ADR-0007.R2 | ref: ADR-0007.R2 |
| ADR-0009.R1 | ref: ADR-0009.R1 |
| ADR-0009.R1.N1 | ref: ADR-0009.R1.N1 |
| ADR-0009.R1.N2 | ref: ADR-0009.R1.N2 |
| ADR-0009.R7 | ref: ADR-0009.R7 |
| ADR-0009.R19 | ref: ADR-0009.R19 |
| ADR-0009.R19.N1 | ref: ADR-0009.R19.N1 |
| ADR-0011.R6.N2 | ref: ADR-0011.R6.N2 |
| ADR-0019.R5 | ref: ADR-0019.R5 |
| ADR-0019.R5.N1 | ref: ADR-0019.R5.N1 |
| ADR-0020.D0 | R1 |
| ADR-0020.R1 | R3 |
| ADR-0020.R1.N1 | R3 |
| ADR-0020.R2 | R4 |
| ADR-0020.R2.N1 | R4 |
| ADR-0020.R3 | R5, R6 |
| ADR-0020.R3.N1 | R5 |
| ADR-0020.R3.N2 | R5 |
| ADR-0020.R4 | R7, R8, R9 |
| ADR-0020.R4.N1 | R7 |
| ADR-0020.R4.N2 | R9 |
| ADR-0020.R4.N3 | R8 |
| ADR-0020.R5 | R10 |
| ADR-0020.R5.N1 | R11, R12 |
| ADR-0020.R5.N2 | R11 |
| ADR-0020.R5.N3 | R10 |
| ADR-0020.R5.N4 | R13, R14 |
| ADR-0020.R5.N5 | R14 |
| ADR-0020.R5.N6 | R14 |
| ADR-0020.R6 | R15 |
| ADR-0020.R7 | R16, R17 |
| ADR-0020.R7.N1 | R16 |
| ADR-0020.R7.N2 | R19 |
| ADR-0020.R7.N3 | R17, R18 |
| ADR-0020.R8 | R20 |
| ADR-0020.R8.N1 | R20 |
| ADR-0020.R9 | R21 |
| ADR-0020.R10 | R22 |
| ADR-0020.R10.N1 | R22 |
| ADR-0020.R11 | R23, R24, R25 |
| ADR-0020.R11.N1 | R24 |
| ADR-0020.R11.N2 | R24 |
| ADR-0020.R11.N3 | R23, R24 |
| ADR-0020.R11.N4 | R25 |
| ADR-0020.R11.N5 | R26 |
