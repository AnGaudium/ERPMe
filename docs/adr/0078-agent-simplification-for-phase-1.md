# ADR-0078: Agent scope and the common work model for Phase 1

Status: accepted (2026-11-21) under ADR-0005, reviewed by Claude Opus 5.5 after two review rounds (builders: Claude Opus 5.5, proposed 2026-11-19; Claude Fable 5.2, the chief architect of session S1, to whom the author delegated the Phase 1 agent scope, reworked 2026-11-21). Design items: DS-32, DS-33, DS-34. Related decisions: D2, D11, D15. Principles 3, 8, 12, 13. ADR-0013, ADR-0024, ADR-0029, ADR-0030, ADR-0032, ADR-0036, ADR-0042, ADR-0043, ADR-0044, ADR-0048, ADR-0050, ADR-0051, ADR-0054, ADR-0057, ADR-0058, ADR-0059, ADR-0060, ADR-0062, ADR-0063, ADR-0064, ADR-0065, ADR-0066, ADR-0073, ADR-0077.

## Decision

The agent layer of Phase 1 keeps its agentic capabilities and loses most of its machinery. The safety rules stay as they are; what shrinks is what each agent needs to exist. The core stays deterministic, and agents take part in business work through the same work items as people.

- **Six agent types in Phase 1, on one runtime:** `assistant` (ADR-0077), `analysis` (ADR-0060), `bank_matching`, `purchase_invoice`, `document_reader` (the vision step of ADR-0057) and `planning` (ADR-0051 rules 23–25). The other eight designed agent types move to Phase 2, with their designs, DDL drafts and seams kept.
- **One work model.** A work item is the unit of business work for people, deterministic code and agents. An agent run is one attempt at a work item, not the work itself. The work item kind is the contract between a domain module and whoever does the work, so a new agent type joins an existing workflow without a change to the module (rules 11 to 14).
- **Agent types as declarations.** An agent type is a typed Python declaration, like a command (ADR-0073). The runtime of ADR-0050 is written once; an agent type adds only its declaration, its workflow steps and its evaluation set.
- **No live shadow for agents.** Promotion to `assisted` comes from the offline evaluation set. In use, a daily quality check on what people did with the agent's drafts replaces the shadow comparison (rule 15). Mode `active` exists only where the auto-post gateway runs live for a document type, on the in-use evidence of ADR-0065 rule 11.
- **Two budget tiers:** the company's daily cost cap, and the per-run ceilings that each agent type version declares. The nine per-agent-type budget settings are removed.
- **The gateway and AI drafting stay deterministic at the decision point.** The auto-post gateway (ADR-0065) and the artifact lifecycle (ADR-0059) are code and data, not agents; agents only feed them drafts and proposals that a checker, a backtest or a person decides.
- **One consolidated text** replaces ten ADRs as the coding agents' source (rule 10).

The safety model is unchanged: the hard floors, the permission intersection, taint, the tainted read scope, drafts only, and the gateway's conditions for tainted drafts. Changing them is the author's decision (ADR-0005 item 7) and is not part of this ADR.

### Rules

**Scope**

1. Agent types of Phase 1:

   | Agent type | Starts after | Why it is in Phase 1 |
   | --- | --- | --- |
   | `assistant` | step 5 (work package 8); its evaluation set is a step 5 gate item (ADR-0077 rule 23) | The one interactive entry: ask, act, resolve (ADR-0077 rules 13–18); it routes questions that need figures to `analysis`, and drafts what the deferred agents would help with |
   | `analysis` | step 5 gate | Turns a question into a deterministic analysis plan whose figures are server cells (ADR-0060); started by the assistant or from the analysis view |
   | `bank_matching` | step 6 gate | Unmatched bank lines are daily work; the deterministic cascade does most of it, and the agent reads only the free-text remainder (ADR-0051) |
   | `purchase_invoice` | step 7 gate | Supplier invoices are the largest manual entry load; the agent drafts from a stored e-invoice record or a verified extraction (ADR-0051; ADR-0057 rule 26) |
   | `document_reader` | step 7 gate | The tool-less vision step of the intake ladder, run only when the deterministic readers fail and the vision seat is configured (ADR-0057 rules 4 and 11) |
   | `planning` | after the manual path of planning with multi-level MRP is built and has passed its gate (after step 5; ADR-0024 rule 26, ADR-0032 rule 7). The runbook does not place that work yet (open question) | Planners work by exception. Code computes the candidate actions and their effect on the projection; the one LLM step chooses among them and explains, with every number checked against its input; the output is a change proposal a person approves (ADR-0051 rules 23–25) |

   A Phase 1 agent type is listed in this table. Adding one is a scope change, for the author (ADR-0005 item 2).

   Details of the table:
   - `purchase_invoice` keeps both entry paths of ADR-0051 and ADR-0057 rule 26: a stored e-invoice record, and (version 1.1.0) a document extraction that a person verified after the deterministic ladder. Its Phase 1 declaration is the "next version" of ADR-0063 rule 11: it declares the wake-up kind `supplier_invoice_received` `configurable`, so `agents.purchase_invoice.wake_up_mode.supplier_invoice_received` applies with default `always`.
   - The `assistant` declaration's interim ceilings, new here: 8 LLM calls, 40 tool calls, 40,000 input tokens, 4,000 output tokens, USD 0.50, 120 seconds and 2,000 rows read per run. `assist.max_cost_per_run` (default USD 0.20, bounds 0.01 to 0.50) may only lower the cost ceiling. Its evaluation set passes at 90% of all tasks and 100% of the refusal and taint tasks.
   - `planning` is the safest kind of agent the design has: it declares `may_read_untrusted: false`, reads internal data only and is never tainted (ADR-0050 rule 28); it writes nothing but a draft change proposal, and floor 7 requires approval of every proposal (ADR-0043 rule 9). Its ceilings are those of ADR-0051 rule 9, and its evaluation set passes its golden set at 90% (ADR-0051 rule 7); the size of the set is fixed with the declaration. This restores, for planning, what ADR-0032 rule 7 decided: the planning agent is done before the platform counts as complete.
   - **One at a time.** Each agent type is built behind its manual path (spec 11, B6) and counts as done only when its evaluation set passes. Agent types that start after the same gate are built in the order of this table. No gate depends on an agent's accuracy in use: the gate items that name an agent are evaluation sets on recorded and synthetic cases (the assistant's at step 5, ADR-0077 rule 23). No agent in mode `active` is a go-live condition.

    Note (author's delegation, 2026-11-21; decided by the chief architect): the build order now places the manual path of planning with multi-level MRP as step 5b ([runbook](../runbook/steps-5-9.md), [spec 11](../spec/11-build-order.md)). The `planning` agent starts after the step 5b gate; this replaces "the runbook does not place that work yet" in the table above. Its golden pair of rule 13 is an item of the agent's own completion, not of the step 5b gate.

2. Agent types moved to Phase 2, each keeping its design, DDL draft and catalog rows as seams:
   - `auto_post_advisor` (ADR-0065 rule 18). It reads months of gateway outcomes that do not exist before go-live. Until then a person proposes gateway settings and decision tables, and the assistant in `act` mode may draft them on request (rule 8);
   - `customer_onboarding` and `quotation` (ADR-0051);
   - `data_migration` (ADR-0051). At step 11, migration uses the staged import of ADR-0030 and ADR-0044 with stored mappings and deterministic fuzzy matching, and the assistant's help is bounded: an `act` run is tainted and reads its request, the batch row as context subject and at most 100 selected import rows, so it may draft mappings for the selected rows only and proposes no merges against existing records. The bulk of the mapping is stored mappings and deterministic fuzzy matching. Every batch is still simulated and checked before it posts;
   - `product_engineering` (ADR-0062);
   - `production`, `production_capture` and `production_variance` (ADR-0064). The production core and its manual capture stay in Phase 1. `production` reads no outside content, so it is the first to bring forward when a Phase 2 agent is chosen.

   Each moved agent type is registered with mode `off` and no workflow code in Phase 1. Its leaf, settings and evaluation rows exist, and the work item kinds it would wake on are raised and handled by people (rule 12). `check` refuses any other mode for it in seed and configuration, and `UpdateAgentTypeSetting` refuses it at run time (rule 5), so `StartAgentRun` refuses it with the existing `agent_mode_off` (ADR-0050 rule 15).

**Declarations**

3. An agent type is declared in `backend/src/nativeflows/agents/agent_types/<agent_type>.py` as one `AgentTypeDeclaration` named `DECLARATION`, written by `generate` into the agent type catalog. (The folder `declarations/` holds the module's command and query declarations, ADR-0073 rule 1.) It holds:
   - `agent_type` and `version` (semver);
   - the subject tables it may start from, and the work item kinds that wake it;
   - the tool list: registered queries, plus commands registered `is_draft_only`;
   - the output schema of each LLM step (ADR-0050 rules 35, 36);
   - the per-run ceilings: LLM calls, tool calls, input and output tokens, cost, seconds and rows read;
   - the seat and data class of each LLM step (spec 17);
   - the path of its evaluation set and its pass threshold;
   - every other element that ADR-0050 rule 12 and its notes declare: `may_read_untrusted`, `scope_kind` and its scope resolver, `field_classes`, the prompt templates, `auto_post_document_types` (ADR-0065 rule 11), the wake-up kinds declared `configurable` (ADR-0063 rule 11) and, for `analysis`, the catalog hash.

   The declaration is the only place these values live. The prose of ADR-0051 per agent type becomes the declaration's docstring and its workflow steps.

4. `nativeflows-dev check` validates every declaration:
   - the tool list names only registered queries and `is_draft_only` commands, and none of the never-list of ADR-0050 rule 30;
   - every per-run ceiling is set;
   - every LLM step has an output schema with no confidence, score, probability or certainty field (ADR-0050 rule 35);
   - the evaluation set exists, and a version without a passing result cannot be promoted (rule 6);
   - no work item kind is declared by two agent types (rule 12).

   A failure names the declaration's file and line, the rule and a one-line fix (ADR-0022 rule 13).

**Modes and promotion**

5. Phase 1 modes in `agent_type_setting.mode`: `off`, `assisted`, and `active` only as the gateway uses it. The DDL keeps `shadow` for Phase 2. `check` refuses it in Phase 1 seed and configuration, and at run time `UpdateAgentTypeSetting` refuses mode `shadow` in Phase 1, and refuses every mode except `off` for an agent type that has no Phase 1 workflow (rule 2), with `validation_failed` (`agent_mode_not_declared` is ADR-0065 rule 11's code for `active` without declared document types and is not reused).
   - `active` is set for an agent type and the document types named in `active_document_types` only by an approved change proposal, with the evidence of rule 6 (ADR-0065 rule 11). New here: while the document type's gateway mode is not `live`, the agent type counts as `assisted` for the gateway. The assistant and `planning` are never `active`: their outputs are drafts and proposals that a person confirms or approves.
   - The setting `agents.<agent_type>.drift_action` keeps its values. Until Phase 2, `demote_to_shadow` acts as `pause_new_runs`.

6. Promotion to `assisted`:
   - **Evidence.** A version is promoted when it passes its evaluation set with the real provider, per pair of seat and model, and the replay of recorded responses in CI (ADR-0050 rules 39, 40; spec 17). The replay proves the code path; only the real-provider run proves a model, so a new seat model always needs it. The evidence is the stored evaluation result, named in `agent_type_setting.promoted_version` and `promoted_seat_models`.
   - **Where the result lives.** `generate` writes the passing results of a release into an evaluation manifest shipped with it: one row per agent type, behavior hash, seat and model. The runtime reads the manifest; nothing else proves a pair.
   - **Carry-over.** A company already `assisted` stays `assisted` across a change of the behavior hash (version, constants or seat model; ADR-0050 rule 14) when the manifest holds a passing result for the new behavior. The runtime then updates `promoted_version` and `promoted_seat_models` as `system`, with an audit record, so later evidence counts under the behavior that actually runs. The model fallback of ADR-0050 rule 6 uses only models with a passing result in the manifest.
   - **No tunable parameter sets in Phase 1.** No Phase 1 agent type declares a parameter set (ADR-0059 rule 7), so the behavior hash has no per-company part; constants are part of the version.
   - **No result, no run.** A behavior without a passing result runs nothing: where ADR-0050 rule 14 drops the effective mode to `shadow`, Phase 1 drops it to `off`, with the same reason and the same `agent_mode_degraded` work item. This applies to all six types, the assistant's `ask` and resolve purposes included.
   - **`active` does not carry over.** On any change of the behavior hash an `active` agent type counts as `assisted` for the gateway until it is promoted again under ADR-0065 rule 11 on drafts of the new behavior. Draft acceptance counts only drafts written under the current behavior hash.
   - **No live shadow period.** `CreateAgentPromotionEvidence` computes the evidence from the stored evaluation result instead of `GetAgentShadowEvaluation` (ADR-0050 rule 14).
   - **Promotion to `active`** for a document type uses ADR-0065 rule 11 unchanged: `GetAgentDraftAcceptance` over the agent's `assisted` drafts of that document type (at least two calendar months, at least ceil(3 / `auto_post.max_error_rate`) drafts, at least 1 − rate posted unchanged, none to another partner), by an approved proposal another person approves. The gateway's own mode `shadow` for the document type runs its deterministic checker without posting; no live agent shadow is needed.
   - **`analysis`** keeps its stated exception (ADR-0050 rule 14 note): the daily `RunAnalysisEvaluation` on the company's verified examples is its evaluation in use. A version with no passing CI evaluation is `off` like any other; a failing daily evaluation raises `agent_quality_below_threshold` (rule 15).
   - **`document_reader`** is promoted by the golden-set thresholds of ADR-0057 rule 34. Its live shadow-agreement criterion is replaced by the replay of the company golden set of at least 50 real documents, which that rule already requires before `assisted`. It is the one exception to the carry-over: after a change of behavior it returns to `assisted` in a company only when the replay of that company's golden set has passed again (ADR-0057 rule 13).
   - **`planning`** is promoted by its evaluation set; the comparator of ADR-0051 rule 25 measures quality in use on stored output (rule 15), and live shadow runs return in Phase 2.
   - Live shadow comparison of agents against what people did (ADR-0050 rule 14) returns in Phase 2, together with its evidence tables.

**Budgets**

7. Two budget tiers in Phase 1:
   - **Per company per day:** `agents.company_daily_max_cost`, within `agents.installation_daily_max_cost`, with the reserve `agents.internal_reserve_share` as in ADR-0050 rule 22.
   - **Per run:** the ceilings of the agent type version's declaration (rule 3). For the assistant, `assist.max_cost_per_run` may lower its cost ceiling (ADR-0077 rule 13).
   - **Usage rows.** The `company_agent_type` rows of `agent_budget_usage` keep counting cost and runs per agent type. Their `limit_amount` is set to the company's cap, so the row never binds before the company row does; `run_limit_count` stays null. The per-type row's `limit_amount` is refreshed to the company cap in force at every reservation, so a raised cap never leaves a lower limit on it. The reservation of ADR-0050 rule 23 checks the company row, the installation row and, for agent types that read outside content, the `company_outside_content` row; it no longer checks a per-type limit. `agent_budget_exhausted` is raised once per business date and tier that trips, with the open keys of ADR-0050 rule 24 and the rule 55 note: `company:<date>`, `outside_content:<date>` (the outside-content pool: types that read outside content stop, internal types keep running on the reserve) and `installation:<date>`; its subject is the agent type whose reservation failed.
   - **Internal reserve.** `analysis` and `planning` read no outside content, so they are the internal agent types of Phase 1 and draw on `agents.internal_reserve_share` (default 0.40, ADR-0050 rule 22).
   - **Spec 03 rule 8** asks for budgets per agent, per company and per day. Phase 1 reads it as: per agent, the per-run ceilings of the declaration and the per-type usage rows; per company and per day, the company cap. Spec 03 rule 8 and the per-day seat budget of spec 17 are the author's to align (open question).
   - **What the customer sets.** The author's direction of 2026-11-16 let the customer lower every cap (ADR-0050 rule 22, design-hardening note). The author's scope decision of 2026-11-19 (two budget tiers) narrows it: in Phase 1 the customer sets the company's daily cap and the assistant's cost per run. A per-type cap returns under "Revisit when".

   The nine settings `agents.<agent_type>.daily_max_cost`, `.daily_max_runs` and the seven `.run_max_*` keys are removed from `settings.csv`. The reservation before every LLM call, the stop on `budget_exceeded` and the `agent_budget_exhausted` work item stay (ADR-0050 rule 22).

**Gateway, AI drafting, analysis and vision, the light way**

8. Kept in Phase 1, each without new machinery:
   - **The auto-post gateway** (ADR-0065) as designed: a deterministic checker per document type, settings per document type with modes `off`, `shadow` and `live`, the conditions for tainted drafts, `ConfirmAutoPost` and the confirmation cadence. It lands with `policy` at step 5; the purchase invoice checker follows at step 7, after the purchase invoice manual path (this corrects "step 6" in ADR-0065). The deterministic bank cascade is one instance (ADR-0048 rule 9; ADR-0063 rule 8), and the author's lift of 2026-11-16 on `cash.auto_post.accept_llm_originated_rules` stays (ADR-0065 rule 12). What is light: the gateway is code and data, and the agent `active` mode it needs is evidenced by in-use draft acceptance (rule 6), not by a live agent shadow.
   - **AI drafting of tuned artifacts** (ADR-0059). Parameter sets, decision tables and rule sets may be drafted by agents. There is no tuning agent and, in Phase 1, no advisor: drafts come from the stored-resolution proposals of `bank_matching` and `purchase_invoice` (bank matching rules, item mappings; ADR-0051 rule 2), from the parameter and lead-time proposals of `planning` (ADR-0024 rule 23), and from the assistant in `act` mode on request. Every draft enters the deterministic lifecycle of ADR-0059 (backtest before anything runs, then the stages its kind declares, rollback by pointer) and is approved by a person. AI does not write code for the running system (ADR-0059).
   - **The analysis agent** (ADR-0060) as designed: the plan is deterministic, figures are server cells, and the narrative is rendered by code from fixed templates. What is light: it is one declaration on the shared runtime, and the assistant routes questions that need figures to it instead of answering them itself, so there is one analysis path.
   - **The vision reader** (ADR-0057) as the minimal `document_reader` declaration: no tools, one LLM step, the one vision seat `extraction_vision_personal` (ADR-0057 rule 21; disabled until a provider is configured and a data processing permission covers it), per-run ceilings, and its evaluation set. A vision value is aligned to OCR words by code and stays untrusted until a person verifies it (ADR-0057 rules 12, 17).

9. Nothing in this ADR weakens a floor:
   - agents never submit, post, issue, send or approve: those commands are on the never-list (ADR-0050 rule 30), an origin run cannot submit (ADR-0029 rule 6 note), and the floors force `human_post` (ADR-0043 rule 9);
   - effective rights are the intersection of the agent type's and the person's (ADR-0054 rule 16);
   - taint, `ClearTaint` and the tainted read scope are unchanged (ADR-0029; ADR-0050 rules 25–27).

**Documents**

9a. Safety edge cases. EC-57, EC-79 and EC-83 start from the deferred `quotation` agent, and EC-80 and EC-87 from the deferred `customer_onboarding` agent. EC-227 (`advisor_drafts_only`) starts from the deferred `auto_post_advisor`. All six stay in the catalog as Phase 2 cases with their trigger, and cannot run in Phase 1; `design/DS-17-synthetic-dataset.md` excludes them from the Phase 1 coverage counts (the catalog has no phase column). The checks of EC-57, EC-79 and EC-83 (injected instructions in outside content, laundering through a draft, crash and replay) are re-hosted in Phase 1 on `purchase_invoice` (injected text in a supplier e-invoice) and on the assistant (pasted untrusted text in an `act` request): in the assistant's evaluation set and in the DS-16 harness, with new edge-case rows written with the declarations at step 5. EC-185 (`wake_up_by_rule`) is a configurable wake-up check, not a safety check; it is re-hosted on `supplier_invoice_received` of `purchase_invoice` (its row in `catalogs/edge-cases.csv` is rewritten for it) and is not a Phase 2 case.

10. The current agent design is consolidated in [design/agents-current.md](../design/agents-current.md): one text that states what applies in Phase 1, restated from ADR-0029, ADR-0050, ADR-0051, ADR-0057, ADR-0059, ADR-0060, ADR-0063, ADR-0065 and their notes, ADR-0077 and this ADR. The ADRs keep the history and win where the text disagrees. The coding agents read the consolidated text instead of ten ADRs (ADR-0005, "small, self-contained documents").

**One work model**

These rules state in one place what ADR-0042, ADR-0050, ADR-0058 and ADR-0066 already decide, and close what they left unsaid. They add no table.

11. The four things that must not be confused:

    | Concept | In NativeFlows | Authoritative state |
    | --- | --- | --- |
    | Business work | A `work_item` (ADR-0042): kind, subject, evidence, owner, due date | `open`, `claimed`, `done`, `canceled`; the owner is always a person, a role or an approval stage |
    | Progress of a process | The document's lifecycle state, its open work items and, where a company turns it on, the `work_case` that groups them (ADR-0066) | The documents and work items themselves. There is no workflow instance and no orchestration engine in Phase 1 (ADR-0058; D2): waiting is a work item, asynchrony is the outbox |
    | Work given to an agent | The work item while an agent run holds its claim (or an `agent_task` item of the run's own) | `claimed_by_kind` `agent_run`; the claim is a lease that expires |
    | One attempt | An `agent_run` with its steps (ADR-0050) | `queued`, `running`, `completed`, `stopped`, `canceled` |

    - **A run is not the work.** A run that ends leaves the work item unclaimed with its owner, with links to the drafts and a note. Only a person, the owning module or a registered command resolves a work item; agents never do (`is_agent_resolvable` is false for every Phase 1 kind, ADR-0042 rule 16). Several runs may work on one item, one at a time: a retry after a crash continues the same run, and a new run needs a new raise or a person.
    - **A person can always take over.** A person's claim takes the item from a run, whose later commands fail with `work_item_claim_lost` (ADR-0042; INV-205). The drafts and the note stay.
    - **Nothing waits inside a model.** An agent run never waits for a person. The human step finishes as its own command, which raises the next work item or event, and that starts a new run from stored rows: the draft, the work item's links and notes, verified extraction fields, stored resolutions. No state is rebuilt from an earlier model response or a chat (spec 03 rule 9). A follow-up to the assistant is a new request that names a previous request of the same person; `CreateAssistRequest` refuses another person's request (`validation_failed`). An untainted run (`ask` and the resolve purposes) may read that previous request's stored text and answer. An `act` run starts tainted and reads only its own request, its context subject and the selected rows (ADR-0050 rule 27 note), so an `act` follow-up restates what it needs; adding the previous request to the tainted scope would widen that scope and is the author's.
    - **Handoff keeps the controls.** The owner stays the owner; the run acts for the workflow owner or the person who started it, within the intersection of rights; what a tainted run wrote stays tainted until a person other than that human clears it (ADR-0029 rule 8).
    - **A running run finishes on its version.** A change of the agent type's version or mode applies to runs that start afterwards. Rights are evaluated at every call, so a revoked right denies the next call, and the third denial stops the run (ADR-0050 rules 31, 33).

12. The work item kind is the contract.
    - **A domain module names no agent type.** It raises a work item of a kind and registers the commands that act on the subject. Which participant does the work is declared outside it: the kind's owner rule names the people; an agent type's declaration lists the kinds that wake it (rule 3); a deterministic consumer may resolve a kind whose resolution is `system`.
    - **One agent type per kind.** `check` refuses a kind declared by two agent types (rule 4), so a wake-up is never ambiguous.
    - **Adding an agent later changes no module.** The kinds that the deferred agent types wake on are raised in Phase 1 and handled by people. Bringing an agent type forward adds its declaration, its steps and its evaluation set; the module, the work item kind and the manual path stay as they are. The same holds for replacing an agent step by deterministic code.
    - **No capability registry.** A separate catalog of capabilities that workflows request would repeat what the work item kind and the registered commands already state, and add a second place to keep in step. It is reconsidered when two agent types need to serve one kind (see "Revisit when").

13. Every workflow has its manual path, and it is tested.
    - With `llm_provider` unset, every agent mode is `off`, every work item stays with people, and every operation works (Principle 12; ADR-0050 rule 5).
    - **Proposed gate item, for the author (gates are reserved, ADR-0005):** the purchase invoice flow is a golden scenario at step 7 in two variants over the same input files: with agents, using recorded responses, and with the LLM off. Both must end in the same posted invoice. The flow has every kind of step: deterministic intake and extraction, the vision reader, a person's verification, the agent's draft, the three-way match, approval where the match is exceeded, the gateway in `shadow`, and a person's posting. The planning agent gains the same pair for one planning exception at its gate, once the manual path of planning with multi-level MRP has passed its gate (rule 1). This turns "works with LLMs off" from a walk-through into a check.

    Note (author's delegation, 2026-11-21; decided by the chief architect): the purchase invoice golden scenario in two variants (agents on recorded responses, LLM off, both ending in the same posted invoice) is a gate item of step 7 from 2026-11-21 and is no longer proposed ([runbook](../runbook/steps-5-9.md), step 7). The planning pair stays an item of the planning agent's own completion after the step 5b gate, not of that gate.

14. Tracing. An operator follows one piece of work from the work item: `ListAgentRun` filters by `work_item_id`; `GetAgentRun` returns the steps with tool name, plan hash and audit record; the case timeline of ADR-0066 rule 17 shows items, runs, versions, approvals and policy decisions in order. Cost and runs per company, agent type and business date are the `company_agent_type` rows of `agent_budget_usage`, shown on the operations dashboard (ADR-0038).

15. Quality in use. `RunAgentQualityCheck` runs daily per company and `assisted` agent type over the last 30 days (ADR-0051 rule 5). With no live shadow, the measure in Phase 1 applies each workflow's existing comparator to what the agent produced in `assisted` mode against what the person finally did on the same work item: `bank_matching` by ADR-0051 rule 19, `purchase_invoice` by rule 22, `planning` by rule 25, `document_reader` by the field agreement of ADR-0057 rule 34; `analysis` by its daily evaluation (rule 6). The comparator needs no shadow run: the agent's output and the person's result are both stored. For the assistant's `act` drafts there is no comparator: the share of drafts canceled is shown on the operations dashboard and raises nothing.

    A measure more than 10 points below the agent type's evaluation threshold raises `agent_quality_below_threshold`, and `agents.<agent_type>.drift_action` applies. While that item is open, an `active` agent type counts as `assisted` for the gateway (ADR-0065 rule 11).

## Context

The independent assessment of 2026-11-19 found the agent layer designed more thickly than the accounting it guards: about 105,000 words across 11 ADRs, 14 agent types, 26 agent and AI tables, about 41 agent and AI settings, and 43 agent or taint invariants, against 3 tax and 5 cash invariants. Every extra agent type costs a workflow, a tool list, budgets, an evaluation set and tests. Its recommendation 10: drafts only, one agent before go-live, and the gateway, AI tuning, configurable workflows and the analysis agent deferred.

The author accepted level B of the simplification proposal on 2026-11-19 (three agent types), then revised it the same day: NativeFlows is agentic by design, so the gateway, AI drafting, the analysis agent and the vision reader stay in Phase 1, built the light way. On 2026-11-21 the author delegated the scope decision to the chief architect of session S1 and gave two inputs: an architecture recommendation, "Make agentic-by-design a native workflow capability", and the request to consider agents that support planning from the start. His direction: a deterministic core, and agents used as far as they can be inside workflows.

The chief architect's decision, with reasons:

- **Recommendation 10 is taken in its intent, not its letter.** "Drafts only" already holds for every agent. "One agent before go-live" becomes one agent type at a time, each behind its manual path and its evaluation, with no gate depending on one. The gateway stays because the deterministic bank cascade already uses it and it is code, not an agent; its `live` mode for agent drafts cannot be reached before go-live, because its evidence needs two months of use.
- **`auto_post_advisor` moves to Phase 2.** It has nothing to read before go-live, and an agent that proposes loosening auto-post rules is the one whose value depends most on evidence we do not have yet.
- **`planning` comes into Phase 1.** It is the cheapest and safest agent type in the design: internal data, never tainted, one LLM step over candidates that code computed, a proposal that always needs approval. Planning is exception work, which is where an agent helps most, and ADR-0032 rule 7 had already put it before platform completion.
- **The recommendation's three concepts are adopted as statements, not as new machinery.** The design already has a common work model (ADR-0042), separates the run from the work (ADR-0050), and keeps process state in documents and work items (ADR-0058). What was missing was one place that says so, a rule that keeps domain modules free of agent types, a quality measure in use, and a test of the manual path. Rules 11 to 15 add those. A workflow engine, a capability registry and multi-agent coordination are not added: D2 and ADR-0058 decided against the first, the second would duplicate the work item kind, and no Phase 1 workflow needs the third.

SAP Joule and Dynamics 365 Copilot expose one assistant with skills that run with the user's rights and ask the user to confirm; NativeFlows keeps that pattern for the assistant, adds small background agents where the deterministic cascade leaves free text or numbers to explain, and keeps every automatic decision in deterministic code.

## Options considered

| Option | For | Against |
| --- | --- | --- |
| Level A: consolidate documents only | No scope change | Every agent type still needs its machinery and tests |
| Level B: three agent types, declarations, two modes, two budget tiers (first accepted) | Removes most of the build and test load | Drops the gateway, AI drafting, analysis and vision, which an agentic-by-design product needs |
| Level B revised: six agent types with `auto_post_advisor` (the branch of 2026-11-19) | Keeps the agentic capabilities | The advisor has no data before go-live; planning, where agents help with exception work, is left out |
| Six agent types with `planning`, the advisor deferred, and the work model stated (chosen) | Agents sit in purchasing, cash, intake, planning, analysis and the UI; each is small; safety unchanged; later agents join without changing modules | Six evaluation sets to build and keep current |
| Add a workflow engine, a capability registry or agent-to-agent coordination now | Looks like the large vendors' target architecture | Against D2 and ADR-0058; duplicates the work item kind; nothing in Phase 1 needs it |
| Level C: also stop taint at human confirmation | Removes taint chains and `ClearTaint` | Changes a hard floor and reverses the 2026-11-19 decision on approval and taint; the author's |
| One agent before go-live (assessment recommendation 10) | Smallest | Loses the assistant, which the UI plan of ADR-0077 relies on |

## Constraints that come with the decision

- **ADR notes:** ADR-0050 rules 12, 14, 22, 24, 30; ADR-0051 (agent types) and rules 4, 5, 9, 25; ADR-0057 rules 1 and 34 (vision reader as a minimal declaration; golden-set replay instead of shadow agreement); ADR-0058 rule 1 and ADR-0059 rules 1 and 12 (who drafts artifacts; evaluation instead of shadow); ADR-0060 rule 25 (routing from the assistant; evaluation); ADR-0062; ADR-0063 rule 29 (removed definitions); ADR-0064 (production first to bring forward); ADR-0065 rules 11 and 18 and the build line (the advisor in Phase 2; step 7); ADR-0073 rule 1 (agent type declarations); ADR-0077 rule 23; ADR-0024 rule 26 and ADR-0032 rule 7 (the planning agent in Phase 1); ADR-0042 rule 16 (the work model of rules 11 and 12).
- **Catalogs:** nine rows removed from `settings.csv`; the descriptions of `agent_mode_degraded`, `agent_budget_exhausted` and `agent_quality_below_threshold` in `work-item-kinds.csv` follow rules 5 to 7; the row of EC-185 in `edge-cases.csv` is re-hosted on `purchase_invoice` (rule 9a).
- **Design documents:** the coverage rule of `design/DS-17-synthetic-dataset.md` excludes the Phase 2 edge cases of rule 9a from Phase 1 counts; `design/DS-30-ui.sql` makes the same-person follow-up of rule 11 a key.
- **Runbook:** the agents table of steps 5–9 and the step 10 lines name the six agent types.
- **Author's documents** (author's delegation, 2026-11-19): spec 10 (Phase 1 agent list and build table), spec 11 (agents line), spec 14 (evaluation instead of shadow mode) and two glossary rows of spec 00 (agent mode, effective agent mode).
- **ADR-0044 rule 15:** the data migration agent's part moves to Phase 2 (note).

## Revisit when

- A Phase 2 agent type's manual path costs the pilot more than one person-day a week: bring it forward by a scope decision.
- One agent type is measured using more than half of a company's daily cost cap: restore a per-type daily cap.
- The offline evaluation passes but the quality check of rule 15 stays below its threshold for an agent type for 30 days: restore live shadow for that agent type.
- Two agent types need to serve one work item kind, or a workflow needs two agents to work on one item at once: design the capability contract and the coordination then.
- Two real processes need a wait that no document state or work item can express: design durable orchestration (ADR-0058, W10).

## Documents updated

- **ADRs:** [ADR-0024](0024-planning.md), [ADR-0032](0032-phase-1-scope-with-production.md), [ADR-0042](0042-work-queue.md), [ADR-0044](0044-data-migration-and-export.md), [ADR-0050](0050-agent-runtime-and-query-layer.md), [ADR-0051](0051-agent-workflows.md), [ADR-0057](0057-document-intake-and-extraction.md), [ADR-0058](0058-configurable-workflows.md), [ADR-0059](0059-ai-tuning-and-development-of-deterministic-functions.md), [ADR-0060](0060-agent-assisted-reporting-and-analysis.md), [ADR-0062](0062-product-engineering-workflow.md), [ADR-0063](0063-configurable-policy-settings.md), [ADR-0064](0064-production-agent.md), [ADR-0065](0065-deterministic-auto-post-gateway.md), [ADR-0073](0073-coding-pipeline-and-mechanical-assurance.md), [ADR-0077](0077-ui-floorplans-annotations-and-embedded-agent.md), each with a note.
- **Design:** [design/agents-current.md](../design/agents-current.md) (new), [design/architecture-overview.md](../design/architecture-overview.md), [design/DS-05-platform.sql](../design/DS-05-platform.sql), [design/DS-30-ui.sql](../design/DS-30-ui.sql), [design/DS-17-synthetic-dataset.md](../design/DS-17-synthetic-dataset.md), lab `t24_settings.py` ([validation lab](../reviews/2026-11-14-design-validation/lab/t24_settings.py)).
- **Catalogs:** [settings.csv](../catalogs/settings.csv), [work-item-kinds.csv](../catalogs/work-item-kinds.csv), [edge-cases.csv](../catalogs/edge-cases.csv).
- **Runbook:** [steps-5-9.md](../runbook/steps-5-9.md), [go-live.md](../runbook/go-live.md), [steps-0-4.md](../runbook/steps-0-4.md), [README.md](../runbook/README.md).
- **Spec (delegated lines):** spec 00, 10, 11 and 14.
- **Open questions, index and log:** [docs/open-questions.md](../open-questions.md), [docs/adr/README.md](README.md), [docs/runbook/step-log.md](../runbook/step-log.md).
