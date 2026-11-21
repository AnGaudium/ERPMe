Module: attachments    Chunk: 2 of 3    Source ADRs: ADR-0057
Build step(s): 5    Generated from index: 30d5706    Compiled by: Claude Fable 5.2, 2026-11-21

# `attachments` compiled spec, chunk 2: extraction record, fields, vision alignment, rule runs, trust, verification

## Purpose

This chunk states the part of `attachments` law on the extraction record and its rows: `document_extraction`, its fields, words, evidence, rule runs, confirmations and result links; the agent type `document_reader` and the alignment of its values; duplicates; value trust; injection defenses; personal data; and the verification screen and commands. The module never changes partner master data and never fills a payment from a document (R222). The attachment store, the readers, the ladder and the recording are in chunk 1; the mailbox, the purposes' consumers and the settings rules are in chunk 3.

## Entities and tables

DDL: `docs/design/DS-36-document-intake.sql`. The view `extraction_field_trust` (R224) is in the same file.

| Table | Meaning | Key | Parent | Owner |
| --- | --- | --- | --- | --- |
| `document_extraction` | What was read from one clean attachment for one purpose, with its flags and verification; `state` is one of `pending`, `extracted`, `needs_review`, `verified`, `canceled` (R201-R204; ADR-0057.R3, ADR-0057.R4) | `id`; (`company_id`, `attachment_id`, `purpose`) unique; (`company_id`, `id`) | `attachment` | `attachments` |
| `extraction_field` | One value of a field path, append-only; a correction is a new row (R205-R208) | `id`; (`company_id`, `id`) | `document_extraction` | `attachments` |
| `extraction_word` | One word of a page and layer with its normalized box (R209) | `id`; (`document_extraction_id`, `layer`, `page_number`, `word_number`) unique | `document_extraction` | `attachments` |
| `extraction_rule_run` | One result per run, field and rule (R218) | `id`; (`document_extraction_id`, `run_number`, `extraction_field_id`, `rule`) unique | `extraction_field` | `attachments` |
| `extraction_confirmation` | A person's confirmation of one field row (R232) | `id`; `extraction_field_id` unique | `extraction_field` | `attachments` |
| `extraction_result_link` | A subject an extraction led to (R229) | `id`; (`document_extraction_id`, `target_table`, `target_id`) unique | `document_extraction` | `attachments` |

Reads: `attachment`, `document_reader` (`attachments`, chunk 1); `partner`, `contact`, `uom_alias`, `currency` (`master_data`); `inbound_message`; `agent_run`, `agent_run_step`; `user_account`; `e_invoice_record`; `change_proposal`; `quotation`; `purchase_invoice`; `bill_of_materials_revision`; `inspection_result`.

## Commands and queries

The verification commands are in module `attachments`, effect class `other`, `human_only`, at `edit` on the purpose's leaf (R232). The verb `Verify` has level `edit` in `authorization-verb-levels.csv`.

| Name | Actor and authorization | Input | Effect | Events | Error codes |
| --- | --- | --- | --- | --- | --- |
| `CreateExtractionFields` | workflow code of the agent type `document_reader` only; effect class `other`, `is_draft_only`; the purpose's leaf at `edit` (ADR-0057.R31) | not stated (the aligned and unaligned values of a run) | Appends `vision_aligned` and `vision_unaligned` rows with the run as `agent_run_id`, and the rule run that follows, in one transaction (R213) | not stated | not stated |
| `VerifyExtractionFields` | `human_only`; `edit` on the purpose's leaf | extraction, list of current field rows | Appends one `extraction_confirmation` row per field (R232) | not stated | `extraction_field_superseded`, `extraction_not_reviewable` |
| `CorrectExtractionField` | `human_only`; `edit` on the purpose's leaf; verb Correct | extraction, field path, the row it supersedes or none, value, optional evidence | Appends a `human` row and its confirmation; a rule run follows (R232) | `ExtractionFieldCorrected` | `extraction_not_reviewable` |
| `VerifyDocumentExtraction` | `human_only`; `edit` on the purpose's leaf | not stated (the extraction; `rule_overrides` entries with reasons) | Moves the extraction to `verified` and resolves the work item (R233) | `DocumentExtractionVerified` | `extraction_verification_incomplete`, `duplicate_external_document`, `extraction_not_reviewable` |
| `CancelDocumentExtraction` | `human_only`; `edit` on the purpose's leaf | reason | Ends the record as `canceled` and resolves the work item (R233) | `DocumentExtractionCanceled` | `extraction_not_reviewable` |

Not registered commands: the rule run (R218); the alignment by workflow code (R214-R216); the view `extraction_field_trust` (R224); the output schema `DocumentReaderPageOutput` 1.0.0 (R213).

Error codes of R221 raised by commands of chunk 1 or other modules: `extraction_purpose_exists`, `duplicate_external_document`. Check results bound to no command of this chunk: `extraction_rule_failed`, `extraction_rule_overridden` (R220); `duplicate_key_found`, `duplicate_document_suspected` (R221); `document_bank_account_differs` (R222); `hidden_text_suspected` (R227); `injection_signal` (R226). Rule result: `near_match` (R215).

## Rules

### Extraction record

R201. `document_extraction` holds company data. Identity columns: `id`, `company_id`, `attachment_id`, `purpose`, `attachment_sha256`, `detected_media_type`, `document_kind`, `page_count`. It is unique per (company, attachment, purpose).
Source: ADR-0057.R7

R202. Labels and flags of `document_extraction`: `data_label`, copied from the attachment and never lower (R228); `hidden_text_suspected` (R227); `injection_signal` (R226); `is_full_review_required`, true when hidden text is suspected. These flags and `signature_state` are set only by the recording command while the record is `pending` (ADR-0057.R4), and never cleared.
Source: ADR-0057.R7

R203. Result, origin and verification columns of `document_extraction`:
- result: `state`, `reader_attempts`, `final_reader_id` (never a vision reader for state `extracted`), `signature_state`, `partner_id` (ADR-0057.R25), and the subjects it led to in `extraction_result_link` (R229);
- origin and verification: `inbound_message_id` (the message it came with, if any), `requested_by_user_id`, `verified_by_user_id`, `verified_at`, `rule_overrides` (the failed cross-field rules a person verified past, each with a reason, R220), `canceled_reason`, `recorded_at`.
Source: ADR-0057.R7

R204. States of `document_extraction`: `pending` → `extracted`, `needs_review` or `canceled`; `extracted` → `needs_review`, `verified` or `canceled`; `needs_review` → `verified` or `canceled`; `verified` and `canceled` are final. A trigger holds the transitions.
- `pending → canceled` is the system's only, for a rendering of a parsed XML (ADR-0057.R25).
- `extracted` means a deterministic rung gave a valid record and the extraction itself needs no person; for an XML, any human task that remains (a supplier confirmation, a key conflict, an import past the quarantine cap) belongs to its e-invoice record or its mailbox, not to the extraction.
- No field, rule run or confirmation is appended to an extraction in a final state.
Source: ADR-0057.R7

### Fields, words and evidence

R205. `extraction_field` holds company data and is append-only. Value columns: `field_path` (for example `seller_tax_id`, `lines[3].unit_price`), `value_type` (the types of R223), `value_raw` (as printed or stored), `value_normalized` (canonical: ADR-0006.R13 decimals, ISO dates, normalized tax IDs, the codes of resolved records and units), `status`.
- Normalizers are strict: the whole raw value must parse, nothing is discarded, and a value that does not normalize exactly fails its shape rule.
- Trust covers `value_normalized` only; `value_raw` and `evidence` hold outside text and are always served as untrusted columns.
Source: ADR-0057.R8

R206. Provenance and confidence columns of `extraction_field`:
- provenance: `method` (`parsed`, `ocr`, `vision_aligned`, `vision_unaligned`, `computed`, `human`), `evidence_kind` and `evidence` (R210), `document_reader_id`, `agent_run_id` (vision rows), `entered_by_user_id` (human rows);
- confidence: `confidence_raw` (the engine's own score, for example an OCR word confidence; never a model's self-report, ADR-0050.R35) and `confidence_calibrated` (R217);
- rule results and trust are not columns of the row: rule results are rule runs (R218), confirmations are rows of their own (R232), and trust is computed when the field is read (R224).
Source: ADR-0057.R8

R207. A correction of an `extraction_field` row is a new row with method `human`, entered by a person, that names the row it supersedes (`supersedes_field_id`), with the same extraction, field path and value type. A machine row (a vision row) may supersede only a row with status `not_found` or `illegible`. Each path has one root row, and a row is superseded at most once, so the current value of a field is unique: the row of that path that no other row supersedes. Rows are never updated or deleted, except that erasure blanks the values and evidence (R230).
Source: ADR-0057.R8

R208. Methods of an `extraction_field` row:
- `parsed`: a structured reader (rungs 1 to 4);
- `ocr`: a deterministic anchor over text-layer or OCR words (rungs 5 and 6);
- `vision_aligned` and `vision_unaligned`: the alignment of R214-R216;
- `computed`: a value code derived from other fields (totals, taxes, line amounts), never a model value;
- `human`: a person's correction.
Source: ADR-0057.R8

R209. `extraction_word` (company data, append-only) holds one row per word of a page and layer: `layer` (`ocr`, `text_layer`), `page_number`, `word_number` (reading order on the page), `line_number` (the reading-order line on the page), `cell_ref` (the cell of a detected table the word lies in, if any), `text`, the normalized box (`x0`, `y0`, `x1`, `y1` in 0..1 from the page's top left), `confidence_raw`, and for text-layer words `is_on_render` (R227). Word rows are personal and untrusted with their extraction. Rendered page images are not stored: the renderer is deterministic per version and resolution, and normalized boxes redraw on any rendering.
Source: ADR-0057.R9

R210. Evidence, by `evidence_kind`:
- `xpath`: `{"xpath": …}` into the XML;
- `cell`: `{"sheet": …, "cell": "C12"}`;
- `char_span`: `{"page": n, "start": i, "end": j, "region": [x0, y0, x1, y1]}` in the reader's text of a page, with the union of its words' boxes;
- `page_region`: `{"page": n, "region": [x0, y0, x1, y1], "word_ids": [...]}` with consecutive OCR word numbers of one line of that page;
- `qr_payload`: `{"page": n, "region": [...], "property": "TEL;TYPE=work"}`.
Parsed, OCR and aligned rows always carry evidence; computed rows carry none and name their inputs in their rule runs.
Source: ADR-0057.R10

### The agent type `document_reader` and alignment

R211. The agent type `document_reader` (ADR-0050.R12) declares the work item kind `document_extraction_review`. The wake-up consumer (ADR-0050.R16) starts a run when the kind is raised in a company where the agent type is not `off` and the seat is usable for the company (ADR-0057.R21); otherwise the item stays with people, who key or confirm the fields on the verification screen. The precheck D0 ends the run `not_applicable` without an LLM call when the extraction's kind has no pages (XML, spreadsheet, e-mail), when no required field is missing or illegible, or when the extraction is under full review.
Source: ADR-0057.R11

R212. Scope and input of a `document_reader` run:
- scope kind `subject`: the extraction row. `document_extraction` is an outside-content subject table, so the run starts tainted (ADR-0050.R15). It reads its subject, the subject's words, fields and rule runs, and its attachment's pages: a reading of the tainted read scope put to the author (open question).
- no tools: its tool list holds no query and no command for the model. Workflow code renders the pages, calls the gateway and writes the result.
- input per page: the rendered page image, re-encoded without metadata (R228), and the OCR words of that page as `(word_number, line_number, text, box)`, datamarked (R226); the purpose's field list with types.
- at most `intake.vision_max_pages` pages (default 10) per run; a longer document stays with people.
Source: ADR-0057.R11

R213. Output and writing of a `document_reader` run:
- output schema `DocumentReaderPageOutput` 1.0.0: per field path `{value_raw, word_ids, page, status}`, with `status` one of `found`, `not_found`, `illegible`. No confidence field (ADR-0050.R35).
- after alignment (R214-R216), `CreateExtractionFields` (module `attachments`, effect class `other`, `is_draft_only`, on this agent type's list for workflow code only) appends the rows, method `vision_aligned` or `vision_unaligned`, with the run as `agent_run_id`, and the rule run that follows, in the same transaction. Appending rows to an outside subject's extraction as a draft-only write is a reading put to the author (open question).
- the run ends `drafted` and unclaims the item, which goes back to its owner for verification.
- seat: `extraction_vision_personal` (ADR-0057.R21).
Source: ADR-0057.R11

R214. Alignment is done by code, per field the model returned with status `found`. The word numbers named must exist on the page given, be consecutive in reading order on one line (one `line_number`), lie in one table cell or in none (one `cell_ref`), and be adjacent: the horizontal distance between neighbouring words' boxes, in either direction (so right-to-left lines too), is at most 0.6 times the line height, a normal space. Otherwise the value is unaligned. A value split over lines, composed of words from several places, or joined across table cells (a quantity "2" beside a price "500") is never aligned.
Source: ADR-0057.R12

R215. Comparison in alignment:
- exact, for every value type except `text`, `url` and `email`, and for any value that contains a digit: the value's characters, without spaces, must equal the named words' characters exactly. No normalization of digits, separators or signs is allowed before the comparison; code parses the aligned text afterwards with the document's number and date formats (ADR-0057.R5).
- `text`, `url` and `email` values without digits: normalize the value and the named words' text (Unicode NFKC, case folding, collapsed whitespace; diacritics kept). Equal: aligned. A near match, every word within one edit of its counterpart and the same word count: aligned with the rule result `near_match`. Otherwise unaligned.
Source: ADR-0057.R12

R216. Results of alignment:
- an aligned row stores the page's text, not the model's, and its region is the union of the named words' boxes;
- unaligned values are stored with method `vision_unaligned`, are untrusted, and are shown greyed. They never fill a draft and are never confirmed as they are: a person who accepts one keys or confirms it into a `human` row;
- line amounts, totals and taxes are recomputed by code from aligned or parsed inputs (method `computed`) and compared with the printed values; a difference is a failed rule (R220), never a correction.
Source: ADR-0057.R12

R217. Confidence and thresholds:
- raw confidence is the engine's score for OCR words and text-layer words; parsed values have none. A model's self-reported confidence is never asked for or stored.
- calibrated confidence per (company, reader code and version, field path) comes from the company's golden set (ADR-0057.R34). Until a company has one, `confidence_calibrated` stays empty and every vision field needs a person.
- thresholds are per field and are a parameter set of the reader (ADR-0059, level 1, drafted separately). Any change of reader version, model, prompt or seat model recalibrates them from a replay of the golden set, run under the data-processing gate (ADR-0057.R20), before the effective mode returns to assisted (ADR-0050.R14).
Source: ADR-0057.R13

### Rule runs

R218. Validation rules override confidence. `extraction_rule_run` (append-only) holds one row per run, field and rule: the run number (`run_number`, increasing per extraction), the field row, the rule code (`rule`), `passed` (boolean, never null), a detail and, in the DDL, `trigger_kind` (`ladder`, `vision` or `correction`: the write the run follows).
- Every run evaluates every current field. A run follows the recording, every vision write and every correction, in the same transaction as the write; a confirmation changes no value and starts no run.
- Trust uses only the results of the extraction's highest run number: a field without a result in that run is untrusted.
- The rule `shape` is mandatory for every field: it checks the value against its type's closed shape (R223). A field without a passed `shape` result is untrusted.
Source: ADR-0057.R14

R219. Rules of a run, by purpose:
- supplier invoices: quantity × unit price − discount = line amount, within half a minor unit of the document currency per line; lines sum to the net total; per tax rate, base × rate = tax amount within the package's stated-amount tolerance; net + tax − allowances + charges = gross; the buyer's tax ID equals the company's (a misdirected invoice fails); the currency is active for the company; the issue date is not after the receipt date; tax IDs, IBANs and GTINs by their check digits;
- inquiry lines: each row's quantity is a positive decimal; its unit resolves to a unit code (R223); its item reference fits the `code` shape; a row without a quantity fails;
- product sources: each quantity and dimension is a positive decimal with a resolved unit; codes fit the `code` shape;
- contact cards: e-mail and phone normalize by the package's rules (they stay untrusted, R224).
Source: ADR-0057.R14

R220. A failed rule marks the field and the extraction `needs_review`, whatever any confidence says, with the check result `extraction_rule_failed`. A purpose or field without rules has no passed rule, so its fields stay untrusted. A document may be wrong as printed (a total that is not the sum of its lines): a person may verify past a failed cross-field rule only with a reason, recorded in `rule_overrides` with the check result `extraction_rule_overridden`; a failed `shape` rule is never overridden, and an overridden rule does not make its fields trusted.
Source: ADR-0057.R14

### Duplicates and bank details

R221. Duplicates are checked against the company's full history, not only open documents, at these levels:
- level 1, file: the same SHA-256 (ADR-0038: one attachment per company and hash) under the same purpose is the existing extraction (`extraction_purpose_exists`);
- level 2, key: the package's supplier-invoice key (ADR-0030.R10), normalized, equal to that of an existing document or of an incoming e-invoice record that is not quarantined (ADR-0057.R25): the check result `duplicate_key_found` at recording, and `duplicate_external_document` when a record or draft would be created or an extraction verified;
- level 3, near: the same seller, gross amount within the tolerance, and issue date within the window, or the same seller and an equal invoice number after normalization: the check result `duplicate_document_suspected`. The window, the amount tolerance and the number normalization are the company settings `intake.duplicate.date_window_days`, `intake.duplicate.amount_tolerance_minor_units` and `intake.duplicate.number_normalization` (defaults 7 days, 1 minor unit, digits only). With `intake.duplicate.near_outcome` `review`, the default, a suspected invoice posts with its open item blocked for payment and raises `duplicate_document_review`;
- levels 1 and 2 are decisive and cannot be switched off (ADR-0063.R27); level 3 never refuses a document: the suspected invoice still posts, and under `review` only its payment is held until a person resolves the item (ADR-0063.R27); under `advisory` it is the check result alone.
Source: ADR-0057.R15, ADR-0057.R15.N1

R222. A bank account read from a document never changes partner master data and never fills a payment. When it differs from the partner's accounts, the extraction carries the check result `document_bank_account_differs`. A person who wants the change starts a bank-account change proposal, which follows the core's seeded rule (ADR-0043.R15; ADR-0029.R4).
Source: ADR-0057.R16

### Instruction taint and value trust

R223. Instruction taint is unchanged: free text from outside (names, addresses, descriptions, notes) is untrusted, and a run given it becomes tainted (ADR-0029.R10; ADR-0050.R25). The `shape` rule of each value type checks its closed shape:
- `amount`, `quantity`, `percent`: a canonical decimal of at most 18 integer and 6 fraction digits; trust possible;
- `date`: a valid ISO date; trust possible;
- `currency`: a code of the core currency catalog; trust possible;
- `tax_id`: the package's tax ID rule with its check digit; trust possible;
- `bank_account`: IBAN with mod 97, or the package's national format with its check digit; trust possible (it still never changes master data, R222);
- `code`: resolved to exactly one record (an item code, a partner item or supplier item code, a barcode, a manufacturer part number); the normalized value is that record's code; trust possible when resolved;
- `unit`: resolved to a unit code through the partner item's unit text, the unit aliases of ADR-0056 (`uom_alias`) or a unit code; the normalized value is the code; trust possible when resolved;
- `text`, `url`, `email`, `phone`: no closed shape; never trusted.
The `shape` rule of `code` and `unit` resolves the value deterministically against the company's records (the partner's codes when the extraction names its partner); an unresolved code or unit fails it and stays untrusted, as ADR-0051.R20 keeps `seller_item_code` and `unit_text` untrusted.
Source: ADR-0057.R17

R224. Trust is computed when read. The view `extraction_field_trust` gives `is_untrusted` for a field row's normalized value from the row, the extraction, the extraction's highest rule run and the confirmations, in this order:
- untrusted when the extraction has `hidden_text_suspected` or a `signature_state` of `failed` or `signer_mismatch`;
- untrusted when the type is `text`, `url`, `email` or `phone`, or the status is not `found`;
- a person-confirmed row (R232) is trusted when its `shape` result in the highest run passed;
- an unconfirmed row is trusted when its method is `parsed`, `ocr` or `computed`, it has at least one result in the highest run, every one passed, and `shape` passed;
- every other row (vision rows before confirmation) is untrusted.
This reading is the default. The company settings `intake.trust.<document_type>.<field>.require_confirmation`, `intake.trust.<document_type>.min_passed_rules` and `intake.trust.ocr_min_confidence` only tighten it, and loosening below a value in force needs `extraction_mapping` evidence (ADR-0063.R7).
Source: ADR-0057.R17, ADR-0057.R17.N1

R225. Effect and reach of value trust:
- the query layer serves `value_normalized` with this computed attribute in place of `is_untrusted` (ADR-0050.R28), and `value_raw` and `evidence` as untrusted columns always: a run that reads only trusted normalized values and field IDs is not tainted by them; reading anything else taints it (ADR-0050.R25). Because trust is computed, a total that a corrected line makes inconsistent becomes untrusted at once, and a confirmation makes a typed value trusted without rewriting a row.
- with each extraction field it returns to a run, the dispatcher records in the step's `context_refs` the trust it served and the rule run number it used (ADR-0050.R19 note), so `INV-642` checks what was served, not what the view says later.
- the rule reads spec 03 rule 1 ("all external content is labeled untrusted") as applying to free text and to values no deterministic check has confirmed. Beyond the signed XML of ADR-0051.R20, OCR of outside pixels, spreadsheets and cards can give trusted values, under these conditions: the normalized value only, a closed shape per type, codes and units only when they resolve to a record, at least one passed rule in the latest run, a person's confirmation for vision values.
- trust means only that a value carries no instruction. The auto-post gateway counts a value that this rule trusts as basis `trusted`, and the purchase invoice checker still cross-checks amounts and quantities against the order and the receipt (ADR-0065.R10, ADR-0065.R19).
Source: ADR-0057.R17, ADR-0057.R17.N2

### Injection defenses

R226. Injection defenses:
- containment: the vision model has no tools, no memory and no outbound channel; it returns only the typed schema of R213, and code checks every value (R214-R216). An injected instruction has nowhere to go but a field whose shape cannot hold it, or free text, which is untrusted;
- render, then read: the model reads the rendered page image, never the PDF's text layer;
- datamarking: any text passed to a model inside untrusted delimiters (ADR-0050.R8) also has a marker character between words, and the template says so (spotlighting);
- classifiers: an injection classifier, where installed, sets `injection_signal` and the check result `injection_signal`. It is a signal for the reviewer, never a gate and never a reason to trust.
Source: ADR-0057.R18

R227. Hidden text is found by position. A text-layer word is confirmed (`is_on_render` true) only by an OCR word of the rendered page with equal normalized text whose box overlaps it by at least half of the smaller box. A run of at least three consecutive unconfirmed text-layer words, or 20 characters, sets `hidden_text_suspected`, the check result `hidden_text_suspected` and full review (R224).
- The hidden words stay as `text_layer` rows with `is_on_render` false, shown to the reviewer as untrusted evidence.
- Text-layer words take part in rung 5 only where they are confirmed, and rung 5's evidence carries their region.
- Text that OCR reads but people barely see (tiny or low-contrast print) is not hidden text by this test; the evidence box on the screen shows the reviewer where each value stands.
Source: ADR-0057.R18

### Personal data, links and retention

R228. Labels and derived images:
- photos, business cards, delivery notes, voice and inquiry attachments are labelled `personal` as a whole when created, as is every attachment from inbound e-mail. The label is set at creation and never lowered; a reader that finds only organizations does not change it (an e-invoice record's own fields take their labels by partner kind, ADR-0019.R7). Extractions and their fields take the attachment's label or a higher one (`INV-643`).
- every derived image sent anywhere is re-encoded without EXIF, location or device metadata. The original keeps its bytes under the attachment's access rules.
- a redacted copy is still `personal`; redaction never makes an image non-personal.
Source: ADR-0057.R19

R229. `extraction_result_link` names each subject an extraction led to, by `target_table`: `e_invoice_record`, `change_proposal`, `contact`, `partner`, `quotation`, `purchase_invoice`, `bill_of_materials_revision` or `inspection_result` (ADR-0070.R11). The executing consumer of a contact proposal adds the created contact and partner.
Source: ADR-0057.R19

R230. Erasure and retention of extractions:
- the subject's extractions, for `EraseDataSubject` (ADR-0052.R25): those whose `partner_id` is the subject (an individual, sole proprietorship or employee partner), those linked to the subject's contact or partner, and those of the subject's inbound messages;
- erasure blanks `value_raw` and `value_normalized` of their fields to empty text, sets their `evidence` to the blank marker `{}` of ADR-0079.R1 and blanks the text of their words, keeping rows, statuses and counts (ADR-0019.R10); the append-only guard accepts only the erasure results of ADR-0079.R6;
- an extraction linked to an incoming e-invoice record or to a posted accounting document is kept with its attachment for the accounting retention (ADR-0038.R15). Erasure then blanks only the fields that are not among its purpose's accounting fields (for a supplier invoice: contact persons, phones and e-mails printed on it); the accounting fields stay as voucher evidence.
Source: ADR-0057.R19, ADR-0057.R19.N1

### Verification

R231. The verification screen is one of the hand-built screens (ADR-0040.R6 note) and is the registered custom component `extraction_verification`. Dropping a file on a generated form calls `RequestDocumentExtraction` with the form's purpose, and the verified result opens as a draft in that form with per-field provenance (ADR-0077.R18, ADR-0077.R22). The screen shows:
- the page on one side with each field's evidence box, the fields on the other; for an e-invoice, the record's own fields first and the rendering beside them;
- fields ordered by the purpose's risk order: amounts, tax IDs, bank details and dates first;
- keyboard first: Enter confirms a field and moves on; typing corrects it; a click on the page selects the words for a field;
- machine-checked fields (parsed, OCR or aligned, with every rule passing) apart from human-confirmed ones, and unaligned suggestions greyed;
- duplicates found, the hidden-text flag, the injection signal and failed rules at the top;
- the attempts of the ladder and the reader of each value on demand.
Source: ADR-0057.R22, ADR-0057.R22.N1

R232. The verification commands are in module `attachments`, with effect class `other`, `human_only`, at `edit` on the purpose's leaf. Agents never verify. A command on an extraction in a final state returns `extraction_not_reviewable`.
- `VerifyExtractionFields` (extraction, list of current field rows) appends one `extraction_confirmation` row per field (confirmed by, at). A row that is no longer current is refused (`extraction_field_superseded`); a `vision_unaligned` row cannot be confirmed as it is. No rule run follows (R218).
- `CorrectExtractionField` (verb Correct; extraction, field path, the row it supersedes or none, value, optional evidence) appends a `human` row with the same value type and its confirmation; a new rule run follows in the same transaction (R218). It emits `ExtractionFieldCorrected`.
Source: ADR-0057.R23

R233. Ending an extraction:
- `VerifyDocumentExtraction` moves `needs_review` (or `extracted`) to `verified` when every required field of the purpose, or every field under full review, has a current confirmed row, every rule of the latest run passes or is named in `rule_overrides` with a non-empty reason and is not `shape` (R220; the database holds the shape of the entries), and no decisive duplicate stands; otherwise `extraction_verification_incomplete` or `duplicate_external_document`, naming the fields. It resolves the work item and emits `DocumentExtractionVerified`. These conditions need other rows, so the command holds them, and `INV-644` checks them.
- `CancelDocumentExtraction` (reason) ends the record as `canceled`, resolving the item, and emits `DocumentExtractionCanceled`.
Source: ADR-0057.R23

## Invariants

Statements are those of `invariants.csv`. Each row stands once in the module, in the chunk that states the rule its catalog source names.

| Invariant | Name | Check point | Statement | Protects |
| --- | --- | --- | --- | --- |
| `INV-640` | `extraction_rows_append_only` | day | No extraction field, rule run or confirmation row changed after insert except by erasure; every rule run was written in the transaction of a recording, vision write or correction; every superseding field row has the same extraction, field path and value type as the row it supersedes, is a human row or a machine row replacing a row not found or illegible, and supersedes a row no other row supersedes; each path has one root row. | R207, R218, R232 |
| `INV-641` | `vision_values_from_reader_runs` | day | Every `vision_aligned` and `vision_unaligned` row names a run of the agent type `document_reader`, every `vision_aligned` row's words are consecutive on one line, and no `vision_unaligned` row has a confirmation. | R213, R214, R216 |
| `INV-642` | `served_trust_holds` | day | For every extraction field in an agent run step's `context_refs`, the stored served trust equals the trust recomputed from the rows up to the stored rule run number, and a step that received a field served untrusted, or its raw text or evidence, belongs to a run tainted at or before that step. | R224, R225 |
| `INV-643` | `extraction_label_not_lower` | day | Every extraction's and field's data label is at least its attachment's. | R202, R228 |
| `INV-644` | `verified_extraction_complete` | day | Every extraction in state `verified` has a current confirmed row for every required field of its purpose, and for every field when a full review is required; every result of its latest rule run before the verification passed, or is named in `rule_overrides` with a reason and is not `shape`. | R233 |

## Edge cases

| Edge case | Name | Case | Outcome | Protects |
| --- | --- | --- | --- | --- |
| `EC-133` | `e_invoice_resent_other_bytes` | The same invoice arrives again as other bytes with the same supplier-invoice key and a passed signature; the import is refused naming the first record (area `purchasing`; first step 5). | `must_reject:duplicate_external_document` | R221 |
| `EC-135` | `pdf_hidden_instruction` | A PDF invoice carries white text telling an agent to change the bank account; hidden text is flagged by position (`hidden_text_suspected`), the review is full, and nothing changes (area `safety`; first step 5). | `must_succeed` | R227 |
| `EC-136` | `document_bank_account_differs` | A PDF invoice names a bank account the supplier master does not have; the check result `document_bank_account_differs` is shown and no master data or payment changes (area `safety`; first step 5). | `must_succeed` | R222 |
| `EC-139` | `vision_total_on_two_lines` | A vision value for a total cites words on two lines; it is stored unaligned, fills nothing, and the computed total decides the rule (area `documents`; first step 5). | `must_succeed` | R214, R216 |

## Settings

None: the keys named by rules of this chunk have their rows in chunk 3, with the rules that define them (ADR-0063.R27, ADR-0063.R7): `intake.duplicate.date_window_days`, `intake.duplicate.amount_tolerance_minor_units`, `intake.duplicate.number_normalization`, `intake.duplicate.near_outcome` (R221); `intake.trust.<document_type>.<field>.require_confirmation`, `intake.trust.<document_type>.min_passed_rules`, `intake.trust.ocr_min_confidence` (R224). `intake.vision_max_pages` (R212) is named in chunk 3 with the settings of ADR-0057.R37.

## UI annotations

- Custom component: `extraction_verification`, the verification screen (R231; ADR-0077.R18, ADR-0077.R22).
- Work item kind `document_extraction_review`: declared by the agent type `document_reader` (R211); resolved by `VerifyDocumentExtraction` and also by `CancelDocumentExtraction` (R233); its row is in the work item kind table of chunk 3 (ADR-0057.R33).
- The sources of this chunk give no floorplan, facet or tile.

## Conflicts

CONFLICT ADR-0057.R15: ADR-0057.R15.N1 (ADR-0063.R27) governs the near check; its window, amount tolerance and number normalization are company settings and not constants of the purpose, and with `near_outcome` `review` the payment is held, so "advisory only" and "level 3 never blocks" are not restated as they stood: level 3 refuses no document and holds the payment (R221).
CONFLICT ADR-0057.R17: ADR-0057.R17.N1 (ADR-0063.R7) makes the reading of value trust the default that settings only tighten, so the mark "Interim, as stated, until the author answers (open question)" is not restated (R224, R225).
CONFLICT ADR-0057.R19: ADR-0057.R19.N1 governs the erasure of `evidence`: the blank marker `{}` of ADR-0079.R1, not `{"erased": true}` (R230). ADR-0070.R11 with the DS-36 DDL adds the target `inspection_result` to the result links (R229).

## Trace

| Source | Where |
| --- | --- |
| ADR-0057.R7 | R201-R204 |
| ADR-0057.R8 | R205-R208 |
| ADR-0057.R9 | R209 |
| ADR-0057.R10 | R210 |
| ADR-0057.R11 | R211-R213 |
| ADR-0057.R12 | R214-R216 |
| ADR-0057.R13 | R217 |
| ADR-0057.R14 | R218-R220 |
| ADR-0057.R15 | R221 |
| ADR-0057.R15.N1 | R221 |
| ADR-0057.R16 | R222 |
| ADR-0057.R17 | R223-R225 |
| ADR-0057.R17.N1 | R224 |
| ADR-0057.R17.N2 | R225 |
| ADR-0057.R18 | R226, R227 |
| ADR-0057.R19 | R228-R230 |
| ADR-0057.R19.N1 | R230 |
| ADR-0057.R22 | R231 |
| ADR-0057.R22.N1 | R231 |
| ADR-0057.R23 | R232, R233 |
