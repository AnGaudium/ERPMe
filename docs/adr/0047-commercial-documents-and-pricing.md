# ADR-0047: Commercial documents and the pricing procedure

Status: accepted (2026-11-15) under ADR-0005, reviewed by Claude Fable 5.2 (builder Claude Opus 5.5). Design item: DS-22. Related decisions: D4, D5. Principles 1, 3, 5, 6, 9. ADR-0006, ADR-0009, ADR-0011, ADR-0017, ADR-0018, ADR-0019, ADR-0020, ADR-0021, ADR-0023, ADR-0024, ADR-0026, ADR-0027, ADR-0028, ADR-0029, ADR-0030, ADR-0031, ADR-0037, ADR-0041, ADR-0042, ADR-0043, ADR-0044, ADR-0045, ADR-0046.

## Decision

The commercial documents are a thin layer over the core (B3). They hold what was agreed with a partner, price it with one procedure, and post through the core contracts: stock through `inventory`, money through `ledger`, taxes through `tax`. Everything a document does is visible in its plan.

**Sales.** Quotation → sales order → delivery (inventory) → sales invoice. A return is a stock return from the customer (inventory) and, for goods already invoiced, a `sales_return` that credits them. Other changes to an invoice are a `credit_note` or a `debit_note`.

**Purchasing.** Purchase request → purchase order → goods receipt (inventory) → purchase invoice. A return is a stock return to the supplier (inventory) and, for goods already invoiced, a `purchase_return` that records the supplier's credit. These keep ADR-0009 rule 23's and ADR-0027 rule 7's definitions.

**One pricing procedure.** It starts from ADR-0045's `find_price`, applies at most one promotion and the manual discount, and stores the net unit price at the unit-price scale. The line amount is computed from the stored price, rounded once. A document discount percentage is allocated to lines exactly. Every step is stored on the line, so a person, an agent and an auditor see why a price is what it is.

**GR/IR by unit positions.** Each purchase order line prices its units, in order, once: at the order price in force when each unit first posts, by receipt or by invoice. Returns and credit notes take the latest units, and each posting is a difference of rounded cumulative values. The GR/IR balance of a line is then always `round(V(I)) − round(V(R))`, which is exactly zero when received equals invoiced. The lab checks this on 600 random sequences with rounding, reversals and price changes.

**Credit holds.** Credit is checked when an order is submitted. It is enforced at delivery by a hold on the order's demand rows, which `sales` sets and `inventory` respects, so the layers stay intact.

### Rules

**Types and ownership**

1. Document types (ADR-0009 rules 2–3), with their registry flags:

   | Type | Module | Posting | Change orders | E-invoice capable | Approval hold allowed | Reversible | `is_item_creating` | Demand and supply |
   | --- | --- | --- | --- | --- | --- | --- | --- | --- |
   | `quotation` | `sales` | no | no | no | yes | — | no | none |
   | `sales_order` | `sales` | no | yes | no | yes | — | yes | demand, after draft |
   | `sales_invoice` | `sales` | yes | no | yes | no | no | no | — |
   | `sales_return`, `credit_note`, `debit_note` | `sales` | yes | no | yes | no | no | no | — |
   | `purchase_request` | `purchasing` | no | no | no | yes | — | no | supply, from draft |
   | `purchase_order` | `purchasing` | no | yes | no | yes | — | no | supply, from draft |
   | `purchase_invoice` | `purchasing` | yes | no | no | yes | latest only (rule 13) | no | — |
   | `purchase_return`, `purchase_credit_note`, `purchase_debit_note` | `purchasing` | yes | no | no | yes | latest only (rule 13) | no | — |
   | `gr_ir_write_off` | `purchasing` | yes | no | no | yes | latest only (rule 13) | no | — |

   - **Stock documents** (`goods_receipt`, `delivery`, `return_to_supplier`, `return_from_customer`) stay `inventory`'s, with their flags set by DS-09 (ADR-0027 rule 13). Their reversal of order lines is limited by rule 13. From step 5 their lines carry the order line references reserved at step 3 (ADR-0027 rule 7).
   - **Customs declarations, amendments and service receipts** keep the flags ADR-0021 rules 10–11 and ADR-0037 rule 5 give them. A service receipt's reversal is also limited by rule 13.
   - **`is_item_creating`** is a new registry flag. Only types with it create items on order when they leave draft (ADR-0045 rule 16; [ADR-0046](0046-product-configuration.md) rule 11): here `sales_order`, and `production_order` by ADR-0046. Quotations never create items.
   - **Adjustment and replacement invoices.** `sales_return`, `credit_note` and `debit_note` are the adjustment documents of sales invoices (spec 08). Phase 1 models a replacement as a full `credit_note` plus a new invoice. Whether Vietnam requires a single replacement invoice, and the form of returns under the current decree, is for the author to verify. A dedicated type would be the e-invoice add-on's (DS-24).
   - **Who posts corrections.** `Post` or `Issue` of every correction type in this table is `human_only` (ADR-0009 rule 23, interim).
   - **Kits** (bill of materials usage `kit`, ADR-0033 rule 3) come after Phase 1 (open question).

   Note: "Approval hold allowed" for `sales_invoice`, `sales_return`, `credit_note` and `debit_note` is derived from the regime setting `documents.issuance_without_delay`: "no" while it is true, as `l10n_vn` seeds it; the core default is false ([ADR-0053](0053-core-neutrality.md) rule 8). Corrections stay correction documents by the author's core decision of 2026-11-14; the adjustment and replacement invoice forms are `l10n_vn`'s and the e-invoice add-on's ([ADR-0053](0053-core-neutrality.md) rule 14).

   Note: every type in this table, and the stock documents, are `is_printable` and carry the optional header field `print_language` ([ADR-0049](0049-statutory-reporting-and-printing.md) rules 25, 27).

   Note: registry flags of `service_receipt` ([ADR-0037](0037-subcontracting.md) rule 5) (holistic review 2026-11-15, item P15):

   | Type | Module | Posting | Change orders | E-invoice capable | Approval hold allowed | Reversible | `is_item_creating` | Demand and supply |
   | --- | --- | --- | --- | --- | --- | --- | --- | --- |
   | `service_receipt` | `purchasing` | yes | no | no | no | while no invoice refers to it (rule 13) | no | — |

   Note ([ADR-0056](0056-multiple-units-of-measure.md), 2026-11-15): document type `gr_ir_rounding_clearing`: `purchasing`, posting, no change orders, not e-invoice capable, no approval hold, reversed only as a consequence (never by `Reverse`), not item-creating, no demand or supply. Its `Post` is `is_internal_only` and `is_consequence_posting`; its authorization leaf is under purchasing at level `full`, in no template's expansion. It has its own `document` row and no header or line table: its `purchase_order_line_gr_ir_posting` row of kind `rounding_clearing` carries the line, positions and amount (rule 10).
2. Lines, references and copying:
   - **Quantities.** Lines store the entered quantity and unit and the inventory quantity (ADR-0018 rule 11). GR/IR positions, correction limits and progress use inventory quantities.
   - **Line references** use the typed keys of ADR-0028 rule 2: `quotation_line_id`, `sales_order_line_id`, `delivery_line_id`, `return_from_customer_line_id`, `purchase_request_line_id`, `purchase_order_line_id`, `goods_receipt_line_id`, `return_to_supplier_line_id`, and `correction_of_line_id` on correction lines.
   - **Configurations and options.** Lines carry their `product_configuration`, custom text in `document_line_custom_text`, and the checks of [ADR-0046](0046-product-configuration.md) rules 9–10 (completeness, the warehouse of configurable lines, re-evaluation when copied to a new document).
   - **Copying.** `Create<Type>` accepts `source_lines` (a source document's line numbers and quantities). The handler copies the lines with their references, prices, discounts, taxes and configuration, and sets `derived_from_version_id` (ADR-0029 rule 8). It copies only a source line's open quantity, otherwise `quantity_exceeds_open`.
   - **What counts for `document_referenced`** (ADR-0009 rule 7): references from documents that are not canceled or reversed.
   - **Partner snapshot, supplier number.** Documents copy the partner snapshot (ADR-0028 rule 16). Incoming documents carry the supplier's number in `partner_reference`, which also reaches the open item (ADR-0026 rule 1).
   - **Currency.** Invoices, returns and notes of order lines are in the order's currency, otherwise `order_currency_mismatch`.
   - **Closing orders and requests.** An order or request closes automatically (`closed_reason` `fulfilled` on its header) when every line is done by quantity, net of returns and quantity credits: stock lines delivered or received and invoiced, other lines invoiced. A consumer in the owning module runs `Close<Type>` as `system` on the events that complete it, under the document's lock (ADR-0027 rule 10, class 1). `Close` by a person sets `closed_reason` `short`, and cancels the open rest: reservations, and the open quantity of the demand or supply rows. A closed document takes no new deliveries or receipts. Invoices are still accepted up to delivered or received net, and corrections still refer to its lines. This answers ADR-0009 rule 6.

   Note: copy preconditions. `source_lines` may name only a document that is approved or later (approved, issued, posted, or closed), never one in draft, pending approval, rejected or canceled (`source_not_approved`). The pairs: quotation to sales order (within validity, rule 3); sales order to delivery, and to sales invoice for non-stock and service lines (released rows, rule 19); posted delivery to sales invoice and to return from customer; posted or issued sales invoice to sales return, credit note and debit note; purchase request to purchase order; purchase order to goods receipt, service receipt and purchase invoice (released rows); posted goods receipt to return to supplier; posted purchase invoice to purchase return and supplier notes. One `Create<Type>` copies the lines of one source document, deliveries included (pick batches release each document on its own, ADR-0023 rule 16), except that a purchase order may combine several purchase requests, and a sales or purchase invoice may combine deliveries, receipts and order lines of one partner in one currency. The target's partner is the source's.

   Note: copying carries taint. On `Create<Type>` with `source_lines`, and on every `Update` that adds source lines, the new version's `is_tainted` is the OR of the effective taint, at that moment, of every source line's document version; `derived_from_version_id` names the first source document's version, and INV-88 reads the others through the lines' typed references ([ADR-0029](0029-proposals-and-agent-safety.md) rule 8). `inventory`'s stock documents and `production`'s orders created from source lines set it the same way ([ADR-0023](0023-warehouse-management.md) rule 16).

   Note: `service_receipt_line_id` joins the typed line references, for purchase invoice service lines that clear GR/IR against a service receipt (rule 12; [ADR-0037](0037-subcontracting.md) rule 6).

   Note ([ADR-0056](0056-multiple-units-of-measure.md), 2026-11-15): receipts, deliveries, invoices, returns and credits may use any allowed unit of the item; every quantity relation compares inventory quantities. `source_lines` quantities are in the source line's unit, and a copied line takes the source line's unit and snapshot, so a part in the source's unit converts by the cumulative rule (rules 10, 11).

   Note ([ADR-0068](0068-sites-and-core-logistics-payment-master-data.md), 2026-11-21): headers gain `payment_method_id` (quotation, sales order, sales invoice, purchase order, purchase invoice), `delivery_method_id` (sales order, purchase order), and `incoterm_code` with `incoterm_place` (quotation, sales order, delivery, sales invoice, purchase order, goods receipt, purchase invoice). Each is copied from the partner profile at creation and then from the source document, and changeable while the document is a draft or by a change order. Deliveries and goods receipts also carry `delivery_method_id`, `carrier_partner_id` (an active supplier), `tracking_number` and `vehicle_registration`. None of these fields enters pricing, posting or policy.

   Note ([ADR-0069](0069-business-unit-dimension.md), 2026-11-21): every commercial document header carries a nullable `business_unit_id`. Copying fills an empty header from the source, and it can be changed until posting.

    Note ([ADR-0074](0074-core-data-structure-additions.md), 2026-11-21): the partner snapshot also covers the ship-to, bill-to, payer, invoicing-party and payee parties a document names (ADR-0074 rules 1, 2); documents gain a `note` (rule 16) and the headers of ADR-0074 rule 9 gain `custom_values`.

**Sales**

3. `quotation`:
   - **Validity.** `valid_until` (a date). A copy to an order within validity keeps the quotation's prices and discounts. After it, the copy is rejected with `quotation_expired`, unless the client asks to `reprice`; then the lines are priced anew (rule 16).
   - **Closing.** Automatic when every line is fully ordered. A lost quotation is canceled with a reason.
   - **Not demand.** Quotations write no `demand_supply_line` and reserve nothing (ADR-0024 rule 8).

   Note: a quotation holds the sales order's header and lines of rule 4, without demand, reservation or item creation. A line's warehouse is optional; the warehouse checks of an order line ([ADR-0046](0046-product-configuration.md) rule 10 included) run when the line is copied to an order, which requires one. The partner must hold the active `customer` role (ADR-0019 rule 2) at `Create`, `Update` and `Submit`, otherwise `partner_role_missing`.

    Note ([ADR-0074](0074-core-data-structure-additions.md), 2026-11-21): a lost quotation is canceled with a reason of kind `cancel` and a note on the `document` row (`canceled_reason_id`, `canceled_note`, ADR-0074 rule 14); the interim `quotation.cancel_reason` text is gone.
4. `sales_order`:
   - **Header:** customer, currency, price list (from the customer's profile, else the company's default sale list, ADR-0045 rule 5), payment term, salesperson, document discount percentage, requested delivery date.
   - **Lines:** item or configuration, quantity and unit, warehouse, planned delivery date (needed by FEFO, ADR-0023 rule 13), price steps (rule 16), taxes (ADR-0041 rule 6).
   - **Submit.** A policy point with the credit condition (rule 18). Leaving draft creates configured items (rule 1) and demand rows (ADR-0024 rule 8).
   - **Approval.** Each stock line then reserves up to available to promise (ADR-0023 rule 13), and the rest is a backorder. The company setting `sales.reserve_on_approval` (default true, flagged) turns this off. Make-to-order lines reserve production output instead (ADR-0034 rule 14).
5. Deliveries of sales order lines (`delivery`, inventory):
   - **Sources.** Picks (ADR-0023 rule 16), or order lines directly in a warehouse without warehouse tasks.
   - **Quantity.** At most the line's open quantity: `ordered − (delivered − returned)`. More is rejected with `quantity_exceeds_open`. `inventory` reads it from the demand row it owns. Over-delivery is not allowed in Phase 1 (flagged).
   - **Posting.** Movement `sales_issue`, cost of goods sold at delivery. Free goods lines use movement `free_goods_issue` (rule 17).
   - **Credit hold.** Pick release and delivery of a line whose demand row is on hold are rejected with `demand_on_hold` (rule 18).

   Note: returns of closed orders. A `return_from_customer` is accepted against delivery lines of a closed order, within rule 20's limits. It does not reopen the order: the quantity it frees is not deliverable, because a closed order takes no new deliveries, and a replacement is a new order. Rule 7's `sales_return_due` still applies.
6. `sales_invoice`:
   - **Lines.** A stock line refers to a posted delivery line. Its quantity is at most `delivered net − invoiced net` of its order line, otherwise `invoice_exceeds_delivered`. A non-stock or service line refers to an order line, up to its open quantity (`invoice_exceeds_ordered`), or stands alone. Invoicing goods before delivery is not allowed; bill and hold stays the open question it is.
   - **Installments.** The payment term's schedule (ADR-0026 rule 5) is part of the invoice's content, so its due dates and amounts are in the plan. Open items are derived from it at posting and are not in the plan (ADR-0031 rule 1). This settles ADR-0026 rule 3 against ADR-0031 rule 1.
   - **Posting.** Revenue by `revenue_posting` per item group, output tax (ADR-0041), and one receivable control line per installment.
   - **Discounts on the invoice.** The regime setting `sales.discount_presentation` decides: line and document discounts either reduce revenue directly (`net`), or post gross with the discount to `revenue_deduction_trade_discount` (`gross`). Vietnam seeds `net`, `unverified`.
   - **E-invoice.** Issued through the seam of ADR-0028 rules 6–10. The type never waits for approval and is never reversible (ADR-0009 rules 12, 19).

   Note: no stock sale without an order. A delivery line or a sales invoice line of a stock item without a sales order line is rejected with `sales_order_required`: the order comes first, so demand, credit and progress stay uniform, as `purchase_order_required` does for purchases (rule 12). Goods delivered before the cut-over keep rule 8's path.

    Note ([ADR-0074](0074-core-data-structure-additions.md), 2026-11-21): the receivable control line and its open item carry the payer (else the bill-to party, else the sold-to partner); the invoice's tax identity and printed customer are the bill-to party's (ADR-0074 rule 4).
7. Sales returns:
   - **The goods.** `return_from_customer` (inventory) receives returned goods against delivery lines (`correction_of_id`: the delivery; ADR-0027 rule 7). `inventory` checks the quantity against the delivery line, which it owns: returned per delivery line ≤ delivered. The goods go to a `returns` bin as blocked (ADR-0023 rule 19). Their value follows the regime setting for `sales_return_receipt` (ADR-0020 rule 5).
   - **The money.** `sales_return` is the posting correction of ADR-0009 rule 23. `correction_of_id` is the sales invoice, and lines refer to the `return_from_customer` lines they credit. It posts `revenue_deduction_return` and output tax at the original line's price and tax data (ADR-0041 rule 8), and creates a `credit` item, which it may match to the invoice (ADR-0026 rule 9).
   - **When it is due.** A `sales` consumer of the stock return's posted event compares, per order line, invoiced net with delivered net. When invoiced net is the larger, it raises a work item `sales_return_due` for the difference (rule 20). The `sales_return` closes it.
   - **Goods returned before invoicing** need no `sales_return`: they reduce what remains to invoice.

   Note ([ADR-0056](0056-multiple-units-of-measure.md), 2026-11-15): a sales return line that names a return-from-customer line in the same unit and for the same entered quantity takes that line's inventory quantity, so invoiced net and delivered net move together and `sales_return_due` closes exactly (rule 10).
8. `credit_note` and `debit_note` (sales):
   - **Reasons and accounts:**
     - `allowance` → `revenue_deduction_allowance`;
     - `trade_discount` → `revenue_deduction_trade_discount`;
     - `price_correction` and `cancellation` → `revenue_posting` (the invoice's own accounts);
     - a `debit_note` (`price_correction`, `additional_charge`) → `revenue_posting`.

     Returned goods are credited only by `sales_return`.
   - **Original data.** `correction_of_id` is the sales invoice. Lines take the original line's net unit price after the document discount, its taxes, tax date and rate (ADR-0041 rule 8). A quantity credit is `round_amount(quantity × original net unit price after the document discount)`.
   - **Open items.** A credit note creates a `credit` item and may match it to the invoice in the same command (ADR-0026 rule 9).
   - **Invoices from before the cut-over.** A credit note or sales return may name an original that exists only in the old system: `correction_of_id` is empty, and `external_original` holds its number, date, net amounts, tax date and rates. This is allowed only for originals dated before the company's migration cut-over ([ADR-0044](0044-data-migration-and-export.md) rule 13). Rule 20's limits then apply against the entered amounts. Returns of goods delivered before the cut-over come in as `other_receipt` with a reason, since no delivery line exists (flagged). The same applies to supplier documents.

   Note ([ADR-0056](0056-multiple-units-of-measure.md), 2026-11-15): a credit or return line in another unit than its original converts the original's price per inventory unit by its own factor, `round_unit_price(p × d_o / n_o × n / d)`; a credit that completes the invoiced inventory quantity takes exactly the rest of the net amount. The same holds for purchase returns and supplier credits (rule 11).

    Note ([ADR-0074](0074-core-data-structure-additions.md), 2026-11-21): the lines of a return document carry an optional `return_reason_id` (kind `return`); `credit_note.reason` and `debit_note.reason` stay fixed system codes (ADR-0074 rules 14, 15).

**Purchasing**

9. `purchase_request`:
   - **Sources.** People, or the `purchasing` consumer of `ReplenishmentRequested`, as `system` on behalf of the converter ([ADR-0024](0024-planning.md) rule 22). Lines carry item, quantity, requested date, suggested supplier, `origin_planned_order_id`, and `production_order_operation_id` for subcontracted operations (ADR-0037 rule 4).
   - **Open quantity** falls by what is ordered from the line. A request closes automatically when fully ordered.

   Note (flow review, 2026-11-15): for a conversion executed from an approved change proposal (the planning agent's, [ADR-0051](0051-agent-workflows.md) rule 24), the converter is the approving human of [ADR-0029](0029-proposals-and-agent-safety.md) rule 3: the approver whose approval completed the proposal's plan ([ADR-0055](0055-approval-pools-and-stages.md) rule 16 note). The purchase requests are drafted on their behalf, so that person cannot approve them.

   Note (simulation review, 2026-11-15): policy input of a purchase request ([ADR-0043](0043-policy-and-approval.md) rule 4; rule 22). A request carries no price, so for policy only, each line is valued at the first of:
   1. the supplier's purchase price: `find_price` on the purchase list of the line's suggested supplier, else of the item's preferred `supplier_item` supplier (its supplier profile's list, else the company's default purchase list, as on a purchase order), for the line's item, unit, quantity and requested date;
   2. the item's last purchase price: the net unit price of its most recent posted purchase invoice line in the company, converted to the line's unit;
   3. zero, and the request's policy input sets `is_cost_unknown`.

   Amounts are in company currency at the applied rate; the request's amount is the sum of its valued lines. The values live in the policy input and its hash, not on the request. Interim, flagged.
10. `purchase_order`:
    - **Header:** supplier, currency, price list (the supplier's purchase list), payment term, buyer (the supplier profile's default, ADR-0027 rule 6), document discount percentage.
    - **Lines:** item, quantity and unit, receiving warehouse, requested date, price steps (rule 16, without promotions), taxes, `purchase_request_line_id`, and `origin_planned_order_id` and `production_order_operation_id` copied from the request. The supply row gets `ordered_date` at approval (ADR-0024 rule 8).
    - **The GR/IR price.** At approval and at each take-force, `purchasing` pushes each line's GR/IR unit price to `inventory` through `inventory.contract.set_order_line_gr_ir_price`. The price is the line's net amount after the document discount, without tax, divided by its inventory quantity, as an exact rational in the order's currency.
    - **Supply rows from draft** (ADR-0024 rule 8). A draft line whose row carries `origin_planned_order_id` or pegging cannot be removed, nor its draft deleted (`document_line_referenced`). Its quantity is set to zero or the document canceled, which closes the row with `closed_reason` `canceled` (ADR-0024 rule 22). Other draft lines removed by `Update`, or drafts deleted, delete their rows. Rows of documents that have left draft are never deleted. ADR-0024 rule 8 and ADR-0028 rule 2 get notes.

    Note: when the supplier profile names no purchase list, the order takes the company's default purchase list, as a sales order takes the default sale list (rule 4). With neither, or with a list in another currency, the order carries no list and its prices are entered ([ADR-0045](0045-master-data-and-price-lists.md) rule 5 note).
11. Goods receipts of order lines (`goods_receipt`, inventory):
    - **Quantity.** At most the line's open quantity, read from its supply row, times `1 + inventory.purchase_receipt_tolerance_percent / 100` (company setting, default 0). More is rejected with `receipt_exceeds_order`.
    - **Value.** Movement `purchase_receipt` at the GR/IR value of rule 13. The receipt credits GR/IR with `purchase_order_line_id` (ADR-0030 rule 3).

    Note: returns of closed orders. A `return_to_supplier` is accepted against receipt lines of a closed order, within rule 20's limits. It does not reopen the order: a closed line takes no replacement receipt (rule 13's replacement receipt needs an open line), so a replacement is a new order. The GR/IR balance it leaves is cleared as rule 13 says for lines closed short, and rule 15's `supplier_credit_due` still applies.

    Note ([ADR-0056](0056-multiple-units-of-measure.md), 2026-11-15): the tolerance applies to the ordered quantity: received net inventory quantity ≤ the order line's inventory quantity × (1 + tolerance), so partial receipts do not each earn it again (rule 11).
12. `purchase_invoice`:
    - **Header:** supplier, `partner_reference` (the supplier's invoice number; required), `supplier_invoice_date` (the tax date, ADR-0041 rule 7), posting date (DS-19's default), currency and invoice rate (ADR-0011 rule 12), payment term.
    - **Duplicates.** Where the regime declares a natural key for supplier invoices (ADR-0030 rule 10; Vietnam: seller tax ID, form, symbol, number), it applies. Otherwise the fallback key is supplier, `partner_reference` and the year of the supplier's date (flagged). Documents that are canceled or reversed do not count. A second arrival is rejected with `duplicate_external_document`.
    - **Line kinds:**
      - `goods`: refers to a purchase order line. A stock item without an order is rejected with `purchase_order_required`; the buyer creates the order first, so GR/IR stays uniform.
      - `service`: an order line is optional. With a `service_receipt`, it clears GR/IR like goods (ADR-0037 rule 6); without one, it posts to expense.
      - `expense`: no order; the account comes from account determination for the item, or is entered.
      - `landed_cost`: freight, insurance or handling. It posts to `purchase_cost_clearing` and proposes a landed cost (ADR-0021 rule 12); it never touches GR/IR.
    - **Taxes.** The supplier's stated tax per line (ADR-0041 rule 10), and `input_use` on each line.
    - **Posting.** GR/IR debit by rule 13, the price difference as the regime sends it (ADR-0030 rule 4), input tax, and one payable control line per installment.

    Note: for a purchase invoice, the policy input `is_direct_expense` is true when no line references a purchase order line and every line is an expense or service line; it selects the `expense` approval pool ([ADR-0055](0055-approval-pools-and-stages.md) rule 3).

    Note: `expense` lines, and `service` lines without a service receipt, post to the transaction key `purchase_expense` (determinant: item group; required system accounts `expense`, `prepaid_expense` and `construction_in_progress`). A line without an item, or one whose account is entered, takes the entered account, which the command checks against the key (ADR-0015 rules 4, 12). The TT99 template seeds one row, `unverified` ([DS-19](../design/DS-19-vietnam-tt99/README.md)).
13. GR/IR per purchase order line, by unit positions. This details ADR-0030 rule 4:
    - **Positions.** The line's units, in its inventory unit, are positions in order. `R` is the received quantity net of returns, `I` the invoiced quantity net of quantity credits. When a receipt or an invoice first reaches a position, the position is priced at the line's GR/IR price then in force (rule 10). It keeps that price for the life of the line. Prices are stored as layers (from, to, price), exact rationals, in `purchase_order_line_gr_ir_layer`. `V(x)` is the exact value of positions 0 to `x`.
    - **Postings are differences of rounded cumulative values**, in the order's currency:
      - a receipt of `q` credits GR/IR with `round(V(R + q)) − round(V(R))`;
      - an invoice of `q` debits it with `round(V(I + q)) − round(V(I))`; the invoice amount less that is the price difference;
      - a return of `q` debits it with `round(V(R)) − round(V(R − q))`, the latest received positions;
      - a quantity credit of `q` credits it with `round(V(I)) − round(V(I − q))`.

      Rounding is to the currency's minor unit. The balance of the line is therefore always `round(V(I)) − round(V(R))`, and zero whenever `R = I` (INV-37, INV-92).
    - **Reversals.** A document's postings on a line may be reversed only while they are the latest unreversed postings of their side (receipts and returns on `R`; invoices and quantity credits on `I`). The reversal mirrors them exactly. Otherwise `Reverse` is rejected with `reversal_not_latest`, and the correction is a return or a credit. This adds a precondition to ADR-0009 rules 18–19 for goods receipts, service receipts, stock returns and supplier documents with order lines.
    - **Price-only documents.** Supplier credit and debit notes without quantity, and price corrections, never touch GR/IR. Their amount is a price difference and goes as the regime sends `price_difference`.
    - **Consequences.** A return names the receipt lines it returns, but GR/IR moves at the latest positions' value. Stock leaves at the value the regime sets for `purchase_return` (ADR-0020 rule 5). Any difference between that and the GR/IR debit is a price difference, posted on the return. A replacement receipt after a full return posts at the positions' first price. Each receipt line stores its position range, which defines the "matched receipt lines" of ADR-0030 rule 1.
    - **Amendment.** ADR-0030 rule 4 prices a return at "the GR/IR price of the receipt it returns" and a credit note at "the invoice's GR/IR price". With one order price these are the same. After a change order they differ, and only the latest-positions rule keeps INV-37 exact; the lab shows the other rule leaving a residual. It replaces them (a note there).
    - **Ownership.** The layer table, each receipt line's position range, and the interfaces `inventory.contract.set_order_line_gr_ir_price` and `inventory.contract.post_gr_ir_positions` (side, quantity, sign; returning the amount) are `inventory`'s. `purchasing` calls them downward, under the order's document lock (ADR-0027 rule 10, class 1). They belong to the step 3 design (DS-09) and stay empty until step 5 (B3).
    - **Foreign currency.** INV-37 holds in the order's currency. The company-currency residual from different receipt and invoice rates stays with the existing FX open question (ADR-0030 rule 4). Interim, flagged: the posting that makes `R = I` clears the line's company-currency residual to realized exchange difference (`fx_gain_realized`, `fx_loss_realized`).
    - **Lines closed short with `R ≠ I`.** Closing stops receipts, not invoices. A balance left on a closed line is listed by a close checklist task (DS-12) and cleared through the positions, so INV-92 keeps holding: `I > R` by a supplier quantity credit (rule 15); `R > I`, when the supplier will never invoice, by a `gr_ir_write_off` (`purchasing`, internal posting, `human_only`). That document moves `I` up to `R` at the positions' value, debiting GR/IR, and credits the regime's price difference (flagged for the author).

    Note ([ADR-0056](0056-multiple-units-of-measure.md), 2026-11-15): positions count inventory quantities. An invoice's source is always the order line; a receipt or invoice entered in the order line's unit takes its inventory quantity by the cumulative rule; a return or credit takes the part it names as its source, and a purchase return naming a return-to-supplier line in the same unit and entered quantity takes that line's inventory quantity, so R and I move together. When the line is fulfilled within the unit rounding tolerance and R and I still differ, the consequence posting `gr_ir_rounding_clearing` posts on the lagging side at the positions' value, against `price_difference`, with no human step. It also runs on a closed line whose R and I differ by no more than the tolerance. Its positions count in R or I for GR/IR, so INV-92 holds with them; it is the posting that makes R = I for the interim company-currency rule above, and reversing it reverses that entry; it never counts as latest in the latest-only check; and every later GR/IR posting on the line, a `gr_ir_write_off` included, first reverses it as a consequence, after which it fires again if the line is within tolerance. A larger difference stays on the closed-short path (rule 10).

    Note (UoM simulation review, 2026-11-15): the position range a return stores. `return_to_supplier_line.gr_ir_position_from` and `gr_ir_position_to` hold the positions the return actually debits: the order line's latest received positions, from R − q to R, where R is the received net before the return and q the return line's inventory quantity. They are in general not the positions of the receipt it names. The named receipt line, `goods_receipt_line_id`, is stored separately: it is the part reference whose inventory quantity the return mirrors or shares ([ADR-0056](0056-multiple-units-of-measure.md) rule 10, part as source) and the receipt line the return names under **Consequences**. Example: receipts of 2.333, 2.334 and 2.333 kg hold positions 0–2.333, 2.333–4.667 and 4.667–7.000; the return of receipt 2 mirrors that receipt's 2.334 kg and stores positions 4.666–7.000, debiting round(V(7.000)) − round(V(4.666)). With one GR/IR price on the line both ranges have the same value; after a change order they differ, and the stored range is the one that keeps INV-37. Under the interim seed of `purchase_return`, stock leaves at that debit, so the return posts no price difference ([ADR-0020](0020-inventory-and-costing-model.md) rule 5 note). DS-22-09-42 states it on the columns; lab check `t17_uom.py` U70 and U71.

    Note (the author, 2026-11-21): the exchange-rate difference between goods receipt and invoice, the company-currency residual of a line from different receipt and invoice rates, is designed as SAP does (checked against SAP sources, point C2 of the verification section of [reviews/2026-11-21-costing-sap-comparison.md](../reviews/2026-11-21-costing-sap-comparison.md): the decision matches SAP's default; SAP also lets a company keep such differences out of inventory, which the company setting of the chief architect's note below offers). Chief architect's translation (interim, 2026-11-21, until the step that builds it): on a line for an item kept in stock (its receipts post material document lines), the residual is its own difference kind: the posting that clears it debits or credits `purchase_cost_clearing` (the interim key, as for price differences sent to stock) instead of `fx_gain_realized` or `fx_loss_realized`, and calls `inventory.contract.adjust_receipt_value`, which writes a `landed_cost` with `cost_type` `exchange_rate_difference` targeting the line's receipt lines, allocated by value: a `receipt_addition` in that posting's period ([ADR-0021](0021-landed-cost.md) rules 6 and 12 notes; [ADR-0020](0020-inventory-and-costing-model.md) rule 12 note). Lines without stock (services, expenses) keep the interim rule above: realized exchange difference. The difference is measured as the interim rule above says (on the posting that makes R = I). Still to design at the purchase invoice step (DS-22, step 5): measuring it per invoice posting instead of at R = I (the GR/IR positions would then keep the receipt's company-currency amount); confirming the key (`purchase_cost_clearing`, or a transaction key of its own); the `cost_type` value in the `landed_cost_line` DDL and its CHECK; the invoice-first case, where the receipt's rate comes after the invoice's; and returned or written-off quantities.

    Note (chief architect, 2026-11-21; the author's instruction that costing follows SAP): two points of the SAP comparison, settled following SAP as verified (points C2 and A2a of the verification section of [reviews/2026-11-21-costing-sap-comparison.md](../reviews/2026-11-21-costing-sap-comparison.md)).
    - **Exchange-rate difference kept out of stock.** The company setting `costing.exchange_rate_difference_to_stock` (area `inventory`, regime and company option, boolean, core default true, changed only from a period start, in the shape of [ADR-0063](0063-configurable-policy-settings.md) rule 24) chooses the treatment on a line for an item kept in stock. True, the default: the author's note above. False: the residual posts as on a line without stock, to `fx_gain_realized` or `fx_loss_realized`, and stays out of the item's actual cost. The clearing posting reads the value in force on its posting date. The verification does not say which account SAP's alternative posting logic uses; the false path is interim, confirmed with the purchase invoice step (step 5). SAP's other option, treating every rate difference as a price difference through an assumed rate, is not offered.
    - **Planned delivery costs** (interim, details at the purchase invoice step, DS-22, step 5). A purchase order line may carry planned delivery cost conditions: a cost type (the `cost_type` values of [ADR-0021](0021-landed-cost.md) rule 1), an amount for the line, an amount per inventory unit or a percentage of the line's net value, and the freight supplier who will invoice it (the order's supplier when empty). A goods receipt of `q` units adds each condition's planned amount for those units to the receipt line's value, debiting the inventory key with the goods and crediting a delivery-cost clearing key per condition; the amount is a difference of rounded cumulative values over the line's positions, as for GR/IR above, so a fully received line accrues exactly the planned amount, and a return reverses the accrual at the latest positions. The freight supplier's invoice line names the condition and debits the clearing with the accrued amount for the quantity it invoices; the difference between invoiced and accrued is a price difference, handled like the purchase price difference of this rule: as the regime determines `price_difference`, to an account, or to stock through `inventory.contract.adjust_receipt_value` in the invoice's posting period ([ADR-0021](0021-landed-cost.md) rules 6 and 12 notes). Costs with no condition stay the unplanned path of ADR-0021 (`landed_cost`), with the treatment of its rule 12 note. No DDL, transaction key or system account is added now: purchase orders are step 5, a new table then is no migration, and a new transaction key needs a determination row and a chart mapping in every package. What step 5 builds is the planned delivery costs entry under "S2 closure (2026-11-21)" in [open-questions.md](../open-questions.md).
14. Three-way match:
    - **For each goods line**, computed at the invoice's `Submit` and `Post`:
      - quantity: invoiced net may not exceed the ordered quantity times `1 + purchasing.match.quantity_tolerance_percent / 100`; when `purchasing.match.require_receipt` is true, it may not exceed received net either. Otherwise check result `match_quantity_exceeded`;
      - price: the invoice unit price may differ from the order's GR/IR price by at most the larger of `purchasing.match.price_tolerance_percent` of it and `purchasing.match.price_tolerance_amount`. Otherwise `match_price_difference`.
    - **Invoice before receipt** is legitimate by default (ADR-0030 rule 4) and informs with `invoice_before_receipt`. Settings are company settings, defaulting to 0 and false, flagged.
    - **Policy.** A difference sets the new condition `is_match_exceeded` (ADR-0043 rule 3 gets a note), which is part of the invoice's `policy_input` and so of `policy_input_hash`. The seeded rule requires `standard` approval for both `submit` and `post` of a purchase invoice, for every actor kind, when it is true. A mismatched invoice therefore cannot pass by submitting first.

    Note: the order price of the price check is the GR/IR value per unit of the positions the invoice reaches, `(V(I + q) − V(I)) / q`, exact, for an invoice of `q` inventory units at the line's layers (rule 13). It is compared with the invoice line's net amount after the document discount per inventory unit. With one order price this is rule 10's GR/IR price; after a change order it is the price of the very positions the invoice debits, so the tolerance check and the posted price difference agree.

    Note ([ADR-0056](0056-multiple-units-of-measure.md), 2026-11-15): the price check is per inventory unit, as the note says, whatever unit the invoice line is in; `purchasing.match.price_tolerance_amount` is an amount per inventory unit, in the document currency (rule 12).

    Note ([ADR-0065](0065-deterministic-auto-post-gateway.md), 2026-11-21): the purchase invoice checker of the auto-post gateway reads these facts: a line within `auto_post.purchase_invoice.price_tolerance_percent` of the GR/IR price of the positions it reaches, and within `auto_post.purchase_invoice.quantity_tolerance_percent` of the received net (both default 0), is `cross_checked`; any check result of this rule, or `is_match_exceeded`, keeps the invoice for a person ([ADR-0065](0065-deterministic-auto-post-gateway.md) rule 19).
15. Purchase returns:
    - **The goods.** `return_to_supplier` (inventory; `correction_of_id`: the goods receipt) issues them with movement `purchase_return`, debiting GR/IR by rule 13. `inventory` checks returned ≤ received per receipt line.
    - **The money.** `purchase_return` records the supplier's adjustment for returned goods: `correction_of_id` is the purchase invoice, and lines refer to `return_to_supplier` lines. It credits GR/IR by rule 13 as a quantity credit. A `purchasing` consumer raises a work item `supplier_credit_due` when a stock return leaves invoiced net above received net on an order line.
    - **Other supplier credits.** `purchase_credit_note` (`correction_of_id`: the purchase invoice) records the supplier's credit for anything but returned goods. Its quantity lines (goods invoiced but never delivered, or an invoicing error) are quantity credits on `I` by rule 13, within the invoice line's invoiced net (rule 20). Its price lines are price-only. `purchase_debit_note` records the supplier's increase, price-only.

    Note ([ADR-0056](0056-multiple-units-of-measure.md), 2026-11-15): purchase return and supplier credit note lines carry the line unit block, credit note lines also `item_id`. A purchase return line that names a return-to-supplier line in the same unit and for the same entered quantity takes that line's inventory quantity, so the stock return and the supplier's credit move R and I by the same amount (rules 9, 10).

**Pricing**

16. The pricing procedure: `sales.contract.price_line` and `purchasing.contract.price_line`. Each is a pure function of the header (list, currency, document date, partner) and the line (item or configuration values, unit, quantity, manual price, manual discount):
    1. **List price:** `find_price` (ADR-0045 rule 4; [ADR-0046](0046-product-configuration.md) rule 15). The list's currency must equal the document's (`price_list_currency_mismatch`, ADR-0045 rule 5).
    2. **Base price:** the manual price if one is entered (`is_price_manual`), else the list price. A line with neither may not leave draft (`price_required`) unless it is free of charge (rule 17).
    3. **Promotion** (sales only): the one eligible promotion of rule 17.
    4. **Manual discount:** a percentage.
    5. **Net unit price:** the base price after the promotion and then the manual discount, rounded half up to the unit-price scale (ADR-0006) and stored.
    6. **Line amount:** `round_amount(quantity × stored net unit price)` (ADR-0006 rule 18), so the stored values reproduce it.
    7. **Document discount:** a percentage on the header. Its total, `round_amount(Σ line amounts × percentage)`, is allocated to the paid lines in proportion to their amounts, by largest remainder in minor units, with ties to the earlier line. A zero total allocates nothing. Each document that bills or credits lines (an invoice, a credit) applies the percentage to its own lines in the same way. Discount amounts are entered per line, as manual discounts.
    - **Checks at Create and Update:** `price_list_currency_mismatch`, and `tax_inclusive_multiple_codes` for a tax-inclusive list where more than one percent code applies (ADR-0041 rule 9; ADR-0045 rule 5).
    - **The trace.** Each step is a `document_line_price_step` row (step, source table and row, value) in the line's content. It is in the plan and the version hash, and it reproduces the stored net unit price and the line amount (INV-93). Interim, with the open question on trace scope: pricing writes no `derivation_trace` rows; the steps on the line serve Principle 6.
    - **Re-pricing.** A draft line is priced again whenever its item, configuration, unit, quantity or the document date changes, unless its price is manual.
    - **Taxes** are computed by `tax.contract.compute_taxes` on the net amounts after the document discount, with `prices_include_tax` from the list (ADR-0045 rule 5).

    Note: copied prices. A line copied with its price (rules 2–3) is marked `is_price_copied` and keeps the source line's price steps; like a manual price, it is not re-priced when its quantity or the document date changes. A change of its item, configuration or unit, or the client's `reprice`, prices it anew and clears the mark.
17. Promotions (`promotion`; `sales` master data, `master_data_change`, change-tracked, proposal-bound):
    - **Fields:** `code`, `name`, `priority`, dates, optional customer, partner group or price list, scope (an item, a product or an item group), minimum line quantity, and `kind`:
      - `percent` off the base price;
      - `amount_per_unit` off the base price;
      - `free_goods`: a free item and quantity per multiple of the qualifying quantity.
    - **Choice.** At most one promotion per line: the eligible one with the highest priority, then the lowest code. Promotions over a whole order are later (open question).
    - **Free goods** are a generated line: price 0, `is_free_of_charge`, the promotion, and the line it came from. The document discount skips them.
    - **Delivery of free goods.** The flag is copied to the delivery line (a column reserved in the step 3 design). Such lines post movement `free_goods_issue` (new catalog row: out, preliminary price, offset key `free_goods_cost`). The new key `free_goods_cost` has regime alternatives `cost_of_goods_sold` and `selling_expense`, and Vietnam seeds `cost_of_goods_sold`, `unverified`. Their tax treatment is the package's rule, `unverified` (open question).

    Note ([ADR-0056](0056-multiple-units-of-measure.md), 2026-11-15): `minimum_line_quantity`, `qualifying_quantity` and `free_quantity` are inventory-unit quantities; `amount_per_unit` is per inventory unit times the line's factor, rounded once (rule 16).
18. Credit:
    - **Exposure.** `sales.contract.get_credit_exposure(partner)` composes ADR-0030 rule 6's four parts per currency. It converts them to the limit's currency at rate type `transaction` on the check date (ADR-0011 rule 11; flagged). The query `GetCreditExposure` exposes it to people and agents.
    - **At Submit.** The sales order's `Submit` locks as ADR-0030 rule 7 says: classes 1–8, then the partner row (class 9). It reads the exposure with the order included, and passes `is_credit_exceeded` to the policy hook.
    - **Approval is the release.** An order approved while `is_credit_exceeded` was true records that approval as its credit release. It is not held afterwards for the exposure it was approved with.
    - **Holds, set in the same transaction.** Every `sales` command that raises a partner's exposure re-evaluates it under the same locks, and updates holds through `inventory.contract.set_demand_hold`: submit, approval, take-force of a change order, and posting an invoice. Over the limit, it sets `credit_hold` on the open demand rows of the partner's approved orders without a release. Under the limit, it clears them. These row updates take no document lock of the other orders: the hold is a single flag on `inventory`'s rows, set or cleared by a row update that does not conflict with other changes to those orders. A delivery that read no hold just before the hold lands still posts; that race is accepted (flagged). ADR-0027 rule 10 gets a note.
    - **Holds updated by a consumer.** Events that lower exposure (payments and credits through DS-25, cancel and close) are handled by a `sales` consumer, which clears holds. A lowered credit limit (a `master_data` change, which cannot call `sales`) is handled the same way, which leaves a short window before holds land (flagged).
    - **What `inventory` does.** It rejects pick release and delivery of held lines (`demand_on_hold`) and never reads `sales`. `PostDelivery` is no longer `is_policy_in_handler`.
    - **Release.** `ReleaseCreditHold` (a sales order) is `human_only`, with its own permission, a required reason, and segregation from the order's author (ADR-0043 rule 13). Its effect class is `other`. The release lasts until the order's value grows by a change order.
    - **Amendment.** This replaces ADR-0030 rule 7's check at `PostDelivery`, which `inventory` could not compose without reading a higher layer (notes on that rule and on ADR-0030's decision table). EC-21's and EC-63's outcomes stay interim.

    Note: holds generalised to a hold reason. `inventory.contract.set_demand_hold` becomes `inventory.contract.set_demand_supply_hold(rows, reason, is_held)`, with the reasons `not_approved` and `credit_hold`, stored as a set on each demand or supply row. Sales order demand rows and purchase order supply rows are created unreleased (`not_approved`, rule 19). `sales` and `purchasing` release them when the document is approved, or at `Submit` when no approval is required, and set `not_approved` again on `Reject`. `inventory` rejects pick release, delivery and receipt of a row held `not_approved` with `demand_supply_not_released`, and of a row held `credit_hold` with `demand_on_hold`; it still never reads `sales` or `purchasing`.

    Note: when `sales` sets `credit_hold` on an order's rows, it raises one work item `credit_hold` (subject the sales order, owner role `accountant`). The item is resolved by `ReleaseCreditHold`, or by the system when the hold is cleared because the exposure fell under the limit.

    Note (catalog review, 2026-11-15): the stored states of a `credit_hold` row, `held`, `released`, `cleared` and `lapsed` (DS-22-09-42-commercial-inventory.sql), are interim: this rule does not name them.

    Note (simulation review, 2026-11-15): a customer profile without `credit_limit` has no credit check: `is_credit_exceeded` is false and no `credit_hold` is set for that partner; `GetCreditExposure` still reports the exposure. `CreatePartner` leaves the limit empty unless the payload gives one ([ADR-0045](0045-master-data-and-price-lists.md) rule 13 note); a company that wants every customer checked sets a limit on each profile.

    Note ([ADR-0074](0074-core-data-structure-additions.md), 2026-11-21): exposure, the hold and `customer_profile.credit_limit` are those of the payer (else the bill-to party, else the sold-to partner); the demand rows held are those of the orders that resolve to it (ADR-0074 rule 4).

**Demand, supply and progress**

19. Demand and supply rows ([ADR-0024](0024-planning.md) rule 8; ADR-0031 rule 5):
    - **Sales order lines** get demand rows at Submit. Take-force adjusts them. Close or cancel closes them (`closed_reason`).
    - **Purchase request and order lines** get supply rows from draft (rule 10). A request line's open quantity falls as orders are created from it.
    - **Progress.** Delivered and received quantities are read from the rows. Invoiced quantities, including `issuing`, are computed from invoice lines.

    Note: release. Demand rows of sales order lines and supply rows of purchase order lines carry the hold reason `not_approved` until the document is approved (rule 18 note). Unreleased demand rows are not demand: planning, available to promise and reservations ignore them, and `Reject` sets `not_approved` on them again, so a rejected order is never demand and never reserves. Supply rows from draft stay supply for planning (rule 10; ADR-0024 rule 8), released or not, but goods are received against them only once released.

**Corrections and limits**

20. Cumulative limits (ADR-0009 rule 23; INV-40, completed here):
    - **Per delivery or receipt line:** returned ≤ delivered or received (checked by `inventory`).
    - **Per invoice line:** quantity credited (by `sales_return`, `purchase_return` or a quantity credit) ≤ invoiced; amount credited ≤ the line's net amount less earlier credits.
    - **Per order line:** delivered or received net ≤ ordered (with the receipt tolerance); for stock sales order lines, invoiced net ≤ delivered net, except while a `sales_return_due` work item is open; for purchase order lines, invoiced net may exceed received net (invoice before receipt, rule 14, unless `purchasing.match.require_receipt`), and a stock return that leaves it above raises `supplier_credit_due` (rule 15); the quantity credited by returns ≤ the returned quantity not yet credited.

    Violations are rejected with `correction_exceeds_original`. Documents in `issuing` count.
    - **EC-20, interim and flagged:** when a return makes invoiced net exceed delivered net on an order line, a `sales_return` for the difference is due (rule 7). Returned goods that were never invoiced simply reduce what remains to invoice. The author confirms this outcome.

    Note ([ADR-0056](0056-multiple-units-of-measure.md), 2026-11-15): every limit compares inventory quantities and allows the unit rounding tolerance of the source line. It grows by one smallest inventory step per part posted in another unit whose conversion rounded, and by the change each return, credit, reversal or clamped part made to the deviation `P − round(C × f)`; it never shrinks, and with an exact snapshot it stays zero, so every limit is exact (rule 10).

**Posting summary and policy**

21. Postings, by transaction key (ADR-0015):

    | Document | Debit | Credit |
    | --- | --- | --- |
    | Delivery | `cost_of_goods_sold` (free goods: `free_goods_cost`) | inventory |
    | Return from customer | inventory | `cost_of_goods_sold` (regime value) |
    | Sales invoice | `receivable_reconciliation` per installment | `revenue_posting`, `output_tax`; discounts by rule 6 |
    | Sales return | `revenue_deduction_return`, `output_tax` | `receivable_reconciliation` (credit item) |
    | Credit note | by reason (rule 8), `output_tax` | `receivable_reconciliation` (credit item) |
    | Debit note | `receivable_reconciliation` | `revenue_posting`, `output_tax` |
    | Goods receipt | inventory | `gr_ir_clearing` (rule 13) |
    | Purchase invoice, goods | `gr_ir_clearing` (rule 13), price difference (`price_difference` or `purchase_cost_clearing`), `input_tax` | `payable_reconciliation` per installment |
    | Purchase invoice, service with a service receipt | `gr_ir_clearing`, price difference (ADR-0037 rule 6), `input_tax` | `payable_reconciliation` |
    | Purchase invoice, service without one, or expense | expense by determination, `input_tax` | `payable_reconciliation` |
    | Purchase invoice, landed cost | `purchase_cost_clearing`, `input_tax` | `payable_reconciliation` |
    | Return to supplier | `gr_ir_clearing` (rule 13); price difference if the regime's stock value differs | inventory |
    | Purchase return | `payable_reconciliation` | `gr_ir_clearing` (rule 13), price difference, `input_tax` |
    | Supplier credit note | `payable_reconciliation` | `gr_ir_clearing` for quantity lines (rule 13), price difference for price lines, `input_tax` |
    | Supplier debit note | price difference, `input_tax` | `payable_reconciliation` |
    | GR/IR write-off (closed line, `R > I`) | `gr_ir_clearing` (rule 13) | price difference |
    | Release at order close (invoice-first) | `purchase_cost_clearing` | `price_difference` (ADR-0030 rule 4) |

    Note (TT99 example, flow review 2026-11-15; accounts `unverified`, DS-19): a goods line with a price difference. A purchase order line of 100 kg of a raw material at 10,000 VND/kg; the goods receipt of 100 kg posts Dr 152 (`inventory_posting`) 1,000,000 / Cr 33881 (`gr_ir_clearing`) 1,000,000. The supplier invoices 100 kg at 10,500 VND/kg with VAT 10%. GR/IR is debited `round(V(100)) − round(V(0))` = 1,000,000 (rule 13), so the price difference is 50,000. TT99 sends `price_difference` for `raw_material` to 152, an inventory account, so the invoice posts the difference to 33882 (`purchase_cost_clearing`) instead ([ADR-0021](0021-landed-cost.md) rule 12): Dr 33881 1,000,000, Dr 33882 50,000, Dr 1331 (`input_tax`) 105,000 / Cr 331 (`payable_reconciliation`) 1,155,000. In the same transaction `inventory.contract.adjust_receipt_value` writes a `landed_cost` with `cost_type` `price_difference`, `posted`, targeting the receipt line ([ADR-0030](0030-commercial-seams-and-imports.md) rule 1): with the receipt's period open, Dr 152 50,000 / Cr 33882 50,000, so the receipt is valued at 1,050,000 and 33882 is back to zero. If the receipt's period is closed, the same 50,000 leaves 33882 split between the stock still on hand (152) and the consumers that took the goods (method `consumer_split`, ADR-0021 rules 6–7). A regime that sends `price_difference` to an expense account (the TT99 alternative 6324) posts the 50,000 there on the invoice, with no landed cost.

    Note ([ADR-0056](0056-multiple-units-of-measure.md), 2026-11-15): `gr_ir_rounding_clearing` posts GR/IR against `price_difference` at the positions' value, as a consequence posting (rule 10).

    Note (the author, 2026-11-21): in the TT99 example above, when the receipt's period is closed the 50,000 no longer splits between stock and consumers: it posts Dr 152 / Cr 33882 as a `receipt_addition` in the invoice's period and enters that period's average ([ADR-0021](0021-landed-cost.md) rule 6 note).
22. Policy input of each type ([ADR-0043](0043-policy-and-approval.md) rule 4):
    - **Amount:** document total in company currency at the applied rate.
    - **`discount_percent`:** (Σ quantity × list price − net amount after the document discount) ÷ Σ quantity × list price. Lines without a list price count at their base price; free goods count at their list price.
    - **`margin_percent`:** (net amount − cost) ÷ net amount, in company currency, with the cost of free goods included. Cost per inventory unit is the preliminary price in the line's valuation area (ADR-0020 rule 11), or the configuration estimate ([ADR-0046](0046-product-configuration.md) rule 14). An unknown cost leaves margin unknown, and the decision needs a human.
    - **`is_price_below_cost`:** a paid line's net amount after the document discount, per inventory unit in company currency, is below its cost. Free goods do not count.
    - **`is_price_outside_list`:** a line's base price differs from its list price, or it has none.
    - **`is_credit_exceeded`** (sales orders) and **`is_match_exceeded`** (purchase invoices).
    - **Fields.** Cost and margin on documents are field classes `cost` and `margin` (ADR-0017 rule 10).

    Note: `is_price_below_cost` compares a paid line's net amount after the document-discount allocation (rule 16, step 7), divided by its inventory quantity and converted to company currency at the applied rate, with its cost per inventory unit; free goods are excluded. This is the one definition; [ADR-0045](0045-master-data-and-price-lists.md) rule 5's "net unit price" gives way to it.

    Note: `is_cost_unknown` is true when a paid line's cost per inventory unit is unknown: no preliminary price and, for a line without an item or preliminary price, no computable configuration estimate ([ADR-0046](0046-product-configuration.md) rule 14). `margin_percent` is then unknown and the line does not count as below cost, so rules on margin and below cost do not match; the seeded rule on `is_cost_unknown` requires approval instead ([ADR-0043](0043-policy-and-approval.md) rules 3, 15).

    Note (flow review, 2026-11-15): quotations have no credit condition. `is_credit_exceeded` belongs to the sales order's policy input only (rules 4, 18): a quotation creates no demand, reservation or exposure (rule 3). The quotation agent's `GetCreditExposure` finding is information in its note ([ADR-0051](0051-agent-workflows.md) rule 15 note); credit is checked when the order is submitted.

    Note (author's delegation, 2026-11-19): rules 18, 20 and 22 are confirmed as written: EC-20 raises a sales return work item for the invoiced share; EC-21 and EC-63 need approval at Submit, with the other unreleased orders held; EC-22 follows the company's policy rules on `is_price_below_cost`.

**Catalogs**

23. Catalog rows:
    - **Document type:** `gr_ir_write_off` (rule 13).
    - **Errors:** `quotation_expired`, `quantity_exceeds_open`, `invoice_exceeds_delivered`, `invoice_exceeds_ordered`, `receipt_exceeds_order`, `purchase_order_required`, `price_required`, `correction_exceeds_original`, `demand_on_hold`, `order_currency_mismatch`, `reversal_not_latest`.
    - **Check results:** `match_quantity_exceeded`, `match_price_difference`, `invoice_before_receipt`.
    - **Work item kinds:** `sales_return_due` (`sales`), `supplier_credit_due` (`purchasing`).
    - **Movement type and key:** `free_goods_issue`; `free_goods_cost`.
    - **Settings:**
      - company: `sales.reserve_on_approval`, `inventory.purchase_receipt_tolerance_percent`, `purchasing.match.quantity_tolerance_percent`, `purchasing.match.price_tolerance_percent`, `purchasing.match.price_tolerance_amount`, `purchasing.match.require_receipt`;
      - regime, which Vietnam seeds `unverified`: `sales.discount_presentation`, and the alternatives of `free_goods_cost`.
    - **Invariants**, all first at step 5:
      - **INV-40** completed: rule 20's limits;
      - **INV-90:** per sales order line, delivered net ≤ ordered;
      - **INV-91:** per stock sales order line, invoiced net ≤ delivered net, or an open `sales_return_due` work item names the line;
      - **INV-92:** per purchase order line, the GR/IR balance in the order's currency equals `round(V(I)) − round(V(R))` at the line's layers (rule 13);
      - **INV-93:** every line's price steps reproduce its stored net unit price and line amount.
    - **Edge cases:**
      - EC-20, EC-21, EC-22 and EC-63 get interim outcomes (rules 18, 20, 22), flagged for the author;
      - new: a change order that changes a purchase price between two receipts and an invoice; a promotion with free goods and a document discount; an invoice within the price tolerance and one beyond it.

    Note: further rows: errors `demand_supply_not_released`, `sales_order_required`, `source_not_approved` and `partner_role_missing` (rules 2, 3, 6, 18); check result `price_list_currency_differs` ([ADR-0045](0045-master-data-and-price-lists.md) rule 5); work item kind `credit_hold` (`sales`, rule 18); transaction key `purchase_expense` (rule 12); policy condition `is_cost_unknown` (rule 22); company settings `master_data.default_partner_group.customer`, `master_data.default_partner_group.supplier` and `master_data.default_partner_group.employee` ([ADR-0045](0045-master-data-and-price-lists.md) rule 13).

    Note (catalog review, 2026-11-15): the three new edge cases are EC-69 (a purchase price change between two receipts), EC-70 (free goods with a document discount) and EC-71 (purchase invoices within and beyond the price tolerance); [edge-cases.csv](../catalogs/edge-cases.csv) is authoritative.
24. Lab check `t07_commercial.py` ([validation lab](../reviews/2026-11-14-design-validation/README.md)), pure functions:
    - GR/IR on 600 random sequences of receipts, invoices, returns, credits, reversals and change orders, with rounding to 0 and 2 decimals: the balance equals `round(V(I)) − round(V(R))` after every step, and is zero whenever received equals invoiced; reversals of non-latest postings are refused;
    - fixed GR/IR cases, including thirds of a unit, invoice first, a return after a change order, and the residual the receipt-price rule would leave;
    - the pricing procedure with stored prices, the document discount allocation, free goods, and the policy inputs after the document discount;
    - correction limits and EC-20; three-way match tolerances; credit exposure, holds and the release by approval.

    Not covered: tables, locks and consumers; foreign-currency residuals; tax.

## Context

ADR-0045 left pricing as a whole to DS-22, and some twenty accepted ADRs hand DS-22 something: document types and flags, line references, GR/IR at order price, credit checks, corrections, tax and configuration. The reference systems inform the choices:
- **SAP SD/MM:** a condition technique for pricing, GR/IR clearing with price differences, credit management with blocked deliveries, and returns deliveries followed by credit memos.
- **D365:** trade agreements, discounts and charges; three-way matching policies with tolerances; credit holds.
- **Odoo:** pricelists with rules, promotions as programs, invoices from deliveries or orders.

NativeFlows keeps the shapes people expect: an order, then stock, then money. It keeps one pure pricing function with its steps on the line, and enforces the subtle parts (GR/IR, corrections, credit) by invariants the lab checks. The first review of this ADR found that GR/IR was exact only without rounding and without reversals. It also found that return documents had been redefined against ADR-0009 and ADR-0027, and that a mismatched invoice could pass by submitting first. The rounded cumulative postings, the latest-only reversals, the accepted definitions of returns and the seed on both actions fix these.

## Options considered

| Option | For | Against |
| --- | --- | --- |
| GR/IR by unit positions with rounded cumulative postings (chosen) | INV-37 exact under change orders, rounding and reversals; no clearing step | Returns move GR/IR at the latest positions' value, not their own receipt's |
| GR/IR return at the returned receipt's own price (ADR-0030 as written) | Matches the receipt | Leaves residuals after price changes |
| Reversal only of the latest posting of a side (chosen) | Mirrors stay exact | An older document is corrected by a return or a credit |
| Credit hold on demand rows, set by `sales` in its own commands (chosen) | Layers intact; deliveries blocked deterministically for exposure that `sales` raises | A lowered limit reaches holds through a consumer |
| Credit check inside `PostDelivery` (ADR-0030 rule 7) | One place | `inventory` would read `sales` |
| Pricing steps stored on the line (chosen) | Explainable, in the plan, no extra table | Not a generic derivation trace |
| Condition technique (SAP) | Very flexible | A rule engine before it is needed |
| One promotion per line by priority (chosen) | Deterministic and explainable | No stacking; order-level promotions later |
| Stock goods always through an order (chosen) | Uniform GR/IR and three-way match | A quick order for unplanned buys |
| Returns as stock document plus posting correction (chosen) | Keeps ADR-0009 and ADR-0027; each owner posts its own effect | No separate return authorization in Phase 1 |

## Constraints that come with the decision

- **ADR notes:**
  - ADR-0030 rule 4: positions, rounded postings and latest-only reversals (rule 13); rule 7 and the decision table: the delivery check becomes a hold (rule 18);
  - ADR-0024 rule 8 and ADR-0028 rule 2: supply rows of draft lines (rule 10);
  - ADR-0009 rules 6, 7, 18, 23: automatic closing; references that count; the reversal precondition; corrections of originals from before the cut-over;
  - ADR-0027 rule 10: hold updates on other orders' demand rows take no document lock (rule 18);
  - ADR-0043 rule 3: condition `is_match_exceeded`; rule 15: the seeded purchase invoice rule on `submit` and `post`;
  - ADR-0045 rule 16 and ADR-0046 rule 11: `is_item_creating`;
  - ADR-0026 rule 3: the installment schedule is content (rule 6);
  - ADR-0027 rule 4: pricing steps on the line, interim.
- **DS-04:** the errors and check results of rule 23.
- **Catalogs:** INV-40 completed and INV-90 to INV-93; the edge cases; `sales_return_due` and `supplier_credit_due` in [work-item-kinds.csv](../catalogs/work-item-kinds.csv); `free_goods_issue` in [movement-types.csv](../catalogs/movement-types.csv); `free_goods_cost` in [transaction-keys.csv](../catalogs/transaction-keys.csv), with the TT99 determination row (6321, `unverified`) in [DS-19-vietnam-tt99](../design/DS-19-vietnam-tt99/README.md).
- **Other design items:**
  - DS-09: `inventory.contract.set_demand_hold`, `set_order_line_gr_ir_price` and `post_gr_ir_positions`; `purchase_order_line_gr_ir_layer` and receipt position ranges; the free-of-charge column on delivery lines; the reversal precondition on stock documents; the receipt tolerance setting;
  - DS-12: a close task listing GR/IR balances on closed order lines;
  - DS-17: step 5 payload tables, events for returns, notes and promotions, and the new edge cases;
  - DS-19: the regime settings and the `free_goods_cost` alternatives;
  - DS-25: payments and credits lowering exposure; early-payment discounts;
  - DS-27: print contracts of these documents;
  - DS-30: the six entry screens.
- **Open questions:** listed in [open-questions.md](../open-questions.md) under DS-22.

## Revisit when

- Pricing needs condition records, rebates or order-level promotions.
- Bill and hold, consignment or drop shipment enter scope.
- A regime requires a dedicated replacement invoice or a return authorization.

## Documents updated

- **The lab:** [docs/reviews/2026-11-14-design-validation/](../reviews/2026-11-14-design-validation/README.md): `lab/t07_commercial.py`, finding L-15.
- **ADRs:** notes in ADR-0009, ADR-0024, ADR-0026, ADR-0027 (rules 4, 10), ADR-0028, ADR-0030, ADR-0043, ADR-0045 and ADR-0046.
- **Design files:** [docs/design/DS-04-command-envelope.md](../design/DS-04-command-envelope.md), [docs/design/DS-17-synthetic-dataset.md](../design/DS-17-synthetic-dataset.md), [docs/design/backlog.md](../design/backlog.md).
- **Catalogs:** [invariants.csv](../catalogs/invariants.csv), [edge-cases.csv](../catalogs/edge-cases.csv), [work-item-kinds.csv](../catalogs/work-item-kinds.csv), [movement-types.csv](../catalogs/movement-types.csv), [transaction-keys.csv](../catalogs/transaction-keys.csv).
- **Glossary:** [docs/spec/00-reading-guide.md](../spec/00-reading-guide.md).
- **Open questions:** [docs/open-questions.md](../open-questions.md).
- **Index and log:** [docs/adr/README.md](README.md); [docs/runbook/step-log.md](../runbook/step-log.md) at acceptance.
