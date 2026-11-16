# ADR-0050: Agent runtime and read-only query layer

Status: accepted (2026-11-15) under ADR-0005, reviewed by Claude Fable 5.2 (builder Claude Opus 5.5). Design items: DS-32, DS-33. Related decisions: D2, D12, D14. Principles 2, 3, 4, 6, 7, 8, 10, 11, 12, 13. ADR-0002, ADR-0003, ADR-0004, ADR-0005, ADR-0008, ADR-0013, ADR-0014, ADR-0017, ADR-0019, ADR-0022, ADR-0023, ADR-0024, ADR-0027, ADR-0029, ADR-0030, ADR-0038, ADR-0040, ADR-0042, ADR-0043, ADR-0044; spec 02, 03, 04, 13, 14, 17. Workflows: [ADR-0051](0051-agent-workflows.md).

## Decision

**One gateway.** Every LLM call goes through one gateway in layer 5 `agents`. It has one method, `complete`, which also does structured output against a JSON Schema and tool calls. Provider adapters sit behind it. In Phase 1 an installation uses one provider for all seats, the cloud provider of ADR-0002. A local adapter is designed but not enabled until the author decides (spec 17 has no local models in Phase 1). No other module imports a provider library.

**Labels decide what leaves.** The gateway renders every prompt from a versioned template and typed context items, so it knows the data label of every value it sends. The company's routing switch removes personal values before sending. Every personal value sent is logged. Secrets never reach a prompt.

**Runs are recorded.** Each run is an `agent_run` in layer 2 `agent_runs`. Each LLM call and tool call is an `agent_run_step`. Together they hold the agent type and version, template versions, models, inputs as references, tool calls, outputs, tokens, cost, duration, taint and outcome. Telemetry keeps to ADR-0038's allow-lists.

**Budgets stop runs.** Each run has limits on calls, tokens, cost, rows and time, and each company has daily limits. The runtime reserves the worst case before every call. A run that would exceed a limit stops with an outcome and a work item. It never loops.

**Taint is enforced where data is read.** A run whose subject is outside content starts tainted. Any other run becomes tainted when the dispatcher returns untrusted data to it, and the taint is committed before the data is returned. A tainted run reads only its scope (its partner, its import batch, or its subject), its own drafts and reference data, and nothing outside that scope, even read earlier, may enter its prompts or drafts. It runs only commands registered `is_draft_only`.

**Tools are fixed and narrow.** An agent type version declares a fixed tool list of registered queries and commands. The tool definitions are generated from the registry, as for MCP. Permissions are the intersection of the agent type and the human acted for. LLM steps get read tools only; workflow code runs commands after a deterministic check. No tool list holds a `human_only`, posting or `outbound_send` command, or a `Submit`, `Post` or `Issue`.

**Outputs are checked.** Every LLM step has a pydantic output schema. An invalid output gets at most two retries with the validation errors, then the run stops with a work item. Deterministic code checks every valid output before use.

**Runs replay.** Recorded runs can be replayed with their recorded LLM outputs, deterministically, or re-run against another model or prompt for comparison. Each workflow has a golden evaluation set from the synthetic dataset. Shadow-mode metrics feed the promotion rules of ADR-0051.

**The query layer.** Agents and reports read through semantic views in schema `query`, served by the read-only role `nativeflows_readonly` with short timeouts, pagination and row limits. The views mask field classes, apply record scope, and omit `is_untrusted` columns unless asked. Management reporting reads views by system account. Views are exposed as registered queries and described as MCP resources. Audit data is never on an agent's tool list.

### Rules

**Modules**

1. Three modules carry this ADR (ADR-0022 rule 2; ADR-0027 rule 1):

   | Module | Layer | Owns |
   | --- | --- | --- |
   | `agent_runs` | 2 | `agent_type`, `agent_type_version`, `agent_type_setting`, `agent_run`, `agent_run_step`, `agent_budget_usage`, `agent_promotion_evidence`; the contract functions `create_run`, `complete_run`, `cancel_run`, `write_agent_type_setting`, `write_promotion_evidence`, `mark_run_tainted`, `reserve_budget`, `settle_budget`, `record_run_step` and `get_run_context`, which the layer-5 handlers of `agents` call |
   | `agents` | 5 | The gateway and its adapters, the runtime, the workflows of ADR-0051, prompt templates, output schemas, tool definition generation, the replay adapter; the commands `StartAgentRun`, `CompleteAgentRun`, `CancelAgentRun` and `UpdateAgentTypeSetting`, the scope resolvers, `GetAgentShadowEvaluation` with the workflow comparators, and `RunAgentQualityCheck` |
   | `query` | 5 | Schema `query`: the views, their declarations, the query builder, the `List<View>` and `Get<View>` queries, list export |

   - **Imports.** `agents` imports `registry` (dispatch) and the `agent_runs` and `work` contracts. Its command handlers (scope resolvers, shadow comparators) may also import the contracts of the layer 3–4 modules whose subjects its agent types declare (`crm`, `purchasing`, `cash`, `planning`, `sales`, `master_data`). Workflows reach data only through registered queries and commands, and nothing in `agents` imports `query` or `imports`, its layer-5 peers.
   - **Layer 2 stays tables and contracts.** `agent_runs` holds the tables and the contract functions only. Resolvers, comparators and evaluations read layer 3–5 data, so they live in `agents`, and the bank auto-post evidence lives in `cash` (ADR-0051 rule 18). `query` imports `db`, `registry` and `agent_runs` (for taint). `registry` imports the `agent_runs` contract for credentials, tool lists and taint. `agent_runs` imports `work` only.
   - **No agent framework** (ADR-0002). Workflows are plain code that calls the gateway and the dispatcher.

   Note ([ADR-0057](0057-document-intake-and-extraction.md), proposed 2026-11-15): `agent_runs` also owns `data_processing_permission` and its contract function; `agents` holds its commands `SetDataProcessingPermission` and `EndDataProcessingPermission` and the agent types `document_reader` and `product_engineering` ([ADR-0057](0057-document-intake-and-extraction.md) rules 1, 11, 20; [ADR-0062](0062-product-engineering-workflow.md)).

   Note ([ADR-0060](0060-agent-assisted-reporting-and-analysis.md), proposed 2026-11-15): `query` also owns the analysis catalog, validator, compiler and executor, the analysis queries and the tables of DS-33-analysis.sql, and now imports the `work` contract to raise its two work item kinds; `agents` owns the `analysis` workflow (rule 1).

**LLM gateway**

2. The gateway interface is one function, `agents.gateway.complete(request) -> response`.
   - **Request:** `seat`; `template_code` and `template_version`; the context items (rule 8); optional `output_schema` (a JSON Schema generated from a pydantic model); optional `tools` (definitions generated from the registry, rule 29); `reasoning_level` (`low`, `medium`, `high`, `very_high`, spec 17); `max_output_tokens`; `timeout_seconds`; the `agent_run_id` and step ordinal.
   - **Response:** `output` (the parsed object when a schema was given), `text`, `tool_calls` (name and arguments), `stop_reason` (`end`, `max_tokens`, `tool_use`, `refusal`), `usage` (input, output, cache-read and cache-write tokens), `cost_amount` with `cost_currency` (rule 7), `provider`, `model`, `latency_ms`, and `request_hash` (SHA-256 of the canonical rendered request, rule 38).
   - **Structured output and tool calls** are modes of the same call. A request with `output_schema` uses the provider's structured output when the model's capability flag says so, else a tool-call shim with the same schema. The response is always validated by the runtime (rule 35), whatever the provider promises.
3. Adapters:
   - **`anthropic`:** the Anthropic SDK (ADR-0002). The reasoning level maps to effort (spec 17); temperature is not sent.
   - **`local`:** an OpenAI-compatible HTTP endpoint run by the operator (vLLM, llama.cpp server or similar), called with `httpx`, which the Anthropic SDK already brings. Temperature from the seat applies. It is designed so that a later decision needs no gateway change, and it is not enabled: `llm_provider` does not accept it (rule 5).
   - **`replay`:** returns recorded responses (rule 38).
   - **`stub`:** the recording stub of ADR-0022 rule 9 for `test` and `simulation` environments. It returns fixed outputs per template and records requests, and it is what the CI canary tests read (rule 11).

   Each adapter publishes capability flags per model: structured output, tool calls, image and PDF input, context length, reasoning control, prompt caching. A seat uses an advanced feature only when the flag is set, with a fallback otherwise (spec 17, "no lowest common denominator").
4. Only `nativeflows.agents.gateway.adapters` may import a provider library (`anthropic`) or call a provider host. An import-linter `forbidden` contract enforces it (ADR-0022 rule 6), and handlers still import no LLM library (ADR-0008 rule 4).
5. Seats and providers:
   - **`seatmap.yaml`** (spec 17) lives in `backend/nativeflows/agents/seatmap.yaml`. Each seat names: required capabilities, reasoning level, temperature where supported, output token limit, the model per provider, a fallback chain within the same provider, and the evaluation report that admitted each (seat, model) pair (rule 40). It changes by commit only, and CI refuses a change whose evaluation report is missing or failed.
   - **One provider per installation in Phase 1.** The installation setting `llm_provider` (from `NATIVEFLOWS_LLM_PROVIDER`) selects the adapter for every seat. In Phase 1 it accepts only `anthropic`, the configured cloud provider; startup refuses any other value. The endpoint and API key come from the deployment's secret store, are read only by the gateway process, and never appear in a prompt, log or span. Fallback chains never cross providers in Phase 1.
   - **The local option.** Spec 17 says Phase 1 has no local models. The `local` adapter is designed but not enabled. Whether Phase 1 may use a local provider at all, and whether it may then receive personal values, is the author's (open question; scope). Until then, with the switch on, personal values are stripped from every request (rule 9).
   - **Off.** `llm_provider` unset means the LLM is off. Every agent mode is then `off`, and every operation still works by hand (Principle 12).

   Note ([ADR-0057](0057-document-intake-and-extraction.md), proposed 2026-11-15): the seat class `extraction_vision_personal` (structured output, image and PDF input, data class `personal`, no tools) is designed and usable for a company only while an active `data_processing_permission` covers it; otherwise its runs end `routing_blocked` with `data_processing_not_permitted`. Each provider endpoint declares its processing region and country in the adapter configuration, the provider registry the permissions name ([ADR-0057](0057-document-intake-and-extraction.md) rules 20, 21).

   Note ([ADR-0059](0059-ai-tuning-and-development-of-deterministic-functions.md), proposed 2026-11-15): each seat names a pinned model snapshot identifier, never an alias, so a provider's change under one name is a seat change with its evaluation (X7; rule 26).
6. Provider failures:
   - **Retries.** A retryable provider error (rate limit, overload, server error, timeout) is retried at most twice with exponential backoff, within the run's time budget (rule 23). Then the next model of the seat's fallback chain is tried once; a run of an assisted agent type tries only models in its setting's `promoted_seat_models` (rule 14). Then the call fails with `llm_provider_unavailable`. When an assisted run's promoted chain is exhausted, the run ends with outcome `provider_unavailable` and its work item goes back to people.
   - **Refusals.** A provider refusal is an invalid output (rule 35), with reason `refusal`.
   - **Circuit breaker.** Five consecutive failures of one (provider, model) within 60 seconds open its circuit for 5 minutes, per installation. Calls on an open circuit fail at once with `llm_provider_unavailable` and spend nothing.
7. Cost:
   - **Prices** per model are rows in `seatmap.yaml` (input, output, cache-read and cache-write price per million tokens, currency USD, `effective_from`).
   - **Computation.** The gateway computes each call's cost from the provider's reported usage and the price in force. Cost is an operational figure in `cost_amount` (domain `types.amount`) with `cost_currency` `USD`, exempt from telemetry rule 11 as ADR-0038 rule 10 allows. It never enters the books.
   - **Token counts** before a call use the adapter's counter (the provider's count endpoint, or a conservative estimate of 1 token per 3 characters for `local`), for the reservation of rule 23.

**Data labels and routing**

8. Prompts are rendered by the gateway, never assembled by workflow code:
   - **Templates** (rule 13) declare their inputs: each is a field path from a query result model, or a literal of the template.
   - **Context items.** Workflow code passes context items: `(field path, row reference, value)` taken from query results, plus the label, field class, `is_untrusted` and `is_secret` attributes the registry declares for that field. Code never passes a free string. A value derived from another (a token, a handle, an extract) keeps the source row of the value it came from.
   - **Rendering.** The gateway fills the template from the items and adds, around each untrusted value, a fixed delimiter and the instruction that text inside it is data, not instructions. This lowers injection risk; it is not the control. The controls are taint (rules 25–28), fixed tools (rule 29) and checks (rule 36).
   - **Tool results.** What a model-called read tool returns (rule 32) comes back through the dispatcher's query path, with its taint and scope rules, and reaches the model as context items with their labels, like any other input.

   Note ([ADR-0057](0057-document-intake-and-extraction.md), proposed 2026-11-15): a rendered page image is a context item of kind `attachment_page`, carrying its attachment's label as a whole; the gateway sends or refuses it whole. Untrusted text also gets a marker between words (datamarking), which the template states. For extraction fields, the attribute the dispatcher reads for taint is the trust computed by `extraction_field_trust` ([ADR-0057](0057-document-intake-and-extraction.md) rules 17, 18, 21).
9. Labels and the routing switch:
   - **Per value.** The gateway evaluates each item's label per row, with row conditions such as partner kind (ADR-0019 rule 7). An unknown kind counts as personal.
   - **`routing_switch`** is a company setting (change-tracked, ADR-0038 rule 3, so whoever turns it on or off is recorded as accountable; spec 17). Default off.
   - **Switch on (Phase 1).** Before sending, the gateway replaces every `personal` and `sensitive_personal` value with a typed placeholder, `[personal:<table>.<field>]`. It then scans the rendered request for the exact text of every removed value, and rejects the request with `llm_routing_refused` if any remains. An input that the template declares `maskable` (the column samples of the data migration agent) is replaced instead by a shape mask: each upper-case letter by `A`, every other letter (lower-case or without case) by `a`, every Unicode digit by `9`, other characters kept, so only the character classes and the length leave. A step whose template marks a removed input as required is not sent at all. The run then ends with outcome `routing_blocked` and leaves its work item to people.
   - **Sensitive personal** values are never sent to any model in Phase 1, whatever the switch says. No Phase 1 workflow needs them.
   - **Seat data classes.** Each seat declares in `seatmap.yaml` the highest label it may receive, from spec 17's "data visible" column: `internal` for the non-personal seats, `personal` for the seats with personal data, `per_routing` for drafting and data Q&A (personal when the switch is off). The gateway removes values above the seat's class whatever the switch says, so a step that needs personal values uses a personal seat. The data migration seat is `personal`, and personal-labelled column samples go to no other seat.
   - **Labels fixed here.** `bank_statement_line` description, counterparty name and counterparty account are `personal`, because a payer may be a person. A value a step extracts keeps the label of its source field.
   - **Embeddings** are after Phase 1 (spec 13); the same rules will apply.

   Note ([ADR-0057](0057-document-intake-and-extraction.md), proposed 2026-11-15): the core registers the regime setting `data_processing.policy` without a default (per data class: allowed or not, and whether processing in another country needs a recorded assessment); a regime that declares none fails closed. The gateway evaluates it with the company's `data_processing_permission` rows for whole-attachment items and the vision seat class, in every run mode, golden-set replays and evaluations included; whether it applies to field-level personal values is an open question ([ADR-0057](0057-document-intake-and-extraction.md) rule 20).

   Note ([ADR-0063](0063-configurable-policy-settings.md), proposed 2026-11-15): the gateway applies the regime policy and the company's `data_processing_permission` rows to every request carrying a personal value, field values included: without a permission the values become placeholders or shape masks and a step that needs one ends `routing_blocked`; `data_processing.never_send_fields` only narrows; the switch stays the kill switch (rule 15).
10. Processing log (ADR-0019 rule 11; spec 17 "logging always on"):
    - **When.** Every call that sends at least one personal value, with the switch on or off.
    - **What.** One `personal_data_processing_log` entry per call: purpose (agent type and step code), provider, model, whether the provider is local, and the list of (table, field, row ID) sent. Values are never logged.
    - **Order.** The entry and the call's `llm_request` step row are committed before the request is sent. If either insert fails, the call is not made.
11. Minimization and secrets:
    - **Only declared fields.** A template receives only the fields it declares, never whole records. Where the model only needs to tell records apart, items carry short handles (`r1`, `r2`) that the runtime maps back, not names or IDs.
    - **Secrets.** Fields that hold secrets (token hashes, TOTP and OIDC secrets, webhook credentials, ADR-0044 rule 17) carry the schema attribute `is_secret`. No view and no query result model returned to an agent run contains one (a registry CI check), and the gateway rejects an item with `is_secret` with `llm_routing_refused`.
    - **Canary tests.** CI seeds canary values in secret fields, and in personal fields of a company with the switch on, runs every golden case through the `stub` adapter, and fails if any canary appears in a recorded request, a step row, a span or a log line.

**Agent types, prompts and modes**

12. Agent types are code, versioned as one artifact:
    - **Declaration.** Each workflow module `nativeflows.agents.workflows.<agent_type>` declares: `code`, `version` (semver), the ordered steps, the tool list (rule 29), the declared permissions (ADR-0017 rule 11), the work item kinds it may claim (ADR-0042 rule 10), `scope_kind` (`partner`, `import_batch`, `subject`) with its scope resolver (rule 15), the subject tables it accepts (rule 15), `may_read_untrusted`, the seat of each LLM step, its prompt templates and output schemas with their versions, its budget maximums (rule 22), and its evaluation suite with threshold (rule 39).
    - **Rows.** At startup the registry writes `agent_type` (`code`, `name`, `is_active`) and one immutable `agent_type_version` row per version (all of the above as data, plus a `content_hash`), like the generated catalogs. Nobody edits them.
    - **New versions.** Changing any declared element, template or schema changes the content hash. CI fails when the hash changes and the version does not, and a new version needs a passing evaluation (rule 40).
    - **Names.** `agent_type` codes are `snake_case` nouns of the workflow (ADR-0004): `customer_onboarding`, `quotation`, `bank_matching`, `purchase_invoice`, `planning`, `data_migration` (ADR-0051).

    Note: an agent type version also declares `field_classes` (default none), so a run sees a `cost` or `margin` field only when both its agent type and its human have the class; it declares no record scope, which comes from the human alone and is narrowed by the tainted scope. Its declared permissions are its tool list: one set, which ADR-0017 rule 11 calls the declared permissions and rule 29 the tool list, so rule 31's intersection is the tool list with the human's rights ([ADR-0054](0054-users-roles-and-authorizations.md) rule 16 note).

    Note ([ADR-0058](0058-configurable-workflows.md), proposed 2026-11-15): each claimable kind carries `wake_up`: `always`, or `configurable` (started only by a company's automation rule with action `start_agent`). A version may declare `configurable_triggers` (event type, subject table). The six agent types of [ADR-0051](0051-agent-workflows.md) keep every kind `always` and declare no trigger until the author decides (rule 7).

    Note ([ADR-0060](0060-agent-assisted-reporting-and-analysis.md), proposed 2026-11-15): the agent type `analysis` (scope kind `subject` on `analysis_question`, or on `analysis_example` for evaluation runs; `may_read_untrusted: false`; field classes `cost` and `margin`) also declares the analysis catalog hash it was evaluated with, so a catalog change is a new version (rules 20, 25).

    Note ([ADR-0063](0063-configurable-policy-settings.md), proposed 2026-11-15): a kind declared `configurable` takes the company setting `agents.<agent_type>.wake_up_mode.<kind>` (`always`, the default, `by_rule`, `off`); the quotation agent's `inbound_message_matched` and the purchase invoice agent's `supplier_invoice_received` are declared configurable in their next versions (rule 11).

    Note ([ADR-0064](0064-production-agent.md), proposed 2026-11-15): agent types `production` (scope `subject` on `production_order` or `production_version`, `may_read_untrusted: false`), `production_capture` (scope `subject` on one `production_order` resolved from a `document_extraction`, tainted at start) and `production_variance` (scope `subject` on `analysis_question` or `production_order`, field class `cost`), each with its leaf `agent_<agent_type>` (rule 1).
13. Prompt templates:
    - **Files.** `backend/nativeflows/agents/prompts/<agent_type>/<template_code>.md`, Markdown with front matter: `code`, `version` (semver), `seat`, `inputs` (field paths, with `required`), `output_schema` (pydantic model path and its version).
    - **Overlays.** Provider-specific wording is a small overlay file `<template_code>.<provider>.md` (spec 17). The base and overlay are hashed together.
    - **Versions.** CI fails when a template's content hash changes without a version change. A run records, per step, the template code, version and content hash.
    - **Language.** Templates are English (reading guide rule 6). Outputs that people read are written in the language the step's input names (a contact's `preferred_language`, else the company's), as an IETF language tag. No template or output schema fixes a list of languages.
14. Company settings and modes:
    - **`agent_type_setting`** (company data, change-tracked): agent type, `mode` (`off`, `shadow`, `assisted`), `workflow_owner_id` (the human runs from events and schedules act for, ADR-0017 rule 12; required unless `off`), lowered budget values, and `promoted_version` with `promoted_seat_models`: the agent type version and the (seat, model) pairs the evidence covered, set when the mode moves to `assisted`.
    - **Modes.** `off`: no runs. `shadow`: runs execute every command in simulate mode only, so nothing persists except their run records and denials; their would-be outputs are recorded for comparison (rule 41). Shadow runs bind their work item without claiming it, so people work on it as usual; the dispatcher skips the claim check for them because they only simulate. `assisted`: runs create drafts and change proposals. Agents never post (ADR-0043 rule 9, floor 4), so there is no further mode.
    - **Effective mode.** The stored mode is the person's choice, and no command changes it on its own. The runtime computes the effective mode at each start: an `assisted` type whose current version's behavior hash (its content hash without budget maximums) differs from that of `promoted_version`, or whose seat models are not all in `promoted_seat_models`, runs as `shadow`. So a new version, a constants change or a model change runs in shadow until a person promotes it again, while lowering budgets keeps it assisted.
    - **Commands.** `UpdateAgentTypeSetting` has effect class `master_data_change`, is change-tracked and `is_proposal_bound`, and is on no agent tool list (rule 30). A person may lower the mode or change other fields directly. A change that sets `assisted` is accepted only from the execution of an approved change proposal (ADR-0029 rule 3); otherwise it returns `proposal_required`. The person who submits the proposal vouches for its evidence, and a person other than the submitter approves it; an approval by the submitter returns `approver_is_submitter`. This is an exception to ADR-0043 rule 13's interim, which otherwise lets a person approve their own document. Default for every company: `off`.
    - **Frozen evidence.** `CreateAgentPromotionEvidence` (module `agents`, effect class `other`, a person's command) computes the evidence once, from `GetAgentShadowEvaluation` or, for data migration, from an attached rehearsal report (ADR-0051 rule 28). It writes an immutable `agent_promotion_evidence` row (owned by `agent_runs`): agent type, date range, the behavior hash and seat models it covered, the figures, the thresholds applied and `is_sufficient`. The proposal's `UpdateAgentTypeSetting` payload names that row. Creating the proposal refuses evidence that is not sufficient (`shadow_evidence_insufficient`). Executing it only checks that the agent type's current behavior hash and seat models still equal the row's, and fails with `promotion_evidence_stale` otherwise; it never re-reads live figures, so the plan hash stays stable between simulation, approval and execution.
    - **Visible drops.** `GetAgentTypeSetting` returns the stored mode, the effective mode and the reason they differ (`version_changed`, `seat_model_changed`). When the effective mode first differs from the stored mode for a company and agent type, `agents` raises one work item `agent_mode_degraded` (owner `company_owner`, key the agent type within the company, due `days:1`). It is checked at every `StartAgentRun` and by the daily `RunAgentQualityCheck`, and it resolves when the agent type is promoted again or its mode is lowered.

    Note: `UpdateAgentTypeSetting` needs `full` on the leaf `agent` (a declared minimum level), so `edit` there no longer gives it, and a change whose resulting `workflow_owner_id` does not hold `start_agent:<agent_type>` in the company is refused with `workflow_owner_not_permitted`. The leaf `agent` belongs to module `agents`, and each agent type has its own leaf `agent_<agent_type>` below it for `start_agent:<agent_type>` ([ADR-0054](0054-users-roles-and-authorizations.md) rule 24 note). "The interim, which otherwise lets a person approve their own document" is superseded by [ADR-0055](0055-approval-pools-and-stages.md) rule 7, condition 5, which excludes writers; `approver_is_submitter` stays, also in the small-company mode.

    Note ([ADR-0059](0059-ai-tuning-and-development-of-deterministic-functions.md), proposed 2026-11-15): this ladder is the pattern that [ADR-0059](0059-ai-tuning-and-development-of-deterministic-functions.md) rule 12 generalizes to every L1 and L2 artifact. An agent type version that declares its constants as a tunable parameter set includes the current version's `parameters_hash` in its behavior hash, so a promoted parameter set makes it run as `shadow` until it is promoted again (rule 7).

    Note ([ADR-0060](0060-agent-assisted-reporting-and-analysis.md), proposed 2026-11-15): the `analysis` agent type is a stated exception to the shadow comparison: in `shadow` it answers nobody and the daily job `RunAnalysisEvaluation` runs it on the company's verified examples, acting for each example's releaser; its promotion evidence is the version's CI evaluation report and, from 30 verified examples, that shadow evaluation (rule 25).

    Note (Design hardening, 2026-11-16): the `lowered_budget` values of `agent_type_setting` move to the settings registry as `setting_value` rows of scope `agent_type` (rule 22 note); `agent_type_setting` keeps the mode, the workflow owner and the promotion. A budget change is not an `UpdateAgentTypeSetting` change, and budget values stay outside the behavior hash, so the effective mode is unaffected.

    Note ([ADR-0065](0065-deterministic-auto-post-gateway.md), 2026-11-16 (proposed)): a fourth mode, `active`: `assisted`, and in addition the type's drafts of the document types named at promotion may pass the auto-post gateway as tainted drafts. The agent still only drafts (floor 4 of [ADR-0043](0043-policy-and-approval.md) rule 9). The version declares `auto_post_document_types`, otherwise `agent_mode_not_declared`. Setting `active` is a proposal that another person approves, from `assisted` at the same behavior hash and seat models, naming per document type an `agent_promotion_evidence` row with target mode `active` from `GetAgentDraftAcceptance` (at least ceil(3 / `auto_post.max_error_rate`) drafts over at least two calendar months, at least (1 - rate) posted unchanged, none to another partner); `agent_type_setting.active_document_types` records the types. The effective mode drops as today on a version or seat model change, and counts as `assisted` for the gateway while an `agent_quality_below_threshold` item is open. Lowering is direct. "Agents never post ..., so there is no further mode" now reads: there is no mode in which an agent posts ([ADR-0065](0065-deterministic-auto-post-gateway.md) rule 11).

**Runs**

15. Starting a run, `StartAgentRun` (module `agents`, effect class `other`; it writes through `agent_runs.contract.create_run`):
    - **Payload:** agent type, and either a `work_item_id`, or a subject (`subject_table`, `subject_id`) for a run a person starts without an exception.
    - **Who.** The wake-up consumer `agent_wake_up` (rule 16) for items of kinds the agent type declares, a schedule, or a person.
    - **The human acted for** follows ADR-0017 rule 12 and nothing else: a run a person starts acts for that person; a run from a schedule acts for the schedule's owner; a run triggered by an event or by incoming e-mail, which every wake-up is, acts for the owner of that workflow, the setting's required `workflow_owner_id`. For agent runs the "owner of that intake or workflow" is always that setting, so a mailbox owner or a statement's importer is never the human acted for by being one, and the sender of outside content never is. That human needs `start_agent:<agent_type>`.
    - **Actor.** From a wake-up or a schedule, `StartAgentRun` runs as actor `system` on behalf of that human (ADR-0013 rule 9); from a person, as that person.
    - **Checks:** the mode is not `off` (`agent_mode_off`); the daily budgets are not exhausted (`agent_budget_exceeded`, rule 24); the item's kind is declared by the agent type (`agent_kind_not_declared`); the subject's table is one the agent type accepts (`agent_kind_not_declared`); the scope resolver finds a scope (`agent_scope_unresolved`).
    - **Claim.** The handler claims the work item for the run (ADR-0042 rules 9–11), or creates and claims an `agent_task` item for a subject (ADR-0042 rule 11). A held claim fails with `work_item_claimed`. A shadow run binds the item without a claim (rule 14).
    - **Scope.** The handler binds the run's scope by the agent type's scope resolver: a pure function of the subject's stored, trusted fields, such as the interaction's matched `partner_id` (ADR-0019 rule 15) or the import batch. It never reads an `is_untrusted` field. If the resolver finds no scope, the command fails with `agent_scope_unresolved`, the wake-up consumer treats that as a skip rather than a retry, and the item stays with people. The scope never changes during a run.
    - **Taint at start.** The handler decides from the subject row itself, whoever starts the run, a person included. The run starts tainted (`tainted_at` is its start) when its work item has `is_tainted` (ADR-0042 rule 15; `taint_source_kind` `work_item`), or when its subject row is outside content (`outside_subject`): an inbound interaction (the subjects of `inbound_message` and `interaction_unmatched`), an incoming e-invoice record, a bank statement line, an import batch or an import row, or any row whose `is_untrusted` is true. The registry marks these subject tables. So such a run reads nothing before it is tainted. An agent type only lists the subject tables it accepts; it does not decide taint. The kind `inbound_message` is renamed `inbound_message_matched` ([ADR-0052](0052-minimal-crm.md) rule 15).
    - **Result.** An `agent_run` in state `queued`, and the event `AgentRunStarted`.

    Note ([ADR-0057](0057-document-intake-and-extraction.md), proposed 2026-11-15): `document_extraction` is an outside-content subject table: a `document_reader` run on it starts tainted, and reads its words, fields, rule runs and pages, a reading put to the author ([ADR-0057](0057-document-intake-and-extraction.md) rule 11).
16. Executing a run:
    - **Wake-ups.** The consumer `agent_wake_up` reacts to `WorkItemRaised` for kinds an agent type declares, in companies where that type's mode is not `off`, and dispatches `StartAgentRun` (ADR-0013 rule 12; ADR-0042 rule 14). It skips `WorkItemRaised` events that carry an origin agent run (ADR-0013 rules 9, 11), so nothing in an agent's chain wakes an agent. Only raises wake agents, so a run that unclaims an item never wakes another (no loop). For a tainted item this stays within ADR-0013 rule 11, because the run starts tainted (rule 15) and can only draft.
    - **No agent wakes an agent.** A kind that a command on any agent tool list can raise may not be declared by any agent type (a registry check), like `agent_task` (ADR-0042 rule 11).
    - **Runner.** The `external` consumer `agent_runner` of `AgentRunStarted` runs on a new queue `agents` (ADR-0013 rules 10, 13). Its delivery lease is 5 minutes, and the live runner extends `locked_until` every 60 seconds, a technical timer (ADR-0013 rule 7), so a dead runner is noticed within 5 minutes. It calls the gateway with no transaction open.
    - **Run token.** At execution start the runner mints a run token (ADR-0017 rule 3) bound to the run, agent type version, tool list, human acted for and work item, expiring at `started_at` plus the run's time limit plus 60 seconds and revoked when the run ends. A retry revokes the earlier token and mints a new one with the same expiry. The runner dispatches every tool call in process with it (ADR-0008 rule 8).
    - **One call at a time.** A run's LLM calls and tool calls are sequential, never parallel, so taint, budgets and replay each have one order.
    - **Claim renewal.** Each command renews the claim (ADR-0042 rule 10); the runner also renews it before each LLM call that would outlast it.
    - **Crash and retry.** If the runner dies, the delivery is retried (ADR-0013 rule 7), at most 3 attempts. The retry continues the same run:
      - it settles every reservation the dead attempt left open at its reserved amount, recorded on the `llm_request` row, the worst case, because the provider may have charged it;
      - it replays the recorded steps through the `replay` adapter (rule 38) up to the last recorded response, then continues live; a request row without a response row is a call with an unknown outcome, and it is made again;
      - a replayed request whose hash differs from the recorded one (the data changed meanwhile) stops the run with outcome `resume_diverged`;
      - the time limit counts from `started_at`, the crash included, so a retry that cannot finish in time ends with `time_exceeded`.

      Command idempotency keys (rule 32) and draft keys (ADR-0030 rule 11) make repeated commands return their first results. After the third failed attempt the delivery is held (ADR-0013 rule 8), and the run reaper, a system job of module `agents` on queue `jobs` (actor `system`, on behalf of the run's human), records outcome `crashed` through `CompleteAgentRun`.

    Note ([ADR-0058](0058-configurable-workflows.md), proposed 2026-11-15): `agent_wake_up` skips kinds that an agent type declares `configurable`. A rule's `start_agent` acts for the setting's `workflow_owner_id`, as rule 15 says, and the rule's owner also needs `start_agent:<agent_type>`. It may start the agent on a tainted or outside-content subject when the agent type accepts that subject table, the run starting tainted, and it is skipped on events that carry an origin agent run. A run started from an event, by a wake-up or a rule, inherits the event's causation chain and depth, and its tool calls and its drafts' events carry them (rules 7, 9, 12).

    Note ([ADR-0063](0063-configurable-policy-settings.md), proposed 2026-11-15): `agent_wake_up` skips a configurable kind only while the company's wake-up mode is `by_rule` or `off`; under `always`, the default, it starts the agent as before (rule 11).
17. Ending a run:
    - **`CompleteAgentRun`** (effect class `other`), dispatched by the runner in the transaction that marks the delivery done (ADR-0013 rule 10). It records the outcome, totals and output references, unclaims the work item (or resolves the run's `agent_task`), revokes the run token and emits `AgentRunCompleted`. It runs as actor `system` on behalf of the run's human, with the run as `origin_agent_run_id`, so the items it raises carry the run's taint (INV-210). The run's own tool calls run as actor `agent` with the run token.
    - **States:** `queued` → `running` → `completed` | `stopped` | `canceled`.
    - **Outcomes:**

      | Outcome | State | What happens to the work item |
      | --- | --- | --- |
      | `drafted` (drafts or proposals made), `no_action` (nothing to do), `not_applicable` (not this workflow's case) | `completed` | Unclaimed, back to its owner, with links to drafts and a note |
      | `routing_blocked` (rule 9) | `completed` | Same |
      | `claim_lost` (a person took the item) | `stopped` | Stays with that person |
      | `budget_exceeded`, `time_exceeded`, `output_invalid`, `provider_unavailable`, `resume_diverged`, `crashed` (third failed attempt) | `stopped` | Unclaimed; `agent_run_stopped` raised (rule 55) |
      | `denials_repeated` (rule 33) | `stopped` | Unclaimed; `agent_denials_repeated` raised |
      | `canceled` | `canceled` | Unclaimed |

    - **Cancel.** `CancelAgentRun` (a person with `start_agent:<agent_type>`, or the company's owner) stops a run between steps. The runner checks the state before every step.

    Note: `CancelAgentRun` needs `start_agent:<agent_type>` of the run's agent type or the capability `cancel_agent_runs` (`full` on `agent`), which replaces "or the company's owner" ([ADR-0054](0054-users-roles-and-authorizations.md) rule 24 note).

    Note ([ADR-0060](0060-agent-assisted-reporting-and-analysis.md), proposed 2026-11-15): the `analysis` agent type adds the outcome `answered` and the abstentions `ambiguous_term`, `ambiguous_member`, `out_of_coverage`, `not_permitted`, `data_not_ready` and `too_broad`, all in state `completed`, which `ck_agent_run_outcome` of DS-05-platform.sql allows; the run's `agent_task` item is resolved, and a stopped run sets its question to `failed` (rules 21, 24).
18. `agent_run` columns (company data, not partitioned, never deleted while a version or event refers to it):
    - **Identity:** `id`, `company_id`, `agent_type_code`, `agent_type_version`, `seatmap_hash`, `mode` (`live`, `shadow`, `replay`, `evaluation`), `replay_of_run_id`.
    - **Trigger and actor:** `trigger_kind` (`work_item`, `person`, `schedule`), `work_item_id`, `subject_table`, `subject_id`, `started_by_kind` and `started_by_id`, `on_behalf_of_id`.
    - **Scope and taint:** `scope_kind`, `scope_partner_id`, `scope_import_batch_id`; `tainted_at`, `taint_source_kind` (`work_item`, `outside_subject`, `untrusted_field`, `tainted_row`, `outside_attachment`), `taint_source_table`, `taint_source_id`.
    - **Budget:** `budget` (the limits in force at start, as JSON), and the totals `llm_call_count`, `tool_call_count`, `input_tokens`, `output_tokens`, `cache_tokens`, `rows_read`, `denial_count`, `cost_amount`, `cost_currency`.
    - **Timing and result:** `state`, `outcome`, `started_at`, `ended_at`, `duration_ms`, `input_refs` and `output_refs` (typed references: table, ID, role), `trace_id`, `recorded_at`.

    Note (catalog review, 2026-11-15): column names in DS-05-platform.sql follow ADR-0004 rule 13: `input_token_count`, `output_token_count`, `cache_token_count` and `row_read_count` on `agent_run` for `input_tokens`, `output_tokens`, `cache_tokens` and `rows_read`; `agent_run_step` records `input_token_count`, `output_token_count`, `cache_read_token_count` and `cache_write_token_count`. The budget limits keep their names (`max_input_tokens` and the like).
19. `agent_run_step` (company data, append-only, partitioned by month on `id`, ADR-0002 "agent run logs"):
    - **Columns:** `id`, `company_id`, `agent_run_id`, `ordinal`, `step_code`, `kind` (`llm_request`, `llm_response`, `tool_request`, `tool_result`), `request_step_id` (on a response or result row, its request row), `attempt`, `recorded_at`, `duration_ms`.
      - **LLM request and response rows:** `seat`, `provider`, `model`, `template_code`, `template_version`, `template_hash`, `output_schema_version`, `request_hash`, `reserved_amount` and `request_body` on the request row and `response_body` on the response row (as sent and received, after redaction), `context_refs` (the source row of every context item), `validation_errors`, token counts, `cost_amount`, `personal_fields_sent` and `redacted_fields` (table, field, row ID lists), `personal_subject_refs` (the data subjects whose values were sent).
      - **Tool request and result rows:** `tool_name`, `schema_version`, `mode` (`simulate`, `execute`, or `query`), `request_refs` (the source row of every reference in the input), `result_refs` (the table and ID of every row returned or written), `error_code`, `plan_hash`, `audit_record_id`.
    - **Platform records.** Run rows after start, steps, taint marks and budget usage are written by the runtime through the `agent_runs` contract in their own short transactions, like idempotency and denial records (ADR-0008 rule 16; ADR-0038 rule 5). They are not commands, and no client can write them. Starting, completing and cancelling a run are commands.
    - **Append-only.** A row is never updated: a request row is committed before its call and the response or result row after it.
    - **Bodies stay local.** Bodies are stored in the database only, never sent to telemetry (spec 17).
    - **Retention.** Partitions older than `agent_run_step_retention_days` (installation setting, default 400, flagged for the author) are dropped. The `agent_run` row stays.

    Note ([ADR-0057](0057-document-intake-and-extraction.md), proposed 2026-11-15): for every extraction field a step receives, `context_refs` also records the trust the dispatcher served and the rule run number it used, and whether the raw text or evidence was served; INV-642 checks those values ([ADR-0057](0057-document-intake-and-extraction.md) rule 17).
20. Queries, export and erasure:
    - **Queries.** `ListAgentRun` and `GetAgentRun` (with its steps, paged), each with its generated permission. Request and response bodies are returned only to holders of the capability `read_agent_run_bodies` (ADR-0017 rule 4; in the `owner` template only); access to bodies is by that capability alone. They are on no agent tool list (rule 30).
    - **Export.** `ExportCompanyData` includes both tables (ADR-0044 rule 17).
    - **Erasure.** `EraseDataSubject` (ADR-0019 rule 10) blanks `request_body` and `response_body` of every step whose `personal_subject_refs` or `personal_fields_sent` names the subject or one of its rows, keeping the rows and counts.

    Note: `read_agent_run_bodies` is `full` on its own authorization leaf `agent_run_bodies`, which every role template except `owner` sets to `none` ([ADR-0054](0054-users-roles-and-authorizations.md) rules 8, 11).
21. Telemetry (ADR-0038 rules 10–11):
    - **Spans.** One span per gateway call and per tool call, as children of the run's span (`agent_run.trace_id`). Allow-listed attributes: agent type and version, step code, seat, provider, model, template code and version, token counts, cost, duration, attempt, outcome or error code, and `is_tainted` as a boolean. Never text, values or IDs other than the trace ID.
    - **Metrics:** tokens and cost per agent type (ADR-0038 rule 10), runs by outcome, budget trips, denials per agent type, retries per step, and the deterministic share per workflow (spec 14). Labels are codes only.

**Budgets**

22. Limits:
    - **Per run,** declared by the agent type version as maximums (values in ADR-0051): `max_llm_calls`, `max_tool_calls`, `max_input_tokens`, `max_output_tokens`, `max_cost`, `max_seconds`, `max_rows_read`.
    - **Per company, agent type and business date:** `daily_max_cost` and `daily_max_runs`, declared by the agent type version.
    - **Per company and business date:** `agents.company_daily_max_cost` (company setting, default USD 50).
    - **Per installation and day:** `agents.installation_daily_max_cost` (installation setting, default USD 200). It changes only through installation configuration, never by a company setting or a command, and every change is logged with the operator who made it.
    - **Lowering only.** Company settings may lower any of these, never raise them. Raising a value set here is the author's (ADR-0005 item 7). The values are the agent's proposal, flagged for the author (open question), and every agent type's daily cost stays below the company's daily cap.
    - **Test runs** keep ADR-0003 R6. Evaluation runs have their own cap (rule 40).

    Note: every budget day is the company's business date (`clock.today`, ADR-0007 rule 15), the installation's daily row included: it is keyed by the business date of the company whose run reserves, so "per installation and day" means per business date.

    Note (Design hardening, 2026-11-16): the customer sets the caps. The author has directed this (2026-11-16); it replaces "Lowering only", "Raising a value set here is the author's (ADR-0005 item 7)" and the open question on these values. Every cost and run limit is a definition of the settings registry ([ADR-0063](0063-configurable-policy-settings.md) rule 1), its `source` naming this rule:
    - **Installation maxima,** set at deployment by the operator and recorded as `setting_value` rows naming the operator account, a raise approved by a second operator account (ADR-0063 rule 2): `agents.installation_daily_max_cost` (default USD 200), and the installation value of `agents.company_daily_max_cost`, which is the maximum of every company's cap; when the deployment names none, `agents.installation_daily_max_cost` is that maximum.
    - **Company values,** within those maxima: `agents.company_daily_max_cost` (default USD 50); per agent type `agents.<agent_type>.daily_max_cost` and `agents.<agent_type>.daily_max_runs`; per run `agents.<agent_type>.run_max_llm_calls`, `agents.<agent_type>.run_max_tool_calls`, `agents.<agent_type>.run_max_input_tokens`, `agents.<agent_type>.run_max_output_tokens`, `agents.<agent_type>.run_max_cost`, `agents.<agent_type>.run_max_seconds` and `agents.<agent_type>.run_max_rows_read`. The core default of the agent-type keys is `unset`, meaning that the agent type version's declared value applies, and a first company value is compared with that declared value (ADR-0063 rule 3). The version still declares every per-run value as a ceiling for safety: a company value above it returns `setting_out_of_bounds`, as does a company cap above the installation maximum.
    - **The reserve pool.** `agents.internal_reserve_share` (company, default 0.40, bounds 0 to 0.9) is the share of the company's daily cap that only internal agent types may use: a version is internal when it declares `may_read_untrusted: false` and accepts no subject that is outside content, so its runs are never tainted by design (for example `planning`, `production` and `analysis`). Agent types that read outside content share the remainder, (1 − share) × the company cap; internal agent types may use the whole cap. Rule 23's note gives the check.
    - **Change path** (ADR-0063 rule 3): lowering a cap or limit, or raising the reserve share, is immediate, by one person holding `edit` on the leaf `agent`. Raising a cap or limit, or lowering the reserve share, is a loosening: a change proposal approved by another person holding `agent` at `full`, logged in `setting_value`. As for every loosening, a one-person company cannot raise them.
    - **Hard locks** stay: the worst case is reserved before every call (rule 23); a run that would exceed any cap or limit stops (rule 24); no company value lies above the installation maximum, refused by the `setting_value` trigger and applied again at read time (ADR-0063 rule 1); no setting turns reservation off.
    - **Lowering reaches running runs.** `agent_run.budget` keeps the per-run values in force at start, and each reservation checks the run against the lower of that snapshot and the values in force.

    The declared values of [ADR-0051](0051-agent-workflows.md) rule 9 and of later agent types stay the core defaults of the daily values and the ceilings of the per-run values.
23. Accounting by reservation:
    - **Before every LLM call** the runtime computes the worst case: counted input tokens times the input price, plus `max_output_tokens` times the output price. `agent_runs.contract.reserve_budget` adds it, in one statement each, to the run's totals and to `agent_budget_usage` rows (company, agent type, business date; company, business date; installation, day), each guarded by `reserved + spent + amount <= limit`. If any guard fails, nothing is reserved, the call is not made, and the run stops with `budget_exceeded`.
    - **After the call,** `settle_budget` replaces the reservation by the actual cost. A failed call settles at the provider's reported usage, or zero when it reports none; a call whose outcome is unknown settles at its reserved amount (rule 16).
    - **Counts.** LLM calls, tool calls and rows read are checked the same way before each call (rows against the query's `limit`).
    - **Time.** Before each step the runtime checks the remaining time; a step that cannot start in time ends the run with `time_exceeded`. An LLM call's timeout is the remaining time.
    - **No overshoot.** So no run and no daily row ever exceeds its limit, also with runs in parallel. INV-212 checks it, and the lab checks interleavings.

    Note (Design hardening, 2026-11-16): each guarded statement first sets the row's `limit_amount` (and `run_limit_count`) to the limit in force for that business date from `registry.contract.get_setting`, so a lowering applies at the next reservation, and a row whose spent amount already exceeds a lowered limit accepts nothing more. A run of an agent type that reads outside content, and any run that is tainted when it reserves, also reserves on the row of scope `company_outside_content` (company, business date), whose limit is (1 − `agents.internal_reserve_share`) × the company cap in force, rounded down to the cent; an internal run reserves on its agent type, company and installation rows only, so the reserve stays free for it. All guards of one call run in one transaction: if any fails, nothing is reserved and the run stops with `budget_exceeded`. INV-212 covers the new row like every `agent_budget_usage` row; [DS-05-platform.sql](../design/DS-05-platform.sql) adds the scope kind.
24. Circuit breakers (spec 03 rule 8):
    - **Daily.** When a daily guard fails, `StartAgentRun` for that scope returns `agent_budget_exceeded` until the next business date, the wake-up consumer skips, and one `agent_budget_exhausted` item (per company, agent type and date) tells the company's owner. Work items stay with people (Principle 12).
    - **Provider.** Rule 6's circuit.
    - **No loops.** A stopped run is never restarted automatically. A new run on the same item needs a person, or a new raise.

    Note (Design hardening, 2026-11-16): when the outside-content pool trips, `agent_budget_exhausted` uses the open key `outside_content:<business date>`, and internal agent types keep running on the reserve until the company row trips.

**Taint**

25. Run taint (ADR-0029 rule 10):
    - **`agent_run.tainted_at`** is set once and never cleared, with its source columns. It is set at start (rule 15), or by the dispatcher's query path just before it returns to the run any of: a non-null `is_untrusted` field; a row whose effective `is_tainted` is true; a work item with `is_tainted`; the content of an attachment whose source kind is outside content.
    - **Commit first.** The dispatcher calls `agent_runs.contract.mark_run_tainted` in its own committed transaction before it returns the result. If that commit fails, the result is not returned. So every later command of the run starts after `tainted_at`, and `recorded_at` comparisons (INV-88) hold.
    - **Inputs after taint.** From `tainted_at` on, the runtime refuses, before the gateway call or the dispatch, a context item or a command input whose recorded source row (rule 8; `context_refs`, `request_refs`) is outside the tainted read scope (rule 27), also when the row was read before the taint, with `tainted_read_out_of_scope`. Only the runtime knows that provenance. A row reached through recorded provenance from a row in scope is in scope, for example the item behind the `item_id` of the partner's `partner_item` row.
    - **The dispatcher's check.** As a second line, the dispatcher checks every reference-typed ID in a tainted run's payload whose table has a partner or import batch scope column, or is a document, against the run's scope and its drafts (rule 27). References to tables without such a column (items, units) are covered by the runtime's provenance check. The command envelope of ADR-0008 does not change.
    - **Aggregates.** A deterministic aggregate (a sum, count or balance) computed over rows that include tainted versions does not taint the run: taint guards against untrusted text, and an aggregate carries none. Individual rows of tainted versions still taint. This reading is flagged for the author (open question).
    - **One place.** This applies to every query result returned to a run: views, module queries and the results and check details of commands, using the result model's field attributes. It does not depend on the agent asking nicely.

    Note: a generated file (attachment source kind `generated`) whose rendered instance held a non-null `is_untrusted` field carries `contains_untrusted`. Returning its content to a run taints the run as an attachment from outside content does, with `taint_source_kind` `untrusted_field` and source table `attachment` ([ADR-0049](0049-statutory-reporting-and-printing.md) rule 28).
26. A tainted run's commands:
    - **`is_draft_only`** is a new registry attribute (ADR-0008 rule 1) of commands that only create or update drafts, change proposals, work item notes or suggestion fields. Such a command is never of effect class `posting`, `master_data_change` or `outbound_send`, and never a `Submit`, `Post` or `Issue`; CI checks this.
    - **What it may run:** only commands registered `is_draft_only`. The dispatcher rejects any other command from a tainted run with `tainted_run_not_allowed`, before policy, with a denial record. This adds to the structural guards: such commands are not on agent tool lists (rule 30), agents' posts are `human_post` (ADR-0043 rule 9, floor 4) and master data needs a proposal (ADR-0029 rule 4).
    - **Its writes are tainted:** document versions (INV-88), events (ADR-0013 rule 11), work item raises and notes (INV-210).

    Note ([ADR-0060](0060-agent-assisted-reporting-and-analysis.md), proposed 2026-11-15): `UpdateAnalysisAnswer` is registered `is_draft_only` although it writes no draft: it writes once to the run's own question row, which only the asker reads, and changes no document, master data or outside party, so it carries no more risk than a work item note (rule 21).
27. Tainted read scope, the literal spec 03 rule 1 (ADR-0029 rule 14):
    - **A tainted run reads only:**
      1. rows in its scope: rows whose partner column equals `scope_partner_id` (scope `partner`), rows of `scope_import_batch_id` (scope `import_batch`), or the run's subject row (scope `subject`);
      2. its work item, the item's evidence links and its notes;
      3. documents and change proposals that it or an earlier run of the same work item and agent type wrote, with their plans and check results;
      4. reference data: the core catalogs (system accounts, transaction keys, movement types, work item kinds, currencies, units), the active package's data (chart template, administrative units, settings), and registry metadata (schemas, view declarations).
    - **Everything else** returns `tainted_read_out_of_scope`, with a denial record. Company master data outside the scope (other partners, the item catalog, price lists, the company's chart) is not reference data.
    - **Declared scope columns.** Every view and every query result model declares its partner column and import batch column, or none. A query without the run's scope column is refused for a tainted run.
    - **Redaction of command responses.** In responses to a tainted run, check details and plan parts that name records outside the scope are replaced by `{"redacted": true}` with counts (for example, `partner_duplicate_suspected` gives `{"redacted": true, "candidate_count": 2}`). The plan hash is still computed over the full plan (ADR-0008 rule 12).
    - **Inputs, not only reads.** The same scope bounds what a tainted run may put into a prompt or a command (rule 25), so rows read before the taint cannot be used after it.
    - **Flagged.** Scope kind `subject`, items 2, 3 and 4, and the data migration agent's reading of its migration's mapping profile (ADR-0051 rule 26) are this ADR's readings of the literal rule. Through item 3 a tainted run also sees the server-computed prices and taxes in its own draft's plan. The author's answer to the open question may change all of them.

    Note ([ADR-0063](0063-configurable-policy-settings.md), proposed 2026-11-15): item 4 also covers declared projections (`tainted_projection` on a query's result model: closed shapes and internal names only, at most 20 rows per call and 10 calls per run) while `agents.tainted_reference_reads` reads `declared_projections`, the default; the run stays tainted (rule 16).

    Note ([ADR-0066](0066-work-cases.md), 2026-11-16 (proposed)): work cases do not widen item 2: a run reads its work item, the item's evidence links and its notes, never the work case the item belongs to. `GetWorkCase` and `ListWorkCaseTimeline` are on no agent tool list in Phase 1 ([ADR-0066](0066-work-cases.md) rule 19).
28. Untrusted fields:
    - **Omitted by default.** Views and query result models omit `is_untrusted` columns unless the request sets `include_untrusted: true` (ADR-0029 rule 10). Listing documents therefore does not taint.
    - **Agent types that must stay clean** declare `may_read_untrusted: false` (for example `planning`). For their runs, `include_untrusted` returns `untrusted_read_not_allowed`, and rows that would taint them are left out, with `is_taint_filtered: true` in the response.
    - **Numeric projections.** `ListPegging` and `demand_supply_overview` return rows of tainted versions as a numeric-only projection: IDs, quantities, dates and states, no free text. Like aggregates (rule 25), such rows do not taint, so the clean planning agent is not filtered on them (flagged, open question). The projection applies only to agent-run callers; people see full rows within their permissions.

    Note ([ADR-0060](0060-agent-assisted-reporting-and-analysis.md), proposed 2026-11-15): `ListAnalysisCellRow` returns a numeric projection to agent runs as `ListPegging` does: IDs, document numbers and types, dates, accounts and contributions, no free text; such rows do not taint and are not filtered from a clean run, so a cell still equals its drill rows (rule 16).

**Tools and permissions**

29. Tool lists (spec 03 rule 2; ADR-0008 rule 6):
    - **What.** An agent type version's tool list names registered queries and commands. Nothing is inferred from a prompt.
    - **Definitions.** Tool definitions are generated from the registry with the same names (`snake_case`, ADR-0004 rule 19) and JSON Schemas as the MCP tools. NativeFlows's own runs call the dispatcher in process; outside MCP clients use the MCP transport with their own credentials.
    - **Checked per call.** The dispatcher checks every call against the run token's tool list and rejects others with `tool_not_allowed`, with a denial record.

    Note: the tool list is step 2 of the dispatcher's check order, first after the credential and before `human_only`, `proposal_required` and permission ([DS-04](../design/DS-04-command-envelope.md#dispatcher-check-order)). Allowed-target commands of ADR-0029 rule 2 (effect class `master_data_change` or `is_proposal_bound`) are kept off tool lists too, a registry check that INV-214 covers: agents reach them only through `CreateChangeProposal`, so an agent run that calls one directly gets `tool_not_allowed`, and `proposal_required` is met by consumer commands carrying an origin run (EC-56).

    Note ([ADR-0059](0059-ai-tuning-and-development-of-deterministic-functions.md), proposed 2026-11-15): generated tool definitions state each tool's side-effect class (`read` for queries, `draft` for `is_draft_only` commands, the only classes agents get) and its allowed states as preconditions. The dispatcher enforces them, not the description (X2; rule 26).
30. Never on a tool list (a registry CI check and INV-214):
    - commands of effect class `posting`, and every `Submit<Type>`, `Post<Type>` and `Issue<Type>`: people submit, post and issue agent drafts, which in Phase 1 also covers the release of production orders by `Submit` (ADR-0034 rule 5). Agents create change proposals as drafts; a person submits them (ADR-0029 rule 3), and a person other than the human the run acted for approves them (ADR-0017 rule 16);
    - commands registered `human_only` or of effect class `outbound_send`;
    - `Approve<Type>`, `Reject<Type>`, `ClearTaint`, `ConfirmAutoPost`, `UpdateAgentTypeSetting`, `CreateAgentPromotionEvidence`, policy rule and procedure commands, role assignments;
    - `StartAgentRun`, `CancelAgentRun`, `CompleteAgentRun` (no agent starts agents), and claim, assign and resolve commands of work items (the runtime manages the run's claim);
    - audit queries (ADR-0038 rule 7), `ListAgentRun`, `GetAgentRun`, `ListAllowedCommand`, `GetSessionContext`, `GetPolicyEvaluation`, and `CreateListExport` (rule 54).

    Note ([ADR-0057](0057-document-intake-and-extraction.md), proposed 2026-11-15): also never on a tool list: `SetDataProcessingPermission` and `EndDataProcessingPermission`; `CreateExtractionFields` is on `document_reader`'s list for workflow code only ([ADR-0057](0057-document-intake-and-extraction.md) rules 11, 20).

    Note ([ADR-0059](0059-ai-tuning-and-development-of-deterministic-functions.md), proposed 2026-11-15): also `CreateArtifactEvidence`, `SetArtifactVersionState`, `SetArtifactCurrentVersion`, `RecordGoldenCaseLabel`, `ListGoldenCaseLabel`, `CreateAutomationRule`, `UpdateAutomationRule`, `ConfirmAutomationRuleOwnership`, `CreateDecisionTable`, `CreateParameterSet`, `DisableAutomationRule` and `EnableAutomationRule`. Agents draft artifact versions only (rule 27; [ADR-0058](0058-configurable-workflows.md) rule 27).

    Note ([ADR-0060](0060-agent-assisted-reporting-and-analysis.md), proposed 2026-11-15): `ListAnalysisResultRow`, the list query through which people export analysis results, and `ListAnalysisQuestion` are on no tool list either (rules 14, 17).

    Note ([ADR-0064](0064-production-agent.md), proposed 2026-11-15): also never on a tool list: `TransferStockReservation` (accepted only from a change proposal's execution), `ImportOperationConfirmation` (an integration's command) and `RunProductionOrderCheck` (a system job) (rules 12, 24, 25; INV-730).
31. Effective permissions are the intersection of the agent type's declared permissions and those of the human acted for, re-evaluated at every call against current assignments, for permissions, record scope and field classes (ADR-0017 rule 11). A tainted run's read scope (rule 27) narrows that further. The tool list is a third limit: a tool must be on the list and allowed by the intersection.

    Note: agent types get no role assignments, so no further set of rights joins this intersection; the human's owner scope binds the run as their record scope does ([ADR-0054](0054-users-roles-and-authorizations.md) rule 16).

    Note ([ADR-0060](0060-agent-assisted-reporting-and-analysis.md), proposed 2026-11-15): for analysis plans the fact-view permissions and their read grants are those of the run's human alone: the `analysis` agent type holds no `List<fact view>` permission, and its limit on facts is that `EvaluateAnalysisPlan`, `GetAnalysisPlanExplanation`, `ListAnalysisCellRow` and `ListAnalysisDimensionMember` are on its tool list; field classes stay the intersection (rule 13).
32. LLM steps read, code writes:
    - **Read tools only.** An LLM step's tools are a subset of the tool list holding only queries. Commands on the list are called by workflow code, never chosen by the model.
    - **Every command** is built by workflow code from a validated output (rules 35–36), sent in simulate mode, checked against the step's deterministic expectations, then executed with the simulated `plan_hash` (Principle 2). In `shadow` mode the execute call is skipped.
    - **Keys.** Idempotency keys are `<agent_run_id>:<step_code>:<n>`. Drafts carry `origin_work_item_id`, `workflow_step` and `draft_ordinal` (ADR-0030 rule 11). A `duplicate_draft` on a re-run is read as "already done": the runtime continues with the draft it names.
33. Repeated denials (ADR-0017 rule 8):
    - **Stop.** The runtime counts every denial code returned to the run (any code of ADR-0038 rule 5, including those this ADR adds) in `agent_run.denial_count`. It does not count denial records, which are coalesced and may be dropped (ADR-0038 rule 5). The third denial stops the run with outcome `denials_repeated`.
    - **Signal.** `agent_denials_repeated` is raised for the company's owner, with the run and the denial codes as evidence. Workflow code is written so that a clean run gets no denials; CI fails a golden case that produces one.

    Note: the counted codes are those of [ADR-0038](0038-audit-and-observability.md) rule 5's note returned to the run. `llm_routing_refused` and `work_item_claim_lost` are not counted: they end the run with `routing_blocked` and `claim_lost`.
34. `ListAllowedCommand` stays people-only in Phase 1 (ADR-0040 rule 8). Agents plan from their fixed tool list and from simulate mode, whose refusals are recorded. This is the proposed answer to the open question.

**Structured outputs**

35. Output schemas:
    - **Every LLM step** declares a pydantic output model (unknown fields rejected, ADR-0008 rule 3) with a version. Output schemas never hold a field for the model's own confidence, score or probability (Principle 3); a CI check rejects field names `confidence`, `score`, `probability` and `certainty`.
    - **Validation.** The runtime parses and validates every output, also from providers that promise schema conformance.
    - **Bounded retries.** An invalid output, a refusal or a cut-off output gets at most two retries (three attempts), each with the validation errors (codes and paths, without echoing the invalid text) added to the request. Retries count against budgets.
    - **Then stop.** After the third failure the step fails with `llm_output_invalid`, and the run stops with outcome `output_invalid` (rule 17).
36. Deterministic checks after validation, per step (named in ADR-0051):
    - **References** in an output must be handles or IDs that the step's input contained. Anything else is rejected as invalid output.
    - **Codes** must exist in their catalogs; enumerations are closed.
    - **Stated values.** A value extracted from a document (a quantity in a request, a reference token in a bank description) must appear in its quoted source span in the input after normalization; otherwise it is dropped.
    - **No computation.** No output value becomes a price, tax, quantity to post, account or match score. Prices, taxes and accounts come from the deterministic functions that own them (ADR-0045 rule 4, ADR-0047 rule 16, ADR-0041, ADR-0015); a requested quantity is shown as stated by the customer.
    - **Free text** an output carries (an explanation, a quotation text) is checked: every number in it must equal a number of the step's input or of the draft. Customer-facing text is also checked by the outbound content check of ADR-0029 rule 14. Module `crm` owns that check (ADR-0029 rule 14) and exposes it as the query `GetOutboundContentCheck`. A module that owns customer-facing drafts, such as `sales`, may not import `crm` (same layer), so it declares an outbound-check hook that `crm` registers and `app` (layer 6) wires, the pattern of the policy evidence hook (ADR-0051 rule 18). The handler of every command that creates or updates a customer-facing draft calls the hook, so a finding is the check result `outbound_content_flagged` in that command's plan. The workflow treats it as a failed check. The check never runs through a send command.

    Note ([ADR-0060](0060-agent-assisted-reporting-and-analysis.md), proposed 2026-11-15): analysis explanations hold this by construction: in Phase 1 the model writes no text that reaches the person. Code renders every number as a key fact from fixed templates, and the model returns only a narrative plan of claim template codes with fact handles, and code renders the members from each fact's row; code checks each claim's precondition on the served cells, drops the steps that fail, and renders the rest from the claim catalog (rule 23; INV-413).

**Replay and evaluation**

37. Run modes (`agent_run.mode`): `live`; `shadow` (rule 14); `replay`, with recorded outputs; `evaluation`, live calls against the golden set. Replay and evaluation runs happen only in `test` and `simulation` environments, or on staging (ADR-0003 R12).
38. Replay:
    - **Matching.** The `replay` adapter returns the recorded response for (step code, ordinal, attempt) when the new request's `request_hash` equals the recorded one. A different hash is a divergence: strict replay fails with `replay_diverged` (a harness result, not an API error); comparison replay records the divergence and continues live.
    - **The determinism contract.** The same database state, agent type version and recorded responses give the same tool calls, the same commands and the same plan hashes. CI checks this per golden case. Rendering is canonical (sorted keys, canonical numbers and dates, ADR-0006 rule 13, ADR-0007 rule 3), so the hash is stable.
    - **Re-run for comparison.** The same cases run live with another model, seat setting or template version, and their outputs are compared with the recorded run and with the known answer (rule 39).
39. Golden evaluation sets:
    - **Cases.** One set per workflow, built from the synthetic dataset's input files and the simulator's known answer (DS-17 rule 20; ADR-0003 R8): the input, the expected drafted commands, and the expected outcome.
    - **Recordings.** Recordings of the reference run are synthetic, so they are committed under `backend/tests/agents/<agent_type>/`. Pilot recordings are replayed only on staging and never enter the repository (D16).
    - **Scoring.** Workflow comparators (ADR-0051) compare drafted commands field by field. The eval judge, a different model from the one scored (spec 17), scores free text only.
    - **Literal scope in the answers.** For a case whose run is tainted, the known answer is what the literal read scope allows: a line whose item the partner has no relation with is expected unresolved, and a tainted quotation run expects no configuration and no text (ADR-0051 rule 10).
    - **Thresholds.** At least 90% of cases equal the known answer (ADR-0003 R8), or the higher threshold ADR-0051 sets for the workflow.
40. CI and evaluation gates (Principle 11):
    - **Replay suite** on every commit that touches `agents`, the registry schemas its tools use, or the views; it must stay inside ADR-0003 R6's 15 minutes.
    - **Evaluation run** with the real provider whenever a template, output schema, agent type version or `seatmap.yaml` changes; merging needs it to pass. It runs in CI with a provider key held by the CI secret store. It never runs on pull requests from forks, which never receive the key.
    - **Spend.** An evaluation run is capped at USD 10 per agent type by a circuit breaker; above that it fails as inconclusive.
    - **Report.** `evaluation_report.json` (cases, scores, thresholds, model, template versions, cost) is a CI artifact; `seatmap.yaml` names the report that admitted each (seat, model) pair.
41. Shadow metrics:
    - **Recorded output.** A shadow run records its would-be commands, their simulated plans and plan hashes in `output_refs` and its steps.
    - **Comparison.** When a person resolves the same case, the workflow's comparator (ADR-0051) compares the person's result with the shadow output.
    - **Query.** `GetAgentShadowEvaluation` (agent type, company, date range) returns cases, agreement, deterministic share, cost per case and duration. ADR-0051's promotion rules read it.

**Query layer**

42. Placement and names:
    - **Schema `query`** holds the semantic views (ADR-0004 rule 16's placement; ADR-0022 rule 7 keeps tables in `nativeflows`).
    - **Names** are nouns, unique across the database and never equal to a table name (ADR-0004 rules 9, 16): row views end in `_overview`; aggregates use their own noun (`system_account_turnover`).
    - **Owner.** `query` declares each view in its `views.py` with its SQL; a CI check fails on a view without a declaration.
43. Roles and connections:
    - **Owner role.** Views are owned by `nativeflows_query_owner` (`NOLOGIN`, never `BYPASSRLS`), which has `SELECT` on the base tables it needs. Views use `security_barrier`. The generated company policy (ADR-0017 rule 19) applies to `nativeflows_query_owner`; a test runs every view as `nativeflows_readonly` without `nativeflows.company_id` and expects no rows.
    - **Reader role.** `nativeflows_readonly` has `USAGE` on schema `query` and `SELECT` on its views, and no grant in `nativeflows`.
    - **Connections.** A separate pool for `nativeflows_readonly`, with `default_transaction_read_only` on, `statement_timeout` 10 seconds for agent runs and 30 seconds otherwise (ADR-0022 rule 9 allows lowering), and `transaction_timeout` 30 seconds.
44. `SELECT` only (ADR-0040 rule 13):
    - **The builder** composes each statement from the view declaration and the request: one `SELECT` with bound parameters. No client sends SQL, and agents never write SQL (Principle 7). A CI test checks that every built statement is a single `SELECT`.
    - **No side effects.** Views call no volatile function. `EXECUTE` on `pg_notify` is revoked from `PUBLIC` and granted to `nativeflows_app` and `nativeflows_worker`.

    Note ([ADR-0060](0060-agent-assisted-reporting-and-analysis.md), proposed 2026-11-15): the analysis compiler emits one statement whose top level is a `SELECT`, with read-only common table expressions, over declared views only and with every value bound; the same CI test covers it (rule 12).
45. View declarations, beside the SQL:
    - **Columns:** meaning (English, translated), type, data label or row condition (ADR-0019 rule 7), field class, `is_untrusted`. A column with `is_secret` is refused by CI.
    - **Scope columns:** record scope (`branch_id`, `warehouse_id`, ADR-0017 rule 9), the partner column and the import batch column for taint scope (rule 27), and for document rows the effective `is_tainted`.
    - **Access:** filterable columns with their operators, sortable columns, the default stable order, and the key for `Get<View>`.

    Note: document rows also declare the owner scope columns of their document, `owner_employee_id` and `created_by_user_id`; a row that follows a document (a line, an open item) declares the document it follows ([ADR-0054](0054-users-roles-and-authorizations.md) rules 14–15).
46. Exposure:
    - **Queries.** Each view gives `List<View>` and, where keyed, `Get<View>`, registered by `query` (ADR-0004 rule 21). REST and MCP are generated (Principle 10). Their names are the view's noun in `PascalCase`: `ListPartnerOverview`, `ListSystemAccountTurnover`.
    - **MCP resources** (Principle 7): `nativeflows://query/views` lists the views, and `nativeflows://query/views/<name>` returns a declaration (columns, meanings, labels, field classes, untrusted flags, filters). They hold metadata only; data comes through the queries.

    Note ([ADR-0060](0060-agent-assisted-reporting-and-analysis.md), proposed 2026-11-15): the analysis catalog adds the resources `nativeflows://query/measures`, `nativeflows://query/measures/<code>`, `nativeflows://query/dimensions` and `nativeflows://query/dimensions/<code>`, metadata only (rule 14).
47. Filters and pages:
    - **Operators:** equality; `in` (at most 100 values); ranges on dates, amounts and quantities; `contains` on declared text columns (case and diacritics folded). Sorting only on declared columns, with `id` as the tiebreak.
    - **Pages.** Cursor paging (ADR-0008 rule 22): `limit` default 100, maximum 1,000. For agent runs the maximum is 200, and `max_rows_read` caps a run's total (rule 22).
48. Field classes and record scope, applied in the view and in the builder:
    - **Session settings.** The builder sets, with `SET LOCAL`, `nativeflows.company_id`, `nativeflows.field_classes`, `nativeflows.scope_branch_ids`, `nativeflows.scope_warehouse_ids` and, for tainted runs, `nativeflows.taint_scope_partner_id` or `nativeflows.taint_scope_import_batch_id`, `nativeflows.taint_subject`, `nativeflows.taint_work_item_id` and `nativeflows.taint_document_ids` (the drafts of its work item and agent type), all from the actor's effective rights (rule 31).
    - **Field classes.** Each class column is `CASE WHEN query.has_field_class('<class>') THEN … END`, so a missing class yields null even if the builder errs. The builder also leaves those columns out of the result (ADR-0017 rule 10: omitted, not null).
    - **Record scope.** Each view computes `is_in_scope` from the scope settings. The builder always filters on it, and computes `is_scope_filtered` with one `EXISTS` over the same filters and `NOT is_in_scope`, which returns one boolean and no row.

    Note: the builder also sets `nativeflows.read_grants`: the actor's assignments in force that grant the query's permission, for an agent run those of its human, as a list of (branch IDs, warehouse IDs, owner scope, the employee IDs of the organization resolver's set, user ID). A view's `is_in_scope` is true for a document row when one grant passes both record scope and owner scope, and for other rows when one passes record scope ([ADR-0054](0054-users-roles-and-authorizations.md) rules 13–15).

    Note ([ADR-0059](0059-ai-tuning-and-development-of-deterministic-functions.md), proposed 2026-11-15): for a run of a drafting agent type (one whose tool list holds an artifact draft command), the builder also excludes the held-out cases, by the hash rule, from every row query and aggregate: rows of the declared case tables and rows whose declared case-reference columns point at a held-out case. An aggregate it cannot filter is refused with `held_out_filter_unavailable`. Only queries registered held-out filtered may be on such a tool list, and reads of evidence, shadow outcomes, monitor snapshots, automation executions and `GetAutoPostShadowEvaluation` never are (rule 16).

    Note ([ADR-0060](0060-agent-assisted-reporting-and-analysis.md), proposed 2026-11-15): for analysis plans, which read several fact views in one statement, `nativeflows.read_grants` is a map keyed by view name: each fact view's entry holds the assignments that grant that view's `List` permission, and each view's `is_in_scope` reads its own entry, so one fact's grant never widens another's. The builder also sets `nativeflows.business_date` for views that compare dates with it (rule 13).

    Note ([ADR-0060](0060-agent-assisted-reporting-and-analysis.md), proposed 2026-11-15): this note replaces the list format of the first note above: `nativeflows.read_grants` is always a map keyed by view name, for every query of the read-only layer, so each view's `is_in_scope` reads one format; a `List<View>` query sets a one-entry map, and an analysis plan one entry per fact view it reads (ADR-0060 rule 13).
49. Taint in the views: the builder applies rules 25–28. It omits untrusted columns unless asked and reads the effective `is_tainted` column of returned rows. Each view computes `is_in_taint_scope` as rule 27 defines the scope: its partner or import batch column equals the run's scope, or the row is the run's subject, its work item or one of `nativeflows.taint_document_ids`. Views of reference data are declared `is_reference` and always pass. For tainted runs the builder filters on `is_in_taint_scope`, and refuses a view that has none of these columns and is not `is_reference`.
50. Never in an agent's reach:
    - **Audit.** No view over `audit_record`, `audit_change`, `audit_denial`, `policy_decision`, `agent_run_step` or `personal_data_processing_log` is registered for agents. Tainted runs never read audit data (ADR-0038 rule 7). People read these through their own queries.
    - **Secrets.** Never in a view (rule 45).
51. Initial views, for the six business flows and the first agents:

    | View | Over | Partner column | Untrusted columns | Field class columns | Flows |
    | --- | --- | --- | --- | --- | --- |
    | `partner_overview` | partner, roles, profiles, groups, credit limit, payment term, price list | `id` | — | — | All |
    | `contact_overview` | contact with its partner | `partner_id` | — | — | Sales, onboarding |
    | `partner_item_overview` | `partner_item` and `supplier_item` rows with item code, name and units | `partner_id` | — | `supplier_item` price: `cost` | Purchasing, quotation |
    | `item_overview` | item, product, units, groups, tax group, tracking flags, barcodes | — | — | preliminary price: `cost` | All |
    | `price_list_entry_overview` | price list entries with list, item, unit, break and dates | — | — | purchase lists: `cost` | Sales, purchasing |
    | `configuration_model_overview` | configurable products, released revisions, characteristics and allowed values | — | — | — | Quotation |
    | `open_item_overview` | open items with system account, dates, amounts, open amount, days overdue, collection flags | `partner_id` | dispute reason | — | Cash, collections |
    | `stock_overview` | stock by item, warehouse, bin, status, lot with expiry, reserved quantity | — | — | value: `cost` | Stock, planning |
    | `demand_supply_overview` | `demand_supply_line` rows with source document and dates | `partner_id` | — | — | Planning, sales |
    | `planned_order_overview` | planned orders with state, dates, supplier or version, pegging count | — | — | — | Planning |
    | `document_overview` | documents of every type: number, state, change state, partner, dates, totals, currency, version, effective taint, origin work item and run | `partner_id` | — | — | All |
    | `document_line_overview` | lines with item, configuration, quantity, unit, net price, amounts, open quantity | `partner_id` | line free text from outside | unit cost and margin: `cost`, `margin` | All |
    | `interaction_overview` | interactions without body: kind, direction, partner, contact, occurred at, subject, sender authentication | `partner_id` | subject, body, summary | — | Sales, onboarding |
    | `bank_statement_line_overview` | statement lines with money account, dates, amount, reference, counterparty, match state | — | description | — | Bank matching |
    | `import_row_overview` | rows of an import batch with raw and mapped values and errors | (import batch column `import_batch_id`) | raw values | — | Migration |
    | `system_account_turnover` | rule 53 | — | — | — | Management reporting |
    | `forecast_accuracy` | forecast against actual demand per item, warehouse and period (ADR-0024 rule 12) | — | — | — | Planning |

    - **Later views**, added by ordinary changes with the step that builds their tables: `warehouse_task_overview` and `count_accuracy` (ADR-0023 rule 23), production views (DS-52 to DS-54).
    - **Labels.** Personal columns keep their labels (contact fields, row-conditional partner fields). Bank descriptions, counterparty names and counterparty accounts are personal (rule 9).

    Note: the document views (`document_overview`, `document_line_overview`, `open_item_overview` through its origin document, `demand_supply_overview` through its source document) apply owner scope. `system_account_turnover`, `forecast_accuracy` and `stock_overview` total over documents without returning them and are registered `is_owner_scoped: false`, so they need an assignment with owner scope `branch` or `company` ([ADR-0054](0054-users-roles-and-authorizations.md) rule 15).

    Note ([ADR-0058](0058-configurable-workflows.md), proposed 2026-11-15): new views `automation_execution_overview` (no partner column, so closed to tainted runs) and `decision_artifact_overview` (agent types with their settings, and every artifact with its kind, owner, state, version in force and last monitor result, the one registry of X9). Both return only rows inside the reader's record and owner scope and replace values of field classes the reader lacks by their hashes (rule 11; [ADR-0059](0059-ai-tuning-and-development-of-deterministic-functions.md) rule 26).

    Note ([ADR-0060](0060-agent-assisted-reporting-and-analysis.md), proposed 2026-11-15): the analysis layer adds the views `journal_line_overview` (with `is_closing_entry`, `is_migration_entry`, `is_special_period` and the `opening_turnover` rows, which only a company-wide grant sees), `sales_line_overview`, `purchase_line_overview`, `stock_movement_overview`, `production_output_overview` and `production_variance_overview`, with the label views of its dimensions and the helper views `posting_period_dimension` and `open_item_line_dimension`, which carry no scope and are joined only on keys of in-scope fact rows. Each declares its grain and omits untrusted columns; `production_variance_overview` is registered `is_owner_scoped: false` (rule 3).

    Note ([ADR-0064](0064-production-agent.md), proposed 2026-11-15): production views `production_order_overview`, `production_order_component_overview`, `production_order_operation_overview` and `shop_floor_posting_overview`, without a partner column and with the subject column `production_order_id` (`id` for the header), so a tainted capture run reads only its order's rows (rule 13).
52. Computed module queries stay with their modules and are allowed on tool lists: `GetPrice` (ADR-0045 rule 4), `EvaluateConfiguration` (ADR-0046 rule 8), `GetConfigurationEstimate`, `GetCreditExposure` (ADR-0047 rule 18), `GetAvailableToPromise` (ADR-0023), `GetProjectedAvailability`, `ListPegging`, `ListCapacityLoad`, `GetCapacityLevelingProposal` (ADR-0024, ADR-0036), `GetAllocationProposal` (ADR-0048 rule 6), `GetOutboundContentCheck` (`crm`, ADR-0029 rule 14; rule 36), `ListWorkItem` and `GetWorkItem` (ADR-0042). A view never re-implements a figure a module computes: exposure, availability and prices come only from these queries. They run in read-only transactions under the same timeouts, and rules 25–28 apply to their results.

    Note: the reporting queries are computed module queries too: `GetStatutoryReport`, `ListBookRow`, `ListReportLineContribution`, and the definition, filing, comparative value and render job queries of `reporting`. For agent runs they run under the 10-second statement timeout for agent runs (rule 43), so an agent reads a large book by cursor ([ADR-0049](0049-statutory-reporting-and-printing.md) rule 15).
53. Management reporting (ADR-0027 rule 8):
    - **`system_account_turnover`:** per company, posting period, system account (ADR-0010), branch, cost center, project and transaction currency: debit and credit turnover and closing balance in company currency, and in group currency where set. It reads `account_period_balance` for locked periods and journal lines for open ones (ADR-0014 rule 18), so figures agree with the books.
    - **Statutory reports** stay DS-26's. Management reports are views and exports, never documents.

    Note ([ADR-0060](0060-agent-assisted-reporting-and-analysis.md), proposed 2026-11-15): management reports are analysis plans over the facts of the analysis catalog, `system_account_turnover` among them; saved analyses and KPIs keep them as company data (rules 3, 26, 27).
54. List export (ADR-0040 rule 6):
    - **`CreateListExport`** (module `query`, effect class `other`): a `List<…>` query, its filters, columns and language. It creates a `list_export` record (`state`: `queued`, `running`, `done`, `failed`) and emits `ListExportCreated`. A long-job consumer of that event on queue `jobs` (ADR-0031 rule 15) writes the file, so no job is enqueued on a handler's path (ADR-0013 rule 13).
    - **The consumer** pages through the query as the requester, so field classes and scope apply, translates headers and enumerations on the server, and writes an `.xlsx` with XlsxWriter (ADR-0002). More rows than `list_export_max_rows` (installation setting, default 100,000) fail with `list_export_too_large`.
    - **The file** is an attachment that is not accounting evidence; its bytes are deleted after 7 days. Downloading it needs the same query permission and is audited. An export containing personal columns writes a processing-log entry (ADR-0019 rule 11).
    - **Agents** never export (rule 30).

    Note: `CreateListExport` refuses every query of module `reporting` with `list_export_query_not_allowed`. Statutory reports and books leave only through `RenderReport`, which carries the opening, totals and closing rows and the full-scope check ([ADR-0049](0049-statutory-reporting-and-printing.md) rule 20).

    Note ([ADR-0060](0060-agent-assisted-reporting-and-analysis.md), proposed 2026-11-15): people export analysis results through `ListAnalysisResultRow`, which reruns the plan as the requester; agents still never export (rule 17).

**Catalogs and checks**

55. Catalog rows:
    - **Errors** (DS-04):

      | Code | Category | Retryable | When |
      | --- | --- | --- | --- |
      | `agent_mode_off` | precondition | no | The agent type is `off` for the company, or the LLM is off |
      | `agent_budget_exceeded` | precondition | no | A run or daily budget would be exceeded; `details` names the limit |
      | `agent_scope_unresolved` | precondition | no | The agent type's scope resolver found no scope for the subject |
      | `approver_is_submitter` | permission | no | The person who submitted a promotion proposal tried to approve it (rule 14) |
      | `promotion_evidence_stale` | precondition | no | The agent type's behavior hash or seat models no longer equal the frozen promotion evidence (rule 14) |
      | `llm_provider_unavailable` | unavailable | yes | The provider failed after retries and fallback, or its circuit is open |
      | `llm_output_invalid` | validation | no | An LLM output failed its schema or checks three times |
      | `llm_routing_refused` | permission | no | A request still held a personal value with the switch on, or held a secret |
      | `tool_not_allowed` | permission | no | The tool is not on the run's list |
      | `agent_kind_not_declared` | precondition | no | `StartAgentRun` names a work item kind or subject table the agent type does not accept |
      | `tainted_read_out_of_scope` | permission | no | A tainted run asked for rows outside its scope, or used such a row in a prompt or a command input |
      | `untrusted_read_not_allowed` | permission | no | A run of an agent type that must stay clean asked for untrusted fields |
      | `tainted_run_not_allowed` | permission | no | A tainted run sent a command not registered `is_draft_only` |
      | `list_export_too_large` | precondition | no | The list has more rows than `list_export_max_rows` |

    - **Denial records** (ADR-0038 rule 5) also cover `tool_not_allowed`, `tainted_read_out_of_scope`, `untrusted_read_not_allowed` and `tainted_run_not_allowed`.
    - **Check result** (DS-04): `outbound_content_flagged` (rule 36).
    - **Work item kinds** (module `agents`, which raises them through `work.contract`): `agent_run_stopped` (subject the agent type, owner the human of the first run raising it, `open_key` `<outcome>:<business date>`, the runs as evidence), `agent_budget_exhausted` (subject the agent type, owner `company_owner`, `open_key` the business date), `agent_denials_repeated` (subject the run, owner `company_owner`, the default key), `agent_mode_degraded` (subject the agent type, owner `company_owner`, key the agent type within the company; rule 14).
    - **Invariants** (safety; first step 5, the window in which the first agent runs after the step 4 gate), INV-210 to INV-215, in the range INV-200 to INV-299 (ADR-0038 rule 8). INV-206 to INV-209 are left free for design items drafted at the same time; codes are not a sequence promise:
      - **INV-210:** every outbox event, work item raise and work item note written by an agent run tainted at the row's `recorded_at` (its `tainted_at` at or before that instant, the instant INV-88 uses for versions), or by a consumer whose origin run was tainted at the origin event's `recorded_at`, has `is_tainted` true.
      - **INV-211:** every audit record with an `agent_run_id` names a command on the tool list of that run's agent type version.
      - **INV-212:** every ended run's totals are within its budget snapshot and its reservations are zero; every `agent_budget_usage` row's spent plus reserved is within its limit.
      - **INV-213:** every LLM step that sent personal values has its processing-log entry; no LLM step sent a personal value while its company's routing switch was on.
      - **INV-214:** no agent type version's tool list holds a command or query that rule 30 forbids.
      - **INV-215:** every row reference in `result_refs`, `context_refs` and `request_refs` of a step recorded after its run's `tainted_at` is inside that run's tainted read scope (rule 27), wherever the row was first read.
    - **Registry attribute:** `is_draft_only` (ADR-0008 rule 1). **Capability:** `read_agent_run_bodies` (ADR-0017 rule 4).
    - **Settings:** company `routing_switch`, `agents.company_daily_max_cost`; installation `llm_provider` (Phase 1: `anthropic` only), `agents.installation_daily_max_cost`, `agent_run_step_retention_days`, `list_export_max_rows`.
    - **Verbs** (glossary): Start gains "or start an agent run"; Complete gains "or finish an agent run with its outcome".

    Note: open keys carry the agent type, so two agent types never share an item: `agent_budget_exhausted` uses `<agent_type>:<business date>` for an agent type's daily limits, and `company:<business date>` or `installation:<business date>` when the company's or the installation's daily cap tripped (subject the agent type whose reservation failed); `agent_run_stopped` uses `<agent_type>:<outcome>:<business date>`. **INV-216** (safety, first step 5; INV-217 to INV-219 stay free): every audit record of a command run by an agent run tainted at the record's `recorded_at`, or by a consumer whose origin run was tainted at the origin event's `recorded_at`, has `is_draft_only` true as registered at the time, except `CompleteAgentRun` ([ADR-0038](0038-audit-and-observability.md) rule 2 note; [ADR-0013](0013-outbox-and-events.md) rule 11 note).

    Note (Design hardening, 2026-11-16): `agents.company_daily_max_cost` and `agents.installation_daily_max_cost` are registered in [settings.csv](../catalogs/settings.csv), with the agent-type and reserve settings of rule 22's note.
56. Lab check `t10_agents.py` ([validation lab](../reviews/2026-11-14-design-validation/README.md)), pure functions: budget reservation without overshoot under interleaved runs; taint on read (untrusted field, tainted row, tainted item at start, clean agent types filtered); the tainted read scope with own drafts and reference data; the permission intersection re-evaluated after the human loses a right; tool list checks and the denial stop; schema-validated output with two retries; routing-switch redaction with the residual scan; shadow mode never executing; replay determinism and divergence. Round 1 adds: outside-content subjects starting tainted; rows read before taint refused as prompt or command inputs; `is_draft_only`; seat data classes; the one rule for the human acted for; the supplier gate; orphaned reservations settled at the worst case and a diverged resume stopped; denials counted when their records are dropped; wake-ups skipping agent-origin events; shadow runs without a claim; aggregates that do not taint; the outbound check in a draft's plan; the bank re-run's guards, its tainted rule proposal and the shadow comparator on the pure cascade; aligned taint instants. Not covered: the database, RLS, the provider, the queue.

    Note: the lab also checks the dispatcher's check order for EC-56 and for replays (step 6 before step 8), and its query path refuses by run gates before permission ([DS-04](../design/DS-04-command-envelope.md#dispatcher-check-order)).

## Context

DS-32 and DS-33 are needed by the first agent, after step 4 (spec 11). Many accepted ADRs left obligations here: the run's columns and `tainted_at` (ADR-0027, ADR-0029), run tokens and tool lists (ADR-0017), denial signals and telemetry (ADR-0038), claims and wake-ups (ADR-0042), routing by row labels and the processing log (ADR-0019), budgets (ADR-0003 R6, ADR-0022), placement and timeouts of views (ADR-0004, ADR-0022), list export and the `SELECT`-only rule (ADR-0040), and management reporting (ADR-0027 rule 8).

Constraints:
- Spec 03's hard floors cannot be relaxed (ADR-0005 item 7). This ADR implements them and adds checks; it relaxes none.
- Spec 17 fixes one provider behind a common interface in Phase 1, labels on every field, and the routing switch.
- ADR-0002 fixes the Anthropic SDK behind a thin self-written gateway and rejects agent frameworks.
- Handlers make no network call (ADR-0008 rule 4), so LLM calls run in an external consumer outside transactions (ADR-0013 rule 10).

How others do it, concepts only. SAP's Joule and S/4HANA AI services keep business logic in the application and call models through a central hub with grounding and data masking; reads go through CDS views with authorization checks. NativeFlows follows the same split: one gateway with masking by label, semantic views with scope and field filters, and the business core deciding everything.

The main risk is prompt injection from outside content. Instructions cannot be filtered reliably from text. So the design never trusts the model: taint is set where data is read, tainted runs cannot act or see beyond their scope, tools are fixed and read-only for the model, and every output is checked by code.

## Options considered

| Option | For | Against |
| --- | --- | --- |
| One gateway function with adapters (chosen) | One place for labels, logging, cost and replay | Provider-specific features need capability flags |
| Provider SDKs called from workflows | Less code | Labels, logs and budgets would be repeated and missed |
| An agent framework | Ready-made loops | ADR-0002 rejects it; hides control flow from replay |
| Taint set in the dispatcher's read path, committed first (chosen) | Cannot be skipped by workflow code; ordering is provable | One extra transaction on the first untrusted read |
| Taint declared by workflow code | Simple | A bug or injection could skip it |
| Runs on outside subjects start tainted; out-of-scope rows refused as inputs after taint (chosen) | Nothing read before taint reaches a prompt or draft | A few deterministic reads are scoped too |
| LLM steps read, code writes (chosen) | Every write is checked and simulated by code | Less autonomy for the model |
| Model may call write tools | Fewer steps | Model output would reach commands unchecked |
| Budget reservation before each call (chosen) | No overshoot, also in parallel | Reserves the worst case |
| Count after the call | Simple | Overshoots by one call per run, unbounded in parallel |
| Views in schema `query` owned by a non-bypass role (chosen) | RLS applies; reader has no table grants | One more role |
| Views with `security_invoker` | No owner role | The reader would need table grants, so a builder bug could read tables directly |
| Run steps as platform records (chosen) | One audit row per business command stays meaningful | An exception to "every write is a command", like denial records |
| Run steps as commands | Uniform | Thousands of audit rows per run, and audit of audit |

## Constraints that come with the decision

- **ADR notes:**
  - ADR-0004 rule 16: views in schema `query`;
  - ADR-0008 rule 6: tool lists and tool definitions; rule 25: agent budgets beside rate limits;
  - ADR-0013 rule 12: the wake-up consumer starts runs through `StartAgentRun`; rule 13: queue `agents`;
  - ADR-0014 rule 17: agents read views and module queries;
  - ADR-0017 rule 3: the run token; rule 4: `start_agent:<agent_type>`; rule 11: the third limit of tool lists; rule 12: the tainted read scope; rule 18: `nativeflows_query_owner`; rule 19: scope and classes through session settings in views;
  - ADR-0019 rule 7: label evaluation per value; rule 10: erasure of run steps; rule 11: the gateway's log entries;
  - ADR-0022 rule 2: the three modules and their imports; rule 6: the provider import contract; rule 7: schema `query` and the owner role; rule 9: 10-second agent queries;
  - ADR-0023 rule 23: warehouse views later;
  - ADR-0024 rule 12: `forecast_accuracy`;
  - ADR-0027 rule 1: the columns of `agent_runs`;
  - ADR-0029 rule 10: taint on read in the dispatcher, `tainted_at`; rule 14: the reading of the literal scope;
  - ADR-0038 rule 5: new denial codes; rule 7: run queries also off tool lists; rules 10–11: gateway spans and attributes;
  - ADR-0040 rule 6: `CreateListExport`; rule 8: people-only stays; rule 13: `SELECT` only and `pg_notify`;
  - ADR-0042 rule 10: claims by `StartAgentRun`; rule 14: `agent_wake_up`; rule 18: the new kinds;
  - ADR-0044 rule 16: personal data in import files under the interim;
  - ADR-0008 rule 1: `is_draft_only`; ADR-0013 rule 7: the runner's heartbeat; ADR-0013 rule 11: wake-ups skip agent-origin events; ADR-0017 rule 4: `read_agent_run_bodies`; ADR-0019 rule 17 and ADR-0029 rule 14: `GetOutboundContentCheck`; ADR-0034 rule 5: people release in Phase 1; ADR-0042 rule 11: shadow runs bind without a claim; ADR-0043 rule 14: the evidence hook.
- **DS-04:** the errors of rule 55; commands `StartAgentRun`, `CompleteAgentRun`, `CancelAgentRun`, `UpdateAgentTypeSetting`, `CreateListExport`; queries `ListAgentRun`, `GetAgentRun`, `GetAgentShadowEvaluation`, `GetOutboundContentCheck` and the view queries; check result `outbound_content_flagged`.
- **Catalogs:** the work item kinds, INV-210 to INV-215.
- **DS-16:** hard-floor property tests: taint committed before data; tainted commands refused; the read scope; the intersection; no tool outside the list; budgets never exceeded; the canary tests.
- **DS-17:** recordings of reference runs for the golden sets (rule 39).
- **DS-18:** import-linter contract, the replay suite and the evaluation job in CI.
- **DS-37:** the provider secret, the `local` endpoint, queue `agents` workers.
- **Glossary** rows for the new terms.
- **Open questions:** a local provider in Phase 1; the readings of the literal read scope, including aggregates and own-draft prices; budget values and retention; `ListAllowedCommand` stays people-only.

## Revisit when

- The author answers the open question on the read scope, or allows a local provider to receive personal data.
- After Phase 1: several providers, fallbacks across providers, pseudonymization, embeddings (spec 17).
- Measured spend or latency shows a budget or timeout set here is wrong for a workflow.
- `system_account_turnover` exceeds its timeout on the large dataset; then it becomes a read model updated at period lock.

## Documents updated

- **ADRs:** notes in [ADR-0004](0004-naming-conventions.md), [ADR-0008](0008-command-envelope-and-registry.md), [ADR-0013](0013-outbox-and-events.md), [ADR-0014](0014-universal-journal.md), [ADR-0017](0017-permission-envelope.md), [ADR-0019](0019-partners-and-crm-foundation.md), [ADR-0022](0022-repository-and-engineering-conventions.md), [ADR-0023](0023-warehouse-management.md), [ADR-0024](0024-planning.md), [ADR-0027](0027-cross-cutting-ownership.md), [ADR-0029](0029-proposals-and-agent-safety.md), [ADR-0038](0038-audit-and-observability.md), [ADR-0040](0040-ui-architecture.md), [ADR-0042](0042-work-queue.md), [ADR-0044](0044-data-migration-and-export.md).
- **Design files:** [docs/design/DS-04-command-envelope.md](../design/DS-04-command-envelope.md), [docs/design/backlog.md](../design/backlog.md).
- **Catalogs:** [work-item-kinds.csv](../catalogs/work-item-kinds.csv), [invariants.csv](../catalogs/invariants.csv).
- **The lab:** [docs/reviews/2026-11-14-design-validation/](../reviews/2026-11-14-design-validation/README.md): `lab/t10_agents.py`.
- **Glossary:** [docs/spec/00-reading-guide.md](../spec/00-reading-guide.md).
- **Open questions:** [docs/open-questions.md](../open-questions.md).
- **Index and log:** [docs/adr/README.md](README.md); [docs/runbook/step-log.md](../runbook/step-log.md) at acceptance.
