Module: crm    Chunk: 3 of 3    Source ADRs: ADR-0052, ADR-0057, ADR-0059
Build step(s): 3, 5    Generated from index: 30d5706    Compiled by: Claude Fable 5.2, 2026-11-21

# Compiled spec: `crm`, chunk 3

## Purpose

`crm` owns mailboxes, interactions, complaints, processing bases, outbound messages and data subject requests; it is a layer-4 module that imports no other layer-4 module. This chunk states the erasure of a data subject, the document type `outbound_message` and its sending, data labels and retention, summaries, insights and tax lookups, the command, event and catalog registers of the module, the lab check, the mailbox route for documents, business cards and the tuning of the duplicate search. Mailbox intake, matching, complaints, bases and the request document stand in chunks 1 and 2. Role templates, the area tree, retention rules and work case registration belong to `permissions`, `audit` and `work`; their units are traced `ref:` and not restated.

## Entities and tables

DDL: `docs/design/DS-35-crm.sql`. Rows of the tables that the rules of this chunk define.

| Table | Meaning | Key | Parent | Owner |
| --- | --- | --- | --- | --- |
| `outbound_message` | Typed header of the non-posting document type; holds no personal text (R414) | `id`; unique (`company_id`, `message_id_hash`) | `document`, `mailbox`, `partner` | `crm` |
| `outbound_message_content` | Subject and body of a message, outside the header and the version (R415) | `id`; unique (`company_id`, `outbound_message_id`, `content_hash`) | `document` | `crm` |
| `outbound_message_recipient` | Recipient contacts of the message's partner (R416) | `id`; unique (`outbound_message_id`, `contact_id`) | `outbound_message`, `contact` | `crm` |
| `outbound_message_delivery` | One row per delivery attempt, the late data of the document (R426) | `id`; unique (`outbound_message_id`, `attempt_number`) | `outbound_message` | `crm` |
| `outbound_message_delivery_recipient` | The addresses one attempt used, copied at send (R425) | `id`; unique (`outbound_message_delivery_id`, `contact_id`) | `outbound_message_delivery` | `crm` |
| `interaction_summary` | Summary of a partner's interactions; an agent's arrives by an approved change proposal (R436) | `id` | `partner`, `interaction` | `crm` |
| `partner_insight` | Computed insight with its method; deleted by erasure (R437) | `id`; unique (`partner_id`, `name`) | `partner` | `crm` |
| `partner_tax_lookup` | Dated snapshot of a tax ID lookup; `result` is untrusted (R439) | `id` | `partner` | `crm` |

Tables of other chunks that the rules here name, without a row: `mailbox`, `interaction`, `interaction_content`, `interaction_participant`, `inbound_message`, `complaint`, `processing_basis`, `data_subject_request`, `data_subject_request_content`, `partner_email_domain`, `partner_search_key`, `public_mail_domain`.

Reads: `document`, `document_version`, `partner`, `contact`, `user_account`, `retention_rule`, `e_invoice_record`, `document_extraction`, `extraction_result_link`, `audit_change`.

## Commands and queries

Rows for the commands whose rules stand in this chunk; R441 gives effect class and flags of every `crm` command. Effect class is `other` unless the row says otherwise. Authorization leaves are those of `authorization-areas.csv`, levels those of `authorization-verb-levels.csv`. "Not stated" means the sources fill no value.

| Name | Actor and authorization | Input | Effect | Events | Error codes |
| --- | --- | --- | --- | --- | --- |
| `EraseDataSubject` | `human_only`; leaf `data_protection` at `full` | a deletion request in `approved` with its subject identified | R401-R411 | `DataSubjectErased` | not stated |
| `CreateOutboundMessage`, `UpdateOutboundMessage` | leaf `outbound_message` at `edit`; `is_draft_only` | header, content, recipients | writes the draft and its content row, calls `GetOutboundContentCheck` (R417) | generated document events (ADR-0009.R22) | check result `outbound_content_flagged`; `invalid_state_transition` for `Update` (R419) |
| `DeleteOutboundMessage`, `SubmitOutboundMessage`, `CancelOutboundMessage` | leaf `outbound_message` at `edit` | the message | generated verbs (ADR-0009.R2) | generated document events | not stated |
| `ApproveOutboundMessage`, `RejectOutboundMessage` | leaf `outbound_message`, the role's approval flag | the message | generated verbs | generated document events | not stated |
| `SendOutboundMessage` | leaf `outbound_message` at `post`; effect class `outbound_send`; a person, or `system` under R424; never an agent | an `approved` message | R420-R425 | `OutboundMessageSendRequested` | `mailbox_not_sending`, `recipient_address_missing`, `recipient_not_partner_contact`, `consent_missing`, `outbound_content_out_of_scope`, `document_not_approved`, `automatic_send_not_allowed` |
| `RecordOutboundMessageOutcome` | only `crm_mail_sender`; `is_internal_only` (ADR-0054.R8.N1); leaf `outbound_message` | the attempt and its outcome | R427-R430 | `OutboundMessageOutcomeRecorded` | not stated |
| `CreateInteractionSummary`, `UpdateInteractionSummary` | leaf `interaction` at `edit`; `is_proposal_bound` | partner, interaction, `summary_text` | writes `interaction_summary` (R436) | not stated | not stated |
| `DeleteInteractionSummary` | leaf `interaction` at `edit`; `human_only` | the summary | deletes it | not stated | not stated |
| `UpdatePartnerInsight`, `DeletePartnerInsight` | leaf `partner_insight` at `edit`; `human_only` | the insight | R438 | not stated | not stated |
| `RunPartnerInsightComputation` (job) | nightly job; `is_internal_only` (ADR-0054.R8.N1); leaf `partner_insight` | not stated | computes `partner_insight` rows (R437) | `PartnerInsightComputationCompleted` | not stated |
| `RecordPartnerTaxLookup` | `is_internal_only` (ADR-0054.R8.N1); leaf `partner_insight` | `tax_id`, `provider`, `result` | writes `partner_tax_lookup` (R439) | not stated | not stated |
| `ProposeContactFromExtraction` | verb Propose at `edit` on `partner`; `is_draft_only` | a verified extraction | drafts a change proposal (R471) | not stated | not stated |
| `GetOutboundContentCheck` (query) | registered query owned by `crm` (R417); area not stated | a customer-facing draft | returns the outbound content check, evaluated in the plan of every command that creates or updates a customer-facing draft (R16, R417; ADR-0050.R36) | none | check result `outbound_content_flagged`; the send still refuses with `outbound_content_out_of_scope` |

Not registered commands: the consumers `crm_partner_search`, `crm_mailbox_probe`, `crm_mail_sender`, `crm_payment_reminder_drafts` (R444) and `mailbox_document_intake` (R457). `CloseOutboundMessage` and `ReopenOutboundMessage` do not exist (R413, R419).

Codes of the rules here bound to commands of other chunks or modules: `mailbox_owner_not_permitted` (`UpdateMailbox`, R456); `duplicate_external_document`, `e_invoice_superseded` (`tax`, R464-R466); check results `quarantine_limit_reached`, `duplicate_key_found`, `e_invoice_key_conflict` (R458, R464, R466); `version_conflict`, `concurrent_update` (R446); the other codes of R447.

## Rules

### Erasure of a data subject

R401. `EraseDataSubject` (`human_only`, `crm`; ADR-0019.R10) takes a deletion request in state `approved` with its subject identified.
Source: ADR-0052.R25

R402. The subject's rows. For a contact: interactions whose `contact_id` is the contact; participants whose `contact_id` is the contact; participants and inbound messages whose normalized `email_address` or `sender_address` equals an address of the subject (the contact's address and those the request names), matched or not. For an individual, sole proprietorship or employee partner: also every interaction, complaint and outbound message of that partner, and its contacts' rows as above.
Source: ADR-0052.R25

R403. Blanked in `crm`: the subject's participant addresses and names; for interactions the subject wrote (as their contact, their `from` participant or the sender of their inbound message), the interaction's subject and content; the raw `Message-ID`, sender address, display name, domain, parse notes and `sender_authentication` of the subject's inbound messages; complaint titles and resolution notes of the subject's complaints; the content rows of outbound messages whose only recipient is the subject or whose partner is the subject, the subject's delivery recipient addresses, and the `failure_reason` of those attempts; interaction summaries and tax lookups of the subject; an individual partner's `partner_email_domain.domain` (deactivated); and the requester data and `outcome_note` of the subject's earlier, closed requests. Each blanked row gets `erased_at` and keeps its kinds, dates, partner links and hashes; a blanked content row also loses its `content_salt`, so its hash can no longer confirm a guessed text.
Source: ADR-0052.R25

R404. Shared threads: an interaction with other participants keeps their rows and, when the subject did not write it, its subject and content; only the subject's address and text fields are blanked.
Source: ADR-0052.R25

R405. The subject's `partner_insight` and `partner_search_key` rows are deleted, not blanked; they are derived and recomputable.
Source: ADR-0052.R25

R406. Erasure closes the subject's current bases with `end_reason: erased`, and resolves the open `follow_up_due` items of the subject's tasks with resolution `erased` (`INV-503`).
Source: ADR-0052.R25

R407. The request's requester data is kept while the request is open, because the answer goes to the requester. `EraseDataSubject` closes the request as its last step and blanks the request's content row except `identity_proof_hash`, which stays as evidence that the requester was verified. How long that proof may be kept is the author's (open question). A deletion request closed without erasure (refused) keeps its requester data as the evidence of the answer, until a later erasure.
Source: ADR-0052.R25

R408. Headers and versions of outbound messages and data subject requests hold no personal text (R414; ADR-0052.R24), so erasure never touches a document in a final state, and `INV-504` holds.
Source: ADR-0052.R25

R409. Lower layers are erased through their contracts: `master_data` (partner and contact fields), `agent_runs` (run logs), `audit` (`audit_change`, ADR-0038.R4), `attachments` (links, except those to posted accounting documents, ADR-0038.R15) and `work` (work item notes). The subject's document extractions (by partner, by result links to the subject's contact or partner, by the subject's inbound messages) are erased through `attachments.contract`, except the accounting fields of an extraction linked to an incoming e-invoice record or a posted accounting document (ADR-0057.R19). `EraseDataSubject` of a partner also clears the bodies of that partner's record thread and ends their attachment links (ADR-0076.R10); threads on the partner's documents are an open question.
Source: ADR-0052.R25, ADR-0052.R25.N1, ADR-0052.R25.N2

R410. Other modules react to `DataSubjectErased`, which carries only IDs. The `sales`, `purchasing` and `cash` consumers erase their own personal data outside accounting documents (DS-22, DS-25); the `imports` consumer `imports_data_subject_erasure` blanks the subject's values in staging rows of import batches (DS-21). Data on accounting documents is kept for the legal retention period: the snapshots that `sales`, `purchasing` and `cash` keep on posted documents and versions are destroyed after their retention period by `DestroyRetainedPersonalData` (`system`, `is_internal_only`, module `audit`), run by the retention job. Both commands use the same catalog-driven hooks under the erasure exception of ADR-0079.R7: each module destroys its own tables in its consumer of `DataSubjectErased` or `PersonalDataDestructionDue`. Before then the subject is blocked (ADR-0079.R6, ADR-0079.R7, ADR-0079.R9).
Source: ADR-0052.R25, ADR-0052.R25.N3

R411. `EraseDataSubject` writes an audit record and a processing log entry (ADR-0038.R9).
Source: ADR-0052.R25

### The document type `outbound_message`

R412. `outbound_message` is a non-posting document type of `crm` (ADR-0009). Its drafts get versions, taint, approval and agent-draft keys (ADR-0029.R8; ADR-0030.R11).
Source: ADR-0052.R27

R413. States: `draft → (pending_approval →) approved → sending → closed`, and `canceled` (ADR-0009.R6, plus `sending`). `sending` is not final, like `issuing` in ADR-0028.R6: header and recipients are immutable in it, as in a final state (ADR-0009.R14), because the content has gone to the mail server. `closed` is reached only by the delivery outcome `sent` (R427). The type registers no `Close` command (`CloseOutboundMessage` does not exist), an exception to the generated verbs of ADR-0009.R2.
Source: ADR-0052.R27

R414. Header: sending mailbox (`mailbox_id`), partner, `message_type` (`reply`, `document`, `payment_reminder`, `follow_up`, `marketing`, `general`), `content_hash`, `in_reply_to_interaction_id`, `message_id` (made at `Create` as `<UUIDv7@mailbox domain>` and kept on every attempt; it names no person), `message_id_hash`. Delivery facts are not on the header (R426).
Source: ADR-0052.R27

R415. The `subject` and `body_text` live in `outbound_message_content`, keyed by (`company_id`, `outbound_message_id`, `content_hash`), with `erased_at`. Each row has a random `content_salt` (128 bits, hex); `content_hash` is the SHA-256 over the message's ID, the salt and the canonical JSON of subject and body, so a blanked row's hash cannot confirm a guessed text. `Create` and `Update` write a new row when the text changes. The version's canonical content holds the hash, never the text.
Source: ADR-0052.R27

R416. Recipients are rows of `outbound_message_recipient` (contact, `role`: `to`, `cc`, `bcc`). They are only contacts of the message's partner, held by a composite key to `contact`, never addresses taken from an inbound message (ADR-0019.R17). They hold no address; the addresses used are copied at send into the delivery recipients (R425).
Source: ADR-0052.R27

R417. `crm` owns `GetOutboundContentCheck` (ADR-0050.R36). `CreateOutboundMessage` and `UpdateOutboundMessage` call it directly, as `crm`'s own customer-facing drafts, so a finding is the check result `outbound_content_flagged` in their plan.
Source: ADR-0052.R27

R418. Attachments are linked, such as a quotation PDF from the print worker of DS-27. Commands of the type: the generated `Create`, `Update`, `Delete`, `Submit`, `Approve`, `Reject` and `Cancel`; `SendOutboundMessage`; `RecordOutboundMessageOutcome`.
Source: ADR-0052.R27

R419. There is no `ReopenOutboundMessage`: ADR-0009.R4 already lets `Update` take an `approved` document back to `draft` with a new version, voiding the approval. `Update` is refused in `sending`, where an attempt is in flight, in `closed` and `canceled` (`invalid_state_transition`), and while the latest attempt is `unknown` (R429).
Source: ADR-0052.R27

### Sending an outbound message

R420. `SendOutboundMessage` (effect class `outbound_send`) runs only on an `approved` message. `Submit` brings a draft there, and the policy decides whether someone must approve it first (ADR-0029.R6; ADR-0043); a client may send `Submit` and `Send` as one batch. Agents never submit or send (ADR-0050.R30). Send adds no policy point. Its checks run in the order R421, R422, R423, R424, and any failure refuses the whole send.
Source: ADR-0052.R28

R421. Delivery check: the mailbox has `is_sending_enabled` (`mailbox_not_sending`); the message has at least one `to` recipient, and each recipient contact is active and has an address (`recipient_address_missing`) and belongs to the message's partner (`recipient_not_partner_contact`).
Source: ADR-0052.R28

R422. Consent check: for each recipient, take the purpose of the message type. If it needs consent, a current consent basis must exist for the contact (or for its partner when that is an individual or a sole proprietorship), with no pending proposal to close it. A type with no purpose counts as needing consent. Else `consent_missing`, naming the recipients (ADR-0019.R9).
Source: ADR-0052.R28

R423. Scope check (ADR-0029.R14): every linked document, and the source document of every attached print, has the message's partner (`document.partner_id`). Attached prints come from a customer print contract without `cost` or `margin` field classes (DS-27). No number of another partner's document appears as a whole token in the subject or body. Else `outbound_content_out_of_scope`. For a generated file the check reads the attachment's own columns through `attachments.contract`, never `reporting`: it passes the file only when `generated_kind` is `print`, `generated_audience` is `external`, and the partner of `generated_subject_document_id` is the message's partner; otherwise `outbound_content_out_of_scope` (ADR-0049.R28, ADR-0049.R29). The check also refuses a message whose linked document, or the source document of an attached print, is in `draft` or `pending_approval` at send, with `document_not_approved`; for a quotation reply the order is therefore: approve the quotation, then send.
Source: ADR-0052.R28, ADR-0052.R28.N1, ADR-0052.R28.N2

R424. Actor check: a person may send any type. A `system` actor may send only types in the company setting `crm.automatic_send_types` (default empty), and only a version that is not effectively tainted and that has no origin agent run. Else `automatic_send_not_allowed`.
Source: ADR-0052.R28

R425. After the checks, in one transaction, the message moves to `sending`, a new `outbound_message_delivery` attempt is inserted (`attempt_number`, `requested_at`, no outcome yet), the recipient addresses are copied into `outbound_message_delivery_recipient` (`outbound_message_delivery_id`, contact, role, `email_address`, `erased_at`), and `OutboundMessageSendRequested` is emitted.
Source: ADR-0052.R28

R426. `outbound_message_delivery` is the late data of ADR-0009.R14: its own table that refers to the document. Each row is one attempt; its outcome columns (`outcome`: `sent`, `failed`, `unknown`; `outcome_at`, `sent_at`, `sent_content_hash`, `interaction_id`, `failure_reason`) are set once, and only erasure blanks `failure_reason` (ADR-0052.R7). The latest attempt is the one with the highest `attempt_number`. The database holds at most one attempt without an outcome and at most one `sent` attempt per message.
Source: ADR-0052.R28

R427. The external consumer `crm_mail_sender` (ADR-0013.R10) sends through the mailbox connector and records the result with `RecordOutboundMessageOutcome`. Sent: the attempt gets `sent_at`, the `sent_content_hash` of the submitted MIME (ADR-0052.R13 uses it to recognize own messages) and an outbound e-mail interaction with the message's participants and content; the message moves to `closed`. That interaction is untrusted when the sent version is tainted, so later reads of it still taint.
Source: ADR-0052.R28

R428. Failed (a permanent refusal): the attempt gets `failure_reason`; the message returns to `approved` and the work item `outbound_message_failed` is raised. A person sends again, changes it with `Update` (back to draft), or cancels it.
Source: ADR-0052.R28

R429. Unknown (no answer, such as a timeout). Where the connector cannot search the sent folder, the attempt records `unknown`, the message returns to `approved` at once, the work item `outbound_message_failed` is raised, and the message is never resent blindly. Where the connector can search, the attempt follows the note of ADR-0013.R10: the message stays in `sending`; `crm_mail_sender` waits the settle delay, searches for the `Message-ID` (our reference, which serves as the message's idempotency key) twice, at least the delay apart, and submits again only when both searches find nothing; after the configured unknown rounds the attempt records `unknown` and the message returns to `approved` with `outbound_message_failed`. While the latest attempt is `unknown`, `UpdateOutboundMessage` is refused with `invalid_state_transition`: a changed text under the same `Message-ID` could be recorded as sent when the earlier text is what left. A person sends again or cancels.
Source: ADR-0052.R28, ADR-0052.R28.N3

R430. Command handlers make no network calls (ADR-0022.R6), so the search is the consumer's: when the previous attempt of the message is `unknown`, `crm_mail_sender` searches the mailbox's sent folder for the `Message-ID` before it submits, where the connector can. When it finds the message, it records `sent` for the new attempt without submitting again; when the connector cannot search, it records `unknown` again rather than resend.
Source: ADR-0052.R28

R431. Payment reminders: the `crm` consumer of the completion event of `RunDunning` (ADR-0048.R17) drafts one `payment_reminder` message per customer, owned by the human the run acted for. Recipients are the partner's active contacts with `is_accounts_contact` and an address (a flag of DS-20). DS-20 has no partner-level e-mail address, so when no contact is flagged the draft has no recipient and its note says so; a person adds one before sending. A person sends it. `cash` never imports `crm`.
Source: ADR-0052.R28

### Data labels and retention

R432. Data labels (ADR-0019.R7; spec 17) and the `is_untrusted` attribute (ADR-0029.R10) per field. The list is an extract of `personal-data-fields.csv`; where they disagree the catalog wins and the difference is a defect (ADR-0079.R2).
- `interaction.subject`, `interaction_content.body_text`: personal; untrusted when the interaction `is_untrusted`.
- `interaction_participant.email_address`, `display_name`: personal; untrusted for participants of an untrusted interaction.
- `inbound_message.message_id`, `sender_address`, `sender_display_name`, `sender_domain`, `sender_authentication`, `parse_notes`: personal; always untrusted.
- `complaint.title`, `resolution_note`: personal; `title` untrusted when `is_title_untrusted`.
- `outbound_message_content.subject`, `body_text`; `outbound_message_delivery_recipient.email_address`; `outbound_message_delivery.failure_reason`: personal; not untrusted, taint lives on the version.
- `data_subject_request_content` requester fields, `outcome_note`: personal; requester fields untrusted when taken from a message.
- `interaction_summary.summary_text`: personal; untrusted when the summary `is_untrusted`.
- `partner_email_domain.domain`, `partner_search_key` columns, `partner_tax_lookup.tax_id` and `result`: by the partner's kind, as ADR-0019.R7; `result` always untrusted.
- `partner_insight.value`: by the partner's kind; not untrusted.
- `data_subject_request_content.identity_proof_hash`: personal, subject kind `requester`, always (the catalog row governs); not untrusted.
- `mailbox` columns, processing purposes and bases, the processing log, the other hashes: internal; not untrusted.
Source: ADR-0052.R29, ADR-0052.R29.N1

R433. Event payloads carry IDs, states and codes only, never the fields of R432 (ADR-0013.R4).
Source: ADR-0052.R29

R434. Interactions and messages are kept until erased. Whether they must be deleted after a time when no request comes is a package rule for the author (open question). The setting `crm.interaction_retention_days` is not registered: the retention class `crm_interaction` of ADR-0079.R9, set per company by `retention_rule`, stands in its place.
Source: ADR-0052.R30, ADR-0052.R30.N1

R435. Attachments follow ADR-0038.R15. A file from an e-mail that is later linked to a posted document becomes accounting evidence.
Source: ADR-0052.R30

### Summaries, insights and lookups

R436. `interaction_summary` (ADR-0019.R20; spec 03 rule 9): partner, interaction, `summary_text`, `agent_run_id`, `model`, `prompt_version`, `is_untrusted`, `edited_by_user_id`, `erased_at`. An agent's summary is a change proposal (`CreateInteractionSummary` is `is_proposal_bound`, R441); a person submits and approves it.
Source: ADR-0052.R31

R437. `partner_insight`: partner, `name`, `value`, `method`, `computed_date`, `edited_by_user_id`. The nightly job `RunPartnerInsightComputation` computes the insights deterministically from interactions and from `documents.contract.list_partner_documents`, such as the average days between orders and the last order date, and emits `PartnerInsightComputationCompleted`.
Source: ADR-0052.R31

R438. A person may edit or remove what the system learned (ADR-0019.R20). `UpdatePartnerInsight` sets `edited_by_user_id`, and the job never overwrites an edited value until a person deletes it with `DeletePartnerInsight`; then the job computes it again.
Source: ADR-0052.R31

R439. `partner_tax_lookup`: `tax_id`, `provider`, `looked_up_at`, `result`, `erased_at`; the dated snapshot of ADR-0019.R18, written by `RecordPartnerTaxLookup`.
Source: ADR-0052.R31

### Command register

R440. Commands and queries of `crm` carry effect class and flags (ADR-0008.R1; ADR-0027.R17; ADR-0029.R2; ADR-0050.R26). `is_draft_only` is true only for the commands that create or update drafts of `outbound_message` and `data_subject_request`; they are the only `crm` commands a tainted run may send. Every other agent change in `crm` is a change proposal (`CreateChangeProposal`, ADR-0029.R1).
Source: ADR-0052.R32

R441. Per command: effect class `other`, no flag and `is_draft_only` false, unless its line says otherwise. The commands that only a system job or consumer runs are `is_internal_only` (ADR-0054.R8.N1): no role holds them at any level, and they have no REST endpoint, MCP tool or tool definition.
- `CreateMailbox`, `UpdateMailbox`: `human_only`.
- `VerifyMailboxAuthentication`, `RecordMailboxAuthenticationCheck`: the second `is_internal_only`, only for `crm_mailbox_probe`.
- `RunMailboxIntake`, `RecordInboundMessage`, `RecordMailboxIntakeOutcome`: the last two `is_internal_only`, only for the intake job; `RunMailboxIntake` keeps a declared `full`, since a person may also start it.
- `CreateInteraction`, `MatchInteraction`: `is_proposal_bound`.
- `CreateInteractionLink`, `DeleteInteractionLink`: no flag.
- `UnmatchInteraction`: `human_only`.
- `CreatePartnerEmailDomain`, `UpdatePartnerEmailDomain`, `CreateProcessingPurpose`, `UpdateProcessingPurpose`: effect class `master_data_change`.
- `CreateComplaint`, `UpdateComplaint`, `CloseComplaint`, `ReopenComplaint`, `CreateProcessingBasis`, `CloseProcessingBasis`: `is_proposal_bound`.
- `CreateOutboundMessage`, `UpdateOutboundMessage`: `is_draft_only`.
- `DeleteOutboundMessage`, `SubmitOutboundMessage`, `ApproveOutboundMessage`, `RejectOutboundMessage`, `CancelOutboundMessage`: no flag; no `CloseOutboundMessage` or `ReopenOutboundMessage` exists.
- `RecordOutboundMessageOutcome`: `is_internal_only`, only for `crm_mail_sender`.
- `SendOutboundMessage`: effect class `outbound_send` (R420).
- `CreateDataSubjectRequest`, `UpdateDataSubjectRequest`: `is_draft_only`.
- `DeleteDataSubjectRequest`, `SubmitDataSubjectRequest`, `ApproveDataSubjectRequest`, `RejectDataSubjectRequest`, `CancelDataSubjectRequest`, `CloseDataSubjectRequest`: no flag.
- `EraseDataSubject`: `human_only`.
- `CreateInteractionSummary`, `UpdateInteractionSummary`: `is_proposal_bound`.
- `DeleteInteractionSummary`, `UpdatePartnerInsight`, `DeletePartnerInsight`: `human_only`.
- `RunPartnerDuplicateScan`, `RunPartnerInsightComputation`, `RecordPartnerTaxLookup`: `is_internal_only`.
Source: ADR-0052.R32

R442. Queries of `crm`: `ListPartnerTimeline`, `ListInteraction`, `GetInteraction`, `ListInboundMessage`, `ListComplaint`, `GetComplaint`, `ListProcessingBasis`, `ListPartnerDuplicateCandidate`, `ListMailbox`, `GetOutboundContentCheck`.
Source: ADR-0052.R32

### Events, consumers and locks

R443. Events of `crm`, none of which carries a personal field: `MailboxCreated`, `MailboxUpdated`, `MailboxAuthenticationCheckRecorded`, `MailboxIntakeCompleted`, `MailboxIntakeOutcomeRecorded`, `InboundMessageRecorded`, `InteractionCreated`, `InteractionMatched`, `InteractionUnmatched`, `PartnerEmailDomainCreated`, `PartnerEmailDomainUpdated`, `ComplaintCreated`, `ComplaintUpdated`, `ComplaintClosed`, `ComplaintReopened`, `ProcessingBasisCreated`, `ProcessingBasisClosed`, `OutboundMessageSendRequested`, `OutboundMessageOutcomeRecorded`, `DataSubjectErased`, `PartnerDuplicateScanCompleted`, `PartnerInsightComputationCompleted`, and the generated document events of `outbound_message` and `data_subject_request` (ADR-0009.R22).
Source: ADR-0052.R33

R444. Consumers of `crm`: `crm_partner_search` (partner and contact events; ADR-0052.R17), `crm_mailbox_probe` (external; ADR-0052.R11), `crm_mail_sender` (external; R427), `crm_payment_reminder_drafts` (the completion event of `RunDunning`; R431).
Source: ADR-0052.R33

R445. Consumers elsewhere: the complaint consumer of `cash` (ADR-0052.R21); the erasure consumers of `sales`, `purchasing`, `cash` and `imports` (R410).
Source: ADR-0052.R33

R446. Lock order: commands of `crm` take no lock class beyond their own rows and `event_subject` (ADR-0027.R10). Concurrent edits of a complaint or a match fail with `version_conflict` or `concurrent_update`.
Source: ADR-0052.R33

### Catalog rows

R447. DS-04 errors of `crm`: `public_mail_domain`, `interaction_in_future`, `interaction_already_matched`, `link_partner_mismatch`, `recipient_not_partner_contact`, `recipient_address_missing`, `mailbox_not_sending`, `automatic_send_not_allowed`, `data_subject_kind_invalid`, `consent_evidence_missing`. Check results: `interaction_unmatched`, `email_domain_shared`. `automatic_send_not_allowed` also writes denial records (ADR-0038.R5). Reads outside a tainted run's scope use `tainted_read_out_of_scope` of ADR-0050, which DS-04 and ADR-0038.R5 list.
Source: ADR-0052.R34

R448. Work item kinds of this ADR: `complaint_open`, `follow_up_due`, `outbound_message_failed`, `mailbox_unreachable`, `data_subject_request_received`; the kind for a matched inbound e-mail is named `inbound_message_matched` (ADR-0052.R15). Owner rules (ADR-0042.R7): `subject_assignee` (the user the subject names as assignee, such as a task's) and `subject_owner` (the user the subject names as owner, such as a mailbox's `owner_user_id`).
Source: ADR-0052.R34

R449. CRM invariants use INV-500 to INV-599, area `crm`: `INV-500` (automatic matches only for authenticated senders), `INV-501` (the open-complaint flag equals open complaints), `INV-502` (sent attempts had consent), `INV-503` (one work item per follow-up task), `INV-504` (erased rows are blank), `INV-505` (a message is closed exactly when an attempt was sent). `INV-49`, area `documents`, the last free code of the documents group 40–49 (DS-16): the shared document row's partner and date equal the header's.
Source: ADR-0052.R34

R450. Edge cases of this ADR: `EC-84` to `EC-91`, `EC-99` and `EC-100`; `EC-92` to `EC-98` are reserved for ADR-0049. The business event types `email_received`, `interaction_recorded`, `complaint_raised`, `complaint_resolved`, `consent_given`, `consent_withdrawn`, `data_subject_erasure_requested` and `message_sent` are first executable at step 5 (DS-17). DS-17 keeps one business event per fact.
Source: ADR-0052.R34

R451. `email_received` is the one event for "a message arrives in a mailbox and intake records it". E-mails that DS-17 names by their business meaning are that same fact and are not also emitted as `email_received`: `quotation_requested` and `customer_inquiry_received` (ADR-0051.R11, ADR-0051.R14) and `bank_account_change_requested` (ADR-0029.R4).
Source: ADR-0052.R34

R452. The other event types are people's acts: `interaction_recorded` (a call, meeting, chat, note or task a person enters; never an e-mail), `complaint_raised` and `complaint_resolved` (ADR-0052.R20, ADR-0052.R21), `consent_given` and `consent_withdrawn` (a person records or ends a basis with its evidence, ADR-0052.R23), `data_subject_erasure_requested` (a person records a deletion request and erases, R401) and `message_sent` (a person sends an outbound message, R420). When the act follows an e-mail, it refers to that e-mail's event.
Source: ADR-0052.R34

R453. `EC-87` and EC-80 are both `customer_inquiry_received`: EC-80 (ADR-0051) is the onboarding proposal for a sender whose tax ID an existing partner holds, rejected; `EC-87` is the clean path with no duplicate, approved and then matched by a person, plus an unauthenticated unknown sender that wakes no agent.
Source: ADR-0052.R34

### Lab check

R454. Lab check `t11_crm.py` (validation lab) loads DS-20, DS-35 and DS-06 together. It does not cover commands, consumers, the connector and its probe, the timeline query and erasure across modules. It checks:
- the natural key of inbound messages: the provider key, the canonical row per hashes, copies that must share hashes and interaction and point to a canonical row, reused `Message-ID`s and own messages;
- composite company keys, contacts held inside their partner, lowercase contact e-mail, and recipients only from the message's partner;
- interaction kinds, directions, matches, tasks, the untrusted inbound e-mail, links only between rows of the same partner, and unmatching refused while a link exists;
- the append-only trigger, with and without the erasure setting, on interactions, inbound messages, content and delivery tables, and the processing log's own trigger;
- a model of the final-state trigger of ADR-0009.R14 on the `outbound_message` and `data_subject_request` headers, their recipients and `document_version`: no change in `sending` or a final state, and erasure of a closed message's content row without touching header or version;
- delivery attempts: one open attempt, one sent attempt, outcomes set once;
- content rows: a random salt in every row, blanked by erasure; deletes only inside the `Delete` of a draft, never of a submitted message or under another document's setting;
- complaint states, consent evidence, one current basis, closing once, `company_id` and `recorded_at` coverage, the DDL loading top to bottom, and no personal text column on the document headers of `outbound_message` and `data_subject_request`;
- as pure functions: the RFC 8601 parser and sender authentication (quoted strings, comments, single `From`, DMARC errors failing closed), own-message recognition, the matching cascade with its candidate order on shuffled inputs, and name normalization with the core fold table and trigram search.
Source: ADR-0052.R35

### Scope

R455. These CRM features are Phase 2 or later, not Phase 1: leads, opportunities and a pipeline; marketing (campaigns, segments, lists); appointments and calendar sync; chat and telephony channels; service cases with service levels (SLA). The CRM-only profile does not bring them forward.
Source: ADR-0052.V.N1

### Documents from a mailbox

R456. `mailbox` has `document_intake_purpose` (`supplier_invoice`, `inquiry_lines`, `shop_floor_report` or empty; the last value by ADR-0064.R27) and `document_intake_quarantine_limit` (default 20). `UpdateMailbox` (`human_only`, ADR-0052.R11) refuses a purpose when the mailbox owner does not hold `edit` on the purpose's leaf (`mailbox_owner_not_permitted`), so deliveries never fail for rights.
Source: ADR-0057.R25

R457. The `crm` consumer `mailbox_document_intake` of `InboundMessageRecorded` requests, as `system` on behalf of the mailbox owner and with `inbound_message_id`, an extraction for every XML part first. Other parts are requested only after every XML part of the message is recorded, by the same consumer reacting to their `DocumentExtractionRecorded`, or by its daily sweep once `crm.document_intake_xml_timeout_minutes` (default 60) have passed without a recording; and only when the message is matched to exactly one active partner (ADR-0052.R15), which needs its sender authentication to pass (ADR-0052.R14). Authentication alone is not enough: a stranger's domain or a free mail address can pass it. From a message that is not matched, non-XML parts are stored only, and a person may request their extraction from the message.
Source: ADR-0057.R25

R458. The quarantine cap is decided after the read, when the signature state is known. It counts the quarantined records imported from messages not matched to a partner, per mailbox and business date, the date being the message's receipt in the company's time zone; records of matched messages and records with a passed signature never count. Past the cap, the XML's extraction is still recorded as `extracted` but its record is not imported: the extraction carries the check result `quarantine_limit_reached`, and one `e_invoice_quarantine_overflow` item per mailbox and business date tells the mailbox owner and lists those extractions; a person imports any of them from the item with `ImportEInvoiceRecord`, which then follows the person's import path (R463), or closes the item. Nothing is canceled for the cap.
Source: ADR-0057.R25

R459. There is no other limit on parts: non-XML parts of messages not matched to a partner are stored only and cost no reading; XML parts cost a bounded deterministic read (ADR-0057.R5) and their quarantined records are capped; documents of matched partners are read, and the agent budgets of ADR-0050.R22 bound them where a model is involved.
Source: ADR-0057.R25

R460. The extraction's `partner_id` is the active supplier whose normalized tax ID equals a `passed` seller tax ID (exactly one), else the interaction's matched partner, else empty. It selects the mapping rules of ADR-0057.R5.
Source: ADR-0057.R25

R461. When the e-invoice reader of rung 1 gives a structurally valid record (schema and arithmetic), the `tax` consumer `e_invoice_intake` of `DocumentExtractionRecorded` runs `ImportEInvoiceRecord` as `system` on behalf of the human the request acted for (the mailbox owner for the mailbox route), whatever the signature, with `source_attachment_id`, `inbound_message_id`, `signature_state`, the clearance code state (`present`, `missing`, `not_required`), the arithmetic outcome and both the stated issue time and the signing time. The extraction links the record (`extraction_result_link`) and ends `extracted`; it raises no review item of its own, so each XML gives at most one human task, the record's.
Source: ADR-0057.R25

R462. `e_invoice_record.source_attachment_id` is unique among incoming records: a second import of the same attachment, by the route, a person, or several people importing the same listed extraction, returns the first record and creates nothing.
Source: ADR-0057.R25

R463. For an XML a person uploaded and requested (`RequestDocumentExtraction`, purpose `supplier_invoice`), the same consumer imports it on behalf of that person, with `imported_by_user_id` set to them, so the importer confirmation of ADR-0051.R20 applies; quarantine, supersession and key conflicts work as for the mailbox, and the quarantine cap does not apply.
Source: ADR-0057.R25

R464. Duplicates are an outcome: `duplicate_external_document` from the import ends the route normally; the extraction gets the check result `duplicate_key_found` and a link to the existing record, and the delivery completes.
Source: ADR-0057.R25

R465. A record whose `signature_state` is not `passed` is imported quarantined (`is_quarantined`): it holds no supplier-invoice key and the purchase invoice agent starts only after a person confirms its supplier with `ConfirmEInvoiceSupplier`, which lifts the quarantine; the key check runs then and refuses a second holder (`duplicate_external_document`). The structured fields of a `failed` or `signer_mismatch` record count as untrusted; those of an `absent` one do not, unless the package's format declares the signature mandatory (ADR-0057.R6). Quarantined records of one sender in one mailbox on one business date share one `e_invoice_quarantine_review` item, the one human task for them; records that share a key are shown together in it.
Source: ADR-0057.R25

R466. A later record with the same key and a `passed` signature supersedes a quarantined one: the quarantined record gets `superseded_by_record_id`, and `e_invoice_record_superseded` tells an accountant. `ConfirmEInvoiceSupplier` refuses a superseded record (`e_invoice_superseded`). When the key is held by a confirmed, formerly quarantined record, the record with a passed signature is still imported, with `key_conflict_with_record_id` naming the holder and the check result `e_invoice_key_conflict`; it raises `e_invoice_key_conflict` for an accountant, and no agent starts on either until a person resolves the conflict. A genuine signed invoice is never refused silently.
Source: ADR-0057.R25

R467. A PDF of the same message is the XML's rendering only when the XML's invoice number appears as a whole token in the PDF's text layer; the file name stem only decides between several XML parts that match. It is then linked to the record as its rendering, as received and unverified, and its request ends `canceled` by the system with reason `rendering_of_parsed_xml`. Any other PDF is extracted as a document of its own.
Source: ADR-0057.R25

R468. The e-invoice provider connection (pulling records from a provider or the tax authority, the authority status and revocation check) stays the DS-24 add-on; it uses the same import path.
Source: ADR-0057.R25

### Business cards

R469. Rung 3 decodes a QR code with a vCard or MeCard into contact fields (name, organization, job title, e-mails, phones, address, URL). The values are personal; names, e-mails, phones and URLs are untrusted.
Source: ADR-0057.R27

R470. Without a QR code, rung 6 gives OCR words; the vision step runs only where the seat is enabled; otherwise a person keys the fields beside the image.
Source: ADR-0057.R27

R471. After verification, `ProposeContactFromExtraction` (module `crm`, effect class `other`, `is_draft_only`, verb Propose at `edit` on `partner`) drafts a change proposal with `CreateContact`, and `CreatePartner` when the person chose a new partner, from the confirmed fields, and links it. The server's duplicate checks on e-mail and phone (ADR-0052.R17) are in its plan. The proposal copies untrusted names, so it is tainted; a person submits it and another approves it (ADR-0043.R9, floor 7).
Source: ADR-0057.R27

### Tuning the duplicate search

R472. The partner duplicate search of ADR-0052.R17 stays the company setting `crm.duplicate_name_threshold`. When `crm` registers `backtest`, `compare` and `monitor` for `crm.find_partner_duplicates`, a company may opt in to tuning by creating its parameter set, seeded from the setting's value, after which the parameter set's value is used. Planning's forecast and exception parameters (ADR-0024) are candidates for their own declarations.
Source: ADR-0059.R8

## Invariants

Statements are those of `invariants.csv`. Each row stands once in the module, in the chunk that states the rule its catalog source names first.

| Invariant | Name | Check point | Statement | Protects |
| --- | --- | --- | --- | --- |
| `INV-502` | `sent_messages_had_consent` | day, first step 5 | Every delivery attempt of an outbound message whose type's purpose needs consent had, for each delivery recipient, a consent basis started at or before `requested_at` and not ended before it. | R422; ADR-0019.R9 |
| `INV-505` | `outbound_closed_iff_sent` | day, first step 5 | An outbound message is closed exactly when one of its delivery attempts has outcome `sent`; a message in `sending` has exactly one attempt without an outcome, and a message in any other state has none. | R413, R425-R427; ADR-0009.R14 |

Named by rules of this chunk, with their rows in other chunks: `INV-504` (R408; catalog source ADR-0052.R7 and ADR-0052.R25), `INV-503` (R406), `INV-500`, `INV-501`, `INV-49` (R449).

## Edge cases

| Edge case | Name | Case | Outcome | Protects |
| --- | --- | --- | --- | --- |
| `EC-89` | `consent_withdrawn_before_send` | A contact withdraws marketing consent after a marketing draft was written; sending it is rejected. | `must_reject:consent_missing` | R422; ADR-0019.R9 |
| `EC-99` | `outbound_outcome_unknown` | A send times out without an answer; the attempt records `unknown` and the message returns to `approved`; an `Update` of the text is refused with `invalid_state_transition`; the next send makes `crm_mail_sender` search the sent folder before it submits, find the message and record `sent` without sending it twice. | `must_reject:invalid_state_transition` for the `Update`; `must_succeed` otherwise | R419, R429, R430 |
| `EC-137` | `business_card_vcard_qr` | A business card photo with a vCard QR code becomes a contact change proposal with duplicate checks on e-mail and phone; the created contact is linked to the extraction. First step 5, event type `contact_card_scanned`. | `must_succeed` | R469, R471 |
| `EC-240` | `quote_request_case_auto` | With `work_case.quote_request.mode` `auto`, a matched customer e-mail opens one case; the tainted quotation run's draft and the later `approval_pending` item join it; a second raise for the same message adds nothing. | `must_succeed` | ADR-0066.R6, ADR-0066.R10 |
| `EC-241` | `quote_request_clean_note_path` | In the same case the salesperson's own note starts an untainted run that configures products; the case shows one tainted and one clean draft, and its taint summary counts one. | `must_succeed` | ADR-0066.R18; ADR-0051.R14 |

Named by rules of this chunk, with their rows in other chunks: `EC-84` to `EC-88`, `EC-90` (catalog source ADR-0052.R24 and ADR-0052.R25), `EC-91`, `EC-100` (R450).

## Settings

None: `settings.csv` holds no row with a `crm.` key.

The rules of this chunk name these settings, which have no row in `settings.csv`: `crm.automatic_send_types` (company setting, a list of `message_type` values, default empty; R424) and `crm.document_intake_xml_timeout_minutes` (minutes, default 60, scope not stated; R215, R457). `crm.duplicate_name_threshold` (R472) is described in chunk 2. `crm.interaction_retention_days` is not registered (R434).

Reads: `work_case.<kind>.mode` (`work`; `EC-240`); `messaging.message_retention_days` (area `work`, company, default 0), one of the existing retention settings that stay beside the retention classes and bound technical stores (ADR-0079.R9).

## UI annotations

The sources state no floorplan, title, facet, field annotation or tile for the module. Work item kinds of module `crm` (`work-item-kinds.csv`); none is agent-resolvable:

| Kind | Subject table | Owner | Due | Resolution | Rule |
| --- | --- | --- | --- | --- | --- |
| `interaction_unmatched` | `interaction` | `role:sales_clerk` | `days:1` | `person` | R14, R229, R233 |
| `inbound_message_matched` | `interaction` | `role:sales_clerk` | `days:1` | `person` | R14, R208, R230, R448 |
| `partner_duplicate_suspected` | `partner` | `role:accountant` | `days:5` | `person` | R240 |
| `data_subject_request_due` | `data_subject_request` | `company_owner` | `subject_due_date` | `person` | R262 |
| `data_subject_request_received` | `data_subject_request` | `company_owner` | `days:1` | `command`: `UpdateDataSubjectRequest` | R262, R448 |
| `complaint_open` | `complaint` | `role:sales_clerk` | `days:2` | `command`: `CloseComplaint` | R250, R448 |
| `follow_up_due` | `interaction` | `subject_assignee:assignee_user_id` | `subject_due_date` | `person`; also superseded by a corrected task or resolved as `erased` | R245, R246, R406, R448 |
| `outbound_message_failed` | `document` | `document_owner` | `same_day` | `system`: when the message closes, is updated back to draft or is canceled | R428, R429, R448 |
| `mailbox_unreachable` | `mailbox` | `subject_owner:owner_user_id` | `same_day` | `system`: the next successful intake | R219, R448 |

`inbound_message_matched` is the trigger of the work case kind `quote_request` (`sales`) (R230). `e_invoice_quarantine_overflow` (R215, R458) is a kind of `tax` with a `mailbox` as subject.

Work case kinds of module `crm` (`work-case-kinds.csv`, registration by ADR-0066.R3): `customer_issue` (trigger `complaint_open`; origin tables `complaint`, `interaction`; `role:sales_clerk`, `days:2`, `person`) and `customer_onboarding` (trigger `interaction_unmatched`; origin table `interaction`; `role:sales_clerk`, `days:1`, `person`).

Authorization leaves of `crm` (`authorization-areas.csv`, ADR-0054.R7): `interaction`, `complaint`, `outbound_message`, `data_subject_request`, `mailbox`, `data_protection`, `partner_insight`.

## Conflicts

CONFLICT ADR-0052.R29: the rule's table labels `identity_proof_hash` internal; the catalog row `data_subject_request_content,identity_proof_hash` of `personal-data-fields.csv` is `personal`, subject kind `requester`, condition `always`, and governs by ADR-0052.R29.N1, stated in R432.
CONFLICT ADR-0052.R32: the rule's table gives no flag to `RecordInboundMessage`, `RecordMailboxIntakeOutcome`, `RecordMailboxAuthenticationCheck`, `RecordOutboundMessageOutcome`, `RecordPartnerTaxLookup`, `RunPartnerDuplicateScan` and `RunPartnerInsightComputation`; ADR-0054.R8.N1 governs and registers them `is_internal_only`, stated in R441.
CONFLICT ADR-0052.R30.N1: the reserved setting `crm.interaction_retention_days` of the rule is not registered; ADR-0052.R30.N1 governs and names the retention class `crm_interaction` of ADR-0079.R9, stated in R434.
CONFLICT ADR-0052.R28: the rule returns every `unknown` attempt to `approved` at once; ADR-0052.R28.N3 governs where the connector can search the sent folder (the message stays in `sending` through the settle delay and the searches), stated in R429.
CONFLICT ADR-0057.R25: the rule lists the purposes `supplier_invoice` and `inquiry_lines`; the DDL constraint `ck_mailbox_document_intake_purpose` also allows `shop_floor_report`, added by ADR-0064.R27, which governs the value list in R456.

## Proposed (not law)

None

## Trace

| Source | Where |
| --- | --- |
| ADR-0052.R25 | R401-R411 |
| ADR-0052.R25.N1 | R409 |
| ADR-0052.R25.N2 | R409 |
| ADR-0052.R25.N3 | R410 |
| ADR-0052.R27 | R412-R419 |
| ADR-0052.R28 | R420-R431 |
| ADR-0052.R28.N1 | R423 |
| ADR-0052.R28.N2 | R423 |
| ADR-0052.R28.N3 | R429 |
| ADR-0052.R29 | R432, R433 |
| ADR-0052.R29.N1 | R432 |
| ADR-0052.R30 | R434, R435 |
| ADR-0052.R30.N1 | R434 |
| ADR-0052.R31 | R436-R439 |
| ADR-0052.R32 | R440-R442 |
| ADR-0052.R33 | R443-R446 |
| ADR-0052.R34 | R447-R453 |
| ADR-0052.R35 | R454 |
| ADR-0052.V.N1 | R455 |
| ADR-0054.R7 | ref: ADR-0054.R7 |
| ADR-0054.R7.N2 | ref: ADR-0054.R7.N2 |
| ADR-0054.R11 | ref: ADR-0054.R11 |
| ADR-0054.R11.N4 | ref: ADR-0054.R11.N4 |
| ADR-0054.R11.N6 | ref: ADR-0054.R11.N6 |
| ADR-0054.R11.N7 | ref: ADR-0054.R11.N7 |
| ADR-0054.R11.N8 | ref: ADR-0054.R11.N8 |
| ADR-0054.R11.N9 | ref: ADR-0054.R11.N9 |
| ADR-0054.R11.N10 | ref: ADR-0054.R11.N10 |
| ADR-0057.R25 | R456-R468 |
| ADR-0057.R27 | R469-R471 |
| ADR-0057.R33 | ref: ADR-0057.R33 |
| ADR-0059.R8 | R472 |
| ADR-0062.R3 | ref: ADR-0062.R3 |
| ADR-0064.R27 | ref: ADR-0064.R27 |
| ADR-0066.R3 | ref: ADR-0066.R3 |
| ADR-0070.R16 | ref: ADR-0070.R16 |
| ADR-0079.R3 | ref: ADR-0079.R3 |
| ADR-0079.R9 | ref: ADR-0079.R9 |
| ADR-0079.R9.N1 | ref: ADR-0079.R9.N1 |
| ADR-0079.R9.N2 | ref: ADR-0079.R9.N2 |
| ADR-0079.R17 | ref: ADR-0079.R17 |
