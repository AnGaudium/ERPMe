# How AI agents read these documents

The `docs/` folder of this repository is the source specification for AI agents that design and write the code. Start here, then follow the reading order in [docs/README.md](../README.md). Read with these conventions.

1. **Precedence when documents conflict:** ADRs (`docs/adr/`) → Decided items (`docs/decisions.md`, D1–D17) → Build order and Lean scope (`docs/spec/11-build-order.md`, `docs/spec/10-roadmap.md`) → other files in `docs/spec/` → Legacy (`docs/spec/19-legacy.md`, background only). The archived Vietnamese version in `docs/archive/` is never a requirement. The two earlier Odoo-based documents are business reference only, not requirements.
2. **Scope:** the scope of Phases 0–1 is set by the Lean scope section (`10-roadmap.md`) and the Steps table (`11-build-order.md`). A "(After Phase 1)" or "(Phase 2)" label elsewhere means the data model must leave room for it, but the feature and UI are not built yet.
3. **Normative words:** "must" and "must not" are mandatory; "should" is a recommendation, and doing otherwise requires the reason in an ADR; "may" is optional.
4. **Unverified:** a legal rule marked "unverified" must not be hard-coded. Put it in the localization package as configuration, flag it, and keep it in the open questions.
5. **When the documents are silent:** do not infer accounting, tax or legal rules; record an open question and ask the author. For small technical decisions, choose the simplest option consistent with ADR-002 and record it.
6. **Code identifiers are English**, following the glossary below. Never use transliterated Vietnamese for table, column, command or variable names.
7. **Reference IDs:** Principles 1–13; decisions D1–D17; Build steps 0–11; chart-of-accounts rules 1–7; ADR-001, ADR-002; design items DS-xx. Commits, new ADRs and open questions must cite these IDs. Edge cases use EC-xx (see `12-testing.md`).

**Glossary and code identifiers:**

| Term | Code identifier | Notes |
| --- | --- | --- |
| Command | command | Pydantic schema; see Principle 1 |
| Simulation | simulate, plan\_hash | Principle 2 |
| Actor, principal acted for | actor, on\_behalf\_of | Actor kinds: human, agent, integration |
| Company, branch | company (company\_id), branch | Branch is an analytical dimension |
| Document | document | Header and lines |
| Journal entry, journal line | journal\_entry, journal\_line |  |
| Universal journal | journal\_line | One table carrying all analytical dimensions |
| Material document | material\_document | Quantities; one-to-one link to the accounting document |
| System account | system\_account | Fixed in the core |
| Operational account | account | Where postings land; points to exactly one system\_account |
| Transaction key | transaction\_key | Drives account determination |
| Valuation class | valuation\_class | Attribute of an item |
| Movement type | movement\_type | Configuration table |
| Goods received / invoice received clearing | gr\_ir\_clearing |  |
| Price difference | price\_difference |  |
| Transaction, company, group currency | transaction\_currency, company\_currency, group\_currency |  |
| Preliminary price | preliminary\_price | Valuation price used during the period |
| Period-end actual costing | period\_end\_actual\_costing | Periodic weighted average |
| Landed cost | landed\_cost | Purchase costs incurred after receipt |
| Posting period | posting\_period | States: open, soft\_locked, locked |
| Localization package | localization\_package | e.g. l10n\_vn, l10n\_us |
| Work queue item | work\_item | Business work; distinct from technical jobs (job) |
| Policy, approval | policy, approval |  |
| Partner, item, warehouse | partner, item, warehouse | One partner, many roles |
| Data label | data\_label | public, internal, personal, sensitive\_personal |
| Model seat | seat | Declared in seatmap.yaml |
