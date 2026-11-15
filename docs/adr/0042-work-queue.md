# ADR-0042: Work queue

Status: accepted (2026-11-14) under ADR-0005, reviewed by Claude Fable 5.2 (builder Claude Opus 5.5). Design item: DS-29. Related decisions: D2. Principles 3, 8, 12. ADR-0004, ADR-0007, ADR-0009, ADR-0012, ADR-0013, ADR-0017, ADR-0019, ADR-0023, ADR-0024, ADR-0027, ADR-0028, ADR-0029, ADR-0030, ADR-0031, ADR-0036, ADR-0037, ADR-0038, ADR-0040; spec 02, 03, 07, 14.

## Decision

Every exception, pending approval and other piece of business work is one `work_item` in module `work` (layer 2). A work item has:
- a registered kind;
- a subject;
- evidence links;
- an owner (a user, or a role within a record scope);
- a business due date;
- a state;
- a claim that makes a person or an agent run its only worker at a time.

**Raising and resolving.** Modules raise and resolve work items through `work.contract`, idempotently, by a key that allows one open item per exception. A person or agent takes an item by claiming it, and a person's claim always overrides an agent's: the agent's next command fails. Kinds are a registry catalog, so agents and people see one list.

**Agents and safety.** Agent runs start from work items (ADR-0013 rule 12); a run a person or a schedule starts gets an `agent_task` item of its own. The run's item is bound to the run, so the dispatcher checks the claim on every command. A run started from an item raised by a tainted event is tainted.

**Build order.** The core of `work` is built with the first agent, before step 5, because agents depend on it.

### Rules

**Kinds and items**

1. Work item kinds are registered by their owning module, like command types (ADR-0008 rule 1).
   - **Registration:** code, owning module, subject table, owner rule, due rule, `resolution` (`system` when the exception ends, `command` for the `resolution_command` it names, `person` for `ResolveWorkItem`), `is_agent_resolvable`, and meaning.
   - **Catalog.** [docs/catalogs/work-item-kinds.csv](../catalogs/work-item-kinds.csv) is seeded by this ADR with the kinds earlier ADRs named. Once `work` exists, the generator writes it from the registry.
   - **Names.** Kinds are `snake_case` names of the exception (ADR-0004), such as `short_pick` or `approval_pending`.
2. `work_item` columns:
   - **Identity:** `id`, `company_id`, `kind`, `subject_table`, `subject_id`, `open_key`.
   - **State:** `state` (`open`, `claimed`, `done`, `canceled`).
   - **Owner:**
     - `owner_kind` (`user` or `role`);
     - `owner_user_id`, or `owner_role` with its record-scope dimensions (`branch_id`, `warehouse_id`).
   - **Timing and display:**
     - `due_date` (a business date) and `priority` (`low`, `normal`, `high`);
     - `details`: parameters for the kind's i18n message, which hold IDs and amounts, never personal free text. Amounts keep their field classes and are filtered like any field (ADR-0017 rule 10).
   - **Provenance and outcome:**
     - `is_tainted`, `origin_event_id` and `origin_agent_run_id`;
     - `resolution` (a code) and `resolved_at`;
     - `version`.

   The table has `company_id`, row-level security and the generated company policy (ADR-0017 rule 19).
3. `work_item_link` (`work_item_id`, `target_table`, `target_id`, `link_kind`: `evidence`, `draft`, `result`) holds the evidence and what was done about it, such as a derivation trace, a pegging row, a task, a delivery, or a draft the agent made.
   - **Notes.** `work_item_note` (author, text, `created_at`) is append-only. A note an agent writes from outside content is marked untrusted (ADR-0029 rule 10).
4. Uniqueness. A unique partial index on (`company_id`, `kind`, `open_key`) where `state` is `open` or `claimed` allows one open item per exception.
   - **The default key** is the subject ID. A kind may compose the key, for example a work center and the start of an overloaded range (ADR-0036 rule 11).

**Raising and resolving (`work.contract`)**

5. `work.contract.raise_work_item(kind, subject, open_key, evidence, details, owner, due_date)` runs in the caller's transaction.
   - **Idempotent.** If an open item with the key exists, it adds the evidence, updates `details` and keeps the owner, claim and due date; no event is emitted. Otherwise it creates the item and emits `WorkItemRaised`.
   - **Owner and due date.** The calling module computes them by the kind's rules (rules 7, 8), because it knows buyers, calendars and periods, and applies the fallback of rule 7. Layer-2 callers (`documents`, `permissions`, `attachments`, `policy`, `agent_runs`) cannot reach the working calendar, so their `days:<n>` rules count calendar days.
   - **Taint.** `is_tainted` is the OR of the item's value and the raising event's or actor's taint, so a tainted re-raise taints an open item; `origin_agent_run_id` is kept from the first raise.
   - **Locks.** Work item rows are the last lock class (ADR-0027 rule 10), taken in (`kind`, `open_key`) order, so two commands raising items cannot deadlock.
   - **The plan.** Raised items are listed in the plan like events and never hashed (ADR-0008 rule 12).
6. `work.contract.resolve_work_item(kind, open_key, resolution)` closes the open item when the exception ends: a planning run no longer raises it (ADR-0024 rule 21), or a held posting completes (ADR-0028 rule 7). It sets `state: done`, `resolution` and `resolved_at`, and drops any claim. Resolving a key with no open item does nothing.
7. Owner rules:
   - **Kind rules:**
     - `buyer` (the product's or supplier's buyer, ADR-0018 rule 3; ADR-0027 rule 12);
     - `planning_owner` (ADR-0036 rule 11);
     - `warehouse_role` (role `warehouse_keeper` scoped to the subject's warehouse);
     - `document_owner` (the human who created the document or on whose behalf an agent did);
     - `issuer` (the human who issued an e-invoice);
     - `approver_role` (the procedure's approver role, ADR-0043);
     - `rule_owner` (a policy rule's owner, ADR-0043);
     - `company_owner` (the `owner` role);
     - `role:<role template>`, such as `role:accountant`, company-wide.
   - **Fallback.** When a rule yields no one, or the person is deactivated, the owner is the `owner` role. When an owner is deactivated after the raise, `permissions` raises `owner_suspended` with that person's open items as evidence, and the company's owner reassigns them with `AssignWorkItem`.
8. Due rules give business dates through the company calendar (ADR-0024 rule 4; calendar days for layer-2 callers, rule 5):
   - `same_day`, or `days:<n>` business days after the raise;
   - `required_date` minus the lead time, for planning;
   - `period_end` of the subject's posting period, for close items;
   - `subject_due_date`, the subject's own due date, such as a data subject request's.

   Overdue is a query condition. Escalation comes after Phase 1 (spec 07).

**Claims**

9. Claims are recorded on the work item: `claimed_by_kind` (`user`, `agent_run`), `claimed_by_id`, `claimed_at`, and `claim_expires_at` for agent claims.
   - **Commands.** `ClaimWorkItem` and `UnclaimWorkItem`. "Release" already means making a master data revision effective (ADR-0033), and a verb never takes a second meaning (ADR-0004 rule 20), so this ADR uses `Unclaim` instead of the `Release` that ADR-0012 foresaw.
   - **Transactions.** Claims run in their own transactions (ADR-0027 rule 10) and take no document or stock lock.
   - **No overlap with a takeover.** `ClaimWorkItem`, `AssignWorkItem` and the expiry job take the item row `FOR UPDATE`. Every command of an agent run bound to an item takes that row `FOR KEY SHARE` in its own transaction, first after its idempotency record (a note on ADR-0027 rule 10), and checks that the run still holds the claim. So no agent command commits after a person's claim. Raises and lease renewals are plain updates of non-key columns, which do not conflict with a key-share lock.
   - **Lease expiry.** A claim is valid while `claim_expires_at` is in the future. Renewal is a separate transaction. A job emits `WorkItemUnclaimed` for expired claims and sets the item back to `open`.
10. Who may claim:
    - **Visibility.** An item is visible to a caller who holds `ListWorkItem` and has the item's subject in their record scope, and who is its owner, holds its owner role in the item's scope, or holds the capability `list_all_work_items`.
    - **Claiming.** It needs `ClaimWorkItem` on a visible item.
    - **Agents.** An agent run claims only items whose kind its agent type declares (DS-32), within the permission intersection (ADR-0017 rule 11). Ownership is checked on the human the run acts for.
    - **Lease.** Agent claims expire after `work_claim_minutes` (company setting, default 30) unless renewed; a run renews on each command.

    Agent claims are taken by `StartAgentRun` and renewed by the runner ([ADR-0050](0050-agent-runtime-and-query-layer.md) rules 15–16).
11. Precedence and exclusion (Principle 8):
    - **A person over an agent.** A person's `ClaimWorkItem` on an item an agent run holds takes the claim. The dispatcher then rejects every later command of that run with `work_item_claim_lost` (rule 11, agent commands), so the agent stops and never works at the same time as a person.
    - **A person over a person.** Taking a claim from another person needs `AssignWorkItem`.
    - **An agent over anyone.** An agent run cannot take a held claim.
    - **Agent commands.** The run's work item is bound on `agent_run` when the run starts (DS-32). The dispatcher derives it from the credential, never from the request (ADR-0008 rule 8), and rejects any command of the run with `work_item_claim_lost` once the claim is gone. A held claim makes a second claimant fail with `work_item_claimed`.
    - **Runs without an exception.** A run a person or a schedule starts creates and claims an `agent_task` item for itself at its start, owned by the person the run acts for. No agent type may declare `agent_task`, so wake-ups cannot loop.

    Shadow runs bind their work item without a claim, and the dispatcher skips the claim check for them because they only simulate ([ADR-0050](0050-agent-runtime-and-query-layer.md) rule 14).
12. Other commands:
    - `AssignWorkItem` sets the owner and may clear a claim.
    - `ResolveWorkItem` (resolution code and note) is for kinds a person resolves.
    - `CancelWorkItem` takes a reason; the system cancels items whose subject is canceled or deleted.
    - `CreateWorkItemNote`.
13. Queries:
    - `ListWorkItem`, filtered by kind, state, owner (me, my roles), subject, due and overdue, with the visibility of rule 10;
    - `GetWorkItem`, with links, notes and claim.

    INV-42 and other checks use `ListWorkItem` by subject.
14. Events: `WorkItemRaised`, `WorkItemClaimed`, `WorkItemUnclaimed`, `WorkItemAssigned`, `WorkItemResolved`, `WorkItemCanceled`.
    - **Agent wake-ups.** Consumers that start agent runs (DS-32) react to `WorkItemRaised` for kinds an agent type declares.
    - **Live screens** update through ADR-0040 rule 13.

    The wake-up consumer is `agent_wake_up`; a kind that a command on an agent tool list can raise is declared by no agent type ([ADR-0050](0050-agent-runtime-and-query-layer.md) rule 16).

**Taint and agents**

15. An item raised by a tainted event, or by a tainted run, has `is_tainted`. A run started from it is tainted from its start (ADR-0029 rule 10), and its drafts are tainted versions.
16. Agents never `ResolveWorkItem` a kind that needs a person's judgement. Each kind declares `is_agent_resolvable`, default false.

**What raises work items**

17. Pending approvals and unconfirmed auto-posts are work items in Phase 1 (Principle 8):
    - **Pending approvals.** A document entering `pending_approval` raises `approval_pending`, owned by the procedure's approver role (ADR-0043). It is resolved by `Approve`, `Reject`, a new version, `Cancel` or `Delete`.
    - **Auto-posts.** Auto-posts add evidence to one `auto_post_unconfirmed` item per rule and period, owned by the rule's owner and due at period end; `ConfirmAutoPost` resolves it when the period's auto-posts are all confirmed.
    - **One exception, one kind.** A held delivery whose consumer has a kind of its own (for example e-invoice issuance, `e_invoice_outage`) raises that kind and not `event_delivery_held` (ADR-0031 rule 16).
    - **Invariants:**
      - **INV-204:** every document in `pending_approval` has exactly one open `approval_pending` item.
      - **INV-205:** no command of an agent run on an item is audited after a person's claim on that item.
    - **What stays later.** Delegation and escalation remain after Phase 1 (spec 07).
18. The catalog seeds the kinds that earlier ADRs name, with their owners:
    - planning exceptions (ADR-0024 rule 21; ADR-0036 rule 11);
    - warehouse exceptions (ADR-0023 rule 21);
    - change proposal execution failures (ADR-0029 rule 3);
    - held deliveries that matter to the business (ADR-0013 rule 8);
    - e-invoice posting held, issue date outside the window, rejection and outage (ADR-0028 rules 7, 8, 10);
    - a suspended owner (ADR-0017 rule 12);
    - unmatched messages, suspected duplicate partners and data subject requests (ADR-0019);
    - rejected attachments (ADR-0038 rule 14);
    - subcontracting order lines (ADR-0037 rule 4);
    - input VAT pending payment evidence and non-deductible (ADR-0041 rule 11).

    Unmatched bank lines and low stock (Principle 8) come with DS-25 and planning.

    `bank_line_unmatched` is added ([ADR-0048](0048-cash-bank-receivables-payables.md) rule 9).

    `agent_run_stopped`, `agent_budget_exhausted` and `agent_denials_repeated` are added ([ADR-0050](0050-agent-runtime-and-query-layer.md) rule 55); `inbound_message`, `supplier_invoice_received`, `agent_quality_below_threshold` and `import_duplicate_suspected` are added ([ADR-0051](0051-agent-workflows.md) rule 30).
19. Defects never enter the queue (ADR-0003 R7), and technical jobs are not work items (spec 07).

**Build order**

20. Agent runs start from work items, and the first agent comes after step 4 (spec 11), before step 5 builds the work queue. So the core of `work` is built with the first agent:
    - the tables;
    - raise and resolve;
    - claims;
    - `ListWorkItem`.

    The interim of ADR-0023 rule 21 (warehouse exceptions as tasks without assignee) and the per-buyer item of ADR-0024 rule 21 end when their kinds are registered. Moving this work in the runbook is the author's (open question).

## Context

Principle 8 makes exceptions, approvals, unmatched bank lines and low stock into work items that a person or an agent takes, never both at once. ADR-0031 rule 16 made every exception one work item. About fifteen earlier rules raise work items without a defined model.

SAP spreads this across workflow inboxes and situation handling. Odoo uses activities on records. ERPMe keeps one queue with a registered kind per exception, so agents and people work from the same list and an agent run always has one claimed item behind it.

## Options considered

| Option | For | Against |
| --- | --- | --- |
| One table with registered kinds (chosen) | One queue; agents and people share it; one claim model | Kinds need registration |
| A table per kind | Typed columns | Many queues; agents must learn each |
| Activities on records (Odoo) | Simple | No claim, no owner role, no evidence links |
| A person's claim overrides an agent's (chosen) | People stay in control; no simultaneous work | An agent run can be stopped midway, which its drafts' idempotency covers (ADR-0030 rule 11) |
| First claim wins for everyone | Simple | A person could wait on an agent |
| Owner as a role in a scope (chosen) | Warehouses and teams share items | Needs scope matching on read |

## Constraints that come with the decision

- **Catalogs:** `docs/catalogs/work-item-kinds.csv` (new; owned by DS-29, generated from the registry once `work` exists); INV-204, INV-205.
- **ADR notes:**
  - ADR-0004 rule 20 and the glossary: `Unclaim`;
  - ADR-0008 rules 1, 8: kinds as registry items; the run's work item derived from the credential;
  - ADR-0012: `Unclaim` instead of `Release`;
  - ADR-0013 rule 12: wake-ups on `WorkItemRaised`;
  - ADR-0023 rule 21 and ADR-0024 rule 21: their interims end;
  - ADR-0022 rule 2 and ADR-0027 rule 1: `work` in layer 2, imported by `registry`, `documents`, `policy`, `outbox`, `permissions`, `attachments`, `agent_runs` and layers 3–4, importing none of them;
  - ADR-0027 rule 10: the item row first after the idempotency record for agent commands, and work items as the last class for raises;
  - ADR-0029 rule 10: `is_tainted` on work items.
- **DS-04:** errors `work_item_claimed` and `work_item_claim_lost`.
- **Other design items:**
  - DS-32: agent types declare their kinds; `agent_run.work_item_id`; `agent_task` items; wake-up consumers; claim renewal;
  - DS-43 and DS-34: kinds of planning and workflows.
- **Open questions:**
  - building the core of `work` with the first agent (a runbook change);
  - pending approvals as work items in Phase 1;
  - a person's claim overriding an agent's;
  - the 30-minute lease.

## Revisit when

- Escalation, delegation or service-level timers are needed.
- One kind produces so many items that people batch them by hand.

## Documents updated

- **Catalogs:** [docs/catalogs/work-item-kinds.csv](../catalogs/work-item-kinds.csv) (new), [docs/catalogs/README.md](../catalogs/README.md).
- **ADRs:** [docs/adr/0008-command-envelope-and-registry.md](0008-command-envelope-and-registry.md), [docs/adr/0022-repository-and-engineering-conventions.md](0022-repository-and-engineering-conventions.md), [docs/adr/0012-posting-periods-and-closing.md](0012-posting-periods-and-closing.md), [docs/adr/0013-outbox-and-events.md](0013-outbox-and-events.md), [docs/adr/0023-warehouse-management.md](0023-warehouse-management.md), [docs/adr/0024-planning.md](0024-planning.md), [docs/adr/0027-cross-cutting-ownership.md](0027-cross-cutting-ownership.md), [docs/adr/0029-proposals-and-agent-safety.md](0029-proposals-and-agent-safety.md): notes.
- **Design files:** [docs/design/DS-04-command-envelope.md](../design/DS-04-command-envelope.md), [docs/design/backlog.md](../design/backlog.md).
- **Glossary:** [docs/spec/00-reading-guide.md](../spec/00-reading-guide.md).
- **Open questions:** [docs/open-questions.md](../open-questions.md).
- **Index and log:** [docs/adr/README.md](README.md); [docs/runbook/step-log.md](../runbook/step-log.md) at acceptance.
