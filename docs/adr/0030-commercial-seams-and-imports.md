# ADR-0030: Commercial seams and staged imports

Status: accepted (2026-11-14) under ADR-0005, reviewed by Claude Fable 5.2 (builder Claude Opus 5.5). Design item: DS-48 (new). Related decisions: D5, D16. Principles 5, 9, 13. Build principles B3, B8. ADR-0005, ADR-0006, ADR-0008, ADR-0009, ADR-0010, ADR-0012, ADR-0013, ADR-0014, ADR-0015, ADR-0016, ADR-0019, ADR-0020, ADR-0021, ADR-0022, ADR-0023, ADR-0026, ADR-0027, ADR-0028, ADR-0029. Assessment findings F5/P-3, F9, F12, F13, F14, F18, F20 ([design assessment 1](../reviews/2026-11-14-design-assessment/README.md)).

## Decision

This ADR settles seven seams before the stock key (step 3), imports (DS-21, step 4) and commercial documents (DS-22, step 5) build on them.

| Seam | Decision |
| --- | --- |
| Price differences sent to stock | A posting interface writes them in the invoice's transaction and splits them by receipt period. A receipt period that is not open is treated as closed, whoever posts |
| GR/IR | GR/IR always carries the order price and the order line, so it clears per line when quantities match. Differences go elsewhere, and a difference for goods not yet received waits in an inventory table until the receipt |
| Credit check | One exposure that includes submitted orders, read under the partner lock at order `Submit`; deliveries respect a credit hold instead of a check at `PostDelivery` ([ADR-0047](0047-commercial-documents-and-pricing.md) rule 18) |
| Ownership axis | `owner_partner_id` is reserved now on every stock row and movement, so goods sold but held, and consignment later, need no migration |
| Imports | Up to 1,000 rows: one command batch, unchanged. Larger: a staged `import_batch` posted as a sequence of command batches with per-row state |
| External documents | Deduplicated by business keys that include the company. The e-invoice key is a localization package declaration |
| Pick release | Allocation takes the stock lock |

Accounting and business choices stay with the author, as flagged interims: closed mode for soft-locked receipt periods; receipt valuation when the invoice comes first; the credit check points; deduplication outcomes; goods sold but held.

### Rules

**Price differences sent to stock** (F5, P-3)

1. When account determination sends an invoice-versus-order difference to stock (ADR-0021 rule 12), the purchase invoice handler calls `inventory.contract.adjust_receipt_value`. This replaces "emits in the same batch a `landed_cost`".
   - **Documents.** The interface writes one `landed_cost` per receipt period of the matched receipt lines, with `cost_type` `price_difference`, so ADR-0021 rule 6's one-case check never rejects the invoice.
   - **How they are written.** Directly as `posted`, inside the invoice's transaction and plan, with no policy decision or approval of their own (ADR-0022 rule 4). Each carries `caused_by_document_id`, the invoice. The receipts are locked as referenced documents (ADR-0027 rule 10, class 1), and the documents are numbered at class 11.
   - **Corrections and reversals.** A correction or reversal of the invoice corrects them through the same interface, by `landed_cost_correction` (ADR-0021 rule 9).
   - **Still possible.** `negative_stock_value` (ADR-0021 rule 9) can still reject the invoice.
2. Each document's mode depends on the receipt's period and on the postable period: the first inventory period on or after the receipt's period whose inventory area is `open`. The rule does not depend on who posts.
   - **The receipt's period is open:** open mode (ADR-0021 rule 6), dated on the invoice's posting date when that lies in the receipt's period. When the receipt's period is earlier, the document is dated on that period's last day. When it is later (an invoice backdated before the receipt), it is dated on the posting date of the latest receipt it targets in that period. This ADR picks these days.
   - **The receipt's period is `soft_locked` or `locked`:** closed mode. The document is dated on the invoice's posting date when that lies in the postable period, on the postable period's first day when the invoice is earlier, and on its last day when the invoice is later. For this interface, `consumer_split` (ADR-0021 rule 7) runs over every period from the receipt's period to the one before the postable period, treating soft-locked periods as locked. It reads their movements as posted at that time. A later costing rerun of a soft-locked period does not change a split already posted. These dates and this range replace, for interface-written documents, ADR-0021 rule 6's "first unlocked inventory period" and rule 7's "every locked period".
   - **Status.** Interim, flagged: the existing open question on earlier unlocked periods is extended to soft-locked periods.

**GR/IR** (F12)

3. `journal_line` gets a nullable `purchase_order_line_id` (ADR-0014 rule 9: a new nullable column by ADR).
   - **Foreign key.** The column exists from step 1, and its foreign key to `purchase_order_line` is added at step 5, when the table exists (as ADR-0028 rule 2 does for line references).
   - **Where it is required.** A line on a system account with control kind `gr_ir` (ADR-0014 rule 10, extended) carries it when its document line refers to a purchase order line. From step 5 every `purchase_receipt` and `purchase_return` line and every goods invoice line for ordered goods must refer to one; goods bought without an order are a DS-22 requirement. Before step 5, references are free text (ADR-0027 rule 7), and opening-balance lines on GR/IR (goods received but not invoiced at cut-over) have none, so those lines leave it null. Opening GR/IR lines come through `opening_balance_entry` ([ADR-0044](0044-data-migration-and-export.md) rule 7).
   - **Enforcement.** The posting handlers enforce it, and INV-37 detects violations; the journal trigger cannot see the document.
4. GR/IR always carries the order price:
   - **Price of a quantity.** The GR/IR unit price of a quantity is the order line's price in force when that quantity first posts, by receipt or by invoice. The counterpart posting uses the same price, matched first in, first out per order line. DS-22 details the matching. A purchase return debits GR/IR at returned quantity × the GR/IR price of the receipt it returns, and a credit note on the invoice credits it at the invoice's GR/IR price.
   - **Receipt first.** The receipt debits inventory and credits GR/IR at quantity × GR/IR price. The invoice then debits GR/IR at invoiced quantity × GR/IR price and credits the payable at invoice value. The difference goes as the regime determines `price_difference` (ADR-0015 rule 4):
     - to a price difference account; or
     - to `purchase_cost_clearing`, then to stock through rule 1 for the received quantity.
   - **Invoice first.** The invoice debits GR/IR at invoiced quantity × GR/IR price, credits the payable, and posts the difference as above.
     - Stock-bound differences for quantities not yet received stay in `purchase_cost_clearing`, and the invoice calls `inventory.contract.record_pending_receipt_adjustment`. That interface writes, in the inventory-owned table `pending_receipt_adjustment`, one row per invoice line: `purchase_order_line_id` (foreign key from step 5), the invoice line, the total difference in company currency, the quantity still to receive and the amount still to apply.
     - The goods receipt handler (step 3, `inventory`) consumes the rows for its line's `purchase_order_line_id` (ADR-0027 rule 7; null before step 5, so nothing is consumed then) in its own transaction. Through `inventory.contract.adjust_receipt_value` it writes a posted `landed_cost` with `cost_type` `price_difference`, allocation rows, `caused_by_document_id` the invoice, and the invoice's clearing line as its source, in the receipt's period. It applies amount pro rata to quantity, and the last receipt takes the rest.
     - **Locks.** Rows are read and written only under the purchase order's document lock (ADR-0027 rule 10, class 1), which both the invoice and the receipt take as a referenced document.
     - **Rows never consumed.** A credit note or correction of the invoice reduces its row through the same interface. When the order line closes with quantity still to receive, DS-22 releases the remaining amount from `purchase_cost_clearing` to the price difference account. Interim, flagged with the invoice-first open question. That release carries no valuation class, so it reaches the regime's generic price difference account ([ADR-0039](0039-vietnam-package-tt99.md) rule 8).
     - The table is designed now and stays empty until step 5, so the step 3 handler needs no change later (B3).
   - **Status.** Interim, flagged: the regime might instead value an invoice-first receipt at the invoice price (open question). The company-currency difference between receipt and invoice rates stays with the existing FX open question.

   Matching is by unit positions per order line, each priced once at first posting; postings are differences of rounded cumulative values, so the balance is zero whenever received equals invoiced; returns and quantity credits take the latest positions, which equals the receipt's or invoice's price when the order price never changed; reversals are allowed only for the latest postings of a side ([ADR-0047](0047-commercial-documents-and-pricing.md) rule 13).
5. INV-37 has two parts:
   - every journal line on a `gr_ir` account whose document line refers to a purchase order line has `purchase_order_line_id`;
   - per purchase order line whose received quantity equals its invoiced quantity, net of returns and credit notes, the GR/IR balance in transaction currency is zero.

   First step 5.

**Credit check** (F9)

6. Credit exposure per partner and currency (`credit_exposure`) is the sum of:
   - open receivable items (`GetPartnerExposure`, ADR-0026 rule 15);
   - invoices in `issuing`, which have no open items yet (ADR-0028 rule 9);
   - delivered but not invoiced value;
   - the undelivered value of orders in `pending_approval` or `approved`.

   DS-22 composes it. It differs from partner exposure (ADR-0026), which is the ledger part alone.
7. Credit check points: Credit excess is a condition of the same evaluation, with a seeded rule requiring approval ([ADR-0043](0043-policy-and-approval.md) rules 4, 15).
   - **Where.** At order `Submit` (a policy point, ADR-0029 rule 6) and at `PostDelivery`, when goods leave. Interim, flagged, with EC-21's open question.
   - **How.** The handler locks classes 1–8 of ADR-0027 rule 10, then the partner row (class 9), then reads the exposure. It passes the result to the policy hook through `context.evaluate_policy(input)`, the dispatcher's one hook (ADR-0029 rule 6), called at that point so that inputs read under locks are current. Such commands are registered `is_policy_in_handler` (ADR-0008 rule 1). For them the dispatcher skips its own evaluation and asserts that the hook ran exactly once.
   - **Concurrency.** Two concurrent orders of one partner therefore see each other's exposure.
   - **When the limit is exceeded.** The outcome is the author's (EC-21).

   The check at `PostDelivery` becomes a credit hold on demand rows, set by `sales` in the commands that raise exposure and respected by `inventory` at pick release and delivery (`demand_on_hold`); `PostDelivery` is no longer `is_policy_in_handler` ([ADR-0047](0047-commercial-documents-and-pricing.md) rule 18).

**Ownership axis** (F13)

8. `owner_partner_id` (null for own stock) is reserved now, as a column, on `stock_quantity` (part of its key), `material_document_line`, `warehouse_movement`, `stock_reservation` and `warehouse_task`.
   - **Non-owned stock** is goods sold but held for a customer, or consignment later. It has quantity and no value, so it never enters `stock_value` and leaves INV-20 unaffected. It is not available to promise.
   - **What changes when it first appears.** The dated negative check (ADR-0020 rule 10) and the keys of INV-21, INV-24, INV-50, INV-51 and INV-52 become per owner, and INV-54 counts own stock only, when non-owned stock is first created. A serial stays one physical unit whoever owns it, so the serial rule and INV-22 stay across owners. Until then every row has a null owner.
   - **Index.** The stock key's unique index treats the null owner as one value (`NULLS NOT DISTINCT`), as for handling unit (bins are never null, [ADR-0031](0031-design-simplifications.md) rule 8).
   - **Phase 1** creates no non-owned stock. The columns cost nothing before step 3; adding them after go-live would migrate append-only tables. `owner_partner_id` is also reserved on production order components and outputs and on `demand_supply_line` ([ADR-0037](0037-subcontracting.md) rule 7).
   - **Accounting is the author's** (open question): goods sold but held, and whether delivery and invoice must share a date in Vietnam.

**Imports** (F14)

9. An import is still posted only through simulated command batches, never by an SQL script (spec 15).
   - **Small imports.** An import of up to 1,000 rows (the batch limit, ADR-0022 rule 9) is one command batch, as before. This covers the step 2 gate.
   - **Large imports.** A larger import is an `import_batch` of module `imports`, a new module in layer 5 that reaches domain modules only through the dispatcher:
     1. **File and staging.** The file is stored as an attachment (ADR-0027 rule 2). Its rows are parsed into `import_row` (owned by `imports`): row number, target command type, payload, `state` (`pending`, `posted`, `failed`), `error` and `result_document_id`.
     2. **Validation.** Every chunk of `import_chunk_rows` rows (an installation setting, default 1,000) is simulated as a command batch. A row may refer only to records that exist or to rows of its own chunk (ADR-0006 rule 3). Dependent data is imported as successive batches, for example partners before their open items. Row-level errors are stored with their row numbers. The batch can be posted only when no row is `failed`.
     3. **Posting.** `RunImport`, `ResumeImport` and `AbandonImportBatch` are `human_only`, effect class `posting`. Being human commands, they reset the origin (ADR-0013 rule 2), so an agent can prepare a batch but never post it. `RunImport` posts the chunks in row order. Each chunk is one command batch in its own long-job transaction (15 minutes, ADR-0022 rule 9), run as `system` on behalf of the human, with idempotency key `<batch id>:<chunk number>`, and it sets its rows `posted`. Each chunk is an internal command that emits an event; a consumer of that event on queue `jobs` runs the next chunk, so progress lives in the database. The batch stays `posting` until every row is `posted` and, for opening-balance imports only, the opening balance clearing account is zero. Then it becomes `posted`. Amended for migrations: a batch is `posted` when all its rows are, and the clearing check belongs to `CompleteMigration` ([ADR-0044](0044-data-migration-and-export.md) rules 3, 12).
     4. **Resume.** A failed chunk rolls back alone. Its error is then recorded on its rows in a separate transaction, and the delivery is held (ADR-0013 rule 8). After a fix, `ResumeImport` continues from the first `pending` row, and posted chunks are never re-run.
     5. **While posting.** A batch in `posting` blocks `LockPostingPeriod` for the periods its rows post into, through a required close check like ADR-0028 rule 11 (a note on ADR-0012 rule 13). It does not block other postings.
     6. **Abandon.** `AbandonImportBatch` stops a batch. Documents already posted stay, and the close check keeps blocking until they are reversed, by ordinary commands or DS-21's bulk reversal.
   - **Glossary.** "Every data import is one command batch" becomes "every data import is posted through simulated command batches; large ones are staged in an `import_batch`".

**Natural keys and agent drafts** (F18)

10. External documents get unique business keys, all including `company_id`. A second arrival is rejected with `duplicate_external_document`, naming the existing record, unless stated otherwise. Interim, flagged: reject versus warn is the author's (open question).

    | Document | Business key |
    | --- | --- |
    | Supplier e-invoice | Declared by the localization package (ADR-0016), flagged `unverified`. Vietnam: seller tax ID, form, symbol and number |
    | Bank statement line | Bank account, bank reference, value date and amount. Without a reference, no key applies: an equal line gives the check result `duplicate_suspected` and both are kept |
    | E-mail | Company, `Message-ID` and content hash (ADR-0019 rule 14, beside the mailbox UID); not a unique index on `Message-ID` alone |

    E-mails need extra care:
    - **Message-ID.** A sender controls the `Message-ID`. Intake skips a second message only when its content hash also matches. Otherwise both are kept and the later is flagged `duplicate_suspected`.
    - **Missing header.** Without a `Message-ID`, only the UID applies.
11. Documents an agent drafts store `origin_work_item_id`, `workflow_step` and `draft_ordinal` (a number the step defines) on the shared `document` row (ADR-0009 rule 1). Together with `document_type` they are unique among documents in any state except `canceled`. A second attempt by any run is rejected with `duplicate_draft`, naming the existing draft, so a re-run of a crashed agent does not draft twice.
12. Pick task creation (ADR-0023 rule 14) takes the `stock_value` lock of each item and warehouse (ADR-0027 rule 10, class 6) before reading available bin stock. Two releases therefore never allocate the same units. PAR-11 tests it.

## Context

The assessment found these gaps:
- **F5, P-3:** price differences into earlier soft-locked periods blocked ordinary invoices, and "same batch" was a client construct.
- **F9:** the credit check had no lock and no data.
- **F12:** GR/IR could not be reconciled per line, and invoice-before-receipt was undefined.
- **F13:** there was no seam for goods sold but held.
- **F14:** imports did not fit the batch and timeout limits.
- **F18:** external documents had no natural-key deduplication.
- **F20:** concurrent pick release was not locked.

Both the closed-mode rule and the GR/IR rule are chosen so that the outcome does not depend on who posts, or on the order in which receipt and invoice arrive.

SAP practice, concepts only: GR/IR clearing by purchase order item at order price; special stock for customer-owned and consignment goods; staged data migration with validation runs.

## Options considered

| Option | For | Against |
| --- | --- | --- |
| Interface splitting by receipt period; non-open periods treated as closed (chosen) | Atomic with the invoice; same result whoever posts | Soft-locked splits are not rerun |
| Depend on the actor's soft-lock capability | Uses the period if allowed | Same invoice, different books by user |
| GR/IR at order price, pending adjustment table (chosen) | Clears per line in either order; core stays unchanged at step 5 | One more inventory table |
| Receipt reads the earlier invoice | No table | Upward import from layer 3 to layer 4 |
| Ownership axis reserved on all stock rows (chosen) | No migration of append-only tables | Unused columns in Phase 1 |
| Staged import with per-row state (chosen) | Deterministic chunks; resumable | Staging tables |
| One transaction per import | Atomic | Breaks the 15-minute limit on real migrations |

## Constraints that come with the decision

- **ADR notes:**
  - ADR-0006 and ADR-0008, their import lines (posted through command batches);
  - ADR-0014 rules 9–10 (GR/IR column and requirement);
  - ADR-0019 rule 14 (Message-ID with content hash);
  - ADR-0020 rules 3 and 8 and ADR-0023 rule 4 (owner axis);
  - ADR-0021 rules 6 and 12 (interface, closed mode for non-open periods, pending adjustments);
  - ADR-0009 rule 1 (draft key columns);
  - ADR-0012 rule 13 (import close check);
  - ADR-0022 rules 2 (module `imports`) and 9 (import chunks as long jobs);
  - ADR-0023 rules 8, 13 and 14 (owner column; lock at task creation);
  - ADR-0008 rule 1 and ADR-0029 rule 6 (`is_policy_in_handler`, `context.evaluate_policy`).
- **DS-06:** `purchase_order_line_id` on `journal_line`, with its foreign key at step 5.
- **DS-04:** errors `duplicate_external_document` and `duplicate_draft`; check result `duplicate_suspected`.
- **DS-16:** INV-37; PAR-11.
- **DS-17:**
  - edge cases EC-61 (invoice before receipt), EC-62 (price difference into a soft-locked receipt period), EC-63 (concurrent orders against one credit limit), EC-64 (duplicate supplier e-invoice by two channels, step 7);
  - the undecided list gains EC-63.
- **Other design items:**
  - DS-09: `pending_receipt_adjustment`; owner columns.
  - DS-21: `imports`, `import_row`, resume and bulk reversal; a fault-injection test of resume.
  - DS-22: exposure, check points, GR/IR matching.
  - DS-24 and DS-25: natural keys.
  - DS-34: draft keys.

## Revisit when

- The author decides the soft-locked, invoice-first or credit-point interims.
- Consignment or bill-and-hold enters scope.

## Documents updated

- **ADRs:** [docs/adr/0006-id-and-numeric-model.md](0006-id-and-numeric-model.md), [docs/adr/0008-command-envelope-and-registry.md](0008-command-envelope-and-registry.md), [docs/adr/0009-document-lifecycle.md](0009-document-lifecycle.md), [docs/adr/0012-posting-periods-and-closing.md](0012-posting-periods-and-closing.md), [docs/adr/0014-universal-journal.md](0014-universal-journal.md), [docs/adr/0019-partners-and-crm-foundation.md](0019-partners-and-crm-foundation.md), [docs/adr/0020-inventory-and-costing-model.md](0020-inventory-and-costing-model.md), [docs/adr/0021-landed-cost.md](0021-landed-cost.md), [docs/adr/0022-repository-and-engineering-conventions.md](0022-repository-and-engineering-conventions.md), [docs/adr/0023-warehouse-management.md](0023-warehouse-management.md), [docs/adr/0029-proposals-and-agent-safety.md](0029-proposals-and-agent-safety.md): notes.
- **Design and catalogs:** [docs/design/DS-06-universal-journal.sql](../design/DS-06-universal-journal.sql), [docs/design/DS-04-command-envelope.md](../design/DS-04-command-envelope.md), [docs/design/DS-16-invariants-and-harness.md](../design/DS-16-invariants-and-harness.md), [docs/catalogs/invariants.csv](../catalogs/invariants.csv), [docs/catalogs/edge-cases.csv](../catalogs/edge-cases.csv), [docs/design/DS-17-synthetic-dataset.md](../design/DS-17-synthetic-dataset.md), [docs/design/backlog.md](../design/backlog.md).
- **Counts:** [docs/README.md](../README.md), [docs/design/README.md](../design/README.md), [docs/prompts/runbook-session.md](../prompts/runbook-session.md).
- **Glossary:** [docs/spec/00-reading-guide.md](../spec/00-reading-guide.md).
- **Open questions:** [docs/open-questions.md](../open-questions.md), on soft-locked receipt periods, invoice-first valuation, credit check points, deduplication outcomes, goods sold but held, and the spec wording on imports.
- **Index and log:** [docs/adr/README.md](README.md); [docs/runbook/step-log.md](../runbook/step-log.md) at acceptance.
