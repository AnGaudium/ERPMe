# ADR-0060: Agent-assisted reporting and analysis

Status: accepted (2026-11-15) under ADR-0005, reviewed by Claude Fable 5.2 (builder Claude Opus 5.5) after six review rounds. Design items: DS-33 (the analysis layer of the read-only query layer), DS-34 (the analysis agent), DS-30 (the analysis screens). Related decisions: D2, D8, D12, D16. Principles 3, 7, 10, 11, 12, 13. ADR-0004, ADR-0005, ADR-0007, ADR-0008, ADR-0010, ADR-0012, ADR-0014, ADR-0017, ADR-0022, ADR-0026, ADR-0027, ADR-0029, ADR-0035, ADR-0038, ADR-0040, ADR-0042, ADR-0044, ADR-0049, ADR-0050, ADR-0051, ADR-0053, ADR-0054, ADR-0055; spec 03, 14, 17.

## Decision

ADR-0050 gave agents and reports a read-only query layer: semantic views, record scope, owner scope, field classes and taint, read through `List<View>` pages of at most 200 rows for agents. It has no aggregation on request. A question such as "net revenue by item group by month" would make a model add rows itself, which Principle 13 forbids: every number shown comes from deterministic code. This ADR adds the missing layer and one agent type on top of it.

**A declared catalog.** Module `query` declares, as code versioned with the release, the facts (semantic views with a stated grain), the measures over them (aggregation, additivity, currency or unit basis, field class) and the dimensions (hierarchies, cardinality). Measures over accounts go through system accounts (ADR-0010) and follow ADR-0049's turnover rules for closing and migration entries, so the catalog is the same in every regime. Phase 1 ships 35 measures and 22 dimensions; companies do not add measures, they save analyses.

**A JSON plan is the only input.** People and agents describe an analysis as a plan: measures, dimensions, filters, time range and grain, comparison, sort and limit. Code validates the plan against the catalog and refuses with typed codes, compiles it to one read-only `SELECT` over the semantic views, and runs it under the asker's rights, fact by fact. `EvaluateAnalysisPlan` returns typed cells; `GetAnalysisPlanExplanation` returns the compiled SQL, the resolved dates and a scope note. Every number in an answer comes from this engine.

**Every cell drills down.** Each cell carries a drill handle that leads, level by level, to documents and journal lines, or to the cells it is computed from. A cell equals the sum of its drill rows, and management totals equal ADR-0049's turnover for the same system accounts, scope and range.

**The model plans and explains; code computes.** The agent type `analysis` is untainted and holds read tools only. A model turns the question into a plan, which code validates and may send back for repair; code runs it; code states every number as key facts from fixed templates, and the model only returns a narrative plan: an ordered list of claim template codes with fact handles, which code checks against the cells and renders. In Phase 1 no word the model writes reaches the person. When the agent cannot answer safely it abstains with a typed outcome.

**Saved analyses, KPIs and examples are company data.** Versioned and immutable once verified, with states `draft`, `verified` and `retired`. Verified ones run without a model. Verified question-and-plan pairs, the analysis examples, answer exact repeats, feed the planner and form the company's evaluation cases beside the core evaluation suite.

**Exact variance contributions.** Change between two periods is split by one dimension into exact additive contributions with a reconciliation row of zero. Production variances are read from ADR-0035's split, never remodelled.

No external semantic engine runs in the core, and agents still never export files.

### Rules

**Module and catalog**

1. Ownership (ADR-0022 rule 2; ADR-0050 rule 1):
   - **`query`** (layer 5) owns the analysis catalog, the validator, the compiler and the executor; the queries `EvaluateAnalysisPlan`, `GetAnalysisPlanExplanation`, `ListAnalysisCellRow`, `ListAnalysisResultRow`, `ListAnalysisCatalog`, `ListAnalysisDimensionMember`, `ListAnalysisQuestion`, `GetAnalysisQuestion`, `ListSavedAnalysis`, `GetSavedAnalysis` and `ListAnalysisExample`; the MCP resources of rule 14; and the tables `analysis_question`, `saved_analysis`, `saved_analysis_version` and `analysis_example` with their commands (DDL draft [DS-33-analysis.sql](../design/DS-33-analysis.sql)).
   - **Imports.** `query` imports `db`, `registry` and `agent_runs`, as before, and now also the `work` contract, to raise its two work item kinds (ADR-0042 rule 5). `work` is layer 2, so the import goes downward.
   - **`agents`** (layer 5) owns the `analysis` workflow (rules 20–25). It reaches `query` only through the dispatcher, as for every workflow; nothing in `agents` imports `query`.
   - **No external engine.** No semantic layer product (Cube, dbt Semantic Layer or the like) runs inside the core: it would duplicate record scope, owner scope, field classes and taint, which the views already enforce, and add a second security model. Exporting the catalog to such tools comes after Phase 1 (rule 38).
2. The catalog lives in `backend/erpme/query/analysis/catalog.py` beside the view declarations (ADR-0050 rule 45). It declares four kinds of object:
   - **Facts:** a semantic view of schema `query`, its grain (what one row is), its time dimensions, its scope columns as the view declares them, and whether it is owner-scoped (ADR-0054 rule 15). A fact view pre-joins every dimension column it offers along a declared many-to-one path, so the compiler never joins facts to dimension tables, except for member labels (rule 12).
   - **Measures:** rule 4.
   - **Dimensions:** rule 5.
   - **Ambiguous terms:** business words that name more than one measure (for example "sales", which may mean ledger revenue or document amounts), each with its candidate measures, used for clarification (rule 24).

   Every object has a definition hash: SHA-256 of its canonical declaration together with the declaration hash of its fact's view (columns and SQL, ADR-0050 rule 45) and the expansion of its selectors as resolved at evaluation (for `system_account:revenue`, the codes of the subtree in the core catalog). A changed view, or a new child account in a selected subtree, changes the hash. Two core catalogs mirror the code: [analysis-measures.csv](../catalogs/analysis-measures.csv) and [analysis-dimensions.csv](../catalogs/analysis-dimensions.csv), owner DS-33, seeded now and generated from the code once `query` exists, as the work item kinds are (ADR-0042). A CI test compares code and catalogs.
3. Facts of Phase 1:

   | Fact view | Grain | Time dimensions | Owner-scoped | Source |
   | --- | --- | --- | --- | --- |
   | `journal_line_overview` (new) | One posted journal line, or one `opening_turnover` row | `posting_date`, `posting_period` | yes, through its document | ADR-0014 lines with system account and its path, operational account, partner, item, branch, warehouse, cost center, project, salesperson, transaction and company amounts, and the flags `is_closing_entry` (ADR-0012 rule 18), `is_migration_entry` (an entry of a migration fiscal year, ADR-0044 rule 2) and `is_special_period` (ADR-0012 rule 2) |
   | `system_account_turnover` | One company, period, system account, branch, cost center, project and transaction currency | `posting_period` | no | ADR-0050 rule 53 |
   | `sales_line_overview` (new) | One posted sales invoice, sales return or credit note line, signed (returns and credits negative) | `posting_date`, `document_date` | yes | ADR-0047 lines with inventory quantity, transaction amount, posted company amount, unit cost (`cost`) and margin (`margin`) |
   | `purchase_line_overview` (new) | One posted purchase invoice, purchase return or purchase credit note line, signed | `posting_date`, `document_date` | yes | ADR-0047 |
   | `open_item_overview` | One open item, at the current snapshot | `document_date`, `due_date` | yes, through its origin document | ADR-0026; ADR-0050 rule 51 |
   | `stock_overview` | One stock row, at the current snapshot | — | no | ADR-0050 rule 51 |
   | `stock_movement_overview` (new) | One posted material document line | `posting_date` | yes, through its document | ADR-0020 |
   | `production_output_overview` (new) | One posted production receipt line or scrap quantity | `posting_date` | yes, through its document | ADR-0034 |
   | `production_variance_overview` (new) | One production order, period and variance category, with the order's output item, warehouse and branch as record scope columns | `posting_period` | no | ADR-0035 rule 15 split, stored (rule 19) |

   - **Opening turnover.** `journal_line_overview` also returns the company's `opening_turnover` rows (ADR-0049 rule 14) as rows with `row_source` `opening_turnover`, dated `opening_date`, with the account and system account they carry and no other dimension (member `none`). They count only in measures that exclude closing entries, as in ADR-0049 rule 14, and a range that cuts through an `opening_turnover` row's dates is refused (V14). So a fiscal year to date that straddles a mid-year cut-over is answered.
     - **Their own bucket.** A time breakdown finer than a row's span shows the row as its own member `~opening`, labelled with its dates ("before cut-over"), outside every month or week bucket and inside the total; it never lands in the cut-over month.
     - **Scope.** These rows have no document, owner or branch, so they are in scope only for a grant on the fact with owner scope `company` and no record scope; any narrower grant leaves them out and sets `is_scope_filtered`.
   - **Helper views.** `posting_period_dimension` (periods with their fiscal year, kind and order) and one line-dimension view per fact that reaches a dimension one-to-many (`open_item_line_dimension`: the items of an open item's origin document lines) carry no scope of their own: they are reference or key views, joined only on keys of fact rows that already passed `is_in_scope`. They are declared in `query` like the facts.
   - **New views** are ordinary additions to ADR-0050 rule 51's table, with column declarations, scope columns and taint columns like the others. They omit every `is_untrusted` column, so no fact taints a run.
   - **The business date** reaches the views as the session setting `erpme.business_date`, which the builder sets, so `is_overdue` and `overdue_bucket` call no volatile function (ADR-0050 rule 44).
4. A measure declares:
   - **Identity:** `code` (`snake_case`), a translated label and description, and synonyms (each synonym belongs to one measure across the catalog; a CI check).
   - **Fact and expression:** its fact; an aggregation (`sum`, `count`, `count_distinct`) over one column of the fact at the fact's grain, with a sign (`1` or `-1`); or a derived form computed after aggregation: `ratio` (numerator and denominator measures of the same fact) or `difference` (two measures of the same fact). A column repeated from a coarser grain (a header amount on a line view) may not be summed; a CI check reads the view declaration.
   - **Selectors:** fixed filters the measure always applies: a system account subtree (`system_account:revenue`), a control kind (`control_kind:receivable`), a kind (`kind:scrap`), a side, and the turnover options of ADR-0049 rules 6–7: `migration_entries:exclude` on every turnover measure over journal lines (migration entries are opening balances, not movements) and `closing_entries:exclude` on the profit-and-loss measures (so the closing to the income summary does not cancel them). Balance measures keep both kinds of entry. Selectors over accounts name only codes of the core catalog [system-accounts.csv](../catalogs/system-accounts.csv), never an operational account code, so a measure means the same in every regime (ADR-0053 rule 1).
   - **Additivity:** `additive`; `semi_additive`, with the one dimension it is not additive over (`posting_period` for balances: the value of a time bucket is its value at the bucket's end; `as_of` for current-snapshot measures, which sum freely over every attribute such as due date or document date); or `non_additive` (distinct counts and ratios: totals are recomputed from rows, never summed from cells).
   - **Basis:** `company_currency`; `transaction_currency` (requires the `currency` dimension or a filter on one currency); `inventory_unit` (requires `item` or `product` as a dimension or a filter on one of them, because each product has one inventory unit, ADR-0018 rule 9); `count`; or `percent` (ratios).
   - **Requires:** a dimension that must be grouped or filtered, besides those of the basis: the ledger turnover measures require `system_account`, since their sum over every account is zero.
   - **Field class** (`cost`, `margin` or none), **default time dimension**, and **status** (`certified` or `deprecated`).
   - **Field classes always.** `cost_of_goods_sold` carries `cost`, and `gross_profit` and `gross_margin_percent` carry `margin`, whatever the plan groups by. Grouped by item, partner or salesperson they would give unit cost and margin, which the line views protect. Statutory statements read the same accounts without a class (ADR-0049 rule 17) because a whole-company statement line reveals no unit figure; analysis can group, so it keeps the class.

   Example, three measures of the Phase 1 catalog:

   | Code | Fact | Expression | Additivity | Basis | Field class |
   | --- | --- | --- | --- | --- | --- |
   | `net_revenue` | `journal_line_overview` | sum of `company_amount`, sign −1, selectors `system_account:revenue`, `closing_entries:exclude`, `migration_entries:exclude` (the subtree includes the revenue deductions, which reduce it) | additive | company currency | — |
   | `stock_quantity` | `stock_overview` | sum of `quantity` | semi-additive over `as_of` | inventory unit (requires `item` or `product`) | — |
   | `sales_margin_percent` | `sales_line_overview` | ratio of `sales_margin` to `sales_net_amount` | non-additive | percent | `margin` |
5. A dimension declares:
   - **Identity:** `code`, label, description, synonyms.
   - **Kind:** `time` (with its grains); `entity` (members are record IDs); `catalog` (members are codes of a core catalog or reference table, such as system accounts, currencies, document types or movement types); or `enum` (members are codes from a closed list in the declaration).
   - **Column:** the column name that every fact offering the dimension uses for it, the same name in each (a CI check).
   - **Hierarchy:** its parent dimension (`item` → `product` → `item_group`; `partner` → `partner_group`; `warehouse` → `branch`; `account` → `system_account`), and for tree dimensions (`system_account`, whose codes form the tree of ADR-0010) a `path` column for subtree filters.
   - **Cardinality:** `low`, `high` or `identifier`, for the guard of rule 10.
   - **Member label:** the label view and its data label: `internal`, or `personal_by_row` where a member may be a person (partners of kind `individual`, employees; ADR-0019 rule 7).
   - **Facts:** the facts that offer it along a many-to-one path; and the facts that reach it only one-to-many (for example `item` from `open_item_overview` through the origin document's lines), where it may filter (compiled to `EXISTS`) but never group.
   - **Weeks** are ISO weeks, starting on Monday.

   Example, three dimensions of the Phase 1 catalog:

   | Code | Kind | Hierarchy | Cardinality | Member label | Facts |
   | --- | --- | --- | --- | --- | --- |
   | `posting_date` | time; grains `day`, `week`, `month`, `quarter`, `year` (calendar) | — | low | — | journal lines, sales and purchase lines, stock movements, production output |
   | `item_group` | entity | top of `item_group` → `product` → `item` | low | internal | journal lines, sales and purchase lines, stock, stock movements, production output and variances |
   | `partner` | entity | below `partner_group` | high | personal by row | journal lines, sales and purchase lines, open items |

   Fiscal grains come from the dimension `posting_period` (`posting_period`, `fiscal_year`), which follows the company's fiscal calendar (ADR-0007).
6. Catalog rules:
   - **Code, not company data.** The core catalog changes only with a release. Its version is the release version and its content hash is part of every result (rule 15). A company adds no measure in Phase 1; it saves analyses (rule 26).
   - **One certified measure per business term.** Synonyms are unique across measures; a word that fits several measures is an ambiguous term (rule 2), never a synonym of one.
   - **Changed definitions.** A release that changes a measure's or dimension's declaration changes its definition hash, so every saved analysis version and example that names it loses its verified badge until a person releases it again (rule 26).
   - **Deprecation.** A measure is never removed while a saved analysis version names it. A deprecated measure still runs for saved analyses, with the check result `analysis_measure_deprecated`, and the planner never uses it.
   - **Neutral core.** Measures, dimensions and the reconciliation invariant use system accounts, control kinds and core enumerations only. A localization package adds no measure and changes none; its operational accounts appear only as members of the dimension `account` (rule 5).
   - **CI checks:** every measure's fact, column, selector and required dimension exist; every system account named by a selector is a code of `system-accounts.csv`; every profit-and-loss measure over journal lines excludes closing entries and every turnover measure over journal lines excludes migration entries; every dimension column exists in each fact that offers it; no fact offers a dimension along a one-to-many path except as declared; no dimension reads an `is_untrusted` or `is_secret` column; synonyms are unique; the catalogs equal the code.

**The analysis plan**

7. The plan, `plan_version` 1, is a JSON object validated by a pydantic model (unknown fields rejected, ADR-0008 rule 3):

   ```json
   {
     "plan_version": 1,
     "measures": ["net_revenue"],
     "dimensions": [{"dimension": "item_group"}, {"dimension": "posting_date", "grain": "month"}],
     "filters": [{"dimension": "branch", "op": "in", "values": ["<branch id>"]},
                 {"dimension": "system_account", "op": "in_subtree", "values": ["revenue_goods"]}],
     "time": {"dimension": "posting_date",
              "range": {"relative": "last_fiscal_quarter"},
              "compare": {"relative": "previous_period"},
              "special_periods": "include"},
     "derived": [{"op": "difference", "of": "net_revenue"}],
     "contributions": null,
     "sort": [{"by": "net_revenue", "dir": "desc"}],
     "limit": 20,
     "with_other_row": true,
     "with_total_row": true
   }
   ```

   - **`measures`:** 1 to 5 measure codes.
   - **`dimensions`:** 0 to 3, each a dimension code, with `grain` for time dimensions.
   - **`filters`:** each a dimension, an operator and member keys: `eq`, `in` and `not_in` (at most 100 values, ADR-0050 rule 47), and `in_subtree` for tree dimensions. Entity members are IDs and catalog and enum members are codes, found through `ListAnalysisDimensionMember` or the catalog, never names.
   - **`time`:** the time dimension; a `range` (`{"from", "to"}` dates, a named period, or `{"relative": …}`, rule 8); an optional `compare` (a second range, or `previous_period`, `previous_month_same_days` or `same_period_last_year`); `special_periods` (`include`, the default, or `exclude`, as ADR-0049 rule 13); and for semi-additive measures `as_of`, which defaults to the end of the range.
   - **`derived`:** `difference`, `growth` (a ratio to the comparison, shown as percent) or `share_of_total`, each `of` a measure; computed by the engine after aggregation, never by a model.
   - **`contributions`:** `{"measure", "dimension", "top"}` for rule 18; it needs `time.compare`.
   - **`sort`, `limit`, `with_other_row`, `with_total_row`:** sort only by a measure or a dimension of the plan; `limit` at most 1,000 for people and 50 for agent runs. A `limit` without the other row truncates (rule 15).
8. Time:
   - **Relative ranges,** a closed list: `today`, `yesterday`, `this_week`, `last_week`, `month_to_date`, `this_month`, `last_month`, `this_calendar_quarter`, `last_calendar_quarter`, `this_calendar_year`, `last_calendar_year`, `this_fiscal_quarter`, `last_fiscal_quarter`, `fiscal_year_to_date`, `this_fiscal_year`, `last_fiscal_year`, and with `n` from 1 to the span limit: `last_n_days`, `last_n_weeks` (whole ISO weeks before the current one) and `last_n_months` (whole months before the current one; twelve gives the rolling year).
   - **Named periods:** `{"month": "2026-03"}`, `{"calendar_quarter": "2026-Q1"}`, `{"calendar_year": 2025}`, `{"fiscal_quarter": "2026-Q2"}` (the second quarter of the fiscal year that starts in 2026) and `{"fiscal_year": 2026}` (the fiscal year that starts in 2026). They let a plan name "March 2026" or "Q1 2026" without computing dates; an absolute `from`/`to` range is for dates a person typed.
   - **Resolution.** Code resolves relative ranges and named periods against the company's business date (`clock.today`, ADR-0007 rule 15) and fiscal calendar, and echoes the absolute dates in the result. A model never computes a date: an absolute date in an agent's plan must be stated in the question (rule 22).
   - **Comparison.** `previous_period` is the range of the same length ending the day before; for whole months, quarters or years it is the previous block of the same length. `previous_month_same_days` shifts the range by one month, day for day (a month to date against the same days of the previous month), with days beyond the month's end clamped to its last day. `same_period_last_year` shifts the range by one year, with 29 February mapped to 28 February.
   - **Which date.** Every plan names its time dimension (posting date, document date, due date or posting period), and the result restates it, so "last month" is never ambiguous between dates.
9. Canonical form and hashes (named apart from ADR-0008's command `plan` and `plan_hash`):
   - **Canonical form:** keys sorted, lists of measures, filters and filter values sorted, defaults filled, canonical numbers and dates (ADR-0006 rule 13; ADR-0007 rule 3).
   - **`analysis_plan_hash`:** SHA-256 of the canonical plan as written, relative dates kept, together with the definition hashes of every catalog object it names. It identifies an analysis for saved analyses, examples and the verified badge, so a verified "last month" stays verified every month, and a changed measure definition ends the verification.
   - **`analysis_resolved_hash`:** SHA-256 of the canonical plan with absolute dates, plus the catalog hash. It keys the result cache (rule 30).

**Validation**

10. Code validates every plan, from people and agents alike, in this order. It collects all violations, returns them in `details.violations` (code, path, message) so a planner can repair them in one round, and answers with the first one's code:

    | # | Check | Code | Category |
    | --- | --- | --- | --- |
    | V1 | The plan matches the model: version, types, list sizes, `limit`, operators per dimension kind, a sort key in the plan | `analysis_plan_invalid` | validation |
    | V2 | Every measure exists and is certified, or deprecated and named by the saved analysis being run | `unknown_measure` | validation |
    | V3 | Every dimension, filter dimension, sort key and time dimension exists, and grains are allowed for it | `unknown_dimension` | validation |
    | V4 | The actor may read every fact (the fact view's `List` permission), holds the field class of every measure named or computed from, and for a fact that is not owner-scoped holds an assignment with owner scope `branch` or `company` (ADR-0054 rule 15); `details` name what is missing, never data | `analysis_not_permitted` | permission |
    | V5 | Every grouping and filter dimension is offered by every measure's fact (common dimensions) | `dimension_not_shared` | validation |
    | V6 | No grouping or contribution dimension reaches a fact only one-to-many | `fan_out_refused` | validation |
    | V7 | A transaction-currency measure has `currency` as a dimension or a filter on one currency; a contribution plan on one has the filter; no derived measure mixes bases | `currency_mixed` | validation |
    | V8 | An inventory-unit measure has `item` or `product` as a dimension or a filter on one of them; a contribution plan on one has the filter | `unit_mixed` | validation |
    | V9 | Every dimension a measure requires is grouped or filtered | `dimension_required` | validation |
    | V10 | `contributions` name an additive measure; `share_of_total` an additive or semi-additive one | `measure_not_additive` | validation |
    | V11 | A range is present where a measure's fact has time dimensions, ordered, and valid in the relative list or as a named period; a comparison has a range; contributions have a comparison | `time_range_invalid` | validation |
    | V12 | Filter members exist and lie in the actor's scope; catalog and enum values are in their lists | `filter_value_unknown` | validation |
    | V13 | Cardinality and cost: the range spans at most `analysis_max_range_months`; at most one `high` or `identifier` grouping dimension, which needs `limit`; at most `analysis_max_cells` cells (`analysis_agent_max_cells` for agent runs); the rows the database planner estimates its scan nodes read at most `analysis_max_estimated_rows` | `analysis_too_broad` | precondition |
    | V14 | The data exists: the range does not start before the company's cut-over date (ADR-0044 rule 10) unless `opening_turnover` rows cover it whole for the measures that read them, no migration run is loading the company, and a current-snapshot fact is not asked as of a past date | `analysis_data_not_ready` | precondition |

    - **Basis pinned by grouping.** When `currency` or `item`/`product` pins a measure's basis as a grouped dimension, the engine computes totals, other rows, shares and ranks per member of that dimension and omits the grand total (rule 12). When a filter pins it, nothing changes.
    - **Not refusals.** A range with periods not locked in `general` gives the check result `analysis_periods_open`; rows left out by scope give `analysis_scope_filtered` (rule 13); rows cut by `limit` give `analysis_rows_truncated` (rule 15).
    - **The same path.** The UI's analysis builder, saved analyses, MCP clients and agents send plans to the same validator. There is no second path.
11. Settings (installation; companies may lower them, never raise them): `analysis_max_cells` (5,000), `analysis_agent_max_cells` (500), `analysis_max_range_months` (60), `analysis_max_estimated_rows` (5,000,000), `analysis_result_cache_seconds` (300), `analysis_question_retention_days` (400). The values are the agent's proposal, flagged for the author.

**Compile and execute**

12. The compile-to-SQL contract (ADR-0050 rule 44):
    - **One statement.** The compiler emits one statement whose top level is a `SELECT`; read-only common table expressions are allowed, data-modifying ones never. The CI test of ADR-0050 rule 44 covers it.
    - **Only declared names.** It reads only fact views and label views of schema `query` that the catalog names. Every identifier comes from the catalog, never from plan text; every value is a bound parameter. A CI property test generates plans and checks that no plan string appears in the SQL text.
    - **Shape.** One aggregation per fact over its view, filtered by that view's `is_in_scope`, the plan's filters and, when every measure of the fact has a selector, by any of them (so rows no measure selects form no empty member); time buckets by `date_trunc` on the declared date column or by the posting period; plans with measures of several facts join the per-fact aggregations on the dimension keys (no fact rows are joined to each other, so nothing fans out); member labels by a left join to the label view after aggregation; derived measures and contributions after aggregation.
    - **Totals and other rows.** Total rows come from `GROUPING SETS`, and the other row from ranking the high-cardinality members within the other grouped members (one currency, one month) and re-aggregating the tail from the fact rows; an other row's drill handle carries the top keys of its group. Non-additive totals and other rows are always recomputed from rows, never summed from cells.
    - **Pinned bases.** When a grouped dimension pins a measure's basis (V7, V8), the grouping sets end at that dimension: subtotals per currency or product, row kind `subtotal`, and no grand total; shares and ranks are taken within the same member. When the pinned dimension is the only grouped dimension, each member row already is its subtotal, so no subtotal rows are added.
    - **Semi-additive measures over time.** Whenever a plan groups a balance by its non-additive dimension, also beside measures of another fact (the per-bucket path then runs inside that fact's own aggregation, and the facts join on the bucket keys), the engine takes for each bucket, per key of the fact (system account, branch, cost center, project, currency), the latest row at or before the bucket's end in period order (a special period after the regular period that ends on the same day), carrying forward a balance through periods without movement (ADR-0014 rule 18 writes no row for those). Other grouped dimensions (branch, system account) are part of the key, so each group carries its own balance; a group without rows in a bucket keeps its last value. The total over time is the value of the last bucket, never a sum of buckets.
      - **Bucket ends.** A posting-period bucket ends with its period; a fiscal-year bucket ends after the year's last special period, so it holds the year-end adjustments and closing.
      - **`special_periods: exclude`** leaves out the special-period rows of the fiscal year that ends on the range's `to`, and nothing else (ADR-0049 rule 13): those buckets disappear, and the balance at the year's end is taken before them. Special periods of earlier years stay in the balance.
    - **Opening buckets.** `opening_turnover` rows form the member `~opening` of a time breakdown (rule 3).
    - **Null members.** Rows without a member (a journal line without a partner) form the member `none`, which is shown and drillable, so totals reconcile.
    - **Exact numbers.** Sums run in `numeric` on the stored amounts and quantities. Ratios are rounded half up to 6 decimals, percent to 2, by the engine only (ADR-0006).
13. Execution:
    - **Role and snapshot.** Under `erpme_readonly` in a read-only `REPEATABLE READ` transaction, so all cells come from one snapshot; `as_of` is that transaction's start. Statement timeout 10 seconds for agent runs and 30 seconds otherwise (ADR-0050 rule 43); a timeout answers `timeout`.
    - **Scope per fact.** ADR-0054 rule 15 evaluates scope per assignment and per permission, and one plan may read several fact views granted by different assignments. So `erpme.read_grants` is always a map keyed by view name, for every query of the layer (a `List<View>` query sets a one-entry map), and never the list of ADR-0050 rule 48's first note: for each fact view of the plan, the actor's assignments in force that grant that view's `List` permission (for an agent run, those of its human), each with its record scope, owner scope, organization set and user (ADR-0050 rule 48 note). Each view's `is_in_scope` reads its own entry, never another view's, so a grant for one fact never widens another. A view without an entry sees no rows.
    - **Agent runs.** For an analysis plan, the fact-view permissions and their grants are those of the run's human alone. The agent type's limit on facts is that `EvaluateAnalysisPlan`, `GetAnalysisPlanExplanation`, `ListAnalysisCellRow` and `ListAnalysisDimensionMember` are on its tool list; it holds no `List<fact view>` permission and reaches facts only through these queries (a note on ADR-0050 rule 31). Field classes stay the intersection of the agent type's and the human's (ADR-0050 rule 12 note).
    - **Scope flag.** Every fact aggregation filters on `is_in_scope`, so totals are totals of the rows the actor may see, and one `EXISTS` per fact sets `is_scope_filtered` with the check result `analysis_scope_filtered`. The answer says so in its scope note; a total is never presented as the company's when rows were left out.
    - **Field classes.** V4 refuses a measure whose class the actor lacks before any SQL runs, so a masked column never sums to a silent zero.
    - **Taint.** Facts omit untrusted columns, and aggregates do not taint (ADR-0050 rule 25), so analysis runs stay clean.
14. Queries (module `query`; ADR-0004 rule 21's computed-query exception, as ADR-0040 rule 8):
    - **Names.** `EvaluateAnalysisPlan` takes the glossary verb `Evaluate`, a query that computes a result from given inputs and stores nothing; the explanation is read as `GetAnalysisPlanExplanation`. Every query of this ADR is a `Get`, `List` or `Evaluate`.
    - **`EvaluateAnalysisPlan`** (plan; optional `saved_analysis_version_id`) → the result envelope (rule 15).
    - **`GetAnalysisPlanExplanation`** (plan) → the canonical plan, `analysis_plan_hash`, the resolved absolute dates, the validation result, the facts and views read, the compiled SQL text with its bound values listed apart, and the scope note (record scope, owner scope, field classes; which facts need owner scope `branch` or `company`). It runs no aggregation. Of the cost guard it returns only `within_limit` or the limit that tripped: planner statistics are table-wide and would hint at volumes beyond the caller's scope, so the raw estimate goes only to holders of the capability `read_analysis_debug`. The SQL is returned to every caller who may run the plan: it names only declared views and the caller's own values.
    - **`ListAnalysisCatalog`** → measures and dimensions with labels, synonyms, bases, hierarchies and the actor's permission on each. The MCP resources `erpme://query/measures`, `erpme://query/measures/<code>`, `erpme://query/dimensions` and `erpme://query/dimensions/<code>` describe the same metadata (ADR-0050 rule 46).
    - **`ListAnalysisDimensionMember`** (dimension, fact, search text, cursor) → members of one dimension: key, code and label, matched on code and label folded for case and diacritics (ADR-0050 rule 47). It needs the `List` permission of the named fact, which must offer the dimension, and returns only members that occur in that fact's rows within the caller's scope for it (rule 13), so nobody enumerates partners, employees or accounts beyond what they may read. It is the one lookup for filter members, so a plan never carries a name. For agent runs a label labelled `personal` comes back as a handle (rule 31).
      - **No oracle.** The response carries no `is_scope_filtered`, no count and no hint of members outside the scope: "no such member" and "outside your scope" are one identical empty answer, as V12.
      - **Timing residual.** The query's time still grows with the matching rows outside the scope, a weak channel. Its bounds: a search text of at least 3 characters, at most 20 members per page, at most two lookups per plan attempt for agent runs, and the run's budget.
      - **Members without rows.** A member with no rows in the fact (a new customer) is found only by a caller whose grant on the fact has owner scope `company` and no record scope and who also holds the `List` permission of the dimension's master data (for partners, `ListPartnerOverview`), who searches that master data; for anyone else the question abstains rather than answering zero.
    - **`ListAnalysisCellRow`** (rule 16) and **`ListAnalysisResultRow`** (rule 17).
    - **Questions and saved analyses:** `ListAnalysisQuestion` and `GetAnalysisQuestion` (rule 21); `ListSavedAnalysis`, `GetSavedAnalysis` and `ListAnalysisExample` (rules 26, 28).
    - **Permissions.** `EvaluateAnalysisPlan`, `GetAnalysisPlanExplanation`, `ListAnalysisCatalog`, `ListAnalysisDimensionMember`, `ListAnalysisCellRow` and `ListAnalysisResultRow` sit on the authorization leaf `general_access` at `read`: each checks the permission of every fact view it reads and the actor's scope (ADR-0054 rule 24 note). The other queries and the commands have leaves of their own (rule 36). All but `ListAnalysisResultRow` and `ListAnalysisQuestion` may be on agent tool lists.
15. The result envelope:
    - **Header:** canonical plan, `analysis_plan_hash`, `analysis_resolved_hash`, resolved dates, catalog version and hash, `as_of`, `is_scope_filtered`, `is_truncated`, `badge` (`verified` or `generated`, rule 26), `checks` (DS-04 format), row count.
    - **Rows:** each row has a `row_kind` (`member`, `other`, `subtotal`, `total`, `reconciliation`), the dimension members (key and label; a personal label is returned to people within their permissions and replaced by a handle for agent runs, rule 31) and one cell per measure and derived value.
    - **Key facts:** the facts code renders for the answer (rule 23), with their template codes and cells.
    - **Cells:** `cell_id` (`c1`, `c2`, … in row order), `cell_kind` (`value`, `change` for differences, growth and contributions, `share`, `ratio`), measure or derived code, value as a canonical decimal string, basis (currency code, unit code, `count` or `percent`), scale, the flags `is_max` and `is_min` set by code on complete results only, and the drill handle.
    - **Truncation.** A `limit` without the other row drops member rows beyond the limit, keeping totals over all rows; `is_truncated` is true and the check result `analysis_rows_truncated` names the limit. No cell of a truncated result carries `is_max`, `is_min` or a rank.
16. Drill handles:
    - **Handle.** A JSON object `{"analysis_plan_hash", "analysis_resolved_hash", "cell": {<dimension>: <member key>, …}, "measure", "cell_kind"}`, and for an other row `"other_excludes"`, the top member keys of its group. The members `none` and `other` are written `~none` and `~other`. A person or an agent can read it and build it again.
    - **Next level.** Drilling replaces each grouped dimension that has a child level by that child, with the cell's members as filters, which gives a new plan, run by `EvaluateAnalysisPlan` (`item_group` → `product` → `item`; `system_account` → its children → `account`; `year` → `quarter` → `month` → `day`).
    - **Rows behind each kind of cell,** listed by `ListAnalysisCellRow` (handle, cursor) by cursor (ADR-0008 rule 22) with document ID, number and type, date, line and the row's contribution:

      | Cell | Drill rows | Sum |
      | --- | --- | --- |
      | Sum of a base measure | The fact rows of the cell, each with its signed column value | Equals the cell |
      | Count | The rows, 1 each | Equals the cell |
      | Distinct count | The rows, with their distinct key | The number of distinct keys equals the cell |
      | `difference` (`gross_profit`) | The rows of both operands, each with its sign in the difference | Equals the cell |
      | `ratio`, `growth`, `share` | Not rows: the handles of its numerator and denominator (or base and comparison) cells, each drillable | — |
      | Contribution member or other row | The member's rows in P1 with their sign and in P0 negated | Equals the change |
      | Total and subtotal | All rows of the cell's group | Equals the cell |
      | Semi-additive balance (`ledger_closing_balance`) | An opening row (the balance at the end of the period before the range's first period, from the turnover rows) and the journal lines of the range, as ADR-0049 rule 10's books | Opening plus lines equals the cell |
      | Reconciliation | None; it is zero by INV-412 | — |

      For `journal_line_overview` and `system_account_turnover` the rows are journal lines, the contract of `ListReportLineContribution` (ADR-0049 rule 16). Rows end at documents, which open in their record view.
    - **Agent runs.** For agent runs `ListAnalysisCellRow` returns a numeric projection (ADR-0050 rule 28): IDs, document numbers and types, dates, accounts and contributions, no free text. Like aggregates, such rows do not taint and are not filtered from a clean run, so the sum holds for agents too.
    - **Same scope, new snapshot.** Drilling validates the plan again under the current actor and reads a new snapshot. If the cell's value differs from the handle's, the response carries `analysis_cell_changed` with both values.
17. Export (ADR-0050 rule 54):
    - **People.** `ListAnalysisResultRow` (plan) returns the result rows as a `List` query, so `CreateListExport` writes them to `.xlsx` unchanged: the consumer reruns the plan as the requester, with field classes, scope and `list_export_max_rows`.
    - **Agents never export.** `ListAnalysisResultRow` and `CreateListExport` are on no agent tool list (ADR-0050 rule 30). An agent's answer is shown in the UI, where the person may export it.

**Variance contributions**

18. Exact additive contributions:
    - **Input.** An additive measure M, a dimension D shared by M's fact, the range P1 (`time.range`), the comparison P0 (`time.compare`), `top` at most 25 (10 by default), and the plan's filters; a transaction-currency or inventory-unit M needs its basis pinned by a filter (V7, V8).
    - **Members.** For each member d of D in P0 or P1, including `none`: M₀(d) and M₁(d) (missing counts as 0) and Δ(d) = M₁(d) − M₀(d).
    - **Rows.** Members ranked by |Δ| descending, then by member key; the top rows; one `other` row with the sum of the rest; one `total` row with M₁ − M₀ computed directly from the fact rows of each period; and one `reconciliation` row, total Δ minus the sum of the member and other rows, which must be exactly zero. A non-zero reconciliation is an `internal_error`, never shown as an answer.
    - **Shares.** Each row's share of the total change, rounded half up to 4 decimals, is a derived cell; it is omitted when the total change is zero.
    - **Ratios** do not decompose additively. A contribution plan on a ratio or distinct count is refused with `measure_not_additive`; the planner may analyse the numerator and denominator instead.
19. Production variances are ADR-0035 rule 15's split (input price, input quantity, resource usage, scrap, lot size, remaining), computed by `production`'s variance function, the function behind `GetProductionOrderVariance`. The analysis layer never remodels them:
    - **Stored rows.** When the period's costing run settles a production order's period cost (ADR-0035), `production` writes the split per order, period and variance category to its read model `production_order_variance`, with the order's output item, warehouse and branch. Its DDL comes with the costing tables of DS-53 (a note in the DS-43-54 draft). `production_variance_overview` reads those rows only (ADR-0050 rule 52: a view never re-implements a module's figure).
    - **Postings.** Under actual costing variances are not posted (ADR-0035 rule 15). If the author chooses standard cost valuation, the posted variance lines become the source and the measure keeps its code.
    - **Deviation from the architect's decision 6,** stated for review: the decision says "posted variance lines". ADR-0035 rule 15 posts none under actual costing, so this ADR reads the stored split, which is the same figure, and keeps the posted lines for standard costing.

**The analysis agent**

20. The agent type `analysis` (ADR-0050 rule 12):
    - **Subjects and scope.** Scope kind `subject`: one `analysis_question` row (rule 21), or one `analysis_example` row for evaluation runs (rule 25). Questions are typed by a signed-in person of the company (`CreateAnalysisQuestion` is `human_only`) and are not outside content, so the run starts clean.
    - **Clean.** `may_read_untrusted: false`, so the run never taints (ADR-0050 rule 28).
    - **Field classes** declared: `cost` and `margin`. A run sees a class only when its human holds it too (ADR-0050 rule 12 note).
    - **Tool list.** Read tools for the LLM steps: `ListAnalysisCatalog`, `ListAnalysisDimensionMember`, `GetAnalysisPlanExplanation`, `ListSavedAnalysis`, `GetSavedAnalysis`, `ListAnalysisExample`. Workflow code also calls `EvaluateAnalysisPlan`, `ListAnalysisCellRow`, `GetAnalysisQuestion`, the command `UpdateAnalysisAnswer` and `CreateChangeProposal`. Nothing that posts, sends or exports.
    - **Seats** (spec 17): classification with personal data for the router (L1), which uses the cloud classification model while the routing switch is off (spec 17's reference seatmap); data Q&A for planning (L2); data Q&A for plain explanations and analysis for contribution plans (L3), which receive no question text. The question is personal (rule 21), so a seat whose class is below `personal` never receives it (ADR-0050 rule 9).
    - **Budgets** per run (ADR-0050 rule 22; maximums, flagged for the author): 14 LLM calls (one route, three plan attempts with at most two member lookups each, two explanations: 12; and two of rule 35's schema retries), 40 tool calls, 140,000 input tokens, 12,000 output tokens, USD 0.95, 180 seconds, 2,000 rows read (result rows count); per company and business date USD 18 and 300 runs. A run that needs more ends `budget_exceeded` and its question `failed`.
    - **Constants** of the version: at most 3 plan attempts (one plan and two repairs), at most 2 member lookups per attempt, at most 5 examples as context, defaults `limit` 20 and `top` 10.
    - **Who may start it:** holders of `start_agent:analysis` (leaf `agent_analysis`, rule 36).
21. Questions:
    - **`analysis_question`** (company data, owner `query`): the asker, the question text (at most 2,000 characters), its language, the run, the state (`open`, `answered`, `abstained`, `failed`), the outcome or, for a failed run, its stop reason, the plan and its hashes, the badge, the key facts, the narrative plan with the steps code dropped, the clarification options, the result as shown (rows, cells and member keys, never member labels, which are resolved again at display under the viewer's rights), `as_of`, and the asker's feedback (`helpful` or `wrong`, with a note).
    - **Label.** The question text, trigger questions, example questions and feedback notes are labelled `personal`: a question may name a person, as a bank description may (ADR-0050 rule 9). With the routing switch off, a question goes to the router and planner seats and every call is logged in the processing log (ADR-0050 rule 10). With the switch on, the gateway removes it, the router step is not sent, and the run ends `routing_blocked`; exact matches with verified examples and saved analyses (rule 22, D2), opening saved analyses and the builder still work, because they need no model. The alternative reading, `internal`, is the author's open question.
    - **Retention.** Question text and feedback notes are blanked after `analysis_question_retention_days`, and when the asker's user account is erased; the outcome, plan and hashes stay.
    - **Commands** (leaf `analysis_question`, rule 36): `CreateAnalysisQuestion` (effect class `other`, `human_only`) creates the row, and the UI then sends `StartAgentRun` with the row as subject, acting for the asker (ADR-0050 rule 15); `UpdateAnalysisAnswer` (effect class `other`, `is_draft_only`, on the `analysis` tool list for workflow code only) writes the outcome, plan, badge, key facts, narrative plan, dropped steps and result to the run's own question, once, and refuses a question of another run or already answered (`analysis_question_answered`); `UpdateAnalysisFeedback` (the asker), once: feedback is never changed or cleared after it is given. The verb is `Update` (an edit of fields of the question), not `Set`, whose glossary meaning is replacing a whole list. Feedback `wrong` raises `analysis_answer_disputed` (owner `company_owner`).
    - **Failed runs.** A consumer of `AgentRunCompleted` in `query` sets a question whose run stopped (`budget_exceeded`, `time_exceeded`, `output_invalid`, `provider_unavailable`, `resume_diverged`, `crashed`, `denials_repeated`, or `canceled`) to `failed` with that reason. ADR-0050's `agent_run_stopped` item stays one per agent type, outcome and business date, never one per question.
    - **Who reads answers.** A question and its stored result are readable only by the asker and by holders of the capability `read_analysis_debug`. Whoever handles a dispute reruns the plan under their own rights; the stored cells were computed under the asker's scope and field classes.
22. Steps:
    - **D1 `load`:** the question; the catalog; the verified saved analyses and examples the asker may see: those with visibility `company`, and the asker's own private ones. Another user's private analysis is never matched, offered as a hint, or revealed by a badge.
    - **D2 `match_verified`:** a normalized question (Unicode case folding, whitespace collapsed, trailing punctuation dropped; letters with diacritics stay distinct, because in several languages they distinguish words) equal to a verified example's or a verified saved analysis version's trigger question gives that plan, with no model. Only exact equality is accepted: similar questions ("net revenue last month by customer" against "net revenue last month") differ in what they ask. A hit skips L1 and L2. D2 and L1 read only the set of D1.
    - **L1 `route`** (seat classification with personal data): input the question and up to 5 similar verified questions as handles, ranked by `rank_candidates` (ADR-0051 rule 1) as hints only. Output `AnalysisRouteOutput`: `kind` (`analysis`, `not_analysis`, `candidate`), `candidate` (a handle or none), `language`. Checks: the handle was offered. `candidate` takes that plan; its badge is computed from its hash like every other (rule 26); `not_analysis` (a request to post, send or change data) ends the run with `not_applicable` and a note written by code that points to the right screen.
    - **L2 `plan`** (seat data Q&A): input the question, the business date and fiscal calendar facts, the catalog entries retrieved by synonym and token match (at most 15 measures, every dimension), the measures the human may not read named as such, and at most 5 nearest verified examples. Read tool `ListAnalysisDimensionMember` for member lookups, at most two per attempt. Output `AnalysisPlanOutput`: `kind` (`plan`, `clarify`, `clarify_member`, `out_of_coverage`, `not_permitted`), with `plan`, or `term` and 2–4 `options`, or a lookup handle, or `nearest` (measure codes). Checks:
      - codes exist; options and nearest name catalog objects; `term` is a catalog term (an ambiguous term or a synonym);
      - member keys came from a lookup result of this run (ADR-0050 rule 36);
      - stated values: every absolute date, named period, `n`, `limit` and `top` in the plan appears in the question (ADR-0050 rule 36's stated-value check). The question is normalized first: number words to digits and month names to month numbers through the language's lists, dates parsed in ISO form and the company's locale formats. A named period needs its year in the question and its month or quarter by number, name or "Q" form; the model never completes a missing year, so "net revenue in March" abstains with period options. `limit` and `top` the question does not state are left empty and code fills the defaults. A plan that fails is sent back like a validation error; after the last repair the run abstains `ambiguous_term` with period options, never `output_invalid`;
      - members: when a lookup for one search text returned more than one member and the plan uses one of them, code ends the run `ambiguous_member` with that lookup's handles, whatever the model chose; `clarify_member` is the model's own way to ask;
      - no KPI field: an agent never proposes a target or threshold.
    - **D3 `validate`:** `GetAnalysisPlanExplanation`. Violations go back to L2 with their codes and paths, at most twice; then rule 24 maps the last code to an abstention.
    - **D4 `run`:** `EvaluateAnalysisPlan`; error codes map by rule 24.
    - **D5 `facts`:** code marks the largest and smallest member rows (`is_max`, `is_min`) on complete results only, and only when the extreme is unique (on a tie no cell is marked), for values and contributions alike, and offers the key facts of rule 23: the totals, the top members, the changes and the contribution rows, at most 12, each with a fact handle.
    - **L3 `explain`** (seat data Q&A, or analysis for contribution plans): input the restatement written by code, cell handles with values, kinds and flags, member handles with their labels where the label is `internal` (personal labels stay handles, rule 31), the offered key facts, the scope and truncation flags and the checks. No question text. Output `AnalysisExplainOutput`: `facts` (at most 5 fact handles, each one of the 12 offered, none twice) and `narrative` (at most 8 steps of rule 23); the schema has no free-text field. Checks: rule 23.
    - **D6 `answer`:** `UpdateAnalysisAnswer` with the key facts, the narrative plan and the steps code dropped. The UI renders both by code at display time.
23. The explanation: key facts and a narrative plan, both rendered by code (ADR-0050 rule 36, made structural). In Phase 1 the model writes no text that reaches the person.
    - **Key facts by code.** Every number an answer states is a key fact that code renders from a fixed template set of the output language, with values formatted by locale, currency, unit and scale (ADR-0040 rule 2):

      | Template | English form |
      | --- | --- |
      | `value` | `<measure> for <member>: <value> (<period>)`, or `(as of <date>)` for a balance or a current-snapshot measure |
      | `total` | `<measure>, total: <value> (<period>)` |
      | `change` | `<measure> for <member> changed from <a> to <b> (<signed change>, <direction word>)` |
      | `share` | `<member>: <share> of <measure> (<period>)` |
      | `contribution` | `<member> contributed <signed change> to the change in <measure> (<period> against <compare period>)` |

      The direction word (rose, fell, was unchanged) is computed from the sign. Code offers up to 12 facts, each with a handle (D5); the model may pick up to 5 of them, each one of the offered handles and none twice (ADR-0050 rule 36); without a pick code shows its own: the total, the largest member and the changes.
    - **A narrative plan, not prose.** The model's `narrative` is an ordered list of at most 8 steps, each `{"claim": <claim template code>, "facts": {<role>: <fact handle>}}`. Every fact handle is one of the 12 offered; the model names no member: code renders `{member}` from the fact's own row; codes and handles are short identifiers, and the schema rejects any other field or value. A plan that breaks the schema is invalid output (ADR-0050 rule 35's retries), and then the answer shows the key facts alone.
    - **The claim catalog.** Code renders every sentence from a closed catalog of claim templates per language. Each template declares its roles and a deterministic precondition on the served cells:

      | Claim | English sentence | Precondition |
      | --- | --- | --- |
      | `largest_value` | `{member} has the largest {measure}.` | a member row (not a total or other row) marked `is_max`, on a complete result with at least two member rows |
      | `smallest_value` | `{member} has the smallest {measure}.` | a member row marked `is_min`, on a complete result with at least two member rows |
      | `largest_contributor` | `{member} is the largest contributor to the change in {measure}.` | a member contribution row; the total change is not zero; the contribution has its sign and is the unique largest of that sign |
      | `largest_offset` | `{member} is the largest offset to the change in {measure}.` | a member contribution row; the total change is not zero; the contribution has the opposite sign and is the unique largest of that sign |
      | `most_of_change` | `{member} explains most of the change in {measure}.` | a member contribution row; the total change is not zero; the contribution has its sign and more than half of the sum of all contributions of that sign, the other row included, so at most one member qualifies |
      | `rose`, `fell` | `{measure} rose for {member}.` / `{measure} fell for {member}.` | a member row's change cell above, or below, the flat band |
      | `flat` | `{measure} was almost unchanged for {member}.` | a member row's absolute change at most the flat band: 1% of the absolute base value (0 when the base is 0), a constant of the agent type version |
      | `same_direction` | `{measure} moved in the same direction for {member_a} and {member_b}.` | two distinct facts of member rows, of the same measure and the same comparison, both changes outside the flat band, with the same sign |
      | `opposite_direction` | `{measure} moved in opposite directions for {member_a} and {member_b}.` | as `same_direction`, with opposite signs |
      | `scope_note` | `These figures cover only the records you may see.` | `is_scope_filtered` |
      | `also`, `meanwhile` | `Also,` / `Meanwhile,` before the next sentence | rendered only between two rendered sentences |

      `{member}` (and `{member_a}`, `{member_b}`) renders the fact's whole row: every grouped member of it ("⟦Item group A⟧ in ⟦November 2026⟧"), and for a pinned basis the pinned member too ("within ⟦USD⟧"), so a claim about one cell never reads as a claim about one of its members. `{measure}` renders as the measure's catalog label; each sentence ends with the citation markers of its facts, which open the key facts. A member renders as a marker, a chip or link in the UI: the chip is the control, and a label's text is data, never interpolated outside its chip, so a label that reads like a claim ("Tripled to 500") stays a name. A CI check holds that no claim template and no catalog label contains a digit, a number word or a unit word.
    - **Preconditions decide.** Before rendering, code evaluates each step's precondition on the served cells. A failing step is dropped and recorded in `narrative_dropped_steps` with its claim and reason; the rest are rendered. So every direction, rank and quantity word comes from code, after code has checked it. The rendered narrative is a pure function of the plan, the cells, the member labels and the catalog: no string from the model reaches it except through a handle that code resolves.
    - **Languages.** A language without a claim catalog and key-fact templates gets key facts only, in the company's default language, or in English when that language has none either. The core ships English; a package supplies the catalog for its language.
    - **The restatement** is written by code from the plan: measures, dimensions, filters, absolute range, time dimension, basis.
    - **What remains.** A true but unhelpful choice or order of claims; the key facts and the table beside them bound it.
    - **Free prose is a later option.** Prose written by the model and screened by a value-free check was tried and rejected for Phase 1 (review round 4): number words of other scripts and languages ("三百", "hai trăm", "deux cents"), exact quantities in words ("no customers", "a single customer"), order and direction synonyms ("dominates", "trails", "collapsed") and character tricks (zero-width and look-alike letters) passed, while only 12 of 22 ordinary sentences did. It may return after Phase 1, gated by an evaluation suite that reports the prose acceptance rate against a threshold (open question).
24. Abstention is a typed outcome of a completed run, tuned for precision: a wrong answer costs more than an abstention.

    | Outcome | When | What the person sees |
    | --- | --- | --- |
    | `answered` | A result, verified or generated | Restatement, table or chart, key facts, narrative, scope note, badge, `as_of`, the "how this was computed" fold |
    | `ambiguous_term` | L2 returns `clarify`, or after the last repair the plan still fails the stated-value check (period options), or the code is `analysis_plan_invalid`, `unknown_measure`, `unknown_dimension`, `currency_mixed`, `unit_mixed`, `dimension_required`, `time_range_invalid` or `filter_value_unknown` | 2–4 options from the catalog (currency or unit choices for the mixing codes, periods for the time codes); choosing one asks again |
    | `ambiguous_member` | Decided by code: a lookup for one search text returned several members and the plan uses one of them; or L2 returns `clarify_member` | The candidate members, rendered by code from their handles for the person within their rights; choosing one asks again |
    | `out_of_coverage` | L2 returns `out_of_coverage`, or the last code is `dimension_not_shared`, `fan_out_refused` or `measure_not_additive` | No measure answers this; the nearest measures; an offer to log a catalog request (`analysis_catalog_request`, owner `company_owner`) |
    | `not_permitted` | L2 returns `not_permitted`, or the code is `analysis_not_permitted` or `permission_denied` (no repair) | What is missing (a field class, a fact, an owner scope), never data |
    | `data_not_ready` | `analysis_data_not_ready` | Why: before the cut-over, a migration is loading, or the figure exists only for today |
    | `too_broad` | `analysis_too_broad` or `timeout` | A request to narrow, with the limit that tripped |

    These outcomes extend ADR-0050 rule 17's table and the check `ck_agent_run_outcome` of DS-05-platform.sql: all are state `completed`, and the run's `agent_task` item is resolved. A question whose run ends `routing_blocked` or `not_applicable` is `abstained` too. The model never falls back to SQL or to arithmetic of its own.
25. Modes and evidence (ADR-0050 rule 14; ADR-0051 rule 4):
    - **`assisted`** answers people's questions; the answer goes only to the asker.
    - **`shadow`** answers nobody. In shadow the daily evaluation job `RunAnalysisEvaluation` (system job of `agents`, actor `system`) starts one run per verified example, with the example as subject, acting for the person who released the example (that person's scope and field classes apply); the run does not call `UpdateAnalysisAnswer` in shadow, because an example has no question row: its plan, hashes, key facts and narrative plan stay in the run's recorded steps (ADR-0050 rule 41), which the comparator reads. Its comparator counts a case equal when the run's `analysis_resolved_hash` equals the example's, or when both results are equal on the same snapshot.
    - **Promotion evidence, a stated exception like data migration's.** An analysis run drafts nothing a person later resolves, so there are no shadow cases of ADR-0051 rule 4. `CreateAgentPromotionEvidence` freezes instead: the version's CI evaluation report (rule 29) and, when the company has at least 30 verified examples, the shadow evaluation over them (at least 90% equal, no wrong answer on an example whose expected outcome is an abstention). With fewer than 30 examples the evidence is the synthetic CI report alone; this is flagged for the author (open question). The proposal to set `assisted` names that snapshot; a person other than the submitter approves it.
    - **Catalog changes.** The `analysis` agent type version declares the catalog hash it was evaluated with, so a catalog change is a new version that runs in shadow until promoted again (ADR-0050 rule 14).

**Saved analyses, KPIs and examples**

26. Saved analyses:
    - **`saved_analysis`** (company data, change-tracked): `code`, `name`, `kind` (`analysis` or `kpi`), `state` (`draft`, `verified`, `retired`), `verified_version`, `latest_version`, owner user, and `visibility` (`private` to its owner, or `company` for every holder of the read permission).
    - **`saved_analysis_version`** (immutable once released): the plan, its `analysis_plan_hash` and the definition hashes it covers, catalog version, presentation (chart kind, layout, column order), `open_filters` (dimensions a viewer may filter without losing the badge), trigger questions, an optional narrative plan written by a person from the same claim catalog (rule 23), the KPI fields of rule 27, the author, the origin agent run, and who released it when.
    - **Commands** (effect class `master_data_change`, change-tracked): `CreateSavedAnalysis` and `UpdateSavedAnalysis` (leaf `general_access` at `edit`; an update writes a new draft version, or sets `retired`) let every builder user keep personal analyses with visibility `private`; visibility `company` and kind `kpi` also need the capability `share_saved_analysis` (leaf `saved_analysis`, `edit`). `ReleaseSavedAnalysis` (leaf `saved_analysis`, post, `human_only`) makes the version the verified version. A verified version stays in force until another version is released. `ListSavedAnalysis` and `GetSavedAnalysis` (leaf `general_access`, `read`) show a caller their own private analyses and every company analysis, so KPI tiles open for everyone; running them still checks each fact's permission.
    - **Release by another person.** The person who releases a version differs from its author, as for change proposals (ADR-0055). In small-company mode (ADR-0054 rule 20) the author may release it, and the version records `is_self_released`.
    - **No clash with examples.** Release refuses a trigger question that equals, in the same language, a verified example's question or another verified version's trigger question within the same visibility set (the company's analyses and examples, or one owner's private ones together with the company's), so D2 never has two answers for one asker.
    - **Agent drafts.** Commands of effect class `master_data_change` are allowed targets of change proposals and stay off tool lists (ADR-0029 rule 2; ADR-0050 rule 29 note). The analysis agent drafts a saved analysis of kind `analysis` or an example only when the asker asks it to, through `CreateChangeProposal`; a person submits and an eligible person approves it (ADR-0055). Release stays a separate human step. Agents draft no KPI.
    - **Running.** Opening a saved analysis runs its verified version (or a draft, for its editors) through `EvaluateAnalysisPlan`, without any model. With a narrative plan, code renders it on every opening and evaluates every step's precondition again on the new cells, dropping the steps that no longer hold. A saved plan refers to each fact either by `{"role": …, "measure": …}`, with the roles `total`, `total_change`, `max`, `min` and `largest_contribution`, or by `{"members": {<dimension>: <key>, …}, "measure": …, "kind": …}`, the full coordinate of the row with `kind` one of `value`, `change`, `share`, `contribution`, never by cell position, so a month in which the rows reorder cannot make a sentence name another member. A reference that resolves to no cell, or to more than one, drops its step. Without a narrative plan the person may ask for an explanation, which is an `analysis` run.
    - **The badge** is computed by code for every result, however its plan was found: `verified` when the plan's `analysis_plan_hash`, taken now, equals the hash stored on a verified saved analysis version or a verified example, or equals it after removing filters on that version's `open_filters`; otherwise `generated`. Since the hash covers the named definitions, a changed definition ends the badge. No model ever sets it. A verified plan still runs under the asker's scope (INV-414).
27. KPIs are saved analyses of kind `kpi` whose versions hold one measure, a time grain, `favorable_direction` (`up` or `down`), `target_value`, and optional `warning_threshold` and `critical_threshold` in the measure's basis, ordered by the direction. People enter targets and thresholds; no agent proposes them. Running a KPI returns the value, the target and a status computed by code: `critical` beyond the critical threshold, `on_track` on the favourable side of the warning threshold (of the target when no warning threshold is set), `warning` between. KPI tiles in the UI are KPIs run. Alerts and subscriptions come after Phase 1.
28. Analysis examples, the verified question-and-plan pairs:
    - **`analysis_example`** (company data, change-tracked): question, normalized question, language, flow (`sales`, `purchasing`, `inventory`, `production`, `open_items`, `ledger`), the expected outcome (`answered` or one abstention of rule 24), the plan and `analysis_plan_hash` for `answered`, `version`, the example it supersedes, `state` (`draft`, `verified`, `retired`), source (`person`, `feedback`, `agent_proposal`), the question it came from, and who released it.
    - **Versioned and immutable.** A released example never changes: a guard freezes its question, plan, hash and expected outcome, and allows only retirement. `UpdateAnalysisExample` on a verified example writes a new draft version that supersedes it; releasing the new version retires the old one in the same command. One verified example per normalized question and language.
    - **Commands** (leaf `saved_analysis`): `CreateAnalysisExample` and `UpdateAnalysisExample` (edit, `master_data_change`), `ReleaseAnalysisExample` (post, `human_only`, by a person other than the author, rule 26).
    - **Uses.** Verified examples answer exact matches without a model (rule 22, D2), give the planner context, and are the company's evaluation cases (rule 25).

**Evaluation**

29. The evaluation suite (ADR-0050 rules 39–40):
    - **Cases.** The core suite holds 50 to 100 cases per flow of rule 28, in English, built on the synthetic dataset (DS-17): question, business date, actor (field classes and scope), expected outcome, expected plan (canonical) and expected result on the dataset. At least one case in five expects an abstention, with its code. Packages may add questions in their language as test data of the package.
    - **Scoring.** A case is equal when the plan's `analysis_resolved_hash` equals the expected one, or the results are equal on the dataset. A wrong answer is an `answered` outcome whose result differs from the expected result, or an answer where an abstention was expected.
    - **Leave one out.** The examples given as context never include the case under test.
    - **Thresholds:** at least 90% of cases equal (ADR-0003 R8), at most 2% of cases wrong, and at least 90% of the abstention cases abstaining with the expected outcome.
    - **Explanation metrics.** The report also counts narrative steps dropped per claim template and refusals by error code, so a claim the model misuses, or a validation code that keeps recurring, shows up per release.
    - **When.** The replay suite on every commit that touches `query`'s analysis code, the catalog or the workflow; the live evaluation whenever a template, output schema, the catalog, the agent type version or `seatmap.yaml` changes (ADR-0050 rule 40). The report adds plan match, result match, wrong-answer rate, abstention precision and recall, and cost per case.

**Cost control**

30. Cost:
    - **No model when it is not needed.** Verified saved analyses, exact matches with verified examples and plan cache hits skip L1 and L2; a saved analysis with a narrative plan uses no model at all. People who build analyses in the UI use no model.
    - **Plan cache.** Normalized question → plan, keyed by company, user, scope fingerprint (a hash of the per-view read grants, owner scope sets and field classes the builder would set, rule 13), language, catalog hash and the agent type version. Cleared when an example or saved analysis is released or retired.
    - **Result cache.** Keyed by company, user, `analysis_resolved_hash` and the same scope fingerprint, kept `analysis_result_cache_seconds`; a cached result shows its own `as_of`. A plan without entity filters has the same resolved hash in every company, and two users with equal grants may still own different documents, so neither key omits company or user.
    - **Budgets.** Rule 20's run and daily budgets, under the company and installation caps of ADR-0050 rule 22, with the reservation of rule 23. A cheap classification model routes; the data Q&A and analysis seats only plan and explain.
    - **No loops.** At most three plan attempts with two lookups each and one explanation retry per run; no exploration of many queries.

**Security and privacy**

31. Rules that keep the floors of spec 03:
    - **Same rights as the human.** Every query of the run is checked against the intersection of the agent type and its human (ADR-0050 rule 31), with the human's record scope and owner scope, per fact view (rule 13).
    - **Member labels.** Agent runs receive member labels labelled `personal` as handles (`m1`, `m2`); the gateway would remove them anyway (ADR-0050 rule 9). The narrative plan names no member at all; code renders members from the facts' rows, so names never need to reach a model or come back from it.
    - **Questions.** Personal by label (rule 21), logged when sent, blocked when the switch is on.
    - **Stored answers** hold member keys, never labels, and are readable by the asker and holders of `read_analysis_debug` only (rule 21).
    - **Untainted.** No fact holds untrusted text, and the agent type may not read it.
    - **No audit data.** No fact reads audit tables (ADR-0050 rule 50).
    - **No files, no actions.** Agents never export (rule 17), never post, never send.
    - **Small cells.** Suppression of small cells for personal measures comes after Phase 1; Phase 1 has no personal measure.

**User interface**

32. Screens (ADR-0040; DS-30):
    - **Analysis builder:** measures, dimensions and filters as chips from `ListAnalysisCatalog`; the plan is the builder's state. Users without `start_agent:analysis`, such as the sales clerk of the seed, analyse here.
    - **Answer view:** the restatement; the table or chart; the key facts, each figure clickable (its drill handle); the narrative sentences rendered by code, with member chips and citation markers that open the cited fact; a "how this was computed" fold with the plan as chips and the SQL; the scope note; the truncation note; the badge; `as_of`.
    - **Saved analyses and KPI tiles:** lists and tiles of saved analyses and KPIs run on open.
    - **No client arithmetic** (ADR-0040 rule 2): charts plot server cells; totals, shares and changes are server cells.

**Phase 1 catalog**

33. The 35 measures of Phase 1 (catalog `analysis-measures.csv`):

    | Fact | Measures |
    | --- | --- |
    | `journal_line_overview` | `net_revenue`, `revenue_deduction`, `cost_of_goods_sold` (`cost`), `gross_profit` (difference, `margin`), `gross_margin_percent` (ratio, `margin`), `operating_expense` (selling and administrative expense), `ledger_debit_turnover`, `ledger_credit_turnover`, `ledger_net_turnover` |
    | `system_account_turnover` | `ledger_closing_balance` (semi-additive over `posting_period`) |
    | `sales_line_overview` | `sales_net_amount`, `sales_line_amount` (transaction currency), `sales_quantity`, `sales_cost` (`cost`), `sales_margin` (`margin`), `sales_margin_percent` (ratio, `margin`), `sales_document_count`, `sales_customer_count` |
    | `purchase_line_overview` | `purchase_net_amount`, `purchase_line_amount` (transaction currency), `purchase_quantity` |
    | `open_item_overview` | `receivable_open_amount`, `receivable_overdue_amount`, `payable_open_amount`, `payable_overdue_amount`, `open_item_count` (all semi-additive over `as_of`) |
    | `stock_overview` | `stock_quantity`, `stock_value` (`cost`) (semi-additive over `as_of`) |
    | `stock_movement_overview` | `stock_receipt_quantity`, `stock_issue_quantity`, `stock_movement_value` (`cost`) |
    | `production_output_overview` | `production_output_quantity`, `production_scrap_quantity`, `production_order_count` |
    | `production_variance_overview` | `production_variance_amount` (`cost`) |

    The profit-and-loss measures exclude closing and migration entries; the ledger turnover measures exclude migration entries, as ADR-0049 rule 6's turnover does. `sales_net_amount` and `purchase_net_amount` are the lines' posted net amounts in company currency, as their journal lines carry them; `net_revenue` is the ledger's figure, which also holds manual entries and deductions, so "sales" is an ambiguous term between them (rule 2). `sales_line_amount` and `purchase_line_amount` are in the document's currency.
34. The 22 dimensions of Phase 1 (catalog `analysis-dimensions.csv`): `posting_date`, `document_date`, `due_date`, `posting_period`; `partner`, `partner_group`, `salesperson`; `item`, `product`, `item_group`; `warehouse`, `branch`; `system_account`, `account`, `cost_center`, `project`; `currency`, `document_type`, `movement_type` (kind `catalog`); `overdue_bucket` (`not_due`, `days_1_30`, `days_31_60`, `days_61_90`, `days_over_90`, from days overdue at the business date), `variance_category` (kind `enum`); `production_order`.

**Invariants, catalogs and lab**

35. Invariants, in the reporting block INV-400 to INV-499 (ADR-0049 rule 31), first at step 5 with the first agent (ADR-0050 rule 55):
    - **INV-410** (`reporting`): every drillable cell equals its drill rows by the table of rule 16: the sum of their contributions for sums, counts, differences, totals, subtotals and contribution rows, the number of distinct keys for distinct counts, and the opening row plus the lines for balances, at the same snapshot.
    - **INV-411** (`reporting`): for full scope, every range and every system account subtree, each ledger measure equals ADR-0049 rule 6's turnover measure over the operational accounts mapped to that subtree for the same range and `special_periods` option (`change` for the net measures and their signed forms, `debit_turnover` and `credit_turnover` for the side measures), with `closing_entries=exclude` for the profit-and-loss measures and migration entries left out, in every regime. Statement lines are not claimed, since a line may split a measure by side or partner.
    - **INV-412** (`reporting`): every total, subtotal and other row equals the aggregation of its fact rows (never a sum of non-additive cells); no total row adds values of different currencies or inventory units; every contribution plan's reconciliation row is zero.
    - **INV-413** (`safety`): every user-visible sentence of an analysis answer is rendered by code, either from a key-fact template or from a claim template whose precondition held on the served cells; every stored narrative plan holds only claim codes, roles and handles.
    - **INV-414** (`safety`): every answer recorded with badge `verified` has an `analysis_plan_hash` equal, after removing filters on open dimensions, to a saved analysis version or analysis example that was verified at its recorded_at.
36. Catalog rows:
    - **New catalogs:** `analysis-measures.csv`, `analysis-dimensions.csv` (owner DS-33).
    - **Errors** (DS-04): `analysis_plan_invalid`, `unknown_measure`, `unknown_dimension`, `dimension_not_shared`, `fan_out_refused`, `currency_mixed`, `unit_mixed`, `dimension_required`, `measure_not_additive`, `time_range_invalid`, `filter_value_unknown` (validation); `analysis_not_permitted` (permission); `analysis_too_broad`, `analysis_data_not_ready`, `analysis_question_answered` (precondition).
    - **Check results:** `analysis_scope_filtered`, `analysis_periods_open`, `analysis_rows_truncated`, `analysis_cell_changed`, `analysis_measure_deprecated`.
    - **Agent run outcomes:** `answered`, `ambiguous_term`, `ambiguous_member`, `out_of_coverage`, `not_permitted`, `data_not_ready`, `too_broad`, added to `ck_agent_run_outcome` for state `completed`.
    - **Work item kinds** (module `query`): `analysis_answer_disputed` (subject `analysis_question`, owner `company_owner`, due `days:5`, person), `analysis_catalog_request` (subject `analysis_question`, owner `company_owner`, due `days:30`, person).
    - **Authorization** (ADR-0054):
      - leaf `analysis_question` (below `reports`, module `query`): `CreateAnalysisQuestion`, `UpdateAnalysisFeedback` and `UpdateAnalysisAnswer` at `edit` (verb `Update`, rule 21) (the last for the human an analysis run acts for); `ListAnalysisQuestion` and `GetAnalysisQuestion` at `read`, own questions only;
      - leaf `general_access`: `CreateSavedAnalysis` and `UpdateSavedAnalysis` at `edit` (private analyses), `ListSavedAnalysis` and `GetSavedAnalysis` at `read`, with the analysis queries of rule 14;
      - leaf `saved_analysis` (below `reports`, module `query`): `ListAnalysisExample` at `read`; the capability `share_saved_analysis`, `CreateAnalysisExample` and `UpdateAnalysisExample` at `edit`; `ReleaseSavedAnalysis` and `ReleaseAnalysisExample` at `post`;
      - leaf `analysis_debug` (below `administration`, module `query`): the capability `read_analysis_debug` at `full`, `none` in every template except `owner`;
      - leaf `agent_analysis` (below `agent`): `start_agent:analysis` at `edit`.

      `t12_access.py` registers these leaves, the two capabilities and the commands and queries, and checks the expansion. Interim template rows: `analysis_question` at `edit` and `agent_analysis` at `edit` for the chief accountant, accountant, sales manager, purchasing manager and production planner; `saved_analysis` at `post` for the chief accountant and at `edit` for the other four; `analysis_debug` at `none` for the IT administrator (the owner and IT administrator hold the rest through their parents). Flagged for the author.
    - **Settings:** rule 11.
    - **Edge cases** (EC-150 to EC-155 and EC-170; EC-171 to EC-179 are reserved for this ADR): EC-150, an owner-scoped clerk's total in the builder; EC-151, a transaction-currency question over two currencies; EC-152, margin asked without the class; EC-153, revenue change by customer between an open and a locked month; EC-154, a question outside the catalog; EC-155, management revenue equal to the journal at month end; EC-170, revenue over a year closed by closing entries and adjusted in a special period.
    - **Glossary:** analysis catalog, fact, measure (analysis), additivity, basis, dimension (analysis), analysis plan, analysis plan hash, drill handle, variance contribution, reconciliation row, analysis question, abstention, key fact, narrative plan, claim template, claim precondition, named period, saved analysis, verified badge, KPI, analysis example.
37. Lab check `t18_analysis.py` ([validation lab](../reviews/2026-11-14-design-validation/README.md)):
    - **Pure, explanation:** the narrative plan's shape (offered handles only, none twice, no free-text field), so every probe of review rounds 2 and 3 is not representable; a property test in which random plans with arbitrary strings in every field never put a model string into the output except resolved member labels; true and false cases of every claim precondition; dropped steps recorded; saved references by every role and by full coordinate, surviving reordered rows and dropping unresolvable or ambiguous references; ties marking no extreme; the reviewer's failing cases of round 5 (a cell of two dimensions, mixed measures or one fact twice in a direction pair, mixed-sign and zero-total contributions, orphan connectors, one member row) refused or dropped; key facts with the as-of date for balances; fail-closed languages.
    - **Pure:** the two catalogs (field counts, unique codes, fewer than 40 measures, every selector a core system account, the turnover options on journal measures, every required and basis dimension offered by the fact, unique synonyms, field classes on ledger cost and margin); plan validation, where good plans pass and a bad plan is refused with each code of rule 10; the compiler (one `SELECT` over declared views with bound values, an `is_in_scope` filter per fact, subtotals per pinned basis, truncation, per-bucket carry-forward); canonical hashes with definition hashes; relative dates; contributions on random data; the one-row, direction and superlative checks on citation references; named periods and the normalized stated-value check; exact-only matching; the stated-value check; the abstention mapping; the badge; scope-keyed caches; per-view grants.
    - **With `--load`,** on every DDL file from `load_all.py`: the tables of DS-33-analysis.sql and their checks; agent runs completing with each analysis outcome; then a seeded company with posted documents, a closing entry, a special-period entry and a migration entry, lab views for three facts with per-view grants, and plans whose cells equal their drill rows by kind and whose management totals equal ADR-0049's turnover over the operational accounts; per-currency subtotals; two facts under two owner scopes; scoped member lookup; per-bucket closing balances by period, by period and branch, by fiscal year, with special periods excluded and beside a second fact; an `opening_turnover` row in its own bucket and its scope.
    - **Not covered:** the model, the gateway, the dispatcher, RLS of the views, the production read model.

**After Phase 1**

38. Later, each by an ordinary change or its own ADR:
    - price-volume-mix for revenue and margin, with one documented convention and a zero remainder;
    - segment search over two-dimension combinations with caps;
    - KPI alerts, subscriptions and scheduled summaries;
    - small-cell suppression for personal measures, with a company threshold;
    - company-defined measures, with review and evaluation;
    - historical open-item and stock balances as of past dates (Phase 1 reads them from the ledger's closing balances by system account);
    - pre-aggregates for hot measures;
    - export of the catalog to outside BI tools (an open semantic-model format);
    - saved list views (ADR-0040 rule 6) and dashboards with layout beyond KPI tiles;
    - the period-close assistant and the variance agent (ADR-0051 rule 29) as workflows on this layer.

**Notes to accepted ADRs**

39. Notes are appended to: ADR-0022 rule 2; ADR-0027 rule 8; ADR-0035 rule 15; ADR-0038 rule 12; ADR-0040 rules 2 and 6; ADR-0049 rules 16, 18 and 31; ADR-0050 rules 1, 12, 14, 17, 26, 28, 30, 31, 36, 44, 46, 48 (two notes), 51, 53 and 54; ADR-0051 rules 4, 7, 9 and 29; ADR-0054 rules 15 and 24.

## Context

The author asked for agent-assisted reporting and analysis after a capability check (2026-11-15) found the read side designed and safe (semantic views, MCP resources, the statutory engine with drill-down, the data Q&A and analysis seats) but no analysis agent, no aggregation on request, and no saved management reports or KPIs. Answering "sales by item group by month" with `List<View>` pages would force the model to add rows, or truncate silently at 200 rows.

The 2026-11-15 survey compared text-to-SQL benchmarks, semantic layers (dbt MetricFlow, Cube, LookML, Snowflake semantic views, Power BI models), AI analyst products, verified-query practice, number grounding and contribution analysis:
- **Free SQL from a model is wrong too often** on real schemas, and its failures (wrong joins, fan-out, unit and currency mixing, wrong dates) look plausible. Products that work route the model through a semantic layer, show the query, and let people correct it.
- **Semantic layers** declare measures with additivity, dimensions with hierarchies and joins with cardinality; MetricFlow's common-dimension rule and fan-out guards are the basis of V5 and V6.
- **Verified queries** serve twice: as context for the planner and as direct answers labelled trusted. Evaluations remove the case under test from the context.
- **Narrated numbers** are safe only when statistics produce the facts and the model writes around them. Review rounds 2 to 4 showed that placeholders and a numeral check cannot hold Principle 13 against numbers written as words; the narrative plan of rule 23 holds it by construction, because code renders every sentence.
- **Abstention** must be designed in; systems rarely abstain well otherwise.
- **Contributions** are exact for additive measures; ratios need numerator and denominator.
- **Security** is enforced in the engine under the user's identity, never in the prompt; caches must key on scope.

Review round 4 (2026-11-15) showed that word lists cannot keep numbers and quantities out of free prose, so in Phase 1 the model only plans: it picks key facts and claim templates, and code checks and renders every sentence. Review round 3 (2026-11-15) showed that any check around values placed in free prose leaves a way to build numbers ("12 500", "12 point 500", "12 – 500"), so the explanation was redesigned: code renders every number as a key fact, and the prose holds no value. Review round 2 (2026-11-15) found that adjacent placeholders and scale words could still build numbers, that sentences could swap values, and gaps in periods, grants, lookups, carry-forward and opening turnover; this version closes them. Review round 1 (2026-11-15) found that the first draft summed closing entries into profit and loss, totalled currencies when grouping pinned them, scoped all facts of a plan by one grant list, accepted fuzzy matches as verified answers, and labelled questions `internal`; this version corrects those and the further points of that review.

ADR-0005: the agent decides technical points, with SAP as reference when unsure, and the option easiest for AI agents wins among correct ones. SAP's analytical CDS views with annotations (measures, aggregation behaviour, dimensions, hierarchies) and its AI services, which call models only above authorized CDS views, follow the same split. One plan format for people and agents, self-describing drill handles and catalog resources serve the goal.

## Options considered

| Option | For | Against |
| --- | --- | --- |
| Declared catalog, JSON plan, code compiles one `SELECT` (chosen) | Every number from code; scope and field classes reused; validation gives typed refusals | Questions outside the catalog abstain; a compiler to build and test |
| Model writes SQL against the views | Wide coverage | Plausible wrong numbers; fan-out and mixing undetectable; breaks ADR-0050 rule 44 |
| Model sums rows from `List<View>` | No new code | Breaks Principle 13; truncates at 200 rows |
| External semantic engine (Cube, dbt SL) | Mature | A second security model; duplicates scope, field classes and taint |
| Company-defined measures in Phase 1 | Flexibility | Semantic drift and unreviewed definitions; saved analyses cover the need |
| Model writes digits, checked against cells afterwards | Freer prose | Rounding, formatting and derived numbers make matching brittle |
| Placeholders for values in prose, with checks around them | Fluent prose with figures | Three review rounds each found a new way to build a number from adjacent values and words |
| Key facts rendered by code, prose without values and with citation markers, screened by word lists | Some model prose | Round 4: other-script numerals, quantities in words, synonyms and character tricks passed, and 12 of 22 ordinary sentences; rejected for Phase 1, a later option behind an acceptance gate |
| Key facts and a narrative plan of claim templates with preconditions, all rendered by code (chosen) | No model word reaches the person; every claim checked on the cells | Stiffer explanations; the claim catalog must grow by release |
| One read-grant list per statement | Simple | One fact's grant widens another's scope |
| Read grants per fact view (chosen) | Each view scoped by the assignments that grant it | A map instead of a list in the session settings |
| Fuzzy acceptance of verified questions | Fewer model calls | A subset question gets a verified answer to another question |
| Exact matches only, similar questions as hints (chosen) | No wrong verified answer | More router calls |
| Question text `internal` | Analysis works with the switch on | Names reach the provider unlogged |
| Question text `personal` (chosen) | Logged; blocked with the switch on | Model questions stop with the switch on; exact matches and the builder still work |
| Badge claimed by the model | — | Unverifiable |
| Badge from the plan hash with definition hashes (chosen) | Deterministic; ends when a definition changes | Plans must be canonical |
| Promotion by shadow comparison with people | ADR-0051's general rule | An analysis run has no case a person resolves; examples and the CI suite give evidence instead |
| Sales amounts in company currency computed from document lines | One fact | Would re-implement conversion; the posted amounts are stored |
| Production variances recomputed from lines | No read model | Re-implements ADR-0035; two answers for one figure |

## Constraints that come with the decision

- **DDL:** [DS-33-analysis.sql](../design/DS-33-analysis.sql) (new): `analysis_question`, `saved_analysis`, `saved_analysis_version`, `analysis_example`, with guards and forced row-level security. DS-05-platform.sql: the outcomes of rule 24 in `ck_agent_run_outcome`. DS-53: `production_order_variance` with the costing tables (a note in DS-43-54-planning-production.sql).
- **Views:** `journal_line_overview`, `sales_line_overview`, `purchase_line_overview`, `stock_movement_overview`, `production_output_overview`, `production_variance_overview`, and the label and dimension views, declared in `query`; `erpme.read_grants` as a map per view; `erpme.business_date`.
- **DS-04:** the errors and check results of rule 36.
- **Catalogs:** `analysis-measures.csv`, `analysis-dimensions.csv`; INV-410 to INV-414; EC-150 to EC-155 and EC-170; the work item kinds; the authorization leaves, capability and template rows.
- **DS-16:** the invariants and a property test of the compiler (no plan text in SQL, one statement).
- **DS-17:** the evaluation suite's cases and expected results on the synthetic dataset.
- **DS-30:** the screens of rule 32.
- **DS-34:** the `analysis` workflow, its prompts, schemas and golden set.
- **Packages:** claim catalogs and key-fact templates for their languages (rule 23).
- **Lab:** `t18_analysis.py`; `t12_access.py` registers the new agent type, leaves, capabilities, commands and queries and checks their expansion.
- **Open questions:** question text `personal` or `internal`; promotion below 30 examples; free model prose after Phase 1 behind an acceptance gate; budgets and settings; the template seed.

## Revisit when

- Abstentions of `out_of_coverage` cluster on a missing measure: add it to the catalog.
- Measured latency of a fact exceeds its timeout on the large dataset: add a read model or pre-aggregate.
- The author answers the open question on question text and the routing switch, or allows a local model.
- A customer needs company-defined measures or alerts.

## Documents updated

- **This ADR** (new) and the index row in [docs/adr/README.md](README.md).
- **DDL:** [docs/design/DS-33-analysis.sql](../design/DS-33-analysis.sql) (new); [docs/design/DS-05-platform.sql](../design/DS-05-platform.sql) (`ck_agent_run_outcome`); [docs/design/DS-43-54-planning-production.sql](../design/DS-43-54-planning-production.sql) (a note on `production_order_variance`).
- **ADRs:** notes in ADR-0022, ADR-0027, ADR-0035, ADR-0038, ADR-0040, ADR-0049, ADR-0050, ADR-0051 and ADR-0054 (rule 39).
- **Design files:** [docs/design/DS-04-command-envelope.md](../design/DS-04-command-envelope.md), [docs/design/DS-16-invariants-and-harness.md](../design/DS-16-invariants-and-harness.md), [docs/design/DS-17-synthetic-dataset.md](../design/DS-17-synthetic-dataset.md), [docs/design/backlog.md](../design/backlog.md) (DS-30, DS-33, DS-34, DS-53).
- **Catalogs:** [analysis-measures.csv](../catalogs/analysis-measures.csv), [analysis-dimensions.csv](../catalogs/analysis-dimensions.csv) (new); [invariants.csv](../catalogs/invariants.csv), [edge-cases.csv](../catalogs/edge-cases.csv), [work-item-kinds.csv](../catalogs/work-item-kinds.csv), [authorization-areas.csv](../catalogs/authorization-areas.csv), [role-template-levels.csv](../catalogs/role-template-levels.csv), [README.md](../catalogs/README.md).
- **Glossary:** [docs/spec/00-reading-guide.md](../spec/00-reading-guide.md) (rows only).
- **Open questions:** [docs/open-questions.md](../open-questions.md).
- **The lab:** [docs/reviews/2026-11-14-design-validation/](../reviews/2026-11-14-design-validation/README.md): `lab/t18_analysis.py` (new), `lab/t12_access.py`.
- **Log:** [docs/runbook/step-log.md](../runbook/step-log.md) at acceptance.
