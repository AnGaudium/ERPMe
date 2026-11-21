Module: documents    Chunk: 2 of 3    Source ADRs: ADR-0009, ADR-0027, ADR-0028, ADR-0029
Build step(s): 1, 2, 3, 4, 4b, 5    Generated from index: 30d5706    Compiled by: Claude Fable 5.2, 2026-11-21

# `documents` compiled spec, chunk 2: corrections, line identity, change orders, e-invoiced lifecycle, approval context, change proposal content

## Purpose

This chunk states the part of `documents` law on: correction documents, the widened numbering invariant, line identity and line references, change orders on approved documents, the two-phase lifecycle of e-invoiced documents (`draft → issuing → posted`), the re-check of the approval context, the partner snapshot, and the content and allowed targets of the `change_proposal` document. `documents` is layer 2 (ADR-0029.R1). It does not own the e-invoice record or the provider adapter (`tax`), the policy decision (`policy`), or `demand_supply_line` and the execution tables. The base lifecycle (states, versions, numbering, approval, reversal) is in chunk 1; the execution of change proposals, taint and the other shared rules are in chunk 3.

## Entities and tables

DDL: `docs/design/DS-05-platform.sql`.

| Table | Meaning | Key | Parent | Owner |
| --- | --- | --- | --- | --- |
| `posting_intent` | The frozen plan, rates and `plan_hash` of one `Issue` attempt, with its state and whether the e-invoice was required (R232) | `id`; (`company_id`, `id`) unique | `document_version` (of `document`) | documents |
| `change_proposal` | Typed header of the non-posting document type `change_proposal`: plan, `plan_hash`, evidence, reason, `document_date` (R260), and `execution_error`, the non-retryable error of the last execution attempt (`ADR-0029.R3`) | `id`, equal to the `document` row's `id` | `document` | documents |
| `change_proposal_item` | One command of the proposal's batch: `command_type`, `schema_version`, `payload`, `target_table`, `target_id`, `expected_version` (absent when the command creates the record) and `field_changes` (before and after per field) (R260). Its `id` is stable (`ADR-0029.R3`) | `id`; (`change_proposal_id`, `item_index`) unique | `change_proposal` | documents |

Named by rules of this chunk, with their rows in chunk 1: `document`, `document_version`, `approval`.

Reads: `demand_supply_line`, `stock_reservation`, `warehouse_task`, `transfer_order_line`, `stock_transfer_line`, `return_from_customer_line` (`inventory`, `planning`); `policy_decision` (`policy`); the e-invoice record (`tax`); `employee_profile`, `partner` (`master_data`); `applied_rate`, `derivation_trace`, `journal_entry` (`ledger`); `numbering_series` (chunk 1).

## Commands and queries

Authorization: the catalog `authorization-areas.csv` holds the leaf `change_proposal` (kind `document_type`, under `master_data`, module `documents`) for the change proposal commands. For the other commands the sources of this chunk name no area. Verb levels are those of `authorization-verb-levels.csv`: `Create`, `Update`, `Submit`, `Cancel` and `Recall` need `edit`; `Issue`, `Post`, `Complete`, `Record`, `Reopen` and `Close` need `post`; `Approve` and `Reject` need the role's approval flag (level `approve`).

| Name | Actor / authorization | Input | Effect | Events | Error codes |
| --- | --- | --- | --- | --- | --- |
| `Create<CorrectionType>` | human or agent; area not stated, level `edit` | `correction_of_id` (or `external_original`), the lines to correct | Creates a correction draft with the line data copied from the original (R202, R205) | not stated | not stated |
| `Post<CorrectionType>` | `human_only`; `system` only as the completion of an `Issue`; level `post` | not stated | Posts the correction document (R204, R206) | not stated | not stated |
| `Issue<CorrectionType>` | `human_only`; level `post` | not stated | Issues an e-invoiced correction (R206, R232) | `IssueRequested` | as `Issue<Type>` |
| `CancelChange<Type>` | anyone with the type's `Update` permission, including the agent that wrote the change | `pending_version` | Discards the pending change (R223) | not stated | not stated |
| `Issue<Type>` | human or policy-allowed; effect class `posting`; level `post` | not stated | Validates, freezes the plan on a `posting_intent`, requests the e-invoice, moves the document to `issuing` (R232, R233) | `IssueRequested` | `e_invoice_invalid`, `approval_context_changed` |
| `Record<Type>EInvoiceOutcome` | `system`, a command of `tax`, run by the external consumer; level `post` | `accepted` with the e-invoice number and issue date, or `rejected` with the reason | Writes the outcome on the e-invoice record; always succeeds (R234) | `EInvoiceAccepted`, `EInvoiceRejected` | none |
| `Complete<Type>Posting` | `human_only`; effect class `posting`; level `post`; with `post_in_soft_locked_period` where needed | not stated | Completes a held posting of an accepted e-invoice (R236) | not stated | not stated |
| `Reopen<Type>` | run by the consumer of `EInvoiceRejected`; level `post` | not stated | Returns the document to `draft` with the rejection reason; creates a work item for the issuer (R237) | not stated | not stated |
| `Recall<Type>` | `human_only`; level `edit` | not stated | Returns a document in `issuing` to `draft` and skips the pending issue delivery (R240) | not stated | rejected while the delivery is `running` (no code stated) |
| `CreateChangeProposal` | the proposer holds the permission `CreateChangeProposal`; area `change_proposal`, level `edit` | the items (commands and payloads), reason, evidence | Creates a proposal draft; the server computes diff, expected versions and plan (R261) | not stated | `employee_organization_command_required` |
| `UpdateChangeProposal` | area `change_proposal`, level `edit`; also run as `system` by the executing consumer after a failed execution (`ADR-0029.R3`) | as `CreateChangeProposal` | Writes the next version; the server computes diff, expected versions and plan again (R261); after a failed execution, with the error and the new plan, the approval voided and the proposal back in `draft` (`ADR-0029.R3`) | not stated | `employee_organization_command_required`, `proposal_item_referenced` (`ADR-0029.R3`) |

`Post<Type>` as the completion of an `Issue` (registered `is_consequence_posting`, R235) returns `invalid_state_transition` for any other caller, state or hash where the e-invoice is required; `Post` of an approved document returns `approval_context_changed` (R250). The base rows of `Update`, `Post`, `Submit`, `Approve`, `Reject`, `Cancel` and `Close` are in chunk 1; the `Update<Type>` row there holds the line and change-order effects and codes of R210, R217, R222 and R223.

Contract functions and interfaces, not registered commands: `tax.contract.request_e_invoice` (R232); the interface `EInvoiceValidator`, published by the core and implemented by the localization package (R238); the query `GetPartnerExposure` of `ledger`, read by R239.

Check results and codes bound to no single command of this chunk: `partner_snapshot_stale` (check result at `Post` or `Issue`, R251); `target_changed` (every allowed-target command, R263); `external_call_outcome_unknown` (the stop of the issuance retry, R240).

## Rules

### Correction documents

R201. A correction document is an ordinary posting document of a correction type (`sales_return`, `purchase_return`, `credit_note`, `debit_note`, adjustment or replacement invoice) whose `correction_of_id` points to the posted, not reversed, original of the same company. A reversal document cannot be the original of a correction.
Source: ADR-0009.R23

R202. A correction document is created from the original in one command: `Create<CorrectionType>` takes `correction_of_id` and the lines to correct and copies their data from the original, so the user or agent changes only what differs. `correction_of_id` is set at `Create`, never changed, and part of the version content (ADR-0009.R9), so an approval binds to it.
Source: ADR-0009.R23

R203. An original may have several correction documents, each correcting part of it (some lines, a quantity, a price). A correction document is itself a posted document and may be corrected the same way. The limits on the cumulative correction (for example returns never above the quantity delivered) are ADR-0047.R20 and are checked by `INV-40`.
Source: ADR-0009.R23

R204. A correction document goes through the same states, approval, period checks and numbering as any document; it posts in an open period even when the original's period is locked.
Source: ADR-0009.R23

R205. A credit note or sales return may correct an invoice that exists only in the old system, with `external_original` instead of `correction_of_id`, for originals dated before the migration cut-over; limits then apply against the entered amounts. `sales_return` and `purchase_return` credit returned goods and refer to the stock return lines.
Source: ADR-0009.R23

R206. Who may post correction documents is an open question for the author, because a correction that fully offsets its original undoes a posted document, which the spec reserves to humans (spec 14). Interim, flagged: only a human may post or issue them. The registry flag is the one rule for corrections by non-humans: `Post<CorrectionType>` and `Issue<CorrectionType>` are registered `human_only` (ADR-0008.R2), so agents and, under the interim, integrations neither post nor issue a correction, and `system` runs `Post<CorrectionType>` only as the completion of an `Issue` (ADR-0043.R9; ADR-0028.R7.N1). Agents may create correction drafts but not submit them: no `Submit`, `Post` or `Issue` is on an agent tool list, so people submit (ADR-0050.R30).
Source: ADR-0009.R23, ADR-0009.R23.N1

R207. Which correction types each document type allows, their fields and their accounting and stock effect are decided by DS-09, DS-22 and DS-24; the cost of a sales return is ADR-0020.R5.N6.
Source: ADR-0009.R23

### Numbering invariant

R208. `INV-07` covers every document that holds a number, in any state: per numbering series the counters are exactly 1 to `next_value` − 1, each once. This widens the invariant to non-posting documents and never weakens it. It is flagged, because it rests on the interim of ADR-0009.R8 (numbering of non-posting documents at approval).
Source: ADR-0027.R16

### Line identity and line references

R210. `Update` submits the full list of lines. Lines are matched to existing rows by `line_number`. A line number is never renumbered and never reused in its document. A new line takes the next unused number; a missing number deletes its row. Row `id`s are stable, and version content still excludes them (ADR-0009.R9).
Source: ADR-0028.R1

R211. Commercial document lines and `demand_supply_line` (ADR-0024.R8) refer to other document lines by typed foreign keys. Each key is named after the referenced line table, for example `sales_order_line_id`, `transfer_order_line_id`, `goods_receipt_line_id`. A line referred to as the corrected line uses `correction_of_line_id` (ADR-0004.R12); it may name a line of the same table or, where the correction is a document of another type, a line of another line table (ADR-0047.R2; DS-22-09-42-commercial-inventory.sql). `transfer_order_line_id` on `demand_supply_line` gets its key with `transfer_order_line`, and `stock_transfer_line` names the order line it fulfils by the same typed key (ADR-0075.R14). Only `demand_supply_line` and the commercial documents carry typed foreign keys to document lines.
Source: ADR-0028.R2, ADR-0028.R2.N2, ADR-0028.R2.N3, ADR-0028.D0

R212. The typed production columns on `demand_supply_line` (`production_order_component_id`, `production_order_output_id`, `for_demand_supply_line_id`, `owner_partner_id`) and `production_order_operation_id` on purchase lines (ADR-0034.R9; ADR-0036.R9; ADR-0037.R4 and R7) belong to the production core step (step 4b, ADR-0032.R7). They are not a commercial document changing the core, so B3 holds. The simulation and the DDL drafts assume the columns exist.
Source: ADR-0028.R2, ADR-0028.R2.N1, ADR-0028.D0.N1

R213. Each line table declares its reference roles. Each role allows at most one non-null column, and a role is mandatory where the table declares it.
Source: ADR-0028.R2

R214. Execution tables refer to `demand_supply_line_id` only: `stock_reservation`, `warehouse_task` and pegging (ADR-0023.R13, ADR-0023.R14; ADR-0024.R20). This stands for "a demand line" in those rules and cuts the line-reference pairs of each line table to one.
Source: ADR-0028.R2

R215. As in ADR-0027.R7, `demand_supply_line` has from step 3 the nullable columns for every Phase 1 line table (`transfer_order_line_id`, the stock document lines, and `sales_order_line_id`, `purchase_order_line_id`, `purchase_request_line_id`); the foreign key constraints for step 5 tables are added at step 5, so the table does not change.
Source: ADR-0028.R2

R216. `demand_supply_line` rows are never rebuilt, are unique per source line and direction, are created before the first reservation, and are closed with `closed_reason` when a line is removed when a change takes force. A draft purchase request or order line whose supply row carries `origin_planned_order_id` or pegging cannot be removed: its quantity goes to zero, or the document is canceled, closing the row as `canceled`. Other draft lines removed in draft delete their rows. Rows are never deleted once their document has left draft (ADR-0047.R10).
Source: ADR-0028.R2

R217. Once another document refers to a line: the line cannot be deleted (`document_line_referenced`); its item, unit and warehouse cannot change (`referenced_line_immutable`); its quantity cannot go below the quantity already fulfilled by referring documents (`quantity_below_fulfilled`). Documents in `issuing` count as fulfilling (R239).
Source: ADR-0028.R3

### Change orders

R220. A document type may declare `is_change_order_allowed`. In Phase 1 these are sales and purchase orders (step 5), transfer orders (from step 5; at step 3 transfer orders have no change orders) and production orders (ADR-0034.R8). An approved order stays in force on its last approved version while a change is drafted and approved.
Source: ADR-0028.R4, ADR-0028.D0

R221. Storage of a change. The document keeps `version` = the version in force, and its typed rows stay at that version. A change is stored as the next `document_version` row (rows are never updated, ADR-0009.R14). It is pending exactly when `document.pending_version` points to it, and its canonical content is the authority for the change until it takes force. The document records `pending_version` and `change_state`: `none`, `drafting` or `pending_approval`. A replaced or discarded change stays as a version row that never took force, so the version in force may skip numbers.
Source: ADR-0028.R4

R222. Step 3 interim: before change orders exist for transfer orders (step 5), `Update` of an approved transfer order that has reservations, tasks or fulfillment is rejected (`document_referenced`), so steps 3 and 4 never orphan execution. The change state columns exist from step 3; turning the flag on at step 5 only enables the commands, so the core table does not change.
Source: ADR-0028.R4

R223. Commands on a change:
- `Update` of an `approved` document writes or replaces the pending version: `change_state` becomes `drafting`.
- `Submit` asks the policy and moves it to `pending_approval`.
- `Approve` makes it the version in force.
- `Reject` (approver) or `Cancel` of the change (anyone with the type's `Update` permission, including the agent that wrote it; `CancelChange<Type>`) discards it.
- An `Update` while `pending_approval`, and `Cancel` or `Close` with a pending change, are rejected with `change_pending`.
Source: ADR-0028.R4

R224. Commands on the pending change carry `pending_version`; other commands carry `version` (ADR-0009.R10). A change has no number of its own; the document keeps its number. For `INV-10`, "current version" means the version in force; this is a definition, not a change to the invariant, and it is listed for the author.
Source: ADR-0028.R4

R225. Execution (reservations, pick release, deliveries, receipts, planning demand) uses the version in force. When the pending version takes force, `Approve` locks the document row and re-checks R217 against current fulfillment. Execution commands lock the documents they refer to first (ADR-0027.R10, position 1), so take-force and execution never interleave.
Source: ADR-0028.R5

R226. When a change takes force, the posting interfaces adjust only lines whose item, quantity, warehouse or date changed, in `line_number` order. Unstarted pick tasks above a new quantity are canceled. Started tasks complete, and the excess goes back to stock by a move task.
Source: ADR-0028.R5

R227. Open question (business behavior): whether execution may continue while a change is pending, and at which price quantities not yet invoiced are invoiced. Interim, flagged: execution continues on the version in force, and the new price applies to quantities invoiced after the change takes force.
Source: ADR-0028.R5

### E-invoiced documents: states

R230. A document type declares `is_e_invoice_capable`. Whether an e-invoice is required for it is the setting `documents.e_invoice_required`, per document type, core default false, set by the regime (DS-24; ADR-0016; ADR-0053.R8). For such a type, with the e-invoice required, the states are `draft → issuing → posted`, and back to `draft` on rejection, without approval hold (ADR-0009.R12). For types with `is_approval_hold_allowed: regime`, while `documents.issuance_without_delay` is false the approval hold is available and the states are `draft → pending_approval → approved → issuing → posted`: `Issue<Type>` is allowed only from `approved`, and a rejection returns the document to `draft`, to be submitted again. While that setting is true, the states without approval hold apply.
Source: ADR-0028.R6, ADR-0028.R6.N1, ADR-0028.R6.N2

R231. `issuing` is not final. Header and lines are immutable in it, as in `posted` (ADR-0009.R14), because the content has been sent to the tax authority. The commands allowed in `issuing` are the outcome commands of R234 to R237 and `Recall<Type>` (R240). Outbound messages use the same pattern with the non-final state `sending` (ADR-0052.R27).
Source: ADR-0028.R6

### E-invoiced documents: the flow

R232. `Issue<Type>` (human or policy-allowed; verb `Issue`, event form `IssueRequested`; effect class `posting`). The dispatcher asks the policy here, and the decision is stored. The command:
- runs the package validation of R238, and the same period checks and period share lock as `Post` (ADR-0009.R13; ADR-0012.R9);
- freezes `posting_date`, which must equal the content's, as with `Post` (ADR-0009.R9);
- resolves the rates (ADR-0011.R1) and computes the prospective journal and open items as its plan, with that `plan_hash`;
- stores the frozen plan, the rates and the hash on a `posting_intent` row (owned by `documents`; one per `Issue` attempt, never reused; state `pending`, `posted`, `reopened` or `recalled`; it also records that the e-invoice was required);
- requests the e-invoice through `tax.contract.request_e_invoice` (ADR-0027.R8);
- moves the document to `issuing`.
No journal row, document number or open item is written yet. The result returns state `issuing` and the e-invoice record ID.
Source: ADR-0028.R7

R233. `Issue` from `draft` always evaluates the policy. `Issue<Type>` from `approved` (an approval hold, ADR-0053.R8) asks the policy nothing new while the `policy_input_hash` and the actor kind equal those of the approved version's decision; it stores that decision, bound to the approved version, on the `posting_intent`. When either differs, it evaluates again, as from `draft`. Floors 3 to 6 of ADR-0043.R9 still apply at `Issue`, and the plan and its hash are computed at `Issue`.
Source: ADR-0028.R7, ADR-0028.R7.N2

R234. `Record<Type>EInvoiceOutcome` (verb `Record`; `system`, in `tax`) is run by the external consumer (ADR-0013.R10). It writes `accepted` (with the e-invoice number and issue date) or `rejected` (with the reason) on the e-invoice record, and always succeeds. It emits `EInvoiceAccepted` or `EInvoiceRejected`.
Source: ADR-0028.R7

R235. On `EInvoiceAccepted`, a transactional consumer runs `Post<Type>` as actor `system` on behalf of the event's `on_behalf_of_id` (ADR-0013.R9). It uses the stored `expected_plan_hash` and frozen rates, and writes the journal, the number, the open items and the e-invoice reference.
- That completion `Post<Type>` is registered `is_consequence_posting` and carries the issuer's decision: the policy is not asked again, and floors 3 to 6 and the actor-kind policy point are applied at `Issue` and not repeated, so an e-invoiced correction or an agent-drafted e-invoiced invoice posts without a held delivery (ADR-0043.R5, ADR-0043.R9; ADR-0027.R12).
- Under the human-only interim of ADR-0009.R12 this completion is allowed on behalf of the issuer (ADR-0027.R12).
- Where the e-invoice is required, `Post<Type>` is accepted only from this internal caller, in state `issuing`, with an `accepted` e-invoice record and the stored `expected_plan_hash`; anything else returns `invalid_state_transition`.
Source: ADR-0028.R7, ADR-0028.R7.N1

R236. If the completing posting fails (a changed plan, a soft-locked or locked period, a changed account), the delivery is held with a work item. A human completes it with `Complete<Type>Posting` (verb `Complete`; `human_only`, effect class `posting`, same preconditions; with `post_in_soft_locked_period` where needed), and corrects it afterwards with an adjustment document if needed. The consumer is idempotent: an already posted document counts as done, so the held delivery resolves.
Source: ADR-0028.R7

R237. On `EInvoiceRejected`, a consumer runs `Reopen<Type>`, which returns the document to `draft` with the rejection reason and creates a work item for the issuer.
Source: ADR-0028.R7

R238. Package validation. Before the request, `EInvoiceValidator` checks schema, buyer tax ID format, registered symbol and dates. It is published by the core and implemented by the localization package (ADR-0016.R17). It is network-free and deterministic, and runs in simulation and at `Issue`. Failures return `e_invoice_invalid`, with the package's code in `details`. A `posting_date` outside the regime's window (package data) is rejected here. An acceptance whose issue date falls outside the window is held with a work item instead of posting; the posting date is never changed silently.
Source: ADR-0028.R8

R239. While a document is in `issuing`: it counts toward invoiced quantity (ADR-0009.R7) and toward cumulative correction limits (`INV-40`); it counts in partner exposure (DS-22 composes it with `GetPartnerExposure`, ADR-0026.R15); it has no journal entry, number or open item (`INV-44`).
Source: ADR-0028.R9

R240. Outages. A document stays in `issuing` during an outage; the intent retries and its deliveries are held with work items (ADR-0013.R8). An unknown issuance outcome follows ADR-0013.R10: the e-invoice request sends our reference as the provider's idempotency key where it has one; the retry waits the settle delay and requests again only after a pair of status queries, at least the delay apart, both report nothing held; after the configured unknown rounds it stops with `external_call_outcome_unknown`. The document stays in `issuing` throughout. `Recall<Type>` (verb `Recall`; `human_only`) returns the document to `draft` only when the last pair of status queries recorded on the e-invoice record by the external consumer (ADR-0013.R10), at least the delay apart, both report "nothing held". In the same transaction it skips the pending issue delivery, and it is rejected while that delivery is `running`.
Source: ADR-0028.R10, ADR-0028.R10.N1

R241. Close check. ADR-0012.R13 gets a required core check task that blocks `LockPostingPeriod` while the period has any document whose `posting_date` falls in it and that is either in `issuing`, or accepted but not posted. So books never hold an invoice that was not issued, and an issued invoice is never left without books.
Source: ADR-0028.R11, ADR-0028.D0

R242. Placement: the two-phase lifecycle is built at step 5 with sales invoices. A deterministic stub adapter accepts or rejects from test data. The stub stays in the core build and the tests. The provider adapter is an add-on designed after the core (backlog, add-ons section); it replaces the stub without changing the core.
Source: ADR-0028.R12

R243. The two-phase model is the interim, flagged: whether e-invoiced documents may instead post first and be reversed while unissued is the author's decision (legal; open question). Also the author's: which date governs posting and the e-invoice; what "acceptance" means for invoice kinds without a tax authority code (unverified, spec 08); how cost of goods sold already posted by a delivery is presented while its invoice is in `issuing` across a period end.
Source: ADR-0028.R13, ADR-0028.D0

### Approval context

R250. Recording and re-checking the approval context:
- At `Submit` (and at `Issue` or `Post` from `draft`), the `policy_decision` records the approval procedure required and a `policy_input_hash`. The hash covers the inputs evaluated: amounts in company currency at the rates applied, partner exposure, and price and margin checks.
- The `approval` row refers to the `policy_decision_id` it satisfies.
- At `Post` of an approved document, and at `Issue`, the policy is asked again when the `policy_input_hash` differs. An approval stands while the new decision requires the same or a lower approval procedure; procedures compare by rank (ADR-0043.R2) and by stages: the existing approvals stand when every stage the new plan requires already has its approvals in the round (ADR-0055.R8). Otherwise the command is rejected with `approval_context_changed`, whose `details` give the approved and current amounts and procedures.
- The document may then be submitted again without edit (`approved → pending_approval`). A resubmission continues the round when the pool stays the same and starts a new one when it changes (ADR-0055.R11).
Source: ADR-0028.R14, ADR-0028.R14.N1, ADR-0028.D0

### Partner snapshot

R251. Partner name, address and tax ID (ADR-0019.R5) are copied by `Create` and `Update` and are part of the content when the document is written. The snapshot covers every named party of a document (ship-to, bill-to, payer, invoicing party, payee; ADR-0074.R1). Posting never changes them. At `Post` or `Issue`, a snapshot that differs from the partner's master returns the check result `partner_snapshot_stale`, evaluated per named party (ADR-0074.R5). Whether that warns or blocks is business behavior. Interim, flagged: it warns, and for the tax ID on e-invoiced types `Issue` is rejected with `e_invoice_invalid`.
Source: ADR-0028.R16, ADR-0028.R16.N1, ADR-0028.D0

### Invariants, edge cases and events of the hardening

R252. The hardening is held by the invariants `INV-41`, `INV-42`, `INV-43`, `INV-44`, `INV-45`, `INV-46` and `INV-47` and the edge cases `EC-53`, `EC-54`, `EC-55`, `EC-59` and `EC-60` (statements in the Invariants and Edge cases sections). `INV-82` is tightened: the approvals must refer to the latest policy decision on the posted version, or satisfy its procedure, by stages (R250). `EC-56` to `EC-58` are held by DS-47. DS-17 adds the business events `sales_order_changed`, `e_invoice_rejected` and `e_invoice_outage`, raising the log schema to 0.2.0.
Source: ADR-0028.R17

### Change proposals: content and targets

R260. `change_proposal` is a non-posting document type owned by `documents` (layer 2). It holds `items`: a batch of ADR-0008.R20, so a single change is a one-item list. Each item records: its command type, schema version and payload; the target record and its expected version, `expected_version`, the SHA-256 of the record's canonical JSON (the forms of ADR-0008.R12), absent when the command creates the record; the before-and-after values per field. The proposal also holds the simulated plan of the whole batch with its `plan_hash`, evidence references (attachments, interactions, derivation traces, the agent run), the reason and a `document_date`.
Source: ADR-0029.R1

R261. `CreateChangeProposal` and `UpdateChangeProposal` compute diff, expected versions and plan on the server; the caller never supplies them. The proposer needs the permission `CreateChangeProposal`. The human the proposer acts for, or the proposer when human, must hold each target command's permission (ADR-0017.R13).
Source: ADR-0029.R1

R262. A change proposal may not target `employee_profile.department_id`, `manager_partner_id` or `user_account_id`; it is refused with `employee_organization_command_required` (ADR-0054.R6).
Source: ADR-0029.R1.N1

R263. Allowed targets of a change proposal: commands whose `effect_class` (ADR-0027.R17) is `master_data_change`, and commands registered `is_proposal_bound` (a registry attribute, ADR-0008.R1). Never allowed: `human_only` commands, commands of effect class `posting` or `outbound_send`, and change-proposal commands. Every allowed-target command takes an optional `expected_version`. A caller that gives it gets `target_changed` when the record's current hash differs; the executing consumer always gives it. DS-20 builds this into the master data commands at step 2, and the owner of each `is_proposal_bound` command builds it into that command.
Source: ADR-0029.R2

## Invariants

Statements are those of `invariants.csv`. Each row stands once in the module, in the chunk that states the rule its catalog source names.

| Invariant | Name | Check point | Statement | Protects |
| --- | --- | --- | --- | --- |
| `INV-40` | `corrections_within_original` | day | Cumulative corrections never exceed the original: returned per delivery line within delivered, credited quantity per invoice line within invoiced, credited amount within the line's net amount, and the same for purchase lines (ADR-0047.R20). | R203, R239 |
| `INV-41` | `referenced_lines_live` | day | Every line referred to by an open `demand_supply_line` row, or by a line of a document that is not canceled or reversed, belongs to a document that is not canceled. | R216, R217 |
| `INV-42` | `accepted_e_invoice_posted` | day | Every accepted e-invoice has a posted document, or an open work item while its posting is held. | R235, R236 |
| `INV-43` | `single_pending_change` | day | `pending_version` is null exactly when `change_state` is `none`, and otherwise is greater than `version`. | R221 |
| `INV-44` | `issuing_writes_nothing` | day | A document in `issuing` has no journal entry, document number or open item. | R232, R239 |
| `INV-45` | `quantity_not_below_fulfilled` | day | No document line's quantity is below the quantity fulfilled by referring documents. | R217 |
| `INV-46` | `posted_e_invoiced_has_acceptance` | day | Every posted document with a `posting_intent` recording that the e-invoice was required has an accepted e-invoice. Flagged: the e-invoice posting model (R243). | R230, R235 |
| `INV-47` | `execution_on_version_in_force` | day | Open reservations and unstarted warehouse tasks refer only to open `demand_supply_line` rows. | R214, R225 |
| `INV-86` | `proposal_targets_never_by_agent` | day | No audit row of a command whose effect class is `master_data_change` or that is registered `is_proposal_bound` has actor agent or an origin agent run. | R263; ADR-0029.R4.N2 |

Named by rules of this chunk, with their rows elsewhere: `INV-07` (R208; area `ledger`, its row in chunk 1), `INV-10` (R224; chunk 1), `INV-82` (R252; its catalog source names ADR-0009.R11 first).

## Edge cases

Cases and outcomes are those of `edge-cases.csv`.

| Edge case | Name | Case | Outcome | Protects |
| --- | --- | --- | --- | --- |
| `EC-20` | `return_of_partly_invoiced_goods` | A customer returns goods of which only part was invoiced. Interim, flagged (ADR-0047.R20): a sales return for the invoiced share is due; uninvoiced returned goods reduce what remains to invoice. | `must_succeed` | R203 |
| `EC-53` | `e_invoice_rejected` | An e-invoice rejected for a wrong buyer tax ID returns the invoice to draft; it is corrected and issued again; nothing is posted before acceptance. | `must_succeed` | R237 |
| `EC-54` | `order_changed_after_partial_pick` | An approved order is changed after part of it was picked; the version in force stays until the change is approved; only changed lines are adjusted. | `must_succeed` | R221, R226 |
| `EC-55` | `rates_cross_approval_threshold` | Rates move between approval and posting so the required procedure rises; posting is rejected with `approval_context_changed` and the document is submitted again. | `must_succeed` | R250 |
| `EC-59` | `e_invoice_outage_across_period_end` | A provider outage keeps an invoice in `issuing` across month end; the period lock is blocked until it posts. | `must_succeed` | R240, R241 |
| `EC-60` | `backdated_issue_outside_window` | An invoice issued with a posting date outside the regime's window is rejected by package validation. | `must_succeed` | R238 |
| `EC-312` | `party_stale_snapshot` | A bill-to party's address changes after the order; posting the invoice returns `partner_snapshot_stale` for that party. | `must_succeed` | R251 |

Named by R252 and held by DS-47, of area `safety`, with their rows in the `policy` and `registry` specs: `EC-56`, `EC-58`.

## Settings

None: the keys `documents.e_invoice_required` and `documents.issuance_without_delay` named by R230 have no row in `settings.csv`; chunk 3 states them once (`ADR-0053.R8`, `ADR-0053.R8.N1`).

Reads: `fx.document_rate.allowed` (`ledger`; ADR-0011.R12); `movement_type.purchase_return.value_source`, `movement_type.purchase_return.costing_role`, `movement_type.purchase_return.include_landed_cost`, `movement_type.sales_return_receipt.value_source`, `movement_type.sales_return_receipt.costing_role` (`inventory`; ADR-0020.R5.N2, ADR-0020.R5.N5); `integrations.<provider>.status_settle_delay_minutes`, `integrations.<provider>.max_unknown_rounds` (ADR-0013.R10; the settle delay and the unknown rounds of R240).

## UI annotations

The sources of this chunk hold no ADR-0077 floorplan, tile or field annotation. Work item kinds raised by rules of this chunk are rows of `work-item-kinds.csv` owned by other modules: `e_invoice_rejected`, `e_invoice_outage`, `e_invoice_posting_held` and `e_invoice_date_outside_window` (`tax`; R236 to R240) and `external_call_outcome_unknown` (`outbox`; R240).

## Conflicts

CONFLICT ADR-0009.R23: the rule's closing paragraphs govern its bullets. ADR-0050.R30 governs submission: agents create correction drafts but do not submit them, so "agents may create and submit correction drafts" is not restated (R206). ADR-0047.R20 sets the cumulative limits, in place of "set by DS-22" (R203). ADR-0020.R5.N6 decides the cost of a sales return, so its mark "an existing open question" is not restated (R207).
CONFLICT ADR-0028.R2: ADR-0028.R2.N2 with ADR-0047.R2 governs `correction_of_line_id`, which may name a line of another line table, not only "a line of the same table" (R211). ADR-0028.D0.N1 governs the production columns: they belong to step 4b and B3 holds, so "flagged for the author" and "the author's decision under B3" are not restated (R212). The rule's closing paragraph citing ADR-0047.R10 governs deletion: rows of lines removed in draft are deleted, so "never deleted" holds only once the document has left draft (R216).
CONFLICT ADR-0028.R2.N1: ADR-0028.D0.N1 (author's delegation, 2026-11-19) is later and decides the question this note kept open; R212 keeps only that the simulation and the DDL drafts assume the columns.
CONFLICT ADR-0028.R6: ADR-0028.R6.N1 with ADR-0053.R8 governs the approval hold: it is available for types with `is_approval_hold_allowed: regime` while `documents.issuance_without_delay` is false, so "approval hold stays unavailable" holds only without that case (R230).
CONFLICT ADR-0028.R7: ADR-0028.R7.N2 governs `Issue` from `approved`: the stored decision of the approved version is reused while hash and actor kind are equal, so "the dispatcher asks the policy here" holds for `draft` and for a changed input only (R233).
CONFLICT ADR-0028.R10: ADR-0028.R10.N1 governs the condition of `Recall<Type>`: the last pair of status queries, at least the settle delay apart, both report nothing held, not the last status alone (R240).
CONFLICT ADR-0028.R12: the rule's closing note of the author (2026-11-15) governs: the provider adapter is an add-on designed after the core, so "DS-24 replaces the stub at step 7" is not restated (R242).
CONFLICT ADR-0028.R14: ADR-0028.R14.N1 with ADR-0055.R8 and ADR-0055.R11 governs the comparison: by stages and rounds, so "the comparison is DS-28's" is not restated (R250).
CONFLICT ADR-0028.R16: ADR-0028.R16.N1 with ADR-0074.R1 and ADR-0074.R5 governs the scope of the snapshot: every named party, each evaluated on its own, not the document's partner alone (R251).
CONFLICT ADR-0028.R17: ADR-0028.R14.N1 governs how approvals satisfy a later decision, so the tightening of `INV-82` reads by stages (R252); the catalog statement of `INV-82` is the authority.

## Proposed (not law)

None

## Trace

| Source | Where |
| --- | --- |
| ADR-0009.R23 | R201-R207 |
| ADR-0009.R23.N1 | R206 |
| ADR-0011.R3 | ref: ADR-0011.R3 |
| ADR-0011.R3.N1 | ref: ADR-0011.R3.N1 |
| ADR-0011.R3.N2 | ref: ADR-0011.R3.N2 |
| ADR-0011.R12 | ref: ADR-0011.R12 |
| ADR-0017.R16 | ref: ADR-0017.R16 |
| ADR-0017.R16.N1 | ref: ADR-0017.R16.N1 |
| ADR-0020.R4 | ref: ADR-0020.R4 |
| ADR-0020.R4.N1 | ref: ADR-0020.R4.N1 |
| ADR-0020.R4.N2 | ref: ADR-0020.R4.N2 |
| ADR-0020.R4.N3 | ref: ADR-0020.R4.N3 |
| ADR-0020.R5.N1 | ref: ADR-0020.R5.N1 |
| ADR-0020.R5.N2 | ref: ADR-0020.R5.N2 |
| ADR-0020.R5.N4 | ref: ADR-0020.R5.N4 |
| ADR-0020.R5.N5 | ref: ADR-0020.R5.N5 |
| ADR-0020.R5.N6 | ref: ADR-0020.R5.N6 |
| ADR-0022.R2.N9 | ref: ADR-0022.R2.N9 |
| ADR-0023.R22.N2 | ref: ADR-0023.R22.N2 |
| ADR-0027.R4 | ref: ADR-0027.R4 |
| ADR-0027.R4.N1 | ref: ADR-0027.R4.N1 |
| ADR-0027.R16 | R208 |
| ADR-0028.D0 | R211, R220, R241, R243, R250, R251 |
| ADR-0028.D0.N1 | R212 |
| ADR-0028.R1 | R210 |
| ADR-0028.R1.N1 | not applicable: citation convention for "ADR-0028 rule N", no rule content |
| ADR-0028.R2 | R211-R216 |
| ADR-0028.R2.N1 | R212 |
| ADR-0028.R2.N2 | R211 |
| ADR-0028.R2.N3 | R211 |
| ADR-0028.R3 | R217 |
| ADR-0028.R4 | R220-R224 |
| ADR-0028.R5 | R225-R227 |
| ADR-0028.R6 | R230-R231 |
| ADR-0028.R6.N1 | R230 |
| ADR-0028.R6.N2 | R230 |
| ADR-0028.R7 | R232-R237 |
| ADR-0028.R7.N1 | R235 |
| ADR-0028.R7.N2 | R233 |
| ADR-0028.R8 | R238 |
| ADR-0028.R9 | R239 |
| ADR-0028.R10 | R240 |
| ADR-0028.R10.N1 | R240 |
| ADR-0028.R11 | R241 |
| ADR-0028.R12 | R242 |
| ADR-0028.R13 | R243 |
| ADR-0028.R14 | R250 |
| ADR-0028.R14.N1 | R250 |
| ADR-0028.R16 | R251 |
| ADR-0028.R16.N1 | R251 |
| ADR-0028.R17 | R252 |
| ADR-0029.D0 | ref: ADR-0029.D0 |
| ADR-0029.R1 | R260-R261 |
| ADR-0029.R1.N1 | R262 |
| ADR-0029.R1.N2 | not applicable: citation convention for "ADR-0029 rule N", no rule content |
| ADR-0029.R2 | R263 |
