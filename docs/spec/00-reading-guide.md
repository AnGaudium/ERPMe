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
| Actor, principal acted for | actor, on\_behalf\_of | Actor kinds: human, agent, integration, system. A system actor is a deterministic job (costing, FX revaluation, closing entries, scheduled matching); its on\_behalf\_of is always the accountable human: the policy owner or the human who triggered the job Actor rows: `user_account`, `agent_type` with `agent_run`, `integration_client`, registered system job ([ADR-0017](../adr/0017-permission-envelope.md)). |
| Company, branch | company (company\_id), branch | The legal entity with its currency, time zone, package, regime, costing scope and fiscal calendar owner; a branch or dependent unit of it, also an analytical dimension ([ADR-0027](../adr/0027-cross-cutting-ownership.md) rule 5) |
| Document | document | Header and lines |
| Document state | draft, pending\_approval, approved, posted, reversed, canceled, closed | Documents in a final state (posted, reversed, canceled, closed) are immutable; `closed` ends an approved non-posting document that has had activity, `canceled` one that has had none; column `document.state` ([ADR-0009](../adr/0009-document-lifecycle.md)) |
| Document type | document\_type; is\_posting, is\_approval\_hold\_allowed, is\_reversible | Registered once per type; the flags say whether it posts, whether its posting may wait for approval, and whether it can be reversed ([ADR-0009](../adr/0009-document-lifecycle.md) rule 2) |
| Reversal document | reversal\_of | Points to the document it reverses; passes the same period checks as any document; for internal document types, and, as a flagged interim rule, for outside-party documents nothing refers to yet ([ADR-0009](../adr/0009-document-lifecycle.md) rule 19). Column `reversal_of_id` ([ADR-0004](../adr/0004-naming-conventions.md) rule 12) |
| Correction document | correction\_of | A return, credit note, debit note, adjustment or replacement invoice that corrects a posted document, created from it. Column `correction_of_id` ([ADR-0009](../adr/0009-document-lifecycle.md) rule 23) |
| Journal entry, journal line | journal\_entry, journal\_line |  |
| Universal journal | journal\_line | One table carrying all analytical dimensions; canonical list in [05](05-accounting-inventory-core.md); final columns in [ADR-0014](../adr/0014-universal-journal.md) |
| Side | side | debit or credit: the turnover column a journal line belongs to; amounts are signed, debit positive and credit negative |
| Storno line | is\_storno | A journal line flagged as storno: its amounts have the sign opposite to its side and reduce that side's turnover (SAP's negative posting) |
| General journal, balance transfer | document types general\_journal, balance\_transfer | Document types for manual journal entries and for moving a balance between operational accounts |
| Database transaction number | database\_transaction\_number | The PostgreSQL transaction that created a journal entry, set by a trigger; a posted entry never gains lines |
| Account period balance | account\_period\_balance | Cache of turnover and cumulative balance per account, period, transaction currency and closing-entry flag, written when a period is locked |
| Material document | material\_document | Quantities. Zero or one accounting document per material document; value-only accounting documents (e.g. revaluations) have no material document |
| System account | system\_account | Fixed in the core; catalog [system-accounts.csv](../catalogs/system-accounts.csv), which is the word list for system account codes; a tree whose leaves are postable ([ADR-0010](../adr/0010-system-chart-of-accounts.md)) |
| Account type | account\_type | asset, liability, equity, income, expense; inherited by an operational account from its system account |
| Normal balance | normal\_balance | debit or credit; the side a balance usually sits on; contra accounts have the opposite of their type |
| Contra account | is\_contra | An account that reduces another of the same type, e.g. accumulated depreciation, revenue deductions |
| Bilateral account | is\_bilateral | A receivable or payable account whose open items may sit on either side, e.g. trade receivables holding customer advances; presented split by open item kind |
| Open item | open\_item (open\_item\_kind: invoice, credit, advance, payment\_on\_account, loan, other) | One obligation with a partner on one account, created by one journal line; its amounts are the sum of the lines that refer to it ([ADR-0026](../adr/0026-open-item-core.md)) |
| Natural side | natural\_side: debit, credit | Which side an open item sits on: debit when the partner owes, credit when the company owes |
| Settlement | settle (state is\_settled) | A line that reduces an open item, partly or fully; matching is settlement of two items against each other |
| Carrying amount | carrying amount | An open item's open company or group amount as of a date, including or excluding revaluation per the regime |
| Installment | installment\_number | One due part of a document under its payment term; each is its own control line and open item |
| Payment term | payment\_term, payment\_term\_line | Installments of a document: percent, due days, base date and optional early-payment discount |
| Open item matching | open\_item\_matching | Internal document that settles two items of one partner and account against each other |
| Partner exposure | partner\_exposure | Open receivable and payable amounts of a partner by kind and due bucket |
| Has posting | has\_posting | Set on an operational account by its first journal line; freezes its code, mapping, postable flag and currency ([ADR-0010](../adr/0010-system-chart-of-accounts.md) rule 12) |
| Control kind | control\_kind | inventory, receivable, payable, gr\_ir, cost\_object, fixed\_asset, loan or none: which core module owns postings to a system account and which invariant checks it |
| Effective control kind | effective control kind | The control kind a rule applies to a line: a gated kind (`cost_object`, `fixed_asset`, `loan`) counts as `none` before the company's subledger activation ([ADR-0025](../adr/0025-later-phase-seams.md)) |
| Subledger reclassification | subledger\_reclassification | Document type created only by `ActivateSubledger`: moves an account's undimensioned balance into its subledger dimensions at the activation date |
| Subledger activation | subledger\_activation | Irreversible start of a gated subledger for a company, at a period start after earlier periods are locked, with a reclassification of the balance |
| Cost object | cost\_object | A cost collector carrying work in process; also a control kind; kinds and lifecycle designed in Phase 2 |
| Fixed asset | fixed\_asset | An asset record (stub until Phase 3); also a system account node and a control kind |
| Costing graph | costing\_graph | Stock nodes (item, valuation area) and, from Phase 2, cost-object nodes, linked by the period's value flows; solved per strongly connected component |
| Operational account | account | Where postings land; points to exactly one system\_account |
| Transaction key | transaction\_key | Drives account determination: transaction key × valuation class × valuation area → operational account; catalog [transaction-keys.csv](../catalogs/transaction-keys.csv) ([ADR-0015](../adr/0015-account-determination.md)) |
| Account determination | account\_determination | Company table mapping a transaction key and determinant values to an operational account; the row that matches on the most significant determinants wins (key order); cross-checked against the key's required system accounts |
| Determinant | determinants | What a transaction key's account depends on, most significant first: valuation\_class, warehouse, item\_group, partner\_group, tax\_code, currency |
| Item group | item\_group | Company grouping of items for revenue, cost of goods sold and consumption accounts |
| Partner group | partner\_group | Company grouping of partners that gives new partners their default reconciliation accounts |
| Valuation class | valuation\_class | Attribute of a stock item; company data seeded from the regime template; drives inventory account determination |
| Valuation area | valuation\_area\_level, valuation\_warehouse\_id | The company, or a physical warehouse with its attached transit and goods-sent warehouses, per the company's costing policy (`valuation_area_level`), not changeable by command once stock is posted; a line records it as `valuation_warehouse_id` (null at company level) |
| Movement type | movement\_type | Core catalog [movement-types.csv](../catalogs/movement-types.csv): direction, value source, costing role and offset transaction key of a stock movement ([ADR-0020](../adr/0020-inventory-and-costing-model.md)) |
| Value source | value\_source: document, preliminary\_price, issuing\_value, regime | How a movement type finds the value of a line; for returns and count differences a required regime setting |
| Costing role | costing\_role: receipt, revalued\_issue, transfer, regime | How a movement type takes part in period-end costing: enters the receipts, is revalued to the actual average, or moves value between areas |
| Preliminary price | preliminary\_price | Deterministic price per item, valuation area and period that issues use until period-end costing; error `preliminary_price_missing` when none can be found |
| Warehouse kind | kind: physical, transit, goods\_sent | Goods on the way and goods sent but still owned are warehouses of their own kinds, attached to a physical warehouse's valuation area; the kind picks the inventory key |
| Material document line | material\_document\_line | One stock movement: item, warehouse, movement type, quantity in the inventory unit, lot or serial, value |
| Stock quantity, stock value | stock\_quantity, stock\_value | Quantity per item, warehouse, bin, lot or serial, stock status and handling unit (ADR-0023); value per item and warehouse; changed only through the stock lock helper |
| Lot, serial number | lot, serial\_number | Tracking of stock movements, with no cost of their own; lots may carry expiry dates |
| Stock count | stock\_count | Counted quantities; differences post as count shortage and surplus movements |
| Bin management | is\_bin\_managed, outbound\_flow: direct, staged | Warehouse settings: every stock row has a bin; outbound picks go to the default shipping bin (direct) or through staging and packing (staged) ([ADR-0023](../adr/0023-warehouse-management.md)) |
| Zone, bin, bin type | zone, bin, bin\_type | Storage places inside a warehouse |
| Stock status | stock\_status: available, quality\_inspection, blocked | A classification of stock usability (not a lifecycle state); carries no value |
| Handling unit, handling unit type | handling\_unit, handling\_unit\_type | A pallet, carton or tote with its own barcode; one nesting level in Phase 1; carries no value |
| Storage condition | storage\_condition | Company data such as ambient, cold or hazardous, matched by putaway rules |
| Warehouse movement | warehouse\_movement | Quantity-only move inside one warehouse (bin, status, handling unit); no journal entry |
| Warehouse task | warehouse\_task | Work in a warehouse: putaway, pick, replenishment, move, status change, count; states open, assigned, in\_progress, confirmed, canceled |
| Putaway rule, removal strategy | putaway\_rule, removal\_strategy: fefo, fifo | Rule tables that choose target bins and the stock to pick, deterministically |
| Stock reservation, available to promise | stock\_reservation, available\_to\_promise | Stock held for a demand line; available stock minus reserved quantities until the goods issue |
| Pick batch | pick\_batch | Pick tasks of several demand documents walked together; a wave is a batch released at a set time |
| Pick face | bin\_item | The fixed picking bin of an item in a warehouse, with minimum and maximum quantities for replenishment |
| Demand line | demand line | A document line that needs stock (sales order line, transfer order line; production component later); reservations and pick tasks serve it |
| Putaway preview | putaway\_preview | Query result showing the bins a draft putaway rule set would choose |
| Planning parameters | item\_warehouse\_planning | Planning method, source, levels, safety stock, lot size, firm horizon and receiving days of an item in a warehouse ([ADR-0024](../adr/0024-planning.md)) |
| Supplier item, supplier purchasing term, supplier item lead time | supplier\_item, supplier\_purchasing\_term, supplier\_item\_lead\_time | A supplier's lead times, minimum, multiple and preference per item; minimum amount and container capacity per supplier; measured lead-time mean and deviation |
| Replenishment request | replenishment\_request | Hand-over of converted planned orders from planning to the purchasing and inventory modules |
| Sales history | sales\_history | Imported weekly sales per item and warehouse for weeks before the first posting, written by `ImportSalesHistory` ([ADR-0024](../adr/0024-planning.md)) |
| Demand event | demand\_event | A calendar-tagged event such as Tết with its date window per year, used for event indices |
| Transfer route | transfer\_route | Source and destination warehouse with lead time, for transfer replenishment |
| Working calendar | working\_calendar | Working weekdays and holidays of a warehouse or supplier |
| Demand and supply line | demand\_supply\_line | Read model of open demand and supply per item, warehouse and date, written by documents |
| Forecast, forecast run, forecast adjustment | forecast, forecast\_run, forecast\_adjustment | Weekly statistical demand spread to days; the job that computes it; a recorded change with a reason |
| Planning run | planning\_run | The deterministic netting job; stores input and output hashes |
| Planned order | planned\_order | A proposal to buy, move or (Phase 2) produce, with a stable business key; states proposed, firmed, converted, canceled |
| Pegging | pegging (pegging\_target\_kind: demand\_line, forecast, safety\_stock, stock\_level, lot\_size\_excess) | What a planned order covers; sums exactly to its quantity |
| Action message | action\_message: expedite, cancel, postpone, reduce | Advice on existing supply |
| Planning exception | planning\_exception\_kind | A condition a buyer must look at, e.g. shortage inside lead time |
| Projected availability | projected\_availability | Day-by-day stock plus supply minus demand, as `GetProjectedAvailability` returns it |
| Goods received / invoice received clearing | gr\_ir\_clearing |  |
| Price difference | price\_difference |  |
| Price control | price\_control | Per product, read through its items ([ADR-0018](../adr/0018-product-and-item-model.md)). Phase 1: periodic weighted average with a preliminary price. Standard price and moving average after Phase 1 |
| Transaction, company, group currency | transaction\_currency, company\_currency, group\_currency |  |
| Period-end actual costing | period\_end\_actual\_costing | Periodic weighted average |
| Landed cost | landed\_cost | Receipt value adjustment: allocates amounts held on `purchase_cost_clearing` (duty, freight, price differences) to receipt lines. Same period: added to the receipt value before costing. Locked period: posted in the first unlocked period, split by consumer ([ADR-0021](../adr/0021-landed-cost.md)) |
| Landed cost line, target, allocation | landed\_cost\_line, landed\_cost\_target, landed\_cost\_allocation (mode: open, closed) | A cost with its source journal line; the receipt lines it goes to; the computed share per target with its basis snapshot and mode (open: added to the receipt's period; closed: split for a locked period) |
| Landed cost correction | landed\_cost\_correction | Correction type of a landed cost: signed differences per cost line and target |
| Closed-period method | landed\_cost.closed\_period\_method: consumer\_split, stock\_coverage | Regime setting: how landed cost for a locked receipt period is split between consumers and stock |
| Cost type | cost\_type: capitalized\_tax, freight, insurance, handling, price\_difference, other | Kind of a landed cost line |
| Allocation method | allocation\_method: value, quantity, weight, manual | How a landed cost line is divided among its targets, exactly, by largest remainder |
| Customs declaration | customs\_declaration | Step 5 posting document of what customs assessed for an import; taxes as tax-code rows (`customs_declaration_tax`); proposes a landed cost; corrected by `customs_declaration_amendment` |
| Import treatment | import\_treatment: capitalize, recoverable | Tax code attribute: whether an import tax is added to the goods' cost or recovered as input tax; a package rule |
| Posting period | posting\_period | Regular or special period of a fiscal year; states open, soft\_locked, locked per posting area ([ADR-0012](../adr/0012-posting-periods-and-closing.md)) |
| Posting area | area: general, inventory, receivable, payable | Part of a regular period opened and closed on its own; a line's area is its system account's control kind; special periods have general only |
| Special period | kind: special | Up to four periods for year-end adjustments, dated the fiscal year's last day, chosen explicitly |
| Close task | close\_task | One item of a period's close checklist, per area: job, check or manual; an area locks only when its required tasks are done and still current |
| Sequential close task | is\_sequential | A close task that must run in period order, e.g. period-end actual costing; rerunning it sets the same task of later periods back to pending |
| Entry count at done | entry\_count\_at\_done | The number of relevant entries in a task's period and area when it was done; a larger count at lock time makes the task stale |
| Fiscal calendar owner, lead days | fiscal\_calendar\_owner, fiscal\_year\_lead\_days | The human on whose behalf the next fiscal year is created, and how many days before year end (default 30) |
| Future posting periods | future\_posting\_periods | Company setting, default 1: how many regular periods after the current one accept postings ([ADR-0012](../adr/0012-posting-periods-and-closing.md) rule 6) |
| Closing entry | is\_closing\_entry | Marker on journal entries posted by the closing job, so period-range reports can exclude them |
| Accounting regime | accounting\_regime | Rule set inside a localization package; the Vietnam package has two: TT99 and TT133 |
| Localization package | localization\_package | e.g. l10n\_vn, l10n\_us; a directory with a manifest, data files and interface code ([ADR-0016](../adr/0016-localization-package-structure.md)) |
| Package template | package\_template | Package content copied into a company at setup and then owned by it: chart, determination, valuation classes, item groups, checklist, numbering, print templates |
| Package rule | package\_rule | Package content read live and dated: regime settings, tax rates, statutory reports, data labels |
| Basis | basis: legal\_source, author\_decision, unverified, company\_decision | What every package template entry and package rule rests on; only the author sets verification and decisions (ADR-0003 R10) |
| Regime setting | regime\_setting | One dated rule of an accounting regime, read through `regime_setting(company, key, date)`; keys, schemas, date basis and company options registered by the core; a used row's value never changes |
| Work queue item | work\_item | Business work; distinct from technical jobs (job) |
| Permission, capability | permission | The name of a command type or query, or a registered capability such as `post_in_soft_locked_period` or `start_agent:<agent_type>`; generated, never hand-maintained ([ADR-0017](../adr/0017-permission-envelope.md)) |
| Role, role assignment | role, role\_assignment | A company's named set of permissions, and its grant to a user with optional record and field scope; templates owner, chief\_accountant, accountant, warehouse\_keeper, sales, purchasing, viewer; installation role operator |
| Record scope | record scope | Branches or warehouses an assignment is limited to (document headers and master data); rows outside are reported as not found; filtered results say `is_scope_filtered` |
| Field class | field\_class: cost, margin | Closed list of labels on schema fields that an assignment grants; fields of other classes are omitted from responses |
| Policy, approval | policy, approval | An approval row binds to a document version and its `version_hash`; a new version voids it ([ADR-0009](../adr/0009-document-lifecycle.md) rule 11) |
| Document version, version hash | document\_version, version\_hash | Every change to an unposted document writes a new version; its canonical content is hashed with SHA-256 |
| Numbering series | numbering\_series | Gapless counter per company, document type, fiscal year and optional branch; posting documents are numbered at posting, by the fiscal year of the posting date ([ADR-0009](../adr/0009-document-lifecycle.md) rules 8, 15) |
| Policy decision | policy\_decision | The policy engine's outcome (allow, deny, approval required, human only) stored against a document version ([ADR-0009](../adr/0009-document-lifecycle.md) rule 11) |
| Partner, item, warehouse | partner, item, warehouse | One partner, many roles. An item is one sellable, stockable variant of a product; documents, stock and journal lines refer to items ([ADR-0018](../adr/0018-product-and-item-model.md)) |
| Product | product | What all variants share: product category, buyer, item group, valuation class, units, tracking, item tax group, price control; a product without variants has one item |
| Product type | product\_type: stock, non\_stock, service | Whether a product is kept and valued in stock |
| Variant attribute | variant\_attribute, variant\_attribute\_value, item\_variant\_value | Company-defined dimension such as color or size; any number per product; each item has one value per attribute, unique combination (`variant_key`) |
| Unit of measure, inventory unit | uom, inventory\_uom\_id | Core catalog of units (companies may add their own) with quantity kind and decimal places; stock and cost are always in the product's inventory unit (the spec's stock unit) |
| Unit conversion | uom\_conversion | Exact global conversion between two units of one kind: one from-unit = numerator / denominator to-units |
| Product unit | product\_uom | Another unit a product may use, with its exact conversion to the inventory unit; with the inventory unit, the spec's UoM group |
| Item barcode | item\_barcode | Barcode of an item in one unit (e.g. a carton) |
| Classification scheme | classification\_scheme, classification\_value, product\_classification | Company-defined grouping of products for analysis; `product_line` is seeded and protected; one value per scheme per product |
| Product category | product\_category | Built-in hierarchy of products that proposes defaults when a product is created |
| Item tax group, partner tax group | item\_tax\_group, partner\_tax\_group | The two axes of the dated tax matrix (with direction) that proposes and checks a line's tax codes (DS-23) |
| Tracking | tracking: none, lot, serial | Whether a product's stock movements carry lots or serial numbers |
| Partner kind | partner\_kind: organization, household\_business, individual | Decides row-conditional data labels: name, tax ID, addresses, phones, emails and bank accounts of household businesses and individuals are personal; unknown kind is treated as personal ([ADR-0019](../adr/0019-partners-and-crm-foundation.md)) |
| Partner role, profile | partner\_role; customer\_profile, supplier\_profile, employee\_profile | Roles added to one partner over time, deactivated not deleted; each role's own data in its profile, selected by the document's role. Employees are partners with the employee role |
| Contact | contact | A person at a partner; every field labeled personal |
| Processing basis | processing\_basis | Lawful basis per data subject and purpose (contract, legal obligation, consent), withdrawable; checked before sending a message whose purpose needs consent |
| Processing log | personal\_data\_processing\_log | Record of processing the law asks to log: personal fields sent to LLMs, lookups of individuals, exports, erasures |
| Data-subject request | data\_subject\_request, EraseDataSubject | Access, correction or deletion request under the Personal Data Protection Law; a document; erasure is human only and the one command that blanks append-only content |
| Interaction | interaction, interaction\_content | Append-only record of contact with a partner (email, note, call, meeting, chat); untrusted when from outside; the timeline adds documents by query |
| Mailbox | mailbox | Email intake per company with an owning human; messages become untrusted interactions, matched deterministically (reply thread, then authenticated sender); outside content never chooses an agent's read scope |
| Partner item | partner\_item | A partner's own code, name and unit for one of our items; the stored mappings of the purchase invoice agent |
| Partner insight, interaction summary | partner\_insight, interaction\_summary | What the system learned about a partner, as visible data: computed values with their method, summaries with their agent run |
| Buyer | buyer\_id | The employee (a partner with the employee role) responsible for purchasing a product |
| Data translation | data\_translation | Names users enter for company data in other languages (products, variant values, company units, classification values); an item's display name is the product name plus its variant values |
| Data label | data\_label | public, internal, personal, sensitive\_personal |
| Routing switch | routing\_switch | Per company, off by default. In Phase 1, when on, personal-labeled fields are removed from every LLM request |
| Model seat | seat | Declared in seatmap.yaml |
| Synthetic dataset | synthetic\_dataset | Fictional companies generated by the business simulator; sizes small, medium, large ([12-testing.md](12-testing.md#synthetic-dataset)) |
| Golden scenario | golden\_scenario | A business case with expected results from a hand-built spreadsheet; directory with `scenario.yaml`, the author's workbook (single source) and the generated `expected.csv` ([DS-16](../design/DS-16-invariants-and-harness.md)) |
| Regression scenario | regression\_scenario | The shrunk event sequence of a defect, frozen with `expected_failure` until fixed and kept in CI |
| Proposed scenario | proposed\_scenario | Events proposed by the test-scenario model, without expected values |
| Naive recomputation | erpme\_reference | Expected results computed from the business-event log alone, written from the spec without core code |
| Check point | check\_point: command, day, run | When an invariant is checked: around each command, after each simulated day or state-machine step, or at the end of a run |
| Outcome class | outcome: must\_succeed, must\_reject, may\_reject | Expected result of a business event, set before execution by the simulator or state machine, never by the core (INV-19) |
| Violation | violation | JSON record of a failed check: check ID (INV-xx, REF-…, PAR-xx), business keys, expected and actual, first failing command |
| Invariant checker, scenario tool | erpme-check, erpme-scenario | CLIs: run the invariant registry read-only against a database (JSON output); export, freeze and run scenarios |
| Test tooling packages | erpme\_events, erpme\_client, erpme\_adapters, erpme\_testkit, erpme\_reference, erpme\_simulator | Top-level packages outside `erpme` that the product never imports (DS-16, DS-17) |
| Invariant | INV-xx | A named rule checked at its check point (around commands, after each simulated day); catalog [invariants.csv](../catalogs/invariants.csv) (DS-16) |
| Edge case | EC-xx | A named situation the simulator injects at a known frequency; catalog [edge-cases.csv](../catalogs/edge-cases.csv) (DS-17) |
| Business event, business event type | business\_event, business\_event\_type | A fact of the business written by the simulator (`goods_received`): snake\_case enumerated values in the past tense, never outbox events; contrast the core event `GoodsReceiptPosted` (ADR-0004 rule 22) |
| Business-event log | business\_event\_log | JSON Lines of business events, one per line with `ref`, outcome class and retry flag; schema `docs/catalogs/business-events.schema.json` ([DS-17](../design/DS-17-synthetic-dataset.md)) |
| Simulator triple | (simulator version, seed, dataset version) | Identifies a run; with the package and catalog versions it yields a byte-identical log and input files |
| Adapter | erpme\_adapters.step\_n | Translates business events mechanically into the commands that exist at build step n; decides no accounting |
| Profile | profile | Versioned simulator parameters for a dataset size, e.g. `vn_trading_small@1` |
| Module | module | Python package `erpme.<module>`; list, layers and database layout in [ADR-0022](../adr/0022-repository-and-engineering-conventions.md) |
| Posting interface | `<module>.contract.<verb>_<noun>` | A function in a module's `contract.py` that takes the caller's `context` and writes within the calling command's transaction and plan (ADR-0022 rule 4) |
| Composition root | erpme.app | Registers every module's handlers and runs startup checks; entry points `erpme serve`, `erpme worker`, `erpme admin` |
| Build step marker | build\_step | `[tool.erpme] build_step` in the root `pyproject.toml`: the current build step, raised by the author at each gate |
| Developer CLI | erpme-dev | Runs every check; CI jobs call only its subcommands (ADR-0022 rule 14) |
| Check role | erpme\_check | Database role for invariant checks: SELECT only, subject to RLS |
| Command type | command\_type | Name of a command: `PascalCase` verb from the command verb list + glossary noun, e.g. `PostGoodsReceipt`; `snake_case` form for MCP tools and handlers |
| Query | query | Read-only operation: `Get<Noun>` (one record), `List<Noun>` (filtered list). Not a command; no idempotency key |
| Event, event type | event, event\_type | A fact written to the outbox: `PascalCase` noun + the verb's event form, e.g. `GoodsReceiptPosted`; schema in DS-13 |
| Outbox | outbox\_event | Transactional outbox: one row per event, written in the same transaction as the state change (D4, [ADR-0013](../adr/0013-outbox-and-events.md)) |
| Event subject, subject sequence | event\_subject, subject\_sequence | The record an event is about, and its event counter 1, 2, 3, …: the only ordering of events ([ADR-0013](../adr/0013-outbox-and-events.md)) |
| Consumer | consumer | A registered handler of event types; changes data only through commands inside its delivery transaction |
| Event delivery | event\_delivery | One row per (consumer, event): pending, done, held or skipped; delivered in subject order; a held delivery blocks later ones until a human retries or skips it |
| Queue | queue (events, jobs, integrations, pdf) | Procrastinate queues of the technical queue |
| Technical job | job | Background job on the technical queue (Procrastinate); distinct from work\_item |
| Idempotency key | idempotency\_key | Per (actor, command type), Principle 9; retention and rules in DS-04 |
| Schema version | schema\_version | Version of a command schema (semver, [07](07-shared-foundation.md#extensibility-and-upgrades)) or an event schema (DS-13); rules in DS-04 |
| Lifecycle state column | state | Column holding a lifecycle value: document, posting period, work item and every other lifecycle. Never `status` |
| Derivation trace | derivation\_trace (derivation\_trace\_id) | Record that explains a derived value (cost, price, tax): its source lines and the rules applied, Principle 6. Built thin for costing in step 3 (DS-09). Not OpenTelemetry's `trace_id`, which is kept for observability (DS-36); generic schema in [ADR-0027](../adr/0027-cross-cutting-ownership.md) rule 3 |
| Agent run, agent type | agent\_run, agent\_type | One agent execution (actor context, taint, spend, outcome); an agent kind's declared permissions and budgets; module `agent_runs`, layer 2 |
| Work item | work\_item | Business work for a person or agent, with claim and due date; module `work`, layer 2 (DS-29) |
| Attachment | attachment, attachment\_link | File stored once per company by SHA-256, outside the database, linked to any record; module `attachments`, layer 2 |
| Effect class | effect\_class: posting, master\_data\_change, outbound\_send, other | Registry attribute of every command, used by agent-safety checks (INV-80) |
| Stock document types | goods\_receipt, delivery, stock\_transfer, stock\_count, internal\_consumption, other\_receipt, other\_issue, scrap, return\_to\_supplier, return\_from\_customer, opening\_balance, transfer\_order | Core documents of module `inventory` (ADR-0027 rule 7); `opening_balance` here is stock only, account opening balances have their own type (DS-21) |
| Validity naming | start\_date, end\_date; effective\_from; \_at | Date validity uses start and end dates; dated settings use effective\_from; points in time end in \_at |
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
| Unit conversion factor | numerator, denominator (columns) | One alternative unit = numerator / denominator stock units, two positive integers; model in [ADR-0018](../adr/0018-product-and-item-model.md) |
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
| Human only | human\_only | Registry flag on commands an agent never executes (closing periods, reversing posted documents), and an integration neither while ADR-0008 rule 2's open question stands; agents may simulate them; a system job may run one on behalf of a human only where an ADR says so ([ADR-0027](../adr/0027-cross-cutting-ownership.md) rule 12) |
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
| Cancel | End an open document that is not posted, or an open warehouse task or reservation | Canceled |
| Erase | Remove a data subject's personal data irreversibly | Erased |
| Request | Hand work to another module for execution, e.g. replenishment or an e-invoice | Requested |
| Pack, Unpack | Put stock into or take it out of a handling unit | Packed, Unpacked |
| Firm | Fix a proposal so later runs keep it, e.g. a planned order | Firmed |
| Activate | Start enforcing something once, irreversibly, e.g. a subledger | Activated |
| Convert | Turn a record into another mode or form once: a warehouse to bin management, a planned order into draft documents | Converted |
| Match, Unmatch | Link or unlink bank lines or documents; open items are settled against each other by an `open_item_matching` document | Matched, Unmatched |
| Transfer | Move records to another account or owner, e.g. a partner's open items | Transferred |
| Allocate | Distribute an amount or quantity over targets | Allocated |
| Import | Read an external file into the system | Imported |
| Run | Start a deterministic system job, e.g. period-end actual costing | Completed (`<job noun>Completed`) |
| Assign | Set the owner of a work item or a warehouse task | Assigned |
| Start | A person begins work on an assigned warehouse task | Started |
| Close | End further activity on an approved record that has had some, e.g. an order | Closed |
| Restrict | Narrow who may post in a posting period (open to soft-locked) | Restricted |
| Open | Let a restricted posting period accept postings from everyone with permission again (soft-locked to open) | Opened |
| Lock | Stop all postings in a posting period (soft-locked to locked) | Locked |
| Unlock | Take a locked posting period back to soft-locked, with approval | Unlocked |
| Confirm | A human confirms a fact the system cannot check, e.g. a manual close task | Confirmed |
| Skip | Leave out an optional step with a reason, e.g. an optional close task | Skipped |
| Retry | Try a held step again, e.g. a held event delivery | Retried |
| Replay | Deliver retained events again to a consumer that has not handled them | Replayed |

Work items get the verbs Claim and Release from DS-29, because Lock belongs to posting periods; a command batch needs no verb ([ADR-0008](../adr/0008-command-envelope-and-registry.md) rule 20). A posted document is never canceled: it is corrected by a correction document or, if its type is internal, reversed (Principle 5, [ADR-0009](../adr/0009-document-lifecycle.md) rules 19, 23), so Cancel never applies to posted documents.

**Allowed abbreviations** ([ADR-0004](../adr/0004-naming-conventions.md) rule 2). No other abbreviation is used in an identifier. Terms not listed are written in full: `cost_of_goods_sold`, `receivable`, `payable`, `general_ledger`, `bill_of_materials`.

| Abbreviation | Stands for |
| --- | --- |
| id | identifier |
| uom | unit of measure |
| fx | foreign exchange |
| vat | value-added tax |
| gr\_ir | goods received / invoice received |
| fefo, fifo | first expired first out, first in first out |
| hs | Harmonized System (customs commodity codes) |
| l10n, i18n | localization, internationalization |
| llm, ui | large language model, user interface |
| api, rest, mcp, url, http, oidc | the standard interface and protocol terms |
| sdk, db, crm | software development kit, database, customer relationship management (module names, ADR-0022) |
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
