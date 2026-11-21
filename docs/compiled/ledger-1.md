Module: ledger    Chunk: 1 of 3    Source ADRs: ADR-0004, ADR-0006, ADR-0007, ADR-0008, ADR-0010, ADR-0011, ADR-0012, ADR-0014, ADR-0015
Build step(s): 0, 1, 3, 5, 6, 8    Generated from index: 30d5706    Compiled by: Claude Fable 5.2, 2026-11-21

# Compiled spec: `ledger`, chunk 1 (system chart, multi-currency, universal journal, account determination)

## Purpose

`ledger` is a layer 3 (core business) module. It owns the system chart of accounts, the operational accounts, the universal journal, multi-currency amounts and rates, and account determination. This chunk states the law of ADR-0010, ADR-0011, ADR-0014 and ADR-0015, with the `ledger` rules of ADR-0006 and ADR-0012. Open items, payment terms, the later-phase subledger seams, derivation traces, opening turnover, the business unit dimension and the reporting rules are in the other chunks. `ledger` does not own posting periods, documents, partners, items, tax codes or stock values; it reads them.

## Entities and tables

DDL: `docs/design/DS-06-universal-journal.sql`.

| Table | Meaning | Key | Parent | Owner |
| --- | --- | --- | --- | --- |
| `system_account` | Global catalog row of the system chart (R1) | `id` (uuid5), unique `code` | `system_account` (`parent_id`) | ledger |
| `transaction_key` | Global catalog row of a transaction key (R64) | `id` (uuid5), unique `code` | none | ledger |
| `account` | Operational account of a company (R10) | `id`, unique (`company_id`, `code`) | `company`; `account` (`parent_id`) | ledger |
| `applied_rate` | One conversion a document used, with its quotes (R22) | `id` | `company` | ledger |
| `journal_entry` | Accounting effect of one posted document (R42) | `id`, unique `document_id` | `document` | ledger |
| `journal_line` | One line of an entry with amounts, dimensions and links (R46) | `id`, unique (`journal_entry_id`, `line_number`) | `journal_entry` | ledger |
| `account_period_balance` | Cache of turnover and closing balance per account and period (R61) | `id`, unique (`company_id`, `account_id`, `posting_period_id`, `transaction_currency`, `is_closing_entry`) | `account` | ledger |

Defined by rule, without DDL in the design files: `account_determination` (R70), `exchange_rate` (R29), `exchange_rate_source` (R28).

Reads: `company`, `currency`, `document`, `posting_period`, `posting_period_area_state`, `fiscal_year`, `close_task`, `partner`, `customer_profile`, `supplier_profile`, `module_activation`, `item`, `warehouse`, `valuation_class`, `branch`, `cost_center`, `project`, `tax_code`, `tax_line`, `cost_object`, `business_unit`, `stock_value`; and, from the other chunks of this module, `open_item`, `fixed_asset`, `derivation_trace`.

## Commands and queries

Authorization, input details and events are given only where the sources of this chunk state them.

| Name | Actor / authorization | Input | Effect | Events | Error codes |
| --- | --- | --- | --- | --- | --- |
| `CreateAccount` | area `chart_of_accounts`, level `edit` | an operational account (R10) | creates an `account` row; rejects an unmapped postable account and a mapping to an inner node (R11) | not stated | not stated |
| `CreateExchangeRate` | area `exchange_rate`, level `edit` | a quote for a company's own source (R28, R29) | adds an `exchange_rate` quote | not stated | not stated |
| `ImportExchangeRate` | area `exchange_rate`, level `edit` | quotes for a company's own source (R28) | adds `exchange_rate` quotes | not stated | not stated |
| `GetExchangeRate` (query) | level `read` (computed query); area not stated | rate type, currency pair, date, company | returns the unsaved applied rate the lookup would produce, with its quotes and their age (R34) | none | `exchange_rate_missing` |
| `CreateAccountDetermination` | area `chart_of_accounts`, level `edit` | key, determinant values, account (R70) | saves a row after the cross-check of R67 (R73) | not stated | `account_determination_mismatch` |
| `UpdateAccountDetermination` | area `chart_of_accounts`, level `edit` | a row (R70) | changes a row after the cross-check of R67 (R73) | not stated | `account_determination_mismatch` |
| `DeleteAccountDetermination` | area `chart_of_accounts`, level `edit` | a row | removes a row (R73) | not stated | not stated |

Authorization areas of this chunk (catalog `authorization-areas.csv`, all under `finance`): the functions `chart_of_accounts` (accounts and account determination) and `exchange_rate` (rate sources and manual rates), and the document types `general_journal` (R44), `balance_transfer` (R44) and `fx_revaluation` (the revaluation documents of R37). Levels are those of the verb in `authorization-verb-levels.csv`.

Error codes raised on the posting path: `exchange_rate_missing` (R30), `document_rate_out_of_tolerance` (R32), `regime_configuration_missing` (R33), `plan_hash_mismatch` (R34), `manual_posting_to_control_account` (R53), `account_determination_missing` (R71, R72), `account_determination_mismatch` (R73). Check result: `settlement_rate_unusual` (R32).

## Rules

### System chart of accounts

R1. The system chart is the catalog `docs/catalogs/system-accounts.csv`, owned by DS-07, with columns `code`, `parent_code`, `account_type`, `normal_balance`, `is_contra`, `is_bilateral`, `control_kind`, `is_postable`, `added_in`, `name`, `meaning`. The core loads it into the global table `system_account` (no `company_id`), one column per catalog column, except that `parent_code` is stored as `parent_id`, a key to the parent's uuid5 `id` that the loader resolves (`ADR-0004.R12`). Each row's `id` is `uuid5(…, "system_account:<code>")` (`ADR-0006.R4`). `name` and `meaning` are English source text, translated through i18n (Principle 7). The catalog is the word list for system account codes in the glossary.
Source: ADR-0010.R1, .N1

R2. `code` is a `snake_case` English identifier (ADR-0004), for example `inventory_merchandise`; it never contains a country's account number. Leaves in the receivable, payable, tax and fixed asset families start with their family's name (`receivable_trade`, `tax_payable_output`). Core code refers to system accounts only through a type generated from the catalog (for example `SystemAccount.INVENTORY_MERCHANDISE`), never by string literals or operational account codes.
Source: ADR-0010.R2

R3. `account_type` is one of `asset`, `liability`, `equity`, `income`, `expense`, which are also the roots of the tree; a child has its parent's type. `asset`, `liability` and `equity` are balance-sheet types; `income` and `expense` are profit-and-loss types.
Source: ADR-0010.R3, ADR-0010.D0

R4. `normal_balance` is `debit` for assets and expenses and `credit` for liabilities, equity and income, except contra accounts (`is_contra: true`), which have the opposite normal balance (for example `fixed_asset_accumulated_depreciation`, `revenue_deduction_return`). A balance on the other side is allowed; it is a fact for reports and checks, not an error.
Source: ADR-0010.R4

R5. `control_kind` says which core module owns postings to the account and what an invariant can check. `inventory`: valued stock, posted only through the inventory module (material document lines and value-only lines carrying item and warehouse through the stock lock helper, `ADR-0020.R9`); its balances equal the inventory valuation report. `receivable` and `payable`: partner open-item accounts; every line carries a partner and an open item, and balances equal the sum of open items. `gr_ir`: GR/IR clearing. `none`: no control. The gated kinds `cost_object`, `fixed_asset` and `loan` are enforced per company only from an irreversible activation; before it the effective kind is `none` (`ADR-0025.R3`, `ADR-0025.R4`, `ADR-0025.R5`). Open items on these accounts follow `ADR-0026.R3`. The invariants use `control_kind`; account determination uses it together with the tree (R13). Which partner accounts carry `receivable` or `payable` may still change in 0.x as DS-25 decides. Every production cost operational account carries `cost_behavior` (`variable` or `fixed`), seeded by the regime template (`ADR-0035.R7`, `ADR-0039.R6`).
Source: ADR-0010.R5

R6. `is_bilateral: true` marks a receivable or payable account whose open items may sit on either side and whose balance is presented split by side, for example `receivable_trade` holding customer advances and `payable_trade` holding advances to suppliers. Only accounts with `control_kind` `receivable` or `payable` can be bilateral.
Source: ADR-0010.R6

R7. Only leaves are postable; inner nodes group leaves. A leaf never becomes an inner node. A new leaf may take only meaning that its parent's `_other` leaf covered or that no leaf covered, so existing leaves never change meaning; nodes expected to be refined have an `_other` leaf.
Source: ADR-0010.R7

R8. The hierarchy and the types carry no presentation rule: where an account appears in a statutory report is set by the localization package on operational accounts (DS-26). Leaves whose presentation differs between regimes sit directly under their root (for example `payment_discount_given`, `rounding_loss`, `inventory_write_down_expense`).
Source: ADR-0010.R8

R9. The catalog is at version 0.x until the step 0 gate; until then DS-08 to DS-11, DS-25 and DS-41 (`ADR-0025.R5`) may still change rows. Version 1.0.0 is released at the step 0 gate and tagged `system-accounts-1.0.0`. From then on the catalog changes by additions only: a released row's `code`, `parent_code`, `account_type`, `normal_balance`, `is_contra`, `is_bilateral`, `control_kind`, `is_postable`, `added_in` and `meaning` never change, and no row is removed; a changed meaning is a new account. Adding rows or a column (with a value for every existing row) raises the minor version; rewording `name` or `meaning` without changing what it means is a patch version. An account that a later step needs (DS-25 at step 6 included) is an addition under this rule.
Source: ADR-0010.R9, .N1

R10. An operational account is a row of `account`: `id`, `company_id`, `code` (the company's own account number, which is data of its chart template), `name`, `parent_id` (the operational tree used by statutory reports), `is_postable`, `system_account_id`, `currency` (nullable: restricts the account to one transaction currency, for example a USD bank account), `cost_behavior` (nullable; `variable` or `fixed`, on production cost accounts, R5), `has_posting`, `is_active` and `recorded_at`. Only postable operational accounts receive journal lines. Manual journal entries on accounts whose `control_kind` is not `none` follow R53.
Source: ADR-0010.R10

R11. Every postable operational account maps to exactly one postable system account; non-postable operational accounts have no mapping. The mapping gives the operational account its type, normal balance, control kind and flags. `CreateAccount` and the localization package's CI reject an unmapped postable account or a mapping to an inner node. A company whose old chart has one account where the system chart has several leaves (for example one financial income account covering `interest_income`, `fx_gain_realized` and `rounding_gain`) splits it into sub-accounts, one per leaf; the data migration mapping (DS-21) does the split.
Source: ADR-0010.R11

R12. The first journal line on an operational account sets `has_posting = true` in the same transaction, which locks the account row. From then on a trigger rejects changes to `code`, `system_account_id`, `is_postable` and `currency`. To move to another system account, the company creates a new operational account and moves the balance: by a balance transfer document (R44) for accounts with `control_kind` `none`, per open item for receivable and payable accounts (`ADR-0026.R12`), and by a valuation change for inventory accounts (DS-09). Balances on an account whose gated control kind is active are moved by its Phase 2 or 3 module (ADR-0025). When the catalog adds a system account, existing mappings are untouched.
Source: ADR-0010.R12

R13. A transaction key declares a required system account (a leaf or a node) and, optionally, a required control kind. Account determination returns an operational account; the core checks that its system account is the required one or a descendant of it and, if a control kind is declared, has that control kind, and blocks the posting otherwise (R67, R73).
Source: ADR-0010.R13

R14. The core, the policy engine, agents, management reports and consolidation refer only to system accounts. Statutory reports and books are defined by the localization package on operational accounts (DS-26). Consolidation of companies in one instance sums balances by system account; intercompany eliminations use the partner on intercompany open items. Agents may read statutory reports, books and their drill-downs, which are operational-account views, to answer questions and explain figures; they never use an operational code to choose an account, a policy input or a posting (`ADR-0049.R18`).
Source: ADR-0010.R14, .N1

R15. A balance on a bilateral account is presented as a receivable or an advance (or a payable or an advance) per open item: each open item carries a kind defined in `ADR-0026.R2`, and statutory reports split the balance by that kind and by partner (DS-26). The split is set by the options of an account term: `by` (`account`, `partner` or `partner_kind`), required on the split measures with no core default, `kind`, and `term` with `undated` (`ADR-0049.R7`).
Source: ADR-0010.R15, .N1

R16. CI checks the catalog on every change: unique codes; every `parent_code` exists; no cycles; the roots are those of R3; a child has its parent's type, and its contra flag where the parent is contra; normal balance follows R4; only receivable and payable accounts are bilateral; `control_kind` other than `none` only on leaves; exactly the leaves are postable; family prefixes (R2). From 1.0.0 it also compares with the latest released tag: no released row removed or changed except wording (R9).
Source: ADR-0010.R16

R17. CI checks every chart template in a localization package (DS-14, DS-19): every postable operational account maps to a postable system account; every system account the core uses for determination or closing is reachable from at least one operational account of the template, or the package states why not. The TT99 template states its unreached accounts in `unreached_system_accounts.csv` (`ADR-0039.R4`, `ADR-0039.R11`).
Source: ADR-0010.R17

R18. Version 0.1.0 of the chart covers what the core needs in Phases 0 and 1 (inventory, GR/IR clearing, purchase cost clearing, price difference, cost of goods sold, receivables, payables, input and output tax, FX gains and losses, rounding gains and losses, revenue and its deductions, expenses by group), the technical accounts for closing and migration (`income_summary`, `opening_balance_clearing`), and enough other accounts that every balance of a migrating company has a place, with an `_other` leaf under every root. How each regime maps to it is DS-19; how amounts are posted to it is DS-06, DS-08 and the localization package.
Source: ADR-0010.R18

R19. The system chart is mandatory and plays the role of a group chart; the localization package supplies the operational chart template; a separate country chart is deferred (open question on foreign-invested companies). Type and control kind are set once on the system account and the operational account inherits them.
Source: ADR-0010.R19

### Multi-currency

R20. A foreign-currency document has one `transaction_currency` (currency exchange documents are the exception, R23) and may carry a `document_exchange_rate` entered by the user. Rates are resolved when the document is posted, not while it is a draft; a draft shows an indicative rate only. For e-invoiced types rates are resolved at `Issue` (`ADR-0028.R7`).
Source: ADR-0011.R1

R21. Every journal line has `transaction_currency`, `transaction_amount`, `company_currency`, `company_amount` and, when the installation's `group_currency` is set, `group_currency` and `group_amount`. A line that adjusts only company or group amounts (realized FX, revaluation, rounding) has transaction amount 0 and the transaction currency of the item or account it adjusts.
Source: ADR-0011.R2

R22. Each line refers to the applied rate of each conversion it used: `company_applied_rate_id` and `group_applied_rate_id`. An `applied_rate` row holds `from_currency`, `to_currency`, `rate` (ADR-0006 `ExchangeRate`), `origin` (`lookup`, `document`, `invoice`, `customs`, `settlement` or `book`), the selection date, and the quotes used (`first_exchange_rate_id`, and `second_exchange_rate_id` for a cross rate, R30). Many lines of one document share one applied rate. Group amounts are converted from the transaction amount with the group translation rate, with these exceptions: the clearing lines of a currency exchange take the group amount of the incoming leg, on an applied rate of origin `settlement`; outflows from money accounts take their group book value (`ADR-0048.R12`); and, interim until the step 3 costing specification, the value-only lines of period-end actual costing (revaluation, the residual of `ADR-0020.R13` and rounding) take their group amount from the costing solve run on group amounts (`ADR-0020.R12`).
Source: ADR-0011.R3, .N1, .N2

R23. Every journal entry balances in each transaction currency, in company currency and in group currency. A document that exchanges one currency for another therefore posts balancing lines in each currency through the clearing system account `currency_exchange_clearing`, also used by settle lines in another currency (`ADR-0048.R12`).
Source: ADR-0011.R4

R24. Converting and rounding follow ADR-0006: only `convert_amount`, per line, with one rounding line per entry for differences in company or group currency (R49).
Source: ADR-0011.R5

R25. `company_currency` is fixed when the company is created and never changes once it has postings. The installation's `group_currency` is set before the first posting in the installation and never changes afterwards.
Source: ADR-0011.R6

R26. Inventory value is always in company currency: `stock_value` and material document lines hold company amounts only. The group amounts that inventory journal lines carry by R21 are defined for every stock and costing line: movements are translated at posting (R22), and period-end actual costing computes the group-currency average and revaluation from group amounts, once per carried currency, never by retranslating the company-currency result (`ADR-0020.R12`). Phase 1 carries company currency, and group currency when the installation sets one. Which rate values an import goods receipt is an open question.
Source: ADR-0011.R6, .N2

R27. The exchange-rate difference between goods receipt and invoice follows `ADR-0047.R13` (interim until the step that builds it). On a line for an item kept in stock, where the company setting `costing.exchange_rate_difference_to_stock` is true, it enters the item's actual cost in company currency as a `receipt_addition` in the posting period of the posting that clears it (`ADR-0020.R12`); its group amount follows R35 (interim, step 5). On lines without stock it stays a realized exchange difference.
Source: ADR-0011.R6.N1, .N2

R28. `exchange_rate_source` holds `code`, `reference_currency` (the currency the source quotes against), `company_id` (null for a public source fetched by a job; set for a company's own manual source) and which publication of a day its fetch job stores. Each company chooses its default source; the installation sets `group_exchange_rate_source_id` and the quote kind for group translation. Rate fetch jobs per public source are provided by localization packages. Manual rates are entered only into a company's own source (`CreateExchangeRate`, `ImportExchangeRate`), never into a public one.
Source: ADR-0011.R8

R29. `exchange_rate` rows are quotes as published: `exchange_rate_source_id`, `from_currency`, `to_currency`, `unit` (positive integer, default 1: the rate is for `unit` units of `from_currency`), `quote_kind`, `effective_date` (the publisher's business date in the source's country), `version` and `rate`, unique on (source, from, to, kind, date, version). Quote kinds are `buy_cash`, `buy_transfer`, `sell_cash`, `sell_transfer`, `average` and `central` (a central bank's reference rate); a source publishes the kinds it has. A correction is a new `version`; a quote that an applied rate refers to never changes.
Source: ADR-0011.R9

R30. A lookup takes, from the chosen source, the highest version of the quote with the latest `effective_date` on or before the selection date, for the required quote kind: first the pair in either direction (a reverse quote is divided by `convert_amount`, `ADR-0006.R10`), otherwise a cross rate through the source's reference currency from the quotes of both legs, both recorded on the applied rate. The applied rate's `rate` is computed once per unit of `from_currency` (dividing by `unit`, combining the quotes of a cross rate) and rounded by `round_exchange_rate`; `convert_amount` then uses that single rate. A currency the source does not quote fails with `exchange_rate_missing`; there is no silent fallback to another source. A quote older than the rate type's `max_rate_age_days` (R31) also fails with `exchange_rate_missing`, which names the source, pair, kind and date and the commands that add a quote.
Source: ADR-0011.R10

R31. Lookup rate types are `transaction` (recognizing a foreign-currency transaction), `revaluation` (period end) and `group_translation` (to group currency). For each, the configuration declares the quote kind, which may differ by the side of the foreign-currency item (debit or credit balance), the selection date, and `max_rate_age_days`. The regime declares them for company currency; the installation declares `group_translation`. A document has one applied rate per currency pair and rate type, so its lines never mix quotes. Which side's quote a lookup takes comes from the document type's registry attribute `fx_quote_side` (`debit_items` or `credit_items`: customer-side types debit, supplier-side types credit, corrections as their original). A `general_journal` uses its entered `document_exchange_rate`, or else the one quote kind the regime declares for it (key `general_journal` of the transaction-rate quote setting, no core default).
Source: ADR-0011.R11, .N1

R32. Document rate types are `document` (R20), `invoice` (the rate printed on a foreign-currency invoice, kept separately from the book rate), `customs` (from the customs declaration, separate from the accounting rate) and `settlement` (a payment's actual rate). They are stored on their documents and recorded as applied rates with that origin. The regime declares whether a document rate may replace the lookup rate and within what tolerance; outside it, posting fails with `document_rate_out_of_tolerance`. `fx.document_rate.allowed` takes a value per document group; group `cash_and_bank` uses `always`, with the check result `settlement_rate_unusual` outside tolerance (`ADR-0048.R12`).
Source: ADR-0011.R12

R33. The core has no default for any value of R31 and R32: a posting that needs a value the regime has not declared fails with `regime_configuration_missing`. Interim TT99 values are flagged configuration in the `l10n_vn` package until verified (open questions); the TT99 seeds and their key names are in `ADR-0039.R9`.
Source: ADR-0011.R13

R34. The query `GetExchangeRate` (rate type, currency pair, date, company) returns the unsaved applied rate the lookup would produce (a computed result, an exception to the stored record of `ADR-0004.R21`), with its quotes and their age. The rate is part of the plan, so a quote added between simulation and execution gives `plan_hash_mismatch` (`ADR-0008.R13`).
Source: ADR-0011.R14

R35. Carrying amounts, book rates and realized FX are computed separately in company currency and in group currency. When a foreign-currency open item is settled or a foreign-currency cash or bank balance is paid out, the amount leaving the account in each currency is its carrying amount by the book rate method the regime declares per kind of item: `specific` (each open item keeps its own amounts) or `moving_average` (a running weighted average per account and currency). The settlement amount is the amount, in that currency, of the line that settles the item. The difference posts through account determination to the realized FX transaction keys. Open items use the specific method only, flagged (`ADR-0026.R6`, `ADR-0026.R7`). For money accounts under `moving_average`: the rate is the cumulative recorded balance's, separately for company and group currency; an outflow emptying the balance takes all of it; cash may not go negative at any later date; overdraft beyond the balance is valued at the settlement rate (`ADR-0048.R12`).
Source: ADR-0011.R15

R36. Whether realized FX after a revaluation is measured from the original carrying amount or the revalued one is the regime setting `realized_fx_basis` (`original` or `revalued`), flagged until verified; the TT99 key is `fx.realized_fx_basis` (`ADR-0039.R9`). `revalued` is meaningful only with the `delta` method; configuration validation rejects it with `reverse_and_repost`. Balance-level accounts (`moving_average`) always measure realized differences from the revalued balance, so configuration validation also rejects `original` with method `delta` when the scope revalues any account per balance. Settlement mechanics: `ADR-0026.R6`. This rule leaves the build step of that logic pending the author; `ADR-0026.R17.N1` builds the open-item core, clearing included, in step 1.
Source: ADR-0011.R16, .N1

R37. Period-end revaluation is a system job (actor `system`, on behalf of the human who starts the close; `ADR-0008.R2`) that creates and posts revaluation documents, computed separately for company currency (regime settings) and group currency (installation settings). It can be simulated before closing (Principle 2).
Source: ADR-0011.R17

R38. The regime declares: per system account, whether it is revalued per open item, per balance (account and currency), or not at all; how often (every period end or only at fiscal year end); the method, `reverse_and_repost` (reversed on the first day of the next period) or `delta` (only the change since the last revaluation); and the target, unrealized FX transaction keys or an equity account such as `fx_difference_equity` first. The next period of `reverse_and_repost` is the next regular period in the sequence of `ADR-0012.R8`, never a special period, so a revaluation of a fiscal year's last regular period is reversed on the first day of the next fiscal year. `fx.revaluation.scope` also takes `excluded_open_item_kinds`: the open item kinds never revalued, on any account; it is a regime value with no core default (R33); the TT99 seed of this value is flagged content of the localization package, `unverified`; whether an employee advance is monetary, and so revalued, is the author's (open question). The core excludes `opening_balance_clearing` (`ADR-0044.R12`) and `currency_exchange_clearing` (`ADR-0048.R12`) from every revaluation scope.
Source: ADR-0011.R18, .N1, .N2

R39. A revaluation line posts to the revalued operational account itself and refers to the open item it revalues, so the open item's carrying amount and the control account stay equal (R5); the offsetting line goes to the target. It is an `adjusts` line (`ADR-0026.R10`). A backdated posting into a revalued open period makes that period's revaluation stale; the close reruns it (DS-12).
Source: ADR-0011.R19

R40. Revaluation documents are internal documents (`ADR-0009.R19`); `reverse_and_repost` reverses them by system job; whether a human may reverse them is DS-12. The logic is built in step 8.
Source: ADR-0011.R20

R41. The accounting regime supplies, as configuration with legal sources or `unverified` flags: R31 to R33 for company currency, R35, R36 and R38. The TT99 values are verified before the step 1 gate for the FX rules and before steps 6 and 8 for realized FX and revaluation (`ADR-0003.R10`).
Source: ADR-0011.R21

### Universal journal

R42. A `journal_entry` is the accounting effect of one posted document: `id`, `company_id`, `document_id` (unique; zero or one entry per document), `posting_date`, `document_date`, `posting_period_id`, `fiscal_year_id`, `is_closing_entry` (`ADR-0012.R18`), `close_task_id` (nullable; `ADR-0012.R12`), `database_transaction_number` (the PostgreSQL transaction that created it, set by a trigger, never by a client), `line_count` (the number of lines the posting writes), the nullable `business_unit_trace_id` (the entry's business unit derivation trace, ADR-0069) and `recorded_at`. Posting date, period and fiscal year are copied from the document at posting and never change.
Source: ADR-0014.R1, .N1

R43. A material document (DS-09) belongs to the same document as its entry, so there is zero or one accounting document per material document. An entry whose document has no material document is value-only (revaluations, costing adjustments). `journal_entry.note` holds the document's header note, copied at posting; the entry stays append-only (`ADR-0074.R17`).
Source: ADR-0014.R2, .N1

R44. Manual journal entries are documents of type `general_journal`; moving a balance from one operational account to another (R12) uses documents of type `balance_transfer`. Both are internal documents (`ADR-0009.R3`, `ADR-0009.R19`).
Source: ADR-0014.R3

R45. Within a posting date, journal entries have no business order; displays order by posting date and document number. The order in which costing processes stock movements of one day is defined by DS-09 (`ADR-0007.R10`).
Source: ADR-0014.R4

R46. `journal_line` columns. Keys: `id`, `journal_entry_id`, `company_id`, `line_number` (unique within the entry), and `posting_period_id`, `posting_date` and `fiscal_year_id`, copied from the entry at insert and never changed (`INV-99`). Accounts: `account_id` (operational, postable; R10), `system_account_id` (copied from the account's mapping, frozen after the first posting), `transaction_key_id` (null when the account comes from the document or master data, R68). Side and amounts: `side` (`debit` or `credit`), `is_storno`; `transaction_currency`, `transaction_amount`; `company_currency`, `company_amount`; `group_currency`, `group_amount` (both null when the installation has no group currency); `company_applied_rate_id`, `group_applied_rate_id` (R22). Dimensions, all nullable: `branch_id`, `partner_id`, `item_id`, `warehouse_id`, `cost_center_id`, `project_id`, `salesperson_id`, `tax_code_id`, `cost_object_id`, `fixed_asset_id`. Links, all nullable: `material_document_line_id`, `open_item_id`, `derivation_trace_id`. Text and time: `description` (nullable, data label `internal`), `recorded_at`. Currency columns are foreign keys to `currency.code`, named by currency type; they are the one exception to the `_id` suffix of `ADR-0004.R12`. The primary key is `id`; partitioning follows `ADR-0006.R23`.
Source: ADR-0014.R5, .N1, .N2

R47. Amounts are signed: positive is debit, negative is credit, in every currency. `side` says which turnover a line belongs to; `is_storno` says the line reduces that side's turnover. For a line that is not storno, every non-zero amount has the sign of its side; for a storno line, the opposite sign; both except the case of R48. Balance of anything = `SUM(amount)`; debit turnover = `SUM(amount) WHERE side = 'debit'` (storno lines included, which lowers it); this is the debit that `ADR-0008.R21` refers to.
Source: ADR-0014.R6

R48. An original adjustment line that changes only company or group amounts (realized FX, revaluation, rounding; R21) has `transaction_amount = 0`; its side follows the sign of its company amount, or of its group amount when the company amount is zero, and its other amount may have the opposite sign. The rounding line (R49) is such a line; its transaction currency is that of the item or account it adjusts (R21), and its company and group amounts carry the rounding.
Source: ADR-0014.R7, .N1

R49. Each journal line's company-currency and group-currency amounts are rounded per line. If the rounded lines of an entry do not balance in company currency or in group currency, the posting logic adds one rounding line with transaction amount 0 and the difference in each unbalanced currency, posted to the operational account mapped to the system account `rounding_gain` or `rounding_loss`. The account is chosen by the sign of the company-currency difference, or of the group-currency difference when the company-currency difference is zero. Which operational accounts these map to is declared per company when the company is set up; the localization package proposes defaults. In each currency, the rounding line's absolute value must not exceed half a minor unit times the number of lines of the entry; a larger difference means wrong input, and the command is rejected.
Source: ADR-0006.R20

R50. A reversal document (`ADR-0009.R18`) repeats the original's lines with the same line numbers and negated amounts: by the storno method with the same sides and `is_storno = true`, by the swapped method with opposite sides and `is_storno = false`; the localization package chooses the method (`ADR-0009.R20`). A correction document (`ADR-0009.R23`) has ordinary lines of its own.
Source: ADR-0014.R8

R51. The dimension list is company, branch, account, partner, item, warehouse, cost center, project, salesperson, plus `tax_code_id`, `cost_object_id` and `fixed_asset_id` (`ADR-0025.R1`), and `business_unit_id` (nullable, with `business_unit_source`; in Phase 1 only profit-and-loss lines carry it, derived at posting in a fixed order; ADR-0069). Journal tax lines carry `tax_code_id`, base lines none; the tax subledger `tax_line` links bases to documents (`ADR-0041.R11`, `ADR-0041.R12`). `salesperson_id` refers to a partner with the `employee` role (`ADR-0019.R3`, `ADR-0027.R6`); `cost_center_id` and `project_id` refer to tables that DS-20 defines. Intercompany lines use `partner_id` (R14). Quantities are reached through `material_document_line_id`, not stored on journal lines. `journal_line` also has a nullable `purchase_order_line_id`, with its foreign key from step 5 (`ADR-0030.R3`), and a nullable `journal_line.evidence_method`, only on lines with an open item (`ADR-0048.R18`). A new dimension is a new nullable column, added by ADR.
Source: ADR-0014.R9, .N1

R52. Required columns by the system account's control kind (R5): `receivable` and `payable` lines need `partner_id` and `open_item_id`; `inventory` lines need `item_id` and `warehouse_id`, and `material_document_line_id` when the entry's document has a material document. For the gated kinds these rules read the effective control kind, active only from the company's subledger activation (`ADR-0025.R4`): `cost_object` lines need `cost_object_id`, `fixed_asset` lines `fixed_asset_id`, `loan` lines `partner_id` and `open_item_id`. Lines on `gr_ir` accounts whose document line refers to a purchase order line need `purchase_order_line_id`, enforced by the posting handlers and detected by `INV-37` (`ADR-0030.R3`). An account restricted to one currency accepts only lines in that transaction currency, and `company_currency` must be the company's currency. The `partner_id` of a receivable or payable line is the payer (else the bill-to party, else the sold-to partner) of a sales document and the invoicing party (else the ordered-from partner) of a purchase document, which may differ from the header's `partner_id` (`ADR-0074.R4`). Open items and the one posting path follow `ADR-0026.R3`. Opening balances of control accounts come through typed opening documents, never a general journal (`ADR-0044.R7`, `ADR-0044.R8`, `ADR-0044.R9`).
Source: ADR-0014.R10, .N2

R53. Manual `general_journal` lines on accounts whose effective control kind is `receivable`, `payable` or `loan` are rejected with `manual_posting_to_control_account` unless the flagged setting `journal.manual_posting_to_control_accounts` is true (`ADR-0048.R15`). Manual journal lines on accounts whose effective control kind is `inventory`, `gr_ir`, `cost_object` or `fixed_asset` are always rejected with `manual_posting_to_control_account`, whatever the setting. The posting logic enforces this, not the database.
Source: ADR-0014.R10, .N1

R54. A deferred constraint trigger on `journal_entry` checks once per entry, at commit and when the dispatcher runs `SET CONSTRAINTS ALL IMMEDIATE` before hashing (`ADR-0008.R9`), that the entry has at least two lines and exactly `line_count` lines, that `SUM(transaction_amount)` is zero per transaction currency, that `SUM(company_amount)` is zero, and that group amounts are either all null or sum to zero. Posting code inserts all lines of an entry before the plan is hashed.
Source: ADR-0014.R11

R55. The `BEFORE INSERT` trigger on each line (`journal_line_check_insert`) first sets the account's `has_posting` if it is not yet set (R12), which locks the account row and freezes its mapping. It then takes `company_id`, `posting_period_id`, `posting_date` and `fiscal_year_id` from the line's entry and `system_account_id` from its account, and rejects a line that states different values. It rejects a `line_number` above the entry's `line_count`. It rejects a line whose entry was created in another transaction (`database_transaction_number`), so a posted entry never gains lines. It finds the line's posting area from the control kind (`general` for every line in a special period, `ADR-0012.R4`), reads that area's state row `FOR SHARE`, and rejects the line when the row is missing or `locked`. It checks R47, R48 and the required columns and currencies of R52.
Source: ADR-0014.R12, ADR-0014.R5.N2

R56. `journal_entry` and `journal_line` accept only `INSERT`: triggers reject `UPDATE`, `DELETE` and `TRUNCATE`. Exception: the destruction path of ADR-0079 may blank `journal_entry.note` and `journal_line.description` under the erasure marker of a committed `EraseDataSubject` or `DestroyRetainedPersonalData`; no amount, account, date or key changes, and the CI test that `UPDATE` fails keeps running for every other column and command (`ADR-0079.R6`, `ADR-0079.R7`). Backups are restored with triggers disabled (DS-37). Row-level security on `company_id` follows DS-15.
Source: ADR-0014.R13, .N1

R57. In a plan (`ADR-0008.R12`), journal lines appear with their IDs tokenized, and without `database_transaction_number` and `recorded_at`. Journal rows get their IDs from `context.new_id`, never from a column default.
Source: ADR-0014.R14

R58. Invariants check that every line's `system_account_id` equals its account's mapping (`INV-05`), that every entry balances per currency (`INV-01`), that amounts are at their currency's minor unit (`INV-03`, `ADR-0006.R14`), that each entry has at most one line with a rounding transaction key (`rounding_gain` or `rounding_loss`; `INV-04`), and that the period balance cache equals the lines (`INV-06`).
Source: ADR-0014.R15

R59. Indexes on `journal_line`: `(company_id, account_id, posting_period_id)`, `(company_id, system_account_id, posting_period_id)`, `(company_id, partner_id)` where not null, `(open_item_id)` where not null, `(material_document_line_id)` where not null. On `journal_entry`: `(company_id, posting_date)` for balances as of a date (`ADR-0007.R23`) and `(posting_period_id, close_task_id)` for close task staleness (`ADR-0012.R12`).
Source: ADR-0014.R16

R60. AR/AP subledgers and inventory value are views over `journal_line` and open items (ADR-0026), not separate ledgers. The open item cache equals its lines (`INV-33`). Agents read through the semantic views of schema `query` and the computed module queries; management reporting reads `system_account_turnover` (`ADR-0050.R51`, `ADR-0050.R52`, `ADR-0050.R53`).
Source: ADR-0014.R17

R61. `account_period_balance` caches, per (`company_id`, `account_id`, `posting_period_id`, `transaction_currency`, `is_closing_entry`), debit and credit turnover in transaction, company and group currency, and the cumulative closing balance of the lines with that `is_closing_entry` value up to the period's end; an account's balance is the sum of its closing-entry row and its other row. It is written when a period's `general` area is locked; unlocking deletes that period's rows. A period with no movement has no rows; its balance is the closing balance of the latest earlier row. Balances of unlocked periods are computed from lines. It is never written on the posting path.
Source: ADR-0014.R18

R62. Balance-sheet balances are cumulative at all times: the balance on any date is the sum of all lines up to that date, across fiscal years, so no opening entry is posted at year start. Stored period-closing balances are a cache rebuilt from journal lines (R61).
Source: ADR-0012.R19

R63. The journal tables are not partitioned in Phase 1 (`ADR-0006.R23`).
Source: ADR-0014.R19

### Account determination

R64. The transaction key catalog is `docs/catalogs/transaction-keys.csv`, owned by DS-08, with columns `code`, `name`, `determinants`, `required_system_accounts`, `required_control_kind`, `has_regime_alternatives` (`ADR-0027.R11`), `added_in`, `meaning`. It is loaded into the global table `transaction_key` (no `company_id`; `id` by uuid5 from `"transaction_key:<code>"`, `ADR-0006.R4`); core code refers to keys only through a generated type (`TransactionKey.INVENTORY_POSTING`). It follows the system chart's versioning (R9). The catalog file is authoritative for the set of keys; it includes `cash_in_transit` for money transfers (`ADR-0048.R12`). Transfers need no key: they post between inventory keys (`ADR-0020.R6`); landed cost posts to inventory keys and credits the source account (`ADR-0021.R1`).
Source: ADR-0015.R1, .N1

R65. A key may share its code with a system account (for example `price_difference`, `rounding_gain`) only when every account it requires is that account or a descendant of it; other keys describe the posting (`inventory_posting`, `input_tax`, `income_summary_transfer`). Exception: keys marked `has_regime_alternatives` may also list alternatives that are a regime choice under R67 (`ADR-0027.R11`). CI checks this rule, and checks the catalog like the system chart: unique codes, every required system account exists, determinants from R66, `name` and `meaning` present.
Source: ADR-0015.R2

R66. `determinants` is an ordered list, from most to least significant, drawn from: `valuation_class`, `warehouse`, `item_group`, `partner_group`, `tax_code`, `currency`. An empty list means one account per company. The business unit is not a determinant: it is derived after the account is determined and never feeds account determination (ADR-0069). Valuation classes and item groups are company data seeded from the localization package.
Source: ADR-0015.R3, .N1, ADR-0015.D0

R67. `required_system_accounts` lists one or more system accounts (leaves or nodes); the determined account's system account must be one of them or a descendant. `required_control_kind`, when set, must also match (R13; `INV-16`). An account under the `inventory` node must have control kind `inventory` unless the key names that leaf itself. Where a key allows several accounts (`price_difference`: price differences or stock; `inventory_count_surplus`: pending, inventory differences or income), the choice is the regime's accounting rule, made by its default determination. When `price_difference` determines an inventory account, the invoice posts the difference to `purchase_cost_clearing` and a `landed_cost` moves it to stock (`ADR-0021.R12`).
Source: ADR-0015.R4

R68. Lines whose account the system determines carry their `transaction_key_id` (R46). Lines whose account comes from the document or from master data have none: a payment's bank or cash account, the revalued account in a revaluation (R39), the accounts being closed (`ADR-0012.R18`), the lines of a `balance_transfer` or a `general_journal`, an expense account the user chose on a supplier invoice.
Source: ADR-0015.R5

R69. The valuation area follows the company's costing policy `valuation_area_level`: `company`; `warehouse` (a physical warehouse with its attached transit and goods-sent warehouses, `ADR-0020.R2`); or `site` (a site with all its physical warehouses and their attached transit and goods-sent warehouses, ADR-0068). It is set at company setup and not changeable by command once stock has been posted; a change would be a migration, which `ADR-0020.R16` does not support in Phase 1 (open question). The `warehouse` determinant is independent of that level: a row may name a warehouse to give it its own accounts even when costing is company-wide. A site is no determinant.
Source: ADR-0015.R8, .N1

R70. `account_determination` rows: `id`, `company_id`, `transaction_key_id`, the determinant columns `valuation_class_id`, `warehouse_id`, `item_group_id`, `partner_group_id`, `tax_code_id`, `currency` (each nullable; null means "any"), and `account_id` (a postable operational account of the company). A row may set only determinant columns its key declares; the command checks this. Rows are unique on (company, key, all determinant columns) with `NULLS NOT DISTINCT`.
Source: ADR-0015.R9

R71. Matching: a row matches when every determinant it sets equals the posting's value; a posting with no value for a determinant matches only rows that leave it empty. Among matching rows, compare their determinants in the key's order: the first determinant that one row sets and the other leaves empty decides (for `cost_of_goods_sold`, with valuation class, warehouse, item group: a row with only the valuation class beats a row with warehouse and item group). The result is unique. If nothing matches, the posting is rejected with `account_determination_missing`, naming the key, the determinant values and the command that adds a row.
Source: ADR-0015.R10

R72. Partner keys (`receivable_reconciliation`, `payable_reconciliation`) read the partner's own `receivable_account_id` or `payable_account_id` at posting. Their rows, by `partner_group_id`, only give new partners their default; `CreatePartner` and `UpdatePartner` check the partner's accounts against R67. Changing the account of a partner with open items moves the items by `TransferPartnerOpenItems` (`ADR-0026.R12`). Customer and supplier advances use the same account and are told apart per open item (R15). In the CRM-only deployment profile (`ADR-0052.R1`) `customer_profile.receivable_account_id` and `supplier_profile.payable_account_id` are nullable; they are required while module `ledger` is activated for the company (`module_activation`): the partner commands fill an empty account from the defaults above or fail with `account_determination_missing`, `ActivateModule` for `ledger` does the same for existing profiles, and `INV-38` checks the result; the database does not hold it.
Source: ADR-0015.R11, .N1

R73. Before posting, the core checks the determined account against the key (R67); a mismatch is rejected with `account_determination_mismatch`, naming the key, the account and what was required. `CreateAccountDetermination` and `UpdateAccountDetermination` run the same check when a row is saved; `DeleteAccountDetermination` removes a row, after which postings that matched only that row fail with `account_determination_missing`. A row's change affects only later postings; posted lines keep their account. Changes are audited (DS-36).
Source: ADR-0015.R12

## Invariants

Statements are those of `invariants.csv`. Each row stands once in the module, in the chunk that states the rule its catalog source names.

| Invariant | Name | Check point | Statement | Protects |
| --- | --- | --- | --- | --- |
| `INV-01` | `entry_balances_per_currency` | day | Every journal entry sums to zero per transaction currency and in company currency; its group amounts are either all null or sum to zero. | R23, R54, R58 |
| `INV-04` | `rounding_line_bounded` | day | An entry has at most one line with a rounding key; it has transaction amount 0, posts to the account mapped to `rounding_gain` or `rounding_loss`, and in each currency is at most half a minor unit times the entry's line count. | R49, R58 |
| `INV-05` | `system_account_matches_mapping` | day | Every line's `system_account_id` equals the mapping of its operational account. | R46, R55, R58 |
| `INV-06` | `balance_cache_equals_lines` | day | The period balance cache equals the sum of the journal lines it summarizes. | R58, R61 |
| `INV-08` | `posted_documents_unchanged` | day | The fingerprint of every posted document (its header without state, its versions, journal entries and lines, material lines) equals the fingerprint recorded when the harness first saw it posted; state may change only from posted to reversed. | R56 |
| `INV-16` | `line_passes_key_cross_check` | day | Every journal line with a transaction key posts to an account whose system account is among the key's required system accounts and control kind. | R13, R67, R73 |
| `INV-38` | `partner_accounts_while_ledger_active` | day | While `module_activation` shows `ledger` active for a company, every `customer_profile` of the company has `receivable_account_id` and every `supplier_profile` has `payable_account_id`. | R72 |
| `INV-99` | `journal_line_dates_match_entry` | day | Every journal line's `posting_date` and `fiscal_year_id` equal those of its journal entry. | R46, R55 |

Named by rules of this chunk, with their rows in other chunks: `INV-03` (R58; chunk 3), `INV-33` (R60; chunk 2), `INV-37` (R52; chunk 3).

## Edge cases

| Edge case | Name | Case | Outcome | Protects |
| --- | --- | --- | --- | --- |
| `EC-03` | `rounding_many_small_lines` | A foreign-currency entry with many small lines whose converted amounts need a rounding line. | `must_succeed` | R49 |
| `EC-05` | `foreign_currency_journal` | A journal entry in USD converted at the published book rate. | `must_succeed` | R30 |

## Settings

| Key | Value type | Scopes | Core default | Used by |
| --- | --- | --- | --- | --- |
| `journal.manual_posting_to_control_accounts` | boolean | `regime` | `false` | R53; ADR-0048.R15, ADR-0026.R16 |

The regime values of R31, R32, R36 and R38 (`fx.document_rate.allowed`, `fx.realized_fx_basis`, `fx.revaluation.scope` among them) have no core default (R33).

Reads: `costing.exchange_rate_difference_to_stock` (inventory; boolean; regime and company; core default true), used by R27.

## Conflicts

CONFLICT ADR-0010.R10: ADR-0014.R10 with ADR-0014.R10.N1 and ADR-0048.R15 decides manual journal entries on control accounts, so "decided by DS-06 and DS-25" is not restated and R10 points to R53; the DS-06 DDL and ADR-0010.R5 (with ADR-0035.R7) add `cost_behavior` to the columns the rule lists.
CONFLICT ADR-0010.R1.N1: the table `system_account` stores `parent_id` where the catalog has `parent_code`; ADR-0010.R1.N1 governs and R1 states it.
CONFLICT ADR-0011.R15: the rule's closing paragraph citing ADR-0048.R12 settles backdating and negative balances under `moving_average` for money accounts, so "are DS-25" is not restated (R35).
CONFLICT ADR-0014.R7.N1: the rounding line takes the transaction currency of the item or account it adjusts, never the company currency as such; ADR-0014.R7.N1 with ADR-0011.R2 governs, stated in R48.
CONFLICT ADR-0014.R9: the rule's closing sentence citing ADR-0041.R11 and ADR-0041.R12 decides that journal tax lines carry `tax_code_id` and base lines none, so "decided by DS-23" is not restated (R51).
CONFLICT ADR-0014.R10: the rule's closing paragraph citing ADR-0048.R15 and ADR-0014.R10.N1 govern: the block is the setting `journal.manual_posting_to_control_accounts`, which opens only `receivable`, `payable` and `loan`; the other kinds are always rejected (R53). The setting stays flagged, as ADR-0026.R16 names it.
CONFLICT ADR-0015.R1.N1: the totals of keys given in ADR-0015.D0 are historical; by ADR-0015.R1.N1 the catalog file is authoritative, stated in R64 without a total.
FALSE-POSITIVE ADR-0011.R18.N2: "reversed" is the accounting reversal of a revaluation document on the first day of the next regular period, which the note defines and R38 states; nothing is contradicted.

## Trace

| Source | Where |
| --- | --- |
| ADR-0004.R9 | ref: ADR-0004.R9 |
| ADR-0004.R10 | ref: ADR-0004.R10 |
| ADR-0006.R4 | ref: ADR-0006.R4 |
| ADR-0006.R20 | R49 |
| ADR-0006.R23.N2 | ref: ADR-0006.R23.N2 |
| ADR-0007.R9.N1 | ref: ADR-0007.R9.N1 |
| ADR-0007.R9.N2 | ref: ADR-0007.R9.N2 |
| ADR-0008.R10 | ref: ADR-0008.R10 |
| ADR-0010.D0 | R3, System chart of accounts |
| ADR-0010.R1 | R1 |
| ADR-0010.R1.N1 | R1 |
| ADR-0010.R2 | R2 |
| ADR-0010.R3 | R3 |
| ADR-0010.R4 | R4 |
| ADR-0010.R5 | R5 |
| ADR-0010.R6 | R6 |
| ADR-0010.R7 | R7 |
| ADR-0010.R8 | R8 |
| ADR-0010.R9 | R9 |
| ADR-0010.R9.N1 | R9 |
| ADR-0010.R10 | R10 |
| ADR-0010.R11 | R11 |
| ADR-0010.R12 | R12 |
| ADR-0010.R13 | R13 |
| ADR-0010.R14 | R14 |
| ADR-0010.R14.N1 | R14 |
| ADR-0010.R15 | R15 |
| ADR-0010.R15.N1 | R15 |
| ADR-0010.R16 | R16 |
| ADR-0010.R17 | R17 |
| ADR-0010.R18 | R18 |
| ADR-0010.R19 | R19 |
| ADR-0011.D0 | Multi-currency |
| ADR-0011.R1 | R20 |
| ADR-0011.R2 | R21 |
| ADR-0011.R3 | R22 |
| ADR-0011.R3.N1 | R22 |
| ADR-0011.R3.N2 | R22 |
| ADR-0011.R4 | R23 |
| ADR-0011.R5 | R24 |
| ADR-0011.R6 | R25, R26 |
| ADR-0011.R6.N1 | R27 |
| ADR-0011.R6.N2 | R26, R27 |
| ADR-0011.R8 | R28 |
| ADR-0011.R9 | R29 |
| ADR-0011.R10 | R30 |
| ADR-0011.R11 | R31 |
| ADR-0011.R11.N1 | R31 |
| ADR-0011.R12 | R32 |
| ADR-0011.R13 | R33 |
| ADR-0011.R14 | R34 |
| ADR-0011.R15 | R35 |
| ADR-0011.R16 | R36 |
| ADR-0011.R16.N1 | R36 |
| ADR-0011.R17 | R37 |
| ADR-0011.R18 | R38 |
| ADR-0011.R18.N1 | R38 |
| ADR-0011.R18.N2 | R38 |
| ADR-0011.R19 | R39 |
| ADR-0011.R20 | R40 |
| ADR-0011.R21 | R41 |
| ADR-0012.R4 | ref: ADR-0012.R4 |
| ADR-0012.R19 | R62 |
| ADR-0014.D0 | Universal journal |
| ADR-0014.R1 | R42 |
| ADR-0014.R1.N1 | R42 |
| ADR-0014.R2 | R43 |
| ADR-0014.R2.N1 | R43 |
| ADR-0014.R3 | R44 |
| ADR-0014.R4 | R45 |
| ADR-0014.R5 | R46 |
| ADR-0014.R5.N1 | R46 |
| ADR-0014.R5.N2 | R46, R55 |
| ADR-0014.R6 | R47 |
| ADR-0014.R7 | R48 |
| ADR-0014.R7.N1 | R48 |
| ADR-0014.R8 | R50 |
| ADR-0014.R9 | R51 |
| ADR-0014.R9.N1 | R51 |
| ADR-0014.R10 | R52, R53 |
| ADR-0014.R10.N1 | R53 |
| ADR-0014.R10.N2 | R52 |
| ADR-0014.R11 | R54 |
| ADR-0014.R12 | R55 |
| ADR-0014.R13 | R56 |
| ADR-0014.R13.N1 | R56 |
| ADR-0014.R14 | R57 |
| ADR-0014.R15 | R58 |
| ADR-0014.R16 | R59 |
| ADR-0014.R17 | R60 |
| ADR-0014.R18 | R61 |
| ADR-0014.R19 | R63 |
| ADR-0015.D0 | R66, Account determination |
| ADR-0015.R1 | R64 |
| ADR-0015.R1.N1 | R64 |
| ADR-0015.R2 | R65 |
| ADR-0015.R3 | R66 |
| ADR-0015.R3.N1 | R66 |
| ADR-0015.R4 | R67 |
| ADR-0015.R5 | R68 |
| ADR-0015.R8 | R69 |
| ADR-0015.R8.N1 | R69 |
| ADR-0015.R9 | R70 |
| ADR-0015.R10 | R71 |
| ADR-0015.R11 | R72 |
| ADR-0015.R11.N1 | R72 |
| ADR-0015.R12 | R73 |
