# ADR-0026: Open-item core

Status: accepted (2026-11-14) under ADR-0005, reviewed by Claude Fable 5.2 (builder Claude Opus 5.5). Design item: DS-44 (new, split from DS-25). Related decisions: D5, D10. Principles 5, 6, 9, 13. Build principles B2, B3. ADR-0005, ADR-0006, ADR-0007, ADR-0008, ADR-0009, ADR-0010, ADR-0011, ADR-0014, ADR-0015, ADR-0017, ADR-0019, ADR-0022, ADR-0023, ADR-0025. Assessment finding F2 ([design assessment 1](../reviews/2026-11-14-design-assessment/README.md)).

## Decision

Open items are part of the ledger core, because the step 1 journal already needs them: the journal foreign key and trigger, the step 4 opening balances and invariants, and step 5 invoices and credit checks. Designing them now is technical. Building them from step 1, ahead of DS-25's step 6, changes the build order, which is the author's (open question).

**What an open item is.** One obligation with a partner on one operational account (an invoice installment, a credit, an advance, a payment on account, a loan drawdown), created by exactly one journal line.

**Settlement.** Every later line that settles or adjusts the item refers to it: payments, matching, realized FX, revaluation, reversals. The item's amounts are therefore the sum of its lines; the subledger stays a view over the journal (ADR-0014 rule 17), and the cache on the row serves queries and locking. Lines declare their item effect to the one journal posting interface, so nothing can bypass the cache. Settlement is explicit (the document names the items), partial or full, never above the open amount, and serialized per item.

**Currency.** Open-item accounts always use the `specific` book rate method (interim, flagged); the moving average applies only to balance-level accounts.

DS-25 keeps payments, bank statements, matching UX, netting, payment allocation rules, dunning and write-off processes, all on these interfaces.

### Rules

**The table**

1. An `open_item` holds:

   | Group | Fields |
   | --- | --- |
   | Identity (immutable, by trigger) | `company_id`, `partner_id`, `account_id` (operational, mapped to a system account whose effective control kind is `receivable`, `payable` or `loan`, ADR-0025 rule 4), `open_item_kind`, `natural_side` (`debit`: the partner owes; `credit`: the company owes), `transaction_currency`, `origin_document_id`, `origin_journal_line_id` (unique) |
   | Terms | `installment_number` (information), `payment_term_id`, `document_date`, `posting_date`, `due_date` (required for `invoice` and `credit`, null for `advance`, `payment_on_account` and `loan`), `discount_due_date`, `discount_percent` (one tier; further tiers out of scope) |
   | References | `reference` (the company's own number, e.g. an old invoice number at migration), `partner_reference` (e.g. the supplier's invoice number) |
   | Original amounts | `original_transaction_amount`, `original_company_amount`, `original_group_amount` |
   | Cache | `open_transaction_amount`, `open_company_amount`, `open_group_amount`, `revaluation_company_amount`, `revaluation_group_amount` (sums of open revaluation lines), `is_settled`, `is_reversed`, `last_settlement_date` (the latest posting date of a settling line, recomputed on reversal) |
   | Links | `predecessor_open_item_id` (rule 12) |

   DS-25 attributes such as dunning level, payment block and dispute live in a side table keyed by `open_item_id`, so the core table does not change.
2. `open_item_kind` is a core catalog: `invoice`, `credit` (credit notes and debit notes that reduce an invoice), `advance` (non-monetary per spec 07, excluded from revaluation by kind, ADR-0011 rule 18), `payment_on_account` (money received or paid without an item to settle), `loan` (one per drawdown, ADR-0025), `other`. DS-25 may add kinds; statutory presentation per kind and side is DS-26's (ADR-0010 rule 15), and the meaning of each kind for presentation is the regime's (open question).

**One posting path**

3. Every journal line on an account whose effective control kind is `receivable`, `payable` or `loan` declares its item effect to `ledger.contract.write_journal_entry` (ADR-0022 rule 4):
   - `creates`: kind, due dates, terms, references; the line becomes the item's origin, and its amounts the item's original amounts;
   - `settles`: the item ID; the line has the opposite sign to the item's `natural_side`;
   - `adjusts`: the item ID, for lines that change only company or group amounts (realized FX, revaluation; transaction amount 0);
   - `reverses`: the item ID, for the mirrored lines of a reversal document (rule 11).

   The ledger creates the item (with its ID from `context.new_id`, inserted before the line, which refers to it; the `origin_journal_line_id` foreign key is `DEFERRABLE INITIALLY DEFERRED`), updates the cache under the item lock and writes the plan entries. No other code writes `open_item`; it is a serialized table under ADR-0008 rule 10 (lock helper only, no lock in simulation, CI check). Created items, with kind, due dates and amounts, appear in the plan, so an approval binds to them.
4. A line that refers to an item must match the item's company, partner, account and transaction currency (`open_item_mismatch`, also checked by the journal trigger). Settling in another currency goes through currency exchange clearing (ADR-0011 rule 4), so lines on an item are always in its currency.
5. Installments: a document posts one control-account line per installment, each creating one item; transaction amounts are split by the largest-remainder method, and company and group amounts are rounded per line with the rounding line (ADR-0006 rule 20). A `payment_term` has `code`, `name`, `is_active` and `payment_term_line` rows (`amount_percent`, `due_days`, `due_date_base`: `document_date` or `end_of_month`, optional `discount_percent` and `discount_days`); the percents sum to 100 (`payment_term_invalid`). The document proposes installments from the partner's term (ADR-0019 profiles), editable before posting.

**Settlement**

6. A settlement:
   - locks the item; is rejected when its transaction amount exceeds the open transaction amount, including on a settled item (`open_item_oversettled`);
   - is rejected when it is dated before a revaluation line of the item that has not itself been reversed (`open_item_revaluation_later`: reverse or rerun that revaluation first, ADR-0011 rule 19; interim, flagged). A `reverse_and_repost` revaluation counts as reversed, because the revaluation job posts its reversal, dated the first day of the next period, in the same run;
   - takes the carrying amount as of the settlement's posting date, computed from the item's lines dated on or before it (not the current cache);
   - with `realized_fx_basis` `revalued`: the share settled ÷ open transaction amount of the open company and group amounts including revaluation; with `original` (only meaningful with `delta`, ADR-0011 rule 16): the same share of the amounts excluding revaluation, and the matching share of revaluation is released to the revaluation target in the same entry (interim, flagged);
   - the settlement that settles the item takes exactly what is left, so a settled item has all open amounts zero;
   - realized FX is the settlement's amount in each currency minus the carrying amount leaving, posted through the realized FX keys (ADR-0011 rule 15).
7. Open-item accounts use the `specific` method only; `moving_average` (ADR-0011 rule 15) applies to balance-level accounts such as cash and bank (interim, flagged; open question).
8. Overpayment: the excess of a payment over the items it names is posted by the document as a new `payment_on_account` item (interim, flagged: the business may instead refund or hold). Write-offs and early-payment discounts settle items through the same interface with their own lines; their accounting and approval are DS-25's and the regime's (flagged).
9. Matching items of one partner and account in one currency is an `open_item_matching` document (internal, ADR-0009 rule 19): two lines netting to zero in transaction currency, each settling one item at that item's carrying amount, plus realized FX lines for the difference (flagged). A credit note always creates a `credit` item; applying it to an invoice is always an `open_item_matching`, which the correction document may create in the same command. Who may post a matching (agent draft, policy, human) is DS-28's. Netting across accounts or partners, and across currencies, is DS-25's.
10. Revaluation lines (ADR-0011 rule 19) are `adjusts` lines on items of accounts the regime revalues per open item; accounts revalued per balance carry no item reference on revaluation lines.

**Reversal, moves, loans**

11. Reversal:
    - reversing a document whose items have unreversed settling lines from other documents is rejected (`open_item_settled`); the settlements are reversed first;
    - reversing an untouched origin sets `is_reversed` (the item is neither open nor reported as paid); the same revaluation rule as in rule 6 applies, so a revalued item's revaluation is reversed first;
    - a settlement's reversal mirrors its lines exactly, including realized FX, and restores the cache; shares are never recomputed;
    - an item moved by rule 12 cannot have its origin reversed until the move is reversed.
12. Moving items to another account, e.g. when a partner's reconciliation account changes (ADR-0015 rule 11), is `TransferPartnerOpenItems` (human-only; the verb Transfer is added to the glossary). In one transaction it changes the partner's account and posts `balance_transfer` documents (ADR-0014 rule 3) with one line pair per item, at most 1,000 items per document (ADR-0022 rule 9): each pair settles the old item and creates a new one with the same open and revaluation amounts in all three currencies, terms and `predecessor_open_item_id`, with no realized FX. A reversal is rejected once a new item has settlements. `UpdatePartner` cannot change a reconciliation account while the partner has open items on it (`partner_has_open_items`).
13. Loans: no item exists on a `loan` account before the subledger is activated (ADR-0025 rule 4); afterwards each drawdown creates its own `loan` item, and drawdowns of one contract share its `reference` (refining ADR-0025 rule 3's "one open item per loan contract"). How loans are revalued (per item or per balance) follows the existing open question.

**Locks, queries, general journal**

14. Lock order: partner rows (for the credit check, DS-22), then open item rows ascending ID, after bin rows and before numbering counters (notes in ADR-0022 rule 10 and ADR-0023 rule 10). Two settlements of one item are serialized (PAR-10).
15. Queries:
    - `ListOpenItem`: by partner, account, kind, due date, currency, state, and `as_of` (an item is open on a date when `posting_date <= as_of` and it is not settled or reversed by lines dated on or before it);
    - `GetPartnerExposure` (a computed result, like `GetExchangeRate`): open receivable and payable amounts per partner and currency by kind and due bucket. Open order value is added by DS-22's own query; `ledger` never reads a higher layer.

    Indexes: `(company_id, partner_id)`, `(company_id, account_id)` and `(company_id, due_date)` where neither settled nor reversed; `(origin_document_id)`.
16. `general_journal` lines may declare `creates` or `settles` when the flagged rule on manual journals (ADR-0014 rule 10) allows posting to control accounts; step 1 tests run with that flag on in the test configuration, so the interfaces and invariants are exercised from step 1.

**Placement**

17. Design now; proposed build: step 1 (table, catalog, payment terms, the posting path, matching, queries); step 4 (opening items per invoice, DS-21); step 5 (invoices, credit notes); step 6 (DS-25 processes). The step change is the author's decision.

## Context

- Assessment finding F2: the step 1 journal declares `open_item_id` with a foreign key and a trigger requiring it on receivable and payable lines (ADR-0014 rule 10; DS-06); INV-30..32 start at step 4; opening balances hold AR/AP per invoice at step 4 (spec 15); invoices and the credit limit come at step 5; DS-25 (step 6) was the only owner, and B3 forbids core changes after step 5.
- ADR-0010 rule 15, ADR-0011 rules 15–19 and ADR-0025 depend on the open-item model.
- SAP practice, concepts only: open-item managed reconciliation accounts, one line item per installment, clearing documents, residual items. ERPMe keeps an item record with the journal as the only source of amounts and requires explicit references, so agents never guess.

## Options considered

| Option | For | Against |
| --- | --- | --- |
| Item record per control line, amounts as a cache over its lines (chosen) | Subledger stays a view; explicit references; one posting path | A cache to keep equal (invariant) |
| One item per document with an installment child table | Fewer items | Installment amounts not on lines; INV-33 cannot hold |
| Open item = the journal line itself | No extra table | Journal lines are append-only; due dates and state need a home |
| Separate AR/AP ledger | Familiar | A second book; against ADR-0014 rule 17 |
| Core allocates payments (oldest first) | Convenient | Business behavior; hidden decisions |
| `moving_average` on open-item accounts | Regime freedom | Item caches would not sum; residual rules needed in the core |

## Constraints that come with the decision

- Notes in ADR-0008 rule 10 (serialized table), ADR-0009 rules 3 and 18, ADR-0023 rule 10, ADR-0025 rule 3, ADR-0010 rules 5, 9, 12, 15, ADR-0011 rules 15, 16, 19, ADR-0014 rules 10, 17, ADR-0015 rule 11, ADR-0019 (payment terms), ADR-0022 rule 10.
- DS-06: `open_item`, `payment_term`, `payment_term_line` DDL with named constraints, deferred foreign key, RLS.
- DS-04: errors `open_item_mismatch`, `open_item_oversettled`, `open_item_settled`, `open_item_revaluation_later`, `partner_has_open_items`, `payment_term_invalid`.
- DS-16: INV-33 (cache equals lines in three currencies; settled implies all open amounts zero), INV-34 (no open amount against the natural side), INV-35 (lines match their item), INV-36 (a successor's original and revaluation amounts equal its predecessor's open and revaluation amounts); PAR-10 (two payments on one item); rule 29: naive open items from step 4.
- DS-17: business event `credit_note_issued` (step 5); installments and terms in payloads; edge cases EC-46..52.
- DS-21, DS-22 (installments, credit check composing exposure), DS-25 (scope as in the Decision), DS-28 (who posts matching).
- spec 11 and the runbook: build placement pending the author.

## Revisit when

- Settlement contention on one item measurably limits throughput.
- A regime needs moving-average book rates on open-item accounts.

## Documents updated

- [docs/adr/0008-command-envelope-and-registry.md](0008-command-envelope-and-registry.md), [docs/adr/0009-document-lifecycle.md](0009-document-lifecycle.md), [docs/adr/0010-system-chart-of-accounts.md](0010-system-chart-of-accounts.md), [docs/adr/0011-multi-currency.md](0011-multi-currency.md), [docs/adr/0014-universal-journal.md](0014-universal-journal.md), [docs/adr/0015-account-determination.md](0015-account-determination.md), [docs/adr/0019-partners-and-crm-foundation.md](0019-partners-and-crm-foundation.md), [docs/adr/0022-repository-and-engineering-conventions.md](0022-repository-and-engineering-conventions.md): notes.
- [docs/design/DS-06-universal-journal.sql](../design/DS-06-universal-journal.sql), [docs/design/DS-04-command-envelope.md](../design/DS-04-command-envelope.md), [docs/design/DS-16-invariants-and-harness.md](../design/DS-16-invariants-and-harness.md), [docs/design/DS-17-synthetic-dataset.md](../design/DS-17-synthetic-dataset.md), [docs/catalogs/invariants.csv](../catalogs/invariants.csv), [docs/catalogs/edge-cases.csv](../catalogs/edge-cases.csv), [docs/design/backlog.md](../design/backlog.md).
- [docs/spec/00-reading-guide.md](../spec/00-reading-guide.md): glossary.
- [docs/open-questions.md](../open-questions.md): build placement; book rate method on open-item accounts; overpayment; released revaluation share; kinds for presentation; realized FX on matching; re-pointed DS-25 questions.
- [docs/adr/README.md](README.md); [docs/runbook/step-log.md](../runbook/step-log.md) at acceptance.
