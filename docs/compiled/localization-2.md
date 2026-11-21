Module: localization    Chunk: 2 of 2    Source ADRs: ADR-0039, ADR-0041, ADR-0053, ADR-0057
Build step(s): 0, 1, 6, 7, 8    Generated from index: 30d5706    Compiled by: Claude Fable 5.2, 2026-11-21

# Compiled spec: `localization`, chunk 2

## Purpose

`localization` owns the structure of localization packages, the loader that checks and loads them, and the installation table `regime_setting`. It is a layer-2 platform module (ADR-0022.R2). It owns no country value: rates, account numbers, form layouts, thresholds and legal references are flagged content of a package such as `l10n_vn`, and this spec names only the mechanism, the files and the keys. This chunk holds R201 and up: the core-or-overlay test, the test package `l10n_xx`, ownership of package content, and the format and check rules that the `l10n_vn` draft (DS-19) fixes for chart templates, account determination and settings. `localization-1.md` holds R1 to R199: package structure, bases, regime settings and the loader.

## Entities and tables

DDL: `docs/design/DS-05-platform.sql`. The row of `regime_setting` is in `localization-1.md`; the rules of this chunk define no table. Package files named by the rules below are repository files, not tables.

Reads (not owned): `company` (`legal_form`, `localization_package`), `transaction_key`, `movement_type`, `tax_matrix`, `company_tax_matrix`, `setting_definition`; the catalogs `system-accounts.csv`, `transaction-keys.csv`, `movement-types.csv` and `settings.csv`.

## Commands and queries

None: see chunk 1; the units of this chunk register no command or query of `localization`. They name `CreateCompany` (`master_data`, R221), the job `RunBalanceCarryForward` (`ledger`, R219), and `Submit`, `Approve`, `Reject` and `Issue<Type>` of `documents` (ADR-0053.R8). The package check `check_package.py` (R236 to R239) is a lab and CI program, not a command.

## Rules

### Core or overlay

R201. A rule, value or name is overlay when its content comes from one country's law or standards: a legal threshold, a legal enum, an account number, a form, or a legal citation used as the reason for a behavior. Overlay content lives in a localization package. The core holds the mechanism, its neutral names and the schema a package fills.
Source: ADR-0053.R1

R202. The test: would the rule read the same for a company in a country the core has never seen? If not, the country-specific part moves to a package, as a package rule, a package template or a regime setting (ADR-0016.R5). New design items apply the test; reviewers apply it as part of the spec check of ADR-0005, and `template.md` is not changed.
Source: ADR-0053.R1

R203. Core text may mention a country only as a labelled example or as a pointer to the package (for example "`l10n_vn` seeds this"). Neither may be the only statement of a behavior.
Source: ADR-0053.R1

R204. Not overlay: the UI language (the Vietnamese UI is shipped by the core, D8; R211), and decisions the author took for the core even when one country motivated them (ADR-0053.R14).
Source: ADR-0053.R1

R205. The data-processing policy is core and regime-neutral: the core registers the key `data_processing.policy` and the gate, without a default. A regime's values are package data, and the test package `l10n_xx` declares its own (ADR-0057.R20; R241).
Source: ADR-0053.R1.N1

R206. Every core setting is registered with a core default or `fail_closed`. A key whose content is a regime's law or accounting rule has no core default; packages fill such neutral keys and may only tighten core floors (ADR-0063.R1, ADR-0063.R18).
Source: ADR-0053.R1.N2

### Test package `l10n_xx`

R207. Core property tests (DS-16) run on `l10n_xx`, a minimal fictional test package, so core tests never depend on the overlay. `XX` is in the ISO 3166-1 user-assigned range, so it never names a real country. `l10n_xx` is built with the test kit, not as a country package.
Source: ADR-0053.R9

R208. `l10n_xx` contains: one regime, `test`; every core-required setting, with dummy values; a chart of about 30 accounts that satisfies ADR-0010.R17; a default determination for every key; two or three tax codes with a test rate change; one `payment_evidence_threshold` rule with a fictional threshold.
Source: ADR-0053.R9

R209. Its entries carry the basis `test_fixture` (`basis` in CSV files, `status: test_fixture` in YAML). The basis is valid only in a package whose manifest sets `is_test_package: true`; `check_package.py` rejects it in any other package. `test_fixture` counts as verified for ADR-0016.R12.
Source: ADR-0053.R9

R210. The loader refuses a test package at deploy time in a `production` installation, so gate tests never deploy one there. The harness either calls the gate as a function that takes the environment as input, or loads `l10n_xx` into its throwaway database and then sets that database's `environment` to `production` (ADR-0007.R15). Either way, single entries are marked `unverified` in the fixture.
Source: ADR-0053.R9

### Terminology, datasets and ownership

R211. Terminology of the core: UI language strings, including the Vietnamese UI (D8), the core catalog's plain translations of system account and key names (such as `income_summary`), and the plain translations of core unit names. Terminology of a package's terminology catalog: the country's accounting names for system accounts and keys, and the package's statutory unit names as terminology keys with their bases (ADR-0056.R2, ADR-0056.R18; ADR-0016.R18; ADR-0040.R15, ADR-0040.R19).
Source: ADR-0053.R16, ADR-0053.R16.N1

R212. Business profiles and the tax ID generator of the synthetic dataset are package-supplied (component "synthetic dataset parameters", ADR-0016.R5). The core simulator is country-neutral. `l10n_xx` supplies `xx_core_small@1`, which carries every edge case; core CI runs it with the `min_small` check.
Source: ADR-0053.R15

R213. `l10n_vn` supplies `vn_trading_small@1`, `vn_trading_medium@1` and the planned `vn_manufacturing_*` profile, with the tax ID format and prefix of DS-17 rule 19, and runs `vn_trading_small@1` with the `min_small` check in its package-level CI. Step gates keep the datasets spec 12 names, its small and medium datasets, which are these `l10n_vn` profiles; spec 12 is unchanged. Changing a gate's dataset is the author's (ADR-0005 item 4).
Source: ADR-0053.R15

R214. `l10n_vn` runs in package-level golden tests and its dataset profiles (R213). Its golden scenarios stay a mandatory CI test of the package (ADR-0016.R15).
Source: ADR-0053.R9

R215. Ownership: the tax draft of ADR-0041.R21 (R240) and the costing method names and product cost sheet of ADR-0035.R16 are content of `l10n_vn`, owned by ADR-0039. `l10n_vn` owns its tax data and DS-23 owns only the format (R233). "Best practice and Vietnamese rules together" in ADR-0032.R3 reads "best practice; regimes configure".
Source: ADR-0053.R13

### Chart template rules (regime `tt99` of `l10n_vn`, DS-19)

R216. A package adds detail accounts to a regime's chart template only where one account of the regime's chart must map to several system leaves (ADR-0010.R11), or where the core needs an account the regime's chart lacks. In `regimes/tt99/chart_template.csv` (ADR-0039.R1) the detail accounts reach `revenue_goods`, `revenue_services`, `revenue_other`, one leaf each for the kinds of financial income and financial expense, the deduction leaves, `cost_of_goods_sold`, `inventory_write_down_expense`, `inventory_difference`, `price_difference`, `gr_ir_clearing`, `purchase_cost_clearing`, `payable_other`, `production_cost_other`, `production_cost_overhead`, and a technical account for `opening_balance_clearing` that is zero after migration. The account codes are flagged package content and are not core law.
Source: ADR-0039.R3

R217. Detail codes sit one level below an account of the regime's chart, never at a level of that chart, so a later amendment of the regime cannot collide with them. An account split this way becomes a node, so a posting must use a detail account.
Source: ADR-0039.R3

R218. Every postable account of the template maps to the system leaf that matches its nature; presentation stays on operational accounts (ADR-0010.R8). The mapping choices that are not obvious from the account's nature are `unverified` under one open question; they use the leaves `fixed_asset_tangible`, `fixed_asset_other`, `asset_other`, `inventory_raw_material`, `receivable_loan`, `payable_other`, `liability_other`, `production_cost_overhead`, `income_summary` and `retained_earnings`, and the production cost and work-in-process leaves of ADR-0035.R18. The account numbers are flagged package content. An allowance mapped to `asset_other`, which has no contra leaf, may carry a credit balance (ADR-0010.R4); reports by system account then show it as a negative asset. An inventory account that needs a warehouse to be determined gets a warehouse row the company adds (R225).
Source: ADR-0039.R4

R219. Carrying the year's retained earnings into the accumulated account at the new year is the close task `balance_carry_forward`, which runs the idempotent job `RunBalanceCarryForward` of `ledger` with the two accounts as parameters (ADR-0049.R22, ADR-0049.R23); it is a closing task of step 8 (DS-26).
Source: ADR-0039.R4, ADR-0039.R4.N1

R220. `unreached_system_accounts.csv` states the system accounts no operational account reaches, and why (ADR-0010.R17). For `tt99` it states `inventory_other`, `income_other`, `expense_other` and `revenue_deduction_other`, for which the regime's chart has no account.
Source: ADR-0039.R4

R221. The `condition` column of a chart template row is empty, `legal_form=<code>` or `legal_form!=<code>`. The manifest declares the legal forms with their legal source; `l10n_vn` declares the codes `joint_stock`, `limited_liability`, `private_enterprise` and `partnership`, which are flagged package content. `CreateCompany` records `company.legal_form`, which is null for packages that declare none (DS-20; ADR-0027.R5). A condition lets one account be a node for one legal form and a postable account for every other company.
Source: ADR-0039.R5

R222. The legal form selects rows only when the company is set up. A company whose legal form changes later keeps its postable account (ADR-0010.R12); it opens the detail accounts under the parent account and moves the balance by a balance transfer, flagged.
Source: ADR-0039.R5

R223. Every production cost account of a chart template carries `cost_behavior`, variable or fixed, because ADR-0035.R7 splits each pool group by it. The seeds are `unverified` package content. A company that needs a finer split adds detail accounts.
Source: ADR-0039.R6

### Account determination template

R224. Format of the determination template (`account_determination.csv`, ADR-0039.R1): `transaction_key`, the determinant columns of ADR-0015.R9, `account_code`, the basis columns and a `note`. The determinant columns use the package's seed codes for valuation class, item group and partner group. The seed rows are package content; `tt99` seeds the valuation classes `raw_material`, `tools_supplies`, `semi_finished`, `finished_goods` and `merchandise`, the item groups `merchandise`, `product`, `service` and `other`, and the partner groups `domestic`, `foreign`, `dependent_unit` and `employee`. The template may name the package's own tax codes (ADR-0041.R1).
Source: ADR-0039.R7

R225. The template never names warehouses or currencies, which are company data, and tax code rows other than the package's own are DS-23's. Companies add those rows, for example a warehouse row for a bonded warehouse; DS-23 adds tax code rows, for example for input tax on fixed assets.
Source: ADR-0039.R7

R226. The default determination of `tt99` is a set of interim choices, all `unverified`; the rounding rows cite an author's decision, and their detail accounts are the package's. The accounts and the alternatives the package weighs are flagged package content. The choices cover: price differences; GR/IR clearing (`gr_ir_clearing`); purchase cost clearing; stock count shortage and surplus, pending decision; scrap; consumption, where a company routes issues to other expense accounts by adding rows (open question on purpose); other issues and other receipts (`other_receipt_offset`); the revaluation offset, write-downs and their allowance; realized and unrealized foreign exchange, the unrealized straight to profit or loss, read with `fx.revaluation.frequency`; rounding and payment discounts; income summary, retained earnings and opening balances; reconciliation accounts; production.
Source: ADR-0039.R8

R227. Price differences with a valuation class go to stock through `purchase_cost_clearing` and a landed cost (ADR-0015.R4). Without a valuation class they go to a price difference expense account: service invoice differences after an order closes (ADR-0037.R6), and order lines closed with quantity never received (ADR-0030.R4).
Source: ADR-0039.R8

R228. Reconciliation accounts have defaults, separate accounts for dependent units, and an advance account for employees; as suppliers, employees fall to the default payable reconciliation account, because no payable-control account fits them (open question). Production determination covers consumption, output and work-in-process transfer, abnormal, unabsorbed and residual cost, and external processing; processor stock stays on its inventory account (ADR-0037.R1).
Source: ADR-0039.R8

R229. The presentation of the GR/IR clearing and purchase cost clearing detail accounts uses DS-26's format (ADR-0049.R22); the lines are DS-19's report definitions. The package also chooses the line of each balance: a debit balance of GR/IR clearing is presented apart from its credit balance.
Source: ADR-0039.R8, ADR-0039.R8.N1

### Package and regime settings

R230. Each choice is its own key, so each carries its own basis. The core registers every key with its schema (DS-18). The values are flagged package content of `settings.yaml` (package level and `regimes/tt99/`), `unverified` unless an author's decision is their basis. The keys:
- package level (every regime): `reversal.method`, `reversal.locked_period_posting_date`, `reversal.material_document_value`, `posting_date.default.purchase_invoice` (an author's decision), `posting_date.default.purchase_invoice_month_closed`, `posting_date.default.other`, `attachment_retention_years` (ADR-0038), `documents.issuance_without_delay` (`unverified`; ADR-0053.R8) and `documents.e_invoice_required` (`unverified`; ADR-0053.R8.N1);
- regime level, rate dates and quotes: `fx.transaction_rate.date_basis`, `fx.transaction_rate.quote`, `fx.revaluation_rate.quote`, `fx.revaluation_rate.date_basis`, `fx.document_rate.allowed`;
- regime level, book and realized FX: `fx.book_rate_method`, `fx.realized_fx_basis` (the `realized_fx_basis` of ADR-0011.R16);
- regime level, revaluation: `fx.revaluation.frequency`, `fx.revaluation.method`, `fx.revaluation.target`, and `fx.revaluation.scope`, listed per system account (per open item, per balance, or none);
- regime level, imports: `fx.import_receipt.rate`, `fx.import_receipt.invoice_difference`;
- regime level, closing and inventory: `closing.method`, `journal.manual_posting_to_control_accounts`, the `movement_type.<code>.*` keys that movement-types.csv marks `regime`, `landed_cost.closed_period_method`, `stock_count.bin_difference_method`;
- regime level, production (ADR-0035.R18): `production.wip_method`, `production.abnormal_cost.applies`, `production.abnormal_cost.tolerance_percent`, `production.normal_capacity.applies`, `production.co_product_split`, `production.estimate_price_basis`.
Source: ADR-0039.R9, ADR-0039.R9.N1

R231. Not settings: the behavior ADR-0035 fixes in the core and flags (abnormal cost at period actual, the units-in-process definition, the negative residual offset, zero value under a capped planned WIP, the disassembly split, the singular fallback); subledger activation, which is core behavior (ADR-0034.R15); company data (`wip_completion_percent`, pool allocation rules, the `by_product_price` list); where accounts go, since unabsorbed, abnormal and residual cost reach cost of goods sold through determination (R226); the alternative accounting for processor stock, which would need a core change (ADR-0037.R1); and the non-cash payment threshold, which is the package's deductibility rule `non_cash_payment_threshold` (ADR-0053.R3, ADR-0053.R8).
Source: ADR-0039.R9, ADR-0039.R9.N1

R232. The period pattern is a package template, not a rule (ADR-0016.R5; ADR-0012.R1): `close_checklist.yaml` seeds the periods. Its tasks come in step 8.
Source: ADR-0039.R9

### What the package ships and what is owned elsewhere

R233. `l10n_vn` owns its tax data under ADR-0039: codes, rates, matrix, groups (with `import_treatment` and item tax groups), return forms, package kinds and deductibility rules. DS-23 owns only their format. The golden scenarios of `l10n_vn` are to be listed with DS-19 (open question) (ADR-0053.R10, ADR-0053.R13).
Source: ADR-0039.R10, ADR-0039.R10.N1

R234. Statutory reports, books, print templates and close task content follow the formats of ADR-0049. The regime's definitions are DS-19 data from step 6 (interim until the author decides the build order, ADR-0049.R30); the close task content comes from step 8.
Source: ADR-0039.R10, ADR-0039.R10.N2

R235. Owned elsewhere, not shipped by DS-19: numbering formats (ADR-0009 interim); the e-invoice adapter (DS-24); bank readers (DS-25); data protection rules (DS-35), which are the `data_protection` package rules (ADR-0052.R24); the working calendar (ADR-0024).
Source: ADR-0039.R10

### Package check `check_package.py`

R236. The check `check_package.py` runs for each declared legal form. On the chart template it checks: ADR-0010.R11 and the template analogues of ADR-0010.R16 (unique codes, parents present, no cycles, only leaves postable and mapped to postable leaves); ADR-0010.R17 (every system account a transaction key or closing uses is reached, or stated with a reason; a stated account that is reached fails too); and values: `is_postable`, `cost_behavior` on exactly the production cost accounts, no currency in a template, and a condition or cost behavior only on a row whose basis is a package choice.
Source: ADR-0039.R11, ADR-0039.R11.N1

R237. On determination (ADR-0015.R4, ADR-0015.R9, ADR-0015.R10, ADR-0015.R13) it checks: only declared determinants, and no warehouse, tax code or currency in a template; the required system account and control kind, and the inventory-node rule; unique rows; a unique match for every combination of seed values, including no valuation class on keys that do not require stock control.
Source: ADR-0039.R11

R238. On bases (ADR-0016.R6) it checks: exactly one basis per entry; a legal source with document, article and date; an author decision with reference, date and name; every open question cited is an open (`- [ ]`) question in open-questions.md. On required settings it checks the `movement_type.<code>.*` keys derived from the catalog.
Source: ADR-0039.R11

R239. `--self-test` applies broken copies, each of which must fail. They cover: a receivable account on inventory and a mapping to an inner node; a missing revenue row, a missing generic price difference row, and GR/IR on a supplier reconciliation account; a cost-object account on the inventory key (control kind); a cost behavior on a legal-source row, an unknown open question, a closed question cited, and a missing required setting; a setting with two bases, and a removed unreached statement.
Source: ADR-0039.R11

### Tax draft and intake content of `l10n_vn`

R240. The tax draft of `l10n_vn` lives in `docs/design/DS-19-vietnam-tt99/tax/` and is content of `l10n_vn`, owned by ADR-0039 (ADR-0053.R13). It holds the item tax groups `standard`, `standard_reducible`, `reduced`, `not_subject` and `not_declared`, the partner tax groups `domestic`, `export`, `no_vat_invoice` and `foreign_supplier`, tax codes (among them fixed-asset input codes, a not-declared sale code, import VAT codes and assessed import duty, excise, environmental protection tax and trade remedy duty), and a VAT return form whose deductible box reads `deductible:`. Tax code names, rates, dates, box numbers and legal references are flagged package content and are not restated; the unconfirmed points are open questions.
Source: ADR-0041.R21, ADR-0041.R21.N1

R241. The core names no national law. In `l10n_vn` (DS-19) the following are package content: the legal basis and XML structure of the e-invoice reader, selected by schema version, with unverified points under an open question (DS-40); the package setting `intake.e_invoice_formats`, which records the formats its reader selects, `unverified`; the values of `data_processing.policy`, `unverified` (open question), so that under ADR-0016.R12 the setting fails closed in production; and the OCR language, tax ID rules, label anchors and unit names, as package data.
Source: ADR-0057.R30

## Invariants

| Invariant | Name | Check point | Protects |
| --- | --- | --- | --- |
| `INV-302` | company_tax_rows_approved | day | ADR-0041.R3.N2 (area `tax`) |

`INV-302` is stated and protected by `tax`: company tax rows name an executed, separately approved change proposal, and a company row never applies where a package row in force is not `is_adjustable`. It concerns this module because `tax_matrix` is installation data like `regime_setting` (ADR-0041.R3.N2).

## Edge cases

None: the catalog rows of this module hold no edge case.

## Settings

| Key | Type | Scope | Core default | Rule |
| --- | --- | --- | --- | --- |
| `journal.manual_posting_to_control_accounts` | boolean, `false_tighter` | regime (`regime_setting`) | false | R230 |
| `stock_count.bin_difference_method` | enum `net`, `gross`; `neutral` | regime (`regime_setting`) | none (`fail_closed`) | R230 |

Both are package rows (leaf `package`, change effect `package_release`) and keys of other areas (`ledger`, `inventory`) that packages fill. Chunk 1 holds the rows of `data_processing.policy`, `documents.unit_name_max_length`, `documents.issuance_without_delay`, `documents.e_invoice_required` and `intake.e_invoice_formats`. The other keys of R230 have no row in `settings.csv`; the `movement_type.<code>.*` rows of `settings.csv` are keys of `inventory`.

## UI annotations

None: the sources hold no ADR-0077 annotation for this module.

## Conflicts

CONFLICT ADR-0039.R10: the rule lists tax codes, rates, `import_treatment` and item tax groups as DS-23's and statutory reports as step 8 content; ADR-0039.R10.N1 with ADR-0053.R13 gives the tax data to `l10n_vn`, and ADR-0039.R10.N2 moves the report definitions to step 6 data (R233, R234).
CONFLICT ADR-0039.R8: the sentence that capital contributed in kind has no allowed account under `other_receipt_offset` is not restated; the transaction key catalog row now allows `owner_capital` and the open question is closed, so R226 names only the key.

## Proposed (not law)

None.

## Trace

| Source | Where |
| --- | --- |
| ADR-0039.R3 | R216, R217 |
| ADR-0039.R4 | R218, R219, R220 |
| ADR-0039.R4.N1 | R219 |
| ADR-0039.R5 | R221, R222 |
| ADR-0039.R6 | R223 |
| ADR-0039.R7 | R224, R225 |
| ADR-0039.R8 | R226, R227, R228, R229 |
| ADR-0039.R8.N1 | R229 |
| ADR-0039.R9 | R230, R231, R232 |
| ADR-0039.R9.N1 | R230, R231 |
| ADR-0039.R10 | R233, R234, R235 |
| ADR-0039.R10.N1 | R233 |
| ADR-0039.R10.N2 | R234 |
| ADR-0039.R11 | R236, R237, R238, R239 |
| ADR-0039.R11.N1 | R236 |
| ADR-0041.R3.N2 | ref: ADR-0041.R3.N2 |
| ADR-0041.R21 | R240 |
| ADR-0041.R21.N1 | R240 |
| ADR-0053.R1 | R201, R202, R203, R204 |
| ADR-0053.R1.N1 | R205 |
| ADR-0053.R1.N2 | R206 |
| ADR-0053.R8 | ref: ADR-0053.R8 |
| ADR-0053.R8.N1 | ref: ADR-0053.R8.N1 |
| ADR-0053.R9 | R207, R208, R209, R210, R214 |
| ADR-0053.R13 | R215 |
| ADR-0053.R15 | R212, R213 |
| ADR-0053.R16 | R211 |
| ADR-0053.R16.N1 | R211 |
| ADR-0057.R30 | R241 |
