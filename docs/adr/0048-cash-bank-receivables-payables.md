# ADR-0048: Cash, bank, receivables and payables processes

Status: accepted (2026-11-15) under ADR-0005, reviewed by Claude Fable 5.2 (builder Claude Opus 5.5). Design item: DS-25. Related decisions: D4, D5. Principles 1, 3, 8, 9, 13. ADR-0006, ADR-0007, ADR-0009, ADR-0010, ADR-0011, ADR-0012, ADR-0013, ADR-0014, ADR-0015, ADR-0016, ADR-0019, ADR-0022, ADR-0026, ADR-0027, ADR-0028, ADR-0029, ADR-0030, ADR-0038, ADR-0039, ADR-0041, ADR-0042, ADR-0043, ADR-0044, ADR-0047.

## Decision

The open-item core of ADR-0026 already settles items, computes carrying amounts and realized exchange differences, and reverses settlements exactly. DS-25 adds the business processes on top of it, in the layer-4 module `cash`, without changing the core.

**Money accounts.** A company's cash boxes and bank accounts become `money_account` records, each on its own operational account. Balances, book rates and statements are therefore per account.

**Payments.** Four posting types: `cash_receipt`, `cash_payment`, `bank_receipt` and `bank_payment`. Their lines say what they do:
- settle named open items, in the item's currency or through an exchange inside the document;
- create an advance or a payment on account;
- post directly to an account, such as an expense without an order;
- record a bank charge.

Allocation is always explicit. A deterministic query proposes it, and a person or an enabled rule accepts it.

**Bank statements.** Package readers import them, and a deterministic cascade matches them to documents. Already-posted documents come first. Then whole-token references within one partner, then the counterparty's bank account with an exact amount, then a bounded subset of that partner's items. The same input, in any order, always gives the same proposal. An LLM may suggest rules or read descriptions, but its output never counts in a score and is never auto-posted.

**Other processes.** Early-payment discounts, write-offs, netting, currency exchange, employee advances and their settlement, cash counts, bad-debt provisions, prepaid amortization and dunning. Each is a small document or job with stated accounts.

**Core and overlay.** The author's rule (2026-11-15): Vietnamese accounting standards and Vietnamese tax are an overlay outside the core. Everything here that is Vietnamese (accounts, provision bands, the netting agreement, the non-cash payment threshold, the invoice key fields) is a regime setting or a package row of `l10n_vn` (ADR-0016), never core behavior. The core only knows that such settings exist.

### Rules

**Module and types**

1. `cash` (layer 4, ADR-0022 rule 2) owns the tables and document types of this ADR. It calls `ledger.contract.write_journal_entry` for every posting, `tax.contract.record_payment_evidence` for taxed lines without an open item, and reads open items through `ledger` queries. It imports no other layer-4 module: what it needs from `crm` and `purchasing` reaches it through their events (rules 14, 17). Document types (ADR-0009 rules 2–3):

   | Type | Posting | Reversible | Rules |
   | --- | --- | --- | --- |
   | `cash_receipt`, `cash_payment`, `bank_receipt`, `bank_payment` | yes | while unreferenced (rule 16) | 3, 5–9, 12 |
   | `currency_exchange` | yes | yes, internal | 12 |
   | `partner_netting` | yes | yes, internal | 10 |
   | `write_off` | yes | yes, internal | 11 |
   | `advance_settlement` | yes | while unreferenced | 13 |
   | `cash_count` | no | — | 4 |
   | `cash_count_adjustment` | yes | yes, internal | 4 |
   | `provision_entry`, `prepaid_amortization` | yes, by system jobs | yes, internal | 14 |

   - **Approval hold** is allowed on all of them. None is e-invoice capable.
   - **`general_journal`** stays `ledger`'s (ADR-0014 rule 3). Rule 15 adds its approval and control-account rules.
   - **Spec 08's names:** cash receipt (phiếu thu) is `cash_receipt`, cash payment (phiếu chi) is `cash_payment`, and bank credit and debit advices are `bank_receipt` and `bank_payment`. The cash book is a report (DS-26).

   Note: the Vietnamese voucher names are examples from spec 08; the types are neutral ([ADR-0053](0053-core-neutrality.md) rule 14).

   Note: the cash book is a book definition over journal lines grouped by account. The payment types are `is_printable` and carry `print_language` ([ADR-0049](0049-statutory-reporting-and-printing.md) rules 10, 27).

   Note: a further posting type, `money_transfer` (reversible while unreferenced, rule 16; approval hold allowed; not e-invoice capable; authorization leaf `money_transfer` under `banking`), moves money between two money accounts of the company in one currency. It has no partner, open item or tax. Its accounting is in rule 12's notes; the registry row follows the table above (holistic review, 2026-11-15).

**Money accounts**

2. `money_account` (company data, `master_data_change`, change-tracked; agents propose changes, ADR-0029 rule 5):
   - **Fields:** `code`, `name`, `kind` (`cash`, `bank`), `currency`, `account_id`, `is_active`. Banks also carry the bank's name and code, the account number and branch, and `is_overdraft_allowed`, which Phase 1 allows only on bank accounts in company currency (`overdraft_not_allowed`).
   - **The operational account** has system account `cash_on_hand` (cash) or `cash_in_bank` (bank) in its hierarchy, and its currency equals the money account's (ADR-0010 rule 10). Each operational account serves at most one money account.
   - **Natural key of statement lines.** The money account is the "bank account" of ADR-0030 rule 10's key.

**Payments**

3. Payment documents (`cash_receipt`, `cash_payment`, `bank_receipt`, `bank_payment`):
   - **Header:**
     - `money_account_id`, whose kind matches the type (`money_account_kind_mismatch`) and whose currency is the document's;
     - document and posting dates, and for bank documents the value date;
     - the partner (optional when all lines are account lines);
     - for a foreign currency, the settlement rate (rate type `settlement`, ADR-0011 rule 12);
     - a reference;
     - for a `bank_payment` to a partner, `partner_bank_account_id` in the content (ADR-0028 rule 15), an active account of that partner;
     - for cash documents, the payer's or payee's name as a snapshot.
   - **Line kinds:**
     - **`settle`:** an open item and the amount in the item's currency. In the document's currency, it settles directly. In another currency, it is an exchange inside the document: the line carries the item-currency amount and the bank's rate, and the document adds one line per currency on key `currency_exchange_clearing` (rule 12; ADR-0026 rule 4). An optional discount follows rule 7. `paid_by_third_party` marks a payment made by someone other than the item's partner.
     - **`advance`:** creates an `advance` item for the partner, on the account determination gives (the trade account, or `receivable_employee_advance` for employees).
     - **`on_account`:** creates a `payment_on_account` item. This is also how an overpayment is recorded (ADR-0026 rule 8).
     - **`account`:** posts to an account the line names, with optional cost center, project and taxes. A taxed line needs the supplier: a partner, or a tax ID and name kept as a one-time snapshot. It also needs the fields of the regime's supplier-invoice key (Vietnam: form, symbol and number), the invoice date, and the stated tax (ADR-0041 rules 7, 10). The supplier-invoice key of ADR-0030 rule 10 applies to these lines and to purchase invoices together, so one invoice cannot be deducted twice (`duplicate_external_document`).
     - **`bank_charge`:** posts to key `bank_charge`.
   - **Evidence** (rule 18). Lines that settle or create an item carry `evidence_method`: `cash` for cash documents, `bank_transfer` for bank documents, `card` when the line says so, `third_party` when `paid_by_third_party` is set. A taxed `account` line has no open item. In the posting transaction, the document calls `tax.contract.record_payment_evidence` for it with the same method (ADR-0041 rule 15).
   - **Invoices in `issuing`** have no open item yet (ADR-0028 rule 9). A payment that arrives then is an advance or a payment on account, matched later.
   - **Policy input:**
     - amount in company currency;
     - `is_direct_expense`: an `account` line to an expense;
     - `is_bank_account_recent`: the beneficiary account was created or changed within `cash.bank_account_cooling_days` (company setting, default 7);
     - `is_rate_unusual`: rule 12's rate check.

     The conditions join ADR-0043 rule 3 (a note there).

   Note: the settlement rate is optional. Without one, the document converts at the transaction lookup rate (applied rate origin `lookup`, ADR-0011 rule 11), and rule 12's rate check is skipped: there is nothing to compare, so neither `settlement_rate_unusual` nor `settlement_rate_unchecked` is returned, and `is_rate_unusual` is false (holistic review, 2026-11-15).
4. Cash counts:
   - **`cash_count`** (non-posting) records a cash money account, the counted amount (optionally by denomination) and the book balance at the time. It is kept as evidence even when nothing differs.
   - **`cash_count_adjustment`.** When a count is approved with a difference, it creates and posts this document:
     - a surplus to key `cash_surplus` (TT99 3381, pending resolution);
     - a shortage to key `cash_shortage` (TT99 1381, pending resolution).

     A foreign-currency difference is valued at the money account's book rate (rule 12). The accounts are `unverified`. The pending account is resolved later by a general journal or an employee receivable. A count written by an agent run leaves its adjustment as a draft for a person (ADR-0043 rule 9, floor 5).
5. Policy and agents:
   - **Agents** may draft payments and propose allocations. An agent's posting gets `human_post` (ADR-0043 rule 9, floor 4). A payment is posted by `system` only through rule 9's auto-post, which is disabled by default. The system postings of rules 4 and 14 are adjustments and close jobs, not payments.
   - **Bank account changes** keep ADR-0029 rule 4: a proposal approved by a human who wrote no version of it.
   - **No money moves from ERPMe in Phase 1.** Payment documents record payments made through the bank or the cash box. Payment files and bank connections that send money are add-ons after the core, like the e-invoice provider (open question).

**Allocation and discounts**

6. Allocation is explicit (ADR-0026 rule 3): each `settle` line names its item and amount.
   - **`GetAllocationProposal`** (partner, amount, currency, side, date) is a deterministic query. It skips blocked and disputed items (rule 17). It returns an item of exactly that amount (the oldest due among equals); otherwise items oldest due first, the last one partly settled; and any rest as `on_account`. It lists the partner's open credits and advances separately, for the person to apply.
   - **Use.** It is never applied by itself: a person accepts it, an agent drafts with it, or an enabled matching rule uses it (rule 9).
7. Early-payment discounts (ADR-0026 rules 1, 8):
   - **When.** A `settle` line takes the item's discount when the payment's document date (a bank line's value date) is on or before the item's `discount_due_date`.
   - **How much.** For an item with discount `p`, a cash amount `c` in the item's currency settles `round(c ÷ (1 − p/100))`, capped at the open amount. The discount is that amount minus `c`, so a partial payment takes a partial discount. In a foreign currency, the discount line is valued at the item's carrying amount for its share, as ADR-0026 rule 6 does for any settlement.
   - **Posting.** `payment_discount_given` (customers) or `payment_discount_received` (suppliers), on a line that settles the item with `evidence_method` `none`. The author classified payment discounts as financial income and expense (2026-11-14). The absence of a VAT adjustment is `unverified`.
   - **Naming.** The policy input `discount_percent` is a price discount (ADR-0047 rule 22); the open item's `discount_percent` is a payment discount. Payment policy inputs use `payment_discount_amount`.

**Bank statements and matching**

8. Bank statements:
   - **Records.** `bank_statement` holds the money account, statement number, period, opening and closing balance, source attachment, reader code, and `has_gap`. `bank_statement_line` holds the booking and value date, the signed amount, the bank reference, the counterparty's name, bank code and account number, the description, and `match_state` (`unmatched`, `matched`, or `ignored` with a reason) with the matched document.
   - **Import.** `ImportBankStatement` (verb Import) runs a `BankStatementReader` from the localization package (ADR-0016 rule 17) on an attached file. These fields are the reader's interface (DS-14).
   - **Checks at import:**
     - opening balance plus the lines must equal closing balance, otherwise the import is rejected with `bank_statement_unbalanced`;
     - an opening balance that differs from the previous closing balance sets `has_gap` and returns the check result `bank_statement_gap`.
   - **Duplicates** follow ADR-0030 rule 10's natural key. Descriptions are `is_untrusted` (ADR-0029 rule 10), and so is description text copied into a draft.
   - **Formats.** A generic CSV reader ships in the core test kit for the synthetic dataset (DS-17). Two or three bank formats are package work for step 6 (spec 06).
   - **Reconciliation.** `GetBankReconciliation` (money account, date) compares the statement's closing balance with the book balance, and lists unmatched lines and unmatched book postings. The close checklist task "bank statements reconciled" (ADR-0012 rule 13) reads it.
   - **Ignoring a line** (`IgnoreBankLine`, with a reason; the new verb Ignore) is `human_only`.
   - **One line, one document** in Phase 1. Several lines to one document, or one line to several, come later (open question).

   `BankLineSuggestionRecorded` carries IDs only; the suggested tokens stay on the line as untrusted fields ([ADR-0051](0051-agent-workflows.md) rule 17).

   Note: `match_state` gains `proposed`. A proposed line names its document in `proposed_document_id`, with the cascade's `score` and `match_basis` (`already_posted`, `reference`, `company_rule`, `account_amount`, `account_subset`, `llm_suggestion` or `manual`); a matched line names its document as before. `GetBankReconciliation` counts proposed lines as unmatched, so neither the reconciliation nor its close task treats a draft as booked. INV-95 is unchanged (holistic review, 2026-11-15).
9. Matching:
   - **The cascade:** `match_bank_line`, a pure function, checked by the lab on shuffled inputs. It first puts open items and documents in a canonical order (due date, then ID). An inflow considers only items on the debit side, an outflow only items on the credit side, and only items in the money account's currency. Then it applies, in order:
     1. **Already posted:** an unmatched posted document of this money account in the same direction and amount, dated within 5 days, whose reference is a token of the description or whose partner owns the counterparty's account. The closest date wins, then the earliest, then the lowest ID (score 95). Nothing new is drafted.
     2. **Reference:** items whose reference or partner reference appears as a whole token in the description, all of one partner. Only reference-shaped tokens count: at least four characters with a digit, or the package's pattern for its invoice numbers.
        - The exact sum settles them (score 100). When the counterparty's account belongs to another partner, the draft is marked `paid_by_third_party` and scores 70.
        - Otherwise, those items are settled oldest due first, partly if the amount is short, with any excess on account (score 80). The cascade never switches to another item.
        - Tokens naming items of several partners make the line unmatched (`ambiguous_reference`).
     3. **Account and amount:** the partner that owns the counterparty's bank code and account number, and its item of exactly that amount, the oldest due among equals (score 90, or 60 when several are equal). An account owned by several partners makes the line unmatched (`shared_account`).
     4. **Account and subset:** the fewest of that partner's items that sum exactly to the amount, searched among its 6 oldest, the oldest set first, then the lowest IDs (score 70).
     5. **Unmatched:** otherwise a work item `bank_line_unmatched`.
   - **Company rules.** `bank_matching_rule` (company data, proposal-bound) maps a description token or a counterparty account to a partner or an account. Rules apply before step 3, and only to lines with no match at steps 1 and 2.
   - **Outcome.** Steps 2–4 draft a `bank_receipt` or `bank_payment` with the lines found, as `system` on behalf of the importer, and record the match. `MatchBankLine` links a line to an existing document. `UnmatchBankLine` unlinks it. It is rejected with `bank_statement_line_posted` when the document was created from that line and is posted; its fix names `Reverse<Type>`, which is `human_only` and unmatches the line itself (rule 16).
   - **Auto-post.** A rule allowing `system` to post a deterministic match below an amount is disabled by default. It needs shadow-mode evidence, an owner and confirmation (ADR-0029 rule 13; ADR-0043 rule 14). Drafts from a statement imported by an agent run are never auto-posted (ADR-0043 rule 9, floor 5; ADR-0029 rule 12).
   - **LLMs.** An agent reading descriptions works on tainted input. Its suggestions are drafts or proposed rules, never part of a score, and never auto-posted (spec 03 rule 1).

   The agent records its reading with `RecordBankLineSuggestion`; a consumer re-runs the cascade with it and drafts without a score ([ADR-0051](0051-agent-workflows.md) rules 17–18).

   Note: the cascade proposes; it never matches a line to a draft. Step 1 and the drafts of steps 2–4 leave the line `proposed`. The line becomes `matched` only in the transaction that posts its proposed document, or by `MatchBankLine` naming a posted document; `MatchBankLine` naming a draft makes that draft the proposal. Discarding or canceling a proposed draft, or `UnmatchBankLine` on a proposed line, returns the line to `unmatched` in the same transaction. A document is the proposal of at most one line (rule 8: one line, one document), and an auto-post matches the line in its posting transaction (holistic review, 2026-11-15).

   Note: a reference in a description is untrusted (ADR-0029 rule 10), so step 2's score depends on whose account paid:
   - **the item's partner owns the counterparty's account** (also when it shares it): 100 for the exact amount, 80 otherwise;
   - **no partner owns it, or the line names none:** the draft is flagged `counterparty_unverified`, scores at most 85 for the exact amount and 65 otherwise, and is never auto-posted;
   - **only other partners own it:** the draft is marked `paid_by_third_party` in the partial branch too, scores at most 60 in both branches, and is never auto-posted.

   `t08_cash.py` covers each case (holistic review, 2026-11-15).

   Note: an invoice's installments share its reference. Among the referenced items in due-date order, a prefix that sums exactly to the amount scores 100 and settles those items; otherwise a single referenced item equal to the amount scores 90 and settles that item; otherwise the partial branch applies. A token `<reference>-<installment_number>` (e.g. `INV-0101-2`) names that installment alone. The caps of the previous note apply to these scores, and `t08_cash.py` covers them (holistic review, 2026-11-15).

   Note (catalog review, 2026-11-15): the flag `paid_by_third_party` is the column `is_paid_by_third_party` of `payment_line` (DS-05-platform.sql; ADR-0004 rule 13).

**Netting and write-offs**

10. `partner_netting`:
    - **What it does.** It settles one partner's receivable items against its payable items on different accounts, in one currency, for equal amounts, with `evidence_method` `offset`. The lines go directly between the accounts at the items' carrying amounts, with realized exchange differences (ADR-0026 rule 6).
    - **Agreement.** The regime setting `cash.netting_requires_agreement` (Vietnam seeds true, `unverified`) requires an attached agreement, otherwise `netting_agreement_missing`.
    - **Scope.** Netting within one account is `open_item_matching` (ADR-0026 rule 9). Items in different currencies are netted after an exchange (rule 12). Netting across partners comes later (open question).
11. `write_off`:
    - **Reasons and accounts:**
      - `small_difference`: up to `cash.small_difference_limit` per item, in company currency (company setting, default 0; above it `write_off_above_limit`), to `payment_difference_income` or `payment_difference_expense`;
      - `bad_debt`: a receivable, first against `bad_debt_allowance` up to the allowance available, the rest to `bad_debt_expense`. Required evidence is the regime's: `l10n_vn` requires an attachment proving the debt is uncollectible (dissolution, death, court ruling, or the time conditions of its provision rules);
      - `payable_release`: a payable no longer owed, to `payable_release_income`.
    - **Evidence and status.** Settlements carry `evidence_method` `none`. Written-off items stay as settled items (ADR-0039 rule 2).
    - **Recovery.** A later receipt of a written-off debt is an `account` line to `bad_debt_recovery`.
    - **Who posts.** Posting is `human_only` (flagged). A limit above which approval is needed is the company's policy.

**Foreign currency**

12. Currency and rates:
    - **Payment rates.** Payments in a foreign currency carry the settlement rate (ADR-0011 rule 12). The regime setting `fx.document_rate.allowed` takes a value per document group. Group `cash_and_bank` (the four payment types, `currency_exchange` and settle-line exchanges) uses `always`, because these documents record the bank's or cash desk's actual rate. Vietnam seeds this `unverified`; `never` stays the default for other documents.
    - **Rate check.** A rate outside the setting's `tolerance_percent` of the transaction rate returns the check result `settlement_rate_unusual` and sets `is_rate_unusual` for the policy, so a mistyped rate is seen before it posts. Without a transaction-rate quote the check is skipped with the check result `settlement_rate_unchecked`; it never raises `exchange_rate_missing`.
    - **Book rate of money accounts** (ADR-0011 rule 15, `moving_average`). An outflow takes the money account's average rate over its cumulative recorded balance when the outflow posts. It is computed separately for company and group currency. Whenever a posting of any kind (an outflow, an inflow, a reversal) leaves the foreign balance at zero, the same entry posts the remaining company and group amounts to realized exchange difference, so no residual is left. A backdated posting does not restate outflows already posted. The realized difference is the outflow's value at the settlement rate less its book value.
    - **Floors.** A money account without `is_overdraft_allowed`, cash or bank, may not be below zero in its currency at the posting date or any later date, in posting-date order (`money_account_negative`). Overdraft is allowed only on bank accounts in company currency, where no book rate applies.
    - **Settling items** in a foreign currency follows ADR-0026 rule 6.
    - **Currency exchange.** `currency_exchange` moves an amount out of one money account and another amount into a second one in another currency. A settle line in another currency does the same inside a payment (rule 3). Each side posts against key `currency_exchange_clearing`. Its new system account `currency_exchange_clearing` (control kind `none`) is excluded from every revaluation scope by the core, like `opening_balance_clearing` (ADR-0011 rule 18). Per document, it nets to zero in company and group currency after the realized difference of the outgoing side, which takes its book value. Per transaction currency it may keep balances, which revaluation never touches. TT99 maps it to a technical account 998, `unverified` (ADR-0011 rule 4 gets a note).
    - **Ownership of the realized FX logic.** It is ADR-0026 rule 6. The author-owned runbook still names DS-10 (open question).

    Note: transfers between money accounts. A `money_transfer` is one document per side, so each statement line matches its own document (rule 8). The outgoing side names the source and the target money account and posts the source's credit against key `cash_in_transit`; the incoming side refers to the outgoing one and posts the target's debit against the same key for the same transaction amount. Posting the outgoing side drafts the incoming side. Both money accounts must share a currency (`money_transfer_currency_mismatch`; across currencies, `currency_exchange`). In a foreign currency both sides carry the source's book value in company and group currency, so a transfer has no realized difference, and `cash_in_transit` nets to zero per transfer in every currency. A payment's `account` line that names a money account's operational account is rejected with `money_account_line_not_allowed`: money moves between money accounts only by `money_transfer` or `currency_exchange`. TT99 maps key `cash_in_transit` to 113, `unverified` (holistic review, 2026-11-15).

    Note: each money account has one `money_account_balance` row, owned by `cash` and serialized (ADR-0008 rule 10): the cumulative foreign, company and group balance that the book rate and the floor read. Every posting on a money account's operational account locks it, after partner rows and before open items ([ADR-0027](0027-cross-cutting-ownership.md) rule 10's note). Postings that `ledger` makes on these accounts, such as revaluation and general journal lines, take it through a lock hook that `cash` registers (ADR-0022 rule 2) (holistic review, 2026-11-15).

    Note: group currency. In a `currency_exchange` and in a settle line's exchange, both clearing lines take the group amount of the incoming leg, on an applied rate of origin `settlement`, so the clearing account nets to zero in group currency too, and the outgoing side's group difference is realized. The group moving average applies to every money account, company-currency ones included, because their group amount is a translation. Overdraft beyond the balance is valued as ADR-0011 rule 15's note says, at the settlement rate; for the group amount of a company-currency account that is the group translation rate of the posting (holistic review, 2026-11-15).

**Advances**

13. Advances:
    - **Customer and supplier advances** are `advance` items on the trade account (`advance` lines, rule 3). They are applied to invoices by `open_item_matching` (ADR-0026 rule 9). The matching's settling lines carry the advance's own evidence method, copied from the line that created the advance item (rule 18). A `payment_on_account` matched later does the same.
    - **Employee advances** are `advance` lines to an employee partner on `receivable_employee_advance` (TT99 141).
    - **`advance_settlement`** is the employee's accounting for an advance:
      - **Lines** are expenses (account, amount, cost center, and taxes with the supplier and the supplier's invoice, as rule 3's taxed lines). Each records how the employee paid the supplier (`cash`, `bank_transfer`, `card`), passed to `tax.contract.record_payment_evidence`.
      - **The advance items** it names are settled with `evidence_method` `offset`.
      - **Expenses below the advance** leave the rest open, repaid by a `cash_receipt`.
      - **Expenses above the advance:** the excess is paid to the employee first by a `cash_payment` or `bank_payment` with an `advance` line, and then settled. This is the common practice for account 141, `unverified`, and needs no payable account for employees. The open questions on employees as suppliers and on salaries per employee stay as they are.

    Note: settling the excess as a further advance is regime-neutral: one open item per advance. The account-141 practice is `l10n_vn`'s reading ([ADR-0053](0053-core-neutrality.md) rule 14).

**Close jobs**

14. Close jobs (ADR-0027 rule 8; ADR-0012 rule 13). Both are system jobs that post ordinary documents as `system`. The documents are reversible, and the jobs are idempotent per period.
    - **`RunBadDebtProvision` (period):**
      - It considers open `invoice` items on receivable accounts with control kind `receivable`, excluding employee advances, at their open company-currency amounts at the period end.
      - Each item gets a percentage by days overdue from the regime setting `cash.bad_debt_provision.buckets`. Vietnam seeds bands at 30, 50, 70 and 100 percent, `unverified`.
      - The partner's open credits and advances are not netted (flagged). Items in dispute are listed for the accountant rather than skipped (flagged).
      - It posts the difference between the required allowance and the current balance of `bad_debt_allowance` as a `provision_entry`: an increase to `bad_debt_expense`, or a release.
    - **`RunPrepaidAmortization` (period):**
      - A `prepaid_schedule` (journal line on `prepaid_expense`, total, first period, number of periods, target account, cost center) is created by a person. A `cash` consumer of posted purchase invoices and payments with lines on `prepaid_expense` drafts one for the person to confirm.
      - The job posts each period's share straight-line, the last period taking the rest, as a `prepaid_amortization`. The account comes from the schedule (ADR-0015 rule 5).

**Journal entries and reversals**

15. General journal entries (ADR-0014 rule 3):
    - **Approval.** Spec 08 asks for approval. The core seeds a rule requiring `standard` approval for `submit` and `post` of `general_journal`, for every actor kind (flagged; small companies follow ADR-0043 rule 13).
    - **Control accounts.** Lines on accounts with a control kind are rejected with `manual_posting_to_control_account`, unless the regime setting `journal.manual_posting_to_control_accounts` is true (ADR-0014 rule 10 gets a note; Vietnam seeds false).
    - **Expenses without an order** may use a payment's `account` line or a purchase invoice's `expense` line (ADR-0047 rule 12). Both apply the supplier-invoice key.

    Note: the approval seed is core segregation-of-duties practice, not a Vietnamese rule ([ADR-0053](0053-core-neutrality.md) rule 14).
16. Reversals (ADR-0009 rules 18–19):
    - **When.** A payment, netting, write-off or settlement document may be reversed while no document that is not reversed or canceled refers to it.
    - **How.** The reversal mirrors its lines exactly, realized differences and evidence methods included (ADR-0026 rule 11; EC-52). A bank statement line matched to the document returns to `unmatched` in the same transaction.
    - **Registry.** ADR-0009 rule 19 gets a note listing these types.

**Collections**

17. Dunning:
    - **Side tables.** `open_item_collection` (open item, `dunning_level`, `last_reminder_date`, `is_payment_blocked`, `is_disputed`, dispute reason) and `partner_collection` (partner, `has_open_complaint`), owned by `cash` (ADR-0026 rule 1's side table).
    - **Complaints.** A `cash` consumer of `crm`'s complaint events (DS-35) sets and clears `has_open_complaint`. `cash` never imports `crm`. The events are `ComplaintCreated`, `ComplaintUpdated`, `ComplaintClosed` and `ComplaintReopened`; on each, the consumer reads the partner's open complaints with `ListComplaint`, so their order does not matter ([ADR-0052](0052-minimal-crm.md) rule 21).
    - **`RunDunning` (date).** It proposes reminder drafts per customer, for overdue items that are not blocked or disputed, by levels of days overdue (company setting `cash.dunning.levels`, default 7, 30 and 60). Customers with an open complaint are skipped (spec 13).
    - **Sending.** Reminders are outbound message drafts. A person sends them, after the consent check (ADR-0019 rule 9). Interest on late payment comes later. The drafts are `crm` outbound messages, made by `crm`'s consumer of `RunDunning`'s completion event, which carries per customer the level and open item IDs; recipients are the contacts flagged `is_accounts_contact` ([ADR-0052](0052-minimal-crm.md) rule 28).

**Ledger and tax seams**

18. Changes to the core tables (DS-06), each a new column or check by ADR (ADR-0014 rule 9, which gets a note):
    - **`journal_line.evidence_method`**, nullable, with `CHECK (evidence_method IS NULL OR open_item_id IS NOT NULL)`. Values: `cash`, `bank_transfer`, `card`, `offset`, `third_party`, `none`.
      - **Lines that carry it:** every line with an `open_item_id` that is not the item's origin line and has a non-zero transaction amount (so not the `adjusts` lines of revaluation and realized differences), except the reversal of an origin line; plus the origin lines of `advance` and `payment_on_account` items, which record how the advance was paid.
      - **Matchings:** a matching against an advance or a payment on account copies that item's origin method onto its settling lines. A matching of a credit note uses `none`.
      - **Transfers.** In a `balance_transfer` the settling line uses `none`, and the creating line of a successor advance or payment on account copies its predecessor's origin method.
      - **Opening items.** Opening advance and payment-on-account lines carry `evidence_method` (a note on ADR-0044 rule 8), so a supplier advance paid by bank before cut-over still gives payment evidence when matched.
      - **Reversals** of non-origin lines copy the original's method.
      - **ADR-0041 rule 15** named these cases without values. `none` replaces the gap and "inherited" resolves to the concrete method (notes on ADR-0041 rule 15 and ADR-0026 rule 6). `OpenItemSettled` carries the method.
    - **`open_item.original_posting_date`**, required by ADR-0026 rule 1 and ADR-0044 rule 8, which the DDL lacked. It is the posting date for ordinary items. For opening items it is the old system's date, which the opening line now carries (a note on ADR-0044 rule 8).
    - **`ck_open_item_due_date`** now matches ADR-0026 rule 1: required for `invoice` and `credit`, empty for `advance`, `payment_on_account` and `loan`, either for `other`. Opening advance and payment-on-account lines therefore carry no due date (the same note).
19. Credit exposure:
    - **Settlements lower it.** `OpenItemSettled` (ledger) reaches the `sales` consumer that clears credit holds ([ADR-0047](0047-commercial-documents-and-pricing.md) rule 18).
    - **The tax evidence consumer** reads the same event (ADR-0041 rule 15).

**Catalogs**

20. Catalog rows:
    - **System account:** `currency_exchange_clearing` (a leaf under `asset`, not bilateral, control kind `none`; ADR-0010's count becomes 117 accounts, 99 postable), excluded from revaluation by the core. TT99 maps it to technical account 998, `unverified`.
    - **Transaction keys**, each with its TT99 row (`unverified`):
      - `bank_charge` → `administrative_expense` (6427 proposed). The author decided (2026-11-15) that the company declares this account at setup: setup shows the package's proposal, and the company confirms it or picks another (6425 and 635 are common). The choice is a company determination row with basis `company_decision` (ADR-0016 rules 6–7);
      - `cash_surplus` → `asset_surplus_pending` (3381);
      - `cash_shortage` → `asset_shortage_pending` (1381);
      - `payment_difference_income` → `non_operating_income` (711);
      - `payment_difference_expense` → `non_operating_expense` (811);
      - `bad_debt_expense` → `administrative_expense` (6426);
      - `bad_debt_allowance` → `receivable_allowance` (2293);
      - `bad_debt_recovery` → `non_operating_income` (711);
      - `payable_release_income` → `non_operating_income` (711);
      - `currency_exchange_clearing` → `currency_exchange_clearing` (998).
    - **Errors:** `money_account_negative`, `money_account_kind_mismatch`, `overdraft_not_allowed`, `bank_statement_unbalanced`, `bank_statement_line_posted`, `netting_agreement_missing`, `manual_posting_to_control_account`, `write_off_above_limit`.
    - **Check results:** `bank_statement_gap`, `settlement_rate_unusual`, `settlement_rate_unchecked`.
    - **Work item kinds:** `bank_line_unmatched` (a note on ADR-0042 rule 18).
    - **Settings:**
      - company: `cash.bank_account_cooling_days`, `cash.small_difference_limit`, `cash.dunning.levels`;
      - regime, which Vietnam seeds `unverified`: `cash.netting_requires_agreement`, `cash.bad_debt_provision.buckets`, and the per-group value of `fx.document_rate.allowed`.
    - **Invariants**, all first at step 6:
      - **INV-94:** the balance of every money account without overdraft, in its currency, is never negative at any date; a money account whose foreign balance is zero has zero company and group balances;
      - **INV-95:** every matched bank statement line refers to a posted, unreversed document of the same money account whose amount on that money account equals the line's;
      - **INV-96:** each bank statement's opening balance equals the previous statement's closing balance, or the statement has `has_gap`;
      - **INV-97:** every journal line that rule 18 lists has an `evidence_method`, and no other line has one.
    - **Edge cases:**
      - a duplicate bank line without a reference;
      - a payment arriving while its invoice is in `issuing`;
      - an early-payment discount on a partial payment;
      - a cash count with a shortage;
      - a currency exchange between two money accounts;
      - a bad-debt provision across buckets followed by a write-off;
      - an employee advance overspent and topped up before settlement.

      DS-17 adds events `cash_counted`, `currency_exchanged` and `advance_settled` to its cash group; EC-77 uses `period_closed`.

    Note: `cash_surplus` and `cash_shortage` also list `non_operating_income` and `non_operating_expense`, and `bank_charge` lists `financial_expense`, as regime alternatives; the TT99 rows are unchanged ([ADR-0053](0053-core-neutrality.md) rule 6).

    Note (catalog review, 2026-11-15): the seven edge cases are EC-72 to EC-78, in the order listed; [edge-cases.csv](../catalogs/edge-cases.csv) is authoritative.
21. Lab check `t08_cash.py` ([validation lab](../reviews/2026-11-14-design-validation/README.md)), pure functions:
    - the matching cascade: already-posted first, whole-token references within one partner, side and currency, partial references, shared accounts, subsets, and the same proposal for shuffled inputs;
    - allocation proposals; discounts by rule 7's gross-up; provision buckets;
    - company rules and a third-party reference; short tokens that are not references;
    - the book rate: a backdated cash outflow refused by the floor, the same floor on a bank account, a backdated outflow emptying the balance and a reversed inflow both leaving no residual, overdraft refused in a foreign currency;
    - cash count differences.

    The DS-06 changes run under the existing journal and opening tests. Not covered: tables, locks, consumers, statement readers, tax evidence.

## Context

ADR-0026 deliberately left the processes to DS-25: payments, allocation, matching, netting, write-offs, discounts and dunning, all on its interfaces. Spec 08 lists the Vietnamese minimum: cash receipts and payments, cash book and counts, employee advances, expenses without a purchase order, general journal entries with approval, netting, payment discounts, provisions by aging, and prepaid amortization. Spec 14 wants bank matching to be a deterministic cascade, with the LLM only reading descriptions.

The reference systems:
- **SAP:** payment documents with clearing, electronic bank statements with search strings, dunning runs and provisions.
- **D365:** journals for payments, bank reconciliation with matching rules, collections.
- **Odoo:** payments, and bank statement lines reconciled with models and follow-up levels.

ERPMe keeps the documents Vietnamese accountants know and the matching rules explicit and deterministic.

The first review found five things:
- the exchange clearing sat on a revalued account;
- backdated outflows could take cash below zero and leave residuals;
- reversal and unmatch blocked each other;
- `cash` reached two other layer-4 modules;
- the cascade could propose a second receipt for one already posted, or switch to another invoice.

The dedicated clearing account, the cumulative-balance book rate with the all-date floor, the reversal that unmatches, the event consumers, and the reordered cascade fix them.

## Options considered

| Option | For | Against |
| --- | --- | --- |
| Four payment types by channel and direction (chosen) | Matches Vietnamese vouchers and numbering; simple screens | Four types sharing one handler |
| One payment type with flags | Fewer types | Numbering series and prints differ per voucher anyway |
| Explicit allocation with a deterministic proposal (chosen) | No hidden decisions; agents and people see the same proposal | One more step for a person |
| Automatic oldest-first allocation in the core | Fast | Rejected by ADR-0026 as hidden business behavior |
| Deterministic cascade with already-posted first and bounded subsets (chosen) | Reproducible, explainable, no duplicate receipts | Misses matches a fuzzy model might find |
| LLM scoring of matches | More matches | Not reproducible; ADR-0029 forbids auto-posting them |
| Book rate over the cumulative recorded balance (chosen) | No residual when emptied; simple | A backdated inflow does not change outflows already posted |
| Book rate as of each posting date | Date-faithful | Leaves company-currency residuals after backdating |
| A dedicated, unrevalued exchange clearing account (chosen) | Never revalued; per-document zero in company currency | A technical account in the package |

## Constraints that come with the decision

- **ADR notes:**
  - ADR-0011 rule 4: the clearing system account; rule 12: the per-group document rate setting and the rate check; rule 15: the book rate and floors; rule 18: the clearing account excluded from revaluation;
  - ADR-0014 rules 9 and 10: the new column; the control-account error and setting;
  - ADR-0026 rules 1, 6: the side tables and DDL corrections; evidence values;
  - ADR-0041 rule 15: evidence values;
  - ADR-0043 rule 3: payment conditions; rule 15: the general journal seed;
  - ADR-0044 rule 8: the opening line's original posting date, due dates and evidence method;
  - ADR-0010 rule 16 and the count: the new leaf system account;
  - ADR-0009 rule 19: reversible types of this ADR;
  - ADR-0042 rule 18: `bank_line_unmatched`.
- **DDL:** [DS-06-universal-journal.sql](../design/DS-06-universal-journal.sql): `journal_line.evidence_method` and its check, `open_item.original_posting_date`, the due-date check.
- **DS-04:** the errors and check results of rule 20.
- **Catalogs:** the system account and keys of rule 20 with their TT99 rows; INV-94 to INV-97; the edge cases; `bank_line_unmatched`.
- **Other design items:**
  - DS-14 and the packages: bank statement readers with rule 8's fields;
  - DS-17: step 6 payload tables, the generic CSV statement, and the new events;
  - DS-19: the regime settings and technical account 998;
  - DS-26: the cash book and the presentation of advances;
  - DS-27: voucher prints;
  - DS-30: the cash receipt, cash payment and journal entry screens;
  - DS-34: the bank matching agent;
  - DS-35: complaint events.
- **Open questions:** listed in [open-questions.md](../open-questions.md) under DS-25.

## Revisit when

- Payments are sent from ERPMe (payment files, bank connections).
- Netting across partners, interest on late payment, multi-tier payment discounts, or many-to-many statement matching enter scope.

## Documents updated

- **The lab:** [docs/reviews/2026-11-14-design-validation/](../reviews/2026-11-14-design-validation/README.md): `lab/t08_cash.py`, finding L-16; t01 and t04 fixtures for the DS-06 columns.
- **ADRs:** notes in ADR-0009, ADR-0010, ADR-0011, ADR-0014, ADR-0026, ADR-0041, ADR-0042, ADR-0043 and ADR-0044.
- **Design files:** [docs/design/DS-06-universal-journal.sql](../design/DS-06-universal-journal.sql), [docs/design/DS-04-command-envelope.md](../design/DS-04-command-envelope.md), [docs/design/DS-17-synthetic-dataset.md](../design/DS-17-synthetic-dataset.md), [docs/design/backlog.md](../design/backlog.md).
- **Package:** [DS-19-vietnam-tt99](../design/DS-19-vietnam-tt99/README.md): chart row 998, determination rows and settings.
- **Catalogs:** [system-accounts.csv](../catalogs/system-accounts.csv), [transaction-keys.csv](../catalogs/transaction-keys.csv), [invariants.csv](../catalogs/invariants.csv), [edge-cases.csv](../catalogs/edge-cases.csv), [work-item-kinds.csv](../catalogs/work-item-kinds.csv).
- **Glossary:** [docs/spec/00-reading-guide.md](../spec/00-reading-guide.md).
- **Open questions:** [docs/open-questions.md](../open-questions.md).
- **Index and log:** [docs/adr/README.md](README.md); [docs/runbook/step-log.md](../runbook/step-log.md) at acceptance.
