Module: agents    Chunk: 2 of 8    Source ADRs: ADR-0050
Build step(s): 2, 4    Generated from index: 30d5706    Compiled by: Claude Opus 5.5, 2026-11-21

# `agents` compiled spec, chunk 2: run execution, ending, limits, taint, tool lists, LLM steps and replay

## Purpose

This chunk states the part of `agents` law on executing and ending an agent run, the run queries and telemetry, the cost and count limits with reservation and circuit breakers, run taint, tool lists and effective permissions, LLM steps, repeated denials, output schemas and deterministic checks, run modes and replay. `agents` declares agent types and runs them; the run records and the budget rows are written through `agent_runs.contract` (co-primary for several rules here). Starting a run, scopes, agent types and workflows are in the other chunks.

## Entities and tables

DDL: `docs/design/DS-05-platform.sql` (run records) and `docs/design/DS-30-ui.sql`. The rules of this chunk define no owned table; `assist_request` has its row in the chunk that states ADR-0077.R13.

Reads: `agent_run`, `agent_run_step`, `agent_budget_usage`, `llm_request` (`agent_runs`); `setting_value` (`registry`); `work_item` (`work`); `attachment` (`attachments`); `partner_item`.

## Commands and queries

Authorization area: the function leaf `agent` (catalog `authorization-areas.csv`) covers agent run queries and the capability `cancel_agent_runs` at `full`; `start_agent:<agent_type>` is on each agent type's own leaf below `agent` (`agent_analysis`, `agent_assistant`, `agent_production` and the like). The capability `read_agent_run_bodies` is `full` on the leaf `agent_run_bodies` (module `agent_runs`).

| Name | Actor and authorization | Input | Effect | Events | Error codes |
| --- | --- | --- | --- | --- | --- |
| `CompleteAgentRun` | dispatched by the runner or the run reaper; actor `system` on behalf of the run's human, `origin_agent_run_id` the run; effect class `other` | the run, outcome, totals, output references | Records the outcome, totals and output references, unclaims the work item or resolves the run's `agent_task`, revokes the run token (R216) | `AgentRunCompleted` | not stated |
| `CancelAgentRun` | `start_agent:<agent_type>` of the run's agent type, or `cancel_agent_runs` (`full` on `agent`) | the run | Stops the run between steps, outcome `canceled` (R220) | not stated | not stated |
| `ListAgentRun` | query, generated permission; area `agent` | not stated | Lists runs; bodies only with `read_agent_run_bodies` (R221) | none | not stated |
| `GetAgentRun` | query, generated permission; area `agent` | the run | Returns the run with its steps, paged; bodies only with `read_agent_run_bodies` (R221) | none | not stated |

Consumers, jobs and contract functions, not registered commands: the consumer `agent_wake_up` of `WorkItemRaised` (R201); the `external` consumer `agent_runner` of `AgentRunStarted` on queue `agents` (R204); the run reaper, a system job on queue `jobs` (R210); `agent_runs.contract.reserve_budget` and `settle_budget` (R233, R235); `agent_runs.contract.mark_run_tainted` (R243).

Error codes bound to no command of this chunk: `StartAgentRun` returns `agent_budget_exceeded` while a daily guard is tripped (R238); the dispatcher returns `tool_not_allowed` (R249) and the runtime `tainted_read_out_of_scope` (R244); a step fails with `llm_output_invalid` (R262); a setting change returns `setting_out_of_bounds` (R228); a re-run gets `duplicate_draft` (R257); `outbound_content_flagged` is a check result (R267); `replay_diverged` is a harness result, not an API error (R269).

## Rules

### Executing a run

R201. Wake-ups. The consumer `agent_wake_up` reacts to `WorkItemRaised` for kinds an agent type declares, in companies where that type's mode is not `off`, and dispatches `StartAgentRun` (ADR-0013.R12; ADR-0042.R14). It skips `WorkItemRaised` events that carry an origin agent run (ADR-0013.R9, ADR-0013.R11), so nothing in an agent's chain wakes an agent. Only raises wake agents, so a run that unclaims an item never wakes another (no loop). For a tainted item this stays within ADR-0013.R11, because the run starts tainted (ADR-0050.R15) and can only draft.
Source: ADR-0050.R16

R202. Configurable kinds. `agent_wake_up` skips a kind that an agent type declares `configurable` only while the company's wake-up mode (`agents.<agent_type>.wake_up_mode.<kind>`) is `by_rule` or `off`; under `always`, the default, it starts the agent (ADR-0063.R11).
Source: ADR-0050.R16.N1, ADR-0050.R16.N2

R203. Starting by an automation rule. A rule's `start_agent` acts for the setting's `workflow_owner_id`, as ADR-0050.R15 says, and the rule's owner also needs `start_agent:<agent_type>`. It may start the agent on a tainted or outside-content subject when the agent type accepts that subject table, the run starting tainted, and it is skipped on events that carry an origin agent run. A run started from an event, by a wake-up or a rule, inherits the event's causation chain and depth, and its tool calls and its drafts' events carry them (ADR-0058.R7, ADR-0058.R9, ADR-0058.R12).
Source: ADR-0050.R16.N1

R204. No agent wakes an agent. A kind that a command on any agent tool list can raise may not be declared by any agent type (a registry check), like `agent_task` (ADR-0042.R11).
Source: ADR-0050.R16

R205. Runner. The `external` consumer `agent_runner` of `AgentRunStarted` runs on a new queue `agents` (ADR-0013.R10, ADR-0013.R13). Its delivery lease is 5 minutes, and the live runner extends `locked_until` every 60 seconds, a technical timer (ADR-0013.R7), so a dead runner is noticed within 5 minutes. It calls the gateway with no transaction open.
Source: ADR-0050.R16

R206. Run token. At execution start the runner mints a run token (ADR-0017.R3) bound to the run, agent type version, tool list, human acted for and work item, expiring at `started_at` plus the run's time limit plus 60 seconds and revoked when the run ends. A retry revokes the earlier token and mints a new one with the same expiry. The runner dispatches every tool call in process with it (ADR-0008.R8).
Source: ADR-0050.R16

R207. One call at a time. A run's LLM calls and tool calls are sequential, never parallel, so taint, budgets and replay each have one order. Each command renews the claim (ADR-0042.R10); the runner also renews it before each LLM call that would outlast it.
Source: ADR-0050.R16

R208. Crash and retry. If the runner dies, the delivery is retried (ADR-0013.R7), at most 3 attempts. The retry continues the same run:
- it settles every reservation the dead attempt left open at its reserved amount, recorded on the `llm_request` row, the worst case, because the provider may have charged it;
- it replays the recorded steps through the `replay` adapter (R268) up to the last recorded response, then continues live; a request row without a response row is a call with an unknown outcome, and it is made again;
- a replayed request whose hash differs from the recorded one (the data changed meanwhile) stops the run with outcome `resume_diverged`;
- the time limit counts from `started_at`, the crash included, so a retry that cannot finish in time ends with `time_exceeded`.
Source: ADR-0050.R16

R209. Command idempotency keys (R257) and draft keys (ADR-0030.R11) make repeated commands return their first results.
Source: ADR-0050.R16

R210. After the third failed attempt the delivery is held (ADR-0013.R8), and the run reaper, a system job of module `agents` on queue `jobs` (actor `system`, on behalf of the run's human), records outcome `crashed` through `CompleteAgentRun`.
Source: ADR-0050.R16

### Ending a run

R215. `CompleteAgentRun` (effect class `other`) is dispatched by the runner in the transaction that marks the delivery done (ADR-0013.R10). It records the outcome, totals and output references, unclaims the work item (or resolves the run's `agent_task`), revokes the run token and emits `AgentRunCompleted`.
Source: ADR-0050.R17

R216. `CompleteAgentRun` runs as actor `system` on behalf of the run's human, with the run as `origin_agent_run_id`, so the items it raises carry the run's taint (`INV-210`). The run's own tool calls run as actor `agent` with the run token.
Source: ADR-0050.R17

R217. Run states: `queued` → `running` → `completed` | `stopped` | `canceled`.
Source: ADR-0050.R17

R218. Outcomes, their state and what happens to the work item:
- `drafted` (drafts or proposals made), `no_action` (nothing to do), `not_applicable` (not this workflow's case): `completed`; the item is unclaimed, back to its owner, with links to drafts and a note.
- `routing_blocked` (ADR-0050.R9): `completed`; the same.
- `claim_lost` (a person took the item): `stopped`; the item stays with that person.
- `budget_exceeded`, `time_exceeded`, `output_invalid`, `provider_unavailable`, `resume_diverged`, `crashed` (third failed attempt): `stopped`; unclaimed; `agent_run_stopped` raised (ADR-0050.R55).
- `denials_repeated` (R260): `stopped`; unclaimed; `agent_denials_repeated` raised.
- `canceled`: `canceled`; unclaimed.
Source: ADR-0050.R17

R219. The `analysis` agent type adds the outcome `answered` and the abstentions `ambiguous_term`, `ambiguous_member`, `out_of_coverage`, `not_permitted`, `data_not_ready` and `too_broad`, all in state `completed`, which `ck_agent_run_outcome` of `DS-05-platform.sql` allows. The run's `agent_task` item is resolved, and a stopped run sets its question to `failed` (ADR-0060.R21, ADR-0060.R24).
Source: ADR-0050.R17.N2

R220. Cancel. `CancelAgentRun` stops a run between steps; it needs `start_agent:<agent_type>` of the run's agent type or the capability `cancel_agent_runs` (`full` on `agent`; ADR-0054.R24). The runner checks the state before every step.
Source: ADR-0050.R17, ADR-0050.R17.N1

### Run queries, export, erasure and telemetry

R221. Queries. `ListAgentRun` and `GetAgentRun` (with its steps, paged) each have their generated permission. Request and response bodies are returned only to holders of the capability `read_agent_run_bodies` (ADR-0017.R4); access to bodies is by that capability alone. `read_agent_run_bodies` is `full` on its own authorization leaf `agent_run_bodies`, which every role template except `owner` sets to `none` (ADR-0054.R8, ADR-0054.R11). Both queries are on no agent tool list (R250).
Source: ADR-0050.R20, ADR-0050.R20.N1

R222. Export and erasure. `ExportCompanyData` includes `agent_run` and `agent_run_step` (ADR-0044.R17). `EraseDataSubject` (ADR-0019.R10) blanks `request_body` and `response_body` of every step whose `personal_subject_refs` or `personal_fields_sent` names the subject or one of its rows, keeping the rows and counts.
Source: ADR-0050.R20

R223. Telemetry spans (ADR-0038.R10, ADR-0038.R11). One span per gateway call and per tool call, as children of the run's span (`agent_run.trace_id`). Allow-listed attributes: agent type and version, step code, seat, provider, model, template code and version, token counts, cost, duration, attempt, outcome or error code, and `is_tainted` as a boolean. Never text, values or IDs other than the trace ID.
Source: ADR-0050.R21

R224. Telemetry metrics: tokens and cost per agent type (ADR-0038.R10), runs by outcome, budget trips, denials per agent type, retries per step, and the deterministic share per workflow (spec 14). Labels are codes only.
Source: ADR-0050.R21

### Limits

R225. Per run, the agent type version declares maximums (values in ADR-0051): `max_llm_calls`, `max_tool_calls`, `max_input_tokens`, `max_output_tokens`, `max_cost`, `max_seconds`, `max_rows_read`. The per-type daily limits `daily_max_cost` and `daily_max_runs` (per company, agent type and business date) are no Phase 1 tier and bind no run (ADR-0078.R7, R226). The declared values of ADR-0051.R9 and of later agent types stay the ceilings of the per-run values.
Source: ADR-0050.R22, ADR-0050.R22.N2

R226. Phase 1 has two tiers: the company's daily cap (with the installation maximum and the internal reserve) and the per-run ceilings of the agent type version's declaration (ADR-0078.R7). The keys `agents.<agent_type>.daily_max_cost`, `agents.<agent_type>.daily_max_runs` and `agents.<agent_type>.run_max_*` are not in `settings.csv`; reservation, stop and `agent_budget_exhausted` stay. The per-type usage rows of `agent_budget_usage` keep counting cost and runs, with `limit_amount` equal to the company's cap and `run_limit_count` null, so they never bind before the company row; each reservation refreshes that `limit_amount` to the company cap in force, so a raised cap never leaves a lower limit on it. The reservation checks the company row, the installation row and, for agent types that read outside content, the `company_outside_content` row, and no per-type limit.
Source: ADR-0050.R22, ADR-0050.R22.N2, ADR-0050.R22.N3

R227. The customer sets the caps. Every cost and run limit is a definition of the settings registry (ADR-0063.R1), its `source` naming ADR-0050 rule 22. Installation maxima are set at deployment by the operator and recorded as `setting_value` rows naming the operator account, a raise approved by a second operator account (ADR-0063.R2): `agents.installation_daily_max_cost` (default USD 200), and the installation value of `agents.company_daily_max_cost`, which is the maximum of every company's cap; when the deployment names none, `agents.installation_daily_max_cost` is that maximum. `agents.installation_daily_max_cost` changes only through installation configuration, never by a company setting or a command, and every change is logged with the operator who made it.
Source: ADR-0050.R22, ADR-0050.R22.N2

R228. Company values lie within those maxima: `agents.company_daily_max_cost` (default USD 50) per company and business date. The version still declares every per-run value as a ceiling for safety; a company cap above the installation maximum returns `setting_out_of_bounds`.
Source: ADR-0050.R22, ADR-0050.R22.N2, ADR-0050.R22.N3

R229. When the deployment names no installation value of `agents.company_daily_max_cost`, the startup step records one equal to `agents.installation_daily_max_cost` (a `setting_value` row of scope `installation`, the operator account as changer), and records it again whenever that value changes, so the generic trigger and `get_setting` apply the maximum with no special case.
Source: ADR-0050.R22.N4

R230. The reserve pool. `agents.internal_reserve_share` (company, default 0.40, bounds 0 to 0.9) is the share of the company's daily cap that only internal agent types may use. A version is internal when it declares `may_read_untrusted: false` and accepts no subject that is outside content, so its runs are never tainted by design. Agent types that read outside content share the remainder, (1 − share) × the company cap; internal agent types may use the whole cap. The Phase 1 internal types are `analysis` and `planning` (ADR-0078.R7); `production` is a Phase 2 type. R234 gives the check.
Source: ADR-0050.R22.N2, ADR-0050.R22.N3, ADR-0050.R22.N5

R231. Change path (ADR-0063.R3). Lowering a cap or limit, or raising the reserve share, is immediate, by one person holding `edit` on the leaf `agent`. Raising a cap or limit, or lowering the reserve share, is a loosening: a change proposal approved by another person holding `agent` at `full`, logged in `setting_value`. As for every loosening, a one-person company cannot raise them.
Source: ADR-0050.R22.N2

R232. Hard locks stay: the worst case is reserved before every call (R233); a run that would exceed any cap or limit stops (R238); no company value lies above the installation maximum, refused by the `setting_value` trigger and applied again at read time (ADR-0063.R1); no setting turns reservation off. Lowering reaches running runs: `agent_run.budget` keeps the per-run values in force at start, and each reservation checks the run against the lower of that snapshot and the values in force. Test runs keep ADR-0003.R6; evaluation runs have their own cap (ADR-0050.R40).
Source: ADR-0050.R22, ADR-0050.R22.N2

### Accounting by reservation

R233. Before every LLM call the runtime computes the worst case: counted input tokens times the input price, plus `max_output_tokens` times the output price. `agent_runs.contract.reserve_budget` adds it, in one statement each, to the run's totals and to the `agent_budget_usage` rows of the run: scope `company_agent_type` (company, agent type, business date), `company` (company, business date) and `installation` (installation, day), each guarded by `reserved + spent + amount <= limit`; in Phase 1 the `company_agent_type` row carries the company's cap and checks no per-type limit (R226; ADR-0078.R7). All guards of one call run in one transaction: if any guard fails, nothing is reserved, the call is not made, and the run stops with `budget_exceeded`.
Source: ADR-0050.R23, ADR-0050.R23.N1

R234. Each guarded statement first sets the row's `limit_amount` (and `run_limit_count`) to the limit in force for that business date from `registry.contract.get_setting`, so a lowering applies at the next reservation, and a row whose spent amount already exceeds a lowered limit accepts nothing more. A run of an agent type that reads outside content, and any run that is tainted when it reserves, also reserves on the row of scope `company_outside_content` (company, business date), whose limit is (1 − `agents.internal_reserve_share`) × the company cap in force, rounded down to the cent; an internal run reserves on its agent type, company and installation rows only, so the reserve stays free for it. `INV-212` covers the new row like every `agent_budget_usage` row; `DS-05-platform.sql` adds the scope kind.
Source: ADR-0050.R23.N1

R235. After the call, `settle_budget` replaces the reservation by the actual cost. A failed call settles at the provider's reported usage, or zero when it reports none; a call whose outcome is unknown settles at its reserved amount (R208).
Source: ADR-0050.R23

R236. Budget day. Every budget day is the company's business date (`clock.today`, ADR-0007.R15), the installation's daily row included: it is keyed by the business date of the company whose run reserves, so "per installation and day" means per business date.
Source: ADR-0050.R22.N1

R237. Counts and time. LLM calls, tool calls and rows read are checked the same way before each call (rows against the query's `limit`). Before each step the runtime checks the remaining time; a step that cannot start in time ends the run with `time_exceeded`. An LLM call's timeout is the remaining time. So no run and no daily row ever exceeds its limit, also with runs in parallel; `INV-212` checks it, and the lab checks interleavings.
Source: ADR-0050.R23

### Circuit breakers

R238. Daily (spec 03 rule 8). When a daily guard fails, `StartAgentRun` for that scope returns `agent_budget_exceeded` until the next business date and the wake-up consumer skips. Work items stay with people (Principle 12). In Phase 1 the daily guard per company, agent type and date is not checked, because the per-type limits are removed; the daily guards are the company row, the installation row and the outside-content pool (ADR-0078.R7).
Source: ADR-0050.R24, ADR-0050.R24.N2

R239. `agent_budget_exhausted` tells the company's owner. It is raised once per business date and tier that trips, with the open keys `company:<business date>`, `outside_content:<business date>` and `installation:<business date>` (ADR-0050.R55); its subject is the agent type whose reservation failed. When the outside-content pool trips, types that read outside content stop and internal types keep running on the reserve until the company row trips.
Source: ADR-0050.R24, ADR-0050.R24.N1, ADR-0050.R24.N2

R240. Provider: the circuit of ADR-0050.R6. No loops: a stopped run is never restarted automatically; a new run on the same item needs a person, or a new raise.
Source: ADR-0050.R24

### Run taint

R241. `agent_run.tainted_at` (ADR-0029.R10) is set once and never cleared, with its source columns (`taint_source_kind`, `taint_source_table`, `taint_source_id`). It is set at start (ADR-0050.R15), or by the dispatcher's query path just before it returns to the run any of: a non-null `is_untrusted` field; a row whose effective `is_tainted` is true; a work item with `is_tainted`; the content of an attachment whose source kind is outside content.
Source: ADR-0050.R25

R242. A generated file (attachment source kind `generated`) whose rendered instance held a non-null `is_untrusted` field carries `contains_untrusted`. Returning its content to a run taints the run as an attachment from outside content does, with `taint_source_kind` `untrusted_field` and source table `attachment` (ADR-0049.R28). The other values of `taint_source_kind` are `work_item`, `outside_subject`, `tainted_row` and `outside_attachment`.
Source: ADR-0050.R25.N1

R243. Commit first. The dispatcher calls `agent_runs.contract.mark_run_tainted` in its own committed transaction before it returns the result. If that commit fails, the result is not returned. So every later command of the run starts after `tainted_at`, and `recorded_at` comparisons (`INV-88`) hold.
Source: ADR-0050.R25

R244. Inputs after taint. From `tainted_at` on, the runtime refuses, before the gateway call or the dispatch, a context item or a command input whose recorded source row (ADR-0050.R8; `context_refs`, `request_refs`) is outside the tainted read scope (ADR-0050.R27), also when the row was read before the taint, with `tainted_read_out_of_scope`. Only the runtime knows that provenance. A row reached through recorded provenance from a row in scope is in scope, for example the item behind the `item_id` of the partner's `partner_item` row.
Source: ADR-0050.R25

R245. The dispatcher's check. As a second line, the dispatcher checks every reference-typed ID in a tainted run's payload whose table has a partner or import batch scope column, or is a document, against the run's scope and its drafts (ADR-0050.R27). References to tables without such a column (items, units) are covered by the runtime's provenance check. The command envelope of ADR-0008 does not change.
Source: ADR-0050.R25

R246. Aggregates. A deterministic aggregate (a sum, count or balance) computed over rows that include tainted versions does not taint the run: taint guards against untrusted text, and an aggregate carries none. Individual rows of tainted versions still taint. This reading is flagged for the author (open question).
Source: ADR-0050.R25

R247. One place. Run taint applies to every query result returned to a run: views, module queries and the results and check details of commands, using the result model's field attributes. It does not depend on the agent asking nicely.
Source: ADR-0050.R25

### Tool lists and effective permissions

R248. Tool lists (spec 03 rule 2; ADR-0008.R6). An agent type version's tool list names registered queries and commands; nothing is inferred from a prompt. In Phase 1 the tool list lives in the agent type's `AgentTypeDeclaration`, and `check` refuses any entry on the list of R250 and any command not registered `is_draft_only` (ADR-0078.R3, ADR-0078.R4).
Source: ADR-0050.R29, ADR-0050.R30.N7

R249. Tool definitions are generated from the registry with the same names (`snake_case`, ADR-0004.R19) and JSON Schemas as the MCP tools. They state each tool's side-effect class (`read` for queries, `draft` for `is_draft_only` commands, the only classes agents get) and its allowed states as preconditions; the dispatcher enforces them, not the description (ADR-0059 X2; ADR-0059.R26). NativeFlows's own runs call the dispatcher in process; outside MCP clients use the MCP transport with their own credentials. The dispatcher checks every call against the run token's tool list and rejects others with `tool_not_allowed`, with a denial record. The tool list is step 2 of the dispatcher's check order, first after the credential and before `human_only`, `proposal_required` and permission (DS-04).
Source: ADR-0050.R29, ADR-0050.R29.N1, ADR-0050.R29.N2

R250. Never on a tool list (a registry CI check and `INV-214`):
- commands of effect class `posting`, and every `Submit<Type>`, `Post<Type>` and `Issue<Type>`: people submit, post and issue agent drafts, which in Phase 1 also covers the release of production orders by `Submit` (ADR-0034.R5); agents create change proposals as drafts, a person submits them (ADR-0029.R3), and a person other than the human the run acted for approves them (ADR-0017.R16);
- commands registered `human_only` or of effect class `outbound_send`;
- `Approve<Type>`, `Reject<Type>`, `ClearTaint`, `ConfirmAutoPost`, `UpdateAgentTypeSetting`, `CreateAgentPromotionEvidence`, policy rule and procedure commands, role assignments;
- `StartAgentRun`, `CancelAgentRun`, `CompleteAgentRun` (no agent starts agents), and claim, assign and resolve commands of work items (the runtime manages the run's claim);
- audit queries (ADR-0038.R7), `ListAgentRun`, `GetAgentRun`, `ListAllowedCommand`, `GetSessionContext`, `GetPolicyEvaluation`, and `CreateListExport` (ADR-0050.R54).
Source: ADR-0050.R30

R251. Allowed-target commands of ADR-0029.R2 (effect class `master_data_change` or `is_proposal_bound`) are kept off tool lists too, a registry check that `INV-214` covers: agents reach them only through `CreateChangeProposal`, so an agent run that calls one directly gets `tool_not_allowed`, and `proposal_required` is met by consumer commands carrying an origin run (`EC-56`).
Source: ADR-0050.R29.N1

R252. Also never on a tool list:
- `SetDataProcessingPermission` and `EndDataProcessingPermission`; `CreateExtractionFields` is on `document_reader`'s list for workflow code only (ADR-0057.R11, ADR-0057.R20);
- `CreateArtifactEvidence`, `SetArtifactVersionState`, `SetArtifactCurrentVersion`, `RecordGoldenCaseLabel`, `ListGoldenCaseLabel`, `CreateAutomationRule`, `UpdateAutomationRule`, `ConfirmAutomationRuleOwnership`, `CreateDecisionTable`, `CreateParameterSet`, `DisableAutomationRule` and `EnableAutomationRule`; agents draft artifact versions only (ADR-0059.R27; ADR-0058.R27);
- `ListAnalysisResultRow`, the list query through which people export analysis results, and `ListAnalysisQuestion` (ADR-0060.R14, ADR-0060.R17);
- `TransferStockReservation` (accepted only from a change proposal's execution), `ImportOperationConfirmation` (an integration's command) and `RunProductionOrderCheck` (a system job) (ADR-0064.R12, ADR-0064.R24, ADR-0064.R25; `INV-730`);
- `CreateAssistRequest` and `GetAgentBudgetStatus` (ADR-0077.R14, ADR-0077.R17);
- the queries `ListConversation`, `ListMessage`, `ListNotification` and `ListNotificationPreference`; no agent type's tool list may name them (ADR-0076).
Source: ADR-0050.R30.N1, ADR-0050.R30.N2, ADR-0050.R30.N3, ADR-0050.R30.N4, ADR-0050.R30.N5, ADR-0050.R30.N6

R253. Effective permissions are the intersection of the agent type's declared permissions and those of the human acted for, re-evaluated at every call against current assignments, for permissions, record scope and field classes (ADR-0017.R11). Agent types get no role assignments, so no further set of rights joins this intersection; the human's owner scope binds the run as their record scope does (ADR-0054.R16). A tainted run's read scope (ADR-0050.R27) narrows that further. The tool list is a third limit: a tool must be on the list and allowed by the intersection.
Source: ADR-0050.R31, ADR-0050.R31.N1

R254. For analysis plans the fact-view permissions and their read grants are those of the run's human alone: the `analysis` agent type holds no `List<fact view>` permission, and its limit on facts is that `EvaluateAnalysisPlan`, `GetAnalysisPlanExplanation`, `ListAnalysisCellRow` and `ListAnalysisDimensionMember` are on its tool list; field classes stay the intersection (ADR-0060.R13).
Source: ADR-0050.R31.N2

### LLM steps and repeated denials

R255. Read tools only. An LLM step's tools are a subset of the tool list holding only queries. Commands on the list are called by workflow code, never chosen by the model.
Source: ADR-0050.R32

R256. Every command is built by workflow code from a validated output (R261 to R267), sent in simulate mode, checked against the step's deterministic expectations, then executed with the simulated `plan_hash` (Principle 2). In `shadow` mode, which returns in Phase 2 (ADR-0078.R5), the execute call is skipped.
Source: ADR-0050.R32

R257. Keys. Idempotency keys are `<agent_run_id>:<step_code>:<n>`. Drafts carry `origin_work_item_id`, `workflow_step` and `draft_ordinal` (ADR-0030.R11). A `duplicate_draft` on a re-run is read as "already done": the runtime continues with the draft it names.
Source: ADR-0050.R32

R258. `ListAllowedCommand` stays people-only in Phase 1 (ADR-0040.R8). Agents plan from their fixed tool list and from simulate mode, whose refusals are recorded. The rule marks this as the proposed answer to the open question.
Source: ADR-0050.R34

R259. Repeated denials stop (ADR-0017.R8). The runtime counts every denial code returned to the run in `agent_run.denial_count`: the codes of ADR-0038.R5 and its note, including those ADR-0050 adds. It does not count denial records, which are coalesced and may be dropped (ADR-0038.R5). `llm_routing_refused` and `work_item_claim_lost` are not counted: they end the run with `routing_blocked` and `claim_lost`.
Source: ADR-0050.R33, ADR-0050.R33.N1

R260. The third denial stops the run with outcome `denials_repeated`, and `agent_denials_repeated` is raised for the company's owner, with the run and the denial codes as evidence. Workflow code is written so that a clean run gets no denials; CI fails a golden case that produces one.
Source: ADR-0050.R33

### Output schemas and deterministic checks

R261. Every LLM step declares a pydantic output model (unknown fields rejected, ADR-0008.R3) with a version. Output schemas never hold a field for the model's own confidence, score or probability (Principle 3); a CI check rejects field names `confidence`, `score`, `probability` and `certainty`. The runtime parses and validates every output, also from providers that promise schema conformance.
Source: ADR-0050.R35

R262. Bounded retries. An invalid output, a refusal or a cut-off output gets at most two retries (at most 3 attempts), each with the validation errors (codes and paths, without echoing the invalid text) added to the request. Retries count against budgets. After the third failure the step fails with `llm_output_invalid`, and the run stops with outcome `output_invalid` (R218).
Source: ADR-0050.R35

R263. Deterministic checks run after validation, per step (named in ADR-0051). References in an output must be handles or IDs that the step's input contained; anything else is rejected as invalid output. Codes must exist in their catalogs; enumerations are closed.
Source: ADR-0050.R36

R264. Stated values. A value extracted from a document (a quantity in a request, a reference token in a bank description) must appear in its quoted source span in the input after normalization; otherwise it is dropped.
Source: ADR-0050.R36

R265. No computation. No output value becomes a price, tax, quantity to post, account or match score. Prices, taxes and accounts come from the deterministic functions that own them (ADR-0045.R4, ADR-0047.R16, ADR-0041, ADR-0015); a requested quantity is shown as stated by the customer.
Source: ADR-0050.R36

R266. Free text an output carries (an explanation, a quotation text) is checked: every number in it must equal a number of the step's input or of the draft. Analysis explanations hold this by construction: in Phase 1 the model writes no text that reaches the person; code renders every number as a key fact from fixed templates, the model returns only a narrative plan of claim template codes with fact handles, code renders the members from each fact's row, checks each claim's precondition on the served cells, drops the steps that fail, and renders the rest from the claim catalog (ADR-0060.R23; `INV-413`).
Source: ADR-0050.R36, ADR-0050.R36.N1

R267. Customer-facing text is also checked by the outbound content check of ADR-0029.R14, which module `crm` owns and exposes as the query `GetOutboundContentCheck`. A module that owns customer-facing drafts, such as `sales`, may not import `crm` (same layer), so it declares an outbound-check hook that `crm` registers and `app` (layer 6) wires, the pattern of the policy evidence hook (ADR-0051.R18). The handler of every command that creates or updates a customer-facing draft calls the hook, so a finding is the check result `outbound_content_flagged` in that command's plan. The workflow treats it as a failed check. The check never runs through a send command.
Source: ADR-0050.R36

### Run modes and replay

R268. Run modes (`agent_run.mode`): `live`; `shadow` (ADR-0050.R14); `replay`, with recorded outputs; `evaluation`, live calls against the golden set. Replay and evaluation runs happen only in `test` and `simulation` environments, or on staging (ADR-0003.R12). The DDL keeps `shadow` for Phase 2: Phase 1 starts no live shadow run of an agent (ADR-0078.R6).
Source: ADR-0050.R37

R269. Matching. The `replay` adapter returns the recorded response for (step code, ordinal, attempt) when the new request's `request_hash` equals the recorded one. A different hash is a divergence: strict replay fails with `replay_diverged` (a harness result, not an API error); comparison replay records the divergence and continues live.
Source: ADR-0050.R38

R270. The determinism contract. The same database state, agent type version and recorded responses give the same tool calls, the same commands and the same plan hashes. CI checks this per golden case. Rendering is canonical (sorted keys, canonical numbers and dates, ADR-0006.R13, ADR-0007.R3), so the hash is stable. Re-run for comparison: the same cases run live with another model, seat setting or template version, and their outputs are compared with the recorded run and with the known answer (ADR-0050.R39).
Source: ADR-0050.R38

## Invariants

Statements are those of `invariants.csv`. Each row stands once in the module, in the chunk that states the rule its catalog source names.

| Invariant | Name | Check point | Statement | Protects |
| --- | --- | --- | --- | --- |
| `INV-210` | `tainted_run_outputs_tainted` | day | Every outbox event, work item raise and work item note written by an agent run tainted at the row's `recorded_at` (`tainted_at` at or before it, the instant `INV-88` uses), or by a consumer whose origin run was tainted at the origin event's `recorded_at`, has `is_tainted` true. | R216, R241, R243 |
| `INV-211` | `agent_commands_on_tool_list` | day | Every audit record with an `agent_run_id` names a command on the tool list of that run's agent type version. | R248, R249 |
| `INV-212` | `agent_spend_within_budget` | day | Every ended agent run's totals are within its budget snapshot and its reservations are zero; every `agent_budget_usage` row's spent plus reserved amount is within its limit. | R226, R232, R233, R234, R237 |
| `INV-214` | `agent_tool_lists_safe` | day | No agent type version's tool list holds a command of effect class `posting`, a `Submit`, `Post` or `Issue` command, a `human_only`, `outbound_send` or `is_internal_only` command, an allowed-target command of ADR-0029.R2 (effect class `master_data_change` or `is_proposal_bound`), an approval, taint clearing, auto-post confirmation, policy, role, agent-setting or promotion-evidence command, an agent run command or query, a work item claim, assign or resolve command, an audit query, `ListAllowedCommand`, `GetSessionContext`, `GetPolicyEvaluation` or `CreateListExport`. | R250, R251 |

Named by rules of this chunk, with their rows in other chunks: `INV-88` (R243), `INV-413` (R266), `INV-730` (R252).

## Edge cases

| Edge case | Name | Case | Outcome | Protects |
| --- | --- | --- | --- | --- |
| `EC-83` | `agent_run_resumed_after_crash` | A quotation run's worker crashes after an LLM call; the retry replays the recorded step and continues, and the quotation is drafted once. Phase 2 case: it starts from the deferred `quotation` agent, and its check is re-hosted on `purchase_invoice` and the assistant (ADR-0078.R9a). | `must_succeed` | R208, R209, R269 |

Named by rules of this chunk, with its row in another chunk: `EC-56` (R251).

## Settings

| Key | Value type | Scopes | Core default | Rule |
| --- | --- | --- | --- | --- |
| `agents.company_daily_max_cost` | amount (USD), bounds `0..`, `lower_tighter` | `installation`; `company` | 50 | R227, R228, R229 |
| `agents.installation_daily_max_cost` | amount (USD), bounds `0..`, `lower_tighter`; storage `deployment`, leaf `operator` | `installation` | 200 | R227, R229 |
| `agents.internal_reserve_share` | decimal, bounds `0..0.9`, `higher_tighter` | `company` | 0.40 | R230, R231, R234 |

Named by rules of this chunk, with its row in another chunk: `agents.<agent_type>.wake_up_mode.<kind>` (R202). The agent-type budget keys of R226 are absent from `settings.csv` by ADR-0078.R7.

## Conflicts

CONFLICT ADR-0050.R17: ADR-0050.R17.N1 governs who may cancel; "or the company's owner" is not restated, the capability `cancel_agent_runs` takes its place (R220).
CONFLICT ADR-0050.R17.N1: the note replaces the company owner's right to cancel by the capability `cancel_agent_runs` (`full` on `agent`), following ADR-0054.R24; stated in R220.
CONFLICT ADR-0050.R22: ADR-0050.R22.N2 governs; "Lowering only", the author's reserve on raising and the open question on the values are not restated (R227, R231). ADR-0050.R22.N3 (ADR-0078.R7) removes every per-type limit in Phase 1, so the version-declared `daily_max_cost` and `daily_max_runs` bind no run (R225, R226).
CONFLICT ADR-0050.R23: ADR-0078.R7 governs the per-type row: its limit is the company's cap in force and the reservation checks no per-type limit (R233, R234).
CONFLICT ADR-0050.R32: the skipped execute call of `shadow` mode is Phase 2 under ADR-0078.R5 and ADR-0078.R6 (R256).
CONFLICT ADR-0050.R37: the run mode `shadow` stays in the DDL for Phase 2; Phase 1 starts no live shadow run, under ADR-0078.R6 (R268).
CONFLICT ADR-0050.R22.N2: ADR-0050.R22.N3 governs the company values; the agent-type keys the note defined are removed from `settings.csv` (R226), and ADR-0050.R22.N5 names `analysis` and `planning` as the Phase 1 internal types instead of the example `production` (R230).
CONFLICT ADR-0050.R24: ADR-0050.R24.N2 governs the daily guard; in Phase 1 no guard per company, agent type and date is checked, and `agent_budget_exhausted` is raised per business date and tier (R238, R239).

## Trace

| Source | Where |
| --- | --- |
| ADR-0050.R16 | R201, R204-R210 |
| ADR-0050.R16.N1 | R202, R203 |
| ADR-0050.R16.N2 | R202 |
| ADR-0050.R17 | R215-R218, R220 |
| ADR-0050.R17.N1 | R220 |
| ADR-0050.R17.N2 | R219 |
| ADR-0050.R20 | R221, R222 |
| ADR-0050.R20.N1 | R221 |
| ADR-0050.R21 | R223, R224 |
| ADR-0050.R22 | R225-R228, R232 |
| ADR-0050.R22.N1 | R236 |
| ADR-0050.R22.N2 | R225-R228, R230-R232 |
| ADR-0050.R22.N3 | R226, R228, R230 |
| ADR-0050.R22.N4 | R229 |
| ADR-0050.R22.N5 | R230 |
| ADR-0050.R23 | R233, R235, R237 |
| ADR-0050.R23.N1 | R233, R234 |
| ADR-0050.R24 | R238-R240 |
| ADR-0050.R24.N1 | R239 |
| ADR-0050.R24.N2 | R238, R239 |
| ADR-0050.R25 | R241, R243-R247 |
| ADR-0050.R25.N1 | R242 |
| ADR-0050.R26.N2 | ref: ADR-0050.R26.N2 |
| ADR-0050.R27.N3 | ref: ADR-0050.R27.N3 |
| ADR-0050.R29 | R248, R249 |
| ADR-0050.R29.N1 | R249, R251 |
| ADR-0050.R29.N2 | R249 |
| ADR-0050.R30 | R250 |
| ADR-0050.R30.N1 | R252 |
| ADR-0050.R30.N2 | R252 |
| ADR-0050.R30.N3 | R252 |
| ADR-0050.R30.N4 | R252 |
| ADR-0050.R30.N5 | R252 |
| ADR-0050.R30.N6 | R252 |
| ADR-0050.R30.N7 | R248 |
| ADR-0050.R31 | R253 |
| ADR-0050.R31.N1 | R253 |
| ADR-0050.R31.N2 | R254 |
| ADR-0050.R32 | R255-R257 |
| ADR-0050.R33 | R259, R260 |
| ADR-0050.R33.N1 | R259 |
| ADR-0050.R34 | R258 |
| ADR-0050.R35 | R261, R262 |
| ADR-0050.R36 | R263-R267 |
| ADR-0050.R36.N1 | R266 |
| ADR-0050.R37 | R268 |
| ADR-0050.R38 | R269, R270 |
