Module: audit    Chunk: 2 of 2    Source ADRs: ADR-0079
Build step(s): 0    Generated from index: 30d5706    Compiled by: Claude Fable 5.2, 2026-11-21

# Compiled spec: `audit`, chunk 2

## Purpose

`audit` owns the audit records and the evidence of personal data protection. This chunk states personal data protection
(ADR-0079): the personal data catalog, the states of a data subject (blocked, released, destroyed), the single
destruction path and its database exception, retention rules and the retention job, the logged reads, encryption,
restore, and the handling of incidents and breaches. Chunk 1 states the audit record, field changes, denials and the
processing log. Each module destroys its own tables in its own consumer; `audit` owns the scope, the evidence and the
commands named below. The sensitive field class (ADR-0079.R11) belongs to `permissions`.

## Entities and tables

DDL: `docs/design/DS-64-personal-data.sql`. Chunk 1 carries `audit_record`, `audit_change`, `audit_denial` and
`personal_data_processing_log`.

| Table | Meaning | Key | Parent | Owner |
| --- | --- | --- | --- | --- |
| `data_subject_state` | One row per subject that is or has been blocked: `state`, `cause`, `blocked_at`, `destroy_due_date`, `destroyed_at`, `released_at`, the request document (R216). | `id`; unique (`subject_table`, `subject_id`); unique (`company_id`, `id`) | `company` (null only for a user account subject) | `audit` |
| `retention_rule` | Per company and retention class: start event, months until blocking, months until destruction, `source`, `package_rule_ref`, `is_verified`, `is_adjustable` (R245, R247). | `id`; unique (`company_id`, `retention_class`); unique (`company_id`, `id`) | `company` | `audit` |
| `data_erasure_entry` | One row per rewritten row: names the columns, holds no values; append-only (R240). | `id`; unique (`company_id`, `id`) | `company` (null only for a user account subject's installation rows) | `audit` |
| `personal_data_read_log` | One row per logged read: query name, accountable user, actor, `read_kind` (`sensitive_field`, `blocked_subject`, `export`), field names and row count, never values; append-only (R254). | `id`; unique (`company_id`, `id`) | `company` | `audit` |
| `personal_data_breach` | What an authority asks for about one breach case (R258). | `id`; unique `work_case_id`; unique (`company_id`, `id`) | `work_case` | `audit` |

Reads: `partner`, `contact`, `user_account`, `document`, `document_version`, `journal_entry`, `journal_line`, `payment`, `payment_line`, `tax_line`, `idempotency_record`, `custom_field_definition`, `posting_intent`, `processing_basis`, `work_case`, `approval`, `artifact_transition`, `automation_execution`, `setting_value`, `taint_clearance`, `work_item_note`, `analysis_example`, `company_setup_acknowledgement`, `document_extraction`, `saved_analysis_version`; the catalogs `catalogs/personal-data-fields.csv` and `catalogs/personal-data-exclusions.csv`.

## Commands and queries

| Name | Actor and authorization | Input | Effect | Events | Error codes |
| --- | --- | --- | --- | --- | --- |
| `ExportDataSubject` | `human_only`; leaf `data_protection` at `full` | One data subject | Writes the subject's catalog values, `processing_basis` rows and processing log entries into a file deleted after 7 days; writes an audit record and a processing log entry of kind `export` (R214); logged in `personal_data_read_log` (R254) | not stated | not stated |
| `ReleaseDataSubject` | `human_only`; leaf `data_protection` at `full`; module `audit` | A subject in state `blocked`, a reason | Sets the state `released`; writes an audit record (R221) | not stated | not stated |
| `EraseDataSubject` | `human_only`; leaf `data_protection` at `full`; a command of `crm`, defined by ADR-0019.R10 and ADR-0052.R25 | An approved deletion request | Blocks the subject and destroys at once what a request destroys (R229, R246) | `DataSubjectErased` | not stated |
| `DestroyRetainedPersonalData` | `system`; `is_internal_only`; module `audit`; run by the retention job | A subject and the retention classes whose period has ended under a verified rule | Destroys those classes' columns (R230) | `PersonalDataDestructionDue` with the due classes | not stated |
| `BlockDataSubject` | `system`; `is_internal_only`; module `audit` | A subject | Writes `data_subject_state` (R250) | not stated | not stated |
| `RunPersonalDataRetention` (job) | `system`; queue `jobs`; daily | None stated | Blocks subjects whose purpose has ended and runs `DestroyRetainedPersonalData` (R250) | not stated | not stated |

Not registered commands: `ReapplyErasures`, a step of the restore procedure (R256); the erasure scope of `audit.contract`
(R232); the event `DataErasureRecorded`, emitted by `audit.contract` and consumed by the erasure journal writer (R241);
the database functions `erasure_update_allowed`, `erasure_column_change_allowed`, `erasure_marker_valid` and
`erasure_command_record` of DS-05 (R233 to R237); the build command `check` (R210).

Error code bound to no named command: `data_subject_blocked` (R218).

## Rules

### Personal data catalog

R201. `catalogs/personal-data-fields.csv` has one row per column: table, column, subject kind (`partner`, `contact`, `user`, `employee`, `requester`, `other`), category (`identity`, `contact`, `financial`, `online_identifier`, `credential`, `free_text`, `snapshot`), label (`personal` or `sensitive_personal`, spec 17), condition, store class, erasure action and retention class.
Source: ADR-0079.R1

R202. The condition of a catalog row is `always`; or `partner_is_person`: the label applies when the row's partner is an individual or a sole proprietorship, or its kind is unknown (ADR-0019.R7); or `may_contain`: free text or JSON that may name a person.
Source: ADR-0079.R1

R203. The store class of a catalog row is `master` (a record that changes), `frozen_document` (posted documents, their versions, payments, tax lines), `append_only` (journal, audit, logs, CRM and intake rows) or `expiring` (removed by a retention job or a partition drop).
Source: ADR-0079.R1

R204. The erasure action of a catalog row is `tokenize` (a stable token, unique per row, that identifies nobody), `blank`, `clear_keys`, `delete_row`, `drop_with_partition`, or `keep` for a hash or ID kept as evidence, with the reason.
Source: ADR-0079.R1

R205. `blank` sets NULL only where the column is nullable and no CHECK ties its nullness to another column or flag; otherwise it sets the marker of the column's type: `''` for text, `{}` for an array column, `[]` for a JSON column a CHECK types as an array and `{}` for any other JSON column.
- The erasure flag the destruction path sets in the same update (`erased_at`, `body_removed_at`) does not count as a tie: a CHECK that asks for NULL once that flag is set gets NULL.
- Where a CHECK refuses both NULL and the marker (for example `coalesce(length(btrim(x)), 0) > 0` under a condition the row meets), the action is `tokenize`.
- A column inside a primary key, a UNIQUE constraint or a unique index is never blanked: it is tokenized, or its row is deleted.
- A `blank` row whose result is a marker says so in its note ("blank gives the marker ...").
Source: ADR-0079.R1

R206. `clear_keys` removes named keys from a JSON column and leaves the others. The row's note names the keys: for `custom_values`, the keys whose `custom_field_definition` has `is_personal_data` true; for `document_version.content`, the keys that mirror the header's and lines' catalog columns and those `custom_values` keys; for `posting_intent.plan`, the note and description keys of its entries and lines.
Source: ADR-0079.R1

R207. `catalogs/personal-data-exclusions.csv` lists the columns that match the personal-name pattern of R209 and hold no personal data (a legal entity's name, the company's own bank account, a code from a closed list), each with a reason. A row with column `*` excludes a whole table; its reason starts with the pattern-matching columns it covers (`covers: name; <reason>`), so a matching column added to the table later fails `check` until it is listed or catalogued. The `*` row is used only for code and configuration tables that have no person-related column.
Source: ADR-0079.R1

R208. The catalog is the single source. In the build, a field's label, category and erasure action are annotations of its Python declaration (ADR-0073), and `generate` writes the catalog from them. Until the declarations exist, the CSV file is the source and step 0 work loads it into the declarations.
Source: ADR-0079.R2

R209. The personal-name pattern matches:
- column names with a personal word: `email`, `phone`, `address`, `tax_id`, `account_number`, `holder_name`, `display_name`, `login`, `counterparty`, `sender_`, `recipient`, `partner_name`, `contact_name`, `*_name_text`, `custom_values`, `body`, `request_text`, `question_text`, `signature`;
- names with a free-text word (`note`, `comment`, `remark`, `description`, `reason`) or a name column (`name`, `*_name`);
- except reference and code columns: names ending in `_id`, `_ids`, `_kind` or `_code`.
Source: ADR-0079.R2

R210. `check` fails when:
- a column that matches the pattern, or whose declaration has a personal label, is in neither file or in both;
- a catalog row names no real column;
- a `blank` row names a column of a unique key or a column whose CHECKs refuse both NULL and the marker;
- a table excluded with `*` has a matching column outside its covers list;
- a custom field has no `is_personal_data` value (ADR-0074.R8; the column has no default, so the command must state it).
The lab `t31_personal_data.py` runs the same check against the DDL until the build exists.
Source: ADR-0079.R2

R211. Nothing but the catalog decides what is personal data. The label tables in ADR-0052.R29 and the prose lists of ADR-0019.R7, ADR-0038 and ADR-0050.R9 are read as extracts of the catalog. Where they disagree, the catalog wins and the disagreement is a defect.
Source: ADR-0079.R2

R212. The keys of `custom_values` whose definition has `is_personal_data` true are catalog members by rule: one catalog row per table with `custom_values`, with action `clear_keys`, stands for them.
Source: ADR-0079.R2

### What the catalog drives

R213. The labels the LLM gateway strips or routes (ADR-0050.R9; D12) are the catalog's labels, with the row condition evaluated per value.
Source: ADR-0079.R3

R214. `ExportDataSubject` (`human_only`, leaf `data_protection` at `full`) writes every catalog value of one subject, the subject's `processing_basis` rows and its processing log entries into a file that is deleted after 7 days, as `ExportCompanyData` is (ADR-0044.R17). It writes an audit record and a processing log entry of kind `export`. Columns with condition `may_contain` are included only from rows that reference the subject. Columns of subject kind `other` are included only when the requester is that person and a person adds them.
Source: ADR-0079.R3

R215. The catalog also drives blocking and destruction (R216 to R244), masking and retention. Lists, searches, exports and the UI mask a blocked subject's catalog columns (R219) and every `sensitive_personal` column (ADR-0079.R11). The retention job reads the retention class (R245).
Source: ADR-0079.R3

### Data subject states

R216. A data subject is a partner, a contact or a user account. An employee is a partner with the role `employee` (ADR-0019.R2, ADR-0019.R3). `data_subject_state` holds one row per subject that is blocked or has been: `blocked`, `released` or `destroyed`, with the cause (`request` or `retention`), the dates and the request document. A later block updates the same row.
Source: ADR-0079.R4

R217. Columns of subject kind `requester` and `other` belong to no data subject record and are not reached through `data_subject_state`. `requester` columns (the requester details of a data subject request) follow the request's retention class. `other` columns (named officers on a print profile) are changed by editing the record.
Source: ADR-0079.R4

R218. A blocked subject cannot be named on a new document, interaction, message recipient list or agent run, and is left out of search and of every LLM request, whatever the routing switch says. The one exception is a follow-on document of an existing document of the same subject: a payment or clearing of its open item, a reversal (`reversal_of_id`), a correction (`correction_of_id`: credit and debit notes), and a return that references its delivery or receipt lines. Everything else is refused with `data_subject_blocked`.
Source: ADR-0079.R5

R219. A blocked subject's catalog columns are masked in lists, searches, exports and the UI for everyone who does not hold the capability `read_blocked_personal_data`. Statutory reports and prints of posted documents (ADR-0049) are not masked: they are the legal purpose the data is kept for. The capability is the leaf `blocked_personal_data`; the `owner` template holds it at `full`, like every capability, and grants it to the people who answer authorities and auditors (ADR-0017.R6); no other template holds it; every read under it is logged (R254).
Source: ADR-0079.R5

R220. Posted documents, open items and the journal of a blocked subject stay complete and keep working: a blocked customer's invoice can still be paid, reversed, corrected and reported. Amounts, accounts and document numbers are never masked.
Source: ADR-0079.R5

R221. `ReleaseDataSubject` (`human_only`, leaf `data_protection` at `full`, module `audit`) releases a block made in error or for a returning customer, only from `blocked`, with a reason; it writes an audit record. A destroyed subject is never released.
Source: ADR-0079.R5

### Destruction

R222. Destroyed means every catalog column of the subject, in every store class, has had its erasure action applied. Each module's hook sets its table's erasure flag (`erased_at`, `body_removed_at`), where the table has one, in the same update.
Source: ADR-0079.R6

R223. Master and CRM stores are destroyed as `EraseDataSubject` does under ADR-0019.R10 and ADR-0052.R25.
Source: ADR-0079.R6

R224. Frozen documents and versions: the snapshot columns (`partner_name`, `partner_tax_id`, addresses, the party columns of ADR-0074) are blanked and the catalog keys of `document_version.content` are cleared (`clear_keys`). The version's stored `version_hash` stays unchanged and the version's `erased_at` (DS-05) is set, so the hash is no longer checked against the content (as ADR-0038.R4 marks erased audit rows with `erased_at`; `INV-10` skips such versions).
Source: ADR-0079.R6

R225. Journal: `journal_entry.note` and `journal_line.description` of entries that name the subject as partner are blanked. No amount, account, date or key changes, so every balance and every invariant of the ledger holds.
Source: ADR-0079.R6

R226. Audit rows, proposals, agent run steps, extractions and messages are blanked as their ADRs say (ADR-0038.R4; ADR-0050.R20; ADR-0057.R19; ADR-0076.R10); change proposal payloads and field changes that name the subject are blanked the same way.
Source: ADR-0079.R6

R227. Attachments: links end and bytes are released as ADR-0038.R15 says. A file linked to several subjects keeps its bytes until its last link ends.
Source: ADR-0079.R6

R228. Derived stores: search keys and insights are deleted; trigram indexes follow their rows; embeddings do not exist in Phase 1.
Source: ADR-0079.R6

R229. `EraseDataSubject` and `DestroyRetainedPersonalData` destroy, through one path driven by the catalog. `EraseDataSubject` stays as ADR-0019.R10 and ADR-0052.R25 define it: `human_only`, run by a person on an approved deletion request. It blocks the subject and destroys at once what R246 says a request destroys. Data of classes a request does not destroy stays, blocked. The request is answered with what has been destroyed and what is kept, under which rule and until when, or "no retention rule yet".
Source: ADR-0079.R7

R230. `DestroyRetainedPersonalData` (`system`, `is_internal_only`, module `audit`) is run by the retention job (R250). It takes a subject and the retention classes whose period has ended under a verified rule, and destroys those classes' columns.
Source: ADR-0079.R7

R231. Each destroying command emits an event that carries only IDs: `EraseDataSubject` emits `DataSubjectErased` (ADR-0052.R25); `DestroyRetainedPersonalData` emits `PersonalDataDestructionDue` with the due classes; `audit.contract` emits `DataErasureRecorded` per entry for the erasure journal writer (R241), a separate event, so that each event has one owning module. Each module destroys its own tables in its consumer of these events, in the consumer's own transaction, with the hook generated from the catalog. No module imports a peer (ADR-0022).
Source: ADR-0079.R7

R232. The consumer opens an erasure scope through `audit.contract` with the originating command's ID. `audit.contract` binds the scope to that command's subject and, for `DestroyRetainedPersonalData`, its due classes: a consumer cannot rewrite rows of another subject or of another class under that command's ID. Through the scope, and in its own transaction, the consumer writes an `idempotency_record` of the originating command's type, keyed by that command's ID and the consumer's name, and sets the marker `nativeflows.erasure_command_id` (ADR-0038.R4) to that record's ID.
Source: ADR-0079.R7, .N1

R233. The triggers that refuse changes to posted documents, versions, journal rows and append-only rows allow, under a valid marker, an update that changes only catalog columns of that table. `erasure_update_allowed()` (`docs/design/DS-05-platform.sql`) returns true only under a valid marker, when every changed column is a catalog column that the trigger passes as an argument, or the erasure flag (`erased_at`, `body_removed_at`) set from null; generated columns are skipped; it never allows a delete. Any other column, or any other command, is refused.
Source: ADR-0079.R7, .N1

R234. Under the marker a catalog column may only take an erasure result of R222 to R228: NULL, the blank marker (`''`, `{}`, `[]`), the token `erased-` followed by 12 to 64 lowercase hex digits (`tokenize`), or a part of the old JSON object (`clear_keys`). A column that already holds such a result is never rewritten. Where the trigger passes a key list (`document_version.content`), an erasure removes or blanks only the listed keys; the column is never blanked whole (`'{}'`, `'[]'` and JSON null are refused), so a posted version keeps its amounts and lines (`erasure_column_change_allowed` in DS-05). A JSON column without a key list is blanked whole.
Source: ADR-0079.R7, .N1, .N2

R235. The triggers that pass their catalog columns are the refusing triggers of `document`, `document_version`, `payment`, `payment_line`, `tax_line`, change proposals, period unlock requests, `journal_entry` (`note`), `journal_line` (`description`) and the append-only `approval`, `artifact_transition`, `automation_execution`, `setting_value`, `taint_clearance` and `work_item_note`; the generated trigger of the DS-22 headers and lines passes them as the second argument of `document_check_frozen`. The lists are generated from the catalog, and lab t31 checks them against it. The append-only tables with guard functions of their own (`analysis_example`, `company_setup_acknowledgement`, `document_extraction`, `posting_intent`, `saved_analysis_version`) get the same argument when those functions are next changed.
Source: ADR-0079.R7, .N1

R236. The marker is valid only when `erasure_marker_valid()` (DS-05) finds an `idempotency_record` with that `id`, scope `EraseDataSubject` or `DestroyRetainedPersonalData`, written in the same transaction (`transaction_id = pg_current_xact_id()`, ADR-0008.R16) and belonging to the company of the row being changed, not only to the session's company (`erasure_marker_valid(p_row)`). `erasure_update_allowed`, `platform_check_append_only` and `crm_check_append_only` call it, and a load without `idempotency_record` refuses every marker. Same transaction, not committed, is the test: a committed record can be named by any later session, which the database cannot tell from the consumer it is meant for.
Source: ADR-0079.R7, .N1, .N2

R237. Only `erasure_command_record()` writes an `idempotency_record` of scope `EraseDataSubject` or `DestroyRetainedPersonalData`. It is a security-definer function in the pattern of `nativeflows_claim`, owned by the no-login role `nativeflows_erasure_writer`; it takes the company from the session and inserts as the dispatcher does. The role, its grant and the ownership are created with the database roles (DS-18). The DDL revokes EXECUTE on `erasure_command_record` from PUBLIC beside the function; DS-18 grants it to the dispatcher's role only.
Source: ADR-0079.R7.N3

R238. The trigger `trg_idempotency_record_check_scope` refuses the scopes `EraseDataSubject` and `DestroyRetainedPersonalData`, and a change of scope into them, unless `current_user` is the owner of `erasure_command_record()`. On every row, not only on erasure rows, it refuses any change of `id`, `company_id`, `scope` and `transaction_id`, so an erasure record of an earlier transaction can never be re-armed for the current one by moving its `transaction_id`.
Source: ADR-0079.R7.N3

R239. The database does not prove who may run an erasure; that is the command layer's permission check (`EraseDataSubject` is `human_only`; `DestroyRetainedPersonalData` is internal to the retention job). The database proves only that an idempotency record of an erasure command, for this company, exists in this transaction. The dispatcher's role can write a marker by calling `erasure_command_record()`, and under it the guards still refuse every change but an erasure result in a catalog column.
Source: ADR-0079.R7.N2, ADR-0079.R7.N3

R240. Every rewrite appends a `data_erasure_entry`: subject, target table and row key (the row's primary key, which for tables without an `id` is several columns), column names, action, cause, request, command and time. It holds no values. An installation row (a user account's) names no request document: `ck_data_erasure_entry_request_company` and `ck_data_subject_state_request_company` require `company_id` whenever `data_subject_request_id` is set, so the composite key to `document` always holds; a user account's state blocked by a request carries the request's company, and its installation erasure entries are reached through `command_id`.
Source: ADR-0079.R7, .N3

R241. `audit.contract`'s insert of a `data_erasure_entry` emits the IDs-only event `DataErasureRecorded` in the same transaction. After commit its consumer, the erasure journal writer, appends one line per entry to the erasure journal: an object of its own under a prefix of the object store that the attachment orphan sweep never touches (it is not an attachment). A line holds every column of its entry (id, subject, target table, row key, column names, action, cause, request, command and time) and no values, so a restore can re-insert the entry and apply it. Delivery is at least once; appending an `id` twice is harmless.
Source: ADR-0079.R7

### Stores that cannot be rewritten

R242. A backup is never edited. The backup retention window is at most `attachments.delete_grace_days` (ADR-0038.R15), so a destroyed value leaves the last backup within that window. After any restore, and before the system opens, `ReapplyErasures` re-applies the erasures the restored database lacks (R256).
Source: ADR-0079.R8

R243. A provider that retained a request is outside the system; the provider registry's `retention_days` and no-training flag (ADR-0063.R14) are what the company relies on, and the processing log names what has been sent.
Source: ADR-0079.R8

R244. Crypto-shredding (a key per subject, destroyed to erase) is not used in Phase 1. In-place destruction reaches every store the database holds, and it keeps documents readable by SQL, reports and printing. A write-once archive, if one is ever added, must be encrypted with keys that can be destroyed per retention period.
Source: ADR-0079.R8

### Retention

R245. `retention_rule` holds, per company and retention class, the start event, the months until blocking and the months until destruction. The classes are `master_data`, `accounting_document`, `crm_interaction`, `message`, `agent_log`, `intake`, `audit`, `access_account`, `analysis_text` and `data_subject_request`.
Source: ADR-0079.R9

R246. What a request destroys is a fixed property of the class and does not depend on whether a retention rule exists:
- `crm_interaction`, `message`, `agent_log`, `intake`, `analysis_text` and derived rows (search keys, insights): destroyed at once by a request, with or without a rule;
- `master_data`: destroyed at once when no posted document names the subject and it has no open item; otherwise the subject is blocked and its master data is destroyed together with `accounting_document`;
- `audit`: the images of a column are masked when that column is destroyed (ADR-0038.R4);
- `access_account`: by the existing rule for user accounts (ADR-0054.R3: tokenized when the account is erased);
- `data_subject_request`: destroyed by a request as ADR-0052.R25 says: the requester data and `outcome_note` of the subject's earlier closed requests, and at close the request's own content row, except `identity_proof_hash`, which is kept;
- `accounting_document`: never destroyed by a request; only by the retention job under a verified rule. With no verified rule it stays, blocked, and the class is reported.
Source: ADR-0079.R9

R247. Retention periods are configurable per customer. Each company sets its own rule per retention class (start event, months until blocking, months until destruction); a localization package may supply defaults, each flagged verified or unverified (ADR-0016.R12). The core seeds no period. A company's own rule needs no package rule and no adjustable mark, and its legal correctness is the company's responsibility, as with the routing switch (D12). A company's own rule counts as verified for R230, R249, R250, `INV-894` and `EC-354`: the person who records it confirms it (`is_verified` true), and because destruction cannot be undone the rule is set or changed through a change proposal that another person approves. A package default counts as verified only when the package flags it verified.
Source: ADR-0079.R9, .N1

R248. In `retention_rule` (`docs/design/DS-64-personal-data.sql`), `source` is `package` or `company`; `company` means a rule the company wrote itself or a package default it adjusted. `package_rule_ref` is nullable and required only for source `package` (`ck_retention_rule_package_rule_ref`); a company rule that adjusts a package default keeps its `package_rule_ref`. `is_adjustable` is the package's mark and gates nothing. A rule of source `company` must have `is_verified` true (`ck_retention_rule_company_verified`).
Source: ADR-0079.R9, .N1, .N2

R249. No rule, no destruction by the job. Where a class has no verified rule, the job neither blocks nor destroys for that class, and `check` and the operations dashboard report the class as without a retention rule. Keeping too long is reported; destroying too early cannot be undone.
Source: ADR-0079.R9, .N1

R250. `RunPersonalDataRetention` runs daily as `system` on queue `jobs`. For each subject it computes the start event per class (for example the posting date of the last document that names the partner), blocks a subject whose purpose has ended through `BlockDataSubject` (`system`, `is_internal_only`, module `audit`, which writes `data_subject_state`; a person's block comes through `EraseDataSubject`), and runs `DestroyRetainedPersonalData` for the classes whose period has ended. A subject with an open item, an open document, an open data subject request or an open dispute is never blocked by the job.
Source: ADR-0079.R9

R251. The evidence of retention is the `data_erasure_entry` rows and one processing log entry of kind `retention` per subject and run, a kind of `personal_data_processing_log` beside those of ADR-0052.R26.
Source: ADR-0079.R9

R252. The existing retention settings stay (`messaging.message_retention_days`, the analysis question retention, the agent run step retention). They bound technical stores and may be shorter than a retention rule; where both apply, the shorter wins for stores that are not accounting evidence.
Source: ADR-0079.R9

### Reading personal data

R253. Personal columns are read under the record scope and leaves a role already has (ADR-0054). No new field class covers ordinary personal data: a sales clerk must read a customer's name.
Source: ADR-0079.R10

R254. `personal_data_read_log` gets one row, with query name, actor kind, the accountable user, the integration client or agent run when there is one, field names and row count and no values, for:
- every read that returns a `sensitive_personal` column;
- every read of a blocked subject's unmasked data;
- every `ExportDataSubject`, `ExportCompanyData` and list export that includes a personal column (ADR-0044; ADR-0050).
A read by an integration client or an agent run is logged under its accountable person (ADR-0017). Ordinary reads of personal columns are not logged: the record of who may read is the role assignment. The log is append-only and is kept as audit rows are (ADR-0038.R6).
Source: ADR-0079.R12

### Encryption and restore

R255. Encryption is a property of the deployment that `nativeflows-ops check` verifies before go-live (DS-37):
- the database volume, the attachment store and the backup repository are encrypted at rest;
- backups are encrypted by the backup tool with a key held in the deployment's secret store, never in the repository or beside the backups;
- connections are TLS;
- secrets in the database (`totp_secret`, integration credentials) stay encrypted at column level under a key from the secret store (ADR-0054);
- the backup retention window is at most `attachments.delete_grace_days` (R242).
The core does not encrypt business columns: PostgreSQL must be able to index, join and constrain them.
Source: ADR-0079.R13

R256. A restore runs with triggers disabled (ADR-0014). `ReapplyErasures` is a step of the restore procedure, run with triggers still disabled; it is not a dispatcher command and does not use the erasure marker. It reads the erasure journal (R241) and, for every line whose `id` is missing from `data_erasure_entry`, re-inserts the entry from the line's columns with that `id` and applies its action to the target row, then writes one audit record. The restore runbook (S7; DS-37) makes this a step that cannot be skipped: the application refuses to start while the journal holds an `id` the table lacks.
Source: ADR-0079.R14

### Incidents and breaches

R257. These signals raise the work item `personal_data_incident_suspected`, owned by the company owner until a company names its data-protection role (open question):
- a honeytoken record seeded in production (DS-37) is read or sent;
- more than a set number of denials for one actor in an hour (ADR-0038.R5);
- an export, or a run of reads in `personal_data_read_log`, above a set row count by one actor in a day;
- an integration token used after revocation or from outside its allowed company;
- an `llm_routing_refused` caused by a personal value while the routing switch is on.
The thresholds are installation settings added with DS-37; until then the signals are raised by people.
Source: ADR-0079.R15

R258. A breach is handled as a work case of kind `personal_data_breach`, opened by a person from the work item or directly. The table `personal_data_breach` holds what an authority asks for: when it has been discovered and when it happened, the catalog categories and subject kinds involved, the estimated number of subjects, the containment, and when the authority and the subjects have been notified.
Source: ADR-0079.R16

R259. The steps of a breach case are assess, contain, record, notify, close. The case cannot be resolved while the notification fields a package rule requires are empty.
Source: ADR-0079.R16

R260. The breach notification deadline is configurable per customer: the setting `data_protection.breach_notification_hours` (named `breach_notification_hours` in the rule text; integer hours from discovery, scopes regime and company, core default unset, lower is tighter, leaf `data_protection`), for which a localization package may supply the regime value. The core holds no country's value. The core computes `notification_due_at` of `personal_data_breach` from the setting and raises the due date on the case; with no value the due date is empty and the case says so.
Source: ADR-0079.R16, .N1, .N2

R261. The evidence of a breach is the audit records, denials, the read log and the processing log (ADR-0038.R9).
Source: ADR-0079.R16

R262. Not in Phase 1: pseudonymization before sending to a cloud model (spec 17, after Phase 1); a consent-management UI beyond `processing_basis` (ADR-0019.R9); masking of a production copy for a sandbox; per-subject encryption keys.
Source: ADR-0079.R17

## Invariants

Sources are those of `invariants.csv`. `INV-10` belongs to the ledger area; it stands here because R224 changes what it
checks. Chunk 1 carries the invariants its rules name.

| INV | Check point | Statement | Protects |
| --- | --- | --- | --- |
| `INV-10` | day | `version_content_matches_rows` (area `ledger`): the current document version's content and `version_hash` equal those computed from the typed rows; versions with `erased_at` set are skipped. | R224 |
| `INV-890` | run | `personal_data_catalog_complete` (area `platform`): every column matching the personal-name pattern or declared with a personal label is in the catalog or the exclusions; every catalog row names a real column. | R209, R210 |
| `INV-891` | day | `blocked_subject_not_processed` (area `safety`): while a subject is blocked, no document, interaction, outbound message or agent run created after its `blocked_at` names it, except a follow-on document of an existing document of the same subject: a payment or clearing of its open item, a reversal, a correction (credit or debit note) or a return that references its delivery or receipt lines. | R218 |
| `INV-892` | day | `destroyed_subject_is_blank` (area `safety`): for a subject in state `destroyed`, every catalog column of its rows holds the erasure action's result (for `clear_keys`: the named keys are absent), and a `data_erasure_entry` exists for each rewritten row. | R222, R240 |
| `INV-893` | command | `erasure_changes_catalog_columns_only` (area `safety`): a row of a frozen or append-only table differs from its state before an erasure only in catalog columns; ledger balances before and after are equal. | R233, R225 |
| `INV-894` | day | `no_destruction_without_rule` (area `safety`): every `data_erasure_entry` with cause `retention` falls after the destruction date of a verified `retention_rule` of its class; no entry with cause `request` rewrites a column of the class `accounting_document`. A company's own rule counts as verified (R247). | R246, R249 |

## Edge cases

| EC | Name | Case | Outcome | Source |
| --- | --- | --- | --- | --- |
| `EC-350` | `erasure_request_during_retention` | A customer with posted invoices asks for erasure, with or without retention rules; its CRM text, messages and derived rows are destroyed at once; its master data stays because posted documents name it; the subject is blocked; the invoices stay and can be paid and reversed; the answer names what has been destroyed and what is kept, under which rule and until when, or says "no retention rule yet". | `must_succeed` | ADR-0079.R7 (R229, R246) |
| `EC-351` | `destruction_after_retention` | The retention period of that customer ends; the job blanks the snapshots on the invoices and their versions; the trial balance is unchanged. | `must_succeed` | ADR-0079.R6, ADR-0079.R7, ADR-0079.R9 (R224, R230, R250) |
| `EC-352` | `restore_before_erasure` | The database is restored to a point before a destruction; `ReapplyErasures` applies every erasure journal line whose `id` the restored `data_erasure_entry` lacks before the system opens. | `must_succeed` | ADR-0079.R14 (R256) |
| `EC-353` | `blocked_subject_refused` | A new sales order for a blocked customer is refused; a payment for its open invoice, a credit note correcting that invoice and a return that references its delivery lines post; the printed invoice is not masked. | `must_reject:data_subject_blocked` for the sales order; `must_succeed` for the follow-on documents | ADR-0079.R5 (R218, R219) |
| `EC-354` | `class_without_rule` | A company whose package has no verified rule for `crm_interaction`, and that has no rule of its own (R247); the job destroys nothing of that class and reports it. | `must_succeed` | ADR-0079.R9 (R249) |

## Settings

| Key | Value type | Scopes | Core default | Used by |
| --- | --- | --- | --- | --- |
| `data_protection.breach_notification_hours` | integer (bounds `1..`; `lower_tighter`; leaf `data_protection`) | `regime`, `company` | `unset` | R260 |

Reads: `attachments.delete_grace_days` (`attachments`; ADR-0038.R15), used by R242 and R255; `messaging.message_retention_days` (`work`; ADR-0076.R11), used by R252; `ui.post_review` (`ui`; ADR-0067.R13), named by R15 of chunk 1; `ui.post_review_max_amount` (`ui`; ADR-0067.R20), named only by the catalog rows of ADR-0067.R20 and used by no rule of `audit`.

The signal thresholds of R257 are installation settings added with DS-37; the sources name no key for them and
`settings.csv` holds none. The analysis question retention and the agent run step retention of R252 are named by the
rule without a key.

## UI annotations

The sources state no floorplan, title, facet, field annotation or tile for this chunk. Kinds of `audit` in the catalogs:

| Kind | Catalog | Subject table | Owner | Due | Resolution | Rule |
| --- | --- | --- | --- | --- | --- | --- |
| `personal_data_incident_suspected` | `work-item-kinds.csv` | `company` | `company_owner` | `same_day` | `person`; open key: the signal and the business date; a person opens a `personal_data_breach` case from it or resolves it | R257 |
| `personal_data_breach` | `work-case-kinds.csv` | none | `company_owner` | `days:1` | `person`; opened by a person with no origin; open key: the case's own ID, so several breaches may be open at once | R258, R259 |

## Conflicts

CONFLICT ADR-0079.R7: the rule text accepts the marker when a committed erasure command with that ID exists; ADR-0079.R7.N1 replaces this with an idempotency record written in the same transaction, stated in R232 and R236.
CONFLICT ADR-0079.R7.N1: the note supersedes the committed-command test of the exception and of ADR-0038.R4.N2 (chunk 1 states the same under ADR-0038.R4.N2, R25); ADR-0079.R7.N1 governs, and ADR-0079.R7.N2 adds the company of the changed row, stated in R236.
CONFLICT ADR-0079.R9: the rule text makes periods package rules that a company adjusts only where the package marks it adjustable, and has every row name its package rule; ADR-0079.R9.N1 governs, stated in R247 and R248.
CONFLICT ADR-0079.R9.N1: a company's own retention rule needs no package rule and counts as verified, so the package-only reading of the rule no longer applies; ADR-0079.R9.N1 governs, stated in R247.
CONFLICT ADR-0079.R9.N2: the constraint `ck_retention_rule_adjusted` is dropped and `package_rule_ref` is nullable for source `company`; ADR-0079.R9.N2 governs with the DDL of DS-64, stated in R248.
CONFLICT ADR-0079.R16: the rule text makes the breach deadline a package rule `breach_notification_hours` per regime; ADR-0079.R16.N1 makes it a setting and ADR-0079.R16.N2 gives the key `data_protection.breach_notification_hours`, stated in R260.

## Proposed (not law)

None

## Trace

| Source | Where |
| --- | --- |
| ADR-0079.R1 | R201-R207 |
| ADR-0079.R2 | R208-R212 |
| ADR-0079.R3 | R213-R215 |
| ADR-0079.R4 | R216, R217 |
| ADR-0079.R5 | R218-R221 |
| ADR-0079.R6 | R222-R228 |
| ADR-0079.R7 | R229-R236, R240, R241 |
| ADR-0079.R7.N1 | R232-R236 |
| ADR-0079.R7.N2 | R234, R236, R239 |
| ADR-0079.R7.N3 | R237-R240 |
| ADR-0079.R8 | R242-R244 |
| ADR-0079.R9 | R245-R252 |
| ADR-0079.R9.N1 | R247-R249 |
| ADR-0079.R9.N2 | R248 |
| ADR-0079.R10 | R253 |
| ADR-0079.R12 | R254 |
| ADR-0079.R13 | R255 |
| ADR-0079.R14 | R256 |
| ADR-0079.R15 | R257 |
| ADR-0079.R16 | R258-R261 |
| ADR-0079.R16.N1 | R260 |
| ADR-0079.R16.N2 | R260 |
| ADR-0079.R17 | R262 |
