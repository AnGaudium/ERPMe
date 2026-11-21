Module: tax    Chunk: 1 of 2    Source ADRs: ADR-0018, ADR-0027, ADR-0041, ADR-0053, ADR-0080
Build step(s): 0, 2, 5, 7    Generated from index: 30d5706    Compiled by: Claude Fable 5.2, 2026-11-21

# Compiled spec: tax, chunk 1 (codes, rates, matrix, treatment, document taxes, computation, package)

## Purpose

`tax` owns tax codes, dated rates, the dated tax matrix, the tax treatment rules, the taxes and the tax treatment in a document's content, the immutable tax subledger with its adjustments, filed tax return snapshots, and e-invoice records and intents. It is a layer-3 module (ADR-0022 rule 2): it may import the `ledger` contract, and `ledger` never imports it. It does not own item tax groups, partner tax statuses and tax treatments (`master_data`), customs declarations (`purchasing`), the journal (`ledger`) or `posting_intent` (`documents`). It holds no country rule: a regime's values are package rows, or a company's own approved rows. This chunk holds R1 to R199: configuration, determination and computation. `tax-2.md` holds R201 and up: the subledger, deductibility, returns and e-invoices.

## Entities and tables

DDL: `docs/design/DS-05-platform.sql`. The module owns <!-- count:tables -->9<!-- /count --> tables with DDL; this chunk lists those its rules use, `tax-2.md` the others.

| Table | Meaning | Key | Parent | Owner |
| --- | --- | --- | --- | --- |
| `tax_code` | A package rule (`company_id` null) or a company's own code | `id`; unique `localization_package, code` | package or company | tax |
| `tax_rate` | A dated rate of a code | `id`; `uq_tax_rate_tax_code_id_effective_from` | `tax_code` | tax |
| `tax_matrix` | Package rows: direction, treatment code, item tax group code and date give tax codes | `id`; `uq_tax_matrix_key` | package (installation data) | tax |
| `company_tax_matrix` | A company's own matrix rows, never updated or deleted | `id`; `uq_company_tax_matrix_key` | company | tax |
| `tax_treatment_rule` | A dated rule that derives the tax treatment; package or company row | `id`; `uq_tax_treatment_rule_key` | package or company | tax |
| `document_tax_treatment` | The treatment of a document header (`line_number` null) and of each line | `id`; unique `document_id, line_number` | `document` | tax |
| `document_line_tax` | The tax of a document line, per tax code | `id`; unique `document_id, line_number, tax_code_id` | `document` | tax |

Reads (not owned): `item_tax_group`, `tax_treatment`, `partner_tax_status`, `partner`, `partner_address`, `site`, `product` and the product category (`master_data`); `document` (`documents`); `change_proposal`, `change_proposal_execution`; `derivation_trace`; `tax_line` (`tax-2.md`); the `transaction_key` catalog; `regime_setting`.

## Commands and queries

Where a cell says "not stated", the module's source units do not state it.

| Name | Actor and authorization | Input | Effect | Events | Errors |
| --- | --- | --- | --- | --- | --- |
| `GetDocumentTaxes` (query) | not stated | a document | reads its `document_line_tax` rows (R61) | none | not stated |

Contract function: `tax.contract.compute_taxes(lines, currency, rounding_level, prices_include_tax)` (R67); error `tax_inclusive_multiple_codes`. SQL functions: `tax_rate_in_force` (`tax_rate_missing`), `tax_effective_item_tax_group` (`item_tax_group_missing`, `item_tax_group_inactive`), `tax_treatment_derive` (`tax_treatment_missing`, `tax_treatment_ambiguous`), `tax_matrix_codes` (`tax_matrix_missing`), `tax_treatment_rule_never_applies`. The document verbs `Create` and `Update` compute the document's taxes (R61). A company's own tax rows are written by an executing change proposal (R41; errors `tax_change_proposal_invalid`, `tax_rate_row_invalid`, `tax_matrix_row_invalid`, `tax_treatment_rule_invalid`, `tax_history_scope`); the authorization leaf `tax_setup` covers tax codes and the tax matrix. The source units name no command for package or company tax rows.

## Rules

### Ownership

R1. `tax` owns e-invoice records and intents (DS-24), the computation of `document_line_tax`, the subledger `tax_line` with its adjustments, and filed `tax_return` snapshots. Its imports go downward (as ADR-0024 rule 22).
Source: ADR-0027.R8

R2. The same ownership list names, outside `tax`: `customs_declaration` and its tax rows, owned by `purchasing` from step 5 (ADR-0021 rule 10); audit records, owned by `audit` (layer 2, DS-36), with one row per executed command carrying `command_type`, `actor_kind`, `actor_id`, `agent_run_id`, `idempotency_key`, `origin_agent_run_id`, `on_behalf_of_id` and `policy_decision_id` (ADR-0038 rules 1–8); the full data export `ExportCompanyData` (DS-21; ADR-0044 rule 17); management reporting, which is the analysis layer of `query` over the DS-33 semantic views and never documents, whose measures over accounts equal ADR-0049's turnover for the same scope and range (`INV-411`; ADR-0060), while statutory reports stay DS-26; bad-debt provisions and prepaid amortization (DS-25, close tasks); the inventory write-down to net realizable value (DS-09, a close task).
Source: ADR-0027.R8, ADR-0027.R8.N1

R3. The core is regime-neutral. Values, enums, legal thresholds, account choices and legal rationale that are specific to one country belong to its localization package (`l10n_vn` for Vietnam; structure ADR-0016, content ADR-0039). A core rule may name Vietnam only as a labelled example or as a pointer to the package. Core property tests run on the fictional test package `l10n_xx`.
Source: ADR-0053.D0

### Tax codes

R4. `tax_code` holds one row per package and `code`, with a `name` (i18n); it also holds a company's own codes (R38).
Source: ADR-0041.R1

R5. `tax_kind` is one of `vat`, `sales_tax`, `excise`, `customs_duty` or `other`.
Source: ADR-0041.R1, ADR-0041.R1.N1, ADR-0053.R2

R6. A tax code may carry `package_kind`, the package's own name for the kind, from the list the package declares in `tax/package_kinds.csv` (`code`, `tax_kind`, names, basis columns). Each package kind belongs to exactly one core kind, a code's `package_kind` must belong to the code's `tax_kind`, and a package kind may not reuse a core kind's code.
Source: ADR-0041.R1.N1, ADR-0053.R2

R7. `direction` of a code is `sale`, `purchase` or `import`. Import codes are entered on the customs declaration and never determined by the matrix.
Source: ADR-0041.R1, ADR-0018.R16, ADR-0080.R6

R8. `calculation` is `percent` of the base; `none` for zero-rated, not-subject, not-declared and no-VAT codes, which record a base and no tax; or `assessed`, an amount stated by a customs declaration (ADR-0021). `sequence` is the order of codes on one line.
Source: ADR-0041.R1

R9. `base_includes` lists the core kinds or package kinds of the same line whose taxes are added to this code's base. A package kind selects only the codes that carry it, so a package can include one excise in a base and leave out another.
Source: ADR-0041.R1, ADR-0041.R1.N1, ADR-0053.R2

R10. Which package kinds a package declares, the core kind each belongs to, and what its codes name in `base_includes` are values of the localization package. `l10n_vn`'s mapping and its VAT bases are flagged package content, `unverified`, with their open questions; the core states none of these values.
Source: ADR-0041.R1.N1, ADR-0053.R2

R11. A code names its transaction key in `transaction_key_id`, a key to the `transaction_key` catalog (ADR-0004 rule 12); the package CSV keeps the key's code and the loader resolves it. `deductibility` is `deductible` or `not_deductible`, for purchase and import VAT codes. `import_treatment` is `capitalize` or `recoverable` (ADR-0021 rule 11).
Source: ADR-0041.R1, ADR-0041.R1.N2

R12. `fixed_asset_code` is an optional capital-goods mapping usable by any regime: the code a purchase or import line uses instead when it acquires a fixed asset (its account maps under `fixed_asset` or `construction_in_progress`), so its tax reaches the regime's capital-goods input tax account.
Source: ADR-0041.R1, ADR-0041.R1.N1, ADR-0053.R12

R13. `e_invoice_label`, the label an e-invoice prints for a code without a computed rate, is data of the e-invoice add-on (DS-24) and no column of the core `tax_code`; a percent code prints its rate. Until DS-24 defines its file, the draft column and the lab check of labels stay in DS-19's `tax_codes.csv`, marked as add-on data.
Source: ADR-0041.R1, ADR-0041.R1.N1, ADR-0053.R12

R14. Which return boxes a code feeds is defined by the return form (R238), not on the code.
Source: ADR-0041.R1

### Rates

R15. `tax_rate` has `id` (package rows: uuid5 of `'<package>:tax_rate:<code>:<effective_from>'`), `company_id` (null for a package row), `source` (`package` or `company`), `tax_code_id`, `effective_from`, `rate_percent` (`types.percent`, not negative; ADR-0006 rule 9), `basis` and `change_proposal_id`. `uq_tax_rate_tax_code_id_effective_from` allows one rate per code and effective date.
Source: ADR-0041.R2, ADR-0041.R2.N1

R16. The rate in force on a tax date is the row with the latest `effective_from` on or before it (`tax_rate_in_force`, STABLE); none raises `tax_rate_missing`.
Source: ADR-0041.R2.N1, ADR-0041.R7

R17. A rate change is one new dated row on the code; a temporary reduction is a rate row followed by a row restoring the rate. Each country's rates are its own package's, or, without a package, the company's own.
Source: ADR-0041.R2, ADR-0041.R2.N1

### Tax history guards

R18. In `tax_code`, `tax_rate`, `tax_matrix`, `company_tax_matrix` and `tax_treatment_rule`, no row that a posted tax row or a frozen treatment refers to is deleted. The keys of `document_line_tax` and `tax_line` refuse the delete of a used code or rate (`document_line_tax.tax_rate_id`, `tax_line.tax_rate_id`), the key of `document_tax_treatment` that of a used rule, and `trg_tax_matrix_check_delete` that of a package matrix row a posted `tax_line` used (its key, on or after its date). Company matrix rows are never deleted.
Source: ADR-0041.R2.N1, ADR-0041.R2.N2

R19. An unused row may be deleted, a future-dated rate included; the loader may replace or delete an unused package row.
Source: ADR-0041.R2.N1, ADR-0041.R2.N2

R20. A used row is immutable except its deactivation fields, of which the DDL of these tables has none (ADR-0016 rule 13). After insert, rates, matrix rows and treatment rules change only their `basis` (for rates: `trg_tax_rate_check_change`); they are ended by a later dated row, a null treatment code ending a rule. A code that a posted tax row uses changes only its name and basis (`tax_code_check_change`, `tax_code_used`).
Source: ADR-0041.R2, ADR-0041.R2.N1, ADR-0041.R2.N2

R21. A new `tax_rate` row may not be dated on or before the latest tax date already used by a posted `tax_line` of its code (`tax_rate_row_invalid`). A new matrix row or treatment rule may not be dated on or before the latest posted use of its key: direction, treatment code and item tax group code for the matrix (`tax_matrix_row_invalid`), direction and determinants for a rule (`tax_treatment_rule_invalid`).
Source: ADR-0041.R2.N2, ADR-0080.R3.N1

R22. The guard trigger functions run with definer rights and a pinned `search_path`, owned by `nativeflows_migration`, the loading role and the one role with `BYPASSRLS` (ADR-0017 rule 18; the ownership is set with the database roles, DS-18), because the checks must read every company's posted rows whatever role writes the row.
Source: ADR-0041.R2.N2

R23. Each guard first checks the scope of the row being written (`tax_history_check_scope`; error `tax_history_scope`): a company row only in its own company's session, a package row only under `installation` or by a role with `BYPASSRLS`.
Source: ADR-0041.R2.N2

R24. The guards then call the helpers `tax_matrix_key_last_use`, `tax_treatment_rule_key_last_use`, `tax_code_last_use` and `tax_code_is_used` with the company of that row: a company row's own company, or every company of the package only for a package row. The helpers run with their caller's rights, return only a date or a boolean, and have EXECUTE revoked from PUBLIC: only the definer triggers and the package loader call them, and no application role is granted them. An index on `tax_line (direction, tax_code_id, tax_date)` serves them.
Source: ADR-0041.R2.N2

R25. A draft's `document_line_tax` row names its rate row by key, so that rate counts as used and cannot be deleted while the draft holds it. `Update` recomputes the line and posting copies the frozen rows, so `tax_rate_missing` needs no check at posting.
Source: ADR-0041.R2.N2

### Statuses, treatments and item tax groups

R26. `partner_tax_status` (on `partner.partner_tax_status_id`) says what a party is and is an input. `tax_treatment`, with the directions it applies to, says what a transaction is and is the matrix axis. Both are package templates copied into the company, as the item tax groups are, and a company may add its own (basis `company_decision`). The core seeds neither list. No `partner_tax_group` exists, and no document column for one.
Source: ADR-0080.R1, ADR-0080.D0, ADR-0018.R16.N2, ADR-0041.R3

R27. The partner tax status read by the treatment derivation, and the tax ID copied to `tax_line`, are those of the document's bill-to party (else the sold-to partner) on sales and of its invoicing party on purchases (ADR-0074.R4.N1).
Source: ADR-0041.R3.N1

R28. Item tax groups are company data seeded by the localization package and named by nature, not by rate; the list is a package template whose basis the author verifies (DS-19, DS-23; ADR-0039 rule 10). Configured is the group, never the rate, on the product, the product category or the company.
Source: ADR-0018.R16, ADR-0041.R7.N1

R29. A product's effective item tax group is the product's own `item_tax_group_id` (nullable: empty inherits), else that of the nearest category up its `parent_id` chain with `default_item_tax_group_id`, else the company setting `tax.default_item_tax_group` in force on the tax date. None raises `item_tax_group_missing`. A group found at a level and not active raises `item_tax_group_inactive`; it is never skipped for a lower level.
Source: ADR-0018.R16, ADR-0018.R16.N1, ADR-0041.R7.N1

R30. `tax_effective_item_tax_group(company, product, date)`, STABLE with a pinned `search_path`, resolves it and returns the group and its level: `product`, `product_category` or `company`.
Source: ADR-0041.R7.N1

### Matrix

R31. The tax matrix maps (direction, `tax_treatment`, item tax group, effective date) to tax codes. `tax_matrix` is a package rule (ADR-0016 rule 5) and installation data like `regime_setting`: `tax_treatment_code` and `item_tax_group_code` (the groups by code), direction `sale` or `purchase` only, `tax_code_ids` (codes of the same package and direction, checked by `trg_tax_matrix_check_insert`), `is_adjustable` and `basis`. `uq_tax_matrix_key` allows one row per key and date.
Source: ADR-0041.R3, ADR-0041.R3.N2, ADR-0041.R3.N3, ADR-0080.R2, ADR-0080.D0

R32. `is_adjustable` is the package's mark that a company may define its own row for that key.
Source: ADR-0041.R3.N2

R33. `company_tax_matrix` keys on the company's own `tax_treatment_id` and `item_tax_group_id`, is append-only and needs an executed change proposal another person approved (R41).
Source: ADR-0041.R3, ADR-0041.R3.N2, ADR-0041.R3.N3, ADR-0080.R2

R34. A company matrix row is refused with `tax_matrix_row_invalid` where the company's package has a row for the same package, direction, tax treatment code and item tax group code that is not marked `is_adjustable`. With no package row, the key contains a group the company added itself, because the package covers all its own groups (R73). The refusal is early feedback only; the precedence of R35 holds without it.
Source: ADR-0041.R3, ADR-0041.R3.N2, ADR-0080.R3.N1

R35. For the key (direction, treatment code, item tax group code), the package row in force applies when it is not adjustable, whatever the load order or the company row's date. A company row applies only where no package row is in force for the key or the one in force is adjustable, so a package row dated after an older company row decides from its own date. `tax_matrix_codes` returns the codes of the treatment and the item tax group in this precedence.
Source: ADR-0041.R3.N2, ADR-0080.R3, ADR-0080.R3.N1

R36. Import duty and excise come from the customs declaration (DS-11), not from the matrix.
Source: ADR-0018.R16

### Verification gate and a company's own tax rows

R37. Reading an `unverified` tax code, rate or matrix row in a `production` installation fails with `regime_setting_unverified`, as for settings (ADR-0016 rule 12).
Source: ADR-0041.R4

R38. A company, also one in a country without a package, may define its own tax codes, dated rates and matrix rows for its own tax groups, and its own treatment rules. Each such row carries `source` `company`, the basis `company_decision` and `change_proposal_id`, and counts as verified for R37; its legal correctness is the company's responsibility (D12). The core seeds no rate.
Source: ADR-0041.R4.N1, ADR-0018.R16.N1, ADR-0080.R3

R39. A company row never silently shadows a package row. A company code begins with `x-`, so it never equals a package code (`ck_tax_code_company_code`). A company rate dates only a code of its own company (`tax_rate_row_invalid`). A company matrix row follows R34.
Source: ADR-0041.R4.N1

R40. `tax_code`, `tax_rate` and `tax_treatment_rule` hold package rows (`company_id` null) and company rows, and take the shared-reference row-level security of the ADR-0017 rule 19 note: every company reads the package rows and only its own.
Source: ADR-0041.R4.N1, ADR-0080.R3

R41. A company tax code, rate, matrix row or treatment rule is written only while its company's change proposal executes (ADR-0029 rule 3): the proposal's document is a `change_proposal` in state `approved` (set only by `Approve` from a human who wrote no version, ADR-0055 rule 7 condition 5), it has an item for the row's table, and its `change_proposal_execution` row exists by commit (a deferred constraint trigger). A draft, an approved but unexecuted, a closed or an unrelated proposal is refused with `tax_change_proposal_invalid` (`tax_change_proposal_check`, `tax_change_proposal_check_executed`).
Source: ADR-0041.R4.N1, ADR-0041.R4.N2

### Tax treatment rules

R42. `tax_treatment_rule` holds package rows and company rows. Its determinants, each empty for any value, are `document_type`, `ship_from_country`, `ship_to_country`, `is_tax_zone` (on `partner_address` and `site`), `partner_tax_status_code` and `item_kind` (`goods` or `service`); `direction` and `effective_from` are always filled.
Source: ADR-0080.R3, ADR-0080.D0

R43. Per source (package or company) and determinant set, the row in force is the one with the latest `effective_from` on or before the date; a null `tax_treatment_code` ends a rule.
Source: ADR-0080.R3

R44. Among the rows in force of one source that match, the row with the most filled determinants wins, then the higher `priority`. A remaining tie raises `tax_treatment_ambiguous`; no match, or a treatment the company lacks, raises `tax_treatment_missing`.
Source: ADR-0080.R3, ADR-0080.D0, ADR-0041.R7.N2

R45. Specificity counts the filled determinants and is no subset comparison: a row with more filled determinants beats a row with fewer, also when the fewer are narrower. The subset test of R47 applies only to replacing an adjustable package row. A country test is written as a specific row and a general one: (sale, ship-to `XX`) gives domestic and (sale) gives export, so a destination other than `XX` falls to export.
Source: ADR-0080.R3, ADR-0080.R3.N1

R46. Package rows are evaluated alone first, independent of load order and insert time; the package winner is chosen among the package rows alone by R44. If a package row in force matches and is not `is_adjustable`, it is the answer and no company row is considered; a company rule with more determinants or a higher priority never overrides it. Company rows are considered only when no package row in force matches or the matching package row is adjustable.
Source: ADR-0080.R3.N1

R47. Where the matching package row is adjustable, a company row replaces it only when the company row fills every determinant the package row fills, with the same value; a less specific company row, such as a company catch-all, leaves the package row the answer. Among the company rows that qualify, R44 applies.
Source: ADR-0080.R3.N1

R48. A company rule with the determinants of a package row not marked `is_adjustable` is refused at insert with `tax_treatment_rule_invalid`, as early feedback only. A company rule that a package rule not adjustable fully covers can never apply: the change proposal that would write it gets the check result `tax_treatment_rule_never_applies` (DS-04), from the function of that name its validation calls. It holds when, on the rule's effective date, the best package row in force among those that match every transaction the company rule matches is not adjustable; package rows dated later are not read.
Source: ADR-0080.R3, ADR-0080.R3.N1

R49. `tax_treatment_derive`, STABLE with a pinned `search_path`, derives the treatment and returns it with the rule used.
Source: ADR-0080.R3, ADR-0041.R7.N2

R50. No Incoterm is read (ADR-0068 stays advisory). The ship-from country is the address of the document's site or warehouse. The ship-to country and zone flag come from the address `tax.destination_party` names (ADR-0074 rules 1 to 4), or, for a service line, from `tax.services_place_of_supply`.
Source: ADR-0080.R6

### Tax treatment on the document

R51. `document_tax_treatment` holds the header's treatment (`line_number` null) and each line's. It is part of the content like `document_line_tax` and frozen with it. The header value defaults the lines; a line may differ. Every line with tax rows has a row (`INV-303`).
Source: ADR-0080.R4, ADR-0080.D0, ADR-0041.R7.N2

R52. `source` is `rule` (with `tax_treatment_rule_id`), `manual`, or `original` (copied from the corrected or reversed document). A manual row keeps what the rule gave in `derived_tax_treatment_id`; `differs_from_rule` raises the check result `tax_treatment_differs_from_rule`.
Source: ADR-0080.R4, ADR-0041.R7.N2, ADR-0018.R16.N2

R53. A correction's or reversal's header and every line take the original's treatment with source `original`; a line without its own row on the original takes the original's header. The correction's header equals the original's unless R54 applies. A reversal repeats the original exactly and never states another treatment. `document_tax_treatment_check_insert` enforces this.
Source: ADR-0080.R4, ADR-0080.R4.N1, ADR-0041.R7.N2

R54. To fix a wrong treatment on a posted document, the correction document names the original (`correction_of_id`) and states the corrected treatment on its header or lines with source `manual` and a `reason`; the row is flagged (`differs_from_rule`, `tax_treatment_differs_from_rule`).
Source: ADR-0080.R4.N1

### Settings

R55. The core registers these keys with their schemas, all with `date_basis` `document_date` (ADR-0016 rule 10): `tax.rate_date_basis` (per document type: which date is the tax date); `tax.declaration_date_basis` (`sale`, `purchase`, `import`); `tax.rounding_level` (`line` or `document`); `tax.stated_amount_tolerance` (per line, in minor units); `tax.apportionment` (the return boxes whose sum is taxable revenue and total revenue); and `tax.return_period`, an option a company picks (`monthly` or `quarterly`, ADR-0016 rule 11).
Source: ADR-0041.R5

R56. `tax.non_cash_payment_threshold` is no core key; its content is the parameters of a package-declared `payment_evidence_threshold` rule in `tax/deductibility_rules.yaml` (R216).
Source: ADR-0041.R5.N1, ADR-0053.R3

R57. Treatment settings (`settings.csv`): `tax.destination_party` names the party whose address gives the ship-to country and zone flag for goods, `ship_to` (default), `bill_to` or `payer`, and a package may set another value for its country; `tax.treatment_rederive_on_change` (default true): a change of ship-to, site or partner before the document freezes derives rows of source `rule` again; `tax.treatment_override.allowed`: who may set a treatment by hand, `document_editor`, `tax_setup` (default) or `none`; `tax.treatment_override.reason_required` (default true): a manual treatment that differs from the rule needs a reason.
Source: ADR-0080.R5, ADR-0080.R5.N1

R58. `tax.services_place_of_supply` is `customer_country` or `performance_location`, a regime key a package sets and flags. It has no core default and is a required regime setting (`fail_closed`), like the `movement_type.sales_return_receipt.*` pair: a company whose package sets no value, or a company without a package, fails with `regime_configuration_missing` when a service line needs it.
Source: ADR-0080.R5, ADR-0080.R5.N1

### Document taxes and determination

R59. A document line's taxes are rows of `document_line_tax`, one per line and tax code. They are part of the document's content, so in its version and its plan (ADR-0031 rule 1), and they replace any `tax_code_ids` array.
Source: ADR-0041.R6, ADR-0041.D0

R60. Each row has `tax_code_id`, `rate_percent`, `tax_rate_id`, the matrix row used as a derivation trace (`derivation_trace_id`; ADR-0027 rule 3), `item_tax_group_id` and `item_tax_group_source`, and in document currency `base_transaction_amount`, `tax_transaction_amount` (the amount used: the stated tax when there is one) and `computed_tax_transaction_amount` (the engine's own result). Purchase lines also carry `input_use`: `taxable` (the default), `non_taxable` or `shared`.
Source: ADR-0041.R6, ADR-0041.R6.N1, ADR-0041.R7.N1

R61. `Create` and `Update` compute the rows, and they freeze with the content, in `issuing` and `approved`. `GetDocumentTaxes` reads them, so DS-24 issues exactly these amounts. The frozen group and its level keep a drafted or posted line unchanged when a product, a category or the setting changes later.
Source: ADR-0041.R6, ADR-0041.R7.N1

R62. The codes of a line come from the matrix by direction, the document's or line's tax treatment, the product's effective item tax group (R29) and the tax date, and the line is checked against the matrix. The errors of determination are `tax_matrix_missing` and `tax_rate_missing`.
Source: ADR-0041.R7, ADR-0041.R7.N1, ADR-0041.R7.N2, ADR-0018.R16

R63. The tax date is read from `tax.rate_date_basis`: the invoice date for sales, the supplier's invoice date for purchases, the declaration date for imports (flagged).
Source: ADR-0041.R7

R64. A line may carry a tax code that differs from the matrix only when it is taken from an external document; the difference is the check result `tax_code_differs_from_matrix`, shown for review. This is interim and flagged: whether a line may differ is an open question for the author.
Source: ADR-0018.R16, ADR-0041.R7, ADR-0041.R7.N1

R65. A correction document (`correction_of_id`: a return, a credit note, an adjustment or replacement invoice, ADR-0009 rule 23) takes each corrected line's tax date, codes and rates from the original line (flagged); its declaration date is its own. A correction of an invoice from before a migration carries its original tax date and rate as entered fields (ADR-0044.R13).
Source: ADR-0041.R8

R66. A reversal copies the original's tax rows negated and never recomputes; its declaration date is its posting date.
Source: ADR-0041.R8

### Computation

R67. Computation is one pure function, `tax.contract.compute_taxes(lines, currency, rounding_level, prices_include_tax)`. Each line carries its amount and its codes, already resolved with `rate_percent`, `calculation`, `sequence` and `base_includes`; the function reads nothing else, and the client computes nothing (ADR-0040 rule 2).
Source: ADR-0041.R9, ADR-0041.D0

R68. Codes are applied in `sequence` across the whole document: each code is computed, rounded and, at document level, allocated before the codes that depend on it. A code's base is the line's net amount plus the line's taxes of earlier codes whose kind it includes. `none` codes give zero tax; `assessed` amounts and stated taxes are taken as given.
Source: ADR-0041.R9

R69. With `tax.rounding_level` `line`, each tax is rounded to the currency's minor unit with its rounding mode (ADR-0006 rule 17). With `document`, each code's total is rounded once and spread over the lines by largest remainder, normalized by the sign of the total, so a negated document gets exactly the negated taxes.
Source: ADR-0041.R9

R70. For prices including tax, base = gross ÷ (1 + rate), rounded, and tax = gross − base. This is allowed only with one `percent` code on the line (otherwise `tax_inclusive_multiple_codes`) and is always computed per line.
Source: ADR-0041.R9

R71. On lines from an external document (a supplier's invoice) the stated tax per code is the amount used. The function still computes its own, and a difference beyond `tax.stated_amount_tolerance` gives the check result `tax_amount_differs_from_computed`.
Source: ADR-0041.R10, ADR-0041.D0

### Package files and checks

R72. Package files (DS-14), at package level under `tax/`: `tax_codes.csv`, `tax_rates.csv`, `tax_matrix.csv`, `item_tax_groups.csv`, `package_kinds.csv`, `deductibility_rules.yaml` and `returns/`. DS-14 (tax file formats) names the files for partner tax statuses, tax treatments and treatment rules; the source units name none.
Source: ADR-0041.R20, ADR-0053.R2, ADR-0053.R3

R73. The lab check (`check_package.py`) verifies: enums and dates; one row per key and date; deductibility on purchase and import VAT codes; labels on sale codes without a rate (add-on data, R13); that the matrix covers every direction × applicable treatment × item group on every day from the first date; that every `percent` code has a rate on every such day; that every code's transaction key resolves in the regime's determination; that every return source parses and refers to existing codes and boxes, and every box a formula names exists; that the `tax.*` settings exist, without `tax.non_cash_payment_threshold`; that every row has a basis; and the core kinds, the declared package kinds with their core kind, `base_includes` and `deductibility_rules.yaml`.
Source: ADR-0041.R20, ADR-0041.R20.N1, ADR-0053.R2, ADR-0053.R3

### Transaction keys

R74. A tax without a transaction key of its own posts through `other_tax`, determined by tax code, with the required system account `tax_payable_other`. `transaction-keys.csv` has no key `environmental_protection_tax`.
Source: ADR-0053.R5

R75. The accounts behind `other_tax` are rows of the package's `account_determination.csv`, chosen by tax code; every tax code must resolve (ADR-0015 rule 13). `l10n_vn` does so with a generic `other_tax` row beside a row for its environmental protection tax code, which posts through `other_tax`; these rows are flagged package content, `unverified`. The core states no account value.
Source: ADR-0053.R5

R76. The keys `special_consumption_tax`, `import_export_duty` and `trade_remedy_duty` keep their names. Neutral names for them, whether `trade_remedy_duty` takes `has_regime_alternatives`, and the names of the system accounts `tax_payable_special_consumption` and `tax_payable_import_export_duty` are an open question while the key catalog is 0.x.
Source: ADR-0053.R5, ADR-0053.R17

### Neutral test cases, package content and scope

R77. The neutral edge cases take their values from the active package, so core CI runs them on `l10n_xx`'s fictional values: `EC-65` `credit_note_across_rate_change`, `EC-66` `payment_condition_failed`, `EC-27` `invoice_corrections` (event type `invoice_corrected`) and `EC-41` `import_across_holiday`. Their Vietnamese versions are golden scenarios of `l10n_vn`, whose expected values are the author's (ADR-0005 item 3); DS-19 has no list of golden scenarios yet (open question).
Source: ADR-0053.R10

R78. Neutral readings recorded by notes on other ADRs: in ADR-0048 rule 1 the Vietnamese voucher names are examples; in ADR-0048 rule 13 settling an excess as a further advance is regime-neutral, one open item per advance (the advance-account practice is `l10n_vn`'s reading); in ADR-0048 rule 15 the general journal approval seed is core segregation-of-duties practice; the account number in ADR-0037 rule 8 is a labelled `l10n_vn` example of work in process; in ADR-0009 rule 19 and ADR-0047 rule 1 "never reversible" for sales invoices and e-invoiced documents rests on the author's core decision of 2026-11-14, and the adjustment and replacement invoice forms are `l10n_vn`'s and the e-invoice add-on's; DS-20 `branch.is_declaring_unit` means "files tax returns separately"; in spec 07 realized FX differences post to the realized FX keys.
Source: ADR-0053.R14

R79. Not in Phase 1 unless the author decides otherwise (open question): the direct VAT method, foreign contractor tax withholding, personal income tax withholding, and capitalizing non-deductible VAT into stock or assets (`input_tax_non_deductible` requires an expense).
Source: ADR-0041.R22

R80. Also after Phase 1: taxes computed per physical quantity and the statistical unit of customs declarations. They will convert through `master_data.contract.convert_quantity` to the unit the package names, and stay package rules.
Source: ADR-0041.R22.N1

## Invariants

1. `INV-302` `company_tax_rows_approved` (area `tax`, check point `day`): every `tax_code`, `tax_rate`, `company_tax_matrix` and `tax_treatment_rule` row of source `company` names a change proposal of its company that has an item for the row's table and was executed (its `change_proposal_execution` exists), approved by a person other than its writers (ADR-0055 rule 7 condition 5); and no tax treatment or tax codes of a posted document came from a company row on a date when a package row of the company's package matched and was in force without `is_adjustable`, or from a company treatment rule that replaced an adjustable package rule whose filled determinants it does not all fill with the same values. For the matrix the key is the direction, tax treatment code and item tax group code; for treatment rules the direction and determinants. Protects R41, R35, R46, R47.
2. `INV-303` `document_tax_treatment_complete` (area `tax`, `day`): every document with tax rows has a header treatment, every line with tax rows its own row, a row of source `rule` names the rule that gives its treatment for the document's inputs and date, and the matrix rows its tax rows used are those of its treatment. Protects R51, R62.
3. `INV-411` `management_turnover_equals_report_turnover` (area `reporting`, check point `run`): named by the ownership note of R2; it protects no rule of `tax`.

## Edge cases

1. `EC-26` `tax_rate_change_mid_period`: a change of a fictional date-effective test tax code in mid-month, with invoices on both sides of the date. `must_succeed`.
2. `EC-65` `credit_note_across_rate_change`: a credit note corrects a sale after a rate change between the sale and the credit note; it keeps the original line's tax date and rate, and its declaration date is its own. `must_succeed`.
3. `EC-27` `invoice_corrections`: a posted sales invoice corrected by a correction document in the form the package defines (ADR-0009 rule 23). `must_succeed`.
4. `EC-41` `import_across_holiday` (area `planning`): an import whose supplier processing and transit span a multi-day holiday from the package calendar. `must_succeed`.

## Settings

| Key | Type | Scope | Core default | Rule |
| --- | --- | --- | --- | --- |
| `tax.default_item_tax_group` | code of an `item_tax_group` | company | unset | R29 |
| `tax.destination_party` | enum `ship_to`, `bill_to`, `payer` | company | `ship_to` | R57, R50 |
| `tax.services_place_of_supply` | enum `customer_country`, `performance_location` | regime (`regime_setting`) | none (`fail_closed`) | R58 |
| `tax.treatment_rederive_on_change` | boolean | company | true | R57 |
| `tax.treatment_override.allowed` | enum `document_editor`, `tax_setup`, `none` | company | `tax_setup` | R57 |
| `tax.treatment_override.reason_required` | boolean, `true_tighter` | company | true | R57 |
| `tax.rate_date_basis` | per document type: which date is the tax date | not stated | not stated | R55, R63 |
| `tax.rounding_level` | `line` or `document` | not stated | not stated | R55, R69 |
| `tax.stated_amount_tolerance` | per line, in minor units | not stated | not stated | R55, R71 |

R55 also registers `tax.declaration_date_basis`, `tax.apportionment` and `tax.return_period`, which the rules of `tax-2.md` read. `tax.non_cash_payment_threshold` is no core setting (R56). Named by R55 but absent from `settings.csv`: `tax.rate_date_basis`, `tax.declaration_date_basis`, `tax.rounding_level`, `tax.stated_amount_tolerance`, `tax.apportionment`, `tax.return_period`; the source units state no value type, scope or default beyond the cells above.

## UI annotations

None: the source units of this chunk carry no annotation of ADR-0077; the work item kinds of `tax` are listed in `tax-2.md`.

## Conflicts

CONFLICT ADR-0041.D0: its matrix by partner tax group is replaced by the treatment axis; ADR-0080.R2 governs, stated in R31.
CONFLICT ADR-0041.R1: the tax kind list, the column `transaction_key` and the core column `e_invoice_label` are replaced; ADR-0053.R2, ADR-0041.R1.N2 and ADR-0053.R12 govern (R5, R11, R13).
CONFLICT ADR-0041.R3: partner tax group columns and "company rows only for keys with a company-added group" are replaced; ADR-0080.R2 and ADR-0041.R3.N2 govern (R31, R34).
CONFLICT ADR-0041.R3.N1: the note's "partner tax group" of the bill-to or invoicing party reads partner tax status; ADR-0074.R4.N1 governs (R27).
CONFLICT ADR-0041.R5: its key list loses `tax.non_cash_payment_threshold`; ADR-0041.R5.N1 with ADR-0053.R3 governs (R55).
CONFLICT ADR-0041.R5.N1: `tax.non_cash_payment_threshold` left the core keys of rule 5; ADR-0053.R3 governs (R56).
CONFLICT ADR-0041.R7: its lookup by partner tax group and by the product's own group gives way to treatment and effective group; ADR-0041.R7.N2 and ADR-0041.R7.N1 govern (R62, R29).
CONFLICT ADR-0041.R8: its opening sentence on corrections of pre-migration invoices is an inline addition from ADR-0044 rule 13; applied in R65, nothing contradicted.
CONFLICT ADR-0041.R7.N2: the lookup reads the tax treatment where rule 7 read the document's partner tax group; ADR-0080.R3 and ADR-0080.R4 govern (R62).
CONFLICT ADR-0041.R20: `partner_tax_groups.csv` and coverage by partner group are read on the treatment axis; ADR-0080.R1 governs (R72, R73); the source units name no package file for statuses and treatments.
CONFLICT ADR-0041.R20.N1: the lab check requires `deductibility_rules.yaml` and the kinds where rule 20 required the threshold setting; ADR-0053.R2 and ADR-0053.R3 govern (R73).
CONFLICT ADR-0018.R16.N1: a product has an effective item tax group, own or inherited; this note with ADR-0041.R7.N1 governs over "each product has an `item_tax_group_id`" (R29).
CONFLICT ADR-0018.R16.N2: partners and documents carry no partner tax group; ADR-0080.R1 governs, with status and treatment (R26, R52).
CONFLICT ADR-0080.R5.N1: `tax.services_place_of_supply` has no core default; this note governs over the default `customer_country` of rule 5 (R58).
CONFLICT ADR-0080.R3.N1: no contradiction found with ADR-0080.R3, which defers to this note for the precedence; the note is the governing text of R46 and R47.
FALSE-POSITIVE ADR-0041.R2.N2: "no longer exists" describes a deleted rate row; the note adds the history guards and contradicts nothing.
CONFLICT ADR-0080.R4.N1: a correction may state a corrected treatment on its header with source `manual` and a reason, where rule 4 says its header must equal the original's; this note governs (R53, R54).

## Proposed (not law)

None.

## Trace

| Source | Where |
| --- | --- |
| ADR-0015.R3 | ref: ADR-0015.R3 |
| ADR-0015.R3.N1 | ref: ADR-0015.R3.N1 |
| ADR-0016.R13.N2 | ref: ADR-0016.R13.N2 |
| ADR-0018.R3.N4 | ref: ADR-0018.R3.N4 |
| ADR-0018.R16 | R7, R28-R29, R36, R62, R64 |
| ADR-0018.R16.N1 | R29, R38 |
| ADR-0018.R16.N2 | R26, R52 |
| ADR-0027.R8 | R1-R2, R244 |
| ADR-0027.R8.N1 | R2 |
| ADR-0041.R1 | R4-R5, R7-R9, R11-R14 |
| ADR-0041.R1.N1 | R5-R6, R9-R10, R12-R13 |
| ADR-0041.R1.N2 | R11 |
| ADR-0041.R2 | R15, R17, R20 |
| ADR-0041.R2.N1 | R15-R20 |
| ADR-0041.R2.N2 | R18-R25 |
| ADR-0041.R3 | R26, R31, R33-R34 |
| ADR-0041.R3.N1 | R27 |
| ADR-0041.R3.N2 | R31-R35 |
| ADR-0041.R3.N3 | R31, R33 |
| ADR-0041.R4 | R37 |
| ADR-0041.R4.N1 | R38-R41 |
| ADR-0041.R4.N2 | R41 |
| ADR-0041.R5 | R55 |
| ADR-0041.R5.N1 | R56 |
| ADR-0041.R6 | R59-R61 |
| ADR-0041.R6.N1 | R60, R202 |
| ADR-0041.R7 | R16, R62-R64 |
| ADR-0041.R7.N1 | R28-R30, R60-R62, R64 |
| ADR-0041.R7.N2 | R44, R49, R51-R53, R62 |
| ADR-0041.R8 | R65-R66 |
| ADR-0041.R9 | R67-R70 |
| ADR-0041.R10 | R71 |
| ADR-0041.R20 | R72-R73 |
| ADR-0041.R20.N1 | R73 |
| ADR-0041.R22 | R79 |
| ADR-0041.R22.N1 | R80 |
| ADR-0053.D0 | R3 |
| ADR-0053.R2 | R5-R6, R9-R10, R72-R73 |
| ADR-0053.R5 | R74-R76 |
| ADR-0053.R10 | R77 |
| ADR-0053.R12 | R12-R13 |
| ADR-0053.R14 | R78 |
| ADR-0053.R17 | R76 |
| ADR-0074.R4 | ref: ADR-0074.R4 |
| ADR-0074.R4.N1 | ref: ADR-0074.R4.N1 |
| ADR-0080.D0 | R26, R31, R42, R44, R51 |
| ADR-0080.R1 | R26 |
| ADR-0080.R2 | R31, R33 |
| ADR-0080.R3 | R35, R38, R40, R42-R45, R48-R49 |
| ADR-0080.R3.N1 | R21, R34-R35, R45-R48 |
| ADR-0080.R4 | R51-R53 |
| ADR-0080.R4.N1 | R53-R54 |
| ADR-0080.R5 | R57-R58 |
| ADR-0080.R5.N1 | R57-R58 |
| ADR-0080.R6 | R7, R50 |
