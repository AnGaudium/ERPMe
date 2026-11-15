# ADR-0043: Policy table and one-level approval

Status: accepted (2026-11-14) under ADR-0005, reviewed by Claude Fable 5.2 (builder Claude Opus 5.5). Design item: DS-28. Related decisions: D2. Principles 2, 3, 8. ADR-0003, ADR-0005, ADR-0008, ADR-0009, ADR-0011, ADR-0012, ADR-0013, ADR-0017, ADR-0022, ADR-0023, ADR-0024, ADR-0026, ADR-0027, ADR-0028, ADR-0029, ADR-0030, ADR-0034, ADR-0036, ADR-0038, ADR-0040, ADR-0041, ADR-0042; spec 03, 07, 14.

## Decision

Policy is a deterministic threshold table per company, as runbook B7 asks.
- **Rules.** Each `policy_rule` matches an action (`submit`, `post`, `issue`), a document type and an actor kind, plus ordered conditions on the policy input: amount, discount, margin, price below cost, price outside the list, credit exceeded.
- **The decision has two dimensions:** the approval rank required (none, or a procedure's rank), and whether only a person may post. It is `denied` if any matching rule denies. Matching rules combine by taking the maximum of each dimension, so a decision never depends on rule order.
- **What is stored.** The result maps onto ADR-0029's stored outcomes.
- **Floors.** The dispatcher applies floors that no rule can relax:
  - permissions;
  - segregation of duties;
  - taint;
  - agents only draft;
  - change proposals always need approval;
  - corrections are posted by people.

**Defaults.** People may act. Unattended system and integration postings need a person, unless a company rule with an owner, a maximum and confirmation allows them. Deterministic postings that a person started (close jobs, revaluation, import chunks, tax adjustments) are evaluated as that person.

**Saving rules.** A rule set is accepted only if it is monotonic: a riskier input never gets a looser decision. This is checked on every change over every ordered condition.

**Approvals.** One level, by a procedure with a unique rank.

### Rules

**Ownership**

1. Module `policy` (layer 2) owns `policy_rule`, `approval_procedure`, `policy_decision`, `auto_post_confirmation` and `period_unlock_request`'s policy step.
   - **Approvals.** `approval` rows stay with `documents`, beside the versions they bind to (ADR-0009 rule 11).
   - **Imports within layer 2:** `registry` imports the `policy` contract, `policy` imports the `work` contract, and `policy` imports neither `registry` nor `documents`. ADR-0022 rule 2 and ADR-0027 rule 1 get notes.

**Rules and procedures**

2. `approval_procedure` (company data):
   - **Columns:** `code`, `name`, `rank` (an integer unique per company), `approver_role`, `scope_binding` (`document_scope` or `company`), `is_active`.
   - **When an approval satisfies a decision.** When its procedure's rank is at least the rank required.
   - **Rank and roles.** That a higher rank's role may stand in for a lower one is a business choice (open question).
3. `policy_rule` (company data, versioned: a change writes a new version with `effective_from`, and decisions record the version they used):
   - **What it matches:**
     - `action`: `submit`, `post`, `issue`, or `direct_master_data_change` (rule 12);
     - `document_type` (empty for all), or for `direct_master_data_change` the `command_type`;
     - `actor_kind`: `human`, `agent`, `integration`, `system`, or empty for all.
   - **Conditions** (optional; bounds are half-open: `_min` inclusive, `_max` exclusive; amounts are zero or more, discounts from 0 to 100, margins any value, negative included):
     - `amount_company_min`, `amount_company_max`;
     - `discount_percent_min`;
     - `margin_percent_max`;
     - `is_price_below_cost`, `is_price_outside_list`, `is_credit_exceeded` (true matches only true).
   - **What it gives:**
     - `effect`: `deny`; or `require_approval` with `approval_procedure_id`; or `require_human_post`; or `allow`;
     - `is_confirmation_required`;
     - `owner_user_id`;
     - `is_enabled`.
   - **Rules that loosen.** A rule that allows a non-human actor (`allow` with `actor_kind` other than `human`, or empty) must have an owner and an `amount_company_max`, at every action. At `post` and `issue` it must also have `is_confirmation_required`. The command rejects anything else with `policy_rule_invalid`.
   - **New versions.** A new version of such a rule starts disabled, and the previous version stays in force until the new one is enabled.

   For a configurable line without an item or preliminary price, the cost conditions use the configuration estimate, and an unknown cost makes the decision need human confirmation ([ADR-0046](0046-product-configuration.md) rule 14).

   Condition `is_match_exceeded` (a purchase invoice outside the three-way match tolerances) is added ([ADR-0047](0047-commercial-documents-and-pricing.md) rule 14).

    Conditions `is_direct_expense`, `is_bank_account_recent` and `is_rate_unusual` are added for payment documents ([ADR-0048](0048-cash-bank-receivables-payables.md) rules 3, 12).
4. Policy input. Each document type registers a `policy_input` function, which gives:
   - amounts in company currency at the rates applied;
   - discount and margin;
   - the price-list and cost checks;
   - credit exceeded.

   `policy_input_hash` is its canonical SHA-256 (ADR-0028 rule 14). Inputs read under locks come through `context.evaluate_policy` (ADR-0029 rule 6): the credit check is a condition of the same evaluation, not an action of its own (ADR-0030 rule 7).

**Evaluation**

5. Which actor is evaluated:
   - **Consequence postings.** Commands registered `is_consequence_posting`, when their chain was started by a person's command and carries no origin agent run, are deterministic postings run on behalf of that person: close jobs (ADR-0012), FX revaluation (ADR-0011 rule 17), import chunks (ADR-0030 rule 9), tax adjustments (ADR-0041 rule 13) and automatic production receipts (ADR-0034). They are evaluated with actor kind `human` and that person as actor (ADR-0013 rule 9), and they need no confirmation. Their document types are named (`closing_entry`, `fx_revaluation`, `tax_adjustment`, and the production receipt), so rules can exclude them. If a rule requires approval or denies one, the job fails with a `consequence_posting_blocked` work item for the company's owner.
   - **Unattended postings.** Scheduled jobs and workflow auto-posts (DS-34) are evaluated as `system`.

   The only unattended workflow posting is the deterministic bank cascade's auto-post ([ADR-0051](0051-agent-workflows.md) rule 18).
6. Rules in force. They are the enabled versions in force on `clock.today` when the command runs, not on the document's date, so backdating cannot select old rules.
7. Combining:
   - **Denials.** Any matching `deny` gives `denied`.
   - **Otherwise:**
     - the required rank is the highest `require_approval` procedure rank among matching rules, or none;
     - `human_post` is true if any matching rule says `require_human_post`;
     - `is_confirmation_required` is true if any matching `allow` rule says so.
   - **Recorded rule.** The decision records every matching rule's ID and version, and as `policy_rule_id` the one that set the rank, or else the human-post flag, or else the confirmation. Ties go to the lowest rule ID.
   - **Baseline for non-human actors.** For `agent`, `system` and `integration`, the evaluation starts from a baseline:
     - at `submit`, `human_post`, as spec 14's default ("drafts automatic; a person confirms before posting"); for types with no posting step, floor 9.8 turns it into the lowest-rank procedure;
     - at `post` and `issue`, `human_post`.

     A matching `allow` rule lifts the baseline. Restrictive rules add to it and never lift it. For `human` the baseline is empty. So a rule that requires approval above an amount never frees a system posting below it.
8. Mapping to ADR-0029's stored outcome:
   - `denied` → `denied`;
   - a rank → `approval_required`, with the procedure;
   - otherwise `human_post` → `human_only`;
   - otherwise → `allowed`.

   The decision also stores `required_rank` and `human_post`, so a document approved under a human-post requirement is still posted by a person.
9. Floors, applied by the dispatcher around the table:
   1. permission, record scope and `human_only` commands, before anything (ADR-0008 rule 5);
   2. segregation of duties for `Approve` (ADR-0017 rule 16);
   3. taint: on an effectively tainted version (ADR-0029 rules 8–11), a non-human `submit` gets at least the lowest rank, and a non-human `post` or `issue` gets `human_post` (INV-84);
   4. agents only draft (ADR-0003 R8): an agent's `post` or `issue` gets `human_post`;
   5. an LLM never contributes to an auto-post (spec 03 rule 1): a `system` posting of a document with a version written by an agent run, or carrying an origin agent run, gets `human_post`;
   6. corrections (`correction_of_id`, ADR-0009 rule 23) by a non-human get `human_post` (interim, open question);
   7. change proposals: their `submit` always gets at least the lowest rank (rule 12);
   8. submit of a type with no posting step (non-posting documents such as orders and production orders, ADR-0009 rule 6): a `human_post` from a non-human actor becomes the lowest rank, because human-only means nothing there;
   9. reversals of posted documents and period closing are `human_only` commands with no policy step (ADR-0009 rule 18; open question).

   For commands registered `is_policy_in_handler`, the floors run inside `context.evaluate_policy`.

   **On every post and issue.** Floors 3 to 6 are checked by the dispatcher on every `Post` and `Issue` command, including `Post` of an approved document, which asks no policy (ADR-0009 rule 11). A violation gives `human_only`. A `Post` of an approved document by an actor of another kind than the one its decision was made for is also a policy point (a note on ADR-0029 rule 6). So a document a person submitted is not posted by a non-human without its own decision.
10. Documents that may not wait (`is_approval_hold_allowed: false`): a rank becomes `human_post` and the stored outcome is `human_only` (ADR-0009 rule 12 interim). Note: for types with `is_approval_hold_allowed: regime` this applies while `documents.issuance_without_delay` is true for the document's date; while it is false they follow the ordinary approval path ([ADR-0053](0053-core-neutrality.md) rule 8).

**Monotonic rule sets**

11. Saving, enabling or disabling a rule checks the company's whole rule set for each future effective date in it. The set must be monotonic for every action, document type and actor kind:
    - **The order of risk.**
      - Riskier inputs: a larger amount, a larger discount, a smaller margin, and true booleans.
      - Stricter decisions: compared per dimension, with denied above everything, rank by procedure rank, and the posting control level `free` < `confirm` < `human` (human post, else confirmation, else free). Confirmation and human post form one level because moving from "allowed with confirmation" to "a person posts" is stricter, though confirmation drops.
    - **The test.** A riskier input must never give a less strict decision in any dimension.
    - **How it is evaluated.** At every combination of breakpoints of the numeric conditions (each bound, and one smallest step below it: a minor unit for amounts, 0.000001 for percents, within each condition's domain, so margins below zero are included) and both values of each boolean.
    - **Failure.** A set that fails is rejected with `policy_rule_invalid`, naming the inputs.
    - **Why.** Strictest-wins with defaults is not monotonic by construction (lab finding L-11).
    - **Owner suspension.** A deactivated owner suspends only the rules that allow a non-human actor (ADR-0017 rule 12; ADR-0042). Restrictive rules stay in force, and an `owner_suspended` work item asks the company's owner to reassign them.

**Approvals, proposals and confirmations**

12. Change proposals (ADR-0029 rules 1–5):
    - **Submit.** It always requires at least the lowest-rank procedure.
    - **Who approves.** The approver must hold that procedure's role, the target commands' permissions and every field class the proposal changes (ADR-0029 rule 3), and segregation of duties applies.
    - **The bank-account rule.** It is seeded (rule 15) and cannot be disabled while ADR-0029 rule 4's interim stands: the command that changes a partner's bank account returns `proposal_required`.
    - **The mechanism.** A rule with `action` `direct_master_data_change`, a `command_type`, and `effect` `deny` for `human` is checked by the dispatcher before the command runs. Only `deny` is allowed for this action. It writes no decision row, only the error.
13. Approvals:
    - **Commands.** `Approve<Type>` and `Reject<Type>` are human actions (ADR-0017 rule 15).
    - **Who may approve.** The approver must hold the procedure's role in the document's scope.
    - **The row.** Each writes an immutable `approval` row (version, decision, reason, actor, on whose behalf, `decided_at`, `policy_decision_id`).
    - **Work items.** A pending approval is the work item `approval_pending` (ADR-0042 rule 17).
    - **Small companies.** Until the author decides, a person may approve their own document, and segregation of duties (which covers documents an agent wrote on the approver's behalf) applies to every company, and a company without a second eligible person cannot satisfy a rule that requires approval. The command that saves such a rule returns the check result `policy_no_eligible_approver` (open question).

    Exception to the interim: a proposal promoting an agent type to assisted mode must be approved by a person other than its submitter (`approver_is_submitter`), so a one-person company cannot promote an agent until the author decides ([ADR-0050](0050-agent-runtime-and-query-layer.md) rule 14).
14. Auto-posts and confirmation:
    - **Scope.** `is_confirmation_required` applies only to `post` and `issue` by `system` or `integration` actors.
    - **Work items.** Each such posting adds evidence to one `auto_post_unconfirmed` work item per rule and period (ADR-0042).
    - **Confirming.** `ConfirmAutoPost` (a list) may be run only by the owner on the rule's latest version, so a reassignment moves the duty. INV-87 covers every `system` and `integration` posting with confirmation required.
    - **Shadow mode.** A rule that lets `system` or `integration` post is enabled only by `EnablePolicyRule` with the shadow-mode evidence recorded (ADR-0003 R8; DS-34). A rule with empty `actor_kind` that allows is treated the same.

    The shadow evidence comes through an evidence hook that `policy` declares and `cash` registers (`GetAutoPostShadowEvaluation`), wired by `app`, and is stored on the rule version; `EnablePolicyRule` returns `shadow_evidence_insufficient` below the figures of [ADR-0051](0051-agent-workflows.md) rule 18.
15. Templates. The core seeds each company with:
    - two procedures, `standard` (rank 10, `accountant`) and `senior` (rank 20, `chief_accountant`);
    - the bank-account rule of rule 12;
    - one rule for action `submit`, actor kind `human`, giving `require_approval` with `standard` when `is_credit_exceeded` (ADR-0030 rule 7); non-human actors already need approval at submit by the baseline.

    It seeds no thresholds and no rule that lets a non-human post; those are the company's and the author's (open question).

    A rule requiring `standard` approval for both `submit` and `post` of a purchase invoice, for every actor kind, when `is_match_exceeded` is seeded ([ADR-0047](0047-commercial-documents-and-pricing.md) rule 14).

    A rule requiring `standard` approval for `submit` and `post` of `general_journal`, for every actor kind, is seeded ([ADR-0048](0048-cash-bank-receivables-payables.md) rule 15).

**Specific points**

16. Unlocking a period. `UnlockPostingPeriod` (`human_only`, ADR-0012) takes the ID of an approved `period_unlock_request`. That is a non-posting document (period, area, reason) whose `Submit` is a policy point, which always requires at least the lowest-rank procedure. The unlock closes the request in the same transaction, so one request unlocks once, and records the request's `policy_decision_id` in its audit record (ADR-0038 rule 2).
17. Other points:
    - **Matching.** Matchings (`open_item_matching`, ADR-0026 rule 9) are documents with the usual points.
    - **Stock counts** post through the usual points (ADR-0023 rule 18).
    - **Production orders.** Their release is `submit` of type `production_order` (ADR-0034 rule 4); there is no `release` action.
    - **None in Phase 1, defaults apply:** automatic conversion of planned orders and automatic release (ADR-0024 rule 22; ADR-0036), and further record-scope dimensions (ADR-0017 rule 9). Flagged.

**Commands and queries**

18. Commands and queries:
    - **Rules:** `CreatePolicyRule`, `UpdatePolicyRule` (a new version), `EnablePolicyRule`, `DisablePolicyRule`.
    - **Procedures:** `CreateApprovalProcedure`, `UpdateApprovalProcedure`.
    - **Registration.** All are `human_only`, effect class `master_data_change`, change-tracked (ADR-0038 rule 3) and on no agent tool list. One person may change policy alone (open question).
    - **Queries:** `ListPolicyRule`, `ListApprovalProcedure`, `ListPolicyDecision`.
    - **`GetPolicyEvaluation`** (action, type, actor kind, input; computed) is for people only, like `ListAllowedCommand` (ADR-0040 rule 8).
19. Invariants:
    - **INV-82** is restated by rank: every posted document whose decision requires a rank has an `approved` approval on that version whose procedure has at least that rank.
    - **INV-202:** the enabled rule set passes the check of rule 11.
    - **INV-203:** every enabled rule that allows a non-human actor has an owner and a maximum, and confirmation at post and issue.

## Context

DS-28 is needed by step 5. Until then the policy engine is a stub that allows everything, while the hard floors already apply (ADR-0017 rule 17).
- **Already fixed:** ADR-0029 fixed the policy points and the decision record; ADR-0028 fixed the approval context.
- **The brief:** runbook B7 asks for a threshold table per action type with one-level approval, generalized only at the second or third concrete case.
- **The first review:** a single ordered outcome scale was not a strictness order, system defaults would have stopped close jobs, and the monotonicity check covered amount only. This version separates the approval rank from the human-post requirement, evaluates consequence postings as their person, and checks every ordered condition.

SAP's release strategies classify documents and assign release codes; Odoo's approvals are per model. ERPMe keeps one table across documents, with safety floors in the dispatcher.

## Options considered

| Option | For | Against |
| --- | --- | --- |
| Two-dimensional decision, maximum per dimension (chosen) | A real strictness order; order-free; human post and approval combine | Mapped back to ADR-0029's four outcomes |
| One ordered outcome scale | Simple | `human_only` is not stricter than approval (ADR-0009 rule 11) |
| Consequence postings as their person (chosen) | Close jobs and revaluation run without auto-post confirmations | Needs a registry attribute |
| Monotonicity checked on save (chosen) | Catches loosening sets the author would not intend | Breakpoint enumeration on each change |

## Constraints that come with the decision

- **ADR notes:**
  - ADR-0008 rule 1: `is_consequence_posting`;
  - ADR-0009 rules 11, 12, 18: decisions and floors at every post, the no-wait outcome, reversals;
  - ADR-0012 (the `UnlockPostingPeriod` row and the DS-28 constraint): the unlock request;
  - ADR-0017 rule 17: the stub ends at step 5;
  - ADR-0022 rule 2 and ADR-0027 rule 1: `policy` and the imports;
  - ADR-0026 rule 9: matchings;
  - ADR-0028 rule 14: rank;
  - ADR-0029 rules 2, 4, 6, 7, 13: the floors, the human proposal rule, the policy point for a change of actor kind, the stored `required_rank`, `human_post` and matching rules, confirmation by the owner;
  - ADR-0030 rule 7: credit as a condition;
  - ADR-0034 rule 5: release is submit;
  - ADR-0038 rule 2: the unlock decision.
- **Catalogs:** INV-82 restated; INV-202, INV-203.
- **DS-04:** `policy_rule_invalid`; check result `policy_no_eligible_approver`.
- **Other design items:**
  - DS-16: monotonicity and floor tests;
  - DS-34: shadow-mode evidence and unattended postings.
- **Open questions:**
  - defaults;
  - rank substitution;
  - small companies;
  - corrections;
  - reversals without policy;
  - one-person policy changes;
  - thresholds.

## Revisit when

- A second or third concrete case needs more than one level, or conditions the table cannot express (runbook B7).

## Documents updated

- **The lab:** [docs/reviews/2026-11-14-design-validation/](../reviews/2026-11-14-design-validation/README.md): `lab/policy_lab.py`, finding L-11.
- **Catalogs:** [docs/catalogs/invariants.csv](../catalogs/invariants.csv).
- **ADRs:** [docs/adr/0008-command-envelope-and-registry.md](0008-command-envelope-and-registry.md), [docs/adr/0009-document-lifecycle.md](0009-document-lifecycle.md), [docs/adr/0012-posting-periods-and-closing.md](0012-posting-periods-and-closing.md), [docs/adr/0017-permission-envelope.md](0017-permission-envelope.md), [docs/adr/0022-repository-and-engineering-conventions.md](0022-repository-and-engineering-conventions.md), [docs/adr/0026-open-item-core.md](0026-open-item-core.md), [docs/adr/0027-cross-cutting-ownership.md](0027-cross-cutting-ownership.md), [docs/adr/0028-document-lifecycle-hardening.md](0028-document-lifecycle-hardening.md), [docs/adr/0029-proposals-and-agent-safety.md](0029-proposals-and-agent-safety.md), [docs/adr/0030-commercial-seams-and-imports.md](0030-commercial-seams-and-imports.md), [docs/adr/0034-production-orders-and-shop-floor.md](0034-production-orders-and-shop-floor.md), [docs/adr/0038-audit-and-observability.md](0038-audit-and-observability.md): notes.
- **Design files:** [docs/design/DS-04-command-envelope.md](../design/DS-04-command-envelope.md), [docs/design/backlog.md](../design/backlog.md).
- **Glossary:** [docs/spec/00-reading-guide.md](../spec/00-reading-guide.md).
- **Open questions:** [docs/open-questions.md](../open-questions.md).
- **Index and log:** [docs/adr/README.md](README.md); [docs/runbook/step-log.md](../runbook/step-log.md) at acceptance.
