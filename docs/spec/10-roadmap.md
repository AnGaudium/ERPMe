# Roadmap and phase gates

No parallel run with the old accounting software: the pilot customer goes live fully on the new system, tax books included. Full accounting is therefore in the first go-live phase, and that phase's gate must be strict. Each phase opens only when the previous one passes its gate. Timeframe 12–18 months. No commitment to any pilot customer until the platform is complete, i.e. Build step 10 has passed its gate.

1. **Phase 0 · Foundation:** command layer, append-only journal, multi-company, accounting regime packages, minimal extensibility (module boundaries), pipeline GitHub → test server → staging for the core, a model running scenarios continuously on the test server, invariant tests, a sample Vietnamese company with one year of transactions.
   - Gate (same as Build step 4): ledger, inventory and costing replay the reference dataset at core-command level, through REST and MCP, and pass the step 4 comparisons. Invariant tests green. The invariant checker runs after every test-model scenario.
2. **Phase 1 · Go-live with a trading pilot:** minimal CRM (partners, interaction timeline, email intake), sales, purchasing, imports and landed cost, multi-currency with FX revaluation, multiple warehouses and barcode, full accounting with the Vietnam package and the basic US package (cash, bank, AR/AP, tax and e-invoicing, periodic weighted average cost, period close, books, financial statements), Vietnamese print templates as configuration. Agents: purchase invoices, data migration, quotations, bank statement matching.
   - Gate: the customer operates for real and closes at least 3 consecutive monthly periods, and files at least one VAT return from the system. Inventory matches the stock count, AR/AP match partner confirmations, bank balances match statements. The customer's chief accountant signs off.
3. **Phase 2 · Assembly:** multi-level BOM, production cost, disassembly.
   - Gate: an assembly customer closes production cost for one period, matching a manual spreadsheet.
4. **Phase 3 · Expansion:** fixed assets, loans, full approval, chat channels (Zalo OA), repeat-sales suggestions, website and e-commerce from seeded skills, AI customization pipeline per customer, local models. Phases 2 and 3 start after Phase 1 passes its gate.
   - Gate: a reference customer with audited financial statements. At least one partner deploys independently without the author.

Pilot selection criteria (select and commit only after the platform is complete): a trading business of 10–50 people, imports and foreign-currency transactions allowed, a chief accountant willing to switch fully, an owner who commits time, regular incoming e-invoices, agreement to share anonymized data for the agent evaluation suite. Go live at the start of an accounting period so opening balances are clean.

## Lean scope for Phases 0 and 1

Phases 0 and 1 build only what a trading business, including importers with foreign-currency transactions, needs to operate for real. Month estimates below are estimates; gates are the conditions. Within 18 months, the Phase 1 gate lands around months 15–18. The schema still leaves room for later parts (full UoM groups, catch weight, multi-level approval, user-defined fields); only features and UI are deferred.

| Month (estimate) | Work |
| --- | --- |
| 1 | Step 0: ADRs, repo, CI, test server, reference data |
| 1–3 | Steps 1–2: universal journal, two-tier chart and Vietnam package, master data, currencies and rates |
| 3–5 | Steps 3–4: inventory, costing, landed cost; reference data import and reconciliation. Data migration agent |
| 5–8 | Steps 5–7: commercial documents including imports, cash and AR/AP including foreign currency, tax and e-invoicing. Quotation, bank matching and purchase invoice agents |
| 8–10 | Steps 8–9: period close, FX revaluation, reports, print templates, hand-built screens, warehouse app |
| 10–12 | Step 10: platform completion on one year of reference data, TT133, localization skill and basic US package |
| After platform completion | Step 11: select pilot, rehearsal, go-live at the start of a quarter |
| 3–4 months after go-live | Close 3 monthly periods and one tax period, pass the Phase 1 gate |

**Built in full from the start** (cheap now, very expensive later):

- The pydantic command layer is the single source for REST, MCP and TypeScript types.
- Append-only journal, numbering at posting, posting periods.
- `company_id` on every table, `Decimal` for money and quantities, transaction and company currency on every document and journal line. UI strings through i18n, English source; no country rules in the core.
- Idempotency and stock posting serialized per (item, warehouse).
- `actor` and `on_behalf_of` on every command.
- Data labels and the routing switch, off by default.
- Every operation works with LLMs turned off.

**Built thin:**

- Simulation: run the real command in a transaction and roll back; hash the resulting journal lines and stock movements as `plan_hash`. No separate simulation code.
- Policy engine: a threshold table per action type, no rule language yet. One-level approval.
- Cost trace only for costing.
- Agent evaluation: replay of recorded responses in CI, plus a real-LLM evaluation run whenever a model or prompt changes. No scheduled multi-provider runs yet.
- CRM: partners, contacts, interaction timeline, email intake, quotations.
- LLM gateway: one provider behind a common interface.
- UI: list and form screens generated from command schemas for most screens. Hand-built only for the 5–6 most-used entry screens: sales invoice, goods receipt, goods issue, cash receipt, cash payment, journal entry.

**After Phase 1:** user-defined fields and tables, plugin SDK, per-customer AI customization pipeline, multi-provider seatmap, local models and pseudonymization, catch weight, other countries' localization packages (by the community), additional e-invoice providers, pgvector, chat channels, offline warehouse app, multi-level approval, assembly (Phase 2).

**Support time:** from go-live, reserve 30–50% of time for the pilot customer. No feature releases on closing days or near tax deadlines.
