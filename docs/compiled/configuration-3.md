Module: configuration    Chunk: 3 of 3    Source ADRs: ADR-0059, ADR-0063, ADR-0066
Build step(s): 1, 3, 5    Generated from index: 30d5706    Compiled by: Claude Fable 5.2, 2026-11-21

# `configuration` compiled spec, chunk 3: lifecycle moves, evidence, thresholds, golden cases, ADR-0059 commands and catalog rows, automation settings

## Purpose

`configuration` (layer 2) owns the versioned decision artifacts of a company: automation rules, decision tables and parameter sets, with their lifecycle, evidence and transition log. This chunk states the lifecycle moves and who makes them, the evidence bundle, the time split and the held-out golden cases, the thresholds per function, stale evidence, gates, golden case labels, retention, the rule on AI-written code, the commands and catalog rows of ADR-0059, the automation settings and the automation action `open_work_case`. The artifact kinds, states and parameter sets stand in chunk 2, automation rules and decision tables in chunk 1. `automation` computes evidence and runs the monitor (ADR-0059.R21); its rule is traced `ref:` and not restated.

## Entities and tables

DDL: `docs/design/DS-28-34-configuration-artifacts.sql`.

| Table | Meaning | Key | Parent | Owner |
| --- | --- | --- | --- | --- |
| `artifact_transition` | Immutable log: one row per lifecycle or pointer move of an artifact of any kind (R408) | `id`; (`company_id`, `id`) unique | `company`; names `artifact_promotion_evidence` and `change_proposal` | `configuration` |
| `artifact_promotion_evidence` | Immutable evidence bundle of any kind, computed once by `CreateArtifactEvidence`; also the re-evaluations of ADR-0059.R4 (R409 to R415) | `id`; (`company_id`, `id`) unique | `company` | `configuration` |
| `golden_case_label` | Company data, append-only: a person's label of the expected outcome of one case of a function (R438) | `id`; (`company_id`, `id`) unique; (`company_id`, `function_code`, `case_table`, `case_id`) unique while `retired_at` is null | `company` | `configuration` |
| `artifact_monitor_snapshot` | Immutable: one row per artifact version in force and day, written by `RunArtifactMonitor` (ADR-0059.R21) | `id`; (`artifact_version_id`, `window_to`) unique | `company`; names the `artifact_transition` a breach caused | `configuration` |

Named by this chunk, with their rows in other chunks: `artifact_shadow_outcome`, `parameter_set` (chunk 2); `decision_table`, `automation_rule` (chunk 1).

Reads: `change_proposal`, `user_account`, `company`, `agent_run`, `setting_value`, `extension_point`, `bank_matching_rule`, `agent_type`.

## Commands and queries

Authorization is that of the leaf `configuration` (function, parent `administration`) of `authorization-areas.csv`, unless the cell names another.

| Name | Actor and authorization | Input | Effect | Events | Error codes |
| --- | --- | --- | --- | --- | --- |
| `CreateParameterSet`, `UpdateParameterSet` | `configuration` at `edit` (drafts); effect class `master_data_change` | Function code and owner | Creates or changes a `parameter_set` | not stated | not stated |
| `CreateParameterSetVersion`, `UpdateParameterSetVersion`, `DeleteParameterSetVersion` | `configuration` at `edit`; effect class `other`; `is_draft_only` | A draft version and its values | Drafts only; bounds and order checked | not stated | not stated |
| `SetArtifactVersionState` | `configuration` at `full` (declared minimum level `full`); effect class `master_data_change`; change-tracked; `is_proposal_bound` for raising; on no agent tool list | Artifact version, target state, evidence | Raises or lowers a version's state and moves the pointers (R402, R403); calls the pure validators and the hook `artifact_checks` (ADR-0058.R1) | not stated | `proposal_required`, `artifact_evidence_stale`, `approver_is_submitter`, `segregation_of_duties`, `artifact_invalid` |
| `SetArtifactCurrentVersion` | `configuration` at `full`; effect class `other`; on no agent tool list | Artifact and a target version, or null | Rollback of `current_version_id` (R405); calls the pure validators and the hook `artifact_checks` (ADR-0058.R1) | not stated | `artifact_version_not_eligible`, `artifact_invalid` |
| `RecordGoldenCaseLabel` | A person with the approve flag on the labelled function's own leaf; effect class `other`; on no agent tool list | Function code, case table and ID, expected outcome | Appends a `golden_case_label` (R437, R438) | not stated | `golden_label_not_permitted` |
| `GetParameterSet`, `ListDecisionArtifact`, `ListArtifactEvidence`, `GetArtifactEvidence`, `ListArtifactTransition`, `ListArtifactMonitorSnapshot` (queries) | Modules `automation`, `configuration`; filtered by the reader's rights; artifact evidence, transitions and monitor snapshots at `read` on the leaf `automation` | not stated | Read | none | not stated |
| `ListGoldenCaseLabel` (query) | `configuration`; on no agent tool list | not stated | Read | none | not stated |
| `GetArtifactVersionContent` (query) | not stated | An artifact version | Returns the version's canonical JSON and content hash (R460) | none | not stated |

The rows of the commands and queries that ADR-0058.R27 registers for `configuration` (automation rules, decision tables, `DisableAutomationRule`, `EnableAutomationRule`, `GetArtifactValidation`) are in chunk 2.

Commands of other modules that this chunk's rules name: `CreateArtifactEvidence` and `RunArtifactMonitor` (`automation`), `CreateBankMatchingRuleVersion` (`cash`), `CreateWorkCase` (R461), `UpdateAgentTypeSetting`.

Error codes bound to no command of `configuration`: `artifact_evidence_insufficient`, `auto_post_evidence_outdated`, `parameter_out_of_bounds`, `parameter_order_violated`; raised at evidence creation by `automation`: `drafting_window_violated`, `drafting_run_steps_missing`, `backtest_window_not_after_drafting`, `backtest_source_undated`, `held_out_case_seen`; raised by the query layer: `held_out_filter_unavailable`.

## Rules

### Lifecycle moves and who makes them

R401. `CreateArtifactEvidence` (`automation`, effect class `other`, a person's command, on no agent tool list) computes evidence once (R409 to R415). Stage `backtest` evidence that is sufficient moves a draft to `backtested`; stage `preview` records an attempt that is never sufficient; stage `live` covers a shadow or assisted period.
Source: ADR-0059.R13

R402. `SetArtifactVersionState` (`configuration`, effect class `master_data_change`, change-tracked, `is_proposal_bound`, declared minimum level `full`) raises a version to `shadow`, `assisted` or `active` only from an approved change proposal and names evidence; otherwise it returns `proposal_required`, as for `UpdateAgentTypeSetting`. Raising to `assisted` or `active` also moves `current_version_id`; raising to `shadow` sets `shadow_version_id`.
Source: ADR-0059.R13

R403. Lowering through `SetArtifactVersionState` (demotion to `shadow`, retirement) is direct. Retiring the version in force clears the pointer in the same update (the trigger does it), writes a `retired` transition and, for a parameter set, marks the dependent auto-post evidence outdated (ADR-0059 rule 6).
Source: ADR-0059.R13

R404. Proposals for `SetArtifactVersionState` expire after `artifacts.proposal_ttl_days` (company setting, default 30) instead of `change_proposal_ttl_days`.
Source: ADR-0059.R13

R405. `SetArtifactCurrentVersion` (`configuration`, effect class `other`, level `full`) is the rollback. It moves `current_version_id` to a version of the same artifact whose state is `active` or `assisted`, or to null (core defaults, or none), at once and without evidence, because the target was evidenced when promoted. It repeats the target's validity check and, for automation rules, the graph check of ADR-0058.R15, under the company's configuration lock. A version never promoted returns `artifact_version_not_eligible`, an invalid one `artifact_invalid`.
Source: ADR-0059.R13

R406. Segregation: the proposal's submitter vouches for the evidence. Its approver is neither the submitter (`approver_is_submitter`, also in the small-company mode) nor the version's drafter, nor the human its drafting run or consumer acted for (`segregation_of_duties`, ADR-0017.R16).
Source: ADR-0059.R13

R407. Taint: a version drafted by a tainted run, or derived from untrusted text such as a bank token, is written tainted (ADR-0029.R8, ADR-0029.R10); a person submits it, and the approval is the trust boundary.
Source: ADR-0059.R13

R408. Every move writes an immutable `artifact_transition` row: kind (`artifact_kind`), artifact, version, `move` (`backtested`, `promoted`, `demoted`, `retired`, `rolled_back`, `disabled`, `enabled`, `invalidated`, `deprecation_found`), states (`from_state`, `to_state`), pointers before and after (`previous_current_version_id`, `new_current_version_id`), evidence, proposal, actor and reason.
Source: ADR-0059.R13

### The evidence bundle

R409. `artifact_promotion_evidence` is the immutable evidence bundle. Its identity is kind, artifact, version, `stage` (`backtest`, `preview`, `live`, `reevaluation`) and the `content_hash` of the version. A re-evaluation of core defaults names the function code and the company instead of an artifact and version.
Source: ADR-0059.R14

R410. The bundle records what ran: `engine_version` (the function version, or the registry version for rules and tables) and the baseline, which is the version in force at creation and its hash (the core defaults' hash, or the hash of nothing).
Source: ADR-0059.R14

R411. The bundle records the windows: the version's drafting window and the evaluation window; `case_count` and the declared `min_case_count`; `data_window_hash`, the SHA-256 of the sorted IDs of the cases evaluated; and `window_reuse_count`, the number of earlier evidence rows of any stage for the same artifact whose evaluation windows overlap this one, which the proposal shows.
Source: ADR-0059.R14

R412. The bundle records golden cases and reads: `golden_set_hash`, the held-out case count (`held_out_case_count`), the count of held-out cases found in the drafting run's reads (`held_out_seen_count`, R425), and `drafting_reads_hash`, the SHA-256 of the drafting run's recorded read references, frozen so the check survives the steps' retention.
Source: ADR-0059.R14

R413. The bundle's `figures` are computed against the baseline. For a scorer: precision of acted and of suggested decisions, coverage, abstentions, decisions that change (count and money value), false acted decisions in money terms, and the precision and coverage curve at each candidate threshold. For rules and tables: the replay diff. For live evidence: the comparator's agreement. The undated current-state reads are listed.
Source: ADR-0059.R14

R414. The bundle also holds the changed sample (`changed_sample`, R427), the thresholds applied (R428), `is_sufficient`, `drafted_by_filtered_run` (R424), and who created it: a person, or for a re-evaluation the monitor job (`created_by_kind` `system`).
Source: ADR-0059.R14

R415. The database holds that sufficient evidence has at least `min_case_count` cases (which is at least 1), that previews and re-evaluations are never sufficient, and that a sample holds at most 20 decisions.
Source: ADR-0059.R14

### Time split, no look-ahead

R416. Every draft has a drafting window, so no version is without one. A drafting run declares it, and every query it calls is bounded by it. A person's draft declares the data window they used, by default everything up to the draft's date.
Source: ADR-0059.R15

R417. Look-ahead in reads: at evidence creation `automation` checks the drafting run's recorded read references (ADR-0050.R19) against each source's declared as-of column and refuses evidence when one is dated after the window (`drafting_window_violated`). Reads of evidence, shadow outcomes and monitor snapshots count by their evaluation window or business date. Undated current-state reads are listed in the bundle. When the drafting run's steps have been dropped (the retention of ADR-0050.R19), evidence is refused (`drafting_run_steps_missing`).
Source: ADR-0059.R15

R418. Out of sample: the evaluation window of a `backtest` or `preview` starts strictly after the drafting window ends (`backtest_window_not_after_drafting`; the database holds it).
Source: ADR-0059.R15

R419. Dated sources only: a `backtest` may read only tables that the registry declares with an as-of date column (`backtest_source_undated` otherwise). It reconstructs each case's inputs as they were when the decision was made: open items as of the line's value date, partner bank accounts by their validity, documents at their version then. A case whose inputs cannot be reconstructed is left out and counted.
Source: ADR-0059.R15

R420. Every evaluation window is recorded, previews included (stage `preview`), and `window_reuse_count` shows the approver how often the same window was tried.
Source: ADR-0059.R15

### Held-out golden cases

R421. A case is held out when the first byte of the SHA-256 of the UTF-8 text `<company ID>:<case ID>` (both UUIDs in canonical lowercase hyphenated form) is below 51, about one case in five. The assignment is deterministic, so nobody chooses it, and the database checks a label's `is_held_out` against it.
Source: ADR-0059.R16

R422. For a run of a drafting agent type, the query layer excludes the held-out cases from every row query and aggregate the run calls, whether labelled or not: rows of the declared case tables, and rows of other tables whose declared case-reference columns point at a held-out case (the receipt proposed from a held-out line, its lines and settlements). An aggregate that cannot apply the filter is refused (`held_out_filter_unavailable`). Code that fits or searches candidates uses only cases that are not held out. `ListGoldenCaseLabel` is on no tool list.
Source: ADR-0059.R16

R423. A registry CI check refuses a drafting agent type version whose tool list holds a query not registered as held-out filtered. Reads of evidence, shadow outcomes, monitor snapshots, automation executions and `GetAutoPostShadowEvaluation` are on no drafting tool list, because they hold per-case results of the later window.
Source: ADR-0059.R16

R424. The query layer does not filter a person's reads. Evidence records whether the version was drafted by a filtered run or by a person (`drafted_by_filtered_run`), so the approver knows what "held-out" means for it.
Source: ADR-0059.R16

R425. As the second line, at evidence creation `automation` intersects the held-out case IDs with every row reference the drafting run recorded (`context_refs`, `result_refs`, `request_refs`), each mapped to its case through the case-reference columns. A non-empty intersection makes the evidence insufficient (`held_out_case_seen`), and the database refuses sufficient evidence with a non-zero count.
Source: ADR-0059.R16

R426. The `auto_post_advisor` agent type is a drafting agent type of Phase 2: its tools `ListAutoPostCase`, `EvaluateAutoPostBacktest` and `ListAutoPostThresholdCandidate` are held-out filtered, its decision table drafts follow this lifecycle, and its settings proposals carry the backtest as evidence (ADR-0065.R17, ADR-0065.R18). In Phase 1 people propose gateway settings and tables, and the assistant may draft them on request (ADR-0078.R2, ADR-0078.R8).
Source: ADR-0059.R16.N1, ADR-0059.R16.N2

### Baseline, changed sample and thresholds

R427. The figures compare the candidate with the version in force on the same cases. Up to 20 changed decisions are sampled for inspection, chosen by sorting the changed case IDs by SHA-256 of (evidence data window hash, case ID), so the same evidence always shows the same sample. The proposal shows the diff, not only totals.
Source: ADR-0059.R17

R428. Each tunable function declares its stages and neutral thresholds, and each L2 kind its own; companies set them as settings `artifacts.<function code or kind>.<threshold>`, never below the declaration's small-company minimum. The case minimums and the evidence window are registered settings with bounds that never go below the small-company minimum (section Settings; ADR-0063 rule 10). The precision targets, the held-out golden-case threshold, the demotion formula and the held-out share stay the declared values of R429 to R433 (open question); those values are proposals, flagged for the author. The small-company minimums never lower the evidence of ADR-0051.R18 for enabling auto-post (300 proposals over two statement months).
Source: ADR-0059.R18, ADR-0059.R18.N1

R429. Declared thresholds of `cash.match_bank_line`:
- Backtest: ≥ 200 cases over ≥ 28 days (small-company minimum 50).
- Live (shadow or assisted): ≥ 100 compared cases over ≥ 10 business days (minimum 30).
- Promote when: suggested-decision precision is not below the baseline's and ≥ 95%; coverage loss ≤ 5 points; held-out golden ≥ 95% over at least 20 held-out cases (minimum 10); an acting path follows `auto_post.max_error_rate` (ADR-0063 rule 10).
- Demote when: over 30 days and ≥ 100 decisions (minimum 30), the override rate is ≥ the larger of twice the evidenced rate and the evidenced rate plus 5 points, or the acted share moved by more than 10 points.
Source: ADR-0059.R18, ADR-0059.R18.N1

R430. Declared thresholds of the kind `matching_rule`: backtest ≥ 1 later line, none matched elsewhere; live ≥ 10 suggest-mode drafts; promote on live evidence with ≥ 99% posted unchanged; demote when any confirm-mode match was changed by a person within 30 days.
Source: ADR-0059.R18

R431. Declared thresholds of the kinds `decision_table` and `automation_rule`: backtest is a replay over `automation.replay_window_days` of retained events (core default 30) that holds at least `automation.replay_min_events` events (core default 20; at 0 the diff is shown without a count gate), the settings of ADR-0063.R20 (R459); live evidence is optional; promote when the version is valid, its tests pass, the graph check passes and the submitter has read the diff; demote when an upgrade makes it invalid (ADR-0058.R25), and for rules by the breaker.
Source: ADR-0059.R18

R432. Declared thresholds of the kinds `report_definition` and `analysis_definition`: backtest ≥ 1 hand-checked cell; no live stage; promote when every checked cell equals; no demotion threshold.
Source: ADR-0059.R18

R433. Declared thresholds of the kind `extraction_mapping`: backtest ≥ 50 documents over ≥ 28 days; live ≥ 50 documents; promote at field agreement ≥ 95%; demote when the override rate is ≥ the evidenced rate plus 5 points.
Source: ADR-0059.R18

R434. Executing a promotion re-reads no figures. It checks that the version's content hash, the engine version and the baseline (the version in force and its hash) still equal the evidence's; otherwise it returns `artifact_evidence_stale`, and new evidence is needed. A function release does not demote a version already in force, because core CI tests the function on its golden sets and the re-evaluation (ADR-0059.R4) and the monitor (ADR-0059.R21) watch it, but it makes every pending evidence for that function stale.
Source: ADR-0059.R19

### Thresholds of a scorer and deterministic gates

R435. A scorer has the thresholds show (a suggestion or draft is made) and act (the system may act without a person). Both are calibrated on the company's own outcomes: the evidence holds the precision and coverage curve, and a promotion picks thresholds that meet the function's precision. Act is null (off) by default. Below show, the case abstains to a person.
Source: ADR-0059.R20

R436. Gate fields are an allowlist. Conditions, decision table inputs, scorer inputs and gates read only fields that the registry declares `is_gate_field`: deterministic fields. CI derives LLM lineage from the output schemas: a field that an LLM step's output fills, directly or through any computation, is never declared a gate field (a registry check). Values that agents draft into documents are covered by taint and by ADR-0029.R12, not by this list. An LLM's self-reported confidence is never a gate, and output schemas hold no confidence field (ADR-0050.R35).
Source: ADR-0059.R20

### Golden case labels and retention

R437. A golden case label is recorded by a person who holds the approve flag on the authorization leaf the function declares (ADR-0054.R7), checked at `RecordGoldenCaseLabel` (`golden_label_not_permitted`).
Source: ADR-0059.R22

R438. `golden_case_label` (company data) holds the function code (`function_code`), case table and ID (`case_table`, `case_id`), expected outcome (`expected`), `is_held_out` (R421), labeller and date (`labelled_by_user_id`, `labelled_on`). Labels are append-only; a correction retires the old label (`retired_at`, set once) and records a new one.
Source: ADR-0059.R22

R439. The core ships synthetic golden sets only (ADR-0050.R39). Company labels never enter the repository (D16).
Source: ADR-0059.R22

R440. Artifact versions, transitions, evidence, shadow outcomes, automation executions, monitor snapshots, golden labels, the decision records that name an artifact version and `setting_value` rows (ADR-0063 rule 2) follow the audit retention of ADR-0038: never deleted in Phase 1. A regime may require a longer minimum for decision records as package configuration (ADR-0016.R6), never a shorter one; the core names no regime.
Source: ADR-0059.R23, ADR-0059.R23.N1

### AI-written code (L3)

R441. In Phase 1 no AI-written code runs in production, and no artifact holds code, a script, an expression or SQL.
Source: ADR-0059.R24

R442. AI may write code for the core or a package only as a source change, like any other change (ADR-0003, ADR-0022): tests first, static analysis, CI with the invariant harness, the golden sets and the replay suite, and mechanical assurance and two independent model reviews, behind branch protection with no override; the author reviews behavior at the gates (ADR-0073 rules 11 to 19). AI-written code never runs except through the repository. This also changes the hard lock of ADR-0063 rule 6 for repository code (author, 2026-11-18).
Source: ADR-0059.R24, ADR-0059.R24.N2

R443. Sandboxed extensions come after Phase 1 and are an author decision (open question): pure extension functions with typed inputs and outputs, with no input or output and capped CPU, memory and time, reviewed tests first and consumed as proposals by core code. Phase 1 ships only the `extension_point` registry; after Phase 1 the runtime is WebAssembly with fuel metering under `extensions.wasm_enabled` and per-point budgets (ADR-0063 rule 19). Spec 16's builder pipeline is their path.
Source: ADR-0059.R24, ADR-0059.R24.N1

### Cross-cutting confirmations

R444. Unchanged, as already in ADR-0050 and ADR-0051: workflow first and code-set gates (ADR-0051.R3), the taint model with fixed plans (ADR-0050 rules 25 to 28), human approval of proposals with diffs (ADR-0029.R1), budgets and breakers (ADR-0050 rules 22 to 24), deterministic comparators before the eval judge (ADR-0050.R39). Calibrated abstention is the show threshold of R435.
Source: ADR-0059.R26

R445. A seat's model is a pinned snapshot identifier, never an alias, so a provider's change under one name is a seat change with its evaluation (ADR-0050 rule 5 note).
Source: ADR-0059.R26

R446. Generated tool definitions state each tool's side-effect class (`read` for queries, `draft` for `is_draft_only` commands; agents get no other class) and its allowed states as preconditions, enforced by the dispatcher, not by the description (ADR-0050 rule 29 note).
Source: ADR-0059.R26

R447. Spans of agent runs, LLM calls, tool calls and automation executions use the OpenTelemetry GenAI attribute names where they exist and carry the command request ID, agent run ID, work item ID and automation execution ID, values excluded (ADR-0038 rule 10 note).
Source: ADR-0059.R26

R448. One registry: `ListDecisionArtifact` and the view `decision_artifact_overview` list agent types with their settings and every artifact with its kind, owner, state, version in force and last monitor result, filtered by the reader's rights (ADR-0050 rule 51 note).
Source: ADR-0059.R26

R449. Information-flow labels on derived values stay a direction, flagged to revisit after Phase 1.
Source: ADR-0059.R26

### Commands, queries and catalog rows

R450. Commands and queries of the artifact lifecycle, each with its module, effect class and notes:
- `CreateParameterSet`, `UpdateParameterSet`: `configuration`, `master_data_change`; function code and owner.
- `CreateParameterSetVersion`, `UpdateParameterSetVersion`, `DeleteParameterSetVersion`: `configuration`, `other`; drafts only, `is_draft_only`; bounds and order checked.
- `CreateBankMatchingRuleVersion`: `cash`, `other`; drafts only, `is_draft_only`; the consumer's carrier (ADR-0059 rule 10).
- `CreateArtifactEvidence`: `automation`, `other`; a person's command, on no agent tool list; stages `backtest`, `preview`, `live`.
- `SetArtifactVersionState`: `configuration`, `master_data_change`; `is_proposal_bound` for raising; minimum level `full`.
- `SetArtifactCurrentVersion`: `configuration`, `other`; rollback; level `full`.
- `RecordGoldenCaseLabel`: `configuration`, `other`; approve flag on the function's leaf.
- `RunArtifactMonitor`: `automation`, `other`; daily system job, also the release re-evaluation; `is_internal_only`.
- `GetParameterSet`, `ListDecisionArtifact`, `ListArtifactEvidence`, `GetArtifactEvidence`, `ListArtifactTransition`, `ListArtifactMonitorSnapshot`: `automation`, `configuration`; queries, filtered by the reader's rights.
- `ListGoldenCaseLabel`: `configuration`; query, on no agent tool list.
Source: ADR-0059.R27

R451. `CreateArtifactEvidence`, `SetArtifactVersionState`, `SetArtifactCurrentVersion`, `RecordGoldenCaseLabel` and `ListGoldenCaseLabel` join the list of ADR-0050.R30 of commands never on a tool list.
Source: ADR-0059.R27

R452. Error codes (DS-04) by class:
- precondition: `artifact_evidence_insufficient`, `artifact_evidence_stale`, `artifact_version_not_eligible`, `drafting_window_violated`, `drafting_run_steps_missing`, `held_out_case_seen`, `auto_post_evidence_outdated`;
- validation: `backtest_window_not_after_drafting`, `backtest_source_undated`, `parameter_out_of_bounds`, `parameter_order_violated`;
- permission: `golden_label_not_permitted`, `held_out_filter_unavailable`.
Source: ADR-0059.R28

R453. Work item kinds of module `automation`, each resolved by a person:
- `artifact_demoted`, `artifact_invalidated` and `artifact_reference_deprecated`: subject `artifact_transition`; owner the artifact's owner, named by the raiser; due `days:5`, `days:1` and `days:30`.
- `artifact_function_changed`: subject the re-evaluation in `artifact_promotion_evidence`; owner named by the raiser: the set's owner, `company_owner` under core defaults, and each dependent auto-post rule's owner, one item per owner with the owner in its key; due `days:5`.
Source: ADR-0059.R28

R454. Company settings of the artifact lifecycle are `artifacts.<function code or kind>.<threshold>` for the values of R428 and `artifacts.proposal_ttl_days` (30). Declared per function, for `cash.match_bank_line`: `reevaluation_window_days` (60), `reevaluation_max_window_days` (180) and `reevaluation_min_cases` (50).
Source: ADR-0059.R28

R455. The invariants of the artifact lifecycle are `INV-677`, `INV-678`, `INV-679`, `INV-680`, `INV-681`, `INV-682`, `INV-683`, `INV-684` and `INV-685`, and its edge cases are `EC-163`, `EC-164`, `EC-165`, `EC-166` and `EC-168`, all in the block of ADR-0058 rule 28; their statements are the rows of `invariants.csv` and `edge-cases.csv` (sections Invariants and Edge cases of this module's chunks).
Source: ADR-0059.R28

R456. The lab check `t23_ai_artifacts.py` of the validation lab covers, as pure functions:
- lifecycle moves allowed and refused for each ladder; the pointer and rollback;
- the backtest window strictly after the drafting window, the default window of a person's draft, minimum case counts and window reuse;
- held-out cases assigned deterministically, filtered from the drafting run's queries through case tables and case-reference columns, the closed drafting tool list, a path property test and the schema-derived path check, and the check by ID sets;
- evidence frozen by hash and promotion refused on a stale content, engine or baseline hash; the changed sample;
- parameter bounds, safety caps and order constraints; the reduced cascade under different parameter sets, with the parameters hash excluding the function version, tied matches never acting, assisted never acting from the line's state, evidence marked outdated by a demotion and refused at enabling, the re-evaluation's pass rule with `too_few_cases` and the one-step widening to the smallest sufficient window up to the maximum, and unverified drafts never acting;
- the scorer's show and act thresholds and their calibration; the gate-field allowlist with LLM lineage; demotion on override drift to the version in force before;
- matching rules in suggest and confirm mode with step 3–4 scores and caps, and account rules with the token shape, sign and ambiguity checks.
With `--load` it checks: the evidence, transition, shadow and monitor rows immutable; the out-of-sample, minimum-count, preview, held-out and sample checks; labels append-only with `is_held_out` checked by hash; parameter values bounded with safety caps not null. The result is recorded as the next lab finding of the validation lab README.
Source: ADR-0059.R29

### Automation settings

R457. Levels 1 and 3 of spec 16 are in Phase 1, as ADR-0058 has them. The spec texts are the author's (open question): spec 16 should split level 1 into 1a (Phase 1: settings, parameter sets, policy thresholds, approval pools, decision tables) and 1b (after Phase 1: user-defined fields and tables), and say level 3 is "structured rules over a registry vocabulary, no rule language", controlled by stored tests, a replay diff and a change proposal; spec 10 should say "no rule language; structured decision tables and automation rules (ADR-0058)".
Source: ADR-0063.R20

R458. `automation.dispatch_paused` is a company setting, default false. Pausing is one person with `edit` on `configuration`, at once; resuming is a proposal. While paused the automation consumer acknowledges events without evaluating them, and nothing is replayed on resume.
Source: ADR-0063.R20

R459. Company settings of automation: `automation.max_active_rules` (200, bounds 1 to 1,000), `automation.replay_window_days` (30, bounds 7 to 90, within the outbox retention) and `automation.replay_min_events` (20, bounds 0 to 1,000; at 0 the diff is shown without a count gate).
Source: ADR-0063.R20

R460. Export and import as draft (flagged): `GetArtifactVersionContent` returns a version's canonical JSON and content hash. Another deployment of the same customer imports it only as a new draft through the kind's draft command, recording the source hash, and the draft then runs its own tests, replay and proposal on that deployment's data.
Source: ADR-0063.R20

R461. ADR-0058 gains the automation action `open_work_case` (mode `by_rule` of work cases): kind, origin from the triggering subject, and owner by `named_by_raiser`. It runs `CreateWorkCase` as `system` on behalf of the rule's owner, who needs `CreateWorkCase` and read rights on the subject (ADR-0058.R9). A rule may open only a kind whose mode is `by_rule` or `auto`.
Source: ADR-0066.R7

## Invariants

Statements are those of `invariants.csv`; each row stands once in the module, here when its catalog source names a rule of this chunk or a rule no chunk of the module states. First step 5 for each, 6 for `INV-682`. The row of `INV-677` is in chunk 1, the rows of `INV-678` and `INV-681` in chunk 2.

| Invariant | Name | Check point | Statement | Protects |
| --- | --- | --- | --- | --- |
| `INV-671` | `causation_depth_bounded` | day | Every outbox event and audit record has `causation_depth` between 0 and 3, and at least 1 where it names a rule version; every audit record with an `automation_rule_version_id` has its triggering event's chain and that event's depth plus one; every consumer command, and every tool call of an agent run started from an event, has that event's chain and depth. | ADR-0058.R12 |
| `INV-679` | `artifact_promotions_evidenced` | day | Every `promoted` transition names sufficient evidence of the same version whose content hash, engine version and baseline equalled the version's at execution, from an approved change proposal whose approver was neither its submitter nor the version's drafter nor the human its drafting run acted for. | R402, R406, R434 |
| `INV-680` | `backtests_out_of_sample` | day | Every backtest evidence's evaluation window starts after its version's drafting window; no sufficient evidence has fewer cases than its minimum, a held-out case among its drafting run's recorded reads mapped through the case-reference columns (checked against `drafting_reads_hash` and, while retained, the steps), or a read dated after the drafting window; no drafting agent type version's tool list holds a query that is not held-out filtered. | R415, R417, R418, R423, R425 |
| `INV-682` | `auto_post_parameters_evidenced` | day | Every bank document posted by `system` from a cascade proposal has a line that carries the parameters hash its auto-post rule's enabling evidence names, `match_parameter_state` `active` or `core_default`, `match_is_tied` false and no `counterparty_unverified` or `paid_by_third_party` flag, and that rule version's `shadow_evidence_outdated_by` is null; every demotion, rollback, invalidation or failed re-evaluation of the parameter set set it on every dependent rule version in its own transaction. | ADR-0059.R6; ADR-0043.R14 |
| `INV-683` | `gates_read_gate_fields` | day | No condition field, decision table input or scorer gate reads a field that is not registered `is_gate_field`, and no gate field has LLM lineage. | R436 |
| `INV-684` | `breaches_demote` | day | Every monitor snapshot that breached its threshold has the demotion transition it caused, and no demoted version is in force again without later evidence. | ADR-0059.R21 |
| `INV-685` | `golden_labels_by_approvers` | day | Every golden case label was recorded by a user who held the approve flag on its function's leaf that day, and its `is_held_out` equals the deterministic assignment (a database check). | R421, R437 |

## Edge cases

Statements are those of `edge-cases.csv`, placed as the invariants are. First executable step 6 for each, 5 for `EC-162`. The rows of `EC-163` and `EC-164` are in chunk 2.

| Edge case | Name | Case | Outcome | Rules |
| --- | --- | --- | --- | --- |
| `EC-162` | `upgrade_invalidates_rule` | An upgrade removes a condition field after its deprecation window; the rule is disabled with `upgrade_invalid` and its owner gets `artifact_invalidated`; nothing fails at run time. | `must_succeed` | ADR-0058.R25 |
| `EC-165` | `bank_token_rule_suggest_then_confirm` | A bank token rule is written as a draft version, waits for a later line, is approved into suggest mode by a second person, drafts without a score, and moves to confirm mode on live evidence with its score from steps 3-4; a line naming another partner's reference stays a suggestion. | `must_succeed` | ADR-0059.R10 |
| `EC-166` | `held_out_case_leak` | A drafting run read a held-out golden case; its evidence is insufficient and the promotion is refused. | `must_reject:held_out_case_seen` | R425 |
| `EC-168` | `bank_account_rule` | A bank-fee token rule maps to the bank charges account; an outflow with the whole token drafts to that account at `cap_company_rule` under the unverified-counterparty cap, flagged `counterparty_unverified` and never auto-posted; an inflow with it only suggests, and more than one rule on one line suggests. | `must_succeed` | ADR-0059.R10 |

## Settings

Rows of `settings.csv` (leaf `configuration`, storage `setting_value`, change effect `immediate`; area `autonomy` for the `artifacts.*` keys, `automation` for the others). The rows of the breaker keys and of the flood guard are in chunk 1.

| Key | Type | Scopes | Core default | Bounds | Direction | Rule |
| --- | --- | --- | --- | --- | --- | --- |
| `artifacts.<function_or_kind>.max_window_days` | integer | `company` | 90 | 28..365 | `lower_tighter` | R428; ADR-0059.R4.N1 |
| `artifacts.cash.match_bank_line.min_backtest_cases` | integer | `company` | 200 | 50..5000 | `higher_tighter` | R428, R429 |
| `artifacts.cash.match_bank_line.min_live_cases` | integer | `company` | 100 | 30..5000 | `higher_tighter` | R428, R429 |
| `automation.dispatch_paused` | boolean | `company` | false | true or false | `true_tighter` | R458 |
| `automation.max_active_rules` | integer | `company` | 200 | 1..1000 | `lower_tighter` | R459 |
| `automation.replay_window_days` | integer | `company` | 30 | 7..90 | `higher_tighter` | R431, R459 |
| `automation.replay_min_events` | integer | `company` | 20 | 0..1000 | `higher_tighter` | R431, R459 |

`artifacts.proposal_ttl_days` (company, default 30; R404, R454) and the general form `artifacts.<function code or kind>.<threshold>` (R428, R454) are named by the rules and have no row of their own in `settings.csv`. `reevaluation_window_days`, `reevaluation_max_window_days` and `reevaluation_min_cases` are declared per function, not settings (R454).

Reads: `auto_post.max_error_rate` (R429), `agents.<agent_type>.drift_action` (ADR-0059.R21.N1), `extensions.wasm_enabled` (R443), `change_proposal_ttl_days` (R404).

## UI annotations

None: see chunk 2, which shows the rows of the work item kinds that R453 names (module `automation` in `work-item-kinds.csv`); the units of this chunk hold no other ADR-0077 annotation.

## Conflicts

CONFLICT ADR-0059.R16.N1: the later note ADR-0059.R16.N2 (ADR-0078 rules 2 and 8) governs: `auto_post_advisor` and its held-out filtered tools are Phase 2, and in Phase 1 people propose gateway settings and tables; stated in R426.
CONFLICT ADR-0059.R18: the note ADR-0059.R18.N1 governs: the case minimums and the evidence window are registered settings, and an acting path follows `auto_post.max_error_rate` where the rule's table sets acted precision of 99%; the other values keep the mark flagged (R428, R429). ADR-0063.R20 governs the replay backtest of the kinds `decision_table` and `automation_rule`: the settings `automation.replay_window_days` and `automation.replay_min_events` stand where the rule's table has 30 days and at least 1 event (R431).
CONFLICT ADR-0059.R24: the note ADR-0059.R24.N1 names WebAssembly with fuel metering as the sandbox after Phase 1, where the rule leaves WebAssembly or a microVM; the note governs, and the author decision stays open (R443).
CONFLICT ADR-0059.R24.N2: mechanical assurance and independent model reviews behind branch protection replace "human review" of source changes; ADR-0073.R11 and the rules after it govern (R442).

## Proposed (not law)

None

## Trace

| Source | Where |
| --- | --- |
| ADR-0059.R13 | R401-R408 |
| ADR-0059.R14 | R409-R415 |
| ADR-0059.R15 | R416-R420 |
| ADR-0059.R16 | R421-R425 |
| ADR-0059.R16.N1 | R426 |
| ADR-0059.R16.N2 | R426 |
| ADR-0059.R17 | R427 |
| ADR-0059.R18 | R428-R433 |
| ADR-0059.R18.N1 | R428, R429 |
| ADR-0059.R19 | R434 |
| ADR-0059.R20 | R435-R436 |
| ADR-0059.R21 | ref: ADR-0059.R21 |
| ADR-0059.R21.N1 | ref: ADR-0059.R21.N1 |
| ADR-0059.R22 | R437-R439 |
| ADR-0059.R23 | R440 |
| ADR-0059.R23.N1 | R440 |
| ADR-0059.R24 | R441-R443 |
| ADR-0059.R24.N1 | R443 |
| ADR-0059.R24.N2 | R442 |
| ADR-0059.R26 | R444-R449 |
| ADR-0059.R27 | R450-R451 |
| ADR-0059.R28 | R452-R455 |
| ADR-0059.R29 | R456 |
| ADR-0059.W | not applicable: worked examples of the lifecycle and of L3; the rules state every identifier they use |
| ADR-0063.R20 | R457-R460 |
| ADR-0066.R7 | R461 |
