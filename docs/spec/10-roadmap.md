# Roadmap and phase gates

No parallel run with the old accounting software: the pilot customer goes live fully on the new system, tax books included. Full accounting is therefore in the first go-live phase, and that phase's gate must be strict. Each phase opens only when the previous one passes its gate. Timeframe 12–18 months. No commitment to any pilot customer until the platform is complete, i.e. Build step 10 has passed its gate.

1. **Phase 0 · Foundation:** command layer, append-only journal, multi-company, localization packages with accounting regimes, minimal extensibility (module boundaries), pipeline GitHub → test server for the core (staging is built at step 10, [ADR-0003](../adr/0003-build-operating-rules.md) R2), a model running scenarios continuously on the test server, invariant tests, the small and medium synthetic datasets for the Vietnamese company (one year of transactions in the medium size).
   - Gate (same as Build step 4): the medium synthetic dataset (Vietnamese company, one year) replays day by day through core commands, called through REST and MCP, with every invariant green after every simulated day. Costing, FX and balances match the golden scenarios and the naive recomputation. The coverage report shows every edge case for steps 1–3 exercised.
2. **Phase 1 · Go-live with a trading pilot:** minimal CRM (partners, contacts, interaction timeline, email intake), sales, purchasing, imports and landed cost, multi-currency with FX revaluation, multiple warehouses and barcode, warehouse management ([ADR-0023](../adr/0023-warehouse-management.md)), full accounting with the Vietnam package and the basic US package (cash, bank, AR/AP, tax and e-invoicing, periodic weighted average cost, period close, books, financial statements), Vietnamese print templates as configuration. Agents ([ADR-0078](../adr/0078-agent-simplification-for-phase-1.md)): purchase invoices, bank statement matching, the in-app assistant with analysis, the vision reader of document intake, and planning after the planning slice with multi-level MRP; data migration, quotation, the auto-post advisor and the other agents come after Phase 1.
   - Gate: the customer operates for real and closes at least 3 consecutive monthly periods, and files at least one VAT return from the system. Inventory matches the stock count, AR/AP match partner confirmations, bank balances match statements. The customer's chief accountant signs off.
3. **Phase 2 · Assembly:** multi-level BOM, production cost, disassembly.
   - Gate: an assembly customer closes production cost for one period, matching a manual spreadsheet.
4. **Phase 3 · Expansion:** fixed assets, loans, full approval, chat channels (Zalo OA), repeat-sales suggestions, website and e-commerce from seeded skills, AI customization pipeline per customer, local models. Phases 2 and 3 start after Phase 1 passes its gate.
   - Gate: a reference customer with audited financial statements. At least one partner deploys independently without the author.

Pilot selection criteria for the first pilot only; they do not limit the target market (select and commit only after the platform is complete): a trading business of 10–50 people, imports and foreign-currency transactions allowed, a chief accountant willing to switch fully, an owner who commits time, regular incoming e-invoices, agreement to share anonymized data for agent evaluation, kept outside the repository (pilot data never enters the repository). Go live at the start of an accounting period, preferably a quarter, so opening balances are clean.

## Lean scope for Phases 0 and 1

Phases 0 and 1 build only what a trading business, including importers with foreign-currency transactions, needs to operate for real. The build carries no calendar dates and no dated plan: the build order and the gates are the only schedule, with no deadline and no customer commitment (author, 2026-11-19). The schema still leaves room for later parts (catch weight, multi-level approval, user-defined fields); only features and UI are deferred.

| Order | Work |
| --- | --- |
| Step 0 | ADRs, repo, CI, test server, small synthetic dataset |
| Steps 1–2 | Universal journal, two-tier chart and Vietnam package, master data, currencies and rates |
| Steps 3–4 | Inventory, costing, landed cost; sequential replay of the medium synthetic dataset |
| Step 4b | Production core (Phase 1, [ADR-0032](../adr/0032-phase-1-scope-with-production.md)): starts after step 4's gate and may run beside step 5; its gate check is the independent naive recomputation |
| Steps 5–7 | Commercial documents including imports, cash and AR/AP including foreign currency, tax and e-invoicing. Assistant and analysis agents (after step 5), bank matching (after step 6), purchase invoices and the vision reader (after step 7), planning after the planning slice with multi-level MRP |
| Steps 8–9 | Period close, FX revaluation, reports, print templates, hand-built screens, warehouse app |
| Step 10 | Platform completion on the large synthetic dataset, TT133 regime, localization skill and basic US package |
| After platform completion | Step 11: select pilot, rehearsal, go-live at the start of an accounting period, preferably a quarter |
| After go-live | Close 3 monthly periods and one tax period, pass the Phase 1 gate |

**Built in full from the start** (cheap now, very expensive later):

- The pydantic command layer is the single source for REST, MCP and TypeScript types.
- Append-only journal, numbering at posting, posting periods.
- `company_id` on every table, `Decimal` for money and quantities, transaction and company currency on every document and journal line. UI strings through i18n, English source; no country rules in the core.
- Idempotency and stock posting serialized per (item, warehouse).
- `actor` and `on_behalf_of` on every command.
- Data labels and the routing switch, off by default. Phase 1 has no local models: when the switch is on, personal-labeled fields are removed from every LLM request, and the gateway rejects a request that still contains one.
- Every operation works with LLMs turned off.

**Built thin:**

- Simulation: run the real command in a transaction and roll back; hash the resulting journal lines and stock movements as `plan_hash`. No separate simulation code.
- Policy engine: a threshold table per action type, no rule language yet. One-level approval.
- Cost trace only for costing.
- Agent evaluation: replay of recorded responses in CI, plus a real-LLM evaluation run whenever a model or prompt changes. No scheduled multi-provider runs yet.
- CRM: partners, contacts, interaction timeline, email intake, quotations.
- LLM gateway: one provider behind a common interface.
- UI: list and form screens generated from command schemas for most screens. Hand-built only for the 6 most-used entry screens: sales invoice, goods receipt, goods issue, cash receipt, cash payment, journal entry.

Planning is designed in [ADR-0024](../adr/0024-planning.md); its phase is the author's decision (open question).

**After Phase 1:** form builders and custom tables (a minimal custom-field seam, definitions plus `custom_values` on the listed masters and document headers, is in Phase 1, [ADR-0074](../adr/0074-core-data-structure-additions.md)), plugin SDK, per-customer AI customization pipeline, multi-provider seatmap, scheduled multi-provider evaluation runs, local models and pseudonymization, catch weight, other countries' localization packages (by the community), additional e-invoice providers, pgvector, chat channels, offline warehouse app, multi-level approval, assembly (Phase 2).

**Support time:** from go-live, reserve 30–50% of time for the pilot customer. No feature releases on closing days or near tax deadlines.
