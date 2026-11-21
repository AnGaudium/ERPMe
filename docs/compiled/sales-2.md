Module: sales    Chunk: 2 of 2    Source ADRs: ADR-0047, ADR-0048, ADR-0057, ADR-0074
Build step(s): 0, 2, 5, 7    Generated from index: 30d5706    Compiled by: Claude Fable 5.2, 2026-11-21

# `sales` compiled spec, chunk 2: credit holds, demand and supply rows, cumulative limits, postings, policy inputs, catalog rows, inquiry attachments, document parties

## Purpose

`sales` owns the customer-side commercial documents: quotations, sales orders, sales invoices, sales returns, credit notes, debit notes and promotions (chunk 1). This chunk states credit exposure and credit holds, the demand and supply rows of order lines, the cumulative limits, the postings by transaction key, the policy inputs, the catalog rows and lab check of ADR-0047, the quotation lines read from an inquiry spreadsheet, and the document parties and header note of ADR-0074. Rules that ADR-0047 and ADR-0074 give to `sales` together with `purchasing` or `inventory` are stated in full here and in those modules. `sales` never posts stock: `inventory` owns the demand rows, deliveries and returns from customers. Agent workflows, document owners, units of measure and payment, Incoterm and delivery master data belong to other modules and are traced `ref:`.

## Entities and tables

DDL: `docs/design/DS-22-09-42-commercial-inventory.sql`.

| Table | Meaning | Key | Parent | Owner |
| --- | --- | --- | --- | --- |
| `credit_hold` | The credit hold or credit release of one sales order: the limit and the exposure at the check, the state, the release (`release_kind` `approval` or `manual`) and the `credit_hold` work item (R203, R204, R209 to R211). The DDL column `released_order_amount` is marked interim: ADR-0047 does not state it | `id`; (`company_id`, `id`) | `sales_order` | `sales` |

The rules of this chunk add to, or constrain, tables whose rows stand in chunk 1: the party columns and `note` on `quotation`, `sales_order`, `sales_invoice`, `sales_return`, `credit_note` and `debit_note` (R244, R245, R249); the lines `quotation_line`, `sales_order_line`, `sales_invoice_line`, `sales_return_line`, `credit_note_line` and `debit_note_line` under the limits of R216 to R218; `promotion` is not changed here.

Reads: `partner`, `partner_address`, `partner_relationship`, `customer_profile` (`credit_limit`, `receivable_account_id`), `supplier_profile`, `document`, `document_version`, `work_item`, `open_item`, `tax_line`, `delivery`, `return_from_customer`, `return_from_customer_line`, `goods_receipt`, `return_to_supplier`, `return_to_supplier_line`, `service_receipt`, `purchase_request`, `purchase_order`, `purchase_invoice`, `purchase_return`, `purchase_return_line`, `purchase_credit_note`, `purchase_debit_note`, `purchase_order_line_gr_ir_posting`, `landed_cost`, `payment_method`, `delivery_method`, `payment`, `agent_type`, `agent_type_version`, `policy_rule_version`, `setting_value`, `company`.

## Commands and queries

| Name | Actor and authorization | Input | Effect | Events | Error codes |
| --- | --- | --- | --- | --- | --- |
| `GetCreditExposure` (query) | People and agents; area and level not stated | A partner | Returns the credit exposure that `sales.contract.get_credit_exposure(partner)` composes, also for a partner without `credit_limit` (R201, R202) | None (query) | not stated |
| `ReleaseCreditHold` | `human_only`; its own permission; segregated from the order's author (ADR-0043.R13); area and level not stated | A sales order and a required reason | Releases the order's credit hold until the order's value grows by a change order; effect class `other`; resolves the `credit_hold` work item (R209, R210) | not stated | not stated |
| `GetQuotationLinesFromExtraction` (computed query) | Leaf `quotation` at `read` | An extracted or verified extraction | Returns proposed quotation lines and the unresolved rows; writes nothing (R240) | None (query) | not stated |

Not commands, declared or run by `sales`: the contract function `sales.contract.get_credit_exposure(partner)` (R201); the consumer that clears credit holds on events that lower exposure, among them `OpenItemSettled` (R206, R207). `sales` calls `inventory.contract.set_demand_supply_hold(rows, reason, is_held)` (R204, R205). The sales order's `Submit`, approval, `Reject` and take-force of a change order, and the posting of an invoice, are commands of chunk 1 that R203 to R205 extend.

Codes raised by the rules of this chunk: `correction_exceeds_original` (R219); `party_invalid` and `partner_role_missing` (R248); the check result `partner_snapshot_stale` (R248); the check result `formula_cell_found` (R239). `inventory` raises `demand_on_hold` and `demand_supply_not_released` (R205, R208). R233 and R234 list the catalog rows of ADR-0047.

## Rules

### Credit exposure and credit holds

R201. `sales.contract.get_credit_exposure(partner)` composes the parts of ADR-0030.R6 per currency. It converts them to the limit's currency at rate type `transaction` on the check date (ADR-0011.R11; flagged). The query `GetCreditExposure` exposes it to people and agents. Exposure, the hold and `customer_profile.credit_limit` are those of the payer (else the bill-to party, else the sold-to partner; ADR-0074.R4).
Source: ADR-0047.R18, ADR-0047.R18.N5

R202. A customer profile without `credit_limit` has no credit check: `is_credit_exceeded` is false and no `credit_hold` is set for that partner; `GetCreditExposure` still reports the exposure. `CreatePartner` leaves the limit empty unless the payload gives one (ADR-0045.R13); a company that wants every customer checked sets a limit on each profile.
Source: ADR-0047.R18.N4

R203. The sales order's `Submit` locks as ADR-0030.R7 says: classes 1–8, then the partner row (class 9). It reads the exposure with the order included, and passes `is_credit_exceeded` to the policy hook. An order approved while `is_credit_exceeded` was true records that approval as its credit release; it is not held afterwards for the exposure it was approved with. So an order that would take a customer over its credit limit needs approval at `Submit` (`EC-21`), and of orders submitted at the same time each credit check sees the other's exposure (`EC-63`).
Source: ADR-0047.R18, ADR-0047.R22.N4

R204. Every `sales` command that raises a partner's exposure re-evaluates it under the same locks and updates holds in the same transaction through `inventory.contract.set_demand_supply_hold(rows, reason, is_held)`: submit, approval, take-force of a change order, and posting an invoice. Over the limit, it sets `credit_hold` on the open demand rows of the partner's approved orders without a release; under the limit, it clears them. The demand rows held are those of the orders that resolve to the payer (ADR-0074.R4). These row updates take no document lock of the other orders: the hold is a flag on `inventory`'s rows, set or cleared by a row update that does not conflict with other changes to those orders. A delivery that read no hold just before the hold lands still posts; that race is accepted (flagged).
Source: ADR-0047.R18, ADR-0047.R18.N1, ADR-0047.R18.N5

R205. A hold has a reason. `inventory.contract.set_demand_supply_hold(rows, reason, is_held)` takes the reasons `not_approved` and `credit_hold`, stored as a set on each demand or supply row. Sales order demand rows and purchase order supply rows are created unreleased (`not_approved`, R215). `sales` and `purchasing` release them when the document is approved, or at `Submit` when no approval is required, and set `not_approved` again on `Reject`. `inventory` rejects pick release, delivery and receipt of a row held `not_approved` with `demand_supply_not_released`, and of a row held `credit_hold` with `demand_on_hold`; it never reads `sales` or `purchasing`.
Source: ADR-0047.R18.N1

R206. Events that lower exposure (payments and credits through DS-25, cancel and close) are handled by a `sales` consumer, which clears holds. A lowered credit limit (a `master_data` change, which cannot call `sales`) is handled the same way, which leaves a short window before holds land (flagged).
Source: ADR-0047.R18

R207. Settlements lower credit exposure: `OpenItemSettled` (ledger) reaches the `sales` consumer that clears credit holds (R206). The exposure and the holds it clears are those of the payer, as ADR-0030.R6 reads (ADR-0074.R4). The tax evidence consumer reads the same event (ADR-0041.R15).
Source: ADR-0048.R19, ADR-0048.R19.N1

R208. `inventory` rejects pick release and delivery of held lines (`demand_on_hold`) and never reads `sales`. `PostDelivery` is not `is_policy_in_handler`, and credit is not checked at `PostDelivery`.
Source: ADR-0047.R18

R209. `ReleaseCreditHold` (a sales order) is `human_only`, with its own permission, a required reason, and segregation from the order's author (ADR-0043.R13). Its effect class is `other`. The release lasts until the order's value grows by a change order.
Source: ADR-0047.R18

R210. When `sales` sets `credit_hold` on an order's rows, it raises one work item `credit_hold` (subject the sales order, owner role `accountant`). The item is resolved by `ReleaseCreditHold`, or by the system when the hold is cleared because the exposure fell under the limit.
Source: ADR-0047.R18.N2

R211. The stored states of a `credit_hold` row are `held`, `released`, `cleared` and `lapsed` (`docs/design/DS-22-09-42-commercial-inventory.sql`). They are interim: ADR-0047.R18 does not name them.
Source: ADR-0047.R18.N3

### Demand and supply rows

R212. Sales order lines get demand rows at `Submit` (ADR-0024.R8; ADR-0031.R5). Take-force adjusts them. Close or cancel closes them (`closed_reason`).
Source: ADR-0047.R19

R213. Purchase request and purchase order lines get supply rows from draft (ADR-0047.R10). A request line's open quantity falls as orders are created from it.
Source: ADR-0047.R19

R214. Delivered and received quantities are read from the demand and supply rows. Invoiced quantities, including those of documents in `issuing`, are computed from invoice lines.
Source: ADR-0047.R19

R215. Demand rows of sales order lines and supply rows of purchase order lines carry the hold reason `not_approved` until the document is approved (R205). Unreleased demand rows are not demand: planning, available to promise and reservations ignore them, and `Reject` sets `not_approved` on them again, so a rejected order is never demand and never reserves. Supply rows from draft stay supply for planning (ADR-0047.R10; ADR-0024.R8), released or not, but goods are received against them only once released.
Source: ADR-0047.R19.N1

### Cumulative limits

R216. Per delivery or receipt line: returned ≤ delivered or received (checked by `inventory`). This and R217 and R218 are the cumulative limits of ADR-0009.R23 and complete `INV-40`.
Source: ADR-0047.R20

R217. Per invoice line: quantity credited (by `sales_return`, `purchase_return` or a quantity credit) ≤ invoiced; amount credited ≤ the line's net amount less earlier credits.
Source: ADR-0047.R20

R218. Per order line:
- delivered or received net ≤ ordered (with the receipt tolerance);
- for stock sales order lines, invoiced net ≤ delivered net, except while a `sales_return_due` work item is open;
- for purchase order lines, invoiced net may exceed received net (invoice before receipt, ADR-0047.R14, unless `purchasing.match.require_receipt`), and a stock return that leaves it above raises `supplier_credit_due` (ADR-0047.R15);
- the quantity credited by returns ≤ the returned quantity not yet credited.
Source: ADR-0047.R20

R219. A violation of the limits of R216 to R218 is rejected with `correction_exceeds_original`. Documents in `issuing` count. Every limit compares inventory quantities and allows the unit rounding tolerance of the source line. That tolerance grows by one smallest inventory step per part posted in another unit whose conversion rounded, and by the change each return, credit, reversal or clamped part made to the deviation `P − round(C × f)`; it never shrinks, and with an exact snapshot it stays zero, so every limit is exact (ADR-0056.R10).
Source: ADR-0047.R20, ADR-0047.R20.N1

R220. When a return makes invoiced net exceed delivered net on an order line, a `sales_return` for the difference is due (ADR-0047.R7): a sales return work item is raised for the invoiced share (`EC-20`). Returned goods that were never invoiced reduce what remains to invoice.
Source: ADR-0047.R20, ADR-0047.R22.N4

### Postings by transaction key

R221. Sales-side documents post by transaction key (ADR-0015):
- Delivery: debit `cost_of_goods_sold` (free goods: `free_goods_cost`); credit inventory.
- Return from customer: debit inventory; credit `cost_of_goods_sold` (regime value).
- Sales invoice: debit `receivable_reconciliation` per installment; credit `revenue_posting`, `output_tax`; discounts by ADR-0047.R6.
- Sales return: debit `revenue_deduction_return`, `output_tax`; credit `receivable_reconciliation` (credit item).
- Credit note: debit by reason (ADR-0047.R8), `output_tax`; credit `receivable_reconciliation` (credit item).
- Debit note: debit `receivable_reconciliation`; credit `revenue_posting`, `output_tax`.
Source: ADR-0047.R21

R222. Purchase-side documents post by transaction key (ADR-0015):
- Goods receipt: debit inventory; credit `gr_ir_clearing` (ADR-0047.R13).
- Purchase invoice, goods: debit `gr_ir_clearing` (ADR-0047.R13), price difference (`price_difference` or `purchase_cost_clearing`), `input_tax`; credit `payable_reconciliation` per installment.
- Purchase invoice, service with a service receipt: debit `gr_ir_clearing`, price difference (ADR-0037.R6), `input_tax`; credit `payable_reconciliation`.
- Purchase invoice, service without one, or expense: debit expense by determination, `input_tax`; credit `payable_reconciliation`.
- Purchase invoice, landed cost: debit `input_tax` and, as the setting `landed_cost.unplanned_cost_treatment` chooses (ADR-0021.R12.N2), `purchase_cost_clearing` under `distribute_to_items` (the default) or the account determined by `purchase_expense` under `separate_account` (interim until step 5; never stock); credit `payable_reconciliation`.
- Return to supplier: debit `gr_ir_clearing` (ADR-0047.R13), and price difference if the regime's stock value differs; credit inventory.
- Purchase return: debit `payable_reconciliation`; credit `gr_ir_clearing` (ADR-0047.R13), price difference, `input_tax`.
- Supplier credit note: debit `payable_reconciliation`; credit `gr_ir_clearing` for quantity lines (ADR-0047.R13), price difference for price lines, `input_tax`.
- Supplier debit note: debit price difference, `input_tax`; credit `payable_reconciliation`.
- GR/IR write-off (closed line, `R > I`): debit `gr_ir_clearing` (ADR-0047.R13); credit price difference.
- Release at order close (invoice-first): debit `purchase_cost_clearing`; credit `price_difference` (ADR-0030.R4).
Source: ADR-0047.R21

R223. On a goods line with a price difference, an invoice of `q` debits GR/IR with `round(V(I + q)) − round(V(I))`, `I` being the invoiced net before it (ADR-0047.R13), and the invoice amount less that is the price difference. Where the regime sends `price_difference` for the item's valuation class to an inventory account, the invoice posts the difference to `purchase_cost_clearing` instead (ADR-0021.R12), and in the same transaction `inventory.contract.adjust_receipt_value` writes a `landed_cost` with `cost_type` `price_difference`, `posted`, targeting the receipt line (ADR-0030.R1), which moves the difference from `purchase_cost_clearing` into the receipt's stock value (`inventory_posting`). A price difference sent to stock for a receipt of an earlier period posts as the note on ADR-0021.R6 says; the method `consumer_split` is not used for it. A regime that sends `price_difference` to an expense account posts the difference there on the invoice, with no landed cost. The accounts are flagged package content of the localization package (`unverified`, DS-19).
Source: ADR-0047.R21.N1, ADR-0047.R21.N3

R224. `gr_ir_rounding_clearing` posts GR/IR against `price_difference` at the positions' value, as a consequence posting (ADR-0056.R10).
Source: ADR-0047.R21.N2

### Policy inputs

R225. The policy input of each document type (ADR-0043.R4) holds the amount: the document total in company currency at the applied rate.
Source: ADR-0047.R22

R226. `discount_percent` is (Σ quantity × list price − net amount after the document discount) ÷ Σ quantity × list price. Lines without a list price count at their base price; free goods count at their list price.
Source: ADR-0047.R22

R227. `margin_percent` is (net amount − cost) ÷ net amount, in company currency, with the cost of free goods included. Cost per inventory unit is the preliminary price in the line's valuation area (ADR-0020.R11), or the configuration estimate (ADR-0046.R14). An unknown cost leaves margin unknown, and the decision needs a human.
Source: ADR-0047.R22

R228. `is_price_below_cost` is true when a paid line's net amount after the document-discount allocation (ADR-0047.R16, step 7), divided by its inventory quantity and converted to company currency at the applied rate, is below its cost per inventory unit. Free goods are excluded. This is the one definition; the "net unit price" of ADR-0045.R5 gives way to it. A sales price below cost has no fixed outcome: it follows the company's policy rules on `is_price_below_cost` (`EC-22`).
Source: ADR-0047.R22, ADR-0047.R22.N1, ADR-0047.R22.N4

R229. `is_price_outside_list` is true when a line's base price differs from its list price, or it has none.
Source: ADR-0047.R22

R230. `is_credit_exceeded` belongs to the policy input of sales orders only (ADR-0047.R4, R203), and `is_match_exceeded` to that of purchase invoices. Quotations have no credit condition: a quotation creates no demand, reservation or exposure (ADR-0047.R3). The quotation agent's `GetCreditExposure` finding is information in its note (ADR-0051.R15); credit is checked when the order is submitted.
Source: ADR-0047.R22, ADR-0047.R22.N3

R231. `is_cost_unknown` is true when a paid line's cost per inventory unit is unknown: no preliminary price and, for a line without an item or preliminary price, no computable configuration estimate (ADR-0046.R14). `margin_percent` is then unknown and the line does not count as below cost, so rules on margin and below cost do not match; the seeded rule on `is_cost_unknown` requires approval instead (ADR-0043.R3, ADR-0043.R15).
Source: ADR-0047.R22.N2

R232. Cost and margin on documents are field classes `cost` and `margin` (ADR-0017.R10).
Source: ADR-0047.R22

### Catalog rows and lab check of ADR-0047

R233. ADR-0047 adds the document type `gr_ir_write_off` (ADR-0047.R13) and these errors: `quotation_expired`, `quantity_exceeds_open`, `invoice_exceeds_delivered`, `invoice_exceeds_ordered`, `receipt_exceeds_order`, `purchase_order_required`, `price_required`, `correction_exceeds_original`, `demand_on_hold`, `order_currency_mismatch`, `reversal_not_latest`, `demand_supply_not_released`, `sales_order_required`, `source_not_approved` and `partner_role_missing` (ADR-0047.R2, ADR-0047.R3, ADR-0047.R6, R205).
Source: ADR-0047.R23, ADR-0047.R23.N1

R234. Further catalog rows of ADR-0047:
- check results: `match_quantity_exceeded`, `match_price_difference`, `invoice_before_receipt` and `price_list_currency_differs` (ADR-0045.R5);
- work item kinds: `sales_return_due` (`sales`), `supplier_credit_due` (`purchasing`) and `credit_hold` (`sales`, R210);
- movement type `free_goods_issue` and transaction keys `free_goods_cost` and `purchase_expense` (ADR-0047.R12);
- policy condition `is_cost_unknown` (R231).
Source: ADR-0047.R23, ADR-0047.R23.N1

R235. Settings of ADR-0047:
- company: `sales.reserve_on_approval`, `inventory.purchase_receipt_tolerance_percent`, `purchasing.match.quantity_tolerance_percent`, `purchasing.match.price_tolerance_percent`, `purchasing.match.price_tolerance_amount`, `purchasing.match.require_receipt`, and `master_data.default_partner_group.customer`, `master_data.default_partner_group.supplier` and `master_data.default_partner_group.employee` (ADR-0045.R13);
- regime: `sales.discount_presentation`, and the alternatives of `free_goods_cost`; their values are flagged content of a localization package (`unverified`).
Source: ADR-0047.R23, ADR-0047.R23.N1

R236. Invariants of ADR-0047, all first at step 5:
- `INV-40` completed: the limits of R216 to R219;
- `INV-90`: per sales order line, delivered net ≤ ordered;
- `INV-91`: per stock sales order line, invoiced net ≤ delivered net, or an open `sales_return_due` work item names the line;
- `INV-92`: per purchase order line, the GR/IR balance in the order's currency equals `round(V(I)) − round(V(R))` at the line's layers (ADR-0047.R13);
- `INV-93`: every line's price steps reproduce its stored net unit price and line amount.
Source: ADR-0047.R23

R237. Edge cases of ADR-0047: `EC-20`, `EC-21`, `EC-22` and `EC-63` have the outcomes of R220, R203 and R228. `EC-69` is a change order that changes a purchase price between two receipts and an invoice; `EC-70` a promotion with free goods and a document discount; `EC-71` purchase invoices within and beyond the price tolerance. `docs/catalogs/edge-cases.csv` is authoritative.
Source: ADR-0047.R23, ADR-0047.R23.N2, ADR-0047.R22.N4

R238. The lab check `t07_commercial.py` (validation lab) covers, as pure functions:
- GR/IR on 600 random sequences of receipts, invoices, returns, credits, reversals and change orders, with rounding to 0 and 2 decimals: the balance equals `round(V(I)) − round(V(R))` after every step, and is zero whenever received equals invoiced; reversals of non-latest postings are refused;
- fixed GR/IR cases, including thirds of a unit, invoice first, a return after a change order, and the residual the receipt-price rule would leave;
- the pricing procedure with stored prices, the document discount allocation, free goods, and the policy inputs after the document discount;
- correction limits and `EC-20`; three-way match tolerances; credit exposure, holds and the release by approval.
It does not cover tables, locks and consumers, foreign-currency residuals, or tax.
Source: ADR-0047.R24

### Inquiry attachments

R239. Inquiry spreadsheets: rung 4 reads cell values into rows `lines[n].*` with cell evidence. Headers map by exact header, then by the partner's `column_header` rules; merged headers are unmerged by position. A cell with a formula is read as its cached value with the check result `formula_cell_found`. A cell beginning with `=`, `+`, `-` or `@` is kept as text and never evaluated.
Source: ADR-0057.R28

R240. `GetQuotationLinesFromExtraction` (module `sales`, computed query, at `read` on `quotation`) turns the rows of an extracted or verified extraction into proposed quotation lines: item by the partner's item code, the company's item code or a barcode, each as a whole value; unit by the partner item's unit text, the unit aliases or a unit code; quantity as stated. Unresolved rows are returned as such. A person creates or updates the quotation from the result; no row becomes a line without a person.
Source: ADR-0057.R28

R241. Drawings and PDF requests are stored, shown beside the quotation and not read in Phase 1 unless the vision seat is enabled for the company.
Source: ADR-0057.R28

### Document parties

R242. A sales document keeps `partner_id` as the sold-to party (the buyer: price list, salesperson, payment term, currency and print language come from its profile) and may name further parties: `ship_to` (where the goods go), `bill_to` (whose identity the invoice carries) and `payer` (who owes the money). A purchase document keeps `partner_id` as the ordered-from party and may name `invoicing_party` (who issued the invoice and carries the payable) and `payee` (who receives the payment).
Source: ADR-0074.R1

R243. A party that is not stated is the next one up: `ship_to` and `bill_to` fall back to the sold-to party; `payer` to the bill-to party; `invoicing_party` to the ordered-from party; `payee` to the invoicing party. A customer with one account therefore carries no new value on its documents.
Source: ADR-0074.R1

R244. Every party is `<role>_partner_id`, `<role>_name` and, for `ship_to`, `bill_to` and `invoicing_party`, `<role>_address_id` and `<role>_address` (a `jsonb` snapshot with the keys of `partner_address`); `bill_to` and `invoicing_party` also carry `<role>_tax_id`. The columns are the snapshot style of ADR-0028.R16: copied by `Create` and `Update`, part of the content, never changed by posting. A name exists exactly when the party is named (`ck_<table>_<role>`). The address is named by `(partner, address)` through the key `UNIQUE (company_id, partner_id, id)` on `partner_address`, so an address of another partner is refused by the database.
Source: ADR-0074.R1

R245. The party columns sit on these headers:
- `ship_to`, `bill_to`, `payer`: `quotation`, `sales_order`;
- `ship_to`: `delivery` (it replaces the interim `delivery_address`);
- `bill_to`, `payer`: `sales_invoice`, `sales_return`, `credit_note`, `debit_note`;
- `invoicing_party`, `payee`: `purchase_order`, `purchase_invoice`, `purchase_return`, `purchase_credit_note`, `purchase_debit_note`.
Source: ADR-0074.R2

R246. Receipts, returns to suppliers, returns from customers and service receipts keep the one partner they have: a receipt is of what the ordered-from party delivered, whoever invoices it. A document made from another (an order to a delivery or an invoice, an invoice to its credit note) copies the parties of its source, which a person may change until posting.
Source: ADR-0074.R2

R247. Each consequence uses this party:
- open item and its partner, the receivable control line, matching, allocation proposals, dunning and its recipients, statements: `payer`, else `bill_to`, else sold-to;
- credit exposure, credit hold, `customer_profile.credit_limit` and `receivable_account_id`: the same party; exposure sums the open items, invoices in `issuing`, delivered-not-invoiced value and undelivered order value whose payer resolves to it;
- tax identity (the partner tax status read by the tax treatment derivation, `tax_line.partner_tax_id`, the e-invoice buyer and the printed customer): `bill_to`, else sold-to; on purchases the invoicing party;
- the address that gives the tax treatment's ship-to country and zone flag: the party of the setting `tax.destination_party` (`ship_to` by default, `bill_to` or `payer`), and for a service line `tax.services_place_of_supply` (ADR-0080.R3, ADR-0080.R5, ADR-0080.R6);
- delivery address and the delivery note's addressee (the carrier stays the delivery method's, ADR-0068.R22): `ship_to`, else sold-to;
- `document.partner_id`, the owner scope, CRM links, `INV-49`: sold-to, unchanged;
- price list, salesperson, payment term, currency, print language, minimum remaining shelf life: sold-to;
- purchases, payable open item and control line, the supplier-invoice natural key and duplicate check, input tax identity: `invoicing_party`, else ordered-from;
- purchases, the payment's partner and the beneficiary's bank account (ADR-0028.R15): `payee`, else the invoicing party;
- purchases, GR/IR, supplier price list, buyer, lead times, three-way match (it compares the invoice with the order and the receipt): ordered-from;
- defaults that ADR-0068 copies from a profile (payment method, Incoterm, delivery method): the sold-to partner's customer profile on sales documents; the ordered-from partner's supplier profile on purchase documents.
Source: ADR-0074.R4, ADR-0074.R4.N1

R248. A named party is an active partner of the company, and its address is one of its own (`party_invalid`). The party that carries the open item (payer, else bill-to, else sold-to; on purchases the invoicing party) must hold the `customer` or `supplier` role of the side, otherwise `partner_role_missing` (ADR-0047.R3). The check `partner_snapshot_stale` (ADR-0028.R16) reads every named party the same way. A `payee` that is not the invoicing party, and a `payer` that is not the bill-to party, change who is paid and who is chased: their relationship rows are changed only through change proposals when an agent acts (ADR-0029.R4, as bank accounts).
Source: ADR-0074.R5

R249. `document` and `document_version` hold no note (the version content is canonical JSON of the header and lines). A `note text` column (at most 4,000 characters) is on the headers `quotation`, `sales_order`, `purchase_request`, `purchase_order`, `goods_receipt`, `return_to_supplier`, `delivery`, `return_from_customer`, `service_receipt`, `sales_invoice`, `sales_return`, `credit_note`, `debit_note`, `purchase_invoice`, `purchase_return`, `purchase_credit_note` and `purchase_debit_note`, and on the headers of ADR-0075. It is internal free text: content of the version, frozen at posting, untrusted for agents (ADR-0029), and printed only by a layout that names it (ADR-0049). Line `description` columns stay.
Source: ADR-0074.R16

## Invariants

Statements are those of `invariants.csv`. This chunk holds the rows whose catalog source is a rule of this chunk or of another module; chunk 1 holds `INV-93`. "Protects" names a rule of this chunk or the source ID of a rule stated elsewhere.

| Invariant | Name | Check point | Statement | Protects |
| --- | --- | --- | --- | --- |
| `INV-40` | `corrections_within_original` | day | Cumulative corrections never exceed the original: returned per delivery line within delivered, credited quantity per invoice line within invoiced, credited amount within the line's net amount, and the same for purchase lines. | R216 to R219; ADR-0009.R23 |
| `INV-88` | `taint_inherited` | day | Every document version written by a run tainted at its `recorded_at`, or whose origin run was, or whose previous or `derived_from_version_id` version was effectively tainted when it was written, has `is_tainted` true. Flagged in the catalog: taint clearing (ADR-0029.R8). | ADR-0029.R8; ADR-0047.R2.N2 |
| `INV-90` | `sales_delivered_within_ordered` | day | Per sales order line, delivered net of returns never exceeds the ordered quantity. | R218 |
| `INV-91` | `sales_invoiced_within_delivered` | day | Per stock sales order line, invoiced net of quantity credits never exceeds delivered net of returns, unless an open `sales_return_due` work item names the line. Purchase lines may be invoiced before receipt (ADR-0047.R14). | R218, R220 |
| `INV-92` | `gr_ir_equals_rounded_positions` | day | Per purchase order line, the GR/IR balance in the order's currency equals `round(V(I)) - round(V(R))` at the line's position layers, V being the exact value of positions up to a quantity and rounding to the currency's minor unit; it is zero when received net equals invoiced net. | ADR-0047.R13; ADR-0030.R5; R236 |
| `INV-49` | `document_partner_matches_header` | day | For every document type with a partner field, the shared document row's `partner_id` and `document_date` equal the typed header's values; types without one have both empty. | ADR-0052.R18; R247 |
| `INV-600` | `line_unit_snapshot_consistent` | day | Every quantity line carries its unit block; its snapshot equals `convert_quantity` for its item and unit when the unit was set (the item row, the product row or the global pair then in force), or its source line's snapshot for a line in the source's unit; its inventory quantity is `round_quantity(quantity x factor)` in the line's mode, or the cumulative value of `INV-601`. | ADR-0056.R6, ADR-0056.R9 |
| `INV-601` | `cumulative_parts_sum` | day | For every posted source line (for invoices, the order line), each forward part in its unit posted `round((C + q) × f) − P` at its snapshot, positive and clamped to between `q × f − 1` and `q × f + 1` inventory units (a value of zero or less is rejected), with C and P the actual net sums of the earlier posted parts in that unit; each return, credit or reversal of a part in the part's unit mirrors the part or takes its cumulative share of the part's stored inventory quantity, never exceeding it; a money-side return naming a stock return line in its unit and entered quantity posted that line's inventory quantity; T(S) grew only by rounded parts in other units and by the changes returns, credits, reversals and clamps made to the deviation; and when C reaches the source's entered quantity, P is within T(S) of its inventory quantity, and equal to it when T(S) is zero. | ADR-0056.R10; R219 |
| `INV-863` | `payer_is_open_item_partner` | day | The open item of a posted sales invoice, credit note or debit note belongs to its payer, else its bill-to party, else its sold-to partner; the open item of a purchase document to its invoicing party, else its ordered-from partner. | R247 |
| `INV-864` | `document_party_complete` | day | Every named document party has its name; a tax ID, an address or an address key is held only with its party, and the address is one of the party's own; every party is a partner of the document's company; a party is named exactly when its name is. | R242, R244, R245 |

## Edge cases

Cases are those of `edge-cases.csv`. The catalog rows of `EC-20`, `EC-21`, `EC-22` and `EC-63` still read "Interim, flagged"; ADR-0047.R22.N4 confirms their outcomes (R203, R220, R228). `EC-70` stands in chunk 1.

| Edge case | Name | Case | Outcome | Protects |
| --- | --- | --- | --- | --- |
| `EC-20` | `return_of_partly_invoiced_goods` | A customer returns goods of which only part was invoiced: a sales return for the invoiced share is due; uninvoiced returned goods reduce what remains to invoice. | `must_succeed` | R220 |
| `EC-21` | `credit_limit_exceeded` | A sales order that would take a customer over its credit limit: approval at `Submit`; deliveries of other unreleased orders held. | `must_succeed` | R203, R204 |
| `EC-22` | `price_below_cost` | A sales price below the item's current cost: `is_price_below_cost` feeds the policy; the outcome is the company's rules. | `must_succeed` | R228 |
| `EC-63` | `concurrent_orders_one_credit_limit` | Two orders of one customer are submitted at the same time; each credit check sees the other's exposure. | `must_succeed` | R203; ADR-0030.R7 |
| `EC-69` | `purchase_price_change_between_receipts` | A change order changes a purchase price between two receipts; the invoice clears GR/IR at each position's first-posted price, and a return after the change takes the latest positions. | `must_succeed` | ADR-0047.R13; R237 |
| `EC-71` | `purchase_invoice_match_tolerance` | One supplier invoice within the price tolerance posts without approval; another beyond it needs approval through `is_match_exceeded`. | `must_succeed` | ADR-0047.R14; R237 |
| `EC-310` | `invoice_head_office_and_payer` | An order with a ship-to site, a head-office bill-to party and a paying group: the delivery goes to the site, the invoice and its tax carry the head office, the open item and the credit exposure the group. | `must_succeed` | R247 |
| `EC-311` | `party_defaults_from_relationships` | A partner with one default ship-to and no payer relationship gets the ship-to on a new order and no payer; changing the default does not touch an existing order. | `must_succeed` | R242, R243; ADR-0074.R3 |
| `EC-312` | `party_stale_snapshot` | A bill-to party's address changes after the order; posting the invoice returns `partner_snapshot_stale` for that party. | `must_succeed` | R248; ADR-0028.R16 |
| `EC-318` | `header_note_frozen` | A note written on a draft is part of its version and cannot change after posting; the journal entry carries a copy. | `must_succeed` | R249; ADR-0074.R17 |
| `EC-319` | `payee_change_by_proposal` | An agent that changes a supplier's payee relationship directly is refused with `proposal_required`; its proposal executes after a person approves. | `must_reject:proposal_required` for the direct change; `must_succeed` for the proposal | R248; ADR-0029.R4 |

Reads: the agent edge cases `EC-57`, `EC-79`, `EC-80`, `EC-83`, `EC-87`, `EC-185` and `EC-227` (ADR-0078.R9a) belong to `agents`; those that start from the deferred `quotation` and `customer_onboarding` agents cannot run in Phase 1.

## Settings

None: `docs/catalogs/settings.csv` holds no row whose key or area is of `sales`; the keys `sales.reserve_on_approval` and `sales.discount_presentation`, named by R235, are stated in chunk 1.

Keys of other modules named by R235 and R218 but absent from `settings.csv`: `inventory.purchase_receipt_tolerance_percent`, `purchasing.match.quantity_tolerance_percent`, `purchasing.match.price_tolerance_percent`, `purchasing.match.price_tolerance_amount`, `purchasing.match.require_receipt`, `master_data.default_partner_group.customer`, `master_data.default_partner_group.supplier` and `master_data.default_partner_group.employee`. Their value types, scopes beyond "company" or "regime" (R235) and core defaults are not stated by the rules of this chunk.

Reads: `tax.destination_party` and `tax.services_place_of_supply` (R247); `documents.e_invoice_required` (ADR-0053.R8; `documents.issuance_without_delay` is stated in chunk 1); `agents.<agent_type>.wake_up_mode.<kind>` (ADR-0050.R12); `agents.<agent_type>.daily_max_cost` and `agents.<agent_type>.daily_max_runs` (ADR-0051.R9); `auto_post.max_error_rate`, `cash.bank_charge.auto_post_ceiling` and `cash.bank_charge.codes` (ADR-0063.R3).

## UI annotations

The sources of this chunk state no floorplan, title, facet, field annotation or tile. Work item kinds of `sales` (`work-item-kinds.csv`):

| Kind | Subject table | Owner | Due | Resolution | Rule |
| --- | --- | --- | --- | --- | --- |
| `credit_hold` | `sales_order` | `role:accountant` | `days:1` | `command`: `ReleaseCreditHold`, or the system when the hold is cleared | R210 |

It is not agent-resolvable. The kind `sales_return_due` (R218, R220) has its row in chunk 1.

## Conflicts

CONFLICT ADR-0047.R18.N1: the hold function is `inventory.contract.set_demand_supply_hold(rows, reason, is_held)` with a set of hold reasons, not `set_demand_hold` with one flag; ADR-0047.R18.N1 governs, stated in R204 and R205.
CONFLICT ADR-0047.R18: the closing clause that leaves the outcomes of EC-21 and EC-63 interim is dropped, because ADR-0047.R22.N4 confirms approval at Submit with the other unreleased orders held (R203); the flags on the rate type, the delivery race and the consumer window are kept; ADR-0047.R18.N5 moves the exposure, the holds, `customer_profile.credit_limit` and the held demand rows from the partner to the payer (else the bill-to party, else the sold-to partner; ADR-0074.R4), stated in R201 and R204.
CONFLICT ADR-0047.R20: the mark "interim and flagged, the author confirms" on the EC-20 bullet is dropped; ADR-0047.R22.N4 confirms that a sales return work item is raised for the invoiced share (R220).
CONFLICT ADR-0047.R22: ADR-0047.R22.N4 turns the policy inputs from a proposal awaiting the author into a decision; EC-22 follows the company's policy rules on is_price_below_cost (R228).
CONFLICT ADR-0047.R23: its edge-case bullet calls the outcomes of EC-20, EC-21, EC-22 and EC-63 interim and flagged for the author; ADR-0047.R22.N4 governs and R237 states them as decided.
CONFLICT ADR-0047.R21: its row "Purchase invoice, landed cost: debit `purchase_cost_clearing`" holds only under `landed_cost.unplanned_cost_treatment` `distribute_to_items`; ADR-0021.R12.N2 governs, and under `separate_account` the line debits the account determined by `purchase_expense` (R222).
CONFLICT ADR-0047.R21.N3: the closed-period branch of the worked example (method consumer_split) no longer applies; ADR-0047.R21.N3 governs and R223 sends a late price difference to the posting of the ADR-0021 rule 6 note.
CONFLICT ADR-0048.R19.N1: the exposure and holds cleared by OpenItemSettled are those of the payer, not of the document partner; ADR-0048.R19.N1 governs, following ADR-0074.R4 (R207).
CONFLICT ADR-0074.R4.N1: the table row on tax identity is replaced by the text of ADR-0074.R4.N1, with partner tax status, the tax treatment derivation and the setting for the destination party (R247).

## Proposed (not law)

None

## Trace

| Source | Where |
| --- | --- |
| ADR-0047.R18 | R201, R203, R204, R206, R208, R209 |
| ADR-0047.R18.N1 | R204, R205 |
| ADR-0047.R18.N2 | R210 |
| ADR-0047.R18.N3 | R211 |
| ADR-0047.R18.N4 | R202 |
| ADR-0047.R18.N5 | R201, R204 |
| ADR-0047.R19 | R212, R213, R214 |
| ADR-0047.R19.N1 | R215 |
| ADR-0047.R20 | R216, R217, R218, R219, R220 |
| ADR-0047.R20.N1 | R219 |
| ADR-0047.R21 | R221, R222 |
| ADR-0047.R21.N1 | R223 |
| ADR-0047.R21.N2 | R224 |
| ADR-0047.R21.N3 | R223 |
| ADR-0047.R22 | R225, R226, R227, R228, R229, R230, R232 |
| ADR-0047.R22.N1 | R228 |
| ADR-0047.R22.N2 | R231 |
| ADR-0047.R22.N3 | R230 |
| ADR-0047.R22.N4 | R203, R220, R228, R237 |
| ADR-0047.R23 | R233, R234, R235, R236, R237 |
| ADR-0047.R23.N1 | R233, R234, R235 |
| ADR-0047.R23.N2 | R237 |
| ADR-0047.R24 | R238 |
| ADR-0048.R19 | R207 |
| ADR-0048.R19.N1 | R207 |
| ADR-0050.R12 | ref: ADR-0050.R12 |
| ADR-0050.R12.N1 | ref: ADR-0050.R12.N1 |
| ADR-0050.R12.N2 | ref: ADR-0050.R12.N2 |
| ADR-0050.R12.N4 | ref: ADR-0050.R12.N4 |
| ADR-0051.D0 | ref: ADR-0051.D0 |
| ADR-0051.D0.N1 | ref: ADR-0051.D0.N1 |
| ADR-0051.D0.N2 | ref: ADR-0051.D0.N2 |
| ADR-0051.D0.N3 | ref: ADR-0051.D0.N3 |
| ADR-0051.D0.N4 | ref: ADR-0051.D0.N4 |
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
| ADR-0051.R15 | ref: ADR-0051.R15 |
| ADR-0051.R15.N1 | ref: ADR-0051.R15.N1 |
| ADR-0051.R15.N2 | ref: ADR-0051.R15.N2 |
| ADR-0051.R15.N3 | ref: ADR-0051.R15.N3 |
| ADR-0051.R15.N4 | ref: ADR-0051.R15.N4 |
| ADR-0051.R15.N5 | ref: ADR-0051.R15.N5 |
| ADR-0053.R8 | ref: ADR-0053.R8 |
| ADR-0053.R8.N1 | ref: ADR-0053.R8.N1 |
| ADR-0054.R14 | ref: ADR-0054.R14 |
| ADR-0054.R14.N1 | ref: ADR-0054.R14.N1 |
| ADR-0056.R10 | ref: ADR-0056.R10 |
| ADR-0056.R10.N1 | ref: ADR-0056.R10.N1 |
| ADR-0057.R28 | R239, R240, R241 |
| ADR-0057.R31 | ref: ADR-0057.R31 |
| ADR-0063.R3 | ref: ADR-0063.R3 |
| ADR-0063.R3.N1 | ref: ADR-0063.R3.N1 |
| ADR-0063.R3.N2 | ref: ADR-0063.R3.N2 |
| ADR-0068.R15 | ref: ADR-0068.R15 |
| ADR-0068.R19 | ref: ADR-0068.R19 |
| ADR-0068.R22 | ref: ADR-0068.R22 |
| ADR-0068.R22.N1 | ref: ADR-0068.R22.N1 |
| ADR-0074.R1 | R242, R243, R244 |
| ADR-0074.R2 | R245, R246 |
| ADR-0074.R4 | R247 |
| ADR-0074.R4.N1 | R247 |
| ADR-0074.R5 | R248 |
| ADR-0074.R16 | R249 |
| ADR-0078.R2 | ref: ADR-0078.R2 |
| ADR-0078.R9a | ref: ADR-0078.R9a |
