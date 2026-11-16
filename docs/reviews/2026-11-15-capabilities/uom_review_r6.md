# Review of ADR-0056 "Multiple units of measure", round 6 — verdict: ACCEPT

0 blocking, 0 should-fix, 2 nits. The round-5 should-fix and both nits are resolved, and I found nothing new that blocks. The two nits below can be taken at acceptance or left. File:line refer to the round-6 review copy ("0056" = `adr/0056-multiple-units-of-measure.md`).

What I ran, on my own database `nativeflows_lab_ru`, dropping the schemas in separate statements before each load:
- `t17_uom.py --load`: 114/114. `t14`: 83/83. `t16 --load`: 99/99.
- `t01` 16/16, `t02` 6/6, `t03` 4/4, `t04` 5/5, `t05` 62/62, `t06` 60/60, `t07` 38/38, `t08` 46/46.
- `check_package.py` on tt99: PASS; self-test 28 of 28 caught.
- Cleanup done: database dropped, `/tmp/ru` and temp files deleted, repo untouched (`git status` clean).

## Round-5 items verified

- **S1:** resolved in all four places.
  - Rules 8 and 10 name the master-data problem and both remedies: stock in the finer unit (ADR-0018 rule 11 and rule 22's workaround), or a larger quantity for an occasional small part.
  - The DS-04 `quantity_rounds_to_zero` row covers both cases (the line's own conversion, or a forward part's cumulative value), names `details` including `smallest_postable_quantity`, and gives the remedies.
  - The ADR-0018 rule 11 note carries the widened error, and rule 24 lists it.
  - The new check result `unit_step_below_inventory_step` is in rule 7, rule 20, rule 25 and DS-04.
  - I rechecked the two stated smallest quantities: 3 m for bars at 1/6 (round(0.5) = 1), and 2 units after the first 3/5-piece receipt (round(1.8) − 1 = 1). Both are right (U68).
- **N1:** resolved. The INV-601 catalog row starts with a capital and has no backticks; its wording still equals the ADR's.
- **N2:** resolved. Rule 10 states that refusing a completing part is not a closing event.

## Nits

- **N1 (0056:95, rule 7).** The warning fires when one entered step is below half an inventory step. The ADR's own first example, the unit of 3/5 piece, is not flagged (0.6 is above 0.5; U69 confirms it), although its single-unit receipts are refused every second time. Either widen the threshold to "below one inventory step", or say that the warning covers only units whose smallest quantity rounds to zero on its own.
- **N2 (0056:95; U69).** The warning is raised by `CreateProductUom`. A catalog unit used without a product row (U69's minutes on a product kept in days) has no creation step, so nobody sees the warning. Say where it surfaces for catalog units (for example in `GetItemUnits`), or that it does not.

## Standing confirmations

- **Arithmetic:** the cumulative rule, part-as-source returns with exact shares, money-follows-stock, the clamp band for positive values, the 2-unit database bound (provable, and held on 52,811 adversarial sequences in round 4), the tolerance T(S) (zero for exact units, never below the deviation), and the GR/IR rounding clearing with reverse-and-re-fire (20,000 sequences in round 3) are all unchanged since I verified them.
- **Amendment discipline:** every amended ADR and the glossary change by added lines only.
- **Catalogs:** no duplicate invariant codes; DS-04 has both new rows.
- **Core neutrality and the public repo rule:** no Vietnamese law in core rules and no customer information, unchanged.
