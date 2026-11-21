Module: purchasing    Chunk: 1 of 3    Source ADRs: ADR-0024, ADR-0027, ADR-0030, ADR-0037, ADR-0047
Build step(s): 1, 4b, 5    Generated from index: 30d5706    Compiled by: Claude Fable 5.2, 2026-11-21

# `purchasing` compiled spec, chunk 1: ownership, document types, lines and copying, purchase request, conversion, purchase order, GR/IR seam, subcontracting

## Purpose

`purchasing` owns the commercial documents of the buying side: `purchase_request`, `purchase_order`, `purchase_invoice`, `purchase_return`, `purchase_credit_note`, `purchase_debit_note`, `gr_ir_write_off`, `gr_ir_rounding_clearing` and `service_receipt`, and `customs_declaration`. It does not own stock documents (`inventory`), the journal and open items (`ledger`), tax computation (`tax`), price lists (`master_data`) or production orders (`production`); it posts through their contracts. This chunk states the ownership list, the document types and their registry flags, lines, references and copying, the purchase request, the conversion of planned orders, the purchase order, the GR/IR seam of ADR-0030 and the purchasing side of subcontracting. The purchase invoice, GR/IR positions, returns, notes, pricing and change orders are in chunk 2; the later additions are in chunk 3.

## Entities and tables

DDL: `docs/design/DS-22-09-42-commercial-inventory.sql`.

| Table | Meaning | Key | Parent | Owner |
| --- | --- | --- | --- | --- |
| `purchase_request` | Header of a purchase request (R22) | `id`; (`company_id`, `id`) | `document` | `purchasing` |
| `purchase_request_line` | Line of a purchase request, with its unit block and origin references (R22) | `id`; (`purchase_request_id`, `line_number`) unique | `purchase_request` | `purchasing` |
| `purchase_order` | Header of a purchase order (R31) | `id`; (`company_id`, `id`) | `document` | `purchasing` |
| `purchase_order_line` | Line of a purchase order, with its price steps stored (R32) | `id`; (`purchase_order_id`, `line_number`) unique | `purchase_order` | `purchasing` |
| `service_receipt` | Header of the posting document that records a processor's delivery of an external operation (R47) | `id`; (`company_id`, `id`) | `document` | `purchasing` |
| `service_receipt_line` | Line of a service receipt, naming its `purchase_order_line_id`, with yield, scrap, `is_final`, the output lot and its GR/IR positions (R47) | `id`; (`service_receipt_id`, `line_number`) unique | `service_receipt` | `purchasing` |

Owned by rule, without DDL: `customs_declaration` and its tax rows (R1; ADR-0021.R10).

The tables `purchase_invoice`, `purchase_invoice_line`, `purchase_return`, `purchase_return_line`, `purchase_credit_note`, `purchase_credit_note_line`, `purchase_debit_note`, `purchase_debit_note_line`, `gr_ir_write_off` and `gr_ir_write_off_line` have their rows in chunk 2.

Reads: `journal_line`, `open_item`, `payment_term` (`ledger`); `pending_receipt_adjustment`, `replenishment_request`, `purchase_order_line_gr_ir_posting`, `landed_cost`, `goods_receipt_line`, `return_to_supplier_line` (`inventory`); `planned_order`, `planning_setting` (`planning`); `production_order_operation`, `operation_progress_component` (`production`); `document`, `document_version`, `document_line_price_step`, `document_line_custom_text` (`documents`); `partner`, `supplier_item`, `price_list`, `item`, `product_configuration`, `payment_method`, `delivery_method`, `incoterm`, `business_unit`, `warehouse` (`master_data`); `document_line_tax`, `tax_line` (`tax`).

## Commands and queries

The commands of each type are the generated document verbs of ADR-0009. Authorization: the document type leaf of the same name under the area `purchasing` (`authorization-areas.csv`: `purchase_request`, `purchase_order`, `service_receipt`, `customs_declaration`, `gr_ir_rounding_clearing`), at the level of the verb (`authorization-verb-levels.csv`: `Create`, `Update`, `Submit`, `Cancel` at `edit`; `Close`, `Post` at `post`; `Reverse` at `full`). The templates `buyer` and `warehouse_keeper` hold `post` on `service_receipt` (R47).

| Name | Actor and authorization | Input | Effect | Events | Error codes |
| --- | --- | --- | --- | --- | --- |
| `Create<Type>` of `purchase_request`, `purchase_order`, `service_receipt` | a person, or `system` on behalf of the converter for drafted requests (R22, R28); leaf of the type, `edit` | header, lines, optional `source_lines` | Creates the draft; copies source lines (R15, R16) | not stated | `quantity_exceeds_open`, `source_not_approved`, `order_currency_mismatch` |
| `Update` of a type | leaf of the type, `edit` | changed header or lines, added source lines | Changes the draft; removes draft lines and their supply rows (R34) | not stated | `document_line_referenced` |
| `Cancel` of a type | leaf of the type, `edit` | not stated | Cancels the document; closes its supply rows with `closed_reason` `canceled` (R34) | not stated | not stated |
| `Close<Type>` of `purchase_request`, `purchase_order` | `system` on the completing events, or a person; leaf of the type, `post` | not stated | Sets `closed_reason` (R19, R23) | not stated | not stated |
| `Post` of `service_receipt` | a human for a tainted draft; effect class `posting`, under policy as a purchase document; leaf `service_receipt`, `post` | not stated | Posts progress, backflush, service cost and, where set, the automatic receipt in one transaction (R48) | the ADR-0009 document events | `negative_stock`, `movement_not_allowed_at_processor`, `service_receipt_without_operation` |
| `Reverse` of `service_receipt` | leaf `service_receipt`, `full` | not stated | Reverses the automatic receipt, the backflush, the cost and the progress, in this order (R49) | not stated | refused once an invoice refers to the receipt; code not stated |
The row of `Post` of `gr_ir_rounding_clearing` (R11) stands in chunk 3.

Consumers and contract functions, not registry commands: the `purchasing` consumer of `ReplenishmentRequested` (R28); the `purchasing` consumer of the production order's approval event (R45); the consumer that runs `Close<Type>` as `system` (R19). `purchasing` calls `inventory.contract.set_order_line_gr_ir_price` (R33), `inventory.contract.record_pending_receipt_adjustment` (R40) and `production.contract.record_operation_progress` (R48). `inventory.contract.request_replenishment` (called by `ConvertPlannedOrder` of `planning`, R27) and `inventory.contract.adjust_receipt_value` (R41) are `inventory`'s; `tax.contract.request_e_invoice` (R3) is `tax`'s; `ExportCompanyData` (R4) is DS-21's.

## Rules

### Ownership

R1. `purchasing` owns `customs_declaration` and its tax rows, from step 5 (ADR-0021.R10).
Source: ADR-0027.R8

R2. The same ownership list names, outside `purchasing`: e-invoice records and intents, owned by `tax` (DS-24), which also owns the computation of `document_line_tax`, the subledger `tax_line` with its adjustments, and filed `tax_return` snapshots (ADR-0041), with imports going downward (as ADR-0024.R22); audit records, owned by `audit` (layer 2, DS-36), with one row per executed command: `command_type`, `actor_kind`, `actor_id`, `agent_run_id`, `idempotency_key` (needed by `INV-81`), and also `origin_agent_run_id`, `on_behalf_of_id` and `policy_decision_id` (ADR-0029.R15; full columns, changes and denials: ADR-0038.R1 to ADR-0038.R8); the full data export `ExportCompanyData` (DS-21; ADR-0044.R17); management reporting, which is the analysis layer of `query`: declared measures over the DS-33 semantic views, plans compiled to one `SELECT`, saved analyses and KPIs as company data, still never documents, whose measures over accounts use system accounts and ADR-0049's turnover rules for closing and migration entries and equal ADR-0049's turnover for the same scope and range (`INV-411`; ADR-0060), while statutory reports stay DS-26; bad-debt provisions and prepaid amortization (DS-25, close tasks); the inventory write-down to net realizable value (DS-09, a close task). These computations are not DS-26's, whatever ADR-0012.R17 names.
Source: ADR-0027.R8, ADR-0027.R8.N1

R3. A sales document requests issuance through `tax.contract.request_e_invoice`, synchronously; it writes the e-invoice record and its intent. The external consumer then issues it asynchronously, and the document posts on acceptance (ADR-0028.R7).
Source: ADR-0027.R8

R4. `ExportCompanyData` writes a company package with master data, documents with all versions, journal and material lines, open items, stock, attachments and audit rows, as one JSON Lines file per table plus the attachment files. It is not the import batch format; contents, exclusions and download are ADR-0044.R17.
Source: ADR-0027.R8

R5. A-7(d), a GR/IR invariant, is deferred to the GR/IR line-reference work before step 5 (assessment F12).
Source: ADR-0027.R20

### Document types and registry flags

R6. Document types (ADR-0009.R2, ADR-0009.R3) and their registry flags. Each entry gives: module; posting; change orders; e-invoice capable; approval hold allowed; reversible; `is_item_creating`; demand and supply.
- `quotation`: `sales`; not posting; no change orders; not e-invoice capable; approval hold allowed; reversibility does not apply; not item-creating; no demand or supply.
- `sales_order`: `sales`; not posting; change orders; not e-invoice capable; approval hold allowed; reversibility does not apply; item-creating; demand, after draft.
- `sales_invoice`: `sales`; posting; no change orders; e-invoice capable; approval hold derived from the regime setting `documents.issuance_without_delay` (no approval hold while it is true; core default false; ADR-0053.R8); not reversible; not item-creating.
- `sales_return`, `credit_note`, `debit_note`: `sales`; posting; no change orders; e-invoice capable; approval hold derived from `documents.issuance_without_delay` as for `sales_invoice`; not reversible; not item-creating.
- `purchase_request`: `purchasing`; not posting; no change orders; not e-invoice capable; approval hold allowed; reversibility does not apply; not item-creating; supply, from draft.
- `purchase_order`: `purchasing`; not posting; change orders; not e-invoice capable; approval hold allowed; reversibility does not apply; not item-creating; supply, from draft.
- `purchase_invoice`: `purchasing`; posting; no change orders; not e-invoice capable; approval hold allowed; reversible, latest only (ADR-0047.R13); not item-creating.
- `purchase_return`, `purchase_credit_note`, `purchase_debit_note`: `purchasing`; posting; no change orders; not e-invoice capable; approval hold allowed; reversible, latest only (ADR-0047.R13); not item-creating.
- `gr_ir_write_off`: `purchasing`; posting; no change orders; not e-invoice capable; approval hold allowed; reversible, latest only (ADR-0047.R13); not item-creating.
- `service_receipt` (R47): `purchasing`; posting; no change orders; not e-invoice capable; no approval hold; reversible while no invoice refers to it (ADR-0047.R13); not item-creating.
The value a regime gives `documents.issuance_without_delay` is flagged content of the localization package (`l10n_vn`).
Source: ADR-0047.R1, .N1, .N3

R7. The stock documents (`goods_receipt`, `delivery`, `return_to_supplier`, `return_from_customer`) stay `inventory`'s, with their flags set by DS-09 (ADR-0027.R13). Their reversal of order lines is limited by ADR-0047.R13. From step 5 their lines carry the order line references reserved at step 3 (ADR-0027.R7). Customs declarations and amendments keep the flags ADR-0021.R10 and ADR-0021.R11 give them, and service receipts those of R47. A service receipt's reversal is also limited by ADR-0047.R13.
Source: ADR-0047.R1

R8. `is_item_creating` is a registry flag. Only types with it create items on order when they leave draft (ADR-0045.R16, ADR-0046.R11): `sales_order`, and `production_order` by ADR-0046. Quotations never create items.
Source: ADR-0047.R1

R9. `sales_return`, `credit_note` and `debit_note` are the adjustment documents of sales invoices (spec 08). Corrections stay correction documents; Phase 1 models a replacement as a full `credit_note` plus a new invoice. The adjustment and replacement invoice forms are the localization package's (`l10n_vn`) and the e-invoice add-on's (ADR-0053.R14); whether a regime requires a single replacement invoice, and the form of returns, is decided by its localization package and is unverified, for the author to verify; a dedicated type would be the e-invoice add-on's (DS-24). `Post` or `Issue` of every correction type of R6 is `human_only` (ADR-0009.R23, interim). Kits (bill of materials usage `kit`, ADR-0033.R3) come after Phase 1 (open question).
Source: ADR-0047.R1, .N1

R10. Every type of R6, and the stock documents, are `is_printable` and carry the optional header field `print_language` (ADR-0049.R25, ADR-0049.R27).
Source: ADR-0047.R1.N2

R11. Document type `gr_ir_rounding_clearing` (ADR-0056): `purchasing`, posting, no change orders, not e-invoice capable, no approval hold, reversed only as a consequence (never by `Reverse`), not item-creating, no demand or supply. Its `Post` is `is_internal_only` and `is_consequence_posting`; its authorization leaf is under purchasing at level `full`, in no template's expansion. It has its own `document` row and no header or line table: its `purchase_order_line_gr_ir_posting` row of kind `rounding_clearing` carries the line, positions and amount (ADR-0056.R10).
Source: ADR-0047.R1.N4

### Lines, references and copying

R12. Lines store the entered quantity and unit and the inventory quantity (ADR-0018.R11). GR/IR positions, correction limits and progress use inventory quantities. Receipts, deliveries, invoices, returns and credits may use any allowed unit of the item; every quantity relation compares inventory quantities (ADR-0056).
Source: ADR-0047.R2, .N4

R13. Line references use the typed keys of ADR-0028.R2: `quotation_line_id`, `sales_order_line_id`, `delivery_line_id`, `return_from_customer_line_id`, `purchase_request_line_id`, `purchase_order_line_id`, `goods_receipt_line_id`, `return_to_supplier_line_id`, and `correction_of_line_id` on correction lines. `service_receipt_line_id` joins them, for purchase invoice service lines that clear GR/IR against a service receipt (ADR-0047.R12, R50).
Source: ADR-0047.R2, .N3

R14. Lines carry their `product_configuration`, custom text in `document_line_custom_text`, and the checks of ADR-0046.R9 and ADR-0046.R10 (completeness, the warehouse of configurable lines, re-evaluation when copied to a new document).
Source: ADR-0047.R2

R15. `Create<Type>` accepts `source_lines` (a source document's line numbers and quantities). The handler copies the lines with their references, prices, discounts, taxes and configuration, and sets `derived_from_version_id` (ADR-0029.R8). It copies only a source line's open quantity, otherwise `quantity_exceeds_open`. `source_lines` quantities are in the source line's unit, and a copied line takes the source line's unit and snapshot, so a part in the source's unit converts by the cumulative rule (ADR-0056.R10, ADR-0056.R11).
Source: ADR-0047.R2, .N4

R16. Copy preconditions. `source_lines` may name only a document that is approved or later (approved, issued, posted, or closed), never one in draft, pending approval, rejected or canceled (`source_not_approved`). The pairs:
- quotation to sales order (within validity, ADR-0047.R3);
- sales order to delivery, and to sales invoice for non-stock and service lines (released rows, ADR-0047.R19);
- posted delivery to sales invoice and to return from customer;
- posted or issued sales invoice to sales return, credit note and debit note;
- purchase request to purchase order;
- purchase order to goods receipt, service receipt and purchase invoice (released rows);
- posted goods receipt to return to supplier;
- posted purchase invoice to purchase return and supplier notes.
One `Create<Type>` copies the lines of one source document, deliveries included (pick batches release each document on its own, ADR-0023.R16), except that a purchase order may combine several purchase requests, and a sales or purchase invoice may combine deliveries, receipts and order lines of one partner in one currency. The target's partner is the source's.
Source: ADR-0047.R2.N1

R17. Copying carries taint. On `Create<Type>` with `source_lines`, and on every `Update` that adds source lines, the new version's `is_tainted` is the OR of the effective taint, at that moment, of every source line's document version; `derived_from_version_id` names the first source document's version, and `INV-88` reads the others through the lines' typed references (ADR-0029.R8). `inventory`'s stock documents and `production`'s orders created from source lines set it the same way (ADR-0023.R16).
Source: ADR-0047.R2.N2

R18. What counts for `document_referenced` (ADR-0009.R7): references from documents that are not canceled or reversed. Documents copy the partner snapshot (ADR-0028.R16); it also covers the ship-to, bill-to, payer, invoicing-party and payee parties a document names (ADR-0074.R1, ADR-0074.R2). Incoming documents carry the supplier's number in `partner_reference`, which also reaches the open item (ADR-0026.R1). Invoices, returns and notes of order lines are in the order's currency, otherwise `order_currency_mismatch`.
Source: ADR-0047.R2, .N7

R19. Closing orders and requests. An order or request closes automatically (`closed_reason` `fulfilled` on its header) when every line is done by quantity, net of returns and quantity credits: stock lines delivered or received and invoiced, other lines invoiced. A consumer in the owning module runs `Close<Type>` as `system` on the events that complete it, under the document's lock (ADR-0027.R10, class 1). `Close` by a person sets `closed_reason` `short`, and cancels the open rest: reservations, and the open quantity of the demand or supply rows. A closed document takes no new deliveries or receipts. Invoices are still accepted up to delivered or received net, and corrections still refer to its lines. This answers ADR-0009.R6.
Source: ADR-0047.R2

R20. Headers carry `payment_method_id` (quotation, sales order, sales invoice, purchase order, purchase invoice), `delivery_method_id` (sales order, purchase order), and `incoterm_code` with `incoterm_place` (quotation, sales order, delivery, sales invoice, purchase order, goods receipt, purchase invoice). Each is copied from the partner profile at creation and then from the source document, and changeable while the document is a draft or by a change order. Deliveries and goods receipts also carry `delivery_method_id`, `carrier_partner_id` (an active supplier), `tracking_number` and `vehicle_registration`. None of these fields enters pricing, posting or policy (ADR-0068).
Source: ADR-0047.R2.N5

R21. Every commercial document header carries a nullable `business_unit_id`; copying fills an empty header from the source, and it can be changed until posting (ADR-0069). Documents carry a `note` (ADR-0074.R16), and the headers of ADR-0074.R9 carry `custom_values`.
Source: ADR-0047.R2.N6, ADR-0047.R2.N7

### Purchase request

R22. `purchase_request` comes from people, or from the `purchasing` consumer of `ReplenishmentRequested`, as `system` on behalf of the converter (R28). `purchase_request_line` carries item (`item_id`), quantity with its unit block, `requested_date`, the suggested supplier (`suggested_supplier_id`), `origin_planned_order_id`, and `production_order_operation_id` for subcontracted operations (R45). The DDL also holds `warehouse_id` on the line (the supply row needs it, ADR-0024.R8) and `buyer_id` on the header, both marked interim.
Source: ADR-0047.R9

R23. The open quantity of a request line falls by what is ordered from the line. A request closes automatically when fully ordered.
Source: ADR-0047.R9

R24. For a conversion executed from an approved change proposal (the planning agent's, ADR-0051.R24), the converter is the approving human of ADR-0029.R3: the approver whose approval completed the proposal's plan (ADR-0055.R16). The purchase requests are drafted on their behalf, so that person cannot approve them.
Source: ADR-0047.R9.N1

R25. Policy input of a purchase request (ADR-0043.R4; ADR-0047.R22). A request carries no price, so for policy only, each line is valued at the first of:
- the supplier's purchase price: `find_price` on the purchase list of the line's suggested supplier, else of the item's preferred `supplier_item` supplier (its supplier profile's list, else the company's default purchase list, as on a purchase order), for the line's item, unit, quantity and requested date;
- the item's last purchase price: the net unit price of its most recent posted purchase invoice line in the company, converted to the line's unit;
- zero, and the request's policy input sets `is_cost_unknown`.
Amounts are in company currency at the applied rate; the request's amount is the sum of its valued lines. The values live in the policy input and its hash, not on the request. Interim, flagged.
Source: ADR-0047.R9.N2

### Conversion of planned orders

R26. `ConvertPlannedOrder` takes firmed or proposed planned orders. Purchase orders are grouped by supplier, warehouse, and release date within `conversion_window_days`; transfer orders by route. Production planned orders convert through `production.contract` (ADR-0036.R8). A planned order converts whole; a split is two `UpdatePlannedOrder` calls in Phase 1.
Source: ADR-0024.R22

R27. Hand-over. The command sets `converted` and calls the posting interface `inventory.contract.request_replenishment`, which writes one `replenishment_request` with a line per planned order (carrying `origin_planned_order_id`) and emits `ReplenishmentRequested` from `inventory`, so every importer imports downward (ADR-0022.R2). The replenishment request line carries the planned order's order unit and snapshot (ADR-0056.R14).
Source: ADR-0024.R22, .N1

R28. Drafts. The `purchasing` consumer of `ReplenishmentRequested` groups the request's purchase lines by supplier, warehouse and release window into draft purchase requests (interim, flagged: the default target, following spec 09's request → order chain). `inventory` creates the draft transfer orders itself. Drafts are created as actor `system` on behalf of the converter, follow their own approval (DS-28), and carry `origin_planned_order_id`. The drafted purchase request line carries the planned order's order unit and snapshot; a purchase order copied from a request keeps the request's unit unless the person changes it (ADR-0056.R14). Service lines for external operations are drafted the same way, from the production order's approval event (R45).
Source: ADR-0024.R22, .N1

R29. Canceled drafts. When the document lines of a converted order close with `closed_reason` `canceled` (ADR-0024.R8), the next run sets it `canceled` and may propose again.
Source: ADR-0024.R22

R30. Auto-conversion. Converting under a value threshold by policy is an open question (DS-28). Sending to a supplier always stays a separate approved step. For agents, `UpdatePlannedOrder`, `FirmPlannedOrder` and `ConvertPlannedOrder` are proposal-bound for every order type (ADR-0036.R12).
Source: ADR-0024.R22

### Purchase order

R31. `purchase_order` header: supplier (`partner_id`, the ordered-from party of ADR-0074.R1), currency, price list (the supplier's purchase list), payment term, buyer (the supplier profile's default, ADR-0027.R6), document discount percentage; it may also name the parties `invoicing_party` and `payee` (ADR-0074.R2). Price list and buyer are read from the ordered-from supplier (ADR-0074.R4). When the supplier profile names no purchase list, the order takes the company's default purchase list, as a sales order takes the default sale list (ADR-0047.R4). With neither, or with a list in another currency, the order carries no list and its prices are entered (ADR-0045.R5).
Source: ADR-0047.R10, .N1

R32. `purchase_order_line` carries item, quantity and unit, receiving warehouse, requested date, price steps (ADR-0047.R16, without promotions), taxes, `purchase_request_line_id`, and `origin_planned_order_id` and `production_order_operation_id` copied from the request. The supply row gets `ordered_date` at approval (ADR-0024.R8).
Source: ADR-0047.R10

R33. The GR/IR price. At approval and at each take-force, `purchasing` pushes each line's GR/IR unit price to `inventory` through `inventory.contract.set_order_line_gr_ir_price`. The price is the line's net amount after the document discount, without tax, divided by its inventory quantity, as an exact rational in the order's currency.
Source: ADR-0047.R10

R34. Supply rows from draft (ADR-0024.R8). A draft line whose row carries `origin_planned_order_id` or pegging cannot be removed, nor its draft deleted (`document_line_referenced`). Its quantity is set to zero or the document canceled, which closes the row with `closed_reason` `canceled` (ADR-0024.R22). Other draft lines removed by `Update`, or drafts deleted, delete their rows. Rows of documents that have left draft are never deleted.
Source: ADR-0047.R10

### GR/IR seam

R35. `journal_line` has a nullable `purchase_order_line_id` (ADR-0014.R9: a new nullable column by ADR). The column exists from step 1, and its foreign key to `purchase_order_line` is added at step 5, when the table exists (as ADR-0028.R2 does for line references).
Source: ADR-0030.R3

R36. Where it is required. A line on a system account with control kind `gr_ir` (ADR-0014.R10, extended) carries `purchase_order_line_id` when its document line refers to a purchase order line. From step 5 every `purchase_receipt` and `purchase_return` line and every goods invoice line for ordered goods must refer to one; goods bought without an order are a DS-22 requirement. Before step 5, references are free text (ADR-0027.R7), and opening-balance lines on GR/IR (goods received but not invoiced at cut-over) have none, so those lines leave it null. Opening GR/IR lines come through `opening_balance_entry` (ADR-0044.R7). The posting handlers enforce it, and `INV-37` detects violations; the journal trigger cannot see the document.
Source: ADR-0030.R3

R37. GR/IR always carries the order price. The GR/IR unit price of a quantity is the order line's price in force when that quantity first posts, by receipt or by invoice. The counterpart posting uses the same price, matched first in, first out per order line. Matching is by unit positions per order line, each priced once at first posting; postings are differences of rounded cumulative values, so the balance is zero whenever received equals invoiced; returns and quantity credits take the latest positions, which equals the receipt's or invoice's price when the order price never changed; reversals are allowed only for the latest postings of a side (ADR-0047.R13). A purchase return debits GR/IR for the returned quantity, and a credit note on the invoice credits it, at those positions.
Source: ADR-0030.R4

R38. Receipt first. The receipt debits inventory and credits GR/IR at quantity × GR/IR price. The invoice then debits GR/IR at invoiced quantity × GR/IR price and credits the payable at invoice value. Both amounts are taken at the positions the quantity reaches, as differences of rounded cumulative values (ADR-0047.R13). The difference goes as the regime determines `price_difference` (ADR-0015.R4): to a price difference account; or to `purchase_cost_clearing`, then to stock through ADR-0030.R1 for the received quantity.
Source: ADR-0030.R4

R39. Invoice first. The invoice debits GR/IR at invoiced quantity × GR/IR price, credits the payable, and posts the difference as in R38. Interim, flagged: the regime might instead value an invoice-first receipt at the invoice price (open question).
Source: ADR-0030.R4

R40. Stock-bound differences for quantities not yet received stay in `purchase_cost_clearing`, and the invoice calls `inventory.contract.record_pending_receipt_adjustment`. That interface writes, in the inventory-owned table `pending_receipt_adjustment`, one row per invoice line: `purchase_order_line_id` (foreign key from step 5), the invoice line, the total difference in company currency, the quantity still to receive and the amount still to apply. The table stays empty until step 5, so the step 3 handler needs no change later (B3).
Source: ADR-0030.R4

R41. The goods receipt handler (step 3, `inventory`) consumes the rows for its line's `purchase_order_line_id` (ADR-0027.R7; null before step 5, so nothing is consumed then) in its own transaction. Through `inventory.contract.adjust_receipt_value` it writes a posted `landed_cost` with `cost_type` `price_difference`, allocation rows, `caused_by_document_id` the invoice, and the invoice's clearing line as its source, in the receipt's period. It applies amount pro rata to quantity, and the last receipt takes the rest.
Source: ADR-0030.R4

R42. Rows of `pending_receipt_adjustment` are read and written only under the purchase order's document lock (ADR-0027.R10, class 1), which both the invoice and the receipt take as a referenced document. A credit note or correction of the invoice reduces its row through the same interface. When the order line closes with quantity still to receive, DS-22 releases the remaining amount from `purchase_cost_clearing` to the price difference account (interim, flagged with the invoice-first open question). That release carries no valuation class, so it reaches the regime's generic price difference account (ADR-0039.R8).
Source: ADR-0030.R4

R43. The exchange-rate difference between goods receipt and invoice is designed as SAP does (interim translation of the chief architect, 2026-11-21): on a line for an item kept in stock the company-currency difference between receipt and invoice rates enters the item's actual cost; on other lines it stays a realized exchange difference (ADR-0047.R13). On a stocked line the company setting `costing.exchange_rate_difference_to_stock` chooses: true, the default, enters the actual cost; false posts it to realized exchange difference (ADR-0047.R13.N4).
Source: ADR-0030.R4, .N1

R44. `INV-37` has these parts, first executable at step 5: every journal line on a `gr_ir` account whose document line refers to a purchase order line has `purchase_order_line_id`; and per purchase order line whose received quantity equals its invoiced quantity, net of returns and credit notes, the GR/IR balance in transaction currency is zero.
Source: ADR-0030.R5

### Subcontracting: buying the service

R45. Drafting. Releasing a production order emits its approval event (ADR-0009.R22). A `purchasing` consumer drafts one purchase request line per external operation (the pattern of R28, actor `system`), for the service item and the operation's planned quantity at the supplier's price. The line carries `production_order_operation_id`, a typed line reference that ADR-0028.R2 reserves to the author under B3, so it is flagged (open question). A re-release drafts nothing twice: the consumer's key is the operation.
Source: ADR-0037.R4

R46. Changes to the production order. A change of G updates a draft line, or creates a work item when an order line exists. `Cancel` and technical completion cancel open draft lines, or create a work item for open order lines. Choosing another supplier after release is a change order on the production order (ADR-0034.R8): component issue warehouses move to the new location, and staged stock moves by transfer.
Source: ADR-0037.R4

R47. `service_receipt` is a posting document type owned by `purchasing`, for purchase order lines that carry `production_order_operation_id`. It records a supplier's delivery, so it follows `goods_receipt`'s flagged interim (ADR-0009.R19; ADR-0027.R13): reversible while no invoice refers to it, otherwise corrected by a correction document. Its record scope uses the processor location as the warehouse dimension (ADR-0017.R9), and it emits the ADR-0009 document events. Its fields: yield (`yield_quantity`), scrap (`scrap_quantity`), `is_final`, and, for automatic receipt, the output lot (`output_lot_id`). Its authorization leaf sits under Purchasing (`authorization-areas.csv`), its registry flags are in R6, and the templates `buyer` and `warehouse_keeper` hold `post` on it (ADR-0054.R11).
Source: ADR-0037.R5, .N1

R48. Posting a `service_receipt`, in one transaction:
- progress, through `production.contract.record_operation_progress` (ADR-0034.R12);
- the backflush of the operation's components at the processor location, by cumulative progress and rounded up, as `production_issue` with the order's cost object; `record_operation_progress` computes and posts it and stores the generated lines in the production-owned `operation_progress_component`, keyed by the calling posting document, as for confirmations; `service_receipt` holds only its own lines;
- the service cost: debit `production_cost_other` (order), credit GR/IR clearing at the order price with `purchase_order_line_id` (R35 to R44), key `production_external_service`;
- when the operation is the order's last, of either control, and the version sets automatic receipt, the output into the production warehouse (ADR-0034.R13).
Source: ADR-0037.R5

R49. Too little stock at the processor rejects the receipt with `negative_stock`. Reversal of a `service_receipt` is refused once an invoice refers to the receipt; otherwise it reverses, in this order: the automatic receipt, the backflush, the cost and the progress. A receipt drafted from a processor's delivery note is tainted (ADR-0029.R10), so a human posts it. Simulation applies as for any command.
Source: ADR-0037.R5

R50. After the service receipt:
- Invoice differences. The invoice clears GR/IR at the order price (R37). A service has no pending receipt adjustment, so a difference posts straight to the order's `production_cost_other` while the order is not closed, and after close to the price-difference account, never the stock-bound path, since a service has no receipt lines. Both are interim and flagged. After close the difference posts without a valuation class, so it reaches the generic price difference row (ADR-0039.R8).
- Actual consumption. When the processor reports actual consumption, a `production_issue` or return at the processor location adjusts the order.
- Leftovers come back by transfer.
Source: ADR-0037.R6

R51. Document commands of subcontracting follow ADR-0009. Posting a service receipt is effect class `posting`, under policy as a purchase document (DS-28). `service_receipt` records the processor's delivery, a fact: `is_approval_hold_allowed: false`, so it reaches no approval pool and a rank becomes `human_post` (ADR-0055.R2). Errors and check results: `movement_not_allowed_at_processor`, `negative_stock`, and `service_receipt_without_operation` for a line without `production_order_operation_id`.
Source: ADR-0037.R11, .N1

R52. Build placement: subcontracting runs on the production core (step 4b) and on purchase orders and the service receipt of `purchasing` (step 5), and its planning rules (ADR-0037.R2, ADR-0037.R3) use the planning run of step 5b. It is built in step 5b, after the gates of steps 4b and 5.
Source: ADR-0037.R11.N2

## Invariants

Statements are those of `invariants.csv`. Each row stands once in the module, in the chunk that states the rule its catalog source names.

| Invariant | Name | Check point | Statement | Protects |
| --- | --- | --- | --- | --- |
| `INV-37` | `gr_ir_per_order_line` | day | Every journal line on a `gr_ir` account whose document line refers to a purchase order line has `purchase_order_line_id`; per purchase order line whose received quantity equals its invoiced quantity, net of returns and credit notes, the GR/IR balance in transaction currency is zero. Flagged with the invoice-first valuation of ADR-0030.R4. | R36, R37, R44 |
| `INV-81` | `human_only_never_by_agent` | day | No audit row of a command registered `human_only` has actor kind `agent`, or `integration` while the interim holds. | R2, R9 |

Named by rules of this chunk, with their rows in other chunks: `INV-88` (R17), `INV-411` (R2).

## Edge cases

| Edge case | Name | Case | Outcome | Protects |
| --- | --- | --- | --- | --- |
| `EC-61` | `invoice_before_receipt` | Under the flagged interim, the supplier invoice posts before the goods arrive; GR/IR carries the order price, the difference for unreceived goods waits as a pending receipt adjustment, and GR/IR clears per order line once quantities match. | `must_succeed` | R39 to R41 |
| `EC-62` | `price_difference_soft_locked_receipt` | An invoice differs from a receipt whose period is soft-locked; the difference posts as a receipt addition in an open period (the invoice's, or the first open one after it), whoever posts, and the invoice is not blocked (ADR-0030.R2 note). | `must_succeed` | R38; ADR-0030.R2 |

## Settings

None: the rules of this chunk name no setting key owned by `purchasing`. `conversion_window_days` (R26) is a column of `planning_setting`, not a key of `settings.csv`.

Reads: `documents.issuance_without_delay` (`documents`; regime setting, core default false; ADR-0053.R8), used by R6, which has no row in `settings.csv` (the keys the module names without a row are listed once, in chunk 3); `costing.exchange_rate_difference_to_stock` (`inventory`), used by R43, with its row in chunk 2's Reads. Keys of `inventory` named by the units this chunk traces as `ref:`: `movement_type.purchase_return.value_source`, `movement_type.purchase_return.costing_role`, `movement_type.purchase_return.include_landed_cost`, `movement_type.sales_return_receipt.value_source`, `movement_type.sales_return_receipt.costing_role`, `movement_type.stock_count_shortage.value_source`, `movement_type.stock_count_shortage.costing_role`, `movement_type.stock_count_surplus.value_source`, `movement_type.stock_count_surplus.costing_role`, `stock_count.bin_difference_method`; and of `ledger`: `journal.manual_posting_to_control_accounts`.

## Conflicts

CONFLICT ADR-0047.R1: ADR-0047.R1.N1 (ADR-0053.R8, ADR-0053.R14) governs; approval hold of `sales_invoice`, `sales_return`, `credit_note` and `debit_note` is derived from the regime setting `documents.issuance_without_delay`, not fixed at "no", and the adjustment and replacement invoice forms belong to the localization package and the e-invoice add-on; whether a regime requires a single replacement invoice is decided by its localization package and stays unverified, for the author to verify (R6, R9).
FALSE-POSITIVE ADR-0047.R1.N4: the flag word "reversed" describes how `gr_ir_rounding_clearing` documents are reversed as a consequence; the note adds a document type and reverses no rule.
CONFLICT ADR-0030.R4: the "Amendment" of ADR-0047.R13 (chunk 2, R208) replaces the return price "the GR/IR price of the receipt it returns" and the credit note price "the invoice's GR/IR price": returns and quantity credits take the latest positions of the order line, and all GR/IR postings are differences of rounded cumulative values (R37, R38). ADR-0030.R4.N1 answers the exchange-rate difference between receipt and invoice, so its mark "open question" is not restated, and ADR-0047.R13.N4 adds the company setting `costing.exchange_rate_difference_to_stock` for stocked lines (R43).
CONFLICT ADR-0047.R10: ADR-0074.R2 puts the parties `invoicing_party` and `payee` on the `purchase_order` header, and ADR-0074.R4 reads price list and buyer from the ordered-from supplier (R31).
CONFLICT ADR-0047.R9: the DS-22 DDL governs the columns of `purchase_request` and `purchase_request_line`: `buyer_id` and `warehouse_id` stand beside the fields the rule lists, marked interim in the DDL, and ADR-0024.R22.N1 adds the unit block (R22, R28).

## Trace

| Source | Where |
| --- | --- |
| ADR-0009.R19 | ref: ADR-0009.R19 |
| ADR-0009.R19.N1 | ref: ADR-0009.R19.N1 |
| ADR-0009.R23 | ref: ADR-0009.R23 |
| ADR-0009.R23.N1 | ref: ADR-0009.R23.N1 |
| ADR-0020.R5 | ref: ADR-0020.R5 |
| ADR-0020.R5.N1 | ref: ADR-0020.R5.N1 |
| ADR-0020.R5.N2 | ref: ADR-0020.R5.N2 |
| ADR-0020.R5.N3 | ref: ADR-0020.R5.N3 |
| ADR-0020.R5.N4 | ref: ADR-0020.R5.N4 |
| ADR-0020.R5.N5 | ref: ADR-0020.R5.N5 |
| ADR-0020.R5.N6 | ref: ADR-0020.R5.N6 |
| ADR-0021.R3.N1 | ref: ADR-0021.R3.N1 |
| ADR-0021.R6.N2 | ref: ADR-0021.R6.N2 |
| ADR-0023.R7 | ref: ADR-0023.R7 |
| ADR-0023.R7.N1 | ref: ADR-0023.R7.N1 |
| ADR-0023.R7.N2 | ref: ADR-0023.R7.N2 |
| ADR-0023.R7.N3 | ref: ADR-0023.R7.N3 |
| ADR-0024.R22 | R26, R27, R28, R29, R30 |
| ADR-0024.R22.N1 | R27, R28 |
| ADR-0027.R7 | ref: ADR-0027.R7 |
| ADR-0027.R7.N1 | ref: ADR-0027.R7.N1 |
| ADR-0027.R7.N2 | ref: ADR-0027.R7.N2 |
| ADR-0027.R8 | R1, R2, R3, R4 |
| ADR-0027.R8.N1 | R2 |
| ADR-0027.R20 | R5 |
| ADR-0030.R3 | R35, R36 |
| ADR-0030.R4 | R37, R38, R39, R40, R41, R42, R43 |
| ADR-0030.R4.N1 | R43 |
| ADR-0030.R5 | R44 |
| ADR-0037.R4 | R45, R46 |
| ADR-0037.R5 | R47, R48, R49 |
| ADR-0037.R5.N1 | R47 |
| ADR-0037.R6 | R50 |
| ADR-0037.R11 | R51 |
| ADR-0037.R11.N1 | R51 |
| ADR-0037.R11.N2 | R52 |
| ADR-0039.R9 | ref: ADR-0039.R9 |
| ADR-0039.R9.N1 | ref: ADR-0039.R9.N1 |
| ADR-0047.D0 | ref: ADR-0047.D0 |
| ADR-0047.R1 | R6, R7, R8, R9 |
| ADR-0047.R1.N1 | R6, R9 |
| ADR-0047.R1.N2 | R10 |
| ADR-0047.R1.N3 | R6 |
| ADR-0047.R1.N4 | R11 |
| ADR-0047.R2 | R12, R13, R14, R15, R18, R19 |
| ADR-0047.R2.N1 | R16 |
| ADR-0047.R2.N2 | R17 |
| ADR-0047.R2.N3 | R13 |
| ADR-0047.R2.N4 | R12, R15 |
| ADR-0047.R2.N5 | R20 |
| ADR-0047.R2.N6 | R21 |
| ADR-0047.R2.N7 | R18, R21 |
| ADR-0047.R9 | R22, R23 |
| ADR-0047.R9.N1 | R24 |
| ADR-0047.R9.N2 | R25 |
| ADR-0047.R10 | R31, R32, R33, R34 |
| ADR-0047.R10.N1 | R31 |
