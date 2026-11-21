Module: query    Chunk: 3 of 4    Source ADRs: ADR-0060
Build step(s): 5    Generated from index: 30d5706    Compiled by: Claude Fable 5.2, 2026-11-21

# `query` compiled spec, chunk 3: plan validation, compile to SQL, execution, analysis queries, result envelope, drill, contributions, questions, explanation

## Purpose

This chunk states the part of `query` law on the analysis layer's run path: how code validates an analysis plan, compiles it to one read-only SQL statement, executes it under the actor's scope, returns the result envelope and drill handles, computes exact contributions, stores questions in `analysis_question`, and renders the explanation by code. `query` computes figures only from declared fact views and never remodels another module's figure (R441). The agent type `analysis` belongs to `agents` (ADR-0060.R20). The catalog of measures and dimensions, the plan model, saved analyses, examples and the authorization leaves are in the other chunks.

## Entities and tables

DDL: `docs/design/DS-33-analysis.sql`.

| Table | Meaning | Key | Parent | Owner |
| --- | --- | --- | --- | --- |
| `analysis_question` | One question a person asked, the subject of an analysis run, with its outcome, plan and result as shown (R443) | `id`; (`company_id`, `id`) unique | `company` | `query` |

Reads: `agent_run` (`agents`), `user_account`, `company`, `opening_turnover` (`ledger`), `production_order_variance` (`production`), and the tables `saved_analysis_version` and `analysis_example` of the other chunks.

## Commands and queries

Every query below is a `Get`, `List` or `Evaluate` (verb level `read`); `Update` is at `edit`. No source of this chunk states an emitted event.

| Name | Actor and authorization | Input | Effect | Events | Error codes |
| --- | --- | --- | --- | --- | --- |
| `EvaluateAnalysisPlan` | leaf `general_access` at `read`; checks the permission of every fact view it reads and the actor's scope; may be on agent tool lists | plan; optional `saved_analysis_version_id` | Returns the result envelope (R421, R428-R431) | none | `analysis_plan_invalid`, `unknown_measure`, `unknown_dimension`, `analysis_not_permitted`, `dimension_not_shared`, `fan_out_refused`, `currency_mixed`, `unit_mixed`, `dimension_required`, `measure_not_additive`, `time_range_invalid`, `filter_value_unknown`, `analysis_too_broad`, `analysis_data_not_ready` (R402); `timeout` (R415); `internal_error` (R439) |
| `GetAnalysisPlanExplanation` | leaf `general_access` at `read`; may be on agent tool lists | plan | Returns the canonical plan, hashes, validation result, SQL text and scope note; runs no aggregation (R422) | none | not stated |
| `ListAnalysisCatalog` | leaf `general_access` at `read`; may be on agent tool lists | not stated | Lists measures and dimensions with the actor's permission on each (R423) | none | not stated |
| `ListAnalysisDimensionMember` | leaf `general_access` at `read`; needs the `List` permission of the named fact; may be on agent tool lists | dimension, fact, search text, cursor | Lists members of one dimension within the caller's scope (R424-R426) | none | not stated |
| `ListAnalysisCellRow` | leaf `general_access` at `read`; may be on agent tool lists | handle, cursor | Lists the rows behind a cell (R434-R436) | none | not stated |
| `ListAnalysisResultRow` | leaf `general_access` at `read`; on no agent tool list | plan | Returns the result rows as a `List` query for export (R437) | none | not stated |
| `ListAnalysisQuestion` | leaf `analysis_question` at `read`, own questions only; on no agent tool list | not stated | Lists questions (R427, R449) | none | not stated |
| `GetAnalysisQuestion` | leaf `analysis_question` at `read`, own questions only; called by the workflow code of `analysis` | not stated | Reads one question (R427, R449) | none | not stated |
| `CreateAnalysisQuestion` | leaf `analysis_question` at `edit`; `human_only`; effect class `other` | question text | Creates the `analysis_question` row (R446) | not stated | not stated |
| `UpdateAnalysisAnswer` | leaf `analysis_question` at `edit`, for the human an analysis run acts for; effect class `other`, `is_draft_only`; workflow code of `analysis` only | outcome, plan, badge, key facts, narrative plan, dropped steps, result | Writes the answer to the run's own question, once (R446) | not stated | `analysis_question_answered` |
| `UpdateAnalysisFeedback` | leaf `analysis_question` at `edit`; the asker | feedback (`helpful` or `wrong`), note | Records feedback, once; `wrong` raises `analysis_answer_disputed` (R447) | not stated | not stated |

`ListSavedAnalysis`, `GetSavedAnalysis` and `ListAnalysisExample` are named by R427 and stated in the chunk that holds ADR-0060.R26 and ADR-0060.R28. Not registered commands: the consumer of `AgentRunCompleted` in `query` (R448). Check results, not refusals: `analysis_periods_open`, `analysis_scope_filtered`, `analysis_rows_truncated` (R404), `analysis_cell_changed` (R436). The capability `read_analysis_debug` (leaf `analysis_debug`, at `full`) opens the raw cost estimate (R422) and other people's stored answers (R449).

## Rules

### Plan validation

R401. Code validates every plan, from people and agents alike, in the order V1 to V14 of R402. It collects all violations, returns them in `details.violations` (code, path, message) so a planner can repair them in one round, and answers with the first one's code. The UI's analysis builder, saved analyses, MCP clients and agents send plans to the same validator; there is no second path.
Source: ADR-0060.R10

R402. The validation checks, each with its code and category:
- V1: the plan matches the model: version, types, list sizes, `limit`, operators per dimension kind, a sort key in the plan. `analysis_plan_invalid`, validation.
- V2: every measure exists and is certified, or deprecated and named by the saved analysis being run. `unknown_measure`, validation.
- V3: every dimension, filter dimension, sort key and time dimension exists, and grains are allowed for it. `unknown_dimension`, validation.
- V4: the actor may read every fact (the fact view's `List` permission), holds the field class of every measure named or computed from, and for a fact that is not owner-scoped holds an assignment with owner scope `branch` or `company` (ADR-0054.R15); `details` name what is missing, never data. `analysis_not_permitted`, permission.
- V5: every grouping and filter dimension is offered by every measure's fact (common dimensions). `dimension_not_shared`, validation.
- V6: no grouping or contribution dimension reaches a fact only one-to-many. `fan_out_refused`, validation.
- V7: a transaction-currency measure has `currency` as a dimension or a filter on one currency; a contribution plan on one has the filter; no derived measure mixes bases. `currency_mixed`, validation.
- V8: an inventory-unit measure has `item` or `product` as a dimension or a filter on one of them; a contribution plan on one has the filter. `unit_mixed`, validation.
- V9: every dimension a measure requires is grouped or filtered. `dimension_required`, validation.
- V10: `contributions` name an additive measure; `share_of_total` an additive or semi-additive one. `measure_not_additive`, validation.
- V11: a range is present where a measure's fact has time dimensions, ordered, and valid in the relative list or as a named period; a comparison has a range; contributions have a comparison. `time_range_invalid`, validation.
- V12: filter members exist and lie in the actor's scope; catalog and enum values are in their lists. `filter_value_unknown`, validation.
- V13, cardinality and cost: the range spans at most `analysis_max_range_months`; at most one `high` or `identifier` grouping dimension, which needs `limit`; at most `analysis_max_cells` cells (`analysis_agent_max_cells` for agent runs); the rows the database planner estimates its scan nodes read are at most `analysis_max_estimated_rows`. `analysis_too_broad`, precondition.
- V14, the data exists: the range does not start before the company's cut-over date (ADR-0044.R10) unless `opening_turnover` rows cover it whole for the measures that read them, no migration run is loading the company, and a current-snapshot fact is not asked as of a past date. `analysis_data_not_ready`, precondition.
Source: ADR-0060.R10

R403. When `currency` or `item`/`product` pins a measure's basis as a grouped dimension, the engine computes totals, other rows, shares and ranks per member of that dimension and omits the grand total (R410). When a filter pins the basis, nothing changes.
Source: ADR-0060.R10

R404. These are check results, not refusals: a range with periods not locked in `general` gives `analysis_periods_open`; rows left out by scope give `analysis_scope_filtered` (R418); rows cut by `limit` give `analysis_rows_truncated` (R431).
Source: ADR-0060.R10

### Limits

R405. The limits are installation settings that a company may lower and never raise: `analysis_max_cells` (5,000), `analysis_agent_max_cells` (500), `analysis_max_range_months` (60), `analysis_max_estimated_rows` (5,000,000), `analysis_result_cache_seconds` (300), and the retention of question text, whose registry key is `analysis.question_retention_days` (installation and company, default 400, a company may only lower it; ADR-0063.R2 asks for dotted keys). The values of the first five are the agent's proposal, flagged for the author; they are not retention settings.
Source: ADR-0060.R11, ADR-0060.R11.N1

### Compile to SQL

R406. The compiler emits one statement whose top level is a `SELECT` (ADR-0050.R44). Read-only common table expressions are allowed, data-modifying ones never; the CI test of ADR-0050.R44 covers it.
Source: ADR-0060.R12

R407. The compiled statement reads only fact views and label views of schema `query` that the catalog names. Every identifier comes from the catalog, never from plan text, and every value is a bound parameter. A CI property test generates plans and checks that no plan string appears in the SQL text.
Source: ADR-0060.R12

R408. Shape of the statement: one aggregation per fact over its view, filtered by that view's `is_in_scope`, by the plan's filters and, when every measure of the fact has a selector, by any of the selectors, so rows no measure selects form no empty member. Time buckets come from `date_trunc` on the declared date column or from the posting period. A plan with measures of several facts joins the per-fact aggregations on the dimension keys; no fact rows are joined to each other, so nothing fans out. Member labels come from a left join to the label view after aggregation; derived measures and contributions are computed after aggregation.
Source: ADR-0060.R12

R409. Total rows come from `GROUPING SETS`. The other row comes from ranking the high-cardinality members within the other grouped members (one currency, one month) and re-aggregating the tail from the fact rows; its drill handle carries the top keys of its group. Non-additive totals and other rows are always recomputed from rows, never summed from cells (`INV-412`).
Source: ADR-0060.R12

R410. When a grouped dimension pins a measure's basis (V7, V8), the grouping sets end at that dimension: subtotals per currency or product with row kind `subtotal`, no grand total, and shares and ranks taken within the same member. When the pinned dimension is the only grouped dimension, each member row already is its subtotal and no subtotal rows are added.
Source: ADR-0060.R12

R411. Semi-additive measures over time: whenever a plan groups a balance by its non-additive dimension, the engine takes for each bucket, per key of the fact (system account, branch, cost center, project, currency), the latest row at or before the bucket's end in period order, a special period coming after the regular period that ends on the same day. It carries a balance forward through periods without movement, for which ADR-0014.R18 writes no row. Other grouped dimensions (branch, system account) are part of the key, so each group carries its own balance, and a group without rows in a bucket keeps its last value. The total over time is the value of the last bucket, never a sum of buckets. The same holds beside measures of another fact: the per-bucket path then runs inside the balance fact's own aggregation and the facts join on the bucket keys.
Source: ADR-0060.R12

R412. A posting-period bucket ends with its period; a fiscal-year bucket ends after the year's last special period, so it holds the year-end adjustments and closing. `special_periods: exclude` leaves out the special-period rows of the fiscal year that ends on the range's `to`, and nothing else (ADR-0049.R13): those buckets disappear and the balance at the year's end is taken before them, while special periods of earlier years stay in the balance.
Source: ADR-0060.R12

R413. `opening_turnover` rows form the member `~opening` of a time breakdown (ADR-0060.R3). Rows without a member, such as a journal line without a partner, form the member `none`, which is shown and drillable, so totals reconcile.
Source: ADR-0060.R12

R414. Sums run in `numeric` on the stored amounts and quantities. Ratios are rounded half up to 6 decimals and percent to 2, by the engine only (ADR-0006).
Source: ADR-0060.R12

### Execution

R415. A plan executes under the role `nativeflows_readonly` in a read-only `REPEATABLE READ` transaction, so all cells come from one snapshot; `as_of` is that transaction's start. The statement timeout is 10 seconds for agent runs and 30 seconds otherwise (ADR-0050.R43); a timeout answers `timeout`.
Source: ADR-0060.R13

R416. Scope is evaluated per fact, because ADR-0054.R15 evaluates scope per assignment and per permission and one plan may read several fact views granted by different assignments. `nativeflows.read_grants` is always a map keyed by view name, for every query of the layer; a `List<View>` query sets a one-entry map. The entry of each fact view of the plan holds the actor's assignments in force that grant that view's `List` permission (for an agent run, those of its human), each with its record scope, owner scope, organization set and user (ADR-0050.R48). Each view's `is_in_scope` reads its own entry, never another view's, so a grant for one fact never widens another. A view without an entry sees no rows.
Source: ADR-0060.R13

R417. For an agent run of an analysis plan, the fact-view permissions and their grants are those of the run's human alone. The agent type's limit on facts is that `EvaluateAnalysisPlan`, `GetAnalysisPlanExplanation`, `ListAnalysisCellRow` and `ListAnalysisDimensionMember` are on its tool list; it holds no `List<fact view>` permission and reaches facts only through these queries (ADR-0050.R31). Field classes stay the intersection of the agent type's and the human's (ADR-0050.R12).
Source: ADR-0060.R13

R418. Every fact aggregation filters on `is_in_scope`, so totals are totals of the rows the actor may see. One `EXISTS` per fact sets `is_scope_filtered` with the check result `analysis_scope_filtered`, and the answer says so in its scope note; a total is never presented as the company's when rows are left out.
Source: ADR-0060.R13

R419. V4 refuses a measure whose field class the actor lacks before any SQL runs, so a masked column never sums to a silent zero. Facts omit untrusted columns and aggregates do not taint (ADR-0050.R25), so analysis runs stay clean.
Source: ADR-0060.R13

### Queries of the analysis layer

R420. The analysis queries belong to module `query` under the computed-query exception of ADR-0004.R21, as ADR-0040.R8. `EvaluateAnalysisPlan` takes the glossary verb `Evaluate`: a query that computes a result from given inputs and stores nothing. The explanation is read as `GetAnalysisPlanExplanation`. Every query of ADR-0060 is a `Get`, `List` or `Evaluate`.
Source: ADR-0060.R14

R421. `EvaluateAnalysisPlan` (plan; optional `saved_analysis_version_id`) returns the result envelope of R428 to R431.
Source: ADR-0060.R14

R422. `GetAnalysisPlanExplanation` (plan) returns the canonical plan, `analysis_plan_hash`, the resolved absolute dates, the validation result, the facts and views read, the compiled SQL text with its bound values listed apart, and the scope note (record scope, owner scope, field classes; which facts need owner scope `branch` or `company`). It runs no aggregation. Of the cost guard it returns only `within_limit` or the limit that tripped; the raw planner estimate goes only to holders of the capability `read_analysis_debug`, because planner statistics are table-wide. The SQL is returned to every caller who may run the plan: it names only declared views and the caller's own values.
Source: ADR-0060.R14

R423. `ListAnalysisCatalog` returns measures and dimensions with labels, synonyms, bases, hierarchies and the actor's permission on each. The MCP resources `nativeflows://query/measures`, `nativeflows://query/measures/<code>`, `nativeflows://query/dimensions` and `nativeflows://query/dimensions/<code>` describe the same metadata (ADR-0050.R46).
Source: ADR-0060.R14

R424. `ListAnalysisDimensionMember` (dimension, fact, search text, cursor) returns members of one dimension: key, code and label, matched on code and label folded for case and diacritics (ADR-0050.R47). It needs the `List` permission of the named fact, which must offer the dimension, and returns only members that occur in that fact's rows within the caller's scope for it (R416), so nobody enumerates partners, employees or accounts beyond what they may read. It is the one lookup for filter members, so a plan never carries a name. For agent runs a label labelled `personal` comes back as a handle (ADR-0060.R31).
Source: ADR-0060.R14

R425. The response of `ListAnalysisDimensionMember` carries no `is_scope_filtered`, no count and no hint of members outside the scope: "no such member" and "outside your scope" are one identical empty answer, as V12. Its time still grows with the matching rows outside the scope, a weak channel bounded by: a search text of at least 3 characters, at most 20 members per page, at most two lookups per plan attempt for agent runs, and the run's budget.
Source: ADR-0060.R14

R426. A member with no rows in the fact (a new customer) is found only by a caller whose grant on the fact has owner scope `company` and no record scope and who also holds the `List` permission of the dimension's master data (for partners, `ListPartnerOverview`); that caller searches that master data. For anyone else the question abstains rather than answering zero.
Source: ADR-0060.R14

R427. The other queries of the layer are `ListAnalysisCellRow` (R434), `ListAnalysisResultRow` (R437), `ListAnalysisQuestion` and `GetAnalysisQuestion` (R449), and `ListSavedAnalysis`, `GetSavedAnalysis` and `ListAnalysisExample` (ADR-0060.R26, ADR-0060.R28). `EvaluateAnalysisPlan`, `GetAnalysisPlanExplanation`, `ListAnalysisCatalog`, `ListAnalysisDimensionMember`, `ListAnalysisCellRow` and `ListAnalysisResultRow` sit on the authorization leaf `general_access` at `read`: each checks the permission of every fact view it reads and the actor's scope (ADR-0054.R24). The other queries and the commands have leaves of their own (ADR-0060.R36). All but `ListAnalysisResultRow` and `ListAnalysisQuestion` may be on agent tool lists.
Source: ADR-0060.R14

### Result envelope

R428. The header of the result envelope holds: the canonical plan, `analysis_plan_hash`, `analysis_resolved_hash`, resolved dates, catalog version and hash, `as_of`, `is_scope_filtered`, `is_truncated`, `badge` (`verified` or `generated`, ADR-0060.R26), `checks` (DS-04 format) and the row count.
Source: ADR-0060.R15

R429. Each row of the envelope has a `row_kind` (`member`, `other`, `subtotal`, `total`, `reconciliation`), the dimension members (key and label) and one cell per measure and derived value. A personal label is returned to people within their permissions and replaced by a handle for agent runs (ADR-0060.R31).
Source: ADR-0060.R15

R430. Each cell holds `cell_id` (`c1`, `c2`, … in row order), `cell_kind` (`value`; `change` for differences, growth and contributions; `share`; `ratio`), the measure or derived code, the value as a canonical decimal string, the basis (currency code, unit code, `count` or `percent`), the scale, the flags `is_max` and `is_min`, set by code on complete results only, and the drill handle. The envelope also holds the key facts code renders for the answer (R450), with their template codes and cells.
Source: ADR-0060.R15

R431. A `limit` without the other row drops member rows beyond the limit and keeps totals over all rows; `is_truncated` is true and the check result `analysis_rows_truncated` names the limit. No cell of a truncated result carries `is_max`, `is_min` or a rank.
Source: ADR-0060.R15

### Drill handles

R432. A drill handle is a JSON object `{"analysis_plan_hash", "analysis_resolved_hash", "cell": {<dimension>: <member key>, …}, "measure", "cell_kind"}`, and for an other row also `"other_excludes"`, the top member keys of its group. The members `none` and `other` are written `~none` and `~other`. A person or an agent can read a handle and build it again.
Source: ADR-0060.R16

R433. Drilling to the next level replaces each grouped dimension that has a child level by that child, with the cell's members as filters; this gives a new plan, run by `EvaluateAnalysisPlan`. The levels: `item_group` → `product` → `item`; `system_account` → its children → `account`; `year` → `quarter` → `month` → `day`.
Source: ADR-0060.R16

R434. `ListAnalysisCellRow` (handle, cursor) lists the rows behind a cell by cursor (ADR-0008.R22) with document ID, number and type, date, line and the row's contribution. Per kind of cell, the drill rows and their sum (`INV-410`):
- Sum of a base measure: the fact rows of the cell, each with its signed column value; the sum equals the cell.
- Count: the rows, 1 each; the sum equals the cell.
- Distinct count: the rows, with their distinct key; the number of distinct keys equals the cell.
- `difference` (`gross_profit`): the rows of both operands, each with its sign in the difference; the sum equals the cell.
- `ratio`, `growth`, `share`: not rows, but the handles of its numerator and denominator (or base and comparison) cells, each drillable.
- Contribution member or other row: the member's rows in P1 with their sign and in P0 negated; the sum equals the change.
- Total and subtotal: all rows of the cell's group; the sum equals the cell.
- Semi-additive balance (`ledger_closing_balance`): an opening row (the balance at the end of the period before the range's first period, from the turnover rows) and the journal lines of the range, as the books of ADR-0049.R10; opening plus lines equals the cell.
- Reconciliation: none; it is zero by `INV-412`.
For `journal_line_overview` and `system_account_turnover` the rows are journal lines, the contract of `ListReportLineContribution` (ADR-0049.R16). Rows end at documents, which open in their record view.
Source: ADR-0060.R16

R435. For agent runs `ListAnalysisCellRow` returns a numeric projection (ADR-0050.R28): IDs, document numbers and types, dates, accounts and contributions, no free text. Like aggregates, such rows do not taint and are not filtered from a clean run, so the sum holds for agents too.
Source: ADR-0060.R16

R436. Drilling validates the plan again under the current actor and reads a new snapshot. If the cell's value differs from the handle's, the response carries `analysis_cell_changed` with both values.
Source: ADR-0060.R16

### Export

R437. `ListAnalysisResultRow` (plan) returns the result rows as a `List` query, so `CreateListExport` writes them to `.xlsx` unchanged (ADR-0050.R54): the consumer reruns the plan as the requester, with field classes, scope and `list_export_max_rows`. Agents never export: `ListAnalysisResultRow` and `CreateListExport` are on no agent tool list (ADR-0050.R30); an agent's answer is shown in the UI, where the person may export it.
Source: ADR-0060.R17

### Exact additive contributions

R438. A contribution plan takes an additive measure M, a dimension D shared by M's fact, the range P1 (`time.range`), the comparison P0 (`time.compare`), `top` at most 25 (10 by default) and the plan's filters. A transaction-currency or inventory-unit M needs its basis pinned by a filter (V7, V8).
Source: ADR-0060.R18

R439. For each member d of D in P0 or P1, including `none`, the engine computes M₀(d) and M₁(d), a missing value counting as 0, and Δ(d) = M₁(d) − M₀(d). The rows are: the members ranked by |Δ| descending, then by member key; the top rows; one `other` row with the sum of the rest; one `total` row with M₁ − M₀ computed directly from the fact rows of each period; and one `reconciliation` row, the total Δ minus the sum of the member and other rows, which must be exactly zero (`INV-412`). A non-zero reconciliation is an `internal_error`, never shown as an answer.
Source: ADR-0060.R18

R440. Each contribution row's share of the total change, rounded half up to 4 decimals, is a derived cell; it is omitted when the total change is zero. Ratios do not decompose additively: a contribution plan on a ratio or distinct count is refused with `measure_not_additive`, and the planner may analyse the numerator and denominator instead.
Source: ADR-0060.R18

### Production variances

R441. Production variances are the split of ADR-0035.R15 (input price, input quantity, resource usage, scrap, lot size, remaining), computed by the variance function of `production`, the function behind `GetProductionOrderVariance`. The analysis layer never remodels them. When the period's costing run settles a production order's period cost (ADR-0035), `production` writes the split per order, period and variance category to its read model `production_order_variance`, with the order's output item, warehouse and branch; its DDL comes with the costing tables of DS-53. `production_variance_overview` reads those rows only (ADR-0050.R52: a view never re-implements a module's figure).
Source: ADR-0060.R19

R442. Under actual costing variances are not posted (ADR-0035.R15), so the analysis layer reads the stored split and not posted variance lines. If the author chooses standard cost valuation, the posted variance lines become the source and the measure keeps its code.
Source: ADR-0060.R19

### Questions

R443. `analysis_question` is company data owned by `query`. A row holds: the asker (`asked_by_user_id`), the question text (`question_text`, at most 2,000 characters), its `language`, the run (`agent_run_id`), the `state` (`open`, `answered`, `abstained`, `failed`), the `outcome` or, for a failed run, its stop reason (`failure_reason`), the `plan` and its hashes, the `badge`, the `key_facts`, the `narrative_plan` with the steps code dropped (`narrative_dropped_steps`), the `clarification_options`, the `result` as shown (rows, cells and member keys, never member labels, which are resolved again at display under the viewer's rights), `as_of`, and the asker's `feedback` (`helpful` or `wrong`) with a `feedback_note`. The DDL also carries `catalog_version`, the verified source of a hit (`saved_analysis_version_id` or `analysis_example_id`, exactly one of them for badge `verified`), `asked_at`, `answered_at`, `feedback_at` and `erased_at`. `outcome` is one of `answered`, `ambiguous_term`, `ambiguous_member`, `out_of_coverage`, `not_permitted`, `data_not_ready`, `too_broad`, `not_applicable` and `routing_blocked`; state `abstained` holds an abstention, `not_applicable` or `routing_blocked` (ADR-0060.R24), and state `failed` holds no outcome but the `failure_reason`.
Source: ADR-0060.R21

R444. The question text, trigger questions, example questions and feedback notes are labelled `personal`: a question may name a person, as a bank description may (ADR-0050.R9). Under the per-request gate of ADR-0063.R15 and ADR-0063.R17, a question reaches the router and planner seats when a permission covers them, and every call is logged in the processing log (ADR-0050.R10). When the gate does not pass it, the gateway removes the question, the router step is not sent and the run ends `routing_blocked`; exact matches with verified examples and saved analyses (ADR-0060.R22), opening saved analyses and the builder still work, because they need no model. The alternative reading of the label, `internal`, is the author's open question.
Source: ADR-0060.R21, ADR-0060.R21.N1

R445. Question text and feedback notes are blanked after `analysis.question_retention_days`, and when the asker's user account is erased; the outcome, plan and hashes stay.
Source: ADR-0060.R21, ADR-0060.R11.N1

R446. Commands on the leaf `analysis_question` (ADR-0060.R36):
- `CreateAnalysisQuestion` (effect class `other`, `human_only`) creates the row; the UI then sends `StartAgentRun` with the row as subject, acting for the asker (ADR-0050.R15).
- `UpdateAnalysisAnswer` (effect class `other`, `is_draft_only`, on the `analysis` tool list for workflow code only) writes the outcome, plan, badge, key facts, narrative plan, dropped steps and result to the run's own question, once; it refuses a question of another run or already answered with `analysis_question_answered`.
- `UpdateAnalysisFeedback` (the asker) records feedback once; feedback is never changed or cleared after it is given.
The verb is `Update` (an edit of fields of the question), not `Set`, whose glossary meaning is replacing a whole list.
Source: ADR-0060.R21

R447. Feedback `wrong` raises the work item `analysis_answer_disputed` (owner `company_owner`).
Source: ADR-0060.R21

R448. A consumer of `AgentRunCompleted` in `query` sets a question whose run stopped (`budget_exceeded`, `time_exceeded`, `output_invalid`, `provider_unavailable`, `resume_diverged`, `crashed`, `denials_repeated` or `canceled`) to `failed` with that reason. The `agent_run_stopped` item of ADR-0050 stays one per agent type, outcome and business date, never one per question.
Source: ADR-0060.R21

R449. A question and its stored result are readable only by the asker and by holders of the capability `read_analysis_debug`. Whoever handles a dispute reruns the plan under their own rights, because the stored cells are computed under the asker's scope and field classes.
Source: ADR-0060.R21

### The explanation: key facts and a narrative plan

R450. An explanation is key facts and a narrative plan, both rendered by code (ADR-0050.R36, made structural). In Phase 1 the model writes no text that reaches the person (`INV-413`). The restatement of the question is written by code from the plan: measures, dimensions, filters, absolute range, time dimension, basis.
Source: ADR-0060.R23

R451. Every number an answer states is a key fact that code renders from a fixed template set of the output language, with values formatted by locale, currency, unit and scale (ADR-0040.R2). The templates and their English forms:
- `value`: `<measure> for <member>: <value> (<period>)`, or `(as of <date>)` for a balance or a current-snapshot measure.
- `total`: `<measure>, total: <value> (<period>)`.
- `change`: `<measure> for <member> changed from <a> to <b> (<signed change>, <direction word>)`.
- `share`: `<member>: <share> of <measure> (<period>)`.
- `contribution`: `<member> contributed <signed change> to the change in <measure> (<period> against <compare period>)`.
The direction word (rose, fell, was unchanged) is computed from the sign.
Source: ADR-0060.R23

R452. Code offers up to 12 key facts, each with a handle (ADR-0060.R22). The model may pick up to 5 of them, each one of the offered handles and none twice (ADR-0050.R36); without a pick code shows its own: the total, the largest member and the changes.
Source: ADR-0060.R23

R453. The model's `narrative` is a plan, not prose: an ordered list of at most 8 steps, each `{"claim": <claim template code>, "facts": {<role>: <fact handle>}}`. Every fact handle is one of the offered key facts. The model names no member: code renders `{member}` from the fact's own row. Codes and handles are short identifiers, and the schema rejects any other field or value. A plan that breaks the schema is invalid output (the retries of ADR-0050.R35), and then the answer shows the key facts alone.
Source: ADR-0060.R23

R454. Code renders every sentence from a closed catalog of claim templates per language. Each template declares its roles and a deterministic precondition on the served cells. The claims, with English sentence and precondition:
- `largest_value`: `{member} has the largest {measure}.` A member row (not a total or other row) marked `is_max`, on a complete result with at least two member rows.
- `smallest_value`: `{member} has the smallest {measure}.` A member row marked `is_min`, on a complete result with at least two member rows.
- `largest_contributor`: `{member} is the largest contributor to the change in {measure}.` A member contribution row; the total change is not zero; the contribution has its sign and is the unique largest of that sign.
- `largest_offset`: `{member} is the largest offset to the change in {measure}.` A member contribution row; the total change is not zero; the contribution has the opposite sign and is the unique largest of that sign.
- `most_of_change`: `{member} explains most of the change in {measure}.` A member contribution row; the total change is not zero; the contribution has its sign and more than half of the sum of all contributions of that sign, the other row included, so at most one member qualifies.
- `rose`, `fell`: `{measure} rose for {member}.` / `{measure} fell for {member}.` A member row's change cell above, or below, the flat band.
- `flat`: `{measure} was almost unchanged for {member}.` A member row's absolute change at most the flat band: 1% of the absolute base value (0 when the base is 0), a constant of the agent type version.
- `same_direction`: `{measure} moved in the same direction for {member_a} and {member_b}.` Two distinct facts of member rows, of the same measure and the same comparison, both changes outside the flat band, with the same sign.
- `opposite_direction`: `{measure} moved in opposite directions for {member_a} and {member_b}.` As `same_direction`, with opposite signs.
- `scope_note`: `These figures cover only the records you may see.` `is_scope_filtered`.
- `also`, `meanwhile`: `Also,` / `Meanwhile,` before the next sentence. Rendered only between two rendered sentences.
Source: ADR-0060.R23

R455. `{member}` (and `{member_a}`, `{member_b}`) renders the fact's whole row: every grouped member of it, and for a pinned basis the pinned member too, so a claim about one cell never reads as a claim about one of its members. `{measure}` renders as the measure's catalog label. Each sentence ends with the citation markers of its facts, which open the key facts. A member renders as a marker, a chip or link in the UI: the chip is the control, and a label's text is data, never interpolated outside its chip, so a label that reads like a claim stays a name. A CI check holds that no claim template and no catalog label contains a digit, a number word or a unit word.
Source: ADR-0060.R23

R456. Before rendering, code evaluates each step's precondition on the served cells. A failing step is dropped and recorded in `narrative_dropped_steps` with its claim and reason; the rest are rendered. Every direction, rank and quantity word so comes from code, after code has checked it. The rendered narrative is a pure function of the plan, the cells, the member labels and the catalog: no string from the model reaches it except through a handle that code resolves. What remains possible is a true but unhelpful choice or order of claims, bounded by the key facts and the table beside them.
Source: ADR-0060.R23

R457. A language without a claim catalog and key-fact templates gets key facts only, in the company's default language, or in English when that language has none either. The core ships English; a package supplies the catalog for its language.
Source: ADR-0060.R23

R458. The setting `analysis.narrative_mode` selects how answers explain: `facts_only` or `claim_plan`, the default; its installation value is a maximum that a company may only lower. `free_prose`, prose written by the model, is outside the bounds in Phase 1; it unlocks per language and model version at 80% acceptance with no unbacked claim (ADR-0063.R25).
Source: ADR-0060.R23, ADR-0060.R23.N1

## Invariants

| INV | Check point | Statement | Protects |
| --- | --- | --- | --- |
| `INV-410` | run | Every drillable analysis cell equals its drill rows by the list of R434: the sum of their contributions for sums, counts, differences, totals, subtotals and contribution rows, the number of distinct keys for distinct counts, and the opening row plus the lines for balances, at the same snapshot. Name `analysis_cell_equals_drill_rows`; area `reporting`; keys `plan`, `cell`; first step 5. | R434, R435 |
| `INV-412` | run | Every total, subtotal and other row of an analysis result equals the aggregation of its fact rows, never a sum of non-additive cells; no total row adds values of different currencies or inventory units; every contribution result's reconciliation row is zero. Name `analysis_totals_from_rows`; area `reporting`; keys `plan`; first step 5. | R409, R410, R439 |
| `INV-413` | day | Every user-visible sentence of an analysis answer is rendered by code, from a key-fact template or from a claim template whose precondition held on the served cells; every stored narrative plan holds only claim codes, roles and handles. Name `analysis_sentences_rendered_by_code`; area `safety`; keys `analysis_question`; first step 5. | R450, R451, R453, R454, R456 |

`INV-411` has its row in chunk 2, and `INV-414` and `INV-716` have theirs in chunk 4.

## Edge cases

| EC | Name | Case | Outcome | Source |
| --- | --- | --- | --- | --- |
| `EC-150` | `analysis_owner_scoped_total` | A sales clerk with owner scope `own` builds an analysis of last month's net invoiced sales in the analysis builder (the seed gives the clerk no analysis agent); the result totals only their documents, carries the scope note and `analysis_scope_filtered`, and its drill lists only their invoices. | `must_succeed` | ADR-0060.R13; R416, R418 |
| `EC-151` | `analysis_two_currencies` | A question over sales invoices in two currencies asks for document amounts without naming a currency; the plan is refused with `currency_mixed`, and the planner repairs it to company-currency amounts or the agent asks which currency (`ambiguous_term`); grouped by currency, the result has one subtotal per currency and no grand total. | `must_reject:currency_mixed` or `must_succeed` | ADR-0060.R10; ADR-0060.R24; R402, R410 |
| `EC-152` | `analysis_margin_without_class` | A user without the `margin` field class asks for gross profit by customer; the run abstains with `not_permitted`, names the missing class and shows no figure. | `must_reject:analysis_not_permitted` | ADR-0060.R10; ADR-0060.R24; R402, R419 |
| `EC-153` | `analysis_change_open_month` | Net revenue change by customer between a locked month and the open current month: the contribution rows reconcile to zero, the total change equals the journal's, and `analysis_periods_open` is returned. | `must_succeed` | ADR-0060.R18; R404, R439 |

`EC-155` and `EC-170` have their rows in chunk 2, and `EC-154` has its row in chunk 4.

## Settings

| Key | Value type | Scopes | Core default | Used by |
| --- | --- | --- | --- | --- |
| `analysis.question_retention_days` | integer | `installation`; `company` (a company may only lower it) | 400 | R405, R445 |
| `analysis.pseudonymize_known_subjects` | boolean | `company` | true | ADR-0060.R20.N1 |

`analysis_max_cells`, `analysis_agent_max_cells`, `analysis_max_range_months`, `analysis_max_estimated_rows` and `analysis_result_cache_seconds` are named by R405 and have no row in `settings.csv`. The row of `analysis.narrative_mode` (R458) is in the chunk that holds ADR-0063.R25.

`list_export_max_rows` (R437) is stated in chunk 2 with ADR-0050.R54; it too has no row in `settings.csv`.

## UI annotations

The sources of this chunk state no floorplan, title, facet, field annotation or tile. The work item kind `analysis_answer_disputed`, which R447 raises, has its row in chunk 4 with the other kind of module `query`.

## Conflicts

CONFLICT ADR-0060.R11: ADR-0060.R11.N1 governs the retention setting; its registry key is the dotted `analysis.question_retention_days` with default 400 at installation and company scope, so the undotted name is not restated (R405).
CONFLICT ADR-0060.R21: ADR-0060.R21.N1 governs the routing of a question; the per-request gate of ADR-0063 replaces the routing switch, so "with the routing switch off" and "on" are not restated (R444); ADR-0060.R11.N1 gives the retention key its dotted name (R445).
CONFLICT ADR-0060.R23: ADR-0060.R23.N1 and ADR-0063.R25 govern free prose; the gate is 80% acceptance with no unbacked claim per language and model version and ADR-0063.R25 marks the point answered, so "(open question)" is not restated (R458).

## Proposed (not law)

None

## Trace

| Source | Where |
| --- | --- |
| ADR-0060.R10 | R401-R404 |
| ADR-0060.R11 | R405 |
| ADR-0060.R11.N1 | R405, R445 |
| ADR-0060.R12 | R406-R414 |
| ADR-0060.R13 | R415-R419 |
| ADR-0060.R14 | R420-R427 |
| ADR-0060.R15 | R428-R431 |
| ADR-0060.R16 | R432-R436 |
| ADR-0060.R17 | R437 |
| ADR-0060.R18 | R438-R440 |
| ADR-0060.R19 | R441, R442 |
| ADR-0060.R20 | ref: ADR-0060.R20 |
| ADR-0060.R20.N1 | ref: ADR-0060.R20.N1 |
| ADR-0060.R21 | R443-R449 |
| ADR-0060.R21.N1 | R444 |
| ADR-0060.R23 | R450-R458 |
| ADR-0060.R23.N1 | R458 |
