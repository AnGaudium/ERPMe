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
| Command batch | command\_batch | A set of commands simulated and executed together; every data import is posted through command batches, and large ones are staged in an import batch |
| Import batch | import\_batch, import\_row | A staged data import above 1,000 rows: a stored file, rows with their own state, validated and posted in chunks of command batches, resumable ([ADR-0030](../adr/0030-commercial-seams-and-imports.md)) |
| Migration | migration | A company's move from its old system: phased import batches, opening documents in a one-day migration fiscal year, reconciliation, completion ([ADR-0044](../adr/0044-data-migration-and-export.md)) |
| Opening balance entry | opening\_balance\_entry, opening\_open\_item\_entry | Opening documents per currency for account balances and for open items per old invoice, offset to the opening balance clearing account |
| Import key map | import\_key\_map | Map from a migrated record's external code to its ID, so corrected re-runs update instead of duplicating |
| Opening turnover | opening\_turnover | Non-posting year-to-date debit and credit turnover per account before a mid-year cut-over, read by statutory reports; owned by `ledger`, dated by start and end date ([ADR-0049](../adr/0049-statutory-reporting-and-printing.md) rule 14) |
| Simulation | simulate, plan\_hash | Principle 2 |
| Actor, principal acted for | actor, on\_behalf\_of | Actor kinds: human, agent, integration, system. A system actor is a deterministic job (costing, FX revaluation, closing entries, scheduled matching); its on\_behalf\_of is always the accountable human: the policy owner or the human who triggered the job Actor rows: `user_account`, `agent_type` with `agent_run`, `integration_client`, registered system job ([ADR-0017](../adr/0017-permission-envelope.md)). |
| Company, branch | company (company\_id), branch | The legal entity with its currency, time zone, package, regime, costing scope and fiscal calendar owner; a branch or dependent unit of it, also an analytical dimension ([ADR-0027](../adr/0027-cross-cutting-ownership.md) rule 5) |
| Document | document | Header and lines |
| Document state | draft, pending\_approval, approved, issuing, posted, reversed, canceled, closed | Documents in a final state (posted, reversed, canceled, closed) are immutable; `closed` ends an approved non-posting document that has had activity, `canceled` one that has had none; column `document.state` ([ADR-0009](../adr/0009-document-lifecycle.md)) |
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
| Change order | is\_change\_order\_allowed, pending\_version, change\_state: none, drafting, pending\_approval | A change to an approved order kept as a pending version (the version row `document.pending_version` points to) while the approved version stays in force ([ADR-0028](../adr/0028-document-lifecycle-hardening.md)) |
| Issuing | issuing, is\_e\_invoice\_capable, posting\_intent | State of an e-invoiced document after `Issue` and before posting; the frozen plan waits on the posting intent; posted on acceptance, back to draft on rejection |
| Incoming e-invoice record | e\_invoice\_record (direction incoming), e\_invoice\_record\_line, EInvoiceRecordReader | A supplier's e-invoice stored by `ImportEInvoiceRecord` (a person's XML file read by the package's reader) or by the e-invoice add-on; it raises `supplier_invoice_received` for a person or the purchase invoice agent ([ADR-0051](../adr/0051-agent-workflows.md) rule 20) |
| Completing approver | (approval row) | The approver whose approval completed a document's approval plan; an approved change proposal executes on their behalf, and they are the converter of the drafts it creates ([ADR-0055](../adr/0055-approval-pools-and-stages.md) rule 16) |
| Policy input hash | policy\_input\_hash | Hash of the inputs a policy decision evaluated; posting asks again when it changes, and an approval stands while the required procedure does not rise |
| Change proposal | change\_proposal, change\_proposal\_execution | Non-posting document holding exact commands for changes that are not documents, with their diff, the targets' expected versions and the simulated plan; executed by a consumer after a human approval ([ADR-0029](../adr/0029-proposals-and-agent-safety.md)) |
| Policy point | policy\_decision | A command at which the dispatcher evaluates policy once and the handler stores the decision: `Submit`, `Post` from draft, `Issue`, and `Post` of an approved document whose policy input hash changed; the stored record is the row Policy decision |
| Tainted version | is\_tainted, derived\_from\_version\_id | A document version written by a tainted run or derived from a tainted version; immutable, inherited by later and derived versions |
| Taint clearance | taint\_clearance | Immutable record by which a human clears a version's taint, with a reason; not a data label |
| Untrusted field | is\_untrusted | Schema attribute of a field filled from outside content; separate from data labels; a run given such a field becomes tainted |
| Auto-post | auto\_post\_confirmation, is\_confirmation\_required | A posting by actor `system` that a policy rule allowed with confirmation required; its rule owner confirms it before the period is locked |
| Partner exposure | partner\_exposure | Open receivable and payable amounts of a partner by kind and due bucket |
| Credit exposure | credit\_exposure | Partner exposure plus invoices in issuing, delivered but not invoiced value and undelivered submitted or approved orders; read under the partner lock |
| Owner partner | owner\_partner\_id | Reserved stock axis naming who owns stock we hold; null for own stock; non-owned stock has quantity and no value |
| Default bin | default\_bin\_id | The bin every warehouse gets at creation, with a default zone; the only bin of a warehouse that is not bin-managed, filled in by handlers and hidden in the UI ([ADR-0031](../adr/0031-design-simplifications.md)) |
| Pending receipt adjustment | pending\_receipt\_adjustment | A stock-bound price difference from an invoice posted before the goods arrived, consumed by the receipt |
| Subcontracting | subcontracting | Production by an outside processor from materials we send (in Vietnamese, gia công); designed in DS-55 ([ADR-0032](../adr/0032-phase-1-scope-with-production.md)) |
| Processor location | processor\_partner\_id; inventory\_at\_processor\_posting | A physical warehouse standing for a processor; stock there is ours and valued ([ADR-0037](../adr/0037-subcontracting.md)) |
| External operation | control: external; service\_item\_id, default\_supplier\_id | A routing operation done by a subcontractor, bought as a service and confirmed by a service receipt |
| Service receipt | service\_receipt; operation\_progress\_component | Purchasing's receipt of an external operation's service: records progress, consumes components at the processor, posts the service cost |
| Bill of materials | bill\_of\_materials, usage: production, kit | What an item is made from; its content lives in revisions ([ADR-0033](../adr/0033-production-master-data.md)) |
| Revision | bill\_of\_materials\_revision, routing\_revision, start\_date, content\_hash | One immutable released version of a bill of materials or routing; the valid one on a date is the highest revision started on or before it |
| Explosion date | explosion\_date | The planned start date of an order or planned order; selects production versions and revisions |
| Base quantity | base\_quantity | The output quantity that component quantities and standard times refer to |
| Component | bill\_of\_materials\_component, consumption\_method: manual, backflush\_at\_operation, backflush\_at\_receipt | An item consumed to make another, with its quantity, scrap rate and consuming operation |
| Co-product, by-product | bill\_of\_materials\_output, output\_type, cost\_coefficient | Outputs besides the main one; children of the main output for cycles and low-level codes |
| Phantom | item\_production\_setting, is\_phantom | An item never planned or made on its own; its bill of materials is exploded into its parent's |
| Routing, operation | routing, routing\_operation, routing\_operation\_activity, control: internal, external; is\_milestone | The sequence of operations that makes an item, with activity quantities per work center |
| Work center | work\_center, activity\_type, work\_center\_activity | Where operations run: capacity, calendar, activities, cost center and bins |
| Production version | production\_version | The one explicit way to make an item in a production warehouse: bill of materials, routing, lot range, dates |
| Production order | production\_order, order\_type: standard, rework, disassembly; good\_quantity, planned\_output\_quantity, scheduling\_direction | An order to make a good quantity of an item by a production version from a start date; non-posting; "released" means approved, with no Release command ([ADR-0034](../adr/0034-production-orders-and-shop-floor.md)) |
| Production order lines | production\_order\_component, production\_order\_output, production\_order\_operation, production\_order\_output\_serial | Components, outputs, operations and assigned output serials of an order |
| Execution state | execution\_state: not\_started, in\_progress, technically\_complete | How far a released order has run; technical completion ends logistics; a job closes it after settlement |
| Production issue | production\_issue, is\_return | Internal posting document issuing components to, or returning them from, an order's cost object |
| Operation confirmation | operation\_confirmation, yield\_quantity, scrap\_quantity | Internal posting document recording yield, scrap and activities of an operation, with its backflush |
| Production receipt | production\_receipt | Internal posting document receiving an order's outputs |
| Cost pool | cost\_object kind cost\_pool; pool\_allocation\_rule | One cost object per factory cost center, collecting labor and overhead until period-end allocation by its rule ([ADR-0035](../adr/0035-production-costing.md)) |
| WIP method | wip\_method: direct\_material, equivalent\_units, planned\_cost; wip\_completion\_percent | How an open order's period-end WIP is valued once it has receipts in the period |
| Units in process | units in process | Units an open order has material for but has not received; a constant per order and period |
| Normal capacity | normal\_capacity | The driver quantity at which fixed overhead is fully absorbed; below it the rest goes to cost of goods sold |
| Abnormal cost, residual cost | production\_abnormal\_cost, production\_residual\_cost | Consumption above norm at completion, and cost of a completed order with no output in the period; both to cost of goods sold |
| Cost estimate | cost\_estimate, cost\_estimate\_line, activity\_rate | Planned cost of a production version by cost component; the benchmark for target cost and variances |
| Costing lot quantity | cost\_estimate.costing\_lot\_quantity | The quantity a cost estimate is computed for; fixed quantities and setup are spread over it (ADR-0035 rule 14) |
| Target cost, variance | variance categories: input price, input quantity, resource usage, scrap, lot size, remaining | The released estimate scaled to output, and the analysis of actual against it; never posted |
| Cost behavior | cost\_behavior: variable, fixed | Whether a production cost account varies with output; splits pool groups and drives normal-capacity absorption |
| Production order period cost | production\_order\_period\_cost | Per order, period and cost component: opening, incurred, abnormal, to-output and closing amounts |
| By-product price | price\_list (kind by\_product) | The company's price list of kind `by_product`, valuing by-products (interim stand-in for net realisable value; [ADR-0045](../adr/0045-master-data-and-price-lists.md) rule 2) |
| Backflush | backflush\_at\_operation, backflush\_at\_receipt | Automatic issue of components on confirmation or receipt, by cumulative progress |
| Generated backflush line | operation\_progress\_component | A component issue generated by a confirmation, a service receipt or a production receipt, keyed by that calling document (ADR-0034 rule 12) |
| As built | output\_serial\_number\_id, is\_as\_built\_required | The link from a component lot or serial to the assigned output serial it went into |
| Low-level code | low\_level\_code | The longest path from a top item to an item in released bills of materials; MRP plans in that order |
| Where-used | where\_used | The parents that use an item as a component or output (`ListWhereUsed`) |
| Production structure | production\_structure | One row per company, locked by releases and version saves so structure checks see a stable graph |
| Has posting | has\_posting | Set on an operational account by its first journal line; freezes its code, mapping, postable flag and currency ([ADR-0010](../adr/0010-system-chart-of-accounts.md) rule 12) |
| Control kind | control\_kind | inventory, receivable, payable, gr\_ir, cost\_object, fixed\_asset, loan or none: which core module owns postings to a system account and which invariant checks it |
| Effective control kind | effective control kind | The control kind a rule applies to a line: a gated kind (`cost_object`, `fixed_asset`, `loan`) counts as `none` before the company's subledger activation ([ADR-0025](../adr/0025-later-phase-seams.md)) |
| Subledger reclassification | subledger\_reclassification | Document type created only by `ActivateSubledger`: moves an account's undimensioned balance into its subledger dimensions at the activation date |
| Subledger activation | subledger\_activation | Irreversible start of a gated subledger for a company, at a period start after earlier periods are locked, with a reclassification of the balance |
| Cost object | cost\_object | A cost collector carrying work in process; also a control kind; kinds and lifecycle designed in DS-53 ([ADR-0032](../adr/0032-phase-1-scope-with-production.md)) |
| Fixed asset | fixed\_asset | An asset record (stub until Phase 3); also a system account node and a control kind |
| Costing graph | costing\_graph | Stock nodes (item, valuation area) and cost-object nodes (production orders and cost pools, [ADR-0035](../adr/0035-production-costing.md)), linked by the period's value flows; solved per strongly connected component |
| Operational account | account | Where postings land; points to exactly one system\_account |
| Detail account | account | Operational account a package or company opens below a statutory account, e.g. 5152 under 515, so each maps to one system account ([ADR-0039](../adr/0039-vietnam-package-tt99.md)) |
| Legal form | company.legal\_form | Type of enterprise under national law (e.g. joint stock); selects chart template rows through `condition` |
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
| Planned order | planned\_order | A proposal to buy, move or produce (DS-54), with a stable business key; states proposed, firmed, converted, canceled |
| Frozen planned order | planned\_order (state proposed, release date inside the firm fence) | A proposed planned order inside the firm fence; runs keep it unchanged and count it as supply (ADR-0024 rule 19) |
| Forecast tier | forecast\_line.tier: none, short\_mean, unindexed, indexed | How much history a weekly forecast used (ADR-0024 rule 11) |
| Planning strategy | planning\_strategy: make\_to\_stock, make\_to\_order | Whether a node nets demand against free stock, or plans each sales line on its own against supply linked to it (`for_demand_supply_line_id`) ([ADR-0036](../adr/0036-multi-level-mrp.md)) |
| Dependent demand | planned\_order\_component | Component demand of a planned production order, derived each run and pegged to it |
| Availability date | availability\_date | When a planned production order's output can be used: planned end plus receiving days |
| Capacity overload, leveling proposal | capacity\_overload; ListCapacityLoad, GetCapacityLevelingProposal | An overloaded work-center range, and a read-only proposal of new order dates that fit capacity |
| Pegging | pegging (pegging\_target\_kind: demand\_line, forecast, safety\_stock, stock\_level, lot\_size\_excess, planned\_order) | What a planned order covers; sums exactly to its quantity |
| Action message | action\_message: expedite, cancel, postpone, reduce | Advice on existing supply |
| Planning exception | planning\_exception\_kind | A condition a buyer or planner must look at, e.g. shortage inside lead time or a capacity overload |
| Projected availability | projected\_availability | Day-by-day stock plus supply minus demand, as `GetProjectedAvailability` returns it |
| Goods received / invoice received clearing | gr\_ir\_clearing |  |
| Price difference | price\_difference |  |
| Price control | price\_control | Per product, read through its items ([ADR-0018](../adr/0018-product-and-item-model.md)). Phase 1: periodic weighted average with a preliminary price. Standard price and moving average after Phase 1 |
| Price list | price\_list, price\_list\_entry | Per company, kind sale, purchase or by-product, one currency, `is_tax_included` for sale lists; entries per item and unit with quantity breaks and dates, plus option extras; read by one lookup rule ([ADR-0045](../adr/0045-master-data-and-price-lists.md)) |
| Price lookup | find\_price, GetPrice | The one computation of a list price for an item, unit, quantity, date and chosen options, with the rows used for the trace ([ADR-0045](../adr/0045-master-data-and-price-lists.md) rule 4) |
| Pricing procedure | price\_line, document\_line\_price\_step | List price, base price, one promotion, manual discount, net unit price stored at the unit-price scale, line amount from it, document discount percentage allocated by largest remainder; each step stored on the line ([ADR-0047](../adr/0047-commercial-documents-and-pricing.md) rule 16) |
| Promotion | promotion | A dated percent, amount or free goods offer on an item, product or item group; at most one per line, by priority ([ADR-0047](../adr/0047-commercial-documents-and-pricing.md) rule 17) |
| Sales return, purchase return | sales\_return, purchase\_return | The posting correction that credits returned goods already invoiced, referring to the stock return lines (`return_from_customer`, `return_to_supplier`) ([ADR-0047](../adr/0047-commercial-documents-and-pricing.md) rules 7, 15) |
| GR/IR position | purchase\_order\_line\_gr\_ir\_layer | A purchase order line's unit positions, each priced once at the GR/IR price in force when first posted; postings are differences of rounded cumulative values; returns and credits take the latest positions ([ADR-0047](../adr/0047-commercial-documents-and-pricing.md) rule 13) |
| Credit hold | credit\_hold | A hold `sales` sets on demand rows of a customer over its credit limit; pick release and delivery of held lines are refused ([ADR-0047](../adr/0047-commercial-documents-and-pricing.md) rule 18) |
| Release (demand and supply rows) | not\_approved, demand\_supply\_not\_released | The hold reason a sales or purchase order's rows carry until the order is approved; unreleased demand is not demand, and pick release, delivery and receipt refuse such rows ([ADR-0047](../adr/0047-commercial-documents-and-pricing.md) rules 18–19) |
| Unknown cost | is\_cost\_unknown | A paid commercial line whose cost per inventory unit is unknown (no preliminary price, no computable configuration estimate); the seeded policy rule requires approval ([ADR-0047](../adr/0047-commercial-documents-and-pricing.md) rule 22) |
| Three-way match | match\_quantity\_exceeded, match\_price\_difference | The check of a purchase invoice against its order and receipts, within company tolerances ([ADR-0047](../adr/0047-commercial-documents-and-pricing.md) rule 14) |
| Money account | money\_account | A cash box or bank account of the company, on its own operational account ([ADR-0048](../adr/0048-cash-bank-receivables-payables.md) rule 2) |
| Payment document | cash\_receipt, cash\_payment, bank\_receipt, bank\_payment | A receipt or payment by cash or bank, whose lines settle named open items, create advances, or post to an account ([ADR-0048](../adr/0048-cash-bank-receivables-payables.md) rule 3) |
| Bank statement | bank\_statement, bank\_statement\_line | An imported statement whose lines are matched to documents by a deterministic cascade ([ADR-0048](../adr/0048-cash-bank-receivables-payables.md) rules 8–9) |
| Partner netting | partner\_netting | Settling a partner's receivables against its payables on different accounts, in one currency ([ADR-0048](../adr/0048-cash-bank-receivables-payables.md) rule 10) |
| Write-off | write\_off | Settling an item that will not be paid: a small difference, a bad debt or a payable no longer owed ([ADR-0048](../adr/0048-cash-bank-receivables-payables.md) rule 11) |
| Advance settlement | advance\_settlement | An employee's accounting for an advance with expenses ([ADR-0048](../adr/0048-cash-bank-receivables-payables.md) rule 13) |
| Cash count | cash\_count, cash\_count\_adjustment | A record of counted cash, kept as evidence; a difference is posted by the adjustment it creates ([ADR-0048](../adr/0048-cash-bank-receivables-payables.md) rule 4) |
| Currency exchange | currency\_exchange | Moving money between two money accounts in different currencies, through the unrevalued clearing account ([ADR-0048](../adr/0048-cash-bank-receivables-payables.md) rule 12) |
| Money transfer | money\_transfer | Moving money between two money accounts in one currency, one document per side, through cash in transit ([ADR-0048](../adr/0048-cash-bank-receivables-payables.md) rule 12, note) |
| Bank line match state | match\_state: unmatched, proposed, matched, ignored | A statement line's state; `proposed` names a draft or posted document the cascade or a person proposed (`proposed_document_id`, `score`, `match_basis`); `matched` only once that document is posted ([ADR-0048](../adr/0048-cash-bank-receivables-payables.md) rules 8–9, notes) |
| Counterparty unverified | counterparty\_unverified | Flag on a bank-line draft whose reference matched while no partner owns the paying account; its score is capped and it is never auto-posted ([ADR-0048](../adr/0048-cash-bank-receivables-payables.md) rule 9, note) |
| Money account balance | money\_account\_balance | The serialized row per money account holding its cumulative balance for the book rate and the floor ([ADR-0048](../adr/0048-cash-bank-receivables-payables.md) rule 12, note) |
| Collection status | open\_item\_collection, partner\_collection | Dunning level, payment block, dispute and open complaint, kept beside open items and partners ([ADR-0048](../adr/0048-cash-bank-receivables-payables.md) rule 17) |
| Evidence method | evidence\_method | How a settlement or an advance was paid, in any regime (read by deductibility conditions, ADR-0053 rule 11): cash, bank transfer, card, offset, third party, or none; matchings against advances copy the advance's method ([ADR-0048](../adr/0048-cash-bank-receivables-payables.md) rule 18; ADR-0041 rule 15) |
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
| Overlay | overlay | Country-specific content (values, enums, thresholds, account choices, legal rationale) that lives in a localization package; the core is regime-neutral and names a country only as a labelled example ([ADR-0053](../adr/0053-core-neutrality.md) rule 1) |
| Test package | l10n\_xx, is\_test\_package, test\_fixture | Fictional localization package for core tests; its entries carry the basis `test_fixture`; refused in production installations ([ADR-0053](../adr/0053-core-neutrality.md) rule 9) |
| Package template | package\_template | Package content copied into a company at setup and then owned by it: chart, determination, valuation classes, item groups, checklist, numbering, print templates |
| Package rule | package\_rule | Package content read live and dated: regime settings, tax rates, statutory reports, data labels |
| Basis | basis: legal\_source, author\_decision, unverified, company\_decision, test\_fixture (test packages only) | What every package template entry and package rule rests on; only the author sets verification and decisions (ADR-0003 R10) |
| Regime setting | regime\_setting | One dated rule of an accounting regime, read through `regime_setting(company, key, date)`; keys, schemas, date basis and company options registered by the core; a used row's value never changes |
| Work queue item | work\_item | Business work; distinct from technical jobs (job) (see also Work item) |
| Permission, capability | permission | The name of a command type or query, or a registered capability such as `post_in_soft_locked_period` or `start_agent:<agent_type>`; generated, never hand-maintained ([ADR-0017](../adr/0017-permission-envelope.md)) |
| Role, role assignment | role, role\_assignment | A company's named set of permissions, and its grant to a user with optional record and field scope; roles store levels per authorization area; templates owner, chief\_accountant, accountant, cashier, sales\_clerk, sales\_manager, buyer, purchasing\_manager, warehouse\_keeper, production\_planner, shop\_floor\_lead, auditor, it\_administrator, found by `template_code` ([ADR-0054](../adr/0054-users-roles-and-authorizations.md)); installation role operator |
| Record scope | record scope | Branches or warehouses an assignment is limited to (document headers and master data); rows outside are reported as not found; filtered results say `is_scope_filtered` |
| Field class | field\_class: cost, margin | Closed list of labels on schema fields that an assignment grants; fields of other classes are omitted from responses |
| Authorization area | authorization\_area | Node of the core tree of areas (sales, purchasing, inventory, production, planning, finance, banking, master data, administration, reports) whose leaves are document types, master data, functions and report groups; every permission has one leaf ([ADR-0054](../adr/0054-users-roles-and-authorizations.md)) |
| Authorization level | level: none, read, edit, post, full; can\_approve | What a role may do on a node and below; expanded into permissions by verb, effect class and a command's declared minimum level; approval is a separate flag |
| Owner scope | owner\_scope\_read, owner\_scope\_edit: own, team, department, branch, company | Which documents a user assignment reaches by their owner, beside record scope; everything that shows a document's data follows it |
| Document owner | owner\_employee\_id, created\_by\_user\_id, owner\_field | The employee a document belongs to (salesperson, buyer, or the creator's employee) and the human who created it |
| Department, team | department, team, team\_member | Company organization for access and routing: a tree of departments with managers, and optional teams of employees; changed only by dedicated commands at level full |
| Shared user | — | A user account with current or future role assignments in more than one company; only an operator changes its e-mail or credentials |
| User invitation | user\_invitation | A company's request to link an existing login, pending until that user confirms it or it expires (30 days by default); a new login's invitation is confirmed at creation |
| Permission hold | role\_permission\_hold | A permission an upgrade would have added to a role but held back because it would break segregation mode block or the small-company bound; a person confirms or ignores it |
| Delegation | delegation | A dated lending of a user's approval authority or role assignments to another user, never to an agent |
| Segregation rule | segregation\_rule (catalog), company\_segregation\_rule | A pair of conflicting permission sets, checked on every change of rights and on related documents |
| Small-company mode | permissions.small\_company\_mode, segregation\_exception | Company mode for at most two posting or approving users: segregation refusals become recorded exceptions, reviewed by the owner each period (flagged) |
| Policy, approval | policy, approval | An approval row binds to a document version and its `version_hash`; a new version voids it ([ADR-0009](../adr/0009-document-lifecycle.md) rule 11) |
| Document version, version hash | document\_version, version\_hash | Every change to an unposted document writes a new version; its canonical content is hashed with SHA-256 |
| Numbering series | numbering\_series | Gapless counter per company, document type, fiscal year and optional branch; posting documents are numbered at posting, by the fiscal year of the posting date ([ADR-0009](../adr/0009-document-lifecycle.md) rules 8, 15) |
| Policy decision | policy\_decision | The policy engine's outcome (allow, deny, approval required, human only) stored against a document version ([ADR-0009](../adr/0009-document-lifecycle.md) rule 11) (see also Policy point) |
| Partner, item, warehouse | partner, item, warehouse | One partner, many roles. An item is one sellable, stockable variant of a product; documents, stock and journal lines refer to items ([ADR-0018](../adr/0018-product-and-item-model.md)) |
| Product | product | What all variants share: product category, buyer, item group, valuation class, units, tracking, item tax group, price control; a product without variants has one item |
| Product type | product\_type: stock, non\_stock, service | Whether a product is kept and valued in stock |
| Variant attribute | variant\_attribute, variant\_attribute\_value, item\_variant\_value | Company-defined dimension such as color or size; any number per product; `variant_mode` is `variant` (each item has one value per such attribute, unique combination `variant_key`) or `line_option` ([ADR-0045](../adr/0045-master-data-and-price-lists.md) rule 15) (see also Characteristic) |
| Line option | variant\_mode: line\_option; document\_line\_option | An attribute chosen on a document line that creates no item, may add a price extra, and travels to delivery and production ([ADR-0045](../adr/0045-master-data-and-price-lists.md)) |
| Configurable product | product.is\_configurable | A product sold through a configuration model; its items are configured items ([ADR-0046](../adr/0046-product-configuration.md) rule 2) |
| Characteristic | variant\_attribute | An attribute of a configurable product, item-defining (variant mode) or a line option; a list or a number in a range with a step ([ADR-0046](../adr/0046-product-configuration.md) rule 3) (see also Variant attribute) |
| Configuration model | configuration\_model, configuration\_model\_revision | A product's rules, tables and defaults, in released revisions ([ADR-0046](../adr/0046-product-configuration.md) rule 4) |
| Configuration | product\_configuration | An immutable, content-addressed record of the chosen values of a product's characteristics, numbers stored as numbers; it holds no model revision ([ADR-0046](../adr/0046-product-configuration.md) rule 9) |
| Configured item | item of a configurable product | The item for one combination of item-defining values, created when a sales or production order leaves draft ([ADR-0046](../adr/0046-product-configuration.md) rule 11) |
| Selection condition | selection\_condition | A condition on item-defining characteristics that keeps a component or operation in a configured explosion ([ADR-0046](../adr/0046-product-configuration.md) rule 12) |
| Number rate | price\_list\_characteristic\_rate | A price list's rate per unit of a numeric characteristic, per inventory unit ([ADR-0046](../adr/0046-product-configuration.md) rule 15) |
| Line custom text | document\_line\_custom\_text | Free text a line gives for an `is_custom` value; personal and untrusted, kept off the shared configuration ([ADR-0046](../adr/0046-product-configuration.md) rule 9) |
| Configuration estimate | estimate\_configuration, GetConfigurationEstimate | The cost of a configuration computed from its values alone, used by cost checks before the configured item exists ([ADR-0046](../adr/0046-product-configuration.md) rule 14) |
| Serial configuration | GetSerialConfiguration | A delivered unit's item-defining values, line options and as-built components together ([ADR-0046](../adr/0046-product-configuration.md) rule 16) |
| Allowed value | product\_attribute\_value | A value a product allows for one of its attributes; none listed means every value ([ADR-0045](../adr/0045-master-data-and-price-lists.md) rule 15) |
| Option extra | price\_list\_option\_extra | A price list's extra per inventory unit for a chosen line option value, for one product or all ([ADR-0045](../adr/0045-master-data-and-price-lists.md) rule 17) |
| Declaring unit | is\_declaring\_unit | The company, or a branch that files tax returns separately with its own tax ID ([ADR-0041](../adr/0041-tax-engine.md) rule 11, [ADR-0045](../adr/0045-master-data-and-price-lists.md) rule 8) |
| Cost center kind | cost\_center.kind | `production`, `production_service`, `selling`, `administration` or `other` ([ADR-0045](../adr/0045-master-data-and-price-lists.md) rule 9) |
| Project state | project.state | `open` or `closed`; a posting to a closed project is rejected ([ADR-0045](../adr/0045-master-data-and-price-lists.md) rule 9) |
| Item created on order | is\_item\_created\_on\_order | A product whose document lines may name a new combination of variant values; the item is created when the document leaves draft ([ADR-0045](../adr/0045-master-data-and-price-lists.md) rule 16) |
| Unit of measure, inventory unit | uom, inventory\_uom\_id | Core catalog of units (companies may add their own) with quantity kind and decimal places; stock and cost are always in the product's inventory unit (the spec's stock unit) |
| Unit conversion | uom\_conversion | Exact global conversion between two units of one kind: one from-unit = numerator / denominator to-units |
| Product unit | product\_uom | Another unit a product may use, with its exact conversion to the inventory unit; with the inventory unit, the spec's UoM group |
| Item barcode | item\_barcode | Barcode of an item in one unit (e.g. a carton) |
| Barcode | barcode | A code printed as bars or a matrix that a scanner reads; in ERPMe a GS1 key, an internal code or a legacy code, registered once per company ([ADR-0061](../adr/0061-barcodes.md)) |
| Barcode registry | barcode | One row per barcode of a company, unique across item units, bins, handling units, lots, serials, barcoded documents and reserved codes, and for numeric codes on their digits padded to 14; written by a trigger on the typed tables |
| Barcode type | barcode.barcode\_type | item\_unit, bin, handling\_unit, lot, serial, document, or internal (a reserved code with no owner) |
| Internal code | — | A barcode that is not a GS1 key: one upper-case letter, then up to 47 of A–Z, 0–9, - . / \_ |
| Reserved barcode | barcode.retired\_type, barcode.retired\_owner\_id | A code retired from its object or reserved by the company; it never resolves to another object, and its own owner may take it back |
| Legacy barcode | is\_legacy\_barcode, barcode.is\_legacy | An old system's label code kept on migration: unique in the registry, may start with a digit, never parsed as GS1 or treated as a GTIN |
| GS1 element string, application identifier (AI) | erpme.gs1 | GS1 data as AIs of two to four digits, each followed by its value, separated by FNC1 (GS) after variable-length values |
| GTIN, SSCC | — | GS1 keys of a trade item (stored as 14 digits) and of a logistic unit (18 digits), each with a mod-10 check digit |
| GS1 company prefix | gs1\_company\_prefix | A prefix licensed from GS1; a company may hold several, one of which generates new GTINs |
| GS1 Digital Link | — | A URI form of GS1 keys and attributes; parsed like an element string, never fetched |
| Symbology identifier | scan.symbology\_identifier | The three characters a scanner sends before the data (]C1 for GS1-128), which tell GS1 data from plain data |
| Scan | scan | One read of a barcode, sent in a command or query as raw text with its identifier, source and decoder; the server evaluates it again |
| Scan-to-confirm, scan-to-search | EvaluateBarcode | A posting step accepts only the object or type it expects; search only opens records |
| Keyboard wedge | scan.source | A scanner that types its data into the focused field, recognized by prefix, suffix and speed |
| Barcoded document type | document.is\_barcoded | A printable type whose numbers are registered as barcodes behind a reserved prefix |
| Item label, lot label, serial label | ListItemLabel, ListLotLabel, ListSerialLabel | Print subjects that put an item unit's, a lot's or a serial's barcode on a label, with GS1 data when it has a GTIN |
| Traceability code provider | TraceabilityCodeProvider | A package interface for a country's traceability codes on labels; the core ships none |
| Set (single-value form) | Set\<Record\>\<Field\> | A command that replaces one field's value of a record that has no update command, e.g. a lot's label code (`SetLotBarcode`); the verb Set otherwise replaces a whole list of values |
| Item-level unit | product\_uom.item\_id | A product unit row for one item (a variant or configured item), resolved before the product's rows ([ADR-0056](../adr/0056-multiple-units-of-measure.md)) |
| Conversion snapshot | uom\_numerator, uom\_denominator, uom\_factor\_source | The factor a line used to convert its entered quantity to the inventory unit, and its source (identity, item, product, global); stored on the line, never re-read |
| Line unit block | quantity, uom\_id, snapshot, inventory\_quantity | The six fields every quantity line stores |
| Exact unit, inexact unit | product\_uom.is\_exact | A unit is exact when every quantity it can hold converts to a quantity the inventory unit can hold: numerator × 10^dI divisible by denominator × 10^dE |
| Cumulative conversion | convert\_part | A forward part of a source line in the source's unit takes round((C + q) × f) − P with C and P the actual net sums, so parts that complete the line sum to its inventory quantity; a return or credit takes the part it names as source |
| Unit rounding tolerance | — | Of a source line: one smallest inventory step per part posted in another unit whose conversion rounded, plus the change each return, credit, reversal or clamped part made to the deviation P − round(C × f); it only grows, is zero for exact units, and widens the upper limits and the closing check alike |
| GR/IR rounding clearing | gr\_ir\_rounding\_clearing | The consequence posting that moves the lagging GR/IR side to the other at the positions' value when a line is fulfilled within the unit rounding tolerance |
| Service receipt inventory quantity | service\_receipt\_line.inventory\_quantity | For a service, the quantity in the service item's inventory unit (hours, pieces of work); the name follows the line unit block, not stock |
| Retired unit | is\_active, retired\_at | A unit, product unit row or conversion taken out of new use; history and follow-on lines keep it; a changed pack size retires the row and a new row of the same unit takes over |
| Statutory unit name | uom.<code>.name (package terminology) | A unit's name on statutory outputs, supplied by a localization package; else the core translation |
| Factor source | product\_uom.factor\_source | How a product unit's factor was set: stated, packaging (from its contains relation) or nominal (an approximation for goods that vary per piece) |
| Packaging hierarchy | contains\_uom\_id, contains\_quantity | "1 pallet contains 40 cartons": a product unit's contained unit and whole count, checked against the factors |
| Counting unit, default pick unit | is\_counting\_unit, is\_default\_pick\_unit | Units a count may be entered in; the unit a pick list proposes |
| Supplier order unit | supplier\_item.order\_uom\_id | The unit of a supplier's minimum and multiple, and the proposed unit of its purchase lines |
| Proposed unit | proposed\_uom\_source | The unit a new line proposes, in order: source line, barcode, partner item, supplier item, product default, inventory unit |
| Unit alias | uom\_alias | Unit text as partners and old systems write it, normalized and mapped to a unit for intake; unknown text is never guessed |
| Issue multiple | bill\_of\_materials\_component.issue\_multiple | Rounds a component's order-line requirement up to whole cans, rolls or reels |
| Classification scheme | classification\_scheme, classification\_value, product\_classification | Company-defined grouping of products for analysis; `product_line` is seeded and protected; one value per scheme per product |
| Product category | product\_category | Built-in hierarchy of products that proposes defaults when a product is created |
| Item tax group, partner tax group | item\_tax\_group, partner\_tax\_group | The two axes of the dated tax matrix (with direction) that proposes and checks a line's tax codes (DS-23) |
| Tax code | tax\_code | Package rule naming one tax treatment: core kind (vat, sales\_tax, excise, customs\_duty, other) with an optional package kind, direction, calculation, transaction key, deductibility, import treatment; rates dated per code ([ADR-0041](../adr/0041-tax-engine.md)) |
| Tax matrix | tax\_matrix | Dated map from direction, partner tax group and item tax group to tax codes, as a fiscal position does |
| Document line tax | document\_line\_tax | Base, rate and tax per document line and code, part of the document's content and frozen with it |
| Tax line | tax\_line | Immutable tax subledger row written at posting, tied to the journal tax line |
| Tax line adjustment | tax\_line\_adjustment | Append-only later change of a tax line: condition met, condition failed, apportionment, period move, reversal of an adjustment ([ADR-0053](../adr/0053-core-neutrality.md) rule 3) |
| Deductibility state | deductible, conditional, not\_deductible | Projection of a purchase or import tax row from its initial state and adjustments; `conditional` means deductible while a package-declared condition can still fail ([ADR-0053](../adr/0053-core-neutrality.md) rule 3) |
| Deductibility condition | deductibility\_rules.yaml; condition\_type: payment\_evidence\_threshold | Package rule of a core condition type with the package's parameters, e.g. `l10n_vn`'s non-cash payment threshold ([ADR-0053](../adr/0053-core-neutrality.md) rule 3) |
| Package kind | package\_kind | A package's own name for a tax kind, declared in `tax/package_kinds.csv` under one core kind ([ADR-0053](../adr/0053-core-neutrality.md) rule 2) |
| Tax return | tax\_return | Immutable snapshot of a filed return; later changes appear as prior-period adjustments |
| Declaration date | declaration\_date | The date that places a tax row or adjustment in a return period |
| Report definition | report\_definition; kind: statement, book | A statutory statement or book defined as package data (a dated header and a CSV of lines or columns) and read live, or a company's own definition beside the package's ([ADR-0049](../adr/0049-statutory-reporting-and-printing.md)) |
| Report line | report\_line | One line of a statement definition: label, sources or a formula, or a check that must be zero; also a golden scenario kind |
| Measure | opening, opening\_debit, opening\_credit, debit\_turnover, credit\_turnover, change, closing, closing\_debit, closing\_credit | What an account term reads over a date range, in company currency; debit and credit parts come from the bilateral split by account, partner, or partner and open-item kind |
| Counterpart attribution | counterpart | The split of each journal entry into pairs of a positive and a negative line, in proportion and rounded so every line's pairs sum exactly; used for counterpart filters, the counterpart column of books and the direct cash flow |
| Statutory report filing | statutory\_report\_filing | Immutable snapshot of a filed statement; a later recomputation shows the difference, filed as a supplement |
| Report comparative value | report\_comparative\_value | Company data per report line and range, for comparatives before the cut-over, entered at migration |
| Print template | print\_template, print\_template\_version; audience: external, internal | Jinja2 HTML and CSS rendered to PDF; a package template copied into the company; every change is a new immutable version |
| Print data contract | print\_data\_contract | Versioned (semver) JSON Schema of what a print template receives for one subject: a document's version content plus derived print fields, or a query result |
| Print profile | print\_profile | Company or branch header data for prints: address, phone, representatives, bank details, logo, seal and signature images |
| Render job | render\_job | A request to produce a PDF, XLSX or XML file from a print template or report definition, run on queue `pdf`; its file becomes an attachment |
| Generated file | attachment source kind generated; contains\_untrusted | An attachment the render worker produced: not scanned for malware, and records its kind, audience, subject document and whether the rendered data held untrusted fields; accounting evidence when it prints a posted document or is a filed statement |
| Tracking | tracking: none, lot, serial | Whether a product's stock movements carry lots or serial numbers |
| Partner kind | partner\_kind: organization, sole\_proprietorship, individual | Decides row-conditional data labels: name, tax ID, addresses, phones, emails and bank accounts of sole proprietorships (unincorporated businesses not registered as enterprises, whose identifiers are the owner's; in Vietnam, household businesses, named by `l10n_vn`) and individuals are personal; unknown kind is treated as personal ([ADR-0019](../adr/0019-partners-and-crm-foundation.md)) |
| Partner role, profile | partner\_role; customer\_profile, supplier\_profile, employee\_profile | Roles added to one partner over time, deactivated not deleted; each role's own data in its profile, selected by the document's role. Employees are partners with the employee role |
| Contact | contact | A person at a partner; every field labeled personal |
| Processing basis | processing\_basis | Lawful basis per data subject and purpose (contract, legal obligation, consent), withdrawable; checked before sending a message whose purpose needs consent |
| Processing log | personal\_data\_processing\_log | Record of processing the law asks to log: personal fields sent to LLMs, lookups of individuals, exports, erasures |
| Data-subject request | data\_subject\_request, EraseDataSubject | Access, correction or deletion request under the Personal Data Protection Law; a document; erasure is human only and the one command that blanks append-only content |
| Interaction | interaction, interaction\_content | Append-only record of contact with a partner (email, note, call, meeting, chat, task); untrusted when from outside; the timeline adds documents by query |
| Mailbox | mailbox | Email intake per company with an owning human; messages become untrusted interactions, matched deterministically (reply thread, then authenticated sender); outside content never chooses an agent's read scope |
| Partner item | partner\_item | A partner's own code, name and unit for one of our items; the stored mappings of the purchase invoice agent |
| Partner insight, interaction summary | partner\_insight, interaction\_summary | What the system learned about a partner, as visible data: computed values with their method, summaries with their agent run |
| Inbound message | inbound\_message | One fetched e-mail per mailbox with its natural key (provider key; `Message-ID` and content hashes), sender authentication and interaction; a copy in a second mailbox points to the canonical row ([ADR-0052](../adr/0052-minimal-crm.md)) |
| Sender authentication | sender\_authentication, is\_sender\_authenticated | DMARC pass, or DKIM aligned exactly with the single `From` domain when DMARC is absent or none, read by an RFC 8601 parser only from the company's receiving server after a probe verified it; required for every automatic match |
| Partner e-mail domain | partner\_email\_domain, public\_mail\_domain | Domains that identify a partner's e-mail; public mail domains (core and package list) never do |
| Interaction link | interaction\_link, complaint\_document | References from a matched interaction or a complaint to documents or complaints of the same partner, never copies |
| Match candidate | interaction\_match\_candidate | A partner a deterministic step suggests for an unmatched message, with its best reason and rank; evidence for a person, never a match |
| Follow-up task | interaction kind task, follow\_up\_due | An interaction with a due date and an assignee; its work item holds its state |
| Complaint | complaint: open, closed | A partner's complaint with linked documents; while one is open, dunning skips the customer ([ADR-0048](../adr/0048-cash-bank-receivables-payables.md) rule 17; [ADR-0052](../adr/0052-minimal-crm.md)) |
| Processing purpose, lawful basis | processing\_purpose, lawful\_basis | A purpose of processing personal data, whether it needs consent and which outbound message types it covers; the lawful basis of a processing basis is contract, legal obligation or consent |
| Outbound message, delivery attempt | outbound\_message: draft, approved, sending, closed; outbound\_message\_delivery: sent, failed, unknown | A message draft to a partner's contacts, a document type whose subject and body sit in a content row; a person sends it after the consent and scope checks; each send is a delivery attempt, and only a sent attempt closes the message |
| Partner timeline | ListPartnerTimeline | Interactions, complaints and the partner's documents in date order, by query; untrusted fields only on request |
| Partner search key | partner\_search\_key | Normalized name (marks removed, a fixed Latin-to-ASCII fold table, package stop words) and tax ID of a partner for the deterministic duplicate search |
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
| Query | query | Read-only operation: `Get<Noun>` (one record), `List<Noun>` (filtered list). Not a command; no idempotency key; `Evaluate<Noun>` computes a result from given inputs ([ADR-0004](../adr/0004-naming-conventions.md) rule 21 note) |
| Event, event type | event, event\_type | A fact written to the outbox: `PascalCase` noun + the verb's event form, e.g. `GoodsReceiptPosted`; schema in DS-13 |
| Outbox | outbox\_event | Transactional outbox: one row per event, written in the same transaction as the state change (D4, [ADR-0013](../adr/0013-outbox-and-events.md)) |
| Event subject, subject sequence | event\_subject, subject\_sequence | The record an event is about, and its event counter 1, 2, 3, …: the only ordering of events ([ADR-0013](../adr/0013-outbox-and-events.md)) |
| Consumer | consumer | A registered handler of event types; changes data only through commands inside its delivery transaction |
| Event delivery | event\_delivery | One row per (consumer, event): pending, done, held or skipped; delivered in subject order; a held delivery blocks later ones until a human retries or skips it |
| Queue | queue (events, jobs, integrations, pdf) | Worker queues; `jobs` runs Procrastinate jobs and long-job consumers ([ADR-0031](../adr/0031-design-simplifications.md) rule 15) |
| Technical job | job | Background job on the technical queue (Procrastinate); distinct from work\_item |
| Idempotency key | idempotency\_key | Per (actor, command type), Principle 9; retention and rules in DS-04 |
| Schema version | schema\_version | Version of a command schema (semver, [07](07-shared-foundation.md#extensibility-and-upgrades)) or an event schema (DS-13); rules in DS-04 |
| Lifecycle state column | state | Column holding a lifecycle value: document, posting period, work item and every other lifecycle. Never `status` |
| Derivation trace | derivation\_trace (derivation\_trace\_id) | Record that explains a derived value (cost, price, tax): its source lines and the rules applied, Principle 6. Built thin for costing in step 3 (DS-09). Not OpenTelemetry's `trace_id`, which is kept for observability (DS-36); generic schema in [ADR-0027](../adr/0027-cross-cutting-ownership.md) rule 3 |
| Audit record | audit\_record | One immutable record per executed command: actor, on whose behalf, policy decision, agent run, subject, plan hash ([ADR-0038](../adr/0038-audit-and-observability.md)) |
| Audit change | audit\_change | Field-level before and after values of a change-tracked table, child of an audit record |
| Change tracking | is\_change\_tracked | Table declaration that makes the write helpers record field changes: master data, settings, role assignments, period state, production structures |
| Audit denial | audit\_denial | Coalesced record of commands or queries refused for permission, human-only, proposal, policy, outbound scope or segregation reasons |
| Agent run, agent type | agent\_run, agent\_type | One agent execution (actor context, taint, spend, outcome); an agent kind's declared permissions and budgets; module `agent_runs`, layer 2 |
| LLM gateway | `agents.gateway.complete` | The one function through which every LLM call goes: templates, data labels and the routing switch, cost, the processing log and replay ([ADR-0050](../adr/0050-agent-runtime-and-query-layer.md)) |
| Agent type version | agent\_type\_version | Immutable, generated record of one version of an agent type: steps, tool list, permissions, declared work item kinds, scope kind, seats, prompt templates, output schemas, budgets and evaluation threshold |
| Agent mode | agent\_type\_setting.mode: off, shadow, assisted | Per company and agent type: no runs; runs without effect whose outputs are compared with what people did; runs that draft. Agents never post |
| Agent run step | agent\_run\_step | One row of an LLM call or tool call of a run, in request and response pairs (`llm_request` and `llm_response`, `tool_request` and `tool_result`): the request row is written before the call with its reserved amount, the response row after it, with versions, tokens, cost and row references; append-only platform records, not commands |
| Run token | run token | Short-lived credential of one agent run, bound to its agent type version, tool list, human acted for and work item |
| Internal-only command | is\_internal\_only | Registry attribute of a command that only a consumer or system job runs in process, such as an outcome a worker records; no endpoint, tool or authorization level reaches it |
| Run taint | agent\_run.tainted\_at | The instant a run first received untrusted data; set once, never cleared, committed before the data is returned |
| Tainted read scope | scope\_kind: partner, import\_batch, subject | What a tainted run may read: its scope rows, its work item, the drafts of its work item, and reference data; after the taint, also what it may put into a prompt or a command input, whenever the row was read |
| Prompt template | prompt template | Versioned Markdown file from which the gateway renders an LLM request; declares its inputs, seat and output schema |
| Context item | context item | A value passed to the gateway with its field path, row, data label, field class and untrusted flag; never a free string |
| Agent budget | agent\_budget\_usage | Reserved and spent LLM cost per company, agent type and date, per company and per installation; reserved before each call, so no limit is exceeded |
| Run mode, replay | agent\_run.mode: live, shadow, replay, evaluation | Replay re-executes a run with its recorded LLM outputs and must give the same commands and plan hashes |
| Golden evaluation set | golden set | Synthetic cases per workflow with the simulator's known answer, used by replay and evaluation runs |
| Semantic view | schema `query`, `<noun>_overview` | Read-only view for agents and reports, declared with meanings, labels, field-class masking, record scope, taint scope and untrusted columns |
| Secret field | is\_secret | Schema attribute of a field holding a secret; never in a view, in a query result for an agent, or in a prompt |
| List export | list\_export (command `CreateListExport`) | A list query written by a job to an `.xlsx` attachment, with the requester's field classes and scope |
| Shadow evaluation | query `GetAgentShadowEvaluation` | Comparison of shadow-run outputs with what people did; the evidence for promoting an agent type to assisted mode ([ADR-0051](../adr/0051-agent-workflows.md)) |
| Draft-only command | is\_draft\_only | Registry attribute of commands that only create or update drafts, change proposals, notes or suggestion fields; the only commands a tainted agent run may run ([ADR-0050](../adr/0050-agent-runtime-and-query-layer.md)) |
| Agent run bodies capability | read\_agent\_run\_bodies | Capability (in the `owner` template only) to read the request and response bodies of agent run steps; access to bodies is by this capability alone |
| Document extraction | document\_extraction | What was read from one clean attachment for one purpose, with its state, reader attempts and flags ([ADR-0057](../adr/0057-document-intake-and-extraction.md)) |
| Extraction field | extraction\_field | One extracted value with its evidence, method and the engine's confidence; append-only, a correction supersedes the earlier row and keeps its type |
| Rule run | extraction\_rule\_run | One evaluation of the purpose's rules over every current field, appended after each recording, correction or confirmation; the latest counts |
| Extraction confirmation | extraction\_confirmation | A person's confirmation of a current field row |
| Reader ladder | rung | The fixed order of readers: structured XML, embedded XML, QR and vCard, spreadsheet, PDF text layer, OCR words, vision; the first valid record wins |
| Document reader | document\_reader | A registered pure reader (code, version, rung), and the tool-less agent type that adds vision values |
| Alignment | vision\_aligned, vision\_unaligned | Code's check that a vision value stands at consecutive cited OCR words of one line, numbers exactly; an unaligned value is a greyed suggestion that fills nothing |
| Closed shape | shape | The form a value type must have to be trusted: a canonical decimal, an ISO date, a catalog currency, a checked tax ID or IBAN, a code or unit resolved to a record |
| Value trust | extraction\_field\_trust | Computed when read: a normalized value that fits its shape and passed the extraction's latest rules from a deterministic reader, or that a person confirmed, carries no instruction and does not taint a run; raw text and evidence never |
| Quarantined e-invoice record | is\_quarantined | An incoming record whose signature did not pass: it holds no duplicate key and waits for a person's supplier confirmation |
| Code series | code\_series | A master-data code sequence without fiscal year or branch, such as product codes issued at a proposal's execution |
| Hidden text suspected | hidden\_text\_suspected | Text in a PDF's text layer without an OCR counterpart at its position on the rendered page; forces a full review |
| Data-processing policy | data\_processing.policy, data\_processing\_permission | The regime's rule per data class for model providers and cross-border processing, without a core default, and the company's permitted providers |
| Personal vision seat | extraction\_vision\_personal | The seat class that reads personal page images; disabled until a company configures a permitted provider |
| Extraction mapping rule | extraction\_mapping\_rule | A per-partner rule learned from corrections (a label, column header or unit text that means a field), changed only through proposals |
| Product engineering | product\_engineering | The agent type that drafts products, items, bills of materials and routings from a person's note or spreadsheet, with checks, estimate and an evidence pack ([ADR-0062](../adr/0062-product-engineering-workflow.md)) |
| Proposal-item reference | proposed\_change\_proposal\_item\_id | A draft structure's pointer to the stable ID of the proposal item that will create its item; release is blocked until it is bound |
| Cost estimate gap | cost\_estimate\_gap | What an estimate could not price (price, rate, activity quantity, pending item, unstated setup or run time); listed, never zero |
| Readiness requirement | product\_category\_requirement | A category's rule of what a product needs before release |
| Manufacturer part number | item\_manufacturer\_part | A manufacturer's code for an item, used in component resolution with its manufacturer |
| Effective agent mode | promoted\_version, promoted\_seat\_models | The mode a run uses: an assisted agent type whose version behavior or seat models differ from the promoted ones runs as shadow; the stored mode stays the person's choice |
| Shape mask | shape mask (`maskable` template input) | A personal value replaced by its shape before it reaches a model with the routing switch on: upper-case letters become `A`, other letters `a`, Unicode digits `9`, other characters kept |
| Promotion evidence | agent\_promotion\_evidence | Immutable snapshot of the shadow or rehearsal evidence for promoting an agent type: date range, behavior hash, seat models, figures and thresholds; the promotion proposal names it |
| Outbound content check | query `GetOutboundContentCheck` (check result `outbound_content_flagged`) | The check that a customer-facing draft names no other partner's records and carries no cost or margin fields; evaluated in the plan of the command that creates or updates the draft |
| Outside subject | (registry mark on subject tables) | A run subject that is outside content (an inbound interaction, an incoming e-invoice record, a bank statement line, an import batch or row, or any row whose `is_untrusted` is true); a run on it starts tainted, whoever starts it |
| Work item | work\_item | Business work for a person or agent, with claim and due date; module `work`, layer 2 (DS-29); kinds registered in [work-item-kinds.csv](../catalogs/work-item-kinds.csv) ([ADR-0042](../adr/0042-work-queue.md)) (see also Work queue item) |
| Policy rule | policy\_rule | Row of the company's threshold table: action, type, actor kind, ordered conditions, effect, owner ([ADR-0043](../adr/0043-policy-and-approval.md)). Agents, systems and integrations start from a baseline (a person posts; approval for types with no posting step) that only an allow rule lifts |
| Approval procedure | approval\_procedure | A named rank, unique per company; a policy decision's rank selects the required stages of the document's approval pool ([ADR-0055](../adr/0055-approval-pools-and-stages.md)) |
| Approval pool | approval\_pool, approval\_pool\_document\_type | A company's group of document types that share approval stages; a selector may route by a boolean policy input |
| Approval stage | approval\_stage, approval\_stage\_member | An ordered step of a pool: members, required approvals k of n, minimum rank, escalation role, due days from the day it became current |
| Approval step | approval | One person's immutable approve or reject decision at a stage, bound to a document version |
| Approval round | — | The approvals counted for one submission: from Submit until Post, a rejection, an edit or a cancel; a resubmission after a context change continues it unless the pool changes |
| Approval plan | approval\_plan | The required stages recorded in a policy decision when it is made; never empty for a decision with a rank |
| Consequence posting | is\_consequence\_posting | A deterministic posting run on behalf of the person who started its chain, evaluated by policy as that person |
| Period unlock request | period\_unlock\_request | Non-posting document asking to unlock a period area; its approval lets `UnlockPostingPeriod` run once ([ADR-0043](../adr/0043-policy-and-approval.md)) |
| Attachment | attachment, attachment\_link | File stored once per company by SHA-256, outside the database, linked to any record; module `attachments`, layer 2 |
| Scan state | attachment.state: pending\_scan, clean, rejected | Result of scanning an uploaded file; only `clean` attachments may be linked to a posted document |
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
| Check result | check\_result (response field `checks`) | A finding that does not stop a command, with code, message, rule, field and details; part of `plan_hash` by code and field ([ADR-0040](../adr/0040-ui-architecture.md)) |
| Allowed command | allowed\_command (query `ListAllowedCommand`) | A command applicable to a record now, or the error code it would return |
| Session context | session\_context (query `GetSessionContext`) | The signed-in user's companies, permissions, field classes, record scope, language and time zone, returned for the UI to draw itself |
| UI metadata | ui\_metadata (`x-erpme-*` annotations) | Hints in the generated JSON Schemas from which the renderer draws screens |
| Command palette | command\_palette | Keyboard search (`Ctrl/Cmd+K`) over the commands, queries, lists and records the user may use |
| Expected plan hash | expected\_plan\_hash | The `plan_hash` the client reviewed; required to execute; a different hash rejects the execution |
| Command registry | command\_registry | The one place where command types and queries are registered; REST, MCP, JSON Schema and TypeScript are generated from it |
| Error code | code (in `errors`) | Stable `snake_case` identifier of an error, with category, HTTP status, rule, fix and retryable flag |
| Idempotency record | idempotency\_record | Stored response of a successful execution under (actor, command type or `command_batch`, idempotency key), kept at least 90 days |
| Human only | human\_only | Registry flag on commands an agent never executes (closing periods, reversing posted documents), and an integration neither while ADR-0008 rule 2's open question stands; agents may simulate them; a system job may run one on behalf of a human only where an ADR says so ([ADR-0027](../adr/0027-cross-cutting-ownership.md) rule 12) |
| Command scope | scope: company, installation | Whether a command or query acts in one company (`company_id` required) or on the whole installation |
| User session | user\_session | A server-side sign-in session of a user account, stored as a token hash ([ADR-0017](../adr/0017-permission-envelope.md) rule 2; DS-15) |
| Credential reset | credential\_reset | A one-time password reset token, stored as a hash ([ADR-0054](../adr/0054-users-roles-and-authorizations.md) rule 4) |
| Integration token | integration\_token | An integration client's credential, stored only as a hash and valid at most one year ([ADR-0017](../adr/0017-permission-envelope.md) rule 3) |
| Installation role assignment | installation\_role\_assignment | Grant of the installation role `operator` to a user account ([ADR-0017](../adr/0017-permission-envelope.md) rule 7) |
| Role level | role\_level | A role's level and approval flag on one node of the authorization area tree, inherited downward ([ADR-0054](../adr/0054-users-roles-and-authorizations.md) rule 8) |
| Role permission | role\_permission | The stored expansion of a role's levels minus its holds in force, which the dispatcher reads ([ADR-0054](../adr/0054-users-roles-and-authorizations.md) rule 9) |
| Role assignment scope | role\_assignment\_scope | The record scope of a role assignment, one branch or warehouse per row; none means the whole company ([ADR-0017](../adr/0017-permission-envelope.md) rule 9) |
| Delegation role assignment | delegation\_role\_assignment | A role assignment of the delegator lent by a delegation of kind `role_assignments` ([ADR-0054](../adr/0054-users-roles-and-authorizations.md) rule 21) |
| Segregation review | segregation\_review | The owner's confirmed review of one posting period's segregation exceptions in the small-company mode (`ConfirmSegregationReview`, [ADR-0054](../adr/0054-users-roles-and-authorizations.md) rule 20) |
| Company currency activation | company\_currency\_activation | A currency a company has activated for use ([ADR-0011](../adr/0011-multi-currency.md) rule 7) |
| Working calendar holiday | working\_calendar\_holiday | A non-working date of a working calendar, copied from a package template entry or added by the company ([ADR-0045](../adr/0045-master-data-and-price-lists.md) rule 10) |
| Partner address | partner\_address | An address of a partner (DS-20) |
| Partner bank account | partner\_bank\_account | A partner's bank account, changed only through change proposals ([ADR-0029](../adr/0029-proposals-and-agent-safety.md) rule 4) |
| Product variant attribute | product\_variant\_attribute | A variant attribute assigned to a product, in variant mode or as a line option (DS-20; [ADR-0046](../adr/0046-product-configuration.md) rule 3) |
| Interaction participant | interaction\_participant | An address taking part in an interaction (`from`, `to`, `cc`, `bcc`, `reply_to`, `attendee`), resolved to a contact or user where possible ([ADR-0052](../adr/0052-minimal-crm.md)) |
| Data subject request content | data\_subject\_request\_content | The personal text of a data subject request, kept outside its header and version so that erasure can blank it ([ADR-0052](../adr/0052-minimal-crm.md) rule 24) |
| Outbound message content | outbound\_message\_content | The subject and body of an outbound message, kept outside its header and version ([ADR-0052](../adr/0052-minimal-crm.md) rule 27) |
| Outbound message recipient | outbound\_message\_recipient | A recipient of an outbound message, only a contact of the message's partner ([ADR-0052](../adr/0052-minimal-crm.md) rule 27) |
| Outbound message delivery recipient | outbound\_message\_delivery\_recipient | An address one delivery attempt used, copied at send ([ADR-0052](../adr/0052-minimal-crm.md) rule 28) |
| Partner tax lookup | partner\_tax\_lookup | A dated snapshot of a tax ID lookup, written by `RecordPartnerTaxLookup`; its result is untrusted ([ADR-0019](../adr/0019-partners-and-crm-foundation.md) rule 18; [ADR-0052](../adr/0052-minimal-crm.md)) |
| Configuration rule | configuration\_rule | A rule of a configuration model revision: a condition with an effect, or a `forbid` ([ADR-0046](../adr/0046-product-configuration.md) rule 6) |
| Configuration table | configuration\_table, configuration\_table\_column, configuration\_table\_row | A table of allowed value combinations in a configuration model revision, with its columns and rows ([ADR-0046](../adr/0046-product-configuration.md) rule 7) |
| Configuration default | configuration\_default | A default value of a characteristic in a configuration model revision ([ADR-0046](../adr/0046-product-configuration.md) rule 8) |
| Product configuration value | product\_configuration\_value | One value of a stored product configuration ([ADR-0046](../adr/0046-product-configuration.md) rule 9) |
| Role template | role.template\_code | A seeded set of levels from which a company role is created; owner rules `role:<template>` resolve through it, never through role codes; the list is [role-templates.csv](../catalogs/role-templates.csv) ([ADR-0054](../adr/0054-users-roles-and-authorizations.md) rule 11) |
| Bank matching rule | bank\_matching\_rule | A company rule, proposal-bound, that maps a bank description token or a counterparty account to a partner or an account, applied before step 3 of the matching cascade ([ADR-0048](../adr/0048-cash-bank-receivables-payables.md) rule 9) |
| System account turnover | system\_account\_turnover | Aggregate query view of turnover per system account, read by management reporting ([ADR-0050](../adr/0050-agent-runtime-and-query-layer.md) rules 51–53) |
| Partner item overview | partner\_item\_overview | Row view of a partner's `partner_item` rows, the only item source of a tainted quotation run ([ADR-0051](../adr/0051-agent-workflows.md) rule 10) |
| Work item owner rules | run\_on\_behalf\_of, subject\_owner, subject\_assignee | Owner rules of work item kinds: the human the agent run acts for; the user the subject names as its owner; the user the subject names as its assignee ([ADR-0042](../adr/0042-work-queue.md) rule 7 notes) |

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
| Cancel | End an open document that is not posted, or an open warehouse task, reservation, work item, delegation or invitation | Canceled |
| Clear | Remove a flag deliberately with a reason, e.g. a document version's taint (`ClearTaint`) or a sign-in lockout (`ClearUserAccountLockout`) | Cleared |
| Resume | Continue a stopped job from where it stopped, e.g. an import batch (`ResumeImport`) | Resumed |
| Abandon | Stop a job for good; what it already posted stays until reversed, e.g. an import batch | Abandoned |
| Issue | Request legal issuance of a document; it posts when the issue is accepted (e.g. `IssueSalesInvoice`) | IssueRequested |
| Record | Store an outcome reported by an outside system or by a worker that ran outside the transaction, e.g. an e-invoice outcome or a rendered file ([ADR-0049](../adr/0049-statutory-reporting-and-printing.md) rule 20) | Recorded |
| Recall | Take back a request sent to an outside system before it took effect | Recalled |
| Complete | Finish a held step by a human, e.g. a posting after acceptance; or end the logistics of a production order (technical completion); or finish a migration; or finish an agent run with its outcome (`CompleteAgentRun`) | Completed |
| Reopen | Return a document to draft after an outside step failed; or return a technically complete production order to in progress; or return a closed complaint to open | Reopened |
| Erase | Remove a data subject's personal data irreversibly | Erased |
| Request | Hand work to another module for execution, e.g. replenishment or an e-invoice | Requested |
| Pack | Put stock into a handling unit | Packed |
| Unpack | Take stock out of a handling unit | Unpacked |
| Firm | Fix a proposal so later runs keep it, e.g. a planned order | Firmed |
| Activate | Start enforcing something once, irreversibly, e.g. a subledger | Activated |
| Claim | A person or agent run takes a work item as its only worker | Claimed |
| Accept | Record that a difference found by a check stands, with a reason, e.g. a migration difference | Accepted |
| Validate | Simulate a staged batch or file without posting and record its errors | Validated |
| Export | Produce a company's full data as files | Exported |
| Unclaim | Give up the claim of a work item | Unclaimed |
| Resolve | Close a work item whose exception a person has dealt with | Resolved |
| Enable | Put something in force, reversibly, unlike Activate: a policy rule version, a user account, a segregation rule, the small-company mode | Enabled |
| Disable | Take a policy rule version, a user account, a segregation rule or the small-company mode out of force | Disabled |
| Reserve | Hold stock for a demand line, e.g. components of a production order | Reserved |
| Release | Make a draft revision of master data effective from its start date, e.g. a bill of materials revision | Released |
| Convert | Turn a record into another form once, e.g. a planned order into draft documents | Converted |
| Match | Link bank lines or documents, or an interaction and its partner; open items are settled against each other by an `open_item_matching` document | Matched |
| Unmatch | Undo a match: unlink bank lines or documents, or an interaction and its partner | Unmatched |
| Ignore | Set an imported line aside with a reason, so that no rule or person matches it ([ADR-0048](../adr/0048-cash-bank-receivables-payables.md) rule 8); or keep withheld a permission an upgrade held back (`IgnoreRolePermissionHold`) | Ignored |
| Transfer | Move records to another account or owner, e.g. a partner's open items | Transferred |
| Allocate | Distribute an amount or quantity over targets | Allocated |
| Import | Read an external file into the system | Imported |
| Set | Replace a record's whole list of values in one command, e.g. a price list's entries (`SetPriceListEntries`) | Set |
| Verify | Check or confirm data and record the result: a configuration against an outside system (`VerifyMailboxAuthentication`), or extracted values by a person (`VerifyExtractionFields`, `VerifyDocumentExtraction`) | Verified |
| Correct | Append a person's correction that supersedes an earlier value (`CorrectExtractionField`) | Corrected |
| Propose | Draft a change proposal from verified data (`ProposeContactFromExtraction`) | Proposed |
| Bind | Replace a draft's reference to a proposal item by the item its execution created (`BindProposedItems`) | Bound |
| End | End or narrow a dated permission or setting (`EndDataProcessingPermission`) | Ended |
| Run | Start a deterministic system job, e.g. period-end actual costing | Completed (`<job noun>Completed`) |
| Assign | Set the owner of a work item or a warehouse task; or attach output serials to a production order | Assigned |
| Start | A person begins work on an assigned warehouse task; or start a migration's loading or reconciliation; or start an agent run (`StartAgentRun`) | Started |
| Close | End further activity on an approved record that has had some, e.g. an order, or a change proposal once executed; or end a processing basis when consent is withdrawn or its purpose ends | Closed |
| Restrict | Narrow who may post in a posting period (open to soft-locked) | Restricted |
| Open | Let a restricted posting period accept postings from everyone with permission again (soft-locked to open) | Opened |
| Lock | Stop all postings in a posting period (soft-locked to locked) | Locked |
| Unlock | Take a locked posting period back to soft-locked, with approval | Unlocked |
| Confirm | A human confirms a fact the system cannot check, e.g. a manual close task or that they are the person a company invited (`ConfirmUserInvitation`), or accepts a result the system produced, e.g. auto-posts (`ConfirmAutoPost`) or a permission an upgrade held back (`ConfirmRolePermissionHold`) | Confirmed |
| Skip | Leave out an optional step with a reason, e.g. an optional close task | Skipped |
| Retry | Try a held step again, e.g. a held event delivery | Retried |
| Replay | Deliver retained events again to a consumer that has not handled them | Replayed |
| Render | Produce a file from a print template or a report definition, as a job; the file does not exist when the command commits ([ADR-0049](../adr/0049-statutory-reporting-and-printing.md) rule 20) | RenderRequested |
| File | Record that a statutory report or tax return was submitted to an authority, storing an immutable snapshot (`FileStatutoryReport`, `FileTaxReturn`) | Filed |
| Send | Hand a message to its outside channel for delivery, e.g. an outbound message; the outcome is recorded later | SendRequested |
| Get | Query one record by `id`; a query, not a command ([ADR-0004](../adr/0004-naming-conventions.md) rule 21) | none (queries emit no event) |
| List | Query a filtered list of records; a query, not a command | none |
| Evaluate | Query that computes a result from given inputs and stores nothing, e.g. a configuration (`EvaluateConfiguration`) ([ADR-0004](../adr/0004-naming-conventions.md) rule 21 note) | none |
| Raise | The system opens a work item for an exception it found (`work.contract.raise_work_item`, [ADR-0042](../adr/0042-work-queue.md) rule 5); no command type uses it | Raised (`WorkItemRaised`) |

Work items get the verbs Claim and Unclaim ([ADR-0042](../adr/0042-work-queue.md)), because Lock belongs to posting periods and Release to master data revisions; a command batch needs no verb ([ADR-0008](../adr/0008-command-envelope-and-registry.md) rule 20). A posted document is never canceled: it is corrected by a correction document or, if its type is internal, reversed (Principle 5, [ADR-0009](../adr/0009-document-lifecycle.md) rules 19, 23), so Cancel never applies to posted documents.

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
