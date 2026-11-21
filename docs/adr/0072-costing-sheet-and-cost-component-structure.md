# ADR-0072: Costing sheet and cost component structure

Status: accepted (2026-11-21) under ADR-0005, reviewed by Claude Fable 5.2 (builder Claude Opus 5.5; proposed 2026-11-18) after three review rounds, the fixes verified by Claude Opus 5.5.
Design items: DS-53 (costing), DS-56 (configured product costing), DS-26 (reports), DS-34 (agents), DS-15 (roles). Related decisions: D6. Principles 6, 12, 13. ADR-0004, ADR-0006, ADR-0007, ADR-0008, ADR-0020, ADR-0022, ADR-0029, ADR-0033, ADR-0034, ADR-0035, ADR-0043, ADR-0045, ADR-0046, ADR-0051, ADR-0060, ADR-0062, ADR-0063, ADR-0064, ADR-0068, ADR-0069.

## Decision

The author's decision of 2026-11-18: ADR-0035 keeps actual costing as it is (the order cost sheet's row source `production_order_period_cost`, actual overhead through cost-center pools at normal capacity, variance analysis). The gap is planned costing. `cost_estimate` priced overhead with an interim table, `overhead_surcharge` (one percent per cost center and period, with no stated base), and an interim `cost_estimate_line.cost_center_id`; cost components were fixed at four. This ADR closes the gap with two structures and makes the costing milestones of an order explicit.

**A costing sheet for planned costing only.** A simplified SAP costing sheet: ordered rows of three kinds (base, surcharge, subtotal); surcharges as a percent of a base or subtotal, or an amount per output unit or per activity unit; rates by effective dates with optional conditions on site, item group and valuation class; each surcharge credits a cost center for reporting and lands in a detailed component. Administration and selling rows apply only to selling-price costing (cost-plus), never to the production estimate. One sheet per site, with an optional override per production version. It prices estimates, configured products and quotes; it never values stock and never posts.

**A configurable cost component structure for reporting.** Up to 12 detailed components per company, each mapped deterministically from activity types, item groups, valuation classes and accounts, each rolling up to exactly one of the four posting components. Postings, valuation, settlement keys and INV-106 are unchanged: estimate lines carry the detail, and the period-end job writes a detail read model beside `production_order_period_cost`.

**Costing milestones.** Partial receipts keep the item's preliminary price (consistency with the item's issues in the same period), with a query that shows planned against preliminary per receipt; a non-posting projected final cost query at completion; the period-end order of ADR-0035 summarized with what becomes final.

| Need | Today | Decision |
| --- | --- | --- |
| Overhead in an estimate | `overhead_surcharge`: a percent per cost center and period, no base (interim) | Costing sheet rows with a stated base, percent or per-unit rates, conditions (rules 6–9) |
| The cost center of an estimate line | `cost_estimate_line.cost_center_id` (interim) | `credited_cost_center_id`, only on surcharge lines (rule 11) |
| Cost components | Four, fixed | Four posting components plus up to 12 detailed ones for reports (rules 2–5) |
| Quote costing | `estimate_configuration`, production cost only | Plus administration and selling rows in `GetSellingPriceCosting` (rule 10) |
| Expected order result before period end | None | `GetProductionOrderProjectedCost`, provisional (rule 14) |

### Rules

**Scope**

1. Planned costing only:
   - **What the sheet prices.** `cost_estimate` (draft and released, configured items' estimates included, ADR-0035 rule 14; ADR-0046 rule 14), `estimate_configuration` and `GetConfigurationEstimate` (ADR-0046 rule 14), selling-price costing (rule 10), the projected final cost (rule 14) and the absorption report (rule 12).
   - **What it never does.** It values no stock and posts nothing. Actual overhead stays with the pools of ADR-0035 rule 7.
   - **Where a released estimate already reaches valuation**, it still does, unchanged, and only with its production rows: the preliminary price of a produced item without history (ADR-0035 rule 4; ADR-0020 rule 11), `planned_cost` WIP (ADR-0035 rule 9) and the disassembly split (ADR-0035 rule 13).
   - **Unchanged.** ADR-0035 rules 2–13 and 16; the row source `production_order_period_cost` and a localization package's book over it.

**Cost component structure**

2. `cost_component_detail` (company data, `production`):
   - **Columns.** `code`, `name`, `cost_component` (`material`, `labor`, `overhead` or `other`, the posting component it rolls up to), `sequence` (report order), `is_default`, `is_active`.
   - **Defaults.** `CreateCompany` seeds four rows, coded as the posting components, with `is_default` true. Each company has exactly one active default per posting component (INV-850). A default is never deactivated and never changes component. A company that defines nothing more sees today's four components.
   - **Limit.** At most 12 active rows per company, the defaults included (`cost_component_detail_limit`). Twelve columns fit one report row; finer analysis belongs to accounts and activity types, which the detail is mapped from.
   - **Fixed component.** Once an estimate line or a period cost detail row names a detail, its `cost_component` cannot change (`cost_component_detail_in_use`).
   - **An example set** (not seeded): `raw_material` and `packaging` (material); `direct_labor` (labor); `machine`, `energy`, `depreciation` and `overhead` (overhead); `subcontracting` (other).
3. Mapping, `cost_component_detail_mapping` (company data, `production`):
   - **Rows.** A detail and one source: `activity_type`, `item_group`, `valuation_class` or `account` (an operational account). The row carries its detail's posting component through a composite key, and one source maps to at most one detail per posting component (a unique key), so the mapping is a function.
   - **The function.** `production.map_cost_component_detail(company, cost_component, activity_type, item_group, valuation_class, account)` is pure. It looks only among details of the given posting component, in this order: activity type, item group, valuation class, account; the first hit wins; no hit gives the component's default.
   - **Why this order.** Activity type first, so that planned activity cost in an estimate and actual cost allocated by the same activity land in the same detail; item attributes before the account, because all material lines post to one leaf; the account last, for pool cost allocated by a constant basis.
   - **Why postings are unchanged.** The function never leaves the line's posting component, so no amount moves between the four components, leaves, keys or pools.
   - **Facts per line:**

     | Line | Facts passed |
     | --- | --- |
     | Estimate material line; issue, return and their revaluation; consumer-split share (ADR-0021 rule 7) | the item's group and valuation class, the line's account |
     | Estimate activity line | the activity type |
     | Pool allocation (ADR-0035 rule 7) | the allocation rule's activity type when the driver is one, and the source line's account |
     | External service on `production_cost_other` | the service item's group when it has one, and the account |
     | Abnormal cost (ADR-0035 rule 10) | its component line's item, or its activity type |
     | Estimate surcharge line | none: its row names the detail (rule 6) |
4. Where the detail is stored (the storage decision):
   - **Estimates.** `cost_estimate_line.cost_component_detail_id`, NOT NULL, stamped when the estimate is computed and frozen with it. A composite key holds it to the line's `cost_component`.
   - **Order actuals.** `production_order_period_cost` and `production_cost_settlement_line` keep their keys, so INV-106, ADR-0035 rule 5's settlement keys and reruns are unchanged. The period-end job writes, in the same transaction, the read model `production_order_period_cost_detail`: one row per order, period and detail, with the same six amounts; a rerun rewrites it with its parent.
   - **The split.** Opening = the detail's closing of the order's previous period with costs (none: the default detail takes the parent's opening). Incurred and abnormal: each line by rule 3. Residual and closing: the parent's amounts split in proportion to each detail's available amount (opening + incurred − abnormal) by largest remainder, ties by `sequence`, then `code`; when the component's available amount is 0, both go to the default detail. To-output: the rest per detail. Every column sums exactly to the parent (INV-851), and each row balances like its parent.
   - **Why not a key on `production_order_period_cost`.** The solve, the WIP methods and INV-106 work per posting component (ADR-0035 rules 6, 9). A detailed key would multiply nodes, settlement lines and rerun differences for a reporting need.
   - **Why not a pure report-time mapping.** The WIP carried between periods needs the previous period's split, a mapping change would restate closed periods, and the analysis layer reads one stored figure (ADR-0060 rule 19; ADR-0035 rule 15 note). The same function still maps journal and document lines at report time for drill-down (rule 5).

   Note (chief architect, 2026-11-21, under the author's delegation of that day; the author's instruction that costing follows SAP): the actual cost component split through stock (SAP carries the standard cost estimate's split through actual costing across levels, from a period start; point A4 of the verification section of [reviews/2026-11-21-costing-sap-comparison.md](../reviews/2026-11-21-costing-sap-comparison.md)) is a seam in Phase 1, not built. The split stops at the order, as stored above. The later feature carries values per posting component through the stock nodes of [ADR-0020](0020-inventory-and-costing-model.md) rule 12's solve as extra right-hand sides of the same system, stores them as a read model per item, valuation area, period and component, and starts at a period start with an opening split taken from purchase (all `material`) or from the released estimate's components; nothing posted changes, so Phase 1 needs no column for it (ADR-0020 rule 12 note of this date).
5. Reports:
   - **`GetCostEstimate`** shows lines by detail and the costed sheet rows (rule 8).
   - **The order cost report** (DS-26) and **`GetProductionOrderVariance`** take an optional grouping `cost_component_detail`: target per detail from the estimate's lines, scaled as ADR-0035 rule 15 says; actual from `production_order_period_cost_detail`. The variance categories are unchanged.
   - **`ListProductionOrderVarianceDriver`** (ADR-0064 rule 10) gives each driver row its detail through rule 3.
   - **`production_order_variance`** (ADR-0060 rule 19) stays per category, without a detail column.
   - **Books.** A book definition over `production_order_period_cost` may group by detail; that choice belongs to its package.

**Costing sheet**

6. `costing_sheet` (company data, `production`: `code`, `name`, `is_active`) and its ordered `costing_sheet_row` rows (`row_number`, positive; `row_kind`; `label`; `usage`):
   - **`base`.** Its members (`costing_sheet_base_member`) are posting components or detailed components. It reads the estimate's priced lines (material, activity, external service), never surcharge lines. Each priced line counts in at most one base row of a sheet (members disjoint, `costing_sheet_row_invalid`); a line no base row covers stays in the total and bears no surcharge. `is_lower_level_included` (default false): false takes only the version's own lines (level 0); true also the lines rolled up from made components, as when semi-finished goods carry material overhead at the parent.
   - **`surcharge`.** `surcharge_kind`:
     - `percent` of `base_row_number`, an earlier base or subtotal row;
     - `per_output_unit`: an amount per unit of the costing lot quantity, in the output's inventory unit;
     - `per_activity_unit`: an amount per unit of `activity_type_id`, over the estimate's own activity quantities of that type.

     It names `credited_cost_center_id`, the cost center credited for planned-versus-absorbed reporting only (rule 12). A `production` row names `cost_component_detail_id`, the detail it lands in, whose posting component is `labor`, `overhead` or `other`; never `material`, because material is issued items (ADR-0035 rule 2), and material handling overhead is an overhead detail.
   - **`subtotal`.** It sums the base and surcharge rows from `from_row_number` to `to_row_number`, both earlier rows; subtotals inside the range are skipped, so nothing counts twice.
   - **`usage`.** `production` (default) or `selling` (administration and selling overhead). Only surcharge and subtotal rows may be `selling`; a selling surcharge credits a cost center of kind `administration` or `selling` and names no detail; a production row never refers to a selling row.
   - **Simplified from SAP.** No overhead keys, credit keys or origin groups: conditions on rates (rule 7) and the detail on the row do that work.
7. Rates, `costing_sheet_rate`:
   - **Columns.** Sheet and row; `valid_from` and `valid_to` (inclusive, open end allowed); optional conditions `site_id`, `item_group_id` and `valuation_class_id`; `rate_percent` for percent rows, `rate_amount` (company currency per unit) for per-unit rows, the kind carried by a composite key.
   - **No overlap** for one sheet, row and condition set (an exclusion constraint, `costing_rate_overlap`).
   - **Selection** on the costing date (estimates, projections) or the document date (selling costing): among valid rows whose stated conditions all match the costed output (the site of the version's production warehouse, ADR-0068 rule 10; the output item's item group; its valuation class), the most specific wins by fixed precedence: site, then item group, then valuation class, compared as a three-digit binary number. No tie can remain, because the exclusion constraint forbids two valid rows with the same condition set.
   - **Missing is a gap.** A stored rate 0 is a real zero. No valid row gives the gap `costing_rate_missing`, left out of the total and never zero (ADR-0062 rule 12).
   - **Why dates, not periods.** Quotes and estimates cost future dates whose posting periods may not exist yet; a period's rate is a date range. `activity_rate` stays per period (ADR-0035 rule 17).
8. Evaluation, `production.evaluate_costing_sheet(priced lines, sheet, rates, purpose, context)`, a pure function:
   - **Order.** Rows in `row_number` order. A base row's value is the sum of its rounded lines. Percent: `round_amount(base × rate ÷ 100)`; per unit: `round_amount(quantity × rate)` (ADR-0006 rule 18). Subtotals add.
   - **Purpose.** `production` evaluates production rows only; `selling` evaluates all rows (rule 10).
   - **Lines.** Each production surcharge row with a rate writes one `cost_estimate_line`: `cost_component` from its detail, `cost_component_detail_id`, `costing_sheet_row_number`, `credited_cost_center_id`, quantity (the base amount, or the units), price (the rate), amount. A row whose value is 0 (a stored zero rate or an empty base) writes no line; its snapshot row still shows it.
   - **Snapshot.** `cost_estimate_sheet_row` keeps each evaluated production row (kind, label, base amount, rate, amount), so the sheet as costed survives later edits of the sheet. `cost_estimate.costing_sheet_id` names the sheet used.
   - **Levels.** Each estimate applies its own version's sheet. Rolled-up lines of made components keep their details and their own surcharge lines; per-unit rows count level 0 only.
   - **Gaps.** With a gap, surcharges are computed on the priced lines; the estimate is incomplete and cannot be released anyway (ADR-0062 rule 12).
   - **Planned WIP.** For `planned_cost` WIP (ADR-0035 rule 9), a percent or per-activity surcharge line counts with the share of its base row's planned cost that lies up to the last confirmed operation; a per-output-unit line counts once the last operation is confirmed.
9. Assignment:
   - **Per site.** `site_costing_sheet` (site, sheet), owned by `production`, because `master_data` may not refer to a production table (ADR-0022 rule 2).
   - **Per version.** `production_version.costing_sheet_id`, optional, overrides the site's sheet; for a configurable product, the product-level version's (ADR-0046 rule 12).
   - **Which sheet.** The version's override, else the sheet of its production warehouse's site, else none. With none, the estimate has no surcharge lines; when `production.costing_sheet.required` is true, it has the gap `costing_sheet_missing`.
   - **Why per site.** Overhead rates differ by plant (SAP assigns the costing sheet per plant through the valuation variant); the version override covers a line with its own cost structure.

**Selling-price costing**

10. Administration and selling rows:
    - **`GetSellingPriceCosting`** (module `production`, computed query, `report_production` at `read`, field class `cost`): an item or a configurable product with item-defining values, a quantity, a date and an optional site. It takes the released estimate valid on the date (ADR-0035 rule 14 note), or `estimate_configuration` for values without an item, and evaluates the current sheet with purpose `selling` over its priced lines at the date's rates. It returns the rows, the cost of goods manufactured (production rows), administration and selling, the total cost and any gaps. It is never stored and posts nothing.
    - **`estimate_configuration`** takes `purpose` as a function parameter, default `production`: it is a pure function of `production.contract` with no table, so nothing is added to a schema. (review note, 2026-11-21)
    - **Cost checks stay on production cost.** The below-cost and margin checks (ADR-0043 rule 3; ADR-0045 rule 5; ADR-0046 rule 14) never include selling rows: the floor protects what will post to cost of goods sold, and a cost-plus markup is a pricing choice for price lists and policy rules.
    - **Never in the estimate.** A selling row never writes a `cost_estimate_line` (INV-852), so it never reaches a preliminary price, WIP or a variance.

**Interim tables replaced**

11. `overhead_surcharge` is dropped and `cost_estimate_line.cost_center_id` is settled:
    - **Meaning migrated.** "A planned surcharge per cost center" (ADR-0035 rule 14) is a percent surcharge row crediting that cost center, its percent a rate whose dates cover the period, on a base row the company states. There is no data to migrate (design only).
    - **The column** becomes `credited_cost_center_id`, set exactly on surcharge lines (with `costing_sheet_row_number`) and nowhere else.
    - **Both interim markers are removed** from the DDL.

**Planned versus absorbed**

12. `GetCostCenterAbsorption` (module `production`, computed query, `report_production` at `read`, field class `cost`), per cost center and period:
    - **Actual.** The pool's cost (journal lines), what the job allocated to orders and what went unabsorbed (settlement lines; ADR-0035 rule 7).
    - **Planned absorption.** The production surcharge rows that credit the cost center, applied to the period's actual bases at the rates valid on the period's last day: incurred amounts per detail from `production_order_period_cost_detail`, activity quantities from posted confirmations, output from net receipts.
    - **The difference** is what a standard-cost system would post as over- or under-absorption; here it is reported only (rule 21).

**Costing milestones**

13. Partial output receipts during the order:
    - **Kept.** A receipt posts at the item's preliminary price (ADR-0035 rule 4; ADR-0020 rule 11) and is revalued at period end; the order's estimate does not price it.
    - **Why.** Under periodic average there is one price per item, valuation area and period for every movement of the item. Receipts and issues of the same item in the period (to a parent order, a delivery, a transfer) carry the same provisional unit value, so the area's provisional balance is quantity × one price and period end revalues only differences. Order-level prices would give the item several provisional prices in one period, with issues at a price no receipt carried. SAP values receipts at planned cost for moving-average materials, where the receipt sets the price; NativeFlows has no moving price.
    - **Made visible.** `GetProductionReceiptValuation` (module `production`, computed query, `report_production` at `read`, field class `cost`), per receipt line: quantity, the preliminary unit price and value posted, the order's planned unit cost (the target of ADR-0035 rule 15 per unit; co-products by `cost_coefficient`), the difference and its percent, `is_provisional` until the receipt's period is settled, then the settled value too. It posts nothing.
14. Order completion and close:
    - **The sequence.** Technical completion stops logistics and WIP (ADR-0034 rule 6; ADR-0035 rule 10). Abnormal cost is assessed once, over the whole order, by the next period-end run (ADR-0035 rule 10). The final actual cost is known only after the run of the period that holds the completion, because pools and actual prices are periodic (ADR-0035 rules 5–7). The close job closes the order after that settlement and the inventory area's lock (ADR-0034 rule 7).
    - **`GetProductionOrderProjectedCost`** (module `production`, computed query, `report_production` at `read`, field class `cost`; it posts and stores nothing), available at any time and meant for completion:
      - settled periods: the actual amounts of `production_order_period_cost` (final);
      - unsettled postings: net issued quantities × the current preliminary price of the item and area; confirmed activity quantities × the `activity_rate` of the execution work center for the business date's period; external service costs as posted; overhead from the order's costing sheet (production rows, rates on the business date) on these bases, since pools are known only at period end;
      - less the by-product value, and the projected abnormal cost by ADR-0035 rule 10's formula on cumulative quantities;
      - per unit over cumulative good receipts (co-products by coefficient), against the target cost, by component and by detail;
      - what it cannot price is a gap, never zero;
      - `is_provisional` is false only when the order is technically complete and every period with its postings is settled; the result then equals the stored actuals.
    - **Completion in a period with no receipt.** The unsettled cost of a period without receipts is shown as projected residual (ADR-0035 rule 10: it goes to cost of goods sold, and earlier receipts keep their value), not as cost to output.
    - **Reopen.** `ReopenProductionOrder` returns the order to `in_progress` (ADR-0034 rule 6), and the next run reverses the abnormal assessment (ADR-0035 rule 10). The projection is computed on each call, so it shows an order in progress, with nothing stored to undo.
15. Period end. The job's order is ADR-0035 rule 12 (issue revaluation, pool allocation, unabsorbed overhead, abnormal cost, residual, WIP transfer, receipt revaluation):
    - **What becomes final.** The period's actual prices, allocations at normal capacity, revalued issues and receipts, abnormal and residual cost, and each order's closing WIP per component, in `production_order_period_cost` and now `production_order_period_cost_detail`.
    - **Multi-period orders.** Closing WIP per component is the next period's opening (ADR-0035 rules 8, 9); the detail split follows it (rule 4).
    - **Reruns.** A reopened and re-solved period posts only differences per key (ADR-0035 rule 5; ADR-0012 rule 15); the read models are rewritten. A later posting into the period makes the job stale (ADR-0035 rule 3).
16. Timeline:

    | Milestone | Document or job | Price basis | Postings | Final or provisional | What the user sees |
    | --- | --- | --- | --- | --- | --- |
    | Issue or return | `production_issue` | the item's preliminary price | Debit `production_cost_material` (order), credit inventory | Provisional | Order cost so far; projected final cost |
    | Confirmation | `operation_confirmation` | none (quantities) | None | Quantities final; their cost at period end | Projected final cost at planned rates and sheet |
    | Partial receipt | `production_receipt` | the item's preliminary price | Debit inventory, credit WIP (order) | Provisional | `GetProductionReceiptValuation`: planned against preliminary |
    | Technical completion | `CompleteProductionOrder` | none | None; WIP stops, abnormal cost waits for the run | Provisional | `GetProductionOrderProjectedCost` (rule 14) |
    | Period end | costing job, `production_cost_settlement` | period actual average; pools at normal capacity | The seven steps of ADR-0035 rule 12 | Final for the period, unless reopened and solved again | `production_order_period_cost` and its detail; variance; absorption |
    | Close | `CloseProductionOrder` (system job) | none | None (cost postings still allowed on a rerun) | Final | Order cost report and variance |

**Commands, agents and effect class**

17. Commands (module `production`, effect class `master_data_change`, change-tracked, `is_proposal_bound`, with the optional `expected_version` of ADR-0029 rule 2; leaf `costing_structure` at `edit`):
    - `CreateCostingSheet` and `UpdateCostingSheet` (header and rows with their base members as one list); `SetCostingSheetRates` (rates of one sheet: add, end-date, remove a future row); `SetSiteCostingSheet`; `CreateCostComponentDetail`, `UpdateCostComponentDetail` and `SetCostComponentDetailMappings`. The version override goes through `UpdateProductionVersion`.
    - **Activity rates** (ADR-0035 rule 17), which had no stated leaf, use `costing_structure` too.
    - **Why `master_data_change`, not `other`.** It follows ADR-0035 rule 17. Estimates never value stock directly, but a released estimate reaches valuation in three places (rule 1), and a configured item's estimate is released with no approval (ADR-0046 rule 14). A rate change can therefore move stock values, as an activity rate can. Class `other` would let an agent change rates without a proposal and would escape a `direct_master_data_change` rule (ADR-0043 rule 12). The estimate commands stay `other` (ADR-0035 rule 14): they compute from these gated inputs.
18. Agents:
    - **Which agents.** No costing agent type exists; ADR-0051 leaves a period-close assistant for later, and it will inherit this rule. The `production` agent type (ADR-0064 rule 1) gains the subject table `costing_sheet`. `product_engineering` estimates with the sheet unchanged (ADR-0062 rule 12).
    - **Drafts only.** The agent drafts sheets, rows, assignments, details and mappings as change proposals (ADR-0029 rules 2, 4); a person submits, and a person other than the human the run acted for approves.
    - **Rates by code only.** A rate enters a proposal only from a person's import batch or note, copied as a stated value with its source (ADR-0051 rule 1; ADR-0062 rule 16), or from `GetCostingRateSuggestion` (module `production`, computed query, `costing_structure` at `read`, field class `cost`): for a surcharge row, the actual pool cost of the credited cost center over the last N closed periods (default 3) ÷ the row's actual base, with its inputs. The model never chooses, sees or writes a rate (the type's field classes stay none).
    - **The variance agent** (`production_variance`, field class `cost`) may read `GetCostCenterAbsorption` to explain absorption gaps.

**Settings, catalogs and DDL**

19. Setting (ADR-0063; leaf `costing_structure`, company scope, change immediate, outdates none): **`production.costing_sheet.required`**, boolean, default false (today's behavior: no sheet, no surcharge); true is tighter and makes a missing sheet the gap `costing_sheet_missing`.
20. Catalog rows and DDL ([DS-43-54-planning-production.sql](../design/DS-43-54-planning-production.sql), owner `production`):
    - **Tables:** `cost_component_detail`, `cost_component_detail_mapping`, `costing_sheet`, `costing_sheet_row`, `costing_sheet_base_member`, `costing_sheet_rate`, `site_costing_sheet`, `cost_estimate_sheet_row`, `production_order_period_cost_detail`. **Columns:** `production_version.costing_sheet_id`; `cost_estimate.costing_sheet_id`; `cost_estimate_line.cost_component_detail_id`, `costing_sheet_row_number`, `credited_cost_center_id` (was `cost_center_id`); `cost_estimate_gap` columns `costing_sheet_id`, `costing_sheet_row_number` and kinds `costing_rate_missing`, `costing_sheet_missing`. **Dropped:** `overhead_surcharge`.
    - **Errors** (DS-04): `costing_sheet_row_invalid`, `costing_rate_overlap` (validation); `cost_component_detail_limit`, `cost_component_detail_in_use` (precondition).
    - **Leaf** `costing_structure` (master data, module `production`); `chief_accountant` and `production_planner` at `edit`.
    - **Event type** `costing_structure_set_up` (DS-17).
    - **Invariants** INV-850 to INV-854 and **edge cases** EC-300 to EC-307, below.
    - **Lab:** [t26_costing_sheet.py](../reviews/2026-11-14-design-validation/lab/t26_costing_sheet.py): the mapping order, the sheet's evaluation (percent and per-unit rows, subtotals, lower levels, selling rows), rate selection and gaps, the roll-up on random estimates, the job's detail split on random two-period orders, the projection's flags; with `--load`, the DDL's keys and checks.

**Later, with a seam**

21. Standard cost valuation, and actual overhead applied by costing sheet with an over- or under-absorption variance, belong to the standard method (estimates with variances, and standard cost valuation if the author chooses it) that ADR-0035 rule 16 lists and leaves to the author. Not designed here. The seam:
    - `evaluate_costing_sheet` is pure over any base, so a job can apply it to actual bases, as `GetCostCenterAbsorption` already does;
    - every surcharge row names its credited cost center and detail, the two keys an absorption posting needs;
    - such a posting would debit the order and credit the pool with the planned absorption, leaving the pool's rest as the variance; that needs a new settlement step, a transaction key, a method value and the author's choice. Nothing in this ADR posts.

    Note (chief architect, 2026-11-21, under the author's delegation of that day; the author's instruction that costing follows SAP): the choice is made. As in SAP, valuation at a standard price is a price-control option beside periodic actual costing (the default, D6), the later ADR decides between SAP's two configurations, standard price with variance postings and no actual costing, or standard price with actual costing, and actual overhead is applied by costing sheet with the over- or under-absorption left as a variance on the pool. This seam is where an ADR after step 5 designs both ([ADR-0035](0035-production-costing.md) rule 16 note; [open-questions.md](../open-questions.md), DS-53 entries). The phase is stated by that ADR: after step 5 and after Phase 1 unless the author moves it, since ADR-0018 rule 3 and spec 09 keep standard price out of Phase 1; until then those hold.

## Context

- **The ask.** The author asked for planned costing that a manufacturer can explain: how overhead enters a cost estimate, on what base and at what rate, and costs that read in more than four buckets, without touching actual costing.
- **What SAP does.** CO-PC's costing sheet (base, overhead rate, credit) prices overhead in cost estimates; the cost component structure maps cost elements to up to 40 components and rolls them into the estimate's split. NativeFlows takes the concept in a simpler form: three row kinds, rates by date and three conditions, one structure per company, 12 details.
- **What exists.** ADR-0035 values at periodic actual with pools, normal capacity and an exact solve; its estimate is a benchmark. ADR-0062 makes a missing price a gap, never zero. ADR-0068 adds sites. ADR-0069's business unit does not change estimates or sheets: they carry no business unit, a credited cost center is used only for reporting, and pool postings keep their derivation. The production cost lines that post carry the unit of the order's output product (ADR-0069 rule 9). (review note, 2026-11-21)
- **Constraints.** No change to postings, settlement keys or INV-106; agents draft only (ADR-0029); one noun per thing (ADR-0004); configurable over hard locks; the core holds no country rules.

## Options considered

| Option | For | Against |
| --- | --- | --- |
| Keep `overhead_surcharge` and add a base column | Small | No per-unit rates, no conditions, no subtotal, no selling rows |
| Costing sheet with three row kinds (chosen) | SAP concept, explainable, one pure function | Five small tables |
| Rates per posting period | Like `activity_rate` | Future quotes need periods that may not exist |
| Rates by effective dates with three conditions (chosen) | Any costing date; deterministic precedence | One exclusion constraint per condition set |
| Detailed component as a key of `production_order_period_cost` | One table | Multiplies solve nodes, settlement keys and rerun differences; touches INV-106 |
| Detail as a pure report-time mapping | No new table | Needs every past period for WIP; a mapping change restates closed periods |
| Detail stamped on estimate lines and written by the job as a read model (chosen) | INV-106 and keys unchanged; history stable; one stored figure | One read model written by the job |
| Receipts at the order's planned cost | Closer to the final cost of one order | Several provisional prices per item and period; issues at a price no receipt carried |
| Receipts at the item's preliminary price, planned shown by a query (chosen) | One provisional price per item and period | The provisional value of one order's receipt can differ from its plan |
| Effect class `other` for sheets and rates | Estimates never value stock | Released estimates reach valuation in three places; agents would bypass proposals |

## Consequences

- **Accounting:** postings, valuation, settlement, INV-106 to INV-108 and the order cost sheet's row source are unchanged.
- **Controllers:** overhead in estimates has a stated base and rate per site, per item group or per valuation class; reports show up to 12 components that sum exactly to the four; the absorption report shows planned against actual per cost center.
- **Sales:** quotes can show cost-plus totals with administration and selling overhead, while cost checks stay on production cost.
- **Managers:** a provisional projected result at completion and planned against preliminary per receipt.
- **Build:** two pure functions (`map_cost_component_detail`, `evaluate_costing_sheet`), nine small tables, five queries, seven commands. Small-model friendly.
- **Revisit when:**
  - the author chooses standard cost valuation or applied overhead (rule 21);
  - a company needs more than 12 detailed components, or a structure per site;
  - quotes need a costing sheet per customer or per sales channel.

## Documents updated

- **ADRs** (notes tagged "ADR-0072, 2026-11-21"): ADR-0033 rule 13; ADR-0035 rules 14, 15, 17; ADR-0046 rule 14; ADR-0062 rule 12; ADR-0063 rule 29; ADR-0064 rule 1.
- **Catalogs:** settings.csv (1), authorization-areas.csv (1), role-template-levels.csv (2), invariants.csv (5), edge-cases.csv (8); the catalogs README.
- **Design:** DS-43-54-planning-production.sql; DS-04 (errors); DS-16 (invariant block and count); DS-17 (event type, edge case block and count); the glossary (new rows only); backlog; the generated overview.
- **Lab:** `t26_costing_sheet.py` and the lab README (finding L-32); fixtures of `t16_planning_production_ddl.py` and `t21_product_engineering.py` seed the default details that estimate lines now name; `t24_settings.py` C12 reads "adds 1 definition" in the singular too.
- **Index and log:** docs/adr/README.md; docs/open-questions.md; docs/runbook/step-log.md.

## Edge cases and invariants

**Invariants** (DS-16; block INV-850 to INV-859, INV-850 to INV-854 taken; first step with the production core):

- **INV-850** `cost_component_detail_default` (area `production`): every company has exactly one active default detailed component per posting component, and every estimate line, mapping row and period cost detail row names a detail of its own posting component.
- **INV-851** `period_cost_detail_sums` (area `production`): for every order, period and posting component, the rows of `production_order_period_cost_detail` sum exactly, in each amount column, to the `production_order_period_cost` row, and each detail's opening equals its closing of the order's previous period with costs.
- **INV-852** `estimate_without_selling_rows` (area `production`): every released estimate's lines sum to its `company_amount`, and its level 0 surcharge lines and sheet-row snapshot come only from `production` rows of the sheet it names. Rolled-up lines of made components (level above 0) keep the row number of the component's own estimate and are covered by that estimate's snapshot. (review note, 2026-11-21)
- **INV-853** `estimate_surcharge_rated` (area `production`): every production surcharge row of a released estimate's sheet has a snapshot row whose rate is the one rule 7 selects on the costing date.
- **INV-854** `costing_structure_by_proposal` (area `safety`): no audit row of a costing-structure command (rule 17) carries an origin agent run, except the execution of an approved change proposal.

**Edge cases** (DS-17; block EC-300 to EC-309, EC-300 to EC-307 taken):

- **EC-300** `costing_sheet_rows`: a sheet with base rows for material and conversion, a 10% material overhead, an amount per machine hour, an amount per output unit and a subtotal; the estimate's surcharge lines land in their details and credit their cost centers; the lines sum to the total.
- **EC-301** `costing_rate_conditions`: rates for the sheet with no condition, for an item group, and for a site and that item group; an item of the group at that site takes the third, another site the second, another group the first.
- **EC-302** `costing_rate_missing_gap`: a percent row without a valid rate on the costing date gives `costing_rate_missing`; the total leaves it out, the estimate is not released (`cost_estimate_incomplete`); a stored rate 0 is no gap.
- **EC-303** `selling_rows_quote_only`: administration and selling rows appear in `GetSellingPriceCosting` for a quotation, never in the released estimate, the preliminary price or the below-cost check.
- **EC-304** `version_sheet_override`: a production version with its own sheet costs with it, another version of the site with the site's; with `production.costing_sheet.required` true, a site without a sheet gives `costing_sheet_missing`.
- **EC-305** `detail_rollup_two_periods`: an order open across a period end with raw material, packaging, labor and an unmapped overhead account; the detail rows sum exactly to the four components in both periods, the unmapped cost lands in the default overhead detail, and the second period opens with the first's closing split.
- **EC-306** `projected_cost_at_completion`: an order completed in a period without receipts shows its projected final cost with the period's cost as projected residual; after a reopen and a further receipt the projection is in progress again; after the run it equals the settled actuals and is no longer provisional.
- **EC-307** `agent_drafts_costing_sheet`: the production agent's direct `SetCostingSheetRates` is refused with `proposal_required`; its proposal, with rates from `GetCostingRateSuggestion`, executes after a person approves.
