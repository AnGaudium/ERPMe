# Agents: the current design for Phase 1

Generated 2026-11-19 from ADR-0078, ADR-0050 and ADR-0051 with their notes, ADR-0029, ADR-0043 rule 9, ADR-0054 rules 11, 16 and 24, ADR-0077 rules 13–18, ADR-0057 (the deterministic ladder only), ADR-0048 (rules 8, 9 and 5), ADR-0063 (agent settings) and the rows `agents.*` and `assist.*` of `docs/catalogs/settings.csv`.

A rule cites its source as `ADR-nnnn rule n` or `ADR-nnnn rule n note`. A "note" is a "Note (" paragraph at the end of that rule. Where a rule has no cite, it joins the rule before it.

## 1. Purpose and precedence

1.1 This file is for a coding agent that builds Phase 1. It states only what applies in Phase 1. Read it instead of the eleven ADRs.

1.2 The ADRs win wherever this text disagrees with them. Fix the text, not the ADR.

1.3 This text is regenerated when an ADR changes. Do not edit it by hand to change a rule (ADR-0078 rule 10).

1.4 Precedence when sources differ: ADR-0078 first, then the notes of ADR-0050 and ADR-0051, then their rule text, then the other ADRs (ADR-0078 rule 9, Decision).

1.5 The safety model is unchanged by Phase 1. The hard floors, the permission intersection, taint, the tainted read scope and drafts-only all stay. Changing them is the author's decision (ADR-0078 Decision; ADR-0005 item 7).

1.6 If `llm_provider` is unset, the LLM is off. Every agent mode is then `off` and every operation still works by hand (ADR-0050 rule 5).

## 2. Phase 1 agent types

2.1 Phase 1 has exactly three agent types (ADR-0078 rule 1):

| Agent type | Trigger / subject | What it drafts | Starts after |
| --- | --- | --- | --- |
| `bank_matching` | Work item `bank_line_unmatched`; subject: one `bank_statement_line` (ADR-0051 rule 17) | No document. It stores a suggestion on the line (tokens, payer name, purpose) with `RecordBankLineSuggestion`. A `cash` consumer may then draft a receipt or payment from it (ADR-0051 rules 17, 18) | step 6 gate |
| `purchase_invoice` | Work item `supplier_invoice_received`; subject: a stored incoming `e_invoice_record` (ADR-0051 rule 20) | A purchase invoice draft, and one change proposal with `CreatePartnerItem` mappings (ADR-0051 rule 21) | step 7 gate |
| `assistant` | A person: the UI assist panel or command bar, with an `assist_request` row as subject (ADR-0077 rules 13, 14) | Answers, drafts and change proposals through `is_draft_only` commands (ADR-0077 rules 13, 17) | step 5 gate |

2.2 A Phase 1 agent type is one of these three. Adding one is a scope change for the author (ADR-0078 rule 1; ADR-0005 item 2).

2.3 Each type has its own authorization leaf `agent_<agent_type>`, below the leaf `agent` (ADR-0050 rule 12 note; ADR-0054 rule 24 note). The assistant's is `agent_assistant` (ADR-0077 rule 13).

2.4 `agent_type` codes are `snake_case` nouns (ADR-0050 rule 12).

2.5 The other agent types are registered with mode `off` and no workflow code. See section 13 (ADR-0078 rule 2).

## 3. Declarations

3.1 An agent type is one typed Python declaration, like a command (ADR-0078 Decision, ADR-0073). It lives in `backend/src/nativeflows/agents/declarations/<agent_type>.py` as one `AgentTypeDeclaration` named `DECLARATION`. `generate` writes it into the agent type catalog (ADR-0078 rule 3).

3.2 The declaration holds (ADR-0078 rule 3):
- `agent_type` and `version` (semver);
- the subject tables it may start from, and the work item kinds that wake it;
- the tool list: registered queries, plus commands registered `is_draft_only`;
- the output schema of each LLM step (ADR-0050 rules 35, 36);
- the per-run ceilings: LLM calls, tool calls, input tokens, output tokens, cost, seconds and rows read;
- the seat and data class of each LLM step (spec 17);
- the path of its evaluation set and its pass threshold.

3.3 The declaration is the only place these values live. The prose of ADR-0051 per agent type becomes the declaration's docstring and its workflow steps (ADR-0078 rule 3).

3.4 Prompt templates are Markdown files `backend/nativeflows/agents/prompts/<agent_type>/<template_code>.md` with front matter: `code`, `version`, `seat`, `inputs` (field paths, with `required`) and `output_schema`. A provider overlay is a small file `<template_code>.<provider>.md`. Base and overlay are hashed together. CI fails when a template's hash changes without a version change. A run records template code, version and hash per step (ADR-0050 rule 13).

3.5 `nativeflows-dev check` validates every declaration (ADR-0078 rule 4):
- the tool list names only registered queries and `is_draft_only` commands, and none of the never-list (section 5.6);
- every per-run ceiling is set and within the installation maxima;
- every LLM step has an output schema with no `confidence`, `score`, `probability` or `certainty` field;
- the evaluation set exists, and a version without a passing result cannot be promoted.

3.6 A registry check: a work item kind that a command on any agent tool list can raise may not be declared by any agent type. `agent_task` is such a kind (ADR-0050 rule 16).

3.7 Wake-up kinds are `always` in version 1 of the declared types. A kind may be declared `configurable`, and then the company setting `agents.<agent_type>.wake_up_mode.<kind>` (`always` default, `by_rule`, `off`) applies (ADR-0050 rule 12 notes; ADR-0063 rule 11; `settings.csv`). ADR-0063 rule 11 names `supplier_invoice_received` of `purchase_invoice` as one such kind, "in its next version".

## 4. Starting and running a run

### Starting

4.1 `StartAgentRun` (module `agents`, effect class `other`) writes through `agent_runs.contract.create_run`. Payload: the agent type, and either a `work_item_id`, or a subject (`subject_table`, `subject_id`) for a run a person starts without an exception (ADR-0050 rule 15).

4.2 Who starts it: the consumer `agent_wake_up` for items of kinds the type declares, a schedule, or a person (ADR-0050 rule 15).

4.3 The human acted for (ADR-0050 rule 15):
- A run a person starts acts for that person.
- A run from a schedule acts for the schedule's owner.
- A run triggered by an event or e-mail, which every wake-up is, acts for the setting's required `workflow_owner_id`.
- A mailbox owner or a statement's importer is never the human acted for by being one. The sender of outside content never is.
- That human needs `start_agent:<agent_type>`.

4.4 Actor: from a wake-up or schedule, `StartAgentRun` runs as actor `system` on behalf of that human. From a person, as that person (ADR-0050 rule 15; ADR-0013 rule 9).

4.5 Checks at start (ADR-0050 rule 15):
- the mode is not `off`: else `agent_mode_off`;
- the daily budgets are not exhausted: else `agent_budget_exceeded`;
- the item's kind is declared, and the subject's table is accepted: else `agent_kind_not_declared`;
- the scope resolver finds a scope: else `agent_scope_unresolved`.

4.6 Claim: the handler claims the work item for the run (ADR-0042 rules 9–11), or creates and claims an `agent_task` item for a subject. A held claim fails with `work_item_claimed` (ADR-0050 rule 15).

4.7 Scope: the handler binds the run's scope by the type's scope resolver. The resolver is a pure function of the subject's stored, trusted fields. It never reads an `is_untrusted` field. If it finds no scope, the command fails with `agent_scope_unresolved`, the wake-up consumer skips (no retry) and the item stays with people. The scope never changes during a run (ADR-0050 rule 15).

4.8 Taint at start is decided from the subject row, whoever starts the run (ADR-0050 rule 15). A run starts tainted (`tainted_at` is its start) when:
- its work item has `is_tainted` (`taint_source_kind` `work_item`); or
- its subject row is outside content (`outside_subject`): an inbound interaction, an incoming e-invoice record, a bank statement line, an import batch or row, or any row whose `is_untrusted` is true.

An agent type only lists the subject tables it accepts. It does not decide taint (ADR-0050 rule 15).

4.9 The assistant starts with an `assist_request` row as subject. A run of `purpose` `act` always starts tainted. `ask`, `resolve_command` and `resolve_filter` start untainted (ADR-0050 rule 15 note; ADR-0077 rule 13).

### Wake-ups

4.10 The consumer `agent_wake_up` reacts to `WorkItemRaised` for kinds an agent type declares, in companies where the type's mode is not `off`, and dispatches `StartAgentRun` (ADR-0050 rule 16).

4.11 It skips `WorkItemRaised` events that carry an origin agent run, so nothing in an agent's chain wakes an agent. Only raises wake agents, so a run that unclaims an item never wakes another (ADR-0050 rule 16).

4.12 It skips a configurable kind only while the company's wake-up mode is `by_rule` or `off` (ADR-0050 rule 16 notes; ADR-0063 rule 11).

### Running

4.13 The `external` consumer `agent_runner` of `AgentRunStarted` runs on queue `agents`. Its delivery lease is 5 minutes. The live runner extends `locked_until` every 60 seconds. It calls the gateway with no transaction open (ADR-0050 rule 16).

4.14 At execution start the runner mints a run token bound to the run, agent type version, tool list, human acted for and work item. It expires at `started_at` plus the run's time limit plus 60 seconds and is revoked when the run ends. A retry revokes the old token and mints a new one with the same expiry. The runner dispatches every tool call in process with it (ADR-0050 rule 16).

4.15 A run's LLM calls and tool calls are sequential, never parallel (ADR-0050 rule 16).

4.16 Crash and retry (ADR-0050 rule 16): a dead runner's delivery is retried, at most 3 attempts, and the retry continues the same run.
- It settles each open reservation at its reserved amount, replays the recorded steps through the `replay` adapter up to the last response, then continues live. A request row with no response row is made again.
- A replayed request whose hash differs from the recorded one stops the run with `resume_diverged`. The time limit counts from `started_at`, the crash included (`time_exceeded`).
- After the third failed attempt the run reaper (a system job on queue `jobs`) records outcome `crashed` through `CompleteAgentRun`.

### States and outcomes

4.17 Run states: `queued` → `running` → `completed` | `stopped` | `canceled` (ADR-0050 rule 17).

4.18 `CompleteAgentRun` (effect class `other`) is dispatched by the runner in the transaction that marks the delivery done. It records outcome, totals and output references, unclaims the work item (or resolves the run's `agent_task`), revokes the run token and emits `AgentRunCompleted`. It runs as actor `system` on behalf of the run's human, with the run as `origin_agent_run_id`, so the items it raises carry the run's taint (INV-210). The run's own tool calls run as actor `agent` with the run token (ADR-0050 rule 17).

4.19 Outcomes (ADR-0050 rule 17):

| Outcome | State | Work item |
| --- | --- | --- |
| `drafted`, `no_action`, `not_applicable` | `completed` | Unclaimed, back to its owner, with links to drafts and a note |
| `routing_blocked` | `completed` | Same |
| `claim_lost` | `stopped` | Stays with the person who took it |
| `budget_exceeded`, `time_exceeded`, `output_invalid`, `provider_unavailable`, `resume_diverged`, `crashed` | `stopped` | Unclaimed; `agent_run_stopped` raised |
| `denials_repeated` | `stopped` | Unclaimed; `agent_denials_repeated` raised |
| `canceled` | `canceled` | Unclaimed |

4.20 Repeated denials: the runtime counts every denial code returned to the run in `agent_run.denial_count`. The third denial stops the run with `denials_repeated`, and `agent_denials_repeated` is raised for the company's owner. `llm_routing_refused` and `work_item_claim_lost` are not counted: they end the run with `routing_blocked` and `claim_lost` (ADR-0050 rule 33 and note). Workflow code is written so that a clean run gets no denials. CI fails a golden case that produces one (ADR-0050 rule 33).

4.21 No loops. A stopped run is never restarted automatically. A new run on the same item needs a person, or a new raise (ADR-0050 rule 24).

### Cancel

4.22 `CancelAgentRun` stops a run between steps. The runner checks the state before every step (ADR-0050 rule 17). It needs `start_agent:<agent_type>` of the run's type, or the capability `cancel_agent_runs` (`full` on `agent`) (ADR-0050 rule 17 note; ADR-0054 rule 24 note).

### Records

4.23 Run and body queries (`ListAgentRun`, `GetAgentRun`) are on no agent tool list. Request and response bodies need the capability `read_agent_run_bodies`, held only by the `owner` template (ADR-0050 rule 20 and note; ADR-0054 rule 11).

## 5. Rights

5.1 An agent type version declares a fixed tool list of registered queries and commands. Nothing is inferred from a prompt (ADR-0050 rule 29).

5.2 The dispatcher checks every call against the run token's tool list. A tool not on it gets `tool_not_allowed` and a denial record. The tool list is step 2 of the dispatcher's check order, first after the credential (ADR-0050 rule 29 and note).

5.3 LLM steps read, code writes. An LLM step's tools are a subset of the tool list holding only queries. Commands on the list are called by workflow code, never chosen by the model (ADR-0050 rule 32).

5.4 Every command is built by workflow code from a validated output, sent in simulate mode, checked against the step's deterministic expectations, then executed with the simulated `plan_hash` (ADR-0050 rule 32).

5.5 Effective permissions are the intersection of the agent type's declared permissions (its tool list) and those of the human acted for. They are re-evaluated at every call, for permissions, record scope and field classes. A tainted run's read scope narrows them further. A tool must be on the list and allowed by the intersection (ADR-0050 rule 31 and note; ADR-0054 rule 16).

5.6 Never on a tool list (registry CI check, INV-214; ADR-0050 rule 30 and notes):
- commands of effect class `posting`, and every `Submit<Type>`, `Post<Type>` and `Issue<Type>`;
- commands registered `human_only` or of effect class `outbound_send`;
- `Approve<Type>`, `Reject<Type>`, `ClearTaint`, `ConfirmAutoPost`, `UpdateAgentTypeSetting`, `CreateAgentPromotionEvidence`, policy rule and procedure commands, role assignments;
- `StartAgentRun`, `CancelAgentRun`, `CompleteAgentRun`, and claim, assign and resolve commands of work items (the runtime manages the claim);
- audit queries, `ListAgentRun`, `GetAgentRun`, `ListAllowedCommand`, `GetSessionContext`, `GetPolicyEvaluation`, `CreateListExport`;
- `SetDataProcessingPermission`, `EndDataProcessingPermission` (ADR-0057 note);
- `CreateAssistRequest` and `GetAgentBudgetStatus` (ADR-0077 rules 14, 17).

5.7 Commands of effect class `master_data_change`, and commands registered `is_proposal_bound` (the allowed targets of ADR-0029 rule 2), are kept off tool lists too. Agents reach them only through `CreateChangeProposal`. An agent run that calls one directly gets `tool_not_allowed` (ADR-0050 rule 29 note; ADR-0029 rule 4 note).

5.8 Agent types get no role assignments. No role or level lets an agent approve, receive a delegation or run a `human_only` command. The human's owner scope binds the run as their record scope does (ADR-0054 rule 16 and note; ADR-0050 rule 31 note).

5.9 A consumer command for an event with `origin_agent_run_id` runs with the intersection of the consumer's registered permissions, the agent type's permissions and the human acted for's. It never has effect class `posting` or `master_data_change`. It creates drafts, work items and change proposals only (ADR-0029 rule 12). A human command resets the origin, so the executing consumer of a human approval is not narrowed.

5.10 `UpdateAgentTypeSetting` needs `full` on the leaf `agent`. A change whose resulting `workflow_owner_id` does not hold `start_agent:<agent_type>` in the company is refused with `workflow_owner_not_permitted` (ADR-0050 rule 14 note; ADR-0054 rule 24 note).

5.11 Hard floors that agents meet (ADR-0043 rule 9; ADR-0078 rule 9):
- Permission, record scope and `human_only` commands are checked first.
- Segregation of duties for `Approve`.
- On an effectively tainted version, a non-human `Submit` gets at least the lowest approval rank, and a non-human `Post` or `Issue` gets `human_post` (floor 3).
- Agents only draft: an agent's `Post` or `Issue` gets `human_post` (floor 4).
- An LLM never contributes to an auto-post: a `system` posting of a document with a version written by an agent run, or carrying an origin agent run, gets `human_post` (floor 5).
- Change proposals: their `Submit` always gets at least the lowest rank (floor 7).
- A change of a partner's bank account always goes through a change proposal approved by a person other than its writer, in every company (tenth floor, ADR-0043 rule 9 note; ADR-0029 rule 4).

5.12 Agents never submit, post, issue, send or approve These commands are on the never-list (ADR-0050 rule 30; 5.6). `Submit` from any actor carrying an origin agent run is refused with `origin_run_submit_not_allowed`, before policy (ADR-0029 rule 6 note). Effective rights are the intersection of the type's tool list and the person's rights (ADR-0054 rule 16). ADR-0043 rule 9 adds only `human_post` for agent postings (ADR-0078 rule 9).

## 6. Untrusted content and taint

### Run taint

6.1 `agent_run.tainted_at` is set once and never cleared, with its source columns. It is set at start (4.8), or by the dispatcher's query path just before it returns to the run any of: a non-null `is_untrusted` field; a row whose effective `is_tainted` is true; a work item with `is_tainted`; the content of an attachment whose source kind is outside content (ADR-0050 rule 25).

6.2 Commit first. The dispatcher calls `agent_runs.contract.mark_run_tainted` in its own committed transaction before it returns the result. If that commit fails, the result is not returned (ADR-0050 rule 25).

6.3 A deterministic aggregate (sum, count, balance) over rows that include tainted versions does not taint the run. Individual rows of tainted versions still taint. This reading is flagged for the author (ADR-0050 rule 25).

6.4 Views and query result models omit `is_untrusted` columns unless the request sets `include_untrusted: true`. Listing documents therefore does not taint (ADR-0050 rule 28; ADR-0029 rule 10).

6.5 An agent type that must stay clean declares `may_read_untrusted: false`. For its runs `include_untrusted` returns `untrusted_read_not_allowed`, and rows that would taint are left out with `is_taint_filtered: true` (ADR-0050 rule 28).

### Tainted commands

6.6 A tainted run runs only commands registered `is_draft_only`. The dispatcher rejects any other command from it with `tainted_run_not_allowed`, before policy, with a denial record (ADR-0050 rule 26).

6.7 `is_draft_only` is a registry attribute of commands that only create or update drafts, change proposals, work item notes or suggestion fields. Such a command is never of effect class `posting`, `master_data_change` or `outbound_send`, and never a `Submit`, `Post` or `Issue`. CI checks this (ADR-0050 rule 26).

6.8 `UpdateAssistAnswer` is registered `is_draft_only`. It is on the `assistant` tool list for workflow code only, and writes only the answer fields of its own `assist_request` (ADR-0050 rule 26 note; ADR-0077 rule 14).

### Version taint

6.9 `document_version.is_tainted` is set at insert and never changed. It is true when a run tainted at that time wrote the version (directly or as origin of a consumer chain), or when the version it derives from had effective taint when written (ADR-0029 rule 8).

6.10 A version whose content copies a value from an `is_untrusted` field is written tainted. Example: a matching-rule proposal built from a token an agent read in a bank description (ADR-0029 rule 8).

6.11 No policy decision for a non-human actor is `allowed` on an effectively tainted version or proposal. A tainted version is posted, sent or executed only by a human, or after a human approval (ADR-0029 rule 11 and note).

### ClearTaint

6.12 `ClearTaint` is `human_only`, needs a reason, and writes an immutable `taint_clearance` row. The human for whom the tainted run acted cannot clear it (`segregation_of_duties`). Clearing never changes field attributes or read-taint (ADR-0029 rule 8). It is on no tool list (5.6). Status: interim, flagged for the author.

### Tainted read scope

6.13 A tainted run reads only (ADR-0050 rule 27; ADR-0029 rule 14):
1. rows in its scope: rows whose partner column equals `scope_partner_id` (scope `partner`), rows of `scope_import_batch_id` (scope `import_batch`), or the run's subject row (scope `subject`);
2. its work item, the item's evidence links and its notes;
3. documents and change proposals that it, or an earlier run of the same work item and agent type, wrote, with their plans and check results;
4. reference data: the core catalogs (system accounts, transaction keys, movement types, work item kinds, currencies, units), the active package's data (chart template, administrative units, settings), and registry metadata (schemas, view declarations).

6.14 Everything else returns `tainted_read_out_of_scope`, with a denial record. Company master data outside the scope (other partners, the item catalog, price lists, the company's chart) is not reference data (ADR-0050 rule 27).

6.15 Every view and query result model declares its partner column and import batch column, or none. A query without the run's scope column is refused for a tainted run. Views of reference data are declared `is_reference` and always pass (ADR-0050 rules 27, 49).

6.16 Inputs, not only reads. From `tainted_at` on, the runtime refuses, before the gateway call or the dispatch, a context item or command input whose recorded source row is outside the tainted read scope. This holds also for rows read before the taint. The error is `tainted_read_out_of_scope`. A row reached through recorded provenance from a row in scope is in scope (ADR-0050 rule 25, rule 27).

6.17 Declared projections. A query result model may declare `tainted_projection`: closed shapes and internal names only, at most 20 rows per call and 10 calls per run. While the setting `agents.tainted_reference_reads` reads `declared_projections` (the default), these count as reference data. `literal` narrows it back to the literal scope. The run stays tainted. Beyond the call cap a query returns `tainted_projection_cap_reached`. An agent type version uses a projection only when it names the query on its tool list (ADR-0050 rule 27 note; ADR-0063 rule 16; ADR-0029 rule 14 note). The first instance is `ListItemCandidate`.

6.18 The outbound content check (module `crm`, query `GetOutboundContentCheck`) rejects a customer draft that refers to another partner's records or carries `cost` or `margin` fields, with `outbound_content_out_of_scope`. A command that creates or updates a customer-facing draft calls it through a hook. A finding is the check result `outbound_content_flagged` in that command's plan, and the workflow treats it as a failed check (ADR-0029 rule 14; ADR-0050 rule 36).

## 7. LLM steps

### The gateway

7.1 Every LLM call goes through one gateway in layer 5 `agents`: `agents.gateway.complete(request) -> response`. Provider adapters sit behind it. No other module imports a provider library (ADR-0050 Decision, rules 2, 4).

7.2 Phase 1 uses one provider for all seats: `llm_provider` accepts only `anthropic`. Startup refuses any other value. The `local` adapter is designed but not enabled. Fallback chains never cross providers (ADR-0050 rule 5). The adapters `replay` and `stub` exist for tests and replay (ADR-0050 rule 3).

7.3 `seatmap.yaml` (in `backend/nativeflows/agents/`) names for each seat its capabilities, reasoning level, model per provider, fallback chain within the provider, prices and data class, and the evaluation report that admitted each (seat, model) pair. It changes by commit only. Each seat names a pinned model snapshot, never an alias (ADR-0050 rules 5, 7, and rule 5 note).

7.4 Provider failures: a retryable error is retried at most twice with backoff, within the run's time budget; then the next model of the fallback chain once (an assisted type uses only models in `promoted_seat_models`); then `llm_provider_unavailable`. Five consecutive failures of one (provider, model) in 60 seconds open its circuit for 5 minutes (ADR-0050 rule 6).

### Prompts

7.5 Prompts are rendered by the gateway, never assembled by workflow code. Templates declare their inputs as field paths from query result models, or literals. Workflow code passes context items `(field path, row reference, value)` taken from query results, with the label, field class, `is_untrusted` and `is_secret` attributes the registry declares. Code never passes a free string. A value derived from another keeps the source row (ADR-0050 rule 8).

7.6 Secrets: fields with `is_secret` are in no view and no query result model returned to an agent run. The gateway rejects an item with `is_secret` with `llm_routing_refused`. CI seeds canary values and fails if any appears in a request, step row, span or log line (ADR-0050 rule 11).

### Output schemas and checks

7.7 Every LLM step declares a pydantic output model (unknown fields rejected) with a version, named `<AgentType><Step>Output`, version 1.0.0 (ADR-0050 rule 35; ADR-0051 rule 3).

7.8 No output schema holds a field for the model's own confidence, score or probability. CI rejects the field names `confidence`, `score`, `probability` and `certainty` (ADR-0050 rule 35).

7.9 The runtime validates every output, also from providers that promise schema conformance. An invalid output, refusal or cut-off output gets at most two retries (three attempts), each with the validation errors (codes and paths, without echoing the invalid text). Retries count against budgets. After the third failure the step fails with `llm_output_invalid` and the run stops with outcome `output_invalid` (ADR-0050 rule 35).

7.10 Deterministic checks after validation (ADR-0050 rule 36):
- References in an output must be handles or IDs that the step's input contained. Anything else is invalid output.
- Codes must exist in their catalogs. Enumerations are closed.
- A stated value (a quantity in a request, a reference token in a bank description) must appear in its quoted source span in the input after normalization. Otherwise it is dropped.
- No computation: no output value becomes a price, tax, quantity to post, account or match score. These come from the deterministic functions that own them.
- Free text an output carries: every number in it must equal a number of the step's input or of the draft.

### Deterministic first

7.11 The order of each step: stored rules and mappings, then exact lookup, then fuzzy match with a deterministic score, then an LLM for what remains (ADR-0051 rule 1).

7.12 Fuzzy acceptance: `agents.workflows.rank_candidates` scores candidates by `rapidfuzz` token-set ratio on text folded for case and diacritics. A candidate is accepted without an LLM when its score is at least 92 and leads the next by at least 8. Otherwise the top candidates (at most 5, or 10 where stated) go to an LLM step. The constants belong to the agent type version. Changing them is a new version with an evaluation (ADR-0051 rule 1).

7.13 The LLM never computes or chooses a price, discount, tax, quantity to post, account, match or score. It reads, chooses among candidates that code gave it, and writes text. A stated value is copied as stated, checked against its source span, and shown as stated (ADR-0051 rule 1; ADR-0050 rule 36).

### Seats, data classes and the routing switch

7.14 Each seat declares in `seatmap.yaml` the highest label it may receive: `internal`, `personal`, or `per_routing` (personal when the switch is off). The gateway removes values above the seat's class whatever the switch says, so a step that needs personal values uses a personal seat (ADR-0050 rule 9). In `agent` declarations each LLM step names its seat and data class (ADR-0078 rule 3).

7.15 `routing_switch` is a company setting, change-tracked, default off. With it on, before sending, the gateway replaces every `personal` and `sensitive_personal` value with a typed placeholder `[personal:<table>.<field>]`. It then scans the rendered request for the exact text of every removed value, and rejects the request with `llm_routing_refused` if any remains (ADR-0050 rule 9).

7.16 A step whose template marks a removed input as required is not sent. The run ends with outcome `routing_blocked` and leaves its work item to people (ADR-0050 rule 9).

7.17 Sensitive personal values are never sent to any model in Phase 1, whatever the switch says. No Phase 1 workflow needs them (ADR-0050 rule 9).

7.18 `bank_statement_line` description, counterparty name and counterparty account are `personal`. A value a step extracts keeps the label of its source field (ADR-0050 rule 9).

7.19 The gateway also applies the regime policy and the company's `data_processing_permission` rows to every request that carries a personal value, field values included. Without a permission covering it, the values become placeholders or shape masks, and a step that needs one ends `routing_blocked`. `data_processing.never_send_fields` only narrows. The switch stays the kill switch (ADR-0050 rule 9 notes; ADR-0063 rule 15).

7.20 Processing log: every call that sends at least one personal value, switch on or off, writes one `personal_data_processing_log` entry (purpose, provider, model, whether local, the list of table, field, row ID sent; never values). The entry and the call's `llm_request` step row are committed before the request is sent. If either insert fails, the call is not made (ADR-0050 rule 10; INV-213).

## 8. Budgets and limits

8.1 Phase 1 has two budget tiers (ADR-0078 rule 7):
- Per company per day: `agents.company_daily_max_cost`, within `agents.installation_daily_max_cost`, with the reserve `agents.internal_reserve_share` (default 0 in Phase 1, see 8.6).
- Per run: the ceilings of the agent type version's declaration. For the assistant, `assist.max_cost_per_run` may lower its cost ceiling.

8.2 The nine settings `agents.<agent_type>.daily_max_cost`, `agents.<agent_type>.daily_max_runs` and the seven `agents.<agent_type>.run_max_*` keys are removed. A per-type daily cap returns only if one agent type is measured crowding out the others (ADR-0078 rule 7).

8.3 Per-run ceilings, declared in the declaration (ADR-0078 rule 3): `max_llm_calls`, `max_tool_calls`, `max_input_tokens`, `max_output_tokens`, `max_cost`, `max_seconds`, `max_rows_read` (ADR-0050 rule 22). The declared values of ADR-0051 rule 9 for the two background agents (the agent's proposal, flagged for the author):

| Agent type | LLM calls | Tool calls | Input tokens | Output tokens | Cost (USD) | Seconds | Rows read |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `bank_matching` | 3 | 10 | 15,000 | 2,000 | 0.05 | 120 | 100 |
| `purchase_invoice` | 15 | 60 | 120,000 | 10,000 | 0.60 | 300 | 2,000 |

8.4 The assistant's interim per-run ceilings are 8 LLM calls, 40 tool calls, 40,000 input tokens, 4,000 output tokens, USD 0.50, 120 seconds and 2,000 rows read (ADR-0078 rule 1). `assist.max_cost_per_run` (company setting, default USD 0.20, bounds 0.01 to 0.50) may only lower the cost ceiling. Lowering is immediate. Raising is a proposal another person approves (ADR-0077 rules 13, 14; `settings.csv`).

8.5 Company daily caps (ADR-0050 rule 22 notes; `settings.csv`):
- `agents.installation_daily_max_cost`: installation setting, default USD 200, set at deployment by the operator and logged with the operator account. A raise needs a second operator account.
- `agents.company_daily_max_cost`: default USD 50. The installation value, set at deployment, is the maximum of every company's value. Without one, `agents.installation_daily_max_cost` is. No company cap may exceed it (`setting_out_of_bounds`).
- Every budget day is the company's business date (`clock.today`) (ADR-0050 rule 22 note).

8.6 `agents.internal_reserve_share` (company, bounds 0 to 0.9) is the share of the company's daily cap that only internal agent types may use. No Phase 1 agent type is internal (each may read outside content), so it defaults to 0 in Phase 1. ADR-0050 rule 22's 0.40 returns with the internal types (ADR-0078 rule 7; `settings.csv`).

8.7 Change path (ADR-0050 rule 22 note; ADR-0063 rule 3): lowering a cap or raising the reserve share is immediate, by one person holding `edit` on the leaf `agent`. Raising a cap, or lowering the reserve share, is a loosening: a change proposal approved by another person holding `agent` at `full`. A one-person company cannot raise them.

8.8 Reservation before every LLM call (ADR-0050 rule 23 and note):
- The runtime computes the worst case: counted input tokens times the input price, plus `max_output_tokens` times the output price. `agent_runs.contract.reserve_budget` adds it to the run's totals and to the `agent_budget_usage` rows, guarded by `reserved + spent + amount <= limit`. It checks the company row only. The per-type `company_agent_type` rows keep counting cost and runs with no limit (ADR-0078 rule 7). All guards of one call run in one transaction.
- If any guard fails, nothing is reserved, the call is not made, and the run stops with `budget_exceeded`.
- After the call, `settle_budget` replaces the reservation by the actual cost. A failed call settles at the reported usage (zero if none). A call with an unknown outcome settles at its reserved amount.
- LLM calls, tool calls and rows read are checked the same way. Before each step the runtime checks the remaining time; a step that cannot start in time ends the run with `time_exceeded`.
- Lowering a limit applies at the next reservation. No run and no daily row ever exceeds its limit, also in parallel (INV-212).

8.9 Daily stop: when the company cap is reached, `StartAgentRun` for that company returns `agent_budget_exceeded` until the next business date. The wake-up consumer skips. One `agent_budget_exhausted` item is raised per company and business date, subject the agent type whose reservation failed, and tells the company's owner. Work items stay with people (ADR-0078 rule 7; ADR-0050 rule 24).

## 9. Modes, evaluation and promotion

### Modes

9.1 Phase 1 offers two modes in `agent_type_setting.mode`: `off` and `assisted`. The DDL keeps `shadow` and `active` as values for Phase 2. `check` refuses them in Phase 1 seed and configuration (ADR-0078 rule 5).

9.2 `off`: no runs. `assisted`: runs create drafts and change proposals (ADR-0050 rule 14). Agents never post (ADR-0050 rule 30; ADR-0043 rule 9, floor 4 gives `human_post`), so there is no mode in which an agent posts.

9.3 `agent_type_setting` (company data, change-tracked) holds the agent type, `mode`, `workflow_owner_id` (required unless `off`), and `promoted_version` with `promoted_seat_models`. Default mode for every company: `off` (ADR-0050 rule 14 and notes).

9.4 `UpdateAgentTypeSetting` has effect class `master_data_change`, is change-tracked and `is_proposal_bound`, and is on no agent tool list. A person may lower the mode or change other fields directly. A change that sets `assisted` is accepted only from the execution of an approved change proposal. Otherwise it returns `proposal_required`. A person other than the submitter approves it. An approval by the submitter returns `approver_is_submitter` (ADR-0050 rule 14; ADR-0029 rule 4).

### Evaluation and promotion

9.5 A version is promoted to `assisted` when it passes its evaluation set and the replay of recorded responses in CI. The evidence is the stored evaluation result, named in `agent_type_setting.promoted_version` and `promoted_seat_models` (ADR-0078 rule 6). `CreateAgentPromotionEvidence` computes the evidence from the stored offline evaluation result instead of `GetAgentShadowEvaluation` (ADR-0078 rule 6).

9.6 Spec 17 requires each pair of seat and model to pass. The evaluation result records the pair (ADR-0078 rule 6).

9.7 The offline evaluation runs in CI for each release, so its result is installation-wide. A company already `assisted` stays `assisted` across a new version or seat model whose evaluation for that pair passed; no new proposal is needed. A version or seat model without a passing result runs nothing: where ADR-0050 rule 14 drops the effective mode to `shadow`, Phase 1 drops it to `off`. There is no live shadow period. This applies to all three types, the assistant's `ask` and resolve purposes included (ADR-0078 rule 6).

9.8 The evaluation set and its pass threshold are in the declaration. Each workflow has a golden evaluation set built from the synthetic dataset's input files and the simulator's known answer: the input, the expected drafted commands and the expected outcome. Recordings of the reference run are synthetic and committed under `backend/tests/agents/<agent_type>/` (ADR-0050 rule 39).

9.9 Thresholds: at least 90% of cases equal the known answer, or the higher threshold set for the workflow. Golden set thresholds from ADR-0051 rule 7: `bank_matching` 90%, `purchase_invoice` 95%. The assistant's set has about 50 tasks across its three modes (read answers with correct citations, drafts with correct field diffs, refusals outside its scope, taint handling including pasted untrusted text). It passes at 90% of all tasks and 100% of its refusal and taint tasks, and is a step 5 gate item (ADR-0078 rule 1; ADR-0077 rule 13; ADR-0050 rule 39).

9.10 Replay: the `replay` adapter returns the recorded response when the new request's `request_hash` equals the recorded one. A different hash is a divergence (`replay_diverged`, a harness result). The same database state, version and recorded responses give the same tool calls, commands and plan hashes; CI checks this per golden case (ADR-0050 rule 38).

### Drift

9.11 `RunAgentQualityCheck` (daily system job in `agents`) computes, per company and assisted agent type, the 30-day share of drafts accepted unedited and of drafts rejected or canceled. When agreement falls 10 points below the workflow's threshold, it raises `agent_quality_below_threshold` (owner `company_owner`, due 5 days) with the figures. It does not demote by itself (ADR-0051 rule 5).

9.12 The setting `agents.<agent_type>.drift_action` keeps its values: `signal` (default), `pause_new_runs`, `demote_to_shadow`. `pause_new_runs` makes the effective mode `off` for new runs until a person resolves the item. Until Phase 2, `demote_to_shadow` acts as `pause_new_runs` (ADR-0078 rule 5; ADR-0063 rule 12).

9.13 Effective mode: the stored mode is the person's choice and no command changes it on its own. The runtime computes an effective mode at each start. It stays `assisted` while the version and seat models in use have a passing evaluation (9.7). A version or seat model without a passing result has effective mode `off`, with the reason and work item of 9.14 (ADR-0078 rule 6; ADR-0050 rule 14 note).

9.14 `GetAgentTypeSetting` returns the stored mode, the effective mode and the reason they differ (`version_changed`, `seat_model_changed`). When they first differ, `agents` raises one work item `agent_mode_degraded` (owner `company_owner`, due `days:1`), which resolves when the type is promoted again or its mode is lowered. It is checked at every `StartAgentRun` and by the daily `RunAgentQualityCheck` (ADR-0050 rule 14).

## 10. Outputs to people

10.1 Agents draft documents and change proposals. People submit, approve, post and send (ADR-0051 Decision; ADR-0050 rule 30).

10.2 One batch per output. Each document or proposal is created in one command (or one command batch) at the end of its step, simulated and checked first. A run never leaves half a document (ADR-0051 rule 8).

10.3 Links and notes. The run links each draft to its work item (`link_kind` `draft`, ADR-0042 rule 3) and writes one work item note saying what it did and what it left. A note that quotes outside content is untrusted (ADR-0051 rule 8).

10.4 Change proposals (ADR-0029 rules 1–3):
- `change_proposal` is a non-posting document type. The server computes its items' diff, expected versions and plan; the caller never supplies them. Lifecycle: `draft → pending_approval` by `Submit`; `Approve` or `Reject` by a human; a consumer executes it after approval.
- Agents and their consumers create proposals as drafts only. A person submits them, and a person other than the human the run acted for approves them. No writer of any version approves. The approver must hold the target permissions and every field class the proposal changes.

10.5 In Phase 1 nothing auto-posts except the deterministic bank cascade, disabled by default, with an owner and confirmation (ADR-0078 rule 8; ADR-0048 rule 9; ADR-0063 rule 8). Its details are in 12.13 to 12.16. No other document type auto-posts.

## 11. The assistant

11.1 Its tool list: read queries that the never-list (5.6) does not exclude, commands registered `is_draft_only`, and `UpdateAssistAnswer` for workflow code only (ADR-0077 rule 13).

11.2 A run is started by `StartAgentRun` with the user's `start_agent:assistant`, held at `edit` on the leaf `agent_assistant`, so it acts for that person in that person's own context (ADR-0077 rule 13).

11.3 Typed text reaches the agent through one row. `CreateAssistRequest` is `human_only` and writes an `assist_request` with: `purpose` (`ask`, `act`, `resolve_command`, `resolve_filter`); `text` up to 2,000 characters; the context (`subject_table`, `subject_id`, up to 100 selected IDs, the active filters as JSON, the floorplan code); the requesting user. The UI then sends `StartAgentRun` with the row as subject (ADR-0077 rule 14).

11.4 The run writes its answer to the row through `UpdateAssistAnswer`. Its drafts link to its `agent_task` work item. A live update tells the panel (ADR-0077 rule 14).

11.5 Runs are asynchronous. There is no multi-turn dialogue. A follow-up is a new request that names the previous one (ADR-0077 rule 14; ADR-0050 rule 15 note).

11.6 Taint: a run of `purpose` `act` always starts tainted. `ask`, `resolve_command` and `resolve_filter` start untainted, and taint propagates when they read untrusted data. A tainted run runs only `is_draft_only` commands and reads only the tainted read scope (ADR-0077 rule 13).

11.7 Modes: `ask`, `resolve_command` and `resolve_filter` follow the stated exception of the analysis agent: they answer only the asking person. `act` uses `off` and `assisted` in Phase 1. The assistant is never promoted to `active`, so its drafts always need a person to confirm them (ADR-0077 rule 13).

11.8 Budget: one run costs at most `assist.max_cost_per_run` (default USD 0.20), within the ceiling in 8.4 and the company daily cap. The panel shows the company's remaining daily agent budget through `GetAgentBudgetStatus` (ADR-0077 rules 13, 17; ADR-0078 rule 7).

11.9 Hard rules (ADR-0077 rule 16):
- No screen automation. The agent works only through registered commands and queries on its tool list.
- Nothing is auto-submitted. A draft or proposal opens in the plan panel with its field diff and taint badge, and a person confirms it.
- No UI-only API. The panel, command bar and inline affordances call registered commands and queries through the generated client.
- No pop-ups. Outputs that need attention arrive as work items and in the notification inbox.
- No invented values. A value for a price, tax, quantity, account or score must equal a value in its input or the draft (7.10).

11.10 Inline affordances (ADR-0077 rule 18):
- Fill from document: a dropped PDF or photo calls `RequestDocumentExtraction`; the deterministic intake ladder reads it (see 12.21). Only `ai-fillable` fields are filled.
- Value help may list AI candidates already stored on the draft. They are never selected automatically. No model is called per keystroke.
- `resolve_filter` returns a structured filter validated against the list's filter schema, shown as editable chips before it runs.
- The command bar (`Ctrl/Cmd+K`): `resolve_command` returns a proposed invocation validated against its schema. The bar opens the command's form prefilled and runs simulate. It never executes by itself.

11.11 The assistant also covers, as drafts only, what the deferred agents would help with by hand (ADR-0078 rule 1). At step 11 the assistant in `act` mode may draft migration mappings on a draft import batch (ADR-0078 rule 2).

## 12. The two background agents

### Common

12.1 Both runs start tainted, because their subject is outside content (4.8). They read only their scope (6.13) and run only `is_draft_only` commands in the model-facing path (6.6).

12.2 Both runs act for the workflow owner (`workflow_owner_id` of the type's setting) and need `start_agent:<agent_type>` (ADR-0051 rules 17, 20; 4.3).

### bank_matching

12.3 Trigger: a work item `bank_line_unmatched`, which the agent type declares. Scope `subject`: the statement line, which is outside content (ADR-0051 rule 17).

12.4 D1: the cascade `match_bank_line` already ran at import and found nothing, which is why the item exists. Its order: already posted, reference, account and amount, account and subset, else the item. Company rules `bank_matching_rule` apply before step 3. The scores and the counterparty caps are in ADR-0048 rule 9 and its notes (ADR-0051 rule 17).

12.5 L1 `read_description`: seat classification with personal data, because descriptions are personal. Output `BankMatchingReadOutput`: `reference_tokens` (at most 5), `payer_name_text`, `stable_payer_token`, `purpose` (`invoice_payment`, `advance`, `refund`, `salary`, `tax`, `bank_charge`, `internal_transfer`, `loan`, `unknown`) (ADR-0051 rule 17).

12.6 Checks on L1: every reference token is a whole token of the description and reference-shaped, or it is dropped. The payer name and the stable token are substrings of the description after folding, at least 3 characters long (ADR-0051 rule 17).

12.7 D2 `record_suggestion`: `RecordBankLineSuggestion` (module `cash`, effect class `other`, `is_draft_only`) stores the tokens, name, purpose and run on the line, all `is_untrusted`. It emits `BankLineSuggestionRecorded`, which carries IDs only. Step code `bank_matching.suggest`. The run then ends `drafted` or `no_action`. It never matches, posts or reads partners (ADR-0051 rule 17; ADR-0048 rule 9).

12.8 Re-run of the cascade: a `cash` consumer of `BankLineSuggestionRecorded` runs `match_bank_line` once more, with the suggested tokens added as reference tokens at step 2 only, under step 2's guards. Each token must be a whole token of the description and reference-shaped (at least four characters with a digit, or the package's pattern for its invoice numbers). All the items its tokens name must belong to one partner (ADR-0051 rule 18).

12.9 If it finds items of exactly one partner, it drafts the receipt or payment as ADR-0048 rule 9 does, as `system` on behalf of the run's human. The draft is marked `match_basis` `llm_suggestion` with no score. The draft carries the run as its origin, so it is tainted, and a person posts it (floors 3 and 5). Its data never returns to the run (ADR-0051 rule 18).

12.10 Rule proposals: when a person posts a document matched to a line that carried a `stable_payer_token`, or matches such a line by hand, a `cash` consumer creates a `bank_matching_rule` change proposal as a draft (token → that partner; it never submits it) if the token appears in at least two of that partner's lines in the last 90 days and in no other partner's lines. The proposal copies an untrusted token, so its version is written tainted. A person submits it, and a person approves it (ADR-0051 rule 19; ADR-0029 rules 3, 5). ADR-0078 rule 8 keeps these stored-resolution proposals in Phase 1.

12.11 Failures: no usable token gives a note and outcome `no_action`. With the routing switch on, descriptions are personal and L1 cannot be sent, so every run ends `routing_blocked` (ADR-0051 rule 19).

12.12 Whether matches from an approved LLM-proposed rule may auto-post stays governed by ADR-0063 rule 8: `cash.auto_post.accept_llm_originated_rules` defaults false and may be enabled only by an approved loosening. The author's lift of 2026-11-16 stays (ADR-0078 rule 8; ADR-0065 rule 12; ADR-0063 rule 8 note).

### The bank cascade's auto-post

12.13 Only cascade matches with a score and no LLM contribution may auto-post, under an enabled rule. It is disabled by default. It needs shadow-mode evidence of the deterministic cascade (the ADR-0059 lifecycle, which stays), an owner and confirmation (ADR-0078 rule 8; ADR-0048 rule 9; ADR-0051 rule 18; ADR-0043 rule 14).

12.14 Its evidence is `GetAutoPostShadowEvaluation` (module `cash`). `EnablePolicyRule` for such a rule obtains it through an evidence hook that `policy` declares and `cash` registers, wired by `app`. It is rejected with `shadow_evidence_insufficient` unless it covers at least 300 proposals over at least two statement months, with at least 99% posted unchanged and no proposal posted to another partner. The 300 and 99% are the default of `auto_post.max_error_rate` (ADR-0051 rule 18 and notes; ADR-0063 rule 10).

12.15 Drafts from a statement imported by an agent run are never auto-posted. `llm_suggestion` drafts never auto-post (ADR-0048 rule 9; ADR-0051 rule 18).

12.16 The owner confirms auto-posts with `ConfirmAutoPost` before the period locks. An unconfirmed auto-post blocks `LockPostingPeriod` (ADR-0029 rule 13). The tuned-artifact lifecycle (backtest, shadow, assisted, active, rollback) stays, because the cascade uses it. Only AI drafting of artifacts is deferred (ADR-0078 rule 8).

### purchase_invoice

12.17 Trigger: a work item `supplier_invoice_received`, raised for a stored incoming e-invoice record (`e_invoice_record`, `direction` `incoming`). The agent never parses a raw attachment itself. Until the e-invoice add-on exists, the same record is created when a person imports an XML file through the package's reader (ADR-0051 rule 20).

12.18 Scope `partner`: the supplier whose normalized tax ID equals the record's verified seller tax ID, when exactly one active supplier has it, and only if the record's signature check passed. Without a passed signature check, a run starts only after the person who imported the record has confirmed its supplier (`ConfirmEInvoiceSupplier`). Otherwise `StartAgentRun` fails with `agent_scope_unresolved` and the item stays with people (ADR-0051 rule 20).

12.19 Taint: the record's structured fields are not untrusted. Free text and codes from the seller (`seller_name`, `order_reference`, `seller_item_code`, `item_name`, `unit_text`, notes) are. The record is outside content, so the run starts tainted (ADR-0051 rule 20).

12.20 Inputs: the record's header and lines, `partner_overview`, `partner_item_overview` (the supplier's `partner_item` and `supplier_item` rows), and the supplier's open purchase order lines from `document_line_overview` with ordered, received and invoiced quantities (ADR-0051 rule 20).

12.21 The record path and the ladder (ADR-0051 rule 20 and notes; ADR-0057 rules 4, 6, 25, 26):
- `EInvoiceRecordReader` is network-free and deterministic. It parses one XML file into the record's fields and lines and returns `signature_state` (`passed`, `failed`, `absent`).
- `ImportEInvoiceRecord` (module `tax`) runs the reader, refuses a second record with the same supplier-invoice key (`duplicate_external_document`), and writes the record. When the signature did not pass, its plan carries `e_invoice_signature_unverified`.
- In the same transaction `tax` raises `supplier_invoice_received` for the record.
- The deterministic ladder of intake stays in Phase 1: structured XML, XML embedded in a PDF, QR and vCard, spreadsheet cells, PDF text layer confirmed by OCR, OCR words. A system job runs it, not an agent. The vision rung (rung 7, agent type `document_reader`) is deferred and the vision seat stays disabled (ADR-0078 rule 2; ADR-0057 rule 4).
- A record without a passed signature is imported quarantined (`is_quarantined`): it holds no supplier-invoice key and the agent waits for `ConfirmEInvoiceSupplier` (ADR-0057 rule 25).

12.22 D1 `check_record`: the status check of the reader; the signature check or supplier confirmation was already required to start. The duplicate key: the draft's simulation returns `duplicate_external_document`, and the run ends `not_applicable` naming the existing document (ADR-0051 rule 21).

12.23 D2 `map_lines`: per line, the supplier's item code against `partner_item`; else the supplier's `supplier_item` code; else `rank_candidates` over the supplier's related items. The unit maps through the partner item's unit text, `uom_alias`, then a unit code. A line whose unit text resolves to nothing stays unresolved with `unit_text_unresolved` and D5 also proposes an alias (`CreateUomAlias`) (ADR-0051 rule 21 and note).

12.24 L1 `choose_item`, for unmapped lines: seat classification, and the personal seat when the supplier is an individual or sole proprietorship. Input: the line's name and unit and at most 10 candidates from the supplier's related items. Output `PurchaseInvoiceChooseItemOutput`: `choice` (handle or `none`), `reason_code`. Checks: the handle was offered; the line's unit converts to one of the item's units; otherwise `none` (ADR-0051 rule 21).

12.25 D3 `select_order_line`, per mapped goods line: the purchase order named in the record's order reference and its line for the item; else the only open line for the item; else the oldest open line whose received but uninvoiced quantity covers the line; else unresolved. Pure, on canonical order (date, then ID) (ADR-0051 rule 21).

12.26 D4 `draft_invoice`: `CreatePurchaseInvoice` with the header from the record (supplier, `partner_reference`, `supplier_invoice_date`, currency, rate as stated) and the resolved lines (`goods` lines with their order line, quantity, unit price and the supplier's stated tax copied from the record). Unresolved lines are not drafted. Step code `purchase_invoice.draft` (ADR-0051 rule 21).

12.27 Checks on D4's simulated plan: lines and order lines come from D2, L1 and D3; header totals equal the record's when nothing was left out, else the note gives the difference; the three-way match results (`match_quantity_exceeded`, `match_price_difference`, `invoice_before_receipt`) go into the note (ADR-0051 rule 21).

12.28 D5 `propose_mappings`: one change proposal with a `CreatePartnerItem` item for each line L1 resolved, with the record as evidence. Step code `purchase_invoice.mapping` (ADR-0051 rule 21).

12.29 Human gates: an accountant completes, submits and posts the invoice. The three-way match condition `is_match_exceeded` requires approval. A tainted draft needs a person to post. The mapping proposal is a draft; a person submits it, and a person other than the workflow owner approves it, after which the next invoice maps deterministically (ADR-0051 rule 22; ADR-0043 rule 9).

12.30 Failures: no supplier, or more than one: no run. An unreadable record: `not_applicable`. Unresolved lines are normal (ADR-0051 rule 22).

12.31 Version 1.1.0 of the agent, per ADR-0057 rule 26: PDF-only supplier invoices get deterministic reading and full human verification. A `purchasing` consumer of `DocumentExtractionVerified` raises `supplier_invoice_extracted` for a verified supplier-invoice extraction without an e-invoice record. The agent then runs D1 (key check) and D2 to D5, scoped to the supplier whose tax ID equals the verified `seller_tax_id`, when exactly one active supplier has it. It accepts `document_extraction` as a subject. ADR-0078 rule 1 keeps both entry paths.

## 13. Deferred to Phase 2

13.1 Everything in this list is registered `off` or not built in Phase 1. Its design, DDL drafts, settings rows and seams stay (ADR-0078 rule 2). Do not build it. Do not describe it here.

13.2 Agent types moved to Phase 2, each registered with mode `off`, no workflow code, and refused by `StartAgentRun` with `agent_mode_off` (ADR-0078 rule 2; ADR-0050 rule 15):
- `customer_onboarding` and `quotation` (ADR-0051).
- `planning` (ADR-0051).
- `data_migration` (ADR-0051; ADR-0044; ADR-0030).
- `document_reader`, the vision step of the intake ladder (ADR-0057).
- `product_engineering` (ADR-0062).
- `production`, `production_capture` and `production_variance` (ADR-0064).
- `analysis` (ADR-0060).
- `auto_post_advisor` (ADR-0065).

13.3 Machinery deferred with them (ADR-0078 rules 5, 6, 8; the last item is older):
- Modes `shadow` and `active`, live shadow comparison against what people did (ADR-0050 rule 14), `GetAgentShadowEvaluation` and its evidence tables.
- The general auto-post gateway (ADR-0065), including auto-post of tainted drafts and the `auto_post_document_types` declaration.
- AI drafting of tuned artifacts (ADR-0059): parameter sets, decision tables and rule sets are drafted by people in Phase 1.
- AI-drafted automation rules (ADR-0058, ADR-0059).
- The analysis agent and its explanation layer (ADR-0060).
- The vision reader of document intake and the seat class `extraction_vision_personal` (ADR-0057).
- Older deferrals, in their own ADRs: the `local` provider adapter (ADR-0050 rule 5) and embeddings (ADR-0050 rule 9).

13.4 Phase 1 mobile capture is a photo, attached to a draft or sent through the deterministic intake ladder, and text to the assistant. The capture agent `production_capture` is in Phase 2 (ADR-0077 rule 18; ADR-0078 rule 2).

## 14. Error codes and work item kinds used in Phase 1

### Error codes

14.1 From ADR-0050 rule 55: `agent_mode_off`, `agent_budget_exceeded`, `agent_scope_unresolved`, `approver_is_submitter`, `promotion_evidence_stale`, `llm_provider_unavailable`, `llm_output_invalid`, `llm_routing_refused`, `tool_not_allowed`, `agent_kind_not_declared`, `tainted_read_out_of_scope`, `untrusted_read_not_allowed`, `tainted_run_not_allowed`, `list_export_too_large` (not used by agents; people export lists).

14.2 Check result: `outbound_content_flagged` (ADR-0050 rule 55).

14.3 Other codes met by agent runs and their consumers:
- `work_item_claimed` (ADR-0050 rule 15).
- `proposal_required`, `target_changed` (ADR-0029 rules 2, 4).
- `origin_run_submit_not_allowed` (ADR-0029 rule 6 note).
- `segregation_of_duties` (ADR-0029 rules 3, 8).
- `outbound_content_out_of_scope` (ADR-0029 rule 14).
- `workflow_owner_not_permitted` (ADR-0050 rule 14 note).
- `shadow_evidence_insufficient` (ADR-0051 rule 30; used by the bank auto-post rule, 12.14).
- `setting_out_of_bounds`, `tainted_projection_cap_reached` (ADR-0063 rule 29).
- `duplicate_external_document`, `duplicate_draft` (ADR-0051 rule 21; ADR-0050 rule 32).
- `e_invoice_record_unreadable`, `e_invoice_supplier_mismatch`, check result `e_invoice_signature_unverified` (ADR-0051 rule 30 note).
- `unit_text_unresolved` (ADR-0051 rule 21 note, ADR-0056).
- Three-way match results `match_quantity_exceeded`, `match_price_difference`, `invoice_before_receipt` (ADR-0051 rule 21).
- Replay harness result `replay_diverged` (ADR-0050 rule 38).

### Run outcomes

14.4 `drafted`, `no_action`, `not_applicable`, `routing_blocked`, `claim_lost`, `budget_exceeded`, `time_exceeded`, `output_invalid`, `provider_unavailable`, `resume_diverged`, `crashed`, `denials_repeated`, `canceled` (ADR-0050 rule 17).

### Work item kinds

14.5 Wake agents: `bank_line_unmatched` (ADR-0048 rule 9; ADR-0051 rule 17), `supplier_invoice_received` (module `tax`; ADR-0051 rule 20 and note), `supplier_invoice_extracted` (ADR-0057 rule 26).

14.6 Raised by `agents` (ADR-0050 rule 55): `agent_run_stopped`, `agent_budget_exhausted`, `agent_denials_repeated`, `agent_mode_degraded`. Also `agent_quality_below_threshold` (ADR-0051 rule 30).

14.7 Created by the runtime for a subject run: `agent_task` (ADR-0042 rule 11; ADR-0050 rule 15).

14.8 Invariants that apply (safety): INV-210 to INV-216 (ADR-0050 rule 55); INV-84 to INV-88 (ADR-0029 rule 16). Agent edge cases: EC-56 (ADR-0029), EC-81, EC-82 (ADR-0051 rule 30). EC-57, EC-79, EC-83 and EC-185 are Phase 2 cases; their checks are re-hosted on `purchase_invoice` and the assistant (ADR-0078 rule 9a).

14.9 Names used in Phase 1. Rows of `settings.csv`: `agents.installation_daily_max_cost`, `agents.company_daily_max_cost`, `agents.internal_reserve_share`, `agents.<agent_type>.drift_action`, `agents.<agent_type>.wake_up_mode.<kind>` (configurable kinds only), `agents.tainted_reference_reads`, `assist.max_cost_per_run`. Named by ADR-0050 rule 55 as company or installation values: `routing_switch`, `llm_provider`, `agent_run_step_retention_days` (default 400), `list_export_max_rows`. Named by ADR-0029 rule 3: `change_proposal_ttl_days` (company setting, interim default 14).

## 15. Conflicts found

Conflict: ADR-0063 rule 11 declares `supplier_invoice_received` configurable "in its next version"; ADR-0050 rule 12 note keeps every kind `always` for the ADR-0051 types. Treated as `always` unless the declaration says `configurable` (3.7).

Conflict: two notes of ADR-0054 rule 11 seed `start_agent` differently. Followed the later note: `it_administrator` holds no agent type, `owner` holds all, and the `assistant` leaf goes to every UI template except `it_administrator` and `auditor`. The rest of the seed is in `role-template-levels.csv`.
