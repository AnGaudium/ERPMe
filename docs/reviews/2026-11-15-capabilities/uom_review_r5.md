# Review of ADR-0056 "Multiple units of measure", round 5 — verdict: NOT YET

0 blocking, 1 should-fix, 2 nits. Round-4 S1, S2, N1 and N2 are resolved and the arithmetic is sound. The one open item is the design consequence you asked me to check: the text does not yet say that a refused real receipt is a master-data problem, and the error does not guide the person. It is a wording fix in three places; no rule or DDL has to change. File:line refer to the round-5 review copy ("0056" = `adr/0056-multiple-units-of-measure.md`).

What I ran, on my own database `nativeflows_lab_ru`, dropping the schemas in separate statements before each load:
- `t17_uom.py --load`: 112/112. `t14`: 83/83. `t16 --load`: 99/99.
- `t01` 16/16, `t02` 6/6, `t03` 4/4, `t04` 5/5, `t05` 62/62, `t06` 60/60, `t07` 38/38, `t08` 46/46.
- `check_package.py` on tt99: PASS; self-test 28 of 28 caught.
- Cleanup done: database dropped, `/tmp/ru` and temp files deleted, repo untouched (`git status` clean).

## Should-fix

**S1. A refused real receipt is not named as a master-data problem, and `quantity_rounds_to_zero` does not guide the person (0056:102, rule 8; 0056:131, rule 10; `DS-04:210`; `0018` rule 11).**
- The rule itself is right: refusing a forward part that computes to zero or less is what stops the inflation. But it now refuses real goods. With bars kept in pieces and 1 m = 1/6 bar, a remnant of 2 m can never be received in metres, and it cannot be entered in pieces either (0.33 of a 0-decimal unit).
- Rule 10's remedy is "the person receives a larger quantity, or the line closes by inventory comparison". Neither helps the person holding 2 m. The real remedy is to keep stock in the finer unit. ADR-0018 rule 11 already says a company chooses as inventory unit the smallest unit it sells or counts, and rule 22 of this ADR gives the workaround (length as inventory unit, the piece as a `nominal` product unit), but rules 8 and 10 point to neither.
- The DS-04 row still reads "The quantity converted to the inventory unit rounds to zero (ADR-0018 rule 11)". For the new case that is untrue: in the 3/5-piece example the second receipt of 1 unit converts on its own to 1 piece, and is refused because the cumulative value is zero. An agent reading the catalog cannot tell why, or what to do.
- ADR-0018 rule 11 has no note that the error now also covers a forward part.
- Fix, all wording:
  - Rule 10 (and rule 8): say that a unit whose usual quantities fall below one inventory step is a master-data problem, with the pointer to ADR-0018 rule 11 and rule 22's workaround; keep "a larger quantity" only as the remedy for an occasional small part.
  - DS-04 row: cover both cases (the line's own conversion, or a forward part's cumulative value of zero or less), name `details` (the computed value, C and P, and the smallest entered quantity that would post), and give the two remedies.
  - A note on ADR-0018 rule 11 for the widened error, listed in rule 24.
  - Optionally a check result when a product unit is created whose one entered step is below half an inventory step, so the problem shows at master data and not at the dock.

## Nits

- **N1 (`invariants.csv:134`).** The generated INV-601 row starts in lower case and carries backticks, unlike its neighbours. Capitalise it and drop the backticks in the generator, or accept the style.
- **N2 (0056:131).** "Or the line closes by inventory comparison within T(S)": a completing part computes to zero or less only when P has already reached Q_S, so the line was fulfilled at the earlier posting and is already closed. Say that, so nobody reads the refusal as the closing event.

## Round-4 items verified

- **S1:** resolved. A forward part computing to zero or less is rejected; the clamp band applies to positive values only. U66 and U67 reproduce both of my examples: ten receipts of 1 unit post 1 piece once, and 2 m against whole bars is refused every time while 12 m post 2 bars. This is the variant I tested in round 4 on 52,942 adversarial sequences with no violation.
- **S2:** resolved. The INV-601 catalog row now equals the ADR's statement word for word.
- **N1:** resolved. The per-posting bounds are right: a return or credit changes the deviation by less than one unit plus two steps (stated as below three units), and a reversal or clamp by at most one unit plus one step. The growth is stated as accepted.
- **N2:** resolved ("strictly below two units").

## Also confirmed

- **Refusal and completion:** no conflict. A refused completing part never leaves a line open that should close (see N2), and the 2-unit database bound is unaffected.
- **Amendment discipline:** every amended ADR and the glossary change by added lines only.
- **Catalogs:** no duplicate invariant codes; DS-04's `part_quantity_clamped` row matches the new rule.
