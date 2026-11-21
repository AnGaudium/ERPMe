# Phase 0: steps 0–4

Steps 0–4 are Phase 0. The Phase 0 gate is the step 4 gate ([10-roadmap.md](../spec/10-roadmap.md)). The build carries no calendar dates: the build order and the gates are the only schedule (D15 note in [decisions.md](../decisions.md)). Section headings follow [README.md](README.md#how-to-use-it).

Applies to every step below:

- CI runs on every commit with the small synthetic dataset; the nightly run uses the largest dataset the current adapters can replay ([testing-operations.md](testing-operations.md)).
- "Built in full from the start" items in [10-roadmap.md](../spec/10-roadmap.md#lean-scope-for-phases-0-and-1) are built when their layer is built, never deferred: `company_id` on every table, `Decimal`/`NUMERIC` for money and quantities, transaction and company currency on every journal line, `actor` and `on_behalf_of` on every command, idempotency, i18n with English source, data labels and the routing switch.
- Schema changes are free until the freeze 4 weeks before go-live (B8); concentrate risky changes here.

Note ([ADR-0073](../adr/0073-coding-pipeline-and-mechanical-assurance.md), 2026-11-21): every gate report also carries ADR-0073 rule 21's mechanical summary and the plain-Vietnamese acceptance report with a demo; the gate texts are unchanged. Work packages run one at a time until the step 1 gate has passed with measured numbers. After that they may run in parallel within a step when their allowlists are disjoint, never across steps (ADR-0073 rule 22).

---

## Step 0 · Preparation

**Entry criteria:** specification committed (D17); ADR-0001 and ADR-0002 accepted. `main` is on the public repository `AnGaudium/NativeFlows`, because CI runs on GitHub Actions (ADR-0002) ([ADR-0003](../adr/0003-build-operating-rules.md) R3).

**Design items first:** DS-01 to DS-18 (DS-09 ADR only; DS-10 and DS-11 ADR only; DS-15 envelope part only). These cover every ADR in "Decide by ADR before writing code" in [11-build-order.md](../spec/11-build-order.md). No production code before they are accepted ([AGENTS.md](../../AGENTS.md)).

**Work packages, in order:**

1. DS-01 glossary and naming, then DS-02 ID and numeric model and DS-03 time model.
2. DS-04 command envelope and registry; DS-05 document lifecycle; DS-07 system chart (catalog); DS-10 multi-currency ADR; DS-12 posting periods; DS-13 outbox.
3. DS-06 universal journal data model (depends on DS-02, 03, 05, 07, 10, 12); DS-08 account determination; DS-09 inventory and costing ADR; DS-11 landed cost ADR; DS-14 localization package structure; DS-15 permission envelope.
4. DS-16 invariant catalog and harness spec; DS-17 synthetic dataset spec and edge-case catalog v1, each edge case with its first executable step; DS-18 repo conventions, including the DCO check, the 15-minute CI limit and coverage enforcement ([ADR-0003](../adr/0003-build-operating-rules.md) R1, R4–R6).
5. Repo skeleton per DS-18: monorepo layout, import-linter contracts, CLAUDE.md and coding-agent skills, CI with pyright strict.
6. Test server per DS-18 ([testing-operations.md](testing-operations.md#environments)).
7. Invariant-checking harness per DS-16: the INV-xx catalog as code, Hypothesis state-machine skeleton, golden-scenario file reader, reference comparison report.
8. Business simulator v1 per DS-17: fictional Vietnamese company, seeded, writing the versioned business-event log; edge-case injection with coverage report.
9. First golden scenarios (spreadsheets built by the author) for the cases listed in [12-testing.md](../spec/12-testing.md): average cost with transfers, returns, backdated documents, landed cost after partial sale, USD import with duty at a different rate, FX revaluation, discounts, rounding.

**How agents are used:** builder agents draft each DS file from the spec; a reviewer agent on a different model checks each draft for contradictions with D1–D17 and the build order; technical items are accepted when the review leaves no blocking or should-fix finding, and reserved decisions inside an item go to the author ([ADR-0005](../adr/0005-technical-decisions-delegated.md)). Builder agents write the skeleton, harness and simulator. Golden expected values are built by the author, never by an agent.

**Verification:** each DS file meets the "done" rule in [design/README.md](../design/README.md); CI green on the empty skeleton; the simulator, run twice with the same seed and dataset version, produces an identical event log; the small dataset at this step is the event log plus input files and contains every EC v1 edge case at least once as events ([ADR-0003](../adr/0003-build-operating-rules.md) R1).

Note ([ADR-0073](../adr/0073-coding-pipeline-and-mechanical-assurance.md), 2026-11-21): work package 5 also builds ADR-0073's pipeline, written by Claude Opus 5.5:

- declaration types and the validator;
- `scaffold`, `work-package` and the hook;
- `scope-guard`;
- `mutation`, with the SQL mutator;
- the model review workflow and its checklists;
- `.github/assurance.toml`;
- `acceptance`.

The author sets branch protection. The gate report shows each part refusing a planted violation, the protection settings read from the API, and the measured CI time per job and review cost per run (ADR-0073 rule 21). No product code is merged before this.

**Exit gate (verbatim):**

> ADRs decided. The simulator produces the small synthetic dataset for the Vietnamese company

**Artifacts:** ADRs and DS files for DS-01 to DS-18; catalogs for system accounts, transaction keys, movement types and EC v1; repo skeleton; CI; test server; harness; simulator v1; small dataset event log (seed, version); first golden scenarios.

**Risks:** design work expands beyond what step 0 needs; ADRs decided on assumptions that the open legal questions later contradict; the simulator grows into a product of its own.

**Fallback:** if an ADR cannot be decided because a legal question is open, decide the structure and keep the rule as flagged configuration ([escalation.md](escalation.md#unverified-legal-rules)). If the simulator is late, ship v1 with only the events step 1 needs and extend it per step (DS-17 allows extension at every step); the gate still requires the small dataset.

---

## Step 1 · Ledger

**Entry criteria:** step 0 gate passed.

**Design items first:** DS-19 Vietnam package TT99 (FX rules only after legal verification), DS-30 renderer part, DS-36 audit part.

**Work packages, in order:**

1. Command registry and dispatcher with the envelope (DS-04): idempotency, `plan_hash` by run-and-rollback, error model, schema versioning.
2. REST and MCP generated from the command schemas (Principle 10).
3. Two-tier chart and the localization package loader (DS-07, DS-14); Vietnam package with the TT99 regime and FX rules (DS-19).
4. Daily rate table; universal journal posting in transaction and company currency with the rounding line (DS-06, DS-10).
5. Append-only journal with DB triggers, reversal, numbering at posting, posting periods (DS-05, DS-12).
6. Audit log (DS-36), outbox (DS-13), i18n with English source.
7. Schema-driven renderer, minimal (DS-30), to operate and test (B6).
8. Simulator adapter for step 1: translates journal-level events into step 1 commands.

**How agents are used:** builders implement each package; the reviewer checks every change touching posting, triggers or idempotency, and the author reviews those line by line. The recomputation writer starts the naive trial-balance recomputation from the spec.

Note ([ADR-0073](../adr/0073-coding-pipeline-and-mechanical-assurance.md), 2026-11-21): "the author reviews those line by line" now reads: those changes pass mutation testing and two model reviews as required check runs, and the author reviews behavior from the acceptance report. Claude Haiku 5.5 codes command packages, one at a time; the first 3–5 are measured, and at least one of them posts money (ADR-0073 rule 5). The registry, dispatcher, `numeric`, triggers, RLS and the first package of each kind are assigned up front to Claude Opus 5.5. Gate evidence: every sensitive package of the step at the interim package mutation threshold, property tests for money arithmetic and posting balance green, SQL tests for every trigger and policy, and no pending declaration (ADR-0073 rule 21).

**Verification:** branch coverage of 90% or more on the core packages is enforced from this step ([ADR-0003](../adr/0003-build-operating-rules.md) R4). Hypothesis state machine posts random transaction sequences in VND and foreign currencies; after each step every ledger invariant holds: each entry balances per transaction currency, company currency and group currency; trial balance sums to zero; rounding lands on the defined system account; no number gaps; posted documents never change; reversal nets to zero; retry with the same idempotency key returns the identical result; executed result equals the simulated `plan_hash`. Small dataset (journal-level events) replays in CI. Concurrency test for numbering and idempotency.

**Exit gate (verbatim):**

> Invariants green on random transaction sequences, foreign currency included. Trial balance correct

**Artifacts:** ledger module; Vietnam package TT99 v1; REST and MCP endpoints; renderer v1; step 1 adapter; ledger INV-xx in code; regression scenarios for every defect found.

**Risks:** TT99 FX rules still unverified (open question); `plan_hash` canonical form unstable across runs; triggers and RLS weaker than intended.

**Fallback:** if Hypothesis finds a failing sequence, shrink it, freeze it as a regression scenario, fix, rerun. The TT99 FX rules and the reversal questions are verified before this gate ([ADR-0003](../adr/0003-build-operating-rules.md) R10); until then they are flagged configuration and the affected golden scenarios are marked "pending verification".

---

## Step 2 · Master data

**Entry criteria:** step 1 gate passed.

**Design items first:** DS-20 master data model; DS-23 tax engine data model part.

**Work packages, in order:**

1. Partners with roles, items with UoM groups (stock, purchase, sales unit; fixed factors), warehouses, currencies, valuation classes (DS-20).
2. Account determination table: transaction key × valuation class × valuation area → operational account, with the cross-check (DS-08).
3. Tax code and date-effective rate tables, data model only (DS-23).
4. Command batches: simulate a batch, then execute it with its `plan_hash`.
5. Simulator adapter for step 2: master-data events to commands.

**How agents are used:** builders implement; the reviewer checks label coverage (every field has a data label) and identifier naming against the glossary.

**Verification:** master data of the small and medium datasets imports through command batches; re-importing the same batch with the same idempotency keys changes nothing; account determination cross-check passes for every valuation class in the dataset; all step 1 invariants stay green.

Note ([ADR-0073](../adr/0073-coding-pipeline-and-mechanical-assurance.md), 2026-11-21): gate evidence adds account determination and command batches at the package mutation threshold, and re-import idempotency shown in the acceptance report (ADR-0073 rule 21).

**Exit gate (verbatim):**

> Master data of the synthetic dataset imports through command batches

**Artifacts:** master data module; account determination table for TT99; tax data model; step 2 adapter.

**Risks:** bins and catch weight leak into Phase 1 features (only reserved columns are allowed); UoM rounding.

**Fallback:** a batch that fails is fixed at the command level, never by direct SQL. If the master data model needs a change already depended on by step 1, it goes through B2 (a measured reason, recorded in an ADR) and step 1 tests rerun.

---

## Step 3 · Inventory, costing, landed cost

**Entry criteria:** step 2 gate passed.

**Design items first:** DS-09 algorithm spec (warehouses only; BOM levels at step 4b, the production core, [ADR-0032](../adr/0032-phase-1-scope-with-production.md)); DS-11 landed cost logic; movement type catalog. The negative-stock time point (a design question for DS-09) is answered; the legal items for step 3 in the [ADR-0003](../adr/0003-build-operating-rules.md) R10 schedule are verified before the gate.

**Work packages, in order:**

1. Movement types table and material documents for receipts, issues and transfers; zero or one accounting document per material document.
2. Stock posting serialized per (item, warehouse); negative-stock rule (DS-09).
3. Lots and serials tracked in stock movements, with no cost of their own.
4. Stock count with differences.
5. Preliminary price and period-end actual costing across warehouses, porting the existing periodic-average engine (see the DS-09 open question on where it lives).
6. Landed cost: same open period added to the receipt value; a cost for an earlier period, unlocked or locked, posted on its own date in the current period (the period of its posting date, which is not locked) as a receipt addition that enters that period's average, with no charge to past consumers; dated in an earlier period that is not locked, it makes that period stale like any backdated document (DS-11; ADR-0021 rule 6 note: the author's decision of 2026-11-21 and the chief architect's translation).
7. Valuation postings to the journal through account determination.
8. Cost trace for costing (Principle 6, built thin).
9. Simulator adapter for step 3: stock and cost events to commands.

**How agents are used:** builders implement; the reviewer and the author review every change to stock posting and costing. The recomputation writer completes the naive periodic-average recomputation straight from raw transactions, without reading core code. The test-scenario model starts proposing stock situations on the test server.

Note ([ADR-0073](../adr/0073-coding-pipeline-and-mechanical-assurance.md), 2026-11-21): the author's review of stock posting and costing changes is replaced by mutation testing and two model reviews; he reviews the acceptance report. Gate evidence: `inventory` and costing at the package mutation threshold, property tests for stock quantity and value conservation, and the report's stock and journal per item, warehouse and period against the naive recomputation (ADR-0073 rule 21).

**Verification:** golden scenarios for average cost with transfers, returns, backdated documents, landed cost after partial sale and after period close, USD import with duty at a different rate; naive recomputation equals the core result per item, warehouse and period; inventory system account balances (152, 155, 156 in TT99) equal the inventory valuation report; no negative stock; parallel tests for concurrent issues of the same (item, warehouse); edge cases for steps 1–3 appear in the coverage report.

**Exit gate (verbatim):**

> Matches golden scenarios, including imports with later costs, and the independent recomputation. No negative stock. Putaway, picking, short pick and count flows pass their edge cases

**Artifacts:** inventory and costing modules; DS-09 algorithm spec; movement type catalog; step 3 adapter; naive costing recomputation; golden results.

**Risks:** golden and naive results disagree for reasons of interpretation (an accounting rule, not a bug); deadlocks or throughput limits from serialized stock posting; the ported engine carries Odoo-era assumptions.

**Fallback:** when the core, the naive recomputation and the golden scenario disagree, the author decides which reading of the spec is right and records it (ADR or DS update); the code is never changed just to match one reference. A throughput problem is measured first, then handled by ADR (B2).

---

## Step 4 · Sequential replay of the synthetic dataset

**Entry criteria:** step 3 gate passed. Medium dataset (1 Vietnamese company, TT99, 1 year, about 10,000 documents) generated by the simulator.

**Design items first:** DS-21 import batch format (opening balances in several currencies).

**Work packages, in order:**

1. Opening balances including foreign currency as one command batch (DS-21).
2. Day-by-day replay driver calling core commands through REST and through MCP, with month-end closes.
3. Reference comparison report per simulated day: invariants, naive recomputation, golden scenarios.
4. Edge-case coverage report filtered to steps 1–3.
5. Performance baseline: replay time per simulated day, recorded for later comparison.

**How agents are used:** builders write the driver and reports; the test-scenario model proposes extra situations; every defect becomes a regression scenario. Periodic independent review of stock posting, outbox and idempotency by a reviewer agent from a different provider ([risks.md](../risks.md)).

**Verification:** the full medium replay nightly, within 4 hours ([ADR-0003](../adr/0003-build-operating-rules.md) R6); every invariant after every simulated day; costing, FX and balances against golden scenarios and naive recomputation; both REST and MCP paths exercised.

Note ([ADR-0073](../adr/0073-coding-pipeline-and-mechanical-assurance.md), 2026-11-21): gate evidence adds mutation scores held since step 3, with no fall of more than 2 points, and the acceptance report showing the replay day by day (ADR-0073 rule 21).

**Exit gate (verbatim):**

> The medium synthetic dataset (Vietnamese company, one year) replays day by day through core commands, called through REST and MCP, with every invariant green after every simulated day. Costing, FX and balances match the golden scenarios and the naive recomputation. The coverage report shows every edge case for steps 1–3 exercised

This is also the Phase 0 gate. Review [risks.md](../risks.md) at this gate.

**Artifacts:** replay driver; medium dataset (seed, version); reference comparison and coverage reports; performance baseline; Phase 0 gate record in [step-log.md](step-log.md).

**Risks:** a defect found here requires a contract change in step 1 or 3; replay too slow to run nightly.

**Fallback:** a failure is reproduced from (seed, dataset version, day), frozen as a regression scenario and fixed in the lowest layer it belongs to, then steps 1–3 verification reruns. Commercial documents (step 5) do not start until this gate passes; this is the purpose of step 4 ([11-build-order.md](../spec/11-build-order.md)).

**After the gate:** no agent starts yet; the first, the assistant, is built inside step 5 (work package 8; its evaluation set is a step 5 gate item; see [steps-5-9.md](steps-5-9.md#agents); [ADR-0078](../adr/0078-agent-simplification-for-phase-1.md)).
