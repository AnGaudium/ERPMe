Module: purchasing    Chunk: 3 of 3    Source ADRs: ADR-0047, ADR-0056, ADR-0057, ADR-0063, ADR-0065, ADR-0066, ADR-0074
Build step(s): 0, 1, 4, 5, 7    Generated from index: 30d5706    Compiled by: Claude Fable 5.2, 2026-11-21

# Compiled spec: `purchasing`, chunk 3

## Purpose

`purchasing` owns the commercial documents of the buying side (requests, orders, service receipts, supplier invoices, their corrections and the GR/IR write-off) and sits in layer 4 (ADR-0022.R2). It does not own stock documents (`inventory`), the journal and open items (`ledger`), tax (`tax`), units and partners (`master_data`) or the agent runtime (`agents`). This chunk states the catalog rows of the commercial documents, the cumulative rule for parts of a line and the GR/IR rounding clearing, the purchase invoice agent's path from a verified PDF extraction, the near-duplicate review, the purchase invoice auto-post checker, the approved-request policy input, the document parties and the header note. As owner of the rest it also holds the invariants and edge cases whose rows stand in neither chunk 1 nor chunk 2. Agent types, budgets, the gateway's settings and master data are law of other modules; their units are traced `ref:` and not restated.

## Entities and tables

DDL: `docs/design/DS-22-09-42-commercial-inventory.sql`. The rules of this chunk define no table. The rows of `purchase_request`, `purchase_order`, `service_receipt` and their line tables stand in chunk 1; the rows of `purchase_invoice`, `purchase_invoice_line`, `purchase_return`, `purchase_return_line`, `purchase_credit_note`, `purchase_credit_note_line`, `purchase_debit_note`, `purchase_debit_note_line`, `gr_ir_write_off` and `gr_ir_write_off_line` stand in chunk 2. A `purchase_return_line` names its `return_to_supplier_line_id` (R415); `gr_ir_write_off_line` is kept in the inventory unit only (ADR-0056.R9).

Columns that the rules of this chunk put on headers of chunks 1 and 2:

- `purchase_order`, `purchase_invoice`, `purchase_return`, `purchase_credit_note`, `purchase_debit_note`: the party columns of `invoicing_party` and `payee` (R443, R444).
- `purchase_request`, `purchase_order`, `service_receipt`, `purchase_invoice`, `purchase_return`, `purchase_credit_note`, `purchase_debit_note`: `note` (R451).
- `purchase_request_line.estimated_unit_price` is not in the DDL yet; it is added at build step 5 (R440).

The document type `gr_ir_rounding_clearing` has a `document` row and no header or line table (R421).

Reads: `document`, `purchase_order_line_gr_ir_posting`, `return_to_supplier_line`, `goods_receipt_line`, `sales_return_line`, `return_from_customer_line`, `material_document_line`, `partner`, `partner_address`, `partner_relationship`, `partner_item`, `supplier_item`, `supplier_profile`, `customer_profile`, `open_item_collection`, `document_extraction`, `e_invoice_record`, `tax_line`, `agent_type_setting`.

## Commands and queries

| Name | Actor and authorization | Input | Effect | Events | Error codes |
| --- | --- | --- | --- | --- | --- |
| `Post` of `gr_ir_rounding_clearing` | The system only: `is_internal_only` and `is_consequence_posting`; leaf `gr_ir_rounding_clearing` under `purchasing` at level `full`, in no template's expansion | not stated | Posts or re-posts the clearing of a purchase order line (R418 to R422); the triggering command returns `gr_ir_rounding_cleared` or `gr_ir_rounding_clearing_reversed` | not stated | not stated |

Not registered commands:

- the pure function `master_data.contract.convert_part(f, C, P, q, unit, mode)`, called by every handler that posts a part (R424);
- the checker `purchasing.purchase_invoice_auto_post`, run by the gateway job (R434);
- the `purchasing` consumer of `DocumentExtractionVerified`, which raises `supplier_invoice_extracted` (R427).

Codes raised by the rules of this chunk and bound to no command named here: errors `quantity_rounds_to_zero` (R411, R413), `party_invalid` and `partner_role_missing` (R449), `agent_scope_unresolved` (R428), `open_item_payment_blocked` (R432), `duplicate_external_document` (R430, R437); check results `part_quantity_clamped` (R412), `part_quantity_recomputed` (R423), `quantity_rounded` (R417), `partner_snapshot_stale` (R450). R401 and R402 list the error codes and check results of the commercial documents as catalog rows.

## Rules

### Catalog rows of the commercial documents

R401. The catalogs hold the document type `gr_ir_write_off` (ADR-0047.R13) and the errors `quotation_expired`, `quantity_exceeds_open`, `invoice_exceeds_delivered`, `invoice_exceeds_ordered`, `receipt_exceeds_order`, `purchase_order_required`, `price_required`, `correction_exceeds_original`, `demand_on_hold`, `order_currency_mismatch`, `reversal_not_latest`, `demand_supply_not_released`, `sales_order_required`, `source_not_approved` and `partner_role_missing`.
Source: ADR-0047.R23, ADR-0047.R23.N1

R402. The check results of the commercial documents are `match_quantity_exceeded`, `match_price_difference`, `invoice_before_receipt` and `price_list_currency_differs` (ADR-0045.R5).
Source: ADR-0047.R23, ADR-0047.R23.N1

R403. Further catalog rows: the work item kinds `sales_return_due` (`sales`), `supplier_credit_due` (`purchasing`) and `credit_hold` (`sales`); the movement type `free_goods_issue`; the transaction keys `free_goods_cost` and `purchase_expense`; the policy condition `is_cost_unknown`.
Source: ADR-0047.R23, ADR-0047.R23.N1

R404. Settings of the commercial documents:
- company: `sales.reserve_on_approval`, `inventory.purchase_receipt_tolerance_percent`, `purchasing.match.quantity_tolerance_percent`, `purchasing.match.price_tolerance_percent`, `purchasing.match.price_tolerance_amount`, `purchasing.match.require_receipt`, `master_data.default_partner_group.customer`, `master_data.default_partner_group.supplier` and `master_data.default_partner_group.employee` (ADR-0045.R13);
- regime: `sales.discount_presentation` and the alternatives of `free_goods_cost`; the values a localization package seeds for them are flagged package content, `unverified`.
Source: ADR-0047.R23, ADR-0047.R23.N1

R405. Invariants of the commercial documents, all first checked at build step 5:
- `INV-40`, completed by the limits of ADR-0047.R20;
- `INV-90`: per sales order line, delivered net ≤ ordered;
- `INV-91`: per stock sales order line, invoiced net ≤ delivered net, or an open `sales_return_due` work item names the line;
- `INV-92`: per purchase order line, the GR/IR balance in the order's currency equals `round(V(I)) − round(V(R))` at the line's layers (ADR-0047.R13);
- `INV-93`: every line's price steps reproduce its stored net unit price and line amount.
Source: ADR-0047.R23

R406. Edge cases of the commercial documents: `EC-20`, `EC-21`, `EC-22` and `EC-63` take the outcomes of ADR-0047.R18, ADR-0047.R20 and ADR-0047.R22, which are confirmed as written (ADR-0047.R22.N4); `EC-69` is a purchase price change between two receipts, `EC-70` free goods with a document discount, and `EC-71` purchase invoices within and beyond the price tolerance. `edge-cases.csv` is authoritative.
Source: ADR-0047.R23, ADR-0047.R23.N2

R407. The lab check `t07_commercial.py` of the validation lab runs pure functions over: GR/IR on 600 random sequences of receipts, invoices, returns, credits, reversals and change orders with rounding to 0 and 2 decimals (the balance equals `round(V(I)) − round(V(R))` after every step and is zero whenever received equals invoiced; reversals of non-latest postings are refused); fixed GR/IR cases, including thirds of a unit, invoice first, a return after a change order, and the residual the receipt-price rule would leave; the pricing procedure with stored prices, the document discount allocation, free goods and the policy inputs after the document discount; correction limits and `EC-20`; three-way match tolerances; credit exposure, holds and the release by approval. It does not cover tables, locks and consumers, foreign-currency residuals or tax.
Source: ADR-0047.R24

### Parts add up: the cumulative rule

R408. A source line S has entered quantity q_S in unit U, factor f (the snapshot of S) and inventory quantity Q_S = round(q_S × f). Forward parts refer to S: receipts of a purchase order line, deliveries of a sales order line, invoices, and issues of a component line. Returns, credits and reversals refer to a posted part.
Source: ADR-0056.R10

R409. The source of an invoice is always the order line, for stock lines too: C and P count the order line's invoices, and the delivery or receipt line an invoice line names serves matching only.
Source: ADR-0056.R10

R410. Forward parts in U are converted at the snapshot of S. C is the actual net entered quantity in U of the posted parts of S (forward parts less their returns, credits and reversals), and P their actual net inventory quantity. A forward part of q has inventory quantity `round((C + q) × f) − P`, rounded in the mode of S (ADR-0056.R8). After any forward part P equals `round(C × f)`, whatever came before.
Source: ADR-0056.R10

R411. A forward part whose computed value is zero or less is rejected with `quantity_rounds_to_zero`, as a line with no source is; the error's `details` give the smallest entered quantity that would post. Refusing such a completing part closes nothing: it computes to zero or less only when P has already reached Q_S, so the line was fulfilled and closed at the earlier posting. A unit whose usual quantities fall below one inventory step is a master-data problem: stock belongs in the finer unit (ADR-0018.R11; the bar as a product unit, `nominal` when bar lengths vary), and `unit_step_below_inventory_step` flags such units when they are created (ADR-0056.R7).
Source: ADR-0056.R10

R412. A positive computed value is clamped to the band from `q × f − 1` to `q × f + 1` inventory units, the bounds rounded inward to the unit's decimals, with the check result `part_quantity_clamped` when the clamp changed it. The change counts in the line's unit rounding tolerance (R417), and the part stays within one inventory unit of its exact conversion for the database's gross-error check (ADR-0056.R9).
Source: ADR-0056.R10

R413. Returns, credits and reversals take the part they name as their source, in that part's unit. A reversal, or a return of the whole part, mirrors the part's stored inventory quantity. A partial return takes its cumulative share of the part: `round(v × (r₀ + r) / q) − v₀`, where q and v are the part's entered and stored inventory quantities and r₀ and v₀ what the part's earlier returns took. The returns of a part sum exactly to its stored inventory quantity and never exceed it, also when the part was clamped. A partial return whose share rounds to zero is rejected (`quantity_rounds_to_zero`); the small entered rest it leaves on the part is accepted. A return or credit in another unit converts on its own.
Source: ADR-0056.R10

R414. A return to supplier of a part of a purchase order line takes its inventory quantity from the part it names (R413) and moves GR/IR at the line's latest received positions (ADR-0047.R13). `return_to_supplier_line.gr_ir_position_from` and `gr_ir_position_to` store the positions actually debited, from R − q to R; `goods_receipt_line_id` stores the named part. Under the interim regime seed of `purchase_return` (value source `document`), the value that leaves stock is that GR/IR debit, `round(V(R)) − round(V(R − q))`, so the return posts no price difference (ADR-0020.R5). Lab check `t17_uom.py`, U70 and U71.
Source: ADR-0056.R10, ADR-0056.R10.N1

R415. A money return follows its stock return: a money-side return line that names a stock return line in the same unit and for the same entered quantity takes that stock line's inventory quantity. This holds for a `purchase_return_line` naming its `return_to_supplier_line` and a `sales_return_line` naming its `return_from_customer_line`; R and I then move by the same quantity, GR/IR stays zero, and on the sales side `sales_return_due` closes.
Source: ADR-0056.R10

R416. A forward part that brings C to q_S brings P to Q_S, unless a clamped part or a return, credit or reversal left a deviation, which stays within T(S); the returns of a part never exceed the part. Reversals need no order of their own: a part that a return or credit names cannot be reversed (`document_referenced`, ADR-0009.R18), and a mirrored reversal of an unreturned part only shifts C and P, which the next forward part corrects. GR/IR keeps its latest-only rule for documents with purchase order lines (ADR-0047.R13).
Source: ADR-0056.R10

R417. The unit rounding tolerance T(S):
- it grows by one smallest step of the inventory unit (10^−dI) for each part of S posted in another unit whose conversion rounded (`quantity_rounded`);
- it grows, for each return, credit or reversal of a part in U and each clamped forward part, by the amount that posting changed the deviation `P − round(C × f)` (nothing when the deviation is unchanged); the part being posted counts;
- it grows monotonically: a counted part that is later reversed stays counted; a return or credit adds less than three inventory units, a reversal or a clamp at most one unit plus one step;
- a part in another unit converts on its own (`round(q × its factor)`) and takes no part in C or P;
- it applies both ways: the upper limits `quantity_exceeds_open`, `receipt_exceeds_order` (after the receipt tolerance), `invoice_exceeds_delivered` and `correction_exceeds_original` allow T(S) more, and S counts as fulfilled by quantity when its fulfilled inventory quantity is within T(S) of Q_S;
- with an exact snapshot and none of these parts T(S) is zero and every comparison is exact.
Source: ADR-0056.R10

R418. The system posts `gr_ir_rounding_clearing` when a purchase order line is fulfilled within its tolerance and its received net R and invoiced net I both lie within T(S) of its inventory quantity but differ, or when a closed line's R and I differ by no more than T(S), whatever they stand at against Q_S. It runs only within T(S); a larger difference stays the closed-short path of ADR-0047.R13.
Source: ADR-0056.R10

R419. The clearing posts on the lagging side at the positions' value (ADR-0047.R13): on R, crediting GR/IR with `round(V(I)) − round(V(R))`, when I > R; on I, debiting it with `round(V(R)) − round(V(I))`, when R > I; against the regime's `price_difference` key (ADR-0047.R21). Its positions count in R or I for GR/IR, so `INV-92` holds with them, and never in received or invoiced quantities.
Source: ADR-0056.R10

R420. The clearing never counts in the latest-only reversal check of ADR-0047.R13, so it never blocks a reversal. Every later GR/IR posting on the line (a receipt, invoice, return, credit, reversal or `gr_ir_write_off`) first reverses an active clearing as a consequence, in the same transaction; the clearing fires again when the line is still, or again, within tolerance.
Source: ADR-0056.R10

R421. The document type `gr_ir_rounding_clearing` is registered as: `purchasing`, posting, internal, no change orders, not e-invoice capable, no approval hold, reversed only as a consequence (never by `Reverse`), not item-creating. Its `Post` is `is_internal_only` and `is_consequence_posting`; no template's expansion holds it, and its authorization leaf sits under purchasing at level `full`. It has its own `document` row (DS-05) and no header or line table: the `purchase_order_line_gr_ir_posting` row of kind `rounding_clearing` carries the line, positions and amount. The command that triggered it returns `gr_ir_rounding_cleared`, or `gr_ir_rounding_clearing_reversed`.
Source: ADR-0056.R10

R422. The clearing is the posting that makes R = I for the interim company-currency rule of ADR-0047.R13, so it also clears the line's company-currency residual: to realized exchange difference on a line without stock, and on a line for an item kept in stock as the setting `costing.exchange_rate_difference_to_stock` chooses (ADR-0047.R13.N3, ADR-0047.R13.N4); reversing the clearing reverses that entry too.
Source: ADR-0056.R10

R423. A part's inventory quantity is provisional on a draft and recomputed at Post from the then-posted C and P, under the source document's lock, as GR/IR postings are. A reservation or open pick task made for the provisional quantity is adjusted by the difference at Post. A pick task already confirmed at the provisional quantity is not changed: the difference becomes a follow-up warehouse task, an extra pick or a putaway back. Either way the check result `part_quantity_recomputed` names it for the warehouse. `INV-600` and `INV-601` apply to posted parts.
Source: ADR-0056.R10

R424. One function computes every part: `master_data.contract.convert_part(f, C, P, q, unit, mode)`, pure, called by every handler that posts a part; returns and credits call it with the part as source.
Source: ADR-0056.R10

### Supplier invoices from a PDF

R425. For a PDF-only supplier invoice the intake ladder parses an embedded XML first (rung 2); otherwise it uses the text layer, confirmed by OCR, and OCR words with the package's label anchors and the supplier's mapping rules (rungs 5 and 6); vision only where the seat is enabled.
Source: ADR-0057.R26

R426. Every required field of such an invoice is confirmed by a person; there is no automatic posting and no automatic match, and the extraction never reaches `extracted` from rungs 5 to 7.
Source: ADR-0057.R26

R427. A `purchasing` consumer of `DocumentExtractionVerified` raises `supplier_invoice_extracted` (subject the extraction) for a verified supplier-invoice extraction without an e-invoice record. Version 1.1.0 of the `purchase_invoice` agent type declares that kind and accepts `document_extraction` as a subject (ADR-0051.R20).
Source: ADR-0057.R26

R428. The run's scope is the supplier whose normalized tax ID equals the verified `seller_tax_id`, when exactly one active supplier has it; otherwise `agent_scope_unresolved`.
Source: ADR-0057.R26

R429. The run's inputs come from the current confirmed fields: `seller_tax_id`, `invoice_number` and the package's key fields as the partner reference, `issue_date` as the supplier invoice date, `currency`, `net_total`, `tax_amount`, `gross_total`, and per `lines[n]`: `seller_item_code`, `item_name` (free text, untrusted), `unit_text`, `quantity`, `unit_price`, `line_amount`, `tax_rate`.
Source: ADR-0057.R26

R430. The run's steps: D1 is the duplicate key check (ADR-0057.R15, `duplicate_external_document`), then D2 to D5 of ADR-0051.R21. The run starts tainted, as every run on an outside subject.
Source: ADR-0057.R26

### Near-duplicate invoices

R431. The near-duplicate check of ADR-0057.R15 reads the company settings `intake.duplicate.date_window_days` (7, bounds 0 to 90), `intake.duplicate.amount_tolerance_minor_units` (1, bounds 0 to 100), `intake.duplicate.number_normalization` (`digits_only`, the default, `alnum_casefold` or `exact`) and `intake.duplicate.near_outcome` (`review`, the default, or `advisory`).
Source: ADR-0063.R27

R432. Under outcome `review`, a purchase invoice posted while level 3 suspects a duplicate gets, in the transaction that posts it, `is_payment_blocked` and `payment_block_reason` `duplicate_review` on its `open_item_collection` row (ADR-0048.R17), and raises `duplicate_document_review`. A person resolves it by recording "not a duplicate" with a reason, which clears both columns in the transaction that resolves the work item, or by canceling or reversing the document, which leaves no open amount to pay. Until then a cash or bank payment cannot settle the item (`open_item_payment_blocked`, checked on the line and again at `Post`).
Source: ADR-0063.R27, ADR-0063.R27.N1

R433. The exact duplicate key cannot be switched off and runs on every channel (intake, manual entry, import, agent); a match is never deleted or rejected without a person.
Source: ADR-0063.R27

### The purchase invoice auto-post checker

R434. The checker `purchasing.purchase_invoice_auto_post`, version 1, is the first checker of the auto-post gateway: actor `system`, `runner: gateway_job`, `accepts_tainted: true`. It follows the purchase invoice manual path at build step 7 (ADR-0078.R8).
Source: ADR-0065.R19

R435. The checker's order match, supplier history and `partner_item` lookup use the ordered-from supplier (`partner_id`); its duplicate check uses the invoicing party (R447).
Source: ADR-0065.R19

R436. The checker's rules, in order; a failure gives `require_human` unless marked:
- `supplier_differs_from_order` (`reject`): a referenced purchase order belongs to another supplier than the invoice;
- `line_kind_not_matchable`: a line is not a `goods` line with an order line, or a `service` line with a service receipt (expense and landed-cost lines have no deterministic cross-check);
- `line_item_not_mapped`: a line's item is not the item that the supplier's approved `partner_item` or `supplier_item` row gives for the source record line's seller code, a lookup the checker repeats; an item an LLM chose (ADR-0051.R21, step L1) is `llm_read_only`;
- `supplier_history_below_minimum`: the supplier has fewer posted, unreversed purchase invoices in the company than `auto_post.purchase_invoice.min_supplier_invoices`;
- `price_outside_auto_post_tolerance`: a line's net unit price per inventory unit differs from the GR/IR price of the positions it reaches (ADR-0047.R13, ADR-0047.R14) by more than `auto_post.purchase_invoice.price_tolerance_percent`;
- `quantity_outside_auto_post_tolerance`: the invoiced net exceeds the received net by more than `auto_post.purchase_invoice.quantity_tolerance_percent`, or is invoiced before receipt;
- `order_not_fully_received`: while `auto_post.purchase_invoice.require_full_receipt` is true, a referenced order line's received net is below its ordered quantity;
- `duplicate_suspected`: the near-duplicate check (ADR-0057.R15; R431) suspects the invoice.
Source: ADR-0065.R19

R437. An exact duplicate key already fails the draft's simulation with `duplicate_external_document`, so the decision is `reject`. Open check results also stop an auto-post through ADR-0065.R5 (`match_quantity_exceeded`, `match_price_difference`, `invoice_before_receipt`, `tax_amount_differs_from_computed`), and the seeded `is_match_exceeded` rule requires an approval, so the first rule of ADR-0065.R5 fails too.
Source: ADR-0065.R19

R438. Bases of the checker's values: quantities and prices of a record with a passed signature are `trusted`; within tolerance of the order and receipt they are also `cross_checked`; the item is `trusted` only through `line_item_not_mapped`. On a failure the work item names the line, the order line, both prices and the tolerance.
Source: ADR-0065.R19

### Purchase orders within an approved request

R439. Approvals stay per document: a work case adds no approval object, stage or record, and one approval never counts for more than one document version (ADR-0055.R7). A company may let a purchase order need no approval of its own when the policy input `is_within_approved_request` is true: every order line comes from an approved purchase request line of the same item, its quantity is within the request line's open quantity, and its unit price does not exceed the request line's estimated price by more than a tolerance setting (default 0). The core seeds no rule that uses the input, so the default stays approval per document as each company configures it.
Source: ADR-0066.R20

R440. The estimated price is the column `purchase_request_line.estimated_unit_price` (in the request's currency), added with the input at build step 5; the open quantity of a request line is its `quantity` minus the quantity already ordered through `purchase_order_line.purchase_request_line_id`. The input and its tolerance setting are added to the catalogs with the purchase-order policy inputs at build step 5 (DS-22, DS-28); until then approval is per document.
Source: ADR-0066.R20

### Document parties

R441. A sales document keeps `partner_id` as the sold-to party (the buyer: price list, salesperson, payment term, currency and print language come from its profile) and may also name `ship_to` (where the goods go), `bill_to` (whose identity the invoice carries) and `payer` (who owes the money). A purchase document keeps `partner_id` as the ordered-from party and may also name `invoicing_party` (who issued the invoice and carries the payable) and `payee` (who receives the payment).
Source: ADR-0074.R1

R442. A party that is not stated is the next one up: `ship_to` and `bill_to` fall back to the sold-to party; `payer` to the bill-to party; `invoicing_party` to the ordered-from party; `payee` to the invoicing party.
Source: ADR-0074.R1

R443. Every party is stored as `<role>_partner_id`, `<role>_name` and, for `ship_to`, `bill_to` and `invoicing_party`, `<role>_address_id` and `<role>_address` (a `jsonb` snapshot with the keys of `partner_address`); `bill_to` and `invoicing_party` also carry `<role>_tax_id`. The columns follow the snapshot style of ADR-0028.R16: copied by `Create` and `Update`, part of the content, never changed by posting. A name exists exactly when the party is named (`ck_<table>_<role>`). The address is named by `(partner, address)` through the key `UNIQUE (company_id, partner_id, id)` on `partner_address`, so the database refuses an address of another partner.
Source: ADR-0074.R1

R444. The party columns sit on these headers:
- `ship_to`, `bill_to`, `payer`: `quotation`, `sales_order`;
- `ship_to`: `delivery` (it replaces the interim `delivery_address`);
- `bill_to`, `payer`: `sales_invoice`, `sales_return`, `credit_note`, `debit_note`;
- `invoicing_party`, `payee`: `purchase_order`, `purchase_invoice`, `purchase_return`, `purchase_credit_note`, `purchase_debit_note`.
Source: ADR-0074.R2

R445. Receipts, returns to suppliers, returns from customers and service receipts keep the one partner they have: a receipt is of what the ordered-from party delivered, whoever invoices it. A document made from another (an order to a delivery or an invoice, an invoice to its credit note) copies the parties of its source, which a person may change until posting.
Source: ADR-0074.R2

R446. Which party each consequence uses on the sales side:
- open item and its partner, the receivable control line, matching, allocation proposals, dunning and its recipients, statements: `payer`, else `bill_to`, else sold-to;
- credit exposure, credit hold, `customer_profile.credit_limit` and `receivable_account_id`: the same party; exposure sums the open items, invoices in `issuing`, delivered-not-invoiced value and undelivered order value whose payer resolves to it;
- tax identity (the partner tax status read by the tax treatment derivation, `tax_line.partner_tax_id`, the e-invoice buyer and the printed customer): `bill_to`, else sold-to;
- the address that gives the tax treatment's ship-to country and zone flag: the party of the setting `tax.destination_party` (`ship_to` by default, `bill_to` or `payer`), and for a service line `tax.services_place_of_supply` (ADR-0080.R3, ADR-0080.R5, ADR-0080.R6);
- delivery address and the delivery note's addressee: `ship_to`, else sold-to (the carrier stays the delivery method's, ADR-0068.R22);
- `document.partner_id`, the owner scope, CRM links, `INV-49`: sold-to;
- price list, salesperson, payment term, currency, print language, minimum remaining shelf life: sold-to.
Source: ADR-0074.R4, ADR-0074.R4.N1

R447. Which party each consequence uses on the purchase side:
- payable open item and control line, the supplier-invoice natural key and duplicate check, input tax identity: `invoicing_party`, else ordered-from;
- the payment's partner and the beneficiary's bank account (ADR-0028.R15): `payee`, else the invoicing party;
- GR/IR, supplier price list, buyer, lead times and the three-way match, which compares the invoice with the order and the receipt: ordered-from.
Source: ADR-0074.R4, ADR-0074.R4.N1

R448. The defaults that ADR-0068 copies from a profile (payment method, Incoterm, delivery method) come from the sold-to partner's customer profile on sales documents and from the ordered-from partner's supplier profile on purchase documents.
Source: ADR-0074.R4, ADR-0074.R4.N1

R449. A named party is an active partner of the company, and its address is one of its own (`party_invalid`). The party that carries the open item (payer, else bill-to, else sold-to; on purchases the invoicing party) must hold the `customer` or `supplier` role of the side, otherwise `partner_role_missing` (ADR-0047.R3).
Source: ADR-0074.R5

R450. The check `partner_snapshot_stale` (ADR-0028.R16) reads every named party the same way. A `payee` that is not the invoicing party, and a `payer` that is not the bill-to party, change who is paid and who is chased: their relationship rows are changed only through change proposals when an agent acts (ADR-0029.R4, as bank accounts).
Source: ADR-0074.R5

### Header note

R451. `document` and `document_version` hold no note (the version content is canonical JSON of the header and lines). A `note text` column (at most 4,000 characters) stands on the headers `quotation`, `sales_order`, `purchase_request`, `purchase_order`, `goods_receipt`, `return_to_supplier`, `delivery`, `return_from_customer`, `service_receipt`, `sales_invoice`, `sales_return`, `credit_note`, `debit_note`, `purchase_invoice`, `purchase_return`, `purchase_credit_note` and `purchase_debit_note`, and on the headers of ADR-0075. It is internal free text: content of the version, frozen at posting, untrusted for agents (ADR-0029), and printed only by a layout that names it (ADR-0049). Line `description` columns stay.
Source: ADR-0074.R16

## Invariants

Statements are those of `invariants.csv`. This chunk holds the rows whose catalog source is a rule stated here, or a rule of another module that a rule of the module names. `INV-40`, `INV-90`, `INV-91`, `INV-92` and `INV-93` (R405) have their rows in chunk 2, with ADR-0047.R13, ADR-0047.R16 and ADR-0047.R20.

| Invariant | Name | Check point | Statement | Protects |
| --- | --- | --- | --- | --- |
| `INV-49` | `document_partner_matches_header` | day | For every document type with a partner field, the shared document row's `partner_id` and `document_date` equal the typed header's values; types without one have both empty. Area `documents`. | R446; ADR-0052.R18 |
| `INV-88` | `taint_inherited` | day | Every document version written by a run tainted at its `recorded_at`, or whose origin run was, or whose previous or `derived_from_version_id` version was effectively tainted when it was written, has `is_tainted` true. Flagged: taint clearing (ADR-0029.R8). Area `safety`. | ADR-0047.R2.N3; ADR-0029.R8 |
| `INV-411` | `management_turnover_equals_report_turnover` | run | For full scope, every range and every system account subtree, each ledger analysis measure equals the turnover measure of ADR-0049.R6 over the operational accounts mapped to that subtree for the same range and `special_periods` option (`change`, `debit_turnover` or `credit_turnover`), with `closing_entries=exclude` for the profit-and-loss measures and migration entries left out, in every regime. Area `reporting`. | ADR-0027.R8.N1; ADR-0060.R4, ADR-0060.R35, ADR-0049.R7 |
| `INV-600` | `line_unit_snapshot_consistent` | day | Every quantity line carries its unit block; its snapshot equals `convert_quantity` for its item and unit when the unit was set (the item row, the product row or the global pair then in force), or its source line's snapshot for a line in the source's unit; its inventory quantity is `round_quantity(quantity x factor)` in the line's mode, or the cumulative value of `INV-601`. Area `documents`. | R423; ADR-0056.R6, ADR-0056.R9 |
| `INV-601` | `cumulative_parts_sum` | day | For every posted source line (for invoices, the order line), each forward part in its unit posted `round((C + q) × f) − P` at its snapshot, positive and clamped to between `q × f − 1` and `q × f + 1` inventory units (a value of zero or less is rejected), with C and P the actual net sums of the earlier posted parts in that unit; each return, credit or reversal of a part in the part's unit mirrors the part or takes its cumulative share of the part's stored inventory quantity, never exceeding it; a money-side return naming a stock return line in its unit and entered quantity posted that line's inventory quantity; T(S) grew only by rounded parts in other units and by the changes returns, credits, reversals and clamps made to the deviation; and when C reaches the source's entered quantity, P is within T(S) of its inventory quantity, and equal to it when T(S) is zero. Area `documents`. | R409 to R417 |
| `INV-718` | `duplicate_review_holds_payment` | day | Every purchase invoice ran the exact duplicate key on its channel, and every posted one suspected at level 3 under outcome review had its open item blocked for payment until the review was resolved. Area `safety`. | R432, R433 |
| `INV-863` | `payer_is_open_item_partner` | day | The open item of a posted sales invoice, credit note or debit note belongs to its payer, else its bill-to party, else its sold-to partner; the open item of a purchase document to its invoicing party, else its ordered-from partner. Area `receivables_payables`. | R446, R447 |
| `INV-864` | `document_party_complete` | day | Every named document party has its name; a tax ID, an address or an address key is held only with its party, and the address is one of the party's own; every party is a partner of the document's company; a party is named exactly when its name is. Area `documents`. | R443, R444 |

## Edge cases

Statements are those of `edge-cases.csv`. This chunk holds the rows of area `purchasing` whose catalog source is no rule of chunks 1 and 2, the rows whose source is a rule stated here, and `EC-21` and `EC-63` (R406), whose source rule ADR-0047.R18 belongs to `sales`. The catalog rows of `EC-21` and `EC-63` still read "Interim, flagged"; ADR-0047.R22.N4 confirms their outcomes, so the mark is not restated. `EC-20`, `EC-22`, `EC-69`, `EC-70` and `EC-71` (R406) have their rows in chunk 2; the rows of area `purchasing` sourced from ADR-0030 stand in chunk 1.

| Edge case | Name | Case | Outcome | Protects |
| --- | --- | --- | --- | --- |
| `EC-21` | `credit_limit_exceeded` | A sales order that would take a customer over its credit limit: approval at Submit; deliveries of other unreleased orders held. Area `documents`. | `must_succeed` | R406; ADR-0047.R18 |
| `EC-63` | `concurrent_orders_one_credit_limit` | Two orders of one customer are submitted at the same time; each credit check sees the other's exposure. Area `documents`. | `must_succeed` | R406; ADR-0047.R18 |
| `EC-81` | `supplier_invoice_line_unmapped` | A supplier e-invoice line has no `partner_item` mapping; the agent chooses among the supplier's related items, drafts the invoice and proposes the mapping; after approval the next invoice of that item maps without an LLM. | `must_succeed` | ADR-0051.R20, ADR-0051.R21, ADR-0051.R22 |
| `EC-101` | `carton_received_in_pieces` | An order of 10 cartons of 24 is received as 100 and 140 pieces and invoiced as 10 cartons; the order line is fulfilled and GR/IR is zero. | `must_succeed` | ADR-0056.R9, ADR-0056.R11 |
| `EC-102` | `bag_partial_receipts` | An order of 3 bags of 7/3 kg is received in receipts of 1 bag each: 2.333, 2.334 and 2.333 kg, summing to the ordered 7.000 kg; the invoice of 3 bags leaves GR/IR at zero. | `must_succeed` | R410 |
| `EC-106` | `e_invoice_unknown_unit_text` | A supplier e-invoice writes a unit text the company has never seen; the agent leaves the line unresolved with `unit_text_unresolved` and proposes an alias, which a person approves before the line is drafted. | `must_succeed` | ADR-0056.R19, ADR-0051.R21 |
| `EC-107` | `invoice_per_kg_against_bags` | Goods ordered and received in bags of 7/3 kg are invoiced per kg; quantity and price are matched per inventory unit. | `must_succeed` | ADR-0056.R11, ADR-0056.R12 |
| `EC-130` | `return_of_inexact_part` | Of the receipts of one bag of 7/3 kg each (2.333, 2.334, 2.333 kg) invoiced as 3 bags (7.000 kg), the second is returned and posts its own 2.334; the supplier's credit of 1 bag names that return line and posts the same 2.334, so R = I = 4.666 and GR/IR stays zero; a replacement receipt of one bag posts 2.334. On the sales side the same return and credit leave invoiced net equal to delivered net, and `sales_return_due` closes. | `must_succeed` | R413, R415 |
| `EC-132` | `e_invoice_xml_by_mail` | A supplier e-mails an XML e-invoice with its PDF to a mailbox with purpose `supplier_invoice`; the system imports the record, the agent starts in the supplier's scope, and the PDF whose text layer holds the invoice number is linked as the rendering, its extraction canceled by the system. | `must_succeed` | ADR-0057.R25 |
| `EC-133` | `e_invoice_resent_other_bytes` | The same invoice arrives again as other bytes with the same supplier-invoice key and a passed signature; the import is refused naming the first record. | `must_reject:duplicate_external_document` | ADR-0057.R15 |
| `EC-146` | `pdf_beside_xml_other_invoice` | A message carries an XML invoice and a PDF of a second invoice; the PDF matches neither by file name nor by number and is extracted as its own document. | `must_succeed` | ADR-0057.R25 |
| `EC-192` | `near_duplicate_payment_held` | A second invoice of the same seller, one minor unit apart and three days later, posts with its open item blocked for payment and a `duplicate_document_review`; resolving it as not a duplicate releases the block. | `must_succeed` | R432 |
| `EC-220` | `purchase_invoice_auto_post` | An agent-drafted invoice of a supplier with enough history matches its fully received order exactly; with the type live, tainted drafts enabled and the agent active, the gateway posts it as system and an `auto_post_unconfirmed` item asks the rule's owner to confirm. | `must_succeed` | R436; ADR-0065.R3, ADR-0065.R10 |
| `EC-221` | `purchase_invoice_price_variance` | A line 5% above the order price with a 1% tolerance gets `require_human`, and `auto_post_review` names `price_outside_auto_post_tolerance` with both prices. | `must_succeed` | R436, R438; ADR-0065.R4 |
| `EC-228` | `duplicate_invoice_rejected` | An agent drafts an invoice whose supplier invoice key is already posted; the simulation returns `duplicate_external_document`, the decision is `reject`, and the draft stays for a person. | `must_succeed` | R437; ADR-0065.R4 |
| `EC-243` | `purchase_chain_sod_in_case` | In a case, the approver of a purchase order tries to post its goods receipt from the case view and is refused with `segregation_of_duties` (`purchase_order_vs_goods_receipt`). Area `safety`. | `must_reject:segregation_of_duties` | R439; ADR-0054.R19 |
| `EC-310` | `invoice_head_office_and_payer` | An order with a ship-to site, a head-office bill-to party and a paying group: the delivery goes to the site, the invoice and its tax carry the head office, the open item and the credit exposure the group. Area `receivables_payables`. | `must_succeed` | R446 |
| `EC-311` | `party_defaults_from_relationships` | A partner with one default ship-to and no payer relationship gets the ship-to on a new order and no payer; changing the default does not touch an existing order. Area `documents`. | `must_succeed` | R441, R442; ADR-0074.R3 |
| `EC-312` | `party_stale_snapshot` | A bill-to party's address changes after the order; posting the invoice returns `partner_snapshot_stale` for that party. Area `documents`. | `must_succeed` | R450; ADR-0028.R16 |
| `EC-318` | `header_note_frozen` | A note written on a draft is part of its version and cannot change after posting; the journal entry carries a copy. Area `documents`. | `must_succeed` | R451; ADR-0074.R17 |
| `EC-319` | `payee_change_by_proposal` | An agent that changes a supplier's payee relationship directly is refused with `proposal_required`; its proposal executes after a person approves. Area `safety`. | `must_reject:proposal_required`, then `must_succeed` | R450; ADR-0029.R4 |

## Settings

| Key | Value type | Scopes | Core default | Used by |
| --- | --- | --- | --- | --- |
| `intake.duplicate.date_window_days` | integer (0..90) | `company` | 7 | R431 |
| `intake.duplicate.amount_tolerance_minor_units` | integer (0..100) | `company` | 1 | R431 |
| `intake.duplicate.number_normalization` | enum (`exact`, `alnum_casefold`, `digits_only`) | `company` | `digits_only` | R431 |
| `intake.duplicate.near_outcome` | enum (`advisory`, `review`) | `company` | `review` | R431, R432 |
| `auto_post.purchase_invoice.min_supplier_invoices` | integer (3..1000) | `company` | 10 | R436 |
| `auto_post.purchase_invoice.price_tolerance_percent` | percent (0..10) | `company` | 0 | R436 |
| `auto_post.purchase_invoice.quantity_tolerance_percent` | percent (0..10) | `company` | 0 | R436 |
| `auto_post.purchase_invoice.require_full_receipt` | boolean | `company` | `true` | R436 |

Keys the module names that have no row in `settings.csv` (stated here once for all chunks): the `purchasing` keys `purchasing.match.quantity_tolerance_percent`, `purchasing.match.price_tolerance_percent`, `purchasing.match.price_tolerance_amount` and `purchasing.match.require_receipt` (R404; company settings, defaults 0 and false, flagged, as chunk 2 states with ADR-0047.R14); and keys of other modules: `sales.reserve_on_approval`, `sales.discount_presentation`, `inventory.purchase_receipt_tolerance_percent`, `master_data.default_partner_group.customer`, `master_data.default_partner_group.supplier`, `master_data.default_partner_group.employee` (R404) and `documents.issuance_without_delay` (ADR-0047.R1.N1, chunk 1). The tolerance setting of R439 has no key yet (R440).

Reads: `tax.destination_party`, `tax.services_place_of_supply`, `auto_post.<document_type>.mode`, `auto_post.<document_type>.max_amount_company`, `auto_post.<document_type>.allowed_currencies`, `auto_post.<document_type>.allow_tainted`, `auto_post.<document_type>.require_verified_values`, `auto_post.allow_tainted_drafts`, `auto_post.confirmation_cadence`, `auto_post.max_error_rate`, `agents.<agent_type>.wake_up_mode.<kind>`, `agents.<agent_type>.drift_action`, `agents.tainted_reference_reads`, `assist.max_cost_per_run`, `cash.auto_post.accept_llm_originated_rules`, `cash.bank_charge.auto_post_ceiling`, `movement_type.purchase_return.value_source`, `movement_type.purchase_return.costing_role`, `movement_type.purchase_return.include_landed_cost`.

## UI annotations

The sources of this chunk state no floorplan, title, facet, field annotation or tile. Work item kinds of `purchasing` raised by its rules:

| Kind | Subject table | Owner | Due | Resolution | Rule |
| --- | --- | --- | --- | --- | --- |
| `supplier_invoice_extracted` | `document_extraction` | `role:accountant` | `days:2` | `person` | R427 |
| `duplicate_document_review` | `document` | `role:accountant` | `days:2` | `person` | R432 |

Neither is agent-resolvable. `supplier_credit_due` (R403) has its row with ADR-0047.R15 in chunk 2. The catalog `work-case-kinds.csv` also holds the work case kind `supplier_invoice` of module `purchasing`, triggered by `supplier_invoice_received`; its rules are law of `work` (ADR-0066.R3).

## Conflicts

CONFLICT ADR-0047.R23: the outcomes of the edge cases EC-20, EC-21, EC-22 and EC-63 are no longer interim or flagged for the author; ADR-0047.R22.N4 confirms rules 18, 20 and 22 as written (R406).
CONFLICT ADR-0074.R4: ADR-0074.R4.N1 governs the tax identity row: the partner tax status read by the tax treatment derivation replaces the partner tax group read by the tax matrix, and the destination address follows the settings of ADR-0080 (R446, R447).
CONFLICT ADR-0056.R10: the clearing's residual goes to realized exchange difference only on a line without stock; on a line for an item kept in stock ADR-0047.R13.N3 and ADR-0047.R13.N4 govern through the setting `costing.exchange_rate_difference_to_stock` (R422).
CONFLICT ADR-0065.R19: the index places the checker at build step 6; ADR-0078.R8 corrects this to step 7, after the purchase invoice manual path (R434).

## Proposed (not law)

None

## Trace

| Source | Where |
| --- | --- |
| ADR-0047.R23 | R401-R406 |
| ADR-0047.R23.N1 | R401-R404 |
| ADR-0047.R23.N2 | R406 |
| ADR-0047.R24 | R407 |
| ADR-0050.R12 | ref: ADR-0050.R12 |
| ADR-0050.R12.N1 | ref: ADR-0050.R12.N1 |
| ADR-0050.R12.N2 | ref: ADR-0050.R12.N2 |
| ADR-0050.R12.N4 | ref: ADR-0050.R12.N4 |
| ADR-0051.D0 | ref: ADR-0051.D0 |
| ADR-0051.D0.N1 | ref: ADR-0051.D0.N1 |
| ADR-0051.D0.N2 | ref: ADR-0051.D0.N2 |
| ADR-0051.D0.N3 | ref: ADR-0051.D0.N3 |
| ADR-0051.D0.N4 | ref: ADR-0051.D0.N4 |
| ADR-0051.R5.N3 | ref: ADR-0051.R5.N3 |
| ADR-0051.R7 | ref: ADR-0051.R7 |
| ADR-0051.R7.N1 | ref: ADR-0051.R7.N1 |
| ADR-0051.R7.N2 | ref: ADR-0051.R7.N2 |
| ADR-0051.R7.N3 | ref: ADR-0051.R7.N3 |
| ADR-0051.R9 | ref: ADR-0051.R9 |
| ADR-0051.R9.N1 | ref: ADR-0051.R9.N1 |
| ADR-0051.R9.N2 | ref: ADR-0051.R9.N2 |
| ADR-0051.R9.N3 | ref: ADR-0051.R9.N3 |
| ADR-0051.R9.N4 | ref: ADR-0051.R9.N4 |
| ADR-0051.R9.N5 | ref: ADR-0051.R9.N5 |
| ADR-0051.R20.N1 | ref: ADR-0051.R20.N1 |
| ADR-0051.R21 | ref: ADR-0051.R21 |
| ADR-0051.R21.N1 | ref: ADR-0051.R21.N1 |
| ADR-0051.R22.N1 | ref: ADR-0051.R22.N1 |
| ADR-0054.R14 | ref: ADR-0054.R14 |
| ADR-0054.R14.N1 | ref: ADR-0054.R14.N1 |
| ADR-0055.R3 | ref: ADR-0055.R3 |
| ADR-0056.R9 | ref: ADR-0056.R9 |
| ADR-0056.R10 | R408-R424 |
| ADR-0056.R10.N1 | R414 |
| ADR-0057.R26 | R425-R430 |
| ADR-0059.R1.N1 | ref: ADR-0059.R1.N1 |
| ADR-0063.R24 | ref: ADR-0063.R24 |
| ADR-0063.R27 | R431-R433 |
| ADR-0063.R27.N1 | R432 |
| ADR-0063.E.N1 | ref: ADR-0063.E.N1 |
| ADR-0065.R2 | ref: ADR-0065.R2 |
| ADR-0065.R8 | ref: ADR-0065.R8 |
| ADR-0065.R11 | ref: ADR-0065.R11 |
| ADR-0065.R11.N1 | ref: ADR-0065.R11.N1 |
| ADR-0065.R19 | R434-R438 |
| ADR-0066.R20 | R439-R440 |
| ADR-0068.R15 | ref: ADR-0068.R15 |
| ADR-0068.R19 | ref: ADR-0068.R19 |
| ADR-0068.R22 | ref: ADR-0068.R22 |
| ADR-0068.R22.N1 | ref: ADR-0068.R22.N1 |
| ADR-0074.R1 | R441-R443 |
| ADR-0074.R2 | R444-R445 |
| ADR-0074.R4 | R446-R448 |
| ADR-0074.R4.N1 | R446-R448 |
| ADR-0074.R5 | R449-R450 |
| ADR-0074.R7 | ref: ADR-0074.R7 |
| ADR-0074.R7.N1 | ref: ADR-0074.R7.N1 |
| ADR-0074.R7.N2 | ref: ADR-0074.R7.N2 |
| ADR-0074.R16 | R451 |
| ADR-0077.R23.N1 | ref: ADR-0077.R23.N1 |
| ADR-0078.D0 | ref: ADR-0078.D0 |
| ADR-0078.R1 | ref: ADR-0078.R1 |
| ADR-0078.R1.N1 | ref: ADR-0078.R1.N1 |
| ADR-0078.R8 | ref: ADR-0078.R8 |
| ADR-0078.R9a | ref: ADR-0078.R9a |
| ADR-0078.R13.N1 | ref: ADR-0078.R13.N1 |
| ADR-0078.R15 | ref: ADR-0078.R15 |
