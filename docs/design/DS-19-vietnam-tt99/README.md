# DS-19: Vietnam package draft (l10n_vn, regime tt99)

Draft package data decided by [ADR-0039](../../adr/0039-vietnam-package-tt99.md); the ADR wins if this folder disagrees. The layout is the DS-14 package layout; at step 1 the folder moves unchanged to `l10n/l10n_vn/` (DS-18).

| File | Content |
| --- | --- |
| [manifest.yaml](manifest.yaml) | Package manifest, with the legal forms that select chart rows |
| [settings.yaml](settings.yaml) | Package rules for every regime: reversal, default posting dates, attachment retention, invoice issuance and the e-invoice requirement, tax settings, the data-processing policy and the incoming e-invoice formats ([ADR-0057](../../adr/0057-document-intake-and-extraction.md) rule 30) |
| [regimes/tt99/chart_template.csv](regimes/tt99/chart_template.csv) | All 184 TT99 codes, the package's detail accounts and 999, mapped to system accounts; `condition`; `cost_behavior`; the key is (`code`, `condition`): code 4111 has one row for `legal_form=joint_stock` and one for the other legal forms |
| [regimes/tt99/account_determination.csv](regimes/tt99/account_determination.csv) | Default determination for every transaction key, with a note on each interim choice |
| [regimes/tt99/unreached_system_accounts.csv](regimes/tt99/unreached_system_accounts.csv) | System accounts the template does not reach, and why (ADR-0010 rule 17) |
| [regimes/tt99/valuation_classes.csv](regimes/tt99/valuation_classes.csv), [item_groups.csv](regimes/tt99/item_groups.csv), [partner_groups.csv](regimes/tt99/partner_groups.csv) | Seed codes used by the determination |
| [regimes/tt99/close_checklist.yaml](regimes/tt99/close_checklist.yaml) | Period pattern and special periods; tasks come in step 8 |
| [regimes/tt99/settings.yaml](regimes/tt99/settings.yaml) | Regime rules: FX, closing, movement types, landed cost, counts, production |
| [tax/](tax/tax_codes.csv) | Tax codes with their package kinds ([package_kinds.csv](tax/package_kinds.csv)), dated rates, tax matrix, item and partner tax groups, the 01/GTGT form ([ADR-0041](../../adr/0041-tax-engine.md)), and the non-cash payment condition ([deductibility_rules.yaml](tax/deductibility_rules.yaml); [ADR-0053](../../adr/0053-core-neutrality.md)) |
| [i18n/vi/unit_names.csv](i18n/vi/unit_names.csv) | Statutory Vietnamese names of the core units for e-invoice lines and statutory prints, terminology keys `uom.<code>.name`, all `unverified`; the length setting `documents.unit_name_max_length` is in [settings.yaml](settings.yaml), empty until verified ([ADR-0056](../../adr/0056-multiple-units-of-measure.md) rule 18); checked against `catalogs/units.csv` |

Bases: TT99 rows that only restate Appendix II carry it as legal source (not yet verified). Every package choice is `unverified` and cites an open question, except the two author decisions (purchase invoice posting date; rounding to 515 and 635). Production refuses unverified content (ADR-0016 rule 12).

Check (needs PyYAML), from the repository root:

    python3 -I docs/reviews/2026-11-14-design-validation/lab/check_package.py docs docs/design/DS-19-vietnam-tt99 tt99
    python3 -I docs/reviews/2026-11-14-design-validation/lab/check_package.py --self-test docs docs/design/DS-19-vietnam-tt99 tt99

Both must pass.
