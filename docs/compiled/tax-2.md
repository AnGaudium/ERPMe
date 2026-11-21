Module: tax    Chunk: 2 of 2    Source ADRs: ADR-0027, ADR-0028, ADR-0041, ADR-0051, ADR-0053, ADR-0057
Build step(s): 0, 3, 5, 7    Generated from index: 30d5706    Compiled by: Claude Fable 5.2, 2026-11-21

# Compiled spec: tax, chunk 2 (subledger, deductibility, returns, e-invoices)

## Purpose

`tax` owns tax codes, rates, the tax matrix, treatment rules, document taxes, the immutable tax subledger with its adjustments, filed tax return snapshots, and e-invoice records and intents. It is a layer-3 module (ADR-0022 rule 2): it may import the `ledger` contract, and `ledger` never imports it. This chunk holds R201 and up: the subledger, adjustments, deductibility, payment evidence, returns, the issue flow of e-invoiced documents and incoming e-invoice records. `tax-1.md` holds R1 to R199: configuration, determination and computation.

## Entities and tables

DDL: `docs/design/DS-05-platform.sql`.

| Table | Meaning | Key | Parent | Owner |
| --- | --- | --- | --- | --- |
| `tax_line` | The immutable tax subledger, written at posting | `id`; unique `company_id, id` | `document` | tax |
| `tax_line_adjustment` | An append-only later change of a tax line | `id`; unique `company_id, id` | `tax_line` | tax |

Defined by rule, without DDL: `e_invoice_record` and `e_invoice_record_line` (the DDL comes with DS-24 or the tax DDL draft), the e-invoice intent, and `tax_return` (R1, R251, R234).

Reads (not owned): `document_line_tax`, `tax_code`, `tax_rate` (`tax-1.md`); `document`, `posting_intent` (`documents`); `journal_entry`, `journal_line` (`ledger`); `customs_declaration` (`purchasing`); `branch`; `partner`; `mailbox`; `document_extraction`, `extraction_result_link`; `partner_overview`, `partner_item_overview`, `document_line_overview`; setting `crm.document_intake_xml_timeout_minutes`.

## Commands and queries

Where a cell says "not stated", the module's source units do not state it.

| Name | Actor and authorization | Input | Effect | Events | Errors |
| --- | --- | --- | --- | --- | --- |
| `Record<Type>EInvoiceOutcome` | `system` (the external consumer); verb `Record` | the e-invoice record, the outcome | writes `accepted` or `rejected` on the record; always succeeds (R245) | `EInvoiceAccepted`, `EInvoiceRejected` | none |
| `ImportEInvoiceRecord` | a person, or an intake as `system`; leaf `purchase_invoice` at `edit`; effect class `other`; on no agent tool list | an attached XML file | writes an incoming record and raises `supplier_invoice_received` (R256-R259) | not stated | `e_invoice_record_unreadable`, `duplicate_external_document`; check results `e_invoice_signature_unverified`, `e_invoice_key_conflict` |
| `ConfirmEInvoiceSupplier` | `human_only`; leaf `purchase_invoice` at `post`; effect class `other` | the record, the supplier | records the supplier and lifts the quarantine (R263) | not stated | `partner_role_missing`, `e_invoice_supplier_mismatch`, `permission_denied`, `e_invoice_superseded`, `duplicate_external_document` |
| `PostTaxAdjustment` | `system`; document type `tax_adjustment` (authorization area `tax_adjustment`) | an adjustment that moves tax between input tax and expense | posts through `input_tax_non_deductible` (R209) | not stated | not stated |
| `GetTaxReturn` (query) | not stated | form, period, declaring unit | computes the boxes, or returns the filed snapshot and the difference (R233, R235) | none | not stated |
| `FileTaxReturn` | not stated | form, period, declaring unit | stores an immutable `tax_return` snapshot (R234) | not stated | not stated |
| `RenderTaxReturn` | not stated (ADR-0049 rule 21) | a return | exports the return file (R237) | not stated | not stated |

Contract functions: `tax.contract.request_e_invoice` (R244), `tax.contract.record_tax_lines` (R201), `tax.contract.record_payment_evidence` (R226). Consumers: `tax_payment_evidence` of `OpenItemSettled` (R226), `e_invoice_intake` of `DocumentExtractionRecorded` (R271). Interface: `EInvoiceRecordReader` (R254). The document commands `Issue<Type>`, `Post<Type>`, `Complete<Type>Posting` and `Reopen<Type>` of R241 to R250 are commands of `documents`, with the verbs `Issue`, `Post`, `Complete` and `Reopen`.

## Rules

### Tax subledger

R201. Posting writes `tax_line` rows through `tax.contract.record_tax_lines`, in the posting transaction. The rows are immutable, owned by `tax`, and records in the plan (ADR-0031 rule 1). For sales and purchases they copy the posted version's `document_line_tax` rows (`INV-301`); for imports, the customs declaration's tax rows (ADR-0021).
Source: ADR-0041.R11, ADR-0041.R12, ADR-0041.D0

R202. Each row has the company, the declaring unit in `declaring_branch_id` (null for the company, or a branch with `is_declaring_unit`, ADR-0027 rule 5; ADR-0045 rule 8; the ADR names it `declaring_unit`), the document and line, `journal_entry_id`, the partner snapshot's tax ID in `partner_tax_id` (ADR-0028 rule 16), `tax_code_id`, `tax_rate_id`, direction, `input_use`, `rate_percent`, `base_transaction_amount` and `tax_transaction_amount` in document currency, `base_company_amount` and `tax_company_amount` in company currency, `tax_date`, `declaration_date` and `initial_deductibility`.
Source: ADR-0041.R11, ADR-0041.R6.N1

R203. `initial_deductibility` is `deductible`, `conditional` or `not_deductible`. Each purchase or import row also records `deductibility_rule_id`, the package rule row in force on its tax date (null when none applies), fixed at posting, so a later rule row never changes a posted line's condition.
Source: ADR-0041.R11.N1, ADR-0053.R3

R204. Zero-rated, not-subject and no-VAT codes write rows with zero tax, so return bases come from `tax_line` alone.
Source: ADR-0041.R11

R205. The journal gets one tax line per tax code, entry and tax line role, converted once by `convert_amount` (ADR-0011 rule 5) and carrying `tax_code_id`; base lines carry no tax code (ADR-0014.R9). Recoverable import VAT therefore has a payable line through `import_tax` and a recoverable line through `input_tax` (ADR-0021 rule 11).
Source: ADR-0041.R12, ADR-0041.R12.N1

R206. The company amounts of the tax rows are that journal line's company amount, spread over the rows by largest remainder over their exact converted values, so the subledger and the journal tie by construction. `INV-300`: per entry and code, the tax rows sum to the journal tax line in both currencies; that is the line posted through the code's `transaction_key` (for import VAT, the `import_tax` line), or through `input_tax_non_deductible` for rows with `input_use: non_taxable`; both carry `tax_code_id`. The invariants `INV-300` to `INV-399` are the group of area `tax` (DS-16).
Source: ADR-0041.R12, ADR-0041.R12.N1

### Adjustments

R207. Later changes are `tax_line_adjustment` rows, append-only: `adjusts_tax_line_id`, `kind`, `deductible_delta_transaction_amount` and `deductible_delta_company_amount` (the ADR names them `deductible_delta`, in document and company currency; positive raises deductible VAT), `declaration_date`, `reason`, and `journal_entry_id` when a journal entry posts. The DDL also has `reversal_of_id`, the adjustment a `reversal_of_adjustment` undoes, marked interim as not stated in ADR-0041.
Source: ADR-0041.R13, ADR-0041.D0

R208. The kinds are `condition_met`, `condition_failed`, `apportionment`, `period_move` and `reversal_of_adjustment`. `condition_failed` records the condition type's failure reason in `reason`; for `payment_evidence_threshold` the reasons are `failing_method` and `lapsed`.
Source: ADR-0041.R13.N1, ADR-0053.R3

R209. An adjustment that moves tax between input tax and expense posts a `tax_adjustment` document (`PostTaxAdjustment`, actor `system`) through `input_tax_non_deductible`. The posting carries the source line's dimensions (cost center, project, item) and posts on the adjustment's declaration date.
Source: ADR-0041.R13

R210. An adjustment whose declaration date falls in a period that does not admit it (locked, or soft-locked without the capability; ADR-0012 rule 5 note) takes the first day of the earliest later period that admits it as its declaration date, is declared in that period's return, and raises a `tax_adjustment_redated` work item for the accountant.
Source: ADR-0041.R13.N2

### Deductibility

R211. The deductibility of a purchase or import tax row is a projection: its `initial_deductibility` plus its append-only adjustments. The states are `deductible`, `conditional` (deductible now, but a condition can still fail) and `not_deductible`, driven by package-declared conditions of core types.
Source: ADR-0041.R14, ADR-0041.R14.N1, ADR-0053.R3

R212. At posting a row becomes: `deductible` when no condition applies or the condition is met, no posting; `conditional` when a condition applies and is not yet met, no posting; `not_deductible` when the condition fails, and the tax posts to expense; `not_deductible` for `input_use: non_taxable`, and the tax posts straight to expense; `deductible` until apportionment for `input_use: shared`, with an `apportionment` adjustment (R230).
Source: ADR-0053.R3

R213. After posting: a `deductible` row that a later event brings under the condition becomes `conditional`; a `conditional` row whose condition is met for the whole amount becomes `deductible`; neither posts. Where the condition fails for a share, that share becomes `not_deductible` by a `condition_failed` adjustment to expense. A `not_deductible` share that failed with reason `lapsed` becomes `deductible` by a `condition_met` adjustment when the condition is met later; a share that failed by `failing_method` stays `not_deductible`.
Source: ADR-0053.R3

R214. When the settlement behind a state change is reversed, the row returns to the state before it, with a `reversal_of_adjustment` when that change made an adjustment and nothing otherwise.
Source: ADR-0053.R3

R215. Moves between `deductible` and `conditional` change no deductible amount and need no adjustment row: the projection derives them from the condition's recorded inputs, the documents it aggregates and the settlements' evidence methods.
Source: ADR-0053.R3

R216. Conditions are package rules in `tax/deductibility_rules.yaml`. Each entry has `code`, `condition_type`, `applies_to` (`tax_kind` and `directions`), `parameters`, `effective_from` and a basis (ADR-0016 rule 6). Its identity is (`code`, `effective_from`), and a used row never changes value (ADR-0016 rule 13). The package kinds file and this file belong to the tax component of ADR-0016 rule 5.
Source: ADR-0053.R3

R217. Per (`tax_kind`, direction), across codes, the entry with the latest `effective_from` on or before the tax date of the invoice line is in force. An entry of the core condition type `none` (no parameters) ends the rule before it. Entries overlap only when they share (`tax_kind`, direction, `effective_from`); the loader rejects that with the loader error `deductibility_rule_overlap` (catalogued in DS-14, Loader errors; reported at deploy time like `regime_setting_in_use`), and `check_package.py` rejects it too.
Source: ADR-0053.R3, ADR-0053.R3.N1, ADR-0053.R3.N3

R218. Condition types are core: the core registers each type with its parameter schema and its evaluation. The first type is `payment_evidence_threshold`, with the parameters `threshold` (`amount`, `currency`, `includes_tax`); `aggregation` (a `default` of `per_seller_per_day` or `per_document`, with optional overrides `by_document_kind`); `failing_methods` (the `evidence_method` values that fail the condition; `none` never meets or fails it, every other recorded method meets it); `lapse` (`due_date`: the share still unpaid at the open item's due date fails with reason `lapsed`; or `none`); and `exempt_document_kinds` (document kinds the condition never applies to).
Source: ADR-0053.R3

R219. The tested amount is the document total, with its taxes when `includes_tax` is true and without them otherwise. `per_seller_per_day` sums the tested amounts of one seller's documents that share the supplier's invoice date; `per_document` tests each document alone. The condition applies when the tested amount is at or above `threshold.amount`.
Source: ADR-0053.R3

R220. The threshold is tested in the threshold's `currency`. A document total in another currency converts at the transaction lookup rate (ADR-0011 rule 11) on the tax date, and that applied rate is recorded on the tax line (`threshold_applied_rate_id`: named by ADR-0053.R3.N2, not in the DDL of `tax_line`).
Source: ADR-0053.R3.N2

R221. `l10n_vn` declares one rule of type `payment_evidence_threshold`, named `non_cash_payment_threshold`. Its values for `applies_to`, `threshold`, `aggregation`, `failing_methods`, `lapse` and `exempt_document_kinds`, its deductibility table, its legal sources and its return box are flagged package content of the localization package, `unverified`, under the open question on input VAT and non-cash payment; the core states none of them.
Source: ADR-0053.R3, ADR-0041.R14, ADR-0041.R14.N1

R222. Work item `tax_condition_pending`: a tax line's deductibility condition is not yet met; the system resolves it when the condition is met or fails. Work item `tax_deductibility_changed`: a tax line's deductibility fell by a `condition_failed` adjustment, for a person to review.
Source: ADR-0053.R4, ADR-0041.R14.N1

### Payment evidence

R223. Every settlement of an open item (ADR-0026 rule 6) records `evidence_method`: `cash`, `bank_transfer`, `card`, `offset`, `third_party` or `none` (write-offs, payment discounts, credit note matchings, balance transfers). It is recorded on the settlement, because offsets have no payment document, and stored on the journal line (ADR-0048 rule 18).
Source: ADR-0041.R15

R224. `journal_line.evidence_method` (DS-06, `INV-97`) keeps its name and values and records how a settlement was paid, in any regime; a condition's `failing_methods` decides what fails it. The consumer `tax_payment_evidence` and `tax.contract.record_payment_evidence` keep their names: they record evidence, which any condition may read.
Source: ADR-0053.R11, ADR-0041.R15.N1

R225. Payment evidence travels by event, so `ledger` never imports `tax` (ADR-0022 rule 2): `ledger` emits `OpenItemSettled` (item, amount, date, method, `reversal_of`) through the outbox.
Source: ADR-0041.R15

R226. The transactional `tax` consumer `tax_payment_evidence` calls `tax.contract.record_payment_evidence` and, when a share becomes non-deductible, posts the `tax_adjustment` through the `ledger` contract (ADR-0013 rule 9), which `tax` may import. The adjustment follows the payment; it is not in the payment's plan. Settlements of opening open items, which have no tax rows, are skipped (ADR-0044.R13).
Source: ADR-0041.R15

R227. Matching an invoice against an advance or a payment on account copies that item's own method, which its origin line records. Matching against a credit note reduces the amount the condition covers and counts as neither cash nor an offset.
Source: ADR-0041.R15, ADR-0053.R3

R228. Import VAT rows follow the customs declaration's link to its supplier invoice lines (ADR-0021) to find the open items whose settlements give evidence.
Source: ADR-0041.R15

R229. A daily job applies `condition_failed` with reason `lapsed` where the condition has a lapse.
Source: ADR-0041.R15, ADR-0041.R15.N1

### Apportionment and declaration date

R230. Rows with `input_use: shared` are apportioned at period end by the ratio of `tax.apportionment` (taxable revenue boxes over total revenue boxes), with an annual true-up at fiscal year end. A close task posts the result as `apportionment` adjustments.
Source: ADR-0041.R16

R231. The declaration date comes from `tax.declaration_date_basis`: for sales the invoice date; for purchases the invoice date (whether it should be the date a valid invoice is received is an open question); for imports the date of the tax payment voucher.
Source: ADR-0041.R17

R232. Input VAT may be declared in a later period by a `period_move` adjustment, within the limit the author verifies (open question).
Source: ADR-0041.R17

### Returns

R233. Returns are computed and filed per declaring unit and return period. `GetTaxReturn` (form, period, declaring unit) computes the boxes from `tax_line` and the adjustments whose declaration date is in the period, by the package-defined form.
Source: ADR-0041.R18, ADR-0041.D0

R234. `FileTaxReturn` stores an immutable `tax_return` snapshot: form, period, unit, `supplement_number` (0 for the original filing), the boxes, `filed_at`, `filed_by` and the submission reference. Later changes show as adjustments, never as a rewritten period.
Source: ADR-0041.R18, ADR-0041.D0

R235. For a filed period, `GetTaxReturn` returns the snapshot and the difference from a fresh computation, which is what a supplementary return declares.
Source: ADR-0041.R18

R236. Adjustments declared in a period for rows of an earlier filed period feed that period's prior-period boxes, not the current deduction. When a supplementary return changes an earlier period's carried-forward box, the change reaches the current period through its prior-period boxes, not by rewriting later periods (flagged).
Source: ADR-0041.R18

R237. Exporting a return file is `RenderTaxReturn` (ADR-0049 rule 21), step 7 work on these queries (DS-26).
Source: ADR-0041.R18, ADR-0041.R18.N1

R238. A return form is package data, `tax/returns/<form>.csv`: `box`, labels, `source`, basis. Sources are separated by `;` and summed: `base:<code>` and `tax:<code>`; `deductible:<code>`, the deductible tax of rows of the period after their adjustments; `prior_decrease` and `prior_increase`, the prior-period adjustments of R236; `formula:<expression>` over `[box]` references, with `+`, the ASCII `-`, `pos(…)` and `neg(…)`; `carry:<box>`, the box of the latest filing of the previous period.
Source: ADR-0041.R19, ADR-0041.R19.N1, ADR-0041.R18

R239. With no earlier filed return, `carry:` reads the migration's `opening_vat_carry_forward` (ADR-0044.R13).
Source: ADR-0041.R19

R240. Form codes are lowercased with non-alphanumerics as `_` (ADR-0004 rule 5). A form file gains an optional header (`effective_from`, `exports`) at its next version; until then the undated file is effective from the package's first date (ADR-0049 rules 5, 21).
Source: ADR-0041.R19, ADR-0041.R19.N1

### Issuing an e-invoiced document

R241. `Issue<Type>` (human or policy-allowed; verb `Issue`, event form `IssueRequested`; effect class `posting`) is where the dispatcher asks the policy, and the decision is stored. It runs the package validation of ADR-0028 rule 8 and the same period checks and period share lock as `Post` (ADR-0009 rule 13; ADR-0012 rule 9); freezes `posting_date`, which must equal the content's (ADR-0009 rule 9); resolves the rates (ADR-0011 rule 1) and computes the prospective journal and open items as its plan, with that `plan_hash`.
Source: ADR-0028.R7

R242. `Issue<Type>` stores the frozen plan, the rates and the hash on a `posting_intent` row (owned by `documents`; one per `Issue` attempt, never reused; state `pending`, `posted`, `reopened` or `recalled`; it also records that the e-invoice was required), requests the e-invoice and moves the document to `issuing`. No journal row, document number or open item is written yet; the result returns state `issuing` and the e-invoice record ID.
Source: ADR-0028.R7

R243. `Issue<Type>` from `approved` (an approval hold, ADR-0053 rule 8) asks the policy nothing new while the `policy_input_hash` and the actor kind equal those of the approved version's decision; it stores that decision, bound to the approved version, on the `posting_intent`. When either differs it evaluates again, as from `draft`, where `Issue` always evaluates. Floors 3–6 of ADR-0043 rule 9 still apply at `Issue`, and the plan and its hash are computed at `Issue`.
Source: ADR-0028.R7.N2

R244. A sales document requests issuance through `tax.contract.request_e_invoice`, synchronously; it writes the e-invoice record and its intent. The external consumer then issues it asynchronously, and the document posts on acceptance.
Source: ADR-0027.R8, ADR-0028.R7

R245. `Record<Type>EInvoiceOutcome` (verb `Record`; `system`, in `tax`) is run by the external consumer (ADR-0013 rule 10). It writes `accepted` (with the e-invoice number and issue date) or `rejected` (with the reason) on the e-invoice record, always succeeds, and emits `EInvoiceAccepted` or `EInvoiceRejected`.
Source: ADR-0028.R7

R246. On `EInvoiceAccepted` a transactional consumer runs `Post<Type>` as actor `system` on behalf of the event's `on_behalf_of_id` (ADR-0013 rule 9). It uses the stored `expected_plan_hash` and frozen rates, and writes the journal, the number, the open items and the e-invoice reference.
Source: ADR-0028.R7

R247. That completion `Post<Type>` is registered `is_consequence_posting` and carries the issuer's decision: the policy is not asked again, and floors 3 to 6 and the actor-kind policy point are applied at `Issue` and not repeated (ADR-0043 rules 5 and 9 notes), so an e-invoiced correction or an agent-drafted e-invoiced invoice posts without a held delivery. Under the human-only interim of ADR-0009 rule 12 this completion is allowed on behalf of the issuer (ADR-0027 rule 12).
Source: ADR-0028.R7, ADR-0028.R7.N1

R248. Where the e-invoice is required, `Post<Type>` is accepted only from this internal caller, in state `issuing`, with an `accepted` e-invoice record and the stored `expected_plan_hash`; anything else returns `invalid_state_transition`.
Source: ADR-0028.R7

R249. If that posting fails (a changed plan, a soft-locked or locked period, a changed account), the delivery is held with a work item (`e_invoice_posting_held`). A human completes it with `Complete<Type>Posting` (verb `Complete`; `human_only`, effect class `posting`, same preconditions; with `post_in_soft_locked_period` where needed), and corrects it afterwards with an adjustment document if needed. The consumer is idempotent: an already posted document counts as done, so the held delivery resolves.
Source: ADR-0028.R7

R250. On `EInvoiceRejected` a consumer runs `Reopen<Type>`, which returns the document to `draft` with the rejection reason and creates a work item for the issuer (`e_invoice_rejected`).
Source: ADR-0028.R7

### Incoming e-invoice records

R251. `e_invoice_record` holds incoming records beside the outgoing ones, with `direction` `incoming`, and their lines in `e_invoice_record_line`. The intake seam is named in the core; the e-invoice add-on (DS-24) fills it later, and until then a person imports an XML file through the package's reader.
Source: ADR-0051.R20, ADR-0051.R20.N1

R252. The agent reads from the record: `seller_tax_id` (normalized), `seller_name`, the fields of the package's supplier-invoice key (ADR-0030 rule 10), `invoice_date`, `currency`, `stated_rate`, `order_reference`, `net_amount`, `tax_amount`, `gross_amount`, `signature_state`, `authority_status` (`unchecked` until the add-on's status check records one), `supplier_partner_id`, `supplier_confirmed_by_user_id`, `imported_by_user_id`; and per line `line_number`, `seller_item_code`, `item_name`, `unit_text`, `quantity`, `unit_price`, `net_amount`, `tax_rate` and `stated_tax_amount`.
Source: ADR-0051.R20.N1

R253. Free text and codes from the seller (`seller_name`, `order_reference`, `seller_item_code`, `item_name`, `unit_text`, notes) are `is_untrusted`; the structured fields are not (ADR-0029 rule 10), except those of a `failed` or `signer_mismatch` record, and those of an `absent` one when the package's format declares the signature mandatory. The record is outside content, so an agent run on it starts tainted (ADR-0050 rule 15).
Source: ADR-0051.R20, ADR-0051.R20.N1, ADR-0051.R20.N2, ADR-0057.R25

R254. `EInvoiceRecordReader` is an interface the core publishes and the localization package implements (ADR-0016 rule 17), like `EInvoiceValidator` and `BankStatementReader`. It is network-free and deterministic: it parses one XML file into the record's fields and lines, checks its schema and its signature offline, and returns `signature_state`: `passed`, `failed`, `absent` or `signer_mismatch` (ADR-0057 rule 6). The add-on may register its own reader and an intake that uses the same import path. The agent never parses a raw attachment itself.
Source: ADR-0051.R20, ADR-0051.R20.N1, ADR-0051.R20.N2

R255. `signature_state` is `passed` only when the signature is valid, chains to an authority the package lists, was made while the certificate was valid, and the certificate's subject maps to the seller's tax ID. Revocation is the add-on's check.
Source: ADR-0051.R20.N2

R256. `ImportEInvoiceRecord` (module `tax`, effect class `other`, leaf `purchase_invoice` at its verb's level `edit`; run by a person, or by an intake as `system`; on no agent tool list) takes an attached XML file. It runs the reader (`e_invoice_record_unreadable`, with the package's code in `details`), normalizes the seller tax ID, and writes the record with `direction` `incoming` and `imported_by_user_id`. When the signature did not pass, its plan carries the check result `e_invoice_signature_unverified`.
Source: ADR-0051.R20.N1

R257. It refuses a second record that would hold the same supplier-invoice key (`duplicate_external_document`), except as R262 and R266 say. From the mailbox route that refusal is an outcome, not a held delivery: the extraction gets the check result `duplicate_key_found` and a link to the existing record, and the delivery completes.
Source: ADR-0051.R20.N1, ADR-0051.R20.N2, ADR-0057.R25

R258. `e_invoice_record.source_attachment_id` is unique among incoming records: a second import of the same attachment, by the route, a person, or several people importing the same listed extraction, returns the first record and creates nothing.
Source: ADR-0051.R20.N2, ADR-0057.R25

R259. In the same transaction `tax` raises `supplier_invoice_received` for the record (subject and open key the record; the catalog row's module is `tax`).
Source: ADR-0051.R20, ADR-0051.R20.N1

R260. The purchase invoice agent is triggered by `supplier_invoice_received`. Its scope is `partner`: the supplier whose normalized tax ID equals the record's verified seller tax ID, when exactly one active supplier has it (ADR-0050 rule 15), and only if the record's signature check passed; otherwise the confirmed supplier of R263. Without either, `StartAgentRun` fails with `agent_scope_unresolved` and the item stays with people.
Source: ADR-0051.R20, ADR-0051.R20.N1

R261. The agent's inputs are the record's header and lines, `partner_overview`, `partner_item_overview` (the supplier's `partner_item` and `supplier_item` rows), and the supplier's open purchase order lines from `document_line_overview` with ordered, received and invoiced quantities. Version 1.1.0 of the agent also declares `supplier_invoice_extracted` and accepts a verified supplier-invoice extraction as its subject, scoped to the supplier with the verified seller tax ID, with D1 the key check and D2 to D5 as ADR-0051 rule 21 (ADR-0057.R26).
Source: ADR-0051.R20, ADR-0051.R20.N2

R262. A record whose `signature_state` is not `passed` is imported quarantined (`is_quarantined`): it holds no supplier-invoice key, and the purchase invoice agent starts only after a person confirms its supplier with `ConfirmEInvoiceSupplier`, which lifts the quarantine. The key check runs then and refuses a second holder (`duplicate_external_document`).
Source: ADR-0051.R20.N2, ADR-0057.R25

R263. `ConfirmEInvoiceSupplier` (module `tax`, `human_only`, effect class `other`, leaf `purchase_invoice` at its verb's level `post`) records the supplier of a record whose signature did not pass: `supplier_partner_id`, `supplier_confirmed_by_user_id` and the time. The partner must hold the active `supplier` role (`partner_role_missing`) and have the record's seller tax ID (`e_invoice_supplier_mismatch`). For a file a person imported only its importer confirms (`permission_denied` for anyone else); for a mailbox record any holder may. A superseded record is refused (`e_invoice_superseded`).
Source: ADR-0051.R20, ADR-0051.R20.N1, ADR-0051.R20.N2, ADR-0057.R25

R264. Quarantined records of one sender in one mailbox on one business date share one `e_invoice_quarantine_review` item, the one human task for them; records that share a key are shown together in it.
Source: ADR-0051.R20.N2, ADR-0057.R25

R265. A later record with the same key and a `passed` signature supersedes a quarantined one: the quarantined record gets `superseded_by_record_id`, and `e_invoice_record_superseded` tells an accountant.
Source: ADR-0051.R20.N2, ADR-0057.R25

R266. When the key is held by a confirmed, formerly quarantined record, the record with a passed signature is still imported, with `key_conflict_with_record_id` naming the holder and the check result `e_invoice_key_conflict`. It raises `e_invoice_key_conflict` for an accountant, and no agent starts on either record until a person resolves the conflict. A genuine signed invoice is never refused silently (`INV-646`).
Source: ADR-0051.R20.N2, ADR-0057.R25

R267. `mailbox` gains `document_intake_purpose` (`supplier_invoice`, `inquiry_lines` or empty) and `document_intake_quarantine_limit` (default 20). `UpdateMailbox` (`human_only`, ADR-0052 rule 11) refuses a purpose when the mailbox owner does not hold `edit` on the purpose's leaf (`mailbox_owner_not_permitted`), so deliveries never fail for rights.
Source: ADR-0057.R25

R268. The `crm` consumer `mailbox_document_intake` of `InboundMessageRecorded` requests, as `system` on behalf of the mailbox owner and with `inbound_message_id`, an extraction for every XML part first. Other parts are requested only after every XML part of the message is recorded (by the same consumer reacting to their `DocumentExtractionRecorded`, or by its daily sweep once `crm.document_intake_xml_timeout_minutes`, default 60, have passed without a recording), and only when the message is matched to exactly one active partner (ADR-0052 rule 15), which needs its sender authentication to pass (ADR-0057 rule 14). From a message that is not matched, non-XML parts are stored only, and a person may request their extraction from the message.
Source: ADR-0057.R25

R269. The quarantine cap is decided after the read, when the signature state is known. It counts the quarantined records imported from messages not matched to a partner, per mailbox and business date (the message's receipt in the company's time zone); records of matched messages and records with a passed signature never count. Past the cap the XML's extraction is still recorded as `extracted` but its record is not imported: the extraction carries the check result `quarantine_limit_reached`, and one `e_invoice_quarantine_overflow` item per mailbox and business date tells the mailbox owner and lists those extractions. A person imports any of them from the item with `ImportEInvoiceRecord` (R272 then applies), or closes the item. Nothing is canceled for the cap, and there is no other daily limit on parts: documents of matched partners are read, bounded by the agent budgets of ADR-0050 rule 22 where a model is involved.
Source: ADR-0057.R25, ADR-0051.R20.N2

R270. The extraction's `partner_id` is the active supplier whose normalized tax ID equals a `passed` seller tax ID (exactly one), else the interaction's matched partner, else empty. It selects the mapping rules of ADR-0057 rule 5.
Source: ADR-0057.R25

R271. When the e-invoice reader gives a structurally valid record (schema and arithmetic), the `tax` consumer `e_invoice_intake` of `DocumentExtractionRecorded` runs `ImportEInvoiceRecord` as `system` on behalf of the human the request acted for (the mailbox owner for the mailbox route), whatever the signature, with `source_attachment_id`, `inbound_message_id`, `signature_state`, the clearance code state (`present`, `missing`, `not_required`), the arithmetic outcome, the stated issue time and the signing time. The extraction links the record (`extraction_result_link`), ends `extracted` and raises no review item of its own, so each XML gives at most one human task, the record's.
Source: ADR-0057.R25, ADR-0051.R20.N2

R272. For an XML a person uploaded and requested (`RequestDocumentExtraction`, purpose `supplier_invoice`), the same consumer imports it on behalf of that person, with `imported_by_user_id` set to them, so the importer confirmation of R263 applies. Quarantine, supersession and key conflicts work as for the mailbox, and the quarantine cap does not apply.
Source: ADR-0057.R25, ADR-0051.R20.N2

R273. A PDF of the same message is the XML's rendering only when the XML's invoice number appears as a whole token in the PDF's text layer; the file name stem only decides between several XML parts that match. It is then linked to the record as its rendering, as received and unverified, and its request ends `canceled` by the system with reason `rendering_of_parsed_xml`. Any other PDF is extracted as a document of its own.
Source: ADR-0057.R25

R274. The e-invoice provider connection (pulling records from a provider or the tax authority, the authority status and the revocation check) stays the DS-24 add-on; it uses the same import path.
Source: ADR-0057.R25

## Invariants

1. `INV-300` `tax_lines_tie_to_journal` (area `tax`, check point `day`): per journal entry and tax code, the `tax_line` rows sum to the journal tax line in document and company currency: the line posted through the code's transaction key (`import_tax` for import VAT), or through `input_tax_non_deductible` for rows with `input_use` `non_taxable`. Protects R206.
2. `INV-301` `tax_lines_equal_document_taxes` (area `tax`, `day`): the `tax_line` rows of a posted document equal the `document_line_tax` rows of its posted version in code, base, rate and tax. Protects R201.
3. `INV-646` `e_invoice_key_among_unquarantined` (area `tax`, `day`): incoming records that are not quarantined share a supplier-invoice key only when the later has a passed signature and names the earlier in `key_conflict_with_record_id`; a record with `superseded_by_record_id` is quarantined and names a record with a passed signature and the same key. Protects R262, R265, R266.
4. `INV-97` `evidence_on_listed_lines` (area `ledger`, `day`): every journal line with an open item that is not the item's origin line, has a non-zero transaction amount and is not the reversal of an origin line, and every origin line of an advance or payment-on-account item, has an `evidence_method`; no other line has one. Protects R223, R224.
5. `INV-81` `human_only_never_by_agent` (area `safety`, `day`): no audit row of a command registered `human_only` has actor kind agent, or integration while the interim holds. Concerns R263, R249 and the audit row of R2.

## Edge cases

1. `EC-31` `import_vat_on_customs`: import VAT on a customs declaration, recovered or capitalized per the tax code's import treatment. `must_succeed`.
2. `EC-53` `e_invoice_rejected`: an e-invoice rejected for a wrong buyer tax ID returns the invoice to draft; it is corrected and issued again; nothing is posted before acceptance. `must_succeed`.
3. `EC-59` `e_invoice_outage_across_period_end`: a provider outage keeps an invoice in `issuing` across month end; the period lock is blocked until it posts. `must_succeed`.
4. `EC-60` `backdated_issue_outside_window`: an invoice issued with a posting date outside the regime's window is rejected by package validation. `must_succeed`.
5. `EC-64` `duplicate_supplier_e_invoice`: the same supplier e-invoice arrives by e-mail and through the provider; the second arrival names the existing record. `must_reject:duplicate_external_document`.
6. `EC-66` `payment_condition_failed`: a purchase invoice at or above the active package's payment-evidence threshold is paid partly by a method the package's condition lists as failing; the failing share of its input tax becomes non-deductible by a `condition_failed` adjustment, and `tax_deductibility_changed` is raised. `must_succeed`.
7. `EC-185` `wake_up_by_rule`: the purchase invoice agent's `supplier_invoice_received` is set to `by_rule` with a rule on one supplier; an incoming record of that supplier starts the agent, one of another supplier stays with people. `must_succeed`.

## Settings

| Key | Type | Scope | Core default | Rule |
| --- | --- | --- | --- | --- |
| `tax.declaration_date_basis` | per `sale`, `purchase`, `import` | not stated | not stated | R231 |
| `tax.apportionment` | the return boxes of taxable and of total revenue | not stated | not stated | R230 |
| `tax.return_period` | `monthly` or `quarterly`, an option a company picks (ADR-0016 rule 11) | not stated | not stated | R233 |

These keys are registered by R55 and are absent from `settings.csv`. Read, not owned: `crm.document_intake_xml_timeout_minutes` (default 60; R268).

## UI annotations

The module's source units carry no floorplan, title, facet, field annotation or tile of ADR-0077. Work item kinds of `tax` (`work-item-kinds.csv`):

| Kind | Subject | Owner rule | Due rule | Resolution |
| --- | --- | --- | --- | --- |
| `supplier_invoice_received` | `e_invoice_record` | `role:accountant` | `days:2` | person |
| `e_invoice_quarantine_review` | `mailbox` | `role:accountant` | `days:2` | command `ConfirmEInvoiceSupplier` |
| `e_invoice_quarantine_overflow` | `mailbox` | `subject_owner:owner_user_id` | `days:1` | command `ImportEInvoiceRecord` |
| `e_invoice_record_superseded` | `e_invoice_record` | `role:accountant` | `days:2` | person |
| `e_invoice_key_conflict` | `e_invoice_record` | `role:accountant` | `days:1` | person |
| `e_invoice_posting_held` | `document` | `issuer` | `same_day` | command `Complete<Type>Posting` (R249) |
| `e_invoice_rejected` | `document` | `issuer` | `same_day` | command `Issue<Type>` (R250) |
| `e_invoice_date_outside_window` | `document` | `issuer` | `same_day` | command `Complete<Type>Posting` (ADR-0028 rule 8) |
| `e_invoice_outage` | `document` | `role:accountant` | `same_day` | system (ADR-0028 rule 10) |
| `tax_adjustment_redated` | `tax_line` | `role:accountant` | `days:5` | person |
| `tax_condition_pending` | `tax_line` | `role:accountant` | `days:5` | system |
| `tax_deductibility_changed` | `tax_line` | `role:accountant` | `days:5` | person |

## Conflicts

CONFLICT ADR-0041.R11: the DDL column is `declaring_branch_id` where rule 11 says `declaring_unit`; the DDL of `tax_line` in DS-05 decides the name (R202).
CONFLICT ADR-0041.R12.N1: one journal tax line per code, entry and tax line role replaces "per tax code and entry"; this note governs (R205).
CONFLICT ADR-0041.R13: the DDL splits `deductible_delta` into a transaction and a company amount column and adds `reversal_of_id`; the DDL of `tax_line_adjustment` in DS-05 decides the names (R207).
CONFLICT ADR-0041.R13.N1: the adjustment kinds `payment_evidence`, `cash_payment` and `due_date_lapse` of rule 13 are gone; ADR-0053.R3 governs (R208).
CONFLICT ADR-0041.R14.N1: the state `deductible_until_due`, the threshold setting and the Vietnamese table of rule 14 are not core law; ADR-0053.R3 governs (R211, R221).
CONFLICT ADR-0041.R15: its closing paragraph from ADR-0048 rule 18 adds the method `none` and the copy of an advance's or payment on account's own method; applied in R223 and R227.
CONFLICT ADR-0041.R15.N1: the daily job applies `condition_failed` with reason `lapsed`, not the kind `due_date_lapse`; ADR-0053.R3 governs (R229).
CONFLICT ADR-0041.R19: its inline sentence from ADR-0044 rule 13 adds the opening carry-forward for `carry:` without an earlier filing; applied in R239, nothing contradicted.
CONFLICT ADR-0051.R20.N1: its `signature_state` list lacks `signer_mismatch`, which ADR-0051.R20.N2 and ADR-0057.R25 use (ADR-0057 rule 6); the later text governs (R254).
CONFLICT ADR-0051.R20.N2: quarantine, key conflicts imported and not refused, and confirmation by any holder for a mailbox record govern over the first note's flat refusal and importer-only confirmation; this note and ADR-0057.R25 govern (R257, R263).
CONFLICT ADR-0053.R3.N1: an overlap is only a shared (`tax_kind`, direction, `effective_from`), narrower than rule 3's "at most one rule on any date"; this note governs (R217).
CONFLICT ADR-0053.R3.N2: the threshold is tested in its own currency; this note governs over rule 3's company-currency comparison and its `regime_configuration_missing` (R220).

## Proposed (not law)

None.

## Trace

| Source | Where |
| --- | --- |
| ADR-0014.R9 | ref: ADR-0014.R9 |
| ADR-0014.R9.N1 | ref: ADR-0014.R9.N1 |
| ADR-0028.R7 | R241-R242, R244-R250 |
| ADR-0028.R7.N1 | R247 |
| ADR-0028.R7.N2 | R243 |
| ADR-0041.D0 | R59, R67, R71, R201, R207, R233-R234, Purpose |
| ADR-0041.R11 | R201-R202, R204 |
| ADR-0041.R11.N1 | R203 |
| ADR-0041.R12 | R201, R205-R206 |
| ADR-0041.R12.N1 | R205-R206 |
| ADR-0041.R13 | R207, R209 |
| ADR-0041.R13.N1 | R208 |
| ADR-0041.R13.N2 | R210 |
| ADR-0041.R14 | R211, R221 |
| ADR-0041.R14.N1 | R211, R221-R222 |
| ADR-0041.R15 | R223, R225-R229 |
| ADR-0041.R15.N1 | R224, R229 |
| ADR-0041.R16 | R230 |
| ADR-0041.R17 | R231-R232 |
| ADR-0041.R18 | R233-R238 |
| ADR-0041.R18.N1 | R237 |
| ADR-0041.R19 | R238-R240 |
| ADR-0041.R19.N1 | R238, R240 |
| ADR-0044.R13 | ref: ADR-0044.R13 |
| ADR-0051.R20 | R251, R253-R254, R259-R261, R263 |
| ADR-0051.R20.N1 | R251-R254, R256-R257, R259-R260, R263 |
| ADR-0051.R20.N2 | R253-R255, R257-R258, R261-R266, R269, R271-R272 |
| ADR-0053.R3 | R56, R72-R73, R203, R208, R211-R219, R221, R227 |
| ADR-0053.R3.N1 | R217 |
| ADR-0053.R3.N2 | R220 |
| ADR-0053.R3.N3 | R217 |
| ADR-0053.R4 | R222 |
| ADR-0053.R11 | R224 |
| ADR-0057.R25 | R253, R257-R258, R262-R274 |
| ADR-0057.R26 | ref: ADR-0057.R26 |
