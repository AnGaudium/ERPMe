Module: agent_runs    Chunk: 2 of 2    Source ADRs: ADR-0050, ADR-0057, ADR-0063, ADR-0065, ADR-0078
Build step(s): 1, 4, 5, 6    Generated from index: 30d5706    Compiled by: Claude Fable 5.2, 2026-11-21

# Compiled spec: `agent_runs`, chunk 2

## Purpose

`agent_runs` (layer 2) owns the run tables and the contract functions that the layer-5 handlers of `agents` call (ADR-0050.R1). This chunk states budget reservation and the Phase 1 budget tiers, run taint, run modes, the catalog rows of the agent runtime, the data-processing policy with the table `data_processing_permission`, tainted reads of declared projections, the Phase 1 modes and promotion of agent types, and run tracing. The gateway, the runtime, the workflows and the commands are law of `agents`; the units for which `agent_runs` is not primary are traced `ref:` and not restated.

## Entities and tables

DDL: `docs/design/DS-05-platform.sql` for `agent_budget_usage`; `docs/design/DS-36-document-intake.sql` (section `[agent_runs]`) for `data_processing_permission`.

| Table | Meaning | Key | Parent | Owner |
| --- | --- | --- | --- | --- |
| `agent_budget_usage` | Cost and runs reserved and spent per budget scope and business date: `scope_kind` (`company_agent_type`, `company`, `company_outside_content`, `installation`), `company_id` (null exactly for `installation`), `agent_type_code` (set exactly for `company_agent_type`), `business_date`, `limit_amount`, `reserved_amount`, `spent_amount`, `run_count`, `run_limit_count` (only on `company_agent_type`, null in Phase 1), `currency` (`USD`); guarded by `reserved_amount` + `spent_amount` <= `limit_amount` (R201 to R203, R208). | `id`; `UNIQUE NULLS NOT DISTINCT (scope_kind, company_id, agent_type_code, business_date)` | `company`, `agent_type` | `agent_runs` |
| `data_processing_permission` | What a company permits a model provider to process: data class, seat class, provider, region and country, cross-border flag, assessment, approver, optional purposes, the provider's terms and retention, suspension, validity dates. Company data, change-tracked (R231). | `id`; `UNIQUE (company_id, id)`; no overlap per (`company_id`, `data_class`, `seat_class`, `provider`, `processing_region`) over `effective_from` to `effective_to` | `company` | `agent_runs` |

The DDL comment on `agent_budget_usage.business_date` says the installation row uses the UTC day; the installation row is keyed by the business date of the company whose run reserves (ADR-0050.R22.N1, `settings.csv`), and this spec follows that.

Tables with their rows in chunk 1 (ADR-0050.R1), which rules of this chunk write or constrain:

- `agent_run`: `mode` (R220), `tainted_at`, `taint_source_kind`, `taint_source_table`, `taint_source_id` (R214, R219), `budget`, `reserved_amount`, `cost_amount` and the call and row counters (R201, R205, R207).
- `agent_run_step`: `context_refs`, `request_refs`, `result_refs` (R216, R240), `reserved_amount` (R201).
- `agent_type_setting`: `mode`, `promoted_version`, `promoted_seat_models`, `active_document_types` (R243 to R256).
- `agent_promotion_evidence`: `target_mode` (`assisted`, `active`) and `document_type`, which is set exactly when `target_mode` is `active` (R253).
- `agent_type`, `agent_type_version`: the declaration with `auto_post_document_types` (R252).

Reads: `setting_value`, `work_item`, `attachment`, `audit_record`, `policy_decision`, `personal_data_processing_log`, `document_extraction`, `item`, `partner_item`, `assist_request`.

## Commands and queries

`agent_runs` registers no command; the commands that write its tables are registered by `agents` (ADR-0050.R1). The rows below hold only what the rules state. The rows of `UpdateAgentTypeSetting`, `CreateAgentPromotionEvidence`, `ListAgentRun` and `GetAgentRun` stand in chunk 1; rules R242, R250, R253, R256 and R257 of this chunk add to them.

| Name | Actor and authorization | Input | Effect | Events | Error codes |
| --- | --- | --- | --- | --- | --- |
| `SetDataProcessingPermission` (module `agents`) | leaf `data_processing` at `full`; only from the execution of an approved change proposal whose approver differs from its submitter; `is_proposal_bound`; on no agent tool list | data class, seat class, provider, region, optional `purposes`, assessment | writes a `data_processing_permission` row; effect class `master_data_change` (R232) | not stated | `approver_is_submitter`, `data_processing_not_permitted` |
| `EndDataProcessingPermission` (module `agents`) | leaf `data_processing` at `full`; `human_only`; on no tool list | the permission | narrows or ends it directly (R233) | not stated | not stated |
| `RunDataProcessingProviderCheck` (job) | catalog leaf `data_processing`: the provider check job; at startup and daily | none | sets `suspended_at`, raises `data_processing_permission_suspended` (R235) | not stated | not stated |
| `GetAgentDraftAcceptance` (query, module `agents`) | not stated | agent type, document type, window | the acceptance of the type's `assisted` drafts (R253) | none | not stated |
| `ListItemCandidate` (query, module `master_data`) | on the tool list of the agent type version that uses the projection (R239) | typed match keys: code, barcode, normalized name | the first `tainted_projection` (R238) | none | `tainted_projection_cap_reached` |

Contract functions of `agent_runs`, not commands: `agent_runs.contract.reserve_budget` (R201), `settle_budget` (R205), `agent_runs.contract.mark_run_tainted` (R215), and the contract function that writes `data_processing_permission` (ADR-0050.R1.N1 names none).

Error codes bound to no command of this module: the catalog rows of R221, and the run outcomes `budget_exceeded`, `time_exceeded`, `routing_blocked` that the rules of this chunk set.

## Rules

### Budget reservation

R201. Before every LLM call the runtime computes the worst case: counted input tokens times the input price, plus `max_output_tokens` times the output price. `agent_runs.contract.reserve_budget` adds it, in one statement each, to the run's totals and to the `agent_budget_usage` rows of the run: scope `company_agent_type` (company, agent type, business date), `company` (company, business date) and `installation` (installation, day: the business date of the company whose run reserves, ADR-0050.R22.N1), each guarded by `reserved + spent + amount <= limit`.
Source: ADR-0050.R23

R202. Each guarded statement first sets the row's `limit_amount` to the limit in force for that business date from `registry.contract.get_setting`, so a lowering applies at the next reservation, and a row whose spent amount already exceeds a lowered limit accepts nothing more. The `limit_amount` of a `company_agent_type` row is the company's cap in force, refreshed at every reservation, so the row never binds before the company row does and a raised cap never leaves a lower limit on it; its `run_limit_count` stays null. The reservation checks no per-type limit.
Source: ADR-0050.R23.N1, ADR-0078.R7

R203. A run of an agent type that reads outside content, and any run that is tainted when it reserves, also reserves on the row of scope `company_outside_content` (company, business date), whose limit is (1 − `agents.internal_reserve_share`) × the company cap in force, rounded down to the cent. An internal run reserves on its agent type, company and installation rows only, so the reserve stays free for it. `INV-212` covers this row like every `agent_budget_usage` row; `DS-05-platform.sql` holds the scope kind.
Source: ADR-0050.R23.N1, ADR-0078.R7

R204. All guards of one call run in one transaction. If any guard fails, nothing is reserved, the call is not made, and the run stops with `budget_exceeded`.
Source: ADR-0050.R23, ADR-0050.R23.N1

R205. After the call, `settle_budget` replaces the reservation by the actual cost. A failed call settles at the provider's reported usage, or zero when it reports none; a call whose outcome is unknown settles at its reserved amount (ADR-0050.R16).
Source: ADR-0050.R23

R206. LLM calls, tool calls and rows read are checked the same way before each call (rows against the query's `limit`). Before each step the runtime checks the remaining time; a step that cannot start in time ends the run with `time_exceeded`. An LLM call's timeout is the remaining time.
Source: ADR-0050.R23

R207. No run and no daily row ever exceeds its limit, also with runs in parallel. `INV-212` checks it, and the lab checks interleavings.
Source: ADR-0050.R23

### Budget tiers in Phase 1

R208. Phase 1 has these budget tiers and no other:
- Per company per day: `agents.company_daily_max_cost`, within `agents.installation_daily_max_cost`, with the reserve `agents.internal_reserve_share` (ADR-0050.R22).
- Per run: the ceilings of the agent type version's declaration (ADR-0078.R3). For the assistant, the company setting `assist.max_cost_per_run` may lower its cost ceiling (ADR-0077.R13).
- The `company_agent_type` rows of `agent_budget_usage` keep counting cost and runs per agent type (R202).
Source: ADR-0078.R7, ADR-0050.R55.N3

R209. No budget value has scope `agent_type` in Phase 1. The keys `agents.<agent_type>.daily_max_cost`, `agents.<agent_type>.daily_max_runs` and the `agents.<agent_type>.run_max_*` keys are not in `settings.csv`. The reservation before every LLM call, the stop on `budget_exceeded` and the `agent_budget_exhausted` work item stay (ADR-0050.R22).
Source: ADR-0078.R7, ADR-0050.R55.N3

R210. `agent_budget_exhausted` is raised once per business date and tier that trips, with the open keys `company:<date>`, `outside_content:<date>` and `installation:<date>`. Under `outside_content:<date>` the outside-content pool tripped: agent types that read outside content stop, internal types keep running on the reserve. Its subject is the agent type whose reservation failed.
Source: ADR-0078.R7

R211. `analysis` and `planning` read no outside content, so they are the internal agent types of Phase 1 and draw on `agents.internal_reserve_share` (default 0.40, ADR-0050.R22).
Source: ADR-0078.R7

R212. Spec 03 rule 8 reads "Budgets: per run for each agent type, and per company per day, with a circuit breaker." Phase 1 meets it so: per agent, the per-run ceilings of the declaration and the per-type usage rows; per company and per day, the company cap. Spec 17 says the seat's budget is per run and the daily budget is the company's.
Source: ADR-0078.R7, ADR-0078.R7.N1

R213. In Phase 1 the customer sets the company's daily cap, the assistant's cost per run and `agents.internal_reserve_share`. A per-type cap returns under the "Revisit when" of ADR-0078.
Source: ADR-0078.R7, ADR-0078.R7.N2

### Run taint

R214. `agent_run.tainted_at` is set once and never cleared, with its source columns (`taint_source_kind`, `taint_source_table`, `taint_source_id`). It is set at start (ADR-0050.R15), or by the dispatcher's query path just before it returns to the run any of:
- a non-null `is_untrusted` field;
- a row whose effective `is_tainted` is true;
- a work item with `is_tainted`;
- the content of an attachment whose source kind is outside content.
Source: ADR-0050.R25

R215. The dispatcher calls `agent_runs.contract.mark_run_tainted` in its own committed transaction before it returns the result. If that commit fails, the result is not returned. So every later command of the run starts after `tainted_at`, and `recorded_at` comparisons (`INV-88`) hold.
Source: ADR-0050.R25

R216. From `tainted_at` on, the runtime refuses, before the gateway call or the dispatch, a context item or a command input whose recorded source row (ADR-0050.R8; `context_refs`, `request_refs`) is outside the tainted read scope (ADR-0050.R27), also when the row was read before the taint, with `tainted_read_out_of_scope`. Only the runtime knows that provenance. A row reached through recorded provenance from a row in scope is in scope, for example the item behind the `item_id` of the partner's `partner_item` row.
Source: ADR-0050.R25

R217. As a second line, the dispatcher checks every reference-typed ID in a tainted run's payload whose table has a partner or import batch scope column, or is a document, against the run's scope and its drafts (ADR-0050.R27). References to tables without such a column (items, units) are covered by the runtime's provenance check. The command envelope of ADR-0008 does not change.
Source: ADR-0050.R25

R218. A deterministic aggregate (a sum, count or balance) computed over rows that include tainted versions does not taint the run: taint guards against untrusted text, and an aggregate carries none. Individual rows of tainted versions still taint. Run taint applies to every query result returned to a run: views, module queries and the results and check details of commands, using the result model's field attributes. It does not depend on the agent asking nicely.
Source: ADR-0050.R25

R219. A generated file (attachment source kind `generated`) whose rendered instance held a non-null `is_untrusted` field carries `contains_untrusted`. Returning its content to a run taints the run as an attachment from outside content does, with `taint_source_kind` `untrusted_field` and source table `attachment` (ADR-0049.R28). The other values of `taint_source_kind` are `work_item`, `outside_subject`, `tainted_row` and `outside_attachment`.
Source: ADR-0050.R25.N1

### Run modes

R220. `agent_run.mode` is `live`, `shadow` (ADR-0050.R14), `replay` (with recorded outputs) or `evaluation` (live calls against the golden set). Replay and evaluation runs happen only in `test` and `simulation` environments, or on staging (ADR-0003 R12). Phase 1 starts no live shadow run of an agent (R251).
Source: ADR-0050.R37

### Catalog rows of the agent runtime

R221. Error codes (DS-04), each with category and retryable flag:
- `agent_mode_off` (precondition, no): the agent type is `off` for the company, or the LLM is off.
- `agent_budget_exceeded` (precondition, no): a run or daily budget would be exceeded; `details` names the limit.
- `agent_scope_unresolved` (precondition, no): the agent type's scope resolver found no scope for the subject.
- `approver_is_submitter` (permission, no): the person who submitted a promotion proposal tried to approve it (ADR-0050.R14).
- `promotion_evidence_stale` (precondition, no): the agent type's behavior hash or seat models no longer equal the frozen promotion evidence (ADR-0050.R14).
- `llm_provider_unavailable` (unavailable, yes): the provider failed after retries and fallback, or its circuit is open.
- `llm_output_invalid` (validation, no): an LLM output failed its schema or checks three times.
- `llm_routing_refused` (permission, no): a request still held a personal value with the switch on, or held a secret.
- `tool_not_allowed` (permission, no): the tool is not on the run's list.
- `agent_kind_not_declared` (precondition, no): `StartAgentRun` names a work item kind or subject table the agent type does not accept.
- `tainted_read_out_of_scope` (permission, no): a tainted run asked for rows outside its scope, or used such a row in a prompt or a command input.
- `untrusted_read_not_allowed` (permission, no): a run of an agent type that must stay clean asked for untrusted fields.
- `tainted_run_not_allowed` (permission, no): a tainted run sent a command not registered `is_draft_only`.
- `list_export_too_large` (precondition, no): the list has more rows than `list_export_max_rows`.
Source: ADR-0050.R55

R222. Denial records (ADR-0038.R5) also cover `tool_not_allowed`, `tainted_read_out_of_scope`, `untrusted_read_not_allowed` and `tainted_run_not_allowed`. The check result `outbound_content_flagged` (ADR-0050.R36) is registered in DS-04.
Source: ADR-0050.R55

R223. Work item kinds of module `agents`, which raises them through `work.contract`:
- `agent_run_stopped`: subject the agent type, owner the human of the first run raising it, `open_key` `<agent_type>:<outcome>:<business date>`, the runs as evidence.
- `agent_budget_exhausted`: subject the agent type whose reservation failed, owner `company_owner`, `open_key` by tier (R210).
- `agent_denials_repeated`: subject the run, owner `company_owner`, the default key.
- `agent_mode_degraded`: subject the agent type, owner `company_owner`, key the agent type within the company (ADR-0050.R14).
- Open keys carry the agent type or the tier, so no item is shared between agent types by accident.
Source: ADR-0050.R55, ADR-0050.R55.N1

R224. The invariants `INV-210` to `INV-215` and `INV-216` (area safety; first step 5, the window in which the first agent runs after the step 4 gate) lie in the range `INV-200` to `INV-299` (ADR-0038.R8). INV-206 to INV-209 and INV-217 to INV-219 stay free; codes are not a sequence promise. Their statements stand in the Invariants tables (`INV-212` and `INV-215` in chunk 1).
Source: ADR-0050.R55, ADR-0050.R55.N1

R225. Further catalog rows:
- Registry attribute `is_draft_only` (ADR-0008.R1); capability `read_agent_run_bodies` (ADR-0017.R4).
- Settings: company `routing_switch` and `agents.company_daily_max_cost`; installation `llm_provider` (Phase 1: `anthropic` only), `agents.installation_daily_max_cost`, `agents.run_step_retention_days` and `list_export_max_rows`.
- `agents.company_daily_max_cost` and `agents.installation_daily_max_cost` are registered in `settings.csv`, with the reserve setting `agents.internal_reserve_share`; the agent-type settings of ADR-0050.R22.N2 are removed by ADR-0050.R55.N3 and ADR-0078.R7.
- Verbs (glossary): Start gains "or start an agent run"; Complete gains "or finish an agent run with its outcome".
Source: ADR-0050.R55, ADR-0050.R55.N2

R226. The lab check `t10_agents.py` of the validation lab is pure functions. It covers: budget reservation without overshoot under interleaved runs; taint on read (untrusted field, tainted row, tainted item at start, clean agent types filtered); the tainted read scope with own drafts and reference data; the permission intersection re-evaluated after the human loses a right; tool list checks and the denial stop; schema-validated output with two retries; routing-switch redaction with the residual scan; shadow mode never executing; replay determinism and divergence; outside-content subjects starting tainted; rows read before taint refused as prompt or command inputs; `is_draft_only`; seat data classes; the one rule for the human acted for; the supplier gate; orphaned reservations settled at the worst case and a diverged resume stopped; denials counted when their records are dropped; wake-ups skipping agent-origin events; shadow runs without a claim; aggregates that do not taint; the outbound check in a draft's plan; the bank re-run's guards, its tainted rule proposal and the shadow comparator on the pure cascade; aligned taint instants; the dispatcher's check order for `EC-56` and for replays (step 6 before step 8); and that the dispatcher's query path refuses by run gates before permission (DS-04, dispatcher check order). It does not cover the database, RLS, the provider or the queue.
Source: ADR-0050.R56, ADR-0050.R56.N1

### Data-processing policy and permissions

R227. The regime setting `data_processing.policy` (ADR-0016.R9) is registered by the core without a default. A regime that declares no value makes every check fail closed with `regime_configuration_missing` (ADR-0016.R10). Every package states its policy, the test package `l10n_xx` included (ADR-0053.R9); a regime may open it as an option for companies (ADR-0016.R11).
Source: ADR-0057.R20

R228. The schema of `data_processing.policy` holds, per data class (`internal`, `personal`, `sensitive_personal`):
- `model_processing`: `allowed`, `forbidden`, `company_option`;
- `cross_border`: `allowed`, `requires_assessment`, `forbidden`, `company_option`;
- `assessment_kind` (a package code) and `assessment_deadline_days` (from the first transfer);
- `allowed_countries` (an optional list of ISO codes);
- `max_provider_retention_days` and `requires_no_training`;
- `exemptions`: package-declared conditions of core-registered condition types, as the deductibility conditions of ADR-0053.R3.
Source: ADR-0063.R18, ADR-0057.R20.N1

R229. The first schema's fields read as the widened ones: `allowed` true or false as `model_processing` `allowed` or `forbidden`; `assessment_for_cross_border` true or false as `cross_border` `requires_assessment` or `allowed`. Packages move to the new fields at their next release.
Source: ADR-0063.R18

R230. The policy has no core default and fails closed (ADR-0016.R10). A package may only tighten the core floors: no sensitive personal values in Phase 1, whole images only, logging always on, no provider that trains on customer data. A permission is refused with `data_processing_not_permitted` when its provider's `retention_days` exceeds `max_provider_retention_days` or its country is outside `allowed_countries`. The core holds no country content; country packages state their values.
Source: ADR-0063.R18

R231. `data_processing_permission` (owner `agent_runs`, company data, change-tracked) lists what the company permits: `data_class` (`internal` or `personal`), `seat_class`, `provider`, `processing_region` and `processing_country`, `is_cross_border`, the assessment attachment and date where one is needed (`assessment_attachment_id`, `assessed_on`), who approved it (`approved_by_user_id`), optional `purposes` from `supplier_invoice`, `contact_card`, `inquiry_lines`, `product_source`, the terms reference and retention it was approved under (`provider_terms_ref`, `provider_retention_days`), `suspended_at` with `suspension_reason` (`provider_region_changed`, `provider_terms_changed`), and the dates `effective_from` and `effective_to`. A company has no row by default, so the seat `extraction_vision_personal` is off.
Source: ADR-0057.R20, ADR-0057.R20.N1, ADR-0063.R14

R232. `SetDataProcessingPermission` (module `agents`, effect class `master_data_change`, change-tracked, `is_proposal_bound`, on no agent tool list, verb Set with the declared minimum level `full` on the leaf `data_processing`) is accepted only from the execution of an approved change proposal whose approver differs from its submitter (`approver_is_submitter`), like a promotion (ADR-0050.R14). Its check refuses a permission that the regime policy forbids, or a cross-border one without an assessment where the policy requires one (`data_processing_not_permitted`). A permission names a provider and region of the provider registry; the handler copies the region's country and computes `is_cross_border` against the company's country. The proposer types neither.
Source: ADR-0057.R20, ADR-0057.R20.N1, ADR-0063.R14

R233. `EndDataProcessingPermission` (module `agents`, `human_only`, verb End with the declared minimum level `full` on the leaf `data_processing`, on no tool list) narrows or ends a permission directly. The leaf `data_processing` under `agent` (module `agents`) holds both commands, so a data-protection role can approve without the right to manage agents. Changes stay four-eyes proposals.
Source: ADR-0057.R20, ADR-0057.R20.N1, ADR-0063.R14

R234. Each provider endpoint of the installation declares in its adapter configuration (DS-37) the processing region and its country, and: `retention_days` (0 for zero retention), `abuse_review` (`human`, `automated`, `none`), `is_training_on_customer_data` (must be false; an endpoint that says true is refused at startup) and `terms_ref` (the data-processing terms in force).
Source: ADR-0057.R20, ADR-0063.R14

R235. When the registry changes an endpoint's region or terms reference under an active permission, `RunDataProcessingProviderCheck` (at startup and daily) sets the permission's `suspended_at` and raises `data_processing_permission_suspended` for `company_owner`. A suspended permission covers nothing until a new one is approved.
Source: ADR-0063.R14, ADR-0057.R20.N1

R236. The gateway evaluates the policy and the company's permissions before every request that carries a personal value (ADR-0063.R15), a whole-attachment item (ADR-0057.R21) or goes to a seat of class `extraction_vision_personal`, in every run mode (live, shadow, replay against the provider, evaluation and golden-set replays). It refuses the request with `data_processing_not_permitted` when no active permission covers the item's data class, the seat class, the provider and its registered region; the run ends `routing_blocked`.
Source: ADR-0057.R20, ADR-0057.R20.N1

R237. A company may permit the installation's cloud provider for `extraction_vision_personal` through a `data_processing_permission` row; adding the seat to spec 17's seat list stays the author's. Hard: the seat has no tools; `routing_switch` stays the company's kill switch; no sensitive personal data class in Phase 1; images are sent or refused whole.
Source: ADR-0063.R14

### Tainted reads of declared projections

R238. The registry attribute `tainted_projection` on a query's result model names the columns a tainted run receives. CI accepts only closed shapes (ID, code, unit, status, category, date, quantity) and `internal` names, never prices, costs, stock, partner columns, `personal` columns or free text. Its first instance is `ListItemCandidate`, the query ADR-0062.R17 called `ResolveItemCandidates` (query verbs are only `Get`, `List`, `Evaluate` and `Render`, ADR-0004.R21): id, code, name, unit, category and status of items, by typed match keys (code, barcode, normalized name), at most 20 rows per call and at most 10 calls per run; rows restricted to another partner are excluded. Beyond the call cap it returns `tainted_projection_cap_reached`.
Source: ADR-0063.R16

R239. The setting `agents.tainted_reference_reads` (company, with an optional per-agent-type value) is `literal` or `declared_projections`, default `declared_projections`. An agent type version uses a projection only when it names the query on its tool list.
Source: ADR-0063.R16

R240. Declared projections join the reference data of the literal scope (ADR-0050.R27, item 4) as the reading of spec 03 rule 1, and they are the only read beyond items 1 to 3 of ADR-0050.R27. The setting only narrows that reading back to the literal scope, so no setting widens the floor (ADR-0029.R14). The run stays tainted; projected calls are recorded in the step's `context_refs` with the projection version and the row count. The readings (a) to (r) of the cited ADRs stand as readings of ADR-0050.R27.
Source: ADR-0063.R16, ADR-0063.R16.N1

### Modes of an agent type in Phase 1

R241. The Phase 1 modes in `agent_type_setting.mode` are `off`, `assisted`, and `active` only as the gateway uses it. The DDL keeps `shadow` for Phase 2; `check` refuses it in Phase 1 seed and configuration.
Source: ADR-0078.R5

R242. At run time `UpdateAgentTypeSetting` refuses mode `shadow` in Phase 1, and refuses every mode except `off` for an agent type that has no Phase 1 workflow (ADR-0078.R2), with `validation_failed`. `agent_mode_not_declared` is the code for `active` without declared document types (R252) and is not reused.
Source: ADR-0078.R5

R243. `active` is set for an agent type and the document types named in `active_document_types` only by an approved change proposal, with the evidence of R253. While the document type's gateway mode is not `live`, the agent type counts as `assisted` for the gateway. The assistant and `planning` are never `active`: their outputs are drafts and proposals that a person confirms or approves.
Source: ADR-0078.R5

R244. The setting `agents.<agent_type>.drift_action` keeps its values (`signal`, `pause_new_runs`, `demote_to_shadow`). Until Phase 2, `demote_to_shadow` acts as `pause_new_runs`.
Source: ADR-0078.R5

### Promotion to `assisted`

R245. A version is promoted to `assisted` when it passes its evaluation set with the real provider, per pair of seat and model, and the replay of recorded responses in CI (ADR-0050.R39, ADR-0050.R40; spec 17). The replay proves the code path; only the real-provider run proves a model, so a new seat model always needs it. The evidence is the stored evaluation result, named in `agent_type_setting.promoted_version` and `promoted_seat_models`.
Source: ADR-0078.R6

R246. `generate` writes the passing results of a release into an evaluation manifest shipped with it: one row per agent type, behavior hash, seat and model. The runtime reads the manifest; nothing else proves a pair. The model fallback of ADR-0050.R6 uses only models with a passing result in the manifest.
Source: ADR-0078.R6

R247. A company already `assisted` stays `assisted` across a change of the behavior hash (version, constants or seat model; ADR-0050.R14) when the manifest holds a passing result for the new behavior. The runtime then updates `promoted_version` and `promoted_seat_models` as `system`, with an audit record, so later evidence counts under the behavior that actually runs.
Source: ADR-0078.R6

R248. No Phase 1 agent type declares a parameter set (ADR-0059.R7), so the behavior hash has no per-company part; constants are part of the version.
Source: ADR-0078.R6

R249. A behavior without a passing result runs nothing: where ADR-0050.R14 drops the effective mode to `shadow`, Phase 1 drops it to `off`, with the same reason and the same `agent_mode_degraded` work item. This applies to every Phase 1 agent type, the assistant's `ask` and resolve purposes included.
Source: ADR-0078.R6

R250. `CreateAgentPromotionEvidence` computes the evidence from the stored evaluation result instead of `GetAgentShadowEvaluation` (ADR-0050.R14). Exceptions by agent type:
- `analysis` keeps its exception (ADR-0050.R14): the daily `RunAnalysisEvaluation` on the company's verified examples is its evaluation in use. A version with no passing CI evaluation is `off` like any other; a failing daily evaluation raises `agent_quality_below_threshold` (ADR-0078.R15).
- `document_reader` is promoted by the golden-set thresholds of ADR-0057.R34. Its live shadow-agreement criterion is replaced by the replay of the company golden set of at least 50 real documents, which that rule already requires before `assisted`. It is the one exception to the carry-over of R247: after a change of behavior it returns to `assisted` in a company only when the replay of that company's golden set has passed again (ADR-0057.R13).
- `planning` is promoted by its evaluation set; the comparator of ADR-0051.R25 measures quality in use on stored output (ADR-0078.R15).
Source: ADR-0078.R6

R251. Phase 1 has no live shadow period. Live shadow comparison of agents against what people did (ADR-0050.R14) returns in Phase 2, together with its evidence tables; live shadow runs of `planning` return then too. The gateway's own mode `shadow` for a document type runs its deterministic checker without posting, so no live agent shadow is needed. `assisted` comes from the evaluation (R245) and `active` from the in-use draft acceptance (R253).
Source: ADR-0078.R6, ADR-0065.R11.N1

### Agent mode `active`

R252. `active` is `assisted` plus one thing: the type's drafts of the document types named at promotion may pass the gateway as tainted drafts. The agent still only drafts; floor 4 of ADR-0043.R9 and the tool list rules are unchanged. An agent type version names the document types it may draft for the gateway (`auto_post_document_types`). Setting `active` for a version that names none returns `agent_mode_not_declared`. The next version of the `purchase_invoice` agent type names `purchase_invoice`.
Source: ADR-0065.R11

R253. `UpdateAgentTypeSetting` to `active` runs only from an approved change proposal that another person approves (`approver_is_submitter`, also in the small-company mode), from a type already promoted to `assisted` with the same behavior hash and seat models. It names one `agent_promotion_evidence` row per document type, with target mode `active`, computed by `CreateAgentPromotionEvidence` from `GetAgentDraftAcceptance`: the type's `assisted` drafts of that document type under the promoted behavior hash and seat models over at least two calendar months, at least N = ceil(3 / `auto_post.max_error_rate`) of them, at least (1 − rate) posted unchanged by people (the version the run wrote was posted with no later version), and none posted to another partner. Otherwise it returns `shadow_evidence_insufficient`. The executing transaction records the document types in `agent_type_setting.active_document_types`.
Source: ADR-0065.R11, ADR-0078.R6

R254. `active` does not carry over a change of the behavior hash: until the type is promoted again under R253 on drafts of the new behavior, it counts as `assisted` for the gateway. Draft acceptance counts only drafts written under the current behavior hash.
Source: ADR-0065.R11.N1, ADR-0078.R6

R255. The effective mode is computed by ADR-0050.R14 with R249. While an `agent_quality_below_threshold` item is open for the type, an `active` type counts as `assisted` for the gateway, whatever `agents.<agent_type>.drift_action` says, because drift that touches an acting path always suspends it (ADR-0063.R12).
Source: ADR-0065.R11, ADR-0065.R11.N1

R256. Lowering `active` to `assisted` or below is direct, by one person, at once.
Source: ADR-0065.R11

### Tracing

R257. An operator follows one piece of work from the work item: `ListAgentRun` filters by `work_item_id`; `GetAgentRun` returns the steps with tool name, plan hash and audit record; the case timeline of ADR-0066.R17 shows items, runs, versions, approvals and policy decisions in order. Cost and runs per company, agent type and business date are the `company_agent_type` rows of `agent_budget_usage`, shown on the operations dashboard (ADR-0038).
Source: ADR-0078.R14

## Invariants

Statements are those of `invariants.csv`; every row has first step 5, except `INV-764` (first step 6). "Protects" names a rule of this chunk or the source ID of a rule stated elsewhere. The rows of `INV-212` and `INV-215` stand in chunk 1.

| Invariant | Name | Check point | Statement | Protects |
| --- | --- | --- | --- | --- |
| `INV-88` | `taint_inherited` | day | Every document version written by a run tainted at its `recorded_at`, or whose origin run was, or whose previous or `derived_from_version_id` version was effectively tainted when it was written, has `is_tainted` true. Flagged: taint clearing (ADR-0029.R8). | R215; ADR-0029.R8 |
| `INV-210` | `tainted_run_outputs_tainted` | day | Every outbox event, work item raise and work item note written by an agent run tainted at the row's `recorded_at` (`tainted_at` at or before it, the instant `INV-88` uses), or by a consumer whose origin run was tainted at the origin event's `recorded_at`, has `is_tainted` true. | R214, R215; ADR-0050.R26, ADR-0013.R11, ADR-0042.R5 |
| `INV-211` | `agent_commands_on_tool_list` | day | Every audit record with an `agent_run_id` names a command on the tool list of that run's agent type version. | ADR-0050.R29 |
| `INV-213` | `personal_llm_sends_logged` | day | Every LLM step that sent personal values has its `personal_data_processing_log` entry; no LLM step sent a personal value while its company's routing switch was on. Flagged: local provider and personal data (ADR-0050.R5). | ADR-0050.R9, ADR-0050.R10 |
| `INV-214` | `agent_tool_lists_safe` | day | No agent type version's tool list holds a command of effect class `posting`, a Submit, Post or Issue command, a `human_only`, `outbound_send` or `is_internal_only` command, an allowed-target command of ADR-0029.R2 (effect class `master_data_change` or `is_proposal_bound`), an approval, taint clearing, auto-post confirmation, policy, role, agent-setting or promotion-evidence command, an agent run command or query, a work item claim, assign or resolve command, an audit query, `ListAllowedCommand`, `GetSessionContext`, `GetPolicyEvaluation` or `CreateListExport`. | ADR-0050.R29, ADR-0050.R30 |
| `INV-216` | `tainted_commands_draft_only` | day | Every audit record of a command run by an agent run tainted at the record's `recorded_at`, or by a consumer whose origin run was tainted at the origin event's `recorded_at` (the instant `INV-210` uses), has `is_draft_only` true as registered at the time, except `CompleteAgentRun`. | R215; ADR-0050.R26 |
| `INV-645` | `vision_only_with_permission` | day | Every LLM request of any run mode that carried an attachment page was covered at its `recorded_at` by an active data-processing permission for its company, data class, seat class, provider and registered region, with the company's routing switch off. | R236; ADR-0057.R21 |
| `INV-764` | `agent_active_evidenced` | day | Every `agent_type_setting` in mode `active` names document types its promoted agent type version declares, each covered by sufficient `agent_promotion_evidence` with target mode `active` at the promoted behavior hash, from a proposal approved by a person other than its submitter. | R252, R253 |

`INV-200` is named by R224 only as the lower bound of the block; it is an audit invariant and has no row here.

## Edge cases

| Edge case | Name | Case | Outcome | Protects |
| --- | --- | --- | --- | --- |
| `EC-56` | `bank_account_change_by_email` | An e-mail asks to change a supplier's bank account; the agent run's direct call is rejected with `tool_not_allowed` (the command is on no tool list), a consumer command carrying the run as origin with `proposal_required`, and a change proposal approved by a second human succeeds (DS-04 dispatcher check order). | `must_reject:tool_not_allowed`, `must_reject:proposal_required`, then `must_succeed` | R226; ADR-0029 |

## Settings

Rows of `settings.csv` whose governing rule stands in this chunk. The rows of `agents.company_daily_max_cost`, `agents.installation_daily_max_cost`, `agents.internal_reserve_share` and `agents.run_step_retention_days` stand in chunk 1 (ADR-0050.R22, ADR-0050.R19).

| Key | Value type | Scopes | Core default | Bounds | Used by |
| --- | --- | --- | --- | --- | --- |
| `agents.tainted_reference_reads` | enum | company; agent_type | `declared_projections` | `literal`, `declared_projections`; `literal` is tighter | R239, R240 |
| `data_processing.policy` | object (schema of R228) | regime | none: fail closed | schema; packages only tighten | R227 to R230 |
| `assist.max_cost_per_run` | amount (USD) | company | 0.20 | 0.01..0.5; lower is tighter | R208, R213 |
| `agents.<agent_type>.drift_action` | enum | agent_type | `signal` | `signal`, `pause_new_runs`, `demote_to_shadow`, in that order | R244, R255 |

R225 names `routing_switch`, `llm_provider` and `list_export_max_rows`; `settings.csv` holds no row with these keys.

Reads: `auto_post.max_error_rate` (R253); `automation.breaker_failures` and `automation.breaker_window_minutes` (`automation`; ADR-0058.R28, traced `ref:`); `cash.auto_post.accept_llm_originated_rules` (`cash`; ADR-0065.R22, traced `ref:`). The row of `agents.<agent_type>.wake_up_mode.<kind>` stands in chunk 1.

## UI annotations

The sources give no floorplan, title, facet, field annotation or tile for this module. Work item kinds that the rules of this chunk name (catalog `work-item-kinds.csv`, module `agents`; none is agent-resolvable):

| Kind | Subject table | Owner | Due | Resolution | Rule |
| --- | --- | --- | --- | --- | --- |
| `agent_run_stopped` | `agent_type` | `run_on_behalf_of` | `days:1` | `person` | R223 |
| `agent_budget_exhausted` | `agent_type` | `company_owner` | `same_day` | `person` | R210, R223 |
| `agent_denials_repeated` | `agent_run` | `company_owner` | `same_day` | `person` | R223 |
| `agent_mode_degraded` | `agent_type` | `company_owner` | `days:1` | `system` | R223, R249 |
| `agent_quality_below_threshold` | `agent_type` | `company_owner` | `days:5` | `person` | R250, R255 |
| `data_processing_permission_suspended` | `data_processing_permission` | `company_owner` | `days:1` | `person` | R235 |

## Conflicts

CONFLICT ADR-0050.R23: the per-type usage row no longer carries a limit of its own; its limit is the company cap and the reservation checks no per-type limit, governed by ADR-0078.R7 (R202, R203). The installation row's day is the business date of the company whose run reserves, governed by ADR-0050.R22.N1, not the UTC day of the DDL comment on `agent_budget_usage.business_date` (R201).
CONFLICT ADR-0050.R25: the mark "flagged for the author (open question)" on aggregates that do not taint is dropped; ADR-0063.R16.N1 confirms the readings (a) to (r) of ADR-0050.R27, and reading (g) is this one (R218, R240).
CONFLICT ADR-0050.R37: the run mode `shadow` stays in the DDL, but Phase 1 starts no live shadow run of an agent, governed by ADR-0078.R6 (R251).
CONFLICT ADR-0050.R55.N2: the agent-type settings the note registers with the reserve setting are removed in Phase 1, governed by ADR-0050.R55.N3 and ADR-0078.R7 (R225).
CONFLICT ADR-0050.R55: the settings list names `agent_run_step_retention_days`; its registry key is `agents.run_step_retention_days` by ADR-0050.R19.N2, and the open key of `agent_budget_exhausted` is by tier under ADR-0078.R7 (R210, R225).
CONFLICT ADR-0050.R55.N1: the open key `<agent_type>:<business date>` of `agent_budget_exhausted` for an agent type's daily limits no longer exists, because Phase 1 has no per-type limit; ADR-0078.R7 gives the keys `company:<date>`, `outside_content:<date>` and `installation:<date>` (R210).
CONFLICT ADR-0057.R20: the commands sit on the leaf `data_processing`, not `agent` (ADR-0063.R14); the gateway gate applies to every request carrying a personal value, which closes the rule's open question (ADR-0057.R20.N1, ADR-0063.R15); the policy schema is the widened one of ADR-0063.R18 (R228, R232, R233, R236).
CONFLICT ADR-0063.R16: the mark "partly answered, open for the author's confirmation" is dropped; ADR-0063.R16.N1 confirms the reading (R240).
CONFLICT ADR-0065.R11: a version or seat model change drops the effective mode to `off` in Phase 1, not `shadow`, and the evidence for `assisted` is the evaluation, not a live shadow period, governed by ADR-0078.R6 and ADR-0065.R11.N1 (R249, R251, R254, R255).
CONFLICT ADR-0078.R7: the customer also sets `agents.internal_reserve_share`, added by ADR-0078.R7.N2 (R213).
CONFLICT ADR-0078.R7.N1: the bullet on spec 03 rule 8 is no longer an open question; the note records that spec 03 rule 8 and spec 17 were aligned on 2026-11-21, and R212 states the aligned text.

## Proposed (not law)

None

## Trace

| Source | Where |
| --- | --- |
| ADR-0050.R23 | R201, R204, R205, R206, R207 |
| ADR-0050.R23.N1 | R202, R203, R204 |
| ADR-0050.R25 | R214-R218 |
| ADR-0050.R25.N1 | R219 |
| ADR-0050.R33 | ref: ADR-0050.R33 |
| ADR-0050.R33.N1 | ref: ADR-0050.R33.N1 |
| ADR-0050.R37 | R220 |
| ADR-0050.R39 | ref: ADR-0050.R39 |
| ADR-0050.R50 | ref: ADR-0050.R50 |
| ADR-0050.R55 | R221-R225 |
| ADR-0050.R55.N1 | R223, R224 |
| ADR-0050.R55.N2 | R225 |
| ADR-0050.R55.N3 | R208, R209 |
| ADR-0050.R56 | R226 |
| ADR-0050.R56.N1 | R226 |
| ADR-0051.R5.N2 | ref: ADR-0051.R5.N2 |
| ADR-0051.R8 | ref: ADR-0051.R8 |
| ADR-0051.R8.N1 | ref: ADR-0051.R8.N1 |
| ADR-0051.R9.N4 | ref: ADR-0051.R9.N4 |
| ADR-0054.R8 | ref: ADR-0054.R8 |
| ADR-0054.R8.N1 | ref: ADR-0054.R8.N1 |
| ADR-0057.R1 | ref: ADR-0057.R1 |
| ADR-0057.R1.N1 | ref: ADR-0057.R1.N1 |
| ADR-0057.R5 | ref: ADR-0057.R5 |
| ADR-0057.R20 | R227, R231-R234, R236 |
| ADR-0057.R20.N1 | R228, R231, R232, R233, R235, R236 |
| ADR-0057.R21 | ref: ADR-0057.R21 |
| ADR-0057.R21.N1 | ref: ADR-0057.R21.N1 |
| ADR-0057.R35 | ref: ADR-0057.R35 |
| ADR-0058.R8 | ref: ADR-0058.R8 |
| ADR-0058.R8.N1 | ref: ADR-0058.R8.N1 |
| ADR-0058.R9 | ref: ADR-0058.R9 |
| ADR-0058.R9.N1 | ref: ADR-0058.R9.N1 |
| ADR-0058.R28 | ref: ADR-0058.R28 |
| ADR-0059.R2 | ref: ADR-0059.R2 |
| ADR-0059.R21.N1 | ref: ADR-0059.R21.N1 |
| ADR-0062.R22 | ref: ADR-0062.R22 |
| ADR-0063.R11 | ref: ADR-0063.R11 |
| ADR-0063.R12 | ref: ADR-0063.R12 |
| ADR-0063.R14 | R231-R235, R237 |
| ADR-0063.R16 | R238-R240 |
| ADR-0063.R16.N1 | R240 |
| ADR-0063.R18 | R228-R230 |
| ADR-0065.R11 | R252, R253, R255, R256 |
| ADR-0065.R11.N1 | R251, R254, R255 |
| ADR-0065.R22 | ref: ADR-0065.R22 |
| ADR-0073.R1.N2 | ref: ADR-0073.R1.N2 |
| ADR-0077.R13 | ref: ADR-0077.R13 |
| ADR-0077.R13.N1 | ref: ADR-0077.R13.N1 |
| ADR-0078.R3 | ref: ADR-0078.R3 |
| ADR-0078.R5 | R241-R244 |
| ADR-0078.R6 | R245-R251, R253, R254 |
| ADR-0078.R7 | R202, R203, R208-R213 |
| ADR-0078.R7.N1 | R212 |
| ADR-0078.R7.N2 | R213 |
| ADR-0078.R11 | ref: ADR-0078.R11 |
| ADR-0078.R14 | R257 |
| ADR-0078.R15 | ref: ADR-0078.R15 |
