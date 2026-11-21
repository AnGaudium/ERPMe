# ADR-0021: Landed cost

Status: accepted (2026-11-14) under ADR-0005, reviewed by Claude Fable 5.2 (builder Claude Opus 5.5). Design item: DS-11 (ADR part for step 0; formulas and layouts specified for step 3). Related decisions: D5, D6, D10. Principles 5, 6, 13. Build principle B3. ADR-0004, ADR-0005, ADR-0006, ADR-0008, ADR-0009, ADR-0010, ADR-0011, ADR-0012, ADR-0014, ADR-0015, ADR-0016, ADR-0018, ADR-0020.

## Decision

Step 3 delivers one core mechanism, the `landed_cost` document: a receipt value adjustment. It takes amounts already posted to `purchase_cost_clearing`, allocates them to receipt lines (by value, quantity, weight or manual amounts, exactly and deterministically), and moves them from clearing into stock.

What happens depends on the state of the receipt's inventory period (ADR-0012):
- **Same period:** the allocated cost is added to the receipt's value before period-end costing.
- **Earlier period, still not locked:** the document must be dated in the receipt's period (interim, flagged).
- **Locked period:** the cost goes to whoever took the goods. The core recomputes the locked periods' actual costing with the cost added, and posts in the first unlocked period the difference per consumer, plus the share still on hand as stock.

The customs declaration, supplier cost invoices and invoice price differences to stock are step 5 documents (B3). Each posts its amounts to `purchase_cost_clearing` and proposes a `landed_cost` document. Accounting choices stay with the author, as flagged regime settings and open questions:
- the closed-period method;
- the earlier-unlocked case;
- the treatment of import taxes;
- returns after landed cost.

### Rules

**The core mechanism (step 3)**

1. A `landed_cost` is a posting document in company currency with three tables:
   - `landed_cost_line`: one cost with `line_number`, `cost_type`, `amount`, `allocation_method`, `source_journal_line_id` (the journal line on `purchase_cost_clearing` that holds the cost), and nullable `item_id` and `tax_code_id`.
   - `landed_cost_target`: the receipt material document lines (ADR-0020) a cost line is allocated to, with `manual_amount` for the `manual` method.
   - `landed_cost_allocation`: one row per target with the snapshot of its basis, its exact share, its amount, its mode (`open` or `closed`) and `derivation_trace_id`.

   Each cost line has its own targets; a cost line with `item_id` may target only receipts of that item (`landed_cost_target_invalid`). `cost_type` values: `capitalized_tax` (with the tax code), `freight`, `insurance`, `handling`, `price_difference`, `other`.

   The document type declares `inventory_value_role` `receipt_addition` (ADR-0020 rule 12). It adds no transaction key: it posts to the inventory keys and credits the source line's account.
2. Sources:
   - The amount comes from the source journal line in company currency. It is never reconverted, so the clearing account nets to zero.
   - One source may be allocated in parts.
   - What has been allocated is computed from the landed cost lines that refer to the source (ADR-0009 rule 7). A line that would take more than the unallocated rest is rejected with `landed_cost_source_exceeded`.
   - The credit posts to the source line's operational account, not to a newly determined one.
   - A source must be a posted, unreversed line of the same company on an account mapped to `purchase_cost_clearing`, otherwise `landed_cost_source_invalid`.
   - In step 3 and 4 tests, sources are general journal entries on `purchase_cost_clearing` (a `none` control kind account; ADR-0010).
   - A source that is a credit (a freight credit note, a duty refund) gives a negative cost line.
3. Eligible targets are lines of movement types `purchase_receipt` and `other_receipt` (ADR-0020 rule 4) that are not reversed. Any other target is rejected with `landed_cost_target_invalid`. The basis is the line as posted. How purchase returns of the receipt affect landed cost already allocated is an open question (rule 16).
   - Customs or freight assessed before the goods receipt simply wait in clearing.
   - Goods received into a `transit` warehouse take the cost there. The inventory key follows the target's warehouse kind (`inventory_posting`, `inventory_in_transit_posting` or `inventory_goods_sent_posting`, ADR-0020 rule 1), and transfers carry it onward through costing.

   Note ([ADR-0063](0063-configurable-policy-settings.md), 2026-11-15): a purchase return carries its receipt's proportional share of allocated landed cost while `movement_type.purchase_return.include_landed_cost` reads true, the core default (rule 24).

**Allocation**

4. Methods:

   | Method | Basis | Condition |
   | --- | --- | --- |
   | `value` | The target's own receipt value, without landed costs already added | Independent of the order in which landed cost documents post |
   | `quantity` | Inventory quantity converted to one unit | All targets' units have the same `quantity_kind` (ADR-0018 rule 8); company units convert through `product_uom` |
   | `weight` | Quantity × the item's `gross_weight` per inventory unit, converted to kilograms | Gross weight, because freight and insurance are charged on shipping weight (ADR-0018 rule 4) |
   | `manual` | Amounts entered per target | Their sum must equal the cost line, otherwise `allocation_manual_sum_mismatch` |

   A missing basis or a zero total basis is rejected with `allocation_basis_missing`, which names the targets and the fix (set the weight, or choose another method). The basis values are snapshotted in the allocation rows, because master data may change later.
5. Shares are exact rationals. Amounts are rounded with the largest-remainder method to the company currency's minor unit; ties go to the earlier target by material document number, then `line_number`. The amounts sum exactly to the cost line, and the trace records which targets received the remainder units (ADR-0006 rule 21). Negative cost lines are allocated the same way.

**Periods**

6. Each target's mode is fixed by the `inventory` area state (ADR-0012) of its receipt's posting period, compared with the landed cost document's posting period:

   | Case | Rule |
   | --- | --- |
   | Same period | `open`: a value-only line per target, debiting the inventory key of the target's warehouse and crediting the source account, through the stock lock helper (ADR-0020 rules 9, 15). Period-end costing then includes it in the actual average (ADR-0020 rule 12) |
   | Receipt period earlier, not `locked` | Rejected with `landed_cost_period_mismatch`, naming the receipt's period and its valid posting date range. The cost is then posted into that period, whose costing reruns (ADR-0020 rule 14); if the source is dated later, clearing shows a credit at that period's end until the source's date, an accrual effect. Interim, flagged: the spec does not state this case (open question) |
   | Landed cost posting period earlier than the receipt's period | Rejected with `landed_cost_period_mismatch`: stock cannot take value before it exists; the cost waits in clearing |
   | Receipt period `locked` | `closed`: rule 7. The posting date must lie in the first unlocked inventory period, otherwise `landed_cost_period_mismatch` names it |

   Price-difference documents written by `inventory.contract.adjust_receipt_value` use the postable period, dates and split range of [ADR-0030](0030-commercial-seams-and-imports.md) rule 2 instead. Targets of one document must fall into one case and one receipt period. Otherwise `landed_cost_period_mismatch` lists the groups to split into separate documents. The plan shows each target's mode.

   Note (author's delegation, 2026-11-19): confirmed: a landed cost goes into the receipt's period while that period is open. When it is locked, rule 7 applies (the first unlocked period, split by consumer); that is not an error. `landed_cost_period_mismatch` only names the required period, its date range or the groups to split, which is consistent with this.

   Note (the author, 2026-11-21): a late landed cost follows SAP (checked against SAP sources on 2026-11-21, point C1 of the verification section of [reviews/2026-11-21-costing-sap-comparison.md](../reviews/2026-11-21-costing-sap-comparison.md): SAP never posts into a closed period; a posting may be dated in the previous period while that period is still open. This is consistent with the decision: the document posts on its own posting date in a period that is not locked, "the current open period" being the period of that date; which periods accept postings is NativeFlows' own backdating rule, [ADR-0012](0012-posting-periods-and-closing.md) rule 10 note, not SAP's window): it is booked in the current open period, on its own posting date, whether the receipt's period is the same, earlier and unlocked, soft-locked or locked; it is never forced into the receipt's period, no earlier period is recomputed and no past consumer is charged. A landed cost in the same open period as its receipt is unchanged. Chief architect's translation (interim, 2026-11-21, until the step that builds it): each target's allocated amount (rules 4, 5) posts as a value-only `receipt_addition` line on the target's item and warehouse in the posting period, debiting that warehouse's inventory key and crediting the source account through the stock lock helper ([ADR-0020](0020-inventory-and-costing-model.md) rules 9, 12, 15), so it enters that period's actual average of the target's valuation area. Superseded: the rows "Receipt period earlier, not `locked`" and "Receipt period `locked`" of the table, the requirement that the targets of one document fall into one case and one receipt period, and the 2026-11-19 note below. Cases the decision leaves open, interim, flagged (chief architect): (a) `landed_cost_period_mismatch` stays only for a posting date earlier than a target's receipt posting date (stock cannot take value before it exists); a posting date in a period that is not open is refused by ADR-0012 as for any document. (b) The allocation basis across receipt lines stays rules 4 and 5, on the receipt lines as posted, whatever happened to the goods since. (c) A receipt already returned, in full or in part, takes its share like any target, and the share enters the area's average as the cost of consumed goods does; a return posted after the landed cost carries its share as `movement_type.purchase_return.include_landed_cost` says (rule 3 note). (d) When the target's area has no quantity on the posting date, the line still posts, and period-end costing treats the value left at zero quantity by ADR-0020 rule 13. A negative cost line (a credit) that would make a warehouse's `stock_value` negative is still refused with `negative_stock_value`, as rule 9 and its 2026-11-19 note say. (e) The valuation area is the one of the target receipt line's warehouse; goods transferred to another area since the receipt do not carry the cost there. (f) `landed_cost_allocation.mode` is `open` on every new row; `closed` is no longer written, and the step 3 DDL decides whether the column stays. What else must change is the landed-cost rebuild entry under "S2 closure (2026-11-21)" in [open-questions.md](../open-questions.md).
7. Closed mode, method `consumer_split`, the interim seed (shares landing on production consumption go to the order's material pool, [ADR-0035](0035-production-costing.md) rule 8):
   - The core reruns ADR-0020 rule 12's exact solve for the item over every locked period from the receipt's period on, once as posted and once with the allocated amount added to the receipt. It takes the difference per movement type offset key, item and warehouse.
   - The quantity on hand at the end of the last locked period takes the rest, per warehouse that holds it, as a `receipt_addition` value-only line in the posting period.
   - Consumers are not a fixed list. Every revalued movement in those periods gets its share through its own offset key: sales from any warehouse, consumption, scrap, other issues, count shortages, and later production. Transfers carry value to receiving warehouses, and returns enter as the regime sets them (ADR-0020 rule 5). Degenerate cases follow ADR-0020 rule 13.
   - Consumer lines carry item and warehouse, with no partner, and leave `material_document_line_id` null.
   - The allocation row and its trace name the contributing periods and movements (Principle 6).
   - The lines are rounded by largest remainder so they sum exactly to the allocated amount.

   Note (the author, 2026-11-21): superseded: closed mode and the method `consumer_split` are no longer used; a late landed cost posts as the rule 6 note of this date says.
8. The closed-period method is the regime setting `landed_cost.closed_period_method`, with options `consumer_split` (rule 7) and `stock_coverage`. Under `stock_coverage`, the stock share of a target is min(1, quantity of the item on hand in the receipt's valuation area at the end of the last locked period ÷ the target's receipt quantity); that share goes to stock as a `receipt_addition`, split over the warehouses holding the quantity in proportion to it, and the rest to the `price_difference` key. If the regime maps `price_difference` to an inventory account, the rest also goes to stock, to the same warehouses.
   - The setting's date basis is the posting date (ADR-0016 rule 10).
   - The Vietnam package seeds `consumer_split` with basis `unverified`. In production it is refused until verified (ADR-0016 rule 12).
   - Whether either method is acceptable under VAS is the existing open question, now with these two alternatives.

   Note (the author, 2026-11-21): superseded with rule 7: the regime setting `landed_cost.closed_period_method` and its options `consumer_split` and `stock_coverage` are removed. No core catalog holds it (`settings.csv` has no row); the Vietnam package's seed (DS-19 `regimes/tt99/settings.yaml`; ADR-0039 rule 9) goes in its rework. The VAS question of this rule is answered by the author's decision and closed.

**Correction and reversal**

9. Corrections and reversals:
   - A landed cost is corrected by the correction type `landed_cost_correction` (`correction_of_id`, ADR-0009 rule 23; its `Post` command is registered like other correction types, ADR-0008 rule 1). It holds signed differences per cost line and target, and follows the same period rules.
   - Whether `landed_cost` is an internal document that may be reversed (ADR-0009 rules 18–20) is an open question. Interim, flagged: `is_reversible` true, with the extra precondition that no `stock_value` it touched becomes negative.
   - A landed cost targeting a receipt refers to it, so the receipt cannot be reversed while it stands (`document_referenced`, ADR-0009 rule 19).
   - A value-only inventory line that would make a warehouse's `stock_value` negative is rejected with `negative_stock_value`; values left at zero quantity are handled by costing (ADR-0020 rule 13).

   Note (author's delegation, 2026-11-19): confirmed: a landed cost document is reversible as long as no stock value becomes negative.

**Source documents (step 5)**

10. A `customs_declaration` posts what customs assessed for an import.
    - Header: declaration number and date, supplier, the purchase orders or receipts it covers. `transaction_currency` is the currency customs assesses in.
    - Lines: item, quantity, unit; `hs_code`; `country_of_origin` (ISO 3166-1 alpha-2); customs value in the declared currency, and the customs exchange rate. The customs rate is document rate type `customs` (ADR-0011 rule 12) and converts customs value only to compute tax bases, never a journal amount.
    - Taxes: each line has rows in `customs_declaration_tax` (tax code, base, assessed amount, recomputed amount). Import duty, excise, environmental protection tax, anti-dumping or safeguard duty and import VAT are all tax codes (DS-23), not fixed columns.
    - Amounts are recorded as assessed. The core recomputes them from the tax codes and reports differences as the check result `customs_assessment_differs`, never changing the assessed amount.
    - Journal conversion follows ADR-0011.
11. Posting a customs declaration:
    - credits each tax's payable account through its tax code's key (`import_export_duty`, `special_consumption_tax`, `import_tax`; DS-23 adds keys for other import taxes);
    - debits either `purchase_cost_clearing`, when the tax code's `import_treatment` is `capitalize`, or the recoverable tax account through `input_tax`, when it is `recoverable` (e.g. deductible import VAT to 1331, [08](../spec/08-l10n-vn.md#imports-and-purchase-costs)).

    `import_treatment`, including when import VAT is not deductible and is capitalized, is a package rule with a basis, flagged until verified (open question; DS-19, DS-23). Import tax codes and the tax rows written at posting: [ADR-0041](0041-tax-engine.md) rules 1, 11.
    - The declaration proposes a `landed_cost` with one cost line per declaration line and capitalized tax. Each cost line targets only receipt lines of that item, prorated by received over declared quantity, less what is already allocated (one declaration, receipts of 600 and then 400 units).
    - A customs amendment is the correction type `customs_declaration_amendment` (`correction_of_id`), posting differences.
    - `customs_declaration` is not reversible, deliberately stricter than ADR-0009 rule 19's interim: it records an outside party's document, and the amendment type corrects it.
12. Other sources and the GR/IR link:
    - A supplier's freight, insurance or handling invoice posts its cost to `purchase_cost_clearing` (DS-22).
    - A goods receipt credits `gr_ir_clearing`, and the goods invoice debits it.
    - Invoice-versus-receipt differences (with receipts at the order price, invoice versus order; [ADR-0030](0030-commercial-seams-and-imports.md) rule 4) keep one mechanism, the regime's determination of the `price_difference` key (ADR-0015 rule 4). When it determines a price difference account, the invoice posts there. When it determines an inventory account, the invoice posts the difference to `purchase_cost_clearing` instead, and calls `inventory.contract.adjust_receipt_value`, which writes `landed_cost` documents with `cost_type` `price_difference` targeting the matched receipt lines in the invoice's transaction (replacing "emits in the same batch"), so receipts in locked periods get the same treatment (rules 6–8) and nothing waits in clearing for a person.
    - Landed costs never pass through GR/IR. Price differences sent to stock are written by `inventory.contract.adjust_receipt_value`, split per receipt period; a receipt period that is not open is treated as closed; differences for goods not yet received wait in `pending_receipt_adjustment`; GR/IR carries the order price ([ADR-0030](0030-commercial-seams-and-imports.md) rules 1, 2, 4).
    - Which TT99 account holds GR/IR clearing, which rate values an import receipt and where rate differences go are existing open questions, read as regime settings by DS-22.

    Note (the author, 2026-11-21): price differences sent to stock for an earlier period are booked in the current open period, like any late purchase cost (rule 6 note); the exchange-rate difference between goods receipt and invoice is designed as SAP does ([ADR-0047](0047-commercial-documents-and-pricing.md) rule 13 note). Chief architect's translation (interim, 2026-11-21, until the step that builds it): both go to stock as a `receipt_addition` in the posting period of the document `inventory.contract.adjust_receipt_value` writes, whatever the state of the receipt's period, and rule 1's `cost_type` values gain `exchange_rate_difference` for the exchange-rate difference of a stock item ([ADR-0020](0020-inventory-and-costing-model.md) rule 12 note).

    Note (chief architect, 2026-11-21; the author's instruction that costing follows SAP): delivery costs, settled following SAP as verified (points A2a and A2b of the verification section of [reviews/2026-11-21-costing-sap-comparison.md](../reviews/2026-11-21-costing-sap-comparison.md)).
    - **Planned delivery costs** are conditions on the purchase order line, accrued at goods receipt into the receipt's stock value against a delivery-cost clearing key and cleared by the freight supplier's invoice, a difference being a price difference handled like the purchase price difference ([ADR-0047](0047-commercial-documents-and-pricing.md) rule 13 note of this date; interim, built at step 5). This answers "Revisit when: planned delivery costs on purchase orders are needed". The accrual is part of the receipt's document value, so it is no `landed_cost`; only the invoice's difference sent to stock is one.
    - **Unplanned delivery costs** are the `landed_cost` path of this ADR: a supplier's cost invoice line with no planned condition (`line_kind` `landed_cost`). The company setting `landed_cost.unplanned_cost_treatment` (area `inventory`, regime and company option, core default `distribute_to_items`, changed only from a period start, in the shape of [ADR-0063](0063-configurable-policy-settings.md) rule 24) chooses: `distribute_to_items`, today's behavior, the cost posts to `purchase_cost_clearing` and is allocated to receipt lines by rules 4 to 6; `separate_account`, the line posts to its own account and never reaches stock or an allocation, as SAP's separate account debits no stock and no account assignment. Interim until step 5: the `separate_account` line is determined by the existing key `purchase_expense` (by item group, or the entered account), so no new transaction key is needed; a key of its own would need a row in every package. SAP's third choice, distributing together with the planned delivery costs, is not offered. Customs declarations (rule 11, `import_treatment`) and price differences sent to stock are not unplanned delivery costs and are not affected.
13. Products get `hs_code` and `country_of_origin` (ADR-0018, "deliberately elsewhere"). They are proposed on declaration lines. The code's length and format are country data. `hs` (Harmonized System) is added to the allowed abbreviations.

**Checks**

14. DS-16 invariants:
    - allocations sum to each cost line;
    - no source is allocated beyond its amount;
    - per source line, the `purchase_cost_clearing` balance equals its unallocated rest.

    A close task (ADR-0012) lists sources still unallocated at period end. `purchase_cost_clearing` is a liability in the system chart but carries a debit while costs wait; its presentation is DS-19's. TT99: 33882, under other payables, a debit balance under other receivables (interim, [ADR-0039](0039-vietnam-package-tt99.md) rule 8; DS-26).

    Note: DS-26 defines the report format, and DS-19's report definitions place the lines of 33882, so both statements hold ([ADR-0049](0049-statutory-reporting-and-printing.md) rule 22).

    Note ([ADR-0068](0068-sites-and-core-logistics-payment-master-data.md), 2026-11-21): `ListExpectedLandedCost` lists goods receipts whose purchase Incoterm leaves main carriage or insurance to the buyer and that have no `freight` or `insurance` cost line. The close task shows the list next to the unallocated sources, as information that blocks nothing.
15. DS-17 edge cases: landed cost after partial sale and after period close (existing); one declaration covering several receipts; customs assessed before the goods receipt.
16. Open questions for the author:
    - the earlier-unlocked case (rule 6);
    - the closed-period method and its alternatives (rule 8, extending the existing question);
    - import tax treatment and non-deductible import VAT (rule 11);
    - the value of a purchase return after landed cost was allocated to the receipt;
    - whether `landed_cost` is an internal, reversible document (rule 9).

    Note (the author, 2026-11-21): the first two questions (the earlier-unlocked case and the closed-period method) are answered by the rule 6 note of this date.

## Context

DS-11's ADR part is needed by ADR-0020 (receipt values and costing), DS-22 (purchase documents) and the step 3 gate. The logic is specified for step 3. Constraints:

- Customs declaration as its own document with its own customs rate. Duty and excise capitalized; import VAT to 33312 and 1331. Later costs allocated by value, quantity or weight. Same open period: added to the receipt value before costing. Earlier closed period: posted now and allocated by the quantity each consumer took ([08](../spec/08-l10n-vn.md#imports-and-purchase-costs), [05](../spec/05-accounting-inventory-core.md), [11](../spec/11-build-order.md)).
- Step 3 gets landed cost; customs declarations and purchase cost documents come at step 5 and emit only step 1 and step 3 commands (B3; [11](../spec/11-build-order.md)).
- Golden scenarios: landed cost after partial sale and after period close; a USD import with duty at a different rate ([12](../spec/12-testing.md)). Multi-currency and landed cost are in Phase 1 (D10).
- SAP practice (D5): planned and unplanned delivery costs and subsequent debits, with stock coverage. The material ledger distributes price differences to ending stock and consumption. Rule 7 applies that idea across locked periods without reopening them. ADR-0005: accounting choices are regime settings.

## Options considered

| Option | For | Against |
| --- | --- | --- |
| Closed-period split as the difference of two exact costing runs (chosen as interim seed) | Covers every movement type, transfers and period chains; order-independent; equals a naive recomputation | One costing rerun per item over locked periods |
| Fixed consumer list with quantity proportions | Simple to state | Misses scrap, counts and goods-sent sales; transfers need recursion; periodic average has no receipt identity |
| `stock_coverage` (SAP subsequent debit) | Simplest | Consumption share sits in price difference, not COGS; offered as a regime option |
| Fixed duty, excise and VAT columns on the declaration | Matches the Vietnamese form | Other import taxes need schema changes; country shape in the core |
| Reconvert cost lines at their own rate | Self-contained | Leaves residues on the clearing account |
| Rounding difference to the last line | Simple | Depends on line order |

## Constraints that come with the decision

- DS-04:
  - errors `allocation_basis_missing` (precondition), `allocation_manual_sum_mismatch`, `landed_cost_source_invalid`, `landed_cost_source_exceeded`, `landed_cost_target_invalid`, `landed_cost_period_mismatch`, `negative_stock_value`;
  - check result `customs_assessment_differs`.
- ADR-0020: value-only `receipt_addition` lines, the costing rerun used by rule 7.
- DS-16: invariants of rule 14. DS-17: edge cases of rule 15.
- DS-18: catalog and `inventory_value_role` checks.
- DS-19: `landed_cost.closed_period_method`; presentation of `purchase_cost_clearing` ([ADR-0039](0039-vietnam-package-tt99.md) rules 8, 9). `import_treatment` rules moved to DS-23 ([ADR-0039](0039-vietnam-package-tt99.md) rule 10).
- DS-22: cost invoices, GR/IR, price differences to stock through `landed_cost` in the invoice's batch.
- DS-23: tax codes for import taxes with `import_treatment`.
- Step 3 spec: rerun formula, layout of consumer lines, performance for many locked periods.

## Revisit when

- Planned delivery costs on purchase orders are needed (accruing freight at receipt).
- Customs declarations arrive electronically from the customs system.
- The rerun over locked periods is measurably slow for long histories.

## Documents updated

- [docs/adr/0018-product-and-item-model.md](0018-product-and-item-model.md), [docs/adr/0020-inventory-and-costing-model.md](0020-inventory-and-costing-model.md), [docs/adr/0015-account-determination.md](0015-account-determination.md) (rules 1, 4): links and notes.
- [docs/catalogs/transaction-keys.csv](../catalogs/transaction-keys.csv): meaning of `price_difference`.
- [docs/spec/00-reading-guide.md](../spec/00-reading-guide.md):
  - glossary rows for landed cost (updated), landed cost correction, customs declaration and amendment, landed cost line, target and allocation (with mode), allocation method, cost type, closed-period method, import treatment;
  - `hs` in the allowed abbreviations.
- [docs/design/DS-04-command-envelope.md](../design/DS-04-command-envelope.md): error and check result codes.
- [docs/design/backlog.md](../design/backlog.md): DS-11 row links here.
- [docs/adr/README.md](README.md): index row.
- [docs/open-questions.md](../open-questions.md): the questions of rule 16.
- [docs/runbook/step-log.md](../runbook/step-log.md): entry at acceptance.
