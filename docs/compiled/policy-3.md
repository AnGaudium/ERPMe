Module: policy    Chunk: 3 of 4    Source ADRs: ADR-0055, ADR-0059
Build step(s): 3, 5    Generated from index: 30d5706    Compiled by: Claude Fable 5.2, 2026-11-21

# `policy` compiled spec, chunk 3: pool selector, approval stages, eligibility, rounds, escalation, artifact hooks

## Purpose

This chunk states the part of `policy` law on: the selector that sends a document type to an approval pool, approval stages and their members, the approval plan a decision records, who may approve a stage, approval rounds and counting, rejection, edits and approval context, the pending-stage work item, escalation, delegation, and the hooks `policy` exposes to `configuration` and `cash` for tunable functions. `policy` decides rank, pool and plan; the `approval` rows and the document states belong to `documents`, work items to `work`, roles and delegations to `permissions`. `policy` imports no layer-4 module (R451). Policy rules, procedures, decisions, pools and the auto-post gateway are in the other chunks.

## Entities and tables

DDL: `docs/design/DS-15-access.sql`.

| Table | Meaning | Key | Parent | Owner |
| --- | --- | --- | --- | --- |
| `approval_pool_document_type` | Selector row: which pool a document type uses, by default or under a boolean policy input (R401-R405) | `id`; (`company_id`, `document_type`, `position`) unique (`uq_approval_pool_document_type_key`) | `approval_pool` | `policy` |
| `approval_stage` | One stage of a pool: its rank floor, the approvals it needs, scope binding, escalation role and due days (R406); the DDL bounds `due_days` to 1 to 90 | `id`; (`approval_pool_id`, `sequence`) unique; (`approval_pool_id`, `code`) unique; (`company_id`, `id`) | `approval_pool` | `policy` |
| `approval_stage_member` | A user or a role that is a member of a stage, with its `position` (R407); `member_kind` is `user` or `role` (DDL) | `id`; (`approval_stage_id`, `user_account_id`, `role_id`) unique (`ux_approval_stage_member`) | `approval_stage` | `policy` |

Named by rules of this chunk, with their rows in other chunks: `approval_pool`, `approval_procedure`, `policy_decision`, `policy_rule_version`.

Reads: `approval`, `document`, `document_version`, `change_proposal` (`documents`); `work_item` (`work`); `role`, `user_account`, `delegation`, `segregation_exception` (`permissions`); `company` (`master_data`); `parameter_set`, `parameter_set_version`, `parameter_set_value`, `artifact_transition`, `artifact_promotion_evidence`, `artifact_shadow_outcome`, `golden_case_label`, `artifact_monitor_snapshot` (`configuration`); `agent_promotion_evidence` (`agent_runs`).

## Commands and queries

Authorization area (catalog `authorization-areas.csv`): the function `policy` under `administration` covers policy rules, approval procedures and approval pools and policy decisions; `RunApprovalEscalation` is `is_internal_only`. The level of a verb is the catalog's (`Create` and `Update`: `edit`; `List` and `Get`: `read`). `Approve` and `Reject` are given by the role's approval flag on the document type's own leaf, not by a level (ADR-0054.R9).

| Name | Actor and authorization | Input | Effect | Events | Error codes |
| --- | --- | --- | --- | --- | --- |
| `CreateApprovalPool` | `human_only`, `master_data_change`, change-tracked, on no agent tool list; area `policy` | a pool with its stages, members and selector rows as one change (a list) | Creates the pool after the save checks of R408 and R409 (R442) | not stated | `approval_pool_invalid`; check result `approval_stage_unsatisfiable` |
| `UpdateApprovalPool` | as `CreateApprovalPool` | stages, members and selector rows as one change (a list) | Changes the pool; member changes take effect at once (R418, R442) | not stated | `approval_pool_invalid`; check result `approval_stage_unsatisfiable` |
| `RunApprovalEscalation` | system job command, daily; `is_internal_only` | not stated | Sets overdue approval items to `high`, adds the escalation role to the evidence, applies the fallback of R433; changes no approval (R436) | not stated | not stated |
| `ListApprovalPool` | query; area `policy` | not stated | Lists approval pools (R443) | none | not stated |
| `GetApprovalProgress` | computed query; agents may call it; area not stated | document | Returns the plan, current stage, counted approvals, due date, fallback reason and the caller's eligibility with the reason when not; writes no denial records (R444) | none | not stated |

Commands of other modules that this chunk constrains: `Submit`, `Approve<Type>`, `Reject<Type>`, `Update`, `Post`, `Issue` (`documents`; errors `human_only`, `approver_not_eligible`, `segregation_of_duties`, `approval_already_given`, `approval_would_strand_stage`, `approval_plan_empty`, `approval_context_changed`, `origin_run_submit_not_allowed`, check result `approval_stage_unsatisfiable`); `CreateApprovalProcedure` and `UpdateApprovalProcedure` (ADR-0043.R18) run the save checks of R408.

Contract functions and hooks, not registered commands: `mark_auto_post_evidence_outdated(company, function_code, by_id)` (R452); the evidence hook function `auto_post_eligibility`, registered by `cash` (R451); the hook `artifact_in_force_changed` declared by `configuration` and registered by `policy` (R452); the visibility function of ADR-0055.R1 (R432).

## Rules

### Pool selector

R401. `approval_pool_document_type` (company data) holds the selector, with the columns `document_type`, `position`, `condition_input`, `approval_pool_id`. The default row has position 0 and no condition; the database allows at most one per document type and company. Conditional rows have position 1 or more and name a boolean input of that type's `policy_input` (ADR-0043.R4).
Source: ADR-0055.R3

R402. Selection: conditional rows are tried in position order, and the first whose input is true chooses the pool; otherwise the default row does. With no row for the type, the pool is `general`. The selection is recorded in the decision (R415), so it is never repeated differently.
Source: ADR-0055.R3

R403. Seeded conditional rows: `cash_payment` and `bank_payment` with `is_direct_expense` send to `expense` (default `general`); `purchase_invoice` with `is_direct_expense` sends to `expense` (default `po`).
Source: ADR-0055.R3

R404. For a purchase invoice, `is_direct_expense` is true when no line references a purchase order line and every line is an `expense` or service line (ADR-0047.R12). In ADR-0043.R3 it joins the condition of ADR-0048.R3.
Source: ADR-0055.R3

R405. Monotonic selection: a conditional row may only send a document to a pool that needs at least as many approvals at every rank as the default pool, measured as the sum of k over the stages R410 requires. Booleans are riskier when true (ADR-0043.R11), so a riskier document never needs fewer approvals. A row that breaks this is refused with `approval_pool_invalid`.
Source: ADR-0055.R3

### Stages and members

R406. `approval_stage` (company data) has the columns: pool, `sequence` (unique in the pool), `code`, `name`, `min_rank`, `required_approvals` (k, at least 1), `scope_binding` (`document_scope` or `company`, taken from ADR-0043.R2), optional `escalation_role_id`, `due_days` (calendar days, default 2), `is_active`.
Source: ADR-0055.R4

R407. The members of a stage are `approval_stage_member` rows, each a user or a role; a stage has at least one. The column `position` is the stage's order of its members top to bottom (null sorts last): the notifications of ADR-0076.R6 go to at most 20 eligible members, the first 20 in that order.
Source: ADR-0055.R4, .N1

R408. Checks on save return `approval_pool_invalid`. They are run by `CreateApprovalPool` and `UpdateApprovalPool`, and also by `CreateApprovalProcedure` and `UpdateApprovalProcedure` (ADR-0043.R18), since a procedure's rank or activity changes what the stages must cover. The checks:
- every active pool has an active stage, and `min_rank` does not decrease along `sequence` among active stages;
- the first active stage's `min_rank` is at most the lowest active procedure rank, so every rank requires at least one stage;
- every active stage has a member;
- no selector row names an inactive pool, and `general` is active;
- the monotonic selection of R405.
Source: ADR-0055.R4

R409. Too few people: for each active procedure rank, the required stages are satisfiable when their places can be filled by distinct people: k places per stage, each filled by a different active user who is directly eligible for that stage in some scope (a member who holds an `Approve<Type>` of the pool's types; R416, condition 2). Outside the small-company mode of ADR-0054, the preparer may not approve, so the places must still be fillable with any one of those people left out. Saving returns the check result `approval_stage_unsatisfiable`, naming each rank that fails. `Submit` returns the same check result for its own plan and document, counting the document's writers out (R416, condition 5). For stages this check result replaces `policy_no_eligible_approver` (ADR-0043.R13).
Source: ADR-0055.R4

### Required stages and the seed

R410. Required stages of a decision:
- a decision without a rank requires no stage;
- otherwise it requires every active stage of the selected pool whose `min_rank` is at most the decision's rank, in `sequence` order; because `min_rank` does not decrease, these are always the first stages of the pool, and a higher rank adds stages at the end;
- a decision with a rank and no required stage is refused with `approval_plan_empty`; the checks of R408 make this unreachable in a consistent company, and the refusal keeps an inconsistent one from approving nothing (`INV-230`);
- a higher rank never requires fewer approvals, so the check of ADR-0043.R11 still describes the strictness of a rule set.
Source: ADR-0055.R5

R411. Approval procedures keep `code`, `name`, `rank` and `is_active`. The `approver_role` and `scope_binding` of ADR-0043.R2 are on the stages, not on `approval_procedure`.
Source: ADR-0055.R5

R412. The seed (ADR-0043.R15) gives each seeded pool the stages `standard` and `senior`, whose role members are the company's roles with these templates (ADR-0054.R11):
- `standard`: `min_rank` 10, k 1, members `accountant`, `chief_accountant` and `owner`, so that a company always has someone in every stage;
- `senior`: `min_rank` 20, k 1, members `chief_accountant` and `owner`;
- pool `mo`: its stage `standard` also seeds the role with template `production_planner` as a member; that template gets `can_approve` on `production_order`, with `edit` on `delegation` as every approving template has, so a planner can release orders at rank 10 (ADR-0054.R11). Interim, flagged for the author;
- pool `general`: its stage `standard` also has the role members `sales_manager`, `purchasing_manager` and `production_planner`; these templates have `edit` with `can_approve` on `change_proposal` (ADR-0054.R11), so they submit change proposals and approve them. The other pools keep the seed.
Source: ADR-0055.R5, .N1, .N2

R413. Rank 20 needs approvals by different people, one per stage: stages are cumulative. This is flagged. Members per pool (for example a sales manager for `sales`) are the company's choice.
Source: ADR-0055.R5

R414. Eligibility for a change proposal still needs the target permissions (R416; ADR-0043.R12): planning proposals are approved by the production planner, the purchasing manager or the owner (accountants and chief accountants read planning only); partner proposals (customer onboarding, supplier item mappings) by the sales manager, the purchasing manager or the owner; price-list proposals by the purchasing manager or the owner.
Source: ADR-0055.R5.N2

### The plan in the decision

R415. The decision records the plan. At every policy point that gives a rank, `policy_decision` (ADR-0029.R7) also stores `approval_pool_id`; `approval_plan`, the required stages with their ID, `sequence`, `code`, `min_rank`, k, `scope_binding`, `escalation_role_id` and `due_days`, as they were in force on `clock.today`; and `continues_policy_decision_id` for a resubmission that continues the round (R429). A later change to the pool affects only later decisions. Members are not frozen: eligibility is evaluated at each `Approve` (R416).
Source: ADR-0055.R6

### Who may approve the current stage

R416. The current stage is the first stage of the plan that has fewer than k counted approvals (R424). A person may approve or reject it when condition 1 holds, one of conditions 2 to 4 holds, and conditions 5 to 8 hold (condition 8 is R417):
1. A human actor (ADR-0017.R15).
2. Directly eligible: a member AND holding the permission, for a stage whose stage and pool are still active. A member is listed as a user member, or holds a member role through an assignment in force; with `scope_binding` `document_scope` that assignment's record scope must cover the document, and with `company` any assignment in the company counts. The permission is `Approve<Type>` (ADR-0054.R9) with the document inside their read scope (ADR-0054.R13).
3. Or a substitute of a directly eligible person, through a delegation of kind `approval` in force from that person (ADR-0054.R21).
4. Or an escalation holder, once the stage is overdue (R435): holding the stage's escalation role under the same scope binding, AND `Approve<Type>` with the document inside their read scope.
5. Not a writer: neither the person nor, for a substitute, the delegator is a human who wrote any version of the document: a human actor of a version, the `on_behalf_of` of any version, or the `on_behalf_of` of a version's origin agent run (ADR-0017.R16). The author and every later editor are ineligible, also through an agent acting for them.
6. Not counted yet: neither the person nor the delegator appears in a counted approval (R424): an approval of the current round at a stage of the current plan, at any stage of it. Approvals of earlier rounds, and approvals at stages the current plan no longer requires, are not read.
7. No segregation pair of ADR-0054.R19 is broken.
Source: ADR-0055.R7

R417. Condition 8, no stranded stage (`Approve` only). Consider the places still open in the plan: this stage's and every later required stage's, filled by distinct people who meet conditions 1, 2 or 3, and 5 to 7 for the stage they fill. If those places can be filled now, but no longer once this person counts at this stage, the person is needed for a later stage and nobody else can take that place: the approval is refused with `approval_would_strand_stage`. If the places cannot be filled either way, the approval is allowed and the fallback of R433 applies. `ListAllowedCommand` and the plan show the refusal before execution, like a check result.
Source: ADR-0055.R7

R418. Recovery from a stranded stage: another eligible person approves this stage; the author updates or cancels the document, which ends the round; or a person changes the stage's members with `UpdateApprovalPool`, which takes effect at once because members are not frozen.
Source: ADR-0055.R7

R419. Direct eligibility wins: a person directly eligible acts as themselves, even if a delegation would also make them eligible. Otherwise `Approve` and `Reject` may name `delegated_from_user_id`, an optional field of their payload (ADR-0009.R2), the delegator they act for; if they name none, the delegation in force with the lowest ID among those that make them eligible is used. Escalation is used only when no delegation applies.
Source: ADR-0055.R7

R420. Errors of R416 and R417: `human_only` (condition 1); `approver_not_eligible` (none of conditions 2 to 4, or a named delegator who does not make them eligible); `segregation_of_duties` (conditions 5 and 7); `approval_already_given` (condition 6); `approval_would_strand_stage` (condition 8). For a change proposal the approver also holds the target permissions and field classes (ADR-0043.R12).
Source: ADR-0055.R7

R421. Small companies: in the small-company mode of ADR-0054, condition 5 is lifted for the document's human writers and recorded as a segregation exception. The agent-run part of condition 5 is lifted only as ADR-0067.R16 states, when all hold: every agent run that wrote a version acting for the approver was started by an event or schedule; the approved version has no effective taint (never tainted, or cleared by `ClearTaint`, a self-clearance included); and the approver holds the `owner` or `chief_accountant` role template and is eligible for the stage. Each such approval writes a `segregation_exception` of kind `own_agent_draft_approval`, reviewed in the period review (`INV-803`). Never lifted: a run the approver started by their own act (`segregation_of_duties`), a tainted version, and condition 6. The approver of a change proposal that loosens a registered setting also meets conditions 5 and 6, and the small-company mode does not lift `approver_is_submitter` for it (ADR-0063.R3).
Source: ADR-0055.R7, .N1

R422. An approval given through bulk review (ADR-0042.R12) or from a work case (ADR-0066.R16) is one `Approve<Type>` per document, checked against conditions 1 to 8 and recorded as its own `approval` row; one approval never counts for more than one document, and a case adds no approval object. A company may let a purchase order need no approval of its own when the policy input `is_within_approved_request` is true; approvals otherwise stay per document (ADR-0066.R20).
Source: ADR-0055.R7.N2, .N3, .N4

### Rounds, counting and completion

R423. The round. A round starts with a `Submit` from draft. It ends with `Post` (or `Issue`) of the document, a rejection, an edit or a cancel. For types with no posting step (orders, production orders, change proposals, period unlock requests) it ends when the last required stage completes and the document becomes `approved`. For an e-invoiced document it ends with `Issue`, whose decision the completion `Post` carries (ADR-0043.R5). A resubmission without edit after `approval_context_changed` continues the round when the selected pool stays the same, and starts a new round when the pool changes (R429, R430). `Submit` from an actor carrying an origin agent run is refused with `origin_run_submit_not_allowed`: a person submits what an agent chain drafted (ADR-0029.R6).
Source: ADR-0055.R8, .N1

R424. Counted approvals of a stage are its `approved` rows within the current round, for stages of the current plan. A round has one version, because an edit ends it. When a continued round's new plan drops a stage (a lower rank, or a stage deactivated in between), the approvals at that stage stay recorded but no longer count.
Source: ADR-0055.R8

R425. Completion and order:
- when a stage reaches k, the next required stage becomes current on that day, and its work item is raised in the same transaction (R431);
- when the last required stage reaches k, the document becomes `approved` (ADR-0009.R4) and `<Type>Approved` is emitted; for a type with a posting step the round stays open until the document is posted, so a context change at `Post` can still continue it;
- approvals are recorded only for the current stage, so stage s is never approved before stages 1 to s−1 are complete (`INV-226`).
Source: ADR-0055.R8

### Rejection, edits and approval context

R426. Reject: `Reject<Type>` by a person who meets conditions 1 to 7 of R416 returns the document to `draft` with the reason (ADR-0009.R4). The round ends and the work item is resolved. A later `Submit`, with or without an edit, starts a new round, so earlier approvals no longer count.
Source: ADR-0055.R10

R427. Edit: `Update` writes a new version, voids every approval (ADR-0009.R9) and ends the round. Change orders bind approvals to the pending version in the same way (ADR-0028.R4).
Source: ADR-0055.R10

R428. Approval context (ADR-0028.R14): at `Post` of an approved document, or `Issue`, with a changed `policy_input_hash`, a new decision is made. The approvals stand when every stage its plan requires already has k counted approvals in the round, matched by stage ID; eligibility is not re-evaluated, and the `Post` then ends the round. Otherwise the command returns `approval_context_changed`.
Source: ADR-0055.R11

R429. After `approval_context_changed` the document may be resubmitted without edit (`approved → pending_approval`). When the new decision selects the same pool, it continues the round: a stage that appears in both plans keeps its approvals and only the missing stages are pending.
Source: ADR-0055.R11

R430. If the selector now chooses a different pool, the resubmission starts a new round: no earlier approval counts, and every stage of the new plan is pending.
Source: ADR-0055.R11

### Pending stages as work items

R431. Pending stages are work items (ADR-0042.R17). A document in `pending_approval` has exactly one open `approval_pending` item, for its current stage (`INV-204`). Its open key is the document ID. When a stage completes, its item is resolved and the next stage's item is raised in the same transaction.
Source: ADR-0055.R12

R432. Owner of the item: the owner kind `approval_stage` with `owner_approval_stage_id` (ADR-0042.R2, ADR-0042.R7). The item is visible to everyone eligible under R416: members in scope, substitutes in force, and escalation holders once overdue, through the visibility function of ADR-0055.R1.
Source: ADR-0055.R12

R433. Fallback to the owner: when nobody could approve the current stage, the item's owner becomes `company_owner` (the fallback of ADR-0042.R7; ADR-0054.R11), with the stage and a reason in `details`: `members_left` (no member holds the role or permission any more), `members_disabled`, `members_all_writers` or `members_all_counted`, or `stage_inactive` or `pool_inactive` (deactivated after the plan was recorded). The checks of R408 keep a selector from naming an inactive pool and an active pool from having no stage, so those states have no reason of their own. The fallback is checked when the stage becomes current and by the daily `RunApprovalEscalation` job (R436), which moves the item back to the stage once someone is eligible again. Nobody is eligible for a stage of a recorded plan whose stage or pool was deactivated afterwards. The owner fixes the members or reactivates the stage, or the author updates or cancels the document, and a new submission takes the stages then in force.
Source: ADR-0055.R12

R434. Due date, claims and agents of the item:
- the due date is the day the stage became current plus the stage's `due_days`, in calendar days, because `documents` is a layer-2 caller (ADR-0042.R5); the kind's due rule is `stage_due_days` (ADR-0042.R8);
- `Approve` needs no claim, and a claim never stops another eligible person from approving, since a stage may need several approvers;
- an agent type may declare `approval_pending` only to prepare the approval file (spec 07: summary, history, risks) as notes and evidence; agents never approve (ADR-0017.R15).
Source: ADR-0055.R12

### Escalation and delegation

R435. Escalation: when `clock.today` is after a stage's due date (R434), holders of its `escalation_role_id` become eligible for that stage too (R416, condition 4). The escalation never lowers k and never lifts conditions 5 to 8.
Source: ADR-0055.R13

R436. A daily system job, `RunApprovalEscalation`, sets the priority of overdue approval items to `high`, adds the escalation role to the evidence, and applies the fallback of R433. It changes no approval.
Source: ADR-0055.R13

R437. Escalation is in Phase 1 (ADR-0042.R8; flagged). The wording of spec 07 is proposed in an open question, because specs are the author's (ADR-0032.R7).
Source: ADR-0055.R13

R438. Delegation: a substitute acts under ADR-0054.R21. The approval row records `delegated_from_user_id`. Both the substitute and the delegator must pass conditions 5 to 7 of R416.
Source: ADR-0055.R14

### Documents that may not wait, and other policy points

R439. For a document that may not wait (`is_approval_hold_allowed: false`, including the invoice types for which ADR-0053.R8 derives it from `documents.issuance_without_delay`), a rank becomes `human_post` and the stored outcome is `human_only` (ADR-0043.R10). No pool or stage applies. The value is read for the document date when the decision is made, so a document's pool use follows the setting in force for it.
Source: ADR-0055.R15

R440. Change proposals and period unlock requests go to the `general` pool by default. The floors of ADR-0043.R9 hold: floor 7 (change proposals) and floor 8 (types with no posting step) give at least the lowest rank, which requires at least the first stage. Reversals keep no policy step (ADR-0043.R9, floor 9).
Source: ADR-0055.R16

R441. "The approving human" of ADR-0029.R3, on whose behalf an approved change proposal executes, is the approver whose approval completed the plan: the counted approval that brought the last required stage to k (R425). That human is the converter of the drafts the execution creates (ADR-0047.R9; ADR-0024.R22), so a writer of those drafts who cannot approve them (R416, condition 5); approvers at earlier stages are not. A purchasing manager who approves planning proposals (pool `general`) is therefore the converter of the purchase requests the execution drafts and cannot approve them; a company should not make the purchasing manager the only member of the stage `standard` of pool `pr`.
Source: ADR-0055.R16.N1, .N2

### Commands, catalog rows and lab check

R442. `CreateApprovalPool` and `UpdateApprovalPool` take stages, members and selector rows as one change (a list). They are `human_only`, `master_data_change`, change-tracked (ADR-0038.R3) and on no agent tool list, like the commands of ADR-0043.R18.
Source: ADR-0055.R17

R443. `RunApprovalEscalation` is a system job command (R433, R436). `ListApprovalPool` is the query of pools.
Source: ADR-0055.R17

R444. `GetApprovalProgress` (document) is a computed query, an exception to ADR-0004.R21 like `GetPrice`. It returns the plan, the current stage, the counted approvals, the due date and any fallback reason, and whether the caller is eligible, with the reason when not. Agents may call it to prepare approval files; it writes no denial records.
Source: ADR-0055.R17

R445. Catalog rows of the approval stages:
- errors: `approver_not_eligible` (permission); `approval_already_given`, `approval_would_strand_stage` and `approval_plan_empty` (precondition); `approval_pool_invalid` (validation); `segregation_of_duties` also covers condition 5 of R416;
- check result: `approval_stage_unsatisfiable` (on save and at `Submit`);
- work item kinds: `approval_pending` has owner rule `approval_stage` and due rule `stage_due_days`; no new kind;
- invariants, first at step 5: `INV-82` is stated by stages (every posted document whose decision requires a rank has, for every stage of the plan of the decision its `Post` used, at least k counted `approved` approvals on the posted version within the round that the `Post` ended; documents whose outcome is `human_only` are excluded); `INV-224`, `INV-225`, `INV-226` and `INV-230` as in section Invariants;
- edge cases: `EC-112`, `EC-113`, `EC-114`, `EC-115` and `EC-117` as in section Edge cases;
- glossary: approval pool, approval stage, approval step, approval round, approval plan; the approval procedure row changes.
Source: ADR-0055.R18

R446. The lab check `t12_access.py` of the validation lab holds pure functions on the shapes of the DS-15 DDL. It checks:
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
- the one-person and two-person outcomes of R447.
Source: ADR-0055.R19

R447. Outcomes with the seeded stages (R412) and the seeded procedures `standard` (rank 10) and `senior` (rank 20); ADR-0017.R15 and ADR-0017.R16 hold in all of them:
- one person, the owner, mode off: no ranked decision can be approved, and saving the stages returns `approval_stage_unsatisfiable` for ranks 10 and 20;
- one person, mode on: a rank-10 document the owner wrote is approved by the owner at `standard`, with a segregation exception, and reviewed in the period review (ADR-0054.R20). For a rank-20 document `Submit` returns `approval_stage_unsatisfiable`; the owner may still approve `standard` (condition 8 refuses only avoidable strandings), after which the item falls back to the owner as `company_owner` with reason `members_all_counted`, and the document can only be updated to a lower rank or canceled. How a one-person company meets such approvals is the open question of ADR-0017.R17; a company of one should not configure rules that require rank 20;
- owner and accountant, mode off: rank 10 is satisfiable by the person who did not write the document; rank 20 is unsatisfiable and `Submit` says so, because `senior` needs `chief_accountant` or `owner` and the owner either wrote the document or is already counted at `standard`;
- owner and accountant, mode on, rank 20: on a document the accountant wrote, the owner's approval of `standard` is refused with `approval_would_strand_stage`; the accountant approves `standard` (own document, recorded as an exception) and the owner approves `senior`. On a document the owner wrote, the accountant approves `standard` and the owner approves `senior` with an exception. Every own-document approval is in the owner's period review.
Source: ADR-0055.R20

### Modules and hooks of tunable functions

R448. `configuration` (layer 2) owns `parameter_set`, `parameter_set_version`, `parameter_set_value`, `artifact_transition`, `artifact_promotion_evidence`, `artifact_shadow_outcome`, `golden_case_label` and `artifact_monitor_snapshot` (DDL in `DS-28-34-configuration-artifacts.sql`), the contract function `get_parameters`, and the pure lifecycle and parameter checks (ADR-0022.R2).
Source: ADR-0059.R2

R449. `automation` (layer 5, ADR-0058.R1) owns `CreateArtifactEvidence`, `RunArtifactMonitor` and the queries of ADR-0059.R27 that read layer 3–4 data; the commands of `configuration` that need its checks call them through the hook `artifact_checks` of ADR-0058.R1.
Source: ADR-0059.R2

R450. The module that owns a tunable function or an L2 kind registers, with its declaration, the pure functions `backtest`, `compare` and `monitor` in its contract: `backtest` runs the function under one parameter set against another, or one rule version against another, over a window of its own resolved history, inputs as of decision time; `compare` sets an outcome against a person's final result; `monitor` reads decisions and overrides over a window. `automation` calls them; for the bank cascade they live in `cash`, as `GetAutoPostShadowEvaluation` does (ADR-0051.R18).
Source: ADR-0059.R2

R451. The auto-post hook: the evidence hook of `policy` (ADR-0043.R14) has a second function, `auto_post_eligibility`, which `cash` registers and `app` wires: for a `system` posting of a cascade draft it answers whether the draft's line meets ADR-0059.R6, and the policy floor gives `human_post` when it does not. So `policy` imports no layer-4 module.
Source: ADR-0059.R2

R452. The contract of `policy` has `mark_auto_post_evidence_outdated(company, function_code, by_id)`, which sets `shadow_evidence_outdated_by` on every enabled rule version whose stored evidence names that function (`EnablePolicyRule` stores the function code with the hash). `configuration` declares the hook `artifact_in_force_changed`, which `policy` registers and `app` wires (the pattern of ADR-0022.R2); `configuration` calls it inside the transaction of every pointer move, retirement and failed re-evaluation of a parameter set (`automation` reaches it through the contract of `configuration`), so no module imports `policy` sideways or up.
Source: ADR-0059.R2

R453. Lifecycle and evidence get no new table per kind: one transition log, one evidence table and one shadow table serve every kind. The generic `artifact_promotion_evidence` is used, not `agent_promotion_evidence`, whose columns (agent type, behavior hash, seat models) belong to agent types; the agent table stays as it is.
Source: ADR-0059.R2

## Invariants

Statements are those of `invariants.csv`; check point `day`, first at step 5.

| Invariant | Name | Check point | Statement | Protects |
| --- | --- | --- | --- | --- |
| `INV-224` | `approvers_distinct_per_round` | day | Within one approval round no human appears in two counted approvals, as approver or as delegator. | R416, R424 |
| `INV-225` | `approver_not_writer` | day | No counted approval's approver or delegator wrote a version of the document, acted as `on_behalf_of` of one, or was the human of its origin agent run, unless a `segregation_exception` records it under the small-company mode; the agent-run part has no exception. Flagged in the catalog: writers excluded. | R416, R421 |
| `INV-226` | `stage_approvals_in_sequence` | day | Every approval row's stage was current when it was decided: every earlier stage of the decision's plan had its required approvals in the round before it. | R425 |
| `INV-230` | `ranked_decision_has_plan` | day | Every policy decision with a required rank has a non-empty `approval_plan`. | R410, R415 |

The catalog statement of `INV-225` ("the agent-run part has no exception") predates ADR-0067.R16: an approval of kind `own_agent_draft_approval` that R421 allows is a recorded exception, checked by `INV-803`.

Named by rules of this chunk, with their rows in other chunks: `INV-82` (R445; its catalog source is ADR-0009.R11) in chunk 1, `INV-204` (R431) in chunk 4.

## Edge cases

Rows of `edge-cases.csv`, area `documents`, first executable at step 5.

| Edge case | Name | Case | Outcome | Protects |
| --- | --- | --- | --- | --- |
| `EC-112` | `approval_two_stages_k_of_n` | A purchase order above the senior rank is approved by one accountant at the first stage and by two of three managers at a stage with k = 2, then posts. | `must_succeed` | R410, R416, R425 |
| `EC-113` | `approval_edit_after_first_stage` | A document edited after its first stage approval loses that approval; the resubmission starts again at the first stage. | `must_succeed` | R427 |
| `EC-114` | `approval_rejected_at_second_stage` | A rejection at the second stage returns the document to draft with the reason; the next round starts at the first stage and earlier approvals do not count. | `must_succeed` | R426 |
| `EC-115` | `approval_by_substitute` | An approver on leave delegated approval authority; the substitute approves inside the window, recorded with `delegated_from`, and is refused the day after it ends. | `must_succeed`, then `must_reject:approver_not_eligible` | R438, R416 |
| `EC-117` | `approval_would_strand_stage` | In a two-person company in small-company mode, the owner tries to approve the first stage of a rank-20 document the accountant wrote and is refused; the accountant approves the first stage and the owner the second. | `must_reject:approval_would_strand_stage`, then `must_succeed` | R417, R447 |

## Settings

None: the rules of this chunk define no setting of `policy`.

Reads: `documents.issuance_without_delay` (ADR-0053.R8), named by R439; `settings.csv` holds no row with that key.

## Conflicts

CONFLICT ADR-0055.R7: ADR-0067.R16 (accepted 2026-11-21, later than ADR-0055 of 2026-11-15) governs; in the small-company mode the agent-run part of condition 5 is lifted for event- or schedule-started runs on an untainted version approved by an `owner` or `chief_accountant` eligible for the stage, recorded as `own_agent_draft_approval`; a run the approver started by their own act, a tainted version and condition 6 stay never lifted (R421).

CONFLICT ADR-0055.R7.N3: ADR-0055.R7.N4 decides the question the note left open for the author, so R422 states the purchase order case as decided under ADR-0066.R20 and keeps no open question.

## Trace

| Source | Where |
| --- | --- |
| ADR-0055.R3 | R401-R405 |
| ADR-0055.R4 | R406-R409 |
| ADR-0055.R4.N1 | R407 |
| ADR-0055.R5 | R410-R413 |
| ADR-0055.R5.N1 | R412 |
| ADR-0055.R5.N2 | R412, R414 |
| ADR-0055.R6 | R415 |
| ADR-0055.R7 | R416-R421 |
| ADR-0055.R7.N1 | R421 |
| ADR-0055.R7.N2 | R422 |
| ADR-0055.R7.N3 | R422 |
| ADR-0055.R7.N4 | R422 |
| ADR-0055.R8 | R423-R425 |
| ADR-0055.R8.N1 | R423 |
| ADR-0055.R10 | R426, R427 |
| ADR-0055.R11 | R428-R430 |
| ADR-0055.R12 | R431-R434 |
| ADR-0055.R13 | R435-R437 |
| ADR-0055.R14 | R438 |
| ADR-0055.R15 | R439 |
| ADR-0055.R16 | R440 |
| ADR-0055.R16.N1 | R441 |
| ADR-0055.R16.N2 | R441 |
| ADR-0055.R17 | R442-R444 |
| ADR-0055.R18 | R445 |
| ADR-0055.R19 | R446 |
| ADR-0055.R20 | R447 |
| ADR-0059.R2 | R448-R453 |
