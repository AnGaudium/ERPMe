# ADR-0015: Account determination

Status: accepted (2026-11-14) under ADR-0005, reviewed by Claude Fable 5.2. [ADR-0018](0018-product-and-item-model.md): valuation class and item group are product fields, read through the item. [ADR-0019](0019-partners-and-crm-foundation.md) rule 3: partner accounts live in role profiles; the document's role selects the profile. Design item: DS-08. Related decisions: D5, D6, D7. Principles 6, 7, 13. Chart-of-accounts rule 5. ADR-0004, ADR-0005, ADR-0006, ADR-0010, ADR-0011, ADR-0012, ADR-0014.

## Decision

Every automatic posting whose account the system must choose finds it deterministically from a transaction key and the posting's determinants. The core ships a catalog of transaction keys ([transaction-keys.csv](../catalogs/transaction-keys.csv), version 0.1.0, 44 keys with the production keys of [ADR-0035](0035-production-costing.md)), each declaring which determinants it uses (valuation class and warehouse, item group, partner group, tax code, currency, or none) and which system accounts and control kind its account must have. Each company has one `account_determination` table: a row maps a key and a combination of determinant values to an operational account, and the row that matches on the most significant determinants wins; partner keys read the partner's own reconciliation account. The result is cross-checked against the key before posting (chart-of-accounts rule 5). Valuation classes and item groups are company data seeded from the localization package. This follows SAP's automatic account determination: inventory transaction keys with valuation classes, revenue determination, reconciliation accounts on business partners, tax accounts per tax key and exchange-difference accounts.

### Rules

**Transaction keys**

1. The catalog is `docs/catalogs/transaction-keys.csv`, owned by DS-08, with columns `code`, `name`, `determinants`, `required_system_accounts`, `required_control_kind`, `has_regime_alternatives` ([ADR-0027](0027-cross-cutting-ownership.md) rule 11), `added_in`, `meaning`. It is loaded into the global table `transaction_key` (no `company_id`; `id` by uuid5 from `"transaction_key:<code>"`, ADR-0006 rule 4); core code refers to keys only through a generated type (`TransactionKey.INVENTORY_POSTING`). It follows the system chart's versioning: 0.x until the step 0 gate, then additions only (ADR-0010 rule 9). DS-09 adds the keys for other receipts and issues and scrapping (transfers need no key: they post between inventory keys, ADR-0020 rule 6); DS-23 and DS-25 add theirs (DS-11 adds none: landed cost posts to inventory keys and credits the source account, [ADR-0021](0021-landed-cost.md) rule 1; tax details, payments, bank charges, currency exchange clearing).
2. A key may share its code with a system account (e.g. `price_difference`, `rounding_gain`) only when every account it requires is that account or a descendant of it; other keys describe the posting (`inventory_posting`, `input_tax`, `income_summary_transfer`). CI checks this rule, and checks the catalog like the system chart: unique codes, every required system account exists, determinants from rule 3, `name` and `meaning` present. Exception: keys marked `has_regime_alternatives` in the catalog may also list alternatives that are a regime choice under rule 4 ([ADR-0027](0027-cross-cutting-ownership.md) rule 11).
3. `determinants` is an ordered list, from most to least significant, drawn from: `valuation_class`, `warehouse`, `item_group`, `partner_group`, `tax_code`, `currency`. An empty list means one account per company.
4. `required_system_accounts` lists one or more system accounts (leaves or nodes); the determined account's system account must be one of them or a descendant. `required_control_kind`, when set, must also match (ADR-0010 rule 13). An account under the `inventory` node must have control kind `inventory` unless the key names that leaf itself, so an allowance or work in process never receives stock value by accident. Where a key allows several accounts (e.g. `price_difference`: price differences or stock; `inventory_count_surplus`: pending, inventory differences or income), the choice is the regime's accounting rule, made by its default determination (open questions). When `price_difference` determines an inventory account, the invoice posts the difference to `purchase_cost_clearing` and a `landed_cost` moves it to stock ([ADR-0021](0021-landed-cost.md) rule 12).
5. Lines whose account the system determines carry their `transaction_key_id` (ADR-0014 rule 5). Lines whose account comes from the document or from master data — a payment's bank or cash account, the revalued account in a revaluation (ADR-0011 rule 19), the accounts being closed (ADR-0012 rule 18), the lines of a `balance_transfer` or a `general_journal`, an expense account the user chose on a supplier invoice — have none.

**Valuation classes, item groups and valuation areas**

6. A `valuation_class` is company data (`company_id`, `code`, `name`, `is_active`) that groups stock items for inventory accounts (e.g. merchandise, raw materials, finished goods), seeded from the regime template (DS-19). Each stock item has one valuation class (DS-20); an item without stock has none.
7. An `item_group` is company data that groups items for revenue, cost of goods sold and consumption accounts (spec [05](../spec/05-accounting-inventory-core.md): "item group"), seeded the same way. Each item has one item group (DS-20).
8. The valuation area is the company or a physical warehouse with its attached transit and goods-sent warehouses (ADR-0020 rule 2), per the company's costing policy `valuation_area_level` (`warehouse` or `company`), set at company setup and not changeable by command once stock has been posted; a change of costing scope is applied retrospectively under VAS 29 ([08](../spec/08-l10n-vn.md#costing)) and would be a migration; ADR-0020 rule 16 does not support it in Phase 1 (open question). The `warehouse` determinant is independent of that level: a row may name a warehouse to give it its own accounts even when costing is company-wide.

**The determination table**

9. `account_determination` rows: `id`, `company_id`, `transaction_key_id`, the determinant columns `valuation_class_id`, `warehouse_id`, `item_group_id`, `partner_group_id`, `tax_code_id`, `currency` (each nullable; null means "any"), and `account_id` (a postable operational account of the company). A row may set only determinant columns its key declares; the command checks this. Rows are unique on (company, key, all determinant columns) with `NULLS NOT DISTINCT`.
10. Matching: a row matches when every determinant it sets equals the posting's value; a posting with no value for a determinant matches only rows that leave it empty. Among matching rows, compare their determinants in the key's order: the first determinant that one row sets and the other leaves empty decides. Example for `cost_of_goods_sold` (valuation class, warehouse, item group): a row with only the valuation class beats a row with warehouse and item group. The result is unique. If nothing matches, the posting is rejected with `account_determination_missing`, naming the key, the determinant values and the command that adds a row.
11. Partner keys (`receivable_reconciliation`, `payable_reconciliation`) read the partner's own `receivable_account_id` or `payable_account_id` at posting (DS-20), as SAP stores the reconciliation account on the business partner. Their rows, by `partner_group_id`, only give new partners their default; `CreatePartner` and `UpdatePartner` check the partner's accounts against rule 4. Changing the account of a partner with open items moves the items by `TransferPartnerOpenItems` ([ADR-0026](0026-open-item-core.md) rule 12). Customer and supplier advances use the same account and are told apart per open item (ADR-0010 rule 15). Moving open items when the account changes: [ADR-0026](0026-open-item-core.md) rule 12.
12. Before posting, the core checks the determined account against the key (rule 4); a mismatch is rejected with `account_determination_mismatch`, naming the key, the account and what was required. `CreateAccountDetermination` and `UpdateAccountDetermination` run the same check, so misconfiguration is caught when a row is saved; `DeleteAccountDetermination` removes a row, after which postings that matched only that row fail with `account_determination_missing`. A row's change affects only later postings; posted lines keep their account (ADR-0014). Changes are audited (DS-36).
13. The localization package supplies a default determination template per regime, written with its chart template's operational account codes and applied at company setup (DS-14, DS-19). Its CI checks every row against rule 4 and resolves every combination of key, valuation class, item group, partner group, tax code and currency that the template's documents can produce.

**Use by agents**

14. The query `GetAccountDetermination` (key, determinant values, company) returns the account a posting would use, the matching row and the check result — a computed result, an exception to ADR-0004 rule 21 as in ADR-0011 rule 14 — so an agent can explain a posting before simulating it (Principles 6, 13). `ListAccountDetermination` lists a company's rows.

## Context

DS-08 is needed by step 1 (posting) and step 2 (the determination table). Constraints:

- Transaction key (inventory posting, offsetting entry, GR/IR clearing, price difference, cost of goods sold …) × item valuation class × valuation area → operational account; the valuation area is the warehouse or the company per costing policy; non-inventory keys (revenue, AR/AP reconciliation, tax, FX) use other determinants (partner reconciliation account, tax code, item group) ([05](../spec/05-accounting-inventory-core.md)).
- Account determination is cross-checked against the system account the key requires (chart-of-accounts rule 5, [06](../spec/06-localization.md)); default determination per regime in the localization package (06). A change of costing method or scope is applied retrospectively ([08](../spec/08-l10n-vn.md#costing)).
- ADR-0010: system accounts, control kinds, determination by descendant or control kind. ADR-0014: transaction key on automatic lines.
- SAP practice (D5): OBYC inventory keys (BSX, WRX, PRD, GBB with account modifiers such as VAX, VBR, INV, BSA) with valuation classes; VKOA revenue determination by customer and material account assignment groups; reconciliation accounts on business partners; OB40 tax accounts per tax account key; OBA1 exchange-difference accounts ([SAP Learning: account determination](https://learning.sap.com/courses/cross-functional-customizing-in-sap-s-4hana-materials-management/setting-up-account-determination-for-specific-transactions)).
- ADR-0005: which account a regime uses for each key is an accounting rule (DS-19); the mechanism is the agent's.

## Options considered

| Option | For | Against |
| --- | --- | --- |
| One table per company with nullable determinants, matched by key order (chosen) | One place to look; deterministic; works for every key | The order rule must be learned; an example is in rule 10 |
| A separate table per key family (SAP OBYC, VKOA, OB40) | Each table has exactly its columns | Agents must know which table serves which key |
| Account modifiers as in SAP (GBB-VAX, GBB-VBR) | Familiar to SAP users | A second code per key; separate keys are explicit |
| Reconciliation account only in the table | One mechanism | One row per partner to move a customer; SAP keeps it on the partner |
| Valuation classes as a core catalog | Same in every company | Classes differ by business and regime |
| Key on every automatic line, including bank and closed accounts | Uniform | Those accounts come from the document or master data; a key would add nothing |

## Constraints that come with the decision

- DS-04: errors `account_determination_missing`, `account_determination_mismatch`; queries `GetAccountDetermination`, `ListAccountDetermination`.
- DS-09: stock movement keys (rule 1); how consumption separates selling from administrative expense; the key and value a sales return uses (open question on return cost); a migration for a change of valuation area level.
- DS-11: landed cost keys. DS-23: tax keys and duty codes. DS-25: payment, bank and clearing keys; moving open items when a partner's account changes.
- DS-14, DS-19: default determination templates and their CI checks; the TT99 template.
- DS-16: invariant that every line with a key passes rule 4.
- DS-20: valuation class and item group on items; partner groups and reconciliation accounts on partners; `valuation_area_level` on companies.

## Revisit when

- A key needs a determinant not in rule 3, e.g. revenue by customer group as SAP's VKOA allows.
- Matching by key order surprises users more than once in the pilot.

## Documents updated

- [docs/catalogs/transaction-keys.csv](../catalogs/transaction-keys.csv): new, version 0.1.0.
- [docs/catalogs/README.md](../catalogs/README.md): transaction keys status; valuation classes are company data.
- [docs/adr/0014-universal-journal.md](0014-universal-journal.md): note on lines without a key and on the two rounding keys.
- [docs/design/DS-04-command-envelope.md](../design/DS-04-command-envelope.md): two error codes.
- [docs/spec/00-reading-guide.md](../spec/00-reading-guide.md): glossary rows for account determination, determinant, item group, partner group, valuation area level; transaction key and valuation class rows updated.
- [docs/open-questions.md](../open-questions.md): TT99 targets for price and count differences; selling versus administrative consumption; change of valuation area level; the key for transfers out of `fx_difference_equity`.
- [docs/design/backlog.md](../design/backlog.md): DS-08 row links here.
- [docs/adr/README.md](README.md): index row.
- [docs/runbook/step-log.md](../runbook/step-log.md): entry.
