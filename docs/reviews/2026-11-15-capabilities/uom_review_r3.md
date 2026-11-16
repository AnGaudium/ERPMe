# Review of ADR-0056 "Multiple units of measure", round 3 — verdict: NOT YET

0 blocking, 2 should-fix, 7 nits. All six round-2 items and the six nits are resolved. Both should-fix items are new and come from the round-3 backstop and share rules; each has a small, tested fix. File:line refer to the round-3 review copy ("0056" = `adr/0056-multiple-units-of-measure.md`).

What I ran, on my own database `nativeflows_lab_ru`:
- `t17_uom.py --load`: 106/106. `t14`: 83/83. `t16 --load`: 99/99.
- `t01` 16/16, `t02` 6/6, `t03` 4/4, `t04` 5/5, `t05` 62/62, `t06` 60/60, `t07` 38/38, `t08` 46/46.
- `check_package.py` on tt99: PASS; self-test 28 of 28 caught.
- My own random runs (below): 33,254 part sequences and 20,000 clearing sequences.
- Cleanup done: database dropped, `/tmp/ru` and temp files deleted, repo untouched (`git status` clean).

## Should-fix

**S1. The tolerance counts every return, credit and reversal, also for exact units, where one step is a whole piece (0056:131, rule 10; `0047` rule 20 note; glossary row).**
- T(S) now adds one smallest inventory step "for each return, credit or reversal of a part in U", with no condition. With an exact snapshot nothing ever rounds, so the deviation is always zero, yet T grows.
- Example with cartons of 24 (exact, pieces at 0 decimals): order 10 cartons = 240, receive 10, return 1 carton. T is now 1 piece.
  - A receipt of 23 pieces brings R to 239. The line is "within T(S) of Q_S", so it counts as fulfilled and closes one piece short.
  - A receipt of 25 pieces (241) passes `receipt_exceeds_order` with zero receipt tolerance.
  - With R = 239 and I = 240, both within T, `gr_ir_rounding_clearing` fires and posts the value of a whole piece to price difference with no human step.
- Three returns give three pieces. The same holds for any inexact unit on a 0-decimal inventory unit.
- Fix: count a return, credit or reversal only when it changed the deviation P − round(C × f). I tested that rule on 24,988 random sequences: the deviation never exceeded T, completion stayed within T, and T stayed zero for every exact unit. Restate rule 10, INV-601, the ADR-0047 rule 20 note and the glossary row, and add an exact-unit case to U22 (T must stay 0).

**S2. With a 0-decimal inventory unit, legitimate postings now break the database's gross-error check (0056:124, rule 9; the `ck_*_uom_quantity` checks; 0056:129-130).**
- Rule 9 says the bound `|inventory_quantity × d − quantity × n| ≤ d` (one whole inventory unit) is one "which every rounding and the cumulative rule satisfy". That held while P always equalled round(C × f). After a return it no longer does, and for pieces one step is one whole unit.
- Forward part, unit of 7/3 pieces with 1 decimal: receive 0.6 (posts 1); return 0.3 of it (share round(0.5) = 1); receive 1.2, which posts round(1.5 × 7/3) − 0 = 4 against an exact 2.8. The difference is 1.2 pieces, so the row is refused by `ck_goods_receipt_line_uom_quantity`.
- Return, unit of 25/72 pieces: parts of 7 (posts 2) and 18 (posts 7, exact 6.25); a partial return of 17 takes round(7 × 17/18) = 7 against an exact 5.90. The difference is 1.1 pieces, so the return line is refused.
- In my runs this occurred in 2,596 forward parts and 620 returns out of 33,254 sequences, all with a 0-decimal inventory unit. Lab U22 draws the inventory unit's decimals from 1, 2 and 3 only, and checks the bound on forward parts only, so it cannot see it.
- Fix, either:
  - widen the check to a bound these rules provably keep, and prove it in U22 with 0-decimal inventory units and returns; or
  - cap a part so that it stays within one inventory unit of its exact conversion (posting the capped value with a check result), which keeps the DDL as it is.
- Either way, correct the sentence in rule 9 and add 0 decimals and the return lines to U22's bound check.

## Nits

- **N1 (0056:129).** A partial return whose share rounds to zero is rejected in the lab (`t17_uom.py:354`), and you named it as a builder decision, but rule 10 does not say it. State it with its error code. It leaves a small entered rest on the part that can never be returned; say that is accepted.
- **N2 (0056:130 against 0056:102).** Say which wins when a forward part's own conversion rounds to zero: rule 8 rejects it (`quantity_rounds_to_zero`), the floor would post one step. The lab floors without checking.
- **N3 (0056:132, "Re-evaluated").** The list of later postings (receipt, invoice, return, credit, reversal) omits `gr_ir_write_off`. Add it.
- **N4 (0056:132; `0047` rule 13, foreign currency).** ADR-0047's interim rule clears the company-currency residual at "the posting that makes R = I". Say whether the clearing counts as that posting, and that reversing it reverses that entry too.
- **N5 (0056:132).** The clearing needs R and I both within T of Q_S. A line closed short whose R and I differ by a step (a credit that could not follow its stock return, for example a split credit) still goes to the human path. Either accept that in words or let the clearing also run when a closed line has |R − I| ≤ T.
- **N6 (DS-04, `reversal_not_latest` row).** The added text has an unbalanced parenthesis.
- **N7 (0056:131).** Say that T(S) only grows: a reversed part that was counted stays counted.

## Builder decisions you asked me to scrutinise

- **Partial returns take a cumulative share of the stored quantity:** sound. In 33,254 sequences no share was negative, no return exceeded its part, and the returns of a part summed exactly to its stored quantity. Its only side effects are N1 and the return half of S2.
- **The backstop also counts reversals and floored parts:** the arithmetic holds (the deviation never exceeded T and completion was always within T), but the unconditional count is too wide (S1).
- **The clearing fires only when R and I are both within T:** right for fulfilled lines; N5 is the one gap.
- **Reverse-then-re-fire at every later posting:** sound. In 20,000 sequences with two price layers (35,999 clearings fired, 31,755 reversed) the GR/IR balance always equalled round(V(I)) − round(V(R)) after a reversal and was zero after every clearing. It never blocks a reversal because it never counts as latest.

## Round-2 items verified

- **S1:** resolved. A money return naming its stock return line in the same unit and quantity takes that line's quantity (U60: R = I = 4.666, GR/IR zero; sales side closes `sales_return_due`). EC-130 now includes the credit.
- **S2:** resolved. An invoice's source is always the order line (U61: 2.333 / 2.334 / 2.333 reach 7.000).
- **S3:** resolved. The clearing has its side, never counts as latest, is reversed and re-fired, and has a document row, an `authorization-areas.csv` row, a DS-22 comment and DS-04 check results (U62, D42).
- **S4:** resolved. A part computing to zero or less posts one step with `part_quantity_floored`; U22 uses decimal entered units.
- **S5:** resolved in rule 5, the ADR-0045 note and the DS-04 row: run the replacement on the next business date.
- **S6:** resolved. Only day to hour is exact; the HUR row in `units.csv` is corrected.
- **N1–N6:** all done (ADR-0009 rule 18 cited; transitive packaging; retiring a catalog row stated as intended; Submit and Post re-resolve and the document returns to draft; the edge-case file is sorted; confirmed pick tasks get a follow-up task).

## Also confirmed

- **Amendment discipline:** every amended ADR and the glossary change by added lines only.
- **Catalogs:** no duplicate invariant, edge-case or authorization codes.
- **No Vietnamese law in core rules,** and no customer information in the changes: unchanged from round 2.
