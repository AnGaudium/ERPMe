Module: agents    Chunk: 1 of 8    Source ADRs: ADR-0050
Build step(s): 4    Generated from index: 30d5706    Compiled by: Claude Opus 5.5, 2026-11-21

# `agents` compiled spec, chunk 1: module boundary, gateway, data routing, agent types, modes, starting a run

## Purpose

`agents` is a layer-5 module (ADR-0022.R2): it owns the LLM gateway and its adapters, the runtime, the agent workflows, prompt templates, output schemas, tool definition generation and the replay adapter, and the commands that start, end and configure agent runs. It owns no run table: `agent_runs` (layer 2) holds the run tables and the contract functions `agents` calls. This chunk states the module boundary, the gateway, seats and providers, provider failures and cost, prompt rendering, labels and the routing switch, the processing log, minimization, agent type declarations, company modes and promotion, and `StartAgentRun`. Budgets, the run loop, taint, tools, checks, evaluation and the workflows are in the other chunks.

## Entities and tables

The table `assist_request` (`docs/design/DS-30-ui.sql`) is owned by `agents`; its row is in the chunk that states ADR-0077.R13. Rules of this chunk name it as a run subject (R87, R89).

Reads: `agent_type`, `agent_type_version`, `agent_type_setting`, `agent_run`, `agent_run_step`, `agent_promotion_evidence`, `data_processing_permission` (`agent_runs`); `personal_data_processing_log` (`audit`); `work_item` (`work`); `setting_value` (`registry`); `interaction` (`crm`); `bank_statement_line` (`cash`); `document_extraction` (`attachments`); `analysis_question`, `analysis_example` (`query`); `production_order`, `production_version` (`production`); `import_batch`, `import_row` (`imports`).

## Commands and queries

Authorization: the leaf `agent` (module `agents`, under `administration`) covers agent type settings (`UpdateAgentTypeSetting` at `full`), promotion evidence and agent run queries; `start_agent:<agent_type>` is on each agent type's own leaf below it (`agent_analysis`, `agent_assistant`, `agent_auto_post_advisor`, `agent_product_engineering`, `agent_production`, `agent_production_capture`, `agent_production_variance`); the leaf `data_processing` covers `SetDataProcessingPermission` (through an approved proposal) and `EndDataProcessingPermission` (at `full`).

| Name | Actor and authorization | Input | Effect | Events | Error codes |
| --- | --- | --- | --- | --- | --- |
| `StartAgentRun` | effect class `other`; the wake-up consumer `agent_wake_up` or a schedule (actor `system` on behalf of the human), or a person; the human acted for needs `start_agent:<agent_type>` (for `assistant`, the user's `start_agent:assistant` at `edit` on the leaf `agent_assistant`, ADR-0077.R13) | agent type; a `work_item_id`, or `subject_table` and `subject_id` (an `assist_request` for `assistant`) | Writes an `agent_run` in state `queued` through `agent_runs.contract.create_run`, claims the work item or an `agent_task` item, binds scope and taint (R80-R89) | `AgentRunStarted` | `agent_mode_off`, `agent_budget_exceeded`, `agent_kind_not_declared`, `agent_scope_unresolved`, `work_item_claimed` |
| `UpdateAgentTypeSetting` | a person; `full` on leaf `agent`; effect class `master_data_change`, change-tracked, `is_proposal_bound`; on no agent tool list | agent type, `mode`, `workflow_owner_id`, promotion fields naming an `agent_promotion_evidence` row; for mode `active`, one such row per document type | Writes `agent_type_setting`; for mode `active` records `active_document_types` (R70-R75; ADR-0065.R11) | not stated | `proposal_required`, `approver_is_submitter`, `workflow_owner_not_permitted`, `promotion_evidence_stale`, `agent_mode_not_declared`, `shadow_evidence_insufficient`, `validation_failed` (mode `shadow` in Phase 1, or a mode other than `off` for an agent type without a Phase 1 workflow; ADR-0078.R5) |
| `CreateAgentPromotionEvidence` | a person; effect class `other`; leaf `agent` | agent type, date range; for target mode `active`, a document type | Writes one immutable `agent_promotion_evidence` row from the stored evaluation result, or for target mode `active` from `GetAgentDraftAcceptance` (R76; ADR-0078.R6, ADR-0065.R11) | not stated | not stated |
| `GetAgentTypeSetting` | query; leaf `agent` | agent type | Stored mode, effective mode and the reason they differ (R78) | none | not stated |
| `GetAgentDraftAcceptance` | query; area not stated | agent type, document type, behavior hash and seat models | The type's drafts of that document type and how people posted them, for the evidence of mode `active` (R75; ADR-0065.R11) | none | not stated |

Named here, stated in other chunks: `CompleteAgentRun`, `CancelAgentRun` (ADR-0050.R17), `SetDataProcessingPermission`, `EndDataProcessingPermission` (ADR-0057.R20, ADR-0063.R14), `CreateAssistRequest` (`human_only`; ADR-0077.R13), `GetAgentBudgetStatus` (people-only query on no tool list; ADR-0077.R17), `GetAgentShadowEvaluation` (query, leaf `agent`; Phase 2, it feeds no Phase 1 promotion, R73; ADR-0050.R41).

Contract function, not a command: `agents.gateway.complete(request) -> response` (R10). Jobs: the daily `RunAgentQualityCheck` (R78) and the daily `RunAnalysisEvaluation` (R77). Gateway error codes bound to no named command: `llm_provider_unavailable` (R21, R23), `llm_routing_refused` (R42, R55), `data_processing_not_permitted` (R20). Run outcomes set here: `provider_unavailable` (R21), `routing_blocked` (R20, R44, R50).

## Rules

### Module boundary

R1. `agents` (layer 5) owns the gateway and its adapters, the runtime, the workflows of ADR-0051, prompt templates, output schemas, tool definition generation and the replay adapter; the commands `StartAgentRun`, `CompleteAgentRun`, `CancelAgentRun`, `UpdateAgentTypeSetting`, `SetDataProcessingPermission` and `EndDataProcessingPermission`; the scope resolvers; `GetAgentShadowEvaluation` with the workflow comparators; `RunAgentQualityCheck`; the agent types `document_reader` and `product_engineering` (ADR-0057.R1, ADR-0057.R11, ADR-0057.R20; ADR-0062); and the `analysis` workflow (ADR-0060.R1). `product_engineering` is not a Phase 1 agent type (R63).
Source: ADR-0050.R1, .N1, .N2

R2. `agent_runs` (layer 2) owns the tables `agent_type`, `agent_type_version`, `agent_type_setting`, `agent_run`, `agent_run_step`, `agent_budget_usage`, `agent_promotion_evidence` and `data_processing_permission`, and the contract functions `create_run`, `complete_run`, `cancel_run`, `write_agent_type_setting`, `write_promotion_evidence`, `mark_run_tainted`, `reserve_budget`, `settle_budget`, `record_run_step` and `get_run_context` and the contract function of `data_processing_permission`, which the layer-5 handlers of `agents` call (ADR-0022.R2; ADR-0027.R1).
Source: ADR-0050.R1, .N1

R3. `query` (layer 5) owns schema `query`: the views, their declarations, the query builder, the `List<View>` and `Get<View>` queries and list export; the analysis catalog, validator, compiler and executor, the analysis queries and the tables of DS-33-analysis.sql. It imports the `work` contract to raise its work item kinds.
Source: ADR-0050.R1, .N2

R4. Imports and layers:
- `agents` imports `registry` (dispatch) and the `agent_runs` and `work` contracts. Its command handlers (scope resolvers, comparators) may also import the contracts of the modules of layers 3 and 4 whose subjects its agent types declare (`crm`, `purchasing`, `cash`, `planning`, `sales`, `master_data`).
- Workflows reach data only through registered queries and commands, and nothing in `agents` imports `query` or `imports`, its layer-5 peers.
- `agent_runs` holds the tables and the contract functions only. Resolvers, comparators and evaluations read layer 3–5 data, so they live in `agents`, and the bank auto-post evidence lives in `cash` (ADR-0051.R18).
- `query` imports `db`, `registry` and `agent_runs` (for taint). `registry` imports the `agent_runs` contract for credentials, tool lists and taint. `agent_runs` imports `work` only.
- There is no agent framework (ADR-0002): workflows are plain code that calls the gateway and the dispatcher.
Source: ADR-0050.R1

### Gateway interface and adapters

R10. The gateway interface is one function, `agents.gateway.complete(request) -> response`. The request holds: `seat`; `template_code` and `template_version`; the context items (R31); optional `output_schema` (a JSON Schema generated from a pydantic model); optional `tools` (definitions generated from the registry, ADR-0050.R29); `reasoning_level` (`low`, `medium`, `high`, `very_high`, spec 17); `max_output_tokens`; `timeout_seconds`; the `agent_run_id` and step ordinal.
Source: ADR-0050.R2

R11. The response holds: `output` (the parsed object when a schema was given), `text`, `tool_calls` (name and arguments), `stop_reason` (`end`, `max_tokens`, `tool_use`, `refusal`), `usage` (input, output, cache-read and cache-write tokens), `cost_amount` with `cost_currency` (R25), `provider`, `model`, `latency_ms`, and `request_hash` (SHA-256 of the canonical rendered request, ADR-0050.R38).
Source: ADR-0050.R2

R12. Structured output and tool calls are modes of the same call. A request with `output_schema` uses the provider's structured output when the model's capability flag says so, else a tool-call shim with the same schema. The runtime always validates the response (ADR-0050.R35), whatever the provider promises.
Source: ADR-0050.R2

R13. Adapters:
- `anthropic`: the Anthropic SDK (ADR-0002). The reasoning level maps to effort (spec 17); temperature is not sent.
- `local`: an OpenAI-compatible HTTP endpoint run by the operator (vLLM, llama.cpp server or similar), called with `httpx`, which the Anthropic SDK already brings. Temperature from the seat applies. It is designed so that a later decision needs no gateway change, and it is not enabled: `llm_provider` does not accept it (R17).
- `replay`: returns recorded responses (ADR-0050.R38).
- `stub`: the recording stub of ADR-0022.R9 for `test` and `simulation` environments. It returns fixed outputs per template and records requests, and the CI canary tests read it (R56).
Source: ADR-0050.R3

R14. Each adapter publishes capability flags per model: structured output, tool calls, image and PDF input, context length, reasoning control, prompt caching. A seat uses an advanced feature only when the flag is set, with a fallback otherwise (spec 17, "no lowest common denominator").
Source: ADR-0050.R3

R15. Only `nativeflows.agents.gateway.adapters` may import a provider library (`anthropic`) or call a provider host. An import-linter `forbidden` contract enforces it (ADR-0022.R6), and handlers still import no LLM library (ADR-0008.R4).
Source: ADR-0050.R4

### Seats and providers

R16. `seatmap.yaml` (spec 17) lives in `backend/nativeflows/agents/seatmap.yaml`. Each seat names: required capabilities, reasoning level, temperature where supported, output token limit, the model per provider as a pinned model snapshot identifier (never an alias, so a provider's change under one name is a seat change with its evaluation; X7, ADR-0059.R26), a fallback chain within the same provider, and the evaluation report that admitted each (seat, model) pair (ADR-0050.R40). It changes by commit only, and CI refuses a change whose evaluation report is missing or failed.
Source: ADR-0050.R5, .N2

R17. One provider per installation in Phase 1. The installation setting `llm_provider` (from `NATIVEFLOWS_LLM_PROVIDER`) selects the adapter for every seat. In Phase 1 it accepts only `anthropic`, the configured cloud provider; startup refuses any other value. The endpoint and API key come from the deployment's secret store, are read only by the gateway process, and never appear in a prompt, log or span. Fallback chains never cross providers in Phase 1.
Source: ADR-0050.R5

R18. Spec 17 says Phase 1 has no local models. The `local` adapter is designed but not enabled. Whether Phase 1 may use a local provider at all, and whether it may then receive personal values, is the author's (open question; scope). Until then, with the switch on, personal values are stripped from every request (R42).
Source: ADR-0050.R5

R19. `llm_provider` unset means the LLM is off. Every agent mode is then `off`, and every operation still works by hand (Principle 12).
Source: ADR-0050.R5

R20. The seat class `extraction_vision_personal` (structured output, image and PDF input, data class `personal`, no tools) is designed and usable for a company only while an active `data_processing_permission` covers it; otherwise its runs end `routing_blocked` with `data_processing_not_permitted`. Each provider endpoint declares its processing region and country in the adapter configuration, the provider registry the permissions name (ADR-0057.R20, ADR-0057.R21).
Source: ADR-0050.R5.N1

### Provider failures and cost

R21. A retryable provider error (rate limit, overload, server error, timeout) is retried at most twice with exponential backoff, within the run's time budget (ADR-0050.R23). Then the next model of the seat's fallback chain is tried once; a run of an assisted agent type tries only models in its setting's `promoted_seat_models` (R70), and in Phase 1 only models with a passing result in the evaluation manifest (ADR-0078.R6). Then the call fails with `llm_provider_unavailable`. When an assisted run's promoted chain is exhausted, the run ends with outcome `provider_unavailable` and its work item goes back to people.
Source: ADR-0050.R6

R22. A provider refusal is an invalid output (ADR-0050.R35), with reason `refusal`.
Source: ADR-0050.R6

R23. Circuit breaker: five consecutive failures of one (provider, model) within 60 seconds open its circuit for 5 minutes, per installation. Calls on an open circuit fail at once with `llm_provider_unavailable` and spend nothing.
Source: ADR-0050.R6

R24. Prices per model are rows in `seatmap.yaml`: input, output, cache-read and cache-write price per million tokens, currency USD, `effective_from`.
Source: ADR-0050.R7

R25. The gateway computes each call's cost from the provider's reported usage and the price in force. Cost is an operational figure in `cost_amount` (domain `types.amount`) with `cost_currency` `USD`, exempt from telemetry rule 11 as ADR-0038.R10 allows. It never enters the books.
Source: ADR-0050.R7

R26. Token counts before a call use the adapter's counter (the provider's count endpoint, or a conservative estimate of 1 token per 3 characters for `local`), for the reservation of ADR-0050.R23.
Source: ADR-0050.R7

### Prompts and context items

R30. Prompts are rendered by the gateway, never assembled by workflow code. Templates (R35) declare their inputs: each is a field path from a query result model, or a literal of the template.
Source: ADR-0050.R8

R31. Workflow code passes context items: `(field path, row reference, value)` taken from query results, plus the label, field class, `is_untrusted` and `is_secret` attributes the registry declares for that field. Code never passes a free string. A value derived from another (a token, a handle, an extract) keeps the source row of the value it came from. A rendered page image is a context item of kind `attachment_page`, carrying its attachment's label as a whole; the gateway sends or refuses it whole. For extraction fields, the attribute the dispatcher reads for taint is the trust computed by `extraction_field_trust` (ADR-0057.R17, ADR-0057.R18, ADR-0057.R21).
Source: ADR-0050.R8, .N1

R32. The gateway fills the template from the items and adds, around each untrusted value, a fixed delimiter and the instruction that text inside it is data, not instructions. Untrusted text also gets a marker between words (datamarking), which the template states. This lowers injection risk; it is not the control. The controls are taint (ADR-0050.R25 to ADR-0050.R28), fixed tools (ADR-0050.R29) and checks (ADR-0050.R36).
Source: ADR-0050.R8, .N1

R33. What a model-called read tool returns (ADR-0050.R32) comes back through the dispatcher's query path, with its taint and scope rules, and reaches the model as context items with their labels, like any other input.
Source: ADR-0050.R8

R35. Prompt template files are `backend/nativeflows/agents/prompts/<agent_type>/<template_code>.md`, Markdown with front matter: `code`, `version` (semver), `seat`, `inputs` (field paths, with `required`), `output_schema` (pydantic model path and its version).
Source: ADR-0050.R13

R36. Provider-specific wording is a small overlay file `<template_code>.<provider>.md` (spec 17). The base and overlay are hashed together.
Source: ADR-0050.R13

R37. CI fails when a template's content hash changes without a version change. A run records, per step, the template code, version and content hash.
Source: ADR-0050.R13

R38. Templates are English (reading guide rule 6). Outputs that people read are written in the language the step's input names (a contact's `preferred_language`, else the company's), as an IETF language tag. No template or output schema fixes a list of languages.
Source: ADR-0050.R13

### Labels, the routing switch and data processing

R40. The gateway evaluates each item's label per row, with row conditions such as partner kind (ADR-0019.R7). An unknown kind counts as personal. The labels the gateway strips or routes are those of `personal-data-fields.csv`, with each row's condition evaluated per value (ADR-0079.R2, ADR-0079.R3).
Source: ADR-0050.R9, .N3

R41. `routing_switch` is a company setting, change-tracked (ADR-0038.R3), so whoever turns it on or off is recorded as accountable (spec 17). Default off. The switch is the kill switch: no permission overrides it (ADR-0063.R15).
Source: ADR-0050.R9, .N2

R42. With the switch on (Phase 1), before sending, the gateway replaces every `personal` and `sensitive_personal` value with a typed placeholder, `[personal:<table>.<field>]`. It then scans the rendered request for the exact text of every removed value, and rejects the request with `llm_routing_refused` if any remains.
Source: ADR-0050.R9

R43. An input that the template declares `maskable` (the column samples of the data migration agent, a Phase 2 agent type, ADR-0078.R2) is replaced instead by a shape mask: each upper-case letter by `A`, every other letter (lower-case or without case) by `a`, every Unicode digit by `9`, other characters kept, so only the character classes and the length leave.
Source: ADR-0050.R9

R44. A step whose template marks a removed input as required is not sent at all. The run then ends with outcome `routing_blocked` and leaves its work item to people.
Source: ADR-0050.R9

R45. Sensitive personal values are never sent to any model in Phase 1, whatever the switch says. No Phase 1 workflow needs them.
Source: ADR-0050.R9

R46. Each seat declares in `seatmap.yaml` the highest label it may receive, from spec 17's "data visible" column: `internal` for the non-personal seats, `personal` for the seats with personal data, `per_routing` for drafting and data Q&A (personal when the switch is off). The gateway removes values above the seat's class whatever the switch says, so a step that needs personal values uses a personal seat. The data migration seat (Phase 2, ADR-0078.R2) is `personal`, and personal-labelled column samples go to no other seat.
Source: ADR-0050.R9

R47. `bank_statement_line` description, counterparty name and counterparty account are `personal`, because a payer may be a person; these labels are an extract of `personal-data-fields.csv`. A value a step extracts keeps the label of its source field.
Source: ADR-0050.R9, .N3

R48. Embeddings are after Phase 1 (spec 13); the same rules will apply.
Source: ADR-0050.R9

R49. The core registers the regime setting `data_processing.policy` without a default (per data class: allowed or not, and whether processing in another country needs a recorded assessment); a regime that declares none fails closed. The gateway evaluates it with the company's `data_processing_permission` rows for whole-attachment items and the vision seat class, in every run mode, golden-set replays and evaluations included (ADR-0057.R20).
Source: ADR-0050.R9.N1

R50. The gateway applies the regime policy and the company's `data_processing_permission` rows to every request carrying a personal value, field values included: without a permission the values become placeholders or shape masks, and a step that needs one ends `routing_blocked`. `data_processing.never_send_fields` only narrows what a permission allows.
Source: ADR-0050.R9.N1, .N2

### Processing log, minimization and secrets

R51. Every call that sends at least one personal value, with the switch on or off, writes one `personal_data_processing_log` entry (ADR-0019.R11; spec 17 "logging always on"): purpose (agent type and step code), provider, model, whether the provider is local, and the list of (table, field, row ID) sent. Values are never logged.
Source: ADR-0050.R10

R52. The processing log entry and the call's `llm_request` step row are committed before the request is sent. If either insert fails, the call is not made.
Source: ADR-0050.R10

R54. A template receives only the fields it declares, never whole records. Where the model only needs to tell records apart, items carry short handles (`r1`, `r2`) that the runtime maps back, not names or IDs.
Source: ADR-0050.R11

R55. Fields that hold secrets (token hashes, TOTP and OIDC secrets, webhook credentials, ADR-0044.R17) carry the schema attribute `is_secret`. No view and no query result model returned to an agent run contains one (a registry CI check), and the gateway rejects an item with `is_secret` with `llm_routing_refused`.
Source: ADR-0050.R11

R56. CI seeds canary values in secret fields, and in personal fields of a company with the switch on, runs every golden case through the `stub` adapter, and fails if any canary appears in a recorded request, a step row, a span or a log line.
Source: ADR-0050.R11

### Agent types

R60. Agent types are code, versioned as one artifact. Each agent type's one `AgentTypeDeclaration`, in `nativeflows.agents.agent_types.<agent_type>` (ADR-0078.R3), declares:
- `code`, `version` (semver) and the ordered steps;
- the tool list (ADR-0050.R29), which is also its declared permissions: one set, which ADR-0017.R11 calls the declared permissions, so the intersection of ADR-0050.R31 is the tool list with the human's rights (ADR-0054.R16);
- the work item kinds it may claim (ADR-0042.R10), each with `wake_up` (R65), and optionally `configurable_triggers` (event type, subject table);
- `scope_kind` (`partner`, `import_batch`, `subject`) with its scope resolver and the subject tables it accepts (R86), and `may_read_untrusted`;
- `field_classes` (default none): a run sees a `cost` or `margin` field only when both its agent type and its human have the class; a version declares no record scope, which comes from the human alone and is narrowed by the tainted scope;
- the seat of each LLM step, its prompt templates and output schemas with their versions;
- its budget maximums (ADR-0050.R22), which in Phase 1 are only the per-run ceilings of its declaration (ADR-0078.R3, ADR-0078.R7), and its evaluation suite with threshold (ADR-0050.R39).
In Phase 1 these elements live in the agent type's `AgentTypeDeclaration` (ADR-0078.R3).
Source: ADR-0050.R12, .N1, .N2

R61. At startup the registry writes `agent_type` (`code`, `name`, `is_active`) and one immutable `agent_type_version` row per version (all of the declaration as data, plus a `content_hash`), like the generated catalogs. Nobody edits them.
Source: ADR-0050.R12

R62. Changing any declared element, template or schema changes the content hash. CI fails when the hash changes and the version does not, and a new version needs a passing evaluation (ADR-0050.R40).
Source: ADR-0050.R12

R63. `agent_type` codes are `snake_case` nouns of the workflow (ADR-0004), for example `customer_onboarding`, `quotation`, `bank_matching`, `purchase_invoice`, `planning`, `data_migration` (ADR-0051). The Phase 1 agent types are `assistant`, `analysis`, `bank_matching`, `purchase_invoice`, `document_reader` and `planning` (ADR-0078.R1). `auto_post_advisor`, `customer_onboarding`, `quotation`, `data_migration`, `product_engineering` and the `production` types are Phase 2 types: registered with mode `off` and no workflow code in Phase 1 (ADR-0078.R2).
Source: ADR-0050.R12, .N6

R64. Declarations of further agent types:
- `analysis`: scope kind `subject` on `analysis_question`, or on `analysis_example` for evaluation runs; `may_read_untrusted: false`; field classes `cost` and `margin`. It also declares the analysis catalog hash it was evaluated with, so a catalog change is a new version (ADR-0060.R20, ADR-0060.R25).
- `production`: scope `subject` on `production_order` or `production_version`, `may_read_untrusted: false`.
- `production_capture`: scope `subject` on one `production_order` resolved from a `document_extraction`, tainted at start.
- `production_variance`: scope `subject` on `analysis_question` or `production_order`, field class `cost`.
- Each `production` type has its leaf `agent_<agent_type>` (`agent_production`, `agent_production_capture`, `agent_production_variance`; ADR-0064.R1). None of them is a Phase 1 agent type (R63).
Source: ADR-0050.R12.N3, .N5

R65. Each claimable kind carries `wake_up`: `always`, or `configurable`. A kind declared `configurable` takes the company setting `agents.<agent_type>.wake_up_mode.<kind>` (`always`, the default, `by_rule`, `off`); under `by_rule` the agent is started only by a company's automation rule with action `start_agent` (ADR-0058.R7, ADR-0063.R11). The Phase 1 `purchase_invoice` declaration declares `supplier_invoice_received` `configurable`, default `always`; every other kind of the Phase 1 agent types stays `always`. The quotation agent's `inbound_message_matched` is declared `configurable` in its next version, when that Phase 2 type is brought forward (ADR-0078.R2). A kind is declared by at most one agent type, and `check` refuses a second declaration (ADR-0078.R1, ADR-0078.R12).
Source: ADR-0050.R12, .N2, .N4, .N6

### Company setting, modes and promotion

R70. `agent_type_setting` is company data, change-tracked, one row per company and agent type: `agent_type_code`, `mode` (`off`, `shadow`, `assisted`, `active`; default `off` for every company), `workflow_owner_id` (the human whom runs from events and schedules act for, ADR-0017.R12; required unless `off`), `promoted_version` with `promoted_seat_models` (the agent type version and the (seat, model) pairs the evidence covered, set when the mode moves to `assisted`), and `active_document_types` (the document types of mode `active`, set in mode `active` only, naming at least one document type). It holds no budget value. The DDL keeps `shadow` for Phase 2; `check` refuses it in Phase 1 seed and configuration (ADR-0078.R5).
Source: ADR-0050.R14, .N4, .N5, .N8, ADR-0055.R7

R71. Modes:
- `off`: no runs.
- `shadow` (Phase 2): runs execute every command in simulate mode only, so nothing persists except their run records and denials; their would-be outputs are recorded for comparison (ADR-0050.R41). Shadow runs bind their work item without claiming it, so people work on it as usual, and the dispatcher skips the claim check for them because they only simulate.
- `assisted`: runs create drafts and change proposals.
- `active`: `assisted`, and in addition the type's drafts of the document types named at promotion may pass the auto-post gateway as tainted drafts (ADR-0065.R11).
- There is no mode in which an agent posts: the agent still only drafts (ADR-0043.R9, floor 4).
- Phase 1 modes are `off`, `assisted`, and `active` only as the gateway uses it. Live agent shadow returns in Phase 2, and `demote_to_shadow` of `agents.<agent_type>.drift_action` acts as `pause_new_runs` until then (ADR-0078.R5, ADR-0078.R6).
Source: ADR-0050.R14, .N5, .N6, ADR-0055.R7

R72. The stored mode is the person's choice, and no command changes it on its own. The runtime computes the effective mode at each start from the behavior hash: the current version's content hash without budget maximums. No Phase 1 agent type declares a parameter set, so in Phase 1 the behavior hash has no per-company part and constants are part of the version (ADR-0078.R6). Phase 2: an agent type version that declares its constants as a tunable parameter set includes the current version's `parameters_hash` in its behavior hash, so a promoted parameter set changes it (ADR-0059.R7, ADR-0059.R12). Budget values stay outside the behavior hash, so a budget change leaves the effective mode unaffected. After Phase 1, an `assisted` type whose behavior hash differs from that of `promoted_version`, or whose seat models are not all in `promoted_seat_models`, runs as `shadow` until a person promotes it again.
Source: ADR-0050.R14, .N2, .N4, .N6, ADR-0055.R7

R73. Effective mode in Phase 1 (ADR-0078.R5, ADR-0078.R6):
- A behavior hash without a passing evaluation result runs as `off` instead of `shadow`, with the same `agent_mode_degraded` item (R78).
- The passing results of a release live in its evaluation manifest, one row per agent type, behavior hash, seat and model.
- A company already `assisted` stays `assisted` across a change of the hash that the manifest shows as passing; the runtime then updates `promoted_version` and `promoted_seat_models` as `system`, with an audit record. Otherwise those fields change only by an approved proposal.
- `document_reader` is the one exception: it returns to `assisted` in a company only when the replay of that company's golden set has passed again (ADR-0057.R13).
- `active` does not carry over a change of the hash: the type counts as `assisted` for the gateway until it is promoted again. It also counts as `assisted` for the gateway while an `agent_quality_below_threshold` item is open.
- No live shadow comparison runs in Phase 1, so `GetAgentShadowEvaluation` feeds no Phase 1 promotion.
Source: ADR-0050.R14, .N5, .N6, ADR-0055.R7

R74. `UpdateAgentTypeSetting` has effect class `master_data_change`, is change-tracked and `is_proposal_bound`, is on no agent tool list (ADR-0050.R30) and needs `full` on the leaf `agent` (a declared minimum level; `edit` there does not give it). The leaf `agent` belongs to module `agents`, and each agent type has its own leaf `agent_<agent_type>` below it for `start_agent:<agent_type>` (ADR-0054.R24).
- A person may lower the mode or change other fields directly.
- A change whose resulting `workflow_owner_id` does not hold `start_agent:<agent_type>` in the company is refused with `workflow_owner_not_permitted`.
- A change that sets `assisted` is accepted only from the execution of an approved change proposal (ADR-0029.R3); otherwise it returns `proposal_required`.
- The person who submits the proposal vouches for its evidence, and a person other than the submitter approves it; an approval by the submitter returns `approver_is_submitter`, also in the small-company mode. Writers are excluded from approving by ADR-0055.R7, condition 5.
- A budget change is not an `UpdateAgentTypeSetting` change.
- In Phase 1 it refuses mode `shadow`, and every mode except `off` for an agent type that has no Phase 1 workflow, with `validation_failed`; `agent_mode_not_declared` keeps its own meaning (R75; ADR-0078.R5).
Source: ADR-0050.R14, .N1, .N4, ADR-0055.R7

R75. Setting `active` is a proposal that another person approves, from `assisted` at the same behavior hash and seat models (ADR-0065.R11). The version declares `auto_post_document_types`, otherwise `agent_mode_not_declared`. The proposal names per document type an `agent_promotion_evidence` row with target mode `active` from `GetAgentDraftAcceptance`: at least ceil(3 / `auto_post.max_error_rate`) drafts over at least two calendar months, at least (1 - rate) posted unchanged, none to another partner. `agent_type_setting.active_document_types` records the types. Lowering is direct.
Source: ADR-0050.R14, .N5, ADR-0055.R7

R76. Frozen evidence. `CreateAgentPromotionEvidence` (module `agents`, effect class `other`, a person's command) computes the evidence once, from the sources of R77: in Phase 1 from the stored evaluation result instead of `GetAgentShadowEvaluation`, which returns with live shadow in Phase 2, and for target mode `active` from `GetAgentDraftAcceptance` (ADR-0078.R6, ADR-0065.R11). It writes an immutable `agent_promotion_evidence` row (owned by `agent_runs`): agent type, date range (`start_date`, `end_date`), the `behavior_hash` and `seat_models` it covered, the `figures`, the `thresholds` applied and `is_sufficient`; the row also holds `target_mode` (`assisted`, `active`), `document_type` (set exactly when the target mode is `active`), `attachment_id` and `created_by_user_id`. The proposal's `UpdateAgentTypeSetting` payload names that row. Creating the proposal refuses evidence that is not sufficient (`shadow_evidence_insufficient`). Executing it only checks that the agent type's current behavior hash and seat models still equal the row's, and fails with `promotion_evidence_stale` otherwise; it never re-reads live figures, so the plan hash stays stable between simulation, approval and execution.
Source: ADR-0050.R14, .N5, ADR-0055.R7

R77. Promotion evidence by agent type:
- Promotion to `assisted` in Phase 1 uses the offline evaluation set run with the real provider per pair of seat and model, and the replay of recorded responses in CI (ADR-0050.R39, ADR-0050.R40). Promotion to `active` uses the in-use draft acceptance of R75.
- `analysis` keeps its offline evaluation exception: the daily job `RunAnalysisEvaluation` runs it on the company's verified examples, acting for each example's releaser, and its promotion evidence is the version's CI evaluation report and, from 30 verified examples, that evaluation (ADR-0060.R25). In Phase 1 the daily evaluation is its evaluation in use, and a version without a passing CI evaluation is `off` (ADR-0078.R6).
- The assistant has no shadow comparison. Its promotion evidence is the stored result of its evaluation set (ADR-0077.R13), which `CreateAgentPromotionEvidence` records; at effective mode `off` the assistant starts no run and answers nobody (ADR-0078.R6).
- This ladder is the pattern that ADR-0059.R12 generalizes to every L1 and L2 artifact.
- Phase 2, with live agent shadow: `analysis` in `shadow` answers nobody and its daily evaluation is its shadow evaluation; for data migration, a Phase 2 agent type (ADR-0078.R2), the evidence comes from an attached rehearsal report (ADR-0051.R28).
Source: ADR-0050.R14, .N2, .N3, .N6, .N7, ADR-0055.R7

R78. Visible drops. `GetAgentTypeSetting` returns the stored mode, the effective mode and the reason they differ (`version_changed`, `seat_model_changed`). When the effective mode first differs from the stored mode for a company and agent type, `agents` raises one work item `agent_mode_degraded` (owner `company_owner`, key the agent type within the company, due `days:1`). It is checked at every `StartAgentRun` and by the daily `RunAgentQualityCheck`, and it resolves when the agent type is promoted again or its mode is lowered.
Source: ADR-0050.R14, .N6, ADR-0055.R7

R79. No budget value has scope `agent_type` in Phase 1: the per-type keys are removed (ADR-0078.R7), and the budget values left `agent_type_setting`. An agent type's per-run ceilings are its declaration's; the assistant's cost per run is the company setting `assist.max_cost_per_run`.
Source: ADR-0050.R14, .N4, .N8, ADR-0055.R7

### Starting a run

R80. `StartAgentRun` (module `agents`, effect class `other`) writes through `agent_runs.contract.create_run`. Its payload is the agent type, and either a `work_item_id`, or a subject (`subject_table`, `subject_id`) for a run a person starts without an exception.
Source: ADR-0050.R15

R81. `StartAgentRun` is called by the wake-up consumer `agent_wake_up` (ADR-0050.R16) for items of kinds the agent type declares, by a schedule, or by a person.
Source: ADR-0050.R15

R82. The human acted for follows ADR-0017.R12 and nothing else: a run a person starts acts for that person; a run from a schedule acts for the schedule's owner; a run triggered by an event or by incoming e-mail, which every wake-up is, acts for the owner of that workflow, the setting's required `workflow_owner_id`. For agent runs the "owner of that intake or workflow" is always that setting, so a mailbox owner or a statement's importer is never the human acted for by being one, and the sender of outside content never is. That human needs `start_agent:<agent_type>`.
Source: ADR-0050.R15

R83. From a wake-up or a schedule, `StartAgentRun` runs as actor `system` on behalf of that human (ADR-0013.R9); from a person, as that person.
Source: ADR-0050.R15

R84. Checks: the mode is not `off` (`agent_mode_off`), which also refuses every Phase 2 agent type (ADR-0078.R2); the daily budgets are not exhausted (`agent_budget_exceeded`, ADR-0050.R24), in Phase 1 the company's daily cap, the outside-content pool and the installation maximum (ADR-0078.R7); the item's kind is declared by the agent type (`agent_kind_not_declared`); the subject's table is one the agent type accepts (`agent_kind_not_declared`); the scope resolver finds a scope (`agent_scope_unresolved`).
Source: ADR-0050.R15

R85. The handler claims the work item for the run (ADR-0042.R9 to ADR-0042.R11), or creates and claims an `agent_task` item for a subject (ADR-0042.R11). A held claim fails with `work_item_claimed`. A shadow run (Phase 2, R71) binds the item without a claim.
Source: ADR-0050.R15

R86. The handler binds the run's scope by the agent type's scope resolver: a pure function of the subject's stored, trusted fields, such as the interaction's matched `partner_id` (ADR-0019.R15) or the import batch. It never reads an `is_untrusted` field. If the resolver finds no scope, the command fails with `agent_scope_unresolved`, the wake-up consumer treats that as a skip rather than a retry, and the item stays with people. The scope never changes during a run.
Source: ADR-0050.R15

R87. Taint at start. The handler decides from the subject row itself, whoever starts the run, a person included. The run starts tainted (`tainted_at` is its start) when its work item has `is_tainted` (ADR-0042.R15; `taint_source_kind` `work_item`), or when its subject row is outside content (`outside_subject`). The registry marks these outside-content subject tables:
- an inbound interaction (the subjects of `inbound_message_matched` and `interaction_unmatched`; ADR-0052.R15);
- an incoming e-invoice record, a bank statement line, an import batch or an import row, or any row whose `is_untrusted` is true;
- `document_extraction`: a `document_reader` run on it starts tainted and reads its words, fields, rule runs and pages (ADR-0057.R11);
- `assist_request` only when its `purpose` is `act`: such a run starts tainted with `taint_source_kind` `outside_subject` and source table `assist_request` (ADR-0077.R13).
So such a run reads nothing before it is tainted. An agent type only lists the subject tables it accepts; it does not decide taint.
Source: ADR-0050.R15, .N1, .N2

R88. The result of `StartAgentRun` is an `agent_run` in state `queued`, and the event `AgentRunStarted`.
Source: ADR-0050.R15

R89. The UI's assist panel starts runs of the agent type `assistant` with an `assist_request` row as subject, which carries the user's typed text (up to 2,000 characters, written by the `human_only` `CreateAssistRequest`) and the screen's context, as `analysis_question` does for the analysis agent; runs stay asynchronous with no dialogue. A run of `purpose` `act` always starts tainted; `ask` and the resolve purposes start untainted and taint propagates when they read untrusted data. One run costs at most `assist.max_cost_per_run` (default USD 0.20). `GetAgentBudgetStatus`, a people-only query on no tool list, shows the company's remaining daily agent budget, not a per-agent-type budget (ADR-0078.R7; ADR-0077.R13, ADR-0077.R14, ADR-0077.R17).
Source: ADR-0050.R15.N3

## Invariants

Statements are those of `invariants.csv`. Each row stands once in the module, in the chunk that states the rule its catalog source names.

| Invariant | Name | Check point | Statement | Protects |
| --- | --- | --- | --- | --- |
| `INV-213` | `personal_llm_sends_logged` | day (first step 5; flagged: ADR-0050 rule 5, local provider and personal data) | Every LLM step that sent personal values has its `personal_data_processing_log` entry; no LLM step sent a personal value while its company's routing switch was on. | R42, R51, R52 |

## Edge cases

None: no edge case of the catalog names a rule of this chunk (ADR-0050.R1 to ADR-0050.R15) as its source.

## Settings

None: the settings used by rules of this chunk have their rows in the chunks of the rules their catalog source names: `agents.<agent_type>.wake_up_mode.<kind>` (R65; ADR-0063.R11), `agents.<agent_type>.drift_action` (R71; ADR-0063.R12), `data_processing.policy` (R49; ADR-0063.R18), `data_processing.never_send_fields` (R50; ADR-0063.R15) and `assist.max_cost_per_run` (R79, R89; ADR-0077.R13).

The installation setting `llm_provider` (R17, R19) and the company setting `routing_switch` (R41) are named by rules but absent from `settings.csv`.

Reads: `auto_post.max_error_rate` (`policy`; ADR-0063.R10), used by R75.

## UI annotations

Work item kinds raised by rules of this chunk (`work-item-kinds.csv`): `agent_mode_degraded` (R78; its row stands with the other kinds of module `agents` in chunk 3) and `agent_task` (subject `agent_run`, owner `run_on_behalf_of`, due `days:1`, resolution `system`; no agent type may declare it; R85). The assist panel and the command bar are stated with ADR-0077.R13 and ADR-0040.R7.N1. The sources of this chunk hold no floorplan, facet or tile annotation.

## Conflicts

CONFLICT ADR-0050.R9.N1: ADR-0050.R9.N2 answers the note's open question; the regime policy and permissions apply to field-level personal values too (R50).
CONFLICT ADR-0050.R12: ADR-0050.R12.N6 governs the set of Phase 1 agent types; the codes listed in the rule text stay only as examples of the naming rule (R63).
CONFLICT ADR-0050.R12.N2: ADR-0050.R12.N6 governs; `supplier_invoice_received` of `purchase_invoice` is declared `configurable`, so "keep every kind `always` until the author decides" is not restated (R65).
CONFLICT ADR-0050.R14: ADR-0055.R7 governs approval of one's own document, so the interim of ADR-0043.R13 is not restated (R74); ADR-0050.R14.N5 adds the mode `active` (R70, R71); ADR-0050.R14.N6 governs the Phase 1 effective mode (R73); ADR-0050.R14.N8 with the DDL removes the lowered budget values from `agent_type_setting` (R70, R79); ADR-0078.R5 adds the Phase 1 refusals of `UpdateAgentTypeSetting` with `validation_failed` (R74), and ADR-0078.R6 replaces `GetAgentShadowEvaluation` by the stored evaluation result as the Phase 1 source of `CreateAgentPromotionEvidence` (R76).
CONFLICT ADR-0050.R14.N1: ADR-0055.R7 governs; `full` on the leaf `agent` is required, `edit` no longer gives the command, and `approver_is_submitter` stays (R74).
CONFLICT ADR-0050.R14.N4: ADR-0050.R14.N8 governs; the budget values left `agent_type_setting`, and no `setting_value` row of scope `agent_type` holds one in Phase 1 (R79).
CONFLICT ADR-0050.R14.N5: the note governs the sentence "so there is no further mode"; R71 states the mode `active` and that there is no mode in which an agent posts.
CONFLICT ADR-0050.R14.N6: the note governs Phase 1; a hash without a passing evaluation runs as `off`, not `shadow`, live agent shadow waits for Phase 2, and the runtime may update `promoted_version` as `system` (R71, R73).
CONFLICT ADR-0050.R15: the rule's own closing sentence renames the kind `inbound_message` to `inbound_message_matched` (ADR-0052.R15), so only the new name is stated (R87); the shadow binding is a Phase 2 case under ADR-0050.R14.N6 (R85); the daily budget check is the company, outside-content and installation tiers of ADR-0078.R7, and `agent_mode_off` refuses the Phase 2 types of ADR-0078.R2 (R84).
CONFLICT ADR-0050.R12: ADR-0078.R3 governs the place of the declaration: it is `agent_types/<agent_type>.py`, not the workflow module `workflows.<agent_type>` that ADR-0050.R12 names, and the workflow module holds the steps (R60, R1420); no note on ADR-0050.R12 orders the two (source finding SRC-3), so ADR-0078.R3 stands as current law because it is the later accepted ADR. ADR-0078.R2 registers the Phase 2 agent types with mode `off` and no workflow code (R63), and ADR-0078.R3 with ADR-0078.R7 make the declared budget maximums the per-run ceilings of the `AgentTypeDeclaration` (R60).
CONFLICT ADR-0050.R14.N2: ADR-0078.R6 governs: no Phase 1 agent type declares a parameter set, so the `parameters_hash` part of the behavior hash is Phase 2 (R72), and the analysis shadow evaluation is Phase 2 while its daily evaluation is its Phase 1 evaluation in use (R77).
CONFLICT ADR-0050.R14.N7: the data migration agent is a Phase 2 type under ADR-0078.R2, so its rehearsal evidence is stated as Phase 2 (R77); `CreateAgentPromotionEvidence` computes Phase 1 evidence from the stored evaluation result under ADR-0078.R6 (R76).
CONFLICT ADR-0050.R9: the data migration agent named for `maskable` column samples and the data migration seat is a Phase 2 type under ADR-0078.R2; the mechanism stays (R43, R46).
CONFLICT ADR-0050.R6: ADR-0078.R6 narrows the model fallback in Phase 1 to models with a passing result in the evaluation manifest, stated beside the promoted chain in R21.

## Proposed (not law)

None

## Trace

| Source | Where |
| --- | --- |
| ADR-0040.R7.N1 | ref: ADR-0040.R7.N1 |
| ADR-0050.R1 | R1-R4 |
| ADR-0050.R1.N1 | R1, R2 |
| ADR-0050.R1.N2 | R1, R3 |
| ADR-0050.R2 | R10-R12 |
| ADR-0050.R3 | R13, R14 |
| ADR-0050.R4 | R15 |
| ADR-0050.R5 | R16-R19 |
| ADR-0050.R5.N1 | R20 |
| ADR-0050.R5.N2 | R16 |
| ADR-0050.R6 | R21-R23 |
| ADR-0050.R7 | R24-R26 |
| ADR-0050.R8 | R30-R33 |
| ADR-0050.R8.N1 | R31, R32 |
| ADR-0050.R9 | R40-R48 |
| ADR-0050.R9.N1 | R49, R50 |
| ADR-0050.R9.N2 | R41, R50 |
| ADR-0050.R9.N3 | R40, R47 |
| ADR-0050.R10 | R51, R52 |
| ADR-0050.R11 | R54-R56 |
| ADR-0050.R12 | R60-R63, R65 |
| ADR-0050.R12.N1 | R60 |
| ADR-0050.R12.N2 | R60, R65 |
| ADR-0050.R12.N3 | R64 |
| ADR-0050.R12.N4 | R65 |
| ADR-0050.R12.N5 | R64 |
| ADR-0050.R12.N6 | R63, R65 |
| ADR-0050.R13 | R35-R38 |
| ADR-0050.R14 | R70-R79 |
| ADR-0050.R14.N1 | R74 |
| ADR-0050.R14.N2 | R72, R77 |
| ADR-0050.R14.N3 | R77 |
| ADR-0050.R14.N4 | R70, R72, R74, R79 |
| ADR-0050.R14.N5 | R70, R71, R73, R75, R76 |
| ADR-0050.R14.N6 | R71-R73, R77, R78 |
| ADR-0050.R14.N7 | R77 |
| ADR-0050.R14.N8 | R70, R79 |
| ADR-0050.R15 | R80-R88 |
| ADR-0050.R15.N1 | R87 |
| ADR-0050.R15.N2 | R87 |
| ADR-0050.R15.N3 | R89 |
