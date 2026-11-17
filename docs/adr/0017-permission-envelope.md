# ADR-0017: Permission model, envelope part

Status: accepted (2026-11-14) under ADR-0005, reviewed by Claude Fable 5.2. Design item: DS-15 (envelope part for step 0; the full model is due at step 5). Related decisions: D2, D12, D14. Principles 3, 4, 7, 10. ADR-0004, ADR-0005, ADR-0008, ADR-0009, ADR-0012, ADR-0013, ADR-0014, ADR-0016.

## Decision

Every command and query is checked against one permission model before it runs (ADR-0008 rule 5). Actors are humans, agents, integrations and system jobs. Permissions are generated: the name of each command type and query, plus a few registered capabilities that are not commands (posting in a soft-locked period, starting an agent of a type). Roles bundle permissions per company; a role assignment may limit a human to some branches or warehouses (record scope) and grants field classes such as cost and margin. An agent's effective permissions are the intersection of its agent type's and those of the human it acts for, re-evaluated at every command; that human is bound from the trigger (whoever started the run, the owner of a schedule or of an email intake, never an email's sender). System jobs and consumers hold the permissions declared when they are registered. The hard floors stay hard: only humans approve; the human who triggered an agent never approves a draft that agent touched, including drafts made by consumers reacting to the agent's events; agents never execute `human_only` commands. PostgreSQL row-level security pins every transaction to its one company and fails closed. Roles, scopes and policies beyond what the dispatcher needs now are designed with DS-28 for step 5.

### Rules

**Actors and credentials**

1. Actor kinds are `human` (a `user_account` row), `agent` (an `agent_type` with an `agent_run`), `integration` (an `integration_client`) and `system` (a registered system job or consumer); the actor context of every command is built from the credential (ADR-0008 rule 8), and `on_behalf_of` is the "principal acted for" of the glossary.
2. Humans authenticate with a password (argon2) and TOTP, or through OIDC (ADR-0002). TOTP is mandatory for users holding the `owner` or `chief_accountant` role and for operators; whether to require it for every user is an open question. Sessions are stored server-side and revocable; installation settings set the idle timeout (default 2 hours), the absolute lifetime (default 12 hours) and the lockout (default 15 minutes after 10 failed sign-ins). `user_account` and `integration_client` have `is_active`; deactivating one revokes its sessions and tokens at once.

   Note: TOTP is required by the role flag `is_totp_required`, also for a substitute who holds such a role through a delegation, not by holding a role of a given name; lockout, password resets that keep TOTP and revoke sessions, shared users whose credentials only an operator changes, and the user lifecycle: [ADR-0054](0054-users-roles-and-authorizations.md) rules 3–4.
3. An integration uses an API token stored only as a hash, with an expiry of at most one year, revocable; it is bound to its client, its companies and its accountable human. An agent run uses a short-lived run token bound to its agent type, run, tool list and `on_behalf_of` (DS-32). System jobs and consumers run in process with the actor context they were started with (ADR-0013). No credential lets a client choose `actor` or `on_behalf_of`.

   The run token is minted when the run executes, is also bound to the run's work item, expires at `started_at` plus the run's time limit plus 60 seconds and is revoked when the run ends ([ADR-0050](0050-agent-runtime-and-query-layer.md) rule 16).

**Permissions and roles**

4. A permission is either the name of a registered command type or query (e.g. `PostGoodsReceipt`, `ListJournalLine`), declared by the registry with the command (ADR-0008 rule 1), or a registered capability that no single command expresses: `post_in_soft_locked_period` (ADR-0012 rule 5), `start_agent:<agent_type>` (DS-32) and others added by the ADR that needs them. The list is generated, never maintained by hand. Simulating a command needs the same permission as executing it, and every item of a command batch is checked. `ListAllowedCommand` (people only in Phase 1) and `GetSessionContext` evaluate permissions without running a command ([ADR-0040](0040-ui-architecture.md) rules 8, 12).

   `StartAgentRun` checks `start_agent:<agent_type>` on the human the run acts for ([ADR-0050](0050-agent-runtime-and-query-layer.md) rule 15).

   Capability `read_agent_run_bodies` gates the request and response bodies of agent run steps ([ADR-0050](0050-agent-runtime-and-query-layer.md) rule 20).
5. A role is a named set of permissions in one company (`role`: `company_id`, `code`, `name`, permissions). The core ships role templates — `owner`, `chief_accountant`, `accountant`, `warehouse_keeper`, `sales`, `purchasing`, `viewer` — copied into a company at setup and editable by it. The registry names, for each command, the templates that include it by default; when an upgrade adds commands, companies are offered the additions to their copied roles (as SAP proposes authorization defaults; mechanism with the upgrade policy, DS-37). The template contents are interim defaults that the author may change.

   Note: roles store a level per authorization area, expanded deterministically into these permissions; thirteen job-role templates replace this list ([ADR-0054](0054-users-roles-and-authorizations.md) rules 7–11). Within a leaf, an upgrade's new commands follow the level, a change to the proposal mechanism flagged as an open question ([ADR-0054](0054-users-roles-and-authorizations.md) rule 9).
6. A role assignment gives a user a role in a company, with an optional record scope (rule 9) and field classes (rule 10). Each permission applies within the scope of the assignment that grants it; a user's rights are the union of their assignments. Assigning roles is a command that needs its own permission; nobody can grant a permission they do not hold, or assign a role to themselves; the last user with `owner` in a company cannot lose it. Interim, flagged: the `owner` template holds every permission and capability, so a one-person company's bootstrapped owner can work alone; whether that is right joins the small-team open question (rule 17).

   Note: assignments gain owner scopes for reading and editing and dated validity; principals are users and integration clients; an assignment for an existing login stays pending until that user confirms the company's invitation; a delegation lends a user's rights to another user for a dated window ([ADR-0054](0054-users-roles-and-authorizations.md) rules 3, 12–13, 21).
7. Installation-level roles (`operator`: loading packages, ADR-0016; installation-scoped commands) are rows of `installation_role_assignment`. The first operator and the first company's owner are created by a command-line bootstrap when the installation is set up; the last operator cannot be removed.

**Checks, record scope and field classes**

8. Before anything runs, the dispatcher checks that the actor holds the command's or query's permission in the command's company; otherwise `permission_denied`. Every denial (`permission_denied`, `human_only`, `segregation_of_duties`) is written to the audit log with the actor context (DS-36); repeated denials of one agent run are a signal of injected instructions (DS-32). Refusals for safety reasons leave denial records ([ADR-0038](0038-audit-and-observability.md) rule 5). Exception: `GetSessionContext` needs only a valid credential and returns the caller's own rights ([ADR-0040](0040-ui-architecture.md) rule 12).

   Note: exception: `ConfirmUserInvitation` and the invited person's `CancelUserInvitation` are company-scoped, and their check is that the caller is the invitation's user, since that person holds no permission in the company yet ([ADR-0054](0054-users-roles-and-authorizations.md) rule 3).
9. Record scope in the envelope covers the header-level `branch_id` and `warehouse_id` of documents and the same dimensions of master data. A document is visible as a whole if its header is in scope; its journal entry and lines follow the document. A document whose scoped dimension is empty is visible to every assignment of the company. Queries return only rows inside the scope and say so with `is_scope_filtered: true` when rows were left out, so totals are not mistaken for complete ones; a command on a record outside the scope fails with `record_not_found` (ADR-0008 rule 5). Other dimensions are added with DS-28. The same filter applies over REST and MCP (Principle 10). Production documents use `production_warehouse_id` as their warehouse dimension ([ADR-0034](0034-production-orders-and-shop-floor.md) rule 18).

   Note: statutory reports and books need the whole company: an actor with a limited record scope gets `report_scope_incomplete`, never partial totals ([ADR-0049](0049-statutory-reporting-and-printing.md) rule 17).

   Note: owner scope (`own`, `team`, `department`, `branch`, `company`) narrows the record scope for documents, and everything that shows a document's data follows it; aggregating queries need `branch` or `company` ([ADR-0054](0054-users-roles-and-authorizations.md) rules 13–15).
10. Field classes are a closed list in the glossary, starting with `cost` and `margin`; a schema field may carry one. An assignment grants field classes; a field of a class the actor lacks is omitted from responses, plans, events delivered to clients and error details (ADR-0008 rules 12, 24). A command that sets such a field fails with `permission_denied`; an `Update` that does not mention it keeps its value. Data labels ([17](../spec/17-seatmap-data-classification.md)) are separate and govern LLM routing.

**Agents, system jobs and integrations**

11. An agent type declares its fixed tool list (DS-32, [03](../spec/03-agent-safety.md) rule 2) and its permissions. An agent run's effective permissions, record scope and field classes are the intersection of its agent type's and those of its `on_behalf_of` human in that company, evaluated against current assignments at every command ([03](../spec/03-agent-safety.md) rule 3). Starting a run needs `start_agent:<agent_type>` for that human.

    The tool list is a third limit beside the intersection: a tool must be on the list and allowed by both ([ADR-0050](0050-agent-runtime-and-query-layer.md) rules 29, 31).

    Note: agent types get no role assignments; an agent run's rights stay as here and in ADR-0050 rule 31, and its human's owner scope binds it ([ADR-0054](0054-users-roles-and-authorizations.md) rule 16).
12. The `on_behalf_of` of a run is bound when it starts: the human who started it; for a scheduled run, the owner of the schedule; for a run triggered by incoming email or another event, the owner of that intake or workflow, a required setting. The sender or author of outside content never becomes `on_behalf_of`. If that human is deactivated or loses the rights, the run's next command fails; schedules and intakes they own are suspended and a work item tells the company's owners (DS-29). The same applies to other owners named by the core, e.g. the `fiscal_calendar_owner` (ADR-0012 rule 3). A run that read untrusted content keeps only the narrowed rights of [03](../spec/03-agent-safety.md) rule 1 (DS-32; ADR-0013 rule 11).

    The narrowed rights are the tainted read scope of [ADR-0050](0050-agent-runtime-and-query-layer.md) rule 27 (scope rows, the work item, the run's own drafts, reference data) and the command limit of its rule 26 (`tainted_run_not_allowed`).

    For agent runs the owner of an intake or workflow is always the agent type setting's `workflow_owner_id` ([ADR-0050](0050-agent-runtime-and-query-layer.md) rule 15).
13. System jobs and consumers hold the permissions declared when they are registered; their `on_behalf_of` names the accountable human ([03](../spec/03-agent-safety.md) rule 3) but does not limit them, except where an ADR sets a condition on that human (e.g. close jobs in a soft-locked period need an `on_behalf_of` with `post_in_soft_locked_period`, ADR-0012 rule 5). Integrations get role assignments on their `integration_client` per company, like users; their accountable human is for accountability. Narrowed: a consumer command for an event with an origin agent run uses the intersection of the consumer's, the agent type's and the human's permissions, with no policy exception; such a command never posts or changes master data ([ADR-0029](0029-proposals-and-agent-safety.md) rule 12).
14. Agents never execute `human_only` commands; they may simulate them (ADR-0008 rule 2).

    Note: struck for agents: every agent actor runs under a tool list that holds no `human_only` command ([ADR-0050](0050-agent-runtime-and-query-layer.md) rules 29–30), and the tool list is checked first, so the call is refused with `tool_not_allowed` and no agent simulates such a command ([DS-04](../design/DS-04-command-envelope.md#dispatcher-check-order)).

**Approval and segregation of duties**

15. `Approve<Type>` and `Reject<Type>` are executed only by human actors ([07](../spec/07-shared-foundation.md#approval-engine): agents never approve on a human's behalf).
16. Each `document_version` records the full actor context of the command that wrote it: `actor_kind`, `actor_id`, `on_behalf_of_id`, `agent_run_id` and `origin_agent_run_id`: the agent run at the start of the chain that led to this write, carried on events and inherited through every consumer that reacts to them (ADR-0013 rules 2, 9), so a draft made two consumers away from an agent still counts. `Approve<Type>` is rejected with `segregation_of_duties` if any version of the document was written by an agent run, directly or through a consumer, whose `on_behalf_of` is the approving human ([03](../spec/03-agent-safety.md) rule 5). No policy or company setting relaxes this.

    Note ([ADR-0067](0067-quickflows-operating-presets.md), 2026-11-17 (proposed)): proposed for the author's confirmation: spec 03 rule 5's "the person who triggers" is read as the human whose own act started the run (a start command, a note or message they wrote, a work item they handed to the agent). This rule's check is stricter: it refuses every human the run acted for, the workflow owner of event and schedule runs included. It stays the default, and "no policy or company setting relaxes this" applies to the floor itself; only the small-company mode relaxes the stricter part, for untainted versions, as a recorded exception ([ADR-0054](0054-users-roles-and-authorizations.md) rule 20 note; [ADR-0067](0067-quickflows-operating-presets.md) rule 16).
17. Whether the human who triggered an agent may post that agent's draft without approval when the policy requires none, how a company of one or two people meets required approvals, and whether one human may be both preparer and approver of their own document ([03](../spec/03-agent-safety.md) rule 6) are open questions for the author, designed with DS-28 for step 5. Interim: rules 15–16 apply to every company; posting without approval follows the policy table, which is a stub that allows everything until DS-28 (ADR-0008 rule 5). The policy stub ends at step 5 with the table of [ADR-0043](0043-policy-and-approval.md).

    Note: proposed answers, flagged for the author: an explicit small-company exception mode ([ADR-0054](0054-users-roles-and-authorizations.md) rule 20), and stage approvals that exclude every writer of the document by default ([ADR-0055](0055-approval-pools-and-stages.md) rules 7, 20). The hard floor of rule 16 is never relaxed.

**Database defense**

18. Database roles: `nativeflows_migration` owns the schema and runs migrations, and is the only role with `BYPASSRLS`, so data migrations see every company; `nativeflows_app` runs commands and queries; `nativeflows_worker` runs delivery workers and system jobs; `nativeflows_claim` owns the delivery claim function and has a policy on `event_delivery` that sees every row, and nothing else; `nativeflows_readonly` serves the read-only query layer (DS-33); `nativeflows_check` runs the invariant checks, SELECT only and subject to RLS ([ADR-0022](0022-repository-and-engineering-conventions.md) rule 7; DS-16). Every table with `company_id` has `FORCE ROW LEVEL SECURITY`.

    `nativeflows_query_owner` (no login, never `BYPASSRLS`) owns the views of schema `query`; `nativeflows_readonly` reads only those views ([ADR-0050](0050-agent-runtime-and-query-layer.md) rule 43).

    Note ([ADR-0063](0063-configurable-policy-settings.md), proposed 2026-11-15): application roles (`nativeflows_app`, `nativeflows_worker`, `nativeflows_readonly`, `nativeflows_check`) get no `TEMPORARY` privilege on the database and SELECT only on `setting_definition`. Trigger functions and security-definer functions introduced from ADR-0063 on (from DS-28-settings.sql) name their tables with the schema and pin `search_path = nativeflows, pg_temp`, so a temporary table cannot stand in for a table they read; the trigger functions of the earlier DDL files follow as a DS-18 backlog item. The new no-login role `nativeflows_setting_reader` owns `setting_installation_value`, with one policy on `setting_value` that sees rows with a null company; EXECUTE on the function is revoked from PUBLIC and granted to the application roles (rules 1, 2).
19. Each transaction sets the current company with `set_config('nativeflows.company_id', …, true)`. Policies allow a row only when its `company_id`, compared as text, equals that setting; if the setting is missing, no row is visible (fail closed). Rows with a null `company_id` (installation-scoped events and deliveries, ADR-0013 rule 14) are visible only when the setting is the explicit value `installation`. A registered cross-company query (e.g. consolidation) sets `nativeflows.company_ids` to the companies the actor may see, and a second, read-only policy accepts those. Delivery workers claim `event_delivery` rows through one security-definer function owned by `nativeflows_claim`, which returns only the row and its company, then set the company before running the consumer (ADR-0013 rule 7). `idempotency_record` carries `company_id` and follows the same policies. Procrastinate's tables are technical, have no company and are reachable only by `nativeflows_worker`. Record scope and field classes stay in the dispatcher and in the read-only layer's views (DS-33); RLS guards companies only, as the second line of defense ([03](../spec/03-agent-safety.md) rule 4).

    The views apply field classes and record scope from session settings that the query layer sets, and the company policy applies to `nativeflows_query_owner` ([ADR-0050](0050-agent-runtime-and-query-layer.md) rules 43, 48).

    Note: the invited user's pending list (`ListPendingUserInvitation`) is a registered cross-company query: its `nativeflows.company_ids` are the companies holding a pending invitation for that user, found by a security-definer function owned by the no-login role `nativeflows_invitation` in the pattern of `nativeflows_claim`, and it returns only that user's rows; no role gains `BYPASSRLS` ([ADR-0054](0054-users-roles-and-authorizations.md) rule 3).

## Context

DS-15's envelope part is needed by ADR-0008 (dispatcher checks), ADR-0009 (approvals), ADR-0012 (soft-locked periods) and ADR-0013 (consumers). Constraints:

- Agents are principals with their own permissions; actor kinds human, agent, integration, system; an agent's effective permission is the intersection with the human it acts for; a system actor's `on_behalf_of` is the accountable human; record and field permissions by the canonical dimensions; query layer and MCP apply the same filters; RLS second line of defense; the person who triggers an agent must not approve its drafts; untrusted content limits a run ([03-agent-safety.md](../spec/03-agent-safety.md); Principles 4, 10). Agents never approve on a human's behalf; only the chief-accountant role posts in a soft-locked period ([07](../spec/07-shared-foundation.md)). Hard floors cannot be relaxed (03, 14).
- Authentication tools: argon2, pyotp, Authlib (ADR-0002). SAP practice: authorization objects beside transaction codes, role templates and default proposals on upgrade (D5).
- ADR-0005: hard floors and business behavior not in the spec are the author's.

## Options considered

| Option | For | Against |
| --- | --- | --- |
| Permissions generated from commands and queries, plus registered capabilities (chosen) | Nothing to keep in sync; agents can see exactly what they may call | Many permissions; roles bundle them |
| Role identity checks (e.g. "is chief accountant") | Simple | Breaks when a company renames or edits roles |
| System jobs limited by their human's rights | One rule for all | A warehouse keeper's posting event would fail the follow-on commands it triggers |
| RLS over all of a user's companies | One setting | A handler bug could touch another company; the transaction already knows its company |
| `on_behalf_of` from the email sender | Direct | Outside content would choose whose rights an agent uses |
| Relax segregation of duties for one-person companies | Practical | A hard floor; only the author may decide |

## Constraints that come with the decision

- DS-04 / ADR-0008: errors `permission_denied`, `record_not_found`, `segregation_of_duties`; `is_scope_filtered` in query results; capabilities in the registry.
- ADR-0008: the registry declares capabilities (rule 4). ADR-0009: `document_version` actor columns (rule 16). ADR-0012: rule 5 uses `post_in_soft_locked_period`. ADR-0013: `origin_agent_run_id` on events and consumer commands.
- DS-16: invariants that responses hold no field outside the actor's classes and that rules 15–16 hold.
- DS-18: database roles, `FORCE ROW LEVEL SECURITY`, policies generated per table, the claim function, the bootstrap command.
- DS-28: policy table, approval procedures, small teams, more record-scope dimensions (step 5).
- DS-29: work items for suspended schedules and intakes. DS-32: agent types, run tokens, tool lists, tainted runs, denial signals. DS-33: scope and field classes in semantic views. DS-36: audit of assignments and denials. DS-37: role template additions on upgrade.

## Revisit when

- A company needs record scope on a dimension outside rule 9 before step 5.
- Step 5 designs the full model (DS-15 full part, DS-28).

## Documents updated

- [docs/adr/0009-document-lifecycle.md](0009-document-lifecycle.md), [docs/adr/0012-posting-periods-and-closing.md](0012-posting-periods-and-closing.md), [docs/adr/0013-outbox-and-events.md](0013-outbox-and-events.md): notes for rules 16, 13 and 16.
- [docs/design/DS-04-command-envelope.md](../design/DS-04-command-envelope.md): error code `segregation_of_duties`.
- [docs/spec/00-reading-guide.md](../spec/00-reading-guide.md): actor row extended; rows for permission, capability, role, role assignment, record scope, field class.
- [docs/design/backlog.md](../design/backlog.md): DS-15 row links here (envelope part).
- [docs/adr/README.md](README.md): index row.
- [docs/open-questions.md](../open-questions.md): approvals in small companies, preparer and approver, posting one's agent's draft without approval; TOTP for every user.
- [docs/runbook/step-log.md](../runbook/step-log.md): entry.
