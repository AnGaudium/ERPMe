# ADR-0035: Production costing

Status: accepted (2026-11-14) under ADR-0005, reviewed by Claude Fable 5.2 (builder Claude Opus 5.5). Design item: DS-53 (new). Related decisions: D6. Principles 6, 12, 13. ADR-0005, ADR-0008, ADR-0010, ADR-0012, ADR-0014, ADR-0015, ADR-0016, ADR-0020, ADR-0021, ADR-0025, ADR-0027, ADR-0031, ADR-0032, ADR-0033, ADR-0034. Research: [reference systems](../research/2026-11-14-production/01-reference-systems.md), [Vietnamese rules](../research/2026-11-14-production/02-vietnam-rules.md). Lab: [design validation](../reviews/2026-11-14-design-validation/README.md), findings L-05 and L-06.

## Decision

Production cost is periodic actual cost, solved exactly per period. It extends the period-end costing of ADR-0020 rule 12 with cost-object nodes (ADR-0025 rule 6), so that one solve values these together:
- stock, transfers, production orders, rework cycles and co-products;
- WIP by cost component across periods;
- the overhead pools that production consumes.

During the period, issues and receipts post at preliminary prices. At period end the costing job allocates pools, takes out unabsorbed and abnormal cost, moves collected cost into WIP, and revalues issues and receipts to actual. It records each order's period cost by component.

A released cost estimate per production version is the benchmark for target cost and variance analysis. It never values stock unless the author chooses standard cost valuation (ADR-0032 rule 3; TT99 allows it).

The lab ran this exact model over two periods (finding L-06), and every check passed:
- pools fed by indirect materials, split into fixed and variable parts;
- normal capacity, and an idle pool;
- activity and constant bases;
- the three WIP methods, carried by component;
- abnormal cost at completion;
- a residual on a completed order;
- a capped planned WIP;
- a by-product and co-products;
- a rework cycle;
- a singular component;
- rounding to the minor unit.

Value was conserved exactly in both periods.

Linearity holds because of three restrictions this ADR makes:
- allocation weights are quantities or constants, never solved values;
- units in process and completion shares are constants;
- abnormal cost is assessed when an order completes.

The accounting choices are the author's (ADR-0005 item 1). Each one below is a regime or company setting with a flagged interim (rule 18).

### Rules

**Cost objects and collection**

1. `cost_object` (ADR-0025 rule 2, owned by `production`) has `kind`, which is `production_order` (one per order, ADR-0034 rule 15) or `cost_pool` (one per cost center that collects production cost); `production_order_id` or `cost_center_id`, matching the kind; and `state` (`open`, `closed`).

   Note: cost object states (holistic review 2026-11-15, item P27). A `production_order` cost object becomes `closed` when its order is closed ([ADR-0034](0034-production-orders-and-shop-floor.md) rule 7). A `cost_pool` cost object becomes `closed` when its cost center is deactivated and the period's job has left its balance at zero. A line naming a closed cost object is rejected with `cost_object_closed`, except the lines of `production_cost_settlement`, which may still post to it when a period is reopened and solved again ([ADR-0034](0034-production-orders-and-shop-floor.md) rule 6's table).
2. Collection:
   - **Material** reaches orders through issues.
   - **Labor and overhead** reach the cost center's pool through their own documents: payroll journals, depreciation, service invoices, and internal consumption to a factory cost center. A posting handler fills the pool of the line's cost center when a line on a production cost leaf names a cost center and no cost object. With neither, the line is rejected (`control_dimension_missing`).
   - **External operations** (DS-55) post the service cost directly to the order's `production_cost_other`.
   - **One name per component.** The cost components are `material`, `labor`, `overhead` and `other`. Each matches a production cost leaf (`production_cost_material`, `_labor`, `_overhead`, `_other`) and a pool group of the same name. `other` holds external services.
   - **Collecting per order** answers part of the DS-41 question on cost collection (open question): the order is the cost object, and per-product or per-process views are reports (rule 16).
3. Area. Lines on accounts with control kind `cost_object` are in area `inventory` (ADR-0025 rule 4 is amended; ADR-0012 rule 4 gets a note), because they are inventory valuation. So:
   - pool and WIP postings into a period whose inventory area is locked are rejected like any stock posting;
   - any such posting after the costing job makes the job stale (ADR-0012 rule 12).

   Fixed assets and loans stay in `general`.

**During the period**

4. Shop-floor documents (ADR-0034) post at preliminary prices (ADR-0020 rule 11):

   | Movement type | Journal | Value |
   | --- | --- | --- |
   | `production_issue`, `disassembly_issue` | Debit `production_cost_material` (order), credit inventory | Preliminary price, revalued at period end |
   | `production_return` | Debit inventory, credit `production_cost_material` (order) | Like an issue with the opposite sign: the period's preliminary price, revalued to the period's actual. A return in a later period is valued in that period |
   | `production_receipt`, `co_product_receipt`, `disassembly_receipt` | Debit inventory, credit `inventory_work_in_process` (order) | Preliminary price, revalued at period end |
   | `by_product_receipt` | Debit inventory, credit `inventory_work_in_process` (order) | The regime's by-product value (rule 13), final |

   - **Confirmations post no journal.** Their activity quantities drive allocation.
   - **Preliminary price of a produced item.** ADR-0020 rule 11's fallback also reads receipts with costing role `production_output`. An item with no history takes the released cost estimate's unit cost. Without one, `preliminary_price_missing`.

**The period-end costing job**

5. The production part runs inside the period-end actual costing job (ADR-0020 rule 12; sequential, ADR-0012 rule 16), as one solve per period. That job is the settlement task of ADR-0034 rule 7.
   - **Documents.** The job writes one internal document per run, `production_cost_settlement`, with lines keyed by (cost object, cost component, step).
   - **Reruns** post only the differences per key (ADR-0012 rule 15).
   - **Simulation.** The job can be simulated like any command (ADR-0008 rule 9). Its plan lists the journal lines and the period cost records, and the document version follows ADR-0031 rule 1.

   Note: registry flags of `production_cost_settlement`: module `production`; posting; internal; no change orders; not e-invoice capable; `is_approval_hold_allowed: false`, because the job writes it as actor `system`; not reversible, because a rerun posts the differences (ADR-0012 rule 15); not item-creating; no demand or supply. Its authorization leaf `production_cost_settlement` sits under Finance beside `costing_adjustment`, and its commands are the job's (`full`, [ADR-0054](0054-users-roles-and-authorizations.md) rule 8) (holistic review 2026-11-15, item P27).
6. Unknowns and linearity:
   - **Unknowns.** One price per stock node (item, valuation area).
   - **Linear forms.** Pool values (constants plus indirect issues at those prices), allocations, order pools, WIP, outputs and abnormal cost are all linear forms in those prices. Allocation weights, units in process, completion shares and normal capacities are quantities or constants.
   - **Solving.** The system is solved per strongly connected component in topological order, in exact rationals (ADR-0025 rule 6). A singular component keeps the preliminary prices of its nodes (ADR-0020 rule 13).
7. Pools:
   - **Groups.** Each pool's period value is split by account into groups (`labor`, `overhead`, `other`). Each group is split into variable and fixed parts by the account's `cost_behavior` (rule 18).
   - **Allocation rule.** One rule per (cost center, group) says how the group is allocated:
     - by one activity type recorded on the cost center's work centers (actual quantities from confirmations); or
     - by a constant basis: output quantity, standard material quantity, or material at preliminary prices.

     The choice per cost center is company data (`pool_allocation_rule`).
   - **Variable part.** Allocated in proportion to the driver.
   - **Fixed part.**
     - It is allocated at fixed value ÷ max(actual driver quantity, normal capacity).
     - Normal capacity is set per (cost center, activity type or basis, period) in the driver's unit.
     - The unabsorbed rest goes to cost of goods sold (key `production_unabsorbed_overhead`).
     - Without a normal capacity, all of it is absorbed, with the close check result `normal_capacity_missing`.
   - **Idle pool.** A pool with no driver quantity in the period goes wholly to cost of goods sold, flagged.
   - **Unconfigured pool.** A pool group with cost but no `pool_allocation_rule` fails the job with `pool_allocation_rule_missing`.
   - **Material on a pool.** A line on `production_cost_material` whose cost object is a pool is rejected (`material_on_cost_pool`). Indirect materials go to `production_cost_overhead`.
   - **Postings.** Allocation lines debit the order and credit the pool on the source line's own account. Such mirror lines carry no transaction key (ADR-0015 rule 5). Pools end the period at zero.

   Note ([ADR-0071](0071-work-orders-and-shop-floor-execution.md), 2026-11-21): an allocation by activity type counts a confirmation at its `work_center_id`, the execution work center; time logs never enter the solve (ADR-0071 rules 11, 16).
8. Order pools. Per order and cost component (`material`, `labor`, `overhead`, `other`):
   - pool = opening WIP + the period's incurred cost;
   - incurred cost: material issued net of returns at actual prices, allocations, external service costs (`other`), and the ADR-0021 rule 7 consumer-split shares that land on the order's consumption.
9. WIP at period end, for orders that are not technically complete:
   - **Inputs.** R = main output received in the period. U = units in process.
   - **Units in process.** U = max(0, E − cumulative main output received).
     - **E.** The smallest, over non-fixed `manual` component lines, of net issued quantity × G ÷ required quantity. Backflushed lines follow progress, so they are left out.
     - **No qualifying line.** E = G.
     - **Status.** A constant, flagged.
   - **No receipt in the period.** Every component stays WIP.
   - **`direct_material`** (interim default): material WIP = material pool × U ÷ (R + U). Conversion goes wholly to the outputs.
   - **`equivalent_units`:** per component, WIP = pool × U·s ÷ (R + U·s). The share s is 1 for material and, for conversion, the share of routing hours confirmed, or the company's `wip_completion_percent` when set.
   - **`planned_cost`:** WIP = U × the released estimate's cost up to the last confirmed operation, a constant. If the solve gives the order's outputs a negative value, its WIP is capped at its pool and the system is solved again, at most once per order. The order gets the check result `planned_wip_capped` and its outputs are valued at zero, as a degenerate case of ADR-0020 rule 13.

   Note: E when no non-fixed `manual` line qualifies (holistic review 2026-11-15, item P17):
   - the order has operations and a `backflush_at_operation` component: E = cumulative (yield + scrap) of the order's first operation × G ÷ Q;
   - otherwise (every component `backflush_at_receipt`, no component, or no routing): E = cumulative main output received, so U = 0.

   This replaces "No qualifying line. E = G", which gave an order that had not started units in process. The lab [t13_production.py](../reviews/2026-11-14-design-validation/lab/t13_production.py) checks these cases. Whether this reading of units in process is right stays flagged for the author with the units-in-process definition (rule 18).

   Note: for a `disassembly` order, progress is the net input issued. E = the net issued quantity of the header item; D = the smallest, over output lines, of cumulative net received × G ÷ the line's planned quantity; U = max(0, E − D), and R is the period's increase of D (holistic review 2026-11-15, item P16).
10. Technically complete orders keep no WIP:
    - **Abnormal cost.** Assessed once, at completion, over the whole order. Per component line, the excess is the net issued quantity minus required × (cumulative received ÷ G) × (1 + tolerance), floored at 0. It is valued at the period's actual price and posted to cost of goods sold (key `production_abnormal_cost`). The same applies to activity quantities against standards. A reopen reverses it, and the next completion assesses it again.
    - **No output in the period.** A completed order whose pool is not zero but which received no output in the period sends that cost to cost of goods sold as a residual (key `production_residual_cost`), flagged. Examples: late allocations, consumer-split shares, late confirmations. A completed order with no good output at all does the same with its whole cost.
    - **A residual may be negative.** In particular, when completion falls in a period without receipts, an abnormal debit can be offset by a negative residual on the same order. Earlier outputs then keep the abnormal cost, and net cost of goods sold is unchanged. This limitation is flagged (rule 18).

    Note ([ADR-0071](0071-work-orders-and-shop-floor-execution.md), 2026-11-21): receipt scrap carries no value and does not change abnormal cost, which reads receipts; the scrap variance (`GetProductionOrderVariance`) counts it with confirmation scrap (ADR-0071 rule 4).
11. Outputs. The value to outputs is the sum of the component pools, minus WIP, minus abnormal cost, minus the by-product value.
    - **Co-products** share it by `cost_coefficient` × quantity (rule 13).
    - **A negative value** (for example a by-product worth more than the order's cost) sends the shortfall to cost of goods sold as a negative residual, and the outputs get zero, flagged. Like the planned-cost cap, it is applied by solving again, at most once per order (lab L-06).
    - **Rounding.** Outputs sum exactly to the value per order, by largest remainder. Node residuals follow ADR-0020 rule 13 (lab L-06).
12. Postings of the job, in this order:
    1. revaluation of issues and returns, against the order's or pool's leaf;
    2. pool allocations and unabsorbed fixed cost;
    3. abnormal and residual cost;
    4. transfer of each order's collected leaves to `inventory_work_in_process` (key `production_wip_transfer`), always, also under TT133 (rule 18);
    5. revaluation of receipts.

    The job writes `production_order_period_cost` per order, period and component, with opening, incurred, abnormal, to-output and closing amounts. After the postings each order's WIP balance must equal its closing amounts, otherwise the job fails with `production_cost_not_balanced`.

**By-products, co-products and disassembly**

13. Splits:
    - **By-product value.** `by_product_receipt` has value source `regime` (ADR-0020 rule 5). The Vietnam package seeds it, `unverified`, as the company's price list of kind `by_product` per item and period ([ADR-0045](0045-master-data-and-price-lists.md) rule 2), standing for net realisable value (VAS 02 para 09). A missing price rejects the receipt (`by_product_price_missing`).
    - **Co-products.** They share by coefficients; `relative_sales_value` from a price list is an option. Coefficients that sum to zero are rejected when the order is released (`co_product_weights_zero`). The list is the default sale list ([ADR-0045](0045-master-data-and-price-lists.md) rule 6).
    - **Disassembly.** Outputs share by the unit costs in their own released estimates, then by preliminary prices, then by quantity. Flagged.

**Cost estimates and variances**

14. `cost_estimate`:
    - **Header and lines.** It has a header (production version, costing date, `state` `draft` or `released`, price basis) and `cost_estimate_line` rows (cost component, component item or activity type, quantity, price, amount, level), rolled up level by level from the released estimates of made components.
    - **Price basis.** `actual_average` (the last closed period's actual price; interim default, flagged), `preliminary_price` or `purchase_price`. `purchase_price` is the preferred supplier's purchase-list price ([ADR-0045](0045-master-data-and-price-lists.md) rule 6).
    - **Rates.** `activity_rate` (work center, activity type, period, rate) holds planned rates. Overhead uses a planned surcharge per cost center.
    - **Commands.** `CreateCostEstimate` computes it on the server. `ReleaseCostEstimate` freezes it as the version's benchmark. Both are effect class `other`, because estimates never value stock.

    An estimate for a configured item names the item (`item_id`) with the product-level version, and is computed and released by the system when the item is created ([ADR-0046](0046-product-configuration.md) rules 11, 14).

    Note: `cost_estimate` gains `costing_lot_quantity`, the quantity the estimate is computed for: fixed quantities and setup are spread over it, and the versions of made components are selected for it. It lies in the version's lot range and defaults to the version's `minimum_lot_quantity`, or one inventory unit when that is zero. The estimate valid for a version on a date is the latest released one, by costing date and then release time, whose costing date is on or before that date; target cost (rule 15) and the order's `policy_input` use it. For the preliminary price of an item without history (rule 4), the version is the one [ADR-0033](0033-production-master-data.md) rule 13 selects on the posting date for the line's warehouse and quantity (for a production receipt, the order's own version), and its valid estimate gives the unit cost (holistic review 2026-11-15, item P18).

    Note (UoM simulation review, 2026-11-15): under price basis `preliminary_price`, a purchased component that has no receipt yet is priced at the preliminary price of [ADR-0020](0020-inventory-and-costing-model.md) rule 11 and its note: the supplier purchase list price (`find_price` in the inventory unit), else the last purchase invoice price, else a manual preliminary price; without any, the estimate cannot price the component and returns `preliminary_price_missing` naming it. Made components keep their chain: the estimate rolls up their released estimates (above), and their preliminary price stays rule 4's (receipts with costing role `production_output`, else the released estimate's unit cost, else `preliminary_price_missing`).

    Note ([ADR-0062](0062-product-engineering-workflow.md), 2026-11-15): `CreateCostEstimate` is also registered `is_draft_only` and computes on draft revisions: a draft estimate may have no production version. What it cannot price (a missing purchase price, activity rate or activity quantity, a pending item, an unstated setup or run time, a missing routing) is a `cost_estimate_gap` row, left out of the total and never zero; an estimate with a gap or without a version is never released (`cost_estimate_incomplete`). `previous_cost_estimate_id` names the estimate a delta compares with ([ADR-0062](0062-product-engineering-workflow.md) rule 12).

    Note ([ADR-0072](0072-costing-sheet-and-cost-component-structure.md), 2026-11-21): overhead in an estimate comes from the costing sheet of the production version, else of its site (rules 6–9). It replaces the interim `overhead_surcharge` and "a planned surcharge per cost center" (rule 11). `cost_estimate_line` gains `cost_component_detail_id`, and on surcharge lines only `costing_sheet_row_number` and `credited_cost_center_id`, the settled `cost_center_id`; `cost_estimate_sheet_row` keeps the sheet as costed. A missing rate is the gap `costing_rate_missing`, never zero. Administration and selling rows never enter an estimate (rule 10).

    Note (S2 open questions, 2026-11-21): `ReleaseCostEstimate` is registered with effect class `master_data_change`, so it is proposal-bound for agents; `CreateCostEstimate` stays `other`. A released estimate feeds the preliminary price, so an agent release would reach valuation.
15. Variance analysis:
    - **Target cost.** The released estimate valid on the order's explosion date, scaled to the received quantity.
    - **Query.** `GetProductionOrderVariance` splits actual minus target into input price, input quantity, resource usage, scrap, lot size and remaining.
    - **Postings.** None: output already carries actual cost.
    - **Agent.** The variance agent (DS-34) ranks orders by variance and links them to documents.

    The variance agent is a later agent ([ADR-0051](0051-agent-workflows.md) rule 29).

    Note ([ADR-0060](0060-agent-assisted-reporting-and-analysis.md), 2026-11-15): the split is also written per order, period and variance category, with the order's output item, warehouse and branch, to `production`'s read model `production_order_variance` when the costing run settles the order's period cost; its DDL comes with the costing tables of DS-53 (a note in DS-43-54-planning-production.sql). The analysis fact `production_variance_overview` reads those rows only, so the variance agent and the analysis layer read one figure (rule 19).

    Note ([ADR-0064](0064-production-agent.md), 2026-11-15): the variance agent is `production_variance` on the analysis layer; `GetProductionOrderUsageVariance` gives in-period quantity variances before settlement and `ListProductionOrderVarianceDriver` the document lines per category and cost component, which sum to `production_order_variance` (rules 9–11, 20).

    Note ([ADR-0072](0072-costing-sheet-and-cost-component-structure.md), 2026-11-21): the order cost report and `GetProductionOrderVariance` may group by detailed cost component, read from `production_order_period_cost_detail`, a read model the job writes beside `production_order_period_cost` without changing its key, INV-106 or the settlement keys (rules 4, 5). Receipts keep the item's preliminary price (rule 4 of this ADR); `GetProductionReceiptValuation` shows planned against preliminary value per receipt, and `GetProductionOrderProjectedCost` a provisional projected final cost at completion (ADR-0072 rules 13, 14).

**Vietnamese costing methods**

16. The methods are views over the one model, so a choice per product group changes reports and settings, not the core:
    - **Giản đơn and đơn đặt hàng:** per order.
    - **Hệ số:** coefficients.
    - **Tỷ lệ:** a report of actual against planned cost per product group.
    - **Phân bước có tính giá bán thành phẩm:** multi-level orders.
    - **Phân bước không tính giá bán thành phẩm:** phantoms inside one order.
    - **Định mức:** estimates with variances, and standard cost valuation if the author chooses it.

    DS-26 builds the reports, including the product cost sheet (thẻ tính giá thành), from `production_order_period_cost`.

    Note: the Vietnamese method names and the product cost sheet are `l10n_vn`'s content, owned by ADR-0039; the core keeps the views ([ADR-0053](0053-core-neutrality.md) rule 13).

    Note: the core provides the row source `production_order_period_cost` for books; `l10n_vn`'s cost sheet is a book definition over it, with field class `cost` ([ADR-0049](0049-statutory-reporting-and-printing.md) rules 10, 22).

    Note (the author, 2026-11-21: costing follows SAP): the choice the standard method leaves open is answered. Standard cost valuation becomes, as in SAP, a price-control option with variance postings beside periodic actual costing (the default, D6); overhead is applied by costing sheet with the over- or under-absorption left as a variance; the released cost estimate (rule 14) gives the standard price. The design comes by an ADR after step 5, on the seam of [ADR-0072](0072-costing-sheet-and-cost-component-structure.md) rule 21. Price control is a product field today ([ADR-0018](0018-product-and-item-model.md) rules 3 and 18); the granularity (the product, or material and valuation area as in SAP) and the change rule are decided by that ADR, which amends ADR-0018 rules 3 and 18 if needed; it is the undecided price-control point of the SAP comparison entry ([open-questions.md](../open-questions.md), DS-53 entries and S2 closure). The phase is stated by that ADR: after step 5 and after Phase 1 unless the author moves it, since ADR-0018 rule 3 and spec 09 keep standard price out of Phase 1; until then those hold.

**Data, catalogs and checks**

17. Tables and commands. All maintenance commands are `master_data_change`, because they change valuation:
    - `pool_allocation_rule` (cost center, group, driver);
    - `normal_capacity` (cost center, driver, period, quantity);
    - `activity_rate`;
    - `by_product_price`, which is the company's price list of kind `by_product` ([ADR-0045](0045-master-data-and-price-lists.md) rule 2);
    - `production_order_period_cost`, written only by the job.

    Note ([ADR-0072](0072-costing-sheet-and-cost-component-structure.md), 2026-11-21): the costing sheets with their rates and site assignments, and the detailed cost components with their mappings, are `master_data_change` too, for the same reason: a released estimate reaches valuation through rules 4, 9 and 13. Their commands and `activity_rate`'s use the leaf `costing_structure` (ADR-0072 rule 17).
18. Settings. These are seeded `unverified` and flagged (ADR-0016 rule 12), and the regime makes them binding, as questions to the author:
    - `wip_method`;
    - `wip_completion_percent`;
    - the pool allocation rules;
    - the abnormal-cost tolerance and whether abnormal cost applies at all (VAS 02 para 11);
    - whether the normal-capacity rule applies (VAS 02 para 08);
    - unabsorbed, abnormal and residual cost going to cost of goods sold;
    - abnormal cost valued at period actual;
    - the units-in-process definition;
    - a negative residual offsetting abnormal cost when completion has no receipt;
    - received stock valued at zero when planned WIP is capped;
    - the co-product, by-product and disassembly splits;
    - the estimate price basis;
    - the singular fallback;
    - `cost_behavior` of overhead accounts;
    - subledger activation before the first release (ADR-0034 rule 15).

    TT99 keys and the `cost_behavior` seeds: [ADR-0039](0039-vietnam-package-tt99.md) rules 6, 9.

    **Account mapping.** TT99 maps the leaves to 621, 622 and 627 and WIP to 154. TT133 maps them to sub-accounts of 154 per cost element plus one for WIP, because an operational account maps to one system account (ADR-0010 rule 11). The mapping is DS-19's and the author's (the DS-41 question).

    Note: the neutral references are IAS 2 paragraph 16 (abnormal amounts) and paragraph 13 (normal capacity); VAS 02 paragraphs 11 and 08 are `l10n_vn`'s rationale ([ADR-0053](0053-core-neutrality.md) rule 6).

    Note: setting keys, with the interim value a regime package seeds until it has a basis (holistic review 2026-11-15, item P19): `production.wip_method` (`direct_material`), `production.abnormal_cost.applies` (true), `production.abnormal_cost.tolerance_percent` (0), `production.normal_capacity.applies` (true), `production.co_product_split` (`cost_coefficient`), `production.estimate_price_basis` (`actual_average`). TT99 seeds exactly these ([ADR-0039](0039-vietnam-package-tt99.md) rule 9). `wip_completion_percent` and the pool allocation rules are company data. The other points of this list are fixed core behavior, flagged: unabsorbed, abnormal and residual cost to cost of goods sold; abnormal cost at period actual; the units-in-process definition (rule 9 and its notes); the negative residual offset; zero value under a capped planned WIP; the by-product value source `regime` (rule 13); the disassembly split; the singular fallback; `cost_behavior` as account data; subledger activation before the first release.
19. Catalog changes, version 0.x:
    - **Movement types:**

      | Code | Direction | Value source | Costing role | Offset key |
      | --- | --- | --- | --- | --- |
      | `production_issue` | out | `preliminary_price` | `production_input` | `production_consumption` |
      | `production_return` | in | `preliminary_price` | `production_input` | `production_consumption` |
      | `production_receipt` | in | `preliminary_price` | `production_output` | `production_output` |
      | `co_product_receipt` | in | `preliminary_price` | `production_output` | `production_output` |
      | `by_product_receipt` | in | `regime` | `production_output` | `production_output` |
      | `disassembly_issue` | out | `preliminary_price` | `production_input` | `production_consumption` |
      | `disassembly_receipt` | in | `preliminary_price` | `production_output` | `production_output` |

      ADR-0020 rule 4 gains the costing roles `production_input` (into a cost-object node, revalued; a return counts negative) and `production_output` (from one, revalued unless its value is final).
    - **Transaction keys**, the count becoming 44 ([ADR-0037](0037-subcontracting.md) adds two more, 46 in total):

      | Key | Accounts | Determinants |
      | --- | --- | --- |
      | `production_consumption` | `production_cost_material` | none |
      | `production_output` | `inventory_work_in_process` | valuation class of the order's main output |
      | `production_wip_transfer` | `inventory_work_in_process` | valuation class of the order's main output |
      | `production_abnormal_cost` | `cost_of_goods_sold` | none |
      | `production_unabsorbed_overhead` | `cost_of_goods_sold` | none |
      | `production_residual_cost` | `cost_of_goods_sold` | none |

      The leaf side of the transfer, the abnormal cost and allocations copy the source line's account.

      `consumption` also lists `production_cost_overhead`, for internal consumption to a factory cost center.

    Note: `production_abnormal_cost` and `production_unabsorbed_overhead` list `cost_of_goods_sold;expense_other` as regime alternatives; TT99 keeps 6325 under 632 ([ADR-0053](0053-core-neutrality.md) rule 6).

    Note: for a `disassembly` order the determinant of `production_output` and `production_wip_transfer` is the valuation class of the header item, the input being taken apart, because its outputs are co-product lines (holistic review 2026-11-15, item P16).
20. Catalog rows reserved in the production range (ADR-0033 rule 16):
    - **INV-106:** after the job, each order's `inventory_work_in_process` balance equals the closing amounts of its latest `production_order_period_cost`, and a technically complete order's is zero.
    - **INV-107:** after the job, each `cost_pool` cost object's balance on the production leaves is zero for the period.
    - **INV-108:** the naive recomputation (DS-16 rule 29), extended with cost-object nodes, reproduces every production receipt's value.
    - **Edge cases:**
      - an order open across a period end under each WIP method;
      - an idle pool;
      - fixed overhead below normal capacity;
      - abnormal consumption at completion;
      - a late cost on a completed order;
      - a capped planned WIP;
      - a by-product worth more than the order;
      - a rework cycle;
      - a singular component.

## Context

The author asked for production costing by best practice, learning from SAP without copying it.
- **What SAP does.** It values at standard during the period, then collects differences and settles them.
- **What NativeFlows does.** It reaches actual cost directly, because its solver values the whole graph exactly.

The design meets the Vietnamese rules the research found:
- TT99's provisional price with a period-end true-up;
- normal capacity;
- abnormal costs outside product cost;
- by-products deducted;
- the common WIP methods.

It also answers Odoo's gaps. The first review found that allocation by solved values breaks linearity, that cross-period WIP and late costs had no rule, and that the first lab overstated its coverage. This version restricts the bases, records WIP by component, and was validated by a second, fuller lab.

## Options considered

| Option | For | Against |
| --- | --- | --- |
| Periodic actual through the exact solve, estimates as benchmark (chosen) | Actual cost per TT99 and VAS 02; validated | Values final only at period end |
| Standard cost valuation with variance postings | Stable unit costs | Settlement and price-difference accounts; the author's choice |
| Allocation by solved material cost | Common in practice | Nonlinear; replaced by material at preliminary prices |
| Abnormal cost per period | Earlier recognition | Ill-defined when issues and output fall in different periods |
| Cost-object lines in area `general` | ADR-0025's original choice | Late pool postings would not make the costing stale |

## Constraints that come with the decision

- **ADR notes:**
  - ADR-0010 (`cost_behavior`);
  - ADR-0012 rules 4, 13 (area of cost-object lines; the job settles production);
  - ADR-0015 (key count 44);
  - ADR-0020 rules 4, 5, 11, 12 (roles, by-product value source, preliminary price, nodes);
  - ADR-0021 rule 7 (production consumers);
  - ADR-0025 rules 2, 4, 6 (kinds, area, nodes);
  - ADR-0034 rule 7 (settlement task).
- **DS-06:** `cost_object` columns, area mapping and activation checks (lab L-03, L-07).
- **Catalogs:** seven movement types, six keys, and the widened `consumption` key.
- **DS-04:** errors `production_cost_not_balanced`, `by_product_price_missing`, `co_product_weights_zero`, `pool_allocation_rule_missing`, `material_on_cost_pool`; check results `normal_capacity_missing`, `planned_wip_capped`.
- **DS-16:** the naive recomputation with cost-object nodes; INV-106 to INV-108.
- **Glossary:** cost pool, pool allocation rule, WIP method, units in process, normal capacity, abnormal cost, residual cost, cost estimate, target cost, variance, cost behavior, production order period cost.
- **Other design items:** DS-19 (mapping and seeds), DS-26 (reports), DS-34 (variance and close agents).
- **Open questions:** every setting of rule 18; secondary allocation between cost centers (later); standard cost valuation; the DS-41 question.

## Revisit when

- The author chooses standard cost valuation, or a method rule 16 cannot show.
- A company needs secondary allocation in Phase 1.

## Documents updated

- **ADRs:** [docs/adr/0010-system-chart-of-accounts.md](0010-system-chart-of-accounts.md), [docs/adr/0012-posting-periods-and-closing.md](0012-posting-periods-and-closing.md), [docs/adr/0015-account-determination.md](0015-account-determination.md), [docs/adr/0020-inventory-and-costing-model.md](0020-inventory-and-costing-model.md), [docs/adr/0021-landed-cost.md](0021-landed-cost.md), [docs/adr/0025-later-phase-seams.md](0025-later-phase-seams.md), [docs/adr/0034-production-orders-and-shop-floor.md](0034-production-orders-and-shop-floor.md): notes.
- **SQL and catalogs:** [docs/design/DS-06-universal-journal.sql](../design/DS-06-universal-journal.sql), [docs/catalogs/movement-types.csv](../catalogs/movement-types.csv), [docs/catalogs/transaction-keys.csv](../catalogs/transaction-keys.csv).
- **Design:** [docs/design/DS-04-command-envelope.md](../design/DS-04-command-envelope.md), [docs/design/DS-16-invariants-and-harness.md](../design/DS-16-invariants-and-harness.md), [docs/design/backlog.md](../design/backlog.md).
- **Validation:** [docs/reviews/2026-11-14-design-validation/README.md](../reviews/2026-11-14-design-validation/README.md).
- **Glossary:** [docs/spec/00-reading-guide.md](../spec/00-reading-guide.md).
- **Open questions:** [docs/open-questions.md](../open-questions.md).
- **Index and log:** [docs/adr/README.md](README.md); [docs/runbook/step-log.md](../runbook/step-log.md) at acceptance.
