# ADR-0054: Users, roles and authorizations

Status: accepted (2026-11-15) under ADR-0005, reviewed by Claude Fable 5.2 (builder Claude Opus 5.5). Design item: DS-15 (full part; the envelope part is ADR-0017). Related decisions: D2, D5, D12, D14. Principles 3, 4, 7, 10. ADR-0004, ADR-0005, ADR-0008, ADR-0009, ADR-0012, ADR-0016, ADR-0017, ADR-0019, ADR-0022, ADR-0026, ADR-0027, ADR-0028, ADR-0029, ADR-0038, ADR-0040, ADR-0042, ADR-0043, ADR-0044, ADR-0045, ADR-0047, ADR-0048, ADR-0049, ADR-0050, ADR-0052, ADR-0055; spec 03, 07, 14, 17.

## Decision

ADR-0017 fixed the envelope: permissions are the names of registered commands, queries and capabilities; roles bundle them per company; assignments add record scope and field classes; an agent's rights are an intersection with its human's; row-level security pins each transaction to one company. This ADR completes the model for step 5, in the style of SAP Business One.

**Authorization levels.** A core catalog arranges every command, query and capability in a tree of authorization areas: Sales, Purchasing, Inventory, Production, Planning, Finance, Banking, Master data, CRM, Administration and Reports. Leaves are document types, master data nouns, functions and report groups. A role stores one level per node: `none`, `read`, `edit`, `post` or `full`, and separately whether it may approve. The level expands into permissions by a fixed rule over each command's verb and effect class. The dispatcher checks only the expanded permissions, so ADR-0017's single permission path stays.

**Templates.** The core ships thirteen job-role templates. A company copies them at setup and changes them freely.

**Data ownership.** Each user assignment carries an owner scope for reading and one for editing: `own`, `team`, `department`, `branch` or `company`. Every document has an owner employee (the salesperson, the buyer, or the creator) and a creating user. Owner scope narrows the record scope of ADR-0017 rule 9, and everything that shows a document's data follows it. Row-level security still guards only the company.

**Organization for access.** Departments (a tree with managers) and optional teams are company data. Employees gain a department and a manager. Because these change who sees what, they change only through dedicated `human_only` commands at level `full`.

**Segregation of duties.** A core catalog lists conflicting permission pairs. They are checked on every path that changes a person's rights (company setting: warn or block) and when a command acts on a document related to one the same person handled on the other side. Small companies get an explicit exception mode with compensating controls, flagged for the author.

**Delegation.** A user may delegate approval authority, or named role assignments, to another user for a dated window. Delegation is audited and never goes to an agent. ADR-0055 uses it for approvals.

**Users.** User accounts are created, disabled and enabled, never deleted. One account may work in several companies. A company that names an existing login only invites it: the person confirms in their own session, and a shared account's credentials are changed only by an operator. There are no user groups: roles carry permissions, and departments, teams and roles carry routing.

### Rules

**Module, tables and registrations**

1. Ownership and the DDL draft:
   - **`permissions`** (layer 2, ADR-0022 rule 2) owns `user_account`, `user_session`, `credential_reset`, `integration_client`, `integration_token`, `installation_role_assignment`, `role`, `role_level`, `role_permission`, `role_assignment`, `role_assignment_scope`, `delegation`, `delegation_role_assignment`, `user_invitation`, `role_permission_hold`, `company_segregation_rule`, `segregation_exception` and `segregation_review`, and the work item kinds `segregation_review_due` (rule 20) and `role_permission_held` (rule 9).
   - **`master_data`** (layer 3) owns `department`, `team` and `team_member`, and the new `employee_profile` columns (rule 6).
   - **The DDL draft** is [DS-15-access.sql](../design/DS-15-access.sql). ADRs win if it disagrees. It follows DS-20's conventions: `company_id` on every company table, composite keys on `(company_id, id)`, `FORCE ROW LEVEL SECURITY` and the generated company policy (ADR-0017 rule 19).
   - **Installation tables.** `user_account`, `user_session`, `credential_reset`, `integration_client`, `integration_token` and `installation_role_assignment` have no `company_id` and no company policy. `erpme_app` reaches them only through `permissions.contract` and the authentication endpoints. `erpme_readonly` sees users only through a view `company_user` of the users with an assignment in the current company (DS-33).
   - **Catalog files.** The area tree, verb levels, templates and segregation rules are core catalogs (rule 25), not tables. Tables store their codes as text, validated by commands.
2. Registered functions. Access decisions need data from modules that may not import each other, so each module registers functions with the dispatcher, like handlers, and `app` (layer 6) wires them. Beyond ADR-0022 rule 2's existing imports (`documents`, `permissions` and `policy` import `work`), `work`, `documents`, `permissions` and `policy` import nothing from each other for this ADR or ADR-0055:
   - **The organization resolver**, from `master_data`: for a user in a company, the user's employee, the employees of the user's teams, and the employees under the user (rule 13). It reads current data in the command's transaction.
   - **Related documents**, from each module that owns document types: for a document, the documents linked to it by a segregation relation (rule 19).
   - **Document actors**, from `documents`: who wrote each version, who approved, and who posted a document (from `document_version`, `approval` and the audit record of the `Post`, ADR-0038 rule 2).
   - **Effective rights**, from `permissions`: a principal's permissions, record scope, owner scopes and field classes in force on a day, with delegations, and the holders of a role in a scope. The dispatcher's permission check and the segregation checks of rules 18–19 call it.
   - **The period resolver**, from `periods`: the posting period of a date, for the review items of rule 20.
   - **Stage eligibility, plan and work item visibility** of ADR-0055 (its rule 1): `policy` registers the stage reader, and the dispatcher combines it with effective rights and document actors. `work` filters items through a registered visibility function (rule 15), so it never reads assignments or stages itself.

   Note: the document-actors function also returns the submitter of each round (the human of the `Submit`: its actor, or its `on_behalf_of`), which `approver_is_submitter` reads ([ADR-0050](0050-agent-runtime-and-query-layer.md) rule 14).

**Users**

3. `user_account` (installation data, label `personal`, spec 17):
   - **Columns:** `login` (lower case, unique in the installation), `display_name`, `email`, `language`, `time_zone`, the credential columns of rule 4, `is_active`, `created_at`, `disabled_at`, `erased_at`.
   - **One account, several companies.** A user works in a company through role assignments there. Without an assignment in force, the company is not offered (`GetSessionContext`, ADR-0040 rule 12).
   - **Linked users.** A user is linked to a company when they hold a current or future role assignment there (one whose `valid_to` is empty or not before `clock.today`) that is not pending (below). A user linked to more than one company is **shared**.
   - **Creating or inviting** (`CreateUserAccount`, company-scoped, sent in one batch with its first `CreateRoleAssignment` in that company, ADR-0008 rule 20). It matches only on the exact `login`; it never searches by name or e-mail. Either way it writes a `user_invitation` row (company, login, and the display name and e-mail as the company typed them), and its result and plan are the same: the invitation ID and nothing else.
     - **A new login:** the account is created from what the company typed, and the invitation is `confirmed` at once. The batch's assignment, which names the invitation, is in force from its dates.
     - **An existing login:** nothing about the account changes. The invitation is `pending`, and the batch's assignment is pending with it: it grants no access, is not in force, and does not count toward linked or shared users, the segregation checks or the small-company bound.
     - **What the company sees.** Until confirmation, the company's queries show only the invitation: what it typed, and the state `pending`. The account's own name, e-mail and other companies are never shown to it, and its credential commands answer `record_not_found` for that user.
     - **The accepted trade-off.** The command's answer is the same either way, but the invitation's state is not: `confirmed` at once means the login was new, `pending` means it already existed. So a company learns whether a login exists, and nothing more about the account. This is accepted, because the person must confirm before anything is shared. The UI warns on a pending invitation that the login belongs to an existing account and that only its owner can confirm.
     - **Expiry.** A pending invitation expires after the installation setting `invitation_expiry_days` (default 30): it becomes `expired` (state set by the daily job, and checked at confirmation), and its assignments never come into force. The company re-sends by running `CreateUserAccount` again, which writes a new invitation; `UpdateRoleAssignment` may move the old assignments onto it.
     - **Confirmation.** The invited person runs `ConfirmUserInvitation` (`human_only`). The pending assignments then come into force, through the checks of rule 18 like any change of rights. The person may instead run `CancelUserInvitation`, and so may the company's administrator (level `edit` on `user_account`) while it is pending; a canceled invitation's assignments never come into force.
     - **Company scope for the invited person.** Both commands are company-scoped: the envelope names the invitation's company, and the transaction sets `erpme.company_id` to it as for any command (ADR-0017 rule 19). The invited person holds no permission there yet, so for these two commands the dispatcher's permission check is that the caller is the invitation's user, as `GetSessionContext` needs only a valid credential (a note on ADR-0017 rule 8); the company's administrator cancels through the ordinary permission.
     - **The pending list.** `ListPendingUserInvitation` (also in `GetSessionContext`) is a registered cross-company query (ADR-0017 rule 19). Its `erpme.company_ids` are the companies holding a pending invitation for the caller, and it returns only the caller's own rows. Those companies come from one security-definer function, `pending_invitation_companies`, owned by a no-login role `erpme_invitation` whose only policy on `user_invitation` sees pending rows; it returns company IDs for the session's user and nothing else, in the pattern of `erpme_claim`. No role gains `BYPASSRLS` (a note on ADR-0017 rule 19).
     - **Two people, one login.** If the company meant someone else, nothing happens to the account's owner: they see an invitation they do not recognize and leave or cancel it, and the company sees it stay pending and cancels it. INV-231 checks that no assignment from an invitation was ever in force before its user confirmed it, and that every first link of a user to a company came through a confirmed invitation.
   - **Other commands:**
     - `UpdateUserAccount` changes name, e-mail, language and time zone.
     - `DisableUserAccount` and `EnableUserAccount`. Disabling revokes sessions and tokens at once (ADR-0017 rule 2), suspends schedules and intakes the user owns, and raises `owner_suspended` (ADR-0017 rule 12; ADR-0042 rule 7).
   - **Whose credentials a company may touch.** A company's credential commands (`UpdateUserAccount`, `DisableUserAccount`, `EnableUserAccount`, `CreateCredentialReset`, `ClearUserAccountLockout`) reach only users linked to that company; for any other user they answer `record_not_found`.
   - **Shared users.** For a shared user, a change of display name or e-mail by `UpdateUserAccount`, `DisableUserAccount`, `CreateCredentialReset` and `ClearUserAccountLockout` are run only by an operator; a company caller gets `user_shared_across_companies`. To disable, the company ends its own assignments instead. When a user becomes shared (a confirmation linking a second company), every unused reset token a company issued for them is voided, so a token handed out earlier cannot be used against the other company.
   - **Operators.** An operator (installation scope, ADR-0017 rule 7) may always run the name and e-mail change, the reset and the lockout clearance, for any user. This is also the recovery path of a sole owner who is locked out or has lost their password: nobody in the company holds every right the owner holds, so the operator does it.
   - **No escalation inside a company.** For the name or e-mail change and `CreateCredentialReset`, a company caller must hold every permission the target user holds in the company (assignments and delegations in force), with a company-wide assignment; otherwise `grant_exceeds_own_rights`. So an IT administrator cannot reset an owner's password and sign in as the owner. `ClearUserAccountLockout` is exempt, because it grants no access: the person still needs their password and TOTP.
   - **Never deleted.** No `Delete` command exists, so history keeps every reference. Erasing a former user's personal data (`EraseDataSubject`, ADR-0019 rule 10) replaces name, login and e-mail with a token and sets `erased_at`; the ID stays.
   - **INV-227** checks the shared-user and escalation conditions from the audit records.
4. Authentication (ADR-0017 rule 2, unchanged where not stated):
   - **Credentials:** `password_hash` (argon2), `totp_secret` (encrypted at rest, DS-18), `is_totp_enabled`, and `oidc_issuer` with `oidc_subject`, unique together.
   - **Lockout:** `failed_sign_in_count` and `locked_until`. After the installation's limit (default 10 failures), sign-in is refused with `user_account_locked` until `locked_until` (default 15 minutes later). `ClearUserAccountLockout` ends a lockout early (rule 3's conditions). A successful sign-in resets the count.
   - **TOTP.** A role has `is_totp_required`. A user who holds any such role in any company, directly or through a delegation in force (rule 21), or who is an operator, must enable TOTP before the session is created. Templates `owner`, `chief_accountant` and `it_administrator` set it. This replaces the test "holds the role `owner` or `chief_accountant`" in ADR-0017 rule 2, which would break when a company renames roles. Whether every user needs TOTP stays open.
   - **Password reset.** `CreateCredentialReset` (rule 3's conditions) makes a one-time token, stored as a hash, valid for at most 24 hours, and returns the link once. The person hands it over; ERPMe sends nothing in Phase 1. The token records `issued_in_company_id`, the company whose caller issued it (empty for an operator), so it can be voided when the user becomes shared (rule 3). A new hand-written endpoint `POST /api/auth/password` consumes the token or, with the current password, changes it (a note on ADR-0040 rule 12).
   - **What a reset does.** Consuming the token sets the password, revokes every session of the user and every other unused reset token, and writes an audit record, as creating it did. It never clears TOTP enrolment or the OIDC link: a user with TOTP still needs their code at the next sign-in. Re-enrolling a lost TOTP device is an operator task (DS-18).
   - **Sessions** are `user_session` rows (token hash, CSRF token hash, idle and absolute expiry, `revoked_at`).
5. No user groups. Business One's user groups mainly route alerts and approvals. Here, permissions come only from roles (one path for the dispatcher and for agents to reason about), and routing uses roles, approval stages (ADR-0055), departments and teams. One concept fewer is easier for people and agents. Revisit when routing needs a set of people that no role, department or team expresses.

**Organization for access**

6. Departments, teams and employees (`master_data`, `master_data_change`, change-tracked, `human_only`, because they change access):
   - **`department`:** `code`, `name`, optional `parent_id` (a tree; a cycle is refused with `department_cycle`), optional `manager_partner_id` (an active employee), `is_active`.
   - **`team`:** `code`, `name`, optional `department_id`, and members in `team_member` (employee partners). Teams are optional, for example a sales team across departments.
   - **`employee_profile`** gains `department_id` and `manager_partner_id`, the employee's manager. The chain of managers must not loop (`employee_manager_cycle`). This changes DS-20, and ADR-0045 rule 11 gets a note.
   - **Users and employees.** A user's position in a company is the employee profile whose `user_account_id` is that user. DS-20 makes `user_account_id` unique per company instead of across the installation, so a user who works for two companies can be an employee of both. A user without an employee profile can own documents only as their creator (rule 14).
   - **Commands:** `CreateDepartment`, `UpdateDepartment`, `CreateTeam`, `UpdateTeam` (with its members), and `UpdateEmployeeOrganization` (an employee's `department_id`, `manager_partner_id` and `user_account_id`). All are on the leaf `organization` and need level `full` (rule 8's minimum level), because each can widen someone's owner scope. Queries `ListDepartment`, `ListTeam`.
   - **One way in.** `UpdateEmployeeOrganization` is the only command that changes the three `employee_profile` columns. `CreatePartner` and `UpdatePartner` (DS-20) leave them unchanged and refuse a payload that names them, and so does a change proposal that targets them (ADR-0029), with `employee_organization_command_required`. INV-228 checks it.
   - **No self-change, by effect.** Each of these commands computes the caller's organization resolver result (rule 2: their employee, their teams' employees and the employees under them) before and after the change, in its own transaction. If it differs, the command is refused with `organization_self_change`, as nobody assigns a role to themselves (ADR-0017 rule 6). This catches every route: naming the caller as someone's manager, moving employees into the caller's department, reparenting a department under one the caller manages, joining a team, or linking a profile. A caller whose assignments in force all have owner scope `company` is exempt, since nothing can widen for them; so a sole owner can link their own employee profile.

**Authorization areas and levels**

7. The area tree is the core catalog [authorization-areas.csv](../catalogs/authorization-areas.csv):
   - **Columns:** `code`, `parent_code`, `kind` (`area`, `document_type`, `master_data`, `function`, `report`), `module`, `name`, `added_in`, `meaning`.
   - **Roots:** `sales`, `purchasing`, `inventory`, `production`, `planning`, `finance`, `banking`, `master_data`, `crm`, `administration`, `reports`.
   - **Leaves.** Each document type is a leaf with the type's name. Master data nouns are grouped into leaves such as `partner`, `partner_bank_account` and `price_list`. Functions are leaves such as `posting_period`, `exchange_rate`, `role` and `agent_run_bodies`. Report groups are leaves such as `report_finance`.
   - **Printing and reports** ([ADR-0049](0049-statutory-reporting-and-printing.md)): `print_profile` under Master data (company and branch print profiles, seals and signatures; `none` in every template except `owner`), and `print_template` under Administration (print templates and print data contracts; print data itself follows its subject, rule 24). The leaves of every ADR-0049 command and query are listed in rule 24.
   - **CRM** ([ADR-0052](0052-minimal-crm.md)) has the leaves `interaction` (interactions, participants, links, partner e-mail domains, summaries, inbound messages and the partner timeline), `complaint`, `outbound_message` and `data_subject_request` (document types), `mailbox` (mailboxes, their authentication probe and the intake), `data_protection` (processing purposes and bases; `EraseDataSubject` at `full`), and `partner_insight` (insights, the duplicate scan and tax lookups).
   - **Every permission has one leaf.** Commands and queries of a document type belong to its leaf, and those of a master data noun to that noun's leaf. Every other command, query and capability declares its leaf when it is registered (a note on ADR-0008 rule 1). CI fails when a permission has no leaf or names one outside the catalog.
   - **Generation.** The catalog is seeded by this ADR and generated from the registry once it exists, like the work item kinds (ADR-0042 rule 1).
   - **Installation-scoped commands** (package loading, installation roles, the operator variants of rule 3) stay with the `operator` role (ADR-0017 rule 7) and are outside the tree. `ConfirmUserInvitation` and the invited person's `CancelUserInvitation` need no leaf either: their check is that the caller is the invitation's user (rule 3).

   Note: new leaves: one per agent type under `agent` (`agent_customer_onboarding`, `agent_quotation`, `agent_bank_matching`, `agent_purchase_invoice`, `agent_planning`, `agent_data_migration`), each holding `start_agent:<agent_type>`, and `event_delivery` under Administration; `agent` belongs to module `agents`. `StartAgentRun` and `CancelAgentRun` need no leaf of their own: their check is a capability (rule 24 note), as the invitation commands' check is the caller. Commands registered `is_internal_only` keep their leaf for grouping, and no level reaches them (rule 8 note).
8. The level a permission needs:
   - **Levels are ordered:** `none` < `read` < `edit` < `post` < `full`.
   - **Queries** (`Get`, `List`, computed queries) need `read`.
   - **Commands** need the highest of their verb's level, their effect class's level, and the minimum level they declare at registration, if any. Verb levels are the core catalog [authorization-verb-levels.csv](../catalogs/authorization-verb-levels.csv). Effect classes (ADR-0008 rule 1): `posting` and `outbound_send` need `post`, `master_data_change` needs `edit`, and `other` adds nothing.
   - **The verb levels, in short:**
     - `read`: Render (a file of data the caller may read; ADR-0049 rule 20);
     - `edit`: Create, Update, Delete, Submit, Cancel, Recall, Request, Claim, Unclaim, Resolve, Assign, Start, Reserve, Pack, Unpack, Firm, Convert, Allocate, Match, Unmatch, Ignore, Validate, Import, Set, Verify;
     - `post`: Post, Issue, Record, Complete, Reopen, Close, Release, Confirm, Accept, Transfer, Run, Resume, Abandon, Restrict, Open, Skip, Retry, Send, File;
     - `full`: Reverse, Lock, Unlock, Clear, Erase, Activate, Enable, Disable, Export, Replay.
   - **Declared minimum levels** raise a command above its verb: `UpdateEmployeeOrganization` and the other organization commands are `full` on `organization` (rule 6), and `AcceptMigrationDifference` is `full` on `opening_balance_entry` (rule 24). Commands that only a registered system job or worker runs, such as CRM's `Record…` and `Run…` commands of the intake, outcomes, tax lookups, the duplicate scan and the insight computation, declare `full` on their leaf, so no ordinary role holds them; the job holds its permissions by registration (ADR-0017 rule 13).
   - **File commands** sit on report leaves at their verb's level, `post`: `FileStatutoryReport` (ADR-0049 rule 19) on `report_finance`, and `FileTaxReturn` (ADR-0041 rule 18) on `report_tax`. Template `chief_accountant` has `post` on both.
   - **Approve and Reject** are not given by a level but by the role's approval flag (rule 9).
   - **Capabilities** declare their leaf and level when registered: `post_in_soft_locked_period` is `full` on `posting_period` (so spec 07's chief accountant holds it through Finance `full`), `start_agent:<agent_type>` is `edit` on `agent`, `list_all_work_items` is `full` on `work_queue_administration`, `delegate_for_others` is `full` on `delegation`, and `read_agent_run_bodies` (ADR-0050 rule 20) is `full` on its own leaf `agent_run_bodies`, which every template except `owner` sets to `none`.
   - **New verbs.** A verb in the glossary must have a row in the verb catalog; CI fails otherwise. This ADR adds the rows for Send, File, Render and Verify (`VerifyMailboxAuthentication`, ADR-0052), and the glossary rows for Set, which DS-20's price list commands already use, and for Verify.
   - **`human_only`** stays a registry flag beside the level. No level gives an agent a `human_only` command (ADR-0017 rule 14).

   Note: commands that only a registered system job or consumer runs are registered `is_internal_only` instead ([ADR-0008](0008-command-envelope-and-registry.md) rule 1 note): the expansion skips them, so no role holds them at any level, `owner` included, and they have no REST endpoint, MCP tool or tool definition. They are `CompleteAgentRun`, `Record<Type>EInvoiceOutcome`, `RecordInboundMessage`, `RecordMailboxIntakeOutcome`, `RecordMailboxAuthenticationCheck`, `RecordOutboundMessageOutcome`, `RecordPartnerTaxLookup`, `RecordRenderOutcome`, `RunApprovalEscalation`, `RunAgentQualityCheck`, `RunPartnerDuplicateScan` and `RunPartnerInsightComputation`, and every later command of that kind. A declared `full` stays only for system commands a person may also start, such as `RunMailboxIntake`.
9. Role levels and their expansion:
   - **`role_level`** (role, node, `level`, `can_approve`) may be set on any node. A leaf's effective level and approval flag come from the nearest node at or above it that has a row; with none, `none` and false. So "Sales: `post`" with "credit_note: `read`" gives `post` on every sales leaf except credit notes, as in Business One's tree.
   - **`can_approve`** needs a level of at least `read` on the same row. It adds `Approve<Type>` and `Reject<Type>` of the document types below.
   - **The expansion** of a role is the set of every registered permission whose leaf's effective level is at least the level the permission needs (rule 8), plus the approval commands of rule 9. It is a pure function of the role's rows and the registry catalog, so the same rows always give the same set.
   - **Storage.** The expansion is stored in `role_permission`, with `role.registry_version` and `role.expansion_hash` (SHA-256 of the sorted list). It is recomputed in the transaction of every `UpdateRole` and by the upgrade step for every role (DS-37). The upgrade report lists, per role, the permissions gained.
   - **Upgrades.** Within a leaf, new commands follow the level automatically, because the level states the company's intent; a new leaf starts at its parent's level, and the template's level for it is offered as an addition (ADR-0017 rule 5's proposal mechanism). Interim, flagged (open question): this changes ADR-0017 rule 5, under which every addition was offered. A gained permission that would break the segregation mode `block` or the small-company bound (rules 18, 20) is held back instead:
     - **`role_permission_hold`** (company, role, permission, `reason` `segregation_conflict` or `small_company_mode_active`, `registry_version`, `state`, created by the upgrade step, decided by and at). States: `held` until a person decides; `granted`; `ignored`, which keeps the permission withheld until a person next changes the role's levels; `ended`, when that change comes.
     - **Holds in force** are those `held` or `ignored`. The stored `role_permission` is the expansion minus the holds in force (INV-220).
     - **`ConfirmRolePermissionHold`** grants the permission. It is a change of rights, so the checks of rules 18 and 20 run again, and the caller must hold the permission (rule 10); otherwise the hold stays.
     - **`IgnoreRolePermissionHold`** keeps it withheld. An `UpdateRole` that changes the role's levels ends every hold of the role (state `ended`): the new expansion is computed in full, under the same checks.
     - **Work item.** When the upgrade step creates holds in a company, it raises one `role_permission_held` item for `company_owner`, with the holds as evidence; it is resolved when no hold of the company is `held`.
     - Both commands are `human_only`, `master_data_change`, on the leaf `role`, change-tracked and on no agent tool list.
   - **The dispatcher** checks `role_permission` only (ADR-0017 rule 8). INV-220 checks that every stored set equals the expansion minus the holds in force.
   - **No single-permission additions** in Phase 1: a role is its levels. Revisit when a company needs one command without its leaf.
10. Roles are company data (`role`: `code`, `name`, `template_code`, `basis`, `is_totp_required`, suggested owner scopes, `is_active`):
    - **Commands:** `CreateRole` (blank, or copied from a template) and `UpdateRole` (name, levels, flags). All are `human_only`, `master_data_change`, change-tracked (ADR-0038 rule 3) and on no agent tool list.
    - **No escalation.** A person may create or change a role only when they hold every permission the role would gain, with a company-wide assignment; otherwise `grant_exceeds_own_rights`. The plan of `UpdateRole` lists the permissions gained and lost, so the role editor shows the effect before it is executed.
    - **Basis.** A copied template row keeps the template's basis; rows the company changes get `company_decision` (ADR-0016 rule 12).
    - **`template_code`** stays when the company renames or edits the role. It is how the core finds "the owner role" or "the accountant role" (rule 11).

**Templates**

11. The core seeds thirteen job-role templates: the catalogs [role-templates.csv](../catalogs/role-templates.csv) (attributes) and [role-template-levels.csv](../catalogs/role-template-levels.csv) (levels per node). They replace ADR-0017 rule 5's list: `sales` becomes `sales_clerk` and `sales_manager`, `purchasing` becomes `buyer` and `purchasing_manager`, and `viewer` becomes `auditor`.

    | Template | In short | Suggested owner scope (read / edit) |
    | --- | --- | --- |
    | `owner` | `full` and approve everywhere (ADR-0017 rule 6 interim) | company / company |
    | `chief_accountant` | Finance and Banking `full`, supplier invoices and sales corrections `full`; files statutory reports and tax returns; other areas `read`; policy administration; approves | company / company |
    | `accountant` | Finance and Banking `post`, posting periods and the chart `read`; invoices `post`; approves | company / company |
    | `cashier` | Cash documents and counts `post`, bank documents `read`; no reports | company / own |
    | `sales_clerk` | Quotations, orders and sales corrections `edit`; customers `edit` | own / own |
    | `sales_manager` | Sales `post` and approve; price lists `edit` | department / department |
    | `buyer` | Requests, orders and supplier invoices `edit`; suppliers `edit`; planning `edit` | own / own |
    | `purchasing_manager` | Purchasing `post` and approve; planning `post` | department / department |
    | `warehouse_keeper` | Inventory `post`; production issues and receipts `post`; orders `read` | branch / branch |
    | `production_planner` | Production `post`, Planning `full`, production structures `edit` | company / company |
    | `shop_floor_lead` | Confirmations, production issues and receipts `post`; production orders `read` (the shop-floor role of ADR-0034 rule 18) | branch / branch |
    | `auditor` | `read` everywhere, audit records included; nothing else | company / own |
    | `it_administrator` | Users, roles, assignments, delegations, organization and settings `full`; policy and segregation rules `read`; no Finance or Banking, no data import, no agent run bodies | company / company |

    - **Approvers.** Templates `owner`, `chief_accountant`, `accountant`, `sales_manager` and `purchasing_manager` have `can_approve` in their areas. Each of them also has `edit` on `delegation`, so that a person can delegate their own approvals (rule 21). `delegate_for_others` (`full` on `delegation`) stays with `owner` and `it_administrator`, who may delegate only what they hold themselves. ADR-0055's seeded stages name `accountant`, `chief_accountant` and `owner`.
    - **Everyone** gets `read` on `general_access` (`ListAllowedCommand`, ADR-0040 rule 8) and `edit` on `work_queue`.
    - **CRM levels.** `sales_clerk` and `buyer` edit interactions and outbound drafts, and `sales_clerk` complaints; `sales_manager` and `purchasing_manager` post and approve outbound messages, and `sales_manager` closes complaints; `chief_accountant` posts and approves outbound messages (dunning reminders, ADR-0048 rule 17), `accountant` drafts them; `it_administrator` has `mailbox` `full`; `owner` has CRM `full`, `data_protection` included; `auditor` reads CRM.
    - **Agent run bodies.** Only `owner` holds `read_agent_run_bodies`; every other template sets `agent_run_bodies` to `none`, as ADR-0050 rule 20 intends.
    - **The cashier** gets no report leaf. ADR-0049's book queries (`ListBookRow`, `RenderReport`) take the report code as a parameter, so a leaf cannot narrow them to the cash and bank books: `read` on `report_finance` would show every book and statement. The cashier sees cash through the cash documents and counts they hold; the cash book itself is read by an accountant. Revisit if cashiers need the book itself, with a report-code dimension.
    - **Print profiles.** Only `owner` holds `UpdatePrintProfile` (ADR-0049 rule 26): every other template sets `print_profile` to `none`.
    - **The IT administrator** can assign only roles whose permissions they hold (rule 10; ADR-0017 rule 6), so finance roles are assigned by an owner. It has no `data_import`, since imports post (ADR-0044).
    - **Seeded conflicts.** Templates `owner`, `chief_accountant` and `accountant` hold both sides of some seeded segregation rules, as small accounting teams usually do. In `warn` mode this shows as check results, and the per-document check of rule 19 is the control. A company that wants `block` narrows these roles first (rule 18).
    - **Owner rules that name a template** (ADR-0042 rule 7) resolve through `role.template_code`, never through role codes or names. `role:<template>` means the holders of the company's active roles with that `template_code`. `company_owner` means the holders of active roles with `template_code` `owner`; if there is none, the holders of a role with every permission of the template `owner` (rule 12 keeps one). When no active role has the template a `role:<template>` rule names, the item goes to `company_owner`. A note on ADR-0042 rule 7.
    - **Renamed owner rules.** `role:sales` becomes `role:sales_clerk` in [work-item-kinds.csv](../catalogs/work-item-kinds.csv) (kinds `interaction_unmatched`, `sales_return_due`, the matched inbound message kind and `complaint_open`), with notes on ADR-0019 rule 15, ADR-0051 rule 30 and ADR-0052 rule 20.
    - **Interim.** The template contents are defaults that the author may change (flagged; open question).

    Note: template changes from the production review. `production_planner` gets `post` with `can_approve` on `production_order` and `edit` on `delegation`, and is a member of pool `mo`'s `standard` stage (interim, flagged for the author). `buyer` and `warehouse_keeper` get `post` on `service_receipt`, a Purchasing leaf ([ADR-0037](0037-subcontracting.md) rule 5's note). `production_planner` therefore joins the approving templates (holistic review 2026-11-15, item P14).

    Note: every template except `auditor` has `edit` on `general_access`, which now also holds `CreateAttachment`, `CreateListExport` and `GetApprovalProgress`, each checked against its subject's or query's own permission (rule 24 note). Interim seed, flagged for the author: `start_agent:<agent_type>` at `edit` on the agent type's leaf for `sales_manager` (`quotation`, `customer_onboarding`), `chief_accountant` (`bank_matching`, `purchase_invoice`) and `production_planner` (`planning`); `owner` and `it_administrator` hold every agent type through Administration `full`, and `owner` is the one for `data_migration`. The recommended workflow owner of each agent type ([ADR-0050](0050-agent-runtime-and-query-layer.md) rule 14) is a holder of the same template; the hard floor keeps that person from approving the agent's drafts, so another approver does (open question).

    Note (flow review, 2026-11-15): the templates other than `owner` now hold no both sides of a seeded segregation rule (rule 17). The changes, in [role-template-levels.csv](../catalogs/role-template-levels.csv) and [role-templates.csv](../catalogs/role-templates.csv):
    - `accountant`: `partner` `read` (was `edit`; `partner_vs_purchase_invoice`); `cash_payment` and `bank_payment` `edit` with approval (was `post` through Banking; `purchase_invoice_vs_payment`): an accountant drafts, submits and approves payments and does not post them;
    - `chief_accountant`: `cash_payment` and `bank_payment` `edit` with approval (`purchase_invoice_vs_payment`); `partner_bank_account` `read` (was `edit`; `bank_account_vs_payment`), so partner bank accounts are the owner's by default, and a company may give them to a role without payment rights;
    - `cashier`: `bank_payment` `post`: the cashier posts the payments accountants prepare (in Phase 1 a bank payment records a transfer made outside ERPMe, [ADR-0048](0048-cash-bank-receivables-payables.md) rule 3);
    - `sales_manager`: `price_list` `read` (was `edit`; `price_list_vs_sales_approval`), and `sales_clerk`: `price_list` `edit` (was `read`): price lists are maintained by the sales clerk, who approves nothing, while prices outside the list or below cost still reach the sales manager through policy (ADR-0043 rule 3);
    - `purchasing_manager`: `purchase_invoice` `edit` with approval (was `post` through Purchasing; `partner_vs_purchase_invoice`): accountants post supplier invoices.

    Payment reversals (`full`) stay with `owner`. `owner` keeps every permission (rule 12), so its conflicts remain and rule 19's per-document check is its control; for every other template this replaces the bullet **Seeded conflicts**. Lab check `t12_access.py` checks that no other template holds both sides of a seeded rule. Also ([ADR-0055](0055-approval-pools-and-stages.md) rule 5 note): `sales_manager`, `purchasing_manager` and `production_planner` have `edit` with `can_approve` on `change_proposal`, so they submit and approve change proposals, and `production_planner` has `edit` on `delegation` as an approving template. Interim, flagged with the template contents (open question).

    Note (catalog review, 2026-11-15): the templates `accountant`, `sales_clerk` and `buyer` also get `change_proposal` at `edit` without the approval flag, so the people who handle agent proposals in their area (bank matching rules, customer onboarding, purchase mapping) can submit them; approval stays with the `general` pool ([ADR-0055](0055-approval-pools-and-stages.md) rule 5 note). `change_proposal` is on no side of a seeded segregation rule, so every template except `owner` stays free of conflicts.

    Note (simulation review, 2026-11-15): a workflow owner must not be a planned approver of the agent's drafts, since the hard floor keeps that person from approving them. The interim seed of `start_agent:<agent_type>`, and with it the recommended workflow owner of each agent type, changes (it replaces the seed of the general-access note above):
    - `quotation` and `customer_onboarding`: `sales_clerk` (was `sales_manager`);
    - `purchase_invoice` and `bank_matching`: `accountant` (was `chief_accountant`);
    - `planning`: `production_planner`, and `data_migration`: `owner`, unchanged.

    `sales_manager` and `chief_accountant` no longer hold these capabilities, so the people who approve quotations, onboarding proposals and mismatched supplier invoices are not their writers through a run. `owner` and `it_administrator` keep every agent type. In [role-template-levels.csv](../catalogs/role-template-levels.csv); lab check `t12_access.py` C28. Interim, flagged with the template contents (open question).

**Assignments, record scope and owner scope**

12. `role_assignment` (company data, change-tracked):
    - **Columns:** role; `principal_kind` (`user` or `integration_client`) with the matching ID; `owner_scope_read` and `owner_scope_edit` (users only); `field_classes` (ADR-0017 rule 10); `valid_from` and `valid_to` (business dates in the company's time zone, inclusive; empty end is open); `granted_by_user_id`.
    - **Record scope** is `role_assignment_scope` rows, each a branch or a warehouse (ADR-0017 rule 9). None means the whole company.
    - **Commands:** `CreateRoleAssignment` and `UpdateRoleAssignment`. An assignment ends by setting `valid_to`; it is never deleted, so history shows who could do what on any date.
    - **Only linked users or invitations.** For a user not linked to the company (rule 3), both commands answer `record_not_found`, unless the assignment names that user's pending or confirmed invitation in the company. So a company that still knows a former user's ID, from history, cannot give them rights again without a new invitation that the person confirms.
    - **ADR-0017 rule 6 holds:** nobody assigns a permission they do not hold (`grant_exceeds_own_rights`) or assigns to themselves, and the last user with a role holding every permission of the template `owner` in a company keeps it (`last_owner_required`).
    - **In force** means `valid_from` ≤ `clock.today` ≤ `valid_to`, the role and principal are active, and the assignment is not pending: it names no invitation, or a `confirmed` one (rule 3). An assignment naming a `pending` or `canceled` invitation grants nothing and counts nowhere.
13. Owner scope:
    - **Values:**
      - `own`: documents whose owner employee is the user's employee, or whose creating user is the user;
      - `team`: as `own`, plus documents whose owner employee is in one of the user's teams;
      - `department`: as `own`, plus documents whose owner employee is under the user (below);
      - `branch`: every document inside the assignment's record scope, which must not be empty;
      - `company`: every document of the company; the assignment must have no record scope.
    - **"Under the user"** means: employees of the user's own department; employees of every department in the subtree of a department the user manages; and employees whose chain of managers leads to the user. The organization resolver computes this set from current data on each request, so a transfer takes effect at once, as in Business One.
    - **Read and edit.** Queries, `Approve` and `Reject` use the read scope. Every other command uses the edit scope. The edit scope may not be wider than the read scope: `own` fits under any scope, `team` under `team`, `branch` or `company`, `department` under `department`, `branch` or `company`, and `branch` under `branch` or `company`. Otherwise `role_assignment_invalid`; the database holds the pairs.
    - **Who has it.** Only user assignments carry owner scopes. Integration assignments have none; an agent run is bound by its human's owner scope (rule 16).
14. The document owner:
    - **Columns.** The shared `document` row (ADR-0009 rule 1, which gets a note) gains `owner_employee_id` (an employee partner, nullable) and `created_by_user_id`.
    - **`created_by_user_id`** is the human of version 1: the actor if human, else its `on_behalf_of` (for agents, system jobs, consumers and integrations).
    - **`owner_employee_id`** comes from the field the document type registers as `owner_field` (a note on ADR-0009 rule 2). Defaults: `salesperson_id` for sales types, `buyer_id` for purchasing types, and the creating user's employee for every other type. `documents` sets it at `Create` and on every `Update` that changes the owner field; neither column is part of the version content.
    - **Defaults by type:**

      | Types | Owner field |
      | --- | --- |
      | `quotation`, `sales_order`, `sales_invoice`, `sales_return`, `credit_note`, `debit_note` | `salesperson_id` |
      | `purchase_request`, `purchase_order`, `purchase_invoice`, `purchase_return`, `purchase_credit_note`, `purchase_debit_note`, `gr_ir_write_off` | `buyer_id` |
      | every other type | the creating user's employee |

    - **No owner.** An owner field naming an employee without a user account still works through `department` and `team`; a document with no owner employee is reached through `own` only by its creator.

    Note: agent workflows set a draft's owner field from the scope partner's profile: `salesperson_id` from `customer_profile.salesperson_id`, `buyer_id` from `supplier_profile.buyer_id`, left empty when the profile names none ([ADR-0051](0051-agent-workflows.md) rule 8 note). The person holding the claim of the work item a draft is linked to reads and edits that draft while the claim holds, whatever their owner scope (record scope and permissions still apply), through the visibility function of rule 2 ([ADR-0042](0042-work-queue.md) rule 10 note).
15. How the scopes combine:
    - **Per assignment:** row-level security (company) AND record scope AND owner scope. Across assignments: a row is visible or editable when any assignment that grants the permission allows it (ADR-0017 rule 6).
    - **Outside the scope:** a command gets `record_not_found`, and a query leaves the row out with `is_scope_filtered: true` (ADR-0017 rule 9). The read-only layer's views apply the same filters (DS-33).
    - **Master data** is filtered by record scope only; owner scope applies to documents.
    - **What follows the document.** Everything that shows a document's data is filtered by that document's read scope, record and owner scope together, so no side path shows what the document list hides. Each owning ADR gets a note:
      - its journal entry, journal lines and stock movements (ADR-0017 rule 9);
      - work items whose subject is a document, or a line of one: visible only when the caller's read scope reaches the document, besides the conditions of ADR-0042 rule 10; the visibility function of rule 2 applies it;
      - the partner timeline: a document entry appears only when the caller's read scope reaches the document; otherwise it is left out with `is_scope_filtered` (ADR-0052 rule 18);
      - audit queries: `ListAuditRecord` and `GetAuditRecord` show a record whose subject is a document only within that document's read scope (ADR-0038 rule 7);
      - open items (`ListOpenItem`, ADR-0026 rule 15) and the partner statements listed from them: each open item follows its origin document;
      - attachments linked to a document, and print files rendered from one: they follow the document (ADR-0038 rule 14; ADR-0049 rule 20);
      - the live-update header (ADR-0040 rule 13): it also carries the subject document's `owner_employee_id` and `created_by_user_id`, as IDs, and a header is forwarded only when the session's read scope reaches the document, checked against the same cached assignments and organization set.
    - **Aggregating queries.** A query that totals over documents without returning them is registered `is_owner_scoped: false` (a note on ADR-0008 rule 1). This covers reports (DS-26; ADR-0049) and also non-report aggregates such as `GetPartnerExposure` (ADR-0026 rule 15) and aging totals over open items. It needs an assignment with owner scope `branch` or `company` for its permission; otherwise `permission_denied`. So totals never reveal documents outside a user's owner scope.
    - **Row-level security** stays company-only (ADR-0017 rule 19). Owner and record scope live in the dispatcher and the read-only layer, as the second line is for companies.

**Agents and integrations**

16. Agents and integrations:
    - **Agents.** An agent run's rights stay as ADR-0050 rule 31 states: its agent type's declared permissions (the fixed tool list, ADR-0017 rule 11) intersected with the rights of the human it acts for, re-evaluated at every call. Agent types get no role assignments. The human's owner scope binds the run, as their record scope does (a note on ADR-0050 rule 31).
    - **Integrations** keep ADR-0017 rule 13, with roles and record scope and no owner scope.
    - **Never.** No role or level lets an agent approve (ADR-0017 rule 15), receive a delegation (rule 21), or run a `human_only` command.

    Note: the agent type's declared permissions and its fixed tool list are one set, and the agent type also declares field classes (default none) and no record scope ([ADR-0050](0050-agent-runtime-and-query-layer.md) rule 12 note).

**Segregation of duties**

17. The catalog [segregation-rules.csv](../catalogs/segregation-rules.csv):
    - **Columns:** `code`, `side_a` and `side_b` (lists of permissions), `document_relation`, `meaning`, `added_in`.
    - **Document relations:**
      - `none`: checked at assignment only;
      - `referenced_order`: the side-B document has lines that reference lines of the side-A document;
      - `settled_item`: the side-B document settles an open item that the side-A document created;
      - `bank_account_used`: the side-B payment uses a partner bank account whose latest change the person wrote or approved.
    - **Seeded rules:**

      | Code | Side A | Side B | Relation |
      | --- | --- | --- | --- |
      | `bank_account_vs_payment` | maintain partner bank accounts | post or approve cash and bank payments | `bank_account_used` |
      | `purchase_order_vs_goods_receipt` | create, change or approve purchase orders | post goods receipts | `referenced_order` |
      | `purchase_invoice_vs_payment` | post or approve supplier invoices | post cash and bank payments | `settled_item` |
      | `price_list_vs_sales_approval` | maintain price lists | approve quotations and sales orders | `none` |
      | `partner_vs_purchase_invoice` | create or change partners | post supplier invoices | `none` |
      | `role_administration_vs_posting` | change roles and assignments | post journal entries, payments and supplier invoices | `none` |

    - **Company enablement.** `company_segregation_rule` (rule code, `is_enabled`, `basis`). Every catalog rule is enabled at company setup. `EnableSegregationRule` and `DisableSegregationRule` are `human_only` and change-tracked.
    - **Price list rule.** Permissions cannot see "below cost", so the rule separates maintaining prices from approving sales at all. The below-cost check itself stays a policy condition (ADR-0043 rule 3).
    - **Catalog names.** CI checks that every permission in the catalog is registered.

    Note: the seeded templates other than `owner` hold no both sides of these rules (rule 11 note).

    Note (catalog review, 2026-11-15): assignments of the `owner` template are exempt from the checks that keep mode `block` free of conflicts (rule 18: the switch to `block`, `EnableSegregationRule` and every rights path; INV-229), because that template holds every permission (rule 12) and would otherwise make `block` impossible in any company. The owner still meets rule 19's per-document check: one person cannot act on both sides of a pair on one document. A user whose other assignments hold both sides is not exempt (lab t12, E5b and E5c).

    Note (simulation review, 2026-11-15): the exemption covers assignments only. It never reaches approval eligibility: [ADR-0055](0055-approval-pools-and-stages.md) rule 7, condition 7, applies to the owner on each document like anyone else, through rule 19's check for the rules with a document relation (`bank_account_vs_payment`, `purchase_order_vs_goods_receipt`, `purchase_invoice_vs_payment`). The rules with relation `none` (`price_list_vs_sales_approval`, `partner_vs_purchase_invoice`, `role_administration_vs_posting`) are checked at assignment only, for everyone, so they bar no one from approving a given document; the simulation's refusal of the owner's quotation approval under `price_list_vs_sales_approval` (trace 3.20) was not what rule 19 says.
18. Check on every change of rights:
    - **When.** On every path that changes a person's effective rights: `CreateRoleAssignment`, `UpdateRoleAssignment`, `UpdateRole` (for every holder), `EnableUserAccount`, `CreateDelegation` of both kinds (the substitute's own rights plus what is lent), `ConfirmUserInvitation` (the pending assignments), `ConfirmRolePermissionHold` (every holder of the role), `EnableSegregationRule` (for every user), and the re-expansion on upgrade (rule 9).
    - **The test.** A rule conflicts when the union of a user's permissions from assignments and delegations in force on any common day holds at least one permission of each side.
    - **The company setting** `permissions.segregation_assignment_mode`: `warn` gives the check result `segregation_conflict_found`; `block` gives the error `segregation_conflict`, except on upgrade, where the gain becomes a hold (rule 9). Interim default `warn` (flagged), so that small teams can start.
    - **Switching to `block`** is refused with `segregation_conflict` while any current assignment or delegation conflicts, so `block` always starts from a clean state. With every path above checked, no conflict exists while the mode is `block` (INV-229). Settings with the prefix `permissions.` belong to the leaf `segregation_rule` at level `full`, not to `company_setting`.
    - **Review.** `ListSegregationConflict` lists the current conflicts per user, for owners and auditors.
19. Check on one document, at command time, for rules with a document relation:
    - **The test.** Before a side-B permission runs on a document, the dispatcher asks the related-documents function for the documents linked by the rule's relation, and the document-actors function for who acted on them. If the acting human performed a side-A command on a related document, the command is refused with `segregation_of_duties`, with the rule and the related document in `details`. The same holds the other way round, A after B.
    - **The acting human** is the human actor, or the `on_behalf_of` of a non-human actor, and also the delegator when a substitute acts (rule 21).
    - **Always on.** It applies in both assignment modes, and in simulation. ADR-0017 rule 16 and ADR-0055 rule 7 are separate and unchanged.

    Note (flow review, 2026-11-15): the minimum cast of a purchase-to-pay run with a mismatched supplier invoice, under these rules and the seeded templates (rule 11 note), is three finance users: A (an accountant) drafts and posts the invoice; B, an eligible approver of the `po` pool's current stage other than A, who wrote it ([ADR-0055](0055-approval-pools-and-stages.md) rule 7), approves it; C (a cashier) posts the payment, because `purchase_invoice_vs_payment` refuses A and B. Whoever last changed the supplier's bank account (by default the owner) may neither post nor approve that payment (`bank_account_vs_payment`), and whoever wrote or approved the purchase order may not post its goods receipt (`purchase_order_vs_goods_receipt`), so a warehouse keeper does. [DS-17](../design/DS-17-synthetic-dataset.md)'s `vn_*` profiles seed this cast (its rule 18 note).
20. Small companies (open question, flagged for the author: ADR-0017 rule 17):
    - **The mode.** Company setting `permissions.small_company_mode`, changed by `EnableSmallCompanyMode` and `DisableSmallCompanyMode` (`human_only`; level `full` on `segregation_rule`).
    - **The bound.** Only while at most two active users hold any permission of effect class `posting` or any approval permission in the company; otherwise `small_company_mode_not_allowed`. While it is on, every path of rule 18 that would make a third such user is refused with `small_company_mode_active`, and the upgrade turns the gain into a hold (rule 9). INV-223 checks the bound.
    - **What it relaxes:**
      - the assignment check of rule 18 is skipped;
      - a refusal of rule 19 becomes a recorded exception: the command runs and writes a `segregation_exception` row (rule, user, command, document, related document, audit record);
      - ADR-0055 rule 7's exclusion of a document's own writers is lifted for humans, with an exception row.
    - **What it never relaxes:** the hard floor that the human who triggered an agent never approves that agent's drafts (ADR-0017 rule 16; spec 03 rule 5), that one person counts in one stage only (ADR-0055 rule 7), and `human_only`.
    - **Compensating controls:**
      - every exception appears in `ListSegregationException`, the owner review report;
      - the first exception of a posting period raises one `segregation_review_due` work item for `company_owner`, with the period as its open key, due at period end; later exceptions of the period add evidence to it. `permissions` raises it in the command's transaction and finds the period through the period resolver (rule 2);
      - `ConfirmSegregationReview` resolves it and writes a `segregation_review` row (period, count, who, when);
      - every exception is in the audit log (ADR-0038).
    - **The gap.** In a one-person company the owner reviews their own actions, which is weaker than four eyes. Whether the mode is acceptable, and whether the review must block the period lock, is for the author.

    Note: interim, flagged for the author: the mode never lifts [ADR-0029](0029-proposals-and-agent-safety.md) rule 4's bank-account rule either; a bank account proposal is approved by a human who wrote no version of it (open question).

**Delegation**

21. `delegation` (company data, change-tracked):
    - **Columns:** `delegator_user_id`, `substitute_user_id`, `kind` (`approval` or `role_assignments`), `start_date`, `end_date` (inclusive, at most 366 days), `reason`, `state` (`active`, `canceled`), `created_by_user_id`. `delegation_role_assignment` lists the delegated assignments of kind `role_assignments`.
    - **Never to an agent.** The substitute is a user account, which no agent has, and every command that uses a delegation must come from a human actor.
    - **Other checks** (`delegation_invalid`): not to oneself; the substitute is active and holds an assignment in force in the company; the listed assignments belong to the delegator; delegated authority cannot be delegated again; and when a delegated role, or a role whose approvals are lent, has `is_totp_required`, the substitute has TOTP enabled (and rule 4 then requires it at sign-in).
    - **Segregation.** `CreateDelegation` of either kind runs rule 18's check on the substitute's own rights plus what is lent.
    - **In force** when `state` is `active`, `start_date` ≤ `clock.today` ≤ `end_date`, and the delegator is active. It lends only what the delegator holds on that day, so a delegator who loses a right loses it for the substitute too.
    - **Kind `approval`.** The substitute is eligible wherever the delegator is directly eligible in an approval stage (ADR-0055 rule 7). The delegator's `Approve` and `Reject` permissions and the read of the subject are lent with the delegator's scope.
    - **Kind `role_assignments`.** The listed assignments act as the substitute's own, with the delegator's record scope and with owner scope evaluated as the delegator. The author asked for approval delegation only; whether this kind stays is an open question.
    - **Commands.** `CreateDelegation` by the delegator, which every approving template allows (rule 11); for an absent user, by a holder of `delegate_for_others` who also holds what is delegated (no escalation). `CancelDelegation` ends it early. Both are `human_only`.
    - **Audit.** A command executed under a delegation records `delegated_from_user_id` in its audit record (a note on ADR-0038 rule 2) and, for approvals, in the approval row (ADR-0055 rule 9).
    - **The delegator** keeps their own rights during the window.

**UI**

22. Screens and queries (ADR-0040):
    - **Role editor:** a hand-built screen (DS-30). Rows are the area tree, columns the five levels and "approve". It shows inherited values, and the plan of `UpdateRole` gives the permissions gained and lost before execution.
    - **Assignment form:** principal, role, record scope, owner scopes (defaulting to the role's suggestions), field classes, dates.
    - **`ListAllowedCommand`** keeps its interface. Its checks read the expanded permissions, the owner scope (outside it the subject is `record_not_found`), delegations, the segregation checks of rule 19, and for `Approve` the stage eligibility of ADR-0055 (a note on ADR-0040 rule 8).
    - **`GetSessionContext`** also returns owner scopes and the delegations in force (a note on ADR-0040 rule 12).

**Commands and queries**

23. Registration:
    - **`permissions` commands:** `CreateUserAccount`, `ConfirmUserInvitation`, `CancelUserInvitation`, `UpdateUserAccount`, `DisableUserAccount`, `EnableUserAccount`, `ClearUserAccountLockout`, `CreateCredentialReset`, `CreateRole`, `UpdateRole`, `ConfirmRolePermissionHold`, `IgnoreRolePermissionHold`, `CreateRoleAssignment`, `UpdateRoleAssignment`, `CreateDelegation`, `CancelDelegation`, `EnableSegregationRule`, `DisableSegregationRule`, `EnableSmallCompanyMode`, `DisableSmallCompanyMode`, `ConfirmSegregationReview`.
    - **`master_data` commands:** those of rule 6, `UpdateEmployeeOrganization` included.
    - **All of them** are `human_only`, effect class `master_data_change` (`other` for `ClearUserAccountLockout`, `CreateCredentialReset`, `CancelUserInvitation` and `ConfirmSegregationReview`), change-tracked, and on no agent tool list. They are not proposal-bound: an agent cannot propose access changes.
    - **Queries:** `ListUserAccount`, `GetUserAccount`, `ListUserInvitation`, `ListPendingUserInvitation` (the caller's own, across companies), `ListRolePermissionHold`, `ListRole`, `GetRole`, `ListRolePermission`, `ListRoleAssignment`, `ListDelegation`, `ListAuthorizationArea`, `ListSegregationRule`, `ListSegregationConflict`, `ListSegregationException`.
    - **Verbs.** Enable and Disable extend to user accounts, segregation rules and the small-company mode; Cancel to delegations and invitations; Clear to a lockout; Confirm to an invitation (the invited person confirms they are the one meant) and to a held permission (a person accepts what the upgrade produced); Ignore to a held permission (glossary notes). No new verb is needed here; Verify comes from ADR-0052.

**Obligations of earlier ADRs**

24. Answers to the DS-15 items earlier ADRs left open:
    - **ADR-0004 rule 16, ADR-0013 rules 14 and 16, ADR-0014 (journal RLS):** answered by ADR-0017 rules 18–19; nothing to add.
    - **ADR-0008 rules 2, 5, 8, 12:** answered by ADR-0017, completed by rules 8–16 here (levels, owner scope, field filtering unchanged).
    - **ADR-0009 (who may submit, approve and post; segregation):** levels (rule 8), the approval flag (rule 9), segregation (rules 17–20) and ADR-0055.
    - **ADR-0011 (permission to enter manual rates):** the leaf `exchange_rate` under Finance; `CreateExchangeRate` needs `edit` there. Templates `chief_accountant` and `accountant` have it.
    - **ADR-0012 (chief-accountant role, period states, close tasks, `fiscal_calendar_owner`):** `post_in_soft_locked_period` is `full` on `posting_period`, held by templates `owner` and `chief_accountant`. Restrict and Open need `post`, Lock and Unlock `full`, on the same leaf; close jobs are `Run` on `costing_run` and `close_checklist`. The calendar owner stays a company column (ADR-0012 rule 3).
    - **ADR-0016 (operator loads packages; who chooses regime options):** loading stays with the `operator` installation role. Regime options are the leaf `regime_option` under Finance, at level `full`.
    - **ADR-0019 (field labels with row conditions; field classes):** field classes stay `cost` and `margin`. Labels with row conditions are data labels for LLM routing (spec 17; DS-32), not permissions.
    - **ADR-0034 rule 18 (a shop-floor role template):** `shop_floor_lead`.
    - **ADR-0044 rule 11 ("a holder of the `chief_accountant` role" accepts a migration difference):** that test would break when a company renames roles, as ADR-0017 rule 2's did. `AcceptMigrationDifference` is a permission on the leaf `opening_balance_entry` with the declared minimum level `full` (rule 8), so Finance `full` holds it: templates `owner` and `chief_accountant`, not `accountant`. A note on ADR-0044 rule 11.
    - **ADR-0049 rules 17, 20, 26 (permissions of reporting and printing):**
      - on `report_finance`: `GetStatutoryReport`, `ListBookRow`, `ListReportLineContribution`, `ListReportDefinition`, `GetReportDefinition`, `ListStatutoryReportFiling`, `GetStatutoryReportFiling`, `ListReportComparativeValue` (`read`); `RenderReport` (`read`, Render); `CreateReportDefinition`, `UpdateReportDefinition`, `CreateReportComparativeValue`, `UpdateReportComparativeValue`, `DeleteReportComparativeValue` (`edit`); `FileStatutoryReport` (`post`);
      - on `report_tax`: `RenderTaxReturn` (`read`); `FileTaxReturn` (`post`, ADR-0041 rule 18); `RunTaxReturnOffset` (verb `Run`, effect class `posting`; the period-end tax offset job of ADR-0049 rule 23, holistic review 2026-11-15);
      - on `general_access`: `RenderPrint`, `GetPrintData`, `GetRenderJob` and `ListRenderJob` (`read`), so everyone may print, and see the print data of, what they may read; `RenderPrint` and `GetPrintData` check the subject's own `Get<Type>` and read scope (record and owner scope), and refuse otherwise as `Get<Type>` would (ADR-0049 rules 20, 25);
      - on `print_template`: only templates and print data contracts, which hold no document data: `CreatePrintTemplate`, `UpdatePrintTemplate` (`edit`), `GetPrintDataContract` (`read`), and the render worker's `RecordRenderOutcome` (declared `full`, system only). So `print_template` never lets an IT administrator or an auditor read a document's content;
      - on `print_profile`: `CreatePrintProfile`, `UpdatePrintProfile` (`edit`), held only by `owner`;
      - templates: the reporting queries go to `owner`, `chief_accountant` and `accountant`, as ADR-0049 rule 17 says, and also to `auditor`, read-only; `FileStatutoryReport` and `FileTaxReturn` to `owner` and `chief_accountant`. A note on ADR-0049 rule 17 lists these.
    - **Backlog DS-15 (`on_behalf_of` and segregation for scheduled and e-mail runs):** ADR-0017 rules 12 and 16 stand: the owner of the schedule or intake is the human acted for, so that person never approves the run's drafts.
    - **Backlog DS-15 (teams of one or two):** rule 20, flagged, and ADR-0055 rule 20's walk-throughs.
    - **Still open:** integrations and `human_only` (ADR-0008 rule 2), TOTP for every user, and the small-company questions (ADR-0017 rule 17).

    Note: agent and platform commands whose leaf no rule stated ([ADR-0050](0050-agent-runtime-and-query-layer.md) rules 14–20; [ADR-0013](0013-outbox-and-events.md) rules 8, 16; [ADR-0029](0029-proposals-and-agent-safety.md) rules 8, 13; [ADR-0038](0038-audit-and-observability.md) rule 13; [ADR-0043](0043-policy-and-approval.md) rule 18; [ADR-0055](0055-approval-pools-and-stages.md) rule 17):

    | Command, query or capability | Leaf | Level | Flags |
    | --- | --- | --- | --- |
    | `start_agent:<agent_type>` | `agent_<agent_type>` | `edit` | capability |
    | `StartAgentRun` | none: its check is `start_agent:<agent_type>` of the payload's agent type, held by the human actor or, for `system` from a wake-up or schedule, by the human acted for | — | `other`; on no tool list |
    | `CancelAgentRun` | none: `start_agent:<agent_type>` of the run's agent type, or `cancel_agent_runs` | — | `other`; on no tool list |
    | `cancel_agent_runs` | `agent` | `full` | capability; replaces "or the company's owner" |
    | `UpdateAgentTypeSetting` | `agent` | `full` (declared) | `master_data_change`, `is_proposal_bound`, on no tool list; the resulting `workflow_owner_id` must hold `start_agent:<agent_type>` (`workflow_owner_not_permitted`) |
    | `CreateAgentPromotionEvidence` | `agent` | `edit` | `other`; a person's command; on no tool list |
    | `GetAgentTypeSetting`, `GetAgentShadowEvaluation`, `ListAgentRun`, `GetAgentRun` | `agent` | `read` | bodies need `read_agent_run_bodies` |
    | `CompleteAgentRun`, `RunAgentQualityCheck` | `agent` | — | `is_internal_only` |
    | `ClearTaint` | `policy` | `full` | `human_only` |
    | `ConfirmAutoPost` | `policy` | `post` | only the rule's owner (ADR-0043 rule 14) |
    | `ListPolicyDecision` | `policy` | `read` | — |
    | `RunApprovalEscalation` | `policy` | — | `is_internal_only` |
    | `GetApprovalProgress` | `general_access` | `read` | checks the document's own `Get<Type>` and read scope, like `GetPrintData` |
    | `CreateAttachment` | `general_access` | `edit` | linking the file to a record needs that record's own `Update` |
    | `CreateListExport` | `general_access` | `edit` | its consumer pages the exported query as the requester, so that query's permission and scope apply; on no tool list |
    | `RetryEventDelivery`, `SkipEventDelivery` | `event_delivery` | `post` | `human_only`; deliveries with a company; installation deliveries stay the operator's |
    | `ReplayEvents` | `event_delivery` | `full` | `human_only` |

**Catalogs and lab**

25. Catalog rows:
    - **New catalogs:** `authorization-areas.csv`, `authorization-verb-levels.csv`, `role-templates.csv`, `role-template-levels.csv`, `segregation-rules.csv`, listed in the catalogs README with owner DS-15.
    - **Errors:** `user_account_locked` (unauthenticated), `grant_exceeds_own_rights`, `segregation_conflict` and `organization_self_change` (permission), `role_assignment_invalid`, `delegation_invalid`, `department_cycle`, `employee_manager_cycle`, `employee_organization_command_required` (validation), `last_owner_required`, `user_shared_across_companies`, `small_company_mode_not_allowed`, `small_company_mode_active` (precondition). `segregation_of_duties` also covers rule 19.
    - **Check result:** `segregation_conflict_found`.
    - **Work item kinds:** `segregation_review_due` (`permissions`, subject `posting_period`, owner `company_owner`, due `period_end`, resolved by `ConfirmSegregationReview`); `role_permission_held` (`permissions`, subject `company`, owner `company_owner`, due `days:7`, resolved by the system when no hold is `held`).
    - **Settings (company):** `permissions.segregation_assignment_mode` (`warn`), `permissions.small_company_mode` (false). **Installation:** `invitation_expiry_days` (30).
    - **Invariants**, first at step 5 (block INV-220 to INV-239; INV-216 to INV-219 are unused gaps, reserved by no design item):
      - **INV-220:** every role's `role_permission` equals the expansion of its levels under the current registry minus the role's holds in force (`held` or `ignored`), and `expansion_hash` matches the stored list;
      - **INV-221:** every user assignment with owner scope `branch` has a record scope, every one with `company` has none, the edit scope is not wider than the read scope, and no other assignment has an owner scope;
      - **INV-222:** every command audited with `delegated_from_user_id` lies inside a delegation in force from that user to the actor on that day, of a kind that covers the command;
      - **INV-223:** while `permissions.small_company_mode` is on, at most two active users hold a posting or approval permission, and every `segregation_exception` was recorded while the mode was on;
      - **INV-227:** every name or e-mail change, credential reset and lockout clearance of a user account was executed by an operator, or by a company caller when the user was linked to that company and to no other on that day; every such name or e-mail change and reset by a company caller was made by one who held every permission the user held in the company; no consumed reset changed `is_totp_enabled`; every session of the user created before a consumed reset is revoked; and no reset token issued by a company was used after its user became shared;
      - **INV-228:** every recorded change of `employee_profile.department_id`, `manager_partner_id` or `user_account_id` belongs to an `UpdateEmployeeOrganization` audit record;
      - **INV-229:** while `permissions.segregation_assignment_mode` is `block`, no user's permissions in force on any day hold both sides of an enabled segregation rule;
      - **INV-231:** no role assignment naming an invitation was in force before that invitation was confirmed by its own user (the actor of `ConfirmUserInvitation`), unless it created a new account, and none naming a pending, canceled or expired invitation is in force; and every user assignment that was its user's first link to a company (no current or future link there when it was created) names a confirmed invitation, except the bootstrap owner's.
    - **Edge cases** (block EC-110 to EC-129; EC-97 to EC-109 follow the reporting block of ADR-0049, which starts at EC-92 and takes what it needs, and this ADR uses none of them): EC-110, an owner-scoped sales clerk and their manager; EC-111, a user who holds both the buyer and the warehouse keeper role writes a purchase order and then tries to post its goods receipt; EC-116, an IT administrator of one company tries to reset the password of a user shared with another company; EC-118, two people, one login: a company invites an existing login meaning someone else, and the account's owner never gains or loses anything.

    Note: INV-216 is now [ADR-0050](0050-agent-runtime-and-query-layer.md)'s (rule 55 note); INV-217 to INV-219 stay unused.

    Note (catalog review, 2026-11-15): corrected: the reporting block of [ADR-0049](0049-statutory-reporting-and-printing.md) is EC-92 to EC-98; EC-99 and EC-100 are CRM rows of [ADR-0052](0052-minimal-crm.md); EC-101 to EC-109 are unused. This ADR's block is EC-110 to EC-129, of which EC-110 to EC-118 are taken (with ADR-0055's).
26. Lab check `t12_access.py` ([validation lab](../reviews/2026-11-14-design-validation/README.md)), on DS-15-access.sql loaded with DS-20 and DS-06:
    - the field counts of every catalog file it reads, and every glossary verb against the verb catalog;
    - level expansion: inheritance and overrides, verbs against effect classes, declared minimum levels, the approval flag, capabilities, the templates' delegation and agent run body rights, and the same set for shuffled inputs;
    - owner scope filtering `own`, `team`, `department` (manager subtree and reporting chain), `branch` and `company` on real rows, and the database's refusal of inconsistent scope pairs and of agent type assignments;
    - pending invitations (two people colliding on one login; a former user whose ID the company still knows; confirmation only by the invited user; expiry), linked and shared users, the operator path, the no-escalation rule and its lockout exemption, and a reset that keeps TOTP, revokes sessions and is voided when the user becomes shared, on real rows;
    - permission holds on upgrade: the stored set is the expansion minus the holds, and granting re-runs the checks;
    - the organization guard: `UpdatePartner` refused on the three columns, `full` required, and no self-change by effect on real rows (a manager set to the caller, employees moved into the caller's department, a department reparented under the caller's), with the company-scope exemption;
    - a leaf for every CRM command and query of ADR-0052 and every reporting and printing command and query of ADR-0049, the print profile kept to `owner`, and no report leaf for the cashier;
    - a segregation pair blocking one document, warn and block on every rights path, the delegation checks, and the small-company exception and bound;
    - the delegation window;
    - `company_id` on every company table of the file;
    - the approval engine of ADR-0055 (its rule 19).

    The result is recorded as the next lab finding of the validation lab README.

    Note: the lab also checks that `is_internal_only` commands are in no template's expansion, the interim `start_agent` seed, and the leaves of rule 24's table note.

## Context

ADR-0017 designed only what the dispatcher needed at step 0 and left the full model to step 5, with DS-28. Runbook steps 5–9 list "full permissions with segregation of duties" as step 5 work. The author asked (2026-11-15) for users, roles and authorizations in the style of SAP Business One.

**Business One's model,** studied for its concepts:
- **General authorizations:** a tree of forms and functions with "Full", "Read only" and "No authorization" per user.
- **Data ownership:** documents visible by owner, with manager, team, department and branch options.
- **Approval procedures and stages:** separate from authorizations (ADR-0055).
- **Users** linked to employees with departments and managers.

S/4HANA uses authorization objects with field values inside roles, too fine-grained for an SME and for an agent to reason about.

**What ERPMe keeps.** Permissions remain command and query names, generated from the registry (ADR-0017 rule 4), because agents call commands and the dispatcher checks names. The levels are a way to store and edit those permissions, not a second model. Business One's three levels are too coarse for a system where posting is a separate, auditable step, so `read`, `edit`, `post` and `full` split it the way ERPMe's lifecycle splits it (ADR-0009). Approval is a separate flag, as in Business One, where approval stages are not authorizations.

**Account takeover and escalation.** One account serves several companies, and owner scope depends on organization data. Both are paths around the permission check if a company can change another company's user credentials, or a person can change their own place in the organization. Rules 3 and 6 close them: an existing login is only invited and must confirm, shared accounts are an operator's, credential commands need every right of the target, and organization commands are refused when they would change the caller's own reach.

**Small companies.** The backlog asks for rules for accounting teams of one or two people (DS-15), and ADR-0017 rule 17 left them open. Segregation rules that only block would leave such companies unable to work. An exception mode with an owner review is how auditors usually accept such companies, but whether it is acceptable here is the author's (ADR-0005).

## Options considered

| Option | For | Against |
| --- | --- | --- |
| Levels per tree node, expanded into permission names (chosen) | Business One's matrix for people; one permission path for the dispatcher and agents; deterministic | A verb catalog to keep; levels cannot express a single command |
| Store permission lists in roles (ADR-0017 as it was) | Exact | Hundreds of names per role; upgrades need manual proposals |
| Authorization objects with field values (S/4HANA) | Very fine-grained | Too complex for SMEs and for agents to reason about |
| Three levels as in Business One | Familiar | "Full" would mix drafting and posting, which ERPMe separates |
| Approve inside `full` | Fewer columns | An approver would also get edit and reverse rights; Business One separates approval |
| Owner scope beside record scope (chosen) | Data ownership as in Business One; record scope unchanged | Two filters to combine, and every side path must follow both |
| Owner scope in row-level security | Second line for owners too | Org data changes per request; RLS stays company-only by ADR-0017 rule 19 |
| Owner evaluated from live organization data (chosen) | Transfers take effect at once | A document's visibility can change without the document changing |
| Department stamped on each document | Visibility never changes | Stale after transfers; a second copy of org data |
| User groups for routing | Business One has them | A second grouping beside roles, departments and teams |
| Link an existing login at once | One step | A company could attach anyone's account by guessing a login, and would learn that it exists |
| Invite an existing login, confirmed by its owner (chosen) | The account's owner decides; the company learns nothing it did not type | One more step for a person who works for two companies |
| Hold upgrade gains that break `block` or the small-company bound (chosen) | Upgrades never create a conflict; a person decides each gain | A hold table and a work item |
| Agent types with role assignments as a third set | Per-company limits on an agent type | A second place to grant agent rights beside the tool list; ADR-0050 rule 31 already bounds agents |
| Segregation by catalog pairs, on every rights path and per document (chosen) | Common audit practice; per-document checks catch the actual fraud path | Needs related-documents functions per type |
| Segregation by assignment only | Simple | Blocks small teams or is switched off; misses the per-document case |
| Small-company exception mode with review (chosen, flagged) | Small companies can work; every exception is visible | Weaker than four eyes; the author's decision |

## Constraints that come with the decision

- **ADR notes:**
  - ADR-0017 rules 2, 5, 6, 8, 9, 11, 17, 19: the invited person's commands and the pending list; TOTP by role flag; templates; owner scope and delegation; owner scope as a further dimension; agent rights unchanged, bound by the human's owner scope; the small-company mode;
  - ADR-0008 rule 1: each command, query and capability declares its leaf and optionally a minimum level; aggregating queries declare `is_owner_scoped`;
  - ADR-0009 rules 1, 2: `owner_employee_id`, `created_by_user_id` and `owner_field`;
  - ADR-0019 rule 15: `role:sales_clerk`;
  - ADR-0022 rule 2: the registered functions of rule 2;
  - ADR-0026 rule 15: open items follow their origin document; `GetPartnerExposure` is `is_owner_scoped: false`;
  - ADR-0029 rule 1: change proposals refuse the organization columns;
  - ADR-0038 rules 2, 7, 14: `delegated_from_user_id`; audit queries and attachments follow owner scope;
  - ADR-0040 rules 8, 12, 13: `ListAllowedCommand` checks and the password endpoint; session context; the live-update header follows owner scope;
  - ADR-0042 rules 7, 10: owner rules by `template_code`; work item visibility follows owner scope;
  - ADR-0044 rule 11: `AcceptMigrationDifference` by permission;
  - ADR-0045 rule 11: employee department and manager, `user_account_id` unique per company, changed only by `UpdateEmployeeOrganization`;
  - ADR-0049 rules 17, 20: the leaves and templates of its commands and queries; print files follow owner scope;
  - ADR-0050 rules 20, 31: the leaf `agent_run_bodies`; owner scope binds agent runs;
  - ADR-0051 rule 30: `role:sales_clerk`;
  - ADR-0052 rules 18, 20: document entries of the timeline also need read owner scope; the owner rule `role:sales` resolves as `role:sales_clerk`;
  - ADR-0034 rule 18: the shop-floor template.
- **DDL:** [DS-15-access.sql](../design/DS-15-access.sql) (new; with `user_invitation` and `role_permission_hold`); [DS-20-master-data.sql](../design/DS-20-master-data.sql): `employee_profile.department_id`, `manager_partner_id`, the unique key.
- **DS-04:** the errors and check result of rule 25.
- **Catalogs:** the five new catalogs; INV-220 to INV-223 and INV-227 to INV-229; edge cases; `segregation_review_due`; owner rule `role:sales_clerk`.
- **Other design items:**
  - DS-16: the invariants and a property test that the expansion is deterministic;
  - DS-18: encryption of TOTP secrets, session settings, operator re-enrolment of TOTP;
  - DS-20: `CreatePartner` and `UpdatePartner` refuse the organization columns;
  - DS-26: `is_owner_scoped` on reports;
  - DS-30: role editor, assignment and delegation screens;
  - DS-33: owner scope in the read-only views, `company_user`;
  - DS-37: re-expansion of roles on upgrade, with permission holds.
- **Open questions:** template contents and owner scope defaults; the assignment mode default; the small-company mode; delegation of kind `role_assignments`; upgrades that grant new commands inside a leaf automatically; TOTP and integrations stay open.

## Revisit when

- A company needs a single command without its leaf, or a record-scope dimension beyond branch and warehouse.
- Routing needs a set of people that no role, department or team expresses.
- The author decides the small-company questions.

## Documents updated

- **The DDL draft:** [docs/design/DS-15-access.sql](../design/DS-15-access.sql) (new); [docs/design/DS-20-master-data.sql](../design/DS-20-master-data.sql).
- **The lab:** [docs/reviews/2026-11-14-design-validation/](../reviews/2026-11-14-design-validation/README.md): `lab/t12_access.py`.
- **ADRs:** notes in ADR-0008, ADR-0009, ADR-0017, ADR-0019, ADR-0022, ADR-0026, ADR-0029, ADR-0034, ADR-0038, ADR-0040, ADR-0042, ADR-0044, ADR-0045, ADR-0049, ADR-0050, ADR-0051 and ADR-0052.
- **Design files:** [docs/design/DS-04-command-envelope.md](../design/DS-04-command-envelope.md), [docs/design/backlog.md](../design/backlog.md).
- **Catalogs:** [authorization-areas.csv](../catalogs/authorization-areas.csv), [authorization-verb-levels.csv](../catalogs/authorization-verb-levels.csv), [role-templates.csv](../catalogs/role-templates.csv), [role-template-levels.csv](../catalogs/role-template-levels.csv), [segregation-rules.csv](../catalogs/segregation-rules.csv) (new); [invariants.csv](../catalogs/invariants.csv), [edge-cases.csv](../catalogs/edge-cases.csv), [work-item-kinds.csv](../catalogs/work-item-kinds.csv), [README.md](../catalogs/README.md).
- **Glossary:** [docs/spec/00-reading-guide.md](../spec/00-reading-guide.md).
- **Open questions:** [docs/open-questions.md](../open-questions.md).
- **Index and log:** [docs/adr/README.md](README.md); [docs/runbook/step-log.md](../runbook/step-log.md) at acceptance.
