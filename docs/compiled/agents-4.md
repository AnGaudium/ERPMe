Module: agents    Chunk: 4 of 8    Source ADRs: ADR-0051
Build step(s): 2, 5, 5b, 7    Generated from index: 30d5706    Compiled by: Claude Opus 5.5, 2026-11-21

# Compiled spec: `agents`, chunk 4

## Purpose

`agents` owns the agent types, their declarations and settings, and the workflows each agent type runs (ADR-0022.R2).
This chunk states five workflows of ADR-0051: the quotation agent (Phase 2), the bank matching agent, the purchase invoice
agent, the planning agent and the data migration agent (Phase 2), each with its trigger, scope, inputs, steps, outputs, human gates,
shadow comparator and failures. The commands these workflows call belong to their own modules (`sales`, `cash`, `tax`,
`purchasing`, `planning`, `imports`); the shared rules of agent workflows (ADR-0051 rules 1 to 13) stand in chunk 3.

## Entities and tables

The rules of this chunk define no table that `agents` owns.

Defined by rule, without DDL: `e_invoice_record` and `e_invoice_record_line` (owned by `tax`, ADR-0027.R8; R634).

Reads: `interaction`, `inbound_message`, `partner`, `contact`, `partner_item`, `supplier_item`, `item`, `quotation`,
`bank_statement_line`, `bank_matching_rule`, `e_invoice_record`, `e_invoice_record_line`, `purchase_invoice`,
`currency`, `tax_rate`, `uom_alias`, `planning_exception`, `planned_order`, `supplier_item_lead_time`
(`docs/design/DS-43-54-planning-production.sql`), `import_batch`, `import_row`.

## Commands and queries

| Name | Actor and authorization | Input | Effect | Events | Error codes |
| --- | --- | --- | --- | --- | --- |
| `ImportEInvoiceRecord` | Module `tax`, effect class `other`, leaf `purchase_invoice` at its verb's level `edit`; a person, the add-on's intake job or the mailbox route as `system`; on no agent tool list | An attached XML file | Runs the reader, normalizes the seller tax ID, writes the incoming record and raises `supplier_invoice_received` (R636, R637) | not stated | `e_invoice_record_unreadable`, `duplicate_external_document`; check results `e_invoice_signature_unverified`, `e_invoice_key_conflict` |
| `ConfirmEInvoiceSupplier` | Module `tax`, `human_only`, effect class `other`, leaf `purchase_invoice` at its verb's level `post` | A record whose signature did not pass, and a partner | Records `supplier_partner_id`, `supplier_confirmed_by_user_id` and the time (R639) | not stated | `partner_role_missing`, `e_invoice_supplier_mismatch`, `permission_denied`, `e_invoice_superseded` |
| `RecordBankLineSuggestion` | Module `cash`, effect class `other`, `is_draft_only` | The tokens, name and purpose read by the run | Stores them on the statement line, all `is_untrusted` (R622) | `BankLineSuggestionRecorded` (IDs only) | not stated |
| `CreateBankMatchingRuleVersion` | A `cash` consumer, or a person holding `edit` on the leaf `bank_statement`; on no agent tool list | A token and a partner | Writes a `bank_matching_rule` version in `draft` (R624) | not stated | not stated |

Each agent type of this chunk is started under its own leaf of the area `agent`, capability `start_agent:<agent_type>` at
`edit` (`authorization-areas.csv`): `agent_quotation`, `agent_bank_matching`, `agent_purchase_invoice`, `agent_planning`,
`agent_data_migration`.

Not commands: the workflow steps of each agent type (L-steps call a model seat, D-steps are code), the pure function
`match_bank_line` (ADR-0051.R18) and the reader interface `EInvoiceRecordReader` (R635). The workflows call commands and
queries of other modules (`CreateQuotation`, `CreatePurchaseInvoice`, `UpdateImportBatch`, `ValidateImportBatch`,
`EvaluateConfiguration`, `EvaluateBarcode`, `GetCreditExposure`, `GetAvailableToPromise`), registered there.

Codes and check results the workflows of this chunk read or raise without a command of their own: `agent_scope_unresolved`
(R631), `price_missing`, `outbound_content_flagged` (R611, R613), `barcode_unknown`, `barcode_ambiguous`, `barcode_retired`
(R608), `match_quantity_exceeded`, `match_price_difference`, `invoice_before_receipt` (R643), `unit_text_unresolved`
(R641), `quarantine_limit_reached` (R638), `routing_blocked` (R619, R628).

## Rules

### Quotation agent (Phase 2 agent type, design kept)

R601. The quotation agent is a Phase 2 agent type: in Phase 1 it is registered with mode `off` and no workflow code, and its kind `inbound_message_matched` is raised and handled by people (ADR-0078.R2). It has two triggers. One is a work item `inbound_message_matched`, which `crm` raises for an inbound e-mail whose sender authentication passed and that is matched to exactly one partner, automatically or by `MatchInteraction` (ADR-0052.R15; ADR-0019.R15). The other is a person who starts the agent on an interaction, which gets an `agent_task` (ADR-0042.R11). `inbound_message` remains the name of the kind's table in `crm` (ADR-0052 rule 13).
Source: ADR-0051.R14, ADR-0051.R14.N2

R602. Scope `partner`: the interaction's matched partner (ADR-0050.R15), which must hold the active customer role; otherwise no run starts.
Source: ADR-0051.R14

R603. An inbound e-mail is outside content, so a run on it starts tainted (ADR-0050.R15), also when a person starts it, and works under ADR-0051.R10. A run a person starts on their own internal note (an interaction with `is_untrusted` false) is not tainted, so it may read the catalog and configure; if it later receives untrusted data, ADR-0051.R10 applies from then on, and nothing it read before may enter a prompt or the draft (ADR-0050.R25).
Source: ADR-0051.R14

R604. The designed configuring path: a salesperson records the customer's request as a `note` interaction in their own words (`CreateInteraction`, `is_untrusted` false), the person's own text for which they vouch, and starts the quotation agent on it; that run is untainted, so it reads the catalog, configures (L4) and writes the text (L5). A run woken by `inbound_message_matched` on a customer's e-mail stays tainted: it resolves only the partner's related items, leaves configurable lines unresolved with their hints, writes no text and hands over to a person, who may then record such a note. Whether a tainted run may configure stays the author's open question (DS-47, DS-32: the quotation hard floor and the readings of spec 03 rule 1); simulations show this path and say so.
Source: ADR-0051.R14.N1

R605. Inputs: `interaction_overview` (with `include_untrusted` for an e-mail), `partner_overview`, `contact_overview`, `partner_item_overview`, the partner's earlier lines from `document_line_overview`, `GetCreditExposure`; in untainted runs also `item_overview`, `configuration_model_overview`, `EvaluateConfiguration`, `GetConfigurationEstimate` and `GetAvailableToPromise`.
Source: ADR-0051.R14

R606. L1 `classify_message` (seat classification with personal data): output `QuotationClassifyOutput`: `intent` (`quotation_request`, `order`, `complaint`, `payment_question`, `delivery_question`, `other`), `language`. Anything but `quotation_request` ends the run `not_applicable` with a note. A run on an inbound e-mail always runs L1. L1 is skipped in a run that a person starts on their own note: the person classified the request by starting the run, so the run begins at L2 with intent `quotation_request`.
Source: ADR-0051.R15, ADR-0051.R15.N3

R607. L2 `extract_request` (seat classification with personal data): output `QuotationExtractOutput`: `lines` (description text, quantity as stated, unit text, requested date text, `characteristic_hints` as name and value texts, `source_span`), `customer_reference`, `requested_delivery_date`. Checks: spans; each quantity is a positive decimal that appears in its span; dates parse; at most 50 lines (more ends the run `not_applicable`, for a person).
Source: ADR-0051.R15

R608. D1 `resolve_items`, per line, in this order:
1. the partner's own code (`partner_item`) found as a whole token in the line;
2. an item code or barcode found as a whole token, among the candidates the run may read (ADR-0051.R10 in tainted runs; the catalog otherwise); a barcode resolves through `EvaluateBarcode` in `search` mode, keeping only `item_unit` candidates, and a typed issue (`barcode_unknown`, `barcode_ambiguous`, `barcode_retired`) leaves the line unresolved, never guessed;
3. `rank_candidates` over the same candidates (ADR-0051.R1).
An unknown supplier GTIN may only be drafted as a `CreateItemBarcode` proposal (ADR-0061 rules 13, 14).
Source: ADR-0051.R15, ADR-0051.R15.N4

R609. L3 `choose_item` (seat classification with personal data, since the line text is an extract of the e-mail), only for lines left open with candidates: input the line's text and unit and at most 5 candidates (handle, code, name, units). Output `QuotationChooseItemOutput`: `choice` (a handle or `none`), `reason_code` (`exact_name`, `synonym`, `attribute_match`, `no_match`). Checks: the handle was offered; the line's unit text maps to one of the item's units by the unit tables, else the line keeps the item's sales unit and a note. Lines with `none` stay unresolved.
Source: ADR-0051.R15

R610. L4 `configure` (seat drafting), for lines whose item belongs to a configurable product, in untainted runs only. The model may call one read tool, `evaluate_configuration`; its results come back through the dispatcher's query path and reach the model as labelled context items (ADR-0050.R8). Input: the hints and the product's characteristics and allowed values. Output `QuotationConfigureOutput`: values by characteristic code (value code or number). The workflow code calls `EvaluateConfiguration` with them; a violation, a missing characteristic or a value that the span check drops is fed back with the reason, at most 3 rounds, and each such round counts toward the 3. A dropped value is never replaced by a model or characteristic default. Checks: every number appears in a hint's span; the final evaluation `is_complete` with no violation, and no characteristic whose value was dropped got its value from a default in `EvaluateConfiguration`. Otherwise (after the last round such a characteristic is missing) the line is drafted with the values that passed, which a draft allows (ADR-0046), and a note lists what is missing. In tainted runs configurable lines are left unresolved with their hints in the note.
Source: ADR-0051.R15, ADR-0051.R15.N2

R611. D2 `draft_quotation`: `CreateQuotation` for the scope partner with the resolved lines: item or configuration values, unit and stated quantity. The agent passes no price, discount or tax: the pricing procedure prices the lines (ADR-0047.R16) and the tax engine computes taxes. Checks on the simulated plan: every item came from D1 or L3; the partner is the scope partner; no manual price or discount; `price_missing` and other check results go into the note. Step `quotation.draft`.
Source: ADR-0051.R15

R612. D3 `checks`: `GetCreditExposure` for the partner, and in untainted runs `GetAvailableToPromise` per stock line and `GetConfigurationEstimate` for new configurations. Findings go into the note; the credit finding is information for the salesperson. The agent evaluates no policy condition: the conditions at a quotation's `Submit` are discount, margin, below cost and outside the list (`discount_percent`, `margin_percent`, `is_price_below_cost`, `is_price_outside_list`), evaluated by policy (ADR-0043.R3). Quotations have no credit condition (ADR-0047 rule 22 note); credit is checked at the sales order's `Submit`.
Source: ADR-0051.R15, ADR-0051.R15.N1

R613. L5 `write_text` (seat drafting), in untainted runs only (ADR-0051.R10): input the customer's name, the draft's lines as priced in its plan, the validity date and the language. Output `QuotationTextOutput`: `cover_text`, `reply_subject`, `reply_body` (at most 4,000 characters). Checks: every number in the text equals a number of the draft (quantity, price, total, date); no other partner's name; no check result `outbound_content_flagged` in the plans of the quotation update and the reply draft (ADR-0050.R36). The cover text goes onto the quotation's note, and the reply becomes an outbound message draft (ADR-0019.R17) on the same work item, step `quotation.reply`.
Source: ADR-0051.R15

R614. This version of the quotation agent does not read attachments (ADR-0057.R28). A person may turn the rows of an inquiry spreadsheet's extraction into quotation lines through `GetQuotationLinesFromExtraction`.
Source: ADR-0051.R15.N5

R615. Outputs of the quotation agent: the quotation draft, the reply draft, a note listing unresolved lines and findings, and the links.
Source: ADR-0051.R16

R616. Human gates of the quotation agent: a salesperson reviews, completes the unresolved lines, and submits the quotation, a policy point with the discount, margin, below-cost and outside-the-list conditions of R612 and no credit condition (ADR-0043.R3). A person sends the reply; the gate checks consent and content (ADR-0019.R17). Policy thresholds are the company's rules on quotation submit; the agent sets none.
Source: ADR-0051.R16, ADR-0051.R15.N1

R617. At a quotation's approval, when its version is effectively tainted, the approval screen and the `approval_pending` work item offer `ClearTaint` on that version, with a required reason; an approver other than the person the tainted run acted for may clear it (ADR-0029.R8). Otherwise the taint passes to the order and every document derived from it (ADR-0047.R2). Whether an approval by another person should stop the inheritance by itself is an open question for the author.
Source: ADR-0051.R16.N1

R618. Shadow comparator of the quotation agent: per quotation, against the quotation a person created for the same interaction, line agreement on item or configuration hash, unit and quantity. A case is equal when every line the agent resolved is equal and it resolved at least half of the person's lines. Free text is scored by the eval judge on the golden set only.
Source: ADR-0051.R16

R619. Failures of the quotation agent: unresolved lines are a normal result. `routing_blocked`, invalid output and budgets follow ADR-0050.R17.
Source: ADR-0051.R16

### Bank matching agent

R620. The bank matching agent is triggered by a work item `bank_line_unmatched` (ADR-0048.R9), which the agent type declares. Runs act for the workflow owner (ADR-0050.R15). Scope `subject`: the statement line, which is outside content, so the run starts tainted (ADR-0050.R15). Input: `bank_statement_line_overview` for that line, with `include_untrusted`. D1: the cascade already ran at import and found nothing, which is why the item exists.
Source: ADR-0051.R17

R621. L1 `read_description` (seat classification with personal data, because descriptions are personal, ADR-0050.R9): output `BankMatchingReadOutput`: `reference_tokens` (at most 5), `payer_name_text`, `stable_payer_token`, `purpose` (`invoice_payment`, `advance`, `refund`, `salary`, `tax`, `bank_charge`, `internal_transfer`, `loan`, `unknown`). Checks: every reference token is a whole token of the description and reference-shaped as ADR-0051.R18 requires, or it is dropped; the payer name and the stable token are substrings of the description after folding, at least 3 characters long.
Source: ADR-0051.R17

R622. D2 `record_suggestion`: `RecordBankLineSuggestion` (module `cash`, effect class `other`, `is_draft_only`) stores the tokens, name, purpose and run on the line, all `is_untrusted`, and emits `BankLineSuggestionRecorded`, which carries IDs only (ADR-0013.R4). Step `bank_matching.suggest`. The run then ends `drafted` or `no_action`. It never matches, posts or reads partners.
Source: ADR-0051.R17

R623. A `bank_charge` purpose read by the model never qualifies a line for the `bank_charge` rule class, and an `llm_suggestion` draft never auto-posts, whatever the settings (ADR-0063.R8, ADR-0063.R9).
Source: ADR-0051.R17.N1

R624. Rule proposals: when a person posts a document matched to a line that carried a `stable_payer_token`, or matches such a line by hand, a `cash` consumer writes the rule as a `bank_matching_rule` version in `draft` (token to that partner) with `CreateBankMatchingRuleVersion`, if the token appears in at least two of that partner's lines in the last 90 days and in no other partner's lines; it drafts no change proposal. `CreateBankMatchingRule` creates the rule's identity in the same batch. The version copies an untrusted token, so it is written tainted, as a version derived from untrusted content (ADR-0029 rules 8, 10). A person holding `edit` on the leaf `bank_statement` may call `CreateBankMatchingRuleVersion` too; it is on no agent tool list.
Source: ADR-0051.R19, ADR-0051.R19.N1

R625. The rule version's drafting window ends at the value date of the second qualifying line. The version becomes `backtested` once at least the declared minimum of later lines carry the token and people matched each of them to the partner. The only proposal is `SetArtifactVersionState`: approved, the rule starts in `assisted` (suggest mode) and reaches `active` (confirm mode) on live evidence (ADR-0059.R10).
Source: ADR-0051.R19.N1

R626. Human gates of the bank matching agent: a person posts the drafted document or matches the line, which resolves the item; a person approves the rule version (ADR-0029.R5).
Source: ADR-0051.R19, ADR-0051.R19.N1

R627. Comparator of the bank matching agent: in Phase 1 it measures quality in use on stored output, the tokens the agent recorded in `assisted` mode (ADR-0078.R15); a shadow run (Phase 2) records its tokens but nothing persists, so no consumer runs. The comparator runs the pure `match_bank_line` on the line with the agent's tokens added at step 2, under the same guards as ADR-0051.R18, and compares its proposal with the person's final match: equal when partner and settled items are equal. A proposal of nothing counts as different when the person matched the line to an invoice.
Source: ADR-0051.R19

R628. Failures of the bank matching agent: no usable token gives a note and outcome `no_action`. With the routing switch on, descriptions are personal and L1 cannot be sent, so every run ends `routing_blocked` (ADR-0050.R9).
Source: ADR-0051.R19

### Purchase invoice agent: trigger, scope and intake

R629. The purchase invoice agent is triggered by a work item `supplier_invoice_received`, raised for a stored incoming e-invoice record (`e_invoice_record`). The incoming intake is the e-invoice add-on (DS-24). Until it exists, the record is created when a person imports an XML file through the package's reader, or by the core's mailbox route (R636), and the agent starts from that. The agent never parses a raw attachment itself.
Source: ADR-0051.R20, ADR-0051.R20.N2

R630. Version 1.1.0 of the purchase invoice agent also declares `supplier_invoice_extracted` and accepts a verified supplier-invoice extraction as its subject, scoped to the supplier with the verified seller tax ID, with D1 the key check and D2 to D5 as R641 to R645 (ADR-0057 rules 6, 25, 26).
Source: ADR-0051.R20.N2

R631. Scope `partner`: the supplier whose normalized tax ID equals the record's verified seller tax ID, when exactly one active supplier has it (ADR-0050.R15), and only if the record's signature check passed. Without a passed signature check, a run starts only after the record's supplier is confirmed with `ConfirmEInvoiceSupplier` (R639). Otherwise `StartAgentRun` fails with `agent_scope_unresolved` and the item stays with people (the supplier may need onboarding).
Source: ADR-0051.R20, ADR-0051.R20.N1, ADR-0051.R20.N2

R632. Taint: the record's structured fields (seller tax ID, the fields of the package's supplier-invoice key, ADR-0030.R10, dates, amounts, rates) are not untrusted; its free text (item names, notes) is (ADR-0029.R10). The structured fields of a `failed` or `signer_mismatch` record count as untrusted; those of an `absent` one do not, unless the package's format declares the signature mandatory. The record is outside content, so the run starts tainted (ADR-0050.R15).
Source: ADR-0051.R20, ADR-0051.R20.N2

R633. Inputs: the record's header and lines, `partner_overview`, `partner_item_overview` (the supplier's `partner_item` and `supplier_item` rows), the supplier's open purchase order lines from `document_line_overview` with ordered, received and invoiced quantities.
Source: ADR-0051.R20

R634. The intake seam of DS-24 is named in the core; the e-invoice add-on fills it later. `e_invoice_record` (owned by `tax`, ADR-0027.R8) holds incoming records beside the outgoing ones, with `direction` `incoming`, and their lines in `e_invoice_record_line`. The agent reads: `seller_tax_id` (normalized), `seller_name`, the fields of the package's supplier-invoice key (ADR-0030.R10), `invoice_date`, `currency`, `stated_rate`, `order_reference`, `net_amount`, `tax_amount`, `gross_amount`, `signature_state`, `authority_status` (`unchecked` until the add-on's status check records one), `supplier_partner_id`, `supplier_confirmed_by_user_id`, `imported_by_user_id`; and per line `line_number`, `seller_item_code`, `item_name`, `unit_text`, `quantity`, `unit_price`, `net_amount`, `tax_rate` and `stated_tax_amount`. Free text and codes from the seller (`seller_name`, `order_reference`, `seller_item_code`, `item_name`, `unit_text`, notes) are `is_untrusted`. The DDL comes with DS-24 or the tax DDL draft.
Source: ADR-0051.R20.N1

R635. `EInvoiceRecordReader` is an interface the core publishes and the localization package implements (ADR-0016.R17), like `EInvoiceValidator` and `BankStatementReader`: network-free and deterministic, it parses one XML file into the record's fields and lines, checks its schema and its signature offline, and returns `signature_state` (`passed`, `failed`, `absent`, `signer_mismatch`). `signature_state` is `passed` only when the signature is valid, chains to an authority the package lists, was made while the certificate was valid, and the certificate's subject maps to the seller's tax ID; revocation is the add-on's check. The add-on may register its own reader and an intake that uses the same import path.
Source: ADR-0051.R20.N1, ADR-0051.R20.N2

R636. `ImportEInvoiceRecord` (module `tax`, effect class `other`, leaf `purchase_invoice` at its verb's level `edit`; run by a person, or as `system` by the add-on's intake job or the core's mailbox route; on no agent tool list) takes an attached XML file. It runs the reader (`e_invoice_record_unreadable` with the package's code in `details`), normalizes the seller tax ID, and writes the record with `direction` `incoming` and `imported_by_user_id`. When the signature did not pass, its plan carries the check result `e_invoice_signature_unverified`. The mailbox route imports XML e-invoices that arrive in a mailbox with purpose `supplier_invoice` as `system` on behalf of the mailbox owner, with `source_attachment_id`, `inbound_message_id`, the clearance code state and the stated issue and signing times. An XML a person uploaded is imported on that person's behalf, as its importer. `source_attachment_id` is unique among incoming records, so a second import of the same file returns the first record.
Source: ADR-0051.R20.N1, ADR-0051.R20.N2

R637. In the same transaction `tax` raises `supplier_invoice_received` for the record (subject and open key the record; the catalog row's module is `tax`). `ImportEInvoiceRecord` refuses a second record with the same supplier-invoice key (`duplicate_external_document`), except as R638 says; from the mailbox route `duplicate_external_document` is an outcome, not a held delivery.
Source: ADR-0051.R20.N1, ADR-0051.R20.N2

R638. A record without a passed signature is imported quarantined (`is_quarantined`): it holds no supplier-invoice key, and the agent waits for `ConfirmEInvoiceSupplier`. Quarantined records of one sender and day share one `e_invoice_quarantine_review` item. Past a mailbox's cap for messages not matched to a partner, an XML is extracted but not imported (`quarantine_limit_reached`, `e_invoice_quarantine_overflow`). A later record with a passed signature and the same key supersedes a quarantined one (`superseded_by_record_id`, `e_invoice_record_superseded`). When a confirmed, formerly quarantined record holds the key, the later record is imported with `key_conflict_with_record_id` and `e_invoice_key_conflict`, never refused (ADR-0057.R25).
Source: ADR-0051.R20.N2

R639. `ConfirmEInvoiceSupplier` (module `tax`, `human_only`, effect class `other`, leaf `purchase_invoice` at its verb's level `post`) records the supplier of a record whose signature did not pass: `supplier_partner_id`, `supplier_confirmed_by_user_id` and the time. The partner must hold the active `supplier` role (`partner_role_missing`) and have the record's seller tax ID (`e_invoice_supplier_mismatch`). For a file a person imported only its importer confirms (`permission_denied` for anyone else); for a mailbox record any holder may confirm. It refuses a superseded record (`e_invoice_superseded`).
Source: ADR-0051.R20.N1, ADR-0051.R20.N2

### Purchase invoice agent: steps, gates and the rest

R640. D1 `check_record`: the status check of the reader (DS-24); the signature check, or the person's supplier confirmation, was already required to start (R631). The duplicate key (ADR-0030.R10; ADR-0047.R12): the draft's simulation returns `duplicate_external_document`, and the run ends `not_applicable` naming the existing document, which is in scope.
Source: ADR-0051.R21

R641. D2 `map_lines`, per line: the supplier's item code against `partner_item`; else the supplier's `supplier_item` code; else `rank_candidates` over the supplier's related items (ADR-0051.R10). A line's unit text maps through the partner item's text, `uom_alias`, then a unit code; otherwise the line stays unresolved with `unit_text_unresolved` and D5 also proposes an alias (`CreateUomAlias`).
Source: ADR-0051.R21, ADR-0051.R21.N1

R642. L1 `choose_item` (seat classification; the personal seat when the supplier is an individual or a sole proprietorship, ADR-0050.R9), for unmapped lines: input the line's name and unit and at most 10 candidates from the supplier's related items. Output `PurchaseInvoiceChooseItemOutput`: `choice` (handle or `none`), `reason_code`. Checks: the handle was offered; the line's unit converts to one of the item's units; otherwise `none`.
Source: ADR-0051.R21

R643. D3 `select_order_line`, per mapped goods line: the purchase order named in the record's order reference, if any, and its line for the item; else the only open line for the item; else the oldest open line whose received but uninvoiced quantity covers the line; else unresolved. Pure, on canonical order (date, then ID). D3 compares inventory quantities and prices per inventory unit, whatever unit the e-invoice line is in (ADR-0056 rule 19).
Source: ADR-0051.R21, ADR-0051.R21.N1

R644. D4 `draft_invoice`: `CreatePurchaseInvoice` with the header from the record (supplier, `partner_reference`, `supplier_invoice_date`, currency, rate as stated) and the resolved lines: `goods` lines with their order line, quantity, unit price and the supplier's stated tax copied from the record (ADR-0041.R10). Unresolved lines are not drafted. Checks on the simulated plan: lines and order lines come from D2, L1 and D3; header totals equal the record's when nothing was left out, else the note gives the difference; the three-way match results (`match_quantity_exceeded`, `match_price_difference`, `invoice_before_receipt`) go into the note. Step `purchase_invoice.draft`.
Source: ADR-0051.R21

R645. D5 `propose_mappings`: one change proposal with a `CreatePartnerItem` item for each line L1 resolved, and a `CreateUomAlias` item for each unit text R641 left unresolved, with the record as evidence. Step `purchase_invoice.mapping`.
Source: ADR-0051.R21, ADR-0051.R21.N1

R646. Outputs of the purchase invoice agent: the draft invoice, the mapping proposal, a note with unresolved lines, differences and check results.
Source: ADR-0051.R22

R647. Human gates of the purchase invoice agent: an accountant completes, submits and posts the invoice. The three-way match condition `is_match_exceeded` requires approval (ADR-0047.R14). A tainted draft needs a person to post (ADR-0043.R9), unless the company enables the auto-post gateway for purchase invoices with tainted drafts and this agent type is `active`; then a draft that passes the checker of ADR-0065.R19 posts as `system`, and the rule's owner confirms it. The next version of this agent type declares `auto_post_document_types` with `purchase_invoice` (ADR-0065 rules 10, 11, 19). The run creates the mapping proposal as a draft; a person submits it (ADR-0029.R3), and a person other than the workflow owner approves it, after which the next invoice maps deterministically.
Source: ADR-0051.R22, ADR-0051.R22.N1

R648. Policy thresholds of the purchase invoice agent: the company's purchase invoice rules (amount, `is_match_exceeded`, direct expense).
Source: ADR-0051.R22

R649. Comparator of the purchase invoice agent, used in Phase 1 on stored output (ADR-0078.R15): the agent's draft against the purchase invoice posted with the same supplier invoice key, per line, item, order line, quantity and unit; equal when all drafted lines are equal and the header matches.
Source: ADR-0051.R22

R650. Failures of the purchase invoice agent: no supplier, or more than one, gives no run. An unreadable record gives `not_applicable`. Unresolved lines are normal.
Source: ADR-0051.R22

R651. The work items `supplier_invoice_received` and `supplier_invoice_extracted` are closed by the owning module when the invoice draft linked to them is posted or canceled, through `work.contract.resolve_work_item` (ADR-0042.R6), and a person resolves one by hand when no draft was made. Both kinds keep resolution `person` in the catalog, because ADR-0042.R12 leaves `ResolveWorkItem` to kinds a person resolves and a `system` kind could not also be resolved by hand. The module's call is written with the purchase invoice at step 7.
Source: ADR-0051.R22.N2

### Planning agent

R652. The planning agent is triggered by work items `planning_exception` and `capacity_overload` (ADR-0042.R18), which the agent type declares, and by runs a planner starts on an item and warehouse.
Source: ADR-0051.R23

R653. Scope of the planning agent: the data is internal; the agent type declares `may_read_untrusted: false`, so its runs never become tainted (ADR-0050.R28) and read within the permission intersection.
Source: ADR-0051.R23

R654. Inputs of the planning agent: the exception, `ListPegging`, `GetProjectedAvailability`, `planned_order_overview`, `demand_supply_overview`, `stock_overview`, `GetAvailableToPromise` for other warehouses, `partner_item_overview` for supplier terms, `ListCapacityLoad`, `GetCapacityLevelingProposal`, `forecast_accuracy`.
Source: ADR-0051.R23

R655. D1 `gather`: pegging, projection and the planned orders involved.
Source: ADR-0051.R24

R656. D2 `candidate_actions`, computed by code from the exception code, each with its effect on the projection:
- a shortage inside lead time: firm and convert the proposed planned order now; or a stock transfer from a warehouse whose available to promise covers it;
- supplier minimums or container fill: the consolidation of planned orders inside the conversion window that meets the minimum (ADR-0024.R23);
- capacity overload: the leveling proposal's new dates (ADR-0036.R12);
- a missing parameter, or a planned lead time that differs from the stored mean of `supplier_item_lead_time` (ADR-0024.R2) by more than 20%: a parameter change, with the stored mean and standard deviation as evidence. No median is computed.
Source: ADR-0051.R24, ADR-0051.R24.N1

R657. L1 `explain` (seat analysis): input the exception facts, pegging rows, projection buckets and the candidates with their computed effects. Output `PlanningExplainOutput`: `explanation` (at most 1,200 characters), `recommended` (a candidate handle or `none`), `reason_codes`. Checks: the handle was offered; every number in the text appears in the input.
Source: ADR-0051.R24

R658. D3 `propose`: one change proposal with the recommended candidate's commands (`UpdatePlannedOrder`, `FirmPlannedOrder`, `ConvertPlannedOrder`, which are proposal-bound, ADR-0036.R12; or a parameter update, ADR-0024.R23; the lead-time update is `UpdateSupplierItem` on the measured supplier item, with the stored mean and standard deviation as evidence), with pegging and projection as evidence and the explanation as the reason. With `none`, only the note. Step `planning.propose`.
Source: ADR-0051.R24, ADR-0051.R24.N2

R659. Outputs of the planning agent: the proposal and a note with the explanation.
Source: ADR-0051.R25

R660. Human gates of the planning agent: the run creates the proposal as a draft, and a planner submits it (ADR-0029.R3). The approver is an eligible person of the current stage of the proposal's pool (`general` by default) who holds `ApproveChangeProposal` and the target permissions (ADR-0055.R7; ADR-0043.R12), that is `edit` on `planned_order` for the planned-order commands. Under the seed these are the production planner, the purchasing manager and the owner (ADR-0055 rule 5 note); accountants and chief accountants read planning only. The human the run acted for stays excluded. The executing consumer converts, and the drafts it creates follow their own approval (ADR-0024.R22). Sending to a supplier stays a separate approved step.
Source: ADR-0051.R25, ADR-0051.R25.N1

R661. Policy thresholds of the planning agent: proposals always need approval (ADR-0043.R9, floor 7); automatic conversion stays an open question (ADR-0043.R17).
Source: ADR-0051.R25

R662. Shadow comparator of the planning agent: the recommended action against what the planner did on the same exception before it closed, equal when the action type, the planned order and the quantity and dates are equal. In Phase 1 it is used on stored output (no shadow run). The agent type is promoted by its evaluation set at the golden-set threshold of 90% in the table of ADR-0051.R7 (the size of the set is fixed with the declaration); its quality in use is that comparator against what the planner did (ADR-0078 rules 1, 6, 15).
Source: ADR-0051.R25, ADR-0051.R25.N2

R663. Failures of the planning agent: no candidate gives the explanation only, outcome `no_action`.
Source: ADR-0051.R25

R664. The planning agent is a Phase 1 agent type. It starts after the step 5b gate, the manual path of `planning` with multi-level MRP (runbook steps 5 to 9, spec 11; ADR-0078.R1; ADR-0024 rule 26, ADR-0032 rule 7).
Source: ADR-0051.R25.N2, ADR-0051.R25.N3

### Data migration agent (Phase 2 agent type, design kept)

R665. The data migration agent is a Phase 2 agent type, registered with mode `off` and no workflow code in Phase 1; at step 11 migration uses the staged import, and the assistant's `act` help is bounded as ADR-0078.R2 states (ADR-0044.R15). The agent is started by a person on a draft import batch of a migration in `draft` or `loading` (`agent_task`; `start_agent:data_migration`).
Source: ADR-0051.R26

R666. Scope `import_batch` (spec 03 rule 1). The batch is outside content, so the run starts tainted (ADR-0050.R15; ADR-0044.R15).
Source: ADR-0051.R26

R667. Inputs of the data migration agent: `import_row_overview` of the batch with raw values, the import template's schema for the batch's phase (registry metadata), the migration's mapping profile (outside the batch: a reading flagged with ADR-0050.R27), and reference data (ADR-0050.R27): the package chart template, units, currencies, administrative units, tax ID rules.
Source: ADR-0051.R26

R668. D1 `map_columns`: exact header match to template field paths; then the core and package synonym lists; then the migration's mapping profile for the same old system and header.
Source: ADR-0051.R27

R669. L1 `map_columns` (seat data migration), for headers left: input header names, the target fields (path, meaning, type) and five sample values for each column. Output `DataMigrationMapColumnsOutput`: per column, a field path or `none`, and a transform (`none`, `date_dmy`, `date_mdy`, `decimal_comma`, `decimal_point`, `split_code_name`). Checks: each path is a field of the phase's template; one field takes at most one column; at least 95% of the sample values parse with the transform; otherwise `none`.
Source: ADR-0051.R27

R670. D2 `normalize`: tax IDs, phones, addresses (administrative unit codes), dates and decimals by the package's and core's rules. Values that fail stay raw with a row error.
Source: ADR-0051.R27

R671. D3 `map_accounts`: old account codes equal to a package chart template code map directly. L2 `map_accounts` (seat data migration), for old accounts left: input the old code and name and at most 10 template accounts by `rank_candidates`. Output `DataMigrationMapAccountsOutput`: `choice` (handle or `none`). Checks: the handle was offered. Accounts that need a company split stay for a person (ADR-0044.R6).
Source: ADR-0051.R27

R672. D4 `find_duplicates`: rows of the batch with an equal normalized key (tax ID, e-mail, code), and pairs whose name score is between 85 and 95. L3 `judge_duplicates` (seat data migration), for the pairs in that band: output `DataMigrationDuplicateOutput`: `verdict` (`same`, `different`, `unsure`), `reason_code`. Checks: enumerations.
Source: ADR-0051.R27

R673. D5 `update_batch`: `UpdateImportBatch` (DS-21's command on draft batches, `is_draft_only`) writes the mapping, the normalized values, the old account map and the merge suggestions for pairs that are equal by key or judged `same`; each suggestion raises `import_duplicate_suspected` for the batch's creator. The migration's mapping profile is updated in the same batch. Then `ValidateImportBatch` simulates the batch (ADR-0044.R5); its errors go into the note. Duplicate checks against existing company partners return redacted (ADR-0050.R27). Step `data_migration.update`.
Source: ADR-0051.R27

R674. Outputs of the data migration agent: the updated draft batch, the mapping profile, duplicate work items, the validation result and a note.
Source: ADR-0051.R28

R675. Human gates of the data migration agent: a person reviews the batch, decides merges, and runs it (`RunImport`, `human_only`); only a person completes or reverses a migration (ADR-0044 rules 5, 12, 14). Policy thresholds: none; import chunks are consequence postings of the person who runs them (ADR-0043.R5).
Source: ADR-0051.R28

R676. Personal data in migration: contacts in import files are personal, so their column samples go only to the data migration seat, class `personal`. With the routing switch on, they are replaced by shape masks (character class and length, ADR-0050.R9), so L1 maps those columns from their headers and shapes; the local model of ADR-0044.R16 waits for the author's answer.
Source: ADR-0051.R28

R677. Promotion evidence of the data migration agent is the stated exception to ADR-0051.R4: migration runs before go-live, so production has no shadow cases. The evidence is a staging rehearsal (ADR-0003.R12; ADR-0044.R1) with the agent in `shadow` on the version being promoted, meeting all of these:
- it covers every phase's batches of one complete rehearsal;
- at least 95% of the agent's column mappings and 95% of its old-account mappings equal those of the batches the person ran, over at least 100 mapped columns;
- no shadow output read or wrote outside its batch;
- the rehearsal's reconciliation passed (ADR-0044.R11).
Source: ADR-0051.R28

R678. The rehearsal's `evaluation_report.json`, with the hash of the staging snapshot it ran on, is attached to `CreateAgentPromotionEvidence`, which freezes its figures and version in the snapshot instead of reading `GetAgentShadowEvaluation`; the change proposal for `UpdateAgentTypeSetting` names that snapshot. The person who submits the proposal vouches for the report, and a person other than the submitter approves it.
Source: ADR-0051.R28

R679. Failures of the data migration agent: a batch larger than the run's row budget is handled in several runs, each on a range of rows; budgets stop a run cleanly between ranges.
Source: ADR-0051.R28

## Edge cases

| Edge case | Name | Case | Outcome | Protects |
| --- | --- | --- | --- | --- |
| `EC-81` | `supplier_invoice_line_unmapped` | A supplier e-invoice line has no `partner_item` mapping; the agent chooses among the supplier's related items, drafts the invoice and proposes the mapping; after approval the next invoice of that item maps without an LLM. Area `purchasing`, first step 7. | `must_succeed` | R642, R645, R647 |
| `EC-82` | `bank_description_free_text_reference` | A bank line's description names an invoice in free text that the cascade cannot use; the suggestion leads to a tainted draft without a score, which an enabled auto-post rule does not post. Area `cash`, first step 6. | `must_succeed` | R621, R622, R623; ADR-0051.R18 |

Also citing rules of this chunk, with a first source of another module: `EC-106` (unit text unresolved, R641) and `EC-241`
(the clean note path, R604).

## Conflicts

CONFLICT ADR-0051.R14: the inline note in the rule renames the trigger kind to `inbound_message_matched` (ADR-0052.R15), confirmed by ADR-0051.R14.N2; R601 states the new name, and that `quotation` is a Phase 2 type under ADR-0078.R2.
CONFLICT ADR-0051.R26: `data_migration` is a Phase 2 type under ADR-0078.R2, and its part of ADR-0044.R15 moves to Phase 2 (R665).
CONFLICT ADR-0051.R28: the rehearsal with the agent in `shadow` is Phase 2 content, because `data_migration` is a Phase 2 type and no live agent shadow runs in Phase 1 (ADR-0078.R2, ADR-0078.R6; R677, R678).
CONFLICT ADR-0051.R14.N2: the work item kind `inbound_message` became `inbound_message_matched` while the table keeps its old name; ADR-0052.R15 governs, stated in R601.
CONFLICT ADR-0051.R15: the "credit conditions" evaluated at `Submit` in D3 are corrected by ADR-0051.R15.N1; quotations have no credit condition, stated in R612.
CONFLICT ADR-0051.R16: the human gate's credit condition at quotation submit is removed by the correction note ADR-0051.R15.N1 on the previous rule; R616 lists discount, margin, below cost and outside the list.
CONFLICT ADR-0051.R19: the consumer no longer drafts a change proposal that a person submits; ADR-0051.R19.N1 (with ADR-0059.R10) makes it a tainted draft rule version, stated in R624 to R626; the comparator runs on stored output in Phase 1 under ADR-0078.R15 (R627).
CONFLICT ADR-0051.R19.N1: flagged "instead of": the draft `bank_matching_rule` version written by `CreateBankMatchingRuleVersion` replaces the change proposal draft of the rule; the note governs (R624, R625).
CONFLICT ADR-0051.R20: confirmation only by the importer holds for uploaded files; for a mailbox record any holder may confirm under ADR-0051.R20.N2 (ADR-0057.R25), stated in R631 and R639.
CONFLICT ADR-0051.R20.N1: its signature list lacks `signer_mismatch`, and its flat key refusal yields to quarantine and key conflicts; the later note ADR-0051.R20.N2 governs (R635, R637, R638).
CONFLICT ADR-0051.R20.N2: supersedes parts of the first intake note: mailbox route, quarantine, supersession, key conflicts imported and never refused; the note itself with ADR-0057.R25 governs, stated in R636 to R639.
CONFLICT ADR-0051.R22: "a tainted draft needs a person to post" now holds unless the auto-post gateway is enabled for this agent type, under ADR-0051.R22.N1 and ADR-0065.R19; stated in R647; the comparator runs on stored output in Phase 1 under ADR-0078.R15 (R649).
CONFLICT ADR-0051.R24: the lead-time test against a median of the last receipts is replaced by the stored mean of `supplier_item_lead_time` under ADR-0051.R24.N1; stated in R656.
CONFLICT ADR-0051.R25: the approver of the planning proposal is an eligible person of the pool's current stage, correcting "a planner other than the human", under ADR-0051.R25.N1 and ADR-0055.R7; stated in R660.
CONFLICT ADR-0051.R25.N2: its sentence that the runbook does not place the planning work yet is replaced by ADR-0051.R25.N3 (step 5b gate); stated in R664.
CONFLICT ADR-0051.R25.N3: flagged "replaces": the planning agent starts after the step 5b gate, which governs over the earlier note's open placement (ADR-0078.R1); stated in R664.

## Trace

| Source | Where |
| --- | --- |
| ADR-0051.R14 | R601-R603, R605 |
| ADR-0051.R14.N1 | R604 |
| ADR-0051.R14.N2 | R601 |
| ADR-0051.R15 | R606-R613 |
| ADR-0051.R15.N1 | R612, R616 |
| ADR-0051.R15.N2 | R610 |
| ADR-0051.R15.N3 | R606 |
| ADR-0051.R15.N4 | R608 |
| ADR-0051.R15.N5 | R614 |
| ADR-0051.R16 | R615, R616, R618, R619 |
| ADR-0051.R16.N1 | R617 |
| ADR-0051.R17 | R620-R622 |
| ADR-0051.R17.N1 | R623 |
| ADR-0051.R19 | R624, R626-R628 |
| ADR-0051.R19.N1 | R624-R626 |
| ADR-0051.R20 | R629, R631-R633 |
| ADR-0051.R20.N1 | R631, R634-R637, R639 |
| ADR-0051.R20.N2 | R629-R632, R635-R639 |
| ADR-0051.R21 | R640-R645 |
| ADR-0051.R21.N1 | R641, R643, R645 |
| ADR-0051.R22 | R646-R650 |
| ADR-0051.R22.N1 | R647 |
| ADR-0051.R22.N2 | R651 |
| ADR-0051.R23 | R652-R654 |
| ADR-0051.R24 | R655-R658 |
| ADR-0051.R24.N1 | R656 |
| ADR-0051.R24.N2 | R658 |
| ADR-0051.R25 | R659-R663 |
| ADR-0051.R25.N1 | R660 |
| ADR-0051.R25.N2 | R662, R664 |
| ADR-0051.R25.N3 | R664 |
| ADR-0051.R26 | R665-R667 |
| ADR-0051.R27 | R668-R673 |
| ADR-0051.R28 | R674-R679 |
