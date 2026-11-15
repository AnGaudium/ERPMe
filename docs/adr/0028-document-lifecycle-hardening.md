# ADR-0028: Document lifecycle hardening

Status: accepted (2026-11-14) under ADR-0005, reviewed by Claude Fable 5.2 (builder Claude Opus 5.5). Design item: DS-46 (new). Related decisions: D2. Principles 2, 4, 5, 12, 13. ADR-0004, ADR-0005, ADR-0007, ADR-0008, ADR-0009, ADR-0011, ADR-0012, ADR-0013, ADR-0016, ADR-0017, ADR-0019, ADR-0022, ADR-0023, ADR-0024, ADR-0026, ADR-0027. Assessment findings A-1, O-1 (F1), O-2 (F8), F7, C-7 ([design assessment 1](../reviews/2026-11-14-design-assessment/README.md)).

## Decision

This ADR amends the document lifecycle (ADR-0009) in five places, before step 3 and step 5 code depends on them:

1. **Line identity.** A line's `line_number` is its identity in its document: never renumbered, never reused. A referenced line cannot disappear or change what it is. Execution tables (reservations, warehouse tasks, pegging) refer to demand and supply lines through `demand_supply_line`. Only that read model and the commercial documents carry typed foreign keys to document lines.
2. **Change orders.** An approved order stays in force on its last approved version while a change is drafted and approved. The change has its own small state machine and is stored as a pending version beside the version in force.
3. **E-invoiced documents** follow `draft → issuing → posted`. `Issue<Type>` freezes the content, posting date, rates and prospective journal, and requests the e-invoice. Acceptance is recorded first and always succeeds; a consumer then posts the frozen plan. A rejection returns the document to draft. Books never hold an invoice that was not issued, and an issued invoice is never left without books: a required close check blocks the period lock while either can happen. The legal choice is the author's; this is the interim, flagged.
4. **Approval context.** An approval stands while the policy, asked again at posting, requires the same or a lower approval procedure. Otherwise the document goes back for approval without being edited.
5. **Partner snapshot.** Partner data copied onto a document is part of its content when the document is written.

### Rules

**Line identity and references**

1. `Update` submits the full list of lines.
   - **Matching.** Lines are matched to existing rows by `line_number`. A line number is never renumbered and never reused in its document. A new line takes the next unused number; a missing number deletes its row.
   - **IDs.** Row `id`s are stable, and version content still excludes them (ADR-0009 rule 9).
2. Commercial document lines and `demand_supply_line` (ADR-0024 rule 8) refer to other document lines by typed foreign keys. Each key is named after the referenced line table, e.g. `sales_order_line_id`, `transfer_order_line_id`, `goods_receipt_line_id`. A line of the same table referred to as its correction uses `correction_of_line_id` (ADR-0004 rule 12). Production line columns on `demand_supply_line` are added before step 3, flagged for the author ([ADR-0034](0034-production-orders-and-shop-floor.md) rule 9). So is `for_demand_supply_line_id` on supply rows ([ADR-0036](0036-multi-level-mrp.md) rule 9). `production_order_operation_id` on purchase lines and `owner_partner_id` on `demand_supply_line` are flagged likewise ([ADR-0037](0037-subcontracting.md) rules 4, 7).
   - **Roles.** Each table declares its reference roles. Each role allows at most one non-null column, and a role is mandatory where the table declares it.
   - **Execution tables** refer to `demand_supply_line_id` only: `stock_reservation`, `warehouse_task` and pegging (ADR-0023 rules 13–14; ADR-0024 rule 20). This replaces "a demand line" in those rules and cuts the line-reference pairs from about four per line table to one.
   - **Step 3.** As in ADR-0027 rule 7, `demand_supply_line` has from step 3 the nullable columns for every Phase 1 line table (`transfer_order_line_id`, the stock document lines, and `sales_order_line_id`, `purchase_order_line_id`, `purchase_request_line_id`); the foreign key constraints for step 5 tables are added at step 5, so the table does not change. Later line tables (production) are the author's decision under B3.
   - **Lifecycle.** `demand_supply_line` rows are never deleted or rebuilt, are unique per source line and direction, are created before the first reservation, and are closed with `closed_reason` when a line is removed when a change takes force.

   A draft purchase request or order line whose supply row carries `origin_planned_order_id` or pegging cannot be removed (its quantity goes to zero, or the document is canceled, closing the row as `canceled`). Other draft lines removed in draft delete their rows. Rows are never deleted once their document has left draft ([ADR-0047](0047-commercial-documents-and-pricing.md) rule 10).
3. Once another document refers to a line:
   - the line cannot be deleted (`document_line_referenced`);
   - its item, unit and warehouse cannot change (`referenced_line_immutable`);
   - its quantity cannot go below the quantity already fulfilled by referring documents (`quantity_below_fulfilled`).

   Documents in `issuing` count as fulfilling (rule 9).

**Change orders**

4. A document type may declare `is_change_order_allowed`. In Phase 1 these are sales and purchase orders (step 5) and transfer orders (from step 5; at step 3 transfer orders have no change orders). Production orders allow change orders too ([ADR-0034](0034-production-orders-and-shop-floor.md) rule 8).
   - **Storage.** The document keeps `version` = the version in force, and its typed rows stay at that version. A change is stored as the next `document_version` row (rows are never updated, ADR-0009 rule 14). It is pending exactly when `document.pending_version` points to it, and its canonical content is the authority for the change until it takes force. The document records `pending_version` and `change_state`: `none`, `drafting` or `pending_approval`. A replaced or discarded change stays as a version row that never took force, so the version in force may skip numbers.
   - **Step 3 interim.** Before change orders exist for transfer orders (step 5), `Update` of an approved transfer order that has reservations, tasks or fulfillment is rejected (`document_referenced`), so steps 3–4 never orphan execution. The change state columns exist from step 3; turning the flag on at step 5 only enables the commands, so the core table does not change.
   - **Commands.**
     - `Update` of an `approved` document writes or replaces the pending version: `change_state` becomes `drafting`.
     - `Submit` asks the policy and moves it to `pending_approval`.
     - `Approve` makes it the version in force.
     - `Reject` (approver) or `Cancel` of the change (anyone with the type's `Update` permission, including the agent that wrote it; `CancelChange<Type>`) discards it.
     - An `Update` while `pending_approval`, and `Cancel` or `Close` with a pending change, are rejected with `change_pending`.
   - **Content of `version`.** Commands on the pending change carry `pending_version`; other commands carry `version` (ADR-0009 rule 10).
   - **Numbering.** A change has no number of its own; the document keeps its number.
   - **Current version.** For INV-10, "current version" means the version in force. This is a definition, not a change to the invariant, and it is listed for the author.
5. Taking force:
   - **Execution** (reservations, pick release, deliveries, receipts, planning demand) uses the version in force.
   - **Locks and checks.** When the pending version takes force, `Approve` locks the document row and re-checks rule 3 against current fulfillment. Execution commands lock the documents they refer to first (ADR-0027 rule 10, position 1), so take-force and execution never interleave.
   - **Adjustment.** The posting interfaces adjust only lines whose item, quantity, warehouse or date changed, in `line_number` order. Unstarted pick tasks above a new quantity are canceled. Started tasks complete, and the excess goes back to stock by a move task.
   - **Business behavior** (open question): whether execution may continue while a change is pending, and at which price quantities not yet invoiced are invoiced. Interim, flagged: execution continues on the version in force, and the new price applies to quantities invoiced after the change takes force.

**E-invoiced documents**

6. A document type declares `is_e_invoice_capable`. Whether an e-invoice is required for it is the regime's setting (DS-24; ADR-0016). For such a type, with the e-invoice required, the states are `draft → issuing → posted`, and back to `draft` on rejection. Approval hold stays unavailable (ADR-0009 rule 12).
   - **`issuing` is not final.** Header and lines are immutable in it, as in `posted` (ADR-0009 rule 14), because the content has been sent to the tax authority.
   - **Commands allowed in `issuing`:** the outcome commands of rule 7, and `Recall<Type>` (rule 10). Outbound messages use the same pattern with the non-final state `sending` ([ADR-0052](0052-minimal-crm.md) rule 27).

   Note: for types with `is_approval_hold_allowed: regime`, while `documents.issuance_without_delay` is false the approval hold is available, and the states are `draft → pending_approval → approved → issuing → posted`. `Issue<Type>` is allowed only from `approved`, and a rejection returns the document to `draft`, to be submitted again. While the setting is true, this rule applies as written ([ADR-0053](0053-core-neutrality.md) rule 8).
7. The flow:
   1. **`Issue<Type>`** (human or policy-allowed; verb Issue, event form `IssueRequested`; effect class `posting`). The dispatcher asks the policy here, and the decision is stored. The command:
      - runs the package validation of rule 8, and the same period checks and period share lock as `Post` (ADR-0009 rule 13; ADR-0012 rule 9);
      - freezes `posting_date`, which must equal the content's, as with `Post` (ADR-0009 rule 9);
      - resolves the rates (ADR-0011 rule 1) and computes the prospective journal and open items as its plan, with that `plan_hash`;
      - stores the frozen plan, the rates and the hash on a `posting_intent` row (owned by `documents`; one per `Issue` attempt, never reused; state `pending`, `posted`, `reopened` or `recalled`; it also records that the e-invoice was required);
      - requests the e-invoice through `tax.contract.request_e_invoice` (ADR-0027 rule 8);
      - moves the document to `issuing`.

      No journal row, document number or open item is written yet. The result returns state `issuing` and the e-invoice record ID.
   2. **`Record<Type>EInvoiceOutcome`** (verb Record; system, in `tax`) is run by the external consumer (ADR-0013 rule 10). It writes `accepted` (with the e-invoice number and issue date) or `rejected` (with the reason) on the e-invoice record, and always succeeds. It emits `EInvoiceAccepted` or `EInvoiceRejected`.
   3. **On `EInvoiceAccepted`**, a transactional consumer runs `Post<Type>` as actor `system` on behalf of the event's `on_behalf_of_id` (ADR-0013 rule 9). It uses the stored `expected_plan_hash` and frozen rates, and writes the journal, the number, the open items and the e-invoice reference.
      - The policy is not asked again; the decision was taken at `Issue`. Under ADR-0009 rule 12's human-only interim this completion is allowed on behalf of the issuer (ADR-0027 rule 12).
      - Where the e-invoice is required, `Post<Type>` is accepted only from this internal caller, in state `issuing`, with an `accepted` e-invoice record and the stored `expected_plan_hash`; anything else returns `invalid_state_transition`.
      - If posting fails (a changed plan, a soft-locked or locked period, a changed account), the delivery is held with a work item. A human completes it with `Complete<Type>Posting` (verb Complete; `human_only`, effect class `posting`, same preconditions; with `post_in_soft_locked_period` where needed), and corrects it afterwards with an adjustment document if needed. The consumer is idempotent: an already posted document counts as done, so the held delivery resolves.
   4. **On `EInvoiceRejected`**, a consumer runs `Reopen<Type>`, which returns the document to `draft` with the rejection reason and creates a work item for the issuer.
8. Package validation:
   - **The interface.** Before the request, `EInvoiceValidator` checks schema, buyer tax ID format, registered symbol and dates. It is published by the core and implemented by the localization package (ADR-0016 rule 17). It is network-free and deterministic, and runs in simulation and at `Issue`.
   - **Errors.** Failures return `e_invoice_invalid`, with the package's code in `details`.
   - **Dates.** A `posting_date` outside the regime's window (package data) is rejected here. An acceptance whose issue date falls outside the window is held with a work item instead of posting; the posting date is never changed silently.
9. While a document is in `issuing`:
   - it counts toward invoiced quantity (ADR-0009 rule 7) and toward cumulative correction limits (INV-40);
   - it counts in partner exposure (DS-22 composes it with `GetPartnerExposure`, ADR-0026 rule 15);
   - it has no journal entry, number or open item (INV-44).
10. Outages:
    - A document stays in `issuing` during an outage. The intent retries and its deliveries are held with work items (ADR-0013 rule 8).
    - `Recall<Type>` (verb Recall; `human_only`) returns it to `draft` only when the last status recorded on the e-invoice record by the external consumer's status query (ADR-0013 rule 10) is "nothing held". In the same transaction it skips the pending issue delivery, and it is rejected while that delivery is `running`.
11. Close check. ADR-0012 rule 13 gets a required core check task that blocks `LockPostingPeriod` while the period has any document whose `posting_date` falls in it and that is either:
    - in `issuing`, or
    - accepted but not posted.
12. Placement: the two-phase lifecycle is built at step 5 with sales invoices. A deterministic stub adapter accepts or rejects from test data. DS-24 replaces the stub with the provider adapter at step 7, without changing the core. Note (author, 2026-11-15): the provider adapter is an add-on designed after the core, not a step 7 item; the stub stays in the core build and the tests ([backlog](../design/backlog.md), add-ons section).
13. Whether e-invoiced documents may instead post first and be reversed while unissued is the author's (legal; open question). Also the author's:
    - which date governs posting and the e-invoice;
    - what "acceptance" means for invoice kinds without a tax authority code (unverified, spec 08);
    - how cost of goods sold already posted by a delivery is presented while its invoice is in `issuing` across a period end.

**Approval context**

14. Recording and re-checking: Approvals compare by procedure rank ([ADR-0043](0043-policy-and-approval.md) rule 2).
    - **At `Submit`** (and at `Issue` or `Post` from `draft`), the `policy_decision` records the approval procedure required and a `policy_input_hash`. The hash covers the inputs evaluated: amounts in company currency at the rates applied, partner exposure, and price and margin checks.
    - **The approval row** refers to the `policy_decision_id` it satisfies.
    - **At `Post` of an approved document, and at `Issue`**, the policy is asked again when the `policy_input_hash` differs. The existing approvals stand when they satisfy the new decision's procedure (the comparison is DS-28's). Otherwise the command is rejected with `approval_context_changed`, whose `details` give the approved and current amounts and procedures.
    - **Resubmission.** The document may then be submitted again without edit (`approved → pending_approval`).

    Note: the comparison is by stages. Approvals stand when every stage the new plan requires already has its approvals in the round; a resubmission continues the round when the pool stays the same and starts a new one when it changes ([ADR-0055](0055-approval-pools-and-stages.md) rules 8, 11).
15. Payment-type documents (DS-25) carry the beneficiary's `partner_bank_account_id` in their content.

**Partner snapshot**

16. Partner name, address and tax ID (ADR-0019 rule 5) are copied by `Create` and `Update` and are part of the content. Posting never changes them.
    - At `Post` or `Issue`, a snapshot that differs from the partner's master returns the check result `partner_snapshot_stale`.
    - Whether that warns or blocks is business behavior. Interim, flagged: it warns, and for the tax ID on e-invoiced types `Issue` is rejected with `e_invoice_invalid`.

**Checks**

17. Invariants, one statement each:
    - **INV-41:** every line referred to by an open `demand_supply_line` row, or by a line of a document that is not canceled or reversed, belongs to a document that is not canceled.
    - **INV-42:** every accepted e-invoice has a posted document, or an open work item while the posting is held.
    - **INV-43:** `pending_version` is null exactly when `change_state` is `none`, and otherwise is greater than `version`.
    - **INV-44:** a document in `issuing` has no journal entry, number or open item.
    - **INV-45:** no line's quantity is below its fulfilled quantity.
    - **INV-46:** every posted document with a `posting_intent` recording that the e-invoice was required has an accepted e-invoice.
    - **INV-47:** open reservations and unstarted warehouse tasks refer only to open `demand_supply_line` rows.
    - INV-82 is tightened: the approvals must refer to the latest policy decision on the posted version, or satisfy its procedure.
    - EC-56 to EC-58 are held by DS-47.

    Edge cases:
    - **EC-53:** an e-invoice is rejected for a wrong buyer tax ID; the document is corrected and issued again.
    - **EC-54:** an order is changed after partial picking.
    - **EC-55:** rates cross an approval threshold between approval and posting.
    - **EC-59:** a provider outage across a period end blocks the lock until the posting completes.
    - **EC-60:** an invoice is issued with a backdated posting date outside the regime's window.

    DS-17 adds business events `sales_order_changed`, `e_invoice_rejected` and `e_invoice_outage`, raising the log schema to 0.2.0.

## Context

The assessment found five problems:
- **A-1:** the step 3 tables referred to document lines whose identity and reference shape were undefined.
- **O-1, F1:** a posted sales invoice whose e-invoice is rejected was a dead end.
- **O-2, F8:** `Update` of an approved, partly fulfilled order orphaned execution.
- **F7:** approval bound content, not the posting effect or context.
- **C-7:** copying partner data at posting changed approved content.

SAP practice, concepts only: stable item numbers, change documents, release strategies re-triggered on value change, and output-dependent posting.

Vietnamese e-invoicing rules (spec 08) are unverified; the package defines acceptance.

ERPMe's answer keeps three things true:
- the books hold neither unissued invoices nor issued invoices without postings;
- every posting effect is simulated and hashed before a human commits to it;
- approvals hold while the procedure they satisfied still applies.

## Options considered

| Option | For | Against |
| --- | --- | --- |
| `line_number` as identity; execution refers to `demand_supply_line` (chosen) | One reference shape for execution; few FK pairs; stable identity | Line numbers have gaps |
| Typed FKs from every execution table to every line table | Direct | About four columns per line table; step 5 tables absent at step 3 |
| Pending version beside the version in force (chosen) | Execution keeps its basis; one approval path | A second version pointer and a small change state machine |
| `Issue`, then record the outcome, then post by a consumer (chosen as interim) | No unissued invoice in the books; failures never lose an acceptance; plan hashed before commit | Posting is asynchronous for these types |
| Post first, reverse while unissued | Synchronous | Books may hold revenue that never becomes legal |
| Approval valid only for identical inputs | Strict | Any rate move would block foreign-currency documents forever |

## Constraints that come with the decision

- **ADR-0009 notes:** status line; rules 1, 2 (flags `is_change_order_allowed` and `is_e_invoice_capable`), 4 (states `issuing` and change states), 5, 6, 7, 9, 10, 11, 12, 13, 14, 19; "Revisit when" triggered.
- **Other ADR notes:**
  - ADR-0012 rule 13 (the close check);
  - ADR-0013 rule 10 (the outcome recorded first);
  - ADR-0019 rule 5;
  - ADR-0023 rules 13–14 and ADR-0024 rule 20 (`demand_supply_line_id`);
  - ADR-0027 rules 7–8.
- **Registry:** `Issue<Type>`, `Post<Type>` and `Complete<Type>Posting` have effect class `posting`; verbs Issue, Reopen, Record, Recall and Complete are added; `RecordEInvoiceOutcome` is one command in `tax`; the per-type commands are added to ADR-0009 rule 2's list and ADR-0008 rule 1's CI rule.
- **ADR-0011 rule 1:** rates of these types are resolved at `Issue`.
- **ADR-0024 rule 8:** `demand_supply_line` lifecycle.
- **DS-04:**
  - errors `document_line_referenced`, `referenced_line_immutable`, `quantity_below_fulfilled`, `change_pending`, `approval_context_changed`, `e_invoice_invalid`;
  - check result `partner_snapshot_stale`.
- **DS-16:** INV-41 to INV-47.
- **DS-17:** EC-53 to EC-55, EC-59, EC-60, and log schema 0.2.0.
- **Design items:** DS-22, DS-24 (validator, adapter, outcome command), DS-25 (bank account), DS-28 (procedures, input hash).

## Revisit when

- The author decides post-first with reversal for e-invoiced types.
- Change orders are needed for documents other than orders.

## Documents updated

- **ADRs:** [docs/adr/0009-document-lifecycle.md](0009-document-lifecycle.md), [docs/adr/0012-posting-periods-and-closing.md](0012-posting-periods-and-closing.md), [docs/adr/0013-outbox-and-events.md](0013-outbox-and-events.md), [docs/adr/0019-partners-and-crm-foundation.md](0019-partners-and-crm-foundation.md), [docs/adr/0023-warehouse-management.md](0023-warehouse-management.md), [docs/adr/0024-planning.md](0024-planning.md), [docs/adr/0027-cross-cutting-ownership.md](0027-cross-cutting-ownership.md): notes.
- **Design and catalogs:** [docs/design/DS-04-command-envelope.md](../design/DS-04-command-envelope.md), [docs/design/DS-16-invariants-and-harness.md](../design/DS-16-invariants-and-harness.md), [docs/catalogs/invariants.csv](../catalogs/invariants.csv), [docs/catalogs/edge-cases.csv](../catalogs/edge-cases.csv), [docs/design/DS-17-synthetic-dataset.md](../design/DS-17-synthetic-dataset.md), [docs/design/backlog.md](../design/backlog.md).
- **Glossary:** [docs/spec/00-reading-guide.md](../spec/00-reading-guide.md).
- **Open questions:** [docs/open-questions.md](../open-questions.md), covering:
  - the e-invoice posting model, date, acceptance meaning, and cost of goods sold presentation;
  - execution and pricing during a pending change;
  - stale partner snapshot;
  - INV-10's "current version";
  - document numbers following acceptance order.
- **Records:** [docs/adr/README.md](README.md); [docs/runbook/step-log.md](../runbook/step-log.md) at acceptance.
