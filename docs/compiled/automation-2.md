Module: automation    Chunk: 2 of 2    Source ADRs: ADR-0059, ADR-0063, ADR-0065, ADR-0066
Build step(s): 1, 3, 5, 6, 7, 9    Generated from index: 30d5706    Compiled by: Claude Fable 5.2, 2026-11-21

# Compiled spec: `automation`, chunk 2

## Purpose

`automation` (layer 5) runs company-composed automation rules and the system jobs and consumers that dispatch through `registry`; it owns no table. This chunk states the commands and catalog rows of the tunable-artifact evidence (ADR-0059), the automation and autonomy settings of ADR-0063, the runner of the auto-post gateway and its deterministic tools (ADR-0065), and the work case opener and resolver (ADR-0066). The gateway itself, its decision record and its generic rules belong to `policy`; artifact tables belong to `configuration`. Chunk 1 states the automation rule engine, the artifact evidence rules and the monitor.

## Entities and tables

None: the module owns no table.

Reads: `policy_decision`, `policy_rule`, `policy_rule_version`, `artifact_transition`, `artifact_promotion_evidence`, `artifact_monitor_snapshot`, `golden_case_label`, `agent_type`, `agent_type_setting`, `agent_promotion_evidence`, `document`, `audit_record`, `setting_value`.

## Commands and queries

| Name | Actor and authorization | Input | Effect | Events | Error codes |
| --- | --- | --- | --- | --- | --- |
| `ListArtifactEvidence`, `GetArtifactEvidence`, `ListArtifactTransition`, `ListArtifactMonitorSnapshot`, `GetParameterSet`, `ListDecisionArtifact` | Area `automation` at `read` for evidence, transitions and monitor snapshots; filtered by the reader's rights; modules `automation` and `configuration` (R201) | not stated | Query | none | not stated |
| `RunAutoPostGateway` | System job; `is_internal_only` | Per company and document type whose `auto_post.<document_type>.mode` is `shadow` or `live` | Effect class `other`; simulates and dispatches `Post<Type>` as `system` (R233-R237, R253) | not stated | not stated |
| `ListAutoPostCase` | not stated; held-out filtered | Document type, date range | Query (R250) | none | not stated |
| `EvaluateAutoPostBacktest` | not stated; held-out filtered | Candidate settings values, candidate decision table rows, evaluation window | Computed query (R251) | none | not stated |
| `ListAutoPostThresholdCandidate` | not stated; held-out filtered | not stated | Computed query (R252) | none | not stated |

The rows of `CreateArtifactEvidence` and `RunArtifactMonitor` are in chunk 1.

Not registered commands of this chunk: the transactional consumer `work_case_opener` (queue `events`, R260) and the work case resolver, a system job (R263). The hook `auto_post_checker` and the pure function `policy.contract.evaluate_auto_post` are declared by `policy` (R231). The sources name no module for `GetArtifactVersionContent` (R222).

Commands of other modules that the rules of this chunk name: `CreateParameterSet`, `UpdateParameterSet`, `CreateParameterSetVersion`, `UpdateParameterSetVersion`, `DeleteParameterSetVersion`, `SetArtifactVersionState`, `SetArtifactCurrentVersion`, `RecordGoldenCaseLabel`, `ListGoldenCaseLabel`, `EnableAutomationRule` (`configuration`); `CreateBankMatchingRuleVersion` (`cash`); `RecordAutoPostDecision`, `EvaluateAutoPostGateway`, `EnablePolicyRule`, `ConfirmAutoPost` (`policy`); `GetPurchaseInvoiceAutoPostShadowEvaluation` (`purchasing`); `GetAgentDraftAcceptance`, `UpdateAgentTypeSetting` (`agents`); `CreateWorkCase`, `ResolveWorkCase` (`work`).

Error codes bound to no command of this module: those of R202, and `auto_post_checker_missing`, `agent_mode_not_declared`, `shadow_evidence_insufficient`, `plan_hash_mismatch`.

## Rules

### Tunable artifacts: commands and catalog rows

R201. ADR-0059 registers these commands and queries (name: module, effect class, notes):
- `CreateParameterSet`, `UpdateParameterSet`: `configuration`, `master_data_change`; function code and owner.
- `CreateParameterSetVersion`, `UpdateParameterSetVersion`, `DeleteParameterSetVersion`: `configuration`, `other`; drafts only; `is_draft_only`; bounds and order checked.
- `CreateBankMatchingRuleVersion`: `cash`, `other`; drafts only; `is_draft_only`; the consumer's carrier (ADR-0059.R10).
- `CreateArtifactEvidence`: `automation`, `other`; a person's command; on no agent tool list; stages `backtest`, `preview`, `live`.
- `SetArtifactVersionState`: `configuration`, `master_data_change`; `is_proposal_bound` for raising; minimum level `full`.
- `SetArtifactCurrentVersion`: `configuration`, `other`; rollback; level `full`.
- `RecordGoldenCaseLabel`: `configuration`, `other`; approve flag on the function's leaf.
- `RunArtifactMonitor`: `automation`, `other`; daily system job, also the release re-evaluation; `is_internal_only`.
- `GetParameterSet`, `ListDecisionArtifact`, `ListArtifactEvidence`, `GetArtifactEvidence`, `ListArtifactTransition`, `ListArtifactMonitorSnapshot`: `automation`, `configuration`; query; filtered by the reader's rights.
- `ListGoldenCaseLabel`: `configuration`; query; on no agent tool list.
- `CreateArtifactEvidence`, `SetArtifactVersionState`, `SetArtifactCurrentVersion`, `RecordGoldenCaseLabel` and `ListGoldenCaseLabel` are commands never on a tool list (ADR-0050.R30).
Source: ADR-0059.R27

R202. The error codes of ADR-0059 (DS-04) are, by class:
- precondition: `artifact_evidence_insufficient`, `artifact_evidence_stale`, `artifact_version_not_eligible`, `drafting_window_violated`, `drafting_run_steps_missing`, `held_out_case_seen`, `auto_post_evidence_outdated`;
- validation: `backtest_window_not_after_drafting`, `backtest_source_undated`, `parameter_out_of_bounds`, `parameter_order_violated`;
- permission: `golden_label_not_permitted`, `held_out_filter_unavailable`.
Source: ADR-0059.R28

R203. The work item kinds of ADR-0059 belong to module `automation` and are resolved by a person:
- `artifact_demoted` (`days:5`), `artifact_invalidated` (`days:1`) and `artifact_reference_deprecated` (`days:30`): subject `artifact_transition`; owner the artifact's owner, named by the raiser.
- `artifact_function_changed` (`days:5`): subject the re-evaluation in `artifact_promotion_evidence`; owner named by the raiser, namely the set's owner (`company_owner` under core defaults) and each dependent auto-post rule's owner, one item per owner with the owner in its key.
Source: ADR-0059.R28

R204. Company settings of ADR-0059: `artifacts.<function code or kind>.<threshold>` holds the values of ADR-0059.R18, and `artifacts.proposal_ttl_days` is 30. Declared per function, for `cash.match_bank_line`: `reevaluation_window_days` (60), `reevaluation_max_window_days` (180) and `reevaluation_min_cases` (50).
Source: ADR-0059.R28

R205. The invariants of ADR-0059 (the block of ADR-0058.R28) are:
- `INV-677`: every artifact version out of draft has the content its `content_hash` names, and its child rows have not changed since it left draft.
- `INV-678`: every current pointer names a version of its artifact in state `assisted` or `active`, every shadow pointer one in `shadow`.
- `INV-681`: every parameter value lies within the bounds and order constraints its function declared at the version's function version, and no safety cap is null or exceeds its core default.
- `INV-682`: every bank document posted by `system` from a cascade proposal has a line that carries the parameters hash the enabling evidence of its auto-post rule names, a `match_parameter_state` of `active` or `core_default`, `match_is_tied` false and no `counterparty_unverified` or `paid_by_third_party` flag, and that rule version's evidence is not marked outdated; every demotion, rollback, invalidation and failed re-evaluation of the parameter set marked the evidence of every dependent rule version outdated in its own transaction.
- `INV-683`: no condition field, decision table input or scorer gate reads a field that is not registered `is_gate_field`, and no gate field has LLM lineage.
- `INV-679` (`promoted` transitions evidenced), `INV-680` (backtests out of sample, with `drafting_reads_hash`), `INV-684` (breaches demote) and `INV-685` (golden case labels, with `is_held_out`): the statements are the rows of chunk 1.
Source: ADR-0059.R28

R206. The edge cases of ADR-0059 (the block of ADR-0058.R28) are:
- `EC-164`: a function release between the evidence and the approval's execution makes the promotion fail with `artifact_evidence_stale`, while the version already in force keeps acting and gets a re-evaluation.
- `EC-165`: a bank token rule is written as a draft version, waits for a later line, is approved into suggest mode by a second person, and moves to confirm mode on live evidence with its score from steps 3–4.
- `EC-168`: a bank-fee token rule maps to the bank charges account; an outflow with the whole token drafts to that account at `cap_company_rule` under the unverified-counterparty cap, flagged `counterparty_unverified` and never auto-posted; an inflow with it only suggests, and a line that more than one such rule matches only suggests.
- `EC-163` and `EC-166`: the cases are the rows of chunk 1.
Source: ADR-0059.R28

### Promotion, demotion and the acting error ceiling

R210. The acting ceiling is `auto_post.max_error_rate`: company scope, default 1%, bounds 0.1% to 2%. The evidence of an auto-post rule on a learned or probabilistic matching path needs N proposals with at least (1 − rate) posted unchanged, N ≥ 3 ÷ rate, over at least two statement months, and none posted to another partner. This is an observed error rate at most the ceiling over N cases, not a 95% bound, which holds only when none was changed. The default gives the 300 proposals at 99% of ADR-0051.R18; 2% gives 150 and 0.1% gives 3,000.
Source: ADR-0063.R10

R211. Windows, not lower bars. `artifacts.<function_or_kind>.max_window_days` (default 90, bounds 28 to 365) lets a small company collect evidence over a longer window; the minimums never fall below the declaration's small-company minimum, and they never lower the acting ceiling. The suggest-mode minimums of the bank cascade are settings with bounds: `artifacts.cash.match_bank_line.min_backtest_cases` (200, bounds 50 to 5,000) and `artifacts.cash.match_bank_line.min_live_cases` (100, bounds 30 to 5,000); other functions declare theirs the same way. The precision targets, the held-out golden-case threshold, the demotion formula and the held-out share are the declared values of ADR-0059, not settings (open question).
Source: ADR-0063.R10

R212. Demotion is as ADR-0059.R21 defines it, judged only over at least 30 decisions (a loosening, ADR-0063.R5); the window is widened as for re-evaluation (ADR-0059.R4) until 30 are reached.
Source: ADR-0063.R10

R213. Hard: any auto-post that a person reverses, or records as wrong when confirming (ADR-0043.R14), suspends the document type (ADR-0065.R16, ADR-0065.R20). In the same transaction the evidence of every enabled rule version that allows `system` or `integration` to post that document type is outdated, and `auto_post_suspended` is raised for each such rule's owner. Later candidates get `require_human` (`auto_post_evidence_mismatch`) until a new rule version is enabled on new evidence. A live `require_human` is stored as `human_only`, and the DDL forces `human_post` true for it.
Source: ADR-0063.R10

### Agent wake-up modes

R214. The setting `agents.<agent_type>.wake_up_mode.<kind>` has scope `agent_type`, values `always`, `by_rule`, `off` and default `always`. Under `always`, `agent_wake_up` starts the agent. Under `by_rule`, `agent_wake_up` skips the kind, and only an automation rule with action `start_agent` and its own conditions starts the agent; items no rule starts stay with people. Under `off`, every item goes to people.
Source: ADR-0063.R11

R215. Only kinds an agent type version declares `configurable` accept the wake-up setting. The first are the quotation agent's `inbound_message_matched` and the purchase invoice agent's `supplier_invoice_received`, declared in their next versions. "Configurable" means that the company chooses the mode, with `always` as the default; "configurable means configured" of ADR-0058.R7 applies only under `by_rule`.
Source: ADR-0063.R11

R216. The conditions of a `start_agent` rule read trusted metadata only: the receiving mailbox or channel, the partner matched by address (never by a model), whether the partner is known, branch, document source and attachment type.
Source: ADR-0063.R11

R217. Narrowing the wake-up mode (`by_rule`, `off`) is one person with `edit` on `agent`; widening is a proposal. Hard: no agent wakes an agent; a rule never widens tools, scope, budget or taint handling; no trigger on approval, posting or send events.
Source: ADR-0063.R11

### Automation settings, breaker and flood guard

R220. Customization levels 1 and 3 of spec 16 are in Phase 1, as ADR-0058 has them. The spec texts are the author's, and their wording is an open question: spec 16 should split level 1 into 1a (Phase 1: settings, parameter sets, policy thresholds, approval pools, decision tables) and 1b (after Phase 1: user-defined fields and tables), and say level 3 is "structured rules over a registry vocabulary, no rule language", controlled by stored tests, a replay diff and a change proposal; spec 10 should say "no rule language; structured decision tables and automation rules (ADR-0058)".
Source: ADR-0063.R20

R221. Company settings of automation:
- `automation.dispatch_paused` (default false): pausing is one person with `edit` on `configuration`, at once; resuming is a proposal; while paused the automation consumer acknowledges events without evaluating them, and nothing is replayed on resume.
- `automation.max_active_rules` (200, bounds 1 to 1,000).
- `automation.replay_window_days` (30, bounds 7 to 90, within the outbox retention).
- `automation.replay_min_events` (20, bounds 0 to 1,000; at 0 the diff is shown without a count gate).
Source: ADR-0063.R20

R222. Export and import as draft (flagged): `GetArtifactVersionContent` returns a version's canonical JSON and content hash. Another deployment of the same customer imports it only as a new draft through the kind's draft command, recording the source hash; the draft then runs its own tests, replay and proposal on that deployment's data.
Source: ADR-0063.R20

R223. The circuit breaker of ADR-0058.R16 reads company settings, each with an optional override in a rule version's content (hashed with it): `automation.breaker_failures` (5, bounds 1 to 50), `automation.breaker_window_minutes` (60, bounds 5 to 1,440) and `automation.breaker_consecutive` (20, bounds 3 to 200, and at least `automation.breaker_failures`).
Source: ADR-0063.R21

R224. Flood guard: `automation.max_executions_per_rule_per_hour` (500, bounds 10 to 10,000; a rule version may override it). Beyond it in a clock hour of the recorded instant, the consumer records outcome `rate_limited` and runs no action, a declared technical timer (ADR-0007.R10); `rate_limited` never counts toward the breaker. It raises `automation_rule_rate_limited` for the rule's owner, one per rule and business date.
Source: ADR-0063.R21

R225. Hard: the breaker cannot be turned off (no value means never). What counts is fixed: `refused`, `failed`, `partial`; never skips by design, `skipped_same_target`, `depth_exceeded` or `rate_limited`. Re-enabling is a person's `EnableAutomationRule`. The depth cap of 3 stays a constant.
Source: ADR-0063.R21

### Auto-post gateway: design, ownership and runner

R230. The auto-post gateway generalizes the auto-post path of ADR-0043.R14:
- Any document type whose owning module declares an auto-post checker can be auto-posted through the same path. The gateway is a pure function of `policy` (layer 2) that calls domain checker functions registered through a hook and wired by `app`; no module is added.
- Maker and checker: an agent or a deterministic import makes a draft, the dispatcher simulates the posting, and the gateway checks the draft and its simulation and returns `auto_post`, `require_human` or `reject`. Every decision writes a `policy_decision` row with the checker's evidence. An `auto_post` posts as `system` in a new transaction, pinned to the simulated plan hash and business date, and the policy rule's owner confirms it.
- Thresholds are registered settings with bounds, directions and safe core defaults (ADR-0063); logic over several variables lives in typed decision tables (ADR-0058); checker code holds no customer constant. A company starts with auto-post `off` for every document type.
- A draft with values an LLM read from outside content may be auto-posted only when the company and the document type both enable it (default off, a loosening that another person approves), the drafting agent type is in agent mode `active` on evidence, the checker passes, and every value the checker relies on carries a verification result.
- A document type runs in shadow first and goes live only on evidence meeting `auto_post.max_error_rate`, through a change proposal that another person approves. One confirmed wrong auto-post suspends the document type at once.
- The first instance is the purchase invoice. The bank cascade and the production import are instances of the same gateway and keep their behavior.
Source: ADR-0065.D0

R231. Ownership and the hook:
- `policy` owns the gateway: the pure function `policy.contract.evaluate_auto_post`, the generic rules of ADR-0065.R5, the decision record (ADR-0065.R6) and the internal command `RecordAutoPostDecision`.
- `policy` declares the hook `auto_post_checker`. A module registers, per document type it owns, one checker implementation; `app` (layer 6) wires it. `policy` imports no module above it (ADR-0022.R2, ADR-0043.R1).
- Inputs that `policy` cannot read itself are passed in by the dispatcher (`registry`), which already reads them for the actor context: the generic settings of ADR-0065.R8 with their values and sources (`registry.contract.get_setting`), the draft version's effective taint, the agent run that wrote it, that run's agent type, behavior hash and effective mode (ADR-0050.R14), and the simulation result.
- The runner is the system job `RunAutoPostGateway` of module `automation` (layer 5), which already imports `registry` for dispatch and the contracts of layers 3 and 4 (ADR-0058.R1). It is not an automation rule: it runs no company-composed action, and its only posting path is a gateway decision (R244).
Source: ADR-0065.R1

R232. The gateway is in Phase 1. The agent mode `active` it needs keeps the in-use draft acceptance evidence of ADR-0065.R11, with no live agent shadow. `auto_post_advisor` (ADR-0065.R18) is a Phase 2 agent type; until then people propose gateway settings and decision tables, and the assistant in `act` mode may draft them on request. The purchase invoice checker lands at step 7, after the purchase invoice manual path (ADR-0078.R1, ADR-0078.R2, ADR-0078.R5, ADR-0078.R6, ADR-0078.R8).
Source: ADR-0065.R1.N1

R233. Candidates, for checkers with `runner: gateway_job`. `RunAutoPostGateway` runs every 5 minutes (a declared technical timer; the business date is fixed per run, ADR-0007.R17) per company and document type whose `auto_post.<document_type>.mode` is `shadow` or `live`. A candidate is a draft of that type whose latest version was written by a non-human (an agent run that has ended, a consumer, an integration or a system job), with no gateway decision for that version yet. A version a person wrote is never a candidate: a person posts it.
Source: ADR-0065.R3

R234. Simulate. For each candidate, in its own transaction, the job simulates `Post<Type>` as `system` on behalf of the owner of the enabled policy rule that allows the posting (spec 03 rule 3), or of the company's owner when none is enabled. The simulation returns the plan, `plan_hash`, the check results, `as_of_date` (ADR-0007.R15) and the gateway's decision, computed at the policy point after the handler has built the plan, as for commands registered `is_policy_in_handler` (DS-04 check order, step 9).
Source: ADR-0065.R3

R235. Execute. When the decision is `auto_post` and the mode is `live`, the job executes `Post<Type>` in a new transaction with `expected_plan_hash` set to the simulated hash and `as_of_date` set to the simulated date. The gateway is evaluated again inside that execution on the same inputs; the `policy_decision` row commits with the posting.
Source: ADR-0065.R3

R236. Otherwise (`require_human`, `reject`, shadow mode, a refused execution, an error) the job writes the decision with `RecordAutoPostDecision` in a transaction of its own and raises `auto_post_review` unless the mode is `shadow`.
Source: ADR-0065.R3

R237. The job starts its own causation chain with no origin agent run. The passed checker decision is the trust boundary, as a person's command resets the origin (ADR-0013.R2). ADR-0029.R12 and `INV-85` stand as written: no consumer on an agent's chain posts. The decision's evidence names the run that wrote the draft.
Source: ADR-0065.R3

### Auto-post gateway: hard rules

R238. No LLM in the checker. Neither the gateway nor a checker calls the LLM gateway, starts an agent run or reads model output other than the draft's own values. Checker code lives in the core or a package, reviewed like other code (ADR-0059.R24). The hard rules R238 to R243 are cross-cutting hard locks in the sense of ADR-0063.R6.
Source: ADR-0065.R7

R239. Fail closed. An unknown case, missing reference data, an unmatched decision table row, a setting without a value in force, a stale input or any exception gives `require_human`, never `auto_post`.
Source: ADR-0065.R7

R240. Read-only. The gateway and checkers never write. They never change a draft's value to make it pass; only the posting command writes, and only the simulated plan.
Source: ADR-0065.R7

R241. System execution. The posting runs as `system` on behalf of the enabled rule's owner, never as the person who started the agent, and its audit record names the decision.
Source: ADR-0065.R7

R242. Plan check. The execution must reproduce `expected_plan_hash` with the pinned `as_of_date`. A different plan returns `plan_hash_mismatch` (ADR-0008.R13); nothing posts, and the job records `require_human` with reason `auto_post_plan_changed`.
Source: ADR-0065.R7

R243. Confirmation. Every gateway posting is an auto-post under ADR-0043.R14 and ADR-0029.R13: the rule's owner confirms it with `ConfirmAutoPost`, unconfirmed auto-posts block the period lock, and `INV-87` holds. The window of one `auto_post_unconfirmed` item follows `auto_post.confirmation_cadence` (ADR-0065.R8).
Source: ADR-0065.R7

R244. Automation rules never approve or post. ADR-0058.R3 stands unchanged: no automation rule submits, approves, posts or issues. The gateway is a policy decision on a draft at the policy point of `Post<Type>`, evaluated by core code with settings and a decision table at a module decision point; it is not an automation rule, so ADR-0058.R3 needs no exception. A decision table used here only outputs a decision; it runs no action.
Source: ADR-0065.R13

### Auto-post gateway: shadow mode and evidence

R245. In mode `shadow` the job evaluates every candidate and records the decision (ADR-0065.R6) without posting or raising `auto_post_review`.
Source: ADR-0065.R14

R246. The evidence function of a checker is an evidence hook in the pattern of `GetAutoPostShadowEvaluation` (ADR-0043.R14). For the purchase invoice it is `GetPurchaseInvoiceAutoPostShadowEvaluation` (module `purchasing`): over a date range, the shadow decisions `auto_post` under one checker version and one decision table version, and of those drafts the share that people posted unchanged (the evaluated version posted with no later version, not canceled, not reversed by the evidence date). Drafts still open are not counted.
Source: ADR-0065.R14

R247. Floor. At least N = ceil(3 / `auto_post.max_error_rate`) such decisions over at least two calendar months, at least (1 − rate) posted unchanged, none posted to another supplier (the rule of three of ADR-0063.R10; 300 at 99% with the default). Below it `EnablePolicyRule` returns `shadow_evidence_insufficient`.
Source: ADR-0065.R14

R248. Bound. `EnablePolicyRule` stores the evidence with the checker version, the decision table version and content hash, and the setting keys the evidence was judged under (`evidence_setting_keys`, ADR-0043.R14). A gateway decision in `live` whose checker version or table version differs gets `require_human` (`auto_post_evidence_mismatch`).
Source: ADR-0065.R14

R249. No checker, no system posting. `EnablePolicyRule` for a rule that allows `system` or `integration` to post or issue a document type with no registered checker returns `auto_post_checker_missing`.
Source: ADR-0065.R14

### Auto-post gateway: deterministic tools, commands and catalog rows

R250. The numbers of a proposal come from code, never from a model (ADR-0063.R6). `ListAutoPostCase` (module `automation`, query, held-out filtered, ADR-0059.R16) returns the cases of a document type in a date range, one per posted, canceled or reversed draft, with the checker's facts as of its decision, the human outcome (posted unchanged, posted changed, canceled, reversed) and no free text.
Source: ADR-0065.R17

R251. `EvaluateAutoPostBacktest` (computed, held-out filtered) returns, for candidate settings values and candidate decision table rows over an evaluation window that starts after the drafting window (ADR-0059.R15): the decisions the gateway would have taken on each case, the expected auto-post rate, the error rate (auto-posts whose drafts people changed, canceled or reversed), the changed decisions against the settings and table in force, and the result on held-out golden cases.
Source: ADR-0065.R17

R252. `ListAutoPostThresholdCandidate` (computed) returns candidate threshold sets computed by code from the case distribution (the observed variances and amounts at fixed quantiles), each with its backtest figures.
Source: ADR-0065.R17

R253. ADR-0065 registers these commands and queries (name: module, effect class, notes):
- `RunAutoPostGateway`: `automation`, `other`; system job every 5 minutes per company and document type in `shadow` or `live`; `is_internal_only`; dispatches `Post<Type>` as `system` (R233-R237).
- `RecordAutoPostDecision`: `policy`, `other`; `is_internal_only`; writes a `require_human`, `reject` or shadow decision and raises `auto_post_review`.
- `GetPurchaseInvoiceAutoPostShadowEvaluation`: `purchasing`, query; evidence function registered through the hook (R246); on no agent tool list.
- `GetAgentDraftAcceptance`: `agents`, query; figures for an `active` promotion (ADR-0065.R11); on no agent tool list.
- `EvaluateAutoPostGateway`: `policy`, query; computed, for people: the decision a draft would get now, with every rule's outcome; on no agent tool list.
- `ListAutoPostCase`, `EvaluateAutoPostBacktest`, `ListAutoPostThresholdCandidate`: `automation`, query; held-out filtered (R250-R252).
- `UpdateAgentTypeSetting` gains the mode `active` (ADR-0065.R11). `EnablePolicyRule` gains `auto_post_checker_missing` (R249). `ConfirmAutoPost` follows the cadence of ADR-0065.R8.
Source: ADR-0065.R21

R254. The catalog rows of ADR-0065 are:
- Settings: the definitions of ADR-0065.R8 in `settings.csv` (`auto_post.<document_type>.mode`, `auto_post.<document_type>.max_amount_company`, `auto_post.<document_type>.allowed_currencies`, `auto_post.<document_type>.allow_tainted`, `auto_post.<document_type>.require_verified_values`, `auto_post.allow_tainted_drafts`, `auto_post.confirmation_cadence`, `auto_post.purchase_invoice.min_supplier_invoices`, `auto_post.purchase_invoice.price_tolerance_percent`, `auto_post.purchase_invoice.quantity_tolerance_percent`, `auto_post.purchase_invoice.require_full_receipt`); `cash.auto_post.accept_llm_originated_rules` gets bounds `true|false` (ADR-0065.R12).
- Errors (DS-04): `auto_post_checker_missing` (precondition), `agent_mode_not_declared` (validation).
- Gateway reason codes, recorded in `policy_decision.auto_post_reason_code` and not errors: the codes of ADR-0065.R5, ADR-0065.R7 and ADR-0065.R10, and the checker's codes of ADR-0065.R19.
- Work item kind `auto_post_review`: module `policy`, subject `document`, `role:accountant`, `days:1`, resolved by the system when the version is posted, canceled or replaced. `auto_post_unconfirmed` is due at the end of its confirmation window (`named_by_raiser`, ADR-0065.R8).
- Registry vocabulary (DS-04): the auto-post checker declaration (ADR-0065.R2).
- Authorization area: `agent_auto_post_advisor` under `agent` (ADR-0054.R24).
- DDL (`docs/design/DS-05-platform.sql`): `policy_decision` gains `auto_post_decision`, `auto_post_mode`, `auto_post_reason_code`, `auto_post_checker_code`, `auto_post_checker_version`, `auto_post_plan_hash`, `auto_post_as_of_date` and `auto_post_evidence`, with a check that ties them to the stored outcome; `agent_type_setting.mode` accepts `active`, with `active_document_types`; `agent_promotion_evidence` gains `target_mode` and `document_type`. Checkers are registry declarations in code, not a table.
- Invariants `INV-760` to `INV-764` of the block INV-760 to INV-789, and `INV-84` restated; edge cases `EC-220` to `EC-228` of the block EC-220 to EC-239.
Source: ADR-0065.R22

### Work cases: opener and resolver

R260. Mode `auto`. The transactional consumer `work_case_opener` of module `automation` (layer 5, queue `events`) reacts to `WorkItemRaised` for kinds that a case kind names as its trigger, only where the company's mode for that case kind is `auto`. It runs `CreateWorkCase` as `system` on behalf of the event's human (ADR-0013.R9), with key `work_case_opener:<event id>:1`. The origin is the item's subject when its table is allowed, the item is attached, and the partner is copied only from the subject's matched `partner_id`.
Source: ADR-0066.R6

R261. `work_case_opener` skips events that carry an origin agent run, so nothing in an agent's chain opens a case. On a tainted event it may still run, because opening a case drafts, posts and sends nothing (ADR-0013.R11).
Source: ADR-0066.R6

R262. Mode `by_rule`. The automation rule action `open_work_case` (ADR-0058) takes the kind, the origin from the triggering subject, and the owner by `named_by_raiser`. It runs `CreateWorkCase` as `system` on behalf of the rule's owner, who needs `CreateWorkCase` and read rights on the subject (ADR-0058.R9). A rule may open only a kind whose mode is `by_rule` or `auto`.
Source: ADR-0066.R7

R263. Resolution `system`. The case resolves, with resolution `completed`, when every `artifact` target that is not unlinked is in a final state (`posted`, `reversed`, `canceled` or `closed`, ADR-0009.R14), or, for a change proposal (ADR-0066.R8), in `closed` or `canceled` (ADR-0029.R3), and no linked work item is `open` or `claimed`.
Source: ADR-0066.R15

R264. The work case resolver is a system job of module `automation` (layer 5), beside `work_case_opener`. It runs when a linked item is resolved or canceled and when a linked document reaches a final state. It reads the linked targets' states through their modules' contracts and resolves the case with the ordinary command `ResolveWorkCase`, run as `system` for kinds with resolution `system`; the command has no internal flag (ADR-0066.R13), so people keep running it for kinds with resolution `person`. `work` itself reads no document state.
Source: ADR-0066.R15

## Invariants

The rows of `INV-679`, `INV-680`, `INV-684` and `INV-685` are in chunk 1. `R205` in a statement cell means the statement of that invariant in R205; `invariants.csv` adds the detail given after it. Area `platform`: `INV-677`, `INV-678`, `INV-681`; every other row `safety`. First step 6: `INV-682`, `INV-760` to `INV-764`, `INV-87`; every other row 5.

| INV | Check point | Statement | Protects |
| --- | --- | --- | --- |
| `INV-677` `artifact_versions_immutable` | day | R205 | ADR-0058.R21, ADR-0059.R12 |
| `INV-678` `artifact_pointers_eligible` | day | R205; for automation rules the current pointer names a version in `active` | ADR-0059.R12 |
| `INV-681` `parameters_within_bounds` | day | R205 | ADR-0059.R3 |
| `INV-682` `auto_post_parameters_evidenced` | day | R205; "not marked outdated" is `shadow_evidence_outdated_by` null | ADR-0059.R6, ADR-0043.R14 |
| `INV-683` `gates_read_gate_fields` | day | R205 | ADR-0059.R20 |
| `INV-760` `auto_post_gateway_decided` | day | Every posting by `system` or `integration` of a document type with a registered auto-post checker has a `policy_decision` with `auto_post_decision` `auto_post` and mode `live`, a checker code and version, evidence in which every rule passed, and an `auto_post_plan_hash` equal to the posted plan's hash; its policy rule version was enabled with evidence naming that checker version and decision table version, not outdated on the posting date. | R233-R243, R245-R249 |
| `INV-761` `auto_post_tainted_gated` | day | Every gateway posting of a tainted draft happened while `auto_post.allow_tainted_drafts` and `auto_post.<document_type>.allow_tainted` were true on its date, with the drafting agent type's effective mode `active` for that document type at the behavior hash its evidence covered, and, while `require_verified_values` was true, no amount or quantity of the plan with basis `llm_read_only`. | R230, ADR-0065.R10 |
| `INV-762` `auto_post_gateway_without_model` | day | No LLM call or agent run has a causation chain that `RunAutoPostGateway` started, and no gateway decision's evidence names a model output other than the draft's own values. | R238 |
| `INV-763` `wrong_auto_post_suspends_document_type` | day | Every reversal of a gateway posting, and every confirmation recording one wrong, marked in the same transaction the evidence of every enabled rule version allowing `system` or `integration` to post that document type outdated. | R213, ADR-0065.R16 |
| `INV-764` `agent_active_evidenced` | day | Every `agent_type_setting` in mode `active` names document types its promoted agent type version declares, each covered by sufficient `agent_promotion_evidence` with target mode `active` at the promoted behavior hash, from a proposal approved by a person other than its submitter. | R232, ADR-0065.R11 |
| `INV-84` `tainted_never_auto_allowed` | day | No policy decision with outcome `allowed` for a non-human actor concerns a document version (change proposals included) that was effectively tainted at the time of the decision, except a live auto-post gateway decision `auto_post` under ADR-0065.R10 (`INV-761`). | R230, ADR-0065.R12 |
| `INV-85` `agent_consumers_never_post` | day | No audit row with actor `system` and an origin agent run has effect class `posting` or `master_data_change`. | R237 |
| `INV-87` `auto_posts_confirmed_before_lock` | day | Every posting by actor `system` or `integration` whose policy decision has `is_confirmation_required`, in a locked period, has an `auto_post_confirmation` row. | R243 |

## Edge cases

The rows of `EC-163` and `EC-166` are in chunk 1. `R206` in a case cell means the case of that row in R206; `edge-cases.csv` adds the detail given after it. Area `platform`: `EC-164`; `cash`: `EC-165`, `EC-168`; `purchasing`: `EC-220`, `EC-221`, `EC-228`; `safety`: `EC-222` to `EC-227`. The first executable step of every row is 6.

| EC | Name | Case | Outcome | Source |
| --- | --- | --- | --- | --- |
| `EC-164` | `promotion_evidence_stale` | R206; the owner gets `artifact_function_changed` with a re-evaluation, and new evidence succeeds | `must_reject:artifact_evidence_stale`, then `must_succeed` | ADR-0059.R4, ADR-0059.R19 |
| `EC-165` | `bank_token_rule_suggest_then_confirm` | R206; in suggest mode it drafts without a score; a line naming another partner's reference stays a suggestion | `must_succeed` | ADR-0059.R10 |
| `EC-168` | `bank_account_rule` | R206 | `must_succeed` | ADR-0059.R10 |
| `EC-220` | `purchase_invoice_auto_post` | An agent-drafted invoice of a supplier with enough history matches its fully received order exactly; with the type `live`, tainted drafts enabled and the agent `active`, the gateway posts it as `system` and an `auto_post_unconfirmed` item asks the rule's owner to confirm. | `must_succeed` | ADR-0065.R3 (R233-R237), ADR-0065.R10, ADR-0065.R19 |
| `EC-221` | `purchase_invoice_price_variance` | A line 5% above the order price with a 1% tolerance gets `require_human`, and `auto_post_review` names `price_outside_auto_post_tolerance` with both prices. | `must_succeed` | ADR-0065.R4, ADR-0065.R19 |
| `EC-222` | `tainted_auto_post_disabled` | The same clean invoice with `auto_post.allow_tainted_drafts` false gets `require_human` (`auto_post_tainted_not_enabled`); a direct change to true returns `proposal_required`. | `must_reject:proposal_required` for the change; `must_succeed` | ADR-0065.R8, ADR-0065.R10 |
| `EC-223` | `llm_chosen_item_not_verified` | A line whose item the LLM chose among candidates gets `require_human` (`line_item_not_mapped`); after the mapping proposal is approved, the supplier's next invoice posts. | `must_succeed` | ADR-0065.R10, ADR-0065.R19 |
| `EC-224` | `plan_changed_before_execution` | The goods receipt is reversed between simulation and execution; the execution returns `plan_hash_mismatch`, nothing posts, and the decision is `require_human` (`auto_post_plan_changed`). | `must_reject:plan_hash_mismatch` | ADR-0065.R7 (R242) |
| `EC-225` | `wrong_auto_post_suspends_document_type` | The owner confirms one auto-posted invoice as wrong; every enabled purchase invoice auto-post rule's evidence is outdated, `auto_post_suspended` is raised, and the next clean invoice gets `require_human`. | `must_succeed` | ADR-0065.R16 |
| `EC-226` | `gateway_fail_closed` | A decision table in force has no row for one case, and another case reads a setting with no value in force; both get `require_human`. | `must_succeed` | ADR-0065.R5, ADR-0065.R7 (R239), ADR-0065.R9 |
| `EC-227` | `advisor_drafts_only` | The advisor proposes thresholds and a table from six months of invoices; it drafts a table version and a change proposal and cannot submit, approve or enable them; its tool list excludes held-out cases. The advisor is a Phase 2 agent type (R232). | `must_succeed` | ADR-0065.R17 (R250-R252), ADR-0065.R18 |
| `EC-228` | `duplicate_invoice_rejected` | An agent drafts an invoice whose supplier invoice key is already posted; the simulation returns `duplicate_external_document`, the decision is `reject`, and the draft stays for a person. | `must_succeed` | ADR-0065.R4, ADR-0065.R19 |

## Settings

Storage of every key: `setting_value`; change effect `immediate`.

| Key | Value type | Scopes | Core default | Bounds, direction | Used by |
| --- | --- | --- | --- | --- | --- |
| `automation.dispatch_paused` | boolean | `company` | `false` | `true_tighter` | R221, R12 |
| `automation.max_active_rules` | integer | `company` | 200 | 1..1000, `lower_tighter` | R221 |
| `automation.replay_window_days` | integer | `company` | 30 | 7..90, `higher_tighter` | R221, R33 |
| `automation.replay_min_events` | integer | `company` | 20 | 0..1000, `higher_tighter` | R221, R36 |
| `automation.breaker_failures` | integer | `company`; `rule_version` | 5 | 1..50, `lower_tighter` | R223, R29 |
| `automation.breaker_window_minutes` | integer | `company`; `rule_version` | 60 | 5..1440, `higher_tighter` | R223, R29 |
| `automation.breaker_consecutive` | integer | `company`; `rule_version` | 20 | 3..200, `lower_tighter`; never below `automation.breaker_failures` | R223, R29 |
| `automation.max_executions_per_rule_per_hour` | integer | `company`; `rule_version` | 500 | 10..10000, `lower_tighter` | R224, R30 |
| `agents.<agent_type>.wake_up_mode.<kind>` | enum `always`, `by_rule`, `off` | `agent_type` | `always` | `order:always<by_rule<off` | R214 |
| `auto_post.max_error_rate` | percent | `company` | 1 | 0.1..2, `lower_tighter` | R210, R230, R247 |
| `artifacts.<function_or_kind>.max_window_days` | integer | `company` | 90 | 28..365, `lower_tighter` | R211 |
| `artifacts.cash.match_bank_line.min_backtest_cases` | integer | `company` | 200 | 50..5000, `higher_tighter` | R211 |
| `artifacts.cash.match_bank_line.min_live_cases` | integer | `company` | 100 | 30..5000, `higher_tighter` | R211 |
| `auto_post.<document_type>.mode` | enum `off`, `shadow`, `live` | `company` | `off` | `order:live<shadow<off` | R233, R245 |
| `auto_post.confirmation_cadence` | enum `period`, `week`, `day` | `company` | `period` | `order:period<week<day` | R243 |
| `cash.auto_post.accept_llm_originated_rules` | boolean | `company` | `false` | `false_tighter` | R254 |

R204 names `artifacts.proposal_ttl_days` (30), the pattern `artifacts.<function code or kind>.<threshold>` and the per-function declarations `reevaluation_window_days`, `reevaluation_max_window_days` and `reevaluation_min_cases`; `settings.csv` holds no row for them. The other keys listed in R254 are settings of `policy` (ADR-0065.R8). `artifacts.proposal_ttl_days` replaces `change_proposal_ttl_days` for the proposals of `SetArtifactVersionState` (ADR-0059.R13).

## UI annotations

The sources state no floorplan, title, facet, field annotation or tile of ADR-0077 for the module. Work item kinds of module `automation` whose rows are in this chunk:

| Kind | Subject table | Owner | Due | Resolution | Rule |
| --- | --- | --- | --- | --- | --- |
| `artifact_function_changed` | `artifact_promotion_evidence` | `named_by_raiser` | `days:5` | `person` | R203 |
| `automation_rule_rate_limited` | `automation_rule` | `subject_owner:owner_user_id` | `days:1` | `person` | R224 |

Chunk 1 holds the rows of `artifact_demoted`, `artifact_invalidated`, `artifact_reference_deprecated` (R203), `automation_notice`, `automation_owner_scope_narrowed` and `automation_rule_disabled`. None of the kinds is agent-resolvable. Kinds of `policy` raised under the rules of this chunk: `auto_post_review`, `auto_post_suspended`, `auto_post_unconfirmed`. The authorization area `automation` ("Automation evidence", under `administration`) holds automation executions and replays at `read`, `CreateArtifactEvidence` at `full`, and artifact evidence, transitions and monitor snapshots at `read`.

## Conflicts

CONFLICT ADR-0063.R10: ADR-0065.R16 governs (accepted 2026-11-21, later): a suspension covers every enabled rule version of the document type, not one rule, and later candidates get `require_human` (`auto_post_evidence_mismatch`); R213 states it. Other conflicts: see chunk 1.

## Proposed (not law)

None

## Trace

| Source | Where |
| --- | --- |
| ADR-0059.R27 | R201 |
| ADR-0059.R28 | R202-R206 |
| ADR-0063.R10 | R210-R213 |
| ADR-0063.R11 | R214-R217 |
| ADR-0063.R20 | R220-R222 |
| ADR-0063.R21 | R223-R225 |
| ADR-0065.D0 | R230 |
| ADR-0065.R1 | R231 |
| ADR-0065.R1.N1 | R232 |
| ADR-0065.R3 | R233-R237 |
| ADR-0065.R7 | R238-R243 |
| ADR-0065.R13 | R244 |
| ADR-0065.R14 | R245-R249 |
| ADR-0065.R17 | R250-R252 |
| ADR-0065.R21 | R253 |
| ADR-0065.R22 | R254 |
| ADR-0066.R6 | R260, R261 |
| ADR-0066.R7 | R262 |
| ADR-0066.R15 | R263, R264 |
