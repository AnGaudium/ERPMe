# ADR-0041: Tax engine

Status: accepted (2026-11-14) under ADR-0005, reviewed by Claude Fable 5.2 (builder Claude Opus 5.5). Design item: DS-23. Related decisions: D3, D9. Principles 2, 5, 6. ADR-0004, ADR-0005, ADR-0006, ADR-0007, ADR-0008, ADR-0009, ADR-0011, ADR-0012, ADR-0014, ADR-0015, ADR-0016, ADR-0018, ADR-0021, ADR-0026, ADR-0027, ADR-0028, ADR-0031, ADR-0038, ADR-0039, ADR-0040; spec 06, 08.

## Decision

Tax codes, dated rates and a dated tax matrix are package rules, read live. The matrix maps (direction, partner tax group, item tax group, date) to tax codes, as SAP's tax determination and Odoo's fiscal positions do.

**Document content.** A document's taxes are part of its content: one `document_line_tax` row per line and tax code, with base, rate and tax. They are computed by one pure function when the document is created or updated, and frozen with the content, so what an e-invoice sends is what posts. A supplier's stated tax is recorded as stated and checked against the computation.

**Tax subledger.** Posting copies those rows into the immutable tax subledger `tax_line`, with company-currency amounts that tie to the journal by construction. Everything that happens later is an append-only `tax_line_adjustment`:
- payment evidence for input VAT;
- apportionment;
- a later declaration period.

**Returns.** They are computed from the subledger by a package-defined form. A filed return is stored as an immutable snapshot, so later changes show as adjustments, never as a rewritten period.

**Vietnamese content.** It ships as draft package data: the 8% reduction ending on 2026-12-31, the non-cash payment rule, and the 01/GTGT mapping. All of it is flagged. Lab tests check the computation, the foreign-currency tie-out, corrections across the rate change, and the seed data.

### Rules

**Tax data**

1. `tax_code` (package rule, one row per package):
   - **Identity:** `code`, `name` (i18n).
   - **Kind and direction:**
     - `tax_kind`: `vat`, `import_duty`, `special_consumption`, `environmental_protection` or `trade_remedy`;
     - `direction`: `sale`, `purchase` or `import`. Import codes are entered on the customs declaration, never determined by the matrix (ADR-0018 rule 16 gets a note).
   - **Calculation:**
     - `calculation`: `percent` of the base; `none` for zero-rated, not-subject, not-declared and no-VAT codes, which record a base and no tax; or `assessed`, an amount stated by a customs declaration (ADR-0021).
     - `sequence`: the order of codes on one line.
     - `base_includes`: the tax kinds of the same line added to this code's base. For example, VAT's base includes special consumption and environmental protection tax.
   - **Posting and treatment:**
     - `transaction_key`;
     - `deductibility`: `deductible` or `not_deductible`, for purchase and import VAT;
     - `fixed_asset_code`: the code used instead when a purchase line acquires a fixed asset (its account maps under `fixed_asset` or `construction_in_progress`), so its tax reaches the fixed-asset input tax account;
     - `import_treatment`: `capitalize` or `recoverable` (ADR-0021 rule 11).
   - **Outputs:**
     - `e_invoice_label`: the label an e-invoice prints for a code without a computed rate (`0%`, `KCT`, `KKKNT`); a percent code prints its rate (DS-24).
     - Which return boxes a code feeds is defined by the return form (rule 19), not on the code.

   Note: `tax_kind` is one of `vat`, `sales_tax`, `excise`, `customs_duty` or `other`. A package keeps its own names in `package_kind`, declared in `tax/package_kinds.csv`, and `base_includes` may name core kinds or package kinds. `l10n_vn` maps `import_duty` and `trade_remedy` to `customs_duty`, and `special_consumption` and `environmental_protection` to `excise`; the base example above is `l10n_vn`'s. `fixed_asset_code` is an optional capital-goods mapping usable by any regime: the code a purchase or import line uses instead when it acquires a fixed asset, so its tax reaches the regime's capital-goods input tax account. `e_invoice_label` leaves the core `tax_code` for the data of the e-invoice add-on (DS-24); the draft column stays in DS-19 until DS-24 defines its file ([ADR-0053](0053-core-neutrality.md) rules 2, 12).

   Note (S2 findings closure, 2026-11-21): the column is `transaction_key_id`, a key to the `transaction_key` catalog (ADR-0004 rule 12); the package CSV keeps the code and the loader resolves it (chief architect's decision, 2026-11-17). The DDL is in [DS-05-platform.sql](../design/DS-05-platform.sql), section tax codes, owner `tax`, with the `tax_kind` values of the note above.
2. `tax_rate`: `tax_code`, `effective_from`, `rate_percent` (ADR-0006 rule 9) and basis.
   - **Temporary rates.** A temporary reduction is a rate row followed by a row restoring the rate.
   - **Used rows never change** (ADR-0016 rule 13).

   Note (chief architect, 2026-11-21, under the author's delegation of that day): the DDL is written ([DS-05-platform.sql](../design/DS-05-platform.sql), section tax codes, rates and matrix, owner `tax`). `tax_rate` has `id uuid` (package rows: uuid5 of `'<package>:tax_rate:<code>:<effective_from>'`, ADR-0016 rule 13 note), `company_id` (null for a package row; rule 4 note), `source` (`package` or `company`), `tax_code_id`, `effective_from`, `rate_percent` (`types.percent`, not negative), `basis` and `change_proposal_id`. `uq_tax_rate_tax_code_id_effective_from` makes "one rate per code and effective date" true. "Used rows never change" is held by the database: after insert only `basis` changes (`trg_tax_rate_check_change`), and a used row cannot be deleted, because `document_line_tax.tax_rate_id` and `tax_line.tax_rate_id` now refer to it by key; an unused package row may be replaced by the loader. The rate in force on a tax date is the latest `effective_from` on or before it (`tax_rate_in_force`, STABLE; none raises `tax_rate_missing`). This is also how rates that change over time and differ by country are configured: a rate change is one new dated row on the code, and each country's rates are its own package's (or, without a package, the company's own, rule 4 note). Lab `t34_tax_configuration.py` T10 to T14 and T18.

3. `tax_matrix`: `direction`, `partner_tax_group`, `item_tax_group`, `effective_from`, `tax_codes`, basis. It is a package rule (ADR-0016 rule 5).
   - **Company rows.** A company may add `company_tax_matrix` rows only for keys that contain a group the company added itself (ADR-0018 rule 16). A row that would shadow a package key is rejected with `tax_matrix_row_invalid`, so the legal mapping and its verification gate cannot be bypassed.
   - **Groups.** Item and partner tax groups are package templates copied into the company.

    Note ([ADR-0074](0074-core-data-structure-additions.md), 2026-11-21): the document's partner tax group, and the tax ID copied to `tax_line`, are those of its bill-to party (else the sold-to partner) on sales and of its invoicing party on purchases (ADR-0074 rule 4).

   Note (chief architect, 2026-11-21, under the author's delegation of that day): `tax_matrix` and `company_tax_matrix` are written in [DS-05-platform.sql](../design/DS-05-platform.sql). `tax_matrix` is installation data like `regime_setting`: the groups by code (a company's groups are copies of the package's templates), direction `sale` or `purchase` only (import codes are never determined), `tax_code_ids` (codes of the same package and direction, checked by `trg_tax_matrix_check_insert`), `is_adjustable` and `basis`; `uq_tax_matrix_key` makes one row per key and date. `is_adjustable` is the package's mark that a company may define its own row for that key; it reuses the mark of `retention_rule` ([ADR-0079](0079-personal-data-protection.md) rule 9), since no regime-setting flag of that kind exists. `company_tax_matrix` keys on the company's own groups (company keys), is append-only and needs an executed proposal another person approved. The protection of this rule is kept and stated exactly: a company row is refused with `tax_matrix_row_invalid` where the company's package has a row for the same package, direction and group codes that is not marked `is_adjustable`; with no package row, the key contains a group the company added itself, because the package covers all its own groups (rule 20). Where a company row and a package row are in force for one key (an adjustable key), the company row is used. INV-302 checks the approval and the shadowing; lab t34 T15, T15a and T24 to T28.

4. Production gate. Reading an `unverified` tax code, rate or matrix row in a `production` installation fails with `regime_setting_unverified`, as for settings (ADR-0016 rule 12).

   Note (chief architect, 2026-11-21, under the author's delegation of that day): a country without a package, or a company's own taxes. Applying the author's decision of 2026-11-21 on retention ([ADR-0079](0079-personal-data-protection.md) rule 9 notes: a company's own rule counts as verified; it is set through a change proposal another person approves; the core seeds no value), a company may define its own tax codes, dated rates and matrix rows for its own tax groups. Each is set only by executing a change proposal another person approves (`change_proposal_id`, INV-302), carries `source` `company` and the basis `company_decision`, and counts as verified for this rule because the company states it; its legal correctness is the company's responsibility, as with the routing switch (D12). A company row never silently shadows a package row: a company code begins with `x-`, so it never equals a package code (`ck_tax_code_company_code`, as company units on `uom`); a company rate dates only a code of its own company (`tax_rate_row_invalid`, so a package code's rate stays the package's); a company matrix row follows the rule 3 note. `tax_code` and `tax_rate` hold both kinds of row (company_id null for package rows) and take the shared-reference row-level security of the [ADR-0017](0017-permission-envelope.md) rule 19 note of this date: every company reads package rows and only its own. Before this note, ADR-0041 already allowed company matrix rows for keys with a company-added group (rule 3) and company-added item and partner groups ([ADR-0018](0018-product-and-item-model.md) rule 16); new are the company's own codes and rates, `source`, the approval and the `is_adjustable` mark. The core still seeds no rate. Lab t34 T19 to T27.

5. Settings. The core registers these keys with their schemas, all with `date_basis` `document_date` (ADR-0016 rule 10):
   - `tax.rate_date_basis` (per document type: which date is the tax date);
   - `tax.declaration_date_basis` (`sale`, `purchase`, `import`);
   - `tax.rounding_level` (`line` or `document`);
   - `tax.non_cash_payment_threshold` (amount, currency, whether VAT is included, same-day aggregation);
   - `tax.stated_amount_tolerance` (per line, in minor units);
   - `tax.apportionment` (the return boxes whose sum is taxable revenue and total revenue);
   - `tax.return_period`, an option a company picks (`monthly` or `quarterly`, ADR-0016 rule 11).

   Note: `tax.non_cash_payment_threshold` is no longer a core key. Its content is the parameters of a package-declared `payment_evidence_threshold` rule in `tax/deductibility_rules.yaml` ([ADR-0053](0053-core-neutrality.md) rule 3).

**Document taxes**

6. A document line's taxes are rows of `document_line_tax`. They are part of the document's content, so in its version and its plan (ADR-0031 rule 1). They replace any `tax_code_ids` array. Each row has:
   - **The code and rate:** `tax_code_id`, `rate_percent`, `tax_rate_id`, and the matrix row used, as a derivation trace (ADR-0027 rule 3).
   - **Amounts:** base and `tax` in document currency, where `tax` is the amount used (the stated tax when there is one), and `computed_tax`, the engine's own result.

   **When they are computed.** `Create` and `Update` compute them, and they freeze with the content, in `issuing` and `approved` (ADR-0028 rule 7). `GetDocumentTaxes` reads them, so DS-24 issues exactly these amounts.

   **Purchase lines** also carry `input_use`: `taxable` (the default), `non_taxable` or `shared` (rules 14, 16).

   Note (catalog review, 2026-11-15): column names in DS-05-platform.sql follow ADR-0004 rule 13: `base_transaction_amount`, `tax_transaction_amount` and `computed_tax_transaction_amount` on `document_line_tax`, and `base_transaction_amount` and `tax_transaction_amount` on `tax_line`, for base, `tax` and `computed_tax` in document currency.
7. Determination:
   - **Lookup.** The codes come from the matrix by direction, the document's partner tax group, the product's item tax group and the tax date.
   - **The tax date** is read from `tax.rate_date_basis`: the invoice date for sales, the supplier's invoice date for purchases, the declaration date for imports (flagged).
   - **Overrides.** A line may differ from the matrix only as ADR-0018 rule 16 allows, with the check result `tax_code_differs_from_matrix`.
   - **Errors:** `tax_matrix_missing`, `tax_rate_missing`.

   Note (chief architect, 2026-11-21, under the author's delegation of that day; the author's proposal and agreement of that day): tax configuration at three levels. The author proposed (2026-11-21, translated) that tax rates be configured globally, then per product category, then per product, the global default passing down and a category's or product's own value taking precedence, so that rates changing over periods and rates differing by country are solved. The chief architect proposed configuring the item tax group, not the rate, at those three levels, with rates dated on the tax code (rule 2), and the author agreed on 2026-11-21, finding configuration by tax group more correct than assigning a tax directly to the product. The reason: a rate change is then one new dated row on the code and history never changes, and the buyer side still decides the code through the matrix (partner tax group and direction, rule 3). The lookup of this rule takes the product's effective item tax group: the product's own `item_tax_group_id` (now nullable: empty inherits), else the nearest category up its `parent_id` chain with `default_item_tax_group_id`, else the company setting `tax.default_item_tax_group` in force on the tax date (a `code` setting naming an active `item_tax_group`, [ADR-0063](0063-configurable-policy-settings.md) rule 29 note); none raises `item_tax_group_missing` (DS-04). One SQL function resolves it, `tax_effective_item_tax_group(company, product, date)`, STABLE with a pinned `search_path`, returning the group and its level (`product`, `product_category` or `company`). A document line's tax rows already snapshot the code, rate and rate row (rule 6), and nothing recorded the group or its level, so `document_line_tax` gains `item_tax_group_id` and `item_tax_group_source`; frozen with the content, they keep a drafted or posted line unchanged when a product, a category or the setting changes later (lab t34 T03 to T09, T16, T17). A line may still differ from the matrix only as [ADR-0018](0018-product-and-item-model.md) rule 16 allows. The new error `tax_rate_row_invalid` belongs to the rule 4 note.

8. Corrections and reversals: A correction of an invoice from before a migration carries its original tax date and rate as entered fields ([ADR-0044](0044-data-migration-and-export.md) rule 13).
   - **Corrections.** A correction document (`correction_of_id`: a return, a credit note, an adjustment or replacement invoice, ADR-0009 rule 23) takes each corrected line's tax date, codes and rates from the original line, so a January 2027 credit note for a December 2026 sale at 8% stays at 8% (flagged). Its declaration date is its own.
   - **Reversals.** A reversal copies the original's tax rows negated and never recomputes; its declaration date is its posting date.
9. Computation is one pure function, `tax.contract.compute_taxes(lines, currency, rounding_level, prices_include_tax)`. Each line carries its amount and its codes, already resolved with `rate_percent`, `calculation`, `sequence` and `base_includes`. The function reads nothing else.
   - **Order and bases.** Codes are applied in `sequence` across the whole document: each code is computed, rounded and, at document level, allocated before the codes that depend on it. A code's base is the line's net amount plus the line's taxes of earlier codes whose kind it includes. `none` codes give zero tax. `assessed` amounts and stated taxes are taken as given.
   - **Rounding level** (`tax.rounding_level`):
     - `line` rounds each tax to the currency's minor unit with its rounding mode (ADR-0006 rule 17);
     - `document` rounds each code's total once and spreads it over the lines by largest remainder, normalized by the sign of the total, so a document negated gets exactly the negated taxes (lab finding L-10).
   - **Prices including tax.** Base = gross ÷ (1 + rate), rounded, and tax = gross − base. This is allowed only with one `percent` code on the line (otherwise `tax_inclusive_multiple_codes`), and it is always computed per line.
   - **The client computes nothing** (ADR-0040 rule 2).
10. Stated tax. On lines from an external document (a supplier's invoice), the stated tax per code is the amount used, because deductible VAT is the amount on the invoice. The function still computes its own, and a difference beyond `tax.stated_amount_tolerance` gives the check result `tax_amount_differs_from_computed`.

**Tax subledger**

11. Posting writes `tax_line` rows through `tax.contract.record_tax_lines`, in the posting transaction. Rows are immutable and owned by `tax`, and they are records in the plan (ADR-0031 rule 1). The sources are:
    - for sales and purchases, a copy of the posted version's `document_line_tax` rows;
    - for imports, the customs declaration's tax rows (ADR-0021).

    Each row has:
    - **Links and identity:** company, `declaring_unit` (the company, or a branch with `is_declaring_unit`, ADR-0027 rule 5), document and line, journal entry, the partner snapshot's tax ID (ADR-0028 rule 16);
    - **The tax:** `tax_code_id`, `tax_rate_id`, direction, `input_use`, `rate_percent`, and base and tax in document and company currency;
    - **Dates:** `tax_date`, `declaration_date`;
    - **Deductibility:** `initial_deductibility` (rule 14).

    **Zero rows.** Zero-rated, not-subject and no-VAT codes write rows with zero tax, so return bases come from `tax_line` alone.

    A branch is a declaring unit when `is_declaring_unit` is set ([ADR-0045](0045-master-data-and-price-lists.md) rule 8).

    Note: `initial_deductibility` takes the neutral states `deductible`, `conditional` or `not_deductible`. Each purchase or import row also records `deductibility_rule_id`, the package rule row in force on its tax date (null when none applies), fixed at posting ([ADR-0053](0053-core-neutrality.md) rule 3).
12. Company currency and the journal:
    - **Journal tax lines.** The journal gets one tax line per tax code and entry, converted once by `convert_amount` (ADR-0011 rule 5) and carrying `tax_code_id`. Base lines carry no tax code (ADR-0014 rule 9).
    - **Tax rows.** Their company amounts are that journal line's company amount, spread over the rows by largest remainder over their exact converted values, so the subledger and the journal tie by construction.
    - **Invariants:**
      - **INV-300:** per entry and code, the tax rows sum to the journal tax line in both currencies. That is the line posted through the code's `transaction_key` (for import VAT, the `import_tax` line), or through `input_tax_non_deductible` for rows with `input_use: non_taxable`; both carry `tax_code_id`.
      - **INV-301:** a posted document's tax rows equal its posted version's `document_line_tax`.

      They open a new group, INV-300 to INV-399, area `tax` (DS-16).

    Note: the journal gets one tax line per tax code, entry and tax line role. Recoverable import VAT therefore has two: the payable line through `import_tax` and the recoverable line through `input_tax` ([ADR-0021](0021-landed-cost.md) rule 11). INV-300 reads the `import_tax` line, as it says (holistic review, 2026-11-15).
13. Later changes are `tax_line_adjustment` rows, append-only:
    - **Columns:** `adjusts_tax_line_id`, `kind`, `deductible_delta` (in document and company currency; positive raises deductible VAT), `declaration_date`, `reason`, and the journal entry when one posts.
    - **Kinds:** `payment_evidence`, `cash_payment`, `due_date_lapse`, `apportionment`, `period_move`, `reversal_of_adjustment`.
    - **Postings.** An adjustment that moves VAT between input tax and expense posts a `tax_adjustment` document (`PostTaxAdjustment`, actor `system`) through `input_tax_non_deductible`. The posting carries the source line's dimensions (cost center, project, item) and posts on the adjustment's declaration date.

    Note: the kinds are `condition_met`, `condition_failed` (with the condition type's reason in `reason`, e.g. `failing_method` or `lapsed`), `apportionment`, `period_move` and `reversal_of_adjustment`. `payment_evidence`, `cash_payment` and `due_date_lapse` are gone ([ADR-0053](0053-core-neutrality.md) rule 3).

    Note: an adjustment whose declaration date falls in a period that does not admit it ([ADR-0012](0012-posting-periods-and-closing.md) rule 5's note: locked, or soft-locked without the capability) takes the first day of the earliest later period that admits it as its declaration date, so it is declared in that period's return, and raises a `tax_adjustment_redated` work item for the accountant (holistic review, 2026-11-15).

**Input VAT deductibility (Vietnam, flagged)**

14. A purchase or import VAT row's deductibility is a projection: its `initial_deductibility` plus its adjustments. The threshold is `tax.non_cash_payment_threshold`, seeded at VND 5,000,000 including VAT per invoice, with same-day invoices of one seller added together (VAT Law 48/2024 Article 14; Decree 181/2025 Article 26). Imports below the threshold per shipment are outside it.

    | From | Event | To | In box [25] | Posting |
    | --- | --- | --- | --- | --- |
    | (posting) | below the threshold, or paid non-cash at posting | `deductible` | yes | none |
    | (posting) | at or above the threshold, not yet paid | `deductible_until_due` | yes | none |
    | (posting) | paid in cash at posting, at or above the threshold | `not_deductible` | no | to expense |
    | (posting) | `input_use: non_taxable` | `not_deductible` | no | tax goes straight to expense |
    | (posting) | `input_use: shared` | `deductible` | yes, until apportionment | rule 16 |
    | `deductible` | a later same-day invoice of the seller reaches the threshold | `deductible_until_due` | yes | none |
    | `deductible_until_due` | non-cash payment evidence for the whole amount | `deductible` | yes | none |
    | `deductible_until_due` | a cash payment of part of the amount | that share `not_deductible` | no for the share | `cash_payment` adjustment to expense |
    | `deductible_until_due` | the due date passes with part unpaid | that share `not_deductible`, with a work item | no for the share | `due_date_lapse` adjustment to expense |
    | `not_deductible` (lapse) | later non-cash payment | `deductible` | yes, as a later adjustment | `payment_evidence` adjustment |
    | any | the payment or settlement is reversed | the state before it | as before | `reversal_of_adjustment` |
    | `deductible_until_due` | matched against an advance | as the advance's method gives | as that row | as that row |
    | `deductible_until_due` | matched against a credit note | the evidence-requiring amount drops by the credit | yes | none |

    Note: the core projection is neutral: states `deductible`, `conditional` (replacing `deductible_until_due`) and `not_deductible`, driven by package-declared conditions of core types. This table, the threshold and its legal sources are `l10n_vn`'s rule `non_cash_payment_threshold` of type `payment_evidence_threshold`, and "In box [25]" is its return box. The work items are `tax_condition_pending` and `tax_deductibility_changed` ([ADR-0053](0053-core-neutrality.md) rules 3, 4).

15. Payment evidence travels by event, so `ledger` never imports `tax` (ADR-0022 rule 2): Settlements of opening open items, which have no tax rows, are skipped ([ADR-0044](0044-data-migration-and-export.md) rule 13).
    - **The method.** Every settlement of an open item (ADR-0026 rule 6) records `evidence_method`: `cash`, `bank_transfer`, `card`, `offset` or `third_party`. It is recorded on the settlement because offsets have no payment document.
    - **The event.** `ledger` emits `OpenItemSettled` (item, amount, date, method, `reversal_of`) through the outbox.
    - **The consumer.** The transactional `tax` consumer `tax_payment_evidence` calls `tax.contract.record_payment_evidence` and, when a share becomes non-deductible, posts the `tax_adjustment` through the `ledger` contract (ADR-0013 rule 9). So the adjustment follows the payment; it is not in the payment's plan. `tax` may import the `ledger` contract (a note on ADR-0022 rule 2).
    - **Settlements that are not payments:**
      - matching an invoice against an advance inherits the advance's evidence method;
      - matching against a credit note reduces the amount that needs evidence and counts as neither cash nor an offset.
    - **Imports.** Import VAT rows follow the customs declaration's link to its supplier invoice lines (ADR-0021) to find the open items whose settlements give evidence.
    - **The due-date job.** A daily job applies `due_date_lapse`.

    Value `none` is added (write-offs, payment discounts, credit note matchings, balance transfers); a matching against an advance or a payment on account copies that item's own method, which its origin line records. The value is stored on the journal line ([ADR-0048](0048-cash-bank-receivables-payables.md) rule 18).

    Note: `evidence_method` records how a settlement was paid, in any regime; a condition's `failing_methods` decides what fails it. The due-date job applies `condition_failed` with reason `lapsed` where the condition has a lapse ([ADR-0053](0053-core-neutrality.md) rules 3, 11).
16. Apportionment. Rows with `input_use: shared` are apportioned at period end by the ratio of `tax.apportionment` (taxable revenue boxes over total revenue boxes), with an annual true-up at fiscal year end. A close task posts the result as `apportionment` adjustments.
17. Declaration date. It comes from `tax.declaration_date_basis`:
    - **Sales:** the invoice date.
    - **Purchases:** the invoice date; whether it should be the date a valid invoice is received is an open question.
    - **Imports:** the date of the tax payment voucher.
    - **Later periods.** Input VAT may be declared in a later period by a `period_move` adjustment, within the limit the author verifies (open question).

**Returns**

18. Returns are computed and filed per declaring unit and return period:
    - **Computing.** `GetTaxReturn` (form, period, declaring unit) computes the boxes from `tax_line` and adjustments whose declaration date is in the period.
    - **Filing.** `FileTaxReturn` stores an immutable `tax_return` snapshot: form, period, unit, `supplement_number` (0 for the original filing), the boxes, `filed_at`, `filed_by`, and the submission reference. `carry:` reads the latest filing of the previous period. When a supplementary return changes an earlier period's carried-forward box, the change reaches the current period through its prior-period boxes, not by rewriting later periods (flagged).
    - **After filing.** For a filed period, `GetTaxReturn` returns the snapshot and the difference from a fresh computation, which is what a supplementary return declares.
    - **Prior-period adjustments.** Adjustments declared in a period for rows of an earlier filed period feed that period's prior-period boxes (in Vietnam [37] and [38]), not the current deduction.
    - **Exporting** a return file is step 7 work on these queries (DS-26).

    Note: the export is `RenderTaxReturn` ([ADR-0049](0049-statutory-reporting-and-printing.md) rule 21).
19. A return form is package data, `tax/returns/<form>.csv`: `box`, labels, `source`, basis. Sources are separated by `;` and summed: With no earlier filed return, `carry:` reads the migration's `opening_vat_carry_forward` ([ADR-0044](0044-data-migration-and-export.md) rule 13).
    - `base:<code>` and `tax:<code>`;
    - `deductible:<code>`, the deductible tax of rows of the period after their adjustments;
    - `prior_decrease` and `prior_increase`, the prior-period adjustments of rule 18;
    - `formula:<expression>` over `[box]` references, with `+`, `−`, `pos(…)` and `neg(…)`;
    - `carry:<box>`, the box of the previous filed return.

    Form codes are lowercased with non-alphanumerics as `_`: `01/GTGT` is `01_gtgt` (ADR-0004 rule 5).

    Note: the minus sign in formulas is the ASCII `-`, as DS-14 and `01_gtgt.csv` write it; the `−` above means `-`. A form file gains an optional header (`effective_from`, `exports`) at its next version; until then the undated file is effective from the package's first date ([ADR-0049](0049-statutory-reporting-and-printing.md) rules 5, 21).

**Files and checks**

20. Package files (DS-14), at package level under `tax/`:
    - `tax_codes.csv`, `tax_rates.csv`, `tax_matrix.csv`;
    - `item_tax_groups.csv`, `partner_tax_groups.csv` (with the directions each partner group applies to);
    - `returns/`.

    The lab check verifies:
    - **Values:** enums and dates; one row per key and date; deductibility on purchase and import VAT codes; labels on sale codes without a rate.
    - **Coverage:**
      - the matrix covers every direction × applicable partner group × item group on every day from the first date;
      - every `percent` code has a rate on every such day;
      - every code's transaction key resolves in the regime's determination.
    - **Returns:** every source parses and refers to existing codes and boxes, and every box the form names in a formula exists.
    - **Settings:** the `tax.*` settings exist.
    - **Bases:** every row has one.

    Note: the check also validates the neutral tax kinds, package kinds, `base_includes` and `deductibility_rules.yaml`, and no longer requires `tax.non_cash_payment_threshold` ([ADR-0053](0053-core-neutrality.md) rules 2, 3).

**Vietnamese content (draft, all unverified)**

21. The Vietnamese draft lives in `docs/design/DS-19-vietnam-tt99/tax/`:
    - **Item tax groups:** `standard` (10%), `standard_reducible` (10%, at 8% from 2025-07-01 to 2026-12-31 under Resolution 204/2025/QH15 and Decree 174/2025/ND-CP), `reduced` (5%), `not_subject`, `not_declared`.
    - **Partner tax groups:** `domestic`, `export` (0% with the conditions of Decree 181 Article 18), `no_vat_invoice`, `foreign_supplier`.
    - **Codes:**
      - fixed-asset input codes, domestic and imported (to 1332);
      - a not-declared sale code (`KKKNT`, box [32a]);
      - import VAT at 10%, at the reducible rate and at 5%;
      - assessed import duty, excise, environmental protection tax and trade remedy duty.
    - **The 01/GTGT form:** bases and taxes by rate, deductible [25] from `deductible:`, prior-period [37]/[38], [22] carried from [43], and the computed boxes, in the Circular 80/2021 layout pending the Circular 89/2026 form. [23]/[24] include imports, and [23a]/[24a] are the import subset.
    - **Unconfirmed points** are open questions: the 8% at import, 8% sales in [32]/[33], the reduction appendix to the return, and the late-deduction limit.

    Note: this content is `l10n_vn`'s, owned by ADR-0039 ([ADR-0053](0053-core-neutrality.md) rule 13).
22. Not in Phase 1 unless the author decides otherwise (open question): the direct VAT method, foreign contractor tax withholding, personal income tax withholding, and capitalizing non-deductible VAT into stock or assets (`input_tax_non_deductible` requires an expense).

    Note ([ADR-0056](0056-multiple-units-of-measure.md), 2026-11-15): also after Phase 1: taxes computed per physical quantity (per litre, per kg) and the statistical unit of customs declarations. They will convert through `master_data.contract.convert_quantity` to the unit the package names, and stay package rules (rule 23).

## Context

DS-23 is needed by step 2 (data model) and step 7 (logic and returns). The Vietnamese texts changed in 2025–2026:
- **VAT:** Law 48/2024/QH15, and Decree 181/2025/ND-CP as amended by Decrees 359/2025 and 144/2026.
- **Invoices:** Decree 254/2026/ND-CP and Circular 91/2026/TT-BTC.
- **Tax administration:** Circular 89/2026/TT-BTC, which has a new 01/GTGT form from the third quarter of 2026.

The research behind this ADR read only some primary texts; unconfirmed points are open questions. The first review found that a mutable subledger, recomputation at posting, and live returns would let filed periods change silently. This version freezes taxes in the document, keeps the subledger append-only, and snapshots filed returns.

SAP stores tax items per document and declares through its advance return; Odoo maps taxes through fiscal positions and tax grids. NativeFlows combines a dated matrix with document tax rows, an append-only subledger and filed snapshots.

## Options considered

| Option | For | Against |
| --- | --- | --- |
| Taxes as document content (chosen) | What is issued is what posts; agents see taxes in simulation | One more child table |
| Recompute at posting | No stored rows | E-invoice and posting can differ |
| Immutable subledger with adjustments and filed snapshots (chosen) | Filed returns reproducible; supplementary returns are diffs | Two tables |
| Mutable deductibility state | Simple | Filed periods change silently |
| Journal tax line as the authority for company amounts (chosen) | Ties to the ledger by construction | Allocation step |
| Dated rates on stable codes (chosen) | The 8% window ends by data | The e-invoice label follows the rate |

## Constraints that come with the decision

- **Catalogs:**
  - transaction keys `input_tax_non_deductible`, `environmental_protection_tax`, `trade_remedy_duty`;
    - note: `environmental_protection_tax` is replaced by `other_tax`, determined by tax code ([ADR-0053](0053-core-neutrality.md) rule 5);
  - invariants INV-300 and INV-301 (a new group for tax);
  - edge cases for the credit note across the rate change and for cash above the threshold.
- **ADR notes:**
  - ADR-0014 rule 9: tax lines and no tax code on base lines;
  - ADR-0015: the keys;
  - ADR-0016 rule 5: the matrix as a package rule with gated company rows;
  - ADR-0018 rule 16: import codes are not determined;
  - ADR-0021 rule 11: import tax rows in `tax_line`;
  - ADR-0022 rule 2: `tax` may import the `ledger` contract, never the reverse;
  - ADR-0026 rule 6: `evidence_method` on settlements and the `OpenItemSettled` event;
  - ADR-0027: `tax` owns the subledger and returns;
  - ADR-0039 rule 7: tax code rows in the determination template.
- **DS-04:**
  - errors `tax_matrix_missing`, `tax_rate_missing`, `tax_matrix_row_invalid`, `tax_inclusive_multiple_codes`;
  - check results `tax_code_differs_from_matrix`, `tax_amount_differs_from_computed`.
- **DS-14:** the tax files and return grammar.
- **Other design items:**
  - DS-22: `document_line_tax`, `input_use`, `correction_of_id`, prices including tax;
  - DS-24: `GetDocumentTaxes` at `Issue`;
  - DS-25: payment methods and `record_payment_evidence`;
  - DS-26: return export.
- **Open questions:**
  - codes, matrix and boxes;
  - tax and declaration dates, including imports and corrections;
  - rounding level;
  - the deductibility table and threshold;
  - the late-deduction limit;
  - the reduction appendix;
  - the not-declared code;
  - Phase 1 scope of other regimes.

## Revisit when

- The author verifies the rules, a new decree or circular changes rates or forms, or the 8% reduction is extended.
- A pilot needs the direct method or contractor tax.

## Documents updated

- **The Vietnamese tax draft:** [docs/design/DS-19-vietnam-tt99/tax/](../design/DS-19-vietnam-tt99/README.md).
- **The lab:** [docs/reviews/2026-11-14-design-validation/](../reviews/2026-11-14-design-validation/README.md): `lab/tax_lab.py`, finding L-10; `check_package.py` tax checks.
- **Catalogs:** [docs/catalogs/transaction-keys.csv](../catalogs/transaction-keys.csv), [docs/catalogs/invariants.csv](../catalogs/invariants.csv), [docs/catalogs/edge-cases.csv](../catalogs/edge-cases.csv).
- **ADRs:** [docs/adr/0014-universal-journal.md](0014-universal-journal.md), [docs/adr/0015-account-determination.md](0015-account-determination.md), [docs/adr/0016-localization-package-structure.md](0016-localization-package-structure.md), [docs/adr/0018-product-and-item-model.md](0018-product-and-item-model.md), [docs/adr/0021-landed-cost.md](0021-landed-cost.md), [docs/adr/0026-open-item-core.md](0026-open-item-core.md), [docs/adr/0027-cross-cutting-ownership.md](0027-cross-cutting-ownership.md), [docs/adr/0039-vietnam-package-tt99.md](0039-vietnam-package-tt99.md): notes.
- **Design files:** [docs/design/DS-04-command-envelope.md](../design/DS-04-command-envelope.md), [docs/design/DS-14-localization-package.md](../design/DS-14-localization-package.md), [docs/design/DS-16-invariants-and-harness.md](../design/DS-16-invariants-and-harness.md), [docs/design/backlog.md](../design/backlog.md).
- **Glossary:** [docs/spec/00-reading-guide.md](../spec/00-reading-guide.md).
- **Open questions:** [docs/open-questions.md](../open-questions.md).
- **Index and log:** [docs/adr/README.md](README.md); [docs/runbook/step-log.md](../runbook/step-log.md) at acceptance.
