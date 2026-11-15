# Review of ADR-0056 "Multiple units of measure", round 2 — verdict: NOT YET

0 blocking, 6 should-fix, 6 nits. B1 and S1–S9 of round 1 are resolved as designed; the should-fix items below are new, and four of them come from the round-1 fixes themselves. File:line refer to the round-2 review copy (`adr/0056-multiple-units-of-measure.md` = "0056").

What I ran, on my own database `erpme_lab_ru` with the standard load you described:
- `t17_uom.py --load`: 102/102.
- `t14`: 83/83. `t16 --load`: 99/99.
- `t01` 16/16, `t02` 6/6, `t03` 4/4, `t04` 5/5, `t05` 62/62, `t06` 60/60, `t07` 38/38, `t08` 46/46.
- `check_package.py` on `l10n_vn` / tt99: PASS, 15 of 15 unit names; `--self-test`: 28 of 28 broken copies caught.
- Cleanup done: database dropped, `/tmp/ru` and my temp files deleted, repo untouched (`git status` clean).

## Should-fix

**S1. A stock return and its money credit can now differ by one step in the same unit, and nothing clears it (0056:129-132, rule 10; `0047` rule 20).**
- Bag example: receipts 2.333 / 2.334 / 2.333, one invoice line of 3 bags (7.000). Return receipt 2: it mirrors 2.334, so R = 4.666. The supplier's credit of 1 bag on the invoice line applies the cumulative rule on that part: 7.000 − 4.667 = 2.333, so I = 4.667.
- R ≠ I by 0.001 kg, a 30 residual on GR/IR. T(S) is zero (it counts only parts in another unit), so the rounding clearing does not fire. The line falls to the closed-short path, whose remedy for I > R is a further supplier credit of 0.001 kg.
- Sales side, same numbers: delivered net 4.666 against invoiced net 4.667 leaves `sales_return_due` open for 0.001 kg.
- This did not exist in round 1 (returns re-ran the order-line rule, so R = I at equal C). It is the cost of the part-as-source fix.
- Fix, either:
  - a money-side return line that names a stock return line (`purchase_return_line.return_to_supplier_line_id`, `sales_return_line.return_from_customer_line_id`) in the same unit and entered quantity takes that stock line's inventory quantity; or
  - T(S), and with it the clearing and the limits, also counts one step per return or credit of a part in U.
- Add the case to U22 or a new check, and extend EC-130 to the credit.

**S2. The source line of a sales invoice is ambiguous, and one reading breaks the sum (0056:127).**
- Rule 10 says forward parts are "invoices of an order or delivery line". A stock sales invoice line carries both references.
- If S is the delivery line: three delivery lines of 2.333 / 2.334 / 2.333, each invoiced as 1 bag, post round(7/3) = 2.333 each. Invoiced 6.999 against delivered 7.000, so the order line never completes. Rule 10's Q_S = round(q_S × f) is also untrue when S is itself a part (delivery line 2 stores 2.334).
- Fix: state that for every invoice the source is the order line (C and P over the order line's invoices), with the delivery line as a reference only. Or state that a forward part completing a part-as-source takes the rest of its stored inventory quantity. Add a lab check for invoices of delivery lines.

**S3. `gr_ir_rounding_clearing` is declared but not carried through, and it collides with latest-only reversal (0056:132; `0047:177`, `0047:286`; `DS-22` posting-kind check).**
- ADR-0047 rule 13 lets a document be reversed only while its postings are the latest unreversed of their side. The clearing adds a posting on the lagging side. After it fires, the last invoice (or receipt) on that side is no longer latest, so `Reverse` fails with `reversal_not_latest`. The text does not say which side the clearing counts on, nor that it is undone.
- A return or credit after the clearing can take R or I out of tolerance; nothing says the clearing is reversed then, or that it fires again.
- Rule 25 calls it a document type, and `purchase_order_line_gr_ir_posting.document_id` requires a document. But there is no `authorization-areas.csv` row (`gr_ir_write_off` has one), no header or line table, and no DS-04 registration beyond the posting kind.
- Fix: state the side, state that the clearing never blocks a reversal and is reversed as a consequence when its line leaves tolerance or its side is reversed, and add the catalog row and DDL (or say which existing document carries the posting).

**S4. A forward part can compute to zero or below (0056:128).**
- With C and P as actual sums, P can sit a step above round(C × f) after a mirrored return or an out-of-order reversal. A small forward part then gives round((C + q) × f) − P ≤ 0 although q × f alone rounds above zero.
- I found this in 1,515 of 20,000 random sequences with a 1- or 2-decimal entered unit (for example f = 8/147, dE = 2, dI = 2). The line tables have `CHECK (inventory_quantity > 0)`, so the handler would hit a database error.
- U22 uses whole entered quantities only, so it does not see it.
- Fix: state the outcome (reject with `quantity_rounds_to_zero`, or post at least one step and let the next part correct), and add decimal entered quantities to U22.

**S5. The stated way out of `price_entry_starts_today` does not work (0056:65; the DS-04 row; `0045` rule 3 note).**
- The rule says the person "ends or removes it first". ADR-0045 rule 7's note forbids removing an entry whose start is on or before the business date, and end-dating it cannot go below its start, so it still starts today.
- The only real way out is to run the replacement on the next business date. The DS-04 text would send an agent into a loop.
- Fix: say so in rule 5, the ADR-0045 note and the DS-04 row. Or let the command end the entry on the business date and say which factor prices lines for the rest of that day.

**S6. Rule 2 misstates one conversion (0056:39).**
- "Hour to minute and day to hour are exact only toward the smaller unit." Hour to minute is not exact: hours hold 2 decimals, minutes 0, and 0.01 h is 0.6 min (60 × 10^0 is not divisible by 1 × 10^2).
- So hour and minute are inexact both ways, like day and minute. Day to hour is exact, as stated. `units.csv` and lab U17 only cover minute to hour.
- Fix: correct the sentence, and the HUR row's meaning in `units.csv`.

## Nits

- **N1 (0056:129-130).** "Reversals need no order of their own" relies on ADR-0009 rule 18: a part with a return cannot be reversed (`document_referenced`). That is the builder decision you named, but rule 10 does not say it; cite it there. The lab models it (`t17_uom.py:339`).
- **N2 (0056:66).** Packaging replacement names only rows that contain the replaced unit. Say it applies transitively (pack → carton → pallet).
- **N3 (0056:57, 80).** Retiring a `catalog` row leaves a level "with rows but none active", so rule 6 stops with `uom_retired` and the catalog unit is blocked for that product. Say whether that is intended.
- **N4 (0056:114).** A draft re-resolved at Post changes its inventory quantity after approval, and its unit price still belongs to the old pack. Say whether Submit re-resolves too, or that `uom_factor_changed` sends the document back.
- **N5 (`edge-cases.csv`).** EC-130 and EC-131 sit before EC-101 in the file. No duplicates; order only.
- **N6 (0056:133).** `part_quantity_recomputed` covers a pick task "that must change". Say what happens when the task is already confirmed at the provisional quantity.

## Builder decisions you asked me to scrutinise

- **The completing return takes the rest:** sound. No return exceeds its part in the lab's 600 sequences or in mine. It is the cause of S1, which needs its own fix.
- **A reversal only for a part with no returns:** sound, and already enforced by ADR-0009 rule 18; only the citation is missing (N1).
- **`product_uom.recorded_at` and the general INV-603 `line_factor_in_force`:** sound. It covers item-level superseding, which the round-1 statement missed.
- **The rounding clearing as a new GR/IR posting kind, firing when R and I are both within tolerance:** the trigger and the arithmetic are right (U51, D42); the gaps are in S3.
- **Unit-name length as a check result at save, with statutory outputs refusing:** sound, and core-neutral as a regime setting.

## Round-1 items verified

- **B1:** resolved. Returns, credits and reversals take the part they name; INV-601 is restated; U22 runs whole and partial returns and reversals in any order. The latest-only extension is gone; GR/IR keeps its own rule unchanged.
- **S1:** resolved. T(S) applies to the four upper limits and the closing check; EC-131 and the 8/3 example are right (8.001 within 0.003).
- **S2:** resolved in principle by the clearing; see new S3.
- **S3:** resolved. Parts are provisional on drafts and recomputed at Post under the source lock.
- **S4:** resolved (U52: earlier entries end-dated, later ones removed, scoped by level), except the remedy text in new S5.
- **S5:** resolved. Containing rows are replaced in the same command or it is refused; the review list now has bill of materials lines, partner items and defaults.
- **S6:** resolved. An item-level row over a used product-level unit is a replacement for that item.
- **S7:** resolved. Prices, defaults and the order unit take any resolved unit; a catalog-unit row takes only the catalog factor (`uom_conversion_conflict`). Notes on ADR-0018 rule 12 and ADR-0045 rule 3 are there.
- **S8:** resolved. `serial_unit_not_exact` covers product, item and catalog units; INV-604 is restated.
- **S9:** resolved. Core i18n holds plain names, the package holds statutory names (flagged as an open question); notes on ADR-0016, ADR-0019 and ADR-0053 are present.
- **N1–N9:** all done. Tonne and cubic metre now have 6 decimals, so mass, length and volume pairs are exact both ways (I rechecked each); `item_barcode` has a surrogate key; the fold table is ADR-0052 rule 17's; `check_package.py` fails on a missing unit name.

## Also confirmed

- **No Vietnamese law in core rules:** ADR-0056 and every core file it changes cite no decree, circular or statutory field. The legal question sits in `open-questions.md` as an `l10n_vn` package question, and the package setting is empty and `unverified`. Remaining Vietnamese mentions are labelled examples ("Thùng", VND in the worked example) and the core Vietnamese UI language, both allowed by ADR-0053 rule 1.
- **Amendment discipline:** all 18 amended ADRs and the glossary are changed by added lines only; no accepted line is removed.
- **Catalogs:** no duplicate invariant or edge-case codes; `master_data` is added to the DS-16 areas.
- **Public repo rule:** no customer information in the changes.

## Correction to my round-1 hand-off

I reported `uom_review_r1.md` as 125 lines; the file is 119 lines. Its content is the full review as delivered.
