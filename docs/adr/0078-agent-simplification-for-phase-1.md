# ADR-0078: Agent simplification for Phase 1

Status: proposed (2026-11-19) under ADR-0005 (builder Claude Opus 5.5); scope set by the author on 2026-11-19: level B of the agent simplification proposal, then revised the same day to keep the auto-post gateway, AI drafting of tuned artifacts, the analysis agent and the vision reader in Phase 1 ("agentic by design"), built the light way. Design items: DS-32, DS-33, DS-34. Related decisions: D2, D11, D15. Principles 3, 12, 13. ADR-0029, ADR-0030, ADR-0043, ADR-0044, ADR-0048, ADR-0050, ADR-0051, ADR-0054, ADR-0057, ADR-0058, ADR-0059, ADR-0060, ADR-0062, ADR-0063, ADR-0064, ADR-0065, ADR-0073, ADR-0077.

## Decision

The agent layer of Phase 1 keeps its agentic capabilities and loses most of its machinery. The safety rules stay as they are; what shrinks is what each agent needs to exist.

- **Six agent types in Phase 1, on one runtime:** `bank_matching`, `purchase_invoice`, `assistant` (ADR-0077), `analysis` (ADR-0060), `document_reader` (the vision step of ADR-0057) and `auto_post_advisor` (ADR-0065). The other eight designed agent types move to Phase 2, with their designs, DDL drafts and seams kept.
- **Agent types as declarations.** An agent type is a typed Python declaration, like a command (ADR-0073). The runtime of ADR-0050 is written once; an agent type adds only its declaration, its workflow steps and its evaluation set. `document_reader` and `auto_post_advisor` are minimal declarations: no tools for the first, read queries and draft proposals only for the second.
- **No live shadow for agents.** Promotion to `assisted` comes from the offline evaluation set and the replay of recorded responses. Mode `active` exists only where the auto-post gateway runs live for a document type, and its evidence is the in-use acceptance of the agent's drafts that ADR-0065 rule 11 already defines (drafts posted unchanged by people over at least two months), with no live shadow run.
- **Two budget tiers:** the company's daily cost cap, and the per-run ceilings that each agent type version declares. The nine per-agent-type budget settings are removed.
- **The gateway and AI drafting stay deterministic at the decision point.** The auto-post gateway (ADR-0065) and the artifact lifecycle (ADR-0059) are code and data, not agents; agents only feed them drafts and proposals that a checker, a backtest or a person decides.
- **One consolidated text** replaces eleven ADRs as the coding agents' source (rule 10).

The safety model is unchanged: the hard floors, the permission intersection, taint, the tainted read scope, drafts only, and the gateway's conditions for tainted drafts. Changing them is the author's decision (ADR-0005 item 7) and is not part of this ADR.

### Rules

**Scope**

1. Agent types of Phase 1:

   | Agent type | Starts after | Why it stays |
   | --- | --- | --- |
   | `bank_matching` | step 6 gate | Unmatched bank lines are daily work; the deterministic cascade does most of it, and the agent reads only the free-text remainder (ADR-0051) |
   | `purchase_invoice` | step 7 gate | Supplier invoices are the largest manual entry load; the agent drafts from a stored e-invoice record or a verified extraction (ADR-0051; ADR-0057 rule 26) |
   | `assistant` | step 5 gate | The one interactive entry: ask, act, resolve (ADR-0077 rules 13–18); it routes questions that need figures to `analysis`, and drafts what the deferred agents would help with |
   | `analysis` | step 5 gate | Turns a question into a deterministic analysis plan whose figures are server cells (ADR-0060); started by the assistant or from the analysis view |
   | `document_reader` | step 7 gate | The tool-less vision step of the intake ladder, run only when the deterministic readers fail and the vision seat is configured (ADR-0057 rules 12–14) |
   | `auto_post_advisor` | step 7 gate | Reads gateway outcomes and drafts decision-table and settings proposals for the gateway (ADR-0065); it never changes a setting itself |

   A Phase 1 agent type is listed in this table. Adding one is a scope change, for the author (ADR-0005 item 2).

   Two details of the table:
   - `purchase_invoice` keeps both entry paths of ADR-0051 and ADR-0057 rule 26: a stored e-invoice record, and (version 1.1.0) a document extraction that a person verified after the deterministic ladder.
   - The `assistant` declaration's interim ceilings, new here: 8 LLM calls, 40 tool calls, 40,000 input tokens, 4,000 output tokens, USD 0.50, 120 seconds and 2,000 rows read per run. `assist.max_cost_per_run` (default USD 0.20, bounds 0.01 to 0.50) may only lower the cost ceiling. Its evaluation set passes at 90% of all tasks and 100% of the refusal and taint tasks.

2. Agent types moved to Phase 2, each keeping its design, DDL draft and catalog rows as seams:
   - `customer_onboarding` and `quotation` (ADR-0051);
   - `planning` (ADR-0051);
   - `data_migration` (ADR-0051). At step 11, migration uses the staged import of ADR-0030 and ADR-0044 with stored mappings and deterministic fuzzy matching, and the assistant in `act` mode may draft mappings on a draft import batch. Every batch is still simulated and checked before it posts;
   - `product_engineering` (ADR-0062);
   - `production`, `production_capture` and `production_variance` (ADR-0064). The production core and its manual capture stay in Phase 1.

   Each moved agent type is registered with mode `off` and no workflow code in Phase 1. Its leaf, settings and evaluation rows exist. `check` refuses any other mode for it in seed and configuration, so `StartAgentRun` refuses it with the existing `agent_mode_off` (ADR-0050 rule 15).

**Declarations**

3. An agent type is declared in `backend/src/nativeflows/agents/declarations/<agent_type>.py` as one `AgentTypeDeclaration` named `DECLARATION`, written by `generate` into the agent type catalog. It holds:
   - `agent_type` and `version` (semver);
   - the subject tables it may start from, and the work item kinds that wake it;
   - the tool list: registered queries, plus commands registered `is_draft_only`;
   - the output schema of each LLM step (ADR-0050 rules 35, 36);
   - the per-run ceilings: LLM calls, tool calls, input and output tokens, cost, seconds and rows read;
   - the seat and data class of each LLM step (spec 17);
   - the path of its evaluation set and its pass threshold.

   The declaration is the only place these values live. The prose of ADR-0051 per agent type becomes the declaration's docstring and its workflow steps.

4. `nativeflows-dev check` validates every declaration:
   - the tool list names only registered queries and `is_draft_only` commands, and none of the never-list of ADR-0050 rule 30;
   - every per-run ceiling is set and within the installation maxima;
   - every LLM step has an output schema with no confidence, score, probability or certainty field (ADR-0050 rule 35);
   - the evaluation set exists, and a version without a passing result cannot be promoted (rule 6).

   A failure names the declaration's file and line, the rule and a one-line fix (ADR-0022 rule 13).

**Modes and promotion**

5. Phase 1 modes in `agent_type_setting.mode`: `off`, `assisted`, and `active` only as the gateway uses it. The DDL keeps `shadow` for Phase 2, and `check` refuses it in Phase 1 seed and configuration.
   - `active` is set for an agent type and the document types named in `active_document_types` only by an approved change proposal, with the evidence of rule 6, and only while `auto_post.<document_type>.mode` is `live` (ADR-0065 rule 11). The assistant is never `active` (ADR-0077 rule 13).
   - The setting `agents.<agent_type>.drift_action` keeps its values. Until Phase 2, `demote_to_shadow` acts as `pause_new_runs`.

6. Promotion to `assisted`:
   - A version is promoted when it passes its evaluation set and the replay of recorded responses in CI (ADR-0050). The evidence is the stored evaluation result, named in `agent_type_setting.promoted_version` and `promoted_seat_models`.
   - Spec 17 requires each pair of seat and model to pass; the evaluation result records the pair.
   - The offline evaluation runs in CI for each release, so its result is installation-wide. A company already `assisted` stays `assisted` across a new version or seat model whose evaluation for that pair passed; no new proposal is needed. A version or seat model without a passing result runs nothing: where ADR-0050 rule 14 drops the effective mode to `shadow`, Phase 1 drops it to `off`, with the same reason and the same `agent_mode_degraded` work item. There is no live shadow period in Phase 1. This applies to all six types, the assistant's `ask` and resolve purposes included.
   - `CreateAgentPromotionEvidence` computes the evidence from the stored offline evaluation result instead of `GetAgentShadowEvaluation` (ADR-0050 rule 14).
   - Promotion to `active` for a document type uses ADR-0065 rule 11 unchanged: `GetAgentDraftAcceptance` over the agent's `assisted` drafts of that document type (at least two calendar months, at least ceil(3 / `auto_post.max_error_rate`) drafts, at least 1 − rate posted unchanged, none to another partner), by an approved proposal another person approves. The gateway's own mode `shadow` for the document type runs its deterministic checker without posting; no live agent shadow is needed.
   - `analysis` keeps its stated exception (ADR-0050 rule 14 note): the daily `RunAnalysisEvaluation` on the company's verified examples is its offline evaluation, whatever its mode; it does not use mode `shadow`.
   - `document_reader` is promoted by the golden-set thresholds of ADR-0057 rule 34. Its live shadow-agreement criterion is replaced by the replay of the company golden set of at least 50 real documents, which that rule already requires before `assisted`.
   - Live shadow comparison of agents against what people did (ADR-0050 rule 14) returns in Phase 2, together with its evidence tables.

**Budgets**

7. Two budget tiers in Phase 1:
   - **Per company per day:** `agents.company_daily_max_cost`, within `agents.installation_daily_max_cost`, with the reserve `agents.internal_reserve_share` as in ADR-0050 rule 22. 
   - **Per run:** the ceilings of the agent type version's declaration (rule 3). For the assistant, `assist.max_cost_per_run` may lower its cost ceiling (ADR-0077 rule 13).
   - **Usage rows.** The `company_agent_type` rows of `agent_budget_usage` keep counting cost and runs per agent type, with no limit (`run_limit_count` and the per-type cost limit stay null). The reservation of ADR-0050 rule 23 checks the company row only. `agent_budget_exhausted` is raised once per company and business date when the company cap is reached, subject the agent type whose reservation failed.
   - **Internal reserve.** `analysis` reads no outside content, so it is the internal agent type of Phase 1 and draws on `agents.internal_reserve_share` (default 0.40, ADR-0050 rule 22). `auto_post_advisor` reads supplier invoices and is not internal.

   The nine settings `agents.<agent_type>.daily_max_cost`, `.daily_max_runs` and the seven `.run_max_*` keys are removed from `settings.csv`. A per-type daily cap returns only if one agent type is measured crowding out the others. The reservation before every LLM call, the stop on `budget_exceeded` and the `agent_budget_exhausted` work item stay (ADR-0050 rule 22).

**Gateway, AI drafting, analysis and vision, the light way**

8. Kept in Phase 1, each without new machinery:
   - **The auto-post gateway** (ADR-0065) as designed: a deterministic checker per document type, settings per document type with modes `off`, `shadow` and `live`, the conditions for tainted drafts, `ConfirmAutoPost` and the confirmation cadence. It lands with `policy` at step 5; the purchase invoice checker and the advisor follow at step 7 (ADR-0065). The deterministic bank cascade is one instance (ADR-0048 rule 9; ADR-0063 rule 8), and the author's lift of 2026-11-16 on `cash.auto_post.accept_llm_originated_rules` stays (ADR-0065 rule 12). What is light: the gateway is code and data, and the agent `active` mode it needs is evidenced by in-use draft acceptance (rule 6), not by a live agent shadow.
   - **AI drafting of tuned artifacts** (ADR-0059). Parameter sets, decision tables and rule sets may be drafted by agents. There is no tuning agent: drafts come from `auto_post_advisor` (gateway decision tables and settings), from the stored-resolution proposals of `bank_matching` and `purchase_invoice` (bank matching rules, item mappings; ADR-0051 rule 2), and from the assistant in `act` mode on request. Every draft enters the deterministic lifecycle of ADR-0059 (backtest before anything runs, then the stages its kind declares, rollback by pointer) and is approved by a person. AI does not write code for the running system (ADR-0059).
   - **The analysis agent** (ADR-0060) as designed: the plan is deterministic, figures are server cells, and the narrative is rendered by code from fixed templates. What is light: it is one declaration on the shared runtime, and the assistant routes questions that need figures to it instead of answering them itself, so there is one analysis path.
   - **The vision reader** (ADR-0057) as the minimal `document_reader` declaration: no tools, one LLM step, the vision seats `extraction_vision` and `extraction_vision_personal` (disabled until a provider is configured), per-run ceilings, and its evaluation set. A vision value is aligned to OCR words by code and stays untrusted until a person verifies it (ADR-0057 rules 13, 14).

9. Nothing in this ADR weakens a floor:
   - agents never submit, post, issue, send or approve: those commands are on the never-list (ADR-0050 rule 30), an origin run cannot submit (ADR-0029 rule 6 note), and the floors force `human_post` (ADR-0043 rule 9);
   - effective rights are the intersection of the agent type's and the person's (ADR-0054 rule 16);
   - taint, `ClearTaint` and the tainted read scope are unchanged (ADR-0029; ADR-0050 rules 25–27).

**Documents**

9a. Safety edge cases. EC-57, EC-79, EC-83 and EC-185 start from the deferred `quotation` agent. They stay in the catalog as Phase 2 cases. Their checks (injected instructions in outside content, laundering through a draft, crash and replay) are re-hosted in Phase 1 on `purchase_invoice` (injected text in a supplier e-invoice) and on the assistant (pasted untrusted text in an `act` request): in the assistant's evaluation set and in the DS-16 harness, with new edge-case rows written with the declarations at step 5.

10. The current agent design is consolidated in [design/agents-current.md](../design/agents-current.md): one text that states what applies in Phase 1, drawn from ADR-0029, ADR-0050, ADR-0051 and their notes, ADR-0077 and this ADR. The ADRs keep the history and win where the text disagrees. The coding agents read the consolidated text instead of eleven ADRs (ADR-0005, "small, self-contained documents").

## Context

The independent assessment of 2026-11-19 found the agent layer designed more thickly than the accounting it guards: about 105,000 words across eleven ADRs, 14 agent types, 26 agent and AI tables, about 41 agent and AI settings, and 43 agent or taint invariants, against 3 tax and 5 cash invariants. A pilot of 10–50 people gains little from most of it before go-live, and every extra agent type costs a workflow, a tool list, budgets, an evaluation set and tests. The author accepted level B of the simplification proposal on 2026-11-19: fewer agent types and less machinery, the safety model unchanged.

The author first accepted level B (three agent types), then revised it the same day: NativeFlows is agentic by design, so the gateway, AI drafting, the analysis agent and the vision reader stay in Phase 1, built the light way. SAP Joule and Dynamics 365 Copilot expose one assistant with skills that run with the user's rights and ask the user to confirm; NativeFlows keeps that pattern for the assistant, adds small background agents where the deterministic cascade leaves free text or numbers to explain, and keeps every automatic decision in deterministic code.

## Options considered

| Option | For | Against |
| --- | --- | --- |
| Level A: consolidate documents only | No scope change | Every agent type still needs its machinery and tests |
| Level B: three agent types, declarations, two modes, two budget tiers (first accepted) | Removes most of the build and test load | Drops the gateway, AI drafting, analysis and vision, which an agentic-by-design product needs |
| Level B revised: six agent types on one runtime, declarations, no live agent shadow, two budget tiers, deterministic gateway and lifecycle (chosen) | Keeps the agentic capabilities; machinery per agent stays small; safety unchanged | Six evaluation sets to build and keep current |
| Level C: also stop taint at human confirmation | Removes taint chains and `ClearTaint` | Changes a hard floor and reverses the 2026-11-19 decision on approval and taint; the author's |
| One agent before go-live (assessment recommendation 10) | Smallest | Loses the assistant, which the UI plan of ADR-0077 relies on |

## Constraints that come with the decision

- **ADR notes:** ADR-0050 rules 14, 22, 30; ADR-0051 (agent types) and rules 4, 9; ADR-0057 (vision reader as a minimal declaration); ADR-0058 and ADR-0059 (who drafts artifacts); ADR-0060 (routing from the assistant); ADR-0062; ADR-0063 rule 29 (removed definitions); ADR-0064; ADR-0065; ADR-0073 rule 1 (agent type declarations); ADR-0077 rule 23.
- **Catalogs:** nine rows removed from `settings.csv`.
- **Runbook:** the agents table of steps 5–9 and the step 10 lines name the six agent types.
- **Author's documents not edited:** spec 10 (Phase 1 agents, data migration and quotation agents), spec 11 (four go-live agents), spec 14 and spec 00 (shadow as a mode) still describe the earlier design. Their wording is the author's (open question).
- **ADR-0044 rule 15:** the data migration agent's part moves to Phase 2 (note).

## Revisit when

- A Phase 2 agent type's manual path costs the pilot more than one person-day a week: bring it forward by a scope decision.
- One agent type is measured using more than half of a company's daily cost cap: restore a per-type daily cap.
- The offline evaluation passes but drafts are rejected in use more often than its threshold allows: restore live shadow for that agent type.

## Documents updated

- **ADRs:** [ADR-0050](0050-agent-runtime-and-query-layer.md), [ADR-0051](0051-agent-workflows.md), [ADR-0057](0057-document-intake-and-extraction.md), [ADR-0058](0058-configurable-workflows.md), [ADR-0059](0059-ai-tuning-and-development-of-deterministic-functions.md), [ADR-0060](0060-agent-assisted-reporting-and-analysis.md), [ADR-0062](0062-product-engineering-workflow.md), [ADR-0063](0063-configurable-policy-settings.md), [ADR-0064](0064-production-agent.md), [ADR-0065](0065-deterministic-auto-post-gateway.md), [ADR-0073](0073-coding-pipeline-and-mechanical-assurance.md), [ADR-0077](0077-ui-floorplans-annotations-and-embedded-agent.md), each with a note.
- **Design:** [design/agents-current.md](../design/agents-current.md) (new).
- **Catalogs:** [settings.csv](../catalogs/settings.csv).
- **Runbook:** [steps-5-9.md](../runbook/steps-5-9.md), [go-live.md](../runbook/go-live.md), [steps-0-4.md](../runbook/steps-0-4.md).
- **Open questions, index and log:** [docs/open-questions.md](../open-questions.md), [docs/adr/README.md](README.md), [docs/runbook/step-log.md](../runbook/step-log.md).
