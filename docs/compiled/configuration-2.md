Module: configuration    Chunk: 2 of 3    Source ADRs: ADR-0058, ADR-0059
Build step(s): 1, 3    Generated from index: 30d5706    Compiled by: Claude Fable 5.2, 2026-11-21

# `configuration` compiled spec, chunk 2: activation, commands, catalog rows, levels, parameter sets, kinds and states

## Purpose

`configuration` (layer 2) owns the company's versioned artifacts: automation rules, decision tables and parameter sets, with their lifecycle, evidence and monitoring tables. This chunk states the activation of a version through a change proposal, what is left for after Phase 1, the commands and catalog rows of ADR-0058, and from ADR-0059 the levels, the module split, the tunable parameter declarations, parameter sets, the kinds with their ladders and the lifecycle states. Rule content, the graph check, decision tables and replay are in chunk 1; evidence, promotion, monitoring and golden cases are in chunk 3. `configuration` imports no module of a higher layer: `automation` (layer 5) runs the checks that read their data through the hook `artifact_checks`.

## Entities and tables

DDL: `docs/design/DS-28-34-configuration-artifacts.sql`.

| Table | Meaning | Key | Parent | Owner |
| --- | --- | --- | --- | --- |
| `parameter_set` | Company data; one per company and tunable function, with the pointers to the version in force and the version in shadow (R234) | `id`; (`company_id`, `function_code`) unique; (`company_id`, `id`) | `company` | `configuration` |
| `parameter_set_version` | One version of a parameter set with the lifecycle columns; immutable once out of draft (R234, R247) | `id`; (`parameter_set_id`, `version`) unique; (`company_id`, `id`) | `parameter_set` | `configuration` |
| `parameter_set_value` | One parameter value of a version, with the copied type, default and bounds (R234) | `id`; (`parameter_set_version_id`, `parameter_code`) unique | `parameter_set_version` | `configuration` |
| `artifact_shadow_outcome` | The outcome of a version in shadow beside the outcome of the version in force (or of the core defaults), per case (R227, R247) | `id`; (`artifact_version_id`, `case_table`, `case_id`) unique | `company` | `configuration` |

Owned tables with their rows in chunk 1: `automation_rule`, `automation_rule_version`, `automation_execution`, `automation_scope_skip`, `decision_table`, `decision_table_version`, `decision_table_row`, `configuration_state`. Owned tables with their rows in chunk 3: `artifact_transition`, `artifact_promotion_evidence`, `golden_case_label`, `artifact_monitor_snapshot` (R224, R227).

Reads: `company`, `user_account`, `partner_item` (`master_data`); `change_proposal`, `agent_run`, `agent_type`, `agent_promotion_evidence`; `purchase_invoice`; `bank_matching_rule`, `bank_statement_line` (`cash`); `policy_rule_version` (`policy`); `outbox_event`, `audit_record`.

## Commands and queries

Authorization leaf `configuration` (catalog `authorization-areas.csv`, a function under `administration`, module `configuration`): automation rules, decision tables and parameter sets, with drafts at `edit`; `ConfirmAutomationRuleOwnership` by the named owner; `SetArtifactVersionState`, `SetArtifactCurrentVersion`, `DisableAutomationRule` and `EnableAutomationRule` at `full`; `RecordGoldenCaseLabel` needs the approve flag on the labelled function's own leaf. The level of a verb is the catalog's (`Create`, `Update`, `Delete`: `edit`; `List`, `Get`, `Evaluate`: `read`). The sources of this chunk state no input schema and no emitted event for these commands, and bind no error code to one of them except where a row says so.

| Name | Actor and authorization | Input | Effect | Events | Error codes |
| --- | --- | --- | --- | --- | --- |
| `CreateAutomationRule`, `UpdateAutomationRule` | leaf `configuration`, `edit`; an owner change of a rule with a version in force is `is_proposal_bound` | code, name, owner | Effect class `master_data_change`; change-tracked (R207); an owner change clears the recorded consent (ADR-0058.R9) | not stated | not stated |
| `ConfirmAutomationRuleOwnership` | only the named owner, in their own session; leaf `configuration` | not stated | Effect class `other`; records the owner's consent in `owner_confirmed_at` and `owner_confirmed_user_id` (R207; ADR-0058.R9) | not stated | not stated |
| `CreateAutomationRuleVersion`, `UpdateAutomationRuleVersion`, `DeleteAutomationRuleVersion` | leaf `configuration`, `edit`; `is_draft_only`; an agent type version may declare them | not stated | Effect class `other`; drafts only (R207) | not stated | not stated |
| `CreateDecisionTable`, `UpdateDecisionTable` | leaf `configuration`, `edit` | not stated | Effect class `master_data_change` (R207) | not stated | not stated |
| `CreateDecisionTableVersion`, `UpdateDecisionTableVersion`, `DeleteDecisionTableVersion` | leaf `configuration`, `edit`; `is_draft_only`; an agent type version may declare them | not stated | Effect class `other`; drafts with their rows (R207) | not stated | not stated |
| `DisableAutomationRule` | leaf `configuration`, declared minimum level `full`; the breaker and the owner consumer run it under their registered permission, not the owner's | reason | Effect class `other` (R207); sets `disabled_at` and `disabled_reason` and raises `automation_rule_disabled` (ADR-0058.R9, ADR-0058.R16) | not stated | not stated |
| `EnableAutomationRule` | a person; leaf `configuration`, declared minimum level `full` | not stated | Effect class `other` (R207); re-enables the same current version after the graph check and validity of ADR-0058.R15, through the pure validators and the hook `artifact_checks`; resolves `automation_rule_disabled` (R212; ADR-0058.R16) | not stated | `automation_rule_cycle`, `automation_depth_exceeded`, `artifact_invalid` |
| `ListDecisionTable`, `GetDecisionTable`, `EvaluateDecisionTable` | query; leaf `configuration`, `read`; an agent type version may declare them | not stated | Reads decision tables (R207) | none | not stated |
| `GetArtifactValidation` | query; leaf `configuration`, `read`; an agent type version may declare it | a draft | Returns the findings of ADR-0058.R5, ADR-0058.R9, ADR-0058.R14, ADR-0058.R15, ADR-0058.R19, ADR-0058.R20 and ADR-0058.R22 for a draft, through the hook for the owner's scope (R207) | none | not stated |

Commands and queries of module `automation` that R208 lists: `RaiseAutomationWorkItem`, `RecordAutomationExecution`, `RunArtifactUpgradeCheck`, `RunAutomationOwnerScopeCheck`, `ListAutomationRule`, `GetAutomationRule`, `ListAutomationExecution`, `GetAutomationReplay`; leaf `automation` (module `automation`: executions and replays at `read`, `CreateArtifactEvidence` at `full`).

The rows of `SetArtifactVersionState` and `SetArtifactCurrentVersion` and of the other commands of ADR-0059.R27 are in chunk 3; on the activation path of R201 to R205 `SetArtifactVersionState` returns `approver_is_submitter`, `segregation_of_duties`, `artifact_evidence_stale` and `artifact_invalid`.

Contract functions, hooks and jobs that are not registered commands: `configuration.contract.get_parameters(company, function_code)` (R236); the hook `artifact_checks`, declared by `configuration`, registered by `automation` (R225); the hook `artifact_in_force_changed`, declared by `configuration`, registered by `policy` (R229); the contract functions `backtest`, `compare` and `monitor` of each owning module (R226); `policy`'s `auto_post_eligibility` and `mark_auto_post_evidence_outdated(company, function_code, by_id)` (R228, R229).

Error codes of R210, R231 and R234 that the rules of this chunk bind to no named command: `automation_depth_exceeded`, `automation_owner_not_confirmed`, `decision_no_match`, `decision_input_out_of_domain`, `decision_table_version_in_use`, `automation_command_not_allowed`, `automation_action_not_allowed`, `automation_owner_scope_insufficient`, `automation_rule_cycle`, `decision_table_overlap`, `artifact_tests_failed`, `artifact_version_immutable`, `parameter_order_violated`, `parameter_out_of_bounds`.

## Rules

### Activation through a change proposal

R201. `SetArtifactVersionState` (ADR-0059.R13) to `active` or `shadow` is `is_proposal_bound` and runs only from an approved change proposal (ADR-0029.R5); the proposal names the evidence. A kind that has the stage `assisted` is raised to it the same way, and a raise outside an approved proposal returns `proposal_required` (ADR-0059.R13).
Source: ADR-0058.R24

R202. Validation on creation of the proposal: the version is valid against the current registry and for the owner (ADR-0058.R9), its tests pass, the graph check of ADR-0058.R15 passes, the owner has consented, and its evidence is sufficient; anything else is refused. A pinned decision table version that is not `assisted` or `active` is accepted only when an earlier item of the same proposal raises it to one of them.
Source: ADR-0058.R24, ADR-0058.R24.N1

R203. Who: a person submits; a person who is neither the submitter (`approver_is_submitter`) nor the version's drafter nor the human its drafting run or consumer acted for (`segregation_of_duties`) approves; `approver_is_submitter` holds also in the small-company mode (ADR-0059.R13). The approver holds the target permissions of every item (ADR-0043.R12). With the role templates of ADR-0054.R11: the owner, the chief accountant and the sales, purchasing and production managers draft and submit; the owner and the chief accountant approve, never an activation they submitted or drafted, so the owner's drafts go to the chief accountant and the chief accountant's to the owner.
Source: ADR-0058.R24, ADR-0058.R24.N1

R204. Execution, under the company's `configuration_state` lock, checks that the version's content hash, the registry version and the current version still equal the evidence's (`artifact_evidence_stale`), repeats validity and the graph check (ADR-0058.R15), then moves the pointer and sets `effective_from`.
Source: ADR-0058.R24

R205. One change proposal may activate a decision table version and the rule version that pins it. Its items are one `SetArtifactVersionState` per version, the table versions first, each naming its own evidence. Execution runs every item in one transaction under the company's `configuration_state` lock, so both versions come into force or neither: a rule item that would run before its table is refused with `artifact_invalid` and the whole execution rolls back (ADR-0058.R20).
Source: ADR-0058.R24.N1

### After Phase 1

R206. After Phase 1 (decision 10), each by its own decision:
- an expression language for conditions, a non-Turing-complete subset of CEL or FEEL with static types (W9);
- durable orchestration with versions pinned at start, only when two real long-running processes need it, which is the justification test (W10);
- tenant environments and promotion pipelines for configuration (W11), and a visual designer over the same artifacts (W12);
- user-defined tables (spec 16 level 1).
User-defined fields without custom tables are in Phase 1: ADR-0074.R8 to ADR-0074.R12 give them a minimal seam, a definition table and a `custom_values` column on chosen tables.
Source: ADR-0058.R26, ADR-0058.R26.N1

### Commands and queries of ADR-0058

R207. Commands and queries of module `configuration`, with effect class and flags:
- `CreateAutomationRule`, `UpdateAutomationRule`: `master_data_change`; code, name, owner; change-tracked; an owner change of a rule with a version in force is `is_proposal_bound`.
- `ConfirmAutomationRuleOwnership`: `other`; only the named owner, in their own session.
- `CreateAutomationRuleVersion`, `UpdateAutomationRuleVersion`, `DeleteAutomationRuleVersion`: `other`; drafts only; `is_draft_only`.
- `CreateDecisionTable`, `UpdateDecisionTable`: `master_data_change`.
- `CreateDecisionTableVersion`, `UpdateDecisionTableVersion`, `DeleteDecisionTableVersion`: `other`; drafts with their rows; `is_draft_only`.
- `DisableAutomationRule`, `EnableAutomationRule`: `other`; declared minimum level `full`; the breaker and the owner consumer run Disable under their registered permission.
- `ListDecisionTable`, `GetDecisionTable`, `EvaluateDecisionTable`: query.
- `GetArtifactValidation`: query; the findings of ADR-0058.R5, ADR-0058.R9, ADR-0058.R14, ADR-0058.R15, ADR-0058.R19, ADR-0058.R20 and ADR-0058.R22 for a draft, through the hook for the owner's scope.
Source: ADR-0058.R27

R208. Commands and queries of module `automation`, with effect class and flags:
- `RaiseAutomationWorkItem`: `other`; `is_internal_only`, `is_automation_allowed`, `is_draft_only`; checked by the owner's read right on the subject.
- `RecordAutomationExecution`: `other`; `is_internal_only`.
- `RunArtifactUpgradeCheck`: `other`; system job at upgrade; `is_internal_only`.
- `RunAutomationOwnerScopeCheck`: `other`; daily system job (ADR-0058.R9); `is_internal_only`, leaf `automation`.
- `ListAutomationRule`, `GetAutomationRule`, `ListAutomationExecution`, `GetAutomationReplay`: query; filtered by the reader's scope and classes (ADR-0058.R11); the replay runs no action.
Source: ADR-0058.R27

R209. Evidence, state and pointer commands are those of ADR-0059.R27. All commands of R207, R208 and ADR-0059.R27 are on no agent tool list, except the draft commands and the queries, which an agent type version may declare (ADR-0050.R29). None of them is `is_automation_allowed`, apart from the flag R208 gives `RaiseAutomationWorkItem`.
Source: ADR-0058.R27

### Catalog rows of ADR-0058

R210. Error codes (DS-04). Precondition: `automation_depth_exceeded`, `automation_owner_not_confirmed`, `decision_no_match`, `decision_input_out_of_domain`, `decision_table_version_in_use`, `artifact_tests_failed`, `artifact_version_immutable`. Permission: `automation_command_not_allowed`, `automation_action_not_allowed`, `automation_owner_scope_insufficient`. Validation: `automation_rule_cycle`, `decision_table_overlap`, `artifact_invalid`.
Source: ADR-0058.R28

R211. Check results: `automation_same_target_warning`, `automation_schedule_feedback`, `automation_owner_scope_limited`, `replay_not_reconstructable`, `decision_table_gap`, `decision_table_completeness_not_proven`.
Source: ADR-0058.R28

R212. Work item kinds of module `automation`:
- `automation_task` and `automation_notice`: subject `automation_execution`; owner and due date named by the raising rule, the kind rule `named_by_raiser`.
- `automation_rule_disabled`: subject `automation_rule`; owner named by the raiser: the rule's owner, or `company_owner` for `owner_inactive` and when the owner can no longer open the company; `days:1`; resolved by `EnableAutomationRule`.
- `automation_owner_scope_narrowed`: subject `automation_rule`; owner the rule's owner, `subject_owner:owner_user_id`; `days:5`; resolved by a person.
- `artifact_invalidated` and `artifact_reference_deprecated`: subject `artifact_transition` (ADR-0059.R28).
Source: ADR-0058.R28

R213. Settings: `automation.breaker_failures` (core default 5) and `automation.breaker_window_minutes` (core default 60), company settings, each with an optional override in a rule version's content; ADR-0063.R21 sets their bounds and adds `automation.breaker_consecutive` and the flood guard `automation.max_executions_per_rule_per_hour` beside them. Secret, per company, in the deployment's secret store: `automation.value_hmac_key`.
Source: ADR-0058.R28

R214. Authorization leaves under Administration (ADR-0054.R7): `configuration` (module `configuration`: automation rules, decision tables and parameter sets, ownership confirmation; state and pointer moves, Disable and Enable at `full`) and `automation` (module `automation`: executions, replays, evidence; `CreateArtifactEvidence` at `full`).
Source: ADR-0058.R28

R215. Lock: the company's `configuration_state` row joins class 3 of the lock order of ADR-0027.R10.
Source: ADR-0058.R28

R216. Invariants: block `INV-670` to `INV-699`, areas `safety` and `platform`. Of ADR-0058: `INV-670`, `INV-671`, `INV-672`, `INV-673`, `INV-674`, `INV-675`, `INV-676`, `INV-686`, `INV-687`. Of ADR-0059: `INV-677`, `INV-678`, `INV-679`, `INV-680`, `INV-681`, `INV-682`, `INV-683`, `INV-684`, `INV-685`. Edge cases: block `EC-156` to `EC-169`. Of ADR-0058: `EC-156`, `EC-157`, `EC-158`, `EC-159`, `EC-160`, `EC-161`, `EC-162`, `EC-167`. Of ADR-0059: `EC-163`, `EC-164`, `EC-165`, `EC-166`, `EC-168`. Each statement is its catalog row, written once in the module (sections 5 and 6).
Source: ADR-0058.R28

R217. Lab check `t22_workflows.py` (validation lab), pure functions: condition evaluation by type and operator; the gate-field allowlist; the allowed actions, the permission per action and the by-design skips; owner scope and field classes, the scope count and its check result, the daily owner check on the stored cells, and reader filtering with omission; cycle detection over rule graphs with discriminator nodes, undeclared emit values and consumer edges (including the review's probe, which must fail activation); the static depth and the runtime cap; the same-rule-same-target guard; field-change triggers; idempotency keys; the circuit breaker in a window and in a row; independent actions and their outcomes; evaluate-all-then-act order independence; decision tables under both hit policies with pairwise overlap against brute force, box-subtraction completeness that never claims a false gap and stops at its cap (ADR-0058.R18), out-of-domain inputs and no-match handling, and aggregators against shuffled rows; the replay diff. With `--load`, on all DDL from `load_all.py`: versions inserted only as drafts and immutable once out of draft, the allowed transitions, frozen rows, pointers only to versions in force and cleared on retirement, the owner's confirmation tied to the current owner, pinned table versions active and neither retired nor demoted while pinned, the depth checks on executions, events and audit records, the execution keys, and forced row-level security. The result is recorded as the next lab finding of the validation lab README.
Source: ADR-0058.R29

R218. Example of a rule: `large_order_warehouse_alert` has the trigger `SalesOrderApproved` (a transition, so no watched fields), the condition (`amount_company`, `gt`, a threshold) on the event type's condition source, where `amount_company` is a gate field with no field class, and the action `raise_work_item` with owner `role:warehouse_keeper` (the role template `warehouse_keeper`) and a due date in 1 business day. Its action runs `RaiseAutomationWorkItem` with the key `automation:<rule version>:<event>:1` at depth 1; a second match in the same chain is recorded `skipped_same_target`. A `notify` action emits `WorkItemRaised[automation_notice]`, a different trigger node than `WorkItemRaised[automation_task]`.
Source: ADR-0058.W

### Levels, drafting and the lifecycle in short

R219. Every L1 and L2 artifact, whoever drafted it, moves draft → backtested → shadow → assisted → active, and can be retired. The version in force is a pointer, and rollback moves the pointer back. Each kind, and each tunable function, declares which of the middle stages it needs. These accepted commands change with this lifecycle: `CreateReportDefinition` and `UpdateReportDefinition` become draft-only commands (ADR-0059.R11), and bank matching rules become draft versions raised by a change proposal (ADR-0059.R10).
Source: ADR-0059.D0

R220. The levels (decision 11 of the author's decisions of 2026-11-15):
- L1, parameter sets (R230 to R239; ADR-0059.R5 to ADR-0059.R8).
- L2, rules as data (R240 to R246; ADR-0059.R10, ADR-0059.R11): decision tables (ADR-0058.R18 to ADR-0058.R20), matching rules, pricing and validation rules, report definitions (ADR-0049.R11), analysis definitions (artifact kind `analysis_definition`, a declarative spec over the analysis layer that its own ADR designs), and extraction mapping rules (artifact kind `extraction_mapping`, for the intake design).
- L3, code (ADR-0059.R24).
Source: ADR-0059.R1

R221. Who drafts: people; deterministic proposal consumers (such as that of ADR-0051.R19); and agent runs whose agent type version declares the draft commands (`Create<Kind>Version`, `is_draft_only`) on its tool list, called drafting agent types. An agent type that drafts parameter sets is designed by its own ADR, as ADR-0051.R29 does for later agents. Phase 1 has no tuning agent: drafts come from the stored-resolution proposals of `bank_matching` and `purchase_invoice`, from the parameter and lead-time proposals of `planning`, and from the assistant in `act` mode on request. Phase 1 has no advisor: `auto_post_advisor` is a Phase 2 agent type. Every draft is backtested and passes this lifecycle before it runs (ADR-0078.R8).
Source: ADR-0059.R1, ADR-0059.R1.N1

R222. The model chooses, code computes. Candidate values, tolerances and rule rows are computed by code (a grid search over the declared bounds and order constraints, a token count, a replay) on the drafting window without the held-out cases (ADR-0059.R16). An LLM step only chooses among code's candidates and writes the explanation (ADR-0051.R1; Principle 13). Its explanation passes the number check of ADR-0050.R36.
Source: ADR-0059.R1

R223. Outside the lifecycle, for now: item mappings (`partner_item`), planning parameters and lead times (ADR-0024.R23), putaway rules and count plans (ADR-0023.R21). Each changes one record through a change proposal carrying that case's evidence (ADR-0051.R21, ADR-0051.R24), a person sees its effect on that record, and a wrong one is corrected per record; they join when their owners add versions. Partner matching (the duplicate search of ADR-0052.R17) is a setting unless a company opts in (ADR-0059.R8), and item matching's fuzzy constants stay agent type version constants (ADR-0059.R7).
Source: ADR-0059.R1

### Modules, contracts and hooks

R224. `configuration` (layer 2; ADR-0022.R2) owns `parameter_set`, `parameter_set_version`, `parameter_set_value`, `artifact_transition`, `artifact_promotion_evidence`, `artifact_shadow_outcome`, `golden_case_label` and `artifact_monitor_snapshot` (DDL in `DS-28-34-configuration-artifacts.sql`), the contract function `get_parameters`, and the pure lifecycle and parameter checks.
Source: ADR-0059.R2

R225. `automation` (layer 5, ADR-0058.R1) owns `CreateArtifactEvidence`, `RunArtifactMonitor` and the queries of ADR-0059.R27 that read layer 3–4 data; the commands of `configuration` that need its checks call them through the hook `artifact_checks` of ADR-0058.R1.
Source: ADR-0059.R2

R226. Owning modules. The module that owns a tunable function or an L2 kind registers, with its declaration, these pure functions in its contract: `backtest` (the function under one parameter set and another, or under one rule version and another, over a window of its own resolved history, inputs as of decision time), `compare` (an outcome against a person's final result) and `monitor` (decisions and overrides over a window). `automation` calls them; for the bank cascade they live in `cash`, as `GetAutoPostShadowEvaluation` already does (ADR-0051.R18).
Source: ADR-0059.R2

R227. No new table per kind for lifecycle or evidence: one transition log (`artifact_transition`), one evidence table (`artifact_promotion_evidence`) and one shadow table (`artifact_shadow_outcome`) serve every kind. A generic `artifact_promotion_evidence` is used rather than `agent_promotion_evidence`, whose columns (agent type, behavior hash, seat models) belong to agent types; the agent table stays as it is.
Source: ADR-0059.R2

R228. The auto-post hook. `policy`'s evidence hook of ADR-0043.R14 gains a second function, `auto_post_eligibility`, which `cash` registers and `app` wires: for a `system` posting of a cascade draft it answers whether the draft's line meets ADR-0059.R6, and the policy floor gives `human_post` when it does not. So `policy` imports no layer-4 module.
Source: ADR-0059.R2

R229. The outdated marker's writer. `policy`'s contract gains `mark_auto_post_evidence_outdated(company, function_code, by_id)`, which sets `shadow_evidence_outdated_by` on every enabled rule version whose stored evidence names that function (`EnablePolicyRule` stores the function code with the hash). `configuration` declares the hook `artifact_in_force_changed`, which `policy` registers and `app` wires (the pattern of ADR-0022.R2); `configuration` calls it inside the transaction of every pointer move, retirement and failed re-evaluation of a parameter set (`automation` reaches it through `configuration`'s contract), so no module imports `policy` sideways or up. The hook is also called when the decision table version in force at the auto-post gateway's decision point changes, is demoted or is rolled back, so the gateway evidence that names the earlier version is marked outdated in the same transaction (ADR-0059.R6.N1; ADR-0065.R9, ADR-0065.R14).
Source: ADR-0059.R2

### Tunable parameter declarations

R230. A deterministic function may declare in the registry (ADR-0008.R1): its `function_code` (such as `cash.match_bank_line`), its `function_version` (semver, bumped by any change of its code or declaration), its authorization leaf (for golden labels, ADR-0059.R22), its case tables (the rows its decisions are about) and its case-reference paths (columns of other tables that point at a case directly, or through a declared path of foreign keys, such as a payment line through its payment to the bank statement line), both for held-out filtering (ADR-0059.R16). A CI check derived from the schema refuses a foreign key to a declared case table that is not a declared case-reference column, and a property test checks that a filtered query returns no row tied to a held-out case. Each L2 kind declares the same.
Source: ADR-0059.R3

R231. The declaration of a tunable function also holds:
- each parameter: `code`, type (`integer`, `decimal`, `score`, `percent`, `days`), core default, minimum and maximum, `is_nullable` (null means off), and `is_safety_cap`: a cap whose maximum is the core default, which is never off and can only be lowered;
- order constraints between parameters (`a > b`), checked with the bounds (`parameter_order_violated`);
- its stages and thresholds (ADR-0059.R18), with the small-company minimums below which no company may set them;
- its synthetic golden set (ADR-0050.R39), which every parameter set version must pass at the function's threshold.
Source: ADR-0059.R3

R232. Not tunable: hard floors, guards and shapes (the reference-token shape of ADR-0048.R9, the routing switch, taint, the rule that a tied match never acts), and anything spec 03 fixes. Bounds and constraints are part of the declaration and change only by a release.
Source: ADR-0059.R3

### Parameter sets

R234. Shape (company data). One `parameter_set` per company and function, with `owner_user_id`, `current_version_id` and `shadow_version_id`. A `parameter_set_version` carries the lifecycle columns of R247 to R250 and `function_version`. Its `parameter_set_value` rows copy each declared parameter's type, default and bounds at that function version, and the database refuses a value outside them (`parameter_out_of_bounds`), a safety cap above its default, or an empty safety cap.
Source: ADR-0059.R4

R235. Hashes. `parameters_hash` is the SHA-256 of the canonical JSON (ADR-0006.R13) of (function code, the values sorted by code); it does not include the function version, which every decision records beside it. A version's `content_hash` covers its values with their copied types, defaults and bounds, sorted by code, and its function version.
Source: ADR-0059.R4

R236. Effective values. `configuration.contract.get_parameters(company, function_code)` returns the current version's values, or the core defaults when there is none, with `parameters_hash`, the function version, the parameter set version and its state (`core_default`, `assisted`, `active`). Every decision the function makes records all of these (in its own row, or its derivation trace), so each outcome names the parameters behind it and whether they could act.
Source: ADR-0059.R4

R237. Only through the lifecycle: values change only by a new version that passes R247 to R250 and ADR-0059.R13 to ADR-0059.R19. A small company's evidence window may reach `artifacts.<function_or_kind>.max_window_days` (default 90, at most 365): a longer window, never a lower bar (ADR-0063.R10).
Source: ADR-0059.R4, ADR-0059.R4.N1

R238. A function release (a new `function_version`) leaves the parameters hash, and so the auto-post binding of ADR-0059.R6, unchanged. `RunArtifactMonitor` writes a re-evaluation for every company that uses the function: the parameters in force, a version or the core defaults, under the new function version over the window of their last evidence (for core defaults, the window of the auto-post rule's evidence, else the function's declared `reevaluation_window_days`, 60 for `cash.match_bank_line`, two statement months as ADR-0051.R18 counts), stored as evidence of stage `reevaluation`; for core defaults that row names the function code and the company and no version. It raises `artifact_function_changed`, one item per owner with the owner in its key, for the parameter set's owner (`company_owner` under core defaults) and for the owner of each auto-post rule that depends on it, with the re-evaluation as subject. A changed core default changes the core defaults' hash, which the upgrade check of ADR-0058.R25 reports.
Source: ADR-0059.R4

R239. The re-evaluation of R238 passes on the acting figure only: of the proposals at or above the auto-post rule's floor and below its maximum, at least the 99% of ADR-0051.R18 equal people's final results, and none was drafted to another partner. A pass leaves auto-post as it is; a failure marks the dependent rule's evidence outdated (ADR-0059.R6). The function declares `reevaluation_min_cases` (50 for `cash.match_bank_line`), counted on acting proposals only; with fewer the result is `too_few_cases` and the evidence is left unmarked. The monitor then widens the window in one step to the smallest window that holds `reevaluation_min_cases` acting proposals, capped at the function's declared `reevaluation_max_window_days` (180 for the cascade), and judges on it, so a small company's release is still judged; while the cap holds too few it repeats the attempt daily until a verdict is possible or newer evidence replaces it. If the maximum window still holds too few acting proposals, the evidence stays unmarked and the owner's `artifact_function_changed` item records that the release could not be judged and stays open for a person.
Source: ADR-0059.R4

### Kinds and ladders

R240. Each L2 kind declares its stages, evidence function, comparator and thresholds. Kind `parameter_set`: owner the function's module; stages as the function declares, for `cash.match_bank_line` draft, backtested, shadow, assisted, active; backtest evidence: the function under both sets on a later window, and the golden sets; live comparison: shadow outcomes against people's final results.
Source: ADR-0059.R9

R241. Kind `decision_table`: owner `configuration`; stages draft, backtested, active, with shadow optional; backtest evidence: validation, tests and the replay diff (ADR-0058.R23); live comparison: shadow outcomes against the current version's.
Source: ADR-0059.R9

R242. Kind `automation_rule`: owner `configuration`; stages draft, backtested, active, with shadow optional; backtest evidence as for `decision_table`; live comparison: would-be actions against the current version's.
Source: ADR-0059.R9

R243. Kind `matching_rule`: owner `cash` (`bank_matching_rule`); stages draft, backtested, assisted (suggest), active (confirm), with shadow optional; backtest evidence: later lines carrying the token, against people's matches; live comparison: suggest-mode drafts posted unchanged.
Source: ADR-0059.R9

R244. Kinds `report_definition` and `analysis_definition`: owners `reporting` and the analysis layer; stages draft, backtested, active; backtest evidence: a render of the draft version on a closed period, with at least one cell a person checked by hand; no live comparison.
Source: ADR-0059.R9

R245. Kind `extraction_mapping`: owner the intake module; stages draft, backtested, shadow, active; backtest evidence: fields on a later window of documents against people's corrections; live comparison: shadow extractions against people's corrections.
Source: ADR-0059.R9

R246. Every ladder needs `backtested`: a version leaves draft only to it. Pricing and validation rules that exist as company data (promotions, ADR-0047.R17; configuration rules, ADR-0046) adopt the lifecycle when their owners add the version columns; until then they keep their own versioning and change proposals.
Source: ADR-0059.R9

### States, pointers and moves

R247. States of an artifact version (A1; decision 12):
- `draft`: editable; validation and tests on demand. Versions are inserted only as drafts.
- `backtested`: content frozen; valid, tests passing, backtest evidence sufficient.
- `shadow`: computed beside the version in force on live cases; its outcomes are recorded in `artifact_shadow_outcome` (automation rules: `automation_execution` in mode `shadow`) and never shown or used.
- `assisted`: in force where a person decides (drafts, proposals, suggestions), never where the system acts without a person (auto-post, confirm-mode matches, unattended actions).
- `active`: in force everywhere, acting paths included, within policy and the hard floors.
- `retired`: final; never in force again.
Source: ADR-0059.R12

R248. Pointers. `current_version_id` names the version in force (state `assisted` or `active`; null means the core defaults, or no artifact); `shadow_version_id` names at most one version in shadow. A version's state says the furthest it was promoted, so several versions may be `active`; the pointer says which is in force.
Source: ADR-0059.R12

R249. Allowed moves, held by triggers: from `draft` only to `backtested`; from there forward to a later state (skipping only stages the kind or function does not require, a command check); `assisted` or `active` back to `shadow` (demotion); any state except `draft` to `retired`; never back to `draft`, never out of `retired`. A version in force is demoted only after the pointer has moved off it. Leaving `shadow` clears the shadow pointer that names the version, and retiring clears both pointers that name it.
Source: ADR-0059.R12

R250. The content hash of a version is defined per kind by ADR-0058.R21, and for parameter sets by R235. The agent-type ladder of ADR-0050.R14 (off, shadow, assisted) is the same pattern for code artifacts. For agent types, where the ladder says "shadow", Phase 1 uses the evaluation of ADR-0078.R6 (the evaluation set with the real provider, and replay); the artifact states of R247 are unchanged.
Source: ADR-0059.R12, ADR-0059.R12.N1

## Invariants

Statements are those of `invariants.csv`; each row stands once in the module, here when its catalog source names a rule of this chunk. First step 5 for each.

| Invariant | Name | Check point | Statement | Protects |
| --- | --- | --- | --- | --- |
| `INV-678` | `artifact_pointers_eligible` | day | Every current pointer names a version of its artifact in state assisted or active (automation rules: active), and every shadow pointer a version in shadow. | R248, R249 |
| `INV-681` | `parameters_within_bounds` | day | Every parameter value lies within the bounds and order constraints its function declared at the version's function version, and no safety cap is null or exceeds its core default. | R231, R234 |

Named by R216, with their rows in the chunk of the catalog source rule: `INV-670`, `INV-672`, `INV-673`, `INV-674`, `INV-675`, `INV-676`, `INV-677`, `INV-686`, `INV-687` (chunk 1); `INV-679`, `INV-680`, `INV-683`, `INV-684`, `INV-685` (chunk 3). The catalog source of `INV-671` (ADR-0058.R12) and of `INV-682` (ADR-0059.R6; ADR-0043.R14) is no rule of this module; their rows are in chunk 3, with `INV-684`.

## Edge cases

Statements are those of `edge-cases.csv`, placed as the invariants are. First executable step 6 for each.

| Edge case | Name | Case | Outcome | Rules |
| --- | --- | --- | --- | --- |
| `EC-163` | `bank_parameters_promoted_then_demoted` | A parameter set for the bank cascade drafted from three months is backtested on the next two, shadowed, promoted with frozen evidence, keeps auto-post off until new evidence under its hash, and is demoted to shadow by override drift a month later; the demotion marks the auto-post rule's evidence outdated, and `EnablePolicyRule` refuses it until a new rule version brings new evidence. | `must_succeed` | R247 to R250; ADR-0059.R5, ADR-0059.R6, ADR-0059.R13 to ADR-0059.R21 |
| `EC-164` | `promotion_evidence_stale` | A function release between the evidence and the approval's execution makes the promotion fail with `artifact_evidence_stale`, while the version in force keeps acting, its owner gets `artifact_function_changed` with a re-evaluation, and new evidence succeeds. | `must_reject:artifact_evidence_stale` or `must_succeed` | R238; ADR-0059.R19 |

Named by R216, with their rows elsewhere: `EC-156`, `EC-157`, `EC-158`, `EC-159`, `EC-160`, `EC-161`, `EC-167` (chunk 1); `EC-166` (chunk 3). The catalog source of `EC-162` (ADR-0058.R25) and of `EC-165` and `EC-168` (ADR-0059.R10) is no rule of this module; their rows are in chunk 3.

## Settings

None: see chunk 1 for the rows of `automation.breaker_failures` and `automation.breaker_window_minutes` (R213) and chunk 3 for the row of `artifacts.<function_or_kind>.max_window_days` (R237).

`automation.value_hmac_key` (R213) is a company secret in the deployment's secret store and has no row in `settings.csv`. `reevaluation_window_days`, `reevaluation_min_cases` and `reevaluation_max_window_days` (R238, R239) are values of a function's registry declaration, not settings.

## UI annotations

The sources of this chunk state no floorplan, title, facet, field annotation or tile. Work item kinds of module `automation` that the rules of this module's chunks name, each once, with the values of `work-item-kinds.csv`:

| Kind | Subject table | Owner | Due | Resolution | Rule |
| --- | --- | --- | --- | --- | --- |
| `automation_task` | `automation_execution` | `named_by_raiser` | `named_by_raiser` | `person` | R212 |
| `automation_notice` | `automation_execution` | `named_by_raiser` | `days:7` | `person` | R212 |
| `automation_rule_disabled` | `automation_rule` | `named_by_raiser` | `days:1` | `command`: `EnableAutomationRule` | R212 |
| `automation_owner_scope_narrowed` | `automation_rule` | `subject_owner:owner_user_id` | `days:5` | `person` | R212 |
| `artifact_invalidated` | `artifact_transition` | `named_by_raiser` | `days:1` | `person` | R212 |
| `artifact_reference_deprecated` | `artifact_transition` | `named_by_raiser` | `days:30` | `person` | R212 |
| `artifact_demoted` | `artifact_transition` | `named_by_raiser` | `days:5` | `person` | ADR-0059.R28 |
| `artifact_function_changed` | `artifact_promotion_evidence` | `named_by_raiser` | `days:5` | `person` | R238, R239 |

None of them is agent-resolvable. For `automation_notice` the catalog row gives the due rule `days:7`, while ADR-0058.R28 names `named_by_raiser` for owner and due date; R212 keeps the rule's wording and this table the catalog's; no ADR orders the rule and the catalog row, so the difference is a finding on the sources, not a choice of this spec.

## Conflicts

CONFLICT ADR-0058.R24: ADR-0059.R13 governs the moves of `SetArtifactVersionState` for every kind; raising to `assisted` is bound to a proposal like `active` and `shadow`, a raise outside one returns `proposal_required`, and the approver is also not the human a drafting consumer acted for (R201, R203).
CONFLICT ADR-0058.R26: ADR-0058.R26.N1 with ADR-0074.R8 governs; user-defined fields are a Phase 1 seam, so R206 lists only user-defined tables after Phase 1.
CONFLICT ADR-0058.R26.N1: the note moves user-defined fields without custom tables out of the list of ADR-0058.R26 into Phase 1 (ADR-0074.R8 to ADR-0074.R12); R206 states the result once.
CONFLICT ADR-0058.R28: ADR-0063.R21 governs the breaker settings; they are company settings with an optional override in a rule version's content, and `automation.breaker_consecutive` and `automation.max_executions_per_rule_per_hour` stand beside the keys the rule lists, which R213 states instead of "company" alone.
CONFLICT ADR-0059.R1: ADR-0059.R1.N1 with ADR-0078.R8 governs drafting in Phase 1; R221 states that no tuning agent and no advisor exist in Phase 1 and names the sources of drafts.
CONFLICT ADR-0059.R2: the later note ADR-0059.R6.N1 (ADR-0065.R9, ADR-0065.R14) extends the calls of the hook `artifact_in_force_changed` from parameter sets to the decision table version in force at the auto-post gateway's decision point; R229 states both.
CONFLICT ADR-0059.R12: ADR-0059.R12.N1 with ADR-0078.R6 governs the agent-type ladder in Phase 1; where it says "shadow", R250 states the evaluation set and replay, and the artifact states stay as written.

## Trace

| Source | Where |
| --- | --- |
| ADR-0058.R24 | R201, R202, R203, R204 |
| ADR-0058.R24.N1 | R202, R203, R205 |
| ADR-0058.R26 | R206 |
| ADR-0058.R26.N1 | R206 |
| ADR-0058.R27 | R207, R208, R209 |
| ADR-0058.R28 | R210, R211, R212, R213, R214, R215, R216 |
| ADR-0058.R29 | R217 |
| ADR-0058.W | R218 |
| ADR-0059.D0 | R219 |
| ADR-0059.R1 | R220, R221, R222, R223 |
| ADR-0059.R1.N1 | R221 |
| ADR-0059.R2 | R224, R225, R226, R227, R228, R229 |
| ADR-0059.R3 | R230, R231, R232 |
| ADR-0059.R4 | R234, R235, R236, R237, R238, R239 |
| ADR-0059.R4.N1 | R237 |
| ADR-0059.R9 | R240, R241, R242, R243, R244, R245, R246 |
| ADR-0059.R12 | R247, R248, R249, R250 |
| ADR-0059.R12.N1 | R250 |
