# ADR-0075: Stock documents

Status: proposed (2026-11-19) under ADR-0005 (builder Claude Sonnet 5.5).
Design items: DS-09 (stock documents), DS-22, DS-42 (warehouse management), DS-58 (quality). Related decisions: none new. Principles 6, 12. ADR-0004, ADR-0006, ADR-0009, ADR-0014, ADR-0015, ADR-0020, ADR-0023, ADR-0027, ADR-0031, ADR-0034, ADR-0056, ADR-0069, ADR-0070, ADR-0074.

## Decision

ADR-0020 rules 4 to 7 and 18, ADR-0023 rules 7 and 18 and ADR-0027 rule 7 describe four stock documents, and ADR-0027 rule 7 promised their DDL in a "DS-09 stock documents deliverable, written before step 3". No DDL file defines them: only the material document layer and the warehouse tasks exist, and ADR-0070 rule 15 already drafts `scrap` and `internal_consumption` documents and names them in `inspection_lot_execution.target_table`. This ADR writes the four, each as a typed header with lines in the pattern of `goods_receipt` (ADR-0009 rule 1), reversible, posting one material document and its journal entry through the posting interfaces.

| Document | Header and lines | Movement types | Key choice |
| --- | --- | --- | --- |
| Stock transfer | `stock_transfer`, `stock_transfer_line` | `transfer_out`, `transfer_in` | One document type with three steps (`direct`, `dispatch`, `receive`) |
| Stock count | `stock_count`, `stock_count_line` | `stock_count_shortage`, `stock_count_surplus` | The book quantity is stored on each line at the freeze; the difference is counted minus book |
| Scrap | `scrap`, `scrap_line` | `scrap` | A required reason of kind `scrap`; the held status the goods leave |
| Internal consumption | `internal_consumption`, `internal_consumption_line` | `internal_consumption`, `quality_sample` | Exactly one cost center or project, except a quality sample |

No movement type is added: the catalog of ADR-0020 rule 4 already holds every one of them (`docs/catalogs/movement-types.csv`).

### Rules

**The four documents**

1. **Stock transfer** (`inventory`). The header names `from_warehouse_id` and `to_warehouse_id` (different), a `step`, an optional `reference` (the sender's or the carrier's) and a `note` (ADR-0074 rule 16). A line names the item, the unit block of ADR-0056 rule 9, the lot or serial (never both), the `from_bin_id` and `to_bin_id` and, optionally, a handling unit. Transfers move `available` stock only (the allowed status of `transfer_out` and `transfer_in`, ADR-0023 rule 7), so a line has no status; held stock is released by a `status_change` first. The bins are optional: outside bin-managed warehouses the default bin applies (ADR-0031 rule 8), and in bin-managed warehouses the source bin is the non-pickable bin the confirmed picks moved the goods to, the receiving bin the default receiving bin until putaway (ADR-0023 rules 7, 14, 15). The pick tasks that precede `transfer_out` and the putaway task after `transfer_in` are created as for a delivery and a receipt.
   - **Reservations.** A transfer is a voluntary issue: `transfer_out` is refused with `stock_reserved` when it would cut into reservations (ADR-0023 rule 13).
   - **`direct`.** One document between two physical warehouses: each line posts `transfer_out` and `transfer_in` in one material document, at the issuing value, with both journal lines (ADR-0020 rule 6).
2. **Through transit** (ADR-0023 rule 7, ADR-0020 rule 1). A transfer to a warehouse of kind `transit` or `goods_sent` is two documents:
   - **`dispatch`** posts `transfer_out` from the source and `transfer_in` into the transit warehouse. Its stock is owned and valued there (the keys `inventory_in_transit_posting` and `inventory_goods_sent_posting`).
   - **`receive`** names its dispatch (`dispatch_transfer_id`, at most one receive per dispatch) and posts out of the transit warehouse and into the destination. Each of its lines names a dispatch line (`dispatch_line_id`) of the same item, lot, serial and handling unit, and receives no more than that line sent (INV-867). The handling unit keeps its identity.
   - **A short receipt** leaves the rest in the transit warehouse, where it is visible as stock, until a count or a reversal of the dispatch settles it. The ADR adds no write-off document for it (open question).
   - **Warehouse kinds** are held by INV-868: `direct` between two physical warehouses, `dispatch` into a transit or goods-sent warehouse, `receive` out of the dispatch's.
   - **Reversal.** A transfer is reversible (ADR-0020 rule 7): a reversal repeats the lines in the opposite direction, is refused with `negative_stock` when the stock has moved on (ADR-0020 rule 10), and a `dispatch` with a posted `receive` cannot be reversed before it (`dispatch_has_receive`). The open question on whether a package requires an internal transport document keeps its place in `open-questions.md`; the core flag is `is_reversible` true.
3. **Stock count** (`inventory`). One count document counts one warehouse. Each line is one counted entry:
   - **The key** of a line is (item, bin, lot or serial, status); `bin_id` is required (the default bin outside bin-managed warehouses). Several lines may share a key, each entered in the product's counting unit with the unit block and summed in the inventory unit (ADR-0056 rule 15; ADR-0020 rule 18 note).
   - **The book quantity.** `book_quantity` and `book_taken_at` store the stock of the key at the freeze, in the inventory unit: the confirmation of the count task when the warehouse has tasks, else the creation of the draft (ADR-0023 rule 18). Every line of a key holds the same book quantity, time and difference reason (INV-865). A key with no stock has book 0, so a surplus found where nothing was booked is a line.
   - **What is counted.** A key with no line is not counted and posts nothing. A counted zero is a line with quantity 0. Serials are counted one by one: quantity 0 or 1.
   - **The difference** of a key is the sum of its counted quantities minus its stored book quantity. Posting posts that, so a pick or a putaway between the freeze and the posting never becomes a difference (ADR-0023 rule 18). A positive difference posts `stock_count_surplus`, a negative one `stock_count_shortage`, valued as ADR-0020 rules 5 and 11 say (a surplus at the preliminary price, else `preliminary_price_missing`). INV-866 ties the posted movements to the differences.
   - **Task link.** `count_task_id` names the confirmed count task that created the line, when there is one (ADR-0023 rule 18).
   - **Reasons.** `difference_reason_id` (kind `count_difference`, ADR-0074 rule 13) and `difference_note` explain a difference; both are optional, and the reason is the same on every line of a key (INV-865). A report shows a difference without a reason as unexplained. Whether a reason is required is a policy for a later setting (open question).
   - **Bin netting.** The regime setting `stock_count.bin_difference_method` of ADR-0023 rule 18 is unchanged: netting corrects the bins by warehouse movements with `source_command` `count_correction`, and INV-866 holds either way because it sums per (item, warehouse, lot or serial).
   - **Posting** runs through the normal lifecycle with policy and approval (ADR-0009 rules 11, 13). A shortage and a physical fact always post and cancel reservations deterministically (ADR-0023 rule 13). The material lines name the key's lowest `line_number` as `source_line_number`.
   - **Reversal.** A count is reversible (ADR-0020 rule 7): the opposite movements are refused with `negative_stock` when a surplus has been consumed.
4. **Scrap** (`inventory`). A line names the item, the quantity, the bin, the lot or serial, the status the goods leave (`stock_status`, so held goods are scrapped from `blocked` or `quality_inspection` as ADR-0070 rule 15 drafts them), an optional handling unit, a required scrap reason (`scrap_reason_id`, kind `scrap`; a line without one is `reason_invalid`) with an optional `reason_note`, and optionally one cost center or one project (never both) when the regime's account determination reads it. It posts `scrap` (preliminary price, revalued issue, offset key `scrap`). Scrap is a voluntary issue: it is refused with `stock_reserved` when it would cut into reservations (ADR-0023 rule 13). A line created by the quality executor carries the held status and the inspection lot's link through `inspection_lot_execution.target_table` (DS-58); nothing else of the document is special.
5. **Internal consumption** (`inventory`). A line is `internal` or a `quality_sample` (`consumption_kind`), and names exactly one cost center or project that bears it; a quality sample may name none, because a sample destroyed by testing is issued by a draft that the quality executor creates and a warehouse keeper posts, to the offset key `consumption`, and belongs to the inspection lot (ADR-0070 rule 15). The status is the one the goods leave. It posts `internal_consumption` or `quality_sample` (preliminary price, revalued issue, offset key `consumption`), a voluntary issue like scrap.
   - **The purpose of a consumption** (the question of the account chosen by purpose, open in `open-questions.md`) is carried by the line's cost center or project. The transaction key `consumption` still has the determinants valuation class, warehouse and item group (ADR-0015); whether a regime's account determination also reads the cost center is that question and is not decided here.

**Common to the four**

6. **Typed headers.** Each header's primary key is its `document` row (ADR-0009 rule 1): `document_type` `stock_transfer`, `stock_count`, `scrap`, `internal_consumption`. The lines are unique by `line_number`. Every table has `company_id`, composite company keys, `recorded_at` and the owner comment (`inventory`). The registry flags, declared in code (ADR-0009 rule 2): posting true, reversible true (ADR-0020 rule 7), approval hold allowed true. Numbering is a `numbering_configuration` row per type like any posting type (ADR-0009 rule 15). The authorization leaves already exist as document types under `inventory` in `authorization-areas.csv` (`stock_transfer`, `stock_count`, `internal_consumption`, `scrap`); the `warehouse_keeper` template has `inventory` at `post`.
7. **Posting.** `Post<Type>` writes the number, the `material_document` with one line per movement, the stock quantities and values through the stock lock helper, and the journal entry through the posting interfaces in one transaction (ADR-0009 rule 13; ADR-0022): the lock order is that of ADR-0027 rule 10. A material line names its source line by `source_line_number`, as `goods_receipt` does; no back-link column is kept. The negative stock check is dated and applies to every issuing movement (ADR-0020 rule 10; ADR-0031 rule 14).
8. **Header notes and custom fields.** The four headers carry `note` (ADR-0074 rule 16); the document `canceled_reason_id` of ADR-0074 rule 14 applies to them like any type. They carry no `custom_values` in Phase 1. Scrap, count and consumption headers may name a `business_unit_id` (ADR-0069 rule 8); a transfer has none, because it posts no profit-and-loss line.
9. **Commands and queries.** `Create`, `Update`, `Delete` (draft), `Submit`, `Approve`, `Reject`, `Post`, `Cancel` and `Reverse` per type (ADR-0009 rules 4, 11, 18), as for every posting document, plus `GenerateStockCountLines` (creates the draft's lines with their book quantities for a scope of bins or items and writes no counted quantity); the confirmation of a count task creates the draft count (ADR-0023 rule 18). Queries: `GetStockCount` with the differences and reasons per key, and `ListStockTransferInTransit`, the dispatches not fully received. These are new names, registered in the command registry (ADR-0008) when the code is written.
10. **Not in this ADR.** `other_receipt`, `other_issue`, `opening_balance` and the non-posting `transfer_order` (ADR-0027 rule 7) still have no DDL; `demand_supply_line.transfer_order_line_id` stays without its foreign key until `transfer_order` exists. The count settings `movement_type.stock_count_shortage.*` and `.stock_count_surplus.*` that ADR-0020 rule 5 requires are not in `settings.csv` yet (open question).

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
- **Build:** eight tables, no new movement type, five invariants, ten edge cases. Small-model friendly: each type is the `goods_receipt` pattern.
- **Revisit when:**
  - a package needs an internal transport document for a transfer, or a write-off document for a short receipt;
  - a company needs the reason on a count difference to be required;
  - a company counts several warehouses in one document.

## Documents updated

- **ADRs** (notes tagged "ADR-0075, proposed 2026-11-19"): ADR-0020 rules 7 and 18; ADR-0023 rules 7 and 18; ADR-0027 rule 7; ADR-0069 rule 8; ADR-0070 rule 15.
- **Catalogs:** invariants.csv (5), edge-cases.csv (10).
- **Design:** DS-22-09-42-commercial-inventory.sql; DS-04 (`dispatch_has_receive`); DS-16 and DS-17 (blocks and counts); the glossary (new rows only); the generated overview.
- **Lab:** `t28_stock_count.py` and the lab README (findings); `t17_uom.py` D03 and `t14_commercial_inventory_ddl.py` M5 (shared with ADR-0074).
- **Index and log:** docs/adr/README.md; docs/open-questions.md; docs/runbook/step-log.md.

## Edge cases and invariants

**Invariants** (DS-16; block INV-865 to INV-869; first step 3):

- **INV-865** `count_key_consistent` (area `inventory`): every line of one count key (item, bin, lot or serial, status) holds the same book quantity, freeze time and difference reason.
- **INV-866** `count_difference_posted_exactly` (area `inventory`): for a posted count, per item, warehouse and lot or serial, the signed sum of its material lines equals the sum over its keys of counted minus stored book quantity, with bin netting or without.
- **INV-867** `transfer_receive_within_dispatch` (area `inventory`): a posted `receive` names the posted `dispatch` of its `dispatch_transfer_id`, each line names a dispatch line of the same item, lot, serial and handling unit, and receives no more than it sent.
- **INV-868** `transfer_warehouse_kinds` (area `inventory`): a `direct` transfer is between two physical warehouses; a `dispatch` goes to a `transit` or `goods_sent` warehouse; a `receive` comes out of its dispatch's destination.
- **INV-869** `stock_document_movement_types` (area `inventory`): the material lines of a posted stock document use only the movement types of its kind (transfer: `transfer_out` and `transfer_in`; count: the two count types; scrap: `scrap`; consumption: `internal_consumption` or `quality_sample` by its line kind), in the type's direction, flipped for a reversal.

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
- **EC-329** `scrap_without_reason`: a scrap line without a reason of kind `scrap`, or with a reason of another kind, is refused.
