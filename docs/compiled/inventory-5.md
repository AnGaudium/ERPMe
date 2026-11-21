Module: inventory    Chunk: 5 of 7    Source ADRs: ADR-0027, ADR-0028, ADR-0030, ADR-0031, ADR-0034, ADR-0035, ADR-0037, ADR-0044, ADR-0047
Build step(s): 1, 3, 4, 4b, 5    Generated from index: 30d5706    Compiled by: Claude Opus 5.5, 2026-11-21

# Compiled spec: `inventory`, chunk 5

## Purpose

`inventory` owns stock quantities and values, stock documents, warehouse tasks, reservations and the open demand and
supply read model (ADR-0022.R2). This chunk states the invoice-to-stock value seam (late purchase cost booked in the
period of the cost document), the owner axis, the default bin, the dated negative-stock check, the typed line references
of `demand_supply_line`, the production staging and movement types, the processor location, opening stock, and the
inventory side of deliveries, goods receipts and returns of commercial order lines. Commercial documents, production
orders, planning, localization packages and imports are other modules'; their units are traced `ref:` and not restated.

## Entities and tables

DDL: `docs/design/DS-22-09-42-commercial-inventory.sql`, `docs/design/DS-43-54-planning-production.sql`,
`docs/design/DS-20-master-data.sql`. The stock documents of commercial order lines (R832 to R841):

| Table | Meaning | Key | Parent | Owner |
| --- | --- | --- | --- | --- |
| `goods_receipt` | Goods receipt header; `partner_id` the supplier (R839, R840) | `id` = its `document` row | `document` | `inventory` |
| `goods_receipt_line` | One received item quantity, with `purchase_order_line_id` and its GR/IR position range (R839) | `id`; unique (`goods_receipt_id`, `line_number`) | `goods_receipt` | `inventory` |
| `delivery` | Delivery header; `partner_id` the customer (R833) | `id` = its `document` row | `document` | `inventory` |
| `delivery_line` | One delivered item quantity, with `sales_order_line_id` (R833) | `id`; unique (`delivery_id`, `line_number`) | `delivery` | `inventory` |
| `return_to_supplier` | Return to supplier header; its `document` row's `correction_of_id` is the goods receipt (R841) | `id` = its `document` row | `document` | `inventory` |
| `return_to_supplier_line` | One returned quantity, naming `goods_receipt_line_id` (R841) | `id`; unique (`return_to_supplier_id`, `line_number`) | `return_to_supplier` | `inventory` |
| `return_from_customer` | Return from customer header; its `document` row's `correction_of_id` is the delivery (R834, R835) | `id` = its `document` row | `document` | `inventory` |
| `return_from_customer_line` | One returned quantity, naming `delivery_line_id` (NOT NULL) (R835) | `id`; unique (`return_from_customer_id`, `line_number`) | `return_from_customer` | `inventory` |

This chunk also adds to, or constrains:

- `stock_quantity`, `material_document_line`, `warehouse_movement`, `stock_reservation`, `warehouse_task`: `owner_partner_id` (R806); `bin_id` NOT NULL on `stock_quantity`, `material_document_line`, `warehouse_movement` and `handling_unit` (R812).
- `material_document_line`: `posting_date` and its index (R819, R820).
- `demand_supply_line`: typed source-line columns, roles and lifecycle (R823 to R827); the stored open quantity (R828).
- `stock_reservation`: `picked_quantity`, `fulfilled_quantity` (R829), `destination_bin_id`, `release_sequence` (R831).
- `bin`: the default bin (R811) and `bin_type` `production` (R831).
- `opening_balance`, `opening_balance_line`: opening stock (R842 to R844).
- `movement_type`: the production movement types (R845).

Reads: `warehouse` (`default_bin_id`, `is_bin_managed`, `processor_partner_id`, `default_receiving_bin_id`, `default_shipping_bin_id`), `landed_cost`, `production_order_component`, `production_order_output`, `transfer_order_line`, `stock_transfer_line`, `preliminary_price`, `stock_value`.

## Commands and queries

| Name | Actor / authorization | Input | Effect | Events | Error codes |
| --- | --- | --- | --- | --- | --- |
| `CreateWarehouse` | not stated | A warehouse of kind `physical`, `transit` or `goods_sent` | Also creates its default bin and default zone (R811) | not stated | not stated |
| `UpdateWarehouse` | `human_only`; leaf `warehouse` (area `master_data`) | `is_bin_managed: true` with `default_receiving_bin_id` and `default_shipping_bin_id`, on a `physical` warehouse | Switches the warehouse to bin-managed; the default bin becomes an ordinary storage bin; no way back (R436, R813) | not stated | not stated |

`RunPickRelease` (R830, R831) and `PostDelivery` (R833) have their rows in chunk 4.

The posting commands of `goods_receipt`, `return_from_customer`, `return_to_supplier` and `opening_balance` (leaves of the same names under area `inventory`) carry names not stated in these sources; their rules are R839 to R841, R835 to R838 and R842 to R844.

Not commands: the posting interface `inventory.contract.adjust_receipt_value`, called by the purchase invoice handler (R801 to R805).

The credit check of the commercial seams is one exposure read under the partner lock at order `Submit`; deliveries respect a credit hold instead (ADR-0047.R18), which `inventory` enforces with `demand_on_hold` (R833).

Codes raised by the rules of this chunk and bound to no named command: `negative_stock` (R821), `warehouse_not_bin_managed` (R812), `movement_not_allowed_at_processor` (R818), `receipt_exceeds_order` (R839), `opening_unit_value_differs` (R843), `migration_not_open` (R842), `negative_stock_value` (R803).

## Rules

### Landed cost from purchase invoices

R801. When account determination sends an invoice-versus-order difference to stock (ADR-0021.R12), the purchase invoice handler calls `inventory.contract.adjust_receipt_value`. The interface writes `landed_cost` documents with `cost_type` `price_difference`, one per receipt period of the matched receipt lines; this split is no longer needed and stays, interim, until DS-22 designs the invoice.
Source: ADR-0030.R1, ADR-0030.R2.N1

R802. These `landed_cost` documents are written directly as `posted`, inside the invoice's transaction and plan, with no policy decision or approval of their own (ADR-0022.R4). Each carries `caused_by_document_id`, the invoice. The receipts are locked as referenced documents (ADR-0027.R10, class 1), and the documents are numbered at class 11.
Source: ADR-0030.R1

R803. A correction or reversal of the invoice corrects these documents through the same interface, by `landed_cost_correction` (ADR-0021.R9). `negative_stock_value` (ADR-0021.R9) can still reject the invoice.
Source: ADR-0030.R1

R804. A document written by `inventory.contract.adjust_receipt_value` is booked in its own posting period, whatever the state (`open`, `soft_locked` or `locked`) of the receipt's period, and the rule does not depend on who posts (interim, chief architect under the author's delegation of 2026-11-21; `ADR-0021.R6.N2` governs late purchase cost). Its amount enters stock as a value-only `receipt_addition` that takes part in the actual cost of that period. No locked period is recomputed, nothing is allocated retroactively to past consumers, `consumer_split` does not run, and no document is forced back into the receipt's period.
Source: ADR-0030.R2, ADR-0030.R2.N1

R805. The posting date of such a document is:
- the invoice's posting date, when that date's inventory period is not locked and the date is not earlier than the posting date of the latest receipt the document targets;
- that receipt's posting date, when the invoice is earlier;
- the first day of the first inventory period after the invoice's date that is not locked, when the invoice's period is locked.
Source: ADR-0030.R2, ADR-0030.R2.N1

### Owner axis

R806. `owner_partner_id` (null for own stock) is a column of `stock_quantity` (part of its key), `material_document_line`, `warehouse_movement`, `stock_reservation` and `warehouse_task`. It is also reserved on `production_order_component`, `production_order_output` and `demand_supply_line` (ADR-0037.R7). The columns cost nothing before step 3; adding them after go-live would migrate append-only tables.
Source: ADR-0030.R8

R807. Non-owned stock is goods sold but held for a customer, or consignment later. It has quantity and no value, so it never enters `stock_value` and leaves `INV-20` unaffected. It is not available to promise. Phase 1 creates no non-owned stock, and every row has a null owner.
Source: ADR-0030.R8

R808. When non-owned stock is first created, the dated negative check (ADR-0020.R10) and the keys of `INV-21`, `INV-24`, `INV-50`, `INV-51` and `INV-52` become per owner, and `INV-54` counts own stock only. A serial stays one physical unit whoever owns it, so the serial rule and `INV-22` stay across owners.
Source: ADR-0030.R8

R809. The stock key's unique index treats the null owner as one value (`NULLS NOT DISTINCT`), as for handling unit; bins are never null (R812). The accounting of goods sold but held, and whether delivery and invoice must share a date under the localization package's law, are the author's (open question).
Source: ADR-0030.R8

R810. The owner axis has no ownership-transfer default, so nothing reads a document's Incoterm here. When ownership of goods in transit from the shipping point is designed, the Incoterm is its input.
Source: ADR-0030.R8.N1

### Bins and the default bin

R811. Every warehouse, of every kind (`physical`, `transit`, `goods_sent`), has a default bin and a default zone, both created by `CreateWarehouse`, and `warehouse.default_bin_id` names the bin. The default bin has code `DEFAULT`, barcode `<warehouse code>-DEFAULT`, type `storage`, and no capacity or mix limits. It cannot be deactivated while the warehouse is not bin-managed.
Source: ADR-0031.R7

R812. `bin_id` is NOT NULL in `stock_quantity`, `material_document_line`, `warehouse_movement` and `handling_unit`. In a warehouse that is not bin-managed, clients omit `bin_id` and the handler fills the default bin; a bin given for such a warehouse is rejected with `warehouse_not_bin_managed`. Handling units in `transit` and `goods_sent` warehouses carry the default bin. The stock key's unique index needs `NULLS NOT DISTINCT` for lot or serial, handling unit and owner, not for the bin.
Source: ADR-0031.R8

R813. `is_bin_managed` means bins are visible and putaway, pick, move and replenishment tasks are used. A warehouse that is not bin-managed has exactly its default bin, which the UI hides. Only `physical` warehouses may switch: `UpdateWarehouse` (`human_only`) may set `is_bin_managed: true` at any time, together with the `default_receiving_bin_id` and `default_shipping_bin_id` that ADR-0023.R1 requires. The default bin then becomes an ordinary storage bin, stock leaves it by ordinary move tasks, and deliveries created before the switch issue from the default bin. The reverse is not supported. There is no `ConvertWarehouse` and no `bin_management_locked`.
Source: ADR-0031.R9

R814. Bin rows are locked only for capacity, mix and count checks (ADR-0027.R10, class 8). A default bin has no limits. In a warehouse that is not bin-managed, count tasks cover items and the derived bin block of ADR-0023.R18 does not apply, so such a warehouse takes no bin lock.
Source: ADR-0031.R10

R815. `INV-56`: every stock row has a bin of its own warehouse, and a warehouse that is not bin-managed has exactly one bin, its `default_bin_id`.
Source: ADR-0031.R11

### Processor locations

R816. A processor location is a `physical` warehouse with `processor_partner_id` (a column of the warehouse, ADR-0020.R1), not bin-managed. A company has at most one active location per processor. Stock there is ours and valued, in the area the company's valuation level gives (ADR-0020.R2).
Source: ADR-0037.R1

R817. Stock lines at a processor location use the inventory key `inventory_at_processor_posting`, with the inventory leaves and the determinants valuation class and warehouse, so a regime can show stock at processors on its own account; the accounts a package maps to it are flagged package content of the localization package. Interim, flagged: materials stay inventory until the service receipt consumes them. Another accounting at sending is the author's (open question) and would need the transfer to post per order.
Source: ADR-0037.R1

R818. Materials go to a processor location by an ordinary transfer, moving quantity and value (ADR-0020.R6). Whether an invoice is issued for materials sent to a domestic processor is flagged package content of the localization package (`unverified`); whether an internal transport document is needed is the regime's setting (DS-24). Only transfers in and out, production issues and returns, count differences and opening balances (stock at processors at cut-over) may post at a processor location; anything else is rejected with `movement_not_allowed_at_processor`.
Source: ADR-0037.R1

### Dated negative-stock check

R819. `material_document_line` has `posting_date`, copied from its posting document and protected by the append-only trigger. `INV-48` checks that it equals the document's posting date.
Source: ADR-0031.R12

R820. An index on `material_document_line (company_id, item_id, warehouse_id, lot_id, serial_number_id, posting_date) INCLUDE (direction, quantity)` lets the check run as an index-only scan.
Source: ADR-0031.R13

R821. The dated negative-stock check runs under the `stock_value` lock (ADR-0020.R10). δ is the document's net quantity change per key; lines are not checked one by one, and a key with δ ≥ 0 is not checked. For posting date p:
1. `current` is the key's total from `stock_quantity`, across bins, statuses, handling units and, until non-owned stock first appears, owners (R808); it includes lines already posted with later dates;
2. read that key's lines with `posting_date > p`, grouped by date;
3. for each date d in {p} and those dates, closing(d) = `current` minus the sum of changes dated after d;
4. reject with `negative_stock` if min over d of closing(d) + δ < 0.
The scan reads every later line of the key; those lie in open periods and in future periods up to `future_posting_periods` (ADR-0012.R6), so a backdated posting into an early open period reads more. In simulate mode the helper's in-memory overlay feeds the same computation.
Source: ADR-0031.R14

R822. `INV-48` (area `inventory`, coded in 40–49) and `INV-58` (R829) are first executable at step 3; `INV-56` is restated by R815. The DS-16 hash test is ADR-0031.R4.
Source: ADR-0031.R18

### Demand and supply lines

R823. Commercial document lines and `demand_supply_line` (ADR-0024.R8) refer to other document lines by typed foreign keys, each named after the referenced line table, e.g. `sales_order_line_id`, `transfer_order_line_id`, `goods_receipt_line_id`. A line referred to as its correction uses `correction_of_line_id` (ADR-0004.R12); it may name a line of another line table where the correction is a document of another type (ADR-0047.R2).
Source: ADR-0028.R2, ADR-0028.R2.N2

R824. Each table declares its reference roles; each role allows at most one non-null column, and a role is mandatory where the table declares it. The execution tables `stock_reservation`, `warehouse_task` and pegging refer to `demand_supply_line_id` only (ADR-0023.R13, ADR-0023.R14, ADR-0024.R20).
Source: ADR-0028.R2

R825. From step 3 `demand_supply_line` has a nullable column per source line table, with `source_kind` naming the one that is set: `sales_order_line_id`, `purchase_order_line_id`, `purchase_request_line_id` (foreign keys added at step 5, so the table does not change) and `transfer_order_line_id`, whose key comes with `transfer_order_line`; `stock_transfer_line` names the order line it fulfils by the same typed key (ADR-0075.R14). Later line tables (production) are the author's decision under B3.
Source: ADR-0028.R2, ADR-0028.R2.N3

R826. `demand_supply_line` rows are unique per source line and direction, are created before the first reservation, and are closed with `closed_reason` (`fulfilled`, `canceled`) when a line is removed as a change takes force. A draft purchase request or order line whose supply row carries `origin_planned_order_id` or pegging cannot be removed: its quantity goes to zero, or the document is canceled, closing the row as `canceled`. Other lines removed in draft delete their rows. Rows are never deleted or rebuilt once their document has left draft (ADR-0047.R10).
Source: ADR-0028.R2

R827. Interim, flagged for the author under B3: the columns `production_order_component_id`, `production_order_output_id` (ADR-0034.R9), `for_demand_supply_line_id` on supply rows (ADR-0036.R9) and `owner_partner_id` on `demand_supply_line`, and `production_order_operation_id` on purchase lines (ADR-0037.R4, ADR-0037.R7), are assumed to exist for the simulation and the DDL drafts. The flag and its open question stay; dropping them later is a DDL change before step 3.
Source: ADR-0028.R2, ADR-0028.R2.N1

R828. The open delivery or receipt quantity of a stock line is stored once, in `demand_supply_line` (ADR-0024.R8). Posting interfaces write it in the referring document's transaction (ADR-0028.R3), and DS-22's delivery and receipt progress queries read it. Invoiced progress (which counts documents in `issuing`, ADR-0028.R9), fulfilled quantities (which `quantity_below_fulfilled` needs, ADR-0028.R3) and lines without a `demand_supply_line` row are computed from referring documents. ADR-0009.R7 is narrowed to match, and `INV-63` checks the stored open quantity.
Source: ADR-0031.R5

### Reservations, picks and staging

R829. `stock_reservation` keeps `picked_quantity` and `fulfilled_quantity` (ADR-0023.R13). Available to promise reads them under the `stock_value` lock for every reservation and pick release, so it must not join tasks and deliveries. `INV-58`: per demand line, the reservations' picked quantities equal the confirmed pick-task quantities, and their fulfilled quantities equal the posted delivery quantities for that line; production issues and backflush fulfil reservations too, so `INV-58` counts them (ADR-0034.R11).
Source: ADR-0031.R6

R830. Pick task creation (ADR-0023.R14) takes the `stock_value` lock of each item and warehouse (ADR-0027.R10, class 6) before reading available bin stock, so concurrent releases never allocate the same units. PAR-11 tests it.
Source: ADR-0030.R12

R831. `bin_type` gains `production` (ADR-0023.R2), which pick removal never reads. A work center's `supply_bin_id` and `output_bin_id` must be of that type (ADR-0033.R11); a work center without a supply bin stages to the production warehouse's default bin. `RunPickRelease` (ADR-0023.R14) also serves production orders: its pick tasks move reserved components to the reservation's `destination_bin_id`, released by `release_sequence`. Plain warehouses have no tasks, and issues take stock from the default bin. Staging moves quantity only (ADR-0023.R8).
Source: ADR-0034.R10

### Stock documents of commercial order lines

R832. Reversibility of `goods_receipt` and `delivery` follows ADR-0009.R19's flagged interim: reversible while unreferenced. Their flags are set by the DS-09 stock documents deliverable, and ADR-0020.R7 is aligned.
Source: ADR-0027.R13

R833. A `delivery` of sales order lines takes them from picks (ADR-0023.R16), or directly from order lines in a warehouse without warehouse tasks. Its quantity is at most the line's open quantity, `ordered − (delivered − returned)`, which `inventory` reads from the demand row it owns; more is rejected with `quantity_exceeds_open`. Over-delivery is not allowed in Phase 1 (flagged). It posts movement `sales_issue`, cost of goods sold at delivery; free goods lines use movement `free_goods_issue` (ADR-0047.R17). Pick release and delivery of a line whose demand row is on hold are rejected with `demand_on_hold` (ADR-0047.R18).
Source: ADR-0047.R5

R834. A `return_from_customer` is accepted against delivery lines of a closed order, within ADR-0047.R20's limits. It does not reopen the order: the quantity it frees is not deliverable, because a closed order takes no new deliveries, and a replacement is a new order. The work item `sales_return_due` (R837) still applies.
Source: ADR-0047.R5.N1

R835. `return_from_customer` (inventory) receives returned goods against delivery lines (`correction_of_id`: the delivery; ADR-0027.R7). `inventory` checks the quantity against the delivery line, which it owns: returned per delivery line ≤ delivered. The goods go to a `returns` bin as blocked (ADR-0023.R19). Their value follows the regime setting for `sales_return_receipt` (ADR-0020.R5).
Source: ADR-0047.R7

R836. `sales_return` is the posting correction of ADR-0009.R23: `correction_of_id` is the sales invoice, and its lines refer to the `return_from_customer` lines they credit. It posts `revenue_deduction_return` and output tax at the original line's price and tax data (ADR-0041.R8), and creates a `credit` item, which it may match to the invoice (ADR-0026.R9).
Source: ADR-0047.R7

R837. A `sales` consumer of the stock return's posted event compares, per order line, invoiced net with delivered net. When invoiced net is the larger, it raises a work item `sales_return_due` for the difference (ADR-0047.R20), and the `sales_return` closes it. Goods returned before invoicing need no `sales_return`: they reduce what remains to invoice.
Source: ADR-0047.R7

R838. A sales return line that names a return-from-customer line in the same unit and for the same entered quantity takes that line's inventory quantity, so invoiced net and delivered net move together and `sales_return_due` closes exactly (ADR-0056.R10).
Source: ADR-0047.R7.N1

R839. A `goods_receipt` of purchase order lines receives at most the line's open quantity, read from its supply row, with the tolerance applied to the ordered quantity: received net inventory quantity ≤ the order line's inventory quantity × (1 + `inventory.purchase_receipt_tolerance_percent` / 100) (company setting, default 0), so partial receipts do not each earn it again. More is rejected with `receipt_exceeds_order`.
Source: ADR-0047.R11, ADR-0047.R11.N2

R840. A `goods_receipt` posts movement `purchase_receipt` at the GR/IR value of ADR-0047.R13 and credits GR/IR with `purchase_order_line_id` (ADR-0030.R3).
Source: ADR-0047.R11

R841. A `return_to_supplier` is accepted against receipt lines of a closed order, within ADR-0047.R20's limits. It does not reopen the order: a closed line takes no replacement receipt (ADR-0047.R13's replacement receipt needs an open line), so a replacement is a new order. The GR/IR balance it leaves is cleared as ADR-0047.R13 says for lines closed short, and ADR-0047.R15's `supplier_credit_due` still applies.
Source: ADR-0047.R11.N1

### Opening stock

R842. Opening stock uses the stock document type `opening_balance` (ADR-0020.R7), stored as `opening_balance` and `opening_balance_line` (ADR-0075.R13). Each line carries item, warehouse, bin (the default bin where there are no bins, R812), stock status, handling unit, lot or serial, the unit block and quantity, and the spread `company_amount`. It posts only in the migration period (`migration_not_open`, `INV-870`). Processor locations are allowed (R816).
Source: ADR-0044.R9, ADR-0044.R9.N2

R843. The file gives one total value per item and valuation area. The handler spreads it over that item's lines by quantity, by largest remainder, so the lines sum exactly to the old books' value; a line without its total is rejected with `opening_unit_value_differs`. The total divided by the quantity becomes the first `preliminary_price`, with `price_source` `opening` (ADR-0020.R11; `INV-872`), so no costing run is needed in the migration period.
Source: ADR-0044.R9, ADR-0044.R9.N2

R844. Lots and serials of opening stock carry no cost of their own (ADR-0018; open question against spec 15). `INV-20` to `INV-24` hold. Opening stock lines carry the line unit block with the snapshot resolved at load; quantities with more decimals than their unit holds are rejected and listed with the unit's decimals (ADR-0056.R9, ADR-0056.R21).
Source: ADR-0044.R9, ADR-0044.R9.N1

### Production movement types and transaction keys

R845. The catalog `movement-types.csv` holds these production movement types (code: direction, value source, costing role, offset key):
- `production_issue`: out, `preliminary_price`, `production_input`, `production_consumption`;
- `production_return`: in, `preliminary_price`, `production_input`, `production_consumption`;
- `production_receipt`: in, `preliminary_price`, `production_output`, `production_output`;
- `co_product_receipt`: in, `preliminary_price`, `production_output`, `production_output`;
- `by_product_receipt`: in, `regime`, `production_output`, `production_output`;
- `disassembly_issue`: out, `preliminary_price`, `production_input`, `production_consumption`;
- `disassembly_receipt`: in, `preliminary_price`, `production_output`, `production_output`.
Source: ADR-0035.R19

R846. ADR-0020.R4 gains the costing roles `production_input` (into a cost-object node, revalued; a return counts negative) and `production_output` (from one, revalued unless its value is final).
Source: ADR-0035.R19

R847. The catalog `transaction-keys.csv` holds these production keys (key: accounts; determinants):
- `production_consumption`: `production_cost_material`; none;
- `production_output`: `inventory_work_in_process`; valuation class of the order's main output;
- `production_wip_transfer`: `inventory_work_in_process`; valuation class of the order's main output;
- `production_abnormal_cost`: `cost_of_goods_sold`; none;
- `production_unabsorbed_overhead`: `cost_of_goods_sold`; none;
- `production_residual_cost`: `cost_of_goods_sold`; none.
The leaf side of the transfer, the abnormal cost and allocations copy the source line's account. `consumption` also lists `production_cost_overhead`, for internal consumption to a factory cost center.
Source: ADR-0035.R19

R848. `production_abnormal_cost` and `production_unabsorbed_overhead` list `cost_of_goods_sold;expense_other` as regime alternatives (ADR-0053.R6); the account a package picks is flagged package content of the localization package.
Source: ADR-0035.R19.N1

R849. For a `disassembly` order the determinant of `production_output` and `production_wip_transfer` is the valuation class of the header item, the input being taken apart, because its outputs are co-product lines.
Source: ADR-0035.R19.N2

## Invariants

Statements are those of `invariants.csv`; this chunk holds the rows whose catalog source is a rule of this chunk.

| Invariant | Name | Check point | Statement | Protects |
| --- | --- | --- | --- | --- |
| `INV-48` | `material_line_posting_date` | day | Every `material_document_line.posting_date` equals the posting date of its posting document. | R819, R822 |
| `INV-58` | `reservation_quantities_match_execution` | day | Per demand line, the reservations' picked quantities equal the confirmed pick-task quantities, and their fulfilled quantities equal the posted delivery, production issue and backflush quantities for that line. | R829 |

Named by rules of this chunk, with their rows in other chunks: `INV-20`, `INV-21`, `INV-22`, `INV-24`, `INV-50`, `INV-51`, `INV-52`, `INV-54` (R807, R808, R844), `INV-56` (R815), `INV-63` (R828), `INV-870` (R842), `INV-872` (R843).

## Settings

None: no row of `settings.csv` belongs to the rules of this chunk.

`inventory.purchase_receipt_tolerance_percent` (company setting, default 0; R839) is named by ADR-0047.R11 and absent from `settings.csv`. The rules of this chunk also use the regime setting for `sales_return_receipt` (R835), whose rows stand with ADR-0020.R5.

Reads: `journal.manual_posting_to_control_accounts` (`ledger`; named by ADR-0039.R9, traced `ref:`), `production.reservation.mode` and `production.reservation.window_days` (`production`; named by ADR-0034.R9.N1, traced `ref:`).

## Conflicts

CONFLICT ADR-0030.R2: superseded in part by ADR-0030.R2.N1 under the author's late purchase cost decision (ADR-0021.R6.N2); the open and closed modes, the soft-locked treatment and the consumer_split range are gone; R804 and R805 state the receipt_addition in its own posting period and its dates.
CONFLICT ADR-0030.R2.N1: conflict-flagged note applied as the governing text of R804 and R805; it also answers the flagged status of rule 2, so the interim open question on soft-locked receipt periods is dropped.
CONFLICT ADR-0030.R1: the clause that the per-period split keeps the one-case check of ADR-0021 rule 6 from rejecting the invoice is dropped, since ADR-0021.R6.N2 removed that requirement; the split stays interim until DS-22, as ADR-0030.R2.N1 says (R801).
CONFLICT ADR-0030.D0: the seam table's split of price differences by receipt period and the closed mode for soft-locked receipt periods are superseded by ADR-0030.R2.N1 and ADR-0021.R6.N2; the current seam is R804.
CONFLICT ADR-0028.R2: "a line of the same table" for correction_of_line_id yields to ADR-0028.R2.N2 (another line table when the correction is another document type); the step 3 columns are stated as the DDL of DS-43-54 holds them, one column per source_kind, with no stock document line column (R825).
CONFLICT ADR-0047.R11: the receipt tolerance applies to the ordered quantity, not to each open quantity, as ADR-0047.R11.N2 says; R839 states the cumulative limit on received net inventory quantity.

## Trace

| Source | Where |
| --- | --- |
| ADR-0027.R13 | R832 |
| ADR-0027.R17 | ref: ADR-0027.R17 |
| ADR-0028.D0 | ref: ADR-0028.D0 |
| ADR-0028.D0.N1 | ref: ADR-0028.D0.N1 |
| ADR-0028.R2 | R823, R824, R825, R826, R827 |
| ADR-0028.R2.N1 | R827 |
| ADR-0028.R2.N2 | R823 |
| ADR-0028.R2.N3 | R825 |
| ADR-0028.R17 | ref: ADR-0028.R17 |
| ADR-0030.D0 | Landed cost from purchase invoices |
| ADR-0030.R1 | R801, R802, R803 |
| ADR-0030.R2 | R804, R805 |
| ADR-0030.R2.N1 | R801, R804, R805 |
| ADR-0030.R4 | ref: ADR-0030.R4 |
| ADR-0030.R4.N1 | ref: ADR-0030.R4.N1 |
| ADR-0030.R8 | R806, R807, R808, R809 |
| ADR-0030.R8.N1 | R810 |
| ADR-0030.R12 | R830 |
| ADR-0031.D0 | Bins and the default bin |
| ADR-0031.R1 | ref: ADR-0031.R1 |
| ADR-0031.R5 | R828 |
| ADR-0031.R6 | R829 |
| ADR-0031.R7 | R811 |
| ADR-0031.R8 | R812 |
| ADR-0031.R9 | R813 |
| ADR-0031.R10 | R814 |
| ADR-0031.R11 | R815 |
| ADR-0031.R12 | R819 |
| ADR-0031.R13 | R820 |
| ADR-0031.R14 | R821 |
| ADR-0031.R18 | R822 |
| ADR-0034.R9 | ref: ADR-0034.R9 |
| ADR-0034.R9.N1 | ref: ADR-0034.R9.N1 |
| ADR-0034.R10 | R831 |
| ADR-0034.R11.N2 | ref: ADR-0034.R11.N2 |
| ADR-0034.R12.N5 | ref: ADR-0034.R12.N5 |
| ADR-0034.R19 | ref: ADR-0034.R19 |
| ADR-0035.R14 | ref: ADR-0035.R14 |
| ADR-0035.R14.N1 | ref: ADR-0035.R14.N1 |
| ADR-0035.R14.N2 | ref: ADR-0035.R14.N2 |
| ADR-0035.R14.N3 | ref: ADR-0035.R14.N3 |
| ADR-0035.R14.N4 | ref: ADR-0035.R14.N4 |
| ADR-0035.R14.N5 | ref: ADR-0035.R14.N5 |
| ADR-0035.R19 | R845, R846, R847 |
| ADR-0035.R19.N1 | R848 |
| ADR-0035.R19.N2 | R849 |
| ADR-0036.R9 | ref: ADR-0036.R9 |
| ADR-0036.R9.N1 | ref: ADR-0036.R9.N1 |
| ADR-0037.R1 | R816, R817, R818 |
| ADR-0037.R5 | ref: ADR-0037.R5 |
| ADR-0037.R5.N1 | ref: ADR-0037.R5.N1 |
| ADR-0037.R7 | ref: ADR-0037.R7 |
| ADR-0039.R9 | ref: ADR-0039.R9 |
| ADR-0039.R9.N1 | ref: ADR-0039.R9.N1 |
| ADR-0039.R11 | ref: ADR-0039.R11 |
| ADR-0039.R11.N1 | ref: ADR-0039.R11.N1 |
| ADR-0044.R7 | ref: ADR-0044.R7 |
| ADR-0044.R7.N1 | ref: ADR-0044.R7.N1 |
| ADR-0044.R9 | R842, R843, R844 |
| ADR-0044.R9.N1 | R844 |
| ADR-0044.R9.N2 | R842, R843 |
| ADR-0045.R1 | ref: ADR-0045.R1 |
| ADR-0045.R1.N1 | ref: ADR-0045.R1.N1 |
| ADR-0046.R14 | ref: ADR-0046.R14 |
| ADR-0046.R14.N1 | ref: ADR-0046.R14.N1 |
| ADR-0046.R14.N2 | ref: ADR-0046.R14.N2 |
| ADR-0046.R14.N3 | ref: ADR-0046.R14.N3 |
| ADR-0046.R14.N4 | ref: ADR-0046.R14.N4 |
| ADR-0046.R14.N5 | ref: ADR-0046.R14.N5 |
| ADR-0047.R1 | ref: ADR-0047.R1 |
| ADR-0047.R1.N1 | ref: ADR-0047.R1.N1 |
| ADR-0047.R1.N2 | ref: ADR-0047.R1.N2 |
| ADR-0047.R1.N3 | ref: ADR-0047.R1.N3 |
| ADR-0047.R1.N4 | ref: ADR-0047.R1.N4 |
| ADR-0047.R3 | ref: ADR-0047.R3 |
| ADR-0047.R3.N1 | ref: ADR-0047.R3.N1 |
| ADR-0047.R3.N2 | ref: ADR-0047.R3.N2 |
| ADR-0047.R5 | R833 |
| ADR-0047.R5.N1 | R834 |
| ADR-0047.R7 | R835, R836, R837 |
| ADR-0047.R7.N1 | R838 |
| ADR-0047.R8 | ref: ADR-0047.R8 |
| ADR-0047.R8.N1 | ref: ADR-0047.R8.N1 |
| ADR-0047.R8.N2 | ref: ADR-0047.R8.N2 |
| ADR-0047.R11 | R839, R840 |
| ADR-0047.R11.N1 | R841 |
| ADR-0047.R11.N2 | R839 |
