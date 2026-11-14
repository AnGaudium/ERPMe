# Build order

The goal is to build each layer once, never building and fixing at the same time. Rework usually comes from five sources: changing the data model after modules depend on it, building features before the accounting core is proven correct, building UI before commands are stable, building frameworks before a real need, and learning customer requirements too late. The principles and order below block each source.

**Principles:**

1. **Decide early what is expensive to change.** The ADR list below is decided before the first line of code.
2. **Build inside out.** Each layer passes its gate before the layer above is built. A lower layer changes its contract only for a measured reason.
3. **Commercial documents are a thin layer that emits core commands.** Sales orders, goods receipts and invoices only emit stock and journal commands already verified in the lower layer. Adding a new document never changes the core.
4. **Reference results exist before code.** Golden scenarios, invariants and the reference dataset exist before or alongside the corresponding layer, so each layer is built right the first time.
5. **Reference data from the first month, but no customer commitment.** The reference dataset is our own synthetic dataset: fictional companies whose transactions a seeded simulator feeds to the system day by day, as in real operation (see Continuous testing). Odoo's demo data is used only as a checklist of what kinds of data to prepare; nothing is copied. Build against this data; the pilot is chosen only when the platform is complete.
6. **Hand-built UI and agents always come later.** While building, use the schema-generated UI to operate and test. Hand-built screens come only after the module's commands pass their gate. An agent comes only after its manual path works.
7. **No frameworks before need.** Policy engine, approval and extensibility are built exactly as far as the first concrete case requires; generalize at the second or third case.
8. **Change the schema freely before go-live; freeze it 4 weeks before go-live.** Without real data, schema changes are nearly free, so concentrate risky changes there. After go-live every schema change needs a migration of real data.

**Decide by ADR before writing code:**

- ID model; precision of quantity, unit price, company currency, foreign currency.
- Document date, posting date, recording timestamp, time zone.
- Command envelope: `actor`, `on_behalf_of`, idempotency key, `plan_hash`, schema version.
- Document lifecycle and versioning, numbering, posting periods.
- Universal journal and its dimensions; material documents separate from accounting documents; transaction key × valuation class → account.
- Costing model: price control per item, period-end actual costing, movement types table, GR/IR clearing account.
- Multi-currency: transaction, company and optional group currency; rate types (transaction, book, revaluation, customs); FX rules inside the accounting regime package.
- Landed cost: a command adjusting receipt value after goods receipt, with the issued share allocated to COGS, linked to the customs declaration and cost documents.
- Analytical dimensions (branch, warehouse, salesperson), and reserved columns for UoM groups, lots and serials.
- Outbox event format.
- Localization package structure, the system chart and many-to-one mapping rules, i18n with English source.

**Steps and gates:**

| Step | What to build | Gate before the next step |
| --- | --- | --- |
| 0 · Preparation | ADRs above. Repo, CI with pyright strict, test server, invariant-checking harness. Edge-case catalog v1 and the first version of the business simulator (fictional Vietnamese and US companies). First golden scenarios | ADRs decided. The simulator produces the small dataset for the Vietnamese and US companies |
| 1 · Ledger | Two-tier chart (system and operational) and the localization package mechanism, Vietnam package with TT99 and FX rules, universal journal posting in transaction and company currency, i18n with English source, append-only journal, reversal, numbering, posting periods, command envelope, outbox, REST and MCP generated from schemas | Invariants green on random transaction sequences, foreign currency included. Trial balance correct |
| 2 · Master data | Partners, items, basic UoM, warehouses, currencies, daily rate table, valuation classes, transaction key → account table | Reference master data imports through command batches |
| 3 · Inventory, costing, landed cost | Movement types table; material documents for receipts, issues, transfers; stock posting serialized per (item, warehouse); period-end actual costing (existing periodic-average engine ported); receipt value adjustment for landed cost with the issued share allocated to COGS; valuation posts journal lines | Matches golden scenarios, including imports with later costs, and the independent recomputation. No negative stock |
| 4 · Sequential replay of the synthetic dataset | Sequential import of the medium dataset through core commands, day by day with month-end closes: opening balances including foreign currency, journal lines and stock movements | One year replays with every invariant green after every simulated day. Costing, FX and balances match the golden scenarios and the naive recomputation. The coverage report shows every edge case for steps 1–3 exercised |
| 5 · Commercial documents | Quotation, sales order, delivery, sales invoice; purchase request, PO, goods receipt, purchase invoice, including foreign currency, via the GR/IR clearing account and three-way match on quantity and price; customs declaration with its own customs rate; purchase cost documents allocated by value, quantity or weight; returns, discounts, credit limit. Each document emits only step 1 and step 3 commands | Import purchase → receipt → sale → issue runs end to end through REST and MCP; books equal step 4 |
| 6 · Cash and AR/AP | Cash receipts and payments, bank statement import, manual matching, open items per invoice, netting, advances; foreign-currency payments, book rate, realized FX differences | AR/AP subledgers match accounts 131 and 331 in both transaction and company currency. Cash and bank books match |
| 7 · Tax and e-invoicing | Date-effective tax rates, import VAT, outgoing e-invoices via BKAV, incoming e-invoices, 01/GTGT XML | Tax amounts on the synthetic dataset match the independent tax recomputation; the 01/GTGT return matches a hand-built golden return |
| 8 · Period close and reports | Period-close checklist, period-end FX revaluation, closing entries, Vietnamese books, B01, B02, print templates as configuration | Period close on reference data matches the golden scenarios and the naive recomputation, FX differences included |
| 9 · Hand-built UI and warehouse app | 5–6 most-used entry screens, warehouse screens with barcode | An outside accountant enters one real day of documents, no slower than MISA |
| 10 · Platform completion | Replay the large synthetic dataset (several companies, several years, about 100,000 documents a year) through commercial documents (not only core commands), fix every difference, add TT133; write the AI skill for localization packages and use it to build the basic US package; write deployment documentation | The large dataset passes every invariant and reference comparison, and the coverage report shows every edge case exercised. This is the platform-complete milestone; pilot selection starts here |
| 11 · Pilot selection and go-live rehearsal | Select the pilot, build the reader for their current system if it does not exist yet (e.g. MISA for a Vietnamese pilot), load their real data on staging, replay their latest month, freeze the schema | The rehearsal month matches the customer's books in their current system. The chief accountant agrees to go live |

Steps 0–4 correspond to Phase 0; steps 5–11 are the Phase 1 build before go-live. Step 4 comes before commercial documents on purpose: the core is proven correct on the reference dataset before any layer depends on it. The step 11 rehearsal runs on staging; it is not a production parallel run with the old software.

Agents are not a separate step. Each agent is built right after its manual path passes its gate: data migration after step 4, quotation after step 5, bank matching after step 6, purchase invoices after step 7. All four are done before the platform counts as complete.
