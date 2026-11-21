Module: inventory    Chunk: 3 of 7    Source ADRs: ADR-0021, ADR-0023
Build step(s): 0, 3, 5    Generated from index: 30d5706    Compiled by: Claude Opus 5.5, 2026-11-21

# Compiled spec: `inventory`, chunk 3

## Purpose

`inventory` owns material documents, stock, costing, landed cost and the warehouse management tables (ADR-0022.R2); it
sits in layer 3. This chunk states late landed costs and the removed closed-period method, landed cost corrections and
reversals, customs declarations, the GR/IR link and delivery costs, the clearing invariants, and the base of warehouse
management: scope, warehouses, zones and bins, the stock key, negative stock at bin level, handling units, movements
with bins, warehouse movements, reversal with bins and the lock order. The module layering of ADR-0022 belongs to
`process` and the product inspection points to `master_data`; those units are traced `ref:`.

## Entities and tables

DDL: `docs/design/DS-20-master-data.sql` (`zone`, `bin`) and `docs/design/DS-22-09-42-commercial-inventory.sql` (the others).

| Table | Meaning | Key | Parent | Owner |
| --- | --- | --- | --- | --- |
| `zone` | A group of bins in one warehouse (R439) | `id`; unique (`warehouse_id`, `code`) | `warehouse` | `inventory` |
| `bin` | A storage place in a warehouse, with type, capacity and blocks (R439-R441) | `id`; unique (`warehouse_id`, `code`) and (`company_id`, `barcode`) | `zone`, `warehouse` | `inventory` |
| `handling_unit` | A pallet, carton or tote with its content (R447-R451) | `id`; unique (`company_id`, `code`) and (`company_id`, `barcode`) | `handling_unit_type`, `bin` | `inventory` |
| `warehouse_movement` | Append-only quantity move between bins, statuses and handling units inside one warehouse (R456, R457) | `id` | `warehouse`, `warehouse_task` | `inventory` |
| `pending_receipt_adjustment` | Invoice first: the stock-bound price difference of an invoice line for quantities not yet received, with `total_company_amount`, `quantity_to_receive` and `amount_to_apply`, waiting until the receipt (R417) | `id`; unique `purchase_invoice_line_id` | `purchase_order_line`, `purchase_invoice_line` | `inventory` |

Defined by rule, without DDL: `customs_declaration` and `customs_declaration_tax` (R408-R410).

Named by this chunk, with rows in other chunks: `stock_quantity` (R443), `stock_value` (R407, R444, R459),
`warehouse_task` (R456, R459), `material_document_line` (R452), the landed cost tables of ADR-0021.R1, and the stock
document tables `goods_receipt`, `other_receipt`, `other_receipt_line`, `other_issue`, `other_issue_line`,
`opening_balance`, `opening_balance_line`, `scrap`, `internal_consumption` and `return_to_supplier_line` (R453, R454).

Reads: `warehouse` (`is_bin_managed`, `outbound_flow`, `default_bin_id`, `default_receiving_bin_id`,
`default_shipping_bin_id`, `is_handling_unit_managed`), `product` (`hs_code`, `country_of_origin`, `inspection_points`),
`item`, `handling_unit_type`, `barcode`, `journal_line`, `purchase_order_line`, `purchase_invoice_line`, tax codes.

## Commands and queries

Commands and queries named by this chunk, with their rows in other chunks: `UpdateWarehouse` (R436; chunk 5),
`PackHandlingUnit` and `UnpackHandlingUnit` (R447, R448, R456; chunk 4), `GetStockBalance` at bin level (R446; chunk 4)
and `ListExpectedLandedCost` (R425; chunk 7).

Not registered commands: the contract function `inventory.contract.adjust_receipt_value` (R416, R417); the daily job
`RunRetiredSsccCleanup` (R451). The correction types `landed_cost_correction` (R404) and
`customs_declaration_amendment` (R414) post by their `Post` command, registered like other correction types; document
types `landed_cost` (area `purchasing`, module `inventory`) and `customs_declaration` (area `purchasing`, module
`purchasing`) in `authorization-areas.csv`.

Codes raised by the rules of this chunk: `negative_stock_value` (R405, R407), `document_referenced` (R406),
`bin_not_empty` (R441), `barcode_taken` and `barcode_retired` (R440), `negative_stock`, `invalid_state_transition`
and `stock_reserved` (R458), `handling_unit_mismatch` (R460); check result `customs_assessment_differs` (R410).

## Rules

### Late landed cost and the removed closed-period method

R401. There is no closed mode and no method `consumer_split`. A late purchase cost (landed cost) is booked in the period of the cost document's own posting date, which must be a period that is not locked, whatever the state of the target receipt's period (ADR-0021.R6, rule 6 note of 2026-11-21). Each target's allocated amount posts as a value-only `receipt_addition` line on the target's item and warehouse in that posting period, so the value enters stock and takes part in the actual cost (average) of the recording period. No locked period is recomputed or rerun, nothing is allocated retroactively to past consumers (sales, consumption, scrap, other issues, count shortages, transfers, production), and no consumer line is written.
Source: ADR-0021.R7, ADR-0021.R7.N1

R402. No regime setting chooses a closed-period method: `landed_cost.closed_period_method` and its options `consumer_split` and `stock_coverage` do not exist, and no core catalog holds the setting (`settings.csv` has no row). The `receipt_addition` of the posting period gives the result SAP gives under actual costing (`periodic_average`, ADR-0020.R11): the late cost is a receipt difference of the posting period, spread by that period's costing over its consumption and ending stock. An area with no quantity left goes to the residual of ADR-0020 rule 13.
Source: ADR-0021.R8, ADR-0021.R8.N1

R403. The `l10n_vn` package's seed of the removed setting (DS-19 `regimes/tt99/settings.yaml`; ADR-0039.R9) goes in the package's rework. Whether the regime's accounting standard accepts the core mechanism for a cost of a closed period is not decided by the core: it stays open with the `l10n_vn` package work (DS-11 entry on landed cost of a closed period, deferred; DS-19).
Source: ADR-0021.R8, ADR-0021.R8.N1

### Landed cost corrections and reversals

R404. A landed cost is corrected by the correction type `landed_cost_correction` (`correction_of_id`, ADR-0009.R23; its `Post` command is registered like other correction types, ADR-0008.R1). It holds signed differences per cost line and target, and follows the same period rules as a landed cost (ADR-0021.R6).
Source: ADR-0021.R9

R405. `landed_cost` is an internal document that may be reversed (ADR-0009 rules 18–20): `is_reversible` is true, with the extra precondition that no `stock_value` it touched becomes negative (`negative_stock_value`).
Source: ADR-0021.R9, ADR-0021.R9.N1

R406. A landed cost targeting a receipt refers to it, so the receipt cannot be reversed while the landed cost stands (`document_referenced`, ADR-0009.R19).
Source: ADR-0021.R9

R407. A value-only inventory line that would make a warehouse's `stock_value` negative is rejected with `negative_stock_value`; values left at zero quantity are handled by costing (ADR-0020 rule 13).
Source: ADR-0021.R9

### Customs declarations

R408. A `customs_declaration` posts what customs assessed for an import. Header: declaration number and date, supplier, the purchase orders or receipts it covers; `transaction_currency` is the currency customs assesses in. Journal conversion follows ADR-0011.
Source: ADR-0021.R10

R409. A declaration line holds item, quantity, unit; `hs_code`; `country_of_origin` (ISO 3166-1 alpha-2); the customs value in the declared currency, and the customs exchange rate. The customs rate is document rate type `customs` (ADR-0011.R12) and converts customs value only to compute tax bases, never a journal amount.
Source: ADR-0021.R10

R410. Each line has rows in `customs_declaration_tax` (tax code, base, assessed amount, recomputed amount). Import duty, excise, environmental protection tax, anti-dumping or safeguard duty and import VAT are all tax codes (DS-23), not fixed columns. Amounts are recorded as assessed. The core recomputes them from the tax codes and reports differences as the check result `customs_assessment_differs`, never changing the assessed amount.
Source: ADR-0021.R10

R411. Posting a customs declaration credits each tax's payable account through its tax code's key (`import_export_duty`, `special_consumption_tax`, `import_tax`; DS-23 adds keys for other import taxes). It debits `purchase_cost_clearing` when the tax code's `import_treatment` is `capitalize`, or the recoverable tax account through `input_tax` when it is `recoverable`; that account is flagged content of the localization package. Import tax codes and the tax rows written at posting: ADR-0041 rules 1, 11.
Source: ADR-0021.R11

R412. `import_treatment`, including when import VAT is not deductible and is capitalized, is a package rule with a basis, flagged until verified (open question; DS-19, DS-23).
Source: ADR-0021.R11

R413. The declaration proposes a `landed_cost` with one cost line per declaration line and capitalized tax. Each cost line targets only receipt lines of that item, prorated by received over declared quantity, less what is already allocated.
Source: ADR-0021.R11

R414. A customs amendment is the correction type `customs_declaration_amendment` (`correction_of_id`), posting differences. `customs_declaration` is not reversible, deliberately stricter than ADR-0009 rule 19's interim: it records an outside party's document, and the amendment type corrects it.
Source: ADR-0021.R11

### GR/IR link and price differences

R415. A goods receipt credits `gr_ir_clearing`, and the goods invoice debits it; GR/IR carries the order price (ADR-0030 rules 1, 2, 4). Landed costs never pass through GR/IR. A supplier's freight, insurance or handling invoice posts its cost to `purchase_cost_clearing` (DS-22) when the option `landed_cost.unplanned_cost_treatment` is `distribute_to_items`, and to the account of `separate_account`, never stock, when it is `separate_account` (R421).
Source: ADR-0021.R12

R416. Invoice-versus-receipt differences (with receipts at the order price, invoice versus order; ADR-0030.R4) keep one mechanism, the regime's determination of the `price_difference` key (ADR-0015.R4). When it determines a price difference account, the invoice posts there. When it determines an `inventory` account, the invoice posts the difference to `purchase_cost_clearing` instead, and calls `inventory.contract.adjust_receipt_value`, which writes `landed_cost` documents with `cost_type` `price_difference` targeting the matched receipt lines in the invoice's transaction, so nothing waits in clearing for a person.
Source: ADR-0021.R12

R417. A price difference sent to stock for a receipt of an earlier period is a late purchase cost: it goes to stock as a `receipt_addition` in the posting period of the document `inventory.contract.adjust_receipt_value` writes, whatever the state of the receipt's period; that document's posting date follows ADR-0030.R2.N1 (R805), and no locked period is recomputed. Differences for goods not yet received wait in `pending_receipt_adjustment`. Interim (chief architect's translation of the author's decision of 2026-11-21, until the step that builds it).
Source: ADR-0021.R12, ADR-0021.R12.N1

R418. The exchange-rate difference between goods receipt and invoice is designed as SAP does (ADR-0047.R13 note). For a stock item it goes to stock as a `receipt_addition` in the posting period in the same way, with `cost_type` `exchange_rate_difference` (ADR-0021.R1; ADR-0020.R12 note). Interim, until the step that builds it.
Source: ADR-0021.R12.N1

R419. Which TT99 account holds GR/IR clearing and which rate values an import receipt are open questions, read as regime settings by DS-22.
Source: ADR-0021.R12

### Delivery costs

R420. Planned delivery costs are conditions on the purchase order line, accrued at goods receipt into the receipt's stock value against a delivery-cost clearing key and cleared by the freight supplier's invoice; a difference is a price difference handled like the purchase price difference (ADR-0047.R13 note; interim, built at step 5). The accrual is part of the receipt's document value, so it is no `landed_cost`; only the invoice's difference sent to stock is one.
Source: ADR-0021.R12.N2

R421. Unplanned delivery costs are the `landed_cost` path: a supplier's cost invoice line with no planned condition (`line_kind` `landed_cost`). The setting `landed_cost.unplanned_cost_treatment` (area `inventory`, regime and company option, core default `distribute_to_items`, changed only from a period start, in the shape of ADR-0063.R24) chooses:
- `distribute_to_items`: the cost posts to `purchase_cost_clearing` and is allocated to receipt lines by ADR-0021 rules 4 to 6;
- `separate_account`: the line posts to its own account and never reaches stock or an allocation, as SAP's separate account debits no stock and no account assignment.
Source: ADR-0021.R12.N2

R422. Interim until step 5: the `separate_account` line is determined by the existing key `purchase_expense` (by item group, or the entered account), so no new transaction key is needed. SAP's third choice, distributing together with the planned delivery costs, is not offered. `separate_account` expenses a purchase cost, an accounting policy, so a regime package that opens it records it as a flagged value. Customs declarations (`import_treatment`) and price differences sent to stock are not unplanned delivery costs and are not affected.
Source: ADR-0021.R12.N2

### Product customs data

R423. Products get `hs_code` and `country_of_origin` (ADR-0018). They are proposed on declaration lines. The code's length and format are country data. `hs` (Harmonized System) is in the allowed abbreviations.
Source: ADR-0021.R13

### Clearing invariants and close

R424. The DS-16 invariants of landed cost (`INV-26`, `INV-27`): allocations sum to each cost line; no source is allocated beyond its amount; per source line, the `purchase_cost_clearing` balance equals its unallocated rest.
Source: ADR-0021.R14

R425. A close task (ADR-0012) lists sources still unallocated at period end. Next to them it shows `ListExpectedLandedCost`: goods receipts whose purchase Incoterm leaves main carriage or insurance to the buyer and that have no `freight` or `insurance` cost line, as information that blocks nothing (ADR-0068).
Source: ADR-0021.R14, ADR-0021.R14.N2

R426. `purchase_cost_clearing` is a liability in the system chart but carries a debit while costs wait. DS-26 defines the report format and DS-19's report definitions place the lines of the regime's clearing account (ADR-0049.R22); the account number and its placement (under other payables, a debit balance under other receivables) are flagged content of the localization package (interim, ADR-0039.R8).
Source: ADR-0021.R14, ADR-0021.R14.N1

### Landed cost edge cases and open questions

R427. DS-17 holds the landed cost edge cases: landed cost after partial sale and after period close; one declaration covering several receipts; customs assessed before the goods receipt. A landed cost after period close follows R401: it posts in the period of its own posting date as a value-only `receipt_addition`, and the closed period is not recomputed (`EC-12`).
Source: ADR-0021.R15

R428. The open question of landed cost left for the author is import tax treatment and non-deductible import VAT (R412). The earlier-unlocked case and the closed-period method are answered by the decision on late purchase costs (R401); the value of a purchase return after allocation follows `movement_type.purchase_return.include_landed_cost` (ADR-0021.R3.N1); reversibility is answered (R405).
Source: ADR-0021.R16, ADR-0021.R16.N1

### Warehouse management: model and scope

R429. Two levels change one stock table, `stock_quantity`, whose key holds bin, stock status and handling unit, so they cannot drift apart:
- inventory level, what the books see: material documents (ADR-0020) move quantity and value per item, warehouse, lot or serial and status;
- warehouse level, where the goods physically are: warehouse movements move quantity between bins, statuses and handling units inside one warehouse, carry no value and post no journal.
Source: ADR-0023.D0

R430. Each level keeps its own rule for time: the books check stock per (item, warehouse, lot or serial) at the end of every date from the posting date on (ADR-0020.R10); physical places are checked on their current balance only, because where goods are is a fact of now.
Source: ADR-0023.D0

R431. Execution is data-driven and deterministic:
- putaway and removal strategies are rule tables;
- tasks are written by code in the same transaction as the document that causes them;
- every scan is an ordinary command with an idempotency key;
- agents propose rule changes, count plans and exception resolutions as drafts, and code executes them (Principles 2, 12);
- exceptions become work items (Principle 8); routine tasks stay in their own high-volume table.
Source: ADR-0023.D0

R432. A warehouse without bins keeps working as in ADR-0020. A warehouse with bins chooses its flow: direct (receive to a shelf, pick straight into the goods issue) or staged (receiving bin, putaway, staging, packing). A small shop and a managed distribution warehouse run on the same model.
Source: ADR-0023.D0

R433. Phase 1 holds the full warehouse feature list, with no cut (ADR-0032):
- core at step 3: bins and zones, stock statuses, handling units (one nesting level), putaway (`fixed_bin`, `nearest_free`), reservations and available to promise, removal by FEFO or FIFO, counts by bin, returns disposition, transfers with bins;
- pick release from demand lines at step 3;
- documents at step 5: partial deliveries from confirmed picks, packing, printing of labels and lists;
- a second slice after the first is proven: pick batches and waves, the replenishment job, cycle-count plans, the `consolidate` and `empty_bin` putaway methods, and the `staged` flow with `staging` and `packing` bins.
Source: ADR-0023.D0, ADR-0023.H.N1

R434. Later: slotting optimization by an agent; cross-docking; dock and yard appointments; labor management; value-added services and kitting (Phase 2; kits as bills of materials are Phase 1 in DS-51, ADR-0032); SSCC labels with carrier integration; deeper nesting of handling units.
Source: ADR-0023.D0

### Warehouses, zones and bins

R435. A warehouse (ADR-0020.R1) gets `is_bin_managed` (default false); for bin-managed warehouses `outbound_flow` (`direct`; `staged` in the second slice), `default_receiving_bin_id` and `default_shipping_bin_id`; and `is_handling_unit_managed`.
Source: ADR-0023.R1

R436. Every warehouse, of every kind, has a default zone and a default bin, named by `warehouse.default_bin_id` (ADR-0031.R7). Only `physical` warehouses manage bins. `UpdateWarehouse` (`human_only`) may set `is_bin_managed: true` on a physical warehouse, with the `default_receiving_bin_id` and `default_shipping_bin_id` of R435. The reverse is not supported. There is no `ConvertWarehouse` command (ADR-0031.R9).
Source: ADR-0023.R1

R437. In `transit` and `goods_sent` warehouses stock rows and handling units use the default bin, never a null one (ADR-0031.R8); handling units travel with their content, and stock there is always `available`.
Source: ADR-0023.R1

R438. Features per warehouse mode:
- plain and bin-managed warehouses: stock status and inspection (`inspection_points`, ADR-0023.R3.N1); reservations; `status_change` and `count` tasks (in plain warehouses count tasks cover items and `status_change` uses the default bin); handling units;
- bin-managed warehouses only: bins, putaway and removal strategies, and putaway, pick, move and replenishment tasks.
Source: ADR-0023.R1

R439. A `zone` (`warehouse_id`, `code`, `name`) groups bins. A `bin` holds:
- `warehouse_id` and `zone_id`: where it is;
- `code`: unique in the warehouse; its segments are informational;
- `barcode`: unique in the company, so a scan resolves without the warehouse; default: the code;
- `bin_type`: `receiving`, `storage`, `picking`, `shipping`, `quality`, `returns`, `damage`, `production` (work-center supply and output bins, never read by pick removal, ADR-0034.R10); `staging` and `packing` come with the second slice and are not in the DDL check;
- `pick_sequence`;
- capacity: optional `maximum_weight` (kg, gross), `maximum_volume` (m³), `maximum_handling_units`;
- booleans `is_mixed_item_allowed`, `is_mixed_lot_allowed`, `is_blocked_for_putaway`, `is_blocked_for_picking` (manual blocks only), `is_active`.
Source: ADR-0023.R2

R440. The bin barcode is an internal code in normalized (upper-case) form, registered in the company's barcode registry: unique across bins, item units, handling units, lots, serials and barcoded documents, so a bin code equal to an item barcode is refused (`barcode_taken`). The default "the code" applies when the code fits the internal code format; an old system's numeric label may be kept as a legacy code (`is_legacy_barcode`). A changed barcode stays reserved: an old label resolves to `barcode_retired`, and the bin may take its old code back (ADR-0061 rules 7, 8).
Source: ADR-0023.R2.N1

R441. Bins are created and changed in batches (ADR-0008). A bin with stock cannot be deactivated (`bin_not_empty`). The default bin has code `DEFAULT` and barcode `<warehouse code>-DEFAULT`, and cannot be deactivated while the warehouse is not bin-managed (ADR-0031.R7).
Source: ADR-0023.R2

R442. The recommended model is one physical warehouse per site, with zones and bins for raw materials, the production floor, finished goods and quality. Split into several warehouses only when they need separate keepers, stock reports or accounts. The setup agent proposes this, and nothing enforces it (ADR-0068).
Source: ADR-0023.R2.N2

### Stock key and negative stock

R443. The key of `stock_quantity` is (company, item, warehouse, bin, lot or serial, `stock_status`, `handling_unit_id`), plus the reserved `owner_partner_id` (ADR-0030.R8). Every row has a bin of its own warehouse: the default bin outside bin-managed warehouses (ADR-0031.R8).
Source: ADR-0023.R4

R444. `stock_status` is a classification, not a lifecycle state: `available`, `quality_inspection` or `blocked`. Statuses, bins and handling units carry no value: `stock_value` stays per (item, warehouse), and inventory accounts are unchanged (ADR-0020.R8). This status axis replaces the "stock types" option that ADR-0020 rejected; queries group by (item, warehouse) unless they ask for more.
Source: ADR-0023.R4

R445. Whether a regime wants quality or blocked stock presented apart is an open question; none is known for TT99.
Source: ADR-0023.R4

R446. Negative stock with bins:
- the dated end-of-day check of ADR-0020.R10 stays at (item, warehouse, lot or serial), summed over bins, statuses and handling units, and uses the algorithm of ADR-0031.R14; it is decided law, not an open question (ADR-0020.R10.N1);
- every full key is checked on its current balance only: no bin, status or handling unit goes below zero now;
- a backdated document names where the goods are now, and its dated check still runs at the inventory level;
- bin-level `GetStockBalance` has no `as_of`.
Source: ADR-0023.R5

### Handling units

R447. A `handling_unit` holds `code` and `barcode` (unique in the company), `handling_unit_type_id` (company data: pallet, carton or tote, with tare weight and dimensions), `parent_handling_unit_id` (one level in Phase 1: a carton on a pallet), `warehouse_id`, `bin_id` (the default bin in `transit` and `goods_sent`) and `state`: `open` (content may change), `closed` (content changes only by `UnpackHandlingUnit`) or `shipped` (set by the goods issue).
Source: ADR-0023.R6

R448. Handling unit behavior:
- the unit's row is authoritative for an empty unit; for a unit with content, the unit, its stock rows and its children are in one bin (DS-16);
- scanning a unit moves all its content in one task;
- a partial pick from a unit takes the quantity out into no unit or into a new one;
- content may mix statuses;
- a returned unit is received as a new unit;
- `PackHandlingUnit` and `UnpackHandlingUnit` are warehouse movements.
Source: ADR-0023.R6

R449. Handling unit types stay physical containers, unrelated to product units in Phase 1; a quantity per handling unit type and packaging dimensions come after Phase 1 (ADR-0056 rule 15).
Source: ADR-0023.R6.N1

R450. A handling unit's barcode is an SSCC (18 digits, valid check digit) or an internal code (default prefix `HU-`), registered in the barcode registry. A receipt scan of a supplier's (00) gives a new handling unit that SSCC in a handling-unit-managed warehouse.
Source: ADR-0023.R6.N2

R451. A supplier's retired SSCC is deleted by the daily job `RunRetiredSsccCleanup` once `barcode.sscc_reuse_months` have passed (a company setting, default 12, unverified), so the pallet may come back. An SSCC under the company's own prefixes, active or not, needs a person; NativeFlows never reissues one, and SSCC assignment comes after Phase 1 (ADR-0061 rules 7, 17, 25).
Source: ADR-0023.R6.N2

### Inventory-level movements with bins

R452. Inventory-level movements are material documents (ADR-0020), with `bin_id`, `stock_status` and `handling_unit_id` filled in on their lines where managed (the production types: ADR-0034 rules 11 and 13).
Source: ADR-0023.R7

R453. Bin, status and task per movement type:
- `purchase_receipt`, `other_receipt` (`other_receipt_line`): the line's bin, or the default receiving bin; `quality_inspection` when the product's `inspection_points` contains `goods_receipt`, else `available`; a putaway task, unless the line names a `storage` or `picking` bin;
- `sales_return_receipt`: a `returns` bin; `blocked`; disposition (ADR-0023 rule 19), then putaway if restocked;
- `opening_balance` (`opening_balance_line`): the line's bin, the final bin named in the import (DS-21); any status; no task;
- `sales_issue`, `transfer_out`: the non-pickable bin the confirmed picks moved the goods to: the default shipping bin (direct flow) or a `staging` or `shipping` bin (staged flow), in a plain warehouse its default bin; `available`; pick tasks precede it in bin-managed warehouses (ADR-0023 rules 14–15);
- `purchase_return`, `scrap`, `other_issue` (`other_issue_line`), `internal_consumption`: the line's bin; any status (rejected goods are mostly `blocked`); no task;
- `transfer_in`: the default receiving bin; `available`; putaway;
- `stock_count_shortage`, `stock_count_surplus`: the counted bin; the counted status; no task.
Source: ADR-0023.R7, ADR-0023.R7.N1, ADR-0023.R7.N3

R454. Issuing documents name the status they issue from: `return_to_supplier_line` has `stock_status`, and `scrap` and `internal_consumption` lines carry the status they leave (ADR-0070 rules 2, 15; ADR-0075 rules 4, 5).
Source: ADR-0023.R7.N1, ADR-0023.R7.N2

R455. A transfer moves `available` stock only, so a transfer line has no status. It is one document (`direct`: a source bin on `transfer_out` and a receiving bin on `transfer_in`) or two through a `transit` warehouse (`dispatch`, `receive`), the handling unit keeping its identity (ADR-0075 rules 1, 2). Dispatch to a customer may be a `sales_issue`, or a `transfer_out` to a `goods_sent` warehouse (ADR-0020.R4).
Source: ADR-0023.R7, ADR-0023.R7.N2

### Warehouse movements

R456. `warehouse_movement` lines are written by confirmed tasks and by the pack, unpack and count-correction commands. Each line holds, inside one warehouse: item, lot or serial, a positive quantity in the inventory unit, `from_bin_id` and `to_bin_id`, `from_stock_status` and `to_stock_status`, `from_handling_unit_id` and `to_handling_unit_id`, `business_date` (`clock.today`, for history only), its source as exactly one of `warehouse_task_id` and `source_command` (`pack`, `unpack`, `count_correction`), and the reserved `owner_partner_id` (ADR-0030.R8).
Source: ADR-0023.R8

R457. Warehouse movements are append-only and post no journal. Per (item, warehouse, lot or serial) their quantities net to zero (DS-16, `INV-50`). `stock_quantity` per full key equals material lines plus warehouse movements (`INV-51`); both are written through the stock lock helper. Warehouse movements are stock movements in a plan (ADR-0008.R12).
Source: ADR-0023.R8

### Reversal with bins

R458. Reversal of a material document with bins (ADR-0020.R7; ADR-0009.R18):
- it posts to the original lines' bins, statuses and handling units, and is refused with `negative_stock` when the stock is no longer there; the error's fix says to move it back with a move task first;
- it cancels the original's open tasks in the same transaction;
- it is refused with `invalid_state_transition` while a task of the original is `in_progress`;
- a reversal that takes stock out counts as a voluntary issue for `stock_reserved` (ADR-0023 rule 13).
Source: ADR-0023.R9

### Locks

R459. The lock order of warehouse commands is the complete order of ADR-0027.R10 (documents, period area state rows, warehouse task rows, handling unit rows parent first, `stock_value` rows, `stock_quantity` rows, bin rows for capacity, mix and count checks, then the later classes). Reservation writes take the `stock_value` row like postings, so reservations are serialized with the stock they hold; the cost is that moves of one item in one warehouse are serialized.
Source: ADR-0023.R10, ADR-0027.R10

R460. PAR tests of warehouse locking (DS-16): PAR-06, two putaways of different items into the last free bin: the second putaway proposal is computed under the bin lock and goes to another bin or none; PAR-07, a handling-unit move against a pick from that unit: one command succeeds and the other fails with `handling_unit_mismatch`; PAR-08, two confirmations of one task: exactly one writes movements and the other is a replay or `invalid_state_transition`; PAR-09 (long profile), 8 concurrent confirmations of one item in different bins, where a p95 above 1 s triggers the revisit line.
Source: ADR-0023.R10, ADR-0027.R10

## Invariants

Statements are those of `invariants.csv`; each row stands once in the module, in the chunk of the rule its catalog source names.

| Invariant | Name | Check point | Statement | Protects |
| --- | --- | --- | --- | --- |
| `INV-50` | `warehouse_movements_net_zero` | day | Warehouse movements net to zero per item, warehouse and lot or serial. | R457 |
| `INV-51` | `stock_rows_equal_movements` | day | `stock_quantity` per full key equals its material lines plus warehouse movements. | R457 |
| `INV-52` | `no_negative_current_stock` | day | No current `stock_quantity` per full key is negative. | R446 |
| `INV-56` | `bins_match_warehouse_mode` | day | Every stock row has a bin of its own warehouse, and a warehouse that is not bin-managed has exactly one bin, its `default_bin_id`. | R436, R443; ADR-0031.R11 |

Named by rules of this chunk, with rows in chunk 2 (catalog source ADR-0021 rules 5 and 2): `INV-26`, `INV-27` (R424).

## Edge cases

| Edge case | Name | Case | Outcome | Protects |
| --- | --- | --- | --- | --- |
| `EC-13` | `import_customs_rate` | A USD import whose customs rate differs from the book rate, with import duty. | `must_succeed` | R409, R410; ADR-0011.R12 |

The landed cost edge cases of R427 (`EC-11`, `EC-12`, `EC-29`, `EC-30`) stand in the chunks of the rules their catalog source names.

## Settings

| Key | Value type | Scopes | Core default | Used by |
| --- | --- | --- | --- | --- |
| `landed_cost.unplanned_cost_treatment` | enum: `distribute_to_items`, `separate_account`; leaf `regime_option`, changed only from a period start | `regime`, `company` | `distribute_to_items` | R421, R422 |

`barcode.sscc_reuse_months` (R451; company setting, default 12, unverified) has no row in `settings.csv`.
`landed_cost.closed_period_method` is not a setting (R402).

## UI annotations

None: the sources hold no ADR-0077 annotation for this chunk's units.

## Conflicts

CONFLICT ADR-0021.R7: closed mode and the consumer split over locked periods are superseded; R401 states the late-cost law of ADR-0021.R7.N1 and ADR-0021.R6.N2 (posting period of the cost document, receipt addition, no recomputation).
CONFLICT ADR-0021.R7.N1: this note governs; rule 7's closed mode is no longer used and R401 states the posting of ADR-0021.R6.N2 instead.
CONFLICT ADR-0021.R8: the regime setting landed_cost.closed_period_method with consumer_split and stock_coverage is removed by ADR-0021.R8.N1; R402 and R403 state what remains.
CONFLICT ADR-0021.R8.N1: governing note of the author's late purchase cost decision; the closed-period setting and both options are removed, stated in R402 and R403.
CONFLICT ADR-0021.R9: the interim, flagged reversibility of landed cost is confirmed by ADR-0021.R9.N1; R405 drops the interim mark.
CONFLICT ADR-0021.R12: late price differences sent to stock post as a receipt addition in the document's posting period whatever the receipt period's state (ADR-0021.R12.N1, R417, R418), replacing the closed treatment; unplanned delivery costs gain the company option of ADR-0021.R12.N2 (R421).
CONFLICT ADR-0021.R16: the earlier-unlocked case and the closed-period method are answered by ADR-0021.R16.N1, the purchase return value by ADR-0021.R3.N1 and reversibility by ADR-0021.R9.N1; R428 keeps only the import tax question open.
CONFLICT ADR-0023.D0: the feature list proposed pending the author's confirmation is confirmed by ADR-0023.H.N1 (full list kept in Phase 1, no cut); R433 states it as decided.
CONFLICT ADR-0023.R1: plain warehouses without bins, null bins in transit warehouses and ConvertWarehouse are superseded by ADR-0031.R7, ADR-0031.R8 and ADR-0031.R9; R436 and R437 state the default bin law.
CONFLICT ADR-0023.R4: the bin bullet saying rows outside bin-managed warehouses have no bin is superseded by ADR-0031.R8; R443 states that every row has a bin.
CONFLICT ADR-0023.R5: the negative-stock open question named here is answered by ADR-0020.R10.N1, which makes the dated check law; R446 drops the open question.
CONFLICT ADR-0023.R7: the inspection requirement becomes inspection points and transfers carry available stock without status (ADR-0023.R7.N1, ADR-0023.R7.N2, ADR-0023.R7.N3); R453 to R455 state the result.
CONFLICT ADR-0023.R10: its lock list is superseded by the complete order of ADR-0027.R10, which R459 cites; the reservation and PAR test clauses still hold.

## Proposed (not law)

None

## Trace

| Source | Where |
| --- | --- |
| ADR-0021.R7 | R401 |
| ADR-0021.R7.N1 | R401 |
| ADR-0021.R8 | R402, R403 |
| ADR-0021.R8.N1 | R402, R403 |
| ADR-0021.R9 | R404-R407 |
| ADR-0021.R9.N1 | R405 |
| ADR-0021.R10 | R408-R410 |
| ADR-0021.R11 | R411-R414 |
| ADR-0021.R12 | R415-R417, R419 |
| ADR-0021.R12.N1 | R417, R418 |
| ADR-0021.R12.N2 | R420-R422 |
| ADR-0021.R13 | R423 |
| ADR-0021.R14 | R424-R426 |
| ADR-0021.R14.N1 | R426 |
| ADR-0021.R14.N2 | R425 |
| ADR-0021.R15 | R427 |
| ADR-0021.R16 | R428 |
| ADR-0021.R16.N1 | R428 |
| ADR-0022.R2 | ref: ADR-0022.R2 |
| ADR-0022.R2.N1 | ref: ADR-0022.R2.N1 |
| ADR-0022.R2.N2 | ref: ADR-0022.R2.N2 |
| ADR-0022.R2.N3 | ref: ADR-0022.R2.N3 |
| ADR-0022.R2.N4 | ref: ADR-0022.R2.N4 |
| ADR-0022.R2.N5 | ref: ADR-0022.R2.N5 |
| ADR-0022.R2.N6 | ref: ADR-0022.R2.N6 |
| ADR-0022.R2.N7 | ref: ADR-0022.R2.N7 |
| ADR-0022.R2.N8 | ref: ADR-0022.R2.N8 |
| ADR-0022.R2.N9 | ref: ADR-0022.R2.N9 |
| ADR-0022.R2.N10 | ref: ADR-0022.R2.N10 |
| ADR-0022.R2.N11 | ref: ADR-0022.R2.N11 |
| ADR-0022.R2.N12 | ref: ADR-0022.R2.N12 |
| ADR-0022.R2.N13 | ref: ADR-0022.R2.N13 |
| ADR-0022.R2.N14 | ref: ADR-0022.R2.N14 |
| ADR-0022.R10 | ref: ADR-0022.R10 |
| ADR-0023.H.N1 | R433 |
| ADR-0023.D0 | R429-R434 |
| ADR-0023.R1 | R435-R438 |
| ADR-0023.R2 | R439, R441 |
| ADR-0023.R2.N1 | R440 |
| ADR-0023.R2.N2 | R442 |
| ADR-0023.R3.N1 | ref: ADR-0023.R3.N1 |
| ADR-0023.R4 | R443-R445 |
| ADR-0023.R5 | R446 |
| ADR-0023.R6 | R447, R448 |
| ADR-0023.R6.N1 | R449 |
| ADR-0023.R6.N2 | R450, R451 |
| ADR-0023.R7 | R452, R453, R455 |
| ADR-0023.R7.N1 | R453, R454 |
| ADR-0023.R7.N2 | R454, R455 |
| ADR-0023.R7.N3 | R453 |
| ADR-0023.R8 | R456, R457 |
| ADR-0023.R9 | R458 |
| ADR-0023.R10 | R459, R460 |
