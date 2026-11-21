Module: permissions    Chunk: 1 of 4    Source ADRs: ADR-0017
Build step(s): 0, 5    Generated from index: 30d5706    Compiled by: Claude Fable 5.2, 2026-11-21

# Compiled spec: `permissions`, chunk 1 (permission envelope: actors, credentials, permissions, scope, agents, hard floors, database roles and row-level security)

## Purpose

`permissions` is a layer 2 (platform) module. It owns the actors' accounts and credentials, roles, role assignments, delegations and segregation of duties, and the database roles and row-level security that pin a transaction to its company. This chunk states the law of ADR-0017 (the permission envelope). Users, invitations, authorization areas and levels, role templates, owner scope, segregation rules, the small-company mode and delegations (ADR-0054 and later ADRs) are in the other chunks. `permissions` does not own the command registry and dispatcher, the policy table, approvals, agent runs or the audit log; it states the checks they apply.

## Entities and tables

DDL: `docs/design/DS-15-access.sql`.

| Table | Meaning | Key | Parent | Owner |
| --- | --- | --- | --- | --- |
| `integration_client` | An integration actor with its accountable human (R2, R5) | `id`, unique `code` | `user_account` (`accountable_user_id`) | permissions |
| `integration_token` | API token of an integration client, stored as a hash (R5) | `id`, unique `token_hash` | `integration_client` | permissions |
| `installation_role_assignment` | Installation-level role `operator` of a user (R11) | `id`, unique (`user_account_id`, `role`) | `user_account` | permissions |

Named by the rules of this chunk, with their rows in the chunks that compile ADR-0054: `user_account` (R2, R3), `user_session` (R3), `role`, `role_assignment`, `role_permission`, `user_invitation`.

Reads: `agent_type`, `agent_run`, `agent_type_version`, `document_version`, `event_delivery`, `outbox_event`, `idempotency_record`, `setting_definition`, `setting_value`, `module_activation`, `system_account`, `transaction_key`, `company`, `branch`, `department`, `team`, `partner`, `uom`, `uom_alias`, `tax_code`, `tax_rate`, `tax_treatment_rule`, `audit_record`, `audit_change`, `policy_decision`, `change_proposal`, `company_setup_acknowledgement`, `data_erasure_entry`, `data_subject_state`, `document`, `bin`, `stock_value`, `stock_quantity`, `posting_period_area_state`.

## Commands and queries

Only the commands and queries that the units of this chunk constrain; the user, role, assignment, delegation and segregation commands are in the other chunks.

| Name | Actor / authorization | Input | Effect | Events | Error codes |
| --- | --- | --- | --- | --- | --- |
| `ListAllowedCommand` (query) | people only in Phase 1; area `general_access`, level `read` | not stated | evaluates permissions without running a command (R7) | none | not stated |

`GetSessionContext` (R7, R13) has its row in chunk 2.

Not registered commands: the command-line bootstrap that creates the first operator and the first company's owner (R11); the security-definer delivery claim function owned by `nativeflows_claim` (R34); the security-definer function owned by `nativeflows_invitation` behind `ListPendingUserInvitation` (R36).

Error codes bound to no command of this chunk: `permission_denied` (R12, R17), `human_only` and `segregation_of_duties` (R12, R27), `record_not_found` (R15), `report_scope_incomplete` (R15), `tool_not_allowed` (R25), `tainted_run_not_allowed` (R22).

## Rules

### Model and actors

R1. Every command and query is checked against one permission model before it runs (`ADR-0008.R5`). Actors are humans, agents, integrations and system jobs. Permissions are generated. The hard floors stay hard: only humans approve; the human who triggered an agent never approves a draft that agent touched, including drafts made by consumers reacting to the agent's events; agents never execute `human_only` commands. PostgreSQL row-level security pins every transaction to its one company and fails closed. Roles, scopes and policies beyond what the dispatcher needs now are designed with DS-28 for step 5.
Source: ADR-0017.D0

R2. Actor kinds are `human` (a `user_account` row), `agent` (an `agent_type` with an `agent_run`), `integration` (an `integration_client`) and `system` (a registered system job or consumer). The actor context of every command is built from the credential (`ADR-0008.R8`), and `on_behalf_of` is the "principal acted for" of the glossary.
Source: ADR-0017.R1

### Credentials

R3. Humans authenticate with a password (argon2) and TOTP, or through OIDC (ADR-0002). TOTP is required by the role flag `is_totp_required`, also for a substitute to whom a delegation lends the approvals of such a role (only approval delegation exists, `ADR-0054.R21.N1`), and for operators; holding a role of a given name does not decide it. Whether to require TOTP for every user is an open question. Sessions are stored server-side (`user_session`) and revocable. Installation settings set the idle timeout (default 2 hours), the absolute lifetime (default 12 hours) and the lockout (default 15 minutes after 10 failed sign-ins). `user_account` and `integration_client` have `is_active`; deactivating one revokes its sessions and tokens at once. Lockout, password resets that keep TOTP and revoke sessions, shared users whose credentials only an operator changes, and the user lifecycle are stated by `ADR-0054.R3` and `ADR-0054.R4`.
Source: ADR-0017.R2, .N1

R4. An integration uses an API token stored only as a hash (`integration_token`), with an expiry of at most one year, revocable; it is bound to its client, its companies and its accountable human. System jobs and consumers run in process with the actor context they were started with (ADR-0013). No credential lets a client choose `actor` or `on_behalf_of`.
Source: ADR-0017.R3

R5. An agent run uses a short-lived run token bound to its agent type, run, tool list, `on_behalf_of` (DS-32) and the run's work item. The token is minted when the run executes, expires at `started_at` plus the run's time limit plus 60 seconds and is revoked when the run ends (`ADR-0050.R16`).
Source: ADR-0017.R3

### Permissions, roles and assignments

R6. A permission is either the name of a registered command type or query (for example `PostGoodsReceipt`, `ListJournalLine`), declared by the registry with the command (`ADR-0008.R1`), or a registered capability that no single command expresses: `post_in_soft_locked_period` (`ADR-0012.R5`), `start_agent:<agent_type>` (DS-32), `read_agent_run_bodies`, which gates the request and response bodies of agent run steps (`ADR-0050.R20`), and others added by the ADR that needs them. The list is generated, never maintained by hand.
Source: ADR-0017.R4

R7. Simulating a command needs the same permission as executing it, and every item of a command batch is checked. `ListAllowedCommand` (people only in Phase 1) and `GetSessionContext` evaluate permissions without running a command (`ADR-0040.R8`, `ADR-0040.R12`). `StartAgentRun` checks `start_agent:<agent_type>` on the human the run acts for (`ADR-0050.R15`).
Source: ADR-0017.R4

R8. A `role` is a named set of permissions in one company (`company_id`, `code`, `name`). A role stores a level per authorization area, expanded deterministically into its permissions, and the core ships job-role templates (`ADR-0054.R7` to `ADR-0054.R11`), copied into a company at setup and editable by it. Within a leaf, an upgrade's new commands follow the level; this change to the proposal mechanism is flagged as an open question (`ADR-0054.R9`). The template contents are interim defaults that the author may change.
Source: ADR-0017.R5, .N1

R9. A role assignment gives a principal a role in a company, with an optional record scope (R14) and field classes (R17). Principals are users and integration clients. Each permission applies within the scope of the assignment that grants it; a user's rights are the union of their assignments. Assignments also carry owner scopes for reading and editing and a dated validity; an assignment for an existing login stays pending until that user confirms the company's invitation; a delegation lends a user's approvals to another user for a dated window, approval delegation being the only kind (`ADR-0054.R21.N1`; `ADR-0054.R3`, `ADR-0054.R12`, `ADR-0054.R13`, `ADR-0054.R21`).
Source: ADR-0017.R6, .N1

R10. Assigning roles is a command that needs its own permission. Nobody can grant a permission they do not hold, or assign a role to themselves. The last user with a role holding every permission of the template `owner` in a company keeps it (`last_owner_required`, `ADR-0054.R12`). Interim, flagged: the `owner` template holds every permission and capability except the commands registered `is_internal_only`, which no role holds (`ADR-0054.R8.N1`), so a one-person company's bootstrapped owner can work alone; whether that is right joins the small-team open question (R29).
Source: ADR-0017.R6

R11. Installation-level roles (`operator`: loading packages, ADR-0016; installation-scoped commands) are rows of `installation_role_assignment`. The first operator and the first company's owner are created by a command-line bootstrap when the installation is set up. The last operator cannot be removed.
Source: ADR-0017.R7

### Enforcement: permission, record scope, field classes

R12. Before anything runs, the dispatcher checks that the actor holds the command's or query's permission in the command's company; otherwise `permission_denied`. Every denial (`permission_denied`, `human_only`, `segregation_of_duties`) is written to the audit log with the actor context (DS-36). Repeated denials of one agent run are a signal of injected instructions (DS-32). Refusals for safety reasons leave denial records (`ADR-0038.R5`).
Source: ADR-0017.R8

R13. Exceptions to the permission check of R12. `GetSessionContext` needs only a valid credential and returns the caller's own rights (`ADR-0040.R12`). `ConfirmUserInvitation` and the invited person's `CancelUserInvitation` are company-scoped, and their check is that the caller is the invitation's user, since that person holds no permission in the company yet (`ADR-0054.R3`).
Source: ADR-0017.R8, .N1

R14. Record scope in the envelope covers the header-level `branch_id` and `warehouse_id` of documents and the same dimensions of master data. A document is visible as a whole if its header is in scope; its journal entry and lines follow the document. A document whose scoped dimension is empty is visible to every assignment of the company. Production documents use `production_warehouse_id` as their warehouse dimension (`ADR-0034.R18`). Other dimensions are added with DS-28. Owner scope (`own`, `team`, `department`, `branch`, `company`) narrows the record scope for documents, and everything that shows a document's data follows it; aggregating queries need `branch` or `company` (`ADR-0054.R13` to `ADR-0054.R15`).
Source: ADR-0017.R9, .N2

R15. Queries return only rows inside the scope and say so with `is_scope_filtered: true` when rows were left out, so totals are not mistaken for complete ones. A command on a record outside the scope fails with `record_not_found` (`ADR-0008.R5`). The same filter applies over REST and MCP (Principle 10). Statutory reports and books need the whole company: an actor with a limited record scope gets `report_scope_incomplete`, never partial totals (`ADR-0049.R17`).
Source: ADR-0017.R9, .N1

R16. Field classes are a closed list in the glossary: `cost`, `margin` and `sensitive_personal` (`ADR-0079.R11`); a schema field may carry one. An assignment grants field classes. A column labelled `sensitive_personal` is returned only to an assignment that holds the class; only the `owner` template suggests it by default, so the owner can grant it (R10), and no Phase 1 column carries it. The leaf `blocked_personal_data` is held the same way: `owner` at `full`, every other template at `none`. No agent type version may hold `sensitive_personal`: `agent_type_version.field_classes` stays limited to `cost` and `margin` (DS-05). Data labels (spec 17) are separate and govern LLM routing.
Source: ADR-0017.R10, .N1

R17. A field of a class the actor lacks is omitted from responses, plans, events delivered to clients and error details (`ADR-0008.R12`, `ADR-0008.R24`). A command that sets such a field fails with `permission_denied`; an `Update` that does not mention it keeps its value.
Source: ADR-0017.R10

### Agents, system jobs and integrations

R18. An agent type declares its fixed tool list (DS-32, spec 03 rule 2) and its permissions. An agent run's effective permissions, record scope and field classes are the intersection of its agent type's and those of its `on_behalf_of` human in that company, evaluated against current assignments at every command (spec 03 rule 3). Starting a run needs `start_agent:<agent_type>` for that human. The tool list is a third limit beside the intersection: a tool must be on the list and allowed by both (`ADR-0050.R29`, `ADR-0050.R31`). Agent types get no role assignments, and the human's owner scope binds the run (`ADR-0054.R16`).
Source: ADR-0017.R11, .N1

R19. The `on_behalf_of` of a run is bound when it starts: the human who started it; for a scheduled run, the owner of the schedule; for a run triggered by incoming email or another event, the owner of that intake or workflow, a required setting. For agent runs the owner of an intake or workflow is always the agent type setting's `workflow_owner_id` (`ADR-0050.R15`). The sender or author of outside content never becomes `on_behalf_of`.
Source: ADR-0017.R12

R20. If the `on_behalf_of` human is deactivated or loses the rights, the run's next command fails; schedules and intakes they own are suspended and a work item (kind `owner_suspended`) tells the company's owners (DS-29). The same applies to other owners named by the core, for example the `fiscal_calendar_owner` (`ADR-0012.R3`).
Source: ADR-0017.R12

R21. A run that read untrusted content keeps only the narrowed rights of spec 03 rule 1 (DS-32; `ADR-0013.R11`): the tainted read scope of `ADR-0050.R27` (scope rows, the work item, the run's own drafts, reference data) and the command limit of `ADR-0050.R26`.
Source: ADR-0017.R12

R22. A command outside the command limit of a tainted run (R21) is refused with `tainted_run_not_allowed` (`ADR-0050.R26`).
Source: ADR-0017.R12

R23. System jobs and consumers hold the permissions declared when they are registered. Their `on_behalf_of` names the accountable human (spec 03 rule 3) but does not limit them, except where an ADR sets a condition on that human; for example close jobs in a soft-locked period need an `on_behalf_of` with `post_in_soft_locked_period` (`ADR-0012.R5`). Integrations get role assignments on their `integration_client` per company, like users; their accountable human is for accountability.
Source: ADR-0017.R13

R24. A consumer command for an event with an origin agent run uses the intersection of the consumer's, the agent type's and the human's permissions, with no policy exception; such a command never posts or changes master data (`ADR-0029.R12`).
Source: ADR-0017.R13

### Hard floors

R25. Agents never execute and never simulate `human_only` commands: every agent actor runs under a tool list that holds no `human_only` command (`ADR-0050.R29`, `ADR-0050.R30`), and the tool list is checked first, so the call is refused with `tool_not_allowed` (DS-04, dispatcher check order).
Source: ADR-0017.R14, .N1

R26. `Approve<Type>` and `Reject<Type>` are executed only by human actors; agents never approve on a human's behalf (spec 07, approval engine). `INV-17` checks it.
Source: ADR-0017.R15

R27. Each `document_version` records the full actor context of the command that wrote it: `actor_kind`, `actor_id`, `on_behalf_of_id`, `agent_run_id` and `origin_agent_run_id`. `origin_agent_run_id` is the agent run at the start of the chain that led to this write, carried on events and inherited through every consumer that reacts to them (`ADR-0013.R2`, `ADR-0013.R9`), so a draft made by a consumer far down the chain from an agent still counts. `Approve<Type>` is rejected with `segregation_of_duties` if any version of the document was written by an agent run, directly or through a consumer, whose `on_behalf_of` is the approving human (spec 03 rule 5).
Source: ADR-0017.R16

R28. Spec 03 rule 5's "the person who triggers" is read as the human whose own act started the run (a start command, a note or message they wrote, a work item they handed to the agent). The check of R27 is stricter: it refuses every human the run acted for, the workflow owner of event and schedule runs included, and it stays the default. No policy or company setting relaxes the floor itself; only the small-company mode relaxes the stricter part, for untainted versions, as a recorded exception (`ADR-0054.R20`, `ADR-0067.R16`).
Source: ADR-0017.R16, .N1

R29. Open questions for the author, designed with DS-28 for step 5: whether the human who triggered an agent may post that agent's draft without approval when the policy requires none; how a company of one or two people meets required approvals; whether one human may be both preparer and approver of their own document (spec 03 rule 6). Interim: R26 to R28 apply to every company, and posting without approval follows the policy table of ADR-0043 from step 5 (before step 5 a stub that allows everything, `ADR-0008.R5`). Proposed answers, flagged for the author: an explicit small-company exception mode (`ADR-0054.R20`), and stage approvals that exclude every writer of the document by default (`ADR-0055.R7`, `ADR-0055.R20`). The hard floor of R27 is never relaxed.
Source: ADR-0017.R17, .N1

### Database roles

R30. Database roles: `nativeflows_migration` owns the schema and runs migrations, and is the only role with `BYPASSRLS`, so data migrations see every company; `nativeflows_app` runs commands and queries; `nativeflows_worker` runs delivery workers and system jobs; `nativeflows_claim` owns the delivery claim function and has a policy on `event_delivery` that sees every row, and nothing else; `nativeflows_readonly` serves the read-only query layer (DS-33) and reads only the views of schema `query`; `nativeflows_query_owner` (no login, never `BYPASSRLS`) owns those views (`ADR-0050.R43`); `nativeflows_check` runs the invariant checks, SELECT only and subject to RLS (`ADR-0022.R7`; DS-16). Every table with `company_id` has `FORCE ROW LEVEL SECURITY`.
Source: ADR-0017.R18

R31. The application roles (`nativeflows_app`, `nativeflows_worker`, `nativeflows_readonly`, `nativeflows_check`) get no `TEMPORARY` privilege on the database and SELECT only on `setting_definition`; revoking `TEMPORARY` is a DS-18 item. The no-login role `nativeflows_setting_reader` owns the function `setting_installation_value`, with one policy on `setting_value` that sees rows with a null company; EXECUTE on the function is revoked from PUBLIC and granted to the application roles (`ADR-0063.R1`, `ADR-0063.R2`).
Source: ADR-0017.R18.N1, ADR-0017.R18.N2

R32. Every function of the design files pins `SET search_path = nativeflows, pg_temp`, and trigger functions and security-definer functions name their tables with the schema, so a temporary table cannot stand in for a table they read. `gen_overview.py --check` refuses a function without the pin, and lab t31 Z06 checks the loaded catalog.
Source: ADR-0017.R18.N1, ADR-0017.R18.N2

### Row-level security

R33. Each transaction sets the current company with `set_config('nativeflows.company_id', …, true)`. Policies allow a row only when its `company_id`, compared as text, equals that setting; if the setting is missing, no row is visible (fail closed). Rows with a null `company_id` (installation-scoped events and deliveries, `ADR-0013.R14`) are visible only when the setting is the explicit value `installation`. A registered cross-company query (for example consolidation) sets `nativeflows.company_ids` to the companies the actor may see, and a second, read-only policy accepts those.
Source: ADR-0017.R19

R34. Delivery workers claim `event_delivery` rows through one security-definer function owned by `nativeflows_claim`, which returns only the row and its company, then set the company before running the consumer (`ADR-0013.R7`). `idempotency_record` carries `company_id` and follows the same policies. Procrastinate's tables are technical, have no company and are reachable only by `nativeflows_worker`.
Source: ADR-0017.R19

R35. Record scope and field classes stay in the dispatcher and in the read-only layer's views (DS-33); RLS guards companies only, as the second line of defense (spec 03 rule 4). The views apply field classes and record scope from session settings that the query layer sets, and the company policy applies to `nativeflows_query_owner` (`ADR-0050.R43`, `ADR-0050.R48`).
Source: ADR-0017.R19

R36. The invited user's pending list (`ListPendingUserInvitation`) is a registered cross-company query: its `nativeflows.company_ids` are the companies holding a pending invitation for that user, found by a security-definer function owned by the no-login role `nativeflows_invitation` in the pattern of `nativeflows_claim`, and it returns only that user's rows; no role gains `BYPASSRLS` (`ADR-0054.R3`).
Source: ADR-0017.R19.N1

R37. Every design file ends with one generated section that enables and forces RLS and creates `company_policy` and `company_ids_policy`, with the predicates of R33, on every table of the file with `company_id` and on its default partitions (the installation variant where `company_id` is nullable); no file holds a hand-written block. This covers the company tables of `DS-06-universal-journal.sql`, `idempotency_record` of DS-05 (with the installation exception) and `module_activation` (`DS-28-settings.sql`). `system_account` and `transaction_key` are global catalogs without policies. The lab's `RLS_ALLOWLIST` is empty. Lab t15 A11 and t31 Z04 check the policies.
Source: ADR-0017.R19.N2, ADR-0017.R19.N4, ADR-0017.R19.N5

R38. Shared reference catalogs: a table whose null-company rows are core or package rows that every company reads takes a third generated variant: the installation variant of `company_policy` (a company writes only its own rows; null rows only under `installation`) plus `shared_read_policy FOR SELECT USING (company_id IS NULL)`. It applies to `uom` and to `tax_code`, `tax_rate` and `tax_treatment_rule` (`ADR-0080.R3`), which hold company rows (`ADR-0041.R4`). The other nullable tables hold installation-scoped records, not reference rows, and keep the installation variant (lab `gen_overview.RLS_SHARED_READ`; lab t31 Y01 to Y05).
Source: ADR-0017.R19.N5

R39. `company` has no `company_id`; its generated policies compare its own `id`: `company_policy` with `nativeflows.company_id`, `company_ids_policy` with `nativeflows.company_ids`, so a session sees its own company and a registered cross-company query the companies it lists. `CreateCompany` sets the setting to the new company's id before it inserts the row (`gen_overview.RLS_SELF`; lab t31 Y06). The guard `gen_overview.py --check` prints the tables and partitions under row-level security, the nullable ones, the shared reference catalogs and `company`.
Source: ADR-0017.R19.N5

### Company isolation by keys

R40. Keys hold company isolation too. Every foreign key from a company table (`company_id NOT NULL`) to a company table is composite, `FOREIGN KEY (company_id, x_id) REFERENCES t (company_id, id)`, and the target carries `UNIQUE (company_id, id)` (named `uq_<table>_company_id_id` where added, ADR-0004). A nullable `x_id` is fine: the key is MATCH SIMPLE and unchecked while `x_id` is null. Self-references follow the rule. A partitioned table is partitioned by range of `id` (`ADR-0006.R22`), so its `UNIQUE (company_id, id)` contains the partition key and needs no exception. `ON DELETE`, `ON UPDATE` and `DEFERRABLE` clauses are kept as written; a `SET NULL` or `SET DEFAULT` action must name its column, or it would null `company_id`. A lab stub that a composite key targets has the same unique key. Polymorphic references are not foreign keys and are out of scope.
Source: ADR-0017.R19.N3

R41. Multi-column keys follow R40: `company_id` is added on both sides, for example `FOREIGN KEY (company_id, bin_id, warehouse_id) REFERENCES bin (company_id, id, warehouse_id)`, and the target gets `uq_<table>_company_id_<columns>` (`uq_<table>_company_key` where that name would exceed 63 bytes) beside its existing unique key, which stays for the keys that use it; so no key between company tables relies on an anchor column. `schema_phase_b.py` rule 3 converts the keys; `gen_overview.py` fails on any key between company tables without `company_id` and on a nullable-company table missing from its `COMPANY_KEY_ALLOWLIST`; labs t16 (S06b) and t17 (D01b) check the rule on the loaded catalog.
Source: ADR-0017.R19.N3

R42. Exceptions to R40, which stay single-column (`COMPANY_KEY_ALLOWLIST`): keys to or from a table whose `company_id` is nullable (installation-or-company rows), namely the keys to `uom`, to `audit_record` and to `outbox_event`, the latter from `audit_change` and `event_delivery`, whose own `company_id` is nullable; and keys to installation tables without `company_id` (for example `user_account`). Through the single-column keys to `uom` and to `audit_record` a row can name another company's unit or audit record: a company's own unit stays in its company by the command check of `ADR-0045.R13`, and `INV-606` and `INV-200` check the keys.
Source: ADR-0017.R19.N3, ADR-0017.R19.N4

R43. A composite key from a table whose `company_id` can be null is unchecked while it is null (MATCH SIMPLE), so each such key has a CHECK that sets `company_id` whenever its column is set: `audit_record` to `policy_decision` (`ck_audit_record_policy_decision_company`; installation commands have no policy decision), `setting_value` to `change_proposal` and `company_setup_acknowledgement` (`ck_setting_value_company_keys`; an installation value is approved by the operators' deployment change), `data_erasure_entry` and `data_subject_state` to `document` (`ADR-0079.R7`), and `tax_code` and `tax_rate` to `change_proposal` (`ck_tax_code_scope`, `ck_tax_rate_scope`). Lab t31 Y11 checks every composite key from such a table on the loaded catalog.
Source: ADR-0017.R19.N5

### What the database proves

R44. An application role can set `nativeflows.company_id` to any company or to `installation`: `set_config` is open to every role, and nothing in the database ties the setting to the authenticated actor. So the company boundary is enforced by the dispatcher, which builds the actor context from the credential, checks the actor's permissions for the envelope's `company_id` and sets the setting for each transaction (`ADR-0008.R5`, `ADR-0008.R7`, `ADR-0008.R8`; R33). Row-level security is the second line: it stops a query or a handler that forgets the company, not a session that lies about it. No mechanism makes the setting unforgeable: the `nativeflows_claim` pattern narrows what a definer function returns, not who sets the company. Open: DS-18 builds an unforgeable company setting or records this boundary as final.
Source: ADR-0017.R19.N6

R45. Shared reference rows (`company_id` null in `uom`, `tax_code`, `tax_rate` and `tax_treatment_rule`) are writable only under the setting value `installation`, which only the operators' deployment path uses (`nativeflows admin migrate` loading the core catalogs and the package, `ADR-0022.R8`). An application session that set `installation` could write them; the dispatcher never sets it for a company command.
Source: ADR-0017.R19.N6

R46. TRUNCATE ignores row-level security and row triggers. Every table with `company_id`, every append-only table and every table with a delete guard therefore has the generated `trg_<table>_refuse_truncate` (`stock_value`, `stock_quantity`, `idempotency_record`, `posting_period_area_state` and `uom_alias` included). Retention drops whole partitions and never truncates (`ADR-0013.R15`, `ADR-0038.R6`), and application roles are never granted TRUNCATE (R30; DS-18). Lab t31 Z03 to Z05 check each trigger enabled and running its function, each policy with its predicate and no other permissive policy, and the TRUNCATE guards; also Z07, Z08 and Y01 to Y04.
Source: ADR-0017.R19.N6

## Invariants

| Invariant | Statement | Check point | Protects |
| --- | --- | --- | --- |
| `INV-15` | No response, plan, delivered event or error detail holds a field of a field class the actor lacks. | command | R17 |
| `INV-17` | Every approval was made by a human, and no approved document has a version whose `agent_run_id` or `origin_agent_run_id` belongs to a run on behalf of the approver. | day | R26, R27 |
| `INV-200` | An `audit_change` row and its `audit_record` have the same `company_id` (both null for an installation-scoped record), and a `change_proposal_execution_item` or `segregation_exception` names an `audit_record` of its own company; the keys stay single-column because `audit_record` has installation rows (`gen_overview.COMPANY_KEY_ALLOWLIST`). The catalog row holds the query, empty when it holds. | day | R42 |

`INV-606` (area `master_data`: every row that names a unit names a core unit or a unit of the row's own company) also protects R42; its row belongs to `master_data`.

## Settings

None: `settings.csv` holds no key owned by the rules of this chunk. R3 names installation settings for the session idle timeout (default 2 hours) and the absolute session lifetime (default 12 hours) without giving their keys; the lockout settings are named with `ADR-0054.R4` in chunk 2.

## UI annotations

Work item kind `owner_suspended` (module `permissions`, subject table `user_account`, owner rule `company_owner`, due rule `days:1`, resolution `person`, not agent-resolvable): an owner of schedules, intakes, workflows, policy rules or open work items was deactivated or lost rights; what they own is suspended or reassigned (R20; `ADR-0042.R7`, `ADR-0043.R11`). The units of this chunk hold no other ADR-0077 annotation.

## Conflicts

CONFLICT ADR-0017.R2: the TOTP test by role name (`owner`, `chief_accountant`) gives way to the role flag `is_totp_required` of ADR-0017.R2.N1 and ADR-0054.R4; R3 states the flag only.
CONFLICT ADR-0017.R2.N1: TOTP for "a substitute who holds such a role through a delegation" follows ADR-0054.R21.N1, which drops delegation of role assignments: the substitute needs TOTP when a delegation lends the approvals of a role with `is_totp_required`; R3 states it.
CONFLICT ADR-0017.R5: the role templates named in the rule and the direct permission list give way to levels per authorization area and the job-role templates of ADR-0054.R7 to ADR-0054.R11, as ADR-0017.R5.N1 says; the offer of upgrade additions gives way to ADR-0054.R9, still flagged open.
CONFLICT ADR-0017.R6: "the last user with `owner`" reads as ADR-0054.R12 states it (the last holder of a role with every permission of the template `owner`, `last_owner_required`), and "every permission" of the `owner` template excludes the `is_internal_only` commands that no role holds (ADR-0054.R8.N1); R10 states both, keeping the interim flag.
CONFLICT ADR-0017.R6.N1: "a delegation lends a user's rights" is narrowed by ADR-0054.R21.N1 to approval delegation, the only kind left; R9 states it.
CONFLICT ADR-0017.R13: the closing sentence narrows a consumer command for an event with an origin agent run to the intersection of ADR-0029.R12; R24 states the narrowed result.
CONFLICT ADR-0017.R14: ADR-0017.R14.N1 strikes "they may simulate them" for agents, because the tool list check of ADR-0050.R29 refuses the call first; R25 states that no agent simulates a `human_only` command.
CONFLICT ADR-0017.R16: "no policy or company setting relaxes this" holds for the floor only; ADR-0017.R16.N1 (ADR-0067.R16) lets the small-company mode relax the stricter workflow-owner part as a recorded exception; R28 states it.
CONFLICT ADR-0017.R17: the policy stub that allows everything ends at step 5 with the policy table of ADR-0043, by the rule's own closing sentence; R29 keeps the open questions and the flagged proposals of ADR-0017.R17.N1.
CONFLICT ADR-0017.R18.N1: the trigger functions of the earlier DDL files left as a DS-18 backlog item are covered by ADR-0017.R18.N2, under which every function pins the search path; R32 states the current result.
CONFLICT ADR-0017.R19.N2: the hand-written rls_v1 policies of DS-06 are replaced by the generated section of ADR-0017.R19.N4; R37 states the generated policies only.
CONFLICT ADR-0017.R19.N3: the claim that a row can never name another company's record is narrowed by ADR-0017.R19.N4 for the single-column keys to `uom` and `audit_record`; R42 states the exception and its invariants. Its example `tax_code` of an installation table without `company_id` is not kept, because ADR-0017.R19.N5 gives `tax_code` company rows.
CONFLICT ADR-0017.R19.N4: the `uom` entry of `RLS_ALLOWLIST` and the open point on reading installation rows are closed by the shared-read variant of ADR-0017.R19.N5; R37 and R38 state the closed result.

## Trace

| Source | Where |
| --- | --- |
| ADR-0004.R13 | ref: ADR-0004.R13 |
| ADR-0017.D0 | R1 |
| ADR-0017.R1 | R2 |
| ADR-0017.R2 | R3 |
| ADR-0017.R2.N1 | R3 |
| ADR-0017.R3 | R4, R5 |
| ADR-0017.R4 | R6, R7 |
| ADR-0017.R5 | R8 |
| ADR-0017.R5.N1 | R8 |
| ADR-0017.R6 | R9, R10 |
| ADR-0017.R6.N1 | R9 |
| ADR-0017.R7 | R11 |
| ADR-0017.R8 | R12, R13 |
| ADR-0017.R8.N1 | R13 |
| ADR-0017.R9 | R14, R15 |
| ADR-0017.R9.N1 | R15 |
| ADR-0017.R9.N2 | R14 |
| ADR-0017.R10 | R16, R17 |
| ADR-0017.R10.N1 | R16 |
| ADR-0017.R11 | R18 |
| ADR-0017.R11.N1 | R18 |
| ADR-0017.R12 | R19, R20, R21, R22 |
| ADR-0017.R13 | R23, R24 |
| ADR-0017.R14 | R25 |
| ADR-0017.R14.N1 | R25 |
| ADR-0017.R15 | R26 |
| ADR-0017.R16 | R27, R28 |
| ADR-0017.R16.N1 | R28 |
| ADR-0017.R17 | R29 |
| ADR-0017.R17.N1 | R29 |
| ADR-0017.R18 | R30 |
| ADR-0017.R18.N1 | R31, R32 |
| ADR-0017.R18.N2 | R31, R32 |
| ADR-0017.R19 | R33, R34, R35 |
| ADR-0017.R19.N1 | R36 |
| ADR-0017.R19.N2 | R37 |
| ADR-0017.R19.N3 | R40, R41, R42 |
| ADR-0017.R19.N4 | R37, R42 |
| ADR-0017.R19.N5 | R37, R38, R39, R43 |
| ADR-0017.R19.N6 | R44, R45, R46 |
