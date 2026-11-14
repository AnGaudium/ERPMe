# ADR-0031: Design simplifications

Status: accepted (2026-11-14) under ADR-0005, reviewed by Claude Fable 5.2 (builder Claude Opus 5.5). Design item: DS-49 (new). Related decisions: D2, D3, D14. Principles 8, 10, 13. Build principles B3, B8. ADR-0002, ADR-0005, ADR-0008, ADR-0009, ADR-0012, ADR-0013, ADR-0020, ADR-0022, ADR-0023, ADR-0024, ADR-0027, ADR-0028, ADR-0029, ADR-0030. Optimizer findings OPT-01, OPT-03, OPT-05, OPT-07, OPT-08, OPT-10 ([design assessment 1](../reviews/2026-11-14-design-assessment/README.md)).

## Decision

The optimizer proposed six simplifications that touch the plan format, the stock key, the worker design or the shape of exceptions. Each becomes expensive after step 1 or step 3, so each is decided now.

| Finding | Decision |
| --- | --- |
| OPT-01: two canonical hashes | Accepted. The plan also contains the canonical content of the document versions and records a command writes. One `plan_hash` then covers ledger, stock, document and record changes |
| OPT-03: open quantity stored three ways | Accepted for the open delivery or receipt quantity of stock lines, stored once in `demand_supply_line`. Not accepted for reservations: their picked and fulfilled quantities stay stored, because available to promise reads them under the stock lock |
| OPT-05: two stock-key modes | Accepted. Every warehouse has a default bin, `bin_id` is never null, and `ConvertWarehouse` disappears |
| OPT-07: the dated negative-stock check has no data structure | Accepted: `posting_date` on material lines, an index, and a stated algorithm |
| OPT-08: two queue machineries | Not decided here. Procrastinate is ADR-0002's tool choice, which ADR-0005 item 2 reserves for the author. Dropping it is the agent's recommendation in the open questions. Only the consumer queue `jobs` is added now |
| OPT-10: exceptions in three shapes | Accepted: one work item per exception from step 5; lists per buyer or warehouse are queries |

The other optimizer findings are either decided elsewhere (OPT-02 in the adjudication; OPT-11 in ADR-0027), or left to the design item that owns them, or the author's (OPT-12, OPT-13, OPT-21).

### Rules

**One plan hash** (OPT-01)

1. The canonical plan (ADR-0008 rule 12; DS-04 "Canonical plan for hashing") becomes `{"journal_lines", "stock_movements", "document_versions", "record_versions", "result"}`.
   - **`document_versions`:** one entry per document version the command writes: the document ID, `version` and the version's canonical `content` (ADR-0009 rule 9). A pending version of a change order counts (ADR-0028 rule 4).
   - **`record_versions`:** one entry per record written by an allowed-target command (ADR-0029 rule 2): table, ID and the record's canonical fields after the write.
   - **Canonical forms.** Both lists are subject to DS-04 steps 2–3: IDs created in the run become `new:<table>:<n>`, and `DocumentNumber` and `SystemInstant` values are removed. They contain content, not precomputed hashes. The stored `version_hash` and `expected_version` remain hashes of stored values and are a different thing.
   - **Order.** Both lists are in the order the handler wrote the rows.
   - **Outside the hash.** Results listed like events stay outside it, as before (warehouse task proposals, ADR-0023 rule 11; planning run results, ADR-0024 rule 17). Tasks, reservations, `demand_supply_line` rows, open items and events are not in the plan either.
2. The response's `plan` carries both lists, so an agent sees the prices, discounts and taxes that execute will commit. As for journal lines, they are filtered by the actor's field classes, and generated IDs are real IDs outside the hash. Returning an `is_untrusted` field taints the run (ADR-0029 rule 10). The uniform two-call protocol stays.
3. A concurrent edit of the same draft usually gives `version_conflict` first (ADR-0009 rule 10). When it gives `plan_hash_mismatch`, the agent reviews the returned plan and resends with its hash (ADR-0008 rule 13), or reads again and simulates again.
4. DS-16 adds a hash test: a batch whose first item creates a record with a server-generated ID and whose second item refers to it gives equal hashes in simulate and execute.

**One stored open quantity** (OPT-03)

5. The open delivery or receipt quantity of a stock line is stored once, in `demand_supply_line` (ADR-0024 rule 8). Posting interfaces write it in the referring document's transaction (ADR-0028 rule 3), and DS-22's delivery and receipt progress queries read it.
   - **What stays computed.** Invoiced progress (which counts documents in `issuing`, ADR-0028 rule 9), fulfilled quantities (which `quantity_below_fulfilled` needs, ADR-0028 rule 3) and lines without a `demand_supply_line` row are computed from referring documents, as before.
   - **ADR-0009 rule 7** is narrowed to match. INV-63 checks the stored open quantity.
6. `stock_reservation` keeps `picked_quantity` and `fulfilled_quantity` (ADR-0023 rule 13). Available to promise reads them under the `stock_value` lock for every reservation and pick release, so it must not join tasks and deliveries. INV-58 is new: per demand line, the reservations' picked quantities equal the confirmed pick-task quantities, and their fulfilled quantities equal the posted delivery quantities for that line. Production issues and backflush fulfil reservations too, so INV-58 counts them ([ADR-0034](0034-production-orders-and-shop-floor.md) rule 11).

**One stock-key mode** (OPT-05)

7. Every warehouse, of every kind (`physical`, `transit`, `goods_sent`), has a default bin and a default zone, both created by `CreateWarehouse`, and `warehouse.default_bin_id` names the bin.
   - **The default bin.** Code `DEFAULT`, barcode `<warehouse code>-DEFAULT`, type `storage`, and no capacity or mix limits.
   - **Lifetime.** It cannot be deactivated while the warehouse is not bin-managed.
8. `bin_id` is NOT NULL in `stock_quantity`, `material_document_line`, `warehouse_movement` and `handling_unit`.
   - **Who fills it.** In a warehouse that is not bin-managed, clients omit `bin_id` and the handler fills the default bin. A bin given for such a warehouse is rejected with `warehouse_not_bin_managed`.
   - **Handling units.** In `transit` and `goods_sent` warehouses they carry the default bin.
   - **Uniqueness.** The stock key's unique index no longer needs `NULLS NOT DISTINCT` for the bin. It still does for lot or serial, handling unit and owner.
9. `is_bin_managed` keeps its meaning: bins are visible, and putaway, pick, move and replenishment tasks are used.
   - **Not bin-managed.** The warehouse has exactly its default bin, which the UI hides.
   - **Switching.** Only `physical` warehouses may switch. `UpdateWarehouse` (`human_only`) may set `is_bin_managed: true` at any time, together with the `default_receiving_bin_id` and `default_shipping_bin_id` that ADR-0023 rule 1 requires. The default bin then becomes an ordinary storage bin, and stock leaves it by ordinary move tasks. Deliveries created before the switch issue from the default bin.
   - **No way back.** The reverse is not supported.
   - **Removed.** `ConvertWarehouse` and `bin_management_locked`.
10. Bin rows are locked only for capacity, mix and count checks (ADR-0027 rule 10, class 8). A default bin has no limits. In a warehouse that is not bin-managed, count tasks cover items, and the derived bin block of ADR-0023 rule 18 does not apply. Such a warehouse therefore takes no bin lock.
11. INV-56 is restated, which strengthens it: every stock row has a bin of its own warehouse, and a warehouse that is not bin-managed has exactly one bin, its `default_bin_id`.

**Dated negative-stock check** (OPT-07)

12. `material_document_line` gets `posting_date`, copied from its posting document and protected by the append-only trigger. INV-48 checks that it equals the document's posting date.
13. An index on `material_document_line (company_id, item_id, warehouse_id, lot_id, serial_number_id, posting_date) INCLUDE (direction, quantity)` allows the check to run as an index-only scan.
14. The algorithm runs under the `stock_value` lock (ADR-0020 rule 10).
    - **δ.** The document's net quantity change per key. Lines are not checked one by one, and a key with δ ≥ 0 is not checked.
    - **Steps.** For posting date p:
      1. `current` is the key's total from `stock_quantity`, across bins, statuses, handling units and, until non-owned stock first appears, owners (ADR-0030 rule 8). It includes lines already posted with later dates.
      2. Read that key's lines with `posting_date > p`, grouped by date.
      3. For each date d in {p} and those dates, closing(d) = `current` minus the sum of changes dated after d.
      4. Reject with `negative_stock` if min over d of closing(d) + δ < 0.
    - **Cost.** The scan reads every later line of the key. Those lines lie in open periods and in future periods up to `future_posting_periods` (ADR-0012 rule 6), so a backdated posting into an early open period reads more.
    - **Simulate mode.** The helper's in-memory overlay feeds the same computation.

**Consumer queue `jobs`**

15. ADR-0013 rule 6 allows the consumer queue `jobs` beside `events` and `integrations`, for consumers that do long-job work. ADR-0030 rule 9's import chunks are the first. Such a consumer has a lease of its 15-minute timeout (ADR-0022 rule 9) plus one minute. Whether all jobs move onto the delivery machinery is the OPT-08 question for the author.

**One shape for exceptions** (OPT-10)

16. From step 5, every exception is one `work_item` (DS-29) with `kind`, `subject` (table and ID), `evidence` (links to a derivation trace, pegging, task or delivery), `owner` and `due_date`. The claimable unit is the single work item (Principle 8).
    - **Lists are queries.** Lists per buyer, warehouse or close are queries.
    - **Domain rows stay as evidence.** Planning exception rows and short-pick tasks remain.
17. The consumer `planning_work_items` keeps one work item per open planning exception, not per buyer, and closes those that a run no longer raises (ADR-0024 rule 21). The interim of ADR-0023 rule 21 before step 5 stands.

**Checks**

18. Invariants:
    - **INV-48** (new): every `material_document_line.posting_date` equals its posting document's posting date. Area `inventory`, coded in 40–49 because 20–29 is full. First step 3.
    - **INV-58** (new): rule 6. First step 3.
    - **INV-56:** restated by rule 11.

    The DS-16 hash test is rule 4.

## Context

The optimizer's simplifications were left to be decided one by one (assessment README item 6). A builder AI reads every branch and every second mechanism as something to implement and test. Removing them before code is cheaper than at any later point:
- the plan format feeds INV-12, DS-16 hash locks and the generated clients;
- the stock key becomes a data migration after step 3.

OPT-03 is accepted only for open quantities. Moving reservation quantities into joins would put a join across tasks and deliveries on the most contended lock in the system (OPT-02).

OPT-08 is the author's, because it replaces a tool chosen in ADR-0002. The open question carries the agent's recommendation and the points a design would have to settle.

SAP practice, concepts only: every storage location has at least one storage bin in EWM; open quantities are kept on schedule lines. ERPMe takes neither model; it removes the null-bin branch and keeps one open-quantity store.

## Options considered

| Option | For | Against |
| --- | --- | --- |
| OPT-01: canonical content of versions and records in the plan (chosen) | One hash; simulate shows computed values; tokens apply | Larger plans |
| OPT-01: precomputed hashes in the plan | Small | Cannot be tokenized; creates never match |
| OPT-01: execute without hash for drafts | Fewer calls | Two behaviors |
| OPT-05: default bin everywhere (chosen) | No null branch; no conversion command | One hidden bin and zone per warehouse |
| OPT-03 for reservations too | One store | A join on the hottest lock |
| OPT-08 decided here | Done at once | Reserved for the author (ADR-0005 item 2) |

## Constraints that come with the decision

- **ADR notes:**
  - ADR-0008 rule 12;
  - ADR-0009 rule 7;
  - ADR-0013 rules 6 and 13;
  - ADR-0020 rules 3, 8 and 10;
  - ADR-0023 rules 1, 2, 4, 5, 6, 8, 9, 13, 16, 18 and 21, and its command list;
  - ADR-0024 rule 21;
  - ADR-0030 rule 8 (index wording).
- **DS-04:**
  - the canonical plan and the `plan` field;
  - `bin_management_locked` removed;
  - `warehouse_not_bin_managed` restated.
- **DS-16:** INV-48 and INV-58; INV-56 restated; the hash test.
- **Other design items:** DS-09 (default bin and zone; index); DS-22 (progress reads); DS-29 (the exception contract).
- **Open questions:** OPT-08, dropping Procrastinate (ADR-0005 item 2).

## Revisit when

- The author decides OPT-08.
- A warehouse needs many bins without tasks.

## Documents updated

- **ADRs:** [docs/adr/0008-command-envelope-and-registry.md](0008-command-envelope-and-registry.md), [docs/adr/0009-document-lifecycle.md](0009-document-lifecycle.md), [docs/adr/0013-outbox-and-events.md](0013-outbox-and-events.md), [docs/adr/0020-inventory-and-costing-model.md](0020-inventory-and-costing-model.md), [docs/adr/0023-warehouse-management.md](0023-warehouse-management.md), [docs/adr/0024-planning.md](0024-planning.md), [docs/adr/0030-commercial-seams-and-imports.md](0030-commercial-seams-and-imports.md): notes.
- **Design and catalogs:** [docs/design/DS-04-command-envelope.md](../design/DS-04-command-envelope.md), [docs/design/DS-16-invariants-and-harness.md](../design/DS-16-invariants-and-harness.md), [docs/catalogs/invariants.csv](../catalogs/invariants.csv), [docs/design/backlog.md](../design/backlog.md).
- **Counts:** [docs/README.md](../README.md), [docs/design/README.md](../design/README.md), [docs/prompts/runbook-session.md](../prompts/runbook-session.md).
- **Glossary:** [docs/spec/00-reading-guide.md](../spec/00-reading-guide.md): default bin; the verb Convert.
- **Open questions:** [docs/open-questions.md](../open-questions.md).
- **Index and log:** [docs/adr/README.md](README.md); [docs/runbook/step-log.md](../runbook/step-log.md) at acceptance.
