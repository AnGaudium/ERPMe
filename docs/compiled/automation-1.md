Module: automation    Chunk: 1 of 2    Source ADRs: ADR-0058, ADR-0059
Build step(s): 1, 2, 3    Generated from index: 30d5706    Compiled by: Claude Fable 5.2, 2026-11-21

# Compiled spec: `automation`, chunk 1

## Purpose

`automation` (layer 5, ADR-0022.R2) executes the company's automation rules on events and computes the evidence that
moves a configured artifact through its lifecycle. This chunk states the execution of rules by the consumer
`automation_dispatch` (owner, rights, scope, taint, guards, execution records, causation chain, circuit breaker), the
replay diff, upgrade safety, and the artifact evidence rules (module split, moves, time split, held-out cases, monitor
and demotion). `automation` owns no table: the artifact and execution tables belong to `configuration`. Chunk 2 states
the artifact queries and catalog rows, the automation settings and the auto-post gateway.

## Entities and tables

None: `automation` owns no table. DDL of the tables it writes through `configuration`:
`docs/design/DS-28-34-configuration-artifacts.sql`.

Reads: `automation_rule` (`owner_scope`, `owner_confirmed_at`, `owner_confirmed_user_id`), `automation_execution`, `automation_scope_skip`, `artifact_transition`, `artifact_promotion_evidence`, `artifact_shadow_outcome`, `artifact_monitor_snapshot`, `golden_case_label`, `parameter_set`, `parameter_set_version`, `parameter_set_value`, `document_version`, `outbox_event`, `audit_record`, `agent_promotion_evidence`.

## Commands and queries

Only what the rules of this chunk state; chunk 2 holds the artifact queries and the commands of the auto-post gateway.
Authorization area `automation`: automation executions and replays at `read`, filtered by the reader's scope and
classes; `CreateArtifactEvidence` at `full`.

| Name | Actor and authorization | Input | Effect | Events | Error codes |
| --- | --- | --- | --- | --- | --- |
| `RunAutomationOwnerScopeCheck` (system job) | `system`; `is_internal_only`; daily | not stated | recomputes `automation_rule.owner_scope` for every rule with a version in force; disables rules of an inactive owner; raises `automation_owner_scope_narrowed` (R6 to R8) | not stated | not stated |
| `RecordAutomationExecution` | internal | not stated | writes one execution row per matched rule version, after its actions (R18) | not stated | not stated |
| `ListAutomationExecution` (query) | area `automation` at `read` | not stated | execution rows, filtered by the reader (R22) | none | not stated |
| `GetAutomationReplay` (query) | area `automation` at `read` | one event | why a rule did or did not act on the event; runs no action (R21, R22) | none | not stated |
| `RunArtifactUpgradeCheck` (system job) | not stated; runs at every core or package upgrade | not stated | re-validates artifact versions, deactivates the invalid ones (R38 to R40) | not stated | not stated |
| `CreateArtifactEvidence` | a person; area `automation` at `full`; effect class `other`; on no agent tool list | stage `backtest`, `preview` or `live` | computes evidence once and stores it in `artifact_promotion_evidence` (R36, R47) | not stated | `drafting_window_violated`, `drafting_run_steps_missing`, `backtest_window_not_after_drafting`, `backtest_source_undated`; evidence insufficient: `held_out_case_seen` |
| `RunArtifactMonitor` (system job) | `is_internal_only`; daily | not stated | effect class `other`; writes `artifact_monitor_snapshot` rows, demotes beyond the threshold, raises `artifact_demoted` (R64, R65); also the release re-evaluation (ADR-0059.R27) | not stated | not stated |

Not registered commands: the transactional consumer `automation_dispatch` (queue `events`, R12); the hook
`artifact_checks` (R42); the contract functions `backtest`, `compare` and `monitor` that owning modules register (R43);
the agent view `automation_execution_overview` (R22).

Commands of `configuration` that the rules of this chunk name: `ConfirmAutomationRuleOwnership`, `UpdateAutomationRule`
(R4), `DisableAutomationRule`, `EnableAutomationRule` (R29, R31, R32), `SetArtifactVersionState` (R48),
`SetArtifactCurrentVersion` (R49), `ListGoldenCaseLabel` (R59). `GetAutoPostShadowEvaluation` belongs to `cash` (R43).

Codes bound to no command of the table: `automation_owner_scope_insufficient`, `permission_denied` (R2);
`automation_owner_not_confirmed` (R4); `automation_depth_exceeded` (R28); `proposal_required` (R48);
`artifact_version_not_eligible`, `artifact_invalid` (R49); `approver_is_submitter`, `segregation_of_duties` (R50);
`held_out_filter_unavailable` (R59). Check results: `automation_owner_scope_limited` (R3, R35),
`automation_same_target_warning` (R19), `replay_not_reconstructable` (R35).

## Rules

### Owner, rights, scope and taint

R1. Each action runs as actor `system` on behalf of the rule's owner (the exception of ADR-0013.R9, like `agent_wake_up`), except the agent run that `start_agent` starts, which acts for the agent setting's `workflow_owner_id` as ADR-0050.R15 requires. The rule's owner also needs `start_agent:<agent_type>`, so neither person extends the other's reach.
Source: ADR-0058.R9

R2. At validation and again at each execution the owner must hold: the permission of each action (the table of ADR-0058.R8); the permission of the trigger's condition source query; the field class of every condition field and of every value an action carries (payload fields and decision table outputs, ADR-0017.R10). A missing permission or field class refuses the action with `automation_owner_scope_insufficient` or `permission_denied`, recorded as `refused`, which counts toward the breaker (R29).
Source: ADR-0058.R9

R3. At execution the consumer reads the facts with the owner's record and owner scope (ADR-0017.R9; ADR-0054.R13 to ADR-0054.R15). A subject outside them is not evaluated, as a non-match. The consumer adds it to a value-free daily count per rule, `automation_scope_skip` (rule, business date, count). Validation, the replay and its diff return the check result `automation_owner_scope_limited` with the owner's scope and the number of window events outside it, shown in the activation proposal. When the record or owner scope of the owner of a rule in force narrows, the daily check (R6, R7) raises `automation_owner_scope_narrowed` for the rule's owner.
Source: ADR-0058.R9

R4. An owner is set only with their consent: the owner is the submitter of the activation proposal, or confirms ownership with `ConfirmAutomationRuleOwnership`, their own command. `owner_confirmed_at` and `owner_confirmed_user_id` record it; the database requires that user to be the current owner while a version is in force; activation without it is refused (`automation_owner_not_confirmed`). Changing the owner of a rule that has a version in force runs through a change proposal (`UpdateAutomationRule` is `is_proposal_bound` for that field), re-checks the new owner's rights and scope, and needs the new owner's consent; the old owner stays in force until the change executes. Every owner change clears `owner_confirmed_at` and `owner_confirmed_user_id`, so consent never carries over to another person.
Source: ADR-0058.R9

R5. `automation_rule.owner_scope` (jsonb) stores, per rule, the owner's effective scope for that rule as a set of cells (ADR-0054.R15). There is one cell per assignment in force whose role grants the permission of the rule's condition source, split to single values: branch ID or `all`, warehouse ID or `all`, the read owner scope level, and for `team` and `department` the resolved unit IDs with the employee IDs the organisation resolver yields. Branch, warehouse and employee IDs are not hidden values. The set is stored at activation, at an owner change and when an `automation_owner_scope_narrowed` item is resolved.
Source: ADR-0058.R9

R6. The system job `RunAutomationOwnerScopeCheck` (`automation`, `is_internal_only`, daily, actor `system`) recomputes the set for every rule with a version in force, from the assignments, their roles and their validity dates read through the `permissions` contract, so a lapsed assignment, a role edit or a reorganisation is caught without an event. When the owner's account is disabled, or the owner has no assignment in force in the company (its `valid_to` passed), the job disables the owner's rules with reason `owner_inactive` and raises `automation_rule_disabled` for `company_owner`, who reassigns them by the change of R4; no other case involves `company_owner` in this job.
Source: ADR-0058.R9

R7. A stored cell is covered when some new cell has the same or `all` branch, the same or `all` warehouse, a level at least as high, and, for `team` and `department`, all of the stored cell's employee IDs. The scope narrowed when a stored cell is not covered; the job then raises `automation_owner_scope_narrowed` for the rule's owner, naming the uncovered cells. With levels `team` and `department` every colleague who leaves the owner's team or department uncovers a cell, so such items are frequent and expected. While the item is open for the rule (its open key is the rule), no second item is raised and the stored set is not changed; resolving it stores the new set.
Source: ADR-0058.R9

R8. Any other difference found by the job (wider cells, or an equal reach from reshuffled assignments) only updates the stored set and raises nothing.
Source: ADR-0058.R9

R9. For segregation of duties (ADR-0055.R7, condition 5) the writers of a draft made by a rule are the rule's owner, the version's drafter (or the human its drafting run acted for) and the triggering event's human. None of them approves what the rule drafted.
Source: ADR-0058.R9

R10. Actions inherit taint from the triggering event and subject. On a tainted event, or a subject whose effective version is tainted or which is outside content (the subject tables of ADR-0050.R15), the consumer runs drafts, work items and notices tainted, runs `start_agent` when the agent type accepts that subject table (the run starts tainted, ADR-0050.R15, ADR-0050.R16), and skips `set_hold`. On an event that carries an origin agent run it skips `start_agent`, so no agent wakes an agent (ADR-0050.R16). Skips are decided before any action runs, recorded per action as `skipped` with the reason, and never count toward the breaker (R29). Notices about tainted subjects go only through the notification path of ADR-0076: a `notify` action raises `automation_notice`, which reaches only people inside the company.
Source: ADR-0058.R9, ADR-0058.R9.N1

R11. A rule triggered by an event that carries an origin agent run acts under the intersection of ADR-0029.R12.
Source: ADR-0058.R9

### Execution by `automation_dispatch`

R12. The transactional consumer `automation_dispatch` (queue `events`) subscribes to every event type registered `is_automation_trigger`. For each event it takes the company's rules whose current or shadow version has that trigger and is not disabled. The version used is the one in force on the event's business date: the current version when the date is on or after its `effective_from`, otherwise the version the transition log shows in force that day if it is still eligible; when none was, the event is not evaluated and leaves no record. While `automation.dispatch_paused` is true the consumer acknowledges events without evaluating them, and nothing is replayed on resume (ADR-0063.R20).
Source: ADR-0058.R10

R13. The consumer reads each rule's condition source once per event, with the owner's rights and scope (R2, R3): a document subject at the version the event names (an immutable `document_version`), any other subject as it is now, with the hash of what it read. It evaluates every matching rule's conditions on those facts before running any action, so no rule sees another's effects in the same dispatch.
Source: ADR-0058.R10

R14. Guards run per matched rule in rule-ID order, and the results do not depend on the order: the event's depth below 3 (R28), the same-target guard (ADR-0058.R13), the rule not disabled, and the skips of R10.
Source: ADR-0058.R10

R15. The consumer allocates the execution's ID first, so a raised work item can name it as subject. Each action runs in its own savepoint through the dispatcher, with idempotency key `automation:<rule version id>:<event id>:<n>` (ADR-0058.R17), and gets its own outcome in `action_results`: `done`, `skipped` (by design, R10), `refused` (permission, scope, field class) or `failed` (anything else). A non-retryable error rolls back only that action's savepoint. A retryable error (`concurrent_update`, `timeout`) rolls back the delivery, which is retried (ADR-0013.R8). One failing action or rule never holds the delivery for the others.
Source: ADR-0058.R10

R16. The execution's outcome follows from its actions:
   - `acted`: at least one `done`, none `refused` or `failed`;
   - `partial`: some `done`, some `refused` or `failed`;
   - `skipped`: every action skipped by design;
   - `failed`: no `done` and at least one `failed`;
   - `refused`: no `done`, at least one `refused` and none `failed`;
   - before any action: `skipped_same_target` or `depth_exceeded`;
   - beyond the flood guard, with no action run: `rate_limited` (ADR-0063.R21; R30).
   Source: ADR-0058.R10

R17. Shadow versions are evaluated the same way and record their would-be actions with outcome `would_act`; nothing runs.
Source: ADR-0058.R10

R18. `RecordAutomationExecution` (internal) writes one row per matched rule version, after its actions (R20).
Source: ADR-0058.R10

R19. Activation returns the check result `automation_same_target_warning` when another active rule has the same trigger and an action on the same target kind, so a person sees that both will act.
Source: ADR-0058.R10

### Execution records

R20. An `automation_execution` row holds: rule and version, `mode` (`live`, `shadow`), event ID and type, the event's business date, subject and the version read, the subject's scope dimensions (branch, warehouse, document) for readers' scope, causation chain and depth, `outcome`, the condition results (field, operator, field class, data label, value read, result), the input hash, each action's kind, command, key, outcome and audit record or error, taint, origin agent run and the owner acted for. In a condition result a personal value is stored as a keyed hash (HMAC-SHA-256 under the company's secret `automation.value_hmac_key`) or omitted, never as a plain hash.
Source: ADR-0058.R11

R21. Not recorded per event: events where a rule's conditions did not match, and subjects outside the owner's scope, which only the daily count of R3 records. `GetAutomationReplay` answers for one event why a rule did not act.
Source: ADR-0058.R11

R22. `ListAutomationExecution`, the agent view `automation_execution_overview` (ADR-0050.R51), `GetAutomationReplay` and the frozen replay diffs of R36 return a row only when the subject is inside the reader's record and owner scope. For a field class the reader lacks they omit the value and that condition's result and set the marker `is_class_filtered` on it (the omission of ADR-0017.R10); they never show a hash in its place. The stated residue: an `acted` outcome still tells such a reader that the conditions held.
Source: ADR-0058.R11

R23. The HMAC key lives in the deployment's secret store, is never in a view or a prompt, and keyed hashes are compared only inside the system. Keys are versioned and never rotated in place: a new key version hashes new values, every stored hash names its key version, old key versions are kept for verification only, and stored values are never re-hashed.
Source: ADR-0058.R11

R24. An agent run reads execution records with its intersection of rights (ADR-0050.R31). The view `automation_execution_overview` has no partner column and so is closed to tainted runs. A drafting agent type never has it on its tool list (R60).
Source: ADR-0058.R11

R25. Execution records are kept as decision records under ADR-0059.R23.
Source: ADR-0058.R11

### Causation chain

R26. Every `outbox_event` and `audit_record` carries `causation_chain_id`, `causation_depth` (no default; the writer always sets it) and `automation_rule_version_id`. The database requires a depth of at least 1 where a rule version is named (ADR-0013.R2, ADR-0038.R2).
Source: ADR-0058.R12

R27. The dispatcher assigns the chain, never the request:
   - a command from a transport, a person or a scheduled job starts a chain (a new UUIDv7, depth 0);
   - a consumer command inherits its event's chain and depth (ADR-0013.R9);
   - an automation action inherits the triggering event's chain with depth plus one and names its rule version;
   - an agent run started from an event (a wake-up, or `start_agent`) inherits that event's chain and depth, and every tool call of the run and every event of its drafts carries them;
   - a run a person starts begins a chain, also on an item a rule raised.
   Source: ADR-0058.R12

R28. The depth cap is 3. The dispatcher refuses an automation action whose depth would exceed 3 with `automation_depth_exceeded` (DS-04 check order, step 2), and the consumer records `depth_exceeded` without trying. A database check keeps `causation_depth` between 0 and 3 on `outbox_event` and `audit_record`. The cap is a core constant, not a setting (ADR-0063.R21).
Source: ADR-0058.R12, ADR-0058.R9.N1

### Circuit breaker

R29. The consumer runs `DisableAutomationRule` with reason `circuit_breaker` when a rule's live executions record, among outcomes `refused`, `failed` or `partial`, either `automation.breaker_failures` (default 5, bounds 1 to 50) within `automation.breaker_window_minutes` (default 60, bounds 5 to 1,440), or `automation.breaker_consecutive` (default 20, bounds 3 to 200, at least the failures) in a row at any rate. Each is a company setting with an optional override in a rule version's content, hashed with it (ADR-0063.R21). The breaker cannot be turned off: no value means never. Skips by design and outcomes `skipped_same_target`, `depth_exceeded` and `rate_limited` do not count. The window is counted on the executions' business date and recorded instant, a declared technical timer of the breaker (ADR-0007.R10, as ADR-0013.R7 declares the delivery timers); the count in a row needs no clock.
Source: ADR-0058.R16, ADR-0058.R16.N1, ADR-0058.R9.N1

R30. The flood guard `automation.max_executions_per_rule_per_hour` (default 500, bounds 10 to 10,000; a rule version may override it) records outcome `rate_limited` and runs no action; `rate_limited` never counts toward the breaker (ADR-0063.R21).
Source: ADR-0058.R16.N1

R31. `DisableAutomationRule` runs under the consumer's registered permission, not the owner's, because the owner may be the one who lost a right. It raises `automation_rule_disabled` for the owner, or for `company_owner` when the owner can no longer open the company.
Source: ADR-0058.R16

R32. A person runs `EnableAutomationRule`, which re-enables the same current version after the checks of ADR-0058.R15; it never changes the version.
Source: ADR-0058.R16

### Replay diff

R33. The replay diff is the evidence of stage `backtest` for automation rules and decision tables. Its window is by default the retained events of the trigger type from the last 30 days (`automation.replay_window_days`, bounds 7 to 90, within the outbox retention, ADR-0063.R20; ADR-0013.R15 keeps 400 days). The window is recorded in the evidence, like every backtest window (R57).
Source: ADR-0058.R23

R34. The candidate and the current version (or none) are evaluated on each event's facts as R13 reads them, with the owner's scope. The replay never runs an action.
Source: ADR-0058.R23

R35. The diff holds the subjects where the outcome differs, each with both outcomes and the actions that would differ, the amounts of the subjects' amount fields, and counts. Events whose trigger is not `is_replayable` are evaluated on current state and counted as `replay_not_reconstructable` (a check result). Events whose subject lies outside the owner's scope are counted, not evaluated, and returned as `automation_owner_scope_limited` (R3). Whoever reads the diff sees it filtered by their own scope and classes (R22).
Source: ADR-0058.R23

R36. `CreateArtifactEvidence` stores the diff in `artifact_promotion_evidence` with the hashes of ADR-0059.R14. There is no pass threshold beyond the minimum count of events (`automation.replay_min_events`, default 20; at 0 the diff is shown without a count gate; ADR-0063.R20): the person who submits the activation reads the diff and vouches for it.
Source: ADR-0058.R23

### Upgrade safety

R37. References in configuration are registry items with a version and a deprecation status. A deprecated item stays usable for at least one minor release.
Source: ADR-0058.R25

R38. At every core or package upgrade the system job `RunArtifactUpgradeCheck` re-validates every current, shadow and still-eligible earlier version of every artifact, runs its tests and a 7-day replay, and repeats the graph check.
Source: ADR-0058.R25

R39. On failure the artifact is deactivated, never left to fail at run time: a rule is disabled (`upgrade_invalid`); a rule that pins an invalid decision table version is disabled with it; a table's pointer for decision points is cleared; a parameter set's pointer falls back to the core defaults (ADR-0059.R4). Each writes a transition `invalidated` and raises `artifact_invalidated` for the owner, with the findings.
Source: ADR-0058.R25

R40. A deprecated reference writes a transition `deprecation_found` with no state change and raises `artifact_reference_deprecated` for the owner, without deactivation.
Source: ADR-0058.R25

### Module split for artifacts

R41. `configuration` (layer 2) owns `parameter_set`, `parameter_set_version`, `parameter_set_value`, `artifact_transition`, `artifact_promotion_evidence`, `artifact_shadow_outcome`, `golden_case_label` and `artifact_monitor_snapshot` (DDL in `docs/design/DS-28-34-configuration-artifacts.sql`), the contract function `get_parameters`, and the pure lifecycle and parameter checks.
Source: ADR-0059.R2

R42. `automation` (layer 5, ADR-0058.R1) owns `CreateArtifactEvidence`, `RunArtifactMonitor` and the queries of ADR-0059.R27 that read layer 3 and layer 4 data. The commands of `configuration` that need its checks call them through the hook `artifact_checks` of ADR-0058.R1.
Source: ADR-0059.R2

R43. The module that owns a tunable function or an L2 kind registers, with its declaration, these pure functions in its contract: `backtest` (the function under one parameter set and another, or one rule version and another, over a window of its own resolved history, inputs as of decision time), `compare` (an outcome against a person's final result) and `monitor` (decisions and overrides over a window). `automation` calls them. For the bank cascade they live in `cash`, as `GetAutoPostShadowEvaluation` does (ADR-0051.R18).
Source: ADR-0059.R2

R44. The evidence hook of `policy` (ADR-0043.R14) has a second function, `auto_post_eligibility`, which `cash` registers and `app` wires: for a `system` posting of a cascade draft it answers whether the draft's line meets ADR-0059.R6, and the policy floor gives `human_post` when it does not. So `policy` imports no layer-4 module.
Source: ADR-0059.R2

R45. The contract of `policy` holds `mark_auto_post_evidence_outdated(company, function_code, by_id)`, which sets `shadow_evidence_outdated_by` on every enabled rule version whose stored evidence names that function (`EnablePolicyRule` stores the function code with the hash). `configuration` declares the hook `artifact_in_force_changed`, which `policy` registers and `app` wires (the pattern of ADR-0022.R2). `configuration` calls it inside the transaction of every pointer move, retirement and failed re-evaluation of a parameter set; `automation` reaches it through the contract of `configuration`, so no module imports `policy` sideways or up.
Source: ADR-0059.R2

R46. No kind gets a new table for lifecycle or evidence: one transition log, one evidence table and one shadow table serve every kind. The generic `artifact_promotion_evidence` is used, not `agent_promotion_evidence`, whose columns (agent type, behavior hash, seat models) belong to agent types; the agent table stays as it is.
Source: ADR-0059.R2

### Moves of an artifact version

R47. `CreateArtifactEvidence` (`automation`, effect class `other`, a person's command, on no agent tool list) computes evidence once (ADR-0059.R14). Stage `backtest` evidence that is sufficient moves a draft to `backtested`; stage `preview` records an attempt that is never sufficient; stage `live` covers a shadow or assisted period.
Source: ADR-0059.R13

R48. `SetArtifactVersionState` (`configuration`, effect class `master_data_change`, change-tracked, `is_proposal_bound`, declared minimum level `full`): raising a version to `shadow`, `assisted` or `active` runs only from an approved change proposal and names evidence (otherwise `proposal_required`, as for `UpdateAgentTypeSetting`). Raising to `assisted` or `active` also moves `current_version_id`; raising to `shadow` sets `shadow_version_id`. Lowering (demotion to `shadow`, retirement) is direct. Retiring the version in force clears the pointer in the same update (the trigger does it), writes a `retired` transition and, for a parameter set, marks the dependent auto-post evidence outdated (ADR-0059.R6). Proposals for it expire after `artifacts.proposal_ttl_days` (company setting, default 30), not `change_proposal_ttl_days`.
Source: ADR-0059.R13

R49. `SetArtifactCurrentVersion` (`configuration`, effect class `other`, level `full`) is the rollback. It moves `current_version_id` to a version of the same artifact whose state is `active` or `assisted`, or to null (core defaults, or none), at once and without evidence, because the target was evidenced when promoted. It repeats the target's validity check and, for automation rules, the graph check of ADR-0058.R15, under the company's configuration lock. A version never promoted returns `artifact_version_not_eligible`, an invalid one `artifact_invalid`.
Source: ADR-0059.R13

R50. The proposal's submitter vouches for the evidence. Its approver is neither the submitter (`approver_is_submitter`, also in the small-company mode) nor the version's drafter, nor the human its drafting run or consumer acted for (`segregation_of_duties`, ADR-0017.R16).
Source: ADR-0059.R13

R51. A version drafted by a tainted run, or derived from untrusted text such as a bank token, is written tainted (ADR-0029.R8, ADR-0029.R10). A person submits it, and the approval is the trust boundary.
Source: ADR-0059.R13

R52. Every move writes an immutable `artifact_transition` row: kind, artifact, version, move (`backtested`, `promoted`, `demoted`, `retired`, `rolled_back`, `disabled`, `enabled`, `invalidated`, `deprecation_found`), states, pointers before and after, evidence, proposal, actor and reason.
Source: ADR-0059.R13

### Time split, no look-ahead

R53. Every draft has a drafting window. A drafting run declares it, and every query it calls is bounded by it. A person's draft declares the data window they used, by default everything up to the draft's date.
Source: ADR-0059.R15

R54. At evidence creation `automation` checks the drafting run's recorded read references (ADR-0050.R19) against each source's declared as-of column and refuses evidence when one is dated after the window (`drafting_window_violated`). Reads of evidence, shadow outcomes and monitor snapshots count by their evaluation window or business date. Undated current-state reads are listed in the bundle. When the drafting run's steps have been dropped (the retention of ADR-0050.R19), evidence is refused (`drafting_run_steps_missing`).
Source: ADR-0059.R15

R55. The evaluation window of a backtest or preview starts strictly after the drafting window ends (`backtest_window_not_after_drafting`; the database holds it).
Source: ADR-0059.R15

R56. A `backtest` may read only tables that the registry declares with an as-of date column (`backtest_source_undated` otherwise). It reconstructs each case's inputs as they were when the decision was made: open items as of the line's value date, partner bank accounts by their validity, documents at their version then. A case whose inputs cannot be reconstructed is left out and counted.
Source: ADR-0059.R15

R57. Every evaluation window is recorded, previews included (stage `preview`), and `window_reuse_count` shows the approver how often the same window was tried.
Source: ADR-0059.R15

### Held-out golden cases

R58. A case is held out when the first byte of the SHA-256 of the UTF-8 text `<company ID>:<case ID>` (both UUIDs in canonical lowercase hyphenated form) is below 51, about one case in five. The assignment is deterministic, and the database checks a label's `is_held_out` against it.
Source: ADR-0059.R16

R59. For a run of a drafting agent type, the query layer excludes the held-out cases from every row query and aggregate the run calls, whether labelled or not: rows of the declared case tables, and rows of other tables whose declared case-reference columns point at a held-out case (the receipt proposed from a held-out line, its lines and settlements). An aggregate that cannot apply the filter is refused (`held_out_filter_unavailable`). Code that fits or searches candidates uses only cases that are not held out. `ListGoldenCaseLabel` is on no tool list.
Source: ADR-0059.R16

R60. A registry CI check refuses a drafting agent type version whose tool list holds a query not registered as held-out filtered. Reads of evidence, shadow outcomes, monitor snapshots, automation executions and `GetAutoPostShadowEvaluation` are on no drafting tool list, because they hold per-case results of the later window.
Source: ADR-0059.R16

R61. The query layer does not filter a person's reads. Evidence records whether the version was drafted by a filtered run or by a person (`drafted_by_filtered_run`).
Source: ADR-0059.R16

R62. As the second line, at evidence creation `automation` intersects the held-out case IDs with every row reference the drafting run recorded (`context_refs`, `result_refs`, `request_refs`), each mapped to its case through the case-reference columns. A non-empty intersection makes the evidence insufficient (`held_out_case_seen`), and the database refuses sufficient evidence with a non-zero count.
Source: ADR-0059.R16

R63. The `auto_post_advisor` agent type is a drafting agent type: its tools `ListAutoPostCase`, `EvaluateAutoPostBacktest` and `ListAutoPostThresholdCandidate` are held-out filtered, its decision table drafts follow the lifecycle of R47 to R52, and its settings proposals carry the backtest as evidence (ADR-0065.R17, ADR-0065.R18). It is a Phase 2 agent type; in Phase 1 people propose gateway settings and tables, and the assistant may draft them on request (ADR-0078.R2, ADR-0078.R8).
Source: ADR-0059.R16.N1, ADR-0059.R16.N2

### Monitor, override rate and drift

R64. Daily, `RunArtifactMonitor` (system job of `automation`) asks the owning module's `monitor` function, for every artifact version in force, for the decisions it made in the trailing 30 days and the overrides: decisions a person changed, reversed or discarded (for the cascade, proposals not posted unchanged). It writes one immutable `artifact_monitor_snapshot` per version and day, with the evidenced rates as the baseline.
Source: ADR-0059.R21

R65. Demotion is judged only over at least 30 decisions; the window is widened as for re-evaluation (ADR-0059.R4) until 30 are reached (ADR-0063.R10). Beyond the demotion threshold of the function or kind (ADR-0059.R18), the job moves the pointer back to the version that was in force before (the promotion's `previous_current_version_id`) when it is still eligible and passes its validity check, otherwise to the core defaults or to none. It demotes the version to `shadow` so it keeps being measured, writes the transition, and raises `artifact_demoted` for the artifact's owner with the figures, naming any auto-post rule whose evidence the demotion outdated (ADR-0059.R6). Promotion back needs new evidence.
Source: ADR-0059.R21, ADR-0059.R21.N1

R66. `RunArtifactMonitor` does not demote agent types. The quality monitor of ADR-0051.R5 follows the setting `agents.<agent_type>.drift_action` (ADR-0063.R10, ADR-0063.R12).
Source: ADR-0059.R21, ADR-0059.R21.N1

## Invariants

The invariants whose catalog source names a rule of this chunk and that no other spec of `automation` already holds; chunk 2 holds the others and cites these by ID. `INV-670`, `INV-671`, `INV-673`, `INV-674`, `INV-686` and `INV-687` stand only in the `configuration` spec (rows in `specs/configuration-1.md`). Area
and first step (`invariants.csv`): `INV-679` and `INV-680` `safety`, `INV-684` and `INV-685` `platform`; first step 5.

| INV | Check point | Statement | Protects |
| --- | --- | --- | --- |
| `INV-679` `artifact_promotions_evidenced` | day | Every `promoted` transition names sufficient evidence of the same version whose content hash, engine version and baseline equalled the version's at execution, from an approved change proposal whose approver was neither its submitter nor the version's drafter nor the human its drafting run acted for. | R48, R50; ADR-0059.R19 |
| `INV-680` `backtests_out_of_sample` | day | Every backtest evidence's evaluation window starts after its version's drafting window; no sufficient evidence has fewer cases than its minimum, a held-out case among its drafting run's recorded reads mapped through the case-reference columns (checked against `drafting_reads_hash` and, while retained, the steps), or a read dated after the drafting window; no drafting agent type version's tool list holds a query that is not held-out filtered. | R54, R55, R60, R62; ADR-0059.R14 |
| `INV-684` `breaches_demote` | day | Every monitor snapshot that breached its threshold has the demotion transition it caused, and no demoted version is in force again without later evidence. | R64, R65 |
| `INV-685` `golden_labels_by_approvers` | day | Every golden case label was recorded by a user who held the approve flag on its function's leaf that day, and its `is_held_out` equals the deterministic assignment (a database check). | R58; ADR-0059.R22 |

## Edge cases

The edge cases whose catalog source names a rule of this chunk and that no other spec of `automation` already holds; chunk 2 holds the others and cites these by ID. `EC-156`, `EC-158`, `EC-159`, `EC-160`, `EC-162` and `EC-167` stand only in the `configuration` spec (rows in `specs/configuration-1.md`). Area: `EC-163` `cash`, `EC-166` `safety`; first executable step 6.

| EC | Name | Case | Outcome | Source |
| --- | --- | --- | --- | --- |
| `EC-163` | `bank_parameters_promoted_then_demoted` | A parameter set for the bank cascade drafted from three months is backtested on the next two, shadowed, promoted with frozen evidence, keeps auto-post off until new evidence under its hash, and is demoted to shadow by override drift a month later; the demotion marks the auto-post rule's evidence outdated, and `EnablePolicyRule` refuses it until a new rule version brings new evidence. | `must_succeed` | ADR-0059.R5, ADR-0059.R6, ADR-0059.R12 to ADR-0059.R21 |
| `EC-166` | `held_out_case_leak` | A drafting run read a held-out golden case; its evidence is insufficient and the promotion is refused. | `must_reject:held_out_case_seen` | ADR-0059.R16 (R62) |

## Settings

The rows of the `automation.*` keys are in chunk 2, with the rules of ADR-0063.R20 and ADR-0063.R21 that define them.
The rules of this chunk use `automation.breaker_failures`, `automation.breaker_window_minutes` and
`automation.breaker_consecutive` (R29), `automation.max_executions_per_rule_per_hour` (R30),
`automation.replay_window_days` (R33), `automation.replay_min_events` (R36) and `automation.dispatch_paused` (R12).

`artifacts.proposal_ttl_days` (R48) has no row in `settings.csv`; chunk 2 states it with the other keys of ADR-0059.R28.
`automation.value_hmac_key` (R20) is a company secret in the deployment's secret store, not a setting.

Reads: `agents.<agent_type>.drift_action` (owned by `agents`; scope `agent_type`; enum `signal`, `pause_new_runs`, `demote_to_shadow`; core default `signal`), used by R66; `change_proposal_ttl_days` (R48).

## UI annotations

The units of this chunk state no floorplan, title, facet, field annotation or tile. Work item kinds of `automation`
that the rules of this chunk raise (rows of `work-item-kinds.csv`; chunk 2 holds `artifact_function_changed` and
`automation_rule_rate_limited`):

| Kind | Subject table | Owner | Due | Resolution | Rule |
| --- | --- | --- | --- | --- | --- |
| `automation_owner_scope_narrowed` | `automation_rule` | `subject_owner:owner_user_id` | `days:5` | `person` | R3, R7 |
| `automation_rule_disabled` | `automation_rule` | `named_by_raiser` | `days:1` | `command`: `EnableAutomationRule` | R6, R31 |
| `automation_notice` | `automation_execution` | `named_by_raiser` | `days:7` | `person` | R10 |
| `artifact_invalidated` | `artifact_transition` | `named_by_raiser` | `days:1` | `person` | R39; ADR-0059.R28 |
| `artifact_reference_deprecated` | `artifact_transition` | `named_by_raiser` | `days:30` | `person` | R40; ADR-0059.R28 |
| `artifact_demoted` | `artifact_transition` | `named_by_raiser` | `days:5` | `person` | R65; ADR-0059.R28 |

None of them is agent-resolvable.

## Conflicts

CONFLICT ADR-0058.R9: the mark flagged on notices reaching only people inside the company is dropped; ADR-0058.R9.N1 confirms the notification path of ADR-0076 and governs R10.
CONFLICT ADR-0058.R10: ADR-0063.R21 adds the execution outcome `rate_limited` of the flood guard to the outcomes of the consumer, and ADR-0063.R20 lets `automation.dispatch_paused` stop the evaluation of events; R12 and R16 state both.
CONFLICT ADR-0058.R16: the fixed threshold of 20 in a row and the flagged defaults (5 failures, 60 minutes) yield to the bounded settings of ADR-0058.R16.N1 (ADR-0063.R21), which ADR-0058.R9.N1 confirms; R29 states them without the mark, with the hard rules of ADR-0063.R21 that the breaker cannot be turned off and that `rate_limited` never counts.
CONFLICT ADR-0058.R23: the fixed replay window of 30 days and the unnamed minimum count of events yield to the bounded settings `automation.replay_window_days` and `automation.replay_min_events` of ADR-0063.R20; R33 and R36 state them.
CONFLICT ADR-0059.R21: the sentence that the agent quality monitor keeps only signalling yields to ADR-0059.R21.N1, under which agent types follow the drift action setting of ADR-0063.R12; R66 states it. Demotion is judged only over at least 30 decisions, with the window widened until they are reached, under ADR-0063.R10; R65 states it.

## Proposed (not law)

None

## Trace

| Source | Where |
| --- | --- |
| ADR-0058.R9 | R1-R11 |
| ADR-0058.R9.N1 | R10, R28, R29 |
| ADR-0058.R10 | R12-R19 |
| ADR-0058.R11 | R20-R25 |
| ADR-0058.R12 | R26-R28 |
| ADR-0058.R16 | R29, R31, R32 |
| ADR-0058.R16.N1 | R29, R30 |
| ADR-0058.R23 | R33-R36 |
| ADR-0058.R25 | R37-R40 |
| ADR-0059.R2 | R41-R46 |
| ADR-0059.R13 | R47-R52 |
| ADR-0059.R15 | R53-R57 |
| ADR-0059.R16 | R58-R62 |
| ADR-0059.R16.N1 | R63 |
| ADR-0059.R16.N2 | R63 |
| ADR-0059.R21 | R64-R66 |
| ADR-0059.R21.N1 | R65, R66 |
