Module: purchasing    Chunk: 2 of 3    Source ADRs: ADR-0047
Build step(s): 3, 5, 7    Generated from index: 30d5706    Compiled by: Claude Fable 5.2, 2026-11-21

# `purchasing` compiled spec, chunk 2: purchase invoice, GR/IR positions, invoice match, supplier corrections, pricing, limits, postings, policy input

## Purpose

This chunk states the part of `purchasing` law on: the `purchase_invoice`, GR/IR by unit positions per purchase order line, the invoice match, purchase returns and supplier credit and debit notes, the pricing procedure `purchasing.contract.price_line`, supply rows, cumulative limits, postings by transaction key and the policy input. `purchasing` owns the supplier documents; `inventory` owns the stock documents, the GR/IR layer table and the GR/IR interfaces, which `purchasing` calls downward. Rules that are co-primary with `sales` or `inventory` are stated here in full. Document types, copy, orders, requests, service receipts, agents and the auto-post gateway are in the other chunks.

## Entities and tables

DDL: `docs/design/DS-22-09-42-commercial-inventory.sql`.

| Table | Meaning | Key | Parent | Owner |
| --- | --- | --- | --- | --- |
| `purchase_invoice` | Header of a supplier invoice (R201, R202) | `id`; (`company_id`, `id`) | `document` | `purchasing` |
| `purchase_invoice_line` | Line of kind `goods`, `service`, `expense` or `landed_cost` (R203) | `id`; (`purchase_invoice_id`, `line_number`) unique | `purchase_invoice` | `purchasing` |
| `purchase_return` | The supplier's adjustment for returned goods (R224) | `id`; (`company_id`, `id`) | `document` | `purchasing` |
| `purchase_return_line` | Line naming a `return_to_supplier` line and the invoice line it corrects (R224) | `id`; (`purchase_return_id`, `line_number`) unique | `purchase_return` | `purchasing` |
| `purchase_credit_note` | The supplier's credit for anything but returned goods (R225) | `id`; (`company_id`, `id`) | `document` | `purchasing` |
| `purchase_credit_note_line` | Quantity or price credit line, `credit_kind` `quantity` or `price` (R225) | `id`; (`purchase_credit_note_id`, `line_number`) unique | `purchase_credit_note` | `purchasing` |
| `purchase_debit_note` | The supplier's increase, price-only (R225) | `id`; (`company_id`, `id`) | `document` | `purchasing` |
| `purchase_debit_note_line` | Price line on a purchase invoice line (R225) | `id`; (`purchase_debit_note_id`, `line_number`) unique | `purchase_debit_note` | `purchasing` |
| `gr_ir_write_off` | Write-off of a GR/IR balance on a closed line with `R > I` (R216) | `id`; (`company_id`, `id`) | `document` | `purchasing` |
| `gr_ir_write_off_line` | One purchase order line written off: `purchase_order_line_id`, `inventory_quantity`, `line_amount` (R216) | `id`; (`gr_ir_write_off_id`, `line_number`) unique | `gr_ir_write_off` | `purchasing` |

Named by rules of this chunk, with their rows in other chunks: `purchase_order`, `purchase_order_line`, `purchase_request`, `purchase_request_line`, `service_receipt`, `service_receipt_line`.

Reads: `purchase_order_line_gr_ir_layer`, `return_to_supplier`, `return_to_supplier_line`, `goods_receipt_line`, `landed_cost`, `landed_cost_line` (`inventory`); `document`, `document_line_price_step` (`documents`); `derivation_trace`, `payment_term`, `account` (`ledger`); `partner`, `item`, `uom` (`master_data`); `sales_return`, `sales_order_line` (`sales`).

## Commands and queries

The sources name document verbs, not command names. Authorization areas are the document types of `authorization-areas.csv` under the area `purchasing`: `purchase_invoice`, `purchase_return`, `purchase_credit_note`, `purchase_debit_note`, `gr_ir_write_off` and `gr_ir_rounding_clearing` (posted only by the system as a consequence posting, `is_internal_only`, level `full`, in no template's expansion). The level of a verb is the catalog's (`Create`, `Update`, `Submit`: `edit`; `Post`, `Issue`: `post`; `Reverse`: `full`).

| Name | Actor and authorization | Input | Effect | Events | Error codes |
| --- | --- | --- | --- | --- | --- |
| `Create`, `Update` of a priced document | area of the document type, `edit` | header and lines | Prices each line (R226) and runs the pricing checks (R227) | not stated | `price_list_currency_mismatch`, `tax_inclusive_multiple_codes` |
| `Submit` of `purchase_invoice` | area `purchase_invoice`, `edit` | the draft invoice | Computes the match per goods line (R219-R221); sends the draft to policy | not stated | check results `match_quantity_exceeded`, `match_price_difference`, `invoice_before_receipt` |
| `Post` of `purchase_invoice` | area `purchase_invoice`, `post` | the invoice | Computes the match again and posts by R204 and R233 | not stated | check results as for `Submit` |
| `Post` of `purchase_return`, `purchase_credit_note`, `purchase_debit_note` | `human_only` (ADR-0047.R1); area of the document type, `post` | the correction document | Posts by R224, R225 and R233, within the limits of R232 | not stated | not stated |
| `Post` of `gr_ir_write_off` | `human_only`; area `gr_ir_write_off`, `post` | closed order lines with `R > I` | Moves `I` up to `R` and posts by R216 | not stated | not stated |
| `Reverse` of a document with GR/IR postings | area of the document type, `full` | the document | Mirrors its GR/IR postings while they are the latest of their side (R209) | not stated | `reversal_not_latest` |

Contract functions, not registered commands: `purchasing.contract.price_line` (R226); `inventory`'s `inventory.contract.set_order_line_gr_ir_price`, `inventory.contract.post_gr_ir_positions` (R213) and `inventory.contract.adjust_receipt_value` (R214, R218, R233); `tax.contract.compute_taxes` (R227). The client action `reprice` is named by R229 without a registration.

Consumer, not a command: the `purchasing` consumer that raises `supplier_credit_due` (R224).

Error codes bound to no named command: `duplicate_external_document` (R202), `purchase_order_required` (R203), `price_required` (R226), `correction_exceeds_original` (R232).

## Rules

### Purchase invoice

R201. The `purchase_invoice` header holds the supplier (`partner_id`, the ordered-from party), `partner_reference` (the supplier's invoice number; required), `supplier_invoice_date` (the tax date, ADR-0041.R7), the posting date (DS-19's default), the currency and the invoice rate (ADR-0011.R12; the DDL column `invoice_rate`, marked interim there because ADR-0047 does not name it) and the payment term. It may also name the parties `invoicing_party` and `payee` (ADR-0074.R1, ADR-0074.R2).
Source: ADR-0047.R12

R202. Duplicates. Where the regime declares a natural key for supplier invoices (ADR-0030.R10), it applies; its key fields are content of the localization package (the DDL column `external_document_key`, marked interim). Otherwise the fallback key is the invoicing party (else the ordered-from supplier, ADR-0074.R4), `partner_reference` and the year of the supplier's date (flagged). Documents that are canceled or reversed do not count. A second arrival is rejected with `duplicate_external_document`.
Source: ADR-0047.R12

R203. Line kinds of `purchase_invoice_line` (`line_kind`):
- `goods`: refers to a purchase order line. A stock item without an order is rejected with `purchase_order_required`; the buyer creates the order first, so GR/IR stays uniform.
- `service`: an order line is optional. With a `service_receipt`, it clears GR/IR like goods (ADR-0037.R6); without one, it posts to expense.
- `expense`: no order; the account comes from account determination for the item, or is entered.
- `landed_cost`: freight, insurance or handling. It posts to `purchase_cost_clearing` and proposes a landed cost (ADR-0021.R12); it never touches GR/IR.
Source: ADR-0047.R12

R204. Taxes and posting of a purchase invoice. Each line carries the supplier's stated tax (ADR-0041.R10) and `input_use`. The invoice posts the GR/IR debit by R208, the price difference as the regime sends it (ADR-0030.R4), input tax, and one payable control line per installment. The payable control line, its open item and the input tax identity are the invoicing party's, else the ordered-from supplier's; GR/IR and the match stay with the ordered-from supplier (ADR-0074.R4).
Source: ADR-0047.R12

R205. For a purchase invoice, the policy input `is_direct_expense` is true when no line references a purchase order line and every line is an `expense` or `service` line; it selects the `expense` approval pool (ADR-0055.R3).
Source: ADR-0047.R12, .N1

R206. `expense` lines, and `service` lines without a service receipt, post to the transaction key `purchase_expense` (determinant: item group; required system accounts `expense`, `prepaid_expense` and `construction_in_progress`). A line without an item, or one whose account is entered, takes the entered account, which the command checks against the key (ADR-0015.R4, ADR-0015.R12). The determination row for the key is content of the localization package; the TT99 template's row is `unverified` (DS-19).
Source: ADR-0047.R12, .N2

### GR/IR per purchase order line, by unit positions

These rules detail ADR-0030.R4.

R207. Positions. The line's units, in its inventory unit, are positions in order; positions count inventory quantities. `R` is the received quantity net of returns, `I` the invoiced quantity net of quantity credits. When a receipt or an invoice first reaches a position, the position is priced at the line's GR/IR price then in force (ADR-0047.R10). It keeps that price for the life of the line. Prices are stored as layers (from, to, price), exact rationals, in `purchase_order_line_gr_ir_layer`. `V(x)` is the exact value of positions 0 to `x`. An invoice's source is always the order line; a receipt or invoice entered in the order line's unit takes its inventory quantity by the cumulative rule; a return or credit takes the part it names as its source, and a purchase return naming a return-to-supplier line in the same unit and entered quantity takes that line's inventory quantity, so `R` and `I` move together.
Source: ADR-0047.R13, .N1

R208. GR/IR postings are differences of rounded cumulative values, in the order's currency:
- a receipt of `q` credits GR/IR with `round(V(R + q)) − round(V(R))`;
- an invoice of `q` debits it with `round(V(I + q)) − round(V(I))`; the invoice amount less that is the price difference;
- a return of `q` debits it with `round(V(R)) − round(V(R − q))`, the latest received positions;
- a quantity credit of `q` credits it with `round(V(I)) − round(V(I − q))`.
Rounding is to the currency's minor unit. The balance of the line is therefore always `round(V(I)) − round(V(R))`, and zero whenever `R = I` (`INV-37`, `INV-92`). The latest-positions rule prices a return and a quantity credit, also after a change order, and replaces the return and credit note prices of ADR-0030.R4; only it keeps `INV-37` exact.
Source: ADR-0047.R13

R209. Reversals. A document's postings on a line may be reversed only while they are the latest unreversed postings of their side (receipts and returns on `R`; invoices and quantity credits on `I`). The reversal mirrors them exactly. Otherwise `Reverse` is rejected with `reversal_not_latest`, and the correction is a return or a credit. This adds a precondition to ADR-0009.R18 and ADR-0009.R19 for goods receipts, service receipts, stock returns and supplier documents with order lines.
Source: ADR-0047.R13

R210. Price-only documents. Supplier credit and debit notes without quantity, and price corrections, never touch GR/IR. Their amount is a price difference and goes as the regime sends `price_difference`.
Source: ADR-0047.R13

R211. Consequences of the positions. A return names the receipt lines it returns, but GR/IR moves at the latest positions' value. Stock leaves at the value the regime sets for `purchase_return` (ADR-0020.R5). Any difference between that and the GR/IR debit is a price difference, posted on the return. A replacement receipt after a full return posts at the positions' first price. Each receipt line stores its position range, which defines the "matched receipt lines" of ADR-0030.R1.
Source: ADR-0047.R13

R212. The position range a return stores. `return_to_supplier_line.gr_ir_position_from` and `gr_ir_position_to` hold the positions the return actually debits: the order line's latest received positions, from `R − q` to `R`, where `R` is the received net before the return and `q` the return line's inventory quantity. They are in general not the positions of the receipt it names. The named receipt line, `goods_receipt_line_id`, is stored separately: it is the part reference whose inventory quantity the return mirrors or shares (ADR-0056.R10, part as source) and the receipt line the return names under R211. With one GR/IR price on the line both ranges have the same value; after a change order they differ, and the stored range is the one that keeps `INV-37`. Under the interim seed of `purchase_return`, stock leaves at that debit, so the return posts no price difference (ADR-0020.R5 note). DS-22-09-42 states it on the columns.
Source: ADR-0047.R13, .N2

R213. Ownership. The layer table, each receipt line's position range, and the interfaces `inventory.contract.set_order_line_gr_ir_price` and `inventory.contract.post_gr_ir_positions` (side, quantity, sign; returning the amount) are `inventory`'s. `purchasing` calls them downward, under the order's document lock (ADR-0027.R10, class 1). They belong to the step 3 design (DS-09) and stay empty until step 5 (B3).
Source: ADR-0047.R13

R214. Foreign currency. `INV-37` holds in the order's currency. The company-currency residual of a line from different receipt and invoice rates is measured on the posting that makes `R = I`, and that posting clears it (interim, until the step that builds it):
- On a line without stock (services, expenses) the residual is cleared to realized exchange difference (`fx_gain_realized`, `fx_loss_realized`); interim, flagged.
- On a line for an item kept in stock (its receipts post material document lines) the company setting `costing.exchange_rate_difference_to_stock` (area `inventory`, regime and company option, boolean, core default true, changed only from a period start, in the shape of ADR-0063.R24) chooses the treatment. The clearing posting reads the value in force on its posting date.
- True, the default: the residual is its own difference kind. The posting that clears it debits or credits `purchase_cost_clearing` (the interim key, as for price differences sent to stock) and calls `inventory.contract.adjust_receipt_value`, which writes a `landed_cost` with `cost_type` `exchange_rate_difference` targeting the line's receipt lines, allocated by value: a `receipt_addition` in that posting's period (notes of ADR-0021.R6 and ADR-0021.R12; note of ADR-0020.R12).
- False: the residual posts as on a line without stock, to `fx_gain_realized` or `fx_loss_realized`, and stays out of the item's actual cost. The false path is interim, confirmed with the purchase invoice step (step 5). A regime package that opens false records it as a flagged value.
- Treating every rate difference as a price difference through an assumed rate is not offered.
Source: ADR-0047.R13, .N3, .N4

R215. Still to design at the purchase invoice step (DS-22, step 5) for the exchange-rate difference of R214: measuring it per invoice posting, not at `R = I` (the GR/IR positions would then keep the receipt's company-currency amount); confirming the key (`purchase_cost_clearing`, or a transaction key of its own); the `cost_type` value in the `landed_cost_line` DDL and its CHECK; the invoice-first case, where the receipt's rate comes after the invoice's; and returned or written-off quantities.
Source: ADR-0047.R13.N3

R216. Lines closed short with `R ≠ I`. Closing stops receipts, not invoices. A balance left on a closed line is listed by a close checklist task (DS-12) and cleared through the positions, so `INV-92` keeps holding: `I > R` by a supplier quantity credit (R225); `R > I`, when the supplier will never invoice, by a `gr_ir_write_off` (`purchasing`, internal posting, `human_only`). That document moves `I` up to `R` at the positions' value, debiting GR/IR, and credits the regime's price difference (flagged for the author).
Source: ADR-0047.R13

R217. The consequence posting `gr_ir_rounding_clearing`. When the line is fulfilled within the unit rounding tolerance and `R` and `I` still differ, it posts on the lagging side at the positions' value, against `price_difference`, with no human step. It also runs on a closed line whose `R` and `I` differ by no more than the tolerance; a larger difference stays on the closed-short path of R216 (ADR-0056.R10). Its positions count in `R` or `I` for GR/IR, so `INV-92` holds with them. It is the posting that makes `R = I` for R214, and reversing it reverses that entry. It never counts as latest in the latest-only check of R209. Every later GR/IR posting on the line, a `gr_ir_write_off` included, first reverses it as a consequence, after which it fires again if the line is within tolerance.
Source: ADR-0047.R13.N1

R218. Planned delivery costs (interim; details at the purchase invoice step, DS-22, step 5):
- A purchase order line may carry planned delivery cost conditions: a cost type (the `cost_type` values of ADR-0021.R1), an amount for the line, an amount per inventory unit or a percentage of the line's net value, and the freight supplier who will invoice it (the order's supplier when empty).
- A goods receipt of `q` units adds each condition's planned amount for those units to the receipt line's value, debiting the inventory key with the goods and crediting a delivery-cost clearing key per condition. The amount is a difference of rounded cumulative values over the line's positions, as in R208, so a fully received line accrues exactly the planned amount, and a return reverses the accrual at the latest positions.
- The freight supplier's invoice line names the condition and debits the clearing with the accrued amount for the quantity it invoices. The difference between invoiced and accrued is a price difference, handled like the purchase price difference: as the regime determines `price_difference`, to an account, or to stock through `inventory.contract.adjust_receipt_value` in the invoice's posting period (notes of ADR-0021.R6 and ADR-0021.R12).
- Costs with no condition stay the unplanned path of ADR-0021 (`landed_cost`), with the treatment of the ADR-0021.R12 note.
- No DDL, transaction key or system account exists for this yet; step 5 builds the planned delivery costs entry under "S2 closure (2026-11-21)" in `docs/open-questions.md`.
Source: ADR-0047.R13.N4

### Invoice match

R219. The match is computed for each `goods` line at the invoice's `Submit` and `Post`:
- Quantity: invoiced net may not exceed the ordered quantity times `1 + purchasing.match.quantity_tolerance_percent / 100`; when `purchasing.match.require_receipt` is true, it may not exceed received net either. Otherwise the check result is `match_quantity_exceeded`.
- Price: the invoice price may differ from the order price by at most the larger of `purchasing.match.price_tolerance_percent` of it and `purchasing.match.price_tolerance_amount`. Otherwise `match_price_difference`.
- The order price of the price check is the GR/IR value per unit of the positions the invoice reaches, `(V(I + q) − V(I)) / q`, exact, for an invoice of `q` inventory units at the line's layers (R207). It is compared with the invoice line's net amount after the document discount per inventory unit. With one order price this is the GR/IR price of ADR-0047.R10; after a change order it is the price of the very positions the invoice debits, so the tolerance check and the posted price difference agree.
- The price check is per inventory unit, whatever unit the invoice line is in; `purchasing.match.price_tolerance_amount` is an amount per inventory unit, in the document currency (ADR-0056.R12).
Source: ADR-0047.R14, .N1, .N2

R220. Invoice before receipt is legitimate by default (ADR-0030.R4) and informs with `invoice_before_receipt`. The `purchasing.match.*` settings are company settings, defaulting to 0 and false, flagged.
Source: ADR-0047.R14

R221. Match policy. A difference sets the condition `is_match_exceeded` (ADR-0043.R3), which is part of the invoice's `policy_input` and so of `policy_input_hash`. The seeded rule requires `standard` approval for both `submit` and `post` of a purchase invoice, for every actor kind, when it is true. A mismatched invoice therefore cannot pass by submitting first.
Source: ADR-0047.R14

R222. The purchase invoice checker of the auto-post gateway reads these facts: a line within `auto_post.purchase_invoice.price_tolerance_percent` of the GR/IR price of the positions it reaches, and within `auto_post.purchase_invoice.quantity_tolerance_percent` of the received net (both default 0), is `cross_checked`; any check result of R219 or R220, or `is_match_exceeded`, keeps the invoice for a person (ADR-0065.R19).
Source: ADR-0047.R14.N3

### Purchase returns and supplier corrections

R223. The goods of a purchase return. `return_to_supplier` (`inventory`; `correction_of_id`: the goods receipt) issues them with movement `purchase_return`, debiting GR/IR by R208. `inventory` checks returned ≤ received per receipt line.
Source: ADR-0047.R15

R224. The money of a purchase return. `purchase_return` records the supplier's adjustment for returned goods: `correction_of_id` is the purchase invoice, and lines refer to `return_to_supplier` lines. It credits GR/IR by R208 as a quantity credit. Its lines carry the line unit block. A purchase return line that names a return-to-supplier line in the same unit and for the same entered quantity takes that line's inventory quantity, so the stock return and the supplier's credit move `R` and `I` by the same amount (ADR-0056.R9, ADR-0056.R10). A `purchasing` consumer raises a work item `supplier_credit_due` when a stock return leaves invoiced net above received net on an order line.
Source: ADR-0047.R15, .N1

R225. Other supplier credits. `purchase_credit_note` (`correction_of_id`: the purchase invoice) records the supplier's credit for anything but returned goods. Its quantity lines (goods invoiced but never delivered, or an invoicing error) are quantity credits on `I` by R208, within the invoice line's invoiced net (R232). Its price lines are price-only. Its lines carry the line unit block and `item_id` (`credit_kind` `quantity` or `price`, a DDL column marked interim because ADR-0047 does not name it; the unit block and `item_id` are filled on quantity lines). `purchase_debit_note` records the supplier's increase, price-only.
Source: ADR-0047.R15, .N1

### Pricing

R226. The pricing procedure is `sales.contract.price_line` and `purchasing.contract.price_line`. Each is a pure function of the header (list, currency, document date, partner) and the line (item or configuration values, unit, quantity, manual price, manual discount), in these steps:
- List price: `find_price` (ADR-0045.R4, ADR-0046.R15). The list's currency must equal the document's (`price_list_currency_mismatch`, ADR-0045.R5).
- Base price: the manual price if one is entered (`is_price_manual`), else the list price. A line with neither may not leave draft (`price_required`) unless it is free of charge (ADR-0047.R17).
- Promotion (sales only): the one eligible promotion of ADR-0047.R17.
- Manual discount: a percentage.
- Net unit price: the base price after the promotion and then the manual discount, rounded half up to the unit-price scale (ADR-0006) and stored.
- Line amount: `round_amount(quantity × stored net unit price)` (ADR-0006.R18), so the stored values reproduce it.
- Document discount: a percentage on the header. Its total, `round_amount(Σ line amounts × percentage)`, is allocated to the paid lines in proportion to their amounts, by largest remainder in minor units, with ties to the earlier line. A zero total allocates nothing. Each document that bills or credits lines (an invoice, a credit) applies the percentage to its own lines in the same way. Discount amounts are entered per line, as manual discounts.
Source: ADR-0047.R16

R227. Pricing checks at `Create` and `Update`: `price_list_currency_mismatch`, and `tax_inclusive_multiple_codes` for a tax-inclusive list where more than one percent code applies (ADR-0041.R9, ADR-0045.R5). Taxes are computed by `tax.contract.compute_taxes` on the net amounts after the document discount, with `prices_include_tax` from the list (ADR-0045.R5).
Source: ADR-0047.R16

R228. The price trace. Each step is a `document_line_price_step` row (step, source table and row, value) in the line's content. It is in the plan and the version hash, and it reproduces the stored net unit price and the line amount (`INV-93`). Interim, with the open question on trace scope: pricing writes no `derivation_trace` rows; the steps on the line serve Principle 6.
Source: ADR-0047.R16

R229. Re-pricing. A draft line is priced again whenever its item, configuration, unit, quantity or the document date changes, unless its price is manual. A line copied with its price (ADR-0047.R2, ADR-0047.R3) is marked `is_price_copied` and keeps the source line's price steps; like a manual price, it is not re-priced when its quantity or the document date changes. A change of its item, configuration or unit, or the client's `reprice`, prices it anew and clears the mark.
Source: ADR-0047.R16, .N1

### Demand and supply rows

R230. Demand and supply rows (ADR-0024.R8, ADR-0031.R5). Sales order lines get demand rows at Submit; take-force adjusts them; close or cancel closes them (`closed_reason`). Purchase request and order lines get supply rows from draft (ADR-0047.R10). A request line's open quantity falls as orders are created from it. Delivered and received quantities are read from the rows. Invoiced quantities, including `issuing`, are computed from invoice lines.
Source: ADR-0047.R19

R231. Release. Demand rows of sales order lines and supply rows of purchase order lines carry the hold reason `not_approved` until the document is approved (ADR-0047.R18 note). Unreleased demand rows are not demand: planning, available to promise and reservations ignore them, and `Reject` sets `not_approved` on them again, so a rejected order is never demand and never reserves. Supply rows from draft stay supply for planning (ADR-0047.R10, ADR-0024.R8), released or not, but goods are received against them only once released.
Source: ADR-0047.R19.N1

### Cumulative limits

R232. Cumulative limits (ADR-0009.R23; `INV-40`, completed here):
- Per delivery or receipt line: returned ≤ delivered or received (checked by `inventory`).
- Per invoice line: quantity credited (by `sales_return`, `purchase_return` or a quantity credit) ≤ invoiced; amount credited ≤ the line's net amount less earlier credits.
- Per order line: delivered or received net ≤ ordered (with the receipt tolerance); for stock sales order lines, invoiced net ≤ delivered net, except while a `sales_return_due` work item is open; for purchase order lines, invoiced net may exceed received net (invoice before receipt, R220, unless `purchasing.match.require_receipt`), and a stock return that leaves it above raises `supplier_credit_due` (R224); the quantity credited by returns ≤ the returned quantity not yet credited.
- Violations are rejected with `correction_exceeds_original`. Documents in `issuing` count.
- `EC-20`: when a return makes invoiced net exceed delivered net on an order line, a `sales_return` for the difference, the invoiced share, is due and a sales return work item is raised (ADR-0047.R7). Returned goods that were never invoiced simply reduce what remains to invoice.
- Every limit compares inventory quantities and allows the unit rounding tolerance of the source line. The tolerance grows by one smallest inventory step per part posted in another unit whose conversion rounded, and by the change each return, credit, reversal or clamped part made to the deviation `P − round(C × f)`; it never shrinks, and with an exact snapshot it stays zero, so every limit is exact (ADR-0056.R10).
Source: ADR-0047.R20, .N1, ADR-0047.R22.N4

### Postings

R233. Postings by transaction key (ADR-0015), given as document: debit; credit.
- Delivery: `cost_of_goods_sold` (free goods: `free_goods_cost`); inventory.
- Return from customer: inventory; `cost_of_goods_sold` (regime value).
- Sales invoice: `receivable_reconciliation` per installment; `revenue_posting`, `output_tax`, discounts by ADR-0047.R6.
- Sales return: `revenue_deduction_return`, `output_tax`; `receivable_reconciliation` (credit item).
- Credit note: by reason (ADR-0047.R8), `output_tax`; `receivable_reconciliation` (credit item).
- Debit note: `receivable_reconciliation`; `revenue_posting`, `output_tax`.
- Goods receipt: inventory; `gr_ir_clearing` (R208).
- Purchase invoice, goods: `gr_ir_clearing` (R208), price difference (`price_difference` or `purchase_cost_clearing`), `input_tax`; `payable_reconciliation` per installment.
- Purchase invoice, service with a service receipt: `gr_ir_clearing`, price difference (ADR-0037.R6), `input_tax`; `payable_reconciliation`.
- Purchase invoice, service without one, or expense: expense by determination, `input_tax`; `payable_reconciliation`.
- Purchase invoice, landed cost: debit `input_tax` and, as the setting `landed_cost.unplanned_cost_treatment` chooses (ADR-0021.R12.N2), `purchase_cost_clearing` under `distribute_to_items` (the default) or the account determined by `purchase_expense` under `separate_account` (interim until step 5; never stock); credit `payable_reconciliation`.
- Return to supplier: `gr_ir_clearing` (R208), price difference if the regime's stock value differs; inventory.
- Purchase return: `payable_reconciliation`; `gr_ir_clearing` (R208), price difference, `input_tax`.
- Supplier credit note: `payable_reconciliation`; `gr_ir_clearing` for quantity lines (R208), price difference for price lines, `input_tax`.
- Supplier debit note: price difference, `input_tax`; `payable_reconciliation`.
- GR/IR write-off (closed line, `R > I`): `gr_ir_clearing` (R208); price difference.
- Release at order close (invoice-first): `purchase_cost_clearing`; `price_difference` (ADR-0030.R4).
- `gr_ir_rounding_clearing` posts GR/IR against `price_difference` at the positions' value, as a consequence posting (ADR-0056.R10).
- A goods line with a price difference: GR/IR is debited by R208 and the rest is the price difference. Where the regime sends `price_difference` to an inventory account, the invoice posts the difference to `purchase_cost_clearing` (ADR-0021.R12) and, in the same transaction, `inventory.contract.adjust_receipt_value` writes a `landed_cost` with `cost_type` `price_difference`, `posted`, targeting the receipt line (ADR-0030.R1); with the receipt's period open it debits `inventory_posting` and credits `purchase_cost_clearing`, which returns to zero. For a receipt of an earlier period the difference sent to stock posts as the ADR-0021.R6 note says. Where the regime sends `price_difference` to an expense account, the invoice posts the difference there, with no landed cost. The accounts of the TT99 example are `unverified` content of the localization package (DS-19).
Source: ADR-0047.R21, .N1, .N2, .N3

### Policy input

R234. Policy input of each type (ADR-0043.R4):
- Amount: document total in company currency at the applied rate.
- `discount_percent`: (Σ quantity × list price − net amount after the document discount) ÷ Σ quantity × list price. Lines without a list price count at their base price; free goods count at their list price.
- `margin_percent`: (net amount − cost) ÷ net amount, in company currency, with the cost of free goods included. Cost per inventory unit is the preliminary price in the line's valuation area (ADR-0020.R11), or the configuration estimate (ADR-0046.R14). An unknown cost leaves margin unknown, and the decision needs a human.
- `is_price_below_cost`: a paid line's net amount after the document-discount allocation (R226, document discount step), divided by its inventory quantity and converted to company currency at the applied rate, is below its cost per inventory unit; free goods are excluded. This is the one definition; the "net unit price" of ADR-0045.R5 gives way to it. `EC-22` follows the company's policy rules on `is_price_below_cost`.
- `is_price_outside_list`: a line's base price differs from its list price, or it has none.
- `is_credit_exceeded` (sales orders) and `is_match_exceeded` (purchase invoices).
- Fields: cost and margin on documents are field classes `cost` and `margin` (ADR-0017.R10).
- `EC-21` and `EC-63` need approval at Submit, with the other unreleased orders held (ADR-0047.R18).
Source: ADR-0047.R22, .N1, .N4

R235. `is_cost_unknown` is true when a paid line's cost per inventory unit is unknown: no preliminary price and, for a line without an item or preliminary price, no computable configuration estimate (ADR-0046.R14). `margin_percent` is then unknown and the line does not count as below cost, so rules on margin and below cost do not match; the seeded rule on `is_cost_unknown` requires approval (ADR-0043.R3, ADR-0043.R15).
Source: ADR-0047.R22.N2

R236. Quotations have no credit condition. `is_credit_exceeded` belongs to the sales order's policy input only (ADR-0047.R4, ADR-0047.R18): a quotation creates no demand, reservation or exposure (ADR-0047.R3). The quotation agent's `GetCreditExposure` finding is information in its note (ADR-0051.R15 note); credit is checked when the order is submitted.
Source: ADR-0047.R22.N3

## Invariants

Statements are those of `invariants.csv`. Each row stands once in the module.

| Invariant | Name | Check point | Statement | Protects |
| --- | --- | --- | --- | --- |
| `INV-40` | `corrections_within_original` | day | Cumulative corrections never exceed the original: returned per delivery line within delivered, credited quantity per invoice line within invoiced, credited amount within the line's net amount, and the same for purchase lines (ADR-0047.R20). | R232 |
| `INV-90` | `sales_delivered_within_ordered` | day | Per sales order line, delivered net of returns never exceeds the ordered quantity. | R232 |
| `INV-91` | `sales_invoiced_within_delivered` | day | Per stock sales order line, invoiced net of quantity credits never exceeds delivered net of returns, unless an open `sales_return_due` work item names the line. Purchase lines may be invoiced before receipt (ADR-0047.R14). | R232, R220 |
| `INV-92` | `gr_ir_equals_rounded_positions` | day | Per purchase order line, the GR/IR balance in the order's currency equals `round(V(I)) - round(V(R))` at the line's position layers, `V` being the exact value of positions up to a quantity and rounding to the currency's minor unit; it is zero when received net equals invoiced net. | R208, R216, R217 |
| `INV-93` | `price_steps_reproduce_price` | day | Every commercial document line's price steps reproduce its net unit price and its line amount. | R226, R228 |

Named by rules of this chunk, with its row in another chunk: `INV-37` (R208, R212, R214; its catalog source is ADR-0030.R3 and ADR-0030.R5).

## Edge cases

The catalog rows of `EC-20` and `EC-22` still read "Interim, flagged"; ADR-0047.R22.N4 confirms their outcomes, so the mark is not restated (R232, R234).

| Edge case | Name | Case | Outcome | Protects |
| --- | --- | --- | --- | --- |
| `EC-20` | `return_of_partly_invoiced_goods` | A customer returns goods of which only part was invoiced: a sales return for the invoiced share is due; uninvoiced returned goods reduce what remains to invoice. | `must_succeed` | R232 |
| `EC-22` | `price_below_cost` | A sales price below the item's current cost: `is_price_below_cost` feeds the policy; the outcome is the company's rules. | `must_succeed` | R234 |
| `EC-69` | `purchase_price_change_between_receipts` | A change order changes a purchase price between two receipts; the invoice clears GR/IR at each position's first-posted price, and a return after the change takes the latest positions. | `must_succeed` | R207, R208 |
| `EC-70` | `free_goods_with_document_discount` | A sales order with a free goods promotion and a document discount; the discount is allocated to the paid lines by largest remainder and the free line stays at zero. | `must_succeed` | R226 |
| `EC-71` | `purchase_invoice_match_tolerance` | One supplier invoice within the price tolerance posts without approval; another beyond it needs approval through `is_match_exceeded`. | `must_succeed` | R219, R221 |

Named by R234, with their rows in chunk 3: `EC-21`, `EC-63` (their catalog source is ADR-0047.R18 and ADR-0030).

## Settings

The rules of this chunk name `purchasing.match.quantity_tolerance_percent`, `purchasing.match.require_receipt`, `purchasing.match.price_tolerance_percent` and `purchasing.match.price_tolerance_amount` (R219, R220: company settings, defaults 0 and false, flagged; the amount is per inventory unit in the document currency). They have no row in `settings.csv`; chunk 3 lists, once, every key the module names without a row.

Reads: `costing.exchange_rate_difference_to_stock` (`inventory`; boolean, scopes regime and company, core default true, changed only from a period start; R214); `auto_post.purchase_invoice.price_tolerance_percent` and `auto_post.purchase_invoice.quantity_tolerance_percent` (R222; their rows are in chunk 3).

## UI annotations

The sources of this chunk hold no floorplan, facet, field or tile annotation of ADR-0077. Work item kind of `purchasing` raised by its rules (`work-item-kinds.csv`):

| Kind | Subject table | Owner | Due | Resolution | Rule |
| --- | --- | --- | --- | --- | --- |
| `supplier_credit_due` | `purchase_order_line` | `buyer` | `days:5` | `system`: closed when a `purchase_return` records the supplier's credit | R224, R232 |

It is raised when a return to the supplier left an order line's invoiced net above its received net, and it is not agent-resolvable.

## Conflicts

CONFLICT ADR-0047.R12: ADR-0074.R4 governs the parties: the supplier-invoice fallback key, the payable control line, its open item and the input tax identity use the invoicing party, else the ordered-from supplier, and the header may name `invoicing_party` and `payee` (ADR-0074.R2) (R201, R202, R204).
CONFLICT ADR-0047.R13: the foreign currency bullet sent every residual to realized exchange difference and left the rest with the FX open question; ADR-0047.R13.N3 and ADR-0047.R13.N4 govern for stocked lines (R214).
CONFLICT ADR-0047.R13.N3: on a line for an item kept in stock the residual goes to `purchase_cost_clearing` and the receipt value, not to `fx_gain_realized` or `fx_loss_realized`; the company setting of ADR-0047.R13.N4 chooses between them (R214).
CONFLICT ADR-0047.R14: the price check compares the invoice line's net amount after the document discount per inventory unit with the positions' value `(V(I + q) − V(I)) / q`, as ADR-0047.R14.N1 and ADR-0047.R14.N2 say (R219).
CONFLICT ADR-0047.R20: the mark "interim and flagged" on the `EC-20` outcome is dropped, because ADR-0047.R22.N4 confirms the limits as written (R232).
CONFLICT ADR-0047.R21: its row "Purchase invoice, landed cost: debit `purchase_cost_clearing`" holds only under `landed_cost.unplanned_cost_treatment` `distribute_to_items`; ADR-0021.R12.N2 governs, and under `separate_account` the line debits the account determined by `purchase_expense` (R233).
CONFLICT ADR-0047.R21.N3: the closed-period branch of the example in ADR-0047.R21.N1 (method `consumer_split`) no longer applies; ADR-0047.R21.N3 governs and a late price difference posts as the ADR-0021.R6 note says (R233).
CONFLICT ADR-0047.R22: ADR-0047.R22.N4 confirms the policy input as written, so the interim mark of `EC-22` is dropped; ADR-0047.R22.N1 gives the one definition of `is_price_below_cost` (R234).

## Proposed (not law)

None

## Trace

| Source | Where |
| --- | --- |
| ADR-0047.R12 | R201, R202, R203, R204, R205, R206 |
| ADR-0047.R12.N1 | R205 |
| ADR-0047.R12.N2 | R206 |
| ADR-0047.R13 | R207, R208, R209, R210, R211, R212, R213, R214, R216 |
| ADR-0047.R13.N1 | R207, R217 |
| ADR-0047.R13.N2 | R212 |
| ADR-0047.R13.N3 | R214, R215 |
| ADR-0047.R13.N4 | R214, R218 |
| ADR-0047.R14 | R219, R220, R221 |
| ADR-0047.R14.N1 | R219 |
| ADR-0047.R14.N2 | R219 |
| ADR-0047.R14.N3 | R222 |
| ADR-0047.R15 | R223, R224, R225 |
| ADR-0047.R15.N1 | R224, R225 |
| ADR-0047.R16 | R226, R227, R228, R229 |
| ADR-0047.R16.N1 | R229 |
| ADR-0047.R19 | R230 |
| ADR-0047.R19.N1 | R231 |
| ADR-0047.R20 | R232 |
| ADR-0047.R20.N1 | R232 |
| ADR-0047.R21 | R233 |
| ADR-0047.R21.N1 | R233 |
| ADR-0047.R21.N2 | R233 |
| ADR-0047.R21.N3 | R233 |
| ADR-0047.R22 | R234 |
| ADR-0047.R22.N1 | R234 |
| ADR-0047.R22.N2 | R235 |
| ADR-0047.R22.N3 | R236 |
| ADR-0047.R22.N4 | R232, R234 |
