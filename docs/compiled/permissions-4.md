Module: permissions    Chunk: 4 of 4    Source ADRs: ADR-0054, ADR-0067, ADR-0079
Build step(s): 0, 5    Generated from index: 30d5706    Compiled by: Claude Fable 5.2, 2026-11-21

# Compiled spec: `permissions`, chunk 4

## Purpose

`permissions` (layer 2, ADR-0022.R2) owns user accounts, roles, role assignments, delegations and the segregation of duties. This chunk states the small-company mode, approval delegation, the access screens and queries, the registration of the module's commands and queries, the authorization leaves of commands that other ADRs left open, the catalog rows of ADR-0054, its lab check and the field class `sensitive_personal`. As owner of the rest it also holds the invariants, edge cases, settings and work item kinds that no rule of chunks 1 to 3 places. Approval pools and stages belong to `policy`, approval rows to `documents`, work items to `work`; their units are traced `ref:` and not restated.

## Entities and tables

DDL: `docs/design/DS-15-access.sql`.

| Table | Meaning | Key | Parent | Owner |
| --- | --- | --- | --- | --- |
| `delegation` | An approval delegation from a delegator to a substitute user for a dated window; company data, change-tracked; `kind` holds the single value `approval` (R620) | `id`; unique (`company_id`, `id`) | `company`; `user_account` (delegator, substitute, creator) | `permissions` |
| `segregation_exception` | Immutable record of a segregation refusal that ran as a recorded exception in the small-company mode (R605); `kind` is `pair`, `own_document_approval`, `own_agent_draft_approval` or `own_run_taint_clearance`; `rule_code` is set exactly for kind `pair` | `id` | `company`; `user_account` | `permissions` |
| `segregation_review` | The owner's review of a posting period's exceptions, written by `ConfirmSegregationReview` (R606) | `id`; unique (`company_id`, `posting_period_id`) | `company`; `posting_period` | `permissions` |

Tables of `permissions` whose rows stand in other chunks and that the rules here name: `user_account`, `role`, `role_assignment`, `role_permission`, `role_permission_hold`, `company_segregation_rule`.

Reads: `posting_period`, `audit_record`, `approval`, `employee_profile`, `company`, `work_item`.

## Commands and queries

All commands of the module are `human_only`, change-tracked, on no agent tool list and not proposal-bound (R642). A cell the sources do not fill says "not stated".

| Name | Actor / authorization | Input | Effect | Events | Error codes |
| --- | --- | --- | --- | --- | --- |
| `EnableSmallCompanyMode`, `DisableSmallCompanyMode` | `segregation_rule` at `full`; `human_only`; `master_data_change` | not stated | sets the company setting `permissions.small_company_mode` (R601) | not stated | `small_company_mode_not_allowed` (R602) |
| `ConfirmSegregationReview` | `human_only`; effect class `other`; leaf `segregation_rule` (catalog: reviews); level not stated (the catalog level of the verb `Confirm` is `post`) | not stated | resolves `segregation_review_due` and writes a `segregation_review` row (R606) | not stated | not stated |
| `CreateDelegation` | the delegator, with `edit` on `delegation`; for an absent user a holder of the capability `delegate_for_others` (`full` on `delegation`) who also holds what is delegated; `human_only`; `master_data_change` | the columns of R620 | creates a `delegation` after the checks of R622 and R623 | not stated | `delegation_invalid` |
| `CancelDelegation` | leaf `delegation`; `human_only`; `master_data_change`; level not stated (the catalog level of the verb `Cancel` is `edit`) | the delegation | ends it early (R626) | not stated | not stated |
| `ListSegregationException` (query) | leaf `segregation_rule` (catalog: exceptions); level not stated (the catalog level of the verb `List` is `read`) | not stated | the owner review report (R606) | none | not stated |

The other registered commands and queries of the module are listed in R640 and R643; their rows stand in the chunks that state their rules. Commands and queries of other modules whose leaf and level this chunk states: R651 to R681.

Error codes bound to no single command: `small_company_mode_active` (every path of ADR-0054.R18 that would make a third posting or approving user, R602) and `segregation_of_duties` (R608, R610). The codes ADR-0054 adds to the catalog are in R691.

Authorization areas owned by `permissions` (catalog `authorization-areas.csv`, all functions below `administration`): `user_account` (users), `role` (roles and assignments), `delegation` (delegations; capability `delegate_for_others` at `full`) and `segregation_rule` (segregation rules, conflicts, exceptions, reviews and the small-company mode).

## Rules

### Small-company mode

R601. The small-company mode is the company setting `permissions.small_company_mode`, changed by `EnableSmallCompanyMode` and `DisableSmallCompanyMode` (`human_only`; level `full` on `segregation_rule`). The mode is flagged for the author (ADR-0017.R17).
Source: ADR-0054.R20

R602. The mode is allowed only while at most two active users hold any permission of effect class `posting` or any approval permission in the company; otherwise `small_company_mode_not_allowed`. While it is on, every path of ADR-0054.R18 that would make a third such user is refused with `small_company_mode_active`, and the upgrade turns the gain into a hold (ADR-0054.R9). `INV-223` checks the bound.
Source: ADR-0054.R20

R603. While the mode is on:
- the assignment check of ADR-0054.R18 is skipped;
- a refusal of ADR-0054.R19 becomes a recorded exception: the command runs and writes a `segregation_exception` row;
- the exclusion of a document's own writers (ADR-0055.R7) is lifted for humans, with an exception row.
Source: ADR-0054.R20

R604. The mode never relaxes: the hard floor that the human who triggered an agent never approves that agent's drafts (ADR-0017.R16; spec 03 rule 5; read as in R608); that one person counts in one stage only (ADR-0055.R7); `human_only`; and the bank-account rule of ADR-0029.R4, a policy floor (ADR-0043.R9 note): a bank account proposal is approved by a human who wrote no version of it.
Source: ADR-0054.R20, ADR-0054.R20.N1, ADR-0054.R20.N5

R605. A `segregation_exception` row is immutable and records its `kind`, the rule (`rule_code`, set only for a pair of segregation rules), the user, the command (`command_type`), the document, the related document and the audit record. The notes name the kinds `own_agent_draft_approval` (R608) and `own_run_taint_clearance` (R610). Every exception is recorded while the mode is on (`INV-223`) and is in the audit log (ADR-0038).
Source: ADR-0054.R20, ADR-0054.R20.N2, ADR-0054.R20.N3

R606. Compensating controls of the mode:
- every exception appears in `ListSegregationException`, the owner review report;
- the first exception of a posting period raises one `segregation_review_due` work item for `company_owner`, with the period as its open key, due at period end; later exceptions of the period add evidence to it. `permissions` raises it in the command's transaction and finds the period through the period resolver (ADR-0054.R2);
- `ConfirmSegregationReview` resolves it and writes a `segregation_review` row (period, count, who, when).
Source: ADR-0054.R20

R607. In a one-person company the owner reviews their own actions, which is weaker than four eyes. Whether the mode is acceptable, and whether the review must block the period lock, stays open for the author.
Source: ADR-0054.R20

R608. While `permissions.small_company_mode` is on, an `Approve<Type>` that ADR-0017.R16 would refuse runs as a recorded exception, a `segregation_exception` of kind `own_agent_draft_approval`, when all of these hold:
- every agent run that wrote a version acting for the approver was started by an event or schedule (the approver as the agent type's `workflow_owner_id`, ADR-0050.R14), not by the approver's own act;
- the version being approved has no effective taint: never tainted, or cleared by a `ClearTaint`, a self-clearance under ADR-0067.R17 included (ADR-0029.R8);
- the approver holds an assignment of the `owner` or `chief_accountant` role template and is eligible for the stage (ADR-0055.R7).
The approval and a clearance are separate commands and each writes its own `segregation_exception`. Each case is reviewed with the period's other exceptions through `segregation_review_due` and `ConfirmSegregationReview` (R606).
Source: ADR-0067.R16, ADR-0054.R20.N2, ADR-0054.R20.N4

R609. Spec 03 rule 5 ("the person who triggers an agent must not approve that agent's drafts") is read so that "the person who triggers" is the human whose own act started the run: a start command, a note or message they wrote, or a work item they handed to the agent. A run started by an event or schedule acts for the workflow owner, who is accountable for it (spec 03 rule 3) but did not trigger it. Under this reading the floor of R604 stands. Still refused: a run the approver started by their own act (`segregation_of_duties`), a tainted version, and every such approval outside the small-company mode. The reading is decided by the author's delegation to the chief architect (2026-11-17); the spec 03 wording stays the author's to align (open question). The operating preset `quickflows` enables the mode through `EnableSmallCompanyMode` while its bound holds (ADR-0067.R6, ADR-0067.R16, ADR-0067.R17).
Source: ADR-0067.R16, ADR-0054.R20.N2

R610. While the mode is on, the human for whom a tainted run acted may clear that run's versions, one `ClearTaint` per version with a reason, never in bulk; each clearance writes a `segregation_exception` of kind `own_run_taint_clearance` for `ConfirmSegregationReview` at period close. A self-cleared version never counts as cleared for the auto-post gateway's tainted-draft eligibility or for promotion evidence (ADR-0067.R17).
Source: ADR-0054.R20.N3

### Delegation

R620. `delegation` is company data and change-tracked. Columns: `delegator_user_id`, `substitute_user_id`, `kind` with the single value `approval`, `start_date`, `end_date` (inclusive, at most 366 days), `reason`, `state` (`active`, `canceled`), `created_by_user_id`. Only approval delegation exists; the kind `role_assignments` is dropped until a company needs it and no table `delegation_role_assignment` exists. The glossary row in spec 00 is left for the next spec pass.
Source: ADR-0054.R21, ADR-0054.R21.N1

R621. A delegation never goes to an agent: the substitute is a user account, which no agent has, and every command that uses a delegation must come from a human actor.
Source: ADR-0054.R21

R622. `CreateDelegation` refuses with `delegation_invalid`: a delegation to oneself; a substitute who is not active or holds no assignment in force in the company; a delegation of delegated authority; and a substitute without TOTP enabled when a role whose approvals are lent has `is_totp_required` (ADR-0054.R4 then requires it at sign-in).
Source: ADR-0054.R21, ADR-0054.R21.N1

R623. `CreateDelegation` runs the segregation check of ADR-0054.R18 on the substitute's own rights plus what is lent.
Source: ADR-0054.R21

R624. A delegation is in force when `state` is `active`, `start_date` ≤ `clock.today` ≤ `end_date`, and the delegator is active. It lends only what the delegator holds on that day, so a delegator who loses a right loses it for the substitute too. The delegator keeps their own rights during the window.
Source: ADR-0054.R21

R625. Under a delegation in force the substitute is eligible wherever the delegator is directly eligible in an approval stage (ADR-0055.R7). The delegator's `Approve` and `Reject` permissions and the read of the subject are lent with the delegator's scope.
Source: ADR-0054.R21

R626. `CreateDelegation` is run by the delegator, which every approving template allows (ADR-0054.R11); for an absent user it is run by a holder of `delegate_for_others` who also holds what is delegated (no escalation). `CancelDelegation` ends a delegation early. Both are `human_only`.
Source: ADR-0054.R21

R627. A command executed under a delegation records `delegated_from_user_id` in its audit record (ADR-0038.R2) and, for approvals, in the approval row (ADR-0055.R9). `INV-222` checks it.
Source: ADR-0054.R21

### Screens and queries

R630. The role editor is a hand-built screen (DS-30). Rows are the area tree, columns the levels and "approve". It shows inherited values, and the plan of `UpdateRole` gives the permissions gained and lost before execution.
Source: ADR-0054.R22

R631. The assignment form holds: principal, role, record scope, owner scopes (defaulting to the role's suggestions), field classes, dates.
Source: ADR-0054.R22

R632. `ListAllowedCommand` keeps its interface (ADR-0040.R8). Its checks read the expanded permissions, the owner scope (outside it the subject is `record_not_found`), delegations, the segregation checks of ADR-0054.R19, and for `Approve` the stage eligibility of ADR-0055.
Source: ADR-0054.R22

R633. `GetSessionContext` also returns owner scopes and the delegations in force (ADR-0040.R12).
Source: ADR-0054.R22

### Registration

R640. The commands of `permissions` are `CreateUserAccount`, `ConfirmUserInvitation`, `CancelUserInvitation`, `UpdateUserAccount`, `DisableUserAccount`, `EnableUserAccount`, `ClearUserAccountLockout`, `CreateCredentialReset`, `CreateRole`, `UpdateRole`, `ConfirmRolePermissionHold`, `IgnoreRolePermissionHold`, `CreateRoleAssignment`, `UpdateRoleAssignment`, `CreateDelegation`, `CancelDelegation`, `EnableSegregationRule`, `DisableSegregationRule`, `EnableSmallCompanyMode`, `DisableSmallCompanyMode`, `ConfirmSegregationReview`.
Source: ADR-0054.R23

R641. The `master_data` commands of ADR-0054 are those of ADR-0054.R6, `UpdateEmployeeOrganization` included.
Source: ADR-0054.R23

R642. All commands of R640 and R641 are `human_only`, effect class `master_data_change` (`other` for `ClearUserAccountLockout`, `CreateCredentialReset`, `CancelUserInvitation` and `ConfirmSegregationReview`), change-tracked, and on no agent tool list. They are not proposal-bound: an agent cannot propose access changes.
Source: ADR-0054.R23

R643. The queries of `permissions` are `ListUserAccount`, `GetUserAccount`, `ListUserInvitation`, `ListPendingUserInvitation` (the caller's own, across companies), `ListRolePermissionHold`, `ListRole`, `GetRole`, `ListRolePermission`, `ListRoleAssignment`, `ListDelegation`, `ListAuthorizationArea`, `ListSegregationRule`, `ListSegregationConflict`, `ListSegregationException`.
Source: ADR-0054.R23

R644. Verbs: Enable and Disable extend to user accounts, segregation rules and the small-company mode; Cancel to delegations and invitations; Clear to a lockout; Confirm to an invitation (the invited person confirms they are the one meant) and to a held permission (a person accepts what the upgrade produced); Ignore to a held permission (glossary notes). The module needs no new verb; Verify comes from ADR-0052.
Source: ADR-0054.R23

### Leaves and levels of other modules' commands

R650. The DS-15 items of ADR-0004.R16, ADR-0013.R14, ADR-0013.R16 and ADR-0014 (journal RLS) are answered by ADR-0017.R18 and ADR-0017.R19. Those of ADR-0008 rules 2, 5, 8 and 12 are answered by ADR-0017, completed by ADR-0054 rules 8 to 16 (levels, owner scope, field filtering unchanged). Those of ADR-0009 (who may submit, approve and post; segregation) are answered by levels (ADR-0054.R8), the approval flag (ADR-0054.R9), segregation (ADR-0054 rules 17 to 20) and ADR-0055.
Source: ADR-0054.R24

R651. Manual exchange rates (ADR-0011): the leaf `exchange_rate` under Finance; `CreateExchangeRate` needs `edit` there. Templates `chief_accountant` and `accountant` have it.
Source: ADR-0054.R24

R652. Periods (ADR-0012): `post_in_soft_locked_period` is `full` on `posting_period`, held by templates `owner` and `chief_accountant`. Restrict and Open need `post`, Lock and Unlock `full`, on the same leaf; close jobs are `Run` on `costing_run` and `close_checklist`. The calendar owner (`fiscal_calendar_owner`) stays a company column (ADR-0012.R3).
Source: ADR-0054.R24

R653. Packages and regime options (ADR-0016): loading packages stays with the `operator` installation role. Regime options are the leaf `regime_option` under Finance, at level `full`.
Source: ADR-0054.R24

R654. Field classes are `cost`, `margin` and `sensitive_personal` (R710). Labels with row conditions (ADR-0019) are data labels for LLM routing (spec 17; DS-32), not permissions.
Source: ADR-0054.R24, ADR-0079.R11

R655. The shop-floor role template of ADR-0034.R18 is `shop_floor_lead`.
Source: ADR-0054.R24

R656. `AcceptMigrationDifference` (ADR-0044.R11) is a permission on the leaf `opening_balance_entry` with the declared minimum level `full` (ADR-0054.R8), so Finance `full` holds it: templates `owner` and `chief_accountant`, not `accountant`. It is not a test on holding the `chief_accountant` role.
Source: ADR-0054.R24

R657. On `report_finance` (ADR-0049.R17): `GetStatutoryReport`, `ListBookRow`, `ListReportLineContribution`, `ListReportDefinition`, `GetReportDefinition`, `ListStatutoryReportFiling`, `GetStatutoryReportFiling`, `ListReportComparativeValue` at `read`; `RenderReport` at `read` (verb Render); `CreateReportDefinition`, `UpdateReportDefinition`, `CreateReportComparativeValue`, `UpdateReportComparativeValue`, `DeleteReportComparativeValue` at `edit`; `FileStatutoryReport` at `post`.
Source: ADR-0054.R24

R658. On `report_tax`: `RenderTaxReturn` at `read`; `FileTaxReturn` at `post` (ADR-0041.R18); `RunTaxReturnOffset` (verb `Run`, effect class `posting`; the period-end tax offset job of ADR-0049.R23).
Source: ADR-0054.R24

R659. On `general_access`: `RenderPrint`, `GetPrintData`, `GetRenderJob` and `ListRenderJob` at `read`, so everyone may print, and see the print data of, what they may read. `RenderPrint` and `GetPrintData` check the subject's own `Get<Type>` and read scope (record and owner scope), and refuse otherwise as `Get<Type>` would (ADR-0049.R20, ADR-0049.R25).
Source: ADR-0054.R24

R660. On `print_template` stand only templates and print data contracts, which hold no document data: `CreatePrintTemplate`, `UpdatePrintTemplate` at `edit`, `GetPrintDataContract` at `read`, and the render worker's `RecordRenderOutcome` (declared `full`, system only). So `print_template` never lets an IT administrator or an auditor read a document's content. On `print_profile`: `CreatePrintProfile`, `UpdatePrintProfile` at `edit`, held only by `owner`.
Source: ADR-0054.R24

R661. Reporting in the templates: the reporting queries go to `owner`, `chief_accountant` and `accountant` (ADR-0049.R17), and also to `auditor`, read-only; `FileStatutoryReport` and `FileTaxReturn` go to `owner` and `chief_accountant`.
Source: ADR-0054.R24

R662. `on_behalf_of` and segregation for scheduled and e-mail runs: ADR-0017.R12 and ADR-0017.R16 stand. The owner of the schedule or intake is the human acted for, so that person never approves the run's drafts, except as R608 allows (ADR-0067.R16).
Source: ADR-0054.R24, ADR-0067.R16

R663. Teams of one or two people are served by the small-company mode (R601 to R610, flagged) and the walk-throughs of ADR-0055.R20.
Source: ADR-0054.R24

R664. Still open: integrations and `human_only` (ADR-0008.R2), TOTP for every user, and the small-company questions (ADR-0017.R17).
Source: ADR-0054.R24

R670. Agent commands and capabilities (ADR-0050 rules 14 to 20):
- `start_agent:<agent_type>`: capability on the leaf `agent_<agent_type>` at `edit`;
- `StartAgentRun`: no leaf; its check is `start_agent:<agent_type>` of the payload's agent type, held by the human actor or, for `system` from a wake-up or schedule, by the human acted for; effect class `other`; on no tool list;
- `CancelAgentRun`: no leaf; its check is `start_agent:<agent_type>` of the run's agent type, or `cancel_agent_runs`; `other`; on no tool list;
- `cancel_agent_runs`: capability on `agent` at `full`; it is the only other way to cancel a run (the company's owner holds no separate right);
- `UpdateAgentTypeSetting`: `agent` at `full` (declared); `master_data_change`, `is_proposal_bound`, on no tool list; the resulting `workflow_owner_id` must hold `start_agent:<agent_type>`, else `workflow_owner_not_permitted`;
- `CreateAgentPromotionEvidence`: `agent` at `edit`; `other`; a person's command; on no tool list;
- `GetAgentTypeSetting`, `GetAgentShadowEvaluation`, `ListAgentRun`, `GetAgentRun`: `agent` at `read`; bodies need `read_agent_run_bodies`;
- `CompleteAgentRun`, `RunAgentQualityCheck`: leaf `agent`, `is_internal_only`.
Source: ADR-0054.R24.N1

R671. Policy, general and event commands (ADR-0013 rules 8 and 16; ADR-0029 rules 8 and 13; ADR-0038.R13; ADR-0043.R18; ADR-0055.R17):
- `ClearTaint`: `policy` at `full`; `human_only`;
- `ConfirmAutoPost`: `policy` at `post`; only the rule's owner (ADR-0043.R14);
- `ListPolicyDecision`: `policy` at `read`;
- `RunApprovalEscalation`: leaf `policy`, `is_internal_only`;
- `GetApprovalProgress`: `general_access` at `read`; it checks the document's own `Get<Type>` and read scope, like `GetPrintData`;
- `CreateAttachment`: `general_access` at `edit`; linking the file to a record needs that record's own `Update`;
- `CreateListExport`: `general_access` at `edit`; its consumer pages the exported query as the requester, so that query's permission and scope apply; on no tool list;
- `RetryEventDelivery`, `SkipEventDelivery`: `event_delivery` at `post`; `human_only`; deliveries with a company; installation deliveries stay the operator's;
- `ReplayEvents`: `event_delivery` at `full`; `human_only`.
Source: ADR-0054.R24.N1

R672. `EvaluateBarcode` is a member of `general_access` at `read`: it checks each candidate's own read permission and answers `barcode_unknown` when none is readable (ADR-0061.R12). `RunRetiredSsccCleanup`, leaf `product`, is registered `is_internal_only` beside `RunApprovalEscalation`: no level grants it and no role holds it (ADR-0061.R7).
Source: ADR-0054.R24.N2

R673. The analysis queries over facts, and private saved analyses (`CreateSavedAnalysis`, `UpdateSavedAnalysis` at `edit`; `ListSavedAnalysis`, `GetSavedAnalysis` at `read`), sit on `general_access` and check each fact view's own permission (ADR-0060).
Source: ADR-0054.R24.N3

R674. Analysis leaves: `analysis_question` below `reports` (questions, feedback and the run's answer at `edit`, the asker's own questions at `read`); `saved_analysis` below `reports` (examples at `read` and `edit`, the capability `share_saved_analysis` for company-wide analyses and KPIs at `edit`, releases at `post`); `analysis_debug` below `administration` (capability `read_analysis_debug` at `full`, `none` in every template except `owner`); `agent_analysis` below `agent`. Interim rows give `analysis_question` and `agent_analysis` at `edit`, and `saved_analysis` at `post` (chief accountant) or `edit`, to the chief accountant, accountant, sales manager, purchasing manager and production planner (ADR-0060.R36).
Source: ADR-0054.R24.N3

### Catalog rows

R690. ADR-0054 adds the catalogs `authorization-areas.csv`, `authorization-verb-levels.csv`, `role-templates.csv`, `role-template-levels.csv` and `segregation-rules.csv`, listed in the catalogs README with owner DS-15.
Source: ADR-0054.R25

R691. Error codes by class: `user_account_locked` (unauthenticated); `grant_exceeds_own_rights`, `segregation_conflict` and `organization_self_change` (permission); `role_assignment_invalid`, `delegation_invalid`, `department_cycle`, `employee_manager_cycle`, `employee_organization_command_required` (validation); `last_owner_required`, `user_shared_across_companies`, `small_company_mode_not_allowed`, `small_company_mode_active` (precondition). `segregation_of_duties` also covers ADR-0054.R19. The check result is `segregation_conflict_found`.
Source: ADR-0054.R25

R692. Work item kinds of `permissions`: `segregation_review_due` (subject `posting_period`, owner `company_owner`, due `period_end`, resolved by `ConfirmSegregationReview`) and `role_permission_held` (subject `company`, owner `company_owner`, due `days:7`, resolved by the system when no hold is `held`).
Source: ADR-0054.R25

R693. Company settings: `permissions.segregation_assignment_mode` (default `warn`) and `permissions.small_company_mode` (default false). Installation setting: `invitation_expiry_days` (default 30).
Source: ADR-0054.R25

R694. The invariants of ADR-0054 are first checked at step 5 and take the block `INV-220` to `INV-239`: `INV-220`, `INV-221`, `INV-222`, `INV-223`, `INV-227`, `INV-228`, `INV-229` and `INV-231`. `INV-216` belongs to ADR-0050 (its rule 55 note); `INV-217` to `INV-219` stay unused, reserved by no design item.
Source: ADR-0054.R25, ADR-0054.R25.N1

R695. The edge cases of ADR-0054 take the block `EC-110` to `EC-129`: `EC-110`, `EC-111`, `EC-116` and `EC-118` are its own, `EC-110` to `EC-118` are taken together with those of ADR-0055, and `EC-119` to `EC-129` are the barcode edge cases of ADR-0061 (its rule 27), which fills the block. The reporting block of ADR-0049 is `EC-92` to `EC-98`; `EC-99` and `EC-100` are CRM rows of ADR-0052; `EC-101` to `EC-109` are not ADR-0054's: the note left them unused, and the catalog now holds `EC-101` to `EC-109` as edge cases of ADR-0056 (its rules 9, 11 and 14).
Source: ADR-0054.R25, ADR-0054.R25.N2, ADR-0054.R25.N3

### Lab check

R700. The lab check `t12_access.py` of the validation lab runs on DS-15-access.sql loaded with DS-20 and DS-06, and its result is recorded as the next lab finding of the validation lab README. It checks:
- the field counts of every catalog file it reads, and every glossary verb against the verb catalog;
- level expansion: inheritance and overrides, verbs against effect classes, declared minimum levels, the approval flag, capabilities, the templates' delegation and agent run body rights, and the same set for shuffled inputs;
- owner scope filtering `own`, `team`, `department` (manager subtree and reporting chain), `branch` and `company` on real rows, and the database's refusal of inconsistent scope pairs and of agent type assignments;
- pending invitations (people colliding on one login; a former user whose ID the company still knows; confirmation only by the invited user; expiry), linked and shared users, the operator path, the no-escalation rule and its lockout exemption, and a reset that keeps TOTP, revokes sessions and is voided when the user becomes shared, on real rows;
- permission holds on upgrade: the stored set is the expansion minus the holds, and granting re-runs the checks;
- the organization guard: `UpdatePartner` refused on the guarded columns, `full` required, and no self-change by effect on real rows (a manager set to the caller, employees moved into the caller's department, a department reparented under the caller's), with the company-scope exemption;
- a leaf for every CRM command and query of ADR-0052 and every reporting and printing command and query of ADR-0049, the print profile kept to `owner`, and no report leaf for the cashier;
- a segregation pair blocking one document, warn and block on every rights path, the delegation checks, and the small-company exception and bound;
- the delegation window;
- `company_id` on every company table of the file;
- the approval engine of ADR-0055 (its rule 19);
- that `is_internal_only` commands are in no template's expansion, the `start_agent` seed (confirmed by ADR-0054.R11.N9), and the leaves of R670 and R671.
Source: ADR-0054.R26, ADR-0054.R26.N1

### Field class `sensitive_personal`

R710. `sensitive_personal` is a field class beside `cost` and `margin` (ADR-0017.R10). A column with that label is returned only to an assignment that holds the class. Only the `owner` template suggests it by default (`role-templates.csv`), so the owner can grant it. No Phase 1 column carries it; the class exists so that a package or a custom field can use it without a schema change.
Source: ADR-0079.R11

## Invariants

Statements are those of `invariants.csv`. Each row stands once in the module; this chunk holds the rows whose catalog source is a rule of this chunk or a rule of no chunk of the module.

| Invariant | Statement | Check point | Protects |
| --- | --- | --- | --- |
| `INV-222` | Every command audited with `delegated_from_user_id` lies inside a delegation in force on that day from that user to the human actor, of a kind that covers the command. | day | R624, R627 |
| `INV-223` | While `permissions.small_company_mode` is on, at most two active users hold a posting or approval permission, and every `segregation_exception` was recorded while the mode was on. Flagged: small-company mode (ADR-0054.R20). | day | R602, R605 |
| `INV-228` | Every recorded change of `employee_profile.department_id`, `manager_partner_id` or `user_account_id` belongs to an `UpdateEmployeeOrganization` audit record. | day | ADR-0054.R6; R641 |
| `INV-805` | Every `taint_clearance` whose actor is the human the tainting run acted for was recorded while `permissions.small_company_mode` was on, by a single `ClearTaint` command with a reason, and has a `segregation_exception` of kind `own_run_taint_clearance`; no `policy_decision` has `auto_post_decision` `auto_post` in mode `live` for a draft whose only clearances are such self-clearances; and no `agent_promotion_evidence` figure counts such a version. | day | R610; ADR-0067.R17 |

Named by the rules of this chunk, with their rows in the chunks that state their source rules: `INV-220` (ADR-0054.R9), `INV-221` (ADR-0054.R13), `INV-227` (ADR-0054.R3, ADR-0054.R4), `INV-229` (ADR-0054.R18), `INV-231` (ADR-0054.R3, ADR-0054.R12). Invariants that only the `ref:` units of this chunk name are stated by their own modules: INV-82, INV-84, INV-224, INV-225, INV-226 and INV-230 (ADR-0055.R18), INV-414 (ADR-0060.R26), INV-760 to INV-764 (ADR-0065.R22), INV-800 to INV-804 (ADR-0067.R20).

## Edge cases

| Edge case | Name | Case | Outcome |
| --- | --- | --- | --- |
| `EC-115` | `approval_by_substitute` | An approver on leave delegated approval authority; the substitute approves inside the window, recorded with `delegated_from`, and is refused the day after it ends. | `must_succeed` inside the window; `must_reject:approver_not_eligible` after it (R624, R625, R627; ADR-0055.R14) |
| `EC-117` | `approval_would_strand_stage` | In a two-person company in small-company mode, the owner tries to approve the first stage of a rank-20 document the accountant wrote and is refused; the accountant approves the first stage and the owner the second. | `must_reject:approval_would_strand_stage` for the owner's first attempt; `must_succeed` for the rest (R603, R604; ADR-0055.R7, ADR-0055.R20) |
| `EC-256` | `self_clear_taint_small_company` | In a one-person company with the small-company mode on, the owner clears the purchase invoice agent's tainted draft with a reason; an `own_run_taint_clearance` exception is recorded, the gateway still treats the draft as tainted (`require_human`), and a bulk clearance of such drafts is refused; with the mode off, the single clearance is refused. | `must_succeed` for the single clearance in the mode; `must_reject:segregation_of_duties` for the bulk clearance and outside the mode (R610; ADR-0067.R17, ADR-0029.R8) |

Named by R695, with their rows in the chunks that state their source rules: `EC-110` (ADR-0054.R13, ADR-0054.R14), `EC-111` (ADR-0054.R19), `EC-116` and `EC-118` (ADR-0054.R3). Edge cases that only the `ref:` units of this chunk name are stated by their own modules: EC-112, EC-113 and EC-114 (ADR-0055.R18), EC-220 to EC-228 (ADR-0065.R22), EC-250 to EC-255 (ADR-0067.R20).

## Settings

None: `settings.csv` holds no key of this chunk. R693 names the company setting `permissions.small_company_mode` (on or off, default false; used by R601, R602, R608 and R610), which is absent from `settings.csv`; `setting-presets.csv` sets it per operating preset (ADR-0067.R6). The other settings R693 names, absent from `settings.csv` too, are stated in chunk 3 (`permissions.segregation_assignment_mode`) and chunk 2 (`invitation_expiry_days`).

Reads: `analysis.narrative_mode`, `cash.auto_post.accept_llm_originated_rules`, `messaging.message_retention_days`, `ui.post_review`, `ui.post_review_max_amount`, `work_case.<kind>.mode`, `work_case.production_disruption.mode`.

## UI annotations

The sources hold no ADR-0077 floorplan, title, facet, field annotation or tile for the module; the role editor is a hand-built screen (R630). Work item kind `segregation_review_due` (catalog `work-item-kinds.csv`; module `permissions`, subject table `posting_period`, owner rule `company_owner`, due rule `period_end`, resolution `command` by `ConfirmSegregationReview`, not agent-resolvable): the first segregation exception of a posting period in the small-company mode (R606, R692). The module's other kinds have their rows in chunk 1 (`owner_suspended`, ADR-0017.R12) and chunk 2 (`role_permission_held`, ADR-0054.R9).

## Conflicts

CONFLICT ADR-0054.R20: the check of ADR-0017 rule 16 is relaxed in the mode for event- or schedule-started runs and the exception row carries a kind, as ADR-0067.R16 and ADR-0054.R20.N2 decide; stated in R605, R608 and R609.
CONFLICT ADR-0054.R20.N1: the mark "interim, flagged" on the bank-account rule is dropped because ADR-0054.R20.N5 (2026-11-19) confirms it as a policy floor; stated in R604.
CONFLICT ADR-0054.R20.N2: its clause "never tainted, or cleared by another person" reads as ADR-0054.R20.N4 and ADR-0067.R16 give it, a self-clearance included; stated in R608.
CONFLICT ADR-0054.R21.N1: the kind `role_assignments` and the table `delegation_role_assignment` of ADR-0054.R21 are dropped; R620 and R622 state approval delegation only, as the DDL does.
CONFLICT ADR-0054.R24: its statement that field classes stay `cost` and `margin` is extended by the later ADR-0079.R11 with `sensitive_personal`; stated in R654 and R710. Its backlog bullet that the owner of a schedule or intake never approves the run's drafts is relaxed in the small-company mode by ADR-0067.R16 as a recorded exception of R608; R662 states the bullet with that exception.
CONFLICT ADR-0054.R24.N1: the capability `cancel_agent_runs` replaces the words "or the company's owner" in the check of `CancelAgentRun` (ADR-0050); R670 states the capability only.
CONFLICT ADR-0054.R26.N1: the mark "interim" on the `start_agent` seed that the lab checks is dropped, because ADR-0054.R11.N9 (2026-11-19) confirms the rest of the interim seed; R700 states it without the mark.
CONFLICT ADR-0054.R25.N1: the gap INV-216 to INV-219 of ADR-0054.R25 now starts at INV-217, since INV-216 belongs to ADR-0050; stated in R694.
CONFLICT ADR-0054.R25.N2: the edge-case numbering of ADR-0054.R25 is corrected: the rule's "`EC-97` to `EC-109` follow the reporting block" gives way to the reporting block `EC-92` to `EC-98`, the CRM rows `EC-99` and `EC-100`, and `EC-101` to `EC-109` outside ADR-0054; R695 states the corrected ranges.

## Proposed (not law)

None

## Trace

| Source | Where |
| --- | --- |
| ADR-0054.R20 | R601-R607 |
| ADR-0054.R20.N1 | R604 |
| ADR-0054.R20.N2 | R605, R608, R609 |
| ADR-0054.R20.N3 | R605, R610 |
| ADR-0054.R20.N4 | R608 |
| ADR-0054.R20.N5 | R604 |
| ADR-0054.R21 | R620-R627 |
| ADR-0054.R21.N1 | R620, R622 |
| ADR-0054.R22 | R630-R633 |
| ADR-0054.R23 | R640-R644 |
| ADR-0054.R24 | R650-R664 |
| ADR-0054.R24.N1 | R670, R671 |
| ADR-0054.R24.N2 | R672 |
| ADR-0054.R24.N3 | R673, R674 |
| ADR-0054.R25 | R690-R695 |
| ADR-0054.R25.N1 | R694 |
| ADR-0054.R25.N2 | R695 |
| ADR-0054.R25.N3 | R695 |
| ADR-0054.R26 | R700 |
| ADR-0054.R26.N1 | R700 |
| ADR-0055.R1 | ref: ADR-0055.R1 |
| ADR-0055.R5.N1 | ref: ADR-0055.R5.N1 |
| ADR-0055.R18 | ref: ADR-0055.R18 |
| ADR-0057.R33 | ref: ADR-0057.R33 |
| ADR-0057.W | ref: ADR-0057.W |
| ADR-0058.W | ref: ADR-0058.W |
| ADR-0060.R23 | ref: ADR-0060.R23 |
| ADR-0060.R23.N1 | ref: ADR-0060.R23.N1 |
| ADR-0060.R26 | ref: ADR-0060.R26 |
| ADR-0065.R22 | ref: ADR-0065.R22 |
| ADR-0066.R2 | ref: ADR-0066.R2 |
| ADR-0066.R3 | ref: ADR-0066.R3 |
| ADR-0067.R16 | R608, R609, R662 |
| ADR-0067.R17 | ref: ADR-0067.R17 |
| ADR-0067.R20 | ref: ADR-0067.R20 |
| ADR-0070.R8 | ref: ADR-0070.R8 |
| ADR-0070.R15 | ref: ADR-0070.R15 |
| ADR-0070.R15.N1 | ref: ADR-0070.R15.N1 |
| ADR-0071.R18 | ref: ADR-0071.R18 |
| ADR-0074.R1 | ref: ADR-0074.R1 |
| ADR-0074.R3 | ref: ADR-0074.R3 |
| ADR-0076.R10 | ref: ADR-0076.R10 |
| ADR-0079.R11 | R654, R710 |
