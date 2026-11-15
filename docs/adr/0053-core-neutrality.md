# ADR-0053: Core neutrality: Vietnamese accounting and tax as an overlay

Status: accepted (2026-11-15) under ADR-0005, reviewed by Claude Fable 5.2 (builder Claude Opus 5.5). Design item: none of its own; it amends DS-04, DS-06, DS-14, DS-16, DS-17, DS-19, DS-20, DS-22, DS-23 and DS-25. Related decisions: D3, D7, D8, D9, D16. ADR-0004, ADR-0005, ADR-0009, ADR-0015, ADR-0016, ADR-0019, ADR-0024, ADR-0027, ADR-0028, ADR-0032, ADR-0035, ADR-0037, ADR-0039, ADR-0040, ADR-0041, ADR-0043, ADR-0047, ADR-0048; spec 06, 07, 13, 17.

## Decision

The author ruled on 2026-11-15: Vietnamese accounting (VAS, TT99, TT133) and Vietnamese tax are an overlay outside the core. They live in the localization package `l10n_vn`: its structure is ADR-0016, its TT99 content ADR-0039, its data [DS-19-vietnam-tt99](../design/DS-19-vietnam-tt99/README.md). This ADR makes the ruling a core principle and fixes every leak an audit found.

**The core is regime-neutral.** Values, enums, legal thresholds, account choices and legal rationale that are specific to Vietnam belong to the package. A core rule may name Vietnam only as a labelled example ("e.g. 131 in TT99") or as a pointer to the package.

**What changes.**
- Tax kinds become a neutral list, and packages keep their own names in `package_kind`.
- The non-cash payment rule becomes one instance of a neutral deductibility condition that a package declares.
- Work item kinds, a transaction key, a partner kind and an approval-hold flag get neutral names or regime settings.
- Accounts the core fixed for Vietnam become regime alternatives.
- Core property tests run on a fictional test package, `l10n_xx`. Vietnamese edge-case values move to `l10n_vn`'s golden scenarios.
- Vietnamese content in accepted ADRs is marked as `l10n_vn`'s by notes.

Every amended ADR gets a note at the end of the amended rule, citing a rule of this ADR (ADR-0005).

### Rules

**Principle**

1. Core or overlay. A rule, value or name is overlay when its content comes from one country's law or standards. That covers a legal threshold, a legal enum, an account number, a form or a legal citation used as the reason for a behavior. Overlay content lives in a localization package. The core holds the mechanism, its neutral names and the schema a package fills.
   - **The test.** Would the rule read the same for a company in a country the core has never seen? If not, the country-specific part moves to a package, as a package rule, a package template or a regime setting (ADR-0016 rule 5).
   - **Allowed mentions in core text.** A labelled example ("e.g. 131 in TT99", "in Vietnam, a household business") or a pointer to the package ("`l10n_vn` seeds this"). Neither may be the only statement of a behavior.
   - **New design items** apply the test. ADR-0016's Decision paragraph already states the rule ("the core holds none of it"); this ADR makes it checkable item by item. [template.md](template.md) has no checklist, so it is not changed; reviewers apply the test as part of the spec check of ADR-0005.
   - **Not overlay:** the UI language (Vietnamese is shipped by the core, D8; rule 16), and decisions the author took for the core even when Vietnam motivated them (rule 14).

**Tax**

2. Tax kinds. The core `tax_kind` of a tax code is one of `vat`, `sales_tax`, `excise`, `customs_duty` or `other` (ADR-0041 rule 1 gets a note).
   - **Package names.** A tax code may carry `package_kind`, free text from a list the package declares in `tax/package_kinds.csv` (`code`, `tax_kind`, names, basis columns). Each package kind belongs to exactly one core kind, and a code's `package_kind` must belong to the code's `tax_kind`. A package kind may not reuse a core kind's code.
   - **`base_includes`** lists core kinds or package kinds of the same line. A package kind selects only the codes that carry it. So a package can include one excise in a base and leave out another.
   - **`l10n_vn`'s mapping**, `unverified` with the existing open question on Vietnamese tax codes:

     | Package kind | Core kind |
     | --- | --- |
     | `import_duty` | `customs_duty` |
     | `special_consumption` | `excise` |
     | `environmental_protection` | `excise` |
     | `trade_remedy` | `customs_duty` |

     VAT codes keep `tax_kind` `vat` and no package kind. Vietnamese VAT bases keep their content by naming package kinds: `special_consumption;environmental_protection`, and for imports `import_duty;special_consumption;environmental_protection`. So trade remedy duty stays out of the import VAT base, as before. Whether it should be in that base is unchanged and stays the author's question.
   - **The lab check** (`check_package.py`) validates core kinds, declared package kinds, their core kind and `base_includes`.
3. Deductibility. The core keeps a generic deductibility projection for purchase and import tax rows: `initial_deductibility` plus append-only `tax_line_adjustment` rows (ADR-0041 rules 11, 13–15 get notes).
   - **States:** `deductible`, `conditional`, `not_deductible`. `conditional` replaces `deductible_until_due`: the tax is deductible now, but a condition can still fail.
   - **Adjustment kinds:** `condition_met`, `condition_failed`, `apportionment`, `period_move`, `reversal_of_adjustment`. They replace `payment_evidence`, `cash_payment` and `due_date_lapse`. `condition_failed` records the condition type's failure reason in `reason`. For `payment_evidence_threshold` the reasons are `failing_method` (the old `cash_payment`) and `lapsed` (the old `due_date_lapse`).
   - **The projection:**

     | From | Event | To | Posting |
     | --- | --- | --- | --- |
     | (posting) | no condition applies, or the condition is met at posting | `deductible` | none |
     | (posting) | a condition applies and is not yet met | `conditional` | none |
     | (posting) | the condition fails at posting | `not_deductible` | the tax posts to expense |
     | (posting) | `input_use: non_taxable` | `not_deductible` | the tax posts straight to expense |
     | (posting) | `input_use: shared` | `deductible` until apportionment | `apportionment` adjustment (ADR-0041 rule 16) |
     | `deductible` | a later event brings the row under the condition (e.g. a later same-day document of the seller reaches the threshold) | `conditional` | none |
     | `conditional` | the condition is met for the whole amount | `deductible` | none |
     | `conditional` | the condition fails for a share | that share `not_deductible` | `condition_failed` adjustment to expense |
     | `not_deductible` (failed, reason `lapsed`) | the condition is met later | `deductible` | `condition_met` adjustment |
     | any | the settlement behind a state change is reversed | the state before it | `reversal_of_adjustment` when that change made an adjustment; otherwise none |

     Moves between `deductible` and `conditional` change no deductible amount and post nothing. The projection derives them from the condition's recorded inputs (the documents it aggregates and the settlements' evidence methods), so they need no adjustment row. A share that failed by `failing_method` stays `not_deductible`.

     Matching against an advance takes the advance's evidence method, and a credit note reduces the amount the condition covers, as ADR-0041 rule 15 already says.
   - **Conditions are package rules.** A package declares them in `tax/deductibility_rules.yaml`. Each entry has `code`, `condition_type`, `applies_to` (`tax_kind` and `directions`), `parameters`, `effective_from` and a basis (ADR-0016 rule 6). Its identity is (`code`, `effective_from`), and a used row never changes value (ADR-0016 rule 13).
   - **Condition types are core.** The core registers each type with its parameter schema and its evaluation. The first type is `payment_evidence_threshold`, with these parameters:
     - `threshold`: `amount`, `currency`, `includes_tax`;
     - `aggregation`: a `default` (`per_seller_per_day` or `per_document`), with optional overrides per document kind (`by_document_kind`);
     - `failing_methods`: the `evidence_method` values that fail the condition (rule 11). `none` never meets or fails it, and every other recorded method meets it;
     - `lapse`: `due_date` (the share still unpaid at the open item's due date fails, with reason `lapsed`) or `none`;
     - `exempt_document_kinds`: document kinds the condition never applies to.
   - **How `payment_evidence_threshold` is evaluated:**
     - **Which rule.** The rule row in force on the tax date of the invoice line (ADR-0041 rule 7). Posting fixes that row on the tax line (`deductibility_rule_id`, a note on ADR-0041 rule 11), so a later row never changes a posted line's condition.
     - **One rule at a time.** At most one rule may apply to a (`tax_kind`, direction) on any date. The loader rejects an overlap with the loader error `deductibility_rule_overlap`, reported at deploy time like `regime_setting_in_use`, and `check_package.py` rejects it too.
     - **The tested amount** is the document total, with its taxes when `includes_tax` is true and without them otherwise. Amounts compare in company currency: a document in another currency converts at its own applied rate (ADR-0011 rule 5). A company whose currency differs from the threshold's `currency` fails the evaluation with `regime_configuration_missing`.
     - **Aggregation.** `per_seller_per_day` sums the tested amounts of one seller's documents that share an invoice date (the supplier's invoice date). `per_document` tests each document alone.
     - **The comparison.** The condition applies when the tested amount is at or above `threshold.amount`.
   - **`l10n_vn`'s rule** `non_cash_payment_threshold`, `unverified`, with the existing open question on input VAT and non-cash payment:
     - applies to `vat` codes for `purchase` and `import`;
     - threshold VND 5,000,000 including VAT;
     - aggregation per seller per day, and per document for customs declarations, which keeps ADR-0041 rule 14's "imports below the threshold per shipment are outside it";
     - failing method `cash`;
     - lapse at the due date;
     - no exempt document kinds.
   - **The setting.** `tax.non_cash_payment_threshold` is no longer a core-registered setting (ADR-0041 rule 5 gets a note). Its content becomes the parameters of the package-declared rule above, under the package's own name. The lab check stops requiring it and validates `deductibility_rules.yaml` instead.
   - **The package kinds and rules files** join the tax component of ADR-0016 rule 5 (a note there).

   Note: which deductibility rule is in force. Per (`tax_kind`, direction), across codes, the entry with the latest `effective_from` on or before the tax date is in force. An entry of the core condition type `none` (no parameters) ends the rule before it, so no condition applies from its date. Two entries overlap only when they share (`tax_kind`, direction, `effective_from`); the loader's `deductibility_rule_overlap` and `check_package.py` reject that and nothing else. DS-14 says the same (holistic review, 2026-11-15).

   Note: the threshold is tested in the threshold's `currency`. A document total in another currency converts at the transaction lookup rate (ADR-0011 rule 11) on the tax date, and that applied rate is recorded on the tax line (`threshold_applied_rate_id`). This replaces the company-currency comparison and its `regime_configuration_missing` (holistic review, 2026-11-15).

   Note (catalog review, 2026-11-15): the loader error `deductibility_rule_overlap` is catalogued in [DS-14](../design/DS-14-localization-package.md) (Loader errors), not in DS-04; where this ADR lists it under DS-04, read DS-14.
4. Work item kinds (catalog `work-item-kinds.csv`):
   - `input_vat_payment_evidence` becomes `tax_condition_pending`: a tax line's deductibility condition is not yet met. It resolves by the system when the condition is met or fails.
   - `input_vat_not_deductible` becomes `tax_deductibility_changed`: a tax line's deductibility fell by a `condition_failed` adjustment, for a person to review.

   Module, subject, owner, due rule and resolution are unchanged. ADR-0041 names neither code (its rule 14 says "with a work item"), so its rule 14 note covers them.
5. Transaction key `other_tax`. `environmental_protection_tax` is dropped from `transaction-keys.csv`.
   - **The new key.** A tax without a key of its own posts through `other_tax`, determined by tax code, required system account `tax_payable_other`. The key count is unchanged.
   - **TT99 rows** (`account_determination.csv`, `unverified`):
     - `other_tax` with tax code `import_environmental_protection` → 33381, which keeps the old row's account;
     - a generic `other_tax` row → 33382 "Other taxes", so every tax code resolves (ADR-0015 rule 13).

     The package's environmental protection tax code moves to `other_tax`. It has no core key of its own, and it is an excise only in `l10n_vn`'s classification; a dedicated key would name one country's tax, so it posts through `other_tax`, with its account chosen by tax code.
   - **References.** The only ADR that names the old key is ADR-0041, in its constraints, which gets a note. ADR-0021 and ADR-0015 do not name it.
   - **Not renamed here:** `special_consumption_tax`, `import_export_duty` and `trade_remedy_duty` (rule 17).
6. Regime alternatives. Several keys gain alternatives in `required_system_accounts`, separated by `;`, with `has_regime_alternatives` set true, the format of `fx_gain_unrealized`:

   | Key | Required system accounts | TT99 row |
   | --- | --- | --- |
   | `cash_surplus` | `asset_surplus_pending;non_operating_income` | 3381, unchanged |
   | `cash_shortage` | `asset_shortage_pending;non_operating_expense` | 1381, unchanged |
   | `bank_charge` | `administrative_expense;financial_expense` (ADR-0048 rule 20 lets a company pick 635) | 6427, unchanged |
   | `production_abnormal_cost` | `cost_of_goods_sold;expense_other` | 6325, unchanged |
   | `production_unabsorbed_overhead` | `cost_of_goods_sold;expense_other` | 6325, unchanged |

   - **Meanings.** The meanings of the two production keys cite IAS 2 instead of VAS 02: paragraph 16 for abnormal amounts and paragraph 13 for unallocated fixed overhead. Both are recognized as an expense of the period; which expense is the regime's choice. VAS 02 stays `l10n_vn`'s rationale for 632.
   - **The column.** `has_regime_alternatives` now also marks keys that do not share a system account's code. It says the list holds alternatives a regime or company chooses between, not one required account. ADR-0027 rule 11 gets a note.
   - **Unchanged:** the INV-16 cross-check and the lab check, since a row must still map under one of the listed accounts. `expense_other` stays a stated unreached account of TT99.
   - **Notes** on ADR-0048 rule 20 and ADR-0035 rules 18 and 19.

**Master data and documents**

7. Partner kind. `household_business` becomes `sole_proprietorship`: an unincorporated business that is not registered as an enterprise, whose identifiers (tax ID, address) are its owner's.
   - **`l10n_vn`'s mapping.** The household business (hộ kinh doanh) maps here. The private enterprise (doanh nghiệp tư nhân, legal form `private_enterprise`) is a registered enterprise and maps to `organization`.
   - **Personal data.** Labels are `personal` when `partner_kind` is `individual` or `sole_proprietorship`.
   - **Vietnamese name.** `l10n_vn`'s terminology catalog names the value "Hộ kinh doanh" (`enum.partner_kind.sole_proprietorship`, ADR-0040 rule 15).
   - **Where it changes:**
     - the DS-20 DDL `ck_partner_kind`, a draft, edited directly;
     - notes on ADR-0019 rules 1 and 7, covering the term in its rules 4, 9, 11 and 18;
     - the glossary, spec 13, spec 17 and the wording of one open question.
8. Approval hold on invoices. For `sales_invoice`, `sales_return`, `credit_note` and `debit_note`, whether an approval hold is allowed is the regime's, through the setting `documents.issuance_without_delay`. True means the document is issued without delay, so no approval hold.
   - **Registry.** These four types are registered with `is_approval_hold_allowed: regime`, a third value beside `true` and `false` (ADR-0009 rule 2). Other types keep their fixed flags.
   - **Commands.** `Submit`, `Approve` and `Reject` are always generated for the four types. While the setting is true for the document's date, they are rejected at run time with `approval_hold_not_allowed` (precondition, a new DS-04 row), and the type behaves as `is_approval_hold_allowed: false`: ADR-0009 rule 12's interim (human only) and ADR-0043 rule 10 apply.
   - **The setting** is boolean, read through `regime_setting(company, key, document_date)`, with `date_basis` `document_date`.
   - **States with an e-invoice.** When the hold is allowed and an e-invoice is required (ADR-0028 rule 6), the states are `draft → pending_approval → approved → issuing → posted`. `Issue<Type>` is allowed only from `approved`. A rejection by the provider returns the document to `draft`, and it is submitted again. When the setting is true, ADR-0028 rule 6 applies as written: `draft → issuing → posted`.
   - **Core default false.** The key is the first optional key with a core default:
     - ADR-0016 rule 15's check that every required key has a row for each regime does not apply to it;
     - a regime without a row reads false instead of failing with `regime_configuration_missing` (ADR-0016 rule 10);
     - the default is core behavior, not a package rule, so it carries no basis and is not subject to the unverified gate of ADR-0016 rule 12. A package row overrides it and carries its own basis.
   - **`l10n_vn`** seeds it true at package level, for every regime, because it comes from invoice law, not from the accounting regime (`settings.yaml`, `unverified`, with a new open question). So Vietnamese behavior is unchanged.
   - **Notes** on ADR-0009 rules 2 and 12, ADR-0016 rules 10 and 15, ADR-0028 rule 6, ADR-0039 rule 9, ADR-0043 rule 10 and ADR-0047 rule 1.

   Note (flow review, 2026-11-15): whether an e-invoice is required ([ADR-0028](0028-document-lifecycle-hardening.md) rule 6) is the regime setting `documents.e_invoice_required`: a map from document type to boolean, read through `regime_setting(company, key, document_date)` with `date_basis` `document_date`. Only `is_e_invoice_capable` types may be named. It is the second optional key with a core default and is handled like `documents.issuance_without_delay` above: no row, or a type missing from the map, reads false, with no basis and outside the unverified gate. `l10n_vn` seeds it at package level, for every regime, true for `sales_invoice`, `sales_return`, `credit_note` and `debit_note` (`settings.yaml`, `unverified`, open question). Under `l10n_vn` these types therefore take `Issue<Type>`, `issuing` and the posting by `system` on behalf of the issuer (ADR-0028 rule 7); where the setting reads false they post with `Post<Type>`. Until the e-invoice add-on (DS-24) exists, the core build, the tests and the simulation use the deterministic stub adapter of ADR-0028 rule 12.

**Tests and catalogs**

9. Test packages. Core property tests (DS-16) run on `l10n_xx`, a minimal fictional test package, so core tests never depend on the overlay. `XX` is in the ISO 3166-1 user-assigned range, so it never names a real country.
   - **Contents:**
     - one regime, `test`;
     - every core-required setting, with dummy values;
     - a chart of about 30 accounts that satisfies ADR-0010 rule 17;
     - a default determination for every key;
     - two or three tax codes with a test rate change;
     - one `payment_evidence_threshold` rule with a fictional threshold.
   - **Bases.** Its entries carry the basis `test_fixture` (`basis` in CSV files, `status: test_fixture` in YAML), valid only in a package whose manifest sets `is_test_package: true`; `check_package.py` rejects it in any other package. `test_fixture` counts as verified for ADR-0016 rule 12.
   - **Production.** The loader refuses a test package at deploy time in a `production` installation. So gate tests never deploy one there. The harness either calls the gate as a function that takes the environment as input, or loads `l10n_xx` into its throwaway database and then sets that database's `environment` to `production` (ADR-0007 rule 15). Either way, single entries are marked `unverified` in the fixture.
   - **Notes** on ADR-0016 rules 6, 12 and 15.
   - **`l10n_vn`** runs in package-level golden tests and its dataset profiles (rule 15). Its golden scenarios stay a mandatory CI test of the package (ADR-0016 rule 15).
   - **DS-16** gets an amendment paragraph at its rule 18 (isolation).
   - **Who builds it.** `l10n_xx` is built with the test kit, not as a country package.
10. Edge cases (catalog `edge-cases.csv`, version 0.1.0). The neutral cases take their values from the active package, so core CI runs them on `l10n_xx`'s fictional values, in EC-26's style:
    - **EC-65** `credit_note_across_rate_change`: a credit note corrects a sale after a rate change of the profile's test tax code between the sale and the credit note. It keeps the original line's tax date and rate, and its declaration date is its own.
    - **EC-66**, renamed `payment_condition_failed`: a purchase invoice at or above the active package's payment-evidence threshold is paid partly by a method the package's condition lists as failing. The failing share of its input tax becomes non-deductible by a `condition_failed` adjustment, and a `tax_deductibility_changed` work item is raised.
    - **EC-27**, renamed `invoice_corrections`, with the event type `invoice_corrected`, which replaces `invoice_replaced` and `invoice_adjusted` in DS-17's Tax group: a posted sales invoice is corrected by a correction document in the form the package defines (ADR-0009 rule 23).
    - **EC-41**, renamed `import_across_holiday`: an import whose supplier processing and transit span a multi-day holiday from the package calendar.

    **The Vietnamese versions** become golden scenarios of `l10n_vn`:
    - a January 2027 credit note for a December 2026 sale at the reduced 8%;
    - a purchase invoice of at least VND 5,000,000 including VAT paid partly in cash;
    - a replaced and an adjusted e-invoice, with the e-invoice add-on;
    - an import across Tết.

    DS-19 has no list of golden scenarios yet, so an open question asks DS-19 to carry them. Their expected values are the author's (ADR-0005 item 3).
11. Settlement evidence. `journal_line.evidence_method` (DS-06, ADR-0048 rule 18, INV-97) keeps its name and values. It records how a settlement was paid, in any regime. Regimes use it through conditions such as `failing_methods` (rule 3); Vietnam's non-cash rule is one user. The DS-06 column comment and the glossary say so. Nothing is renamed: the column is committed and a running simulation refers to it. The consumer `tax_payment_evidence` and the function `tax.contract.record_payment_evidence` keep their names too: they record evidence, which any condition may read.
12. Tax code columns:
    - **`fixed_asset_code`** stays core. It is an optional capital-goods mapping, usable by any regime: the code a purchase or import line uses instead when it acquires a fixed asset, so its tax reaches the regime's capital-goods input tax account.
    - **`e_invoice_label`** leaves the core `tax_code`. It moves to the data of the e-invoice add-on (DS-24, now an add-on after the core). Until DS-24 defines its file, the draft column stays in DS-19's `tax_codes.csv`, and the lab check of labels stays with it, marked as add-on data.
    - **Notes** on ADR-0041 rule 1.

**Vietnamese content in core ADRs**

13. Ownership by notes:
    - **ADR-0041 rule 21** (the Vietnamese tax draft) and **ADR-0035 rule 16** (Vietnamese costing method names and the product cost sheet) are `l10n_vn`'s content, owned by ADR-0039.
    - **ADR-0039 rule 10** is amended: `l10n_vn` owns Vietnamese tax data (codes, rates, matrix, groups, return forms, package kinds, deductibility rules); DS-23 owns only the format.
    - **ADR-0032 rule 3**'s "best practice and Vietnamese rules together" reads "best practice; regimes configure".
14. Neutral rationale, by notes:
    - **ADR-0048 rule 1:** the Vietnamese voucher names are examples.
    - **ADR-0048 rule 13:** settling an excess as a further advance is regime-neutral: one open item per advance. The account-141 practice is `l10n_vn`'s reading.
    - **ADR-0048 rule 15:** the general journal approval seed is core segregation-of-duties practice, not a Vietnamese rule.
    - **ADR-0037 rule 8:** "154" reads "work in process (e.g. 154 in TT99)".
    - **ADR-0009 rule 19 and ADR-0047 rule 1:** "never reversible" for sales invoices and e-invoiced documents rests on the author's core decision of 2026-11-14. The adjustment and replacement invoice forms are `l10n_vn`'s and the e-invoice add-on's.
    - **DS-20** `branch.is_declaring_unit`: "files tax returns separately".
    - **Spec 07:** realized FX differences post "to the realized FX keys (e.g. 515/635 in TT99)".
15. Synthetic dataset. Business profiles and the tax ID generator are package-supplied (component "synthetic dataset parameters", ADR-0016 rule 5). The core simulator is country-neutral.
    - **`l10n_vn`** gets `vn_trading_small@1`, `vn_trading_medium@1` and the planned `vn_manufacturing_*` profile, with the official tax ID format and prefix of DS-17 rule 19.
    - **`l10n_xx`** supplies `xx_core_small@1`, which carries every edge case. Core CI runs it with the `min_small` check.
    - **`l10n_vn`** runs `vn_trading_small@1` with the same check in its package-level CI.
    - **Step gates** keep the datasets spec 12 names, the Vietnamese small and medium profiles, now run as `l10n_vn` package profiles. Changing a gate's dataset is the author's (ADR-0005 item 4).
    - **DS-17** gets an amendment paragraph.
    - **Spec 12** is unchanged (it is the author's). Its small and medium datasets are the `l10n_vn` profiles.
16. Terminology:
    - **Core:** UI language strings, including the Vietnamese UI (D8), and the core catalog's plain translations of system account and key names.
    - **`l10n_vn`'s terminology catalog:** Vietnamese accounting names for system accounts and keys (e.g. `income_summary` as "Xác định kết quả kinh doanh").
    - **Notes** on ADR-0016 rule 18 and ADR-0040 rules 15 and 19.

**Follow-ups**

17. Open questions:
    - **Neutral key names.** Neutral names for `special_consumption_tax`, `import_export_duty` and `trade_remedy_duty`, while the key catalog is 0.x. Whether `trade_remedy_duty` also takes `has_regime_alternatives` belongs to the same question, and so do the system accounts `tax_payable_special_consumption` and `tax_payable_import_export_duty`.
    - **Not needed:** a review of the remaining Vietnamese labelled examples, since rule 1 allows them.

## Context

The author's ruling of 2026-11-15 is the first sentence of the Decision. ADR-0048 already applied it to cash and bank. AGENTS.md and spec 06 already say the core contains no country's rules, and ADR-0016 built the package mechanism. But step 0 designs were written with the first pilot in mind, and an audit of the accepted ADRs, catalogs and drafts found these leaks:
- **Enums with Vietnamese values:** tax kinds, partner kind, deductibility states and adjustment kinds.
- **A legal threshold registered as a core setting:** `tax.non_cash_payment_threshold`.
- **Account choices and legal citations in the core key catalog:** VAS 02, 3381, 1381.
- **A per-type approval flag that encodes a Vietnamese issuance rule.**
- **Core tests and edge cases that depend on Vietnamese law:** the 8% reduction and the VND 5,000,000 threshold.
- **Vietnamese names in core rationale.**

SAP S/4HANA keeps country rules in country versions on top of a neutral core:
- tax codes per country, with a neutral tax type and condition types;
- deductibility per tax code;
- per-country procedures.

Odoo does the same with `l10n_*` modules and generic tax groups. ERPMe already follows that pattern. This ADR removes what slipped through.

## Options considered

| Option | For | Against |
| --- | --- | --- |
| Neutral core kinds with a package-declared `package_kind` (chosen) | Core logic can switch on five kinds; packages keep their own names; bases stay exact through package kinds | Two columns to read |
| Keep Vietnamese kinds in the core | No change | Every new country adds core enum values; breaks the ruling |
| Free package kinds only | Fully flexible | The core cannot reason about kinds (excise in a base, customs on imports) |
| Neutral deductibility states with package-declared conditions of core types (chosen) | One projection for every regime; the threshold is data with a basis; agents read one table | The core must name condition types |
| Package code computing deductibility | Any rule possible | ADR-0016 rule 17 forbids accounting logic in package code; not testable as data |
| `other_tax` by tax code (chosen) | One key for every minor tax; accounts by tax code | One more row per package for a dedicated account |
| A key per tax | Explicit | Catalog grows per country |
| Approval hold by regime setting; commands always generated and refused at run time (chosen) | Vietnamese behavior unchanged; neutral elsewhere; one registry entry per type | A third flag value; the first optional key with a core default |
| Keep `is_approval_hold_allowed: false` fixed per type | Simple | Encodes a Vietnamese issuance rule in the core registry |
| Fictional test package `l10n_xx` for core tests (chosen) | Core tests never move when Vietnamese law changes; a forcing function for complete required keys | One more package to keep |
| Core tests on `l10n_vn` | No extra package | Core tests break on overlay changes; unverified rules in every core test |
| Rename `evidence_method` | Even more neutral name | Committed column, running simulation; the name is already neutral |

## Constraints that come with the decision

- **Review rule.** Every new design item passes rule 1's test. A reviewer finding overlay content in core text is a should-fix finding.
- **No new Vietnamese values in core enums, catalogs or schemas.** Package kinds, package conditions and package terminology are the outlets.
- **ADR notes:**
  - ADR-0009 rules 2, 12, 19;
  - ADR-0016 rules 5, 6, 10, 12, 15, 18;
  - ADR-0019 rules 1, 7;
  - ADR-0027 rule 11;
  - ADR-0028 rule 6;
  - ADR-0032 rule 3;
  - ADR-0035 rules 16, 18, 19;
  - ADR-0037 rule 8;
  - ADR-0039 rules 9, 10;
  - ADR-0040 rules 15, 19;
  - ADR-0041 rules 1, 5, 11, 13, 14, 15, 20, 21 and its constraints;
  - ADR-0043 rule 10;
  - ADR-0047 rule 1;
  - ADR-0048 rules 1, 13, 15, 20.
- **Catalogs:**
  - `transaction-keys.csv`: `other_tax` replaces `environmental_protection_tax`; alternatives and meanings of rule 6;
  - `work-item-kinds.csv`: rule 4;
  - `edge-cases.csv`: EC-27, EC-41, EC-65, EC-66.
- **DS-04:** error `approval_hold_not_allowed`. The loader error `deductibility_rule_overlap` is reported at deploy time, like `regime_setting_in_use`.
- **DDL:** DS-20 `ck_partner_kind` and the `is_declaring_unit` comment; DS-06 the `evidence_method` comment.
- **Package draft (DS-19):**
  - `tax/tax_codes.csv`: `package_kind`, neutral kinds, `other_tax`;
  - new `tax/package_kinds.csv` and `tax/deductibility_rules.yaml`;
  - `settings.yaml` without `tax.non_cash_payment_threshold` and with `documents.issuance_without_delay`;
  - TT99 `account_determination.csv` with the `other_tax` rows;
  - the README.
- **Lab:** `check_package.py` checks neutral kinds, package kinds, `base_includes` and deductibility rules, no longer requires `tax.non_cash_payment_threshold`, rejects overlapping deductibility rules and `test_fixture` outside a test package, and has six new self-test mutations.
- **Design files:** DS-14 (tax file columns, test package flag), DS-16 (amendment at rule 18), DS-17 (amendment on profiles; the Tax event group).
- **Step 0 harness work:** builds `l10n_xx` (rule 9).
- **Later work:** DS-24 takes `e_invoice_label`.
- **Open questions:**
  - the approval hold setting;
  - `l10n_vn` golden scenarios;
  - neutral key names;
  - the non-cash question, pointed at the package rule.

## Revisit when

- A second country package (the basic US package, DS-38) needs a condition type or tax kind the core lacks.
- A regime needs deductibility logic that a parameterized condition type cannot express.
- The author decides that a Vietnam-motivated behavior should be core after all, or the reverse.

## Documents updated

- **ADRs:** notes in [ADR-0009](0009-document-lifecycle.md), [ADR-0016](0016-localization-package-structure.md), [ADR-0019](0019-partners-and-crm-foundation.md), [ADR-0027](0027-cross-cutting-ownership.md), [ADR-0028](0028-document-lifecycle-hardening.md), [ADR-0032](0032-phase-1-scope-with-production.md), [ADR-0035](0035-production-costing.md), [ADR-0037](0037-subcontracting.md), [ADR-0039](0039-vietnam-package-tt99.md), [ADR-0040](0040-ui-architecture.md), [ADR-0041](0041-tax-engine.md), [ADR-0043](0043-policy-and-approval.md), [ADR-0047](0047-commercial-documents-and-pricing.md), [ADR-0048](0048-cash-bank-receivables-payables.md).
- **Catalogs:** [transaction-keys.csv](../catalogs/transaction-keys.csv), [work-item-kinds.csv](../catalogs/work-item-kinds.csv), [edge-cases.csv](../catalogs/edge-cases.csv).
- **Design files:** [DS-04-command-envelope.md](../design/DS-04-command-envelope.md), [DS-06-universal-journal.sql](../design/DS-06-universal-journal.sql), [DS-14-localization-package.md](../design/DS-14-localization-package.md), [DS-16-invariants-and-harness.md](../design/DS-16-invariants-and-harness.md), [DS-17-synthetic-dataset.md](../design/DS-17-synthetic-dataset.md), [DS-20-master-data.sql](../design/DS-20-master-data.sql), [backlog.md](../design/backlog.md).
- **Package:** [DS-19-vietnam-tt99](../design/DS-19-vietnam-tt99/README.md): tax codes, package kinds, deductibility rules, settings, determination rows, README.
- **The lab:** [check_package.py](../reviews/2026-11-14-design-validation/lab/check_package.py).
- **Spec:** the glossary in [00-reading-guide.md](../spec/00-reading-guide.md); [07-shared-foundation.md](../spec/07-shared-foundation.md); [13-crm.md](../spec/13-crm.md); [17-seatmap-data-classification.md](../spec/17-seatmap-data-classification.md).
- **Open questions:** [docs/open-questions.md](../open-questions.md).
- **Index and log:** [docs/adr/README.md](README.md); [docs/runbook/step-log.md](../runbook/step-log.md) at acceptance.
