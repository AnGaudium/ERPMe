Module: configuration    Chunk: 1 of 3    Source ADRs: ADR-0058
Build step(s): 1    Generated from index: 30d5706    Compiled by: Claude Fable 5.2, 2026-11-21

# `configuration` compiled spec, chunk 1: automation rules, decision tables, versions

## Purpose

`configuration` (layer 2, ADR-0022.R2) owns the company's configuration artifacts: automation rules, decision tables and parameter sets, with their versions, pure evaluators, pure validators and write functions. This chunk states the tiers, the registry vocabulary, the shape of an automation rule, its owner, rights, scope and taint, execution records, loop guards, the circuit breaker, decision tables, versions and stored tests. `configuration` does not own the consumer, the replay, the upgrade check, evidence or the monitor (`automation`, layer 5), nor approvals, waiting and asynchrony (R8). The commands, parameter sets, the artifact lifecycle and evidence are in the other chunks.

## Entities and tables

DDL: `docs/design/DS-28-34-configuration-artifacts.sql`. ADRs win where the DDL disagrees (R4).

| Table | Meaning | Key | Parent | Owner |
| --- | --- | --- | --- | --- |
| `automation_rule` | Identity of a versioned automation rule, with owner, consent, stored owner scope and pointers (R17, R25, R27) | `id`; (`company_id`, `code`) unique; (`company_id`, `id`) | `company` | `configuration` |
| `automation_rule_version` | One version of a rule: trigger, conditions, actions, tests, pins, lifecycle (R18) | `id`; (`automation_rule_id`, `version`) unique; (`company_id`, `id`) | `automation_rule` | `configuration` |
| `automation_execution` | Record of one execution of a rule version on one event (R35) | `id`; (`automation_rule_version_id`, `event_id`, `mode`) unique; (`company_id`, `id`) | `automation_rule_version` | `configuration` |
| `automation_scope_skip` | Value-free daily count per rule of subjects outside the owner's scope (R24) | `id`; (`automation_rule_id`, `business_date`) unique | `automation_rule` | `configuration` |
| `configuration_state` | One row per company, locked by every activation, enable, rollback and demotion (R48) | `id`; `company_id` unique | `company` | `configuration` |
| `decision_table` | Identity of a versioned decision table, with owner and pointers (R53) | `id`; (`company_id`, `code`) unique; (`company_id`, `id`) | `company` | `configuration` |
| `decision_table_version` | One version: hit policy, inputs, outputs, tests, lifecycle (R53, R55, R56) | `id`; (`decision_table_id`, `version`) unique; (`company_id`, `id`) | `decision_table` | `configuration` |
| `decision_table_row` | One row of a table version, frozen with it (R53) | `id`; (`decision_table_version_id`, `row_number`) unique | `decision_table_version` | `configuration` |

Named by rules of this chunk, with their rows in other chunks: `parameter_set` (chunk 2), `artifact_promotion_evidence` (chunk 3).

Reads: `outbox_event`, `audit_record`, `bank_statement_line`, `agent_run`, `change_proposal`, `user_account`, `company`.

## Commands and queries

Each command row stands once in the module. The rows of the commands that ADR-0058.R27 registers for `configuration` (`CreateAutomationRule`, `UpdateAutomationRule`, `ConfirmAutomationRuleOwnership`, `DisableAutomationRule`, `EnableAutomationRule`, the version and decision table commands, `GetArtifactValidation`) are in chunk 2; the rows of `SetArtifactVersionState` and `SetArtifactCurrentVersion` (ADR-0059.R27) are in chunk 3. `RaiseAutomationWorkItem` is a command of `automation`: `is_internal_only`, no role holds it, and it is checked by the owner's read right on the subject (R21). What the rules of this chunk add to those rows: `ConfirmAutomationRuleOwnership` records `owner_confirmed_at` and `owner_confirmed_user_id` (R25); an owner change by `UpdateAutomationRule` clears the consent (R26); `DisableAutomationRule` sets `disabled_at` and `disabled_reason` and raises `automation_rule_disabled` (R49, R51); `EnableAutomationRule` repeats the checks of R43 to R48 and returns `automation_rule_cycle`, `automation_depth_exceeded` or `artifact_invalid` (R52); `SetArtifactVersionState`, `SetArtifactCurrentVersion` and `EnableAutomationRule` call the pure validators and the hook `artifact_checks` (R3).

Contract functions, not registered commands: the pure evaluators `evaluate_conditions` and `evaluate_decision_table`, the pure validators and the write functions (R1); the hook `artifact_checks` (R3); the trigger `automation_rule_version_check_pins` (R59). Commands and jobs of `automation` that these rules name: `CreateArtifactEvidence`, `GetAutomationReplay`, `ListAutomationExecution`, `RunAutomationOwnerScopeCheck`, the consumer `automation_dispatch`.

Codes bound to no command of the table: `automation_owner_scope_insufficient`, `permission_denied` (R23); `automation_owner_not_confirmed` (R25); `artifact_invalid` with reason `trigger_unwatched` (R41); `decision_table_overlap` (R55); `decision_input_out_of_domain` (R58); `decision_table_version_in_use` (R59); `artifact_version_immutable` (R63); `artifact_tests_failed` (R66). Check results: `automation_owner_scope_limited` (R24), `automation_schedule_feedback` (R44), `decision_table_gap`, `decision_table_completeness_not_proven` (R57). Typed outcome: `decision_no_match` (R57).

## Rules

### Ownership and module split

R1. `configuration` (layer 2, ADR-0022.R2) owns the tables `automation_rule`, `automation_rule_version`, `automation_execution`, `decision_table`, `decision_table_version`, `decision_table_row`, `automation_scope_skip` and `configuration_state`, and the tables of ADR-0059.R2. Its contract holds the pure evaluators (`evaluate_conditions`, `evaluate_decision_table`), the pure validators (rule validity, the graph check of R43 to R48, the table check of R55 to R57) and the write functions. It imports the `registry` contract (read-only declarations) and `work`.
Source: ADR-0058.R1

R2. `automation` (layer 5) owns the consumer `automation_dispatch` (ADR-0058.R10), the replay (ADR-0058.R23), the upgrade check (ADR-0058.R25), evidence and the monitor (ADR-0059), and the commands of ADR-0058.R27 that read layer 3–4 data. It imports `registry` (dispatch), the `configuration`, `work` and `permissions` contracts, and the contracts of the modules of layer 3 and layer 4 whose deterministic functions it evaluates; none of its layer-5 peers.
Source: ADR-0058.R1

R3. `configuration` declares the hook `artifact_checks` (the pattern of ADR-0022.R2), which `automation` registers and `app` wires, for the parts of a check that read layer 3–5 data: the condition source's permission and scope for the owner, and the replay at execution. The commands `SetArtifactVersionState`, `SetArtifactCurrentVersion` and `EnableAutomationRule` of `configuration` call their pure validators directly and the hook for the rest, so no import goes up.
Source: ADR-0058.R1

R4. The DDL draft is `docs/design/DS-28-34-configuration-artifacts.sql`, a file apart from the platform file; it writes out the row-level security of its tables in the pattern of `DS-05-platform.sql`. The platform file only gains the causation columns of ADR-0058.R12 on `outbox_event` and `audit_record`, and the columns of ADR-0059.R6 on `bank_statement_line`. ADRs win if the DDL disagrees.
Source: ADR-0058.R1

R5. Automation rules and decision tables are in Phase 1. Agents may draft them only as artifacts under the lifecycle of ADR-0059: the stored-resolution proposals of `bank_matching` and `purchase_invoice`, the parameter and lead-time proposals of `planning`, and the assistant on request. Phase 1 has no advisor: `auto_post_advisor` is a Phase 2 agent type. A person approves (ADR-0078.R8). Workflow code never names an agent type; the work item kind is the contract (ADR-0078.R12).
Source: ADR-0058.R1.N1

### Tiers and what stays code

R6. A company configures in these tiers and no other: (a) parameters: registered company settings (typed, bounded, change-tracked) and, for the constants of a deterministic function that decide outcomes on business data, the versioned parameter sets of ADR-0059.R3 and ADR-0059.R4; (b) decision tables (R53 to R61); (c) automation rules (R17 to R52).
Source: ADR-0058.R2

R7. Vocabulary is code, composition is configuration. Event types, condition fields, commands, decision points, hold interfaces, scheduled jobs and agent triggers are registry items with versions (R10 to R16); a company composes them in rows. A need that the vocabulary cannot express is a code change in the core or in a package, reviewed like code (ADR-0059.R24). No artifact holds code, an expression, a template language or SQL; conditions are structured triples (R19).
Source: ADR-0058.R2

R8. These stay code or their own configuration. Approvals are configured only by policy rules (ADR-0043) and approval pools and stages (ADR-0055); an automation rule never routes an approval, approves or rejects. Waiting is a work item (ADR-0042) and asynchrony the outbox (ADR-0013); Phase 1 has no BPMN, no orchestration engine and no long-running process instance. Document lifecycles (ADR-0009) and agent workflow steps (ADR-0051) change only by a new release or agent type version. The auto-post gateway is a policy decision at the policy point of `Post<Type>`, evaluated by core code with settings and a decision table at a module decision point; it is not an automation rule, and no automation rule posts (ADR-0065.R13).
Source: ADR-0058.R3, ADR-0058.R3.N1

R9. An automation rule can never: submit, approve, reject, post, issue, reverse or send; change master data, settings, roles, policy or another artifact; widen an agent's tool list; relax a hard floor of spec 03.
Source: ADR-0058.R3

### Registry vocabulary

R10. An event type is usable as a trigger only when its registration declares:
- `is_automation_trigger` and its condition source: a registered query that takes the subject's ID, and its version for documents, and returns the condition fields; its permission, record scope and owner scope are the owner's test of R23 and R24;
- condition fields: name, type (`amount`, `quantity`, `percent`, `integer`, `date`, `boolean`, `code`, `reference`), data label and field class. Only fields the registry declares `is_gate_field` may be condition fields: an allowlist of deterministic fields, never a field fed by an LLM step's output directly or through computation (ADR-0059.R20). A field marked `is_untrusted` (ADR-0029.R10) or labelled `sensitive_personal` is never declared one, so outside text and model output never steer a rule;
- optionally a discriminator field (such as a work item's `kind`), which makes (event type, value) a node of the rule graph (R43);
- for an update event, its watchable fields, which the payload reports in `changed_fields` by name only (R41);
- `is_replayable`: the condition source reads an immutable version, so the replay of ADR-0058.R23 sees the facts as they were.
Source: ADR-0058.R4

R11. `is_automation_allowed` is a registry attribute. A command so registered is a `Create<Type>` that creates a draft (never an update or delete of one), is also `is_draft_only` (ADR-0050.R26), is never of effect class `posting`, `master_data_change` or `outbound_send`, never `human_only` or `is_proposal_bound`, and never a command of `configuration` or `automation` other than `RaiseAutomationWorkItem`. `CreateChangeProposal` is not automation-allowed: a rule never proposes master data changes. CI checks this. `StartAgentRun` and hold commands are reached only through their own action kinds (R14, R20).
Source: ADR-0058.R5

R12. Every command declares the event types it may emit and, for an event type with a discriminator, the discriminator values; a declaration without values counts as able to emit every value, which reaches every discriminated trigger of that type. Registered consumers and scheduled jobs declare the same for the commands they run. A registry check compares the declarations with the handlers' emits in tests. The graph check of R43 reads them.
Source: ADR-0058.R5

R13. An action's payload is built from the rule's payload template: each field is a literal, a condition field of the trigger, or an output of a pinned decision table version (R59). Validation type-checks it against the command's schema at the registry version, so an action never carries a free string from outside content.
Source: ADR-0058.R5

R14. A module may register a command `is_hold` for a subject table: effect class `other`, it only sets a block that a later step respects (a delivery or payment block), it never releases one, and a person releases it with the module's own release command. Phase 1 registers none yet; the open item payment block of DS-25 and a delivery block on sales orders are the first candidates. Until a module registers one, the action `set_hold` has no vocabulary.
Source: ADR-0058.R6

R15. Each claimable work item kind an agent type version declares carries `wake_up`: `always` (the hard-wired wake-up of ADR-0050.R16) or `configurable`. An agent type version may also declare `configurable_triggers`: pairs of (trigger event type, subject table) on which a company may start it. The subject tables it accepts (ADR-0050.R15) say whether outside content may start it. Making a kind or trigger configurable is a new agent type version (ADR-0050.R12).
Source: ADR-0058.R7

R16. For a kind declared `configurable` the company chooses the wake-up mode, `always` by default (ADR-0063.R11, which names the kinds and the setting). Under the mode `by_rule`, `agent_wake_up` skips the kind, and a company starts the agent on it, or on a configurable trigger, only by an automation rule whose action is `start_agent`, with its own conditions; without such a rule the item stays with people (Principle 12).
Source: ADR-0058.R7, ADR-0058.R7.N1

### Shape of an automation rule

R17. An automation rule is company data in `automation_rule`: `code`, `name`, `owner_user_id` (required), `owner_confirmed_at` and `owner_confirmed_user_id` (R25), `owner_scope` (R27), the pointer `current_version_id` to the version in force, `shadow_version_id` (ADR-0059.R12), and `disabled_at` with `disabled_reason` (`circuit_breaker`, `owner_inactive`, `upgrade_invalid`, `person`).
Source: ADR-0058.R8

R18. A version (`automation_rule_version`) holds `trigger_event_type`, an optional `trigger_discriminator`, `watched_fields`, `conditions`, at least 1 and at most 5 `actions`, `tests`, the pinned decision table versions it uses (`decision_table_version_ids`), and the lifecycle columns of ADR-0059.R12.
Source: ADR-0058.R8

R19. Conditions are triples (`field`, `operator`, `value`), all of which must hold. Operators by type: `eq`, `ne`, `in`, `not_in` for codes, references and booleans; `lt`, `le`, `gt`, `ge` and `between` (half-open, as ADR-0043.R3) for numbers and dates; `is_null`, `is_not_null` for any type; `decision` names a pinned decision table version, a boolean output and the handling of `decision_no_match` (R60). An alternative is a second rule.
Source: ADR-0058.R8

R20. Action kinds, each with what it runs and the permission checked for the owner (R23):
- `create_draft`: an `is_automation_allowed` command with its payload template (R13); the command's own permission; the draft carries the rule version as its origin.
- `raise_work_item`: `RaiseAutomationWorkItem`, kind `automation_task`; read permission on the subject (its `Get` or `List` query, with record and owner scope); owner: a user, a role template, `document_owner` of the subject, or a decision table output; due in N business days; text from the rule.
- `notify`: `RaiseAutomationWorkItem`, kind `automation_notice`; the same read permission; an in-app notice in the recipients' work queue; e-mail and push stay after Phase 1 (ADR-0040.R14).
- `start_agent`: `StartAgentRun` with the triggering work item or subject; `start_agent:<agent_type>`; only an agent type that declares the trigger (R15).
- `set_hold`: a registered `is_hold` command on the subject (R14); the command's own permission; released only by a person.
- `open_work_case`: `CreateWorkCase` for a case kind whose company mode is `by_rule` or `auto`, with the triggering subject as origin and the owner by `named_by_raiser`; the owner needs `CreateWorkCase` and the read permission on the subject; it drafts, posts and sends nothing (ADR-0066.R7).
Source: ADR-0058.R8, ADR-0058.R8.N1

R21. `RaiseAutomationWorkItem` stays `is_internal_only`, so no role holds it; its check is the owner's read right on the subject, which the dispatcher applies to it in place of a permission of its own.
Source: ADR-0058.R8

### Owner, rights, scope and taint

R22. Each action runs as actor `system` on behalf of the rule's owner (the exception of ADR-0013.R9, like `agent_wake_up`), except the agent run that `start_agent` starts, which acts for the agent setting's `workflow_owner_id` as ADR-0050.R15 requires; the rule's owner also needs `start_agent:<agent_type>`, so neither person extends the other's reach.
Source: ADR-0058.R9

R23. The owner must hold, at validation and again at each execution: the permission of each action (R20); the permission of the trigger's condition source query; the field class of every condition field and of every value an action carries (payload fields and decision table outputs, ADR-0017.R10). A missing permission or field class refuses the action with `automation_owner_scope_insufficient` or `permission_denied`, recorded as `refused`, which counts toward the breaker (R49). So no rule is an oracle on data its owner cannot read.
Source: ADR-0058.R9

R24. At execution the consumer reads the facts with the owner's record and owner scope (ADR-0017.R9; ADR-0054.R13 to ADR-0054.R15). A subject outside them is not evaluated, as a non-match. The consumer adds it to a value-free daily count per rule, `automation_scope_skip` (rule, business date, `skipped_count`); validation, the replay and its diff return the check result `automation_owner_scope_limited` with the owner's scope and the number of window events outside it, shown in the activation proposal; and when the record or owner scope of the owner of a rule in force narrows, `automation_owner_scope_narrowed` is raised for the rule's owner by the daily check of R28.
Source: ADR-0058.R9

R25. An owner is set only with their consent: the owner is the submitter of the activation proposal, or confirms ownership with `ConfirmAutomationRuleOwnership`, their own command. `owner_confirmed_at` and `owner_confirmed_user_id` record it, the database requires that user to be the current owner while a version is in force, and activation without it is refused (`automation_owner_not_confirmed`).
Source: ADR-0058.R9

R26. Changing the owner of a rule that has a version in force runs through a change proposal (`UpdateAutomationRule` is `is_proposal_bound` for that field), re-checks the new owner's rights and scope, and needs the new owner's consent; the old owner stays in force until the change executes. Every owner change clears the recorded consent (`owner_confirmed_at` and `owner_confirmed_user_id`), so consent never carries over to another person.
Source: ADR-0058.R9

R27. `automation_rule.owner_scope` (jsonb) stores, per rule, the owner's effective scope for that rule as a set of cells (ADR-0054.R15: scopes combine per assignment, and a row is visible when any assignment that grants the permission allows it). There is one cell per assignment in force whose role grants the permission of the rule's condition source, split to single values: (branch ID or `all`, warehouse ID or `all`, the read owner scope level, and for `team` and `department` the resolved unit IDs with the employee IDs the organisation resolver yields). Branch, warehouse and employee IDs are not hidden values. The set is stored at activation, at an owner change and when an `automation_owner_scope_narrowed` item is resolved.
Source: ADR-0058.R9

R28. The system job `RunAutomationOwnerScopeCheck` (`automation`, `is_internal_only`, daily, actor `system`) recomputes the set for every rule with a version in force, from the assignments, their roles and their validity dates read through the `permissions` contract, so an assignment that lapses by date, a role edit or a reorganisation is caught without an event.
Source: ADR-0058.R9

R29. When the owner's account is disabled, or the owner has no assignment in force in the company (its `valid_to` passed), the job disables the owner's rules with reason `owner_inactive` and raises `automation_rule_disabled` for `company_owner`, who reassigns them by the change of R26; this is the only case that involves `company_owner`.
Source: ADR-0058.R9

R30. A stored cell is covered when some new cell has the same or `all` branch, the same or `all` warehouse, a level at least as high, and, for `team` and `department`, all of the stored cell's employee IDs. The scope narrowed when a stored cell is not covered; the job then raises `automation_owner_scope_narrowed` for the rule's owner, naming the uncovered cells. With levels `team` and `department`, every colleague who leaves the owner's team or department uncovers a cell, so such items are frequent and expected. While the item is open for the rule (its open key is the rule), no second item is raised and the stored set is not changed, so the item keeps showing the difference; resolving it stores the new set.
Source: ADR-0058.R9

R31. Anything else that differs in the recomputed set (wider cells, or an equal reach from reshuffled assignments, which splitting to single values keeps silent) only updates the stored set and raises nothing.
Source: ADR-0058.R9

R32. A draft made by a rule counts as its writers, for segregation of duties (ADR-0055.R7 condition 5): the rule's owner, the version's drafter (or the human its drafting run acted for), and the triggering event's human. None of them approves what the rule drafted.
Source: ADR-0058.R9

R33. Actions inherit taint from the triggering event and subject. On a tainted event, or a subject whose effective version is tainted or which is outside content (the subject tables of ADR-0050.R15), the consumer runs drafts, work items and notices tainted, and `start_agent` when the agent type accepts that subject table (the run starts tainted, ADR-0050.R15 and ADR-0050.R16); it skips `set_hold`. On an event that carries an origin agent run it skips `start_agent`, so no agent wakes an agent (ADR-0050.R16). Skips are decided before any action runs, recorded per action as `skipped` with the reason, and never count toward the breaker (R49). A notice reaches only people inside the company: a `notify` action raises `automation_notice`, and notices about tainted subjects go only through the notification path of ADR-0076.
Source: ADR-0058.R9, ADR-0058.R9.N1

R34. A rule triggered by an event that carries an origin agent run acts under the intersection of ADR-0029.R12.
Source: ADR-0058.R9

### Execution records

R35. `automation_execution` records: rule and version, `mode` (`live`, `shadow`), event ID and type, the event's business date, subject and the version read, the subject's scope dimensions (branch, warehouse, document) for readers' scope, causation chain and depth, `outcome` (`acted`, `partial`, `skipped`, `would_act`, `skipped_same_target`, `depth_exceeded`, `refused`, `failed`, `rate_limited`), the condition results (field, operator, field class, data label, value read, result), the input hash, each action's kind, command, key, outcome (`done`, `skipped`, `refused`, `failed`) and audit record or error, taint, origin agent run and the owner acted for. A personal value is stored as a keyed hash, HMAC-SHA-256 under the company's secret `automation.value_hmac_key`, or omitted, never as a plain hash.
Source: ADR-0058.R11, ADR-0058.R16.N1

R36. Not recorded per event: events where a rule's conditions did not match, and subjects outside the owner's scope, which only the daily count of R24 records. `GetAutomationReplay` answers "why did my rule not act on this order" for one event.
Source: ADR-0058.R11

R37. `ListAutomationExecution`, the agent view `automation_execution_overview` (ADR-0050.R51), `GetAutomationReplay` and the frozen replay diffs of ADR-0058.R23 return a row only when the subject is inside the reader's record and owner scope. For a field class the reader lacks they omit the value and that condition's result, and set the marker `is_class_filtered` on it (the omission of ADR-0017.R10); they never show a hash in its place. The residue is stated: an `acted` outcome still tells such a reader that the conditions held.
Source: ADR-0058.R11

R38. The HMAC key lives in the deployment's secret store, is never in a view or a prompt, and keyed hashes are compared only inside the system. Keys are versioned and never rotated in place: a new key version hashes new values, every stored hash names its key version, old key versions are kept for verification only, and stored values are never re-hashed.
Source: ADR-0058.R11

R39. An agent run reads execution records with its intersection of rights (ADR-0050.R31); the view `automation_execution_overview` has no partner column and so is closed to tainted runs; a drafting agent type never has it on its tool list (ADR-0059.R16). Execution records are kept as decision records under ADR-0059.R23.
Source: ADR-0058.R11

### Same target, field-change triggers, idempotency

R40. A rule acts at most once per (chain, subject). A unique index on `automation_execution` (rule, chain, subject) over live executions with outcome `acted` or `partial` holds it; a second match in the chain is recorded `skipped_same_target`.
Source: ADR-0058.R13

R41. Transitions (`SalesOrderApproved`, ADR-0009.R22) are changes by nature. Update events (`PartnerUpdated`, `SalesOrderChanged`) trigger a rule only through its `watched_fields`, which must be non-empty and among the event type's watchable fields; the rule fires only when the event's `changed_fields` intersect them. A rule on an update event without watched fields is invalid (`artifact_invalid`, reason `trigger_unwatched`). There is no "on any write".
Source: ADR-0058.R14

R42. One execution exists per (rule version, event, mode), a unique key of `automation_execution`; every action's command key is `automation:<rule version id>:<event id>:<n>`, so a retried delivery replays the stored responses (ADR-0008.R16) and never duplicates a draft or an item.
Source: ADR-0058.R17

### The graph check

R43. Nodes of the rule graph are event types, split by discriminator value where declared. Each rule (active, disabled or the candidate) adds edges from its trigger node to every node its actions' commands may emit (R12); an emit declared without values reaches every discriminated node of its type. Each registered consumer adds edges from its subscribed events to the events of the commands it may run.
Source: ADR-0058.R15

R44. A scheduled job starts a chain at depth 0 and adds edges from itself to the events of its commands; nothing leads into it. A loop through a scheduled job can therefore repeat once per schedule run, each time at depth 0; activation returns the check result `automation_schedule_feedback` when the candidate's actions emit an event type on a table that a scheduled job declares it reads and that job's events reach the candidate's trigger, so a person sees it.
Source: ADR-0058.R15

R45. A cycle through the candidate is refused with `automation_rule_cycle`, naming the path. Cycles of consumers alone are the core's concern (ADR-0013) and are not reported.
Source: ADR-0058.R15

R46. The depth at which a rule can act is 1 plus the largest number of rule edges on any path that leads to its trigger. A candidate that could act beyond depth 3, or that would push another rule beyond it, is refused with `automation_depth_exceeded`.
Source: ADR-0058.R15

R47. The graph check runs at the evidence (ADR-0058.R23), at the creation of an activation proposal, again at its execution, at `EnableAutomationRule`, at every rollback (`SetArtifactCurrentVersion`) and automatic demotion (ADR-0059.R21), and at every upgrade (ADR-0058.R25), each time with validity (R10 to R13, R22 to R34) against the current registry and over the whole set. Disabled rules stay in the graph, so enabling one cannot close a cycle. A failing target is refused with `artifact_invalid`; the monitor's demotion then falls back to the core defaults or to none.
Source: ADR-0058.R15

R48. Every activation, enable, rollback and demotion first locks the company's `configuration_state` row (lock class 3 of ADR-0027.R10), so parallel approvals cannot together form a cycle that each alone does not. The runtime cap of ADR-0058.R12 remains the backstop for paths no declaration shows.
Source: ADR-0058.R15

### Circuit breaker

R49. The consumer runs `DisableAutomationRule` with reason `circuit_breaker` when a rule's live executions record, among outcomes `refused`, `failed` or `partial`, either `automation.breaker_failures` within `automation.breaker_window_minutes`, or `automation.breaker_consecutive` in a row at any rate; each of these settings may be overridden in a rule version's content, and the breaker cannot be turned off: no value means never (ADR-0063.R21). Skips by design and outcomes `skipped_same_target`, `depth_exceeded` and `rate_limited` do not count. The window is counted on the executions' business date and recorded instant, declared a technical timer of the breaker (ADR-0007.R10, as ADR-0013.R7 declares the delivery timers); the count in a row needs no clock.
Source: ADR-0058.R16, ADR-0058.R16.N1, ADR-0058.R9.N1

R50. The flood guard `automation.max_executions_per_rule_per_hour` records the outcome `rate_limited` and runs no action; `rate_limited` never counts toward the breaker (ADR-0063.R21).
Source: ADR-0058.R16.N1

R51. `DisableAutomationRule` runs under the consumer's registered permission, not the owner's, because the owner may be the one who lost a right. It raises `automation_rule_disabled` for the owner, or for `company_owner` when the owner can no longer open the company.
Source: ADR-0058.R16

R52. A person runs `EnableAutomationRule`, which re-enables the same current version after the checks of R43 to R48; it never changes the version.
Source: ADR-0058.R16

### Decision tables: shape and hit policies

R53. A decision table is company data in `decision_table`, `decision_table_version` and `decision_table_row`. Inputs are declared with a type and a domain: `code` inputs list their allowed values (a registry enumeration, or a company list copied into the version); numeric inputs (`amount`, `quantity`, `percent`, `integer`) a half-open range, unbounded where empty; `boolean` inputs true and false. Outputs are typed (`code`, `amount`, `integer`, `boolean`, `role_template`, `user`), and for the monotone policy each names its aggregator. Rows hold one cell per input (a set of values, a half-open range, a boolean, or nothing, meaning any) and one value per output. A version has at most 200 rows and 6 inputs.
Source: ADR-0058.R18

R54. Decision tables are used in automation rules (the `decision` operator, payload fields, the owner and due days of a work item) and at decision points that modules declare in the registry with their input and output schema and a code default for `decision_no_match`. The core declares no module decision point in Phase 1; candidates are work item owner routing per kind and putaway rules (ADR-0023.R21).
Source: ADR-0058.R18

R55. Hit policy `unique`: at most one row matches any input. Validation compares every pair of rows exactly (boxes overlap when every input's cells intersect) and refuses an overlap with `decision_table_overlap`, naming the overlapping rows and a point they share.
Source: ADR-0058.R19

R56. Hit policy `monotone`: every matching row contributes, and each output combines by an aggregator that is commutative, associative and idempotent: `max`, `min`, `any`, `all`, `union`, `intersection`. `sum`, `first` and priorities are not offered, so the result never depends on row order or on duplicate rows.
Source: ADR-0058.R19

R57. Completeness is not required: an input that no row matches is the typed outcome `decision_no_match`. Validation may prove completeness by box subtraction: it subtracts each row's box from the declared domain and stops at the first uncovered box, under a work cap of 100,000 box operations. It returns the check result `decision_table_gap` with a witness point when it finds one, and `decision_table_completeness_not_proven` when the cap is reached; it never reports a gap it did not find, and neither result refuses the version.
Source: ADR-0058.R19

R58. A null input, a code value not in the version's list (a value added to the company list after the version froze) or a number outside the declared range is `decision_input_out_of_domain`.
Source: ADR-0058.R19

### Decision tables: binding and evaluation records

R59. A rule names the decision table versions it uses, by ID, as part of its content (and so of its content hash, R64); they are versions of the company's tables. A rule version leaves draft (for `backtested`) only when every pinned table version exists in the company and is frozen: `backtested`, `shadow`, `assisted` or `active`, never `draft` or `retired`. A rule version becomes `active` only when every pinned version is `assisted` or `active`; a shadow rule version may pin a `backtested` or `shadow` table version. The trigger `automation_rule_version_check_pins` holds both moves, and validation and each execution apply the same split. A pinned version cannot be retired or demoted to `shadow` while a current or shadow rule version pins it: `decision_table_version_in_use`. A table's pointer, its rollback or a new table version never changes a rule: a rule that should use a new table version needs a new version of its own, with its own replay. A table's pointer serves module decision points only.
Source: ADR-0058.R20, ADR-0058.R20.N1

R60. Every use of a table in a rule states its handling of `decision_no_match`: `no_match: false` (a condition fails, or the action is skipped as by design) or a typed default value; validation refuses a use without one. `decision_input_out_of_domain` makes that rule's execution `failed` with the code, which counts toward the breaker. A module decision point uses its code default for `decision_no_match`.
Source: ADR-0058.R20

R61. Every evaluation records (table code, version, input hash, matched rows, output or outcome). An automation rule stores it in its execution's condition results; a module's decision point stores it in its own record or derivation trace (ADR-0027.R3), with the version as `rule_version`.
Source: ADR-0058.R20

### Versions and stored tests

R62. Decision tables and automation rules use the ladder draft → `backtested` → `active` of the lifecycle of ADR-0059.R12, with an optional `shadow` stage and no `assisted` stage for rules. `backtested` here means: valid, tests passing, replay frozen as evidence (ADR-0058.R23). A version leaves draft only to `backtested`.
Source: ADR-0058.R21

R63. A version is inserted only as a draft and is editable only in `draft`. From `backtested` on, its content never changes; a trigger refuses it (`artifact_version_immutable`). A change is a new version.
Source: ADR-0058.R21

R64. `content_hash` is the SHA-256 of the canonical JSON (the forms of ADR-0006.R13) of the version's content: for a rule, its trigger, discriminator, watched fields, conditions, actions with their payload templates, tests and the IDs and content hashes of the decision table versions it pins; for a table, its hit policy, inputs, outputs, tests and its rows sorted by row number; for a parameter set, that of ADR-0059.R4. Lifecycle columns, IDs of the version itself, drafter and timestamps are outside it.
Source: ADR-0058.R21

R65. Activation sets `effective_from`, never before the business date of the activation; the consumer uses the version in force on the event's business date (ADR-0058.R10), so backdating selects nothing old (the reasoning of ADR-0043.R6). The rule's `current_version_id` names the one version in force; rollback moves the pointer (ADR-0059.R13).
Source: ADR-0058.R21

R66. Each version carries its tests: for a rule, an event with the subject's field values and the expected match and actions; for a table, inputs and expected outputs or outcomes. Validation runs them, and a failing test refuses evidence (`artifact_tests_failed`). A person may save an evaluation shown by `GetAutomationReplay` as a test of a new draft.
Source: ADR-0058.R22

## Invariants

Statements are those of `invariants.csv`; each row stands once in the module, here when its catalog source names a rule of this chunk. First step 5 for each.

| Invariant | Name | Check point | Statement | Protects |
| --- | --- | --- | --- | --- |
| `INV-670` | `automation_actions_registered` | day | Every audit record with an `automation_rule_version_id` names a command registered `is_automation_allowed` at the time, `StartAgentRun` or a registered hold command, and ran as `system` on behalf of the rule's owner at that time, except the agent run a `StartAgentRun` started, which acts for the agent setting's workflow owner. | R11, R22 |
| `INV-672` | `automation_once_per_chain_target` | day | No two live executions with outcome `acted` or `partial` share rule, causation chain and subject, and no rule version has more than one execution of one event in one mode. | R40, R42 |
| `INV-673` | `automation_owner_permitted` | day | Every action recorded `done` in a live execution ran while the rule's owner held in the company on that business date the action's permission: the command's own for `create_draft` and `set_hold`, the subject's `Get` or `List` permission with record and owner scope for `raise_work_item` and `notify`, `start_agent:<agent_type>` for `start_agent`; evaluated from the audit record and the owner's assignments in force. | R20, R23 |
| `INV-674` | `automation_taint_inherited` | day | Every action of an execution whose event or subject was tainted is an `is_draft_only` command, `RaiseAutomationWorkItem`, or `StartAgentRun` of an agent type that accepts the subject table, and wrote tainted rows; no `StartAgentRun` with an `automation_rule_version_id` follows an event that carries an origin agent run, and no `set_hold` follows a tainted event or subject. | R33 |
| `INV-675` | `automation_graph_bounded` | day | No current, shadow or disabled automation rule version, with the others, forms a cycle in the rule graph or acts beyond depth 3 under the registry in force. | R45, R46, R47 |
| `INV-676` | `decision_tables_order_free` | day | Every `unique` decision table version out of draft has no two rows whose boxes intersect, every `monotone` one uses only commutative, associative and idempotent aggregators, every rule version that uses a table version states its handling of `decision_no_match`, and every table version a current or shadow rule version pins is `assisted` or `active`. | R55, R56, R59, R60 |
| `INV-677` | `artifact_versions_immutable` | day | Every artifact version out of draft has the content its `content_hash` names, and its child rows have not changed since it left draft. | R63, R64; ADR-0059.R12 |
| `INV-686` | `automation_owner_scope` | day | Every live execution's subject was inside its owner's record and owner scope on that business date, and the owner held the field class of every condition field and action value of the version then; no stored condition value is a plain hash of a personal value, and every out-of-scope subject is in the rule's daily count. | R23, R24, R35 |
| `INV-687` | `automation_draft_writers` | day | No approval of a draft that an automation rule made was given by the rule's owner, the version's drafter or the human its drafting run acted for, or the triggering event's human. | R32 |

`INV-671` (catalog source ADR-0058.R12, a rule of `automation`) has its row in chunk 3. The other invariants of the module have their rows in chunks 2 and 3.

## Edge cases

Statements are those of `edge-cases.csv`; each row stands once in the module, here when its catalog source names a rule of this chunk. First executable step 5 for each.

| Edge case | Name | Case | Outcome | Rules |
| --- | --- | --- | --- | --- |
| `EC-156` | `large_order_alerts_warehouse` | A sales order above the rule's threshold is approved; the warehouse gets one automation work item, and a second matching event in the same causation chain is recorded `skipped_same_target`. | `must_succeed` | R20, R40; ADR-0058.R10 |
| `EC-157` | `automation_cycle_refused` | A rule that raises an automation task on any automation task is refused at activation as a cycle, and so is a rule on `WorkItemRaised[automation_task]` whose purchase request draft a consumer answers with work items of undeclared kinds; with a notice instead of a task the first is accepted. | `must_reject:automation_rule_cycle` or `must_succeed` | R43, R45 |
| `EC-158` | `automation_depth_cap` | A fourth rule on a chain of three is refused at activation for depth; a path no declaration showed stops at depth 3 at run time. | `must_reject:automation_depth_exceeded` or `must_succeed` | R46; ADR-0058.R12 |
| `EC-159` | `automation_owner_loses_right` | The owner of an active rule loses the right to create purchase requests; five refusals within an hour disable the rule and raise `automation_rule_disabled`; when the owner's last assignment ends, the rules are disabled `owner_inactive` and `company_owner` gets the item. | `must_succeed` | R23, R29, R49 |
| `EC-160` | `automation_on_agent_chain` | An event of an agent's chain reaches a rule with `create_draft` and `start_agent`; the draft is created tainted, the agent start is skipped by design, and the execution is `acted` without counting toward the breaker. | `must_succeed` | R33 |
| `EC-161` | `decision_table_overlap_and_gap` | A decision table with an overlap is refused; with the overlap fixed and a gap left it is accepted with `decision_table_gap`, and an input in the gap takes the rule's no-match handling. | `must_reject:decision_table_overlap` or `must_succeed` | R55, R57, R60 |
| `EC-167` | `automation_owner_and_reader_scope` | An owner without the margin class cannot activate a rule on a margin field; a rule whose owner covers one branch never evaluates orders of another; validation returns `automation_owner_scope_limited` and the daily count grows; a reader without that branch sees none of its executions, and a reader without margin sees margin values and their results omitted, marked `is_class_filtered`. | `must_reject:automation_owner_scope_insufficient` or `must_succeed` | R23, R24, R37 |

## Settings

Rows of `settings.csv` (area `automation`, leaf `configuration`, storage `setting_value`, change effect `immediate`) that R49 and R50 use. The other `automation.*` keys and the `artifacts.*` keys have their rows in chunk 3.

| Key | Type | Scopes | Core default | Bounds | Direction | Rule |
| --- | --- | --- | --- | --- | --- | --- |
| `automation.breaker_failures` | integer | `company`; `rule_version` | 5 | 1..50 | `lower_tighter` | R49 |
| `automation.breaker_window_minutes` | integer | `company`; `rule_version` | 60 | 5..1440 | `higher_tighter` | R49 |
| `automation.breaker_consecutive` | integer | `company`; `rule_version` | 20 | 3..200, never below `automation.breaker_failures` | `lower_tighter` | R49 |
| `automation.max_executions_per_rule_per_hour` | integer | `company`; `rule_version` | 500 | 10..10000 | `lower_tighter` | R50 |

`automation.value_hmac_key` (R35, R38) is a company secret in the deployment's secret store, not a setting; it has no row in `settings.csv`.

## UI annotations

The units of this chunk state no floorplan, title, facet, field annotation or tile. Work item kinds that the rules of this chunk raise: `automation_task` and `automation_notice` (R20), `automation_owner_scope_narrowed` (R24, R30) and `automation_rule_disabled` (R29, R51). Their rows in `work-item-kinds.csv` belong to `automation`; chunk 2 shows them.

## Conflicts

CONFLICT ADR-0058.R7: ADR-0058.R7.N1 (ADR-0063.R11) governs; a `configurable` kind means the company chooses the wake-up mode, `always` by default, and "configurable means configured" holds only under `by_rule`. The interim list of kinds and the open question for the author are answered by ADR-0063.R11 and not restated (R15, R16).
CONFLICT ADR-0058.R8: ADR-0058.R8.N1 (ADR-0066.R7) adds the action kind `open_work_case` to the kinds of the rule's table; R20 states every kind.
CONFLICT ADR-0058.R9: ADR-0058.R9.N1 confirms that notices reach only people inside the company, through the notification path of ADR-0076, so the mark "flagged" is dropped (R33).
CONFLICT ADR-0058.R11: ADR-0063.R21, cited by ADR-0058.R16.N1, adds the outcome `rate_limited`, which the DDL check of `automation_execution` holds; R35 states the enum with every value.
CONFLICT ADR-0058.R16: ADR-0058.R16.N1 (ADR-0063.R21) replaces the fixed 20 in a row by the setting `automation.breaker_consecutive` and bounds the other thresholds, each with an override in a rule version's content; ADR-0058.R9.N1 confirms them, so the mark "flagged" on the defaults is dropped (R49).
CONFLICT ADR-0058.R20: ADR-0058.R20.N1 governs the pin check; leaving draft needs frozen table versions (`backtested`, `shadow`, `assisted` or `active`) and only becoming `active` needs `assisted` or `active`, in place of "only `active` or `assisted`" at every check (R59).

## Proposed (not law)

None

## Trace

| Source | Where |
| --- | --- |
| ADR-0027.R10.N2 | ref: ADR-0027.R10.N2 |
| ADR-0058.D0 | Tiers and what stays code |
| ADR-0058.R1 | R1-R4 |
| ADR-0058.R1.N1 | R5 |
| ADR-0058.R2 | R6-R7 |
| ADR-0058.R3 | R8-R9 |
| ADR-0058.R3.N1 | R8 |
| ADR-0058.R4 | R10 |
| ADR-0058.R5 | R11-R13 |
| ADR-0058.R6 | R14 |
| ADR-0058.R7 | R15-R16 |
| ADR-0058.R7.N1 | R16 |
| ADR-0058.R8 | R17-R21 |
| ADR-0058.R8.N1 | R20 |
| ADR-0058.R9 | R22-R34 |
| ADR-0058.R9.N1 | R33, R49 |
| ADR-0058.R11 | R35-R39 |
| ADR-0058.R13 | R40 |
| ADR-0058.R14 | R41 |
| ADR-0058.R15 | R43-R48 |
| ADR-0058.R16 | R49, R51, R52 |
| ADR-0058.R16.N1 | R35, R49, R50 |
| ADR-0058.R17 | R42 |
| ADR-0058.R18 | R53-R54 |
| ADR-0058.R19 | R55-R58 |
| ADR-0058.R20 | R59-R61 |
| ADR-0058.R20.N1 | R59 |
| ADR-0058.R21 | R62-R65 |
| ADR-0058.R22 | R66 |
| ADR-0058.R23 | ref: ADR-0058.R23 |
