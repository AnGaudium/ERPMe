Module: policy    Chunk: 4 of 4    Source ADRs: ADR-0059, ADR-0063, ADR-0065, ADR-0067
Build step(s): 1, 3, 5, 6, 7    Generated from index: 30d5706    Compiled by: Claude Fable 5.2, 2026-11-21

# `policy` compiled spec, chunk 4: auto-post evidence, the error ceiling, the auto-post gateway, self-clearance of taint

## Purpose

`policy` owns policy rules, policy decisions, approval procedures, pools and stages, and the auto-post path, in layer 2 (ADR-0022.R2). This chunk states
the deterministic auto-post gateway (the pure function, its generic rules, its decision record, its settings, tainted
drafts, shadow evidence, enabling and demotion), the binding of auto-post evidence to parameter sets and decision tables,
the acting error ceiling, and self-clearance of taint in the small-company mode. The runner `RunAutoPostGateway` belongs
to `automation`, the purchase invoice checker to `purchasing`, the agent mode `active` to `agents`, the setting change
path and presets to `registry`; their units are traced `ref:` and not restated. As owner of the rest, this chunk also holds
the invariants and edge cases whose catalog source names no rule of chunks 1 to 3.

## Entities and tables

DDL: `docs/design/DS-05-platform.sql`. The rules of this chunk define no table. They add to, or constrain, tables whose rows stand in other chunks:

- `policy_decision`: the gateway columns `auto_post_decision`, `auto_post_mode`, `auto_post_reason_code`, `auto_post_checker_code`, `auto_post_checker_version`, `auto_post_plan_hash`, `auto_post_as_of_date` and `auto_post_evidence`, tied to the stored outcome by the check `ck_policy_decision_auto_post` (R621, R622).
- `policy_rule_version`: `shadow_evidence`, `shadow_evidence_outdated_by` and `evidence_setting_keys` (R602, R603, R608, R648, R651).
- `policy_rule`, `auto_post_confirmation`: named by the rules below, unchanged.

Checkers are registry declarations in code, not a table (R657).

Reads: `bank_statement_line`, `setting_value`, `agent_type_setting`, `agent_promotion_evidence`, `segregation_exception`, `document`, `document_version`, `audit_record`, `purchase_invoice`, `operation_confirmation`, `approval_stage`, `approval_stage_member`.

## Commands and queries

| Name | Actor and authorization | Input | Effect | Events | Error codes |
| --- | --- | --- | --- | --- | --- |
| `RecordAutoPostDecision` | `is_internal_only`; run by the job `RunAutoPostGateway` (R613); effect class `other` | not stated | Writes a `require_human`, `reject` or shadow decision as a `policy_decision` row and raises `auto_post_review` unless the mode is `shadow` (R621, R645) | not stated | not stated |
| `EvaluateAutoPostGateway` (query) | For people; on no agent tool list; area and level not stated (the catalog leaf `policy` covers policy decisions) | A draft | Computed: the decision the draft would get now, with every rule's outcome | None (query) | not stated |

Not commands, declared by `policy`: the pure function `policy.contract.evaluate_auto_post` (R610, R620) and the hook `auto_post_checker` (R611). Hooks of other chunks or modules that the rules use: `auto_post_eligibility` (R602) and `artifact_in_force_changed` (R604, R636).

Commands whose rows stand in other chunks, with what this chunk adds: `EnablePolicyRule` returns `auto_post_evidence_outdated` (R603), `shadow_evidence_insufficient` (R647) and `auto_post_checker_missing` (R649); `ConfirmAutoPost` follows `auto_post.confirmation_cadence` (R627, R632).

Commands and queries of other modules named by the rules: `RunAutoPostGateway`, `ListAutoPostCase`, `EvaluateAutoPostBacktest`, `ListAutoPostThresholdCandidate` (`automation`); `GetPurchaseInvoiceAutoPostShadowEvaluation` (`purchasing`); `GetAgentDraftAcceptance`, `UpdateAgentTypeSetting` (`agents`); `GetAutoPostShadowEvaluation` (`cash`); `UpdateCompanySetting` (`registry`); `ClearTaint`, `ConfirmSegregationReview`, `EnableSmallCompanyMode`; `GetProductionImportShadowEvaluation`, `ImportOperationConfirmation` (`production`); `Post<Type>` (verb `Post`, catalog level `post`).

Error codes of R657 bound to no command of this chunk: `agent_mode_not_declared` (validation). `plan_hash_mismatch` is returned by the posting execution (R626); `segregation_of_duties` by `ClearTaint` (R660). The gateway reason codes of R620, R626 and R637 are values of `policy_decision.auto_post_reason_code`, not errors.

## Rules

### Auto-post evidence bound to parameters

R601. A cascade proposal records on its `bank_statement_line` the `match_parameters_hash`, the `match_function_version`, the `match_parameter_set_version_id` and the `match_parameter_state` in force, and `match_is_tied`. `GetAutoPostShadowEvaluation` counts only proposals made under one hash, which its result names.
Source: ADR-0059.R6

R602. The evidence that `EnablePolicyRule` stores names that hash and the parameter set's latest transition at that moment (null when it has none). Through the hook `auto_post_eligibility` (ADR-0059.R2), a `system` posting of a cascade draft gets `human_post` unless its line carries the evidenced hash, was proposed while the state in force was `active` or `core_default` (so assisted never acts, which the line itself shows), is not tied, and the rule version's evidence is not marked outdated. A function release does not switch it off by itself (ADR-0059.R4).
Source: ADR-0059.R6

R603. Evidence becomes outdated without comparing times. A demotion, a rollback or an invalidation of the parameter set, and a re-evaluation below the thresholds (ADR-0059.R4), mark the stored evidence of every dependent auto-post rule version as outdated, in the same transaction, through the hook of ADR-0059.R2: `policy_rule_version.shadow_evidence_outdated_by` names the transition or the re-evaluation. A new parameter set version taking force does the same; raising the version already in force from `assisted` to `active` does not, because the pointer does not move. `EnablePolicyRule` refuses evidence that is outdated, or whose recorded latest transition is not the parameter set's latest (`auto_post_evidence_outdated`). Stored evidence is set once, so re-arming needs a new rule version with new evidence, and a demotion back to an earlier hash never re-arms auto-post on old evidence.
Source: ADR-0059.R6

R604. The auto-post gateway's stored evidence names the checker version and the version of the decision table at its decision point. A change of the table version in force, its demotion or its rollback marks that evidence outdated through `artifact_in_force_changed`, in the same transaction, as for parameter sets (R636, R648).
Source: ADR-0059.R6, ADR-0059.R6.N1

### The acting error ceiling, promotion and demotion

R605. The acting ceiling is `auto_post.max_error_rate` (company, default 1%, bounds 0.1% to 2%). The evidence of an auto-post rule on a learned or probabilistic matching path needs N proposals with at least (1 − rate) posted unchanged, N ≥ 3 ÷ rate, over at least two statement months, and none posted to another partner. This is an observed error rate at most the ceiling over N cases; it is not a 95% bound, which holds only when none was changed. The default gives N = 300 at 99% (ADR-0051.R18), 2% gives 150, 0.1% gives 3,000.
Source: ADR-0063.R10

R606. Windows, not lower bars: `artifacts.<function_or_kind>.max_window_days` (default 90, bounds 28 to 365) lets a small company collect evidence over a longer window; the minimums never fall below the declaration's small-company minimum, and they never lower the acting ceiling. The suggest-mode minimums of the bank cascade (module `cash`) are settings with bounds: `artifacts.cash.match_bank_line.min_backtest_cases` (200, bounds 50 to 5,000) and `artifacts.cash.match_bank_line.min_live_cases` (100, bounds 30 to 5,000); other functions declare theirs the same way. The precision targets, the held-out golden-case threshold, the demotion formula and the held-out share stay the declared values of ADR-0059, not settings (open question).
Source: ADR-0063.R10

R607. Demotion stays as ADR-0059.R21 defines it, judged only over at least 30 decisions (a loosening, ADR-0063.R5), the window widened as for re-evaluation (ADR-0059.R4) until 30 are reached.
Source: ADR-0063.R10

R608. Any auto-post that a person reverses, or records as wrong when confirming (ADR-0043.R14), marks its rule version's evidence outdated in the same transaction and raises `auto_post_suspended` for the rule's owner; the rule's later postings get `human_post` until a new rule version brings new evidence. For a gateway posting R651 widens the marking to the document type.
Source: ADR-0063.R10

### Gateway: ownership and checker declaration

R610. `policy` owns the gateway: the pure function `policy.contract.evaluate_auto_post`, the generic rules of R620, the decision record (R621) and the internal command `RecordAutoPostDecision` (R656).
Source: ADR-0065.R1

R611. `policy` declares the hook `auto_post_checker`. A module registers, per document type it owns, one checker implementation; `app` (layer 6) wires it. `policy` imports no module above it (ADR-0022.R2; ADR-0043.R1).
Source: ADR-0065.R1

R612. Inputs that `policy` cannot read itself are passed in by the dispatcher (`registry`), which already reads them for the actor context: the generic settings of R628 with their values and sources (`registry.contract.get_setting`), the draft version's effective taint, the agent run that wrote it, that run's agent type, behavior hash and effective mode (ADR-0050.R14), and the simulation result.
Source: ADR-0065.R1

R613. The runner is the system job `RunAutoPostGateway` of module `automation` (layer 5), which already imports `registry` for dispatch and the contracts of layers 3 and 4 (ADR-0058.R1). It is not an automation rule: it runs no company-composed action, and its only posting path is a gateway decision (ADR-0065.R13). Its position in the flow is ADR-0065.R3.
Source: ADR-0065.R1

R614. The gateway is in Phase 1. The agent mode `active` it needs keeps the in-use draft acceptance evidence of ADR-0065.R11, with no live agent shadow. `auto_post_advisor` (ADR-0065.R18) is a Phase 2 agent type; until then people propose gateway settings and decision tables, and the assistant in `act` mode may draft them on request. The purchase invoice checker lands at step 7, after the purchase invoice manual path (ADR-0078.R1, ADR-0078.R2, ADR-0078.R5, ADR-0078.R6, ADR-0078.R8).
Source: ADR-0065.R1, ADR-0065.R1.N1

R615. Checker declaration (registry vocabulary, DS-04). Each checker declares, with a version:
- `document_type` and `actor_kind` (`system`, or `integration` for an import);
- `runner`: `gateway_job` (ADR-0065.R3) or `own` (the module's existing trigger, ADR-0065.R20);
- `rules`: the ordered list of its rule codes, each with the decision it gives on failure (`require_human` or `reject`) and the values it reports;
- `facts`: the input schema of its decision point `auto_post.<document_type>` (ADR-0058.R18), every fact a registered gate field (ADR-0059.R20), with the code default `require_human` for `decision_no_match`;
- `accepts_tainted` (true or false), and the plan fields whose amounts and quantities need a verification result (R637);
- `allowed_check_codes`: check results that do not stop an auto-post (empty for every Phase 1 checker);
- its evidence function (R646) and the settings keys it reads.
Source: ADR-0065.R2

R616. The registry refuses a second checker for one document type. The placeholder `<document_type>` of the keys of R628 lists the document types whose checker declares `runner: gateway_job`; in Phase 1 that is `purchase_invoice` only.
Source: ADR-0065.R2

### Gateway: decisions and evaluation

R617. Decision `auto_post`: the posting runs as `system` (ADR-0065.R3). The decision's outcome is `allowed` with `is_confirmation_required`, so it joins `auto_post_unconfirmed` (ADR-0043.R14).
Source: ADR-0065.R4

R618. Decision `require_human`: the stored outcome is `human_only`. `auto_post_review` names the first failed rule in the checker's order and the values involved, for example "`price_outside_auto_post_tolerance`: unit price 5.0% above the order price, tolerance 1.0%". A person may post the draft under their own policy decision.
Source: ADR-0065.R4

R619. Decision `reject`: the stored outcome is `denied` for `system`. `auto_post_review` names the reason; the draft is wrong as it stands (a simulation error such as `duplicate_external_document`, or a checker rule declared `reject`), and a person corrects or cancels it. The gateway never cancels or changes it. The gateway decides a version once; a new version of the draft is a new candidate when its writer is a non-human.
Source: ADR-0065.R4

R620. `evaluate_auto_post` evaluates every rule below and records each outcome. The decision is the strictest outcome (`reject` above `require_human` above `auto_post`), so it never depends on rule order. The reason code is the first failure in this order:
- `auto_post_rule_not_allowed`: the policy table's decision for this `system` posting (ADR-0043.R7 to ADR-0043.R9, floors included except as R640 states) is not `allowed` with confirmation, for example no enabled rule, an amount above the rule's `amount_company_max`, or an approval that the seeded `is_match_exceeded` rule requires. In mode `shadow` the missing enabled rule for `system` is not a failure, because R650 enables that rule only after the shadow evidence exists: the floors and every other policy rule are evaluated as if a rule allowing `system` to post the document type with confirmation were enabled, and the amount is bounded by `auto_post_amount_above_maximum`;
- `auto_post_simulation_error` (`reject`): the simulation returned an error;
- `auto_post_check_result`: the plan carries a check result not in the checker's `allowed_check_codes`;
- `auto_post_amount_above_maximum`: the posting's amount in company currency is above `auto_post.<document_type>.max_amount_company`;
- `auto_post_currency_not_allowed`: the document currency is neither the company currency nor in `auto_post.<document_type>.allowed_currencies`;
- the tainted-draft rules of R637 (`auto_post_tainted_not_enabled`, `auto_post_agent_not_active`, `auto_post_value_unverified`);
- `auto_post_evidence_mismatch`: in `live` mode, the checker version or the decision table version in force differs from what the enabled rule's stored evidence names, or that evidence is outdated (R648);
- the checker's own rules, in its declared order, and its decision table (R633);
- `auto_post_input_missing`, `auto_post_checker_error`, `auto_post_decision_no_match`: fail-closed outcomes (R623).
Source: ADR-0065.R5

R621. Every gateway decision is one `policy_decision` row with action `post` (or `issue`), the actor evaluated (`system` or `integration`), the stored outcome of R617 to R619, and:
- `auto_post_decision` (`auto_post`, `require_human`, `reject`), `auto_post_mode` (`shadow` or `live`), `auto_post_reason_code` (null for `auto_post`);
- `auto_post_checker_code` and `auto_post_checker_version`;
- `auto_post_plan_hash` and `auto_post_as_of_date`, from the simulation;
- `auto_post_evidence` (JSON): the settings read, each with key, value and source (ADR-0063.R1); the decision table and parameter set versions with their content hashes; every rule's code, outcome and values; the verification basis of every amount and quantity the plan uses (R637); the draft's taint, the run that wrote it, its agent type, behavior hash and effective mode; the enabled policy rule version and its evidence reference.
Source: ADR-0065.R6

R622. The audit record of the posting names the decision (ADR-0029.R15). A shadow decision is stored with outcome `human_only`, because in shadow `system` may not post. The columns are in the DDL of DS-05 (R657).
Source: ADR-0065.R6

### Gateway: hard rules

R623. The rules of this topic are cross-cutting hard locks in the sense of ADR-0063.R6. Fail closed: an unknown case, missing reference data, an unmatched decision table row, a setting without a value in force, a stale input or any exception gives `require_human`, never `auto_post`.
Source: ADR-0065.R7

R624. No LLM in the checker. Neither the gateway nor a checker calls the LLM gateway, starts an agent run or reads model output other than the draft's own values. Checker code lives in the core or a package, reviewed like other code (ADR-0059.R24).
Source: ADR-0065.R7

R624a. Read-only. The gateway and checkers never write. They never change a draft's value to make it pass; only the posting command writes, and only the simulated plan.
Source: ADR-0065.R7

R625. System execution. The posting runs as `system` on behalf of the enabled rule's owner, never as the person who started the agent, and its audit record names the decision.
Source: ADR-0065.R7

R626. Plan check. The execution must reproduce `expected_plan_hash` with the pinned `as_of_date`. A different plan returns `plan_hash_mismatch` (ADR-0008.R13); nothing posts, and the job records `require_human` with reason `auto_post_plan_changed`.
Source: ADR-0065.R7

R627. Confirmation. Every gateway posting is an auto-post under ADR-0043.R14 and ADR-0029.R13: the rule's owner confirms it with `ConfirmAutoPost`, unconfirmed auto-posts block the period lock, and `INV-87` holds. The window of one `auto_post_unconfirmed` item follows `auto_post.confirmation_cadence` (R632).
Source: ADR-0065.R7

### Gateway: settings

R628. The gateway's settings are registered in `settings.csv` with leaf `policy` and change effect `immediate`; section Settings gives each key's default, bounds, direction and `outdates` value. The keys are `auto_post.<document_type>.mode`, `auto_post.<document_type>.max_amount_company`, `auto_post.<document_type>.allowed_currencies`, `auto_post.<document_type>.allow_tainted`, `auto_post.<document_type>.require_verified_values`, `auto_post.allow_tainted_drafts`, `auto_post.confirmation_cadence`, `auto_post.purchase_invoice.min_supplier_invoices`, `auto_post.purchase_invoice.price_tolerance_percent`, `auto_post.purchase_invoice.quantity_tolerance_percent` and `auto_post.purchase_invoice.require_full_receipt`.
Source: ADR-0065.R8

R629. Change path (ADR-0063.R3): tightening is immediate by one person holding `edit` on `policy`; loosening is a change proposal approved by another person holding `policy` at `full`. So turning a document type to `shadow` or `live`, raising its maximum, adding a currency, enabling tainted drafts and switching verification off each need a second person, and a one-person company cannot do any of them. The setup path of ADR-0067.R9 never applies to an `auto_post.*` key, `cash.auto_post.*` included.
Source: ADR-0065.R8

R630. Amounts are in company currency; the core gives no other value than 0, because an amount depends on the currency (as `cash.bank_charge.auto_post_ceiling`). The core defaults are safe because the mode starts `off` and the maximum at 0.
Source: ADR-0065.R8

R631. A loosening of a key with `outdates: auto_post` marks the stored evidence of every enabled rule version that lists the key outdated (ADR-0063.R3.N1), so a looser checker re-arms only on new evidence.
Source: ADR-0065.R8

R632. Confirmation cadence: `period` gives one `auto_post_unconfirmed` item per rule and posting period. `week` and `day` make the window the ISO week or the business date; the item is due at the window's end. The close task blocks the period lock in every cadence.
Source: ADR-0065.R8

### Gateway: decision tables

R633. Each checker declares the decision point `auto_post.<document_type>` (ADR-0058.R18 to ADR-0058.R20), whose inputs are its facts and whose output is a `code` from `auto_post`, `require_human`, `reject`, with the declared order `auto_post < require_human < reject`. Hit policy `unique`, or `monotone` with aggregator `max` over that order, so the strictest row wins.
Source: ADR-0065.R9

R634. The gateway uses the table's current version only when its state is `active` (ADR-0059.R12: `assisted` is never in force where the system acts). With no table, or none `active`, the checker's rules alone decide. In shadow mode the table's shadow version, when there is one, is evaluated as well and recorded.
Source: ADR-0065.R9

R635. `decision_no_match` and `decision_input_out_of_domain` give `require_human` (`auto_post_decision_no_match`). A table output `auto_post` never lifts a failed checker rule, because the decision is the strictest outcome (R620).
Source: ADR-0065.R9

R636. A change of the table version in force marks the gateway evidence that names the earlier version outdated, through the hook `artifact_in_force_changed` (ADR-0059.R6), in the same transaction.
Source: ADR-0065.R9

### Gateway: tainted drafts and floors

R637. A draft is tainted for the gateway when its version is effectively tainted (ADR-0029.R8, ADR-0029.R9) or was written by an agent run, or the document carries an origin agent run (ADR-0043.R9, floors 3 and 5). A version cleared only by the human its tainting run acted for, which the small-company mode allows (R658), still counts as tainted here, and such versions never count as evidence for mode `active` (R661). A tainted draft is auto-posted only when all of these hold; otherwise the decision is `require_human`:
- `auto_post.allow_tainted_drafts` is true for the company (`auto_post_tainted_not_enabled`);
- `auto_post.<document_type>.allow_tainted` is true and the checker declares `accepts_tainted` (`auto_post_tainted_not_enabled`);
- the agent type of the run that wrote the version is in effective mode `active` for this document type (ADR-0065.R11; `auto_post_agent_not_active`);
- the checker passes (R620, ADR-0065.R19);
- every value the checker relies on has a declared verification basis: `trusted` (the value trust of ADR-0057.R17, or a structured field that ADR-0051.R20 does not mark untrusted), `cross_checked` (a deterministic comparison confirmed it, such as the three-way match of ADR-0065.R19 within tolerance), or `llm_read_only` (an LLM step's output or an untrusted field with no such confirmation). The checker records the basis of each value in the evidence.
Source: ADR-0065.R10, ADR-0065.R10.N1

R638. While `auto_post.<document_type>.require_verified_values` is true, every amount and quantity the posting uses must be `trusted` or `cross_checked` (`auto_post_value_unverified`). A company may set it false only through a change proposal; the bases are still recorded. Trust means a value carries no instruction, not that it is true (ADR-0057.R17), so the checker's cross-checks run on trusted values too.
Source: ADR-0065.R10

R640. Floors 3 and 5 of ADR-0043.R9 give `human_post` for a non-human posting of a tainted or agent-written version. For a `system` posting whose gateway decision is `auto_post` with every condition of R637 and R638 met, they are satisfied by the gateway: the decision is `allowed` with confirmation. In every other case they apply unchanged. Floors 4 and 6, permissions, segregation of duties and `human_only` commands are untouched.
Source: ADR-0065.R12

R641. `INV-84` reads: no policy decision with outcome `allowed` for a non-human actor concerns an effectively tainted version, except a live gateway decision `auto_post` under R637, which `INV-761` checks.
Source: ADR-0065.R12

R642. Spec 03 rule 1 names the deterministic auto-post gateway as part of the rule, and its lead-in says the gateway is not a relaxation. This is the single permitted edit to spec 03, applied on 2026-11-21 under the author's decision of 2026-11-16 and delegation of 2026-11-19.
Source: ADR-0065.R12

R643. LLM-originated bank rules: the bounds of `cash.auto_post.accept_llm_originated_rules` are true and false, default false. ADR-0063.R8 keeps its conditions, and `llm_suggestion` drafts never auto-post (ADR-0063.R6).
Source: ADR-0065.R12

R644. The tainted read scope (ADR-0029.R14) is unchanged: the gateway lets a checked draft post; it widens no run's reads.
Source: ADR-0065.R12

### Gateway: shadow mode, evidence, enabling and demotion

R645. In mode `shadow` the job evaluates every candidate and records the decision (R621) without posting or raising `auto_post_review`.
Source: ADR-0065.R14

R646. The evidence function of a checker is an evidence hook in the pattern of `GetAutoPostShadowEvaluation` (ADR-0043.R14). For the purchase invoice it is `GetPurchaseInvoiceAutoPostShadowEvaluation` (module `purchasing`): over a date range, the shadow decisions `auto_post` under one checker version and one decision table version, and of those drafts the share that people posted unchanged (the evaluated version posted with no later version, not canceled, not reversed by the evidence date). Drafts still open are not counted.
Source: ADR-0065.R14

R647. Evidence floor: at least N = ceil(3 / `auto_post.max_error_rate`) such decisions over at least two calendar months, at least (1 − rate) posted unchanged, none posted to another supplier (the rule of three of R605; N = 300 at 99% with the default). Below it `EnablePolicyRule` returns `shadow_evidence_insufficient`.
Source: ADR-0065.R14

R648. `EnablePolicyRule` stores the evidence with the checker version, the decision table version and content hash, and the setting keys the evidence was judged under (`evidence_setting_keys`, ADR-0043.R14). A gateway decision in `live` whose checker version or table version differs gets `require_human` (`auto_post_evidence_mismatch`).
Source: ADR-0065.R14

R649. No checker, no system posting: `EnablePolicyRule` for a rule that allows `system` or `integration` to post or issue a document type with no registered checker returns `auto_post_checker_missing`.
Source: ADR-0065.R14

R650. A document type is enabled in this order:
- A person proposes the thresholds, mode `shadow` and, where wanted, the tainted settings, in one change proposal of `UpdateCompanySetting` items; another person approves it (R629).
- The gateway runs in shadow until the evidence floor is met (R647).
- The rule's owner creates a policy rule that allows `post` of the document type for actor kind `system`, with `amount_company_max` and `is_confirmation_required` (ADR-0043.R3), and enables it with `EnablePolicyRule`, which stores the shadow evidence.
- A person proposes `auto_post.<document_type>.mode` `live`; a second person approves it.
Source: ADR-0065.R15

R651. One wrong auto-post suspends the type. A reversal of a gateway posting, or a confirmation recording it wrong (ADR-0043.R14), marks in the same transaction the evidence of every enabled rule version that allows `system` or `integration` to post that document type outdated, and raises `auto_post_suspended` for each such rule's owner. Later candidates get `require_human` (`auto_post_evidence_mismatch`) until a new rule version is enabled on new evidence.
Source: ADR-0065.R16

R652. Stop at once: any person holding `edit` on `policy` sets the mode to `shadow` or `off` immediately; lowering an agent type from `active` is immediate too (ADR-0065.R11).
Source: ADR-0065.R16

R653. Drift: an artifact demotion of the decision table, a new table version in force, a loosened setting and a new checker version all outdate or mismatch the evidence (R631, R636, R648).
Source: ADR-0065.R16

### Gateway: commands and catalog rows

R656. Commands and queries of the gateway, each with its module and effect class:
- `RunAutoPostGateway` (`automation`, `other`): system job every 5 minutes per company and document type in `shadow` or `live`; `is_internal_only`; dispatches `Post<Type>` as `system` (ADR-0065.R3).
- `RecordAutoPostDecision` (`policy`, `other`): `is_internal_only`; writes a `require_human`, `reject` or shadow decision and raises `auto_post_review`.
- `GetPurchaseInvoiceAutoPostShadowEvaluation` (`purchasing`, query): evidence function registered through the hook (R646); on no agent tool list.
- `GetAgentDraftAcceptance` (`agents`, query): figures for an `active` promotion (ADR-0065.R11); on no agent tool list.
- `EvaluateAutoPostGateway` (`policy`, query): computed, for people: the decision a draft would get now, with every rule's outcome; on no agent tool list.
- `ListAutoPostCase`, `EvaluateAutoPostBacktest`, `ListAutoPostThresholdCandidate` (`automation`, query): held-out filtered (ADR-0065.R17).
- `UpdateAgentTypeSetting` gains the mode `active` (ADR-0065.R11). `EnablePolicyRule` gains `auto_post_checker_missing` (R649). `ConfirmAutoPost` follows the cadence of R632.
Source: ADR-0065.R21

R657. Catalog rows and DDL of the gateway:
- Settings: the keys of R628, in `settings.csv`; `cash.auto_post.accept_llm_originated_rules` gets bounds `true|false` (R643).
- Errors (DS-04): `auto_post_checker_missing` (precondition), `agent_mode_not_declared` (validation).
- Gateway reason codes, recorded in `policy_decision.auto_post_reason_code` and not errors: the codes of R620, R626 and R637, and the checker's codes of ADR-0065.R19.
- Work item kind `auto_post_review` (module `policy`, subject `document`, `role:accountant`, `days:1`, resolved by the system when the version is posted, canceled or replaced). `auto_post_unconfirmed` is due at the end of its confirmation window (`named_by_raiser`, R632).
- Registry vocabulary (DS-04): the auto-post checker declaration (R615).
- Authorization area `agent_auto_post_advisor` under `agent` (ADR-0054.R24).
- DDL (`DS-05-platform.sql`): `policy_decision` holds `auto_post_decision`, `auto_post_mode`, `auto_post_reason_code`, `auto_post_checker_code`, `auto_post_checker_version`, `auto_post_plan_hash`, `auto_post_as_of_date` and `auto_post_evidence`, with a check that ties them to the stored outcome; `agent_type_setting.mode` accepts `active`, with `active_document_types`; `agent_promotion_evidence` holds `target_mode` and `document_type`. Checkers are registry declarations in code, not a table.
- Invariants `INV-760` to `INV-764` of the block INV-760 to INV-789, `INV-84` as R641 states it, and edge cases `EC-220` to `EC-228` of the block EC-220 to EC-239.
Source: ADR-0065.R22

### Self-clearance of taint in the small-company mode

R658. While `permissions.small_company_mode` is on, the human for whom a tainted run acted may run `ClearTaint` on that run's versions, which ADR-0029.R8 otherwise refuses with `segregation_of_duties`. The chief architect decided this under the author's delegation of 2026-11-17.
Source: ADR-0067.R17

R659. Outside the mode ADR-0029.R8 applies unchanged. One-click post still never applies to an agent-written draft (ADR-0067.R12).
Source: ADR-0067.R17

R660. One `ClearTaint` per version, with a reason, as a single command: never a batch item, a bulk review or a case-level confirmation (ADR-0066.R18); otherwise `segregation_of_duties`. Each self-clearance writes a `segregation_exception` of kind `own_run_taint_clearance` and is reviewed with the period's other exceptions through `segregation_review_due` and `ConfirmSegregationReview` at period close (ADR-0054.R20).
Source: ADR-0067.R17

R661. Never for automation. A version whose only clearances are self-clearances counts as tainted for the gateway's tainted-draft eligibility (R637) and never feeds the evidence for agent mode `active` (ADR-0065.R11; ADR-0050.R14; ADR-0059.R18). The shadow evidence of R646 and R647 counts drafts posted unchanged and is not affected. A self-clearance is a clearance whose actor is the human the tainting run acted for, derived from the rows, so no new column is needed.
Source: ADR-0067.R17

## Invariants

Statements are those of `invariants.csv`; first at step 5, `INV-760` to `INV-764` at step 6. Each row stands once in the module; this chunk holds the rows whose catalog source is a rule of this chunk, a rule of another module or a spec. "Protects" names a rule of this chunk or the source ID of a rule stated elsewhere.

| Invariant | Name | Check point | Statement | Protects |
| --- | --- | --- | --- | --- |
| `INV-17` | `approvals_human_and_segregated` | day | Every approval was made by a human, and no approved document has a version whose `agent_run_id` or `origin_agent_run_id` belongs to a run on behalf of the approver. | ADR-0017.R15, ADR-0017.R16 |
| `INV-80` | `tainted_never_acts` | day | No tainted outbox event whose command has effect class `posting`, `master_data_change` or `outbound_send` has a non-human actor. | spec 03 rule 1; ADR-0013.R11; ADR-0027.R17 |
| `INV-204` | `one_approval_item_per_pending_document` | day | Every document in `pending_approval` has exactly one open `approval_pending` work item. | ADR-0042.R17 |
| `INV-760` | `auto_post_gateway_decided` | day | Every posting by `system` or `integration` of a document type with a registered auto-post checker has a `policy_decision` with `auto_post_decision` `auto_post` and mode `live`, a checker code and version, evidence in which every rule passed, and an `auto_post_plan_hash` equal to the posted plan's hash; its policy rule version was enabled with evidence naming that checker version and decision table version, not outdated on the posting date. | R617-R627, R645-R649; ADR-0065.R3 |
| `INV-761` | `auto_post_tainted_gated` | day | Every gateway posting of a tainted draft happened while `auto_post.allow_tainted_drafts` and `auto_post.<document_type>.allow_tainted` were true on its date, with the drafting agent type's effective mode `active` for that document type at the behavior hash its evidence covered, and, while `require_verified_values` was true, no amount or quantity of the plan with basis `llm_read_only`. | R637, R638, R640, R641; ADR-0065.R11 |
| `INV-762` | `auto_post_gateway_without_model` | day | No LLM call or agent run has a causation chain that `RunAutoPostGateway` started, and no gateway decision's evidence names a model output other than the draft's own values. | R624 |
| `INV-763` | `wrong_auto_post_suspends_document_type` | day | Every reversal of a gateway posting, and every confirmation recording one wrong, marked in the same transaction the evidence of every enabled rule version allowing `system` or `integration` to post that document type outdated. | R651 |
| `INV-764` | `agent_active_evidenced` | day | Every `agent_type_setting` in mode `active` names document types its promoted agent type version declares, each covered by sufficient `agent_promotion_evidence` with target mode `active` at the promoted behavior hash, from a proposal approved by a person other than its submitter. | ADR-0065.R11 |

Named by rules of this chunk, with their rows in chunk 1: `INV-84` (R641), `INV-87` (R627). `INV-85` and `INV-88` also have their rows in chunk 1.

## Edge cases

Statements are those of `edge-cases.csv`; first executable at step 6. `EC-56`, `EC-57` and `EC-58` have their rows in chunk 1.

| Edge case | Name | Case | Outcome | Protects |
| --- | --- | --- | --- | --- |
| `EC-220` | `purchase_invoice_auto_post` | An agent-drafted invoice of a supplier with enough history matches its fully received order exactly; with the type live, tainted drafts enabled and the agent active, the gateway posts it as `system` and an `auto_post_unconfirmed` item asks the rule's owner to confirm. | `must_succeed` | R617, R637; ADR-0065.R3, ADR-0065.R19 |
| `EC-221` | `purchase_invoice_price_variance` | A line 5% above the order price with a 1% tolerance gets `require_human`, and `auto_post_review` names `price_outside_auto_post_tolerance` with both prices. | `must_succeed` | R618; ADR-0065.R19 |
| `EC-222` | `tainted_auto_post_disabled` | The same clean invoice with `auto_post.allow_tainted_drafts` false gets `require_human` (`auto_post_tainted_not_enabled`); a direct change to true returns `proposal_required`. | `must_reject:proposal_required`; `must_succeed` | R629, R637 |
| `EC-223` | `llm_chosen_item_not_verified` | A line whose item the LLM chose among candidates gets `require_human` (`line_item_not_mapped`); after the mapping proposal is approved, the supplier's next invoice posts. | `must_succeed` | R637; ADR-0065.R19 |
| `EC-224` | `plan_changed_before_execution` | The goods receipt is reversed between simulation and execution; the execution returns `plan_hash_mismatch`, nothing posts, and the decision is `require_human` (`auto_post_plan_changed`). | `must_reject:plan_hash_mismatch` | R626 |
| `EC-225` | `wrong_auto_post_suspends_document_type` | The owner confirms one auto-posted invoice as wrong; every enabled purchase invoice auto-post rule's evidence is outdated, `auto_post_suspended` is raised, and the next clean invoice gets `require_human`. | `must_succeed` | R651 |
| `EC-226` | `gateway_fail_closed` | A decision table in force has no row for one case, and another case reads a setting with no value in force; both get `require_human`. | `must_succeed` | R620, R623, R635 |
| `EC-228` | `duplicate_invoice_rejected` | An agent drafts an invoice whose supplier invoice key is already posted; the simulation returns `duplicate_external_document`, the decision is `reject`, and the draft stays for a person. | `must_succeed` | R619; ADR-0065.R19 |

`EC-227` (`advisor_drafts_only`, ADR-0065.R17, ADR-0065.R18) concerns the advisor agent and is not stated here.

## Settings

All keys: scope `company`, storage `setting_value`, change effect `immediate`. Leaf `policy` unless the row says otherwise.

| Key | Value type (bounds) | Direction | Outdates | Core default | Used by |
| --- | --- | --- | --- | --- | --- |
| `auto_post.max_error_rate` | percent (`0.1..2`) | `lower_tighter` | `auto_post` | `1` | R605, R647 |
| `artifacts.<function_or_kind>.max_window_days` | integer (`28..365`); leaf `configuration` | `lower_tighter` | `promotion` | `90` | R606 |
| `artifacts.cash.match_bank_line.min_backtest_cases` | integer (`50..5000`); leaf `configuration` | `higher_tighter` | `promotion` | `200` | R606 |
| `artifacts.cash.match_bank_line.min_live_cases` | integer (`30..5000`); leaf `configuration` | `higher_tighter` | `promotion` | `100` | R606 |
| `auto_post.<document_type>.mode` | enum (`off`, `shadow`, `live`) | `order:live<shadow<off` | `none` | `off` | R628, R650, R652 |
| `auto_post.<document_type>.max_amount_company` | amount (`0..`) | `lower_tighter` | `auto_post` | `0` | R620, R630 |
| `auto_post.<document_type>.allowed_currencies` | code_list (currency codes) | `subset_tighter` | `auto_post` | `[]` (company currency only) | R620 |
| `auto_post.<document_type>.allow_tainted` | boolean | `false_tighter` | `auto_post` | `false` | R637 |
| `auto_post.<document_type>.require_verified_values` | boolean | `true_tighter` | `auto_post` | `true` | R638 |
| `auto_post.allow_tainted_drafts` | boolean | `false_tighter` | `auto_post` | `false` | R637 |
| `auto_post.confirmation_cadence` | enum (`period`, `week`, `day`) | `order:period<week<day` | `none` | `period` | R627, R632 |
| `auto_post.purchase_invoice.min_supplier_invoices` | integer (`3..1000`) | `higher_tighter` | `auto_post` | `10` | R628; ADR-0065.R19 |
| `auto_post.purchase_invoice.price_tolerance_percent` | percent (`0..10`) | `lower_tighter` | `auto_post` | `0` | R628; ADR-0065.R19 |
| `auto_post.purchase_invoice.quantity_tolerance_percent` | percent (`0..10`) | `lower_tighter` | `auto_post` | `0` | R628; ADR-0065.R19 |
| `auto_post.purchase_invoice.require_full_receipt` | boolean | `true_tighter` | `auto_post` | `true` | R628; ADR-0065.R19 |

Reads: `cash.auto_post.accept_llm_originated_rules` (area `cash`, leaf `policy`; bounds `true|false`, default `false`, R643), `cash.bank_charge.auto_post_ceiling`, `cash.bank_charge.codes`, `permissions.small_company_mode`, `ui.post_review`, `ui.post_review_max_amount`.

## UI annotations

The sources of this chunk state no floorplan, title, facet, field annotation or tile. Work item kinds of `policy` that the rules of this chunk raise (catalog `work-item-kinds.csv`):

| Kind | Subject table | Owner | Due | Resolution | Rule |
| --- | --- | --- | --- | --- | --- |
| `auto_post_review` | `document` | `role:accountant` (role template `accountant`) | `days:1` | `system`: when the version is posted, canceled or replaced by a later version | R618, R619, R657 |
| `auto_post_suspended` | `policy_rule` | `rule_owner` | `days:1` | `person` | R608, R651 |
| `auto_post_unconfirmed` | `policy_rule` | `rule_owner` | `named_by_raiser`: the end of the confirmation window | `command`: `ConfirmAutoPost`, once all auto-posts of the window are confirmed | R617, R627, R632, R657 |

None of them is agent-resolvable. `auto_post_unconfirmed` is also raised under ADR-0029.R13 and ADR-0043.R14 (chunks 1 and 2). Of another module: `segregation_review_due` (R660).

## Conflicts

CONFLICT ADR-0065.R1: the phase and build step follow the later note ADR-0065.R1.N1 (ADR-0078): the purchase invoice checker lands at step 7 and `auto_post_advisor` is a Phase 2 agent type, stated in R614.
CONFLICT ADR-0065.R5: the review note of 2026-11-21 inside item 1 governs shadow mode: a missing enabled rule for `system` is not a failure there, stated in R620.
CONFLICT ADR-0065.R8: the review note of 2026-11-21 inside the change path excludes every `auto_post.*` key from the setup path of ADR-0067.R9, stated in R629.
CONFLICT ADR-0065.R12: the rewording of spec 03 rule 1 is applied (2026-11-21), no longer pending, so R642 states the reworded text as current.
CONFLICT ADR-0067.R17: the review note of 2026-11-21 narrows "evidence" to tainted-draft eligibility and agent mode `active`; shadow evidence of ADR-0065.R14 is not affected, stated in R661.
CONFLICT ADR-0063.R10: for a gateway posting the later ADR-0065.R16 widens the suspension from the rule version to every enabled rule version of the document type, stated in R651; R608 keeps the rest.

## Proposed (not law)

None

## Trace

| Source | Where |
| --- | --- |
| ADR-0059.R6 | R601-R604 |
| ADR-0059.R6.N1 | R604 |
| ADR-0063.R3 | ref: ADR-0063.R3 |
| ADR-0063.R3.N1 | ref: ADR-0063.R3.N1 |
| ADR-0063.R3.N2 | ref: ADR-0063.R3.N2 |
| ADR-0063.R10 | R605-R608 |
| ADR-0064.R25.N1 | ref: ADR-0064.R25.N1 |
| ADR-0065.D0 | ref: ADR-0065.D0 |
| ADR-0065.R1 | R610-R614 |
| ADR-0065.R1.N1 | R614 |
| ADR-0065.R2 | R615, R616 |
| ADR-0065.R3 | ref: ADR-0065.R3 |
| ADR-0065.R4 | R617-R619 |
| ADR-0065.R5 | R620 |
| ADR-0065.R6 | R621, R622 |
| ADR-0065.R7 | R623, R624, R624a, R625-R627 |
| ADR-0065.R8 | R628-R632 |
| ADR-0065.R9 | R633-R636 |
| ADR-0065.R10 | R637, R638 |
| ADR-0065.R10.N1 | R637 |
| ADR-0065.R12 | R640-R644 |
| ADR-0065.R14 | R645-R649 |
| ADR-0065.R15 | R650 |
| ADR-0065.R16 | R651-R653 |
| ADR-0065.R21 | R656 |
| ADR-0065.R22 | R657 |
| ADR-0066.R2 | ref: ADR-0066.R2 |
| ADR-0067.R2 | ref: ADR-0067.R2 |
| ADR-0067.R3 | ref: ADR-0067.R3 |
| ADR-0067.R6 | ref: ADR-0067.R6 |
| ADR-0067.R17 | R658-R661 |
| ADR-0076.R6 | ref: ADR-0076.R6 |
