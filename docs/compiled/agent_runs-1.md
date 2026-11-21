Module: agent_runs    Chunk: 1 of 2    Source ADRs: ADR-0029, ADR-0050
Build step(s): 4    Generated from index: 30d5706    Compiled by: Claude Fable 5.2, 2026-11-21

# `agent_runs` compiled spec, chunk 1: module boundaries, agent types, modes, run records, limits, run taint

## Purpose

`agent_runs` is layer 2 (ADR-0022.R2). It owns the agent type, setting, run, step, budget usage, promotion evidence and data-processing permission tables and the contract functions that write them (R2). It holds no gateway, runtime, workflow, command handler or resolver: those are law of `agents` (layer 5), and the views are law of `query` (R3, R5). This chunk states the module boundaries, agent types and their versions, the company setting and its modes, the run and step records, the limits, run taint and the tainted read scope. Reservation, the daily budget rows, the stop rules and the data-processing permission are in chunk 2.

## Entities and tables

DDL: `docs/design/DS-05-platform.sql`. Named here without a row, because the rules that define them are in chunk 2: `agent_budget_usage`, `data_processing_permission`.

| Table | Meaning | Key | Parent | Owner |
| --- | --- | --- | --- | --- |
| `agent_type` | One agent type, installation data written at startup (R11) | `id`; `code` unique | none | `agent_runs` |
| `agent_type_version` | One immutable version of an agent type with its declaration and hashes (R11) | `id`; (`agent_type_code`, `version`) unique | `agent_type` | `agent_runs` |
| `agent_type_setting` | A company's mode, workflow owner and promotion for one agent type (R20) | `id`; (`company_id`, `agent_type_code`) unique | `company`, `agent_type` | `agent_runs` |
| `agent_promotion_evidence` | Immutable evidence of one promotion, computed once (R27) | `id`; (`company_id`, `id`) | `company`, `agent_type` | `agent_runs` |
| `agent_run` | One run of an agent type version for a company (R30) | `id`; (`company_id`, `id`) | `company`, `agent_type_version` | `agent_runs` |
| `agent_run_step` | One request, response or result row of an LLM call or tool call of a run, append-only (R32) | `id` | `agent_run` | `agent_runs` |

Reads: `work_item` (`work`); `user_account`, `company`, `partner`, `attachment`, `setting_value`, `audit_record`, `document`, `interaction_summary`, `assist_request`, `analysis_question`, `analysis_example`, `production_order`, `production_version`, `document_extraction`.

## Commands and queries

The commands and queries below are registered by `agents` (R3); they are listed because rules of this chunk state them. Authorization leaves are those of `authorization-areas.csv`: `agent` (module `agents`: agent type settings, promotion evidence, agent run queries) and `agent_run_bodies` (module `agent_runs`).

| Name | Actor and authorization | Input | Effect | Events | Error codes |
| --- | --- | --- | --- | --- | --- |
| `UpdateAgentTypeSetting` | a person; `full` on leaf `agent`; on no agent tool list; `assisted` and `active` only from the execution of an approved change proposal that another person approves; lowering is direct, by one person | agent type, mode, `workflow_owner_id`, for a promotion the evidence row (for `active` one per document type) | Changes `agent_type_setting`; effect class `master_data_change`, change-tracked, `is_proposal_bound`; to `active` records `active_document_types` (R24, R25; ADR-0065.R11) | not stated | `proposal_required`, `approver_is_submitter`, `workflow_owner_not_permitted`, `promotion_evidence_stale`, `agent_mode_not_declared`, `validation_failed` (mode `shadow` in Phase 1, or any mode except `off` for a type without a Phase 1 workflow; ADR-0078.R5), `shadow_evidence_insufficient` (to `active`; ADR-0065.R11) |
| `CreateAgentPromotionEvidence` | a person; leaf `agent`, level not stated | agent type, date range, target mode, document type | Writes one immutable `agent_promotion_evidence` row; effect class `other`; in Phase 1 from the stored evaluation result, for `active` from `GetAgentDraftAcceptance` (R27; ADR-0078.R6) | not stated | none stated |
| `GetAgentTypeSetting` | query; leaf `agent`, level not stated | agent type | Returns the stored mode, the effective mode and the reason they differ (R29) | none | none stated |
| `ListAgentRun` | query, generated permission; leaf `agent` at `read` (ADR-0054.R8); on no agent tool list (`INV-214`) | filter `work_item_id` (ADR-0078.R14) | Lists runs (R36) | none | none stated |
| `GetAgentRun` | query, generated permission; leaf `agent` at `read`; bodies need `read_agent_run_bodies` (`full` on leaf `agent_run_bodies`); on no agent tool list | a run | Returns a run with its steps, paged, with tool name, plan hash and audit record (R36; ADR-0078.R14) | none | none stated |

Contract functions of `agent_runs`, not registered commands, called by the layer-5 handlers of `agents`: `create_run`, `complete_run`, `cancel_run`, `write_agent_type_setting`, `write_promotion_evidence`, `mark_run_tainted`, `reserve_budget`, `settle_budget`, `record_run_step`, `get_run_context`, and the contract function of `data_processing_permission` (R2).

Named by rules of this chunk and stated elsewhere: `StartAgentRun`, `CompleteAgentRun`, `CancelAgentRun` (ADR-0050.R15, ADR-0050.R17); `GetAgentShadowEvaluation`, `GetAgentDraftAcceptance`, the jobs `RunAgentQualityCheck` and `RunAnalysisEvaluation` (`agents`); `ExportCompanyData`, `EraseDataSubject`, `GetOutboundContentCheck`.

Error codes bound to no command of the table: `shadow_evidence_insufficient` (creating the promotion proposal, R27), `setting_out_of_bounds` (a company value above its maximum, R42), `outbound_content_out_of_scope` (the outgoing-message gate of `crm`, R55).

## Rules

### Overview and module boundaries

R1. Each run is an `agent_run` in layer 2 `agent_runs`, and each LLM call and tool call is an `agent_run_step`. Together they hold the agent type and version, template versions, models, inputs as references, tool calls, outputs, tokens, cost, duration, taint and outcome. Telemetry keeps to the allow-lists of ADR-0038. The rest of the design is law of `agents` and `query` and is given here only as the frame:
- Every LLM call goes through one gateway in layer 5 `agents` with one method, `complete`, which also does structured output against a JSON Schema and tool calls; provider adapters sit behind it. In Phase 1 an installation uses one provider for all seats, the cloud provider of ADR-0002; a local adapter is designed but not enabled until the author decides. No other module imports a provider library.
- The gateway renders every prompt from a versioned template and typed context items, so it knows the data label of every value it sends. The company's routing switch removes personal values before sending, every personal value sent is logged, and secrets never reach a prompt.
- Each run has limits on calls, tokens, cost, rows and time, and each company has daily limits. The runtime reserves the worst case before every call; a run that would exceed a limit stops with an outcome and a work item and never loops.
- A run whose subject is outside content starts tainted; any other run becomes tainted when the dispatcher returns untrusted data to it, and the taint is committed before the data is returned. A tainted run reads only its scope (its partner, its import batch or its subject), its own drafts and reference data; nothing outside that scope, even read earlier, may enter its prompts or drafts; it runs only commands registered `is_draft_only`.
- An agent type version declares a fixed tool list of registered queries and commands, with tool definitions generated from the registry, as for MCP. LLM steps get read tools only; workflow code runs commands after a deterministic check. No tool list holds a `human_only`, posting or `outbound_send` command, or a `Submit`, `Post` or `Issue`.
- Every LLM step has a pydantic output schema. An invalid output gets at most two retries with the validation errors, then the run stops with a work item. Deterministic code checks every valid output before use.
- Recorded runs can be replayed with their recorded LLM outputs, deterministically, or re-run against another model or prompt for comparison. Each workflow has a golden evaluation set from the synthetic dataset.
- Agents and reports read through semantic views in schema `query`, served by the read-only role `nativeflows_readonly` with short timeouts, pagination and row limits. The views mask field classes, apply record scope and omit `is_untrusted` columns unless asked. Management reporting reads views by system account. Views are exposed as registered queries and described as MCP resources. Audit data is never on an agent's tool list.
Source: ADR-0050.D0

R2. `agent_runs` (layer 2) owns the tables `agent_type`, `agent_type_version`, `agent_type_setting`, `agent_run`, `agent_run_step`, `agent_budget_usage`, `agent_promotion_evidence` and `data_processing_permission`, and the contract functions `create_run`, `complete_run`, `cancel_run`, `write_agent_type_setting`, `write_promotion_evidence`, `mark_run_tainted`, `reserve_budget`, `settle_budget`, `record_run_step` and `get_run_context` and the contract function of `data_processing_permission`, which the layer-5 handlers of `agents` call (ADR-0022.R2; ADR-0027.R1).
Source: ADR-0050.R1, .N1

R3. `agents` (layer 5) owns the gateway and its adapters, the runtime, the workflows of ADR-0051, prompt templates, output schemas, tool definition generation and the replay adapter; the commands `StartAgentRun`, `CompleteAgentRun`, `CancelAgentRun`, `UpdateAgentTypeSetting`, `SetDataProcessingPermission` and `EndDataProcessingPermission`; the scope resolvers; `GetAgentShadowEvaluation` with the workflow comparators; `RunAgentQualityCheck`; the agent types `document_reader` and `product_engineering` (ADR-0057.R1, ADR-0057.R11, ADR-0057.R20; ADR-0062); and the `analysis` workflow (ADR-0060.R1).
Source: ADR-0050.R1, .N1, .N2

R4. `query` (layer 5) owns schema `query`: the views, their declarations, the query builder, the `List<View>` and `Get<View>` queries and list export; the analysis catalog, validator, compiler and executor, the analysis queries and the tables of DS-33-analysis.sql (ADR-0060.R1).
Source: ADR-0050.R1, .N2

R5. Imports and layers:
- `agents` imports `registry` (dispatch) and the `agent_runs` and `work` contracts. Its command handlers (scope resolvers, shadow comparators) may also import the contracts of the layer 3 and 4 modules whose subjects its agent types declare (`crm`, `purchasing`, `cash`, `planning`, `sales`, `master_data`). Workflows reach data only through registered queries and commands, and nothing in `agents` imports `query` or `imports`, its layer-5 peers.
- `agent_runs` holds the tables and the contract functions only. Resolvers, comparators and evaluations read layer 3 to 5 data, so they live in `agents`, and the bank auto-post evidence lives in `cash` (ADR-0051.R18).
- `query` imports `db`, `registry`, `agent_runs` (for taint) and the `work` contract, to raise its work item kinds. `registry` imports the `agent_runs` contract for credentials, tool lists and taint. `agent_runs` imports `work` only.
- There is no agent framework (ADR-0002): workflows are plain code that calls the gateway and the dispatcher.
Source: ADR-0050.R1, .N2

### Agent types and versions

R10. Agent types are code, versioned as one artifact. Each workflow module `nativeflows.agents.workflows.<agent_type>` declares:
- `code` and `version` (semver), and the ordered steps;
- the tool list (ADR-0050.R29), which is also its declared permissions: one set, which ADR-0017.R11 calls the declared permissions, so the intersection of ADR-0050.R31 is the tool list with the human's rights (ADR-0054.R16);
- the work item kinds it may claim (ADR-0042.R10), each with `wake_up` (R14), and optionally `configurable_triggers` (event type, subject table);
- `scope_kind` (`partner`, `import_batch`, `subject`) with its scope resolver and the subject tables it accepts (ADR-0050.R15), and `may_read_untrusted`;
- `field_classes` (default none): a run sees a `cost` or `margin` field only when both its agent type and its human have the class. A version declares no record scope; that comes from the human alone and is narrowed by the tainted scope;
- the seat of each LLM step, its prompt templates and output schemas with their versions;
- its budget maximums (R40) and its evaluation suite with threshold (ADR-0050.R39).
Source: ADR-0050.R12, .N1, .N2

R11. At startup the registry writes `agent_type` (`code`, `name`, `is_active`) and one immutable `agent_type_version` row per version, like the generated catalogs; nobody edits them. An `agent_type_version` row holds `agent_type_code`, `version`, `content_hash`, `behavior_hash` (the content hash without budget maximums), `declaration` (the declared elements of R10 as data) and `field_classes`, which may hold only `cost` and `margin`.
Source: ADR-0050.R12, .N1

R12. Changing any declared element, template or schema changes the content hash. CI fails when the hash changes and the version does not, and a new version needs a passing evaluation (ADR-0050.R40).
Source: ADR-0050.R12

R13. `agent_type` codes are `snake_case` nouns of the workflow (ADR-0004), for example `customer_onboarding`, `quotation`, `bank_matching`, `purchase_invoice`, `planning`, `data_migration` (ADR-0051). The Phase 1 types are `assistant`, `analysis`, `bank_matching`, `purchase_invoice`, `document_reader` and `planning` (ADR-0078.R1). Later declared types:
- `analysis`: scope kind `subject` on `analysis_question`, or on `analysis_example` for evaluation runs; `may_read_untrusted: false`; field classes `cost` and `margin`. It also declares the analysis catalog hash it was evaluated with, so a catalog change is a new version (ADR-0060.R20, ADR-0060.R25).
- `production`: scope `subject` on `production_order` or `production_version`, `may_read_untrusted: false`.
- `production_capture`: scope `subject` on one `production_order` resolved from a `document_extraction`, tainted at start.
- `production_variance`: scope `subject` on `analysis_question` or `production_order`, field class `cost`.
- Each of the `production` types has its leaf `agent_<agent_type>` (ADR-0064.R1).
- `auto_post_advisor`, `customer_onboarding`, `quotation`, `data_migration`, `product_engineering` and the `production` types are Phase 2 types: registered with mode `off` and no workflow code in Phase 1 (ADR-0078.R2).
Source: ADR-0050.R12, .N3, .N5, .N6

R14. Each claimable kind carries `wake_up`: `always`, or `configurable`. A `configurable` kind takes the company setting `agents.<agent_type>.wake_up_mode.<kind>` (`always`, the default, `by_rule`, `off`); under `by_rule` the agent is started only by a company's automation rule with action `start_agent` (ADR-0058.R7, ADR-0063.R11). The Phase 1 `purchase_invoice` declaration declares `supplier_invoice_received` `configurable`, default `always`; every other kind of the Phase 1 types stays `always`. The quotation agent's `inbound_message_matched` is declared `configurable` in its next version. A kind is declared by at most one agent type, and `check` refuses a second declaration (ADR-0078.R1, ADR-0078.R12).
Source: ADR-0050.R12, .N2, .N4, .N6

### Company setting and modes

R20. `agent_type_setting` is company data, change-tracked, one row per company and agent type: `agent_type_code`, `mode` (`off`, `shadow`, `assisted`, `active`; default `off` for every company), `workflow_owner_id` (the human whom runs from events and schedules act for, ADR-0017.R12; required unless `off`), `promoted_version` with `promoted_seat_models` (the agent type version and the (seat, model) pairs the evidence covered, set when the mode moves to `assisted`), and `active_document_types` (set in mode `active` only, naming at least one document type). The row holds no budget value.
Source: ADR-0050.R14, .N4, .N5, .N8, ADR-0055.R7

R21. Modes:
- `off`: no runs.
- `shadow` (Phase 2): runs execute every command in simulate mode only, so nothing persists except their run records and denials; their would-be outputs are recorded for comparison (ADR-0050.R41). Shadow runs bind their work item without claiming it, so people work on it as usual, and the dispatcher skips the claim check for them because they only simulate.
- `assisted`: runs create drafts and change proposals.
- `active`: `assisted`, and in addition the type's drafts of the document types named at promotion may pass the auto-post gateway as tainted drafts (ADR-0065.R11).
- There is no mode in which an agent posts: the agent still only drafts (ADR-0043.R9, floor 4).
- Phase 1 modes are `off`, `assisted`, and `active` only as the gateway uses it. Live agent shadow returns in Phase 2, and `demote_to_shadow` acts as `pause_new_runs` until then (ADR-0078.R5, ADR-0078.R6).
Source: ADR-0050.R14, .N5, .N6, ADR-0055.R7

R22. Effective mode. The stored mode is the person's choice, and no command changes it on its own. The runtime computes the effective mode at each start from the behavior hash: the current version's content hash without budget maximums. No Phase 1 agent type declares a parameter set, so in Phase 1 the behavior hash has no per-company part and constants are part of the version (ADR-0078.R6). Phase 2: an agent type version that declares its constants as a tunable parameter set includes the current version's `parameters_hash` in its behavior hash, so a promoted parameter set changes it (ADR-0059.R7, ADR-0059.R12). Budget values stay outside the behavior hash, so a budget change leaves the effective mode unaffected. An `assisted` type whose behavior hash differs from that of `promoted_version`, or whose seat models are not all in `promoted_seat_models`, runs with a lower effective mode until a person promotes it again: `off` in Phase 1 (R23); Phase 2, when live agent shadow returns: `shadow` (ADR-0078.R6).
Source: ADR-0050.R14, .N2, .N4, .N6, ADR-0055.R7

R23. Effective mode in Phase 1 (ADR-0078.R5, ADR-0078.R6):
- A behavior hash without a passing evaluation result runs as `off`, with the same `agent_mode_degraded` item (R29).
- The passing results of a release live in its evaluation manifest, one row per agent type, behavior hash, seat and model.
- A company already `assisted` stays `assisted` across a change of the hash that the manifest shows as passing; the runtime then updates `promoted_version` and `promoted_seat_models` as `system`, with an audit record. Otherwise those fields change only by an approved proposal.
- `document_reader` is the one exception: it returns to `assisted` in a company only when the replay of that company's golden set has passed again (ADR-0057.R13).
- `active` does not carry over a change of the hash: the type counts as `assisted` for the gateway until it is promoted again. It also counts as `assisted` for the gateway while an `agent_quality_below_threshold` item is open.
Source: ADR-0050.R14, .N5, .N6, ADR-0055.R7

R24. `UpdateAgentTypeSetting` has effect class `master_data_change`, is change-tracked and `is_proposal_bound`, is on no agent tool list (ADR-0050.R30) and needs `full` on the leaf `agent` (a declared minimum level; `edit` does not give it). The leaf `agent` belongs to module `agents`, and each agent type has its own leaf `agent_<agent_type>` below it for `start_agent:<agent_type>` (ADR-0054.R24).
- A person may lower the mode or change other fields directly.
- A change whose resulting `workflow_owner_id` does not hold `start_agent:<agent_type>` in the company is refused with `workflow_owner_not_permitted`.
- A change that sets `assisted` is accepted only from the execution of an approved change proposal (ADR-0029.R3); otherwise it returns `proposal_required`.
- The person who submits the proposal vouches for its evidence, and a person other than the submitter approves it; an approval by the submitter returns `approver_is_submitter`, also in the small-company mode. Writers are excluded from approving by ADR-0055.R7, condition 5.
- A budget change is not an `UpdateAgentTypeSetting` change.
Source: ADR-0050.R14, .N1, .N4, ADR-0055.R7

R25. Setting `active` is a proposal that another person approves, from `assisted` at the same behavior hash and seat models (ADR-0065.R11). The version declares `auto_post_document_types`, otherwise `agent_mode_not_declared`. The proposal names per document type an `agent_promotion_evidence` row with target mode `active` from `GetAgentDraftAcceptance`: at least ceil(3 / `auto_post.max_error_rate`) drafts over at least two calendar months, at least (1 - rate) posted unchanged, none to another partner. `agent_type_setting.active_document_types` records the types. Lowering is direct.
Source: ADR-0050.R14, .N5, ADR-0055.R7

R26. Promotion evidence by kind of agent type:
- Promotion to `assisted` in Phase 1 uses the offline evaluation set run with the real provider per pair of seat and model, and the replay of recorded responses in CI (ADR-0050.R39, ADR-0050.R40). Promotion to `active` uses the in-use draft acceptance of R25.
- `analysis` keeps its offline evaluation exception: the daily job `RunAnalysisEvaluation` runs it on the company's verified examples, acting for each example's releaser, and its promotion evidence is the version's CI evaluation report and, from 30 verified examples, that evaluation (ADR-0060.R25). In Phase 1 the daily evaluation is its evaluation in use, and a version without a passing CI evaluation is `off` (ADR-0078.R6).
- The assistant has no shadow comparison. Its promotion evidence is the stored result of its evaluation set (ADR-0077.R13), which `CreateAgentPromotionEvidence` records; at effective mode `off` the assistant starts no run and answers nobody (ADR-0078.R6).
- This ladder is the pattern that ADR-0059.R12 generalizes to every L1 and L2 artifact.
- Phase 2, with live agent shadow: `analysis` is a stated exception to the shadow comparison, in `shadow` it answers nobody and its daily evaluation is its shadow evaluation; for data migration, a Phase 2 agent type (ADR-0078.R2), the evidence comes from an attached rehearsal report (ADR-0051.R28).
Source: ADR-0050.R14, .N2, .N3, .N6, .N7, ADR-0055.R7

R27. Frozen evidence. `CreateAgentPromotionEvidence` (module `agents`, effect class `other`, a person's command) computes the evidence once, from the sources of R26: in Phase 1 from the stored evaluation result instead of `GetAgentShadowEvaluation`, which returns with live shadow in Phase 2, and for target mode `active` from `GetAgentDraftAcceptance` (ADR-0078.R6, ADR-0065.R11). It writes an immutable `agent_promotion_evidence` row (owned by `agent_runs`): agent type, date range (`start_date`, `end_date`), the `behavior_hash` and `seat_models` it covered, the `figures`, the `thresholds` applied and `is_sufficient`; the row also holds `target_mode` (`assisted`, `active`), `document_type` (set exactly when the target mode is `active`), `attachment_id` (the data migration rehearsal report) and `created_by_user_id`. The proposal's `UpdateAgentTypeSetting` payload names that row. Creating the proposal refuses evidence that is not sufficient (`shadow_evidence_insufficient`). Executing it only checks that the agent type's current behavior hash and seat models still equal the row's, and fails with `promotion_evidence_stale` otherwise; it never re-reads live figures, so the plan hash stays stable between simulation, approval and execution.
Source: ADR-0050.R14, .N5, ADR-0055.R7

R28. No budget value has scope `agent_type` in Phase 1: the per-type keys are removed (ADR-0078.R7). An agent type's per-run ceilings are its declaration's; the assistant's cost per run is the company setting `assist.max_cost_per_run`.
Source: ADR-0050.R14, .N4, .N8, ADR-0055.R7

R29. Visible drops. `GetAgentTypeSetting` returns the stored mode, the effective mode and the reason they differ (`version_changed`, `seat_model_changed`). When the effective mode first differs from the stored mode for a company and agent type, `agents` raises one work item `agent_mode_degraded` (owner `company_owner`, key the agent type within the company, due `days:1`). It is checked at every `StartAgentRun` and by the daily `RunAgentQualityCheck`, and it resolves when the agent type is promoted again or its mode is lowered.
Source: ADR-0050.R14, .N6, ADR-0055.R7

### Run records

R30. `agent_run` is company data, not partitioned, and never deleted while a version or event refers to it. Columns:
- Identity: `id`, `company_id`, `agent_type_code`, `agent_type_version`, `seatmap_hash`, `mode` (`live`, `shadow`, `replay`, `evaluation`), `replay_of_run_id`.
- Trigger and actor: `trigger_kind` (`work_item`, `person`, `schedule`), `work_item_id`, `subject_table`, `subject_id`, `started_by_kind` (`human`, `system`) and `started_by_id`, `on_behalf_of_id`.
- Scope and taint: `scope_kind`, `scope_partner_id`, `scope_import_batch_id`; `tainted_at`, `taint_source_kind` (`work_item`, `outside_subject`, `untrusted_field`, `tainted_row`, `outside_attachment`), `taint_source_table`, `taint_source_id`.
- Budget: `budget` (the limits in force at start, as JSON; the limits keep their names, `max_input_tokens` and the like), and the totals `llm_call_count`, `tool_call_count`, `input_token_count`, `output_token_count`, `cache_token_count`, `row_read_count`, `denial_count`, `cost_amount`, `cost_currency`, with `reserved_amount` for open reservations (ADR-0050.R23).
- Timing and result: `state` (`queued`, `running`, `completed`, `stopped`, `canceled`), `outcome`, `started_at`, `ended_at`, `duration_ms`, `input_refs` and `output_refs` (typed references: table, ID, role), `trace_id`, `recorded_at`.
Source: ADR-0050.R18, .N1

R31. `agent_run_step` is company data, append-only, partitioned by month on `id` (ADR-0002, "agent run logs"). Columns:
- Every row: `id`, `company_id`, `agent_run_id`, `ordinal`, `step_code`, `kind` (`llm_request`, `llm_response`, `tool_request`, `tool_result`), `request_step_id` (on a response or result row, its request row), `attempt`, `recorded_at`, `duration_ms`.
- LLM request and response rows: `seat`, `provider`, `model`, `template_code`, `template_version`, `template_hash`, `output_schema_version`, `request_hash`, `reserved_amount` and `request_body` on the request row and `response_body` on the response row (as sent and received, after redaction), `context_refs` (the source row of every context item), `validation_errors`, the token counts `input_token_count`, `output_token_count`, `cache_read_token_count` and `cache_write_token_count`, `cost_amount`, `personal_fields_sent` and `redacted_fields` (table, field, row ID lists), `personal_subject_refs` (the data subjects whose values were sent).
- Tool request and result rows: `tool_name`, `schema_version`, `mode` (`simulate`, `execute`, or `query`), `request_refs` (the source row of every reference in the input), `result_refs` (the table and ID of every row returned or written), `error_code`, `plan_hash`, `audit_record_id`.
- `erased_at` records when erasure blanked the bodies (R37); the column is interim, not stated in ADR-0050.
- For every extraction field a step receives, `context_refs` also records the trust the dispatcher served and the rule run number it used, and whether the raw text or evidence was served; `INV-642` checks those values (ADR-0057.R17).
Source: ADR-0050.R19, .N1, ADR-0050.R18.N1

R32. Platform records. Run rows after start, steps, taint marks and budget usage are written by the runtime through the `agent_runs` contract in their own short transactions, like idempotency and denial records (ADR-0008.R16; ADR-0038.R5). They are not commands, and no client can write them. Starting, completing and cancelling a run are commands.
Source: ADR-0050.R19

R33. An `agent_run_step` row is never updated: a request row is committed before its call and the response or result row after it.
Source: ADR-0050.R19

R34. Bodies are stored in the database only, never sent to telemetry (spec 17).
Source: ADR-0050.R19

R35. Retention. `agent_run_step` partitions older than the installation setting `agents.run_step_retention_days` (a deployment value, default 400, flagged for the author) are dropped. The `agent_run` row stays.
Source: ADR-0050.R19, .N2

R36. `ListAgentRun` and `GetAgentRun` (with its steps, paged) each have their generated permission and are on no agent tool list (ADR-0050.R30). Request and response bodies are returned only to holders of the capability `read_agent_run_bodies` (ADR-0017.R4); access to bodies is by that capability alone. `read_agent_run_bodies` is `full` on its own authorization leaf `agent_run_bodies`, which every role template except `owner` sets to `none` (ADR-0054.R8, ADR-0054.R11).
Source: ADR-0050.R20, .N1

R37. `ExportCompanyData` includes `agent_run` and `agent_run_step` (ADR-0044.R17). `EraseDataSubject` (ADR-0019.R10) blanks `request_body` and `response_body` of every step whose `personal_subject_refs` or `personal_fields_sent` names the subject or one of its rows, keeping the rows and counts.
Source: ADR-0050.R20

### Limits

R40. Limits per run are declared by the agent type version as maximums (values in ADR-0051): `max_llm_calls`, `max_tool_calls`, `max_input_tokens`, `max_output_tokens`, `max_cost`, `max_seconds`, `max_rows_read`. Phase 1 has the company's daily cap (with the installation maximum and the internal reserve) and the per-run ceilings of the agent type version's declaration, and no other tier (ADR-0078.R7), so the per-type daily limits `daily_max_cost` and `daily_max_runs` (per company, agent type and business date) bind no run:
- The company setting keys `agents.<agent_type>.daily_max_cost`, `agents.<agent_type>.daily_max_runs` and `agents.<agent_type>.run_max_*` are not in `settings.csv`.
- Reservation, stop and `agent_budget_exhausted` stay.
- The per-type usage rows of `agent_budget_usage` keep counting cost and runs, with `limit_amount` equal to the company's cap and `run_limit_count` null, so they never bind before the company row; each reservation refreshes that `limit_amount` to the company cap in force, so a raised cap never leaves a lower limit on it.
- The reservation checks the company row, the installation row and, for agent types that read outside content, the `company_outside_content` row, and no per-type limit.
Source: ADR-0050.R22, .N2, .N3

R41. The customer sets the caps (author's direction, 2026-11-16). Every cost limit is a definition of the settings registry (ADR-0063.R1) whose `source` names ADR-0050 rule 22. Installation maxima are set at deployment by the operator and recorded as `setting_value` rows naming the operator account, a raise approved by a second operator account (ADR-0063.R2):
- `agents.installation_daily_max_cost` (default USD 200), per installation and business date; it changes only through installation configuration, never by a company setting or a command, and every change is logged with the operator who made it;
- the installation value of `agents.company_daily_max_cost`, which is the maximum of every company's cap.
- When the deployment names no installation value of `agents.company_daily_max_cost`, the startup step records one equal to `agents.installation_daily_max_cost` (a `setting_value` row of scope `installation`, the operator account as changer), and records it again whenever that value changes, so the generic trigger and `get_setting` apply the maximum with no special case.
Source: ADR-0050.R22, .N2, .N4

R42. The company value `agents.company_daily_max_cost` (default USD 50) is the company's cap per business date, within the installation maximum. A company cap above the installation maximum returns `setting_out_of_bounds`. The version declares every per-run value as a ceiling for safety, and the declared values of ADR-0051.R9 and of later agent types stay the ceilings of the per-run values.
Source: ADR-0050.R22, .N2, .N3

R43. The reserve pool. `agents.internal_reserve_share` (company, default 0.40, bounds 0 to 0.9) is the share of the company's daily cap that only internal agent types may use. A version is internal when it declares `may_read_untrusted: false` and accepts no subject that is outside content, so its runs are never tainted by design. Agent types that read outside content share the remainder, (1 − share) × the company cap; internal agent types may use the whole cap. The Phase 1 internal types that draw on the share are `analysis` and `planning`; `production` is a Phase 2 type (ADR-0078.R7). The check is in ADR-0050.R23.
Source: ADR-0050.R22, .N2, .N3, .N5

R44. Change path (ADR-0063.R3). Lowering a cap or limit, or raising the reserve share, is immediate, by one person holding `edit` on the leaf `agent`. Raising a cap or limit, or lowering the reserve share, is a loosening: a change proposal approved by another person holding `agent` at `full`, logged in `setting_value`. As for every loosening, a one-person company cannot raise them.
Source: ADR-0050.R22, .N2

R45. Hard locks: the worst case is reserved before every call (ADR-0050.R23); a run that would exceed any cap or limit stops (ADR-0050.R24); no company value lies above the installation maximum, refused by the `setting_value` trigger and applied again at read time (ADR-0063.R1); no setting turns reservation off. Lowering reaches running runs: `agent_run.budget` keeps the per-run values in force at start, and each reservation checks the run against the lower of that snapshot and the values in force.
Source: ADR-0050.R22, .N2

R46. Every budget day is the company's business date (`clock.today`, ADR-0007.R15), the installation's daily row included: it is keyed by the business date of the company whose run reserves, so "per installation and day" means per business date.
Source: ADR-0050.R22, .N1

R47. Test runs keep ADR-0003.R6. Evaluation runs have their own cap (ADR-0050.R40).
Source: ADR-0050.R22

### Run taint and the tainted read scope

R50. Run taint:
- `is_untrusted` is a schema attribute separate from data labels (spec 17). It is set on fields filled from outside content: e-mail bodies, supplier e-invoice free text, bank statement texts and `interaction_summary` (ADR-0019.R20).
- A run becomes tainted when the query layer (DS-33) returns to it any of: an `is_untrusted` field; a row of an effectively tainted version; a work item created from a tainted event; or an attachment from outside content.
- DS-33 views omit `is_untrusted` fields unless they are asked for, so listing documents does not taint a run.
- Master data changed by an approved proposal is not tainted, because the human approval is the trust boundary.
- The dispatcher applies run taint to every query result returned to a run, and commits `agent_run.tainted_at` before it returns the data (ADR-0050.R25).
- Work items carry `is_tainted` as an OR over their raises (ADR-0042.R5).
Source: ADR-0029.R10, .N1

R51. Value trust, a reading of spec 03 rule 1, interim until the author answers (ADR-0057.R17):
- An extraction field's normalized value is not untrusted when it fits its type's closed shape and passed every rule of the extraction's latest rule run from a deterministic reader, or a person confirmed it and its shape passed.
- Its raw text and evidence are always untrusted.
- Free text, URLs, e-mails, phones, codes and units that resolve to no record, vision values before confirmation, and every field of an extraction with a failed or mismatched signature or with suspected hidden text are untrusted.
- Trust is computed when the field is read, never stored on it, and means that the value carries no instruction, not that it is true.
Source: ADR-0029.R10.N2

R52. The tainted read scope is the literal spec 03 rule 1, which names this rule as the tainted read scope: a tainted run reads only records scoped to its related partner. ADR-0050.R27 reads the literal rule as: scope rows, the run's work item, the drafts it or an earlier run of the same item wrote, and reference data (flagged). The scope is not widened (author's delegation, 2026-11-21; decided by the chief architect), and ADR-0050.R27 stays as written. A workflow that needs one more read for a tainted run (for example item candidates for matching) gets it only as a declared projection of a registered query (`tainted_projection`: closed shapes, internal names, row and call limits; ADR-0063.R16), added by an ADR note for that workflow. Declared projections of closed shapes (the first is `ListItemCandidate`) join the reference data of the literal scope; the company setting `agents.tainted_reference_reads` only narrows it back to the literal scope, so no setting widens the floor.
Source: ADR-0029.R14, .N2, .N5, .N6

R53. No policy, threshold or setting relaxes a hard floor of spec 03, with one exception, the author's decision of 2026-11-16: a tainted draft may be auto-posted when the company enables it for the document type and the deterministic checker passes (default off; ADR-0065.R10, ADR-0065.R12). The exception lets a checked draft post and widens no run's reads.
Source: ADR-0029.R14, .N3

R54. Runs on subjects that are outside content start tainted, and after taint no out-of-scope row may enter a prompt or a command input (ADR-0050.R15, ADR-0050.R25). The effects on the quotation and purchase invoice workflows are in ADR-0051.R10.
Source: ADR-0029.R14

R55. Outbound check. The outgoing-message gate (ADR-0019.R17, module `crm`) rejects a customer draft that refers to another partner's records, or carries `cost` or `margin` fields, with `outbound_content_out_of_scope`. It only tightens. It also runs in draft plans through `GetOutboundContentCheck` (ADR-0050.R36). For a generated file the check reads the attachment's `generated_kind`, `generated_audience` and `generated_subject_document_id`: only an external print of a document of the message's partner passes (ADR-0049.R29). The CRM's outbound checks, and `tainted_read_out_of_scope` for its timeline and duplicate queries outside the scope partner, are in ADR-0052.R16, ADR-0052.R18 and ADR-0052.R28.
Source: ADR-0029.R14, .N1

## Invariants

Statements are those of `invariants.csv`. Each row stands once in the module, in the chunk that states the rule its catalog source names first.

| Invariant | Name | Check point | Statement | Protects |
| --- | --- | --- | --- | --- |
| `INV-212` | `agent_spend_within_budget` | day | Every ended agent run's totals are within its budget snapshot and its reservations are zero; every `agent_budget_usage` row's spent plus reserved amount is within its limit. | R30, R40, R45; ADR-0050.R23 |
| `INV-215` | `tainted_reads_in_scope` | day | Every row reference in `result_refs`, `context_refs` and `request_refs` of a step recorded after its run's `tainted_at`, wherever the row was first read, is inside that run's tainted read scope: its scope rows, its work item and evidence, drafts of its work item and agent type, or reference data. Flagged: ADR-0050 rule 27, reading of the literal read scope. | R52; ADR-0050.R25, ADR-0050.R27, ADR-0063.R16 |

Named by rules of this chunk, with their rows elsewhere: `INV-642` (R31; a row of module `attachments`). The other invariants of the agent runtime stand in chunk 2.

## Settings

Rows of `settings.csv` whose source is a rule of this chunk; area `agents`.

| Key | Value type | Scopes | Core default | Bounds | Used by |
| --- | --- | --- | --- | --- | --- |
| `agents.company_daily_max_cost` | amount (USD) | installation; company | 50 | 0.. ; lower is tighter | R41, R42 |
| `agents.installation_daily_max_cost` | amount (USD) | installation (deployment) | 200 | 0.. ; lower is tighter | R41 |
| `agents.internal_reserve_share` | decimal | company | 0.40 | 0..0.9; higher is tighter | R43 |
| `agents.run_step_retention_days` | integer | installation (deployment) | 400 | 1.. | R35 |
| `agents.<agent_type>.wake_up_mode.<kind>` | enum | agent_type | `always` | `always`, `by_rule`, `off`; `off` is tightest | R14 |

Named by rules of this chunk, with their rows in chunk 2: `assist.max_cost_per_run` (R28), `agents.tainted_reference_reads` (R52).

Reads: `auto_post.max_error_rate` (`policy`; R25); `data_processing.policy` and `data_processing.never_send_fields` (ADR-0050.R9.N1, ADR-0050.R9.N2).

## Conflicts

CONFLICT ADR-0029.R14: ADR-0029.R14.N6 governs; the recommendation to the author to widen the read scope for quotations is decided and not restated (R52), and ADR-0029.R14.N3 gives the hard-floor sentence its exception (R53).
CONFLICT ADR-0029.R14.N3: the note governs the sentence "no policy, threshold or setting relax a hard floor"; R53 states it with the auto-post exception of ADR-0065.R10, and the open question on rewording spec 03 is closed by ADR-0029.R14.N5.
CONFLICT ADR-0029.R14.N5: ADR-0029.R14.N6 governs; the conflict the note records for the author is decided, the wider wording of decision item 2 is withdrawn (R52).
CONFLICT ADR-0029.R14.N6: the note turns the open recommendation into a decision; R52 states that the tainted read scope is not widened and that further reads come only as a `tainted_projection`.
CONFLICT ADR-0050.R12: ADR-0050.R12.N6 governs the set of Phase 1 agent types; the codes listed in the rule text stay only as examples of the naming rule (R13).
CONFLICT ADR-0050.R12.N2: ADR-0050.R12.N6 governs; `supplier_invoice_received` of `purchase_invoice` is declared `configurable`, so "keep every kind `always` until the author decides" is not restated (R14).
CONFLICT ADR-0050.R14: ADR-0055.R7 governs approval of one's own document, so "the interim of ADR-0043 rule 13" is not restated (R24); ADR-0050.R14.N5 adds the mode `active` (R20, R21); ADR-0050.R14.N6 governs the Phase 1 effective mode (R23); ADR-0050.R14.N8 with the DDL removes the lowered budget values from `agent_type_setting` (R20, R28); ADR-0078.R6 replaces `GetAgentShadowEvaluation` by the stored evaluation result as the source of promotion evidence in Phase 1 and makes the `shadow` drop of the effective mode the Phase 2 law (R22, R27); ADR-0078.R2 makes data migration a Phase 2 agent type, so its rehearsal evidence is stated as Phase 2 (R26).
CONFLICT ADR-0050.R14.N1: ADR-0055.R7 governs; `full` on the leaf `agent` is required, `edit` no longer gives the command, and `approver_is_submitter` stays (R24).
CONFLICT ADR-0050.R14.N2: ADR-0078.R6 governs: no Phase 1 agent type declares a parameter set, so the `parameters_hash` part of the behavior hash is Phase 2 (R22).
CONFLICT ADR-0050.R14.N3: ADR-0078.R6 governs: with no live shadow in Phase 1, the daily evaluation is the Phase 1 evaluation in use of `analysis`, and its answering nobody in `shadow` is Phase 2 (R26).
CONFLICT ADR-0050.R14.N7: ADR-0078.R6 governs: a behavior without a passing result drops to effective mode `off`, not `shadow`, in Phase 1, so the assistant starts no run at effective mode `off` (R26).
CONFLICT ADR-0050.R14.N4: ADR-0050.R14.N8 governs; the budget values left `agent_type_setting`, and no `setting_value` row of scope `agent_type` holds one in Phase 1 (R28).
CONFLICT ADR-0050.R14.N5: the note governs the sentence "so there is no further mode"; R21 states the mode `active` and that there is no mode in which an agent posts.
CONFLICT ADR-0050.R14.N6: the note governs Phase 1; a hash without a passing evaluation runs as `off`, not `shadow`, and the runtime may update `promoted_version` as `system` (R23).
CONFLICT ADR-0050.R18: ADR-0050.R18.N1 with the DDL governs the count column names; the DDL adds `reserved_amount` (ADR-0050.R23) and the values of `started_by_kind` (R30).
CONFLICT ADR-0050.R19: ADR-0050.R19.N2 governs the setting key `agents.run_step_retention_days`; the DDL adds the interim column `erased_at`, and ADR-0050.R18.N1 names the token count columns (R31, R35).
CONFLICT ADR-0050.R22: ADR-0050.R22.N2 governs; "Lowering only", the author's reserve on raising and the open question on the values are not restated (R41, R44). ADR-0050.R22.N3 and ADR-0078.R7 remove every per-type limit in Phase 1, the declared `daily_max_cost` and `daily_max_runs` included (R40). ADR-0050.R22.N1 governs the budget day; the DDL comment "the installation row uses the UTC day" on `agent_budget_usage` is not followed (R46).
CONFLICT ADR-0050.R22.N2: ADR-0050.R22.N3 governs the company values; the agent-type keys the note defined are removed from `settings.csv`, and the rest of the note stands (R40 to R45).

## Trace

| Source | Where |
| --- | --- |
| ADR-0017.R1 | ref: ADR-0017.R1 |
| ADR-0017.R4 | ref: ADR-0017.R4 |
| ADR-0017.R10.N1 | ref: ADR-0017.R10.N1 |
| ADR-0017.R11 | ref: ADR-0017.R11 |
| ADR-0017.R11.N1 | ref: ADR-0017.R11.N1 |
| ADR-0019.R10 | ref: ADR-0019.R10 |
| ADR-0019.R10.N1 | ref: ADR-0019.R10.N1 |
| ADR-0019.R10.N2 | ref: ADR-0019.R10.N2 |
| ADR-0029.R10 | R50 |
| ADR-0029.R10.N1 | R50 |
| ADR-0029.R10.N2 | R51 |
| ADR-0029.R14 | R52-R55 |
| ADR-0029.R14.N1 | R55 |
| ADR-0029.R14.N2 | R52 |
| ADR-0029.R14.N3 | R53 |
| ADR-0029.R14.N4 | not applicable: history of the rewording of spec 03 rule 1, whose result ADR-0029.R14.N5 states |
| ADR-0029.R14.N5 | R52 |
| ADR-0029.R14.N6 | R52 |
| ADR-0029.R16 | ref: ADR-0029.R16 |
| ADR-0029.R16.N1 | ref: ADR-0029.R16.N1 |
| ADR-0029.K.N1 | ref: ADR-0029.K.N1 |
| ADR-0030.R11 | ref: ADR-0030.R11 |
| ADR-0038.R11 | ref: ADR-0038.R11 |
| ADR-0042.R7.N3 | ref: ADR-0042.R7.N3 |
| ADR-0042.R9 | ref: ADR-0042.R9 |
| ADR-0042.R9.N1 | ref: ADR-0042.R9.N1 |
| ADR-0042.R11 | ref: ADR-0042.R11 |
| ADR-0050.D0 | R1 |
| ADR-0050.R1 | R2-R5 |
| ADR-0050.R1.N1 | R2, R3 |
| ADR-0050.R1.N2 | R3-R5 |
| ADR-0050.R5.N1 | ref: ADR-0050.R5.N1 |
| ADR-0050.R9.N1 | ref: ADR-0050.R9.N1 |
| ADR-0050.R9.N2 | ref: ADR-0050.R9.N2 |
| ADR-0050.R12 | R10-R14 |
| ADR-0050.R12.N1 | R10, R11 |
| ADR-0050.R12.N2 | R10, R14 |
| ADR-0050.R12.N3 | R13 |
| ADR-0050.R12.N4 | R14 |
| ADR-0050.R12.N5 | R13 |
| ADR-0050.R12.N6 | R13, R14 |
| ADR-0050.R13 | ref: ADR-0050.R13 |
| ADR-0050.R14 | R20-R29 |
| ADR-0050.R14.N1 | R24 |
| ADR-0050.R14.N2 | R22, R26 |
| ADR-0050.R14.N3 | R26 |
| ADR-0050.R14.N4 | R20, R22, R24, R28 |
| ADR-0050.R14.N5 | R20, R21, R23, R25, R27 |
| ADR-0050.R14.N6 | R21, R22, R23, R26, R29 |
| ADR-0050.R14.N7 | R26 |
| ADR-0050.R14.N8 | R20, R28 |
| ADR-0050.R15 | ref: ADR-0050.R15 |
| ADR-0050.R15.N2 | ref: ADR-0050.R15.N2 |
| ADR-0050.R16.N1 | ref: ADR-0050.R16.N1 |
| ADR-0050.R17 | ref: ADR-0050.R17 |
| ADR-0050.R17.N1 | ref: ADR-0050.R17.N1 |
| ADR-0050.R17.N2 | ref: ADR-0050.R17.N2 |
| ADR-0050.R18 | R30 |
| ADR-0050.R18.N1 | R30, R31 |
| ADR-0050.R19 | R31-R35 |
| ADR-0050.R19.N1 | R31 |
| ADR-0050.R19.N2 | R35 |
| ADR-0050.R20 | R36, R37 |
| ADR-0050.R20.N1 | R36 |
| ADR-0050.R21 | ref: ADR-0050.R21 |
| ADR-0050.R22 | R40-R47 |
| ADR-0050.R22.N1 | R46 |
| ADR-0050.R22.N2 | R40-R45 |
| ADR-0050.R22.N3 | R40, R42, R43 |
| ADR-0050.R22.N4 | R41 |
| ADR-0050.R22.N5 | R43 |
