Module: cash    Chunk: 1 of 2    Source ADRs: ADR-0028, ADR-0048
Build step(s): 1, 2, 3, 6    Generated from index: 30d5706    Compiled by: Claude Fable 5.2, 2026-11-21

# `cash` compiled spec, chunk 1: money accounts, payments, bank statements, matching, netting, write-off, currency, advances

## Purpose

`cash` is the layer-4 module of the DS-25 business processes on top of the open-item core of `ledger` (ADR-0026): money accounts, payment documents, bank statements and their matching, discounts, netting, write-offs, currency exchange, money transfers, cash counts and advances. It does not own open items, the journal or tax: it posts through `ledger.contract.write_journal_entry` and never changes the core. This chunk states those rules; provisions, prepaid amortization, reversal, dunning and collections, the payment-method defaults, the bank matching agent and the settings of the bank-charge auto-post are in chunk 2.

## Entities and tables

DDL: `docs/design/DS-05-platform.sql`.

| Table | Meaning | Key | Parent | Owner |
| --- | --- | --- | --- | --- |
| `money_account` | A cash box or bank account of a company, on its own operational account (R4) | `id`; (`company_id`, `code`) unique; `account_id` unique | `company`, `account` | `cash` |
| `payment` | Header of a `cash_receipt`, `cash_payment`, `bank_receipt` or `bank_payment` (R5) | `id`; (`company_id`, `id`) | `document`, `money_account` | `cash` |
| `payment_line` | Line of a payment, of one `line_kind` (R7) | `id`; (`payment_id`, `line_number`) unique | `payment` | `cash` |
| `bank_statement` | An imported statement of one money account (R14) | `id`; (`money_account_id`, `statement_number`) unique | `money_account` | `cash` |
| `bank_statement_line` | A statement line with its match state, proposal and suggestion (R14) | `id`; (`bank_statement_id`, `line_number`) unique | `bank_statement` | `cash` |

The rows of `open_item_collection` and `payment_method_money_account` are in chunk 2.

Defined by rule, without DDL: `money_account_balance` (R28). `bank_matching_rule` (R20) has no DDL either; chunk 2 lists it.

Reads: `open_item`, `journal_line`, `account`, `system_account`, `transaction_key` (`ledger`); `partner`, `partner_bank_account`, `company`, `branch`, `cost_center`, `project`, `business_unit`, `payment_method` (`master_data`); `document`, `attachment`, `agent_run`, `user_account`, `policy_decision`, `regime_setting`.

## Commands and queries

Authorization: the document types are leaves of `authorization-areas.csv` owned by `cash`: `cash_receipt`, `cash_payment`, `bank_receipt`, `bank_payment`, `cash_count`, `cash_count_adjustment`, `currency_exchange`, `money_transfer` and `advance_settlement` under `banking`; `partner_netting` and `write_off` under `finance`. The function leaf `bank_statement` under `banking` covers statement import, matching and matching rules, and the master data leaf `money_account` under `banking` covers money accounts. The sources bind no verb level to the commands below.

| Name | Actor and authorization | Input | Effect | Events | Error codes |
| --- | --- | --- | --- | --- | --- |
| `GetAllocationProposal` | deterministic query; area not stated | partner, amount, currency, side, date | Proposes an allocation; never applied by itself (R13) | none | none stated |
| `ImportBankStatement` | verb Import; leaf `bank_statement`; level not stated | an attached file | Runs a `BankStatementReader`, writes `bank_statement` and `bank_statement_line`, runs the cascade (R15, R17) | not stated | `bank_statement_unbalanced`; duplicates by ADR-0030.R10 |
| `GetBankReconciliation` | query; area not stated | money account, date | Compares the statement's closing balance with the book balance; lists unmatched lines and unmatched book postings (R16) | none | none stated |
| `IgnoreBankLine` | `human_only`; verb Ignore; area not stated | line, reason | Sets `match_state` `ignored` with `ignore_reason` (R16) | not stated | none stated |
| `MatchBankLine` | leaf `bank_statement`; level not stated | line, document | Links a line to a posted document, or makes a draft the proposal (R21) | not stated | none stated |
| `UnmatchBankLine` | leaf `bank_statement`; level not stated | line | Unlinks the line; a proposed line returns to `unmatched` (R21) | not stated | `bank_statement_line_posted` |

Named by this chunk's rules: `RecordBankLineSuggestion` with its event `BankLineSuggestionRecorded` (ADR-0051.R17), whose row is in chunk 2, and `Reverse<Type>`, whose reversal rule is ADR-0048.R16 in chunk 2.

Contract functions, hooks and functions that are not registered commands: `ledger.contract.write_journal_entry` and `tax.contract.record_payment_evidence` (called, R1); the pure function `match_bank_line`, tunable as `cash.match_bank_line` (R17, R23); the lock hook that `cash` registers for `money_account_balance` (R28); the auto-post gateway checkers (R22).

Error codes of the documents and master data, bound to no named command: `overdraft_not_allowed` (R4), `money_account_kind_mismatch` (R5), `duplicate_external_document` (R7), `money_account_line_not_allowed` (R7), `netting_agreement_missing` (R24), `write_off_above_limit` (R25), `money_account_negative` (R28), `money_transfer_currency_mismatch` (R30). Check results: `bank_statement_gap` (R15), `settlement_rate_unusual` and `settlement_rate_unchecked` (R26). Reasons of an unmatched line: `ambiguous_reference`, `shared_account` (R18, R19). Draft flag: `counterparty_unverified` (R18).

## Rules

### Module and document types

R1. `cash` (layer 4, ADR-0022.R2) owns the tables and document types of ADR-0048. It calls `ledger.contract.write_journal_entry` for every posting, `tax.contract.record_payment_evidence` for taxed lines without an open item, and reads open items through `ledger` queries. It imports no other layer-4 module: what it needs from `crm` and `purchasing` reaches it through their events (ADR-0048.R14, ADR-0048.R17).
Source: ADR-0048.R1

R2. Document types of `cash` (ADR-0009.R2, ADR-0009.R3):
- `cash_receipt`, `cash_payment`, `bank_receipt`, `bank_payment`: posting; reversible while unreferenced (ADR-0048.R16). They are `is_printable` and carry `print_language` (ADR-0049.R10, ADR-0049.R27).
- `money_transfer`: posting; reversible while unreferenced (ADR-0048.R16); authorization leaf `money_transfer` under `banking`. It moves money between two money accounts of the company in one currency and has no partner, open item or tax (R30).
- `currency_exchange`: posting; reversible, internal (R29).
- `partner_netting`: posting; reversible, internal (R24).
- `write_off`: posting; reversible, internal (R25).
- `advance_settlement`: posting; reversible while unreferenced (R31).
- `cash_count`: non-posting (R10).
- `cash_count_adjustment`: posting; reversible, internal (R10).
- `provision_entry`, `prepaid_amortization`: posting, by system jobs; reversible, internal (ADR-0048.R14).
- Approval hold is allowed on all of them. None is e-invoice capable.
- `general_journal` stays `ledger`'s (ADR-0014.R3); ADR-0048.R15 adds its approval and control-account rules.
- The type names are neutral (ADR-0053.R14): spec 08's cash receipt is `cash_receipt`, its cash payment is `cash_payment`, and its bank credit and debit advices are `bank_receipt` and `bank_payment`. The cash book is a report (DS-26): a book definition over journal lines grouped by account.
Source: ADR-0048.R1, ADR-0048.R1.N1, ADR-0048.R1.N2, ADR-0048.R1.N3

R3. Core and overlay: everything of ADR-0048 that belongs to one country (accounts, provision bands, the netting agreement, the non-cash payment threshold, the invoice key fields) is a regime setting or a row of the localization package (`l10n_vn`, ADR-0016), never core behavior. The core only knows that such settings exist. Each cash box and bank account is a `money_account` on its own operational account, so balances, book rates and statements are per account. The same statement input, in any order, always gives the same matching proposal.
Source: ADR-0048.D0

### Money accounts

R4. `money_account` is company data, changed by `master_data_change` and change-tracked; agents propose changes (ADR-0029.R5).
- Fields: `code`, `name`, `kind` (`cash`, `bank`), `currency`, `account_id`, `is_active`. Banks also carry `bank_name`, `bank_code`, `bank_account_number`, `bank_branch` and `is_overdraft_allowed`, which Phase 1 allows only on bank accounts in company currency (`overdraft_not_allowed`).
- The operational account has system account `cash_on_hand` (`cash`) or `cash_in_bank` (`bank`) in its hierarchy, and its currency equals the money account's (ADR-0010.R10). Each operational account serves at most one money account.
- The money account is the "bank account" of the natural key of statement lines (ADR-0030.R10).
Source: ADR-0048.R2

### Payment documents

R5. The header of a payment document (`cash_receipt`, `cash_payment`, `bank_receipt`, `bank_payment`; table `payment`) holds:
- `money_account_id`, whose kind matches the type (`money_account_kind_mismatch`) and whose currency is the document's (`transaction_currency`);
- document and posting dates, and for bank documents the `value_date`;
- the partner (optional when all lines are `account` lines), with the partner snapshot `partner_name`, `partner_tax_id`, `partner_address` (ADR-0028.R16);
- for a foreign currency, an optional settlement rate `settlement_exchange_rate` (rate type `settlement`, ADR-0011.R12); without one the document converts at the transaction lookup rate (applied rate origin `lookup`, ADR-0011.R11);
- a `reference`;
- for a `bank_payment` to a partner, `partner_bank_account_id` in the content (R6), an active account of that partner;
- for cash documents, the payer's or payee's name as a snapshot (`counterparty_name`);
- `payment_method_id`, copied from the invoice the payment is drafted from. The default money account comes from `payment_method_money_account`, for the document's branch and currency. The method only suggests `evidence_method`; ADR-0048.R18 is unchanged;
- `bank_statement_line_id`, the line the document was drafted from (interim in the DDL), and `print_language`.
Source: ADR-0048.R3, ADR-0048.R3.N1, ADR-0048.R3.N2

R6. Payment-type documents (DS-25) carry the beneficiary's `partner_bank_account_id` in their content.
Source: ADR-0028.R15

R7. A `payment_line` has one `line_kind`:
- `settle`: an open item and the amount in the item's currency (`open_item_id`, `open_item_transaction_amount`). In the document's currency it settles directly. In another currency it is an exchange inside the document: the line carries the item-currency amount and the bank's rate (`exchange_rate`), and the document adds one line per currency on key `currency_exchange_clearing` (R29; ADR-0026.R4). An optional discount follows R14 (`discount_transaction_amount`). The flag `paid_by_third_party`, column `is_paid_by_third_party` (ADR-0004.R13), marks a payment made by someone other than the item's partner.
- `advance`: creates an `advance` item for the partner, on the account that determination gives (the trade account, or `receivable_employee_advance` for employees).
- `on_account`: creates a `payment_on_account` item. This is also how an overpayment is recorded (ADR-0026.R8).
- `account`: posts to an account the line names (`account_id`), with optional cost center, project and taxes, and the explicit `business_unit_id` (ADR-0069.R8). A taxed line needs the supplier: a partner (`supplier_partner_id`), or a tax ID and name kept as a one-time snapshot (`supplier_tax_id`, `supplier_name`). It also needs the fields of the regime's supplier-invoice key (`supplier_invoice_key`; the fields are package content), the invoice date (`supplier_invoice_date`) and the stated tax (ADR-0041.R7, ADR-0041.R10). The supplier-invoice key of ADR-0030.R10 applies to these lines and to purchase invoices together, so one invoice cannot be deducted twice (`duplicate_external_document`). A line that names a money account's operational account is rejected with `money_account_line_not_allowed` (R30).
- `bank_charge`: posts to key `bank_charge`.
Source: ADR-0048.R3, ADR-0048.R9.N4

R8. Evidence (ADR-0048.R18): the lines that settle or create an item (`settle`, `advance`, `on_account`) carry `evidence_method`: `cash` for cash documents, `bank_transfer` for bank documents, `card` when the line says so, `third_party` when `paid_by_third_party` is set (only on `settle` lines). A taxed `account` line has no open item; in the posting transaction the document calls `tax.contract.record_payment_evidence` for it with the same method (ADR-0041.R15). An invoice in `issuing` has no open item yet (ADR-0028.R9): a payment that arrives then is an advance or a payment on account, matched later.
Source: ADR-0048.R3

R9. Policy input of a payment document: the amount in company currency; `is_direct_expense` (an `account` line to an expense); `is_bank_account_recent` (the beneficiary account was created or changed within `cash.bank_account_cooling_days`, company setting, default 7); `is_rate_unusual` (the rate check of R26, false when the document carries no settlement rate). The conditions join ADR-0043.R3.
Source: ADR-0048.R3, ADR-0048.R3.N1

### Cash counts

R10. Cash counts:
- `cash_count` (non-posting) records a cash money account, the counted amount (optionally by denomination) and the book balance at the time. It is kept as evidence even when nothing differs.
- When a count is approved with a difference, it creates and posts a `cash_count_adjustment`: a surplus to key `cash_surplus`, a shortage to key `cash_shortage`. The accounts behind the keys are flagged package content of the localization package, `unverified`; where the regime maps them to an account pending resolution, that account is resolved later by a general journal or an employee receivable.
- A foreign-currency difference is valued at the money account's book rate (R27).
- A count written by an agent run leaves its adjustment as a draft for a person (ADR-0043.R9, floor 5).
Source: ADR-0048.R4

### Policy and agents

R11. Policy and agents:
- Agents may draft payments and propose allocations. An agent's posting gets `human_post` (ADR-0043.R9, floor 4). A payment is posted by `system` only through the auto-post of R22, which is disabled by default. The system postings of R10 and ADR-0048.R14 are adjustments and close jobs, not payments.
- Bank account changes keep ADR-0029.R4: a proposal approved by a human who wrote no version of it.
- No money moves from NativeFlows in Phase 1. Payment documents record payments made through the bank or the cash box. Payment files and bank connections that send money are add-ons after the core, like the e-invoice provider (open question).
Source: ADR-0048.R5

### Allocation and early-payment discounts

R12. Allocation is explicit (ADR-0026.R3): each `settle` line names its item and amount. A proposal is never applied by itself: a person accepts it, an agent drafts with it, or an enabled matching rule uses it (R17 to R22).
Source: ADR-0048.R6

R13. `GetAllocationProposal` (partner, amount, currency, side, date) is a deterministic query. It skips blocked and disputed items (ADR-0048.R17). It returns an item of exactly that amount (the oldest due among equals); otherwise items oldest due first, the last one partly settled; and any rest as `on_account`. It lists the partner's open credits and advances separately, for the person to apply.
Source: ADR-0048.R6

R14. Early-payment discounts (ADR-0026.R1, ADR-0026.R8):
- When: a `settle` line takes the item's discount when the payment's document date (a bank line's value date) is on or before the item's `discount_due_date`.
- How much: for an item with discount `p`, a cash amount `c` in the item's currency settles `round(c ÷ (1 − p/100))`, capped at the open amount. The discount is that amount minus `c`, so a partial payment takes a partial discount. In a foreign currency, the discount line is valued at the item's carrying amount for its share (ADR-0026.R6).
- Posting: `payment_discount_given` (customers) or `payment_discount_received` (suppliers), on a line that settles the item with `evidence_method` `none`. Payment discounts are financial income and expense. The absence of a VAT adjustment is `unverified`.
- Naming: the policy input `discount_percent` is a price discount (ADR-0047.R22); the open item's `discount_percent` is a payment discount. Payment policy inputs use `payment_discount_amount`.
Source: ADR-0048.R7

### Bank statements

R15. `bank_statement` holds the money account, `statement_number`, the period (`period_start_date`, `period_end_date`), `transaction_opening_balance` and `transaction_closing_balance` in the money account's currency, `source_attachment_id`, `reader_code`, `has_gap` and, interim in the DDL, `imported_by_user_id`. `bank_statement_line` holds:
- `booking_date` and `value_date`, the signed `transaction_amount` (inflow positive), `bank_reference`, `counterparty_name`, `counterparty_bank_code`, `counterparty_account_number`, `bank_transaction_code` (ADR-0063.R9) and `description`;
- `match_state`: `unmatched`, `proposed`, `matched`, or `ignored` with `ignore_reason`;
- a matched line names its document in `matched_document_id`; a proposed line names its document in `proposed_document_id`, with the cascade's score (`proposal_score`) and `match_basis`: `already_posted`, `reference`, `company_rule`, `account_amount`, `account_subset`, `bank_charge_rule` (ADR-0063.R9), `llm_suggestion` or `manual`. These are the values of the DDL check; ADR-0059.R10 also names the basis `company_rule_account` for the evidence count of account-rule drafts, which the DDL check does not list;
- the suggested tokens of `BankLineSuggestionRecorded`, which carries IDs only: they stay on the line as untrusted fields (ADR-0051.R17).
- Import: `ImportBankStatement` (verb Import) runs a `BankStatementReader` from the localization package (ADR-0016.R17) on an attached file. These fields are the reader's interface (DS-14).
- Checks at import: opening balance plus the lines must equal closing balance, otherwise the import is rejected with `bank_statement_unbalanced`; an opening balance that differs from the previous closing balance sets `has_gap` and returns the check result `bank_statement_gap`.
- Duplicates follow the natural key of ADR-0030.R10. Descriptions are `is_untrusted` (ADR-0029.R10), and so is description text copied into a draft.
- Formats: a generic CSV reader ships in the core test kit for the synthetic dataset (DS-17). Bank formats are package work for step 6 (spec 06).
Source: ADR-0048.R8, ADR-0048.R8.N1

R16. Reconciliation and line handling:
- `GetBankReconciliation` (money account, date) compares the statement's closing balance with the book balance, and lists unmatched lines and unmatched book postings. It counts `proposed` lines as unmatched, so neither the reconciliation nor its close task treats a draft as booked. The close checklist task "bank statements reconciled" (ADR-0012.R13) reads it. `INV-95` holds unchanged.
- Ignoring a line (`IgnoreBankLine`, with a reason; verb Ignore) is `human_only`.
- One line, one document in Phase 1. Several lines to one document, or one line to several, come later (open question).
Source: ADR-0048.R8, ADR-0048.R8.N1

### Matching cascade

R17. The cascade is `match_bank_line`, a pure function, checked by the lab on shuffled inputs. It first puts open items and documents in a canonical order (due date, then ID). An inflow considers only items on the debit side, an outflow only items on the credit side, and only items in the money account's currency. "Within one partner" means the payer of a receivable and the invoicing party of a payable; a payment goes to its payee and that party's bank account (ADR-0074.R4). It applies R18 and R19 in order.
Source: ADR-0048.R9, ADR-0048.R8.N2

R18. Steps 1 and 2 of the cascade:
- Step 1, already posted: an unmatched posted document of this money account in the same direction and amount, dated within 5 days, whose reference is a token of the description or whose partner owns the counterparty's account. The closest date wins, then the earliest, then the lowest ID (score 95). Nothing new is drafted.
- Step 2, reference: items whose reference or partner reference appears as a whole token in the description, all of one partner. Only reference-shaped tokens count: at least four characters with a digit, or the package's pattern for its invoice numbers. An invoice's installments share its reference; a token `<reference>-<installment_number>` names that installment alone.
- Step 2, exact: among the referenced items in due-date order, a prefix that sums exactly to the amount scores 100 and settles those items; otherwise a single referenced item equal to the amount scores 90 and settles that item.
- Step 2, partial: otherwise the referenced items are settled oldest due first, partly if the amount is short, with any excess on account (score 80). The cascade never switches to another item.
- Tokens naming items of several partners make the line unmatched (`ambiguous_reference`).
- A reference in a description is untrusted (ADR-0029.R10), so the score of step 2 depends on whose account paid. The item's partner owns the counterparty's account (also when it shares it): the scores above. No partner owns it, or the line names none: the draft is flagged `counterparty_unverified`, scores at most 85 for the exact amount and 65 otherwise, and is never auto-posted. Only other partners own it: the draft is marked `paid_by_third_party` in the exact and the partial branch, scores at most 60 in both, and is never auto-posted.
- `t08_cash.py` covers each case.
Source: ADR-0048.R9, ADR-0048.R9.N2, ADR-0048.R9.N3

R19. Steps 3 to 5 of the cascade:
- Step 3, account and amount: the partner that owns the counterparty's bank code and account number, and its item of exactly that amount, the oldest due among equals (score 90, or 60 when several are equal). An account owned by several partners makes the line unmatched (`shared_account`).
- Step 4, account and subset: the fewest of that partner's items that sum exactly to the amount, searched among its 6 oldest, the oldest set first, then the lowest IDs (score 70).
- Step 5, unmatched: otherwise a work item `bank_line_unmatched`.
Source: ADR-0048.R9

R20. Company rules: `bank_matching_rule` maps a description token or a counterparty account to a partner or an account. Rules apply before step 3, and only to lines with no match at steps 1 and 2.
- The rules are artifacts of kind `matching_rule`, written as draft versions, with `match_mode` (ADR-0059.R10).
- A partner rule names the partner only, and steps 3 and 4 score the match.
- An account rule drafts to its account. It scores `cap_company_rule` in confirm mode only for a whole, reference-shaped token and an amount on the account's natural side. Like every draft under the unverified or third-party cap it keeps that flag and is never auto-posted.
- A rule suggests in `assisted` (no score) and confirms in `active` (capped by `cap_company_rule` and the counterparty caps). Several rules on a line, or any ambiguity, suggest.
- The account-rule class `bank_charge` passes the counterparty check on a debit line whose bank transaction code the money account's `cash.bank_charge.codes` lists and that names no counterparty account. It may auto-post per rule under `cash.bank_charge.auto_post_ceiling` with its own evidence, never when open items also match, more than one rule matches or the LLM classified the purpose (ADR-0063.R9).
Source: ADR-0048.R9, ADR-0048.R9.N5, ADR-0048.R9.N6

R21. Outcome and line states. The cascade proposes; it never matches a line to a draft.
- Steps 2 to 4 draft a `bank_receipt` or `bank_payment` with the lines found, as `system` on behalf of the importer. Step 1 and these drafts leave the line `proposed`.
- The line becomes `matched` only in the transaction that posts its proposed document, or by `MatchBankLine` naming a posted document. `MatchBankLine` naming a draft makes that draft the proposal.
- Discarding or canceling a proposed draft, or `UnmatchBankLine` on a proposed line, returns the line to `unmatched` in the same transaction.
- A document is the proposal of at most one line (R16), and an auto-post matches the line in its posting transaction.
- `UnmatchBankLine` unlinks a matched line. It is rejected with `bank_statement_line_posted` when the document was created from that line and is posted; its fix names `Reverse<Type>`, which is `human_only` and unmatches the line itself (ADR-0048.R16).
Source: ADR-0048.R9, ADR-0048.R9.N1

R22. Auto-post and LLMs:
- A rule allowing `system` to post a deterministic match below an amount is disabled by default. It needs shadow-mode evidence, an owner and confirmation (ADR-0029.R13; ADR-0043.R14). Drafts from a statement imported by an agent run are never auto-posted (ADR-0043.R9, floor 5; ADR-0029.R12).
- The auto-post is an instance of the auto-post gateway: `cash` registers checkers for `bank_receipt`, `bank_payment`, `cash_receipt` and `cash_payment` whose rules are these eligibility conditions and the `bank_charge` gates, with the cascade as their trigger. Their decisions are written in the gateway's columns of `policy_decision` (ADR-0065.R20).
- An agent reading descriptions works on tainted input. Its suggestions are drafts or proposed rules, never part of a score, and never auto-posted (spec 03 rule 1). The agent records its reading with `RecordBankLineSuggestion`; a consumer re-runs the cascade with it and drafts without a score (ADR-0051.R17, ADR-0051.R18).
- A rule proposed by an LLM feeds auto-post only while `cash.auto_post.accept_llm_originated_rules` is true (default false) and the conditions of ADR-0063.R8 hold.
Source: ADR-0048.R9, ADR-0048.R9.N6, ADR-0048.R9.N7

R23. The cascade's constants are the defaults of the tunable function `cash.match_bank_line` (ADR-0059.R5, ADR-0059.R6): the 5-day window, the subset size of 6, the scores 95, 100, 80, 90, 60 and 70, the caps 85, 65 and 60, `cap_company_rule` 90 and `show_min_score` 0. ADR-0059.R5 gives each parameter's name and bounds. The tied score 60 is a safety cap, and exact > partial > subset is an order constraint. A tied match is marked on its line (`match_is_tied`) and never auto-posted, outside tuning. A company changes the parameters only by a parameter set version through the lifecycle. Every proposal records the parameters hash (`match_parameters_hash`), the function version (`match_function_version`), the parameter set version (`match_parameter_set_version_id`) and its state (`match_parameter_state`: `core_default`, `assisted`, `active`).
Source: ADR-0048.R9.N5

### Netting and write-off

R24. `partner_netting` settles one partner's receivable items against its payable items on different accounts, in one currency, for equal amounts, with `evidence_method` `offset`. The lines go directly between the accounts at the items' carrying amounts, with realized exchange differences (ADR-0026.R6).
- Agreement: where the regime setting `cash.netting_requires_agreement` is true, an attached agreement is required, otherwise `netting_agreement_missing`. Its value is flagged package content of the localization package, `unverified`.
- Scope: netting within one account is `open_item_matching` (ADR-0026.R9). Items in different currencies are netted after an exchange (R29). Netting across partners comes later (open question).
Source: ADR-0048.R10

R25. `write_off` has these reasons and accounts:
- `small_difference`: up to `cash.small_difference_limit` per item, in company currency (company setting, default 0; above it `write_off_above_limit`), to `payment_difference_income` or `payment_difference_expense`.
- `bad_debt`: a receivable, first against `bad_debt_allowance` up to the allowance available, the rest to `bad_debt_expense`. The required evidence is the regime's, package content of the localization package.
- `payable_release`: a payable no longer owed, to `payable_release_income`.
- Settlements carry `evidence_method` `none`. Written-off items stay as settled items (ADR-0039.R2).
- A later receipt of a written-off debt is an `account` line to `bad_debt_recovery`.
- Posting is `human_only` (flagged). A limit above which approval is needed is the company's policy.
Source: ADR-0048.R11

### Currency, rates and money account balances

R26. Payment rates and the rate check:
- A payment in a foreign currency may carry the settlement rate (ADR-0011.R12; R5). The regime setting `fx.document_rate.allowed` takes a value per document group. Group `cash_and_bank` (the four payment types, `currency_exchange` and settle-line exchanges) uses `always`, because these documents record the bank's or cash desk's actual rate; the package seed of that value is flagged `unverified`. `never` stays the default for other documents.
- A rate outside the setting's `tolerance_percent` of the transaction rate returns the check result `settlement_rate_unusual` and sets `is_rate_unusual` for the policy, so a mistyped rate is seen before it posts. Without a transaction-rate quote the check is skipped with the check result `settlement_rate_unchecked`; it never raises `exchange_rate_missing`.
- Without a settlement rate the check is skipped: neither `settlement_rate_unusual` nor `settlement_rate_unchecked` is returned, and `is_rate_unusual` is false.
- Settling items in a foreign currency follows ADR-0026.R6, which owns the realized FX logic. The author-owned runbook still names DS-10 (open question).
Source: ADR-0048.R12, ADR-0048.R3.N1

R27. Book rate of money accounts (ADR-0011.R15, `moving_average`):
- An outflow takes the money account's average rate over its cumulative recorded balance when the outflow posts. It is computed separately for company and group currency. The realized difference is the outflow's value at the settlement rate less its book value.
- Whenever a posting of any kind (an outflow, an inflow, a reversal) leaves the foreign balance at zero, the same entry posts the remaining company and group amounts to realized exchange difference, so no residual is left.
- A backdated posting does not restate outflows already posted.
- The group moving average applies to every money account, company-currency ones included, because their group amount is a translation.
- Overdraft beyond the balance is valued at the settlement rate (ADR-0011.R15); for the group amount of a company-currency account that is the group translation rate of the posting.
Source: ADR-0048.R12, ADR-0048.R12.N3

R28. Floors and the balance row:
- A money account without `is_overdraft_allowed`, cash or bank, may not be below zero in its currency at the posting date or any later date, in posting-date order (`money_account_negative`; `INV-94`). Overdraft is allowed only on bank accounts in company currency, where no book rate applies.
- Each money account has one `money_account_balance` row, owned by `cash` and serialized (ADR-0008.R10): the cumulative foreign, company and group balance that the book rate and the floor read.
- Every posting on a money account's operational account locks it, after partner rows and before open items (ADR-0027.R10).
- Postings that `ledger` makes on these accounts, such as revaluation and general journal lines, take it through a lock hook that `cash` registers (ADR-0022.R2).
Source: ADR-0048.R12, ADR-0048.R12.N2

R29. `currency_exchange` moves an amount out of one money account and another amount into a second one in another currency. A settle line in another currency does the same inside a payment (R7).
- Each side posts against key `currency_exchange_clearing`. Its system account `currency_exchange_clearing` (control kind `none`) is excluded from every revaluation scope by the core, like `opening_balance_clearing` (ADR-0011.R18).
- Per document, it nets to zero in company and group currency after the realized difference of the outgoing side, which takes its book value. Per transaction currency it may keep balances, which revaluation never touches.
- Group currency: in a `currency_exchange` and in a settle line's exchange, both clearing lines take the group amount of the incoming leg, on an applied rate of origin `settlement`, so the clearing account nets to zero in group currency too, and the outgoing side's group difference is realized.
- The operational account the regime maps the key to is flagged package content of the localization package, `unverified` (ADR-0011.R4).
Source: ADR-0048.R12, ADR-0048.R12.N3

R30. A `money_transfer` is one document per side, so each statement line matches its own document (R16).
- The outgoing side names the source and the target money account and posts the source's credit against key `cash_in_transit`. The incoming side refers to the outgoing one and posts the target's debit against the same key for the same transaction amount. Posting the outgoing side drafts the incoming side.
- Both money accounts must share a currency (`money_transfer_currency_mismatch`; across currencies, `currency_exchange`).
- In a foreign currency both sides carry the source's book value in company and group currency, so a transfer has no realized difference, and `cash_in_transit` nets to zero per transfer in every currency.
- Money moves between money accounts only by `money_transfer` or `currency_exchange`: a payment's `account` line that names a money account's operational account is rejected with `money_account_line_not_allowed`.
- The operational account of key `cash_in_transit` is flagged package content of the localization package, `unverified`.
Source: ADR-0048.R12.N1, ADR-0048.R1.N3

### Advances

R31. Advances:
- Customer and supplier advances are `advance` items on the trade account (`advance` lines, R7). They are applied to invoices by `open_item_matching` (ADR-0026.R9). The matching's settling lines carry the advance's own evidence method, copied from the line that created the advance item (ADR-0048.R18). A `payment_on_account` matched later does the same.
- Employee advances are `advance` lines to an employee partner on `receivable_employee_advance`; its operational account is package content.
- `advance_settlement` is the employee's accounting for an advance. Its lines are expenses (account, amount, cost center, and taxes with the supplier and the supplier's invoice, as the taxed lines of R7). Each records how the employee paid the supplier (`cash`, `bank_transfer`, `card`), passed to `tax.contract.record_payment_evidence`. The advance items it names are settled with `evidence_method` `offset`.
- Expenses below the advance leave the rest open, repaid by a `cash_receipt`.
- Expenses above the advance: the excess is paid to the employee first by a `cash_payment` or `bank_payment` with an `advance` line, and then settled. This is regime-neutral: one open item per advance, and no payable account for employees is needed (ADR-0053.R14). The open questions on employees as suppliers and on salaries per employee stay as they are.
Source: ADR-0048.R13, ADR-0048.R13.N1

## Invariants

- `INV-94` (day): the balance of every money account without overdraft, in its currency and posting-date order, is never negative at any date; a money account whose foreign balance is zero has zero company and group balances. Protects R27, R28.
- `INV-95` (day): every matched bank statement line refers to a posted, unreversed document of the same money account whose amount on that money account equals the line's. Protects R16, R21.
- `INV-96` (day): each bank statement's opening balance equals the previous statement's closing balance, or the statement has `has_gap`; opening plus lines equals closing. Protects R15.

`INV-98`, `INV-501` and `INV-705` are stated in chunk 2.

## Edge cases

| Case | Name | Outcome | Rule |
| --- | --- | --- | --- |
| `EC-72` | `duplicate_bank_line_without_reference`: two equal statement lines without a bank reference; both are kept with `duplicate_suspected` | `must_succeed` | R15 |
| `EC-73` | `payment_while_invoice_issuing`: a customer pays while the invoice is still in `issuing`; the receipt records an advance, matched to the invoice after it posts | `must_succeed` | R8 |
| `EC-74` | `early_payment_discount_partial`: a partial payment within the discount date takes the discount on the share it settles | `must_succeed` | R14 |
| `EC-75` | `cash_count_shortage`: a cash count finds less than the book balance; the shortage posts to the pending account | `must_succeed` | R10 |
| `EC-76` | `currency_exchange_between_accounts`: foreign currency sold from one money account into another; the clearing nets to zero after the realized difference | `must_succeed` | R29 |
| `EC-77` | `bad_debt_provision_then_write_off`: overdue items cross two provision buckets; a later write-off uses the allowance first. First executable at step 8 | `must_succeed` | R25, ADR-0048.R14 |
| `EC-78` | `employee_advance_overspent`: an employee spends more than advanced; the excess is paid as a further advance and the settlement then clears both | `must_succeed` | R31 |

`EC-82`, `EC-163`, `EC-165`, `EC-168`, `EC-182`, `EC-183`, `EC-184` and `EC-263` are stated in chunk 2.

## Settings

None of the keys below has a row in `settings.csv`; the rules define them:

| Key | Value type | Scope | Core default | Used by |
| --- | --- | --- | --- | --- |
| `cash.bank_account_cooling_days` | not stated (days) | company | 7 | R9 |
| `cash.small_difference_limit` | not stated (amount in company currency) | company | 0 | R25 |
| `cash.netting_requires_agreement` | boolean | regime | not stated; the package value is flagged `unverified` | R24 |

The rows of `cash.bank_charge.codes`, `cash.bank_charge.auto_post_ceiling` and `cash.auto_post.accept_llm_originated_rules` (used by R20, R22) are in chunk 2, with the other keys of `cash`.

Reads: `fx.document_rate.allowed` with its `tolerance_percent` (regime setting; ADR-0011.R12; no row in `settings.csv`), used by R26.

## UI annotations

The sources of this chunk state no floorplan, title, facet, field annotation or tile. Work item kind raised by this chunk's rules:

| Kind | Subject table | Owner | Due | Resolution | Rule |
| --- | --- | --- | --- | --- | --- |
| `bank_line_unmatched` | `bank_statement_line` | `role:accountant` | `days:2` | `system`: closed when the line is matched or ignored with a reason; not agent-resolvable | R19 |

The row is that of `work-item-kinds.csv` (module `cash`; ADR-0048.R9; ADR-0042.R1). The bank matching workflow of chunk 2 takes this kind as its trigger (ADR-0051.R17).

## Conflicts

CONFLICT ADR-0048.R1: ADR-0048.R1.N3 adds the posting type `money_transfer` to the type list, and ADR-0048.R1.N1 makes the Vietnamese voucher names examples only, so R2 states neutral types.
CONFLICT ADR-0048.R3: ADR-0048.R3.N1 governs, the settlement rate of a foreign-currency payment is optional (R5); the DDL adds the partner snapshot (ADR-0028.R16) and `business_unit_id` (ADR-0069.R8), stated in R5 and R7.
CONFLICT ADR-0048.R8: ADR-0048.R8.N1 adds `proposed` to `match_state`; the DDL, which is later, names the score `proposal_score` and adds `bank_transaction_code` and the basis `bank_charge_rule` under ADR-0063.R9 (R15); the basis `company_rule_account` of ADR-0059.R10 is not in the DDL check, and R15 says so.
CONFLICT ADR-0048.R9: ADR-0048.R9.N1 governs the outcome, a draft leaves its line `proposed` and never matched (R21); ADR-0048.R9.N2 replaces the third-party score 70 by the cap 60 in both branches (R18); ADR-0048.R9.N3 splits the exact branch into prefix 100 and single item 90 (R18); ADR-0048.R9.N5 turns company rules into `matching_rule` artifacts and the constants into tunable defaults (R20, R23); ADR-0048.R9.N6 (ADR-0063.R8, ADR-0063.R9) lets a `bank_charge` rule pass the counterparty check and auto-post per rule, and lets an approved LLM-proposed rule feed auto-post only under `cash.auto_post.accept_llm_originated_rules` (R20, R22); ADR-0048.R9.N7 (ADR-0065.R20) makes the auto-post a gateway instance (R22).
CONFLICT ADR-0048.R12: ADR-0048.R3.N1 governs the first bullet, a foreign-currency payment may omit the settlement rate and then skips the rate check (R26).
CONFLICT ADR-0048.R13: ADR-0048.R13.N1 governs; paying the excess as a further advance is regime-neutral, so the mark naming the advance-account practice of one country's chart and `unverified` are not restated (R31).

## Trace

| Source | Where |
| --- | --- |
| ADR-0026.R1 | ref: ADR-0026.R1 |
| ADR-0026.R1.N1 | ref: ADR-0026.R1.N1 |
| ADR-0026.R1.N2 | ref: ADR-0026.R1.N2 |
| ADR-0028.R15 | R6 |
| ADR-0048.D0 | R3 |
| ADR-0048.R1 | R1, R2 |
| ADR-0048.R1.N1 | R2 |
| ADR-0048.R1.N2 | R2 |
| ADR-0048.R1.N3 | R2, R30 |
| ADR-0048.R2 | R4 |
| ADR-0048.R3 | R5, R7, R8, R9 |
| ADR-0048.R3.N1 | R5, R9, R26 |
| ADR-0048.R3.N2 | R5 |
| ADR-0048.R4 | R10 |
| ADR-0048.R5 | R11 |
| ADR-0048.R6 | R12, R13 |
| ADR-0048.R7 | R14 |
| ADR-0048.R8 | R15, R16 |
| ADR-0048.R8.N1 | R15, R16 |
| ADR-0048.R8.N2 | R17 |
| ADR-0048.R9 | R17, R18, R19, R20, R21, R22 |
| ADR-0048.R9.N1 | R21 |
| ADR-0048.R9.N2 | R18 |
| ADR-0048.R9.N3 | R18 |
| ADR-0048.R9.N4 | R7 |
| ADR-0048.R9.N5 | R20, R23 |
| ADR-0048.R9.N6 | R20, R22 |
| ADR-0048.R9.N7 | R22 |
| ADR-0048.R10 | R24 |
| ADR-0048.R11 | R25 |
| ADR-0048.R12 | R26, R27, R28, R29 |
| ADR-0048.R12.N1 | R30 |
| ADR-0048.R12.N2 | R28 |
| ADR-0048.R12.N3 | R27, R29 |
| ADR-0048.R13 | R31 |
| ADR-0048.R13.N1 | R31 |
