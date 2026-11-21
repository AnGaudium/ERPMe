Module: ledger    Chunk: 3 of 3    Source ADRs: ADR-0049, ADR-0050, ADR-0053, ADR-0060, ADR-0067, ADR-0068, ADR-0069, ADR-0072, ADR-0074, ADR-0079
Build step(s): 0, 1, 2, 4, 5, 8    Generated from index: 30d5706    Compiled by: Claude Fable 5.2, 2026-11-21

# Compiled spec: `ledger`, chunk 3

## Purpose

`ledger` owns account balances and posting (ADR-0022.R2) and sits in layer 3, beside `master_data`. This chunk states the
ledger's part of statutory reporting (the balance carry-forward job and the hand-over mechanisms), the transaction keys
`other_tax` and the keys with regime alternatives, the company setup phase, the business unit on journal lines, the
journal entry note and the absence of parallel ledgers. It also lists the invariants and edge cases whose catalog source is no
rule stated in chunks 1 and 2. Statutory report definitions and books belong to `reporting`, the analysis catalog to `query`;
their units are traced `ref:` and not restated.

## Entities and tables

DDL: `docs/design/DS-06-universal-journal.sql`. The rules of this chunk define no table. They add to, or constrain, tables whose rows stand in chunks 1 and 2:

- `journal_entry` (chunk 1): `business_unit_trace_id` (R431) and `note` (R439); `close_task_id` marks carry-forward entries (R402). Erasure of a data subject blanks `note` (ADR-0079.R6).
- `journal_line` (chunk 1): `business_unit_id` and `business_unit_source` (R420). It has no `site_id` (ADR-0068.R5) and no ledger column (R440). `evidence_method` records how a settlement was paid, in any regime (ADR-0053.R11). Erasure blanks `description` (ADR-0079.R6).
- `derivation_trace` (chunk 2): the rows with `rule_code` `business_unit_derivation` (R429, R430).
- `account_period_balance` (chunk 1): its key holds no ledger (R440).

Reads: `company` (`first_operating_posting_at`, R416), `business_unit`, `cost_center`, `project`, `item`, `site`, `warehouse`, `document`, `close_task`, `posting_period`, `fiscal_year`, `production_order_period_cost`.

## Commands and queries

| Name | Actor and authorization | Input | Effect | Events | Error codes |
| --- | --- | --- | --- | --- | --- |
| `RunBalanceCarryForward` (job) | A close task (ADR-0049.R23) runs it; ADR-0049.R22 states no area; the catalog level of the verb `Run` is `post`, and the document it posts falls under the document type `balance_transfer` | The fiscal year and the accounts, which are task parameters in the regime's checklist | Posts a `balance_transfer` dated the first day of the new year, with the task's `close_task_id` on the journal entry (R402, R403) | None stated | None stated |

Not commands, declared by `ledger`: the pure function `ledger.contract.derive_business_unit` (R426) and the required hook
`business_unit_defaults` (R425).

Codes raised by the rules of this chunk: `business_unit_invalid` (R422) and `business_unit_missing` (R433) reject a posting;
`business_unit_default_unset` is a check result of `UpdateCompanySetting` (R435).

Authorization area owned by `ledger` that no rule of the chunks names: the document type `closing_entry` under `finance` (catalog `authorization-areas.csv`; closing entries, ADR-0012.R18).

## Rules

### Statutory reporting hand-overs

R401. The operational accounts that a regime maps to GR/IR clearing and to `purchase_cost_clearing` take their statement format from DS-26 (ADR-0049.R6, ADR-0049.R7) and their placement from DS-19's definitions, which use account terms with `closing_debit` and `by=account` (under other receivables) and `closing_credit` (under other payables). The account numbers and the lines are flagged content of the localization package.
Source: ADR-0049.R22

R402. `RunBalanceCarryForward` is a generic job of `ledger`, run by a close task (ADR-0049.R23). It moves an account's balance at the previous fiscal year's last day to another account by a `balance_transfer` dated the first day of the new year, with the task's `close_task_id` on the journal entry. The accounts are task parameters in the regime's checklist; the TT99 checklist uses the job at the new year for its retained-earnings accounts, whose numbers are flagged content of the localization package.
Source: ADR-0049.R22

R403. `RunBalanceCarryForward` is idempotent. Each run transfers the year-end balance minus what earlier runs for the same fiscal year already moved, found by the `close_task_id` of their entries. A reversal of such an entry carries negated amounts (ADR-0014.R8) and is netted out of that sum, so a reversed transfer counts as not moved. A second run with nothing new posts nothing; after a special-period adjustment a run moves only the difference.
Source: ADR-0049.R22

R404. The timing of the carry-forward, and whether a regime wants a special-period adjustment carried this way, are flagged.
Source: ADR-0049.R22

R405. A statement presents advances by open-item kind with `kind=` and `by=partner_kind`, and short-term apart from long-term with `term=` (ADR-0049.R7).
Source: ADR-0049.R22

R406. Materials held for others (ADR-0037.R8) are a book over `stock` with `filters: {owner: non_owned}`, showing quantities and no values (ADR-0030.R8).
Source: ADR-0049.R22

R407. The product cost sheet (ADR-0035.R16) is `l10n_vn`'s book definition over `production_order_period_cost`, with `field_classes: [cost]`; the core provides the row source (ADR-0053.R13).
Source: ADR-0049.R22

R408. The stock valuation report is a book over `stock` as of a date, by item and warehouse. Its total ties to the inventory accounts (INV-402; spec 12).
Source: ADR-0049.R22

### Transaction keys: `other_tax` and regime alternatives

R409. A tax without a transaction key of its own posts through `other_tax`, determined by tax code, with required system account `tax_payable_other`. `transaction-keys.csv` holds no `environmental_protection_tax`.
Source: ADR-0053.R5

R410. The TT99 rows for `other_tax` in the package's `account_determination.csv` are `unverified`, flagged content of the localization package: one row for `other_tax` with tax code `import_environmental_protection` and one generic `other_tax` row, so every tax code resolves (ADR-0015.R13). The operational accounts they name are package values. The package's environmental protection tax code posts through `other_tax` with its account chosen by tax code; the core has no key that names one country's tax.
Source: ADR-0053.R5

R411. The keys `special_consumption_tax`, `import_export_duty` and `trade_remedy_duty` are not renamed by this rule; neutral names for them are an open question (ADR-0053.R17).
Source: ADR-0053.R5

R412. These keys hold alternatives in `required_system_accounts`, separated by `;`, with `has_regime_alternatives` true, in the format of `fx_gain_unrealized`:
   - `cash_surplus`: `asset_surplus_pending;non_operating_income`.
   - `cash_shortage`: `asset_shortage_pending;non_operating_expense`.
   - `bank_charge`: `administrative_expense;financial_expense`; a company may pick the other alternative (ADR-0048.R20).
   - `production_abnormal_cost`: `cost_of_goods_sold;expense_other`.
   - `production_unabsorbed_overhead`: `cost_of_goods_sold;expense_other`.
   - The TT99 determination row of each of these keys picks one alternative; the operational accounts are flagged content of the localization package.
   Source: ADR-0053.R6

R413. `has_regime_alternatives` also marks keys that do not share a system account's code. It says that the list holds alternatives a regime or company chooses between, not one required account (ADR-0027.R11).
Source: ADR-0053.R6

R414. The meanings of `production_abnormal_cost` and `production_unabsorbed_overhead` cite IAS 2: paragraph 16 for abnormal amounts and paragraph 13 for unallocated fixed overhead. Both are recognized as an expense of the period; which expense is the regime's choice. The national standard behind the TT99 choice stays `l10n_vn`'s rationale, as package content.
Source: ADR-0053.R6

R415. A determination row of a key with alternatives must map under one of the listed accounts, so the `INV-16` cross-check and its lab check hold for these keys. `expense_other` stays a stated unreached account of TT99.
Source: ADR-0053.R6

### Company setup phase

R416. A company is in its setup phase while `company.first_operating_posting_at` is null. Opening documents of a migration do not end the phase; the first ordinary posting does. The phase never reopens.
Source: ADR-0067.R7

R417. The ledger sets `company.first_operating_posting_at` once, in the transaction of the first journal entry of the company whose posting period lies outside the migration fiscal year (ADR-0044.R2). It uses `UPDATE … WHERE first_operating_posting_at IS NULL`, which locks the company row, in the pattern of `account.has_posting` (ADR-0010.R12).
Source: ADR-0067.R7

R418. A setup-path command reads the company row `FOR SHARE` through `registry`'s contract before it writes, so it and the first operating posting cannot overlap.
Source: ADR-0067.R7

R419. The upgrade that adds `first_operating_posting_at` sets it, for an existing company, from the company's first journal entry whose posting period lies outside the migration fiscal year.
Source: ADR-0067.R7

### Business unit on journal lines

R420. `journal_line` has the nullable columns `business_unit_id`, a key to `business_unit` within the company, and `business_unit_source`, the step that set the unit: `line`, `item`, `cost_center`, `project`, `document`, `site`, `company_default`, `reversal` or `closing`. `business_unit_source` is null exactly when the unit is null. The index is `(company_id, business_unit_id, posting_period_id)` where the unit is set.
Source: ADR-0069.R4

R421. Only profit-and-loss (P&L) lines carry a unit in Phase 1. A P&L line is a line whose system account has `account_type` `income` or `expense` (ADR-0010.R3), read from the line's `system_account_id`. Balance-sheet lines never carry a unit, `income_summary` and retained earnings included.
Source: ADR-0069.R5

R422. A unit stated directly on a balance-sheet journal line (a general journal line) is refused with `business_unit_invalid`.
Source: ADR-0069.R5

R423. These carry no unit:
   - Material document lines. The P&L journal line that posts a movement, cost of goods sold for example, carries the unit and refers to its material line.
   - Open items. An open item reaches the units of its origin document's P&L lines through that document.
   - Tax lines (ADR-0041), which are balance sheet.
   Source: ADR-0069.R6

R424. `ledger` derives the unit at posting, inside the posting transaction, for every P&L line of the entry. The first match wins, in this order:
   1. the explicit unit of the document line;
   2. the unit of the line's item (its product); for a line whose cost object is a production order (issues, confirmations, receipts, settlement and variance lines) the item is the order's output product, so every P&L line of one order carries one unit and the production cost accounts net to zero per unit;
   3. the unit of the line's cost center;
   4. the unit of the line's project;
   5. the document header's unit;
   6. the unit of the site of the line's warehouse (a transit or goods-sent warehouse through its valuation warehouse, ADR-0068);
   7. `ledger.business_unit.default`, or none.
   Source: ADR-0069.R9

R425. The posting module passes the explicit line unit and the header unit in its posting request. The other candidates come from master data through the hook `business_unit_defaults`, which `ledger` declares, `master_data` registers and `app` wires, because same-layer modules may not import each other (ADR-0022.R2). The hook is required.
Source: ADR-0069.R9

R426. The function `ledger.contract.derive_business_unit` is pure. A conflict between candidates, such as an item unit that differs from the cost center's, is not an error: the first match wins and the trace keeps the losing values.
Source: ADR-0069.R9

R427. The derivation runs after account determination (ADR-0015) has chosen the account, because it needs the account's system account type. It never feeds account determination: a business unit is not a determinant (ADR-0015.R3), so one set of determination rows serves every unit.
Source: ADR-0069.R10

R428. Reversal and closing lines copy their unit instead of deriving it. A reversal document repeats the original's lines (ADR-0014.R8) with their units, source `reversal`. Closing entries close each P&L account per business unit, and each closing line takes the unit of the balance it closes, source `closing` (ADR-0012.R18). Every other document derives anew, corrections included (ADR-0009.R23).
Source: ADR-0069.R11

R429. The derivation writes one `derivation_trace` per journal entry with at least one P&L line, in a company that has at least one `business_unit` row. A company without units skips the derivation entirely: no trace, every unit null.
Source: ADR-0069.R12

R430. The trace has `rule_code` `business_unit_derivation` and `rule_version` `1`. `inputs` holds the header unit, the setting row in force and the master rows read. `steps` holds, per line number, the candidates of R424 in order, each a unit or null. `result` holds, per line number, the unit and the source.
Source: ADR-0069.R12

R431. The nullable `journal_entry.business_unit_trace_id` names the trace; `journal_line.derivation_trace_id` stays costing's (ADR-0027.R3). The trace is part of the posting plan (ADR-0008.R12), so a simulation shows each line's unit and why. The derivation is a trace writer under ADR-0027.R4, by the author's scope decision of 2026-11-17.
Source: ADR-0069.R12

R432. The business unit settings (ADR-0063.R1; `settings.csv`) have area `ledger`, scope `company`, leaf `company_setting`, effect `immediate` and outdates `none`. `ledger.business_unit.default` is the `code` of an active unit of the company, with core default `unset` and direction `neutral`; its value type `code` is one code whose table the bounds name (`business_unit`), checked by the command. `ledger.business_unit.required_on_profit_and_loss` is a boolean with default `false` and direction `true_tighter`.
Source: ADR-0069.R13

R433. While `ledger.business_unit.required_on_profit_and_loss` is true, the posting logic rejects a P&L line that has no unit after the derivation, with `business_unit_missing`, in the simulation and in the execution. `details` names the line, its system account, the candidates tried and the commands that fill one. The check is posting logic, not the trigger, like the control-account setting (ADR-0014.R10).
Source: ADR-0069.R14

R434. Reversal and closing lines (R428) are exempt from the requirement, so documents posted before the setting can still be reversed and closed. The requirement applies only while the company has at least one active business unit; a company without units skips it, as it skips the derivation (R429).
Source: ADR-0069.R14

R435. `UpdateCompanySetting` returns the check result `business_unit_default_unset` when the requirement is true and no default is set, because realized exchange differences, rounding lines and bank charges without a cost center find a unit only through the company default.
Source: ADR-0069.R14

R436. The derivation reads master data and settings as they stand in the posting transaction. A later change to a product, cost center, project, site, header or company default affects only later postings, as a changed determination row does (ADR-0015.R12). Nothing re-derives posted lines, which never change (ADR-0014.R13).
Source: ADR-0069.R15

R437. Moving posted amounts to another unit takes a general journal on the same account, with explicit units on both lines and the approval of ADR-0048.R15.
Source: ADR-0069.R15

R438. The business unit tree is not frozen. It is read when a query runs, so re-parenting a unit regroups history.
Source: ADR-0069.R15

### Journal structure

R439. `journal_entry.note` (at most 4,000 characters) holds the note of the document, copied at posting, so reports read one place. The entry stays append-only. `payment`, `bank_statement` and the production headers keep no note.
Source: ADR-0074.R17

R440. There are no parallel ledgers. Phase 1 serves companies that keep their books under one accounting framework; a second ledger is out of scope by the author's decision. The journal has no ledger column, no ledger in the keys of `journal_line` or `account_period_balance`, and no seam for one. A group that reports under another framework uses the group currency of ADR-0011 and the mapping of its reporting package.
Source: ADR-0074.R18

## Invariants

Statements are those of `invariants.csv`. Each row stands once in the module, in the chunk that states the rule its catalog source names; this chunk holds the rows whose source is a rule of this chunk, a rule of another module or spec 12. "Protects" names a rule of this chunk or the source ID of a rule stated elsewhere.

| Invariant | Name | Check point | Statement | Protects |
| --- | --- | --- | --- | --- |
| `INV-02` | `trial_balance_zero` | day | Per company and posting period, company amounts of all lines sum to zero, and group amounts are all null or sum to zero. | spec 12 |
| `INV-03` | `amount_at_minor_unit` | day | Every stored amount has no more decimal places than its currency's minor unit. | ADR-0006.R14, ADR-0014.R15 |
| `INV-07` | `numbers_without_gaps` | day | Per `numbering_series`, the counters of all documents that hold a number, in any state, are exactly 1 to `next_value` minus 1, each once. Flagged: numbering of non-posting documents at approval (ADR-0009.R8). | ADR-0009.R14, ADR-0009.R15, ADR-0009.R18, ADR-0027.R16; spec 12 |
| `INV-09` | `reversal_nets_to_zero` | day | An original and its reversal net to zero per account, dimension set and currency. Flagged: storno or swapped sides (ADR-0009.R20). | ADR-0009.R20; spec 12 |
| `INV-10` | `version_content_matches_rows` | day | The current document version's content and `version_hash` equal those computed from the typed rows; versions with `erased_at` set are skipped. | ADR-0009.R9, ADR-0079.R6 |
| `INV-14` | `postings_respect_period_state` | command | A posting into a locked period, or into a soft-locked period without the capability, is rejected and writes nothing; one into an open period is not rejected for its period. | ADR-0012 |
| `INV-37` | `gr_ir_per_order_line` | day | Every journal line on a `gr_ir` account whose document line refers to a purchase order line has `purchase_order_line_id`; per purchase order line whose received quantity equals its invoiced quantity, net of returns and credit notes, the GR/IR balance in transaction currency is zero. Flagged: invoice-first valuation (ADR-0030.R4). | ADR-0030.R3, ADR-0030.R5, ADR-0014.R10 |
| `INV-92` | `gr_ir_equals_rounded_positions` | day | Per purchase order line, the GR/IR balance in the order's currency equals round(V(I)) - round(V(R)) at the line's position layers, V being the exact value of positions up to a quantity and rounding to the currency's minor unit; it is zero when received net equals invoiced net. | ADR-0047.R13, ADR-0030.R5 |
| `INV-402` | `book_balances_tie_to_accounts` | run | Each book group's opening and closing balance equals the balance of its accounts (by partner or item where grouped) on those dates, opening plus rows equals closing, and the stock valuation book's total equals the inventory accounts. Area `reporting`. | R408, ADR-0049.R10 |
| `INV-820` | `business_unit_profit_and_loss_only` | day | Every journal line with a business unit has a system account of type income or expense; `business_unit_source` is null exactly when `business_unit_id` is null. | R420, R421 |
| `INV-821` | `business_unit_derivation_reproducible` | day | For every journal entry with a `business_unit_trace_id`, each line's business unit and source equal the trace's result, which is the first non-null candidate of the line's steps, or the copied unit for reversal and closing lines. | R424, R428, R430 |
| `INV-822` | `business_unit_required` | day | No profit-and-loss line other than a reversal or closing line was posted without a business unit while `ledger.business_unit.required_on_profit_and_loss` was true on its posting. | R433, R434 |
| `INV-863` | `payer_is_open_item_partner` | day | The open item of a posted sales invoice, credit note or debit note belongs to its payer, else its bill-to party, else its sold-to partner; the open item of a purchase document to its invoicing party, else its ordered-from partner. | ADR-0074.R4, ADR-0026.R1.N2, ADR-0014.R10.N2 |

Named by a rule of this chunk, with its row in chunk 1: `INV-16` (R415). Invariants of area `reporting` that the `ref:` units of this chunk name, stated by their own modules: INV-401, INV-410, INV-412.

## Edge cases

| Edge case | Name | Case | Outcome | Protects |
| --- | --- | --- | --- | --- |
| `EC-01` | `backdated_document` | A posting whose `posting_date` is earlier than its `sim_date` and than other posted documents, in an open period. | `must_succeed` | spec 12 |
| `EC-02` | `posting_in_soft_locked_period` | A posting into a soft-locked period, by an actor with the capability and by one without. | `must_succeed` with the capability; `must_reject:posting_period_not_open` without | spec 12; ADR-0012 |
| `EC-06` | `reversal_of_internal_document` | A posted internal document reversed in an open period. | `must_succeed` | ADR-0009.R19 |
| `EC-270` | `business_unit_conflict_first_match` | A delivery's cost-of-goods line for a product of unit A, from a site of unit B, on a sales order whose header names C: the line gets A with source `item`, and the entry's trace lists B and C as losing candidates. | `must_succeed` | R424, R426 |
| `EC-271` | `business_unit_required_missing` | With the requirement on and no default, a payment whose settlement posts a realized exchange difference; then the same after the company default is set, which posts with source `company_default`. | `must_reject:business_unit_missing` without a default; `must_succeed` with one | R433 |
| `EC-272` | `business_unit_default_not_retroactive` | A product's unit changes from A to B; the reversal of an invoice posted earlier keeps A (source `reversal`), a new invoice gets B, and net revenue by business unit shows both. | `must_succeed` | R428, R436 |
| `EC-273` | `business_unit_expense_line` | A purchase invoice expense line with a cost center of unit A gets A with source `cost_center`; a second line with an explicit unit D gets D with source `line`. | `must_succeed` | R424; ADR-0069.R8 |

## Settings

| Key | Value type | Scopes | Core default | Used by |
| --- | --- | --- | --- | --- |
| `ledger.business_unit.default` | `code` (bounds: `business_unit`) | `company` | `unset` | R424, R432, R435 |
| `ledger.business_unit.required_on_profit_and_loss` | boolean | `company` | `false` | R432, R433 |

## UI annotations

None: no unit of this chunk carries an annotation of ADR-0077.

## Conflicts

None

## Proposed (not law)

None

## Trace

| Source | Where |
| --- | --- |
| ADR-0049.R6 | ref: ADR-0049.R6 |
| ADR-0049.R7 | ref: ADR-0049.R7 |
| ADR-0049.R9 | ref: ADR-0049.R9 |
| ADR-0049.R10 | ref: ADR-0049.R10 |
| ADR-0049.R12 | ref: ADR-0049.R12 |
| ADR-0049.R14 | ref: ADR-0049.R14 |
| ADR-0049.R15 | ref: ADR-0049.R15 |
| ADR-0049.R16 | ref: ADR-0049.R16 |
| ADR-0049.R16.N1 | ref: ADR-0049.R16 |
| ADR-0049.R19 | ref: ADR-0049.R19 |
| ADR-0049.R22 | R401-R408 |
| ADR-0049.R33 | ref: ADR-0049.R33 |
| ADR-0050.R53 | ref: ADR-0050.R53 |
| ADR-0050.R53.N1 | ref: ADR-0050.R53 |
| ADR-0050.R53.N2 | ref: ADR-0050.R53 |
| ADR-0053.R5 | R409-R411 |
| ADR-0053.R6 | R412-R415 |
| ADR-0053.R11 | ref: ADR-0053.R11 |
| ADR-0060.R2 | ref: ADR-0060.R2 |
| ADR-0060.R3 | ref: ADR-0060.R3 |
| ADR-0060.R5 | ref: ADR-0060.R5 |
| ADR-0060.R6 | ref: ADR-0060.R6 |
| ADR-0060.R7 | ref: ADR-0060.R7 |
| ADR-0060.R10 | ref: ADR-0060.R10 |
| ADR-0060.R12 | ref: ADR-0060.R12 |
| ADR-0060.R16 | ref: ADR-0060.R16 |
| ADR-0060.R37 | ref: ADR-0060.R37 |
| ADR-0067.R7 | R416-R419 |
| ADR-0068.R5 | ref: ADR-0068.R5 |
| ADR-0069.R4 | R420 |
| ADR-0069.R5 | R421, R422 |
| ADR-0069.R6 | R423 |
| ADR-0069.R8 | ref: ADR-0069.R8 |
| ADR-0069.R8.N1 | ref: ADR-0069.R8 |
| ADR-0069.R9 | R424-R426 |
| ADR-0069.R10 | R427 |
| ADR-0069.R11 | R428 |
| ADR-0069.R12 | R429-R431 |
| ADR-0069.R13 | R432 |
| ADR-0069.R14 | R433-R435 |
| ADR-0069.R15 | R436-R438 |
| ADR-0069.R18 | ref: ADR-0069.R18 |
| ADR-0072.R3 | ref: ADR-0072.R3 |
| ADR-0074.R17 | R439 |
| ADR-0074.R18 | R440 |
| ADR-0079.R6 | ref: ADR-0079.R6 |
