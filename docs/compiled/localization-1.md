Module: localization    Chunk: 1 of 2    Source ADRs: ADR-0016, ADR-0039
Build step(s): 1    Generated from index: 30d5706    Compiled by: Claude Fable 5.2, 2026-11-21

# Compiled spec: `localization`, chunk 1

## Purpose

`localization` owns the structure of a localization package (`l10n_<country>`), its loader, the table `regime_setting`
and the rules by which the core reads package content. This chunk states the package structure, the basis of every
entry, regime settings, loading and versions, package code, translations, discovery, and the layout of the `l10n_vn`
package. It states the loader's and the package format's rules only: country values (rates, account numbers, legal
references) are flagged content of the package files and are never restated here. The core holds no country rule.

## Entities and tables

DDL: `docs/design/DS-05-platform.sql`.

| Table | Meaning | Key | Parent | Owner |
| --- | --- | --- | --- | --- |
| `regime_setting` | A dated package rule of one key, for one regime or for every regime of a package; installation data (R17) | `id` (R26); `uq_regime_setting_identity` on (`localization_package`, `accounting_regime`, `key`, `effective_from`) | the package (no table) | localization |

Reads: `company` (`localization_package`, `accounting_regime`), `currency` (`rounding_mode`), `setting_value`, `setting_definition`, `tax_code`, `derivation_trace` (its `inputs` name the `regime_setting` key and `effective_from`, ADR-0027.R3).

## Commands and queries

Where a cell says "not stated", the source units of this chunk do not state it.

| Name | Actor and authorization | Input | Effect | Events | Error codes |
| --- | --- | --- | --- | --- | --- |
| `UpdateCompanyRegimeOption` (command) | authorization area `regime_option`, level full (`authorization-areas.csv`; ADR-0063.R28); audited (DS-36) | a company, a key, the option, `effective_from` | writes the company's choice as a `setting_value` row of scope `company` (R21) | not stated | not stated |
| `ListLocalizationPackage` (query) | not stated; used by agents | not stated | lists the packages (R42) | none | not stated |
| `ListRegimeSetting` (query) | not stated; used by agents | company, date | every setting in force with its basis (R42) | none | not stated |

Not commands: the accessor `regime_setting(company, key, date)` (R19; errors `regime_configuration_missing`, `regime_setting_unverified`); `registry.contract.get_setting` (R18); the package loader (R24; loader error `regime_setting_in_use`, reported at deploy time); the published interfaces of package code (R31 to R34). `CreateCompany` records a company's package and regime (R3).

## Rules

### Package and manifest

R1. A localization package (`l10n_<country>`) is a directory with a manifest, data files for its components and, only where a component needs behavior, Python code behind interfaces the core defines. It holds everything the law of its country governs; the core holds none of it. Package content is either a package template, copied into a company when it is set up and then owned by the company, or a package rule, read live from the installed package version and dated. A rule that a posting has used never changes value. Translations and accounting terminology for the package's languages ship in the package, over the core's English source.
Source: ADR-0016.D0

R2. A package is a directory `l10n/<code>/` in the repository (location fixed by DS-18) with `code` `l10n_<country>` (ADR-0004.R8). Its `manifest.yaml` declares `code`, `name`, `country` (ISO 3166-1 alpha-2), `version` (semver), `core_version` (the range of core versions it works with), `license` (AGPL-3.0 for packages in this repository, as the core), `languages` (BCP 47), `regimes` (each with a `code` such as `tt99` and a `name`), `legal_forms`, which select chart template rows (ADR-0039.R5), and its component files. Format and example: `docs/design/DS-14-localization-package.md`.
Source: ADR-0016.R1

R3. A company uses exactly one package and one of its regimes, chosen when the company is created (`CreateCompany`); `company.localization_package` and `company.accounting_regime` record them. Changing regime later is out of scope for Phase 1.
Source: ADR-0016.R2

R4. An installation has one version of each package. The package's code ships with the application build; its data is loaded when the application is deployed, with the database migrations (DS-37). At startup the application refuses to run if a package's loaded data version differs from its code version. Downgrades are refused.
Source: ADR-0016.R3

R5. In Phase 1, packages live only in this repository and go through the same review as the core (ADR-0003.R5); packages from elsewhere come after Phase 1.
Source: ADR-0016.R4

### Components

R6. The components of a package, each with its kind and format owner:
- package template: the operational chart template per regime, mapped to system accounts (ADR-0010, DS-19);
- package template: default account determination per regime, valuation classes, item groups, partner groups and the statement of unreached system accounts (ADR-0015, DS-19; ADR-0039.R4, ADR-0039.R7);
- package template: close checklist template, period pattern and special period count (ADR-0012);
- package template: numbering formats per document type (ADR-0009);
- package template: print templates (DS-27; format in ADR-0049.R24);
- package rule: regime settings, which are FX rules, reversal method, closing rules, default posting dates and rounding of named calculations (R17 to R22);
- package rule: tax codes, date-effective rates, the tax matrix and tax return formats (DS-23; ADR-0041.R1, ADR-0041.R2, ADR-0041.R3, ADR-0041.R19, ADR-0041.R20), with `tax/package_kinds.csv` and `tax/deductibility_rules.yaml` (ADR-0053.R2, ADR-0053.R3);
- package rule: statutory reports and books (DS-26; formats in ADR-0049.R2 to ADR-0049.R12);
- package rule: default data labels and personal data rules (DS-32), which include the package rules named `data_protection`: consent purposes, request deadlines, public mail domains, name stop words and fold pairs, and the phone rule (ADR-0052.R24);
- translation: translations and accounting terminology (R35 to R41);
- package code: e-invoice adapter, bank statement readers, exchange rate fetchers (DS-24, DS-25, ADR-0011) and `AmountInWords`, the amount in words on prints (ADR-0049.R25);
- package test: golden scenarios and synthetic dataset parameters, which include the business profiles and the tax ID generator of the synthetic dataset (DS-16, DS-17; ADR-0053.R15).
Source: ADR-0016.R5, ADR-0016.R5.N1, ADR-0016.R5.N2

R7. E-invoice labels are not package content: they are data of the e-invoice add-on (ADR-0053.R12).
Source: ADR-0016.R5.N1

### Basis of an entry

R8. Every entry of a package template or package rule carries a basis: `legal_source` (document, article, effective date), or `author_decision` (the open question or ADR it closed, the date and the author's name), or `status: unverified` with its `open_question`. A legal source becomes verified with `verified_by` and `verified_on`. The basis is kept when the entry is copied, so unverified content is visible wherever it is used. The other bases are `company_decision` (R11) and `test_fixture` (R10).
Source: ADR-0016.R6, ADR-0016.D0

R9. The basis fields are set only by the author, or in a change the author merges citing his decision. An agent may find and quote a source but never sets them on its own (ADR-0003.R10; `docs/runbook/escalation.md`, unverified legal rules).
Source: ADR-0016.R6

R10. A test package (manifest `is_test_package: true`) uses the basis `test_fixture`, which counts as verified for R23. The loader refuses a test package at deploy time in a `production` installation; gate tests set the environment in the harness instead (ADR-0053.R9).
Source: ADR-0016.R6

### Package templates

R11. A package template is copied into company-owned rows when the company is set up, with the package version and each entry's basis; the company may then change its copy. Changing a copied entry sets its basis to `company_decision` with the actor and date, and keeps the package's original basis for reference.
Source: ADR-0016.R7, ADR-0016.R6

R12. Whether an entry that a company changed from an `unverified` package entry counts as a localization rule the pilot uses under ADR-0003.R11 is an open question for the author. Interim, flagged: it does not, because the company has decided it under its own accounting policy.
Source: ADR-0016.R7

R13. The close checklist is copied into a company checklist template at setup, from which each period's tasks are copied (ADR-0012.R11).
Source: ADR-0016.R7

R14. A later package version never changes a company's copy. How template changes are offered to companies (listing differences and applying them by command) is designed with the upgrade policy (DS-37).
Source: ADR-0016.R7

R15. The package's statements and books are rules read live. A company's own statements and books are company definitions beside them and never change a package definition (ADR-0049.R11).
Source: ADR-0016.R7.N1

R16. Rounding modes of currencies live in `currency.rounding_mode` (ADR-0006.R17). A package proposes values, and the installation keeps one value per currency, set by the operator when packages differ. Only modes for named calculations, such as tax per line, are regime settings.
Source: ADR-0016.R8

### Regime settings

R17. A regime setting is a row of `regime_setting`: `localization_package`, `accounting_regime` (null for every regime of the package), `key`, `value` (JSON validated by the schema the core registers for that key, or null to end an earlier row), `effective_from` (a business date), its `basis` (JSON, R8) and `recorded_at`; its `id` is computed by the loader (R26). Its identity is (package, regime, key, `effective_from`). For a company, a row for its regime wins over a row for every regime with the same key and date.
Source: ADR-0016.R9

R18. The core registers every key it reads, with its value schema, its `date_basis` (which date selects the row: `posting_date` by default, ADR-0007.R8) and, where the law lets a company choose, the options the regime may permit. This registration is the settings registry for every scope: each definition also states its scope, its core default or `fail_closed`, hard bounds, which direction is tighter, the leaf whose holder changes it, when a change takes effect and which evidence a loosening outdates. The catalog is `catalogs/settings.csv`, and `registry.contract.get_setting` reads every scope (ADR-0063.R1, ADR-0063.R4).
Source: ADR-0016.R10, ADR-0016.R10.N2

R19. The core reads a regime setting only through `regime_setting(company, key, date)`, which returns the row in force on that date. If there is none, or its value is null, the read of a key registered `fail_closed` fails the operation with `regime_configuration_missing`, naming the key, regime, date and how to fix it (ADR-0011.R13); a key registered with a core default reads that default (ADR-0053.R1.N2, ADR-0063.R1).
Source: ADR-0016.R10

R20. `documents.issuance_without_delay` has a core default, false, instead of `regime_configuration_missing` (ADR-0053.R8). `documents.e_invoice_required` is handled the same way: no row, or a document type missing from its map, reads false (ADR-0053.R8.N1). `data_processing.policy` is registered without a core default: a regime that declares none fails closed with `regime_configuration_missing`, and every package states it, the test package included (ADR-0057.R20). Deductibility conditions are package rules of core-registered condition types (ADR-0053.R3).
Source: ADR-0016.R10, ADR-0016.R10.N1

R21. Where the regime permits options, such as whether an approximate rate may be used, the regime setting lists them with a default, and a company picks one with `UpdateCompanyRegimeOption`, audited (DS-36). The choice is a `setting_value` row (scope `company`, append-only, with old value, actor and reason) dated by `effective_from`, and is read through the same accessor by the key's date basis, so a backdated posting uses the choice in force on its date. `UpdateCompanyRegimeOption` follows the asymmetric change path, and an option declared `period_start` takes effect only from the first day of a posting period (ADR-0063.R2, ADR-0063.R3). A company cannot change a setting the regime does not open to it.
Source: ADR-0016.R11, ADR-0016.R11.N1

R22. Enabling an unverified rule is audited as a tracked change of the regime setting (ADR-0038.R3, ADR-0038.R9).
Source: ADR-0016.R11

R23. If a regime setting is `unverified` and the installation's `environment` is `production` (ADR-0007.R15), an operation that reads it fails with `regime_setting_unverified`; there is no override (ADR-0003.R11). In `test` and `simulation` the read is allowed. The same applies to company template entries whose basis is `unverified`, at the points where the core reads them, such as a default determination row. The basis `test_fixture` counts as verified. The core defaults of `documents.issuance_without_delay` and `documents.e_invoice_required` are core behavior, carry no basis and are outside this gate; a package row that overrides one carries its own basis (ADR-0053.R8, ADR-0053.R8.N1, ADR-0053.R9).
Source: ADR-0016.R12

### Loading and versions

R24. Loading a package version validates it (R28, R29), then compares its rows with the installed ones by identity in one transaction. A row's basis may change. Its `value` may change only if no company on that regime has a posted document with a `date_basis` date on or after its `effective_from`; a row present in the installed version and missing from the new one counts as a value change. Otherwise the load fails with the loader error `regime_setting_in_use`, reported at deploy time and not a command error, catalogued in DS-14 (Loader errors). The change must then be a new row with a later `effective_from`, or a later row with a null value to end a rule.
Source: ADR-0016.R13, ADR-0016.R13.N1

R25. A package with companies that use it cannot be removed. What to do about documents already posted under a rule later found wrong is an open question for the author.
Source: ADR-0016.R13

R26. Package rows get deterministic IDs, `id = uuid5(f244ce09-3c6c-4c82-af14-918bdeca6be3, '<package>:<table>:<natural key>')`, computed by the loader, so a row has the same ID in every installation and version (ADR-0006.R4). This applies to `regime_setting` and `tax_code` in `docs/design/DS-05-platform.sql`; for `regime_setting` the name is `<package>:regime_setting:<regime>:<key>:<effective_from>`, with an empty regime written as an empty string.
Source: ADR-0016.R13.N2

R27. A package version is semver. A new dated row, a new template entry or a correction of an unused row is minor or patch. A change that requires companies to change their data is major and ships an upgrade note.
Source: ADR-0016.R14

R28. CI rejects a package unless all of these hold:
- the manifest and every data file match their schemas;
- `core_version` includes the current core and `license` is allowed;
- every key is registered by the core;
- every chart template satisfies ADR-0010.R17 and every default determination ADR-0015.R13;
- every key the core registers as required has a row for each regime; `documents.issuance_without_delay` and `documents.e_invoice_required` are optional, with a core default, and need no row (ADR-0053.R8, ADR-0053.R8.N1);
- every package template entry and package rule has a basis, and the basis `test_fixture` occurs only in a package with `is_test_package: true` (ADR-0053.R9);
- no tax kind and direction has more than one deductibility rule on the same date (ADR-0053.R3);
- the package's translation catalogs are complete for each declared language and its terminology keys exist in the core;
- the mandatory tests pass: core invariants and the package's golden scenarios on the synthetic dataset, and statutory reports matching their sample figures (DS-16, DS-26).
Source: ADR-0016.R15, ADR-0016.D0

R29. The report checks of CI: every definition parses and refers to existing accounts, lines and fields, and every fileable statement has a golden scenario with `report_line` rows. A package without statements, such as the basic US package, has no statement to match (ADR-0049.R32).
Source: ADR-0016.R15.N1

R30. The nightly run lists every `unverified` rule and template entry it exercised (`docs/runbook/escalation.md`, unverified legal rules).
Source: ADR-0016.R16

### Package code

R31. Package code implements only interfaces the core publishes for its component, such as `ExchangeRateFetcher`, `EInvoiceAdapter` and `BankStatementReader`. It imports only the core's public SDK (import-linter, DS-18), changes data only through commands and queries, which review checks because the code runs in the same process, and runs like any consumer or job (ADR-0013). It contains no accounting logic the core needs to post.
Source: ADR-0016.R17

R32. `AmountInWords` (`amount_in_words(amount, currency, language) -> str`) is a published interface; the core ships English. Where no installed implementation covers the print language, the print shows the amount in numerals only, formatted for that language (ADR-0049.R25).
Source: ADR-0016.R17.N1

R33. `TraceabilityCodeProvider` (`traceability_code(item, lot or serial, location, business date) -> {code, label_fields} | None`) is a published interface. The core ships none; label subjects add the optional field `traceability` when the company's package implements it. A country's traceability codes or digital product passports are package code behind it, never core (ADR-0061.R24).
Source: ADR-0016.R17.N2

R34. `DocumentReader` is a published interface for pure readers of the reader ladder, registered on the `document_reader` hook (ADR-0057.R5). `EInvoiceRecordReader` registers through it at rung 1, selects its parser by schema version and defines how a signing certificate's subject maps to the seller's tax ID. A package also supplies the intake data its regime needs: OCR languages, label anchors, number and date formats and the settings `data_processing.policy` and `intake.e_invoice_formats` (ADR-0057.R5, ADR-0057.R6, ADR-0057.R20, ADR-0057.R30). The OCR engine is an installation adapter (`OcrEngine`), not package code.
Source: ADR-0016.R17.N3

### Translations and terminology

R35. English is the source of every string (D8). The core ships catalogs for its own strings and for the names and meanings of system accounts and transaction keys, in English and Vietnamese (D8), in i18next JSON maintained through Weblate (ADR-0002). The core catalog keeps the UI strings and plain translations of system account and key names; the accounting names a regime gives to system accounts and keys belong to the terminology catalog of its package, for Vietnamese that of `l10n_vn` (ADR-0053.R16).
Source: ADR-0016.R18

R36. A package ships catalogs in the same format for its own strings (report lines, template texts, tax code names) and a terminology catalog that overrides core terms for its companies, for example the displayed name of `income_summary`. Chart templates carry each account's name in English and in the package's languages.
Source: ADR-0016.R18

R37. The core catalog holds the plain translations of core unit names (`uom.<code>.name`), the Vietnamese UI included. A package supplies only statutory unit names for its regime, as terminology keys `uom.<code>.name` read from `i18n/<language>/unit_names.csv`, each row with its basis (interim, flagged) (ADR-0056.R2, ADR-0056.R18).
Source: ADR-0016.R18.N1

R38. A string is looked up in this order: the package terminology of the company, the core catalog, then English, in the language of the output. The output language is the user's language for screens; for printed documents it is, in order, the render request's language, the document's `print_language`, the partner's language, then the company's (ADR-0049.R27); emails take the document's or partner's language (DS-27).
Source: ADR-0016.R19, ADR-0016.R19.N1

R39. The server translates what it renders (PDFs, emails, exports, report lines) from the same catalogs; the client translates screens (DS-30). The core catalog keys are generated from the registry (ADR-0040.R15).
Source: ADR-0016.R19

R40. Data that users enter, such as names and descriptions, is never translated. Identifiers, error codes and API error messages stay English (ADR-0004; ADR-0008.R24).
Source: ADR-0016.R19

R41. Statutory outputs (e-invoice lines, statutory prints) take a unit's package statutory name when present, else the core translation. The regime setting `documents.unit_name_max_length` limits their length (ADR-0056.R18).
Source: ADR-0016.R19.N2

### Discovery

R42. Agents discover packages and settings through the queries `ListLocalizationPackage` and `ListRegimeSetting` (company, date: every setting in force with its basis). The repository ships a Markdown skill for agents building packages (DS-38); the basic US package is built with it as its first test.
Source: ADR-0016.R20

### The `l10n_vn` package: layout and format

R43. The regime `tt99` of `l10n_vn` ships: an operational chart template holding every account of the regime's statutory chart, mapped to the system chart; detail accounts the package adds where one statutory account must map to several system leaves, and a technical account; a default account determination that resolves every combination its seed data can produce; and the regime and package settings that earlier ADRs require. The accounts, mappings and setting values are flagged content of the package files (R46) and are not stated in this spec.
Source: ADR-0039.D0

R44. The bases of the `l10n_vn` entries follow R8. A chart row that only restates the statutory chart carries that chart as its `legal_source`, not yet verified. A package choice is `unverified` with an open question: a detail account, a mapping not obvious from the account's nature, a node the package creates, a legal-form condition or a cost behavior; every determination row and every setting is a package choice too. The entries for the purchase invoice posting date and for the accounts used for rounding carry an `author_decision`. Under R23, production refuses the unverified content until the author verifies it.
Source: ADR-0039.D0

R45. The package format of DS-14 has the chart template columns `condition`, which selects rows by the company's legal form, and `cost_behavior`, which seeds the variable or fixed behavior of production cost accounts. It has the files of a determination format, a partner group seed and a statement of unreached system accounts, and legal forms in the manifest (`legal_forms`, R2).
Source: ADR-0039.D0

R46. Until step 1 the `l10n_vn` package lives in `docs/design/DS-19-vietnam-tt99/` in the DS-14 layout, as design files. At step 1 it moves unchanged to `l10n/l10n_vn/` (DS-18), and the design-lab check, which verifies the data against the core catalogs and the open questions and tests itself with deliberately broken copies (`check_package.py`, ADR-0039.R11), becomes the package CI check (R28). Package level: `manifest.yaml` and `settings.yaml`. Regime level, under `regimes/tt99/`: `chart_template.csv`, `account_determination.csv`, `unreached_system_accounts.csv`, `valuation_classes.csv`, `item_groups.csv`, `partner_groups.csv`, `close_checklist.yaml` and `settings.yaml`.
Source: ADR-0039.R1, ADR-0039.D0

R47. The account list of `regimes/tt99/chart_template.csv` was taken from independent reproductions of the statutory chart, compared code by code. The official publication has not been seen; this is an open question, and the list stays flagged package content.
Source: ADR-0039.R1

R48. `regimes/tt99/chart_template.csv` holds every code of the regime's statutory chart with English and Vietnamese names and the statutory tree. The codes, and the choice where the parts of the legal source name different codes for one account (an open question), are flagged package content and are not stated in this spec.
Source: ADR-0039.R2

R49. The regime `tt99` has no off-balance-sheet accounts. Items once kept there are tracked by the core: goods held for others as non-owned stock (ADR-0030), and written-off receivables as closed open items.
Source: ADR-0039.R2

## Invariants

None: see chunk 2, which carries the invariant that concerns this module.

## Edge cases

None: the catalog rows of this module hold no edge case.

## Settings

| Key | Type | Scope | Core default | Rule |
| --- | --- | --- | --- | --- |
| `data_processing.policy` | object (schema), `neutral` | regime (`regime_setting`) | none (`fail_closed`) | R20, R34, R205, R241 |
| `documents.unit_name_max_length` | integer, `1..255`, `lower_tighter` | regime (`regime_setting`) | unset (no limit) | R41 |
| `documents.issuance_without_delay` | boolean, `date_basis` `document_date` (ADR-0053.R8) | regime (`regime_setting`) | false | R20, R23, R28, R230 |
| `documents.e_invoice_required` | map from document type to boolean, `date_basis` `document_date` (ADR-0053.R8.N1) | regime (`regime_setting`) | false | R20, R23, R28, R230 |
| `intake.e_invoice_formats` | not stated | package setting | not stated | R34, R241 |

`documents.issuance_without_delay`, `documents.e_invoice_required` and `intake.e_invoice_formats` are named by the rules and absent from `settings.csv`; both `documents` keys are keys of `documents` (ADR-0053.R8), and the source units state nothing beyond the cells above. Chunk 2 holds the rows of `journal.manual_posting_to_control_accounts` and `stock_count.bin_difference_method` and names the other keys a package fills (R230). Regime settings are package rows (leaf `package`, change effect `package_release`); a company's option under R21 is a `setting_value` row.

## UI annotations

None: the sources hold no ADR-0077 annotation for the units of this chunk.

## Conflicts

CONFLICT ADR-0016.R5: e-invoice labels leave the package for the data of the e-invoice add-on and the tax component gains its kinds and deductibility files; ADR-0016.R5.N1 governs (R6, R7). The clause on company rows of the tax matrix is tax law that ADR-0041.R3.N2 restates, so R6 cites the tax rules and does not restate it.
CONFLICT ADR-0016.R6: the closing sentence adds the basis `test_fixture` and the loader's refusal of a test package in production; ADR-0053.R9 governs (R10).
CONFLICT ADR-0016.R10: the key registration is the settings registry of every scope, ADR-0016.R10.N2 governs (R18); a missing value gives `regime_configuration_missing` only for a key registered `fail_closed` and the core default otherwise, ADR-0053.R1.N2 governs (R19); a missing value of `documents.issuance_without_delay` or `documents.e_invoice_required` gives the core default and no error, where the rule names one such key, ADR-0053.R8 and ADR-0053.R8.N1 govern (R20).
CONFLICT ADR-0016.R11: a company's option is stored as an append-only `setting_value` row and changed by the asymmetric path, where the rule says a dated company row; ADR-0016.R11.N1 governs (R21).
CONFLICT ADR-0016.R12: the gate treats `test_fixture` as verified and leaves the core defaults of both optional `documents` keys outside; ADR-0053.R8, ADR-0053.R8.N1 and ADR-0053.R9 govern (R23).
CONFLICT ADR-0016.R13.N1: the loader error is catalogued in DS-14 where the ADR's document list names DS-04; this note governs (R24).
CONFLICT ADR-0016.R15: an optional key with a core default needs no row for each regime (the rule names one, ADR-0053.R8.N1 adds `documents.e_invoice_required`), and CI gains checks on test packages and deductibility rules; ADR-0053.R3, ADR-0053.R8, ADR-0053.R8.N1 and ADR-0053.R9 govern (R28).
CONFLICT ADR-0016.R18: Vietnamese accounting names of system accounts and keys leave the core catalog for the terminology catalog of `l10n_vn`; ADR-0053.R16 governs (R35).
CONFLICT ADR-0016.R19: the language order of printed documents is the longer order of ADR-0016.R19.N1 (ADR-0049.R27), not only the document's or partner's language (R38).

## Proposed (not law)

None.

## Trace

| Source | Where |
| --- | --- |
| ADR-0016.D0 | R1, R8, R28 |
| ADR-0016.R1 | R2 |
| ADR-0016.R2 | R3 |
| ADR-0016.R3 | R4 |
| ADR-0016.R4 | R5 |
| ADR-0016.R5 | R6 |
| ADR-0016.R5.N1 | R6, R7 |
| ADR-0016.R5.N2 | R6 |
| ADR-0016.R6 | R8-R11 |
| ADR-0016.R7 | R11-R14 |
| ADR-0016.R7.N1 | R15 |
| ADR-0016.R8 | R16 |
| ADR-0016.R9 | R17 |
| ADR-0016.R10 | R18-R20 |
| ADR-0016.R10.N1 | R20 |
| ADR-0016.R10.N2 | R18 |
| ADR-0016.R11 | R21, R22 |
| ADR-0016.R11.N1 | R21 |
| ADR-0016.R12 | R23 |
| ADR-0016.R13 | R24, R25 |
| ADR-0016.R13.N1 | R24 |
| ADR-0016.R13.N2 | R26 |
| ADR-0016.R14 | R27 |
| ADR-0016.R15 | R28 |
| ADR-0016.R15.N1 | R29 |
| ADR-0016.R16 | R30 |
| ADR-0016.R17 | R31 |
| ADR-0016.R17.N1 | R32 |
| ADR-0016.R17.N2 | R33 |
| ADR-0016.R17.N3 | R34 |
| ADR-0016.R18 | R35, R36 |
| ADR-0016.R18.N1 | R37 |
| ADR-0016.R19 | R38-R40 |
| ADR-0016.R19.N1 | R38 |
| ADR-0016.R19.N2 | R41 |
| ADR-0016.R20 | R42 |
| ADR-0027.R3 | ref: ADR-0027.R3 |
| ADR-0039.D0 | R43-R46 |
| ADR-0039.R1 | R46, R47 |
| ADR-0039.R2 | R48, R49 |
