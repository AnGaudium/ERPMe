Module: inventory    Chunk: 2 of 7    Source ADRs: ADR-0020, ADR-0021
Build step(s): 0, 3    Generated from index: 30d5706    Compiled by: Claude Opus 5.5, 2026-11-21

# `inventory` compiled spec, chunk 2: period-end actual costing, degenerate cases, late costs, lots, counts, landed cost

## Purpose

This chunk states the part of `inventory` law on: period-end actual costing and its degenerate cases, reruns and late purchase costs, lots, serial numbers and the reserved valuation type, the stock count document, the stock balance query, and the `landed_cost` document (its tables, sources, targets, allocation methods, rounding and posting period). `inventory` owns stock quantities and values and the costing that revalues them; the journal, accounts and periods belong to `ledger` and `periods`. The other `inventory` topics are in the other chunks.

## Entities and tables

DDL: `docs/design/DS-20-master-data.sql` (`lot`, `serial_number`) and `docs/design/DS-22-09-42-commercial-inventory.sql` (`stock_count`).

| Table | Meaning | Key | Parent | Owner |
| --- | --- | --- | --- | --- |
| `lot` | A lot of an item, tracked on material document lines and in stock quantities; carries no cost (R222, R223) | `id`; (`item_id`, `code`) unique; (`company_id`, `barcode`) unique; (`company_id`, `id`) | `item` | `inventory` |
| `serial_number` | A serial number of an item; a serial-tracked line has quantity 1 (R222, R223) | `id`; (`item_id`, `code`) unique; (`company_id`, `barcode`) unique; (`company_id`, `id`) | `item` | `inventory` |
| `stock_count` | Stock count document: counted quantities of one warehouse; posting creates count shortage and surplus movements (R225) | `id` (the `document`); (`company_id`, `id`, `warehouse_id`) | `document`, `warehouse` | `inventory` |

Defined by rule, without DDL: `landed_cost`, `landed_cost_line`, `landed_cost_target`, `landed_cost_allocation` (R228).

Reads: `material_document_line`, `stock_value`, `stock_quantity`, `stock_count_line`, `preliminary_price`, `movement_type`, `other_receipt`, `return_from_customer_line` (`inventory`, other chunks); `journal_line`, `derivation_trace` (`ledger`); `item`, `product_uom` (`master_data`); `posting_period` (`periods`).

## Commands and queries

Query of this chunk: `GetStockBalance` (R226); its row stands in chunk 4.

Documents of this chunk and their authorization areas (`authorization-areas.csv`): `landed_cost` (document type under `purchasing`, module `inventory`), `stock_count` (document type under `inventory`), the costing adjustment documents of period-end costing (document type `costing_adjustment` under `finance`), and the period-end costing run (function `costing_run` under `finance`). The sources name no command for them in this chunk.

Contract function, not a registry command: `inventory.contract.adjust_receipt_value` writes price-difference documents (R237).

Error codes bound to no named command: `landed_cost_target_invalid` (R228, R230), `landed_cost_source_exceeded` and `landed_cost_source_invalid` (R229), `allocation_manual_sum_mismatch` and `allocation_basis_missing` (R231), `landed_cost_period_mismatch` (R235), `negative_stock_value` (R236), `lot_needs_item` and `serial_needs_item` (R223).

## Rules

### Period-end actual costing

R201. Period-end actual costing is a sequential close task per company and period (ADR-0012.R13, ADR-0012.R16). For each item it computes the actual average of every valuation area from the opening value and quantity plus the period's receipts, including value-only additions classed by the `inventory_value_role` their document type declares in the registry: `receipt_addition` for landed cost and price differences to stock, which count; `costing_adjustment` for costing adjustment documents, which do not count (ADR-0008.R1). It solves the strongly connected components of the areas linked by the period's flows in topological order, each as one exact linear system in rational arithmetic (ADR-0025.R6), so the result is the same on every run and equal to the naive recomputation. It posts value-only adjustment documents (one per company and period, or split by item range when large) that revalue revalued issues and transfers to actual averages, with each movement type's offset key, and a derivation trace per item and area (Principle 6). BOM levels join the system in Phase 1, designed in DS-53 (ADR-0032). Production cost-object nodes, pools and WIP join this solve (ADR-0035.R6).
Source: ADR-0020.R12

R202. A line with costing role `issue_return` whose original issue line is in the period being costed, in the same valuation area, is revalued together with it at the area's actual average, so the pair nets to an issue of the net quantity.
Source: ADR-0020.R12.N1

R203. An `issue_return` line whose original line is in an earlier period keeps the original line's final unit cost after that period's costing. It is counted neither in the period's receipts nor among the revalued issues; the difference between its value and the period's actual average times its quantity stays in the area's closing value and enters the next period through the opening value, with no posting. The rounding residual of R215 is measured after setting that difference aside. When the closing quantity is zero, the period's issues stay at the actual average, and the set-aside difference, with any rounding, is posted as the residual of R215 (`inventory_revaluation_offset` key, with a derivation trace); the presence of a return never moves an area's issues to the preliminary price. Returned units issued again in the same period are issues like any other, valued at the period's actual average; the return's difference stays in the closing value, or goes to the residual when the closing quantity is zero. The other triggers of R215 apply as written: an area with no opening quantity and no receipts, or whose average would be negative, values its issues at the preliminary price and posts the residual. A closing value that would be negative only because of returns kept at their own value is treated like a closing quantity of zero: the issues stay at the actual average, the kept differences are posted as the residual, and the area closes at the actual average times its closing quantity.
Source: ADR-0020.R12.N1

R204. When the earlier period's costing changes the original line's value, on its first run or a rerun (R219), the return follows by a value-only adjustment posted by the costing of the return's own period, dated in that period: that period's sequential task goes back to `pending` when the earlier one runs again (ADR-0012.R16). In no case does a return enter an average, so the linear system of R201 is unchanged and stays exact. A return received into another valuation area than its original's is valued at the original line's cost and stays outside the receiving area's average, as in R203, also when the original is in the same period; its value then follows the original's final cost through this adjustment.
Source: ADR-0020.R12.N1

R205. A partial return takes the cumulative share of the original line's value V: after r of the line's quantity Q has been returned, a return of q takes round(V × (r + q) / Q) − round(V × r / Q), so the returns of a whole line total exactly V. A sales return receipt line always has an original: goods delivered before the migration cut-over come back as `other_receipt` (ADR-0047.R8) and `return_from_customer_line.delivery_line_id` is NOT NULL, so no preliminary-price value is defined for `issue_return` lines.
Source: ADR-0020.R12.N1

R206. A reversal line (`ADR-0020.R7` note of 2026-11-21) is treated in this solve as an `issue_return` line of the original's whole quantity: revalued with the original in the same period and area, otherwise a fixed-value line at the original's current value, followed by a value-only adjustment when a rerun revalues the original. Every statement of R203 and R204 about returns kept at their own value (the closing value, the residual at a zero closing quantity, a negative closing value) applies to it.
Source: ADR-0020.R12.N2

R207. A late landed cost, a price difference or an exchange-rate difference sent to stock is a value-only `receipt_addition` with quantity zero (ADR-0020.R12.N2): it joins the receipts of its posting period and so that period's average. With no quantity base R215 applies: the issues keep the preliminary price, and the addition stays in the closing value while the area holds units, and is the residual of R215 only at a zero closing quantity (R217).
Source: ADR-0020.R12.N2

R208. The exchange-rate difference between goods receipt and purchase invoice follows SAP: it is kept apart from price differences and is part of a stock item's actual cost by default; a company keeps it out of inventory with the company setting `costing.exchange_rate_difference_to_stock` (ADR-0047.R13). Interim, until the step that builds it: on a purchase order line for an item kept in stock, the company-currency difference on GR/IR between the receipt's applied rate and the invoice's applied rate is its own difference kind (`landed_cost` `cost_type` `exchange_rate_difference`) and enters the item's actual average as a `receipt_addition` value-only line on the receipt lines' item and valuation area, in the posting period of the posting that clears it. Lines without stock post it to the exchange-rate difference accounts (ADR-0047.R13, ADR-0011.R6, ADR-0021.R12).
Source: ADR-0020.R12.N3

R209. Group currency of movements (interim; the step 3 costing specification confirms the details): every journal line of a stock movement or a value-only inventory line has its group amount by ADR-0011.R2 and ADR-0011.R3, translated at posting from its transaction amount with the document's applied group rate, the rate of its own posting date. A movement's group amount is that of the inventory journal line that posts it (`ADR-0020.R6`). `material_document_line` and `stock_value` stay in company currency (ADR-0011.R6); the group value of an item and warehouse is the sum of its inventory journal lines' group amounts (ADR-0014.R17).
Source: ADR-0020.R12.N4

R210. At period end the solve of R201 runs once per carried currency (interim). In group currency each area's actual average is computed from the group amounts of its opening value and receipts, through the same flows (transfers, orders, pools, WIP), and each revalued line's group adjustment is that average times its quantity less the line's group amount. The company-currency result is never retranslated. Both currencies share one linear system, whose coefficients are quantities and shares, and differ only in its right-hand side: the second currency adds one right-hand side per component. A group average may rise while the company average falls.
Source: ADR-0020.R12.N4

R211. A costing adjustment line carries the company and group adjustments of the same item, warehouse and offset key; when they have opposite signs, or the company adjustment is zero, the group part is a separate group-only line (transaction and company amount 0, ADR-0011.R2), so the sign rule of ADR-0014 holds (interim). R215 applies per currency: its residuals, rounding included, post in each currency, the group part as a group-only line; which degenerate case applies is decided on quantities and in company currency, and the group currency follows it. An `issue_return` line keeps its original line's final group cost as it keeps the company cost.
Source: ADR-0020.R12.N4

R212. Phase 1 carries company currency always and the installation's group currency when it is set (ADR-0011.R6); a third valuation (profit center) is not designed. Costing adjustment lines take their group amount from the group-currency solve, an exception to ADR-0011.R3 (its note of 2026-11-21) (interim).
Source: ADR-0020.R12.N4

R213. The actual cost component split follows SAP: Phase 1 keeps the seam and builds no split through stock; production orders keep actual cost per posting component, and per detailed component as a read model (ADR-0072.R4). The feature, when built, carries values per posting component along the flows of the R201 solve, each component one more right-hand side, and the components of a node sum exactly to its value. It stores its result as a read model per item, valuation area, period and component beside the postings, which it never changes. It starts at a period start: the opening split of a purchased item is all `material`; that of a produced item follows the components of its released cost estimate (interim). Receipt additions go to `material` (interim).
Source: ADR-0020.R12.N5

### Degenerate cases

R215. Degenerate cases follow one rule: when an item's area has no receipts and no opening quantity, when its closing quantity is zero but value remains beyond the rounding bound of R216, when its closing value or its average would be negative, or when a component's system has no unique solution (for example goods transferred back and forth within a day; other components are solved normally), the area keeps the preliminary price for its issues, and any residual value is posted per warehouse as its own line with the `inventory_revaluation_offset` key and a derivation trace (interim, flagged: where such residuals go is an accounting rule; the regime may map the key). Rounding residuals of the revaluation are posted the same way (ADR-0006.R21). One exception: in an area holding fixed-value lines (`issue_return` lines kept at their own value, and reversals of an earlier period or another area), a closing quantity of zero, or a closing value negative only because of those lines, leaves the issues at the actual average, and the kept difference is posted as this residual (R203). The formulas and the adjustment document layout are specified for step 3.
Source: ADR-0020.R13, .N1

R216. At a zero closing quantity the remainder of an item's area is its book value after the period's lines are valued. The rounding bound of the item and area in the period is half a minor unit for each line whose value the period's costing sets as round(quantity × price) (its revalued issues, transfers out and consumption), plus one minor unit for each `issue_return` line revalued with an original of the same period and area; a reversal revalued with its original takes exactly the original's value and adds nothing. A remainder whose absolute value is at most the bound is a rounding residual: the issues stay at the actual average and the remainder is posted as the residual of R215. A remainder beyond the bound is "value remains" of R215: the area keeps the preliminary price for its issues, except where the fixed-value exception of R215 applies.
Source: ADR-0020.R13.N2

R217. A value-only receipt addition (a late landed cost) in an area with no opening quantity and no receipt quantity, whose only quantity came back by returns or reversals: when the area has a closing quantity, the addition stays in the closing value, the target closing value being round(price × (closing quantity − fixed-value quantity)) + the fixed-value lines' values + the value-only additions, so the addition enters the next period through the opening value; it goes to the residual of R215 only when the closing quantity is zero. The issues of such a period keep the preliminary price.
Source: ADR-0020.R13.N4

R218. SAP's "not distributed" differences map to the cases of R215 (value left at a zero closing quantity, a negative average or closing value, a system without a unique solution) and the kept `issue_return` differences of R203: their residual posts to `inventory_revaluation_offset` and stays there. SAP's "not allocated" differences need no mechanism: cycles are solved exactly by R201; rounding is the rounding residual of R215; consumption without a receipt of the higher-level product stays on the order as work in process (ADR-0035.R9) or, on a technically complete order, goes to cost of goods sold as `production_residual_cost` (ADR-0035.R10); every consumer is revalued. A report of these amounts per item and area reads the derivation traces of the residual, WIP and residual-cost postings; nothing is stored for it.
Source: ADR-0020.R13.N3

### Reruns and late costs

R219. A backdated document in a period that is not locked makes the costing of that period and later unlocked periods stale (ADR-0012.R10, ADR-0012.R12); a rerun posts only the difference (ADR-0012.R15). Locked periods are never recosted.
Source: ADR-0020.R14

R220. Landed cost added in the same open period as its receipt raises the receipt's value through a value-only line (`ADR-0020.R9`) before costing. A late purchase cost (landed cost) is booked in the period of the cost document's own posting date, which must be a period that is not locked (ADR-0012), as a value-only `receipt_addition` (R201) on the target's item and valuation area in that period, so it enters that period's actual average; when the area has no quantity to carry it, R215 applies. No locked period is recomputed, no past consumer is charged, and the cost is never forced into the receipt's period. A document dated in an earlier period that is not locked makes that period's costing stale like any backdated document (R219). The cases are in R233 to R236.
Source: ADR-0020.R15, .N1

R221. A change of `valuation_area_level` after stock is posted is not supported in Phase 1; how it would be applied waits for the open question on the regime's retrospective treatment of a change of costing scope, which is content of the localization package (ADR-0015.R8).
Source: ADR-0020.R16

### Lots, serial numbers and the valuation type

R222. `lot` (company, item, `code`, optional `expiry_date`, `manufacture_date`, and `best_before_date` of ADR-0063.R26) and `serial_number` (company, item, `code`) are tracked on material document lines and in `stock_quantity`; they carry no cost. A serial-tracked line has quantity 1. FEFO and shelf-life picking are Phase 1 (ADR-0023.R14).
Source: ADR-0020.R17

R223. Lot and serial codes are kept as they come, with no character rule, so old and supplier lot numbers load unchanged; the code stays unique per item. Lots and serials have an optional `barcode`, an internal label code unique in the company through the barcode registry; the command that creates a lot or serial whose code does not fit GS1 (10) or (21) (1 to 20 characters of GS1 character set 82) generates one, and labels print it. A lot or serial code scanned without GS1 resolves only with an item from the step's context (`lot_needs_item`, `serial_needs_item`) (ADR-0061.R8, ADR-0061.R13, ADR-0061.R21).
Source: ADR-0020.R17.N1

R224. Valuation stays per item and valuation area; lots and serials carry no cost. Following SAP, the valuation key has a reserved axis: a nullable `valuation_type` on `stock_value`, part of its key `uq_stock_value_key UNIQUE NULLS NOT DISTINCT (company_id, item_id, warehouse_id, valuation_type)`, and on `material_document_line`, never set in Phase 1: on both a CHECK keeps the column null (`ck_stock_value_valuation_type`, `ck_material_document_line_valuation_type`). Split valuation and valuation by lot are later features that fill it and drop the CHECK, with no key change. A split-valued item is lot-tracked and each lot carries one valuation type, so the quantity key (`stock_quantity`) keeps its lot axis and does not change.
Source: ADR-0020.R17.N2, .N3

### Stock count

R225. A stock count (`stock_count` document) holds counted quantities per item, warehouse and lot. Its lines carry the line unit block: a count may be entered in the product's counting units (`is_counting_unit`), several lines per item, bin and lot, each converted half up and summed in the inventory unit (ADR-0056.R15). With warehouse management, counts are created as drafts from count tasks (per bin where bins are managed, lot or serial and status) (ADR-0023.R18). The count's lines store the book quantity, its freeze time and an optional difference reason per key; posting posts the sum of counted quantities minus the stored book quantity per key, as count shortage and surplus movements with the movement types' value sources and keys (`ADR-0020.R5`; ADR-0075.R3; `INV-865`, `INV-866`).
Source: ADR-0020.R18, .N1, .N2

### Simulation and stock balance

R226. In simulation the stock lock helper keeps balances in memory and takes no lock (ADR-0008.R10); the plan shows quantities, values and the preliminary prices used. The query `GetStockBalance` returns quantity and value per item, warehouse and lot, as of a date; it also groups by bin, status and handling unit, on the current balance (ADR-0023.R5, ADR-0023.R23).
Source: ADR-0020.R19

### Landed cost document

R227. Step 3 delivers one core mechanism, the `landed_cost` document: a receipt value adjustment. It takes amounts already posted to `purchase_cost_clearing`, allocates them to receipt lines (by value, quantity, weight or manual amounts, exactly and deterministically), and moves them from clearing into stock in the period of its own posting date (R233). The customs declaration, supplier cost invoices and invoice price differences to stock are step 5 documents (B3); each posts its amounts to `purchase_cost_clearing` and proposes a `landed_cost` document. The treatment of import taxes stays with the author, as flagged regime settings and an open question (ADR-0021.R16.N1); a purchase return after allocated landed cost follows `movement_type.purchase_return.include_landed_cost` (R230).
Source: ADR-0021.D0

R228. A `landed_cost` is a posting document in company currency with these tables:
- `landed_cost_line`: one cost with `line_number`, `cost_type`, `amount`, `allocation_method`, `source_journal_line_id` (the journal line on `purchase_cost_clearing` that holds the cost), and nullable `item_id` and `tax_code_id`;
- `landed_cost_target`: the receipt material document lines a cost line is allocated to, with `manual_amount` for the `manual` method;
- `landed_cost_allocation`: one row per target with the snapshot of its basis, its exact share, its amount, its `mode` and `derivation_trace_id`; every new row has `mode` `open` (R236).
Each cost line has its own targets; a cost line with `item_id` may target only receipts of that item (`landed_cost_target_invalid`). `cost_type` values: `capitalized_tax` (with the tax code), `freight`, `insurance`, `handling`, `price_difference`, `other`, and `exchange_rate_difference` (interim, R208). The document type declares `inventory_value_role` `receipt_addition` (R201). It adds no transaction key: it posts to the inventory keys and credits the source line's account.
Source: ADR-0021.R1, ADR-0020.R12.N3, ADR-0021.R6.N2

R229. Sources of a landed cost:
- the amount comes from the source journal line in company currency and is never reconverted, so the clearing account nets to zero;
- one source may be allocated in parts;
- what has been allocated is computed from the landed cost lines that refer to the source (ADR-0009.R7); a line that would take more than the unallocated rest is rejected with `landed_cost_source_exceeded`;
- the credit posts to the source line's operational account, not to a newly determined one;
- a source must be a posted, unreversed line of the same company on an account mapped to `purchase_cost_clearing`, otherwise `landed_cost_source_invalid`;
- in step 3 and 4 tests, sources are general journal entries on `purchase_cost_clearing` (a `none` control kind account; ADR-0010);
- a source that is a credit (a freight credit note, a duty refund) gives a negative cost line.
Source: ADR-0021.R2

R230. Eligible targets are lines of movement types `purchase_receipt` and `other_receipt` (`ADR-0020.R4`) that are not reversed; any other target is rejected with `landed_cost_target_invalid`. The basis is the line as posted. Customs or freight assessed before the goods receipt wait in clearing. Goods received into a `transit` warehouse take the cost there: the inventory key follows the target's warehouse kind (`inventory_posting`, `inventory_in_transit_posting` or `inventory_goods_sent_posting`, `ADR-0020.R1`), and transfers carry it onward through costing. A purchase return carries its receipt's proportional share of allocated landed cost while `movement_type.purchase_return.include_landed_cost` reads true, the core default (ADR-0063.R24).
Source: ADR-0021.R3, .N1

R231. Allocation methods, given as method: basis; condition.
- `value`: the target's own receipt value, without landed costs already added; independent of the order in which landed cost documents post.
- `quantity`: inventory quantity converted to one unit; all targets' units have the same `quantity_kind` (ADR-0018.R8), and company units convert through `product_uom`.
- `weight`: quantity × the item's `gross_weight` per inventory unit, converted to kilograms; gross weight, because freight and insurance are charged on shipping weight (ADR-0018.R4).
- `manual`: amounts entered per target; their sum must equal the cost line, otherwise `allocation_manual_sum_mismatch`.
A missing basis or a zero total basis is rejected with `allocation_basis_missing`, which names the targets and the fix (set the weight, or choose another method). The basis values are snapshotted in the allocation rows, because master data may change later.
Source: ADR-0021.R4

R232. Shares are exact rationals. Amounts are rounded with the largest-remainder method to the company currency's minor unit; ties go to the earlier target by material document number, then `line_number`. The amounts sum exactly to the cost line, and the trace records which targets received the remainder units (ADR-0006.R21). Negative cost lines are allocated the same way.
Source: ADR-0021.R5

### Landed cost posting period

R233. A landed cost follows SAP: it is booked in the current period, the period of the document's own posting date, which must be a period whose `inventory` area state is not `locked` (`open` or `soft_locked` as ADR-0012 uses it; which periods accept postings is the backdating rule of the ADR-0012.R10 note). The document posts on its own posting date whether the receipt's period is the same, earlier and not locked, or locked. A landed cost in the same open period as its receipt is unchanged. No locked period is recomputed, no past consumer is charged, and the cost is never forced into the receipt's period. A document dated in an earlier period that is not locked makes that period's costing, and every later one's, stale like any backdated document (R219); the period the cost lands in is the one the user dates the document in, within the not-locked periods from the receipt's posting date on.
Source: ADR-0021.R6, .N1, .N2

R234. Each target's allocated amount (R231, R232) posts as a value-only `receipt_addition` line on the target's item and warehouse in the posting period, debiting that warehouse's inventory key and crediting the source account through the stock lock helper (`ADR-0020.R9`, R201, R220), so it enters that period's actual average of the target's valuation area.
Source: ADR-0021.R6, .N2

R235. Interim, flagged (for the step 3 spec to confirm): `landed_cost_period_mismatch` stays only for a posting date earlier than a target's receipt posting date (stock cannot take value before it exists; the cost waits in clearing); a posting date in a locked period is refused by ADR-0012 as for any document.
Source: ADR-0021.R6, .N2

R236. Interim, flagged (for the step 3 spec to confirm):
- the allocation basis across receipt lines stays R231 and R232, on the receipt lines as posted, whatever happened to the goods since;
- a receipt already returned, in full or in part, takes its share like any target, and the share enters the area's average as the cost of consumed goods does; a return posted after the landed cost carries its share as `movement_type.purchase_return.include_landed_cost` says (R230);
- when the target's area has no quantity on the posting date, the line still posts, and period-end costing treats the value left at zero quantity by R215; a negative cost line (a credit) that would make a warehouse's `stock_value` negative is refused with `negative_stock_value` (`ADR-0021.R9`);
- the valuation area is the one of the target receipt line's warehouse; goods transferred to another area since the receipt do not carry the cost there;
- `landed_cost_allocation.mode` is `open` on every new row; `closed` is not written, and the step 3 DDL decides whether the column stays.
Source: ADR-0021.R6.N2

R237. Price-difference documents written by `inventory.contract.adjust_receipt_value` are late purchase costs like any landed cost: each posts in its own posting period as a value-only `receipt_addition`, dated as ADR-0030.R2.N1 says (R805), with no split range over earlier periods. The plan shows each target's mode, which is `open` (R236).
Source: ADR-0021.R6, ADR-0021.R6.N2

## Invariants

Statements are those of `invariants.csv`. Each row stands once in the module, in the chunk that states the rule its catalog source names.

| Invariant | Name | Check point | Statement | Protects |
| --- | --- | --- | --- | --- |
| `INV-26` | `allocations_sum_to_cost` | day | Landed cost allocations sum exactly to each cost line, and every allocation and costing adjustment has a derivation trace. | R228, R232 |
| `INV-27` | `clearing_equals_unallocated` | day | No source line on `purchase_cost_clearing` is allocated beyond its amount, and per source line the clearing balance equals its unallocated rest. | R229 |

Named by rules of this chunk, with their rows in another chunk: `INV-865`, `INV-866` (R225; the chunk stating ADR-0075.R3).

## Edge cases

| Edge case | Name | Case | Outcome | Protects |
| --- | --- | --- | --- | --- |
| `EC-12` | `landed_cost_after_period_lock` | A cost allocated to goods received in a period whose inventory area is locked. Current law (ADR-0021.R6.N2): the cost posts in the period of its own posting date, a period that is not locked, as a value-only `receipt_addition` that takes part in that period's actual cost; the locked period is not recomputed and nothing is allocated to past consumers. The catalog row predates ADR-0021.R6.N2. | `must_succeed` | R233, R234 |
| `EC-15` | `lot_and_serial_movements` | Movements of lot- and serial-tracked items, including a lot split across warehouses. | `must_succeed` | R222 |
| `EC-16` | `stock_count_differences` | A stock count with both a shortage and a surplus. | `must_succeed` | R225 |
| `EC-18` | `degenerate_costing` | Goods transferred back and forth on one day, and an area left with value but no quantity. | `must_succeed` | R215 |
| `EC-29` | `one_cost_source_several_receipts` | One cost source allocated over two partial receipts of the same goods (e.g. 600 then 400 units); from step 5 the source can be a customs declaration. | `must_succeed` | R229 |
| `EC-30` | `cost_before_receipt` | A cost recorded before the goods receipt waits in clearing until allocated. | `must_succeed` | R230 |

## Settings

None: the settings this chunk uses have their rows in other chunks: `costing.exchange_rate_difference_to_stock` (R208; the chunk stating ADR-0047.R13) and `movement_type.purchase_return.include_landed_cost` (R230, R236; the chunk stating ADR-0063.R24).

## UI annotations

None: the sources hold no ADR-0077 annotation for the units of this chunk.

## Conflicts

CONFLICT ADR-0020.R12: the rule's own amendment citing ADR-0032 governs; BOM levels join the costing solve in Phase 1 (DS-53), not Phase 2, so R201 states Phase 1.
CONFLICT ADR-0020.R15: ADR-0020.R15.N1 and ADR-0021.R6.N2 govern (author, 2026-11-21); a late landed cost is booked as a `receipt_addition` in the period of its own posting date, and "landed cost of a locked period is posted now and allocated by consumer" is not restated (R220).
CONFLICT ADR-0020.R17: the rule's closing amendment citing ADR-0023.R14 governs, so FEFO and shelf-life picking are Phase 1; the DDL with ADR-0063.R26 adds `best_before_date` to `lot` (R222).
CONFLICT ADR-0020.R18: the rule's closing amendment citing ADR-0023.R18 and the note ADR-0020.R18.N2 (ADR-0075.R3) govern; every count stores the book quantity per key and posts counted minus that stored quantity (R225).
CONFLICT ADR-0020.R19: the rule's closing amendment citing ADR-0023.R5 and ADR-0023.R23 governs; `GetStockBalance` also groups by bin, status and handling unit on the current balance (R226).
CONFLICT ADR-0021.D0: ADR-0021.R6.N2 governs (author's decision of 2026-11-21 on late purchase costs); the locked-period recomputation per consumer, the earlier-unlocked flagged case and the closed-period method choice are not restated (R227, R233); returns after landed cost are no longer open (ADR-0021.R3.N1, R227).
CONFLICT ADR-0021.R1: ADR-0021.R6.N2 point (f) governs the allocation mode, so only `open` is written; ADR-0020.R12.N3 adds the interim cost type `exchange_rate_difference` (R228).
CONFLICT ADR-0021.R3: ADR-0021.R3.N1 (ADR-0063.R24) settles the open question on purchase returns after allocated landed cost with the setting `movement_type.purchase_return.include_landed_cost`, so the rule's open-question mark is not restated (R230).
CONFLICT ADR-0021.R6: ADR-0021.R6.N2 governs; the table rows "Receipt period earlier, not locked" and "Receipt period locked", closed mode and the requirement that targets of one document share one case and receipt period are superseded (R233-R237).
CONFLICT ADR-0021.R6.N1: superseded by ADR-0021.R6.N2 of 2026-11-21; the confirmation that a locked receipt period sends the cost through consumer split in the first unlocked period no longer holds (R233).
CONFLICT ADR-0021.R6.N2: this note is the governing text of the late-cost decision; its "no longer" marks the end of closed mode, consumer split and the one-case rule, and it supersedes ADR-0021.R6 rows and the 2026-11-19 note (R233-R236).

## Proposed (not law)

None

## Trace

| Source | Where |
| --- | --- |
| ADR-0020.R12 | R201 |
| ADR-0020.R12.N1 | R202-R205 |
| ADR-0020.R12.N2 | R206-R207 |
| ADR-0020.R12.N3 | R208, R228 |
| ADR-0020.R12.N4 | R209-R212 |
| ADR-0020.R12.N5 | R213 |
| ADR-0020.R13 | R215 |
| ADR-0020.R13.N1 | R215 |
| ADR-0020.R13.N2 | R216 |
| ADR-0020.R13.N3 | R218 |
| ADR-0020.R13.N4 | R217 |
| ADR-0020.R14 | R219 |
| ADR-0020.R15 | R220 |
| ADR-0020.R15.N1 | R220 |
| ADR-0020.R16 | R221 |
| ADR-0020.R17 | R222 |
| ADR-0020.R17.N1 | R223 |
| ADR-0020.R17.N2 | R224 |
| ADR-0020.R17.N3 | R224 |
| ADR-0020.R18 | R225 |
| ADR-0020.R18.N1 | R225 |
| ADR-0020.R18.N2 | R225 |
| ADR-0020.R19 | R226 |
| ADR-0021.D0 | R227 |
| ADR-0021.R1 | R228 |
| ADR-0021.R2 | R229 |
| ADR-0021.R3 | R230 |
| ADR-0021.R3.N1 | R230 |
| ADR-0021.R4 | R231 |
| ADR-0021.R5 | R232 |
| ADR-0021.R6 | R233-R235, R237 |
| ADR-0021.R6.N1 | R233 |
| ADR-0021.R6.N2 | R228, R233-R237 |
