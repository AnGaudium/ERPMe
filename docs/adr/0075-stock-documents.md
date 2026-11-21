# ADR-0075: Stock documents

Status: accepted (2026-11-21) under ADR-0005, reviewed by Claude Fable 5.2 (builder Claude Sonnet 5.5; proposed 2026-11-19) after three review rounds, the fixes verified by Claude Opus 5.5.
Design items: DS-09 (stock documents), DS-22, DS-42 (warehouse management), DS-58 (quality). Related decisions: none new. Principles 6, 12. ADR-0004, ADR-0006, ADR-0009, ADR-0014, ADR-0015, ADR-0020, ADR-0023, ADR-0024, ADR-0027, ADR-0028, ADR-0031, ADR-0034, ADR-0044, ADR-0056, ADR-0061, ADR-0063, ADR-0067, ADR-0069, ADR-0070, ADR-0074.

## Decision

ADR-0020 rules 4 to 7 and 18, ADR-0023 rules 7 and 18 and ADR-0027 rule 7 describe four stock documents, and ADR-0027 rule 7 promised their DDL in a "DS-09 stock documents deliverable, written before step 3". No DDL file defines them: only the material document layer and the warehouse tasks exist, and ADR-0070 rule 15 already drafts `scrap` and `internal_consumption` documents and names them in `inspection_lot_execution.target_table`. This ADR writes the four, each as a typed header with lines in the pattern of `goods_receipt` (ADR-0009 rule 1), reversible, posting one material document and its journal entry through the posting interfaces.

| Document | Header and lines | Movement types | Key choice |
| --- | --- | --- | --- |
| Stock transfer | `stock_transfer`, `stock_transfer_line` | `transfer_out`, `transfer_in` | One document type with three steps (`direct`, `dispatch`, `receive`) |
| Stock count | `stock_count`, `stock_count_line` | `stock_count_shortage`, `stock_count_surplus` | The book quantity is stored on each line at the freeze; the difference is counted minus book |
| Scrap | `scrap`, `scrap_line` | `scrap` | A reason of kind `scrap`, required while `documents.reason_required.scrap` is true (review note, 2026-11-21); the held status the goods leave |
| Internal consumption | `internal_consumption`, `internal_consumption_line` | `internal_consumption`, `quality_sample` | Exactly one cost center or project, except a quality sample |
| Other receipt | `other_receipt`, `other_receipt_line` | `other_receipt` | Valued from the document; a reason of kind `other_receipt` |
| Other issue | `other_issue`, `other_issue_line` | `other_issue` | A reason of kind `other_issue`; at most one cost center or project |
| Opening balance | `opening_balance`, `opening_balance_line` | `opening_balance` | Migration period only; its value sets the first preliminary price |
| Transfer order | `transfer_order`, `transfer_order_line` | none (non-posting) | The planned move that stock transfers fulfil |

No movement type is added: the catalog of ADR-0020 rule 4 already holds every one of them (`docs/catalogs/movement-types.csv`). Rules 11 to 15 (the remaining documents and the count settings) were added on 2026-11-19 by the chief architect's decision for the author.

### Rules

**The four documents**

1. **Stock transfer** (`inventory`). The header names `from_warehouse_id` and `to_warehouse_id` (different), a `step`, an optional `reference` (the sender's or the carrier's) and a `note` (ADR-0074 rule 16). A line names the item, the unit block of ADR-0056 rule 9, the lot or serial (never both), the `from_bin_id` and `to_bin_id` and, optionally, a handling unit. Transfers move `available` stock only (the allowed status of `transfer_out` and `transfer_in`, ADR-0023 rule 7), so a line has no status; held stock is released by a `status_change` first. The bins are optional: outside bin-managed warehouses the default bin applies (ADR-0031 rule 8), and in bin-managed warehouses the source bin is the non-pickable bin the confirmed picks moved the goods to, the receiving bin the default receiving bin until putaway (ADR-0023 rules 7, 14, 15). The pick tasks that precede `transfer_out` and the putaway task after `transfer_in` are created as for a delivery and a receipt.
   - **Reservations.** A transfer is a voluntary issue: `transfer_out` is refused with `stock_reserved` when it would cut into reservations (ADR-0023 rule 13).
   - **`direct`.** One document between two physical warehouses: each line posts `transfer_out` and `transfer_in` in one material document, at the issuing value, with both journal lines (ADR-0020 rule 6).
2. **Through transit** (ADR-0023 rule 7, ADR-0020 rule 1). A transfer to a warehouse of kind `transit` or `goods_sent` is two documents:
   - **`dispatch`** posts `transfer_out` from the source and `transfer_in` into the transit warehouse. Its stock is owned and valued there (the keys `inventory_in_transit_posting` and `inventory_goods_sent_posting`).
   - **`receive`** names its dispatch (`dispatch_transfer_id`). At most one live receive per dispatch (a receive that is not canceled and not reversed) is enforced by the command under the dispatch's lock and checked by INV-867; the index on `dispatch_transfer_id` is not unique, because the document state is on another table (review note, 2026-11-21) and posts out of the transit warehouse and into the destination. Each of its lines names a dispatch line (`dispatch_line_id`) of the same item, lot, serial and handling unit, and receives no more than that line sent (INV-867). The handling unit keeps its identity.
   - **Value of the `receive`.** The transit warehouse is an ordinary valuation node. The `receive`'s `transfer_out` takes the transit warehouse's value as any issue does (the preliminary price during the period and the actual cost at period end, ADR-0020 rule 6 and the `transfer` costing role), so a transit balance left by a price change between the two steps is cleared by the period-end costing run, not by a rule of its own. (review note, 2026-11-21)
   - **A short receipt** leaves the rest in the transit warehouse, where it is visible as stock, until a count of the transit warehouse, with a reason of kind `count_difference`, or a reversal of the dispatch settles it. A write-off document waits for a concrete need (decided 2026-11-19).
   - **Warehouse kinds** are held by INV-868: `direct` between two physical warehouses, `dispatch` into a transit or goods-sent warehouse, `receive` out of the dispatch's.
   - **Reversal.** A transfer is reversible (ADR-0020 rule 7): a reversal repeats the lines in the opposite direction, is refused with `negative_stock` when the stock has moved on (ADR-0020 rule 10), and a `dispatch` with a posted `receive` cannot be reversed before it (`dispatch_has_receive`). The open question on whether a package requires an internal transport document keeps its place in `open-questions.md`; the core flag is `is_reversible` true.
3. **Stock count** (`inventory`). One count document counts one warehouse. Each line is one counted entry:
   - **The key** of a line is (item, bin, lot or serial, status); `bin_id` is required (the default bin outside bin-managed warehouses). Several lines may share a key, each entered in the product's counting unit with the unit block and summed in the inventory unit (ADR-0056 rule 15; ADR-0020 rule 18 note).
   - **The book quantity.** `book_quantity` and `book_taken_at` store the stock of the key at the freeze, in the inventory unit: the confirmation of the count task when the warehouse has tasks, else the creation of the draft (ADR-0023 rule 18). Every line of a key holds the same book quantity, time and difference reason (INV-865). A key with no stock has book 0, so a surplus found where nothing was booked is a line.
   - **What is counted.** A key with no line is not counted and posts nothing. A counted zero is a line with quantity 0. Serials are counted one by one: quantity 0 or 1.
   - **The difference** of a key is the sum of its counted quantities minus its stored book quantity. Posting posts that, so a pick or a putaway between the freeze and the posting never becomes a difference (ADR-0023 rule 18). A positive difference posts `stock_count_surplus`, a negative one `stock_count_shortage`, valued as ADR-0020 rules 5 and 11 say (a surplus at the preliminary price, else `preliminary_price_missing`). INV-866 ties the posted movements to the differences.
   - **Task link.** `count_task_id` names the confirmed count task that created the line, when there is one (ADR-0023 rule 18).
   - **Reasons.** `difference_reason_id` (kind `count_difference`, ADR-0074 rule 13) and `difference_note` explain a difference; both are optional in the database; the reason is required while the setting is true (review note, 2026-11-21), and it is the same on every line of a key (INV-865). Whether a key with a difference must have a reason is the company setting `documents.reason_required.count_difference` (core default true; `reason_required`, ADR-0074 rule 22); when it is false, a report shows a difference without a reason as unexplained.
   - **Bin netting.** The regime setting `stock_count.bin_difference_method` of ADR-0023 rule 18 is unchanged: netting corrects the bins by warehouse movements with `source_command` `count_correction`, and INV-866 holds either way because it sums per (item, warehouse, lot or serial).
   - **Posting** runs through the normal lifecycle with policy and approval (ADR-0009 rules 11, 13). A shortage and a physical fact always post and cancel reservations deterministically (ADR-0023 rule 13). The material lines name the key's lowest `line_number` as `source_line_number`.
   - **Reversal.** A count is reversible (ADR-0020 rule 7): the opposite movements are refused with `negative_stock` when a surplus has been consumed.
4. **Scrap** (`inventory`). A line names the item, the quantity, the bin, the lot or serial, the status the goods leave (`stock_status`, so held goods are scrapped from `blocked` or `quality_inspection` as ADR-0070 rule 15 drafts them), an optional handling unit, a scrap reason (`scrap_reason_id`, kind `scrap`), required while `documents.reason_required.scrap` is true, the core default (`reason_required`, ADR-0074 rule 22), with an optional `reason_note` (a scrap drafted by the quality executor takes its reason from the usage decision line, ADR-0070 rule 15; review note, 2026-11-21), and optionally one cost center or one project (never both) when the regime's account determination reads it. It posts `scrap` (preliminary price, revalued issue, offset key `scrap`). Scrap is a voluntary issue: it is refused with `stock_reserved` when it would cut into reservations (ADR-0023 rule 13). A line created by the quality executor carries the held status and the inspection lot's link through `inspection_lot_execution.target_table` (DS-58); nothing else of the document is special.
5. **Internal consumption** (`inventory`). A line is `internal` or a `quality_sample` (`consumption_kind`), and names exactly one cost center or project that bears it; a quality sample may name none, because a sample destroyed by testing is issued by a draft that the quality executor creates and a warehouse keeper posts, to the offset key `consumption`, and belongs to the inspection lot (ADR-0070 rule 15). The status is the one the goods leave. It posts `internal_consumption` or `quality_sample` (preliminary price, revalued issue, offset key `consumption`), a voluntary issue like scrap.
   - **The purpose of a consumption** (the question of the account chosen by purpose, open in `open-questions.md`) is carried by the line's cost center or project. The transaction key `consumption` still has the determinants valuation class, warehouse and item group (ADR-0015); whether a regime's account determination also reads the cost center is that question and is not decided here.

   Note (S2 open questions, 2026-11-21): decided: account determination reads the cost center of an internal consumption, so `cost_center` becomes a determinant of the transaction key `consumption` (`transaction-keys.csv`); the accounts stay regime values. The catalog row waits for the matching empty `cost_center` column in the package files of the regimes (the package check reads every determinant as a column), before the 1.0.0 catalog release.

**Common to the documents**

6. **Typed headers.** Each header's primary key is its `document` row (ADR-0009 rule 1): `document_type` `stock_transfer`, `stock_count`, `scrap`, `internal_consumption`, `other_receipt`, `other_issue`, `opening_balance` and `transfer_order` (non-posting, rule 14) (review note, 2026-11-21). The lines are unique by `line_number`. Every table has `company_id`, composite company keys, `recorded_at` and the owner comment (`inventory`). The registry flags, declared in code (ADR-0009 rule 2): posting true, reversible true (ADR-0020 rule 7), approval hold allowed true, except `transfer_order`, which is non-posting: `is_posting` false, `is_reversible` false (ADR-0009 rules 2, 6). Numbering is a `numbering_configuration` row per type like any posting type (ADR-0009 rule 15). The authorization leaves already exist as document types under `inventory` in `authorization-areas.csv` (`stock_transfer`, `stock_count`, `internal_consumption`, `scrap`, `other_receipt`, `other_issue`, `opening_balance`, `transfer_order`); the `warehouse_keeper` template has `inventory` at `post`.
7. **Posting.** `Post<Type>` writes the number, the `material_document` with one line per movement, the stock quantities and values through the stock lock helper, and the journal entry through the posting interfaces in one transaction (ADR-0009 rule 13; ADR-0022): the lock order is that of ADR-0027 rule 10. A material line names its source line by `source_line_number`, as `goods_receipt` does; no back-link column is kept. The negative stock check is dated and applies to every issuing movement (ADR-0020 rule 10; ADR-0031 rule 14).
8. **Header notes and custom fields.** The headers carry `note` (ADR-0074 rule 16); the document `canceled_reason_id` of ADR-0074 rule 14 applies to them like any type. They carry no `custom_values` in Phase 1. Scrap, count, consumption, other receipt and other issue headers may name a `business_unit_id` (ADR-0069 rule 8) (review note, 2026-11-21); a transfer has none, because it posts no profit-and-loss line.
9. **Commands and queries.** `Create`, `Update`, `Delete` (draft), `Submit`, `Approve`, `Reject`, `Post`, `Cancel` and `Reverse` per type (ADR-0009 rules 4, 11, 18), as for every posting document, plus `GenerateStockCountLines` (creates the draft's lines with their book quantities for a scope of bins or items and writes no counted quantity); the confirmation of a count task creates the draft count (ADR-0023 rule 18). Queries: `GetStockCount` with the differences and reasons per key, and `ListStockTransferInTransit`, the dispatches not fully received. These are new names, registered in the command registry (ADR-0008) when the code is written.
10. **Not in this ADR.** The regime settings of `sales_return_receipt` that ADR-0020 rule 5 also requires (`movement_type.sales_return_receipt.*`) are in `settings.csv` (value source and costing role); only their interim seed value remains open (review note, 2026-11-21). Every stock document type named by ADR-0027 rule 7 now has its DDL.

    Note (the author, 2026-11-21): the interim seed value is set and confirmed: the catalog seeds `sales_return_receipt` with (`document`, `issue_return`), the original delivery line's issue cost, and `issue_return` is built in Phase 1. This is a deliberate deviation from SAP's valuation of a customer return, as SAP's practice is understood (not yet checked against SAP sources; the SAP comparison entry under "S2 closure (2026-11-21)" in [open-questions.md](../open-questions.md)) ([ADR-0020](0020-inventory-and-costing-model.md) rule 5 note of that date).

**Remaining stock documents and the count settings** (the chief architect's decision for the author, 2026-11-19)

11. **Other receipt** (`inventory`, reversible). Goods received without a purchase, sales or production source. A line names the item, the unit block, the bin (else the default receiving bin, with a putaway task in a bin-managed warehouse, ADR-0023 rule 7), the lot or serial, the status (`quality_inspection` when the product requires inspection at receipt, ADR-0070 rule 2), an optional handling unit, its value `company_amount` (the movement type's value source is `document`) and a reason of kind `other_receipt` with an optional `reason_note`, required while `documents.reason_required.other_receipt` is true, the core default (ADR-0074 rule 22). It posts `other_receipt` (receipt, offset key `other_receipt_offset`). A pre-cutover customer return is an other receipt (DS-22 comment on `return_from_customer`).
12. **Other issue** (`inventory`, reversible). Goods issued for a purpose that no other movement type covers. A line names the item, the unit block, the bin, the lot or serial, the status the goods leave, an optional handling unit, a reason of kind `other_issue` with an optional `reason_note` (required while `documents.reason_required.other_issue` is true, the core default), and at most one cost center or project. It posts `other_issue` (preliminary price, revalued issue, offset key `other_issue_offset`), a voluntary issue refused with `stock_reserved` when it would cut into reservations (ADR-0023 rule 13).
    - **Why the bearer is optional here.** The catalog's offset of `other_issue` is an "other expense" key that takes no bearer; an issue that a cost center or project bears is an internal consumption (rule 5), which requires one. A company whose account determination reads a bearer on other issues names one.
13. **Opening balance** (`inventory`, reversible within the migration). The migration opening stock of ADR-0044 rule 9. A line names the item, the warehouse, the bin (the final bin, else the default bin), the status (any, ADR-0023 rule 7), an optional handling unit, the lot or serial, the unit block and its value `company_amount`.
    - **Migration period only.** It posts only into the migration period while the migration is loading or reconciling; anywhere else it is `migration_not_open` (ADR-0044 rule 2; INV-870).
    - **Value.** The import gives one total per item and valuation area; the handler spreads it over the item's lines in that area by quantity, by largest remainder, so the lines sum exactly to the total (`opening_unit_value_differs` when a total is missing, ADR-0044 rule 9; INV-872).
    - **First preliminary price.** The total divided by the quantity of the item in the area is the area's first `preliminary_price`, with `price_source` `opening`, so no costing run is needed in the migration period (ADR-0044 rule 9; ADR-0020 rule 11 note).
    - It posts `opening_balance` (receipt, offset key `opening_balance`, the opening balance clearing account). It has no reason, no business unit and no custom values; it creates no task.
14. **Transfer order** (`inventory`, non-posting, change orders from step 5, ADR-0028 rule 4). ADR-0027 rule 7 names it as the demand document of a planned move, ADR-0024 rule 8 reads its lines as demand at the source and supply at the destination (a transit warehouse included), ADR-0023 rule 13 reserves stock for its lines and ADR-0061 rule 9 barcodes it, so `stock_transfer` does not cover it: a transfer order plans and reserves, a stock transfer moves and posts.
    - **Header and lines.** The header names `from_warehouse_id`, `to_warehouse_id` (different), an optional `transfer_route_id` (when planning converted it, ADR-0024 rule 22), `requested_date` and a `note`. A line names the item, the unit block and an optional lot (never a serial, as a reservation).
    - **Rows.** Approval creates one `demand_supply_line` per line and direction (`transfer_order_line_id`, now with its foreign key; ADR-0028 rule 2), released like the other demand rows.
    - **Fulfilment.** A `stock_transfer_line` names the order line it fulfils (`transfer_order_line_id`): a `direct` transfer between the order's two warehouses, a `dispatch` from its source, a `receive` into its destination, the same item (`transfer_order_line_invalid`; INV-871). The order line's open quantity is its quantity less what posted receipts (or direct transfers) delivered; the order closes `fulfilled` at zero, or a person closes it (ADR-0009 rule 6).
15. **Count settings.** The regime settings that ADR-0020 rule 5 and ADR-0023 rule 18 require are in `settings.csv`, each a required regime setting with no core default (`fail_closed`, so a posting without it fails with `regime_configuration_missing`), set by the regime package: `movement_type.stock_count_shortage.value_source` and `movement_type.stock_count_surplus.value_source` (bounds `preliminary_price`), `movement_type.stock_count_shortage.costing_role` and `movement_type.stock_count_surplus.costing_role` (bounds `receipt`, `revalued_issue`), and `stock_count.bin_difference_method` (`net` or `gross`). No preset sets them: presets carry company settings (ADR-0067), and these are the regime's.

## Context

ADR-0027 rule 7 settled who owns the stock documents and that their fields and flags would be written before step 3; ADR-0020 and ADR-0023 then described their behavior (the book freeze, the two-step transfer, the voluntary issues). The scan of the data structures found the DDL missing, and ADR-0070 needed two of the tables for its executor. Writing them now also gives the step 0 review a complete stock side to review.

## Options considered

| Option | For | Against |
| --- | --- | --- |
| A document type per step of a transfer (`stock_dispatch`, `stock_receipt`) | Each type is simple | Two registrations, two numbering series and two leaves for one concept; ADR-0027 and the leaves name `stock_transfer` |
| One `stock_transfer` type with a `step` (chosen) | One type, number series and leaf; ADR-0023's two forms | A `step` column and two checks |
| The book quantity read at posting | No stored column | Picks after the freeze become differences, against ADR-0023 rule 18 |
| The book quantity stored on every line of a key (chosen) | The freeze is data; INV-866 can check it | The same value repeats on lines of one key |
| A child table for several entries of one key | No repetition | A second table for a unit-conversion convenience |
| A status on transfer lines | Moves held stock | ADR-0023 rule 7 allows `available` only; a `status_change` already does it |
| A cost center on every consumption line, optional | Simple | A consumption with no bearer cannot be reported |
| Exactly one cost center or project, a quality sample excepted (chosen) | Every consumption has a bearer; samples keep the inspection lot | A CHECK with one exception |
| A back-link from each stock line to its material line | Direct join | Written at posting into an immutable line; `goods_receipt` does without |

## Consequences

- **Warehouse:** counts with a frozen book quantity and reasons; transfers between warehouses and through transit with a visible in-transit stock; scrap and consumption with their reasons and bearers.
- **Quality:** the executor's `scrap` and `internal_consumption` drafts have tables, and `target_table` names rows that exist.
- **Accounting:** postings follow the existing movement types and keys; INV-25 and the inventory ties of ADR-0020 rule 6 apply unchanged.
- **Build:** sixteen tables, no new movement type, eight invariants, eighteen edge cases. Small-model friendly: each type is the `goods_receipt` pattern.
- **Revisit when:**
  - a package needs an internal transport document for a transfer, or a write-off document for a short receipt;
  - a company counts several warehouses in one document.

## Documents updated

- **ADRs** (notes tagged "ADR-0075, 2026-11-21"): ADR-0020 rules 7 and 18; ADR-0023 rules 7 and 18; ADR-0024 rule 8; ADR-0027 rule 7; ADR-0028 rule 2; ADR-0044 rule 9; ADR-0063 rule 29 (the five settings); ADR-0069 rule 8; ADR-0070 rule 15.
- **Catalogs:** settings.csv (5, rule 15), invariants.csv (8), edge-cases.csv (18).
- **Design:** DS-22-09-42-commercial-inventory.sql; DS-04 (`dispatch_has_receive`, `transfer_order_line_invalid`); DS-43-54 (the foreign key of `demand_supply_line.transfer_order_line_id`, added in DS-22); DS-16 and DS-17 (blocks and counts); the glossary (new rows only); the generated overview.
- **Lab:** `t28_stock_count.py`, `t29_other_stock_documents.py` and the lab README (findings); `t17_uom.py` D03 and `t14_commercial_inventory_ddl.py` M5 (shared with ADR-0074).
- **Index and log:** docs/adr/README.md; docs/open-questions.md; docs/runbook/step-log.md.

## Edge cases and invariants

**Invariants** (DS-16; block INV-865 to INV-869; first step 3):

- **INV-865** `count_key_consistent` (area `inventory`): every line of one count key (item, bin, lot or serial, status) holds the same book quantity, freeze time and difference reason.
- **INV-866** `count_difference_posted_exactly` (area `inventory`): for a posted count, per item, warehouse and lot or serial, the signed sum of its material lines equals the sum over its keys of counted minus stored book quantity, with bin netting or without.
- **INV-867** `transfer_receive_within_dispatch` (area `inventory`): a posted `receive` names the posted `dispatch` of its `dispatch_transfer_id`, each line names a dispatch line of the same item, lot, serial and handling unit, and receives no more than it sent; a dispatch has at most one live receive (not canceled, not reversed). (review note, 2026-11-21)
- **INV-868** `transfer_warehouse_kinds` (area `inventory`): a `direct` transfer is between two physical warehouses; a `dispatch` goes to a `transit` or `goods_sent` warehouse; a `receive` comes out of its dispatch's destination.
- **INV-869** `stock_document_movement_types` (area `inventory`): the material lines of a posted stock document use only the movement types of its kind (transfer: `transfer_out` and `transfer_in`; count: the two count types; scrap: `scrap`; consumption: `internal_consumption` or `quality_sample` by its line kind; other receipt: `other_receipt`; other issue: `other_issue`; opening balance: `opening_balance`; a transfer order posts none), in the type's direction, flipped for a reversal. (review note, 2026-11-21)

**Edge cases** (DS-17; block EC-320 to EC-329, all taken):

- **EC-320** `count_summed_counting_units`: one key counted in three entries in cartons and pieces; the lines sum in the inventory unit and one difference posts.
- **EC-321** `count_uncounted_key_posts_nothing`: a bin with two items where one is counted: the other posts nothing; a counted zero posts a shortage.
- **EC-322** `count_picks_after_freeze`: a pick between the freeze and the posting is not a difference; the posted difference is counted minus the stored book quantity.
- **EC-323** `count_reversal_refused_when_consumed`: a surplus count whose stock was shipped is not reversible (`negative_stock`).
- **EC-324** `count_shortage_cancels_reservation`: a shortage that cuts into a reservation posts, cancels it deterministically and raises an exception (ADR-0023 rule 13).
- **EC-325** `transfer_through_transit_short_receipt`: a dispatch of 10 is received as 8; 2 remain in the transit warehouse; the dispatch cannot be reversed before its receive.
- **EC-326** `transfer_reversal_refused_after_shipment`: a direct transfer whose goods were delivered is not reversible.
- **EC-327** `scrap_from_held_status`: held goods scrapped from `blocked` with a reason; a scrap that would cut into a reservation is `stock_reserved`.
- **EC-328** `consumption_one_bearer`: a consumption naming both a cost center and a project, or neither, is refused; a quality sample may name neither.
- **EC-329** `scrap_without_reason`: with `documents.reason_required.scrap` true, a scrap line without a reason is refused with `reason_required`; a reason of another kind is refused with `reason_invalid`.

**Invariants of rules 11 to 15** (block INV-870 to INV-879, INV-870 to INV-872 taken):

- **INV-870** `opening_balance_in_migration_period` (area `inventory`): every posted `opening_balance` posts in the migration period of its company.
- **INV-871** `transfer_fulfils_order_line` (area `inventory`): a stock transfer line that names a transfer order line has its item, and its warehouses fit the step: both of the order's for `direct`, its source for `dispatch`, its destination for `receive`; received and directly transferred quantities never exceed the ordered quantity by more than the unit rounding tolerance.
- **INV-872** `opening_value_spread_exact` (area `inventory`): the opening balance lines of an item and valuation area sum exactly to the area's total, and the first preliminary price of the area is that total divided by the quantity.

**Edge cases of rules 11 to 15** (block EC-330 to EC-339, shared with ADR-0074 rule 22; EC-331 to EC-338 taken):

- **EC-331** `other_issue_requires_reason`: an other issue line without a reason is refused with `reason_required`; with a reason of kind `other_issue` and a cost center it posts.
- **EC-332** `other_receipt_valued_from_document`: an other receipt of 10 units valued 1,000 posts 1,000 into stock and the offset key `other_receipt_offset`.
- **EC-333** `opening_balance_outside_migration`: an opening balance dated in an ordinary period is refused with `migration_not_open`.
- **EC-334** `opening_value_spread_sets_price`: one item in three bins with a total of 1,000 for 3 units: the lines take 333, 333 and 334 by largest remainder, and the first preliminary price is 1000/3.
- **EC-335** `transfer_order_two_step_fulfilment`: a transfer order of 10 fulfilled by a dispatch of 10 and a receive of 8; the order line stays open for 2 until a person closes it or a second transfer arrives.
- **EC-336** `transfer_order_line_wrong_warehouse`: a direct transfer that names an order line of other warehouses is refused with `transfer_order_line_invalid`.
- **EC-337** `transfer_order_reservation`: the order line's demand row at the source reserves stock, and a scrap that would cut into it is refused with `stock_reserved`.
- **EC-338** `count_settings_missing`: a count posting in a company whose regime sets no `movement_type.stock_count_shortage.value_source` fails with `regime_configuration_missing`.
