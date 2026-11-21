Module: master_data    Chunk: 5 of 8    Source ADRs: ADR-0056
Build step(s): 4    Generated from index: 30d5706    Compiled by: Claude Opus 5.5, 2026-11-21

# Compiled spec: `master_data`, chunk 5

## Purpose

`master_data` owns partners, products, items, units, prices, warehouses and organization structures, in layer 3
(ADR-0022.R2). This chunk states the multi-unit rules of ADR-0056 from rule 7 on: exact and inexact units, rounding by
use, the line unit block, the cumulative rule and GR/IR rounding clearing, follow-on lines in any unit, one unit and one
price per line, the proposed unit, packaging units, price breaks per unit, unit names on prints, unit aliases, the agent
contract, and the Phase 1 scope and seams. Units, global conversions and product units themselves (ADR-0056 rules 1 to 6)
are in another chunk; migration of units belongs to `imports`.

## Entities and tables

DDL: `docs/design/DS-20-master-data.sql`.

| Table | Meaning | Key | Parent | Owner |
| --- | --- | --- | --- | --- |
| `uom_alias` | Unit text as partners and old systems write it, mapped to a unit, for intake (R853) | `id`; unique (`company_id`, `normalized_alias`) | `company` | `master_data` |

The rules of this chunk also constrain tables whose rows stand in other chunks: `product_uom` (packaging, counting and
pick columns, R842-R845; `is_exact`, R802), `uom` and `uom_conversion` (R867), and `partner_item` (`uom_id`,
`partner_uom_text`; R840, R854).

Reads: the document line tables of `sales`, `purchasing`, `inventory`, `production` and `planning` that carry the line unit
block (R812), `return_to_supplier_line`, `purchase_return_line`, `return_from_customer_line`, `sales_return_line`,
`purchase_order_line_gr_ir_posting`, `material_document_line`, `operation_progress_component`, `gr_ir_write_off_line`,
`supplier_item`, `supplier_purchasing_term`, `handling_unit_type`, `data_translation`, `document`.

## Commands and queries

| Name | Actor and authorization | Input | Effect | Events | Error codes |
| --- | --- | --- | --- | --- | --- |
| `GetItemUnits` | leaf `product`, `read` | An item | Computed query: every allowed unit of the item with its factor, exactness, flags, barcodes and `is_active` (R857) | not stated | not stated |
| `CreateProductUom` | leaf `product_unit`, `edit`; `master_data_change`, change-tracked | A product or item unit row | Creates the row and computes and stores `is_exact` (R802) | not stated | `uom_conversion_conflict` (R658), `serial_unit_not_exact` (R660), `uom_packaging_inconsistent` (R843); check results `unit_inexact`, `unit_step_below_inventory_step` |
| `UpdateProductUom` | leaf `product_unit`, `edit`; `master_data_change`, change-tracked | Flags; retirement; or retirement with a replacement row for the same unit | Changes flags or retires the row; a replacement end-dates the unit's open price entries; a used factor never changes (R858) | not stated | `uom_conversion_in_use` (R661), `price_entry_starts_today` (R664), `uom_packaging_inconsistent` (R665); check result `product_uom_replaced` (R666) |
| `CreateUom` | leaf `product_unit`, `edit`; `master_data_change`, change-tracked | A company unit | Creates the company unit | not stated | not stated |
| `UpdateUom` | leaf `product_unit`, `edit`; `master_data_change`, change-tracked | A company unit | Changes the company unit | not stated | not stated |
| `CreateUomAlias` | leaf `uom_alias`, `edit`; `master_data_change`, change-tracked | Alias text and unit | Creates a `uom_alias` row; an agent proposes it through a change proposal (R855) | not stated | not stated |
| `UpdateUomAlias` | leaf `uom_alias`, `edit`; `master_data_change`, change-tracked | An alias | Changes the alias | not stated | not stated |

Not commands, declared by `master_data`: the pure functions `master_data.contract.convert_part` (R833) and
`master_data.contract.normalize_unit_text` (R853).

The consequence posting `gr_ir_rounding_clearing` (document type under `purchasing`, level `full`) has an
`is_internal_only` `Post`; its rule is R830.

Codes of the unit rules, bound to no single command (R859, R860): errors `uom_not_allowed`, `uom_retired`,
`uom_kind_mismatch`, `serial_unit_not_exact`, `uom_conversion_conflict`, `uom_packaging_inconsistent`,
`uom_conversion_in_use`, `price_entry_starts_today`, `quantity_rounds_to_zero`, `too_many_decimal_places`; check results
`quantity_rounded`, `unit_inexact`, `unit_text_unresolved`, `product_uom_replaced`, `uom_factor_changed`,
`part_quantity_recomputed`, `part_quantity_clamped`, `gr_ir_rounding_cleared`, `gr_ir_rounding_clearing_reversed`,
`unit_name_too_long`, `unit_step_below_inventory_step`.

## Rules

### Exact and inexact units

R801. A conversion from an entered unit E (with `dE` decimal places) to the inventory unit I (`dI` places) with factor n / d is exact when `n × 10^dI` is divisible by `d × 10^dE`. Then every quantity that E can hold converts to a quantity I can hold, and a line never rounds. Otherwise it is inexact: some quantities round, and the cumulative rule (R819) keeps parts adding up.
Source: ADR-0056.R7

R802. `CreateProductUom` computes `is_exact` and stores it. An inexact row is accepted with the check result `unit_inexact` (`details`: factor, decimals, `reason` `decimals`). Global conversions are classified the same way at each use. When one step of the entered unit converts to less than half a step of the inventory unit (`10^−dE × n / d < 10^−dI / 2`), the smallest quantities of the unit round to zero, so `CreateProductUom` also warns with the check result `unit_step_below_inventory_step`: the unit's usual quantities may fall below one inventory step, a master-data problem to settle at creation, not at the dock (R808).
Source: ADR-0056.R7

R803. A line in an inexact or `nominal` unit returns `unit_inexact` with its reason (`decimals` or `nominal`). Inexact units are allowed (1 bag = 7/3 kg is real).
Source: ADR-0056.R7

### Rounding by use

R804. Every converted quantity is rounded once, by `round_quantity(value, unit, mode)` (ADR-0006.R15, ADR-0006.R17), to the target unit's decimals, in the mode its use names. Rounding never changes an amount (ADR-0006.R19).
Source: ADR-0056.R8

R805. Mode `up` applies to requirements; planning proposals, purchase, transfer and production alike (their lot sizes included); supplier minimums and multiples (ADR-0056.R14); issue multiples (ADR-0056.R17); backflush (ADR-0034.R12). Under-supply is the error these uses avoid.
Source: ADR-0056.R8

R806. Mode `half_up` (half away from zero) applies to receipts, deliveries, invoices, returns, credits, counts, transfers and issues a person enters. Planned co-product and by-product quantities also round half up, each in its own inventory unit: they are expected yields, not requirements (ADR-0033.R7).
Source: ADR-0056.R8

R807. Scrap: the planned output quantity Q = G / (1 − assembly scrap) is rounded up once, to the main output's inventory unit, when the order stores it. Each component requirement is computed from that stored Q, exactly, and rounded up once to the component's inventory unit (ADR-0033.R6).
Source: ADR-0056.R8

R808. A rounded line returns `quantity_rounded` with the exact and the rounded value (ADR-0018.R11). A line whose inventory quantity rounds to zero is rejected with the error `quantity_rounds_to_zero`, and so is a forward part against a source line whose cumulative value computes to zero or less (R820): no part ever posts a quantity its entered quantity did not earn. A unit whose usual quantities fall below one inventory step is a master-data problem: the inventory unit is the smallest unit the company sells or counts (ADR-0018.R11), and the workaround of R865 keeps stock in the finer unit. An entered quantity with more decimals than its unit holds is rejected, never rounded (ADR-0006.R14).
Source: ADR-0056.R8

### The line unit block

R809. Every quantity line stores these fields:
- `quantity`, as entered, in `uom_id`;
- `uom_id`;
- `uom_numerator` and `uom_denominator`: the factor to the inventory unit used when the line's unit was set;
- `uom_factor_source`: `identity`, `item`, `product` or `global` (ADR-0056.R6);
- `inventory_quantity`.
Source: ADR-0056.R9

R810. The snapshot is taken when the line's unit or item is set on a draft and is never read again from master data. Copies to follow-on lines in the same unit, the cumulative rule (R819), reversals and reprints use it. A draft line whose unit or item changes is resolved and snapshotted again.
Source: ADR-0056.R9

R811. A draft line snapshotted before its row was retired or superseded (ADR-0056.R5) posts at its snapshot only if it is a follow-on line keeping its source line's snapshot. Any other draft line is resolved again at Submit and again at Post: its entered quantity stays, its inventory quantity follows the new factor, and the check result `uom_factor_changed` names it. A change after approval changes the plan hash, so the document returns to draft for a new approval (ADR-0009). The line is re-priced from the entries in force; the old pack's price is not kept, unless the price is manual.
Source: ADR-0056.R9

R812. The tables with the block (DDL in DS-22-09-42 and DS-43-54) are:
- quotation, sales order, delivery, return from customer, sales invoice, sales return and credit note lines;
- purchase request, purchase order, goods receipt, return to supplier, service receipt, purchase invoice, purchase return and purchase credit note lines;
- production issue, production receipt and generated backflush lines (`operation_progress_component`), and replenishment request lines;
- transfer order and stock count lines, when their DDL is drafted (DS-42).
On lines whose quantity is optional (amount-only credits, expense invoice lines), the block's fields are all set or all empty.
Source: ADR-0056.R9

R813. Bill of materials components and outputs store `quantity`, `uom_id` and the snapshot but no inventory quantity, which stays an exact rational per base quantity (ADR-0056.R17). A planned order keeps `quantity` in the inventory unit and stores its order unit as `order_quantity`, `order_uom_id` and the snapshot (ADR-0056.R14). Generated backflush lines are written in the inventory unit, source `identity`, which the database holds.
Source: ADR-0056.R9

R814. In the inventory unit only: `material_document_line`, stock rows, reservations, warehouse tasks (whose `uom_id` is the demand line's unit, for display only), demand and supply rows, planned order components, production order components and outputs, and `gr_ir_write_off_line`.
Source: ADR-0056.R9

R815. On every table with the block the database holds: positive factors; a known source; `identity` only with 1/1 and an inventory quantity equal to the entered one; and `|inventory_quantity × uom_denominator − quantity × uom_numerator| ≤ 2 × uom_denominator`. This gross-error check keeps the inventory quantity within two inventory units of the exact conversion; the rules keep the bound: per-line rounding stays within half a step, a forward part is clamped to within one inventory unit (R821), and a return's share of a part stays strictly below two units, at most `r / q` of a unit plus one rounding step (R822). A carton line stored as one piece is refused; the exact rounding is not checked there. Whether the snapshot is the right factor for the item and unit, and the exact rounding, are command rules with invariants (ADR-0056.R25).
Source: ADR-0056.R9

R816. Every unit price on a line is per that line's `uom_id` (R838).
Source: ADR-0056.R9

### The cumulative rule

R817. A source line S has entered quantity q_S in unit U, factor f (the snapshot of S) and inventory quantity `Q_S = round(q_S × f)`. Forward parts refer to S: receipts of a purchase order line, deliveries of a sales order line, invoices, and issues of a component line. Returns, credits and reversals refer to a posted part.
Source: ADR-0056.R10

R818. The source of an invoice is always the order line, for stock lines too: C and P count the order line's invoices, and the delivery or receipt line an invoice line names serves matching only.
Source: ADR-0056.R10

R819. Forward parts are in U, at the snapshot of S. C is the actual net entered quantity in U of the posted parts of S (forward parts less their returns, credits and reversals), and P their actual net inventory quantity. A forward part of q has inventory quantity `round((C + q) × f) − P`, rounded in the mode of S (R804). After any forward part, P equals `round(C × f)`, whatever came before.
Source: ADR-0056.R10

R820. A forward part whose computed value is zero or less is rejected with `quantity_rounds_to_zero` (R808), as a line with no source is; posting a step instead would inflate the line. The error's `details` give the smallest entered quantity that would post, so for an occasional small part the person receives a larger quantity. A unit whose usual quantities fall below one inventory step is a master-data problem: stock belongs in the finer unit (ADR-0018.R11; R865, `nominal` when lengths vary); `unit_step_below_inventory_step` flags such units at creation (R802). A completing part computes to zero or less only when P has already reached Q_S, so the line was fulfilled, and closed, at the earlier posting; refusing it closes nothing.
Source: ADR-0056.R10

R821. A positive computed value of a forward part is clamped to the band from `q × f − 1` to `q × f + 1` inventory units (the bounds rounded inward to the unit's decimals), with the check result `part_quantity_clamped` when the clamp changed it. The change counts in the unit rounding tolerance T(S) (R826), so the limits and the closing check absorb it, and the part stays within one inventory unit of its exact conversion.
Source: ADR-0056.R10

R822. Returns, credits and reversals take the part they name as their source, in that part's unit. A reversal, or a return of the whole part, mirrors the part's stored inventory quantity. A partial return takes its cumulative share of the part: `round(v × (r₀ + r) / q) − v₀`, where q and v are the part's entered and stored inventory quantities and r₀ and v₀ what the part's earlier returns took. The returns of a part sum exactly to its stored inventory quantity and never exceed it, even when the part was clamped; a share is within `r / q` of a unit plus one rounding step, below two units. A partial return whose share rounds to zero is rejected (`quantity_rounds_to_zero`); the small entered rest it leaves on the part is accepted. A return or credit in another unit converts on its own. A return never posts more than the part it returns.
Source: ADR-0056.R10

R823. A return to supplier of a part of a purchase order line takes its inventory quantity from the part it names (R822), but moves GR/IR at the line's latest received positions (ADR-0047.R13). `return_to_supplier_line.gr_ir_position_from` and `gr_ir_position_to` store the positions actually debited, from R − q to R; `goods_receipt_line_id` stores the named part. Under the interim regime seed of `purchase_return` (value source `document`), the value that leaves stock is that GR/IR debit, `round(V(R)) − round(V(R − q))`, so the return posts no price difference (ADR-0020.R5).
Source: ADR-0056.R10, ADR-0056.R10.N1

R824. A money return follows its stock return: a money-side return line that names a stock return line in the same unit and for the same entered quantity takes that stock line's inventory quantity: a `purchase_return_line` naming its `return_to_supplier_line`, a `sales_return_line` naming its `return_from_customer_line`. Then R and I move by the same quantity and GR/IR stays zero; on the sales side, invoiced net equals delivered net again and `sales_return_due` closes.
Source: ADR-0056.R10

R825. A forward part that brings C to q_S brings P to Q_S, unless a clamped part or a return, credit or reversal left a deviation, which stays within T(S); parts in U that complete S sum exactly to its inventory quantity, and the returns of a part never exceed the part. Reversals need no order of their own: a part that a return or credit names cannot be reversed (`document_referenced`, ADR-0009.R18), and a mirrored reversal of an unreturned part only shifts C and P, which the next forward part corrects. GR/IR keeps its latest-only rule for documents with purchase order lines (ADR-0047.R13).
Source: ADR-0056.R10

R826. The unit rounding tolerance T(S) grows by one smallest step of the inventory unit (`10^−dI`) for each part of S posted in another unit whose conversion rounded (`quantity_rounded`), and, for each return, credit or reversal of a part in U and each clamped forward part, by the amount it changed the deviation `P − round(C × f)` (nothing when it left the deviation unchanged); the part being posted counts. T(S) grows monotonically: a counted part that is later reversed stays counted. Each deviation-changing posting adds below three inventory units for a return or credit and at most one unit plus one step for a reversal or a clamp. A part in another unit converts on its own (`round(q × its factor)`) and takes no part in C or P. With an exact snapshot and none of these parts, T(S) is zero and every comparison is exact.
Source: ADR-0056.R10

R827. T(S) applies both ways: the upper limits `quantity_exceeds_open`, `receipt_exceeds_order` (after the receipt tolerance), `invoice_exceeds_delivered` and `correction_exceeds_original` allow T(S) more, and S counts as fulfilled by quantity when its fulfilled inventory quantity is within T(S) of Q_S.
Source: ADR-0056.R10

R828. GR/IR rounding clearing: when a purchase order line is fulfilled within its tolerance and its received net R and invoiced net I both lie within T(S) of its inventory quantity but differ, or when a closed line's R and I differ by no more than T(S), whatever they stand at against Q_S, the system posts `gr_ir_rounding_clearing`. It posts on the lagging side at the positions' value (ADR-0047.R13): on R, crediting GR/IR with `round(V(I)) − round(V(R))`, when I > R; on I, debiting it with `round(V(R)) − round(V(I))`, when R > I; against the regime's `price_difference` key (ADR-0047.R21). Its positions count in R or I for GR/IR, so `INV-92` holds with them, and never in received or invoiced quantities. It runs only within T(S); a larger difference stays the closed-short path of ADR-0047.R13.
Source: ADR-0056.R10

R829. The clearing never counts in the latest-only reversal check of ADR-0047.R13, so it never blocks a reversal. Every later GR/IR posting on the line (a receipt, invoice, return, credit, reversal or `gr_ir_write_off`) first reverses an active clearing as a consequence, in the same transaction; the clearing fires again when the line is still, or again, within tolerance.
Source: ADR-0056.R10

R830. Document type `gr_ir_rounding_clearing`: `purchasing`, posting, internal, no change orders, not e-invoice capable, no approval hold, reversed only as a consequence (never by `Reverse`), not item-creating. Its `Post` is `is_internal_only` and `is_consequence_posting`; no template's expansion holds it, and its authorization leaf sits under purchasing at level `full`. It has its own `document` row and no header or line table: the `purchase_order_line_gr_ir_posting` row of kind `rounding_clearing` carries the line, positions and amount. The command that triggered it returns `gr_ir_rounding_cleared`, or `gr_ir_rounding_clearing_reversed`.
Source: ADR-0056.R10

R831. The clearing is the posting that makes R = I for the interim company-currency rule of ADR-0047.R13, so it also clears the line's company-currency residual: to realized exchange difference on a line without stock, and on a line for an item kept in stock as the setting `costing.exchange_rate_difference_to_stock` chooses (ADR-0047.R13.N3, ADR-0047.R13.N4): true, the default, posts it to `purchase_cost_clearing` and writes a `landed_cost` of `cost_type` `exchange_rate_difference` on the line's receipt lines, so it enters the item's actual cost; false posts it to `fx_gain_realized` or `fx_loss_realized` and keeps it out of actual cost; the clearing reads the value in force on its posting date; reversing the clearing reverses that entry too.
Source: ADR-0056.R10

R832. A part's inventory quantity is provisional on a draft and recomputed at Post from the then-posted C and P, under the source document's lock. A reservation or open pick task made for the provisional quantity is adjusted by the difference at Post. A pick task already confirmed at the provisional quantity is not changed: the difference becomes a follow-up warehouse task, an extra pick or a putaway back. Either way the check result `part_quantity_recomputed` names it. `INV-600` and `INV-601` apply to posted parts.
Source: ADR-0056.R10

R833. One function, `master_data.contract.convert_part(f, C, P, q, unit, mode)`, pure, is called by every handler that posts a part; returns and credits call it with the part as source.
Source: ADR-0056.R10

### Follow-on lines in any unit

R834. A receipt, delivery, invoice, return, credit, production issue or receipt may use any allowed unit of the item (ADR-0056.R6), whatever the unit of the line it refers to. Every quantity relation compares inventory quantities: links and open quantities, `quantity_exceeds_open`, correction limits (ADR-0047.R20), the receipt tolerance, the three-way match quantity and GR/IR positions.
Source: ADR-0056.R11

R835. The receipt tolerance applies to the ordered quantity, not to the open quantity: received net inventory quantity ≤ the order line's inventory quantity × (1 + `inventory.purchase_receipt_tolerance_percent` / 100), plus T(S) (R826). A partial receipt cannot earn the tolerance again.
Source: ADR-0056.R11

R836. `source_lines` quantities are in the source line's unit. A copied line takes the source line's unit and snapshot, so the cumulative rule applies to it. If the person changes the unit, the line is resolved again (ADR-0056.R6) and converts on its own.
Source: ADR-0056.R11

R837. Returns and credits priced from their original convert the original's price per inventory unit by their own factor: `round_unit_price(p × (n_o / d_o)⁻¹ × (n / d))`, where p is the original's net unit price after the document discount, n_o / d_o its snapshot and n / d the line's own. A line in the original's unit keeps p unchanged. A quantity credit is `round_amount(quantity × that price)` (ADR-0047.R8). A credit that brings the credited inventory quantity of an invoice line to its invoiced inventory quantity takes exactly the rest of the line's net amount.
Source: ADR-0056.R11

### One unit and one price per line

R838. A line has one unit, and its unit price, at up to 10 decimals (ADR-0006), is per that unit. There is no separate order price unit in Phase 1; a supplier who invoices per 1,000 pieces is served by a product unit `x-1000pcs` or by the 10-decimal price. The order price unit comes after Phase 1 with catch weight (R864).
Source: ADR-0056.R12

R839. The three-way match compares per inventory unit: the invoice line's net amount after the document discount, divided by its inventory quantity, is compared with `(V(I + q) − V(I)) / q`, the GR/IR value per unit of the positions the invoice reaches (ADR-0047.R14). `purchasing.match.price_tolerance_amount` is an amount per inventory unit, in the document currency.
Source: ADR-0056.R12

### The proposed unit

R840. A new line proposes its unit in this order, and the person may choose any allowed unit instead:
- a line copied from a source line: the source line's unit;
- a scanned barcode: the barcode's unit (ADR-0018.R14), or for a GS1 variable-measure scan the measure's unit (R841);
- the partner's own unit for the item, `partner_item.uom_id` (customer or supplier);
- purchasing: the supplier's order unit, `supplier_item.order_uom_id` (ADR-0056.R14);
- the product's `purchase_uom_id` or `sales_uom_id`;
- the inventory unit.
Bill of materials lines set their own unit. Count lines propose the inventory unit and accept the product's counting units (R844). The command response names the proposed unit's source in `proposed_uom_source`: `source_line`, `barcode`, `partner_item`, `supplier_item`, `product_default` or `inventory_unit`. A unit typed by the person or agent always wins and is not reported as proposed.
Source: ADR-0056.R13

R841. A GS1 scan that carries a variable-measure AI (310n net weight, 311n length, 314n area, 315n and 316n net volume) proposes the AI's unit and quantity instead of the barcode's unit: the measure enters in its own unit as the line's entered unit, which must be an allowed unit of the item (`uom_not_allowed`, ADR-0056.R6), and converts by `convert_quantity` in mode `half_up`, as for receipts (R806); `proposed_uom_source` stays `barcode`. The measure itself is never rounded: extra decimals that are zeros are dropped, any other extra decimal is `too_many_decimal_places` (ADR-0006.R14). A count AI, (30) or (37), keeps the barcode's unit (ADR-0061.R17, ADR-0061.R18).
Source: ADR-0056.R13, ADR-0056.R13.N1

### Packaging units

R842. Packaging is a product unit: there is one list of units per product, used by purchasing, sales, the warehouse and barcodes. On `product_uom`, `contains_uom_id` and `contains_quantity` say "1 pallet contains 40 cartons". `contains_quantity` is a whole number above 1, and the contained unit is the inventory unit or another product unit of the same product and item level. The database holds the shape: both fields or neither, a whole number above 1, not the row's own unit. Since factors rise strictly, a cycle cannot form.
Source: ADR-0056.R15

R843. The command checks that the row's factor equals `contains_quantity` × the contained unit's factor, exactly (`uom_packaging_inconsistent`). A row created from the hierarchy has `factor_source` `packaging`.
Source: ADR-0056.R15

R844. `is_counting_unit` marks the units a count may be entered in. A count may have several lines per item, bin and lot in different units; each converts with `half_up` and they sum in the inventory unit (ADR-0020.R18; ADR-0023.R18).
Source: ADR-0056.R15

R845. `is_default_pick_unit` marks at most one unit per product or item, which a pick list proposes when the demand line is in the inventory unit. The pick breakdown ("2 cartons and 3 pieces") uses the packaging hierarchy, from the largest whole unit down (ADR-0023.R14). A retired row cannot be the default pick unit; the database holds both rules. A catalog unit carries these flags through a `catalog` row (ADR-0056.R4).
Source: ADR-0056.R15

R846. After Phase 1: a quantity per handling unit type, and dimensions and weights per packaging unit (ADR-0018.R4). `handling_unit_type` stays the physical container (ADR-0023.R6).
Source: ADR-0056.R15

### Price breaks per unit

R847. ADR-0045.R4 stands. The entered unit's price list entries are searched first; when none qualifies, the quantity is converted exactly to the inventory unit, the inventory unit's entries are searched, and the price is multiplied by the factor and rounded half up to the unit-price scale. The entered unit's entry always wins. Breaks are in each entry's own unit. The factor is `convert_quantity`'s.
Source: ADR-0056.R16

R848. Promotions: `minimum_line_quantity`, `qualifying_quantity` and `free_quantity` are inventory-unit quantities of the line's item and the free item. `amount_per_unit` is per inventory unit and is multiplied by the line's factor and rounded once, as option extras are (ADR-0045.R17).
Source: ADR-0056.R16

R849. After Phase 1: a sales minimum or multiple and delivery rounding. When they come, they are check results with a proposal (`quantity_not_multiple`), never silent rounding.
Source: ADR-0056.R16

### Units on prints and e-invoices

R850. The print contract's `uom` object of a line (ADR-0049.R25) gives the unit's `code` and `name` in the print language. The name comes from the company's `data_translation` for company units, and from the core catalog for core units (ADR-0016.R19). A line prints its own unit and quantity, never re-expressed in the inventory unit.
Source: ADR-0056.R18

R851. Statutory outputs (e-invoice lines through the e-invoice add-on, DS-24, and prints a regime marks statutory) take the package's statutory unit name when present, else the core translation (ADR-0056.R2); the regime setting `documents.unit_name_source` (default `statutory_then_translation`, or `translation`) chooses between them (ADR-0063.R23).
Source: ADR-0056.R18

R852. The core registers the regime setting `documents.unit_name_max_length` (an integer, or empty for no limit); the package supplies its value. A company unit name or translation longer than the value returns the check result `unit_name_too_long` when it is saved, and a statutory output refuses a longer name instead of cutting it.
Source: ADR-0056.R18

### Unit aliases for intake

R853. `uom_alias` (company, `alias` as entered, `normalized_alias`, `uom_id`, `is_active`; unique per company and normalized text) maps unit text written by partners and old systems. Normalization is one pure function, `master_data.contract.normalize_unit_text`: lower case; Unicode NFKD with combining marks removed; the core's language-neutral fold table of ADR-0052.R17 (`đ`→`d`, `ð`→`d`, `ł`→`l`, `ø`→`o`, `ß`→`ss`, `æ`→`ae`, `œ`→`oe`, `þ`→`th`, `ı`→`i`, `ħ`→`h`); then whitespace and the characters `. - _ /` removed ("m²" becomes "m2").
Source: ADR-0056.R19

R854. Unit text for an item resolves to the first of: the partner's `partner_item.partner_uom_text` for the item; else an active alias; else a unit whose code equals the text. Every comparison is between normalized texts: partner texts, aliases and unit codes are normalized the same way. The unit must then be allowed for the item (ADR-0056.R6).
Source: ADR-0056.R19

R855. Unknown unit text is never guessed. The line stays unresolved with the check result `unit_text_unresolved`, and the agent proposes an alias through a change proposal (`CreateUomAlias`, `master_data_change`, ADR-0029).
Source: ADR-0056.R19

R856. The purchase invoice agent (ADR-0051.R21): D2 maps an e-invoice line's unit text by this resolution. D3 selects order lines by comparing inventory quantities (open received but uninvoiced inventory quantity against the line's inventory quantity) and prices per inventory unit (R839).
Source: ADR-0056.R19

### The agent contract

R857. Agents and screens read units through one query and one function. `GetItemUnits` (item), a computed query like `GetPrice`, returns every allowed unit of the item. Each unit comes with its code, name, kind and decimal places; its factor to the inventory unit with source and row; `is_exact` and `factor_source`; its flags (counting, default pick, product purchase or sales default, the `contains` relation); its barcodes; and `is_active`. It lists the inventory unit, the item's and the product's rows, and the core units of the inventory unit's kind that convert through the catalog. `GetItemUnits` is on the leaf `product` at `read`.
Source: ADR-0056.R20

R858. The unit commands are `master_data_change` and change-tracked (ADR-0038.R3). `CreateProductUom`, `UpdateProductUom` (flags; retirement; or retirement with a replacement row for the same unit, which end-dates the unit's open price entries; a used factor never changes, ADR-0056.R5), `CreateUom` and `UpdateUom` (company units) sit on the leaf `product_unit`; `CreateUomAlias` and `UpdateUomAlias` sit on the leaf `uom_alias` below it; both are under `product` in Master data, and each command needs `edit`. The templates `purchasing_manager`, `chief_accountant` and `warehouse_keeper` hold `product_unit` at `edit`, and with it `uom_alias`; `accountant` holds `uom_alias` alone (ADR-0054.R11). A change proposal for these commands, such as an agent's `CreateUomAlias`, is approved with `ApproveChangeProposal` by a member of the `general` pool's stage who also holds the target command (ADR-0043.R12; ADR-0055.R7): the purchasing manager, the chief accountant or the owner.
Source: ADR-0056.R20, ADR-0056.R20.N1

R859. Errors of the unit rules:
- `uom_not_allowed` for any line, price entry, supplier order unit or default whose unit has no path to the inventory unit by ADR-0056.R6 (not only in `find_price`);
- `uom_retired`; `uom_kind_mismatch` (a unit field that requires a kind gets another: dimensions length, weights mass, activity time, container volume and weight);
- `serial_unit_not_exact`; `uom_conversion_conflict`; `uom_packaging_inconsistent`; `uom_conversion_in_use`; `price_entry_starts_today`;
- `quantity_rounds_to_zero` stays an error.
Source: ADR-0056.R20

R860. Check results of the unit rules: `quantity_rounded`, `unit_inexact`, `unit_text_unresolved`, `product_uom_replaced`, `uom_factor_changed`, `part_quantity_recomputed`, `part_quantity_clamped`, `gr_ir_rounding_cleared`, `gr_ir_rounding_clearing_reversed`, `unit_name_too_long`, `unit_step_below_inventory_step`.
Source: ADR-0056.R20

R861. The database holds:
- positive factors;
- the line unit block present, with a known source, the identity rule and the gross-error bound (R815), and generated backflush lines in the identity;
- a product unit never the inventory unit, and an item row only for an item of its product;
- at most one active row per (product, item, unit);
- the canonical direction of global pairs;
- the packaging shape; retirement consistency and at most one default pick unit;
- unique normalized aliases.
Source: ADR-0056.R20

R862. Everything else is command-level with invariants (ADR-0056.R25): that a line's snapshot is the right one, that a line names no retired or superseded row, exactness, packaging consistency, exact units for serials, catalog rows at the catalog's factor, and immutability once used. The database cannot hold these without reading other rows.
Source: ADR-0056.R20

### Phase 1 scope and seams

R863. In Phase 1:
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
Source: ADR-0056.R22

R864. After Phase 1, each with its own ADR:
- catch weight (a second quantity per movement, valuation in the unit the supplier invoices, nominal factor tolerances) together with the order price unit;
- batch-specific factors (an actual factor per lot);
- cut-to-length remnants and cutting optimization;
- quantity per handling unit type, and packaging dimensions and weights;
- sales minimums, multiples and delivery rounding;
- quantity-based taxes and the customs unit (R866);
- EDI unit mappings and GS1 hierarchy export.
Source: ADR-0056.R22

R865. Phase 1 workaround for goods bought or sold by weight or length that vary per piece: make the weight (or length) the inventory unit and the piece a product unit with `factor_source` `nominal`. Lines in pieces then return `unit_inexact` with reason `nominal`. Receipts record the actual weight in kg (R834), so stock, cost and GR/IR are right, and piece counts are approximate. An item-level row (ADR-0056.R4) gives a configured item bought by length its own exact factor.
Source: ADR-0056.R22

R866. Quantity-based taxes (per litre or kg) and the statistical unit of a customs declaration are after Phase 1. They will convert through `convert_quantity` to the unit the package names, and they stay in the package (ADR-0041; ADR-0053).
Source: ADR-0056.R23

R867. Container units: `supplier_purchasing_term.volume_uom_id` and `weight_uom_id` stay as interim columns. Item dimensions and weights convert to them through `uom_conversion` only, so a company unit cannot be a container unit (ADR-0024.R2).
Source: ADR-0056.R23

## Invariants

Statements are those of `invariants.csv`; this chunk holds the rows whose catalog source is a rule of this chunk.

| Invariant | Name | Check point | Statement | Protects |
| --- | --- | --- | --- | --- |
| `INV-601` | `cumulative_parts_sum` | day | For every posted source line (for invoices, the order line), each forward part in its unit posted round((C + q) × f) − P at its snapshot, positive and clamped to between q × f − 1 and q × f + 1 inventory units (a value of zero or less is rejected), with C and P the actual net sums of the earlier posted parts in that unit; each return, credit or reversal of a part in the part's unit mirrors the part or takes its cumulative share of the part's stored inventory quantity, never exceeding it; a money-side return naming a stock return line in its unit and entered quantity posted that line's inventory quantity; T(S) grew only by rounded parts in other units and by the changes returns, credits, reversals and clamps made to the deviation; and when C reaches the source's entered quantity, P is within T(S) of its inventory quantity, and equal to it when T(S) is zero. Area `documents`. | R819-R826 |

Named by rules of this chunk, with rows in other chunks or modules: `INV-600` (R832), `INV-92` (R828).

## Edge cases

| ID | Case | Outcome | Rule |
| --- | --- | --- | --- |
| `EC-101` | `carton_received_in_pieces`: An order of 10 cartons of 24 is received as 100 and 140 pieces and invoiced as 10 cartons; the order line is fulfilled and GR/IR is zero. | `must_succeed` | R809, R834 |
| `EC-102` | `bag_partial_receipts`: An order of 3 bags of 7/3 kg is received in three receipts of 1 bag: 2.333, 2.334 and 2.333 kg, summing to the ordered 7.000 kg; the invoice of 3 bags leaves GR/IR at zero. | `must_succeed` | R819 |
| `EC-106` | `e_invoice_unknown_unit_text`: A supplier e-invoice writes a unit text the company has never seen; the agent leaves the line unresolved with `unit_text_unresolved` and proposes an alias, which a person approves before the line is drafted. | `must_succeed` | R855, ADR-0051.R21 |
| `EC-107` | `invoice_per_kg_against_bags`: Goods ordered and received in bags of 7/3 kg are invoiced per kg; quantity and price are matched per inventory unit. | `must_succeed` | R834, R839 |
| `EC-130` | `return_of_inexact_part`: Of three receipts of one bag of 7/3 kg (2.333, 2.334, 2.333 kg) invoiced as 3 bags (7.000 kg), the second is returned and posts its own 2.334; the supplier's credit of 1 bag names that return line and posts the same 2.334, so R = I = 4.666 and GR/IR stays zero; a replacement receipt of one bag posts 2.334. On the sales side the same return and credit leave invoiced net equal to delivered net, and `sales_return_due` closes. | `must_succeed` | R822, R824 |
| `EC-131` | `deliveries_within_rounding_tolerance`: 8.000 kg ordered and delivered as three bags of 8/3 kg, each converting on its own to 2.667 kg: the third delivery (8.001 kg in total) is accepted within the unit rounding tolerance of 0.003 kg and fulfils the line. | `must_succeed` | R826, R827 |
| `EC-320` | `count_summed_counting_units`: One count key entered in three lines in cartons and pieces: the lines sum in the inventory unit and one difference posts. | `must_succeed` | R844, ADR-0075.R3 |

## Settings

No setting row stands in this chunk: `documents.unit_name_max_length` (R852) and `documents.unit_name_source` (R851) have
their rows in chunk 7.

Named by rules of this chunk but absent from `settings.csv`: `inventory.purchase_receipt_tolerance_percent` (R835) and
`purchasing.match.price_tolerance_amount` (R839).

Read, area `inventory`: `costing.exchange_rate_difference_to_stock` (R831, ADR-0047.R13.N4).

## Conflicts

CONFLICT ADR-0056.R10: the clearing's company-currency residual goes to realized exchange difference only on a line without stock; on a line for an item kept in stock the later notes ADR-0047.R13.N3 and ADR-0047.R13.N4 govern through the setting `costing.exchange_rate_difference_to_stock` (R831).
CONFLICT ADR-0056.R13: the GS1 variable-measure scan proposes the AI's unit and quantity instead of the barcode's unit, by the later note ADR-0056.R13.N1; R840 and R841 state it.
CONFLICT ADR-0056.R13.N1: this note supersedes the barcode branch of the proposed-unit order for variable-measure AIs; stated in R841 and named in R840.
CONFLICT ADR-0056.R20: the unit commands moved from the leaf product to the leaves product_unit and uom_alias by note ADR-0056.R20.N1; R858 states the new leaves, GetItemUnits stays on product.
CONFLICT ADR-0056.R18: the statutory unit name source became the regime setting documents.unit_name_source under the later accepted ADR-0063.R23; R851 states its default and the alternative.

## Trace

| Source | Where |
| --- | --- |
| ADR-0056.R7 | R801-R803 |
| ADR-0056.R8 | R804-R808 |
| ADR-0056.R9 | R809-R816 |
| ADR-0056.R10 | R817-R833 |
| ADR-0056.R10.N1 | R823 |
| ADR-0056.R11 | R834-R837 |
| ADR-0056.R12 | R838, R839 |
| ADR-0056.R13 | R840, R841 |
| ADR-0056.R13.N1 | R841 |
| ADR-0056.R15 | R842-R846 |
| ADR-0056.R16 | R847-R849 |
| ADR-0056.R18 | R850-R852 |
| ADR-0056.R19 | R853-R856 |
| ADR-0056.R20 | R857-R862 |
| ADR-0056.R20.N1 | R858 |
| ADR-0056.R21 | ref: ADR-0056.R21 |
| ADR-0056.R22 | R863-R865 |
| ADR-0056.R23 | R866, R867 |
