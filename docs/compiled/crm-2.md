Module: crm    Chunk: 2 of 3    Source ADRs: ADR-0052
Build step(s): 5    Generated from index: 30d5706    Compiled by: Claude Fable 5.2, 2026-11-21

# Compiled spec: `crm`, chunk 2: content and links, mailboxes and intake, matching, duplicates, timeline, follow-ups, complaints, data protection records

## Purpose

`crm` owns interactions with partners, mailboxes and the e-mail intake, matching, the partner duplicate search, the partner timeline, follow-up tasks, complaints and the data protection records (layer 4). This chunk states ADR-0052 rules 8 to 24: interaction content, participants and links, the interaction commands, `mailbox` and its authentication probe, the intake run, `inbound_message`, sender authentication, matching, the unknown-sender flow, the duplicate search, `ListPartnerTimeline`, follow-ups, `complaint` and its events, `processing_purpose`, `processing_basis` and data subject requests. The interaction itself, partner e-mail domains and the rules of ADR-0019 are in chunk 1; outbound messages, sending, erasure, summaries and insights are in chunk 3. `crm` never classifies message content, never merges partners, and imports no other layer-4 module.

## Entities and tables

DDL: `docs/design/DS-35-crm.sql`.

| Table | Meaning | Key | Parent | Owner |
| --- | --- | --- | --- | --- |
| `interaction_content` | Plain-text body of one interaction (R201) | `id`; `interaction_id` unique | `interaction` | `crm` |
| `interaction_participant` | One sender, recipient or attendee of an interaction (R202) | `id` | `interaction` | `crm` |
| `interaction_link` | Link from a matched interaction to one document or one complaint (R204) | `id`; (`interaction_id`, `document_id`, `complaint_id`) unique | `interaction` | `crm` |
| `complaint_document` | Link from a complaint to a document (R204) | `id`; (`complaint_id`, `document_id`) unique | `complaint` | `crm` |
| `mailbox` | One company mailbox with its connector, probe state and intake state (R210) | `id`; (`company_id`, `code`) unique; (`company_id`, `email_address`) unique | `company` | `crm` |
| `inbound_message` | One fetched e-mail with its natural key, hashes and sender authentication (R220-R223) | `id`; (`company_id`, `mailbox_id`, `provider_message_key`) unique | `mailbox`, `interaction` | `crm` |
| `interaction_match_candidate` | Evidence row naming a partner an unmatched interaction may belong to (R231) | `id`; (`interaction_id`, `partner_id`) unique; (`interaction_id`, `rank`) unique | `interaction` | `crm` |
| `partner_search_key` | Normalized name and tax ID of a partner for the duplicate search (R238) | `id`; `partner_id` unique | `partner` | `crm` |
| `complaint` | A partner's complaint with category and state (R249) | `id`; (`company_id`, `id`, `partner_id`) unique | `company`, `partner` | `crm` |
| `processing_purpose` | A purpose of processing personal data, company data seeded from the package (R254) | `id`; (`company_id`, `code`) unique | `company` | `crm` |
| `processing_basis` | The lawful basis for one data subject and purpose (R256) | `id` | `processing_purpose` | `crm` |
| `data_subject_request` | Typed header of the non-posting document type `data_subject_request` (R259) | `id`, which is the `document` ID | `document` | `crm` |
| `data_subject_request_content` | Personal text of a data subject request (R260) | `id`; (`company_id`, `data_subject_request_id`, `content_hash`) unique | `document` | `crm` |

Named by rules of this chunk, with their rows in other chunks: `interaction`, `partner_email_domain`, `public_mail_domain` (chunk 1); `outbound_message` (chunk 3).

Reads: `document` (`documents`); `partner`, `contact`, `user_account`, `role`, `company` (`master_data`, `permissions`); `work_item`, `work_case` (`work`); `partner_collection` (`cash`, which writes `has_open_complaint` itself).

## Commands and queries

Authorization areas of this chunk (catalog `authorization-areas.csv`, under the area `crm`): the functions `interaction` (interactions, participants, links, matching, inbound messages and the partner timeline), `complaint` (Close and Reopen need `post`), `mailbox` (mailboxes, the probe and the intake; `RunMailboxIntake` at `full`; the probe's and the intake's Record commands are `is_internal_only`), `data_protection` (processing purposes and bases), `partner_insight` (the duplicate scan, whose job command is `is_internal_only`) and the document type `data_subject_request`. The level of a verb is the catalog's (`Get`, `List`: `read`; `Create`, `Update`, `Delete`, `Submit`, `Match`, `Unmatch`, `Verify`: `edit`; `Close`, `Reopen`, `Run`, `Record`: `post`). The sources name no area for `ListPartnerDuplicateCandidate` and `ListComplaint` beyond these meanings.

| Name | Actor and authorization | Input | Effect | Events | Error codes |
| --- | --- | --- | --- | --- | --- |
| `CreateInteraction` | people directly; `is_proposal_bound` for agents; area `interaction` | kind (never inbound e-mail), participants, content, links; for a task due date and assignee | Records the interaction; a task raises `follow_up_due` (R207, R245) | `InteractionCreated` | not stated |
| `MatchInteraction` | `is_proposal_bound`; area `interaction` | interaction, partner, optional contact | Matches an unmatched interaction (R208) | `InteractionMatched` | `interaction_already_matched`, `link_partner_mismatch` |
| `UnmatchInteraction` | `human_only`; area `interaction` | interaction, reason | Removes the match and recomputes the candidates (R209) | `InteractionUnmatched` | `link_partner_mismatch` |
| `CreateInteractionLink` | effect class `other`; area `interaction` | the interaction and its target, a document or a complaint | Writes `interaction_link` (R204-R206) | not stated | `link_partner_mismatch` |
| `DeleteInteractionLink` | effect class `other`; area `interaction` | not stated | Removes the link (R206) | not stated | not stated |
| `CreateMailbox` | `human_only`; area `mailbox` | the columns of R210 | Creates the mailbox and requests a probe (R211, R212) | not stated | not stated |
| `UpdateMailbox` | `human_only`; area `mailbox` | the columns of R210 | Changes the mailbox; requests a probe when the connector settings or `authserv_id` change (R212, R215) | not stated | `mailbox_owner_not_permitted` |
| `VerifyMailboxAuthentication` | a person; area `mailbox` | not stated | Repeats the probe (R214) | not stated | not stated |
| `RecordMailboxAuthenticationCheck` | consumer `crm_mailbox_probe`; `is_internal_only`; area `mailbox` | the probe result | Writes `authentication_probe_result` (R213, R214) | not stated | not stated |
| `RunMailboxIntake` | area `mailbox`, level `full` | not stated | Starts one intake run now (R217) | `MailboxIntakeCompleted` | not stated |
| `RecordInboundMessage` | intake, actor `system`; `is_internal_only`; area `mailbox` | the message, referring to its attachments | Records the inbound message and its interaction, advances the cursor (R218, R219) | not stated | not stated |
| `RecordMailboxIntakeOutcome` | intake, actor `system`; `is_internal_only`; area `mailbox` | success or failure | Records the outcome and `last_intake_at` (R219) | not stated | not stated |
| `ListPartnerDuplicateCandidate` | query; area not stated | any of tax ID, name, e-mail, domain, phone; optionally a partner to leave out | Returns at most ten candidates (R237-R239) | none | `tainted_read_out_of_scope` |
| `RunPartnerDuplicateScan` | nightly job; `is_internal_only`; area `partner_insight` | not stated | Repeats the search for partners changed since its last run (R240) | `PartnerDuplicateScanCompleted` | not stated |
| `ListPartnerTimeline` | query; area `interaction` | partner, `include_superseded`, `include_untrusted`, keyset cursor | Returns the partner's entries (R242-R244) | none | `tainted_read_out_of_scope` |
| `CreateComplaint` | `is_proposal_bound`; area `complaint` | not stated (the columns of R249, documents) | Opens the complaint and raises `complaint_open` (R250) | `ComplaintCreated` | not stated |
| `UpdateComplaint` | `is_proposal_bound`; area `complaint` | category, title, documents | Changes them (R250) | `ComplaintUpdated` | not stated |
| `CloseComplaint` | `is_proposal_bound`; area `complaint`, level `post` | resolution note | Closes the complaint and resolves `complaint_open` (R250) | `ComplaintClosed` | `invalid_state_transition` |
| `ReopenComplaint` | `is_proposal_bound`; area `complaint`, level `post` | not stated | Opens it again (R250) | `ComplaintReopened` | `invalid_state_transition` |
| `ListComplaint` | query; area not stated | not stated | Lists complaints; read by the `cash` consumer (R253) | none | not stated |
| `CreateProcessingPurpose`, `UpdateProcessingPurpose` | effect class `master_data_change`; area `data_protection` | the columns of R254 | Write `processing_purpose` (R254) | not stated | not stated |
| `CreateProcessingBasis` | `is_proposal_bound`; area `data_protection` | not stated (the columns of R256) | Writes a `processing_basis` row (R256-R258) | not stated | `consent_evidence_missing`, `data_subject_kind_invalid` |
| `CloseProcessingBasis` | `is_proposal_bound`; area `data_protection` | basis, end reason | Sets `ended_at` and `end_reason` once (R257, R258) | not stated | not stated |
| `CreateDataSubjectRequest` | a person; an agent drafts (`is_draft_only`); area `data_subject_request` | not stated (the header and content of R259, R260) | Creates the draft and raises `data_subject_request_received` (R262) | not stated | not stated |
| `UpdateDataSubjectRequest` | area `data_subject_request` | not stated | Changes the draft; the one that sets the verified requester and the data subject resolves `data_subject_request_received` (R262) | not stated | not stated |
| `SubmitDataSubjectRequest` | area `data_subject_request` | not stated | Submits it and raises `data_subject_request_due` (R262) | not stated | not stated |

Contract interfaces, consumers and jobs that are not registered commands: the interface `crm.contract.MailboxConnector` (R211); the external consumer `crm_mailbox_probe` (R212); the job `mailbox_intake` (R217); the consumer `mailbox_document_intake` (R215); the consumer of `PartnerCreated`, `PartnerUpdated`, `ContactCreated` and `ContactUpdated` (R240); the core function of sender authentication (R227). `crm` calls `documents.contract.list_partner_documents` (R242), and `CreateAttachment` of `attachments` in the intake batch (R218). `ResolveWorkItem` and `AssignWorkItem` belong to `work` (R233, R245). Every command that writes a link, or matches or unmatches an interaction with links, returns `link_partner_mismatch` when the partner check fails (R205, R206). The onboarding agent's commands return `tainted_run_not_allowed` and `proposal_required` (R234).

## Rules

### Content, participants, attachments and links

R201. `interaction_content` holds one row per interaction: `body_text`, plain text, and `erased_at`. HTML is converted to text by a sanitizer and never stored as HTML.
Source: ADR-0052.R8

R202. `interaction_participant` holds `role` (`from`, `to`, `cc`, `bcc`, `reply_to`, `attendee`), `email_address`, `display_name`, the `contact_id` or `user_account_id` it resolves to, and `erased_at`. Attendees of calls and meetings are contacts or users.
Source: ADR-0052.R8

R203. Attachments are stored by `attachments` and linked to the interaction (ADR-0027.R2). Those from inbound e-mail are untrusted (ADR-0038.R14). The raw message is an attachment too, kept for evidence and referenced by its inbound message (`raw_attachment_id`).
Source: ADR-0052.R8

R204. Links, never copies (ADR-0019.R13). `interaction_link` points from a matched interaction to one document (`document_id`, any type) or one complaint (`complaint_id`), is unique per target, and carries the interaction's `partner_id`. `complaint_document` links a complaint (`complaint_id`) to documents (`document_id`) the same way, with the complaint's `partner_id`.
Source: ADR-0052.R9

R205. Partner check: a link needs a matched interaction, and a target whose partner is set and equals the interaction's or the complaint's: the document's `partner_id` (R241) or the complaint's partner. Otherwise the command fails with `link_partner_mismatch`. This holds for every actor, so a link never leaks another partner's record into a timeline. The database holds the interaction's and the complaint's side by composite keys on (`company_id`, `id`, `partner_id`); the document's side is the command's check.
Source: ADR-0052.R9

R206. `MatchInteraction` and `UnmatchInteraction` recheck the interaction's links and refuse with `link_partner_mismatch` when a link would conflict with the new partner or with none; the person removes the link first. The composite key refuses the same in the database. `CreateInteractionLink` and `DeleteInteractionLink` have effect class `other`.
Source: ADR-0052.R9

### Interaction commands

R207. `CreateInteraction` serves every kind except inbound e-mail, with participants, content, links, and for a task its due date and assignee. People run it directly. It is registered `is_proposal_bound`, so an agent proposes it in a change proposal that a person submits and approves (ADR-0029.R2, ADR-0029.R3, ADR-0029.R4). It emits `InteractionCreated`.
Source: ADR-0052.R10

R208. `MatchInteraction` (partner, optional contact) runs only on an unmatched interaction, else `interaction_already_matched`. It is registered `is_proposal_bound`. It resolves the interaction's `interaction_unmatched` work item and, for an inbound e-mail whose sender authentication passed, raises `inbound_message_matched` (R230). It emits `InteractionMatched`.
Source: ADR-0052.R10

R209. `UnmatchInteraction` is `human_only`, takes a reason, raises `interaction_unmatched` again, and recomputes the match candidates (R232). It emits `InteractionUnmatched`.
Source: ADR-0052.R10

### Mailbox and the authentication probe

R210. `mailbox` (ADR-0019.R14) has the columns `code`, `name`, `email_address`, `connector_kind` (`imap` in Phase 1), `connector_settings` (host, port, folder, submission server; never a secret), `credential_ref` (a key in the installation's secret store, DS-37; the database never holds the secret), `authserv_id` (R224), `owner_user_id`, `is_intake_enabled`, `is_sending_enabled`, `document_intake_purpose` (`supplier_invoice`, `inquiry_lines`, `shop_floor_report` or empty; the last value by ADR-0064.R27), `document_intake_quarantine_limit`, `intake_cursor`, `last_intake_at`, `consecutive_failure_count`, `is_authentication_verified`, `authentication_probe_result`, `authentication_checked_at`, `is_active`, `version`.
Source: ADR-0052.R11, .N1

R211. `CreateMailbox` and `UpdateMailbox` are `human_only`. The connector is the interface `crm.contract.MailboxConnector`: fetch after a cursor, fetch one message by key, send, and find a sent message by `Message-ID`. The core adapter is IMAP over TLS with SMTP submission; other providers (Microsoft Graph, Gmail API) are later adapters. Mailbox connectors belong to `crm`, not to DS-24, which is the e-invoice add-on.
Source: ADR-0052.R11

R212. Trusted results need a probe. R224 trusts the topmost `Authentication-Results` field with the mailbox's `authserv_id`, which holds only if the receiving server adds its own field and strips forged ones that carry its authserv-id. So `CreateMailbox`, and `UpdateMailbox` when the connector settings or `authserv_id` change, set `is_authentication_verified` false and request a probe. The external consumer `crm_mailbox_probe` (ADR-0013.R10) submits a probe message from the mailbox to itself through the submission server, whether or not `is_sending_enabled` is set, that carries a forged `Authentication-Results` field with the mailbox's authserv-id and a probe token; it fetches the message and records the result with `RecordMailboxAuthenticationCheck` in `authentication_probe_result`.
Source: ADR-0052.R11

R213. The values of `authentication_probe_result`:
- `passed`: the fetched message has exactly one field with that authserv-id, it is the topmost field, and the forged one is gone;
- `probe_no_field`: the message carries no field with that authserv-id at all; servers often add none to locally submitted mail, so this is an expected result, and the mailbox stays on manual matching;
- `forged_field_kept` or `field_not_topmost`: the server does not protect the field;
- `transport_error`: the probe could not complete.
Source: ADR-0052.R11

R214. Only `passed` sets `is_authentication_verified`, and only a completed probe with a negative result (`probe_no_field`, `forged_field_kept`, `field_not_topmost`) clears it; a `transport_error` keeps the last state. The probe proves stripping on the submission path only; that the server treats mail from outside the same way is the administrator's configuration, which the probe cannot see (flagged). A person can repeat the probe with `VerifyMailboxAuthentication`; the consumer also repeats it daily. While `is_authentication_verified` is false, intake marks every message of the mailbox not authenticated, with reason `mailbox_not_verified`, and nothing is matched automatically. Intake skips the probe message by its token.
Source: ADR-0052.R11

R215. Document intake from a mailbox. `UpdateMailbox` refuses a `document_intake_purpose` whose leaf the owner cannot `edit` (`mailbox_owner_not_permitted`). The `crm` consumer `mailbox_document_intake` requests extractions of a message's XML parts first, and of its other parts only after them (or after `crm.document_intake_xml_timeout_minutes`) and only for a message matched to exactly one active partner (R229), never for authentication alone. Past the quarantine cap `document_intake_quarantine_limit`, which counts quarantined records of messages not matched to a partner per receipt date, an XML is extracted but not imported, and `e_invoice_quarantine_overflow` lets the owner import it (ADR-0057.R25).
Source: ADR-0052.R11, .N1

### The intake run

R216. Intake is not an agent run. It is deterministic code that runs as actor `system` on behalf of the mailbox owner (ADR-0027.R14; ADR-0017.R12). It calls no LLM and never classifies content. Spec 03 rule 1 restricts agent runs that read untrusted content; intake is not one, so it may record inbound messages and their interactions directly. Labeling every inbound e-mail untrusted (ADR-0052.R6) is how intake meets that rule.
Source: ADR-0052.R12

R217. The job `mailbox_intake` runs per enabled mailbox every `crm.intake_interval_minutes` (company setting, default 5), on the `integrations` queue. `RunMailboxIntake` starts one now; it emits `MailboxIntakeCompleted`. The run fetches at most `crm.intake_batch_size` messages (default 50) after the cursor, with no transaction open (ADR-0013.R10), and streams each raw message and its parts to the object store.
Source: ADR-0052.R12

R218. One batch per message: the run dispatches one command batch (ADR-0008.R20) with `CreateAttachment` for the raw message and for each part of an allowed type (ADR-0038.R13), then `RecordInboundMessage`, which refers to them. Parts of other types are named in the message's `parse_notes` and stay only inside the raw message. A message above `attachment_max_bytes` is recorded without parts, with a parse note. The intake declares only `CreateAttachment`, `RecordInboundMessage` and `RecordMailboxIntakeOutcome`.
Source: ADR-0052.R12

R219. `RecordInboundMessage` advances the cursor (`intake_cursor`) in its own transaction, so a crash re-fetches only uncommitted messages, which the natural key skips. After each run, `RecordMailboxIntakeOutcome` records success or failure and `last_intake_at`. `crm.intake_failure_limit` consecutive failures (default 3) raise `mailbox_unreachable` for the mailbox's `owner_user_id` (owner rule `subject_owner`); the next success resolves it.
Source: ADR-0052.R12

### `inbound_message` and the natural key

R220. The natural key of `inbound_message` (ADR-0030.R10; ADR-0019.R14): `provider_message_key` is the provider's stable key (IMAP: `UIDVALIDITY` and `UID`), unique per mailbox (`mailbox_id`). A message fetched twice is skipped without a command. `message_id_hash` is the SHA-256 of the normalized `Message-ID`. `content_hash` is the SHA-256 over the `From`, `To`, `Cc`, `Date`, `Subject` and `Message-ID` headers and the MIME body; trace headers that differ per mailbox (`Received`, `Delivered-To`, `Authentication-Results`) are left out. For a message without `Message-ID` only the provider key applies.
Source: ADR-0052.R13

R221. The same message in a second mailbox has the same `message_id_hash` and `content_hash`. Its row points with `duplicate_of_inbound_message_id` to the canonical row, the one that is neither a copy nor an own message, and shares its interaction; no second interaction is made. A unique index on (`company_id`, `message_id_hash`, `content_hash`) over canonical rows holds this. A composite foreign key holds that a copy has the same hashes and the same interaction as its target, and that the target is canonical (the generated columns `is_canonical` and `duplicate_target_canonical`), so a copy never points to a copy.
Source: ADR-0052.R13

R222. A reused `Message-ID` with other content gets its own interaction and the check result `duplicate_suspected` (DS-04). An inbound message whose `Message-ID` is one of the company's sent messages counts as own only when its sender authentication passed and its `From` address equals a company mailbox address, or when its `content_hash` equals the `sent_content_hash` of the sent attempt (ADR-0052.R28). It is then recorded with `is_own_message`, points to the outbound interaction, and creates no interaction. Otherwise it is a reused `Message-ID`: it is processed as any other message, with `duplicate_suspected`.
Source: ADR-0052.R13

R223. The raw `Message-ID`, the sender's address, display name and domain are kept in clear for display. They are personal and untrusted, and erasure blanks them. `In-Reply-To` and `References` are kept only as hashes (`referenced_message_id_hashes`). Matching and deduplication use only hashes and normalized addresses. Other columns: `received_at` (the provider's receive time), `raw_attachment_id`, `parse_notes`, `erased_at`.
Source: ADR-0052.R13

### Sender authentication

R224. Results are read only from `Authentication-Results` header fields (RFC 8601) whose authserv-id equals the mailbox's `authserv_id`, taking the topmost such field: the one the company's receiving server added, which the probe of R212 verified. Headers the sender wrote, or copies from other servers, are ignored. Without such a field, or on a mailbox whose probe has not passed, the message is not authenticated.
Source: ADR-0052.R14

R225. A parser of the RFC 8601 grammar reads the fields: quoted strings, comments and folding whitespace are tokens of the grammar, never text to split on, so `smtp.mailfrom="a; dmarc=pass"@x` is one property value. It fails closed: a field above ours whose authserv-id cannot be read, or our field with any syntax error, makes the message not authenticated, with reason `results_unparsable`. The sender is the single mailbox of the RFC 5322 `From` field. Zero or several `From` addresses, or several `From` fields, mean not authenticated (`from_not_single`). `Sender` and the envelope sender are never used.
Source: ADR-0052.R14

R226. Sender authentication passes in these cases only:
- DMARC `pass`, when the result's `header.from` equals the `From` domain. A DMARC `pass` without `header.from` falls through to the exact DKIM test below; one whose `header.from` names another domain is not authenticated.
- DMARC absent or `none` (no policy published): a DKIM signature that passes and whose `header.d` domain equals the `From` domain exactly.
- DMARC `fail`, `temperror`, `permerror`, any other value, or two different DMARC results: not authenticated. Errors fail closed.
- SPF alone never passes. ARC is not trusted in Phase 1.
Source: ADR-0052.R14

R227. The outcome is stored in `sender_authentication` (the parsed results and the reason) and `is_sender_authenticated`. The rule is one core function, used by intake and by tests.
Source: ADR-0052.R14

### Matching

R228. Matching (ADR-0019.R15, made exact) runs only when the sender authentication passes. Each step runs only if the one before found nothing:
- Reply: a referenced `Message-ID` hash equals that of one of the company's sent outbound messages (ADR-0052.R27), and the sender address is an active contact address of that message's partner or one of its delivery recipients. The match is that partner, with the contact when the address belongs to one contact of it.
- Contact address: active contacts of active partners whose `email` equals the sender address. One partner gives a match. The contact is set when exactly one contact of that partner has the address.
- Domain: active `partner_email_domain` rows equal to the `From` domain, skipped when the domain is in `public_mail_domain` at match time.
Source: ADR-0052.R15

R229. A partner superseded under ADR-0019.R19 is replaced by its successor before counting. Exactly one partner: the interaction is matched with its `match_method`. Otherwise (none, several, or not authenticated) it stays unmatched, with the check result `interaction_unmatched` and the work item `interaction_unmatched`.
Source: ADR-0052.R15

R230. An inbound e-mail whose sender authentication passed and that is matched, at intake or later by `MatchInteraction`, raises the work item `inbound_message_matched`, which the quotation agent declares (ADR-0051.R14). Its owner rule `role:sales` resolves as `role:sales_clerk`, through `role.template_code` (ADR-0054.R11). An unauthenticated message matched by a person raises none, so no agent wakes on it; a person may still start an agent on it (ADR-0051.R14). Where the company sets `work_case.quote_request.mode` to `auto`, the raise of `inbound_message_matched` opens a `quote_request` work case through the consumer `work_case_opener`; likewise `interaction_unmatched` opens a `customer_onboarding` case and `complaint_open` a `customer_issue` case, each under its own mode. `crm` itself is unchanged by this, and the case copies `partner_id` only from the matched interaction (ADR-0066.R3, ADR-0066.R6).
Source: ADR-0052.R15, .N1, .N2

R231. The unmatched case stores at most ten `interaction_match_candidate` rows, one per partner, each with its best `reason`. Reasons, in this order: a step found several partners (`several_partners`); the contact or domain step found a partner while authentication failed (`contact_email_unauthenticated`, `domain_unauthenticated`); a tax ID in the body, found by the package's format rule, equals a partner's normalized tax ID (`tax_id_in_content`); the sender's display name is similar to a partner's name by R238 (`name_similarity`, with its `score`). The order of the rows (`rank` 1 to 10, unique per interaction) is: by reason in that order, then `score` descending, then partner code.
Source: ADR-0052.R15

R232. `UnmatchInteraction` replaces the candidates by a new computation; candidates are evidence, not history. Candidates are evidence for a person, never a match (ADR-0019.R15). Forwarded content, a message inside a message, is never matched.
Source: ADR-0052.R15

### E-mail from an unknown sender

R233. An e-mail from an unknown sender follows ADR-0051.R11 to ADR-0051.R13. It waits in the work item `interaction_unmatched` (R229). A person matches it (`MatchInteraction`), creates the partner and contact (DS-20), or ends it with `ResolveWorkItem` and a reason such as spam. The agent type `customer_onboarding` declares the kind but runs only when the sender authentication passed (ADR-0051.R12, D1). An unknown sender that is not authenticated goes to people, with no agent.
Source: ADR-0052.R16

R234. The onboarding run starts tainted (ADR-0050.R15). It drafts one change proposal (ADR-0029.R1) with a `CreatePartner` item, role `customer`, the sender's domain in its `email_domains` unless the domain is public (ADR-0052.R5), and one `CreateContact` item per contact, the sender first. It never creates a partner, contact or domain itself: such commands are not `is_draft_only` (`tainted_run_not_allowed`, ADR-0050.R26) and need a proposal (`proposal_required`, ADR-0029.R4). It proposes no match. The proposal sets the `customer` role, which the quotation agent needs before it may run for the partner (ADR-0051.R14); the approving person decides, a person may change the proposal before submitting it, and the approver may reject it. The proposal names the interaction and the agent run. It is tainted (ADR-0029.R8), so a person submits it and another person approves it (ADR-0051.R13).
Source: ADR-0052.R16

R235. The proposal screen calls `ListPartnerDuplicateCandidate` (R237) with the proposed tax ID, name, contact address and domain, for the approving person. After the proposal is executed, a person confirms the interaction's match with `MatchInteraction` and resolves the item (ADR-0051.R13), and the `crm` consumer of `PartnerCreated` runs the duplicate search again (R240).
Source: ADR-0052.R16

R236. A tainted run never receives other partners' identities. `ListPartnerDuplicateCandidate` and the timeline refuse it with `tainted_read_out_of_scope` (ADR-0050.R27). Check results in a plan returned to it, such as `partner_duplicate_suspected` of ADR-0019.R4, carry only the code and a count; the full details stay on the proposal for the approver.
Source: ADR-0052.R16

### Duplicate search

R237. The duplicate search (ADR-0019.R19) is deterministic and bounded. The query `ListPartnerDuplicateCandidate` takes any of tax ID, name, e-mail, domain and phone, and optionally a partner to leave out. Its keys: normalized tax ID equal (package rule, ADR-0019.R4); contact e-mail equal; partner e-mail domain equal; contact phone equal (E.164, on DS-20's phone index); name similarity by `pg_trgm` (installed, ADR-0022.R8) at or above `crm.duplicate_name_threshold`. That company setting is the threshold of ADR-0019.R19: a `pg_trgm` similarity of the normalized names, between 0 and 1, default 0.6, flagged for tuning. Once `crm` registers `backtest`, `compare` and `monitor` for `crm.find_partner_duplicates`, a company may opt in to tuning by creating its parameter set, seeded from the setting (ADR-0059.R8).
Source: ADR-0052.R17, .N1, .N2

R238. The normalized name: lowercase; Unicode NFKD with combining marks removed; then the core fold table, a fixed, language-neutral Latin-to-ASCII table: `đ`→`d`, `ð`→`d`, `ł`→`l`, `ø`→`o`, `ß`→`ss`, `æ`→`ae`, `œ`→`oe`, `þ`→`th`, `ı`→`i`, `ħ`→`h`; then punctuation to spaces and spaces collapsed. A package may add fold pairs as package data `partner_name_fold_pairs`, next to `partner_name_stop_words`. Then the package's stop words, such as legal-form words, are removed; the core list is empty. The result is kept in `partner_search_key` (`normalized_name`, `normalized_tax_id`).
Source: ADR-0052.R17

R239. The search returns at most ten results. A partner found under two reasons counts once, with its best reason. Results are ordered by reason (tax ID, e-mail, domain, phone, name), then similarity descending, then partner code. The same data gives the same answer.
Source: ADR-0052.R17

R240. The `crm` consumer of `PartnerCreated`, `PartnerUpdated`, `ContactCreated` and `ContactUpdated` updates the search key, then searches. Any candidate raises the existing kind `partner_duplicate_suspected`, with the candidates as evidence. Nothing is merged automatically. Two partners created at the same moment can each miss the other's key, so the nightly job `RunPartnerDuplicateScan` repeats the search for partners changed since its last run and emits `PartnerDuplicateScanCompleted`.
Source: ADR-0052.R17

### The partner timeline

R241. The shared `document` row of ADR-0009.R1 carries `partner_id` and `document_date` (both nullable) and a unique key on (`company_id`, `id`). A document type declares at registration (ADR-0009.R2) `partner_field`, the header column that names its partner or none, and `is_on_partner_timeline`, true by default when it has a partner field. The owning module passes both values to `documents.contract` at every version, so they always equal the header (`INV-49`). Types whose partners sit on lines, such as general journal entries, declare none and stay off the timeline. `document.partner_id` and `INV-49` are the sold-to partner (the ordered-from partner on purchases); the other parties of ADR-0074.R1 are not CRM links.
Source: ADR-0052.R18, .N2

R242. `ListPartnerTimeline` is a query of `crm`. Its sources are the partner's interactions and complaints of `crm`, and `documents.contract.list_partner_documents` for the partner's documents of every timeline type: quotations, orders, deliveries, invoices, returns, payments and the others DS-22 and DS-25 register. `crm` imports no other layer-4 module (ADR-0022.R2, ADR-0022.R6; the practice of ADR-0048.R17). `outbound_message` and `data_subject_request` declare `is_on_partner_timeline: false`; a sent message appears as its outbound interaction. `include_superseded` (default true) adds the entries of partners superseded by this one.
Source: ADR-0052.R18

R243. A timeline entry holds `entry_kind` (`interaction`, `complaint`, `document`), `entry_date`, `entry_at`, the record ID, kind or document type, direction, state (document state, complaint state, or a task's work item state), number, contact and links. `entry_date` is the company-local date of `occurred_at`, the complaint's opening date, or `document_date`. `entry_at` is `occurred_at`, `opened_at`, or the first version's `recorded_at`. The order is by `entry_date`, `entry_at` and ID, all descending, with a keyset cursor on these values (DS-04 queries). Entries carry no amounts; callers read the document. DS-33 may expose the same rows as a view.
Source: ADR-0052.R18

R244. Subjects and summaries come only with `include_untrusted` (default false). Returning one taints the calling run (ADR-0029.R10). Without it the timeline taints nothing. A document entry appears only when the actor holds that type's `Get<Type>` query, the document is inside their record scope (ADR-0017) and inside their read owner scope (ADR-0054.R15). Others are left out, and `is_scope_filtered` is true. Field classes apply as usual. Tainted runs may ask only for their scope partner (spec 03 rule 1; ADR-0029.R14; ADR-0050.R27); otherwise `tainted_read_out_of_scope`.
Source: ADR-0052.R18, .N1

### Follow-ups

R245. A follow-up is an interaction of kind `task`, with `due_date`, `assignee_user_id` and text, usually linked to a document. `CreateInteraction` raises `follow_up_due` with the interaction as subject, the assignee as owner by the owner rule `subject_assignee`, and due rule `subject_due_date` (ADR-0042.R5, ADR-0042.R7, ADR-0042.R8). The task's state is the work item's state; `crm` stores none (`INV-503`). Done is `ResolveWorkItem`; reassignment is `AssignWorkItem`.
Source: ADR-0052.R19

R246. A new due date or text is a new task with `correction_of_id`. Its command resolves the earlier task's work item with resolution `superseded`.
Source: ADR-0052.R19

R247. Agents propose tasks: `CreateInteraction` is `is_proposal_bound` (R207), so an agent's task is a change proposal that a person submits and approves; a tainted run may create the proposal, which is a draft (ADR-0050.R26). ADR-0013.R11 limits consumers of tainted events and does not grant this. A task executed from a tainted proposal is untrusted. This strict reading holds for Phase 1: spec 03 rule 1 permits an untrusted-content run to write interactions, tasks and summaries, but ADR-0052.R10, ADR-0052.R19 and ADR-0052.R31 keep them proposal-bound, so a person submits them. It is revisited with measured intake volumes.
Source: ADR-0052.R19, .N1

R248. These are the minimal follow-ups of Phase 1. Activities with calendars, recurrence and invitations stay after Phase 1 (ADR-0019.R21). Spec 09 places "activities and appointments" after Phase 1, and tasks with an assignee and a due date resemble activities; tasks stay as the flagged interim (open question).
Source: ADR-0052.R19

### Complaints

R249. `complaint` has the columns partner (required), contact, `origin_interaction_id`, `category` (`delivery`, `quality`, `billing`, `service`, `other`), `title`, `is_title_untrusted`, `state` (`open`, `closed`), `opened_at`, `closed_at`, `resolution_note`, `erased_at`, `version`. Linked documents are in `complaint_document`. A complaint is not a document type: it has no versions, approval or number; its history is in `audit` (ADR-0038).
Source: ADR-0052.R20

R250. `CreateComplaint` opens the complaint and raises `complaint_open` (owner `role:sales`, which resolves as `role:sales_clerk` through `role.template_code`, ADR-0054.R11; due rule `days:2`; resolved by `CloseComplaint`). `UpdateComplaint` changes category, title and documents. `CloseComplaint` takes a resolution note. `ReopenComplaint` opens it again. Other transitions fail with `invalid_state_transition`.
Source: ADR-0052.R20, .N1

R251. `CreateComplaint`, `UpdateComplaint`, `CloseComplaint` and `ReopenComplaint` are `is_proposal_bound`, because their effect reaches the dunning of `cash`; a person decides. A title an agent wrote from untrusted content sets `is_title_untrusted`.
Source: ADR-0052.R20

R252. The complaint events that `cash` consumes (ADR-0048.R17) are `ComplaintCreated`, `ComplaintUpdated`, `ComplaintClosed` and `ComplaintReopened`, with the complaint as subject and its ID, partner ID and state as payload. Under ADR-0004.R22, `CreateComplaint` emits `ComplaintCreated`; there is no `ComplaintOpened`, because the verb Open belongs to posting periods.
Source: ADR-0052.R21

R253. Events of different complaints have no common order (ADR-0013.R3). So on each event the `cash` consumer reads the partner's open complaints through the query `ListComplaint` and sets `has_open_complaint` to whether any exist. Two complaints closed in either order leave the right flag (`INV-501`). `cash` never imports `crm`.
Source: ADR-0052.R21

### Processing purposes and bases

R254. `processing_purpose` is company data seeded from the package (ADR-0016.R6, ADR-0016.R7). Columns: `code`, `name`, `is_consent_required`, `message_types` (the outbound message types the purpose covers; one purpose per type, checked by the command), `basis` (the package basis, as in DS-20), `is_active`. The commands `CreateProcessingPurpose` and `UpdateProcessingPurpose` have effect class `master_data_change`.
Source: ADR-0052.R22

R255. The core template applies when the package has none: `contract_communication` (no consent; types `reply`, `document`, `payment_reminder`, `follow_up`, `general`) and `marketing` (consent; type `marketing`). Their rows carry the basis `{"source": "core_template"}`, set by the command like every package basis, so `basis` is never empty. The purposes a localization package seeds are flagged package content (ADR-0052.R24); those of `l10n_vn` are `unverified` (open question).
Source: ADR-0052.R22

R256. `processing_basis` (ADR-0019.R9; the names of ADR-0027.R12) has the columns: the data subject (exactly one of contact and partner), the purpose (`processing_purpose_id`), `lawful_basis` (`contract`, `legal_obligation`, `consent`; the name `basis` is left to the package bases of DS-20), `started_at` (the recording instant; the evidence shows when it was given), `ended_at`, `end_reason` (`withdrawn`, `purpose_ended`, `erased`), `evidence_interaction_id`.
Source: ADR-0052.R23

R257. Consent needs evidence: the interaction that records it, such as an e-mail or a call note. The database refuses consent without it (`consent_evidence_missing`). Silence is never consent. A partner may be the subject only when it is an individual, a sole proprietorship or an employee partner; else `data_subject_kind_invalid`. There is one current basis per subject, purpose and lawful basis, by a unique index. Rows are append-only except `ended_at` and `end_reason`, set once (ADR-0052.R7).
Source: ADR-0052.R23

R258. `CreateProcessingBasis` and `CloseProcessingBasis` (with the end reason) are `is_proposal_bound`: agents propose them from what a message says. While a proposal to close a basis is pending, sending treats the basis as closed (ADR-0052.R28).
Source: ADR-0052.R23

### Data subject requests and package rules

R259. `data_subject_request` is a non-posting document type of `crm` (ADR-0019.R10). Its header holds `request_kind` (`access`, `correction`, `deletion`), the subject (empty until a person identifies it), `origin_interaction_id`, `due_date`, and `content_hash`.
Source: ADR-0052.R24

R260. The requester's name, e-mail and phone (`requester_name`, `requester_email`, `requester_phone`), the `outcome_note` and the `identity_proof_hash` (the SHA-256 of the evidence a person checked to verify the requester) live in `data_subject_request_content`, a `crm` table keyed by (`company_id`, `data_subject_request_id`, `content_hash`). Each row has a random `content_salt` (128 bits, hex). `content_hash` is the SHA-256 over the request's ID, the salt and the canonical JSON of these fields, so rows are never shared between requests, and once erasure blanks the salt the hash can no longer confirm a guessed value. The header and the version's canonical content (ADR-0009.R9) hold only the hash, so neither contains personal text.
Source: ADR-0052.R24

R261. The package rule gives the due date, flagged. Without a package rule it is the received date plus the company setting `crm.data_subject_request_due_days` (default 30), an operational default and not a legal deadline; `due_date` is never empty.
Source: ADR-0052.R24

R262. `CreateDataSubjectRequest` raises `data_subject_request_received` (owner `company_owner`, due rule `days:1`) with the request as subject, so a person verifies the requester and identifies the data subject; the `UpdateDataSubjectRequest` that sets both resolves it. `SubmitDataSubjectRequest` raises the existing `data_subject_request_due` (due rule `subject_due_date`), resolved when the request closes or is canceled; a draft raises none. A person creates the request after reading a message that asks for access, correction or deletion; an agent may draft one (`is_draft_only`, ADR-0052.R32) for a person. Intake never classifies messages, and nothing opens a request or erases anything by itself. Access and correction are done by people with the existing queries and commands in Phase 1.
Source: ADR-0052.R24

R263. Package rules `data_protection`: purposes with their message types, request deadlines, `public_mail_domains`, `partner_name_stop_words`, `partner_name_fold_pairs` and the phone rule are package rules of the existing component "Default data labels and personal data rules" of ADR-0016.R5, named `data_protection` (the item ADR-0039.R10 assigns to DS-35). The reserved retention setting of ADR-0052.R30 is not registered: retention periods are the rules of the class `crm_interaction` of ADR-0079.R9, set per company by `retention_rule` (ADR-0052.R30.N1). The values of the `data_protection` rules are flagged content of the localization package; every value `l10n_vn` ships is `unverified` until the author verifies it.
Source: ADR-0052.R24

## Invariants

Statements are those of `invariants.csv`. Each row stands once in the module, in the chunk that states the rule its catalog source names first.

| Invariant | Name | Check point | Statement | Protects |
| --- | --- | --- | --- | --- |
| `INV-49` | `document_partner_matches_header` (area `documents`) | day, first step 5 | For every document type with a partner field, the shared document row's `partner_id` and `document_date` equal the typed header's values; types without one have both empty. | R241 |
| `INV-500` | `automatic_match_authenticated` | day, first step 5 | No interaction with `match_method` `reply`, `contact_email` or `domain` has an inbound message whose `is_sender_authenticated` is false, or whose mailbox was not authentication-verified when it was recorded. | R214, R224-R229 |
| `INV-501` | `open_complaint_flag_matches` | day, first step 6 | When the complaint consumer of `cash` has no pending, running or held delivery, `partner_collection.has_open_complaint` is true exactly for the partners with an open complaint. | R253 |
| `INV-503` | `follow_up_has_work_item` | day, first step 5 | Every task interaction has exactly one `follow_up_due` work item; it is open or claimed only while no later task corrects it and the task is not erased. | R245, R246 |

## Edge cases

Each row stands once in the module, in the chunk that states the rule its catalog source names first.

| Edge case | Name | Case | Outcome | Protects |
| --- | --- | --- | --- | --- |
| `EC-84` | `spoofed_contact_sender` | An e-mail claims a stored contact's address but fails DMARC; it stays unmatched with the contact's partner as an unauthenticated candidate and a work item. | `must_succeed` | R226, R229, R231 |
| `EC-85` | `same_email_two_mailboxes` | One message reaches two mailboxes; the second inbound message points to the first, canonical one and no second interaction is made. | `must_succeed` | R221 |
| `EC-86` | `reused_message_id` | A second e-mail reuses a `Message-ID` with other content, one of them a `Message-ID` the company sent, from an outside sender; both are kept as their own interactions and the later gets `duplicate_suspected`. | `must_succeed` | R222 |
| `EC-87` | `unknown_sender_onboarding` | An authenticated e-mail from an unknown company whose tax ID no partner holds (unlike `EC-80`): the onboarding run proposes `CreatePartner` with role `customer` and the sender's domain, a person approves it, the duplicate search runs, and a person then confirms the match; a second, unauthenticated e-mail from another unknown sender wakes no agent and waits for a person. | `must_succeed` | R233-R235 |
| `EC-88` | `complaint_pauses_dunning` | A customer with an overdue invoice has two complaints; dunning skips them until both are closed, whichever closes first. | `must_succeed` | R253 |
| `EC-90` | `contact_erasure` | A contact with e-mails in a shared thread, a complaint, a sent outbound message and a posted invoice is erased; their text and addresses are blanked, others' participant rows stay, the closed message's header and version are unchanged, the invoice stays, and the request closes keeping only the identity-proof hash. | `must_succeed` | R260; ADR-0052.R25 |
| `EC-100` | `forged_authentication_results` | An e-mail carries a forged `Authentication-Results` field with the company's authserv-id and a quoted `smtp.mailfrom` value holding `dmarc=pass`, under the receiving server's own field that reports DMARC fail; it stays unmatched. At a mailbox whose probe has not passed, every message is unauthenticated. | `must_succeed` | R214, R224, R225 |

## Settings

None: `settings.csv` holds no row with a `crm.` key.

The rules of this chunk name these company settings, which have no row in `settings.csv`: `crm.intake_interval_minutes` (default 5; R217), `crm.intake_batch_size` (default 50; R217), `crm.intake_failure_limit` (default 3; R219), `crm.duplicate_name_threshold` (between 0 and 1, default 0.6, flagged for tuning; R237), `crm.data_subject_request_due_days` (default 30; R261). `crm.document_intake_xml_timeout_minutes` (R215) is described in chunk 3. R218 also names `attachment_max_bytes`, a setting of `attachments`.

Reads: `work_case.<kind>.mode` (`work`; ADR-0066.R4), read as `work_case.quote_request.mode` in R230.

## UI annotations

The sources hold no ADR-0077 annotation (floorplan, title, facet, field annotation or tile) for the rules of this chunk. Work item kinds that these rules raise: `interaction_unmatched` (R229, R233), `inbound_message_matched` (R230), `mailbox_unreachable` (R219), `partner_duplicate_suspected` (R240), `follow_up_due` (R245), `complaint_open` (R250), `data_subject_request_received` and `data_subject_request_due` (R262); the module's table of work item kinds stands in chunk 3.

## Conflicts

CONFLICT ADR-0052.R24: ADR-0052.R30.N1 governs: the reserved retention setting that the rule lists among the package rules is not registered; the retention class `crm_interaction` of ADR-0079.R9, set per company by `retention_rule`, replaces it (R263).
CONFLICT ADR-0052.R11.N1: the DS-35 DDL and ADR-0064.R27 add the value `shop_floor_report` to `document_intake_purpose`, which the note lists without it; R210 states the current values.
CONFLICT ADR-0052.R18: the index marks the rule superseded only because its text speaks of superseded partners; no later unit replaces it, and R241 to R244 state it with ADR-0052.R18.N1 and ADR-0052.R18.N2 folded in.

## Proposed (not law)

None

## Trace

| Source | Where |
| --- | --- |
| ADR-0052.R8 | R201-R203 |
| ADR-0052.R9 | R204-R206 |
| ADR-0052.R10 | R207-R209 |
| ADR-0052.R11 | R210-R215 |
| ADR-0052.R11.N1 | R210, R215 |
| ADR-0052.R12 | R216-R219 |
| ADR-0052.R13 | R220-R223 |
| ADR-0052.R14 | R224-R227 |
| ADR-0052.R15 | R228-R232 |
| ADR-0052.R15.N1 | R230 |
| ADR-0052.R15.N2 | R230 |
| ADR-0052.R16 | R233-R236 |
| ADR-0052.R17 | R237-R240 |
| ADR-0052.R17.N1 | R237 |
| ADR-0052.R17.N2 | R237 |
| ADR-0052.R18 | R241-R244 |
| ADR-0052.R18.N1 | R244 |
| ADR-0052.R18.N2 | R241 |
| ADR-0052.R19 | R245-R248 |
| ADR-0052.R19.N1 | R247 |
| ADR-0052.R20 | R249-R251 |
| ADR-0052.R20.N1 | R250 |
| ADR-0052.R21 | R252-R253 |
| ADR-0052.R22 | R254-R255 |
| ADR-0052.R23 | R256-R258 |
| ADR-0052.R24 | R259-R263 |
