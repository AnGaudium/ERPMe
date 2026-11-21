Module: attachments    Chunk: 3 of 3    Source ADRs: ADR-0057, ADR-0063
Build step(s): 1, 5    Generated from index: 30d5706    Compiled by: Claude Fable 5.2, 2026-11-21

# `attachments` compiled spec, chunk 3: document flows from a mailbox and uploads, registrations, trust and near-duplicate settings

## Purpose

`attachments` owns stored files, their links and document extraction (ADR-0022.R2). This chunk states the document flows that
use an extraction (supplier invoices from a mailbox, PDF-only supplier invoices, business cards, inquiry attachments), the
registrations of ADR-0057 (commands, events, error codes, check results, work item kinds, invariants, edge cases, settings,
lab check) and the settings of extraction value trust and near-duplicate invoices. Chunks 1 and 2 state the attachment
store, the reader ladder, the extraction tables, value trust and verification. The agent type `document_reader` and its
promotion (ADR-0057.R34, ADR-0078.R1, ADR-0078.R6, ADR-0078.R8, ADR-0078.R15), the purposes `shop_floor_report`
(ADR-0064.R27) and `certificate_of_analysis` (ADR-0070.R11), the work case kind `supplier_invoice` (ADR-0066.R3) and message
attachments (ADR-0076.R4) belong to other modules; their units are traced `ref:` and not restated.

## Entities and tables

DDL: `docs/design/DS-36-document-intake.sql` and `docs/design/DS-05-platform.sql`. The rules of this chunk define no table.
They use tables whose rows stand in chunk 1 (`attachment`, `attachment_link`, `document_reader`) and chunk 2 (the others):

- `document_extraction`: `partner_id` (R405), `inbound_message_id` (R402), `signature_state` (R406, R410), `canceled_reason` with the system's value `rendering_of_parsed_xml` (R412).
- `extraction_result_link`: links an extraction to the `e_invoice_record` it led to (R406, R409) and to a change proposal (R419).
- `extraction_field`, `extraction_rule_run` and `extraction_confirmation`: checked by `INV-640` to `INV-644` (R434).
- `document_reader`: the agent type and the reader registry of the same name (R432).
- `attachment`, `attachment_link` and `extraction_word`: no rule of this chunk changes them; R412 reads the text-layer words of a PDF.

Reads: `mailbox`, `inbound_message`, `e_invoice_record`, `partner`, `contact`, `quotation`, `change_proposal`, `open_item_collection`, `agent_run_step`, `data_processing_permission`, `message`.

## Commands and queries

The registrations are R424 and the events R428. Each command has one row in the module: `RequestDocumentExtraction` and `RecordDocumentExtraction` in chunk 1 (ADR-0057.R3, ADR-0057.R4); `CreateExtractionFields`, `VerifyExtractionFields`, `CorrectExtractionField`, `VerifyDocumentExtraction` and `CancelDocumentExtraction` in chunk 2 (ADR-0057.R11, ADR-0057.R23).

| Name | Actor and authorization | Input | Effect | Events | Error codes |
| --- | --- | --- | --- | --- | --- |
| `GetDocumentExtraction`, `ListDocumentExtraction` | The purpose's leaf, `read` | not stated | Queries: fields and words with their labels and computed trust | None (queries) | not stated |

Not commands of `attachments`: the consumers `mailbox_document_intake` (`crm`, R402), `e_invoice_intake` (`tax`, R406) and the `purchasing` consumer of `DocumentExtractionVerified` (R416); the commands of other modules that R425 registers; `UpdateMailbox` (`crm`), `ImportEInvoiceRecord` and `ConfirmEInvoiceSupplier` (`tax`).

Codes of R429 bound to no command of `attachments`: `e_invoice_schema_unknown` (the package's e-invoice reader, ADR-0057.R6), `data_processing_not_permitted` (ADR-0057.R20), `mailbox_owner_not_permitted` (`UpdateMailbox`, R401), `e_invoice_superseded` (`ConfirmEInvoiceSupplier`, R411). Codes of other modules that the rules of this chunk name: `duplicate_external_document`, `agent_scope_unresolved`, `open_item_payment_blocked`.

## Rules

### Supplier invoices from a mailbox

R401. `mailbox` has `document_intake_purpose` (`supplier_invoice`, `inquiry_lines`, `shop_floor_report` by ADR-0064.R26 and ADR-0064.R27, or empty) and `document_intake_quarantine_limit` (default 20). `UpdateMailbox` (`human_only`, ADR-0052.R11) refuses a purpose when the mailbox owner does not hold `edit` on the purpose's leaf (`mailbox_owner_not_permitted`), so deliveries never fail for rights.
Source: ADR-0057.R25

R402. Route, XML first. The `crm` consumer `mailbox_document_intake` of `InboundMessageRecorded` requests, as `system` on behalf of the mailbox owner and with `inbound_message_id`, an extraction for every XML part first. Other parts are requested only after every XML part of the message is recorded, by the same consumer reacting to their `DocumentExtractionRecorded`, or by its daily sweep once `crm.document_intake_xml_timeout_minutes` (default 60) have passed without a recording; and only when the message is matched to exactly one active partner (ADR-0052.R15), which needs its sender authentication to pass (ADR-0052.R14). Authentication alone is not enough: a stranger's domain or a free mail address can pass it. From a message that is not matched, non-XML parts are stored only, and a person may request their extraction from the message.
Source: ADR-0057.R25

R403. The quarantine cap is decided after the read, when the signature state is known. The cap counts the quarantined records imported from messages not matched to a partner, per mailbox and business date, the date being the message's receipt in the company's time zone; records of matched messages and records with a passed signature never count. Past the cap, the XML's extraction is still recorded as `extracted` but its record is not imported: the extraction carries the check result `quarantine_limit_reached`, and one `e_invoice_quarantine_overflow` item per mailbox and business date tells the mailbox owner and lists those extractions. A person imports any of them from the item with `ImportEInvoiceRecord`, which then follows the person's import path (R408), or closes the item. Nothing is canceled for the cap.
Source: ADR-0057.R25

R404. There is no daily part limit and no other limit: non-XML parts of messages not matched to a partner are stored only and cost no reading; XML parts cost a bounded deterministic read (ADR-0057.R5) and their quarantined records are capped; documents of matched partners are read, and the agent budgets of ADR-0050.R22 bound them where a model is involved.
Source: ADR-0057.R25

R405. `partner_id` of the extraction is the active supplier whose normalized tax ID equals a `passed` seller tax ID (exactly one), else the interaction's matched partner, else empty. It selects the mapping rules of ADR-0057.R5.
Source: ADR-0057.R25

R406. XML to the record. When rung 1's e-invoice reader gives a structurally valid record (schema and arithmetic), the `tax` consumer `e_invoice_intake` of `DocumentExtractionRecorded` runs `ImportEInvoiceRecord` as `system` on behalf of the human the request acted for (the mailbox owner for the mailbox route), whatever the signature, with `source_attachment_id`, `inbound_message_id`, `signature_state`, the clearance code state (`present`, `missing`, `not_required`), the arithmetic outcome and both the stated issue time and the signing time. The extraction links the record (`extraction_result_link`) and ends `extracted`; it raises no review item of its own, so each XML gives at most one human task, the record's.
Source: ADR-0057.R25

R407. One record per file. `e_invoice_record.source_attachment_id` is unique among incoming records: a second import of the same attachment, by the route, a person, or two people importing the same listed extraction, returns the first record and creates nothing.
Source: ADR-0057.R25

R408. A person's upload. For an XML a person uploaded and requested (`RequestDocumentExtraction`, purpose `supplier_invoice`), the consumer `e_invoice_intake` imports it on behalf of that person, with `imported_by_user_id` set to them, so the importer confirmation of ADR-0051.R20 applies. Quarantine, supersession and key conflicts work as for the mailbox, and the quarantine cap does not apply.
Source: ADR-0057.R25

R409. Duplicates are an outcome. `duplicate_external_document` from the import ends the route normally: the extraction gets the check result `duplicate_key_found` and a link to the existing record, and the delivery completes.
Source: ADR-0057.R25

R410. Quarantine. A record whose `signature_state` is not `passed` is imported quarantined (`is_quarantined`): it holds no supplier-invoice key, and the purchase invoice agent starts only after a person confirms its supplier with `ConfirmEInvoiceSupplier`, which lifts the quarantine; the key check runs then and refuses a second holder (`duplicate_external_document`). The structured fields of a `failed` or `signer_mismatch` record count as untrusted; those of an `absent` one do not, unless the package's format declares the signature mandatory (ADR-0057.R6). Quarantined records of one sender in one mailbox on one business date share one `e_invoice_quarantine_review` item, the one human task for them; records that share a key are shown together in it.
Source: ADR-0057.R25

R411. Supersession and conflict. A later record with the same key and a `passed` signature supersedes a quarantined one: the quarantined record gets `superseded_by_record_id`, and `e_invoice_record_superseded` tells an accountant. `ConfirmEInvoiceSupplier` refuses a superseded record (`e_invoice_superseded`). When the key is held by a confirmed, formerly quarantined record, the record with a passed signature is still imported, with `key_conflict_with_record_id` naming the holder and the check result `e_invoice_key_conflict`; it raises the work item `e_invoice_key_conflict` for an accountant, and no agent starts on either record until a person resolves the conflict. A genuine signed invoice is never refused silently.
Source: ADR-0057.R25

R412. The companion PDF. A PDF of the same message is the XML's rendering only when the XML's invoice number appears as a whole token in the PDF's text layer; the file name stem only decides between several XML parts that match. It is then linked to the record as its rendering, as received and unverified, and its request ends `canceled` by the system with reason `rendering_of_parsed_xml`. Any other PDF is extracted as a document of its own.
Source: ADR-0057.R25

R413. The e-invoice provider connection (pulling records from a provider or the tax authority, the authority status and revocation check) stays the DS-24 add-on; it uses the same import path.
Source: ADR-0057.R25

### PDF-only supplier invoices

R414. Ladder for a PDF-only supplier invoice: an embedded XML is parsed first (rung 2). Otherwise the text layer, confirmed by OCR, and OCR words with the package's label anchors and the supplier's mapping rules (rungs 5 and 6); vision only where the seat is enabled.
Source: ADR-0057.R26

R415. Full human verification: every required field is confirmed by a person; there is no automatic posting and no automatic match, and the extraction never reaches `extracted` from rungs 5 to 7.
Source: ADR-0057.R26

R416. A `purchasing` consumer of `DocumentExtractionVerified` raises `supplier_invoice_extracted` (subject the extraction) for a verified supplier-invoice extraction without an e-invoice record. Version 1.1.0 of the purchase invoice agent declares that kind and accepts `document_extraction` as a subject (ADR-0051.R20):
   - Scope: the supplier whose normalized tax ID equals the verified `seller_tax_id`, when exactly one active supplier has it; otherwise `agent_scope_unresolved`.
   - Inputs, from the current confirmed fields: `seller_tax_id`, `invoice_number` and the package's key fields as the partner reference, `issue_date` as the supplier invoice date, `currency`, `net_total`, `tax_amount`, `gross_total`, and per `lines[n]`: `seller_item_code`, `item_name` (free text, untrusted), `unit_text`, `quantity`, `unit_price`, `line_amount`, `tax_rate`.
   - Steps: D1 is the duplicate key check (ADR-0057.R15), then D2 to D5 of ADR-0051.R21. The run starts tainted, as every run on an outside subject.
   Source: ADR-0057.R26

### Business cards

R417. QR first: rung 3 decodes a QR code with a vCard or MeCard into contact fields (name, organization, job title, e-mails, phones, address, URL). The values are personal; names, e-mails, phones and URLs are untrusted.
Source: ADR-0057.R27

R418. Without a QR code, rung 6 gives OCR words; the vision step runs only where the seat is enabled; otherwise a person keys the fields beside the image.
Source: ADR-0057.R27

R419. After verification, `ProposeContactFromExtraction` (module `crm`, effect class `other`, `is_draft_only`, verb Propose at `edit` on `partner`) drafts a change proposal with `CreateContact`, and `CreatePartner` when the person chose a new partner, from the confirmed fields, and links it. The server's duplicate checks on e-mail and phone (ADR-0052.R17) are in its plan. The proposal copies untrusted names, so it is tainted; a person submits it and another approves it (ADR-0043.R9, floor 7).
Source: ADR-0057.R27

### Inquiry attachments

R420. Spreadsheets: rung 4 reads cell values into rows `lines[n].*` with cell evidence. Header mapping is by exact header, then the partner's `column_header` rules; merged headers are unmerged by position; a cell with a formula is read as its cached value with the check result `formula_cell_found`; a cell beginning with `=`, `+`, `-` or `@` is kept as text and never evaluated.
Source: ADR-0057.R28

R421. `GetQuotationLinesFromExtraction` (module `sales`, computed query, at `read` on `quotation`) turns the rows of an extracted or verified extraction into proposed quotation lines: item by the partner's item code, the company's item code or a barcode, each as a whole value; unit by the partner item's unit text, the unit aliases or a unit code; quantity as stated. Unresolved rows are returned as such. A person creates or updates the quotation from the result; no row becomes a line without a person.
Source: ADR-0057.R28

R422. Drawings and PDF requests are stored, shown beside the quotation and not read in Phase 1 unless the vision seat is enabled for the company.
Source: ADR-0057.R28

### Later than Phase 1

R423. Later than Phase 1: delivery-note photo extraction to a draft goods receipt; drawing and PDF request reading (title blocks, parts lists); per-supplier straight-through processing after a golden set shows it; voice notes by a local speech recognizer, with the transcript's audio spans as evidence (`audio_span`), personal and untrusted, drafts only.
Source: ADR-0057.R29

### Registrations: commands, queries and events

R424. Commands and queries of module `attachments`, with effect class, flags, leaf and level (ADR-0054.R7 to ADR-0054.R9):
   - `RequestDocumentExtraction`: `other`; the purpose's leaf, `edit`.
   - `RecordDocumentExtraction`: `other`; the runner only; on no tool list; the purpose's leaf, `post` (system).
   - `CreateExtractionFields`: `other`, `is_draft_only`; `document_reader` workflow code only; the purpose's leaf, `edit`.
   - `VerifyExtractionFields`, `CorrectExtractionField`, `VerifyDocumentExtraction`, `CancelDocumentExtraction`: `other`, `human_only`; the purpose's leaf, `edit`.
   - `GetDocumentExtraction`, `ListDocumentExtraction`: queries; fields and words with their labels and computed trust; the purpose's leaf, `read`.
   Source: ADR-0057.R31

R425. Commands and queries that ADR-0057 registers in other modules:
   - `CreateExtractionMappingRule`, `UpdateExtractionMappingRule`: module `master_data`; `master_data_change`, change-tracked; `partner`, `edit`.
   - `ProposeContactFromExtraction`: module `crm`; `other`, `is_draft_only`; `partner`, `edit`.
   - `GetQuotationLinesFromExtraction`: module `sales`; computed query; `quotation`, `read`.
   - `SetDataProcessingPermission`: module `agents`; `master_data_change`, change-tracked, `is_proposal_bound`; on no tool list; leaf `data_processing` under `agent` (ADR-0063.R14), `full` (declared minimum).
   - `EndDataProcessingPermission`: module `agents`; `master_data_change`, `human_only`; on no tool list; leaf `data_processing` under `agent` (ADR-0063.R14), `full` (declared minimum).
   Source: ADR-0057.R31

R426. Verbs added to the glossary and the verb catalog: Correct (`edit`), Propose (`edit`), End (`edit`; a command may declare a higher minimum).
Source: ADR-0057.R31

R427. The leaf `agent_document_reader` stands under `agent` and holds the capability `start_agent:document_reader` at `edit`; the templates `accountant` and `sales_clerk` hold it at `edit`.
Source: ADR-0057.R31

R428. Events, carrying IDs and codes only (ADR-0013.R4): `DocumentExtractionRequested`, `DocumentExtractionRecorded`, `ExtractionFieldCorrected`, `DocumentExtractionVerified`, `DocumentExtractionCanceled`.
Source: ADR-0057.R31

### Registrations: error codes and check results

R429. DS-04 error codes: `extraction_purpose_exists` (conflict), `extraction_not_reviewable` (precondition), `extraction_field_superseded` (conflict), `extraction_verification_incomplete` (precondition), `e_invoice_schema_unknown` (validation), `data_processing_not_permitted` (permission), `mailbox_owner_not_permitted` (permission), `e_invoice_superseded` (precondition).
Source: ADR-0057.R32

R430. DS-04 check results: `extraction_rule_failed`, `hidden_text_suspected`, `injection_signal`, `document_bank_account_differs`, `duplicate_key_found`, `duplicate_document_suspected`, `vision_value_unaligned`, `formula_cell_found`, `e_invoice_quarantined`, `e_invoice_key_conflict`, `quarantine_limit_reached`, `extraction_rule_overridden`.
Source: ADR-0057.R32

R431. Denial records (ADR-0038.R5) also cover `data_processing_not_permitted`.
Source: ADR-0057.R32

### Registrations: work item kinds

R432. `document_extraction_review` is a work item kind of module `attachments`, subject `document_extraction`, declared by `document_reader`. Its owner rule is `extraction_owner`: the requester for a person's request; for a mailbox request the purpose's role, `role:accountant` for supplier invoices and `role:sales_clerk` for inquiry lines. It is due `days:2` and is resolved by `VerifyDocumentExtraction` or `CancelDocumentExtraction`. It is never raised for an XML whose record was imported.
Source: ADR-0057.R33

R433. Work item kinds that ADR-0057 registers in other modules:
   - `supplier_invoice_extracted`: module `purchasing`, subject `document_extraction`, owner `role:accountant`, due `days:2`; declared by the purchase invoice agent 1.1.0 (R416).
   - `e_invoice_record_superseded`: module `tax`, subject `e_invoice_record`, owner `role:accountant`, due `days:2` (R411).
   - `e_invoice_quarantine_overflow`: module `tax`, subject `mailbox`, open key the business date, owner `subject_owner:owner_user_id`, due `days:1`, resolved when each listed extraction is imported or the owner closes it (R403).
   - `e_invoice_quarantine_review`: module `tax`, subject `mailbox`, open key the sender and business date, owner `role:accountant`, due `days:2`, resolved when every record it lists is confirmed or superseded (R410).
   - `e_invoice_key_conflict`: module `tax`, subject `e_invoice_record`, owner `role:accountant`, due `days:1` (R411).
   Source: ADR-0057.R33

### Registrations: invariants, edge cases, settings and lab check

R434. Document intake holds `INV-640` to `INV-646` of the DS-16 block `INV-640` to `INV-669`, in the areas `platform`, `safety` and `tax`, with first step 5. Each statement stands once, in its row of the Invariants table: `INV-640`, `INV-641`, `INV-642`, `INV-643` and `INV-644` in chunk 2; `INV-645` and `INV-646` in this chunk. For `INV-642`, the extraction's flags are set before any field is served.
Source: ADR-0057.R35

R435. Document intake holds the DS-17 edge cases `EC-132` to `EC-139` and `EC-145` to `EC-148`, of the block `EC-132` to `EC-149` that ADR-0057 and ADR-0062 share. Each case stands once, in its row of the Edge cases table: `EC-134` and `EC-145` in chunk 1; `EC-133`, `EC-135`, `EC-136` and `EC-139` in chunk 2; `EC-132`, `EC-137`, `EC-138`, `EC-146`, `EC-147` and `EC-148` in this chunk. The identifiers the cases end on: `EC-132` the PDF's extraction `canceled`; `EC-133` `duplicate_external_document`; `EC-134` `e_invoice_record_superseded`; `EC-135` `hidden_text_suspected`; `EC-136` `document_bank_account_differs`; `EC-145` `signer_mismatch`; `EC-148` `key_conflict_with_record_id` and `e_invoice_key_conflict`.
Source: ADR-0057.R36

R436. Settings of document intake: regime `data_processing.policy` (registered without a default, ADR-0057.R20); package `intake.e_invoice_formats` (registered key, value per package); company `intake.vision_max_pages` (default 10, lowering only); mailbox `document_intake_quarantine_limit` (default 20); company `crm.document_intake_xml_timeout_minutes` (default 60).
Source: ADR-0057.R37

R437. The lab check `t20_intake.py` of the validation lab holds pure functions for: the ladder order and the stop at the first valid record; alignment (a value at adjacent consecutive words of one line and cell passes; scattered words, words across table cells and fabricated values fail; numbers exactly); closed shapes and value trust computed from rule runs and confirmations; rules over confidence; the duplicate levels with quarantine; the signature conditions; the hidden-text flag by position; vCard parsing; spreadsheet reading; the companion PDF test; mailbox gating; and the policy without a default. With `--load`, on the schema of `load_all.py`, it checks: append-only fields, one root per path, corrections keeping the type, the trust view, rule runs and confirmations, the state transitions and set-once flags, result links, mapping rules and permissions.
Source: ADR-0057.R38

### Extraction value trust settings

R438. The computed trust of ADR-0057.R17 is the default reading, with one addition: the OCR confidence floor of R439, a tightening (ADR-0063.R5).
Source: ADR-0063.R7

R439. Trust settings, company scope, read by the trust view:
   - `intake.trust.<document_type>.<field>.require_confirmation`: default false; when true, a person must confirm the field before it is trusted.
   - `intake.trust.<document_type>.min_passed_rules`: default 1, bounds 1 to 10.
   - `intake.trust.ocr_min_confidence`: default 0.90, bounds 0.80 to 0.99, applied where the OCR engine reports a confidence; below it the field is untrusted.
   Source: ADR-0063.R7

R440. Loosening a trust setting, also below the core default down to the lower bound, is a proposal that names `extraction_mapping` evidence of at least 95% field agreement over at least 50 documents (ADR-0059.R18). Nothing loosens past the bounds or the shape table.
Source: ADR-0063.R7

R441. Hard limits of extraction value trust: free text, URLs, e-mails and phones are never trusted; vision values are never trusted before a person confirms them; nothing is trusted from an extraction with a failed or mismatched signature or suspected hidden text; trust alone never posts or changes master data.
Source: ADR-0063.R7

### Near-duplicate invoices

R442. Settings of the near-duplicate check (level 3 of ADR-0057.R15), company scope: `intake.duplicate.date_window_days` (7, bounds 0 to 90), `intake.duplicate.amount_tolerance_minor_units` (1, bounds 0 to 100), `intake.duplicate.number_normalization` (`digits_only`, the default, `alnum_casefold` or `exact`) and `intake.duplicate.near_outcome` (`review`, the default, or `advisory`).
Source: ADR-0063.R27

R443. Under `review`, a purchase invoice posted while level 3 suspects a duplicate gets, in the transaction that posts it, `is_payment_blocked` and `payment_block_reason` `duplicate_review` on its open item's `open_item_collection` row (ADR-0048.R17), and raises `duplicate_document_review`. `review` is the default outcome of a near duplicate, not an advisory flag alone, because an advisory flag alone let a duplicate be paid (ADR-0063.R5).
Source: ADR-0063.R27, ADR-0063.R27.N1

R444. A person resolves `duplicate_document_review` by recording "not a duplicate" with a reason, which clears `is_payment_blocked` and `payment_block_reason` in the transaction that resolves the item, or by canceling or reversing the document, which leaves no open amount to pay. Until then a cash or bank payment cannot settle the item (`open_item_payment_blocked`, checked on the line and again at `Post`). Lab check `t15_platform_ddl.py` L04 and L05.
Source: ADR-0063.R27, ADR-0063.R27.N1

R445. Hard limits of the duplicate check: the exact key cannot be switched off and runs on every channel (intake, manual entry, import, agent); a match is never deleted or rejected without a person.
Source: ADR-0063.R27

## Invariants

Statements are those of `invariants.csv`, with the identifiers of R434's source. Each row stands once in the module; this chunk holds the rows whose catalog source is a rule of this chunk or a rule of no chunk.

| Invariant | Name | Check point | Statement | Protects |
| --- | --- | --- | --- | --- |
| `INV-645` | `vision_only_with_permission` | day | Every LLM request of any run mode that carried an attachment page was covered, at its `recorded_at`, by an active data-processing permission (`data_processing_permission`) for its company, data class, seat class, provider and registered region, with the company's routing switch off (area `safety`; first step 5). | R434; ADR-0057.R20, ADR-0057.R21 |
| `INV-646` | `e_invoice_key_among_unquarantined` | day | Two incoming e-invoice records that are not quarantined share a supplier-invoice key only when the later has a passed signature and names the earlier in `key_conflict_with_record_id`; a record with `superseded_by_record_id` is quarantined and names a record with a passed signature and the same key (area `tax`; first step 5). | R407, R410, R411 |

Rows in other chunks: `INV-83` in chunk 1; `INV-640`, `INV-641`, `INV-642`, `INV-643` and `INV-644` in chunk 2. `INV-881` is named by ADR-0076.R4 and belongs to `work`.

## Edge cases

Cases are those of `edge-cases.csv`. Each row stands once in the module; this chunk holds the rows whose catalog source is a rule of this chunk or a rule of no chunk.

| Edge case | Name | Case | Outcome | Protects |
| --- | --- | --- | --- | --- |
| `EC-132` | `e_invoice_xml_by_mail` | A supplier e-mails an XML e-invoice with its PDF to a mailbox with purpose `supplier_invoice`; the system imports the record, the agent starts in the supplier's scope, and the PDF whose text layer holds the invoice number is linked as the rendering, its extraction ending `canceled` by the system (area `purchasing`; first step 5). | `must_succeed` | R402, R406, R412 |
| `EC-137` | `business_card_vcard_qr` | A business card photo with a vCard QR code becomes a contact change proposal with duplicate checks on e-mail and phone; the created contact is linked to the extraction (area `crm`; first step 5). | `must_succeed` | R417, R419 |
| `EC-138` | `business_card_no_permitted_provider` | A business card photo without a QR code in a company with no permitted provider; no model is called and a person keys the fields (area `safety`; first step 5). | `must_succeed` | R418; ADR-0057.R20, ADR-0057.R21 |
| `EC-146` | `pdf_beside_xml_other_invoice` | A message carries an XML invoice and a PDF of a second invoice; the PDF matches neither by file name nor by number and is extracted as its own document (area `purchasing`; first step 5). | `must_succeed` | R412 |
| `EC-147` | `unmatched_sender_pdfs` | A sender whose free mail address passes DKIM but matches no partner mails ten PDFs and an unsigned XML to the supplier-invoice mailbox; the PDFs are stored only and no OCR or vision runs until a person requests one, and the XML's quarantined record counts toward the cap (area `safety`; first step 5). | `must_succeed` | R402, R403, R404 |
| `EC-148` | `signed_after_confirmed_unsigned` | A person confirms the supplier of an unsigned record; the genuine signed invoice with the same key arrives later, is imported with `key_conflict_with_record_id`, raises `e_invoice_key_conflict`, and no agent starts until an accountant resolves it (area `safety`; first step 5). | `must_succeed` | R411 |

Rows in other chunks: `EC-134` and `EC-145` in chunk 1; `EC-133`, `EC-135`, `EC-136` and `EC-139` in chunk 2.

## Settings

| Key | Value type | Scope | Core default | Direction | Rule |
| --- | --- | --- | --- | --- | --- |
| `intake.trust.<document_type>.<field>.require_confirmation` | boolean | company (storage `setting_value`) | `false` | `true_tighter` | R439 |
| `intake.trust.<document_type>.min_passed_rules` | integer, bounds `1..10` | company (storage `setting_value`) | 1 | `higher_tighter` | R439, R440 |
| `intake.trust.ocr_min_confidence` | decimal, bounds `0.80..0.99` | company (storage `setting_value`) | 0.90 | `higher_tighter` | R438, R439 |
| `intake.duplicate.date_window_days` | integer, bounds `0..90` | company (storage `setting_value`) | 7 | `higher_tighter` | R442 |
| `intake.duplicate.amount_tolerance_minor_units` | integer, bounds `0..100` | company (storage `setting_value`) | 1 | `higher_tighter` | R442 |
| `intake.duplicate.number_normalization` | enum `exact`, `alnum_casefold`, `digits_only` | company (storage `setting_value`) | `digits_only` | `order:exact<alnum_casefold<digits_only` | R442 |
| `intake.duplicate.near_outcome` | enum `advisory`, `review` | company (storage `setting_value`) | `review` | `order:advisory<review` | R442, R443 |
| `data_processing.policy` | object | regime (storage `regime_setting`) | no core default (R436); the catalog column reads `fail_closed` | `neutral` | R436 |

The rows of `attachments.delete_grace_days` and `attachments.evidence_retention_years` are in chunk 1.

R436 names keys that `settings.csv` does not hold: `intake.e_invoice_formats`, `intake.vision_max_pages` and `crm.document_intake_xml_timeout_minutes`. `document_intake_quarantine_limit` is a column of `mailbox`, not a setting key.

Reads: `agents.<agent_type>.drift_action`, `agents.<agent_type>.wake_up_mode.<kind>`, `assist.max_cost_per_run`, `auto_post.max_error_rate`, `cash.auto_post.accept_llm_originated_rules` (settings of other modules that the `ref:` units of this chunk name).

## UI annotations

The units of this chunk state no floorplan, title, facet, field annotation or tile. The verification screen is the registered custom component `extraction_verification` (ADR-0057.R22.N1, chunk 2). Work item kinds of `attachments` (catalog `work-item-kinds.csv`), the one table of the module:

| Kind | Subject table | Owner | Due | Resolution | Rule |
| --- | --- | --- | --- | --- | --- |
| `attachment_rejected` | `attachment` | `subject_owner:created_by_user_id` (its uploader) | `days:1` | `person` | ADR-0038.R14 |
| `document_extraction_review` | `document_extraction` | `extraction_owner` | `days:2` | `command`: `VerifyDocumentExtraction`, also `CancelDocumentExtraction` | R432; ADR-0057.R4, ADR-0057.R11, ADR-0057.R23 |

## Conflicts

CONFLICT ADR-0057.R25: the rule lists the mailbox purposes `supplier_invoice` and `inquiry_lines`; ADR-0064.R26, ADR-0064.R27 and the DDL of `mailbox` add `shop_floor_report`, so R401 states every value and cites both.
CONFLICT ADR-0057.R31: the rule's table puts `SetDataProcessingPermission` and `EndDataProcessingPermission` on leaf `agent`; the later ADR-0063.R14 moves both commands to the new leaf `data_processing` under `agent`, which R425 states, level `full` unchanged.

## Proposed (not law)

None

## Trace

| Source | Where |
| --- | --- |
| ADR-0057.R25 | R401-R413 |
| ADR-0057.R26 | R414-R416 |
| ADR-0057.R27 | R417-R419 |
| ADR-0057.R28 | R420-R422 |
| ADR-0057.R29 | R423 |
| ADR-0057.R31 | R424-R428 |
| ADR-0057.R32 | R429-R431 |
| ADR-0057.R33 | R432, R433 |
| ADR-0057.R34 | ref: ADR-0057.R34 |
| ADR-0057.R34.N1 | ref: ADR-0057.R34.N1 |
| ADR-0057.R35 | R434 |
| ADR-0057.R36 | R435 |
| ADR-0057.R37 | R436 |
| ADR-0057.R38 | R437 |
| ADR-0057.W | not applicable: worked examples; every identifier they use is stated by a rule |
| ADR-0062.D0 | ref: ADR-0062.D0 |
| ADR-0063.R7 | R438-R441 |
| ADR-0063.R27 | R442-R445 |
| ADR-0063.R27.N1 | R443, R444 |
| ADR-0064.R1 | ref: ADR-0064.R1 |
| ADR-0064.R1.N1 | ref: ADR-0064.R1.N1 |
| ADR-0064.R1.N2 | ref: ADR-0064.R1.N2 |
| ADR-0064.R27 | ref: ADR-0064.R27 |
| ADR-0066.R3 | ref: ADR-0066.R3 |
| ADR-0070.R11 | ref: ADR-0070.R11 |
| ADR-0076.R4 | ref: ADR-0076.R4 |
| ADR-0077.R23.N1 | ref: ADR-0077.R23.N1 |
| ADR-0078.D0 | ref: ADR-0078.D0 |
| ADR-0078.R1 | ref: ADR-0078.R1 |
| ADR-0078.R1.N1 | ref: ADR-0078.R1.N1 |
| ADR-0078.R6 | ref: ADR-0078.R6 |
| ADR-0078.R8 | ref: ADR-0078.R8 |
| ADR-0078.R13.N1 | ref: ADR-0078.R13.N1 |
| ADR-0078.R15 | ref: ADR-0078.R15 |
