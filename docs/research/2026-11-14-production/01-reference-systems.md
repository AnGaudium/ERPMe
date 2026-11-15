# Production in reference systems

Research note for DS-51 to DS-55 ([ADR-0032](../../adr/0032-phase-1-scope-with-production.md)), written by a research agent on 2026-11-14. It is design input, not a decision. Other ERPs are references for concepts only (ADR-0032 rule 2).

**Status tags.** Claims marked [background] come from the agent's general knowledge and were not checked against a source during the research. Claims marked [unsure] are uncertain. SAP help pages are often from older releases; the concepts carry over to S/4HANA.

## SAP S/4HANA: production planning and product costing

**Master data**
- **Bills of materials.** Each has a usage (production, engineering, costing) and alternatives per material, plant and usage [background].
  - **Phantom assemblies** are exploded into the parent's order (special procurement key 50) ([SAP Help](https://help.sap.com/saphelp_46c/helpdata/en/f4/7d2b5f44af11d182b40000e829fbfe/content.htm)).
  - **Co-products** are negative items with a co-product flag, split by equivalence numbers [background].
  - **By-products** are negative items credited at a fixed price [background].
  - Phantoms combined with co-products cause recursion problems in practice, which argues for a simple model.
- **Routings and work centers.**
  - A routing is a list of operations at work centers. Each operation carries standard values (setup, machine, labor) and a control key (internal, external, milestone).
  - Activity types × cost-center rates give the operation cost [background].
  - Process industries use a master recipe and resources.
- **Production versions.**
  - A production version is mandatory in S/4HANA: MRP and order creation find a BOM and routing only through a valid version ([SAP blog](https://blogs.sap.com/2019/12/09/sap-s-4hana-simplified-sourcing-approach/)).
  - One explicit "way to make" object, made of a BOM alternative, a routing, a validity and a lot-size range, makes the choice visible. That suits agents.

**Order types**
- **Production orders:** discrete.
- **Process orders:** recipes and phases. Functionally close to production orders.
- **Repetitive manufacturing:**
  - no orders: planned orders plus backflush to a product cost collector per production version;
  - period-based costing, with WIP at target and periodic settlement ([SAP Learning](https://learning.sap.com/courses/cost-object-controlling-in-sap-s-4hana/using-a-product-cost-collector));
  - a period cost collector is a cost object that lives across periods.

**Order lifecycle**
- Statuses run created → released → partially or finally confirmed → partially or fully delivered → technically complete → closed.
- Technically complete ends logistics: reservations and capacity are removed, and MRP ignores the order. Cost postings stay allowed, so variances and settlement can run.
- Closed blocks all postings.
- Practitioners report that "technically complete" is often misused ([SAP Community](https://community.sap.com/t5/enterprise-resource-planning-blog-posts-by-members/do-you-whitewash-your-production-orders/ba-p/13491754)). Each status must say exactly which postings it allows.

**Execution** [background]
- Goods issue against the order reservation; backflush when the operation is confirmed.
- Operation confirmations carry yield, scrap, rework, activities and dates.
- Goods receipt, optionally automatic on the last confirmation, within tolerances.
- Planned scrap at assembly, component and operation level. Actual scrap is confirmed per operation.

**Order costing**
- **Planned cost** comes from the BOM, the routing and a costing sheet for overhead.
- **Actual cost** comes from:
  - issues;
  - activities at plan or actual rate;
  - period-end overhead surcharges;
  - external processing.
- **Goods receipt** credits the order at standard price.
- **Target cost** is planned cost scaled to the delivered quantity ([SAP Help](https://help.sap.com/saphelp_46c/helpdata/en/5d/ac94de8d49d111a4620060b03c3b0e/content.htm)).
- **WIP**:
  - an order released but not delivered carries its net balance as WIP at actual;
  - a period collector carries WIP at target;
  - at delivery or technical completion, WIP is cancelled and the rest becomes a variance.
- **Variance categories.**
  - Input side: price, quantity, resource-usage, scrap, remaining.
  - Output side: output price, mixed price, lot size, remaining ([SAP Learning](https://learning.sap.com/courses/cost-object-controlling-in-sap-s-4hana/performing-variance-calculation)).
- **Settlement** moves WIP to the balance sheet and variances to price-difference accounts or profitability analysis.
- **Event-based production accounting** posts overhead and WIP at each event and variances at the final receipt ([SAP blog](https://blogs.sap.com/2021/03/29/new-in-production-accounting-event-based-production-cost-posting/)).

**Material ledger**
- The material ledger is mandatory; actual costing in it is optional.
- During the period, goods move at standard price and differences are collected.
- At period end, single-level and then multilevel price determination roll the differences up the actual quantity structure ([SAP Help](https://help.sap.com/saphelp_46c/helpdata/en/0b/ca29f87cc411d38aa60000e83234f3/content.htm)).
- Cycles are handled iteratively [background].
- ERPMe's exact solver over the whole graph (ADR-0025 rule 6) reaches actual cost without standard price, differences and iteration.

## Odoo 17/18 MRP

- **Bills of materials** come in three types: manufacture, kit (a phantom, never stocked) and subcontracting. They support operations, by-products with a fixed "cost share %", variants per attribute, and unbuild orders ([Odoo 18](https://www.odoo.com/documentation/18.0/applications/inventory_and_mrp/manufacturing/subcontracting/subcontracting_basic.html)).
- **Work centers** carry hourly machine and employee costs, capacity, efficiency, setup and cleanup times, and alternatives. Work orders are scheduled forward on calendars ([Odoo 18](https://www.odoo.com/documentation/18.0/applications/inventory_and_mrp/manufacturing/advanced_configuration/using_work_centers.html)).
- **Planning.**
  - Reordering rules and make-to-order routes create draft manufacturing or purchase orders.
  - A manual master production schedule (MPS) exists, which Odoo advises not to mix with reordering rules ([Odoo](https://www.odoo.com/documentation/17.0/applications/inventory_and_mrp/inventory/warehouses_storage/replenishment.html)).
  - There is no classic multi-level MRP run with low-level codes [background].
- **Subcontracting** works through a subcontracting BOM. The receipt creates a subcontract manufacturing order that consumes components at the subcontractor's location; the components can be resupplied on order or dropshipped ([Odoo 17](https://www.odoo.com/documentation/17.0/applications/inventory_and_mrp/manufacturing/subcontracting/subcontracting_resupply.html)).
- **Costing.**
  - Estimated cost comes from the BOM; real cost from consumption and durations ([Odoo 18](https://www.odoo.com/documentation/18.0/applications/inventory_and_mrp/manufacturing/basic_setup/mo_costs.html)).
  - Valuation methods are standard, perpetual average (AVCO) or FIFO.
- **Weaknesses for manufacturers:**
  1. No periodic actual costing. Late bills do not reach finished goods already made or sold, and differences do not roll up through levels.
  2. No WIP at period end in versions 17 and 18, beyond manual accruals. A manual snapshot appears only in the saas-19.2 docs ([Odoo](https://www.odoo.com/documentation/saas-19.2/applications/inventory_and_mrp/manufacturing/basic_setup/work_in_progress.html)).
  3. Overhead is absorbed only through work-center hourly rates. There is no cost-center actual rate and no true-up.
  4. No target costs, no variance categories and no settlement.
  5. No firm horizon or action-message discipline in MRP.

## Microsoft Dynamics 365 SCM

- **Order types.**
  - Production orders cover discrete production (BOM and route).
  - Batch orders use formulas with co-products and by-products. Co-product cost can be allocated by total cost allocation ([MS Learn](https://learn.microsoft.com/en-us/dynamics365/supply-chain/cost-management/methodology-total-cost-allocation)).
  - Kanbans cover lean production.
- **Lifecycle.**
  - Statuses run created → estimated → scheduled → released → started → reported as finished → ended.
  - Each step can be reversed one at a time ([MS Learn](https://learn.microsoft.com/en-us/dynamics365/supply-chain/production-control/reverse-production-order-status)).
- **Flushing principle per BOM line:** manual, start, finish, or available at location ([MS Learn](https://learn.microsoft.com/en-us/dynamics365/supply-chain/production-control/flushing-principles)).
- **WIP.**
  - Estimated postings go to WIP accounts when the picking list, the route card and the report as finished are posted.
  - Ending the order reverses the estimates, posts actual cost and blocks further cost postings ([MS Learn](https://learn.microsoft.com/en-us/dynamics365/finance/general-ledger/production-posting)).
  - Estimates first, then a true-up as new entries, fits an append-only journal.

## Multi-level MRP

Textbook mechanics (APICS; [IFS](https://docs.ifs.com/ifsclouddocs/25r1/Planning/AboutMrp.htm), [Oracle JDE](https://docs.oracle.com/en/applications/jd-edwards/supply-chain-manufacturing/9.2/eoarp/understanding-material-requirements-planning.html)):
- **Low-level codes.**
  - An item's low-level code is the deepest level at which it appears. Recompute it on every structure change and reject cycles there.
  - Items are planned in low-level-code order, so that all dependent demand is known before netting.
- **Gross to net.** Gross requirements (independent and dependent demand, reservations) minus on-hand and scheduled receipts, plus safety stock, per bucket.
  - Reorder point, min/max and forecast become planning policies on one engine.
- **Lot sizing:** lot for lot; fixed; minimum, maximum and rounding; days of supply.
- **Lead-time offsetting.** Purchased items: delivery time plus receipt processing. Made items: fixed days, or computed from the routing. Scrap factors apply.
- **Pegging.** Store single-level pegging each run and derive full pegging by traversal.
- **Stability.** Firm horizons and firm orders. Action messages (new, reschedule in or out, increase, decrease, cancel, expedite) are the planner's and the agent's interface.
- **Run mode.** Regenerative is fast enough for an SME; net change can come later [background].
- **Capacity minimum for a mid-size manufacturer** ([CPIM study guide](https://open-exam-prep.com/study-guides/cpim/mrp-capacity/crp-order-promising-fas)):
  - an infinite load view per work center from routings;
  - simple finite forward scheduling on calendars;
  - optionally, rough-cut capacity derived from routings;
  - no advanced planning and scheduling (APS) in the first version.

## Subcontracting

- **SAP.** A subcontracting order item carries a component BOM. Components move to vendor special stock, the receipt consumes them, and later adjustments are possible. Alternatively, an external operation in a routing.
- **Odoo.** As above.
- **D365.** A service item on a route operation with a vendor resource, or a vendor BOM line ([MS Learn](https://learn.microsoft.com/en-us/dynamics365/supply-chain/production-control/subcontracting)).
- **Vietnam.** Many SMEs process customer-owned materials (gia công), often for export. They need:
  - quantity-only non-owned stock;
  - consumption norms;
  - customs finalization reports.

  One owner dimension on stock serves both directions: our stock at a processor, and a customer's stock with us.

## What agent-first design adds

- **Vendors.** SAP announced production agents in 2025–2026 ([SAP](https://www.sap.com/products/erp/production-planning-and-operations-agent.html)). These agents sit on systems built for screens.
- **Agent roles in ERPMe.** Each role only proposes; deterministic engines compute every number:
  1. **Planning agent:** groups action messages, explains each one through pegging, and proposes conversions.
  2. **Master-data agent:** drafts BOMs and routings from spreadsheets or drawings, and checks cycles, units, missing rates and validity.
  3. **Shop-floor capture agent:** turns chat messages, photos or voice notes into draft confirmations, issues and scrap, checked against tolerances.
  4. **Variance agent:** splits and ranks variances at close and links them to documents.
  5. **Close agent:** finds unconfirmed operations, orders to complete and WIP anomalies before the costing solve.
  6. **Subcontract reconciliation agent:** builds the material balance per processor and drafts statements and customs reports.

## Design decisions proposed by the research

1. **Order model.** One production order model with operations and several inputs and outputs, covering discrete and batch work. A formula flavor (batch size, co-products) is a master-data option. Period cost collectors are a second cost-object type on the same solver nodes.
2. **Production version.** An explicit production version (BOM alternative, routing, validity, lot-size range), mandatory for made items.
3. **Lifecycle.** Planned → released → in progress → technically complete → closed, with the postings each status allows stated precisely.
4. **Consumption.** Set per BOM line: manual, backflush at operation confirmation, or backflush at receipt. An automatic receipt on the last confirmation is optional.
5. **Costing.**
   - Periodic actual cost through the exact solve is authoritative.
   - A planned cost estimate per production version serves quotes, target costs and variances.
   - Receipts post at a provisional price and are revalued at close.
6. **WIP.** WIP at actual by default; equivalent units as an option. Both keep the solve linear.
7. **Variances.** Target costs and variance categories serve as analysis.
8. **Overhead.** Planned rates per work center or cost pool; the actual rate is solved at period end in the same linear system.
9. **Joint outputs.** Co-products are split by equivalence coefficients; by-products are credited at a fixed price; scrap is absorbed by default.
10. **MRP.** A regenerative multi-level run with low-level codes and a per-item planning policy, lot sizes, single-level pegging, firm horizons and action messages.
11. **Capacity.** An infinite load view plus simple finite forward scheduling.
12. **Subcontracting.** An owner dimension on stock; a production order with an external operation, a service purchase order, consumption on receipt and adjustments; quantity-only stock received for processing, with norms.
13. **Chart mapping.** The cost component (material, labor, overhead, external) is a journal dimension, mapped to TT99 (621/622/627 → 154) or TT133 (154).
14. **Agent boundary.** Agents draft; the engines compute; policies approve; posted data is never edited.
