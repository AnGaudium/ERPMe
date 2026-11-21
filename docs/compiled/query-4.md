Module: query    Chunk: 4 of 4    Source ADRs: ADR-0060, ADR-0063, ADR-0064, ADR-0066, ADR-0069, ADR-0071
Build step(s): 1, 5    Generated from index: 30d5706    Compiled by: Claude Fable 5.2, 2026-11-21

# Compiled spec: `query`, chunk 4

## Purpose

`query` is the read layer (layer 5): views in schema `query`, the analysis catalog, analysis plans and the analysis
questions. This chunk states saved analyses, KPIs, analysis examples, the evaluation suite, cost and caches, the floors
kept for agent runs, the analysis screens, the Phase 1 measures and dimensions, the invariants and catalog rows of
ADR-0060, the narrative mode setting, the production views, `ListWorkCaseTimeline` and `GetOperationWorkspace`. Plan
validation, compilation, the answer envelope, questions and the narrative plan are in chunks 1 to 3 and are cited by
their source IDs. Agent types and the assist request belong to `agents` and are traced `ref:`.

## Entities and tables

DDL: `docs/design/DS-33-analysis.sql`. `analysis_question` is defined by ADR-0060.R21 and has its row in chunk 3.

| Table | Meaning | Key | Parent | Owner |
| --- | --- | --- | --- | --- |
| `saved_analysis` | A saved analysis or KPI of a company, with its state, visibility and version pointers (R601). Company data, change-tracked. | `id`; unique (`company_id`, `code`) | `company` | `query` |
| `saved_analysis_version` | One version of a saved analysis: plan, hashes, presentation, open filters, trigger questions, narrative plan, KPI fields (R602, R612). Immutable once released. | `id`; unique (`company_id`, `saved_analysis_id`, `version`) | `saved_analysis` | `query` |
| `analysis_example` | A verified question-and-plan pair, versioned (R613, R614). Company data, change-tracked, immutable once released. | `id`; unique (`company_id`, `normalized_question`, `language`, `version`) | `company` | `query` |

Reads: `analysis_question`, `agent_run`, `user_account`, `company`, `production_order`, `production_order_variance`, `work_case`, `work_item`, `audit_record`, `business_unit`, `site`, `payment_method`, `warehouse`, `assist_request`, `costing_sheet`, `document_extraction`, `production_version`; the fact views named in R646.

## Commands and queries

| Name | Actor and authorization | Input | Effect | Events | Error codes |
| --- | --- | --- | --- | --- | --- |
| `CreateSavedAnalysis` | Leaf `general_access` at `edit`; visibility `company` and kind `kpi` also need the capability `share_saved_analysis` (leaf `saved_analysis`, `edit`) | A saved analysis and its first version | Creates the `saved_analysis`; effect class `master_data_change`, change-tracked (R603) | not stated | not stated |
| `UpdateSavedAnalysis` | As `CreateSavedAnalysis` | The saved analysis and the changed version, or the retirement | Writes a new draft version, or sets `retired` (R603) | not stated | not stated |
| `ReleaseSavedAnalysis` | Leaf `saved_analysis` at `post`, `human_only`; a person other than the author (R606) | The version | Makes the version the verified version (R604); clears the plan cache (R626) | not stated | not stated (R607 refuses a clashing trigger question without naming a code) |
| `ListSavedAnalysis`, `GetSavedAnalysis` | Leaf `general_access` at `read` | not stated | The caller's own private analyses and every company analysis (R605) | none (queries) | not stated |
| `CreateAnalysisExample` | Leaf `saved_analysis` at `edit` | The question, language, flow, expected outcome and plan | Creates a draft `analysis_example`; `master_data_change` (R615) | not stated | not stated |
| `UpdateAnalysisExample` | Leaf `saved_analysis` at `edit` | The example and its changes | On a verified example writes a new draft version that supersedes it (R614); `master_data_change` | not stated | not stated |
| `ReleaseAnalysisExample` | Leaf `saved_analysis` at `post`, `human_only`; a person other than the author (R606) | The example | Verifies the example and retires the one it supersedes in the same command (R614); clears the plan cache (R626) | not stated | not stated |
| `ListAnalysisExample` | Leaf `saved_analysis` at `read` | not stated | not stated beyond its registration (R658) | none (query) | not stated |
| `ListWorkCaseTimeline` | Listed on leaf `work_queue` of `authorization-areas.csv` (a row of module `work`, ADR-0066.R13); level not stated | A work case; `include_untrusted` | The composed timeline of R683 | none (query) | not stated |
| `GetOperationWorkspace` | `production_order` at `read` | One work order | What the tablet shows for it (R687) | none (query) | not stated |

The commands and queries of leaf `analysis_question` and `EvaluateAnalysisPlan` have their rows in chunk 3 (ADR-0060.R14, ADR-0060.R21); R657 states their authorization.

Error codes, check results and run outcomes that ADR-0060.R36 registers are listed in R652 to R654; this chunk binds none of them to a command above.

## Rules

### Saved analyses

R601. `saved_analysis` (company data, change-tracked) holds `code`, `name`, `kind` (`analysis` or `kpi`), `state` (`draft`, `verified`, `retired`), `verified_version`, `latest_version`, the owner user (`owner_user_id`) and `visibility`: `private` to its owner, or `company` for every holder of the read permission.
Source: ADR-0060.R26

R602. `saved_analysis_version` is immutable once released. It holds the plan, its `analysis_plan_hash` and the definition hashes it covers (`definition_hashes`), the catalog version, the presentation (chart kind, layout, column order), `open_filters` (dimensions a viewer may filter without losing the badge), the trigger questions (`trigger_questions`), an optional narrative plan written by a person from the same claim catalog (ADR-0060.R23), the KPI fields of R612, the author (`created_by_user_id`), the origin agent run (`origin_agent_run_id`), who released it when (`released_by_user_id`, `released_at`) and `is_self_released`.
Source: ADR-0060.R26

R603. `CreateSavedAnalysis` and `UpdateSavedAnalysis` have effect class `master_data_change`, are change-tracked and need leaf `general_access` at `edit`. An update writes a new draft version, or sets `retired`. Every builder user may keep personal analyses with visibility `private`. Visibility `company` and kind `kpi` also need the capability `share_saved_analysis` (leaf `saved_analysis`, `edit`).
Source: ADR-0060.R26

R604. `ReleaseSavedAnalysis` (leaf `saved_analysis`, `post`, `human_only`) makes the version the verified version. A verified version stays in force until another version is released.
Source: ADR-0060.R26

R605. `ListSavedAnalysis` and `GetSavedAnalysis` (leaf `general_access`, `read`) show a caller their own private analyses and every company analysis, so KPI tiles open for everyone. Running an analysis still checks each fact's permission.
Source: ADR-0060.R26

R606. The person who releases a version differs from its author, as for change proposals (ADR-0055). In small-company mode (ADR-0054.R20) the author may release it, and the version records `is_self_released`.
Source: ADR-0060.R26

R607. Release refuses a trigger question that equals, in the same language, a verified example's question or another verified version's trigger question within the same visibility set. A visibility set is the company's analyses and examples, or one owner's private analyses together with the company's. So the exact match of ADR-0060.D0 (D2) never has more than one answer for one asker.
Source: ADR-0060.R26

R608. Commands of effect class `master_data_change` are allowed targets of change proposals and stay off tool lists (ADR-0029.R2; ADR-0050.R29). The analysis agent drafts a saved analysis of kind `analysis`, or an example, only when the asker asks it to, through `CreateChangeProposal`; a person submits and an eligible person approves it (ADR-0055). Release stays a separate human step. Agents draft no KPI.
Source: ADR-0060.R26

R609. Opening a saved analysis runs its verified version (or a draft, for its editors) through `EvaluateAnalysisPlan`, without any model. With a narrative plan, code renders it on every opening and evaluates every step's precondition again on the new cells, dropping the steps that no longer hold. Without a narrative plan the person may ask for an explanation, which is an `analysis` run.
Source: ADR-0060.R26

R610. A saved narrative plan refers to each fact either by `{"role": …, "measure": …}`, with the roles `total`, `total_change`, `max`, `min` and `largest_contribution`, or by `{"members": {<dimension>: <key>, …}, "measure": …, "kind": …}`, the full coordinate of the row with `kind` one of `value`, `change`, `share`, `contribution`. It never refers by cell position, so reordered rows cannot make a sentence name another member. A reference that resolves to no cell, or to more than one, drops its step.
Source: ADR-0060.R26

R611. Code computes the badge for every result, however its plan was found. It is `verified` when the plan's `analysis_plan_hash`, taken now, equals the hash stored on a verified saved analysis version or a verified example, or equals it after removing filters on that version's `open_filters`; otherwise `generated`. The hash covers the named definitions, so a changed definition ends the badge. No model ever sets the badge. A verified plan still runs under the asker's scope (`INV-414`).
Source: ADR-0060.R26

R612. A KPI is a saved analysis of kind `kpi` whose versions hold one measure (`kpi_measure`), a time grain (`kpi_time_grain`), `favorable_direction` (`up` or `down`), `target_value`, and optional `warning_threshold` and `critical_threshold` in the measure's basis, ordered by the direction. People enter targets and thresholds; no agent proposes them. Running a KPI returns the value, the target and a status computed by code: `critical` beyond the critical threshold, `on_track` on the favourable side of the warning threshold (of the target when no warning threshold is set), `warning` between. KPI tiles in the UI are KPIs run. Alerts and subscriptions come after Phase 1.
Source: ADR-0060.R27

### Analysis examples

R613. `analysis_example` (company data, change-tracked) holds the question (`question_text`), the normalized question (`normalized_question`), the `language`, the `flow` (`sales`, `purchasing`, `inventory`, `production`, `open_items`, `ledger`), the expected outcome (`expected_outcome`: `answered` or one abstention of ADR-0060.R24: `ambiguous_term`, `ambiguous_member`, `out_of_coverage`, `not_permitted`, `data_not_ready`, `too_broad`), the `plan`, `analysis_plan_hash` and `catalog_version` for `answered` and none of them for an abstention, `version`, the example it supersedes (`supersedes_example_id`), `state` (`draft`, `verified`, `retired`), the `source` (`person`, `feedback`, `agent_proposal`), the question it came from (`origin_analysis_question_id`, set exactly for source `feedback`), its author (`created_by_user_id`), who released it when (`released_by_user_id`, `released_at`), and `is_self_released`, true exactly when the releaser is the author (R606).
Source: ADR-0060.R28

R614. A released example never changes: a guard freezes its question, plan, hash and expected outcome, and allows only retirement. `UpdateAnalysisExample` on a verified example writes a new draft version that supersedes it; releasing the new version retires the old one in the same command. There is one verified example per normalized question and language.
Source: ADR-0060.R28

R615. The example commands are on leaf `saved_analysis`: `CreateAnalysisExample` and `UpdateAnalysisExample` at `edit` with effect class `master_data_change`; `ReleaseAnalysisExample` at `post`, `human_only`, by a person other than the author (R606).
Source: ADR-0060.R28

R616. Verified examples answer exact matches without a model (ADR-0060.R22, D2 of ADR-0060.D0), give the planner context, and are the company's evaluation cases (ADR-0060.R25).
Source: ADR-0060.R28

### Evaluation suite

R617. The evaluation suite follows ADR-0050.R39 and ADR-0050.R40. The core suite holds 50 to 100 cases per flow of R613, in English, built on the synthetic dataset (DS-17). A case holds the question, business date, actor (field classes and scope), expected outcome, expected plan (canonical) and expected result on the dataset. At least one case in five expects an abstention, with its code. Packages may add questions in their language as test data of the package.
Source: ADR-0060.R29

R618. A case is equal when the plan's `analysis_resolved_hash` equals the expected one, or the results are equal on the dataset. A wrong answer is an `answered` outcome whose result differs from the expected result, or an answer where an abstention was expected.
Source: ADR-0060.R29

R619. The examples given as context never include the case under test.
Source: ADR-0060.R29

R620. The thresholds are: at least 90% of cases equal (ADR-0003.R8), at most 2% of cases wrong, and at least 90% of the abstention cases abstaining with the expected outcome.
Source: ADR-0060.R29

R621. The evaluation report also counts narrative steps dropped per claim template and refusals by error code. It adds plan match, result match, wrong-answer rate, abstention precision and recall, and cost per case.
Source: ADR-0060.R29

R622. The replay suite runs on every commit that touches the analysis code of `query`, the catalog or the workflow. The live evaluation runs whenever a template, an output schema, the catalog, the agent type version or `seatmap.yaml` changes (ADR-0050.R40).
Source: ADR-0060.R29

### Cost and caches

R623. Verified saved analyses, exact matches with verified examples and plan cache hits skip L1 and L2. A saved analysis with a narrative plan uses no model at all. People who build analyses in the UI use no model.
Source: ADR-0060.R30

R624. The plan cache maps a normalized question to a plan. Its key is the company, the user, the scope fingerprint, the language, the catalog hash and the agent type version. The scope fingerprint is a hash of the per-view read grants, owner scope sets and field classes the builder would set (ADR-0060.R13).
Source: ADR-0060.R30

R625. The result cache is keyed by company, user, `analysis_resolved_hash` and the same scope fingerprint, and kept `analysis_result_cache_seconds`. A cached result shows its own `as_of`. Neither cache key omits company or user: a plan without entity filters has the same resolved hash in every company, and users with equal grants may still own different documents.
Source: ADR-0060.R30

R626. The plan cache is cleared when an example or a saved analysis is released or retired.
Source: ADR-0060.R30

R627. An analysis run stays inside the run and daily budgets of ADR-0060.R20, under the company and installation caps of ADR-0050.R22, with the reservation of ADR-0050.R23. A cheap classification model routes; the data Q&A and analysis seats only plan and explain. A run makes at most three plan attempts with two lookups each and one explanation retry, and never explores many queries.
Source: ADR-0060.R30

### Floors of spec 03 for analysis runs

R628. Every query of an analysis run is checked against the intersection of the agent type and its human (ADR-0050.R31), with the human's record scope and owner scope, per fact view (ADR-0060.R13).
Source: ADR-0060.R31

R629. Agent runs receive member labels labelled `personal` as handles (`m1`, `m2`); the gateway would remove them anyway (ADR-0050.R9). The narrative plan names no member at all: code renders members from the rows of the facts, so names never reach a model and never come back from one.
Source: ADR-0060.R31

R630. A question is personal by label and is logged when sent. It is blocked, and the run ends `routing_blocked`, when the per-request gate of ADR-0063.R15 and ADR-0063.R17 does not pass it (ADR-0060.R21, ADR-0060.R21.N1).
Source: ADR-0060.R31

R631. Stored answers hold member keys, never labels, and are readable only by the asker and by holders of `read_analysis_debug` (ADR-0060.R21).
Source: ADR-0060.R31

R632. No fact holds untrusted text, and the agent type may not read untrusted text. No fact reads audit tables (ADR-0050.R50).
Source: ADR-0060.R31

R633. Agents never export (ADR-0060.R17), never post and never send.
Source: ADR-0060.R31

R634. Phase 1 has no personal measure. Suppression of small cells for personal measures comes after Phase 1.
Source: ADR-0060.R31

### Screens

R635. The analysis screens follow ADR-0040 and DS-30. The analysis builder shows measures, dimensions and filters as chips from `ListAnalysisCatalog`; the plan is the builder's state. Users without `start_agent:analysis`, such as the sales clerk of the seed, analyse in the builder.
Source: ADR-0060.R32

R636. The answer view shows: the restatement; the table or chart; the key facts, each figure clickable (its drill handle); the narrative sentences rendered by code, with member chips and citation markers that open the cited fact; a "how this was computed" fold with the plan as chips and the SQL; the scope note; the truncation note; the badge; `as_of`.
Source: ADR-0060.R32

R637. Saved analyses and KPIs appear as lists and tiles and are run on open.
Source: ADR-0060.R32

R638. The client does no arithmetic (ADR-0040.R2): charts plot server cells; totals, shares and changes are server cells.
Source: ADR-0060.R32

### Measures and dimensions of Phase 1

R639. The Phase 1 measures are the rows of the catalog `analysis-measures.csv`, by fact (field class, aggregation or additivity in parentheses):
- `journal_line_overview`: `net_revenue`, `revenue_deduction`, `cost_of_goods_sold` (`cost`), `gross_profit` (difference, `margin`), `gross_margin_percent` (ratio, `margin`), `operating_expense` (selling and administrative expense), `ledger_debit_turnover`, `ledger_credit_turnover`, `ledger_net_turnover`;
- `system_account_turnover`: `ledger_closing_balance` (semi-additive over `posting_period`);
- `sales_line_overview`: `sales_net_amount`, `sales_line_amount` (transaction currency), `sales_quantity`, `sales_cost` (`cost`), `sales_margin` (`margin`), `sales_margin_percent` (ratio, `margin`), `sales_document_count`, `sales_customer_count`;
- `purchase_line_overview`: `purchase_net_amount`, `purchase_line_amount` (transaction currency), `purchase_quantity`;
- `open_item_overview`: `receivable_open_amount`, `receivable_overdue_amount`, `payable_open_amount`, `payable_overdue_amount`, `open_item_count` (all semi-additive over `as_of`);
- `stock_overview`: `stock_quantity`, `stock_value` (`cost`) (semi-additive over `as_of`);
- `stock_movement_overview`: `stock_receipt_quantity`, `stock_issue_quantity`, `stock_movement_value` (`cost`);
- `production_output_overview`: `production_output_quantity`, `production_scrap_quantity`, `production_order_count`;
- `production_variance_overview`: `production_variance_amount` (`cost`).
Source: ADR-0060.R33

R640. The profit-and-loss measures exclude closing and migration entries. The ledger turnover measures exclude migration entries, as the turnover of ADR-0049.R6 does.
Source: ADR-0060.R33

R641. `sales_net_amount` and `purchase_net_amount` are the lines' posted net amounts in company currency, as their journal lines carry them. `net_revenue` is the ledger's figure, which also holds manual entries and deductions, so "sales" is an ambiguous term between them (ADR-0060.R2). `sales_line_amount` and `purchase_line_amount` are in the document's currency.
Source: ADR-0060.R33

R642. The Phase 1 dimensions are the rows of the catalog `analysis-dimensions.csv`: `posting_date`, `document_date`, `due_date`, `posting_period`; `partner`, `partner_group`, `salesperson`; `item`, `product`, `item_group`; `warehouse`, `site`, `branch`; `business_unit`; `payment_method`; `system_account`, `account`, `cost_center`, `project`; `currency`, `document_type`, `movement_type` (kind `catalog`); `overdue_bucket` (`not_due`, `days_1_30`, `days_31_60`, `days_61_90`, `days_over_90`, from days overdue at the business date), `variance_category` (kind `enum`); `production_order`.
Source: ADR-0060.R34, ADR-0060.R34.N1, ADR-0060.R34.N3

R643. `site` is a dimension of kind `entity` and the parent of `warehouse`; transit and goods-sent warehouses take the site of their valuation warehouse. `payment_method` is a dimension of kind `entity` on sales and purchase lines.
Source: ADR-0060.R34.N1

R644. In the hierarchy list of ADR-0060.R5 the pair is `warehouse` → `site`, not `warehouse` → `branch`, as `analysis-dimensions.csv` has it; `site` has no parent in the catalog.
Source: ADR-0060.R34.N2

R645. `business_unit` is a dimension of kind `entity`, a tree over `parent_id`, offered by `journal_line_overview` and `system_account_turnover`. It groups by the posted value only.
Source: ADR-0060.R34.N3

R646. The dimension `business_unit` has kind `entity`, column `business_unit_id`, a `business_unit_path` column for its tree over `parent_id`, low cardinality and label `internal` (ADR-0060.R5, ADR-0060.R34). The grain of the facts `journal_line_overview` and `system_account_turnover` gains the unit (ADR-0050.R53). Balance-sheet lines and P&L lines without a unit form the member `none`. `net_revenue`, `cost_of_goods_sold`, `gross_profit` and the other P&L measures answer per unit with no new measure.
Source: ADR-0069.R16

### Invariants of ADR-0060

R647. The analysis invariants lie in the reporting block `INV-400` to INV-499 (ADR-0049.R31) and are first checked at step 5 with the first agent (ADR-0050.R55). `INV-410`, `INV-411` and `INV-412` have area `reporting`; `INV-413` and `INV-414` have area `safety`.
Source: ADR-0060.R35

R648. `INV-410`: every drillable cell equals its drill rows by the table of ADR-0060.R16: the sum of their contributions for sums, counts, differences, totals, subtotals and contribution rows, the number of distinct keys for distinct counts, and the opening row plus the lines for balances, at the same snapshot.
Source: ADR-0060.R35

R649. `INV-411`: for full scope, every range and every system account subtree, each ledger measure equals the turnover measure of ADR-0049.R6 over the operational accounts mapped to that subtree for the same range and `special_periods` option, in every regime. The compared measure is `change` for the net measures and their signed forms, and `debit_turnover` and `credit_turnover` for the side measures; the profit-and-loss measures use `closing_entries=exclude`, and migration entries are left out. Statement lines are not claimed, since a line may split a measure by side or partner.
Source: ADR-0060.R35

R650. `INV-412`: every total, subtotal and other row equals the aggregation of its fact rows, never a sum of non-additive cells; no total row adds values of different currencies or inventory units; the reconciliation row of every contribution plan is zero.
Source: ADR-0060.R35

R651. `INV-413`: every user-visible sentence of an analysis answer is rendered by code, either from a key-fact template or from a claim template whose precondition held on the served cells; every stored narrative plan holds only claim codes, roles and handles. `INV-414`: every answer recorded with badge `verified` has an `analysis_plan_hash` equal, after removing filters on open dimensions, to a saved analysis version or analysis example that was verified at its recorded_at.
Source: ADR-0060.R35

### Catalog rows of ADR-0060

R652. ADR-0060 adds the catalogs `analysis-measures.csv` and `analysis-dimensions.csv` (owner DS-33). Its error codes (DS-04) are, by class:
- validation: `analysis_plan_invalid`, `unknown_measure`, `unknown_dimension`, `dimension_not_shared`, `fan_out_refused`, `currency_mixed`, `unit_mixed`, `dimension_required`, `measure_not_additive`, `time_range_invalid`, `filter_value_unknown`;
- permission: `analysis_not_permitted`;
- precondition: `analysis_too_broad`, `analysis_data_not_ready`, `analysis_question_answered`.
Source: ADR-0060.R36

R653. The check results of the analysis layer are `analysis_scope_filtered`, `analysis_periods_open`, `analysis_rows_truncated`, `analysis_cell_changed` and `analysis_measure_deprecated`.
Source: ADR-0060.R36

R654. The agent run outcomes `answered`, `ambiguous_term`, `ambiguous_member`, `out_of_coverage`, `not_permitted`, `data_not_ready` and `too_broad` are added to `ck_agent_run_outcome` for state `completed`.
Source: ADR-0060.R36

R655. The work item kinds of module `query` are `analysis_answer_disputed` (subject `analysis_question`, owner `company_owner`, due `days:5`, resolved by a person) and `analysis_catalog_request` (subject `analysis_question`, owner `company_owner`, due `days:30`, resolved by a person).
Source: ADR-0060.R36

R656. The settings of the analysis layer are those of ADR-0060.R11, the retention key among them as `analysis.question_retention_days` (ADR-0060.R11.N1). The glossary gains: analysis catalog, fact, measure (analysis), additivity, basis, dimension (analysis), analysis plan, analysis plan hash, drill handle, variance contribution, reconciliation row, analysis question, abstention, key fact, narrative plan, claim template, claim precondition, named period, saved analysis, verified badge, KPI, analysis example.
Source: ADR-0060.R36

R657. Authorization of the analysis layer (ADR-0054), by leaf:
- `analysis_question` (below `reports`, module `query`): `CreateAnalysisQuestion`, `UpdateAnalysisFeedback` and `UpdateAnalysisAnswer` at `edit` (verb `Update`, ADR-0060.R21), the last for the human an analysis run acts for; `ListAnalysisQuestion` and `GetAnalysisQuestion` at `read`, own questions only;
- `general_access`: `CreateSavedAnalysis` and `UpdateSavedAnalysis` at `edit` (private analyses), `ListSavedAnalysis` and `GetSavedAnalysis` at `read`, with the analysis queries of ADR-0060.R14;
- `saved_analysis` (below `reports`, module `query`): `ListAnalysisExample` at `read`; the capability `share_saved_analysis`, `CreateAnalysisExample` and `UpdateAnalysisExample` at `edit`; `ReleaseSavedAnalysis` and `ReleaseAnalysisExample` at `post`;
- `analysis_debug` (below `administration`, module `query`): the capability `read_analysis_debug` at `full`, `none` in every template except `owner`;
- `agent_analysis` (below `agent`): `start_agent:analysis` at `edit`.
Source: ADR-0060.R36

R658. `t12_access.py` registers these leaves, the capabilities `share_saved_analysis` and `read_analysis_debug`, and the commands and queries of R657, and checks the expansion.
Source: ADR-0060.R36

R659. The role template rows are interim and flagged for the author: `analysis_question` at `edit` and `agent_analysis` at `edit` for the chief accountant, accountant, sales manager, purchasing manager and production planner; `saved_analysis` at `post` for the chief accountant and at `edit` for the other templates of that list; `analysis_debug` at `none` for the IT administrator. The owner and the IT administrator hold the rest through their parents.
Source: ADR-0060.R36

R660. The edge cases of ADR-0060 are `EC-150` to `EC-155` and `EC-170`; EC-171 to EC-179 are reserved for ADR-0060. `EC-150` is an owner-scoped clerk's total in the builder; `EC-151` a transaction-currency question over two currencies; `EC-152` margin asked without the class; `EC-153` revenue change by customer between an open and a locked month; `EC-154` a question outside the catalog; `EC-155` management revenue equal to the journal at month end; `EC-170` revenue over a year closed by closing entries and adjusted in a special period.
Source: ADR-0060.R36

### Lab check

R661. The lab check `t18_analysis.py` of the validation lab proves, pure, for explanations: the narrative plan's shape (offered handles only, none twice, no free-text field); a property test in which random plans with arbitrary strings in every field never put a model string into the output except resolved member labels; true and false cases of every claim precondition; dropped steps recorded; saved references by every role and by full coordinate, surviving reordered rows and dropping unresolvable or ambiguous references; ties marking no extreme; refusal or dropping of a cell of two dimensions, mixed measures or one fact twice in a direction pair, mixed-sign and zero-total contributions, orphan connectors and one member row; key facts with the as-of date for balances; fail-closed languages.
Source: ADR-0060.R37

R662. `t18_analysis.py` proves, pure: both catalogs (field counts, unique codes, fewer than 40 measures, every selector a core system account, the turnover options on journal measures, every required and basis dimension offered by the fact, unique synonyms, field classes on ledger cost and margin); plan validation, where good plans pass and a bad plan is refused with each code of ADR-0060.R10; the compiler (one `SELECT` over declared views with bound values, an `is_in_scope` filter per fact, subtotals per pinned basis, truncation, per-bucket carry-forward); canonical hashes with definition hashes; relative dates; contributions on random data; the one-row, direction and superlative checks on citation references; named periods and the normalized stated-value check; exact-only matching; the stated-value check; the abstention mapping; the badge; scope-keyed caches; per-view grants.
Source: ADR-0060.R37

R663. With `--load`, on every DDL file from `load_all.py`, `t18_analysis.py` proves: the tables of DS-33-analysis.sql and their checks; agent runs completing with each analysis outcome; then a seeded company with posted documents, a closing entry, a special-period entry and a migration entry, lab views for three facts with per-view grants, and plans whose cells equal their drill rows by kind and whose management totals equal the turnover of ADR-0049 over the operational accounts; per-currency subtotals; facts under different owner scopes; scoped member lookup; per-bucket closing balances by period, by period and branch, by fiscal year, with special periods excluded and beside a second fact; an `opening_turnover` row in its own bucket and its scope.
Source: ADR-0060.R37

R664. `t18_analysis.py` does not cover the model, the gateway, the dispatcher, RLS of the views or the production read model.
Source: ADR-0060.R37

### Later work and appended notes

R665. These come later, each by an ordinary change or its own ADR:
- price-volume-mix for revenue and margin, with one documented convention and a zero remainder;
- segment search over two-dimension combinations with caps;
- KPI alerts, subscriptions and scheduled summaries;
- small-cell suppression for personal measures, with a company threshold;
- company-defined measures, with review and evaluation;
- historical open-item and stock balances as of past dates (Phase 1 reads them from the ledger's closing balances by system account);
- pre-aggregates for hot measures;
- export of the catalog to outside BI tools (an open semantic-model format);
- saved list views (ADR-0040.R6) and dashboards with layout beyond KPI tiles;
- the period-close assistant and the variance agent (ADR-0051.R29) as workflows on this layer.
Source: ADR-0060.R38

R666. ADR-0060 appends notes to: ADR-0022.R2; ADR-0027.R8; ADR-0035.R15; ADR-0038.R12; ADR-0040.R2 and ADR-0040.R6; ADR-0049.R16, ADR-0049.R18 and ADR-0049.R31; ADR-0050 rules 1, 12, 14, 17, 26, 28, 30, 31, 36, 44, 46, 48 (twice), 51, 53 and 54; ADR-0051 rules 4, 7, 9 and 29; ADR-0054.R15 and ADR-0054.R24.
Source: ADR-0060.R39

### Narrative mode

R667. The setting `analysis.narrative_mode` (ADR-0060.R23) takes `facts_only`, `claim_plan` or `free_prose`. The installation value is the maximum; a company may only lower it. The default is `claim_plan`.
Source: ADR-0063.R25

R668. `free_prose` is not selectable in Phase 1: it is outside the bounds. It unlocks for a language and model version only when the evaluation suite shows at least 80% of ordinary sentences accepted and zero accepted sentences with an unbacked number, rank or direction. Even then prose is labelled model-written, shown beside the key facts, and dropped for the claim plan on any unbacked number. Free prose comes after Phase 1, gated in this way.
Source: ADR-0063.R25

### Production views

R669. The production views of the query layer (the later views of ADR-0050.R51) are in schema `query`. Each has record scope on `production_warehouse_id` and owner scope as the document views. None has a partner column, an untrusted column or a field class column.
Source: ADR-0064.R13

R670. `production_order_overview` is over the header, document state, execution state, version, revisions, G, Q, dates, received quantity and pegged due date; its subject column is `id`.
Source: ADR-0064.R13

R671. `production_order_component_overview` is over the component lines with the quantities and dates of ADR-0064.R5; its subject column is `production_order_id`.
Source: ADR-0064.R13

R672. `production_order_operation_overview` is over the operations with scheduled dates, expected quantity, confirmed yield and scrap, and activities against standards; its subject column is `production_order_id`.
Source: ADR-0064.R13

R673. `shop_floor_posting_overview` is over the lines of issues, confirmations and receipts with state, `entry_source` and posting date; its subject column is `production_order_id`.
Source: ADR-0064.R13

R674. A tainted run of scope `subject` on a production order passes `is_in_taint_scope` for rows whose subject column equals its subject. Reading an order's own lines as its subject is ADR-0064's reading of ADR-0050.R27, added to the grouped question on readings of spec 03 rule 1 (ADR-0062.R3 reads child rows the same way).
Source: ADR-0064.R13

R675. A capture draft a person posted keeps its effective taint (ADR-0029.R9), and the run that wrote it keeps its taint record. For agent-run callers, `shop_floor_posting_overview` and `ListProductionOrderVarianceDriver` return such rows as the numeric projection of ADR-0050.R28: IDs, document numbers, quantities, dates, states and codes, never free text. Such rows do not taint and are not filtered from a clean run, so `production` and `production_variance` see every posting and the drivers still sum (`INV-739`). This reading joins the grouped question on spec 03 rule 1.
Source: ADR-0064.R13

R676. Module queries stay with their modules: `ListWorkCenterLoad`, `GetProductionOrderStatus`, `GetAvailableToPromise`, `GetProjectedAvailability` and the queries of ADR-0064 rules 5 to 10 (ADR-0050.R52).
Source: ADR-0064.R13

### Composed queries

R683. `ListWorkCaseTimeline` is a query of module `query` (layer 5) over views in schema `query`. It composes, ordered by the `recorded_at` and ID of the source rows, with nothing copied:
- the origin (interaction or extraction) and the case's links;
- linked work items with their notes, claims and resolutions;
- agent run summaries (agent type, mode, outcome, taint, step count);
- document and change-proposal versions with actor kind, agent run, taint and clearance;
- approvals and policy decisions;
- audit records the caller may read (ADR-0038.R7).
Source: ADR-0066.R17

R684. `ListWorkCaseTimeline` returns untrusted fields only with `include_untrusted`. Returning one to an agent run taints it (ADR-0029.R10), but the timeline is on no agent tool list in Phase 1.
Source: ADR-0066.R17

R687. `GetOperationWorkspace` is a query of module `query` (layer 5, as ADR-0066.R17, because it composes several modules) and needs `production_order` at `read`. It returns what the tablet shows for one WO:
- instructions: attachments linked to the routing operation of the MO's snapshot revision (found by `routing_revision_id` and `operation_number`, no new column) and to the WO itself;
- components of this WO: required, issued, backflushed, ready and remaining;
- inspection due: open `in_process` inspection lots of ADR-0070 for this MO and operation number, read through `quality.contract`;
- actions from `ListAllowedCommand` (ADR-0040.R8): Start, Pause, Block, Confirm quantity (`CreateOperationConfirmation` and `PostOperationConfirmation` in a batch, with the proposed activities), Record scrap (a confirmation with yield 0), Issue extra component (ADR-0071.R3).
Source: ADR-0071.R14

R688. The tablet is a hand-built PWA screen (ADR-0040.R6); the client computes nothing (ADR-0040.R2).
Source: ADR-0071.R14

## Invariants

Only the rows this chunk owns. `INV-410`, `INV-412` and `INV-413` have their rows in chunk 3 (catalog source ADR-0060.R16, ADR-0060.R12 and ADR-0060.R18, ADR-0060.R23) and `INV-411` in chunk 2 (first catalog source ADR-0060.R4); R648 to R651 state them as rules.

| INV | Check point | Statement | Protects |
| --- | --- | --- | --- |
| `INV-414` | day | Every analysis answer recorded with badge `verified` has an `analysis_plan_hash` equal, after removing filters on open dimensions, to a saved analysis version or analysis example that was verified at its recorded_at. Area `safety`; keys `analysis_question`; first step 5. | R611, R651 |
| `INV-716` | day | No analysis answer was rendered in a narrative mode looser than the installation maximum or the company's value on that date, and none as `free_prose` in Phase 1. Area `platform`; keys `analysis_question`; first step 5. | R667, R668 |

Named by rules of this chunk and stated by their own modules: `INV-400` (area `reporting`, source ADR-0049.R8; named only as the start of the block in R647) and `INV-739` (area `production`, source ADR-0064.R10; R675). INV-793 (area `safety`, source ADR-0066.R13 and ADR-0066.R19) names `ListWorkCaseTimeline`.

## Edge cases

Only the row this chunk owns. `EC-150` to `EC-153` have their rows in chunk 3 and `EC-155` and `EC-170` in chunk 2 (the first rule of their catalog source); R660 names them all.

| EC | Name | Case | Outcome | Source |
| --- | --- | --- | --- | --- |
| `EC-154` | `analysis_out_of_coverage` | A question about a figure no measure holds abstains with `out_of_coverage`, names the nearest measures and offers a catalog request; no number is shown. Area `reporting`; first executable step 5. | `must_succeed` | ADR-0060.R24; R660 |

## Settings

| Key | Value type | Scopes | Core default | Used by |
| --- | --- | --- | --- | --- |
| `analysis.narrative_mode` | enum (bounds `facts_only`, `claim_plan`; order `free_prose` < `claim_plan` < `facts_only`) | `installation`; `company` | `claim_plan` | R667, R668 |

`analysis_result_cache_seconds` (R625) is a setting of ADR-0060.R11 that `settings.csv` does not hold; chunk 3 states ADR-0060.R11.

The row of `analysis.question_retention_days` is in chunk 3 (ADR-0060.R11.N1); ADR-0077.R14, a unit of `agents`, names it too.

Reads: `assist.max_cost_per_run` (named by ADR-0077.R14, a unit of `agents`).

## UI annotations

The sources of this chunk hold no ADR-0077 floorplan, title, facet or field annotation. They give:

- Work item kinds of module `query` (R655; neither is agent-resolvable): the table below.
- Screens (R635 to R638): the analysis builder, the answer view, and the lists and tiles of saved analyses and KPIs.
- Tiles: a KPI tile is a KPI run on open (R612, R637).
- `GetOperationWorkspace` serves a hand-built PWA screen (R688).

| Kind | Subject table | Owner | Due | Resolution | Rule |
| --- | --- | --- | --- | --- | --- |
| `analysis_answer_disputed` | `analysis_question` | `company_owner` | `days:5` | `person` | R655; raised by feedback `wrong` (ADR-0060.R21) |
| `analysis_catalog_request` | `analysis_question` | `company_owner` | `days:30` | `person` | R655; raised when the asker of an `out_of_coverage` abstention asks for the figure (ADR-0060.R24) |

## Conflicts

CONFLICT ADR-0060.R34: the rule's count and list of dimensions are extended by ADR-0060.R34.N1 (`site`, `payment_method`) and ADR-0060.R34.N3 (`business_unit`); R642 lists the current catalog rows without a count.
CONFLICT ADR-0060.R31: ADR-0060.R21.N1 governs how a question is blocked; the per-request gate of ADR-0063.R15 and ADR-0063.R17 stands in R630 and "blocked when the switch is on" is not restated.
CONFLICT ADR-0060.R34.N2: the note governs the hierarchy list of ADR-0060.R5, where `warehouse` → `site` stands in place of `warehouse` → `branch`; R644 states the current pair and chunk 2 applies it to ADR-0060.R5.

## Proposed (not law)

None

## Trace

| Source | Where |
| --- | --- |
| ADR-0060.R26 | R601-R611 |
| ADR-0060.R27 | R612 |
| ADR-0060.R28 | R613-R616 |
| ADR-0060.R29 | R617-R622 |
| ADR-0060.R30 | R623-R627 |
| ADR-0060.R31 | R628-R634 |
| ADR-0060.R32 | R635-R638 |
| ADR-0060.R33 | R639-R641 |
| ADR-0060.R34 | R642 |
| ADR-0060.R34.N1 | R642, R643 |
| ADR-0060.R34.N2 | R644 |
| ADR-0060.R34.N3 | R642, R645 |
| ADR-0060.R35 | R647-R651 |
| ADR-0060.R36 | R652-R660 |
| ADR-0060.R37 | R661-R664 |
| ADR-0060.R38 | R665 |
| ADR-0060.R39 | R666 |
| ADR-0063.R25 | R667, R668 |
| ADR-0064.R1 | ref: ADR-0064.R1 |
| ADR-0064.R1.N1 | ref: ADR-0064.R1.N1 |
| ADR-0064.R1.N2 | ref: ADR-0064.R1.N2 |
| ADR-0064.R13 | R669-R676 |
| ADR-0066.R17 | R683, R684 |
| ADR-0069.R16 | R646 |
| ADR-0071.R14 | R687, R688 |
| ADR-0077.R14 | ref: ADR-0077.R14 |
| ADR-0077.R14.N1 | ref: ADR-0077.R14.N1 |
