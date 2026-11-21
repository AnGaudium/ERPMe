# DS-14: Localization package format

Field-level format for [ADR-0016](../adr/0016-localization-package-structure.md). The ADR's rules win if this file disagrees. Formats of tax, e-invoice, bank, report and print components are owned by DS-23, DS-24, DS-25, DS-26 and DS-27 and added here when they are designed.

## Directory layout

```
l10n/l10n_vn/
  manifest.yaml
  regimes/
    tt99/
      chart_template.csv           # package template: operational accounts (ADR-0010)
      account_determination.csv    # package template: default determination (ADR-0015)
      valuation_classes.csv        # package template
      item_groups.csv              # package template
      partner_groups.csv           # package template (ADR-0039)
      unreached_system_accounts.csv  # package template: ADR-0010 rule 17 statement (ADR-0039)
      close_checklist.yaml         # package template (ADR-0012)
      reports/<code>/              # package rules: <effective_from>.yaml and .csv per statement or book (ADR-0049)
      print_templates/<code>/      # package template: the regime's print forms (ADR-0049)
      settings.yaml                # package rules: regime settings (ADR-0016 rules 9-12)
  settings.yaml                    # package rules for every regime (accounting_regime null)
  numbering.yaml                   # package template: numbering formats (ADR-0009)
  print_templates/<code>/          # package template: print templates for every regime (ADR-0049)
  i18n/
    vi/terminology.json            # overrides of core terms
    vi/l10n_vn.json                # package strings
  code/                            # package code: Python package l10n_vn, interfaces only
  tests/
    golden/                        # package tests: golden scenarios (DS-16)
```

## Manifest

```yaml
code: l10n_vn
name: Vietnam
country: VN
version: 0.1.0
core_version: ">=0.1,<0.2"
license: AGPL-3.0
languages: [vi]
regimes:
  - code: tt99
    name: Circular 99/2025/TT-BTC
legal_forms:                     # optional; select chart template rows (ADR-0039 rule 5)
  - code: joint_stock
    name_en: Joint-stock company
    name_vi: Công ty cổ phần
    legal_source: {document: "<law>", article: "<article>", date: "<date>"}
components:
  chart_template: regimes/{regime}/chart_template.csv
  account_determination: regimes/{regime}/account_determination.csv
  valuation_classes: regimes/{regime}/valuation_classes.csv
  item_groups: regimes/{regime}/item_groups.csv
  partner_groups: regimes/{regime}/partner_groups.csv
  unreached_system_accounts: regimes/{regime}/unreached_system_accounts.csv
  close_checklist: regimes/{regime}/close_checklist.yaml
  reports: regimes/{regime}/reports
  print_templates: [print_templates, regimes/{regime}/print_templates]
  regime_settings: [settings.yaml, regimes/{regime}/settings.yaml]
  numbering: numbering.yaml
  translations: i18n
```

A test package ([ADR-0053](../adr/0053-core-neutrality.md) rule 9) adds `is_test_package: true`. Its entries carry the basis `test_fixture` (`basis` in CSV files, `status: test_fixture` in YAML), which CI rejects in any other package. The loader refuses a test package at deploy time in a `production` installation; gate tests set the environment in the harness instead.

## Basis fields (every template entry and rule)

| Field | When |
| --- | --- |
| `legal_source` | `{document, article, date}` of the law the entry follows |
| `verified_by`, `verified_on` | Set by the author when he has checked the legal source (ADR-0003 R10) |
| `author_decision` | `{reference, date, by}`: the open question or ADR the author's decision closed |
| `status: unverified` + `open_question` | Neither of the above yet |
| `company_decision` | `{by, date}`: a company changed its copy of a template entry (company rows only) |

In CSV templates the basis is six columns: `basis` (`legal_source`, `author_decision` or `unverified`), `basis_document`, `basis_article`, `basis_date`, `verified_by`, `verified_on`; for `author_decision` the document column holds the open question or ADR reference, and for `unverified` the open question.

## Chart template (CSV)

| Column | Meaning |
| --- | --- |
| `code` | Operational account code, e.g. `1561` |
| `name_en` | English name |
| `name_<language>` | Name in each declared language, e.g. `name_vi` |
| `parent_code` | Operational parent, empty for top level |
| `is_postable` | `true` or `false` |
| `system_account` | System account code for postable accounts (ADR-0010 rule 11) |
| `currency` | Optional currency restriction (ADR-0010 rule 10) |
| `condition` | Empty, `legal_form=<value>` or `legal_form!=<value>`: the row applies only to companies of that legal form; each legal form must yield a valid tree ([ADR-0039](../adr/0039-vietnam-package-tt99.md) rule 5) |
| `cost_behavior` | `variable` or `fixed` on every production cost account, empty otherwise ([ADR-0035](../adr/0035-production-costing.md) rule 7; [ADR-0039](../adr/0039-vietnam-package-tt99.md) rule 6) |
| basis columns | As above |

## Account determination (CSV)

| Column | Meaning |
| --- | --- |
| `transaction_key` | Code from the transaction key catalog |
| `valuation_class`, `warehouse`, `item_group`, `partner_group`, `tax_code`, `currency` | Determinants; empty means any ([ADR-0015](../adr/0015-account-determination.md) rule 9). Templates use seed codes for valuation class, item group and partner group, and leave warehouse, tax code and currency empty |
| `account_code` | Operational account code of the regime's chart template |
| basis columns | As above |
| `note` | Why an interim choice was made and its alternatives |

Seed lists (`valuation_classes.csv`, `item_groups.csv`, `partner_groups.csv`) have `code`, `name_en`, `name_<language>` and the basis columns. The TT99 content is in [DS-19-vietnam-tt99](DS-19-vietnam-tt99/README.md) ([ADR-0039](../adr/0039-vietnam-package-tt99.md)). `unreached_system_accounts.csv` has `system_account` and `reason`. `close_checklist.yaml` carries `period_pattern` and `special_period_count` with one basis, and the tasks of ADR-0012. Task fields: below and [ADR-0049](../adr/0049-statutory-reporting-and-printing.md) rule 23.

## Tax files (CSV)

At package level under `tax/` ([ADR-0041](../adr/0041-tax-engine.md) rules 1–3, 19–20):

| File | Columns |
| --- | --- |
| `tax_codes.csv` | `code`, names, `tax_kind` (`vat`, `sales_tax`, `excise`, `customs_duty`, `other`), `package_kind` (optional), `direction`, `calculation`, `sequence`, `base_includes` (core or package kinds separated by `;`), `transaction_key`, `deductibility`, `import_treatment`, `fixed_asset_code`, and, until DS-24 defines its own file, the e-invoice add-on's `e_invoice_label` ([ADR-0053](../adr/0053-core-neutrality.md) rules 2, 12) |
| `package_kinds.csv` | `code` (never a core kind's code), `tax_kind` (the core kind it belongs to), names, basis columns ([ADR-0053](../adr/0053-core-neutrality.md) rule 2) |
| `deductibility_rules.yaml` | A YAML list: `code`, `condition_type`, `applies_to` (`tax_kind`, `directions`), `parameters` (the condition type's schema), `effective_from`, and the basis fields of regime settings. Per tax kind and direction, the entry with the latest `effective_from` on or before the tax date is in force, across codes; an entry with `condition_type: none` and no parameters ends the rule before it; two entries may not share tax kind, direction and `effective_from` ([ADR-0053](../adr/0053-core-neutrality.md) rule 3 and its notes) |
| `tax_rates.csv` | `tax_code`, `effective_from`, `rate_percent` |
| `tax_matrix.csv` | `direction`, `tax_treatment`, `item_tax_group`, `effective_from`, `tax_codes` (separated by `;`), optional `is_adjustable` ([ADR-0080](../adr/0080-tax-treatment-determination.md) rule 2; a package not yet reworked keeps the column name `partner_tax_group`, read as `tax_treatment` until its rework) |
| `item_tax_groups.csv`, `tax_treatments.csv`, `partner_tax_statuses.csv` | `code`, names, and for treatments the `directions` they apply to ([ADR-0080](../adr/0080-tax-treatment-determination.md) rule 1; `partner_tax_groups.csv` is read as `tax_treatments.csv` until a package's rework) |
| `tax_treatment_rules.csv` | `direction`, `document_type`, `ship_from_country`, `ship_to_country`, `is_tax_zone`, `partner_tax_status`, `item_kind` (each empty for any), `priority`, `effective_from`, `tax_treatment` (empty ends a rule), optional `is_adjustable`, basis ([ADR-0080](../adr/0080-tax-treatment-determination.md) rule 3) |
| `returns/<form>.csv` | `box`, labels, `source`: `base:<code>`, `tax:<code>`, `deductible:<code>`, `prior_decrease`, `prior_increase`, `formula:<expression over [box]>` with `+`, `-`, `pos()`, `neg()`, or `carry:<box>`, separated by `;` |

Every row carries the basis columns.

## Regime settings (YAML)

Each entry is one dated rule. The values below show the format only; the Vietnam values and their bases are set in DS-19.

```yaml
- key: reversal.method                 # registered by the core with its schema and date basis
  value: storno
  effective_from: 2026-01-01
  status: unverified
  open_question: "(DS-05, DS-06) Reversal: storno (negative amounts) or swapped debit and credit?"

- key: fx.document_rate.allowed        # a setting with options a company may choose (rule 11)
  value: {options: [never, within_tolerance], default: never, tolerance_percent: "1"}
  effective_from: 2026-01-01
  status: unverified
  open_question: "(DS-10, DS-19) Which published quote ... and may a document carry an approximate rate?"

- key: fx.revaluation.scope           # per system account; excluded_open_item_kinds has no core default (ADR-0011 rule 18)
  value: {per_open_item: [receivable_trade], per_balance: [cash_in_bank], default: none, excluded_open_item_kinds: [advance]}
  effective_from: 2026-01-01
  status: unverified
  open_question: "(DS-10, DS-12, DS-19) Under TT99, are foreign-currency items revalued ..."

- key: example.verified_setting
  value: {...}
  effective_from: 2026-01-01
  legal_source: {document: "<document>", article: "<article>", date: "<date>"}
  verified_by: "<author's name>"
  verified_on: "<date>"
```

## Report definitions (YAML and CSV)

Per regime under `regimes/<regime>/reports/<code>/`, one pair of files per definition version ([ADR-0049](../adr/0049-statutory-reporting-and-printing.md) rules 2–12). The version used is the latest whose `effective_from` is on or before the report's end date. A version a company has filed never changes.

`<effective_from>.yaml` of a statement:

```yaml
# example: TT99's balance sheet, format only (the content is DS-19 data)
code: b01_dn                     # lowercase, non-alphanumerics as _ (ADR-0004 rule 5)
kind: statement
form: B01-DN                     # the official label, data
name_en: Balance sheet
name_vi: "<name>"
effective_from: 2026-01-01
is_fileable: true
comparative: day_before_from     # day_before_from | prior_year_range | none
term_months: 12                  # horizon of term=short and term=long; required when a term uses term=, no core default
display_rounding: half_away_from_zero   # optional; the default
coverage: [asset, liability, equity]
exports: {xml: {template: b01_dn.xml.j2, schema: b01_dn.xsd}}   # optional
field_classes: []
status: unverified
open_question: "(DS-26, DS-27) Statutory reporting and printing choices"
```

A cash flow statement adds `cash_flow: {method: direct, cash_accounts: "<selector>"}`.

`<effective_from>.csv` of a statement:

| Column | Meaning |
| --- | --- |
| `line` | Line code, unique in the version |
| `kind` | `heading`, `line` or `check` (a formula that must be zero) |
| `level` | Indentation, 0 for top level |
| `label_en`, `label_<language>` | Labels |
| `note` | Reference to the notes to the statements, optional |
| `source` | Terms separated by `;` and summed, a `-` prefix subtracting: `account:<selector>:<measure>[:<key>=<value>]...`, `cash_in:<selector>`, `cash_out:<selector>`, `report:<code>:<line>`, `carry:<line>` (over the header's comparative range; not with `comparative: none`), `formula:<expression>` |
| basis columns | As above |

- **Selectors:** operational codes joined by `|`, each with its descendants in the company's tree; `!<code>` removes one with its descendants.
- **Measures:** `opening`, `opening_debit`, `opening_credit`, `debit_turnover`, `credit_turnover`, `change`, `closing`, `closing_debit`, `closing_credit`.
- **Options:** `by=account|partner|partner_kind` (required on `opening_debit`, `opening_credit`, `closing_debit` and `closing_credit`; no core default), `kind=<kinds joined by |>`, `term=short|long` with `undated=short|long` (required with `term`), `closing_entries=exclude`, `counterpart=<selector>`.
- **Formulas:** `[line]`, `+`, `-` (the ASCII hyphen-minus, the only minus sign), parentheses, `pos()`, `neg()`.

Example rows (format only; the TT99 lines are DS-19 data):

```csv
line,kind,level,label_en,label_vi,note,source,basis,basis_document,basis_article,basis_date,verified_by,verified_on
131,line,2,Short-term trade receivables,<label>,,account:131:closing_debit:by=partner_kind:term=short:undated=short,unverified,"(DS-26, DS-27) Statutory reporting and printing choices",,,,
312,line,2,Advances from customers,<label>,,account:131:closing_credit:by=partner_kind:kind=advance|payment_on_account,unverified,"(DS-26, DS-27) Statutory reporting and printing choices",,,,
c01,check,0,Total assets equal total sources,,,formula:[270]-[440],unverified,"(DS-26, DS-27) Statutory reporting and printing choices",,,,
```

A book's header has the statement's names, dates and basis, plus `row_source` (`journal_line`, `material_document_line`, `stock`, `open_item`, `production_order_period_cost`), `scope` (a selector), `filters`, `group_by`, `rows` (`line` or `counterpart`) and `period` (`range` or `as_of`). Its CSV has `column`, `label_en`, `label_<language>`, `field` (a field of the row source's result schema, or `debit`, `credit`, `counterpart_accounts`, `running_balance`, `quantity_in`, `quantity_out`, `running_quantity`), `total` (`sum` or empty) and the basis columns. Rows are ordered, and paged by a cursor over the same keys, as [ADR-0049](../adr/0049-statutory-reporting-and-printing.md) rule 10 says: for `journal_line` and `material_document_line` rows by posting date, document number, document type, `journal_entry.id` (or `material_document.id`) and line number, a counterpart pair's rows by the counterpart line's number; `open_item` rows by the group fields, then the open item's ID; `stock` rows by the group fields, then `item_id`, `warehouse_id`, `owner_partner_id` and `lot_id` or `serial_number_id` where exposed; `production_order_period_cost` rows by the group fields, then `production_order_id`, `posting_period_id` and the cost component. In every key null sorts before any value, and the cursor compares it that way (null equals null, null is less than any value).

A return form (`tax/returns/<form>.csv`) may gain a header `<form>.yaml` with `effective_from` and `exports` at its next version ([ADR-0049](../adr/0049-statutory-reporting-and-printing.md) rule 21).

## Print templates

`print_templates/<code>/` at package level, or `regimes/<regime>/print_templates/<code>/` for a regime's form, which wins over a package-level template of the same code ([ADR-0049](../adr/0049-statutory-reporting-and-printing.md) rules 24–29):

| File | Content |
| --- | --- |
| `template.yaml` | `code`; `subject` (a printable document type, a registered query, `report:<code>` or `partial`); `audience` (`external` or `internal`); `contract_version` (`major.minor`); `languages`; `field_classes` (internal templates only); `is_default`; basis |
| `template.html` | Jinja2 HTML, sandboxed and autoescaped; formatting filters; `t()` for catalog strings; only `asset:` references |
| `style.css` | Optional CSS for WeasyPrint |

## Close checklist tasks

Each entry of `tasks` in `close_checklist.yaml` ([ADR-0049](../adr/0049-statutory-reporting-and-printing.md) rule 23) has `code`, `area`, `kind`, `runs`, `is_required`, `is_sequential`, `depends_on`, `applies_to` (`every_period`, `fiscal_year_end`, `special_period`, `fiscal_year_first_period`), `parameters`, `label_en`, `label_<language>` and the basis fields:

```yaml
tasks:
  - code: balance_carry_forward
    area: general
    kind: job
    runs: RunBalanceCarryForward
    is_required: true
    is_sequential: false
    depends_on: []
    applies_to: fiscal_year_first_period
    parameters: {from_account: "<code>", to_account: "<code>"}
    label_en: Carry last year's result to earlier years
    status: unverified
    open_question: "(DS-26, DS-27) Statutory reporting and printing choices"
```

## Loader errors

The package loader reports these at deploy time, when an operator loads a package version. They are not command errors and have no HTTP status; the load fails as a whole and nothing of the version is installed ([ADR-0016](../adr/0016-localization-package-structure.md) rule 13). The loader also refuses a test package in a `production` installation (Manifest, above).

| Code | When | Rule |
| --- | --- | --- |
| `regime_setting_in_use` | A new version changes the value of a setting row, or drops a row, that a company on the regime has used for a posted document dated on or after the row's `effective_from`; the change must be a new row with a later `effective_from` | [ADR-0016](../adr/0016-localization-package-structure.md) rule 13 |
| `deductibility_rule_overlap` | Two deductibility rules would apply to one (`tax_kind`, direction) on the same date | [ADR-0053](../adr/0053-core-neutrality.md) rule 3 |
| `report_definition_in_use` | A new version changes a report definition version that a company has filed; a correction is a new version with a later date | [ADR-0049](../adr/0049-statutory-reporting-and-printing.md) rule 2 |

## Package code for prints

`AmountInWords`: `amount_in_words(amount, currency, language) -> str`, the amount in words in the package's languages; the core ships English. Where no installed implementation covers the print language, prints show the amount in numerals only ([ADR-0049](../adr/0049-statutory-reporting-and-printing.md) rule 25).
