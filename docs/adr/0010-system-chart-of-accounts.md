# ADR-0010: System chart of accounts

Status: accepted (2026-11-14) under ADR-0005, reviewed by Claude Fable 5.2. Design item: DS-07. Related decisions: D5, D7, D8, D9. Principles 6, 7. Chart-of-accounts rules 1–7. ADR-0004, ADR-0005, ADR-0006, ADR-0009.

## Decision

The core has one fixed, versioned system chart of accounts, kept as a catalog file ([system-accounts.csv](../catalogs/system-accounts.csv), version 0.1.0: 117 accounts, 99 postable, with `currency_exchange_clearing` added by [ADR-0048](0048-cash-bank-receivables-payables.md) rule 12). It is a tree with five roots (asset, liability, equity, income, expense); each account has a type, a normal balance, a control kind (inventory, receivable, payable, GR/IR or none) and flags for contra and bilateral accounts. Every postable operational account of a company maps to exactly one leaf, from which it takes these properties; the mapping never changes once postings exist. The core, the policy engine, agents, management reports and consolidation work only with system accounts; statutory reports and books use operational accounts. The tree groups accounts for core checks only and carries no presentation rule. The catalog stays at 0.x and may still change until the step 0 gate; from 1.0.0 it changes by additions only.

### Rules

**The catalog**

1. The system chart is `docs/catalogs/system-accounts.csv`, owned by DS-07, with columns `code`, `parent_code`, `account_type`, `normal_balance`, `is_contra`, `is_bilateral`, `control_kind`, `is_postable`, `added_in`, `name`, `meaning`. The core loads it into the global table `system_account` (no `company_id`); each row's `id` is `uuid5(…, "system_account:<code>")` (ADR-0006 rule 4). `name` and `meaning` are English source text, translated through i18n (Principle 7). The catalog is the word list for system account codes in the glossary.

    Note (S2 findings closure, 2026-11-21): the table `system_account` has one column per catalog column, except that `parent_code` becomes `parent_id`, a key to the parent's uuid5 `id` that the loader resolves (ADR-0004 rule 12; D7). Its DDL is in [DS-06-universal-journal.sql](../design/DS-06-universal-journal.sql), with `transaction_key`, `account` and `applied_rate`.
2. `code` is a `snake_case` English identifier (ADR-0004), e.g. `inventory_merchandise`; it never contains a country's account number. Leaves in the receivable, payable, tax and fixed asset families start with their family's name (`receivable_trade`, `tax_payable_output`). Core code refers to system accounts only through a type generated from the catalog (e.g. `SystemAccount.INVENTORY_MERCHANDISE`), never by string literals or operational account codes.
3. `account_type` is one of `asset`, `liability`, `equity`, `income`, `expense`; a child has its parent's type. Asset, liability and equity are balance-sheet types; income and expense are profit-and-loss types.
4. `normal_balance` is `debit` for assets and expenses and `credit` for liabilities, equity and income, except contra accounts (`is_contra: true`), which have the opposite normal balance (e.g. `fixed_asset_accumulated_depreciation`, `revenue_deduction_return`). A balance on the other side is allowed; it is a fact for reports and checks, not an error.
5. `control_kind` says which core module owns postings to the account and what an invariant can check: `inventory` (valued stock, posted only through the inventory module: material document lines and value-only lines carrying item and warehouse through the stock lock helper, ADR-0020 rule 9; its balances equal the inventory valuation report, [12-testing.md](../spec/12-testing.md)), `receivable` and `payable` (partner open-item accounts: every line carries a partner and an open item, and balances equal the sum of open items), `gr_ir` (GR/IR clearing, DS-11 and DS-22), or `none`. The invariants (DS-16) use `control_kind`; account determination (DS-08) uses it together with the tree (rule 13). Which partner accounts carry `receivable` or `payable` may still change in 0.x as DS-25 decides (e.g. payroll and other payables are `none` in 0.1.0). Three gated kinds, `cost_object`, `fixed_asset` and `loan`, are enforced per company only from an irreversible activation; before it the effective kind is `none` ([ADR-0025](0025-later-phase-seams.md) rules 3–5). Open items on these accounts follow [ADR-0026](0026-open-item-core.md) rule 3. Operational accounts used for production overhead carry `cost_behavior` (`variable`, `fixed`), seeded by the regime template ([ADR-0035](0035-production-costing.md) rule 7); in fact every production cost account carries it, because pool groups split by it ([ADR-0039](0039-vietnam-package-tt99.md) rule 6).
6. `is_bilateral: true` marks a receivable or payable account whose open items may sit on either side and whose balance is presented split by side, e.g. `receivable_trade` holding customer advances and `payable_trade` holding advances to suppliers ([05](../spec/05-accounting-inventory-core.md), backlog DS-07). Only accounts with `control_kind` `receivable` or `payable` can be bilateral.
7. Only leaves are postable; inner nodes group leaves. A leaf never becomes an inner node. A new leaf may take only meaning that its parent's `_other` leaf covered or that no leaf covered, so existing leaves never change meaning; nodes expected to be refined have an `_other` leaf.
8. The hierarchy and the types carry no presentation rule: where an account appears in a statutory report is set by the localization package on operational accounts (DS-26). Leaves whose presentation differs between regimes sit directly under their root (e.g. `payment_discount_given`, `rounding_loss`, `inventory_write_down_expense`).
9. Versions: 0.x until the step 0 gate, during which DS-08 to DS-11 and DS-25 may still change rows. Version 1.0.0 is released at the step 0 gate and tagged `system-accounts-1.0.0`. From then on the catalog changes by additions only (rule 1 of [06](../spec/06-localization.md)): a released row's `code`, `parent_code`, `account_type`, `normal_balance`, `is_contra`, `is_bilateral`, `control_kind`, `is_postable`, `added_in` and `meaning` never change, and no row is removed; a changed meaning is a new account. Adding rows or a column (with a value for every existing row) raises the minor version; rewording `name` or `meaning` without changing what it means is a patch version. DS-41 also changes rows in 0.x ([ADR-0025](0025-later-phase-seams.md) rule 5).

**Operational accounts and mapping**

10. An operational account is a row of `account`: `id`, `company_id`, `code` (the company's number, e.g. `1561`), `name`, `parent_id` (the operational tree used by statutory reports), `is_postable`, `system_account_id`, `currency` (nullable: restricts the account to one transaction currency, e.g. a USD bank account), `has_posting` and `is_active`. Only postable operational accounts receive journal lines (rule 2 of 06). Whether manual journal entries may post to an account with `control_kind` other than `none` is decided by DS-06 and DS-25.
11. Every postable operational account maps to exactly one postable system account; non-postable operational accounts have no mapping (rule 3 of 06). The mapping gives the operational account its type, normal balance, control kind and flags, so they cannot disagree. `CreateAccount` and the localization package's CI reject an unmapped postable account or a mapping to an inner node. A company whose old chart has one account where the system chart has several leaves (e.g. one financial income account) splits it into sub-accounts, one per leaf, as SAP requires one G/L account per determination target; the data migration mapping (DS-21) does the split.
12. The first journal line on an operational account sets `has_posting = true` in the same transaction, which locks the account row. From then on a trigger rejects changes to `code`, `system_account_id`, `is_postable` and `currency` (rule 4 of 06). To move to another system account, the company creates a new operational account and moves the balance: by a balance transfer document (DS-06) for accounts with `control_kind` `none`, per open item for receivable and payable accounts (DS-25), and by a valuation change for inventory accounts (DS-09). When the catalog adds a system account, existing mappings are untouched. Balances on an account whose gated control kind is active are moved by its Phase 2 or 3 module ([ADR-0025](0025-later-phase-seams.md)). Moving open items: [ADR-0026](0026-open-item-core.md) rule 12.
13. A transaction key declares a required system account (a leaf or a node) and, optionally, a required control kind. Account determination returns an operational account; the core checks that its system account is the required one or a descendant of it and, if a control kind is declared, has that control kind, and blocks the posting otherwise (rule 5 of 06; DS-08).

**Who uses which tier**

14. The core, the policy engine, agents, management reports and consolidation refer only to system accounts. Statutory reports and books are defined by the localization package on operational accounts (rule 6 of 06; DS-26). Consolidation of companies in one instance sums balances by system account (rule 7 of 06); intercompany eliminations use the partner on intercompany open items.

    Note: agents may read statutory reports, books and their drill-downs, which are operational-account views, to answer questions and explain figures. They never use an operational code to choose an account, a policy input or a posting ([ADR-0049](0049-statutory-reporting-and-printing.md) rule 18).
15. A balance on a bilateral account is presented as a receivable or an advance (or a payable or an advance) per open item: each open item carries a kind (e.g. invoice, advance, credit) defined in [ADR-0026](0026-open-item-core.md) rule 2, and statutory reports split the balance by that kind and by partner (DS-26).

    Note: the split is set by the options of an account term: `by` (`account`, `partner` or `partner_kind`), required on the split measures with no core default, `kind`, and `term` with `undated` ([ADR-0049](0049-statutory-reporting-and-printing.md) rule 7).

**Validation**

16. CI checks the catalog on every change: unique codes; every `parent_code` exists; no cycles; five roots; a child has its parent's type and contra flag where the parent is contra; normal balance follows rule 4; only receivable and payable accounts are bilateral; `control_kind` other than `none` only on leaves; exactly the leaves are postable; family prefixes (rule 2). From 1.0.0 it also compares with the latest released tag: no released row removed or changed except wording (rule 9).
17. CI checks every chart template in a localization package (DS-14, DS-19): every postable operational account maps to a postable system account; every system account the core uses for determination or closing is reachable from at least one operational account of the template, or the package states why not. The TT99 template states its unreached accounts in `unreached_system_accounts.csv` and passes the design-lab check ([ADR-0039](0039-vietnam-package-tt99.md) rules 4, 11).

**Catalog content and comparison with SAP**

18. Version 0.1.0 covers what the core needs in Phases 0 and 1 (inventory, GR/IR clearing, purchase cost clearing, price difference, cost of goods sold, receivables, payables, input and output tax, FX gains and losses, rounding gains and losses, revenue and its deductions, expenses by group; [06](../spec/06-localization.md) rule 1), technical accounts for closing and migration (`income_summary`, `opening_balance_clearing`), and enough other accounts that every balance of a migrating company has a place, with an `_other` leaf under every root. How each regime maps to it (e.g. TT99 156 → `inventory_merchandise`; 515 split into sub-accounts for `interest_income`, `fx_gain_realized`, `rounding_gain` and others) is DS-19; how amounts are posted to it is DS-06, DS-08 and the localization package. The classification choices that are presentation or accounting rules are listed in the open questions.
19. In SAP S/4HANA an operational chart holds the G/L accounts, an optional group chart rolls them up for consolidation, and an optional country chart (alternative account numbers) serves local statutory reporting ([SAP Learning](https://learning.sap.com/learning-journeys/implementing-record-to-report-in-sap-s-4hana/identifying-the-chart-of-accounts-types)). In NativeFlows the system chart plays the group chart's role but is mandatory; the localization package supplies the operational chart template; a separate country chart is deferred (open question on foreign-invested companies). Unlike SAP, where account type, reconciliation type and automatic-posting flags are set on each operational G/L account, NativeFlows sets type and control kind once on the system account and the operational account inherits them, so a company cannot misconfigure them.

## Context

DS-07 is needed by DS-06 (journal), DS-08 (account determination), DS-14 and DS-19 (localization packages). Constraints:

- Two-tier chart, many-to-one (D7); system accounts fixed in the core, versioned, additions only, meaning never changes, detailed enough for every core need; chart-of-accounts rules 1–7 ([06-localization.md](../spec/06-localization.md)).
- Core modeled on SAP (D5).
- Mixed-balance accounts such as 131 and 331 hold advances; classification of advances at open-item level (backlog DS-07). Inventory-type and receivable/payable control accounts must equal their subledgers ([12-testing.md](../spec/12-testing.md)).
- The core holds no country rules; the Vietnamese chart (TT99) is a template in the Vietnam package (06, D9).
- ADR-0005: among correct options, the one easiest for AI agents wins; accounting and presentation rules go to the author.

## Options considered

| Option | For | Against |
| --- | --- | --- |
| Catalog as a CSV file in the repository (chosen) | Reviewable in a diff; readable by people and agents; one source loaded into the database | Needs a loader and CI checks |
| Control kind as a column (chosen) | Invariants and determination name what they check; independent of the tree | One more column |
| Control expressed only by the tree (subtree `inventory`) | No extra column | Allowances, goods in transit and work in process sit in the same subtree with different rules |
| Postable inner nodes | Fewer accounts | A node that gains a child breaks existing mappings and determination checks |
| Separate system accounts for customer and supplier advances | Simple presentation | The spec keeps advances on 131/331 and classifies them per open item |
| System account codes as numbers | Familiar to accountants | Numbers carry one country's meaning; agents misread them as operational codes |
| Release 1.0.0 now | Stable codes sooner | DS-08 to DS-11 and DS-25 have not tested the chart yet |

## Constraints that come with the decision

- DS-06: journal lines post to operational accounts only; balance transfer document; `has_posting` set by the first line; manual postings to control accounts.
- DS-08: determination cross-check by descendant or control kind (rule 13).
- DS-09: valuation change to move inventory between accounts; `inventory_difference` use.
- DS-11: `purchase_cost_clearing` and `gr_ir_clearing` use.
- DS-12: closing uses `income_summary` and `retained_earnings` as the regime's closing rules say.
- DS-14, DS-19: chart templates and their CI checks (rule 17); the TT99 mapping, including `rounding_gain` → 515 and `rounding_loss` → 635 (author's decision).
- DS-16: invariants by `control_kind` (rule 5).
- DS-18: catalog loader, generated `SystemAccount` type, CI checks of rule 16, release tag.
- DS-21: `opening_balance_clearing`; splitting old accounts at migration (rule 11).
- DS-25: open item kinds (rule 15); moving open items between accounts. DS-26: statutory reports on operational accounts.

## Revisit when

- A localization package cannot map a balance without using an `_other` leaf for more than 5% of a company's balance-sheet total: add finer system accounts.
- Consolidation needs a level between system and operational accounts, or a foreign-invested company needs a country chart beside its group chart.

## Documents updated

- [docs/catalogs/system-accounts.csv](../catalogs/system-accounts.csv): new, version 0.1.0.
- [docs/catalogs/README.md](../catalogs/README.md): system accounts status and version.
- [docs/spec/00-reading-guide.md](../spec/00-reading-guide.md): glossary rows for account type, normal balance, control kind, contra and bilateral accounts.
- [docs/design/backlog.md](../design/backlog.md): DS-07 row links here.
- [docs/adr/README.md](README.md): index row.
- [docs/open-questions.md](../open-questions.md): chart templates question reworded; classification choices for the author.
- [docs/runbook/step-log.md](../runbook/step-log.md): entry.
