# Phase 1 build: steps 5–9 and the agents

Steps 5–11 are the Phase 1 build before go-live; steps 10 and 11 are in [go-live.md](go-live.md). Each commercial document emits only step 1 and step 3 commands (B3); adding a document never changes the core. Hand-built screens and agents come only after their manual path passes its gate (B6). Section headings follow [README.md](README.md#how-to-use-it).

Applies to every step below:

- The medium dataset replays nightly through the commands of every step built so far; the step 4 result is the baseline the books must keep equalling.
- The simulator's step adapter for each step is a work package of that step: commercial events now become commercial-document commands instead of core commands.
- Policy is a threshold table per action type with one-level approval (B7, DS-28). Generalize only at the second or third concrete case.

---

## Step 5 · Commercial documents

**Entry criteria:** step 4 gate (Phase 0 gate) passed.

**Design items first:** DS-22 commercial documents; DS-15 full permission model; DS-28 policy table and one-level approval; DS-29 work queue; DS-35 minimal CRM.

**Work packages, in order:**

1. Work queue (DS-29) and policy table with one-level approval bound to document version (DS-28); full permissions with segregation of duties (DS-15).
2. Purchasing: purchase request, PO, goods receipt, purchase invoice via the GR/IR clearing account, three-way match on quantity and price, including foreign currency.
3. Imports: customs declaration with its own customs rate; purchase cost documents allocated by value, quantity or weight, following the step 3 landed cost rule.
4. Sales: quotation, sales order, delivery, sales invoice.
5. Returns, discounts, promotions, credit limit.
6. Minimal CRM: partners, contacts, interaction timeline, email intake (DS-35).
7. Step 5 simulator adapter; simulator writes emails with quotation requests ([12-testing.md](../spec/12-testing.md#synthetic-dataset)).
8. The `assistant` agent, the assist panel and the command bar ([ADR-0077](../adr/0077-ui-floorplans-annotations-and-embedded-agent.md) rules 13–18), with its evaluation set.

**How agents are used:** builders implement documents as thin layers; the reviewer checks that no document posts anything except step 1 and step 3 commands, and that the core is unchanged by the pull request (B3).

**Verification:** end-to-end flow import purchase → receipt → sale → issue through REST and MCP; medium replay through commercial documents produces the same books as the step 4 replay; edge cases for partial deliveries, receipts and invoices, returns of partly invoiced goods, credit limit exceeded, price below cost, UoM conversions; GR/IR and price-difference postings against golden scenarios.

**Exit gate (verbatim):**

> Import purchase → receipt → sale → issue runs end to end through REST and MCP; books equal step 4

**Gate item** ([ADR-0077](../adr/0077-ui-floorplans-annotations-and-embedded-agent.md) rule 13; author's delegation, 2026-11-19): the assistant seat passes its evaluation set of about 50 tasks across its three modes (read answers with correct citations, drafts with correct field diffs, refusals outside its scope, taint handling including pasted untrusted text), as spec 17 requires of every pair of seat and model.

**Artifacts:** sales, purchasing, imports, CRM, work queue and policy modules; DS-22 state machines; step 5 adapter; book-comparison report against step 4.

**Risks:** a document needs a core change (B3 is broken).

**Fallback:** if a document seems to need a core change, stop: the author decides whether the core contract changes for a measured reason (ADR, B2, rerun of steps 1–4 verification) or the document is redesigned. Books that differ from step 4 are investigated as defects, never accepted as a new baseline without the author's decision.

---

## Step 5b · Planning and multi-level MRP

**Entry criteria:** step 5 gate and step 4b gate passed. The step may run beside steps 6 and 7; no dates are set (decision of 2026-11-21, author's delegation).

**Design items first:** DS-43 planning ([ADR-0024](../adr/0024-planning.md) rule 26); DS-54 multi-level MRP ([ADR-0036](../adr/0036-multi-level-mrp.md)).

**Work packages, in order:**

1. The later planning slice of [ADR-0024](../adr/0024-planning.md) rule 26: forecast methods chosen by backtest, service-level safety stock and the further action messages.
2. Multi-level MRP ([ADR-0036](../adr/0036-multi-level-mrp.md)): bill of materials explosion with low-level codes and dependent demand.
3. Lead-time offsetting and planned production orders.
4. The capacity check and conversion of planned orders.
5. Step 5b simulator adapter: planning events of the manufacturing company to commands.
6. Subcontracting ([ADR-0037](../adr/0037-subcontracting.md), DS-55), which needs the production core (step 4b) and purchase orders (step 5): built in this step, after both gates.

**How agents are used:** builders implement; the reviewer checks that planning writes only planned orders, pegging and exceptions, and that it changes no document except through conversion. The recomputation writer completes the naive planning recomputation straight from raw demand, supply and bills of materials, without reading planning code, as for costing at step 3.

**Verification:** planned orders, pegging and exceptions on the manufacturing company equal the naive recomputation per item, warehouse and date; edge cases assigned to the step appear in the coverage report and pass; a second planning run on unchanged data produces no change.

**Exit gate (verbatim):**

> On the manufacturing company of the synthetic dataset, the planning run's planned orders, pegging and exceptions equal an independent naive recomputation; every planning edge case assigned to the step passes; a rerun on unchanged data changes nothing

**Artifacts:** the later planning slice and multi-level MRP in the `planning` module; step 5b adapter; naive planning recomputation; golden results.

**Risks:** the naive recomputation and the planning run disagree for reasons of interpretation (a rule of [ADR-0036](../adr/0036-multi-level-mrp.md), not a bug); run time on the large dataset.

**Fallback:** when the planning run, the naive recomputation and a golden scenario disagree, the author decides which reading of the spec is right and records it (ADR or DS update); the code is never changed just to match one reference. A run-time problem is measured first, then handled by ADR (B2).

**After the gate:** the `planning` agent starts ([ADR-0078](../adr/0078-agent-simplification-for-phase-1.md) rule 1). Its golden pair (one planning exception with the agent on recorded responses and with the LLM off, [ADR-0078](../adr/0078-agent-simplification-for-phase-1.md) rule 13) is an item of the agent's own completion, not of the step 5b gate.

---

## Step 6 · Cash and AR/AP

**Entry criteria:** step 5 gate passed.

**Design items first:** DS-25 cash, bank and AR/AP; DS-10 realized FX logic. The book rate for realized FX after a revaluation is verified before this gate ([ADR-0003](../adr/0003-build-operating-rules.md) R10).

**Work packages, in order:**

1. Cash receipts and payments, cash count.
2. Open items per invoice, payment allocation, netting, advances.
3. Bank statement import for 2–3 common bank formats; manual matching.
4. Expenses without a PO; general journal entries with approval.
5. Foreign-currency payments, book rate, realized FX differences.
6. Step 6 adapter; simulator writes bank statement files.

**How agents are used:** as in step 5; the recomputation writer extends the naive recomputation to open items and realized FX.

**Verification:** receivable and payable control accounts equal the sum of open items in transaction and company currency after every simulated day; cash and bank books equal the simulator's records; edge cases for partial foreign-currency payments at a different rate and netting.

**Exit gate (verbatim):**

> AR/AP subledgers match the receivable and payable control accounts (131, 331 in TT99) in both transaction and company currency. Cash and bank books match

**Artifacts:** cash, bank and AR/AP modules; bank statement readers; step 6 adapter.

**Risks:** mixed-balance accounts (131/331 holding advances) classified wrongly; realized FX rule unverified.

**Fallback:** differences are traced through the cost and open-item traces to the first wrong document, frozen as a regression scenario and fixed. An unverified FX rule stays flagged configuration.

---

## Step 7 · Tax and e-invoicing

**Entry criteria:** step 6 gate passed.

**Design items first:** DS-23 tax engine logic; DS-24 e-invoice adapter and BKAV adapter. Decree 70/2025 and the VAT deduction rule for invoices of VND 5 million or more are verified before this gate ([ADR-0003](../adr/0003-build-operating-rules.md) R10).

**Work packages, in order:**

1. Tax determination with date-effective rates; line versus document rounding (DS-23).
2. Import VAT.
3. Outgoing e-invoices via BKAV, against BKAV's test environment only until go-live; issuance never delayed by approval (DS-05).
4. Incoming e-invoice intake.
5. 01/GTGT XML, validated against the XSD (ADR-0002).
6. Independent tax recomputation by the recomputation writer.
7. Step 7 adapter; simulator writes e-invoice XML.

**How agents are used:** builders implement; the author builds the golden 01/GTGT return by hand; no agent computes an expected tax amount.

**Verification:** tax amounts on the medium dataset equal the independent tax recomputation; edge cases for a tax-rate change mid-period and for replaced and adjusted invoices; the 01/GTGT output equals the golden return.

**Exit gate (verbatim):**

> Tax amounts on the synthetic dataset match the independent tax recomputation; the 01/GTGT return matches a hand-built golden return

**Gate item** ([ADR-0078](../adr/0078-agent-simplification-for-phase-1.md) rule 13; author's delegation, 2026-11-21): the purchase invoice flow runs as a golden scenario with the LLM off, from the input files to a posted invoice. The same scenario with agents on recorded responses, over the same input files and ending in the same posted invoice, is an item of the completion of `purchase_invoice` and `document_reader`, which start only after this gate, not of this gate.

**Artifacts:** tax engine; e-invoice adapter interface and BKAV adapter; 01/GTGT generator; golden return.

**Risks:** regulation changes during the build; BKAV test environment differs from production.

**Fallback:** a disagreement on a rule goes to the author and, if legal, to an open question with verification; the rule stays flagged configuration until verified.

---

## Step 8 · Period close and reports

**Entry criteria:** step 7 gate passed.

**Design items first:** DS-26 statutory reporting framework; DS-27 print templates and PDF worker; DS-10 FX revaluation logic (the revaluation method is verified before this gate, [ADR-0003](../adr/0003-build-operating-rules.md) R10); DS-12 close checklist.

**Work packages, in order:**

1. Period-close checklist, including prepaid expense amortization, provisions and the confirmation of agent auto-posts ([03-agent-safety.md](../spec/03-agent-safety.md), rule 6).
2. Period-end FX revaluation (DS-10).
3. Closing entries with the closing-entry marker, posted by actor `system` on behalf of the accountable human.
4. Vietnamese books; B01, B02, B03 as report definitions inside the localization package (DS-26).
5. Print templates as configuration; PDF worker in its own queue (DS-27, ADR-0002).

**How agents are used:** builders implement; the author builds golden close results and statements by hand.

**Verification:** month-end and year-end close on the medium dataset equal golden scenarios and naive recomputation, FX differences included; period-range reports exclude closing entries; postings into soft-locked and locked periods are refused.

**Exit gate (verbatim):**

> Period close on the synthetic dataset matches the golden scenarios and the naive recomputation, FX differences included

**Artifacts:** close module; FX revaluation; books and statements for TT99; print templates; PDF worker.

**Risks:** B03 rules for TT133 unconfirmed (step 10 issue); WeasyPrint limits on complex templates (ADR-0002 revisit condition).

**Fallback:** as in step 3: when references disagree, the author decides the correct reading and records it.

---

## Step 9 · Hand-built UI and warehouse app

**Entry criteria:** step 8 gate passed. The commands behind each screen have passed their gate (B6).

**Design items first:** DS-30 UX spec for the 6 hand-built entry screens; DS-31 warehouse PWA.

**Work packages, in order:**

1. The 6 hand-built entry screens: sales invoice, goods receipt, goods issue, cash receipt, cash payment, journal entry, keyboard-first (DS-30).
2. Warehouse PWA: receipt, issue, transfer and count; barcode per packaging unit (DS-31).
3. Measurement session with an outside accountant who uses MISA daily: one simulated day of at least 50 documents over the 6 screen types, entered in NativeFlows first, then in MISA; pass when NativeFlows's elapsed time is no longer ([ADR-0003](../adr/0003-build-operating-rules.md) R9).

**How agents are used:** builders implement screens against the UX spec; the reviewer checks that screens call only existing commands.

**Verification:** all invariants unchanged, because the UI is only a client; the measurement session uses one day of documents from the synthetic dataset, never real data.

**Exit gate (verbatim):**

> An outside accountant enters one day of documents from the synthetic dataset, no slower than MISA

**Artifacts:** 6 screens; warehouse PWA; measurement record.

**Risks:** the speed target is missed; cheap Android phones and weak networks.

**Fallback:** fix the slowest screen measured, repeat the session. Commands are not changed for UI convenience without B2.

---

## Agents

Agents are not a separate step ([11-build-order.md](../spec/11-build-order.md)). Each is built right after its manual path passes its gate. Phase 1 has six agent types, all done before the platform counts as complete (step 10); the others move to Phase 2 ([ADR-0078](../adr/0078-agent-simplification-for-phase-1.md) rules 1, 2).

| Agent | Starts after | Design items |
| --- | --- | --- |
| Assistant | Step 5 (work package 8); its evaluation set is a step 5 gate item | DS-32, DS-33 (first agent), [ADR-0077](../adr/0077-ui-floorplans-annotations-and-embedded-agent.md) rules 13–18 |
| Analysis | Step 5 gate | [ADR-0060](../adr/0060-agent-assisted-reporting-and-analysis.md) |
| Bank matching | Step 6 gate | DS-34 bank matching, DS-25 |
| Purchase invoices | Step 7 gate | DS-34 purchase invoices, DS-24 |
| Document reader (vision) | Step 7 gate | [ADR-0057](../adr/0057-document-intake-and-extraction.md), vision seat configured |
| Planning | Step 5b gate (the manual path of planning with multi-level MRP; ADR-0024 rule 26, ADR-0032 rule 7) | DS-34 planning, DS-43, DS-54, [ADR-0051](../adr/0051-agent-workflows.md) rules 23–25 |

**Work packages per agent:** the workflow as a code-orchestrated cascade (stored rules and mappings → lookup → fuzzy matching with a deterministic score → LLM only for what remains, Principle 13); fixed tool list; untrusted-content tainting; budgets with circuit breaker; run records; replay evaluation in CI; a real-LLM evaluation run whenever a model or prompt changes (Principle 11); metric for the share of steps handled deterministically ([14-agent-workflows.md](../spec/14-agent-workflows.md)).

**Verification:** the evaluation suite draws on the synthetic dataset and the input files the simulator writes (e-invoice XML, bank statements, emails). The hard floors in [03-agent-safety.md](../spec/03-agent-safety.md) have their own tests: a run that read untrusted content cannot send, change master data or post; the trigger of an agent cannot approve its drafts. Phase 1 promotes on the offline evaluation; live shadow on real transactions returns in Phase 2 ([ADR-0078](../adr/0078-agent-simplification-for-phase-1.md) rules 5, 6). **Done for step 10** ([ADR-0003](../adr/0003-build-operating-rules.md) R8): draft-only mode; replay evaluation green; hard-floor tests green; at least 90% of synthetic cases produce a draft equal to the simulator's known answer, or the higher threshold DS-34 sets. The eval judge scores only free text.

**Fallback:** an agent that does not reach its threshold stays in draft-only mode; every operation still works without an LLM (Principle 12), so no gate depends on an agent's accuracy.
