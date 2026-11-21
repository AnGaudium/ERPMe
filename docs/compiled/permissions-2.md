Module: permissions    Chunk: 2 of 4    Source ADRs: ADR-0029, ADR-0040, ADR-0054
Build step(s): 4, 5, 9    Generated from index: 30d5706    Compiled by: Claude Fable 5.2, 2026-11-21

# `permissions` compiled spec, chunk 2: ownership, user accounts, authentication, transport, authorization areas, levels and role expansion

## Purpose

This chunk states the part of `permissions` law on: what the module owns and the functions modules register for access decisions, user accounts and invitations, authentication and password resets, the session transport, the rights of consumers of agent-origin events, the authorization area tree, the level a permission needs, and the expansion of role levels into stored permissions with its upgrade holds. `permissions` is layer 2 (ADR-0022.R2). The permission envelope of ADR-0017 is in chunk 1; roles, templates, assignments, owner scope and segregation are in chunk 3; the small-company mode, delegation and the catalogs are in chunk 4.

## Entities and tables

DDL: `docs/design/DS-15-access.sql`. The ADRs win where the DDL draft disagrees (R202).

| Table | Meaning | Key | Parent | Owner |
| --- | --- | --- | --- | --- |
| `user_account` | One person's account; installation data, label `personal` (R208, R222) | `id`; `login` unique; (`oidc_issuer`, `oidc_subject`) unique | none | `permissions` |
| `user_session` | Server-side session of a user (R227) | `id`; `token_hash` unique | `user_account` | `permissions` |
| `credential_reset` | One-time password reset token, stored as a hash (R225) | `id`; `token_hash` unique | `user_account` | `permissions` |
| `user_invitation` | A company's invitation of a login, with what the company typed (R210-R215) | `id`; (`company_id`, `id`) | `company`, `user_account` | `permissions` |
| `role_level` | One level and approval flag per role and node of the area tree (R242) | `id`; (`role_id`, `authorization_area`) unique | `role` | `permissions` |
| `role_permission` | The stored expansion of a role minus its holds in force (R244, R246) | `id`; (`role_id`, `permission`) unique | `role` | `permissions` |
| `role_permission_hold` | A permission an upgrade held back for a role (R246) | `id`; (`company_id`, `id`) | `company`, `role` | `permissions` |

Named by rules of this chunk, with their rows in other chunks: `role`, `role_assignment`, `role_assignment_scope`, `delegation`, `integration_client`, `integration_token`, `installation_role_assignment`, `company_segregation_rule`, `segregation_exception`, `segregation_review`.

Reads: `company`, `branch`, `warehouse`, `department`, `team`, `team_member`, `employee_profile` (`master_data`); `posting_period` (`periods`); `document_version`, `approval` (`documents`); `audit_record` (`audit`); `work_item` (`work`).

## Commands and queries

Authorization: the user commands are on the leaf `user_account` and the hold commands on the leaf `role` (catalog `authorization-areas.csv`, under `administration`). The level of a command is that of R236 to R238 (`Create`, `Update`, `Ignore`: `edit`; `Confirm`: `post`; `Clear`, `Enable`, `Disable`: `full`; queries: `read`). The sources state no event for these commands.

| Name | Actor / authorization | Input | Effect | Events | Error codes |
| --- | --- | --- | --- | --- | --- |
| `CreateUserAccount` | company-scoped; leaf `user_account` | exact `login`, display name, e-mail; in one batch with the first `CreateRoleAssignment` | Writes a `user_invitation`; creates the account when the login is new (R210, R211) | not stated | not stated |
| `UpdateUserAccount` | leaf `user_account`; conditions of R217 and R218 | name, e-mail, language, time zone | Changes them (R216) | not stated | `record_not_found`, `user_shared_across_companies`, `grant_exceeds_own_rights` |
| `DisableUserAccount` | leaf `user_account`; conditions of R217 | user | Disables; revokes sessions and tokens, suspends owned schedules and intakes, raises `owner_suspended` (R216) | not stated | `record_not_found`, `user_shared_across_companies` |
| `EnableUserAccount` | leaf `user_account`; conditions of R217 | user | Enables the account (R216) | not stated | `record_not_found` |
| `ConfirmUserInvitation` | `human_only`; company-scoped; the caller is the invitation's user, no leaf (R213) | invitation | Pending assignments come into force through the checks of ADR-0054.R18 | not stated | not stated |
| `CancelUserInvitation` | the invitation's user, or the company's administrator with `edit` on `user_account`, while pending (R213) | invitation | The invitation is `canceled`; its assignments never come into force | not stated | not stated |
| `ListPendingUserInvitation` | registered cross-company query; any valid credential; the caller's own rows (R214) | none | Lists the caller's pending invitations | none | not stated |
| `CreateCredentialReset` | leaf `user_account`; conditions of R217 and R218 | user | Makes a one-time token and returns the link once (R225) | not stated | `record_not_found`, `user_shared_across_companies`, `grant_exceeds_own_rights` |
| `ClearUserAccountLockout` | leaf `user_account`; conditions of R217 | user | Ends a lockout early (R223) | not stated | `record_not_found`, `user_shared_across_companies` |
| `ConfirmRolePermissionHold` | `human_only`, `master_data_change`; leaf `role`; the caller holds the permission (R247) | hold | Grants the held permission after the checks of ADR-0054.R18 and ADR-0054.R20 | not stated | not stated |
| `IgnoreRolePermissionHold` | `human_only`, `master_data_change`; leaf `role` (R247) | hold | Keeps the permission withheld (state `ignored`) | not stated | not stated |
| `GetSessionContext` | installation-scoped query; a valid credential, no permission; on no agent tool list (R229) | none | Returns the caller's own user, companies, rights and environment | none | not stated |

Hand-written endpoints, not registered commands: `POST /api/auth/sign-in`, `POST /api/auth/totp`, `POST /api/auth/sign-out`, `GET /api/auth/oidc/callback`, `POST /api/auth/password`, `GET /api/ui/stream`, `POST /api/ui/stream/subscriptions` (R228). Registered functions and database functions, not commands: the effective-rights function of R206 and the security-definer function `pending_invitation_companies` (R214). Jobs: the daily job that sets invitations `expired` (R212) and the upgrade step that recomputes expansions and creates holds (R244, R245). Sign-in is refused with `user_account_locked` during a lockout (R223).

## Rules

### Ownership and registered functions

R201. `permissions` (layer 2, ADR-0022.R2) owns the tables `user_account`, `user_session`, `credential_reset`, `integration_client`, `integration_token`, `installation_role_assignment`, `role`, `role_level`, `role_permission`, `role_assignment`, `role_assignment_scope`, `delegation`, `user_invitation`, `role_permission_hold`, `company_segregation_rule`, `segregation_exception` and `segregation_review`, and the work item kinds `segregation_review_due` (ADR-0054.R20) and `role_permission_held` (R248). A table `delegation_role_assignment` does not exist (ADR-0054.R21.N1). `master_data` (layer 3) owns `department`, `team` and `team_member`, and the organization columns of `employee_profile` (ADR-0054.R6).
Source: ADR-0054.R1

R202. The DDL draft is `DS-15-access.sql`; the ADRs win if it disagrees. It follows the conventions of DS-20: `company_id` on every company table, composite keys on (`company_id`, `id`), `FORCE ROW LEVEL SECURITY` and the generated company policy (ADR-0017.R19).
Source: ADR-0054.R1

R203. The installation tables `user_account`, `user_session`, `credential_reset`, `integration_client`, `integration_token` and `installation_role_assignment` have no `company_id` and no company policy. `nativeflows_app` reaches them only through `permissions.contract` and the authentication endpoints. `nativeflows_readonly` sees users only through a view `company_user` of the users with an assignment in the current company (DS-33).
Source: ADR-0054.R1

R204. The area tree, the verb levels, the templates and the segregation rules are core catalogs (ADR-0054.R25), not tables. Tables store their codes as text, validated by commands.
Source: ADR-0054.R1

R205. Access decisions need data from modules that may not import each other, so each module registers functions with the dispatcher, like handlers, and `app` (layer 6) wires them. Beyond the existing imports of ADR-0022.R2 (`documents`, `permissions` and `policy` import `work`), the modules `work`, `documents`, `permissions` and `policy` import nothing from each other for ADR-0054 or ADR-0055.
Source: ADR-0054.R2

R206. The registered functions are:
- the organization resolver, from `master_data`: for a user in a company, the user's employee, the employees of the user's teams, and the employees under the user (ADR-0054.R13); it reads current data in the command's transaction;
- related documents, from each module that owns document types: for a document, the documents linked to it by a segregation relation (ADR-0054.R19);
- document actors, from `documents`: who wrote each version, who approved, and who posted a document (from `document_version`, `approval` and the audit record of the `Post`, ADR-0038.R2), and the submitter of each round (the human of the `Submit`: its actor, or its `on_behalf_of`), which `approver_is_submitter` reads (ADR-0050.R14);
- effective rights, from `permissions`: a principal's permissions, record scope, owner scopes and field classes in force on a day, with delegations, and the holders of a role in a scope; the dispatcher's permission check and the segregation checks of ADR-0054.R18 and ADR-0054.R19 call it;
- the period resolver, from `periods`: the posting period of a date, for the review items of ADR-0054.R20;
- stage eligibility, plan and work item visibility of ADR-0055.R1: `policy` registers the stage reader, and the dispatcher combines it with effective rights and document actors; `work` filters items through a registered visibility function (ADR-0054.R15), so it never reads assignments or stages itself.
Source: ADR-0054.R2, ADR-0054.R2.N1

R207. There are no user groups. Permissions come only from roles, which is one path for the dispatcher and for agents; routing uses roles, approval stages (ADR-0055), departments and teams. This is revisited when routing needs a set of people that no role, department or team expresses.
Source: ADR-0054.R5

### User accounts and invitations

R208. `user_account` is installation data with the label `personal` (spec 17). Its columns are `login` (lower case, unique in the installation), `display_name`, `email`, `language`, `time_zone`, the credential columns of R222 and R223, `is_active`, `created_at`, `disabled_at` and `erased_at`.
Source: ADR-0054.R3

R209. One account may work in several companies: a user works in a company through role assignments there, and without an assignment in force the company is not offered (`GetSessionContext`, R229). A user is linked to a company when they hold a current or future role assignment there (one whose `valid_to` is empty or not before `clock.today`) that is not pending (R211). A user linked to more than one company is shared.
Source: ADR-0054.R3

R210. `CreateUserAccount` is company-scoped and is sent in one batch with its first `CreateRoleAssignment` in that company (ADR-0008.R20). It matches only on the exact `login`; it never searches by name or e-mail. For a new and for an existing login it writes a `user_invitation` row (company, login, and the display name and e-mail as the company typed them), and its result and plan are the same: the invitation ID and nothing else.
Source: ADR-0054.R3

R211. The state of a new invitation depends on the login:
- a new login: the account is created from what the company typed, and the invitation is `confirmed` at once; the batch's assignment, which names the invitation, is in force from its dates;
- an existing login: nothing about the account changes; the invitation is `pending`, and the batch's assignment is pending with it: it grants no access, is not in force, and does not count toward linked or shared users, the segregation checks or the small-company bound;
- until confirmation the company's queries show only the invitation: what it typed, and the state `pending`; the account's own name, e-mail and other companies are never shown to it, and its credential commands answer `record_not_found` for that user;
- the state tells the company whether the login existed (`confirmed` at once means new, `pending` means existing) and nothing more about the account; this is accepted, because the person must confirm before anything is shared; the UI warns on a pending invitation that the login belongs to an existing account and that only its owner can confirm.
Source: ADR-0054.R3

R212. A pending invitation expires after the installation setting `invitation_expiry_days` (default 30): it becomes `expired` (the state is set by the daily job and checked at confirmation), and its assignments never come into force. The company re-sends by running `CreateUserAccount` again, which writes a new invitation; `UpdateRoleAssignment` may move the old assignments onto it. The states of `user_invitation` are `pending`, `confirmed`, `canceled` and `expired`.
Source: ADR-0054.R3

R213. The invited person runs `ConfirmUserInvitation` (`human_only`); the pending assignments then come into force, through the checks of ADR-0054.R18 like any change of rights. The person may instead run `CancelUserInvitation`, and so may the company's administrator (level `edit` on `user_account`) while it is pending; a canceled invitation's assignments never come into force. Both commands are company-scoped: the envelope names the invitation's company, and the transaction sets `nativeflows.company_id` to it as for any command (ADR-0017.R19). The invited person holds no permission there yet, so for both commands the dispatcher's permission check is that the caller is the invitation's user (ADR-0017.R8.N1); the company's administrator cancels through the ordinary permission.
Source: ADR-0054.R3

R214. `ListPendingUserInvitation`, whose rows `GetSessionContext` also returns, is a registered cross-company query (ADR-0017.R19). Its `nativeflows.company_ids` are the companies holding a pending invitation for the caller, and it returns only the caller's own rows. Those companies come from one security-definer function, `pending_invitation_companies`, owned by a no-login role `nativeflows_invitation` whose only policy on `user_invitation` sees pending rows; it returns company IDs for the session's user and nothing else, in the pattern of `nativeflows_claim`. No role gains `BYPASSRLS` (ADR-0017.R19.N1).
Source: ADR-0054.R3

R215. If the company meant another person than the login's owner, nothing happens to the account's owner: they see an invitation they do not recognize and leave or cancel it, and the company sees it stay pending and cancels it. `INV-231` checks that no assignment from an invitation was ever in force before its user confirmed it, and that every first link of a user to a company came through a confirmed invitation.
Source: ADR-0054.R3

R216. `UpdateUserAccount` changes name, e-mail, language and time zone. `DisableUserAccount` and `EnableUserAccount` disable and enable an account. Disabling revokes sessions and tokens at once (ADR-0017.R2), suspends schedules and intakes the user owns, and raises `owner_suspended` (ADR-0017.R12; ADR-0042.R7).
Source: ADR-0054.R3

R217. A company's credential commands (`UpdateUserAccount`, `DisableUserAccount`, `EnableUserAccount`, `CreateCredentialReset`, `ClearUserAccountLockout`) reach only users linked to that company; for any other user they answer `record_not_found`. For a shared user, a change of display name or e-mail by `UpdateUserAccount`, and `DisableUserAccount`, `CreateCredentialReset` and `ClearUserAccountLockout`, are run only by an operator; a company caller gets `user_shared_across_companies`. To disable a shared user, the company ends its own assignments instead. When a user becomes shared (a confirmation linking a second company), every unused reset token a company issued for them is voided, so a token handed out earlier cannot be used against the other company. An operator (installation scope, ADR-0017.R7) may always run the name and e-mail change, the reset and the lockout clearance, for any user; this is also the recovery path of a sole owner who is locked out or has lost their password.
Source: ADR-0054.R3

R218. For the name or e-mail change and `CreateCredentialReset`, a company caller must hold every permission the target user holds in the company (assignments and delegations in force), with a company-wide assignment; otherwise the command fails with `grant_exceeds_own_rights`. So an IT administrator cannot reset an owner's password and sign in as the owner. `ClearUserAccountLockout` is exempt, because it grants no access: the person still needs their password and TOTP. `INV-227` checks the shared-user and escalation conditions from the audit records.
Source: ADR-0054.R3

R219. A user account is never deleted: no `Delete` command exists, so history keeps every reference. Erasing a former user's personal data (`EraseDataSubject`, ADR-0019.R10) replaces name, login and e-mail with a token and sets `erased_at`; the ID stays.
Source: ADR-0054.R3

R220. User invitations and credential resets are sent through the one system e-mail transport of ADR-0076.R7: one SMTP submission account in the deployment configuration.
Source: ADR-0054.R3.N1

### Authentication

R221. Authentication is that of ADR-0017.R2 where the rules R222 to R227 do not state otherwise.
Source: ADR-0054.R4

R222. The credential columns of `user_account` are `password_hash` (argon2), `totp_secret` (encrypted at rest, DS-18), `is_totp_enabled`, and `oidc_issuer` with `oidc_subject`, unique together.
Source: ADR-0054.R4

R223. Lockout uses `failed_sign_in_count` and `locked_until`. After the installation's limit (default 10 failures), sign-in is refused with `user_account_locked` until `locked_until` (default 15 minutes later). `ClearUserAccountLockout` ends a lockout early, under the conditions of R217. A successful sign-in resets the count.
Source: ADR-0054.R4

R224. A role has `is_totp_required`. A user who holds any such role in any company, or to whom a delegation in force lends the approvals of such a role (approval delegation is the only kind, ADR-0054.R21.N1), or who is an operator, must enable TOTP before the session is created. The templates `owner`, `chief_accountant` and `it_administrator` set the flag. This test replaces the test "holds the role `owner` or `chief_accountant`" of ADR-0017.R2. Whether every user needs TOTP stays open.
Source: ADR-0054.R4

R225. `CreateCredentialReset`, under the conditions of R217 and R218, makes a one-time token, stored as a hash, valid for at most 24 hours, and returns the link once. The token records `issued_in_company_id`, the company whose caller issued it (empty for an operator), so it can be voided when the user becomes shared (R217). The hand-written endpoint `POST /api/auth/password` consumes the token or, with the current password, changes the password (R228). The reset is sent as R220 states.
Source: ADR-0054.R4

R226. Consuming a reset token sets the password, revokes every session of the user and every other unused reset token, and writes an audit record, as creating it did. It never clears TOTP enrolment or the OIDC link: a user with TOTP still needs their code at the next sign-in. Re-enrolling a lost TOTP device is an operator task (DS-18).
Source: ADR-0054.R4

R227. Sessions are `user_session` rows: token hash, CSRF token hash, idle and absolute expiry, and `revoked_at`.
Source: ADR-0054.R4

### Session transport

R228. Sessions are server-side (ADR-0017.R2), in a cookie `__Host-nativeflows_session` (`Secure`, `HttpOnly`, `SameSite=Lax`). Every state-changing request from a cookie session carries the header `X-NativeFlows-CSRF` with the session's token, and its `Origin` must be the installation's; integrations and agents use bearer tokens and need neither. The client gets the CSRF token from the sign-in response and from `GetSessionContext`. The transport endpoints, owned by `permissions` and `registry`, are the only hand-written ones besides the attachment upload: `POST /api/auth/sign-in`, `POST /api/auth/totp`, `POST /api/auth/sign-out`, `GET /api/auth/oidc/callback`, `GET /api/ui/stream`, `POST /api/ui/stream/subscriptions`, and `POST /api/auth/password`, which consumes a one-time reset token or changes a password (R225). ADR-0008.R6 and ADR-0038.R13 carry a note for them.
Source: ADR-0040.R12, ADR-0040.R12.N1

R229. `GetSessionContext` is installation-scoped and needs only a valid credential, not a permission; this is an exception to ADR-0017.R8. It returns only the caller's own rights, and it is on no agent tool list. After sign-in it returns: the user; their companies with role assignments, permissions, field classes and record scope; their language and time zone; the installation's environment; owner scopes, the delegations in force and the user's pending invitations (R214; ADR-0054.R22). The menu, command bar (the command palette renamed by ADR-0040.R7.N1) and company switch read it.
Source: ADR-0040.R12, ADR-0040.R12.N1

R230. The annotated JSON Schemas and the i18n catalogs (core and every package's terminology) are generated into `frontend/src/generated/`, which is possible because packages ship with the build (ADR-0016.R3). They are loaded per screen and per language by dynamic import, so the shell stays within its size budget (ADR-0040.R17).
Source: ADR-0040.R12

### Consumers of agent-origin events

R231. A consumer command for an event with `origin_agent_run_id` (ADR-0013.R9) runs with the intersection of the consumer's registered permissions, the agent type's permissions and those of the human the run acted for. Such a consumer command never has effect class `posting` or `master_data_change`: it creates drafts, work items and change proposals only; a consumer that needs more drafts a document or a change proposal. ADR-0017.R13 is narrowed accordingly. ADR-0013.R11 still caps tainted events. A human command resets the origin (ADR-0013.R2), so the executing consumer of a human approval is not narrowed.
Source: ADR-0029.R12

### Authorization areas

R232. The area tree is the core catalog `authorization-areas.csv`, with the columns `code`, `parent_code`, `kind` (`area`, `document_type`, `master_data`, `function`, `report`), `module`, `name`, `added_in` and `meaning`. The roots the rule names are `sales`, `purchasing`, `inventory`, `production`, `planning`, `finance`, `banking`, `master_data`, `crm`, `administration` and `reports`; the catalog also holds the root `quality`, which ADR-0070 adds: its rules 13 and 17 put the leaves `inspection_lot`, `usage_decision` and `nonconformance` below it (ADR-0070.R13, ADR-0070.R17). The catalog is seeded by ADR-0054 and generated from the registry once it exists, like the work item kinds (ADR-0042.R1).
Source: ADR-0054.R7

R233. Leaves of the tree:
- each document type is a leaf with the type's name; master data nouns are grouped into leaves such as `partner`, `partner_bank_account` and `price_list`; functions are leaves such as `posting_period`, `exchange_rate`, `role` and `agent_run_bodies`; report groups are leaves such as `report_finance`;
- printing and reports (ADR-0049): `print_profile` under Master data (company and branch print profiles, seals and signatures; `none` in every template except `owner`), and `print_template` under Administration (print templates and print data contracts; print data itself follows its subject); the leaves of every ADR-0049 command and query are listed in ADR-0054.R24;
- CRM (ADR-0052): `interaction` (interactions, participants, links, partner e-mail domains, summaries, inbound messages and the partner timeline), `complaint`, `outbound_message` and `data_subject_request` (document types), `mailbox` (mailboxes, their authentication probe and the intake), `data_protection` (processing purposes and bases; `EraseDataSubject` at `full`), and `partner_insight` (insights, the duplicate scan and tax lookups);
- one leaf per agent type under `agent` (`agent_customer_onboarding`, `agent_quotation`, `agent_bank_matching`, `agent_purchase_invoice`, `agent_planning`, `agent_data_migration`), each holding `start_agent:<agent_type>`; `agent` belongs to module `agents`;
- `event_delivery` under Administration;
- `data_processing` under `agent` (module `agents`), which holds `SetDataProcessingPermission`, `EndDataProcessingPermission` and `RunDataProcessingProviderCheck`, so a data-protection role can approve permissions without managing agents (ADR-0063.R14).
Source: ADR-0054.R7, ADR-0054.R7.N1, ADR-0054.R7.N2

R234. Every permission has one leaf. Commands and queries of a document type belong to its leaf, and those of a master data noun to that noun's leaf. Every other command, query and capability declares its leaf when it is registered (ADR-0008.R1). CI fails when a permission has no leaf or names one outside the catalog. Commands registered `is_internal_only` keep their leaf for grouping, and no level reaches them (R239).
Source: ADR-0054.R7, ADR-0054.R7.N1

R235. Outside the tree, or without a leaf of their own:
- installation-scoped commands (package loading, installation roles, the operator variants of R217) stay with the `operator` role (ADR-0017.R7) and are outside the tree;
- `ConfirmUserInvitation` and the invited person's `CancelUserInvitation` need no leaf: their check is that the caller is the invitation's user (R213);
- `StartAgentRun` and `CancelAgentRun` need no leaf of their own: their check is a capability (ADR-0054.R24.N1).
Source: ADR-0054.R7, ADR-0054.R7.N1

### The level a permission needs

R236. Levels are ordered `none` < `read` < `edit` < `post` < `full`. Queries (`Get`, `List`, computed queries) need `read`. A command needs the highest of its verb's level, its effect class's level, and the minimum level it declares at registration, if any. Verb levels are the core catalog `authorization-verb-levels.csv`. Effect classes (ADR-0008.R1): `posting` and `outbound_send` need `post`, `master_data_change` needs `edit`, and `other` adds nothing.
Source: ADR-0054.R8

R237. The verb levels, in short (the catalog holds every verb):
- `read`: `Render` (a file of data the caller may read; ADR-0049.R20);
- `edit`: `Create`, `Update`, `Delete`, `Submit`, `Cancel`, `Recall`, `Request`, `Claim`, `Unclaim`, `Resolve`, `Assign`, `Start`, `Reserve`, `Pack`, `Unpack`, `Firm`, `Convert`, `Allocate`, `Match`, `Unmatch`, `Ignore`, `Validate`, `Import`, `Set`, `Verify`;
- `post`: `Post`, `Issue`, `Record`, `Complete`, `Reopen`, `Close`, `Release`, `Confirm`, `Accept`, `Transfer`, `Run`, `Resume`, `Abandon`, `Restrict`, `Open`, `Skip`, `Retry`, `Send`, `File`;
- `full`: `Reverse`, `Lock`, `Unlock`, `Clear`, `Erase`, `Activate`, `Enable`, `Disable`, `Export`, `Replay`;
- `Approve` and `Reject` are given by no level but by the role's approval flag (R243).
Source: ADR-0054.R8

R238. A declared minimum level raises a command above its verb: `UpdateEmployeeOrganization` and the other organization commands are `full` on `organization` (ADR-0054.R6), and `AcceptMigrationDifference` is `full` on `opening_balance_entry` (ADR-0054.R24). A declared `full` also stays for system commands a person may also start, such as `RunMailboxIntake`. The file commands sit on report leaves at their verb's level, `post`: `FileStatutoryReport` (ADR-0049.R19) on `report_finance`, and `FileTaxReturn` (ADR-0041.R18) on `report_tax`; the template `chief_accountant` has `post` on both.
Source: ADR-0054.R8, ADR-0054.R8.N1

R239. Commands that only a registered system job or consumer runs are registered `is_internal_only` (ADR-0008.R1): the expansion skips them, so no role holds them at any level, `owner` included, and they have no REST endpoint, MCP tool or tool definition; the job holds its permissions by registration (ADR-0017.R13). They are `CompleteAgentRun`, `Record<Type>EInvoiceOutcome`, `RecordInboundMessage`, `RecordMailboxIntakeOutcome`, `RecordMailboxAuthenticationCheck`, `RecordOutboundMessageOutcome`, `RecordPartnerTaxLookup`, `RecordRenderOutcome`, `RunApprovalEscalation`, `RunAgentQualityCheck`, `RunPartnerDuplicateScan` and `RunPartnerInsightComputation`, and every later command of that kind.
Source: ADR-0054.R8, ADR-0054.R8.N1

R240. Capabilities declare their leaf and level when registered:
- `post_in_soft_locked_period` is `full` on `posting_period`, so the chief accountant of spec 07 holds it through Finance `full`;
- `start_agent:<agent_type>` is `edit` on the agent type's own leaf below `agent` (R233);
- `list_all_work_items` is `full` on `work_queue_administration`;
- `delegate_for_others` is `full` on `delegation`;
- `read_agent_run_bodies` (ADR-0050.R20) is `full` on its own leaf `agent_run_bodies`, which every template except `owner` sets to `none`.
Source: ADR-0054.R8

R241. A verb in the glossary must have a row in the verb catalog; CI fails otherwise. ADR-0054 adds the rows for `Send`, `File`, `Render` and `Verify` (`VerifyMailboxAuthentication`, ADR-0052), and the glossary rows for `Set`, which the price list commands of DS-20 already use, and for `Verify`. `human_only` stays a registry flag beside the level: no level gives an agent a `human_only` command (ADR-0017.R14).
Source: ADR-0054.R8

### Role levels, expansion and holds

R242. `role_level` (role, node, `level`, `can_approve`) may be set on any node of the tree. A leaf's effective level and approval flag come from the nearest node at or above it that has a row; with none, they are `none` and false. So "Sales: `post`" with "credit_note: `read`" gives `post` on every sales leaf except credit notes.
Source: ADR-0054.R9

R243. `can_approve` needs a level of at least `read` on the same row. It adds `Approve<Type>` and `Reject<Type>` of the document types below the node.
Source: ADR-0054.R9

R244. The expansion of a role is the set of every registered permission whose leaf's effective level is at least the level the permission needs (R236 to R238), plus the approval commands of R243. It is a pure function of the role's rows and the registry catalog, so the same rows always give the same set. The expansion is stored in `role_permission`, with `role.registry_version` and `role.expansion_hash` (SHA-256 of the sorted list). It is recomputed in the transaction of every `UpdateRole` and by the upgrade step for every role (DS-37). The upgrade report lists, per role, the permissions gained.
Source: ADR-0054.R9

R245. At an upgrade, new commands within a leaf follow the level automatically, because the level states the company's intent; a new leaf starts at its parent's level, and the template's level for it is offered as an addition (the proposal mechanism of ADR-0017.R5). Interim, flagged (open question): this changes ADR-0017.R5, under which every addition was offered. A gained permission that would break the segregation mode `block` or the small-company bound (ADR-0054.R18, ADR-0054.R20) is held back as a hold (R246).
Source: ADR-0054.R9

R246. `role_permission_hold` holds: company, role, permission, `reason` (`segregation_conflict` or `small_company_mode_active`), `registry_version`, `state`, created by the upgrade step, decided by and at. Its states are `held` until a person decides; `granted`; `ignored`, which keeps the permission withheld until a person next changes the role's levels; and `ended`, when that change comes. Holds in force are those `held` or `ignored`. The stored `role_permission` is the expansion minus the holds in force (`INV-220`).
Source: ADR-0054.R9

R247. `ConfirmRolePermissionHold` grants the permission. It is a change of rights, so the checks of ADR-0054.R18 and ADR-0054.R20 run again, and the caller must hold the permission (ADR-0054.R10); otherwise the hold stays. `IgnoreRolePermissionHold` keeps it withheld. An `UpdateRole` that changes the role's levels ends every hold of the role (state `ended`): the new expansion is computed in full, under the same checks. Both hold commands are `human_only`, `master_data_change`, on the leaf `role`, change-tracked and on no agent tool list.
Source: ADR-0054.R9

R248. When the upgrade step creates holds in a company, it raises one `role_permission_held` work item for `company_owner`, with the holds as evidence; it is resolved when no hold of the company is `held`.
Source: ADR-0054.R9

R249. The dispatcher checks `role_permission` only (ADR-0017.R8). `INV-220` checks that every stored set equals the expansion minus the holds in force. There are no single-permission additions in Phase 1: a role is its levels. This is revisited when a company needs one command without its leaf.
Source: ADR-0054.R9

## Invariants

Statements are those of `invariants.csv`.

| Invariant | Statement | Check point | Protects |
| --- | --- | --- | --- |
| `INV-85` | No audit row with actor system and an origin agent run has effect class posting or master_data_change. | day | R231 |
| `INV-220` | Every role's `role_permission` rows equal the expansion of its `role_level` rows under the current registry minus the role's holds in force (held or ignored), and `expansion_hash` is the SHA-256 of the sorted stored list. | day | R244, R246, R249 |
| `INV-227` | Every name or e-mail change, credential reset and lockout clearance of a user account was executed by an operator, or by a company caller when the user was linked to that company and to no other on that day; every name or e-mail change and reset by a company caller was made by one who held every permission the user held in the company; no consumed reset changed `is_totp_enabled`; every session of the user created before a consumed reset is revoked; no reset token issued by a company was used after its user became shared. | day | R217, R218, R226 |
| `INV-231` | No role assignment naming a `user_invitation` was in force before that invitation was confirmed by its own user, unless the invitation created a new account; none naming a pending, canceled or expired invitation is in force; every user assignment that was its user's first link to a company names a confirmed invitation, except the bootstrap owner's. | day | R211, R213, R215; ADR-0054.R12 |

## Edge cases

| Edge case | Name | Case | Outcome |
| --- | --- | --- | --- |
| `EC-116` | `reset_of_shared_user` | An IT administrator of one company tries to reset the password of a user who also works in another company and is refused; an operator resets it, the user's sessions are revoked and TOTP stays enrolled. | `must_reject:user_shared_across_companies`, then `must_succeed` (R217, R226) |
| `EC-118` | `two_people_one_login` | A company creates a user with a login that another company's user already holds, meaning a different person; the response is the same as for a new login, the assignment stays pending and grants nothing, the company sees only what it typed, its password reset answers `record_not_found`, and it cancels the invitation; the account's owner gains and loses nothing. | `must_succeed` (R210, R211, R215) |

## Settings

None: `settings.csv` holds no key that the rules of this chunk use.

R212 names an installation setting `invitation_expiry_days` (default 30) that has no row in `settings.csv`. R223 names the installation's sign-in failure limit (default 10 failures) and the lockout duration (default 15 minutes) without a setting key.

## UI annotations

The sources hold no ADR-0077 floorplan, facet or tile annotation for the rules of this chunk. Work item kind (catalog `work-item-kinds.csv`): `role_permission_held`, module `permissions`, subject `company`, owner rule `company_owner`, due rule `days:7`, resolution `system`, not agent-resolvable (R248). `owner_suspended`, raised by R216, has its row with ADR-0017.R12 in chunk 1. R211 requires a UI warning on a pending invitation.

## Conflicts

CONFLICT ADR-0054.R1: ADR-0054.R21.N1 governs the table list; `delegation_role_assignment` is dropped from DS-15 and the DDL creates no such table, so R201 does not list it as owned.
CONFLICT ADR-0054.R4: ADR-0054.R3.N1 governs the sending of resets; credential resets go through the system e-mail transport of ADR-0076.R7, so "the person hands it over; NativeFlows sends nothing in Phase 1" is superseded and not restated (R220, R225). ADR-0054.R21.N1 drops delegation of role assignments, so "holds such a role through a delegation in force" reads as a delegation that lends the approvals of such a role (R224).
CONFLICT ADR-0054.R7: the rule's list of roots predates ADR-0070, whose rules 13 and 17 use the catalog root `quality`; R232 states the roots of the rule and the root `quality` of ADR-0070.R13 and ADR-0070.R17.
CONFLICT ADR-0040.R12: "palette" reads "command bar", the name ADR-0040.R7.N1 gives the command palette; R229 states it.
CONFLICT ADR-0054.R8: ADR-0054.R8.N1 governs system-only commands; they are registered `is_internal_only` and no longer declare `full` on their leaf (R238, R239). ADR-0054.R7.N1 governs the leaf of `start_agent:<agent_type>`: each agent type's own leaf below `agent`, not `agent` itself (R240).

## Proposed (not law)

None

## Trace

| Source | Where |
| --- | --- |
| ADR-0019.R2 | ref: ADR-0019.R2 |
| ADR-0019.R15 | ref: ADR-0019.R15 |
| ADR-0019.R15.N1 | ref: ADR-0019.R15.N1 |
| ADR-0019.R15.N2 | ref: ADR-0019.R15.N2 |
| ADR-0029.R8.N3 | ref: ADR-0029.R8.N3 |
| ADR-0029.R12 | R231 |
| ADR-0040.R12 | R228-R230 |
| ADR-0040.R12.N1 | R228, R229 |
| ADR-0042.R2 | ref: ADR-0042.R2 |
| ADR-0042.R2.N1 | ref: ADR-0042.R2.N1 |
| ADR-0042.R2.N2 | ref: ADR-0042.R2.N2 |
| ADR-0042.R2.N3 | ref: ADR-0042.R2.N3 |
| ADR-0042.R7 | ref: ADR-0042.R7 |
| ADR-0042.R7.N1 | ref: ADR-0042.R7.N1 |
| ADR-0042.R7.N2 | ref: ADR-0042.R7.N2 |
| ADR-0042.R7.N3 | ref: ADR-0042.R7.N3 |
| ADR-0042.R7.N4 | ref: ADR-0042.R7.N4 |
| ADR-0042.R7.N5 | ref: ADR-0042.R7.N5 |
| ADR-0045.R13.N1 | ref: ADR-0045.R13.N1 |
| ADR-0051.R30 | ref: ADR-0051.R30 |
| ADR-0051.R30.N1 | ref: ADR-0051.R30.N1 |
| ADR-0051.R30.N2 | ref: ADR-0051.R30.N2 |
| ADR-0051.R30.N3 | ref: ADR-0051.R30.N3 |
| ADR-0052.R8 | ref: ADR-0052.R8 |
| ADR-0052.R15 | ref: ADR-0052.R15 |
| ADR-0052.R15.N1 | ref: ADR-0052.R15.N1 |
| ADR-0052.R15.N2 | ref: ADR-0052.R15.N2 |
| ADR-0052.R20 | ref: ADR-0052.R20 |
| ADR-0052.R20.N1 | ref: ADR-0052.R20.N1 |
| ADR-0052.R27 | ref: ADR-0052.R27 |
| ADR-0054.D0 | Rules |
| ADR-0054.R1 | R201-R204 |
| ADR-0054.R2 | R205, R206 |
| ADR-0054.R2.N1 | R206 |
| ADR-0054.R3 | R208-R219 |
| ADR-0054.R3.N1 | R220 |
| ADR-0054.R4 | R221-R227 |
| ADR-0054.R5 | R207 |
| ADR-0054.R7 | R232-R235 |
| ADR-0054.R7.N1 | R233-R235 |
| ADR-0054.R7.N2 | R233 |
| ADR-0054.R8 | R236-R241 |
| ADR-0054.R8.N1 | R238, R239 |
| ADR-0054.R9 | R242-R249 |
