# ADR-0080: Tax treatment determination

Status: accepted (2026-11-21) by the chief architect under the author's delegation of that day ([decisions.md](../decisions.md), delegation note; [ADR-0005](0005-technical-decisions-delegated.md) note), on the author's request of the same day. Builder Claude Opus 5.5.
Design item: DS-23 (tax). Related decisions: D3, D5. ADR-0016, ADR-0018, ADR-0041, ADR-0063, ADR-0068, ADR-0074; spec 06, 08.

## Decision

Tax has two dimensions, the product and the transaction (the author, 2026-11-21). The tax matrix keys on exactly those two: (direction, `tax_treatment`, item tax group, effective date) → tax codes; rates stay dated on the tax code ([ADR-0041](0041-tax-engine.md) rule 2). The partner tax group of ADR-0041 rule 3 is split in two: `partner_tax_status` says what a party is and is an input; `tax_treatment` says what a transaction is and is the matrix axis. A dated rule table `tax_treatment_rule` derives the treatment from the document's direction, type, ship-from and ship-to countries, a zone flag, the partner's tax status and goods or service; the row with the most filled determinants wins, then the higher priority. The header and each line store the treatment and its source, frozen with the content. This is option B of the comparison in [reviews/2026-11-21-tax-determination-comparison.md](../reviews/2026-11-21-tax-determination-comparison.md); the form chosen is this short ADR, with notes on ADR-0041 rules 3 and 7, ADR-0018 rule 16 and ADR-0074 rule 4 pointing here, because the change adds tables, a derivation and settings that a note at a rule's end would scatter.

### Rules

1. **Status and treatment.** `partner_tax_status` (on `partner.partner_tax_status_id`; e.g. registered, not registered, foreign, exempt entity) and `tax_treatment` (with the directions it applies to; e.g. domestic, export of goods, import of goods, sale into a zone, cross-border service, reverse charge) are package templates copied into the company, as the groups are; the company may add its own (basis `company_decision`). The core seeds neither list: the derivation works on whatever codes the package and the company define. They replace `partner_tax_group`, which no longer exists.
2. **The matrix.** `tax_matrix.tax_treatment_code` replaces `partner_tax_group_code`; `company_tax_matrix.tax_treatment_id` replaces `partner_tax_group_id`. Everything else of ADR-0041 rules 2 to 4 and their notes of 2026-11-21 stays: dated rates, package rows, company rows under approval and `is_adjustable`.
3. **The rule table.** `tax_treatment_rule` holds package rows and company rows under the protection of the [ADR-0041](0041-tax-engine.md) rule 4 note (an approved change proposal, `source` `company`, no row with the determinants of a package row not marked `is_adjustable`: `tax_treatment_rule_invalid`). Determinants, each empty for any value: `document_type`, `ship_from_country`, `ship_to_country`, `is_tax_zone` (on `partner_address` and `site`), `partner_tax_status_code`, `item_kind` (`goods` or `service`); always `direction` and `effective_from`. Per determinant set, the row in force is the latest `effective_from` on or before the date, a company row before a package row; a null `tax_treatment_code` ends a rule. Among the rows in force that match, the most filled determinants win, then the higher `priority`; a remaining tie raises `tax_treatment_ambiguous`; no match, or a treatment the company lacks, raises `tax_treatment_missing`. The table takes the shared-reference row-level security of the [ADR-0017](0017-permission-envelope.md) rule 19 note of 2026-11-21 (every company reads package rows; with it, 384 tables and partitions have row-level security, 17 with a nullable `company_id`, 4 of them shared reference catalogs). One function, `tax_treatment_derive`, STABLE with a pinned `search_path`, does this and returns the treatment and the rule used; `tax_matrix_codes` then returns the codes of the treatment and the item tax group, a company row before a package row ([DS-05-platform.sql](../design/DS-05-platform.sql)). A country test is written as a specific row and a general one: (sale, ship-to `XX`) → domestic is more specific than (sale) → export, so a destination other than `XX` falls to export.
4. **On the document.** `document_tax_treatment` holds the header's treatment (`line_number` null) and each line's, part of the content like `document_line_tax` and frozen with it (ADR-0041 rule 6). `source` is `rule` (with `tax_treatment_rule_id`), `manual`, or `original` (copied from the corrected or reversed document, ADR-0041 rule 8; the header of a correction must equal the original's, by trigger). The header value defaults the lines; a line may differ, e.g. a cross-border service on a document of domestic goods. A manual row keeps what the rule gave in `derived_tax_treatment_id`; `differs_from_rule` raises the check result `tax_treatment_differs_from_rule`. Every line with tax rows has a row (INV-303).
5. **Settings** ([catalogs/settings.csv](../catalogs/settings.csv)), because the systems differ:
   - `tax.destination_party`: which party's address gives the ship-to country and zone flag for goods: `ship_to` (default), `bill_to` or `payer`;
   - `tax.services_place_of_supply`: `customer_country` (default) or `performance_location`, a regime key a package sets and flags, since it is a legal rule per country;
   - `tax.treatment_rederive_on_change`: a change of ship-to, site or partner before the document freezes derives rows of source `rule` again (default true);
   - `tax.treatment_override.allowed`: who may set a treatment by hand: `document_editor`, `tax_setup` (default) or `none`;
   - `tax.treatment_override.reason_required`: a manual treatment that differs from the rule needs a reason (default true).
6. **Not read.** No Incoterm is read ([ADR-0068](0068-sites-and-core-logistics-payment-master-data.md) stays advisory). The ship-from country is the address of the document's site or warehouse; the ship-to country and zone flag come from the address `tax.destination_party` names ([ADR-0074](0074-core-data-structure-additions.md) rules 1 to 4), or, for a service line, from `tax.services_place_of_supply`. Import codes stay entered on the customs declaration.

## Context

The author, 2026-11-21 (translated): tax has two dimensions, one by product, as discussed, and one by type of transaction; goods taxed at 10% are sold domestically at 10% and exported at 0%; look at how the large systems do it. The comparison (SAP S/4HANA, Dynamics 365, Oracle Fusion Tax, Odoo, NetSuite, SAP Business One) found that every system keeps a product category on the product and decides the transaction side per document from ship-to, ship-from, product kind and partner status, never from a partner attribute alone; nine of its twelve cases fail with the transaction type stored on the partner (a foreign customer with a domestic delivery, a domestic customer with delivery abroad, one partner with sites inside and outside a zone, mixed goods and services, and others).

## Options considered

| Option | For | Against |
| --- | --- | --- |
| A: a partner tax group on the document, overridable | One column | Cases 1, 2 and 4 to 8 depend on the user remembering |
| B: derived treatment, two-axis matrix (chosen) | Matches the surveyed systems; matrix, company rows and package rows keep their shape; one table and one function, testable from examples | A rule table and two new lists |
| C: full rule engine (Oracle, SAP condition technique) | Covers triangular trade and place of supply natively | Configuration becomes a program; against D5's lean first release; the extension path |

## Constraints that come with the decision

- **Catalogs:** five settings (rule 5; [ADR-0063](0063-configurable-policy-settings.md) rule 29 note); INV-303; DS-04 errors `tax_treatment_missing`, `tax_treatment_ambiguous`, `tax_treatment_rule_invalid` and check result `tax_treatment_differs_from_rule`.
- **DS-14:** `tax/tax_treatments.csv` (code, names, directions), `tax/partner_tax_statuses.csv` (code, names), `tax/tax_treatment_rules.csv`, and the matrix column `tax_treatment`.
- **Lab:** `t34_tax_configuration.py` part D.
- **Not decided here:** the legal content of any country (which cases are zero-rated, on what evidence); the Vietnam package's treatment list and rules come with the Vietnam rework (open questions).

## Revisit when

- A pilot needs triangular trade, chain transactions or a place of supply that the determinants cannot express (option C).
- A package needs a determinant the rule table lacks (e.g. a subdivision).

## Documents updated

- [ADR-0041](0041-tax-engine.md) rules 3 and 7, [ADR-0018](0018-product-and-item-model.md) rule 16, [ADR-0074](0074-core-data-structure-additions.md) rule 4, [ADR-0063](0063-configurable-policy-settings.md) rule 29: notes.
- [DS-05-platform.sql](../design/DS-05-platform.sql), [DS-20-master-data.sql](../design/DS-20-master-data.sql), [DS-04](../design/DS-04-command-envelope.md), [DS-14](../design/DS-14-localization-package.md), [DS-16](../design/DS-16-invariants-and-harness.md).
- Catalogs: settings, invariants, personal-data exclusions.
- [spec 00 glossary](../spec/00-reading-guide.md); [decisions.md](../decisions.md); [open-questions.md](../open-questions.md); [README](README.md).
