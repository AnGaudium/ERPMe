# ADR-0039: Vietnam package, TT99 regime content

Status: accepted (2026-11-14) under ADR-0005, reviewed by Claude Fable 5.2 (builder Claude Opus 5.5). Design item: DS-19. Related decisions: D3, D7, D9. Principles 6, 7. Chart-of-accounts rules 1–7. ADR-0003, ADR-0005, ADR-0009, ADR-0010, ADR-0011, ADR-0012, ADR-0014, ADR-0015, ADR-0016, ADR-0018, ADR-0020, ADR-0021, ADR-0023, ADR-0027, ADR-0030, ADR-0035, ADR-0037, ADR-0038; spec 06, 08.

## Decision

The Vietnam package's TT99 regime ships:
- an operational chart template with every account of Circular 99/2025/TT-BTC Appendix II, mapped to the system chart;
- a few detail accounts the package adds where one TT99 account must map to several system leaves, plus one technical account;
- a default account determination that resolves every combination its seed data can produce;
- the regime and package settings that earlier ADRs require.

**Draft data and checks.** The data is drafted now as design files in [docs/design/DS-19-vietnam-tt99/](../design/DS-19-vietnam-tt99/README.md), laid out as the package will be. It moves into `l10n/l10n_vn/` at step 1. A design-lab check, which becomes the package CI check, verifies the data against the core catalogs and the open questions, and tests itself with deliberately broken copies.

**Bases.**
- **TT99 accounts** whose row only restates Appendix II carry it as their legal source, not yet verified.
- **Package choices** are `unverified` with an open question: a detail account, a mapping not obvious from the account's nature, a node the package creates, a legal-form condition, or a cost behavior. Every determination row and every setting is a package choice too.
- **Author decisions.** Two entries carry them: the purchase invoice posting date, and the use of 515 and 635 for rounding.

Under ADR-0016 rule 12, production refuses unverified content until the author verifies it.

**DS-14 format changes.**
- **Chart template columns:** `condition` selects rows by the company's legal form, and `cost_behavior` seeds the variable or fixed behavior of production cost accounts.
- **New files:**
  - a determination format;
  - a partner group seed;
  - a statement of unreached system accounts;
  - legal forms in the manifest.

### Rules

**Location and source**

1. Until step 1, the package lives in `docs/design/DS-19-vietnam-tt99/` in the DS-14 layout. At step 1 it moves unchanged to `l10n/l10n_vn/` (DS-18), and the lab check becomes the package CI check (ADR-0016 rule 15).
   - **Package level:** `manifest.yaml` and `settings.yaml`.
   - **Regime level, under `regimes/tt99/`:** `chart_template.csv`, `account_determination.csv`, `unreached_system_accounts.csv`, `valuation_classes.csv`, `item_groups.csv`, `partner_groups.csv`, `close_checklist.yaml` and `settings.yaml`.
   - **Source of the account list.** It was taken from two independent reproductions of Appendix II, compared code by code, and checked against the sub-account counts in Part B. The Official Gazette scan has not been seen (open question).

**Chart template**

2. Contents. The template has all 184 TT99 codes (71 level-1 accounts) with English and Vietnamese names and the TT99 tree:
   - **Off-balance-sheet accounts.** TT99 has none. Items once kept there are tracked by the core: goods held for others as non-owned stock (ADR-0030), and written-off receivables as closed open items.
   - **3524.** Part A of Appendix II lists other provisions as 3525; Part B and every other source say 3524. The template uses 3524 (open question).
3. Detail accounts. Article 11 lets a company open detail accounts. The package adds them only where one TT99 account must map to several system leaves (ADR-0010 rule 11), or where the core needs an account TT99 lacks:

   | TT99 account | Detail accounts | System accounts |
   | --- | --- | --- |
   | 511 | 5111 merchandise, 5112 products, 5113 services, 5118 other | `revenue_goods` (two), `revenue_services`, `revenue_other` |
   | 515 | 5151 interest, 5152 realized FX, 5153 unrealized FX, 5154 rounding, 5155 payment discounts received, 5158 other | one leaf each |
   | 521 | 5211 trade discounts, 5212 returns, 5213 allowances | the three deduction leaves |
   | 632 | 6321 cost of goods sold, 6322 write-downs, 6323 inventory differences, 6324 price differences, 6325 production costs above normal | `cost_of_goods_sold` (6321, 6325), `inventory_write_down_expense`, `inventory_difference`, `price_difference` |
   | 635 | 6351 interest, 6352 realized FX, 6353 unrealized FX, 6354 rounding, 6355 payment discounts given, 6358 other | one leaf each |
   | 3388 | 33881 goods received not invoiced, 33882 purchase costs awaiting allocation, 33888 other | `gr_ir_clearing`, `purchase_cost_clearing`, `payable_other` |
   | 6277 | 62771 external processing of production orders, 62772 other outsourced services | `production_cost_other`, `production_cost_overhead` |
   | none | 999 opening balance clearing (technical, zero after migration) | `opening_balance_clearing` |

   - **Codes.** Detail codes reuse the Circular 200 codes accountants know where they existed (5111–5118, 5211–5213). They sit one level below a TT99 account, never at a TT99 level, so a later amendment cannot collide with them.
   - **Nodes.** 511, 515, 521, 632, 635, 3388 and 6277 become nodes, so a posting must use a detail account.
4. Mapping. Every postable account maps to the system leaf that matches its nature; presentation stays on operational accounts (ADR-0010 rule 8). These choices are `unverified` under one open question:
   - **Fixed and biological assets.** 212 finance-leased assets → `fixed_asset_tangible`. 21511 and 215121 → `fixed_asset_other`; 215122 → accumulated depreciation. 2152 and 2153 (one-harvest livestock and crops) → `asset_other`.
   - **Allowance for biological assets.** 2295 → `asset_other`, which has no contra leaf. Its credit balance is allowed (ADR-0010 rule 4), but reports by system account then show it as a negative asset.
   - **Inventory.** 158 (materials in bonded warehouses) → `inventory_raw_material`; the company adds a warehouse row to determine it (rule 7).
   - **Intercompany.** 136x and 336x → intercompany receivables and payables. Under VAS they serve only dependent units without legal status; group companies use 131 and 331 (open question on dependent units).
   - **Receivables and payables.** 1283 loans granted → `receivable_loan`. 332 dividends payable → `payable_other`.
   - **Liabilities.** 171 (government bond repurchase and resale) → `liability_other`, the usual credit side. 337 → `liability_other`. Funds 353x, 356x and 357 → `liability_other`.
   - **Production costs.** 623x (construction machinery) → `production_cost_overhead`. 621 → material, 622 → labor, 627x → overhead, 154 → work in process (ADR-0035 rule 18).
   - **Closing.** 911 → `income_summary`; 4211 and 4212 → `retained_earnings`. Carrying 4212 into 4211 at the new year is a closing task for step 8 (DS-26).
   - **Unreached accounts.** `unreached_system_accounts.csv` states the system accounts no operational account reaches and why: `inventory_other`, `income_other`, `expense_other` and `revenue_deduction_other`, for which TT99 has no account (ADR-0010 rule 17).
5. Legal form. TT99 opens 41111 and 41112 only for joint-stock companies, so 4111 is a node for them and a postable account for every other company.
   - **The `condition` column.** It is empty, `legal_form=<code>` or `legal_form!=<code>`.
   - **Legal forms.** The manifest declares them with their legal source: `joint_stock`, `limited_liability`, `private_enterprise` and `partnership`, under the Law on Enterprises. `CreateCompany` records `company.legal_form`, which is null for packages that declare none (DS-20; ADR-0027 rule 5).
   - **When it applies.** The legal form selects rows only when the company is set up.
   - **Conversion.** A company that later becomes joint stock keeps its postable 4111 (ADR-0010 rule 12). It opens 41111 and 41112 under 411 and moves the balance by a balance transfer, flagged.
6. Cost behavior. Every production cost account carries `cost_behavior`, because ADR-0035 rule 7 splits each pool group by it. The seeds are `unverified`:
   - **Variable:** 621, 622, 62771, 6272, 6273, 62772, 6232, 6233, 6237.
   - **Fixed:** 6271, 6274, 6275, 6278, 6231, 6234, 6238.
   - **Finer splits.** A company that needs one adds detail accounts.

**Default account determination**

7. Format: `transaction_key`, the determinant columns of ADR-0015 rule 9, `account_code`, the basis columns and a `note`. The determinant columns use seed codes for valuation class, item group and partner group. The template may name the package's own tax codes, as the fixed-asset input codes to 1332 do ([ADR-0041](0041-tax-engine.md) rule 1).
   - **Company data.** The template never names warehouses, tax codes or currencies, which are company data or DS-23's. Companies add those rows, for example a warehouse row to 158 for a bonded warehouse; DS-23 adds tax code rows, for example 1332 for input tax on fixed assets.
   - **Seeds:**
     - valuation classes `raw_material` (152), `tools_supplies` (153), `semi_finished` and `finished_goods` (155), `merchandise` (156);
     - item groups `merchandise`, `product`, `service`, `other` (5111, 5112, 5113, 5118);
     - partner groups `domestic`, `foreign`, `dependent_unit`, `employee`.
8. Interim choices, all `unverified` (the rounding rows cite the author's decision on 515 and 635; their detail accounts are the package's):
   - **Price differences.**
     - With a valuation class, they go to stock through `purchase_cost_clearing` and a landed cost (ADR-0015 rule 4; VAS 02).
     - Without one, they go to 6324: service invoice differences after an order closes (ADR-0037 rule 6), and order lines closed with quantity never received (ADR-0030 rule 4).
   - **GR/IR clearing.** 33881, presented under other payables, and a debit balance (invoice before goods) under goods in transit. A detail account under 331 mapped to `gr_ir_clearing` is the alternative closest to local practice.
   - **Purchase cost clearing.** 33882, which normally carries a debit balance, presented under other receivables. A detail account under 1388 is the alternative (DS-26).
   - **Stock count differences.** Shortage 1381 and surplus 3381, pending decision. The alternatives are 6323 or 711.
   - **Scrap.** 6323, as Circular 200 sends inventory losses to 632; the alternative is 811.
   - **Consumption.** 6422, and 6423 for tools and supplies. A company routes issues to 641x or 627x by adding rows (open question on purpose).
   - **Other movements.** Other issues 811; samples and gifts belong in 641. Other receipts 711. Capital contributed in kind has no allowed account under `other_receipt_offset` (open question).
   - **Revaluation and write-downs.** Revaluation offset 6323. Write-down 6322, allowance 2294.
   - **Foreign exchange.** Realized FX 5152 and 6352. Unrealized FX 5153 and 6353, straight to profit or loss. Circular 200's mechanics hold differences in 413 and move the net to 515 or 635, which gives the same year-end result under `fx.revaluation.frequency: fiscal_year_end`.
   - **Other income and expense.** Rounding 5154 and 6354. Payment discounts 5155 and 6355.
   - **Closing and migration.** Income summary 911, retained earnings 4212, opening balances 999.
   - **Reconciliation accounts.**
     - Defaults: 131 and 331.
     - Dependent units: 1368 and 3368.
     - Employees: 141 for advances. As suppliers, employees fall to 331, because no payable-control account fits them (open question).
   - **Production.** Production consumption 621. Output and WIP transfer 154. Abnormal, unabsorbed and residual cost 6325. External processing 62771. Processor stock stays on its inventory account (ADR-0037 rule 1).

**Settings**

9. Each choice is its own key, so each carries its own basis. The core registers every key with its schema (DS-18). There are 39 entries in all.
   - **Package level** (every regime): `reversal.method` (storno), `reversal.locked_period_posting_date`, `reversal.material_document_value`, `posting_date.default.purchase_invoice` (the author's decision), `posting_date.default.purchase_invoice_month_closed`, `posting_date.default.other`, `attachment_retention_years` (ADR-0038).
   - **Regime level, FX:**
     - rate dates and quotes: `fx.transaction_rate.date_basis` (posting date), `fx.transaction_rate.quote` and `fx.revaluation_rate.quote` (buy transfer for debit items, sell transfer for credit items, at most 7 days old), `fx.revaluation_rate.date_basis` (period end), `fx.document_rate.allowed`;
     - book and realized FX: `fx.book_rate_method`, `fx.realized_fx_basis` (ADR-0011 rule 16's `realized_fx_basis`);
     - revaluation: `fx.revaluation.frequency` (fiscal year end), `fx.revaluation.method` (reverse and repost), `fx.revaluation.target` (profit or loss), and `fx.revaluation.scope`, listed per system account (per open item, per balance, or none);
     - imports: `fx.import_receipt.rate`, `fx.import_receipt.invoice_difference`.
   - **Regime level, closing and inventory:** `closing.method` (entries every period), `journal.manual_posting_to_control_accounts` (false), the nine `movement_type.<code>.*` keys that movement-types.csv marks `regime`, `landed_cost.closed_period_method`, `stock_count.bin_difference_method`.
   - **Regime level, production (ADR-0035 rule 18):** `production.wip_method`, `production.abnormal_cost.applies`, `production.abnormal_cost.tolerance_percent` (0, because norms carry expected scrap), `production.normal_capacity.applies`, `production.co_product_split`, `production.estimate_price_basis`.
   - **Not settings:**
     - fixed in the core and flagged by ADR-0035: abnormal cost at period actual, the units-in-process definition, the negative residual offset, zero value under a capped planned WIP, the disassembly split, and the singular fallback;
     - core behavior: subledger activation (ADR-0034 rule 15);
     - company data: `wip_completion_percent`, pool allocation rules, the `by_product_price` list;
     - where accounts go: unabsorbed, abnormal and residual cost reach cost of goods sold through determination (rule 8);
     - the alternative accounting for processor stock, which would need a core change (ADR-0037 rule 1).
   - **Period pattern.** It is a package template, not a rule (ADR-0016 rule 5; ADR-0012 rule 1): `close_checklist.yaml` seeds monthly periods and one special period. Its tasks come in step 8.

   Note: the package level also carries `documents.issuance_without_delay` (true, `unverified`), and the non-cash threshold left the settings for the deductibility rule `non_cash_payment_threshold` ([ADR-0053](0053-core-neutrality.md) rules 3, 8).
10. Owned elsewhere, not shipped by DS-19:
    - tax codes, rates, `import_treatment` and item tax groups (DS-23, which ADR-0018 rule 16 and ADR-0021 rule 11 now point to);
    - statutory reports and close task content (DS-26, step 8);
    - numbering formats (ADR-0009 interim);
    - the e-invoice adapter (DS-24);
    - bank readers (DS-25);
    - data protection rules (DS-35); Note: these are the `data_protection` package rules ([ADR-0052](0052-minimal-crm.md) rule 24).
    - the working calendar (ADR-0024).

    Note: `l10n_vn` owns the Vietnamese tax data (codes, rates, matrix, groups, return forms, package kinds and deductibility rules) under this ADR; DS-23 owns only their format. `l10n_vn`'s golden scenarios are to be listed with DS-19 (open question) ([ADR-0053](0053-core-neutrality.md) rules 10, 13).

**Validation**

11. The lab check [check_package.py](../reviews/2026-11-14-design-validation/lab/check_package.py) runs for each declared legal form. It checks:
    - **Chart template:**
      - ADR-0010 rule 11, and the template analogues of rule 16: unique codes, parents present, no cycles, only leaves postable and mapped to postable leaves;
      - rule 17: every system account a transaction key or closing uses is reached, or stated with a reason; a stated account that is reached fails too;
      - values: `is_postable`, `cost_behavior` on exactly the production cost accounts, no currency in a template, and a condition or cost behavior only on a row whose basis is a package choice.
    - **Determination (ADR-0015 rules 4, 9, 10 and 13):**
      - only declared determinants, and no warehouse, tax code or currency in a template;
      - the required system account and control kind, and the inventory-node rule;
      - unique rows;
      - a unique match for every combination of seed values, including no valuation class on keys that do not require stock control.
    - **Bases (ADR-0016 rule 6):**
      - exactly one basis per entry;
      - a legal source with document, article and date;
      - an author decision with reference, date and name;
      - every open question cited must be an open (`- [ ]`) question in open-questions.md.
    - **Required settings:** the `movement_type.<code>.*` keys derived from the catalog.

    `--self-test` applies twelve broken copies, each of which must fail. They cover:
    - a receivable account on inventory and a mapping to an inner node;
    - a missing revenue row, a missing generic price difference row, and GR/IR on 331;
    - a cost-object account on the inventory key (control kind);
    - a cost behavior on a legal-source row, an unknown open question, a closed question cited, and a missing required setting;
    - a setting with two bases, and a removed unreached statement.

    Results: 209 combinations resolve for each legal form, the check passes, and the self-test passes. The first draft's defects are recorded as lab finding L-09.

## Context

DS-19 is the first item of step 1 ([steps-0-4.md](../runbook/steps-0-4.md)). TT99 replaced Circular 200 from 1 January 2026:
- it removes 7 level-1 accounts (161, 417, 441, 461, 466, 611, 631) and adds 215 and 332;
- it removes most level-2 accounts and lets companies design their own detail.

That freedom lets the package add the detail accounts the two-tier chart needs without departing from the circular. SAP reaches the same end with one G/L account per determination target.

The accounting choices are the author's (ADR-0005), so every one is flagged; the mechanism (formats, the check) is the agent's.

## Options considered

| Option | For | Against |
| --- | --- | --- |
| Detail accounts one level below TT99 accounts (chosen) | Codes accountants recognize; no collision with a future amendment | 511, 515, 521, 632, 635 become nodes |
| Map 515 and 635 whole to `financial_income_other` and `financial_expense_other` | No added accounts | FX, rounding and discount keys could not reach their leaves (ADR-0010 rule 11) |
| GR/IR as a detail under 3388 (chosen, interim) | Its own account; no partner open items | Local practice credits 331 |
| GR/IR as a detail under 331 | Presents with trade payables, as practice does | A partner account's subtree holds a non-partner clearing account |
| GR/IR on 331 itself | Common practice | 331 is a partner open-item account; GR/IR needs its own control kind |
| Template variants per legal form | Simple files | Duplicates 215 rows for a two-row difference |
| `condition` column (chosen) | One file; general | One more column for the loader |
| One setting object per topic | Fewer keys | One basis for many choices; the author could not verify them one by one |

## Constraints that come with the decision

- **ADR notes:**
  - ADR-0010 rules 5, 17: cost behavior on every production cost account; the statement file and the check.
  - ADR-0011 rules 13, 16: the FX seeds; the `fx.realized_fx_basis` key.
  - ADR-0012 rule 1: the period pattern template.
  - ADR-0015 rule 13: the template and the check.
  - ADR-0016 rules 1, 5: legal forms in the manifest; the partner groups and unreached statement components.
  - ADR-0018 rule 16 and ADR-0021 rule 11: item tax groups and `import_treatment` in DS-23.
  - ADR-0020 rule 5: the movement type seeds.
  - ADR-0021: presentation of 33882.
  - ADR-0027 rule 5: `company.legal_form`.
  - ADR-0035 rule 18: the production keys and cost behavior.
  - ADR-0030 rule 4 and ADR-0037 rule 6: those postings carry no valuation class.
  - ADR-0037 rule 1: the processor key.
  - ADR-0038 rule 15: the retention seed.
- **DS-14:** the `condition` and `cost_behavior` columns, the determination format, `partner_groups.csv`, `unreached_system_accounts.csv`, `legal_forms` in the manifest.
- **Other design items:**
  - DS-18: move the files at step 1; the check becomes package CI; register the setting keys.
  - DS-22: the posting of an order line closed with quantity never received, and of a subcontract service invoice difference after the order closed, carries no valuation class, so it reaches the generic price difference row (ADR-0030 rule 4; ADR-0037 rule 6).
  - DS-20: `company.legal_form`.
  - DS-23: tax code rows, `import_treatment`, item tax groups.
  - DS-26: presentation of 33881, 33882 and the detail accounts; carrying 4212 into 4211.
- **Open questions:**
  - detail accounts and mapping;
  - interim determination choices;
  - the TT99 text (3524 versus 3525, account names to check against the gazette);
  - period pattern;
  - capital contributed in kind;
  - employees as suppliers;
  - updates to the GR/IR, price difference and consumption questions.

## Revisit when

- The author verifies TT99 rules or the Official Gazette text differs from the reproductions.
- An amending circular changes Appendix II.
- A pilot's balances would put more than 5% of the balance-sheet total in an `_other` leaf (ADR-0010).

## Documents updated

- **The package draft:** [docs/design/DS-19-vietnam-tt99/](../design/DS-19-vietnam-tt99/README.md): new.
- **The lab:** [docs/reviews/2026-11-14-design-validation/](../reviews/2026-11-14-design-validation/README.md): `lab/check_package.py`, finding L-09.
- **ADRs:** [docs/adr/0010-system-chart-of-accounts.md](0010-system-chart-of-accounts.md), [docs/adr/0011-multi-currency.md](0011-multi-currency.md), [docs/adr/0012-posting-periods-and-closing.md](0012-posting-periods-and-closing.md), [docs/adr/0015-account-determination.md](0015-account-determination.md), [docs/adr/0016-localization-package-structure.md](0016-localization-package-structure.md), [docs/adr/0018-product-and-item-model.md](0018-product-and-item-model.md), [docs/adr/0020-inventory-and-costing-model.md](0020-inventory-and-costing-model.md), [docs/adr/0021-landed-cost.md](0021-landed-cost.md), [docs/adr/0027-cross-cutting-ownership.md](0027-cross-cutting-ownership.md), [docs/adr/0030-commercial-seams-and-imports.md](0030-commercial-seams-and-imports.md), [docs/adr/0035-production-costing.md](0035-production-costing.md), [docs/adr/0037-subcontracting.md](0037-subcontracting.md), [docs/adr/0038-audit-and-observability.md](0038-audit-and-observability.md): notes.
- **Design files:** [docs/design/DS-14-localization-package.md](../design/DS-14-localization-package.md), [docs/design/backlog.md](../design/backlog.md).
- **Glossary:** [docs/spec/00-reading-guide.md](../spec/00-reading-guide.md).
- **Open questions:** [docs/open-questions.md](../open-questions.md).
- **Index and log:** [docs/adr/README.md](README.md); [docs/runbook/step-log.md](../runbook/step-log.md) at acceptance.
