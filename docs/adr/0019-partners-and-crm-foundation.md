# ADR-0019: Partners, contacts and CRM foundation

Status: accepted (2026-11-14) under ADR-0005, reviewed by Claude Fable 5.2. Design items: DS-20 (partner part) and DS-35 (minimal CRM), drafted ahead of steps 2 and 5. Related decisions: D2, D5, D12, D16. Principles 1, 3, 6, 7, 8, 9, 12, 13. ADR-0004, ADR-0005, ADR-0008, ADR-0009, ADR-0010, ADR-0013, ADR-0014, ADR-0015, ADR-0016, ADR-0017, ADR-0018.

## Decision

A partner is one record per company for every party the company deals with — customer, supplier, employee, lead later — with roles added over time, never converted, so history is never broken ([13](../spec/13-crm.md) principle 1). Data that only one role needs lives in a profile per role. People are contacts of a partner. Personal data is labeled at field level, with labels that depend on the partner's kind where the law does (individuals and household businesses), and anything unknown is treated as personal. The CRM is built for agents first: incoming email and notes become append-only interactions; business documents appear on the partner's timeline through a query, never copied; deterministic code matches emails and detects duplicates before any LLM is asked, and outside content never chooses whose data an agent may read; whatever an agent learns is visible, editable data with its run, never hidden memory; nothing leaves the company without a human or an explicit permission; and the lawful basis of processing and data-subject requests are records, so the Personal Data Protection Law's obligations are executable. Rules that depend on law (tax ID formats, consent purposes, deadlines) are package rules, flagged until verified. Pipelines, opportunities and semantic search come after Phase 1.

### Rules

**Partners and roles**

1. A `partner` belongs to one company and has `code` (unique in the company), `name`, `legal_name`, `partner_kind` (`organization`, `household_business`, `individual`), `tax_id` (normalized, optional), `parent_partner_id` (for a dependent unit, e.g. a supplier's branch), `represents_company_id` (set when the partner is another company of the same installation, for intercompany open items, ADR-0010 rule 14), `country`, `partner_group_id` (ADR-0015 defaults), `partner_tax_group_id` (ADR-0018 rule 16), `preferred_language`, `is_active`. A partner referred to by a document is never deleted; it is deactivated. Note: `household_business` is renamed `sole_proprietorship` (an unincorporated business not registered as an enterprise, whose identifiers are its owner's; `l10n_vn` maps the private enterprise to `organization`), here and wherever this ADR says household business (rules 4, 9, 11, 18); `l10n_vn`'s terminology names it "Hộ kinh doanh" ([ADR-0053](0053-core-neutrality.md) rule 7).

    Note (author's delegation, 2026-11-21; decided by the chief architect): a partner belongs to one company in Phase 1, and so do items and products. The seam for a group is distribution, not shared rows: a group key per record through `external_id_map` with the reserved source system `group` ([ADR-0074](0074-core-data-structure-additions.md) rule 7), and a later command that copies a master and keeps it in step across the companies of one installation.

   Note (S2 open questions, 2026-11-21): the DDL value is the authority: `ck_partner_kind` in DS-20 allows `organization`, `sole_proprietorship` and `individual`, as ADR-0053 rule 7 renames `household_business`. The list above reads accordingly.
2. Roles are rows of `partner_role` (`partner_id`, `role`, `is_active`), with `role` one of `customer`, `supplier`, `employee` in Phase 1 (`lead` and `prospect` after Phase 1, [13](../spec/13-crm.md)). A partner may have no role yet (e.g. a contact's organization). Carriers, customs brokers and banks that invoice the company are suppliers; the tax authority is not a partner (tax payables carry no partner, ADR-0014 rule 10). A role is deactivated, never deleted, once used. Being a customer and a supplier at once is normal and allows netting ([08](../spec/08-l10n-vn.md#minimum-processes-to-operate-for-real)).
3. Profiles hold the data of one role; the role of the document (sales, purchase, employee advance) selects the profile whose accounts and terms it uses:

| Profile | Fields (Phase 1) | Owner of the rules |
| --- | --- | --- |
| `customer_profile` | `receivable_account_id` (ADR-0015 rule 11), `payment_term_id` ([ADR-0026](0026-open-item-core.md) rule 5), `credit_limit` and its currency, `price_list_id`, `salesperson_id`, default `currency`, `minimum_remaining_shelf_life_days` ([ADR-0023](0023-warehouse-management.md) rule 3) | DS-22 (credit limit), DS-25 (terms) |
| `supplier_profile` | `payable_account_id`, `payment_term_id` ([ADR-0026](0026-open-item-core.md) rule 5), `buyer_id`, default `currency` | DS-22, DS-25 |
| `employee_profile` | `user_account_id` (optional), `receivable_account_id` for advances (`receivable_employee_advance`) | DS-25 |

Employees are partners so that advances to them are open items per person (141 in TT99), and so that `salesperson_id` and `buyer_id` (ADR-0014, ADR-0018) refer to partners with the `employee` role. Payroll is not in scope ([09](../spec/09-mvp-scope.md)); whether salaries payable are tracked per employee is an open question.

   `supplier_profile` gains `price_list_id` and a working calendar; `employee_profile` gains `branch_id`, `cost_center_id` and `job_title` ([ADR-0045](0045-master-data-and-price-lists.md) rules 2, 11).

   Note ([ADR-0068](0068-sites-and-core-logistics-payment-master-data.md), 2026-11-21): customer and supplier profiles gain the defaults `payment_method_id`, `delivery_method_id`, `incoterm_code` and `incoterm_place`. All of them are `master_data` references, so the profiles stay free of `cash` and `inventory`.

   Note (S2 findings closure, 2026-11-21): the account fields of `customer_profile` and `supplier_profile` in the table are required only while module `ledger` is activated for the company, so the CRM-only profile holds customers and suppliers without accounts ([ADR-0015](0015-account-determination.md) rule 11 note; INV-38).

4. Tax IDs are normalized and validated by a rule of the localization package (format, check digit, the forms used by organizations, dependent units, household businesses and individuals), flagged `unverified` until the author verifies it (ADR-0016). A second partner with a tax ID that another partner of the company already has, other than its parent or dependent unit, is accepted with the check result `partner_duplicate_suspected` and a work item (rule 19); whether such duplicates should be refused is an open question.

    Note (author's delegation, 2026-11-19): confirmed: a second partner with a tax ID another partner already has is accepted with the `partner_duplicate_suspected` warning and a work item; head offices and their dependent units are exempt.
5. `partner_address` (`kind`: `legal`, `billing`, `delivery`, `other`; address lines; optional `subdivision_code` from the localization package's list of administrative units; postal code; country) and `partner_bank_account` (bank, account number, holder name). The Vietnamese list of administrative units is package data with its basis (for the two-level structure in force since 1 July 2025, verification is the author's, ADR-0016). Documents copy the partner's name, address and tax ID at `Create` and `Update`, as version content ([ADR-0028](0028-document-lifecycle-hardening.md) rule 16; DS-22), so later edits do not change them.

    Note ([ADR-0074](0074-core-data-structure-additions.md), 2026-11-21): besides the sold-to partner's snapshot, a document may carry ship-to, bill-to and payer parties on the sales side and invoicing-party and payee parties on the purchase side, each with its own snapshot; a party not stated is the next one up, and defaults come from `partner_relationship` (ADR-0074 rules 1 to 3). `partner_address` gains `UNIQUE (company_id, partner_id, id)` for the address key.
6. `partner_item` (`partner_id`, `item_id`, the partner's own item code, name and unit, unique on partner and code) stores supplier and customer codes, the stored mappings the purchase invoice agent uses ([14](../spec/14-agent-workflows.md)); a mapping an agent proposes becomes a row only after approval. Supplier purchasing terms live in `supplier_item`, keyed by supplier and item, which may refer to a `partner_item` code ([ADR-0024](0024-planning.md) rule 2). Agent proposals are change proposals ([ADR-0029](0029-proposals-and-agent-safety.md) rules 1–5). The table is in the DS-20 DDL ([ADR-0045](0045-master-data-and-price-lists.md) rule 1).

   Note ([ADR-0056](0056-multiple-units-of-measure.md), 2026-11-15): `partner_item.uom_id` proposes the unit of a line for that partner and item, after the source line and a scanned barcode (rule 13).

**Personal data labels**

7. Labels are declared per schema field (Principle 7, [17](../spec/17-seatmap-data-classification.md)). A field whose label depends on the record declares a registered condition: e.g. partner `name`, `legal_name`, `tax_id`, addresses, phones, emails and bank accounts are `personal` when `partner_kind` is `individual` or `household_business`, and `internal` or `public` otherwise. The LLM gateway (DS-32), event payload checks (ADR-0013 rule 4) and exports evaluate the condition per row; when the kind is unknown, the field is treated as personal. Contact fields and every field of `employee_profile` and of employee partners are always `personal`. Note: the condition reads `individual` or `sole_proprietorship` ([ADR-0053](0053-core-neutrality.md) rule 7).

   The gateway evaluates the label per value and row when it renders a prompt, and removes personal values when the routing switch is on ([ADR-0050](0050-agent-runtime-and-query-layer.md) rules 8–9).

   Note ([ADR-0079](0079-personal-data-protection.md), 2026-11-21): the labels, categories and conditions of every field come from [personal-data-fields.csv](../catalogs/personal-data-fields.csv); the fields named here are an extract of it, and where they disagree the catalog wins (ADR-0079 rules 1-2).

   Note (S2 open questions, 2026-11-21): the condition for personal labels reads `partner_kind` is `individual` or `sole_proprietorship` (the DDL value, ADR-0053 rule 7); the catalog condition `partner_is_person` already uses these values.

**Contacts, processing basis and data subjects**

8. A `contact` is a person at a partner: `partner_id`, `name`, `job_title`, `email`, `phone`, `preferred_language`, `is_active`. A contact belongs to one partner; the same person at two partners is two contacts. Contact commands normalize `email` and `phone`, the database refuses an `email` that is not lowercase, and `is_accounts_contact` marks the contacts that receive payment reminders ([ADR-0052](0052-minimal-crm.md) rules 3, 4, 28).
9. `processing_basis` records the lawful basis per data subject and purpose ([13](../spec/13-crm.md)): the data subject (a contact, or a partner that is an individual or a household business, or an employee partner), `purpose`, `basis` (`contract`, `legal_obligation`, `consent`), `started_at`, `ended_at` (for consent, the withdrawal), and the interaction that is its evidence. Silence is never consent. Which purposes exist, which need consent, and which message types belong to which purpose are package rules or company configuration, flagged until verified; a message whose purpose needs consent is not sent without a current basis, a deterministic check returning `consent_missing`. Purposes as company data, evidence for consent, the column name `lawful_basis` and agent proposals: [ADR-0052](0052-minimal-crm.md) rules 22–23.
10. A `data_subject_request` (access, correction, deletion; the data subject; requester details; state; due date) is a document with its own lifecycle (ADR-0009). An inbound email asking for deletion only creates a work item for a human. `EraseDataSubject` is `human_only` and is the one command allowed to blank append-only content: it erases the subject's personal fields and, for their records, interaction subjects, contents and attachments, summaries, insights, tax lookup snapshots, embeddings and agent run logs, and the requester data of earlier requests once closed, keeping the rows; data on accounting documents is kept for the legal retention period ([13](../spec/13-crm.md)). Deadlines and processing rules are package rules for the author to verify (open question). Erasure also masks the subject's values in `audit_change` ([ADR-0038](0038-audit-and-observability.md) rule 4). The subject's rows, the content tables that keep personal text off immutable documents, the request's own data and the scope across modules: [ADR-0052](0052-minimal-crm.md) rules 24–25.

    Agent run logs: erasure blanks the request and response bodies of the `agent_run_step` rows that name the subject ([ADR-0050](0050-agent-runtime-and-query-layer.md) rule 20).

    Note ([ADR-0057](0057-document-intake-and-extraction.md), 2026-11-15): the subject's document extractions are found by their partner, by result links to the subject's contact or partner, and by the subject's inbound messages; erasure blanks their field values, evidence and word text. An extraction linked to an incoming e-invoice record or a posted accounting document keeps its accounting fields for the accounting retention ([ADR-0057](0057-document-intake-and-extraction.md) rule 19).

    Note ([ADR-0079](0079-personal-data-protection.md), 2026-11-21): `EraseDataSubject` stays `human_only` on an approved request and is driven by the catalog: it blocks the subject and destroys at once what a request destroys per retention class (ADR-0079 rule 9). When a retention period ends, the retention job runs a second command, `DestroyRetainedPersonalData` (`system`, `is_internal_only`, module `audit`), for the classes that are due; both use the same catalog-driven hooks and both are erasure commands. Every rewrite leaves a `data_erasure_entry` (ADR-0079 rules 4-7).
11. A `personal_data_processing_log` records every processing the law asks to log: personal fields sent to an LLM (DS-32; [17](../spec/17-seatmap-data-classification.md) logs this whether the routing switch is on or off), tax ID lookups of individuals and household businesses (rule 18), exports and erasures (DS-36). The breach-notification process and the data-protection role are assigned to DS-40 (open question). Exports and erasures write both an audit record and a log entry ([ADR-0038](0038-audit-and-observability.md) rule 9). The breach notification procedure is DS-40's ([ADR-0038](0038-audit-and-observability.md) rule 9). The log is owned by `audit` ([ADR-0052](0052-minimal-crm.md) rule 26).

    The gateway writes one entry per LLM call that sends personal values, before the call is made ([ADR-0050](0050-agent-runtime-and-query-layer.md) rule 10).

**Interactions and the timeline**

12. An `interaction` is one event of contact with a partner, append-only: `partner_id` (null until matched), `contact_id`, `kind` (`email`, `note`, `call`, `meeting`, `chat`), `direction` (`inbound`, `outbound`, `internal`), `occurred_at`, `subject`, `source` (mailbox and the provider's message UID; the Message-ID header for merging the same message across mailboxes), `sender_authentication` (the SPF, DKIM and DMARC results for email), `is_untrusted` (true for content from outside, [03](../spec/03-agent-safety.md) rule 1), related document IDs, and its body and attachments in `interaction_content`, labeled personal. Attachments are stored by the `attachments` module ([ADR-0027](0027-cross-cutting-ownership.md) rule 2). A correction is a new interaction that refers to the earlier one; only `EraseDataSubject` blanks content. Kind `task`, source fields on `inbound_message`, links and the append-only trigger: [ADR-0052](0052-minimal-crm.md) rules 6–9, 13.
13. The partner timeline is a query (`ListPartnerTimeline`) over interactions and the partner's documents (quotations, orders, invoices, payments) in date order; documents are not copied into interactions ([13](../spec/13-crm.md) principle 2). Sources and layering: [ADR-0052](0052-minimal-crm.md) rule 18.

**Email intake and outgoing messages**

14. A `mailbox` is configured per company with an owner (the human on whose behalf intake runs, ADR-0017 rule 12) and a connector. Intake is a scheduled job with actor `system` on behalf of the mailbox owner, on the `integrations` queue, declared with only the commands that record an inbound interaction and its attachments (ADR-0013 rule 13; [ADR-0027](0027-cross-cutting-ownership.md) rule 14) that fetches messages and records each as an inbound, untrusted interaction by command, deduplicated by mailbox and provider UID. A second message with the same `Message-ID` is skipped only when its content hash also matches ([ADR-0030](0030-commercial-seams-and-imports.md) rule 10). Connector, the probe of the receiving server, intake batches, hashes and sender authentication: [ADR-0052](0052-minimal-crm.md) rules 11–14 (DS-24 is now the e-invoice add-on).
15. Matching is deterministic and every step requires that the message's sender authentication passes: first a reply to an earlier interaction (`In-Reply-To` or `References` naming a message the company sent) whose sender is a stored contact address of that partner or a recipient of the original message, then the exact email of a contact, then the partner's email domains (`partner_email_domain`, excluding public mail domains listed by the core). A tax ID or name found in the body gives a proposal, never a match. A message that is not matched to exactly one partner goes to a work item; an agent may propose a partner with its reason, and a human confirms. No agent run reads partner-scoped data for a message before it is matched this way or confirmed by a human, so outside content never chooses whose data an agent sees ([03](../spec/03-agent-safety.md) rule 1).

    A message matched to exactly one partner raises `inbound_message` (owner `role:sales`), which the quotation agent declares ([ADR-0051](0051-agent-workflows.md) rule 14). Exact steps, the RFC 8601 parser, strict DKIM alignment, candidates and onboarding proposals: [ADR-0052](0052-minimal-crm.md) rules 14–16. The kind is renamed `inbound_message_matched`, raised for authenticated messages matched automatically or by `MatchInteraction` ([ADR-0052](0052-minimal-crm.md) rule 15).

    Note: the owner rule `role:sales` is now `role:sales_clerk` ([ADR-0054](0054-users-roles-and-authorizations.md) rule 11).

    Note (catalog review, 2026-11-15): the work item kind `inbound_message` is now `inbound_message_matched` ([ADR-0052](0052-minimal-crm.md) rule 15); `inbound_message` remains the name of its table there (rule 13).
16. An LLM reads only what deterministic steps leave: the request in free text, item descriptions to map, a summary ([14](../spec/14-agent-workflows.md)). Its outputs are drafts or proposals stored with their agent run ([03](../spec/03-agent-safety.md) rules 7, 9), never actions.
17. Outgoing messages are drafts by default; a human sends them, and only message types the company explicitly permits may be sent automatically ([13](../spec/13-crm.md) principle 5). A tainted run never triggers an automatic send (ADR-0013 rule 11). Recipients are only the partner's stored contact addresses, never addresses taken from an inbound message. Sending checks the processing basis (rule 9), records an outbound interaction and runs as an intent consumer (ADR-0013 rule 10). The gate also rejects a customer draft that refers to other partners' records or carries cost or margin fields, with `outbound_content_out_of_scope` ([ADR-0029](0029-proposals-and-agent-safety.md) rule 14). Outbound messages are a document type with the state `sending`, content rows and delivery attempts; checks and delivery: [ADR-0052](0052-minimal-crm.md) rules 27–28.

    The content check is also the registered query `GetOutboundContentCheck`, evaluated in the plan of every command that creates or updates a customer-facing draft (check result `outbound_content_flagged`); the send still refuses with `outbound_content_out_of_scope` ([ADR-0050](0050-agent-runtime-and-query-layer.md) rule 36).

    Note: a generated file passes the gate in a partner draft only when its attachment has `generated_kind` `print`, `generated_audience` `external`, and a `generated_subject_document_id` whose partner is the message's partner. `crm` reads these columns from the attachment, never from `reporting` ([ADR-0049](0049-statutory-reporting-and-printing.md) rules 28, 29).

**Enrichment, duplicates and insights**

18. Tax ID lookup goes through an interface the localization package implements with an authorized provider, never by bypassing a public portal's captcha ([08](../spec/08-l10n-vn.md#e-invoicing-and-tax)). A result is stored as a dated snapshot with its source; differences from the partner's fields are proposed as an update for a human to accept (master data changes by agents need approval, [14](../spec/14-agent-workflows.md)). A lookup on an individual or household business is logged (rule 11). Differences are proposed as change proposals ([ADR-0029](0029-proposals-and-agent-safety.md) rule 5).
19. Duplicate detection is deterministic: normalized tax ID, normalized email and phone, and name similarity by `pg_trgm` on names with diacritics removed, above a threshold set as company configuration ([14](../spec/14-agent-workflows.md)). A suspected duplicate creates a work item; it is never merged automatically. Interim, flagged: merging is allowed only while the duplicate has no posted documents; otherwise it is deactivated with `superseded_by_partner_id`. Normalized keys, the core fold table, the bounded query and the nightly scan: [ADR-0052](0052-minimal-crm.md) rule 17.
20. Anything the system learns about a partner is visible data ([03](../spec/03-agent-safety.md) rule 9): computed insights (`partner_insight`: name, value, method, computed date; e.g. average days between orders, by a deterministic job) and summaries (`interaction_summary`: text, the agent run, its model and prompt version, `is_untrusted` when made from untrusted content, and the human who last edited it). Both can be edited or removed by a human and are erased with the data they come from. `is_untrusted` is a schema attribute separate from data labels, and reading such a field taints a run ([ADR-0029](0029-proposals-and-agent-safety.md) rule 10). The insight job, `UpdatePartnerInsight`, and agents' summaries as change proposals: [ADR-0052](0052-minimal-crm.md) rule 31.

**Scope**

21. After Phase 1: leads and prospects with a simple pipeline, opportunities, activities and appointments, semantic search with pgvector, chat channels (Zalo Official Account), call recording ([09](../spec/09-mvp-scope.md), [13](../spec/13-crm.md)). Minimal follow-up tasks as work items are in Phase 1 ([ADR-0052](0052-minimal-crm.md) rule 19, flagged); calendars, recurrence and invitations stay after it.

## Context

Partners are needed by step 2 (master data imported by command batches), DS-22 (documents), DS-25 (open items) and the agents of DS-34; the minimal CRM by step 5. Constraints:

- One partner, many roles, no conversion; append-only interaction timeline; semantic search after Phase 1; CRM work in the work queue; a gate on everything sent outside; Personal Data Protection Law 91/2025 (lawful basis per purpose, consent, access/correction/deletion with propagation, processing log, breach notification, data-protection role); tax-ID lookup of individuals is personal-data processing ([13-crm.md](../spec/13-crm.md)). Payroll is not in scope ([09](../spec/09-mvp-scope.md)).
- Deterministic first, LLM last; email attached by address and domain; duplicates by key and similarity score; supplier item mappings; agents need approval to change master data ([14](../spec/14-agent-workflows.md)). No hidden memory; untrusted content limits a run ([03](../spec/03-agent-safety.md)). Field-level data labels; personal default for contacts, employees, emails, household and individual tax IDs and addresses ([17](../spec/17-seatmap-data-classification.md)).
- Earlier ADRs: reconciliation accounts on partners (ADR-0015 rule 11), partner tax group (ADR-0018 rule 16), `on_behalf_of` of intake runs (ADR-0017 rule 12), intents and taint (ADR-0013 rules 10–11), package rules with bases (ADR-0016).
- The author asked for an agentic-first design, not a copy of another system. Practice compared only for the role model: Business One's single business partner ([13](../spec/13-crm.md)), SAP's business partner with roles. Vietnam's two-level administrative units since 1 July 2025 ([Viet Nam News](https://vietnamnews.vn/politics-laws/1720781/viet-nam-sets-two-tier-local-government-system.html)), to be verified as package data.

## Options considered

| Option | For | Against |
| --- | --- | --- |
| One partner with role rows and role profiles (chosen) | No conversion; one history; role data only where needed | Two tables for a partner with one role |
| Separate customer and supplier tables | Familiar | Duplicate records for a partner that is both; no netting without links |
| Employees outside partners | Cleaner HR later | Advances need employee open items like any partner's |
| Copy documents into the timeline | One table to read | Two copies of every document that drift |
| Let the LLM or the message content pick the partner | Less code | Outside content would choose an agent's read scope (hard floor) |
| Agent memory as embeddings or prompts | Easy | Hidden memory, forbidden by spec 03 rule 9; cannot be erased reliably |

## Constraints that come with the decision

- DS-04: error `consent_missing`; check result `partner_duplicate_suspected`; command `EraseDataSubject`.
- DS-14 / ADR-0016: tax ID rules, lookup interface, administrative units, public mail domains, consent purposes, data-subject deadlines as package rules.
- ADR-0015: rule 11 reads the account of the profile the document's role selects.
- DS-15 / ADR-0017: field labels with row conditions; field classes.
- DS-21: partner import through command batches, duplicates as check results.
- DS-22: credit limit, price lists, salespeople and buyers; documents copy name, address and tax ID.
- DS-24: mailbox and messaging connectors, sender authentication. DS-25: payment terms, bank accounts, open items per role.
- DS-29: work items. DS-32: routing by row-conditional labels, processing log of LLM sends, run logs. DS-34: intake, quotation and purchase invoice workflows. DS-36, DS-40: processing log, breach notification, data-protection role.

## Revisit when

- A customer needs one person linked to several partners, or partners shared across companies (open question).
- Lead and opportunity management is built (after Phase 1).

## Documents updated

- [docs/spec/00-reading-guide.md](../spec/00-reading-guide.md): glossary rows for partner kind, partner role, profiles, contact, processing basis, data-subject request, processing log, interaction, mailbox, partner item, partner insight.
- [docs/adr/0015-account-determination.md](0015-account-determination.md): note on rule 11.
- [docs/design/DS-04-command-envelope.md](../design/DS-04-command-envelope.md): error code `consent_missing`.
- [docs/design/backlog.md](../design/backlog.md): DS-20 and DS-35 rows link here.
- [docs/adr/README.md](README.md): index row.
- [docs/open-questions.md](../open-questions.md): data-subject deadlines and processing rules; salaries per employee; refusing duplicate tax IDs; sharing partners across companies; breach notification and data-protection role.
- [docs/runbook/step-log.md](../runbook/step-log.md): entry.
