Module: attachments    Chunk: 1 of 3    Source ADRs: ADR-0027, ADR-0038, ADR-0057
Build step(s): 1, 5    Generated from index: 30d5706    Compiled by: Claude Fable 5.2, 2026-11-21

# `attachments` compiled spec, chunk 1: attachment storage, upload, scan, retention; extraction request, reader ladder, reader contract

## Purpose

`attachments` (layer 2, ADR-0022.R2) owns the attachment rows and their links, and the extraction tables of document intake. This chunk states the law on identity and storage of an attachment, upload, the scan state machine, retention and the orphan sweep, and on the first half of document intake: purposes, requesting an extraction, the ladder runner, the reader contract and the structured e-invoice reader. The bytes live in an object store, never in the database. `attachments` imports no module and no package: readers reach it through the hook `document_reader`. Fields, words, alignment, rule runs, trust, verification, the mailbox route and the agent type's limits are in the other chunks.

## Entities and tables

DDL: `docs/design/DS-05-platform.sql` (`attachment`, `attachment_link`) and `docs/design/DS-36-document-intake.sql` (section `[attachments]`, the extraction tables).

| Table | Meaning | Key | Parent | Owner |
| --- | --- | --- | --- | --- |
| `attachment` | One stored file of a company, identified by its bytes, with its scan state and release marks (R1, R11, R19) | `id`; (`company_id`, `sha256`) unique; (`company_id`, `id`) | `company` | `attachments` |
| `attachment_link` | Link of an attachment to a row of a target table, polymorphic (R3) | `id` | `attachment` | `attachments` |
| `document_reader` | Installation data: one immutable row per registered reader code and version (R39) | `id`; (`code`, `version`) unique | none | `attachments` |

The tables `document_extraction`, `extraction_word`, `extraction_field`, `extraction_rule_run`, `extraction_confirmation` and `extraction_result_link` and the trust view `extraction_field_trust` are owned by `attachments` (R24); their rows stand in chunk 2, with the rules that define them (ADR-0057.R7 to ADR-0057.R10, ADR-0057.R14, ADR-0057.R19, ADR-0057.R23).

Reads: `company`, `partner` (`master_data`); `document`, `inbound_message`, `user_account`, `agent_run`, `message`, `e_invoice_record`, `data_processing_permission`, `agent_type_version`.

## Commands and queries

| Name | Actor and authorization | Input | Effect | Events | Error codes |
| --- | --- | --- | --- | --- | --- |
| `CreateAttachment` | dispatched by the upload endpoint; area `general_access` at `edit` (catalog `authorization-areas.csv`, module `registry`) | SHA-256, size, detected type, data label, source kind | Creates or reuses the `attachment` row; audited (R7) | `AttachmentCreated` | not stated for the command; the upload's codes are under the table |
| `RunAttachmentOrphanSweep` | daily system job, `is_internal_only`, installation scope, effect class `other` | not stated | Deletes orphan objects older than the grace period and sets `bytes_deleted_at` (R21) | not stated | not stated |
| `RequestDocumentExtraction` | a person, or the mailbox route as `system` on behalf of the mailbox owner; verb Request at `edit` on the purpose's leaf; effect class `other` | `attachment_id`, `purpose`, optional `partner_id`; the mailbox route also passes `inbound_message_id` | Creates a `document_extraction` in state `pending` (R29) | `DocumentExtractionRequested` | `attachment_not_available`, `extraction_purpose_exists` |
| `RecordDocumentExtraction` | registered for the ladder runner alone, on no agent tool list; the purpose's leaf at `post` (system; ADR-0057.R31); effect class `other` | words, fields, first rule run, attempts, `final_reader_id`, flags, new state | Records the ladder's result and sets `extracted` or `needs_review` (R35) | `DocumentExtractionRecorded` | not stated |

Not registered commands: the upload endpoint (hand-written, R6); the daily sweep of temporary bytes (R7); the scanner consumer on `integrations` (R11); the contract `attachments.contract`, through which `documents` reads the scan state (R14); the hook `document_reader` and the published interface `DocumentReader` (R25); the external consumer `document_extraction_runner` (R30); the adapter interface `OcrEngine` (R41); the seam `EInvoiceRecordReader` (R43).

Error codes bound to no command of this chunk: the upload returns `attachment_too_large` (category `too_large`, HTTP 413), `attachment_type_not_allowed` and `attachment_rejected` (R8, R12); download, parsing and `Post` return `attachment_not_available` (R13, R14); readers return `e_invoice_record_unreadable` and `e_invoice_schema_unknown` (R37, R43); `VerifyDocumentExtraction` returns `duplicate_external_document` (R36).

## Rules

### Attachment identity, links and generated files

R1. An `attachment` is unique per (`company_id`, SHA-256), column `sha256`. It records media type (`media_type`), size (`byte_count`), storage key (`storage_key`), data label (`data_label`: `public`, `internal`, `personal` or `sensitive_personal`) and source kind (`source_kind`). The DDL lists the source kinds `upload`, `email`, `import`, `integration` and `generated`; it marks the values other than `generated` as interim. The bytes live in an object store, never in the database (DS-37).
Source: ADR-0027.R2

R2. A second upload of the same bytes in the same company reuses the row and keeps the stricter data label. A second creation of the same bytes of a generated file also keeps the stricter `contains_untrusted`.
Source: ADR-0027.R2, .N1

R3. `attachment_link` holds the attachment, the target table and the target ID (`attachment_id`, `target_table`, `target_id`). Its reference is polymorphic, so it is checked by the invariant `INV-83`. The DDL adds `ended_at` (interim): a link ends rather than disappears, for retention.
Source: ADR-0027.R2

R4. Erasure of a data subject (ADR-0019) removes that subject's links, except links to posted accounting documents, which stay as voucher evidence. Bytes are released only when no link remains and retention allows (R17 to R19). DS-36 owns retention, scanning and limits.
Source: ADR-0027.R2, ADR-0038.R15, .N2

R5. Source kind `generated` marks files the render worker produced. They are created in scan state `clean` without a malware scan, because the render worker produces their bytes from company templates in a sandbox without network access; `clean` covers only the scan and says nothing about their content. The row also records `generated_kind`, `generated_audience` (`internal` or `external`), `generated_subject_document_id` and `contains_untrusted`, set at creation and never changed. A generated file whose rendered instance held an `is_untrusted` field carries `contains_untrusted`, and reading it taints a run (ADR-0050.R25, ADR-0049.R28).
Source: ADR-0027.R2.N1, ADR-0038.R14.N1

### Upload

R6. Files go through a dedicated upload endpoint whose limit is `attachment_max_bytes` (default 25 MiB), separate from the 10 MiB request body limit (ADR-0022). The endpoint is a hand-written exception to ADR-0008.R6, with the session and stream endpoints of ADR-0040.R12.
Source: ADR-0038.R13

R7. The endpoint streams the bytes to the object store under a temporary key, then dispatches the registered command `CreateAttachment` (SHA-256, size, detected type, data label, source kind), which is audited and emits `AttachmentCreated`. Bytes are stored write-once under the key `attachments/<company_id>/<sha256>`, in a store with object versioning or object lock where the store offers it (DS-37); an object is never overwritten or changed. The endpoint copies the temporary bytes to that key only when no object is there yet. A daily job sweeps temporary bytes that no attachment row references after 24 hours; no attachment row ever names a temporary key.
Source: ADR-0038.R13, .N2

R8. The upload errors are `attachment_too_large` (category `too_large`, HTTP 413) and `attachment_type_not_allowed`.
Source: ADR-0038.R13

R9. The list of allowed types is installation data: PDF; PNG, JPEG and WebP (not SVG); XML; CSV; XLSX, recognised by its ZIP content types; and e-mail messages. The type is detected from the bytes. A vCard file is not an allowed type in Phase 1.
Source: ADR-0038.R13, .N1

R10. Photos, business cards, delivery notes, voice and inquiry attachments, and every attachment from inbound e-mail, are labelled `personal` as a whole at creation. The label is never lowered; extractions take it or a higher one (ADR-0057.R19).
Source: ADR-0038.R13.N1

### Scan state machine

R11. `attachment.state` is one of `pending_scan`, `clean` and `rejected`. A new attachment emits `AttachmentCreated`. A consumer on `integrations` runs the scanner and records the outcome. A scanner outage retries and is eventually held (ADR-0013.R8).
Source: ADR-0038.R14

R12. A rejected attachment stops being served at once, and the transaction that records the rejection sets its `bytes_released_at`; its bytes are physically removed only by the orphan sweep (R21), after the grace period. Its links are removed with a work item (kind `attachment_rejected`). A new upload of the same SHA-256 as a rejected row is refused with `attachment_rejected`. An upload matching a pending row reuses it.
Source: ADR-0038.R14, .N3

R13. Bytes that are not `clean` are never served, to people or agents: download and parsing fail with `attachment_not_available`. An attachment linked to a document follows that document's read owner scope (ADR-0054.R15). An attachment linked to a message (`target_table` `message`) is served only to those who may read the message's conversation now; withdrawing a message, and message retention, end its links (ADR-0076.R4, ADR-0076.R10).
Source: ADR-0038.R14, .N2, .N4

R14. `Post` of a document with a linked attachment that is not `clean` is rejected with `attachment_not_available`. `documents` reads the state through `attachments.contract`, an import inside layer 2 (ADR-0022, ADR-0027.R1).
Source: ADR-0038.R14

R15. `attachment_scan_mode` is an installation setting: `required`, or `optional`, under which attachments pass with the check result `scan_unavailable` when no scanner is deployed. A `production` installation requires `attachment_scan_mode` = `required`, checked at startup.
Source: ADR-0038.R14, .N5

R16. Attachments from outside content are untrusted (ADR-0029.R10).
Source: ADR-0038.R14

### Retention, release and the orphan sweep

R17. `Post` sets `attachment.is_accounting_evidence` on every linked attachment; it is never unset. Linking a generated file to a posted document, or to a statutory report filing as the submitted file, also sets it (ADR-0049.R19, ADR-0049.R28). Bytes of such an attachment are kept for the period of the setting `attachments.evidence_retention_years` after its last link ends (DDL column `last_link_ended_at`, interim). The setting is a regime setting with no core default (unset): the period is a legal rule the localization package supplies as flagged package content, verified or unverified (ADR-0016.R12). While it is unset or unverified the bytes are never purged (ADR-0063.R29).
Source: ADR-0038.R15, .N1, .N3

R18. The bytes of an attachment that is not accounting evidence are released when its last link goes, including at erasure (ADR-0019.R10).
Source: ADR-0038.R15, .N2

R19. The database and the attachment store share one restore point. No object is physically deleted while a database restore point could still name it. Where a rule deletes bytes (a rejection, the last link of an ordinary attachment, an erasure, the end of retention), the transaction only sets `attachment.bytes_released_at`, and the bytes are no longer served. A rejected attachment and an erased subject's bytes stop being served at once; they are physically gone within the grace period, the window in which database backups still hold the erased rows.
Source: ADR-0038.R15.N2

R20. `attachments.delete_grace_days` (installation, a deployment value, default 35, bounds 7 to 3,650) must be at least the database's point-in-time-recovery window that the deployment configures (DS-37); the startup step refuses to start when it is shorter. DS-37 chooses the store, its versioning or object lock, and the recovery window.
Source: ADR-0038.R15.N2

R21. `RunAttachmentOrphanSweep` (module `attachments`, effect class `other`, installation scope, a daily system job, `is_internal_only`) compares the store's objects with the attachment rows. It deletes an object only when it is an orphan older than the grace period: every row naming its key set `bytes_released_at` more than the grace period ago, or no row names it and the object was written more than the grace period ago. It sets `bytes_deleted_at` on those rows. Attachment rows are never deleted.
Source: ADR-0038.R15.N2

R22. Restore procedure: restore the database to a time T inside the recovery window. Every object an attachment row named at T without a release still exists, because only objects released or written before now minus the grace period have been deleted. Objects written after T are orphans to the restored database, and the sweep deletes them once they are older than the grace period. The store's versioning or object lock covers operator error.
Source: ADR-0038.R15.N2

### Document intake: the seam and its ownership

R23. Document intake is one seam, not one feature per case. A `document_extraction` holds what was read from one clean attachment for one purpose; its `extraction_field` rows hold each value with its evidence, the method that produced it and the engine's own confidence, append-only. A system job, not an agent run, tries deterministic readers by a ladder first; a vision model reads last and code decides; validation rules override any confidence; people verify in the ERP. Phase 1 cases: XML supplier invoices from a mailbox go to `ImportEInvoiceRecord` by the system; PDF-only invoices get deterministic reading and full human verification, then the purchase invoice agent; business cards go through QR and vCard first to a contact change proposal; inquiry spreadsheets become rows a person turns into quotation lines. Non-XML parts of messages not matched to a partner are only stored. Drawings, PDF requests and photos without a QR code are stored and shown, and read only when the vision seat `extraction_vision_personal` is enabled. The value trust of ADR-0057.R17 is a reading of spec 03 rule 1; that reading is the default, which company settings only tighten (ADR-0063.R7).
Source: ADR-0057.D0

R24. Module `attachments` (layer 2, ADR-0022.R2) owns the tables of `DS-36-document-intake.sql` marked `[attachments]`: `document_reader`, `document_extraction`, `extraction_word`, `extraction_field`, `extraction_rule_run`, `extraction_confirmation` and `extraction_result_link`, the trust view `extraction_field_trust`, and the contract functions that write them. An extraction belongs to an attachment and a purpose, not to a document lifecycle. These tables live in a design file of their own, not in `DS-05-platform.sql`.
Source: ADR-0057.R1

R25. `attachments` declares the hook `document_reader`. Modules of any layer register readers on it and `app` (layer 6) wires them (ADR-0022.R2). A package registers its readers through the published interface `DocumentReader` (ADR-0016.R17), so `attachments` imports no module and no package.
Source: ADR-0057.R1

R26. The vision step (rung 7) is a run of the agent type `document_reader` in `agents` (layer 5, ADR-0057.R11), which writes through a registered command of `attachments`. It stays in Phase 1 as a minimal declaration: no tools, one LLM step, the vision seat `extraction_vision_personal` (ADR-0057.R21) disabled until a provider is configured and a data processing permission covers it, per-run ceilings and its evaluation set. The deterministic ladder runs first, and vision values stay untrusted until verified (ADR-0078.R1, ADR-0078.R8).
Source: ADR-0057.R1, .N1

R27. Mapping rules (ADR-0057.R24) are owned by `master_data` (layer 3), section `[master_data]` of the same DDL file, because they name partners. The data-processing permission (ADR-0057.R20) has its table and contract function in `agent_runs` (layer 2), section `[agent_runs]`, and its commands in `agents` (layer 5), like `agent_promotion_evidence` and `CreateAgentPromotionEvidence` (ADR-0050.R1, ADR-0050.R14).
Source: ADR-0057.R1

### Purposes and requesting an extraction

R28. `document_extraction.purpose` is one of the values below; `delivery_note` is reserved for later (ADR-0057.R29). A purpose names its authorization leaf, its required fields, its validation rules (ADR-0057.R14), its accounting fields (ADR-0057.R19) and the risk order of the verification screen (ADR-0057.R22). Purposes are code, registered by the module that consumes them. Purpose, leaf (ADR-0054), consumer:
- `supplier_invoice`: leaf `purchase_invoice`; consumers `purchasing`, `tax`.
- `contact_card`: leaf `partner`; consumer `crm`.
- `inquiry_lines`: leaf `quotation`; consumer `sales`.
- `product_source` (ADR-0062): leaf `production_structure`; consumer `production`.
- `shop_floor_report`: leaf `operation_confirmation`; consumer `production`. It reads order number, operation number, yield, scrap, scrap reason text, lot and posting date, from spreadsheets, photos or an operator's message; a mailbox may carry it as `document_intake_purpose` (ADR-0064.R26).
- `certificate_of_analysis`: leaf `inspection_lot`; consumer `quality`. It reads the supplier lot code, the item code and, per line, the characteristic (`code`), value, unit and stated verdict. Results drafted from it stay unconfirmed until a person confirms them (ADR-0070.R11).
Source: ADR-0057.R2, .N1, .N2

R29. `RequestDocumentExtraction` (module `attachments`, effect class `other`, verb Request at `edit` on the purpose's leaf) requests an extraction.
- Payload: `attachment_id`, `purpose`, optional `partner_id` (a person's statement of whose document it is). The mailbox route also passes `inbound_message_id` (ADR-0057.R25).
- Who: a person, or the mailbox route as `system` on behalf of the mailbox owner (ADR-0057.R25).
- Checks: the attachment is `clean` (`attachment_not_available`, R13); one record per company, attachment and purpose (`extraction_purpose_exists`, naming the existing record).
- Result: a `document_extraction` in state `pending` with the attachment's SHA-256, detected media type and data label (ADR-0057.R19), and the event `DocumentExtractionRequested`.
- Allowed types stay those of R9: PDF, PNG, JPEG, WebP, XML, CSV, XLSX and e-mail messages. A vCard is read from a QR code.
Source: ADR-0057.R3

### The ladder runner

R30. The ladder runner is the external consumer `document_extraction_runner` of `DocumentExtractionRequested`, a long job on queue `jobs` (ADR-0031.R15, ADR-0013.R10). It runs as `system` on behalf of `requested_by_user_id`, calls no LLM, and holds no transaction while it reads.
Source: ADR-0057.R4

R31. The media type comes from the bytes (magic numbers and container structure), never from the file name. The runner records `document_kind`: `xml`, `pdf_embedded_xml`, `pdf_text`, `pdf_image`, `image`, `spreadsheet` or `email`.
Source: ADR-0057.R4

R32. The runner tries the rungs in this order (rung, reader, Phase 1):
- Rung 1 `structured_xml`: structured e-invoice and order XML: package readers for national e-invoice formats, selected by schema version (R43); core-neutral readers for CII and UBL. Phase 1: package readers yes; CII and UBL designed, built when a company needs them.
- Rung 2 `embedded_xml`: XML embedded in a PDF (a hybrid invoice): the PDF's embedded files are listed first and an XML found there goes to the readers of rung 1. Phase 1: detection yes; parsing with rung 1.
- Rung 3 `qr_vcard`: QR and barcodes on an image or page; vCard and MeCard payloads parsed into contact fields. Phase 1: yes.
- Rung 4 `spreadsheet`: cell values of XLSX and CSV, never formulas. Phase 1: yes.
- Rung 5 `pdf_text`: words and positions from the PDF text layer, kept only where OCR of the rendered page confirms each word at its position (ADR-0057.R18). Phase 1: yes.
- Rung 6 `ocr_words`: OCR words with normalized boxes and line numbers, then deterministic field anchors (package label anchors and the partner's mapping rules, ADR-0057.R24). Phase 1: yes, local engine (R41).
- Rung 7 `vision`: the `document_reader` agent run (ADR-0057.R11). Designed; runs only where the seat is enabled (ADR-0057.R21).
Source: ADR-0057.R4

R33. A rung's record is valid when every required field of the purpose has status `found` and every rule of the purpose passes in the rule run that follows it (ADR-0057.R14). The runner stops at the first valid record. When no rung gives a valid record, the runner keeps the union of what the rungs found, an earlier rung's value winning for a field, and the extraction goes to `needs_review`.
Source: ADR-0057.R4

R34. `document_extraction.reader_attempts` lists, per rung tried, the reader code and version and its outcome (`not_applicable`, `invalid`, `partial`, `valid`, `error` with a code). A reader error moves to the next rung; it never fails the job.
Source: ADR-0057.R4

R35. The runner writes through `RecordDocumentExtraction` (module `attachments`, effect class `other`, registered for the runner alone and on no agent tool list): the words (ADR-0057.R9), the fields (ADR-0057.R8), the first rule run (ADR-0057.R14), the attempts, `final_reader_id`, the flags and the new state, `extracted` or `needs_review`. It is the only command that sets the flags (`hidden_text_suspected`, `injection_signal`, `is_full_review_required`) and the `signature_state`, and only while the record is `pending`. It emits `DocumentExtractionRecorded`. A `needs_review` record raises the work item `document_extraction_review` (ADR-0057.R33), except an XML whose e-invoice record is imported, whose one human task is the record's (ADR-0057.R25).
Source: ADR-0057.R4

R36. As soon as the package's supplier-invoice key fields are found, the runner checks the key level of ADR-0057.R15. A hit gives the check result `duplicate_key_found`, shown first on the screen, and `VerifyDocumentExtraction` then refuses with `duplicate_external_document`, so nobody verifies a duplicate.
Source: ADR-0057.R4

### The reader contract

R37. XML readers resolve no DTD and no external entity, expand no entity, and refuse a document nested deeper than 64 levels or larger than the attachment limit (`e_invoice_record_unreadable` for the e-invoice reader). A refusal is the rung's error, never a partial record.
Source: ADR-0057.R5

R38. A reader is the pure function `read(bytes, derived, context) -> ReaderResult`: network-free, deterministic, with no LLM, no clock and no database access. `context` holds the purpose, the company's regime settings the reader declares, and the partner's active mapping rules when a partner is known (ADR-0057.R25 says which partner).
Source: ADR-0057.R5

R39. Each reader declares `code` (`<owner>.<name>`, for example `core.spreadsheet_cells`), a semver `version`, its rung, the document kinds and purposes it reads, and the settings it uses. At startup the registry writes one immutable `document_reader` row per (`code`, `version`) with its content hash (`content_hash`), like `agent_type_version` (ADR-0050.R12). Changing a reader changes its version. The row also holds `package_code`: the localization package that registered the reader, null for core and module readers (DDL).
Source: ADR-0057.R5

R40. A reader returns typed fields, each with status `found`, `not_found` or `illegible`, its value as printed (`value_raw`), its evidence (ADR-0057.R10) and, where the engine gives one, the engine's own confidence. A reader never forces a value: a field it cannot read is `not_found` or `illegible`.
Source: ADR-0057.R5

R41. OCR runs through the adapter interface `OcrEngine` (installation component, DS-37). Phase 1 uses a self-hosted engine on the installation's own hardware, so OCR sends nothing out. Words come in reading order with a line number per page. A cloud layout service would be a later adapter under the data-processing policy (ADR-0057.R20).
Source: ADR-0057.R5

R42. Core readers hold no language, country or format of their own. Language packs for OCR, label anchors, number and date formats, tax ID rules and unit names come from the company's localization package (ADR-0053.R1).
Source: ADR-0057.R5

### The structured e-invoice reader

R43. The structured e-invoice reader is the `EInvoiceRecordReader` of ADR-0051.R20, which the localization package implements. It registers on the `document_reader` hook at rung 1 for the national format its package declares. It reads the root element, namespace and declared version, and selects the parser for that version. A version it has no parser for returns `e_invoice_schema_unknown` with the found version in `details`; no record is created, and the extraction goes to `needs_review` with the attachment kept.
Source: ADR-0057.R6

R44. The reader checks offline: the schema; the arithmetic of ADR-0057.R14; the presence of the format's clearance code where the format requires one; and the signature.
Source: ADR-0057.R6

R45. `signature_state` is one of:
- `passed`, only when all of these hold: the signature over the business data is cryptographically valid; the signing certificate chains to an authority the package lists; the certificate was valid at the signing time the file states; and the certificate's subject identifier equals the seller's tax ID in the file, by the mapping the package defines;
- `signer_mismatch`: valid and chained, but the subject is not the seller (or the package cannot map it);
- `failed`: invalid, unchained or expired at signing;
- `absent`: the file carries no signature; when the package's format declares the signature mandatory, the reader reports `failed` instead;
- `not_applicable` for every other document kind.
Source: ADR-0057.R6

R46. Revocation cannot be checked offline. It is the e-invoice add-on's status check (DS-24); until it runs, `authority_status` stays `unchecked` (ADR-0051.R20).
Source: ADR-0057.R6

R47. The core holds only the generic `e_invoice_record` contract (ADR-0051.R20) and the schema-version selection of R43. Which legal texts define a format, and their versions, are the package's (ADR-0057.R30).
Source: ADR-0057.R6

## Invariants

Statements are those of `invariants.csv`. The `INV` rows of the extraction tables stand in the chunks that state the rules their catalog source names.

| Invariant | Name | Check point | Statement | Protects |
| --- | --- | --- | --- | --- |
| `INV-83` | `attachment_links_resolve` | day | Every `attachment_link` points to an existing row of its target table within the attachment's company (area `platform`; first step 1). | R3 |

## Edge cases

| Edge case | Name | Case | Outcome | Protects |
| --- | --- | --- | --- | --- |
| `EC-134` | `e_invoice_unsigned_first` | An unsigned XML e-invoice is imported quarantined and holds no key; the genuine signed invoice with the same key arrives later, is imported, supersedes the quarantined record and raises `e_invoice_record_superseded` (area `safety`; first step 5). | `must_succeed` | R45; ADR-0057.R25 |
| `EC-145` | `e_invoice_signer_mismatch` | An XML e-invoice signed with a valid certificate of another company names a known supplier's tax ID; `signer_mismatch`, quarantined, and no agent run until a person confirms the supplier (area `safety`; first step 5). | `must_succeed` | R45 |

## Settings

| Key | Value type | Scope | Core default | Direction | Rule |
| --- | --- | --- | --- | --- | --- |
| `attachments.delete_grace_days` | integer, bounds `7..3650` | installation (storage `deployment`) | 35 | `higher_tighter` | R20 |
| `attachments.evidence_retention_years` | integer, bounds `1..` | regime (storage `regime_setting`) | unset | `neutral` | R17 |

`attachment_max_bytes` (R6) and `attachment_scan_mode` (R15) are named by the rules as installation settings and have no row in `settings.csv`.

## UI annotations

The sources of this chunk state no floorplan, title, facet, field annotation or tile. The work item kinds of `attachments` have their rows in the one table of chunk 3: `attachment_rejected`, raised by R12, and `document_extraction_review`, raised by R35.

## Conflicts

CONFLICT ADR-0027.R2: ADR-0038.R15.N2 governs the deletion of bytes; a transaction only releases them (`bytes_released_at`) and the orphan sweep deletes them after the grace period (R4, R19).
CONFLICT ADR-0038.R14: ADR-0038.R14.N3 governs; "their bytes are deleted at once" is not restated, a rejected attachment is released and its bytes go with the orphan sweep (R12).
CONFLICT ADR-0038.R14.N5: this note governs the scan mode of ADR-0038.R14; the requirement on `production` installations is decided and checked at startup, so the marks "flagged" and "open question" are not restated (R15).
CONFLICT ADR-0038.R15: ADR-0038.R15.N3 governs the setting; its registry key is `attachments.evidence_retention_years` with no core default, so the seeded period and the name `attachment_retention_years` are not restated (R17).
CONFLICT ADR-0057.D0: ADR-0063.R7 (with ADR-0057.R17.N1) makes the reading of value trust the default, so "asked of the author" is not restated (R23).
CONFLICT ADR-0038.R15.N2: this note governs where ADR-0038.R15 says bytes are deleted when the last link goes; the transaction sets `bytes_released_at` and physical deletion waits for the grace period (R18, R19).

## Proposed (not law)

None

## Trace

| Source | Where |
| --- | --- |
| ADR-0016.R17.N3 | ref: ADR-0016.R17.N3 |
| ADR-0022.R2.N4 | ref: ADR-0022.R2.N4 |
| ADR-0027.R2 | R1-R4 |
| ADR-0027.R2.N1 | R2, R5 |
| ADR-0027.R17 | ref: ADR-0027.R17 |
| ADR-0038.R13 | R6-R9 |
| ADR-0038.R13.N1 | R9, R10 |
| ADR-0038.R13.N2 | R7 |
| ADR-0038.R14 | R11-R16 |
| ADR-0038.R14.N1 | R5 |
| ADR-0038.R14.N2 | R13 |
| ADR-0038.R14.N3 | R12 |
| ADR-0038.R14.N4 | R13 |
| ADR-0038.R14.N5 | R15 |
| ADR-0038.R15 | R4, R17, R18 |
| ADR-0038.R15.N1 | R17 |
| ADR-0038.R15.N2 | R4, R18-R22 |
| ADR-0038.R15.N3 | R17 |
| ADR-0050.R1.N1 | ref: ADR-0050.R1.N1 |
| ADR-0050.R14.N6 | ref: ADR-0050.R14.N6 |
| ADR-0050.R25.N1 | ref: ADR-0050.R25.N1 |
| ADR-0050.R30.N1 | ref: ADR-0050.R30.N1 |
| ADR-0051.D0.N2 | ref: ADR-0051.D0.N2 |
| ADR-0051.R5.N3 | ref: ADR-0051.R5.N3 |
| ADR-0051.R7.N1 | ref: ADR-0051.R7.N1 |
| ADR-0051.R9.N1 | ref: ADR-0051.R9.N1 |
| ADR-0057.D0 | R23 |
| ADR-0057.R1 | R24-R27 |
| ADR-0057.R1.N1 | R26 |
| ADR-0057.R2 | R28 |
| ADR-0057.R2.N1 | R28 |
| ADR-0057.R2.N2 | R28 |
| ADR-0057.R3 | R29 |
| ADR-0057.R4 | R30-R36 |
| ADR-0057.R5 | R37-R42 |
| ADR-0057.R6 | R43-R47 |
