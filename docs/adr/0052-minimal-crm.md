# ADR-0052: Minimal CRM: partners, contacts, interaction timeline, email intake

Status: accepted (2026-11-15) under ADR-0005, reviewed by Claude Fable 5.2 (builder Claude Opus 5.5). Design item: DS-35. Foundation: [ADR-0019](0019-partners-and-crm-foundation.md). Related decisions: D2, D5, D12, D16. Principles 3, 6, 7, 8, 9, 12, 13. ADR-0004, ADR-0007, ADR-0008, ADR-0009, ADR-0013, ADR-0016, ADR-0017, ADR-0022, ADR-0027, ADR-0028, ADR-0029, ADR-0030, ADR-0038, ADR-0039, ADR-0042, ADR-0043, ADR-0044, ADR-0045, ADR-0048, [ADR-0050](0050-agent-runtime-and-query-layer.md), [ADR-0051](0051-agent-workflows.md), [ADR-0053](0053-core-neutrality.md); spec 03, 09, 13, 14, 17.

## Decision

ADR-0019 laid the foundation of the CRM: one partner with roles, contacts, append-only interactions, a timeline built by query, deterministic e-mail matching, consent records and a gate on outgoing messages. DS-35 completes it for Phase 1 in the layer-4 module `crm`. A DDL draft, [DS-35-crm.sql](../design/DS-35-crm.sql), loads with DS-20 and DS-06 in the design lab.

**What Phase 1 has.**
- Partners and contacts (DS-20), and the e-mail domains of partners.
- Interactions: e-mails, calls, meetings, chats, notes and follow-up tasks.
- E-mail intake from company mailboxes, with sender authentication, attachments and the natural key of ADR-0030.
- Complaints, open or closed. Their events tell `cash` not to chase a customer who has an open issue.
- Processing purposes and bases (the consent records), data subject requests and erasure.
- Outgoing messages: drafts that a person sends after the consent and scope checks, with delivery tracked apart from the document.

Leads, opportunities, marketing automation, appointments, chat connectors and semantic search stay after Phase 1.

**Agents first, safely.** ADR-0052 follows the agent runtime of [ADR-0050](0050-agent-runtime-and-query-layer.md) and the workflows of [ADR-0051](0051-agent-workflows.md); it changes neither.
- Deterministic code records, authenticates and matches every e-mail before any agent sees it. That intake runs as `system`, not as an agent run.
- E-mail content is untrusted, and any agent run that reads it is tainted. A tainted run creates only drafts: outbound message drafts, data subject request drafts and change proposals (the strict reading of spec 03 rule 1, flagged).
- Everything else an agent wants in the CRM is a change proposal that a person submits and approves: new partners, matches, interactions, tasks, summaries, complaints and consent changes.
- The timeline returns no untrusted field unless the caller asks for it.

**One timeline without cross-module imports.** The shared `document` row gains the document's partner and date. `crm` then composes interactions, complaints and all of a partner's documents through the layer-2 `documents` contract. It never imports `sales`, `purchasing` or `cash`, and nothing is copied.

**Personal text outside immutable rows.** Documents in a final state never change (ADR-0009 rule 14), yet erasure must blank personal text. So the subject and body of an outbound message and the requester data of a data subject request live in `crm` content tables that the header and the version reference by hash. Erasure blanks only those rows.

**Vietnam stays an overlay** ([ADR-0053](0053-core-neutrality.md) rule 1). Public mail domains of Vietnamese providers, words removed from names before comparing them, extra letter folds, the phone format, consent purposes and request deadlines are package data of `l10n_vn`, flagged until verified. The core holds no Vietnamese behavior: its name folding is a fixed, language-neutral Latin-to-ASCII table.

### Rules

**Scope and ownership**

1. `crm` (layer 4, ADR-0022 rule 2) owns the tables of [DS-35-crm.sql](../design/DS-35-crm.sql):
   - partner e-mail domains, and the global list of public mail domains;
   - mailboxes and inbound messages;
   - interactions with their content, participants, links and match candidates;
   - complaints and their linked documents;
   - processing purposes, processing bases, and data subject requests (a document type) with their content;
   - outbound messages (a document type) with their content, recipients, delivery attempts and delivery recipients;
   - interaction summaries, partner insights, tax ID lookups and partner search keys (ADR-0019 rules 18–20).

   `audit` owns `personal_data_processing_log` (rule 26). Partners, contacts and their commands stay in `master_data` (DS-20). The ADRs win if the DDL disagrees.
2. Not in Phase 1, so there is no table or command for them now:
   - **Leads, prospects, opportunities, pipeline** ([09](../spec/09-mvp-scope.md); [13](../spec/13-crm.md) says "draft leads after Phase 1"; ADR-0019 rule 21). A party known only from an e-mail becomes a partner only through rule 16's proposal, with the role it proposes; the approving person decides. Whether a quotation needs the `customer` role is DS-22's.
   - **Marketing automation:** campaigns, lists, bulk sends, unsubscribe links.
   - **Appointments:** calendars, invitations and reminders outside the work queue (rule 19 has the minimal follow-ups).
   - **Channels and search:** chat connectors (Zalo Official Account), semantic search with pgvector, call recording.
3. Database conventions are DS-20's:
   - **Row-level security.** Every `crm` table carries `company_id`, `FORCE ROW LEVEL SECURITY` and the generated company policy (ADR-0017 rule 19), except the global catalog `public_mail_domain`. The lab checks the list.
   - **Keys.** References inside a company are composite on (`company_id`, `id`).
   - **Contact keys.** DS-20's `contact` gains `UNIQUE (company_id, id)` and `UNIQUE (company_id, partner_id, id)`. A row that names a partner and a contact then holds both in one key, and the database refuses a contact of another partner. It also gains indexes on (`company_id`, `email`) and (`company_id`, `phone`) for matching and duplicate search, `CHECK (email = lower(email))` as the database's half of rule 4, and the flag `is_accounts_contact` (rule 28).
   - **Times.** Every row carries `recorded_at` (ADR-0007 rule 9), including `public_mail_domain`. Rows that erasure blanks carry `erased_at`. Tables whose rows change in place (`mailbox`, `complaint`, the match columns of `interaction`) also carry `version` or a cursor of their own.
   - **Order.** The DDL loads top to bottom after DS-20 and the shared `document` row: each table follows the tables it references. The lab checks this.

**Partners, contacts and e-mail domains**

4. Commands normalize what matching compares: DS-20's contact commands (`CreateContact`, `UpdateContact`; ADR-0019 rule 8; ADR-0045) and the commands of this ADR:
   - **E-mail addresses** are trimmed and lowercased, with the domain in IDNA ASCII form. An address that does not parse fails with `validation_failed`. DS-20's check on `contact.email` refuses an address that is not lowercase.
   - **Phones** are normalized to E.164 by the package's phone rule, with the company's country as default. Like tax ID rules, the rule is flagged until verified (ADR-0019 rule 4; ADR-0016 rule 5). Without a package rule, the core accepts only numbers already in E.164 form.
   - **Names** are normalized for search as rule 17 says.
5. `partner_email_domain` (partner, `domain`, `is_active`, `erased_at`) holds the domains that ADR-0019 rule 15's third step matches. ADR-0045 rule 1 deferred this table to DS-35.
   - **Form.** Lowercase IDNA ASCII, matched exactly. A subdomain is a row of its own; there are no wildcards. Unique per partner and domain.
   - **Public mail domains.** The global catalog `public_mail_domain` (`domain`, `source`: `core` or `package`, `package_code`, `recorded_at`). The core seeds the large free providers, and the active package adds local ones. A domain in the list cannot be a partner's: `public_mail_domain`. Matching also skips a listed domain at match time, so a row created before its domain was listed never matches (rule 15). This settles ADR-0019, which says "listed by the core" in rule 15 and "package rules" in its constraints: both apply.
   - **Shared domains.** One domain on two active partners (companies of a group) is accepted with the check result `email_domain_shared`. Matching by that domain then never finds exactly one partner.
   - **Commands.** `CreatePartnerEmailDomain` and `UpdatePartnerEmailDomain` (activation) have effect class `master_data_change`, so agents propose them (ADR-0029 rules 2, 4).
   - **From `CreatePartner`.** DS-20's `CreatePartner` takes optional `email_domains`. `master_data` cannot write a `crm` table, so it declares a partner e-mail domain hook that `crm` registers and `app` wires (ADR-0022 rule 2's hooks). The hook runs the checks above and writes the rows in the same transaction. Rule 16's proposal uses it.
   - **Personal domains.** The domain of an individual partner is personal (rule 29); erasure blanks it, sets `erased_at` and deactivates the row (rule 25).

**Interactions**

6. `interaction` follows ADR-0019 rule 12, settled as follows:
   - **Kinds and directions.** `kind`: `email`, `call`, `meeting`, `chat`, `note`, `task`. Notes and tasks have `direction` `internal`. The others are `inbound` or `outbound`, by who started the contact. The database checks both.
   - **Time.** `occurred_at` is an instant. For an inbound e-mail it is the provider's receive time; for an outbound one, the send time. A call, meeting or chat later than now plus five minutes of clock skew fails with `interaction_in_future`, because appointments come after Phase 1.
   - **Partner and contact.** Both are empty until the interaction is matched. A contact needs its partner, and the composite key keeps the contact inside that partner.
   - **`match_method`.** `reply`, `contact_email` or `domain` for an automatic match of an inbound e-mail (rule 15); `entered` when the creator named the partner; `confirmed` after `MatchInteraction`. The database holds that a partner is set exactly when a method and `matched_at` are. `version` counts the match changes.
   - **Source fields.** The mailbox, provider key, `Message-ID` and sender authentication of ADR-0019 rule 12 live on `inbound_message` (rule 13), not on the interaction.
   - **`is_untrusted`.** True for every inbound e-mail (a database check) and for any interaction an executed proposal of a tainted agent run created. Then its subject, content, and its participants' addresses and names are untrusted fields (ADR-0029 rule 10).
   - **Corrections.** A correction is a new interaction whose `correction_of_id` names the earlier one (ADR-0019 rule 12).
   - **Erasure.** `erased_at` marks an interaction whose subject erasure blanked (rule 25).
7. Interactions are append-only, and the database holds it. A trigger on `interaction`, `interaction_content`, `interaction_participant`, `inbound_message`, `processing_basis`, the content tables of rules 24 and 27, and the delivery tables of rule 28 refuses deletes and refuses changes to any column except:
   - columns that change in normal work: the match columns and `version` of an interaction, and `recorded_at` everywhere;
   - columns set once from empty: `ended_at` and `end_reason` of a processing basis, a participant's contact, and the outcome columns of a delivery attempt;
   - columns that only the erasure command changes: subjects, bodies, addresses, names, the raw `Message-ID`, sender authentication results, failure reasons, requester data, outcome notes, the `content_salt` of content rows, and `erased_at`. The trigger allows them only when `erpme.erasure_command_id` is set, which the dispatcher does only for `EraseDataSubject` (ADR-0038 rule 4).
   - **Draft deletes.** The two content tables (`outbound_message_content`, `data_subject_request_content`) also allow `DELETE`, but only inside the generated `Delete` of their document: the dispatcher alone runs `SET LOCAL erpme.document_delete_id` to the document's ID for that command, and the trigger allows the delete only when the setting names the row's document and that document is still a `draft`. As for the erasure gate (ADR-0038 rule 4), DS-36 checks that an idempotency record of a generated `Delete` command for that document exists in the same transaction. `Delete` itself accepts only a never-submitted, unreferenced draft (ADR-0009 rule 4), and removes the header, the recipients and then the content rows in the same transaction. Content rows of superseded draft versions are not deleted by `Update`: the versions refer to them, so they stay until erasure, or until a retention rule the author decides (rule 30).

   `personal_data_processing_log` gets a trigger of its own that refuses every update and delete (rule 26).
8. Content, participants and attachments:
   - **`interaction_content`**, one row per interaction: `body_text`, plain text, and `erased_at`. HTML is converted to text by a sanitizer and never stored as HTML.
   - **`interaction_participant`:** `role` (`from`, `to`, `cc`, `bcc`, `reply_to`, `attendee`), `email_address`, `display_name`, the `contact_id` or `user_account_id` it resolves to, and `erased_at`. Attendees of calls and meetings are contacts or users.
   - **Attachments** are stored by `attachments` and linked to the interaction (ADR-0027 rule 2). Those from inbound e-mail are untrusted (ADR-0038 rule 14). The raw message is an attachment too, kept for evidence and referenced by its inbound message (`raw_attachment_id`).
9. Links, never copies (ADR-0019 rule 13):
   - **`interaction_link`** points from a matched interaction to one document (`document_id`, any type) or one complaint (`complaint_id`), and is unique per target. It carries the interaction's `partner_id`.
   - **`complaint_document`** links a complaint (`complaint_id`) to documents (`document_id`) the same way, with the complaint's `partner_id`.
   - **Partner check.** A link needs a matched interaction, and a target whose partner is set and equals the interaction's or the complaint's: the document's `partner_id` (rule 18) or the complaint's partner. Otherwise `link_partner_mismatch`. This holds for every actor, so a link never leaks another partner's record into a timeline. The database holds the interaction's and the complaint's side by composite keys on (`company_id`, `id`, `partner_id`); the document's side is the command's check.
   - **Matching and links.** `MatchInteraction` and `UnmatchInteraction` recheck the interaction's links and refuse with `link_partner_mismatch` when a link would conflict with the new partner or with none; the person removes the link first. The composite key refuses the same in the database.
   - **Commands.** `CreateInteractionLink` and `DeleteInteractionLink` have effect class `other`.
10. Interaction commands:
    - **`CreateInteraction`** for every kind except inbound e-mail, with participants, content, links, and for a task its due date and assignee. People run it directly. It is registered `is_proposal_bound`, so an agent proposes it in a change proposal that a person submits and approves (ADR-0029 rules 2–4).
    - **`MatchInteraction`** (partner, optional contact) runs only on an unmatched interaction, else `interaction_already_matched`. It is registered `is_proposal_bound`. It resolves the interaction's `interaction_unmatched` work item and, for an inbound e-mail whose sender authentication passed, raises `inbound_message_matched` (rule 15).
    - **`UnmatchInteraction`** is `human_only`, takes a reason, raises `interaction_unmatched` again, and recomputes the match candidates (rule 15).
    - **Events:** `InteractionCreated`, `InteractionMatched`, `InteractionUnmatched`.

**E-mail intake**

11. `mailbox` (ADR-0019 rule 14):
    - **Columns:** `code`, `name`, `email_address`, `connector_kind` (`imap` in Phase 1), `connector_settings` (host, port, folder, submission server; never a secret), `credential_ref` (a key in the installation's secret store, DS-37; the database never holds the secret), `authserv_id` (rule 14), `owner_user_id`, `is_intake_enabled`, `is_sending_enabled`, `intake_cursor`, `last_intake_at`, `consecutive_failure_count`, `is_authentication_verified`, `authentication_probe_result`, `authentication_checked_at`, `is_active`, `version`.
    - **Commands.** `CreateMailbox` and `UpdateMailbox` are `human_only`.
    - **Connector.** The interface `crm.contract.MailboxConnector`: fetch after a cursor, fetch one message by key, send, and find a sent message by `Message-ID`. The core adapter is IMAP over TLS with SMTP submission. Other providers (Microsoft Graph, Gmail API) are later adapters.
    - **Trusted results need a probe.** Rule 14 trusts the topmost `Authentication-Results` field with the mailbox's `authserv_id`. That holds only if the receiving server adds its own field and strips forged ones that carry its authserv-id. So `CreateMailbox`, and `UpdateMailbox` when the connector settings or `authserv_id` change, set `is_authentication_verified` false and request a probe. The external consumer `crm_mailbox_probe` (ADR-0013 rule 10) submits a probe message from the mailbox to itself through the submission server, whether or not `is_sending_enabled` is set, that carries a forged `Authentication-Results` field with the mailbox's authserv-id and a probe token; it fetches the message and records the result with `RecordMailboxAuthenticationCheck` in `authentication_probe_result`:
      - `passed`: the fetched message has exactly one field with that authserv-id, it is the topmost field, and the forged one is gone;
      - `probe_no_field`: the message carries no field with that authserv-id at all. Servers often add none to locally submitted mail, so this is an expected result; the mailbox stays on manual matching;
      - `forged_field_kept` or `field_not_topmost`: the server does not protect the field;
      - `transport_error`: the probe could not complete.

      Only `passed` sets `is_authentication_verified`, and only a completed probe with a negative result (`probe_no_field`, `forged_field_kept`, `field_not_topmost`) clears it; a `transport_error` keeps the last state. The probe proves stripping on the submission path only; that the server treats mail from outside the same way is the administrator's configuration, which the probe cannot see (flagged). A person can repeat the probe with `VerifyMailboxAuthentication`; the consumer also repeats it daily. While `is_authentication_verified` is false, intake marks every message of the mailbox not authenticated, with reason `mailbox_not_verified`, and nothing is matched automatically. Intake skips the probe message by its token.
    - **Ownership.** ADR-0019 listed mailbox connectors under DS-24, which is now the e-invoice add-on (backlog). They belong here.
12. The intake run:
    - **Not an agent run.** Intake is deterministic code that runs as actor `system` on behalf of the mailbox owner (ADR-0027 rule 14; ADR-0017 rule 12). It calls no LLM and never classifies content. Spec 03 rule 1 restricts agent runs that read untrusted content; intake is not one, so it may record inbound messages and their interactions directly. Labeling every inbound e-mail untrusted (rule 6) is how intake meets that rule.
    - **Schedule.** The job `mailbox_intake` runs per enabled mailbox every `crm.intake_interval_minutes` (company setting, default 5), on the `integrations` queue. `RunMailboxIntake` starts one now; it emits `MailboxIntakeCompleted`.
    - **Fetch.** It fetches at most `crm.intake_batch_size` messages (default 50) after the cursor, with no transaction open (ADR-0013 rule 10). It streams each raw message and its parts to the object store.
    - **One batch per message.** It then dispatches one command batch (ADR-0008 rule 20): `CreateAttachment` for the raw message and for each part of an allowed type (ADR-0038 rule 13), then `RecordInboundMessage`, which refers to them. Parts of other types are named in the message's `parse_notes` and stay only inside the raw message. A message above `attachment_max_bytes` is recorded without parts, with a parse note.
    - **Permissions.** The intake declares only these two commands and `RecordMailboxIntakeOutcome`.
    - **Cursor.** `RecordInboundMessage` advances the cursor in its own transaction, so a crash re-fetches only uncommitted messages, which the natural key skips.
    - **Failures.** After each run, `RecordMailboxIntakeOutcome` records success or failure and `last_intake_at`. `crm.intake_failure_limit` consecutive failures (default 3) raise `mailbox_unreachable` for the mailbox's `owner_user_id` (owner rule `subject_owner`); the next success resolves it.
13. `inbound_message` and the natural key (ADR-0030 rule 10; ADR-0019 rule 14):
    - **Provider key.** `provider_message_key` is the provider's stable key (IMAP: `UIDVALIDITY` and `UID`), unique per mailbox (`mailbox_id`). A message fetched twice is skipped without a command.
    - **Hashes.** `message_id_hash` is the SHA-256 of the normalized `Message-ID`. `content_hash` is the SHA-256 over the `From`, `To`, `Cc`, `Date`, `Subject` and `Message-ID` headers and the MIME body. Trace headers that differ per mailbox (`Received`, `Delivered-To`, `Authentication-Results`) are left out.
    - **The same message in a second mailbox** has the same two hashes. Its row points with `duplicate_of_inbound_message_id` to the canonical row, the one that is neither a copy nor an own message, and shares its interaction; no second interaction is made. A unique index on (`company_id`, `message_id_hash`, `content_hash`) over canonical rows holds this. A composite foreign key holds that a copy has the same hashes and the same interaction as its target, and that the target is canonical (the generated columns `is_canonical` and `duplicate_target_canonical`), so a copy never points to a copy.
    - **A reused `Message-ID` with other content** gets its own interaction and the check result `duplicate_suspected` (DS-04).
    - **No `Message-ID`:** only the provider key applies.
    - **Our own messages.** An inbound message whose `Message-ID` is one of the company's sent messages counts as own only when its sender authentication passed and its `From` address equals a company mailbox address, or when its `content_hash` equals the `sent_content_hash` of the sent attempt (rule 28). It is then recorded with `is_own_message`, points to the outbound interaction, and creates no interaction. Otherwise it is a reused `Message-ID`: it is processed as any other message, with `duplicate_suspected`.
    - **What is kept in clear.** The raw `Message-ID`, the sender's address, display name and domain are kept for display. They are personal and untrusted, and erasure blanks them. `In-Reply-To` and `References` are kept only as hashes (`referenced_message_id_hashes`). Matching and deduplication use only hashes and normalized addresses.
    - **Other columns:** `received_at` (the provider's receive time), `raw_attachment_id`, `parse_notes`, `erased_at`.
14. Sender authentication:
    - **Source.** Results are read only from `Authentication-Results` header fields (RFC 8601) whose authserv-id equals the mailbox's `authserv_id`, taking the topmost such field: the one the company's receiving server added, which the probe of rule 11 verified. Headers the sender wrote, or copies from other servers, are ignored. Without such a field, or on a mailbox whose probe has not passed, the message is not authenticated.
    - **Parsing.** A parser of the RFC 8601 grammar reads the fields: quoted strings, comments and folding whitespace are tokens of the grammar, never text to split on. So `smtp.mailfrom="a; dmarc=pass"@x` is one property value. It fails closed: a field above ours whose authserv-id cannot be read, or our field with any syntax error, makes the message not authenticated, with reason `results_unparsable`.
    - **The sender** is the single mailbox of the RFC 5322 `From` field. Zero or several `From` addresses, or several `From` fields, mean not authenticated (`from_not_single`). `Sender` and the envelope sender are never used.
    - **When it passes.**
      - DMARC `pass`, when the result's `header.from` equals the `From` domain. A DMARC `pass` without `header.from` falls through to the exact DKIM test below; one whose `header.from` names another domain is not authenticated.
      - DMARC absent or `none` (no policy published): a DKIM signature that passes and whose `header.d` domain equals the `From` domain exactly.
      - DMARC `fail`, `temperror`, `permerror`, any other value, or two different DMARC results: not authenticated. Errors fail closed.
      - SPF alone never passes. ARC is not trusted in Phase 1.
    - **Stored:** `sender_authentication` (the parsed results and the reason) and `is_sender_authenticated`.
    - **One function.** The rule is one core function, used by intake and by tests.
15. Matching (ADR-0019 rule 15, made exact). It runs only when the sender authentication passes. Each step runs only if the one before found nothing:
    1. **Reply.** A referenced `Message-ID` hash equals that of one of the company's sent outbound messages (rule 27), and the sender address is an active contact address of that message's partner or one of its delivery recipients. The match is that partner, with the contact when the address belongs to one contact of it.
    2. **Contact address.** Active contacts of active partners whose `email` equals the sender address. One partner gives a match. The contact is set when exactly one contact of that partner has the address.
    3. **Domain.** Active `partner_email_domain` rows equal to the `From` domain, skipped when the domain is in `public_mail_domain` at match time.

    A partner superseded under ADR-0019 rule 19 is replaced by its successor before counting. Exactly one partner: the interaction is matched with its `match_method`. Otherwise (none, several, or not authenticated) it stays unmatched, with the check result `interaction_unmatched` and the work item `interaction_unmatched`.
    - **Work items.** An inbound e-mail whose sender authentication passed and that is matched, here or later by `MatchInteraction`, raises `inbound_message_matched` (owner `role:sales`), which the quotation agent declares ([ADR-0051](0051-agent-workflows.md) rule 14). ADR-0051 named the kind `inbound_message`; it is renamed so that it names the event it stands for. An unauthenticated message matched by a person raises none, so no agent wakes on it; a person may still start an agent on it (ADR-0051 rule 14).
    - **Candidates.** The unmatched case stores at most ten `interaction_match_candidate` rows, one per partner, each with its best `reason`. Reasons, in this order: a step found several partners (`several_partners`); the contact or domain step found a partner while authentication failed (`contact_email_unauthenticated`, `domain_unauthenticated`); a tax ID in the body, found by the package's format rule, equals a partner's normalized tax ID (`tax_id_in_content`); the sender's display name is similar to a partner's name by rule 17 (`name_similarity`, with its `score`). The order of the rows (`rank` 1 to 10, unique per interaction) is: by reason in that order, then `score` descending, then partner code.
    - **Recomputed.** `UnmatchInteraction` replaces the candidates by a new computation; candidates are evidence, not history.
    - **Evidence only.** Candidates are evidence for a person, never a match (ADR-0019 rule 15). Forwarded content, a message inside a message, is never matched.

    Note: the owner rule `role:sales` resolves as `role:sales_clerk`, through `role.template_code` ([ADR-0054](0054-users-roles-and-authorizations.md) rule 11).

**Customer onboarding from e-mail**

16. An e-mail from an unknown sender follows [ADR-0051](0051-agent-workflows.md) rules 11–13:
    - **The work item.** It waits in `interaction_unmatched` (rule 15). A person matches it (`MatchInteraction`), creates the partner and contact (DS-20), or ends it with `ResolveWorkItem` and a reason such as spam.
    - **Authenticated senders only.** The agent type `customer_onboarding` declares the kind but runs only when the sender authentication passed (ADR-0051 rule 12, D1). An unknown sender that is not authenticated goes to people, with no agent.
    - **The proposal.** The run starts tainted (ADR-0050 rule 15). It drafts one change proposal (ADR-0029 rule 1) with a `CreatePartner` item, role `customer`, the sender's domain in its `email_domains` unless the domain is public (rule 5), and one `CreateContact` item per contact, the sender first. It never creates a partner, contact or domain itself: such commands are not `is_draft_only` (`tainted_run_not_allowed`, ADR-0050 rule 26) and need a proposal (`proposal_required`, ADR-0029 rule 4). It proposes no match.
    - **The role.** The proposal sets the `customer` role, which the quotation agent needs before it may run for the partner ([ADR-0051](0051-agent-workflows.md) rule 14). The approving person decides; a person may change the proposal before submitting it, and the approver may reject it.
    - **Evidence and taint.** The proposal names the interaction and the agent run. It is tainted (ADR-0029 rule 8), so a person submits it and another person approves it (ADR-0051 rule 13).
    - **Duplicates on approval.** The proposal screen calls `ListPartnerDuplicateCandidate` (rule 17) with the proposed tax ID, name, contact address and domain, for the approving person.
    - **The match.** After the proposal is executed, a person confirms the interaction's match with `MatchInteraction` and resolves the item (ADR-0051 rule 13).
    - **No identities for tainted runs.** A tainted run never receives other partners' identities. `ListPartnerDuplicateCandidate` and the timeline refuse it with `tainted_read_out_of_scope` (ADR-0050 rule 27). Check results in a plan returned to it, such as ADR-0019 rule 4's `partner_duplicate_suspected`, carry only the code and a count; the full details stay on the proposal for the approver.
    - **After execution,** `crm`'s consumer of `PartnerCreated` runs the duplicate search again (rule 17).
17. Duplicate search (ADR-0019 rule 19), deterministic and bounded:
    - **Query.** `ListPartnerDuplicateCandidate` takes any of tax ID, name, e-mail, domain and phone, and optionally a partner to leave out.
    - **Keys.** Normalized tax ID equal (package rule, ADR-0019 rule 4); contact e-mail equal; partner e-mail domain equal; contact phone equal (E.164, on DS-20's phone index); name similarity by `pg_trgm` (installed, ADR-0022 rule 8) at or above `crm.duplicate_name_threshold` (company setting, default 0.6, flagged for tuning).
    - **Normalized name.** Lowercase; Unicode NFKD with combining marks removed; then the core fold table, a fixed, language-neutral Latin-to-ASCII table: `đ`→`d`, `ð`→`d`, `ł`→`l`, `ø`→`o`, `ß`→`ss`, `æ`→`ae`, `œ`→`oe`, `þ`→`th`, `ı`→`i`, `ħ`→`h`; then punctuation to spaces and spaces collapsed. A package may add fold pairs as package data `partner_name_fold_pairs`, next to `partner_name_stop_words`. Then the package's stop words, such as legal-form words, are removed; the core list is empty. The result is kept in `partner_search_key` (`normalized_name`, `normalized_tax_id`).
    - **Order and bound.** At most ten results. A partner found under two reasons counts once, with its best reason. Ordered by reason (tax ID, e-mail, domain, phone, name), then similarity descending, then partner code. The same data gives the same answer.
    - **Upkeep and work items.** `crm`'s consumer of `PartnerCreated`, `PartnerUpdated`, `ContactCreated` and `ContactUpdated` updates the search key, then searches. Any candidate raises the existing kind `partner_duplicate_suspected`, with the candidates as evidence. Nothing is merged automatically.
    - **Nightly scan.** Two partners created at the same moment can each miss the other's key. The nightly job `RunPartnerDuplicateScan` repeats the search for partners changed since its last run and emits `PartnerDuplicateScanCompleted`.

**Partner timeline**

18. `ListPartnerTimeline`, a query of `crm`:
    - **The shared document row.** ADR-0009 rule 1's `document` gains `partner_id` and `document_date` (both nullable) and a unique key on (`company_id`, `id`). A document type declares at registration (ADR-0009 rule 2) `partner_field`, the header column that names its partner or none, and `is_on_partner_timeline`, true by default when it has a partner field. The owning module passes both values to `documents.contract` at every version, so they always equal the header (INV-49). Types whose partners sit on lines, such as general journal entries, declare none and stay off the timeline.
    - **Sources.** `crm`'s interactions and complaints of the partner, and `documents.contract.list_partner_documents` for the partner's documents of every timeline type: quotations, orders, deliveries, invoices, returns, payments and the others DS-22 and DS-25 register. `crm` imports no other layer-4 module (ADR-0022 rules 2 and 6; the practice of ADR-0048 rule 17). `outbound_message` and `data_subject_request` declare `is_on_partner_timeline: false`; a sent message appears as its outbound interaction.
    - **Superseded partners.** `include_superseded` (default true) adds the entries of partners superseded by this one.
    - **Entry.** `entry_kind` (`interaction`, `complaint`, `document`), `entry_date`, `entry_at`, the record ID, kind or document type, direction, state (document state, complaint state, or a task's work item state), number, contact and links. `entry_date` is the company-local date of `occurred_at`, the complaint's opening date, or `document_date`. `entry_at` is `occurred_at`, `opened_at`, or the first version's `recorded_at`.
    - **Order.** By `entry_date`, `entry_at` and ID, all descending, with a keyset cursor on the three (DS-04 queries).
    - **Untrusted fields.** Subjects and summaries come only with `include_untrusted` (default false). Returning one taints the calling run (ADR-0029 rule 10). Without it the timeline taints nothing.
    - **Permissions.** A document entry appears only when the actor holds that type's `Get<Type>` query and the document is inside their record scope (ADR-0017). Others are left out, and `is_scope_filtered` is true. Field classes apply as usual.
    - **Tainted runs** may ask only for their scope partner (spec 03 rule 1; ADR-0029 rule 14; ADR-0050 rule 27); otherwise `tainted_read_out_of_scope`.
    - **No amounts.** Entries carry no amounts; callers read the document. DS-33 may expose the same rows as a view.

    Note: a document entry also needs the document inside the actor's read owner scope; otherwise it is left out and `is_scope_filtered` is true ([ADR-0054](0054-users-roles-and-authorizations.md) rule 15).

**Follow-up tasks**

19. A follow-up is an interaction of kind `task`, with `due_date`, `assignee_user_id` and text, usually linked to a document ("call back about the quotation"):
    - **Its work item.** `CreateInteraction` raises `follow_up_due` with the interaction as subject, the assignee as owner by the new owner rule `subject_assignee`, and due rule `subject_due_date` (ADR-0042 rules 5, 7, 8).
    - **Its state** is the work item's state; `crm` stores none. Done is `ResolveWorkItem`; reassignment is `AssignWorkItem`.
    - **Changes.** A new due date or text is a new task with `correction_of_id`. Its command resolves the earlier task's work item with resolution `superseded`.
    - **Agents propose tasks.** `CreateInteraction` is `is_proposal_bound` (rule 10), so an agent's task is a change proposal that a person submits and approves; a tainted run may create the proposal, which is a draft (ADR-0050 rule 26). ADR-0013 rule 11 limits consumers of tainted events and does not grant this. A task executed from a tainted proposal is untrusted.
    - **Scope.** These are the minimal follow-ups of Phase 1. Activities with calendars, recurrence and invitations stay after Phase 1 (ADR-0019 rule 21 gets a note). Spec 09 places "activities and appointments" after Phase 1, and tasks with an assignee and a due date resemble activities; tasks stay as the flagged interim (open question).

**Complaints**

20. `complaint`:
    - **Columns:** partner (required), contact, `origin_interaction_id`, `category` (`delivery`, `quality`, `billing`, `service`, `other`), `title`, `is_title_untrusted`, `state` (`open`, `closed`), `opened_at`, `closed_at`, `resolution_note`, `erased_at`, `version`. Linked documents are in `complaint_document`.
    - **Commands.** `CreateComplaint` opens it and raises `complaint_open` (owner `role:sales`, due in two days, resolved by `CloseComplaint`). `UpdateComplaint` changes category, title and documents. `CloseComplaint` takes a resolution note. `ReopenComplaint` opens it again. Other transitions fail with `invalid_state_transition`.
    - **Agents propose.** The four commands are `is_proposal_bound`, because their effect reaches `cash`'s dunning; a person decides. A title an agent wrote from untrusted content sets `is_title_untrusted`.
    - **Not a document type.** A complaint has no versions, approval or number; its history is in `audit` (ADR-0038).

    Note: the owner rule `role:sales` resolves as `role:sales_clerk`, through `role.template_code` ([ADR-0054](0054-users-roles-and-authorizations.md) rule 11).
21. The complaint events that `cash` consumes (ADR-0048 rule 17):
    - **Names.** `ComplaintCreated`, `ComplaintUpdated`, `ComplaintClosed` and `ComplaintReopened`, with the complaint as subject and its ID, partner ID and state as payload. Under ADR-0004 rule 22, `CreateComplaint` emits `ComplaintCreated`; there is no `ComplaintOpened`, because the verb Open belongs to posting periods.
    - **Order does not matter.** Events of different complaints have no common order (ADR-0013 rule 3). So on each event the `cash` consumer reads the partner's open complaints through the query `ListComplaint` and sets `has_open_complaint` to whether any exist. Two complaints closed in either order leave the right flag (INV-501). `cash` still never imports `crm`.

**Consent and data subjects**

22. `processing_purpose`, company data seeded from the package (ADR-0016 rules 6–7):
    - **Columns:** `code`, `name`, `is_consent_required`, `message_types` (the outbound message types the purpose covers; one purpose per type, checked by the command), `basis` (the package basis, as in DS-20), `is_active`.
    - **Core template** when the package has none: `contract_communication` (no consent; types `reply`, `document`, `payment_reminder`, `follow_up`, `general`) and `marketing` (consent; type `marketing`). Their rows carry the basis `{"source": "core_template"}`, set by the command like every package basis, so `basis` is never empty.
    - **Vietnam.** The `l10n_vn` purposes are flagged `unverified` (open question).
    - **Commands.** `CreateProcessingPurpose` and `UpdateProcessingPurpose`, effect class `master_data_change`.
23. `processing_basis` (ADR-0019 rule 9; ADR-0027 rule 12's names):
    - **Columns:** the data subject (exactly one of contact and partner), the purpose (`processing_purpose_id`), `lawful_basis` (`contract`, `legal_obligation`, `consent`; renamed from ADR-0019's `basis`, which DS-20 uses for package bases), `started_at` (the recording instant; the evidence shows when it was given), `ended_at`, `end_reason` (`withdrawn`, `purpose_ended`, `erased`), `evidence_interaction_id`.
    - **Consent needs evidence:** the interaction that records it, such as an e-mail or a call note. The database refuses consent without it (`consent_evidence_missing`). Silence is never consent.
    - **Subjects.** A partner may be the subject only when it is an individual, a sole proprietorship or an employee partner; else `data_subject_kind_invalid`.
    - **One current basis** per subject, purpose and lawful basis, by a unique index. Rows are append-only except `ended_at` and `end_reason`, set once (rule 7).
    - **Commands.** `CreateProcessingBasis` and `CloseProcessingBasis` (with the end reason) are `is_proposal_bound`: agents propose them from what a message says. While a proposal to close a basis is pending, sending treats the basis as closed (rule 28).
24. Data subject requests and package rules:
    - **`data_subject_request`**, a non-posting document type of `crm` (ADR-0019 rule 10). Header: `request_kind` (`access`, `correction`, `deletion`), the subject (empty until a person identifies it), `origin_interaction_id`, `due_date`, and `content_hash`.
    - **Its content.** The requester's name, e-mail and phone (`requester_name`, `requester_email`, `requester_phone`), the `outcome_note` and the `identity_proof_hash` (the SHA-256 of the evidence a person checked to verify the requester) live in `data_subject_request_content`, a `crm` table keyed by (`company_id`, `data_subject_request_id`, `content_hash`). Each row has a random `content_salt` (128 bits, hex). `content_hash` is the SHA-256 over the request's ID, the salt and the canonical JSON of these fields, so rows are never shared between requests, and once erasure blanks the salt the hash can no longer confirm a guessed value. The header and the version's canonical content (ADR-0009 rule 9) hold only the hash, so neither contains personal text.
    - **Due date.** The package rule gives it, flagged. Without a package rule it is the received date plus the company setting `crm.data_subject_request_due_days` (default 30), an operational default and not a legal deadline; `due_date` is never empty.
    - **Source.** `CreateDataSubjectRequest` raises `data_subject_request_received` (owner `company_owner`, due in one day) with the request as subject, so a person verifies the requester and identifies the data subject; the `UpdateDataSubjectRequest` that sets both resolves it. `SubmitDataSubjectRequest` raises the existing `data_subject_request_due` (due rule `subject_due_date`), resolved when the request closes or is canceled; a draft raises none. A person creates the request after reading a message that asks for access, correction or deletion; an agent may draft one (`is_draft_only`, rule 32) for a person. Intake never classifies messages, and nothing opens a request or erases anything by itself.
    - **Access and correction** are done by people with the existing queries and commands in Phase 1.
    - **Package rules: `data_protection`.** Purposes with their message types, request deadlines, the reserved retention setting (rule 30), `public_mail_domains`, `partner_name_stop_words`, `partner_name_fold_pairs` and the phone rule are package rules of the existing component "Default data labels and personal data rules" of ADR-0016 rule 5, named `data_protection` (the item ADR-0039 rule 10 assigns to DS-35). Every value `l10n_vn` ships is `unverified` until the author verifies it.
25. `EraseDataSubject` (`human_only`, `crm`; ADR-0019 rule 10) takes a deletion request in state `approved` with its subject identified.
    - **The subject's rows.** For a contact: interactions whose `contact_id` is the contact; participants whose `contact_id` is the contact; participants and inbound messages whose normalized `email_address` or `sender_address` equals an address of the subject (the contact's address and those the request names), matched or not. For an individual, sole proprietorship or employee partner: also every interaction, complaint and outbound message of that partner, and its contacts' rows as above.
    - **What is blanked, in `crm`.** The subject's participant addresses and names; for interactions the subject wrote (as their contact, their `from` participant or the sender of their inbound message), the interaction's subject and content; the raw `Message-ID`, sender address, display name, domain, parse notes and `sender_authentication` of the subject's inbound messages; complaint titles and resolution notes of the subject's complaints; the content rows of outbound messages whose only recipient is the subject or whose partner is the subject, the subject's delivery recipient addresses, and the `failure_reason` of those attempts; interaction summaries and tax lookups of the subject; an individual partner's `partner_email_domain.domain` (deactivated); and the requester data and `outcome_note` of the subject's earlier, closed requests. Each blanked row gets `erased_at` and keeps its kinds, dates, partner links and hashes; a blanked content row also loses its `content_salt`, so its hash can no longer confirm a guessed text.
    - **Shared threads.** An interaction with other participants keeps their rows and, when the subject did not write it, its subject and content; only the subject's address and text fields are blanked.
    - **Deleted, not blanked.** The subject's `partner_insight` and `partner_search_key` rows, which are derived and recomputable.
    - **Bases and work items.** It closes the subject's current bases with `end_reason: erased`, and resolves the open `follow_up_due` items of the subject's tasks with resolution `erased` (INV-503).
    - **The request itself.** Its requester data is kept while the request is open, because the answer goes to the requester. `EraseDataSubject` closes the request as its last step and blanks the request's content row except `identity_proof_hash`, which stays as evidence that the requester was verified. How long that proof may be kept is the author's (open question). A deletion request closed without erasure (refused) keeps its requester data as the evidence of the answer, until a later erasure.
    - **Immutable rows stay.** Headers and versions of outbound messages and data subject requests hold no personal text (rules 24, 27), so erasure never touches a document in a final state, and INV-504 holds.
    - **Lower layers, through their contracts:** `master_data` (partner and contact fields), `agent_runs` (run logs), `audit` (`audit_change`, ADR-0038 rule 4), `attachments` (links, except those to posted accounting documents, ADR-0038 rule 15) and `work` (work item notes).
    - **Other modules** react to `DataSubjectErased`, which carries only IDs. `sales`, `purchasing` and `cash` consumers erase their own personal data outside accounting documents (DS-22, DS-25); `imports`' consumer `imports_data_subject_erasure` blanks the subject's values in staging rows of import batches (DS-21). Data on accounting documents is kept for the legal retention period.
    - **Records.** It writes an audit record and a processing log entry (ADR-0038 rule 9).
26. `personal_data_processing_log` is owned by `audit` (layer 2), because its writers sit in layers 2 to 5: the LLM gateway (DS-32), tax ID lookups, exports (ADR-0044) and erasure.
    - **Writing.** Through `audit.contract.log_personal_data_processing`, in the caller's transaction.
    - **Columns:** `processing_kind` (`llm_send`, `tax_id_lookup`, `export`, `erasure`), `subject_table` and `subject_id` (none for a whole-company export), `field_names`, `recipient` (provider and model, or lookup provider), `agent_run_id`, `audit_record_id`.
    - **Append-only.** It holds IDs and field names, never values, so erasure keeps it. A trigger refuses every update and delete.

**Outgoing messages**

27. `outbound_message` is a non-posting document type of `crm` (ADR-0009). Drafts therefore get versions, taint, approval and agent-draft keys (ADR-0029 rule 8; ADR-0030 rule 11).
    - **States.** `draft → (pending_approval →) approved → sending → closed`, and `canceled` (ADR-0009 rule 6, plus `sending`). `sending` is not final, like `issuing` in [ADR-0028](0028-document-lifecycle-hardening.md) rule 6: header and recipients are immutable in it, as in a final state (ADR-0009 rule 14), because the content has gone to the mail server. `closed` is reached only by the delivery outcome `sent` (rule 28). The type registers no `Close` command (`CloseOutboundMessage` does not exist), an exception to ADR-0009 rule 2's generated verbs.
    - **Header:** sending mailbox (`mailbox_id`), partner, `message_type` (`reply`, `document`, `payment_reminder`, `follow_up`, `marketing`, `general`), `content_hash`, `in_reply_to_interaction_id`, `message_id` (made at `Create` as `<UUIDv7@mailbox domain>` and kept on every attempt; it names no person), `message_id_hash`. Delivery facts are not on the header (rule 28).
    - **Content.** The `subject` and `body_text` live in `outbound_message_content`, keyed by (`company_id`, `outbound_message_id`, `content_hash`), with `erased_at`. Each row has a random `content_salt` (128 bits, hex); `content_hash` is the SHA-256 over the message's ID, the salt and the canonical JSON of subject and body, so a blanked row's hash cannot confirm a guessed text. `Create` and `Update` write a new row when the text changes. The version's canonical content holds the hash, never the text.
    - **Recipients** are rows of `outbound_message_recipient` (contact, `role`: `to`, `cc`, `bcc`). They are only contacts of the message's partner, held by a composite key to `contact`, never addresses taken from an inbound message (ADR-0019 rule 17). They hold no address; the addresses used are copied at send into the delivery recipients (rule 28).
    - **The outbound check.** `crm` owns `GetOutboundContentCheck` ([ADR-0050](0050-agent-runtime-and-query-layer.md) rule 36). `CreateOutboundMessage` and `UpdateOutboundMessage` call it directly, as `crm`'s own customer-facing drafts, so a finding is the check result `outbound_content_flagged` in their plan.
    - **Attachments** are linked, such as a quotation PDF from DS-27's print worker.
    - **Commands:** the generated `Create`, `Update`, `Delete`, `Submit`, `Approve`, `Reject` and `Cancel`; `SendOutboundMessage`; `RecordOutboundMessageOutcome`.
    - **No Reopen.** ADR-0009 rule 4 already lets `Update` take an `approved` document back to `draft` with a new version, voiding the approval, so there is no `ReopenOutboundMessage`. `Update` is refused in `sending`, where an attempt is in flight, in `closed` and `canceled` (`invalid_state_transition`), and while the latest attempt is `unknown` (rule 28).
28. `SendOutboundMessage` (effect class `outbound_send`) runs only on an `approved` message. `Submit` brings a draft there, and the policy decides whether someone must approve it first (ADR-0029 rule 6; ADR-0043); a client may send `Submit` and `Send` as one batch. Agents never submit or send (ADR-0050 rule 30). Send adds no policy point. Its checks run in this order, and any failure refuses the whole send:
    1. **Delivery:** the mailbox has `is_sending_enabled` (`mailbox_not_sending`); the message has at least one `to` recipient, and each recipient contact is active and has an address (`recipient_address_missing`) and belongs to the message's partner (`recipient_not_partner_contact`).
    2. **Consent:** for each recipient, take the purpose of the message type. If it needs consent, a current consent basis must exist for the contact (or for its partner when that is an individual or a sole proprietorship), with no pending proposal to close it. A type with no purpose counts as needing consent. Else `consent_missing`, naming the recipients (ADR-0019 rule 9).
    3. **Scope** (ADR-0029 rule 14): every linked document, and the source document of every attached print, has the message's partner (`document.partner_id`). Attached prints come from a customer print contract without `cost` or `margin` field classes (DS-27). No number of another partner's document appears as a whole token in the subject or body. Else `outbound_content_out_of_scope`.
    4. **Actor:** a person may send any type. A `system` actor may send only types in the company setting `crm.automatic_send_types` (default empty), and only a version that is not effectively tainted and was written without an origin agent run. Else `automatic_send_not_allowed`.

    Then, in one transaction, the message moves to `sending`, a new `outbound_message_delivery` attempt is inserted (`attempt_number`, `requested_at`, no outcome yet), the recipient addresses are copied into `outbound_message_delivery_recipient` (`outbound_message_delivery_id`, contact, role, `email_address`, `erased_at`), and `OutboundMessageSendRequested` is emitted.
    - **Delivery attempts.** `outbound_message_delivery` is the late data of ADR-0009 rule 14: its own table that refers to the document. Each row is one attempt; its outcome columns (`outcome`: `sent`, `failed`, `unknown`; `outcome_at`, `sent_at`, `sent_content_hash`, `interaction_id`, `failure_reason`) are set once, and only erasure blanks `failure_reason` (rule 7). The latest attempt is the one with the highest `attempt_number`. The database holds at most one attempt without an outcome and at most one `sent` attempt per message.
    - **The sender.** The external consumer `crm_mail_sender` (ADR-0013 rule 10) sends through the mailbox connector and records the result with `RecordOutboundMessageOutcome`:
      - **Sent:** the attempt gets `sent_at`, the `sent_content_hash` of the submitted MIME (rule 13 uses it to recognize own messages) and an outbound e-mail interaction with the message's participants and content; the message moves to `closed`. That interaction is untrusted when the sent version was tainted, so later reads of it still taint.
      - **Failed** (a permanent refusal): the attempt gets `failure_reason`; the message returns to `approved` and the work item `outbound_message_failed` is raised. A person sends again, changes it with `Update` (back to draft), or cancels it.
      - **Unknown** (no answer, such as a timeout): the attempt records `unknown`, the message returns to `approved`, and the same work item is raised. While the latest attempt is `unknown`, `UpdateOutboundMessage` is refused with `invalid_state_transition`: a changed text under the same `Message-ID` could be recorded as sent when the earlier text is what left. A person sends again or cancels.
      - **Searching first.** Command handlers make no network calls (ADR-0022 rule 6), so the search is the consumer's: when the previous attempt of the message is `unknown`, `crm_mail_sender` searches the mailbox's sent folder for the `Message-ID` before it submits, where the connector can. When it finds the message, it records `sent` for the new attempt without submitting again; when the connector cannot search, it records `unknown` again rather than resend. It never resends blindly.
    - **Payment reminders.** `crm`'s consumer of `RunDunning`'s completion event (ADR-0048 rule 17) drafts one `payment_reminder` message per customer, owned by the human the run acted for. Recipients are the partner's active contacts with `is_accounts_contact` and an address (DS-20's flag, added by this ADR). DS-20 has no partner-level e-mail address, so when no contact is flagged the draft has no recipient and its note says so; a person adds one before sending. A person sends it. `cash` never imports `crm`.

    Note: for a generated file, check 3 reads the attachment's own columns through `attachments.contract`, never `reporting`: it passes the file only when `generated_kind` is `print`, `generated_audience` is `external`, and the partner of `generated_subject_document_id` is the message's partner; otherwise `outbound_content_out_of_scope` ([ADR-0049](0049-statutory-reporting-and-printing.md) rules 28, 29).

**Personal data and untrusted content**

29. Data labels (ADR-0019 rule 7; spec 17) and the `is_untrusted` attribute (ADR-0029 rule 10) per field:

    | Fields | Label | Untrusted |
    | --- | --- | --- |
    | `interaction.subject`, `interaction_content.body_text` | personal | when the interaction `is_untrusted` |
    | `interaction_participant.email_address`, `display_name` | personal | for participants of an untrusted interaction |
    | `inbound_message.message_id`, `sender_address`, `sender_display_name`, `sender_domain`, `sender_authentication`, `parse_notes` | personal | always |
    | `complaint.title`, `resolution_note` | personal | `title` when `is_title_untrusted` |
    | `outbound_message_content.subject`, `body_text`; `outbound_message_delivery_recipient.email_address`; `outbound_message_delivery.failure_reason` | personal | no; taint lives on the version |
    | `data_subject_request_content` requester fields, `outcome_note` | personal | requester fields when taken from a message |
    | `interaction_summary.summary_text` | personal | when the summary `is_untrusted` |
    | `partner_email_domain.domain`, `partner_search_key` columns, `partner_tax_lookup.tax_id` and `result` | by the partner's kind, as ADR-0019 rule 7 | `result` always |
    | `partner_insight.value` | by the partner's kind | no |
    | `mailbox` columns, processing purposes and bases, the processing log, hashes (including `identity_proof_hash`) | internal | no |

    Event payloads carry IDs, states and codes only, never these fields (ADR-0013 rule 4).
30. Retention:
    - **Interactions and messages** are kept until erased. Whether they must be deleted after a time when no request comes is a package rule for the author (open question). The setting `crm.interaction_retention_days` is reserved and empty.
    - **Attachments** follow ADR-0038 rule 15. A file from an e-mail that is later linked to a posted document becomes accounting evidence.

**What the system learned**

31. Summaries, insights and lookups (ADR-0019 rules 18, 20; spec 03 rule 9):
    - **`interaction_summary`:** partner, interaction, `summary_text`, `agent_run_id`, `model`, `prompt_version`, `is_untrusted`, `edited_by_user_id`, `erased_at`. An agent's summary is a change proposal (`CreateInteractionSummary` is `is_proposal_bound`, rule 32); a person submits and approves it.
    - **`partner_insight`:** partner, `name`, `value`, `method`, `computed_date`, `edited_by_user_id`. The nightly job `RunPartnerInsightComputation` computes the insights deterministically from interactions and from `documents.contract.list_partner_documents`, such as the average days between orders and the last order date, and emits `PartnerInsightComputationCompleted`.
    - **Editing.** ADR-0019 rule 20 lets a person edit or remove what the system learned. `UpdatePartnerInsight` sets `edited_by_user_id`, and the job never overwrites an edited value until a person deletes it with `DeletePartnerInsight`; then the job computes it again.
    - **`partner_tax_lookup`:** `tax_id`, `provider`, `looked_up_at`, `result`, `erased_at`; the dated snapshot of ADR-0019 rule 18, written by `RecordPartnerTaxLookup`.

**Commands, events and catalogs**

32. Commands and queries of `crm`, with effect class and flags (ADR-0008 rule 1; ADR-0027 rule 17; ADR-0029 rule 2; [ADR-0050](0050-agent-runtime-and-query-layer.md) rule 26). `is_draft_only` is true only for the commands that create or update drafts of `outbound_message` and `data_subject_request`; they are the only `crm` commands a tainted run may send. Every other agent change in `crm` is a change proposal (`CreateChangeProposal`, ADR-0029 rule 1):

    | Commands | Effect class | Flags | `is_draft_only` |
    | --- | --- | --- | --- |
    | `CreateMailbox`, `UpdateMailbox` | `other` | `human_only` | no |
    | `VerifyMailboxAuthentication`, `RecordMailboxAuthenticationCheck` | `other` | the second only for `crm_mailbox_probe` | no |
    | `RunMailboxIntake`, `RecordInboundMessage`, `RecordMailboxIntakeOutcome` | `other` | the last two only for the intake job | no |
    | `CreateInteraction`, `MatchInteraction` | `other` | `is_proposal_bound` | no |
    | `CreateInteractionLink`, `DeleteInteractionLink` | `other` | — | no |
    | `UnmatchInteraction` | `other` | `human_only` | no |
    | `CreatePartnerEmailDomain`, `UpdatePartnerEmailDomain`, `CreateProcessingPurpose`, `UpdateProcessingPurpose` | `master_data_change` | — | no |
    | `CreateComplaint`, `UpdateComplaint`, `CloseComplaint`, `ReopenComplaint`, `CreateProcessingBasis`, `CloseProcessingBasis` | `other` | `is_proposal_bound` | no |
    | `CreateOutboundMessage`, `UpdateOutboundMessage` | `other` | — | yes |
    | `DeleteOutboundMessage`, `SubmitOutboundMessage`, `ApproveOutboundMessage`, `RejectOutboundMessage`, `CancelOutboundMessage` | `other` | no `CloseOutboundMessage` or `ReopenOutboundMessage` exists | no |
    | `RecordOutboundMessageOutcome` | `other` | only for `crm_mail_sender` | no |
    | `SendOutboundMessage` | `outbound_send` | rule 28 | no |
    | `CreateDataSubjectRequest`, `UpdateDataSubjectRequest` | `other` | — | yes |
    | `DeleteDataSubjectRequest`, `SubmitDataSubjectRequest`, `ApproveDataSubjectRequest`, `RejectDataSubjectRequest`, `CancelDataSubjectRequest`, `CloseDataSubjectRequest` | `other` | — | no |
    | `EraseDataSubject` | `other` | `human_only` | no |
    | `CreateInteractionSummary`, `UpdateInteractionSummary` | `other` | `is_proposal_bound` | no |
    | `DeleteInteractionSummary`, `UpdatePartnerInsight`, `DeletePartnerInsight` | `other` | `human_only` | no |
    | `RunPartnerDuplicateScan`, `RunPartnerInsightComputation`, `RecordPartnerTaxLookup` | `other` | — | no |

    Queries: `ListPartnerTimeline`, `ListInteraction`, `GetInteraction`, `ListInboundMessage`, `ListComplaint`, `GetComplaint`, `ListProcessingBasis`, `ListPartnerDuplicateCandidate`, `ListMailbox`, `GetOutboundContentCheck`.
33. Events and consumers:
    - **Events** (none carries a personal field): `MailboxCreated`, `MailboxUpdated`, `MailboxAuthenticationCheckRecorded`, `MailboxIntakeCompleted`, `MailboxIntakeOutcomeRecorded`, `InboundMessageRecorded`, `InteractionCreated`, `InteractionMatched`, `InteractionUnmatched`, `PartnerEmailDomainCreated`, `PartnerEmailDomainUpdated`, `ComplaintCreated`, `ComplaintUpdated`, `ComplaintClosed`, `ComplaintReopened`, `ProcessingBasisCreated`, `ProcessingBasisClosed`, `OutboundMessageSendRequested`, `OutboundMessageOutcomeRecorded`, `DataSubjectErased`, `PartnerDuplicateScanCompleted`, `PartnerInsightComputationCompleted`, and the generated document events of `outbound_message` and `data_subject_request` (ADR-0009 rule 22).
    - **`crm` consumers:** `crm_partner_search` (partner and contact events; rule 17), `crm_mailbox_probe` (external; rule 11), `crm_mail_sender` (external; rule 28), `crm_payment_reminder_drafts` (`RunDunning`'s completion event; rule 28).
    - **Consumers elsewhere:** `cash`'s complaint consumer (rule 21); the erasure consumers of `sales`, `purchasing`, `cash` and `imports` (rule 25).
    - **Lock order.** Commands of `crm` take no lock class beyond their own rows and `event_subject` (ADR-0027 rule 10). Concurrent edits of a complaint or a match fail with `version_conflict` or `concurrent_update`.
34. Catalog rows:
    - **DS-04 errors:** `public_mail_domain`, `interaction_in_future`, `interaction_already_matched`, `link_partner_mismatch`, `recipient_not_partner_contact`, `recipient_address_missing`, `mailbox_not_sending`, `automatic_send_not_allowed`, `data_subject_kind_invalid`, `consent_evidence_missing`. **Check results:** `interaction_unmatched`, `email_domain_shared`. `automatic_send_not_allowed` also writes denial records (ADR-0038 rule 5). Reads outside a tainted run's scope use ADR-0050's `tainted_read_out_of_scope`, which DS-04 and ADR-0038 rule 5 already list.
    - **Work item kinds:** `complaint_open`, `follow_up_due`, `outbound_message_failed`, `mailbox_unreachable`, `data_subject_request_received`; ADR-0051's `inbound_message` is renamed `inbound_message_matched` (rule 15). New owner rules (ADR-0042 rule 7): `subject_assignee` (the user the subject names as assignee, such as a task's) and `subject_owner` (the user the subject names as owner, such as a mailbox's `owner_user_id`).
    - **Invariants:** CRM invariants use INV-500 to INV-599, area `crm` (a note on DS-16). INV-500 (automatic matches only for authenticated senders), INV-501 (the open-complaint flag equals open complaints), INV-502 (sent attempts had consent), INV-503 (one work item per follow-up task), INV-504 (erased rows are blank), INV-505 (a message is closed exactly when an attempt was sent). INV-49, area `documents`, the last free code of the documents group 40–49 (DS-16): the shared document row's partner and date equal the header's.
    - **Edge cases** EC-84 to EC-91, EC-99 and EC-100; EC-92 to EC-98 are reserved for ADR-0049, which applies after this ADR. The business event types `email_received`, `interaction_recorded`, `complaint_raised`, `complaint_resolved`, `consent_given`, `consent_withdrawn`, `data_subject_erasure_requested` and `message_sent`, first executable at step 5 (DS-17). DS-17 keeps one business event per fact:
      - **`email_received`** is the one event for "a message arrives in a mailbox and intake records it" (this ADR). E-mails that DS-17 already names by their business meaning are that same fact and are not also emitted as `email_received`: `quotation_requested` and `customer_inquiry_received` (ADR-0051 rules 11, 14) and `bank_account_change_requested` (ADR-0029 rule 4).
      - **The others are people's acts:** `interaction_recorded` (a call, meeting, chat, note or task a person enters; never an e-mail), `complaint_raised` and `complaint_resolved` (rules 20–21), `consent_given` and `consent_withdrawn` (a person records or ends a basis with its evidence, rule 23), `data_subject_erasure_requested` (a person records a deletion request and erases, rule 25) and `message_sent` (a person sends an outbound message, rule 28). When the act follows an e-mail, it refers to that e-mail's event.
      - **EC-87 and EC-80** are both `customer_inquiry_received`: EC-80 (ADR-0051) is the onboarding proposal for a sender whose tax ID an existing partner holds, rejected; EC-87 (this ADR) is the clean path with no duplicate, approved and then matched by a person, plus an unauthenticated unknown sender that wakes no agent.

**Lab**

35. Lab check `t11_crm.py` ([validation lab](../reviews/2026-11-14-design-validation/README.md)) loads DS-20, DS-35 and DS-06 together. It checks:
    - the natural key of inbound messages: the provider key, the canonical row per hashes, copies that must share hashes and interaction and point to a canonical row, reused `Message-ID`s and own messages;
    - composite company keys, contacts held inside their partner, lowercase contact e-mail, and recipients only from the message's partner;
    - interaction kinds, directions, matches, tasks, the untrusted inbound e-mail, links only between rows of the same partner, and unmatching refused while a link exists;
    - the append-only trigger, with and without the erasure setting, on interactions, inbound messages, content and delivery tables, and the processing log's own trigger;
    - a model of ADR-0009 rule 14's final-state trigger on the `outbound_message` and `data_subject_request` headers, their recipients and `document_version`: no change in `sending` or a final state, and erasure of a closed message's content row without touching header or version;
    - delivery attempts: one open attempt, one sent attempt, outcomes set once;
    - content rows: a random salt in every row, blanked by erasure; deletes only inside the `Delete` of a draft, never of a submitted message or under another document's setting;
    - complaint states, consent evidence, one current basis, closing once, `company_id` and `recorded_at` coverage, the DDL loading top to bottom, and no personal text column on the two document headers;
    - as pure functions: the RFC 8601 parser and sender authentication (quoted strings, comments, single `From`, DMARC errors failing closed), own-message recognition, the matching cascade with its candidate order on shuffled inputs, and name normalization with the core fold table and trigram search.

    Not covered: commands, consumers, the connector and its probe, the timeline query and erasure across modules.

## Context

ADR-0019 decided most of the CRM's shape and left DS-35 the details: the e-mail domain table that ADR-0045 deferred, the intake mechanics, the timeline's sources, complaints for dunning (ADR-0048 rule 17), the consent records' table, the processing log's owner, and outgoing messages. Spec 13 puts intake, enrichment, quotation drafting, follow-up and after-sales work in Phase 1, and leads and pipelines after it. Spec 14 wants e-mail attached to a partner by address and domain before any LLM. Spec 03 makes untrusted content a hard floor.

ADR-0050 and ADR-0051 came first and fixed how agents run: taint from the subject row, a literal read scope, `is_draft_only` commands for tainted runs, people who submit, and the onboarding and quotation workflows with their work item kinds. This ADR aligns `crm` to them.

The reference systems:
- **SAP:** business partners with roles, and the interaction center's activities and complaints as transactions with status.
- **Dynamics 365:** activities on a timeline, cases for complaints, server-side mailbox synchronization.
- **Odoo:** a chatter per record and mail aliases that create records from e-mail.

ERPMe takes the timeline and the case-like complaint, but keeps e-mail matching deterministic and authenticated, and lets agents only draft and propose.

Layering decided the timeline. A layer-4 `crm` cannot import `sales` or `cash` (ADR-0048 already moved `cash` off such imports), and copying documents into interactions is what ADR-0019 rule 13 forbids. The tainted read scope of spec 03 rule 1 also needs to know, for any document, which partner it belongs to. One nullable `partner_id` on the shared document row serves both.

Immutability decided the outbound message's shape. ADR-0009 rule 14 freezes a document in a final state, while ADR-0019 rule 10 requires erasure of message text. Keeping the text in a content table referenced by hash, and the delivery facts in late-data rows, satisfies both without an exception to either rule. The `sending` state follows ADR-0028's `issuing`: the content has left, the outcome is not known yet, and only an outcome moves the document on.

## Options considered

| Option | For | Against |
| --- | --- | --- |
| Partner and date on the shared document row; `crm` composes through `documents` (chosen) | One query in `crm`; no layer-4 imports; the tainted read scope gets a generic partner too | A new registry attribute and two columns kept equal to the header |
| Timeline in the layer-5 query module over each module's tables | No change to `documents` | The query layer would know every module's tables; `crm` could not check links |
| `crm` imports the contracts of `sales`, `purchasing` and `cash` | Simple calls | Layer-4 coupling that ADR-0048 removed for the same reason |
| Copy documents into a timeline table by events | Fast reads | Two copies that drift (ADR-0019 rule 13) |
| DMARC pass, or strictly aligned DKIM without a DMARC policy, from a probed server field (chosen) | A sender of a matched e-mail is the domain's owner; forged fields are excluded | Domains with neither need a person to match; a mailbox needs a passing probe |
| SPF pass also counts | More automatic matches | SPF breaks on forwarding and proves only the envelope sender, not the `From` a person sees |
| Tainted runs create only drafts; interactions, tasks and summaries are proposals (chosen, flagged) | The literal spec 03 rule 1; one safety path | More approvals for low-risk records (open question) |
| Tainted runs write interactions, tasks and summaries directly | Less work for people | Outside content would write records other runs then read as fact |
| Agents propose partners, matches, complaints and consent (chosen) | One safety path for everything that changes other modules' behavior | More approvals |
| Complaint as its own record (chosen) | Small; clear events for `cash` | A generic case model comes later |
| Complaint as a document type | Versions and approval | No use for numbering or approval; heavier |
| Outbound message as a document type with `sending`, content rows and delivery attempts (chosen) | Taint on versions, approval, agent-draft keys; final states stay immutable and erasable | Four tables per message |
| Close the message at send and write delivery on the header | Fewer tables | Breaks ADR-0009 rule 14: a closed header would change |
| Blank personal text on headers and versions under an erasure exception | One table | Weakens the immutability every other document relies on |
| Leads in Phase 1 | Matches CRM habits | Spec 09 and 13 put them after Phase 1; the onboarding proposal serves meanwhile |

## Constraints that come with the decision

- **ADR notes:**
  - ADR-0019 rules 8–15, 17, 19, 21: contact normalization and the accounts flag, purposes and evidence, erasure scope, the log's owner, kinds and source fields, timeline sources, intake, matching and the renamed kind, outbound messages, duplicates, follow-ups;
  - ADR-0009 rules 1, 2, 6 and 14: `partner_id`, `document_date`, the composite key, `partner_field` and `is_on_partner_timeline`; no generated `Close` for `outbound_message`; the state `sending`; `sending` and the content and delivery tables;
  - ADR-0028 rule 6: `sending` follows `issuing`;
  - ADR-0016 rule 5: `data_protection` in the personal data rules component;
  - ADR-0022 rule 2: the partner e-mail domain hook;
  - ADR-0042 rule 7: the owner rules `subject_assignee` and `subject_owner`;
  - ADR-0048 rule 17: event names, the re-read through `ListComplaint`, reminder drafts made by `crm`;
  - ADR-0045 rule 1: the deferred table, the contact keys, checks and indexes;
  - ADR-0029 rules 5 and 14: the CRM proposals; the outbound checks and `tainted_read_out_of_scope`;
  - ADR-0030 rule 10: hashes, canonical rows and own messages;
  - ADR-0027 rule 14: one batch per message;
  - ADR-0038 rules 5 and 9: the new denial code; the processing log in `audit`;
  - ADR-0039 rule 10: the `data_protection` component;
  - ADR-0050 rule 15 and ADR-0051 rule 14: the kind `inbound_message_matched`.
- **DDL:** [DS-35-crm.sql](../design/DS-35-crm.sql) (new); [DS-20-master-data.sql](../design/DS-20-master-data.sql): the contact keys, checks, indexes and accounts flag.
- **DS-04:** the errors and check results of rule 34.
- **Catalogs:** the work item kinds, invariants and edge cases of rule 34.
- **Other design items:**
  - DS-14 and the packages: the `data_protection` rules, public mail domains, name stop words and fold pairs, and the phone rule;
  - DS-15: permissions of the new commands and queries, and the role templates that include them (`sales` for interactions and complaints);
  - DS-17: the CRM business events and generated `.eml` files with authentication headers;
  - DS-20: `email_domains` on `CreatePartner` through the hook; the contact flag and checks;
  - DS-21: partner e-mail domains and contacts in the import format; the erasure consumer on staging rows;
  - DS-22 and DS-25: `partner_field` on their document types; erasure consumers; DS-25's `RunDunning` completion event carries per customer the reminder level and open item IDs;
  - DS-27: the customer print contract without cost and margin fields;
  - DS-30: the timeline, unmatched-message and complaint screens;
  - DS-32: logging LLM sends through `audit.contract`;
  - DS-33: views over the timeline;
  - DS-34: the intake and follow-up workflows on the work items of this ADR; tax ID lookup calls recorded by `RecordPartnerTaxLookup`;
  - DS-36 and DS-37: the full erasure trigger check of ADR-0038 rule 4, and the final-state trigger of ADR-0009 rule 14 on the two `crm` document types; the secret store behind `credential_ref`.
- **Open questions:** listed in [open-questions.md](../open-questions.md) under DS-35.

## Revisit when

- Leads, opportunities or a pipeline enter scope.
- A pilot needs another mail provider, or the share of unauthenticated e-mail from real partners is too high for people to match by hand.
- The author lets tainted runs write interactions directly, or activities enter scope.
- Chat channels or call recording are added.
- Copies of employees' own sent mail should become outbound interactions.

## Documents updated

- **Design files:** [docs/design/DS-35-crm.sql](../design/DS-35-crm.sql) (new); [docs/design/DS-20-master-data.sql](../design/DS-20-master-data.sql); [docs/design/DS-04-command-envelope.md](../design/DS-04-command-envelope.md); [docs/design/DS-16-invariants-and-harness.md](../design/DS-16-invariants-and-harness.md); [docs/design/DS-17-synthetic-dataset.md](../design/DS-17-synthetic-dataset.md); [docs/design/backlog.md](../design/backlog.md).
- **The lab:** [docs/reviews/2026-11-14-design-validation/](../reviews/2026-11-14-design-validation/README.md): `lab/t11_crm.py` and its finding.
- **ADRs:** notes in ADR-0009, ADR-0016, ADR-0019, ADR-0022, ADR-0027, ADR-0028, ADR-0029, ADR-0030, ADR-0038, ADR-0039, ADR-0042, ADR-0045, ADR-0048, ADR-0050 and ADR-0051.
- **Catalogs:** [work-item-kinds.csv](../catalogs/work-item-kinds.csv), [invariants.csv](../catalogs/invariants.csv), [edge-cases.csv](../catalogs/edge-cases.csv).
- **Glossary:** [docs/spec/00-reading-guide.md](../spec/00-reading-guide.md): rows for inbound message, sender authentication, partner e-mail domain, links, match candidates, follow-up tasks, complaints, processing purposes, outbound messages and delivery attempts, the timeline and search keys; the verb `Send`; wider intents of Match, Close and Reopen.
- **Open questions:** [docs/open-questions.md](../open-questions.md).
- **Index and log:** [docs/adr/README.md](README.md); [docs/runbook/step-log.md](../runbook/step-log.md) at acceptance.
