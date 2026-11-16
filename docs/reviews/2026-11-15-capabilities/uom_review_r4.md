# Review of ADR-0056 "Multiple units of measure", round 4 — verdict: NOT YET

0 blocking, 2 should-fix, 2 nits. Round-3 S1, S2 and N1–N7 are resolved. The 2-unit bound is provable and held under adversarial runs. One should-fix is a new effect of the clamp's one-step floor; the other is a catalog row left behind. File:line refer to the round-4 review copy ("0056" = `adr/0056-multiple-units-of-measure.md`).

What I ran, on my own database `nativeflows_lab_ru`:
- `t17_uom.py --load`: 110/110. `t14`: 83/83. `t16 --load`: 99/99.
- `t01` 16/16, `t02` 6/6, `t03` 4/4, `t04` 5/5, `t05` 62/62, `t06` 60/60, `t07` 38/38, `t08` 46/46.
- `check_package.py` on tt99: PASS; self-test 28 of 28 caught.
- My own adversarial run: 52,811 sequences (below).
- No "out of shared memory" occurred. Cleanup done: database dropped, `/tmp/ru` and temp files deleted, repo untouched (`git status` clean).

## Should-fix

**S1. The clamp's floor of one step inflates stock with no return involved, and T grows with it, so no limit ever binds (0056:102, rule 8; 0056:130-131, rule 10).**
- Rule 10 introduces the floor for parts that compute to zero "after a return, credit or reversal". But a forward part also computes to zero with no return at all, whenever its own conversion is below one inventory step and the cumulative rounding does not move. Rule 8 now says the clamp wins over `quantity_rounds_to_zero` for every part against a source.
- Each such part posts one whole step. The clamp's change to the deviation is added to T(S) in the same posting, so `receipt_exceeds_order` and the other upper limits always pass.
- Example 1, unit of 3/5 piece (pieces at 0 decimals): an order of 10 units is 6 pieces. Ten receipts of 1 unit post 1 piece each: 10 pieces received against 6 ordered, T = 4, nothing refused. The line counts as fulfilled, and with one invoice of 10 units (I = 6) the rounding clearing posts the value of 4 pieces to price difference with no human step.
- Example 2, bars kept in pieces with 1 m = 1/6 bar: four receipts of 2 m post 4 bars against an exact 1.33. Eighteen such receipts post 18 bars against an order of 6.
- For inventory units with decimals the same happens at 0.001 per part, which is harmless; with 0 decimals a step is a whole piece.
- The band's other two edges are self-limiting (a part raised to q×f − 1 or cut to q×f + 1 always moves the deviation toward zero). Only the one-step floor is not.
- Fix: reject a forward part that computes to zero or less with `quantity_rounds_to_zero` (the person enters a larger part or the inventory unit), and keep the clamp only as the ±1 unit band for positive values. I tested this variant on 52,942 sequences: the forward bound (1 unit), the return bound (below 2 units), deviation ≤ T, completion within T and T = 0 for exact units all held, and both examples above stop inflating (ten receipts of 1 unit post 1 piece once and are then refused). Restate rules 8 and 10, `part_quantity_clamped` in DS-04, and add both examples to the lab.

**S2. The INV-601 row in `catalogs/invariants.csv` still describes the round-3 floor (`invariants.csv:134` against 0056:329).**
- The catalog says a forward part posted round((C + q) × f) − P "or one inventory step when that is not positive". Rule 25 of the ADR now says "clamped to between max(one step, q × f − 1) and q × f + 1", and adds the clause on how T(S) grew.
- DS-17 says the catalog is authoritative, so a harness built from it would report every clamped part as a violation.
- Fix: copy the ADR's INV-601 statement into the catalog row (after S1 is settled).

## Nits

- **N1 (0056:131).** T(S) is monotone but not bounded. A return that leaves a deviation, followed by a forward part that absorbs it, adds to T each cycle while the actual deviation is back at zero; on a 0-decimal inventory unit each cycle adds a piece. The invariants only need the current deviation. Either say the growth is accepted (it needs one posted return per step), or define the tolerance from the current |P − round(C × f)| plus the rounded other-unit parts.
- **N2 (0056:124).** The proof sentence is right but can be tighter: a share differs from its exact conversion by less than r/q of a unit plus one step, so strictly below two units even at 0 decimals. Say "strictly", since the check is `≤ 2d`.

## The three points you asked me to scrutinise

- **Is the 2-unit bound provable in general?** Yes.
  - A forward part is within one inventory unit of q × f by the clamp itself; the band is never empty, because its lower edge is at most one unit and its upper edge at least one unit.
  - A partial return takes round(v(r₀ + r)/q) − round(v r₀/q), which is v × r/q plus a rounding difference strictly below one step. Since |v − q × f| ≤ 1 unit and r ≤ q, the share is within 1 unit plus one step of r × f, so strictly below 2 units. The return that takes the rest is the same formula at r₀ + r = q.
  - A money return that follows its stock return has the same unit and quantity, so the same deviation. Parts in other units stay within half a step.
  - Adversarial run, 52,811 sequences: many one- or two-step parts followed by large partial returns, factors within a few thousandths of half a step, factors far below a step, and inventory units of 0 to 3 decimals. Worst forward deviation 1.000 unit, worst return deviation 1.59 units, no violation. The drafter's finding that clamping the shares would break exact sums is right.
- **Does the clamp conflict with completion or with money-follows-stock?**
  - Money-follows-stock: no conflict. The money line is not a forward part and is never clamped.
  - Completion: when the completing part is clamped, P differs from Q_S, but always within T(S), as rule 10 and INV-601 now state. No completion fell outside T in my runs. The one real conflict is S1: the floor makes P pass Q_S with no return, and T hides it.
- **Is T bounded and monotone?** Monotone, yes. The deviation never exceeded T, and T stayed zero for every exact unit (U65 and my runs). Bounded, no: see N1 and S1.

## Round-3 items verified

- **S1:** resolved. T(S) grows by the size of each change of the deviation and stays 0 for exact units (U65: 239 of 240 does not fulfil the line; 241 is refused).
- **S2:** resolved. Forward parts are clamped, shares are not, and all 20 `ck_*_uom_quantity` checks now use `≤ 2 × uom_denominator` (D44, D45; U22 with 0-decimal inventory units; U64).
- **N1–N7:** all done (zero share rejected with `quantity_rounds_to_zero`; precedence of clamp and rejection stated, which is what S1 now questions; `gr_ir_write_off` in the list; the foreign-currency entry; closed-short lines; the DS-04 parenthesis; T only grows).

## Also confirmed

- **Amendment discipline:** every amended ADR and the glossary change by added lines only.
- **No leftovers of `part_quantity_floored`** in the ADRs, DS-04, the glossary or the DDL; the only stale text is the INV-601 catalog row (S2).
