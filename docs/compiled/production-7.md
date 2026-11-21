Module: production    Chunk: 7 of 7    Source ADRs: ADR-0071, ADR-0072
Build step(s): 5    Generated from index: 30d5706    Compiled by: Claude Opus 5.5, 2026-11-21

# `production` compiled spec, chunk 7: shop-floor effect classes and catalog, costing sheet and cost component structure

## Purpose

`production` (layer 3, ADR-0022.R2) owns production master data, production orders and shop floor, production costing
and subcontracting. This chunk states the effect classes, blocked work orders, settings and catalog rows of ADR-0071
rules 17 to 20, and the planned-costing structures of ADR-0072: detailed cost components and their mapping, the costing
sheet, selling-price costing, absorption and projected-cost queries, and the costing milestones of an order. As owner of
the rest it also carries the table, invariant and edge-case rows of `production` that no rule of chunks 1 to 7 names.
The external ID map of ADR-0074.R7 is `master_data` law, traced `ref:`.

## Entities and tables

DDL: `docs/design/DS-43-54-planning-production.sql`.

| Table | Meaning | Key | Parent | Owner |
| --- | --- | --- | --- | --- |
| `cost_component_detail` | Detailed cost component, company data: `code`, `name`, `cost_component`, `sequence`, `is_default`, `is_active` (R1215-R1217) | `id`; unique (`company_id`, `code`); unique (`company_id`, `id`, `cost_component`) | `company` | `production` |
| `cost_component_detail_mapping` | One source (`source_kind` `activity_type`, `item_group`, `valuation_class` or `account`) mapped to a detail (R1220) | `id`; unique source per (`company_id`, `cost_component`) | `cost_component_detail` | `production` |
| `costing_sheet` | Costing sheet header, company data: `code`, `name`, `is_active` (R1230) | `id`; unique (`company_id`, `code`) | `company` | `production` |
| `costing_sheet_row` | Ordered row of a sheet: `row_kind` `base`, `surcharge` or `subtotal`, `usage` (R1230-R1233) | `id`; unique (`costing_sheet_id`, `row_number`) | `costing_sheet` | `production` |
| `costing_sheet_base_member` | A posting component or a detail that a base row reads (R1230) | `id`; unique (`costing_sheet_id`, `cost_component`, `cost_component_detail_id`) | `costing_sheet_row` | `production` |
| `costing_sheet_rate` | Rate of a surcharge row by dates and optional conditions (R1235) | `id`; exclusion `ex_costing_sheet_rate_overlap` | `costing_sheet_row` | `production` |
| `site_costing_sheet` | The costing sheet of a site (R1245) | `id`; unique (`site_id`) | `costing_sheet` | `production` |
| `cost_estimate_sheet_row` | Snapshot of each evaluated production row of an estimate (R1242) | `id`; unique (`cost_estimate_id`, `row_number`) | `cost_estimate` | `production` |
| `production_order_period_cost_detail` | Read model per order, period and detail with the six amounts of its parent (R1226, R1227) | `id`; unique (`production_order_id`, `posting_period_id`, `cost_component_detail_id`) | `production_order_period_cost` | `production` |
| `production_order_operation_activity` | Activity standard (`activity_type_id`, `quantity`, `basis` `per_order` or `per_base_quantity`) copied with an order operation; no rule of the chunks names it (DDL: ADR-0034 rule 1) | `id`; unique (`production_order_operation_id`, `activity_type_id`) | `production_order_operation` | `production` |

Columns added by this chunk's rules to tables whose rows stand in other chunks: `production_version.costing_sheet_id`
(R1245); `cost_estimate.costing_sheet_id` (R1242); `cost_estimate_line.cost_component_detail_id`,
`costing_sheet_row_number` and `credited_cost_center_id` (R1225, R1241, R1250); `cost_estimate_gap.costing_sheet_id`,
`costing_sheet_row_number` and the kinds `costing_rate_missing`, `costing_sheet_missing` (R1266);
`activity_type.time_log_basis`, `operation_confirmation.work_center_id`, `operation_confirmation_activity.proposed_quantity`,
`production_receipt.scrap_quantity` and `scrap_reason_id` (R1206). Named here, rows in other chunks: `stop_reason`,
`operation_execution`, `operation_assignment`, `operation_time_log`, `operation_confirmation_time_log`, `cost_estimate`,
`cost_estimate_line`, `cost_estimate_gap`, `production_order_period_cost`, `production_cost_settlement`,
`production_cost_settlement_line`, `activity_rate`, `production_issue`, `production_receipt`, `operation_confirmation`,
`production_structure`.

Reads: `cost_center`, `site`, `item_group`, `valuation_class`, `account`, `activity_type`, `journal_line`,
`posting_period`, `work_case`, `external_id_map` (`master_data`, ADR-0074.R7).

## Commands and queries

| Name | Actor and authorization | Input | Effect | Events | Error codes |
| --- | --- | --- | --- | --- | --- |
| `CreateCostingSheet` | `master_data_change`, change-tracked, `is_proposal_bound`; leaf `costing_structure` at `edit` | header and rows with their base members as one list; optional `expected_version` | Creates a costing sheet (R1230, R1260) | not stated | `costing_sheet_row_invalid` |
| `UpdateCostingSheet` | as `CreateCostingSheet` | header and rows with their base members as one list; optional `expected_version` | Replaces the sheet's rows (R1230, R1260) | not stated | `costing_sheet_row_invalid` |
| `SetCostingSheetRates` | as `CreateCostingSheet` | rates of one sheet: add, end-date, remove a future row | Writes `costing_sheet_rate` (R1235, R1260) | not stated | `costing_rate_overlap`; `proposal_required` for an agent outside a proposal (`EC-307`) |
| `SetSiteCostingSheet` | as `CreateCostingSheet` | site, sheet | Writes `site_costing_sheet` (R1245, R1260) | not stated | not stated |
| `CreateCostComponentDetail` | as `CreateCostingSheet` | `code`, `name`, `cost_component`, `sequence` | Creates a detail (R1215, R1260) | not stated | `cost_component_detail_limit` |
| `UpdateCostComponentDetail` | as `CreateCostingSheet` | a detail | Changes a detail (R1216, R1217, R1260) | not stated | `cost_component_detail_limit`, `cost_component_detail_in_use` |
| `SetCostComponentDetailMappings` | as `CreateCostingSheet` | mapping rows | Writes `cost_component_detail_mapping` (R1220, R1260) | not stated | not stated |
| `GetSellingPriceCosting` | computed query; `report_production` at `read`; field class `cost` | item or configurable product with item-defining values, quantity, date, optional site | Selling-price costing with purpose `selling`; stores and posts nothing (R1247) | none | none stated; gaps returned |
| `GetCostCenterAbsorption` | computed query; `report_production` at `read`; field class `cost` | cost center, period | Actual against planned absorption (R1252) | none | none stated |
| `GetProductionReceiptValuation` | computed query; `report_production` at `read`; field class `cost` | receipt | Planned against preliminary value per receipt line (R1254) | none | none stated |
| `GetProductionOrderProjectedCost` | computed query; `report_production` at `read`; field class `cost` | order | Projected final cost; stores and posts nothing (R1256) | none | none stated; gaps returned |
| `GetCostingRateSuggestion` | computed query; `costing_structure` at `read`; field class `cost` | surcharge row | Suggested rate with its inputs (R1263) | none | none stated |

The production version's override goes through `UpdateProductionVersion` (R1260). Activity rates use the leaf
`costing_structure` (R1261). The reports `GetCostEstimate`, `GetProductionOrderVariance` and
`ListProductionOrderVarianceDriver` of other chunks gain the detail (R1229). DS-17 event type of this chunk:
`costing_structure_set_up` (R1267).

Not commands: the pure functions `production.map_cost_component_detail` (R1221) and `production.evaluate_costing_sheet`
(R1240), the function `estimate_configuration` with its `purpose` parameter (R1248), the period-end costing job that
writes `production_order_period_cost_detail` (R1226, R1258), and the system job `CloseProductionOrder` (R1255).

Error codes of ADR-0071.R20 raised by the shop-floor commands of chunk 6: `operation_not_ready`, `operation_done`,
`operation_already_started`, `work_center_not_in_resource_group`, `operation_time_log_open`, `time_log_already_confirmed`,
`stop_reason_required`, `receipt_scrap_not_allowed`; check result `operation_waiting` (R1207).

## Rules

### Shop-floor execution: effect class, actors, blocked WOs, settings and catalog

R1201. The state, assignment, transfer and time-log commands of shop-floor execution change no stock, value or books and send nothing out, so they are effect class `other`. They are not proposal-bound: a wrong start or pause costs nothing until a person posts a confirmation.
Source: ADR-0071.R17

R1202. Integrations (machine signals) run `StartOperation` and `PauseOperation` as actor `integration` with a credential holding `shop_floor_execution` at `edit`; their logs are `recorded` with `entry_source` `integration`, and still only propose.
Source: ADR-0071.R17

R1203. A tainted agent run may run only `CreateOperationTimeLog` and `UpdateOperationTimeLog` (drafts) and the confirmation drafts of ADR-0064.R19; a person confirms the logs and posts the confirmation. An untainted agent may start and pause by class, but no Phase 1 tool list holds these commands (ADR-0050.R30).
Source: ADR-0071.R17

R1204. `BlockOperation` raises the work item `operation_blocked` (subject the operation, owner `role:shop_floor_lead`, due one day, resolution `system`), closed when the WO leaves `blocked`. The work case kind `production_disruption` (ADR-0066.R3) has it as trigger, so `work_case.production_disruption.mode` `auto` opens a case that groups the WO, its stop logs, the work items and the documents made about it.
Source: ADR-0071.R18

R1205. Settings of shop-floor execution (ADR-0063; leaf `production_structure`, company scope, change immediate, outdates none): `production.operation.start_when_waiting` is `warn` (default) or `reject`; `production.operation.stop_reason_on_pause` is a boolean, default false, and true is tighter.
Source: ADR-0071.R19

R1206. Catalog rows and DDL of shop-floor execution (`DS-43-54-planning-production.sql`, owner `production`): the tables `stop_reason`, `operation_execution`, `operation_assignment`, `operation_time_log` and `operation_confirmation_time_log`; the columns `activity_type.time_log_basis`, `operation_confirmation.work_center_id`, `operation_confirmation_activity.proposed_quantity`, and `production_receipt.scrap_quantity` and `scrap_reason_id` (ADR-0074.R14).
Source: ADR-0071.R20

R1207. The verbs Pause and Block are new (level `edit`); Start, Assign and Transfer widen their intent. The errors are `operation_not_ready`, `operation_done`, `operation_already_started`, `work_center_not_in_resource_group`, `operation_time_log_open`, `time_log_already_confirmed`, `stop_reason_required` and `receipt_scrap_not_allowed`; the check result is `operation_waiting`.
Source: ADR-0071.R20

R1208. The leaf `shop_floor_execution` (function, area `production`) grants `shop_floor_lead` at `post` and `production_planner` at `read`. The work item kind is `operation_blocked`, the work case kind `production_disruption`; the invariants are `INV-840` to `INV-845` and the edge cases `EC-290` to `EC-297`.
Source: ADR-0071.R20

### Costing structure: scope

R1211. The costing sheet serves planned costing only. Actual costing of ADR-0035 stays as it is: the order cost sheet's row source `production_order_period_cost`, actual overhead through cost-center pools at normal capacity, and variance analysis. The sheet prices `cost_estimate` (draft and released, configured items' estimates included, ADR-0035.R14, ADR-0046.R14), `estimate_configuration` and `GetConfigurationEstimate` (ADR-0046.R14), selling-price costing (R1247), the projected final cost (R1256) and the absorption report (R1252). Planned costing has explicit milestones: partial receipts at the preliminary price, a non-posting projected final cost at completion, and the period-end order of ADR-0035 with what becomes final (R1253-R1259).
Source: ADR-0072.R1, ADR-0072.D0

R1212. The costing sheet values no stock and posts nothing; actual overhead stays with the pools of ADR-0035.R7. Where a released estimate already reaches valuation it still does, unchanged and only with its production rows: the preliminary price of a produced item without history (ADR-0035.R4, ADR-0020.R11), `planned_cost` WIP (ADR-0035.R9) and the disassembly split (ADR-0035.R13). ADR-0035 rules 2 to 13 and 16, the row source `production_order_period_cost` and a localization package's book over it are unchanged.
Source: ADR-0072.R1

### Detailed cost components

R1215. `cost_component_detail` is company data of `production` with the columns `code`, `name`, `cost_component` (`material`, `labor`, `overhead` or `other`, the posting component it rolls up to), `sequence` (report order), `is_default` and `is_active`. `CreateCompany` seeds four rows, coded as the posting components, with `is_default` true. Each company has exactly one active default per posting component (`INV-850`); a default is never deactivated and never changes component. A company that defines nothing more sees the four posting components.
Source: ADR-0072.R2

R1216. A company has at most 12 active `cost_component_detail` rows, the defaults included (`cost_component_detail_limit`); finer analysis belongs to accounts and activity types, which the detail is mapped from. An example set, not seeded: `raw_material` and `packaging` (material); `direct_labor` (labor); `machine`, `energy`, `depreciation` and `overhead` (overhead); `subcontracting` (other).
Source: ADR-0072.R2

R1217. Once an estimate line or a period cost detail row names a detail, its `cost_component` cannot change (`cost_component_detail_in_use`).
Source: ADR-0072.R2

R1220. `cost_component_detail_mapping` (company data, `production`) rows hold a detail and one source: `activity_type`, `item_group`, `valuation_class` or `account` (an operational account). The row carries its detail's posting component through a composite key, and one source maps to at most one detail per posting component (a unique key), so the mapping is a function.
Source: ADR-0072.R3

R1221. `production.map_cost_component_detail(company, cost_component, activity_type, item_group, valuation_class, account)` is pure. It looks only among details of the given posting component, in the order activity type, item group, valuation class, account; the first hit wins; no hit gives the component's default. Activity type comes first so that planned activity cost in an estimate and actual cost allocated by the same activity land in the same detail; the account comes last, for pool cost allocated by a constant basis.
Source: ADR-0072.R3

R1222. The mapping function never leaves the line's posting component, so no amount moves between the four posting components, leaves, keys or pools; postings are unchanged.
Source: ADR-0072.R3

R1223. Facts passed to the mapping per line:
- estimate material line; issue, return and their revaluation: the item's group and valuation class, and the line's account (no consumer-split share exists, ADR-0021.R7.N1);
- estimate activity line: the activity type;
- pool allocation (ADR-0035.R7): the allocation rule's activity type when the driver is one, and the source line's account;
- external service on `production_cost_other`: the service item's group when it has one, and the account;
- abnormal cost (ADR-0035.R10): its component line's item, or its activity type;
- estimate surcharge line: none, its row names the detail (R1231).
Source: ADR-0072.R3

R1225. In estimates the detail is stored in `cost_estimate_line.cost_component_detail_id`, NOT NULL, stamped when the estimate is computed and frozen with it; a composite key holds it to the line's `cost_component`.
Source: ADR-0072.R4

R1226. For order actuals, `production_order_period_cost` and `production_cost_settlement_line` keep their keys, so `INV-106`, ADR-0035.R5's settlement keys and reruns are unchanged. The period-end job writes, in the same transaction, the read model `production_order_period_cost_detail`: one row per order, period and detail, with the same six amounts; a rerun rewrites it with its parent. No detailed key is added to `production_order_period_cost`, because the solve, the WIP methods and `INV-106` work per posting component (ADR-0035.R6, ADR-0035.R9). The detail is stored, not mapped at report time, because WIP carried between periods needs the previous period's split, a mapping change would restate closed periods, and the analysis layer reads one stored figure (ADR-0060.R19); the same function still maps journal and document lines at report time for drill-down (R1229).
Source: ADR-0072.R4

R1227. The split of `production_order_period_cost_detail`: opening is the detail's closing of the order's previous period with costs (with none, the default detail takes the parent's opening). Incurred and abnormal: each line by R1221. Residual and closing: the parent's amounts split in proportion to each detail's available amount (opening + incurred − abnormal) by largest remainder, ties by `sequence`, then `code`; when the component's available amount is 0, both go to the default detail. To-output: the rest per detail. Every column sums exactly to the parent (`INV-851`), and each row balances like its parent.
Source: ADR-0072.R4

R1228. The actual cost component split through stock (SAP's carrying of the standard estimate's split through actual costing across levels) is a seam in Phase 1, not built; the split stops at the order. The later feature carries values per posting component through the stock nodes of ADR-0020.R12's solve as extra right-hand sides of the same system, stores them as a read model per item, valuation area, period and component, and starts at a period start with an opening split taken from purchase (all `material`) or from the released estimate's components; nothing posted changes, so Phase 1 needs no column for it.
Source: ADR-0072.R4.N1

R1229. Reports by detail: `GetCostEstimate` shows lines by detail and the costed sheet rows (R1242). The order cost report (DS-26) and `GetProductionOrderVariance` take an optional grouping `cost_component_detail`: target per detail from the estimate's lines, scaled as ADR-0035.R15 says; actual from `production_order_period_cost_detail`; the variance categories are unchanged. `ListProductionOrderVarianceDriver` (ADR-0064.R10) gives each driver row its detail through R1221. `production_order_variance` (ADR-0060.R19) stays per category, without a detail column. A book definition over `production_order_period_cost` may group by detail; that choice belongs to its package.
Source: ADR-0072.R5

### Costing sheet

R1230. `costing_sheet` (company data, `production`: `code`, `name`, `is_active`) has ordered `costing_sheet_row` rows (`row_number`, positive; `row_kind`; `label`; `usage`). A `base` row's members (`costing_sheet_base_member`) are posting components or detailed components. It reads the estimate's priced lines (material, activity, external service), never surcharge lines. Each priced line counts in at most one base row of a sheet (members disjoint, `costing_sheet_row_invalid`); a line no base row covers stays in the total and bears no surcharge. `is_lower_level_included` (default false): false takes only the version's own lines (level 0); true also the lines rolled up from made components.
Source: ADR-0072.R6

R1231. A `surcharge` row has a `surcharge_kind`: `percent` of `base_row_number`, an earlier base or subtotal row; `per_output_unit`, an amount per unit of the costing lot quantity in the output's inventory unit; or `per_activity_unit`, an amount per unit of `activity_type_id` over the estimate's own activity quantities of that type. It names `credited_cost_center_id`, the cost center credited for planned-versus-absorbed reporting only (R1252). A `production` surcharge row names `cost_component_detail_id`, the detail it lands in, whose posting component is `labor`, `overhead` or `other`, never `material`, because material is issued items (ADR-0035.R2); material handling overhead is an overhead detail.
Source: ADR-0072.R6

R1232. A `subtotal` row sums the base and surcharge rows from `from_row_number` to `to_row_number`, both earlier rows; subtotals inside the range are skipped, so nothing counts twice.
Source: ADR-0072.R6

R1233. `usage` is `production` (default) or `selling` (administration and selling overhead). Only surcharge and subtotal rows may be `selling`; a selling surcharge credits a cost center of kind `administration` or `selling` and names no detail; a production row never refers to a selling row. The sheet has no overhead keys, credit keys or origin groups: conditions on rates (R1236) and the detail on the row do that work.
Source: ADR-0072.R6

R1235. `costing_sheet_rate` holds sheet and row; `valid_from` and `valid_to` (inclusive, open end allowed); optional conditions `site_id`, `item_group_id` and `valuation_class_id`; `rate_percent` for percent rows and `rate_amount` (company currency per unit) for per-unit rows, the kind carried by a composite key. Rates of one sheet, row and condition set never overlap (an exclusion constraint, `costing_rate_overlap`).
Source: ADR-0072.R7

R1236. A rate is selected on the costing date (estimates, projections) or the document date (selling costing): among valid rows whose stated conditions all match the costed output (the site of the version's production warehouse, ADR-0068.R10; the output item's item group; its valuation class), the most specific wins by fixed precedence: site, then item group, then valuation class, compared as a three-digit binary number. No tie can remain, because the exclusion constraint forbids two valid rows with the same condition set.
Source: ADR-0072.R7

R1237. A stored rate 0 is a real zero. No valid rate row gives the gap `costing_rate_missing`, left out of the total and never zero (ADR-0062.R12).
Source: ADR-0072.R7

R1238. Rates run by dates, not periods, because quotes and estimates cost future dates whose posting periods may not exist yet; a period's rate is a date range. `activity_rate` stays per period (ADR-0035.R17).
Source: ADR-0072.R7

R1240. `production.evaluate_costing_sheet(priced lines, sheet, rates, purpose, context)` is a pure function. It evaluates rows in `row_number` order. A base row's value is the sum of its rounded lines. Percent: `round_amount(base × rate ÷ 100)`; per unit: `round_amount(quantity × rate)` (ADR-0006.R18). Subtotals add. Purpose `production` evaluates production rows only; `selling` evaluates all rows (R1247).
Source: ADR-0072.R8

R1241. Each production surcharge row with a rate writes one `cost_estimate_line`: `cost_component` from its detail, `cost_component_detail_id`, `costing_sheet_row_number`, `credited_cost_center_id`, quantity (the base amount, or the units), price (the rate) and amount. A row whose value is 0 (a stored zero rate or an empty base) writes no line; its snapshot row still shows it.
Source: ADR-0072.R8

R1242. `cost_estimate_sheet_row` keeps each evaluated production row (kind, label, base amount, rate, amount), so the sheet as costed survives later edits of the sheet. `cost_estimate.costing_sheet_id` names the sheet used.
Source: ADR-0072.R8

R1243. Each estimate applies its own version's sheet. Rolled-up lines of made components keep their details and their own surcharge lines; per-unit rows count level 0 only. With a gap, surcharges are computed on the priced lines; the estimate is incomplete and cannot be released anyway (ADR-0062.R12).
Source: ADR-0072.R8

R1244. For `planned_cost` WIP (ADR-0035.R9), a percent or per-activity surcharge line counts with the share of its base row's planned cost that lies up to the last confirmed operation; a per-output-unit line counts once the last operation is confirmed.
Source: ADR-0072.R8

R1245. A site's costing sheet is `site_costing_sheet` (site, sheet), owned by `production`, because `master_data` may not refer to a production table (ADR-0022.R2). `production_version.costing_sheet_id`, optional, overrides the site's sheet; for a configurable product, the product-level version's applies (ADR-0046.R12). Overhead rates differ by plant; the version override covers a line with its own cost structure.
Source: ADR-0072.R9

R1246. The sheet of an estimate is the version's override, else the sheet of its production warehouse's site, else none. With none, the estimate has no surcharge lines; when `production.costing_sheet.required` is true, it has the gap `costing_sheet_missing`.
Source: ADR-0072.R9

R1247. `GetSellingPriceCosting` (module `production`, computed query, `report_production` at `read`, field class `cost`) takes an item or a configurable product with item-defining values, a quantity, a date and an optional site. It takes the released estimate valid on the date (ADR-0035.R14 note), or `estimate_configuration` for values without an item, and evaluates the current sheet with purpose `selling` over its priced lines at the date's rates. It returns the rows, the cost of goods manufactured (production rows), administration and selling, the total cost and any gaps. It is never stored and posts nothing.
Source: ADR-0072.R10

R1248. `estimate_configuration` takes `purpose` as a function parameter, default `production`: it is a pure function of `production.contract` with no table, so nothing is added to a schema.
Source: ADR-0072.R10

R1249. The below-cost and margin checks (ADR-0043.R3, ADR-0045.R5, ADR-0046.R14) never include selling rows: the floor protects what will post to cost of goods sold, and a cost-plus markup is a pricing choice for price lists and policy rules. A selling row never writes a `cost_estimate_line` (`INV-852`), so it never reaches a preliminary price, WIP or a variance.
Source: ADR-0072.R10

R1250. No `overhead_surcharge` table exists. A planned surcharge per cost center (ADR-0035.R14) is a percent surcharge row crediting that cost center, its percent a rate whose dates cover the period, on a base row the company states; there is no data to migrate (design only). The estimate line column is `credited_cost_center_id`, set exactly on surcharge lines (with `costing_sheet_row_number`) and nowhere else; the DDL carries no interim marker for either.
Source: ADR-0072.R11

### Absorption, receipts and order milestones

R1252. `GetCostCenterAbsorption` (module `production`, computed query, `report_production` at `read`, field class `cost`) reports per cost center and period: actual, the pool's cost (journal lines), what the job allocated to orders and what went unabsorbed (settlement lines; ADR-0035.R7); planned absorption, the production surcharge rows that credit the cost center applied to the period's actual bases at the rates valid on the period's last day (incurred amounts per detail from `production_order_period_cost_detail`, activity quantities from posted confirmations, output from net receipts); and the difference, which a standard-cost system would post as over- or under-absorption and which is reported only (R1268).
Source: ADR-0072.R12

R1253. A partial output receipt during the order posts at the item's preliminary price (ADR-0035.R4, ADR-0020.R11) and is revalued at period end; the order's estimate does not price it. Under periodic average there is one price per item, valuation area and period for every movement of the item, so receipts and issues of the same item in the period carry the same provisional unit value and period end revalues only differences; NativeFlows has no moving price.
Source: ADR-0072.R13

R1254. `GetProductionReceiptValuation` (module `production`, computed query, `report_production` at `read`, field class `cost`) shows per receipt line: quantity, the preliminary unit price and value posted, the order's planned unit cost (the target of ADR-0035.R15 per unit; co-products by `cost_coefficient`), the difference and its percent, `is_provisional` until the receipt's period is settled, then the settled value too. It posts nothing.
Source: ADR-0072.R13

R1255. Order completion and close: technical completion stops logistics and WIP (ADR-0034.R6, ADR-0035.R10). Abnormal cost is assessed once, over the whole order, by the next period-end run (ADR-0035.R10). The final actual cost is known only after the run of the period that holds the completion, because pools and actual prices are periodic (ADR-0035 rules 5 to 7). The close job closes the order after that settlement and the inventory area's lock (ADR-0034.R7).
Source: ADR-0072.R14

R1256. `GetProductionOrderProjectedCost` (module `production`, computed query, `report_production` at `read`, field class `cost`; it posts and stores nothing) is available at any time and meant for completion:
- settled periods: the actual amounts of `production_order_period_cost` (final);
- unsettled postings: net issued quantities × the current preliminary price of the item and area; confirmed activity quantities × the `activity_rate` of the execution work center for the business date's period; external service costs as posted; overhead from the order's costing sheet (production rows, rates on the business date) on these bases, since pools are known only at period end;
- less the by-product value, and the projected abnormal cost by ADR-0035.R10's formula on cumulative quantities;
- per unit over cumulative good receipts (co-products by coefficient), against the target cost, by component and by detail;
- what it cannot price is a gap, never zero;
- `is_provisional` is false only when the order is technically complete and every period with its postings is settled; the result then equals the stored actuals.
Source: ADR-0072.R14

R1257. When an order is completed in a period with no receipt, the unsettled cost of that period is shown as projected residual (ADR-0035.R10: it goes to cost of goods sold, and earlier receipts keep their value), not as cost to output. `ReopenProductionOrder` returns the order to `in_progress` (ADR-0034.R6), and the next run reverses the abnormal assessment (ADR-0035.R10); the projection is computed on each call, so it shows an order in progress, with nothing stored to undo.
Source: ADR-0072.R14

R1258. Period end follows the job order of ADR-0035.R12 (issue revaluation, pool allocation, unabsorbed overhead, abnormal cost, residual, WIP transfer, receipt revaluation). What becomes final: the period's actual prices, allocations at normal capacity, revalued issues and receipts, abnormal and residual cost, and each order's closing WIP per component, in `production_order_period_cost` and `production_order_period_cost_detail`. Closing WIP per component is the next period's opening (ADR-0035.R8, ADR-0035.R9); the detail split follows it (R1227). A reopened and re-solved period posts only differences per key (ADR-0035.R5, ADR-0012.R15); the read models are rewritten. A later posting into the period makes the job stale (ADR-0035.R3).
Source: ADR-0072.R15

R1259. Costing timeline of an order:
- issue or return, `production_issue`: the item's preliminary price; debit `production_cost_material` (order), credit inventory; provisional; the user sees order cost so far and the projected final cost;
- confirmation, `operation_confirmation`: no price (quantities); no posting; quantities final, their cost at period end; projected final cost at planned rates and sheet;
- partial receipt, `production_receipt`: the item's preliminary price; debit inventory, credit WIP (order); provisional; `GetProductionReceiptValuation`, planned against preliminary;
- technical completion, `CompleteProductionOrder`: no price; no posting, WIP stops and abnormal cost waits for the run; provisional; `GetProductionOrderProjectedCost`;
- period end, costing job and `production_cost_settlement`: period actual average and pools at normal capacity; the seven steps of ADR-0035.R12; final for the period unless reopened and solved again; `production_order_period_cost` and its detail, variance, absorption;
- close, `CloseProductionOrder` (system job): no price; no posting (cost postings still allowed on a rerun); final; order cost report and variance.
Source: ADR-0072.R16

### Commands, agents, setting and catalog of the costing structure

R1260. The costing-structure commands (module `production`, effect class `master_data_change`, change-tracked, `is_proposal_bound`, with the optional `expected_version` of ADR-0029.R2; leaf `costing_structure` at `edit`) are `CreateCostingSheet` and `UpdateCostingSheet` (header and rows with their base members as one list), `SetCostingSheetRates` (rates of one sheet: add, end-date, remove a future row), `SetSiteCostingSheet`, `CreateCostComponentDetail`, `UpdateCostComponentDetail` and `SetCostComponentDetailMappings`. The version override goes through `UpdateProductionVersion`.
Source: ADR-0072.R17

R1261. Activity rates (ADR-0035.R17) use the leaf `costing_structure` too. The class is `master_data_change`, as in ADR-0035.R17, because a released estimate reaches valuation in three places (R1212) and a configured item's estimate is released with no approval (ADR-0046.R14), so a rate change can move stock values; class `other` would let an agent change rates without a proposal and escape a `direct_master_data_change` rule (ADR-0043.R12). The estimate commands stay `other` (ADR-0035.R14): they compute from these gated inputs.
Source: ADR-0072.R17

R1262. No costing agent type exists; a period-close assistant (ADR-0051) is left for later and will inherit this rule. The `production` agent type (ADR-0064.R1; Phase 2 with mode `off`, ADR-0078.R2) gains the subject table `costing_sheet`; `product_engineering` estimates with the sheet unchanged (ADR-0062.R12). An agent drafts sheets, rows, assignments, details and mappings only as change proposals (ADR-0029.R2, ADR-0029.R4); a person submits, and a person other than the human the run acted for approves.
Source: ADR-0072.R18

R1263. A rate enters a proposal only from a person's import batch or note, copied as a stated value with its source (ADR-0051.R1, ADR-0062.R16), or from `GetCostingRateSuggestion` (module `production`, computed query, `costing_structure` at `read`, field class `cost`): for a surcharge row, the actual pool cost of the credited cost center over the last N closed periods (default 3) ÷ the row's actual base, with its inputs. The model never chooses, sees or writes a rate (the type's field classes stay none).
Source: ADR-0072.R18

R1264. The variance agent (`production_variance`, field class `cost`; Phase 2, ADR-0078.R2) may read `GetCostCenterAbsorption` to explain absorption gaps.
Source: ADR-0072.R18

R1265. Setting (ADR-0063; leaf `costing_structure`, company scope, change immediate, outdates none): `production.costing_sheet.required`, boolean, default false (no sheet, no surcharge); true is tighter and makes a missing sheet the gap `costing_sheet_missing`.
Source: ADR-0072.R19

R1266. Catalog rows and DDL of the costing structure (`DS-43-54-planning-production.sql`, owner `production`): the tables `cost_component_detail`, `cost_component_detail_mapping`, `costing_sheet`, `costing_sheet_row`, `costing_sheet_base_member`, `costing_sheet_rate`, `site_costing_sheet`, `cost_estimate_sheet_row` and `production_order_period_cost_detail`; the columns `production_version.costing_sheet_id`, `cost_estimate.costing_sheet_id`, `cost_estimate_line.cost_component_detail_id`, `costing_sheet_row_number` and `credited_cost_center_id`, and `cost_estimate_gap` columns `costing_sheet_id` and `costing_sheet_row_number` with the kinds `costing_rate_missing` and `costing_sheet_missing`; `overhead_surcharge` is dropped.
Source: ADR-0072.R20

R1267. The errors (DS-04) are `costing_sheet_row_invalid` and `costing_rate_overlap` (validation), `cost_component_detail_limit` and `cost_component_detail_in_use` (precondition). The leaf `costing_structure` (master data, module `production`) grants `chief_accountant` and `production_planner` at `edit`. The event type is `costing_structure_set_up` (DS-17). The invariants are `INV-850` to `INV-854` and the edge cases `EC-300` to `EC-307`. The lab `t26_costing_sheet.py` checks the mapping order, the sheet's evaluation (percent and per-unit rows, subtotals, lower levels, selling rows), rate selection and gaps, the roll-up on random estimates, the job's detail split on random two-period orders and the projection's flags; with `--load`, the DDL's keys and checks.
Source: ADR-0072.R20

R1268. Standard cost valuation, and actual overhead applied by costing sheet with an over- or under-absorption variance, belong to the standard method of ADR-0035.R16. The choice is made, as in SAP: valuation at a standard price is a price-control option beside periodic actual costing (the default, D6); a later ADR decides between SAP's two configurations (standard price with variance postings and no actual costing, or standard price with actual costing), and actual overhead is applied by costing sheet with the over- or under-absorption left as a variance on the pool. That ADR designs both after step 5 and after Phase 1 unless the author moves it, since ADR-0018.R3 and spec 09 keep standard price out of Phase 1; until then those hold. The seam: `evaluate_costing_sheet` is pure over any base, so a job can apply it to actual bases, as `GetCostCenterAbsorption` does; every surcharge row names its credited cost center and detail, the two keys an absorption posting needs; such a posting would debit the order and credit the pool with the planned absorption, leaving the pool's rest as the variance, and needs a new settlement step, a transaction key and a method value. Nothing here posts.
Source: ADR-0072.R21, ADR-0072.R21.N1

## Invariants

Statements are those of `invariants.csv`. A row stands in the chunk holding the rule its catalog source names; this chunk holds the rows of ADR-0072 and those whose source is no rule of chunks 1 to 7. All have check point `day` except `INV-851` (`run`).

| ID | Name | Check point | Statement | Protects |
| --- | --- | --- | --- | --- |
| `INV-109` | `planned_components_match_function` | day | Each proposed, frozen or firmed planned production order's `planned_order_component` rows equal `plan_production` at its stored version, dates and quantity. | ADR-0036.R14 |
| `INV-110` | `converted_planned_order_inert` | day | A converted production planned order contributes no supply or dependent demand to the latest run. | ADR-0036.R14 |
| `INV-113` | `configured_lines_complete` | day | Every non-draft line of a configurable product on a document of an `is_item_creating` type, and every stock document line of one, names a complete configuration and an item whose variant values equal the configuration's item-defining values; a non-draft quotation line names a complete configuration, and an item only when one with those values exists. | ADR-0046.R18 |
| `INV-114` | `configuration_hash_matches` | day | Every `product_configuration`'s `content_hash` equals the hash of its stored values. | ADR-0046.R18 |
| `INV-115` | `structure_conditions_item_defining` | day | Every component and operation condition and sizing of a product-level structure names only item-defining characteristics of its product. | ADR-0046.R18 |
| `INV-850` | `cost_component_detail_default` | day | Every company has exactly one active default detailed cost component per posting component, and every estimate line, mapping row and period cost detail row names a detail of its own posting component. | R1215, R1220, R1225 |
| `INV-851` | `period_cost_detail_sums` | run | For every order, period and posting component, the rows of `production_order_period_cost_detail` sum exactly, in each amount column, to the `production_order_period_cost` row, and each detail's opening equals its closing of the order's previous period with costs. | R1227 |
| `INV-852` | `estimate_without_selling_rows` | day | Every released cost estimate's lines sum to its `company_amount`, and its surcharge lines of level 0 and its sheet-row snapshot come only from `production` rows of the sheet it names; rolled-up lines (level above 0) keep the row number of the component's own estimate and are covered by that estimate's snapshot. | R1241, R1242, R1249 |
| `INV-853` | `estimate_surcharge_rated` | day | Every production surcharge row of a released estimate's costing sheet has a snapshot row whose rate is the one selected on the costing date: valid then, every stated condition matching, the most specific condition set. | R1236, R1242 |
| `INV-854` | `costing_structure_by_proposal` | day | No audit row of a costing-structure command (costing sheets, rates, site assignments, detailed components, mappings, activity rates) carries an origin agent run, except the execution of an approved change proposal. Area `safety`. | R1260, R1262 |

Named by rules of this chunk, rows in chunk 6: `INV-840` to `INV-845`; `INV-106` has its row in the chunk of ADR-0035. `INV-860` is `master_data` law (ADR-0074.R7).

## Edge cases

| ID | Name | Case | Outcome | Protects |
| --- | --- | --- | --- | --- |
| `EC-201` | `reservation_sweeps_race` | Two sweeps start on one goods receipt; together they never reserve more than the receipt or a line's open requirement (a parallel test). | `must_succeed` | ADR-0064.R15 |
| `EC-202` | `sweep_respects_sales_reservation` | Available stock is reserved for a sales order; the sweep reserves nothing from it and the shortage stays listed. | `must_succeed` | ADR-0064.R15 |
| `EC-210` | `capture_milestone_confirmation` | A report for a milestone operation; the earlier operations' generated confirmations appear in the draft's plan, not chosen by the model. | `must_succeed` | ADR-0064.R19, ADR-0034.R12 |
| `EC-211` | `capture_backflush_missing_stock` | A drafted confirmation would backflush more than the supply bin holds; its simulation shows `negative_stock` and the readiness note explains it. | `must_reject:negative_stock` | ADR-0064.R14, ADR-0064.R19 |
| `EC-219` | `reservation_transfer_only_by_proposal` | A reservation transfer outside an approved proposal is refused; through one, the source is reduced and the target gains the same quantity. | `must_reject:proposal_required`; `must_succeed` | ADR-0064.R24 |
| `EC-284` | `output_rework_and_make_to_order` | Rejected make-to-order output gets a draft rework order issuing from `quality_inspection`; the reworked output's lot is accepted, and its release reserves the output for the sales line. | `must_succeed` | ADR-0070.R12, ADR-0070.R15, ADR-0034.R14 |
| `EC-286` | `source_reversed` | A production receipt is reversed while its lot is a draft and the lot is canceled by system; after the lot is approved and released, the reversal is refused with `negative_stock` until the stock is moved back. | `must_succeed`; `must_reject:negative_stock` | ADR-0070.R8 |
| `EC-287` | `in_process_rejection` | An operation confirmation of an operation named by a released `in_process` plan opens a lot without stock; its rejection has no lines and opens an internal nonconformance. | `must_succeed` | ADR-0070.R8, ADR-0070.R12, ADR-0070.R16 |
| `EC-295` | `blocked_wo_case` | A WO is blocked for a breakdown; `operation_blocked` is raised and, with `work_case.production_disruption.mode` `auto`, a case opens; `StartOperation` closes the item. | `must_succeed` | R1204 |
| `EC-300` | `costing_sheet_rows` | A sheet with base rows for material and conversion, a 10% material overhead, an amount per machine hour, an amount per output unit and a subtotal; the estimate's surcharge lines land in their details and credit their cost centers; the lines sum to the total. | `must_succeed` | R1230, R1231, R1241 |
| `EC-301` | `costing_rate_conditions` | Rates with no condition, for an item group, and for a site and that item group; an item of the group at that site takes the third, at another site the second, of another group the first. | `must_succeed` | R1236 |
| `EC-302` | `costing_rate_missing_gap` | A percent row without a valid rate on the costing date gives `costing_rate_missing`; the total leaves it out and release is refused; after the rate is set the estimate is computed again and released; a stored rate 0 is no gap. | `must_reject:cost_estimate_incomplete`; `must_succeed` | R1237; ADR-0062.R12 |
| `EC-303` | `selling_rows_quote_only` | Administration and selling rows appear in `GetSellingPriceCosting` for a quotation and never in the released estimate, the preliminary price or the below-cost check. | `must_succeed` | R1247, R1249 |
| `EC-304` | `version_sheet_override` | A production version with its own costing sheet costs with it, another version of the site with the site's; with `production.costing_sheet.required` true, a site without a sheet gives `costing_sheet_missing`. | `must_succeed` | R1245, R1246 |
| `EC-305` | `detail_rollup_two_periods` | An order open across a period end with raw material, packaging, labor and an unmapped overhead account; the detail rows sum exactly to the four components in both periods, the unmapped cost lands in the default overhead detail, and the second period opens with the first's closing split. | `must_succeed` | R1227 |
| `EC-306` | `projected_cost_at_completion` | An order completed in a period without receipts shows its projected final cost with that period's cost as projected residual; after a reopen and a further receipt the projection is in progress again; after the run it equals the settled actuals and is no longer provisional. | `must_succeed` | R1256, R1257 |
| `EC-307` | `agent_drafts_costing_sheet` | The production agent's direct `SetCostingSheetRates` is refused with `proposal_required`; its proposal, with rates from `GetCostingRateSuggestion`, executes after a person approves. Area `safety`. | `must_reject:proposal_required`; `must_succeed` | R1260, R1262, R1263 |
| `EC-317` | `scrap_reason_needs_scrap` | A production receipt or confirmation with a scrap reason and no scrap quantity is refused. | `must_reject:validation_failed` | ADR-0074.R14 |

Named by rules of this chunk, rows in chunk 6: `EC-290` to `EC-294`, `EC-296` and `EC-297`.

## Settings

Storage `setting_value`, change effect `immediate`.

| Key | Value type | Scopes | Core default | Bounds | Direction | Leaf | Outdates | Used by |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `production.costing_sheet.required` | `boolean` | `company` | `false` | `true\|false` | `true_tighter` | `costing_structure` | `none` | R1246, R1265 |

Named by R1205, with their rows in chunk 6: `production.operation.start_when_waiting` and `production.operation.stop_reason_on_pause` (catalog source ADR-0071 rule 8).

Reads: `work_case.<kind>.mode` (`work`; for this module `work_case.production_disruption.mode`, R1204).

## UI annotations

The sources state no floorplan, title, facet, field annotation or tile for this chunk. Work item kind and work case kind of its rules:

| Kind | Subject table | Owner | Due | Resolution | Rule |
| --- | --- | --- | --- | --- | --- |
| work item `operation_blocked` | `production_order_operation` | `role:shop_floor_lead` | `days:1` | `system`: when the WO leaves `blocked` by `StartOperation` | R1204 |
| work item `shop_floor_report_extracted` | `document_extraction` | `role:shop_floor_lead` | `days:1` | `person`: an extraction of purpose `shop_floor_report` reached `extracted` or `verified`; the capture agent drafts from it, or a person keys the documents | ADR-0064.R19 |
| work item `subcontract_line_review` | `production_order_operation` | `buyer` | `days:1` | `person`: a production order change or cancellation left an external operation's purchase line to review | ADR-0037.R4 |
| work case `production_disruption` (trigger `operation_blocked`; origin tables `production_order_operation`, `production_order`) | not stated | `role:shop_floor_lead` | `days:1` | `person` | R1204 |

Source finding: the owner of the work item kind `shop_floor_report_extracted` is not settled: ADR-0064.R19 and R29 make it the trigger of the capture agent, a Phase 2 agent (ADR-0078.R2), while catalog module is `production`.

## Conflicts

CONFLICT ADR-0072.R21: the note ADR-0072.R21.N1 turns the open choice of the standard method into a decision (price-control option beside periodic actual costing, overhead by costing sheet); R1268 states the decision.
CONFLICT ADR-0072.R3: ADR-0021.R7.N1 and ADR-0025.R8.N1 supersede the landed cost consumer split, so the mapping has no consumer-split facts (R1223).
CONFLICT ADR-0072.R18: ADR-0078.R2 makes the agent types `production` and `production_variance` Phase 2 with mode `off` (R1262, R1264).
CONFLICT ADR-0072.R10: a review note of 2026-11-21 inside the rule makes `purpose` a function parameter of `estimate_configuration`, adding no schema; R1248 states it.

## Proposed (not law)

None

## Trace

| Source | Where |
| --- | --- |
| ADR-0071.R17 | R1201, R1202, R1203 |
| ADR-0071.R18 | R1204 |
| ADR-0071.R19 | R1205 |
| ADR-0071.R20 | R1206, R1207, R1208 |
| ADR-0072.D0 | R1211 |
| ADR-0072.R1 | R1211, R1212 |
| ADR-0072.R2 | R1215, R1216, R1217 |
| ADR-0072.R3 | R1220, R1221, R1222, R1223 |
| ADR-0072.R4 | R1225, R1226, R1227 |
| ADR-0072.R4.N1 | R1228 |
| ADR-0072.R5 | R1229 |
| ADR-0072.R6 | R1230, R1231, R1232, R1233 |
| ADR-0072.R7 | R1235, R1236, R1237, R1238 |
| ADR-0072.R8 | R1240, R1241, R1242, R1243, R1244 |
| ADR-0072.R9 | R1245, R1246 |
| ADR-0072.R10 | R1247, R1248, R1249 |
| ADR-0072.R11 | R1250 |
| ADR-0072.R12 | R1252 |
| ADR-0072.R13 | R1253, R1254 |
| ADR-0072.R14 | R1255, R1256, R1257 |
| ADR-0072.R15 | R1258 |
| ADR-0072.R16 | R1259 |
| ADR-0072.R17 | R1260, R1261 |
| ADR-0072.R18 | R1262, R1263, R1264 |
| ADR-0072.R19 | R1265 |
| ADR-0072.R20 | R1266, R1267 |
| ADR-0072.R21 | R1268 |
| ADR-0072.R21.N1 | R1268 |
| ADR-0074.R7 | ref: ADR-0074.R7 |
| ADR-0074.R7.N1 | ref: ADR-0074.R7.N1 |
| ADR-0074.R7.N2 | ref: ADR-0074.R7.N2 |
