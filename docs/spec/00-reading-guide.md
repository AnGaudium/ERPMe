# How AI agents read these documents

The `docs/` folder of this repository is the source specification for AI agents that design and write the code. Start here, then follow the reading order in [docs/README.md](../README.md). Read with these conventions.

1. **Precedence when documents conflict:** ADRs (`docs/adr/`) → Decided items (`docs/decisions.md`, D1–D17) → Build order and Lean scope (`docs/spec/11-build-order.md`, `docs/spec/10-roadmap.md`) → other files in `docs/spec/` → Legacy (`docs/spec/19-legacy.md`, background only). The archived Vietnamese version in `docs/archive/` is never a requirement. The two earlier documents named in [19-legacy.md](19-legacy.md) are business reference only, not requirements, and are not in this repository.
2. **Scope:** the scope of Phases 0–1 is set by the [Lean scope](10-roadmap.md#lean-scope-for-phases-0-and-1) in `10-roadmap.md` and the [Steps and gates](11-build-order.md#steps-and-gates) table in `11-build-order.md`. A "(After Phase 1)" or "(Phase 2)" label elsewhere means the data model must leave room for it, but the feature and UI are not built yet.
3. **Normative words:** "must" and "must not" are mandatory; "should" is a recommendation, and doing otherwise requires the reason in an ADR; "may" is optional.
4. **Unverified:** a legal rule marked "unverified" must not be hard-coded. Put it in the localization package as configuration, flag it, and keep it in the open questions.
5. **When the documents are silent:** do not infer accounting, tax or legal rules; record an open question and ask the author. Technical decisions are made by the agent under [ADR-0005](../adr/0005-technical-decisions-delegated.md): choose the option that is easiest for AI agents to use, consistent with ADR-0002, and record it.
6. **Code identifiers are English**, following the glossary below and the naming conventions in [ADR-0004](../adr/0004-naming-conventions.md). Never use transliterated Vietnamese for table, column, command or variable names.
7. **Reference IDs:** Principles 1–13; decisions D1–D17; Build steps 0–11; build principles B1–B8 (`11-build-order.md`); chart-of-accounts rules 1–7 (`06-localization.md`); ADR-nnnn (`docs/adr/`); design items DS-xx; invariants INV-xx (DS-16); edge cases EC-xx (DS-17, see `12-testing.md`). Commits, new ADRs and open questions must cite these IDs.

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
| Document state | draft, pending\_approval, approved, posted, reversed, canceled, closed | Documents in a final state (posted, reversed, canceled, closed) are immutable; `closed` ends an approved non-posting document that has had activity, `canceled` one that has had none; column `document.state` ([ADR-0009](../adr/0009-document-lifecycle.md)) |
| Document type | document\_type; is\_posting, is\_approval\_hold\_allowed, is\_reversible | Registered once per type; the flags say whether it posts, whether its posting may wait for approval, and whether it can be reversed ([ADR-0009](../adr/0009-document-lifecycle.md) rule 2) |
| Reversal document | reversal\_of | Points to the document it reverses; passes the same period checks as any document; for internal document types, and, as a flagged interim rule, for outside-party documents nothing refers to yet ([ADR-0009](../adr/0009-document-lifecycle.md) rule 19). Column `reversal_of_id` ([ADR-0004](../adr/0004-naming-conventions.md) rule 12) |
| Correction document | correction\_of | A return, credit note, debit note, adjustment or replacement invoice that corrects a posted document, created from it. Column `correction_of_id` ([ADR-0009](../adr/0009-document-lifecycle.md) rule 23) |
| Journal entry, journal line | journal\_entry, journal\_line |  |
| Universal journal | journal\_line | One table carrying all analytical dimensions; canonical list in [05](05-accounting-inventory-core.md) |
| Material document | material\_document | Quantities. Zero or one accounting document per material document; value-only accounting documents (e.g. revaluations) have no material document |
| System account | system\_account | Fixed in the core; catalog [system-accounts.csv](../catalogs/system-accounts.csv), which is the word list for system account codes; a tree whose leaves are postable ([ADR-0010](../adr/0010-system-chart-of-accounts.md)) |
| Account type | account\_type | asset, liability, equity, income, expense; inherited by an operational account from its system account |
| Normal balance | normal\_balance | debit or credit; the side a balance usually sits on; contra accounts have the opposite of their type |
| Contra account | is\_contra | An account that reduces another of the same type, e.g. accumulated depreciation, revenue deductions |
| Bilateral account | is\_bilateral | A receivable or payable account whose open items may sit on either side, e.g. trade receivables holding customer advances; presented split by open item kind |
| Has posting | has\_posting | Set on an operational account by its first journal line; freezes its code, mapping, postable flag and currency ([ADR-0010](../adr/0010-system-chart-of-accounts.md) rule 12) |
| Control kind | control\_kind | inventory, receivable, payable, gr\_ir or none: which core module owns postings to a system account and which invariant checks it |
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
| Posting period | posting\_period | Regular or special period of a fiscal year; states open, soft\_locked, locked per posting area ([ADR-0012](../adr/0012-posting-periods-and-closing.md)) |
| Posting area | area: general, inventory, receivable, payable | Part of a regular period opened and closed on its own; a line's area is its system account's control kind; special periods have general only |
| Special period | kind: special | Up to four periods for year-end adjustments, dated the fiscal year's last day, chosen explicitly |
| Close task | close\_task | One item of a period's close checklist, per area: job, check or manual; an area locks only when its required tasks are done and still current |
| Sequential close task | is\_sequential | A close task that must run in period order, e.g. period-end actual costing; rerunning it sets the same task of later periods back to pending |
| Entry count at done | entry\_count\_at\_done | The number of relevant entries in a task's period and area when it was done; a larger count at lock time makes the task stale |
| Fiscal calendar owner, lead days | fiscal\_calendar\_owner, fiscal\_year\_lead\_days | The human on whose behalf the next fiscal year is created, and how many days before year end (default 30) |
| Closing entry | is\_closing\_entry | Marker on journal entries posted by the closing job, so period-range reports can exclude them |
| Accounting regime | accounting\_regime | Rule set inside a localization package; the Vietnam package has two: TT99 and TT133 |
| Localization package | localization\_package | e.g. l10n\_vn, l10n\_us |
| Work queue item | work\_item | Business work; distinct from technical jobs (job) |
| Policy, approval | policy, approval | An approval row binds to a document version and its `version_hash`; a new version voids it ([ADR-0009](../adr/0009-document-lifecycle.md) rule 11) |
| Document version, version hash | document\_version, version\_hash | Every change to an unposted document writes a new version; its canonical content is hashed with SHA-256 |
| Numbering series | numbering\_series | Gapless counter per company, document type, fiscal year and optional branch; posting documents are numbered at posting, by the fiscal year of the posting date ([ADR-0009](../adr/0009-document-lifecycle.md) rules 8, 15) |
| Policy decision | policy\_decision | The policy engine's outcome (allow, deny, approval required, human only) stored against a document version ([ADR-0009](../adr/0009-document-lifecycle.md) rule 11) |
| Partner, item, warehouse | partner, item, warehouse | One partner, many roles |
| Data label | data\_label | public, internal, personal, sensitive\_personal |
| Routing switch | routing\_switch | Per company, off by default. In Phase 1, when on, personal-labeled fields are removed from every LLM request |
| Model seat | seat | Declared in seatmap.yaml |
| Synthetic dataset | synthetic\_dataset | Fictional companies generated by the business simulator; sizes small, medium, large ([12-testing.md](12-testing.md#synthetic-dataset)) |
| Golden scenario | golden\_scenario | A business case with expected results from a hand-built spreadsheet |
| Invariant | INV-xx | A named rule checked after every scenario; catalog in DS-16 |
| Edge case | EC-xx | A named situation the simulator injects at a known frequency; catalog in DS-17 |
| Module | module | Python package `erpme.<module>`; list and database layout in DS-18 ([ADR-0004](../adr/0004-naming-conventions.md)) |
| Command type | command\_type | Name of a command: `PascalCase` verb from the command verb list + glossary noun, e.g. `PostGoodsReceipt`; `snake_case` form for MCP tools and handlers |
| Query | query | Read-only operation: `Get<Noun>` (one record), `List<Noun>` (filtered list). Not a command; no idempotency key |
| Event, event type | event, event\_type | A fact written to the outbox: `PascalCase` noun + the verb's event form, e.g. `GoodsReceiptPosted`; schema in DS-13 |
| Outbox | outbox | Transactional outbox written in the same transaction as the state change (D4); design in DS-13 |
| Technical job | job | Background job on the technical queue (Procrastinate); distinct from work\_item |
| Idempotency key | idempotency\_key | Per (actor, command type), Principle 9; retention and rules in DS-04 |
| Schema version | schema\_version | Version of a command schema (semver, [07](07-shared-foundation.md#extensibility-and-upgrades)) or an event schema (DS-13); rules in DS-04 |
| Lifecycle state column | state | Column holding a lifecycle value: document, posting period, work item and every other lifecycle. Never `status` |
| Derivation trace | derivation\_trace (derivation\_trace\_id) | Record that explains a derived value (cost, price, tax): its source lines and the rules applied, Principle 6. Built thin for costing in step 3 (DS-09). Not OpenTelemetry's `trace_id`, which is kept for observability (DS-36) |
| Amount | amount | Money in any currency: domain `types.amount` (`numeric(24, 4)`), Python type `Amount`; stored at the currency's minor unit; a string in JSON ([ADR-0006](../adr/0006-id-and-numeric-model.md)) |
| Quantity | quantity | Quantity in any unit: domain `types.quantity` (`numeric(24, 6)`), Python type `Quantity`; at the unit's decimal places |
| Unit price | unit\_price | Price or cost per unit: domain `types.unit_price` (`numeric(28, 10)`), Python type `UnitPrice` |
| Exchange rate | exchange\_rate | A rate as its source publishes it, with the two currencies that give its direction: domain `types.exchange_rate` (`numeric(30, 15)`), Python type `ExchangeRate`; amounts are converted only by `convert_amount` |
| Exchange rate source | exchange\_rate\_source | A publisher of quotes with a reference currency; public (fetched by a job) or a company's own manual source ([ADR-0011](../adr/0011-multi-currency.md)) |
| Quote kind | quote\_kind | buy\_cash, buy\_transfer, sell\_cash, sell\_transfer, average, central: the published quote an `exchange_rate` row holds; SAP's exchange rate type |
| Rate type | rate\_type | A use of a rate. Lookup: transaction, revaluation, group\_translation (configured quote kind, selection date, `max_rate_age_days`). Document: document, invoice, customs, settlement |
| Applied rate | applied\_rate | The rate one conversion used, with its origin, selection date and the one or two quotes behind it; referenced by journal lines |
| Rate origin | origin (of an applied rate) | lookup, document, invoice, customs, settlement or book |
| Book rate method | book\_rate\_method | specific (per open item) or moving\_average (per account and currency), declared by the regime |
| Realized FX basis | realized\_fx\_basis | original or revalued: which carrying amount realized FX starts from after a revaluation |
| Revaluation | revaluation | Period-end job that restates foreign-currency open items and balances in company and group currency; method reverse\_and\_repost or delta, declared by the regime |
| Percent | percent | A percentage written as percent (8 means 8%): domain `types.percent` (`numeric(9, 6)`), Python type `Percent`; columns end in `_percent` |
| Minor unit | minor\_unit | Decimal places of a currency from ISO 4217 (VND 0, USD 2); amounts are stored at this precision |
| Unit conversion factor | numerator, denominator (columns) | One alternative unit = numerator / denominator stock units, two positive integers; model in DS-20 |
| Rounding line, rounding gain, rounding loss | rounding\_gain, rounding\_loss (system accounts) | The one journal line of an entry that takes its conversion rounding differences, on `rounding_gain` or `rounding_loss` by sign; operational accounts declared per company ([ADR-0006](../adr/0006-id-and-numeric-model.md) rule 20) |
| Rounding mode | rounding\_mode | Per currency: `half_up` (default), `half_even`, `down`, `up` ([ADR-0006](../adr/0006-id-and-numeric-model.md) rule 17) |
| Document date | document\_date | Date printed on the document; taken as given from an external source ([ADR-0007](../adr/0007-time-model.md)) |
| Posting date | posting\_date | On documents that post: decides the posting period, fiscal year, numbering series and balances as of a date (Principle 5); required at posting, no core default |
| Recording timestamp | recorded\_at | Instant (transaction start) of the command that wrote the row or row version; set by the system, never by a client; never an ordering key |
| Company time zone | time\_zone | IANA name per company (e.g. `Asia/Ho_Chi_Minh`); used only to turn an instant into the company's date |
| Fiscal year | fiscal\_year | Row per company with `start_date`, `end_date`, `code`; contiguous; contains regular posting periods; found by date lookup; ranges immutable once used |
| Clock | erpme.clock | The only source of the current instant and business date: `now()` is always the real transaction time; `today(company)` can be set per company in test and simulation environments (`business_date_override`). Also defines the types `BusinessDate` and `Instant` |
| Command envelope | envelope | The fields around every command payload: `command_type`, `schema_version`, `company_id`, `idempotency_key`, `mode`, `expected_plan_hash`, `payload`; the actor, `on_behalf_of` and `agent_run_id` come from the credential ([ADR-0008](../adr/0008-command-envelope-and-registry.md)) |
| Mode | mode | `simulate` (run and roll back) or `execute` (run and commit); the same envelope is sent in both |
| Plan | plan | What a command does: its journal lines and stock movements (response field `plan`) plus its result (response field `result`); `plan_hash` covers all three |
| Expected plan hash | expected\_plan\_hash | The `plan_hash` the client reviewed; required to execute; a different hash rejects the execution |
| Command registry | command\_registry | The one place where command types and queries are registered; REST, MCP, JSON Schema and TypeScript are generated from it |
| Error code | code (in `errors`) | Stable `snake_case` identifier of an error, with category, HTTP status, rule, fix and retryable flag |
| Idempotency record | idempotency\_record | Stored response of a successful execution under (actor, command type or `command_batch`, idempotency key), kept at least 90 days |
| Human only | human\_only | Registry flag on commands agents may not execute (closing periods, reversing posted documents); agents may simulate them |
| Command scope | scope: company, installation | Whether a command or query acts in one company (`company_id` required) or on the whole installation |

**Command verbs** ([ADR-0004](../adr/0004-naming-conventions.md) rules 17–22). A command type starts with one of these verbs; its event, if any, ends with the event form. The intent column says what the verb is for, nothing more: which states and preconditions allow a command is decided by DS-05 and the DS item that owns the noun. A new verb is added here, with its intent and event form, in the same change as the first command that needs it; a verb never takes a second meaning.

| Verb | Intent | Event form |
| --- | --- | --- |
| Create | Bring a new document or master-data record into existence | Created |
| Update | Change an existing document or master-data record | Updated |
| Delete | Remove a record | Deleted |
| Submit | Send a document version for approval | Submitted |
| Approve | Approve a document version | Approved |
| Reject | Reject a document version | Rejected |
| Post | Make a document part of the books or the stock records | Posted |
| Reverse | Post a reversal document for a posted document | Reversed |
| Cancel | End an open document that is not posted | Canceled |
| Match, Unmatch | Link or unlink open items, bank lines or documents | Matched, Unmatched |
| Allocate | Distribute an amount or quantity over targets | Allocated |
| Import | Read an external file into the system | Imported |
| Run | Start a deterministic system job, e.g. period-end actual costing | Completed (`<job noun>Completed`) |
| Assign | Set the owner of a work item | Assigned |
| Close | End further activity on an approved record that has had some, e.g. an order | Closed |
| Restrict | Narrow who may post in a posting period (open to soft-locked) | Restricted |
| Open | Let a restricted posting period accept postings from everyone with permission again (soft-locked to open) | Opened |
| Lock | Stop all postings in a posting period (soft-locked to locked) | Locked |
| Unlock | Take a locked posting period back to soft-locked, with approval | Unlocked |
| Confirm | A human confirms a fact the system cannot check, e.g. a manual close task | Confirmed |
| Skip | Leave out an optional step with a reason, e.g. an optional close task | Skipped |

Work items get the verbs Claim and Release from DS-29, because Lock belongs to posting periods; a command batch needs no verb ([ADR-0008](../adr/0008-command-envelope-and-registry.md) rule 20). A posted document is never canceled: it is corrected by a correction document or, if its type is internal, reversed (Principle 5, [ADR-0009](../adr/0009-document-lifecycle.md) rules 19, 23), so Cancel never applies to posted documents.

**Allowed abbreviations** ([ADR-0004](../adr/0004-naming-conventions.md) rule 2). No other abbreviation is used in an identifier. Terms not listed are written in full: `cost_of_goods_sold`, `receivable`, `payable`, `general_ledger`, `bill_of_materials`.

| Abbreviation | Stands for |
| --- | --- |
| id | identifier |
| uom | unit of measure |
| fx | foreign exchange |
| vat | value-added tax |
| gr\_ir | goods received / invoice received |
| l10n, i18n | localization, internationalization |
| llm, ui | large language model, user interface |
| api, rest, mcp, url, http, oidc | the standard interface and protocol terms |
| json, xml, html, csv, xlsx, pdf, sql | the standard file format and language names |
| pk, fk, uq, ix, ck, trg | prefixes of database constraint, index and trigger names only ([ADR-0004](../adr/0004-naming-conventions.md) rule 15) |

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
