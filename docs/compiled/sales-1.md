Module: sales    Chunk: 1 of 2    Source ADRs: ADR-0030, ADR-0046, ADR-0047
Build step(s): 3, 5    Generated from index: 30d5706    Compiled by: Claude Fable 5.2, 2026-11-21

# `sales` compiled spec, chunk 1: document types, lines and copying, sales documents, pricing, promotions

## Purpose

`sales` owns the commercial documents of the selling side: `quotation`, `sales_order`, `sales_invoice`, `sales_return`, `credit_note` and `debit_note`, the `promotion` master data, the pricing procedure `sales.contract.price_line` and the credit exposure. It does not own stock documents (`inventory`), the journal and open items (`ledger`), tax computation (`tax`) or price lists (`master_data`); it posts through their contracts. This chunk states the credit exposure and its check point, the document types and their registry flags, lines, references and copying, configurations on documents, each sales document, the pricing procedure and promotions. Credit holds, demand and supply rows, the cumulative limits, postings by transaction key, policy inputs, the catalog rows of ADR-0047, inquiry attachments and document parties are in chunk 2.

## Entities and tables

DDL: `docs/design/DS-22-09-42-commercial-inventory.sql`.

| Table | Meaning | Key | Parent | Owner |
| --- | --- | --- | --- | --- |
| `quotation` | Header of a quotation (R21, R22). The DDL column `contact_id` is marked interim: ADR-0047 does not state it | `id`; (`company_id`, `id`) | `document` | `sales` |
| `quotation_line` | Line of a quotation, with its price steps stored (R22, R37) | `id`; (`quotation_id`, `line_number`) unique | `quotation` | `sales` |
| `sales_order` | Header of a sales order (R23). The DDL column `contact_id` is marked interim: ADR-0047 does not state it | `id`; (`company_id`, `id`) | `document` | `sales` |
| `sales_order_line` | Line of a sales order (R23) | `id`; (`sales_order_id`, `line_number`) unique | `sales_order` | `sales` |
| `sales_invoice` | Header of a sales invoice (R25-R29) | `id`; (`company_id`, `id`) | `document` | `sales` |
| `sales_invoice_line` | Line of a sales invoice (R25) | `id`; (`sales_invoice_id`, `line_number`) unique | `sales_invoice` | `sales` |
| `sales_return` | Header of the posting correction that credits returned goods (R31) | `id`; (`company_id`, `id`) | `document` | `sales` |
| `sales_return_line` | Line of a sales return, naming its `return_from_customer` line (R31) | `id`; (`sales_return_id`, `line_number`) unique | `sales_return` | `sales` |
| `credit_note` | Header of a sales credit note, with its `reason` (R33) | `id`; (`company_id`, `id`) | `document` | `sales` |
| `credit_note_line` | Line of a credit note (R34) | `id`; (`credit_note_id`, `line_number`) unique | `credit_note` | `sales` |
| `debit_note` | Header of a sales debit note, with its `reason` (R33) | `id`; (`company_id`, `id`) | `document` | `sales` |
| `debit_note_line` | Line of a debit note (R34) | `id`; (`debit_note_id`, `line_number`) unique | `debit_note` | `sales` |
| `promotion` | Promotion master data (R41) | `id`; (`company_id`, `code`) unique | `company` | `sales` |

Reads: `document`, `document_version`, `document_line_price_step`, `document_line_custom_text` (`documents`); `delivery_line`, `return_from_customer_line`, `demand_supply_line` (`inventory`); `partner`, `customer_profile`, `price_list`, `item`, `product`, `product_configuration`, `item_group`, `partner_group`, `warehouse`, `reason`, `payment_method`, `delivery_method`, `incoterm`, `business_unit` (`master_data`); `open_item`, `payment_term` (`ledger`).

## Commands and queries

The commands of each type are the generated verbs of ADR-0009.R2. Authorization: the document type leaf of the same name under the area `sales` (`authorization-areas.csv`: `quotation`, `sales_order`, `sales_invoice`, `sales_return`, `credit_note`, `debit_note`), at the level of the verb (`authorization-verb-levels.csv`: `Create`, `Update`, `Submit`, `Cancel` at `edit`; `Close`, `Post`, `Issue` at `post`).

| Name | Actor and authorization | Input | Effect | Events | Error codes |
| --- | --- | --- | --- | --- | --- |
| `Create<Type>` of the types above | leaf of the type, `edit` | header, lines, optional `source_lines`; `correction_of_id` or `external_original` for correction types; `reprice` on a copy of a quotation | Creates the draft; copies source lines (R13, R14) | not stated | `quantity_exceeds_open`, `source_not_approved`, `order_currency_mismatch`, `quotation_expired`, `configuration_invalid`, `partner_role_missing`, `price_list_currency_mismatch`, `tax_inclusive_multiple_codes`, `sales_order_required`, `invoice_exceeds_delivered`, `invoice_exceeds_ordered` |
| `Update` of a type | leaf of the type, `edit` | changed header or lines, added source lines | Changes the draft and prices it again (R40) | not stated | `partner_role_missing`, `price_list_currency_mismatch`, `tax_inclusive_multiple_codes` |
| `Submit` of a type | leaf of the type, `edit` | not stated | The document leaves draft; for `sales_order` a policy point with the credit condition (R3, R24) | not stated | `configuration_incomplete`, `configuration_warehouse_not_produced`, `price_required`, `partner_role_missing` |
| `Cancel` of `quotation` | leaf `quotation`, `edit` | reason of kind `cancel`, note | Cancels a lost quotation (R21) | not stated | not stated |
| `Close<Type>` of `quotation`, `sales_order` | `system` on the completing events, or a person; leaf of the type, `post` | not stated | Sets `closed_reason` (R17, R21) | not stated | not stated |
| `Post` and `Issue` of `sales_return`, `credit_note`, `debit_note` | `human_only`; leaf of the type, `post` | not stated | Posts the correction (R7, R31, R33) | not stated | not stated |

Contract function, not a registry command: `sales.contract.price_line` (R37). A change order that alters a line's configuration returns `configuration_in_production` (R20).

## Rules

### Layer and flows

R1. The commercial documents are a thin layer over the core (B3). They hold what was agreed with a partner, price it with one procedure, and post through the core contracts: stock through `inventory`, money through `ledger`, taxes through `tax`. Everything a document does is visible in its plan. Sales runs quotation, sales order, delivery (`inventory`), sales invoice; a return is a stock return from the customer (`inventory`) and, for goods already invoiced, a `sales_return` that credits them; other changes to an invoice are a `credit_note` or a `debit_note`. Purchasing runs purchase request, purchase order, goods receipt (`inventory`), purchase invoice; a return is a stock return to the supplier (`inventory`) and, for goods already invoiced, a `purchase_return` that records the supplier's credit. These keep the definitions of ADR-0009.R23 and ADR-0027.R7.
Source: ADR-0047.D0

### Credit exposure and its check point

R2. Credit exposure (`credit_exposure`) is kept per payer (else bill-to party, else sold-to partner) and currency. It is the sum, under the payer each document resolves to (ADR-0074.R4), of:
- open receivable items (`GetPartnerExposure`, ADR-0026.R15);
- invoices in `issuing`, which have no open items yet (ADR-0028.R9);
- delivered but not invoiced value;
- the undelivered value of orders in `pending_approval` or `approved`.
DS-22 composes it. It differs from partner exposure (ADR-0026), which is the ledger part alone.
Source: ADR-0030.R6, .N1

R3. Credit excess is a condition of the policy evaluation, with a seeded rule requiring approval (ADR-0043.R4, ADR-0043.R15). The check runs at the sales order's `Submit`, a policy point (ADR-0029.R6). The handler locks classes 1–8 of ADR-0027.R10, then the partner row (class 9), then reads the exposure. It passes the result to the policy hook through `context.evaluate_policy(input)`, the dispatcher's one hook (ADR-0029.R6), called at that point so that inputs read under locks are current. Such commands are registered `is_policy_in_handler` (ADR-0008.R1); for them the dispatcher skips its own evaluation and asserts that the hook ran exactly once. Concurrent orders of one partner therefore see each other's exposure (`EC-63`). No policy check runs at `PostDelivery`, which is not `is_policy_in_handler`: goods leaving are governed by a credit hold on demand rows, set by `sales` in the commands that raise exposure and respected by `inventory` at pick release and delivery (`demand_on_hold`; ADR-0047.R18). When the limit is exceeded, the order needs approval at `Submit` and the other unreleased orders are held (`EC-21`; ADR-0047.R18, confirmed by ADR-0047.R22.N4).
Source: ADR-0030.R7, ADR-0047.R18

### Document types and registry flags

R4. Document types (ADR-0009.R2, ADR-0009.R3) and their registry flags. Each entry gives: module; posting; change orders; e-invoice capable; approval hold allowed; reversible; `is_item_creating`; demand and supply.
- `quotation`: `sales`; not posting; no change orders; not e-invoice capable; approval hold allowed; reversibility does not apply; not item-creating; no demand or supply.
- `sales_order`: `sales`; not posting; change orders; not e-invoice capable; approval hold allowed; reversibility does not apply; item-creating; demand, after draft.
- `sales_invoice`: `sales`; posting; no change orders; e-invoice capable; approval hold derived from the regime setting `documents.issuance_without_delay` (no approval hold while it is true; core default false; ADR-0053.R8); not reversible; not item-creating.
- `sales_return`, `credit_note`, `debit_note`: `sales`; posting; no change orders; e-invoice capable; approval hold derived from `documents.issuance_without_delay` as for `sales_invoice`; not reversible; not item-creating.
- `purchase_request`: `purchasing`; not posting; no change orders; not e-invoice capable; approval hold allowed; reversibility does not apply; not item-creating; supply, from draft.
- `purchase_order`: `purchasing`; not posting; change orders; not e-invoice capable; approval hold allowed; reversibility does not apply; not item-creating; supply, from draft.
- `purchase_invoice`: `purchasing`; posting; no change orders; not e-invoice capable; approval hold allowed; reversible, latest only (ADR-0047.R13); not item-creating.
- `purchase_return`, `purchase_credit_note`, `purchase_debit_note`: `purchasing`; posting; no change orders; not e-invoice capable; approval hold allowed; reversible, latest only (ADR-0047.R13); not item-creating.
- `gr_ir_write_off`: `purchasing`; posting; no change orders; not e-invoice capable; approval hold allowed; reversible, latest only (ADR-0047.R13); not item-creating.
- `service_receipt` (ADR-0037.R5): `purchasing`; posting; no change orders; not e-invoice capable; no approval hold; reversible while no invoice refers to it (ADR-0047.R13); not item-creating.
The value a regime gives `documents.issuance_without_delay` is flagged content of the localization package (`l10n_vn`).
Source: ADR-0047.R1, .N1, .N3

R5. The stock documents (`goods_receipt`, `delivery`, `return_to_supplier`, `return_from_customer`) stay `inventory`'s, with their flags set by DS-09 (ADR-0027.R13). Their reversal of order lines is limited by ADR-0047.R13. From step 5 their lines carry the order line references reserved at step 3 (ADR-0027.R7). Customs declarations and amendments keep the flags ADR-0021.R10 and ADR-0021.R11 give them, and service receipts those of ADR-0037.R5. A service receipt's reversal is also limited by ADR-0047.R13.
Source: ADR-0047.R1

R6. `is_item_creating` is a registry flag. Only types with it create items on order when they leave draft (ADR-0045.R16, ADR-0046.R11): `sales_order`, and `production_order` by ADR-0046. Quotations never create items.
Source: ADR-0047.R1

R7. `sales_return`, `credit_note` and `debit_note` are the adjustment documents of sales invoices (spec 08). Corrections stay correction documents; Phase 1 models a replacement as a full `credit_note` plus a new invoice. The adjustment and replacement invoice forms are the localization package's (`l10n_vn`) and the e-invoice add-on's (ADR-0053.R14); whether a regime requires a single replacement invoice, and the form of returns, is decided by its localization package and is unverified, for the author to verify; a dedicated type would be the e-invoice add-on's (DS-24). `Post` or `Issue` of every correction type of R4 is `human_only` (ADR-0009.R23, interim). Kits (bill of materials usage `kit`, ADR-0033.R3) come after Phase 1 (open question).
Source: ADR-0047.R1, .N1

R8. Every type of R4, and the stock documents, are `is_printable` and carry the optional header field `print_language` (ADR-0049.R25, ADR-0049.R27).
Source: ADR-0047.R1.N2

R9. Document type `gr_ir_rounding_clearing` (ADR-0056): `purchasing`, posting, no change orders, not e-invoice capable, no approval hold, reversed only as a consequence (never by `Reverse`), not item-creating, no demand or supply. Its `Post` is `is_internal_only` and `is_consequence_posting`; its authorization leaf is under purchasing at level `full`, in no template's expansion. It has its own `document` row and no header or line table: its `purchase_order_line_gr_ir_posting` row of kind `rounding_clearing` carries the line, positions and amount (ADR-0056.R10).
Source: ADR-0047.R1.N4

### Lines, references and copying

R10. Lines store the entered quantity and unit and the inventory quantity (ADR-0018.R11). GR/IR positions, correction limits and progress use inventory quantities. Receipts, deliveries, invoices, returns and credits may use any allowed unit of the item; every quantity relation compares inventory quantities (ADR-0056).
Source: ADR-0047.R2, .N4

R11. Line references use the typed keys of ADR-0028.R2: `quotation_line_id`, `sales_order_line_id`, `delivery_line_id`, `return_from_customer_line_id`, `purchase_request_line_id`, `purchase_order_line_id`, `goods_receipt_line_id`, `return_to_supplier_line_id`, and `correction_of_line_id` on correction lines. `service_receipt_line_id` joins them, for purchase invoice service lines that clear GR/IR against a service receipt (ADR-0047.R12, ADR-0037.R6).
Source: ADR-0047.R2, .N3

R12. Lines carry their `product_configuration`, custom text in `document_line_custom_text`, and the checks of ADR-0046.R9 and ADR-0046.R10 (R20; completeness, the warehouse of configurable lines, re-evaluation when copied to a new document).
Source: ADR-0047.R2

R13. `Create<Type>` accepts `source_lines` (a source document's line numbers and quantities). The handler copies the lines with their references, prices, discounts, taxes and configuration, and sets `derived_from_version_id` (ADR-0029.R8). It copies only a source line's open quantity, otherwise `quantity_exceeds_open`. `source_lines` quantities are in the source line's unit, and a copied line takes the source line's unit and snapshot, so a part in the source's unit converts by the cumulative rule (ADR-0056.R10, ADR-0056.R11).
Source: ADR-0047.R2, .N4

R14. Copy preconditions. `source_lines` may name only a document that is approved or later (approved, issued, posted, or closed), never one in draft, pending approval, rejected or canceled (`source_not_approved`). The pairs:
- quotation to sales order (within validity, R21);
- sales order to delivery, and to sales invoice for non-stock and service lines (released rows, ADR-0047.R19);
- posted delivery to sales invoice and to return from customer;
- posted or issued sales invoice to sales return, credit note and debit note;
- purchase request to purchase order;
- purchase order to goods receipt, service receipt and purchase invoice (released rows);
- posted goods receipt to return to supplier;
- posted purchase invoice to purchase return and supplier notes.
One `Create<Type>` copies the lines of one source document, deliveries included (pick batches release each document on its own, ADR-0023.R16), except that a purchase order may combine several purchase requests, and a sales or purchase invoice may combine deliveries, receipts and order lines of one partner in one currency. The target's partner is the source's.
Source: ADR-0047.R2.N1

R15. Copying carries taint. On `Create<Type>` with `source_lines`, and on every `Update` that adds source lines, the new version's `is_tainted` is the OR of the effective taint, at that moment, of every source line's document version; `derived_from_version_id` names the first source document's version, and `INV-88` reads the others through the lines' typed references (ADR-0029.R8). `inventory`'s stock documents and `production`'s orders created from source lines set it the same way (ADR-0023.R16).
Source: ADR-0047.R2.N2

R16. What counts for `document_referenced` (ADR-0009.R7): references from documents that are not canceled or reversed. Documents copy the partner snapshot (ADR-0028.R16); it also covers the ship-to, bill-to, payer, invoicing-party and payee parties a document names (ADR-0074.R1, ADR-0074.R2). Incoming documents carry the supplier's number in `partner_reference`, which also reaches the open item (ADR-0026.R1). Invoices, returns and notes of order lines are in the order's currency, otherwise `order_currency_mismatch`.
Source: ADR-0047.R2, .N7

R17. Closing orders and requests. An order or request closes automatically (`closed_reason` `fulfilled` on its header) when every line is done by quantity, net of returns and quantity credits: stock lines delivered or received and invoiced, other lines invoiced. A consumer in the owning module runs `Close<Type>` as `system` on the events that complete it, under the document's lock (ADR-0027.R10, class 1). `Close` by a person sets `closed_reason` `short`, and cancels the open rest: reservations, and the open quantity of the demand or supply rows. A closed document takes no new deliveries or receipts. Invoices are still accepted up to delivered or received net, and corrections still refer to its lines. This answers ADR-0009.R6.
Source: ADR-0047.R2

R18. Headers carry `payment_method_id` (quotation, sales order, sales invoice, purchase order, purchase invoice), `delivery_method_id` (sales order, purchase order), and `incoterm_code` with `incoterm_place` (quotation, sales order, delivery, sales invoice, purchase order, goods receipt, purchase invoice). Each is copied from the partner profile at creation and then from the source document, and changeable while the document is a draft or by a change order. Deliveries and goods receipts also carry `delivery_method_id`, `carrier_partner_id` (an active supplier), `tracking_number` and `vehicle_registration`. None of these fields enters pricing, posting or policy (ADR-0068).
Source: ADR-0047.R2.N5

R19. Every commercial document header carries a nullable `business_unit_id`; copying fills an empty header from the source, and it can be changed until posting (ADR-0069). Documents carry a `note` (ADR-0074.R16), and the headers of ADR-0074.R9 carry `custom_values`.
Source: ADR-0047.R2.N6, ADR-0047.R2.N7

### Configurations on documents

R20. Configurations on documents:
- Leaving draft. A line of a configurable product may leave draft only with a complete configuration (`configuration_incomplete`, listing the missing characteristics and the violations).
- Warehouse. The line's warehouse must be the production warehouse of one of the product's product-level versions (`configuration_warehouse_not_produced`), so make-to-order supply and reservation meet it (ADR-0034.R14). Transfers of configured units are later.
- Copying. Copying a line to a new document (quotation to order, order to delivery) evaluates the configuration under the model revision valid on the new document's date. If it is no longer valid, the copy is rejected with `configuration_invalid` and the violations, and the user reconfigures. An existing document keeps its configuration.
- Downstream copies. Deliveries, returns, credit notes and production orders copy the configuration from their source line without re-evaluation.
- Production orders without a sales line carry the configuration entered on them; their line options are information.
- Change orders (ADR-0028.R4). A change that alters a line's configuration is rejected with `configuration_in_production` while any production order linked to that line is open (not closed or cancelled). Planned orders need nothing: the next planning run replans them for the new item.
Source: ADR-0046.R10

### `quotation`

R21. A `quotation` has `valid_until` (a date). A copy to an order within validity keeps the quotation's prices and discounts. After it, the copy is rejected with `quotation_expired`, unless the client asks to `reprice`; then the lines are priced anew (R37). It closes automatically when every line is fully ordered. A lost quotation is canceled with a reason of kind `cancel` and a note on the `document` row (`canceled_reason_id`, `canceled_note`, ADR-0074.R14); there is no `quotation.cancel_reason` text. Quotations write no `demand_supply_line` and reserve nothing (ADR-0024.R8).
Source: ADR-0047.R3, .N2

R22. A quotation holds the sales order's header and lines of R23, without demand, reservation or item creation. A line's warehouse is optional; the warehouse checks of an order line (R20 included) run when the line is copied to an order, which requires one. The partner must hold the active `customer` role (ADR-0019.R2) at `Create`, `Update` and `Submit`, otherwise `partner_role_missing`.
Source: ADR-0047.R3.N1

### `sales_order`

R23. `sales_order` header: customer, currency, price list (from the customer's profile, else the company's default sale list, ADR-0045.R5), payment term, salesperson, document discount percentage, requested delivery date. Lines: item or configuration, quantity and unit, warehouse, planned delivery date (needed by FEFO, ADR-0023.R13), price steps (R37), taxes (ADR-0041.R6).
Source: ADR-0047.R4

R24. `Submit` of a `sales_order` is a policy point with the credit condition (R3; ADR-0047.R18). Leaving draft creates configured items (R6) and demand rows (ADR-0024.R8); the rows stay unreleased (`not_approved`) until the order is approved, or until `Submit` when no approval is required (ADR-0047.R18.N1, ADR-0047.R19.N1). On approval each stock line reserves up to available to promise (ADR-0023.R13), and the rest is a backorder. The company setting `sales.reserve_on_approval` (default true, flagged) turns this off. Make-to-order lines reserve production output instead (ADR-0034.R14).
Source: ADR-0047.R4

### `sales_invoice`

R25. `sales_invoice` lines. A stock line refers to a posted delivery line. Its quantity is at most `delivered net − invoiced net` of its order line, otherwise `invoice_exceeds_delivered`. A non-stock or service line refers to an order line, up to its open quantity (`invoice_exceeds_ordered`), or stands alone. Invoicing goods before delivery is not allowed; bill and hold stays an open question. No stock sale without an order: a delivery line or a sales invoice line of a stock item without a sales order line is rejected with `sales_order_required`, so demand, credit and progress stay uniform, as `purchase_order_required` does for purchases (ADR-0047.R12). Goods delivered before the cut-over keep the path of R36.
Source: ADR-0047.R6, .N1

R26. Installments. The payment term's schedule (ADR-0026.R5) is part of the invoice's content, so its due dates and amounts are in the plan. Open items are derived from it at posting and are not in the plan (ADR-0031.R1). This settles ADR-0026.R3 against ADR-0031.R1.
Source: ADR-0047.R6

R27. A `sales_invoice` posts revenue by `revenue_posting` per item group, output tax (ADR-0041), and one receivable control line per installment. The receivable control line and its open item carry the payer (else the bill-to party, else the sold-to partner); the invoice's tax identity and printed customer are the bill-to party's (ADR-0074.R4).
Source: ADR-0047.R6, .N2

R28. Discounts on the invoice. The regime setting `sales.discount_presentation` decides: line and document discounts either reduce revenue directly (`net`), or post gross with the discount to `revenue_deduction_trade_discount` (`gross`). The value a regime takes is flagged content of the localization package, `unverified`.
Source: ADR-0047.R6

R29. A `sales_invoice` is issued as an e-invoice through the seam of ADR-0028.R6 to ADR-0028.R10. The type is never reversible (ADR-0009.R19). It does not wait for approval while the regime setting `documents.issuance_without_delay` is true (ADR-0009.R12, ADR-0053.R8).
Source: ADR-0047.R6, ADR-0047.R1.N1

### Sales returns

R30. The goods. `return_from_customer` (`inventory`) receives returned goods against delivery lines (`correction_of_id`: the delivery; ADR-0027.R7). `inventory` checks the quantity against the delivery line, which it owns: returned per delivery line ≤ delivered. The goods go to a `returns` bin as blocked (ADR-0023.R19). Their value follows the regime setting for `sales_return_receipt` (ADR-0020.R5). Goods returned before invoicing need no `sales_return`: they reduce what remains to invoice.
Source: ADR-0047.R7

R31. The money. `sales_return` is the posting correction of ADR-0009.R23. `correction_of_id` is the sales invoice, and lines refer to the `return_from_customer` lines they credit. It posts `revenue_deduction_return` and output tax at the original line's price and tax data (ADR-0041.R8), and creates a `credit` item, which it may match to the invoice (ADR-0026.R9). A sales return line that names a return-from-customer line in the same unit and for the same entered quantity takes that line's inventory quantity, so invoiced net and delivered net move together and `sales_return_due` closes exactly (ADR-0056.R10).
Source: ADR-0047.R7, .N1

R32. When a sales return is due. A `sales` consumer of the stock return's posted event compares, per order line, invoiced net with delivered net. When invoiced net is the larger, it raises a work item `sales_return_due` for the difference (ADR-0047.R20). The `sales_return` closes it.
Source: ADR-0047.R7

### `credit_note` and `debit_note`

R33. Reasons and accounts of the sales `credit_note` and `debit_note`:
- `allowance` posts to `revenue_deduction_allowance`;
- `trade_discount` posts to `revenue_deduction_trade_discount`;
- `price_correction` and `cancellation` post to `revenue_posting` (the invoice's own accounts);
- a `debit_note` (`price_correction`, `additional_charge`) posts to `revenue_posting`.
Returned goods are credited only by `sales_return`. `credit_note.reason` and `debit_note.reason` are fixed system codes; the lines of a return document carry an optional `return_reason_id` (kind `return`; ADR-0074.R14, ADR-0074.R15).
Source: ADR-0047.R8, .N2

R34. Original data. `correction_of_id` is the sales invoice. Lines take the original line's net unit price after the document discount, its taxes, tax date and rate (ADR-0041.R8). A quantity credit is `round_amount(quantity × original net unit price after the document discount)`. A credit or return line in another unit than its original converts the original's price per inventory unit by its own factor, `round_unit_price(p × d_o / n_o × n / d)`; a credit that completes the invoiced inventory quantity takes exactly the rest of the net amount. The same holds for purchase returns and supplier credits (ADR-0056.R11).
Source: ADR-0047.R8, .N1

R35. A credit note creates a `credit` item and may match it to the invoice in the same command (ADR-0026.R9).
Source: ADR-0047.R8

R36. Invoices from before the cut-over. A credit note or sales return may name an original that exists only in the old system: `correction_of_id` is empty, and `external_original` holds its number, date, net amounts, tax date and rates. This is allowed only for originals dated before the company's migration cut-over (ADR-0044.R13). The limits of ADR-0047.R20 then apply against the entered amounts. Returns of goods delivered before the cut-over come in as `other_receipt` with a reason, since no delivery line exists (flagged). The same applies to supplier documents.
Source: ADR-0047.R8

### Pricing procedure

R37. The pricing procedure is `sales.contract.price_line` and `purchasing.contract.price_line`. Each is a pure function of the header (list, currency, document date, partner) and the line (item or configuration values, unit, quantity, manual price, manual discount), in these steps:
- List price: `find_price` (ADR-0045.R4, ADR-0046.R15). The list's currency must equal the document's (`price_list_currency_mismatch`, ADR-0045.R5).
- Base price: the manual price if one is entered (`is_price_manual`), else the list price. A line with neither may not leave draft (`price_required`) unless it is free of charge (R43).
- Promotion (sales only): the one eligible promotion of R42.
- Manual discount: a percentage.
- Net unit price: the base price after the promotion and then the manual discount, rounded half up to the unit-price scale (ADR-0006) and stored.
- Line amount: `round_amount(quantity × stored net unit price)` (ADR-0006.R18), so the stored values reproduce it.
- Document discount: a percentage on the header. Its total, `round_amount(Σ line amounts × percentage)`, is allocated to the paid lines in proportion to their amounts, by largest remainder in minor units, with ties to the earlier line. A zero total allocates nothing. Each document that bills or credits lines (an invoice, a credit) applies the percentage to its own lines in the same way. Discount amounts are entered per line, as manual discounts.
Source: ADR-0047.R16

R38. Pricing checks at `Create` and `Update`: `price_list_currency_mismatch`, and `tax_inclusive_multiple_codes` for a tax-inclusive list where more than one percent code applies (ADR-0041.R9, ADR-0045.R5). Taxes are computed by `tax.contract.compute_taxes` on the net amounts after the document discount, with `prices_include_tax` from the list (ADR-0045.R5).
Source: ADR-0047.R16

R39. The price trace. Each step is a `document_line_price_step` row (step, source table and row, value) in the line's content. It is in the plan and the version hash, and it reproduces the stored net unit price and the line amount (`INV-93`). Interim, with the open question on trace scope: pricing writes no `derivation_trace` rows; the steps on the line serve Principle 6.
Source: ADR-0047.R16

R40. Re-pricing. A draft line is priced again whenever its item, configuration, unit, quantity or the document date changes, unless its price is manual. A line copied with its price (R13, R21) is marked `is_price_copied` and keeps the source line's price steps; like a manual price, it is not re-priced when its quantity or the document date changes. A change of its item, configuration or unit, or the client's `reprice`, prices it anew and clears the mark.
Source: ADR-0047.R16, .N1

### Promotions

R41. A `promotion` is `sales` master data (`master_data_change`, change-tracked, proposal-bound). Fields: `code`, `name`, `priority`, dates, optional customer, partner group or price list, scope (an item, a product or an item group), minimum line quantity, and `kind`:
- `percent` off the base price;
- `amount_per_unit` off the base price;
- `free_goods`: a free item and quantity per multiple of the qualifying quantity.
`minimum_line_quantity`, `qualifying_quantity` and `free_quantity` are inventory-unit quantities; `amount_per_unit` is per inventory unit times the line's factor, rounded once (ADR-0056.R16).
Source: ADR-0047.R17, .N1

R42. At most one promotion applies per line: the eligible one with the highest priority, then the lowest code. Promotions over a whole order are later (open question).
Source: ADR-0047.R17

R43. Free goods are a generated line: price 0, `is_free_of_charge`, the promotion, and the line it came from. The document discount skips them (`EC-70`).
Source: ADR-0047.R17

R44. Delivery of free goods. The `is_free_of_charge` flag is copied to the delivery line (a column reserved in the step 3 design). Such lines post movement `free_goods_issue` (catalog row: out, preliminary price, offset key `free_goods_cost`). The key `free_goods_cost` has the regime alternatives `cost_of_goods_sold` and `selling_expense`; which one a regime takes is flagged content of the localization package, `unverified`. The tax treatment of free goods is the package's rule, `unverified` (open question).
Source: ADR-0047.R17

## Invariants

| Invariant | Name | Check point | Statement | Protects |
| --- | --- | --- | --- | --- |
| `INV-93` | `price_steps_reproduce_price` | day | Every commercial document line's price steps reproduce its net unit price and its line amount. | R37, R39 |

## Edge cases

| Edge case | Name | Case | Outcome | Protects |
| --- | --- | --- | --- | --- |
| `EC-70` | `free_goods_with_document_discount` | A sales order with a free goods promotion and a document discount; the discount is allocated to the paid lines by largest remainder and the free line stays at zero. | `must_succeed` | R37, R43 |

`EC-21` and `EC-63` (R3) have their rows in chunk 2.

## Settings

`docs/catalogs/settings.csv` holds no row whose key or area is of `sales`. The rules of the module name these keys, which have no row there:
- `sales.reserve_on_approval`: company setting, default true, flagged (R24; named again by ADR-0047.R23);
- `sales.discount_presentation`: regime setting, values `net` and `gross`; the value a regime takes is flagged content of the localization package, `unverified` (R28; named again by ADR-0047.R23).

Reads: `documents.issuance_without_delay` (`documents`; regime setting, core default false; ADR-0053.R8), used by R4 and R29; it has no row in `settings.csv` either.

## UI annotations

The sources of this chunk state no floorplan, title, facet, field annotation or tile. Work item kind of `sales` raised by its rules:

| Kind | Subject table | Owner | Due | Resolution | Rule |
| --- | --- | --- | --- | --- | --- |
| `sales_return_due` | `sales_order_line` | `role:sales_clerk` | `days:5` | `system`: closed when a `sales_return` credits the difference | R31, R32; ADR-0047.R20 |

It is not agent-resolvable. The kind `credit_hold` has its row in chunk 2.

## Conflicts

CONFLICT ADR-0030.R6: ADR-0030.R6.N1 (ADR-0074.R4) governs; exposure is kept per payer, else bill-to party, else sold-to partner, and currency, not per partner (R2).
CONFLICT ADR-0030.R7: ADR-0047.R18 governs; the credit check at `PostDelivery` is replaced by the credit hold on demand rows, and `PostDelivery` is not `is_policy_in_handler`; the marks "interim, flagged" on the check point and "the outcome is the author's" are dropped, because ADR-0047.R22.N4 confirms rule 18 of ADR-0047: an exceeded limit needs approval at `Submit`, with the other unreleased orders held (R3).
CONFLICT ADR-0047.R1: ADR-0047.R1.N1 (ADR-0053.R8, ADR-0053.R14) governs; approval hold of `sales_invoice`, `sales_return`, `credit_note` and `debit_note` is derived from the regime setting, not fixed at "no", and the adjustment and replacement invoice forms belong to the localization package and the e-invoice add-on; whether a single replacement invoice is required stays unverified (R4, R7). ADR-0047.R1.N3 governs the flags of `service_receipt` (R4).
CONFLICT ADR-0047.R6: ADR-0047.R1.N1 (ADR-0053.R8) governs; the sales invoice skips the approval queue only while `documents.issuance_without_delay` is true, not always (R29).
FALSE-POSITIVE ADR-0047.R1.N4: the flag word "reversed" describes how `gr_ir_rounding_clearing` documents are reversed as a consequence; the note adds a document type and reverses no rule.

## Trace

| Source | Where |
| --- | --- |
| ADR-0004.R4 | ref: ADR-0004.R4 |
| ADR-0009.R2 | ref: ADR-0009.R2 |
| ADR-0009.R2.N1 | ref: ADR-0009.R2.N1 |
| ADR-0009.R2.N2 | ref: ADR-0009.R2.N2 |
| ADR-0009.R2.N3 | ref: ADR-0009.R2.N3 |
| ADR-0009.R12 | ref: ADR-0009.R12 |
| ADR-0009.R23 | ref: ADR-0009.R23 |
| ADR-0009.R23.N1 | ref: ADR-0009.R23.N1 |
| ADR-0027.R7 | ref: ADR-0027.R7 |
| ADR-0027.R7.N1 | ref: ADR-0027.R7.N1 |
| ADR-0027.R7.N2 | ref: ADR-0027.R7.N2 |
| ADR-0030.R6 | R2 |
| ADR-0030.R6.N1 | R2 |
| ADR-0030.R7 | R3 |
| ADR-0046.R10 | R20 |
| ADR-0047.D0 | R1 |
| ADR-0047.R1 | R4, R5, R6, R7 |
| ADR-0047.R1.N1 | R4, R7, R29 |
| ADR-0047.R1.N2 | R8 |
| ADR-0047.R1.N3 | R4 |
| ADR-0047.R1.N4 | R9 |
| ADR-0047.R2 | R10, R11, R12, R13, R16, R17 |
| ADR-0047.R2.N1 | R14 |
| ADR-0047.R2.N2 | R15 |
| ADR-0047.R2.N3 | R11 |
| ADR-0047.R2.N4 | R10, R13 |
| ADR-0047.R2.N5 | R18 |
| ADR-0047.R2.N6 | R19 |
| ADR-0047.R2.N7 | R16, R19 |
| ADR-0047.R3 | R21 |
| ADR-0047.R3.N1 | R22 |
| ADR-0047.R3.N2 | R21 |
| ADR-0047.R4 | R23, R24 |
| ADR-0047.R6 | R25, R26, R27, R28, R29 |
| ADR-0047.R6.N1 | R25 |
| ADR-0047.R6.N2 | R27 |
| ADR-0047.R7 | R30, R31, R32 |
| ADR-0047.R7.N1 | R31 |
| ADR-0047.R8 | R33, R34, R35, R36 |
| ADR-0047.R8.N1 | R34 |
| ADR-0047.R8.N2 | R33 |
| ADR-0047.R16 | R37, R38, R39, R40 |
| ADR-0047.R16.N1 | R40 |
| ADR-0047.R17 | R41, R42, R43, R44 |
| ADR-0047.R17.N1 | R41 |
