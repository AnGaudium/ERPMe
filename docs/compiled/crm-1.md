Module: crm    Chunk: 1 of 3    Source ADRs: ADR-0019, ADR-0027, ADR-0029, ADR-0048, ADR-0049, ADR-0052
Build step(s): 1, 2, 4, 5, 8    Generated from index: 30d5706    Compiled by: Claude Fable 5.2, 2026-11-21

# `crm` compiled spec, chunk 1: scope, database conventions, e-mail domains, interactions, foundation rules

## Purpose

`crm` is a layer-4 module (ADR-0022.R2). It owns the tables of `docs/design/DS-35-crm.sql`: partner e-mail domains, mailboxes and inbound messages, interactions, complaints, processing purposes and bases, data subject requests, outbound messages, summaries, insights, tax ID lookups and search keys. Partners, contacts and their commands stay in `master_data`; `audit` owns `personal_data_processing_log`. This chunk states the scope of Phase 1, the database conventions, normalization, the append-only trigger, partner e-mail domains, the `interaction` row, and the foundation rules of ADR-0019 on intake, matching, outgoing messages, the tainted read scope, data protection, tax ID lookup, insights and dunning. The detailed rules of ADR-0052 from rule 8 on are in the other chunks.

## Entities and tables

DDL: `docs/design/DS-35-crm.sql`. It loads after DS-20 and the shared `document` row (R5).

| Table | Meaning | Key | Parent | Owner |
| --- | --- | --- | --- | --- |
| `public_mail_domain` | Global catalog of public mail domains: core rows plus the active package's rows (R8) | `id`; `domain` unique | none (no `company_id`) | `crm` |
| `partner_email_domain` | A domain that the domain step of matching compares for a partner (R8) | `id`; (`partner_id`, `domain`) unique | `partner` | `crm` |
| `interaction` | One event of contact with a partner, append-only except matching and erasure (R9, R10) | `id`; (`company_id`, `id`); (`company_id`, `id`, `partner_id`) | `company`; `partner` and `contact` once matched | `crm` |

Named by the rules of this chunk, with their rows in the chunk that states the rule defining them: `interaction_content`, `interaction_participant`, `interaction_link`, `interaction_match_candidate`, `inbound_message`, `mailbox`, `complaint`, `complaint_document`, `processing_purpose`, `processing_basis`, `data_subject_request`, `data_subject_request_content`, `outbound_message`, `outbound_message_content`, `outbound_message_recipient`, `outbound_message_delivery`, `outbound_message_delivery_recipient`, `interaction_summary`, `partner_insight`, `partner_tax_lookup`, `partner_search_key`.

Reads: `partner`, `contact`, `company`, `user_account` (`master_data`, DS-20); `document`, `document_version` (`documents`); `module_activation` (DS-28); `open_item_collection`, `partner_collection` (`cash`); `personal_data_processing_log`, `audit_change`, `data_erasure_entry` (`audit`); `agent_run_step` (`agent_runs`); the columns `generated_kind`, `generated_audience`, `generated_subject_document_id` of the attachment (`attachments`).

## Commands and queries

Authorization: the function leaf `interaction` of `authorization-areas.csv` (parent `crm`) covers interactions, participants, links, matching, partner e-mail domains, summaries, inbound messages and the partner timeline. Verb levels are the catalog's (`Create`: `edit`; `Update`: `edit`).

| Name | Actor and authorization | Input | Effect | Events | Error codes |
| --- | --- | --- | --- | --- | --- |
| `CreatePartnerEmailDomain` | area `interaction`, level `edit`; effect class `master_data_change`, so agents propose it | partner, `domain` | Writes a `partner_email_domain` row after the checks of R8 | `PartnerEmailDomainCreated` (ADR-0052.R33) | `public_mail_domain`, `validation_failed`; check result `email_domain_shared` |
| `UpdatePartnerEmailDomain` | area `interaction`, level `edit`; effect class `master_data_change`, so agents propose it | the row, `is_active` | Activates or deactivates the row (R8) | `PartnerEmailDomainUpdated` (ADR-0052.R33) | not stated |

Named by the rules of this chunk and stated with their own rules in the other chunks: `GetOutboundContentCheck` (R16, R18; ADR-0052.R27), `ListPartnerTimeline` (R11; ADR-0052.R18), `MatchInteraction` (R14; ADR-0052.R15), `RecordMailboxIntakeOutcome` (R13; ADR-0052.R12), `EraseDataSubject` (R20; ADR-0052.R25), `UpdatePartnerInsight` (R22; ADR-0052.R31), `SendOutboundMessage` (ADR-0052.R27).

Not registered commands of `crm`: the partner e-mail domain hook that `master_data` declares, `crm` registers and `app` wires for `CreatePartner` (R8); `crm`'s consumer of the completion event of `RunDunning` (R23); the commands `RunDunning` (`cash`) and `DestroyRetainedPersonalData` (`audit`) belong to their modules.

Error codes and check results bound to no command of this chunk: `interaction_in_future` (R10), `consent_missing` (R19), `outbound_content_out_of_scope` (R16, R17, R18), `tainted_read_out_of_scope` (R18), `open_item_payment_blocked` (R23, raised by `cash`), `permission_denied` and `record_not_found` (R17).

## Rules

### Scope of Phase 1

R1. DS-35 completes the CRM foundation of ADR-0019 for Phase 1 in the layer-4 module `crm`; it follows the agent runtime of ADR-0050 and the workflows of ADR-0051 and changes neither. What holds across the module:
- **Intake before agents.** Deterministic code records, authenticates and matches every e-mail before any agent sees it. That intake runs as `system`, not as an agent run.
- **Tainted runs draft only.** E-mail content is untrusted, and any agent run that reads it is tainted. A tainted run creates only drafts: outbound message drafts, data subject request drafts and change proposals (the strict reading of spec 03 rule 1, flagged).
- **Proposals.** Everything else an agent wants in the CRM is a change proposal that a person submits and approves: new partners, matches, interactions, tasks, summaries, complaints and consent changes.
- **Timeline.** The timeline returns no untrusted field unless the caller asks for it. The shared `document` row carries the document's partner and date; `crm` composes interactions, complaints and all of a partner's documents through the layer-2 `documents` contract, never imports `sales`, `purchasing` or `cash`, and copies nothing.
- **Personal text outside immutable rows.** The subject and body of an outbound message and the requester data of a data subject request live in `crm` content tables that the header and the version reference by hash; erasure blanks only those rows, so a document in a final state never changes (ADR-0009.R14).
- **Localization overlay** (ADR-0053.R1). Public mail domains of local providers, words removed from names before comparing them, extra letter folds, the phone format, consent purposes and request deadlines are package data of the localization package (`l10n_vn`), flagged until verified. The core holds no country behavior: its name folding is a fixed, language-neutral Latin-to-ASCII table.
Source: ADR-0052.D0

R2. `crm` (layer 4, ADR-0022.R2) owns the tables of `docs/design/DS-35-crm.sql`; the ADRs win if the DDL disagrees.
- **Tables.** Partner e-mail domains (`partner_email_domain`) and the global list of public mail domains (`public_mail_domain`); mailboxes and inbound messages (`mailbox`, `inbound_message`); interactions with their content, participants, links and match candidates (`interaction`, `interaction_content`, `interaction_participant`, `interaction_link`, `interaction_match_candidate`); complaints and their linked documents (`complaint`, `complaint_document`); processing purposes, processing bases, and data subject requests (a document type) with their content (`processing_purpose`, `processing_basis`, `data_subject_request`, `data_subject_request_content`); outbound messages (a document type) with their content, recipients, delivery attempts and delivery recipients (`outbound_message`, `outbound_message_content`, `outbound_message_recipient`, `outbound_message_delivery`, `outbound_message_delivery_recipient`); interaction summaries, partner insights, tax ID lookups and partner search keys (`interaction_summary`, `partner_insight`, `partner_tax_lookup`, `partner_search_key`; R21, R22).
- **Not owned.** `audit` owns `personal_data_processing_log` (ADR-0052.R26). Partners, contacts and their commands stay in `master_data` (DS-20).
- **CRM-only profile.** CRM can run on its own as a deployment profile of the one product, not as an edition (spec 18's one edition holds): the kernel, `master_data` partners and contacts, `crm`, `agents` and `query`, intake, analysis and automation, recorded per company in `module_activation` (`docs/design/DS-28-settings.sql`).
- **Independence.** `crm` never depends on `ledger`, `tax`, `inventory`, `cash` or `production`: the import-linter contract `crm_independent_of_accounting` (ADR-0022.R2) enforces it, and `crm` imports `master_data` for partners and contacts. Partner profiles need no account while `ledger` is not activated (ADR-0015.R11). The timeline of ADR-0052.R18 and the commercial screens leave out the entries and actions of a module that is not activated.
Source: ADR-0052.R1, ADR-0052.R1.N1

R3. Not in Phase 1, so there is no table or command for them now:
- **Leads, prospects, opportunities, pipeline** (R4). A party known only from an e-mail becomes a partner only through the proposal of ADR-0052.R16, with the role it proposes; the approving person decides. A quotation needs the active `customer` role (ADR-0047.R3), so such a party becomes a customer through that proposal first.
- **Marketing automation:** campaigns, lists, bulk sends, unsubscribe links.
- **Appointments:** calendars, invitations and reminders outside the work queue (ADR-0052.R19 has the minimal follow-ups).
- **Channels and search:** chat connectors (Zalo Official Account), semantic search with pgvector, call recording.
Source: ADR-0052.R2, ADR-0052.R2.N1

R4. After Phase 1 come: leads and prospects with a simple pipeline, opportunities, activities and appointments, semantic search with pgvector, chat channels (Zalo Official Account) and call recording. Minimal follow-up tasks as work items are in Phase 1 (ADR-0052.R19, flagged); calendars, recurrence and invitations stay after it.
Source: ADR-0019.R21

### Database conventions, normalization and the append-only trigger

R5. Database conventions are DS-20's:
- **Row-level security.** Every `crm` table carries `company_id`, `FORCE ROW LEVEL SECURITY` and the generated company policy (ADR-0017.R19), except the global catalog `public_mail_domain`. The lab checks the list.
- **Keys.** References inside a company are composite on (`company_id`, `id`).
- **Contact keys.** DS-20's `contact` has `UNIQUE (company_id, id)` and `UNIQUE (company_id, partner_id, id)`. A row that names a partner and a contact then holds both in one key, and the database refuses a contact of another partner. `contact` also has indexes on (`company_id`, `email`) and (`company_id`, `phone`) for matching and duplicate search, `CHECK (email = lower(email))` as the database's half of R6, and the flag `is_accounts_contact` (ADR-0052.R28).
- **Times.** Every row carries `recorded_at` (ADR-0007.R9), including `public_mail_domain`. Rows that erasure blanks carry `erased_at`. Tables whose rows change in place (`mailbox`, `complaint`, the match columns of `interaction`) also carry `version` or a cursor of their own.
- **Order.** The DDL loads top to bottom after DS-20 and the shared `document` row: each table follows the tables it references. The lab checks this.
Source: ADR-0052.R3

R6. Commands normalize what matching compares: DS-20's contact commands (`CreateContact`, `UpdateContact`; ADR-0019.R8; ADR-0045) and the commands of ADR-0052:
- **E-mail addresses** are trimmed and lowercased, with the domain in IDNA ASCII form. An address that does not parse fails with `validation_failed`. DS-20's check on `contact.email` refuses an address that is not lowercase.
- **Phones** are normalized to E.164 by the package's phone rule, with the company's country as default. Like tax ID rules, the rule is flagged until verified (ADR-0019.R4; ADR-0016.R5). Without a package rule, the core accepts only numbers already in E.164 form.
- **Names** are normalized for search as ADR-0052.R17 says.
Source: ADR-0052.R4

R7. Interactions are append-only, and the database holds it. A trigger on `interaction`, `interaction_content`, `interaction_participant`, `inbound_message`, `processing_basis`, the content tables of ADR-0052.R24 and ADR-0052.R27, and the delivery tables of ADR-0052.R28 refuses deletes and refuses changes to any column except:
- columns that change in normal work: the match columns and `version` of an interaction, and `recorded_at` everywhere;
- columns set once from empty: `ended_at` and `end_reason` of a processing basis, a participant's contact, and the outcome columns of a delivery attempt;
- columns that only an erasure command changes: subjects, bodies, addresses, names, the raw `Message-ID`, sender authentication results, failure reasons, requester data, outcome notes, the `content_salt` of content rows, and `erased_at`. The trigger allows them only under a valid `nativeflows.erasure_command_id`, the marker of an erasure command: `EraseDataSubject` (ADR-0038.R4) and `DestroyRetainedPersonalData` (R20). Under ADR-0079.R7 and its notes the marker is set by the erasure scope that each module's consumer opens through `audit.contract`, and `crm_check_append_only` accepts it only when `erasure_marker_valid()` finds the `idempotency_record` whose `id` is the marker, of scope `EraseDataSubject` or `DestroyRetainedPersonalData`, written in the same transaction, of the session's company and of the row's company (ADR-0079.R7.N1, ADR-0079.R7.N2; ADR-0038.R4.N3); even then a column may only take an erasure result of ADR-0079.R6. The scope's binding to the command's subject and due classes, and the writing of erasure records only by `erasure_command_record()`, are `audit` law (ADR-0079.R7, ADR-0079.R7.N3).
- **Draft deletes.** The content tables `outbound_message_content` and `data_subject_request_content` also allow `DELETE`, but only inside the generated `Delete` of their document: the dispatcher alone runs `SET LOCAL nativeflows.document_delete_id` to the document's ID for that command, and the trigger allows the delete only when the setting names the row's document and that document is still a `draft`. As for the erasure gate (ADR-0038.R4), DS-36 checks that an idempotency record of a generated `Delete` command for that document exists in the same transaction. `Delete` itself accepts only a never-submitted, unreferenced draft (ADR-0009.R4), and removes the header, the recipients and then the content rows in the same transaction. Content rows of superseded draft versions are not deleted by `Update`: the versions refer to them, so they stay until erasure, or until destruction under the retention class `crm_interaction` of ADR-0079.R9, set per company by `retention_rule`, which replaces the reserved setting of ADR-0052.R30 (ADR-0052.R30.N1).
- **Processing log.** `personal_data_processing_log` gets a trigger of its own that refuses every update and delete (ADR-0052.R26).
Source: ADR-0052.R7, ADR-0019.R10.N2

### Partner e-mail domains

R8. `partner_email_domain` (partner, `domain`, `is_active`, `erased_at`) holds the domains that the domain step of matching (R14) compares.
- **Form.** Lowercase IDNA ASCII, matched exactly. A subdomain is a row of its own; there are no wildcards. Unique per partner and domain.
- **Public mail domains.** The global catalog `public_mail_domain` (`domain`, `source`: `core` or `package`, `package_code`, `recorded_at`). The core seeds the large free providers, and the active package adds local ones. A domain in the list cannot be a partner's: the command fails with `public_mail_domain`. Matching also skips a listed domain at match time, so a row created before its domain was listed never matches (ADR-0052.R15).
- **Shared domains.** One domain on two active partners (companies of a group) is accepted with the check result `email_domain_shared`. Matching by that domain then never finds exactly one partner.
- **Commands.** `CreatePartnerEmailDomain` and `UpdatePartnerEmailDomain` (activation) have effect class `master_data_change`, so agents propose them (ADR-0029.R2, ADR-0029.R4).
- **From `CreatePartner`.** DS-20's `CreatePartner` takes optional `email_domains`. `master_data` cannot write a `crm` table, so it declares a partner e-mail domain hook that `crm` registers and `app` wires (the hooks of ADR-0022.R2). The hook runs the checks above and writes the rows in the same transaction. The proposal of ADR-0052.R16 uses it.
- **Personal domains.** The domain of an individual partner is personal (ADR-0052.R29); erasure blanks it, sets `erased_at` and deactivates the row (ADR-0052.R25).
Source: ADR-0052.R5

### Interactions and the timeline

R9. An `interaction` is one event of contact with a partner, append-only: `partner_id` (null until matched), `contact_id`, `kind`, `direction`, `occurred_at`, `subject`, `is_untrusted` (true for content from outside, spec 03 rule 1), and its body in `interaction_content`, labeled personal. The values of `kind`, `direction` and `match_method`, and the correction column, are in R10. The mailbox, the provider's message key, the `Message-ID` and the `sender_authentication` results (SPF, DKIM and DMARC for email) live on `inbound_message` (ADR-0052.R13), and related documents are links (ADR-0052.R9), not columns of the interaction. Attachments are stored by the `attachments` module (ADR-0027.R2). A correction is a new interaction that refers to the earlier one; only an erasure command (R20) blanks content. The append-only trigger is R7.
Source: ADR-0019.R12

R10. The `interaction` row:
- **Kinds and directions.** `kind`: `email`, `call`, `meeting`, `chat`, `note`, `task`. `direction`: `inbound`, `outbound`, `internal`. Notes and tasks have `direction` `internal`. The others are `inbound` or `outbound`, by who started the contact. The database checks both.
- **Time.** `occurred_at` is an instant. For an inbound e-mail it is the provider's receive time; for an outbound one, the send time. A call, meeting or chat later than now plus 5 minutes of clock skew fails with `interaction_in_future`, because appointments come after Phase 1.
- **Partner and contact.** Both are empty until the interaction is matched. A contact needs its partner, and the composite key keeps the contact inside that partner.
- **`match_method`.** `reply`, `contact_email` or `domain` for an automatic match of an inbound e-mail (ADR-0052.R15); `entered` when the creator named the partner; `confirmed` after `MatchInteraction`. The database holds that a partner is set exactly when a method and `matched_at` are. `version` counts the match changes.
- **Source fields.** The mailbox, provider key, `Message-ID` and sender authentication live on `inbound_message` (ADR-0052.R13), not on the interaction.
- **`is_untrusted`.** True for every inbound e-mail (a database check) and for any interaction an executed proposal of a tainted agent run created. Then its subject, content, and its participants' addresses and names are untrusted fields (ADR-0029.R10).
- **Corrections.** A correction is a new interaction whose `correction_of_id` names the earlier one.
- **Erasure.** `erased_at` marks an interaction whose subject erasure blanked (ADR-0052.R25).
Source: ADR-0052.R6

R11. The partner timeline is a query (`ListPartnerTimeline`) over interactions and the partner's documents (quotations, orders, invoices, payments) in date order; documents are not copied into interactions (spec 13 principle 2). Sources and layering: ADR-0052.R18.
Source: ADR-0019.R13

### E-mail intake and matching

R12. A `mailbox` is configured per company with an owner (the human on whose behalf intake runs, ADR-0017.R12) and a connector. Intake is a scheduled job with actor `system` on behalf of the mailbox owner, on the `integrations` queue, declared with only the commands that record an inbound interaction and its attachments (ADR-0013.R13; R13). It fetches messages and records each as an inbound, untrusted interaction by command, deduplicated by mailbox and provider key (`provider_message_key`; for IMAP `UIDVALIDITY` and `UID`). A second message with the same `Message-ID` makes no second interaction only when its content hash also matches (ADR-0030.R10): its `inbound_message` row then points to the canonical row and shares its interaction (ADR-0052.R13). Connector, the probe of the receiving server, intake batches, hashes and sender authentication: ADR-0052.R11 to ADR-0052.R14.
Source: ADR-0019.R14

R13. E-mail intake (R12) runs on the `integrations` queue as actor `system`, on behalf of the mailbox owner. Its declared permissions are only the commands that record an inbound interaction and its attachments. Actor `integration` stays reserved for integration clients (ADR-0017.R1). One command batch per message, `RecordMailboxIntakeOutcome`, and intake as deterministic code, not an agent run: ADR-0052.R12.
Source: ADR-0027.R14

R14. Matching is deterministic, and every step requires that the message's sender authentication passes. The steps, in order:
- a reply to an earlier interaction (`In-Reply-To` or `References` naming a message the company sent) whose sender is a stored contact address of that partner or a recipient of the original message;
- the exact email of a contact;
- the partner's email domains (`partner_email_domain`), excluding the public mail domains of `public_mail_domain`, which the core and the active package both list (R8).
A tax ID or name found in the body gives a proposal, never a match. A message that is not matched to exactly one partner goes to a work item (`interaction_unmatched`); an agent may propose a partner with its reason, and a human confirms. No agent run reads partner-scoped data for a message before it is matched this way or confirmed by a human, so outside content never chooses whose data an agent sees (spec 03 rule 1). A message whose sender authentication passed and that is matched to exactly one partner, automatically or by `MatchInteraction`, raises the work item kind `inbound_message_matched` (owner `role:sales_clerk`), which the quotation agent declares (ADR-0051.R14); `inbound_message` is the name of the table only (ADR-0052.R13). Exact steps, the RFC 8601 parser, strict DKIM alignment, candidates and onboarding proposals: ADR-0052.R14 to ADR-0052.R16.
Source: ADR-0019.R15, ADR-0019.R15.N1, ADR-0019.R15.N2

R15. An LLM reads only what deterministic steps leave: the request in free text, item descriptions to map, a summary (spec 14). Its outputs are drafts or proposals stored with their agent run (spec 03 rules 7, 9), never actions.
Source: ADR-0019.R16

### Outgoing messages and the tainted read scope

R16. Outgoing messages are drafts by default; a human sends them, and only message types the company explicitly permits may be sent automatically (spec 13 principle 5).
- **Taint.** A tainted run never triggers an automatic send (ADR-0013.R11).
- **Recipients** are only the partner's stored contact addresses, never addresses taken from an inbound message.
- **Sending** checks the processing basis (R19), records an outbound interaction and runs as an intent consumer (ADR-0013.R10).
- **Content gate.** The gate rejects a customer draft that refers to other partners' records or carries cost or margin fields, with `outbound_content_out_of_scope` (R18). The content check is also the registered query `GetOutboundContentCheck`, evaluated in the plan of every command that creates or updates a customer-facing draft (check result `outbound_content_flagged`); the send still refuses with `outbound_content_out_of_scope` (ADR-0050.R36).
- **Generated files.** A generated file passes the gate in a partner draft only when its attachment has `generated_kind` `print`, `generated_audience` `external`, and a `generated_subject_document_id` whose partner is the message's partner. `crm` reads these columns from the attachment, never from `reporting` (R17).
- **Document type.** Outbound messages are a document type with the state `sending`, content rows and delivery attempts; checks and delivery: ADR-0052.R27, ADR-0052.R28.
Source: ADR-0019.R17, ADR-0019.R17.N1

R17. Escaping, audiences and sending of prints:
- **Untrusted fields** (ADR-0029.R10) are escaped like every field and never rendered as HTML, as ADR-0040.R17 asks of screens.
- **Field classes.** An external template's contract omits every field with a field class, so `cost` and `margin` cannot reach a customer-facing print (R18). An internal template's contract keeps only the field classes it declares; the requester must hold them (`permission_denied`). Record scope applies at request (`record_not_found`). So a stored file never depends on who asked for it.
- **Printing is not sending.** Emailing a PDF is an outbound message draft with the file attached, which a person sends after the consent check (R19, R16).
- **The outbound gate** (module `crm`) accepts a generated file in a partner draft only when the attachment's `generated_kind` is `print`, its `generated_audience` is `external`, and the partner of its `generated_subject_document_id` (`document.partner_id`) is the message's partner; otherwise `outbound_content_out_of_scope`. `crm` reads these columns through `attachments.contract` and the partner through `documents.contract`, never from `reporting`, which is a layer-4 module like `crm`.
Source: ADR-0049.R29

R18. The tainted read scope is the literal spec 03 rule 1: a tainted run reads only records scoped to its related partner. It is not widened, and no setting widens it.
- **Reading.** ADR-0050.R27 reads the literal rule as: scope rows, the run's work item, the drafts it or an earlier run of the same item wrote, and reference data (flagged); it stays as written. Spec 03 rule 1 names this rule as the tainted read scope. ADR-0051.R10 gives the effects on the quotation and purchase invoice workflows.
- **Declared projections.** Declared projections of closed shapes (the first is `ListItemCandidate`) join the reference data of the literal scope; the company setting `agents.tainted_reference_reads` only narrows it back to the literal scope (ADR-0063.R16). A workflow that needs one more read for a tainted run (for example item candidates for matching) gets it only as a declared projection of a registered query (`tainted_projection`: closed shapes, internal names, row and call limits), added by an ADR note for that workflow.
- **One exception to "no setting relaxes a hard floor".** A tainted draft may be auto-posted when the company enables it for the document type and the deterministic checker passes (default off; ADR-0065.R10, ADR-0065.R12). This lets a checked draft post and widens no run's reads.
- **Outbound check.** The outgoing-message gate (R16, module `crm`) rejects a customer draft that refers to another partner's records, or carries `cost` or `margin` fields, with `outbound_content_out_of_scope`. For a generated file the check reads the attachment's `generated_kind`, `generated_audience` and `generated_subject_document_id`: only an external print of a document of the message's partner passes (R17). The check also runs in draft plans through `GetOutboundContentCheck` (ADR-0050.R36).
- **Runs.** Runs on subjects that are outside content start tainted, and after taint no out-of-scope row may enter a prompt or a command input (ADR-0050.R15, ADR-0050.R25).
- **CRM queries.** The CRM's outbound checks, and `tainted_read_out_of_scope` for its timeline and duplicate queries outside the scope partner: ADR-0052.R16, ADR-0052.R18, ADR-0052.R28.
Source: ADR-0029.R14, ADR-0029.R14.N1, ADR-0029.R14.N2, ADR-0029.R14.N3, ADR-0029.R14.N5, ADR-0029.R14.N6

### Data protection

R19. `processing_basis` records the lawful basis per data subject and purpose (spec 13): the data subject (a contact, or a partner that is an individual or a household business, or an employee partner), the purpose (`processing_purpose_id`), `lawful_basis` (`contract`, `legal_obligation`, `consent`), `started_at`, `ended_at` (for consent, the withdrawal), and the interaction that is its evidence (`evidence_interaction_id`). Silence is never consent. Which purposes exist, which need consent, and which message types belong to which purpose are package rules or company configuration, flagged until verified; purposes are company data in `processing_purpose`. A message whose purpose needs consent is not sent without a current basis, a deterministic check returning `consent_missing`. Evidence for consent and agent proposals: ADR-0052.R22, ADR-0052.R23.
Source: ADR-0019.R9

R20. A `data_subject_request` (access, correction, deletion; the data subject; requester details; state; due date) is a document with its own lifecycle (ADR-0009). An inbound email asking for deletion only creates a work item for a human.
- **`EraseDataSubject`** is `human_only`, runs on an approved request and is driven by the personal data catalog: it blocks the subject and destroys at once what a request destroys per retention class (ADR-0079.R9). It erases the subject's personal fields and, for their records, interaction subjects, contents and attachments, summaries, insights, tax lookup snapshots, embeddings and agent run logs, and the requester data of earlier requests once closed, keeping the rows; data on accounting documents is kept for the legal retention period (spec 13).
- **`DestroyRetainedPersonalData`** (`system`, `is_internal_only`, module `audit`) is the second erasure command: when a retention period ends, the retention job runs it for the classes that are due. Both commands use the same catalog-driven hooks, both may blank append-only content (R7), and every rewrite leaves a `data_erasure_entry` (ADR-0079.R4 to ADR-0079.R7).
- **Audit.** Erasure also masks the subject's values in `audit_change` (ADR-0038.R4).
- **Agent run logs.** Erasure blanks the request and response bodies of the `agent_run_step` rows that name the subject (ADR-0050.R20).
- **Document extractions.** The subject's document extractions are found by their partner, by result links to the subject's contact or partner, and by the subject's inbound messages; erasure blanks their field values, evidence and word text. An extraction linked to an incoming e-invoice record or a posted accounting document keeps its accounting fields for the accounting retention (ADR-0057.R19).
- **Open.** Deadlines and processing rules are package rules for the author to verify (open question).
- **Detail.** The subject's rows, the content tables that keep personal text off immutable documents, the request's own data and the scope across modules: ADR-0052.R24, ADR-0052.R25.
Source: ADR-0019.R10, ADR-0019.R10.N1, ADR-0019.R10.N2

### Tax ID lookup, insights and summaries

R21. Tax ID lookup goes through an interface the localization package implements with an authorized provider, never by bypassing a public portal's captcha. A result is stored as a dated snapshot with its source (`partner_tax_lookup`); differences from the partner's fields are proposed as change proposals for a human to accept (ADR-0029.R5; master data changes by agents need approval, spec 14). A lookup on an individual or household business is logged (ADR-0019.R11).
Source: ADR-0019.R18

R22. Anything the system learns about a partner is visible data (spec 03 rule 9): computed insights (`partner_insight`: name, value, method, computed date; e.g. average days between orders, by a deterministic job) and summaries (`interaction_summary`: text, the agent run, its model and prompt version, `is_untrusted` when made from untrusted content, and the human who last edited it). Both can be edited or removed by a human and are erased with the data they come from. `is_untrusted` is a schema attribute separate from data labels, and reading such a field taints a run (ADR-0029.R10). The insight job, `UpdatePartnerInsight`, and agents' summaries as change proposals: ADR-0052.R31.
Source: ADR-0019.R20

### Dunning and complaints

R23. Dunning:
- **Side tables.** `open_item_collection` (open item, `dunning_level`, `last_reminder_date`, `is_payment_blocked`, `is_disputed`, dispute reason) and `partner_collection` (partner, `has_open_complaint`), owned by `cash` (the side table of ADR-0026.R1).
- **`open_item_collection`** has its DDL in `docs/design/DS-05-platform.sql`, section money accounts, statements and payments (owner `cash`): one row per open item that has collection data, keyed by the open item and tied to its company; no row reads as level 0, no reminder, not blocked and not disputed. `is_payment_blocked` needs `payment_block_reason`, `duplicate_review` for ADR-0063.R27 or `manual` (interim), and `is_disputed` needs `dispute_reason`; `dunning_level` is 0 exactly while `last_reminder_date` is empty. `partner_collection` has no DDL yet (DS-25).
- **Payment block.** A settle line of a `cash_payment` or `bank_payment` naming a blocked item is refused with `open_item_payment_blocked` (trigger `trg_payment_line_payment_block`), and `Post` of these types repeats the check, so a block set after the draft holds too; receipts are not held (`INV-98`; lab check `t15_platform_ddl.py` L01 to L05).
- **Complaints.** A `cash` consumer of `crm`'s complaint events (DS-35) sets and clears `has_open_complaint`. `cash` never imports `crm`. The events are `ComplaintCreated`, `ComplaintUpdated`, `ComplaintClosed` and `ComplaintReopened`; on each, the consumer reads the partner's open complaints with `ListComplaint`, so their order does not matter (ADR-0052.R21).
- **`RunDunning` (date).** It proposes reminder drafts per customer, for overdue items that are not blocked or disputed, by levels of days overdue (company setting `cash.dunning.levels`, default 7, 30 and 60). Customers with an open complaint are skipped (spec 13). `GetAllocationProposal` and `RunDunning` skip blocked and disputed items.
- **Sending.** Reminders are outbound message drafts. A person sends them, after the consent check (R19). Interest on late payment comes later. The drafts are `crm` outbound messages, made by `crm`'s consumer of the completion event of `RunDunning`, which carries per customer the level and open item IDs; recipients are the contacts flagged `is_accounts_contact` (ADR-0052.R28).
Source: ADR-0048.R17, ADR-0048.R17.N1

## Invariants

Statements are those of `invariants.csv`. Each row stands once in the module, in the chunk that states the first rule its catalog source names.

| Invariant | Name | Check point | Statement | Protects |
| --- | --- | --- | --- | --- |
| `INV-504` | `erased_rows_blank` | day, first step 5 | Every crm row with `erased_at` has its erasure columns empty: interaction subject, content body, participant address and name, inbound message raw fields and sender authentication, complaint title and note, outbound message content and its `content_salt`, delivery recipient address and failure reason, request requester data, outcome note and `content_salt` (the identity-proof hash stays), personal domain; and no erasure changed a header or version of a document in a final state. | R7; ADR-0052.R25 |
| `INV-98` | `payment_block_held` (area `cash`) | day, first step 6 | No cash or bank payment settles an open item that was blocked for payment when the payment posted: at each posted settle line of a `cash_payment` or `bank_payment`, the change history of the item's `open_item_collection` row shows `is_payment_blocked` false. | R23 |

## Edge cases

| Edge case | Name | Case | Outcome | Protects |
| --- | --- | --- | --- | --- |
| `EC-91` | `shared_domain_unmatched` | A domain belongs to two partners of a group; an authenticated e-mail from a new address at that domain stays unmatched with both as candidates. | `must_succeed` | R8; ADR-0052.R15 |

## Settings

None: the units of this chunk name no setting key that `settings.csv` lists for `crm`.

`cash.dunning.levels` (company setting, default 7, 30 and 60; R23) is named by ADR-0048.R17 and has no row in `settings.csv`.

Reads: `agents.tainted_reference_reads` (area `agents`; enum `literal`, `declared_projections`; scopes company and agent type; core default `declared_projections`), used by R18.

## UI annotations

The sources of this chunk state no floorplan, title, facet, field annotation or tile. Work item kinds that the rules of this chunk raise: `inbound_message_matched` and `interaction_unmatched` (R14); the module's table of work item kinds stands in chunk 3.

## Conflicts

CONFLICT ADR-0019.R9: the column is `lawful_basis` and purposes are company data in `processing_purpose`, as the rule's closing sentence citing ADR-0052.R22 and ADR-0052.R23 and the DS-35 DDL say; R19 states the current columns.
CONFLICT ADR-0019.R10: ADR-0019.R10.N2 (ADR-0079) governs: `EraseDataSubject` is no longer the one command allowed to blank append-only content; `DestroyRetainedPersonalData` is a second erasure command using the same catalog-driven hooks, as R20 states.
CONFLICT ADR-0019.R12: ADR-0052.R6 governs: kind `task` is added, and the mailbox, provider key, `Message-ID` and sender authentication live on `inbound_message`, related documents are links; ADR-0019.R10.N2 makes content blankable by either erasure command, not by `EraseDataSubject` alone; R9 states only what still holds and R10 the row.
CONFLICT ADR-0019.R14: ADR-0052.R13 governs the deduplication: the key is `provider_message_key`, and a second message with the same `Message-ID` and content hash is recorded as an `inbound_message` copy of the canonical row sharing its interaction rather than skipped (R12).
CONFLICT ADR-0019.R15: ADR-0019.R15.N1 and ADR-0019.R15.N2 govern: the work item kind is `inbound_message_matched` with owner `role:sales_clerk`; public mail domains are listed by the core and by the package, as ADR-0052.R5 settles (R8, R14).
CONFLICT ADR-0029.R14: ADR-0029.R14.N6 decides the recommendation to the author: the tainted read scope is not widened, so the recommendation is not restated; ADR-0029.R14.N3 adds the auto-post exception of ADR-0065.R10 to the sentence on hard floors (R18).
CONFLICT ADR-0029.R14.N3: the note supersedes the sentence "no policy, threshold or setting relaxes a hard floor" with one exception, tainted auto-post under ADR-0065.R10; the read scope is unchanged, stated in R18.
CONFLICT ADR-0029.R14.N5: the conflict this note records for the author (the wider wording of decision item 2 of 2026-11-19) is decided by ADR-0029.R14.N6: the wider wording is withdrawn and R18 keeps the scope of ADR-0050.R27.
CONFLICT ADR-0029.R14.N6: the note turns the open recommendation into a decision by the chief architect: scope not widened, further reads only as a declared `tainted_projection`; ADR-0029.R14.N6 governs R18.
CONFLICT ADR-0052.R2: ADR-0052.R2.N1 governs: a quotation needs the active `customer` role (ADR-0047.R3), so "whether a quotation needs the role is DS-22's" is not restated (R3).
CONFLICT ADR-0052.R7: ADR-0019.R10.N2 (ADR-0079) makes `DestroyRetainedPersonalData` a second erasure command using the same hooks, and ADR-0079.R7 with its notes governs the marker: it is valid only for the `idempotency_record` whose `id` is the marker, of scope `EraseDataSubject` or `DestroyRetainedPersonalData`, of the session's company and of the row's company, written in the same transaction (ADR-0079.R7.N1, ADR-0079.R7.N2, ADR-0038.R4.N3), set by each module's consumer through `audit.contract`, not by the dispatcher for `EraseDataSubject` alone; ADR-0052.R30.N1 replaces the retention rule left to the author by the retention class `crm_interaction` (R7).
CONFLICT ADR-0048.R17: ADR-0048.R17.N1 governs the side tables: `open_item_collection` has DDL in DS-05 with `payment_block_reason` and `dispute_reason`, and `partner_collection` still has none (R23).

## Trace

| Source | Where |
| --- | --- |
| ADR-0009.R2 | ref: ADR-0009.R2 |
| ADR-0009.R2.N1 | ref: ADR-0009.R2.N1 |
| ADR-0009.R2.N2 | ref: ADR-0009.R2.N2 |
| ADR-0009.R2.N3 | ref: ADR-0009.R2.N3 |
| ADR-0009.R6 | ref: ADR-0009.R6 |
| ADR-0009.R14 | ref: ADR-0009.R14 |
| ADR-0009.R14.N1 | ref: ADR-0009.R14.N1 |
| ADR-0019.R9 | R19 |
| ADR-0019.R10 | R20 |
| ADR-0019.R10.N1 | R20 |
| ADR-0019.R10.N2 | R7, R20 |
| ADR-0019.R12 | R9 |
| ADR-0019.R13 | R11 |
| ADR-0019.R14 | R12 |
| ADR-0019.R15 | R14 |
| ADR-0019.R15.N1 | R14 |
| ADR-0019.R15.N2 | R14 |
| ADR-0019.R16 | R15 |
| ADR-0019.R17 | R16 |
| ADR-0019.R17.N1 | R16 |
| ADR-0019.R18 | R21 |
| ADR-0019.R20 | R22 |
| ADR-0019.R21 | R4 |
| ADR-0027.R14 | R13 |
| ADR-0029.R10 | ref: ADR-0029.R10 |
| ADR-0029.R10.N1 | ref: ADR-0029.R10.N1 |
| ADR-0029.R10.N2 | ref: ADR-0029.R10.N2 |
| ADR-0029.R14 | R18 |
| ADR-0029.R14.N1 | R18 |
| ADR-0029.R14.N2 | R18 |
| ADR-0029.R14.N3 | R18 |
| ADR-0029.R14.N4 | not applicable: history of the rewording of spec 03 rule 1 (delegated 2026-11-19, applied 2026-11-21) |
| ADR-0029.R14.N5 | R18 |
| ADR-0029.R14.N6 | R18 |
| ADR-0042.R18 | ref: ADR-0042.R18 |
| ADR-0042.R18.N1 | ref: ADR-0042.R18.N1 |
| ADR-0042.R18.N2 | ref: ADR-0042.R18.N2 |
| ADR-0045.R1 | ref: ADR-0045.R1 |
| ADR-0045.R1.N1 | ref: ADR-0045.R1.N1 |
| ADR-0048.R17 | R23 |
| ADR-0048.R17.N1 | R23 |
| ADR-0049.R29 | R17 |
| ADR-0050.R15 | ref: ADR-0050.R15 |
| ADR-0050.R15.N2 | ref: ADR-0050.R15.N2 |
| ADR-0051.R14 | ref: ADR-0051.R14 |
| ADR-0051.R14.N1 | ref: ADR-0051.R14.N1 |
| ADR-0051.R14.N2 | ref: ADR-0051.R14.N2 |
| ADR-0051.R15 | ref: ADR-0051.R15 |
| ADR-0051.R15.N1 | ref: ADR-0051.R15.N1 |
| ADR-0051.R15.N2 | ref: ADR-0051.R15.N2 |
| ADR-0051.R15.N3 | ref: ADR-0051.R15.N3 |
| ADR-0051.R15.N4 | ref: ADR-0051.R15.N4 |
| ADR-0051.R15.N5 | ref: ADR-0051.R15.N5 |
| ADR-0051.R30 | ref: ADR-0051.R30 |
| ADR-0051.R30.N1 | ref: ADR-0051.R30.N1 |
| ADR-0051.R30.N2 | ref: ADR-0051.R30.N2 |
| ADR-0051.R30.N3 | ref: ADR-0051.R30.N3 |
| ADR-0052.D0 | R1 |
| ADR-0052.R1 | R2 |
| ADR-0052.R1.N1 | R2 |
| ADR-0052.R2 | R3 |
| ADR-0052.R2.N1 | R3 |
| ADR-0052.R3 | R5 |
| ADR-0052.R4 | R6 |
| ADR-0052.R5 | R8 |
| ADR-0052.R6 | R10 |
| ADR-0052.R7 | R7 |
