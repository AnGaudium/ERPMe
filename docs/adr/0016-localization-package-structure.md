# ADR-0016: Localization package structure

Status: accepted (2026-11-14) under ADR-0005, reviewed by Claude Fable 5.2. Design item: DS-14. Related decisions: D3, D7, D8, D9. Principles 6, 7, 12. Chart-of-accounts rules 1–7. ADR-0003, ADR-0004, ADR-0005, ADR-0006, ADR-0007, ADR-0009, ADR-0010, ADR-0011, ADR-0012, ADR-0013, ADR-0015.

## Decision

A localization package (`l10n_<country>`) is a directory with a manifest, data files for its components and, only where a component needs behavior, Python code behind interfaces the core defines. It holds everything one country's law governs; the core holds none of it ([06](../spec/06-localization.md)). Package content is of two kinds: package templates, copied into a company when it is set up and then owned by the company (chart of accounts, default account determination, valuation classes, item groups, close checklist, numbering formats); and package rules, read live from the installed package version and dated (regime settings such as FX rules, reversal method and closing rules; tax rates; statutory reports). Every template entry and every rule records its basis — a legal source, an author's decision, or the flag `unverified` with its open question — and keeps it when copied, so unverified content is visible wherever it is used and can be refused in production (ADR-0003 R11). Rules that a posting has used never change value. CI rejects a package that lacks bases or tests. Translations and accounting terminology for the package's languages ship in the package, over the core's English source.

### Rules

**Package and manifest**

1. A package is a directory `l10n/<code>/` in the repository (location fixed by DS-18) with `code` `l10n_<country>` (ADR-0004 rule 8). Its `manifest.yaml` declares `code`, `name`, `country` (ISO 3166-1 alpha-2), `version` (semver), `core_version` (the range of core versions it works with), `license` (AGPL-3.0 for packages in this repository, as the core, [18](../spec/18-license-governance.md)), `languages` (BCP 47), `regimes` (each with a `code` such as `tt99` and a `name`) and its component files. Format and example: [DS-14-localization-package.md](../design/DS-14-localization-package.md). The manifest also declares `legal_forms`, which select chart template rows ([ADR-0039](0039-vietnam-package-tt99.md) rule 5).
2. A company uses exactly one package and one of its regimes, chosen when the company is created (`CreateCompany`); `company.localization_package` and `company.accounting_regime` record them. Changing regime later is out of scope for Phase 1.
3. One installation has one version of each package. The package's code ships with the application build; its data is loaded when the application is deployed, with the database migrations (DS-37). At startup the application refuses to run if a package's loaded data version differs from its code version; downgrades are refused.
4. In Phase 1, packages live only in this repository and go through the same review as the core ([ADR-0003](0003-build-operating-rules.md) R5); packages from elsewhere come after Phase 1.

**Components**

5. Components and their kind:

| Component | Kind | Format owner |
| --- | --- | --- |
| Operational chart template per regime, mapped to system accounts | package template | ADR-0010, DS-19 |
| Default account determination per regime; valuation classes; item groups; partner groups; statement of unreached system accounts ([ADR-0039](0039-vietnam-package-tt99.md) rules 4, 7) | package template | ADR-0015, DS-19 |
| Close checklist template, period pattern, special period count | package template | ADR-0012 |
| Numbering formats per document type | package template | ADR-0009 |
| Print templates | package template | DS-27 |
| Regime settings (FX rules, reversal method, closing rules, default posting dates, rounding of named calculations) | package rule | this ADR, rules 9–12 |
| Tax codes, date-effective rates, tax return formats | package rule | DS-23 |
| Statutory reports and books | package rule | DS-26 |
| Default data labels and personal data rules | package rule | DS-32, [17](../spec/17-seatmap-data-classification.md) |
| Translations and accounting terminology | translation | rules 18–19 |
| E-invoice adapter, bank statement readers, exchange rate fetchers | package code | DS-24, DS-25, ADR-0011 |
| Golden scenarios, synthetic dataset parameters | package test | DS-16, DS-17 |

6. Every entry of a package template or package rule carries a basis: `legal_source` (document, article, effective date), or `author_decision` (the open question or ADR it closed, the date and the author's name), or `status: unverified` with its `open_question`; a company's own change to a copied template entry has the basis `company_decision` (actor and date, rule 7). A legal source becomes verified with `verified_by` and `verified_on`. These fields are set only by the author, or in a change the author merges citing his decision; an agent may find and quote a source but never sets them on its own ([ADR-0003](0003-build-operating-rules.md) R10; [escalation.md](../runbook/escalation.md#unverified-legal-rules)).
7. A package template is copied into company-owned rows when the company is set up, with the package version and each entry's basis; the company may then change its copy (TT99 lets a company design its own accounts and books, [07](../spec/07-shared-foundation.md#accounting-regimes-as-configuration)). Changing a copied entry sets its basis to `company_decision` with the actor and date, keeping the package's original basis for reference. Whether an entry a company changed from an `unverified` package entry counts as a localization rule the pilot uses under R11 is an open question for the author; interim, flagged: it does not, because the company has decided it under its own accounting policy. The close checklist is copied into a company checklist template at setup, from which each period's tasks are copied (ADR-0012 rule 11). A later package version never changes a company's copy; how template changes are offered to companies (listing differences and applying them by command) is designed with the upgrade policy (DS-37).
8. Rounding modes of currencies live in `currency.rounding_mode` (ADR-0006 rule 17); a package proposes values, and the installation keeps one value per currency, set by the operator when packages differ. Only modes for named calculations (e.g. VAT per line) are regime settings.

**Regime settings**

9. A regime setting is a row of `regime_setting`: `localization_package`, `accounting_regime` (null for every regime of the package), `key`, `value` (JSON validated by the schema the core registers for that key, or null to end an earlier row), `effective_from` (a business date) and its basis (rule 6). Its identity is (package, regime, key, `effective_from`). For a company, a row for its regime wins over a row for every regime with the same key and date.
10. The core registers every key it reads, with its value schema, its `date_basis` (which date selects the row: `posting_date` by default, ADR-0007 rule 8) and, where the law lets a company choose, the options the regime may permit. The core reads a setting only through `regime_setting(company, key, date)`, which returns the row in force on that date. If there is none, or its value is null, the operation fails with `regime_configuration_missing`, naming the key, regime, date and how to fix it (ADR-0011 rule 13).
11. Where the regime permits options (e.g. whether an approximate rate may be used, [07](../spec/07-shared-foundation.md#multi-currency)), the regime setting lists them with a default, and a company picks one with `UpdateCompanyRegimeOption`, audited (DS-36). The choice is stored as a dated company row (`effective_from`) and read through the same accessor by the key's date basis, so a backdated posting uses the choice in force on its date. A company cannot change a setting the regime does not open to it. Enabling an unverified rule is audited as a tracked change of the regime setting ([ADR-0038](0038-audit-and-observability.md) rules 3, 9).
12. If a regime setting is `unverified` and the installation's `environment` is `production` (ADR-0007 rule 15), an operation that reads it fails with `regime_setting_unverified`; there is no override ([ADR-0003](0003-build-operating-rules.md) R11). In `test` and `simulation` they are allowed. The same applies to company template entries whose basis is `unverified`, at the points where the core reads them (e.g. a default determination row). This is how R11 is enforced: a pilot cannot go live on a flagged rule it uses.

**Loading, versions and CI**

13. Loading a package version validates it (rule 15), then compares its rows with the installed ones by identity in one transaction. A row's basis may change; its `value` may change only if no company on that regime has a posted document with a `date_basis` date on or after its `effective_from`. A row present in the installed version and missing from the new one counts as a value change. Otherwise the load fails with the loader error `regime_setting_in_use` (reported at deploy time, not a command error), and the change must be a new row with a later `effective_from`, or a later row with a null value to end a rule. What to do about documents already posted under a rule later found wrong is an open question for the author. A package with companies that use it cannot be removed.
14. A package version is semver: a new dated row, a new template entry or a correction of an unused row is minor or patch; a change that requires companies to change their data is major and ships an upgrade note.
15. CI rejects a package unless: the manifest and every data file match their schemas; `core_version` includes the current core and `license` is allowed; every key is registered by the core; every chart template satisfies ADR-0010 rule 17 and every default determination ADR-0015 rule 13; every key the core registers as required has a row for each regime; every package template entry and package rule has a basis; the package's translation catalogs are complete for each declared language and its terminology keys exist in the core; and the mandatory tests pass: core invariants and the package's golden scenarios on the synthetic dataset, and statutory reports matching their sample figures (DS-16, DS-26; [06](../spec/06-localization.md)).
16. The nightly run lists every `unverified` rule and template entry it exercised ([escalation.md](../runbook/escalation.md#unverified-legal-rules)).

**Package code**

17. Package code implements only interfaces the core publishes for its component (e.g. `ExchangeRateFetcher`, `EInvoiceAdapter`, `BankStatementReader`), imports only the core's public SDK (import-linter, DS-18), changes data only through commands and queries, which review checks because it runs in the same process, and runs like any consumer or job (ADR-0013). It contains no accounting logic the core needs to post.

**Translations and terminology**

18. English is the source of every string (D8). The core ships catalogs for its own strings and for the names and meanings of system accounts and transaction keys, in English and Vietnamese (D8), in i18next JSON maintained through Weblate (ADR-0002). A package ships catalogs in the same format for its own strings (report lines, template texts, tax code names) and a terminology catalog that overrides core terms for its companies (e.g. `income_summary` shown as "Xác định kết quả kinh doanh"). Chart templates carry each account's name in English and in the package's languages.
19. A string is looked up in this order: the package terminology of the company, the core catalog, then English, in the language of the output: the user's language for screens, the document's or partner's language for printed documents and emails (DS-27). The server translates what it renders (PDFs, emails, exports, report lines) from the same catalogs; the client translates screens (DS-30). Data that users enter (names, descriptions) is never translated. Identifiers, error codes and API error messages stay English (ADR-0004; ADR-0008 rule 24).

**Agents**

20. Agents discover packages and settings through queries: `ListLocalizationPackage` and `ListRegimeSetting` (company, date: every setting in force with its basis). The repository ships a Markdown skill for agents building packages (DS-38), following this ADR; the basic US package is built with it as its first test ([06](../spec/06-localization.md)).

## Context

DS-14 is needed by step 1 (Vietnam package with TT99, DS-19) and by DS-23, DS-24, DS-26, DS-27 and DS-38. Constraints:

- The core holds no country's rules; package components as listed in spec 06; English source with Vietnamese shipped; each country's terminology in its package; CI rejects a package that lacks legal sources or tests; a skill for agents building packages ([06](../spec/06-localization.md), D7, D8, D9).
- Unverified rules live in the package as flagged configuration with their open question; no go-live on a flagged rule the pilot uses (reading guide rule 4; [escalation.md](../runbook/escalation.md); ADR-0003 R10, R11).
- Templates and settings named by earlier ADRs: ADR-0006 (rounding per currency), ADR-0009 (numbering, reversal method), ADR-0010 (chart templates), ADR-0011 (FX settings), ADR-0012 (checklist, closing rules), ADR-0015 (determination templates). Licenses: [18](../spec/18-license-governance.md).
- ADR-0005: the mechanism is the agent's; the rules in a package are the author's.

## Options considered

| Option | For | Against |
| --- | --- | --- |
| Templates copied at setup, rules read live with effective dates (chosen) | Companies own their chart and accounts; law changes reach every company by package upgrade | Two kinds of component to explain |
| Everything copied into the company | One mechanism | A tax rate change would need a command per company |
| Everything read live from the package | Always current | A company could not change its own chart, which TT99 allows |
| Basis only on rules | Simpler templates | Flagged accounting content in templates (determination, checklist) would be invisible |
| Allow changing the value of a used rule | Easy fixes | Earlier results would change by themselves |
| Package code free to import core internals | Easier to write | Breaks module boundaries and upgrades |

## Constraints that come with the decision

- DS-04: `CreateCompany`, `UpdateCompanyRegimeOption`, queries `ListLocalizationPackage`, `ListRegimeSetting`; error `regime_setting_unverified`; loader error `regime_setting_in_use`.
- DS-15: operator permission to load packages; permission to choose regime options.
- DS-16, DS-17: package golden scenarios and dataset parameters.
- DS-18: package location, import-linter contracts, CI jobs of rule 15, public SDK, startup version check.
- DS-19, DS-39: the Vietnam package. DS-38: the skill and the US package.
- DS-23, DS-24, DS-25, DS-26 (reports on company-changed charts), DS-27: formats of their components.
- DS-30: client-side lookup. DS-36: audit of choices and enabled unverified rules. DS-37: data loads at deploy; template change notes.

## Revisit when

- A company needs two packages (e.g. a branch in another country), or a regime change while live.
- Packages from outside this repository are accepted.

## Documents updated

- [docs/design/DS-14-localization-package.md](../design/DS-14-localization-package.md): new, format and example.
- [docs/spec/06-localization.md](../spec/06-localization.md): link to this ADR.
- [docs/spec/00-reading-guide.md](../spec/00-reading-guide.md): glossary rows for package template, package rule, regime setting, basis.
- [docs/design/DS-04-command-envelope.md](../design/DS-04-command-envelope.md): two error codes; `regime_configuration_missing` details.
- [docs/design/backlog.md](../design/backlog.md): DS-14 row links here.
- [docs/adr/README.md](README.md): index row.
- [docs/open-questions.md](../open-questions.md): documents posted under a rule later found wrong; company changes of unverified template entries under R11.
- [docs/runbook/step-log.md](../runbook/step-log.md): entry.
