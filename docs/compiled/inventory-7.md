Module: inventory    Chunk: 7 of 7    Source ADRs: ADR-0061, ADR-0063, ADR-0064, ADR-0068, ADR-0074, ADR-0075
Build step(s): 0, 1, 2, 3, 4, 5    Generated from index: 30d5706    Compiled by: Claude Opus 5.5, 2026-11-21

# Compiled spec: `inventory`, chunk 7

## Purpose

`inventory` owns stock quantities and values, the stock and warehouse documents, warehouse tasks and reservations, and
costing (ADR-0022.R2); it sits in layer 3. This chunk states barcode capture of variable measures and serials on stock
lines, the purchase return value options, the barcode interpretation settings, the reservation transfer between
production orders, the valuation area columns at level `site`, the advisory effect of an Incoterm, the parties and note
of document headers, and the stock documents of ADR-0075. As owner of the rest it also carries the owned tables,
invariants and edge cases that no rule of chunks 1 to 6 names. Quality, production, planning, agents and master data
units of this part are traced `ref:` and not restated.

## Entities and tables

DDL: `docs/design/DS-22-09-42-commercial-inventory.sql`.

| Table | Meaning | Key | Parent | Owner |
| --- | --- | --- | --- | --- |
| `stock_transfer` | Stock transfer header, step `direct`, `dispatch` or `receive` (R1235, R1240) | `id` = its `document` row | `document` | `inventory` |
| `stock_transfer_line` | One moved item, lot or serial, bins, handling unit | `id`; unique `line_number` per transfer | `stock_transfer` | `inventory` |
| `stock_count_line` | One counted entry of a count key, with the frozen book quantity | `id`; unique `line_number` per count | `stock_count` | `inventory` |
| `scrap` | Scrap header (R1255) | `id` = its `document` row | `document` | `inventory` |
| `scrap_line` | One scrapped quantity, status left, scrap reason, optional bearer | `id`; unique `line_number` per scrap | `scrap` | `inventory` |
| `internal_consumption` | Internal consumption header (R1258) | `id` = its `document` row | `document` | `inventory` |
| `internal_consumption_line` | One consumed quantity, `consumption_kind`, its bearer | `id`; unique `line_number` | `internal_consumption` | `inventory` |
| `other_receipt` | Other receipt header (R1268) | `id` = its `document` row | `document` | `inventory` |
| `other_receipt_line` | One received quantity with its value and reason | `id`; unique `line_number` | `other_receipt` | `inventory` |
| `other_issue` | Other issue header (R1269) | `id` = its `document` row | `document` | `inventory` |
| `other_issue_line` | One issued quantity with its reason and optional bearer | `id`; unique `line_number` | `other_issue` | `inventory` |
| `opening_balance` | Migration stock opening balance header (R1271) | `id` = its `document` row | `document` | `inventory` |
| `opening_balance_line` | One opening quantity with its spread value | `id`; unique `line_number` | `opening_balance` | `inventory` |
| `transfer_order` | Non-posting planned move between two warehouses (R1276) | `id` = its `document` row | `document` | `inventory` |
| `transfer_order_line` | One planned item quantity, optional lot | `id`; unique `line_number` | `transfer_order` | `inventory` |

The row of `stock_count` stands in chunk 2; those of `delivery_line` and `goods_receipt_line` in chunk 5. Columns this chunk's rules add to tables whose rows stand in other chunks: `stock_reservation.transferred_from_reservation_id`
(R1216, R1221); `valuation_site_id` on `material_document_line` and `preliminary_price` (R1223, R1224); the ship-to columns
of `delivery` (R1231); `note` on `goods_receipt`, `delivery`, `return_to_supplier` and `return_from_customer` (R1233).

Reads: `document`, `warehouse`, `site`, `company`, `reason`, `cost_center`, `project`, `business_unit`, `warehouse_task`,
`numbering_configuration`, `inspection_lot_execution`, `planning_exception`, `operation_confirmation`, `document_reader`,
`document_extraction`, `extraction_mapping_rule`, `mailbox`, `transfer_route`, `production_order`, `incoterm`, the sales
and purchase document headers of R1231 and R1233.

## Commands and queries

| Name | Actor / authorization | Input | Effect | Events | Error codes |
| --- | --- | --- | --- | --- | --- |
| `TransferStockReservation` | Verb Transfer, `stock_reservation` at `post`; effect class `other`; `is_proposal_bound`; accepted only from the execution of an approved change proposal | Source reservation, target demand line, quantity, `expected_version` of both orders | Reduces the source, creates the target reservation (R1213-R1218) | `StockReservationTransferred` | `reservation_transfer_invalid`, `proposal_required` |
| `Create<Type>`, `Update<Type>`, `Delete<Type>` (draft), `Submit<Type>`, `Cancel<Type>` for each stock document type of R1260 | The type's leaf under `inventory` in `authorization-areas.csv`; verb levels `edit` | Header and lines | Draft lifecycle (ADR-0009.R4, ADR-0009.R11, ADR-0009.R18) | Not stated | `reason_required`, `reason_invalid`, `transfer_order_line_invalid` |
| `Approve<Type>`, `Reject<Type>` | The type's leaf; the role's approval flag | The document version | Approval (ADR-0009.R11) | Not stated | Not stated |
| `Post<Type>` (posting types) | The type's leaf at `post` | The approved document | Number, `material_document`, stock and journal entry in one transaction (R1263) | Not stated | `stock_reserved`, `negative_stock`, `preliminary_price_missing`, `migration_not_open`, `opening_unit_value_differs`, `regime_configuration_missing` |
| `Reverse<Type>` (posting types) | The type's leaf at `full` | The posted document | Opposite movements (R1245, R1254) | Not stated | `negative_stock`, `dispatch_has_receive` |
| `GenerateStockCountLines` | Not stated | A draft count and a scope of bins or items | Creates the draft's lines with their book quantities (R1265) | Not stated | Not stated |
| `GetStockCount` (query) | Not stated | A count | The differences and reasons per key (R1266) | None | Not stated |
| `ListStockTransferInTransit` (query) | Not stated | Not stated | The dispatches not fully received (R1266) | None | Not stated |
| `ListExpectedLandedCost` (query) | Not stated | Not stated | Goods receipts whose Incoterm leaves main carriage or insurance to the buyer and that have no `freight` or `insurance` landed cost line (R1229) | None | Not stated |

The confirmation of a count task creates the draft count (ADR-0023.R18). A transfer order is non-posting and has no
`Post` or `Reverse` (R1261).

## Rules

### Barcode capture on stock lines

R1201. A quantity from a measure AI enters in the AI's unit, which becomes the line's entered unit (ADR-0056.R13). It must be an allowed unit of the item (ADR-0056.R6), else `uom_not_allowed`. The measure is never rounded: one with more decimals than its unit holds is accepted when the extra decimals are zeros (`3105115600` is 1.15600 kg, entered as 1.156), otherwise it is rejected with `too_many_decimal_places` (ADR-0006.R14; ADR-0056.R8). The line takes the unit block of ADR-0056.R9: the snapshot from `convert_quantity`, and the inventory quantity rounded as ADR-0056.R8 says for receipts. `3102001156` on an item kept in `KGM` is 11.56 `KGM`, identity; on an item kept in `GRM` it is converted through the catalog to 11560 `GRM`; on an item kept in pieces without a kilogram unit it is refused; `3105012345` is refused on any item, since `KGM` holds three decimals.
Source: ADR-0061.R18

R1202. Serials are captured per unit: each unit is one scan, and the screen shows a running count ("7 of 20"). A serial scanned twice in one confirmation is refused with `serial_already_scanned`; a serial not in the source bin with an allowed status keeps `serial_not_in_bin` (ADR-0023.R14). With (01) and (21), the item of the GTIN must be the task's item (`scan_mismatch`).
Source: ADR-0061.R19

R1203. Scanning a closed `handling_unit` whose content is serials of the task's item confirms all its serials at once when the task takes the whole unit; a partial take unpacks first (ADR-0023.R6). Serial uniqueness stays per item (ADR-0020.R17). A serial's own internal barcode, when it has one, is unique in the company through the registry.
Source: ADR-0061.R19

### Purchase return value

R1204. The regime keys `movement_type.purchase_return.value_source` and `movement_type.purchase_return.costing_role` are required regime settings without a core default (accounting rules, ADR-0020.R5). A regime may open them as company options (ADR-0016.R11) with two allowed pairs: (`document`, `receipt`), the document value as a negative receipt; and (`preliminary_price`, `revalued_issue`), the current cost as an issue. The recommended pair, and the test package's, is the document value. The keys keep their prefix; a package's seeded value stays open until it is verified.
Source: ADR-0063.R24

R1205. The optional key `movement_type.purchase_return.include_landed_cost` (regime, company option; core default true, as ADR-0053.R8 allows for optional keys) makes a return of a receipt with allocated landed cost carry its proportional share of it. The share is the landed cost allocated to the receipt line, which posts in the period of the cost document as a value-only `receipt_addition` (ADR-0021.R6.N2); a return posted after a late landed cost carries its share as this key says (interim, flagged, case (c) of ADR-0021.R6.N2).
Source: ADR-0063.R24

R1206. A change of the purchase return options takes effect only from the start of a posting period (`period_start`). Each return stamps the option pair and the landed-cost choice in force on its posting date (`INV-715`).
Source: ADR-0063.R24

R1207. Whichever option applies, GR/IR of the order line clears at the order value; the difference posts as a price difference to its named key (ADR-0047.R13), never silently into the average; stock value never goes negative (ADR-0020).
Source: ADR-0063.R24

### Barcode interpretation settings

R1208. Day 00 is read per date AI, per company with a per-category override: `barcode.gs1.day00_policy.<expiry_ai>` for (12), (15), (16), (17), default `last_day` (the GS1 rule), and `barcode.gs1.day00_policy.<production_ai>` for (11), (13), default `first_day`; the values are `last_day`, `first_day` and `reject`. An earlier date is the more conservative reading, so `first_day` is tighter than `last_day` and `reject` tightest; a category of regulated goods may set `reject`.
Source: ADR-0063.R26

R1209. `barcode.gs1.best_before_fills_expiry`, per category, default false: with false, (15) is stored as the lot's `best_before_date` and does not fill `expiry_date` when (17) is absent; true lets (15) fill a new lot's expiry date when (17) is absent.
Source: ADR-0063.R26

R1210. `barcode.unknown_ai_policy`, per company: `report_and_ignore` (default, check result `gs1_element_ignored`) or `reject`.
Source: ADR-0063.R26

R1211. `barcode.separator_suspect`, per scanner profile: `stop_and_confirm` (default) or `trust_transport`, the latter only for a profile proven by a test scan to send GS.
Source: ADR-0063.R26

R1212. Not configurable: check digits, the generated AI table, predefined lengths, the century window from the business date and the character sets. Digital Link URIs are never fetched; a retired code is never reassigned to another owner; each parse result stamps the policy values it used and `day_precision`.
Source: ADR-0063.R26

### Reservation transfer between production orders

R1213. `TransferStockReservation` (module `inventory`, verb Transfer, effect class `other`, `is_proposal_bound`, `stock_reservation` at `post`) transfers a reservation between orders. Its payload is the source reservation, the target demand line, the quantity, and the `expected_version` of both orders.
Source: ADR-0064.R24

R1214. Source and target are demand lines of production order component lines of approved orders that are not technically complete, with the same item and warehouse. The quantity is at most the source's open, unpicked quantity and at most the target line's short quantity at execution, max(0, unreserved open requirement − available to promise of the item in the target's issue warehouse), computed under the target order's lock; a lot-bound reservation keeps its lot. Otherwise `reservation_transfer_invalid`, so a transfer is refused once a goods receipt has made free stock cover the target, whether or not anything has reserved it yet. Reservations of sales orders are not transferred in Phase 1.
Source: ADR-0064.R24

R1215. The proposal's evidence shows the target's shortage and the source order's resulting short quantity and pegged demand, computed by ADR-0064.R16.
Source: ADR-0064.R24

R1216. A database trigger refuses a transferred row whose source is of another company, item, warehouse or lot; any change of `transferred_from_reservation_id` after insert, so a transfer chain has no cycle; and any change of `item_id`, `warehouse_id` or `lot_id` on a row that has or is a transfer source.
Source: ADR-0064.R24

R1217. Effect: the source reservation is reduced (canceled when it reaches 0) and a new reservation for the target carries `transferred_from_reservation_id`, with the target's destination bin and release sequence. Event `StockReservationTransferred`.
Source: ADR-0064.R24

R1218. Like `UpdateAgentTypeSetting` setting `assisted` (ADR-0050.R14), the handler accepts `TransferStockReservation` only from the execution of an approved change proposal and returns `proposal_required` otherwise, for people too.
Source: ADR-0064.R24

R1219. `planning_exception` has the kinds `production_order_start_overdue` and `production_order_overdue`, and a column `production_order_id` with its company key, set exactly for those kinds.
Source: ADR-0064.R27

R1220. `operation_confirmation` has `entry_source` (`person`, `capture_agent`, `production_import`; default `person`) and `external_reference`, set exactly for `production_import`, not blank, and unique per company.
Source: ADR-0064.R27

R1221. `stock_reservation` has `transferred_from_reservation_id`, a company key to `stock_reservation`, never the row itself (`ck_stock_reservation_transferred_from`), with the trigger of ADR-0064.R24.
Source: ADR-0064.R27

R1222. The purpose value `shop_floor_report` is allowed in `document_reader.purposes`, `document_extraction.purpose`, `extraction_mapping_rule.purpose` and `mailbox.document_intake_purpose`.
Source: ADR-0064.R27

### Valuation area at level site

R1223. A line records its valuation area in the nullable columns `valuation_site_id`, set at level `site`, and `valuation_warehouse_id`, set at level `warehouse`. Both are null at level `company`, and at most one is set (`ck_material_document_line_valuation_area`).
Source: ADR-0068.R8

R1224. `material_document_line` and `preliminary_price` carry `valuation_site_id` and `valuation_warehouse_id`. The unique key of `preliminary_price` covers both, with `NULLS NOT DISTINCT`.
Source: ADR-0068.R8

R1225. The stock lock helper sets them from the company's level and the line's warehouse, and `INV-810` checks the result. The costing job keys an area by the pair. A site-level area is never named by a representative warehouse, and there is no `valuation_area` table; the typed columns are additive and the database checks each foreign key.
Source: ADR-0068.R8

R1226. The exact solve over areas linked by transfers (ADR-0020.R12) is unchanged; at level `site` its nodes are sites.
Source: ADR-0068.R9

R1227. Transfers inside one area are value-neutral: the period-end adjustment changes the issue and the receipt by the same amount, so the area's value does not change. `stock_value` still moves per warehouse, and each warehouse's inventory account still equals its stock value (ADR-0020.R6). A lab check covers both properties.
Source: ADR-0068.R9

R1228. The preliminary price fallbacks of ADR-0020.R11 read "the area" as the site. Account determination keeps its `warehouse` determinant; a site gets none.
Source: ADR-0068.R9

### Incoterm effect

R1229. When a purchase's Incoterm leaves the main carriage or insurance to the buyer, the query `ListExpectedLandedCost` (`inventory`) lists its goods receipts that have no `freight` or `insurance` landed cost line (ADR-0021.R1). The purchase agent and the close task of ADR-0021.R14 show this list. It is not a check result, so it forces no plan review (ADR-0067.R12).
Source: ADR-0068.R20

R1230. The owner axis of ADR-0030.R8 has no ownership-transfer default, so nothing reads the Incoterm there; ownership of goods in transit from the shipping point, when it is designed, takes the Incoterm as its input. No posting rule, check result, tax rule or policy condition reads an Incoterm.
Source: ADR-0068.R20

### Parties and notes on document headers

R1231. The party columns sit on these headers:
   - `ship_to`, `bill_to`, `payer`: `quotation`, `sales_order`.
   - `ship_to`: `delivery` (in place of `delivery_address`).
   - `bill_to`, `payer`: `sales_invoice`, `sales_return`, `credit_note`, `debit_note`.
   - `invoicing_party`, `payee`: `purchase_order`, `purchase_invoice`, `purchase_return`, `purchase_credit_note`, `purchase_debit_note`.
   Source: ADR-0074.R2

R1232. Receipts, returns to suppliers, returns from customers and service receipts keep the one partner they have: a receipt is of what the ordered-from party delivered, whoever invoices it. A document made from another (an order to a delivery or an invoice, an invoice to its credit note) copies the parties of its source, which a person may change until posting.
Source: ADR-0074.R2

R1233. `document` and `document_version` hold no note (the version content is canonical JSON of the header and lines). A `note text` column (at most 4,000 characters) is on the headers `quotation`, `sales_order`, `purchase_request`, `purchase_order`, `goods_receipt`, `return_to_supplier`, `delivery`, `return_from_customer`, `service_receipt`, `sales_invoice`, `sales_return`, `credit_note`, `debit_note`, `purchase_invoice`, `purchase_return`, `purchase_credit_note` and `purchase_debit_note`, and on the headers of ADR-0075. It is internal free text: content of the version, frozen at posting, untrusted for agents (ADR-0029), and printed only by a layout that names it (ADR-0049). Line `description` columns stay.
Source: ADR-0074.R16

### Stock documents: overview

R1234. `inventory` writes these stock documents, each a typed header with lines in the pattern of `goods_receipt` (ADR-0009.R1):
   - Stock transfer, `stock_transfer` and `stock_transfer_line`: `transfer_out`, `transfer_in`.
   - Stock count, `stock_count` and `stock_count_line`: `stock_count_shortage`, `stock_count_surplus`.
   - Scrap, `scrap` and `scrap_line`: `scrap`.
   - Internal consumption, `internal_consumption` and `internal_consumption_line`: `internal_consumption`, `quality_sample`.
   - Other receipt, `other_receipt` and `other_receipt_line`: `other_receipt`.
   - Other issue, `other_issue` and `other_issue_line`: `other_issue`.
   - Opening balance, `opening_balance` and `opening_balance_line`: `opening_balance`.
   - Transfer order, `transfer_order` and `transfer_order_line`: none (non-posting).
   - No movement type is added: the `movement_type` catalog (`movement-types.csv`, ADR-0020.R4) holds every one of them.
   Source: ADR-0075.D0

### Stock transfer

R1235. A stock transfer header names `from_warehouse_id` and `to_warehouse_id` (different, `ck_stock_transfer_warehouses`), a `step` (`direct`, `dispatch` or `receive`), an optional `reference` (the sender's or the carrier's) and a `note` (ADR-0074.R16). A line names the item, the unit block of ADR-0056.R9, the lot or serial (never both), the `from_bin_id` and `to_bin_id` and, optionally, a handling unit.
Source: ADR-0075.R1

R1236. Transfers move `available` stock only (the allowed status of `transfer_out` and `transfer_in`, ADR-0023.R7), so a line has no status; held stock is released by a `status_change` first.
Source: ADR-0075.R1

R1237. The bins are optional: outside bin-managed warehouses the default bin applies (ADR-0031.R8); in bin-managed warehouses the source bin is the non-pickable bin the confirmed picks moved the goods to, and the receiving bin is the default receiving bin until putaway (ADR-0023.R7, ADR-0023.R14, ADR-0023.R15). The pick tasks that precede `transfer_out` and the putaway task after `transfer_in` are created as for a `delivery` and a receipt.
Source: ADR-0075.R1

R1238. A transfer is a voluntary issue: `transfer_out` is refused with `stock_reserved` when it would cut into reservations (ADR-0023.R13).
Source: ADR-0075.R1

R1239. A `direct` transfer is one document between two physical warehouses: each line posts `transfer_out` and `transfer_in` in one material document, at the issuing value, with both journal lines (ADR-0020.R6).
Source: ADR-0075.R1

R1240. A transfer to a warehouse of kind `transit` or `goods_sent` is two documents (ADR-0023.R7, ADR-0020.R1). The `dispatch` posts `transfer_out` from the source and `transfer_in` into the transit warehouse; its stock is owned and valued there (the keys `inventory_in_transit_posting` and `inventory_goods_sent_posting`).
Source: ADR-0075.R2

R1241. A `receive` names its dispatch (`dispatch_transfer_id`, set exactly for `receive`, `ck_stock_transfer_dispatch`) and posts out of the transit warehouse and into the destination. At most one live receive per dispatch (not canceled and not reversed) is enforced by the command under the dispatch's lock and checked by `INV-867`; the index on `dispatch_transfer_id` is not unique, because the document state is on another table. Each receive line names a dispatch line (`dispatch_line_id`) of the same item, lot, serial and handling unit, and receives no more than that line sent (`INV-867`). The handling unit keeps its identity.
Source: ADR-0075.R2

R1242. The transit warehouse is an ordinary valuation node. The `receive`'s `transfer_out` takes the transit warehouse's value as any issue does (the preliminary price during the period and the actual cost at period end, ADR-0020.R6 and the `transfer` costing role), so a transit balance left by a price change between the two steps is cleared by the period-end costing run, not by a rule of its own.
Source: ADR-0075.R2

R1243. A short receipt leaves the rest in the transit warehouse, visible as stock, until a count of the transit warehouse, with a reason of kind `count_difference`, or a reversal of the dispatch settles it. A write-off document waits for a concrete need.
Source: ADR-0075.R2

R1244. Warehouse kinds are held by `INV-868`: `direct` between two physical warehouses, `dispatch` into a transit or goods-sent warehouse, `receive` out of the dispatch's.
Source: ADR-0075.R2

R1245. A transfer is reversible (ADR-0020.R7): a reversal repeats the lines in the opposite direction, is refused with `negative_stock` when the stock has moved on (ADR-0020.R10), and a `dispatch` with a posted `receive` cannot be reversed before it (`dispatch_has_receive`). The core flag is `is_reversible` true; whether a package requires an internal transport document stays an open question in `open-questions.md`.
Source: ADR-0075.R2

### Stock count

R1246. One count document counts one warehouse; each line is one counted entry. The key of a line is (item, bin, lot or serial, status); `bin_id` is required (the default bin outside bin-managed warehouses). Several lines may share a key, each entered in the product's counting unit with the unit block and summed in the inventory unit (ADR-0056.R15; ADR-0020.R18).
Source: ADR-0075.R3

R1247. `book_quantity` and `book_taken_at` store the stock of the key at the freeze, in the inventory unit: the confirmation of the count task when the warehouse has tasks, else the creation of the draft (ADR-0023.R18). Every line of a key holds the same book quantity, time and difference reason (`INV-865`). A key with no stock has book 0, so a surplus found where nothing was booked is a line.
Source: ADR-0075.R3

R1248. A key with no line is not counted and posts nothing. A counted zero is a line with quantity 0. Serials are counted one by one: quantity 0 or 1.
Source: ADR-0075.R3

R1249. The difference of a key is the sum of its counted quantities minus its stored book quantity, and posting posts that, so a pick or a putaway between the freeze and the posting never becomes a difference (ADR-0023.R18). A positive difference posts `stock_count_surplus`, a negative one `stock_count_shortage`, valued as ADR-0020.R5 and ADR-0020.R11 say (a surplus at the preliminary price, else `preliminary_price_missing`). `INV-866` ties the posted movements to the differences.
Source: ADR-0075.R3

R1250. `count_task_id` names the confirmed count task that created the line, when there is one (ADR-0023.R18).
Source: ADR-0075.R3

R1251. `difference_reason_id` (kind `count_difference`, ADR-0074.R13) and `difference_note` explain a difference; both are nullable in the database, and the reason is the same on every line of a key (`INV-865`). A key with a difference must have a reason while the company setting `documents.reason_required.count_difference` is true (core default true; `reason_required`, ADR-0074.R22); when it is false, a report shows a difference without a reason as unexplained.
Source: ADR-0075.R3

R1252. The regime setting `stock_count.bin_difference_method` of ADR-0023.R18 is unchanged: netting corrects the bins by warehouse movements with `source_command` `count_correction`, and `INV-866` holds either way because it sums per (item, warehouse, lot or serial).
Source: ADR-0075.R3

R1253. Posting runs through the normal lifecycle with policy and approval (ADR-0009.R11, ADR-0009.R13). A shortage and a physical fact always post and cancel reservations deterministically (ADR-0023.R13). The material lines name the key's lowest `line_number` as `source_line_number`.
Source: ADR-0075.R3

R1254. A count is reversible (ADR-0020.R7): the opposite movements are refused with `negative_stock` when a surplus has been consumed.
Source: ADR-0075.R3

### Scrap and internal consumption

R1255. A `scrap_line` names the item, the quantity, the bin, the lot or serial, the status the goods leave (`stock_status`, so held goods are scrapped from `blocked` or `quality_inspection` as ADR-0070.R15 drafts them), an optional handling unit, a scrap reason (`scrap_reason_id`, kind `scrap`) with an optional `reason_note`, and optionally one cost center or one project (never both, `ck_scrap_line_dimension`) when the regime's account determination reads it. The reason is required while `documents.reason_required.scrap` is true, the core default (`reason_required`, ADR-0074.R22); a scrap drafted by the quality executor takes its reason from the usage decision line (ADR-0070.R15).
Source: ADR-0075.R4

R1256. Scrap posts `scrap` (preliminary price, revalued issue, offset key `scrap`). It is a voluntary issue: it is refused with `stock_reserved` when it would cut into reservations (ADR-0023.R13).
Source: ADR-0075.R4

R1257. A scrap line created by the quality executor carries the held status and the inspection lot's link through `inspection_lot_execution.target_table` (DS-58); nothing else of the document is special.
Source: ADR-0075.R4

R1258. An `internal_consumption_line` is `internal` or a `quality_sample` (`consumption_kind`) and names exactly one cost center or project that bears it; a quality sample may name none, because a sample destroyed by testing is issued by a draft that the quality executor creates and a warehouse keeper posts, to the offset key `consumption`, and belongs to the inspection lot (ADR-0070.R15). The status is the one the goods leave. It posts `internal_consumption` or `quality_sample` (preliminary price, revalued issue, offset key `consumption`), a voluntary issue like scrap.
Source: ADR-0075.R5

R1259. The line's cost center or project carries the purpose of a consumption. Account determination reads the cost center of an internal consumption: `cost_center` is a determinant of the transaction key `consumption` beside valuation class, warehouse and item group (ADR-0015), and the accounts stay regime values. The `transaction-keys.csv` row gains `cost_center` once the package files of the regimes have the matching empty `cost_center` column (the package check reads every determinant as a column), before the 1.0.0 catalog release.
Source: ADR-0075.R5, ADR-0075.R5.N1

### Headers, posting and commands of the stock documents

R1260. Each header's primary key is its `document` row (ADR-0009.R1), with `document_type` `stock_transfer`, `stock_count`, `scrap`, `internal_consumption`, `other_receipt`, `other_issue`, `opening_balance` or `transfer_order`. The lines are unique by `line_number`. Every table has `company_id`, composite company keys, `recorded_at` and the owner comment (`inventory`).
Source: ADR-0075.R6

R1261. The registry flags, declared in code (ADR-0009.R2), are posting true, reversible true (ADR-0020.R7) and approval hold allowed true, except `transfer_order`, which is non-posting: `is_posting` false, `is_reversible` false (ADR-0009.R2, ADR-0009.R6).
Source: ADR-0075.R6

R1262. Numbering is a `numbering_configuration` row per type like any posting type (ADR-0009.R15). The authorization leaves are the document types under `inventory` in `authorization-areas.csv` (`stock_transfer`, `stock_count`, `internal_consumption`, `scrap`, `other_receipt`, `other_issue`, `opening_balance`, `transfer_order`); the `warehouse_keeper` template has `inventory` at `post`. `INV-869` holds the movement types each kind posts.
Source: ADR-0075.R6

R1263. `Post<Type>` writes the number, the `material_document` with one line per movement, the stock quantities and values through the stock lock helper, and the journal entry through the posting interfaces in one transaction (ADR-0009.R13; ADR-0022), in the lock order of ADR-0027.R10. A material line names its source line by `source_line_number`, as `goods_receipt` does; no back-link column is kept. The negative stock check is dated and applies to every issuing movement (ADR-0020.R10; ADR-0031.R14).
Source: ADR-0075.R7

R1264. The headers carry `note` (ADR-0074.R16); the document `canceled_reason_id` of ADR-0074.R14 applies to them like any type. They carry no `custom_values` in Phase 1. Scrap, count, consumption, other receipt and other issue headers may name a `business_unit_id` (ADR-0069.R8); a transfer has none, because it posts no profit-and-loss line.
Source: ADR-0075.R8

R1265. Each stock document type has `Create`, `Update`, `Delete` (draft), `Submit`, `Approve`, `Reject`, `Post`, `Cancel` and `Reverse` (ADR-0009.R4, ADR-0009.R11, ADR-0009.R18), as every posting document, plus `GenerateStockCountLines`, which creates the draft's lines with their book quantities for a scope of bins or items and writes no counted quantity. The confirmation of a count task creates the draft count (ADR-0023.R18).
Source: ADR-0075.R9

R1266. The queries are `GetStockCount`, with the differences and reasons per key, and `ListStockTransferInTransit`, the dispatches not fully received. These names are registered in the command registry (ADR-0008) when the code is written.
Source: ADR-0075.R9

R1267. The regime settings `movement_type.sales_return_receipt.value_source` and `movement_type.sales_return_receipt.costing_role` that ADR-0020.R5 requires are in `settings.csv`. The catalog seeds `sales_return_receipt` with (`document`, `issue_return`), the original delivery line's issue cost, set and confirmed by the author, and `issue_return` is built in Phase 1. This deliberately deviates from SAP, which values a customer return at the current price. Every stock document type named by ADR-0027.R7 has its DDL.
Source: ADR-0075.R10, ADR-0075.R10.N1

### Other receipt, other issue and opening balance

R1268. An other receipt (`inventory`, reversible) takes in goods without a purchase, sales or production source. An `other_receipt_line` names the item, the unit block, the bin (else the default receiving bin, with a putaway task in a bin-managed warehouse, ADR-0023.R7), the lot or serial, the status (`quality_inspection` when the product requires inspection at receipt, ADR-0070.R2), an optional handling unit, its value `company_amount` (the movement type's value source is `document`) and a reason of kind `other_receipt` with an optional `reason_note`, required while `documents.reason_required.other_receipt` is true, the core default (ADR-0074.R22). It posts `other_receipt` (receipt, offset key `other_receipt_offset`). A pre-cutover customer return is an other receipt (DS-22 comment on `return_from_customer`).
Source: ADR-0075.R11

R1269. An other issue (`inventory`, reversible) issues goods for a purpose that no other movement type covers. An `other_issue_line` names the item, the unit block, the bin, the lot or serial, the status the goods leave, an optional handling unit, a reason of kind `other_issue` with an optional `reason_note` (required while `documents.reason_required.other_issue` is true, the core default), and at most one cost center or project (`ck_other_issue_line_dimension`). It posts `other_issue` (preliminary price, revalued issue, offset key `other_issue_offset`), a voluntary issue refused with `stock_reserved` when it would cut into reservations (ADR-0023.R13).
Source: ADR-0075.R12

R1270. The bearer of an other issue is optional because the catalog's offset of `other_issue` is an "other expense" key that takes no bearer; an issue that a cost center or project bears is an internal consumption, which requires one. A company whose account determination reads a bearer on other issues names one.
Source: ADR-0075.R12

R1271. An opening balance (`inventory`, reversible within the migration) is the migration opening stock of ADR-0044.R9. An `opening_balance_line` names the item, the warehouse, the bin (the final bin, else the default bin), the status (any, ADR-0023.R7), an optional handling unit, the lot or serial, the unit block and its value `company_amount`.
Source: ADR-0075.R13

R1272. An opening balance posts only into the migration period while the migration is loading or reconciling; anywhere else it is `migration_not_open` (ADR-0044.R2; `INV-870`).
Source: ADR-0075.R13

R1273. The import gives one total per item and valuation area; the handler spreads it over the item's lines in that area by quantity, by largest remainder, so the lines sum exactly to the total (`opening_unit_value_differs` when a total is missing, ADR-0044.R9; `INV-872`).
Source: ADR-0075.R13

R1274. The total divided by the quantity of the item in the area is the area's first `preliminary_price`, with `price_source` `opening`, so no costing run is needed in the migration period (ADR-0044.R9; ADR-0020.R11).
Source: ADR-0075.R13

R1275. An opening balance posts `opening_balance` (receipt, offset key `opening_balance`, the opening balance clearing account). It has no reason, no business unit and no custom values; it creates no task.
Source: ADR-0075.R13

### Transfer order

R1276. A transfer order (`inventory`, non-posting, change orders from step 5, ADR-0028.R4) is the demand document of a planned move (ADR-0027.R7): ADR-0024.R8 reads its lines as demand at the source and supply at the destination (a transit warehouse included), ADR-0023.R13 reserves stock for its lines and ADR-0061.R9 barcodes it. A transfer order plans and reserves; a stock transfer moves and posts.
Source: ADR-0075.R14

R1277. The `transfer_order` header names `from_warehouse_id`, `to_warehouse_id` (different), an optional `transfer_route_id` (when planning converted it, ADR-0024.R22), `requested_date` and a `note`. A `transfer_order_line` names the item, the unit block and an optional lot (never a serial, as a reservation).
Source: ADR-0075.R14

R1278. Approval creates one `demand_supply_line` per line and direction (`transfer_order_line_id`, with its foreign key; ADR-0028.R2), released like the other demand rows.
Source: ADR-0075.R14

R1279. A `stock_transfer_line` names the order line it fulfils (`transfer_order_line_id`): a `direct` transfer between the order's two warehouses, a `dispatch` from its source, a `receive` into its destination, of the same item (`transfer_order_line_invalid`; `INV-871`). The order line's open quantity is its quantity less what posted receipts (or direct transfers) delivered; the order closes `fulfilled` at zero, or a person closes it (ADR-0009.R6).
Source: ADR-0075.R14

### Count settings

R1280. The regime settings that ADR-0020.R5 and ADR-0023.R18 require for counts are in `settings.csv`, each a required regime setting with no core default (`fail_closed`, so a posting without it fails with `regime_configuration_missing`), set by the regime package: `movement_type.stock_count_shortage.value_source` and `movement_type.stock_count_surplus.value_source` (bounds `preliminary_price`), `movement_type.stock_count_shortage.costing_role` and `movement_type.stock_count_surplus.costing_role` (bounds `receipt`, `revalued_issue`), and `stock_count.bin_difference_method` (`net` or `gross`). No preset sets them: presets carry company settings (ADR-0067), and these are the regime's.
Source: ADR-0075.R15

## Invariants

Statements are those of `invariants.csv`. This chunk holds the rows whose catalog source is a rule of this chunk and the
owned rows that no other chunk states (`INV-28`, `INV-602`, `INV-604`).

| Invariant | Name | Check point | Statement | Protects |
| --- | --- | --- | --- | --- |
| `INV-28` | `inventory_lines_carry_item` | day | Every line on an inventory account carries item and warehouse, and a material document line when its document has a material document. | ADR-0014.R10, ADR-0010.R5 |
| `INV-602` | `stock_only_in_inventory_unit` | day | Every material document line's quantity equals its source document line's inventory quantity, and every stock, reservation, demand, supply and planned quantity is at its item's inventory unit decimals. | ADR-0056.R1, ADR-0056.R9 |
| `INV-604` | `serial_units_exact` | day | Every unit a serial-tracked product resolves (its product and item rows and catalog units) is exact, and every line of such a product has an exact snapshot. | ADR-0056.R4 |
| `INV-810` | `valuation_area_matches_level` | day | Every `material_document_line` and `preliminary_price` row has `valuation_site_id` and `valuation_warehouse_id` both null at level company; at level site only `valuation_site_id`, equal to the site of the line's warehouse (for transit and goods_sent, the site of its valuation warehouse); at level warehouse only `valuation_warehouse_id`, equal to the line's physical warehouse or the physical warehouse it is attached to. | R1223-R1225 |
| `INV-865` | `count_key_consistent` | day | Every line of one count key (item, bin, lot or serial, status) holds the same book quantity, freeze time and difference reason. | R1247, R1251 |
| `INV-866` | `count_difference_posted_exactly` | day | For a posted stock count, per item, warehouse and lot or serial, the signed sum of its material lines equals the sum over its keys of the counted quantity minus the stored book quantity, with bin netting or without. | R1249, R1252 |
| `INV-867` | `transfer_receive_within_dispatch` | day | A posted receive names the posted dispatch of its `dispatch_transfer_id`; each of its lines names a dispatch line of the same item, lot, serial and handling unit and receives no more than it sent; a dispatch has at most one live receive (not canceled, not reversed). | R1241 |
| `INV-868` | `transfer_warehouse_kinds` | day | A direct stock transfer is between two physical warehouses, a dispatch goes to a transit or goods_sent warehouse, and a receive comes out of its dispatch's destination. | R1244 |
| `INV-869` | `stock_document_movement_types` | day | The material lines of a posted stock document use only the movement types of its kind (`transfer_out` and `transfer_in`; the two count types; `scrap`; `internal_consumption` or `quality_sample` by line kind; `other_receipt`; `other_issue`; `opening_balance`; a transfer order posts none), in the type's direction, flipped for a reversal. | R1234, R1262 |
| `INV-870` | `opening_balance_in_migration_period` | day | Every posted `opening_balance` posts in the migration period of its company. | R1272 |
| `INV-871` | `transfer_fulfils_order_line` | day | A stock transfer line that names a transfer order line has its item, and its warehouses fit the step: both of the order's for direct, its source for dispatch, its destination for receive; received and directly transferred quantities never exceed the ordered quantity by more than the unit rounding tolerance. | R1279 |
| `INV-872` | `opening_value_spread_exact` | day | The opening balance lines of an item and valuation area sum exactly to the area's total, and the first preliminary price of the area is that total divided by the quantity. | R1273, R1274 |

The row of `INV-715` (protects R1206) stands in chunk 1.

Named by `ref:` units of this chunk and stated by their own modules: `INV-620` to `INV-624` (master_data), `INV-730`,
`INV-739`, `INV-741`.

## Edge cases

| Edge case | Name | Case | Outcome | Protects |
| --- | --- | --- | --- | --- |
| `EC-08` | `concurrent_issues_same_item` | Two issues of the same item and warehouse in one concurrency_group, with stock sufficient for both; concurrency itself is exercised by PAR-01. | `must_succeed` | Principle 9 |
| `EC-11` | `landed_cost_after_partial_sale` | A freight cost allocated after part of the goods it covers was sold, in the same open period; at steps 3-4 the cost source is the documented test journal. | `must_succeed` | ADR-0021.R6 |
| `EC-122` | `variable_measure_receipt` | A label with (01) indicator 9 and (3103) is received into an item kept in kilograms (identity) and into one kept in grams (through the catalog conversion); a (3105) measure with a non-zero fifth decimal is refused with `too_many_decimal_places`. | `must_succeed` | R1201 |
| `EC-123` | `serials_confirmed_by_handling_unit` | A pick of serial-tracked goods is confirmed by scanning the closed handling unit that holds exactly the serials; in another task one serial scanned twice is refused with `serial_already_scanned`. | `must_succeed` | R1202, R1203 |
| `EC-190` | `purchase_return_option_from_period_start` | A company switches the purchase return option mid-period and is refused with `setting_effective_date_invalid`; from the next period start it succeeds, and a return in that period is valued at the preliminary price with the difference to the price difference key. | `must_reject:setting_effective_date_invalid`, then `must_succeed` | R1206, R1207 |
| `EC-191` | `day00_reject_category` | A category set to reject refuses a (17) with day 00 as `gs1_invalid` (date), while another category reads it as the month's last day. | `must_reject:gs1_invalid`; `must_succeed` | R1208 |
| `EC-200` | `shortage_cleared_while_transfer_pending` | A goods receipt covers the target's shortage while a `transfer_reservation` proposal waits; at execution the target's short quantity is 0, so the transfer fails with `reservation_transfer_invalid` although nothing reserved the receipt, and the next `RunProductionOrderCheck` closes the shortage item. | `must_reject:reservation_transfer_invalid`, then `must_succeed` | R1214 |
| `EC-219` | `reservation_transfer_only_by_proposal` | A reservation transfer outside an approved proposal is refused; through one, the source is reduced and the target gains the same quantity. | `must_reject:proposal_required`, then `must_succeed` | R1217, R1218 |
| `EC-260` | `site_internal_transfer_neutral` | At valuation level site, a transfer from a site's raw-materials warehouse to its production warehouse leaves the site's area value unchanged after period-end costing, while a transfer to a second site moves at the issuing site's average. | `must_succeed` | R1226, R1227 |
| `EC-261` | `second_site_requires_choice` | A one-site company creates a warehouse without naming a site and receives goods into it; after a second site is created, a warehouse created without a site is refused, and moving the stocked warehouse to the second site is refused. | `must_succeed`; `must_reject:site_required`; `must_reject:warehouse_site_fixed` | ADR-0068.R2 |
| `EC-264` | `carrier_on_delivery` | A delivery copies the carrier of its sales order's carrier method, the carrier is changed before posting, and the tracking link is shown; a carrier partner without an active supplier role is refused. | `must_succeed`; `must_reject:partner_role_missing` | ADR-0068.R22 |
| `EC-320` | `count_summed_counting_units` | One count key entered in three lines in cartons and pieces: the lines sum in the inventory unit and one difference posts. | `must_succeed` | R1246 |
| `EC-321` | `count_uncounted_key_posts_nothing` | A bin with two items where one is counted: the other posts nothing; a counted zero posts a shortage. | `must_succeed` | R1248 |
| `EC-322` | `count_picks_after_freeze` | A pick between the freeze and the posting is not a difference: the posted difference is the counted quantity minus the stored book quantity. | `must_succeed` | R1249 |
| `EC-323` | `count_reversal_refused_when_consumed` | A surplus count whose stock was shipped cannot be reversed. | `must_reject:negative_stock` | R1254 |
| `EC-324` | `count_shortage_cancels_reservation` | A count shortage that cuts into a reservation posts, cancels the reservation deterministically and raises an exception. | `must_succeed` | R1253 |
| `EC-325` | `transfer_through_transit_short_receipt` | A dispatch of 10 is received as 8; 2 remain in the transit warehouse; the dispatch cannot be reversed before its receive. | `must_succeed`; `must_reject:dispatch_has_receive` | R1243, R1245 |
| `EC-326` | `transfer_reversal_refused_after_shipment` | A direct transfer whose goods were delivered is not reversible. | `must_reject:negative_stock` | R1239, R1245 |
| `EC-327` | `scrap_from_held_status` | Held goods are scrapped from blocked with a reason; a scrap that would cut into a reservation is refused with `stock_reserved`. | `must_succeed`; `must_reject:stock_reserved` | R1255, R1256 |
| `EC-328` | `consumption_one_bearer` | An internal consumption naming both a cost center and a project, or neither, is refused; a quality sample may name neither. | `must_succeed`; `must_reject:ck_internal_consumption_line_dimension` | R1258 |
| `EC-329` | `scrap_without_reason` | With `documents.reason_required.scrap` true, a scrap line without a reason is refused with `reason_required`; a reason of another kind is refused with `reason_invalid`. | `must_reject:reason_required`; `must_reject:reason_invalid` | R1255 |
| `EC-331` | `other_issue_requires_reason` | An other issue line without a reason is refused with `reason_required`; with a reason of kind other_issue and a cost center it posts. | `must_reject:reason_required`; `must_succeed` | R1269 |
| `EC-332` | `other_receipt_valued_from_document` | An other receipt of 10 units valued 1,000 posts 1,000 into stock and to the offset key `other_receipt_offset`. | `must_succeed` | R1268 |
| `EC-333` | `opening_balance_outside_migration` | An opening balance dated in an ordinary period is refused with `migration_not_open`. | `must_reject:migration_not_open` | R1272 |
| `EC-334` | `opening_value_spread_sets_price` | One item in three bins with a total of 1,000 for 3 units: the lines take 333, 333 and 334 by largest remainder, and the first preliminary price is 1000/3. | `must_succeed` | R1273, R1274 |
| `EC-335` | `transfer_order_two_step_fulfilment` | A transfer order of 10 fulfilled by a dispatch of 10 and a receive of 8; the order line stays open for 2 until a person closes it or a second transfer arrives. | `must_succeed` | R1279 |
| `EC-336` | `transfer_order_line_wrong_warehouse` | A direct transfer that names an order line of other warehouses is refused with `transfer_order_line_invalid`. | `must_reject:transfer_order_line_invalid` | R1279 |
| `EC-337` | `transfer_order_reservation` | The order line's demand row at the source reserves stock, and a scrap that would cut into it is refused with `stock_reserved`. | `must_reject:stock_reserved` | R1276, R1278 |
| `EC-338` | `count_settings_missing` | A count posting in a company whose regime sets no `movement_type.stock_count_shortage.value_source` fails with `regime_configuration_missing`. | `must_reject:regime_configuration_missing` | R1280 |

Named by `ref:` units of this chunk and stated by their own modules: `EC-120`, `EC-121`, `EC-125` to `EC-127`, `EC-129`
(master_data), `EC-330` (ADR-0074.R22). The rows of `EC-119`, `EC-124` and `EC-128` stand in chunk 6.

## Settings

| Key | Value type | Scopes | Core default | Used by |
| --- | --- | --- | --- | --- |
| `movement_type.purchase_return.include_landed_cost` | boolean | `regime`, `company` | `true` | R1205 |
| `movement_type.stock_count_shortage.value_source` | enum `preliminary_price` | `regime` | none (`fail_closed`) | R1280 |
| `movement_type.stock_count_surplus.value_source` | enum `preliminary_price` | `regime` | none (`fail_closed`) | R1280 |
| `movement_type.stock_count_shortage.costing_role` | enum `receipt`, `revalued_issue` | `regime` | none (`fail_closed`) | R1280 |
| `movement_type.stock_count_surplus.costing_role` | enum `receipt`, `revalued_issue` | `regime` | none (`fail_closed`) | R1280 |
| `stock_count.bin_difference_method` | enum `net`, `gross` | `regime` | none (`fail_closed`) | R1252, R1280 |
| `barcode.gs1.day00_policy.<expiry_ai>` | enum `last_day`, `first_day`, `reject` | `company`, `product_category` | `last_day` | R1208 |
| `barcode.gs1.day00_policy.<production_ai>` | enum `last_day`, `first_day`, `reject` | `company`, `product_category` | `first_day` | R1208 |
| `barcode.unknown_ai_policy` | enum `report_and_ignore`, `reject` | `company` | `report_and_ignore` | R1210 |
| `barcode.separator_suspect` | enum `stop_and_confirm`, `trust_transport` | `company`, `scanner_profile` | `stop_and_confirm` | R1211 |

The rows of `movement_type.purchase_return.value_source`, `movement_type.purchase_return.costing_role`, `movement_type.sales_return_receipt.value_source` and `movement_type.sales_return_receipt.costing_role` stand in chunk 1 (used here by R1204 and R1267), the row of `barcode.gs1.best_before_fills_expiry` in chunk 6 (used here by R1209).

Reads: `documents.reason_required.count_difference`, `documents.reason_required.scrap`, `documents.reason_required.return`, `documents.reason_required.reject`, `documents.reason_required.other_receipt`, `documents.reason_required.other_issue`, `documents.reason_required.cancel`, `documents.reason_required.block` (ADR-0074.R22); `production.agent.shortage_candidate_kinds` (ADR-0064.R16); `tax.services_place_of_supply`, `tax.destination_party` (ADR-0080.R5.N1); `barcode.gs_substitute`, `barcode.prefix.handling_unit`, `barcode.prefix.lot`, `barcode.prefix.serial`, `barcode.prefix.item_unit`, `barcode.sscc_reuse_months` (ADR-0061.R29).

## UI annotations

None: the sources hold no ADR-0077 annotation for the units of this chunk or for the owned rows of the rest.

## Conflicts

CONFLICT ADR-0063.R24: the landed cost share a purchase return carries follows the late landed cost law of ADR-0021.R6.N2 (booked in the period of the cost document as a value-only receipt_addition, no closed period recomputed); its case (c), interim and flagged, governs a return posted after the cost (R1205).
CONFLICT ADR-0075.R5: ADR-0075.R5.N1 decides the question left open by the rule: account determination reads the cost center of an internal consumption, so cost_center becomes a determinant of the consumption key (R1259).
CONFLICT ADR-0075.R10: ADR-0075.R10.N1 sets and confirms the interim seed value of the sales return receipt pair, document value with issue_return, which the rule still called open (R1267).

## Proposed (not law)

None

## Trace

| Source | Where |
| --- | --- |
| ADR-0061.R18 | R1201 |
| ADR-0061.R19 | R1202, R1203 |
| ADR-0061.R27 | ref: ADR-0061.R27 |
| ADR-0061.R29 | ref: ADR-0061.R29 |
| ADR-0062.R15 | ref: ADR-0062.R15 |
| ADR-0063.R24 | R1204-R1207 |
| ADR-0063.R26 | R1208-R1212 |
| ADR-0064.R9 | ref: ADR-0064.R9 |
| ADR-0064.R10 | ref: ADR-0064.R10 |
| ADR-0064.R10.N1 | ref: ADR-0064.R10 |
| ADR-0064.R16 | ref: ADR-0064.R16 |
| ADR-0064.R19.N2 | ref: ADR-0064.R19 |
| ADR-0064.R24 | R1213-R1218 |
| ADR-0064.R27 | R1219-R1222 |
| ADR-0064.R29 | ref: ADR-0064.R29 |
| ADR-0068.R8 | R1223-R1225 |
| ADR-0068.R9 | R1226-R1228 |
| ADR-0068.R19 | ref: ADR-0068.R19 |
| ADR-0068.R20 | R1229, R1230 |
| ADR-0068.R22 | ref: ADR-0068.R22 |
| ADR-0068.R22.N1 | ref: ADR-0068.R22 |
| ADR-0068.R25 | ref: ADR-0068.R25 |
| ADR-0069.R8.N1 | ref: ADR-0069.R8 |
| ADR-0070.R1 | ref: ADR-0070.R1 |
| ADR-0070.R2 | ref: ADR-0070.R2 |
| ADR-0070.R9 | ref: ADR-0070.R9 |
| ADR-0070.R12 | ref: ADR-0070.R12 |
| ADR-0070.R15 | ref: ADR-0070.R15 |
| ADR-0070.R15.N1 | ref: ADR-0070.R15 |
| ADR-0070.R16 | ref: ADR-0070.R16 |
| ADR-0071.R2.N1 | ref: ADR-0071.R2 |
| ADR-0071.R4 | ref: ADR-0071.R4 |
| ADR-0071.R4.N1 | ref: ADR-0071.R4 |
| ADR-0074.D0 | ref: ADR-0074.D0 |
| ADR-0074.R2 | R1231, R1232 |
| ADR-0074.R13 | ref: ADR-0074.R13 |
| ADR-0074.R16 | R1233 |
| ADR-0074.R22 | ref: ADR-0074.R22 |
| ADR-0075.D0 | R1234 |
| ADR-0075.R1 | R1235-R1239 |
| ADR-0075.R2 | R1240-R1245 |
| ADR-0075.R3 | R1246-R1254 |
| ADR-0075.R4 | R1255-R1257 |
| ADR-0075.R5 | R1258, R1259 |
| ADR-0075.R5.N1 | R1259 |
| ADR-0075.R6 | R1260-R1262 |
| ADR-0075.R7 | R1263 |
| ADR-0075.R8 | R1264 |
| ADR-0075.R9 | R1265, R1266 |
| ADR-0075.R10 | R1267 |
| ADR-0075.R10.N1 | R1267 |
| ADR-0075.R11 | R1268 |
| ADR-0075.R12 | R1269, R1270 |
| ADR-0075.R13 | R1271-R1275 |
| ADR-0075.R14 | R1276-R1279 |
| ADR-0075.R15 | R1280 |
| ADR-0080.R5.N1 | ref: ADR-0080.R5 |
