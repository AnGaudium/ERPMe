Module: work    Chunk: 2 of 2    Source ADRs: ADR-0066, ADR-0076
Build step(s): 5    Generated from index: 30d5706    Compiled by: Claude Fable 5.2, 2026-11-21

# Compiled spec: `work`, chunk 2

## Purpose

`work` owns the work queue, work cases and internal messaging, and sits in layer 2. This chunk states the work case kinds and their settings, the case links, commands, queries and safety limits (ADR-0066 from rule 3 on), and the messaging core: conversations, messages, mentions, notifications and notification e-mail (ADR-0076). The work item rules and the `work_case` table itself stand in chunk 1. Opening a case by a trigger or an automation rule, the system resolver and the case timeline belong to `automation` and `query` (ADR-0066.R6, ADR-0066.R7, ADR-0066.R15, ADR-0066.R17) and are cited, not restated.

## Entities and tables

DDL: `docs/design/DS-05-platform.sql` (`work_case_link`) and `docs/design/DS-63-messaging.sql` (the messaging tables).

| Table | Meaning | Key | Parent | Owner |
| --- | --- | --- | --- | --- |
| `work_case_link` | One link of a case to a target row; append-only (R207) | `id`; unique partial (`work_case_id`, `target_table`, `target_id`, `link_kind`) while `unlinked_at` is null | `work_case` | `work` |
| `conversation` | A channel, a direct conversation or a record thread (R231) | `id`; unique (`company_id`, `name`) for channels, (`company_id`, `subject_table`, `subject_id`) for record threads, (`company_id`, `direct_key`) for direct conversations | `company` | `work` |
| `conversation_member` | One user's membership; a member is a row with `left_at` null; for a record thread, a follower (R232, R235) | `id`; unique (`conversation_id`, `user_account_id`) | `conversation` | `work` |
| `message` | One post of a person (R238) | `id`; unique (`conversation_id`, `sequence`) | `conversation` | `work` |
| `message_mention` | One mentioned user of a message, with its `position` (R240) | `id`; unique (`message_id`, `position`) and (`message_id`, `user_account_id`) | `message` | `work` |
| `notification` | One inbox row per recipient (R241) | `id`; `ux_notification_recipient_message`, `ux_notification_recipient_work_item` | `company`; names `conversation`, `message`, `work_item`, `notification_email` | `work` |
| `notification_email` | One e-mail to one person, the intent of ADR-0013.R10 (R245) | `id` | `company` | `work` |
| `notification_preference` | A person's e-mail mode per notification kind; a missing row takes the kind's default (R244) | `id`; unique (`company_id`, `user_account_id`, `kind`) | `company` | `work` |

Rows in chunk 1, named by the rules of this chunk: `work_case`, `work_item`, `work_item_link`, `work_item_note`.

Reads: `user_account`, `company`, `document`, `partner`, `product`, `item`, `project`, `attachment_link`, `approval_stage_member`, `setting_value`, `purchase_request_line`, `purchase_order_line`; the catalogs `work-case-kinds.csv` (it also holds the kind `personal_data_breach` of module `audit`, which no unit of `work` states), `work-item-kinds.csv`, `settings.csv`, `authorization-areas.csv`.

## Commands and queries

Every command of this table has effect class `other`. The work case commands are not `human_only` and are on no agent tool list in Phase 1 (R213); the person-facing messaging commands are `human_only` (R249). "Not stated" means the sources fill no value for the cell.

| Name | Actor and authorization | Input | Effect | Events | Error codes |
| --- | --- | --- | --- | --- | --- |
| `CreateWorkCase` | `work_queue` at `edit` | kind; optional origin, owner, due date, `partner_id`, `work_item_ids` | opens a case, or returns the open case of the same `open_key` and attaches the items (R206) | `WorkCaseOpened` (none on the idempotent return) | `work_case_kind_not_enabled`, `work_case_origin_not_allowed` |
| `UpdateWorkCase` | `work_queue` at `edit` | due date, priority, `partner_id` from a trusted source | changes the case | not stated | `work_case_closed` |
| `LinkWorkCaseTarget` | `work_queue`; level not stated (no row for the verb `Link` in `authorization-verb-levels.csv`) | case, target, link kind | adds a `work_case_link` row (R207) | not stated | `work_case_closed` |
| `UnlinkWorkCaseTarget` | `work_queue`; level not stated (no row for the verb `Unlink`) | the link | sets `unlinked_at` once | not stated | `work_case_closed` |
| `ResolveWorkCase` | `work_queue`, verb `Resolve` at `edit`; a person for kinds with resolution `person`, `system` for kinds with resolution `system` | a resolution code | resolves the case (R213, R217) | not stated | `validation_failed`, `work_case_items_open`, `work_case_closed` |
| `AssignWorkCase` | `work_queue_administration` | the owner | changes the owner | not stated | `work_case_closed` |
| `CancelWorkCase` | `work_queue_administration` | a reason | cancels the case | not stated | `work_case_closed` |
| `ListWorkCase` (query) | `work_queue`, verb `List` at `read`; visibility of R216 | filters: kind, state, owner (me, my roles), partner, due, overdue | lists visible cases | none | not stated |
| `GetWorkCase` (query) | `work_queue`, verb `Get` at `read`; visibility of R216 | the case | the case with links, linked work items, downstream documents, pending commands and taint summary (R215) | none | not stated |
| `ListWorkCaseTimeline` (query) | `work_queue`, verb `List` at `read`; visibility of R216 | the case | the timeline of ADR-0066.R17 | none | not stated |
| `CreateConversation` | `messaging` at `edit`; `human_only` | kind; for `channel` `name`, optional `topic`, privacy; for `direct` the people | creates a channel, or creates or returns a direct conversation (R231, R233) | not stated | `channel_name_taken`, `validation_failed` |
| `UpdateConversation` | `messaging` at `edit`; a channel owner; `human_only` | name, topic, privacy | changes the channel | not stated | `channel_name_taken`, `conversation_closed` |
| `CloseConversation` | `messaging_administration` at `full`; `human_only` | the channel | makes the channel read-only | not stated | not stated |
| `CreateConversationMember` | `messaging` at `edit`; `human_only` | conversation, user | adds a channel member or a follower of a record thread (R231, R235) | not stated | `direct_conversation_fixed`, `validation_failed` |
| `UpdateConversationMember` | `messaging` at `edit`; `human_only` | `notify_level`, `last_read_sequence` | sets the caller's notify level and read marker | not stated | not stated |
| `EndConversationMember` | `messaging` at `edit`; `human_only` | the membership | ends a dated membership (leave or remove) | not stated | not stated |
| `CreateMessage` | `messaging` at `edit`; `human_only` | conversation, `body`, optional `parent_message_id`, up to 20 mentioned user IDs, attachments | stores the message with the next `sequence` (R238, R240) | `MessageCreated` | `mention_limit`, `mention_not_permitted`, `validation_failed`, `conversation_closed`, `conversation_subject_invalid`; `tool_not_allowed` and `human_only` (R249) |
| `UpdateMessage` | `messaging` at `edit`; the author; `human_only` | the message; an edited body or a withdrawal | edits or withdraws (R239) | not stated | `message_not_author` |
| `UpdateNotification` | `messaging` at `edit`; `human_only` | one notification, or all of the caller's | marks as read | not stated | not stated |
| `SetNotificationPreferences` | `messaging` at `edit`; `human_only` | the person's whole list of preferences | replaces the person's `notification_preference` rows | not stated | not stated |
| `CreateNotification` | internal-only; run by the consumer `messaging_fanout` | not stated | writes a `notification` row (R241) | `NotificationCreated` | not stated |
| `RunNotificationMail` | internal-only system job, every 5 minutes per company | the company | groups due notifications into `notification_email` rows (R245) | `NotificationEmailCreated`, `NotificationMailCompleted` | not stated |
| `RecordNotificationEmailOutcome` | internal-only; run by the consumer `messaging_mailer` | the e-mail, the outcome | records `sent`, `failed` or `unknown` (R246) | not stated | not stated |
| `RunMessageRetention` | internal-only; daily | not stated | clears old bodies and deletes old notifications and e-mail rows (R250) | not stated | not stated |
| `ListConversation` (query) | `messaging` at `read` | not stated | the reader's channels, direct conversations and followed threads with unread counts | none | not stated |
| `ListMessage` (query) | `messaging` at `read` | the conversation | pages one conversation by sequence | none | not stated |
| `ListNotification` (query) | `messaging`; level not stated | not stated | the caller's notifications and unread count, hiding what the reader can no longer read | none | not stated |
| `ListNotificationPreference` (query) | `messaging`; level not stated | not stated | the caller's preferences | none | not stated |

Events of R214 that the sources bind to no named command: `WorkCaseUpdated`, `WorkCaseAssigned`, `WorkCaseResolved`, `WorkCaseCanceled`.

Error code bound to no named command: `conversation_not_readable` (R254).

Contract function: `work.contract.raise_work_item` takes an optional `work_case_id` (R210). Consumers: `messaging_fanout` (transactional) and `messaging_mailer` (external) (R255). Registered functions wired by `app`: R255.

## Rules

### Case kinds and company settings

R201. Case kinds are registered by their owning module, like work item kinds (ADR-0042.R1). A registration holds:
- `code`, the owning module and the meaning;
- the allowed origin tables;
- `trigger_work_item_kind`, the work item kind whose raise opens a case in mode `auto` (ADR-0066.R6), or none;
- the owner rule and due rule (the kind rules of ADR-0042.R7 and ADR-0042.R8);
- `resolution`: `person` (by `ResolveWorkCase`) or `system` (ADR-0066.R15).
The catalog `work-case-kinds.csv` seeds the kinds of R202. Once `work` exists, the generator writes it from the registry.
Source: ADR-0066.R3

R202. The registered case kinds, each as owning module; trigger work item kind; origin tables; owner; due; resolution. An owner `role:<template>` names a role template (`sales_clerk`, `accountant`, `quality_inspector`, `shop_floor_lead`):
- `quote_request`: `sales`; `inbound_message_matched`; `interaction`; `role:sales_clerk`; `days:2`; `person`. It mirrors the quotation agent's trigger (ADR-0051.R14).
- `customer_issue`: `crm`; `complaint_open`; `complaint`, `interaction`; `role:sales_clerk`; `days:2`; `person`.
- `supplier_invoice`: `purchasing`; `supplier_invoice_received`; `e_invoice_record`, `document_extraction`, `interaction`; `role:accountant`; `days:2`; `system`.
- `customer_onboarding`: `crm`; `interaction_unmatched`; `interaction`; `role:sales_clerk`; `days:1`; `person`. It mirrors the onboarding agent's trigger (ADR-0051.R11).
- `nonconformance`: `quality`; `nonconformance_open`; `nonconformance`, `inspection_lot`; `role:quality_inspector`; `days:5`; `person`. Containment and corrective actions are `nonconformance_action` items in the case (ADR-0070.R16).
- `production_disruption`: `production`; `operation_blocked`; `production_order_operation`, `production_order`; `role:shop_floor_lead`; `days:1`; `person` (ADR-0071.R18).
Source: ADR-0066.R3, ADR-0066.R3.N1, ADR-0066.R3.N2

R203. `work_case.<kind>.mode` (company, enum, default `off`) is company configuration (ADR-0063.R1; `settings.csv`):
- `off`: the kind opens no case;
- `manual`: people open cases of the kind;
- `by_rule`: in addition, automation rules may open them (ADR-0066.R7);
- `auto`: in addition, the raise of the kind's trigger work item opens one (ADR-0066.R6).
A routine flow that the company handles without people, such as signed e-invoice XML posted through the auto-post gateway (ADR-0065), stays `off` or `by_rule`, with conditions on gate fields.
Source: ADR-0066.R4

R204. `work_case.<kind>.due_days` (company, integer, default `unset`, bounds 1 to 90): `unset` means the kind's registered due rule applies. `work.landing_page.<role_template>` (company, enum, default `work_queue`, bounds `work_queue|case_list`) is the home screen for users holding that role template: a user whose role assignments in force include a template mapped to `case_list` lands on the case list; everyone else lands on the work queue. Both surfaces stay reachable for everyone with the rights.
Source: ADR-0066.R4

R205. The settings `work_case.<kind>.mode`, `work_case.<kind>.due_days` and `work.landing_page.<role_template>` are neither tighter nor looser (direction `neutral`): a case grants no right and relaxes no check. A change is immediate and needs the leaf `work_queue_administration`.
Source: ADR-0066.R4

### Opening a case and its links

R206. `CreateWorkCase` takes the kind, an optional origin, an optional owner and due date (otherwise the kind's rules and `due_days`), an optional `partner_id`, and optional `work_item_ids` to attach.
- Idempotent by origin: when an open case of the kind exists for the same `open_key`, the command returns it and attaches the given items; no event is emitted.
- Checks: the company's mode for the kind is not `off` (`work_case_kind_not_enabled`); the origin's table is allowed for the kind (`work_case_origin_not_allowed`); the origin and the attached items are visible to the actor (ADR-0008.R5).
- Events: it emits `WorkCaseOpened`.
Source: ADR-0066.R5

R207. `work_case_link` holds the case's links.
- Columns: `work_case_id`, `target_table`, `target_id`, `link_kind`, `linked_by_kind`, `linked_by_id`, `unlinked_at`, `recorded_at`; the DDL adds `id` and `company_id`, holds `linked_by_kind` to `user` or `system`, and leaves `linked_by_id` null for `system`.
- Link kinds: `origin`, written by `CreateWorkCase`; `evidence`, an interaction, attachment, extraction or work item note; `artifact`, a document or change proposal; `related`, another case, partner or record.
- Append-only: `UnlinkWorkCaseTarget` sets `unlinked_at` once and changes nothing else; the database refuses deletes.
- Same company: a target is in the case's company and visible to the linking actor.
Source: ADR-0066.R8

R208. A case in a final state (`resolved` or `canceled`) refuses every change by command: link, unlink, update, assignment, resolution and cancel (`work_case_closed`, DS-04). Deleting a linked draft is allowed: in the same transaction the system ends the draft's live links by setting `unlinked_at` on them, as it cancels work items whose subject is deleted (ADR-0042.R12). This is a write by `system`, not an `UnlinkWorkCaseTarget` command, so it also works on a case in a final state, and the delete's audit record names it. The table needs no new column.
Source: ADR-0066.R8

R209. Downstream documents are not linked one by one. The case view follows the document flow from each linked document through its typed line references (ADR-0028.R1; ADR-0047.R2), so a goods receipt made from a linked order appears without a link.
Source: ADR-0066.R9

R210. `work_item.work_case_id` (nullable) is set once and never changed. A re-raise keeps it, like `origin_agent_run_id` (ADR-0042.R5). `work.contract.raise_work_item` takes an optional `work_case_id`. Without one, it sets the case itself when the item's subject is an `artifact` target of exactly one open case, or a `draft`-linked target of a work item of exactly one open case. Both lookups read only the tables of `work`. So the `approval_pending` item of a quotation drafted inside a `quote_request` case joins that case without any change to `documents`.
Source: ADR-0066.R10

R211. Agent drafts are reached through their work item: its `draft` links (ADR-0042.R3) and `document.origin_work_item_id` (ADR-0030.R11). No new write path is added for agents.
Source: ADR-0066.R11

R212. A person who creates a document from a case sends a command batch (ADR-0008.R20): `Create<Type>`, then `LinkWorkCaseTarget`, which refers to it by client `id`. The command envelope gains no field.
Source: ADR-0066.R12

### Case commands and queries

R213. The work case commands, all of effect class `other`, none `human_only`, none on an agent tool list in Phase 1:
- `CreateWorkCase`;
- `UpdateWorkCase`: due date, priority, and `partner_id` from a trusted source;
- `LinkWorkCaseTarget` and `UnlinkWorkCaseTarget`;
- `ResolveWorkCase`: a resolution code. It is an ordinary command with no internal flag: people run it for kinds with resolution `person`, and the `automation` resolver of ADR-0066.R15 runs the same command as `system` for kinds with resolution `system`. The command refuses a person on a `system` kind and `system` on a `person` kind with `validation_failed`;
- `AssignWorkCase`: the owner;
- `CancelWorkCase`: a reason.
`CreateWorkCase`, `UpdateWorkCase`, `LinkWorkCaseTarget`, `UnlinkWorkCaseTarget` and `ResolveWorkCase` are in authorization area `work_queue`; `AssignWorkCase` and `CancelWorkCase` are in `work_queue_administration` (ADR-0054.R7).
Source: ADR-0066.R13

R214. `CreateWorkCase` and `LinkWorkCaseTarget` count with work item raises under ADR-0013.R11: they change no document, master data, setting or right, so a consumer of a tainted event may run them. They are not `is_draft_only`, so no tainted agent run gains them. The work case events are `WorkCaseOpened`, `WorkCaseUpdated`, `WorkCaseAssigned`, `WorkCaseResolved` and `WorkCaseCanceled`.
Source: ADR-0066.R13

R215. The work case queries:
- `ListWorkCase`, filtered by kind, state, owner (me, my roles), partner, due and overdue;
- `GetWorkCase`, with links, linked work items, the downstream documents of R209, the pending commands of R217, and the taint summary of R218;
- `ListWorkCaseTimeline` (ADR-0066.R17).
Source: ADR-0066.R14

R216. A case is visible to a caller who holds `ListWorkCase` and who is its owner, holds its owner role in the case's scope, or holds `list_all_work_items`, as for work items (ADR-0042.R10). Inside a visible case, every link, item and timeline row is shown only when the caller may read its target under their own permissions, record scope, owner scope and field classes. Other rows are counted as hidden, never shown. A case therefore never reveals a record its reader could not open directly.
Source: ADR-0066.R14

R217. `GetWorkCase` lists the human commands the case's artifacts still wait for (`Submit`, `Approve`, `Post`, `Issue`, `Send`, `ClearTaint`), read from `ListAllowedCommand` for the caller (ADR-0040.R8). The case view simulates each and lists the plans. On one confirmation it executes each as its own command under the bulk-review conditions (ADR-0042.R12):
- each command has its own idempotency key, `expected_plan_hash`, `as_of_date`, audit record and approval record;
- there is no shared plan hash;
- segregation of duties, approval stages and policy are checked per command, as always.
The batch cap is `work.bulk_review_max_items`. A command that fails stays in the case for single review. `ResolveWorkCase` is refused while a linked work item is open or claimed (`work_case_items_open`).
Source: ADR-0066.R16

### Case safety limits

R218. Taint stays per version. `work_case` has no taint column. `GetWorkCase` computes a taint summary on read: the number of effectively tainted artifact versions (ADR-0029.R9) and their taint sources. Clearance is `ClearTaint` per version (ADR-0029.R8); no case-level clearance exists. The case view shows the tainted versions of a case together, each with its untrusted fields, and each is cleared by its own `ClearTaint` with its own reason and confirmation; no confirmation covers several versions. Revisit when measured cases hold a median of more than 5 tainted versions.
Source: ADR-0066.R18

R219. No wider reads for agents. An agent run starts only on a work item (ADR-0050.R15), and item 2 of ADR-0050.R27 stays "its work item, the item's evidence links and its notes", never the case. `GetWorkCase` and `ListWorkCaseTimeline` are on no agent tool list in Phase 1. A later ADR that wants agents to read cases must keep the tainted read scope.
Source: ADR-0066.R19

R220. Approvals stay per document. A case adds no approval object, stage or record. One approval never counts for more than one document version (ADR-0055.R7). A company may let a purchase order need no approval of its own when the policy input `is_within_approved_request` is true: every order line comes from an approved purchase request line of the same item, its quantity is within the request line's open quantity, and its unit price does not exceed the request line's estimated price by more than a tolerance setting (default 0). The core seeds no rule that uses the input, so the default stays approval per document as each company configures it. The estimated price needs a column added with the input at step 5, `purchase_request_line.estimated_unit_price` (in the request's currency); the open quantity of a request line is its `quantity` minus the quantity already ordered through `purchase_order_line.purchase_request_line_id`. No DDL changes now. The input and its tolerance setting are added to the catalogs with the purchase-order policy inputs at build step 5 (DS-22, DS-28); until then the interim holds (approval per document).
Source: ADR-0066.R20

R221. Work cases are bound by the invariants `INV-790`, `INV-791`, `INV-792` and `INV-793` and the edge cases `EC-240`, `EC-241`, `EC-242`, `EC-243`, `EC-244` and `EC-245`, first executable at step 5.
Source: ADR-0066.R22

### Messaging: conversations

R230. `work` owns a small messaging core, in Phase 1 from step 5: channels, direct conversations, record threads, mentions, one notification inbox and notification e-mail. Messages are plain text with one level of replies. Work items stay the place for work that must be done; a message or notification never replaces one (Principle 8).
Source: ADR-0076.D0

R231. `conversation` (owner `work`, company data) is one of the kinds `channel`, `direct` (R233) and `record` (R234), held by `ck_conversation_shape`. A `channel` is a named team space: `name`, a lower-case slug unique in the company (`channel_name_taken`), and an optional `topic`.
- A public channel is read by any user of the company who holds `messaging` at `read`, and joined and posted in at `edit`; a private channel (`is_private`) is read only by its current members, who add others.
- Whoever creates a channel is its owner (`is_owner`); owners add and remove members and change name, topic and privacy.
- `CloseConversation` (a holder of `messaging_administration`) makes it read-only (`conversation_closed`); channels are never deleted. A private channel whose last member leaves is closed.
Source: ADR-0076.R1

R232. A user takes part in a company's conversations only while holding an active role assignment there (ADR-0054). A member is a `conversation_member` row with `left_at` null, for every read path: messages, notifications, attachments, live updates.
Source: ADR-0076.R1

R233. Direct conversations have 2 to 8 members, fixed at creation: `direct_key` is their sorted IDs (`ck_conversation_direct_key`), unique in the company. `CreateConversation` of kind `direct` must include the actor among the people; with the same people it returns the existing conversation, and a member who had left rejoins only by doing so themselves, which clears `left_at` on the same row. Nobody adds a member (`direct_conversation_fixed`); a different set of people is a new conversation. A direct conversation is never closed.
Source: ADR-0076.R2

R234. A record thread carries the talk about one record and is created by its first message or follow (insert-on-conflict, then the row lock, so two first posts share one thread). `subject_table` is held to `document` (every document, through its `document` row), `partner`, `product`, `item` and `project`; a partner with the `employee` role, and anything else, is `conversation_subject_invalid`. At most one thread exists per record. The refusal of a partner with the `employee` role applies at thread creation only: a partner may gain the role after its thread exists; the role is allowed and the thread is kept, but its posting is closed with a stated reason.
Source: ADR-0076.R3, ADR-0076.R3.N1

R235. Readers and followers of a record thread:
- Readers: whoever may read the record now, through its leaf, record scope and owner scope together (ADR-0054.R15), may read and post in the thread; nobody else, whatever they followed. Permissions are checked on every read, so a person who loses the record loses the thread.
- Followers are the thread's members: the author of a message, every person mentioned in it, and whoever follows with `CreateConversationMember`, which needs read on the record and refuses a person who does not hold `messaging` at `edit` with `validation_failed`. Following is not access.
Source: ADR-0076.R3

R236. Deleting a draft document deletes its thread in the same transaction (its messages, mentions and notifications) and deletes its messages' attachment links, so no link names a deleted message (`INV-83`) and the orphan sweep releases the files (ADR-0038). A thread counts as a reference to a partner, product, item or project, so those are deactivated, never deleted, once they have one. No thread outlives its subject (`INV-880`).
Source: ADR-0076.R3

R237. A record thread is not a queue and not an audit trail. It holds people's talk only: no system messages, field changes or state history (those are the audit rows and versions, ADR-0038, ADR-0009). Work that must be done is a work item linked to the record.
Source: ADR-0076.R3

### Messaging: messages and mentions

R238. `message` holds one post: the author (`author_user_account_id`, a person), `body` (plain text up to 8,000 characters; links render, nothing else is formatted), an optional `parent_message_id` for a reply (one level; a reply to a reply is `validation_failed`), and attachments through `attachment_link` with target table `message`. `CreateMessage` locks the conversation row, adds one to `last_sequence` and stores it as the message's `sequence` (unique per conversation, gapless, `INV-881`). Order and unread use the sequence, never the ID, which carries no meaning (ADR-0006.R6). `UpdateConversationMember` sets the caller's `last_read_sequence`.
Source: ADR-0076.R4

R239. Only the author changes a message (`message_not_author`), with `UpdateMessage`.
- Editing sets `edited_at`; no earlier text is kept; the body keeps the same `<@n>` tokens, so an edit adds or removes no mention and notifies nobody.
- Withdrawing clears the body, sets `withdrawn_at` and ends the message's attachment links. The row stays as "withdrawn" so replies keep their parent.
- Attachments of a message are served only to those who may read its conversation now (ADR-0038.R14).
- A message is not a document: no state, approval, policy or posting. The command's response, its idempotency record and the event carry IDs only, never the body (ADR-0008.R16).
Source: ADR-0076.R4

R240. Mentions are picked in the composer: the command takes up to 20 user IDs (`mention_limit` beyond), stored in `message_mention` with their `position`; the body refers to the n-th one as `<@n>`, and the server rejects a body whose tokens and list differ (`validation_failed`). Names are rendered at read time from the users, only for users active in the company. Every mentioned person must be able to read the conversation and must hold `messaging` at `edit`, so a person holding it only at `read` cannot be mentioned (`mention_not_permitted`; the refusal tells the poster that much about the person's access, which is accepted). A mention in a record thread makes the person a follower. There is no mention of everyone: members choose `notify_level` `all` to hear every post.
Source: ADR-0076.R5

### Messaging: notifications

R241. `notification` is one inbox row per recipient, written only by the internal command `CreateNotification`, which the transactional consumer `messaging_fanout` runs (ADR-0013.R6, ADR-0013.R9; the "notifications" row of ADR-0027.R9). Posting stays one small transaction. From `MessageCreated` it writes one notification per recipient and message (`ux_notification_recipient_message`), of the strongest kind that applies:
- `mention`;
- `direct_message`: a member of the direct conversation with `notify_level` other than `none`;
- `reply`: the parent's author and earlier repliers in that thread;
- `followed`: a member of a channel or record thread with `notify_level` `all`.
The author, a member at `none` (which also suppresses mention notifications), and anyone who cannot read the conversation now or who does not hold `messaging` at `edit` get nothing: the fan-out skips them. Defaults of `notify_level`, set by the command: a direct member, a follower and a mentioned person start at `all`; a channel member at `mentions`.
Source: ADR-0076.R6

R242. From `WorkItemRaised` and `WorkItemAssigned` (ADR-0042.R14) the fan-out writes a `work_item` notification:
- to the item's owning user;
- for an item owned by an approval stage (ADR-0055.R12), to the stage's eligible members as the registered visibility function of ADR-0055 resolves them, at most 20: when there are more, the first 20 from the top of the stage's member list (`approval_stage_member.position`; a role member's holders by display name; a substitute right after the person it stands for), the others seeing the item in the queue;
- for an item owned by the role `company_owner`, the fallback when nobody can approve (ADR-0055.R13), to its holders, the first 20 by display name;
- an item owned by any other role notifies nobody.
Holders whom `RunApprovalEscalation` makes eligible later see the queue but get no notification. One unread notification exists per person and work item (`ux_notification_recipient_work_item`), so a re-raise or a reassignment does not duplicate it. Assigning a work case notifies through the case's work items; `WorkCaseAssigned` has no notification of its own.
Source: ADR-0076.R6

R243. Text, reading and e-mail limits of a notification:
- It stores IDs only (kind, actor, conversation, message, work item). Its line is rendered at read time from current names and document numbers, so erasure reaches it and no message text or partner name is stored.
- Opening the conversation or the work item marks its notifications read; `UpdateNotification` marks one or all of the caller's as read. `ListNotification` and its unread count hide what the reader can no longer read.
- A notification written from a delivery made by `ReplayEvents` (ADR-0013.R16), from an event older than 24 hours, or from a tainted event (ADR-0013.R11: a consumer on a tainted chain sends nothing out) is never e-mailed; it stays in the inbox.
Source: ADR-0076.R6

R244. E-mail is the only channel outside the screen. A notification is `email_pending` when the recipient has an address and its kind's mode is not `off`. The mode is the person's `notification_preference` (set as a whole list with `SetNotificationPreferences`), else the default:
- `mention`, `direct_message`, `work_item`: default `immediate`, sent in the first mail run 5 minutes after it was created, if still unread;
- `reply`, `followed`: default `digest`, sent in the first mail run at or after `messaging.digest_hour` in the recipient's time zone in which the person has no digest yet for that local date, if still unread; it gathers what was created before that hour, and later notifications wait for the next day's digest.
Source: ADR-0076.R7

R245. `RunNotificationMail`, an internal system job every 5 minutes per company, takes the pending notifications that are due and checks each again: the recipient's account is active and has an address, holds an active role assignment in the company, may still read the conversation or work item, its current preference is not `off`, and `messaging.email_notifications` is true. A notification that fails a check is dropped from e-mail; the rest are grouped into one `notification_email` per person and run (`immediate`, or the `digest`), which carries them, and each such row emits `NotificationEmailCreated`. So many quick messages give one e-mail.
Source: ADR-0076.R7

R246. Sending follows ADR-0013.R10: `RunNotificationMail` declares `NotificationEmailCreated` besides its own `NotificationMailCompleted` (ADR-0008.R1), and the external consumer `messaging_mailer` repeats the account, assignment and company-switch checks, records `failed` with reason `stale` for an e-mail more than 24 hours old, and otherwise sends through the installation's system mail transport and records the outcome with `RecordNotificationEmailOutcome`:
- `sent`;
- `failed`: a permanent refusal, or the third temporary one;
- `unknown`: no answer; it is never resent, because the inbox still holds every notification. SMTP has no status query, so this departs from the unknown-outcome rounds of ADR-0013.R10.
The transport is one SMTP submission account in the deployment configuration (DS-18), which carries every system e-mail: notifications, user invitations and credential resets (ADR-0054.R3, ADR-0054.R4). It is no crm mailbox, so `work` depends on no layer-4 module.
Source: ADR-0076.R7, ADR-0076.R7.N1

R247. A notification e-mail holds a subject naming the kind and the document number or channel, the rendered lines, and one link that opens the inbox after a normal sign-in; never message text, never partner names. It is not an approval link: approving stays on the web (spec 07). While `messaging.email_notifications` is false, every mail run drops the company's pending notifications, so turning it back on sends no backlog. Push (browser or app) is after Phase 1.
Source: ADR-0076.R7

### Messaging: reading, people only, retention

R248. Reading and live updates:
- `ListConversation` returns the reader's channels, direct conversations and followed threads with unread counts (by sequence); `ListMessage` pages one conversation by sequence; `ListNotification` and `ListNotificationPreference` complete the queries. There is no message search in Phase 1.
- `MessageCreated` has the message as its subject, so one failing fan-out holds only that message's delivery (ADR-0013.R7), and `NotificationCreated` the notification.
- The live updates of ADR-0040.R13 resolve a message to its conversation and forward the header only to sessions whose user may read the conversation now (the registered visibility function of messaging), and a `NotificationCreated` header only to its recipient's sessions; a tab may subscribe to a conversation it shows, never to the noun `message`. Headers carry IDs, never text.
Source: ADR-0076.R8

R249. The person-facing messaging commands are `human_only` (ADR-0008.R2) and on no agent tool list (ADR-0050.R30): an agent run is refused with `tool_not_allowed`, an integration client or a consumer on an agent chain with `human_only`. No agent run reads messages in Phase 1: `messaging` and `messaging_administration` are never in an agent run's permission intersection, and the query layer exposes no messaging view (ADR-0050). Bodies are labeled personal and untrusted (spec 17; ADR-0029.R10). `INV-883` checks the audit rows.
Source: ADR-0076.R9

R250. `messaging.message_retention_days` (default 0, keep forever): when set, `RunMessageRetention` (daily) clears the body of messages older than that (`body_removed_at`; the rows stay, so replies and sequences stand), ends their attachment links (`ended_at`, so the attachment's own retention applies, ADR-0038.R15), and deletes their mentions and notifications.
- Any change that shortens the period kept, including 0 to a number, takes effect 30 days after its `setting_value` row was recorded: the setting changes at once, and the job reads its history and applies the longer period until then. So no single change wipes the company's talk at once.
- The same job deletes read notifications 90 days after they were read, and `notification_email` rows 90 days after their outcome, first clearing `notification_email_id` on any notification that still names one.
Source: ADR-0076.R10

R251. Erasure, export and read markers:
- Erasing a user account (`user_account.erased_at`, DS-15) reaches every name, since names are rendered at read time. `EraseDataSubject` of a partner (ADR-0052.R25) also clears the bodies of that partner's record thread and ends their attachment links (ADR-0038.R15). Whether it reaches threads on the partner's documents, and whether an employee's own messages are erased, are open questions.
- The full company export (`ExportCompanyData`, ADR-0044.R17, in the owner template only) includes conversations and messages, as company records.
- Read markers (`UpdateConversationMember`, `UpdateNotification`) are commands and so leave audit rows (who marked a conversation read, when), kept as audit rows are.
Source: ADR-0076.R10

### Messaging: permissions, settings and wiring

R252. Leaf `messaging` (area `administration`, kind `function`, module `work`): `edit` runs the person-facing commands; `read` reads public channels and the threads of records one may read.
- Every command of the leaf, `UpdateNotification` and `SetNotificationPreferences` included, needs `edit` (ADR-0054.R8: every `Update` and `Set` command needs at least `edit`).
- Every role template holds `edit`, except the `auditor`, who holds `read`.
- Every command that makes a person a member (`CreateConversation` of kind `direct`, `CreateConversationMember` for a channel or a record thread, and a mention) refuses a person without `messaging` at `edit` (`validation_failed`; `mention_not_permitted` for a mention); a member whose level later drops to `read` keeps the row and gets no notifications.
- A person who holds `messaging` only at `read` reads the channels and record threads their rights allow, gets no notifications, cannot be mentioned and cannot be a conversation member, because they could not mark anything read.
Leaf `messaging_administration`: `full` closes channels and changes the company's messaging settings; held by the `owner` template and the IT administrator only.
Source: ADR-0076.R11

R253. Company settings (ADR-0063) under leaf `messaging_administration`: `messaging.email_notifications` (boolean, `true`), `messaging.digest_hour` (integer 0 to 23, 17) and `messaging.message_retention_days` (integer 0 to 3650, 0 = keep; a lowered value applies after 30 days). A person's own preferences, read markers and `notify_level` are theirs to set with `messaging` at `edit`.
Source: ADR-0076.R11

R254. Registered names of messaging:
- Person-facing commands (`human_only`, effect class `other`; the read checks in commands and queries are command-level tests when built): `CreateConversation`, `UpdateConversation`, `CloseConversation`, `CreateConversationMember`, `UpdateConversationMember`, `EndConversationMember`, `CreateMessage`, `UpdateMessage`, `UpdateNotification`, `SetNotificationPreferences`. `UpdateConversationMember` also moves the caller's read marker; `EndConversationMember` ends a dated membership (leave or remove).
- Internal-only commands (ADR-0008.R1): `CreateNotification`, `RunNotificationMail`, `RecordNotificationEmailOutcome`, `RunMessageRetention`.
- Queries: `ListConversation`, `ListMessage`, `ListNotification`, `ListNotificationPreference`.
- Events (IDs only): `MessageCreated`, `NotificationCreated`, `NotificationMailCompleted`, `NotificationEmailCreated`.
- Errors (DS-04): `mention_not_permitted`, `mention_limit`, `direct_conversation_fixed`, `conversation_closed`, `conversation_not_readable`, `conversation_subject_invalid`, `channel_name_taken`, `message_not_author`.
Source: ADR-0076.R12

R255. Wiring of messaging:
- The transactional consumer `messaging_fanout` subscribes to `MessageCreated`, `WorkItemRaised` and `WorkItemAssigned`.
- The external consumer `messaging_mailer` subscribes to `NotificationEmailCreated`.
- `work` sits in layer 2 and imports neither `permissions`, `registry`, `policy` nor the modules that own the subjects (ADR-0027.R1). As in ADR-0055.R1, those modules register functions that `app` wires: whether a user holds an active role assignment in a company and may read a record with record and owner scope (`permissions`, with each subject table's owner); the eligible members of an approval stage (`policy`, ADR-0055); the company's settings (`registry`).
Source: ADR-0076.R12

R256. Not in Phase 1: message search; push notifications and a mobile app; reactions, pins, polls, rich formatting; voice and video; bots and agent posts; agents that read or summarize conversations; bridges to Slack, Microsoft Teams or Zalo (spec 10 places Zalo OA in Phase 3); shared channels across companies; edit history; scheduled messages; rate limits beyond the mention cap and the e-mail grouping. Each needs its own decision.
Source: ADR-0076.R13

## Invariants

Statements are those of `invariants.csv`. Every row has first step 5; `INV-792`, `INV-793` and `INV-883` have area `safety`, the others `platform`. The rows of `INV-204` and `INV-205` are in chunk 1.

| Invariant | Name | Check point | Statement | Protects |
| --- | --- | --- | --- | --- |
| `INV-790` | `work_case_links_in_company` | day | Every `work_case_link` target with `unlinked_at` null, every work item whose `work_case_id` is set and the origin of every `work_case` exist in the case's company; an unlinked link may point at a deleted draft. | R207, R208, R210; ADR-0066.R2 |
| `INV-791` | `resolved_case_has_no_open_items` | day | No `work_case` in state `resolved` has a linked work item in state `open` or `claimed` whose `recorded_at` is not later than the case's `resolved_at`. | R217; ADR-0066.R15 |
| `INV-792` | `case_actions_are_separate_commands` | day | Every `approval` row and every `taint_clearance` row refers to exactly one document version, and no audit record of a work case command has effect class `posting`, `master_data_change` or `outbound_send`. | R217, R218, R220 |
| `INV-793` | `case_never_widens_agent_reads` | day | No audit record with actor kind `agent` names `GetWorkCase`, `ListWorkCase`, `ListWorkCaseTimeline` or a work case command. | R213, R219 |
| `INV-880` | `record_thread_subject_exists` | day | Every record thread names an existing row of an allowed subject table, of its company. | R234, R236 |
| `INV-881` | `message_sequence_gapless` | day | The messages of a conversation have the sequences 1 to its `last_sequence`, each once. | R238 |
| `INV-882` | `direct_members_fixed` | day | The member rows of a direct conversation are exactly the 2 to 8 users of its `direct_key`. | R233 |
| `INV-883` | `messaging_people_only` | day | No audit row of a person-facing messaging command carries an agent run, an integration client or an automation rule as actor or origin. | R249 |
| `INV-884` | `notification_email_consistent` | day | Every notification carried by an e-mail has the e-mail's recipient and company. | R245 |

Named by R236 and stated by its own module (catalog source ADR-0027.R2): `INV-83`.

## Edge cases

Descriptions are those of `edge-cases.csv` (`EC-242` reworded where the catalog text types a count of commands); every row is first executable at step 5.

| Edge case | Name | Case | Outcome | Protects |
| --- | --- | --- | --- | --- |
| `EC-240` | `quote_request_case_auto` | With `work_case.quote_request.mode` `auto`, a matched customer e-mail opens one case; the tainted quotation run's draft and the later `approval_pending` item join it; a second raise for the same message adds nothing. | `must_succeed` | R210; ADR-0066.R6 |
| `EC-241` | `quote_request_clean_note_path` | In the same case the salesperson's own note starts an untainted run that configures products; the case shows one tainted and one clean draft, and its taint summary counts one. | `must_succeed` | R218; ADR-0051.R14 |
| `EC-242` | `case_bulk_actions_separate` | From a case a person submits two drafts and approves a third in one confirmation; the commands run one by one, each with its own key and plan hash; the approval of a draft that person wrote is refused with `segregation_of_duties` and stays in the case. | `must_reject:segregation_of_duties` for that approval; `must_succeed` for the others | R217; ADR-0042.R12 |
| `EC-243` | `purchase_chain_sod_in_case` | In a case, the approver of a purchase order tries to post its goods receipt from the case view and is refused with `segregation_of_duties` (`purchase_order_vs_goods_receipt`). | `must_reject:segregation_of_duties` | R220; ADR-0054.R19 |
| `EC-244` | `case_hidden_rows` | A sales clerk opens a `supplier_invoice` case linked by an accountant; the invoice's cost fields and the purchase documents outside the clerk's scope are counted as hidden, never shown. | `must_succeed` | R216 |
| `EC-245` | `case_kind_off` | With `work_case.customer_issue.mode` `off`, `complaint_open` opens no case and `CreateWorkCase` for that kind is refused with `work_case_kind_not_enabled`. | `must_reject:work_case_kind_not_enabled` | R203, R206 |
| `EC-340` | `mention_in_record_thread` | A mention on a sales order's thread notifies the person; read within 5 minutes, no e-mail; unread, it goes out in the next mail run, together with the person's other due notifications. | `must_succeed` | R240, R241, R244, R245 |
| `EC-341` | `mention_without_access` | Mentioning a person who cannot read the purchase order is refused with `mention_not_permitted`; 21 mentions are refused with `mention_limit`. | `must_reject:mention_not_permitted`; `must_reject:mention_limit` | R240 |
| `EC-342` | `private_channel_hidden` | A non-member, and a member who left, see nothing of a private channel in `ListConversation`, `ListMessage` or its attachments. | `must_succeed` | R231, R232, R248 |
| `EC-343` | `direct_group_fixed` | Adding a fourth person to a direct conversation of three is refused with `direct_conversation_fixed`; creating one with the four opens a new conversation; a third party cannot open the pair's conversation. | `must_reject:direct_conversation_fixed` for the add; `must_succeed` for the new conversation | R233 |
| `EC-344` | `approval_notifies_stage` | A purchase order waiting at a stage with three eligible approvers notifies the three, each e-mailed after 5 minutes if unread; a stage of 25 notifies the first 20 from the top of its member list, and the other 5 see the item in the queue. | `must_succeed` | R242, R244 |
| `EC-345` | `agent_cannot_post` | An agent run's `CreateMessage` is refused with `tool_not_allowed`; an integration client's with `human_only`. | `must_reject:tool_not_allowed`; `must_reject:human_only` | R249 |
| `EC-346` | `record_access_revoked` | A person loses access to a customer's documents, or holds only own-document owner scope; the threads and notifications of the others' documents are hidden from their lists and unread counts. | `must_succeed` | R235, R243 |
| `EC-347` | `daily_digest_grouped` | Three followed-thread notifications unread at the digest hour arrive in one e-mail, with rendered lines and one link, no message text. | `must_succeed` | R244, R245, R247 |
| `EC-348` | `retention_clears_bodies` | With `messaging.message_retention_days` set from 0 to 365, after the 30-day grace the daily job clears older bodies, keeps a young reply and its cleared parent, ends their attachment links and deletes their notifications. | `must_succeed` | R250 |
| `EC-349` | `no_mail_after_departure` | A person whose role assignment ends at 16:00 gets no 17:00 digest; their pending notifications are dropped from e-mail. | `must_succeed` | R245 |

## Settings

Every key has storage `setting_value` and change effect `immediate`.

| Key | Value type | Scope | Core default | Bounds | Used by |
| --- | --- | --- | --- | --- | --- |
| `work_case.<kind>.mode` | enum | company | `off` | `off|manual|by_rule|auto` (`neutral`; leaf `work_queue_administration`) | R203, R205, R206 |
| `work_case.<kind>.due_days` | integer (business days from opening to the due date) | company | `unset` | 1..90 (`neutral`; leaf `work_queue_administration`) | R204, R205, R206 |
| `work.landing_page.<role_template>` | enum | company | `work_queue` | `work_queue|case_list` (`neutral`; leaf `work_queue_administration`) | R204, R205 |
| `messaging.email_notifications` | boolean | company | `true` | `true|false` (`neutral`; leaf `messaging_administration`) | R245, R247, R253 |
| `messaging.digest_hour` | integer | company | 17 | 0..23 (`neutral`; leaf `messaging_administration`) | R244, R253 |
| `messaging.message_retention_days` | integer | company | 0 | 0..3650 (`neutral`; leaf `messaging_administration`) | R250, R253 |

The row of `work.bulk_review_max_items` (used by R217) stands in chunk 1. The tolerance setting of R220 has no key in the sources and no row in `settings.csv`; it is added with the policy input at build step 5.

## UI annotations

None: the sources hold no ADR-0077 annotation for the units of this chunk; `work` registers no work item kind of its own in `work-item-kinds.csv`, and the case kinds are registrations of other modules (R202).

## Conflicts

CONFLICT ADR-0076.R3: the rule calls a partner that gains the `employee` role after its thread exists an open question; ADR-0076.R3.N1 decides it (role allowed, thread kept, posting closed), and R234 states that result.
CONFLICT ADR-0066.R18: the formerly deferred question of a case-level taint clearance is decided inside the rule text by the chief architect (review note of 2026-11-21): no clearance covers several versions; R218 states the decision without the deferral.
CONFLICT ADR-0066.R20: the formerly deferred purchase-chain approval question is decided inside the rule text (review notes of 2026-11-21): the policy input `is_within_approved_request` comes at build step 5 and approval per document holds as interim; R220 keeps the interim mark.

## Proposed (not law)

None

## Trace

| Source | Where |
| --- | --- |
| ADR-0066.R3 | R201, R202 |
| ADR-0066.R3.N1 | R202 |
| ADR-0066.R3.N2 | R202 |
| ADR-0066.R4 | R203, R204, R205 |
| ADR-0066.R5 | R206 |
| ADR-0066.R8 | R207, R208 |
| ADR-0066.R9 | R209 |
| ADR-0066.R10 | R210 |
| ADR-0066.R11 | R211 |
| ADR-0066.R12 | R212 |
| ADR-0066.R13 | R213, R214 |
| ADR-0066.R14 | R215, R216 |
| ADR-0066.R16 | R217 |
| ADR-0066.R18 | R218 |
| ADR-0066.R19 | R219 |
| ADR-0066.R20 | R220 |
| ADR-0066.R22 | R221 |
| ADR-0066.K.N1 | not applicable: consequence text and revisit conditions; the separability of CRM is law of ADR-0052.R1 and no rule of work cases changes |
| ADR-0071.R18 | ref: ADR-0071.R18 |
| ADR-0076.D0 | R230 |
| ADR-0076.R1 | R231, R232 |
| ADR-0076.R2 | R233 |
| ADR-0076.R3 | R234, R235, R236, R237 |
| ADR-0076.R3.N1 | R234 |
| ADR-0076.R4 | R238, R239 |
| ADR-0076.R5 | R240 |
| ADR-0076.R6 | R241, R242, R243 |
| ADR-0076.R7 | R244, R245, R246, R247 |
| ADR-0076.R7.N1 | R246 |
| ADR-0076.R8 | R248 |
| ADR-0076.R9 | R249 |
| ADR-0076.R10 | R250, R251 |
| ADR-0076.R11 | R252, R253 |
| ADR-0076.R12 | R254, R255 |
| ADR-0076.R13 | R256 |
| ADR-0078.R11 | ref: ADR-0078.R11 |
| ADR-0079.R9 | ref: ADR-0079.R9 |
| ADR-0079.R9.N1 | ref: ADR-0079.R9.N1 |
| ADR-0079.R9.N2 | ref: ADR-0079.R9.N2 |
