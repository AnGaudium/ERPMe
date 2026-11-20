# ADR-0079: Personal data protection in the core

Status: proposed (2026-11-21) under ADR-0005 (builder Claude Fable 5.2).
Design items: DS-36 (audit), DS-35 (CRM), DS-15 (access), DS-37 (operations), DS-40 (go-live kit). Related decisions: D12. Principles 7, 12. ADR-0008, ADR-0009, ADR-0013, ADR-0014, ADR-0016, ADR-0017, ADR-0019, ADR-0028, ADR-0038, ADR-0044, ADR-0050, ADR-0052, ADR-0054, ADR-0057, ADR-0060, ADR-0063, ADR-0066, ADR-0073, ADR-0074, ADR-0076, ADR-0077; spec 17.

## Decision

Personal data is protected by one mechanism for the whole core, not only on the path to an LLM. The core provides the mechanism; every period, deadline and legal basis is a package rule (ADR-0016), so the core holds no country's values (ADR-0053).

- **One catalog.** [personal-data-fields.csv](../catalogs/personal-data-fields.csv) lists every column that holds personal data. It is the single source for the access export, blocking and destruction, the LLM gateway labels, masking and the retention job.
- **Block, then destroy.** A data subject whose purpose has ended is *blocked*: hidden from ordinary users and from all new processing, and kept only for the legal retention period. When that period ends, the subject's data is *destroyed* in place, in every store the catalog names, posted documents included. This is the model SAP uses (blocking and information lifecycle management); it lets accounting records stay complete for as long as the law requires and no longer.
- **Destruction reaches immutable stores through one controlled exception.** Posted documents, document versions, the journal, audit rows and logs are rewritten only by the destruction path, column by column as the catalog says, and every rewrite leaves an entry in an erasure log that a restore replays.
- **No per-subject encryption keys in Phase 1.** Stores that cannot be rewritten are limited to backups, and backups expire.

### Rules

**The catalog**

1. `catalogs/personal-data-fields.csv` has one row per column: table, column, subject kind (`partner`, `contact`, `user`, `employee`, `requester`, `other`), category (`identity`, `contact`, `financial`, `online_identifier`, `credential`, `free_text`, `snapshot`), label (`personal` or `sensitive_personal`, spec 17), condition, store class, erasure action and retention class.
   - **Condition.** `always`; `partner_is_person` (the label applies when the row's partner is an individual or a sole proprietorship, or its kind is unknown; ADR-0019 rule 7); or `may_contain` (free text or JSON that may name a person).
   - **Store class.** `master` (a record that changes), `frozen_document` (posted documents, their versions, payments, tax lines), `append_only` (journal, audit, logs, CRM and intake rows) or `expiring` (removed by a retention job or a partition drop).
   - **Erasure action.** `tokenize` (a stable token that identifies nobody), `blank`, `delete_row`, `drop_with_partition`, or `keep` for a hash or ID kept as evidence, with the reason.
   - `catalogs/personal-data-exclusions.csv` lists the columns that look personal by name and are not (a legal entity's name, the company's own bank account), each with a reason.
2. The catalog is the single source.
   - **In the build,** a field's label, category and erasure action are annotations of its Python declaration (ADR-0073), and `generate` writes the catalog from them. Until the declarations exist, the CSV file is the source and step 0 work loads it into the declarations.
   - **`check` fails** when a column whose name matches the personal-name pattern, or whose declaration has a personal label, is in neither file; when a catalog row names no real column; and when a custom field has no `is_personal_data` value (ADR-0074 rule 8). The lab `t31_personal_data.py` runs the same check against the DDL today.
   - **Nothing else decides.** The label tables in ADR-0052 rule 29 and the prose lists of ADR-0019 rule 7, ADR-0038 and ADR-0050 rule 9 are read as extracts of the catalog. Where they disagree, the catalog wins and the disagreement is a defect.
   - **Custom fields.** The keys of `custom_values` whose definition has `is_personal_data` true are catalog members by rule: one catalog row per table with `custom_values` stands for them.
3. What the catalog drives:
   - **LLM gateway.** The labels the gateway strips or routes (ADR-0050 rule 9; D12) are the catalog's labels, with the row condition evaluated per value.
   - **Access export.** `ExportDataSubject` (`human_only`, leaf `data_protection` at `full`) writes every catalog value of one subject, the subject's `processing_basis` rows and its processing log entries into a file that is deleted after 7 days, as `ExportCompanyData` is (ADR-0044 rule 17). It writes an audit record and a processing log entry of kind `export`. Columns with condition `may_contain` are included only from rows that reference the subject.
   - **Blocking and destruction** (rules 4 to 8).
   - **Masking.** Queries, exports and the UI mask a blocked subject's catalog columns (rule 5) and every `sensitive_personal` column (rule 12).
   - **Retention.** The retention job reads the retention class (rule 9).

**Blocking and destruction**

4. A data subject is a partner, a contact or a user account. An employee is a partner (ADR-0019 rule 3). `data_subject_state` holds one row per subject that is no longer active: `blocked` or `destroyed`, with the cause (`request` or `retention`), the dates and the request.
5. **Blocked** means:
   - the subject cannot be named on a new document, interaction, message recipient list or agent run, and is left out of search and of every LLM request, whatever the routing switch says;
   - its catalog columns are masked for everyone who does not hold the capability `read_blocked_personal_data`, in queries, exports, printing and the UI. The capability is held by no role template by default; a company assigns it to the people who answer authorities and auditors;
   - posted documents, open items and the journal stay complete and keep working: a blocked customer's invoice can still be paid, reversed and reported. Amounts, accounts and document numbers are never masked.
6. **Destroyed** means every catalog column of the subject, in every store class, has had its erasure action applied.
   - **Master and CRM stores:** as `EraseDataSubject` does today (ADR-0019 rule 10; ADR-0052 rule 25).
   - **Frozen documents and versions:** the snapshot columns (`partner_name`, `partner_tax_id`, addresses, the party columns of ADR-0074) and the same keys inside `document_version.content` are blanked. The version's stored hash stays as it was and the version is marked erased, so the hash is no longer checked against the content (the rule ADR-0038 rule 4 uses for audit rows).
   - **Journal:** `journal_entry.note` and `journal_line.description` of entries that name the subject as partner are blanked. No amount, account, date or key changes, so every balance and every invariant of the ledger holds.
   - **Audit, proposals, agent run steps, extractions, messages:** blanked as their ADRs say (ADR-0038 rule 4; ADR-0050 rule 20; ADR-0057 rule 19; ADR-0076 rule 10); change proposal payloads and field changes that name the subject are blanked the same way.
   - **Attachments:** links end and bytes are released as ADR-0038 rule 15 says. A file linked to several subjects keeps its bytes until its last link ends.
   - **Derived stores:** search keys and insights are deleted; trigram indexes follow their rows; embeddings do not exist in Phase 1.
7. One command destroys. `EraseDataSubject` becomes the only destruction path and is driven by the catalog.
   - **Before retention ends** it blocks the subject and destroys only what no retention rule covers (CRM text, summaries, insights, agent bodies, search keys). Data in retention classes still running stays, blocked. The request is answered with what was destroyed and what is kept, under which rule and until when.
   - **After retention ends** the retention job (rule 9) runs the same command as `system` for the rest.
   - **The exception.** The dispatcher sets `nativeflows.erasure_command_id` for this command alone (ADR-0038 rule 4). The triggers that refuse changes to posted documents, versions, journal rows and append-only rows allow, under that marker, an update that changes only catalog columns of that table. Any other column, or any other command, is refused as before. Each module owns the erasure hook for its tables (ADR-0022), generated from the catalog.
   - **Evidence.** Every rewrite appends a `data_erasure_entry`: subject, target table and row, column names, action, cause, request, command and time. It holds no values. The entry is also appended to an erasure journal object in the attachment store, outside the database.
8. Stores that cannot be rewritten.
   - **Backups.** A backup is never edited. The backup retention window is at most `attachments.delete_grace_days` (ADR-0038 rule 15), so a destroyed value leaves the last backup within that window. After any restore, and before the system opens, `ReapplyErasures` replays every erasure journal entry later than the restore point (rule 14).
   - **Provider side.** A provider that retained a request is outside the system; the provider registry's `retention_days` and no-training flag (ADR-0063 rule 15) are what the company relies on, and the processing log names what was sent.
   - **Crypto-shredding** (a key per subject, destroyed to erase) is not used in Phase 1. In-place destruction reaches every store the database holds, and it keeps documents readable by SQL, reports and printing. A write-once archive, if one is ever added, must be encrypted with keys that can be destroyed per retention period.

**Retention**

9. `retention_rule` holds, per company and retention class, the start event, the months until blocking and the months until destruction. The classes are `master_data`, `accounting_document`, `crm_interaction`, `message`, `agent_log`, `intake`, `audit`, `access_account`, `analysis_text` and `data_subject_request`.
   - **Periods are package rules.** A localization package supplies the rules of its regime, each flagged verified or unverified (ADR-0016 rule 12). The core seeds none. A company may shorten or lengthen a period only where the package marks it adjustable.
   - **No rule, no destruction.** Where a class has no verified rule, the job neither blocks nor destroys for that class, and `check` and the operations dashboard report the class as without a retention rule. Keeping too long is reported; destroying too early cannot be undone.
   - **The job.** `RunPersonalDataRetention` runs daily as `system` on queue `jobs`. For each subject it computes the start event per class (for example the posting date of the last document that names the partner), blocks a subject whose purpose has ended, and destroys per class when the class's period has ended. A subject with an open item, an open document, an open data subject request or an open dispute is never blocked by the job.
   - **Evidence** is the `data_erasure_entry` rows and one processing log entry of kind `retention` per subject and run.
   - **Existing retention settings stay** (`messaging.message_retention_days`, the analysis question retention, the agent run step retention). They bound technical stores and may be shorter than a retention rule; where both apply, the shorter wins for stores that are not accounting evidence.

**Reading**

10. Personal columns are read under the record scope and leaves a role already has (ADR-0054). No new field class covers ordinary personal data: a sales clerk must read a customer's name.
11. `sensitive_personal` is a field class beside `cost` and `margin` (ADR-0017 rule 10). A column with that label is returned only to an assignment that holds the class. No role template holds it by default, and no Phase 1 column carries it; the class exists so that a package or a custom field can use it without a schema change.
12. Reads that are logged. `personal_data_read_log` gets one row, with query name, user, field names and row count and no values, for:
    - every read that returns a `sensitive_personal` column;
    - every read of a blocked subject's unmasked data;
    - every `ExportDataSubject`, `ExportCompanyData` and list export that includes a personal column (ADR-0044; ADR-0050).
    Ordinary reads of personal columns are not logged: the record of who may read is the role assignment, and logging every read of a customer name would bury the reads that matter. The log is append-only and is kept as audit rows are (ADR-0038 rule 6).

**Encryption and restore**

13. Encryption is a property of the deployment that `nativeflows-ops check` verifies before go-live (DS-37):
    - the database volume, the attachment store and the backup repository are encrypted at rest;
    - backups are encrypted by the backup tool with a key held in the deployment's secret store, never in the repository or beside the backups;
    - connections are TLS;
    - secrets in the database (`totp_secret`, integration credentials) stay encrypted at column level under a key from the secret store (ADR-0054).
    The core does not encrypt business columns: PostgreSQL must be able to index, join and constrain them.
14. Restore. A restore runs with triggers disabled (ADR-0014). Before the restored system accepts a command, `ReapplyErasures` reads the erasure journal (rule 7) and applies every entry later than the restore point, then writes one audit record. The restore runbook (S7; DS-37) makes this a step that cannot be skipped: the application refuses to start while the journal holds entries the database does not.

**Breach handling**

15. Signals. These raise the work item `personal_data_incident_suspected`, owned by the holder of the `data_protection` leaf at `full`:
    - a canary value seen in a request, log or span (ADR-0050 rule 11);
    - more than a set number of denials for one actor in an hour (ADR-0038 rule 5);
    - an export, or a run of reads in `personal_data_read_log`, above a set row count by one actor in a day;
    - an integration token used after revocation or from outside its allowed company;
    - an `llm_routing_refused` caused by a personal value while the routing switch is on.
    The thresholds are installation settings added with DS-37; until then the signals are raised by people.
16. A breach is handled as a work case of kind `personal_data_breach`, opened by a person from the work item or directly. `personal_data_breach` holds what an authority asks for: when it was discovered and when it happened, the catalog categories and subject kinds involved, the estimated number of subjects, the containment, and when the authority and the subjects were notified.
    - **Steps:** assess, contain, record, notify, close. The case cannot be resolved while the notification fields a package rule requires are empty.
    - **Deadlines** are package rules (`breach_notification_hours` per regime). The core computes `notification_due_at` from the rule and raises the due date on the case; with no rule the due date is empty and the case says so.
    - **Evidence** is the audit records, denials, the read log and the processing log (ADR-0038 rule 9).

**Scope**

17. Not in Phase 1: pseudonymization before sending to a cloud model (spec 17, after Phase 1); a consent-management UI beyond `processing_basis` (ADR-0019 rule 9); masking of a production copy for a sandbox; per-subject encryption keys.

## Context

The author asked for privacy by design across the whole core (session S1, item 3b). The inventory of 2026-11-21 found the pieces designed for the AI path and for CRM, and found the rest missing:

- **No single source.** About 300 columns in about 100 tables can hold personal data; 16 carry a marker. Labels live in prose, in one table of ADR-0052 and in SQL comments.
- **Posted documents have no path.** ADR-0019 rule 10 and ADR-0052 rule 25 say sales, purchasing and cash erase their own data, but posted headers and versions are immutable and no exception exists for them. Sixteen document headers, payments and tax lines hold a partner's name, tax ID and address.
- **No retention schedule.** Retention exists for five technical stores; no rule says when a customer's or an employee's data must go.
- **No read control or read log** for sensitive data; queries write no audit record (ADR-0038 rule 1).
- **Encryption and restore are not stated,** and a restore would bring erased rows back.
- **Breach handling** was assigned to DS-40 with no mechanism.

## Options considered

| Option | For | Against |
| --- | --- | --- |
| Block, then destroy in place, driven by a catalog (chosen) | Accounting stays complete during retention; one path reaches every store; documents stay readable by SQL; the model auditors know from SAP | Triggers on immutable stores need one exception; the catalog must be kept complete, so `check` enforces it |
| Crypto-shredding: personal values encrypted under a key per subject | Reaches backups and any write-once store at once | Every document header, version and audit image becomes ciphertext: no SQL search, constraints or reports on them; key management per subject; much harder for coding agents |
| Move snapshots to a side table that documents reference | One place to erase | Restructures 16 document headers and the plan hash; a document no longer carries its own content (ADR-0028 rule 5) |
| Delete on request, keep nothing | Simple | Breaks legal retention of accounting records |
| A field class for all personal data | Uniform read control | Every role would need it to work; it would protect nothing |

## Constraints that come with the decision

- The triggers of posted documents, versions, the journal and append-only rows gain the erasure exception of rule 7, limited to catalog columns. The DDL change is made with the ledger and document DDL in session S2.
- `check` enforces the catalog (rule 2). A new column with a personal name pattern fails the build until it is in the catalog or the exclusions.
- No handler other than `EraseDataSubject` and `ReapplyErasures` writes under the erasure marker.
- The lab `t31_personal_data.py` loads the new tables and checks the catalog against the DDL.

## Revisit when

- A regime requires destruction of personal data on posted accounting documents before their retention period ends.
- A write-once archive or an analytics copy outside the database is added: decide per-period keys before it holds data.
- The read log grows by more than 1,000,000 rows a month in one company: log by sample or by session.

## Documents updated

- **Catalogs:** [personal-data-fields.csv](../catalogs/personal-data-fields.csv) and [personal-data-exclusions.csv](../catalogs/personal-data-exclusions.csv) (new); [work-case-kinds.csv](../catalogs/work-case-kinds.csv) (`personal_data_breach`); [work-item-kinds.csv](../catalogs/work-item-kinds.csv) (`personal_data_incident_suspected`); [invariants.csv](../catalogs/invariants.csv) (INV-890 to INV-894); [edge-cases.csv](../catalogs/edge-cases.csv) (EC-350 to EC-354).
- **Design:** [DS-64-personal-data.sql](../design/DS-64-personal-data.sql) (new): `data_subject_state`, `retention_rule`, `data_erasure_entry`, `personal_data_read_log`, `personal_data_breach`; the field class `sensitive_personal` in DS-15, DS-20 and DS-05.
- **ADR notes:** ADR-0017 rule 10; ADR-0019 rules 7 and 10; ADR-0038 rules 1, 4 and 9; ADR-0044 rule 17; ADR-0050 rule 9; ADR-0052 rules 25 and 29; ADR-0074 rule 8.
- **Lab:** `t31_personal_data.py` (new).
- **Open questions, backlog, index:** [docs/open-questions.md](../open-questions.md), [backlog.md](../design/backlog.md) (DS-64; DS-37 and DS-40 notes), [docs/adr/README.md](README.md).

## Edge cases and invariants

- **INV-890** `personal_data_catalog_complete`: every column matching the personal-name pattern or declared with a personal label is in the catalog or the exclusions; every catalog row names a real column.
- **INV-891** `blocked_subject_not_processed`: no document, interaction, outbound message or agent run created after a subject's `blocked_at` names that subject.
- **INV-892** `destroyed_subject_is_blank`: for a subject in state `destroyed`, every catalog column of its rows holds the erasure action's result, and a `data_erasure_entry` exists for each rewritten row.
- **INV-893** `erasure_changes_catalog_columns_only`: a row of a frozen or append-only table differs from its state before an erasure only in catalog columns; ledger balances before and after are equal.
- **INV-894** `no_destruction_without_rule`: every `data_erasure_entry` with cause `retention` falls after the destruction date of a verified `retention_rule` of its class.
- **EC-350** `erasure_request_during_retention`: a customer with posted invoices asks for erasure; CRM text is destroyed, the subject is blocked, the invoices stay and can be paid and reversed.
- **EC-351** `destruction_after_retention`: the retention period of that customer ends; the job blanks the snapshots on the invoices and their versions; the trial balance is unchanged.
- **EC-352** `restore_before_erasure`: the database is restored to a point before a destruction; `ReapplyErasures` blanks the same rows before the system opens.
- **EC-353** `blocked_subject_refused`: a new sales order for a blocked customer is refused; a payment for its open invoice posts.
- **EC-354** `class_without_rule`: a company whose package has no verified rule for `crm_interaction`; the job destroys nothing of that class and reports it.
