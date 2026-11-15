# Multi-country and localization packages

The core contains no country's rules. Everything governed by one country's law lives in a localization package. The Vietnam package is built in full, as one package with two accounting regimes (TT99, then TT133); the US package at a basic level; other countries' packages are built by the community following instructions shipped for AI agents.

**Language.** English is the source language of code, data model, command names, UI strings and documentation. The Vietnamese translation ships from the start. Every string goes through i18n from the first commit, because adding it later means touching the whole UI. Each country's accounting terminology lives in that country's package.

**Chart of accounts.** Two tiers, many-to-one. The core has one fixed system chart; each company has its own operational chart, taken from a localization package template (Vietnam TT99, Vietnam TT133, US GAAP) or created by the company. Each operational account points to exactly one system account. The purpose is to make the system simpler: everything in the core only needs to know one fixed set of accounts, however each company numbers and details its own.

1. **System accounts** are fixed in the core, versioned, additions only, meaning never changes. Each has a type and a meaning description (Principle 7). They are detailed enough for every core need: inventory, GR/IR clearing, price difference, COGS, receivables, payables, input and output tax, FX gain and loss, revenue, expenses by group.
2. **Operational accounts** are where postings land. Every journal line posts to an operational account, never directly to a system account.
3. **Mapping is mandatory and type-consistent.** A postable operational account must point to a system account of the same type. The create-account command and the localization package CI check this.
4. **Mapping never changes after postings exist.** To change it, create a new account and transfer the balance with a traceable document, so that reports for earlier periods do not change by themselves.
5. **Account determination is cross-checked.** Account determination (transaction key × valuation class × valuation area → operational account) returns an operational account, and the core checks that it maps to the system account the transaction key requires or a descendant of it (e.g. an inventory receipt must land on an account under inventory). Misconfiguration is blocked before posting.
6. **Who uses which tier.** Core, policy engine, agents, management reports and consolidation reference system accounts. Statutory reports are defined by the localization package on operational accounts, because some lines need more detail than a system account (e.g. presenting receivables by each partner's detailed balance).
7. **Consolidation** of companies in the same instance sums by system account, with no pairwise mapping tables between companies.

| Package component | Vietnam package example |
| --- | --- |
| Accounting regimes, each with an operational chart template mapped to system accounts | TT99, TT133 |
| Default account determination | Transaction key × valuation class × valuation area → operational account, per regime |
| Tax codes, date-effective rates, tax returns | VAT 0/5/8/10%, 01/GTGT XML |
| FX and revaluation rules | Accounts 413, 515, 635 |
| Statutory reports and books | B01, B02, B03, general journal |
| E-invoicing | BKAV adapter |
| Document print templates | Cash receipt, cash payment, goods receipt, goods issue, invoice |
| Bank statement formats, fiscal calendar, rounding | Statement files of 2–3 common banks |
| Translation and terminology | Vietnamese accounting terminology |
| Personal data rules | Law 91/2025, default data labels |
| Golden scenarios and synthetic dataset | Synthetic dataset for the Vietnamese company, hand-built spreadsheets |

**Instructions for AI agents building localization packages.** The repo ships a Markdown skill containing:

- The package structure and the schema of each component in the table above.
- A checklist of what must exist before a package is accepted.
- A requirement that every rule cites the original legal text and its effective date; unverified rules must be flagged.
- Mandatory tests: core invariants, the country's golden scenarios, statutory reports matching sample figures.
- Conventions for naming, terminology translation and annotating uncertain parts.

CI rejects a package that lacks legal sources or tests. Structure, loading and CI checks: [ADR-0016](../adr/0016-localization-package-structure.md). The basic US package is built with this skill as its first test. The basic US package contains the chart, default account determination and basic tax codes; no state tax returns.
