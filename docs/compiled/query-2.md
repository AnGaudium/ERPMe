Module: query    Chunk: 2 of 4    Source ADRs: ADR-0050, ADR-0059, ADR-0060
Build step(s): 3, 4, 5    Generated from index: 30d5706    Compiled by: Claude Fable 5.2, 2026-11-21

# `query` compiled spec, chunk 2: list export, held-out filter, analysis catalog, facts, measures, dimensions, plan, time and hashes

## Purpose

This chunk states the part of `query` law on: the list export, the held-out filter for drafting agent runs, the ownership of the analysis layer, its declared catalog (facts, measures, dimensions, ambiguous terms), the JSON analysis plan, time ranges and the plan hashes. `query` is layer 5 and read-only: it owns the analysis catalog, validator, compiler and executor and the analysis tables; it does not own the `analysis` workflow, which is in `agents`. The semantic views and scope of ADR-0050 are in chunk 1; validation, execution, drill, answers, saved analyses and the catalog lists are in the later chunks.

## Entities and tables

DDL: `docs/design/DS-33-analysis.sql`. `query` owns `analysis_question`, `saved_analysis`, `saved_analysis_version` and `analysis_example` (R202); their rows are in the chunks that state the rules defining them (ADR-0060.R21, ADR-0060.R26, ADR-0060.R28).

Defined by rule, without DDL: `list_export`, one export request with `state` (`queued`, `running`, `done`, `failed`), owner `query` (R230).

The fact views and helper views of R208 and R210 are semantic views of schema `query`, declared in code, not tables.

Reads: `opening_turnover`, `system_account`, `account` (`ledger`); `posting_period`, `fiscal_year` (`periods`); `company`, `item`, `product`, `item_group`, `partner`, `partner_group`, `branch`, `currency` (`master_data`); `production_order_variance`, `golden_case_label`, `agent_run`; the catalog `system-accounts.csv`.

## Commands and queries

| Name | Actor and authorization | Input | Effect | Events | Error codes |
| --- | --- | --- | --- | --- | --- |
| `CreateListExport` | people only, on no agent tool list; `general_access` at `edit`, checked against the exported query's own permission and scope | a `List<…>` query, its filters, columns and language | creates a `list_export` record; effect class `other` (R230) | `ListExportCreated` | `list_export_query_not_allowed`; the consumer fails with `list_export_too_large` |

The analysis queries that R202 names have their rows in the chunks that state their rules. Their authorization leaves (`general_access`, `analysis_question`, `saved_analysis`, `analysis_debug`) are law of `permissions` (ADR-0054.R24.N3).

Not registered commands: the long-job consumer of `ListExportCreated` on queue `jobs` (R230, R231); the held-out filter of the query layer (R235); the registry CI check of R236.

`held_out_filter_unavailable` (R235) is raised by the query layer on an aggregate it cannot filter; chunk 1 lists it on `List<View>`. `held_out_case_seen` is an evidence result of `automation` (R238).

## Rules

### Analysis layer: scope and ownership

R201. ADR-0050's query layer has no aggregation on request, and Principle 13 forbids a model adding rows itself: every number shown comes from deterministic code. The analysis layer adds: a catalog declared by `query` as code versioned with the release; a JSON plan as the only input for people and agents, which code validates against the catalog and refuses with typed codes, compiles to one read-only `SELECT` over the semantic views and runs under the asker's rights, fact by fact; `EvaluateAnalysisPlan`, which returns typed cells, and `GetAnalysisPlanExplanation`, which returns the compiled SQL, the resolved dates and a scope note; a drill handle on each cell that leads, level by level, to documents and journal lines or to the cells it is computed from; the untainted agent type `analysis` with read tools only, where the model plans and explains and code computes, states every number as key facts from fixed templates and checks and renders the model's narrative plan (an ordered list of claim template codes with fact handles); saved analyses, KPIs and examples as company data, versioned and immutable once verified, with states `draft`, `verified` and `retired`; and exact additive variance contributions with a reconciliation row of zero, production variances being read from ADR-0035's split, never remodelled. A cell equals the sum of its drill rows, and management totals equal ADR-0049's turnover for the same system accounts, scope and range. In Phase 1 no word the model writes reaches the person; an agent that cannot answer safely abstains with a typed outcome. Verified saved analyses run without a model; verified analysis examples answer exact repeats, feed the planner and form the company's evaluation cases beside the core evaluation suite. Companies do not add measures, they save analyses.
Source: ADR-0060.D0

R202. `query` (layer 5) owns the analysis catalog, the validator, the compiler and the executor; the queries `EvaluateAnalysisPlan`, `GetAnalysisPlanExplanation`, `ListAnalysisCellRow`, `ListAnalysisResultRow`, `ListAnalysisCatalog`, `ListAnalysisDimensionMember`, `ListAnalysisQuestion`, `GetAnalysisQuestion`, `ListSavedAnalysis`, `GetSavedAnalysis` and `ListAnalysisExample`; the MCP resources of ADR-0060.R14; and the tables `analysis_question`, `saved_analysis`, `saved_analysis_version` and `analysis_example` with their commands (DDL draft `DS-33-analysis.sql`).
Source: ADR-0060.R1

R203. `query` imports `db`, `registry` and `agent_runs`, and the `work` contract to raise its work item kinds `analysis_answer_disputed` and `analysis_catalog_request` (ADR-0042.R5). `work` is layer 2, so the import goes downward.
Source: ADR-0060.R1

R204. `agents` (layer 5) owns the `analysis` workflow (ADR-0060.R20 to ADR-0060.R25). It reaches `query` only through the dispatcher, as every workflow does; nothing in `agents` imports `query`. The `analysis` agent is one of the Phase 1 agent types (ADR-0078.R1): one declaration on the shared runtime and an internal type that draws on the reserve of ADR-0050.R22. The assistant routes questions that need figures to it, so there is one analysis path (ADR-0078.R8).
Source: ADR-0060.R1, ADR-0060.R1.N1

R205. No external engine: no semantic layer product (Cube, dbt Semantic Layer or the like) runs inside the core, because it would duplicate record scope, owner scope, field classes and taint, which the views already enforce, and add a second security model. Exporting the catalog to such tools comes after Phase 1 (ADR-0060.R38).
Source: ADR-0060.R1

### The catalog

R206. The catalog lives in `backend/nativeflows/query/analysis/catalog.py` beside the view declarations (ADR-0050.R45). It declares these kinds of object:
- **Facts:** a semantic view of schema `query`, its grain (what one row is), its time dimensions, its scope columns as the view declares them, and whether it is owner-scoped (ADR-0054.R15). A fact view pre-joins every dimension column it offers along a declared many-to-one path, so the compiler never joins facts to dimension tables, except for member labels (ADR-0060.R12).
- **Measures:** R212.
- **Dimensions:** R214.
- **Ambiguous terms:** business words that name more than one measure (for example "sales": ledger revenue or document amounts), each with its candidate measures, used for clarification (ADR-0060.R24).
Source: ADR-0060.R2

R207. Every catalog object has a definition hash: SHA-256 of its canonical declaration together with the declaration hash of its fact's view (columns and SQL, ADR-0050.R45) and the expansion of its selectors as resolved at evaluation (for `system_account:revenue`, the codes of the subtree in the core catalog). A changed view, or a new child account in a selected subtree, changes the hash. The core catalogs `analysis-measures.csv` and `analysis-dimensions.csv` (owner DS-33) mirror the code; they are seeded now and generated from the code once `query` exists, as the work item kinds are (ADR-0042). A CI test compares code and catalogs. The measures and dimensions of Phase 1 are the rows of these catalogs.
Source: ADR-0060.R2

### Facts

R208. The facts of Phase 1 (view: grain; time dimensions; owner scope; source):
- `journal_line_overview` (new): one posted journal line, or one `opening_turnover` row; `posting_date`, `posting_period`; owner-scoped through its document; ADR-0014 lines with system account and its path, operational account, partner, item, branch, warehouse, cost center, project, business unit (ADR-0069.R16), salesperson, transaction and company amounts, and the flags `is_closing_entry` (ADR-0012.R18), `is_migration_entry` (an entry of a migration fiscal year, ADR-0044.R2) and `is_special_period` (ADR-0012.R2).
- `system_account_turnover`: one company, period, system account, branch, cost center, project, business unit (ADR-0069.R16; ADR-0050.R53) and transaction currency; `posting_period`; not owner-scoped; ADR-0050.R53.
- `sales_line_overview` (new): one posted sales invoice, sales return or credit note line, signed (returns and credits negative); `posting_date`, `document_date`; owner-scoped; ADR-0047 lines with inventory quantity, transaction amount, posted company amount, unit cost (field class `cost`) and margin (field class `margin`).
- `purchase_line_overview` (new): one posted purchase invoice, purchase return or purchase credit note line, signed; `posting_date`, `document_date`; owner-scoped; ADR-0047.
- `open_item_overview`: one open item, at the current snapshot; `document_date`, `due_date`; owner-scoped through its origin document; ADR-0026, ADR-0050.R51.
- `stock_overview`: one stock row, at the current snapshot; no time dimension; not owner-scoped; ADR-0050.R51.
- `stock_movement_overview` (new): one posted material document line; `posting_date`; owner-scoped through its document; ADR-0020.
- `production_output_overview` (new): one posted production receipt line or scrap quantity; `posting_date`; owner-scoped through its document; ADR-0034.
- `production_variance_overview` (new): one production order, period and variance category, with the order's output item, warehouse and branch as record scope columns; `posting_period`; not owner-scoped; the stored split of ADR-0035.R15 (ADR-0060.R19).
Source: ADR-0060.R3

R209. Opening turnover. `journal_line_overview` also returns the company's `opening_turnover` rows (ADR-0049.R14) as rows with `row_source` `opening_turnover`, dated `opening_date`, with the account and system account they carry and no other dimension (member `none`). They count only in measures that exclude closing entries, as in ADR-0049.R14, and a range that cuts through an `opening_turnover` row's dates is refused (V14 of ADR-0060.R10). So a fiscal year to date that straddles a mid-year cut-over is answered.
- **Their own bucket.** A time breakdown finer than a row's span shows the row as its own member `~opening`, labelled with its dates ("before cut-over"), outside every month or week bucket and inside the total; it never lands in the cut-over month.
- **Scope.** These rows have no document, owner or branch, so they are in scope only for a grant on the fact with owner scope `company` and no record scope; any narrower grant leaves them out and sets `is_scope_filtered`.
Source: ADR-0060.R3

R210. Helper views. `posting_period_dimension` (periods with their fiscal year, kind and order) and one line-dimension view per fact that reaches a dimension one-to-many (`open_item_line_dimension`: the items of an open item's origin document lines) carry no scope of their own: they are reference or key views, joined only on keys of fact rows that already passed `is_in_scope`. They are declared in `query` like the facts.
Source: ADR-0060.R3

R211. The new fact views are ordinary additions to the view table of ADR-0050.R51, with column declarations, scope columns and taint columns like the others. They omit every `is_untrusted` column, so no fact taints a run. The business date reaches the views as the session setting `nativeflows.business_date`, which the builder sets, so `is_overdue` and `overdue_bucket` call no volatile function (ADR-0050.R44).
Source: ADR-0060.R3

### Measures

R212. A measure declares:
- **Identity:** `code` (`snake_case`), a translated label and description, and synonyms (each synonym belongs to one measure across the catalog; a CI check).
- **Fact and expression:** its fact; an aggregation (`sum`, `count`, `count_distinct`) over one column of the fact at the fact's grain, with a sign (`1` or `-1`); or a derived form computed after aggregation: `ratio` (numerator and denominator measures of the same fact) or `difference` (a pair of measures of the same fact). A column repeated from a coarser grain (a header amount on a line view) may not be summed; a CI check reads the view declaration.
- **Selectors:** fixed filters the measure always applies: a system account subtree (`system_account:revenue`), a control kind (`control_kind:receivable`), a kind (`kind:scrap`), a side, and the turnover options of ADR-0049.R6 and ADR-0049.R7: `migration_entries:exclude` on every turnover measure over journal lines (migration entries are opening balances, not movements) and `closing_entries:exclude` on the profit-and-loss measures (so the closing to the income summary does not cancel them). Balance measures keep both kinds of entry. Selectors over accounts name only codes of the core catalog `system-accounts.csv`, never an operational account code, so a measure means the same in every regime (ADR-0053.R1).
- **Additivity:** `additive`; `semi_additive`, with the one dimension it is not additive over (`posting_period` for balances: the value of a time bucket is its value at the bucket's end; `as_of` for current-snapshot measures, which sum freely over every attribute such as due date or document date); or `non_additive` (distinct counts and ratios: totals are recomputed from rows, never summed from cells).
- **Basis:** `company_currency`; `transaction_currency` (requires the `currency` dimension or a filter on one currency); `inventory_unit` (requires `item` or `product` as a dimension or a filter on one of them, because each product has one inventory unit, ADR-0018.R9); `count`; or `percent` (ratios).
- **Requires:** a dimension that must be grouped or filtered, besides those of the basis: the ledger turnover measures require `system_account`, since their sum over every account is zero.
- **Field class** (`cost`, `margin` or none), **default time dimension**, and **status** (`certified` or `deprecated`).
Source: ADR-0060.R4

R213. Field classes always. `cost_of_goods_sold` carries `cost`, and `gross_profit` and `gross_margin_percent` carry `margin`, whatever the plan groups by: grouped by item, partner or salesperson they would give unit cost and margin, which the line views protect. Statutory statements read the same accounts without a class (ADR-0049.R17) because a whole-company statement line reveals no unit figure; analysis can group, so it keeps the class. Examples of the catalog `analysis-measures.csv`:
- `net_revenue`: fact `journal_line_overview`; sum of `company_amount`, sign `-1`, selectors `system_account:revenue`, `closing_entries:exclude`, `migration_entries:exclude` (the subtree includes the revenue deductions, which reduce it); `additive`; `company_currency`; no field class.
- `stock_quantity`: fact `stock_overview`; sum of `quantity`; `semi_additive` over `as_of`; `inventory_unit` (requires `item` or `product`); no field class.
- `sales_margin_percent`: fact `sales_line_overview`; `ratio` of `sales_margin` to `sales_net_amount`; `non_additive`; `percent`; field class `margin`.
Source: ADR-0060.R4

### Dimensions

R214. A dimension declares:
- **Identity:** `code`, label, description, synonyms.
- **Kind:** `time` (with its grains); `entity` (members are record IDs); `catalog` (members are codes of a core catalog or reference table, such as system accounts, currencies, document types or movement types); or `enum` (members are codes from a closed list in the declaration).
- **Column:** the column name that every fact offering the dimension uses for it, the same name in each (a CI check).
- **Hierarchy:** its parent dimension (`item` → `product` → `item_group`; `partner` → `partner_group`; `warehouse` → `site`, ADR-0060.R34.N2; `account` → `system_account`), and for tree dimensions (`system_account`, whose codes form the tree of ADR-0010; `business_unit`, a tree over `parent_id` with the column `business_unit_path`, ADR-0069.R16) a `path` column for subtree filters.
- **Cardinality:** `low`, `high` or `identifier`, for the guard of ADR-0060.R10.
- **Member label:** the label view and its data label: `internal`, or `personal_by_row` where a member may be a person (partners of kind `individual`, employees; ADR-0019.R7).
- **Facts:** the facts that offer it along a many-to-one path; and the facts that reach it only one-to-many (for example `item` from `open_item_overview` through the origin document's lines), where it may filter (compiled to `EXISTS`) but never group.
- **Weeks** are ISO weeks, starting on Monday.
Source: ADR-0060.R5

R215. Fiscal grains come from the dimension `posting_period` (grains `posting_period`, `fiscal_year`), which follows the company's fiscal calendar (ADR-0007). Calendar grains come from the time dimensions `posting_date`, `document_date` and `due_date` (`day`, `week`, `month`, `quarter`, `year`). Examples of the catalog `analysis-dimensions.csv`:
- `posting_date`: kind `time`, calendar grains; cardinality `low`; offered by journal lines, sales and purchase lines, stock movements and production output.
- `item_group`: kind `entity`; top of `item_group` → `product` → `item`; cardinality `low`; label `internal`; offered by journal lines, sales and purchase lines, stock, stock movements, production output and variances.
- `partner`: kind `entity`; below `partner_group`; cardinality `high`; label `personal_by_row`; offered by journal lines, sales and purchase lines and open items.
Source: ADR-0060.R5

### Catalog rules

R216. Catalog rules:
- **Code, not company data.** The core catalog changes only with a release. Its version is the release version and its content hash is part of every result (ADR-0060.R15). A company adds no measure in Phase 1; it saves analyses (ADR-0060.R26).
- **One certified measure per business term.** Synonyms are unique across measures; a word that fits several measures is an ambiguous term (R206), never a synonym of one.
- **Changed definitions.** A release that changes a measure's or dimension's declaration changes its definition hash, so every saved analysis version and example that names it loses its verified badge until a person releases it again (ADR-0060.R26).
- **Deprecation.** A measure is never removed while a saved analysis version names it. A deprecated measure still runs for saved analyses, with the check result `analysis_measure_deprecated`, and the planner never uses it.
- **Neutral core.** Measures, dimensions and the reconciliation invariant use system accounts, control kinds and core enumerations only. A localization package adds no measure and changes none; its operational accounts appear only as members of the dimension `account` (R214).
Source: ADR-0060.R6

R217. CI checks of the catalog: every measure's fact, column, selector and required dimension exist; every system account named by a selector is a code of `system-accounts.csv`; every profit-and-loss measure over journal lines excludes closing entries and every turnover measure over journal lines excludes migration entries; every dimension column exists in each fact that offers it; no fact offers a dimension along a one-to-many path except as declared; no dimension reads an `is_untrusted` or `is_secret` column; synonyms are unique; the catalogs equal the code.
Source: ADR-0060.R6

### The plan

R218. The plan, `plan_version` 1, is a JSON object validated by a pydantic model (unknown fields rejected, ADR-0008.R3). Its fields are `plan_version`, `measures`, `dimensions`, `filters`, `time`, `derived`, `contributions`, `sort`, `limit`, `with_other_row` and `with_total_row`:
- **`measures`:** a list of at least 1 and at most 5 measure codes (for example `net_revenue`).
- **`dimensions`:** at most 3 objects (none is allowed), each `{"dimension": <dimension code>}`, with `grain` for time dimensions (for example `item_group`; `posting_date` with `grain` `month`).
- **`filters`:** each `{"dimension", "op", "values"}`: a dimension, an operator and member keys: `eq`, `in` and `not_in` (at most 100 values, ADR-0050.R47), and `in_subtree` for tree dimensions (for example `system_account` `in_subtree` `revenue_goods`). Entity members are IDs and catalog and enum members are codes, found through `ListAnalysisDimensionMember` or the catalog, never names.
- **`time`:** the time `dimension`; a `range` (`{"from", "to"}` dates, a named period, or `{"relative": …}`, R219 and R220); an optional `compare` (a second range, or `{"relative": …}` with `previous_period`, `previous_month_same_days` or `same_period_last_year`); `special_periods` (`include`, the default, or `exclude`, as ADR-0049.R13); and for semi-additive measures `as_of`, which defaults to the end of the range.
- **`derived`:** objects `{"op", "of"}` with `op` `difference`, `growth` (a ratio to the comparison, shown as percent) or `share_of_total`, each `of` a measure; computed by the engine after aggregation, never by a model.
- **`contributions`:** null or `{"measure", "dimension", "top"}` for ADR-0060.R18; it needs `time.compare`.
- **`sort`, `limit`, `with_other_row`, `with_total_row`:** `sort` is a list of `{"by", "dir"}` (`dir` for example `desc`), only by a measure or a dimension of the plan; `limit` at most 1,000 for people and 50 for agent runs. A `limit` without the other row truncates (ADR-0060.R15).
Source: ADR-0060.R7

### Time

R219. Relative ranges are a closed list: `today`, `yesterday`, `this_week`, `last_week`, `month_to_date`, `this_month`, `last_month`, `this_calendar_quarter`, `last_calendar_quarter`, `this_calendar_year`, `last_calendar_year`, `this_fiscal_quarter`, `last_fiscal_quarter`, `fiscal_year_to_date`, `this_fiscal_year`, `last_fiscal_year`, and with `n` from 1 to the span limit: `last_n_days`, `last_n_weeks` (whole ISO weeks before the current one) and `last_n_months` (whole months before the current one; `n` 12 gives the rolling year).
Source: ADR-0060.R8

R220. Named periods: `{"month": "2026-03"}`, `{"calendar_quarter": "2026-Q1"}`, `{"calendar_year": 2025}`, `{"fiscal_quarter": "2026-Q2"}` (the second quarter of the fiscal year that starts in 2026) and `{"fiscal_year": 2026}` (the fiscal year that starts in 2026). They let a plan name "March 2026" or "Q1 2026" without computing dates; an absolute `from`/`to` range is for dates a person typed.
Source: ADR-0060.R8

R221. Resolution. Code resolves relative ranges and named periods against the company's business date (`clock.today`, ADR-0007.R15) and fiscal calendar, and echoes the absolute dates in the result. A model never computes a date: an absolute date in an agent's plan must be stated in the question (ADR-0060.R22).
Source: ADR-0060.R8

R222. Comparison. `previous_period` is the range of the same length ending the day before; for whole months, quarters or years it is the previous block of the same length. `previous_month_same_days` shifts the range by one month, day for day (a month to date against the same days of the previous month), with days beyond the month's end clamped to its last day. `same_period_last_year` shifts the range by one year, with 29 February mapped to 28 February.
Source: ADR-0060.R8

R223. Which date. Every plan names its time dimension (posting date, document date, due date or posting period), and the result restates it, so "last month" is never ambiguous between dates.
Source: ADR-0060.R8

### Canonical form and hashes

R224. Canonical form and hashes of the analysis plan are named apart from the command `plan` and `plan_hash` of ADR-0008:
- **Canonical form:** keys sorted, lists of measures, filters and filter values sorted, defaults filled, canonical numbers and dates (ADR-0006.R13; ADR-0007.R3).
- **`analysis_plan_hash`:** SHA-256 of the canonical plan as written, relative dates kept, together with the definition hashes of every catalog object it names. It identifies an analysis for saved analyses, examples and the verified badge, so a verified "last month" stays verified every month, and a changed measure definition ends the verification.
- **`analysis_resolved_hash`:** SHA-256 of the canonical plan with absolute dates, plus the catalog hash. It keys the result cache (ADR-0060.R30).
Source: ADR-0060.R9

### List export

R230. `CreateListExport` (module `query`, effect class `other`; ADR-0040.R6) takes a `List<…>` query, its filters, columns and language. It creates a `list_export` record (`state`: `queued`, `running`, `done`, `failed`) and emits `ListExportCreated`. A long-job consumer of that event on queue `jobs` (ADR-0031.R15) writes the file, so no job is enqueued on a handler's path (ADR-0013.R13). `CreateListExport` refuses every query of module `reporting` with `list_export_query_not_allowed`: statutory reports and books leave only through `RenderReport`, which carries the opening, totals and closing rows and the full-scope check (ADR-0049.R20).
Source: ADR-0050.R54, ADR-0050.R54.N1

R231. The export consumer pages through the query as the requester, so field classes and scope apply, translates headers and enumerations on the server, and writes an `.xlsx` with XlsxWriter (ADR-0002). More rows than `list_export_max_rows` (installation setting, default 100,000) fail with `list_export_too_large`.
Source: ADR-0050.R54

R232. The export file is an attachment that is not accounting evidence; its bytes are deleted after 7 days. Downloading it needs the same query permission and is audited. An export containing personal columns writes a processing-log entry (ADR-0019.R11).
Source: ADR-0050.R54

R233. Agents never export (ADR-0050.R30). People export analysis results through `ListAnalysisResultRow`, which reruns the plan as the requester (ADR-0060.R17).
Source: ADR-0050.R54, ADR-0050.R54.N2

### Held-out golden cases

R234. Assignment. A golden case is held out when the first byte of the SHA-256 of the UTF-8 text `<company ID>:<case ID>` (both UUIDs in canonical lowercase hyphenated form) is below 51. The assignment is deterministic, so nobody chooses it, and the database checks a label's `is_held_out` against it (`INV-685`).
Source: ADR-0059.R16

R235. Kept from the generator. For a run of a drafting agent type, the query layer excludes the held-out cases from every row query and aggregate the run calls, whether labelled or not: rows of the declared case tables, and rows of other tables whose declared case-reference columns point at a held-out case (the receipt proposed from a held-out line, its lines and settlements). An aggregate that cannot apply the filter is refused (`held_out_filter_unavailable`). Code that fits or searches candidates uses only cases that are not held out. `ListGoldenCaseLabel` is on no tool list.
Source: ADR-0059.R16

R236. A closed tool list. A registry CI check refuses a drafting agent type version whose tool list holds a query not registered as held-out filtered. Reads of evidence, shadow outcomes, monitor snapshots, automation executions and `GetAutoPostShadowEvaluation` are on no drafting tool list, because they hold per-case results of the later window.
Source: ADR-0059.R16

R237. A person's draft. The query layer does not filter a person's reads. Evidence records whether the version was drafted by a filtered run or by a person (`drafted_by_filtered_run`), so the approver knows what "held-out" means for it.
Source: ADR-0059.R16

R238. Checked by ID sets, as the second line: at evidence creation `automation` intersects the held-out case IDs with every row reference the drafting run recorded (`context_refs`, `result_refs`, `request_refs`), each mapped to its case through the case-reference columns; a non-empty intersection makes the evidence insufficient (`held_out_case_seen`, `EC-166`), and the database refuses sufficient evidence with a non-zero count.
Source: ADR-0059.R16

R239. The `auto_post_advisor` agent type is a drafting agent type and a Phase 2 agent type: its tools `ListAutoPostCase`, `EvaluateAutoPostBacktest` and `ListAutoPostThresholdCandidate` are held-out filtered, its decision table drafts follow the lifecycle of ADR-0059, and its settings proposals carry the backtest as evidence (ADR-0065.R17, ADR-0065.R18). In Phase 1 people propose gateway settings and tables, and the assistant may draft them on request (ADR-0078.R2, ADR-0078.R8).
Source: ADR-0059.R16.N1, ADR-0059.R16.N2

## Invariants

| INV | Check point | Statement | Protects |
| --- | --- | --- | --- |
| `INV-411` | run | For full scope, every range and every system account subtree, each ledger analysis measure equals the turnover measure of ADR-0049.R6 over the operational accounts mapped to that subtree for the same range and `special_periods` option (`change`, `debit_turnover` or `credit_turnover`), with `closing_entries=exclude` for the profit-and-loss measures and migration entries left out, in every regime. Name `management_turnover_equals_report_turnover`; area `reporting`; keys `system_account`, `from`, `to`; first step 5. | R212; ADR-0060.R35 |

Cited, with its row in the `automation` spec: `INV-685` (`golden_labels_by_approvers`, area `platform`), whose database check holds a label's `is_held_out` to the deterministic assignment of R234.

## Edge cases

| EC | Name | Case | Outcome | Source |
| --- | --- | --- | --- | --- |
| `EC-155` | `analysis_management_equals_journal` | At month end, net revenue by item group from the analysis layer at full scope equals ADR-0049's `change` measure with `closing_entries=exclude` over the operational accounts of the `revenue` system account subtree (`INV-411`). | `must_succeed` | ADR-0060.R4; ADR-0060.R35 |
| `EC-170` | `analysis_year_closed_by_entries` | A regime closes profit and loss by closing entries and an adjustment posts in the special period: net revenue for the year excludes the closing entry and includes the adjustment, `special_periods` `exclude` leaves it out, the closing balance of the revenue subtree after closing is zero, and both agree with ADR-0049's turnover (R212, R218). | `must_succeed` | ADR-0060.R4; ADR-0060.R7; ADR-0060.R35; ADR-0049.R7; ADR-0049.R13 |

Cited, with its row in the `automation` spec: `EC-166` (`held_out_case_leak`, `must_reject:held_out_case_seen`), the case of R238.

## Settings

None: see chunks 3 and 4; no rule of this chunk uses a key of `settings.csv`.

`list_export_max_rows` (installation setting, default 100,000; R231) is named by ADR-0050.R54 and is absent from `settings.csv`. `nativeflows.business_date` (R211) is a database session setting that the view builder sets, not a key of `settings.csv`.

## Conflicts

CONFLICT ADR-0060.R5: ADR-0060.R34.N2 governs the hierarchy list; `warehouse` → `site` stands in R214 and `warehouse` → `branch` is not restated; ADR-0069.R16 adds the tree dimension `business_unit` with its path column.
CONFLICT ADR-0060.R3: ADR-0069.R16 governs the grain of the facts `journal_line_overview` and `system_account_turnover`, which gains the business unit (ADR-0050.R53.N2 states the same for the view); R208 lists the unit.
CONFLICT ADR-0060.D0: ADR-0060.R34.N3 governs the dimension total; the totals of measures and dimensions typed in the Decision text are not restated, and R207 names the catalogs as the list.
CONFLICT ADR-0059.R16.N1: ADR-0059.R16.N2 governs the phase; `auto_post_advisor` is a Phase 2 agent type, so R239 states that people propose gateway settings and tables in Phase 1.

## Trace

| Source | Where |
| --- | --- |
| ADR-0050.R54 | R230-R233 |
| ADR-0050.R54.N1 | R230 |
| ADR-0050.R54.N2 | R233 |
| ADR-0054.R24.N3 | ref: ADR-0054.R24.N3 |
| ADR-0059.R16 | R234-R238 |
| ADR-0059.R16.N1 | R239 |
| ADR-0059.R16.N2 | R239 |
| ADR-0060.D0 | R201 |
| ADR-0060.R1 | R202-R205 |
| ADR-0060.R1.N1 | R204 |
| ADR-0060.R2 | R206-R207 |
| ADR-0060.R3 | R208-R211 |
| ADR-0060.R4 | R212-R213 |
| ADR-0060.R5 | R214-R215 |
| ADR-0060.R6 | R216-R217 |
| ADR-0060.R7 | R218 |
| ADR-0060.R8 | R219-R223 |
| ADR-0060.R9 | R224 |
