# ADR-0060 "Agent-assisted reporting and analysis" — independent review, round 2 (2026-11-15)

Base: branch ds-uom, HEAD ec0c126 (ADR-0056 accepted). Draft applied by `drafts/ds-analysis/apply_analysis.py` (58 writes, 31 files).
Labs, each on a freshly recreated database: t18 `--load` 148/148, t12 186/186, t15 `--load` 146/146. Database dropped and copy deleted afterwards.
References: `0060:N` is line N of the applied `docs/adr/0060-agent-assisted-reporting-and-analysis.md`; `t18:N` is `lab/t18_analysis.py`. "Reproduced" means run against the lab's own functions.

## Verdict: NOT YET

1 blocking, 9 should-fix, 9 nits. All six round-1 blockers are fixed. What remains is one way a number still enters the explanation, and gaps opened by the round-1 fixes themselves.

## Answers to the four questions

1. **Can a number still enter the explanation? Yes.** Adjacent placeholders and scale letters build numbers no cell holds (B1). Swaps inside one sentence still pass (S1).
2. **Per-view grants map against ADR-0050 rule 48 and ADR-0054 rule 15.** The map itself matches rule 15 (per assignment, per permission). Two contradictions remain: the setting now has two formats for the same views (S3), and an agent run has no declared permission on any fact view (S4).
3. **"Members occurring in the fact's in-scope rows".** The result itself leaks nothing. Whether the response carries `is_scope_filtered` or a count is not stated, and that flag would be an existence oracle for names; a timing residual exists and is not stated (S5).
4. **Carry-forward across special periods.** Correct for one dimension with `special_periods: include` (lab D25: October, November, special period zero after closing, USD key carried). Not correct or not defined for `exclude`, for a second grouped dimension, and unstated for the fiscal-year grain (S6).

## Blocking

**B1. Placeholders can be joined into numbers that no cell holds.** (reproduced)
- Where: 0060:267–271 (rule 23); t18:824–866.
- Problem: the checks look at the text between placeholders, not at what the rendered text says. With cells 3 and 5:
  - `{{m1}} had {{c1}}{{c2}} customers.` passes and renders "A had 35 customers."
  - `{{c1}}.{{c2}}` renders "3.5"; `{{c1}}/{{c2}}` renders "3/5".
  - `{{c1}}k`, `{{c1}} mn` and `{{c1}} K` pass, so a value is scaled a thousand or a million times.
  - `minus {{c1}}` and `{{c1}} times {{c1}}` pass.
- This breaks Principle 13 by construction, which is the claim the ADR makes for the placeholder design.
- Fix: a cell placeholder must be bounded on both sides by whitespace or sentence punctuation followed by whitespace, never by another placeholder, a letter, or `. , / - + × x *`. Add scale words and letters (`k`, `m`, `mn`, `bn`, `thousand` and the like, by language) and sign and operator words (`minus`, `negative`, `times`, `plus`, `over`, `per`) to the number-word classes. Run the numeral check a second time on the rendered text against the set of rendered cell values: every digit run in the rendered narration must be exactly one rendered placeholder. Add lab cases N-series for each form above.

## Should-fix

**S1. Swaps inside one sentence still pass.** (reproduced)
- Where: 0060:270–271.
- `{{m1}} had {{c2}} and {{m2}} had {{c1}}.` passes: both members are named somewhere in the sentence. `{{m1}} fell by {{c3}} while {{m2}} rose by {{c4}}.` passes with c3 positive and c4 negative: the rule asks only that some cited change cell agrees.
- Also passing: "halved" (the fraction class has no verb forms), "sixtieth".
- Fix: a sentence cites cells of one row only, or the total; a direction word needs every cited change cell of the sentence to agree, or the sentence uses `{{dir:…}}`. Add verb forms to the fraction class.

**S2. The stated-value check makes common questions fail, as a failure and not an abstention.** (reproduced)
- Where: 0060:132–133, 0060:259; t18:971.
- "net revenue in March 2026", "in 2025", "Q1 2026" and "the last three months" all fail the check: no relative range names a month, quarter or year, the absolute dates are not literally in the question, and number words are not normalized. The output is then invalid, and after rule 35's retries the run stops `output_invalid` and the question is `failed`.
- Fix: add named periods to the plan, resolved by code: `{"month": "2026-03"}`, `{"calendar_quarter": "2026-Q1"}`, `{"calendar_year": 2025}`, `{"fiscal_year": …}`, `{"fiscal_quarter": …}`. The stated-value check then applies to the year digits and, through the language's month and number-word lists, to the month and `n`. A plan that fails the check after repairs maps to `ambiguous_term` with period options (rule 24 already offers them), never to `output_invalid`.

**S3. `nativeflows.read_grants` has two formats for the same views.**
- Where: 0060:180; the new note on ADR-0050 rule 48.
- The earlier note on rule 48 makes it a list for a `List<View>` query. The new note makes it a map "for analysis plans". The fact views are also `List<View>` queries (ADR-0050 rule 46), and `open_item_overview`, `stock_overview` and `system_account_turnover` already exist. One view's `is_in_scope` cannot read both.
- Fix: the setting is always a map keyed by view name; a `List<View>` query sets a one-entry map. Say so in the note, replacing the list format for every view.

**S4. An agent run holds no permission on any fact view.**
- Where: 0060:150 (V4), 0060:240 (tool list), 0060:332.
- ADR-0050 rule 12's note says an agent type's declared permissions are its tool list, and rule 31 intersects them with the human's. The `analysis` tool list holds `RunAnalysisPlan` but no `List<fact view>`, so the intersection for "the fact view's `List` permission" is empty and V4 refuses every plan of an agent run. The per-view grants map has the same hole ("those of its human" is stated, the intersection is not).
- Fix: state that fact-view permissions and grants of an analysis run are the human's alone, the agent type's limit being `RunAnalysisPlan` on its tool list, with a note on ADR-0050 rule 31; or add the nine `List` queries to the tool list for workflow code only.

**S5. The member lookup's response and its residual are not pinned down.**
- Where: 0060:188.
- If `ListAnalysisDimensionMember` carries the standard `is_scope_filtered` of ADR-0050 rule 48 (one `EXISTS` over the same filters and `NOT is_in_scope`), a search text that returns nothing but sets the flag tells the caller that such a name exists outside their scope; prefix searches then enumerate names. A total count would do the same. The rule says neither way; the lab query returns neither.
- Timing: the query joins label matches to fact rows and then filters on scope, so its time grows with the matching rows outside the scope. This is a weak channel, but it is not stated.
- Fix: the lookup returns no `is_scope_filtered`, no count and no "more outside scope" hint; "no such member" and "outside scope" are one empty answer, as V12. State the timing residual with its bounds: a minimum search length, the page limit, and the run's lookup cap.

**S6. Carry-forward is incomplete beyond the tested case.** (reproduced)
- Where: 0060:127, 0060:175; t18:517, t18:583–598.
- `special_periods: exclude` on `ledger_closing_balance` validates and is ignored: the filter is added only for `journal_line_overview`. ADR-0049 rule 13 removes those entries from `closing` too, for the fiscal year ending on `to`.
- Closing balance by branch and posting period validates and compiles to the single as-of path (`DISTINCT ON`, then grouped by period), which is the round-1 error: no carry-forward per bucket. The per-bucket compiler runs only when `posting_period` is the sole dimension.
- The fiscal-year grain is not stated: its bucket end must be the last special period of the year.
- Fix: carry-forward applies for every plan that groups a balance by its non-additive dimension, with any other grouped dimensions as part of the key; `exclude` skips the special-period rows of the year ending on `to` and nothing else; the fiscal-year bucket ends after its special periods. Add lab cases for the three.

**S7. `opening_turnover` rows distort time buckets and have no scope rule.**
- Where: 0060:53.
- The rows are dated `opening_date`, so "net revenue by month" over a year with a mid-year cut-over puts all earlier months' turnover into the cut-over month. V14 refuses a range that cuts through a row, but a month grain cuts through it silently.
- `journal_line_overview` is owner-scoped through its document; these rows have none. Whether an actor with owner scope `own` sees them is unstated. The lab does not cover them.
- Fix: a time grain finer than the row's span shows these rows as their own member (`~opening`, labelled with its dates), outside the month buckets but inside the total; they are in scope only for grants with owner scope `branch` or `company`.

**S8. The definition hash misses what a measure reads.**
- Where: 0060:38, 0060:95, 0060:138; t18:117–122.
- The hash covers the declaration row. A changed view SQL (a sign, a join) or a changed subtree behind `system_account:revenue` (a new child in `system-accounts.csv`) changes the figure and leaves the hash, so the verified badge stays.
- Fix: a measure's definition hash also covers its fact's view declaration hash and, for a subtree selector, the hash of the subtree's codes.

**S9. `ambiguous_member` has no path in the planner's output.**
- Where: 0060:256–257, 0060:280.
- `AnalysisPlanOutput` has the kinds `plan`, `clarify`, `out_of_coverage`, `not_permitted`; `clarify` needs a catalog term. For agent runs personal labels are handles, so the model cannot judge "several members for one name" either.
- Fix: code decides: when a lookup for one search text returns more than one member and the plan would use one of them, the run ends `ambiguous_member` with that lookup's handles; add the kind `clarify_member` (lookup handle) for the model's own doubt.

## Nits

1. 0060:242: 1 + 3×(1+2) + 2 is already 12, so rule 35's schema retries are not inside the budget as the text says. A run that needs one ends `failed`; say so or raise the figure.
2. 0060:255: "badge `verified` only if its hash also equals the verified one after L2's checks" is unclear, since a `candidate` hit skips L2. Say that the badge is computed from the hash as always.
3. Verb `Set`: the glossary defines it as replacing a record's whole list of values. `SetAnalysisAnswer` and `SetAnalysisFeedback` set fields once; widen the glossary row or use another verb.
4. Pinned basis with only the pinned dimension grouped compiles to `GROUPING SETS ((g1), (g1))`: every member row appears again as a subtotal. Omit the subtotal there.
5. The line-dimension views behind the `EXISTS` filters (`<fact>_line_dimension`) and `posting_period_dimension` are used by the lab but not declared in rule 3 or the note on ADR-0050 rule 51; say they carry no scope and are joined only on keys of in-scope fact rows.
6. t12 learned the agent type only; the leaves `analysis_question` and `analysis_debug`, the capability `read_analysis_debug` and the new commands are not in its registry.
7. A builder user without `saved_analysis` (the sales clerk) can neither save an analysis nor open KPI tiles; state that or seed `read`.
8. `analysis_question_guard` lets feedback be cleared and then set again, so "once" does not hold for feedback.
9. A member with no rows in the fact (a new customer) cannot be found, so the answer is an abstention and not zero; state it.

## Round-1 items

| Item | Status |
| --- | --- |
| B1 closing, migration and special-period entries | Fixed: selectors, flags, INV-411 restated, EC-170, lab D05–D06 |
| B2 mixed currency and unit totals | Fixed: subtotals per pinned member, no grand total (reproduced); nit 4 |
| B3 scope per fact, member lookup | Fixed in substance; S3, S4, S5 remain |
| B4 fuzzy acceptance | Fixed: exact equality only, similar questions are hints |
| B5 `ck_agent_run_outcome` | Fixed in DS-05-platform.sql, lab completes each outcome |
| B6 question label | Fixed: `personal`, logged, `routing_blocked` with the switch on; L3 gets no question |
| S1–S3 narration checks | Largely fixed; B1 and S1 remain |
| S4 numbers through the plan | Fixed, but the fix causes S2 |
| S5 semi-additive buckets | Fixed for one dimension; S6 remains |
| S6 drill table, S7 field classes, S8 truncation, S9 cost guard, S10 cache keys | Fixed (S7 reproduced: refused without the class) |
| S11 badge and examples | Fixed: definition hashes, versioned examples with guard; S8 remains |
| S12 access to answers, S13 evaluation and promotion notes, S15 DDL checks, S16 imports, S18 names | Fixed |
| S14 budget | 12 calls as decided; nit 1 |
| S17 ambiguous member | Outcome added; S9 remains |
| Nits 1–13 | Applied |

## Confirmed sound in round 2

- Profit-and-loss measures exclude closing and migration entries; the lab's management totals equal the turnover over operational accounts with a closing entry, a special-period adjustment and a migration entry seeded.
- Two facts under two owner scopes stay apart in one statement; a view without a grant entry returns nothing.
- The balance drill (opening row plus lines) equals each bucket in the lab.
- DS-33: null-safe state checks, `failed` with its reason, the question and example guards, the deferred key for the verified version, indexes on foreign keys, erasure shape.
- Catalog and numbering: EC-150–155 and EC-170 use existing event types and bases; 142 invariants match DS-16; glossary rows no longer collide.
