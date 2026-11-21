Module: policy    Chunk: 1 of 4    Source ADRs: ADR-0028, ADR-0029, ADR-0043
Build step(s): 3, 4, 5    Generated from index: 30d5706    Compiled by: Claude Fable 5.2, 2026-11-21

# `policy` compiled spec, chunk 1: ownership, proposals for agent calls, policy points, the decision, rules, evaluation and floors

## Purpose

`policy` (layer 2) is the deterministic policy engine: a threshold table of policy rules per company, the policy decision stored at each policy point, the named approval ranks, and the confirmation of auto-posts. This chunk states its ownership, when a command must go through a change proposal, the policy points, what a `policy_decision` records, the `policy_rule` and `approval_procedure` tables, the policy input, which actor is evaluated, how matching rules combine, and the floors that no rule can relax. `policy` does not own `approval` rows, taint clearance or the change proposal carrier (`documents`), nor the dispatcher that applies the floors (`registry`). The rule set's save check, seeded rules, period unlock, approval pools and stages and the auto-post gateway are in the other chunks.

## Entities and tables

DDL: `docs/design/DS-05-platform.sql`.

| Table | Meaning | Key | Parent | Owner |
| --- | --- | --- | --- | --- |
| `policy_rule` | The identity of a versioned policy rule; its ID breaks ties (R17, R30) | `id`; (`company_id`, `code`) unique; (`company_id`, `id`) | `company` | `policy` |
| `policy_rule_version` | One version of a rule: match, conditions, effect and procedure, dated by `effective_from` (R17-R21) | `id`; (`policy_rule_id`, `version`) unique; (`company_id`, `policy_rule_id`, `version`) unique | `policy_rule` | `policy` |
| `approval_procedure` | A named approval rank of a company (R16) | `id`; (`company_id`, `code`) unique; (`company_id`, `rank`) unique | `company` | `policy` |
| `policy_decision` | The outcome of one policy evaluation, bound to a document version; never updated or deleted (R9, R10) | `id`; (`company_id`, `id`); (`company_id`, `id`, `document_version_id`); (`company_id`, `id`, `approval_pool_id`) | `document_version` | `policy` |
| `auto_post_confirmation` | The owner's immutable confirmation of one auto-post (R13) | `id`; `policy_decision_id` unique | `policy_decision` | `policy` |

Reads: `document`, `document_version`, `approval`, `change_proposal`, `change_proposal_execution`, `taint_clearance`, `posting_intent` (`documents`); `user_account`, `role` (`permissions`); `company` (`master_data`); `agent_run` (`agent_runs`); `inspection_lot` (`quality`); `period_unlock_request`; `approval_pool`, `approval_stage` (`policy`, other chunks).

## Commands and queries

Authorization area of the module (catalog `authorization-areas.csv`, under `administration`): the function `policy`, which covers policy rules, approval procedures and approval pools, policy decisions, `ConfirmAutoPost` at `post` (the rule's owner only) and `ClearTaint` at `full`.

| Name | Actor and authorization | Input | Effect | Events | Error codes |
| --- | --- | --- | --- | --- | --- |
| `ConfirmAutoPost` | the policy rule's owner, on the rule's latest version; area `policy` at `post` | a list (of auto-posts; fields not stated) | Writes immutable `auto_post_confirmation` rows; resolves the `auto_post_unconfirmed` work item of the confirmation window once all its auto-posts are confirmed (R13; catalog `work-item-kinds.csv`) | not stated | not stated |

The commands that save a `policy_rule` or an `approval_procedure` (`CreatePolicyRule`, `UpdatePolicyRule`, `EnablePolicyRule`, `DisablePolicyRule`, `CreateApprovalProcedure`, `UpdateApprovalProcedure`; ADR-0043.R18) have their rows in chunk 2; a rule that breaks R21 is rejected with `policy_rule_invalid`.

Contract functions and hooks, not registry commands: `context.evaluate_policy(input)` (R8, R35); the `policy_input` function that each document type registers (R23); the pure function `evaluate_auto_post` and the hook `auto_post_checker` (R1). `RecordAutoPostDecision` is an internal command and `RunAutoPostGateway` a job (R1, R28). Registration flags read by the dispatcher: `is_policy_in_handler` (R8), `is_consequence_posting` (R26), `human_only` (R33, R37).

Commands of other modules that this chunk constrains: `Submit`, `Post`, `Issue`, `Approve` and `Reverse` of documents, `CreateChangeProposal`, `UpdateAgentTypeSetting`, `LockPostingPeriod`.

Error codes bound to those commands: `proposal_required` (R3, R6), `tool_not_allowed` (R3), `origin_run_submit_not_allowed` (R8), `approval_context_changed` (R11), `auto_post_checker_missing` (R28). A floor violation at `Post` or `Issue` gives `human_only` (R35).

## Rules

### Ownership and layer

R1. Module `policy` (layer 2) owns `policy_rule`, `approval_procedure`, `policy_decision`, `auto_post_confirmation` and the policy step of `period_unlock_request`. Approval pools and stages are `policy`'s too. `policy` also owns the auto-post gateway: the pure function `evaluate_auto_post`, the hook `auto_post_checker` that modules register and `app` wires, and the internal command `RecordAutoPostDecision`; the dispatcher passes in the settings and run facts that `policy` cannot read (ADR-0065.R1). `approval` rows stay with `documents`, beside the versions they bind to (ADR-0009.R11); `taint_clearance` and `change_proposal_execution` stay with `documents`. Imports within layer 2: `registry` imports the `policy` contract, `policy` imports the `work` contract, and `policy` imports neither `registry` nor `documents` (ADR-0022.R2, ADR-0027.R1). Stage eligibility combines functions that `policy`, `permissions` and `documents` register with the dispatcher, wired by `app`, so no new import is needed (ADR-0055.R1, ADR-0054.R2).
Source: ADR-0043.R1, .N1, .N2, ADR-0029.K.N1

R2. Agents propose; people or policy approve. ADR-0029 enforces this outside documents, before the first agent (after step 4), by:
- **Change proposals.** Changes that are not documents go through one carrier, a `change_proposal` document: master data, mappings, bank accounts, planning parameters, price lists, forecast adjustments. The server computes the content: the exact commands, a before-and-after diff, the target's expected version, and the plan. The proposal uses the existing document states, policy, approval and segregation of duties. A consumer executes it after a human approval. Agents never run such commands directly, and agent types need no permission on them.
- **One policy hook** at a fixed set of policy points (R7). Each decision records its rule, whether it allowed action without a human, and whether a confirmation is required (R9).
- **Taint on data.** Taint is an immutable property of each document version, inherited by the versions and documents derived from it. A human can clear it explicitly in an immutable clearance record (interim, flagged). Fields from outside content are marked `is_untrusted`, and a run that is given such data becomes tainted.
- **Consumers.** Consumers acting on an agent's events are limited to the same intersection of rights that limits the agent.
- **Auto-post** (R12, R13).
The hard floor on what a tainted run may read is the tainted read scope as ADR-0029.R14 states it, not widened; one more read comes only as a declared projection of a registered query (decided, ADR-0029.R14.N6).
Source: ADR-0029.D0

### Commands that need a change proposal

R3. The dispatcher rejects an allowed-target command with `proposal_required` when it comes from an agent actor, or from any actor carrying an `origin_agent_run_id`, in both simulate and execute mode. The error's fix names `CreateChangeProposal`. The consumer that executes a proposal carries no origin run, because the human `Approve` reset the origin (ADR-0013.R2). `proposal_required` is step 3 of the dispatcher's check order, after the tool list and before permission (DS-04, dispatcher check order). An agent run never reaches it, because allowed-target commands are on no tool list (ADR-0050.R29), so its direct call gets `tool_not_allowed`; a consumer command carrying an origin run gets `proposal_required` whatever its permissions (`EC-56`).
Source: ADR-0029.R4, .N2

R4. A human with the permission may run an allowed-target command directly, unless policy requires a proposal for humans too. Policy does so through a deny-only `direct_master_data_change` rule (ADR-0043.R12).
Source: ADR-0029.R4, .N1

R5. A change of a partner's bank account always goes through a change proposal, also when a human starts it, approved by a human who wrote no version of it. This holds for every company, the small-company mode included, and is a policy floor (R34, floor 10). Human-run DS-21 import batches are outside the carrier.
Source: ADR-0029.R4

R6. Promotion of an agent type always goes through a proposal: a person's direct `UpdateAgentTypeSetting` that sets `assisted` returns `proposal_required` (ADR-0050.R14). A requirement that depends on the payload, such as this one, is the handler's: the consumer executing an approved proposal passes `change_proposal_execution` (the proposal's ID and version) in the handler context, and the handler returns `proposal_required` without it, for people too (DS-04, handler context; ADR-0054.R2).
Source: ADR-0029.R4, .N2

### Policy points

R7. The dispatcher evaluates policy once per command at these policy points, and the handler stores the `policy_decision`:
- `Submit` of any document, including change proposals;
- `Post` from `draft`;
- `Issue` from `draft`, always (ADR-0028.R7);
- `Post` of an approved document, only when its `policy_input_hash` changed (R11);
- `Post` of an approved document by an actor of another kind than its decision's (R35);
- `Issue` from `approved` (ADR-0053.R8), only when its `policy_input_hash` changed or its actor kind differs from the decision's, like `Post` of an approved document (ADR-0055.R11).
This replaces "before a handler that posts" of ADR-0008.R5 and the separate statement of ADR-0009.R11.
Source: ADR-0029.R6, .N1, .N2

R8. A replayed command (ADR-0008.R18) does not evaluate policy again. A handler whose policy inputs are read under locks calls the hook through `context.evaluate_policy(input)` after taking them, for example the credit check; such commands are registered `is_policy_in_handler`, and the dispatcher skips its own evaluation and asserts that the hook ran exactly once (ADR-0030.R7). `Submit` from any actor carrying an origin agent run is refused before policy with `origin_run_submit_not_allowed` (step 3 of the dispatcher check order, DS-04); this holds for every document, not only proposals.
Source: ADR-0029.R6, .N2

### The stored decision

R9. A `policy_decision` is bound to a `document_version_id` and records: the `action` (`submit`, `post` or `issue`); the `outcome` (`allowed`, `approval_required`, `human_only` or `denied`); the `policy_rule_id` and `policy_rule_version`; every matching rule with its version (`matching_rules`); `is_confirmation_required`; the required approval procedure (`approval_procedure_id`), `required_rank` and `human_post`; and the `policy_input_hash` (R11). `is_auto_allowed` is derived, not stored: outcome `allowed` with a non-human actor. The DDL also holds `document_id` and `policy_input` (interim), `decided_at`, the plan columns of ADR-0055.R6 and the gateway columns of ADR-0065.R6.
Source: ADR-0029.R7, .N1

R10. The stored `outcome` follows the evaluation result (R30): `denied` gives `denied`; a rank gives `approval_required`, with the procedure; otherwise `human_post` gives `human_only`; otherwise `allowed`. The decision also stores `required_rank` and `human_post`, so a document approved under a human-post requirement is still posted by a person. It also stores the actor evaluated: `actor_kind`, `actor_id` and `on_behalf_of_id` (interim columns of the DDL, since R26 evaluates the actor).
Source: ADR-0043.R8, .N1

R11. Recording and re-checking of the approval context:
- **At `Submit`** (and at `Issue` or `Post` from `draft`), the `policy_decision` records the approval procedure required and a `policy_input_hash`. The hash covers the inputs evaluated: amounts in company currency at the rates applied, partner exposure, and price and margin checks.
- **The approval row** refers to the `policy_decision_id` it satisfies.
- **At `Post` of an approved document, and at `Issue`**, the policy is asked again when the `policy_input_hash` differs. The existing approvals stand when they satisfy the new decision: the comparison is by stages, and approvals stand when every stage the new plan requires already has its approvals in the round (ADR-0055.R8). Otherwise the command is rejected with `approval_context_changed`, whose `details` give the approved and current amounts and procedures.
- **Resubmission.** The document may then be submitted again without edit (`approved → pending_approval`). A resubmission continues the round when the pool stays the same and starts a new one when it changes (ADR-0055.R11).
Source: ADR-0028.R14, .N1

### Taint and auto-post

R12. No policy decision for a non-human actor is `allowed` on an effectively tainted version or proposal, except through the gateway (R36). On such a version a non-human `Submit` gets at least the lowest-rank approval, and a non-human `Post` or `Issue` gets `human_post` even after an approval (R34, floor 3). A tainted version is posted, sent or executed only by a human, or after a human approval; "after a human approval" covers only what an approval lets proceed without a posting: change proposals executed by their consumer (ADR-0029.R3) and documents with no posting step. Whether a human may post a tainted draft without approval when policy requires none stays the open question of ADR-0017.R17.
Source: ADR-0029.R11, .N1

R13. Auto-post, definition and confirmation:
- **Definition.** An auto-post is a posting by actor `system` or `integration` whose decision is `allowed` with `is_confirmation_required`, set by the policy rule that allowed it. An example is a deterministic bank match (spec 14). The definition holds for the auto-post gateway's postings, which are auto-posts that the rule's owner confirms (ADR-0043.R14, ADR-0065.R7).
- **What is not an auto-post.** Close jobs (costing, FX revaluation, closing entries) are close tasks confirmed through the close (ADR-0012) and set no confirmation.
- **Confirmation.** `ConfirmAutoPost` takes a list and is run by the policy rule's owner, on the rule's latest version, for `system` and `integration` postings (ADR-0043.R14). It writes immutable `auto_post_confirmation` rows: unique `policy_decision_id`, `confirmed_by_id`, `confirmed_at`. The unconfirmed auto-posts of one rule in one confirmation window are one `auto_post_unconfirmed` work item, due at the window's end; the setting `auto_post.confirmation_cadence` sets the window, the posting period by default (ADR-0065.R8, ADR-0065.R22).
- **Close task.** The required close task (ADR-0012.R13) blocks `LockPostingPeriod` while any auto-post of the period is unconfirmed.
- **Thresholds.** The thresholds are DS-28's and the author's; the evidence floor for enabling a rule that lets `system` or `integration` post is the setting `auto_post.max_error_rate` (ADR-0063.R10).
Source: ADR-0029.R13, .N1

R14. "Agent auto-post" in spec 03 rule 6 and ADR-0012.R13 means an auto-post as defined in R13. Agents themselves only draft (ADR-0003.R8), and tainted runs never post (spec 03 rule 1): with the gateway the run only drafts, and the gateway's `system` job posts a checked draft in a causation chain of its own (ADR-0065.R3, ADR-0065.R7).
Source: ADR-0029.R13, .N2

R15. The invariants `INV-84`, `INV-85`, `INV-86`, `INV-87` and `INV-88` and the edge cases `EC-56`, `EC-57` and `EC-58` protect the rules of ADR-0029; their statements are in the Invariants and Edge cases sections. `INV-84` excepts a live gateway decision `auto_post` under ADR-0065.R10, which `INV-761` checks. `INV-85` is not changed by the gateway, because the gateway's job carries no origin agent run (ADR-0065.R3, ADR-0065.R12); outbound sends are covered by `INV-80` and the automatic-send list (ADR-0019.R17), and the intersection of rights itself (ADR-0029.R12) is a DS-16 hard-floor property test. `INV-88` needs `agent_run.tainted_at` from DS-32.
Source: ADR-0029.R16, .N1

### Approval procedures

R16. `approval_procedure` is company data: `code`, `name`, `rank` (an integer unique per company, above zero in the DDL), `basis` (interim in the DDL) and `is_active`. Procedures are named ranks: a decision's rank selects the required stages of the document's approval pool, and approvals satisfy the decision through those stages (R11). `approver_role` and `scope_binding` (`document_scope` or `company`) belong to approval stages, not to the procedure (ADR-0055.R4, ADR-0055.R5). That a higher rank's role may stand in for a lower one is a business choice (open question).
Source: ADR-0043.R2, .N1

### Policy rules

R17. A policy rule is company data and versioned: a change writes a new version with `effective_from`, and decisions record the version they used. The DDL stores a rule as `policy_rule` (its identity, with a `code`, whose ID breaks ties) and `policy_rule_version` (`version`, match, conditions, effect and procedure, dated by `effective_from`); a decision records `policy_rule_id` and `policy_rule_version`.
Source: ADR-0043.R3, ADR-0043.R7.N1

R18. What a rule version matches:
- `action`: `submit`, `post`, `issue`, or `direct_master_data_change` (ADR-0043.R12);
- `document_type` (empty for all), or for `direct_master_data_change` the `command_type`;
- `actor_kind`: `human`, `agent`, `integration`, `system`, or empty for all.
Source: ADR-0043.R3

R19. Conditions of a rule version are optional. Bounds are half-open: `_min` inclusive, `_max` exclusive. Amounts are zero or more, discounts from 0 to 100, margins any value, negative included. A boolean condition is null or true: true matches only true.
- `amount_company_min`, `amount_company_max`;
- `discount_percent_min`;
- `margin_percent_max`;
- `is_price_below_cost`, `is_price_outside_list`, `is_credit_exceeded`;
- `is_match_exceeded`: a purchase invoice outside the three-way match tolerances (ADR-0047.R14);
- `is_direct_expense`, `is_bank_account_recent` and `is_rate_unusual`, for payment documents (ADR-0048.R3, ADR-0048.R12);
- `is_cost_unknown`: a paid line's cost per inventory unit is unknown (ADR-0047.R22, ADR-0046.R14).
Source: ADR-0043.R3, .N1

R20. What a rule version gives:
- `effect`: `deny`; or `require_approval` with `approval_procedure_id`; or `require_human_post`; or `allow`;
- `is_confirmation_required` (in the DDL only with `allow`);
- `owner_user_id`;
- `is_enabled`.
Source: ADR-0043.R3

R21. Rules that loosen. A rule that allows a non-human actor (`allow` with `actor_kind` other than `human`, or empty) must have an owner and an `amount_company_max`, at every action. At `post` and `issue` it must also have `is_confirmation_required`. The command rejects anything else with `policy_rule_invalid` (`INV-203`). A new version of such a rule starts disabled, and the previous version stays in force until the new one is enabled.
Source: ADR-0043.R3

R22. For a configurable line without an item or preliminary price, the cost conditions use the configuration estimate. An unknown cost sets `is_cost_unknown`, and the seeded rule (ADR-0043.R15) makes such a decision need an approval (ADR-0046.R14).
Source: ADR-0043.R3, .N1

### Policy input

R23. Each document type registers a `policy_input` function, which gives: amounts in company currency at the rates applied; discount and margin; the price-list and cost checks; credit exceeded. `policy_input_hash` is its canonical SHA-256 (R11). Inputs read under locks come through `context.evaluate_policy` (R8): the credit check is a condition of the same evaluation, not an action of its own (ADR-0030.R7).
Source: ADR-0043.R4

R24. A purchase request carries no price. Its `policy_input` values each line at the supplier's purchase list price (`find_price`), else the item's last purchase price, else zero with `is_cost_unknown` (ADR-0047.R9).
Source: ADR-0043.R4, .N1

R25. The policy input of `inspection_lot` is the outcome, item, item group, partner and point, and the held quantity at the preliminary price as amount. It adds the flags `is_all_passed` and `is_quality_deviation` (ADR-0070.R13).
Source: ADR-0043.R4, .N2

### Which actor is evaluated

R26. Consequence postings. Commands registered `is_consequence_posting`, when their chain was started by a person's command and carries no origin agent run, are deterministic postings run on behalf of that person: close jobs (ADR-0012), FX revaluation (ADR-0011.R17), import chunks (ADR-0030.R9), tax adjustments (ADR-0041.R13) and automatic production receipts (ADR-0034). They are evaluated with actor kind `human` and that person as actor (ADR-0013.R9), and they need no confirmation. Their document types are named (`closing_entry`, `fx_revaluation`, `tax_adjustment`, and the production receipt), so rules can exclude them. If a rule requires approval or denies one, the job fails with a `consequence_posting_blocked` work item for the company's owner.
Source: ADR-0043.R5

R27. The completion `Post<Type>` that the consumer runs from `issuing` after `EInvoiceAccepted` (ADR-0028.R7) is registered `is_consequence_posting` and evaluated as the issuer: it carries the decision of the `Issue` stored with its `posting_intent` and is not a policy point of its own. It is accepted only from that internal caller, with the stored plan hash and an accepted e-invoice record, so it posts exactly what the issuer's decision covered.
Source: ADR-0043.R5, .N1

R28. Unattended postings. Scheduled jobs and workflow auto-posts (DS-34) are evaluated as `system`. Every unattended posting goes through the auto-post gateway: the bank cascade (ADR-0051.R18) and the production import as `integration` (ADR-0064.R25) keep their own triggers, and the purchase invoice is posted by the gateway's job `RunAutoPostGateway`, evaluated as `system` on behalf of the enabled rule's owner. A document type with no registered checker cannot be auto-posted (`auto_post_checker_missing`) (ADR-0065.R1, ADR-0065.R3, ADR-0065.R14, ADR-0065.R20).
Source: ADR-0043.R5, .N2

### Evaluation: rules in force, combining, baseline

R29. The rules in force are the enabled versions in force on `clock.today` when the command runs, not on the document's date, so backdating cannot select old rules.
Source: ADR-0043.R6

R30. Combining the matching rules:
- **Denials.** Any matching `deny` gives `denied`.
- **Otherwise:** the required rank is the highest `require_approval` procedure rank among matching rules, or none; `human_post` is true if any matching rule says `require_human_post`; `is_confirmation_required` is true if any matching `allow` rule says so.
- **Recorded rule.** The decision records every matching rule's ID and version, and as `policy_rule_id` the one that set the rank, or else the human-post flag, or else the confirmation. Ties go to the lowest rule ID.
A decision therefore never depends on rule order.
Source: ADR-0043.R7

R31. Baseline for non-human actors. For `agent`, `system` and `integration`, the evaluation starts from a baseline: at `submit`, `human_post`, as the default of spec 14 ("drafts automatic; a person confirms before posting"), which floor 8 of R33 turns into the lowest-rank procedure for types with no posting step; at `post` and `issue`, `human_post`. A matching `allow` rule lifts the baseline. Restrictive rules add to it and never lift it. For `human` the baseline is empty. So a rule that requires approval above an amount never frees a system posting below it.
Source: ADR-0043.R7

R32. Policy is a deterministic threshold table per company, as runbook B7 asks. Defaults: people may act; unattended system and integration postings need a person, unless a company rule with an owner, a maximum and confirmation allows them (R21, R31); deterministic postings that a person started are evaluated as that person (R26). A rule set is accepted only if it is monotonic: a riskier input never gets a looser decision, checked on every change over every ordered condition (ADR-0043.R11).
Source: ADR-0043.D0

### Floors

R33. The dispatcher applies floors around the table that no rule can relax. Floors on permission, segregation, agents, change proposals, non-posting types and reversals:
- floor 1: permission, record scope and `human_only` commands, before anything (ADR-0008.R5);
- floor 2: segregation of duties for `Approve` (ADR-0017.R16);
- floor 4: agents only draft (ADR-0003.R8): an agent's `post` or `issue` gets `human_post`;
- floor 7: change proposals: their `submit` always gets at least the lowest rank (ADR-0043.R12);
- floor 8: submit of a type with no posting step (non-posting documents such as orders and production orders, ADR-0009.R6): a `human_post` from a non-human actor becomes the lowest rank, because human-only means nothing there;
- floor 9: reversals of posted documents and period closing are `human_only` commands with no policy step (ADR-0009.R18; open question).
Source: ADR-0043.R9

R34. Floors on taint, LLM contribution, corrections and bank accounts:
- floor 3: taint: on an effectively tainted version (ADR-0029.R8 to ADR-0029.R11), a non-human `submit` gets at least the lowest rank, and a non-human `post` or `issue` gets `human_post` (`INV-84`);
- floor 5: an LLM never contributes to an auto-post (spec 03 rule 1): a `system` posting of a document with a version written by an agent run, or carrying an origin agent run, gets `human_post`;
- floor 6: corrections (`correction_of_id`, ADR-0009.R23) by a non-human get `human_post` (interim, open question);
- floor 10: a change of a partner's bank account always goes through a change proposal approved by a person other than its writer, in every company, the small-company mode included (R5; ADR-0054.R20). No policy rule or setting relaxes it.
Source: ADR-0043.R9, .N3

R35. For commands registered `is_policy_in_handler`, the floors run inside `context.evaluate_policy`. Floors 3 to 6 are checked by the dispatcher on every `Post` and `Issue` command, including `Post` of an approved document, which asks no policy. A violation gives `human_only`. A `Post` of an approved document by an actor of another kind than the one its decision was made for is also a policy point (R7), so a document a person submitted is not posted by a non-human without its own decision. Floors 3 to 6 and the actor-kind policy point are applied at `Issue`, and not again at the completion `Post` of an e-invoiced document (R27).
Source: ADR-0043.R9, .N1

R36. Gateway exception to floors 3 and 5. A `system` posting whose gateway decision is `auto_post` with every tainted-draft condition met satisfies floors 3 and 5 through the gateway and is `allowed` with confirmation (the author's decision of 2026-11-16). The conditions: `auto_post.allow_tainted_drafts` and `auto_post.<document_type>.allow_tainted` true; the drafting agent type `active` for the document type; the checker passed; every amount and quantity `trusted` or `cross_checked` while verification is required (ADR-0065.R10 to ADR-0065.R12). In every other case floors 3 and 5 give `human_post` to a non-human posting of a tainted or agent-written version, and to a `system` posting of a document that carries an origin agent run. Floors 4 and 6 are untouched. Spec 03 rule 1 names the gateway as part of the rule; that rewording was applied on 2026-11-21 (ADR-0065.R12).
Source: ADR-0043.R9, .N2

R37. Corrections by non-humans. The one rule is the registry flag of ADR-0009.R23: `Post<CorrectionType>` and `Issue<CorrectionType>` are `human_only`, refused to agents and, while the interim holds, integrations at step 3 of the dispatcher check order (DS-04). `system` runs `Post<CorrectionType>` only as the completion `Post` of an e-invoiced document, although the command is `human_only` (ADR-0027.R12). Floor 6 and the tool list reach no further case; floor 6 stays as a defensive check with the same reach.
Source: ADR-0043.R9, .N1

## Invariants

Statements are those of `invariants.csv`; first at step 5, `INV-87` at step 6. Each row stands once in the module. `INV-80` and `INV-761` are cited by R15 and have their rows in chunk 4.

| Invariant | Name | Check point | Statement | Protects |
| --- | --- | --- | --- | --- |
| `INV-82` | `required_approval_present` | day | For every posted document whose policy decision on the posted version requires a rank, every stage of the approval plan of the decision its `Post` used (for an e-invoiced document, the decision of its `Issue`) has at least its required number of counted approved approvals on that version within the round that `Post` or `Issue` ended (ADR-0055.R8, ADR-0055.R18); documents whose outcome is `human_only` are excluded. Flagged: ADR-0009.R12, approval required treated as human-only posting. | R11, R16 |
| `INV-84` | `tainted_never_auto_allowed` | day | No policy decision with outcome `allowed` for a non-human actor concerns a document version (change proposals included) that was effectively tainted at the time of the decision, except a live auto-post gateway decision `auto_post` under ADR-0065.R10 (`INV-761`). Flagged: ADR-0029.R8, taint clearing. | R12, R34, R36 |
| `INV-85` | `agent_consumers_never_post` | day | No audit row with actor `system` and an origin agent run has effect class `posting` or `master_data_change`. | R2, R15 |
| `INV-86` | `proposal_targets_never_by_agent` | day | No audit row of a command whose effect class is `master_data_change` or that is registered `is_proposal_bound` has actor `agent` or an origin agent run. | R3 |
| `INV-87` | `auto_posts_confirmed_before_lock` | day | Every posting by actor `system` or `integration` whose policy decision has `is_confirmation_required`, in a locked period, has an `auto_post_confirmation` row. | R13 |
| `INV-88` | `taint_inherited` | day | Every document version written by a run tainted at its `recorded_at`, or whose origin run was, or whose previous or `derived_from_version_id` version was effectively tainted when it was written, has `is_tainted` true. Flagged: ADR-0029.R8, taint clearing. | R2, R15 |
| `INV-203` | `non_human_allowing_rules_bounded` | day | Every enabled policy rule that allows a non-human actor to post or issue has an owner, confirmation and a maximum amount. | R21 |

## Edge cases

Statements are those of `edge-cases.csv` (area `safety`); first executable at step 5, `EC-58` at step 6.

| Edge case | Name | Case | Outcome | Protects |
| --- | --- | --- | --- | --- |
| `EC-56` | `bank_account_change_by_email` | An e-mail asks to change a supplier's bank account; the agent run's direct call is rejected with `tool_not_allowed` (the command is on no tool list), a consumer command carrying the run as origin with `proposal_required`, and a change proposal approved by a second human succeeds (DS-04 dispatcher check order). | `must_reject:tool_not_allowed`, `must_reject:proposal_required`, `must_succeed` | R3, R5 |
| `EC-57` | `injection_laundered_through_draft` | An injected instruction copied into a draft and edited by a human stays tainted; a run given that draft becomes tainted. | `must_succeed` | R2, R12 |
| `EC-58` | `auto_posts_block_close` | Auto-posted bank matches block the period lock until their rule owner confirms them. | `must_succeed` | R13 |

## Settings

None: this chunk's rules define no setting; the keys `auto_post.allow_tainted_drafts` and `auto_post.<document_type>.allow_tainted`, read by R36, have their rows in the chunk that states the gateway (ADR-0065.R8, ADR-0065.R10).

## UI annotations

The units of this chunk state no floorplan, title, facet, field annotation or tile. Work item kind of `policy` raised by this chunk (catalog `work-item-kinds.csv`):

| Kind | Subject table | Owner | Due | Resolution | Rule |
| --- | --- | --- | --- | --- | --- |
| `consequence_posting_blocked` | `document` | `company_owner` | `same_day` | `person` | R26 |

It is not agent-resolvable. The kinds `auto_post_unconfirmed` (R13), `auto_post_suspended` and `auto_post_review` have their rows in chunk 4.

## Conflicts

CONFLICT ADR-0009.R11: ADR-0029.R6 governs the policy points and replaces the separate statement of ADR-0009.R11 on when policy is asked (R7); the `approval` rows of ADR-0009.R11 stay with `documents` (R1).
CONFLICT ADR-0028.R14: ADR-0028.R14.N1 governs; whether existing approvals stand is compared by stages of the approval plan, not by procedure rank alone (R11).
CONFLICT ADR-0029.D0: ADR-0029.R14.N6 (2026-11-21) decides what the decision text left as an open question: the tainted read scope is not widened and extra reads come only as declared projections, so R2 keeps no open question.
CONFLICT ADR-0029.R4: the rule's closing note of 2026-11-19 and ADR-0043.R9.N3 confirm the bank account proposal for every company as a policy floor, so R5 drops the mark "interim, flagged".
CONFLICT ADR-0029.R11: ADR-0029.R11.N1 limits "after a human approval" to change proposals and documents with no posting step, and ADR-0043.R9.N2 adds the gateway exception stated in R36 (R12).
CONFLICT ADR-0029.R13: the definition bullet names actor `system` only, but the rule's lead-in, ADR-0043.R14 (later by number on the same date) and ADR-0065.R7 (accepted 2026-11-21: every gateway posting, `integration` included, is an auto-post) govern, so R13 defines an auto-post as a `system` or `integration` posting, consistent with confirmation and `INV-87`; ADR-0065.R8 and ADR-0065.R22 make one `auto_post_unconfirmed` item cover a confirmation window and fall due at its end, and ADR-0063.R10 sets the evidence floor as the setting `auto_post.max_error_rate`, both stated in R13.
CONFLICT ADR-0029.R16: ADR-0029.R16.N1 restates `INV-84` with the gateway exception, and ADR-0029.R4.N2 adds `tool_not_allowed` to `EC-56`; the catalog statements govern, also for `INV-86` and `INV-87` (R15).
CONFLICT ADR-0043.D0: ADR-0043.R2.N1 governs; "approvals: one level, by a procedure" is not restated, because a rank selects the stages of an approval pool (R16, R32).
CONFLICT ADR-0043.R2: ADR-0043.R2.N1 governs; `approver_role` and `scope_binding` are columns of approval stages, and the procedure keeps `code`, `name`, `rank`, `basis` and `is_active` as in the DDL (R16).
CONFLICT ADR-0043.R3: ADR-0043.R3.N1 turns "human confirmation" for an unknown cost into an approval by the seeded rule (R22), and ADR-0043.R7.N1 with the DDL splits the rule into `policy_rule` and `policy_rule_version` (R17).
CONFLICT ADR-0043.R5.N2: this note governs over the closing sentence of ADR-0043.R5; the bank cascade is not the only unattended workflow posting, every unattended posting goes through the gateway (R28).
CONFLICT ADR-0043.R9.N2: ADR-0065.R12 (review note of 2026-11-21) governs over the note's "(open question)" on the wording of spec 03 rule 1; the rewording is applied, stated in R36.
CONFLICT ADR-0043.R9: ADR-0043.R9.N2 lets a gateway `auto_post` decision satisfy floors 3 and 5 (R36), ADR-0043.R9.N3 adds floor 10 (R34), and ADR-0043.R9.N1 moves the checks of an e-invoiced document to `Issue` (R35, R37).

## Proposed (not law)

None

## Trace

| Source | Where |
| --- | --- |
| ADR-0009.R11 | ref: ADR-0009.R11 |
| ADR-0009.R11.N1 | ref: ADR-0009.R11.N1 |
| ADR-0009.R14 | ref: ADR-0009.R14 |
| ADR-0009.R14.N1 | ref: ADR-0009.R14.N1 |
| ADR-0012.R13 | ref: ADR-0012.R13 |
| ADR-0028.R14 | R11 |
| ADR-0028.R14.N1 | R11 |
| ADR-0029.D0 | R2 |
| ADR-0029.R4 | R3-R6 |
| ADR-0029.R4.N1 | R4 |
| ADR-0029.R4.N2 | R3, R6 |
| ADR-0029.R6 | R7, R8 |
| ADR-0029.R6.N1 | R7 |
| ADR-0029.R6.N2 | R7, R8 |
| ADR-0029.R7 | R9 |
| ADR-0029.R7.N1 | R9 |
| ADR-0029.R11 | R12 |
| ADR-0029.R11.N1 | R12 |
| ADR-0029.R13 | R13, R14 |
| ADR-0029.R13.N1 | R13 |
| ADR-0029.R13.N2 | R14 |
| ADR-0029.R16 | R15 |
| ADR-0029.R16.N1 | R15 |
| ADR-0029.K.N1 | R1 |
| ADR-0042.R2.N1 | ref: ADR-0042.R2.N1 |
| ADR-0042.R7.N1 | ref: ADR-0042.R7.N1 |
| ADR-0043.D0 | R32 |
| ADR-0043.R1 | R1 |
| ADR-0043.R1.N1 | R1 |
| ADR-0043.R1.N2 | R1 |
| ADR-0043.R2 | R16 |
| ADR-0043.R2.N1 | R16 |
| ADR-0043.R3 | R17-R22 |
| ADR-0043.R3.N1 | R19, R22 |
| ADR-0043.R4 | R23-R25 |
| ADR-0043.R4.N1 | R24 |
| ADR-0043.R4.N2 | R25 |
| ADR-0043.R5 | R26-R28 |
| ADR-0043.R5.N1 | R27 |
| ADR-0043.R5.N2 | R28 |
| ADR-0043.R6 | R29 |
| ADR-0043.R7 | R30, R31 |
| ADR-0043.R7.N1 | R17 |
| ADR-0043.R8 | R10 |
| ADR-0043.R8.N1 | R10 |
| ADR-0043.R9 | R33-R37 |
| ADR-0043.R9.N1 | R35, R37 |
| ADR-0043.R9.N2 | R36 |
| ADR-0043.R9.N3 | R34 |
