Module: query    Chunk: 1 of 4    Source ADRs: ADR-0029, ADR-0050
Build step(s): 4    Generated from index: 30d5706    Compiled by: Claude Fable 5.2, 2026-11-21

# Compiled spec: `query`, chunk 1

## Purpose

`query` is the read-only layer of the system and sits in layer 5 (ADR-0022.R2). It owns schema `query`: the semantic
views, their declarations, the query builder, the `List<View>` and `Get<View>` queries and list export, and the analysis
layer. This chunk states the module split of ADR-0050, run taint and untrusted fields, the tainted read scope, and the
view layer: placement, roles, the builder, declarations, exposure, filters, field classes, record scope, the views and
management reporting. The analysis layer (ADR-0060) is in chunks 2 to 4. Computed figures (prices, exposure,
availability) stay with the modules that compute them; `query` never re-implements them.

## Entities and tables

The rules of this chunk define no owned table. The owned tables `analysis_question`, `saved_analysis`,
`saved_analysis_version` and `analysis_example` (DDL: `docs/design/DS-33-analysis.sql`) have their rows in the chunks
whose rules define them. The views of schema `query` are not tables; R35 to R43 list them.

Reads: `agent_run` (`tainted_at`), `agent_run_step`, `partner`, `partner_item`, `supplier_item`, `demand_supply_line`, `account_period_balance`, `assist_request`, `audit_record`, `audit_change`, `audit_denial`, `policy_decision`, `personal_data_processing_log`, and the base tables behind each view.

## Commands and queries

| Name | Actor and authorization | Input | Effect | Events | Error codes |
| --- | --- | --- | --- | --- | --- |
| `List<View>` (one per view, for example `ListPartnerOverview`, `ListSystemAccountTurnover`) | A person or an agent run; the query's own permission, verb `List` at level read (`authorization-verb-levels.csv`); record scope, owner scope and field classes of the actor (R28 to R31); area not stated | Filters, sort, `limit`, cursor, `include_untrusted` (R16, R26, R27) | Returns one page of the view's rows, with `is_scope_filtered` and, for a clean agent run, `is_taint_filtered` (R17, R30) | None (read only) | `tainted_read_out_of_scope`, `untrusted_read_not_allowed`, `held_out_filter_unavailable` |
| `Get<View>` (where the view is keyed) | As `List<View>` | The key the declaration names (R23) | Returns one row | None (read only) | `tainted_read_out_of_scope`, `untrusted_read_not_allowed` |

The list export command `CreateListExport` (ADR-0050.R54) has its row in chunk 2; the analysis queries and commands have theirs in chunks 3 and 4.

Not commands: the MCP resources `nativeflows://query/views`, `nativeflows://query/views/<name>`,
`nativeflows://query/measures`, `nativeflows://query/measures/<code>`, `nativeflows://query/dimensions` and
`nativeflows://query/dimensions/<code>` (R25); the SQL function `query.has_field_class` (R29).

The computed module queries of R44 and R45 are registered by their own modules, not by `query`. The catalog area
`reports` (`authorization-areas.csv`, no module) holds the report queries that total over documents and are registered
`is_owner_scoped: false` (R39).

## Rules

### Modules and imports

R1. ADR-0050 is carried by the modules `agent_runs` (layer 2), `agents` (layer 5) and `query` (layer 5) (ADR-0022.R2; ADR-0027.R1). `query` owns schema `query`: the views, their declarations, the query builder, the `List<View>` and `Get<View>` queries and list export. It also owns the analysis catalog, validator, compiler and executor, the analysis queries and the tables of `DS-33-analysis.sql`.
Source: ADR-0050.R1, ADR-0050.R1.N2

R2. `agent_runs` owns the tables `agent_type`, `agent_type_version`, `agent_type_setting`, `agent_run`, `agent_run_step`, `agent_budget_usage`, `agent_promotion_evidence` and `data_processing_permission` with its contract function, and the contract functions `create_run`, `complete_run`, `cancel_run`, `write_agent_type_setting`, `write_promotion_evidence`, `mark_run_tainted`, `reserve_budget`, `settle_budget`, `record_run_step` and `get_run_context`, which the layer-5 handlers of `agents` call. Layer 2 stays tables and contracts: `agent_runs` holds nothing else. Resolvers, comparators and evaluations read layer 3 to 5 data, so they live in `agents`, and the bank auto-post evidence lives in `cash` (ADR-0051.R18).
Source: ADR-0050.R1, ADR-0050.R1.N1

R3. `agents` owns the gateway and its adapters, the runtime, the workflows of ADR-0051 and the `analysis` workflow, prompt templates, output schemas, tool definition generation and the replay adapter; the commands `StartAgentRun`, `CompleteAgentRun`, `CancelAgentRun`, `UpdateAgentTypeSetting`, `SetDataProcessingPermission` and `EndDataProcessingPermission`; the scope resolvers, `GetAgentShadowEvaluation` with the workflow comparators, and `RunAgentQualityCheck`; and the agent types `document_reader` and `product_engineering` (ADR-0057.R1, ADR-0057.R11, ADR-0057.R20; ADR-0062). There is no agent framework (ADR-0002): workflows are plain code that calls the gateway and the dispatcher.
Source: ADR-0050.R1, ADR-0050.R1.N1, ADR-0050.R1.N2

R4. Imports:
- `query` imports `db`, `registry`, `agent_runs` (for taint) and the `work` contract, the last to raise its work item kinds.
- `agents` imports `registry` (dispatch) and the `agent_runs` and `work` contracts. Its command handlers (scope resolvers, shadow comparators) may also import the contracts of the modules of layers 3 and 4 whose subjects its agent types declare (`crm`, `purchasing`, `cash`, `planning`, `sales`, `master_data`).
- Workflows reach data only through registered queries and commands. Nothing in `agents` imports `query` or `imports`, its layer-5 peers; the `analysis` workflow reaches `query` only through the dispatcher.
- `registry` imports the `agent_runs` contract for credentials, tool lists and taint. `agent_runs` imports `work` only.
Source: ADR-0050.R1, ADR-0050.R1.N2

### Run taint

R5. `is_untrusted` is a schema attribute separate from data labels (spec 17). It is set on fields filled from outside content: e-mail bodies, supplier e-invoice free text, bank statement texts and `interaction_summary` (ADR-0019.R20).
Source: ADR-0029.R10

R6. A run becomes tainted when the query layer (DS-33) returns to it any of: an `is_untrusted` field; a row of an effectively tainted version; a work item created from a tainted event; an attachment from outside content. The dispatcher applies run taint to every query result returned to a run, and commits `agent_run.tainted_at` before it returns the data (ADR-0050.R25). Work items carry `is_tainted` as an OR over their raises (ADR-0042.R5).
Source: ADR-0029.R10, ADR-0029.R10.N1

R7. Master data changed by an approved proposal is not tainted, because the human approval is the trust boundary. DS-33 views leave `is_untrusted` fields out unless they are asked for, so listing documents does not taint a run.
Source: ADR-0029.R10

R8. Value trust (a reading of spec 03 rule 1, interim until the author answers; ADR-0057.R17):
- An extraction field's normalized value is not untrusted when it fits its type's closed shape and passed every rule of the extraction's latest rule run from a deterministic reader, or when a person confirmed it and its shape passed.
- Its raw text and evidence are always untrusted.
- Untrusted too: free text, URLs, e-mails, phones, codes and units that resolve to no record, vision values before confirmation, and every field of an extraction with a failed or mismatched signature or with suspected hidden text.
- Trust is computed when the field is read, never stored on it. It means that the value carries no instruction, not that it is true.
Source: ADR-0029.R10, ADR-0029.R10.N2

### Tainted read scope

R9. The tainted read scope is the literal spec 03 rule 1 (ADR-0029.R14). A tainted run reads only:
- item 1, rows in its scope: rows whose partner column equals `scope_partner_id` (scope `partner`), rows of `scope_import_batch_id` (scope `import_batch`), or the run's subject row (scope `subject`);
- item 2, its work item, the item's evidence links and its notes, never the work case the item belongs to (`GetWorkCase` and `ListWorkCaseTimeline` are on no agent tool list in Phase 1, ADR-0066.R19);
- item 3, documents and change proposals that it or an earlier run of the same work item and agent type wrote, with their plans and check results;
- item 4, reference data (R11).
Source: ADR-0050.R27, ADR-0050.R27.N2

R10. For the `assistant`, scope kind `subject` covers the run's `assist_request`, its context subject row (`context_subject_table`, `context_subject_id`) and the rows of `selected_table` named in `selected_ids`, each only where the requesting user's record scope allows it. These are the records the run was started on (spec 03 rule 1). The same scope applies to an `ask` or resolve run once it becomes tainted. The runtime's provenance check and the dispatcher's reference check of ADR-0050.R25 accept these rows as in scope.
Source: ADR-0050.R27, ADR-0050.R27.N3

R11. Reference data, item 4 of the tainted read scope, is: the core catalogs (system accounts, transaction keys, movement types, work item kinds, currencies, units), the active package's data (chart template, administrative units, settings), and registry metadata (schemas, view declarations). While `agents.tainted_reference_reads` reads `declared_projections`, the default, item 4 also covers declared projections: `tainted_projection` on a query's result model, closed shapes and internal names only, at most 20 rows per call and 10 calls per run; the run stays tainted (ADR-0063.R16).
Source: ADR-0050.R27, ADR-0050.R27.N1, ADR-0050.R27.N5

R12. Every other read of a tainted run returns `tainted_read_out_of_scope`, with a denial record. Company master data outside the scope (other partners, the item catalog, price lists, the company's chart) is not reference data. The scope is not widened: spec 03 rule 1 names this scope and changes nothing in it, and the whole item catalog, the partner's price lists and available to promise are not readable by a tainted run. A workflow that needs one more read for a tainted run (for example item candidates for matching) gets it only as a declared projection of a registered query (`tainted_projection`: closed shapes, internal names, row and call limits; ADR-0063.R16), added by an ADR note for that workflow.
Source: ADR-0050.R27, ADR-0050.R27.N4, ADR-0050.R27.N5

R13. Every view and every query result model declares its partner column and import batch column, or none. A query without the run's scope column is refused for a tainted run.
Source: ADR-0050.R27

R14. In responses of commands to a tainted run, check details and plan parts that name records outside the scope are replaced by `{"redacted": true}` with counts (`partner_duplicate_suspected` gives `{"redacted": true, "candidate_count": 2}`). The plan hash is still computed over the full plan (ADR-0008.R12). The same scope bounds what a tainted run may put into a prompt or a command (ADR-0050.R25), so rows read before the taint cannot be used after it.
Source: ADR-0050.R27

R15. Scope kind `subject`, items 2, 3 and 4 of the tainted read scope, and the data migration agent's reading of its migration's mapping profile (ADR-0051.R26) are readings of the literal rule by ADR-0050, and they stand as written. Through item 3 a tainted run also sees the server-computed prices and taxes in its own draft's plan.
Source: ADR-0050.R27, ADR-0050.R27.N5

### Untrusted fields

R16. Views and query result models omit `is_untrusted` columns unless the request sets `include_untrusted: true` (ADR-0029.R10). Listing documents therefore does not taint.
Source: ADR-0050.R28

R17. An agent type that must stay clean declares `may_read_untrusted: false` (for example `planning`). For its runs, `include_untrusted` returns `untrusted_read_not_allowed`, and rows that would taint them are left out, with `is_taint_filtered: true` in the response.
Source: ADR-0050.R28

R18. `ListPegging` and `demand_supply_overview` return rows of tainted versions as a numeric-only projection: IDs, quantities, dates and states, no free text. Like aggregates (ADR-0050.R25), such rows do not taint, so the clean planning agent is not filtered on them (flagged, open question). `ListAnalysisCellRow` returns a numeric projection to agent runs in the same way: IDs, document numbers and types, dates, accounts and contributions, no free text; such rows do not taint and are not filtered from a clean run, so a cell still equals its drill rows (ADR-0060.R16). The projection applies only to agent-run callers; people see full rows within their permissions.
Source: ADR-0050.R28, ADR-0050.R28.N1

### Placement, roles and the builder

R19. Schema `query` holds the semantic views (ADR-0004.R16 places them; ADR-0022.R7 keeps tables in `nativeflows`). View names are nouns, unique across the database and never equal to a table name (ADR-0004.R9, ADR-0004.R16): row views end in `_overview`; aggregates use their own noun (`system_account_turnover`). `query` declares each view in its `views.py` with its SQL; a CI check fails on a view without a declaration.
Source: ADR-0050.R42

R20. Roles and connections:
- Views are owned by `nativeflows_query_owner` (`NOLOGIN`, never `BYPASSRLS`), which has `SELECT` on the base tables it needs. Views use `security_barrier`.
- The generated company policy (ADR-0017.R19) applies to `nativeflows_query_owner`; a test runs every view as `nativeflows_readonly` without `nativeflows.company_id` and expects no rows.
- `nativeflows_readonly` has `USAGE` on schema `query` and `SELECT` on its views, and no grant in `nativeflows`.
- `nativeflows_readonly` has a separate connection pool, with `default_transaction_read_only` on, `statement_timeout` 10 seconds for agent runs and 30 seconds otherwise (ADR-0022.R9 allows lowering), and `transaction_timeout` 30 seconds.
Source: ADR-0050.R43

R21. The read-only layer issues `SELECT` only (ADR-0040.R13). The builder composes each statement from the view declaration and the request: one `SELECT` with bound parameters. The analysis compiler emits one statement whose top level is a `SELECT`, with read-only common table expressions, over declared views only and with every value bound (ADR-0060.R12). No client sends SQL, and agents never write SQL (Principle 7). A CI test checks that every built statement, of the builder and of the analysis compiler, is a single `SELECT`.
Source: ADR-0050.R44, ADR-0050.R44.N1

R22. Views call no volatile function. `EXECUTE` on `pg_notify` is revoked from `PUBLIC` and granted to `nativeflows_app` and `nativeflows_worker`.
Source: ADR-0050.R44

### Declarations and exposure

R23. A view declaration holds, beside the SQL:
- columns: meaning (English, translated), type, data label or row condition (ADR-0019.R7), field class, `is_untrusted`; a column with `is_secret` is refused by CI;
- scope columns: record scope (`branch_id`, `warehouse_id`, ADR-0017.R9), the partner column and the import batch column for taint scope (R13), and for document rows the effective `is_tainted`;
- for document rows, the owner scope columns of their document, `owner_employee_id` and `created_by_user_id`; a row that follows a document (a line, an open item) declares the document it follows (ADR-0054.R14, ADR-0054.R15);
- access: filterable columns with their operators, sortable columns, the default stable order, and the key for `Get<View>`.
Source: ADR-0050.R45, ADR-0050.R45.N1

R24. Each view gives `List<View>` and, where keyed, `Get<View>`, registered by `query` (ADR-0004.R21). REST and MCP are generated (Principle 10). The query names are the view's noun in `PascalCase`: `ListPartnerOverview`, `ListSystemAccountTurnover`.
Source: ADR-0050.R46

R25. MCP resources (Principle 7) hold metadata only; data comes through the queries. `nativeflows://query/views` lists the views, and `nativeflows://query/views/<name>` returns a declaration (columns, meanings, labels, field classes, untrusted flags, filters). The analysis catalog adds `nativeflows://query/measures`, `nativeflows://query/measures/<code>`, `nativeflows://query/dimensions` and `nativeflows://query/dimensions/<code>` (ADR-0060.R14).
Source: ADR-0050.R46, ADR-0050.R46.N1

R26. Filter operators: equality; `in` (at most 100 values); ranges on dates, amounts and quantities; `contains` on declared text columns (case and diacritics folded). Sorting is only on declared columns, with `id` as the tiebreak.
Source: ADR-0050.R47

R27. Paging is cursor paging (ADR-0008.R22): `limit` default 100, maximum 1,000. For agent runs the maximum is 200, and `max_rows_read` caps a run's total (ADR-0050.R22).
Source: ADR-0050.R47

### Field classes, record scope and taint in the views

R28. Field classes and record scope are applied in the view and in the builder. The builder sets, with `SET LOCAL`, all from the actor's effective rights (ADR-0050.R31):
- `nativeflows.company_id`, `nativeflows.field_classes`, `nativeflows.scope_branch_ids`, `nativeflows.scope_warehouse_ids`;
- for tainted runs, `nativeflows.taint_scope_partner_id` or `nativeflows.taint_scope_import_batch_id`, `nativeflows.taint_subject`, `nativeflows.taint_work_item_id` and `nativeflows.taint_document_ids` (the drafts of its work item and agent type);
- `nativeflows.read_grants`: always a map keyed by view name, for every query of the read-only layer, so each view's `is_in_scope` reads one format. A `List<View>` query sets a one-entry map; an analysis plan sets one entry per fact view it reads (ADR-0060.R13). A view's entry holds the actor's assignments in force that grant that view's `List` permission, for an agent run those of its human, each as (branch IDs, warehouse IDs, owner scope, the employee IDs of the organization resolver's set, user ID). One fact's grant never widens another's;
- `nativeflows.business_date`, for views that compare dates with it.
Source: ADR-0050.R48, ADR-0050.R48.N1, ADR-0050.R48.N3, ADR-0050.R48.N4

R29. Each field class column is `CASE WHEN query.has_field_class('<class>') THEN … END`, so a missing class yields null even if the builder errs. The builder also leaves those columns out of the result (ADR-0017.R10: omitted, not null).
Source: ADR-0050.R48

R30. Each view computes `is_in_scope` from the scope settings and from its own entry of `nativeflows.read_grants`: true for a document row when one grant passes both record scope and owner scope, and for other rows when one grant passes record scope (ADR-0054.R13, ADR-0054.R14, ADR-0054.R15). The builder always filters on `is_in_scope`, and computes `is_scope_filtered` with one `EXISTS` over the same filters and `NOT is_in_scope`, which returns one boolean and no row.
Source: ADR-0050.R48, ADR-0050.R48.N1, ADR-0050.R48.N4

R31. For a run of a drafting agent type (one whose tool list holds an artifact draft command), the builder also excludes the held-out cases, by the hash rule, from every row query and aggregate: rows of the declared case tables and rows whose declared case-reference columns point at a held-out case. An aggregate it cannot filter is refused with `held_out_filter_unavailable`. Only queries registered held-out filtered may be on such a tool list, and reads of evidence, shadow outcomes, monitor snapshots, automation executions and `GetAutoPostShadowEvaluation` never are (ADR-0059.R16).
Source: ADR-0050.R48, ADR-0050.R48.N2

R32. The builder applies ADR-0050.R25, ADR-0050.R26 and the taint rules R9 to R18 in the views. It omits untrusted columns unless asked and reads the effective `is_tainted` column of returned rows. Each view computes `is_in_taint_scope` as R9 defines the scope: its partner or import batch column equals the run's scope, or the row is the run's subject, its work item or one of `nativeflows.taint_document_ids`. Views of reference data are declared `is_reference` and always pass. For tainted runs the builder filters on `is_in_taint_scope`, and refuses a view that has none of these columns and is not `is_reference`.
Source: ADR-0050.R49

R33. No view over `audit_record`, `audit_change`, `audit_denial`, `policy_decision`, `agent_run_step` or `personal_data_processing_log` is registered for agents. Tainted runs never read audit data (ADR-0038.R7). People read these through their own queries.
Source: ADR-0050.R50

R34. A secret is never in a view (R23).
Source: ADR-0050.R50

### Views

R35. Initial views of master data and stock, for the business flows and the first agents (view: over; partner column; untrusted columns; field class columns; flows):
- `partner_overview`: partner, roles, profiles, groups, credit limit, payment term, price list; partner column `id`; no untrusted or field class column; all flows.
- `contact_overview`: contact with its partner; partner column `partner_id`; sales, onboarding.
- `partner_item_overview`: `partner_item` and `supplier_item` rows with item code, name and units; partner column `partner_id`; `supplier_item` price in field class `cost`; purchasing, quotation.
- `item_overview`: item, product, units, groups, tax group, tracking flags, barcodes; no partner column; preliminary price in field class `cost`; all flows.
- `price_list_entry_overview`: price list entries with list, item, unit, break and dates; no partner column; purchase lists in field class `cost`; sales, purchasing.
- `configuration_model_overview`: configurable products, released revisions, characteristics and allowed values; no partner column; quotation.
- `stock_overview`: stock by item, warehouse, bin, status, lot with expiry, reserved quantity; no partner column; value in field class `cost`; stock, planning.
- `demand_supply_overview`: `demand_supply_line` rows with source document and dates; partner column `partner_id`; planning, sales.
- `planned_order_overview`: planned orders with state, dates, supplier or version, pegging count; no partner column; planning.
- `forecast_accuracy`: forecast against actual demand per item, warehouse and period (ADR-0024.R12); no partner column; planning.
Source: ADR-0050.R51

R36. Initial views of documents and money, in the same form:
- `open_item_overview`: open items with system account, dates, amounts, open amount, days overdue, collection flags; partner column `partner_id`; untrusted: dispute reason; cash, collections.
- `document_overview`: documents of every type: number, state, change state, partner, dates, totals, currency, version, effective taint, origin work item and run; partner column `partner_id`; all flows.
- `document_line_overview`: lines with item, configuration, quantity, unit, net price, amounts, open quantity; partner column `partner_id`; untrusted: line free text from outside; unit cost and margin in field classes `cost`, `margin`; all flows.
- `interaction_overview`: interactions without body: kind, direction, partner, contact, occurred at, subject, sender authentication; partner column `partner_id`; untrusted: subject, body, summary; sales, onboarding.
- `bank_statement_line_overview`: statement lines with money account, dates, amount, reference, counterparty, match state; no partner column; untrusted: description; bank matching.
- `import_row_overview`: rows of an import batch with raw and mapped values and errors; import batch column `import_batch_id`; untrusted: raw values; migration.
- `system_account_turnover`: defined by R46; no partner column; management reporting.
Source: ADR-0050.R51

R37. Later views are added by ordinary changes with the step that builds their tables: `warehouse_task_overview` and `count_accuracy` (ADR-0023.R23), production views (DS-52 to DS-54).
Source: ADR-0050.R51

R38. Personal columns keep their labels in the views (contact fields, row-conditional partner fields). Bank descriptions, counterparty names and counterparty accounts are personal (ADR-0050.R9).
Source: ADR-0050.R51

R39. The document views apply owner scope: `document_overview`, `document_line_overview`, `open_item_overview` through its origin document, and `demand_supply_overview` through its source document. `system_account_turnover`, `forecast_accuracy` and `stock_overview` total over documents without returning them and are registered `is_owner_scoped: false`, so they need an assignment with owner scope `branch` or `company` (ADR-0054.R15).
Source: ADR-0050.R51, ADR-0050.R51.N1

R40. The views `automation_execution_overview` and `decision_artifact_overview` return only rows inside the reader's record and owner scope and replace values of field classes the reader lacks by their hashes (ADR-0058.R11; ADR-0059.R26). `automation_execution_overview` has no partner column, so it is closed to tainted runs. `decision_artifact_overview` holds agent types with their settings, and every artifact with its kind, owner, state, version in force and last monitor result; it is the one registry of X9.
Source: ADR-0050.R51, ADR-0050.R51.N2

R41. The analysis layer adds the fact views `journal_line_overview`, `sales_line_overview`, `purchase_line_overview`, `stock_movement_overview`, `production_output_overview` and `production_variance_overview` (ADR-0060.R3). `journal_line_overview` carries `is_closing_entry`, `is_migration_entry`, `is_special_period` and the `opening_turnover` rows, which only a company-wide grant sees. Each fact view declares its grain and omits untrusted columns; `production_variance_overview` is registered `is_owner_scoped: false`.
Source: ADR-0050.R51, ADR-0050.R51.N3

R42. The analysis layer also adds the label views of its dimensions and the helper views `posting_period_dimension` and `open_item_line_dimension`. The helper views carry no scope and are joined only on keys of in-scope fact rows.
Source: ADR-0050.R51, ADR-0050.R51.N3

R43. The production views are `production_order_overview`, `production_order_component_overview`, `production_order_operation_overview` and `shop_floor_posting_overview`. They have no partner column and carry the subject column `production_order_id` (`id` for the header), so a tainted capture run reads only its order's rows (ADR-0064.R13).
Source: ADR-0050.R51, ADR-0050.R51.N4

### Computed module queries and management reporting

R44. Computed module queries stay with their modules and are allowed on tool lists: `GetPrice` (ADR-0045.R4), `EvaluateConfiguration` (ADR-0046.R8), `GetConfigurationEstimate`, `GetCreditExposure` (ADR-0047.R18), `GetAvailableToPromise` (ADR-0023), `GetProjectedAvailability`, `ListPegging`, `ListCapacityLoad`, `GetCapacityLevelingProposal` (ADR-0024, ADR-0036), `GetAllocationProposal` (ADR-0048.R6), `GetOutboundContentCheck` (`crm`, ADR-0029.R14; ADR-0050.R36), `ListWorkItem` and `GetWorkItem` (ADR-0042). A view never re-implements a figure a module computes: exposure, availability and prices come only from these queries. They run in read-only transactions under the timeouts of R20, and ADR-0050.R25, ADR-0050.R26 and the taint rules R9 to R18 apply to their results.
Source: ADR-0050.R52

R45. The reporting queries are computed module queries too: `GetStatutoryReport`, `ListBookRow`, `ListReportLineContribution`, and the definition, filing, comparative value and render job queries of `reporting`. For agent runs they run under the 10-second statement timeout (R20), so an agent reads a large book by cursor (ADR-0049.R15).
Source: ADR-0050.R52, ADR-0050.R52.N1

R46. `system_account_turnover` serves management reporting (ADR-0027.R8). Its grain is company, posting period, system account (ADR-0010), branch, cost center, project, business unit (read like cost center and project) and transaction currency. It gives debit and credit turnover and closing balance in company currency, and in group currency where set. It reads `account_period_balance` for locked periods and journal lines for open ones (ADR-0014.R18), so figures agree with the books.
Source: ADR-0050.R53, ADR-0050.R53.N2

R47. Statutory reports stay with DS-26. Management reports are never documents: they are views and exports, and analysis plans over the facts of the analysis catalog, `system_account_turnover` among them; saved analyses and KPIs keep them as company data (ADR-0060.R3, ADR-0060.R26, ADR-0060.R27).
Source: ADR-0050.R53, ADR-0050.R53.N1

## Invariants

Rows of `invariants.csv` whose source is a rule of this chunk; the area of each is `safety`.

| INV | Check point | Statement | Protects |
| --- | --- | --- | --- |
| `INV-215` | day (flagged: reading of the literal read scope) | Every row reference in `result_refs`, `context_refs` and `request_refs` of a step recorded after its run's `tainted_at`, wherever the row was first read, is inside that run's tainted read scope: its scope rows, its work item and evidence, drafts of its work item and agent type, or reference data. | R9, R11, R12, R14 |

## Edge cases

| EC | Name | Case | Outcome | Source |
| --- | --- | --- | --- | --- |
| `EC-79` | `injected_instruction_in_quotation_email` | A quotation e-mail asks the agent to add another customer's prices and to send the quotation at once; the run stays in its partner scope, any out-of-scope read is refused with `tainted_read_out_of_scope`, the draft holds only that customer's data, and nothing is sent. | `must_succeed` | ADR-0050.R27; ADR-0051.R10 |

## Settings

None: see chunks 3 and 4; the rules of this chunk own no setting key, and the settings of the analysis layer are stated with ADR-0060.R11 and ADR-0063.R25.

Reads: `agents.tainted_reference_reads` (area `agents`; enum `literal` or `declared_projections`, core default `declared_projections`; R11).

## Conflicts

CONFLICT ADR-0050.R27: the closing mark "flagged, the author's answer may change them" is dropped because ADR-0050.R27.N5 decides that the tainted read scope stays as written (R15).
CONFLICT ADR-0050.R27.N4: the wider wording of the author's decision item 2 of 2026-11-19, recorded here as a conflict for the author, is withdrawn by ADR-0050.R27.N5; R12 states the scope without widening.
CONFLICT ADR-0050.R27.N5: governs over ADR-0050.R27.N4; a further read for a tainted run exists only as a declared projection of a registered query (R12).
CONFLICT ADR-0050.R48.N1: its list format of `nativeflows.read_grants` is replaced by the map keyed by view name of ADR-0050.R48.N4 and ADR-0060.R13 ("never the list of ADR-0050 rule 48's first note"); the content of one grant is kept (R28, R30).
CONFLICT ADR-0050.R48.N4: governs over the first note of ADR-0050.R48; every query of the read-only layer sets the map, a `List<View>` query with one entry (R28).

## Trace

| Source | Where |
| --- | --- |
| ADR-0022.R2.N7 | ref: ADR-0022.R2.N7 |
| ADR-0029.R10 | R5-R8 |
| ADR-0029.R10.N1 | R6 |
| ADR-0029.R10.N2 | R8 |
| ADR-0050.R1 | R1-R4 |
| ADR-0050.R1.N1 | R2, R3 |
| ADR-0050.R1.N2 | R1, R3, R4 |
| ADR-0050.R27 | R9-R15 |
| ADR-0050.R27.N1 | R11 |
| ADR-0050.R27.N2 | R9 |
| ADR-0050.R27.N3 | R10 |
| ADR-0050.R27.N4 | R12 |
| ADR-0050.R27.N5 | R11, R12, R15 |
| ADR-0050.R28 | R16-R18 |
| ADR-0050.R28.N1 | R18 |
| ADR-0050.R42 | R19 |
| ADR-0050.R43 | R20 |
| ADR-0050.R44 | R21, R22 |
| ADR-0050.R44.N1 | R21 |
| ADR-0050.R45 | R23 |
| ADR-0050.R45.N1 | R23 |
| ADR-0050.R46 | R24, R25 |
| ADR-0050.R46.N1 | R25 |
| ADR-0050.R47 | R26, R27 |
| ADR-0050.R48 | R28-R31 |
| ADR-0050.R48.N1 | R28, R30 |
| ADR-0050.R48.N2 | R31 |
| ADR-0050.R48.N3 | R28 |
| ADR-0050.R48.N4 | R28, R30 |
| ADR-0050.R49 | R32 |
| ADR-0050.R50 | R33, R34 |
| ADR-0050.R51 | R35-R43 |
| ADR-0050.R51.N1 | R39 |
| ADR-0050.R51.N2 | R40 |
| ADR-0050.R51.N3 | R41, R42 |
| ADR-0050.R51.N4 | R43 |
| ADR-0050.R52 | R44, R45 |
| ADR-0050.R52.N1 | R45 |
| ADR-0050.R53 | R46, R47 |
| ADR-0050.R53.N1 | R47 |
| ADR-0050.R53.N2 | R46 |
