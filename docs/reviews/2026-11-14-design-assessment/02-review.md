# NativeFlows design review, part 2: reviewer lens (completeness and consistency)

Snapshot: `the read-only snapshot of commit 9ac727f` (AGENTS.md, README.md, docs/ without archive/ and prompts/). The reconstruction (`01-reconstruction.md`) was used as a map only. Every claim below was checked against the snapshot text; citations are `file: rule n` (ADR rule numbers) or the catalog row. DS-41 (seams for production costing and asset subledgers) is being drafted and is not treated as missing.

Severity scale (from the brief): **critical** = would force a core redesign after code is written; **high** = a flow cannot work as designed or a principle is violated; **medium** = a gap that a later DS item must close but nobody owns, or the ownership is ambiguous; **low** = clarity.

"Deferred" means a written backlog item owns the point and nothing decided blocks it. Deferred points are not counted as defects.

---

## 1. Verdict

The core is coherent and agentic-first where it is decided: one command layer with simulate/execute, `plan_hash` and idempotency (ADR-0008); document versions with approvals bound to `version_hash` and segregation of duties through `origin_agent_run_id` (ADR-0009, ADR-0017); an append-only universal journal; material documents with movement types and determination by transaction key (ADR-0014, 0015, 0020); landed cost with exact allocation and traces (ADR-0021); warehouse management and planning as deterministic jobs whose proposals are kept out of the hash (ADR-0023, 0024); an outbox with taint propagation (ADR-0013); and country rules kept in packages with `unverified` flags (ADR-0016). Error codes are consistent: every error code an ADR uses is in the DS-04 catalog, except the loader-only `regime_setting_in_use`.

The design is **not ready for step 3 and step 5 code** until four points are fixed:

1. **Document-line references (critical).** How documents refer to each other's lines, and whether a line keeps its identity when the document is updated, is not defined. Yet tables built at step 3 already key on such references.
2. **Master-data approval (high).** No mechanism exists for approving master-data changes. Today approval works only for documents, yet every agent workflow proposes master data.
3. **Build order (high).** Open items, payment terms, tax logic and printing are needed at steps 4–5, but their design items are scheduled for steps 6–8.
4. **Rejected e-invoices (high).** A sales invoice whose e-invoice is rejected has no legal correction path.

Most other flow gaps are correctly deferred to DS-20, 22, 23, 24, 25, 26, 28, 29, 32, 33 and 34.

## 2. Architecture findings

### A-1 (critical): document-line references and line identity are undefined
- Several step 3 core tables refer to "a document line" of another document type:
  - `stock_reservation` and `warehouse_task` refer to "a demand line (a sales order or transfer order line)" (ADR-0023 rules 13, 14);
  - `demand_supply_line` holds "the source document line" (ADR-0024 rule 8);
  - `pegging` holds a "target reference" (ADR-0024 rule 20);
  - INV-62 needs "every document line created from a converted planned order".
- Other decided rules also need line-level links between documents of different types:
  - fulfilment is "computed from the referring documents" (ADR-0009 rule 7);
  - correction documents copy "the lines to correct" (ADR-0009 rule 23);
  - three-way match and partial fulfilment (spec 11, step 5).
- ADR-0009 rule 1 gives lines only `line_number`, and the ADR's options table rejects polymorphic `(document_type, document_id)` references for documents. Nothing says how lines are referenced: no shared line table, no `(document_id, line_number)` convention, no FK rule.
- Nothing says whether `Update` keeps line IDs or replaces the line rows. ADR-0009 rule 9 excludes line IDs from the version content.
- **Impact.** Step 3 (ADR-0023 rule 24) builds reservations and pick tasks before DS-22 exists. If DS-22 later chooses "Update rewrites lines", or a different reference shape, the reservation, task, demand/supply, pegging and correction tables must be redesigned.
- **Fix.** Decide now in an amendment to ADR-0009: line rows keep their `id` across versions, matched by `line_number`; lines are referenced as `(document_id, line_id)` with a real FK through a shared `document_line` key table, or one typed column per referencing pair. Add an invariant that referenced lines are never deleted.

### A-2 (high): master-data changes have no approval mechanism
- Spec 14 requires approval when an agent changes master data (partner, item, price). Spec 07 says the same approval engine serves master data. ADR-0019 rule 6 (`partner_item` row only after approval), ADR-0019 rule 18 (tax-ID differences "proposed as an update for a human to accept") and ADR-0024 rules 1 and 23 (planning parameters and lead times await approval) all rely on it.
- Every decided approval mechanism, however, is bound to a document:
  - `policy_decision` and `approval` refer to `document_version_id` (ADR-0009 rule 11);
  - segregation of duties scans `document_version` (ADR-0017 rule 16);
  - INV-17 checks documents only;
  - the dispatcher asks the policy engine only "before a handler that posts" (ADR-0008 rule 5);
  - DS-28's scope is "binding to document version" (backlog).
- **Impact.** An agent whose type includes `UpdatePartner` or `CreatePartnerItem` executes it directly; "agents propose, humans approve" is not enforced for master data. No item owns this.
- **Fix.** Assign it to DS-28 with an explicit model, e.g. a non-posting document type `master_data_change` whose approval applies the change, so versions, segregation of duties and INV-17 reuse ADR-0009. Extend the dispatcher's policy hook to non-posting commands that DS-28 lists.

### A-3 (medium): the policy engine's call point contradicts itself
- ADR-0008 rule 5: the dispatcher asks the policy engine before any posting handler, and "handlers never do these checks themselves".
- ADR-0009 rule 11:
  - `Submit` (a non-posting command) asks the policy engine and stores a `policy_decision`;
  - `Post` of an `approved` document "does not ask the policy again";
  - `Post` from `draft` asks and stores.
- ADR-0013 rule 9: consumer commands go through the same checks.
- **Impact.** It is unclear who writes `policy_decision` and whether `Post` is evaluated twice. The dispatcher is built at step 1 and DS-28 at step 5, so this is a rework risk.
- **Fix.** Specify one hook: the dispatcher evaluates policy for registered "policy points" (`Submit`, `Post`, the non-posting commands of A-2) and hands the decision to the handler, which persists it. `Post` of an `approved` version skips evaluation and records that in the plan.

### A-4 (medium): ownership and layer placement of cross-cutting tables
These rows are referenced across modules but no module owns them, or the owner is in a layer above the tables that point to them (ADR-0022 rules 2 and 7: one owning module per table; imports only go downward).

| Table | Problem |
| --- | --- |
| `open_item` | `journal_line.open_item_id` (ledger, layer 3) points to it, yet AR/AP sits with DS-25 (the likely owner is `cash`, layer 4) |
| `derivation_trace` | Used by ledger, inventory and landed cost; no owner |
| `agent_type`, `agent_run` | `document_version`, `outbox_event` (layer 2) and `permissions` (layer 2) depend on them, while `agents` is layer 5 |
| `work_item` (DS-29) | No module in ADR-0022 rule 2 |
| Attachment store | ADR-0009 rule 3 assigns attachments to DS-36; ADR-0018 ("Images and documents: owner to be assigned, no backlog item yet") and ADR-0019 rule 12 say unassigned; the DS-36 backlog row says nothing about attachments |
| `customs_declaration` | No module |
| Audit record | DS-36, no module |

- **Fix.** Add a module-ownership table to ADR-0022, e.g. `open_item` in `ledger`, `derivation_trace` in `ledger` or a platform module, `agent_run` in `permissions`, `work_item` in a new platform module. Assign attachments to one DS item; the store also receives e-invoice XML, bank files and e-mails.

### A-5 (medium): master tables used by FK but never defined, and the `employee` conflict
- DS-06 SQL declares `salesperson_id REFERENCES employee (id)` and lists `employee` among tables "defined by their own design items".
- ADR-0019 rule 3 makes employees partners with the `employee` role and says `salesperson_id` and `buyer_id` refer to partners. ADR-0014 rule 9 says "the employee record that DS-20 defines".
- `company`, `branch`, `cost_center` and `project` are FK targets in DS-06 but are defined nowhere. Only ADR-0014 rule 9 points to DS-20 for cost centers and projects, and the DS-20 backlog row does not list them; `company` columns are scattered over ADR-0007, 0011, 0012, 0015 and 0016.
- **Fix.** Change DS-06 to `REFERENCES partner (id)`, and add `company`, `branch`, `cost_center` and `project` to the DS-20 row with a step-1 deadline for `company` and `branch`.

### A-6 (medium): the shipped catalog breaks a CI rule of ADR-0015
- ADR-0015 rule 2 says a key may share its code with a system account "only when every account it requires is that account or a descendant of it… CI checks this rule". It even names `price_difference` as an example.
- In `transaction-keys.csv`, three keys break the rule:
  - `price_difference` also requires `inventory_raw_material`, `inventory_merchandise` and the other inventory accounts;
  - `fx_gain_unrealized` and `fx_loss_unrealized` also require `fx_difference_equity`.
- None of these is a descendant of the account the key is named after, so the step 0/1 CI check fails on the catalog as shipped.
- **Fix.** Rename the keys (e.g. `invoice_price_difference`, `fx_revaluation_gain`) or relax rule 2 for keys whose alternatives are the regime's choice (rule 4).

### A-7 (medium): hard floors and approvals have no invariants
- ADR-0003 R8 makes "every hard-floor test green" part of an agent's "done", yet `invariants.csv` covers only segregation of duties (INV-17). There is no INV for:
  - (a) no document whose version has a tainted origin run was posted by an agent or system actor, and no master data was changed or message sent from a tainted event (spec 03 rule 1; ADR-0013 rule 11);
  - (b) no `human_only` command was executed by an agent or integration (ADR-0008 rule 2);
  - (c) every posted document whose `policy_decision` required approval has an `approved` approval on the posted version (ADR-0009 rule 11);
  - (d) the `gr_ir` control kind. ADR-0010 rule 5 says control kind says "what an invariant can check", and none checks GR/IR;
  - (e) `demand_supply_line` and `stock_reservation` match the open quantities of their source documents. Both are read models written by documents (ADR-0024 rule 8; ADR-0023 rule 13).
- **Fix.** Add INV rows. Removing or weakening invariants is reserved; adding them is technical.

### A-8 (low): the global lock order omits locks the ADRs take
- ADR-0022 rule 10 and ADR-0023 rule 10 list: period, task, handling unit, `stock_value`, `stock_quantity`, bin, numbering, `event_subject`. Not in the list:
  - the `document` row, which ADR-0009 rule 10 says is locked "first" and so contradicts "period rows first";
  - the `account` row locked by the `has_posting` trigger (ADR-0014 rule 12);
  - the `idempotency_record` key wait (ADR-0008 rule 16);
  - the planning state row (ADR-0024 rule 17);
  - future `open_item` rows (DS-25);
  - work-item claims (DS-29).
- **Fix.** Register every lock with its position.

## 3. Flow assessments

Each flow answers two questions:
- **Information:** does the design hold the data, rules and owners for the flow to work end to end?
- **Agentic-first:** do agents propose with evidence while deterministic code executes, policy or humans approve, everything is traceable, and no LLM sits in the decision path?

### 3.1 CPQ (intake → lookup → quotation → pricing → discounts and promotions → approval → order)

| Step | Status |
| --- | --- |
| E-mail intake, deterministic partner match, untrusted interaction, work item, tainted run | Designed (ADR-0019 rules 12–16; ADR-0013 rules 11–12; ADR-0017 rule 12). Connector deferred (DS-24/35); work item deferred (DS-29) |
| Item mapping (stored mapping → fuzzy → LLM) | Mapping storage designed (ADR-0019 rule 6); its approval has no mechanism (A-2) |
| Item, price and stock lookup | Stock queries designed (ADR-0023 rule 13). Price lists deferred to DS-20; discounts and promotions to DS-22; nobody owns the pricing procedure itself (C-3) |
| Quotation document, versions, approval, numbering | Lifecycle designed (ADR-0009 rules 6, 8, 11); type deferred to DS-22; approval conditions deferred to DS-28; EC-21/EC-22 are the author's |
| Sending | Designed: a draft, then human send through an intent consumer, with consent check (ADR-0019 rule 17). PDF needs DS-27, scheduled for step 8 while quotations ship at step 5 (F-2) |
| Quotation → order | Deferred to DS-22 (no rule on copy, closing or reference); depends on A-1 |

- **Information:** not yet sufficient. Price determination and its trace have no single owner (C-3, C-4).
- **Agentic-first:** yes in structure; the agent only drafts and a human sends.
  - Weak point 1: the tainted run's read scope is ambiguous (C-5).
  - Weak point 2: mapping approval has no mechanism (A-2).
  - Weak point 3: the edge-case catalog has no injection or spoofed-sender case (C-6).

### 3.2 O2C (order → credit check → reservation → pick, pack, ship → delivery → e-invoice → receivable → receipt → returns and credit notes)

| Step | Status |
| --- | --- |
| Sales order lifecycle | Designed (ADR-0009 rule 6); type deferred to DS-22; editing an order in force is contradictory (O-2) |
| Credit check | Deferred to DS-22/28; the outcome is the author's (EC-21). Needs AR balances, which need open items at step 5 (F-1) |
| Reservation, pick release, tasks, short pick, delivery from picks, goods issue, COGS | Designed (ADR-0023 rules 13–16; ADR-0020 rules 3–11; `sales_issue` row in movement-types.csv) |
| Sales invoice, e-invoice | Keys designed (transaction-keys.csv); document deferred to DS-22; tax deferred to DS-23; adapter deferred to DS-24. **Rejection path is a defect (O-1)** |
| Receivable, payment receipt, bank matching | Deferred to DS-25 and DS-34; open-item timing defect (F-1) |
| Returns, credit notes | Mechanism designed (ADR-0009 rule 23; ADR-0023 rule 19); cost flagged; document deferred to DS-22/24; EC-20 is the author's. Under a single `correction_of_id`, a return after invoicing needs two corrections (delivery and invoice); DS-22 must say so |

- **Information:** stock and warehouse are complete. The commercial and AR parts are deferred, except O-1, O-2 and F-1.
- **Agentic-first:** yes. Auto-posting is limited to deterministic bank matching after shadow mode, but the confirmation record for auto-posts has no owner (X-1).

### 3.3 Demand planning
- Parameters, demand/supply read model, forecast, netting, planned orders with pegging, firm fence, exceptions, conversion through `inventory.contract.request_replenishment` and the `purchasing` consumer: designed (ADR-0024).
- The building phase and the feature list are the author's (OQ, DS-43).
- **Information:**
  - the transfer order is a defect: it has no owner (P-1);
  - forecast history from goods-sent warehouses is inconsistent (P-2).
- **Agentic-first:** strong.
  - Runs are deterministic, with input and output hashes.
  - Tainted forecast adjustments are never approved by policy (ADR-0024 rule 12).
  - Conversion creates drafts as actor `system`.
  - Gap: parameter changes proposed by agents depend on the missing master-data approval mechanism (A-2).

### 3.4 P2P (request → PO → receipt incl. import, customs and landed cost → supplier invoice → GR/IR → payment)

| Step | Status |
| --- | --- |
| Request, PO | Deferred to DS-22 |
| Goods receipt (`purchase_receipt` → GR/IR), putaway, quality inspection | Designed. Before step 5 the host document is undefined (F-3) |
| Customs declaration, taxes, proposed landed cost | Designed (ADR-0021 rules 10–11). Its module is unassigned (A-4). Its recomputation needs DS-23 logic at step 5 (F-1) |
| Freight invoice → `purchase_cost_clearing`, landed cost open/closed modes | Designed (ADR-0021 rules 1–9, 12) |
| Supplier invoice, price difference | Mechanism designed, but "emits in the same batch" is ambiguous and can block posting (P-3) |
| GR/IR clearing and residuals | Deferred to DS-22; no invariant (A-7) |
| Purchase return | Core designed; value after landed cost flagged (OQ) |
| Payment | Deferred to DS-25 |

- **Information:** sufficient for the stock and value side; P-3 and F-1 must be fixed.
- **Agentic-first:** yes. The purchase invoice agent drafts from e-invoice XML; the LLM only suggests unmapped items; mappings need approval (A-2).

### 3.5 End-to-end information flow
- **Inputs:**
  - e-mail is designed;
  - e-invoice XML is deferred (DS-24);
  - bank files are deferred (DS-25);
  - exchange rates are designed;
  - migration files are deferred (DS-21).
  - Gap: attachments have no owner (A-4).
- **Commands, documents, journal and material ledgers, events:** designed.
- **Read models:** `stock_*`, `demand_supply_line` and `account_period_balance` are designed individually. The list of synchronous and asynchronous read models that spec 07 requires has no owner (X-3).
- **Outputs:**
  - statutory books: DS-26;
  - e-invoices: DS-24;
  - 01/GTGT: DS-23;
  - agent answers: DS-32/33;
  - audit: DS-36;
  - full data export (spec 15) and management reporting (OQ partners' questions): no owner (X-3).
- **Traceability:** strong for actors (`origin_agent_run_id` on versions and events). For derived values it covers costing only (C-4).

### 3.6 Goods flow
- Receipt, putaway, statuses, bins, handling units, transfers (direct and through transit), goods-sent, picking, counts with stored book quantity, scrap and disposition, reversal with bins, negative-stock checks, periodic actual costing, landed cost: designed (ADR-0020, 0021, 0023).
- **Defects:**
  - the transfer order has no owner (P-1);
  - the host document types for step 3 are unnamed (F-3);
  - the rules disagree on whether goods receipts and deliveries can be reversed (L-3).
- No movement type or key exists for issuing promotional goods free of charge (part of C-3).

### 3.7 Finance flow (collection to disbursement)
- **Designed:**
  - FX at recognition, applied rates, realized FX rule, revaluation rule (ADR-0011);
  - periods, area states, close tasks, closing entries (ADR-0012);
  - general journal (ADR-0014 rule 3);
  - the rule that subledger views equal control accounts (ADR-0014 rule 17).
- **Deferred:** AR/AP, cash and bank, advances, netting, payment terms and the currency-exchange clearing account (DS-25); VAT (DS-23); statutory reports (DS-26).
- **Defects:**
  - open items and payment terms are needed before DS-25 (F-1);
  - provision, bad-debt and write-down computations have no owner (X-2);
  - the auto-post confirmation record has no owner (X-1).
- **Agentic-first:**
  - close tasks are `human_only`;
  - jobs run as `system` on behalf of the human who started them;
  - unconfirmed auto-posts block the close by rule, but there is nothing yet to count them with (X-1).

## 4. Flow findings (detail)

**O-1 (high): a rejected or never-issued e-invoice has no correction path**
- The sales invoice is posted, numbered and immutable first (ADR-0009 rules 13–14). The e-invoice is issued afterwards by an outbox intent and an `external` consumer (ADR-0013 rule 10); a held delivery only creates a work item (ADR-0013 rule 8).
- Sales invoices and "every document issued as an e-invoice" are never reversible, and are "corrected by adjustment or replacement invoices" (ADR-0009 rule 19; spec 08).
- If the provider or the tax authority rejects the invoice (e.g. an invalid buyer tax ID), no e-invoice exists to adjust or replace, and the posted invoice can be neither reversed nor edited. No edge case covers this.
- **Fix:**
  - pre-validate in simulation with deterministic package checks;
  - define a "not issued" state of the e-invoice record, which allows reversal of the unissued invoice;
  - ask the author for the legal treatment (reserved, ADR-0005 item 1);
  - add an edge case.

**O-2 (high): editing an order in force contradicts its own delegation and orphans downstream rows**
- ADR-0009 rule 9: "Every `Update` … returns the document to `draft`, voiding any submission or approval."
- ADR-0009 rule 6 delegates "what an `Update` of an approved order that is partly fulfilled does" to DS-22, which cannot choose otherwise without amending rule 9.
- After such an update, the order is no longer in force (rule 6) and no longer counts as demand (ADR-0024 rule 8: "states after `draft`"). Yet its reservations, open pick tasks and pegging remain (ADR-0023 rules 13–14).
- **Fix:** amend rule 9 for non-posting types: either a change version that stays in force, or an explicit `Update` effect on reservations, tasks and demand lines, decided with A-1.

**F-1 (high): items needed at steps 4–5 are scheduled for steps 6–8**
- Every receivable or payable line needs `open_item_id`, enforced by a trigger (ADR-0014 rules 10, 12). INV-30 and INV-31 have `first_step` 4. Step 4 imports AR/AP open items (spec 15; DS-17 `opening_balances_recorded` payload; runbook step 4, work package 1). Step 5 posts sales and purchase invoices. But DS-25, which owns `open_item`, is "needed by step 6", and DS-16 rule 29 puts the naive open-item check at step 6.
- `payment_term` is DS-25 (step 6), yet `customer_profile.payment_term_id` exists at step 2 and invoices need due dates at step 5.
- The credit limit is in scope at step 5 (spec 11) and needs AR balances.
- The customs declaration "recomputes" taxes at step 5 (ADR-0021 rule 10), while DS-23 logic is scheduled for step 7.
- Pick lists on paper "from step 5" (ADR-0023 rule 22) need DS-27, scheduled for step 8.
- **Fix:** split DS-25 (open item and payment term model by step 4) and DS-23 (tax calculation by step 5); pull DS-27's warehouse prints to step 5.

**F-3 (medium): step 3 cannot name its documents**
- `purchase_receipt` and `sales_issue` have `needs_reference = true` (movement-types.csv), but their host documents (goods receipt, delivery) are DS-22, step 5.
- The internal stock document types (transfer, scrap, internal consumption, other receipt and issue, opening balance; ADR-0020 rule 7) have no `document_type` names, commands or fields. DS-09's remaining deliverable is "algorithm spec" only (backlog), although ADR-0009 rule 3 makes DS-09 their owner.
- Yet the step 3 adapter maps `goods_received` and `goods_delivered` to material documents (DS-17 rule 9).
- **Fix:** add a DS-09 "stock documents" deliverable before step 3, defining the internal types and what `needs_reference` points to before DS-22.

**P-1 (medium): the transfer order has no owner**
- It is a demand-line document (glossary "Demand line"; ADR-0023 rule 13), planning demand at the source and supply at the destination (ADR-0024 rule 8), and the target of conversion: "`inventory` creates the draft transfer orders itself" (ADR-0024 rule 22).
- No ADR or DS item defines its type, lifecycle or link to the posting transfer of ADR-0020 rule 6. DS-22 covers "sales and purchase flows" only.
- **Fix:** assign it to DS-22 or a new DS item (module `inventory`).

**P-2 (low): forecast history in goods-sent warehouses**
- Demand history is posted `sales_issue` quantities per warehouse (ADR-0024 rule 10). Goods sent and sold later issue from the `goods_sent` warehouse (ADR-0020 rule 4), whose stock planning "never" counts (ADR-0024 rule 9). Demand therefore lands on a node planning does not plan.
- **Fix:** attribute history to the valuation warehouse.

**P-3 (medium): price difference to stock**
- ADR-0021 rule 12 says the invoice "emits in the same batch a `landed_cost`". A batch is a client construct (ADR-0008 rule 20), and no `inventory.contract` posting interface creates a landed cost.
- If the client must add it, an omitted landed cost leaves the difference waiting in clearing, contradicting "nothing waits in clearing for a person".
- When the receipt's period is earlier and not locked, ADR-0021 rule 6 rejects with `landed_cost_period_mismatch` and forces posting into that period. If that period is soft-locked, an ordinary accountant cannot post the invoice at all (ADR-0012 rule 5).
- **Fix:** define a posting interface for the invoice handler, and settle the earlier-unlocked case (an open question already listed).

**C-3 (medium): pricing has no single owner**
- DS-20 owns "price lists, per item" (ADR-0018 "Deliberately elsewhere"); DS-22 owns "discounts and promotions". No item owns:
  - the price determination procedure (customer price list → item price → quantity breaks → discounts → promotions);
  - quotation validity;
  - the stock and accounting treatment of free promotional goods (no movement type or key in the catalogs);
  - spec 07's approval conditions "price outside price list" and "margin".
- **Fix:** name DS-22 as owner of the pricing procedure and its trace; the tax side of promotions is DS-23/24 (spec 08).

**C-4 (medium): derivation traces cover costing only**
- Principle 6 requires a trace for every derived value (cost, price, tax). Lean scope (spec 10) says "Cost trace only for costing", and the `derivation_trace` table itself is undefined (DS-09 step 3 spec).
- Quotation prices, discounts, credit-check results and tax amounts therefore carry no trace in Phase 1, so agents cannot explain them.
- Changing a Principle's meaning is reserved (ADR-0005 item 10). The author should confirm the Lean scope reading, or require DS-22 and DS-23 to write traces into the shared table.

**C-5 (medium): the tainted run's read scope is ambiguous for quotations**
- Spec 03 rule 1: a tainted run "keeps only read access scoped to the related partner". The quotation workflow needs price lists, stock, FX and margin (spec 14, spec 13), which are not partner data.
- "A draft for a customer may contain only that customer's data" leaves cost and margin fields (field classes, ADR-0017 rule 10) open to leaking into customer drafts.
- **Fix:** DS-32 must define which shared master data a tainted run may read and which field classes it may never read. Hard floors are reserved (ADR-0005 item 7).

**C-6 (medium): edge-case catalog gaps for the decided flows**
`edge-cases.csv` has no case for:
- a rejected e-invoice (O-1);
- a spoofed or unmatched sender, or injected instructions, in a quotation request (spec 03 rule 1; ADR-0019 rule 15);
- an invoice price different from the receipt price, with a later or soft-locked receipt period (ADR-0021 rule 12);
- a purchase return after invoice or after landed cost (OQ);
- a change to an order after reservation or pick (O-2);
- GR/IR residuals at period end;
- discounts, promotions and quotation → order conversion.

**C-7 (medium): partner data copied at posting changes approved content**
- ADR-0019 rule 5: "Documents copy the partner's name, address and tax ID at posting (DS-22)."
- ADR-0009 rule 9: approvals bind to the version content. Rule 14: final rows are immutable. INV-10: the current version's content equals the typed rows.
- Copying at `Post` either changes the rows after approval or breaks INV-10.
- **Fix:** snapshot the partner data at `Create`/`Update`, so it is part of the content.

**X-1 (medium): the auto-post confirmation record has no owner, and "auto-post" is used in two senses**
- Spec 03 rule 6 and ADR-0012 rule 13 require confirmation of "every agent auto-post" in batches, as a close task. Spec 03 rule 1 says "auto-posting is done only by deterministic code".
- There is no table, command or DS item for the confirmation, nor a rule for marking a document as auto-posted (actor `system` under an auto-post policy).
- **Fix:** assign it to DS-28 or DS-34.

**X-2 (medium): close-job computations have no owner**
- ADR-0012 rule 17 sends bad-debt provisions by aging, inventory write-down and prepaid amortization to "step 8 (DS-26 and the regime)". DS-26 is a reporting framework (backlog).
- Prepaid and asset subledgers may fall to DS-41, which is being drafted. Provisions and bad debt still have no owner.

**X-3 (medium): data export, management reporting and the read-model list have no owner**
- Spec 15 promises "full data export at any time".
- Management reporting and BI are an open partners' question.
- Spec 07 requires an explicit list of read models that update synchronously and asynchronously.
- No DS item owns any of the three.

## 5. Low-severity consistency findings

- **L-1, counts and maps:**
  - ADR-0015 says the catalog has "35 keys"; `transaction-keys.csv` has 38;
  - `docs/README.md` and `docs/design/README.md` say "DS-01 to DS-40", while the backlog has DS-42 and DS-43.
- **L-2, glossary and naming drift:**
  - "Preliminary price" is defined twice, with different text;
  - the "Stock quantity" row lacks bin, status and handling unit (ADR-0023 rule 4);
  - `EraseDataSubject` uses the verb Erase, which is not in the verb table (ADR-0004 rules 17–22);
  - `ReplenishmentRequested` uses no listed verb's event form;
  - validity columns are named three ways: `start_date`/`end_date`, `valid_from`/`ended_at`, `effective_from`;
  - buyer is defined twice: `product.buyer_id` and `supplier_profile.buyer_id` (ADR-0024 rule 21 uses only the product's).
- **L-3, reversibility of receipts and deliveries:**
  - ADR-0020 rule 7 says goods receipts and deliveries are corrected by returns;
  - ADR-0009 rule 19 (interim) makes them reversible while unreferenced;
  - ADR-0021 rule 9 assumes receipts are reversible.
- **L-4, planning `on_behalf_of`:** ADR-0024 rule 17 says both "on behalf of the requester" and "on behalf of the company's `planning_owner_id`".
- **L-5, unverified rule closed in the open questions:** the open question on closing to 911/421 is checked `[x]`, while ADR-0012 rule 18 says "flagged until verified against the TT99 text". The reading guide (rule 4) keeps unverified rules open.
- **L-6, numbering invariant:** INV-07 counts only documents in the final states posted and reversed. Non-posting documents are numbered at approval and keep their number when canceled (ADR-0009 rule 8), so their counters either fail INV-07 or are left unchecked.
- **L-7, actor kinds and queues:**
  - e-mail intake is a "scheduled job with actor `integration` on the `jobs` queue" (ADR-0019 rule 14), whereas outside calls belong on `integrations` (ADR-0013 rules 10, 13) and actor `integration` means an `integration_client` (ADR-0017 rule 1);
  - `human_only` `Reverse` is executed by system jobs for revaluations (ADR-0011 rule 20; ADR-0012 rule 15). The flag means "not an agent or integration", not "human".

## 6. Points correctly deferred (not defects)

These are listed for completeness: DS-20 (price lists), DS-22 (commercial state machines, three-way match tolerances, GR/IR clearing), DS-23 (tax codes and rates), DS-24 (e-invoice adapter), DS-25 (cash, bank, advances, netting, currency-exchange clearing account), DS-26 (statutory reports), DS-28 (thresholds), DS-29 (work items), DS-32/33/34 (agent runtime, query layer, workflows), DS-35 (CRM intake connector), DS-36 (audit). The author's open decisions are EC-20, EC-21 and EC-22, return and count valuation, reservation priority, short pick, the planning phase and the warehouse feature list.
