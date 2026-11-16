# Go-live: steps 10–11 and the Phase 1 gate

No parallel run with the old software; the pilot goes live fully on NativeFlows, tax books included (D11). No commitment to any pilot before the step 10 gate (D11, B5). One pilot only until the Phase 1 gate ([risks.md](../risks.md)). Pilot data never enters the repository ([AGENTS.md](../../AGENTS.md)). This file stays high level; the cut-over checklist and rehearsal procedure are designed in DS-40.

---

## Step 10 · Platform completion (months 10–12)

**Entry criteria:** step 9 gate passed; all four agents built ([steps-5-9.md](steps-5-9.md#agents)).

**Design items first:** DS-36 operations dashboard; DS-37 deployment and operations; DS-38 localization skill and basic US package; DS-39 TT133 regime. TT133 status and B03 are verified before this gate ([ADR-0003](../adr/0003-build-operating-rules.md) R10).

**Work packages, in order:**

1. Simulator extended to the large dataset: several companies, the US company included (English names, USD), several years, about 100,000 documents a year.
2. Replay of the large dataset through commercial documents, not only core commands; fix every difference.
3. TT133 regime in the Vietnam package (DS-39).
4. AI skill for localization packages; the basic US package built with it (no state tax returns) (DS-38).
5. Deployment documentation: Docker Compose, backup and restore with pgBackRest, upgrade and migration policy (DS-37); a restore is tested, not only written. Staging is built from this documentation, which tests it ([ADR-0003](../adr/0003-build-operating-rules.md) R2).
6. Operations dashboard: dead tuples, autovacuum lag, queue lag (DS-36, ADR-0002).
7. Load test on the large dataset against the step 4 performance baseline.
8. Independent review of stock posting, outbox and idempotency by a reviewer agent from a different provider.

**Platform-complete review (before the gate is declared):** the author walks through, with evidence:

- every DS item DS-01 to DS-39 is done by the [design/README.md](../design/README.md) rule;
- every open question needed by steps 0–10 is closed; a rule still flagged is listed and is not one the pilot will use ([ADR-0003](../adr/0003-build-operating-rules.md) R11);
- every Phase 1 item of the Lean scope in [10-roadmap.md](../spec/10-roadmap.md#lean-scope-for-phases-0-and-1) exists, and nothing from "After Phase 1" was built beyond reserved schema room;
- the four agents pass their evaluation suites; every operation works with LLMs off (Principle 12);
- [risks.md](../risks.md) reviewed.

**Exit gate (verbatim):**

> The large dataset passes every invariant and reference comparison, and the coverage report shows every edge case exercised. This is the platform-complete milestone; pilot selection starts here

**Artifacts:** large dataset (seed, version); TT133 regime; localization skill; basic US package; deployment documentation; dashboard; load-test report; platform-complete record in [step-log.md](step-log.md).

**Risks:** load reveals locking or vacuum problems; the US package pulls in scope (it stays basic, [risks.md](../risks.md)).

**Fallback:** fix differences in the lowest layer; contract changes follow B2 and rerun the lower gates. Pilot conversations do not start before the gate passes.

---

## Step 11 · Pilot selection and go-live rehearsal (after platform completion)

**Entry criteria:** step 10 gate passed.

**Design items first:** DS-40 go-live kit (cut-over checklist, rehearsal procedure, schema freeze; reader for the pilot's current system if missing).

**Work packages, in order:**

1. **Pilot selection** by the [pilot selection criteria](../spec/10-roadmap.md): trading business of 10–50 people, imports and foreign-currency transactions allowed, chief accountant willing to switch fully, owner who commits time, regular incoming e-invoices, agreement to share anonymized data for agent evaluation outside the repository. The author selects; written commitment only now.
2. **Go-live date:** the start of an accounting period, preferably a quarter.
3. **Reader** for the pilot's current system if none exists (e.g. MISA), using the data migration agent and the DS-21 batch format (D16).
4. **Load real data on staging** (author-operated servers in Vietnam, author-only access; real data deleted within 7 days after the rehearsal, [ADR-0003](../adr/0003-build-operating-rules.md) R12): master data, opening balances, AR/AP open items per invoice, inventory per warehouse, lots and serials with opening cost, each as a simulated command batch, never an SQL script ([15-migration-ux-docs.md](../spec/15-migration-ux-docs.md)).
5. **Rehearsal:** replay the pilot's latest month on staging; compare with their books in the current system; classify every difference (reader mapping, NativeFlows defect, error in the old books) and resolve it.
6. **Schema freeze** 4 weeks before go-live (B8). After the freeze, a schema change needs the author's approval and a tested migration.
7. User accounts, roles and segregation of duties for the pilot's team; the customer decides the routing switch (D12) and who is recorded as accountable.
8. Training with the shipped Vietnamese UI and user guides.

**How agents are used:** the data migration agent proposes mappings and duplicate merges; drafts only, the batch is simulated and checked against the old books' totals before execution. Agents never see pilot data in the repository or in CI.

Before the gate, every localization rule the pilot's transactions use is verified; rules it does not use stay flagged and are disabled for its company ([ADR-0003](../adr/0003-build-operating-rules.md) R11).

**Exit gate (verbatim):**

> The rehearsal month matches the customer's books in their current system. The chief accountant agrees to go live

**Artifacts:** pilot agreement (outside the repository); reader; rehearsal report; frozen schema version; go/no-go record.

**Risks:** the pilot's old books contain errors; the pilot withdraws; the reader takes longer than planned.

**Fallback:** rehearse again with the next month. Differences caused by errors in the old books are agreed with the chief accountant and corrected in the opening balances, never by forcing NativeFlows to reproduce them. If the pilot withdraws, select another pilot by the same criteria.

---

## Cut-over checklist (outline)

DS-40 turns this outline into the checklist. Order on cut-over:

1. Go/no-go meeting with the owner and chief accountant: rehearsal gate passed, schema frozen, backup and restore tested on production, e-invoice provider switched from test to production.
2. Old system: last day of the previous period entered; the old system is closed for new entries in the new period.
3. Final export from the old system; reader run; master data batch simulated and executed.
4. Opening balances batch: simulate, check `plan_hash`, reconcile totals with the old books' trial balance per account, then execute.
5. AR/AP open items per invoice reconciled to the old subledgers; inventory per warehouse reconciled to a physical count; bank balances to statements.
6. Posting period opened; first documents entered on the first day; first e-invoice issued and checked.
7. Full data export works ("what if we want to leave", [15-migration-ux-docs.md](../spec/15-migration-ux-docs.md)).
8. Fallback ([ADR-0003](../adr/0003-build-operating-rules.md) R13): fix forward by default. Abort is the owner's and chief accountant's decision: the open period is re-entered in the old system from NativeFlows's export. The old system stays installed and licensed, closed for entry, until the Phase 1 gate. The last clean abort point is before the first VAT return is filed from NativeFlows.

---

## First three monthly closes

- Each month: the close checklist (DS-12) run with the chief accountant; unconfirmed agent auto-posts block the close ([03-agent-safety.md](../spec/03-agent-safety.md), rule 6); stock count, partner confirmations and bank statements reconciled; the period locked by a human, never by an agent.
- The VAT return for the first tax period is generated from NativeFlows (01/GTGT) and filed by the customer.
- Agents start in shadow mode on the pilot's real transactions; an agent gains auto-posting only after its accuracy exceeds the threshold ([14-agent-workflows.md](../spec/14-agent-workflows.md)). Anonymized pilot data for evaluation stays outside the repository.
- Every defect found in production becomes a synthetic regression scenario reproduced with fictional data, never with pilot data.

## Support mode

From go-live, 30–50% of the author's time is reserved for the pilot ([10-roadmap.md](../spec/10-roadmap.md)).

- No feature releases on closing days or near tax deadlines, applied as a window ([ADR-0003](../adr/0003-build-operating-rules.md) R14): it opens when the previous period is locked and its tax return, if due, is filed, and closes 5 working days before month end. Hotfixes for defects that block operation may ship at any time.
- A release requires CI green, the latest medium and large nightly runs green, and a tested migration for any schema change (B8).
- Hotfixes follow the same six stages in [README.md](README.md#the-unit-of-work), with the regression scenario first.
- Development of Phase 2 and Phase 3 does not start before the Phase 1 gate ([10-roadmap.md](../spec/10-roadmap.md)).

## Phase 1 gate (verbatim from [10-roadmap.md](../spec/10-roadmap.md))

> the customer operates for real and closes at least 3 consecutive monthly periods, and files at least one VAT return from the system. Inventory matches the stock count, AR/AP match partner confirmations, bank balances match statements. The customer's chief accountant signs off.

Expected 3–4 months after go-live. Review [risks.md](../risks.md) at this gate and record the decision in [step-log.md](step-log.md).
