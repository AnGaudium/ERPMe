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
      settings.yaml                # package rules: regime settings (ADR-0016 rules 9-12)
  settings.yaml                    # package rules for every regime (accounting_regime null)
  numbering.yaml                   # package template: numbering formats (ADR-0009)
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
  regime_settings: [settings.yaml, regimes/{regime}/settings.yaml]
  numbering: numbering.yaml
  translations: i18n
```

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

Seed lists (`valuation_classes.csv`, `item_groups.csv`, `partner_groups.csv`) have `code`, `name_en`, `name_<language>` and the basis columns. The TT99 content is in [DS-19-vietnam-tt99](DS-19-vietnam-tt99/README.md) ([ADR-0039](../adr/0039-vietnam-package-tt99.md)). `unreached_system_accounts.csv` has `system_account` and `reason`. `close_checklist.yaml` carries `period_pattern` and `special_period_count` with one basis, and the tasks of ADR-0012.

## Tax files (CSV)

At package level under `tax/` ([ADR-0041](../adr/0041-tax-engine.md) rules 1–3, 19–20):

| File | Columns |
| --- | --- |
| `tax_codes.csv` | `code`, names, `tax_kind`, `direction`, `calculation`, `sequence`, `base_includes` (kinds separated by `;`), `transaction_key`, `deductibility`, `import_treatment`, `fixed_asset_code`, `e_invoice_label` |
| `tax_rates.csv` | `tax_code`, `effective_from`, `rate_percent` |
| `tax_matrix.csv` | `direction`, `partner_tax_group`, `item_tax_group`, `effective_from`, `tax_codes` (separated by `;`) |
| `item_tax_groups.csv`, `partner_tax_groups.csv` | `code`, names, and for partner groups the `directions` they apply to |
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

- key: example.verified_setting
  value: {...}
  effective_from: 2026-01-01
  legal_source: {document: "<document>", article: "<article>", date: "<date>"}
  verified_by: "<author's name>"
  verified_on: "<date>"
```
