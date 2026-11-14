# ADR-0014: Universal journal data model

Status: accepted (2026-11-14) under ADR-0005, reviewed by Claude Fable 5.2. [ADR-0015](0015-account-determination.md) rule 5 says which lines have no transaction key; the rounding key of rule 15 is either `rounding_gain` or `rounding_loss`. Design item: DS-06. Related decisions: D4, D5, D7, D10. Principles 5, 6, 7. ADR-0004, ADR-0005, ADR-0006, ADR-0007, ADR-0008, ADR-0009, ADR-0010, ADR-0011, ADR-0012, ADR-0013.

## Decision

The books are two append-only tables: `journal_entry` (one per posted document that has an accounting effect) and `journal_line` (one table carrying every analytical dimension and the amounts in transaction, company and group currency). As in SAP's ACDOCA, amounts are signed (debit positive, credit negative), each line carries its `side`, and a storno line is flagged explicitly (`is_storno`, SAP's negative posting), so a balance is a plain sum and turnover per side is exact for the Vietnamese trial balance under either reversal method. Each line names its operational and system accounts, its transaction key, its material document line, its open item and its applied rates. Every entry balances to zero in each transaction currency, in company currency and in group currency, checked once per entry by a deferred constraint. Database triggers make the tables append-only, refuse lines in a locked period, and repeat the required-column checks. The DDL draft is [DS-06-universal-journal.sql](../design/DS-06-universal-journal.sql).

### Rules

**Entries**

1. A `journal_entry` is the accounting effect of one posted document: `id`, `company_id`, `document_id` (unique; zero or one entry per document, ADR-0009), `posting_date`, `document_date`, `posting_period_id`, `fiscal_year_id`, `is_closing_entry` (ADR-0012 rule 18), `close_task_id` (nullable; ADR-0012 rule 12), `database_transaction_number` (the PostgreSQL transaction that created it, set by a trigger, never by a client), `line_count` (the number of lines the posting writes) and `recorded_at`. Posting date, period and fiscal year are copied from the document at posting and never change.
2. A material document (DS-09) belongs to the same document, so "zero or one accounting document per material document" ([05](../spec/05-accounting-inventory-core.md)) holds by construction. An entry whose document has no material document is value-only (revaluations, costing adjustments).
3. Manual journal entries are documents of type `general_journal`; moving a balance from one operational account to another (ADR-0010 rule 12) uses documents of type `balance_transfer`. Both are internal documents (ADR-0009 rules 3, 19).
4. Within a posting date, journal entries have no business order; displays order by posting date and document number. The order in which costing processes stock movements of one day is defined by DS-09 (ADR-0007 rule 10).

**Lines**

5. `journal_line` columns:

| Group | Columns |
| --- | --- |
| Keys | `id`, `journal_entry_id`, `company_id`, `line_number` (unique within the entry), `posting_period_id` (copied from the entry) |
| Accounts | `account_id` (operational, postable; ADR-0010 rule 10), `system_account_id` (copied from the account's mapping, frozen after the first posting), `transaction_key_id` (DS-08; null when the account comes from the document or master data, ADR-0015 rule 5) |
| Side and amounts | `side` (`debit` or `credit`), `is_storno`; `transaction_currency`, `transaction_amount`; `company_currency`, `company_amount`; `group_currency`, `group_amount` (both null when the installation has no group currency; ADR-0011 rule 6); `company_applied_rate_id`, `group_applied_rate_id` (ADR-0011 rule 3) |
| Dimensions | `branch_id`, `partner_id`, `item_id`, `warehouse_id`, `cost_center_id`, `project_id`, `salesperson_id`, `tax_code_id`, `cost_object_id`, `fixed_asset_id` ([ADR-0025](0025-later-phase-seams.md)) (all nullable) |
| Links | `material_document_line_id`, `open_item_id`, `derivation_trace_id` (Principle 6) (all nullable) |
| Text and time | `description` (nullable, data label `internal`), `recorded_at` |

Currency columns are foreign keys to `currency.code`, named by currency type as the glossary defines; they are the one exception to ADR-0004 rule 12's `_id` suffix, because ISO 4217 codes are the key agents and people use.

6. Amounts are signed: positive is debit, negative is credit, in every currency. `side` says which turnover a line belongs to; `is_storno` says the line reduces that side's turnover. For a line that is not storno, every non-zero amount has the sign of its side, except the case of rule 7. For a storno line, every non-zero amount has the opposite sign, again except the case of rule 7. Balance of anything = `SUM(amount)`; debit turnover = `SUM(amount) WHERE side = 'debit'` (storno lines included, which lowers it); this is the "debit" that ADR-0008 rule 21 refers to.
7. An original adjustment line that changes only company or group amounts (realized FX, revaluation, rounding; ADR-0011 rule 2) has `transaction_amount = 0`; its side follows the sign of its company amount, or of its group amount when the company amount is zero, and its other amount may have the opposite sign. The rounding line (ADR-0006 rule 20) is such a line, with the company currency as transaction currency.
8. A reversal document (ADR-0009 rule 18) repeats the original's lines with the same line numbers and negated amounts: by the storno method with the same sides and `is_storno = true`, by the swapped method with opposite sides and `is_storno = false`; the localization package chooses the method (ADR-0009 rule 20). A correction document (ADR-0009 rule 23) has ordinary lines of its own.
9. The final dimension list is the canonical list of [05](../spec/05-accounting-inventory-core.md) (company, branch, account, partner, item, warehouse, cost center, project, salesperson) plus `tax_code_id`. Whether base lines (revenue, expense) also carry the tax code, as in SAP, so tax bases can be derived, is decided by DS-23. `salesperson_id` refers to a partner with the `employee` role (ADR-0019 rule 3; [ADR-0027](0027-cross-cutting-ownership.md) rule 6), and `cost_center_id` and `project_id` to tables that DS-20 defines (stubs from step 1). Intercompany lines use `partner_id` (ADR-0010 rule 14). Bins and catch weight are reserved on material document lines (DS-09). A new dimension is a new nullable column, added by ADR. Quantities are reached through `material_document_line_id`, not stored on journal lines. Added by [ADR-0025](0025-later-phase-seams.md) rule 1: nullable `cost_object_id` and `fixed_asset_id`. `journal_line` gains a nullable `purchase_order_line_id`, with its foreign key from step 5 ([ADR-0030](0030-commercial-seams-and-imports.md) rule 3).
10. Required columns by the system account's control kind (ADR-0010 rule 5): `receivable` and `payable` lines need `partner_id` and `open_item_id`; `inventory` lines need `item_id` and `warehouse_id`, and `material_document_line_id` when the entry's document has a material document. An account restricted to one currency accepts only lines in that transaction currency, and `company_currency` must be the company's currency. Whether manual `general_journal` lines may post to accounts whose control kind is not `none` is an open question for the author; interim, flagged: they may not, as SAP blocks direct postings to reconciliation accounts; the posting logic enforces this as a flagged setting, not the database. For the gated kinds `cost_object` (lines need `cost_object_id`), `fixed_asset` (`fixed_asset_id`) and `loan` (`partner_id`, `open_item_id`), these rules read the effective control kind: active only from the company's subledger activation ([ADR-0025](0025-later-phase-seams.md) rule 4). Open items and the one posting path: [ADR-0026](0026-open-item-core.md) rule 3. Lines on `gr_ir` accounts whose document line refers to a purchase order line need `purchase_order_line_id`, enforced by the posting handlers and detected by INV-37 ([ADR-0030](0030-commercial-seams-and-imports.md) rule 3).

**Integrity**

11. A deferred constraint trigger on `journal_entry` checks once per entry, at commit and when the dispatcher runs `SET CONSTRAINTS ALL IMMEDIATE` before hashing (ADR-0008 rule 9), that the entry has at least two lines and exactly `line_count` lines, that `SUM(transaction_amount)` is zero per transaction currency, that `SUM(company_amount)` is zero, and that group amounts are either all null or sum to zero. Posting code inserts all lines of an entry before the plan is hashed.
12. A `BEFORE INSERT` trigger on each line: first sets the account's `has_posting` if it is not yet set (ADR-0010 rule 12), which locks the account row and freezes its mapping; then takes `company_id` and `posting_period_id` from its entry and `system_account_id` from its account, and rejects a line that states different values; rejects a `line_number` above the entry's `line_count`; rejects a line whose entry was created in another transaction (`database_transaction_number`), so a posted entry never gains lines; finds the line's posting area from the control kind (`general` for every line in a special period, ADR-0012 rule 4), reads that area's state row `FOR SHARE`, and rejects the line when the row is missing or `locked`; and checks rules 6 and 7 and the required columns and currencies of rule 10.
13. `journal_entry` and `journal_line` accept only `INSERT`: triggers reject `UPDATE`, `DELETE` and `TRUNCATE`. Together with the document triggers (ADR-0009 rule 14) this is the second line of defence behind the commands (ADR-0002). Backups are restored with triggers disabled (DS-37), because `database_transaction_number` has meaning only inside its transaction. Row-level security on `company_id` follows DS-15.
14. In a plan (ADR-0008 rule 12), journal lines appear with their IDs tokenized, and without `database_transaction_number` and `recorded_at`. Journal rows get their IDs from `context.new_id`, never from a column default.
15. Invariants (DS-16) check that every line's `system_account_id` equals its account's mapping, that every entry balances per currency, that amounts are at their currency's minor unit (ADR-0006 rule 14), that each entry has at most one line with a rounding transaction key (`rounding_gain` or `rounding_loss`), and that the period balance cache equals the lines.

**Indexes and reads**

16. Indexes on `journal_line`: `(company_id, account_id, posting_period_id)`, `(company_id, system_account_id, posting_period_id)`, `(company_id, partner_id)` where not null, `(open_item_id)` where not null, `(material_document_line_id)` where not null. On `journal_entry`: `(company_id, posting_date)` for balances as of a date (ADR-0007 rule 23) and `(posting_period_id, close_task_id)` for close task staleness (ADR-0012 rule 12).
17. AR/AP subledgers and inventory value are views over `journal_line` (and open items, [ADR-0026](0026-open-item-core.md)), not separate ledgers ([05](../spec/05-accounting-inventory-core.md)). Agents and reports read through the read-only query layer (DS-33). The open item cache equals its lines (INV-33; [ADR-0026](0026-open-item-core.md)).
18. `account_period_balance` caches, per (`company_id`, `account_id`, `posting_period_id`, `transaction_currency`, `is_closing_entry`), debit and credit turnover in all three currencies, and the cumulative closing balance of the lines with that `is_closing_entry` value up to the period's end; an account's balance is the sum of its two rows. It is written when a period's `general` area is locked; unlocking deletes that period's rows. A period with no movement has no rows; its balance is the closing balance of the latest earlier row. Balances of unlocked periods are computed from lines. It is never written on the posting path (ADR-0002).
19. No partitioning in Phase 1 (ADR-0006 rule 23).

## Context

DS-06 is needed by step 1 (ledger) and by every module that posts. Constraints:

- One journal-line table with every analytical dimension and amounts in several currencies; subledgers and inventory value are views; material and accounting documents written in the same transaction, zero or one accounting document per material document ([05](../spec/05-accounting-inventory-core.md)).
- Every entry balances per transaction, company and group currency; rounding to a rounding line (05, 07, ADR-0006). Only posted documents are immutable; reversal method (storno or swapped sides) is a localization choice that changes Vietnamese trial-balance turnover (ADR-0009 rule 20).
- Closing-entry marker; triggers protecting posted rows and blocking postings into locked periods (backlog DS-06, ADR-0002). Obligations from ADR-0006 rule 20, ADR-0007 rule 10, ADR-0008 rule 12 and ADR-0010 rules 10 and 12.
- SAP practice (D5): ACDOCA as one table with signed amounts per currency type, a debit/credit indicator (DRCRK) and the transaction key (KTOSL) on each line, and a negative-posting indicator (XNEGP) in the entry view ([SAP PRESS: universal journal](https://blog.sap-press.com/what-is-saps-universal-journal)).
- ADR-0005: among correct options, the one easiest for AI agents wins.

## Options considered

| Option | For | Against |
| --- | --- | --- |
| Signed amounts, `side` and `is_storno` (chosen) | Balances are sums; both reversal methods exact; storno explicit, as in SAP | Three fields to keep consistent; checked by trigger |
| Storno inferred from sign versus side | One field fewer | Ambiguous for adjustment lines with mixed signs |
| Separate debit and credit columns | Familiar layout | Storno needs negative values anyway; balances need two sums |
| Balance check per line insert | Simple trigger | Re-sums the entry for every line: quadratic on large entries |
| Quantity on journal lines (as ACDOCA) | Reports without a join | Duplicates the material document; two places for one quantity |
| Period balance cache updated on every posting | Fast balances at any time | Hot rows on every posting; contention |

## Constraints that come with the decision

- DS-08: transaction keys, including the rounding key.
- DS-09: material documents; value-only entries; costing order within a day; catch weight. Bins: [ADR-0023](0023-warehouse-management.md).
- DS-15: row-level security on journal tables.
- DS-16: invariants of rule 15.
- DS-18: triggers and constraints in migrations; CI tests that `UPDATE`, `DELETE` and `TRUNCATE` fail.
- DS-20: cost center, project and employee tables.
- DS-23: tax codes on tax lines and possibly base lines.
- DS-25: open items. DS-26: turnover by side and closing entries. DS-33: semantic views. DS-37: restores with triggers disabled.

## Revisit when

- Reports on the large dataset are measurably slow (ADR-0002, ADR-0006 rule 23).
- A regime needs a dimension that is not in rule 9.

## Documents updated

- [docs/design/DS-06-universal-journal.sql](../design/DS-06-universal-journal.sql): new, DDL draft.
- [docs/spec/05-accounting-inventory-core.md](../spec/05-accounting-inventory-core.md): the final dimension list points here.
- [docs/adr/0004-naming-conventions.md](0004-naming-conventions.md): note on currency code columns.
- [docs/spec/00-reading-guide.md](../spec/00-reading-guide.md): glossary rows for side, storno line, general journal, balance transfer, database transaction number, account period balance.
- [docs/design/backlog.md](../design/backlog.md): DS-06 row links here.
- [docs/adr/README.md](README.md): index row.
- [docs/open-questions.md](../open-questions.md): manual postings to control accounts.
- [docs/runbook/step-log.md](../runbook/step-log.md): entry.
