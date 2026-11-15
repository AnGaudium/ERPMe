# ADR-0057: Document intake and extraction

Status: accepted (2026-11-15) under ADR-0005, reviewed by Claude Fable 5.2 (builder Claude Opus 5.5) after five review rounds. Design items: DS-36 (the `attachments` module: extraction records), DS-34 (workflow inputs), with the DS-24 seam named. Related decisions: D2, D12. Principles 2, 3, 7, 12, 13. ADR-0008, ADR-0013, ADR-0016, ADR-0017, ADR-0019, ADR-0022, ADR-0027, ADR-0029, ADR-0030, ADR-0038, ADR-0040, ADR-0042, ADR-0043, ADR-0044, ADR-0050, ADR-0051, ADR-0052, ADR-0053, ADR-0054, ADR-0056; spec 03, 13, 14, 17. Product engineering from extracted sources: [ADR-0062](0062-product-engineering-workflow.md).

## Decision

A capability check found multimodal input largely undesigned: business-card photos, a mailbox receiving XML or PDF supplier invoices, and inquiries with attachments were stored but never read, and no record held a value extracted from a page together with its evidence. This ADR adds one seam instead of one feature per case.

**One record per attachment and purpose.** A `document_extraction` holds what was read from one clean attachment for one purpose. Its `extraction_field` rows hold each value with its evidence (an XPath, a cell, a character span with its region, or a run of OCR words on one line), the method that produced it and the engine's own confidence. Rows are append-only: a correction is a new row that supersedes the earlier one and keeps its value type. Validation results live in their own append-only rule runs, re-run on every correction, and a person's confirmation is a row of its own.

**Deterministic first, by a ladder.** A system job, not an agent run, identifies the file by its bytes and tries readers in a fixed order: structured XML, XML embedded in a PDF, QR codes with vCard, spreadsheet cells, the PDF text layer confirmed by OCR at the same position, OCR words with positions, and a vision model last. The first rung that yields a valid record wins. Readers are pure functions that the core, modules and localization packages register through a hook.

**A vision model reads, code decides.** The vision step is a tool-less agent run that returns, per field, the value as printed, the OCR word IDs it read it from, and found, not found or illegible. Code checks that the value stands at those words, which must be consecutive on one line, numbers exactly. An unaligned value is a greyed suggestion that never fills a draft. Totals and taxes are always recomputed by code.

**Rules over confidence.** Closed shapes per value type, arithmetic, check digits, the buyer's tax ID, currency and date checks and duplicate detection override any confidence. Bank details on a document never change partner master data.

**People verify in the ERP.** A verification screen shows the page beside the fields, risky fields first, keyboard first, and keeps machine-checked apart from human-confirmed. A person's corrections become per-partner mapping rules, stored as data and changed only through proposals.

**Two kinds of trust.** Instruction taint stays as designed: free text from outside narrows a run to its subject partner and to drafts. Value trust is new and is computed when a field is read: a field's normalized value that fits the closed shape of its type and passed every rule of the extraction's latest rule run, read by a deterministic reader or confirmed by a person, carries no instruction and does not taint a run that reads only such values. Trust means "carries no instruction", not "is true", and covers the normalized value only: the raw text and the evidence are always served as untrusted. Free text, URLs, e-mails, phones, and codes and unit text that resolve to no record are always untrusted; a failed or mismatched signature or suspected hidden text makes every field untrusted. This widens the sources that can give trusted values (OCR, spreadsheets, cards) and narrows the conditions (closed shapes, at least one passed rule); it is a reading of spec 03 rule 1, asked of the author.

**Signatures that identify the seller.** A structured e-invoice counts as signed only when the signature is valid, chains to an authority the package lists, was made while the certificate was valid, and the certificate's subject is the seller's tax ID. Anything else is quarantined: it holds no duplicate key, and a person confirms its supplier before any agent run. Authenticity belongs to quarantine, not to value trust: an unsigned record is quarantined, but its well-shaped values are not made untrusted, unless the package's format declares the signature mandatory.

**Personal data under a neutral policy.** Photos, business cards, delivery notes, voice and inquiry attachments are personal as a whole. The core registers a regime-neutral data-processing policy without a default: per data class, whether a model provider may process it and whether processing in another country needs a recorded assessment; a regime that declares none fails closed. A new seat class, `extraction_vision_personal`, is designed and stays disabled until a company configures a permitted provider under that policy. Packages supply their regime's values as data.

**Phase 1 cases.** XML supplier invoices from a mailbox go to `ImportEInvoiceRecord` by the system; PDF-only invoices get deterministic reading and full human verification, then the purchase invoice agent; business cards go through QR and vCard first to a contact change proposal; inquiry spreadsheets become rows a person turns into quotation lines. Non-XML parts of messages not matched to a partner are only stored. Drawings, PDF requests and photos without a QR code are stored and shown, and read only when the vision seat is enabled.

### Rules

**Ownership and records**

1. Module `attachments` (layer 2, ADR-0022 rule 2) owns the tables of [DS-36-document-intake.sql](../design/DS-36-document-intake.sql) marked `[attachments]`: `document_reader`, `document_extraction`, `extraction_word`, `extraction_field`, `extraction_rule_run`, `extraction_confirmation` and `extraction_result_link`, the trust view `extraction_field_trust`, and the contract functions that write them.
   - **Why `attachments`.** An extraction belongs to an attachment and a purpose, not to a document lifecycle, and `documents` already imports `attachments.contract` (ADR-0038 rule 14). No new module is needed.
   - **Readers through a hook.** `attachments` declares the hook `document_reader`. Modules of any layer register readers on it and `app` (layer 6) wires them (ADR-0022 rule 2, hooks). A package registers its readers through the published interface `DocumentReader` (ADR-0016 rule 17), so `attachments` imports no module and no package.
   - **The vision step** is a run of the agent type `document_reader` in `agents` (layer 5, rule 11), which writes through a registered command of `attachments`.
   - **Mapping rules** (rule 24) are owned by `master_data` (layer 3), section `[master_data]` of the same file, because they name partners.
   - **The data-processing permission** (rule 20): table and contract function in `agent_runs` (layer 2), section `[agent_runs]`; its two commands in `agents` (layer 5), like `agent_promotion_evidence` and `CreateAgentPromotionEvidence` (ADR-0050 rules 1, 14).
   - **The DDL file.** These tables live in a design file of their own, [DS-36-document-intake.sql](../design/DS-36-document-intake.sql), not in DS-05-platform.sql. The platform lab (`t15`) checks DS-05's installation tables, nullable company columns and policy counts as closed lists, and other drafts edit DS-05 now; a file of its own loads through `load_all.py` with every other file and keeps those checks stable.
2. Purposes. `document_extraction.purpose` is one of `supplier_invoice`, `contact_card`, `inquiry_lines` and `product_source` ([ADR-0062](0062-product-engineering-workflow.md)); `delivery_note` is reserved for later (rule 29). A purpose names its authorization leaf, its required fields, its validation rules (rule 14), its accounting fields (rule 19) and the risk order of the verification screen (rule 22). Purposes are code, registered by the module that consumes them.

   | Purpose | Leaf (ADR-0054) | Consumer |
   | --- | --- | --- |
   | `supplier_invoice` | `purchase_invoice` | `purchasing`, `tax` |
   | `contact_card` | `partner` | `crm` |
   | `inquiry_lines` | `quotation` | `sales` |
   | `product_source` | `production_structure` | `production` |
3. Requesting an extraction, `RequestDocumentExtraction` (module `attachments`, effect class `other`, verb Request at `edit` on the purpose's leaf):
   - **Payload:** `attachment_id`, `purpose`, optional `partner_id` (a person's statement of whose document it is).
   - **Who:** a person, or the mailbox route as `system` on behalf of the mailbox owner (rule 25).
   - **Checks:** the attachment is `clean` (`attachment_not_available`, ADR-0038 rule 14); one record per company, attachment and purpose (`extraction_purpose_exists`, naming the existing record).
   - **Result:** a `document_extraction` in state `pending` with the attachment's SHA-256, detected media type and data label (rule 19), and the event `DocumentExtractionRequested`.
   - **Allowed types** stay ADR-0038 rule 13's: PDF, PNG, JPEG, WebP, XML, CSV, XLSX and e-mail messages. A vCard file is not an allowed type in Phase 1; a vCard is read from a QR code.

**The reader ladder**

4. The ladder runner is the external consumer `document_extraction_runner` of `DocumentExtractionRequested`, a long job on queue `jobs` (ADR-0031 rule 15; ADR-0013 rule 10). It runs as `system` on behalf of `requested_by_user_id`, calls no LLM, and holds no transaction while it reads.
   - **Identify by bytes.** The media type comes from the bytes (magic numbers and container structure), never from the file name. The runner records `document_kind`: `xml`, `pdf_embedded_xml`, `pdf_text`, `pdf_image`, `image`, `spreadsheet` or `email`.
   - **Rungs, in this order:**

     | Rung | Reader | Phase 1 |
     | --- | --- | --- |
     | 1 `structured_xml` | Structured e-invoice and order XML: package readers for national e-invoice formats, selected by schema version (rule 6); core-neutral readers for CII and UBL | Package readers yes; CII and UBL designed, built when a company needs them |
     | 2 `embedded_xml` | XML embedded in a PDF (a hybrid invoice): the PDF's embedded files are listed first and an XML found there goes to rung 1's readers | Detection yes; parsing with rung 1 |
     | 3 `qr_vcard` | QR and barcodes on an image or page; vCard and MeCard payloads parsed into contact fields | Yes |
     | 4 `spreadsheet` | Cell values of XLSX and CSV, never formulas | Yes |
     | 5 `pdf_text` | Words and positions from the PDF text layer, kept only where OCR of the rendered page confirms each word at its position (rule 18) | Yes |
     | 6 `ocr_words` | OCR words with normalized boxes and line numbers, then deterministic field anchors (package label anchors and the partner's mapping rules, rule 24) | Yes, local engine (rule 5) |
     | 7 `vision` | The `document_reader` agent run (rule 11) | Designed; runs only where the seat is enabled (rule 21) |

   - **Stop at the first valid record.** A rung's record is valid when every required field of the purpose has status `found` and every rule of the purpose passes in the rule run that follows it (rule 14). The runner stops there. When no rung gives a valid record, the runner keeps the union of what the rungs found, an earlier rung's value winning for a field, and the extraction goes to `needs_review`.
   - **Attempts are recorded.** `document_extraction.reader_attempts` lists, per rung tried, the reader code and version and its outcome (`not_applicable`, `invalid`, `partial`, `valid`, `error` with a code). A reader error moves to the next rung; it never fails the job.
   - **Recording.** The runner writes through `RecordDocumentExtraction` (module `attachments`, effect class `other`, registered for the runner alone and on no agent tool list): the words (rule 9), the fields (rule 8), the first rule run (rule 14), the attempts, `final_reader_id`, the flags and the new state, `extracted` or `needs_review`. It is the only command that sets the flags and the signature state, and only while the record is `pending`. It emits `DocumentExtractionRecorded`. A `needs_review` record raises the work item `document_extraction_review` (rule 33), except an XML whose e-invoice record is imported, whose one human task is the record's (rule 25).
   - **Early duplicate check.** As soon as the package's supplier-invoice key fields are found, the runner checks rule 15's key level; a hit gives the check result `duplicate_key_found`, shown first on the screen, and `VerifyDocumentExtraction` then refuses with `duplicate_external_document`, so nobody verifies a duplicate.
5. The reader contract:
   - **Safe XML.** XML readers resolve no DTD and no external entity, expand no entity, and refuse a document nested deeper than 64 levels or larger than the attachment limit (`e_invoice_record_unreadable` for the e-invoice reader); a refusal is the rung's error, never a partial record.
   - **Pure.** A reader is `read(bytes, derived, context) -> ReaderResult`: network-free, deterministic, with no LLM, no clock and no database access. `context` holds the purpose, the company's regime settings the reader declares, and the partner's active mapping rules when a partner is known (rule 25 says which partner).
   - **Declared.** Each reader declares `code` (`<owner>.<name>`, for example `core.spreadsheet_cells`), a semver `version`, its rung, the document kinds and purposes it reads, and the settings it uses. At startup the registry writes one immutable `document_reader` row per (code, version) with its content hash, like `agent_type_version` (ADR-0050 rule 12). Changing a reader changes its version.
   - **Output.** Typed fields, each with status `found`, `not_found` or `illegible`, its value as printed (`value_raw`), its evidence (rule 10) and, where the engine gives one, the engine's own confidence. A reader never forces a value: a field it cannot read is `not_found` or `illegible`.
   - **OCR engine.** OCR runs through the adapter interface `OcrEngine` (installation component, DS-37). Phase 1 uses a self-hosted engine on the installation's own hardware, so OCR sends nothing out. Words come in reading order with a line number per page. A cloud layout service would be a later adapter under the data-processing policy (rule 20).
   - **Language-neutral core.** Core readers hold no language, country or format of their own. Language packs for OCR, label anchors, number and date formats, tax ID rules and unit names come from the company's localization package (ADR-0053 rule 1).
6. The structured e-invoice reader:
   - **The seam.** It is ADR-0051 rule 20's `EInvoiceRecordReader`, which the localization package implements. It registers on the `document_reader` hook at rung 1 for the national format its package declares.
   - **Schema-version selection.** The reader reads the root element, namespace and declared version, and selects the parser for that version. A version it has no parser for returns `e_invoice_schema_unknown` with the found version in `details`; no record is created, and the extraction goes to `needs_review` with the attachment kept.
   - **What it checks offline:** the schema; the arithmetic of rule 14; the presence of the format's clearance code where the format requires one; and the signature.
   - **`signature_state`** is one of:
     - `passed`, only when all four hold: the signature over the business data is cryptographically valid; the signing certificate chains to an authority the package lists; the certificate was valid at the signing time the file states; and the certificate's subject identifier equals the seller's tax ID in the file, by the mapping the package defines;
     - `signer_mismatch`: valid and chained, but the subject is not the seller (or the package cannot map it);
     - `failed`: invalid, unchained or expired at signing;
     - `absent`: the file carries no signature; when the package's format declares the signature mandatory, the reader reports `failed` instead;
     - `not_applicable` for every other document kind.
   - **Revocation** cannot be checked offline. It is the e-invoice add-on's status check (DS-24); until it runs, `authority_status` stays `unchecked` (ADR-0051 rule 20 note).
   - **The core** holds only the generic `e_invoice_record` contract (ADR-0051 rule 20 note) and this selection. Which legal texts define a format, and their versions, are the package's (rule 30).
7. `document_extraction` columns (company data):
   - **Identity:** `id`, `company_id`, `attachment_id`, `purpose`, `attachment_sha256`, `detected_media_type`, `document_kind`, `page_count`; unique per (company, attachment, purpose).
   - **Labels and flags:** `data_label`, copied from the attachment and never lower (rule 19); `hidden_text_suspected` (rule 18); `injection_signal` (rule 18); `is_full_review_required`, true when hidden text is suspected. All three flags and `signature_state` are set only by the recording command while the record is `pending` (rule 4), and never cleared.
   - **Result:** `state`, `reader_attempts`, `final_reader_id` (never a vision reader for state `extracted`), `signature_state`, `partner_id` (rule 25), and the subjects it led to in `extraction_result_link` (rule 19).
   - **Origin and verification:** `inbound_message_id` (the message it came with, if any), `requested_by_user_id`, `verified_by_user_id`, `verified_at`, `rule_overrides` (the failed cross-field rules a person verified past, each with a reason, rule 23), `canceled_reason`, `recorded_at`.
   - **States:** `pending` → `extracted`, `needs_review` or `canceled`; `extracted` → `needs_review`, `verified` or `canceled`; `needs_review` → `verified` or `canceled`; `verified` and `canceled` are final. `pending → canceled` is the system's only, for a rendering of a parsed XML (rule 25). `extracted` means a deterministic rung gave a valid record and the extraction itself needs no person; for an XML, any human task that remains (a supplier confirmation, a key conflict, an import past the quarantine cap) belongs to its e-invoice record or its mailbox, not to the extraction. A trigger holds the transitions. No field, rule run or confirmation is appended to an extraction in a final state.
8. `extraction_field` columns (company data, append-only):
   - **Value:** `field_path` (for example `seller_tax_id`, `lines[3].unit_price`), `value_type` (rule 17's list), `value_raw` (as printed or stored), `value_normalized` (canonical: ADR-0006 rule 13 decimals, ISO dates, normalized tax IDs, the codes of resolved records and units), `status`. Normalizers are strict: the whole raw value must parse, nothing is discarded, and a value that does not normalize exactly fails its shape rule. Trust covers `value_normalized` only; `value_raw` and `evidence` hold outside text and are always served as untrusted columns.
   - **Provenance:** `method` (`parsed`, `ocr`, `vision_aligned`, `vision_unaligned`, `computed`, `human`), `evidence_kind` and `evidence` (rule 10), `document_reader_id`, `agent_run_id` (vision rows), `entered_by_user_id` (human rows).
   - **Confidence:** `confidence_raw` (the engine's own score, for example an OCR word confidence; never a model's self-report, ADR-0050 rule 35) and `confidence_calibrated` (rule 13).
   - **No stored trust.** Rule results and trust are not columns of the row: rule results are rule runs (rule 14), confirmations are rows of their own (rule 23), and trust is computed when the field is read (rule 17).
   - **Corrections.** A correction is a new row with method `human`, entered by a person, that names the row it supersedes, with the same extraction, field path and value type. A machine row (a vision row) may supersede only a row with status `not_found` or `illegible`. Each path has one root row, and a row is superseded at most once, so the current value of a field is unique: the row of that path that no other row supersedes.
   - **Append-only.** Rows are never updated or deleted, except that erasure blanks the values and evidence (rule 19).
   - **Methods.** `parsed`: a structured reader (rungs 1 to 4). `ocr`: a deterministic anchor over text-layer or OCR words (rungs 5 and 6). `vision_aligned` and `vision_unaligned`: rule 12. `computed`: a value code derived from other fields (totals, taxes, line amounts), never a model value. `human`: a person's correction.
9. `extraction_word` (company data, append-only): one row per word of a page and layer: `layer` (`ocr`, `text_layer`), `page_number`, `word_number` (reading order on the page), `line_number` (the reading-order line on the page), `cell_ref` (the cell of a detected table the word lies in, if any), `text`, the normalized box (`x0`, `y0`, `x1`, `y1` in 0..1 from the page's top left), `confidence_raw`, and for text-layer words `is_on_render` (rule 18). Word rows are personal and untrusted with their extraction. Rendered page images are not stored: the renderer is deterministic per version and resolution, and normalized boxes redraw on any rendering.
10. Evidence, by `evidence_kind`:
    - `xpath`: `{"xpath": …}` into the XML;
    - `cell`: `{"sheet": …, "cell": "C12"}`;
    - `char_span`: `{"page": n, "start": i, "end": j, "region": [x0, y0, x1, y1]}` in the reader's text of a page, with the union of its words' boxes;
    - `page_region`: `{"page": n, "region": [x0, y0, x1, y1], "word_ids": [...]}` with consecutive OCR word numbers of one line of that page;
    - `qr_payload`: `{"page": n, "region": [...], "property": "TEL;TYPE=work"}`.

    Parsed, OCR and aligned rows always carry evidence; computed rows carry none and name their inputs in their rule runs.

**The vision step**

11. The agent type `document_reader` (ADR-0050 rule 12):
    - **Trigger.** It declares the work item kind `document_extraction_review`. The wake-up consumer (ADR-0050 rule 16) starts a run when the kind is raised in a company where the agent type is not `off` and the seat is usable for the company (rule 21); otherwise the item stays with people, who key or confirm the fields on the verification screen.
    - **Precheck.** D0 ends the run `not_applicable` without an LLM call when the extraction's kind has no pages (XML, spreadsheet, e-mail), when no required field is missing or illegible, or when the extraction is under full review.
    - **Scope and taint.** Scope kind `subject`: the extraction row. `document_extraction` is an outside-content subject table, so the run starts tainted (ADR-0050 rule 15). It reads its subject, the subject's words, fields and rule runs, and its attachment's pages: a reading of the tainted read scope put to the author (open question).
    - **No tools.** Its tool list holds no query and no command for the model. Workflow code renders the pages, calls the gateway and writes the result.
    - **Input.** Per page: the rendered page image, re-encoded without metadata (rule 19), and the OCR words of that page as `(word_number, line_number, text, box)`, datamarked (rule 18); the purpose's field list with types. At most `intake.vision_max_pages` pages (default 10) per run; a longer document stays with people.
    - **Output schema** `DocumentReaderPageOutput` 1.0.0: per field path `{value_raw, word_ids, page, status}`, with `status` one of `found`, `not_found`, `illegible`. No confidence field (ADR-0050 rule 35).
    - **Writing.** After alignment (rule 12), `CreateExtractionFields` (module `attachments`, effect class `other`, `is_draft_only`, on this agent type's list for workflow code only) appends the rows, method `vision_aligned` or `vision_unaligned`, with the run as `agent_run_id`, and the rule run that follows, in the same transaction. Appending rows to an outside subject's extraction as a draft-only write is a reading put to the author (open question). The run ends `drafted` and unclaims the item, which goes back to its owner for verification.
    - **Seat:** `extraction_vision_personal` (rule 21).
12. Alignment, by code, per field the model returned with status `found`:
    - **Words named.** The word numbers must exist on the page given, be consecutive in reading order on one line (one `line_number`), lie in one table cell or in none (one `cell_ref`), and be adjacent: the horizontal distance between neighbouring words' boxes, in either direction (so right-to-left lines too), is at most 0.6 times the line height, a normal space. Otherwise the value is unaligned. A value split over lines, composed of words from several places, or joined across table cells (a quantity "2" beside a price "500") is never aligned.
    - **Exact comparison** for every value type except `text`, `url` and `email`, and for any value that contains a digit: the value's characters, without spaces, must equal the named words' characters exactly. No normalization of digits, separators or signs is allowed before the comparison; code parses the aligned text afterwards with the document's number and date formats (rule 5).
    - **Text, URLs and e-mails without digits.** Normalize the value and the named words' text (Unicode NFKC, case folding, collapsed whitespace; diacritics kept). Equal: aligned. A near match, every word within one edit of its counterpart and the same word count: aligned with the rule result `near_match`. Otherwise unaligned.
    - **Stored text.** An aligned row stores the page's text, not the model's, and its region is the union of the named words' boxes.
    - **Unaligned values** are stored with method `vision_unaligned`, are untrusted, and are shown greyed. They never fill a draft and are never confirmed as they are: a person who accepts one keys or confirms it into a `human` row.
    - **Computed fields.** Line amounts, totals and taxes are recomputed by code from aligned or parsed inputs (method `computed`) and compared with the printed values; a difference is a failed rule (rule 14), never a correction.
13. Confidence and thresholds:
    - **Raw** is the engine's score for OCR words and text-layer words; parsed values have none. A model's self-reported confidence is never asked for or stored.
    - **Calibrated** confidence per (company, reader code and version, field path) comes from the company's golden set (rule 34). Until a company has one, `confidence_calibrated` stays empty and every vision field needs a person.
    - **Thresholds are per field** and are a parameter set of the reader (ADR-0059, level 1, drafted separately). Any change of reader version, model, prompt or seat model recalibrates them from a replay of the golden set, run under the data-processing gate (rule 20), before the effective mode returns to assisted (ADR-0050 rule 14).

**Validation, duplicates and bank details**

14. Rule runs. Validation rules override confidence:
    - **`extraction_rule_run`** (append-only) holds one row per run, field and rule: the run number (increasing per extraction), the field row, the rule code, `passed` (boolean, never null) and a detail. Every run evaluates every current field. A run follows the recording, every vision write and every correction, in the same transaction as the write; a confirmation changes no value and starts no run. Trust uses only the results of the extraction's highest run number: a field without a result in that run is untrusted.
    - **The shape rule** `shape` is mandatory for every field: it checks the value against its type's closed shape (rule 17). A field without a passed `shape` result is untrusted.
    - **Supplier invoices:** quantity × unit price − discount = line amount, within half a minor unit of the document currency per line; lines sum to the net total; per tax rate, base × rate = tax amount within the package's stated-amount tolerance; net + tax − allowances + charges = gross; the buyer's tax ID equals the company's (a misdirected invoice fails); the currency is active for the company; the issue date is not after the receipt date; tax IDs, IBANs and GTINs by their check digits.
    - **Inquiry lines:** each row's quantity is a positive decimal; its unit resolves to a unit code (rule 17); its item reference fits the `code` shape; a row without a quantity fails.
    - **Product sources:** each quantity and dimension is a positive decimal with a resolved unit; codes fit the `code` shape.
    - **Contact cards:** e-mail and phone normalize by the package's rules (they stay untrusted, rule 17).
    - **Effect.** A failed rule marks the field and the extraction `needs_review`, whatever any confidence says, with the check result `extraction_rule_failed`. A purpose or field without rules has no passed rule, so its fields stay untrusted.
    - **Printed errors.** A document may be wrong as printed (a total that is not the sum of its lines). A person may verify past a failed cross-field rule only with a reason, recorded in `rule_overrides` with the check result `extraction_rule_overridden`; a failed `shape` rule is never overridden, and an overridden rule does not make its fields trusted.
15. Duplicates, against the company's full history, not only open documents:
    1. **File:** the same SHA-256 (ADR-0038: one attachment per company and hash) under the same purpose is the existing extraction (`extraction_purpose_exists`);
    2. **Key:** the package's supplier-invoice key (ADR-0030 rule 10), normalized, equal to that of an existing document or of an incoming e-invoice record that is not quarantined (rule 25): the check result `duplicate_key_found` at recording, and `duplicate_external_document` when a record or draft would be created or an extraction verified;
    3. **Near:** the same seller, gross amount within one minor unit, and issue date within 7 days, or the same seller and an invoice number whose digits are equal: the check result `duplicate_document_suspected`, advisory only.

    Levels 1 and 2 are decisive; level 3 never blocks. Its window and test are constants of the purpose, version-controlled with it.

    Note ([ADR-0063](0063-configurable-policy-settings.md), proposed 2026-11-15): the near check's window, amount tolerance and number normalization are the company settings `intake.duplicate.*` (defaults 7 days, 1 minor unit, digits only); with `intake.duplicate.near_outcome` `review`, the default, a suspected invoice posts with its open item blocked for payment and raises `duplicate_document_review`. Levels 1 and 2 cannot be switched off (rule 27).
16. Bank details. A bank account read from a document never changes partner master data and never fills a payment. When it differs from the partner's accounts, the extraction carries the check result `document_bank_account_differs`. A person who wants the change starts a bank-account change proposal, which follows the core's seeded rule (ADR-0043 rule 15; ADR-0029 rule 4).

**Trust and injection**

17. Instruction taint and value trust:
    - **Instruction taint** is unchanged: free text from outside (names, addresses, descriptions, notes) is untrusted, and a run given it becomes tainted (ADR-0029 rule 10; ADR-0050 rule 25).
    - **Closed shapes**, the `shape` rule of each value type:

      | Type | Closed shape | Trust possible |
      | --- | --- | --- |
      | `amount`, `quantity`, `percent` | A canonical decimal of at most 18 integer and 6 fraction digits | Yes |
      | `date` | A valid ISO date | Yes |
      | `currency` | A code of the core currency catalog | Yes |
      | `tax_id` | The package's tax ID rule with its check digit | Yes |
      | `bank_account` | IBAN with mod 97, or the package's national format with its check digit | Yes (still never changes master data, rule 16) |
      | `code` | Resolved to exactly one record (an item code, a partner item or supplier item code, a barcode, a manufacturer part number); the normalized value is that record's code | Yes, when resolved |
      | `unit` | Resolved to a unit code through the partner item's unit text, the unit aliases of [ADR-0056](0056-multiple-units-of-measure.md) (`uom_alias`) or a unit code; the normalized value is the code | Yes, when resolved |
      | `text`, `url`, `email`, `phone` | None | Never |

    - **Resolution in the rule run.** The `shape` rule of `code` and `unit` resolves the value deterministically against the company's records (the partner's codes when the extraction names its partner); an unresolved code or unit fails it and stays untrusted, as ADR-0051 rule 20 keeps `seller_item_code` and `unit_text` untrusted.
    - **Trust, computed when read.** The view `extraction_field_trust` gives `is_untrusted` for a field row's normalized value from the row, the extraction, the extraction's highest rule run and the confirmations:
      1. untrusted when the extraction has `hidden_text_suspected` or a `signature_state` of `failed` or `signer_mismatch`;
      2. untrusted when the type is `text`, `url`, `email` or `phone`, or the status is not `found`;
      3. a person-confirmed row (rule 23) is trusted when its `shape` result in the highest run passed;
      4. an unconfirmed row is trusted when its method is `parsed`, `ocr` or `computed`, it has at least one result in the highest run, every one passed, and `shape` passed;
      5. every other row (vision rows before confirmation) is untrusted.
    - **Effect.** The query layer serves `value_normalized` with this computed attribute in place of `is_untrusted` (ADR-0050 rule 28), and `value_raw` and `evidence` as untrusted columns always: a run that reads only trusted normalized values and field IDs is not tainted by them; reading anything else taints it (ADR-0050 rule 25). Because trust is computed, a total that a corrected line makes inconsistent becomes untrusted at once, and a confirmation makes a typed value trusted without rewriting a row.
    - **What was served.** With each extraction field it returns to a run, the dispatcher records in the step's `context_refs` the trust it served and the rule run number it used (ADR-0050 rule 19 note), so INV-642 checks what was served, not what the view says later.
    - **Status of this rule.** It reads spec 03 rule 1 ("all external content is labeled untrusted") as applying to free text and to values no deterministic check has confirmed. It widens the sources: beyond ADR-0051 rule 20's signed XML, OCR of outside pixels, spreadsheets and cards can give trusted values. It narrows the conditions: the normalized value only, a closed shape per type, codes and units only when they resolve to a record, at least one passed rule in the latest run, a person's confirmation for vision values; ADR-0051 rule 20 keeps `seller_item_code` and `unit_text` untrusted as before. Interim, as stated, until the author answers (open question).

    Note ([ADR-0063](0063-configurable-policy-settings.md), proposed 2026-11-15): this reading is the default; the company settings `intake.trust.<document_type>.<field>.require_confirmation`, `intake.trust.<document_type>.min_passed_rules` and `intake.trust.ocr_min_confidence` only tighten it, and loosening below a value in force needs `extraction_mapping` evidence (rule 7).
18. Injection defenses:
    - **Containment.** The vision model has no tools, no memory and no outbound channel; it returns only the typed schema of rule 11, and code checks every value (rule 12). An injected instruction has nowhere to go but a field whose shape cannot hold it, or free text, which is untrusted.
    - **Render, then read.** The model reads the rendered page image, never the PDF's text layer.
    - **Hidden text, by position.** A text-layer word is confirmed (`is_on_render` true) only by an OCR word of the rendered page with equal normalized text whose box overlaps it by at least half of the smaller box. A run of at least three consecutive unconfirmed text-layer words, or 20 characters, sets `hidden_text_suspected`, the check result `hidden_text_suspected` and full review (rule 17). The hidden words stay as `text_layer` rows with `is_on_render` false, shown to the reviewer as untrusted evidence. Text-layer words take part in rung 5 only where they are confirmed, and rung 5's evidence carries their region.
    - **Limits.** Text that OCR reads but people barely see (tiny or low-contrast print) is not hidden text by this test; the evidence box on the screen shows the reviewer where each value stands.
    - **Datamarking.** Any text passed to a model inside untrusted delimiters (ADR-0050 rule 8) also has a marker character between words, and the template says so (spotlighting).
    - **Classifiers.** An injection classifier, where installed, sets `injection_signal` and the check result `injection_signal`. It is a signal for the reviewer, never a gate and never a reason to trust.
19. Personal data, links and retention:
    - **Whole attachments.** Photos, business cards, delivery notes, voice and inquiry attachments are labelled `personal` as a whole when created, as is every attachment from inbound e-mail. The label is set at creation and never lowered; a reader that finds only organizations does not change it (an e-invoice record's own fields take their labels by partner kind, ADR-0019 rule 7). Extractions and their fields take the attachment's label or a higher one.
    - **Metadata.** Every derived image sent anywhere is re-encoded without EXIF, location or device metadata. The original keeps its bytes under the attachment's access rules.
    - **Redaction.** A redacted copy is still `personal`; redaction never makes an image non-personal.
    - **Result links.** `extraction_result_link` names each subject an extraction led to: `e_invoice_record`, `change_proposal`, `contact`, `partner`, `quotation`, `purchase_invoice` or `bill_of_materials_revision`. The executing consumer of a contact proposal adds the created contact and partner.
    - **The subject's extractions,** for `EraseDataSubject` (ADR-0052 rule 25): those whose `partner_id` is the subject (an individual, sole proprietorship or employee partner), those linked to the subject's contact or partner, and those of the subject's inbound messages.
    - **Erasure** blanks `value_raw` and `value_normalized` of their fields to empty text, replaces their `evidence` with `{"erased": true}` and blanks the text of their words, keeping rows, statuses and counts (ADR-0019 rule 10).
    - **Accounting retention.** An extraction linked to an incoming e-invoice record or to a posted accounting document is kept with its attachment for the accounting retention (ADR-0038 rule 15). Erasure then blanks only the fields that are not among its purpose's accounting fields (for a supplier invoice: contact persons, phones and e-mails printed on it); the accounting fields stay as voucher evidence.
20. The data-processing policy (core, regime-neutral):
    - **Regime setting** `data_processing.policy` (ADR-0016 rule 9), registered by the core without a default: per data class (`internal`, `personal`, `sensitive_personal`), whether processing by a model provider is allowed, and whether processing in another country than the company's needs a recorded assessment. A regime that declares no value makes every check fail closed with `regime_configuration_missing` (ADR-0016 rule 10). Every package states its policy, the test package `l10n_xx` included (ADR-0053 rule 9); a regime may open it as an option for companies (ADR-0016 rule 11).
    - **The provider registry.** Each provider endpoint of the installation declares in its adapter configuration (DS-37) the processing region and its country. A permission names a provider and region of that registry; the handler copies the region's country and computes `is_cross_border` against the company's country. The proposer types neither.
    - **Company permissions.** `data_processing_permission` (owner `agent_runs`, company data, change-tracked) lists what the company permits: data class, seat class, provider, processing region and country, whether it is cross-border, the assessment attachment and date where one is needed, who approved it, and dates.
    - **Commands.** `SetDataProcessingPermission` (module `agents`, effect class `master_data_change`, change-tracked, `is_proposal_bound`, on no agent tool list, verb Set with the declared minimum level `full` on the leaf `agent`) is accepted only from the execution of an approved change proposal whose approver differs from its submitter (`approver_is_submitter`), like a promotion (ADR-0050 rule 14). Its check refuses a permission that the regime policy forbids, or a cross-border one without an assessment where the policy requires one (`data_processing_not_permitted`). `EndDataProcessingPermission` (same module, `human_only`, verb End with the declared minimum level `full` on `agent`, on no tool list) narrows or ends one directly.
    - **Enforcement.** The gateway evaluates the policy and the company's permissions before every request that carries a whole-attachment item (rule 21) or goes to a seat of class `extraction_vision_personal`, in every run mode (live, shadow, replay against the provider, evaluation and golden-set replays), and refuses it with `data_processing_not_permitted` when no active permission covers the item's data class, the seat class, the provider and its registered region; the run ends `routing_blocked`. Whether the same gate should apply to field-level personal values, which ADR-0050 rule 9 routes by the switch alone, is an open question; until answered it applies only as stated here.

    Note ([ADR-0063](0063-configurable-policy-settings.md), proposed 2026-11-15): the gate applies to every request carrying a personal value, not only whole attachments and the vision seat (rule 15). Permissions may name purposes, record the provider's terms and retention, and are suspended when the registry changes the endpoint's region or terms; the commands move to the leaf `data_processing` (rule 14). The policy's schema is widened per data class (rule 18).
21. The seat class `extraction_vision_personal`:
    - **Defined here, in the design layer:** required capabilities structured output and image and PDF input; reasoning `low`; temperature 0 where supported; data class `personal` (ADR-0050 rule 9); no tools.
    - **Disabled until permitted.** The seat is usable for a company only when an active `data_processing_permission` covers data class `personal`, this seat class and the installation's provider and region. The reason it is unusable otherwise is "no permitted provider configured", whatever the regime. With the routing switch on, Phase 1 still sends no personal value to any model (spec 17), so a run ends `routing_blocked`; the local adapter stays designed but not enabled (ADR-0050 rule 5).
    - **Whole-attachment items.** A page image is a new context item kind, `attachment_page`, carrying the attachment's label as a whole. The gateway sends or refuses it as a whole and never strips part of an image. It logs the call in the processing log with the attachment as the row sent (ADR-0050 rule 10).
    - **Spec 17.** Adding the seat to spec 17's seat list is the author's (open question). Until then the seat exists in `seatmap.yaml` only and is used only as this rule allows.

    Note ([ADR-0063](0063-configurable-policy-settings.md), proposed 2026-11-15): a company may permit the installation's cloud provider for this seat through a permission; adding the seat to spec 17's list stays the author's (rule 14).

**Verification and learning**

22. The verification screen, one of the hand-built screens (ADR-0040 rule 6 note):
    - the page on one side with each field's evidence box, the fields on the other; for an e-invoice, the record's own fields first and the rendering beside them;
    - fields ordered by the purpose's risk order: amounts, tax IDs, bank details and dates first;
    - keyboard first: Enter confirms a field and moves on; typing corrects it; a click on the page selects the words for a field;
    - machine-checked fields (parsed, OCR or aligned, with every rule passing) shown apart from human-confirmed ones, and unaligned suggestions greyed;
    - duplicates found, the hidden-text flag, the injection signal and failed rules at the top;
    - the attempts of the ladder and the reader of each value on demand.
23. Verification commands (module `attachments`, effect class `other`, `human_only`, at `edit` on the purpose's leaf):
    - **`VerifyExtractionFields`** (extraction, list of current field rows) appends one `extraction_confirmation` row per field (confirmed by, at). A row that is no longer current is refused (`extraction_field_superseded`); a `vision_unaligned` row cannot be confirmed as it is. No rule run follows (rule 14).
    - **`CorrectExtractionField`** (verb Correct; extraction, field path, the row it supersedes or none, value, optional evidence) appends a `human` row with the same value type and its confirmation; a new rule run follows in the same transaction (rule 14). It emits `ExtractionFieldCorrected`.
    - **`VerifyDocumentExtraction`** moves `needs_review` (or `extracted`) to `verified` when every required field of the purpose, or every field under full review, has a current confirmed row, every rule of the latest run passes or is named in `rule_overrides` with a non-empty reason and is not `shape` (rule 14; the database holds the shape of the entries), and no decisive duplicate stands; otherwise `extraction_verification_incomplete` or `duplicate_external_document`, naming the fields. It resolves the work item and emits `DocumentExtractionVerified`. These conditions need other rows, so the command holds them, and INV-644 checks them.
    - **`CancelDocumentExtraction`** (reason) ends the record as `canceled`, resolving the item, and emits `DocumentExtractionCanceled`.
    - **States.** A command on an extraction in a final state returns `extraction_not_reviewable`. Agents never verify.
24. Corrections become rules:
    - **`extraction_mapping_rule`** (owner `master_data`, company data, change-tracked): partner, purpose, `rule_kind` (`label_anchor`: a label text that precedes a field; `column_header`: a spreadsheet header that means a field; `unit_text`: unit text that means a unit, proposed as a `uom_alias` instead where ADR-0056 applies; a partner's item code is a `partner_item` proposal, ADR-0051 rule 2), the normalized source text, the target field path or unit code, `is_active`.
    - **Proposal-bound.** `CreateExtractionMappingRule` and `UpdateExtractionMappingRule` are `master_data_change` at `edit` on the leaf `partner`; an agent or consumer proposes them through a change proposal (ADR-0029 rule 2). Rules are data, as level 2 of ADR-0059 (drafted separately) describes.
    - **From corrections.** A consumer of `ExtractionFieldCorrected` drafts a mapping-rule proposal (never submits it) when the same correction for the same partner, purpose and field appears in at least two verified extractions in 90 days and conflicts with no active rule. The proposal copies untrusted text, so its version is tainted (ADR-0029 rule 8 note); a person submits it and another approves it.
    - **Measured.** The deterministic share of fields per partner and purpose (verified without a correction, from rungs 1 to 6) is a metric of the quality monitor (ADR-0051 rule 7).

**Phase 1 cases**

25. Supplier invoices from a mailbox:
    - **Mailbox purpose and cap.** `mailbox` gains `document_intake_purpose` (`supplier_invoice`, `inquiry_lines` or empty) and `document_intake_quarantine_limit` (default 20). `UpdateMailbox` (`human_only`, ADR-0052 rule 11) refuses a purpose when the mailbox owner does not hold `edit` on the purpose's leaf (`mailbox_owner_not_permitted`), so deliveries never fail for rights.
    - **Route, XML first.** The `crm` consumer `mailbox_document_intake` of `InboundMessageRecorded` requests, as `system` on behalf of the mailbox owner and with `inbound_message_id`, an extraction for every XML part first. Other parts are requested only after every XML part of the message is recorded, by the same consumer reacting to their `DocumentExtractionRecorded`, or by its daily sweep once `crm.document_intake_xml_timeout_minutes` (default 60) have passed without a recording; and only when the message is matched to exactly one active partner (ADR-0052 rule 15), which needs its sender authentication to pass (rule 14). Authentication alone is not enough: a stranger's domain or a free mail address can pass it. From a message that is not matched, non-XML parts are stored only, and a person may request their extraction from the message.
    - **The quarantine cap.** The decision is taken after the read, when the signature state is known. The cap counts the quarantined records imported from messages not matched to a partner, per mailbox and business date, the date being the message's receipt in the company's time zone; records of matched messages and records with a passed signature never count. Past the cap, the XML's extraction is still recorded as `extracted` but its record is not imported: the extraction carries the check result `quarantine_limit_reached`, and one `e_invoice_quarantine_overflow` item per mailbox and business date tells the mailbox owner and lists those extractions; a person imports any of them from the item with `ImportEInvoiceRecord`, which then follows the person's import path below, or closes the item. Nothing is canceled for the cap.
    - **No daily part limit.** There is no other limit: non-XML parts of messages not matched to a partner are stored only and cost no reading; XML parts cost a bounded deterministic read (rule 5) and their quarantined records are capped; documents of matched partners are read, and the agent budgets of ADR-0050 rule 22 bound them where a model is involved.
    - **Partner.** `partner_id` is the active supplier whose normalized tax ID equals a `passed` seller tax ID (exactly one), else the interaction's matched partner, else empty. It selects the mapping rules of rule 5.
    - **XML to the record.** When rung 1's e-invoice reader gives a structurally valid record (schema and arithmetic), the `tax` consumer `e_invoice_intake` of `DocumentExtractionRecorded` runs `ImportEInvoiceRecord` as `system` on behalf of the human the request acted for (the mailbox owner for the mailbox route), whatever the signature, with `source_attachment_id`, `inbound_message_id`, `signature_state`, the clearance code state (`present`, `missing`, `not_required`), the arithmetic outcome and both the stated issue time and the signing time. The extraction links the record (`extraction_result_link`) and ends `extracted`; it raises no review item of its own, so each XML gives at most one human task, the record's.
    - **One record per file.** `e_invoice_record.source_attachment_id` is unique among incoming records: a second import of the same attachment, by the route, a person, or two people importing the same listed extraction, returns the first record and creates nothing.
    - **A person's upload.** For an XML a person uploaded and requested (`RequestDocumentExtraction`, purpose `supplier_invoice`), the same consumer imports it on behalf of that person, with `imported_by_user_id` set to them, so ADR-0051 rule 20's importer confirmation applies; quarantine, supersession and key conflicts work as for the mailbox, and the quarantine cap does not apply.
    - **Duplicates are an outcome.** `duplicate_external_document` from the import ends the route normally: the extraction gets the check result `duplicate_key_found` and a link to the existing record, and the delivery completes.
    - **Quarantine.** A record whose `signature_state` is not `passed` is imported quarantined (`is_quarantined`): it holds no supplier-invoice key and the purchase invoice agent starts only after a person confirms its supplier with `ConfirmEInvoiceSupplier`, which lifts the quarantine; the key check runs then and refuses a second holder (`duplicate_external_document`). The structured fields of a `failed` or `signer_mismatch` record count as untrusted; those of an `absent` one do not, unless the package's format declares the signature mandatory (rule 6). Quarantined records of one sender in one mailbox on one business date share one `e_invoice_quarantine_review` item, the one human task for them; records that share a key are shown together in it.
    - **Supersession and conflict.** A later record with the same key and a `passed` signature supersedes a quarantined one: the quarantined record gets `superseded_by_record_id`, and `e_invoice_record_superseded` tells an accountant. `ConfirmEInvoiceSupplier` refuses a superseded record (`e_invoice_superseded`). When the key is held by a confirmed, formerly quarantined record, the record with a passed signature is still imported, with `key_conflict_with_record_id` naming the holder and the check result `e_invoice_key_conflict`; it raises `e_invoice_key_conflict` for an accountant, and no agent starts on either until a person resolves the conflict. A genuine signed invoice is never refused silently.
    - **The companion PDF.** A PDF of the same message is the XML's rendering only when the XML's invoice number appears as a whole token in the PDF's text layer; the file name stem only decides between several XML parts that match. It is then linked to the record as its rendering, as received and unverified, and its request ends `canceled` by the system with reason `rendering_of_parsed_xml`. Any other PDF is extracted as a document of its own.
    - **The add-on.** The e-invoice provider connection (pulling records from a provider or the tax authority, the authority status and revocation check) stays the DS-24 add-on; it uses the same import path.
26. PDF-only supplier invoices:
    - **Ladder.** An embedded XML is parsed first (rung 2). Otherwise the text layer, confirmed by OCR, and OCR words with the package's label anchors and the supplier's mapping rules (rungs 5 and 6); vision only where the seat is enabled.
    - **Full human verification.** Every required field is confirmed by a person; there is no automatic posting and no automatic match, and the extraction never reaches `extracted` from rungs 5 to 7.
    - **Then the agent.** A `purchasing` consumer of `DocumentExtractionVerified` raises `supplier_invoice_extracted` (subject the extraction) for a verified supplier-invoice extraction without an e-invoice record. A new version of the purchase invoice agent (1.1.0) declares that kind and accepts `document_extraction` as a subject (ADR-0051 rule 20 note):
      - **Scope:** the supplier whose normalized tax ID equals the verified `seller_tax_id`, when exactly one active supplier has it; otherwise `agent_scope_unresolved`.
      - **Inputs**, from the current confirmed fields: `seller_tax_id`, `invoice_number` and the package's key fields as the partner reference, `issue_date` as the supplier invoice date, `currency`, `net_total`, `tax_amount`, `gross_total`, and per `lines[n]`: `seller_item_code`, `item_name` (free text, untrusted), `unit_text`, `quantity`, `unit_price`, `line_amount`, `tax_rate`.
      - **Steps:** D1 is the duplicate key check (rule 15), then D2 to D5 of ADR-0051 rule 21. The run starts tainted, as every run on an outside subject.
27. Business cards:
    - **QR first.** Rung 3 decodes a QR code with a vCard or MeCard into contact fields (name, organization, job title, e-mails, phones, address, URL). The values are personal; names, e-mails, phones and URLs are untrusted.
    - **No QR.** Rung 6 gives OCR words; the vision step runs only where the seat is enabled; otherwise a person keys the fields beside the image.
    - **Proposal.** After verification, `ProposeContactFromExtraction` (module `crm`, effect class `other`, `is_draft_only`, verb Propose at `edit` on `partner`) drafts a change proposal with `CreateContact`, and `CreatePartner` when the person chose a new partner, from the confirmed fields, and links it. The server's duplicate checks on e-mail and phone (ADR-0052 rule 17) are in its plan. The proposal copies untrusted names, so it is tainted; a person submits it and another approves it (ADR-0043 rule 9, floor 7).
28. Inquiry attachments:
    - **Spreadsheets.** Rung 4 reads cell values into rows `lines[n].*` with cell evidence: header mapping by exact header, then the partner's `column_header` rules; merged headers are unmerged by position; a cell with a formula is read as its cached value with the check result `formula_cell_found`; a cell beginning with `=`, `+`, `-` or `@` is kept as text and never evaluated.
    - **Lines.** `GetQuotationLinesFromExtraction` (module `sales`, computed query, at `read` on `quotation`) turns the rows of an extracted or verified extraction into proposed quotation lines: item by the partner's item code, the company's item code or a barcode, each as a whole value; unit by the partner item's unit text, the unit aliases or a unit code; quantity as stated. Unresolved rows are returned as such. A person creates or updates the quotation from the result; no row becomes a line without a person.
    - **Drawings and PDF requests** are stored, shown beside the quotation and not read in Phase 1 unless the vision seat is enabled for the company.
29. Later than Phase 1: delivery-note photo extraction to a draft goods receipt; drawing and PDF request reading (title blocks, parts lists); per-supplier straight-through processing after a golden set shows it; voice notes by a local speech recognizer, with the transcript's audio spans as evidence (`audio_span`), personal and untrusted, drafts only.

**Legal references in packages**

30. The core names no national law. Package content:
    - **In `l10n_vn`** (DS-19), as examples: the e-invoice reader's legal basis is Decree 254/2026/NĐ-CP and Circular 91/2026/TT-BTC, effective 1 July 2026, with the XML structure of Decision 1450/QĐ-TCT as amended by Decision 1510/QĐ-TCT selected by schema version; whether the circular's format annex replaced that structure, and how the signing certificate's subject maps to the seller's tax ID, are unverified (open question, DS-40). The package setting `intake.e_invoice_formats` records the formats its reader selects, `unverified`.
    - **In `l10n_vn`**: `data_processing.policy` requires a recorded assessment for cross-border processing of personal data, following the Personal Data Protection Law 91/2025/QH15 and Decree 356/2025/NĐ-CP, `unverified` (open question). Under ADR-0016 rule 12 an unverified setting fails closed in production.
    - **In `l10n_vn`**: OCR language `vi`, tax ID rules, label anchors and unit names, as package data.
    - **Stale references.** The design cited Decree 70/2025/NĐ-CP for step 7 (ADR-0003 R10's schedule); it gets a note naming the replacement texts. Spec 08 still cites Decree 70/2025 (author-owned; the open question on replaced texts covers it).

**Catalogs and obligations**

31. Commands, queries and events, with leaf and level (ADR-0054 rules 7–9):

    | Name | Module | Effect class and flags | Leaf, level |
    | --- | --- | --- | --- |
    | `RequestDocumentExtraction` | `attachments` | `other` | the purpose's leaf, `edit` |
    | `RecordDocumentExtraction` | `attachments` | `other`; the runner only; on no tool list | the purpose's leaf, `post` (system) |
    | `CreateExtractionFields` | `attachments` | `other`, `is_draft_only`; `document_reader` workflow code only | the purpose's leaf, `edit` |
    | `VerifyExtractionFields`, `CorrectExtractionField`, `VerifyDocumentExtraction`, `CancelDocumentExtraction` | `attachments` | `other`, `human_only` | the purpose's leaf, `edit` |
    | `GetDocumentExtraction`, `ListDocumentExtraction` | `attachments` | queries; fields and words with their labels and computed trust | the purpose's leaf, `read` |
    | `CreateExtractionMappingRule`, `UpdateExtractionMappingRule` | `master_data` | `master_data_change`, change-tracked | `partner`, `edit` |
    | `ProposeContactFromExtraction` | `crm` | `other`, `is_draft_only` | `partner`, `edit` |
    | `GetQuotationLinesFromExtraction` | `sales` | computed query | `quotation`, `read` |
    | `SetDataProcessingPermission` | `agents` | `master_data_change`, change-tracked, `is_proposal_bound`; on no tool list | `agent`, `full` (declared minimum) |
    | `EndDataProcessingPermission` | `agents` | `master_data_change`, `human_only`; on no tool list | `agent`, `full` (declared minimum) |

    - **New verbs** (glossary and verb catalog): Correct (`edit`), Propose (`edit`), End (`edit`; a command may declare a higher minimum).
    - **Leaf** `agent_document_reader` under `agent` (capability `start_agent:document_reader` at `edit`); the templates `accountant` and `sales_clerk` hold it at `edit`.
    - **Events** (IDs and codes only, ADR-0013 rule 4): `DocumentExtractionRequested`, `DocumentExtractionRecorded`, `ExtractionFieldCorrected`, `DocumentExtractionVerified`, `DocumentExtractionCanceled`.
32. DS-04 rows:
    - **Errors:** `extraction_purpose_exists` (conflict), `extraction_not_reviewable` (precondition), `extraction_field_superseded` (conflict), `extraction_verification_incomplete` (precondition), `e_invoice_schema_unknown` (validation), `data_processing_not_permitted` (permission), `mailbox_owner_not_permitted` (permission), `e_invoice_superseded` (precondition).
    - **Check results:** `extraction_rule_failed`, `hidden_text_suspected`, `injection_signal`, `document_bank_account_differs`, `duplicate_key_found`, `duplicate_document_suspected`, `vision_value_unaligned`, `formula_cell_found`, `e_invoice_quarantined`, `e_invoice_key_conflict`, `quarantine_limit_reached`, `extraction_rule_overridden`.
    - **Denial records** (ADR-0038 rule 5) also cover `data_processing_not_permitted`.
33. Work item kinds:
    - `document_extraction_review` (module `attachments`, subject `document_extraction`, owner `extraction_owner`: the requester for a person's request; for a mailbox request the purpose's role, `role:accountant` for supplier invoices and `role:sales_clerk` for inquiry lines; due `days:2`; resolved by `VerifyDocumentExtraction` or `CancelDocumentExtraction`; never raised for an XML whose record was imported), declared by `document_reader`;
    - `supplier_invoice_extracted` (module `purchasing`, subject `document_extraction`, owner `role:accountant`, due `days:2`), declared by the purchase invoice agent 1.1.0 (rule 26);
    - `e_invoice_record_superseded` (module `tax`, subject `e_invoice_record`, owner `role:accountant`, due `days:2`; rule 25);
    - `e_invoice_quarantine_overflow` (module `tax`, subject `mailbox`, open key the business date, owner `subject_owner:owner_user_id`, due `days:1`, resolved when each listed extraction is imported or the owner closes it; rule 25);
    - `e_invoice_quarantine_review` (module `tax`, subject `mailbox`, open key the sender and business date, owner `role:accountant`, due `days:2`, resolved when every record it lists is confirmed or superseded; rule 25);
    - `e_invoice_key_conflict` (module `tax`, subject `e_invoice_record`, owner `role:accountant`, due `days:1`; rule 25).
34. The agent type `document_reader` in ADR-0051's tables (rules 7 and 9 notes):
    - **Thresholds:** golden set 95% of aligned fields equal to the known value; shadow agreement 95% over at least 50 documents per purpose; and, before `assisted`, a company golden set of at least 50 real documents per purpose labelled by people who hold the purpose's `approve` level, with calibrated thresholds per field (rule 13).
    - **Budgets:** 12 LLM calls, 10 tool calls, 150,000 input tokens, 8,000 output tokens, USD 0.80, 300 seconds, 500 rows per run; USD 10 and 300 runs per company and day.
    - **Shadow comparator:** per field, the aligned value against the person's confirmed value; equal when every aligned field equals and no unaligned value was confirmed unchanged.
35. Invariants (DS-16; block INV-640 to INV-669; INV-640 to INV-646 here, areas `platform`, `safety` and `tax`; first step 5):
    - **INV-640:** no `extraction_field`, `extraction_rule_run` or `extraction_confirmation` row changed after insert except by erasure; every rule run was written in the transaction of a recording, vision write or correction; every superseding field row has the same extraction, field path and value type as the row it supersedes, is a `human` row or a machine row replacing a row not found or illegible, and supersedes a row that no other row supersedes; each path has one root row.
    - **INV-641:** every `vision_aligned` and `vision_unaligned` row names a run of `document_reader`, every `vision_aligned` row's words are consecutive on one line, and no `vision_unaligned` row has a confirmation.
    - **INV-642:** for every extraction field in an agent run step's `context_refs`, the stored served trust equals the trust recomputed from the rows up to the stored rule run number (the extraction's flags being set before any field is served), and a step that received a field served untrusted, or its raw text or evidence, belongs to a run tainted at or before that step.
    - **INV-643:** every extraction's and field's data label is at least its attachment's.
    - **INV-644:** every extraction in state `verified` has a current confirmed row for every required field of its purpose, and for every field when `is_full_review_required`; every result of its latest rule run before the verification passed, or is named in `rule_overrides` with a reason and is not `shape`.
    - **INV-645:** every LLM request of any run mode that carried an attachment page was covered, at its `recorded_at`, by an active `data_processing_permission` for its company, data class, seat class, provider and registered region, with the company's routing switch off.
    - **INV-646:** two incoming e-invoice records that are not quarantined share a supplier-invoice key only when the later has a passed signature and names the earlier in `key_conflict_with_record_id`; a record with `superseded_by_record_id` is quarantined and names a record with a passed signature and the same key.
36. Edge cases (DS-17), EC-132 to EC-139 and EC-145 to EC-148 of the block EC-132 to EC-149 that this ADR and ADR-0062 share:
    - **EC-132:** a supplier e-mails an XML e-invoice with its PDF; the record is imported by the system, the PDF whose text layer holds the invoice number is linked as its rendering and its extraction ends `canceled` by the system;
    - **EC-133:** the same invoice arrives again as other bytes with the same supplier-invoice key and a passed signature; `duplicate_external_document` names the first record;
    - **EC-134:** an unsigned XML e-invoice is imported quarantined, holding no key; the genuine signed invoice with the same key arrives later, is imported, supersedes the quarantined record and raises `e_invoice_record_superseded`;
    - **EC-135:** a PDF invoice carries white text telling an agent to change the bank account; `hidden_text_suspected` forces full review and nothing changes;
    - **EC-136:** a PDF invoice names a bank account the supplier master does not have; `document_bank_account_differs`, and no master data or payment changes;
    - **EC-137:** a business card with a vCard QR code becomes a contact change proposal with duplicate checks;
    - **EC-138:** a business card photo without a QR code in a company with no permitted provider; no model is called and a person keys the fields;
    - **EC-139:** a vision value for a total cites words on two lines; it is stored unaligned, fills nothing, and the computed total decides the rule;
    - **EC-145:** an XML e-invoice signed with a valid certificate of another company names a known supplier's tax ID; `signer_mismatch`, quarantined, and no agent run until a person confirms the supplier;
    - **EC-146:** a message carries an XML invoice and a PDF of a second invoice; the PDF matches neither by file name nor by number and is extracted as its own document;
    - **EC-147:** a sender whose free mail address passes DKIM but matches no partner mails ten PDFs and an unsigned XML to the supplier-invoice mailbox; the PDFs are stored only, no OCR or vision runs until a person requests one, and the XML's quarantined record counts toward the cap;
    - **EC-148:** a person confirms the supplier of an unsigned record; the genuine signed invoice with the same key arrives later, is imported with `key_conflict_with_record_id`, raises `e_invoice_key_conflict`, and no agent starts until an accountant resolves it.
37. Settings: regime `data_processing.policy` (registered without a default, rule 20); package `intake.e_invoice_formats` (registered key, value per package); company `intake.vision_max_pages` (default 10, lowering only); mailbox `document_intake_quarantine_limit` (default 20); company `crm.document_intake_xml_timeout_minutes` (default 60).
38. Lab check `t20_intake.py` ([validation lab](../reviews/2026-11-14-design-validation/README.md)): pure functions for the ladder order and stop at the first valid record, alignment (a value at adjacent consecutive words of one line and cell passes, scattered words, words across table cells and fabricated values fail, numbers exactly), closed shapes and value trust computed from rule runs and confirmations, rules over confidence, the three duplicate levels with quarantine, the signature conditions, the hidden-text flag by position, vCard parsing, spreadsheet reading, the companion PDF test, mailbox gating and the policy without a default; with `--load`, on the schema of `load_all.py`: append-only fields, one root per path, corrections keeping the type, the trust view, rule runs and confirmations, the state transitions and set-once flags, result links, mapping rules and permissions.

### Worked examples

**Example 1: an XML e-invoice from the mailbox.** Mailbox `ap@` has `document_intake_purpose` `supplier_invoice`. An e-mail with `INV-0042.xml` and `INV-0042.pdf` arrives. Intake records the message and two attachments (ADR-0052 rule 12). `mailbox_document_intake` requests the XML's extraction first. Rung 1 identifies the root and version, the package reader parses it; the signature is valid, chains to a listed authority, was made while the certificate was valid, and the certificate's subject maps to the seller tax ID in the file: `passed`. The arithmetic holds and the rule run passes: state `extracted`; amounts, dates, tax IDs and the currency are `parsed` with XPath evidence and fit their shapes, so `extraction_field_trust` reports their normalized values trusted; item names stay untrusted, and seller item codes and unit text are trusted only where they resolve to the supplier's partner items and units. `e_invoice_intake` runs `ImportEInvoiceRecord`; the key is new; the record raises `supplier_invoice_received` and the purchase invoice agent starts in its supplier's scope. The consumer then turns to the PDF: its text layer holds the invoice number `0000042` as a whole token, so it is linked as the rendering and its request ends `canceled` by the system with `rendering_of_parsed_xml`.

**Example 2: a PDF-only invoice.** A foreign supplier, whose message is authenticated and matched to it, sends a scanned PDF. Rung 2 finds no embedded XML; rung 5 finds no text layer; rung 6's OCR gives 412 words on 38 lines. The package's label anchors and the supplier's mapping rule ("Invoice No." means `invoice_number`) find the number, date, seller tax ID and total; lines are not found. The record is not valid, so the extraction goes to `needs_review` and `document_extraction_review` goes to `role:accountant`. No permission exists for the vision seat, so no run starts. The accountant opens the screen: the total "12,450.00" is confirmed with Enter, which appends a confirmation row and starts no rule run; three lines are keyed against the page as `human` rows, each with the rule run of its correction in the same transaction; the last run recomputes net and tax and they equal the printed total; the total, confirmed and passing its shape in that run, is trusted. `VerifyDocumentExtraction` succeeds, `supplier_invoice_extracted` is raised, and the purchase invoice agent drafts the invoice from the confirmed fields; nothing posts without the accountant.

**Example 3: a business card through QR.** A salesperson uploads a card photo with purpose `contact_card` and the customer as partner. Rung 3 decodes a QR code with `BEGIN:VCARD … FN:… TEL;TYPE=work:… EMAIL:… END:VCARD`. The fields are parsed with `qr_payload` evidence; name, title, phone and e-mail are untrusted by type, which matters only for agent runs. The salesperson confirms the fields and runs `ProposeContactFromExtraction`; the proposal's plan shows no duplicate e-mail; a sales manager approves it, and the created contact is linked to the extraction.

**Example 4: an inquiry spreadsheet becomes quotation lines.** An authenticated, matched customer's e-mail carries `RFQ.xlsx` with headers "Part No", "Qty", "Unit". The mailbox `sales@` has purpose `inquiry_lines`. Rung 4 maps "Qty" and "Unit" by exact header and "Part No" by the customer's `column_header` rule; it reads 12 rows with cell evidence (`Sheet1!B5`), notes one formula cell; ten rows' units resolve through the unit aliases and their codes fit the shape, two rows' unit "bộ" does not resolve and stays untrusted. The salesperson calls `GetQuotationLinesFromExtraction`: ten rows resolve by the customer's item codes and units; two stay unresolved. The salesperson creates the quotation with the ten lines and adds the other two by hand.

**Example 5: a vision-aligned field and an unaligned one.** In a company with a permitted provider, the reader returns `invoice_date` "15/11/2026" with word 31, whose OCR text is "15/11/2026": aligned, stored with the page's text, still untrusted until confirmed. It returns `gross_amount` "1.250.000" citing words 88 and 112, which lie on two lines, and `quantity` "2500" citing a "2" and a "500" in neighbouring table cells: both unaligned whatever their text, greyed, untrusted and never prefilled. The computed gross from the lines is 1.205.000, which word 88 shows; the person corrects the field into a `human` row with that value, the rule run passes, and the confirmed amount is trusted.

## Context

The capability check of 2026-11-15 (capability 3) found e-mail intake, attachment storage with taint and the structured e-invoice path designed, but no workflow that lets a model read an image or PDF, no record of extracted values with evidence, and none of the named cases covered end to end. The author asked for multimodal input to be designed.

The 2026-11-15 survey compared Azure, Google, AWS, SAP, ABBYY, Rossum and UiPath with the research on vision extraction and document injection:
- **One human-in-the-loop design.** Per-field confidence, per-field thresholds, validation rules that override confidence, a side-by-side verification screen and learning from corrections are common to every mature product. Google withdrew its managed human review in 2024, which is why the screen belongs in the ERP (rule 22).
- **Quiet errors.** Native image input reached 87–93% field exact-match on invoices and receipts, line items are the weakest part everywhere, and self-reported model confidence is poorly calibrated. Hence code alignment (rule 12) and no model confidence (rule 13).
- **Grounding needs code.** Even strong models mistranscribe some of their own copied evidence; LMDX grounds only to OCR lines. Hence word IDs on one line and exact alignment, with the page's text stored.
- **Injection through documents is measured.** Hidden PDF text survives text-layer parsers, and image injections succeed often. Spotlighting helps but is not a boundary. The structural defense is a tool-less reader with typed output and closed shapes (rules 17, 18).
- **Deterministic first.** Structured XML, hybrid PDFs, QR vCards and spreadsheets read deterministically; a model is the fallback for pixels only (rule 4).
- **The signed XML is the legal original** in the e-invoice regimes surveyed, and its signature proves the seller only when the certificate names the seller (rule 6).
- **Personal data is the attachment.** An image cannot be field-stripped, so labels and routing must apply to the whole file (rules 19–21). Cross-border processing rules differ by regime, so the core holds a neutral policy without default and packages hold the values.

ADR-0005: the agent decides technical points, with SAP as reference when unsure, and the option easiest for AI agents wins among correct ones. One record with evidence per field, one ladder, one alignment rule and trust computed from stored facts give agents and people the same inspectable facts.

## Options considered

| Option | For | Against |
| --- | --- | --- |
| One extraction record with field evidence, owned by `attachments` (chosen) | One seam for every case; evidence inspectable by people and agents | A new table family |
| A feature per case (card scanner, invoice OCR, RFQ reader) | Faster first case | Four evidence models, four trust rules |
| A new module `extraction` | Clear name | ADR-0022 adds modules sparingly; `attachments` already owns the bytes |
| Reader ladder, first valid record wins (chosen) | Deterministic where structure exists; cheap | Partial records need a union rule |
| Always run a vision model | Simplest pipeline | Cost, personal data abroad, quiet errors where XML was available |
| Vision as a tool-less agent run (chosen) | Budgets, replay, processing log and taint unchanged | One more agent type |
| Code alignment to consecutive OCR words of one line, page text stored (chosen) | Catches fabricated, composed and mistranscribed values | Needs an OCR layer with lines for every image |
| Trust the model's citations or confidence | No OCR | Measured to fail quietly |
| Trust computed at read time from rule runs and confirmations (chosen) | Re-run rules and confirmations change trust without rewriting rows; append-only kept | A view over three tables |
| Trust stored on the field row | Simple reads | Frozen on append-only rows while rules re-run |
| Value trust for closed shapes (chosen, author's reading) | Verified numbers and codes do not taint downstream runs | A reading of a hard floor |
| Everything from outside taints | Literal | Downstream product and invoice drafting from verified data becomes useless |
| Signature `passed` only when the certificate names the seller (chosen) | A valid certificate of someone else proves nothing | Needs a package mapping from subject to tax ID |
| Quarantined records hold no key (chosen) | A forged first copy cannot block the genuine invoice | One more state and a superseding step |
| Neutral data-processing policy without default, package values (chosen) | Global core; fails closed | Every package must declare it |
| Hard-code a country's cross-border rule | Fast for one market | Shapes the core around one regime (ADR-0053) |
| Verification screen in the ERP (chosen) | Survives vendor changes; one audit trail | A hand-built screen |

## Constraints that come with the decision

- **DDL:** [DS-36-document-intake.sql](../design/DS-36-document-intake.sql) (new): `document_reader`, `document_extraction`, `extraction_word`, `extraction_field`, `extraction_rule_run`, `extraction_confirmation`, `extraction_result_link`, the view `extraction_field_trust` `[attachments]`; `extraction_mapping_rule` `[master_data]`; `data_processing_permission` `[agent_runs]`; `mailbox.document_intake_purpose` and `document_intake_quarantine_limit` (DS-35). `e_invoice_record` (DDL with DS-24 or the tax draft) gains `source_attachment_id` (unique among incoming records), `inbound_message_id`, `is_quarantined`, `superseded_by_record_id`, `key_conflict_with_record_id`, the clearance code state and the signing time. The test package's settings gain `data_processing.policy` ([DS-16-l10n_xx/settings.yaml](../design/DS-16-l10n_xx/settings.yaml)).
- **ADR notes:** ADR-0003 R10 (stale decree); ADR-0016 rules 10, 17; ADR-0019 rule 10; ADR-0022 rule 2; ADR-0029 rule 10; ADR-0038 rule 13; ADR-0040 rule 6; ADR-0050 rules 1, 5, 8, 9, 15, 19, 30; ADR-0051 rules 7, 9, 15, 20; ADR-0052 rules 11, 25; ADR-0053 rule 1.
- **DS-04:** the errors and check results of rule 32.
- **Catalogs:** six work item kinds; INV-640 to INV-646; EC-132 to EC-139, EC-145 to EC-148; verbs Correct, Propose, End; leaf `agent_document_reader` and its template levels.
- **Package:** `l10n_vn` settings `data_processing.policy` and `intake.e_invoice_formats`, unverified; the test package declares `data_processing.policy` too.
- **Other design items:** DS-17 (input files: XML and PDF invoices, one unsigned and one signed by another company, a PDF with hidden text, card photos with and without QR codes, RFQ spreadsheets; event type `contact_card_scanned`); DS-24 (provider connection, revocation and authority status on the same import path); DS-30 (the verification screen); DS-37 (the OCR engine, renderer and the provider registry with regions).
- **Open questions:** value trust and its narrowing; the tainted reads of the reader run; the seat in spec 17 and its provider; the policy for field-level personal values; the `l10n_vn` format annex, certificate mapping and data-processing values.

## Revisit when

- The author answers the value-trust reading or the seat question.
- A company's golden set supports straight-through processing for a supplier.
- Drawings, delivery notes or voice become Phase 1 needs.
- A provider offers in-region processing that a regime's policy permits without assessment.

## Documents updated

- **This ADR** (new) and the index row in [docs/adr/README.md](README.md).
- **The DDL:** [docs/design/DS-36-document-intake.sql](../design/DS-36-document-intake.sql) (new), [docs/design/DS-35-crm.sql](../design/DS-35-crm.sql).
- **ADRs:** notes in ADR-0003, ADR-0016, ADR-0019, ADR-0022, ADR-0029, ADR-0038, ADR-0040, ADR-0050, ADR-0051, ADR-0052 and ADR-0053.
- **Design files:** [docs/design/DS-04-command-envelope.md](../design/DS-04-command-envelope.md), [docs/design/DS-16-invariants-and-harness.md](../design/DS-16-invariants-and-harness.md), [docs/design/DS-17-synthetic-dataset.md](../design/DS-17-synthetic-dataset.md), [docs/design/backlog.md](../design/backlog.md).
- **Catalogs:** [work-item-kinds.csv](../catalogs/work-item-kinds.csv), [invariants.csv](../catalogs/invariants.csv), [edge-cases.csv](../catalogs/edge-cases.csv), [authorization-areas.csv](../catalogs/authorization-areas.csv), [authorization-verb-levels.csv](../catalogs/authorization-verb-levels.csv), [role-template-levels.csv](../catalogs/role-template-levels.csv).
- **Package:** [docs/design/DS-19-vietnam-tt99/settings.yaml](../design/DS-19-vietnam-tt99/settings.yaml).
- **Glossary:** [docs/spec/00-reading-guide.md](../spec/00-reading-guide.md) (rows only).
- **Open questions:** [docs/open-questions.md](../open-questions.md).
- **The lab:** [docs/reviews/2026-11-14-design-validation/](../reviews/2026-11-14-design-validation/README.md): `lab/t20_intake.py` (new).
- **Log:** [docs/runbook/step-log.md](../runbook/step-log.md) at acceptance.

## Decisions for the author

- **Value trust** (rule 17) as a reading of spec 03 rule 1: may a field's normalized value that fits its type's closed shape and passed every rule of the extraction's latest run, from a deterministic reader, or that a person confirmed, be read without tainting the run? Interim: yes, narrowed as stated: the normalized value only, never the raw text or evidence; free text, URLs, e-mails, phones and unresolved codes and units never; at least one passed rule; vision values only after a person's confirmation; nothing from an extraction with a failed or mismatched signature or with hidden text.
- **The reader run's reads and writes** (rule 11): may a tainted run on an extraction read its words, fields, rule runs and pages, and append draft field rows to it? Interim: yes.
- **The personal vision seat and its provider** (rules 20, 21): may a company permit the installation's cloud provider for personal page images under its regime's policy, or must the seat wait for a local provider? Interim: designed, disabled until a company configures a permitted provider; with the routing switch on, nothing is sent in Phase 1. Adding the seat to spec 17 is the author's.
- **The data-processing gate for field-level personal values** (rule 20): apply the same policy to every personal value sent? Interim: only whole attachments and the vision seat.
- **The e-invoice format annex and the certificate mapping** (rules 6, 30), in `l10n_vn`: does the circular's annex replace the XML structure the package reader parses, and how does a signing certificate's subject map to the seller's tax ID? Interim: selection by schema version, unknown versions to review, unverified.
- **The tainted catalog read** for product engineering: [ADR-0062](0062-product-engineering-workflow.md).
