# Multi-UoM audit (holistic review)

Repo `~/Projects/NativeFlows`, branch `holistic-review`, HEAD 32e7b1c. Read-only audit, 2026-11-15.
Paths are under `docs/`. `0018:33` means `adr/0018-…md` line 33; `DS-20:403` means `design/DS-20-master-data.sql` line 403;
`DS-22` = `DS-22-09-42-commercial-inventory.sql`; `DS-43` = `DS-43-54-planning-production.sql`; `DS-56` = `DS-56-product-configuration.sql`.

## 0. Verdict

The core of the model is sound and consistent: one inventory unit per product, exact rational factors, entered
quantity + unit + inventory quantity on lines, stock/cost/planning/GR-IR only in the inventory unit, one price lookup.
What is missing is everything that happens when a factor is not exact or when units differ along a document chain,
plus several homes nobody owns (unit seed catalog, unit names for print and e-invoice, counting unit, migration of
units, packaging levels). The six-flow simulation used only `EA` with 0 decimals (lab `t14_commercial_inventory_ddl.py:129`),
so no multi-unit path has been exercised beyond `find_price` (lab `t05_master_data.py:175-235`).

Counts: 3 Blocking, 17 Should-fix, 9 Nit.

## 1. Map: what the design says, per question

### Q1. Where conversions are defined; precedence
- Global: `uom_conversion` (from, to, numerator, denominator), same kind only, core units only. 0018:30; DS-20:43-50; "no `uom_conversion` row names a company unit" 0045:122.
- Product: `product_uom` (product, uom, numerator/denominator to the inventory unit). 0018:32; DS-20:403-411.
- Precedence: inventory unit (factor 1) → `product_uom` → `uom_conversion` in either direction, inverted → `uom_not_allowed`. 0045:56; "a `product_uom` row wins over `uom_conversion` for the same pair" 0018:32.
- Variant/item: none. "a field lives on exactly one level; nothing is inherited or overridden" 0018:7. Revisit trigger only: "variants that differ in tax group, unit conversion" 0018:103. Item weight and dimensions are per item, "for one inventory unit" 0018:18, and are not conversions.
- Configured item: none (same as item). Supplier: none; `partner_item.uom_id` only maps the partner's unit text to a product unit, DS-20:530-531; `supplier_item` minimum and multiple are "in the purchase unit" 0024:56. Customer: none. Batch/lot: none.
- Bill of materials component: own snapshot `numerator`/`denominator`, DS-43:426-429 (0033:73).
- Judgement: product and global levels **complete**; chaining through `uom_conversion` and a later `product_uom` row overriding a used global pair **ambiguous** (U-05); item/lot level **missing by decision, not recorded as a decision** (U-10).

### Q2. Which units a line may use; the default
- "A document line may use the inventory unit, a unit in `product_uom`, or a unit of the same kind convertible through `uom_conversion`" 0018:32. Price entries and the product's purchase/sales units: inventory unit or product unit only, 0045:54, 0045:120.
- Default: "`purchase_uom_id` and `sales_uom_id` are the units proposed on purchase and sales documents… A line may choose another allowed unit" 0018:34.
- Not stated per document type: delivery/receipt/invoice/return line against an order line in another unit; transfer, count, production issue/receipt, purchase request from planning; whether `partner_item.uom_id` beats `purchase_uom_id` as the default. **Ambiguous** (U-02, U-08, U-13).

### Q3. How lines store quantity and price; where rounding happens
- "A document line stores its quantity and unit as entered, and its quantity in the inventory unit, computed as `round_quantity(quantity × numerator / denominator, inventory unit)`… `quantity_rounded`… `quantity_rounds_to_zero`… the line's amount is computed from its own quantity and price" 0018:33; 0047:54; 0006:46.
- Input with more decimals than the unit allows is rejected, 0006:41. Line amount `round_amount(quantity × stored net unit price)` 0047:191. So price is per entered unit (implicit, never said in one sentence).
- No conversion snapshot on commercial lines (DS-22: `quantity`, `uom_id`, `inventory_quantity` only). Bill of materials components do snapshot. **Inconsistent** between the two families (U-04).
- Rounding points: inventory quantity per line (half up); price fallback × factor to 10 decimals, 0045:58; requirements up, 0033:88; supplier multiple up, 0024:162.
- Judgement: single line **complete**; sums over partial lines **missing** (U-01).

### Q4. Inventory and costing
- "stock quantities and costs are always in it, and conversion happens in the command layer… so costing never sees another unit" 0018:31; spec 07:35. `material_document_line.quantity` inventory unit, 0020:18, DS-22:1062. `stock_quantity`, reservations, tasks, movements, `demand_supply_line.open_quantity`, `planned_order.quantity`: inventory unit (DS-22:1117, 1161, 1190, 1230; DS-43:280, 617). `preliminary_price.unit_price` "per inventory unit" DS-22:1140. No cost layers (periodic average); GR/IR layers are per inventory-unit position, DS-22:1264-1267.
- Judgement: **complete and consistent**. One gap: no invariant ties `inventory_quantity` to `quantity × factor` (U-17).

### Q5. Purchasing
- Order unit: any allowed unit, default `purchase_uom_id`. Price: `find_price(list, item, unit, quantity, date)` 0047:123, 186. No separate order price unit (U-11).
- GR/IR price: "the line's net amount after the document discount, without tax, divided by its inventory quantity, as an exact rational" 0047:131. Positions "in its inventory unit" 0047:155; DS-22:440-441, 451.
- Receipt tolerance: "At most the line's open quantity, read from its supply row, times `1 + inventory.purchase_receipt_tolerance_percent / 100`" 0047:136 (inventory unit; applied to the open, not the ordered, quantity: U-22).
- Three-way match: quantity against "the ordered quantity times `1 + …quantity_tolerance_percent`" 0047:172; price "per inventory unit" by the note 0047:177; `price_tolerance_amount` has no stated unit or currency 0047:173 (U-12).
- Invoice unit: `purchase_invoice_line.uom_id`, DS-22:835. Purchase return, purchase credit note and write-off lines carry only `inventory_quantity`, DS-22:885, 921, 978, against 0047:54 (U-06).
- Judgement: GR/IR **complete**; tolerance units and the chain in mixed units **ambiguous**.

### Q6. Sales
- Entries "per item and unit, with quantity breaks" 0045:52; break "in that unit". Entered unit first, "even where the inventory unit's break would give a lower price", else inventory unit × factor, 0045:57-58. Configured: item entered → item inventory → product entered → product inventory, 0046:188.
- Extras and number rates "per inventory unit", × factor, rounded once, 0045:162-164, 0046:192-193.
- Promotions: `minimum_line_quantity`, `amount_per_unit`, `free_quantity`, `qualifying_quantity` with no unit, DS-22:69-75, 0047:199-205 (U-09).
- Delivery: "At most the line's open quantity: `ordered − (delivered − returned)`" 0047:84, inventory quantities by 0047:54. Returns and credits "at the original line's price" 0047:98, 110 while `sales_return_line` has its own `uom_id` (DS-22:712) and `credit_note_line` has none (DS-22:750) (U-02, U-06).
- No sales minimum order quantity or sales multiple (e.g. sold only in full cartons): **missing** (U-20).

### Q7. Warehouse
- Handling units: pallet/carton/tote, one nesting level, no value, 0023:105-112; `handling_unit_type` has tare and dimensions, DS-20:350-365. No link between a handling unit type and a product unit, no quantity per handling unit, no packaging hierarchy; "Dimensions of packaging units… are not modeled in Phase 1" 0018:18.
- Picking: "Each task carries the demand line's unit and the inventory quantity; the client derives a breakdown such as '2 cartons and 3 bottles' from `product_uom`" 0023:199; DS-22:1190-1191.
- Barcode per packaging unit, 0018:36; DS-20:514-521.
- Counting: 0023:232-237 and 0020:46 name no unit; 0018:32 says a product unit is one it "may be bought, sold or counted in". No DDL for `stock_count` or transfer order lines.
- Judgement: handling units **complete**; packaging levels, counting unit, capacity per packaging unit **missing** (U-13, U-14).

### Q8. Manufacturing
- Base quantity in the main output's inventory unit, 0033:53. Component "`quantity` per base quantity, with its unit and the quantity in the component's inventory unit… exact by `numerator` and `denominator`" 0033:73. Requirement exact, "rounded once per order line, up… to the component's inventory unit" 0033:88; backflush `round_up` cumulative, 0034:183. Order quantities G and Q in the inventory unit, 0034:44.
- Planning: "every planning quantity is in the item's inventory unit. The supplier's minimum and multiple are applied in the purchase unit, then converted exactly. Rounding excess is shown" 0024:74; lot sizing order 0024:159-165; production: method only, version lot range, 0036:61-65. `planned_order.rounding_excess_quantity` DS-43:618.
- Production issue and receipt lines: `quantity` only, no unit (DS-43:971-979, 1056-1065), while 0034:140 says posted lines "keep item, unit and warehouse".
- Judgement: BOM and netting **complete**; the purchase unit of `supplier_item` **ambiguous and fragile** (U-03); no rounding value for production or transfers (U-21); rounding of Q = G / (1 − scrap) not stated (U-23).

### Q9. Variable conversions
- Catch weight: after Phase 1; `product.catch_weight_uom_id` reserved, not created (0018:17; DS-20:382); `material_document_line.catch_weight_quantity` exists and is checked null (DS-22:1071, 1087). Spec 07:34.
- Cut-to-length: only as a configured item per length with linear sizing of the component (0046:151, DS-43:440-441). No remnant, no lot-level length or weight, no density. **Missing, undecided** (U-10).

### Q10. Changing a conversion after use
- "The inventory unit cannot change, and a `product_uom` row cannot be removed or have its conversion changed, once any document line, price list or stock posting uses it" 0018:35. Price entries: unit never changes after start, 0045:87. Used characteristic unit frozen, DS-04:236.
- Not versioned or dated; no stated way out (new unit); not covered: `purchase_uom_id`/`sales_uom_id` ("Other fields can be updated at any time" 0018:51), bill of materials use, `supplier_item`, barcodes, `uom_conversion` rows. **Ambiguous** (U-03, U-05, U-07).

### Q11. Precision
- `types.quantity numeric(24,6)` "at the unit's decimal places, at most 6" 0006:27; `uom.decimal_places` 0..6, DS-20:37; "never change once a unit is used" 0018:30. Factors `bigint`/`bigint`. Unit price 10 decimals.
- Drift: only "A company therefore chooses as inventory unit the smallest unit it sells or counts" 0018:33 and the daily remainder in forecasts, 0024:113. Nothing for sums of rounded lines (U-01). Decimal places are global per unit, so two companies cannot differ on `KGM` (U-15). `quantity_per_value` is `types.quantity` (6 decimals) DS-43:440 (U-24).

### Q12. E-invoice and print unit names
- Codes "UN/ECE Recommendation 20 codes where one exists"; "Names of core units are translated through the core catalogs; names of company units are user data" 0018:30, 48. Print contract: each `<relation>_id` gains code and name, "the name in the print language where a data translation exists" 0049:261.
- "DS-24: unit names on e-invoices" 0018:97; DS-24 is an add-on not yet designed (backlog.md:77). DS-19 has no unit file. `uom` has no `name` column (DS-20:32-40). ADR-0016 rule 18 lists core catalogs for system accounts and transaction keys only (0016:73). No unit catalog in `catalogs/README.md`. **Missing** (U-16).

### Q13. Migration
- 0044:51 "products and items… price lists"; opening stock lines carry "quantity" 0044:100. No word on unit mapping, company units, old decimals, product units, or the unit of sales history. **Missing** (U-18).

### Q14. DDL against ADRs
- Consistent: `uom`, `uom_conversion`, `product`, `product_uom`, `price_list_entry`, the eleven main line tables (quantity, `uom_id`, `inventory_quantity`), material lines, stock, GR/IR.
- Gaps: U-04, U-06, U-08, U-19, U-25 to U-29 below.

## 2. Findings

### Blocking (decide before the multi-unit simulation)

**U-01. Rounded inventory quantities do not add up along a chain.** 0018:33; 0047:54, 58, 84, 136, 155-162.
Each line rounds on its own. Order 3 bags at 7/3 kg (the lab's own case, `t05:49`) = 7.000 kg; three receipts of 1 bag = 3 × 2.333 = 6.999 kg. The order line keeps 0.001 open, never closes "by quantity" (0047:58); an invoice of 3 bags gives I = 7.000 against R = 6.999, so GR/IR keeps a residual that only the human-only `gr_ir_write_off` clears (0047:169). The same happens for deliveries, sales invoices ("delivered net − invoiced net") and returns. Global imperial conversions (lb → kg) are never exact.
Direction: (a) at `product_uom` creation, compute whether one smallest step of the unit converts exactly at the inventory unit's decimals; if not, return a check result `conversion_inexact` and store the flag; (b) for a line that fulfils a source line in the source line's unit, convert cumulatively: inventory quantity = round(cumulative entered × factor) − inventory quantity already posted, as GR/IR does with values; a line that completes the source in entered units takes the rest; (c) add INV and EC rows (U-17). Consider rejecting inexact `product_uom` factors outright (business factors are decimal in practice); then (b) is needed only for `uom_conversion`.

**U-02. Unit rules along a document chain are not stated.** 0018:34; 0047:54-57, 98, 110, 198; 0028:37.
May a receipt, delivery, invoice, return or credit line use another unit than the line it refers to? `sales_return_line` stores its own `uom_id` and "the original's" `net_unit_price` (DS-22:712-714); a price per carton on a line in bottles is wrong. `source_lines` copy "line numbers and quantities" without saying in which unit.
Direction: stock documents (receipt, delivery, stock returns) may use any allowed unit, since they record what was physically handled; money documents that take a price from a source line (invoice from order, returns, credits) use the source line's unit, enforced with `uom_mismatch`; `source_lines` quantities are in the source line's unit. State that every unit price is per the line's `uom_id`.

**U-03. `supplier_item` quantities hang on a mutable product field.** 0024:56, 74; DS-43:135-136; 0018:51.
`minimum_order_quantity` and `order_multiple` are "in the purchase unit", i.e. `product.purchase_uom_id`, which "can be updated at any time" and is one per product, while suppliers differ (one sells cartons of 24, another pallets). Changing the proposal unit silently rescales every supplier minimum. The draft purchase request line from planning has no stated unit (0047:117; `replenishment_request_line` DS-43:781).
Direction: add `uom_id` to `supplier_item` (the supplier's order unit; inventory unit or product unit; default for that supplier's order lines, ahead of `purchase_uom_id`); the planning consumer drafts the request line in that unit with a whole multiple; freeze nothing else.

### Should-fix

**U-04. No conversion snapshot on document lines; BOM lines have one.** DS-22 lines 138-140 etc.; DS-43:426-429.
Because of rounding the factor cannot be recovered from the two quantities, and U-05 shows it can change. Direction: add `uom_numerator`, `uom_denominator` to every line with `uom_id` (cheap, makes a line self-describing for agents and audit), or state in ADR-0018 that the factor is always re-read and close U-05 by rule. Recommended: snapshot.

**U-05. Precedence holes.** 0018:32, 35; 0045:56.
(1) A `product_uom` row added later for a pair already used through `uom_conversion` changes the factor of a used unit; rule 13 freezes only existing rows. (2) Chains (g → kg → t, or product unit → global unit) are not said to be excluded. (3) Nothing says `uom_conversion` rows are immutable or who maintains them. (4) Lab `factor()` reads `uom_conversion` in one direction only (`t05:179-180`) against "a row in either direction".
Direction: one hop only, say so; `uom_conversion` is a core catalog, shipped and immutable; a `product_uom` row for a unit of the inventory unit's kind is refused once that unit is used on the product; fix the lab.

**U-06. Correction lines without the entered unit.** DS-22:744-761 (`credit_note_line`: quantity, no `uom_id`, no `item_id`), 877-890, 914-930, 972-982; against 0047:54.
A credit note is an e-invoiced document and must print a unit; with `external_original` there is no line to take it from. Direction: add `uom_id` (and `quantity` where only `inventory_quantity` exists) to `credit_note_line`, `purchase_return_line`, `purchase_credit_note_line`; `gr_ir_write_off_line` may stay inventory-only, said in ADR-0047.

**U-07. No way out when a real conversion changes.** 0018:35.
A supplier moves from 24 to 20 per carton. The rule forbids the change and names no remedy. Direction: state it: add a new company unit (`x-carton-20`) and retire the old one; add `is_active` to `product_uom` (DS-20:403); a retired unit is refused on new lines and kept for history. Dated factors are not needed.

**U-08. Stock and production documents have no unit design.** No DDL for transfer order lines or `stock_count` (DS-43:289 "key added with transfer orders"); `production_issue_line`, `production_receipt_line` quantity only (DS-43:979, 1065); 0034:140 mentions a "unit".
Direction: decide per type. Recommended: transfer and count lines carry entered quantity + unit + inventory quantity like commercial lines; production issue, receipt and confirmation are inventory unit only in Phase 1 (say so, and drop "unit" from 0034:140).

**U-09. Promotion quantities have no unit.** DS-22:69-75; 0047:199-205.
Scope can be a product or an item group across different units. Direction: `minimum_line_quantity`, `qualifying_quantity`, `free_quantity` are inventory-unit quantities of the line's and the free item; `amount_per_unit` is per inventory unit × factor like option extras (0045:164).

**U-10. Item-level and lot-level conversions are neither supported nor decided.** 0018:7, 32, 103; 0046:44, 151.
Configured items that differ in length have different weight per piece; `product_uom` is per product, so "piece ↔ kg" cannot exist for them, and rolls or bars with a length per lot cannot be modeled. Item `net_weight` is a second, unlinked source of a mass factor. For a manufacturing prospect this is likely to appear early.
Direction: record a Phase 1 decision: keep the measured unit (m, kg) as inventory unit and carry pieces as lots or handling units; no item-level factor. Add an optional derived factor "mass unit through item weight" only if the author confirms the need; keep catch weight for true variable weight.

**U-11. No order price unit.** 0047:186-191.
A line is priced only per its entered unit, so "order 10 pieces, priced per kg" needs the line in kg. Direction: record as a Phase 1 limit next to catch weight (07:34), with the workaround; revisit with catch weight.

**U-12. `purchasing.match.price_tolerance_amount` has no unit or currency.** 0047:173, 177, 293.
Per inventory unit it is meaningless across items (a bottle against a pallet). Direction: define it as the absolute difference of the line's net amount in the order's currency… or drop it and keep the percentage; state the currency.

**U-13. Counting unit and packaging levels.** 0023:199, 232-237; 0018:32, 36.
The pick breakdown "2 cartons and 3 bottles" needs to know which product units are packaging levels; `product_uom` also holds kg or m. Counting names no unit. Direction: add `is_packaging` (or `packaging_level`) to `product_uom`; count lines accept any allowed unit and several lines per key, summed in the inventory unit.

**U-14. Handling unit types and product units are unrelated.** DS-20:350-365, 392; 0018:18.
No quantity per handling unit and no packaging-unit dimensions, so bin capacity for cartons and "whole pallet" proposals rest on item dimensions only. Direction: Phase 1 limit, stated; later add `product_uom.handling_unit_type_id` and dimensions.

**U-15. `decimal_places` is global per unit and has no seed.** 0018:30; DS-20:37; `catalogs/README.md`.
No core unit catalog exists (codes, kinds, decimals, conversions), yet the decimals of `KGM` bind every company forever. Direction: add `catalogs/uom.csv` and `uom-conversions.csv` (owner DS-20) with generous decimals for measured units (3 for mass, length, volume; 0 for count), and let a product narrow the precision later if needed (not now).

**U-16. Unit names for print and e-invoice have no home.** 0018:30, 48, 97; 0049:261; 0016:73; DS-20:32-40.
`uom` has no `name`; core catalogs do not list unit names; DS-19 ships none; DS-24 is undesigned. A Vietnamese e-invoice line needs the unit name as text. Direction: add `name` to `uom` (English source for core rows, the entered name for company rows); core i18n catalog gains `uom.<code>.name` and `.symbol` in en and vi; the print contract's `uom` object gives code, name and symbol in the print language; the e-invoice add-on reads the same name, and `l10n_vn` may override through its terminology catalog.

**U-17. No invariant and one thin edge case.** `catalogs/invariants.csv` (none on units); `edge-cases.csv:15` EC-14 "Bought in cartons, sold in bottles".
Direction: INV: every line's `inventory_quantity` equals the rule of ADR-0018 rule 11 (or U-01's cumulative rule) for its stored factor; quantities are at their unit's decimals; material line quantity equals its source line's inventory quantity. EC: inexact factor with partial receipts; a unit through `uom_conversion`; price fallback from the inventory unit; a barcode of a carton; supplier multiple in cartons; rounding to zero.

**U-18. Migration says nothing about units.** 0044:51, 100-102; DS-17:90-94.
Direction: phase 2 loads company units, product units and barcodes before products' documents; a unit map (old text → `uom`) lives in the batch like the old-account map; opening stock quantities are in the inventory unit or carry a unit; quantities with too many decimals are rejected (0006:41), so the validation lists them with the unit's decimals; sales history is in the inventory unit.

**U-19. `uom_not_allowed` at the line is the only guard; the database holds nothing.** DS-04:219; DS-22 line tables.
Acceptable by ADR-0045 rule 1, but then the invariant of U-17 is the only net. Also `product_uom` does not refuse the inventory unit itself (command rule 0045:120 only). Direction: keep in commands; add the INV.

**U-20. No sales-side minimum or multiple.** 0045:52 (breaks only).
"Sold only in full cartons" cannot be expressed. Direction: Phase 1 limit, or `sales_multiple` on the product in the sales unit as a check result, not an error.

### Nit

- **U-21.** No rounding value for production or transfer proposals (0036:62; 0024:159-165); fixed lot covers most cases. Say so.
- **U-22.** Receipt tolerance multiplies the open quantity (0047:136), so each partial receipt earns tolerance again; base it on the ordered quantity: received net ≤ ordered × (1 + t).
- **U-23.** Rounding of Q = G / (1 − scrap) and of co-product quantities is not stated (0033:86); requirements round up (0033:88).
- **U-24.** `quantity_per_value` is `types.quantity`, 6 decimals (DS-43:440); kg per mm needs more. Use a rational pair or `types.unit_price` scale.
- **U-25.** Composite primary keys on `uom_conversion`, `product_uom`, `item_barcode` (DS-20:48, 409, 519) against ADR-0006 rule 1 (0006:13); a line or trace cannot name the row. Add `id`.
- **U-26.** ADR-0033 rule 6 says a component stores "the quantity in the component's inventory unit"; DS-43:426-429 stores the factor instead, with `DEFAULT 1` that hides a missing factor. Align the text; drop the defaults.
- **U-27.** `uom.is_active` is in the DDL (DS-20:38), not in ADR-0018; `service_receipt_line.inventory_quantity` for a service is a misnomer worth one glossary line.
- **U-28.** `supplier_purchasing_term.volume_uom_id`/`weight_uom_id` are marked interim (DS-43:156-158); item dimensions must convert to them through `uom_conversion`; say so in ADR-0024 rule 2.
- **U-29.** Quantity-based taxes (per litre or kg) and the customs unit (0037:88; 0021:94) have no unit rule; ADR-0041 has none. Leave to the package, but name the seam.

## 3. Suggested order of work
1. Decide U-01, U-02, U-03 (one amendment note each on ADR-0018, ADR-0047, ADR-0024).
2. DDL pass: U-04, U-06, U-07, U-13, U-16, U-25, U-26 in DS-20 / DS-22 / DS-43.
3. Catalogs: U-15, U-17. Then ADR notes for U-05, U-08 to U-12, U-18.
4. Extend the lab: a product with carton 24/1, bag 7/3 and g ↔ kg through the six flows before the test-database simulation.
