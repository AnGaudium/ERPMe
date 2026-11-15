# ADR-0060 "Agent-assisted reporting and analysis" — independent review, round 3 (2026-11-15)

Base: branch ds-uom, HEAD ec0c126. Draft applied by `drafts/ds-analysis/apply_analysis.py` (63 writes, 31 files).
Labs, each on a freshly recreated database: t18 `--load` 170/170, t12 187/187, t15 `--load` 146/146. Database dropped and copy deleted afterwards.
"Reproduced" means run against the lab's own `numeral_check`, `rendered_check`, `validate` and `compile_plan`.

## Verdict: NOT YET

1 blocking, 3 should-fix, 4 nits. Everything from round 2 except the narration is closed. A number can still be built in the explanation, and the cause is structural: the check is a blocklist around free prose, and each round finds the next gap.

## Blocking

**B1. Two values separated by a space, or by a harmless-looking word, still read as a new number.** (reproduced)
- Where: rule 23, "Isolated placeholders" and "The rendered text, again"; `t18` `numeral_check`, `rendered_check`.
- Passing both checks, with cells 12 and 500 of one row:
  - `{{m1}} had {{c1}} {{c2}} customers.` renders "Line 2 had 12 500 customers." The same passes with a no-break space and a narrow no-break space, which are the thousands separators of several locales.
  - `{{c1}} point {{c2}}` renders "12 point 500"; `{{c1}} to {{c2}}` and `{{c1}} – {{c2}}` (en dash) render a range; `{{c1}} E {{c2}}` passes.
  - `{{c1}} grand` and `{{c1}} squared` pass (scale and operator words not on the list).
  - `{{m1}} {{c1}} customers.` renders "Line 2 12 customers." when the member's label ends in a digit.
- Why the second pass misses it: it compares the multiset of digit runs before and after rendering, so two values side by side are still "two values".
- Fix, by construction rather than by a longer list:
  - At most one cell value per sentence. Pairs that belong together are rendered by code as one placeholder: `{{change:c5}}` ("from 12 to 500"), `{{range:…}}`, `{{share:…}}`.
  - The words directly before and after a cell placeholder come from a closed allowlist per language (was, were, is, of, at, reached, totalled and the like); anything else fails. A language without an allowlist fails closed, as for the number words.
  - A member placeholder and a cell placeholder are never neighbours without an allowlisted word between them.
  - The rendered pass checks positions, not counts: each rendered value has a letter word on both sides.
  - Add lab cases for every form above.

## Should-fix

**S1. Words that change what a value means still pass.** (reproduced)
- "more than {{c1}}", "under {{c1}}", "nearly {{c1}}", "{{c1}} customers each day", "{{c1}} customers on average", "{{c1}} dollars" on a count, "{{c6}} USD" after a value rendered in VND, "{{c1}} nil".
- "over" and "per" are already on the list, so the class is accepted; its other members are missing. No digit is invented, but the sentence states a different quantity.
- Fix: B1's allowlist of neighbour words closes this without further lists. If the blocklist stays, add comparators, approximators, rate words and unit and currency names.

**S2. A balance beside a second fact is not carried per bucket.** (reproduced)
- Where: rule 12, "Semi-additive measures over time"; the multi-fact path of `compile_plan`.
- `ledger_closing_balance` with `ledger_net_turnover` by posting period validates and compiles to the single as-of path (`DISTINCT ON`, then grouped by period). The rule says "whenever a plan groups a balance by its non-additive dimension"; the lab covers one fact only (by period, by period and branch, by fiscal year, with `exclude`, all correct).
- Fix: the per-bucket path applies inside each fact's aggregation of a multi-fact plan; add the lab case "closing balance and movement by period".

**S3. D2 may match another user's private saved analysis.**
- Where: rule 22 D1–D2 ("the company's verified saved analyses"), rule 26 (visibility `private`).
- A private analysis can be released and carry trigger questions. If D2 matches it for another asker, that asker receives its plan with the verified badge, which shows the private analysis exists and what it computes.
- Fix: D2 and the L1 hints use company-visible analyses and the asker's own private ones only; the uniqueness of trigger questions at release is checked within the same visibility set.

## Nits

1. "net revenue in March" without a year fails the stated-value check and abstains with period options. That is the precise choice; say in rule 22 that a month without a year is never completed by the model.
2. Rule 14, "Members without rows": a caller with company owner scope on a fact searches all master data behind the label view, without the master data's own permission. State that this is intended, or require that permission.
3. `{{c6}} USD` shows that a model can add a unit word. Rule 23 says code formats the unit; add that unit and currency names are not written by the model (covered by B1's allowlist).
4. In shadow, `UpdateAnalysisAnswer` simulates on an example subject, which has no question row; say what the simulate call writes to.

## Round-2 items

| Item | Status |
| --- | --- |
| B1 joined placeholders, scale letters | Touching placeholders, `k`, `mn`, `lakh`, `crore`, `minus`, `times` now fail; space-separated values and other words remain (B1 above) |
| S1 swaps in one sentence | Fixed: one row per sentence, all cited change cells must agree (reproduced) |
| S2 stated values | Fixed: named periods, number words and month names normalized; wrong year or unstated period refused; ends `ambiguous_term` (reproduced) |
| S3 grants format | Fixed: always a map; second note on ADR-0050 rule 48 replaces the list |
| S4 agent permission on facts | Fixed: the human's alone; note on ADR-0050 rule 31 |
| S5 member lookup | Fixed: no flag, no count, one empty answer; timing bounds stated |
| S6 carry-forward | Fixed for one fact (reproduced: `exclude`, branch by period, fiscal year); S2 above for two facts |
| S7 opening turnover | Fixed: `~opening` member, company scope only, lab case |
| S8 definition hash | Fixed: view declaration and selector expansion |
| S9 ambiguous member | Fixed: code decides; `clarify_member` |
| Nits | Applied: 14 calls with the arithmetic shown, verb `Update`, `Evaluate`/`Get` query names, private analyses on `general_access` with `share_saved_analysis`, feedback once, helper views declared, t12 registers the leaves |

## Confirmed sound in round 3

- Named periods resolve by code; an invalid month is refused; a named comparison validates.
- `CreateSavedAnalysis` and `UpdateSavedAnalysis` at `edit` on `general_access` fit ADR-0054 rule 8 (`master_data_change` needs `edit`); every template with `general_access` at `edit` can keep private analyses, and the auditor reads.
- `Evaluate` is the glossary verb for a computing query; t12 C10 accepts Get, List, Evaluate and Render.
- Notes now sit on ADR-0050 rules 14, 26, 28, 31 and 48 and on ADR-0051 rule 4, as rule 39 lists.
- No change to the round-1 and round-2 points confirmed earlier: one read-only statement, bound values, per-view scope, subtotals per pinned basis, closing and migration entries, DDL guards.
