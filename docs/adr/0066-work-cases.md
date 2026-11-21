# ADR-0066: Work cases

Status: accepted (2026-11-21) under ADR-0005, reviewed by Claude Fable 5.2 (builder Claude Opus 5.5; proposed 2026-11-16) after three review rounds, the fixes verified by Claude Opus 5.5.
Design items: DS-29 (work queue), DS-30 (UI), DS-28 (settings), DS-04 (errors). Related decisions: D2. Principles 3, 8. ADR-0005, ADR-0008, ADR-0009, ADR-0013, ADR-0022, ADR-0028, ADR-0029, ADR-0040, ADR-0042, ADR-0047, ADR-0050, ADR-0051, ADR-0052, ADR-0054, ADR-0055, ADR-0057, ADR-0058, ADR-0063, ADR-0065.

## Decision

The author's concept of 2026-11-16, the "Task-Artifact Architecture" or "dual-membrane model", asks for a task-centric operational shell above the document-centric core. The chief architect's assessment (lab note `holistic/task_artifact_assessment.md`) found the parts already designed but nothing that ties them together across one business intent. The author approved a narrow, hybrid form on 2026-11-16. This ADR records it.

**One core, one work queue, two surfaces.** A **work case** groups everything about one business intent: the origin that started it, the work items raised along the way, the agent runs on them, the drafts and change proposals they made, and the documents that resulted.
- A case only links. Documents stay the single source of truth, and the case's timeline is composed by query, never copied.
- A case changes no core rule: no lifecycle, approval, segregation of duties, taint, simulation, lock order or posting rule.
- Every human action taken from a case is its own command through the same dispatcher.

**Hybrid by kind of work.** Cases serve unstructured and exception work. Routine structured work keeps the list, form and keyboard grid screens of ADR-0040 and the six hand-built screens. The axis is "unstructured or exception" against "routine structured", not external against internal:
- **Unstructured or exception work, mostly external**, uses cases: quote requests, customer issues, supplier invoices arriving by mailbox, new-customer onboarding.
- **Routine structured work, mostly internal**, keeps the traditional screens: journal entries, stock movements, production orders, period close.
- **Internal exceptions** may use cases later without re-architecture: a shortage, a count difference, a cost-variance investigation, a close issue, an engineering change.
- **Routine external flows** need none: bank statements, signed e-invoice XML, EDI.

**Generic from day one, configured per company.** `work_case` is generic. Case kinds are a registered catalog, and each company decides through settings (ADR-0063) which kinds it uses and whether they open by themselves, by an automation rule, or only by a person. Phase 1 seeds four external kinds: `quote_request`, `customer_issue`, `supplier_invoice` and `customer_onboarding`. Every kind is `off` until the company turns it on, so the defaults reproduce today's behavior.

**What stays rejected.** The parts of the original pitch that would cut through hard rules stay out, and the section "Options considered" states why:
- one approval across a purchase request, purchase order and goods receipt;
- clearing taint for a whole task;
- one simulation for a set of documents whose later steps depend on earlier postings;
- replacing lists and grids with an issue tracker.

A case never widens an agent's read scope.

### Rules

**Scope**

1. A work case is optional context. No command requires a case, no handler reads one, and no document, posting or approval depends on one. Removing every case leaves the books, stock and approvals unchanged. A case kind exists for unstructured or exception work; routine structured flows get no kind.

**Table**

2. `work_case` lives in module `work` (layer 2) and is a company table under row-level security (ADR-0017 rule 19). It holds:
   - **Identity:** `id`, `company_id`, `kind`, and `open_key`, the origin's ID unless the kind composes it (rule 5).
   - **State:** `state`, one of `open`, `resolved` or `canceled`. `resolved` and `canceled` are final.
   - **Owner:** `owner_kind` (`user` or `role`), `owner_user_id`, or `owner_role` with its record-scope dimensions (`branch_id`, `warehouse_id`), stored and resolved exactly as for work items (ADR-0042 rules 2, 7 and their notes). The `approval_stage` owner kind is not used.
   - **Timing:** `due_date`, a business date, and `priority`.
   - **Title:** `title_key` and `title_details`. The title is the kind's i18n message filled with IDs, numbers and codes. It is never text copied from outside content, so the case row holds no untrusted field.
   - **Partner:** `partner_id`, nullable, set only from a trusted source: the origin's deterministic match (ADR-0052 rule 15), or a person.
   - **Origin:** `origin_table` and `origin_id`, nullable for a case a person opens without one.
   - **Outcome:** `resolution` (a code), `resolved_at`, `cancel_reason`.
   - **Bookkeeping:** `version` and `recorded_at`.

   The database refuses deletes and refuses changes to identity, origin and final states. A unique partial index on (`company_id`, `kind`, `open_key`) where `state` is `open` allows one open case per origin and kind.

**Case kinds**

3. Case kinds are registered by their owning module, like work item kinds (ADR-0042 rule 1). A registration holds:
   - `code`, the owning module and the meaning;
   - the allowed origin tables;
   - `trigger_work_item_kind`, the work item kind whose raise opens a case in mode `auto` (rule 6), or none;
   - the owner rule and due rule (the kind rules of ADR-0042 rules 7 and 8);
   - `resolution`: `person` (by `ResolveWorkCase`) or `system` (rule 15).

   The catalog [work-case-kinds.csv](../catalogs/work-case-kinds.csv) seeds the four Phase 1 kinds. Once `work` exists, the generator writes it from the registry.

   | Kind | Owning module | Trigger work item kind | Origin tables | Owner | Due | Resolution |
   | --- | --- | --- | --- | --- | --- | --- |
   | `quote_request` | `sales` | `inbound_message_matched` | `interaction` | `role:sales_clerk` | `days:2` | `person` |
   | `customer_issue` | `crm` | `complaint_open` | `complaint`, `interaction` | `role:sales_clerk` | `days:2` | `person` |
   | `supplier_invoice` | `purchasing` | `supplier_invoice_received` | `e_invoice_record`, `document_extraction`, `interaction` | `role:accountant` | `days:2` | `system` |
   | `customer_onboarding` | `crm` | `interaction_unmatched` | `interaction` | `role:sales_clerk` | `days:1` | `person` |

   The kind `quote_request` mirrors the quotation agent's trigger (ADR-0051 rule 14). The kind `customer_onboarding` mirrors the onboarding agent's trigger (ADR-0051 rule 11).

   Note ([ADR-0070](0070-quality-management-core.md), 2026-11-21): a fifth kind, `nonconformance` (`quality`, trigger `nonconformance_open`, origins `nonconformance` and `inspection_lot`, `role:quality_inspector`, `days:5`, `person`). Containment and corrective actions are `nonconformance_action` items in the case (ADR-0070 rule 16).

   Note ([ADR-0071](0071-work-orders-and-shop-floor-execution.md), 2026-11-21): a sixth kind, `production_disruption` (`production`, trigger `operation_blocked`, origins `production_order_operation` and `production_order`, `role:shop_floor_lead`, `days:1`, `person`) (ADR-0071 rule 18).
4. Company configuration (ADR-0063 rule 1; [settings.csv](../catalogs/settings.csv)):
   - **`work_case.<kind>.mode`** (company, enum, default `off`):
     - `off`: the kind opens no case;
     - `manual`: people open cases of the kind;
     - `by_rule`: in addition, automation rules may open them (rule 7);
     - `auto`: in addition, the raise of the kind's trigger work item opens one (rule 6).

     A routine flow that the company handles without people, such as signed e-invoice XML posted through the auto-post gateway (ADR-0065), stays `off` or `by_rule`, with conditions on gate fields.
   - **`work_case.<kind>.due_days`** (company, integer, default `unset`, bounds 1 to 90): `unset` means the kind's registered due rule applies.
   - **`work.landing_page.<role_template>`** (company, enum, default `work_queue`, bounds `work_queue|case_list`): the home screen for users holding that role template. A user whose role assignments in force include a template mapped to `case_list` lands on the case list; everyone else lands on the work queue, which is today's behavior. Both surfaces stay reachable for everyone with the rights.

   The three settings are neither tighter nor looser (direction `neutral`): a case grants no right and relaxes no check. A change is immediate and needs the leaf `work_queue_administration`.

**Opening a case**

5. `CreateWorkCase` takes the kind, an optional origin, an optional owner and due date (otherwise the kind's rules and `due_days`), an optional `partner_id`, and optional `work_item_ids` to attach.
   - **Idempotent by origin.** When an open case of the kind exists for the same `open_key`, the command returns it and attaches the given items; no event is emitted.
   - **Checks.** The company's mode for the kind is not `off` (`work_case_kind_not_enabled`). The origin's table is allowed for the kind (`work_case_origin_not_allowed`). The origin and the attached items are visible to the actor (ADR-0008 rule 5).
   - **Events.** It emits `WorkCaseOpened`.
6. **Mode `auto`.** The transactional consumer `work_case_opener` of module `automation` (layer 5, queue `events`) reacts to `WorkItemRaised` for kinds that a case kind names as its trigger.
   - **When.** Only where the company's mode for that case kind is `auto`.
   - **What it runs.** `CreateWorkCase` as `system` on behalf of the event's human (ADR-0013 rule 9), with key `work_case_opener:<event id>:1`. The origin is the item's subject when its table is allowed, the item is attached, and the partner is copied only from the subject's matched `partner_id`.
   - **Skips.** It skips events that carry an origin agent run, so nothing in an agent's chain opens a case.
   - **Taint.** On a tainted event it may still run, because opening a case drafts, posts and sends nothing (the note on ADR-0013 rule 11).
7. **Mode `by_rule`.** ADR-0058 gains the action `open_work_case`: kind, origin from the triggering subject, and owner by `named_by_raiser`. It runs `CreateWorkCase` as `system` on behalf of the rule's owner, who needs `CreateWorkCase` and read rights on the subject (ADR-0058 rule 9). A rule may open only a kind whose mode is `by_rule` or `auto`.

**Links and work items**

8. `work_case_link` holds the case's links.
   - **Columns:** `work_case_id`, `target_table`, `target_id`, `link_kind`, `linked_by_kind`, `linked_by_id`, `unlinked_at`, `recorded_at`.
   - **Link kinds:**
     - `origin`, written by `CreateWorkCase`;
     - `evidence`: an interaction, attachment, extraction or work item note;
     - `artifact`: a document or change proposal;
     - `related`: another case, partner or record.
   - **Append-only.** `UnlinkWorkCaseTarget` sets `unlinked_at` once and changes nothing else; the database refuses deletes.
   - **Same company.** A target is in the case's company and visible to the linking actor.
   - **Open cases only.** A case in a final state (`resolved` or `canceled`) refuses every change by command: link, unlink, update, assignment, resolution and cancel (`work_case_closed`, DS-04) (review note, 2026-11-21).
   - **Deleting a linked draft** is allowed. In the same transaction the system ends the draft's live links by setting `unlinked_at` on them, as it cancels work items whose subject is deleted (ADR-0042 rule 12); this is a write by `system`, not an `UnlinkWorkCaseTarget` command, so it also works on a case in a final state, and the delete's audit record names it. The table needs no new column (review note, 2026-11-21).
9. **Downstream documents** are not linked one by one. The case view follows the document flow from each linked document through its typed line references (ADR-0028 rule 1; ADR-0047 rule 2), so a goods receipt made from a linked order appears without a link.
10. `work_item.work_case_id` (nullable) is set once and never changed. A re-raise keeps it, like `origin_agent_run_id` (ADR-0042 rule 5). `work.contract.raise_work_item` takes an optional `work_case_id`. Without one, it sets the case itself when the item's subject is:
    - an `artifact` target of exactly one open case; or
    - a `draft`-linked target of a work item of exactly one open case.

    Both lookups read only `work`'s own tables. So the `approval_pending` item of a quotation drafted inside a `quote_request` case joins that case without any change to `documents`.
11. **Agent drafts** are reached through their work item: its `draft` links (ADR-0042 rule 3) and `document.origin_work_item_id` (ADR-0030 rule 11). No new write path is added for agents.
12. **People who create from a case.** A person who creates a document from a case sends a command batch (ADR-0008 rule 20): `Create<Type>`, then `LinkWorkCaseTarget`, which refers to it by client `id`. The command envelope gains no field.

**Commands, queries and visibility**

13. Commands, all of effect class `other`, none `human_only`, none on an agent tool list in Phase 1:
    - `CreateWorkCase`;
    - `UpdateWorkCase`: due date, priority, and `partner_id` from a trusted source;
    - `LinkWorkCaseTarget` and `UnlinkWorkCaseTarget`;
    - `ResolveWorkCase`: a resolution code, for kinds with resolution `person`. It is an ordinary command with no internal flag: people run it for those kinds, and the `automation` resolver of rule 15 runs the same command as `system` for kinds with resolution `system`. The command refuses a person on a `system` kind and `system` on a `person` kind with `validation_failed` (review note, 2026-11-21);
    - `AssignWorkCase`: the owner;
    - `CancelWorkCase`: a reason.

    The first five are in authorization area `work_queue`, and `AssignWorkCase` and `CancelWorkCase` are in `work_queue_administration` (ADR-0054 rule 7).

    `CreateWorkCase` and `LinkWorkCaseTarget` count with work item raises under ADR-0013 rule 11 (see its note): they change no document, master data, setting or right, so a consumer of a tainted event may run them. They are not `is_draft_only`, so no tainted agent run gains them.

    Events: `WorkCaseOpened`, `WorkCaseUpdated`, `WorkCaseAssigned`, `WorkCaseResolved`, `WorkCaseCanceled`.
14. Queries:
    - **`ListWorkCase`**, filtered by kind, state, owner (me, my roles), partner, due and overdue.
    - **`GetWorkCase`**, with links, linked work items, the downstream documents of rule 9, the pending commands of rule 16, and the taint summary of rule 18.
    - **`ListWorkCaseTimeline`** (rule 17).

    **Visibility.** A case is visible to a caller who holds `ListWorkCase` and who is its owner, holds its owner role in the case's scope, or holds `list_all_work_items`, as for work items (ADR-0042 rule 10). Inside a visible case, every link, item and timeline row is shown only when the caller may read its target under their own permissions, record scope, owner scope and field classes. Other rows are counted as hidden, never shown. A case therefore never reveals a record its reader could not open directly.

**Resolving**

15. **Resolution `system`.** The case resolves, with resolution `completed`, when:
    - every `artifact` target that is not unlinked is in a final state (`posted`, `reversed`, `canceled` or `closed`, ADR-0009 rule 14), or, for a change proposal (rule 8), in `closed` or `canceled` (ADR-0029 rule 3) (review note, 2026-11-21); and
    - no linked work item is `open` or `claimed`.

    The resolver is a system job of module `automation` (layer 5), beside `work_case_opener`. It runs when a linked item is resolved or canceled and when a linked document reaches a final state. It reads the linked targets' states through their modules' contracts and resolves the case with the ordinary command `ResolveWorkCase`, run as `system` for kinds with resolution `system` (rule 13: no internal flag, so people keep running it for kinds with resolution `person`) (review note, 2026-11-21). `work` itself reads no document state (review note, 2026-11-21).
16. **Pending commands.** `GetWorkCase` lists the human commands the case's artifacts still wait for (`Submit`, `Approve`, `Post`, `Issue`, `Send`, `ClearTaint`), read from `ListAllowedCommand` for the caller (ADR-0040 rule 8). The case view simulates each and lists the plans. On one confirmation it executes each as its own command under the bulk-review conditions (ADR-0042 rule 12 note):
    - each command has its own idempotency key, `expected_plan_hash`, `as_of_date`, audit record and approval record;
    - there is no shared plan hash;
    - segregation of duties, approval stages and policy are checked per command, as always.

    The batch cap is `work.bulk_review_max_items`. A command that fails stays in the case for single review. `ResolveWorkCase` is refused while a linked work item is open or claimed (`work_case_items_open`).

**Timeline**

17. `ListWorkCaseTimeline` is a query of module `query` (layer 5) over views in schema `query`. It composes, ordered by the source rows' `recorded_at` and ID, with nothing copied:
    - the origin (interaction or extraction) and the case's links;
    - linked work items with their notes, claims and resolutions;
    - agent run summaries (agent type, mode, outcome, taint, step count);
    - document and change-proposal versions with actor kind, agent run, taint and clearance;
    - approvals and policy decisions;
    - audit records the caller may read (ADR-0038 rule 7).

    Untrusted fields are returned only with `include_untrusted`. Returning one to an agent run taints it (ADR-0029 rule 10), but the timeline is on no agent tool list in Phase 1.

**Safety**

18. **Taint stays per version.** `work_case` has no taint column. `GetWorkCase` computes a taint summary on read: the number of effectively tainted artifact versions (ADR-0029 rule 9) and their taint sources. Clearance is `ClearTaint` per version (ADR-0029 rule 8). No case-level clearance exists. The case view shows the tainted versions of a case together, each with its untrusted fields, and each is cleared by its own `ClearTaint` with its own reason and confirmation; no confirmation covers several versions. The per-version act is the control (spec 03 rule 1), and ADR-0067 rule 17 already forbids batch clearance in the small-company mode. Decided by the chief architect under the author's delegation of 2026-11-19; revisit when measured cases hold a median of more than 5 tainted versions (review note, 2026-11-21).
19. **No wider reads for agents.** An agent run starts only on a work item (ADR-0050 rule 15), and item 2 of ADR-0050 rule 27 stays "its work item, the item's evidence links and its notes", never the case. `GetWorkCase` and `ListWorkCaseTimeline` are on no agent tool list in Phase 1. A later ADR that wants agents to read cases must keep the tainted read scope.
20. **Approvals stay per document.** A case adds no approval object, stage or record. One approval never counts for more than one document version (ADR-0055 rule 7 note). A company may let a purchase order need no approval of its own when the policy input `is_within_approved_request` is true: every order line comes from an approved purchase request line of the same item, its quantity is within the request line's open quantity, and its unit price does not exceed the request line's estimated price by more than a tolerance setting (default 0). The core seeds no rule that uses the input, so the default stays approval per document as each company configures it. The estimated price needs a column added with the input at step 5, `purchase_request_line.estimated_unit_price` (in the request's currency); the open quantity of a request line is its `quantity` minus the quantity already ordered through `purchase_order_line.purchase_request_line_id`. No DDL changes now (review note, 2026-11-21). The input and its tolerance setting are added to the catalogs with the purchase-order policy inputs at build step 5 (DS-22, DS-28); until then the interim holds (approval per document). Decided by the chief architect under the author's delegation of 2026-11-19 (review note, 2026-11-21).

**UI**

21. ADR-0040 rule 6 gains two generated screen kinds:
    - **The case view.** The left pane holds the timeline of rule 17, with untrusted text in the "external content" style (ADR-0040 rule 17). The right pane holds the selected artifact's record view, or its command form with the plan panel. Editing a draft there is an ordinary update command: Review simulates, and the client computes nothing (ADR-0040 rule 2). The pending commands of rule 16 sit above the panes.
    - **The case list.** A list over `ListWorkCase`, beside the work queue list.

    `work.landing_page.<role_template>` chooses a role's home (rule 4). Lists, record views, command forms, the keyboard model and the six hand-built screens are unchanged.

    Note ([ADR-0077](0077-ui-floorplans-annotations-and-embedded-agent.md), 2026-11-21): the case view is the worklist floorplan with its right pane showing an object page, edit form or approval view; the Centers ADR builds on the worklist and overview floorplans (ADR-0077 rules 1–3).

**Checks**

22. Invariants and edge cases are listed in the section "Edge cases and invariants" below.

## Context

- **Already designed.** Most of the concept exists under other names:
  - work items with claims, evidence and draft links (ADR-0042);
  - agent wake-ups on `WorkItemRaised` (ADR-0050 rules 15–16);
  - taint inherited from items to runs to versions (ADR-0029 rules 8–10);
  - the partner timeline (ADR-0052 rule 18);
  - extractions with evidence (ADR-0057);
  - command batches (ADR-0008 rule 20);
  - bulk review (ADR-0042 rule 12 note);
  - the auto-post gateway (ADR-0065, accepted 2026-11-21).
- **The gap.** A work item is one exception, and it closes when the exception ends. A customer e-mail that becomes a quotation passes through `inbound_message_matched`, an agent run, a draft, possibly `approval_pending`, and `follow_up_due`, and no record says these belong together. People handling exception work need one place per intent.
- **Practice** confirms the narrow form:
  - SAP S/4HANA Situation Handling keeps a situation with an anchor object, related objects and actions above the business documents, and opening a related app leaves the situation unchanged.
  - SAP Fiori My Inbox allows mass approval only within one task type, enabled per scenario and capped.
  - Service platforms (ServiceNow, Salesforce) are case-centric because service is their product; their postings live elsewhere.
  - Odoo's chatter is per record, which ADR-0042 already rejected as a queue.
- **The author's decisions (2026-11-16):** the narrow form, the hybrid direction, a generic table, configurable kinds, external kinds first, and the landing page per role. The approval question for the purchase request to order chain and the taint-clearing question were deferred; both were decided on 2026-11-21 under the author's delegation of 2026-11-19 (rules 18, 20) (review note, 2026-11-21).

## Options considered

| Option | For | Against |
| --- | --- | --- |
| `work_case` container in layer 2 that only links (chosen) | One place per intent; no core rule changes; small | One more noun |
| Stretch `work_item` into the case | No new table | Breaks one open item per exception and the 30-minute agent lease (ADR-0042 rules 4, 9) |
| Name it `task` or `case` | The author's word; the common word | "Task" already names warehouse, close, follow-up, agent and automation tasks, and "case" names golden-case labels (ADR-0059); a word takes one meaning (ADR-0004 rule 20) |
| One approval across purchase request, purchase order and goods receipt (rejected) | Fewer clicks | An approval binds to a version its approver saw, and the order does not exist when the request is approved (ADR-0009); a goods receipt records a physical arrival and is not an approval object; `purchase_order_vs_goods_receipt` (ADR-0054 rule 19) and condition 5 of ADR-0055 rule 7 refuse it; requests and orders sit in different pools on purpose (ADR-0055 rule 1) |
| Taint held and cleared per task (rejected) | One click | It would clear versions nobody opened, and versions added after the clearance; it would taint the clean path of a person's own note (ADR-0051 rule 14 note); taint is data lineage per version (ADR-0029 rules 8–9; INV-84, INV-88) |
| One simulation for the whole artifact set at resolve (rejected) | One review | A plan hash belongs to a command and its actor, not to a draft; the set spans several people and days, and SoD forbids one actor submitting, approving and posting; one stale value voids the whole set; simulation takes no locks and is not the bottleneck; agents need the checks at draft time (ADR-0008 rules 9–13; ADR-0051) |
| Issue tracker replacing lists and grids (rejected) | One surface | Routine entry is measured against MISA on six keyboard-first screens (ADR-0003 R9); lists are how accountants audit; the generated renderer is the coding plan's backbone (ADR-0040) |
| Timeline copied into a case table by events | Fast reads | Two copies that drift (ADR-0019 rule 13) |
| Group work items in the UI only, no table | No schema | No origin, owner or state across items |
| Kinds hard-wired on | Simpler | The company decides which processes open cases (the author, 2026-11-16) |

## Consequences

- **For companies:** nothing changes until a kind is turned on. A company that turns on `quote_request` in mode `auto` gets one case per matched customer e-mail, with the agent's draft, the approval item and the follow-up joined to it.
- **For agents:** nothing changes. They start on work items, read the same scope, and only draft.
- **For auditors:** every action in a case is an ordinary audited command. The case adds no record that a posting depends on.
- **For the build:** the tables, commands and queries land with the step-5 work-queue screens, after the `work` core is built with the first agent (ADR-0042 rule 20). The case view and case list are generated screens. Nothing in steps 0 to 4 depends on this ADR. The work is small-model friendly: CRUD with links, one consumer and SQL views.
- **CRM-only deployments (a consequence, not a rule):** a deployment that runs only `crm` and master data would use the case list and case view as its main surface, since its work is mostly external exceptions. This ADR adds nothing that stands in the way. The separability question itself, including the ledger account references on partner profiles, stays open for the author (architecture overview B17).

  Note (S2 closure, 2026-11-21): the separability question was decided on 2026-11-17: CRM runs on its own as a deployment profile of the one product ([ADR-0052](0052-minimal-crm.md) rule 1 note).
- **Revisit when:**
  - a company asks for internal case kinds (shortage, count difference, variance, close issue, engineering change);
  - an agent needs to read a whole case, which would widen ADR-0050 rule 27 and needs the author;
  - a case kind needs service-level timers or escalation beyond its work items.

## Documents updated

- **ADRs** (notes tagged "ADR-0066, 2026-11-21"):
  - [ADR-0013](0013-outbox-and-events.md) rule 11;
  - [ADR-0022](0022-repository-and-engineering-conventions.md) rule 2;
  - [ADR-0029](0029-proposals-and-agent-safety.md) rule 8;
  - [ADR-0040](0040-ui-architecture.md) rule 6;
  - [ADR-0042](0042-work-queue.md) rules 2, 5 and 12;
  - [ADR-0050](0050-agent-runtime-and-query-layer.md) rule 27;
  - [ADR-0052](0052-minimal-crm.md) rule 15;
  - [ADR-0055](0055-approval-pools-and-stages.md) rule 7;
  - [ADR-0058](0058-configurable-workflows.md) rule 8;
  - [ADR-0063](0063-configurable-policy-settings.md) rule 29.
- **Catalogs:** [work-case-kinds.csv](../catalogs/work-case-kinds.csv) (new), [settings.csv](../catalogs/settings.csv) (3 definitions), [invariants.csv](../catalogs/invariants.csv), [edge-cases.csv](../catalogs/edge-cases.csv), [authorization-areas.csv](../catalogs/authorization-areas.csv) (meanings of `work_queue` and `work_queue_administration`), the [catalogs README](../catalogs/README.md).
- **Design files:**
  - [DS-05-platform.sql](../design/DS-05-platform.sql): `work_case`, `work_case_link`, `work_item.work_case_id`, triggers and row-level security;
  - [DS-04-command-envelope.md](../design/DS-04-command-envelope.md): errors and the registry vocabulary;
  - [DS-16-invariants-and-harness.md](../design/DS-16-invariants-and-harness.md) and [DS-17-synthetic-dataset.md](../design/DS-17-synthetic-dataset.md): code blocks;
  - [architecture-overview.md](../design/architecture-overview.md) and the generated appendices.
- **Open questions:** [docs/open-questions.md](../open-questions.md), section "Work cases": the two formerly deferred questions, now answered (rules 18, 20).
- **Index and log:** [docs/adr/README.md](README.md); [docs/runbook/step-log.md](../runbook/step-log.md).
- **Not changed:** `docs/spec/`, including the glossary. The glossary rows for work case, case kind, case view and case list come with acceptance.
- **Catalog rows:**
  - **Errors** (DS-04): `work_case_kind_not_enabled` and `work_case_items_open` (precondition), `work_case_origin_not_allowed` (validation), `work_case_closed` (precondition).
  - **Settings:** `work_case.<kind>.mode`, `work_case.<kind>.due_days` and `work.landing_page.<role_template>`.
  - **Invariants** INV-790 to INV-793 of the block INV-790 to INV-799, and **edge cases** EC-240 to EC-245 of the block EC-240 to EC-249.

## Edge cases and invariants

**Invariants** (DS-16; block INV-790 to INV-799, INV-790 to INV-793 taken; first step 5):

- **INV-790** `work_case_links_in_company` (area `platform`): every `work_case_link` target with `unlinked_at` null, every linked work item and the origin of every `work_case` exist in the case's company; an unlinked link may point at a deleted draft (rule 8) (review note, 2026-11-21).
- **INV-791** `resolved_case_has_no_open_items` (area `platform`): no `work_case` in state `resolved` has a linked work item in state `open` or `claimed` whose `recorded_at` is not later than the case's `resolved_at`.
- **INV-792** `case_actions_are_separate_commands` (area `safety`): every `approval` row and every `taint_clearance` row refers to exactly one document version, and no audit record of a work case command has effect class `posting`, `master_data_change` or `outbound_send`.
- **INV-793** `case_never_widens_agent_reads` (area `safety`): no audit record of a query or command with actor kind `agent` names `GetWorkCase`, `ListWorkCase` or `ListWorkCaseTimeline`, and no work case command has actor kind `agent`.

**Edge cases** (DS-17; block EC-240 to EC-249, EC-240 to EC-245 taken; first step 5):

- **EC-240** `quote_request_case_auto`: with `work_case.quote_request.mode` `auto`, a matched customer e-mail opens one case. The tainted quotation run's draft and the later `approval_pending` item join it. A second raise for the same message adds nothing.
- **EC-241** `quote_request_clean_note_path`: in the same case, the salesperson's own note starts an untainted run that configures products. The case shows one tainted and one clean draft, and its taint summary counts one.
- **EC-242** `case_bulk_actions_separate`: from a case, a person submits two drafts and approves a third in one confirmation. Three commands run with three keys and plan hashes; the approval of a draft the person wrote is refused with `segregation_of_duties` and stays in the case.
- **EC-243** `purchase_chain_sod_in_case`: in a case, the approver of a purchase order tries to post its goods receipt from the case view and is refused with `segregation_of_duties` (`purchase_order_vs_goods_receipt`).
- **EC-244** `case_hidden_rows`: a sales clerk opens a `supplier_invoice` case linked by an accountant; the invoice's cost fields and the purchase documents outside the clerk's scope are counted as hidden, never shown.
- **EC-245** `case_kind_off`: with `work_case.customer_issue.mode` `off`, `complaint_open` opens no case and `CreateWorkCase` for that kind is refused with `work_case_kind_not_enabled`.
