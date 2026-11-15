# ADR-0055: Approval pools and stages

Status: accepted (2026-11-15) under ADR-0005, reviewed by Claude Fable 5.2 (builder Claude Opus 5.5). Design item: DS-28 (extends ADR-0043). Related decisions: D2, D5. Principles 3, 8, 12. ADR-0005, ADR-0008, ADR-0009, ADR-0017, ADR-0022, ADR-0028, ADR-0029, ADR-0038, ADR-0040, ADR-0042, ADR-0043, ADR-0047, ADR-0048, ADR-0053, ADR-0054; spec 03, 07, 14.

## Decision

ADR-0043 decides whether a document needs approval and at which rank, and approves at one level. The author asked (2026-11-15) for approvals grouped by kind of document, with several stages, in the style of SAP Business One. This ADR keeps ADR-0043's policy table and adds what happens after the rank is known.

**Pools.** An `approval_pool` per company groups document types: purchase requests, purchase documents, sales documents, production orders, stock consumption, expenses, and a general pool for everything else. Each document type maps to one pool. A selector may send a document to another pool by a boolean of its policy input, such as `is_direct_expense`.

**Stages.** Each pool has ordered stages. A stage has members (users and roles), a number of approvals required out of its eligible members ("k of n"), a minimum rank, and optional escalation and due days.

**Rank selects stages.** All stages whose minimum rank is at most the decision's rank are required, in sequence. A higher rank therefore never needs fewer approvals, which keeps ADR-0043's monotonic order. Procedures stay as named ranks.

**Execution.** Approvals bind to the document version, as before. An edit voids them, and a rejection at any stage returns the document to draft. Each stage needs k distinct eligible approvers. Nobody who wrote a version approves, and a person counts in one stage only. Each pending stage is the document's one `approval_pending` work item. Substitutes act through ADR-0054's delegations. Agents never approve. When nobody is left who could approve, the work item goes to the company's owner with the reason.

### Rules

**Ownership**

1. Tables, owners and code paths:
   - **`policy`** (layer 2) owns `approval_pool`, `approval_pool_document_type`, `approval_stage` and `approval_stage_member`, beside `approval_procedure` (ADR-0043 rule 1). DDL: [DS-15-access.sql](../design/DS-15-access.sql).
   - **Keys to `permissions`' tables.** `approval_stage.escalation_role_id`, `approval_stage_member.role_id` and `approval_stage_member.user_account_id` are database references to `role` and `user_account`, which `permissions` owns. They are keys only: `policy`'s code never reads assignments; who holds a role is answered by `permissions`' effective-rights function (ADR-0054 rule 2).
   - **Approval rows** stay `documents`' (ADR-0043 rule 1). Each person's decision at a stage is one immutable `approval` row (ADR-0009 rule 11), extended by rule 9. The glossary calls it an approval step. There is no second table for steps: one row per decision is what INV-17 and INV-82 already read.
   - **The approval work item** and its owner column `work_item.owner_approval_stage_id` are `work`'s (ADR-0042 rule 2 gets a note).
   - **Evaluation by registered functions.** As in ADR-0054 rule 2, each module registers functions with the dispatcher and `app` wires them: `policy` the selector, the plan and the stage reader; `permissions` effective rights, delegations and the segregation checks; `documents` the document actors and the counted approvals. The dispatcher combines them for `Submit`, `Approve` and `Reject` (rules 6–8), and `work` filters approval items through a registered visibility function (rule 12). Beyond ADR-0022 rule 2's existing imports, `work`, `documents`, `permissions` and `policy` import nothing from each other; ADR-0022 rule 2 and ADR-0043 rule 1 get notes.

**Pools and selection**

2. `approval_pool` (company data): `code`, `name`, `basis`, `is_active`. The core seeds these pools in every company:

   | Pool | Document types (default row) |
   | --- | --- |
   | `pr` | `purchase_request` |
   | `po` | `purchase_order`, `purchase_invoice`, `purchase_return`, `purchase_credit_note`, `purchase_debit_note`, `gr_ir_write_off` |
   | `sales` | `quotation`, `sales_order`, `sales_invoice`, `sales_return`, `credit_note`, `debit_note` |
   | `mo` | `production_order`, `production_issue` |
   | `consumption` | `internal_consumption`, `other_issue`, `scrap`, `stock_count` |
   | `expense` | `advance_settlement`, `general_journal`; and by selector, payments and purchase invoices with `is_direct_expense` |
   | `general` | every other type that can wait for approval: payments without expense lines, receipts, `change_proposal`, `period_unlock_request`, `write_off`, and the rest |

   - **Companies** may add pools (for example `payment`) and change the mapping with `UpdateApprovalPool`. The seeded mapping is interim (open question).
   - **`general` stays active.** It is the pool of last resort (rule 3), so it cannot be deactivated (`approval_pool_invalid`).
   - **Types that may not wait** never reach a pool (rule 15). For `sales_invoice`, `sales_return`, `credit_note` and `debit_note` this depends on the regime: `is_approval_hold_allowed` is derived from the regime setting `documents.issuance_without_delay` on the document date ([ADR-0053](0053-core-neutrality.md) rule 8). The core default lets them wait, so they keep their `sales` mapping; where a package sets the setting true, rule 15 applies and the mapping is unused. The pool design itself holds no country rule.

   Note: shop-floor facts never wait: `operation_confirmation`, `production_receipt` and `service_receipt` are registered `is_approval_hold_allowed: false`, so they reach no pool (rule 15). Pool `mo` holds `production_order` only. `production_issue` moves to `consumption`, beside the inventory consumption issues, because an issue above requirement may wait for approval (`is_above_requirement`, [ADR-0034](0034-production-orders-and-shop-floor.md) rule 5's note) (holistic review 2026-11-15, item P12).

   Note (flow review, 2026-11-15): the core seed stays minimal. Under [ADR-0043](0043-policy-and-approval.md) rule 15's seed, a person's `Submit` of a purchase request, purchase order, quotation or production order matches no rule, gets no rank and goes straight to `approved`, so pools `pr`, `po`, `mo` and, for quotations, `sales` are reached only through company rules. The core seeds no thresholds; DS-17's `vn_*` profiles add sample company rules and stage members through setup events ([DS-17](../design/DS-17-synthetic-dataset.md) rules 5 and 18, notes).
3. `approval_pool_document_type` (company data) holds the selector:
   - **Columns:** `document_type`, `position`, `condition_input`, `approval_pool_id`.
   - **The default row** has position 0 and no condition. The database allows exactly one per document type and company.
   - **Conditional rows** have position 1 or more and name a boolean input of that type's `policy_input` (ADR-0043 rule 4).
   - **Selection.** Conditional rows are tried in position order; the first whose input is true chooses the pool. Otherwise the default row does. With no row for the type, the pool is `general`. The selection is recorded in the decision (rule 6), so it is never repeated differently.
   - **Seeded conditional rows:** `cash_payment` and `bank_payment` with `is_direct_expense` → `expense` (default `general`); `purchase_invoice` with `is_direct_expense` → `expense` (default `po`).
   - **Purchase invoices.** For a purchase invoice, `is_direct_expense` is true when no line references a purchase order line and every line is an `expense` or service line (a note on ADR-0047 rule 12). It joins the condition of ADR-0048 rule 3 in ADR-0043 rule 3.
   - **Monotonic selection.** A conditional row may only send a document to a pool that needs at least as many approvals at every rank as the default pool (the sum of k over the stages rule 5 requires). Booleans are riskier when true (ADR-0043 rule 11), so a riskier document never needs fewer approvals. Otherwise `approval_pool_invalid`.

**Stages**

4. `approval_stage` (company data) and its members:
   - **Columns:** pool, `sequence` (unique in the pool), `code`, `name`, `min_rank`, `required_approvals` (k, at least 1), `scope_binding` (`document_scope` or `company`, from ADR-0043 rule 2), optional `escalation_role_id`, `due_days` (calendar days, default 2), `is_active`.
   - **Members:** `approval_stage_member` rows, each a user or a role. A stage has at least one.
   - **Checks on save** (`approval_pool_invalid`), run by `CreateApprovalPool`, `UpdateApprovalPool` and also by ADR-0043's `CreateApprovalProcedure` and `UpdateApprovalProcedure`, since a procedure's rank or activity changes what the stages must cover (a note on ADR-0043 rule 18):
     - every active pool has an active stage, and `min_rank` does not decrease along `sequence` among active stages;
     - the first active stage's `min_rank` is at most the lowest active procedure rank, so every rank requires at least one stage;
     - every active stage has a member;
     - no selector row names an inactive pool, and `general` is active;
     - rule 3's monotonic selection.
   - **Too few people.** For each active procedure rank, the required stages are satisfiable when their places can be filled by distinct people: k places per stage, each filled by a different active user who is directly eligible for that stage in some scope (a member who holds an `Approve<Type>` of the pool's types; rule 7, condition 2). Outside ADR-0054's small-company mode, the preparer may not approve, so the places must still be fillable with any one of those people left out. Saving returns the check result `approval_stage_unsatisfiable`, naming each rank that fails. `Submit` returns the same check result for its own plan and document, counting the document's writers out (rule 7, condition 5). This replaces `policy_no_eligible_approver` for stages; ADR-0043 rule 13 gets a note.

**Link to ADR-0043**

5. Required stages:
   - **None.** A decision without a rank requires no stage.
   - **Otherwise** it requires every active stage of the selected pool whose `min_rank` is at most the decision's rank, in `sequence` order. Because `min_rank` does not decrease, these are always the first stages of the pool, and a higher rank adds stages at the end.
   - **Never empty.** A decision with a rank and no required stage is refused with `approval_plan_empty`. Rule 4's checks make this unreachable in a consistent company; the refusal keeps an inconsistent one from approving nothing.
   - **Monotonic.** A higher rank never requires fewer approvals, so ADR-0043 rule 11's check still describes the strictness of a rule set.
   - **Procedures** keep `code`, `name`, `rank` and `is_active`. Their `approver_role` and `scope_binding` move to the stages (a note on ADR-0043 rule 2).
   - **The seed migrates** (a note on ADR-0043 rule 15). Each seeded pool gets two stages, whose role members are the company's roles with these templates (ADR-0054 rule 11):
     - `standard`: `min_rank` 10, k 1, members `accountant`, `chief_accountant` and `owner`. These are the procedure `standard`'s approver role, the role that could satisfy rank 10 through `senior` under ADR-0043 rule 2, and the owner, so that a company always has someone in every stage;
     - `senior`: `min_rank` 20, k 1, members `chief_accountant` and `owner`.
   - **What changes.** Under ADR-0043 one chief accountant's approval satisfied rank 20. Now rank 20 needs two different people, one per stage. This is the cumulative meaning of stages that the author asked for, and it is flagged. Members per pool (for example a sales manager for `sales`) are the company's choice.

   Note: pool `mo`'s first stage `standard` also seeds the role with template `production_planner` as a member. That template gets `can_approve` on `production_order`, with `edit` on `delegation` as every approving template has, so a planner can release orders at rank 10 ([ADR-0054](0054-users-roles-and-authorizations.md) rule 11's note). Interim, flagged for the author (holistic review 2026-11-15, item P14).

   Note (flow review, 2026-11-15): the `general` pool's `standard` stage also has the role members `sales_manager`, `purchasing_manager` and `production_planner`, and these templates have `edit` with `can_approve` on `change_proposal` ([ADR-0054](0054-users-roles-and-authorizations.md) rule 11 note), so they submit change proposals and approve them. Eligibility still needs the target permissions (rule 7; ADR-0043 rule 12): planning proposals are approved by the production planner, the purchasing manager or the owner (accountants and chief accountants read planning only); partner proposals (customer onboarding, supplier item mappings) by the sales manager, the purchasing manager or the owner; price-list proposals by the purchasing manager or the owner. The other pools keep the seed.
6. The decision records the plan. At every policy point that gives a rank, `policy_decision` (ADR-0029 rule 7) also stores:
   - `approval_pool_id`;
   - `approval_plan`: the required stages with their ID, `sequence`, `code`, `min_rank`, k, `scope_binding`, `escalation_role_id` and `due_days`, as they were in force on `clock.today`;
   - `continues_policy_decision_id` for a resubmission that continues the round (rule 11).

   A later change to the pool affects only later decisions. Members are not frozen: eligibility is evaluated at each `Approve` (rule 7).

**Execution**

7. Who may approve the current stage. The current stage is the first stage of the plan that has fewer than k counted approvals (rule 8). A person may approve or reject it when condition 1 holds, one of conditions 2 to 4 holds, and conditions 5 to 8 hold:
   1. **A human** actor (ADR-0017 rule 15).
   2. **Directly eligible:** a member AND holding the permission, for a stage whose stage and pool are still active. A member is listed as a user member, or holds a member role through an assignment in force; with `scope_binding` `document_scope`, that assignment's record scope must cover the document, and with `company` any assignment in the company counts. The permission is `Approve<Type>` (ADR-0054 rule 9) with the document inside their read scope (ADR-0054 rule 13).
   3. **Or a substitute** of a directly eligible person, through a delegation of kind `approval` in force from that person (ADR-0054 rule 21).
   4. **Or an escalation holder,** once the stage is overdue (rule 13): holding the stage's escalation role under the same scope binding, AND `Approve<Type>` with the document inside their read scope.
   5. **Not a writer.** Neither the person nor, for a substitute, the delegator is a human who wrote any version of the document: a human actor of a version, the `on_behalf_of` of any version, or the `on_behalf_of` of a version's origin agent run (ADR-0017 rule 16). This makes the author and every later editor ineligible, including through an agent acting for them.
   6. **Not counted yet.** Neither the person nor the delegator appears in a counted approval (rule 8): an approval of the current round at a stage of the current plan, at any stage of it. Approvals of earlier rounds, and approvals at stages the current plan no longer requires, are not read.
   7. **No segregation pair** of ADR-0054 rule 19 is broken.
   8. **No stranded stage** (`Approve` only). Consider the places still open in the plan: this stage's and every later required stage's, filled by distinct people who meet conditions 1, 2 or 3, and 5 to 7 for the stage they fill. If those places can be filled now, but no longer once this person counts at this stage, then this person is needed for a later stage and nobody else can take that place: the approval is refused with `approval_would_strand_stage`. If the places cannot be filled either way, the approval is allowed and rule 12's fallback applies. `ListAllowedCommand` and the plan show it before execution, like a check result. Recovery: another eligible person approves this stage; the author updates or cancels the document, which ends the round; or a person changes the stage's members with `UpdateApprovalPool`, which takes effect at once because members are not frozen.

   **Direct eligibility wins.** A person directly eligible acts as themselves, even if a delegation would also make them eligible. Otherwise `Approve` and `Reject` may name `delegated_from_user_id`, an optional field of their payload (a note on ADR-0009 rule 2), the delegator they act for; if they name none, the delegation in force with the lowest ID among those that make them eligible is used. Escalation is used only when no delegation applies.

   Errors: `human_only` (1), `approver_not_eligible` (none of 2–4, or a named delegator who does not make them eligible), `segregation_of_duties` (5, 7), `approval_already_given` (6), `approval_would_strand_stage` (8). For a change proposal the approver also holds the target permissions and field classes (ADR-0043 rule 12).

   **Small companies.** In ADR-0054's small-company mode, condition 5 is lifted for the document's human writers and recorded as a segregation exception. The agent-run part of condition 5 is a hard floor and is never lifted, and neither is condition 6. Rule 20 walks through companies of one and two people.
8. Counting and completion:
   - **The round.** A round starts with a `Submit` from draft. It ends with `Post` (or `Issue`) of the document, a rejection, an edit or a cancel. A resubmission without edit after `approval_context_changed` continues it when the selected pool stays the same, and starts a new round when the pool changes (rule 11).
   - **Counted approvals** of a stage are its `approved` rows within the current round, for stages of the current plan. A round has one version, because an edit ends it. When a continued round's new plan drops a stage (a lower rank, or a stage deactivated in between), the approvals at that stage stay recorded but no longer count.
   - **Stage complete.** When a stage reaches k, the next required stage becomes current on that day, and its work item is raised in the same transaction (rule 12).
   - **Document approved.** When the last required stage reaches k, the document becomes `approved` (ADR-0009 rule 4) and `<Type>Approved` is emitted. The round stays open until the document is posted, so a context change at `Post` can still continue it.
   - **Order.** Approvals are recorded only for the current stage, so stage s is never approved before stages 1 to s−1 are complete (INV-226).

   Note: for types with no posting step (orders, production orders, change proposals, period unlock requests), a round ends when the last required stage completes and the document becomes `approved`. For an e-invoiced document it ends with `Issue`, whose decision the completion `Post` carries ([ADR-0043](0043-policy-and-approval.md) rule 5 note). `Submit` from an actor carrying an origin agent run is refused with `origin_run_submit_not_allowed`: a person submits what an agent chain drafted ([ADR-0029](0029-proposals-and-agent-safety.md) rule 6 note).
9. The `approval` row (ADR-0009 rule 11) gains:
   - `approval_stage_id` and `approval_pool_id`;
   - `delegated_from_user_id`, empty unless a substitute acted;
   - `is_escalated`, true when the approver was eligible only through the escalation role;
   - `policy_decision_id`, as now (ADR-0028 rule 14).

   `reason` stays required for both decisions and serves as the comment. Rows stay immutable.
10. Rejection and edits:
    - **Reject.** `Reject<Type>` by a person who meets rule 7's conditions 1 to 7 returns the document to `draft` with the reason (ADR-0009 rule 4). The round ends and the work item is resolved. A later `Submit`, with or without an edit, starts a new round, so earlier approvals no longer count.
    - **Edit.** `Update` writes a new version, voids every approval (ADR-0009 rule 9) and ends the round. Change orders bind approvals to the pending version in the same way (ADR-0028 rule 4).
11. Approval context (ADR-0028 rule 14, which gets a note):
    - **When it applies.** At `Post` of an approved document, or `Issue`, with a changed `policy_input_hash`, a new decision is made.
    - **Approvals stand** when every stage its plan requires already has k counted approvals in the round, matched by stage ID. Eligibility is not re-evaluated. The `Post` then ends the round.
    - **Otherwise** `approval_context_changed`. The document may be resubmitted without edit (`approved → pending_approval`). When the new decision selects the same pool, it continues the round: a stage that appears in both plans keeps its approvals and only the missing stages are pending.
    - **A different pool.** If the selector now chooses another pool, the resubmission starts a new round: no earlier approval counts, and every stage of the new plan is pending.

**Work queue**

12. Pending stages are work items (ADR-0042 rule 17):
    - **One item.** A document in `pending_approval` has exactly one open `approval_pending` item, for its current stage (INV-204 unchanged). Its open key is the document ID. When a stage completes, its item is resolved and the next stage's item is raised in the same transaction.
    - **Owner.** A new owner kind `approval_stage` with `owner_approval_stage_id` (a note on ADR-0042 rules 2 and 7). The item is visible to everyone eligible under rule 7: members in scope, substitutes in force, and escalation holders once overdue, through the visibility function of rule 1.
    - **Fallback to the owner.** When nobody could approve the current stage, the item's owner becomes `company_owner` (ADR-0042 rule 7's fallback; ADR-0054 rule 11), with the stage and a reason in `details`: `members_left` (no member holds the role or permission any more), `members_disabled`, `members_all_writers` or `members_all_counted`, or `stage_inactive` or `pool_inactive` (deactivated after the plan was recorded). Rule 4's checks keep a selector from naming an inactive pool and an active pool from having no stage, so those states need no reason of their own. This is checked when the stage becomes current and by the daily `RunApprovalEscalation` job (rule 13), which moves the item back to the stage once someone is eligible again. Nobody is eligible for a stage of a recorded plan whose stage or pool was deactivated afterwards. The owner fixes the members or reactivates the stage, or the author updates or cancels the document, and a new submission takes the stages then in force.
    - **Due date.** The day the stage became current plus the stage's `due_days`, in calendar days, because `documents` is a layer-2 caller (ADR-0042 rule 5). The kind's due rule is `stage_due_days` (a note on ADR-0042 rule 8).
    - **Claims.** `Approve` needs no claim, and a claim never stops another eligible person from approving, since a stage may need several approvers.
    - **Agents.** An agent type may declare `approval_pending` only to prepare the approval file (spec 07: summary, history, risks) as notes and evidence. Agents never approve (ADR-0017 rule 15).
13. Escalation:
    - **The rule.** When `clock.today` is after a stage's due date (rule 12), holders of its `escalation_role_id` become eligible for that stage too (rule 7, condition 4). The escalation never lowers k and never lifts conditions 5 to 8.
    - **The job.** A daily system job, `RunApprovalEscalation`, sets the priority of overdue approval items to `high`, adds the escalation role to the evidence, and applies rule 12's fallback. It changes no approval.
    - **Phase.** Spec 07 and ADR-0042 rule 8 placed escalation after Phase 1. The author's request brings it into Phase 1 (a note on ADR-0042 rule 8; spec 07's wording is proposed in an open question, because specs are the author's, ADR-0032 rule 7; flagged).
14. Delegation. A substitute acts under ADR-0054 rule 21. The approval row records `delegated_from_user_id`. Both the substitute and the delegator must pass conditions 5 to 7 of rule 7.

**Unchanged points**

15. Documents that may not wait (`is_approval_hold_allowed: false`, including the invoice types for which ADR-0053 rule 8 derives it from `documents.issuance_without_delay`): a rank becomes `human_post` and the stored outcome is `human_only` (ADR-0043 rule 10). No pool or stage applies. The value is read for the document date when the decision is made, so a document's pool use follows the setting in force for it.
16. Other points:
    - **Change proposals and period unlock requests** go to the `general` pool by default.
    - **Floors.** ADR-0043 rule 9's floors are unchanged. Floor 7 (change proposals) and floor 8 (types with no posting step) give at least the lowest rank, which requires at least the first stage.
    - **Reversals** keep no policy step (ADR-0043 rule 9.9).

    Note (flow review, 2026-11-15): "the approving human" of [ADR-0029](0029-proposals-and-agent-safety.md) rule 3, on whose behalf an approved change proposal executes, is the approver whose approval completed the plan: the counted approval that brought the last required stage to k (rule 8). That human is the converter of the drafts the execution creates ([ADR-0047](0047-commercial-documents-and-pricing.md) rule 9; [ADR-0024](0024-planning.md) rule 22), so a writer of those drafts who cannot approve them (rule 7, condition 5); approvers at earlier stages are not.

    Note (simulation review, 2026-11-15): a purchasing manager who approves planning proposals (pool `general`) becomes the converter of the purchase requests the execution drafts, and cannot approve them (the note above). A company should therefore not make the purchasing manager the only member of pool `pr`'s `standard` stage; [DS-17](../design/DS-17-synthetic-dataset.md)'s `vn_*` profiles add the chief accountant (its rule 18 note).

**Commands, queries and catalogs**

17. Commands and queries:
    - **`CreateApprovalPool`** and **`UpdateApprovalPool`** (stages, members and selector rows as one change; a list). They are `human_only`, `master_data_change`, change-tracked (ADR-0038 rule 3) and on no agent tool list, like ADR-0043 rule 18.
    - **`RunApprovalEscalation`:** a system job command (rules 12–13).
    - **Queries:** `ListApprovalPool`.
    - **`GetApprovalProgress`** (document): a computed query, an exception to ADR-0004 rule 21 like `GetPrice`. It returns the plan, the current stage, the counted approvals, the due date and any fallback reason, and whether the caller is eligible, with the reason when not. Agents may call it to prepare approval files; it writes no denial records.
18. Catalog rows:
    - **Errors:** `approver_not_eligible` (permission), `approval_already_given`, `approval_would_strand_stage` and `approval_plan_empty` (precondition), `approval_pool_invalid` (validation). `segregation_of_duties` also covers rule 7, condition 5.
    - **Check result:** `approval_stage_unsatisfiable` (on save and at `Submit`).
    - **Work item kinds:** `approval_pending` gets owner rule `approval_stage` and due rule `stage_due_days`. No new kind.
    - **Invariants**, first at step 5:
      - **INV-82** is restated by stages: every posted document whose decision requires a rank has, for every stage of the plan of the decision its `Post` used, at least k counted `approved` approvals on the posted version within the round that the `Post` ended; documents whose outcome is `human_only` are excluded;
      - **INV-224:** within one round no human appears in two counted approvals (at stages of the round's latest plan), as approver or delegator;
      - **INV-225:** no counted approval's approver or delegator wrote a version of the document (rule 7, condition 5), unless a `segregation_exception` records it under the small-company mode; the agent-run part has no exception;
      - **INV-226:** every approval row's stage was current when it was decided: all earlier stages of the plan had k counted approvals before it;
      - **INV-230:** every policy decision with a rank has a non-empty `approval_plan`.
    - **Edge cases:**
      - EC-112: a purchase order above the senior threshold, approved by one accountant and then by two of three managers in a stage with k = 2;
      - EC-113: a document edited after its first stage, whose approvals are voided;
      - EC-114: a rejection at the second stage, after which resubmission starts again at the first;
      - EC-115: approval by a substitute inside the delegation window, and refusal after it;
      - EC-117: in a two-person company in small-company mode, the owner tries to approve the first stage of a rank-20 document the accountant wrote and is refused with `approval_would_strand_stage`; the accountant approves the first stage and the owner the second.
    - **Glossary:** approval pool, approval stage, approval step, approval round, approval plan; the approval procedure row changes.
19. Lab check `t12_access.py` ([validation lab](../reviews/2026-11-14-design-validation/README.md)), pure functions on the DS-15 DDL's shapes:
    - rank selection, monotonicity and the refusal of an empty plan;
    - the save checks, `general` kept active, and procedure changes re-running them;
    - satisfiability by distinct people, with and without the small-company mode;
    - k of n with distinct approvers across stages;
    - writer and agent-run exclusion;
    - edit invalidation, rejection reset, and the round ending at `Post`;
    - resubmission after a context change keeping stage approvals, and a pool switch starting a new round;
    - the selector by `is_direct_expense` and its monotonic check;
    - delegation eligibility (direct membership first, a named delegator, the lowest delegation ID) and escalation from the day a stage became current;
    - the stranded-stage refusal and the owner fallback;
    - the one-person and two-person walk-throughs of rule 20.

**Small teams**

20. Walk-throughs with the seeded stages (rule 5) and the seeded procedures `standard` (rank 10) and `senior` (rank 20). ADR-0017 rules 15–16 hold in both: agents never approve, and the human an agent run acted for never approves its drafts.
    - **One person, the owner O.** Without the small-company mode, O writes every document and condition 5 excludes O, so no ranked decision can be approved; saving the stages returns `approval_stage_unsatisfiable` for ranks 10 and 20. With the mode on: a rank-10 document O wrote is approved by O at `standard`, with a segregation exception, and reviewed in the period review (ADR-0054 rule 20). A rank-20 document needs two distinct people (condition 6), so one person cannot satisfy it: `Submit` returns `approval_stage_unsatisfiable`; O may still approve `standard` (condition 8 refuses only avoidable strandings), after which the item falls back to O as `company_owner` with reason `members_all_counted`; and the document can only be updated to a lower rank or canceled. How a one-person company meets such approvals is ADR-0017 rule 17's open question; a company of one should not configure rules that require rank 20.
    - **Two people, the owner O and an accountant A**, with the mode off. A document A wrote: at rank 10, O approves `standard`. At rank 20, `standard` can be approved by O only (A is the writer), and then `senior` has nobody left, so rank 20 is unsatisfiable and `Submit` says so. A document O wrote: at rank 10, A approves; at rank 20, A approves `standard` and `senior` needs `chief_accountant` or `owner`, which leaves only O, the writer. So without the mode, two people satisfy rank 10 only.
    - **Two people with the mode on.** A document A wrote at rank 20: if O approves `standard` first, `senior` could then be filled by nobody (A is not a member of `senior`), so O's approval is refused with `approval_would_strand_stage` (condition 8). A approves `standard` (own document, recorded as an exception) and O approves `senior`. A document O wrote at rank 20: A approves `standard`, and O approves `senior` with an exception. Either way two different people approve, and every own-document approval is in the owner's period review.

## Context

ADR-0043 was written for runbook B7: one level, generalized only at the second or third concrete case. The author's request (2026-11-15) names six concrete cases at once: purchase requests, purchase orders, sales, production orders, consumption and expenses.

Spec 07 sees Business One as the model and lists multiple levels, minimum approvers per level, delegation and escalation after Phase 1. ADR-0032 rule 9 left multi-level approval open as a Phase 1 candidate. This ADR moves them into Phase 1 at the author's request, which is a scope change (ADR-0005). It is recorded as such: a note on ADR-0032 rule 9, and draft wording for spec 07 in an open question, since specs are the author's (ADR-0032 rule 7).

**Business One,** studied for its concepts: approval templates name originators, documents, stages and conditions. Each stage has authorizers and a number of approvals required out of them, and stages run in order.

**SAP S/4HANA:** release strategies give classes of purchasing documents a sequence of release codes.

**What ERPMe changes.** It keeps conditions in one place, the policy table (spec 07: "the approval engine never evaluates conditions itself"). The rank is the bridge: the policy says how serious a document is, and the pool says who approves at that level. Pools are by document group rather than by originator, because ERPMe's segregation rules already handle who originates.

**Why exclude writers.** ADR-0043 rule 13 let a person approve their own document until the author decides. With several stages and k of n, four eyes is the point of the design, so this ADR excludes writers by default. The small-company mode of ADR-0054 rule 20 is the explicit way back, flagged for the author.

**Why a document never waits silently.** Members are evaluated live, so people leaving, a stage being deactivated or an early approval by the wrong person can leave a stage that nobody can fill. Rule 7's condition 8 prevents the avoidable case, and rule 12's fallback makes every other case visible to the owner with its reason.

## Options considered

| Option | For | Against |
| --- | --- | --- |
| Pools of document types with ranked stages (chosen) | Business One's structure; conditions stay in the policy table; monotonic by construction | Rank 20 now needs two people where it needed one |
| Approval templates per originator (Business One) | Familiar | Conditions in two places; originator rules duplicate role and segregation data |
| Stages with their own conditions | Very flexible | A second rule engine beside ADR-0043, against spec 07 |
| Each rank picks one stage, not a prefix | One senior approver can be enough | A pool with fewer stages at a higher rank is easy to misconfigure; resubmission loses collected stages |
| Parallel stages | Faster | Sequencing, counting and the single work item get harder; later, if needed |
| A separate `approval_step` table | Matches the request's wording | Two tables for one fact; INV-17 and INV-82 already read `approval` |
| Freeze stage members in the decision | Nothing changes while pending | A member who leaves blocks the document; a new member cannot help |
| Writers excluded by default, exception mode for small companies (chosen) | Four eyes as the default | Changes ADR-0043 rule 13's interim; small companies need the mode |
| Refuse an approval that strands a later stage (chosen) | The document stays approvable; the refusal says why | One more check per approval |
| Let any eligible person approve any stage in any order of people | Simpler | In small teams the wrong first approver can block the document for good |

## Constraints that come with the decision

- **ADR notes:**
  - ADR-0043 rules 1, 2, 13, 15, 18, 19: registered functions, procedures as ranks, stage eligibility, the migrated seed, the pool commands and the procedure commands re-running the pool checks, INV-82;
  - ADR-0009 rules 2, 11: the optional payload field `delegated_from_user_id` of `Approve` and `Reject`; the approval row's columns;
  - ADR-0022 rule 2: registered functions, no new import;
  - ADR-0028 rule 14: the comparison by stages and the round;
  - ADR-0042 rules 2, 7, 8, 17: owner kind `approval_stage`, the owner fallback, due rule `stage_due_days`, escalation in Phase 1, one item per current stage;
  - ADR-0047 rule 12: `is_direct_expense` for purchase invoices;
  - ADR-0032 rule 9: multi-level approval requested by the author.
- **Spec:** spec 07 is the author's document (ADR-0032 rule 7). Draft wording is proposed in an open question: move "multiple levels, sequential, minimum approvers per level" and "delegation and escalation" from "(After Phase 1)" to Phase 1, and replace "Phase 1 approves at one level by threshold" with stages selected by rank; keep parallel levels and channels beyond the web after Phase 1.
- **DDL:** [DS-15-access.sql](../design/DS-15-access.sql): pools, selector, stages, members. The columns rules 6, 9 and 12 add to `policy_decision`, `approval` and `work_item` are listed there as comments, since those tables have no DDL draft yet.
- **DS-04:** the errors and check result of rule 18.
- **Catalogs:** INV-82 restated, INV-224 to INV-226 and INV-230, edge cases, the `approval_pending` owner and due rules.
- **Other design items:**
  - DS-16: the invariants and a property test over random plans;
  - DS-17: the edge cases in the dataset;
  - DS-30: the approval inbox shows the stage, the counted approvals, k and any fallback reason.
- **Open questions:** default members per pool; the type-to-pool mapping; rank 20 needing two people; escalation, multiple levels and delegation in Phase 1; the default due days; writers excluded from approval.

## Revisit when

- A company needs parallel stages, conditions per stage, or members chosen by the document (for example the requester's manager).
- Approval channels beyond the web arrive (spec 07).

## Documents updated

- **The DDL draft:** [docs/design/DS-15-access.sql](../design/DS-15-access.sql) (with ADR-0054).
- **The lab:** [docs/reviews/2026-11-14-design-validation/](../reviews/2026-11-14-design-validation/README.md): `lab/t12_access.py`.
- **ADRs:** notes in ADR-0009, ADR-0022, ADR-0028, ADR-0032, ADR-0042, ADR-0043 and ADR-0047.
- **Design files:** [docs/design/DS-04-command-envelope.md](../design/DS-04-command-envelope.md), [docs/design/backlog.md](../design/backlog.md).
- **Catalogs:** [invariants.csv](../catalogs/invariants.csv), [edge-cases.csv](../catalogs/edge-cases.csv), [work-item-kinds.csv](../catalogs/work-item-kinds.csv).
- **Glossary:** [docs/spec/00-reading-guide.md](../spec/00-reading-guide.md).
- **Open questions:** [docs/open-questions.md](../open-questions.md).
- **Index and log:** [docs/adr/README.md](README.md); [docs/runbook/step-log.md](../runbook/step-log.md) at acceptance.
