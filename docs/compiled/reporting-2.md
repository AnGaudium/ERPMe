Module: reporting    Chunk: 2 of 2    Source ADRs: ADR-0049, ADR-0056, ADR-0059, ADR-0061
Build step(s): 3, 4, 8    Generated from index: 30d5706    Compiled by: Claude Fable 5.2, 2026-11-21

# Compiled spec: `reporting`, chunk 2

## Purpose

`reporting` is a layer-4 module (ADR-0022.R2). It owns statutory report and book definitions, print templates, print
data contracts and render jobs; it imports no other layer-4 module. This chunk states rendering as a job, XML exports and
tax return files, the hand-over mechanisms, printing (templates, subjects, contracts, print profile, language, stored
files, audiences), barcode rendering, the timing, the catalog rows, CI and the lab check, and report definition drafts.
The statement and book engine, comparatives, drill-down and filing are in chunk 1. `ledger` owns account balances and
posting; `master_data` owns `print_profile`; `crm` owns the outbound gate.

## Entities and tables

No DDL file creates a table of `reporting`.

Defined by rule, without DDL:

- `render_job`: one request to render a file: kind, subject, key, state and outcome (R203); a row of a company; its key is not stated beyond the partial unique key (`company_id`, `render_key`) over final subjects in `pending` or `done` (R246).
- `print_template`: a company's copy of a print template (R221); a row of a company; key not stated.
- `print_template_version`: an immutable version of a `print_template` (R221); key not stated.
- `report_definition`, `report_comparative_value`, `statutory_report_filing`: stated in chunk 1 (ADR-0049.R11, ADR-0049.R14, ADR-0049.R19).

Reads: `print_profile`, `company`, `branch`, `partner_address`, `data_translation`, `barcode` (`master_data`, `docs/design/DS-20-master-data.sql`); `document`, `approval`, `partner`; `tax_return`; `report_comparative_value`; `production_order_period_cost`; `close_task`; `account`; the attachment row through `attachments.contract`.

## Commands and queries

"Not stated" means the sources fill no value for the cell. Authorization comes from `authorization-areas.csv`: area
`print_template` covers print templates and print data contracts and holds no document data; printing and `GetPrintData`
are on `general_access` at read, checked against the subject's own permission and scope. Report queries that total
over documents are in area `reports`, registered `is_owner_scoped` false (ADR-0054.R15; R209).

| Name | Actor and authorization | Input | Effect | Events | Error codes |
| --- | --- | --- | --- | --- | --- |
| `RenderPrint` | `general_access` at read with the subject's own check; effect class `other`; not `human_only` | subject (R226), template, language, format | writes a `render_job`, or returns the existing job of the same key for a final document (R246) | `PrintRenderRequested` | `print_template_missing`, `document_not_approved`, `permission_denied`, `record_not_found` |
| `RenderReport` | leaf `report_finance` (ADR-0049.R17.N1), level not stated; effect class `other`; not `human_only` | a statement or book: code, range, options, format | writes a `render_job` | `ReportRenderRequested` | not stated |
| `RenderTaxReturn` | leaf `report_tax` (ADR-0049.R17.N1), level not stated; effect class `other`; not `human_only` | form, period, declaring unit, supplement number, format | writes a `render_job` (R211) | `TaxReturnRenderRequested` | not stated |
| `RecordRenderOutcome` | internal command of `render_worker`; `is_internal_only` | the job and its outcome | records the outcome on the `render_job`; always succeeds | `RenderOutcomeRecorded` | none; outcome codes of R206 |
| `CreatePrintTemplate` | area `print_template`, level not stated; effect class `master_data_change` | not stated beyond the columns of R221 | adds a `print_template` | not stated | `print_template_invalid`, `print_contract_version_unsupported`, `print_template_audience_invalid` |
| `UpdatePrintTemplate` | area `print_template`, level not stated; effect class `master_data_change` | not stated beyond the columns of R221 | writes a new `print_template_version` with basis `company_decision` | not stated | `print_template_invalid`, `print_contract_version_unsupported`, `print_template_audience_invalid` |
| `GetPrintDataContract` (query) | area `print_template`, level not stated | subject, version | returns the contract schema | none | not stated |
| `GetPrintData` (query) | `general_access` with the subject's own check | subject, template | returns the instance a template would receive, filtered by R256 | none | `permission_denied`, `record_not_found` |

Commands, queries and jobs of other modules that the rules name: `CreatePrintProfile` and `UpdatePrintProfile`
(`master_data`, R237), `RunBalanceCarryForward` (job of `ledger`, R213), `CreateListExport` (ADR-0050.R54, R208),
`GetTaxReturn` and `GetDocumentTaxes` (ADR-0041), `SetArtifactVersionState` and `CreateArtifactEvidence` (ADR-0059; R273,
R274), `RecordEInvoiceOutcome` (ADR-0028.R7). `GetStatutoryReport` (R267), `CreateReportDefinition` and `UpdateReportDefinition` (R273) have their rows in chunk 1.

Not commands, declared by `reporting`: the consumer `render_worker` on queue `pdf` (R205); the hook
`print_relation_resolver` (R229); the core template filter `barcode` (R223); a daily job that removes the render-job
link of a non-final document's file (R253). The package interface `AmountInWords` is package code (R230).

Codes bound to no named command of this chunk: `outbound_content_out_of_scope` (the outbound gate of `crm`, R258);
`list_export_query_not_allowed` (`CreateListExport`, R208); check result `unit_name_too_long` (R236).

## Rules

### Rendering as a job

R201. Render is the verb for producing a file from a print template or a report definition, as a job. Its event form is `RenderRequested`, because the file does not exist yet when the command commits; Issue and `IssueRequested` are the precedent (ADR-0004.R22). Export stays the verb for a company's full data (ADR-0044.R17).
Source: ADR-0049.R20

R202. The render commands are `RenderPrint` (the subjects of R226), `RenderReport` (a statement or book: code, range, options, format) and `RenderTaxReturn` (R211). Each checks permissions, scope and the template or definition, writes a `render_job`, and emits `PrintRenderRequested`, `ReportRenderRequested` or `TaxReturnRenderRequested`. Their effect class is `other`; none is `human_only`.
Source: ADR-0049.R20

R203. A `render_job` holds: kind (`print`, `report`, `tax_return`), subject and parameters, template version, contract version, language, the subject's lifecycle and e-invoice state, marker, format, `render_key` (R245), `is_subject_final` (the subject is a document in a final state at request, R246), `state` (`pending`, `done`, `failed`), the attachment, `contains_untrusted` (R252), the error code, and the actor context of the request (ADR-0017.R16).
Source: ADR-0049.R20

R204. A report job also stores, from the worker's snapshot: the definition content hash, every computed line with its current and comparative value and check results, the SHA-256 of those lines in canonical JSON (ADR-0008.R12), the count of the company's journal entries with a posting date on or before `to`, and the hash of the `report_comparative_value` rows of its ranges. Filing reads these (ADR-0049.R19).
Source: ADR-0049.R20

R205. The consumer `render_worker` runs on queue `pdf` in the shape of ADR-0013.R10. It reads the data in one read-only snapshot transaction under the long-job timeout (ADR-0022.R9), renders with no transaction open, and records the outcome with the internal command `RecordRenderOutcome` (verb Record, which always succeeds, like `RecordEInvoiceOutcome`), which emits `RenderOutcomeRecorded`. Its lease is 30 minutes and it makes at most 3 attempts, instead of the defaults of ADR-0013 (5 minutes and 10); a held delivery follows ADR-0013.R8.
Source: ADR-0049.R20

R206. The failures recorded on the job are `render_failed` (a template or definition error at run time), `render_too_large` (above the installation setting `render_max_bytes`, default 100 MiB; the caller narrows the range) and `render_output_invalid` (XML that fails the package's schema).
Source: ADR-0049.R20

R207. Formats: PDF through a print template, which is the package's template for that report or the core's neutral report layout. XLSX, written with XlsxWriter (ADR-0002): one generic layout per kind (statement lines with labels, notes and values; book columns). XML only where the definition declares an export (R210).
Source: ADR-0049.R20

R208. Books leave only through `RenderReport`. `CreateListExport` (ADR-0050.R54) refuses every query of module `reporting` with `list_export_query_not_allowed`, because a list export has no opening, totals or closing rows, no full-scope check and no file a filing can name.
Source: ADR-0049.R20

R209. A print of a document, and its rendered file, follow that document's read owner scope. A report or book totals over documents and is `is_owner_scoped: false` (ADR-0054.R15).
Source: ADR-0049.R20, ADR-0049.R20.N1

### XML exports and tax return files

R210. A definition's `exports.xml` names a Jinja2 XML template (autoescaped for XML) and an XML schema file in the package. The output is validated against the schema with xmlschema (ADR-0002) before it is stored.
Source: ADR-0049.R21

R211. The return export of ADR-0041.R18 is `RenderTaxReturn` (form, period, declaring unit, supplement number, format). It renders the filed `tax_return` snapshot when one exists, otherwise a fresh `GetTaxReturn`, through the return form's export. A return form file gains the same optional header (`effective_from`, `exports`) at its next version; until then the package's undated return layout file counts as effective from the package's first date (ADR-0041.R19). The XML layout of a return for a tax authority's software is flagged package data of the localization package.
Source: ADR-0049.R21

### Hand-over mechanisms

R212. The operational accounts that a regime maps to GR/IR clearing and to `purchase_cost_clearing` take their statement format from DS-26 (ADR-0049.R6, ADR-0049.R7) and their placement from DS-19's definitions, which use account terms with `closing_debit` and `by=account` (under other receivables) and `closing_credit` (under other payables). The account numbers and the lines are flagged content of the localization package.
Source: ADR-0049.R22

R213. `RunBalanceCarryForward` is a generic job of `ledger`, run by a close task (ADR-0049.R23). It moves an account's balance at the previous fiscal year's last day to another account by a `balance_transfer` dated the first day of the new year, with the task's `close_task_id` on the journal entry. The accounts are task parameters in the regime's checklist; the TT99 checklist uses the job at the new year for its retained-earnings accounts, whose numbers are flagged content of the localization package.
Source: ADR-0049.R22

R214. `RunBalanceCarryForward` is idempotent. Each run transfers the year-end balance minus what earlier runs for the same fiscal year already moved, found by the `close_task_id` of their entries. A reversal of such an entry carries negated amounts (ADR-0014.R8) and is netted out of that sum, so a reversed transfer counts as not moved. A second run with nothing new posts nothing; after a special-period adjustment a run moves only the difference.
Source: ADR-0049.R22

R215. The timing of the carry-forward, and whether a regime wants a special-period adjustment carried this way, are flagged.
Source: ADR-0049.R22

R216. A statement presents advances by open-item kind with `kind=` and `by=partner_kind`, and short-term apart from long-term with `term=` (ADR-0049.R7).
Source: ADR-0049.R22

R217. Materials held for others (ADR-0037.R8) are a book over `stock` with `filters: {owner: non_owned}`, showing quantities and no values (ADR-0030.R8).
Source: ADR-0049.R22

R218. The product cost sheet (ADR-0035.R16) is `l10n_vn`'s book definition over `production_order_period_cost`, with `field_classes: [cost]`; the core provides the row source (ADR-0053.R13).
Source: ADR-0049.R22

R219. The stock valuation report is a book over `stock` as of a date, by item and warehouse. Its total ties to the inventory accounts (`INV-402`; spec 12).
Source: ADR-0049.R22

### Print templates

R220. Print templates are package templates (ADR-0016.R5, ADR-0016.R7) under `print_templates/<code>/` (package level) or `regimes/<regime>/print_templates/<code>/` (a regime's form, which wins over a package-level template of the same code). Each has `template.yaml` (subject, audience, contract version, languages, field classes, basis), `template.html` and optionally `style.css`. The core ships neutral English templates for subjects that no package covers (quotations, orders, labels, lists), so the basic US package needs none.
Source: ADR-0049.R24

R221. Setup copies the package templates into `print_template` (company, code, subject, `audience`, languages, `is_default` per subject and language) with immutable `print_template_version` rows (version, HTML, CSS, contract version, field classes, content hash, basis). `UpdatePrintTemplate` writes a new version with basis `company_decision`; `CreatePrintTemplate` adds a template. Both have effect class `master_data_change`, so an agent that builds a template from a customer's old form (spec 16) drafts a change proposal (ADR-0029.R1, ADR-0029.R5).
Source: ADR-0049.R24

R222. A template's `audience` is `external` (sent to partners) or `internal`. An external template may declare no field class (`print_template_audience_invalid`).
Source: ADR-0049.R24

R223. Templates run in Jinja2's sandboxed environment with autoescaping always on. `safe`, `Markup` and raw HTML output are unavailable to templates, so data is always escaped. The core provides formatting filters (amounts, quantities and dates in the print language and the company's time zone), `t()` for catalog strings, and the filter `barcode`. `barcode` renders a label's `barcode` object (`symbology`, `data`, `human_readable`) as SVG and is the only core filter whose output is markup (R277). `{% include %}` reaches only the company's own templates of subject `partial`.
Source: ADR-0049.R24, ADR-0049.R24.N1

R224. The renderer has no network. WeasyPrint's URL fetcher serves only `asset:` references to the company's print assets (print profile images, R238) whose attachment is in scan state `clean` (ADR-0038.R14), and package static files. Everything else is refused. The worker image ships fonts for every package language (DS-37).
Source: ADR-0049.R24

R225. `CreatePrintTemplate` and `UpdatePrintTemplate` compile the template and render its HTML (not the PDF) against the contract's example instance with strict undefined values. An unknown field, filter or tag is rejected with `print_template_invalid`. A contract version the core does not serve is rejected with `print_contract_version_unsupported`.
Source: ADR-0049.R24

### Print subjects and data contracts

R226. A print subject is a document type registered `is_printable` (a registry flag, ADR-0009.R2), or a registered query: the warehouse labels and lists of ADR-0023.R22 (`ListBin`, handling units, the pick and putaway task lists) and the label queries `ListItemLabel`, `ListLotLabel` and `ListSerialLabel`.
Source: ADR-0049.R25, ADR-0049.R25.N2

R227. The contract of a subject is a JSON Schema generated by `nativeflows-dev generate` into `backend/generated/print_contracts/<subject>.<major>.json` (ADR-0022.R17), with each field's field class, data label and `is_untrusted` annotation.
Source: ADR-0049.R25

R228. For a document, the contract is its version content (ADR-0009.R9) plus derived print fields. The first of them:
   - `company`: legal name and tax ID, with the print profile of the company and of the document's branch (R237);
   - `branch`: code, name, tax ID and address;
   - `document`: type, `number`, state, the `marker` (R248), dates, currency and references; a print of an `is_barcoded` document type also carries `document.barcode`;
   - `e_invoice`, for e-invoice-capable types: what `RecordEInvoiceOutcome` stores on the e-invoice record (ADR-0028.R7): state, number and issue date, or the rejection reason; and `extension`, an object whose schema the installed e-invoice add-on defines and generates into the contract (DS-24). The core contract names no country's e-invoice fields;
   - `partner`: the snapshot in the content (ADR-0028.R16) and the partner's code;
   - `lines`: content lines with their taxes and, optionally used, price steps (ADR-0047.R16). Each line's `uom_id` resolves to the unit's code and name in the print language (R234).
   Source: ADR-0049.R25, ADR-0049.R25.N1, ADR-0049.R25.N2

R229. Every `<relation>_id` in the content gains a sibling `<relation>` object with the referenced record's code and name, the name in the print language where a data translation exists (ADR-0018.R17). Documents resolve through `documents.contract` (type and number) and master data through `master_data.contract`. A record owned by another layer-4 module (for example a money account of `cash`) resolves through the hook `print_relation_resolver`, which `reporting` declares and the owning module registers, wired by `app` (the hooks of ADR-0022.R2), so `reporting` imports no layer-4 module. `nativeflows-dev generate` fails when a printable type's content has a relation that nothing resolves.
Source: ADR-0049.R25

R230. The other derived print fields of a document contract:
   - `taxes`: totals per tax code (base, rate or label, tax) from `GetDocumentTaxes` (ADR-0041.R6);
   - `installments`: the schedule in the content (ADR-0047.R6);
   - `totals`: net, discount, tax and gross in document currency, and in company currency with the rate when they differ;
   - `amount_in_words`: the gross amount in the print language, from the package interface `AmountInWords` (package code, ADR-0016.R5 and ADR-0016.R17; the core ships English). When no installed implementation covers the print language, it holds the amount in numerals only, formatted for that language, so a print never fails or shows words in another language;
   - `people`: the preparer (the actor of the version, ADR-0017.R16: a person's name, or the agent type and the person it acted for), the approver (from the `approval` row bound to the version, ADR-0009.R11), and the chief accountant and legal representative from the print profile. These come from document records, not from audit queries, which agents may not read (ADR-0038.R7);
   - `printed`: the instant of rendering in the company's time zone, and the language.
   Source: ADR-0049.R25

R231. For a query subject, the contract is the query's result schema plus `company`, `branch` and `printed`. Each row of a label subject carries `barcode` objects the core computes (symbology, ASCII data, human-readable text). The human-readable line may be in any print language; the encoded data is ASCII (R276).
Source: ADR-0049.R25, ADR-0049.R25.N2

R232. Contract versions are semver per subject. A new optional field is a minor version. Removing, renaming or retyping a field is a major version. A CI check compares the generated schemas with the last release and fails on a breaking change without a new major. The core serves the current major and the previous one until the next LTS release (DS-37). A template declares `contract_version` (`major.minor`); the core accepts it when it serves that major with at least that minor, so a core change does not break a company's template (spec 16).
Source: ADR-0049.R25

R233. `GetPrintDataContract` (subject, version) returns the schema. `GetPrintData` (subject, template) returns the instance a template would receive, filtered as R256 says.
Source: ADR-0049.R25

### Units on prints

R234. The print contract's `uom` object of a line (R228) gives the unit's `code` and `name` in the print language. The name comes from the company's `data_translation` for company units, and from the core catalog for core units (ADR-0016.R19), which the package terminology may override. A line prints its own unit and quantity, never re-expressed in the inventory unit.
Source: ADR-0056.R18, ADR-0049.R25.N1

R235. Statutory outputs (e-invoice lines through the e-invoice add-on, DS-24, and prints a regime marks statutory) take the package's statutory unit name when present, else the core translation (ADR-0056.R2).
Source: ADR-0056.R18

R236. The core registers the regime setting `documents.unit_name_max_length` (an integer, or empty for no limit); the package supplies its value. A company unit name or translation longer than the value returns the check result `unit_name_too_long` when it is saved, and a statutory output refuses a longer name instead of cutting it.
Source: ADR-0056.R18

### Print profile and signatures

R237. `print_profile` (module `master_data`, DS-20; change-tracked; `CreatePrintProfile` and `UpdatePrintProfile`, effect class `master_data_change`) has one row for the company and optionally one per branch; a branch row's non-empty fields win over the company's. Its columns: address (the keys of `partner_address`, ADR-0045.R8), phone, email, website, legal representative's name and title, chief accountant's name (both labeled `personal`, spec 17), bank details printed as text, and the attachment IDs of a logo, a seal image and a signature image. `company` already holds legal name, tax ID and language; `branch` holds name, tax ID and address.
Source: ADR-0049.R26

R238. Print profile images are PNG or JPEG attachments labeled `internal`. Only the `owner` role template holds `UpdatePrintProfile` (DS-15). The contract leaves the seal and signature images empty when the subject has a marker (R248), so a draft never carries them.
Source: ADR-0049.R26

R239. Prints show the printed names of the preparer and approver (R230), as accounting law asks for a preparer and an approver (spec 03 rule 6).
Source: ADR-0049.R26

R240. Digital signatures on PDFs come later (open question).
Source: ADR-0049.R26

R241. The print of an e-invoiced document is not the legal e-invoice, which the provider issues (DS-24). The print shows the e-invoice data of R228 once accepted.
Source: ADR-0049.R26

### Print language

R242. The print language is the render request's `language`, then the document's `print_language`, then the partner's `preferred_language`, then the company's `default_language` (ADR-0016.R19; ADR-0018.R17). `print_language` (BCP 47, optional) is a header field of every printable document type and part of its content (ADR-0047.R1, ADR-0048.R1).
Source: ADR-0049.R27

R243. The template for a subject is the one the request names, else the default template of that language, else the subject's default template; with none, the request fails with `print_template_missing`.
Source: ADR-0049.R27

R244. Printed strings come from the catalogs and the package terminology in the print language. Entered data is never translated (ADR-0016.R19).
Source: ADR-0049.R27

### PDF worker and stored files

R245. The render key is the SHA-256 of the canonical JSON (ADR-0008.R12) of: the subject (document version ID, or query and parameters, or report parameters), the subject's `state`, the template version, the contract version, the language, the marker and the format. The element `state` tracks the lifecycle: for a document it holds `document.state` and, when the document has an e-invoice record, that record's state; for other subjects it is empty. A reversal changes `document.state` without a new version (ADR-0009.R14), and an e-invoice outcome changes no version either, so `state` keeps a reversed or newly accepted document from reusing its old file.
Source: ADR-0049.R28

R246. For a document in a final state (`posted`, `reversed`, `canceled`, `closed`, ADR-0009.R14), `RenderPrint` returns the existing `pending` or `done` job with the same key and renders nothing. A partial unique key on `render_job` (`company_id`, `render_key`) over rows with `is_subject_final` and state `pending` or `done` enforces this: of concurrent requests, the later insert conflicts and returns the first's pending job. A `failed` job leaves the key free. So a final document is rendered once per state, template version, contract version, language and format, and the first file stays even when master data used by derived fields changes later.
Source: ADR-0049.R28

R247. The version printed is the document's current version (ADR-0009.R9). While a change order is pending (ADR-0028.R4), prints use the current approved version, the version in force, never the pending change.
Source: ADR-0049.R28, ADR-0049.R28.N1

R248. The renderer stamps every page, in the print language, with the marker: `REVERSED` when the document is reversed, `CANCELED` when it is canceled, and otherwise `DRAFT` when it has no number. Templates cannot remove it.
Source: ADR-0049.R28

R249. There is no copy marker and no print counter. Printing the same key again returns the same file. A form printed in several labelled copies is a template concern: the template renders the copies in one file.
Source: ADR-0049.R28

R250. The file is stored through `attachments.contract` with source kind `generated` and scan state `clean`. "Clean" is a statement about the malware scan only: the file is not scanned, because the worker produces the bytes from company templates in a sandbox without network access. It says nothing about the content.
Source: ADR-0049.R28

R251. The attachment row (layer 2) records, at creation and never changed: `generated_kind` (the job's kind), `generated_audience` (the template's audience; `internal` for report and tax return files), `generated_subject_document_id` (the printed document; empty for query and report subjects) and `contains_untrusted` (ADR-0027.R2, ADR-0038.R14).
Source: ADR-0049.R28

R252. The render job records whether the rendered instance held any non-null field annotated `is_untrusted`: a print contract field (R227), or a field of a report or book row, whose row source's result schema carries the same annotation (ADR-0049.R10). The attachment takes it as `contains_untrusted`, the same way it takes the strictest data label of the fields the instance contains (a partner snapshot of an individual is `personal`). As with the label, a second creation of the same bytes keeps the stricter value. A run that reads a file with `contains_untrusted` is tainted (ADR-0050.R25).
Source: ADR-0049.R28

R253. A file of a posted document (state `posted`, or `reversed` after it was posted) is linked to the document and is accounting evidence: linking a generated file to a posted document sets `is_accounting_evidence` (ADR-0038.R15). A file of an approved or closed non-posting document is linked to it and is not evidence. A file of a document that is neither posted nor in a final state is linked only to its render job; a daily job removes that link after 30 days, so the bytes go unless another record (such as an outbound message draft) links them (ADR-0027.R2).
Source: ADR-0049.R28

R254. An external print requires an approved document. `RenderPrint` of a document with a template of audience `external` is refused with `document_not_approved` while the document is in `draft` or `pending_approval`; from `approved` on (`issuing`, `posted`, `closed` and the other later states) it renders. A draft prints only with an internal template, which carries the `DRAFT` marker. Types that post without an approval step print externally once posted. The outbound gate checks the same at send (ADR-0052.R28).
Source: ADR-0049.R28.N1

### Escaping, audiences and sending

R255. Untrusted fields (ADR-0029.R10) are escaped like every field and never rendered as HTML, as ADR-0040.R17 asks of screens.
Source: ADR-0049.R29

R256. An external template's contract omits every field with a field class, so `cost` and `margin` cannot reach a customer-facing print (ADR-0029.R14). An internal template's contract keeps only the field classes it declares; the requester must hold them (`permission_denied`). Record scope applies at request (`record_not_found`). So a stored file never depends on who asked for it.
Source: ADR-0049.R29

R257. Printing is not sending. Emailing a PDF is an outbound message draft with the file attached, which a person sends after the consent check (ADR-0019.R9, ADR-0019.R17).
Source: ADR-0049.R29

R258. The outbound gate (module `crm`) accepts a generated file in a partner draft only when the attachment's `generated_kind` is `print`, its `generated_audience` is `external`, and the partner of its `generated_subject_document_id` (`document.partner_id`) is the message's partner; otherwise `outbound_content_out_of_scope`. `crm` reads these columns through `attachments.contract` and the partner through `documents.contract`, never from `reporting`, which is a layer-4 module like `crm` (ADR-0019.R17, ADR-0029.R14, ADR-0052.R28).
Source: ADR-0049.R29

### Timing

R259. The timing is interim until the author answers item 15 of the open question (DS-26, DS-27), because build order is his (ADR-0005). The engine is needed before step 8:
   - Step 5: the print contract, the worker and the templates for warehouse labels and lists (ADR-0023.R22), quotations, orders and delivery notes.
   - Step 6: the statement and book engine, drill-down and listings, with the cash book and bank book definitions the step 6 gate reads; voucher prints of cash and bank documents (ADR-0048).
   - Step 7: the return export (ADR-0041.R18).
   - Step 8: the regime's statements (their form codes are package content), comparatives, filing and the close checklist content.
   - Spec 11 and the runbook place DS-26 and DS-27 at step 8. Every place that applies the move is marked interim: the backlog's "Needed by" column, the text of ADR-0022.R2, and the notes on ADR-0023.R22 and ADR-0039.R10.
   Source: ADR-0049.R30

### Catalog rows

R260. The module's error codes are `report_definition_missing`, `report_definition_protected`, `report_definition_invalid`, `report_scope_incomplete`, `report_range_invalid`, `report_range_before_opening`, `report_not_fileable`, `print_template_missing`, `print_template_invalid`, `print_template_audience_invalid`, `print_contract_version_unsupported`, `report_render_job_mismatch`, `list_export_query_not_allowed`, and the precondition `document_not_approved` (R254), shared with ADR-0052.R28.
Source: ADR-0049.R31, ADR-0049.R31.N1

R261. The job outcome codes `render_failed`, `render_too_large` and `render_output_invalid` are an enumeration of the render job, not error codes of DS-04. The loader error `report_definition_in_use` is catalogued in DS-14 (Loader errors), not in DS-04.
Source: ADR-0049.R31, ADR-0049.R31.N2

R262. The check results are `report_check_failed`, `report_account_not_covered`, `report_comparative_missing`, `report_turnover_incomplete`, `report_periods_open` and `report_snapshot_stale`.
Source: ADR-0049.R31

R263. The module declares no work item kind. A held render delivery shows on the operations dashboard (ADR-0013.R8).
Source: ADR-0049.R31

R264. The invariant group INV-400 to INV-499 has area `reporting` (DS-16). `INV-400`, `INV-401`, `INV-402`, `INV-403` and `INV-404` are those of statutory reporting and printing; `INV-403` is flagged, because it tests package data. `INV-410` to `INV-414` of the block belong to agent-assisted analysis; `INV-413` and `INV-414` have area `safety` (ADR-0060.R35).
Source: ADR-0049.R31, ADR-0049.R31.N3

R265. The edge cases of statutory reporting and printing are `EC-92`, `EC-93`, `EC-94`, `EC-95`, `EC-96`, `EC-97` and `EC-98`. In `EC-97` filing a render made before a later posting succeeds with the check result `report_snapshot_stale`, and the difference view shows the posting. In `EC-98` a printed goods receipt is reversed, so a new print carries `REVERSED` and the first file stays.
Source: ADR-0049.R31

R266. The glossary gains: report definition, report line, measure, counterpart attribution, statutory report filing, report comparative value, print template, print data contract, print profile, render job, generated file (with `contains_untrusted`); the verbs Render and File. The intent of Record covers the render worker's outcome.
Source: ADR-0049.R31

### CI, golden figures and the lab check

R267. DS-16 has the golden kind `report_line` (keys `report`, `line`, `from`, `to`; company amounts), compared through `GetStatutoryReport`. The naive recomputation of step 8 adds report lines from the definitions in the regime snapshot.
Source: ADR-0049.R32

R268. Package CI (ADR-0016.R15) checks that every definition parses; that its selectors name accounts of the regime's chart template; that formulas and `report:` terms refer to existing lines and have no cycle; and that book fields exist in the row source. Every statement with `is_fileable` has at least one golden scenario with `report_line` rows for it, as "statutory reports matching their sample figures".
Source: ADR-0049.R32

R269. A package without statements, such as the basic US package (spec 06), has an empty per-statement requirement. CI still requires its core invariants and golden scenarios, and requires every book it ships to pass the definition checks.
Source: ADR-0049.R32

R270. The test package `l10n_xx` (ADR-0053.R9) ships one fictional statement with a check line and coverage, one book per row source in use at the current step, and one print template, so the core's property tests and `INV-400` to `INV-404` exercise the engine without the overlay.
Source: ADR-0049.R32

R271. The lab check `t09_reporting.py` of the validation lab tests pure functions and does not cover tables, templates, WeasyPrint or XML schemas. It covers:
   - the formula grammar: `pos`, `neg`, unary minus, cycles, the ASCII minus, `carry` over the header's comparative range and an empty `carry` without filing or stored value;
   - definition checks: `by` required on the split measures, `undated` with `term`, `term_months` when `term` is used, no `carry` with `comparative: none`;
   - measures: turnover by side with storno, migration entries out of turnover, closing entries excluded, special periods of the year ending on `to` excluded from turnover, change and closing but not from opening or earlier years;
   - the bilateral split by account, partner, and partner and kind, with kind and term filters and `undated`;
   - counterpart attribution on random entries: exact sums, every pair rounded down or up, mirrored reversals, cancellation between cash accounts, equality with a largest-remainder split when one side has one line;
   - the direct cash flow summing exactly to the change in cash;
   - comparatives from `opening_turnover` and `report_comparative_value`; `opening_turnover` only with `closing_entries=exclude`; counterpart terms incomplete across the cut-over;
   - one year earlier with month ends, across leap years, for both comparative kinds;
   - book row order with the document type and entry tiebreaks, and a cursor that neither repeats nor skips, also over `stock` rows ending on their natural key with null owner and lot sorting first;
   - idempotent balance carry-forward after a special-period adjustment and after a reversed transfer;
   - filing from a render job: a mismatched or unfinished job refused, a stale one filed with `report_snapshot_stale`;
   - render keys, which change with the document's state and e-invoice state, and the `REVERSED` marker.
   Source: ADR-0049.R33

### Report and analysis definitions as drafts

R272. Report and analysis definitions are declarative specs over the query layer (ADR-0050.R42 to ADR-0050.R48), the statutory engine (ADR-0049) and the analysis layer; never SQL and never a number an LLM computed.
Source: ADR-0059.R11

R273. `CreateReportDefinition` and `UpdateReportDefinition` write a draft version (effect class `other`, `is_draft_only`; ADR-0049.R11); activation is `SetArtifactVersionState` through a change proposal.
Source: ADR-0059.R11

R274. `CreateArtifactEvidence` renders the draft version on a fixed closed period and compares it with the cells the person checked by hand, given in the command as (line, column, period, value). At least one cell is required, and evidence is sufficient when every checked cell equals the engine's figure. The person who creates it attests the check.
Source: ADR-0059.R11

### Barcode symbologies and rendering

R275. Symbology and data per label:
   - Bin, document: Code 128; the internal code or the document number.
   - Handling unit: GS1-128 when its barcode is an SSCC, else Code 128; data (00) SSCC; for a single-item unit also (02), (37) and (10) in a second GS1-128 symbol, since one symbol holds at most 48 data characters.
   - Item unit: GS1 DataMatrix when the unit has a GTIN, else DataMatrix; data (01), or the internal code. A template may choose EAN-13 for a GTIN with leading zero for retail points of sale.
   - Lot: GS1 DataMatrix when the item unit has a GTIN and the lot code fits (10), else DataMatrix; data (01) (10), with (17) when the lot has an expiry date, or the lot's internal barcode.
   - Serial: GS1 DataMatrix when the item unit has a GTIN and the serial code fits (21), else DataMatrix; data (01) (21), or the serial's internal barcode.
   Source: ADR-0061.R21

R276. Encoded data is ASCII. GS1 strings are built and validated by `nativeflows.gs1` before rendering, with FNC1 in the first position, never parentheses, fixed-length elements first and one variable element last where the AIs allow it. The human-readable line may carry text in any language in the print language, with the fonts the worker ships (R224).
Source: ADR-0061.R21

R277. The worker draws barcodes as SVG with Zint, called by the core's template filter `barcode`. It runs Zint's command-line program inside the worker's sandbox (GS1 mode, SVG to standard output), so no Python binding is needed. `nativeflows.gs1` has already validated the data, and Zint's own GS1 check, whose AI table may lag the pinned Dictionary, is switched off. The options are verified at build. The markup is geometry the core generates from validated data, the human-readable text is escaped, and templates still cannot emit markup of their own.
Source: ADR-0061.R21, ADR-0049.R24.N1

R278. Licences: libzint is BSD-3-Clause and the Zint command-line program GPL-3.0 (GPL-3.0-or-later if the build check confirms it). Running it as a separate program is aggregation, and both are compatible with the core's AGPL-3.0 (spec 18; to verify at build). Whoever distributes the worker image ships Zint's licence texts with it and offers the corresponding source of the command-line program, as the GPL requires.
Source: ADR-0061.R21

R279. Templates state module size and quiet zones; the renderer refuses values below the symbology's minimum. For thermal printers a template may state the printer's resolution, and modules are then whole printer dots.
Source: ADR-0061.R21, ADR-0049.R24.N1

## Invariants

`INV-400`, `INV-401`, `INV-402`, `INV-403` and `INV-411` have their rows in chunk 1, with the rules their catalog source
names. The rows below are those of the rules of this chunk and those no rule of either chunk states. Sources are those
of `invariants.csv`.

| INV | Check point | Statement | Protects |
| --- | --- | --- | --- |
| `INV-404` | day | `final_subject_render_unique`: for subjects in a final state, no two render jobs in state `pending` or `done` share a render key, and every generated file linked to a posted document was rendered from its posted version. | R246, R253 |
| `INV-410` | run | `analysis_cell_equals_drill_rows`: every drillable analysis cell equals its drill rows by the table of ADR-0060.R16: the sum of their contributions for sums, counts, differences, totals, subtotals and contribution rows, the number of distinct keys for distinct counts, and the opening row plus the lines for balances, at the same snapshot. | ADR-0060.R16 |
| `INV-412` | run | `analysis_totals_from_rows`: every total, subtotal and other row of an analysis result equals the aggregation of its fact rows, never a sum of non-additive cells; no total row adds values of different currencies or inventory units; every contribution result's reconciliation row is zero. | ADR-0060.R12, ADR-0060.R18 |
| `INV-413` | day | `analysis_sentences_rendered_by_code`: every user-visible sentence of an analysis answer is rendered by code, from a key-fact template or from a claim template whose precondition held on the served cells; every stored narrative plan holds only claim codes, roles and handles. Area `safety`. | ADR-0060.R23 |
| `INV-414` | day | `analysis_verified_badge_by_hash`: every analysis answer recorded with badge verified has an `analysis_plan_hash` equal, after removing filters on open dimensions, to a saved analysis version or analysis example that was verified at its `recorded_at`. Area `safety`. | ADR-0060.R26 |

## Edge cases

`EC-92` to `EC-97` and `EC-170` have their rows in chunk 1, with the rules their catalog source names.

| EC | Name | Case | Outcome | Source |
| --- | --- | --- | --- | --- |
| `EC-98` | `printed_document_reversed` | A goods receipt is printed, then reversed; a new print gets a new render key and the `REVERSED` marker, and the first file stays linked as evidence. | `must_succeed` | R245, R248, R253 |
| `EC-150` | `analysis_owner_scoped_total` | A sales clerk with owner scope own builds an analysis of last month's net invoiced sales in the analysis builder; the result totals only their documents, carries the scope note and `analysis_scope_filtered`, and its drill lists only their invoices. | `must_succeed` | ADR-0060.R13 |
| `EC-151` | `analysis_two_currencies` | A question over sales invoices in more than one currency asks for document amounts without naming a currency; the plan is refused with `currency_mixed`, and the planner repairs it to company-currency amounts or the agent asks which currency (`ambiguous_term`); grouped by currency, the result has one subtotal per currency and no grand total. | `must_reject:currency_mixed` or `must_succeed` | ADR-0060.R10, ADR-0060.R24 |
| `EC-153` | `analysis_change_open_month` | Net revenue change by customer between a locked month and the open current month: the contribution rows reconcile to zero, the total change equals the journal's, and `analysis_periods_open` is returned. | `must_succeed` | ADR-0060.R18 |
| `EC-154` | `analysis_out_of_coverage` | A question about a figure no measure holds abstains with `out_of_coverage`, names the nearest measures and offers a catalog request; no number is shown. | `must_succeed` | ADR-0060.R24 |
| `EC-155` | `analysis_management_equals_journal` | At month end, net revenue by item group from the analysis layer at full scope equals the change measure of ADR-0049 with `closing_entries=exclude` over the operational accounts of the revenue system account subtree (`INV-411`). | `must_succeed` | ADR-0060.R4, ADR-0060.R35 |
| `EC-213` | `variance_negative_residual` | An order completed in a period without receipts; the explanation never calls the negative residual a saving. | `must_succeed` | ADR-0064.R20; ADR-0035.R10 |

## Settings

| Key | Value type | Scopes | Core default | Used by |
| --- | --- | --- | --- | --- |
| `documents.unit_name_max_length` | integer, bounds `1..255` | `regime` | `unset` (no limit); the package supplies the value | R236 |

R206 names the installation setting `render_max_bytes` (default 100 MiB); `settings.csv` holds no such key.

## UI annotations

None: the sources hold no ADR-0077 annotation for this module; it declares no work item kind (R263).

## Conflicts

CONFLICT ADR-0049.R24: the sandbox text says no template output is markup; the later note ADR-0049.R24.N1 (ADR-0061, 2026-11-15) adds the core filter `barcode`, whose SVG output is markup the core generates; R223 and R277 state the result.

## Proposed (not law)

None

## Trace

| Source | Where |
| --- | --- |
| ADR-0049.R20 | R201-R209 |
| ADR-0049.R20.N1 | R209 |
| ADR-0049.R21 | R210, R211 |
| ADR-0049.R22 | R212-R219 |
| ADR-0049.R24 | R220-R225 |
| ADR-0049.R24.N1 | R223, R277, R279 |
| ADR-0049.R25 | R226-R233 |
| ADR-0049.R25.N1 | R228, R234 |
| ADR-0049.R25.N2 | R226, R228, R231 |
| ADR-0049.R26 | R237-R241 |
| ADR-0049.R27 | R242-R244 |
| ADR-0049.R28 | R245-R253 |
| ADR-0049.R28.N1 | R247, R254 |
| ADR-0049.R29 | R255-R258 |
| ADR-0049.R30 | R259 |
| ADR-0049.R31 | R260-R266 |
| ADR-0049.R31.N1 | R260 |
| ADR-0049.R31.N2 | R261 |
| ADR-0049.R31.N3 | R264 |
| ADR-0049.R32 | R267-R270 |
| ADR-0049.R33 | R271 |
| ADR-0056.R18 | R234-R236 |
| ADR-0059.R11 | R272-R274 |
| ADR-0061.R21 | R275-R279 |
