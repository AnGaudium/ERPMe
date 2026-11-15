# Research: agent-assisted analysis and barcode capability

Date: 2026-11-15. Input for the architect who designs both areas for ERPMe. Research only: nothing here is decided.

**Tags.** Each claim carries a source tag:

- **[doc]**: vendor or standards documentation;
- **[blog]**: vendor blog, press release, community post or trade press. Vendor accuracy figures are always [blog], because nobody has replicated them;
- **[paper]**: a research paper or benchmark;
- **[inference]**: my own reasoning or general knowledge, not taken from a source.

**ERPMe facts this report builds on** (from ADR-0018, ADR-0023, ADR-0049, ADR-0050):

- Principle 13: every number shown comes from deterministic code.
- Agents read through semantic views in schema `query`, exposed as `List<View>` and `Get<View>`. The builder composes one `SELECT`. Agents never write SQL. There is record scope, owner scope and field classes. Agent pages hold at most 200 rows, capped by `max_rows_read`. The views are described as MCP resources.
- The statutory engine computes every figure as an exact sum of journal lines. `ListReportLineContribution` drills down to them.
- Barcodes: `item_barcode` (item, unit, barcode) is unique per company. Bin barcodes and handling-unit barcodes are each unique in the company.
- Every scan is an idempotent command. Serials are scanned at confirmation. The PWA comes at step 9. Offline scanning comes after Phase 1. SSCC labels with carrier integration are listed as later.

---

# Part A: Agent-assisted reporting and analysis

## A1. Where wrong numbers come from: text-to-SQL today

### Benchmarks

| Benchmark | What it measures | Best reported result | Tag |
| --- | --- | --- | --- |
| **BIRD** | Single questions over 95 real databases with "evidence" hints. Scored by execution accuracy (EX) | About 80% EX for the top single model (Gemini-SQL2, June 2026). 82.4% EX for a multi-component system (Sep 2026). Human baseline 92.96% | [blog] https://aiweekly.co/alerts/googles-gemini-sql2-tops-bird-text-to-sql-at-8004, https://technologymagazine.com/news/huawei-datagallery-tops-benchmark-for-enterprise-text2sql-ai |
| **BIRD Mini-Dev, expert re-verified** | A cleaned subset | 93.2% claimed (ReViSQL). Much of the gap to humans is label noise in BIRD itself | [paper] https://arxiv.org/html/2603.20004v2 |
| **Spider 2.0** (ICLR 2025) | 632 enterprise workflows on BigQuery, Snowflake and dbt projects, with thousand-column schemas, dialects and nested columns | Paper baseline: o1-preview with Spider-Agent about 17–21%. Classic Spider 1.0 was 91% | [paper] https://www.alphaxiv.org/abs/2411.07763v2 |
| **Spider 2.0 leaderboard, Nov 2026** | Same benchmark, three tracks | Snow 96.7, Lite 76.2, **DBT 65.6** (dbt-project tasks remain hard) | [doc] https://spider2-sql.github.io/ |
| **Spider2-snow via a semantic layer** | Agent writes a JSON "Semantic Model Query" that a compiler turns into SQL | 94.15% EX, self-reported | [paper] https://arxiv.org/pdf/2606.31041 |
| **BEAVER** | Real enterprise data warehouses | Very low accuracy for off-the-shelf models. Error mix: schema linking 35.2%, joins 10.9% | [paper] https://arxiv.org/pdf/2409.02038 |
| **TrustSQL** | Whether a model abstains on unanswerable or likely-wrong questions, with penalty scoring | In v1, no method beat "always abstain" across penalty levels. Under severe penalties it stays hard | [paper] https://arxiv.org/abs/2403.15879v4 |

**Reading the numbers [inference].** About 80% on a clean benchmark means one wrong answer in five, and it arrives with the same confidence as the right ones. Leaderboard gains come from heavy agent scaffolding: many samples, execution feedback and self-consistency. That raises cost and latency per question. The highest scores (Spider2-snow above 94%) come from systems that put a semantic or compiler layer between the model and SQL. That is the strongest evidence for the ERPMe direction: the model chooses, code computes.

### Failure modes [paper unless marked]

1. **Schema linking.** Wrong table or column, or a near-synonym column such as `amount` vs `amount_company_currency`. This is the largest category in BEAVER. https://arxiv.org/pdf/2409.02038
2. **Join errors.** An INNER join where LEFT was needed drops unmatched rows. A join to a one-to-many child inflates sums: the "fan-out" or chasm trap. BEAVER files this under missing deduplication and over-aggregation. https://arxiv.org/pdf/2409.02038
3. **Wrong grain or aggregation.** SUM of an already aggregated value. Averaging ratios instead of computing a ratio of sums. COUNT instead of COUNT DISTINCT. https://arxiv.org/pdf/2211.06193, https://arxiv.org/pdf/2503.24364
4. **Ambiguity.** "Revenue" could be invoiced, booked or recognized. "Last month" could be calendar or fiscal. Ambiguity comes both from the question and from the schema. https://arxiv.org/html/2501.18197v1
5. **Values and filters.** Wrong literal (`'Done'` vs `'done'`), a status code missing from a filter, a time zone, an open or closed date bound. These dominate errors across dialects. https://arxiv.org/pdf/2606.08018
6. **Confident answers to underspecified questions.** A correct-looking output can hide wrong logic. https://neurips.cc/virtual/2026/157927
7. **ERP-specific traps [inference].** Reversed or cancelled documents counted twice. Draft vs posted documents. Currency mixing (transaction vs company currency). Unit-of-measure mixing (cartons vs pieces). Fiscal period vs posting date vs document date. Intercompany eliminations. Owner scope silently shrinking a total, so the user sees "total sales" that is only their own sales.

## A2. Semantic layers

A semantic layer declares **measures** (aggregations with a fixed formula), **dimensions** (group-by attributes), **entities and joins** (with cardinality) and **time grains**. A query names measures and dimensions. The engine writes the SQL, so the join path and the aggregation are fixed by the definition, not chosen by a model.

| Layer | Model | How a query is expressed | Agent interface | Notes | Tag |
| --- | --- | --- | --- | --- | --- |
| **dbt Semantic Layer / MetricFlow** | YAML semantic models: entities, dimensions, measures. Metrics of type simple, ratio, cumulative, derived and conversion | `metrics` + `group_by` (`Dimension('order__region')`, `TimeDimension('metric_time','month')`) + `where`. Saved queries hold reusable sets. A multi-metric query allows only the dimensions all its metrics share | JDBC/GraphQL APIs, MCP server | dbt's own benchmark (11 questions): 100% on questions the layer covers vs 51–62% for text-to-SQL. In-sample and small; critics note better modeling alone lifted text-to-SQL to 90% | [doc] https://docs.getdbt.com/docs/build/saved-queries, https://docs.getdbt.com/docs/build/metricflow-commands; [blog] https://docs.getdbt.com/blog/semantic-layer-vs-text-to-sql-2026 |
| **Cube** | Cubes and views with measures, dimensions, segments and joins in YAML or JS | JSON: `measures`, `dimensions`, `timeDimensions` (granularity, dateRange), `filters`, `segments`. `/v1/meta` lists the catalog. `/v1/load` returns rows **and the generated SQL** | REST, GraphQL, SQL API, MCP. An AI API turns a message into a Cube query | Row-level rules come from a signed security context (JWT) and are applied before SQL compiles. Pre-aggregations and a cache | [doc] https://cube.dev/docs/product/apis-integrations/ai-api; [blog] https://cube.dev/articles/governed-ai-data-access |
| **LookML (Looker)** | Views (dimensions, measures), explores (join graph with `relationship:` cardinality), symmetric aggregates prevent fan-out | Explore + fields + filters | Conversational Analytics calls Looker's query API; the model picks fields, Looker writes SQL | Google claims the layer cuts gen-AI data errors by up to two thirds (internal test). Advises narrow agents over few explores | [blog] https://cloud.google.com/blog/products/business-intelligence/how-lookers-semantic-layer-enhances-gen-ai-trustworthiness; [doc] https://docs.cloud.google.com/looker/docs/conversational-analytics-looker-best-practices |
| **Malloy** | Open modeling and query language: sources, measures, dimensions, nested views. Now under the Malloy Foundation | Malloy queries (a full language, not just selection) | Publisher serves models over REST and MCP | Publisher's MCP endpoint has no authentication by default and binds 0.0.0.0, a warning sign for agent exposure | [doc] https://docs.malloydata.dev/documentation/user_guides/publishing/mcp_agents; [blog] https://venturebeat.com/data/57-of-enterprises-traced-a-wrong-ai-answer-to-missing-business-context-credible-bets-portable-open-source-semantic-code-beats-proprietary-metadata |
| **AtScale** | Universal semantic layer (OLAP-style cubes) over warehouses | MDX/DAX/SQL | NLQ via LLM over the model | Vendor TPC-DS test: 20% accuracy schema-only vs 92.5% with the layer (40 questions). Hosts a public TPC-DS text-to-SQL leaderboard | [blog] https://www.atscale.com/?p=24087, https://www.atscale.com/?p=24976 |
| **Snowflake semantic views** | Database objects: logical tables, relationships, facts, dimensions, metrics, synonyms, verified queries | SQL over the semantic view | Cortex Analyst; SELECT privilege on the view | Row access and masking policies apply under the caller's role | [doc] https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-analyst |
| **Open Semantic Interchange → Apache Ossie (incubating)** | Vendor-neutral YAML/JSON: datasets, relationships, metrics, one model per document | Interchange format, not a query engine | — | Spec 0.1.1 (Dec 2025). Renamed and moved to the Apache Incubator in July 2026. Few tools import it yet | [blog] https://atlan.com/know/ai-agent/semantic-layer/what-is-open-semantic-interchange/ |

**Common design [inference]:**

- Measures carry their aggregation and their **grain**.
- Joins carry their **cardinality**, so the engine can refuse or correct fan-out (LookML symmetric aggregates).
- Dimensions carry synonyms and allowed values.
- The catalog is machine-readable, so an agent can list it.
- The query is a small structured object, not SQL.

## A3. AI analyst products

| Product | What grounds the model | Trust mechanism | Shows its work | Abstention / clarification | Security under AI | Cost model | Tag |
| --- | --- | --- | --- | --- | --- | --- | --- |
| **Databricks Genie** (AI/BI) and Genie One | Genie space: chosen Unity Catalog tables, instructions, example SQL, SQL functions | **Trusted assets:** a response is marked *Trusted* when it was produced by a parameterized example query or a registered SQL function. **Benchmarks:** up to 500 test questions with expected SQL, used to evaluate, not to instruct | "Show generated code". Editors can correct and rerun | Asks a clarifying question or says it cannot answer from the given information. Users can "Request review"; managers confirm or correct in a Monitor tab, and can turn a fix into an instruction | Unity Catalog permissions of the user | Warehouse compute | [doc] https://learn.microsoft.com/da-dk/azure/databricks/genie/trusted-assets, https://docs.databricks.com/aws/en/genie/talk-to-genie, https://docs.databricks.com/aws/en/genie/monitor; Genie One 84.5% claim [blog] https://aiweekly.co/alerts/databricks-genie-one-ships-sql-grounded-agentic-ai |
| **Snowflake Cortex Analyst** | Semantic model (YAML) or semantic view; custom instructions | **Verified Query Repository (VQR):** question + SQL pairs using logical names, retrieved by similarity. Answers built on a verified query are flagged. **Evaluations** run the VQR as ground truth and report accuracy, regressions and latency | Returns the SQL with the answer | A classifier step flags ambiguous or non-SQL questions and returns suggestions. Custom instructions can tell it when to reject or ask | Full RBAC, row access and masking policies under the caller's role | **Per message:** 67 credits per 1,000 successful messages, plus warehouse compute. Usage history view per hour | [doc] https://docs.snowflake.com/user-guide/snowflake-cortex/cortex-analyst/verified-query-repository, https://docs.snowflake.com/user-guide/snowflake-cortex/cortex-analyst-evaluations, https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-analyst/custom-instructions; [blog] https://www.snowflake.com/en/blog/engineering/snowflake-cortex-analyst-behind-the-scenes/, https://select.dev/posts/snowflake-cortex-analyst-overview-pricing-and-cost-monitoring |
| **Power BI Copilot** | Semantic model (measures in DAX), with **Prep data for AI**: simplified AI schema, **verified answers** (a chosen visual bound to trigger phrases), AI instructions | Model marked **Approved for Copilot**. Verified answers return a human-built visual | Diagnostics download | — | RLS applies to the user [blog] | Fabric capacity units per token: 400 CU-s per 1k input tokens, 1,200 per 1k output tokens. Cached repeats free for 2 days | [doc] https://learn.microsoft.com/power-bi/create-reports/copilot-prepare-data-ai, https://learn.microsoft.com/fabric/fundamentals/copilot-fabric-consumption |
| **Tableau Pulse / Tableau Agent** | **Metrics layer:** one definition per metric, with favorable direction and key dimensions | An **Insights Platform** of statistical services computes insights first: period change, top and bottom contributors, concentrated contribution, drivers, unusual change. The LLM only summarizes the structured facts | Each insight links to its chart | — | Tableau permissions | Tableau+ bundle | [doc] https://help.tableau.com/current/online/en-us/pulse_insights_platform_insight_types.htm; [blog] https://tableau.com/blog/tableau-pulse-and-tableau-ai |
| **ThoughtSpot Sage → Spotter** | Worksheets/models with columns, synonyms, formulas | The question becomes **search tokens** (a visible intermediate form). The engine resolves join paths and formulas and generates SQL. Memory keeps definitions across follow-ups | Shows tokens and SQL. Users edit tokens to fix an answer | Feedback edits are stored as learned mappings | ThoughtSpot RLS | Per user / consumption | [blog] https://www.thoughtspot.com/blog/introducing-spotter-ai-analyst, https://www.thoughtspot.com/trust/agentic-analytics; [doc] https://docs.thoughtspot.com/cloud/10.15.0.cl/spotter-agent |
| **Looker + Gemini (Conversational Analytics)** | LookML explores | Looker, not the LLM, writes SQL. Agents are configured per explore with instructions | Shows the query and fields | — | LookML access filters, user attributes | Per user | [doc] https://docs.cloud.google.com/looker/docs/2606/conversational-analytics-overview; [blog] https://cloud.google.com/blog/products/data-analytics/gemini-in-looker-deep-dive |
| **SAP Analytics Cloud Just Ask / Joule analytical insights** | Models indexed by an admin (Datasphere models in Business Data Cloud). A vector index over model metadata picks the model | Only admin-indexed models are reachable | Answers as SAC charts | — | SAC and Datasphere authorizations | Joule entitlement + SAC Enterprise | [blog] https://community.sap.com/t5/technology-blog-posts-by-sap/introducing-analytical-insights-in-joule-empowering-smarter-decisions/ba-p/14083673; [doc] https://www.sap.com/products/technology-platform/joule-analytical-insights-feature.html |
| **Oracle Fusion Data Intelligence** | Prebuilt FDI semantic models and KPIs over Fusion ERP, SCM, HCM and CX | AI Assistant in Oracle Analytics. An **MCP server** exposes semantic models, KPIs and workbooks to outside assistants | — | — | Existing role-based access, duty roles and data security policies still apply over MCP | Subscription | [blog] https://blogs.oracle.com/analytics/fusion-data-intelligencefdi-integrated-mcp-server, https://www.oracle.com/sg/news/announcement/ai-world-oracle-announces-ai-assistant-and-new-features-for-fusion-data-intelligence-2025-10-14/ |

**What converges across all eight [inference]:**

1. A curated, **narrow** scope per assistant: a space, explore, admin-indexed model or approved model. Nobody points the model at the whole schema.
2. A **library of human-verified question-to-query pairs**, used both as few-shot grounding and as a "trusted" badge.
3. **Evaluation sets** run like regression tests on every model change.
4. The **query is shown** (SQL, tokens or fields), and a human can correct it. Corrections flow back into the library.
5. **Security is the platform's**, enforced on the executed query under the user's identity, never by prompt.
6. Statistical insight engines (Pulse, Snowflake Top Insights) compute the variance facts first. **The LLM narrates; it does not compute.**

## A4. Verified queries and trusted answers

- **Two uses of the same artifact.** As *retrieval context*: Cortex Analyst pulls similar verified queries into the prompt. As a *direct answer*: Genie's trusted assets execute a parameterized query or function, and the answer is labelled Trusted only when that exact asset produced it. [doc] https://docs.snowflake.com/user-guide/snowflake-cortex/cortex-analyst/verified-query-repository, https://learn.microsoft.com/da-dk/azure/databricks/genie/trusted-assets
- **Evaluation discipline.** Snowflake evaluations remove the verified query under test from a temporary copy of the model, so the score measures generation, not lookup. They report regressions. Genie benchmarks are kept apart from instructions. [doc] https://docs.snowflake.com/user-guide/snowflake-cortex/cortex-analyst-evaluations
- **Maintenance loop.** Feedback → review queue → a fix becomes a verified query or instruction. Snowflake suggests verified queries from usage logs; a human approves them. [doc] https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-analyst/verified-query-suggestions
- **For ERPMe [inference].** A "verified query" maps onto a **saved query plan** (A9) with parameters, an owner, a review state and test cases. When the planner's plan equals a verified plan up to its parameters, the answer carries a *verified* badge. Otherwise it is *generated*. The badge is computed by code from the plan hash, never claimed by the model.

## A5. Number grounding and citation

Sources here are mostly blogs; rigorous studies of numeric claim verification in analytics are thin.

- Grounding means the model can only report what it retrieved. Each figure should travel with source, timestamp and a link the human can follow. [blog] https://arkolith.com/blog/stop-ai-hallucinating-market-data
- Deterministic settings make a wrong number repeatable, not correct. Freshness must be explicit, because the model has no sense of data age. [blog] same source
- Tableau Pulse's order (statistics produce facts, then the LLM writes text) is the best documented product pattern for narrated numbers. [doc] https://help.tableau.com/current/online/en-us/pulse_insights_platform_insight_types.htm

**Mechanism for ERPMe [inference]:**

1. **Result envelope.** Every query result returns typed cells with an id: `{cell_id, measure, dimension values, value, unit or currency, scale}`. It also carries `as_of` (transaction snapshot time), `is_scope_filtered`, the row count, the plan and its hash.
2. **Template narration.** The model writes text with placeholders (`{{c3}}`), never digits. The renderer substitutes the formatted values: locale, currency and rounding all done by code. Principle 13 then holds by construction.
3. **Numeral linter.** A post-check rejects any narration that contains a digit outside a placeholder. Allow-listed literals are dates the user typed and ordinal words. On failure: one retry, then a table-only answer.
4. **Derived numbers** such as "up 12%" or "twice as much" are computed only as declared derived measures or comparison operators in the plan (A9), never by the model.
5. **Every figure clickable.** Each figure carries a drill handle (A9.6) to the rows behind it, ending at documents or journal lines, the same contract as `ListReportLineContribution`.

## A6. Explaining variances (contribution analysis)

**What the products do:**

- **Tableau Pulse:** top and bottom contributors, a concentrated-contribution alert when few members make most of the metric, top drivers of change, unusual-change detection. All computed by statistics; the LLM summarizes them. Third-party descriptions of "drivers" disagree on direction. [doc] https://help.tableau.com/current/online/en-us/pulse_insights_platform_insight_types.htm
- **Snowflake Top Insights** (`SNOWFLAKE.ML.TOP_INSIGHTS`, GA Nov 2024): compares a control and a test period or group. It finds the segments (dimension combinations) that drive the change, using a decision tree, and reports contribution, relative contribution and growth per segment. Categorical cardinality is reduced above 5. [doc] https://docs.snowflake.com/en/user-guide/ml-functions/top-insights
- **Power BI** key influencers and the decomposition tree: an interactive, explainable split of a measure by dimensions. [doc] https://learn.microsoft.com/power-bi/visuals/power-bi-visualization-decomposition-tree

**Transferable maths [inference]**, deterministic and exact, so it fits Principle 13:

1. **Additive contribution.** For an additive measure M and a dimension D, the change ΔM equals the sum over members d of (M₁(d) − M₀(d)). Rank members by |Δ|. The sum must reconcile exactly to the total, shown as a check row; "other" absorbs the tail.
2. **Price-volume-mix** for revenue or margin. Price effect = Σ (p₁ − p₀)·q₁. Volume effect = (Q₁ − Q₀)·p̄₀. Mix effect = Σ (s₁ − s₀)·Q₁·p₀, where s is the share of each item. Use one documented convention. The remainder must be zero; that is a test.
3. **Ratio measures** (margin %, on-time %) do not decompose additively. Decompose the numerator and denominator, or use a rate/mix split.
4. **Manufacturing variances already exist as postings.** ERPMe's production costing (ADR-0035) posts deterministic variances: price, usage or quantity, lot size, scrap, rework. "Why is the cost of product X higher this month?" should be answered by reading those variance postings by type and order, not by a new statistical model. Statistical segment mining is for open questions ("which customer groups drove the sales drop").
5. **Segment search** (two-dimension combinations, pruning by minimum support) is the only part that resembles ML. It can be a deterministic exhaustive search over declared dimensions with caps, so results stay reproducible.

## A7. Saved reports, KPI definitions, governance, row-level security, cost

**Reports and dashboards as data:**

- Power BI moved to text formats: TMDL for the semantic model, PBIR for reports. Both live in git and deploy through CI. [doc] https://learn.microsoft.com/power-bi/developer/projects/projects-dataset, https://powerbi.microsoft.com/blog/power-bi-enhanced-report-format-pbir-in-power-bi-desktop-developer-mode-preview
- LookML dashboards and dbt saved queries and exports are text too. [doc] https://docs.getdbt.com/docs/build/saved-queries
- For agents this matters twice over. An agent can **read** a dashboard definition to answer "what does the sales dashboard count as revenue?". An agent can also **propose** a new report as a reviewable diff, never by mutating live state. [inference]

**KPI definitions as governed objects.** A KPI has:

- a measure (or ratio of measures), grain, time logic, favorable direction and target or threshold source;
- an owner, a version, status (draft, certified, deprecated), a description and synonyms.

The Tableau Pulse metric definition and the Snowflake semantic view metric are the closest product models. [doc] https://tableau.com/metrics; [inference]

**Row-level security under AI queries:**

- Every product enforces security in the engine under the end user's identity: Snowflake RBAC and row access policies, Cube's security context, Unity Catalog, Oracle's data security over MCP, Power BI RLS. Never in the prompt.
- Pitfalls [inference]:
  - **Silent partial totals.** Owner scope makes "total sales" mean "my sales". The answer must say so. ERPMe already computes `is_scope_filtered`; surface it in the answer text.
  - **Inference through aggregates.** Small cells reveal individuals, such as the salary of a one-person department. A minimum cell size rule for personal or `cost` field-class measures.
  - **Cache leakage.** A cached result reused across users with different scope. Cache keys must include the scope fingerprint.
  - **Verified-query bypass.** A trusted query written by an admin must still run under the asker's scope.

**Cost control:**

- Cortex Analyst bills per successful message plus compute. Fabric bills capacity per token and caches repeats for 2 days. [doc] https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-analyst, https://learn.microsoft.com/fabric/fundamentals/copilot-fabric-consumption
- Levers [inference]:
  - verified-plan hits skip the LLM (zero model cost);
  - plan caching by normalized question;
  - pre-aggregates for hot measures;
  - statement timeouts and `max_rows_read` (ERPMe already has them);
  - per-user and per-company monthly budgets;
  - a cheap model for routing and clarification, the strong model only for planning;
  - no agent "exploration loops" that run dozens of queries without a budget.

## A8. Pitfalls (Topic 1)

1. **Row listing as a substitute for aggregation [inference, ERPMe-specific].** Today agents only have `List<View>` with pages of at most 200 rows. Asked "total open receivables by customer", an agent will either sum rows itself, which breaks Principle 13, or truncate silently. **This is the biggest gap.** Aggregation must be a server operation.
2. **Fan-out** when a measure from a parent is grouped by a child dimension, such as document totals grouped by line item. [paper] BEAVER
3. **Non-additive measures summed across dimensions:** averages, ratios, closing balances over time, stock on hand summed over dates. [inference]
4. **Semantic drift.** Two "revenue" measures. Fix: one certified measure per business term, plus synonyms. [inference]
5. **Overconfident answers to out-of-coverage questions.** The semantic layer's ceiling. dbt's benchmark itself shows 0% on questions needing joins the layer did not model. [blog] https://dbt-labs.github.io/dbt-llm-sl-bench
6. **Scope silently filtering totals.** See A7. [inference]
7. **Unverifiable narratives.** Numbers in prose that no cell backs. [inference]
8. **Benchmark optimism.** Vendor accuracy claims (90%+, 84.5%, two thirds fewer errors) are self-measured and in-sample. [blog]
9. **Time ambiguity.** Posting date vs document date vs fiscal period; time zone of "today". [inference]
10. **Currency and unit mixing.** Sums across currencies or units. The catalog must bind every amount measure to a currency basis and every quantity to a unit basis. [inference]

## A9. Transferable pattern: the model plans, code computes

```
question ──► planner (LLM, read-only tools)
               │  reads the catalog (MCP resources)
               ▼
            QueryPlan (JSON) ──► validator (code) ──► compiler (code) ──► executor
                                   │ refuse / clarify       one SELECT over      read-only role,
                                   ▼                        semantic views       scope, timeouts
                              abstention code                                      │
                                                                                   ▼
answer ◄── renderer (code: numbers, units, locale) ◄── narration template (LLM) ◄── ResultEnvelope
            + plan + query + drill handles + scope note + verified/generated badge
```

### A9.1 Declared measure and dimension layer (the catalog)

Extend the view declarations of ADR-0050 rule 45 with an **analytic declaration** per fact view [inference]:

- **Measures:**
  - `name`, `label`, translated description, synonyms;
  - `expression`: a column plus an aggregation `sum`, `count`, `count_distinct`, `min`, `max`;
  - `additivity`: `additive`, `semi_additive(time: last)` for balances and stock, or `non_additive`;
  - `unit_basis`: company currency, transaction currency with a currency dimension required, inventory unit, or count;
  - `field_class` for cost and margin;
  - `default_filters`, for example posted documents only, reversals netted;
  - `owner`, `status` (draft, certified, deprecated).
- **Derived measures:**
  - `ratio(numerator, denominator)`, computed after aggregation;
  - `difference` and `growth` over a comparison period;
  - `share_of_total`.
- **Dimensions:** a column or a join path, with type and cardinality class (low, high, identifier). Each has synonyms, allowed values for low-cardinality enumerations, hierarchy (year > quarter > month; product line > product > item; region > branch) and translation.
- **Time dimensions:** which date the fact is on (posting date, document date, due date), allowed grains, and the company fiscal calendar.
- **Entities and joins:** declared paths only, with cardinality. The compiler refuses a group-by whose path is one-to-many from the measure's grain (fan-out guard), unless the measure is declared at the child grain.
- **Grain** of each fact view, such as "one row per document line".

Source of figures: measures over `system_account_turnover` must reproduce statutory figures. Add an invariant test: a management total equals the statutory engine's total for the same accounts and period, in the spirit of INV-401.

### A9.2 Query plan (the intermediate form)

Example: *"Top 5 customers by invoiced revenue last quarter vs the quarter before, Hanoi branch."*

```json
{
  "plan_version": 1,
  "view": "sales_line_fact",
  "measures": ["invoiced_revenue"],
  "dimensions": ["customer"],
  "filters": [{"dimension": "branch", "op": "eq", "value": "HN"}],
  "time": {"dimension": "posting_date", "range": {"relative": "last_fiscal_quarter"},
           "compare": {"relative": "previous_period"}},
  "derived": [{"name": "delta", "op": "difference", "of": "invoiced_revenue"}],
  "order": [{"by": "invoiced_revenue", "dir": "desc"}],
  "limit": 5,
  "with_other_row": true,
  "with_total_row": true
}
```

- The plan names only catalog objects. Relative dates are resolved by code against the company calendar and time zone (ADR-0007), and echoed back as absolute dates.
- The plan is the unit for caching, verification badges, saved reports and tests.

### A9.3 Validation against the catalog (deterministic checks)

1. Every name exists, is certified (or the user may see draft) and is allowed by the user's field classes.
2. All measures share the requested dimensions (MetricFlow's common-dimension rule).
3. No fan-out path. No non-additive measure aggregated over time unless declared semi-additive with a rule.
4. Currency and unit consistency: amounts in transaction currency need `currency` as a dimension or a filter.
5. Cardinality guard: grouping by a high-cardinality dimension needs `limit` ≤ N and adds an "other" row.
6. Filter values exist (enum check, partner or item lookup resolved to ids by a lookup tool, not guessed).
7. Cost guard: estimated row and scan size within the run budget; time range within a maximum span.
8. Scope: the plan is compiled with the actor's scope settings (ADR-0050 rule 48). If `is_scope_filtered` is true, that flag is part of the result.

Each failure returns a machine code: `unknown_measure`, `ambiguous_term`, `fan_out_refused`, `currency_mixed`, `out_of_coverage`, `too_broad`. The planner may repair the plan once; otherwise the user gets the code as an abstention (A9.5).

### A9.4 Compilation and execution

- The compiler emits **one `SELECT`** over the semantic views: grouped aggregation, `ROLLUP` or `GROUPING SETS` for total rows, and window functions for share and rank. It keeps ADR-0050 rule 44 (no client SQL, single `SELECT`, bound parameters) and runs under `erpme_readonly` with the same timeouts.
- Expose it as **one registered query**, for example `RunAnalysisPlan(plan)` → `ResultEnvelope`, plus `ExplainAnalysisPlan(plan)` → the compiled SQL text and the resolved absolute dates. The MCP resources gain `erpme://query/measures` and `erpme://query/dimensions`.

### A9.5 Answers that show the query and the drill path, and abstention

The answer always shows:

1. a one-line restatement of what was computed: measure, filters, absolute period, currency;
2. the table or chart;
3. the narration, with numbers substituted from cells;
4. a **"How this was computed"** fold with the plan as readable chips (ThoughtSpot-token style) and the SQL for those allowed to see it;
5. a scope note when filtered;
6. a verified or generated badge;
7. `as_of`.

**Drill path.** Every cell carries a `drill` handle: the same plan plus the cell's dimension values as filters, with dimensions replaced by the next level of the hierarchy. The last level is a `List<View>` of the underlying rows, documents or journal lines. Totals must equal the sum of their drill rows; that is a test.

**Abstention** is a first-class, typed outcome. TrustSQL shows that systems rarely abstain well unless built to. The cases:

- `ambiguous_term`: clarify with 2–4 catalog-based options (Cortex Analyst and Genie behaviour);
- `out_of_coverage`: no measure answers this. Say so, name the nearest measures, and offer to log a catalog request;
- `not_permitted`: a field class or scope is missing. Say what is missing, not the data;
- `data_not_ready`: the period is not closed, or the import is running;
- `too_broad`: ask to narrow.

The model never falls back to free SQL or mental arithmetic. In TrustSQL terms a wrong answer costs more than an abstention, so ERPMe should be tuned for high precision.

### A9.6 Saved analyses, KPIs and evaluation

- **Saved analysis** = a named plan + parameters + presentation hints + owner + status. **KPI** = a saved analysis with a single measure, target and favorable direction. Both are company data, versioned, reviewable, and readable by agents as MCP resources.
- **Verified library** = saved analyses marked verified, each with trigger questions. A planner hit on a verified plan skips generation.
- **Evaluation suite** = question → expected plan (or expected result on fixture data), run in CI on every model, prompt or catalog change, with a regression report (Snowflake evaluations, Genie benchmarks). ADR-0050's shadow evaluation can host it.

## A10. Recommendations (Topic 1)

| # | Recommendation | Phase | Tradeoff |
| --- | --- | --- | --- |
| A-1 | **Add server-side aggregation now.** A declared measure and dimension layer on the existing semantic views plus `RunAnalysisPlan` / `ExplainAnalysisPlan`. Without it, any total over more than 200 rows pushes arithmetic into the model, which violates Principle 13 | **Phase 1** | Adds a compiler (GROUP BY, ROLLUP, hierarchy drill) to build and test. Much smaller than a general semantic layer, because the views already exist |
| A-2 | Start with a small catalog: sales lines (invoiced revenue, quantity, margin with field class), purchase lines, open items (open amount, overdue buckets), stock (on hand semi-additive, value with class), production (output, scrap, variances by type), `system_account_turnover` (turnover, closing balance semi-additive). Fewer than 40 measures | **Phase 1** | Coverage is narrow at first. Questions outside it abstain, which is the intended behaviour |
| A-3 | JSON query plan as the only analysis input, validated by code (A9.3 checks 1–8) with typed refusal codes | **Phase 1** | Less expressive than SQL: no ad hoc joins, window logic limited to declared derived measures. That is the point |
| A-4 | Result envelope + placeholder narration + numeral linter. The model never emits digits | **Phase 1** | Slightly stiffer prose. Some natural phrasing ("doubled") must come from declared comparison ops |
| A-5 | Drill handles on every cell down to `List<View>` rows and, for finance, to `ListReportLineContribution`. Invariant test: a cell equals the sum of its drill rows | **Phase 1** | More test fixtures. Hierarchies must be declared |
| A-6 | Typed abstention with clarification options. Tune for precision | **Phase 1** | Users see "I can't answer that" more often early on. Log those as catalog backlog |
| A-7 | Show the plan as readable chips and the scope note in every answer. SQL visible to roles with a `query_debug` right | **Phase 1** | UI work in the PWA and desktop |
| A-8 | Analytic declaration fields (additivity, unit basis, grain, join cardinality) checked in CI. Invariant: management totals equal statutory totals for the same accounts and period | **Phase 1** | CI effort; prevents silent divergence between management and statutory figures |
| A-9 | Saved analyses and KPIs as versioned company data, readable as MCP resources, with a verified state and trigger questions | Phase 1 (data model and verified badge); **later** (KPI targets, alerts, subscriptions) | Governance UI later. Early on, verification is by the implementation team |
| A-10 | Evaluation suite (question → expected plan) in CI and in the shadow evaluation | **Phase 1** for 50–100 questions per flow; grows later | Needs curated questions per customer domain; synthetic first |
| A-11 | Deterministic variance explanation: additive contributions with a reconciliation row; price-volume-mix for revenue and margin; production variances read from postings | Additive contributions **Phase 1**; PVM and segment search **later** | PVM conventions must be documented and shown. Segment search needs caps to stay fast |
| A-12 | Cost controls: verified-plan and plan-cache hits skip the model; per-company budgets; cheap router model; existing timeouts and `max_rows_read` | **Phase 1** (budgets, cache); later (pre-aggregates) | Cache keys must include the scope fingerprint and `as_of` policy |
| A-13 | Small-cell suppression for personal and `cost` field-class measures in aggregated answers | Later (Phase 1 only if HR analytics is in scope) | Can hide legitimate small numbers; make the threshold a company setting |
| A-14 | Export the catalog as Apache Ossie YAML for outside BI tools | **Later** | Spec still 0.x; low value until customers bring a BI tool |
| A-15 | Do not adopt an external semantic layer product (Cube, dbt SL) inside the core | Decision for Phase 1 | Building in-house costs some weeks. An external engine would duplicate scope, field classes and taint rules that ERPMe already enforces in its own views, and would add a second security model |

---

# Part B: Barcode capability in ERP and warehouse

## B1. GS1 identification keys

### GTIN family

| Key | Digits | Where it appears | Notes |
| --- | --- | --- | --- |
| GTIN-8 | 8 | EAN-8 on very small packs | Allocated one by one by the member organization [doc] |
| GTIN-12 | 12 | UPC-A / UPC-E (North America) | — |
| GTIN-13 | 13 | EAN-13; consumer units worldwide | Starts with the GS1 Company Prefix, for example 893 for prefixes issued by GS1 Vietnam |
| GTIN-14 | 14 | ITF-14, GS1-128 or DataMatrix with AI (01); trade units (cases) | Indicator digit 1–8 for packaging levels, 9 for variable measure; 0 = GTIN-13 padded |

- **Storage rule [doc + inference].** Store every GTIN as a 14-digit string, left-padded with zeros; AI (01) always carries 14 digits. Keep the symbology a scan arrived in as an attribute, not as part of the key.
- **Meaning of the indicator.** The packaging hierarchy is defined in master data, not by the digit alone. Sources disagree on whether the digit "means" a level. [blog] https://support.syncforce.com/knowledge/what-is-a-gtin-14
- **Check digit (mod 10).** From the rightmost data digit leftward, weights 3, 1, 3, 1, … Check = (10 − sum mod 10) mod 10. The same rule covers GTIN-8/12/13/14, SSCC (00), GLN, GRAI and GDTI.
  - Worked examples [inference, computed]: `893123456789` gives check `7` → GTIN-13 `8931234567897`. Padded to 14 digits: `08931234567897`. A case-level GTIN-14 with indicator 1: `1893123456789` gives check `4` → `18931234567894`. The check digit changes when the indicator changes, so it must be recomputed, never copied.

### SSCC (AI 00)

- 18 digits: extension digit (0–9, set by the company), GS1 Company Prefix, serial reference, check digit. Unique worldwide for at least one year from shipment (GS1 rule). Never reuse.
- Example [inference]: extension 3, company prefix 8931234, serial `000000000` → `38931234000000000` + check `5`.
- Sources: [doc] https://www.gs1au.org/standards/id-keys/sscc; [blog] https://www.loftware.com/siteassets/resources/reports/local/en_us/handbook-still-sscc-labeling-logistic-units.pdf

### Other keys useful to an assembly manufacturer [doc + inference]

| AI | Key | Use |
| --- | --- | --- |
| (414) + (254) | GLN of a physical location + an extension component (up to 20 characters) for internal sub-locations such as a shelf unit | **Bins.** The extension is internal only, by mutual agreement. https://support.gs1.org/support/solutions/articles/43000734241, https://www.gs1uk.org/knowledge-hub/standards/what-is-a-gln-extension-component |
| (8004) | GIAI, individual asset | Tools, fixtures, returnable racks |
| (8003) | GRAI | Returnable containers |
| (253) | GDTI | Documents |
| (8006) + (8026) | ITIP | Pieces of a trade item shipped in parts |
| (241) | Customer part number | — |
| (240) | Additional product identification | — |
| (90)–(99) | Company internal information | Can be used freely inside the company |

## B2. GS1-128 and Application Identifiers

### Element strings

- A GS1 barcode carries **element strings**: an AI (2–4 digits) followed by its data.
- **FNC1 in the first position** marks the symbol as GS1. For GS1-128, FNC1 comes right after the start character.
- After a **variable-length** element that is not last, a separator is required: FNC1 in the symbol, transmitted by the scanner as **GS (ASCII 29, 0x1D)**.
- Best practice: put fixed-length elements first and one variable element last, so no separator is needed.
- Source: [doc] https://learn.microsoft.com/en-us/dynamics365/supply-chain/warehousing/gs1-barcodes

### Predefined-length table

The first two digits of the AI determine whether the element has a predefined length. This is what lets a parser split without separators. Total lengths, AI included [doc, GS1 General Specifications ch. 7; verify against the Syntax Dictionary]:

| First two digits | Total length |
| --- | --- |
| 00 | 20 |
| 01, 02, 03 | 16 |
| 04 | 18 |
| 11–19 | 8 |
| 20 | 4 |
| 31–36 | 10 |
| 41 | 16 |

All other AIs are variable length and need a GS unless they come last. A frequent bug: hard-coding "(10) is up to 20" without terminating on GS.

### Core AIs for ERPMe

| AI | Content | Format | Notes |
| --- | --- | --- | --- |
| (00) | SSCC | N18 | Handling unit (pallet, carton) |
| (01) | GTIN | N14 | Trade item |
| (02) | GTIN of contained trade items | N14 | Only on a logistic unit that is not itself a trade item, and only together with (37) and (00) |
| (10) | Batch/lot | X..20 | Variable; needs GS unless last |
| (11) / (13) / (15) / (17) | Production / packaging / best-before / expiry date | N6 YYMMDD | DD = 00 means the end of the month for (15) and (17). The century follows the GS1 sliding window: −49 to +50 years from now |
| (21) | Serial | X..20 | Variable. Serial is unique per GTIN, not globally: GTIN + serial forms the SGTIN |
| (30) | Variable count | N..8 | Variable |
| (37) | Count of trade items in a logistic unit | N..8 | Variable; used with (02) |
| (310n) | Net weight, kg | N6 | n = 0–5 decimals: `3102 001156` = 11.56 kg. Siblings: (311n) length m, (315n) volume l, (320n) weight lb, (330n) gross weight kg for logistic units, (337n) kg per m². [doc] https://gs1uk.org/support-training/help-to-use-and-implement-gs1-standards/barcode-variable-measure-items |
| (400) | Customer purchase order number | X..30 | — |
| (7003) | Expiry date and time | N10 | — |

### Validation rules beyond format

Encode these from the GS1 Barcode Syntax Dictionary, not by hand [doc] https://github.com/gs1/gs1-syntax-dictionary:

- check digits on keys;
- valid calendar dates;
- character set 82 for X fields;
- **requisite pairs**, for example (21) needs (01) or (8006), and (37) needs (02) or (8026);
- **invalid pairs**, for example (01) with (02) in the same string;
- a repeated AI must carry the same value.

## B3. Symbologies and symbology identifiers

| Symbology | Typical use | AIM symbology identifier sent by the scanner |
| --- | --- | --- |
| EAN-13 / UPC-A / EAN-8 | Consumer units, POS | `]E0` (EAN-13/UPC-A), `]E4` (EAN-8) |
| ITF-14 | GTIN-14 printed on corrugated cases | `]I1` |
| **GS1-128** | Logistic labels, SSCC, multi-AI strings | `]C1`. Plain Code 128 is `]C0` |
| GS1 DataBar | Fresh food, coupons | `]e0` |
| **GS1 DataMatrix** | Small parts, healthcare, direct part marking, multi-AI on unit level | `]d2`. Plain DataMatrix is `]d1` |
| **GS1 QR Code** | Element strings in QR | `]Q3`. Plain QR (also used for a GS1 Digital Link URI) is `]Q1` |
| GS1 DotCode | High-speed inkjet | `]J1` |

- The identifier is added by the scanner, not encoded in the symbol. It is the only reliable way to tell GS1 data from a plain Code 128 that happens to start with "01". [doc] https://gs1ca.org/documents/GS1-Canada-GS1-DataMatrix-Fact-Sheet-en.pdf, https://learn.microsoft.com/en-us/dynamics365/supply-chain/warehousing/gs1-barcodes
- D365's mobile app strips AIM prefixes that are not in the GS1 list (from version 2.0.17.0), so non-GS1 codes still work when the scanner adds identifiers to everything. [doc] same page

## B4. GS1 Digital Link

- A **URI form** of GS1 keys: `https://{domain}/01/{gtin14}[/22/{cpv}][/10/{lot}][/21/{serial}][?17=YYMMDD&3103=000500]`.
- The primary key and its qualifiers go in the path, in a fixed order. Data attributes go in the query string. Any domain is allowed, so the brand's own domain works. A resolver redirects to product information. [blog] https://www.unitag.io/blog/gs1-digital-link-vs-qr-code-what-brands-and-printers-need-to-know-before-sunrise-2027/, https://ref-pd.gs1.org/sme-guidance/solution-provider-2d-readiness/
- **Sunrise 2027:** an industry goal for retail POS to accept 2D codes (Digital Link QR or GS1 DataMatrix) by the end of 2027. It is not a law. Expect 1D and 2D side by side for years. [blog] https://www.inflowinventory.com/blog/gs1-sunrise-2027/
- Versions: sources cite URI syntax 1.6.0 (2025) or 1.7.0 (2026). Pin to the version GS1 publishes at build time. [blog]
- **For an ERP [inference].** Treat a scanned Digital Link URI as just another encoding of element strings: parse the path and query into AIs and reuse the same validation. Never fetch the URL while scanning: no network on the hot path, and no following of untrusted links. The GS1 Syntax Engine converts both ways. [doc] https://ref.gs1.org/tools/gs1-barcode-syntax-resource/syntax-engine/

## B5. Parsing rules: a deterministic resolver front end

Recommended order [inference, aligned with D365 and GS1 docs]:

1. **Normalize the transport.** Trim the terminator (CR/LF/Tab). Map the configured GS substitute back to 0x1D. Wedges often cannot send ASCII 29, so the scanner is set to send `~` or another rare character, as in D365's setup. Reject other control characters.
2. **Symbology identifier present?**
   - `]C1`, `]d2`, `]Q3`, `]e0`, `]J1` → GS1 element string.
   - `]Q1` or `]d1` with `http(s)://` → candidate Digital Link.
   - `]E0` or `]E4` → GTIN-13/12/8.
   - `]C0` or `]A0` (Code 39) → internal code.
3. **No identifier** (camera decoders, misconfigured wedges): use heuristics only with guards.
   - A string that starts with the FNC1 the decoder emits, or with a GS, → element string.
   - Pure digits of length 8, 12, 13 or 14 with a valid check digit → GTIN.
   - Starts with `http` and contains `/01/` or `/00/` → Digital Link.
   - Otherwise → internal code.
   - Never parse a string like `01…` as GS1 *only* because it starts with 01. Prefer the registry lookup first (step 6) when no identifier is present.
4. **Element string parse.** Read the AI using the table of valid AIs (the AI length follows from its first digits). Read a fixed length, or up to GS or end. Repeat. Validate with the Syntax Dictionary rules (B2). Unknown AI → a typed error, or skip by policy (D365's "Unknown application identifier policy": *Error* or *Skip*).
5. **Interpret.** Dates → ISO dates (century window, DD=00 → last day). 310n → decimal with unit. (01) → GTIN-14.
6. **Resolve** against ERPMe master data (B8).

**Libraries [doc]:**

- **GS1 Barcode Syntax Engine**: C with bindings for C#, Java, Swift and JavaScript/WebAssembly; Apache-2.0. It is the reference for parsing, validation and Digital Link conversion, and runs in the browser (PWA) and on the server. https://github.com/gs1/gs1-syntax-engine
- Python: `biip` parses GS1 element strings, GTINs and SSCCs [doc] https://biip.readthedocs.io/en/latest/api/sscc/. `python-stdnum` carries a GS1 AI table [doc] https://sources.debian.org/src/python-stdnum/2.2-1/stdnum/gs1_ai.dat.
- Recommendation [inference]: one canonical parser on the server (Python, table generated from the Syntax Dictionary) and the WASM Syntax Engine in the PWA for instant feedback. A shared test corpus, GS1's Syntax Tests plus ERPMe's own, keeps the two in agreement.

## B6. Internal codes (prefix 2 and company-specific)

- **Restricted Circulation Numbers.** GS1 prefixes **02 and 20–29** are for restricted use: inside a company, or by national rules of the member organization, often for in-store variable-measure items such as `2 PPPPP VVVVV C` (price or weight embedded). RCNs may only be carried in EAN/UPC symbols and **must not** be used with AIs. [doc] https://www.gs1.org/docs/barcodes/GSCN-23-006-RCN.pdf, https://www.gs1uk.org/knowledge-hub/barcodes/how-to-barcode-variable-measure-items
- Odoo's default nomenclature has a "weighted barcode" rule `21.....{NNDDD}`: an EAN-13 starting 21 with the weight in the last digits. [doc] https://www.odoo.com/documentation/17.0/applications/inventory_and_mrp/barcode/operations/barcode_nomenclature.html
- **Inside a factory [inference].** Many internal codes print as Code 128: bin codes, work order numbers, internal part numbers, employee badges. Collisions are the risk:
  - a purely numeric internal code of 13 digits that happens to pass the GTIN check;
  - a code starting with "00" or "01" read as GS1.
- Rules:
  1. Internal codes should **start with a letter or a typed prefix** (`B-`, `HU-`, `WO-`) so they can never be read as a GTIN or element string.
  2. Use RCN 20–29 EAN-13 only for variable-measure retail needs, if a customer sells by weight.
  3. A company without a GS1 Company Prefix still works fully on internal codes. GS1 keys are optional attributes, not required identifiers.
  4. AIs (90)–(99) can carry internal data inside a GS1 string, for example an internal item code next to a supplier's (01) on a re-label.

## B7. How ERPs and WMS do it

| System | Parsing model | Multi-field capture | Configuration | Notable limits | Tag |
| --- | --- | --- | --- | --- | --- |
| **SAP EWM** (RF framework) | Barcode type and prefix (table `/SCWM/T313G`, `]C1` default for GS1-128). Decoder `/SCWM/EAN128_DECODE` maps AIs to fields: 10 → batch, 21 → serial, 15/17 → dates | RF screens have **verification fields**. A scan is checked against the expected bin, HU or product (scan-to-confirm). The framework parses input fields before the screen logic runs | Barcode Specification under Mobile Data Entry. Custom barcode types and split function modules via BAdI | `/SCWM/BARCODE` limited to 64 characters (workaround: split). One AI type per barcode specification. Much custom code in practice | [blog] https://community.sap.com/t5/supply-chain-management-blog-posts-by-members/decode-ean-128-barcode-with-more-than-64-char-in-ewm/ba-p/13494759, https://blogs.sap.com/2021/07/12/ean128-gs128-application-identifier-implementation-in-ewm/; [doc] https://learning.sap.com/courses/exploring-business-processes-in-sap-ewm-for-sap-s-4hana-cloud-private-edition/outlining-the-radio-frequency-rf-framework-1 |
| **Dynamics 365 SCM** Warehouse Management mobile app | Scanner in wedge mode adds a prefix (AIM identifier) and maps GS to a printable character (`~`). Server parses. *Enhanced GS1 parser* knows the fixed-length AIs | **Generic setup** maps one AI per field (single-field scan fills the focused field). **Barcode data policies** per menu item push several AIs into flow fields: *Process immediately* or *Save as default* with **Auto submit**, sorting for repeated AIs, allow overwriting | Parameters: FNC1, DataMatrix and QR prefix characters; group separator; unknown-AI policy. AI table (fixed length, length, type, decimal, `310n` pattern). SSCC and BOL number sequences aware of the company prefix length | Field-name mapping to step controls is fragile. Customized policies can break flows | [doc] https://learn.microsoft.com/en-us/dynamics365/supply-chain/warehousing/gs1-barcodes, https://learn.microsoft.com/en-us/dynamics365/supply-chain/warehousing/configure-number-sequence-extensions |
| **Odoo Barcode** | **Nomenclature**: ordered rules (type, regex pattern, GS1 content type, Odoo field, sequence); the first matching rule wins. *Default GS1 Nomenclature* covers 00, 01, 02, 10, 21, 11–17, 30, 37, 310n–365n, 410–414, 91 | Multi-AI strings parsed if every AI has a rule. The Barcode app routes a scan by type: product, lot, package, location, operation | Rules editable in developer mode. Custom rules are read but not mapped to fields without code | Users report that Odoo 18's DataMatrix widget prints plain DataMatrix, not GS1 with FNC1. GTINs are bought from GS1, not generated | [doc] https://www.odoo.com/documentation/17.0/applications/inventory_and_mrp/barcode/operations/gs1_nomenclature.html; [blog] https://www.odoo.com/es/forum/ayuda-1/odoo-18-only-generates-datamatrix-instead-of-gs1-datamatrix-288313 |
| **NetSuite WMS** | "Enable Advanced Barcode Scanning?" system rule with GS1 or composite process types. Item barcode setup | Scanning a GS1 or composite barcode fills lot, serial and quantity. Continuous scanning for serials in receiving and picking | Custom AIs supported, only in custom mobile processes. Scanner must transmit FNC1 | Inbound shipment receiving accepts GS1 but not composite barcodes. Mobile-printed labels do not support custom AIs | [doc] https://docs.oracle.com/en/cloud/saas/netsuite/ns-online-help/section_158264895870.html, https://docs.oracle.com/en/cloud/saas/netsuite/ns-online-help/section_158264983840.html |
| **Business Central** | The mobile app shows a camera scan button on text and code fields. AL-controlled scanning (2024 wave 1) handles dedicated Android scanners through intents and events | Item Reference lookup; Item Tracking Lines with "Scan Multiple" for serials and lots; barcodes on production order prints (2025 wave 1) | Developer page for adding scanning; Android 11+ for dedicated scanners | No documented standard GS1 multi-AI parser in the base product. Warehouse GS1 handling is usually an add-on | [doc] https://learn.microsoft.com/en-us/dynamics365/business-central/dev-itpro/developer/devenv-mobile-app-barcode-scanning, https://learn.microsoft.com/en-us/dynamics365/release-plan/2024wave1/smb/dynamics365-business-central/use-al-controlled-barcode-scanning-all-scenarios-business-central-online; [blog] https://yzhums.com/62497/ |

**Lessons [inference]:**

1. Parsing is **configuration plus a standard table**. Every vendor ships the AI table; ERPMe should generate it from GS1's Syntax Dictionary instead of a hand-made list.
2. Multi-field capture needs a **mapping from AI to the fields of the current step**. D365's per-menu-item policy is the most explicit model. In ERPMe this maps to each scan command's input schema.
3. Every vendor depends on scanner configuration (prefix, GS substitution). ERPMe should ship a scanner profile and a **scan test page**.
4. SAP's verification fields are the canonical **scan-to-confirm** design.

## B8. Scan resolution across item, lot, serial, bin, handling unit and document

### Resolver output

A scan resolves to **typed candidates**, not a single guess [inference]:

```
ScanResolution {
  raw, symbology, encoding: gs1_element | digital_link | gtin | rcn | internal,
  elements: {ai → value}                         // when GS1
  candidates: [ {type: item|item_unit|lot|serial|bin|handling_unit|document|partner|employee,
                 id, confidence: exact|contextual, quantity?, uom?, lot?, serial?, expiry?} ],
  issues: [codes]
}
```

### Resolution order

1. **GS1 keys first.**
   - (00) → handling unit by SSCC.
   - (01) → `item_barcode`, whose (item, unit) gives the packaging level.
   - (01)+(10) → lot of that item.
   - (01)+(21) → serial of that item.
   - (414)+(254) → bin.
   - (253) → document.
   - Unknown GTIN → `unknown_gtin`, with an offer to link it (a supplier's GTIN on a purchased component) through a proposal, never silently.
2. **Registry lookup for everything else.** One **company-wide barcode registry** holds (barcode, type, id). Item-unit, bin, handling-unit, document-print and employee-badge barcodes all register there.
   - Today ADR-0018 and ADR-0023 make barcodes unique *within* each type.
   - **Recommend uniqueness across types**: one index over the registry, so a scan never means a bin *and* an item. Odoo resolves by type order; a cross-type collision there is a configuration error found only at scan time.
3. **Context.** The step's expected type decides between remaining candidates and turns "search" into "confirm" (B12).
4. **Lots and serials without GS1.** A bare lot or serial string is unique only per item.
   - Lot: resolve only with item context (the current task's item, or a previous scan in the step).
   - Serial: if serials are unique per company in practice, resolve directly; otherwise require the item.
   - Make serial uniqueness a product-level setting: per item (the GS1 default) or per company (common in assembly plants that laser-mark their own serials).

### Uniqueness rules [inference + doc]

| Identifier | Uniqueness |
| --- | --- |
| GTIN | Unique per item-unit. A GTIN may map to exactly one (item, unit) per company. Variants have distinct GTINs |
| SSCC | Unique and never reused; generated from a number sequence that knows the prefix length, as D365 does |
| Lot | Per item |
| Serial | Per item (or per company by setting). Never reused even after scrap |
| Bin | Per company |
| Handling unit | Per company. Reusable totes need a lifecycle (empty → reassign), not a new code each time |
| Documents | Type prefix + number, so no collision with items |

## B9. Label printing

**Printer languages:**

- **ZPL** (Zebra and most industrial clones):
  - `^BC` Code 128, with `>8` inserting FNC1 for GS1-128;
  - `^BX` DataMatrix with the `_1` escape for FNC1;
  - GS1 QR needs recent firmware.
  - Sources: [doc] https://supportcommunity.zebra.com/articles/en_US/KM_Solution/Creating-GS1-Barcodes-with-Zebra-Printers-for-Data-Matrix-and-Code-128-using-ZPL, https://docs.zebra.com/us/en/printers/software/zpl-pg/c-zpl-zpl-commands/r-zpl-bc.html
- **EPL** is legacy: Zebra desktop printers, still in the field. Support only through ZPL emulation. [inference]
- **PDF labels** rendered on the server print on any printer, including office lasers on A4 label sheets, and fit ERPMe's existing print/render pipeline (ADR-0049). Thermal printers print PDFs too, but slower and with less exact barcode bars, because of rasterization at 203 or 300 dpi. [inference]

**Recommendation [inference]:**

- Phase 1 renders **PDF** through the existing render jobs, with barcodes drawn as vectors by a library that supports GS1 modes and validates AI data. Candidates: Zint (GS1 mode), BWIPP (via Ghostscript), or `python-barcode` + `pylibdmtx`. Verify GS1 validation support at selection.
- Add **ZPL templates** as a second render target for thermal printers, sent by a local print agent or a network socket (port 9100). ZPL gives exact bar widths and speed.

**Symbology choice [doc + inference]:**

| Object | Symbology | Why |
| --- | --- | --- |
| Bin labels | Code 128 (internal code); optional GS1-128 (414)+(254) | Long-range readable. On high racks, large or retro-reflective labels or floor labels. Every 1D scanner and camera can read it |
| Handling unit / pallet / outbound carton | **GS1-128 with (00) SSCC** on a GS1 logistic label (A6 or 4×6 inch), plus optional (02)+(37)+(10) | Customers' receiving docks expect it. Readable at distance |
| Item, lot or serial on components and finished goods | **GS1 DataMatrix** (01)(10) or (01)(21), optional (11)/(17) | Small footprint. Reed-Solomon error correction tolerates damage. Fits direct part marking. Camera-friendly |
| Consumer unit retail | EAN-13; plus Digital Link QR toward 2027 | POS compatibility |
| Documents (pick list, work order, delivery note) | Code 128 or QR with a type-prefixed number | Scan-to-open on any device |

Print quality matters: quiet zones, X-dimension within GS1 ranges, grade per ISO/IEC 15416 (1D) and 15415 (2D). Thermal transfer for durable labels, direct thermal for short-lived ones. [blog] https://racklify.com/encyclopedia/implementing-data-matrix-ecc-200-in-warehousing-and-logistics/

Code 128 vs DataMatrix in short [blog + inference]:

- Code 128 grows wider with data and fails on damage, because it has only a check character.
- DataMatrix is compact and survives up to about 30% damage, but needs a 2D imager (or a camera).
- Most rugged scanners sold today are 2D imagers, so DataMatrix is no longer a hardware burden.
- Linear-only laser scanners still exist in old fleets. Check before choosing DataMatrix-only labels.

## B10. Mobile scanning UX: camera vs rugged scanner

### Camera in the PWA (BarcodeDetector)

- Supported in Chromium on Android, macOS and ChromeOS. **Not on desktop Linux. Not in iOS Safari**: disabled by default through at least Safari 27.2. [doc] https://caniuse.com/mdn-api_barcodedetector, https://orbisk.github.io/vue-use-barcode-detection/compatibility
- Formats depend on the platform. Call `BarcodeDetector.getSupportedFormats()` at startup and fall back to a WASM decoder (ZXing-cpp based) when `data_matrix` or `qr_code` is missing. Requires HTTPS. [doc] https://developer.mozilla.org/en-US/docs/Web/API/BarcodeDetector; [blog] https://eringen.substack.com/p/barcode-scanning-on-ios-the-missing
- **Symbology identifiers and FNC1 [inference].** BarcodeDetector returns `rawValue` and `format` but no AIM identifier, and it is not specified how FNC1 or GS appear. The PWA must therefore:
  1. use `format` (`data_matrix`, `qr_code`, `code_128`) as a stand-in for the identifier;
  2. treat a leading FNC1 or 0x1D, or embedded GS characters, as GS1 markers;
  3. test each target device with a GS1 test sheet.

  A WASM decoder that reports the symbology identifier removes the ambiguity, which argues for shipping one even on Android.
- **Camera UX [inference]:**
  - a viewfinder with a target box and torch toggle;
  - continuous decode with de-duplication of the same value within about 1.5 seconds;
  - haptic and sound on success, a distinct error tone;
  - the option to tap one of several codes in view (a label with many barcodes);
  - **never auto-submit when several codes are visible** unless only one matches the expected type.
- Camera is fine for low volume: receiving a few lines, a cycle count, a supervisor. It is slow and tiring for high-volume picking.

### Rugged scanners (Zebra, Honeywell, Datalogic) as keyboard wedge

- **Main pitfalls:**
  - ASCII 29 (GS) does not survive keystroke output into browsers. Zebra DataWedge notes that web pages read control characters through the DOM, not as Android key presses. Fix: Advanced Data Formatting replaces GS with a printable character and adds the AIM prefix, or use the **Intent output** with a small bridge.
  - Typing speed: use the inter-character delay setting.
  - The keyboard layout of the device.
  - Sources: [doc] https://techdocs.zebra.com/datawedge/latest/guide/output/keystroke/, https://learn.microsoft.com/en-us/dynamics365/supply-chain/warehousing/gs1-barcodes
- **Capturing wedge input in a web page [blog + inference]:**
  - keep one hidden focused input on scan screens;
  - detect a scan by prefix and suffix and timing (a human cannot type 15 characters in 50 ms);
  - suffix Enter ends the scan;
  - keep the soft keyboard hidden (`inputmode="none"`) on scan fields.
  - Source: [blog] https://www.npmjs.com/package/onscan.js
- **Ship a scanner profile** per supported family (DataWedge profile export, Honeywell settings barcode) that sets the AIM prefix on, GS → `~` (configurable, as D365), suffix Enter and symbologies on: Code 128, GS1-128, DataMatrix, QR, EAN/UPC, ITF. Add a **scanner check page** in the PWA that shows the raw codes received for a GS1 test label. [inference]

### General scan UX [inference]

- One screen asks for **one thing**, and it is in large type: "Scan bin A-03-02".
- Show what was resolved: item name and image, lot, expiry, quantity.
- A wrong scan is a clear stop with a reason (`expected bin A-03-02, scanned A-03-04`), never a silent replacement. An override is a separate action with a reason code; ADR-0023 rule 12 already allows a different target.
- Quantity: default from the barcode (310n, (30), (37)) or the packaging unit (carton barcode = 1 carton), then editable. Never default to the task quantity for serial items.
- Undo the last scan within the task before confirmation.
- Big tap targets, gloves, sunlight-readable contrast, landscape and portrait.

## B11. Offline

ADR-0023 defers offline scanning past Phase 1. When it comes [blog + inference]:

- **Queue commands, not state.** Each scan is already an idempotent command with a device key (ADR-0008), so a replayed queue is safe. Store the queue in IndexedDB; mark items pending until the server acknowledges. [blog] https://www.techinterview.org/post/3233470567/lld-offline-first/, https://dev.to/salazarismo/the-hidden-problems-of-offline-first-sync-idempotency-retry-storms-and-dead-letters-1no8
- **Validate locally against a task snapshot.** Download the claimed tasks with expected bins, items, lots and allowed serials, plus the barcode registry subset for that warehouse, so scan-to-confirm works offline. Parsing (WASM Syntax Engine) is local anyway.
- **Server stays the authority.** Replays that conflict (stock already moved, serial already used) come back with a typed reason and land in an exception list for the worker or supervisor. No client-side merge for stock.
- **Limits:**
  - time-box the offline window, for example 4 hours;
  - no offline for steps that post value or finish a shipment;
  - iOS lacks Background Sync, so replay when the app opens;
  - show the queue depth on screen.
- **Phase 1 alternative.** Reliable Wi-Fi coverage plus a quick retry; paper lists from step 5 as the fallback (ADR-0023 rule 22).

## B12. Scan-to-confirm vs scan-to-search

| Mode | Meaning | Where | Resolution |
| --- | --- | --- | --- |
| **Scan-to-confirm** (SAP verification fields) | The system already knows what should be scanned. The scan proves physical presence | Every task step: source bin, HU, item, lot or serial, target bin | Compare against expected values. On mismatch, stop with a reason; override is an explicit alternate action |
| **Scan-to-search** | The user scans to find or open something | Home screen, ad hoc stock inquiry, "what is this?", receiving without a task | Global resolver (B8) returns typed candidates. One exact candidate opens it; several give a chooser; zero offer "unknown barcode" |

Rule [inference]: **posting-relevant steps are always scan-to-confirm.** Search may only *open* things, never post. That also keeps agent and AI features out of the scan path: scans are deterministic commands.

## B13. Serial capture

- **Formats.** (21) X..20, character set 82. Serial uniqueness is per GTIN by GS1. For laser-marked serials on assemblies, a DataMatrix (01)(21) per unit is the norm. [doc] https://www.gs1.org/docs/barcodes/GS1_General_Specifications.pdf
- **Capture patterns [inference]:**
  1. **One scan per unit** with a running count "7 of 20" and duplicate detection within the session (`serial_already_scanned`).
  2. **Scan the container.** When serials were recorded at packing, scanning the HU's SSCC confirms all its serials at once. This is the main time-saver for outbound.
  3. **Range entry** for consecutive serials, with a supervisor right.
  4. **Receipt of supplier-serialized parts.** Parse (01)(21) from the supplier's label; map their GTIN to the item through `item_barcode` or a supplier GTIN link.
- **Production [inference].** Assembly manufacturers usually assign serials at final assembly or at a station. Generating serials from a number sequence, printing a DataMatrix label at the station and scanning it at confirmation closes the loop (ADR-0034). Component serials scanned into the parent serial build a genealogy, which is valuable for warranty and recall.
- **Checks already in ERPMe:** `serial_not_in_bin` at confirmation (ADR-0023). Add `serial_wrong_item`, `serial_status_blocked` and `serial_reused`.

## B14. Vietnamese context

- **Prefix 893.** Assigned by GS1 to GS1 Vietnam, which works under the national standards, metrology and quality authority of the Ministry of Science and Technology. A company prefix is 893 plus an enterprise number (4–7 digits under the 2006 rules). [doc] https://hethongphapluat.com/decision-no-15-2006-qd-bkhcn-of-the-ministry-of-science-and-technology-promulgating-the-regulation-on-allocation-use-and-management-of-article-numbers-and-barcodes.html, https://vietnamnet.vn/en/vietnam-promotes-adoption-of-gs1-standards-2568839.html
- **893 shows who allocated the prefix, not where the goods were made.** Customs reporting confirms that a Vietnamese code on imported goods does not by itself mean fake origin. [blog] https://english.haiquanonline.com.vn/imported-goods-with-vietnamese-code-not-grounds-to-conclude-fake-origin-13890.html. ERPMe must never infer country of origin from a GTIN prefix. [inference]
- **Duties of prefix holders.** After allocation, users declare and update product information in the national database (Circular 10/2020/TT-BKHCN). [doc] https://english.luatvietnam.vn/circular-no-10-2020-tt-bkhcn-detailing-and-providing-measures-to-implement-a-numb-199216-doc1.html
- **Decree 37/2026/NĐ-CP** (effective 23 Jan 2026; guides the Law on Product and Goods Quality; replaces Decree 132/2008) [blog, from legal portals; verify against the official gazette]:
  - defines a **traceability code** built from product trace code, location trace code and lot or serial;
  - confirms 893 as the national prefix;
  - encourages 1D and 2D codes, including QR;
  - introduces a **digital product passport** and electronic labels;
  - makes traceability mandatory for high-risk goods on a list to be published.
  - Sources: https://hethongphapluat.com/nghi-dinh-37-2026-nd-cp-huong-dan-luat-chat-luong-san-pham-hang-hoa/dieu-3/khoan-29, https://luatvietan.vn/diem-moi-nghi-dinh-37-2026-nd-cp-huong-dan-luat-chat-luong-san-pham-hang-hoa.html
- **National standards:** TCVN 6939:2019 (GTIN-13) and TCVN 7825:2019 (= ISO/IEC 15420, EAN/UPC). [doc] https://thuvienphapluat.vn/TCVN/Linh-vuc-khac/TCVN-6939-2019-Ma-so-vat-pham-Ma-so-thuong-pham-toan-cau-13-chu-so-918518.aspx, https://lawnet.vn/en/laws/what-is-vietnam-standard-tcvn-7825-2019-iso-iec-15420-2009-on-information-technology-automatic-iden-150086.html
- **Design consequences [inference]:**
  1. Under the overlay rule, Vietnam-specific traceability-code and digital-passport output belongs in `l10n_vn`. The core supplies GS1 keys, lots, serials, genealogy and Digital Link generation as generic capabilities.
  2. Barcode **data** stays ASCII. Code 128 cannot carry Vietnamese diacritics, and GS1 character set 82 excludes them. Lot codes and internal codes must not contain diacritics; validate at creation. The human-readable text on labels can be Vietnamese, but needs a PDF font with full Vietnamese glyphs and, for ZPL, a downloaded Unicode TrueType font.
  3. Many SME manufacturers have **no GS1 prefix** and label with internal codes. The design must work without one; GS1 features switch on when the company enters its prefix.
  4. Exporters to retailers abroad need GTIN-13/14 and SSCC labels. Electronics and automotive supply chains often prescribe customer-specific labels; ship a template per customer.

## B15. Pitfalls (Topic 2)

1. **GS lost in keyboard wedge**, so (10) swallows the following AI. Fix by GS substitution and AIM prefixes, plus a parse rule that rejects lots containing AI-like tails ending in a fixed-length key with a valid check digit. [doc] D365 page; [inference]
2. **Parsing non-GS1 Code 128 as GS1** because it starts with digits. Fix by symbology identifier or registry lookup first. [inference]
3. **Parentheses in data.** Human-readable `(01)` pasted into the symbol data, or a label template that encodes the parentheses. Odoo notes punctuation must be omitted. [doc] Odoo GS1 page
4. **Plain DataMatrix printed instead of GS1 DataMatrix** (no FNC1); scanners report `]d1`. Odoo users hit this. [blog]
5. **Century and DD=00 in dates. Decimal position in 310n.** [doc] D365 page
6. **Fixed-length flag set on variable AIs** in configuration, as D365 warns. Generate the table; do not hand-edit it. [doc]
7. **Cross-type barcode collisions** (bin code = item code). Today's per-type uniqueness allows them. [inference]
8. **Lot-only scans** resolving to the wrong item's lot. Require item context. [inference]
9. **BarcodeDetector gaps on iOS and Linux.** Format support varies by device. No symbology identifier. [doc]
10. **SAP-style length limits** on barcode fields. GS1 strings can exceed 64 characters; size fields for at least 150 and DataMatrix payloads. [blog]
11. **Reusing SSCCs or serials** after cancellation. [doc + inference]
12. **Printing bars from rasterized PDFs on 203 dpi printers.** Bar width rounding fails verification. Use ZPL native barcodes, or choose module sizes that are whole multiples of the printer dot. [inference]

## B16. Recommendations (Topic 2)

| # | Recommendation | Phase | Tradeoff |
| --- | --- | --- | --- |
| B-1 | **One canonical GS1 parser** on the server: AI table generated from the GS1 Barcode Syntax Dictionary, with check digits, dates, character set 82 and requisite or invalid pairs. Accepts element strings and Digital Link URIs. Shared test corpus with GS1 Syntax Tests | **Phase 1** (step 5, before the PWA, because desktop scanning and receiving need it) | A pinned Dictionary version needs an update job once or twice a year |
| B-2 | **Company-wide barcode registry** across types (item-unit, bin, HU, document print, employee badge) with one uniqueness index, replacing per-type uniqueness. Resolver returns typed candidates | **Phase 1** | A migration of ADR-0018/0023 rules. Small cost now, large later |
| B-3 | **Resolver order:** symbology identifier → GS1 keys → registry → context. Ambiguous or unknown → typed issue, never a guess. Unknown supplier GTIN → proposal to link | **Phase 1** | Needs scanners configured to send identifiers; heuristics only as a guarded fallback |
| B-4 | **Scan-to-confirm on every posting-relevant step**, with mismatch stop and explicit override with reason. Scan-to-search only opens records | **Phase 1** | Slightly more scans per task; much higher accuracy |
| B-5 | **GS1 multi-field capture on receipt and pick:** each scan command's input schema maps AIs to fields ((01) item and unit, (10) lot, (17) expiry, (21) serial, (30)/(37) quantity, (310n) weight). This is D365's policy idea expressed in the command registry instead of per-menu configuration | **Phase 1** for receipt (supplier labels on components); pick and pack at step 9 with the PWA | Requires lot master data to accept expiry from scans; conflicts with existing lot data stop with a reason |
| B-6 | **Internal code format** rule: internal barcodes start with a letter and a type prefix (`B-`, `HU-`, `WO-`, `D-`) and are ASCII only (no diacritics), validated at creation | **Phase 1** | Customers migrating legacy numeric codes need a mapping, or keep them with collision checks |
| B-7 | **GS1 optional per company:** if a GS1 Company Prefix is entered, generate GTIN check digits, SSCC sequences (extension digit + prefix + serial, prefix-length aware) and GS1 labels; otherwise internal codes only | GTIN storage and validation **Phase 1**; SSCC generation **Phase 1 if a customer ships to retailers**, else later with carrier integration (ADR-0023) | SSCC never-reuse needs a durable sequence and a void log |
| B-8 | **Labels as print subjects** (ADR-0049) rendered to **PDF** with vector barcodes (library with GS1 mode); templates: bin (Code 128), HU (GS1-128 SSCC, or Code 128 internal), item/lot/serial (GS1 DataMatrix), document (Code 128) | **Phase 1** (step 5) | PDF on thermal printers is slower; acceptable for step 5 volumes |
| B-9 | **ZPL templates** and a local print agent or socket printing for thermal printers | **Later** (with the PWA at step 9 or after) | Two template languages to maintain; justified by speed and print quality at volume |
| B-10 | **PWA scanning:** BarcodeDetector where formats are supported, WASM fallback (also for iOS); wedge capture with prefix, suffix and timing; scanner profiles (AIM prefix on, GS→`~`, Enter suffix); scanner check page | **Phase 1 step 9** (PWA step) | Device testing matrix; recommend a short list of supported rugged devices |
| B-11 | **Serial capture:** per-unit scan with running count and duplicate check; HU scan confirms packed serials; range entry with a right; serial uniqueness setting per product (per item vs per company); station label printing for produced serials | Per-unit and HU **Phase 1**; range entry and station printing **Phase 1 if the production pilot serializes**, else later | Genealogy (component serial into parent serial) adds data volume; high value for warranty |
| B-12 | **GS1 location keys** (414)+(254) for bins as an optional encoding; GIAI (8004) for tools and fixtures; GDTI (253) for documents | **Later** | Little benefit inside one company; useful when partners scan your locations or assets |
| B-13 | **Digital Link generation** for consumer units and Decree 37/2026 traceability or digital-passport output in `l10n_vn` | **Later** (watch the list of mandatory goods; Sunrise 2027 for retail customers) | Needs a resolver endpoint or a third-party resolver; legal details may still move |
| B-14 | **Offline scanning:** IndexedDB queue of idempotent commands, local validation against claimed-task snapshots and a registry subset, server-authoritative conflicts into an exception list, time-boxed | **Later** (per ADR-0023) | Cache invalidation and exception handling; worth it only where Wi-Fi is poor |
| B-15 | **Field sizes:** barcode fields at least 150 characters for raw scans (stored in the scan command for audit), 20 for lots and serials per GS1, GTIN stored as 14 digits | **Phase 1** | None worth noting |

---

# Part C: Where the two topics meet

1. **Determinism on both sides [inference].** Analysis plans and scan commands are both structured inputs that code validates and executes. The LLM plans a query; it never computes. A scanner (or a camera decoder) produces a string; code parses and resolves it. Neither path lets the model invent a value.
2. **Agents and scans [inference].** Agents may *read* scan history and warehouse task views (`warehouse_task_overview`, `count_accuracy`) through the measure layer, for questions like "scan error rate by bin zone this week" or "most overridden pick locations". Agents never submit scans.
3. **Shared registry as an MCP resource [inference].** The barcode registry is a natural lookup tool for agents: "what is HU-000123?" resolves through the same deterministic resolver, read-only.

# Sources by category (main)

- Benchmarks and papers:
  - BIRD (via) https://aiweekly.co/alerts/googles-gemini-sql2-tops-bird-text-to-sql-at-8004
  - Spider 2.0 https://spider2-sql.github.io/, https://www.alphaxiv.org/abs/2411.07763v2
  - BEAVER https://arxiv.org/pdf/2409.02038
  - TrustSQL https://arxiv.org/abs/2403.15879v4
  - Ambiguity taxonomy https://arxiv.org/html/2501.18197v1
  - Semantic-layer-mediated agent https://arxiv.org/pdf/2606.31041
  - Semantic layers paired benchmark https://www.alphaxiv.org/abs/2604.25149
- Semantic layers:
  - dbt https://docs.getdbt.com/docs/build/saved-queries, https://dbt-labs.github.io/dbt-llm-sl-bench
  - Cube https://cube.dev/docs/product/apis-integrations/ai-api
  - Looker https://docs.cloud.google.com/looker/docs/conversational-analytics-looker-best-practices
  - Malloy https://docs.malloydata.dev/documentation/user_guides/publishing/mcp_agents
  - AtScale https://www.atscale.com/?p=24087
  - Apache Ossie https://atlan.com/know/ai-agent/semantic-layer/what-is-open-semantic-interchange/
- Products:
  - Genie https://learn.microsoft.com/da-dk/azure/databricks/genie/trusted-assets, https://docs.databricks.com/aws/en/genie/monitor
  - Cortex Analyst https://docs.snowflake.com/user-guide/snowflake-cortex/cortex-analyst/verified-query-repository, https://docs.snowflake.com/user-guide/snowflake-cortex/cortex-analyst-evaluations
  - Top Insights https://docs.snowflake.com/en/user-guide/ml-functions/top-insights
  - Power BI https://learn.microsoft.com/power-bi/create-reports/copilot-prepare-data-ai, https://learn.microsoft.com/fabric/fundamentals/copilot-fabric-consumption
  - Tableau Pulse https://help.tableau.com/current/online/en-us/pulse_insights_platform_insight_types.htm
  - Spotter https://www.thoughtspot.com/trust/agentic-analytics
  - Joule https://www.sap.com/products/technology-platform/joule-analytical-insights-feature.html
  - Oracle FDI https://blogs.oracle.com/analytics/fusion-data-intelligencefdi-integrated-mcp-server
- GS1:
  - Syntax resource https://github.com/gs1/gs1-syntax-dictionary, https://github.com/gs1/gs1-syntax-engine
  - RCN https://www.gs1.org/docs/barcodes/GSCN-23-006-RCN.pdf
  - GLN extension https://www.gs1uk.org/knowledge-hub/standards/what-is-a-gln-extension-component
  - SSCC https://www.gs1au.org/standards/id-keys/sscc
  - Variable measure https://gs1uk.org/support-training/help-to-use-and-implement-gs1-standards/barcode-variable-measure-items
  - DataMatrix https://gs1ca.org/documents/GS1-Canada-GS1-DataMatrix-Fact-Sheet-en.pdf
- ERP/WMS:
  - D365 https://learn.microsoft.com/en-us/dynamics365/supply-chain/warehousing/gs1-barcodes
  - Odoo https://www.odoo.com/documentation/17.0/applications/inventory_and_mrp/barcode/operations/gs1_nomenclature.html
  - NetSuite https://docs.oracle.com/en/cloud/saas/netsuite/ns-online-help/section_158264895870.html
  - Business Central https://learn.microsoft.com/en-us/dynamics365/business-central/dev-itpro/developer/devenv-mobile-app-barcode-scanning
  - SAP EWM (community) https://blogs.sap.com/2021/07/12/ean128-gs128-application-identifier-implementation-in-ewm/
- Devices and printing:
  - BarcodeDetector https://developer.mozilla.org/en-US/docs/Web/API/BarcodeDetector, https://caniuse.com/mdn-api_barcodedetector
  - DataWedge https://techdocs.zebra.com/datawedge/latest/guide/output/keystroke/
  - ZPL GS1 https://supportcommunity.zebra.com/articles/en_US/KM_Solution/Creating-GS1-Barcodes-with-Zebra-Printers-for-Data-Matrix-and-Code-128-using-ZPL
- Vietnam:
  - Decree 37/2026 https://hethongphapluat.com/nghi-dinh-37-2026-nd-cp-huong-dan-luat-chat-luong-san-pham-hang-hoa/dieu-3/khoan-29
  - Circular 10/2020 https://english.luatvietnam.vn/circular-no-10-2020-tt-bkhcn-detailing-and-providing-measures-to-implement-a-numb-199216-doc1.html
  - TCVN 6939:2019 https://thuvienphapluat.vn/TCVN/Linh-vuc-khac/TCVN-6939-2019-Ma-so-vat-pham-Ma-so-thuong-pham-toan-cau-13-chu-so-918518.aspx

**Open verification items:**

- The exact predefined-length table, and the requisite and invalid AI pairs, against the current GS1 Syntax Dictionary.
- Decree 37/2026 text against the official gazette.
- BarcodeDetector GS1 FNC1 output on the target Android devices.
- GS1 validation support in the chosen PDF barcode library.
- The BIRD and Spider leaderboard figures, which move monthly.
