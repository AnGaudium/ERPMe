Module: documents    Chunk: 1 of 3    Source ADRs: ADR-0009
Build step(s): 1    Generated from index: 30d5706    Compiled by: Claude Fable 5.2, 2026-11-21

# Compiled spec: `documents`, chunk 1 (shared document row, type registry, states, versions, approval binding, posting, numbering, reversal)

## Purpose

`documents` is a layer 2 (platform) module: document lifecycle, versions and numbering. It owns the shared `document` row, the document type registry, the state machines of posting and non-posting types, `document_version`, `approval`, the numbering tables and the reversal rules. This chunk states the law of ADR-0009 rules 1 to 22. Correction documents, line identity, change orders, the `issuing` state, proposals, taint, parties, reasons and the other document law are in the other chunks. `documents` does not own the typed headers and lines of a document type, the journal, stock, periods or the policy engine; the modules that own them plug into this lifecycle.

## Entities and tables

DDL: `docs/design/DS-05-platform.sql`.

| Table | Meaning | Key | Parent | Owner |
| --- | --- | --- | --- | --- |
| `document` | The shared row of every document: type, company, state, version, number (R1) | `id`; unique (`company_id`, `id`), (`company_id`, `id`, `document_type`), (`company_id`, `document_type`, `number`), (`reversal_of_id`) | `company` | documents |
| `document_version` | One immutable version of a document's content with its hash (R17) | `id`; unique (`document_id`, `version`) | `document` | documents |
| `approval` | One immutable approval decision at a stage, bound to a version (R24) | `id` | `document_version`, `policy_decision` | documents |
| `numbering_configuration` | A company's prefix, per-branch choice and format for a document type (R31); checked for barcoded types (R33, `ADR-0061.R9`). The DDL marks the table interim: ADR-0009 does not state it as a table | `id`; unique (`company_id`, `document_type`) | `company` | documents |
| `numbering_series` | The gapless counter of a document type, fiscal year and branch (R31) | `id`; unique `NULLS NOT DISTINCT` (`company_id`, `document_type`, `fiscal_year_id`, `branch_id`) | `company`, `fiscal_year`, `branch` | documents |

Named here, row in another chunk of this module: `taint_clearance`.

Reads: `company`, `branch`, `partner`, `user_account`, `fiscal_year`, `policy_decision`, `agent_run`, `reason`, `demand_supply_line`, `outbound_message`, `data_subject_request`.

## Commands and queries

The registry generates the commands of a document type from the verb list (R5); `<Type>` is the registered type. Levels are those of the verb in `authorization-verb-levels.csv`; the area is the type's own `document_type` leaf of `authorization-areas.csv` where the catalog holds one. Every command that changes a document carries `version` and can return `version_conflict` (R22) and `invalid_state_transition` (R10).

| Name | Actor / authorization | Input | Effect | Events | Error codes |
| --- | --- | --- | --- | --- | --- |
| `Create<Type>` | level `edit` | header fields and lines; `posting_date` for posting types | inserts the document as `draft`, writes version 1 (R9, R17) | `<Type><event form>` (R44) | not stated |
| `Update<Type>` | level `edit` | `version` (`pending_version` on a pending change), new content with the full list of lines | writes the next version, returns the document to `draft`, voids submission and approval (R17); matches lines by `line_number` (`ADR-0028.R1`); on an `approved` document with `is_change_order_allowed` writes or replaces the pending version instead (`ADR-0028.R4`) | `<Type><event form>` (R44) | `version_conflict`, `invalid_state_transition`, `document_line_referenced`, `referenced_line_immutable`, `quantity_below_fulfilled` (`ADR-0028.R3`), `document_referenced` (`ADR-0028.R4`, step 3 interim), `change_pending` (`ADR-0028.R4`) |
| `Delete<Type>` | level `edit` | `version` | deletes the row of a `draft` never submitted and not referenced (R9, R14) | `<Type><event form>` (R44) | `document_referenced`, `version_conflict`, `invalid_state_transition` |
| `Submit<Type>` | level `edit` | `version` | policy point; `draft` to `pending_approval` or `approved` (R9, R23) | `<Type><event form>` (R44) | `policy_denied`, `approval_hold_not_allowed`, `version_conflict`, `invalid_state_transition` |
| `Approve<Type>` | level `approve` (the role's approval flag) | `version`, optional `delegated_from_user_id` | `pending_approval` to `approved`; writes an `approval` row (R9, R24) | `<Type><event form>` (R44) | `approval_hold_not_allowed`, `version_conflict`, `invalid_state_transition` |
| `Reject<Type>` | level `approve` (the role's approval flag) | `version`, `reason`, optional `delegated_from_user_id` | `pending_approval` to `draft`; writes an `approval` row (R9, R24) | `<Type><event form>` (R44) | `approval_hold_not_allowed`, `version_conflict`, `invalid_state_transition` |
| `Cancel<Type>` | level `edit` | `version` | `draft`, `pending_approval` or `approved` to `canceled` (R9, R14) | `<Type><event form>` (R44) | `document_referenced`, `version_conflict`, `invalid_state_transition` |
| `Post<Type>` (posting types) | level `post` | `version`, `posting_date` | period checks, number, journal entry or material document, `posted`, in one transaction (R27) | `<Type>Posted` | `approval_required`, `posting_date_mismatch`, `approval_context_changed` (`ADR-0028.R14`), `attachment_not_available` (`ADR-0038.R14`), `version_conflict`, `invalid_state_transition` |
| `Reverse<Type>` (reversible posting types) | `human_only`; level `full` | the original's `version`, `posting_date` | creates and posts the reversal document, sets the original to `reversed` (R36) | `<Type>Posted` for the reversal document, `<Type>Reversed` for the original | `document_referenced`, `reversal_not_latest`, `version_conflict`, `invalid_state_transition` |
| `Close<Type>` (non-posting types) | level `post` | `version` | `approved` to `closed` (R12) | `<Type><event form>` (R44), for example `SalesOrderClosed` | `version_conflict`, `invalid_state_transition` |

Per-type commands named by R5 and stated in other chunks or modules: `Issue<Type>`, `Reopen<Type>`, `Recall<Type>`, `Complete<Type>Posting`, `CancelChange<Type>`, `RecordEInvoiceOutcome` (`tax`; spelled `Record<Type>EInvoiceOutcome` in `ADR-0028.R7`), `SendOutboundMessage`, `RecordOutboundMessageOutcome`. Verb levels of the catalog for them: `Issue` `post`, `Reopen` `post`, `Recall` `edit`, `Complete` `post`, `Record` `post`, `Send` `post`.

Numbering configuration is changed under the authorization area `company_setting` (module `registry`: company settings and numbering configuration); the sources name no command for it. Error codes bound to no named command: `barcode_prefix_reserved`, `numbering_barcode_invalid` (R33), `concurrent_update` (R32).

Not registered commands: the numbering lock helper (R32); the database triggers of R28. The query `ListAllowedCommand` (`ADR-0040.R8`) reads the registry's `allowed_states` (R10).

## Rules

### Document row and typed tables

R1. Every document has one row in `document` with `id`, `company_id`, `document_type`, `state`, `version` (the version in force), `number` (null until numbered), `branch_id` (nullable), `reversal_of_id` (nullable), `correction_of_id` (nullable, set at Create, never changed; `ADR-0009.R23`), `partner_id` and `document_date` (nullable, equal to the typed header), `owner_employee_id` (an employee partner) and `created_by_user_id` (for owner scope, `ADR-0054.R14`), `recorded_at`, and a unique key on (`company_id`, `id`). Agent-drafted documents also carry `origin_work_item_id`, `workflow_step` and `draft_ordinal`, filled together or not at all (`ADR-0030.R11`). The row also holds `is_barcoded` (R33), `pending_version` and `change_state` (`none`, `drafting`, `pending_approval`; `ADR-0028.R4`), `posted_at` (R27), `closed_reason` (`fulfilled`, `manual`; R13) and `canceled_reason_id`, `canceled_reason_kind` and `canceled_note` (`ADR-0074.R13`, `ADR-0074.R14`). A row never names both `reversal_of_id` and `correction_of_id`, and neither names the row itself.
Source: ADR-0009.R1, .N1

R2. A document's typed header table (for example `goods_receipt`) has the same `id` as primary key and foreign key to `document`. Its lines are in `<header>_line` (`ADR-0004.R10`), each with a `line_number` unique within the document. Line numbers are line identity; references and the immutability of referenced lines are `ADR-0028.R1`, `ADR-0028.R2` and `ADR-0028.R3`. Versions, approvals, numbering, reversals, work items and audit records refer to `document.id`.
Source: ADR-0009.R1

R3. A typed header may carry a free-text `note` and, on some types, `custom_values` and the party columns of `ADR-0074.R1` (`ADR-0074.R8`, `ADR-0074.R16`). The stock documents of ADR-0075 are typed headers in this pattern.
Source: ADR-0009.R1.N2

### Type registry and generated commands

R4. Each document type is registered once with: `document_type` (a glossary noun, `snake_case`), `is_posting` (it posts to the journal or stock), `is_approval_hold_allowed` (R25), `is_reversible` (R38, default false), its numbering (R31), `is_change_order_allowed` and `is_e_invoice_capable` (`ADR-0028.R4`, `ADR-0028.R6`), `is_printable`, its `owner_field` (`ADR-0054.R14`), and `partner_field` and `is_on_partner_timeline` (`ADR-0052.R18`). A printable type has the optional header field `print_language`, part of its content (`ADR-0049.R25`, `ADR-0049.R27`).
Source: ADR-0009.R1, ADR-0009.R2, .N1, .N2

R5. The registry generates a type's commands from the verb list: `Create`, `Update`, `Delete`, `Submit`, `Approve`, `Reject`, `Cancel`; `Post` and, if reversible, `Reverse` for posting types; `Close` for non-posting types. `Submit`, `Approve` and `Reject` are not generated for types with `is_approval_hold_allowed: false`. Per-type commands added by ADR-0028: `Issue<Type>`, `Reopen<Type>`, `Recall<Type>`, `Complete<Type>Posting`, `CancelChange<Type>`; `RecordEInvoiceOutcome` is one command in `tax`. The generated `Approve<Type>` and `Reject<Type>` take an optional payload field `delegated_from_user_id`, the delegator a substitute acts for (`ADR-0055.R7`).
Source: ADR-0009.R2, .N3

R6. `is_approval_hold_allowed` also takes the value `regime`, for `sales_invoice`, `sales_return`, `credit_note` and `debit_note`. `Submit`, `Approve` and `Reject` are generated for those types and rejected at run time with `approval_hold_not_allowed` while the regime setting `documents.issuance_without_delay` is true for the document's date (`ADR-0053.R8`).
Source: ADR-0009.R2

R7. `outbound_message` registers no `Close`: it closes only by the delivery outcome `sent`. Its per-type commands are `SendOutboundMessage` and `RecordOutboundMessageOutcome`. `Update` returns an approved message to draft, so it has no `Reopen` (`ADR-0052.R27`).
Source: ADR-0009.R2

R8. Which document types exist and their fields are decided by the design items that own them (DS-06, DS-09, DS-22, DS-25). Documents created by system jobs (costing adjustments, FX revaluation, closing entries; DS-09, DS-10, DS-12) are ordinary documents, created and posted through the same commands by actor `system` (`ADR-0008.R2`). Outside this lifecycle law: attachments (module `attachments`, ADR-0027), the supplier's own number on incoming documents (DS-22, DS-24), field permissions and personal data inside version content (DS-15), and documents between companies (after Phase 1). `open_item_matching` and the open-item rules are ADR-0026.
Source: ADR-0009.R3

### States and transitions

R9. States are stored in `document.state` (`ADR-0004.R14`); the column allows `draft`, `pending_approval`, `approved`, `issuing`, `sending`, `posted`, `reversed`, `closed`, `canceled`. Transitions of posting types:
- none to `draft`: `Create<Type>`;
- `draft`, `pending_approval`, `approved` to `draft` (new version): `Update<Type>`;
- `draft` to `pending_approval` or `approved`: `Submit<Type>` (R23);
- `pending_approval` to `approved`: `Approve<Type>`; `pending_approval` to `draft`: `Reject<Type>`;
- `draft` (policy allows without approval) or `approved` to `posted`: `Post<Type>`;
- `posted` to `reversed`: `Reverse<Type>` (posts the reversal document);
- `draft`, `pending_approval`, `approved` to `canceled`: `Cancel<Type>`;
- `draft` (never submitted, not referenced) to row deleted: `Delete<Type>`.
Source: ADR-0009.R4

R10. E-invoiced types add `issuing` (`draft` to `issuing`, then `posted` or back to `draft`); orders with change orders add `change_state`; an approved document may be resubmitted (`approved` to `pending_approval`) after `approval_context_changed` (`ADR-0028.R4`, `ADR-0028.R6`). Any other transition is rejected with `invalid_state_transition`, naming the current state and the commands allowed from it. `posted`, `reversed` and `canceled` are final. `issuing` is not final; the commands allowed in it are those of `ADR-0028.R6`. The allowed commands per state come from the registry's `allowed_states`, which `ListAllowedCommand` reads too (`ADR-0040.R8`).
Source: ADR-0009.R4, ADR-0009.R5

R11. Non-posting types (orders, quotations, requests) use the states `draft`, `pending_approval`, `approved`, `closed` and `canceled`, with the same `Create`, `Update`, `Submit`, `Approve`, `Reject`, `Cancel` and `Delete` rules as R9. An order is in force only once `approved` (by an approver, or directly through `Submit` when the policy needs no approval), so a live order is never a draft.
Source: ADR-0009.R6, ADR-0009.D0

R12. `Close` moves an `approved` non-posting document to `closed`: it ends further activity on a document that has had some; `Cancel` ends one that has had none. `outbound_message` adds the non-final state `sending` between `approved` and `closed`, frozen like `issuing` (`ADR-0052.R27`).
Source: ADR-0009.R6

R13. Sales and purchase orders, requests and quotations close automatically (`closed_reason` `fulfilled`) when every line is done by quantity, net of returns and quantity credits (`ADR-0047.R2`). Updating an approved order with change orders follows `ADR-0028.R4` and `ADR-0028.R5`.
Source: ADR-0009.R6

R14. `Delete` and `Cancel` are rejected with `document_referenced` when another document refers to the document (for example a delivery to an order). References count when they come from documents that are not canceled or reversed (`ADR-0047.R2`).
Source: ADR-0009.R7

R15. Fulfilment progress (quantities invoiced or fulfilled) is computed from the referring documents, never stored as a state. The open delivery or receipt quantity of a stock line is stored once, in `demand_supply_line` (`ADR-0031.R5`). Documents in `issuing` count as fulfilling (`ADR-0028.R9`).
Source: ADR-0009.R7

R16. When and by which date a non-posting document gets its number is an open question for the author. Interim, flagged rule: it is numbered when it first becomes `approved`, from the series of the fiscal year that contains its `document_date`, and keeps its number if canceled.
Source: ADR-0009.R8

### Versions and concurrency

R17. `Create` writes version 1. Every `Update` writes the next version and returns the document to `draft`, voiding any submission or approval, except the `Update` of an approved document with change orders, which writes a pending version (R20). Each version is a row in `document_version` (`id`, `company_id`, `document_id`, `version`, `content`, `version_hash`, `recorded_at`, `actor_kind` (`human`, `agent`, `integration`, `system`), `actor_id`, `on_behalf_of_id`, `agent_run_id`, `origin_agent_run_id` (`ADR-0017.R16`), `is_tainted`, `derived_from_version_id`, `erased_at`), unique on (`document_id`, `version`). In a version written by an agent (`actor_kind` `agent`), `actor_id` is the agent run's ID, equal to `agent_run_id`; the agent type is read through the run. It is the actor `id` of the actor context of `ADR-0008.R8`, so the audit records and events of the same command carry it too. `agent_run_id` is filled exactly when `actor_kind` is `agent`.
Source: ADR-0009.R9, .N1

R18. `content` is the canonical JSON (forms of `ADR-0008.R12`) of the header fields and the lines ordered by `line_number`, without the IDs of the document and its lines, `state`, `version`, `number` and system timestamps. `version_hash` is its SHA-256. The typed rows are authoritative; `INV-10` checks that the current version's `content` equals the content computed from them; for a document with a pending change the current version is the version in force (`ADR-0028.R4`).
Source: ADR-0009.R9

R19. For posting types `posting_date` is a document field set by `Create` or `Update` and is part of the content, so changing it voids an approval. `Post` carries `posting_date` explicitly (`ADR-0007.R8`), and it must equal the document's field; otherwise the command is rejected with `posting_date_mismatch`, so the approved content stays bound.
Source: ADR-0009.R9

R20. A change order keeps the version in force and writes a pending version (`ADR-0028.R4`). A version carries an immutable `is_tainted` and a nullable `derived_from_version_id`; a human clears taint with an immutable `taint_clearance` row (`ADR-0029.R8`, `ADR-0029.R9`).
Source: ADR-0009.R9

R21. When a subject's retention period ends, the destruction path clears the catalog keys of `content` and sets the version's nullable `erased_at`. `version_hash` stays as stored and is not compared with the content of such a version (`INV-10` skips versions with `erased_at` set). No rule binds an approval to the hash itself: an approval names its version by `document_version_id` (R24), so an approval of an erased version stays valid, and the stored hash remains the evidence of what was approved (`ADR-0079.R6`).
Source: ADR-0009.R9.N2

R22. Every command that changes a document (`Update`, `Submit`, `Approve`, `Reject`, `Post`, `Close`, `Cancel`, `Delete`, `Reverse`) carries `version`, the version the client last read, and locks the `document` row first. If `version` is not current, the command is rejected with `version_conflict`, naming the current version. Commands on a pending change carry `pending_version` (`ADR-0028.R4`).
Source: ADR-0009.R10

### Policy and approval binding

R23. Policy is evaluated once per command at the policy points of `ADR-0029.R6` (`Submit`, `Post` from `draft`, `Issue`, and `Post` of an approved document under the conditions stated there), and its outcome is stored in a `policy_decision` row bound to the current `document_version_id`; the decision fields are `ADR-0029.R7`. At `Submit`: allow makes the document `approved` without an approver; approval required makes it `pending_approval`; deny rejects the command with `policy_denied`; human only acts as allow, but only a human may post the document. `Post` from `draft` is rejected with `approval_required` if an approval is needed. `Post` of an `approved` document uses what is bound to its current version (an `approved` approval row, or an allow or human-only `policy_decision`). Approval context is `ADR-0028.R14`; evaluation, floors and procedures are `ADR-0043.R5` to `ADR-0043.R10`; floors 3 to 6 are also checked on `Post` of an approved document (`ADR-0043.R9`). How the policy applies to `Reverse` is R36. Who may approve, including segregation of duties, is DS-15 and DS-28.
Source: ADR-0009.R11, ADR-0029.R6

R24. An approval is an immutable `approval` row: `document_id`, `document_version_id`, `policy_decision_id` (the decision it satisfies, `ADR-0028.R14`), `decision` (`approved` or `rejected`), `reason` (required, not empty), `actor_kind` (always `human`, `ADR-0017.R15`), `actor_id`, `on_behalf_of_id`, `decided_at`, and `reject_reason_id` (only on a `rejected` decision) with `reject_reason_kind`, which is always `reject` (`ADR-0074.R13`, `ADR-0074.R14`). Approvals run through the stages of the document's approval pool: the row also has `approval_stage_id` and `approval_pool_id` (filled together or not at all), `delegated_from_user_id` (never the actor) and `is_escalated` (never together with a delegation) (`ADR-0055.R7`, `ADR-0055.R8`, `ADR-0055.R9`).
Source: ADR-0009.R11, .N1, ADR-0029.R6

R25. A document type whose issuance has a legal deadline (for example a sales invoice issued as an e-invoice) is registered with `is_approval_hold_allowed: false`, because the approval queue must not delay issuance. What happens when the policy requires approval for such a document is an open question for the author. Interim, flagged rule: the outcome is treated as human only, so a human posts it directly and no agent can; the stored outcome is `human_only` (`ADR-0043.R10`). Which types carry the flag is set by DS-22 and DS-24. For e-invoiced types the policy is asked at `Issue`, and under this interim the completion `Post<Type>` on acceptance runs as `system` on behalf of the issuer (`ADR-0028.R7`, `ADR-0027.R12`).
Source: ADR-0009.R12

R26. For `sales_invoice`, `sales_return`, `credit_note` and `debit_note` the flag is derived from the regime setting `documents.issuance_without_delay` (true means no approval hold; core default false). A localization package may seed the setting; its value is flagged package content (`unverified` in the source) and is not core law. The legal deadline is the regime's, not the core's (`ADR-0053.R8`).
Source: ADR-0009.R12

### Posting and immutability

R27. `Post<Type>` runs the period checks (DS-12), assigns the number, writes the journal entry, the material document or both (DS-06, DS-09), and sets `state = posted` and `posted_at`, in one transaction. `posted_at` is filled exactly in the states `posted` and `reversed`. E-invoiced types post by a consumer on acceptance, with the plan frozen at `Issue` (`ADR-0028.R7`).
Source: ADR-0009.R13

R28. Database triggers make documents in a final state (`posted`, `reversed`, `canceled`, `closed`) immutable: every `INSERT`, `UPDATE` and `DELETE` on their header and line rows, and every change to their `document` row, is rejected, except `Reverse` changing `document.state` from `posted` to `reversed` and nothing else. The same immutability applies in `issuing` (`ADR-0028.R6`) and in `sending` of outbound messages. `document_version`, `policy_decision` and `approval` rows are never updated or deleted. A reversal document, like every document, is inserted as `draft` and posted in the same transaction, so the trigger never blocks it. DS-06 adds the same protection to journal and material document rows.
Source: ADR-0009.R14

R29. Data that arrives after posting (e-invoice form, symbol and number from DS-24) is stored in its own tables that refer to the document. The personal text of `outbound_message` and `data_subject_request` lives in `crm` content tables that header and version reference by hash, and delivery attempts are late data, so erasure never changes a final document (`ADR-0052.R24`, `ADR-0052.R25`, `ADR-0052.R27`, `ADR-0052.R28`).
Source: ADR-0009.R14

R30. One exception to R28, for the destruction path only: under the erasure marker of a committed `EraseDataSubject` or `DestroyRetainedPersonalData`, the triggers allow an update of a final document's header and lines, and of `document_version`, that changes only the columns and keys the personal data catalog names for that table (and sets `document_version.erased_at`). Every other change, by every other command, is refused. The trigger DDL belongs to the document DDL (`ADR-0079.R6`, `ADR-0079.R7`).
Source: ADR-0009.R14.N1

### Numbering

R31. Numbers come from `numbering_series` rows keyed by (`company_id`, `document_type`, `fiscal_year_id`, `branch_id`), unique with `NULLS NOT DISTINCT`, with `prefix`, `next_value` (at least 1) and `format`. A company configures, per document type, a prefix, whether series are per branch, and a format: one `numbering_configuration` row per (`company_id`, `document_type`) with `prefix`, `is_per_branch` (default false) and `format` (it must hold a `{counter:N}` placeholder). The series row for a fiscal year is created on first use from that configuration. Format placeholders are `{prefix}`, `{branch_code}`, `{fiscal_year_code}` and `{counter:N}` (zero-padded to at least N digits, never wrapping). `document` has a unique constraint on (`company_id`, `document_type`, `number`).
Source: ADR-0009.R15

R32. The counter is read and incremented only through the numbering lock helper (`ADR-0008.R10`), inside the transaction that numbers the document, so a rolled-back posting leaves no gap and postings of one series are serialized (`INV-07`). Lock helpers take stock locks before numbering locks; a deadlock between batches is returned as the retryable `concurrent_update`.
Source: ADR-0009.R15

R33. A printable document type may be registered `is_barcoded` (Phase 1: purchase orders, goods receipts, sales orders, deliveries, transfer orders, production orders). Its number format must start with `{prefix}` and a separator (`/`, `-` or `.`), and that string (for example `PO/`) is reserved: no other barcoded type's reserved string may start it or be started by it, and no barcode of another type may start with it (`barcode_prefix_reserved`). Creating or changing such a configuration, or a branch or fiscal year code it uses, checks that every number it can produce is an internal code of at most 48 characters (`numbering_barcode_invalid`). `document.is_barcoded` is set at Create from the type's registry flag and never changes, and the number is registered in the barcode registry when it is set (`ADR-0061.R9`).
Source: ADR-0009.R15.N1

R34. The default format is `{prefix}/{fiscal_year_code}/{counter:6}`, or `{prefix}/{branch_code}/{fiscal_year_code}/{counter:6}` for branch series. Numbers are assigned at posting, in posting order. Reversals use their own type's series.
Source: ADR-0009.R16, .N1

R35. Drafts are referred to by `id`. Numbers of e-invoices are assigned by the e-invoice process (DS-24) and stored by it in its own tables (R29).
Source: ADR-0009.R17

### Reversal

R36. `Reverse<Type>` is `human_only` (`ADR-0008.R2`). It carries the original's `version` and an explicit `posting_date`, creates a reversal document of the same type and company with `reversal_of_id` pointing to the original (unique, so a document is reversed at most once, in full), posts it with its own number through the same period checks as any document, and sets the original to `reversed`, in one transaction. It emits `<Type>Posted` for the reversal document and `<Type>Reversed` for the original. It binds to the original's last version. Reversals of posted documents have no policy step (`ADR-0043.R9`).
Source: ADR-0009.R18, ADR-0009.R11, ADR-0029.R6

R37. Preconditions of `Reverse` when later documents depend on the original (a matched invoice, an allocated payment, consumed stock) are set by DS-09, DS-22 and DS-25; for documents whose open items were settled they are `ADR-0026.R11`. For goods receipts, service receipts, stock returns and supplier documents with purchase order lines, `Reverse` is also allowed only while the document's GR/IR postings are the latest of their side on each line (`reversal_not_latest`; `ADR-0047.R13`).
Source: ADR-0009.R18

R38. `is_reversible` is set per document type (default false) by the design item that owns the type, within R39 and R40. A posted document is corrected by correction documents (`ADR-0009.R23`); only internal document types, which no outside party holds, can be reversed. For every reversible type, `Reverse` is rejected with `document_referenced` while a document that is not reversed or canceled refers to the document.
Source: ADR-0009.R19

R39. Reversible internal types: manual journal entries and stock documents between the company's own warehouses (transfers, stock counts); `production_issue`, `operation_confirmation` and `production_receipt` (`ADR-0034.R11`, `ADR-0034.R12`, `ADR-0034.R13`); payments, `advance_settlement` and the internal `currency_exchange`, `partner_netting`, `write_off`, `cash_count_adjustment`, `provision_entry` and `prepaid_amortization`, as `ADR-0048.R1` and `ADR-0048.R16` say. A transfer accompanied by an internal transport e-document cannot be reversed until that legal point is answered (open question); DS-24 adds this as a `Reverse` precondition. For documents created by system jobs (costing adjustments, FX revaluation, closing entries), reversibility is decided by DS-09, DS-10 and DS-12.
Source: ADR-0009.R19

R40. Documents the company records from or issues to an outside party (goods receipts, deliveries, payments, purchase invoices): whether they may be reversed while nothing refers to them or only corrected is an open question for the author. Interim, flagged rule: they are reversible while no document that is not reversed or canceled refers to them. `service_receipt` follows the flagged interim of `goods_receipt`: reversible while no invoice refers to it (`ADR-0037.R5`). Sales invoices and every document issued as an e-invoice are never reversible; they are corrected by adjustment or replacement invoices, and e-invoiced types are posted only on acceptance (`ADR-0028.R6`). This "never reversible" rests on the author's core decision of 2026-11-14 on correction documents, not on a country's law; the adjustment and replacement invoice forms belong to the localization package and the e-invoice add-on (DS-24) (`ADR-0053.R14`).
Source: ADR-0009.R19, .N1

R41. Whether the reversal posts negative amounts (storno) or swapped debit and credit, and which posting date it defaults to when the original period is locked, are accounting rules: configuration of the localization package, flagged until the author decides. The core provides both reversal methods.
Source: ADR-0009.R20, .N1

R42. A reversed material document takes the original line's value; this is a core rule, not localization configuration (`ADR-0020.R7`). It is the value the original line carries when the reversal posts, revaluations included, and in period-end costing the reversal follows the original. This reading is the chief architect's interim translation of the author's rule of 2026-11-21: a reversal is the `Reverse` of one document, and a document that another document refers to cannot be reversed (R38), so the reversal always refers to its one original. The value of reversals of goods issues and transfers is unverified against SAP; the negative-stock and value checks of `ADR-0020.R10` and `ADR-0020.R13` still apply to a reversal.
Source: ADR-0009.R20.N1

R43. A reversal document cannot itself be reversed; to restore a transaction, a new document is posted.
Source: ADR-0009.R21, .N1

### Events

R44. Every transition emits an event `<Type><event form>` through the outbox, for example `GoodsReceiptPosted` and `SalesOrderClosed` (`ADR-0004.R22`, DS-13).
Source: ADR-0009.R22

## Invariants

Statements are those of `invariants.csv`. A row stands in the chunk that holds the first rule its catalog source names.

| Invariant | Name | Check point | Statement | Protects |
| --- | --- | --- | --- | --- |
| `INV-07` | `numbers_without_gaps` | day | Per `numbering_series`, the counters of all documents that hold a number, in any state, are exactly 1 to `next_value` minus 1, each once. Flagged: ADR-0009 rule 8, numbering of non-posting documents at approval. | R16, R28, R31, R32, R36 |
| `INV-10` | `version_content_matches_rows` | day | The current document version's `content` and `version_hash` equal those computed from the typed rows; versions with `erased_at` set are skipped. | R18, R21 |
| `INV-82` | `required_approval_present` | day | For every posted document whose policy decision on the posted version requires a rank, every stage of the approval plan of the decision its Post used (for an e-invoiced document, the decision of its Issue) has at least its required number of counted approved approvals on that version within the round that Post or Issue ended (`ADR-0055.R8`, `ADR-0055.R18`); documents whose outcome is `human_only` are excluded. Flagged: ADR-0009 rule 12, approval required treated as human-only posting. | R23, R24, R25 |

## Settings

None: the regime setting `documents.issuance_without_delay` named by R6 and R26 has no row in `settings.csv`; chunk 3 states it once (`ADR-0053.R8`).

## Conflicts

CONFLICT ADR-0009.R1: the DDL of `document` holds columns the rule does not list (`is_barcoded`, `pending_version`, `change_state`, `posted_at`, `closed_reason`, the canceled reason columns), added by ADR-0061.R9, ADR-0028.R4, ADR-0047.R2, ADR-0074.R13 and ADR-0074.R14; R1 states the current columns.
CONFLICT ADR-0009.R2: the rule's closing sentences citing ADR-0053.R8 add the value `regime` to `is_approval_hold_allowed`, so the flag is not a plain boolean and the verbs are generated for those types (R6); the sentences citing ADR-0052.R27 except `outbound_message` from `Close` (R7).
CONFLICT ADR-0009.R6: ADR-0028.R4 and ADR-0028.R5 govern the update of an approved order and ADR-0047.R2 the automatic close, so the delegation of both points to DS-22 is not restated (R13).
CONFLICT ADR-0009.R7: ADR-0031.R5 stores the open delivery or receipt quantity of a stock line in `demand_supply_line`, so only invoiced and fulfilled progress stay computed (R15); ADR-0047.R2 decides which references count, so "decided by DS-22" is not restated (R14).
CONFLICT ADR-0009.R9.N2: the note governs the hash comparison after erasure: `version_hash` of a version with `erased_at` set is kept and not compared with its content, stated in R21 and in `INV-10`.
CONFLICT ADR-0009.R11: ADR-0029.R6 replaces the rule's separate statement of where policy is asked, so R23 names the policy points by reference and keeps the effects of the outcomes; the DDL of `approval` adds `document_id`, `policy_decision_id` (ADR-0028.R14), the human-only `actor_kind` (ADR-0017.R15) and the reject reason columns (ADR-0074.R13), stated in R24; the sentence that DS-28 decides the policy for `Reverse` yields to ADR-0043.R9 (R36).
CONFLICT ADR-0009.R12: the rule's closing sentences citing ADR-0053.R8 derive the flag of the named sales types from the regime setting `documents.issuance_without_delay` (R26); the interim mark on the human-only outcome is kept, because ADR-0043.R10 keeps it as interim and `INV-82` still flags it; ADR-0028.R7 allows the completion posting of an e-invoiced document by `system` on behalf of the issuer under that interim, so "no agent can" posts it holds, but posting is not by a human alone (R25).
CONFLICT ADR-0009.R15: the DDL creates the table `numbering_configuration` for what the rule calls "a company configures"; R31 states its columns from the DDL, which marks the table interim.
CONFLICT ADR-0009.R16: ADR-0009.R16.N1 confirms the interim format, posting order and series of reversals, so the open-question and interim marks are dropped (R34).
CONFLICT ADR-0009.R20: ADR-0009.R20.N1 makes the value of a reversed material document a core rule (R42); only the reversal method and the default posting date stay flagged localization configuration (R41).
CONFLICT ADR-0009.R20.N1: the note governs over the rule's list of localization points for the value of a reversed material document; its SAP comparison is dropped as rationale and its interim mark is kept in R42.
CONFLICT ADR-0009.R21: ADR-0009.R21.N1 confirms that a reversal document is never reversed, so the interim and open-question marks are dropped (R43).
CONFLICT ADR-0009.R21.N1: the confirming note governs and words the remedy as a new document that is posted; R43 states the note's wording.

## Trace

| Source | Where |
| --- | --- |
| ADR-0009.D0 | R11, Purpose |
| ADR-0009.R1 | R1, R2, R4 |
| ADR-0009.R1.N1 | R1 |
| ADR-0009.R1.N2 | R3 |
| ADR-0009.R2 | R4, R5, R6, R7 |
| ADR-0009.R2.N1 | R4 |
| ADR-0009.R2.N2 | R4 |
| ADR-0009.R2.N3 | R5 |
| ADR-0009.R3 | R8 |
| ADR-0009.R4 | R9, R10 |
| ADR-0009.R5 | R10 |
| ADR-0009.R6 | R11, R12, R13 |
| ADR-0009.R7 | R14, R15 |
| ADR-0009.R8 | R16 |
| ADR-0009.R9 | R17, R18, R19, R20 |
| ADR-0009.R9.N1 | R17 |
| ADR-0009.R9.N2 | R21 |
| ADR-0009.R10 | R22 |
| ADR-0009.R11 | R23, R24, R36 |
| ADR-0009.R11.N1 | R24 |
| ADR-0009.R12 | R25, R26 |
| ADR-0009.R13 | R27 |
| ADR-0009.R14 | R28, R29 |
| ADR-0009.R14.N1 | R30 |
| ADR-0009.R15 | R31, R32 |
| ADR-0009.R15.N1 | R33 |
| ADR-0009.R16 | R34 |
| ADR-0009.R16.N1 | R34 |
| ADR-0009.R17 | R35 |
| ADR-0009.R18 | R36, R37 |
| ADR-0009.R19 | R38, R39, R40 |
| ADR-0009.R19.N1 | R40 |
| ADR-0009.R20 | R41 |
| ADR-0009.R20.N1 | R41, R42 |
| ADR-0009.R21 | R43 |
| ADR-0009.R21.N1 | R43 |
| ADR-0009.R22 | R44 |
