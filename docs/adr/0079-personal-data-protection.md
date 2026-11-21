# ADR-0079: Personal data protection in the core

Status: accepted (2026-11-21) under ADR-0005, reviewed by Claude Opus 5.5 after three review rounds (builder Claude Fable 5.2, with the DDL, catalog and lab built by Claude Opus 5.5 and Claude Sonnet 5.5).
Design items: DS-64 (personal data), DS-36 (audit), DS-35 (CRM), DS-15 (access), DS-37 (operations), DS-40 (go-live kit). Related decisions: D12. Principles 7, 12. ADR-0008, ADR-0009, ADR-0013, ADR-0014, ADR-0016, ADR-0017, ADR-0019, ADR-0028, ADR-0038, ADR-0044, ADR-0050, ADR-0052, ADR-0054, ADR-0057, ADR-0060, ADR-0063, ADR-0066, ADR-0073, ADR-0074, ADR-0076, ADR-0077; spec 17.

## Decision

Personal data is protected by one mechanism for the whole core, not only on the path to an LLM. The core provides the mechanism; every period, deadline and legal basis is a package rule (ADR-0016), so the core holds no country's values (ADR-0053).

Note (author, 2026-11-21): retention periods and the breach notification deadline are set per company, with package defaults; see the notes at rules 9 and 16.

- **One catalog.** [personal-data-fields.csv](../catalogs/personal-data-fields.csv) lists every column that holds personal data. It is the single source for the access export, blocking and destruction, the LLM gateway labels, masking and the retention job.
- **Block, then destroy.** A data subject whose purpose has ended is *blocked*: hidden from ordinary users and from all new processing, and kept only for the legal retention period. When that period ends, the subject's data is *destroyed* in place, in every store the catalog names, posted documents included. This is the model SAP uses (blocking and information lifecycle management); it lets accounting records stay complete for as long as the law requires and no longer.
- **Destruction reaches immutable stores through one controlled exception.** Posted documents, document versions, the journal, audit rows and logs are rewritten only by the destruction path (`EraseDataSubject` on a request, `DestroyRetainedPersonalData` when a retention period ends), column by column as the catalog says, and every rewrite leaves an entry in an erasure journal that a restore re-applies.
- **No per-subject encryption keys in Phase 1.** Stores that cannot be rewritten are limited to backups, and backups expire.

### Rules

**The catalog**

1. `catalogs/personal-data-fields.csv` has one row per column: table, column, subject kind (`partner`, `contact`, `user`, `employee`, `requester`, `other`), category (`identity`, `contact`, `financial`, `online_identifier`, `credential`, `free_text`, `snapshot`), label (`personal` or `sensitive_personal`, spec 17), condition, store class, erasure action and retention class.
   - **Condition.** `always`; `partner_is_person` (the label applies when the row's partner is an individual or a sole proprietorship, or its kind is unknown; ADR-0019 rule 7); or `may_contain` (free text or JSON that may name a person).
   - **Store class.** `master` (a record that changes), `frozen_document` (posted documents, their versions, payments, tax lines), `append_only` (journal, audit, logs, CRM and intake rows) or `expiring` (removed by a retention job or a partition drop).
   - **Erasure action.** `tokenize` (a stable token, unique per row, that identifies nobody), `blank`, `clear_keys`, `delete_row`, `drop_with_partition`, or `keep` for a hash or ID kept as evidence, with the reason.
   - **`blank`** sets NULL only where the column is nullable and no CHECK ties its nullness to another column or flag; otherwise it sets the marker of the column's type: `''` for text, `{}` for an array column, `[]` for a JSON column a CHECK types as an array and `{}` for any other JSON column. The erasure flag the destruction path sets in the same update (`erased_at`, `body_removed_at`) does not count as a tie: a CHECK that asks for NULL once that flag is set gets NULL. Where a CHECK refuses both NULL and the marker (for example `coalesce(length(btrim(x)), 0) > 0` under a condition the row meets), the action is `tokenize`. A column inside a primary key, a UNIQUE constraint or a unique index is never blanked: it is tokenized, or its row is deleted. A `blank` row whose result is a marker says so in its note ("blank gives the marker ...").
   - **`clear_keys`** removes named keys from a JSON column and leaves the others. The row's note names the keys: for `custom_values`, the keys whose `custom_field_definition` has `is_personal_data` true; for `document_version.content`, the keys that mirror the header's and lines' catalog columns and those `custom_values` keys; for `posting_intent.plan`, the note and description keys of its entries and lines.
   - `catalogs/personal-data-exclusions.csv` lists the columns that match the personal-name pattern of rule 2 and hold no personal data (a legal entity's name, the company's own bank account, a code from a closed list), each with a reason. A row with column `*` excludes a whole table; its reason starts with the pattern-matching columns it covers (`covers: name; <reason>`), so a matching column added to the table later fails `check` until it is listed or catalogued. It is used only for code and configuration tables that have no person-related column.
2. The catalog is the single source.
   - **In the build,** a field's label, category and erasure action are annotations of its Python declaration (ADR-0073), and `generate` writes the catalog from them. Until the declarations exist, the CSV file is the source and step 0 work loads it into the declarations.
   - **The personal-name pattern** matches column names with a personal word (`email`, `phone`, `address`, `tax_id`, `account_number`, `holder_name`, `display_name`, `login`, `counterparty`, `sender_`, `recipient`, `partner_name`, `contact_name`, `*_name_text`, `custom_values`, `body`, `request_text`, `question_text`, `signature`), and names with a free-text word (`note`, `comment`, `remark`, `description`, `reason`) or a name column (`name`, `*_name`), except reference and code columns (names ending in `_id`, `_ids`, `_kind` or `_code`). On 2026-11-21 the catalog has 270 rows in 109 tables, and the exclusions 83 columns and 47 whole tables.
   - **`check` fails** when a column that matches the pattern, or whose declaration has a personal label, is in neither file or in both; when a catalog row names no real column; when a `blank` row names a column of a unique key or a column whose CHECKs refuse both NULL and the marker; when a table excluded with `*` has a matching column outside its covers list; and when a custom field has no `is_personal_data` value (ADR-0074 rule 8; the column has no default, so the command must state it). The lab `t31_personal_data.py` runs the same check against the DDL today.
   - **Nothing else decides.** The label tables in ADR-0052 rule 29 and the prose lists of ADR-0019 rule 7, ADR-0038 and ADR-0050 rule 9 are read as extracts of the catalog. Where they disagree, the catalog wins and the disagreement is a defect.
   - **Custom fields.** The keys of `custom_values` whose definition has `is_personal_data` true are catalog members by rule: one catalog row per table with `custom_values`, with action `clear_keys`, stands for them.
3. What the catalog drives:
   - **LLM gateway.** The labels the gateway strips or routes (ADR-0050 rule 9; D12) are the catalog's labels, with the row condition evaluated per value.
   - **Access export.** `ExportDataSubject` (`human_only`, leaf `data_protection` at `full`) writes every catalog value of one subject, the subject's `processing_basis` rows and its processing log entries into a file that is deleted after 7 days, as `ExportCompanyData` is (ADR-0044 rule 17). It writes an audit record and a processing log entry of kind `export`. Columns with condition `may_contain` are included only from rows that reference the subject. Columns of subject kind `other` are included only when the requester is that person and a person adds them.
   - **Blocking and destruction** (rules 4 to 8).
   - **Masking.** Lists, searches, exports and the UI mask a blocked subject's catalog columns (rule 5) and every `sensitive_personal` column (rule 11).
   - **Retention.** The retention job reads the retention class (rule 9).

**Blocking and destruction**

4. A data subject is a partner, a contact or a user account. An employee is a partner with the role `employee` (ADR-0019 rules 2 and 3). `data_subject_state` holds one row per subject that is or was blocked: `blocked`, `released` or `destroyed`, with the cause (`request` or `retention`), the dates and the request document. A later block updates the same row.
   - Columns of subject kind `requester` and `other` belong to no data subject record and are not reached through `data_subject_state`. `requester` columns (the requester details of a data subject request) follow the request's retention class. `other` columns (named officers on a print profile) are changed by editing the record.
5. **Blocked** means:
   - the subject cannot be named on a new document, interaction, message recipient list or agent run, and is left out of search and of every LLM request, whatever the routing switch says. The one exception is a follow-on document of an existing document of the same subject: a payment or clearing of its open item, a reversal (`reversal_of_id`), a correction (`correction_of_id`: credit and debit notes), and a return that references its delivery or receipt lines. Everything else is refused with `data_subject_blocked`;
   - its catalog columns are masked in lists, searches, exports and the UI for everyone who does not hold the capability `read_blocked_personal_data`. Statutory reports and prints of posted documents (ADR-0049) are not masked: they are the legal purpose the data is kept for. The capability is the leaf `blocked_personal_data`; the `owner` template holds it at `full`, like every capability, and grants it to the people who answer authorities and auditors (ADR-0017 rule 6); no other template holds it; every read under it is logged (rule 12);
   - posted documents, open items and the journal stay complete and keep working: a blocked customer's invoice can still be paid, reversed, corrected and reported. Amounts, accounts and document numbers are never masked.
   - **Release.** `ReleaseDataSubject` (`human_only`, leaf `data_protection` at `full`, module `audit`) releases a block made in error or for a returning customer, only from `blocked`, with a reason; it writes an audit record. A destroyed subject is never released.
6. **Destroyed** means every catalog column of the subject, in every store class, has had its erasure action applied. Each module's hook sets its table's erasure flag (`erased_at`, `body_removed_at`), where the table has one, in the same update.
   - **Master and CRM stores:** as `EraseDataSubject` does today (ADR-0019 rule 10; ADR-0052 rule 25).
   - **Frozen documents and versions:** the snapshot columns (`partner_name`, `partner_tax_id`, addresses, the party columns of ADR-0074) are blanked and the catalog keys of `document_version.content` are cleared (`clear_keys`). The version's stored `version_hash` stays as it was and the version's `erased_at` (DS-05) is set, so the hash is no longer checked against the content (as ADR-0038 rule 4 marks erased audit rows with `erased_at`; INV-10 skips such versions).
   - **Journal:** `journal_entry.note` and `journal_line.description` of entries that name the subject as partner are blanked. No amount, account, date or key changes, so every balance and every invariant of the ledger holds.
   - **Audit, proposals, agent run steps, extractions, messages:** blanked as their ADRs say (ADR-0038 rule 4; ADR-0050 rule 20; ADR-0057 rule 19; ADR-0076 rule 10); change proposal payloads and field changes that name the subject are blanked the same way.
   - **Attachments:** links end and bytes are released as ADR-0038 rule 15 says. A file linked to several subjects keeps its bytes until its last link ends.
   - **Derived stores:** search keys and insights are deleted; trigram indexes follow their rows; embeddings do not exist in Phase 1.
7. Two commands destroy, through one path driven by the catalog.
   - **`EraseDataSubject`** stays as ADR-0019 rule 10 and ADR-0052 rule 25 define it: `human_only`, run by a person on an approved deletion request. It blocks the subject and destroys at once what rule 9 says a request destroys. Data of classes a request does not destroy stays, blocked. The request is answered with what was destroyed and what is kept, under which rule and until when, or "no retention rule yet".
   - **`DestroyRetainedPersonalData`** (`system`, `is_internal_only`, module `audit`) is run by the retention job (rule 9). It takes a subject and the retention classes whose period has ended under a verified rule, and destroys those classes' columns.
   - **One path, per module.** Each command emits an event that carries only IDs: `EraseDataSubject` emits `DataSubjectErased` (ADR-0052 rule 25); `DestroyRetainedPersonalData` emits `PersonalDataDestructionDue` with the due classes; `audit.contract` emits `DataErasureRecorded` per entry for the erasure journal writer (Evidence below) (a separate event, so that each event has one owning module). Each module destroys its own tables in its consumer of these events, in the consumer's own transaction, with the hook generated from the catalog. The consumer opens an erasure scope through `audit.contract` with the originating command's ID. `audit.contract` binds the scope to that command's subject and, for `DestroyRetainedPersonalData`, its due classes: a consumer cannot rewrite rows of another subject or of another class under that command's ID. No module imports a peer (ADR-0022).
   - **The exception.** The erasure scope sets `nativeflows.erasure_command_id` (ADR-0038 rule 4). The triggers that refuse changes to posted documents, versions, journal rows and append-only rows allow, under that marker, an update that changes only catalog columns of that table, and accept the marker only when a committed `EraseDataSubject` or `DestroyRetainedPersonalData` with that ID exists. Any other column, or any other command, is refused as before.
   - **Evidence.** Every rewrite appends a `data_erasure_entry`: subject, target table and row key (the row's primary key, which for tables without an `id` is several columns), column names, action, cause, request, command and time. It holds no values. `audit.contract`'s insert of an entry emits the IDs-only event `DataErasureRecorded` in the same transaction; after commit, its consumer, the erasure journal writer, appends one line per entry to the erasure journal: an object of its own under a prefix of the object store that the attachment orphan sweep never touches (it is not an attachment). A line holds every column of its entry (id, subject, target table, row key, column names, action, cause, request, command and time) and no values, so a restore can re-insert the entry and apply it. Delivery is at least once; appending an `id` twice is harmless.

    Note (S2 findings closure, 2026-11-21): the exception is in the DDL. `erasure_update_allowed()` ([DS-05](../design/DS-05-platform.sql)) returns true only under the marker, when every changed column is a catalog column that the trigger passes as an argument, or the erasure flag (`erased_at`, `body_removed_at`) set from null; it never allows a delete. The refusing triggers of `document`, `document_version`, `payment`, `payment_line`, `tax_line`, change proposals, period unlock requests, `journal_entry` (`note`), `journal_line` (`description`) and the append-only `approval`, `artifact_transition`, `automation_execution`, `setting_value`, `taint_clearance` and `work_item_note` pass their catalog columns; the generated trigger of the DS-22 headers and lines passes them as the second argument of `document_check_frozen`. The lists are generated from the catalog, and lab t31 checks them against it. The check that the marker names a committed `EraseDataSubject` or `DestroyRetainedPersonalData` is written with the idempotency records (no DDL yet), as for the existing erasure lists; until then the triggers test the marker's presence. The five append-only tables with guard functions of their own (`analysis_example`, `company_setup_acknowledgement`, `document_extraction`, `posting_intent`, `saved_analysis_version`) get the same argument when those functions are next changed.

8. Stores that cannot be rewritten.
   - **Backups.** A backup is never edited. The backup retention window is at most `attachments.delete_grace_days` (ADR-0038 rule 15), so a destroyed value leaves the last backup within that window. After any restore, and before the system opens, `ReapplyErasures` re-applies the erasures the restored database lacks (rule 14).
   - **Provider side.** A provider that retained a request is outside the system; the provider registry's `retention_days` and no-training flag (ADR-0063 rule 14) are what the company relies on, and the processing log names what was sent.
   - **Crypto-shredding** (a key per subject, destroyed to erase) is not used in Phase 1. In-place destruction reaches every store the database holds, and it keeps documents readable by SQL, reports and printing. A write-once archive, if one is ever added, must be encrypted with keys that can be destroyed per retention period.

**Retention**

9. `retention_rule` holds, per company and retention class, the start event, the months until blocking and the months until destruction. The classes are `master_data`, `accounting_document`, `crm_interaction`, `message`, `agent_log`, `intake`, `audit`, `access_account`, `analysis_text` and `data_subject_request`.
   - **What a request destroys** is a fixed property of the class and does not depend on whether a retention rule exists:
     - `crm_interaction`, `message`, `agent_log`, `intake`, `analysis_text` and derived rows (search keys, insights): destroyed at once by a request, with or without a rule;
     - `master_data`: destroyed at once when no posted document names the subject and it has no open item; otherwise the subject is blocked and its master data is destroyed together with `accounting_document`;
     - `audit`: the images of a column are masked when that column is destroyed (ADR-0038 rule 4);
     - `access_account`: by the existing rule for user accounts (ADR-0054 rule 3: tokenized when the account is erased);
     - `data_subject_request`: destroyed by a request exactly as ADR-0052 rule 25 says: the requester data and `outcome_note` of the subject's earlier closed requests, and at close the request's own content row, except `identity_proof_hash`, which is kept;
     - `accounting_document`: never destroyed by a request; only by the retention job under a verified rule. With no verified rule it stays, blocked, and the class is reported.
   - **Periods are package rules.** A localization package supplies the rules of its regime, each flagged verified or unverified (ADR-0016 rule 12), and every row names its package rule. The core seeds none. A company may shorten or lengthen a period only where the package marks it adjustable; `source` records whether the company adjusted it.
   - **No rule, no destruction by the job.** Where a class has no verified rule, the job neither blocks nor destroys for that class, and `check` and the operations dashboard report the class as without a retention rule. Keeping too long is reported; destroying too early cannot be undone.
   - **The job.** `RunPersonalDataRetention` runs daily as `system` on queue `jobs`. For each subject it computes the start event per class (for example the posting date of the last document that names the partner), blocks a subject whose purpose has ended through `BlockDataSubject` (`system`, `is_internal_only`, module `audit`, which writes `data_subject_state`; a person's block comes through `EraseDataSubject`), and runs `DestroyRetainedPersonalData` for the classes whose period has ended. A subject with an open item, an open document, an open data subject request or an open dispute is never blocked by the job.
   - **Evidence** is the `data_erasure_entry` rows and one processing log entry of kind `retention` per subject and run (a kind this ADR adds to ADR-0052 rule 26).
   - **Existing retention settings stay** (`messaging.message_retention_days`, the analysis question retention, the agent run step retention). They bound technical stores and may be shorter than a retention rule; where both apply, the shorter wins for stores that are not accounting evidence.

   Note (author, 2026-11-21): retention periods are configurable per customer. Each company sets its own rule per retention class (start event, months until blocking, months until destruction); a localization package may supply defaults, flagged verified or unverified as before. A company's own rule needs no package rule and no "adjustable" mark, and its legal correctness is the company's responsibility, as with the routing switch (D12). A company's own rule counts as verified for rules 7 and 9, INV-894 and EC-354: the person who records it confirms it (`is_verified` true), and because destruction cannot be undone the rule is set or changed through a change proposal that another person approves. A package default counts as verified only when the package flags it verified. The core still seeds no period, and "no rule, no destruction by the job" stays. The constraints of `retention_rule` that require a package rule (`package_rule_ref` NOT NULL, `ck_retention_rule_adjusted`) change with the DDL work of session S2: `package_rule_ref` becomes nullable for source `company` (which then also means a rule the company wrote itself, not only an adjusted package rule), `is_adjustable` no longer applies to it, and `is_verified` is set as above.

    Note (S2 findings closure, 2026-11-21): the DDL of the note above ([DS-64](../design/DS-64-personal-data.sql)): `package_rule_ref` is nullable and required only for source `package` (`ck_retention_rule_package_rule_ref`); `ck_retention_rule_adjusted` is dropped, so `is_adjustable` is the package's mark and gates nothing; a rule of source `company` must have `is_verified` true (`ck_retention_rule_company_verified`), because the person who records it confirms it. A company rule that adjusts a package default keeps its `package_rule_ref`. Lab t31's checks X17, X17a and X18 test it.

**Reading**

10. Personal columns are read under the record scope and leaves a role already has (ADR-0054). No new field class covers ordinary personal data: a sales clerk must read a customer's name.
11. `sensitive_personal` is a field class beside `cost` and `margin` (ADR-0017 rule 10). A column with that label is returned only to an assignment that holds the class. Only the `owner` template suggests it by default (`role-templates.csv`), so the owner can grant it; no Phase 1 column carries it; the class exists so that a package or a custom field can use it without a schema change.
12. Reads that are logged. `personal_data_read_log` gets one row, with query name, actor kind, the accountable user, the integration client or agent run when there is one, field names and row count and no values (a read by an integration client or an agent run is logged under its accountable person, ADR-0017), for:
    - every read that returns a `sensitive_personal` column;
    - every read of a blocked subject's unmasked data;
    - every `ExportDataSubject`, `ExportCompanyData` and list export that includes a personal column (ADR-0044; ADR-0050).
    Ordinary reads of personal columns are not logged: the record of who may read is the role assignment, and logging every read of a customer name would bury the reads that matter. The log is append-only and is kept as audit rows are (ADR-0038 rule 6).

**Encryption and restore**

13. Encryption is a property of the deployment that `nativeflows-ops check` verifies before go-live (DS-37):
    - the database volume, the attachment store and the backup repository are encrypted at rest;
    - backups are encrypted by the backup tool with a key held in the deployment's secret store, never in the repository or beside the backups;
    - connections are TLS;
    - secrets in the database (`totp_secret`, integration credentials) stay encrypted at column level under a key from the secret store (ADR-0054);
    - the backup retention window is at most `attachments.delete_grace_days` (rule 8).
    The core does not encrypt business columns: PostgreSQL must be able to index, join and constrain them.
14. Restore. A restore runs with triggers disabled (ADR-0014). `ReapplyErasures` is a step of the restore procedure, run with triggers still disabled; it is not a dispatcher command and does not use the erasure marker. It reads the erasure journal (rule 7) and, for every line whose `id` is missing from `data_erasure_entry`, re-inserts the entry from the line's columns with that `id` and applies its action to the target row, then writes one audit record. The restore runbook (S7; DS-37) makes this a step that cannot be skipped: the application refuses to start while the journal holds an `id` the table lacks.

**Breach handling**

15. Signals. These raise the work item `personal_data_incident_suspected`, owned by the company owner until a company names its data-protection role (open question):
    - a honeytoken record seeded in production (DS-37) is read or sent;
    - more than a set number of denials for one actor in an hour (ADR-0038 rule 5);
    - an export, or a run of reads in `personal_data_read_log`, above a set row count by one actor in a day;
    - an integration token used after revocation or from outside its allowed company;
    - an `llm_routing_refused` caused by a personal value while the routing switch is on.
    The thresholds are installation settings added with DS-37; until then the signals are raised by people.
16. A breach is handled as a work case of kind `personal_data_breach`, opened by a person from the work item or directly. `personal_data_breach` holds what an authority asks for: when it was discovered and when it happened, the catalog categories and subject kinds involved, the estimated number of subjects, the containment, and when the authority and the subjects were notified.
    - **Steps:** assess, contain, record, notify, close. The case cannot be resolved while the notification fields a package rule requires are empty.
    - **Deadlines** are package rules (`breach_notification_hours` per regime). The core computes `notification_due_at` from the rule and raises the due date on the case; with no rule the due date is empty and the case says so.
    - **Evidence** is the audit records, denials, the read log and the processing log (ADR-0038 rule 9).

    Note (author, 2026-11-21): the breach notification deadline is configurable per customer: the setting `breach_notification_hours` (scopes regime and company, core default unset), for which a localization package may supply the regime value; with no value the due date stays empty and the case says so. The setting row is added to `settings.csv` with the work of session S2. The core holds no country's value.

    Note (S2 findings closure, 2026-11-21): the registry key of the setting `breach_notification_hours` is `data_protection.breach_notification_hours` (ADR-0063 rule 2 asks for dotted keys): integer hours from discovery, scopes regime and company, core default unset, lower is tighter, leaf `data_protection`; `personal_data_breach.notification_due_at` is computed from it (ADR-0063 rule 29 note of this date).

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

- The triggers of posted documents (headers and lines), `document_version`, `journal_entry`, `journal_line` and the append-only tables gain the erasure exception of rule 7, limited to catalog columns. The DDL change is made with the ledger and document DDL in session S2.
- `check` enforces the catalog (rule 2). A new column with a personal name pattern fails the build until it is in the catalog or the exclusions.
- Only `EraseDataSubject` and `DestroyRetainedPersonalData` write under the erasure marker. `ReapplyErasures` is a restore step that runs with triggers disabled, not a command.
- The lab `t31_personal_data.py` loads the new tables and checks the catalog against the DDL.

## Revisit when

- A regime requires destruction of personal data on posted accounting documents before their retention period ends.
- A write-once archive or an analytics copy outside the database is added: decide per-period keys before it holds data.
- The read log grows by more than 1,000,000 rows a month in one company: log by sample or by session.

## Documents updated

- **Catalogs:** [personal-data-fields.csv](../catalogs/personal-data-fields.csv) and [personal-data-exclusions.csv](../catalogs/personal-data-exclusions.csv) (new); [authorization-areas.csv](../catalogs/authorization-areas.csv) and [role-template-levels.csv](../catalogs/role-template-levels.csv) (leaf `blocked_personal_data`, held by the `owner` template only; `ExportDataSubject` and `ReleaseDataSubject` on leaf `data_protection`); [role-templates.csv](../catalogs/role-templates.csv) (the `owner` template suggests `sensitive_personal`); [work-case-kinds.csv](../catalogs/work-case-kinds.csv) (`personal_data_breach`); [work-item-kinds.csv](../catalogs/work-item-kinds.csv) (`personal_data_incident_suspected`); [invariants.csv](../catalogs/invariants.csv) (INV-890 to INV-894; INV-10 skips erased versions); [edge-cases.csv](../catalogs/edge-cases.csv) (EC-350 to EC-354).
- **Design:** [DS-64-personal-data.sql](../design/DS-64-personal-data.sql) (new): `data_subject_state`, `retention_rule`, `data_erasure_entry`, `personal_data_read_log`, `personal_data_breach`; the field class `sensitive_personal` in DS-15 and DS-20 (no agent type version may hold it, DS-05); `document_version.erased_at` in DS-05; `custom_field_definition.is_personal_data` without a default in DS-20; the processing log kind `retention` in DS-35; the error `data_subject_blocked` in DS-04; the field class list in [architecture-overview.md](../design/architecture-overview.md); the edge-case and invariant counts in DS-17 and DS-16.
- **ADR notes:** ADR-0009 rules 9 and 14; ADR-0014 rule 13; ADR-0017 rule 10; ADR-0019 rules 7 and 10; ADR-0038 rules 1, 4 and 9; ADR-0044 rule 17; ADR-0050 rule 9; ADR-0052 rules 25, 26 and 29; ADR-0074 rule 8.
- **Lab:** `t31_personal_data.py` (new); `t27_partner_roles.py` states `is_personal_data` in its custom field fixture.
- **Glossary:** rows for data subject state, retention rule, erasure entry and journal, and the personal data catalog; the field class row gains `sensitive_personal` ([00-reading-guide.md](../spec/00-reading-guide.md)).
- **Open questions, backlog, index:** [docs/open-questions.md](../open-questions.md), [backlog.md](../design/backlog.md) (DS-64; DS-37 and DS-40 notes), [docs/adr/README.md](README.md).

## Edge cases and invariants

- **INV-890** `personal_data_catalog_complete`: every column matching the personal-name pattern or declared with a personal label is in the catalog or the exclusions; every catalog row names a real column.
- **INV-891** `blocked_subject_not_processed`: while a subject is blocked, no document, interaction, outbound message or agent run created after its `blocked_at` names it, except a follow-on document of an existing document of the same subject (a payment or clearing of its open item, a reversal, a correction, or a return that references its delivery or receipt lines).
- **INV-892** `destroyed_subject_is_blank`: for a subject in state `destroyed`, every catalog column of its rows holds the erasure action's result (for `clear_keys`: the named keys are absent), and a `data_erasure_entry` exists for each rewritten row.
- **INV-893** `erasure_changes_catalog_columns_only`: a row of a frozen or append-only table differs from its state before an erasure only in catalog columns; ledger balances before and after are equal.
- **INV-894** `no_destruction_without_rule`: every `data_erasure_entry` with cause `retention` falls after the destruction date of a verified `retention_rule` of its class; no entry with cause `request` rewrites a column of the class `accounting_document`.
- **EC-350** `erasure_request_during_retention`: a customer with posted invoices asks for erasure, with or without retention rules; its CRM text, messages and derived rows are destroyed at once; its master data stays because posted documents name it; the subject is blocked; the invoices stay and can be paid and reversed; the answer names what was destroyed and what is kept, under which rule and until when, or says "no retention rule yet".
- **EC-351** `destruction_after_retention`: the retention period of that customer ends; the job blanks the snapshots on the invoices and their versions; the trial balance is unchanged.
- **EC-352** `restore_before_erasure`: the database is restored to a point before a destruction; `ReapplyErasures` applies every erasure journal line whose `id` the restored `data_erasure_entry` lacks before the system opens.
- **EC-353** `blocked_subject_refused`: a new sales order for a blocked customer is refused; a payment for its open invoice, a credit note correcting that invoice and a return that references its delivery lines post; the printed invoice is not masked.
- **EC-354** `class_without_rule`: a company whose package has no verified rule for `crm_interaction`; the job destroys nothing of that class and reports it.
