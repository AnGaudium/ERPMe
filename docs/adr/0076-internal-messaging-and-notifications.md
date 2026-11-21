# ADR-0076: Internal messaging and notifications

Status: accepted (2026-11-21) under ADR-0005, reviewed by Claude Fable 5.2 (builder Claude Opus 5.5; proposed 2026-11-19) after three review rounds, the fixes verified by Claude Opus 5.5.
Design item: DS-63 (new). Related decisions: none new. Principles 3, 8, 12. ADR-0004, ADR-0006, ADR-0008, ADR-0013, ADR-0027, ADR-0029, ADR-0038, ADR-0040, ADR-0042, ADR-0044, ADR-0050, ADR-0052, ADR-0054, ADR-0055, ADR-0063, ADR-0066, ADR-0074; spec 07, spec 17.

## Decision

The author's request of 2026-11-19: internal notifications and conversations "like Slack, but simple and light". Today a person sees a pending approval or an exception only by opening the work queue (ADR-0042); people cannot talk about a document inside the system; and e-mail and push notifications are after Phase 1 (ADR-0040 rule 14; spec 07). This ADR proposes a small messaging core owned by `work`, in Phase 1 from step 5 (the author's decision of 2026-11-19).

| Need | Today | Decision |
| --- | --- | --- |
| Team talk | Outside the system | Channels, public or private (rule 1) |
| One-to-one or small-group talk | Outside the system | Direct conversations of 2 to 8 people, membership fixed (rule 2) |
| Talk about one document or record | None; header notes only (ADR-0074 rule 16) | One record thread per record, readable by whoever may read the record (rule 3) |
| Calling someone in | None | Up to 20 mentions per message, picked in the composer (rule 5) |
| Knowing that something needs you | The work queue, only when opened | One notification inbox: mentions, direct messages, replies, followed conversations, work items for you, approvals waiting for you (rule 6) |
| Being told when away | After Phase 1 | One e-mail per person per 5 minutes, or a daily digest, by preference, never with message text; push stays after Phase 1 (rule 7) |

It is deliberately small: seven tables, plain text, one level of replies, no search, reactions, calls, bots or integrations. Work items stay the place for work that must be done; a message or notification never replaces one (Principle 8).

### Rules

**Conversations**

1. `conversation` (owner `work`, company data) is one of three kinds, held by `ck_conversation_shape`:
   - **`channel`**: a named team space (`name`, a lower-case slug unique in the company, `channel_name_taken`; optional `topic`). A public channel is read by any user of the company who holds `messaging` at `read`, and joined and posted in at `edit`; a private channel (`is_private`) is read only by its current members, who add others. Whoever creates a channel is its owner (`is_owner`); owners add and remove members and change name, topic and privacy. `CloseConversation` (a holder of `messaging_administration`) makes it read-only (`conversation_closed`); channels are never deleted. A private channel whose last member leaves is closed.
   - **`direct`**: rule 2. **`record`**: rule 3.
   - **Who takes part.** A user takes part in a company's conversations only while holding an active role assignment there (ADR-0054). A **member** is a `conversation_member` row with `left_at` null, for every read path: messages, notifications, attachments, live updates.
2. **Direct conversations** have 2 to 8 members, fixed at creation: `direct_key` is their sorted IDs (`ck_conversation_direct_key`), unique in the company. `CreateConversation` of kind `direct` must include the actor among the people; with the same people it returns the existing conversation, and a member who had left rejoins only by doing so themselves, which clears `left_at` on the same row. (review note, 2026-11-21) Nobody adds a member (`direct_conversation_fixed`); a different set of people is a new conversation. A direct conversation is never closed.
3. **Record threads** carry the talk about one record, created by its first message or follow (insert-on-conflict, then the row lock, so two first posts share one thread). `subject_table` is held to `document` (every document, through its `document` row), `partner`, `product`, `item` and `project`; a partner with the `employee` role, and anything else, is `conversation_subject_invalid`. At most one thread per record.
   - **Readers.** Whoever may read the record now, through its leaf, record scope and owner scope together (ADR-0054 rule 15), may read and post in the thread; nobody else, whatever they followed. Permissions are checked on every read, so a person who loses the record loses the thread.
   - **Followers** are the thread's members: the author of a message, every person mentioned in it, and whoever follows with `CreateConversationMember` (which needs read on the record; it refuses a person who does not hold `messaging` at `edit` with `validation_failed`) (review note, 2026-11-21). Following is not access.
   - **Subjects that go.** Deleting a draft document deletes its thread in the same transaction (its messages, mentions and notifications) and deletes its messages' attachment links, so no link names a deleted message (INV-83) and the orphan sweep releases the files (ADR-0038). A thread counts as a reference to a partner, product, item or project, so those are deactivated, never deleted, once they have one. No thread outlives its subject (INV-880). A partner that gains the `employee` role after its thread exists is an open question.
   - **Not a queue and not an audit trail.** A thread holds people's talk only: no system messages, field changes or state history (those are the audit rows and versions, ADR-0038, ADR-0009). Work that must be done is a work item linked to the record. ADR-0066 notes that a per-record chatter is no queue; this thread is not one.

**Messages**

4. `message` holds one post: the author (`author_user_account_id`, a person), `body` (plain text up to 8,000 characters; links render, nothing else is formatted), an optional `parent_message_id` for a reply (one level; a reply to a reply is `validation_failed`), and attachments through `attachment_link` with target table `message`.
   - **Order.** `CreateMessage` locks the conversation row, adds one to `last_sequence` and stores it as the message's `sequence` (unique per conversation, gapless, INV-881). Order and unread use the sequence, never the ID, which carries no meaning (ADR-0006 rule 6). `UpdateConversationMember` sets the caller's `last_read_sequence`.
   - **Edit and withdraw.** Only the author changes a message (`message_not_author`), with `UpdateMessage`: editing sets `edited_at` (no earlier text is kept; the body keeps the same `<@n>` tokens, so an edit adds or removes no mention and notifies nobody); withdrawing clears the body, sets `withdrawn_at` and ends the message's attachment links. The row stays as "withdrawn" so replies keep their parent.
   - **Attachments** of a message are served only to those who may read its conversation now (a note on ADR-0038 rule 14).
   - **No business effect.** A message is not a document: no state, approval, policy or posting. The command's response, its idempotency record and the event carry IDs only, never the body (ADR-0008 rule 16).
5. **Mentions** are picked in the composer: the command takes up to 20 user IDs (`mention_limit` beyond), stored in `message_mention` with their `position`; the body refers to the n-th one as `<@n>`, and the server rejects a body whose tokens and list differ (`validation_failed`). Names are rendered at read time from the users, only for users active in the company. Every mentioned person must be able to read the conversation and must hold `messaging` at `edit`, so a person holding it only at `read` cannot be mentioned (`mention_not_permitted`; the refusal tells the poster that much about the person's access, which is accepted) (review note, 2026-11-21). A mention in a record thread makes the person a follower. There is no mention of everyone: members choose `notify_level` `all` to hear every post.

**Notifications**

6. `notification` is one inbox row per recipient, written only by the internal command `CreateNotification`, which the transactional consumer `messaging_fanout` runs (ADR-0013 rules 6, 9; the "notifications" row of ADR-0027 rule 9). Posting stays one small transaction.
   - **From messages** (`MessageCreated`): one notification per recipient and message (`ux_notification_recipient_message`), of the strongest kind that applies: `mention`; `direct_message` (a member of the direct conversation with `notify_level` other than `none`); `reply` (the parent's author and earlier repliers in that thread); `followed` (a member of a channel or record thread with `notify_level` `all`). The author, a member at `none` (notify level `none` also suppresses mention notifications), and anyone who cannot read the conversation now, or who does not hold `messaging` at `edit`, get nothing: the fan-out skips them (review note, 2026-11-21). (review note, 2026-11-21) Defaults: a direct member, a follower and a mentioned person start at `all`; a channel member at `mentions` (set by the command).
   - **From work items** (`WorkItemRaised`, `WorkItemAssigned`, ADR-0042 rule 14): a `work_item` notification to the item's owning user; for an item owned by an approval stage (ADR-0055 rule 12), to the stage's eligible members as ADR-0055's registered visibility function resolves them, at most 20: when there are more, the first 20 from the top of the stage's member list (`approval_stage_member.position`; a role member's holders by display name; a substitute right after the person it stands for), the others seeing the item in the queue (the author's decision of 2026-11-19); an item owned by the role `company_owner`, the fallback when nobody can approve (ADR-0055 rule 13), notifies its holders, the first 20 by display name; an item owned by any other role notifies nobody. Holders whom `RunApprovalEscalation` makes eligible later see the queue but get no notification. One unread notification per person and work item (`ux_notification_recipient_work_item`), so a re-raise or a reassignment does not duplicate it. Assigning a work case notifies through the case's work items; `WorkCaseAssigned` has no notification of its own. (review note, 2026-11-21)
   - **Text.** A notification stores IDs only (kind, actor, conversation, message, work item). Its line ("Lan mentioned you in SO-2026-0042", "Approval waiting: PO-2026-0107") is rendered at read time from current names and document numbers, so erasure reaches it and no message text or partner name is stored.
   - **Reading.** Opening the conversation or the work item marks its notifications read; `UpdateNotification` marks one or all of the caller's as read. `ListNotification` and its unread count hide what the reader can no longer read.
   - **No e-mail from replays or tainted events.** A notification written from a delivery made by `ReplayEvents` (ADR-0013 rule 16), from an event older than 24 hours, or from a tainted event (ADR-0013 rule 11: a consumer on a tainted chain sends nothing out) is never e-mailed; it stays in the inbox.
7. **E-mail** is the only channel outside the screen. A notification is `email_pending` when the recipient has an address and its kind's mode is not `off`: the person's `notification_preference` (set as a whole list with `SetNotificationPreferences`), else the default:

   | Kind | Default | Sent |
   | --- | --- | --- |
   | `mention`, `direct_message`, `work_item` | `immediate` | in the first mail run 5 minutes after it was created, if still unread |
   | `reply`, `followed` | `digest` | in the first mail run at or after `messaging.digest_hour` in the recipient's time zone in which the person has no digest yet for that local date, if still unread; it gathers what was created before that hour, and later notifications wait for the next day's digest |

   - **The mail run.** `RunNotificationMail`, an internal system job every 5 minutes per company, takes the pending notifications that are due and checks each again: the recipient's account is active and has an address, holds an active role assignment in the company, may still read the conversation or work item, its current preference is not `off`, and `messaging.email_notifications` is true. A notification that fails a check is dropped from e-mail; the rest are grouped into one `notification_email` per person and run (immediate, or the digest), which carries them, and each such row emits `NotificationEmailCreated`. So 50 quick messages give one e-mail.
   - **Sending** follows ADR-0013 rule 10: `RunNotificationMail` declares `NotificationEmailCreated` besides its own `NotificationMailCompleted` (ADR-0008 rule 1 note), and the external consumer `messaging_mailer` repeats the account, assignment and company-switch checks, records `failed` with reason `stale` for an e-mail more than 24 hours old, and otherwise sends through the installation's system mail transport (an SMTP submission account in deployment configuration; no crm mailbox, so `work` depends on no layer-4 module) and records the outcome with `RecordNotificationEmailOutcome`: `sent`; `failed` (a permanent refusal, or the third temporary one); `unknown` (no answer), which is never resent, because the inbox still holds every notification. SMTP has no status query, so this departs from the unknown-outcome rounds of ADR-0013 rule 10's note (a note there).
   - **Content.** A subject naming the kind and the document number or channel, the rendered lines, and one link that opens the inbox after a normal sign-in. Never message text, never partner names. It is not an approval link: approving stays on the web (spec 07).
   - **Off switch.** While `messaging.email_notifications` is false, every mail run drops the company's pending notifications, so turning it back on sends no backlog.
   - **Push** (browser or app) is after Phase 1.
8. **Reading and live updates.**
   - `ListConversation` returns the reader's channels, direct conversations and followed threads with unread counts (by sequence); `ListMessage` pages one conversation by sequence; `ListNotification` and `ListNotificationPreference` complete the queries. There is no message search in Phase 1.
   - **Live.** `MessageCreated` has the message as its subject, so one failing fan-out holds only that message's delivery (ADR-0013 rule 7), and `NotificationCreated` the notification. The live updates of ADR-0040 rule 13 resolve a message to its conversation and forward the header only to sessions whose user may read the conversation now (messaging's registered visibility function), and a `NotificationCreated` header only to its recipient's sessions; a tab may subscribe to a conversation it shows, never to the noun `message`. Headers carry IDs, never text.

**Safety, retention and permissions**

9. **People only.** The person-facing commands are `human_only` (ADR-0008 rule 2) and on no agent tool list (ADR-0050 rule 30): an agent run is refused with `tool_not_allowed`, an integration client or a consumer on an agent chain with `human_only`. No agent run reads messages in Phase 1: `messaging` and `messaging_administration` are never in an agent run's permission intersection, and the query layer exposes no messaging view (ADR-0050). Bodies are labeled personal and untrusted (spec 17; ADR-0029 rule 10). INV-883 checks the audit rows.
10. **Retention, erasure and export.**
    - `messaging.message_retention_days` (default 0, keep forever): when set, `RunMessageRetention` (daily) clears the body of messages older than that (`body_removed_at`; the rows stay, so replies and sequences stand), ends their attachment links (`ended_at`, so the attachment's own retention applies, ADR-0038 rule 15), and deletes their mentions and notifications. Any change that shortens the period kept, including 0 to a number, takes effect 30 days after its `setting_value` row was recorded: the setting changes at once, and the job reads its history and applies the longer period until then. So no single change wipes the company's talk at once.
    - The same job deletes read notifications 90 days after they were read, and `notification_email` rows 90 days after their outcome, first clearing `notification_email_id` on any notification that still names one.
    - **Erasure.** Erasing a user account (`user_account.erased_at`, DS-15) reaches every name, since names are rendered at read time. `EraseDataSubject` of a partner (ADR-0052 rule 25) also clears the bodies of that partner's record thread and ends their attachment links (ADR-0038 rule 15). Whether it reaches threads on the partner's documents, and whether an employee's own messages are erased, are open questions.
    - **Export.** The full company export (`ExportCompanyData`, ADR-0044 rule 17, in the owner template only) includes conversations and messages, as company records.
    - Read markers (`UpdateConversationMember`, `UpdateNotification`) are commands and so leave audit rows (who marked a conversation read, when), kept as audit rows are; accepted as the cost of using the command model.
11. **Permissions and settings.**
    - Leaf `messaging` (area `administration`, kind `function`, module `work`): `edit` runs the person-facing commands; `read` reads public channels and the threads of records one may read. Every command of the leaf, `UpdateNotification` and `SetNotificationPreferences` included, needs `edit` (ADR-0054 rule 8: every `Update` and `Set` command needs at least `edit`). Every role template holds `edit`, except the auditor, who holds `read`. Every command that makes a person a member (`CreateConversation` of kind `direct`, `CreateConversationMember` for a channel or a record thread, and a mention) refuses a person without `messaging` at `edit` (`validation_failed`; `mention_not_permitted` for a mention); a member whose level later drops to `read` keeps the row and gets no notifications. (review note, 2026-11-21) A person who holds `messaging` only at `read` (the `auditor` template) reads the channels and record threads their rights allow, and gets no notifications, cannot be mentioned and cannot be a conversation member, because they could not mark anything read (review note, 2026-11-21).
    - Leaf `messaging_administration`: `full` closes channels and changes the company's messaging settings; held by the owner and the IT administrator only.
    - Company settings (ADR-0063), leaf `messaging_administration`: `messaging.email_notifications` (boolean, true), `messaging.digest_hour` (integer 0 to 23, 17) and `messaging.message_retention_days` (integer 0 to 3650, 0 = keep; a lowered value applies after 30 days).
    - A person's own preferences, read markers and `notify_level` are theirs to set with `messaging` at `edit`.
12. **Commands, queries, events and the wiring.**
    - Person-facing commands (`human_only`, effect class `other`; the read checks in commands and queries are command-level tests when built): `CreateConversation`, `UpdateConversation`, `CloseConversation`, `CreateConversationMember`, `UpdateConversationMember`, `EndConversationMember`, `CreateMessage`, `UpdateMessage`, `UpdateNotification`, `SetNotificationPreferences`. `UpdateConversationMember` also moves the caller's read marker; `EndConversationMember` ends a dated membership (leave or remove).
    - Internal-only commands (ADR-0008 rule 1 note): `CreateNotification`, `RunNotificationMail`, `RecordNotificationEmailOutcome`, `RunMessageRetention`.
    - Queries: `ListConversation`, `ListMessage`, `ListNotification`, `ListNotificationPreference`.
    - Events (IDs only): `MessageCreated`, `NotificationCreated`, `NotificationMailCompleted`, `NotificationEmailCreated`.
    - The transactional consumer `messaging_fanout` subscribes to `MessageCreated`, `WorkItemRaised` and `WorkItemAssigned`.
    - The external consumer `messaging_mailer` subscribes to `NotificationEmailCreated`.
    - **Registered functions.** `work` sits in layer 2 and imports neither `permissions`, `registry`, `policy` nor the modules that own the subjects (ADR-0027 rule 1). As in ADR-0055 rule 1, those modules register functions that `app` wires: whether a user holds an active role assignment in a company and may read a record with record and owner scope (`permissions`, with each subject table's owner); the eligible members of an approval stage (`policy`, ADR-0055); the company's settings (`registry`).
    - Errors (DS-04): `mention_not_permitted`, `mention_limit`, `direct_conversation_fixed`, `conversation_closed`, `conversation_not_readable`, `conversation_subject_invalid`, `channel_name_taken`, `message_not_author`.
13. **Not in Phase 1:** message search; push notifications and a mobile app; reactions, pins, polls, rich formatting; voice and video; bots and agent posts; agents that read or summarize conversations; bridges to Slack, Microsoft Teams or Zalo (spec 10 places Zalo OA in Phase 3); shared channels across companies; edit history; scheduled messages; rate limits beyond the mention cap and the e-mail grouping. Each needs its own decision.

## Context

**Survey of the reference systems** (what each offers for internal talk and notices, as far as it bears on a lean core):

| System | Internal talk | Record discussion | Notices | What we take |
| --- | --- | --- | --- | --- |
| Slack | Public and private channels, DMs and group DMs, threads, mentions, reactions, huddles, apps and bots | Through links and apps | Per-channel levels (all, mentions, nothing), e-mail when away, mobile push, digests | Channels, group DMs with fixed members, one-level threads, mention-only levels, e-mail only when still unread, grouped |
| Odoo Discuss | Channels and direct chat | Chatter on every record: messages, log notes, followers, activities | Inbox; e-mail per follower | Record threads with followers; no system log in the thread and no activities (the work queue does that) |
| SAP S/4HANA (Fiori) | None in the core (collaboration tools sit outside) | Notes on some objects | Notification center fed by workflow and business events | The inbox fed by business events: work items and approvals for you |
| Dynamics 365 / Business Central | Through Microsoft Teams | Notes and links on records, Teams cards | Notifications on the role center and by e-mail for approvals and events | E-mail for approvals; no dependency on an outside chat product |

The lesson: an ERP's own chat should cover talk about its records and tell people what needs them; general chat products do the rest better. So: three conversation kinds, one inbox, e-mail as the only outside channel, and no integrations.

**What it builds on.** The work queue stays the place for work (ADR-0042; Principle 8). Live updates already push headers to screens (ADR-0040 rule 13). Outbox consumers own asynchronous notifications (ADR-0027 rule 9) and external calls (ADR-0013 rule 10). Outbound messages to partners stay in `crm` with their consent and content checks (ADR-0052 rules 27, 28); internal talk never leaves the system.

## Options considered

| Option | For | Against |
| --- | --- | --- |
| No messaging; integrate Slack or Teams | No build | A paid outside product, data outside the system, no record permissions |
| Odoo-style chatter on every record, with system log lines | Familiar | Mixes talk with audit and state history, a second queue, grows every timeline |
| Record threads for talk only, on an allowlist of subjects (chosen) | Small, follows record permissions | No automatic history in the thread |
| Order and unread by UUIDv7 | No counter | Against ADR-0006 rule 6; commit order differs from ID order, so messages are missed |
| A sequence per conversation under its row lock (chosen) | Exact, gapless | One lock per post in a conversation |
| E-mail each notification, or include the text | Simple, informative | Floods people; talk leaves the system |
| One grouped e-mail per run or digest, re-checked at send, no text (chosen) | Quiet; nothing sent after access is lost | A 5-minute delay |
| Delete old messages for retention | Simple | Replies block parents; sequences break |
| Clear old bodies, keep rows (chosen) | Threads and order stand | Metadata stays until the conversation goes |
| Notify every holder of a role or stage | Nobody misses it | Floods a team; the first 20 of a stage, top to bottom |
| Search in Phase 1 | Useful | A new read path to secure; cut for lightness |

## Consequences

- **People:** talk about an order or an invoice where it lives, get told when someone needs them or an approval waits, and get at most one e-mail per 5 minutes when away.
- **Privacy:** talk stays in the system; e-mail carries no text; agents never see it; nothing is mailed after access is lost; retention is a company setting with a 30-day grace.
- **Build:** seven tables, 10 person-facing and 4 internal commands, 4 queries, 4 events, two consumers. One SMTP account. Small-model friendly.
- **Revisit when:** companies ask for push or a mobile app; for search; for agents that summarize threads; for a bridge to an outside chat product.

## Documents updated

- **ADRs** (notes tagged "ADR-0076, 2026-11-21"): ADR-0013 rule 10; ADR-0027 rule 1; ADR-0038 rule 14; ADR-0040 rules 13 and 14; ADR-0042 rule 14; ADR-0052 rule 25; ADR-0055 rule 4 (`approval_stage_member.position`); ADR-0063 rule 29; [ADR-0050](0050-agent-runtime-and-query-layer.md) rule 30 (note of 2026-11-21: the four messaging queries are on no tool list).
- **Catalogs:** authorization-areas.csv (2), role-template-levels.csv (16), settings.csv (3), invariants.csv (5), edge-cases.csv (10).
- **Design:** DS-63-messaging.sql (new); DS-15-access.sql (`approval_stage_member.position`); spec 07's approval-channels line (the author's decision of 2026-11-19); DS-04 (eight errors); DS-16 and DS-17 (blocks and counts); backlog (DS-63); the glossary (new rows only); the generated overview.
- **Lab:** `t30_messaging.py` and the lab README.
- **Index and log:** docs/adr/README.md; docs/open-questions.md; docs/runbook/step-log.md.

## Edge cases and invariants

**Invariants** (DS-16; block INV-880 to INV-889, INV-880 to INV-884 taken; first step 5):

- **INV-880** `record_thread_subject_exists` (area `platform`): every record thread names an existing row of an allowed subject table, of its company.
- **INV-881** `message_sequence_gapless` (area `platform`): the messages of a conversation have the sequences 1 to its `last_sequence`, each once.
- **INV-882** `direct_members_fixed` (area `platform`): the member rows of a direct conversation are exactly the 2 to 8 users of its `direct_key`.
- **INV-883** `messaging_people_only` (area `safety`): no audit row of a person-facing messaging command carries an agent run, an integration client or an automation rule as actor or origin.
- **INV-884** `notification_email_consistent` (area `platform`): every notification carried by an e-mail has the e-mail's recipient and company.

**Edge cases** (DS-17; block EC-340 to EC-349, all taken; first step 5):

- **EC-340** `mention_in_record_thread`: a mention on a sales order's thread notifies the person; read within 5 minutes, no e-mail; unread, it goes out in the next mail run, together with the person's other due notifications.
- **EC-341** `mention_without_access`: mentioning a person who cannot read the purchase order is refused with `mention_not_permitted`; 21 mentions are refused with `mention_limit`.
- **EC-342** `private_channel_hidden`: a non-member, and a member who left, see nothing of a private channel in `ListConversation`, `ListMessage` or its attachments.
- **EC-343** `direct_group_fixed`: adding a fourth person to a direct conversation of three is refused with `direct_conversation_fixed`; creating one with the four opens a new conversation; a third party cannot open the pair's conversation.
- **EC-344** `approval_notifies_stage`: a purchase order waiting at a stage with three eligible approvers notifies the three, each e-mailed after 5 minutes if unread; a stage of 25 notifies the first 20 from the top of its member list, and the other 5 see the item in the queue.
- **EC-345** `agent_cannot_post`: an agent run's `CreateMessage` is refused with `tool_not_allowed`; an integration client's with `human_only`.
- **EC-346** `record_access_revoked`: a person loses access to a customer's documents, or holds only own-document owner scope; the threads and notifications of the others' documents are hidden from their lists and unread counts.
- **EC-347** `daily_digest_grouped`: three followed-thread notifications unread at the digest hour arrive in one e-mail, with rendered lines and one link, no message text.
- **EC-348** `retention_clears_bodies`: with `messaging.message_retention_days` set from 0 to 365, after the 30-day grace the daily job clears older bodies, keeps a young reply and its cleared parent, ends their attachment links and deletes their notifications.
- **EC-349** `no_mail_after_departure`: a person whose role assignment ends at 16:00 gets no 17:00 digest; their pending notifications are dropped from e-mail.
