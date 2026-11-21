Module: documents    Chunk: 3 of 3    Source ADRs: ADR-0029, ADR-0030, ADR-0038, ADR-0053, ADR-0054, ADR-0055, ADR-0061
Build step(s): 0, 1, 3, 4, 5    Generated from index: 30d5706    Compiled by: Claude Fable 5.2, 2026-11-21

# Compiled spec: `documents`, chunk 3

## Purpose

`documents` owns the shared `document` row, its versions, approvals, numbering and change proposals, and sits in layer 2 (ADR-0022.R2). This chunk states the life of a change proposal after `Submit` and the rules that use it as carrier, taint on document versions and its clearance, the business keys of external documents and agent drafts, the attachment scan as `Post` reads it, the approval hold on invoice types set by the regime, the document owner, the stage columns of the `approval` row and document barcodes. As owner of the rest it also lists the owned tables, invariants, edge cases, settings and work item kinds that no rule of the other chunks names. Rules of commercial documents, pricing, units, policy, CRM, audit and personal data that name `documents` belong to their primary modules; their units are traced `ref:` and not restated.

## Entities and tables

DDL: `docs/design/DS-05-platform.sql` and, for the `document_installment` and `document_line_*` tables, `docs/design/DS-22-09-42-commercial-inventory.sql`.

| Table | Meaning | Key | Parent | Owner |
| --- | --- | --- | --- | --- |
| `change_proposal_execution` | Immutable record of the execution of an approved proposal: the proposal version executed (`document_version_id`) and `executed_at` (R404). | `id`; unique `change_proposal_id` (executed once, then closed) | `change_proposal`, `document_version` | documents |
| `change_proposal_execution_item` | Per executed item, its `item_index` and the `audit_record_id` of its command (R404, R408). | `id`; unique (`change_proposal_execution_id`, `item_index`) | `change_proposal_execution` | documents |
| `taint_clearance` | Immutable clearance of the taint of a document version: `cleared_by_user_id`, `reason`, `cleared_at` (R415). | `id`; unique `document_version_id` (one clearance per version; the DDL marks this key interim, not stated in ADR-0029) | `document_version` | documents |
| `document_installment` | Installment of a document: `installment_number`, `due_date`, `transaction_amount`, and `discount_due_date` with `discount_percent`, set together or not at all (ADR-0047.R6, ADR-0026.R5). | `id`; unique (`document_id`, `installment_number`) | `document` | documents |
| `document_line_custom_text` | Free text of an `is_custom` value on a document line, per `variant_attribute_id` (ADR-0046.R9, ADR-0045.R15). | `id`; unique (`document_id`, `line_number`, `variant_attribute_id`) | `document` | documents |
| `document_line_price_step` | One step of a line's price trace: `step` (`list_price`, `base_price`, `promotion`, `manual_discount`, `net_unit_price`, `line_amount`, `document_discount`), `source_table` with `source_id`, `value`, and `source_kind` (`procedure`, `manual`, `copied`; a copied step names `copied_from_document_id` and `copied_from_line_number`). Written by the pricing of `sales` and `purchasing` (ADR-0047.R16). | `id`; unique (`document_id`, `line_number`, `step_number`) | `document` | documents |

Rows in other chunks, to which the rules of this chunk add or which they constrain: `change_proposal_item` (stable `id`, R408; chunk 2), `numbering_configuration` (checked for barcoded types, R446, R447; chunk 1), `document` (`origin_work_item_id`, `workflow_step`, `draft_ordinal`, R424; `owner_employee_id`, `created_by_user_id`, R440 to R442; `is_barcoded`, R445), `document_version` (`is_tainted`, `derived_from_version_id`, R412), `approval` (R444) and `change_proposal` (`plan_hash`, R403; `execution_error`, the non-retryable error of the last execution attempt, R405).

Reads: `attachment` (`state`, through `attachments.contract`, R428), `agent_run`, `audit_record`, `segregation_exception`, `regime_setting`, `customer_profile`, `supplier_profile`, `partner`, `user_account`, `policy_decision`, `work_item`, `fiscal_year`, `branch`; the settings `permissions.small_company_mode` and `ui.post_review`.

## Commands and queries

| Name | Actor / authorization | Input | Effect | Events | Error codes |
| --- | --- | --- | --- | --- | --- |
| `Submit`, `Approve`, `Reject`, `Cancel` on a change proposal | `Submit` and `Cancel` at level `edit`, `Approve` and `Reject` by the role's approval flag, on the leaf `change_proposal` under `master_data` (catalogs `authorization-areas.csv`, `authorization-verb-levels.csv`); `Approve` and `Reject` by a human (R401, R402). The catalog `work-item-kinds.csv` names `SubmitChangeProposal` | The proposal | `draft → pending_approval`; back to `draft` on `Reject`; ended by `Cancel` (R401) | `ChangeProposalApproved` (R403); the events of ADR-0009.R22 | `segregation_of_duties` (R402), `approver_is_submitter` (R410) |
| `CloseChangeProposal` | Run by the executing consumer as `system`, on behalf of the approving human (R403, R404); the catalog level of the verb `Close` is `post` | The proposal | Moves the proposal to `closed` (R404) | not stated | not stated |
| `ListChangeProposal` (query) | not stated | not stated | Lists change proposals (R407) | None | not stated |
| `ClearTaint` | `human_only`; level `full` on the leaf `policy` (catalog `authorization-areas.csv`) | A document version and a reason (required) | Writes a `taint_clearance` row (R415, R416) | not stated | `segregation_of_duties` (R415) |

`UpdateChangeProposal`, also run as `system` after a failed execution (R405) and refused with `proposal_item_referenced` (R408), has its row in chunk 2.

Not registered commands: the transactional consumer of `ChangeProposalApproved` (R403 to R405); the system job that cancels expired proposals (R406); the trigger `document_check_row_change` (R445); the functions that `documents` registers with the dispatcher for document actors and counted approvals (ADR-0054.R2, ADR-0055.R1).

Codes bound to no command named in this chunk: `duplicate_external_document` and the check result `duplicate_suspected` (R421 to R423); `duplicate_draft` (R424); `attachment_not_available` on `Post` of any document type (R428); `approval_hold_not_allowed` on `Submit`, `Approve` and `Reject` of the regime-flagged types (R433); `barcode_prefix_reserved` and `numbering_barcode_invalid` (R446, R447); `plan_hash_mismatch`, `target_changed`, `concurrent_update` and `timeout` inside the execution of a proposal (R405).

## Rules

### Change proposal: approval, execution and expiry

R401. A change proposal uses the non-posting states of ADR-0009 and the events of ADR-0009.R22. `Submit` moves it `draft → pending_approval` and is a policy point. `Approve` or `Reject` is by a human. `Reject` returns the proposal to `draft`, and `Cancel` ends it.
Source: ADR-0029.R3

R402. The approver must hold the target permissions and every field class the proposal changes (ADR-0017.R10), and sees the plan filtered by their field classes. The human for whom the originating run acted cannot approve (`segregation_of_duties`, ADR-0017.R16, which scans every version). No writer of any version approves (ADR-0055.R7, condition 5); the small-company mode lifts that for humans, but never the bank-account rule of ADR-0029.R4 (note on ADR-0054.R20). With approval stages, the approving human is the approver whose approval completed the plan (note on ADR-0055.R16).
Source: ADR-0029.R3, .N1, .N2

R403. A transactional consumer of `ChangeProposalApproved` executes the items as one command batch (ADR-0008.R20). It runs as actor `system`, on behalf of the approving human, with key `<consumer>:<event id>:1`, the stored `plan_hash` as `expected_plan_hash` (an exception to ADR-0013.R9, which otherwise runs internal calls without one), and each item's `expected_version`. The batch runs inside a savepoint of the delivery transaction.
Source: ADR-0029.R3

R404. On success the consumer writes an immutable `change_proposal_execution` row (the proposal version, the audit row of each item, `executed_at`) and runs `CloseChangeProposal`, which moves the proposal to `closed`. The audit record IDs come from the dispatch result (ADR-0038.R1).
Source: ADR-0029.R3

R405. A retryable error (`concurrent_update`, `timeout`) rolls back the delivery and is retried (ADR-0013.R8). On any non-retryable error, such as `plan_hash_mismatch` or `target_changed`, the consumer rolls back to the savepoint and runs `UpdateChangeProposal` as `system`, which commits with the delivery. That writes the next version with the error and the new plan, voids the approval (ADR-0009.R9), returns the proposal to `draft`, and creates a work item.
Source: ADR-0029.R3

R406. A system job cancels proposals that are not approved within `change_proposal_ttl_days`, with reason `expired`. `change_proposal_ttl_days` is a company setting with interim default 14.
Source: ADR-0029.R3

R407. Agents, and the consumers acting on their chains, create proposals as drafts only; a person submits them, and a person other than the human the run acted for approves them (ADR-0050.R30; ADR-0051.R13, ADR-0051.R19, ADR-0051.R22, ADR-0051.R25). The query of proposals is `ListChangeProposal`.
Source: ADR-0029.R3

R408. A draft structure may refer to a proposal item by its stable `change_proposal_item.id`. Reordering items keeps their IDs; an update that would remove or replace a referenced item is refused with `proposal_item_referenced`. Consumers read each executed item's result from its audit record (`change_proposal_execution_item.audit_record_id`) (ADR-0062.R14).
Source: ADR-0029.R3.N3

### Rules that use the change proposal as carrier

R409. These changes use the change proposal as carrier:
   - `partner_item` mappings (ADR-0019.R6);
   - tax ID differences (ADR-0019.R18);
   - planning parameters, lead times and forecast adjustments (ADR-0024.R1, ADR-0024.R12, ADR-0024.R23);
   - price lists (DS-20);
   - putaway rules, pick-face levels and count plans (ADR-0023.R21);
   - agent changes to planned orders: `UpdatePlannedOrder`, `FirmPlannedOrder`, `ConvertPlannedOrder` (ADR-0036.R12);
   - technical completion and reopening of production orders (ADR-0034.R17);
   - releases of bills of materials and routings, production versions, work centers and production settings (ADR-0033.R2);
   - CRM: new partners and contacts from e-mail with their domains, matches, interactions and follow-up tasks, summaries, complaints and processing bases (ADR-0052.R10, ADR-0052.R16, ADR-0052.R19, ADR-0052.R20, ADR-0052.R23, ADR-0052.R31).
   Source: ADR-0029.R5

R410. The carrier also serves the promotion of an agent type to assisted mode (`UpdateAgentTypeSetting`, with a frozen evidence snapshot), whose approver must differ from its submitter (`approver_is_submitter`) (ADR-0050.R14). It serves the activation and promotion of configuration and decision artifacts as well: `SetArtifactVersionState` raising a version, with frozen evidence, and the owner change of an automation rule with a version in force. There the approver is neither the submitter (`approver_is_submitter`) nor the version's drafter nor the human the drafting run acted for (ADR-0058.R9, ADR-0058.R24; ADR-0059.R13).
Source: ADR-0029.R5, .N2

R411. For price lists the carrier binds agents and chains carrying an origin agent run (ADR-0029.R4). A person with the permission runs `SetPriceListEntries` and the other price-list commands directly, unless the company adds a `direct_master_data_change` deny rule for them (ADR-0043.R12); the core seeds only the bank-account rule (ADR-0043.R15). Dual control on prices is an open question for the author.
Source: ADR-0029.R5.N1

### Taint on document versions

R412. `document_version.is_tainted` is set at insert and never changed. It is true when a run tainted at that time wrote the version, directly or as the origin of a consumer chain (ADR-0013.R9, ADR-0013.R11), or when the version it derives from had effective taint (R420) when it was written. That version is the previous version, the version in force for a change (ADR-0028.R4), or, for version 1, the source document version it was created from. The nullable `document_version.derived_from_version_id` stores the last two, so the derivation is checkable.
Source: ADR-0029.R8

R413. A version whose content copies a value from an `is_untrusted` field is written tainted, for example a matching-rule proposal built from a token an agent read in a bank description (ADR-0051.R19).
Source: ADR-0029.R8

R414. A version written from source lines of other documents (a document created by copying, ADR-0047.R2) is tainted when any source line's document version had effective taint when it was written, on `Create` and on every `Update` that adds source lines. `derived_from_version_id` names the first, and `INV-88` also reads the others through the lines' typed references. Handlers of `inventory` and `production` that create documents from source lines set it the same way (ADR-0023.R16).
Source: ADR-0029.R8.N1

R415. `ClearTaint` (`human_only`, reason required) writes an immutable `taint_clearance` row: `document_version_id`, the human actor, the reason and `cleared_at`. The human for whom the tainted run acted cannot clear it (`segregation_of_duties`), except under R416. Clearing never changes field attributes or read-taint.
Source: ADR-0029.R8

R416. While `permissions.small_company_mode` is on (ADR-0054.R20), the human for whom a tainted run acted may clear that run's versions: one `ClearTaint` per version with a reason, as a single command, never a batch item, bulk review or case-level confirmation. Each such clearance writes a `segregation_exception` of kind `own_run_taint_clearance`, reviewed at period close through `ConfirmSegregationReview`. A version whose only clearances are self-clearances counts as tainted for the tainted-draft eligibility of ADR-0065.R10 and never feeds agent promotion or auto-post evidence. Outside the mode R415 applies unchanged (ADR-0067.R17).
Source: ADR-0029.R8.N3

R417. A work case holds no taint of its own. `GetWorkCase` computes a summary of its artifact versions' effective taint on read, and clearance stays `ClearTaint` per version; no case-level clearance exists. The case view shows the tainted versions together, but each is cleared by its own `ClearTaint` with its own reason and confirmation; no confirmation covers several versions (ADR-0066.R18).
Source: ADR-0029.R8.N2

R418. The UI shows the provenance of every agent-written or intake-written value from this data: the source (actor kind, agent run, extraction method), the extraction engine's confidence only, the taint with its clearance, and a link to the audit record, in one visual style with icon and text (ADR-0077.R15).
Source: ADR-0029.R8.N4

R419. The taint rules R412, R413 and R415 are interim and flagged: they change the untrusted-content mechanism (ADR-0005 item 7; open question).
Source: ADR-0029.R8

R420. Effective taint means `is_tainted` with no clearance on that version. A version written later by a tainted run is tainted again.
Source: ADR-0029.R9

### External documents and agent drafts

R421. External documents get unique business keys, all including `company_id`. A second arrival is rejected with `duplicate_external_document`, naming the existing record, unless R422 or R423 states otherwise.
Source: ADR-0030.R10, .N1

R422. The business keys are:
   - supplier e-invoice: declared by the localization package (ADR-0016), flagged `unverified`; the key's parts are package content;
   - bank statement line: bank account, bank reference, value date and amount; without a reference no key applies, and an equal line gives the check result `duplicate_suspected` and both are kept;
   - e-mail: company, `Message-ID` and content hash (ADR-0019.R14, beside the mailbox UID), not a unique index on `Message-ID` alone.
   Source: ADR-0030.R10, .N1

R423. A sender controls the `Message-ID`, so intake skips a second message only when its content hash also matches; otherwise both are kept and the later is flagged `duplicate_suspected`. Without a `Message-ID`, only the UID applies. E-mail keys are stored as hashes, copies point to the canonical row, and a message counts as own only with an authenticated company sender or the sent content hash (ADR-0052.R13).
Source: ADR-0030.R10, .N1

R424. Documents an agent drafts store `origin_work_item_id`, `workflow_step` and `draft_ordinal` (a number the step defines) on the shared `document` row (ADR-0009.R1). Together with `document_type` they are unique among documents in any state except `canceled`. A second attempt by any run is rejected with `duplicate_draft`, naming the existing draft, so a re-run of a crashed agent does not draft twice. `workflow_step` values are `<agent_type>.<step_code>` (ADR-0051.R8).
Source: ADR-0030.R11

### Attachment scan

R425. `attachment.state` is one of `pending_scan`, `clean` and `rejected`. A new attachment emits `AttachmentCreated`. A consumer on `integrations` runs the scanner and records the outcome. A scanner outage retries and is eventually held (ADR-0013.R8).
Source: ADR-0038.R14

R426. A rejected attachment stops being served at once, and the transaction that records the rejection sets its `bytes_released_at`; its bytes are physically removed only by the orphan sweep of the note on ADR-0038.R15, after the grace period. Its links are removed with a work item. A new upload of the same SHA-256 as a rejected row is refused with `attachment_rejected`. An upload matching a pending row reuses it.
Source: ADR-0038.R14, .N3

R427. Bytes that are not `clean` are never served, to people or agents: download and parsing fail with `attachment_not_available`. An attachment linked to a document follows that document's read owner scope (ADR-0054.R15). An attachment linked to a message (`target_table` `message`) is served only to those who may read the message's conversation now; withdrawing a message, and message retention, end its links (ADR-0076.R4, ADR-0076.R10).
Source: ADR-0038.R14, .N2, .N4

R428. `Post` of a document with a linked attachment that is not `clean` is rejected with `attachment_not_available`. `documents` reads the state through `attachments.contract`, an import inside layer 2 (ADR-0022, ADR-0027.R1).
Source: ADR-0038.R14

R429. `attachment_scan_mode` is an installation setting: `required`, or `optional`, under which attachments pass with the check result `scan_unavailable` when no scanner is deployed. A `production` installation requires `attachment_scan_mode` = `required`, checked at startup.
Source: ADR-0038.R14, .N5

R430. Attachments from outside content are untrusted (ADR-0029.R10).
Source: ADR-0038.R14

R431. Generated files (source kind `generated`) are created `clean` without a malware scan: the render worker produces their bytes from company templates in a sandbox without network access. `clean` covers only the scan. A generated file whose rendered instance held an `is_untrusted` field carries `contains_untrusted`, and reading it taints a run (ADR-0050.R25; ADR-0049.R28).
Source: ADR-0038.R14.N1

### Approval hold on invoice types

R432. For `sales_invoice`, `sales_return`, `credit_note` and `debit_note`, whether an approval hold is allowed is the regime's, through the setting `documents.issuance_without_delay`. True means the document is issued without delay, so no approval hold. These types are registered with `is_approval_hold_allowed: regime`, a third value beside `true` and `false` (ADR-0009.R2). Other types keep their fixed flags.
Source: ADR-0053.R8

R433. `Submit`, `Approve` and `Reject` are always generated for these types. While the setting is true for the document's date, they are rejected at run time with `approval_hold_not_allowed` (a precondition), and the type behaves as `is_approval_hold_allowed: false`: the interim of ADR-0009.R12 (human only) and ADR-0043.R10 apply.
Source: ADR-0053.R8

R434. `documents.issuance_without_delay` is boolean, read through `regime_setting(company, key, document_date)`, with `date_basis` `document_date`.
Source: ADR-0053.R8

R435. When the hold is allowed and an e-invoice is required (ADR-0028.R6), the states are `draft → pending_approval → approved → issuing → posted`. `Issue<Type>` is allowed only from `approved`. A rejection by the provider returns the document to `draft`, and it is submitted again. When the setting is true, ADR-0028.R6 applies as written: `draft → issuing → posted`.
Source: ADR-0053.R8

R436. The core default of `documents.issuance_without_delay` is false. It is the first optional key with a core default:
   - the check of ADR-0016.R15, that every required key has a row for each regime, does not apply to it;
   - a regime without a row reads false instead of failing with `regime_configuration_missing` (ADR-0016.R10);
   - the default is core behavior, not a package rule, so it carries no basis and is not subject to the unverified gate of ADR-0016.R12. A package row overrides it and carries its own basis.
   Source: ADR-0053.R8

R437. `l10n_vn` seeds `documents.issuance_without_delay` at package level, for every regime, because it comes from invoice law, not from the accounting regime. The value is flagged content of the localization package (`settings.yaml`, `unverified`, with an open question).
Source: ADR-0053.R8

R438. Whether an e-invoice is required (ADR-0028.R6) is the regime setting `documents.e_invoice_required`: a map from document type to boolean, read through `regime_setting(company, key, document_date)` with `date_basis` `document_date`. Only `is_e_invoice_capable` types may be named. It is the second optional key with a core default and is handled like `documents.issuance_without_delay` (R436): no row, or a type missing from the map, reads false, with no basis and outside the unverified gate. `l10n_vn` seeds it at package level, for every regime; its values are flagged content of the localization package (`settings.yaml`, `unverified`, open question).
Source: ADR-0053.R8.N1

R439. A type for which `documents.e_invoice_required` reads true takes `Issue<Type>`, `issuing` and the posting by `system` on behalf of the issuer (ADR-0028.R7); where the setting reads false the type posts with `Post<Type>`. Until the e-invoice add-on (DS-24) exists, the core build, the tests and the simulation use the deterministic stub adapter of ADR-0028.R12.
Source: ADR-0053.R8.N1

### Document owner

R440. The shared `document` row (ADR-0009.R1) has `owner_employee_id` (an employee partner, nullable) and `created_by_user_id`. `created_by_user_id` is the human of version 1: the actor if human, else its `on_behalf_of` (for agents, system jobs, consumers and integrations).
Source: ADR-0054.R14

R441. `owner_employee_id` comes from the field the document type registers as `owner_field` (ADR-0009.R2). `documents` sets it at `Create` and on every `Update` that changes the owner field; neither column is part of the version content. The defaults by type are:
   - `quotation`, `sales_order`, `sales_invoice`, `sales_return`, `credit_note`, `debit_note`: `salesperson_id`;
   - `purchase_request`, `purchase_order`, `purchase_invoice`, `purchase_return`, `purchase_credit_note`, `purchase_debit_note`, `gr_ir_write_off`: `buyer_id`;
   - every other type: the creating user's employee.
   Source: ADR-0054.R14

R442. An owner field naming an employee without a user account still works through `department` and `team`; a document with no owner employee is reached through `own` only by its creator.
Source: ADR-0054.R14

R443. Agent workflows set a draft's owner field from the scope partner's profile: `salesperson_id` from `customer_profile.salesperson_id`, `buyer_id` from `supplier_profile.buyer_id`, left empty when the profile names none (note on ADR-0051.R8). The person holding the claim of the work item a draft is linked to reads and edits that draft while the claim holds, whatever their owner scope (record scope and permissions still apply), through the visibility function of ADR-0054.R2 (note on ADR-0042.R10).
Source: ADR-0054.R14.N1

### Approval row with stages

R444. The `approval` row (ADR-0009.R11) has `approval_stage_id` and `approval_pool_id`; `delegated_from_user_id`, empty unless a substitute acted; `is_escalated`, true when the approver was eligible only through the escalation role; and `policy_decision_id` (ADR-0028.R14). `reason` stays required for both decisions and serves as the comment. Rows stay immutable.
Source: ADR-0055.R9

### Document barcodes

R445. A document type may be registered `is_barcoded`, a registry flag of printable types (ADR-0009.R15). Phase 1: purchase orders, goods receipts, sales orders, deliveries, transfer orders and production orders. The barcode is the document number: `document.is_barcoded` is set from the flag at `Create`, and `document_check_row_change` refuses any later change. When such a document is numbered, the trigger registers its number in upper case as type `document`.
Source: ADR-0061.R9

R446. The number format of a barcoded type must start with `{prefix}` followed by a separator (`/`, `-` or `.`). That string (`PO/`) is reserved: no barcoded type's reserved string may start another's, and no barcode of another type may start with one (`barcode_prefix_reserved`, checked when a barcode is created and when a numbering configuration is created or changed).
Source: ADR-0061.R9

R447. When a numbering configuration of a barcoded type is created or changed, and when a branch code or fiscal year code that such a format uses is created or changed, the command checks that every number the format can produce is an internal code: its literal characters and the codes it uses are in the internal character set (letters in either case, since the number is registered in upper case), and its longest number, with the counter at full width, has at most 48 characters (`numbering_barcode_invalid`, naming the part that fails). So numbering never fails on the registry's format check. The default format `{prefix}/{fiscal_year_code}/{counter:6}` (ADR-0009.R16) satisfies it when the codes do.
Source: ADR-0061.R9

## Invariants

Statements are those of `invariants.csv`. This chunk holds the rows whose catalog source is a rule of this chunk or a rule of another module. "Protects" names a rule of this chunk or the source ID of a rule stated elsewhere.

| Invariant | Name | Check point | Statement | Protects |
| --- | --- | --- | --- | --- |
| `INV-49` | `document_partner_matches_header` | day | For every document type with a partner field, the shared document row's `partner_id` and `document_date` equal the typed header's values; types without one have both empty. | ADR-0052.R18 |
| `INV-88` | `taint_inherited` | day | Every document version written by a run tainted at its `recorded_at`, or whose origin run was, or whose previous or `derived_from_version_id` version was effectively tainted when it was written, has `is_tainted` true. Flagged: taint clearing (ADR-0029.R8). Area `safety`. | R412, R414 |
| `INV-90` | `sales_delivered_within_ordered` | day | Per sales order line, delivered net of returns never exceeds the ordered quantity. | ADR-0047.R20 |
| `INV-91` | `sales_invoiced_within_delivered` | day | Per stock sales order line, invoiced net of quantity credits never exceeds delivered net of returns, unless an open `sales_return_due` work item names the line. Purchase lines may be invoiced before receipt (ADR-0047.R14). | ADR-0047.R20 |
| `INV-93` | `price_steps_reproduce_price` | day | Every commercial document line's price steps reproduce its net unit price and its line amount. | ADR-0047.R16 |
| `INV-230` | `ranked_decision_has_plan` | day | Every policy decision with a required rank has a non-empty `approval_plan`. | ADR-0055.R5 |
| `INV-600` | `line_unit_snapshot_consistent` | day | Every quantity line carries its unit block; its snapshot equals `convert_quantity` for its item and unit when the unit was set (the item row, the product row or the global pair then in force), or its source line's snapshot for a line in the source's unit; its inventory quantity is `round_quantity`(quantity x factor) in the line's mode, or the cumulative value of `INV-601`. | ADR-0056.R6, ADR-0056.R9 |
| `INV-601` | `cumulative_parts_sum` | day | For every posted source line (for invoices, the order line), each forward part in its unit posted round((C + q) × f) − P at its snapshot, positive and clamped to between q × f − 1 and q × f + 1 inventory units (a value of zero or less is rejected), with C and P the actual net sums of the earlier posted parts in that unit; each return, credit or reversal of a part in the part's unit mirrors the part or takes its cumulative share of the part's stored inventory quantity, never exceeding it; a money-side return naming a stock return line in its unit and entered quantity posted that line's inventory quantity; T(S) grew only by rounded parts in other units and by the changes returns, credits, reversals and clamps made to the deviation; and when C reaches the source's entered quantity, P is within T(S) of its inventory quantity, and equal to it when T(S) is zero. | ADR-0056.R10 |
| `INV-603` | `line_factor_in_force` | day | Every line whose snapshot source is item or product carries the factor of the row in force for its item and unit when its snapshot was taken, at the level it names (an item row before the product row; a level with rows but none in force uncovers nothing; a row is in force from `created_at` until `retired_at`), unless it is a follow-on line keeping its source line's snapshot; no line, price entry, supplier item or product default names a retired company unit or global conversion after its retirement, with the same exemption. | ADR-0056.R2, ADR-0056.R5, ADR-0056.R6 |
| `INV-864` | `document_party_complete` | day | Every named document party has its name; a tax ID, an address or an address key is held only with its party, and the address is one of the party's own; every party is a partner of the document's company; a party is named exactly when its name is. | ADR-0074.R1, ADR-0074.R2 |

Named by the rules of this chunk, with their rows elsewhere: `INV-82` (reads the `approval` rows of R444; row in chunk 1); `INV-17` (area `platform`, reads the same rows; `ADR-0055.R1`) and `INV-84` (area `safety`, effective taint, R420), stated by the specs of their own modules.

## Edge cases

| Edge case | Name | Case | Outcome | Protects |
| --- | --- | --- | --- | --- |
| `EC-14` | `uom_conversion` | Bought in cartons, sold in bottles. | `must_succeed` | spec 12; ADR-0018 |
| `EC-19` | `partial_fulfilment` | Partial deliveries, receipts and invoices of one order. | `must_succeed` | spec 12 |
| `EC-21` | `credit_limit_exceeded` | A sales order that would take a customer over its credit limit. Interim, flagged (ADR-0047.R18): approval at `Submit`; deliveries of other unreleased orders held. | `must_succeed` | spec 12; ADR-0047.R18 |
| `EC-22` | `price_below_cost` | A sales price below the item's current cost. Interim, flagged (ADR-0047.R22): `is_price_below_cost` feeds the policy; the outcome is the company's rules. | `must_succeed` | spec 12; ADR-0045.R5; ADR-0047.R22 |
| `EC-63` | `concurrent_orders_one_credit_limit` | Two orders of one customer are submitted at the same time; each credit check sees the other's exposure. Interim, flagged (ADR-0047.R18). | `must_succeed` | ADR-0030 |
| `EC-69` | `purchase_price_change_between_receipts` | A change order changes a purchase price between two receipts; the invoice clears GR/IR at each position's first-posted price, and a return after the change takes the latest positions. | `must_succeed` | ADR-0047.R13 |
| `EC-70` | `free_goods_with_document_discount` | A sales order with a free goods promotion and a document discount; the discount is allocated to the paid lines by largest remainder and the free line stays at zero. | `must_succeed` | ADR-0047.R16, ADR-0047.R17 |
| `EC-71` | `purchase_invoice_match_tolerance` | One supplier invoice within the price tolerance posts without approval; another beyond it needs approval through `is_match_exceeded`. | `must_succeed` | ADR-0047.R14 |
| `EC-103` | `grams_through_catalog` | A product kept in kilograms is sold and delivered in grams through the core conversion, with no product unit; the lines snapshot source `global`. | `must_succeed` | ADR-0056.R3, ADR-0056.R6 |
| `EC-104` | `item_level_unit` | Two variants of one product have cartons of 24 and of 12; an order of the second variant in cartons converts by its item-level row. | `must_succeed` | ADR-0056.R4, ADR-0056.R6 |
| `EC-105` | `retired_unit` | A supplier changes its carton from 24 to 20: the carton row of 24 is retired and a carton row of 20 added on the same unit code; carton price entries are end-dated; a new order line in cartons converts at 20, while the receipt of an open order in cartons keeps its snapshot of 24. | `must_succeed` | ADR-0056.R5 |
| `EC-112` | `approval_two_stages_k_of_n` | A purchase order above the senior rank is approved by one accountant at the first stage and by two of three managers at a stage with k = 2, then posts. | `must_succeed` | ADR-0055.R5 to ADR-0055.R8 |
| `EC-113` | `approval_edit_after_first_stage` | A document edited after its first stage approval loses that approval; the resubmission starts again at the first stage. | `must_succeed` | ADR-0055.R10 |
| `EC-114` | `approval_rejected_at_second_stage` | A rejection at the second stage returns the document to draft with the reason; the next round starts at the first stage and earlier approvals do not count. | `must_succeed` | ADR-0055.R10 |
| `EC-115` | `approval_by_substitute` | An approver on leave delegated approval authority; the substitute approves inside the window, recorded with `delegated_from`, and is refused the day after it ends. | `must_succeed` inside the window; `must_reject:approver_not_eligible` after it | R444; ADR-0055.R14; ADR-0054.R21 |
| `EC-117` | `approval_would_strand_stage` | In a two-person company in small-company mode, the owner tries to approve the first stage of a rank-20 document the accountant wrote and is refused; the accountant approves the first stage and the owner the second. | `must_reject:approval_would_strand_stage` for the owner at the first stage; then `must_succeed` | ADR-0055.R7, ADR-0055.R20 |
| `EC-131` | `deliveries_within_rounding_tolerance` | 8.000 kg ordered and delivered as three bags of 8/3 kg, each converting on its own to 2.667 kg: the third delivery (8.001 kg in total) is accepted within the unit rounding tolerance of 0.003 kg and fulfils the line. | `must_succeed` | ADR-0056.R10 |
| `EC-139` | `vision_total_on_two_lines` | A vision value for a total cites words on two lines; it is stored unaligned, fills nothing, and the computed total decides the rule. | `must_succeed` | ADR-0057.R12 |
| `EC-252` | `one_click_post_clean` | Under quickflows a person posts a clean sales invoice below the post review maximum and the risk amount; the simulation returns no review reason, the client executes at once, the audit record has `is_review_skipped`, and the history shows the plan. | `must_succeed` | ADR-0067.R12, ADR-0067.R13 |
| `EC-253` | `one_click_post_exception` | The same person posts an invoice above the post review maximum, then a goods delivery with a negative-stock check result; both return review reasons and open the plan panel; a client that sends `is_review_skipped` anyway gets `post_review_required` and nothing is committed. | `must_reject:post_review_required` | ADR-0067.R12, ADR-0067.R13 |
| `EC-311` | `party_defaults_from_relationships` | A partner with one default ship-to and no payer relationship gets the ship-to on a new order and no payer; changing the default does not touch an existing order. | `must_succeed` | ADR-0074.R1 to ADR-0074.R3 |
| `EC-316` | `cancel_with_reason` | A quotation canceled with a reason of kind `cancel` and a note; a reason of another kind or an inactive one is refused with `reason_invalid`. | `must_succeed`; `must_reject:reason_invalid` for the wrong or inactive reason | ADR-0074.R13, ADR-0074.R14 |
| `EC-318` | `header_note_frozen` | A note written on a draft is part of its version and cannot change after posting; the journal entry carries a copy. | `must_succeed` | ADR-0074.R16, ADR-0074.R17 |
| `EC-330` | `reason_required_by_setting` | With the core defaults, a count difference, a scrap line or an other issue without a reason is refused with `reason_required` and a cancel without one succeeds; after `documents.reason_required.scrap` is set false, the same scrap line posts. | `must_reject:reason_required`; `must_succeed` for the cancel and after the change | ADR-0074.R22 |

Rows in chunk 2, whose rules their catalog source names: `EC-20` (ADR-0009.R23), `EC-312` (ADR-0028.R16), `EC-53`, `EC-54`, `EC-55`, `EC-59` and `EC-60` (ADR-0028). Edge cases of other areas that concern the rules of this chunk, stated by the specs of their own modules: `EC-56` (a change proposal approved by a second human), `EC-57` (taint through a draft), `EC-58` (auto-posts block the close; named by `ADR-0028.R17`), `EC-64` and `EC-228` (`duplicate_external_document`).

## Settings

| Key | Value type | Scopes | Core default | Used by |
| --- | --- | --- | --- | --- |
| `documents.unit_name_max_length` | integer (bounds 1..255) | `regime` | `unset` | ADR-0063.R23; ADR-0056.R18 |
| `documents.unit_name_source` | enum (`statutory_then_translation`, `translation`) | `regime` | `statutory_then_translation` | ADR-0063.R23; ADR-0056.R2 |
| `documents.e_invoice_unit_code_scheme` | enum (`none`, `unece_rec20_21`) | `regime` | `unece_rec20_21` | ADR-0063.R23 |
| `documents.reason_required.cancel` | boolean | `company` | `false` | ADR-0074.R22 |
| `documents.reason_required.reject` | boolean | `company` | `true` | ADR-0074.R22 |
| `documents.reason_required.return` | boolean | `company` | `true` | ADR-0074.R22 |
| `documents.reason_required.scrap` | boolean | `company` | `true` | ADR-0074.R22 |
| `documents.reason_required.count_difference` | boolean | `company` | `true` | ADR-0074.R22 |
| `documents.reason_required.block` | boolean | `company` | `false` | ADR-0074.R22 |
| `documents.reason_required.other_receipt` | boolean | `company` | `true` | ADR-0074.R22 |
| `documents.reason_required.other_issue` | boolean | `company` | `true` | ADR-0074.R22 |

Each `documents.reason_required.<kind>` key, when true, refuses a missing reason of that kind with `reason_required`.

Named by the rules of this chunk and absent from `settings.csv`: `change_proposal_ttl_days` (company setting, interim default 14, R406); `attachment_scan_mode` (installation setting, `required` or `optional`, R429); `documents.issuance_without_delay` (regime setting, boolean, core default false, R432 to R437); `documents.e_invoice_required` (regime setting, a map from document type to boolean, core default false, R438, R439). The last two keys are also named by chunks 1 and 2 (`ADR-0009.R2`, `ADR-0009.R12`, `ADR-0028.R6`) and are stated only here.

Reads: `cash.auto_post.accept_llm_originated_rules` (`cash`; `ADR-0065.R22`); `master_data.product_code.assignment`, `master_data.product_code.prefix_source`, `master_data.product_code.pad_width` (`master_data`; `ADR-0062.R9.N1`); `tax.destination_party`, `tax.services_place_of_supply` (`tax`; `ADR-0074.R4.N1`); `permissions.small_company_mode` (R416); `ui.post_review`.

## UI annotations

- Provenance display: every agent-written or intake-written value shows its source, the extraction engine's confidence, taint with its clearance and a link to the audit record, in one visual style (R418; ADR-0077.R15). The color roles `provenance-ai`, `provenance-document` and `taint` are design tokens of `app` (ADR-0077.R21).
- Work item kinds of `documents` (`work-item-kinds.csv`): `change_proposal_failed` (subject `change_proposal`, owner rule `document_owner`, due `days:1`, resolved by the command `SubmitChangeProposal` or by canceling; raised by R405) and `approval_pending` (subject `document`, owner rule `approval_stage`, due `stage_due_days`, resolution command `Approve<Type>`; a document or change proposal waiting for approval, resolved by `Approve`, `Reject`, a new version, `Cancel` or `Delete`; ADR-0042.R17, ADR-0043.R13). Neither is agent-resolvable.
- The sources give no floorplan or tile for the units of this chunk.

## Conflicts

CONFLICT ADR-0029.R3: the question whether a human may approve a proposal they wrote is no longer open; ADR-0029.R3.N1 governs, with condition 5 of ADR-0055.R7 (R402).
CONFLICT ADR-0029.R8: ADR-0029.R8.N3 governs clearance by the human the tainted run acted for while the small-company mode is on; outside the mode the refusal stands (R415, R416).
CONFLICT ADR-0030.R10: the mark "interim, flagged: reject versus warn" is dropped; ADR-0030.R10.N1 confirms that a second arrival is rejected (R421 to R423).
CONFLICT ADR-0038.R14: ADR-0038.R14.N3 governs; "their bytes are deleted at once" is not restated, a rejected attachment is released and its bytes go with the orphan sweep (R426).
CONFLICT ADR-0038.R14.N5: the mark "flagged; open question" on the scan mode of `production` installations is dropped; the requirement is checked at startup (R429).

## Proposed (not law)

None

## Trace

| Source | Where |
| --- | --- |
| ADR-0029.R3 | R401-R407 |
| ADR-0029.R3.N1 | R402 |
| ADR-0029.R3.N2 | R402 |
| ADR-0029.R3.N3 | R408 |
| ADR-0029.R4.N2 | ref: ADR-0029.R4.N2 |
| ADR-0029.R5 | R409, R410 |
| ADR-0029.R5.N1 | R411 |
| ADR-0029.R5.N2 | R410 |
| ADR-0029.R8 | R412, R413, R415, R419 |
| ADR-0029.R8.N1 | R414 |
| ADR-0029.R8.N2 | R417 |
| ADR-0029.R8.N3 | R416 |
| ADR-0029.R8.N4 | R418 |
| ADR-0029.R9 | R420 |
| ADR-0029.K.N1 | ref: ADR-0029.K.N1 |
| ADR-0030.R10 | R421-R423 |
| ADR-0030.R10.N1 | R421-R423 |
| ADR-0030.R11 | R424 |
| ADR-0038.R2 | ref: ADR-0038.R2 |
| ADR-0038.R2.N1 | ref: ADR-0038.R2.N1 |
| ADR-0038.R2.N2 | ref: ADR-0038.R2.N2 |
| ADR-0038.R2.N3 | ref: ADR-0038.R2.N3 |
| ADR-0038.R2.N4 | ref: ADR-0038.R2.N4 |
| ADR-0038.R3 | ref: ADR-0038.R3 |
| ADR-0038.R14 | R425-R430 |
| ADR-0038.R14.N1 | R431 |
| ADR-0038.R14.N2 | R427 |
| ADR-0038.R14.N3 | R426 |
| ADR-0038.R14.N4 | R427 |
| ADR-0038.R14.N5 | R429 |
| ADR-0041.R4.N2 | ref: ADR-0041.R4.N2 |
| ADR-0041.R5 | ref: ADR-0041.R5 |
| ADR-0041.R5.N1 | ref: ADR-0041.R5.N1 |
| ADR-0041.R9 | ref: ADR-0041.R9 |
| ADR-0043.R1 | ref: ADR-0043.R1 |
| ADR-0043.R1.N1 | ref: ADR-0043.R1.N1 |
| ADR-0043.R1.N2 | ref: ADR-0043.R1.N2 |
| ADR-0043.R5.N1 | ref: ADR-0043.R5.N1 |
| ADR-0043.R13 | ref: ADR-0043.R13 |
| ADR-0043.R13.N1 | ref: ADR-0043.R13.N1 |
| ADR-0043.R13.N2 | ref: ADR-0043.R13.N2 |
| ADR-0043.R13.N3 | ref: ADR-0043.R13.N3 |
| ADR-0046.R9 | ref: ADR-0046.R9 |
| ADR-0046.R9.N1 | ref: ADR-0046.R9.N1 |
| ADR-0047.R1.N4 | ref: ADR-0047.R1.N4 |
| ADR-0047.R2 | ref: ADR-0047.R2 |
| ADR-0047.R2.N1 | ref: ADR-0047.R2.N1 |
| ADR-0047.R2.N2 | ref: ADR-0047.R2.N2 |
| ADR-0047.R2.N3 | ref: ADR-0047.R2.N3 |
| ADR-0047.R2.N4 | ref: ADR-0047.R2.N4 |
| ADR-0047.R2.N5 | ref: ADR-0047.R2.N5 |
| ADR-0047.R2.N6 | ref: ADR-0047.R2.N6 |
| ADR-0047.R2.N7 | ref: ADR-0047.R2.N7 |
| ADR-0047.R3.N2 | ref: ADR-0047.R3.N2 |
| ADR-0047.R8 | ref: ADR-0047.R8 |
| ADR-0047.R8.N1 | ref: ADR-0047.R8.N1 |
| ADR-0047.R8.N2 | ref: ADR-0047.R8.N2 |
| ADR-0047.R16 | ref: ADR-0047.R16 |
| ADR-0047.R16.N1 | ref: ADR-0047.R16.N1 |
| ADR-0049.R25 | ref: ADR-0049.R25 |
| ADR-0049.R25.N1 | ref: ADR-0049.R25.N1 |
| ADR-0049.R25.N2 | ref: ADR-0049.R25.N2 |
| ADR-0049.R28 | ref: ADR-0049.R28 |
| ADR-0049.R28.N1 | ref: ADR-0049.R28.N1 |
| ADR-0049.R29 | ref: ADR-0049.R29 |
| ADR-0052.D0 | ref: ADR-0052.D0 |
| ADR-0052.R3 | ref: ADR-0052.R3 |
| ADR-0052.R18 | ref: ADR-0052.R18 |
| ADR-0052.R18.N1 | ref: ADR-0052.R18.N1 |
| ADR-0052.R18.N2 | ref: ADR-0052.R18.N2 |
| ADR-0052.R22 | ref: ADR-0052.R22 |
| ADR-0052.R27 | ref: ADR-0052.R27 |
| ADR-0052.R28 | ref: ADR-0052.R28 |
| ADR-0052.R28.N1 | ref: ADR-0052.R28.N1 |
| ADR-0052.R28.N2 | ref: ADR-0052.R28.N2 |
| ADR-0052.R28.N3 | ref: ADR-0052.R28.N3 |
| ADR-0052.R35 | ref: ADR-0052.R35 |
| ADR-0053.R8 | R432-R437 |
| ADR-0053.R8.N1 | R438, R439 |
| ADR-0054.R2 | ref: ADR-0054.R2 |
| ADR-0054.R2.N1 | ref: ADR-0054.R2.N1 |
| ADR-0054.R11.N4 | ref: ADR-0054.R11.N4 |
| ADR-0054.R11.N6 | ref: ADR-0054.R11.N6 |
| ADR-0054.R11.N7 | ref: ADR-0054.R11.N7 |
| ADR-0054.R14 | R440-R442 |
| ADR-0054.R14.N1 | R443 |
| ADR-0054.R21 | ref: ADR-0054.R21 |
| ADR-0054.R21.N1 | ref: ADR-0054.R21.N1 |
| ADR-0055.R1 | ref: ADR-0055.R1 |
| ADR-0055.R5.N2 | ref: ADR-0055.R5.N2 |
| ADR-0055.R7 | ref: ADR-0055.R7 |
| ADR-0055.R7.N1 | ref: ADR-0055.R7.N1 |
| ADR-0055.R7.N2 | ref: ADR-0055.R7.N2 |
| ADR-0055.R7.N3 | ref: ADR-0055.R7.N3 |
| ADR-0055.R7.N4 | ref: ADR-0055.R7.N4 |
| ADR-0055.R9 | R444 |
| ADR-0056.R10 | ref: ADR-0056.R10 |
| ADR-0056.R10.N1 | ref: ADR-0056.R10.N1 |
| ADR-0058.R10 | ref: ADR-0058.R10 |
| ADR-0061.R7 | ref: ADR-0061.R7 |
| ADR-0061.R9 | R445-R447 |
| ADR-0061.R20 | ref: ADR-0061.R20 |
| ADR-0062.R9 | ref: ADR-0062.R9 |
| ADR-0062.R9.N1 | ref: ADR-0062.R9.N1 |
| ADR-0062.R14 | ref: ADR-0062.R14 |
| ADR-0062.R19 | ref: ADR-0062.R19 |
| ADR-0063.R24 | ref: ADR-0063.R24 |
| ADR-0065.R22 | ref: ADR-0065.R22 |
| ADR-0066.R11 | ref: ADR-0066.R11 |
| ADR-0069.R4 | ref: ADR-0069.R4 |
| ADR-0074.R4 | ref: ADR-0074.R4 |
| ADR-0074.R4.N1 | ref: ADR-0074.R4.N1 |
| ADR-0074.R16 | ref: ADR-0074.R16 |
| ADR-0074.R19 | ref: ADR-0074.R19 |
| ADR-0075.R6 | ref: ADR-0075.R6 |
| ADR-0075.R10.N1 | ref: ADR-0075.R10.N1 |
| ADR-0075.R11 | ref: ADR-0075.R11 |
| ADR-0076.R3 | ref: ADR-0076.R3 |
| ADR-0076.R3.N1 | ref: ADR-0076.R3.N1 |
| ADR-0077.R21 | ref: ADR-0077.R21 |
| ADR-0079.R1 | ref: ADR-0079.R1 |
| ADR-0079.R6 | ref: ADR-0079.R6 |
| ADR-0079.R7.N2 | ref: ADR-0079.R7.N2 |
| ADR-0079.R7.N3 | ref: ADR-0079.R7.N3 |
