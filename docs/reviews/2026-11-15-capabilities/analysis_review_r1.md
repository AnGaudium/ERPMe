# ADR-0060 "Agent-assisted reporting and analysis" — independent review, round 1 (2026-11-15)

Base: branch holistic-review, HEAD 32e7b1c, draft applied by `drafts/ds-analysis/apply_analysis.py` (48 writes, 29 files).
Labs on a throwaway database: t18 `--load` 101/101, t12 186/186, t15 `--load` 146/146. Database dropped and copy deleted afterwards.
File references: `0060:N` is line N of `docs/adr/0060-agent-assisted-reporting-and-analysis.md` as applied; `DS-33:N` is `docs/design/DS-33-analysis.sql`; `t18:N` is `lab/t18_analysis.py`.

## Verdict: NOT YET

6 blocking, 18 should-fix, 13 nits. The architecture (declared catalog, JSON plan, one compiled SELECT, placeholders) is sound and the labs pass, but the labs do not exercise the cases below. Several findings were reproduced against the lab's own validator and compiler (marked "reproduced").

## Blocking

**B1. Ledger profit-and-loss measures and INV-411 ignore closing entries, migration entries and special periods.**
- Where: 0060:66 (`net_revenue`), 0060:313, 0060:330 (INV-411); `analysis-measures.csv` rows 2–10; `invariants.csv` INV-411; EC-155.
- Problem: `net_revenue`, `revenue_deduction`, `cost_of_goods_sold`, `gross_profit`, `gross_margin_percent` and `operating_expense` sum every journal line of the subtree. ADR-0012 rule 18 lets a regime close profit and loss by entries (`is_closing_entry`), and ADR-0049 rule 7 has `closing_entries=exclude` precisely "so the closing to the income summary does not cancel them". With such a regime, net revenue over any range that contains the closing entry is zero. ADR-0049 rule 6 also keeps migration-year entries out of turnover and rule 13 treats special periods; the `ledger_*_turnover` measures include both. INV-411 defines the measure as the plain journal sum and then claims "with INV-401 the statutory figure agrees, in every regime": the statutory income line excludes closing entries, so the two differ. The lab seed (D05) has no closing entry, so it passes.
- Fix: expose `is_closing_entry`, the migration-year flag and the special-period flag on `journal_line_overview`; give the profit-and-loss measures the selector `closing_entries:exclude` and the turnover measures the same turnover definition as ADR-0049 rule 6; restate INV-411 as equality with ADR-0049's turnover measure with `closing_entries=exclude` (statement-line level stays out of the claim, since lines may split by side or partner); add a lab case and an edge case with a closing entry and a special-period entry.

**B2. Total rows, other rows and shares add up different currencies and units when the basis is pinned by grouping.** (reproduced)
- Where: 0060:146–147 (V7, V8), 0060:164 (shape); t18:531.
- Problem: V7 and V8 are satisfied by grouping on `currency` or `product`. The compiler then emits `GROUPING SETS ((g1), ())`, so `sales_line_amount` by currency with `with_total_row` returns a total of VND plus USD, and `sales_quantity` by product with the other row and total sums quantities of different inventory units. `share_of_total` on these measures divides by the same mixed total. The validator returned no violation for all three plans. The lab's own plan P2 (t18:1175) asks for `with_total_row` on currency by partner and never checks the total row. This breaks decision 2 (no sum across currencies without a stated basis).
- Fix: when the basis is pinned by a grouped dimension, totals, other rows, shares and ranks are computed per member of that dimension (partition by it) and the grand total is omitted; when pinned by a filter nothing changes. Add V-checks, INV-412 wording and lab checks on the total row.

**B3. Scope per fact is not defined for the compiled statement, and member lookup has no permission of its own.**
- Where: 0060:169 (scope), 0060:176–178 (lookup, permissions), 0060:143 (V4).
- Problem (a): ADR-0050 rule 48's note sets one `nativeflows.read_grants` per query from "the assignments that grant the query's permission", and ADR-0054 rule 15 evaluates scope per assignment per permission. `RunAnalysisPlan` sits on `general_access`, and one statement may read several fact views whose permissions come from different assignments with different record and owner scopes. The ADR only says "the builder sets the session settings of rule 48". With one grant list, either the union applies (a grant for the sales view widens the journal view: scope escape) or `general_access`'s grants apply (wrong scope for every fact). The lab says owner scope is not covered ("branch scope stands in").
- Problem (b): `ListAnalysisDimensionMember` reads a label view, not a fact, so "checks the permission of every fact view it reads" checks nothing. Any holder of `general_access` can enumerate partners, salespersons (employees, personal labels returned to people), accounts, projects and production orders by search text.
- Fix: state that grants are computed per fact view from the assignments granting that view's `List` permission, carried as a map keyed by view, and that each view's `is_in_scope` reads its own entry; add a lab case with two facts and two different owner scopes. For the lookup: require the `List` permission of at least one fact offering the dimension (or of the master-data view behind the label view) and return only members within that view's scope.

**B4. D2's fuzzy acceptance returns a verified plan, with the verified badge, for a different question.**
- Where: 0060:224 (D2), 0060:214 (constants); t18:717.
- Problem: `rank_candidates` is rapidfuzz token-set ratio (ADR-0051 rule 1). Token-set ratio is 100 whenever one question's tokens are a subset of the other's: "net revenue last month by customer" against the verified "net revenue last month" scores 100 and, with no close second, is accepted without a model. The answer carries badge `verified` and omits the breakdown that was asked. Single-token swaps (`this`/`last`, a year) score in the 90s. For a design "tuned for precision" this is a wrong answer by construction, and it is the path that claims the highest trust.
- Fix: D2 accepts only exact equality of normalized questions. Fuzzy candidates always go to L1 as candidates (the `candidate` kind already exists). Drop the 92/8 constants from the analysis agent type.

**B5. The accepted DDL refuses every analysis outcome.** (reproduced)
- Where: 0060:249 ("extend ADR-0050 rule 17's table"); `DS-05-platform.sql:201–206` (`ck_agent_run_outcome`), not touched by the draft.
- Problem: for state `completed` the check allows only `drafted`, `no_action`, `not_applicable`, `routing_blocked`. `answered`, `ambiguous_term`, `out_of_coverage`, `not_permitted`, `data_not_ready` and `too_broad` are rejected, so no analysis run can complete in the loaded schema. t18 never writes an `agent_run` with these outcomes.
- Fix: amend the check in DS-05-platform.sql with the six outcomes (and say so in "Documents updated"), and add a t18 check that completes a run with each outcome.

**B6. Question text labelled `internal` defeats the routing switch and the processing log.**
- Where: 0060:221, DS-33:14, `open-questions.md` (new first item).
- Problem: a question can name a person ("what does Nguyen Van A owe us"). Labelled `internal`, the name goes to the cloud seat with the switch on, and ADR-0050 rule 10's processing log, which spec 17 requires "always on", records nothing because it logs only personal-labelled values. ADR-0050 rule 9 already set the precedent for this exact doubt: bank descriptions are `personal` "because a payer may be a person". The draft takes the opposite, less safe reading as its interim and only flags it. The same applies to `analysis_example.question_text`, trigger questions and `feedback_note`.
- Fix: interim label `personal`. With the switch off the question is sent and logged; with the switch on the required input is removed and the run ends `routing_blocked`, while D2 exact matches, saved analyses and the builder keep working without a model. Keep the open question for the author, with `internal` as the alternative rather than the interim.

## Should-fix

**S1. The numeral check lets number words through.** (reproduced)
- Where: 0060:235; t18:634–660.
- Problem: the list is matched as exact tokens. "several millions", "doubling", "a tenfold rise", "the first quarter", "a third of sales", "both branches", "hundreds", "thousands" and ASCII "XII" all pass. Ordinal words are absent although the rule says ordinals come only from placeholders. Nothing says what happens when the output language has no list.
- Fix: define the list by class (cardinals, ordinals, fractions, multiplicatives, magnitude nouns, with plurals and inflections, the suffix `-fold`, ASCII Roman numerals as standalone tokens); match on stems; fail closed (table only) when no list exists for the language.

**S2. Directions and superlatives are not enforced.** (reproduced)
- Where: 0060:233, 0060:235 ("Ordinals and directions come only from placeholders").
- Problem: "Revenue fell sharply to {{c1}}, the lowest ever" passes, whatever the cell says. `{{dir:cN}}` is also accepted on a cell that is not a change.
- Fix: add a direction and superlative word list per language to the check (rose, fell, grew, higher, lower, largest, smallest and the like), add placeholders for the facts of D5 (`{{max:…}}`, `{{min:…}}`), and require `dir` to name a difference, growth or contribution cell.

**S3. A placeholder may bind the right number to the wrong statement.**
- Where: 0060:230, 0060:234.
- Problem: the check only proves that `{{c7}}` exists. "Revenue in November was {{c7}}" passes when c7 is October. The number is from code; the sentence is false.
- Fix: a co-reference check: a sentence with a cell placeholder must also hold the member placeholders of that cell's row for every grouped dimension (or the cell is in the total row); otherwise the retry and then the table alone. State the residual risk in the ADR.

**S4. Numbers and dates still enter through the plan.**
- Where: 0060:120, 0060:125–126 ("A model never computes a date"), 0060:262 (agent drafts).
- Problem: L2 may emit absolute `from`/`to` dates, `n`, `limit` and `top`. The relative vocabulary lacks `last_n_months`, `last_n_weeks`, `this_week`, `last_week`, calendar years and rolling twelve months, so "the last six months" forces the model to compute dates. Agent-drafted KPIs would carry `target_value` and thresholds from a model. `term` (clarification) and the `not_analysis` note are unchecked model text.
- Fix: add the missing relative ranges; apply ADR-0050 rule 36's stated-value check to every literal date and number in an L2 plan (it must appear in the question after normalization); agent drafts are of kind `analysis` only, or KPI numbers must be stated in the question; `term` must be a span of the question; the note is a code template.

**S5. Semi-additive measures over time buckets are unspecified, and the lab compiler fails on them.** (reproduced)
- Where: 0060:57, 0060:164; t18:514–517.
- Problem: "closing balance of the revenue subtree by posting period" validates and then raises `KeyError` in the lab compiler. The implemented path takes one latest row per key, which is right for a single as-of and wrong per bucket: ADR-0014 rule 18 writes no row for a period without movement, so a bucket needs the latest row at or before its own end. Separately, the open-item and stock measures are tagged `semi_additive` with default time `due_date`; over due date they are plainly additive.
- Fix: each semi-additive measure names its non-additive dimension (the snapshot or `posting_period`); specify per-bucket carry-forward for `ledger_closing_balance` and test it in the lab; say that snapshot measures sum over their attribute dates.

**S6. The drill invariant covers only additive and distinct-count cells.**
- Where: 0060:13, 0060:186–188, 0060:329 (INV-410).
- Problem: decision 4 and the summary say every cell equals its drill rows. Nothing defines the rows behind a ratio, a `difference` measure (`gross_profit`), `growth`, `share_of_total`, a contribution row, or a closing balance (journal lines since the cut-over plus opening documents; locked periods come from `account_period_balance`). For agent runs, drill rows are individual document rows, which ADR-0050 rules 25 and 28 treat differently from aggregates; a clean agent type gets tainted rows filtered, which would break the sum.
- Fix: define per kind: ratio drills to its numerator and denominator cells; difference to the signed union; derived cells to their operand cells; closing balance to an opening row plus lines, as ADR-0049's books. Extend INV-410 to those. Declare `ListAnalysisCellRow` a numeric projection (ADR-0050 rule 28) for agent runs.

**S7. Ledger cost and margin by item bypass the field classes.** (reproduced)
- Where: `analysis-measures.csv` rows 4–6; 0060:313.
- Problem: an actor without `cost` and `margin` may run `cost_of_goods_sold`, `gross_profit` and `gross_margin_percent` by item, product, partner or salesperson; with `sales_quantity` that is unit cost and margin per item and customer, which `document_line_overview` and `sales_cost`/`sales_margin` protect.
- Fix: class `cost` on `cost_of_goods_sold` and `margin` on `gross_profit` and `gross_margin_percent` whenever the plan groups or filters by a dimension below branch and account level (item, product, item group, partner, partner group, salesperson, warehouse, document type), or always; state the choice against ADR-0049 rule 17.

**S8. A limit without the other row truncates silently.**
- Where: 0060:123, 0060:180, 0060:229 (D5).
- Problem: rows beyond `limit` vanish; the envelope has only a row count. D5 would then mark the "smallest" member among the rows returned.
- Fix: an `is_truncated` flag and check result `analysis_rows_truncated`; D5 offers smallest and rank facts only on complete results.

**S9. The cost ceiling reads the wrong figure, and the estimate is returned to callers.**
- Where: 0060:152 (V13), 0060:174; t18:1239.
- Problem: the lab reads the top node's `Plan Rows`, which is the number of output groups (2 in D20), so `analysis_max_estimated_rows` of 5,000,000 can never trip. `ExplainAnalysisPlan` returns the planner's estimate to every caller, agents included; planner statistics are table-wide, so date-range estimates hint at volumes beyond the caller's scope and company.
- Fix: define the figure as the sum of scan-node rows or total cost; return only "within limit" or the limit that tripped, never the raw estimate.

**S10. The result cache key omits company and user in the text.**
- Where: 0060:285; decision 7; t18:756.
- Problem: rule 30 keys the result cache by `resolved_hash` and the scope fingerprint. A plan without entity filters has the same `resolved_hash` in every company, and two clerks with equal grants and owner scope `own` have different rows. The lab includes company and user; the rule does not.
- Fix: write company and user into both cache keys.

**S11. The verified badge outlives what was verified.**
- Where: 0060:88–90, 0060:131, 0060:264, 0060:267–268; DS-33:128–157.
- Problems: (a) `plan_hash` excludes the catalog, so a release that changes a measure's expression changes every verified KPI silently, still badged `verified`. (b) `UpdateAnalysisExample` may change a verified example's plan in place: no versions, no guard, and INV-414 cannot be checked afterwards. (c) Rule 26's badge bullet names saved analysis versions only, INV-414 and the DDL also examples. (d) A trigger question of a saved analysis may equal an example's question; D2 has no precedence.
- Fix: certified measure definitions are immutable (a change is a new code), or the badge compares a per-measure definition hash stored on the version; a guard trigger freezes question, plan and expected outcome of a verified example (an update returns it to `draft`); align rule 26 with INV-414; release refuses a question already live elsewhere.

**S12. Stored answers and the question commands have no access rules.**
- Where: 0060:217–220, 0060:338–339; DS-33:36; `authorization-areas.csv`.
- Problems: `analysis_question.result` stores cells computed under the asker's scope and field classes. The dispute item goes to `company_owner` and may be reassigned; whoever reads the row sees those figures. The result's data label, field classes and erasure are unstated (member labels of individuals inside JSON would escape `EraseDataSubject`). `CreateAnalysisQuestion`, `RecordAnalysisFeedback`, `RecordAnalysisAnswer`, `GetAnalysisQuestion`, `ListSavedAnalysis`, `GetSavedAnalysis` and `ListAnalysisExample` have no leaf. `CreateAnalysisQuestion` is "a person's command" but not `human_only`, although the untainted status rests on a person having typed the text. Whether saved analyses are private or shared is unstated.
- Fix: the row is readable by its asker only; a reviewer reruns the plan under their own rights; the stored result holds member keys, never labels; give every command and query a leaf and level in rule 36 and the catalog; register `CreateAnalysisQuestion` as `human_only`.

**S13. Evaluation, failure and promotion mechanics are incomplete.**
- Where: 0060:252–253, 0060:219; ADR-0050 rule 14; ADR-0051 rule 4.
- Problems: `RunAnalysisEvaluation` starts runs "on the company's verified examples", but the agent type accepts only `analysis_question` subjects and the human acted for (scope, field classes) is not named. Nobody sets a question to `failed` when a run stops (`budget_exceeded`, `output_invalid`, `crashed`); `agents` cannot write `query`'s table. The promotion exception amends ADR-0050 rule 14 and ADR-0051 rule 4, which get no note (the note sits on ADR-0051 rule 7). Below 30 examples promotion rests on the synthetic CI report alone, against ADR-0051 rule 4's own reasoning, and this is not in the open questions.
- Fix: accept `analysis_example` as a subject (or let the job create flagged questions) and act for the example's releaser; a consumer of `AgentRunCompleted` in `query` closes the question; add notes at both amended rules; flag the below-30 rule for the author.

**S14. The run budget cannot cover the run it describes.**
- Where: 0060:213–214, 0060:287.
- Problem: one route, three plan attempts and two explanations are already 6 LLM calls. Each member lookup in L2 is a further gateway round trip (ADR-0050 rule 2, `stop_reason: tool_use`), and rule 35's schema retries count too. A normal question with one lookup and one repair ends `budget_exceeded`, which raises `agent_run_stopped`.
- Fix: set `max_llm_calls` from the worst case (for example 14) or cap lookups per attempt and say so; map `budget_exceeded` of this agent type to the question state `failed` without an owner work item per question.

**S15. Checks in DS-33-analysis.sql.** (reproduced by evaluating the expressions)
- DS-33:46: a `failed` question must have an outcome, but no outcome value means failed, so a failed run cannot be recorded truthfully. Fix: `(state IN ('open','failed')) = (outcome IS NULL)`, and tie `abstained` to the abstention outcomes.
- DS-33:51: `outcome = 'answered' OR (badge IS NULL AND …)` yields NULL for an open question, so an open row with a badge and result passes. Fix: `outcome IS NOT DISTINCT FROM 'answered' OR (…)`.
- No guard freezes the answer columns after `RecordAnalysisAnswer` ("once" is command-only); add a trigger like the version guard, leaving feedback writable.
- DS-33:71–72: `verified_version` and `latest_version` have no key to `saved_analysis_version (company_id, saved_analysis_id, version)`; add a deferrable composite key.

**S16. Layering statement is wrong for work items.**
- Where: 0060:28, note on ADR-0022 rule 2, note on ADR-0050 rule 1; `work-item-kinds.csv`.
- Problem: `query` raises `analysis_answer_disputed` and `analysis_catalog_request`, which needs `work.contract` (ADR-0042 rule 5). "Its imports do not change" is false.
- Fix: add `work` to `query`'s imports in the rule and both notes. Also add `production_order_variance` to the DS-43-54 draft or the DS-54 backlog row, and update the backlog rows of DS-34 and DS-30.

**S17. No outcome for an ambiguous member.**
- Where: 0060:226, 0060:243.
- Problem: two customers match a name, personal labels are handles, and clarification options are catalog codes only. The planner must guess; a wrong customer is a wrong answer.
- Fix: `ambiguous_term` options may be member handles of one lookup, rendered by code for the person.

**S18. Text and naming errors.**
- 0060:68: `sales_margin_percent` is written as a ratio to `sales_line_amount` (transaction currency); the catalog says `sales_net_amount`. Fix the ADR table.
- `plan` and `plan_hash` already mean the command plan and its hash (ADR-0008 rule 12; glossary rows "Plan", "Expected plan hash"). Rename to `analysis_plan_hash` (column, envelope, glossary) so one name has one meaning for agents.
- Glossary: the new row "Measure" duplicates the existing "Measure" of ADR-0049. Rename to "Measure (analysis)".

## Nits

1. `analysis-dimensions.csv`: `system_account` is kind `entity` though its members are codes; `currency` is `enum` without a closed list. Rule 5 defines neither case.
2. 0060:247: `time_range_invalid` maps to `too_broad` ("narrow"), misleading for a past as-of on a snapshot fact; the lab also maps `analysis_plan_invalid`, which the rule 24 table omits.
3. EC-150 has a sales clerk "ask", but `sales_clerk` has no `agent_analysis` row; say the clerk uses the builder, or seed the row.
4. Week grain: state ISO weeks (Monday). `previous_period` for `month_to_date` compares with the tail of the previous month; add a "same days of the previous month" option.
5. Lab N05 renders "fell by -0.13%"; add `{{abs:cN}}` or sign-aware formatting next to `dir`.
6. `production_variance_overview` offers no item, product, warehouse or branch, and its record scope columns are unstated.
7. `invariants.csv`: INV-410 to INV-414 are appended after INV-505; file order only.
8. A person may release their own saved analysis or example, so "verified" may mean one person; state it or require another person.
9. Decision 6 says "posted variance lines"; rule 19 reads a stored read model instead. The reason is good; list it as a deviation for the architect.
10. In the first fiscal year after a mid-year cut-over `fiscal_year_to_date` always abstains, although `opening_turnover` holds the earlier turnover (ADR-0049 rule 14).
11. `RecordAnalysisAnswer` as `is_draft_only` stretches ADR-0050 rule 26's definition; add a note there.
12. `overdue_bucket` and `is_overdue` depend on the business date; say it reaches the view as a session setting (ADR-0050 rule 44, no volatile functions).
13. DS-33: no indexes on the foreign keys `agent_run_id`, `saved_analysis_version_id`, `analysis_example_id`; `saved_analysis.name` has no non-blank check; `ck_analysis_example_normalized` uses `lower()`, which differs from Python `casefold` for a few scripts.

## Confirmed sound

- One read-only statement over declared views, all values bound, no plan text in SQL; six compiled statements prepare as single statements.
- Additive cells equal their drill rows; distinct counts are recomputed for totals; contributions reconcile to zero on 300 random sets with ties and `none` members.
- Fan-out: one-to-many dimensions filter by `EXISTS` and never group; multi-fact plans aggregate per fact and full-join on keys with null-safe comparison, so no chasm duplication.
- `filter_value_unknown` answers the same for missing and out-of-scope members; V4 refuses a missing field class before any SQL (for the measures that carry one).
- `is_scope_filtered` is ADR-0050 rule 48's existing mechanism, not a new oracle.
- Fiscal relative dates against a fiscal year starting in April; `plan_hash` stable across key and list order.
- The agent holds read tools only, never exports (`ListAnalysisResultRow` and `CreateListExport` off every tool list), drafts only through change proposals, release is `human_only`.
- Catalog: 35 measures, 22 dimensions, unique codes and synonyms, selectors name only core system accounts (the revenue subtree does hold the deduction accounts); no Vietnamese rule in the core.
- DDL: `company_id`, composite company keys, forced row-level security with the same two policies as DS-05, the kind key between analysis and version, null-safe KPI and threshold checks, the released-version guard.
- Numbering: INV-410–414, EC-150–155 and the DS-04 codes are unique; decisions 1–9 are each covered (with the deviation in nit 9).
