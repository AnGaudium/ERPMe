Module: agents    Chunk: 8 of 8    Source ADRs: ADR-0077, ADR-0078
Build step(s): 0, 5, 5b, 7, 11    Generated from index: 30d5706    Compiled by: Claude Opus 5.5, 2026-11-21

# Compiled spec: `agents`, chunk 8

## Purpose

`agents` owns the agent workflows and the embedded assistant; the agent runtime, run records and budgets belong to
`agent_runs`. This chunk states the Phase 1 agent scope of ADR-0078 (the Phase 1 agent types and those moved to Phase 2,
agent type declarations, modes and promotion without a live agent shadow, quality in use, the one work model and the
manual path), the embedded agent and the `assistant` agent type with its subject table `assist_request` (ADR-0077 rule
13), and the assistant's request row, trust display, hard rules, assist panel, inline affordances and command bar (ADR-0077
rules 14 to 18). As the owner of the rest it also lists the invariants and edge cases whose catalog source is no rule
stated in chunks 1 to 7.

## Entities and tables

DDL: `docs/design/DS-30-ui.sql`.

| Table | Meaning | Key | Parent | Owner |
| --- | --- | --- | --- | --- |
| `assist_request` | The typed request of one person to the assistant and its answer; the subject of an `assistant` run, scope kind `subject` (R1271-R1279, R1460-R1465) | `id`; unique `(company_id, id)` and `(company_id, requested_by_user_id, id)` | `company`; `agent_run` by `agent_run_id`; a previous request of the same person by `previous_request_id` | `agents` |

`assist_request` per the DDL: `purpose` is `ask`, `act`, `resolve_command` or `resolve_filter`; `state` is `open`, `answered` or `failed`; `failure_reason` is one of `budget_exceeded`,
`time_exceeded`, `output_invalid`, `provider_unavailable`, `crashed`, `denials_repeated`, `canceled`, `out_of_scope`;
`answer` holds answer handles and record IDs (`ask`), the proposed invocation (`resolve_command`) or the structured filter
(`resolve_filter`); `agent_run_id` is null until `StartAgentRun` binds it; `previous_request_id` keys to a request of the
same company and requesting user.

Reads: `agent_run`, `agent_type_setting` (`mode`, `active_document_types`, `promoted_version`, `promoted_seat_models`),
`agent_type_version`, `agent_budget_usage`, `work_item`, `work_case`, `analysis_question`, `document_extraction`,
`e_invoice_record`, `audit_record`, `change_proposal`.

## Commands and queries

| Name | Actor and authorization | Input | Effect | Events | Error codes |
| --- | --- | --- | --- | --- | --- |
| `CreateAssistRequest` | `human_only`; area not stated | Purpose, request text, language, context, selection, filters, floorplan, optional previous request | Writes an `assist_request` (R1460, R1450) | Not stated | `validation_failed` (previous request of another person) |
| `UpdateAssistAnswer` | Registered `is_draft_only`; called only by workflow code | The run's answer | Writes the answer to the `assist_request` (R1463) | A live update tells the panel | Not stated |
| `GetAgentBudgetStatus` | People only; on no tool list; area not stated | The user's company | Returns the remaining daily agent budget of the company, amounts only (R1470) | None | Not stated |

Commands of other chunks with their rows there that these rules constrain: `UpdateAgentTypeSetting` (chunk 1; refuses
mode `shadow` in Phase 1 and every mode except `off` for an agent type without a Phase 1 workflow with `validation_failed`,
R1424, R1415), `CreateAgentPromotionEvidence` (chunk 1; from the stored evaluation result, R1433), the daily job
`RunAgentQualityCheck` (chunk 3; R1438, R1439). Commands of other modules or chunks: `StartAgentRun` (refuses a mode `off` agent type with
`agent_mode_off`, ADR-0050.R15), `GetAgentDraftAcceptance` and `ConfirmAutoPost` (ADR-0065.R11), `RunAnalysisEvaluation`
(ADR-0060), `RequestDocumentExtraction` (ADR-0057), `ClearTaint` (ADR-0029), `GetAuditRecord`. `GetAgentShadowEvaluation`
is not used for promotion in Phase 1 (R1434).

Tooling, not commands: `nativeflows-dev check` validates every agent type declaration (R1423); `generate` writes the
declarations into the agent type catalog and the evaluation manifest (R1420, R1428).

Error codes bound to no command of this table: `work_item_claim_lost` (a run's command after a person's takeover, R1448);
`agent_mode_not_declared` stays ADR-0065.R11's code and is not reused (R1424).

## Rules

### Phase 1 agent scope

R1401. The agent layer of Phase 1 keeps its agentic capabilities with less machinery. The core stays deterministic, and agents take part in business work through the same work items as people. The safety model is unchanged: the hard floors, the permission intersection, taint, the tainted read scope, drafts only, and the gateway's conditions for tainted drafts. Changing them is the author's decision (ADR-0005 item 7).
Source: ADR-0078.D0

R1402. An agent type is a typed Python declaration, like a command (ADR-0073). The runtime of ADR-0050 is written once; an agent type adds only its declaration, its workflow steps and its evaluation set.
Source: ADR-0078.D0

R1403. Phase 1 has two budget tiers: the company's daily cost cap, and the per-run ceilings that each agent type version declares. The per-agent-type budget settings are removed (ADR-0078.R7).
Source: ADR-0078.D0

R1404. The auto-post gateway (ADR-0065) and the artifact lifecycle (ADR-0059) are code and data, not agents. Agents only feed them drafts and proposals that a checker, a backtest or a person decides.
Source: ADR-0078.D0

R1405. The agent types of Phase 1 run on one runtime. Each starts after the point stated, for the reason stated:
- `assistant`: after step 5 (work package 8); its evaluation set is a step 5 gate item (ADR-0077.R23). It is the one interactive entry: ask, act and resolve (ADR-0077 rules 13–18). It routes questions that need figures to `analysis`, and drafts what the deferred agents would help with.
- `analysis`: after the step 5 gate. It turns a question into a deterministic analysis plan whose figures are server cells (ADR-0060); it is started by the assistant or from the analysis view.
- `bank_matching`: after the step 6 gate. Unmatched bank lines are daily work; the deterministic cascade does most of it, and the agent reads only the free-text remainder (ADR-0051).
- `purchase_invoice`: after the step 7 gate. Supplier invoices are the largest manual entry load; the agent drafts from a stored e-invoice record or a verified extraction (ADR-0051; ADR-0057.R26).
- `document_reader`: after the step 7 gate. It is the tool-less vision step of the intake ladder of ADR-0057, run only when the deterministic readers fail and the vision seat is configured (ADR-0057 rules 4 and 11).
- `planning`: after the step 5b gate; step 5b is the manual path of planning with multi-level MRP (ADR-0024.R26, ADR-0032.R7). Planners work by exception. Code computes the candidate actions and their effect on the projection; the one LLM step chooses among them and explains, with every number checked against its input; the output is a change proposal a person approves (ADR-0051 rules 23–25).
Source: ADR-0078.D0, ADR-0078.R1, ADR-0078.R1.N1

R1406. A Phase 1 agent type is one listed in R1405. Adding one is a scope change, for the author (ADR-0005 item 2).
Source: ADR-0078.R1

R1407. `purchase_invoice` keeps both entry paths of ADR-0051 and ADR-0057.R26: a stored e-invoice record, and (version 1.1.0) a document extraction that a person verified after the deterministic ladder. Its Phase 1 declaration is the "next version" of ADR-0063.R11: it declares the wake-up kind `supplier_invoice_received` `configurable`, so `agents.purchase_invoice.wake_up_mode.supplier_invoice_received` applies with default `always`.
Source: ADR-0078.R1

R1408. The `assistant` declaration has these interim ceilings per run: 8 LLM calls, 40 tool calls, 40,000 input tokens, 4,000 output tokens, USD 0.50, 120 seconds and 2,000 rows read. `assist.max_cost_per_run` (default USD 0.20, bounds 0.01 to 0.50) may only lower the cost ceiling. Its evaluation set passes at 90% of all tasks and 100% of the refusal and taint tasks.
Source: ADR-0078.R1

R1409. `planning` declares `may_read_untrusted: false`, reads internal data only and is never tainted (ADR-0050.R28). It writes nothing but a draft change proposal, and floor 7 requires approval of every proposal (ADR-0043.R9). Its ceilings are those of ADR-0051.R9, and its evaluation set passes its golden set at 90% (ADR-0051.R7); the size of the set is fixed with the declaration. The planning agent is done before the platform counts as complete (ADR-0032.R7).
Source: ADR-0078.R1

R1410. One at a time. Each agent type is built behind its manual path (spec 11, B6) and counts as done only when its evaluation set passes. Agent types that start after the same gate are built in the order of R1405. No gate depends on an agent's accuracy in use: the gate items that name an agent are evaluation sets on recorded and synthetic cases (the assistant's at step 5, ADR-0077.R23). No agent in mode `active` is a go-live condition. The golden pair of the `planning` agent (R1459) is an item of the agent's own completion, not of the step 5b gate.
Source: ADR-0078.R1, ADR-0078.R1.N1

R1411. These agent types move to Phase 2, each keeping its design, DDL draft and catalog rows as seams: `auto_post_advisor` (ADR-0065.R18); `customer_onboarding` and `quotation` (ADR-0051); `data_migration` (ADR-0051); `product_engineering` (ADR-0062); `production`, `production_capture` and `production_variance` (ADR-0064).
Source: ADR-0078.R2

R1412. `auto_post_advisor` reads months of gateway outcomes that do not exist before go-live. Until then a person proposes gateway settings and decision tables, and the assistant in `act` mode may draft them on request (R1441).
Source: ADR-0078.R2

R1413. At step 11, migration uses the staged import of ADR-0030 and ADR-0044 with stored mappings and deterministic fuzzy matching, which do the bulk of the mapping. The assistant's help is bounded: an `act` run is tainted and reads its request, the batch row as context subject and at most 100 selected import rows, so it may draft mappings for the selected rows only and proposes no merges against existing records. Every batch is still simulated and checked before it posts.
Source: ADR-0078.R2

R1414. The production core and its manual capture stay in Phase 1. `production` reads no outside content, so it is the first to bring forward when a Phase 2 agent is chosen.
Source: ADR-0078.R2

R1415. Each agent type moved to Phase 2 is registered with mode `off` and no workflow code in Phase 1. Its leaf, settings and evaluation rows exist, and the work item kinds it would wake on are raised and handled by people (R1455). `check` refuses any other mode for it in seed and configuration, and `UpdateAgentTypeSetting` refuses it at run time (R1424), so `StartAgentRun` refuses it with the existing `agent_mode_off` (ADR-0050.R15).
Source: ADR-0078.R2

R1416. `EC-57`, `EC-79` and `EC-83` start from the deferred `quotation` agent, `EC-80` and `EC-87` from the deferred `customer_onboarding` agent, and `EC-227` (`advisor_drafts_only`) from the deferred `auto_post_advisor`. These cases stay in the catalog as Phase 2 cases with their trigger and cannot run in Phase 1; `design/DS-17-synthetic-dataset.md` excludes them from the Phase 1 coverage counts (the catalog has no phase column).
Source: ADR-0078.R9a

R1417. The checks of `EC-57`, `EC-79` and `EC-83` (injected instructions in outside content, laundering through a draft, crash and replay) are re-hosted in Phase 1 on `purchase_invoice` (injected text in a supplier e-invoice) and on the assistant (pasted untrusted text in an `act` request): in the assistant's evaluation set and in the DS-16 harness, with new edge-case rows written with the declarations at step 5.
Source: ADR-0078.R9a

R1418. `EC-185` (`wake_up_by_rule`) is a configurable wake-up check, not a safety check. It is re-hosted on `supplier_invoice_received` of `purchase_invoice`, its row in `catalogs/edge-cases.csv` is rewritten for it, and it is not a Phase 2 case.
Source: ADR-0078.R9a

R1419. The current agent design is consolidated in `design/agents-current.md`: one text that states what applies in Phase 1, restated from ADR-0029, ADR-0050, ADR-0051, ADR-0057, ADR-0059, ADR-0060, ADR-0063, ADR-0065 and their notes, ADR-0077 and ADR-0078. The ADRs keep the history and win where the text disagrees. The coding agents read the consolidated text instead of these ADRs (ADR-0005, "small, self-contained documents").
Source: ADR-0078.R10

### Agent type declarations

R1420. An agent type is declared in `backend/src/nativeflows/agents/agent_types/<agent_type>.py` as one `AgentTypeDeclaration` named `DECLARATION`, written by `generate` into the agent type catalog. The folder `declarations/` holds the module's command and query declarations (ADR-0073.R1).
Source: ADR-0078.R3

R1421. A declaration holds:
- `agent_type` and `version` (semver);
- the subject tables it may start from, and the work item kinds that wake it;
- the tool list: registered queries, plus commands registered `is_draft_only`;
- the output schema of each LLM step (ADR-0050 rules 35, 36);
- the per-run ceilings: LLM calls, tool calls, input and output tokens, cost, seconds and rows read;
- the seat and data class of each LLM step (spec 17);
- the path of its evaluation set and its pass threshold;
- every other element that ADR-0050.R12 and its notes declare: `may_read_untrusted`, `scope_kind` and its scope resolver, `field_classes`, the prompt templates, `auto_post_document_types` (ADR-0065.R11), the wake-up kinds declared `configurable` (ADR-0063.R11) and, for `analysis`, the catalog hash.
Source: ADR-0078.R3

R1422. The declaration is the only place these values live. The prose of ADR-0051 per agent type becomes the declaration's docstring and its workflow steps.
Source: ADR-0078.R3

R1423. `nativeflows-dev check` validates every declaration:
- the tool list names only registered queries and `is_draft_only` commands, and none of the never-list of ADR-0050.R30;
- every per-run ceiling is set;
- every LLM step has an output schema with no confidence, score, probability or certainty field (ADR-0050.R35);
- the evaluation set exists, and a version without a passing result cannot be promoted (R1427);
- no work item kind is declared by two agent types (R1454).
A failure names the declaration's file and line, the rule and a one-line fix (ADR-0022.R13).
Source: ADR-0078.R4

### Modes, promotion and quality in use

R1424. The Phase 1 modes in `agent_type_setting.mode` are `off`, `assisted`, and `active` only as the gateway uses it. The DDL keeps `shadow` for Phase 2. `check` refuses `shadow` in Phase 1 seed and configuration. At run time `UpdateAgentTypeSetting` refuses mode `shadow` in Phase 1, and refuses every mode except `off` for an agent type that has no Phase 1 workflow (R1415), with `validation_failed`; `agent_mode_not_declared` is ADR-0065.R11's code for `active` without declared document types and is not reused.
Source: ADR-0078.R5

R1425. `active` is set for an agent type and the document types named in `active_document_types` only by an approved change proposal, with the evidence of R1434 (ADR-0065.R11). While the document type's gateway mode is not `live`, the agent type counts as `assisted` for the gateway. The assistant and `planning` are never `active`: their outputs are drafts and proposals that a person confirms or approves.
Source: ADR-0078.R5

R1426. The setting `agents.<agent_type>.drift_action` keeps its values `signal`, `pause_new_runs` and `demote_to_shadow`. Until Phase 2, `demote_to_shadow` acts as `pause_new_runs`.
Source: ADR-0078.R5

R1427. Promotion to `assisted` needs evidence: the version passes its evaluation set with the real provider, per pair of seat and model, and the replay of recorded responses in CI (ADR-0050 rules 39, 40; spec 17). The replay proves the code path; only the real-provider run proves a model, so a new seat model always needs it. The evidence is the stored evaluation result, named in `agent_type_setting.promoted_version` and `promoted_seat_models`.
Source: ADR-0078.R6

R1428. `generate` writes the passing results of a release into an evaluation manifest shipped with it: one row per agent type, behavior hash, seat and model. The runtime reads the manifest; nothing else proves a pair.
Source: ADR-0078.R6

R1429. Carry-over. A company already `assisted` stays `assisted` across a change of the behavior hash (version, constants or seat model; ADR-0050.R14) when the manifest holds a passing result for the new behavior. The runtime then updates `promoted_version` and `promoted_seat_models` as `system`, with an audit record, so later evidence counts under the behavior that actually runs. The model fallback of ADR-0050.R6 uses only models with a passing result in the manifest.
Source: ADR-0078.R6

R1430. No Phase 1 agent type declares a parameter set (ADR-0059.R7), so the behavior hash has no per-company part; constants are part of the version.
Source: ADR-0078.R6

R1431. No result, no run. A behavior without a passing result runs nothing: where ADR-0050.R14 drops the effective mode to `shadow`, Phase 1 drops it to `off`, with the same reason and the same `agent_mode_degraded` work item. This applies to all Phase 1 agent types, the assistant's `ask` and resolve purposes included.
Source: ADR-0078.R6

R1432. `active` does not carry over. On any change of the behavior hash an `active` agent type counts as `assisted` for the gateway until it is promoted again under ADR-0065.R11 on drafts of the new behavior. Draft acceptance counts only drafts written under the current behavior hash.
Source: ADR-0078.R6

R1433. There is no live shadow period. `CreateAgentPromotionEvidence` computes the evidence from the stored evaluation result instead of `GetAgentShadowEvaluation` (ADR-0050.R14). Live shadow comparison of agents against what people did returns in Phase 2, together with its evidence tables.
Source: ADR-0078.R6

R1434. Promotion to `active` for a document type uses ADR-0065.R11 unchanged: `GetAgentDraftAcceptance` over the agent's `assisted` drafts of that document type (at least two calendar months, at least ceil(3 / `auto_post.max_error_rate`) drafts, at least 1 − rate posted unchanged, none to another partner), by an approved proposal another person approves. The gateway's own mode `shadow` for the document type runs its deterministic checker without posting; no live agent shadow is needed.
Source: ADR-0078.R6

R1435. `analysis` keeps its stated exception (ADR-0050.R14 note): the daily `RunAnalysisEvaluation` on the company's verified examples is its evaluation in use. A version with no passing CI evaluation is `off` like any other; a failing daily evaluation raises `agent_quality_below_threshold` (R1439).
Source: ADR-0078.R6

R1436. `document_reader` is promoted by the golden-set thresholds of ADR-0057.R34. Its live shadow-agreement criterion is replaced by the replay of the company golden set of at least 50 real documents, which that rule already requires before `assisted`. It is the one exception to the carry-over: after a change of behavior it returns to `assisted` in a company only when the replay of that company's golden set has passed again (ADR-0057.R13).
Source: ADR-0078.R6

R1437. `planning` is promoted by its evaluation set; the comparator of ADR-0051.R25 measures quality in use on stored output (R1438), and live shadow runs return in Phase 2.
Source: ADR-0078.R6

R1438. `RunAgentQualityCheck` runs daily per company and `assisted` agent type over the last 30 days (ADR-0051.R5). The Phase 1 measure applies each workflow's existing comparator to what the agent produced in `assisted` mode against what the person finally did on the same work item: `bank_matching` by ADR-0051.R19, `purchase_invoice` by ADR-0051.R22, `planning` by ADR-0051.R25, `document_reader` by the field agreement of ADR-0057.R34, and `analysis` by its daily evaluation (R1435). The comparator needs no shadow run: the agent's output and the person's result are both stored. The assistant's `act` drafts have no comparator: the share of drafts canceled is shown on the operations dashboard and raises nothing.
Source: ADR-0078.R15

R1439. A measure more than 10 points below the agent type's evaluation threshold raises `agent_quality_below_threshold`, and `agents.<agent_type>.drift_action` applies. While that item is open, an `active` agent type counts as `assisted` for the gateway (ADR-0065.R11).
Source: ADR-0078.R15

### Kept without new machinery, and the floors

R1440. The auto-post gateway (ADR-0065) stays as designed: a deterministic checker per document type, settings per document type with modes `off`, `shadow` and `live`, the conditions for tainted drafts, `ConfirmAutoPost` and the confirmation cadence. It lands with `policy` at step 5; the purchase invoice checker follows at step 7, after the purchase invoice manual path. The deterministic bank cascade is one instance (ADR-0048.R9; ADR-0063.R8), and the author's lift of 2026-11-16 on `cash.auto_post.accept_llm_originated_rules` stays (ADR-0065.R12). The gateway is code and data, and the agent `active` mode it needs is evidenced by in-use draft acceptance (R1434), not by a live agent shadow.
Source: ADR-0078.R8

R1441. AI drafting of tuned artifacts (ADR-0059) stays: parameter sets, decision tables and rule sets may be drafted by agents. There is no tuning agent and, in Phase 1, no advisor. Drafts come from the stored-resolution proposals of `bank_matching` and `purchase_invoice` (bank matching rules, item mappings; ADR-0051.R2), from the parameter and lead-time proposals of `planning` (ADR-0024.R23), and from the assistant in `act` mode on request. Every draft enters the deterministic lifecycle of ADR-0059 (backtest before anything runs, then the stages its kind declares, rollback by pointer) and is approved by a person. AI does not write code for the running system (ADR-0059).
Source: ADR-0078.R8

R1442. The analysis agent (ADR-0060) stays as designed: the plan is deterministic, figures are server cells, and the narrative is rendered by code from fixed templates. It is one declaration on the shared runtime, and the assistant routes questions that need figures to it instead of answering them itself, so there is one analysis path.
Source: ADR-0078.R8

R1443. The vision reader (ADR-0057) is the minimal `document_reader` declaration: no tools, one LLM step, the one vision seat `extraction_vision_personal` (ADR-0057.R21; disabled until a provider is configured and a data processing permission covers it), per-run ceilings, and its evaluation set. A vision value is aligned to OCR words by code and stays untrusted until a person verifies it (ADR-0057 rules 12, 17).
Source: ADR-0078.R8

R1444. No floor is weakened:
- agents never submit, post, issue, send or approve: those commands are on the never-list (ADR-0050.R30), an origin run cannot submit (ADR-0029.R6 note), and the floors force `human_post` (ADR-0043.R9);
- effective rights are the intersection of the agent type's and the person's (ADR-0054.R16);
- taint, `ClearTaint` and the tainted read scope are unchanged (ADR-0029; ADR-0050 rules 25–27).
Source: ADR-0078.R9

### One work model

R1445. The work model rules (R1446 to R1459) state in one place what ADR-0042, ADR-0050, ADR-0058 and ADR-0066 decide, and close what they left unsaid. They add no table. A work item is the unit of business work for people, deterministic code and agents; an agent run is one attempt at a work item, not the work itself.
Source: ADR-0078.D1, ADR-0078.D0

R1446. Four concepts are kept apart:
- Business work is a `work_item` (ADR-0042): kind, subject, evidence, owner, due date. Its states are `open`, `claimed`, `done` and `canceled`; the owner is always a person, a role or an approval stage.
- The progress of a process is the document's lifecycle state, its open work items and, where a company turns it on, the `work_case` that groups them (ADR-0066). The documents and work items themselves are the state. There is no workflow instance and no orchestration engine in Phase 1 (ADR-0058; D2): waiting is a work item, asynchrony is the outbox.
- Work given to an agent is the work item while an agent run holds its claim (or an `agent_task` item of the run's own): `claimed_by_kind` `agent_run`; the claim is a lease that expires.
- One attempt is an `agent_run` with its steps (ADR-0050), in state `queued`, `running`, `completed`, `stopped` or `canceled`.
Source: ADR-0078.R11

R1447. A run is not the work. A run that ends leaves the work item unclaimed with its owner, with links to the drafts and a note. Only a person, the owning module or a registered command resolves a work item; agents never do (`is_agent_resolvable` is false for every Phase 1 kind, ADR-0042.R16). Several runs may work on one item, one at a time: a retry after a crash continues the same run, and a new run needs a new raise or a person.
Source: ADR-0078.R11

R1448. A person can always take over. A person's claim takes the item from a run, whose later commands fail with `work_item_claim_lost` (ADR-0042; `INV-205`). The drafts and the note stay.
Source: ADR-0078.R11

R1449. Nothing waits inside a model. An agent run never waits for a person. The human step finishes as its own command, which raises the next work item or event, and that starts a new run from stored rows: the draft, the work item's links and notes, verified extraction fields, stored resolutions. No state is rebuilt from an earlier model response or a chat (spec 03 rule 9).
Source: ADR-0078.R11

R1450. A follow-up to the assistant is a new request that names a previous request of the same person (`previous_request_id`); `CreateAssistRequest` refuses another person's request with `validation_failed`. An untainted run (`ask` and the resolve purposes) may read that previous request's stored text and answer. An `act` run starts tainted and reads only its own request, its context subject and the selected rows (ADR-0050.R27 note), so an `act` follow-up restates what it needs; adding the previous request to the tainted scope would widen that scope and is the author's.
Source: ADR-0078.R11, ADR-0077.R14.N1

R1451. Handoff keeps the controls. The owner stays the owner; the run acts for the workflow owner or the person who started it, within the intersection of rights; what a tainted run wrote stays tainted until a person other than that human clears it (ADR-0029.R8).
Source: ADR-0078.R11

R1452. A running run finishes on its version. A change of the agent type's version or mode applies to runs that start afterwards. Rights are evaluated at every call, so a revoked right denies the next call, and the third denial stops the run (ADR-0050 rules 31, 33).
Source: ADR-0078.R11

R1453. A domain module names no agent type. It raises a work item of a kind and registers the commands that act on the subject. Which participant does the work is declared outside it: the kind's owner rule names the people; an agent type's declaration lists the kinds that wake it (R1421); a deterministic consumer may resolve a kind whose resolution is `system`.
Source: ADR-0078.R12

R1454. One agent type per kind: `check` refuses a kind declared by two agent types (R1423), so a wake-up is never ambiguous.
Source: ADR-0078.R12

R1455. Adding an agent later changes no module. The kinds that the deferred agent types wake on are raised in Phase 1 and handled by people. Bringing an agent type forward adds its declaration, its steps and its evaluation set; the module, the work item kind and the manual path stay as they are. The same holds for replacing an agent step by deterministic code.
Source: ADR-0078.R12

R1456. There is no capability registry: a separate catalog of capabilities that workflows request would repeat what the work item kind and the registered commands already state. It is reconsidered when two agent types need to serve one kind ("Revisit when" of ADR-0078).
Source: ADR-0078.R12

R1457. Every workflow has its manual path, and it is tested. With `llm_provider` unset, every agent mode is `off`, every work item stays with people, and every operation works (Principle 12; ADR-0050.R5).
Source: ADR-0078.R13

R1458. The purchase invoice flow is a golden scenario in two variants over the same input files. The variant with the LLM off, from the input files to a posted invoice, is a gate item of step 7. The variant with agents on recorded responses, ending in the same posted invoice, is an item of the completion of `purchase_invoice` and `document_reader`, which start only after that gate. The flow has every kind of step: deterministic intake and extraction, the vision reader, a person's verification, the agent's draft, the three-way match, approval where the match is exceeded, the gateway in `shadow`, and a person's posting.
Source: ADR-0078.R13, ADR-0078.R13.N1

R1459. The `planning` agent has the same pair for one planning exception, with the agent on recorded responses and with the LLM off. The pair is an item of the planning agent's own completion after the step 5b gate, not of that gate.
Source: ADR-0078.R13, ADR-0078.R13.N1

### Embedded agent and the `assistant` agent type

R1269. The UI is generated from metadata: every screen is one of seven floorplans, the declarations of ADR-0073 carry a closed annotation vocabulary that `generate` emits as `x-nativeflows-*` keys, and screens that fit no floorplan are custom components registered by name, each with its own ADR. `nativeflows-dev check` enforces the vocabulary (ADR-0073.R2); Playwright tests are generated per floorplan, with visual regression.
Source: ADR-0077.D0

R1270. The embedded agent is an agent like any other: it calls the same registered commands and queries as external agents, through the same tool lists, and no endpoint exists only for the UI; it works in a side panel scoped to what the user is looking at, never as a separate chat application; it reads, explains and drafts, and only a person submits, posts, approves or sends. The assistant is never promoted to `active`, so its drafts never pass the ADR-0065 gateway.
Source: ADR-0077.D0

R1271. One agent type, `assistant`, serves the UI. It is declared like the agent types of ADR-0051. Its effective rights are the intersection of its declared permissions and the user's, rechecked on every call (ADR-0054.R16; ADR-0050.R31).
Source: ADR-0077.R13

R1272. The assistant's tool list holds read queries that ADR-0050.R30 does not exclude, commands registered `is_draft_only`, and `UpdateAssistAnswer` for workflow code only (ADR-0077.R14). The subset depends on the purpose: `ask`, `resolve_command` and `resolve_filter` runs get read queries only; only `act` runs get the `is_draft_only` commands.
Source: ADR-0077.R13

R1273. A run is started by `StartAgentRun` with the user's `start_agent:assistant`, held at `edit` on the leaf `agent_assistant`, so it acts for that person in that person's own context. The seed gives the leaf to every role template with UI access except `it_administrator`, in line with the decision on `start_agent` of 2026-11-19 (ADR-0054.R11 note), and except `auditor`, which ADR-0054.R11 keeps at `read` everywhere and nothing else, while starting a run is a command; a company may withdraw the leaf from any role.
Source: ADR-0077.R13

R1274. Phase 1 has no per-agent-type budget settings, so the assistant's budgets are the company's daily cap and the ceilings of its declaration (ADR-0050.R22; ADR-0078.R1, ADR-0078.R7). The company setting `assist.max_cost_per_run` (default USD 0.20, bounds 0.01 to 0.50, lower is tighter) caps one run and may only lower the cost ceiling.
Source: ADR-0077.R13, ADR-0077.R13.N1

R1275. The run's scope is scope kind `subject`: its `assist_request` plus the context subject and the selected rows, each checked against the user's record scope. ADR-0050.R27 carries a note that defines this scope for a tainted run, so an `act` run, which always starts tainted, can read these records.
Source: ADR-0077.R13

R1276. A run of `purpose` `act` always starts tainted, because the user may have pasted untrusted content into the text: it starts with `taint_source_kind` `outside_subject` and source table `assist_request`. The registry marks `assist_request` as outside content only when `purpose` is `act` (note at ADR-0050.R15). A run of `ask`, `resolve_command` or `resolve_filter` starts untainted, and taint propagates as usual when it reads untrusted data (ADR-0050.R25). A tainted run may run only `is_draft_only` commands and reads only the tainted read scope (ADR-0050.R26, ADR-0050.R27).
Source: ADR-0077.R13

R1277. The assistant runs only in mode `assisted`; its default is `off`. It is never promoted to `active` (ADR-0065), so its drafts always need a person to confirm them. The evaluation set is its promotion evidence (a step 5 gate item). The purposes `ask`, `resolve_command` and `resolve_filter` answer only the asking person and write nothing; they still require mode `assisted`.
Source: ADR-0077.R13

R1278. The assistant has three modes of use, named once here: ask, act and resolve. Resolve has the purposes `resolve_command` and `resolve_filter`, so `assist_request.purpose` takes `ask`, `act`, `resolve_command`, `resolve_filter`. The evaluation set counts the modes of use. The assist panel of ADR-0077.R17 has panel modes of its own (ask, act, proactive), and the resolve purposes serve the command bar and natural-language filters (ADR-0077.R18).
Source: ADR-0077.R13

R1279. Spec 17 requires every pair of seat and model to pass an evaluation. The set for the seats of ADR-0077.R14 has about 50 tasks across the modes of use: read answers with correct citations, drafts with correct field diffs, refusals outside its scope, and taint handling, pasted untrusted text included. It is built with the assistant and is a step 5 gate item.
Source: ADR-0077.R13

### The embedded assistant

R1460. Typed text reaches the agent through one row, as `analysis_question` does for the analysis agent (ADR-0060). `CreateAssistRequest` is `human_only` and writes an `assist_request` with:
- `purpose`: `ask`, `act`, `resolve_command` or `resolve_filter`;
- `request_text`: up to 2,000 characters;
- `language`: the language tag of the request;
- the context: `context_subject_table` and `context_subject_id`, up to 100 `selected_ids` with `selected_table`, the table of the selected rows (required when `selected_ids` is not empty, null otherwise), `active_filters` as JSON, and the `floorplan` code;
- `requested_by_user_id`: the requesting user.
Source: ADR-0077.R14

R1461. `request_text` is labeled personal (spec 17) and follows the routing switch as `analysis_question.question_text` does (ADR-0060.R21). It is blanked, which sets `erased_at`, when the requesting user's account is erased and by the retention job after `analysis.question_retention_days` (named `analysis_question_retention_days` in ADR-0077.R14), the same value as for analysis questions (ADR-0060.R21; no new setting).
Source: ADR-0077.R14

R1462. The LLM steps of the assistant use the spec 17 seat "Data Q&A" for `ask` and the resolve purposes, and "Drafting" for `act`.
Source: ADR-0077.R14

R1463. The UI then sends `StartAgentRun` with the row as subject. The run writes its answer to the row through `UpdateAssistAnswer`, registered `is_draft_only` and called only by workflow code, as `UpdateAnalysisAnswer` is (ADR-0050.R26 note). Its drafts link to its `agent_task` work item (ADR-0042), and a live update tells the panel (ADR-0040.R13).
Source: ADR-0077.R14

R1464. Assistant runs are asynchronous, and there is no multi-turn dialogue. A follow-up is a new request that names a previous request of the same person, by a key in DS-30; only an untainted run reads it (R1450).
Source: ADR-0077.R14, ADR-0077.R14.N1

R1465. The DDL of `assist_request` is in `DS-30-ui.sql` (owner `agents`). The leaf `agent_assistant`, its seed and `assist.max_cost_per_run` are in the catalogs.
Source: ADR-0077.R14

R1466. Every value an agent or document intake wrote shows where it came from, read from stored data, not from annotations:
- The source shown: the actor kind and the agent run of the version that wrote it (ADR-0029.R8), or the extraction method of ADR-0057.R8 (`parsed`, `ocr`, `vision_aligned`, and the others).
- Confidence: only the extraction engine's `confidence_raw` or `confidence_calibrated`. A language model states no confidence (ADR-0050.R35), so an agent-written value shows "AI drafted" without a number.
- Taint: the badge and the clearance record (ADR-0040.R17).
- Audit: a link to the audit record, for holders of `GetAuditRecord`.
Source: ADR-0077.R15

R1467. Provenance has one visual style: an icon, a text label and a colored edge. Color is never the only signal (ADR-0077.R7).
Source: ADR-0077.R15

R1468. Hard rules of the embedded agent:
- No screen automation. The agent never clicks, types into or reads the rendered UI. It works only through registered commands and queries on its tool list.
- Nothing is auto-submitted. A draft or proposal written by the assistant opens in the plan panel with its field diff and taint badge, and a person confirms it. Only drafts of agent types promoted to `active` may reach the ADR-0065 gateway, and only for posting; the assistant is never one of them.
- No UI-only API. The panel, the command bar and the inline affordances call registered commands and queries through the generated client (ADR-0040.R1).
- No pop-ups. Agent outputs that need attention (exceptions, suggestions, drafted documents) arrive as work items in worklists (ADR-0066; ADR-0042), and through the notification inbox of ADR-0076.
- No invented values. A value the agent proposes for a price, tax, quantity, account or score follows ADR-0050.R36: it must equal a value in its input or the draft.
Source: ADR-0077.R16

R1469. Every floorplan has one assist panel, opened with `Ctrl+/`. It is scoped to the current context: the subject record, the selection, the active filters, or the Center's queue.
Source: ADR-0077.R17

R1470. The panel shows the remaining daily agent budget of the user's company through `GetAgentBudgetStatus`, not a per-agent-type budget (ADR-0078.R7). This people-only query returns amounts, not run bodies, and is on no tool list.
Source: ADR-0077.R17, ADR-0077.R17.N1

R1471. The panel has these modes:
- Ask and explain (`ask`, read only). The answer cites records as links. Every reference in it is an ID or handle that the run read through the query layer (ADR-0050.R36), rendered as a link to that record's object page.
- Propose and act (`act`, write as drafts). The run writes drafts or change proposals only (ADR-0029). They open in the plan panel with a field-level diff and a taint badge where it applies.
- Proactive. The panel never starts a run unasked. Proactive outputs come from the scheduled and triggered agents of ADR-0051 as work items.
Source: ADR-0077.R17

R1472. `x-nativeflows-assist` on a declaration lists suggested question keys (i18n keys) and the `is_draft_only` commands offered as agent actions. `ai-fillable` marks the fields an `act` run may fill.
Source: ADR-0077.R17

R1473. Fill from document. Dropping a PDF or photo on a form uploads an attachment and calls `RequestDocumentExtraction` with the form's purpose. The intake ladder of ADR-0057 produces the extraction, and its verification follows ADR-0057.R22. Once verified, the resulting draft opens in the form. Fields filled from the document show their provenance (R1466), and only `ai-fillable` fields are filled.
Source: ADR-0077.R18

R1474. Value help may list candidates that an agent or intake already stored on the draft, such as matching candidates. They are marked AI and never selected automatically. No language model is called per keystroke.
Source: ADR-0077.R18

R1475. A request with `purpose` `resolve_filter` returns a structured filter for the list's query, validated against its filter schema. The list shows it as editable chips before it runs, so the query itself stays deterministic.
Source: ADR-0077.R18

R1476. Phase 1 mobile capture is photo and text: a photo is attached to a draft or sent through document intake's deterministic ladder (ADR-0057), and text goes to the assistant. The capture agent of ADR-0064 moves to Phase 2 (R1411). Voice stays after Phase 1, as ADR-0064 says; the capture intake can accept an audio attachment later without a new path.
Source: ADR-0077.R18, ADR-0077.R18.N1, ADR-0078.R2

R1477. The command bar `Ctrl/Cmd+K` extends the palette of ADR-0040.R7:
- Typed names match commands, queries, lists and records as before.
- Other text becomes a request with `purpose` `resolve_command`. Its answer is a proposed invocation: a registered command or query type, with a payload validated against its schema.
- The bar shows the resolved command and its parameters. It opens the command's form prefilled, with provenance on the filled fields, and runs simulate before anything executes. It never executes by itself.
Source: ADR-0077.R18

R1478. The open questions of ADR-0077 were decided by the chief architect on the author's delegation of 2026-11-19 and are applied in its rules: the start leaf (rule 13), the taint of typed text (rule 13), `ai-fillable` as a hint (rule 9), the cost cap and DDL (rules 13, 14), voice (rule 18), the line grid without AG Grid (rules 5, 20), user-saved variants (rule 10a) and the evaluation set (rule 13).
Source: ADR-0077.R24

## Invariants

Statements are those of `invariants.csv`. This chunk, the owner of the rest, holds the rows whose catalog source is a rule
of another module. "Protects" names a rule of this chunk or the source ID of a rule stated elsewhere. Named by rules of
this chunk, with their rows in other chunks: `INV-210`, `INV-211`, `INV-212`, `INV-214` (chunk 2), `INV-216` (chunk 3),
`INV-413` (chunk 5).

| Invariant | Name | Check point | Statement | Protects |
| --- | --- | --- | --- | --- |
| `INV-88` | `taint_inherited` | day | Every document version written by a run tainted at its recorded_at, or whose origin run was, or whose previous or `derived_from_version_id` version was effectively tainted when it was written, has `is_tainted` true. Flagged: taint clearing (ADR-0029 rule 8). | ADR-0029.R8, R1451 |
| `INV-200` | `audit_rows_of_own_company` | day | An `audit_change` row and its `audit_record` have the same `company_id` (both null for an installation-scoped record), and a `change_proposal_execution_item` or `segregation_exception` names an `audit_record` of its own company. Query, empty when it holds: `SELECT c.id FROM audit_change c JOIN audit_record r ON r.id = c.audit_record_id WHERE r.company_id IS DISTINCT FROM c.company_id UNION ALL SELECT i.id FROM change_proposal_execution_item i JOIN audit_record r ON r.id = i.audit_record_id WHERE r.company_id IS DISTINCT FROM i.company_id UNION ALL SELECT e.id FROM segregation_exception e JOIN audit_record r ON r.id = e.audit_record_id WHERE r.company_id IS DISTINCT FROM e.company_id`. The keys stay single-column because `audit_record` has installation rows (`gen_overview.COMPANY_KEY_ALLOWLIST`). | ADR-0017.R19 note; ADR-0038 |
| `INV-205` | `no_agent_work_after_takeover` | day | No command of an agent run bound to a work item is audited after a person claimed that item. | ADR-0042.R11, R1448 |
| `INV-215` | `tainted_reads_in_scope` | day | Every row reference in `result_refs`, `context_refs` and `request_refs` of a step recorded after its run's `tainted_at`, wherever the row was first read, is inside that run's tainted read scope: its scope rows, its work item and evidence, drafts of its work item and agent type, or reference data. Flagged: reading of the literal read scope (ADR-0050 rule 27). | ADR-0050.R27, R1450 |

## Edge cases

Rows whose catalog source is a rule of another module. Named by rules of this chunk, with their rows in other chunks:
`EC-79`, `EC-80`, `EC-87` (chunk 3), `EC-83` (chunk 2), `EC-185` (chunk 6) and `EC-227` (chunk 7).

| Edge case | Name | Case | Outcome | Protects |
| --- | --- | --- | --- | --- |
| `EC-56` | `bank_account_change_by_email` | An e-mail asks to change a supplier's bank account; the agent run's direct call is rejected with `tool_not_allowed` (the command is on no tool list), a consumer command carrying the run as origin with `proposal_required`, and a change proposal approved by a second human succeeds (DS-04 dispatcher check order). | `must_reject:tool_not_allowed`, `must_reject:proposal_required`, `must_succeed` | ADR-0029 |
| `EC-57` | `injection_laundered_through_draft` | An injected instruction copied into a draft and edited by a human stays tainted; a run given that draft becomes tainted. Phase 2 case; its check is re-hosted (R1416, R1417). | `must_succeed` | ADR-0029 |

## Settings

| Key | Value type | Scopes | Core default | Rule |
| --- | --- | --- | --- | --- |
| `assist.max_cost_per_run` | amount (USD), bounds `0.01..0.5`, `lower_tighter`; leaf `agent`; storage `setting_value`, change effect `immediate` | `company` | 0.20 | R1274, R1408 |

Named by rules of this chunk, with their rows in chunk 6: `agents.<agent_type>.wake_up_mode.<kind>` (R1407) and
`agents.<agent_type>.drift_action` (R1426, R1439). Reads: `auto_post.max_error_rate` (R1434),
`cash.auto_post.accept_llm_originated_rules` (R1440), `agents.company_daily_max_cost` (ADR-0078.R7).
ADR-0077.R14 names the retention value `analysis_question_retention_days`, which is absent from `settings.csv`; R1461 uses
the catalog key `analysis.question_retention_days` (ADR-0060.R11), the retention key for analysis question text. `llm_provider` (R1457) is
named by ADR-0078.R13 and is absent from `settings.csv`.

## UI annotations

- Every floorplan carries one assist panel, opened with `Ctrl+/` (R1469); the floorplan codes an `assist_request` records
  are `list_report`, `object_page`, `edit_form`, `worklist`, `overview`, `plan_panel`, `approval_view` or `custom:<name>`
  (DDL).
- `x-nativeflows-assist` on a declaration: suggested question keys (i18n keys) and the `is_draft_only` commands offered as
  agent actions (R1472).
- `ai-fillable` on a field: an `act` run or a fill from document may fill it (R1472, R1473).
- Work item kinds: agent outputs that need attention arrive as work items in worklists, never as pop-ups (R1468); an
  assistant run's drafts link to its `agent_task` item (R1463).
- The command bar `Ctrl/Cmd+K` (R1477) and natural-language filters as editable chips (R1475).

## Conflicts

CONFLICT ADR-0078.R1.N1: the planning agent starts after the step 5b gate, which replaces the table's "the runbook does not place that work yet"; its golden pair belongs to the agent's own completion (R1405, R1410).
CONFLICT ADR-0078.R13: the proposed gate item became a decision through ADR-0078.R13.N1; the scenario is split into a step 7 gate item and a completion item, stated in R1458 and R1459.
CONFLICT ADR-0078.R13.N1: flagged note applied; the variant with the LLM off is a step 7 gate item, the variant with agents on recorded responses belongs to the completion of purchase_invoice and document_reader (R1458).
CONFLICT ADR-0077.R13: ADR-0077.R13.N1 (ADR-0078) replaces the per-agent-type budget settings with the company daily cap and the declaration ceilings, and narrows the upper bound of the per-run cost setting from 2 to 0.50; applied in R1274.
CONFLICT ADR-0077.R14: a follow-up may name only a previous request of the same person, and only an untainted run reads it, by ADR-0077.R14.N1 and ADR-0078.R11 (R1450, R1464).
CONFLICT ADR-0077.R17: the panel shows the company's remaining daily agent budget, not a budget for the assistant agent type, by ADR-0077.R17.N1 and ADR-0078.R7 (R1470).
CONFLICT ADR-0077.R18: Phase 1 photo capture goes to a draft attachment or the deterministic intake ladder and the capture agent moves to Phase 2, by ADR-0077.R18.N1 and ADR-0078.R2 (R1476).

## Proposed (not law)

None

## Trace

| Source | Where |
| --- | --- |
| ADR-0077.D0 | R1269, R1270 |
| ADR-0077.R13 | R1271-R1279 |
| ADR-0077.R13.N1 | R1274 |
| ADR-0077.R14 | R1460-R1465 |
| ADR-0077.R14.N1 | R1450, R1464 |
| ADR-0077.R15 | R1466, R1467 |
| ADR-0077.R16 | R1468 |
| ADR-0077.R17 | R1469-R1472 |
| ADR-0077.R17.N1 | R1470 |
| ADR-0077.R18 | R1473-R1477 |
| ADR-0077.R18.N1 | R1476 |
| ADR-0077.R24 | R1478 |
| ADR-0078.D0 | R1401-R1405, R1445 |
| ADR-0078.R1 | R1405-R1410 |
| ADR-0078.R1.N1 | R1405, R1410 |
| ADR-0078.R2 | R1411-R1415, R1476 |
| ADR-0078.R3 | R1420-R1422 |
| ADR-0078.R4 | R1423 |
| ADR-0078.R5 | R1424-R1426 |
| ADR-0078.R6 | R1427-R1437 |
| ADR-0078.R8 | R1440-R1443 |
| ADR-0078.R9 | R1444 |
| ADR-0078.R9a | R1416-R1418 |
| ADR-0078.R10 | R1419 |
| ADR-0078.D1 | R1445 |
| ADR-0078.R11 | R1446-R1452 |
| ADR-0078.R12 | R1453-R1456 |
| ADR-0078.R13 | R1457-R1459 |
| ADR-0078.R13.N1 | R1458, R1459 |
| ADR-0078.R15 | R1438, R1439 |
