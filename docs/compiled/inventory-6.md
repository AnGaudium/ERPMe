Module: inventory    Chunk: 6 of 7    Source ADRs: ADR-0047, ADR-0061
Build step(s): 3, 4, 5    Generated from index: 30d5706    Compiled by: Claude Opus 5.5, 2026-11-21

# Compiled spec: `inventory`, chunk 6

## Purpose

`inventory` owns stock documents, stock rows, valuation and warehouse execution (ADR-0022.R2). This chunk states the
`inventory` side of the commercial documents of ADR-0047: GR/IR per purchase order line by unit positions, purchase
returns, credit holds on demand and supply rows, cumulative limits and postings by transaction key, which `inventory`
shares with `purchasing` and `sales`. It also states the barcode query `EvaluateBarcode`, scan confirmation and GS1
capture on receipts (ADR-0061). The barcode registry, units of measure, books, query views and complaints are law of
other modules; their units are traced `ref:`.

## Entities and tables

DDL: `docs/design/DS-22-09-42-commercial-inventory.sql`.

| Table | Meaning | Key | Parent | Owner |
| --- | --- | --- | --- | --- |
| `purchase_order_line_gr_ir_posting` | Every GR/IR posting of a purchase order line: `document_id`, `line_number`, `posting_kind` (`receipt`, `return`, `invoice`, `quantity_credit`, `write_off`, `rounding_clearing`), `from_position`, `to_position`, `gr_ir_amount` in the order's currency, `reversal_of_posting_id` (R1002, R1003, R1011) | `id`; unique `reversal_of_posting_id` | `purchase_order_line` | `inventory` |
| `purchase_order_line_gr_ir_layer` | GR/IR price of a range of positions of a purchase order line: `from_position`, `to_position`, exact price `price_numerator` / `price_denominator` (R1001) | `id`; ranges of one line never overlap (`ex_purchase_order_line_gr_ir_layer_overlap`) | `purchase_order_line` | `inventory` |

Columns this chunk's rules set on tables whose rows stand in other chunks: `goods_receipt_line.gr_ir_position_from` and
`gr_ir_position_to` (R1005); `return_to_supplier_line.gr_ir_position_from`, `gr_ir_position_to` and
`goods_receipt_line_id` (R1006); `demand_supply_line.hold_reasons` (R1020). The rounding clearing is a row of
`purchase_order_line_gr_ir_posting` (ADR-0056.R10). Documents named: `return_to_supplier`
(R1013), `delivery` (R1020).

Reads: `purchase_order_line`, `purchase_return`, `purchase_credit_note`, `purchase_debit_note`, `gr_ir_write_off`,
`sales_return`, `credit_hold`, `customer_profile`, `partner`, `landed_cost`, `landed_cost_line`, `material_document_line`,
`item_barcode`, `barcode`, `bin`, `handling_unit`, `lot`, `serial_number`, `reason`.

## Commands and queries

| Name | Actor / authorization | Input | Effect | Events | Error codes |
| --- | --- | --- | --- | --- | --- |
| `EvaluateBarcode` (query of `inventory`) | People, the PWA and agents (read-only, on their tool lists); catalog leaf `general_access` at read | `scan`, optional `context`, the business date (R1030) | Computes candidates and issues from the scan; stores nothing (R1030-R1036) | Not stated | None; outcomes are check results (R1036) |
| `GetCreditExposure` (query of `sales`) | Not stated | A partner | Exposes `sales.contract.get_credit_exposure` to people and agents (R1016) | Not stated | Not stated |
| `ReleaseCreditHold` (a sales order) | `human_only`, its own permission, segregation from the order's author (ADR-0043.R13); effect class `other` | The order and a required reason | Records the credit release; resolves the work item `credit_hold` (R1021) | Not stated | Not stated |
| `Reverse` (receipts, service receipts, stock returns, supplier documents with order lines) | Verb level `full` (catalog) | The document | Mirrors the latest unreversed postings of a side (R1003) | Not stated | `reversal_not_latest` |

`ConfirmWarehouseTask` (R1037) and `PostDelivery` (R1020) have their rows in chunk 4. Not commands, declared by `inventory`: `inventory.contract.set_order_line_gr_ir_price` and
`inventory.contract.post_gr_ir_positions` (R1007), `inventory.contract.adjust_receipt_value` (R1008, R1029) and
`inventory.contract.set_demand_supply_hold` (R1018). Declared by `sales`: `sales.contract.get_credit_exposure` (R1016).

Codes raised by the rules of this chunk without a named command: `correction_exceeds_original` (R1025),
`gs1_capture_conflict` (R1041), and on pick release and receipt `demand_on_hold` and `demand_supply_not_released`
(R1020). Check results: `barcode_unknown`, `barcode_ambiguous`, `barcode_retired`, `lot_needs_item`,
`serial_needs_item`, `gs1_invalid`, `scan_malformed`, `gs1_element_ignored`, `scan_heuristic_used`,
`legacy_code_gtin_like` (R1036).

## Rules

### GR/IR per purchase order line, by unit positions

These rules detail ADR-0030.R4.

R1001. Positions. The line's units, in its inventory unit, are positions in order; positions count inventory quantities. `R` is the received quantity net of returns, `I` the invoiced quantity net of quantity credits. When a receipt or an invoice first reaches a position, the position is priced at the line's GR/IR price then in force (ADR-0047.R10). It keeps that price for the life of the line. Prices are stored as layers (from, to, price), exact rationals, in `purchase_order_line_gr_ir_layer`. `V(x)` is the exact value of positions 0 to `x`. An invoice's source is always the order line; a receipt or invoice entered in the order line's unit takes its inventory quantity by the cumulative rule (ADR-0056.R10); a return or credit takes the part it names as its source, and a purchase return naming a return-to-supplier line in the same unit and entered quantity takes that line's inventory quantity, so `R` and `I` move together.
Source: ADR-0047.R13, .N1

R1002. GR/IR postings are differences of rounded cumulative values, in the order's currency:
- a receipt of `q` credits GR/IR with `round(V(R + q)) − round(V(R))`;
- an invoice of `q` debits it with `round(V(I + q)) − round(V(I))`; the invoice amount less that is the price difference;
- a return of `q` debits it with `round(V(R)) − round(V(R − q))`, the latest received positions;
- a quantity credit of `q` credits it with `round(V(I)) − round(V(I − q))`.
Rounding is to the currency's minor unit. The balance of the line is therefore always `round(V(I)) − round(V(R))`, and zero whenever `R = I` (`INV-37`, `INV-92`). The latest-positions rule prices returns and quantity credits, also after a change order, and replaces the return price and the credit note price of ADR-0030.R4; only it keeps `INV-37` exact.
Source: ADR-0047.R13

R1003. Reversals. A document's postings on a line may be reversed only while they are the latest unreversed postings of their side (receipts and returns on `R`; invoices and quantity credits on `I`). The reversal mirrors them exactly. Otherwise `Reverse` is rejected with `reversal_not_latest`, and the correction is a return or a credit. This adds a precondition to ADR-0009.R18 and ADR-0009.R19 for goods receipts, service receipts, stock returns and supplier documents with order lines.
Source: ADR-0047.R13

R1004. Price-only documents. Supplier credit and debit notes without quantity, and price corrections, never touch GR/IR. Their amount is a price difference and goes as the regime sends `price_difference`.
Source: ADR-0047.R13

R1005. Consequences of the positions. A return names the receipt lines it returns, but GR/IR moves at the latest positions' value. Stock leaves at the value the regime sets for `purchase_return` (ADR-0020.R5). Any difference between that and the GR/IR debit is a price difference, posted on the return. A replacement receipt after a full return posts at the positions' first price. Each receipt line stores its position range (`goods_receipt_line.gr_ir_position_from`, `gr_ir_position_to`), which defines the "matched receipt lines" of ADR-0030.R1.
Source: ADR-0047.R13

R1006. The position range a return stores. `return_to_supplier_line.gr_ir_position_from` and `gr_ir_position_to` hold the positions the return actually debits: the order line's latest received positions, from `R − q` to `R`, where `R` is the received net before the return and `q` the return line's inventory quantity. They are in general not the positions of the receipt it names. The named receipt line, `goods_receipt_line_id`, is stored separately: it is the part reference whose inventory quantity the return mirrors or shares (ADR-0056.R10, part as source) and the receipt line the return names under R1005. With one GR/IR price on the line both ranges have the same value; after a change order they differ, and the stored range is the one that keeps `INV-37`. Under the interim seed of `purchase_return`, stock leaves at that debit, so the return posts no price difference (ADR-0020.R5 note). DS-22-09-42 states it on the columns; lab check `t17_uom.py` U70 and U71.
Source: ADR-0047.R13, .N2

R1007. Ownership. The layer table, each receipt line's position range, and the interfaces `inventory.contract.set_order_line_gr_ir_price` and `inventory.contract.post_gr_ir_positions` (side, quantity, sign; returning the amount) are `inventory`'s. `purchasing` calls them downward, under the order's document lock (ADR-0027.R10, class 1). They belong to the step 3 design (DS-09) and stay empty until step 5 (B3).
Source: ADR-0047.R13

R1008. Foreign currency. `INV-37` holds in the order's currency. The company-currency residual of a line from different receipt and invoice rates is measured on the posting that makes `R = I`, and that posting clears it (interim, until the step that builds it):
- On a line without stock (services, expenses) it is cleared to realized exchange difference (`fx_gain_realized`, `fx_loss_realized`); interim, flagged.
- On a line for an item kept in stock (its receipts post material document lines) the company setting `costing.exchange_rate_difference_to_stock` (area `inventory`, regime and company option, boolean, core default true, changed only from a period start, in the shape of ADR-0063.R24) chooses the treatment; the clearing posting reads the value in force on its posting date.
- True, the default (as SAP's default): the residual is its own difference kind. The posting that clears it debits or credits `purchase_cost_clearing` (the interim key, as for price differences sent to stock) and calls `inventory.contract.adjust_receipt_value`, which writes a `landed_cost` with `cost_type` `exchange_rate_difference` targeting the line's receipt lines, allocated by value: a `receipt_addition` in that posting's period (notes of ADR-0021.R6, ADR-0021.R12 and ADR-0020.R12).
- False: the residual posts as on a line without stock, to `fx_gain_realized` or `fx_loss_realized`, and stays out of the item's actual cost. The false path is interim, confirmed with the purchase invoice step (step 5). Keeping the difference out of stock is an accounting policy, so a regime package that opens false records it as a flagged value.
- Treating every rate difference as a price difference through an assumed rate is not offered.
Source: ADR-0047.R13, .N3, .N4

R1009. Still to design at the purchase invoice step (DS-22, step 5) for the exchange-rate difference of R1008: measuring it per invoice posting instead of at `R = I` (the GR/IR positions would then keep the receipt's company-currency amount); confirming the key (`purchase_cost_clearing`, or a transaction key of its own); the `cost_type` value in the `landed_cost_line` DDL and its CHECK; the invoice-first case, where the receipt's rate comes after the invoice's; and returned or written-off quantities.
Source: ADR-0047.R13.N3

R1010. Lines closed short with `R ≠ I`. Closing stops receipts, not invoices. A balance left on a closed line is listed by a close checklist task (DS-12) and cleared through the positions, so `INV-92` keeps holding: `I > R` by a supplier quantity credit (R1015); `R > I`, when the supplier will never invoice, by a `gr_ir_write_off` (`purchasing`, internal posting, `human_only`). That document moves `I` up to `R` at the positions' value, debiting GR/IR, and credits the regime's price difference (flagged for the author).
Source: ADR-0047.R13

R1011. The consequence posting `gr_ir_rounding_clearing`. When the line is fulfilled within the unit rounding tolerance and `R` and `I` still differ, it posts on the lagging side at the positions' value, against `price_difference`, with no human step. It also runs on a closed line whose `R` and `I` differ by no more than the tolerance; a larger difference stays on the closed-short path of R1010 (ADR-0047.R10). Its positions count in `R` or `I` for GR/IR, so `INV-92` holds with them. It is the posting that makes `R = I` for R1008, and reversing it reverses that entry. It never counts as latest in the latest-only check of R1003. Every later GR/IR posting on the line, a `gr_ir_write_off` included, first reverses it as a consequence, after which it fires again if the line is within tolerance.
Source: ADR-0047.R13.N1

R1012. Planned delivery costs (interim; details at the purchase invoice step, DS-22, step 5):
- A purchase order line may carry planned delivery cost conditions: a cost type (the `cost_type` values of ADR-0021.R1), an amount for the line, an amount per inventory unit or a percentage of the line's net value, and the freight supplier who will invoice it (the order's supplier when empty).
- A goods receipt of `q` units adds each condition's planned amount for those units to the receipt line's value, debiting the inventory key with the goods and crediting a delivery-cost clearing key per condition. The amount is a difference of rounded cumulative values over the line's positions, as in R1002, so a fully received line accrues exactly the planned amount, and a return reverses the accrual at the latest positions.
- The freight supplier's invoice line names the condition and debits the clearing with the accrued amount for the quantity it invoices. The difference between invoiced and accrued is a price difference, handled like the purchase price difference: as the regime determines `price_difference`, to an account, or to stock through `inventory.contract.adjust_receipt_value` in the invoice's posting period (notes of ADR-0021.R6 and ADR-0021.R12).
- Costs with no condition stay the unplanned path of ADR-0021 (`landed_cost`), with the treatment of the ADR-0021.R12 note.
- No DDL, transaction key or system account is added for this yet: step 5 builds the planned delivery costs entry under "S2 closure (2026-11-21)" in `docs/open-questions.md`.
Source: ADR-0047.R13.N4

### Purchase returns and supplier corrections

R1013. The goods of a purchase return. `return_to_supplier` (`inventory`; `correction_of_id`: the goods receipt) issues them with movement `purchase_return`, debiting GR/IR by R1002. `inventory` checks returned ≤ received per receipt line.
Source: ADR-0047.R15

R1014. The money of a purchase return. `purchase_return` records the supplier's adjustment for returned goods: `correction_of_id` is the purchase invoice, and lines refer to `return_to_supplier` lines. It credits GR/IR by R1002 as a quantity credit. Its lines carry the line unit block (ADR-0056.R9). A purchase return line that names a return-to-supplier line in the same unit and for the same entered quantity takes that line's inventory quantity, so the stock return and the supplier's credit move `R` and `I` by the same amount (ADR-0056.R10). A `purchasing` consumer raises a work item `supplier_credit_due` when a stock return leaves invoiced net above received net on an order line.
Source: ADR-0047.R15, .N1

R1015. Other supplier credits. `purchase_credit_note` (`correction_of_id`: the purchase invoice) records the supplier's credit for anything but returned goods. Its quantity lines (goods invoiced but never delivered, or an invoicing error) are quantity credits on `I` by R1002, within the invoice line's invoiced net (R1025). Its price lines are price-only. Its lines carry the line unit block and `item_id`. `purchase_debit_note` records the supplier's increase, price-only.
Source: ADR-0047.R15, .N1

### Credit holds and release holds on demand and supply rows

R1016. Exposure. `sales.contract.get_credit_exposure(partner)` composes the parts of ADR-0030.R6 per currency. It converts them to the limit's currency at rate type `transaction` on the check date (ADR-0011.R11; flagged). The query `GetCreditExposure` exposes it to people and agents. Exposure, the hold and `customer_profile.credit_limit` are those of the payer (else the bill-to party, else the sold-to partner); the demand rows held are those of the orders that resolve to it (ADR-0074.R4).
Source: ADR-0047.R18, .N5

R1017. At Submit and approval. The sales order's `Submit` locks as ADR-0030.R7 says: classes 1–8, then the partner row (class 9). It reads the exposure with the order included, and passes `is_credit_exceeded` to the policy hook. An order approved while `is_credit_exceeded` was true records that approval as its credit release; it is not held afterwards for the exposure it was approved with.
Source: ADR-0047.R18

R1018. Holds set in the same transaction. Every `sales` command that raises a partner's exposure re-evaluates it under the same locks, and updates holds through `inventory.contract.set_demand_supply_hold(rows, reason, is_held)` with reason `credit_hold`: submit, approval, take-force of a change order, and posting an invoice. Over the limit, it sets `credit_hold` on the open demand rows of the partner's approved orders without a release. Under the limit, it clears them. These row updates take no document lock of the other orders: the hold is a flag on `inventory`'s rows, set or cleared by a row update that does not conflict with other changes to those orders. A delivery that read no hold just before the hold lands still posts; that race is accepted (flagged).
Source: ADR-0047.R18, .N1

R1019. Holds updated by a consumer. Events that lower exposure (payments and credits through DS-25, cancel and close) are handled by a `sales` consumer, which clears holds. A lowered credit limit (a `master_data` change, which cannot call `sales`) is handled the same way, which leaves a short window before holds land (flagged).
Source: ADR-0047.R18

R1020. Hold reasons. Holds are stored as a set of reasons on each demand or supply row, `demand_supply_line.hold_reasons`, with the values `not_approved` and `credit_hold`. Sales order demand rows and purchase order supply rows are created unreleased (`not_approved`, ADR-0047.R19). `sales` and `purchasing` release them when the document is approved, or at `Submit` when no approval is required, and set `not_approved` again on `Reject`. `inventory` rejects pick release, delivery and receipt of a row held `not_approved` with `demand_supply_not_released`, and of a row held `credit_hold` with `demand_on_hold`; it never reads `sales` or `purchasing`. `PostDelivery` is not `is_policy_in_handler`.
Source: ADR-0047.R18, .N1

R1021. Release. `ReleaseCreditHold` (a sales order) is `human_only`, with its own permission, a required reason, and segregation from the order's author (ADR-0043.R13). Its effect class is `other`. The release lasts until the order's value grows by a change order. When `sales` sets `credit_hold` on an order's rows, it raises one work item `credit_hold` (subject the sales order, owner role `accountant`), resolved by `ReleaseCreditHold`, or by the system when the hold is cleared because the exposure fell under the limit.
Source: ADR-0047.R18, .N2

R1022. The stored states of a `credit_hold` row, `held`, `released`, `cleared` and `lapsed` (DS-22-09-42-commercial-inventory.sql), are interim: ADR-0047.R18 does not name them.
Source: ADR-0047.R18.N3

R1023. A customer profile without `credit_limit` has no credit check: `is_credit_exceeded` is false and no `credit_hold` is set for that partner; `GetCreditExposure` still reports the exposure. `CreatePartner` leaves the limit empty unless the payload gives one (ADR-0045.R13 note); a company that wants every customer checked sets a limit on each profile.
Source: ADR-0047.R18.N4

R1024. These holds replace the credit check of ADR-0030.R7 at `PostDelivery`, which `inventory` could not compose without reading a higher layer. The outcomes of `EC-21` and `EC-63` are confirmed (ADR-0047.R22.N4): approval at Submit, with the other unreleased orders held.
Source: ADR-0047.R18

### Cumulative limits

R1025. Cumulative limits (ADR-0009.R23; `INV-40`, completed here):
- Per delivery or receipt line: returned ≤ delivered or received (checked by `inventory`).
- Per invoice line: quantity credited (by `sales_return`, `purchase_return` or a quantity credit) ≤ invoiced; amount credited ≤ the line's net amount less earlier credits.
- Per order line: delivered or received net ≤ ordered (with the receipt tolerance); for stock sales order lines, invoiced net ≤ delivered net, except while a `sales_return_due` work item is open; for purchase order lines, invoiced net may exceed received net (invoice before receipt, ADR-0047.R14, unless `purchasing.match.require_receipt`), and a stock return that leaves it above raises `supplier_credit_due` (R1014); the quantity credited by returns ≤ the returned quantity not yet credited.
- Violations are rejected with `correction_exceeds_original`. Documents in `issuing` count.
Source: ADR-0047.R20

R1026. `EC-20`: when a return makes invoiced net exceed delivered net on an order line, a `sales_return` for the difference, the invoiced share, is due and a sales return work item is raised (ADR-0047.R7; confirmed by ADR-0047.R22.N4). Returned goods that were never invoiced simply reduce what remains to invoice.
Source: ADR-0047.R20

R1027. Every limit of R1025 compares inventory quantities and allows the unit rounding tolerance of the source line. The tolerance grows by one smallest inventory step per part posted in another unit whose conversion rounded, and by the change each return, credit, reversal or clamped part made to the deviation `P − round(C × f)`; it never shrinks, and with an exact snapshot it stays zero, so every limit is exact (ADR-0056.R10).
Source: ADR-0047.R20.N1

### Postings

R1028. Postings by transaction key (ADR-0015), given as document: debit; credit.
- Delivery: `cost_of_goods_sold` (free goods: `free_goods_cost`); inventory.
- Return from customer: inventory; `cost_of_goods_sold` (regime value).
- Sales invoice: `receivable_reconciliation` per installment; `revenue_posting`, `output_tax`, discounts by ADR-0047.R6.
- Sales return: `revenue_deduction_return`, `output_tax`; `receivable_reconciliation` (credit item).
- Credit note: by reason (ADR-0047.R8), `output_tax`; `receivable_reconciliation` (credit item).
- Debit note: `receivable_reconciliation`; `revenue_posting`, `output_tax`.
- Goods receipt: inventory; `gr_ir_clearing` (R1002).
- Purchase invoice, goods: `gr_ir_clearing` (R1002), price difference (`price_difference` or `purchase_cost_clearing`), `input_tax`; `payable_reconciliation` per installment.
- Purchase invoice, service with a service receipt: `gr_ir_clearing`, price difference (ADR-0037.R6), `input_tax`; `payable_reconciliation`.
- Purchase invoice, service without one, or expense: expense by determination, `input_tax`; `payable_reconciliation`.
- Purchase invoice, landed cost: debit `input_tax` and, as the setting `landed_cost.unplanned_cost_treatment` chooses (ADR-0021.R12.N2), `purchase_cost_clearing` under `distribute_to_items` (the default) or the account determined by `purchase_expense` under `separate_account` (interim until step 5; never stock); credit `payable_reconciliation`.
- Return to supplier: `gr_ir_clearing` (R1002), price difference if the regime's stock value differs; inventory.
- Purchase return: `payable_reconciliation`; `gr_ir_clearing` (R1002), price difference, `input_tax`.
- Supplier credit note: `payable_reconciliation`; `gr_ir_clearing` for quantity lines (R1002), price difference for price lines, `input_tax`.
- Supplier debit note: price difference, `input_tax`; `payable_reconciliation`.
- GR/IR write-off (closed line, `R > I`): `gr_ir_clearing` (R1002); price difference.
- Release at order close (invoice-first): `purchase_cost_clearing`; `price_difference` (ADR-0030.R4).
- `gr_ir_rounding_clearing`: GR/IR against `price_difference` at the positions' value, as a consequence posting (ADR-0056.R10).
Source: ADR-0047.R21, .N2

R1029. A goods line with a price difference. GR/IR is debited by R1002 and the rest is the price difference. Where the regime sends `price_difference` to an inventory account, the invoice posts the difference to `purchase_cost_clearing` (ADR-0021.R12) and, in the same transaction, `inventory.contract.adjust_receipt_value` writes a `landed_cost` with `cost_type` `price_difference`, `posted`, targeting the receipt line (ADR-0030.R1); it debits `inventory_posting` and credits `purchase_cost_clearing`, which returns to zero. The value posts in the posting period of the `adjust_receipt_value` document, dated per R805 (the latest receipt's date when the invoice is earlier; the first unlocked period when the invoice's period is locked), whatever the receipt's period: a value-only `receipt_addition` that takes part in the actual cost of that period. No locked period is recomputed and nothing is allocated to past consumers (ADR-0021.R6.N2). Where the regime sends `price_difference` to an expense account, the invoice posts the difference there, with no landed cost. The accounts of a regime's worked example are flagged `unverified` content of its localization package (DS-19).
Source: ADR-0047.R21.N1, .N3

### Barcode evaluation

R1030. `EvaluateBarcode` is a registered query of module `inventory`, which reads master data and documents through their contracts. It is the third query form of ADR-0004.R21 (its note): it computes a result from the scan it is given and stores nothing. People, the PWA and agents call the same query; agents may call it on their tool lists (ADR-0050), read-only. Input:
- `scan`: `raw`, optional `symbology_identifier`, `source` (`wedge`, `camera` or `manual`), optional `decoder` (`native` or `wasm`, for camera scans), optional `camera_format` as BarcodeDetector names it, optional `confirmed_as_read`;
- optional `context`: `mode` (`search` or `confirm`); `expected`, a list of `{type, id}` or `{type, scope}`, which may name the expected lot or serial code; `item_id` for lot and serial context; `warehouse_id`;
- the business date.
Source: ADR-0061.R12

R1031. `EvaluateBarcode` output: `normalized`, `symbology` (the identifier, or `none`), `encoding` (`gs1_element_string`, `digital_link`, `gtin`, `internal`), `elements` (AI to value, interpreted: ISO dates, decimal measures with their unit), `gs1_syntax_dictionary_version`, `candidates` (each `{type, id, code, item_id, uom_id, lot_id, lot_code, serial_number_id, serial_code, quantity, quantity_uom_id, expiry_date, match: exact | contextual}`) and `issues` (R1036). Candidates the caller may not read are left out; when every candidate is left out, the answer is `barcode_unknown`, so nothing leaks. `barcode_retired` names only the type the code had, never its old owner.
Source: ADR-0061.R12

R1032. Resolution order, step 1, the symbology identifier (sent by the scanner as `]` plus two characters, or by the WebAssembly decoder): `]C1`, `]e0`, `]d2`, `]Q3`, `]J1` mean a GS1 element string; `]E0` a GTIN-13 or a UPC-A sent as 13 digits with a leading zero, `]E4` a GTIN-8; `]I1` an ITF whose check character the scanner validated, a GTIN when it has 14 digits and plain data otherwise; `]Q1` or `]d1` with `http://` or `https://` a candidate Digital Link; `]C0`, `]A0`, `]Q1`, `]d1` otherwise plain data. Any identifier not listed (`]I0`, `]E3`, `]C2`, `]Q2`, `]L0`, …) means plain data, which goes to steps 4 and 5. A plain Code 128 that happens to start with `01` is never parsed as GS1 when the identifier arrives. The order is one and deterministic.
Source: ADR-0061.R13

R1033. Resolution step 2, without an identifier (a wedge without the AIM prefix, a camera decoder that sends none): a scan that equals a registered legacy code, or whose digits padded to 14 equal a numeric legacy code, goes straight to step 4. Otherwise guarded rules apply, each reported as the check result `scan_heuristic_used`: a leading or embedded GS means an element string; 8, 12, 13 or 14 digits with a valid check digit mean a GTIN; `http(s)://` with a primary key AI segment means a Digital Link; other data starting with a digit is parsed as an element string and accepted only when it parses completely, its first element is a key and every check passes. Data that is none of these, a leading letter or digits that fail as a GTIN and as an element string (a numeric lot code), is plain data and goes on to steps 4 and 5; `barcode_unknown` comes only after them.
Source: ADR-0061.R13

R1034. Resolution step 3, GS1 keys. (00) finds a handling unit by SSCC; (01) finds `item_barcode` by GTIN, which gives the item and the unit; (01) with (10) the lot of that item by code; (01) with (21) the serial of that item by code, and with (10) as well, one serial candidate that also carries the lot; (02) with (37) the contained item unit and its count. A lot or serial code the item does not have yet is a candidate without ID, for capture (R1040). A GTIN without AIs (`]E0`, `]E4`, `]I1`, or 8 to 14 digits) that is not registered is looked up once more as a numeric legacy code, comparing digits padded to 14, so an old internal number printed as EAN-13 or UPC-A still resolves (ADR-0061.R8). An unknown GTIN is `barcode_unknown` with `details.key: gtin`; the screen offers `CreateItemBarcode`, and an agent may only draft it as a proposal. (414) with (254), (253), (8003) and (8004) are read and reported as `gs1_element_ignored` in Phase 1 (ADR-0061.R25).
Source: ADR-0061.R13

R1035. Resolution steps 4 to 6:
- Step 4, the registry (ADR-0061.R7), for GTINs without AIs, internal codes, legacy codes and other plain data: the row's type leads to the typed row. A reserved row is `barcode_retired`.
- Step 5, lots and serials without GS1: plain data that is no registered code but is the code of lots or serials of the company resolves only with an item from the context (the task's item, or an item scanned earlier in the step); without one it is `lot_needs_item` or `serial_needs_item`, even when only one item has that code today.
- Step 6, context: in `confirm` mode the expected types and objects filter the candidates; more than one candidate left is `barcode_ambiguous` (a pallet label with (00) and (02) scanned on a search screen, for example).
Source: ADR-0061.R13

R1036. Typed issues, never a guess. Issues are check-result codes in the response, each with `details`: `barcode_unknown` (no key, registry row or code matches), `barcode_ambiguous` (several candidates remain; the screen offers a chooser), `barcode_retired` (`details.retired_type`), `lot_needs_item`, `serial_needs_item`, `gs1_invalid` (`details.reason` from ADR-0061.R3 and `details.ai`), and `scan_malformed`. Information only: `gs1_element_ignored`, `scan_heuristic_used`. A command that registers a legacy code may return `legacy_code_gtin_like` (ADR-0061.R8). The query never picks the first of several candidates, never strips a check digit that fails, and never reads a lot code without an item.
Source: ADR-0061.R14

### Scans in commands

R1037. Scan-to-confirm on every posting step: `ConfirmWarehouseTask` (source bin, handling unit, item, lot, serials, target bin), receipts, deliveries, production issues and receipts, and counts. The step states what it expects: an exact object (the task's source bin), or a type within a scope (a lot of the task's item, a serial of the task's item, an item of the counted bin, any storage bin of the warehouse when the worker changes the target). A scan that resolves to anything else is refused with `scan_mismatch` (`details`: expected and scanned), and a scan with an issue with `scan_unresolved` (`details`: the issues). Nothing is replaced silently.
Source: ADR-0061.R15

R1038. Overrides are separate fields of the command with a reason, never a second scan: a different target bin (ADR-0023.R12, ADR-0023.R15), a shortage reason, typed values when a label is unreadable. Scan-to-search (home screen, stock inquiry, "what is this") calls `EvaluateBarcode` in `search` mode: one candidate opens it, several give a chooser, none offer the unknown-barcode actions. Search only opens records, never posts, and agents never submit scans.
Source: ADR-0061.R15

R1039. Scans in command payloads. A scan command carries each scanned field as a `scan` object (`raw`, `symbology_identifier`, `source`, `decoder`, `confirmed_as_read`) next to the field it fills.
- The server resolves: the handler normalizes, parses and resolves `raw` again with the business date and the step's context; the client's own parse is never trusted. The plan and the stored audit payload keep `raw`, so every scan can be replayed and explained.
- Untrusted text: `raw` and every free-text element (lot and serial codes, (400), (90) to (99), the Digital Link domain) come from someone else's label: they carry `is_untrusted` (ADR-0029.R10), are validated against their format, and are looked up, never followed.
- Idempotency: each scan event gets its own idempotency key on the device (ADR-0008.R14); the camera de-duplicates the same value for 1.5 seconds before a key is made.
Source: ADR-0061.R16

R1040. GS1 multi-field capture on receipts. A scan command's input schema maps AIs to its fields; the mapping is registered with the command (a generated annotation of the JSON Schema), so the PWA, the desktop screen and the server read one table. AI, field, rule:
- (01): `item_id`, `uom_id`; through `item_barcode`; must equal the line's item when a line is expected (`scan_mismatch`).
- (10): lot; an existing lot of the item by code, or a new lot created by the receipt with that code.
- (17): lot `expiry_date`; set on a new lot, compared on an existing one.
- (15): only when (17) is absent; it fills the lot's `expiry_date` only while `barcode.gs1.best_before_fills_expiry` reads true for the category, and with the default false it is stored as the lot's `best_before_date` (ADR-0063.R26).
- (11): lot `manufacture_date`; as (17).
- (21): serial; an existing serial of the item, or a new one created by the receipt; with (10), in that lot.
- (30): `quantity`, in the unit of the (01) barcode.
- (02) + (37): `item_id`, `uom_id`, `quantity`; the contained item unit and its count.
- 310n, 311n, 314n, 315n, 316n: `quantity`, `uom_id`, in the AI's unit (ADR-0061.R18).
- (00): handling unit; a new handling unit of the receipt takes the SSCC as its barcode in a handling-unit-managed warehouse.
Source: ADR-0061.R17, .N1

R1041. GS1 capture outcomes:
- Conflicts stop: a scanned value that differs from a value the person typed, or from an existing lot's expiry or manufacture date, is refused with `gs1_capture_conflict` (`details`: field, scanned, stored). Lot dates change only by their own command.
- Quantity default: from (30), (37) or a measure AI; otherwise 1 in the barcode's unit (one carton for a carton GTIN). Serial items never default to the task quantity.
- Other AIs ((400), (90) to (99), unmapped measures) stay in the payload's parse result and are reported as `gs1_element_ignored`.
- Scope: receipts (goods receipts, production receipts, customer returns) in Phase 1, from step 5 on the desktop; picks and packing at step 9 with the PWA.
Source: ADR-0061.R17

R1042. The annotation of the capture mapping is `x-nativeflows-scan`: the expected barcode type and the GS1 Application Identifier mapping of the field (ADR-0077.R9).
Source: ADR-0061.R17.N2

## Invariants

Statements are those of `invariants.csv`. This chunk holds the rows whose catalog source is a rule stated here.

| Invariant | Name | Check point | Statement | Protects |
| --- | --- | --- | --- | --- |
| `INV-40` | `corrections_within_original` | day | Cumulative corrections never exceed the original: returned per delivery line within delivered, credited quantity per invoice line within invoiced, credited amount within the line's net amount, and the same for purchase lines (ADR-0047.R20). | R1025, R1027; ADR-0009.R23 |
| `INV-92` | `gr_ir_equals_rounded_positions` | day | Per purchase order line, the GR/IR balance in the order's currency equals `round(V(I)) - round(V(R))` at the line's position layers, `V` being the exact value of positions up to a quantity and rounding to the currency's minor unit; it is zero when received net equals invoiced net. | R1002, R1010, R1011; ADR-0030.R5 |

Named by rules of this chunk, with their rows elsewhere: `INV-37` (R1002, R1006, R1008).

## Edge cases

| Edge case | Name | Case | Outcome | Protects |
| --- | --- | --- | --- | --- |
| `EC-20` | `return_of_partly_invoiced_goods` | A customer returns goods of which only part was invoiced: a sales return for the invoiced share is due; uninvoiced returned goods reduce what remains to invoice. | `must_succeed` | R1026; ADR-0009.R23 |
| `EC-21` | `credit_limit_exceeded` | A sales order that would take a customer over its credit limit: approval at Submit; deliveries of other unreleased orders held. | `must_succeed` | R1017, R1018, R1024 |
| `EC-119` | `gs1_receipt_lot_expiry` | A supplier carton label in GS1-128 with (01), (17) and (10) is scanned at receipt: the carton GTIN gives item and unit, the lot is created with its expiry date, and one carton is received in the inventory unit. | `must_succeed` | R1034, R1040 |
| `EC-124` | `bare_lot_code_two_items` | A lot code that two items share is scanned on a search screen; the query returns `lot_needs_item` and no candidate. | `must_succeed` | R1035 |
| `EC-128` | `legacy_codes_migrated` | Migration loads the old system's numeric bin and item labels as legacy codes; one item code passes a GTIN check digit and is listed with `legacy_code_gtin_like`; Code 128 scans of the bins and EAN-13 and UPC-A scans of the item codes resolve to their objects. | `must_succeed` | R1033, R1034; ADR-0061.R8; ADR-0044.R3 |

Named by a rule of this chunk, with its row elsewhere: `EC-63` (R1024; catalog source ADR-0030).

## Settings

| Key | Value type | Scopes | Core default | Used by |
| --- | --- | --- | --- | --- |
| `costing.exchange_rate_difference_to_stock` | boolean (area `inventory`, `regime_option`, changed only from a period start) | `regime`, `company` | `true` | R1008 |
| `barcode.gs1.best_before_fills_expiry` | boolean (area `barcode`, `company_setting`, effect immediate) | `company`, `product_category` | `false` | R1040 |

Read, owned by `purchasing`: `purchasing.match.require_receipt` (R1025).

## UI annotations

- Scan fields of receipt commands carry `x-nativeflows-scan`: the expected barcode type and the GS1 Application Identifier mapping of the field (R1042; ADR-0077.R9).
- Work item kinds raised by the rules of this chunk belong to other modules: `credit_hold` (`sales`, R1021), `supplier_credit_due` (`purchasing`, R1014) and `sales_return_due` (`sales`, R1025).

## Conflicts

CONFLICT ADR-0061.R17: its interim that (15) best before fills the lot's `expiry_date` when (17) is absent is changed by ADR-0063.R26 (note ADR-0061.R17.N1): (15) fills the expiry date only while `barcode.gs1.best_before_fills_expiry` reads true for the category; with the default false it is stored as `best_before_date` (R1040).
CONFLICT ADR-0047.R13: the interim clearing of the company-currency residual to realized exchange difference now holds only for lines without stock; for items kept in stock ADR-0047.R13.N3 and ADR-0047.R13.N4 govern through `costing.exchange_rate_difference_to_stock` (R1008).
CONFLICT ADR-0047.R13.N3: on a stocked line the residual posts to `purchase_cost_clearing` and enters the receipt value as a `receipt_addition` in the clearing posting's period, instead of realized exchange accounts; the setting added by ADR-0047.R13.N4 may send it back there (R1008).
CONFLICT ADR-0047.R18: the outcomes of EC-21 and EC-63 lose their interim mark, because ADR-0047.R22.N4 confirms rule 18 as written (R1024).
CONFLICT ADR-0047.R18.N1: `inventory.contract.set_demand_hold` is replaced by `set_demand_supply_hold` with the hold reasons `not_approved` and `credit_hold` stored per row; this note governs the original hold interface (R1018, R1020).
CONFLICT ADR-0047.R20: the EC-20 outcome is no longer interim and flagged; ADR-0047.R22.N4 confirmed the cumulative limits and its sales return work item for the invoiced share (R1026).
CONFLICT ADR-0047.R21: its row "Purchase invoice, landed cost: debit `purchase_cost_clearing`" holds only under `landed_cost.unplanned_cost_treatment` `distribute_to_items`; ADR-0021.R12.N2 governs, and under `separate_account` the line debits the account determined by `purchase_expense` (R1028).
CONFLICT ADR-0047.R21.N1: the closed-period branch of the example (method `consumer_split`, value split between stock on hand and past consumers) is superseded by ADR-0047.R21.N3 and the late-cost decision of ADR-0021.R6.N2: the price difference posts in the posting period of the `adjust_receipt_value` document (R805) as a value-only `receipt_addition` (R1029).
CONFLICT ADR-0047.R21.N3: this note governs the price difference sent to stock for a receipt of an earlier period; it follows the author's decision recorded at ADR-0021.R6.N2, so no locked period is recomputed and no past consumer is charged (R1029).

## Proposed (not law)

None

## Trace

| Source | Where |
| --- | --- |
| ADR-0047.R13 | R1002, R1003, R1004, R1005, R1007, R1008, R1010, R1001, R1006 |
| ADR-0047.R13.N1 | R1001, R1011 |
| ADR-0047.R13.N2 | R1006 |
| ADR-0047.R13.N3 | R1008, R1009 |
| ADR-0047.R13.N4 | R1008, R1012 |
| ADR-0047.R15 | R1013, R1014, R1015 |
| ADR-0047.R15.N1 | R1014, R1015 |
| ADR-0047.R18 | R1016, R1017, R1018, R1019, R1020, R1021, R1024 |
| ADR-0047.R18.N1 | R1018, R1020 |
| ADR-0047.R18.N2 | R1021 |
| ADR-0047.R18.N3 | R1022 |
| ADR-0047.R18.N4 | R1023 |
| ADR-0047.R18.N5 | R1016 |
| ADR-0047.R20 | R1025, R1026 |
| ADR-0047.R20.N1 | R1027 |
| ADR-0047.R21 | R1028 |
| ADR-0047.R21.N1 | R1029 |
| ADR-0047.R21.N2 | R1028 |
| ADR-0047.R21.N3 | R1029 |
| ADR-0049.R10 | ref: ADR-0049.R10 |
| ADR-0050.R51 | ref: ADR-0050.R51 |
| ADR-0050.R51.N1 | ref: ADR-0050.R51 |
| ADR-0050.R51.N2 | ref: ADR-0050.R51 |
| ADR-0050.R51.N4 | ref: ADR-0050.R51 |
| ADR-0052.R20 | ref: ADR-0052.R20 |
| ADR-0052.R20.N1 | ref: ADR-0052.R20 |
| ADR-0056.R9 | ref: ADR-0056.R9 |
| ADR-0056.R10 | ref: ADR-0056.R10 |
| ADR-0056.R10.N1 | ref: ADR-0056.R10 |
| ADR-0060.R33 | ref: ADR-0060.R33 |
| ADR-0061.R7 | ref: ADR-0061.R7 |
| ADR-0061.R8 | ref: ADR-0061.R8 |
| ADR-0061.R12 | R1030, R1031 |
| ADR-0061.R13 | R1032, R1033, R1034, R1035 |
| ADR-0061.R14 | R1036 |
| ADR-0061.R15 | R1037, R1038 |
| ADR-0061.R16 | R1039 |
| ADR-0061.R17 | R1040, R1041 |
| ADR-0061.R17.N1 | R1040 |
| ADR-0061.R17.N2 | R1042 |
