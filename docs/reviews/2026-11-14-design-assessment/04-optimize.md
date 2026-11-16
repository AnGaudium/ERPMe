# NativeFlows design review, part 4: optimizer lens

Snapshot: `the read-only snapshot of commit 9ac727f` (AGENTS.md, README.md, docs/ without archive/ and prompts/). The reconstruction (`01-reconstruction.md`) was used as a map only. Every claim below was checked against the snapshot file it cites. DS-41 (seams for production costing and asset subledgers) is still being drafted, so its absence is not reported.

Lens: over-engineering, duplication, two ways of doing one thing, concepts that could merge, rules that add moving parts without protecting a gate, and performance and operability risks (locks, hot rows, long jobs, replay budgets). Severity says how much rework the simplification saves if it is made now rather than after code exists. Findings marked **author** touch scope or business behavior, which ADR-0005 reserves to the author. For those, this report proposes options and does not decide.

## 1. Verdict

The core is well-sized in the places that matter most:
- one command envelope;
- posting interfaces that run inside the caller's transaction;
- a universal journal with balances kept off the posting path;
- ordering per subject, not a global sequence;
- no broker, ORM or workflow engine;
- task and planning proposals kept out of `plan_hash`;
- one price-difference path that reuses landed cost.

Nothing here forces a redesign of the core (no critical findings). Most findings are cheap to fix before step 1 code and get expensive later. They fall into three groups:

1. **Hashes and rituals that protect nothing.** For draft documents and `Run*` jobs, the simulate-then-execute protocol hashes almost nothing. The thing that actually binds approvals, `document_version.version_hash`, is a second canonical hash that the plan ignores (OPT-01).
2. **The same fact stored in several places.** The open quantity of a demand line is kept three ways (OPT-03). Planning reaches purchasing through an extra table, an extra event and a consumer, because of a layering reading that ADR-0022 itself contradicts (OPT-04). Warehouses have a null-bin mode next to a bin mode (OPT-05). Stock transfers have two posting shapes plus an order type that has no owner (OPT-06). Employees have two homes (OPT-11). Two queue machineries run side by side (OPT-08). Two read paths each implement the same security filter (OPT-09).
3. **Operability on hot rows.** The `stock_value` row per (item, warehouse) is the one lock for receipts, issues, reservations, picks, landed cost and costing. Period-end costing may hold every such row of the company inside a long-job transaction. Under the 5 s `lock_timeout`, every warehouse command fails during close (OPT-02, high). The dated negative-stock check on the posting hot path has no storage or index defined (OPT-07).

Scope is the biggest lever on the one-developer budget. In Phase 1, the proposed warehouse feature list and planning first slice go beyond the roadmap's "lean scope" (OPT-12, author). So does group-currency logic (OPT-13, author).

## 2. Findings summary

| ID | Severity | Scope | Title | Author |
| --- | --- | --- | --- | --- |
| OPT-02 | high | Goods flow | Period-end costing can hold every `stock_value` lock of a company for a long-job transaction | no |
| OPT-01 | medium | architecture | `plan_hash` ignores document versions, so simulate/execute protects nothing for drafts and `Run*` jobs; two canonical hashes | no |
| OPT-03 | medium | O2C | Open quantity of a demand line is stored three ways | no |
| OPT-04 | medium | Demand planning | Planned order → `replenishment_request` → event → consumer → draft is an avoidable hop; ADR-0022 rules 2 and 6 disagree | no |
| OPT-05 | medium | Goods flow | Plain (null-bin) and bin-managed warehouses are two stock-key modes; one implicit bin removes one | no |
| OPT-06 | medium | Goods flow | Transfers: an undefined transfer order plus two posting shapes | no |
| OPT-07 | medium | Goods flow | Dated negative-stock check on the hot path has no storage, column or index | no |
| OPT-08 | medium | architecture | Two queue machineries (`event_delivery` and Procrastinate) with separate retry, lease and stall logic | no |
| OPT-09 | medium | Information flow | Two read paths each enforce record scope and field classes | no |
| OPT-10 | medium | Information flow | Exceptions take three shapes (unassigned tasks, planning rows rolled up per buyer, work items) | no |
| OPT-11 | medium | architecture | Employee has two homes: DS-06 `REFERENCES employee` against ADR-0019 employee partners | no |
| OPT-12 | medium | architecture | Phase 1 warehouse and planning feature lists exceed the lean scope; proposed cut | yes |
| OPT-13 | medium | Finance flow | Group-currency logic and a second CI installation in Phase 1; keep the columns, defer the logic | yes |
| OPT-14 | low | architecture | Reversal and correction: two link columns and a stored `reversed` state needing a trigger exception | no |
| OPT-15 | low | architecture | RLS compares `company_id` as text, so the policy predicate cannot use the company index | no |
| OPT-16 | low | Information flow | `event_delivery` keeps 400 days unpartitioned so replay can deduplicate | no |
| OPT-17 | low | Demand planning | `RunPlanning` as one long transaction blocks buyers and races firming | no |
| OPT-18 | low | architecture | Lock hold times: numbering counters through 1,000-item batches; period share lock per journal line | no |
| OPT-19 | low | Goods flow | Material lines and journal lines use different sign conventions | no |
| OPT-20 | low | architecture | Seven tool distributions, and every step's adapter kept forever | no |
| OPT-21 | low | P2P | Both closed-period landed-cost methods would be built while the author picks one | yes |
| OPT-22 | low | Information flow | Audit log (DS-36) risks becoming a fifth history of each write | no |
| OPT-23 | low | architecture | "Human only" is expressed in four places; agents need one explanation | no |

## 3. Findings in detail

### OPT-02 (high, Goods flow): period-end costing can lock the whole company's stock

**Evidence**
- ADR-0020 r9: value-only inventory lines, including costing adjustments, "go through the same helper, which updates `stock_value`". The helper locks one `stock_value` row per (item, warehouse) that a document touches.
- ADR-0020 r12: costing "posts value-only adjustment documents (one per company and period, or split by item range when large)".
- ADR-0023 r10: reservations, warehouse movements and task confirmations take the same `stock_value` row.
- ADR-0022 r9: `lock_timeout` is 5 s, and long jobs (costing, close tasks) get a 15-minute `transaction_timeout`.
- ADR-0012 r5: costing for period N runs while period N+1 is open for daily work.

**Failure.** One adjustment document per company locks every touched `stock_value` row until commit. While it runs, every receipt, delivery, reservation, pick confirmation and putaway for those items waits 5 s and then fails with `concurrent_update`. With "split by item range when large" undefined, the long-job timeout allows minutes. Close happens monthly while sales and the warehouse keep working.

**Simplification.**
- Make chunking mandatory and bounded: costing posts one adjustment document per item range, sized to a budget (e.g. at most 200 (item, warehouse) pairs or 2 s per transaction).
- Each chunk commits on its own.
- The close task records progress (last item range done), so a crash resumes. A rerun already posts only the difference (ADR-0012 r15).
- The exact solve stays in memory over all areas; only the posting is chunked.

**What it removes:** company-wide stalls during close, and the need for a "close window" with the warehouse stopped.

**Risk accepted:** costing is no longer atomic across items. The `running` close task must block `LockPostingPeriod` until every chunk is done, which is already the rule for required tasks (r12). A partial run is visible as a task that is not done.

**Now or later:** a one-paragraph rule now. Retrofitting resumable chunking into a written costing engine means reworking its transaction structure.

### OPT-01 (medium, architecture): the plan does not contain what drafts compute, and there are two canonical hashes

**Evidence**
- ADR-0008 r12 and DS-04 "Canonical plan": the plan is journal lines, stock movements and result only. "A command with no journal or stock effect has a plan of its result only."
- ADR-0009 r9: every `Update` writes `document_version.content` (canonical JSON) and `version_hash`, and approvals bind to that hash. ADR-0009 never mentions the plan.
- ADR-0023 r11 and ADR-0024 r17: warehouse task proposals and planning results are listed like events and never hashed.
- ADR-0008 Options table: "`expected_plan_hash` optional" was rejected as "two behaviors".

**Consequence**
- For `CreateQuotation`, `UpdateSalesOrder`, `CreatePurchaseRequest`, master-data commands, `RunPickRelease`, `RunPlanning` and `RunForecast`, every client pays two transactions per write. The hash then binds only a result model whose content is chosen per command.
- Prices, discounts or tax amounts that a handler computes on a draft (Principle 13 puts pricing in deterministic code) are not in the plan unless someone puts them in a result model. Simulate therefore does not show the agent the numbers that execute will commit. Meanwhile the hash that really governs the document, `version_hash`, sits outside the plan.

**Simplification (choose one now)**
- **(A, recommended)** Add `document_versions: [{document, version, version_hash}]` to the canonical plan, so one hash covers ledger, stock and document content. The simulate response shows the computed version content. Keep the uniform two-call protocol, which is easiest for agents.
- **(B)** Allow execute without `expected_plan_hash` for command types whose plan has no journal lines or stock movements. The version hash and approval already gate anything that later posts.

**What it removes:** an empty ritual (B), or the gap between what is reviewed and what is committed (A). Either way, one canonical-hash concept instead of two that do not refer to each other.

**Risk accepted:** (A) a concurrent edit of the same draft now yields `plan_hash_mismatch` as well as `version_conflict`. (B) brings back two behaviors.

**Now or later:** the plan format feeds INV-12, DS-16 r15, DS-17 hash locks and generated clients. Changing it after step 1 invalidates all of them.

### OPT-03 (medium, O2C and demand planning): one open quantity, three stores

**Evidence**
- ADR-0009 r7: "Fulfilment progress (quantities delivered or invoiced) is computed from the referring documents, never stored as a state."
- ADR-0024 r8: `demand_supply_line` stores the open quantity per source document line. Documents write it through posting interfaces, and a purchase request's open quantity "falls by what is ordered from it".
- ADR-0023 r13: `stock_reservation` stores `picked_quantity` and `fulfilled_quantity` and a state derived from them.

**Consequence.** Three representations of "how much of this sales-order line is still open" must agree. Every DS-22 command (create, update, approve, cancel, deliver, return, close) has to maintain two stored copies, and three invariants are needed to catch drift. An agent asking "what is still open" gets different answers depending on which table it reads.

**Simplification.**
- Make `demand_supply_line` the single stored open quantity for every demand and supply line. It is already owned by `inventory` and written in the document's transaction.
- DS-22 fulfilment queries read it instead of recomputing from referring documents.
- `stock_reservation` keeps only the reserved quantity and state. Picked quantity is derived from confirmed pick tasks (`warehouse_movement` rows carry `warehouse_task_id`, ADR-0023 r8). Fulfilled quantity is derived from the delivery's material lines.
- Amend ADR-0009 r7 to "fulfilment is computed by one owner (`demand_supply_line`), never stored on the document".

**What it removes:** two stored copies, their write paths in every commercial command, and two drift invariants.

**Risk accepted:** reservation reads need a join or a view. That is fine at SME volumes.

### OPT-04 (medium, Demand planning and P2P): the replenishment hop is not needed

**Evidence**
- ADR-0024 r22: `ConvertPlannedOrder` calls `inventory.contract.request_replenishment`, which writes `replenishment_request` and emits `ReplenishmentRequested`. The `purchasing` consumer then creates draft purchase requests, while `inventory` creates the draft transfer orders. The stated reason is "so every importer imports downward (ADR-0022 rule 2)".
- ADR-0022 r2 says "A module imports only from lower layers". But r6 says "Independence between modules of layers 3 and 4, except their contract", and r4 makes posting interfaces the cross-module mechanism. `inventory` (layer 3) must call `ledger.contract.write_journal_entry` (also layer 3), so same-layer contract imports are already required.
- ADR-0024 r8: "converted planned orders count as supply for the quantity not yet matched by open supply lines carrying their `origin_planned_order_id`". This rule exists only because the drafts appear asynchronously.

**Simplification.**
- Fix ADR-0022 r2 to say what r6 and the ledger calls need: "lower layers, or another module's `contract` in the same layer, acyclic".
- `ConvertPlannedOrder` then calls `purchasing.contract.create_purchase_request_drafts` and `inventory.contract.create_transfer_order_drafts` in its own transaction, as actor and on behalf of the converter.

**What it removes:**
- the `replenishment_request` table and its lines;
- the `ReplenishmentRequested` event and the `purchasing` consumer;
- held-delivery failure modes for this step;
- the window in which a converted order counts as supply through a special rule (the r8 bullet disappears);
- one glossary concept.

**Risk accepted:** `planning` depends on the `purchasing` contract. Nothing in the snapshot makes `purchasing` import `planning`, so no cycle forms. Whether the target is a purchase request or directly a purchase order stays the author's interim, flagged choice (OQ DS-43), and is unaffected.

### OPT-05 (medium, Goods flow): one implicit bin instead of a null-bin mode

**Evidence**
- ADR-0023 r1: `is_bin_managed`, with "Every row of a bin-managed warehouse has a bin; no row of another warehouse has one". `ConvertWarehouse` exists to move stock into bins. Transit and goods-sent warehouses have null bins, and handling units there have a null `bin_id`.
- ADR-0023 r4–r8: the stock key includes bin.
- ADR-0023 r16: a plain warehouse has no tasks, and the reservation goes straight to `fulfilled`.

**Consequence.** Every stock query, check, lock (bin rows come sixth in the lock order), reservation, count and reversal has a null-bin branch. Correctness tests double.

**Simplification.**
- Every warehouse, of every kind, gets at least one bin. `CreateWarehouse` creates a default bin.
- A "plain" warehouse is one with exactly one bin and `uses_tasks = false`. `bin_id` becomes NOT NULL in `stock_quantity`, material lines and warehouse movements.
- Converting to multi-bin is then ordinary moves out of the default bin, so `ConvertWarehouse` disappears.

**What it removes:** the nullable key column, the NULLS NOT DISTINCT handling, the null-bin branches, and `ConvertWarehouse`.

**Risk accepted:** one extra row per warehouse. Users of plain warehouses never see the bin (the UI hides single-bin warehouses).

**Now or later:** this is the stock key, so after step 3 data exists it becomes a data migration.

### OPT-06 (medium, Goods flow): transfers have an undefined order type and two posting shapes

**Evidence**
- ADR-0020 r6: "A transfer posts both stock lines", one document with `transfer_out` and `transfer_in`.
- ADR-0023 r7: through a `transit` warehouse, a transfer takes "two steps".
- ADR-0024 r8 and r22, ADR-0023 r13, glossary "Demand line": the "transfer order" is a demand document that reservations, picks and planning use. ADR-0024 r22: "`inventory` creates the draft transfer orders itself". No ADR, DS item or backlog row defines its type, lifecycle, or relation to the posting transfer. `grep` finds it only in ADR-0023 r13, ADR-0024 and the glossary.

**Consequence.** Three objects move stock between warehouses with no defined link. A one-document transfer cannot be picked under a reservation, because the reservation needs a demand line on an order. The planning output has no target type.

**Simplification.** Use one pattern, the one sales and purchasing already use:
- a transfer order (non-posting, a demand line at the source and a supply line at the destination), owned by `inventory` and specified by DS-22 or an amendment to ADR-0020;
- a transfer issue (posting, from picks, into the route's transit warehouse or straight to the destination);
- a transfer receipt (posting, from transit).

The one-document direct transfer of ADR-0020 r6 survives only as an internal ad-hoc move without order.

**What it removes:** an ownerless concept, and ambiguity about which shape planning, reservations and picks use.

**Risk accepted:** one more document for planned transfers. That is the same cost sales already pays with order plus delivery.

### OPT-07 (medium, Goods flow): the dated negative-stock check has no data structure

**Evidence**
- ADR-0020 r10: "under the helper's lock, a posting is rejected … if … the closing quantity of its posting date or of any later date would fall below zero".
- ADR-0023 r5: this check stays at (item, warehouse, lot), summed over bins, statuses and handling units.
- `stock_quantity` (ADR-0020 r8, ADR-0023 r4) holds only the current quantity.
- `material_document_line` (ADR-0020 r3) has no `posting_date`. That column sits on `journal_entry` and the document.
- ADR-0014 r16 lists no index that serves this check.

**Consequence.** Each posting line needs the sum of changes dated after its posting date for its key, computed while holding the `stock_value` lock. As written, that is a join across documents per line with no supporting index. It is the hottest path in the system.

**Simplification.**
- Denormalize `posting_date` onto `material_document_line`. `warehouse_movement` does not need it, because physical places are checked on their current balance only.
- Add the index `(company_id, item_id, warehouse_id, lot_id, serial_number_id, posting_date)`.
- State the algorithm: for posting date p, check `current_total + delta − max(0, max over d ≥ p of suffix changes after d) ≥ 0`, reading only lines with `posting_date > p`. Those lines are bounded by `future_posting_periods` (ADR-0012 r6) and by open periods.
- In simulate mode the helper's in-memory overlay applies to the same computation.

**What it removes:** an unspecified hot-path query, which an AI builder would otherwise improvise.

**Risk accepted:** one redundant column, protected by the append-only trigger and an invariant (equals the document's date).

### OPT-08 (medium, architecture): two queue machineries

**Evidence**
- ADR-0013 r6–r8: `event_delivery` has its own claim (`FOR UPDATE SKIP LOCKED`), lease (`locked_until`), backoff, `max_attempts`, `held` state and crash reclaim.
- ADR-0013 r13 and ADR-0022 r12: Procrastinate also runs, with its own retry, heartbeat (30 s) and stalled-job detection (5 min). It runs the delivery workers, system jobs, scheduled jobs and the PDF queue.
- ADR-0017 r18: an `nativeflows_claim` role exists for the delivery claim. ADR-0022 r8: Procrastinate's schema is pinned by an Alembic migration.

**Consequence.** Two implementations of "claim, lease, retry, give up" with different semantics, two dashboards of stuck work, two sets of PAR tests (PAR-04 covers only deliveries), and a third-party schema to keep in step with migrations. An agent debugging a stuck job has to know which machine it is in.

**Simplification (choose one)**
- **(A)** Drop Procrastinate. Model system jobs and scheduled runs as rows in one `job_run` table (or as events to a registered `system` consumer), claimed by the same worker loop with the same lease, backoff and `held` semantics. Scheduling is a small periodic loop in `nativeflows worker`.
- **(B)** Keep Procrastinate only for scheduling and the PDF worker. Delivery workers become a plain loop over `event_delivery`, not Procrastinate tasks.

**What it removes:** (A) one dependency, one schema and one retry semantics. (B) the nesting of one queue inside the other.

**Risk accepted:** (A) we own cron-like scheduling, which is about 50 lines plus a test.

### OPT-09 (medium, Information flow): two read paths, two security filters

**Evidence**
- ADR-0008 r1 and r22: registered `Get`/`List` queries go through the dispatcher, with record scope and field classes applied.
- Principle 7 and backlog DS-33: a separate read-only layer of "semantic views, read-only role, time limits, MCP resources".
- ADR-0017 r19: "Record scope and field classes stay in the dispatcher and in the read-only layer's views". ADR-0017 constraints: "DS-33: scope and field classes in semantic views".

**Consequence.** The cost and margin filter, and the branch or warehouse scope filter, get two independent implementations: Python in the dispatcher and SQL in the views. A field-class leak can appear in one and not the other. Agents get two ways to ask the same question.

**Simplification.** One declaration, two generated outputs. Field classes and scope dimensions are declared once, on the schema registry. DS-33 views are generated from it, column lists filtered per field class through generated per-class views or column privileges, and scope predicates generated from the same dimension list. A CI test compares the two outputs on the same fixture. Alternatively, DS-33 exposes only registry queries plus a small set of generated views.

**What it removes:** a second hand-written security implementation.

**Risk accepted:** DS-33 views become less free-form. That is good for agents.

### OPT-10 (medium, Information flow): exceptions take three shapes

**Evidence**
- Principle 8: exceptions are work items with owner, due date and state; "an agent takes a work item by locking it".
- ADR-0023 r21: before step 5, warehouse exceptions are "tasks without assignee … listed by `ListWarehouseTask`".
- ADR-0024 r21: planning exceptions are rows (`planning_exception_kind`), and "one work item per buyer listing that buyer's open exceptions".
- ADR-0013 r8: a held delivery goes to the dashboard and may create a work item.
- DS-29 (work queue) is unwritten.

**Consequence.**
- A per-buyer roll-up is the wrong lock grain. An agent that claims the buyer's work item blocks the human from every one of that buyer's exceptions (Principle 8).
- Exceptions cannot be resolved, traced or measured individually. Shadow-mode metrics in spec 14 are per item.
- Each domain invents its own "attention" store.

**Simplification.** DS-29 defines one contract: an exception is a `work_item` with `kind`, `subject` (table and ID), `evidence` (a link to the derivation trace, pegging or task), `owner` and `due`, one per exception. Lists per buyer, warehouse or close are queries. Domain rows (planning exception, short pick) may stay as evidence, but the claimable unit is the single work item. The ADR-0023 r21 interim is fine as a step 3–4 stopgap.

**What it removes:** the per-buyer aggregation logic in the `planning_work_items` consumer (open and close sets), and three ad-hoc attention shapes.

**Risk accepted:** more rows. That is trivial.

### OPT-11 (medium, architecture): employee has two homes

**Evidence**
- `DS-06-universal-journal.sql` line 58: `salesperson_id uuid REFERENCES employee (id)`, and lines 8–9 list `employee` among tables "defined by their own design items".
- ADR-0014 r9: "`salesperson_id` refers to the employee record … that DS-20 defines".
- ADR-0019 r3: "Employees are partners so that … `salesperson_id` and `buyer_id` … refer to partners with the `employee` role".
- ADR-0018 r3 says `buyer_id` refers to employees "defined in DS-20".

**Simplification.** Decide for ADR-0019, which is newer and owns the topic. In DS-06, `salesperson_id REFERENCES partner (id)`, plus a check that the partner has an active `employee` role (an invariant, since the role can be deactivated later). Fix the wording of ADR-0014 r9 and ADR-0018 r3. There is no `employee` table.

**What it removes:** a phantom table and a contradiction in the core DDL that an AI builder would resolve at random.

### OPT-12 (medium, architecture, author): Phase 1 warehouse and planning scope against the lean budget

**Evidence**
- Roadmap: "Phases 0 and 1 build only what a trading business … needs to operate for real", with platform completion at months 10–12.
- ADR-0023 "Phase 1, proposed" covers handling units (with nesting), putaway rule tables, the staged flow, pick waves, the replenishment job, cycle-count plans, and PAR-06 to PAR-09. OQ DS-42 asks for confirmation.
- ADR-0024 first slice: reorder point, min/max, time-phased netting, transfer routes, and a weekly forecast with seasonal and event indices. The phase is OQ DS-43.

**Proposed cut (options for the author)**

| Keep in Phase 1 | Defer, keeping a schema seat |
| --- | --- |
| Bins and zones; stock statuses; reservations and ATP; pick tasks from demand lines (direct flow); FEFO/FIFO removal; count tasks by bin; returns disposition; printing of pick lists | Handling units (reserve nullable `handling_unit_id` on the key, logic later); putaway rule engine beyond `fixed_bin` plus the default receiving bin; staged flow; pick waves; replenishment job and trigger; cycle-count plans |
| Planning: reorder point and min/max per (item, warehouse); conversion to drafts | Time-phased netting, transfer graph, forecast indices, pegging beyond demand-line pegs |

**What it removes:** roughly half of ADR-0023's rules and PAR-06/07/09; most of ADR-0024's run logic, and the 2-minute performance target.

**Risk accepted:** importers with a seasonal Tết peak plan by hand in Phase 1. Warehouses using pallets track them outside the system.

**Now or later:** decide before step 2 builds the master-data tables for these features.

### OPT-13 (medium, Finance flow, author): defer group-currency logic, keep the columns

**Evidence**
- Spec 07 and spec 05: "optional group currency". Spec 07: "'Built from the start' means the data model supports them; the matching features and UI follow the scope labels."
- ADR-0011 r3, r8, r11, r15, r17: group translation rates, group realized FX and group revaluation are computed "separately".
- DS-16 r18: CI runs two installations (with and without group currency), and the Hypothesis budget of 4 minutes covers both (r21).

**Simplification.** Keep the nullable `group_*` columns and the balancing constraint. Defer the group rate types, group realized FX and group revaluation until a pilot needs them, and run CI on one installation until then.

**What it removes:** about half of the Hypothesis CI budget, and a group branch in every FX rule of DS-25 and step 8.

**Risk accepted:** a foreign-invested pilot would need this logic before go-live. The pilot profile in the roadmap ("trading business of 10–50 people, imports") does not require it.

### OPT-14 (low, architecture): reversal as a kind of correction

**Evidence**
- ADR-0009 r1: `reversal_of_id` and `correction_of_id`.
- ADR-0009 r14: a trigger exception lets `Reverse` change `state` from `posted` to `reversed`.
- ADR-0009 r7: fulfilment is computed, never stored as a state.
- ADR-0009 r21 and r23: reversals cannot be reversed or corrected.

**Simplification.** Use one link, `corrects_id`, with `correction_kind` (`reversal`, `return`, `credit_note`, …). "Reversed" becomes a computed property: a reversal that is not canceled exists. That removes the only trigger exception on final-state rows. The behavior rules (which types, who posts, storno or swapped) stay as decided and flagged.

**Risk accepted:** queries for "reversed documents" join instead of filtering on state.

### OPT-15 (low, architecture): RLS predicate on text

**Evidence.** ADR-0017 r19: policies allow a row "when its `company_id`, compared as text, equals that setting". The special value `installation` forces the text form.

**Consequence.** `company_id::text = current_setting(...)` cannot match the leading `company_id` column of indexes such as `(company_id, account_id, posting_period_id)` (ADR-0014 r16). Any query that relies on RLS for the company filter scans more than it should.

**Simplification.** Use a STABLE function `nativeflows.current_company_id()` that returns uuid or NULL, and `nativeflows.is_installation_scope()` that returns boolean. The policy becomes `company_id = nativeflows.current_company_id()`, or `company_id IS NULL AND nativeflows.is_installation_scope()`. Fail-closed behavior is unchanged.

### OPT-16 (low, Information flow): delivery retention exists only for replay deduplication

**Evidence.** ADR-0013 r15: `done` deliveries are deleted only after `event_retention_days` (400) from an unpartitioned table. ADR-0013 r16: `ReplayEvents` creates deliveries "that the consumer has no delivery for", relying on the unique key.

**Simplification.** Delete `done` and `skipped` deliveries after 7 days. Replay takes an explicit event range for a paused consumer, and a new consumer stores `replayed_through_event_id`. Alternatively, partition `event_delivery` by month like `outbox_event`.

**What it removes:** a large unpartitioned table that sits on the claim path, and daily mass deletes with their bloat.

### OPT-17 (low, Demand planning): planning run transaction shape

**Evidence**
- ADR-0024 r17: one run per company, a 15-minute long-job timeout, and planned orders updated in place by business key (r18).
- ADR-0024 r19: firmed orders are never changed by a run.
- ADR-0022 r9: `lock_timeout` is 5 s.

**Consequence.** While the run's transaction is open, `FirmPlannedOrder` and `UpdatePlannedOrder` on rows the run has touched wait and fail. A user who firms a row the run read as `proposed` races the run's update.

**Simplification.**
- Compute in memory.
- Write per node chunk in short transactions, with `UPDATE … WHERE state = 'proposed'` (a firmed row is skipped and reported).
- Publish the run as complete with `output_hash` at the end, using the run row as the visibility switch.

### OPT-18 (low, architecture): lock hold times

**Evidence**
- ADR-0009 r15: the numbering counter is locked until commit.
- ADR-0008 r20–r21: a batch of up to 1,000 items is one transaction.
- ADR-0014 r12: the journal line trigger reads the period area state row `FOR SHARE` for every line.

**Consequence.**
- A 1,000-document import or close batch holds each series counter for the whole batch (up to 30 s), so every interactive posting of that type times out.
- Repeated row share locks from many transactions create MultiXact churn on 1–4 rows.

**Simplification.**
- Document that posting batches above about 100 documents run as long jobs outside business hours, or are split.
- Take the period share lock once per command in `periods.contract.check_posting` (it is already first in the lock order). Have the trigger only verify state, with a plain read, since the lock is already held in the same transaction.

### OPT-19 (low, Goods flow): two sign conventions

**Evidence**
- ADR-0014 r6–r8: journal amounts are signed, with `side` and `is_storno`.
- ADR-0020 r3 and r7: material quantities are positive, with `direction` and an `is_reversal` flip.

**Simplification.** Signed `quantity` on material lines (in positive, out negative), keeping `is_reversal` as the counterpart of `is_storno`. Then `SUM(quantity)` is the stock, just as `SUM(amount)` is the balance. One rule for agents and invariants.

### OPT-20 (low, architecture): test tooling granularity

**Evidence**
- ADR-0022 r1 and r6, DS-16 §1: seven distributions (`nativeflows_dev`, `nativeflows_events`, `nativeflows_client`, `nativeflows_adapters`, `nativeflows_simulator`, `nativeflows_testkit`, `nativeflows_reference`), each with its own `pyproject.toml`.
- DS-17 r7: "Adapters of earlier steps are kept, so any log can be replayed at any step."

**Simplification.**
- Keep `nativeflows_reference` separate, because stdlib-only independence matters. Merge the rest into one `nativeflows_harness` distribution with import-linter contracts between its subpackages.
- Keep only the current step's adapter, which already maps every event type with `first_step ≤ N`. Earlier adapters live in git history.
- ADR-0008 r23 serves only the current and previous command majors, so old adapters will break anyway.

### OPT-21 (low, P2P, author): build one closed-period landed-cost method

**Evidence.** ADR-0021 r8: `consumer_split` and `stock_coverage` are both regime options. The Vietnam package seeds `consumer_split` unverified.

**Simplification.** Build only the method the author confirms, and keep the other as a documented option. This is the same principle as ADR-0009 r20 ("the core provides both reversal methods"). That one is cheap; this one is not, because `consumer_split` reruns the exact solve over locked periods.

### OPT-22 (low, Information flow): audit is not a fifth copy

**Evidence.** These already record writes: `document_version` (ADR-0009 r9), `approval` and `policy_decision` (r11), `idempotency_record` with stored responses (ADR-0008 r16), and `outbox_event` with actor context (ADR-0013 r2). DS-36's audit record is "never deleted" (ADR-0012 r9, ADR-0017 r8).

**Simplification.** DS-36 should define the audit trail as views over the immutable tables, plus a table only for facts that nothing else records: denials, settings and role changes, period state changes, exports and erasures.

### OPT-23 (low, architecture): "human only" in four places

**Evidence**
- Registry flag `human_only` (ADR-0008 r2).
- Policy outcome "human only" (ADR-0009 r11).
- The interim rule that approval-required on `is_approval_hold_allowed: false` types means human only (ADR-0009 r12).
- Capability `post_in_soft_locked_period` (ADR-0012 r5).
- Hard floors (ADR-0017 r14–r16).

**Simplification.** Keep the mechanisms. DS-28 adds one error detail, `blocked_by: registry | policy | period | segregation | taint`, with the rule reference, so an agent's simulate tells it why and whom to route to. Generic text is not enough for this.

## 4. Business flows

For each flow: (1) whether the design holds enough information (data, rules, owners) for the flow to work end to end; (2) whether it is agentic-first; (3) what this lens adds. "Deferred" means an unwritten DS item owns it, which is not a defect.

### 4.1 CPQ (email intake → quotation → order)

1. **Information.** Not yet complete, but deferred, not defective.
   - Price lists are DS-20; pricing, discounts, promotions and quotation-to-order conversion are DS-22; thresholds are DS-28; the workflow is DS-34.
   - Intake, matching, the untrusted label, `partner_item` mappings, the lifecycle and approval binding are decided (ADR-0019 r12–r17, ADR-0009).
   - Credit-limit and below-cost outcomes are flagged author questions (EC-21, EC-22).
2. **Agentic-first.** Yes, by construction.
   - Deterministic matching that requires sender authentication.
   - A tainted run limited to one partner.
   - The LLM only maps text, and its output passes a deterministic check.
   - Drafts only; humans approve; segregation of duties through `origin_agent_run_id`; humans send.
3. **This lens.** OPT-01: simulating a quotation draft does not show the computed prices or bind them. Fix it before DS-22 writes the quotation result models. OPT-10: intake and quotation exceptions should be single work items.

### 4.2 O2C (order → credit → reservation → pick/pack/ship → invoice → receivable → payment → returns)

1. **Information.** The core is decided: reservations, picks, delivery from picks, stock and journal at `PostDelivery`, the invoice keys, correction documents and return movements. Deferred: document types (DS-22), tax (DS-23), e-invoice (DS-24), open items and payments (DS-25), credit-limit outcome (flagged). Two sequencing items: `open_item` is needed at step 4 (INV-30 and INV-31 have `first_step` 4) but its owner DS-25 is due at step 6, and no invariant covers `gr_ir`. Other parts of this review cover those.
2. **Agentic-first.** Yes. Agents draft; invoices cannot wait in an approval queue (interim human only); corrections are posted by humans (flagged); bank auto-post requires shadow mode and no LLM contribution.
3. **This lens.**
   - OPT-03: three open-quantity stores per order line.
   - OPT-02: close-time stall of every warehouse command.
   - OPT-05: null-bin branches throughout outbound.
   - OPT-07: hot-path negative-stock check.

### 4.3 Demand planning

1. **Information.** Designed in detail: parameters, supplier terms, routes, calendars, the demand and supply read model, forecast, netting, pegging, conversion and exceptions (ADR-0024). The phase and feature list are the author's (OQ DS-43). The transfer order target has no owner (OPT-06).
2. **Agentic-first.** Yes. The run is a deterministic job, with pegging as its derivation trace. The agent proposes parameter changes and forecast adjustments that need approval; a tainted proposal is never approved by policy (r12); sending stays a separate step.
3. **This lens.**
   - OPT-04: remove the `replenishment_request` hop and the special supply rule for converted orders.
   - OPT-10: one work item per exception, not per buyer.
   - OPT-17: transaction shape of the run.
   - OPT-12: whether time-phased netting and forecast indices belong in Phase 1 (author).

### 4.4 P2P (request → PO → receipt with import, customs, landed cost → invoice → GR/IR → payment)

1. **Information.**
   - Decided: receipt movement and keys, customs declaration posting, landed cost (sources, targets, allocation, open and closed modes), the price-difference path through landed cost, and purchase-return movement.
   - Deferred: document types and three-way tolerances (DS-22), tax codes and `import_treatment` (DS-23, flagged), e-invoice intake (DS-24), payments (DS-25).
   - The customs declaration's owning module is not stated in ADR-0022 r2 (a gap noted by the reconstruction).
2. **Agentic-first.** Yes. The purchase-invoice workflow is deterministic first (XML, signature, `partner_item`, three-way match). Mappings proposed by the LLM become rows only after approval, and a human confirms before posting.
3. **This lens.** OPT-21: build one closed-period method. OPT-04 also shortens the request → order chain.

### 4.5 End-to-end information flow

1. **Information.** Decided: inputs through commands, documents, journal and material ledgers, the outbox and consumers, intents for outside calls. Deferred: read models as views (DS-33), reports (DS-26), print (DS-27), audit (DS-36). Spec 07 asks for a consolidated list of synchronous and asynchronous read models, which exists only spread across the ADRs.
2. **Agentic-first.** Yes. Consumers run with the LLM off (ADR-0013 r12). Agent wake-ups go through work items. Taint propagates.
3. **This lens.**
   - OPT-08: one queue machinery.
   - OPT-09: one security declaration for both read paths.
   - OPT-16: delivery retention.
   - OPT-22: audit as views.
   - OPT-01: one canonical hash.

### 4.6 Goods flow in and out

1. **Information.** Decided: movement types, valuation areas, transit and goods-sent warehouses, bins, statuses, tasks, counts, returns disposition, reversal, preliminary price and period-end costing. Deferred: the costing algorithm specification (step 3). Flagged: return and count valuation, the negative-stock time point. Missing: the transfer order (OPT-06).
2. **Agentic-first.** Yes. Task proposals are deterministic rule tables. Every scan is an idempotent command. Agents draft rules and plans. A scan never posts a count difference.
3. **This lens.** OPT-02 (high), OPT-05, OPT-06, OPT-07, OPT-19, and OPT-12 for handling units and the staged flow.

### 4.7 Finance flow (collection to disbursement)

1. **Information.**
   - Decided: the journal model, account determination, FX recognition, realized FX and revaluation rules (logic later), periods, close tasks and closing entries (flagged until TT99 is verified).
   - Deferred: AR/AP, open items, cash and bank, advances, netting (DS-25); VAT (DS-23); statutory reports (DS-26).
   - Not clearly owned: the algorithms for provisions and amortization (reconstruction D.13).
2. **Agentic-first.** Yes. Close and reversal are human only. Close jobs run as system on behalf of the human, can be simulated, and work with the LLM off. Unconfirmed agent auto-posts block close (ADR-0012 r13).
3. **This lens.** OPT-13: group-currency logic (author). OPT-18: lock hold during close and import batches. OPT-14: one correction link.

## 5. What not to simplify

These look heavy but each protects a gate. Keep them:
- `idempotency_record` claimed first in the transaction (ADR-0008 r16);
- strict per-subject event order with `held` blocking (ADR-0013 r7–r8);
- the deferred balance constraint plus append-only triggers (ADR-0014 r11–r13);
- the posting-date binding to the approved version (ADR-0009 r9);
- the stock lock helper as the only writer (ADR-0020 r8);
- the naive recomputation in stdlib `Fraction` (DS-16 r29);
- the outcome oracle (DS-16 r14);
- taint rules (ADR-0013 r11);
- `account_period_balance` kept off the posting path (ADR-0014 r18).

## 6. Files

- Report: this file.
- Map used: `01-reconstruction.md` (claims re-verified against the snapshot).
