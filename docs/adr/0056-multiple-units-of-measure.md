# ADR-0056: Multiple units of measure

Status: accepted (2026-11-15) under ADR-0005, reviewed by Claude Fable 5.2 (builder Claude Opus 5.5) after six review rounds. Design items: DS-20 (units on the item master), DS-22 (document lines), DS-43 and DS-51 (planning and production lines), DS-42 (counts and packaging). Related decisions: D5, D6. Principles 6, 7. ADR-0004, ADR-0006, ADR-0009, ADR-0016, ADR-0018, ADR-0019, ADR-0020, ADR-0023, ADR-0024, ADR-0029, ADR-0030, ADR-0033, ADR-0034, ADR-0041, ADR-0044, ADR-0045, ADR-0046, ADR-0047, ADR-0049, ADR-0051, ADR-0053.

## Decision

ADR-0018 gave each product one inventory unit and exact conversions for its other units, and ADR-0045 and ADR-0047 used them for prices and GR/IR. That core stays. This ADR completes multi-UoM so that the design holds when a factor is not exact, when units differ along a document chain, and when variants of one product convert differently. The author asked for the conversions to be defined on the item master data.

**Inventory unit only for stock.** Stock, value, costing, planning and GR/IR stay in the inventory unit. Every other unit is converted in the command layer when a line is taken in.

**Conversions on the item master.** `product_uom` holds a product's units, and with `item_id` set, an item's own units for one variant or configured item. A conversion is resolved item, then product, then the global `uom_conversion`, by one pure function, `convert_quantity`. Each unit is classified exact or inexact when it is created.

**A snapshot on every line.** Every quantity line stores its entered quantity, unit, the conversion it used (numerator, denominator, source) and its inventory quantity. A line never reads the master data again. Conversions are immutable once used; a changed pack size retires the row, and a new row for the same unit takes over.

**Parts add up.** When a line is received, issued or invoiced in parts in its own unit, each part's inventory quantity is a difference of rounded cumulative quantities, as GR/IR does with values. Parts that complete the line sum exactly to its inventory quantity, and a return or credit takes the part it names as its source, so it never posts more than that part.

**Follow-on lines in any unit.** A receipt, delivery, invoice or return may use any allowed unit of the item. Links, open quantities, tolerances, three-way match and GR/IR compare inventory quantities.

**Supplier order unit, packaging, aliases.** `supplier_item` names the unit in which a supplier's minimum and multiple are stated. Packaging levels are product units with a `contains` relation. A unit alias table lets agents and imports read unit text, and unknown text is never guessed.

Catch weight, batch-specific factors, an order price unit, handling-unit quantities, packaging dimensions, sales multiples and quantity-based taxes come after Phase 1.

### Rules

**Units and conversions**

1. **The inventory unit.** A product's inventory unit (ADR-0018 rule 9) is the only unit of:
   - stock quantities, material document lines, stock values and costing layers;
   - preliminary and actual prices per unit;
   - reservations, warehouse task quantities, demand and supply rows and their open quantities;
   - MRP netting, planned order quantities, planned order components and pegging;
   - GR/IR positions, receipt and match tolerances, and correction limits.

   Every conversion from another unit happens in the command layer, when a line is taken in. Costing, planning and GR/IR never see another unit. This confirms ADR-0018 rule 9.

2. **Units.** `uom` gains `name` and keeps `is_active`:
   - **Core units** are the catalog `catalogs/units.csv` (owner DS-20), seeded from UN/ECE Recommendation 20 for the core kinds: piece (`H87`), set (`SET`), kilogram (`KGM`), gram (`GRM`), tonne (`TNE`), metre (`MTR`), centimetre (`CMT`), millimetre (`MMT`), square metre (`MTK`), cubic metre (`MTQ`), litre (`LTR`), millilitre (`MLT`), hour (`HUR`), minute (`MIN`) and day (`DAY`). Their `id` is uuid5 of `uom:<code>` (ADR-0006 rule 4). Their `name` is the English name; the core i18n catalog translates it (`uom.<code>.name`), the Vietnamese UI translation included, as for other UI strings (ADR-0016 rule 18; ADR-0053 rule 16).
   - **Packaging and trade units** (box, carton, pallet, bag, roll, can) are company units, coded `x-` (for example `x-carton`), because their size differs per product. Their name is the company's text, translated through `data_translation` (ADR-0018 rule 17).
   - **Decimal places** stay one value per unit, global, at most 6, and never change once the unit is used (ADR-0018 rule 8). Because they bind forever, the catalog gives the large units room: kilogram, metre, square metre and litre 3 decimals, tonne and cubic metre 6, and the small units fewer (gram, millimetre and millilitre 0, centimetre 1). The mass, length and volume pairs are then exact in both directions (rule 7). Of the time pairs, only day to hour is exact (toward the smaller unit); hour and minute, and day and minute, are inexact both ways (0.01 hour is 0.6 minutes, a minute is 0.0166… hours, 0.01 day is 14.4 minutes).
   - **Statutory unit names.** A localization package may supply statutory names of the core units for its regime's statutory outputs (e-invoice lines, statutory prints), as terminology keys `uom.<code>.name` read from its file `i18n/<language>/unit_names.csv`, one row per core unit with its basis (ADR-0016 rules 5, 6, 18). Statutory outputs take the package's name when present, else the core translation (rule 18). The core holds no country's statutory unit names; `l10n_vn`'s draft file is DS-19's.
   - **Retired units.** `is_active` false retires a unit: no new product unit, price entry, supplier order unit, product default unit or source line may name it. History keeps it.

3. **Global conversions.** `uom_conversion` is a core catalog, `catalogs/unit-conversions.csv` (owner DS-20), between core units of one kind:
   - **Direct pairs only.** Each pair is stored once, from the larger unit, so its factor is at least 1 (1 `KGM` = 1000/1 `GRM`). The inverse is derived, never stored. The database refuses a second row for the same pair in either direction.
   - **No chaining.** A conversion is found only as a stored pair or its inverse, never through a third unit. Gram to tonne needs its own row.
   - **Identity and lifecycle.** Each row gets a surrogate `id`, uuid5 of `uom_conversion:<from code>:<to code>`, so a line's trace can name it (ADR-0006 rule 1). Rows are immutable once used. `is_active` false retires one; a retirement is a catalog version. A global conversion is a physical constant, so a retired pair is never replaced by another factor: uniqueness holds over all rows of a pair, and its deterministic `id` stays unique. Only product units need retire-and-replace on the same unit (rule 5).
   - Company units never appear in `uom_conversion` (ADR-0018 rule 8).

4. **Product units on the item master.** `product_uom` lists every other unit of a product, as the author asked:
   - **Identity.** A surrogate `id` (ADR-0006 rule 1), `company_id`, `product_id`, optional `item_id`, `uom_id`, at most one **active** row per (company, product, item, unit), with a null item counting as one value; retired rows of the same unit stay for history.
   - **Item-level rows.** A row with `item_id` set is an item's own unit for one variant or configured item, for example a configured frame bought by the metre at its own length per piece. The item must be one of the product's items; the database holds it. Configured items created on order (ADR-0046 rule 11) get no item rows automatically; a person adds them.
   - **The factor.** `numerator` and `denominator`, positive integers: 1 unit = numerator / denominator inventory units (ADR-0006 rule 11). `inventory_uom_id` repeats the product's inventory unit through a key to the product, so the database refuses a product unit that is the inventory unit itself.
   - **How the factor was set,** `factor_source`: `stated` (a fixed conversion the company states, such as a carton of 24), `packaging` (computed at creation from rule 15's `contains` relation), `catalog` (the factor of a `uom_conversion` pair, below), or `nominal` (an approximation of a variable relation, rule 22's Phase 1 workaround).
   - **Classification,** `is_exact`, computed by the command at creation by rule 7 and never entered.
   - **Packaging and warehouse flags:** `contains_uom_id`, `contains_quantity`, `is_counting_unit`, `is_default_pick_unit` (rule 15).
   - **Lifecycle:** `recorded_at`, `is_active` and `retired_at`: a row is in force from `recorded_at` until `retired_at` (rule 5; INV-603).
   - **Catalog-convertible units.** A product unit may name a unit that converts to the inventory unit through `uom_conversion` only with the catalog's factor (`factor_source` `catalog`), else `uom_conversion_conflict`. Such a row never competes with the catalog; it is where the counting and pick flags of those units live (grams of a product kept in kilograms, counted in grams). Retiring a `catalog` row without a replacement blocks that catalog unit for the product (rule 6: a level with rows but none in force uncovers nothing). This is intended: it is how a company stops a catalog unit for one product.
   - **Units on master data.** Price entries, the product's `purchase_uom_id` and `sales_uom_id`, and `supplier_item.order_uom_id` may use any unit the item resolves by rule 6, catalog units included.
   - **Serial-tracked products.** Every unit allowed for the product (its product and item rows and the catalog units it resolves) must be exact (rule 7), else `serial_unit_not_exact`. With the inventory unit at 0 decimals this means a whole factor from a unit with 0 decimals, so serial counts equal inventory quantities.

5. **Immutable once used; retire and replace.** A `product_uom` or `uom_conversion` row is immutable once any line, price entry, supplier item, barcode or bill of materials refers to it (`uom_conversion_in_use`). A row nothing refers to may still be corrected or deleted.
   - **Replacement keeps the unit code.** To change a used conversion, the company retires the row (`is_active` false, `retired_at` set) and adds a new row for the same product, item and unit, in one command (`UpdateProductUom` with the replacement factor). For example, a supplier's carton changes from 24 to 20 pieces: the `x-carton` row of 24 is retired and an `x-carton` row of 20 takes over. Uniqueness holds among active rows only (rule 4), so the retired row stays for history and for the lines that snapshot it.
   - **An item's own row is a replacement too.** `CreateProductUom` with `item_id`, for a unit the item already resolves at product level, supersedes the product row for that item only, with the same price-entry handling (for that item's entries), the same review list and the same INV-603 handling.
   - **Nothing is ambiguous.** Every line carries its own snapshot (rule 9): existing lines keep 24, new lines resolve to 20 (rule 6), and a follow-on line of an open document in the source line's unit keeps the source's 24 (rule 11).
   - **Price entries,** which name the unit and not its factor. The command covers every entry of the unit valid on or after the business date, at the replaced level: for a product-level row, the entries keyed to the product (configurable products) and those of its items, except items with their own active row for the unit; for an item-level row, that item's entries. An entry that started earlier is end-dated to the day before the business date; one that starts later is removed; one that starts on the business date refuses the command with `price_entry_starts_today`: an entry that has started can be neither removed nor ended before its start (ADR-0045 rule 7 note), so the remedy is to run the replacement on the next business date, when that entry is end-dated like any earlier one. A price per carton of 24 then never prices a carton of 20. Until new entries exist, the lookup falls back to the inventory unit's price × the new factor (rule 16). There is no effective dating: the replacement takes effect when the command runs.
   - **Packaging that contains the unit,** transitively. Active packaging rows of the same level whose `contains_uom_id` is the replaced unit, and the rows that contain those, up the hierarchy (pack → carton → pallet), are retired and replaced in the same command, each factor recomputed; otherwise the command is refused with `uom_packaging_inconsistent` (rule 15).
   - **Kept for review.** The check result `product_uom_replaced` lists what names the unit but is kept: supplier items whose order unit it is (a minimum of 2 cartons now means 2 cartons of 20), barcodes of the unit (GS1 assigns a changed pack its own barcode), active bill of materials component and output lines in the unit (their snapshot keeps the old factor until a new revision), `partner_item` rows with that unit, and product defaults in it, besides the price entries ended or removed.
   - A retired row never returns. There is no effective dating: lines keep their snapshot, so no line needs the old factor from master data. The inventory unit never changes once used; the way out is a new product, as ADR-0018 rule 13 says.
   - **Retirement without replacement** leaves the level with no active row, so new lines in that unit get `uom_retired` (rule 6).

   A retired row or unit takes no new uses (rule 2). A follow-on line that takes its source line's unit and snapshot (rule 11) is not a new use. Open documents can therefore be finished at the retired factor.

6. **Resolution: `convert_quantity`.** `master_data.contract.convert_quantity(item, from_uom, to_uom)` is one pure function, used by every command, by `find_price` and by the queries:
   - **To the inventory unit** (the case every line needs), for a unit U of an item:
     1. U is the inventory unit: factor 1/1, source `identity`;
     2. else the item's active row for U (at most one exists): source `item`;
     3. else the product's active row for U (item null): source `product`;
     4. else a `uom_conversion` row (U, inventory unit), or (inventory unit, U) inverted, between core units of the same kind: source `global`;
     5. else `uom_not_allowed`.
   - **Retired rows.** A level that has rows for U but no active one stops the search with `uom_retired`. It never uncovers the level below, so retiring an item's own carton without a replacement does not switch that item to the product's carton. A level with a replacement resolves to its active row.
   - **Between two units.** The factor is the quotient of the two factors to the inventory unit, each resolved as above. The inventory unit is the item's own pivot, not a chain through the catalog.
   - **The result:** the factor as a reduced fraction, its source (or the two sources), `is_exact` for the pair by rule 7, and the row used (`product_uom.id` or `uom_conversion.id`) for the derivation trace (ADR-0027 rule 3).
   - **Company units** convert only through `product_uom` rows (ADR-0018 rule 8).

   Example (g and kg). A product is kept in `KGM` (3 decimals). A line of 500 `GRM` resolves at step 4 through the catalog row 1 `KGM` = 1000/1 `GRM`, inverted: factor 1/1000, source `global`, exact. The inventory quantity is 0.500 kg. The other way round, a product kept in `GRM` (0 decimals) takes a line of 1.250 `KGM` as 1250 g by the stored row itself.

7. **Exact and inexact units.** A conversion from an entered unit E (with `dE` decimal places) to the inventory unit I (`dI` places) with factor n / d is **exact** when `n × 10^dI` is divisible by `d × 10^dE`. Then every quantity that E can hold converts to a quantity I can hold, and a line never rounds. Otherwise it is **inexact**: some quantities round, and the cumulative rule of rule 10 keeps parts adding up.
   - **Examples:**
     - carton = 24/1 pieces, both 0 decimals: 24 × 1 divisible by 1 × 1, exact;
     - bag = 7/3 kg, bag 0 and kg 3 decimals: 7 × 1000 = 7000 is not divisible by 3 × 1 = 3, inexact;
     - g to kg, factor 1/1000, g 0 and kg 3 decimals: 1 × 1000 divisible by 1000 × 1, exact;
     - kg to g, factor 1000/1, kg 3 and g 0 decimals: 1000 × 1 divisible by 1 × 1000, exact;
     - t to kg and kg to t, t 6 and kg 3 decimals: 1000 × 10^3 divisible by 1 × 10^6, and 1 × 10^6 divisible by 1000 × 10^3, exact both ways;
     - minute to hour, factor 1/60, minute 0 and hour 2 decimals: 1 × 100 is not divisible by 60 × 1, inexact (a minute is 0.0166… hours).
   - **When it is computed.** `CreateProductUom` computes `is_exact` and stores it. An inexact row is accepted with the check result `unit_inexact` (`details`: factor, decimals, `reason` `decimals`). Global conversions are classified the same way at each use. When one step of the entered unit converts to less than half a step of the inventory unit (`10^−dE × n / d < 10^−dI / 2`), the smallest quantities of the unit round to zero, so `CreateProductUom` also warns with the check result `unit_step_below_inventory_step`: the unit's usual quantities may fall below one inventory step, which is a master-data problem to settle now, not at the dock (rule 8).
   - **Lines.** A line in an inexact or `nominal` unit returns `unit_inexact` with its reason (`decimals` or `nominal`). Inexact units are allowed: 1 bag = 7/3 kg is real, and forbidding it would push companies to wrong factors.

8. **Rounding by use.** Every converted quantity is rounded once, by `round_quantity(value, unit, mode)` (ADR-0006 rules 15, 17), to the target unit's decimals, in the mode its use names. Rounding never changes an amount (ADR-0006 rule 19).
   - **`up`:** requirements; planning proposals, purchase, transfer and production alike (their lot sizes included); supplier minimums and multiples (rule 14); issue multiples (rule 17); backflush (ADR-0034 rule 12). Under-supply is the error these uses avoid.
   - **`half_up`** (half away from zero): receipts, deliveries, invoices, returns, credits, counts, transfers and issues a person enters. These record facts, so neither direction is favoured. Planned co-product and by-product quantities also round half up, each in its own inventory unit: they are expected yields, not requirements (ADR-0033 rule 7).
   - **Scrap.** The planned output quantity Q = G / (1 − assembly scrap) is rounded up once, to the main output's inventory unit, when the order stores it. Each component requirement is computed from that stored Q, exactly, and rounded up once to the component's inventory unit (ADR-0033 rule 6).
   - **Check results.** A rounded line returns `quantity_rounded` with the exact and the rounded value (ADR-0018 rule 11). A line whose inventory quantity rounds to zero is still rejected with the error `quantity_rounds_to_zero`, and so is a forward part against a source line whose cumulative value computes to zero or less (rule 10): no part ever posts a quantity its entered quantity did not earn. A unit whose usual quantities fall below one inventory step is a master-data problem: the inventory unit is the smallest unit the company sells or counts (ADR-0018 rule 11), and rule 22's workaround keeps stock in the finer unit (the length as inventory unit, the piece as a `nominal` product unit). An entered quantity with more decimals than its unit holds is rejected, never rounded (ADR-0006 rule 14).

**Lines**

9. **The line unit block.** Every quantity line stores six fields:
   - `quantity`, as entered, in `uom_id`;
   - `uom_id`;
   - `uom_numerator` and `uom_denominator`: the factor to the inventory unit used when the line's unit was set;
   - `uom_factor_source`: `identity`, `item`, `product` or `global` (rule 6);
   - `inventory_quantity`.

   The snapshot is taken when the line's unit or item is set on a draft and is never read again from master data. Copies to follow-on lines in the same unit, the cumulative rule (rule 10), reversals and reprints use it. A draft line whose unit or item changes is resolved and snapshotted again.
   - **Drafts across a retirement.** A draft line snapshotted before its row was retired or superseded (rule 5) posts at its snapshot only if it is a follow-on line keeping its source line's snapshot. Any other draft line is resolved again at Submit and again at Post: its entered quantity stays, its inventory quantity follows the new factor, and the check result `uom_factor_changed` names it. A change after approval changes the plan hash, so the document returns to draft for a new approval (ADR-0009). The line is re-priced from the entries in force; the old pack's price is not kept, unless the price is manual.
   - **Tables with the block** (DDL in DS-22-09-42 and DS-43-54):
     - quotation, sales order, delivery, return from customer, sales invoice, sales return and credit note lines;
     - purchase request, purchase order, goods receipt, return to supplier, service receipt, purchase invoice, purchase return and purchase credit note lines;
     - production issue, production receipt and generated backflush lines (`operation_progress_component`), and replenishment request lines;
     - transfer order and stock count lines, when their DDL is drafted (DS-42).

     On lines whose quantity is optional (amount-only credits, expense invoice lines), the six fields are all set or all empty.
   - **Variants of the block.** Bill of materials components and outputs store `quantity`, `uom_id` and the snapshot but no inventory quantity, which stays an exact rational per base quantity (rule 17). A planned order keeps `quantity` in the inventory unit and stores its order unit as `order_quantity`, `order_uom_id` and the snapshot (rule 14). Generated backflush lines are written in the inventory unit, source `identity`, which the database holds.
   - **Inventory unit only.** `material_document_line`, stock rows, reservations, warehouse tasks (whose `uom_id` is the demand line's unit, for display only), demand and supply rows, planned order components, production order components and outputs, and `gr_ir_write_off_line`.
   - **What the database holds** on every table with the block: positive factors; a known source; `identity` only with 1/1 and an inventory quantity equal to the entered one; and `|inventory_quantity × uom_denominator − quantity × uom_numerator| ≤ 2 × uom_denominator`. This last check is a gross-error check: the inventory quantity lies within two inventory units of the exact conversion. The rules keep that bound provably: per-line rounding stays within half a step; a forward part is clamped to within one inventory unit (rule 10); and a return's share of a part stays strictly below two units, at most `r / q` of a unit (below one) plus one rounding step, because the part itself is within one unit (rule 10). A carton line stored as one piece is still refused; the exact rounding is not checked there. Whether the snapshot is the right factor for the item and unit, and the exact rounding, are command rules with invariants (rule 25).
   - **Prices.** Every unit price on a line is per that line's `uom_id` (rule 12).

10. **Parts add up: the cumulative rule.** A source line S has entered quantity q_S in unit U, factor f (the snapshot of S) and inventory quantity Q_S = round(q_S × f). Forward parts refer to S: receipts of a purchase order line, deliveries of a sales order line, invoices, and issues of a component line. Returns, credits and reversals refer to a posted part.
    - **The source of an invoice** is always the order line, for stock lines too: C and P count the order line's invoices, and the delivery or receipt line an invoice line names serves matching only. Three deliveries of one bag (2.333, 2.334, 2.333) invoiced one by one post 2.333, 2.334 and 2.333 against the order line, so invoiced net reaches delivered net at 7.000; taking each delivery line as source would post 2.333 three times and stop at 6.999.
    - **Forward parts in U, at the snapshot of S.** Let C be the actual net entered quantity in U of the posted parts of S (forward parts less their returns, credits and reversals), and P their actual net inventory quantity. A forward part of q has inventory quantity `round((C + q) × f) − P`, rounded in the mode of S (rule 8). After any forward part, P equals `round(C × f)`, whatever came before, so the rule corrects itself.
    - **Zero or less is rejected; positive values are clamped.** After a return, credit or reversal, P can differ from `round(C × f)`, so a forward part can compute to zero or less, or far from its own exact conversion `q × f`.
      - A forward part whose computed value is zero or less is rejected with `quantity_rounds_to_zero` (rule 8), as a line with no source is: posting a step instead would inflate the line. With a unit of 3/5 piece on pieces with 0 decimals, an order of 10 units is 6 pieces; after a first receipt of one unit (1 piece), a further receipt of one unit computes round(2 × 3/5) − 1 = 0 and is refused, so ten single-unit receipts never post 10 pieces. Bars kept in pieces and received in metres at 1 m = 1/6 bar: a receipt of 2 m computes round(2/6) = 0 and is refused; 12 m post 2 bars.
      - **Remedies.** A unit whose usual quantities fall below one inventory step is a master-data problem: with bars as the inventory unit, a remnant of 2 m cannot be received at all, in metres or in bars. Stock belongs in the finer unit (ADR-0018 rule 11; rule 22's workaround: metres as inventory unit, the bar as a product unit, `nominal` when bar lengths vary); `unit_step_below_inventory_step` flags such units when they are created (rule 7). For an occasional small part only, the person receives a larger quantity: the error's `details` give the smallest entered quantity that would post (3 m in the bar example, 2 units after the first 3/5-piece receipt).
      - **Not a closing event.** A completing part computes to zero or less only when P has already reached Q_S, so the line was fulfilled, and closed, at the earlier posting; refusing the completing part closes nothing.
      - A positive computed value is clamped to the band from `q × f − 1` to `q × f + 1` inventory units (the bounds rounded inward to the unit's decimals), with the check result `part_quantity_clamped` when the clamp changed it. The change counts in the line's unit rounding tolerance (below), so the limits and the closing check absorb it, and the part stays within one inventory unit of its exact conversion for the database's gross-error check.
    - **Returns, credits and reversals take the part they name as their source,** in that part's unit. A reversal, or a return of the whole part, mirrors the part's stored inventory quantity. A partial return takes its cumulative share of the part: `round(v × (r₀ + r) / q) − v₀`, where q and v are the part's entered and stored inventory quantities and r₀ and v₀ what the part's earlier returns took. The returns of a part thus sum exactly to its stored inventory quantity and never exceed it, even when the part itself was clamped. Since the part is within one inventory unit of its exact conversion, a share is within `r / q` of a unit plus one rounding step of its own, below two units. A partial return whose share rounds to zero is rejected (`quantity_rounds_to_zero`); the small entered rest it leaves on the part, which may never be returnable by value, is accepted. A return or credit in another unit converts on its own. So a return never posts more than the part it returns: returning receipt 1 of the example below posts 2.333, not 2.334, and the next receipt of one bag posts round(3 × 7/3) − 4.667 = 2.333.
    - **A money return follows its stock return.** A money-side return line that names a stock return line in the same unit and for the same entered quantity takes that stock line's inventory quantity: a `purchase_return_line` naming its `return_to_supplier_line`, a `sales_return_line` naming its `return_from_customer_line`. Returning receipt 2 (2.334) and crediting its bag then move R and I by the same 2.334, so GR/IR stays zero; on the sales side, invoiced net equals delivered net again and `sales_return_due` closes.
    - **Invariant.** A forward part that brings C to q_S brings P to Q_S, unless a clamped part or a return, credit or reversal left a deviation, which stays within T(S); parts in U that complete S then sum exactly to its inventory quantity, and the returns of a part never exceed the part. Reversals need no order of their own: a part that a return or credit names cannot be reversed (`document_referenced`, ADR-0009 rule 18), and a mirrored reversal of an unreturned part only shifts C and P, which the next forward part corrects. GR/IR keeps its latest-only rule for documents with purchase order lines (ADR-0047 rule 13), unchanged.
    - **The unit rounding tolerance** T(S) grows by one smallest step of the inventory unit (10^−dI) for each part of S posted in another unit whose conversion rounded (`quantity_rounded`), and, for each return, credit or reversal of a part in U and each clamped forward part, by the amount it changed the deviation `P − round(C × f)` (nothing when it left the deviation unchanged); the part being posted counts. T(S) grows monotonically: a counted part that is later reversed stays counted. It is bounded by the number of deviation-changing postings, each adding the change it made: below three inventory units for a return or credit (its share's error, strictly below two units, plus one rounding step) and at most one unit plus one step for a reversal or a clamp. This growth is accepted: each extra step of tolerance needs a return, credit, reversal or clamp that actually changed the deviation. With an exact snapshot nothing rounds and no deviation arises, so T(S) stays zero and every comparison is exact: an order of 10 cartons of 24 pieces received, one carton returned and 23 pieces received is not fulfilled (239 of 240), and a further 25 pieces (241) are refused. (A count of one step per changing posting is not enough: with clamps, a single posting can change the deviation by more than one step.) A part in another unit converts on its own (`round(q × its factor)`) and takes no part in C or P. T(S) applies both ways: the upper limits `quantity_exceeds_open`, `receipt_exceeds_order` (after the receipt tolerance), `invoice_exceeds_delivered` and `correction_exceeds_original` allow T(S) more, and S counts as fulfilled by quantity when its fulfilled inventory quantity is within T(S) of Q_S. With none of these parts, T(S) is zero and the comparisons are exact. Example: 8.000 kg ordered and delivered as three bags of 8/3 kg, each converting on its own to 2.667 kg, is 8.001 kg in total; T = 0.003, so the third delivery is accepted and fulfils the line.
    - **GR/IR rounding clearing.** When a purchase order line is fulfilled within its tolerance and its received net R and invoiced net I both lie within T(S) of its inventory quantity but differ, or when a closed line's R and I differ by no more than T(S), the system posts `gr_ir_rounding_clearing`:
      - **The side.** It posts on the lagging side at the positions' value (ADR-0047 rule 13): on R, crediting GR/IR with `round(V(I)) − round(V(R))`, when I > R; on I, debiting it with `round(V(R)) − round(V(I))`, when R > I; against the regime's `price_difference` key (ADR-0047 rule 21). Its positions count in R or I for GR/IR, so INV-92 holds with them, and never in received or invoiced quantities.
      - **Never latest.** It never counts in the latest-only reversal check of ADR-0047 rule 13, so it never blocks a reversal.
      - **Re-evaluated.** Every later GR/IR posting on the line (a receipt, invoice, return, credit, reversal or `gr_ir_write_off`) first reverses an active clearing as a consequence, in the same transaction; the clearing fires again when the line is still, or again, within tolerance. A posting that takes the line out of tolerance thus leaves the clearing reversed until the line returns.
      - **Registration.** Document type `gr_ir_rounding_clearing`: `purchasing`, posting, internal, no change orders, not e-invoice capable, no approval hold, reversed only as a consequence (never by `Reverse`), not item-creating. Its `Post` is `is_internal_only` and `is_consequence_posting`; no template's expansion holds it, and its authorization leaf sits under purchasing at level `full`. It has its own document row (DS-05 `document`) and no header or line table: the `purchase_order_line_gr_ir_posting` row of kind `rounding_clearing` carries the line, positions and amount. The command that triggered it returns `gr_ir_rounding_cleared`, or `gr_ir_rounding_clearing_reversed`.
      - **Company currency.** The clearing is the posting that makes R = I for the interim company-currency rule of ADR-0047 rule 13, so it also clears the line's company-currency residual to realized exchange difference; reversing the clearing reverses that entry too.
      - **Lines closed short.** It also runs on a closed line whose R and I differ by no more than T(S), whatever they stand at against Q_S (a credit that could not follow its stock return, for example).
      - It runs only within T(S); a larger difference stays the closed-short path of ADR-0047 rule 13.
    - **Provisional on drafts.** A part's inventory quantity is provisional on a draft and recomputed at Post from the then-posted C and P, under the source document's lock, as GR/IR postings are. A reservation or open pick task made for the provisional quantity is adjusted by the difference at Post. A pick task already confirmed at the provisional quantity is not changed: the difference becomes a follow-up warehouse task, an extra pick or a putaway back. Either way the check result `part_quantity_recomputed` names it for the warehouse. INV-600 and INV-601 apply to posted parts.
    - **One function.** `master_data.contract.convert_part(f, C, P, q, unit, mode)`, pure, called by every handler that posts a part; returns and credits call it with the part as source.

    Worked example (bag = 7/3 kg; kg 3 decimals, bag 0). A purchase order line of 3 bags has inventory quantity round(7) = 7.000 kg, at 70,000 per bag, so the GR/IR price is 210,000 / 7 = 30,000 per kg. Three receipts of 1 bag each:

    | Receipt | C before | round((C + 1) × 7/3) | P before | Inventory quantity | GR/IR credit |
    | --- | --- | --- | --- | --- | --- |
    | 1 | 0 | 2.333 | 0.000 | 2.333 | 69,990 |
    | 2 | 1 | 4.667 | 2.333 | 2.334 | 70,020 |
    | 3 | 2 | 7.000 | 4.667 | 2.333 | 69,990 |

    The receipts sum to 7.000 kg and 210,000, the invoice of 3 bags debits 210,000, and GR/IR is zero. A return of receipt 2 would post its own 2.334, after which C = 2 and P = 4.666, and the replacement receipt of one bag posts 7.000 − 4.666 = 2.334. Rounding each receipt on its own would give 3 × 2.333 = 6.999 kg: 0.001 kg would stay open forever, and the line would keep a 30 VND residual that only the human-only write-off could clear.

    Note (UoM simulation review, 2026-11-15): a return to supplier of a part of a purchase order line takes its inventory quantity from the part it names, as above, but moves GR/IR at the line's latest received positions ([ADR-0047](0047-commercial-documents-and-pricing.md) rule 13 and its note). `return_to_supplier_line.gr_ir_position_from` and `gr_ir_position_to` store the positions actually debited, from R − q to R; `goods_receipt_line_id` stores the named part, the part-as-source reference. In the worked example, the return of receipt 2 mirrors its 2.334 kg and stores positions 4.666–7.000. Under the interim regime seed of `purchase_return` (value source `document`), the value that leaves stock is that GR/IR debit, round(V(R)) − round(V(R − q)), so the return posts no price difference ([ADR-0020](0020-inventory-and-costing-model.md) rule 5 note). Lab check `t17_uom.py` U70 and U71.

11. **Follow-on lines in any unit.** A receipt, delivery, invoice, return, credit, production issue or receipt may use any allowed unit of the item (rule 6), whatever the unit of the line it refers to. Pieces may be received against an order in cartons, and an invoice may come per kg against an order in bags. Every quantity relation compares inventory quantities: links and open quantities, `quantity_exceeds_open`, correction limits (ADR-0047 rule 20), the receipt tolerance, the three-way match quantity and GR/IR positions.
    - **Receipt tolerance** applies to the ordered quantity, not to the open quantity: received net inventory quantity ≤ the order line's inventory quantity × (1 + `inventory.purchase_receipt_tolerance_percent` / 100), plus the unit rounding tolerance (rule 10). Each partial receipt therefore cannot earn the tolerance again.
    - **Copying.** `source_lines` quantities are in the source line's unit. A copied line takes the source line's unit and snapshot, so the cumulative rule applies to it. If the person changes the unit, the line is resolved again (rule 6) and converts on its own.
    - **Returns and credits priced from their original** convert the original's price per inventory unit by their own factor. The price is `round_unit_price(p × (n_o / d_o)⁻¹ × (n / d))`, where p is the original's net unit price after the document discount, n_o / d_o its snapshot and n / d the line's own. A line in the original's unit keeps p unchanged. A quantity credit is `round_amount(quantity × that price)` (ADR-0047 rule 8). A credit that brings the credited inventory quantity of an invoice line to its invoiced inventory quantity takes exactly the rest of the line's net amount, so rounding never trips the amount limit.

    Example (carton = 24/1 pieces, both 0 decimals, exact). A purchase order line of 10 cartons at 230,000 has inventory quantity 240 and GR/IR price 2,300,000 / 240 per piece. Receipts are entered in pieces: 100, then 140 (source `identity`, converting on their own). GR/IR is credited round(958,333.33…) = 958,333, then 2,300,000 − 958,333 = 1,341,667. The invoice is 10 cartons: inventory quantity 240, debit 2,300,000. GR/IR is zero, and the match price per inventory unit is the same on both sides (rule 12). The order line is fulfilled by quantity: 240 received of 240 ordered, and the tolerance is zero, since no part rounded.

12. **One unit and one price per line.** A line has one unit, and its unit price, at up to 10 decimals (ADR-0006), is per that unit. There is no separate order price unit in Phase 1; a supplier who invoices per 1,000 pieces is served by a product unit `x-1000pcs` or by the 10-decimal price. The order price unit comes after Phase 1 with catch weight (rule 22).
    - **Three-way match compares per inventory unit.** The invoice line's net amount after the document discount, divided by its inventory quantity, is compared with `(V(I + q) − V(I)) / q`, the GR/IR value per unit of the positions the invoice reaches (ADR-0047 rule 14 note).
    - **`purchasing.match.price_tolerance_amount`** is an amount per inventory unit, in the document currency.

13. **The proposed unit.** A new line proposes its unit in this order, and the person may choose any allowed unit instead:
    1. a line copied from a source line: the source line's unit;
    2. a scanned barcode: the barcode's unit (ADR-0018 rule 14);
    3. the partner's own unit for the item, `partner_item.uom_id` (customer or supplier);
    4. purchasing: the supplier's order unit, `supplier_item.order_uom_id` (rule 14);
    5. the product's `purchase_uom_id` or `sales_uom_id`;
    6. the inventory unit.

    Bill of materials lines set their own unit. Count lines propose the inventory unit and accept the product's counting units (rule 15). The command response names the proposed unit's source in `proposed_uom_source`: `source_line`, `barcode`, `partner_item`, `supplier_item`, `product_default` or `inventory_unit`. A unit typed by the person or agent always wins and is not reported as proposed.

    Note ([ADR-0061](0061-barcodes.md), proposed 2026-11-15): a GS1 scan that carries a variable-measure AI (310n net weight, 311n length, 314n area, 315n and 316n net volume) proposes the AI's unit and quantity instead of the barcode's unit: the measure enters in its own unit as the line's entered unit, which must be an allowed unit of the item (`uom_not_allowed`, rule 6), and converts by `convert_quantity` as rule 8 says for receipts; `proposed_uom_source` stays `barcode`. The measure itself is never rounded: extra decimals that are zeros are dropped, any other extra decimal is `too_many_decimal_places` (rule 8; ADR-0006 rule 14). A count AI, (30) or (37), keeps the barcode's unit (rules 17-18).

**Purchasing and planning**

14. **The supplier's order unit.** `supplier_item` gains `order_uom_id`, NOT NULL: any unit the item resolves (rule 6). The command proposes the product's purchase unit when the row is created. `minimum_order_quantity` and `order_multiple` are in that unit.
    - **No supplier-specific factors.** A supplier whose carton holds 20 instead of 24 gets its own product unit (`x-carton-20`), so one item and unit always have one factor.
    - **Planning** nets in inventory units. For a purchase proposal it converts the shortfall exactly into the order unit, rounds up to the minimum and the multiple there (ADR-0024 rule 15), and converts the order quantity back with `half_up`, as the purchase order line will (rule 9). It stores `order_quantity`, `order_uom_id` and the snapshot on the planned order, `quantity` (the inventory unit) and `rounding_excess_quantity`.
    - **Hand-over.** The replenishment request line and the purchase request line carry the order unit and its snapshot. A purchase order copied from a request keeps the request's unit unless the person changes it.

    Example. The need is 100 pieces; the supplier's order unit is `x-carton` (24 pieces), with minimum 2 and multiple 1. 100 / 24 = 4 1/6 cartons, rounded up to 5 cartons, which is above the minimum: order quantity 5 cartons, quantity 120 pieces, rounding excess 20 pieces.

**Packaging, warehouse and counts**

15. **Packaging is a product unit.** There is one list of units per product, used by purchasing, sales, the warehouse and barcodes.
    - **Hierarchy.** `contains_uom_id` and `contains_quantity` say "1 pallet contains 40 cartons". `contains_quantity` is a whole number above 1, and the contained unit is the inventory unit or another product unit of the same product and item level. The database holds the shape: both fields or neither, a whole number above 1, not the row's own unit. Since factors rise strictly, a cycle cannot form.
    - **Consistency.** The command checks that the row's factor equals `contains_quantity` × the contained unit's factor, exactly (`uom_packaging_inconsistent`). A row created from the hierarchy has `factor_source` `packaging`.
    - **Counting units.** `is_counting_unit` marks the units a count may be entered in. A count may have several lines per item, bin and lot in different units; each converts with `half_up` and they sum in the inventory unit (ADR-0020 rule 18; ADR-0023 rule 18).
    - **Pick units.** `is_default_pick_unit` marks at most one unit per product or item, which a pick list proposes when the demand line is in the inventory unit. The pick breakdown ("2 cartons and 3 pieces") uses the packaging hierarchy, from the largest whole unit down (ADR-0023 rule 14). A retired row cannot be the default pick unit; the database holds both rules. A catalog unit carries these flags through a `catalog` row (rule 4).
    - **After Phase 1:** a quantity per handling unit type, and dimensions and weights per packaging unit (ADR-0018 rule 4). `handling_unit_type` stays the physical container (ADR-0023 rule 6).

**Prices and promotions**

16. **Price breaks per unit.** ADR-0045 rule 4 stands. The entered unit's entries are searched first; when none qualifies, the quantity is converted exactly to the inventory unit, the inventory unit's entries are searched, and the price is multiplied by the factor and rounded half up to the unit-price scale. The entered unit's entry always wins. Breaks are in each entry's own unit. The factor is `convert_quantity`'s.

    Worked example. An item is kept in pieces, and a carton is 24/1 pieces. The sale list has pieces from 0 at 10,000 and from 100 at 9,000, and cartons from 0 at 230,000.
    - 5 cartons (120 pieces): the carton entry applies, at 230,000 per carton. The piece break at 100 would give 9,000 × 24 = 216,000, but the entered unit's entry always wins. This is intended: the price a company sets for a unit is the price of that unit, and a company that wants the break for cartons gives the carton entry its own break.
    - Suppose instead the only carton entry is a break from 10 cartons at 220,000. Then 5 cartons have no qualifying carton entry. The price falls back to pieces: 120 pieces reach the 100 break, so 9,000 × 24 = 216,000 per carton. 2 cartons (48 pieces) give 10,000 × 24 = 240,000.
    - A bag of 7/3 kg on a list in kg (from 0 at 10,000, from 5 at 9,500): 3 bags = exactly 7 kg reach the 5 kg break, so 9,500 × 7/3 = 22,166.6666666667 per bag. 2 bags (4 2/3 kg) give 10,000 × 7/3 = 23,333.3333333333.

    Lab t05 checks the same lookups on real rows (P04 to P15), and t17 checks this example.
    - **Promotions.** `minimum_line_quantity`, `qualifying_quantity` and `free_quantity` are inventory-unit quantities of the line's item and the free item. `amount_per_unit` is per inventory unit and is multiplied by the line's factor and rounded once, as option extras are (ADR-0045 rule 17).
    - **After Phase 1:** a sales minimum or multiple and delivery rounding. When they come, they are check results with a proposal (`quantity_not_multiple`), never silent rounding.

**Production**

17. **Bills of materials and production lines.**
    - **Components and outputs.** Bill of materials component and output lines may use any allowed unit of their item, stored with the snapshot (`uom_numerator`, `uom_denominator`, `uom_factor_source`). There is no default factor; the DDL's `DEFAULT 1` is dropped. The quantity in the inventory unit is `quantity × uom_numerator / uom_denominator`, an exact rational, not stored. This aligns ADR-0033 rule 6's text with the DDL.
    - **Issue multiple.** An optional `issue_multiple` on a component, in the component line's own unit, rounds each order-line requirement up to whole multiples (whole cans, rolls or reels). The order is: the exact requirement with scrap; then up to a whole multiple of `issue_multiple × factor`; then up to the inventory unit's decimals. The difference above the theoretical requirement is planned consumption, visible in costing.
    - **Example.** Paint is kept in litres (3 decimals). The line is 0.25 can per unit, 1 can = 5/1 litres, issue multiple 1 can. For Q = 10 the exact requirement is 2.5 cans = 12.5 litres, rounded up to 3 cans = 15.000 litres.
    - **Production lines.** Production issue, production receipt, generated backflush, transfer and count lines carry the line unit block of rule 9. Posted production lines keep their item, unit and snapshot (ADR-0034 rule 8).
    - **Precision.** `quantity_per_value` stays `types.quantity` (ADR-0006 quantity scale, 6 decimals). A finer rate uses a smaller unit on the line (millimetres instead of metres).

**Names, prints and intake**

18. **Units on prints and e-invoices.** The print contract's `uom` object of a line (ADR-0049 rule 25) gives the unit's `code` and `name` in the print language. The name comes from the company's `data_translation` for company units, and from the core catalog for core units (ADR-0016 rule 19). A line prints its own unit and quantity, never re-expressed in the inventory unit.
    - **Statutory outputs** (e-invoice lines through the e-invoice add-on, DS-24, and prints a regime marks statutory) take the package's statutory unit name when present, else the core translation (rule 2).
    - **Length.** The core registers the regime setting `documents.unit_name_max_length` (an integer, or empty for no limit); the package supplies its value. A company unit name or translation longer than the value returns the check result `unit_name_too_long` when it is saved, and a statutory output refuses a longer name instead of cutting it.

19. **Unit aliases for intake.** `uom_alias` (company, `alias` as entered, `normalized_alias`, `uom_id`, `is_active`; unique per company and normalized text) maps unit text written by partners and old systems.
    - **Normalization** is one pure function, `master_data.contract.normalize_unit_text`: lower case; Unicode NFKD with combining marks removed; the core's language-neutral fold table of [ADR-0052](0052-minimal-crm.md) rule 17 (`đ`→`d`, `ð`→`d`, `ł`→`l`, `ø`→`o`, `ß`→`ss`, `æ`→`ae`, `œ`→`oe`, `þ`→`th`, `ı`→`i`, `ħ`→`h`); then whitespace and the characters `. - _ /` removed. So "Thùng", "THUNG" and "thung" are one alias, and "m²" becomes "m2".
    - **Resolution of unit text** for an item:
      1. the partner's `partner_item.partner_uom_text` for the item;
      2. else an active alias;
      3. else a unit whose code equals the text.

      Every comparison is between normalized texts: partner texts, aliases and unit codes are normalized the same way.

      The unit must then be allowed for the item (rule 6).
    - **Unknown text is never guessed.** The line stays unresolved with the check result `unit_text_unresolved`, and the agent proposes an alias through a change proposal (`CreateUomAlias`, `master_data_change`, ADR-0029).
    - **Purchase invoice agent** ([ADR-0051](0051-agent-workflows.md) rule 21). D2 maps an e-invoice line's unit text by this resolution. D3 selects order lines by comparing inventory quantities (open received but uninvoiced inventory quantity against the line's inventory quantity) and prices per inventory unit (rule 12).

**Agents, errors, migration and later work**

20. **The agent contract.** Agents and screens read units through one query and one function:
    - **`GetItemUnits` (item)**, a computed query like `GetPrice`, returns every allowed unit of the item. Each unit comes with its code, name, kind and decimal places; its factor to the inventory unit with source and row; `is_exact` and `factor_source`; its flags (counting, default pick, product purchase or sales default, the `contains` relation); its barcodes; and `is_active`. It lists the inventory unit, the item's and the product's rows, and the core units of the inventory unit's kind that convert through the catalog.
    - **Commands** (leaf `product`, `master_data_change`, change-tracked, ADR-0038 rule 3):
      - `CreateProductUom`, `UpdateProductUom` (flags; retirement; or retirement with a replacement row for the same unit, which end-dates the unit's open price entries; a used factor never changes, rule 5);
      - `CreateUom`, `UpdateUom` (company units);
      - `CreateUomAlias`, `UpdateUomAlias`.
    - **Errors:**
      - `uom_not_allowed` for any line, price entry, supplier order unit or default whose unit has no path to the inventory unit by rule 6 (not only in `find_price`);
      - `uom_retired`; `uom_kind_mismatch` (a unit field that requires a kind gets another: dimensions length, weights mass, activity time, container volume and weight);
      - `serial_unit_not_exact`; `uom_conversion_conflict`; `uom_packaging_inconsistent`; `uom_conversion_in_use`; `price_entry_starts_today`;
      - `quantity_rounds_to_zero` stays an error.
    - **Check results:** `quantity_rounded`, `unit_inexact`, `unit_text_unresolved`, `product_uom_replaced`, `uom_factor_changed`, `part_quantity_recomputed`, `part_quantity_clamped`, `gr_ir_rounding_cleared`, `gr_ir_rounding_clearing_reversed`, `unit_name_too_long`, `unit_step_below_inventory_step`.
    - **What the database holds:**
      - positive factors;
      - the line unit block present, with a known source, the identity rule and the gross-error bound (rule 9), and generated backflush lines in the identity;
      - a product unit never the inventory unit, and an item row only for an item of its product;
      - at most one active row per (product, item, unit);
      - the canonical direction of global pairs;
      - the packaging shape; retirement consistency and at most one default pick unit;
      - unique normalized aliases.

      Everything else is command-level with invariants (rule 25): that a line's snapshot is the right one, that a line names no retired or superseded row, exactness, packaging consistency, exact units for serials, catalog rows at the catalog's factor, and immutability once used. The database cannot hold these without reading other rows.

    Note (UoM simulation review, 2026-11-15): the unit commands leave the leaf `product`, where only the owner template reached them. `CreateProductUom`, `UpdateProductUom`, `CreateUom` and `UpdateUom` sit on the new leaf `product_unit`, and `CreateUomAlias` and `UpdateUomAlias` on the leaf `uom_alias` below it, both under `product` in Master data ([authorization-areas.csv](../catalogs/authorization-areas.csv)); each needs `edit`, as `master_data_change` does. `GetItemUnits` stays on `product` at `read`. The templates `purchasing_manager`, `chief_accountant` and `warehouse_keeper` hold `product_unit` at `edit`, and with it `uom_alias`; `accountant` holds `uom_alias` alone, so the purchase invoice agent's workflow owner maintains the aliases that resolve supplier unit text, but not units or conversions ([ADR-0054](0054-users-roles-and-authorizations.md) rule 11 note). A change proposal for these commands, such as rule 19's `CreateUomAlias` from an agent, is approved with `ApproveChangeProposal` by a member of the `general` pool's stage who also holds the target command ([ADR-0043](0043-policy-and-approval.md) rule 12; [ADR-0055](0055-approval-pools-and-stages.md) rule 7): the purchasing manager, the chief accountant or the owner. Lab check `t12_access.py` C28c and G53.

21. **Migration** ([ADR-0044](0044-data-migration-and-export.md)). Units are mapped first, in phase 2 (master data):
    - **Order of loading:** company units, unit aliases for every unit text of the old system, product and item units, then barcodes, before products' documents.
    - **Classification.** Product units are classified by rule 7 at load, never imported as exact or inexact.
    - **Unit text.** Old unit text resolves through `uom_alias`. An unresolved text fails the batch row with `unit_text_unresolved`, so the migration agent proposes aliases.
    - **Opening lines.** Opening stock lines and every open document line a migration creates carry the line unit block, with the snapshot resolved at load.
    - **Decimals.** Quantities with more decimals than their unit holds are rejected, and the validation lists them with the unit's decimals.
    - **Sales history** (phase 6) is loaded in the inventory unit, like every planning quantity (ADR-0024 rule 10).

22. **Phase 1 and after.**
    - **In Phase 1:**
      - the inventory unit only for stock;
      - units, global conversions and product units with item-level rows, resolved by `convert_quantity`;
      - exactness and the cumulative rule;
      - the line unit block on every quantity line;
      - follow-on lines in any unit, with tolerances and match in inventory units;
      - one unit and one price per line;
      - the proposed-unit order;
      - the supplier order unit;
      - packaging hierarchy, counting and pick flags;
      - price breaks per unit and promotions per inventory unit;
      - bill of materials units with issue multiples;
      - unit names for prints and e-invoices;
      - unit aliases;
      - the agent contract and migration of units.
    - **After Phase 1, each with its own ADR:**
      - catch weight (a second quantity per movement, valuation in the unit the supplier invoices, nominal factor tolerances) together with the order price unit;
      - batch-specific factors (an actual factor per lot);
      - cut-to-length remnants and cutting optimization;
      - quantity per handling unit type, and packaging dimensions and weights;
      - sales minimums, multiples and delivery rounding;
      - quantity-based taxes and the customs unit (rule 23);
      - EDI unit mappings and GS1 hierarchy export.
    - **Phase 1 workaround** for goods bought or sold by weight or length that vary per piece: make the weight (or length) the inventory unit and the piece a product unit with `factor_source` `nominal`. Lines in pieces then return `unit_inexact` with reason `nominal`. Receipts record the actual weight in kg (rule 11), so stock, cost and GR/IR are right, and piece counts are approximate. An item-level row (rule 4) gives a configured item bought by length its own exact factor.

23. **Seams.**
    - **Quantity-based taxes and the customs unit.** Taxes per litre or kg, and the statistical unit of a customs declaration, are after Phase 1. They will convert through `convert_quantity` to the unit the package names, and they stay in the package ([ADR-0041](0041-tax-engine.md); ADR-0053).
    - **Container units.** `supplier_purchasing_term.volume_uom_id` and `weight_uom_id` stay as interim columns. Item dimensions and weights convert to them through `uom_conversion` only, so a company unit cannot be a container unit (ADR-0024 rule 2).

**Obligations, catalogs and lab**

24. **Accepted rules amended**, each by a note at the end of the rule:
    - **ADR-0006 rules 11, 15:** the line snapshot and exactness; rounding modes by use.
    - **ADR-0016 rules 18, 19:** core translations of unit names and the package's statutory names.
    - **ADR-0018 rules 8–14:** unit names, retirement and catalogs; exact units for serials; item-level rows, surrogate key and resolution; the snapshot and the cumulative rule, and `quantity_rounds_to_zero` widened to forward parts; the proposed-unit order and defaults in any allowed unit; retire and replace, which replaces "cannot be removed or changed" with a way out; barcodes and packaging.
    - **ADR-0019 rule 6:** the partner item's unit proposes the line's unit.
    - **ADR-0020 rules 3, 18:** material lines carry the source line's inventory quantity; counts in several units.
    - **ADR-0023 rules 6, 14, 18:** handling units against packaging; the pick breakdown, the default pick unit and follow-up tasks for recomputed parts; count entry units.
    - **ADR-0024 rules 2, 6, 15, 18, 22:** the supplier order unit and container units; units in planning; lot sizing in the order unit, proposals rounded up; the planned order's order unit; request lines carry it.
    - **ADR-0030 rule 9:** imports resolve unit text through aliases.
    - **ADR-0033 rules 6, 7:** the component snapshot, the alignment of rule 6's text, issue multiples, scrap rounding and precision; the outputs' snapshot and their half-up rounding.
    - **ADR-0034 rules 8, 11–13:** posted lines keep their snapshot; issue, backflush and receipt lines carry the block.
    - **ADR-0041 rule 22:** the seam for quantity-based taxes and the customs unit.
    - **ADR-0044 rules 3, 9:** units first in phase 2, sales history in the inventory unit; opening stock lines carry the block.
    - **ADR-0045 rules 3, 4, 13:** price entries in any allowed unit and at a replacement (with the next-business-date remedy); `convert_quantity` in `find_price` with the worked example; the unit command checks.
    - **ADR-0046 rule 15:** configured items' own units in the configured price.
    - **ADR-0047 rules 1, 2, 7, 8, 11, 13–15, 17, 20, 21:** the clearing's registration; follow-on units and copies; prices of returns and credits in another unit; the receipt tolerance on the ordered quantity; positions with the cumulative rule and the GR/IR rounding clearing; the match per inventory unit and the tolerance amount's unit; purchase return and credit lines with the block; promotion quantities; limits with the unit rounding tolerance; the clearing's posting.
    - **ADR-0049 rule 25:** the line's own unit and its name on prints.
    - **ADR-0051 rule 21:** D2 and D3 in units.
    - **ADR-0053 rule 16:** core translations and package statutory names of units.

25. **Catalog rows:**
    - **New catalogs,** owner DS-20, version 0.1.0, listed in the catalogs README: `units.csv` (15 core units) and `unit-conversions.csv` (12 direct pairs).
    - **Package data:** a package's `i18n/<language>/unit_names.csv`, checked by `check_package.py` against `units.csv` (every core unit named once, with a basis); `l10n_vn`'s draft is DS-19's. **Setting:** the regime setting `documents.unit_name_max_length`.
    - **Errors:** `uom_retired`, `uom_kind_mismatch`, `serial_unit_not_exact`, `uom_conversion_conflict`, `uom_packaging_inconsistent` (validation); `uom_conversion_in_use`, `price_entry_starts_today` (precondition); `uom_not_allowed` widened.
    - **Check results:** `unit_inexact`, `unit_text_unresolved`, `product_uom_replaced`, `uom_factor_changed`, `part_quantity_recomputed`, `part_quantity_clamped`, `gr_ir_rounding_cleared`, `gr_ir_rounding_clearing_reversed`, `unit_name_too_long`, `unit_step_below_inventory_step`; `quantity_rounded` and `quantity_rounds_to_zero` restated; `reversal_not_latest` notes that the clearing never counts.
    - **Document type:** `gr_ir_rounding_clearing` (`purchasing`, internal, consequence posting), its authorization leaf under purchasing, and the GR/IR posting kind `rounding_clearing`.
    - **Invariants**, a new block INV-600 to INV-619 for units of measure (INV-606 to INV-619 unused):
      - **INV-600:** every line's unit block is present and consistent. The snapshot equals `convert_quantity` for its item and unit when the line's unit was set, or its source line's snapshot for a line in the source's unit. The inventory quantity is `round_quantity(quantity × factor)` in the line's mode, or the cumulative value of INV-601;
      - **INV-601:** for every posted source line (for invoices, the order line), each forward part in its unit posted `round((C + q) × f) − P` at its snapshot, positive and clamped to between `q × f − 1` and `q × f + 1` inventory units (a value of zero or less is rejected), with C and P the actual net sums of the earlier posted parts in that unit; each return, credit or reversal of a part in the part's unit mirrors the part or takes its cumulative share of the part's stored inventory quantity, never exceeding it; a money-side return naming a stock return line in its unit and entered quantity posted that line's inventory quantity; T(S) grew only by rounded parts in other units and by the changes returns, credits, reversals and clamps made to the deviation; and when C reaches the source's entered quantity, P is within T(S) of its inventory quantity, and equal to it when T(S) is zero;
      - **INV-602:** stock is only in the inventory unit. Every material line's quantity equals its source document line's inventory quantity, and stock, reservation, demand, supply and planned quantities are at the inventory unit's decimals;
      - **INV-603:** every line whose snapshot source is `item` or `product` carries the factor of the row in force for its item and unit when its snapshot was taken, at the level it names: an item row before the product row, a level with rows but none in force uncovering nothing, a row in force from its `recorded_at` until its `retired_at`. A follow-on line keeping its source line's snapshot is exempt. No line, price entry, supplier item or product default names a retired company unit or global conversion after its retirement, on the same exemption;
      - **INV-604:** every unit a serial-tracked product resolves (its product and item rows and catalog units) is exact, and every line of such a product has an exact snapshot;
      - **INV-605** (area master data): every product unit's `is_exact` equals rule 7's formula; a row names a catalog-convertible unit only with `factor_source` `catalog` and the catalog's factor; at most one active row per product, item and unit; and every packaging row's factor equals `contains_quantity` × the contained unit's factor.
    - **Edge cases** EC-101 to EC-109: a carton of 24 bought in cartons and received in pieces; a bag of 7/3 kg in three partial receipts; grams against kilograms through the catalog; an item-level unit overriding the product's; a retired unit refused on a new line and accepted on a follow-on line; an e-invoice with unknown unit text; an invoice per kg against an order in bags; a bill of materials in cans with an issue multiple; a supplier order unit with a minimum and multiple in cartons. EC-130 and EC-131: the return of one receipt of an inexact unit and the supplier's credit for it; 8.000 kg ordered and delivered as three bags of 8/3 kg within the unit rounding tolerance.

26. **Lab check `t17_uom.py`** ([validation lab](../reviews/2026-11-14-design-validation/README.md)):
    - **Pure functions:**
      - `convert_quantity` resolution (item, product, global in both directions, no chaining, retired rows);
      - exactness;
      - the cumulative rule on the 7/3 bag, returns of a part, and random sequences of parts, whole and partial returns, reversals in any order and parts in other units;
      - the unit rounding tolerance both ways, growing only by changes of the deviation (zero for exact units: cartons of 24 on pieces); parts of zero or less rejected (the 3/5-piece and 1/6-bar examples, with the smallest quantity that would post), the unit step warning, clamped parts, the per-posting growth of T and the gross-error bound on forward parts and returns, over 20,000 sequences with inventory units of 0 to 3 decimals and entered units of 0 to 2; money returns following their stock returns, purchase and sales side; invoices sourced by the order line; the GR/IR rounding clearing fired, reversed by a later credit and fired again; provisional parts recomputed at Post and drafts re-resolved after a retirement;
      - price entries, transitive packaging and item-level rows at a replacement; catalog rows; the fold table;
      - the carton and g↔kg examples;
      - `round_quantity` modes and scrap;
      - the serial whole factor;
      - the proposed-unit order;
      - supplier minimum and multiple in the order unit;
      - three-way match per inventory unit;
      - the price-break example;
      - packaging consistency;
      - the issue multiple;
      - alias normalization.
    - **With `--load`**, on all DDL loaded by `load_all.py`:
      - a purchase order in cartons, receipts in pieces, an invoice in cartons, and GR/IR at zero;
      - the bag order with cumulative receipts;
      - the unit block present on every quantity line table;
      - the database refusing bad factors and snapshots;
      - retirement and the default pick unit;
      - retire and replace of a kg row on the same unit (old lines keep the old snapshot, new lines take the new factor, one active row);
      - item barcodes unique per company; the clearing posting kind;
      - INV-603 over every line table, by level and time in force.

## Context

The holistic review found the multi-UoM core sound but incomplete. The audit (29 findings) found three blocking gaps:
- rounded inventory quantities that do not add up along a chain;
- no unit rules for follow-on documents;
- supplier minimums that hang on a mutable product field.

It also found correction lines without a unit, production and stock lines without one, no unit names for e-invoices, no seed catalog and no migration of units. The six-flow simulation used one unit with 0 decimals, so no multi-unit path had been exercised beyond the price lookup. The author asked for multi-UoM to be researched broadly and its design completed before more testing, with conversions defined on the item master.

The 2026-11-15 survey compared SAP S/4HANA, Dynamics 365, Odoo, NetSuite, SAP Business One and Oracle Fusion, with statutory e-invoice formats and UN/ECE and GS1 standards:
- **One valuation unit.** Every system keeps stock and value in one unit per product, so rule 1 matches the market.
- **More specific scopes.** Conversions moved from global or group scope to product, variant and lot scope over the last years. Dynamics 365 added per-variant conversions because pack sizes depend on size. That is why rule 4 adds item-level rows now, while every lookup still goes through one function.
- **Rounding drift.** Business Central's "5/6 box becomes 4.99998 pieces", Odoo's 2101 instead of 2100, and SAP's invoice-verification rounding differences show the drift the cumulative rule (rule 10) prevents. The survey found no system that solves it; ERPMe reuses its own GR/IR technique.
- **Changed conversions.** Dynamics 365's most common released-quantity failure is a conversion changed under open documents. Oracle and Business One block changes instead. Snapshots and retire-and-replace (rules 5, 9) make blocking unnecessary.
- **A second factor.** SAP's info-record factor differing from the material factor distorts valuation. Business One, NetSuite and Dynamics 365 work without supplier factors, hence rule 14.
- **Packaging.** Odoo 19 merged packaging into units, and the GS1 hierarchy records the quantity of the next level (rule 15).
- **Statutory e-invoices.** Some regimes carry the unit as free text per line, with a length limit. That needs the line's own unit name on statutory outputs, a per-regime length setting (rule 18) and an alias table for intake (rule 19), which no surveyed system has. The legal sources stay in the packages (ADR-0053).
- **Catch weight** is the largest feature swamp in every system that has it, so it waits (rule 22).

ADR-0005: the agent decides technical points, with SAP as reference when unsure, and the easiest option for AI agents wins among correct ones. One resolution function with an explicit source, a snapshot that makes each line self-describing, and `GetItemUnits` serve that goal.

## Options considered

| Option | For | Against |
| --- | --- | --- |
| Inventory unit only for stock, cost, planning and GR/IR (chosen, confirmed) | The whole market does it; costing never sees a factor | Users see inventory units in some views; the client shows both |
| Conversions per product only (ADR-0018 as it was) | One level | Variants and configured items that differ in length or pack cannot convert; adding the level later changes every lookup |
| Item-level rows on `product_uom`, item → product → global (chosen) | Dynamics 365's per-variant pattern; one table and one function | One more level; the source must be shown |
| Inherited item fields overriding product fields in general | Flexible | ADR-0018 rejected inheritance; units are the one place where an override is needed, and it is a row, not a field |
| Re-read the factor from master data | No extra columns | Factors cannot be recovered from rounded quantities; a changed row would change history |
| Snapshot on every line (chosen) | Self-describing lines for agents and auditors; reproducible hashes | Three columns per line |
| Effective-dated conversions | Changes without new codes | No surveyed system has them; snapshots make them unnecessary; dated lookups everywhere |
| Retire and replace by a new row of the same unit, unique among active rows (chosen) | Users keep their unit codes; lines are unambiguous through their snapshots | Price entries in the unit must be end-dated and supplier items and barcodes reviewed (`product_uom_replaced`) |
| Retire and replace with a new unit code | A price or supplier item for the old pack can never price the new one | A new code for each real pack change, even for core units such as kg |
| Reject inexact product units | No rounding at all | Real factors such as 7/3 kg per bag exist; companies would enter wrong factors |
| Per-line rounding only (ADR-0018 as it was) | Simple, stateless | Partial receipts never add up; residuals need human write-offs |
| Cumulative rounding per source line (chosen) | Parts sum exactly; the GR/IR technique already proven in the lab | Follow-on conversion depends on earlier parts |
| Follow-on lines only in the source's unit | Cumulative rule always applies | Pieces cannot be received against cartons; the practical escape from inexact units is closed |
| Supplier-specific factors (SAP info record) | One unit code for every supplier's carton | A second factor per item and unit distorts cost (SAP's own failure class) |
| Supplier order unit naming a product unit (chosen) | One factor per item and unit everywhere | More product units for multi-supplier items |
| A separate order price unit now | Order in pieces, price per kg | Without a real second quantity it is a supplier factor; it belongs with catch weight |
| Packaging as a separate table | Mirrors GS1 | Two lists of units that must agree (Odoo's lesson); packaging as product units with a `contains` relation instead (chosen) |
| Returns re-run the cumulative rule on the source line | One formula | A return could post more than the part it returns (2.334 against 2.333) |
| Returns take the part they name as source (chosen) | Never more than the part; forward parts self-correct | Two levels of source to count; a money return must follow its stock return, and clamps and returns widen the tolerance |
| Guess unit text by similarity | Fewer unresolved lines | A wrong unit silently scales a quantity; aliases with proposals instead (chosen) |

## Constraints that come with the decision

- **DDL:**
  - DS-20: `uom.name`; `uom_conversion` with `id`, `is_active` and the canonical direction; `product_uom` rebuilt (surrogate `id`, `item_id`, `inventory_uom_id`, `factor_source`, `is_exact`, packaging and flags, `recorded_at`, `is_active`, `retired_at`, one active row per unit); `product` gains a key on (company, id, inventory unit); new `uom_alias`; `item_barcode` gains a surrogate `id` with `UNIQUE (company_id, barcode)`.
  - DS-43-54: `supplier_item.order_uom_id`; the snapshot on bill of materials components and outputs (renamed `uom_numerator`, `uom_denominator`, defaults dropped) and `issue_multiple`; the order unit on `planned_order`; the line unit block on replenishment request, production issue, production receipt and backflush lines.
  - DS-22-09-42: the snapshot on every quantity line; `uom_id`, the snapshot and, where missing, `item_id` and `quantity` on credit note, purchase return and purchase credit note lines; the GR/IR posting kind `rounding_clearing`.
- **Commands:** `convert_quantity`, `convert_part` and `normalize_unit_text` in `master_data.contract`, pure; every handler that posts a part of a source line calls `convert_part`.
- **DS-04:** the errors and check results of rule 25.
- **Catalogs:** `units.csv`, `unit-conversions.csv`; INV-600 to INV-605; EC-101 to EC-109, EC-130, EC-131 (the edge-case file sorted by code); the DS-16 area `master_data`; the authorization leaf `gr_ir_rounding_clearing`.
- **Packages:** statutory unit names and the value of `documents.unit_name_max_length` (`l10n_vn`'s drafts in DS-19, unverified).
- **Lab:** `t17_uom.py`; fixture updates in `t01`, `t05`, `t06`, `t14` and `t16` for `uom.name`, the new `product_uom` and `uom_conversion` shape, and the snapshot columns.
- **Other design items:** DS-16 (the invariants); DS-17 (the edge cases, profiles with a carton, a 7/3 bag and grams); DS-24 (the unit name on e-invoice lines, the intake's alias resolution); DS-30 (screens showing entered and inventory quantities, the factor source and `unit_inexact`); DS-31 (scanning per packaging unit, count entry in counting units); DS-42 (transfer and count line DDL with the block).
- **Open questions:** `l10n_vn`'s statutory unit names and their length; the interim choices of this ADR, including where unit names live.

## Revisit when

- A customer needs catch weight, lot-specific factors or an order price unit (rule 22).
- Mixed-unit residuals within the unit rounding tolerance (rule 10) create more close-checklist work than expected.
- A company needs a different number of decimals for a core unit than the catalog gives.
- The e-invoice format limits unit names below the names a package ships.

## Documents updated

- **This ADR** (new) and the index row in [docs/adr/README.md](README.md).
- **The DDL drafts:** [docs/design/DS-20-master-data.sql](../design/DS-20-master-data.sql), [docs/design/DS-22-09-42-commercial-inventory.sql](../design/DS-22-09-42-commercial-inventory.sql), [docs/design/DS-43-54-planning-production.sql](../design/DS-43-54-planning-production.sql).
- **ADRs:** notes in ADR-0006, ADR-0016, ADR-0018, ADR-0019, ADR-0020, ADR-0023, ADR-0024, ADR-0030, ADR-0033, ADR-0034, ADR-0041, ADR-0044, ADR-0045, ADR-0046, ADR-0047, ADR-0049, ADR-0051 and ADR-0053 (rule 24).
- **Design files:** [docs/design/DS-04-command-envelope.md](../design/DS-04-command-envelope.md), [docs/design/DS-16-invariants-and-harness.md](../design/DS-16-invariants-and-harness.md), [docs/design/DS-17-synthetic-dataset.md](../design/DS-17-synthetic-dataset.md), [docs/design/backlog.md](../design/backlog.md).
- **Catalogs:** [units.csv](../catalogs/units.csv), [unit-conversions.csv](../catalogs/unit-conversions.csv) (new); [invariants.csv](../catalogs/invariants.csv), [edge-cases.csv](../catalogs/edge-cases.csv), [README.md](../catalogs/README.md).
- **Package:** [docs/design/DS-19-vietnam-tt99/](../design/DS-19-vietnam-tt99/README.md): `i18n/vi/unit_names.csv` (new), the setting `documents.unit_name_max_length`, manifest and README.
- **Glossary:** [docs/spec/00-reading-guide.md](../spec/00-reading-guide.md) (rows only).
- **Open questions:** [docs/open-questions.md](../open-questions.md).
- **The lab:** [docs/reviews/2026-11-14-design-validation/](../reviews/2026-11-14-design-validation/README.md): `lab/t17_uom.py` (new), the fixtures of t01, t05, t06, t14 and t16, and `check_package.py`.
- **Log:** [docs/runbook/step-log.md](../runbook/step-log.md) at acceptance.
