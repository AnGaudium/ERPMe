# Adjudication of critical and high findings

Snapshot: the read-only snapshot of commit 9ac727f. I checked every finding against the snapshot itself, not against the assessors or the reconstruction.

## Summary

| Surviving id | Merged | Ruling | Final severity | Reserved for author |
| --- | --- | --- | --- | --- |
| F2 | F-1 | confirmed | high | no (the build-order part of F-1 is the author's) |
| O-1 | F1 | partly | high | yes (legal treatment) |
| A-2 | F3 | partly | medium | no |
| A-1 | none | partly | medium | no |
| O-2 | none | partly | medium | yes (does a changed order stay in force) |
| F5 | none | partly | medium | yes (accounting) |
| F4 | none | deferred_not_defect | medium (requirement for DS-32) | no |
| OPT-02 | none | deferred_not_defect | low | no |

## F2 (merges F-1): the open-item model is needed from step 1 but designed only at step 6. Confirmed, high

- DS-06-universal-journal.sql line 61 declares `open_item_id uuid REFERENCES open_item (id)`. Lines 181-185 hold the step 1 trigger that rejects `receivable` and `payable` lines without `partner_id` and `open_item_id` (ADR-0014 rule 10). The file header says `open_item` is "defined by their own design items".
- invariants.csv: INV-30 (control accounts equal open items), INV-31 (control lines carry an open item) and INV-32 (carrying amounts consistent) all start at step 4.
- Step 4 replays journal lines and opening balances (spec 11 step 4; runbook steps-0-4 WP1). DS-17 `opening_balances_recorded` includes open items, and spec 15 imports AR/AP open items per invoice.
- The only item that designs open items is DS-25, needed by step 6 (backlog). ADR-0010 rule 15 and ADR-0011 rules 15 and 19 also hand open-item kinds, carrying amounts and the book rate to DS-25. DS-16 rule 29 does not add naive open-item results until step 6.
- B3 (spec 11) says adding a document never changes the core. A placeholder `open_item` built at steps 1-4 would therefore have to be redesigned at step 6, and the step 4 gate would have to be rerun.
- Fix: a step 0/1 ADR for the open-item core. It covers the table, kind, due date, amounts per currency, settlement links and the posting interface. DS-25 keeps payments, allocation UX, bank formats and netting.

F-1's other parts are real but smaller:
- Customs recomputation at step 5 while DS-23 logic arrives at step 7 (ADR-0021 rule 10 only produces a check result, `customs_assessment_differs`). Medium.
- Pick lists printed from step 5 (ADR-0023 rules 22 and 24) while DS-27 arrives at step 8. ADR-0023 rule 24 is a proposal that the author amends. Low.
- The credit limit at step 5 can read partner balances from journal lines (`partner_id`) without the full DS-25.

Moving steps in spec 11 and the runbook is the author's call.

## O-1 (merges F1): a posted sales invoice whose e-invoice is rejected or never issued. Partly, high

- ADR-0009 rule 13 posts the invoice (journal, number, immutable) in one transaction. Rule 14 keeps the e-invoice data that arrives later in separate tables. Rule 19 says sales invoices and every e-invoiced document are "never reversible". ADR-0013 rule 10 issues the e-invoice asynchronously through an intent.
- ADR-0013 rule 8 makes the failure visible: a held delivery and a work item for "an e-invoice not issued". Nothing goes wrong silently, so critical is overstated.
- The ERP does have a path: a correction document under ADR-0009 rule 23 (a credit note that fully offsets, posted only by a human, plus a new invoice). No rule says whether that path is legal when no e-invoice exists, or how a "replacement" e-invoice could refer to an original that was never issued.
- EC-27 covers only replaced and adjusted invoices. No edge case covers rejection or an outage.
- The point about backdated dates is partly covered by open questions (VAT period date; e-invoice document date; ADR-0009 rule 16 numbering order).
- High stands: the decision changes ADR-0009, which DS-24 (step 7) cannot override, and sales invoices are built at step 5.
- Fix: deterministic pre-validation by the package during simulation, a "not issued" state on the e-invoice record, and an author question on the legal treatment (reverse while unissued, or correct). Add edge cases for rejection and outage.

## A-2 (merges F3): no carrier for approving master-data changes. Partly, medium

The gap is real:
- Spec 14's guardrail table requires approval for agent changes to master data.
- Spec 07 says the approval engine also serves master data.
- ADR-0019 rule 6 (mapping only after approval), ADR-0019 rule 18 (tax-ID differences "proposed as an update for a human to accept") and ADR-0024 rule 23 ("approval-bound commands") all rely on that approval.
- But approvals, `policy_decision` and segregation of duties bind only to `document_version` (ADR-0009 rule 11; ADR-0017 rules 15 and 16). ADR-0008 rule 5 asks the policy engine only before handlers that post. The DS-28 backlog row says "binding to document version" and never names master data.

The severity is overstated:
- The critic's spoofed-email scenario is already refuted. A run that has read untrusted content cannot change master data (spec 03 rule 1, a hard floor; ADR-0013 rule 11 for tainted events).
- An untainted agent gets only the permissions its agent type declares (ADR-0017 rule 11). DS-32 and DS-34 can simply leave out `UpdatePartner` until a carrier exists.
- The first agent comes after step 4, and DS-28 is due by step 5.
- Nothing decided blocks the fix. A non-posting document type such as `master_data_change` is allowed by ADR-0009 rule 3, and versions, approval and segregation of duties then apply unchanged.

Fix: give the carrier to DS-28 explicitly and widen ADR-0008 rule 5 to registered non-posting action types.

## A-1: references to document lines and line identity across Update. Partly, medium

- ADR-0023 rule 13 (`stock_reservation` for "a demand line") and ADR-0024 rules 8 ("the source document line") and 20 ("target reference") never state the column shape of these references. ADR-0009 rule 9 never says whether `Update` keeps line row IDs (content leaves IDs out, and the typed rows are authoritative).
- No new pattern is needed, though. ADR-0022 rule 7 lets foreign keys cross modules ("foreign keys cross modules and are declared by table name"). ADR-0004 rule 12 names every foreign key `<relation>_id`. So nullable `sales_order_line_id` and `transfer_order_line_id` columns are the obvious, additive form.
- Reservations are created by DS-22 document commands only from step 5 (ADR-0023 rule 13, "Build step"), so a step 3 table does not have to be redesigned.
- Rule 9's content hash is built so that either answer on line identity fits. The real remaining hole is line-level referential safety. Rule 7 protects only document-level references, so a line deleted or renumbered by `Update` could leave reservations, tasks and pegging pointing at nothing.
- Critical is overstated: no money or legal effect, and the fix is additive.
- Fix: DS-22 (or an amendment to ADR-0009) states that line rows keep their `id` across versions, matched by `line_number`, and that a referenced line cannot be deleted. Add a DS-16 invariant.

## O-2: Update of an approved, partly fulfilled order. Partly, medium

- ADR-0009 rule 9 ("Every `Update` ... returns the document to `draft`") narrows the delegation in rule 6. DS-22 can still reject such an Update, or let it run with explicit side effects: document commands call `cancel_stock_reservation` (ADR-0023 rule 13) and write `demand_supply_line` (ADR-0024 rule 8). So the delegation is constrained but not contradicted.
- Only a "change version that stays in force" would need an amendment to ADR-0009, which is a normal path.
- The effect of an Update on reservations, open pick tasks and demand is not stated anywhere. DS-22 must cover it.
- Whether a changed order stays in force is business behavior for the author.

## F5: price difference and landed cost into a soft-locked earlier period. Partly, medium

- The interaction is real:
  - ADR-0021 rule 12 emits the price-difference `landed_cost` "in the same batch" as the invoice.
  - Rule 6 requires an earlier, not-locked receipt period to take the cost (`landed_cost_period_mismatch` otherwise).
  - ADR-0012 rule 5 lets only a human with `post_in_soft_locked_period`, or close jobs, post into `soft_locked`.
  - ADR-0008 rule 20 runs a batch all or nothing.
  - So while the receipt's period is soft-locked, an ordinary accountant cannot post such an invoice.
- Rule 6 fixes a mode per target and gives each landed cost document one posting date. An invoice matched to receipts in several periods therefore needs splitting, and that is not specified.
- The case only arises when the regime maps `price_difference` to inventory.
- The main choice is already an open question, flagged interim: post into the receipt's period, or into the current period as for a locked one.
- Medium: the decision belongs to the author, and the fix is to extend that open question with the soft-lock consequence and the splitting rule.

## F4: taint lives only on events. Deferred, not a defect (medium, as a requirement for DS-32)

- Today `is_tainted` exists only on `outbox_event` (ADR-0013 rules 2 and 11).
- DS-32 (backlog) explicitly owns "data labels" and "untrusted-content tainting", and spec 03 rule 1 already says "all external content is labeled untrusted".
- Nothing decided blocks the fix:
  - `document_version` already records `agent_run_id` and `origin_agent_run_id` on every version (ADR-0009 rule 9; ADR-0017 rule 16), so a draft with tainted ancestry can be found from run records once DS-32 stores taint per run.
  - ADR-0009 rule 14, under which versions are never updated, does not prevent a separate provenance or label table.
- ADR-0024 rule 12 can be evaluated from run records.
- Pass the second-order injection and laundering scenario to DS-32 and DS-33 as an explicit requirement.

## OPT-02: costing locks during the close. Deferred, not a defect (low)

- ADR-0020 rule 12 already allows splitting ("split by item range when large"). Rule 13 defers the adjustment document layout to the step 3 algorithm spec ("The formulas and the adjustment document layout are specified for step 3"; backlog DS-09 "algorithm step 3").
- The exact solve needs no stock locks. Only posting the adjustments takes `stock_value` locks.
- ADR-0022 rule 9 already says work that cannot finish within its timeout is split.
- The step 3 spec should bound the chunk size and make chunks resumable. Nothing decided blocks that.
