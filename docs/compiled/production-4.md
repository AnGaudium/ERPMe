Module: production    Chunk: 4 of 7    Source ADRs: ADR-0035, ADR-0036, ADR-0037, ADR-0045, ADR-0046
Build step(s): 4b, 5    Generated from index: 30d5706    Compiled by: Claude Opus 5.5, 2026-11-21

# Compiled spec: `production`, chunk 4

## Purpose

`production` owns production structures, production orders, shop-floor execution and production costing (ADR-0022.R2).
This chunk states the end of production costing (variance analysis, the methods as views, the costing tables, the costing
settings and fixed behavior, the catalog changes and reserved rows), the production side of multi-level planning
(`production.contract.plan_production` and conversion of planned orders), subcontracting (external operations, buying
the service, `service_receipt`, the owner seams), the production uses of prices, and product configuration on
production structures. Planning's graph and run, the `l10n_vn` package, policy points and configuration models are
other modules' law; their units are traced `ref:` and not restated.

## Entities and tables

DDL: `docs/design/DS-43-54-planning-production.sql`.

No table row belongs to this chunk: `normal_capacity` and `pool_allocation_rule` (R611) have their rows in chunk 3.

Defined by rule, without DDL: `production_order_variance`, the read model of the variance split per order, period and variance category (R604; ADR-0060.R19); the DDL file says its DDL comes with the costing tables of DS-53.

The rules of this chunk also use tables whose rows stand in other chunks: `activity_rate` and `production_order_period_cost`
(R611, R613), `production_order_period_cost_detail` (R602), `operation_progress_component` (R651, `INV-112`),
`production_order_operation` (`supplier_partner_id`, R637), `production_order_component` and `production_order_output`
(`owner_partner_id`, R657), `production_order` (`origin_planned_order_id`, R633), `production_version`,
`bill_of_materials`, `bill_of_materials_component` and `routing_operation` (configuration columns, R677 to R680),
`item_low_level_code` (R682), `cost_object` (R663).

Reads: `price_list` and `price_list_entry` (ADR-0045.R2), `supplier_item`, `transfer_route`, `item_warehouse_planning`,
`planned_order`, `planned_order_component`, `demand_supply_line`, `configuration_model`, `configuration_model_revision`,
`product_configuration`, `variant_attribute`, `product_variant_attribute`, `production_structure`, `goods_receipt`,
`service_receipt` (`purchasing`), `stock`.

## Commands and queries

| Name | Actor and authorization | Input | Effect | Events | Error codes |
| --- | --- | --- | --- | --- | --- |
| `GetProductionOrderVariance` (query) | Not stated; the catalog leaf `report_production` (module `query`) covers production and variance reports | A production order | Splits actual minus target cost into variance categories, optionally by detailed cost component (R601, R602) | None | Not stated |
| `ConvertPlannedOrder` (production planned order) | Area `planning` (planned orders); verb level not stated | A production planned order | Writes a draft production order through `production.contract.create_production_order_from_plan`, in one transaction (R633 to R635) | Not stated | Not stated |

Not commands: the pure function `production.contract.plan_production` (R626 to R632); the interfaces
`production.contract.create_production_order_from_plan` (R633), `production.contract.record_operation_progress` (R651)
and `production.contract.estimate_configuration` (R670). Posting a `service_receipt` is a command of `purchasing`'s
document type, whose authorization leaf sits under `purchasing` (R647). The queries `GetProductionOrderUsageVariance`,
`ListProductionOrderVarianceDriver`, `GetProductionReceiptValuation` and `GetProductionOrderProjectedCost` are stated
in the chunks of ADR-0064 and ADR-0072 (R605, R606).

Codes raised by the rules of this chunk: `production_version_missing` (R627); `planning_parameter_missing` with reasons
`processor_location_missing` and `processor_route_missing` (R638, R640, R641); `processor_location_missing` rejects
`CreateProductionOrder`, its updates and change orders (R640); `negative_stock` rejects a service receipt (R652);
`purchase_price_missing` is a check result (R668); `configuration_incomplete`, `configuration_warehouse_not_produced`,
`configuration_invalid` and `configuration_in_production` (R672 to R676); `configured_quantity_negative`,
`routing_conditions_shared`, `configuration_characteristic_not_item_defining` and `revision_in_use` (R678 to R681).

## Rules

### Variance analysis

R601. The target cost of an order is the released estimate valid on the order's explosion date, scaled to the received quantity.
Source: ADR-0035.R15

R602. `GetProductionOrderVariance` splits actual minus target into input price, input quantity, resource usage, scrap, lot size and remaining. It and the order cost report may group by detailed cost component, read from `production_order_period_cost_detail`, a read model the costing job writes beside `production_order_period_cost` without changing its key, `INV-106` or the settlement keys (ADR-0072.R4, ADR-0072.R5).
Source: ADR-0035.R15, ADR-0035.R15.N3

R603. Variance analysis posts nothing: output already carries actual cost.
Source: ADR-0035.R15

R604. When the costing run settles an order's period cost, the variance split is written per order, period and variance category, with the order's output item, warehouse and branch, to `production`'s read model `production_order_variance`. The analysis fact `production_variance_overview` reads only those rows, so the variance agent and the analysis layer read one figure (ADR-0060.R19).
Source: ADR-0035.R15.N1

R605. The variance agent is `production_variance` on the analysis layer (DS-34; ADR-0051.R29), a Phase 2 agent type registered with mode `off` (ADR-0078.R2). It ranks orders by variance and links them to documents. `GetProductionOrderUsageVariance` gives in-period quantity variances before settlement, and `ListProductionOrderVarianceDriver` the document lines per category and cost component, which sum to `production_order_variance` (ADR-0064.R9, ADR-0064.R10, ADR-0064.R11, ADR-0064.R20).
Source: ADR-0035.R15, ADR-0035.R15.N2

R606. Receipts keep the item's preliminary price (ADR-0035.R4). `GetProductionReceiptValuation` shows planned against preliminary value per receipt, and `GetProductionOrderProjectedCost` a provisional projected final cost at completion (ADR-0072.R13, ADR-0072.R14).
Source: ADR-0035.R15.N3

### Costing methods as views

R607. Costing methods are views over the one model, so a choice per product group changes reports and settings, not the core. The views are:
   - per order;
   - coefficients;
   - a report of actual against planned cost per product group;
   - multi-level orders, for a step method that costs the semi-finished output;
   - phantoms inside one order, for a step method that does not cost it;
   - estimates with variances, for a standard method.
   The method names of a country and its product cost sheet are `l10n_vn`'s content, owned by ADR-0039; the core keeps the views (ADR-0053.R13).
   Source: ADR-0035.R16, ADR-0035.R16.N1

R608. The core provides the row source `production_order_period_cost` for books. DS-26 builds the costing reports from it. `l10n_vn`'s product cost sheet is a book definition over it, with field class `cost` (ADR-0049.R10, ADR-0049.R22).
Source: ADR-0035.R16, ADR-0035.R16.N2

R609. Standard cost valuation is a price-control option beside periodic actual costing, which stays the default (D6). A later ADR decides between standard price with variance postings and no actual costing, and standard price with actual costing. Overhead is applied by costing sheet, with over- or under-absorption left as a variance, and the released cost estimate (ADR-0035.R14) gives the standard price. That ADR comes after step 5, on the seam of ADR-0072.R21.
Source: ADR-0035.R16, ADR-0035.R16.N3

R610. Price control is a product field today (ADR-0018.R3, ADR-0018.R18). Its granularity is item and valuation area (the ADR-0018 rule 3 note of 2026-11-21); its change rule is decided by the later ADR of R609, which amends ADR-0018 rules 3 and 18 (the price-control point of the SAP comparison entry in `docs/open-questions.md`). That ADR states the phase: after step 5 and after Phase 1 unless the author moves it. Until then ADR-0018 rule 3 and spec 09 keep standard price out of Phase 1.
Source: ADR-0035.R16.N3

### Costing tables and their commands

R611. Every maintenance command of `pool_allocation_rule` (cost center, group, driver), `normal_capacity` (cost center, driver, period, quantity) and `activity_rate` is `master_data_change`, because it changes valuation.
Source: ADR-0035.R17, ADR-0045.R2

R612. By-product prices are the company's price list of kind `by_product` (ADR-0045.R2); there is no `by_product_price` table. Its maintenance is `master_data_change` too.
Source: ADR-0035.R17, ADR-0045.R2

R613. `production_order_period_cost` is written only by the costing job.
Source: ADR-0035.R17, ADR-0045.R2

R614. Costing sheets with their rates and site assignments, and detailed cost components with their mappings, are `master_data_change`, because a released estimate reaches valuation through ADR-0035 rules 4, 9 and 13. Their commands and `activity_rate`'s use the authorization leaf `costing_structure` (ADR-0072.R17).
Source: ADR-0035.R17.N1

### Costing settings and fixed behavior

R615. These setting keys are seeded `unverified` and flagged (ADR-0016.R12), each with an interim value that a regime package seeds until it has a basis (flagged); the regime makes them binding. The interim values are generic method names and switches, flagged package content of the localization package (ADR-0039.R9), not national legal values:
   - `production.wip_method` (a WIP method of ADR-0035.R9): interim value the regime package seeds (flagged) `direct_material`;
   - `production.abnormal_cost.applies`: interim value the regime package seeds (flagged) true;
   - `production.abnormal_cost.tolerance_percent`: interim value the regime package seeds (flagged) 0;
   - `production.normal_capacity.applies`: interim value the regime package seeds (flagged) true;
   - `production.co_product_split` (the co-product split of ADR-0035.R13): interim value the regime package seeds (flagged) `cost_coefficient`;
   - `production.estimate_price_basis` (a price basis of ADR-0035.R14): interim value the regime package seeds (flagged) `actual_average`.
   Source: ADR-0035.R18, ADR-0035.R18.N2

R616. The neutral references of abnormal cost and normal capacity are IAS 2 paragraph 16 (abnormal amounts) and paragraph 13 (normal capacity); the national standard's paragraphs are `l10n_vn`'s rationale (ADR-0053.R6).
Source: ADR-0035.R18, ADR-0035.R18.N1

R617. `wip_completion_percent` and the pool allocation rules are company data, not settings.
Source: ADR-0035.R18, ADR-0035.R18.N2

R618. These points are fixed core behavior, flagged:
   - unabsorbed, abnormal and residual cost go to cost of goods sold;
   - abnormal cost is valued at period actual;
   - the units-in-process definition (ADR-0035.R9 and its notes);
   - a negative residual offsets abnormal cost when completion has no receipt;
   - received stock is valued at zero when planned WIP is capped;
   - the by-product value source is `regime` (ADR-0035.R13);
   - the disassembly split;
   - the singular fallback;
   - `cost_behavior` of overhead accounts is account data;
   - the subledger is activated before the first release (ADR-0034.R15).
   Source: ADR-0035.R18, ADR-0035.R18.N2

R619. The keys a regime package seeds and its `cost_behavior` seeds are package content (ADR-0039.R6, ADR-0039.R9). The mapping of the production leaves and of WIP to a regime's operational accounts is flagged content of the localization package and is DS-19's and the author's (the DS-41 question). Because an operational account maps to one system account (ADR-0010.R11), a regime whose chart has one WIP account maps the leaves to its sub-accounts per cost element plus one for WIP.
Source: ADR-0035.R18

### Catalog changes

R620. Movement types (code: direction, value source, costing role, offset key):
   - `production_issue`: out, `preliminary_price`, `production_input`, `production_consumption`;
   - `production_return`: in, `preliminary_price`, `production_input`, `production_consumption`;
   - `production_receipt`: in, `preliminary_price`, `production_output`, `production_output`;
   - `co_product_receipt`: in, `preliminary_price`, `production_output`, `production_output`;
   - `by_product_receipt`: in, `regime`, `production_output`, `production_output`;
   - `disassembly_issue`: out, `preliminary_price`, `production_input`, `production_consumption`;
   - `disassembly_receipt`: in, `preliminary_price`, `production_output`, `production_output`.
   Source: ADR-0035.R19

R621. The costing roles of ADR-0020.R4 include `production_input` (into a cost-object node, revalued; a return counts negative) and `production_output` (from one, revalued unless its value is final).
Source: ADR-0035.R19

R622. Transaction keys (key: accounts; determinants):
   - `production_consumption`: `production_cost_material`; none;
   - `production_output`: `inventory_work_in_process`; valuation class of the order's main output;
   - `production_wip_transfer`: `inventory_work_in_process`; valuation class of the order's main output;
   - `production_abnormal_cost`: `cost_of_goods_sold;expense_other`, regime alternatives; none;
   - `production_unabsorbed_overhead`: `cost_of_goods_sold;expense_other`, regime alternatives; none;
   - `production_residual_cost`: `cost_of_goods_sold`; none.
   Which alternative a regime picks, and where its operational account sits, is package content (ADR-0053.R6). ADR-0037.R9 adds `production_external_service` and `inventory_at_processor_posting`.
   Source: ADR-0035.R19, ADR-0035.R19.N1

R623. For a `disassembly` order the determinant of `production_output` and `production_wip_transfer` is the valuation class of the header item, the input being taken apart, because its outputs are co-product lines.
Source: ADR-0035.R19.N2

R624. The leaf side of the WIP transfer, the abnormal cost and allocations copy the source line's account. `consumption` also lists `production_cost_overhead`, for internal consumption to a factory cost center.
Source: ADR-0035.R19

### Reserved catalog rows of costing

R625. The production range (ADR-0033.R16) holds `INV-106` (after the job, an order's `inventory_work_in_process` balance equals the closing amounts of its latest `production_order_period_cost`, zero for a technically complete order), `INV-107` (after the job, each `cost_pool` cost object's balance on the production leaves is zero for the period) and `INV-108` (the naive recomputation of DS-16 rule 29, extended with cost-object nodes, reproduces every production receipt's value).
Source: ADR-0035.R20

R626. Reserved edge cases of costing, without a catalog code yet:
   - an order open across a period end under each WIP method;
   - an idle pool;
   - fixed overhead below normal capacity;
   - abnormal consumption at completion;
   - a late cost on a completed order;
   - a capped planned WIP;
   - a by-product worth more than the order;
   - a rework cycle;
   - a singular component.
   Source: ADR-0035.R20

### Planning production orders

R627. `production.contract.plan_production` is a pure function. Planning calls it in-process, on structures it has loaded in bulk. Mode `backward` (item, warehouse, good quantity, `required_date`, `earliest_start`) serves new proposals: it selects the version valid on `required_date` for the quantity (ADR-0033.R13), as ADR-0034.R2 does, and requires it to be valid on the resulting start, else the next version in order, else `production_version_missing` (ADR-0033.R5 note). It schedules backward; when the start would fall before `earliest_start`, it schedules forward from `earliest_start` and reports the lateness.
Source: ADR-0036.R3, ADR-0036.R3.N1

R628. Mode `forward` (item, warehouse, good quantity, start) selects the version valid on the start. It serves ADR-0036.R10 and `UpdatePlannedOrder`, which calls the function once, in mode `forward` from the order's start (the new one when it sets one), and stores the selected version and dates.
Source: ADR-0036.R3, ADR-0036.R3.N1

R629. Mode `fixed` (`production_version_id`, good quantity, start) keeps the version and the start. It serves firmed and updated orders, conversion and `INV-109`: every run after `UpdatePlannedOrder`, and conversion, use mode `fixed` with the stored version and dates.
Source: ADR-0036.R3, ADR-0036.R3.N1

R630. External operations take their lead times from `supplier_item` and the routes (ADR-0037.R3).
Source: ADR-0036.R3

R631. In every mode the function explodes at the resulting start (ADR-0033.R5, ADR-0033.R6) and returns the version and revisions; the planned start, end and availability dates; the operation schedule; and the components with quantities and dates.
Source: ADR-0036.R3

R632. A version with lead time method `fixed` (`production_lead_time_method`) has no operation schedule: its components are due at the start, and it loads no work center.
Source: ADR-0036.R3

R633. `ConvertPlannedOrder` for a production planned order runs in one transaction. It calls `production.contract.create_production_order_from_plan`, passing the stored version and planned start. That interface uses mode `fixed` and writes the draft production order (ADR-0034) as actor `system` on behalf of the converter, with `origin_planned_order_id`. The draft's output supply line carries `origin_planned_order_id`; its component lines are demand lines.
Source: ADR-0036.R8

R634. A converted production planned order contributes neither supply nor dependent demand; ADR-0024.R8's "quantity not yet matched" rule does not apply to production orders. Pegging is never rewritten: `ListPegging` resolves a converted parent through `origin_planned_order_id`.
Source: ADR-0036.R8

R635. If the draft's explosion differs from the plan (a revision changed meanwhile), the draft wins and the next run nets again. Release follows ADR-0034.R5. Auto-conversion and auto-release are DS-28's (open question).
Source: ADR-0036.R8

### Subcontracting: scope and external operations

R636. Subcontracting has a direction "we subcontract" (our materials go to a processor and the processed goods come back), designed in full for assembly-type manufacturers, and a direction "we process for a customer" (the customer's materials come to us), which has seams and a requirements list only. Whether the second enters Phase 1, with customs reporting for processing, is the author's question (open question). Outsourced work runs on the production core: an external operation on the order, components moved, still ours, to a warehouse that stands for the processor, the service bought on a purchase line tied to the operation, and a service receipt that records progress, consumes the components at the processor, posts the service cost to the order and can receive the output.
Source: ADR-0037.D0

R637. An external operation (ADR-0033.R10) names `service_item_id` (a `service` product) and `default_supplier_id`. On the order, `production_order_operation` holds the chosen supplier in `supplier_partner_id`.
Source: ADR-0037.R2

R638. Components assigned to an external operation have the supplier's processor location as their issue warehouse. They are demand lines there, so planning supplies them through a transfer route from the production warehouse to that location; a missing route raises `planning_parameter_missing` (ADR-0034.R9, ADR-0036.R1).
Source: ADR-0037.R2

R639. Such components are an exception to ADR-0034.R2's backflush-warehouse rule: the service receipt consumes them at the processor location (R651). Serial-tracked components are issued there manually. Whole-item subcontracting is a routing whose only operation is external.
Source: ADR-0037.R2

R640. When the supplier chosen for an external operation that has components has no active processor location, `CreateProductionOrder`, its updates and change orders are rejected with `processor_location_missing`, naming the supplier. A planning run meeting the case for a version's default supplier raises `planning_parameter_missing` with reason `processor_location_missing`.
Source: ADR-0037.R2.N1

R641. An external operation's duration is `supplier_processing_days` of the supplier's `supplier_item` for the service item, on the supplier's calendar, plus the transit days of the return route, the `transfer_route` from the processor location to the production warehouse (ADR-0024.R3). The outbound transit is not added: components reach the processor by their own planned transfer (R638), whose route lead time already offsets them. Without a `supplier_item`, the routing durations apply, on the production warehouse's calendar. A missing return route raises `planning_parameter_missing` (reason `processor_route_missing`) in a run; order scheduling then counts zero transit and returns the same check result.
Source: ADR-0037.R3, ADR-0037.R3.N1

R642. Order scheduling (ADR-0034.R3) and `plan_production` both use this duration; `plan_production` receives the values with the structures it loads. External operations load no work center.
Source: ADR-0037.R3

### Subcontracting: buying the service

R643. Releasing an order emits its approval event (ADR-0009.R22). A `purchasing` consumer drafts one purchase request line per external operation (ADR-0024.R22 pattern, actor `system`), for the service item and the operation's planned quantity at the supplier's price. The line carries `production_order_operation_id`, a typed line reference that ADR-0028.R2 reserves to the author under B3, so it is flagged (open question).
Source: ADR-0037.R4

R644. A re-release drafts nothing twice: the consumer's key is the operation.
Source: ADR-0037.R4

R645. A change of G updates a draft line, or creates a work item when an order line exists. `Cancel` and technical completion cancel open draft lines, or create a work item for open order lines.
Source: ADR-0037.R4

R646. Choosing another supplier after release is a change order on the production order (ADR-0034.R8): component issue warehouses move to the new processor location, and staged stock moves by transfer.
Source: ADR-0037.R4

### Subcontracting: the service receipt

R647. `service_receipt` is a posting document type owned by `purchasing`, for purchase order lines that carry `production_order_operation_id`. Its authorization leaf sits under `purchasing` (`authorization-areas.csv`), its registry flags are in ADR-0047.R1's note, and the templates `buyer` and `warehouse_keeper` hold `post` on it (ADR-0054.R11 note).
Source: ADR-0037.R5, ADR-0037.R5.N1

R648. A service receipt records a supplier's delivery, so it follows `goods_receipt`'s flagged interim (ADR-0009.R19; ADR-0027.R13): reversible while no invoice refers to it, otherwise corrected by a correction document.
Source: ADR-0037.R5

R649. Its record scope uses the processor location as the warehouse dimension (ADR-0017.R9), and it emits the ADR-0009 document events.
Source: ADR-0037.R5

R650. Its fields are yield, scrap, `is_final` and, for automatic receipt, the output lot.
Source: ADR-0037.R5

R651. Posting a service receipt does, in one transaction:
   - progress, through `production.contract.record_operation_progress` (ADR-0034.R12);
   - the backflush of the operation's components at the processor location, by cumulative progress and rounded up, as `production_issue` with the order's cost object; `record_operation_progress` computes and posts it and stores the generated lines in the production-owned `operation_progress_component`, keyed by the calling posting document, as for confirmations; `service_receipt` holds only its own lines;
   - the service cost: debit `production_cost_other` (order), credit GR/IR clearing at the order price with `purchase_order_line_id` (ADR-0030.R3 to ADR-0030.R5), key `production_external_service`;
   - when the operation is the order's last, of either control, and the version sets automatic receipt, the output into the production warehouse (ADR-0034.R13).
   Source: ADR-0037.R5

R652. Too little stock at the processor rejects the service receipt with `negative_stock`.
Source: ADR-0037.R5

R653. Reversal of a service receipt is refused once an invoice refers to it. Otherwise it reverses, in this order: the automatic receipt, the backflush, the cost and the progress.
Source: ADR-0037.R5

R654. A service receipt drafted from a processor's delivery note is tainted (ADR-0029.R10), so a human posts it. Simulation applies as for any command.
Source: ADR-0037.R5

### Subcontracting: afterwards

R655. The invoice clears GR/IR at the order price (ADR-0030.R4). A service has no pending receipt adjustment, so a difference posts straight to the order's `production_cost_other` while the order is not closed, and after close to the price-difference account, never the stock-bound path, since a service has no receipt lines. Both paths are interim and flagged. After close the difference posts without a valuation class, so it reaches the generic price difference row (ADR-0039.R8).
Source: ADR-0037.R6

R656. When the processor reports actual consumption, a `production_issue` or return at the processor location adjusts the order. Leftovers come back by transfer.
Source: ADR-0037.R6

### Subcontracting: owner seams and the follow-up

R657. `owner_partner_id` is reserved on `production_order_component`, `production_order_output` and `demand_supply_line`, so the follow-up needs no change to stock rows, order lines or demand lines; a contract reference on stock document lines and a value source would still be added. This extends ADR-0030.R8's axis, which covers stock rows, material lines, warehouse movements, reservations and tasks. The `demand_supply_line` column is flagged for the author under B3 (ADR-0028.R2).
Source: ADR-0037.R7

R658. In Phase 1 every row has a null owner, so nothing changes for own stock.
Source: ADR-0037.R7

R659. If the author brings processing for a customer into Phase 1, its design must run available to promise, reservation, netting and pick removal per owner; an issue line's owner chooses a quantity-only customer movement type, or `production_issue`.
Source: ADR-0037.R8

R660. Its costing must read order quantities by order line, whatever the costing role; value customer components at zero and leave them out of price-based drivers, estimates and abnormal cost; and post the order's output share debit cost of goods sold, credit `inventory_work_in_process`, at receipt or held in work in process until the fee revenue, as the author chooses. The work-in-process account of a regime is package content (ADR-0053.R14).
Source: ADR-0037.R8, ADR-0037.R8.N1

R661. Its documents and catalogs must include customer material receipt and delivery documents with a contract reference; count differences, scrap and transfers of customer stock; and a value source `none` with its movement types.
Source: ADR-0037.R8

R662. Its customs part must have a regime per processing contract, not per company; customs codes per item; contract norms and their precedence over bills of materials; actual norms and quantity ledgers as derived queries in the customs unit; leftover and report deadlines as regime settings; and the year-end disclosure of materials held for others (DS-26), which is a book over the row source `stock`, filtered to non-owned stock (ADR-0049.R22).
Source: ADR-0037.R8, ADR-0037.R8.N2

### Subcontracting: catalog rows

R663. Transaction key `production_external_service`: account `production_cost_other`, control kind `cost_object`, no determinants.
Source: ADR-0037.R9

R664. Transaction key `inventory_at_processor_posting`: the inventory leaves, control kind `inventory`, determinants valuation class and warehouse.
Source: ADR-0037.R9

R665. The production range (ADR-0033.R16) holds `INV-111` (every material line at a processor location has one of the movement types ADR-0037.R1 allows) and `INV-112` (every `operation_progress_component` line, whatever its calling document, refers to a component line of the same order and to a material line with movement type `production_issue`; for a service receipt that line is at the order's processor location).
Source: ADR-0037.R10, ADR-0037.R10.N1

R666. Reserved edge cases of subcontracting, without a catalog code yet:
   - whole-item subcontracting, with a service receipt that consumes components and receives output;
   - a processor's actual consumption above the backflush;
   - an invoice difference before and after the order closes;
   - a supplier change after release;
   - a reversal of a service receipt.
   Source: ADR-0037.R10

### Production uses of prices

R667. `relative_sales_value` reads the default sale list for the inventory unit, quantity 1 and no options, on the period's last day. From a tax-inclusive list the price is reduced to net by ADR-0041.R9's inclusive split. Which list is the cost-split basis is flagged.
Source: ADR-0045.R6

R668. The estimate's `purchase_price` is the preferred supplier's (ADR-0024.R2) purchase-list price for one purchase unit on the estimate date, converted to the inventory unit, and from a foreign currency at rate type `transaction` on that date (ADR-0011.R11). With none, the estimate uses the actual average and returns the check result `purchase_price_missing`. The fallback is flagged.
Source: ADR-0045.R6

R669. The `by_product` list gives by-product prices per inventory unit in company currency (ADR-0045.R2).
Source: ADR-0045.R6

### Product configuration

R670. Module ownership of product configuration (ADR-0022.R2):
   - `master_data` owns the characteristics (columns on `variant_attribute`), configuration models and their revisions, rules, tables and defaults, `product_configuration` and its values, and the price tables; it publishes `master_data.contract.evaluate_configuration` and `master_data.contract.evaluate_condition`;
   - `production` owns the selection conditions and sizing on bill of materials components and routing operations, product-level production versions, and `production.contract.estimate_configuration`; it calls `evaluate_condition`;
   - the commercial modules (`sales`, `purchasing`) and `production` carry a configuration on their lines.
   Source: ADR-0046.R1

R671. Configuration model maintenance is `master_data_change`, change-tracked (ADR-0038.R3) and `is_proposal_bound` (ADR-0029.R5). Finding or creating a configuration record is part of the line's command.
Source: ADR-0046.R1

R672. A line of a configurable product may leave draft only with a complete configuration (`configuration_incomplete`, listing the missing characteristics and the violations).
Source: ADR-0046.R10

R673. The line's warehouse must be the production warehouse of one of the product's product-level versions (`configuration_warehouse_not_produced`), so make-to-order supply and reservation meet it (ADR-0034.R14). Transfers of configured units are later.
Source: ADR-0046.R10

R674. Copying a line to a new document (quotation to order, order to delivery) evaluates the configuration under the model revision valid on the new document's date. If it is no longer valid, the copy is rejected with `configuration_invalid` and the violations, and the user reconfigures. An existing document keeps its configuration.
Source: ADR-0046.R10

R675. Deliveries, returns, credit notes and production orders copy the configuration from their source line without re-evaluation. Production orders without a sales line carry the configuration entered on them; their line options are information.
Source: ADR-0046.R10

R676. A change order (ADR-0028.R4) that alters a line's configuration is rejected with `configuration_in_production` while any production order linked to that line is open (not closed or cancelled). Planned orders need nothing: the next planning run replans them for the new item.
Source: ADR-0046.R10

R677. `production_version` has `product_id`, exclusive with `item_id`: a version of a configurable product applies to every configured item of it. Version selection for a configured item looks for an item-level version first, then a product-level one (ADR-0033.R13). `bill_of_materials` has `product_id`, exclusive with `item_id`, for the product-level bill of materials (the super bill of materials), whose main output at explosion is the configured item.
Source: ADR-0046.R12

R678. Components of a product-level bill of materials have `selection_condition` (ADR-0046.R5 grammar, without `set` or `unset`; empty means always) and a `sizing`:
   - `fixed`: the stored quantity, which must be positive (`ck_bill_of_materials_component_quantity`);
   - `linear`: quantity = `quantity` + `quantity_per_value` × the value of a numeric item-defining characteristic, with `quantity_per_value` in the component's unit per unit of the characteristic; the base `quantity` may be zero or negative.
   A result of zero drops the line. A result that could be negative is rejected at release (`configured_quantity_negative`), checked at the characteristic's `minimum_value` and `maximum_value`, which covers every value because sizing is linear. Alternatives are separate component rows with exclusive conditions. Lab check `t16_planning_production_ddl.py` N07b covers the negative base.
   Source: ADR-0046.R12, ADR-0046.R12.N2

R679. Routing operations have `selection_condition` and the same linear sizing of their durations. A routing with conditions serves one configurable product (`routing_conditions_shared`), an exception to ADR-0033.R9's sharing.
Source: ADR-0046.R12

R680. Conditions and sizing may name only item-defining characteristics of the product (`configuration_characteristic_not_item_defining`), checked at bill of materials and routing release and at model release (ADR-0046.R4). One item has one structure and one cost: a line option can never change what is built.
Source: ADR-0046.R12

R681. A configured item's structure is the product-level revision valid on the explosion date, like any item's (ADR-0033.R4, ADR-0033.R5); a new revision changes what later orders of an existing configured item use. Because estimates are made at once for new configured items, they pin revisions early, and the withdrawal rule (`revision_in_use`) rarely applies.
Source: ADR-0046.R12

R682. In Phase 1 values are not passed to subassemblies. A component that varies is chosen among fixed items by conditions; a phantom component is exploded with its own structure. The configurable product is a node of the cycle check and of low-level codes (`item_low_level_code`), and its configured items inherit its low-level code (ADR-0033.R8 note).
Source: ADR-0046.R12, ADR-0046.R12.N1

## Invariants

Statements are those of `invariants.csv`. This chunk holds the rows whose catalog source is a rule of this chunk.

| ID | Name | Check point | Statement | Protects |
| --- | --- | --- | --- | --- |
| `INV-106` | `wip_matches_period_cost` | day | After the costing job, each order's `inventory_work_in_process` balance equals the closing amounts of its latest `production_order_period_cost`, and a technically complete order's is zero. | R613, R625 |
| `INV-107` | `cost_pools_cleared` | day | After the costing job, each `cost_pool` cost object's balance on the production leaves is zero for the period. | R625 |
| `INV-108` | `production_receipts_recomputed` | day | The naive recomputation, extended with cost-object nodes, reproduces every production receipt's value. | R625; DS-16 rule 29 |
| `INV-111` | `processor_movements_allowed` | day | Every material line at a processor location has one of the movement types ADR-0037 rule 1 allows there. | R665; ADR-0037.R1 |
| `INV-112` | `backflush_lines_match_order` | day | Every `operation_progress_component` line refers to a component line of the same production order as its calling document and to a material line of that document with movement type `production_issue`; for a service receipt that material line is at the order's processor location. | R651, R665; ADR-0034.R12 |

Named by a rule of this chunk, with its row in another chunk: `INV-109` (R629).

## Settings

No row of `settings.csv` belongs to the rules of this chunk. The keys of R615 (`production.wip_method`,
`production.abnormal_cost.applies`, `production.abnormal_cost.tolerance_percent`, `production.normal_capacity.applies`,
`production.co_product_split`, `production.estimate_price_basis`) are named by the rules but absent from `settings.csv`;
ADR-0039.R9 lists them as regime-level keys a regime package seeds.

Reads: `journal.manual_posting_to_control_accounts` and `stock_count.bin_difference_method` (keys of ADR-0039.R9, owned
elsewhere); `production.mes_import.auto_post` (ADR-0043.R14.N3; its row stands in the chunk of ADR-0064.R25).

## Conflicts

CONFLICT ADR-0035.R16: the notes ADR-0035.R16.N1 and ADR-0035.R16.N3 apply: country method names are package content, and standard cost valuation is decided as a price-control option (R607, R609).
CONFLICT ADR-0035.R17: superseded by ADR-0045.R2; the company's price list of kind by_product replaces the by_product_price table (R612).
CONFLICT ADR-0035.R18: notes ADR-0035.R18.N1 and ADR-0035.R18.N2 govern; listed keys are settings, pool rules company data, the remaining points fixed core behavior (R615 to R618).
CONFLICT ADR-0035.R19: ADR-0035.R19.N1 lists regime alternatives for the abnormal and unabsorbed keys, and ADR-0035.R19.N2 changes the disassembly determinant (R622, R623).
CONFLICT ADR-0036.R3: note ADR-0036.R3.N1 governs version selection in backward mode and the stored version used by later runs (R627 to R629).
CONFLICT ADR-0037.R3: note ADR-0037.R3.N1 governs; only the return route transit is added to the external duration, not the outbound route (R641).
CONFLICT ADR-0037.R8: note ADR-0037.R8.N1 governs; the output share is held in work in process, whose regime account is package content (R660).
CONFLICT ADR-0035.R15.N2: ADR-0078.R2 makes the variance agent `production_variance` a Phase 2 agent type with mode `off` (R605).
CONFLICT ADR-0037.R10: note ADR-0037.R10.N1 extends INV-112 to every operation_progress_component line, whatever its calling document (R665).

## Trace

| Source | Where |
| --- | --- |
| ADR-0035.R15 | R601-R603, R605 |
| ADR-0035.R15.N1 | R604 |
| ADR-0035.R15.N2 | R605 |
| ADR-0035.R15.N3 | R602, R606 |
| ADR-0035.R16 | R607-R609 |
| ADR-0035.R16.N1 | R607 |
| ADR-0035.R16.N2 | R608 |
| ADR-0035.R16.N3 | R609, R610 |
| ADR-0035.R17 | R611-R613 |
| ADR-0035.R17.N1 | R614 |
| ADR-0035.R18 | R615-R619 |
| ADR-0035.R18.N1 | R616 |
| ADR-0035.R18.N2 | R615, R617, R618 |
| ADR-0035.R19 | R620-R622, R624 |
| ADR-0035.R19.N1 | R622 |
| ADR-0035.R19.N2 | R623 |
| ADR-0035.R20 | R625, R626 |
| ADR-0036.R1 | ref: ADR-0036.R1 |
| ADR-0036.R2 | ref: ADR-0036.R2 |
| ADR-0036.R3 | R627-R632 |
| ADR-0036.R3.N1 | R627-R629 |
| ADR-0036.R8 | R633-R635 |
| ADR-0036.R13 | ref: ADR-0036.R13 |
| ADR-0037.D0 | R636 |
| ADR-0037.R2 | R637-R639 |
| ADR-0037.R2.N1 | R640 |
| ADR-0037.R3 | R641, R642 |
| ADR-0037.R3.N1 | R641 |
| ADR-0037.R4 | R643-R646 |
| ADR-0037.R5 | R647-R654 |
| ADR-0037.R5.N1 | R647 |
| ADR-0037.R6 | R655, R656 |
| ADR-0037.R7 | R657, R658 |
| ADR-0037.R8 | R659-R662 |
| ADR-0037.R8.N1 | R660 |
| ADR-0037.R8.N2 | R662 |
| ADR-0037.R9 | R663, R664 |
| ADR-0037.R10 | R665, R666 |
| ADR-0037.R10.N1 | R665 |
| ADR-0039.R9 | ref: ADR-0039.R9 |
| ADR-0039.R9.N1 | ref: ADR-0039.R9.N1 |
| ADR-0043.R14.N3 | ref: ADR-0043.R14.N3 |
| ADR-0043.R17 | ref: ADR-0043.R17 |
| ADR-0043.R17.N1 | ref: ADR-0043.R17.N1 |
| ADR-0045.R6 | R667-R669 |
| ADR-0046.R1 | R670, R671 |
| ADR-0046.R4 | ref: ADR-0046.R4 |
| ADR-0046.R10 | R672-R676 |
| ADR-0046.R12 | R677-R682 |
| ADR-0046.R12.N1 | R682 |
| ADR-0046.R12.N2 | R678 |
