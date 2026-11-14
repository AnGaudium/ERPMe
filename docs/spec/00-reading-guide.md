# How AI agents read these documents

The `docs/` folder of this repository is the source specification for AI agents that design and write the code. Start here, then follow the reading order in [docs/README.md](../README.md). Read with these conventions.

1. **Precedence when documents conflict:** ADRs (`docs/adr/`) → Decided items (`docs/decisions.md`, D1–D17) → Build order and Lean scope (`docs/spec/11-build-order.md`, `docs/spec/10-roadmap.md`) → other files in `docs/spec/` → Legacy (`docs/spec/19-legacy.md`, background only). The archived Vietnamese version in `docs/archive/` is never a requirement. The two earlier documents named in [19-legacy.md](19-legacy.md) are business reference only, not requirements, and are not in this repository.
2. **Scope:** the scope of Phases 0–1 is set by the [Lean scope](10-roadmap.md#lean-scope-for-phases-0-and-1) in `10-roadmap.md` and the [Steps and gates](11-build-order.md#steps-and-gates) table in `11-build-order.md`. A "(After Phase 1)" or "(Phase 2)" label elsewhere means the data model must leave room for it, but the feature and UI are not built yet.
3. **Normative words:** "must" and "must not" are mandatory; "should" is a recommendation, and doing otherwise requires the reason in an ADR; "may" is optional.
4. **Unverified:** a legal rule marked "unverified" must not be hard-coded. Put it in the localization package as configuration, flag it, and keep it in the open questions.
5. **When the documents are silent:** do not infer accounting, tax or legal rules; record an open question and ask the author. For small technical decisions, choose the simplest option consistent with ADR-0002 and record it.
6. **Code identifiers are English**, following the glossary below. Never use transliterated Vietnamese for table, column, command or variable names.
7. **Reference IDs:** Principles 1–13; decisions D1–D17; Build steps 0–11; build principles B1–B8 (`11-build-order.md`); chart-of-accounts rules 1–7 (`06-localization.md`); ADR-0001, ADR-0002; design items DS-xx; invariants INV-xx (DS-16); edge cases EC-xx (DS-17, see `12-testing.md`). Commits, new ADRs and open questions must cite these IDs.

**Glossary and code identifiers:**

This glossary is authoritative. DS-01 extends it in place, in this file; there is no separate glossary file.

| Term | Code identifier | Notes |
| --- | --- | --- |
| Command | command | Pydantic schema; see Principle 1 |
| Command batch | command\_batch | A set of commands simulated and executed together; every data import is one |
| Simulation | simulate, plan\_hash | Principle 2 |
| Actor, principal acted for | actor, on\_behalf\_of | Actor kinds: human, agent, integration, system. A system actor is a deterministic job (costing, FX revaluation, closing entries, scheduled matching); its on\_behalf\_of is always the accountable human: the policy owner or the human who triggered the job |
| Company, branch | company (company\_id), branch | Branch is an analytical dimension |
| Document | document | Header and lines |
| Document state | draft, pending\_approval, approved, posted, reversed | Only posted documents are immutable |
| Reversal document | reversal\_of | Points to the document it reverses; passes the same period checks as any document |
| Journal entry, journal line | journal\_entry, journal\_line |  |
| Universal journal | journal\_line | One table carrying all analytical dimensions; canonical list in [05](05-accounting-inventory-core.md) |
| Material document | material\_document | Quantities. Zero or one accounting document per material document; value-only accounting documents (e.g. revaluations) have no material document |
| System account | system\_account | Fixed in the core |
| Operational account | account | Where postings land; points to exactly one system\_account |
| Transaction key | transaction\_key | Drives account determination: transaction key × valuation class × valuation area → operational account |
| Valuation class | valuation\_class | Attribute of an item |
| Valuation area | valuation\_area | Warehouse or company, per the company's costing policy |
| Movement type | movement\_type | Configuration table |
| Goods received / invoice received clearing | gr\_ir\_clearing |  |
| Price difference | price\_difference |  |
| Price control | price\_control | Per item. Phase 1: periodic weighted average with a preliminary price. Standard price and moving average after Phase 1 |
| Transaction, company, group currency | transaction\_currency, company\_currency, group\_currency |  |
| Preliminary price | preliminary\_price | Valuation price used during the period: the previous costed period's actual average price, or the latest receipt price for a new item or when the previous period is not yet costed |
| Period-end actual costing | period\_end\_actual\_costing | Periodic weighted average |
| Landed cost | landed\_cost | Purchase costs incurred after receipt. Same open period: added to the receipt value before period-end costing. Earlier, closed period: posted in the current period and allocated by consumer (see [05](05-accounting-inventory-core.md)) |
| Posting period | posting\_period | States: open, soft\_locked, locked |
| Accounting regime | accounting\_regime | Rule set inside a localization package; the Vietnam package has two: TT99 and TT133 |
| Localization package | localization\_package | e.g. l10n\_vn, l10n\_us |
| Work queue item | work\_item | Business work; distinct from technical jobs (job) |
| Policy, approval | policy, approval |  |
| Partner, item, warehouse | partner, item, warehouse | One partner, many roles |
| Data label | data\_label | public, internal, personal, sensitive\_personal |
| Routing switch | routing\_switch | Per company, off by default. In Phase 1, when on, personal-labeled fields are removed from every LLM request |
| Model seat | seat | Declared in seatmap.yaml |
| Synthetic dataset | synthetic\_dataset | Fictional companies generated by the business simulator; sizes small, medium, large ([12-testing.md](12-testing.md#synthetic-dataset)) |
| Golden scenario | golden\_scenario | A business case with expected results from a hand-built spreadsheet |
| Invariant | INV-xx | A named rule checked after every scenario; catalog in DS-16 |
| Edge case | EC-xx | A named situation the simulator injects at a known frequency; catalog in DS-17 |

**Regulatory terms:** definitions only; the rules themselves are in the localization files and the open questions.

| Term | Meaning |
| --- | --- |
| VAS | Vietnamese Accounting Standards |
| TT200, TT99/2025, TT133 | Ministry of Finance circulars that set accounting regimes |
| T-VAN | Tax data transmission service provider |
| HTKK, eTax | Tax return software (HTKK) and the tax authority's online portal (eTax) |
| 01/GTGT | VAT return form |
| B01, B02, B03 | Balance sheet, income statement, cash flow statement |
| Law 91/2025/QH15 | Personal Data Protection Law |
| Decree 70/2025 | Decree on e-invoices |
| VAT Law 48/2024 | Value-added tax law |
