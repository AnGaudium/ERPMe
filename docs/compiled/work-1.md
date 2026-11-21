Module: work    Chunk: 1 of 2    Source ADRs: ADR-0031, ADR-0042, ADR-0055, ADR-0066
Build step(s): 4, 5, 7    Generated from index: 30d5706    Compiled by: Claude Fable 5.2, 2026-11-21

# Compiled spec: `work`, chunk 1

## Purpose

`work` (layer 2) owns the work queue: every exception, pending approval and other piece of business work is one `work_item`, raised and resolved by other modules through `work.contract` and taken by a person or an agent run through a claim. This chunk states the work item, its kinds, owners, due dates, claims, commands, queries and events, the approval work item, and the table `work_case` with the principle that a work case only links. The other rules of work cases, and messaging and notifications, are in chunk 2. `work` owns no approval rule, no agent run and no kind's meaning: kinds are registered by their owning modules.

## Entities and tables

DDL: `docs/design/DS-05-platform.sql`.

| Table | Meaning | Key | Parent | Owner |
| --- | --- | --- | --- | --- |
| `work_item` | One exception, pending approval or piece of business work, with its owner, due date, state and claim (R6 to R9, R35) | `id`; unique (`company_id`, `id`); unique partial (`company_id`, `kind`, `open_key`) while `open` or `claimed` (R13) | `company`; optional `work_case` | `work` |
| `work_item_link` | Evidence of a work item and what was done about it (R11) | `id`; unique (`work_item_id`, `target_table`, `target_id`, `link_kind`) | `work_item` | `work` |
| `work_item_note` | Append-only note on a work item (R12) | `id` | `work_item` | `work` |
| `work_case` | One business intent that groups work items and their results by links only (R84 to R88) | `id`; unique (`company_id`, `id`); unique partial (`company_id`, `kind`, `open_key`) while `open` (R88) | `company` | `work` |

`work_case_link` and the messaging tables have their rows in chunk 2.

Reads: `company`, `user_account`, `role` (`template_code`), `branch`, `warehouse`, `partner`, `approval_stage`, `approval_stage_member`, `agent_run` (`on_behalf_of_id`), `document` (`created_by_user_id`), `audit_record`; catalogs `work-item-kinds.csv`, `role-templates.csv`, `authorization-areas.csv`, `authorization-verb-levels.csv`.

## Commands and queries

Areas and levels are those of `authorization-areas.csv` (leaves `work_queue` and `work_queue_administration`, owned by `work`) and `authorization-verb-levels.csv`. The events of the module are listed in R57; the sources bind them to a command only where the table says so.

| Name | Actor and authorization | Input | Effect | Events | Error codes |
| --- | --- | --- | --- | --- | --- |
| `ClaimWorkItem` | A person on a visible item (R40, R43); `work_queue`, verb `Claim` at `edit`. Agent claims are taken by `StartAgentRun` (R45) | not stated | Records the claim (R35); a person's claim takes an agent run's (R47) | not stated | `work_item_claimed` (R50) |
| `UnclaimWorkItem` | `work_queue`, verb `Unclaim` at `edit` | not stated | Ends the claim (R35) | not stated | not stated |
| `AssignWorkItem` | `work_queue_administration` at `full`; the company's owner reassigns a deactivated owner's items with it (R27) | not stated | Sets the owner and may clear a claim (R52); takes a claim from another person (R46) | not stated | not stated |
| `ResolveWorkItem` | `work_queue`, verb `Resolve` at `edit`; for kinds a person resolves; never an agent (R60) | Resolution code and note | Resolves the item (R52) | not stated | not stated |
| `CancelWorkItem` | `work_queue_administration` at `full` | A reason | Cancels the item (R52) | not stated | not stated |
| `CreateWorkItemNote` | `work_queue`, verb `Create` at `edit` | not stated | Adds a `work_item_note` row (R12, R52) | not stated | not stated |
| `ListWorkItem` (query) | `work_queue`, verb `List` at `read`; visibility of R40 to R42; capability `list_all_work_items` (`work_queue_administration` at `full`) | Filters: kind, state, owner (me, my roles), subject, due, overdue | Lists visible work items (R56) | None (query) | not stated |
| `GetWorkItem` (query) | `work_queue`, verb `Get` at `read` | not stated | One item with links, notes and claim (R56) | None (query) | not stated |

Not registered commands: the contract functions `work.contract.raise_work_item` (R14 to R19; emits `WorkItemRaised` when it creates an item; the verb `Raise` at `edit` in `authorization-verb-levels.csv` is used by no command type yet) and `work.contract.resolve_work_item` (R20); the claim expiry job (R39; emits `WorkItemUnclaimed`); the registered visibility function of `work` (R10, R41, R68). Consumers of other modules that react to this module's events: `agent_wake_up` (R57) and `messaging_fanout` (R58).

Error code raised by the dispatcher, bound to no command of `work`: `work_item_claim_lost` (R47, R48).

## Rules

### The work item

R1. From step 5, every exception is one `work_item` (DS-29) with `kind`, `subject` (table and ID), `evidence` (links to a derivation trace, pegging, task or delivery), `owner` and `due_date`. The claimable unit is the single work item (Principle 8). Lists per buyer, warehouse or close are queries. Planning exception rows and short-pick tasks remain as evidence in their domain.
Source: ADR-0031.R16

R2. Every exception, pending approval and other piece of business work is one `work_item` in module `work` (layer 2). It has a registered kind, a subject, evidence links, an owner (a user, or a role within a record scope), a business due date, a state, and a claim that makes one person or one agent run its only worker at a time. Modules raise and resolve work items through `work.contract`, idempotently, by a key that allows one open item per exception. Kinds are a registry catalog, so agents and people see one list.
Source: ADR-0042.D0

R3. Agent runs start from work items (ADR-0013.R12); a run that a person or a schedule starts gets an `agent_task` item of its own. The run's item is bound to the run, so the dispatcher checks the claim on every command. A run started from an item raised by a tainted event is tainted.
Source: ADR-0042.D0

R4. Defects never enter the queue (ADR-0003.R7), and technical jobs are not work items (spec 07).
Source: ADR-0042.R19

R5. The work queue is built at step 5, as item 1 of that step in the runbook (`docs/runbook/steps-5-9.md`), and the first agent comes after it. The core of `work` is the tables, raise and resolve, claims, and `ListWorkItem`. The interim of ADR-0023.R21 (warehouse exceptions as tasks without assignee) and the per-buyer item of ADR-0024.R21 end when their kinds are registered.
Source: ADR-0042.R20, ADR-0042.R20.N1

### Table `work_item`

R6. `work_item` columns:
- identity: `id`, `company_id`, `kind`, `subject_table`, `subject_id`, `open_key`;
- state: `state` (`open`, `claimed`, `done`, `canceled`);
- owner: `owner_kind` (`user`, `role` or `approval_stage`); `owner_user_id`; or `owner_role` with its record-scope dimensions (`branch_id`, `warehouse_id`); or `owner_approval_stage_id`;
- timing and display: `due_date` (a business date) and `priority` (`low`, `normal`, `high`); `details`, the parameters for the kind's i18n message, which hold IDs and amounts, never personal free text; amounts keep their field classes and are filtered like any field (ADR-0017.R10);
- provenance and outcome: `is_tainted`, `origin_event_id` and `origin_agent_run_id`; `resolution` (a code) and `resolved_at`; `version`; the DDL adds `recorded_at`.
Source: ADR-0042.R2, ADR-0042.R2.N1

R7. `work_item` has `company_id`, row-level security and the generated company policy (ADR-0017.R19).
Source: ADR-0042.R2

R8. An item whose `owner_kind` is `approval_stage` is visible to everyone eligible for the stage named by `owner_approval_stage_id` (R68).
Source: ADR-0042.R2.N1

R9. `work_item` has `work_case_id` (nullable), set once and kept by a re-raise; the item then belongs to that work case. A case only links: no rule of the work queue changes for an item in a case (ADR-0066.R10).
Source: ADR-0042.R2.N3

R10. `owner_role` stores the symbolic rule, never a role ID: the bare template code (for example `accountant`) or `company_owner`, with its scope dimensions. `role:<template>` is the notation of the kind catalog, resolved to that column when the item is raised. Who holds the role, and the fallback to `company_owner` when no active role has the template, are resolved when the item is read, by the registered visibility function (ADR-0054.R2, ADR-0054.R11). So the holders of every active role with that template code own the item, and a role created later counts at once.
Source: ADR-0042.R2.N2, ADR-0042.R7.N4

R11. `work_item_link` (`work_item_id`, `target_table`, `target_id`, `link_kind`: `evidence`, `draft`, `result`) holds the evidence and what was done about it, such as a derivation trace, a pegging row, a task, a delivery, or a draft the agent made.
Source: ADR-0042.R3

R12. `work_item_note` is append-only. Its columns are `author_kind` (`user`, `agent_run`, `system`), `author_id` (a user or an agent run, null for `system`), `body_text`, `is_untrusted` and `recorded_at`, which is the `created_at` of the note. A note that an agent writes from outside content is marked untrusted (ADR-0029.R10). `author_kind` and `author_id` are interim in the DDL: the rule names only an author.
Source: ADR-0042.R3

R13. A unique partial index on (`company_id`, `kind`, `open_key`) where `state` is `open` or `claimed` allows one open item per exception. The default key is the subject ID. A kind may compose the key, for example a work center and the start of an overloaded range (ADR-0036.R11).
Source: ADR-0042.R4

### Raise and resolve

R14. `work.contract.raise_work_item(kind, subject, open_key, evidence, details, owner, due_date)` runs in the caller's transaction and is idempotent. If an open item with the key exists, it adds the evidence, updates `details` and keeps the owner, claim and due date; no event is emitted. Otherwise it creates the item and emits `WorkItemRaised`.
Source: ADR-0042.R5

R15. The calling module computes the owner and the due date by the kind's rules (R27 to R33), because it knows buyers, calendars and periods. It computes user-kind owners and applies their fallback (R27) at raise. A role-kind owner is stored as the symbolic rule (R10) and resolved at read time, so layer-2 callers need no import to learn whether a role with the template exists. Layer-2 callers (`documents`, `permissions`, `attachments`, `policy`, `agent_runs`) cannot reach the working calendar, so their `days:<n>` rules count calendar days.
Source: ADR-0042.R5, ADR-0042.R5.N1

R16. On a raise, `is_tainted` is the OR of the item's value and the raising event's or actor's taint, so a tainted re-raise taints an open item. `origin_agent_run_id` is kept from the first raise.
Source: ADR-0042.R5

R17. Work item rows are the last lock class (ADR-0027.R10), taken in (`kind`, `open_key`) order, so concurrent commands raising items cannot deadlock.
Source: ADR-0042.R5

R18. Raised items are listed in the plan like events and never hashed (ADR-0008.R12).
Source: ADR-0042.R5

R19. `raise_work_item` takes an optional `work_case_id`. Without one, it sets the case when the subject is an `artifact` target of exactly one open work case, or a `draft`-linked target of a work item of exactly one open case. Both lookups read only the tables of `work` (ADR-0066.R10).
Source: ADR-0042.R5.N2

R20. `work.contract.resolve_work_item(kind, open_key, resolution)` closes the open item when the exception ends: a planning run no longer raises it (ADR-0024.R21), or a held posting completes (ADR-0028.R7). It sets `state: done`, `resolution` and `resolved_at`, and drops any claim. Resolving a key with no open item does nothing.
Source: ADR-0042.R6

### Kinds

R21. Work item kinds are registered by their owning module, like command types (ADR-0008.R1). A registration names: code, owning module, subject table, owner rule, due rule, `resolution`, `resolution_command`, `is_agent_resolvable`, and meaning. For the kind rules `subject_owner` and `subject_assignee` it also names the subject column that holds the user (R30).
Source: ADR-0042.R1, ADR-0042.R1.N1

R22. `resolution` is `system` when the exception ends, `command` for a kind with a `resolution_command`, and `person` for `ResolveWorkItem`. `bank_line_unmatched` is `system`, closed when its line is matched or ignored, with no resolution command.
Source: ADR-0042.R1, ADR-0042.R1.N1

R23. `docs/catalogs/work-item-kinds.csv` is the kind catalog; once `work` exists, the generator writes it from the registry. Kinds are `snake_case` names of the exception (ADR-0004), such as `short_pick` or `approval_pending`.
Source: ADR-0042.R1

R24. The catalog holds the kinds that other ADRs name, with their owners: planning exceptions (ADR-0024.R21, ADR-0036.R11); warehouse exceptions (ADR-0023.R21), such as `short_pick`; change proposal execution failures (ADR-0029.R3); held deliveries that matter to the business (ADR-0013.R8), `event_delivery_held`; e-invoice posting held, issue date outside the window, rejection and outage (ADR-0028.R7, ADR-0028.R8, ADR-0028.R10), such as `e_invoice_outage`; a suspended owner (ADR-0017.R12), `owner_suspended`; unmatched messages, suspected duplicate partners and data subject requests (ADR-0019), such as `interaction_unmatched`; rejected attachments (ADR-0038.R14), `attachment_rejected`; subcontracting order lines (ADR-0037.R4); input VAT pending payment evidence and non-deductible (ADR-0041.R11); `bank_line_unmatched` (ADR-0048.R9); `agent_run_stopped`, `agent_budget_exhausted` and `agent_denials_repeated` (ADR-0050.R55); `inbound_message_matched`, `supplier_invoice_received`, `agent_quality_below_threshold` and `import_duplicate_suspected` (ADR-0051.R30). Low stock (Principle 8) comes with planning.
Source: ADR-0042.R18, ADR-0042.R18.N1

R25. The work item kind for a matched inbound e-mail is `inbound_message_matched` (ADR-0052.R15); `inbound_message` is only the name of the table of `crm` (ADR-0052.R13).
Source: ADR-0042.R18.N1

R26. Module `automation` registers the kinds `automation_task`, `automation_notice`, `automation_rule_disabled`, `automation_owner_scope_narrowed`, `artifact_invalidated`, `artifact_reference_deprecated`, `artifact_demoted` and `artifact_function_changed` (ADR-0058.R28, ADR-0059.R28).
Source: ADR-0042.R18.N2

### Owner rules

R27. Fallback of the owner. When a kind rule yields no one, or the person is deactivated, the owner is `company_owner`. When an owner is deactivated after the raise, `permissions` raises `owner_suspended` with that person's open items as evidence, and the company's owner reassigns them with `AssignWorkItem`.
Source: ADR-0042.R7, ADR-0042.R7.N3

R28. The owner kind rules are:
- `buyer`: the product's or supplier's buyer (ADR-0018.R3, ADR-0027.R12);
- `planning_owner` (ADR-0036.R11);
- `planning_node_owner`: the company's `planning_owner_id` when the subject node's `replenishment_source` is `production`, otherwise `buyer`; kind `planning_exception` uses it (ADR-0024.R21);
- `warehouse_role`: the template `warehouse_keeper` scoped to the subject's warehouse;
- `document_owner`: the human who created the document or on whose behalf an agent did, read from the document's `created_by_user_id` (ADR-0054.R14), not its owner employee;
- `issuer`: the human of the `Issue` of an e-invoice: its actor, or its `on_behalf_of`;
- `approval_stage`: the item of the current approval stage (R67 to R72);
- `rule_owner`: a policy rule's owner (ADR-0043);
- `company_owner`: the `owner` role template;
- `role:<role template>`, such as `role:accountant` or `role:sales_clerk`, company-wide;
- `run_on_behalf_of` (R29);
- `subject_owner:<column>` and `subject_assignee:<column>` (R30);
- `named_by_raiser` (R32).
Source: ADR-0042.R7, ADR-0042.R7.N1, ADR-0042.R7.N2, ADR-0042.R7.N3

R29. `run_on_behalf_of` is `agent_run.on_behalf_of_id` of the subject run, or of the raising run when the subject is not a run (`agent_run_stopped`, whose subject is the agent type). A re-raise keeps it (R14).
Source: ADR-0042.R7.N3

R30. `subject_assignee:<column>` names the user the subject names as assignee, such as a follow-up task's; `subject_owner:<column>` names the user the subject names as owner, such as a mailbox's `owner_user_id` (ADR-0052.R12, ADR-0052.R19). The user is read from the subject column that the kind's registration names (R21), which may go through one reference as `<reference column>.<column>`. Catalog values:
- `mailbox_unreachable`: `subject_owner:owner_user_id`;
- `follow_up_due`: `subject_assignee:assignee_user_id`;
- `attachment_rejected`: `subject_owner:created_by_user_id`, the uploader (the human of `CreateAttachment`, a column of the attachment row);
- `import_duplicate_suspected`: `subject_owner:import_batch_id.created_by_user_id`, the batch creator.
Source: ADR-0042.R7, ADR-0042.R7.N3

R31. `role:<template>` and `company_owner` resolve through `role.template_code`, never role codes. When no active role has the template, the owner is `company_owner` (ADR-0054.R11). The item of kind rule `approval_stage` falls back to `company_owner` with a reason when nobody could approve (R69).
Source: ADR-0042.R7.N1

R32. `named_by_raiser` serves for owner and due date: the raiser names a user, a role template, `document_owner` of its subject or a decision table output, and N business days. The kinds `automation_task` and `automation_notice` use it. `automation_rule_disabled`, `artifact_demoted`, `artifact_invalidated`, `artifact_reference_deprecated` and `artifact_function_changed` use it for the owner, falling back to `company_owner` when the named owner can no longer open the company. A raiser that names several owners raises one item per owner, with the owner in the open key (ADR-0059.R4, ADR-0059.R28).
Source: ADR-0042.R7.N5

### Due rules

R33. Due rules give business dates through the company calendar (ADR-0024.R4); for layer-2 callers they count calendar days (R15). The rules are:
- `same_day`, or `days:<n>` business days after the raise;
- `required_date` minus the lead time, for planning;
- `period_end` of the subject's posting period, for close items;
- `subject_due_date`, the subject's own due date, such as a data subject request's;
- `stage_due_days`: the day the approval stage became current plus its `due_days`, in calendar days;
- `named_by_raiser` (R32).
Source: ADR-0042.R8, ADR-0042.R8.N1, ADR-0042.R7.N5

R34. Overdue is a query condition. Approval stages escalate in Phase 1 (ADR-0055.R12, ADR-0055.R13); escalation of other work items comes after Phase 1 (spec 07).
Source: ADR-0042.R8, ADR-0042.R8.N1

### Claims

R35. Claims are recorded on the work item: `claimed_by_kind` (`user`, `agent_run`), `claimed_by_id`, `claimed_at`, and `claim_expires_at` for agent claims. The commands are `ClaimWorkItem` and `UnclaimWorkItem`. The verb is `Unclaim` because `Release` means making a master data revision effective (ADR-0033) and a verb never takes a second meaning (ADR-0004.R20).
Source: ADR-0042.R9

R36. Claims run in their own transactions (ADR-0027.R10) and take no document or stock lock.
Source: ADR-0042.R9

R37. No overlap with a takeover. `ClaimWorkItem`, `AssignWorkItem` and the expiry job take the item row `FOR UPDATE`. Every command of an agent run bound to an item takes that row `FOR KEY SHARE` in its own transaction, first after its idempotency record, and checks that the run still holds the claim. So no agent command commits after a person's claim. Raises and lease renewals are plain updates of non-key columns, which do not conflict with a key-share lock.
Source: ADR-0042.R9

R38. The claim check is step 7 of the dispatcher's check order, after the idempotency lookup of step 6: a replay returns its stored response before it, simulations run it at the same position without writing a record, and shadow runs skip it (DS-04, dispatcher check order).
Source: ADR-0042.R9.N1

R39. A claim is valid while `claim_expires_at` is in the future. Renewal is a separate transaction. A job emits `WorkItemUnclaimed` for expired claims and sets the item back to `open`.
Source: ADR-0042.R9

R40. An item is visible to a caller who holds `ListWorkItem` and has the item's subject in their record scope, and who is its owner, holds its owner role in the item's scope, or holds the capability `list_all_work_items`. Claiming needs `ClaimWorkItem` on a visible item.
Source: ADR-0042.R10

R41. An item whose subject is a document, or a line of one, is visible only when the caller's read owner scope reaches the document; `work` applies it through a registered visibility function (ADR-0054.R2, ADR-0054.R15).
Source: ADR-0042.R10.N1

R42. The person holding a work item's claim also reads and edits the drafts linked to it (`link_kind` `draft`) while the claim holds, beyond their owner scope but within their permissions and record scope (ADR-0054.R14).
Source: ADR-0042.R10.N2

R43. An agent run claims only items whose kind its agent type declares (DS-32), within the permission intersection (ADR-0017.R11). A run that a person starts on an item checks ownership on that person. A run from a wake-up claims an item when its agent type declares the kind: ownership is not checked on the workflow owner it acts for, who need not hold the item's owner role.
Source: ADR-0042.R10, ADR-0042.R10.N2

R44. Agent claims expire after `work_claim_minutes` (company setting, default 30) unless renewed; a run renews on each command.
Source: ADR-0042.R10

R45. Agent claims are taken by `StartAgentRun` and renewed by the runner (ADR-0050.R15, ADR-0050.R16).
Source: ADR-0042.R10

### Precedence and exclusion (Principle 8)

R46. An agent run cannot take a held claim. Taking a claim from another person needs `AssignWorkItem`.
Source: ADR-0042.R11

R47. A person's `ClaimWorkItem` on an item that an agent run holds takes the claim. The dispatcher then rejects every later command of that run with `work_item_claim_lost`, so the agent stops and never works at the same time as a person (`INV-205`).
Source: ADR-0042.R11

R48. The work item of a run is bound on `agent_run` when the run starts (DS-32). The dispatcher derives it from the credential, never from the request (ADR-0008.R8), and rejects any command of the run with `work_item_claim_lost` once the claim is gone.
Source: ADR-0042.R11

R49. Shadow runs bind their work item without a claim, and the dispatcher skips the claim check for them because they only simulate (ADR-0050.R14).
Source: ADR-0042.R11

R50. A held claim makes a second claimant fail with `work_item_claimed`.
Source: ADR-0042.R11

R51. A run that a person or a schedule starts creates and claims an `agent_task` item for itself at its start, owned by the person the run acts for. No agent type may declare `agent_task`, so wake-ups cannot loop.
Source: ADR-0042.R11

### Other commands and queries

R52. `AssignWorkItem` sets the owner and may clear a claim. `ResolveWorkItem` (resolution code and note) is for kinds a person resolves. `CancelWorkItem` takes a reason; the system cancels items whose subject is canceled or deleted. `CreateWorkItemNote` adds a note.
Source: ADR-0042.R12

R53. Bulk review. A person may select several work items or drafts in the work queue and submit or approve them together when every selected item:
- is a draft or change proposal whose field values are all trusted (ADR-0057.R17: no `is_untrusted` field, extraction values as the trust view serves them) and whose simulation returns no check result;
- passes every check of the dispatcher's order for that person, shown by its own simulation, so eligibility, segregation of duties and approval stages hold for each item; and
- is executed as its own command, with its own idempotency key, `expected_plan_hash`, `as_of_date`, audit record and approval record; there is no batch command, no batch approval record and no shared plan hash.
Source: ADR-0042.R12.N1

R54. In a bulk review the UI simulates each item, lists them with each plan's summary, and on one confirmation sends one execution per item. An item that fails a condition, or whose execution fails, stays in the queue for single review; the others are unaffected. `work.bulk_review_max_items` (company, default 50, bounds 1 to 500) caps one selection. Bulk review is a person's action in the UI, on no agent tool list and never an automation action; a person still submits or approves each item (spec 03).
Source: ADR-0042.R12.N1

R55. The case view offers the bulk review of R53 and R54 for the pending commands of one work case, under the same conditions and the same cap `work.bulk_review_max_items`: one command, idempotency key, plan hash and approval record per item (ADR-0066.R16).
Source: ADR-0042.R12.N2

R56. Queries: `ListWorkItem`, filtered by kind, state, owner (me, my roles), subject, due and overdue, with the visibility of R40 to R42; and `GetWorkItem`, with links, notes and claim. `INV-42` and other checks use `ListWorkItem` by subject.
Source: ADR-0042.R13

### Events

R57. Events: `WorkItemRaised`, `WorkItemClaimed`, `WorkItemUnclaimed`, `WorkItemAssigned`, `WorkItemResolved`, `WorkItemCanceled`. Consumers that start agent runs (DS-32) react to `WorkItemRaised` for kinds an agent type declares; the wake-up consumer is `agent_wake_up`. A kind that a command on an agent tool list can raise is declared by no agent type (ADR-0050.R16). Live screens update through ADR-0040.R13.
Source: ADR-0042.R14

R58. The transactional consumer `messaging_fanout` turns `WorkItemRaised` and `WorkItemAssigned` into a `work_item` notification: to the owning user; for an item owned by an approval stage, to at most 20 eligible members, the first 20 from the top of the stage's member list. An item owned by the role `company_owner` notifies its holders, and an item owned by any other role notifies nobody (ADR-0076.R6).
Source: ADR-0042.R14.N1

### Taint and agents

R59. An item raised by a tainted event, or by a tainted run, has `is_tainted`. A run started from it is tainted from its start (ADR-0029.R10), and its drafts are tainted versions.
Source: ADR-0042.R15

R60. Agents never `ResolveWorkItem` a kind that needs a person's judgement. Each kind declares `is_agent_resolvable`, default false, and it is false for every Phase 1 kind, since resolve commands are on no tool list (ADR-0050.R30).
Source: ADR-0042.R16, ADR-0042.R1.N1, ADR-0042.R16.N1

R61. The work model is stated in ADR-0078.R11 and ADR-0078.R12. The work item is the unit of work for people, deterministic code and agents; an agent run is one attempt at it and never resolves it. The kind is the contract between a domain module and whoever does the work: the module names no agent type, and at most one agent type declares a given kind.
Source: ADR-0042.R16.N1

### Approvals and auto-posts as work items

R62. Pending approvals and unconfirmed auto-posts are work items in Phase 1 (Principle 8).
Source: ADR-0042.R17

R63. A document entering `pending_approval` raises `approval_pending`, owned by its current approval stage (R67, R68). It is resolved by `Approve`, `Reject`, a new version, `Cancel` or `Delete`.
Source: ADR-0042.R17, ADR-0042.R17.N1

R64. Auto-posts add evidence to one `auto_post_unconfirmed` item per policy rule and confirmation window, owned by the rule's owner and due at the window's end; `ConfirmAutoPost` resolves it when the window's auto-posts are all confirmed. The window is set by `auto_post.confirmation_cadence`: the posting period by default, or the ISO week or the business date (ADR-0065.R7; ADR-0043.R14.N5). The kind's due rule in the catalog is `named_by_raiser`.
Source: ADR-0042.R17

R65. One exception, one kind. A held delivery whose consumer has a kind of its own (for example e-invoice issuance, `e_invoice_outage`) raises that kind and not `event_delivery_held` (ADR-0031.R16).
Source: ADR-0042.R17

R66. `INV-204`: every document in `pending_approval` has exactly one open `approval_pending` item. `INV-205`: no command of an agent run on an item is audited after a person's claim on that item.
Source: ADR-0042.R17

R67. Pending stages are work items. A document in `pending_approval` has exactly one open `approval_pending` item, for its current stage (`INV-204`). Its open key is the document ID. When a stage completes, its item is resolved and the next stage's item is raised in the same transaction. Delegation and escalation of approvals are in Phase 1 (ADR-0055.R13, ADR-0055.R14).
Source: ADR-0055.R12, ADR-0042.R17.N1

R68. The approval item has owner kind `approval_stage` with `owner_approval_stage_id`. It is visible to everyone eligible under ADR-0055.R7: members in scope, substitutes in force, and escalation holders once overdue, through the registered visibility function of ADR-0055.R1.
Source: ADR-0055.R12

R69. Fallback to the owner. When nobody could approve the current stage, the item's owner becomes `company_owner` (R27; ADR-0054.R11), with the stage and a reason in `details`: `members_left` (no member holds the role or permission any more), `members_disabled`, `members_all_writers` or `members_all_counted`, or `stage_inactive` or `pool_inactive` (deactivated after the plan was recorded). The checks of ADR-0055.R4 keep a selector from naming an inactive pool and an active pool from having no stage, so those states need no reason of their own.
Source: ADR-0055.R12

R70. The fallback of R69 is checked when the stage becomes current and by the daily `RunApprovalEscalation` job (ADR-0055.R13), which moves the item back to the stage once someone is eligible again. Nobody is eligible for a stage of a recorded plan whose stage or pool was deactivated afterwards. The owner fixes the members or reactivates the stage, or the author updates or cancels the document, and a new submission takes the stages then in force.
Source: ADR-0055.R12

R71. The due date of the approval item is the day the stage became current plus the stage's `due_days`, in calendar days, because `documents` is a layer-2 caller (R15). The kind's due rule is `stage_due_days`.
Source: ADR-0055.R12

R72. `Approve` needs no claim, and a claim never stops another eligible person from approving, since a stage may need several approvers. An agent type may declare `approval_pending` only to prepare the approval file (spec 07: summary, history, risks) as notes and evidence. Agents never approve (ADR-0017.R15).
Source: ADR-0055.R12

### Work cases: principle and table `work_case`

R80. A work case groups everything about one business intent: the origin that started it, the work items raised along the way, the agent runs on them, the drafts and change proposals they made, and the documents that resulted. A case only links: documents stay the single source of truth, and the case's timeline is composed by query, never copied. A case changes no core rule: no lifecycle, approval, segregation of duties, taint, simulation, lock order or posting rule. Every human action taken from a case is its own command through the same dispatcher. A case never widens an agent's read scope.
Source: ADR-0066.D0

R81. Cases serve unstructured and exception work; routine structured work keeps the list, form and keyboard grid screens of ADR-0040 and the hand-built screens. The axis is "unstructured or exception" against "routine structured", not external against internal:
- unstructured or exception work, mostly external, uses cases: quote requests, customer issues, supplier invoices arriving by mailbox, new-customer onboarding;
- routine structured work, mostly internal, keeps the traditional screens: journal entries, stock movements, production orders, period close;
- internal exceptions may use cases later without re-architecture: a shortage, a count difference, a cost-variance investigation, a close issue, an engineering change;
- routine external flows need none: bank statements, signed e-invoice XML, EDI.
Source: ADR-0066.D0

R82. `work_case` is generic. Case kinds are a registered catalog, and each company decides through settings (ADR-0063) which kinds it uses and whether they open by themselves, by an automation rule, or only by a person. Phase 1 seeds the external kinds `quote_request`, `customer_issue`, `supplier_invoice` and `customer_onboarding`; ADR-0066.R3.N1 and ADR-0066.R3.N2 add the kinds `nonconformance` and `production_disruption`. Every kind is `off` until the company turns it on, so the defaults reproduce the behavior without cases.
Source: ADR-0066.D0

R83. These stay rejected: one approval across a purchase request, purchase order and goods receipt; clearing taint for a whole task; one simulation for a set of documents whose later steps depend on earlier postings; replacing lists and grids with an issue tracker.
Source: ADR-0066.D0

R84. A work case is optional context. No command requires a case, no handler reads one, and no document, posting or approval depends on one. Removing every case leaves the books, stock and approvals unchanged. A case kind exists for unstructured or exception work; routine structured flows get no kind.
Source: ADR-0066.R1

R85. `work_case` lives in module `work` (layer 2) and is a company table under row-level security (ADR-0017.R19). It holds:
- identity: `id`, `company_id`, `kind`, and `open_key`, the origin's ID unless the kind composes it (ADR-0066.R5);
- state: `state`, one of `open`, `resolved` or `canceled`; `resolved` and `canceled` are final;
- timing: `due_date`, a business date, and `priority` (`low`, `normal`, `high`, as for work items);
- origin: `origin_table` and `origin_id`, nullable for a case a person opens without one;
- outcome: `resolution` (a code), `resolved_at`, `cancel_reason`;
- bookkeeping: `version` and `recorded_at`.
Source: ADR-0066.R2

R86. The owner of a `work_case` is `owner_kind` (`user` or `role`), `owner_user_id`, or `owner_role` with its record-scope dimensions (`branch_id`, `warehouse_id`), stored and resolved exactly as for work items (R6, R10, R27 to R32). The `approval_stage` owner kind is not used.
Source: ADR-0066.R2

R87. The title of a `work_case` is `title_key` and `title_details`: the kind's i18n message filled with IDs, numbers and codes. It is never text copied from outside content, so the case row holds no untrusted field. `partner_id` is nullable and set only from a trusted source: the origin's deterministic match (ADR-0052.R15), or a person.
Source: ADR-0066.R2

R88. The database refuses deletes of `work_case` rows and refuses changes to identity, origin and final states. A unique partial index on (`company_id`, `kind`, `open_key`) where `state` is `open` allows one open case per origin and kind. `INV-790` checks that the origin of every case exists in the case's company.
Source: ADR-0066.R2

## Invariants

Statements are those of `invariants.csv`. `INV-790` to `INV-793` have their rows in chunk 2.

| Invariant | Name | Check point | Statement | Protects |
| --- | --- | --- | --- | --- |
| `INV-204` | `one_approval_item_per_pending_document` | day | Every document in `pending_approval` has exactly one open `approval_pending` work item. | R63, R66, R67 |
| `INV-205` | `no_agent_work_after_takeover` | day | No command of an agent run bound to a work item is audited after a person claimed that item. | R37, R47, R66 |

Reads: `INV-42` (`accepted_e_invoice_posted`, of `documents`) reads open work items through `ListWorkItem` by subject (R56).

## Settings

| Key | Value type | Scope | Core default | Bounds | Used by |
| --- | --- | --- | --- | --- | --- |
| `work.bulk_review_max_items` | integer | company | 50 | 1..500 (`lower_tighter`; leaf `work_queue_administration`) | R54, R55 |

`work_claim_minutes` (company setting, default 30; R44) is named by ADR-0042.R10 and has no row in `settings.csv`.

Reads: `auto_post.confirmation_cadence` (R64); `work_case.<kind>.mode` (chunk 2).

## Conflicts

CONFLICT ADR-0042.D0: the build order "with the first agent, before step 5" is replaced by ADR-0042.R20.N1 (the work queue is step 5, item 1, and the first agent follows it); R5 states it and R2, R3 keep the rest of the Decision text.
CONFLICT ADR-0042.R1.N1: the note governs the resolution values: a kind with a `resolution_command` has resolution `command`, and `bank_line_unmatched` is `system` without a resolution command; stated in R22 under ADR-0042.R1.N1.
CONFLICT ADR-0042.R3: the DDL of `work_item_note` stores `author_kind`, `author_id`, `body_text`, `is_untrusted` and `recorded_at` where the rule says author, text and `created_at`; R12 states the DDL columns and keeps the DDL's interim mark on the author columns.
CONFLICT ADR-0042.R5.N1: the calling module applies the fallback only for user-kind owners; a role-kind owner is stored symbolic and resolved at read time by ADR-0042.R2.N2; stated in R15 and R10.
CONFLICT ADR-0042.R7.N1: the kind rule `approver_role` is `approval_stage` (ADR-0055.R12) and the sales template is `role:sales_clerk` (ADR-0054.R11); ADR-0042.R7.N1 governs and R28, R31 state it.
CONFLICT ADR-0042.R7.N3: `subject_owner:<column>` and `subject_assignee:<column>` are kind rules and not part of the fallback, `document_owner` reads `created_by_user_id`, and "the `owner` role" of the fallback is `company_owner`; ADR-0042.R7.N3 governs, stated in R27, R28 and R30.
FALSE-POSITIVE ADR-0042.R7.N5: "no longer" describes a named owner who can no longer open the company, the trigger of the fallback to `company_owner`; the note adds the kind rule `named_by_raiser` and contradicts nothing.
CONFLICT ADR-0042.R8: escalation is after Phase 1 only for work items other than approvals; approval stages escalate in Phase 1 by ADR-0042.R8.N1 (ADR-0055.R13), stated in R34.
CONFLICT ADR-0042.R10: ownership is checked on the human only for a run a person starts; a run from a wake-up claims by its declared kind without that check, by ADR-0042.R10.N2, stated in R43.
CONFLICT ADR-0042.R17: the approval item is owned by its current approval stage and not the procedure's approver role, and delegation and escalation of approvals are in Phase 1 (ADR-0042.R17.N1, ADR-0055.R12; R63, R67); for `auto_post_unconfirmed`, ADR-0065.R7 governs as the later ADR (ADR-0043.R14.N5 and the catalog row of the kind say the same): one item per policy rule and confirmation window set by `auto_post.confirmation_cadence`, due at the window's end, where the rule says one item per rule and period, due at period end; R64 states the window.
CONFLICT ADR-0042.R18: the kind `inbound_message` is named `inbound_message_matched` by ADR-0042.R18.N1, and the rule's later paragraph adds `bank_line_unmatched`, so "unmatched bank lines come with DS-25" is not restated (R24, R25).
CONFLICT ADR-0042.R20: ADR-0042.R20.N1 keeps the runbook: the work queue is step 5, item 1, the first agent comes after it, and moving the work is no open question any more; stated in R5.
CONFLICT ADR-0066.D0: the Decision text names only `quote_request`, `customer_issue`, `supplier_invoice` and `customer_onboarding` as the kinds Phase 1 seeds; the later notes ADR-0066.R3.N1 and ADR-0066.R3.N2 add `nonconformance` and `production_disruption`, and R82 states them (their registrations are in chunk 2).

## Trace

| Source | Where |
| --- | --- |
| ADR-0008.R24 | ref: ADR-0008.R24 |
| ADR-0022.R2.N8 | ref: ADR-0022.R2.N8 |
| ADR-0031.R16 | R1 |
| ADR-0038.R14.N4 | ref: ADR-0038.R14.N4 |
| ADR-0040.R10 | ref: ADR-0040.R10 |
| ADR-0040.R11 | ref: ADR-0040.R11 |
| ADR-0040.R13.N2 | ref: ADR-0040.R13.N2 |
| ADR-0040.R15 | ref: ADR-0040.R15 |
| ADR-0040.R15.N1 | ref: ADR-0040.R15.N1 |
| ADR-0042.D0 | R2, R3 |
| ADR-0042.R1 | R21, R22, R23 |
| ADR-0042.R1.N1 | R21, R22, R60 |
| ADR-0042.R2 | R6, R7 |
| ADR-0042.R2.N1 | R6, R8 |
| ADR-0042.R2.N2 | R10 |
| ADR-0042.R2.N3 | R9 |
| ADR-0042.R3 | R11, R12 |
| ADR-0042.R4 | R13 |
| ADR-0042.R5 | R14, R15, R16, R17, R18 |
| ADR-0042.R5.N1 | R15 |
| ADR-0042.R5.N2 | R19 |
| ADR-0042.R6 | R20 |
| ADR-0042.R7 | R27, R28, R30 |
| ADR-0042.R7.N1 | R28, R31 |
| ADR-0042.R7.N2 | R28 |
| ADR-0042.R7.N3 | R27, R28, R29, R30 |
| ADR-0042.R7.N4 | R10 |
| ADR-0042.R7.N5 | R32, R33 |
| ADR-0042.R8 | R33, R34 |
| ADR-0042.R8.N1 | R33, R34 |
| ADR-0042.R9 | R35, R36, R37, R39 |
| ADR-0042.R9.N1 | R38 |
| ADR-0042.R10 | R40, R43, R44, R45 |
| ADR-0042.R10.N1 | R41 |
| ADR-0042.R10.N2 | R42, R43 |
| ADR-0042.R11 | R46, R47, R48, R49, R50, R51 |
| ADR-0042.R12 | R52 |
| ADR-0042.R12.N1 | R53, R54 |
| ADR-0042.R12.N2 | R55 |
| ADR-0042.R13 | R56 |
| ADR-0042.R14 | R57 |
| ADR-0042.R14.N1 | R58 |
| ADR-0042.R15 | R59 |
| ADR-0042.R16 | R60 |
| ADR-0042.R16.N1 | R60, R61 |
| ADR-0042.R17 | R62, R63, R64, R65, R66 |
| ADR-0042.R17.N1 | R63, R67 |
| ADR-0042.R18 | R24 |
| ADR-0042.R18.N1 | R24, R25 |
| ADR-0042.R18.N2 | R26 |
| ADR-0042.R19 | R4 |
| ADR-0042.R20 | R5 |
| ADR-0042.R20.N1 | R5 |
| ADR-0050.R15 | ref: ADR-0050.R15 |
| ADR-0050.R15.N2 | ref: ADR-0050.R15.N2 |
| ADR-0050.R18 | ref: ADR-0050.R18 |
| ADR-0050.R18.N1 | ref: ADR-0050.R18.N1 |
| ADR-0052.R15.N2 | ref: ADR-0052.R15.N2 |
| ADR-0055.R1 | ref: ADR-0055.R1 |
| ADR-0055.R12 | R67, R68, R69, R70, R71, R72 |
| ADR-0066.D0 | R80, R81, R82, R83 |
| ADR-0066.R1 | R84 |
| ADR-0066.R2 | R85, R86, R87, R88 |
