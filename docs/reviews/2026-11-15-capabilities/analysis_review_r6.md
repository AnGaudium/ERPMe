# ADR-0060 "Agent-assisted reporting and analysis" — independent review, round 6 (2026-11-15)

Base: a `/tmp` copy of `base-integrated` (now with ADR-0058/0059). The draft applies cleanly (62 writes, 31 files).
"Reproduced" means run against the lab's own `validate_narrative`, `render_narrative`, `precondition` and `resolve_saved`, or by evaluating the DDL check expressions in PostgreSQL.

## Verdict: ACCEPT

0 blocking, 0 should-fix, 6 nits. All five round-5 findings are fixed and reproduce as refused or dropped. I found no new contradiction.

## Lab results

| Load | Scripts | Result |
| --- | --- | --- |
| `load_all.py`, fresh database each | t11 163/163, t12 190/190, t14 83/83, t15 146/146, t16 99/99, t17 117/117, t18 187/187, t19 177/177, t20 184/184, t21 93/93, t22 140/140, t23 102/102 | pass |
| Standard load, one session | t01 16/16, t02 6/6, t03 4/4, t04 5/5, t05 62/62, t06 60/60, t07 38/38, t08 46/46, t09 60/60, t10 69/69, t13 24/24 | pass |
| `check_package.py` | regime `tt99`: RESULT PASS | pass |
| Catalog CSV files | 15 files, every row has its header's field count; no duplicate code in the files this draft touches; 178 invariants match DS-16 | pass |

No "out of shared memory" occurred. Database dropped and the copy deleted afterwards. No git was run in `~/Projects/NativeFlows`.

## Round-5 items

| Item | Status | Evidence |
| --- | --- | --- |
| S1 one member of a two-dimension cell | Fixed | A step is `{claim, facts}`; a `members` field makes the plan invalid; the cell (Item group A, November 2026) renders "⟦Item group A⟧ in ⟦November 2026⟧ has the largest Net revenue [1]." (reproduced) |
| S2 direction pairs | Fixed | Different measures and the same fact twice are both dropped, each with its reason (reproduced) |
| S3 contribution claims | Fixed | With +80, +70, −100 and a total of +50: only A "explains most" and is the "largest contributor"; B is dropped; C is dropped as contributor and rendered as "largest offset". A zero total drops all three claims. A tie drops both. An other row that dominates its sign drops `most_of_change` (reproduced) |
| S4 saved references | Fixed | `max`, `total`, `total_change` and a full coordinate with `kind: change` resolve; `first_change`, a partial coordinate, a cell position and a role without a measure resolve to nothing and drop the step (reproduced) |
| S5 DDL check | Fixed | Both constraints refuse a free-text key, a numeric claim, an array for `facts`, a number or boolean leaf, a free-text key at depth, a free string leaf, an extra field, nine steps, a non-object step and a non-array value; they accept a model plan, a saved plan with a coordinate, and a connector (reproduced) |
| Nits | Applied | A connector renders only between two rendered sentences; `smallest_value` states complete results; the chip is named as the control; one member row drops `largest_value` |

## Nits

1. Pinned basis: when the pinned dimension is also a grouped member, the row renders it twice: "⟦USD⟧ in ⟦Customer P3⟧ within ⟦USD⟧". Leave the pinned member out of the "in" list. (reproduced)
2. `largest_value` and `smallest_value` need at least two member rows in the whole result; with a pinned basis the count should be within the pinned member, or a currency with one customer yields a true but empty sentence.
3. The DDL check accepts an array of identifiers as a leaf (`{"fact": ["a", "b"]}`). It cannot be rendered and holds no free text; refuse arrays below a step for tidiness.
4. No claim speaks of the total: `rose`, `fell` and `flat` need a member row, so "Net revenue rose" for a plan without dimensions cannot be said. The key fact already says it; consider `total_rose` and `total_fell` in a later catalog release.
5. Context (0060:467) still says "Placeholders and a numeral check make Principle 13 hold by construction." The decision now says the opposite; reword it to the survey finding only ("statistics produce the facts").
6. Rule 22 L3 still lists "member handles with their labels" as input. That is right as input for choosing; add that the output names none, to match rule 23.

## Confirmed sound

- No model string reaches the output: a free-text claim, a free-text role, an extra field or a handle that was not offered invalidates the plan; the rendered text is a function of the claim catalog, the cells and labels that code resolves.
- Every claim sentence is rendered only when its precondition holds on the served cells, and preconditions are checked again on every render of a saved plan.
- `flat` at a zero base is sound: the band is zero, so only an exact zero is "almost unchanged".
- Earlier rounds' points are unchanged: one read-only statement with bound values, per-view grants as a map, subtotals per pinned basis, closing and migration entries, per-bucket carry-forward, question text `personal`, exact-only matching, the definition hash in the badge, DDL guards.
- Open questions for the author are listed: question label, promotion below 30 examples, free prose after Phase 1, budgets and settings, the template seed.
