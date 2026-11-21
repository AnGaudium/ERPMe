# Review: compiled spec of module `sales` (`specs/sales-1.md`, `specs/sales-2.md`)

Reviewer: Claude Opus 5.5 (the compiler was Claude Fable 5.2). Date 2026-11-21. Repository index 30d5706.
Assignment: spot check N=20, seed 3103; plus a full check of the credit-hold rules (ADR-0047.R18 with notes N1 to N5)
and the GR/IR posting formulas (ADR-0047.R21 with notes N1 to N3) against their sources.

**Verdict: FAIL.** 1 blocking, 1 should-fix, 7 notes. Spot-check error rate 0 of 20 (reverse check 0 of 10). The blocking
finding is in the purchase-side posting table that `sales` states as a co-primary rule. It is outside the sample and was
found by the full check of ADR-0047.R21.

## 1. Lint

`doc_lint.py specs/sales-1.md specs/sales-2.md --module sales`: `LINT PASS findings=0`. 118 units, 45 rules, 93 R-numbers,
118 trace rows, all traced. Retention 129/129 (chunk 1) and 146/147 (chunk 2). REVIEW LIST: 12 CONFLICT, 1 FALSE-POSITIVE,
0 OPEN. SUPERSEDED RULES: 1 (ADR-0030.R7 superseded by ADR-0047.R18, Where R3). Stable-key mismatches: 0.

## 2. Seeded spot check (N=20, seed 3103, over the 66 trace rows that have R-numbers)

| Source | R-numbers | Verdict |
| --- | --- | --- |
| ADR-0047.R8 | R33-R36 | FAITHFUL |
| ADR-0047.R3.N2 | R21 | FAITHFUL |
| ADR-0047.R1.N1 | R4, R7, R29 | FAITHFUL (the `l10n_vn` value is named only as package content, as the compile brief requires) |
| ADR-0047.R21.N2 | R224 | FAITHFUL |
| ADR-0047.R6.N2 | R27 | FAITHFUL |
| ADR-0047.D0 | R1 | FAITHFUL (the pricing, GR/IR and credit paragraphs are covered by R37, R3/R203 and the purchasing rules) |
| ADR-0047.R2 | R10-R13, R16, R17 | FAITHFUL |
| ADR-0047.R22.N3 | R230 | FAITHFUL |
| ADR-0047.R3 | R21 | FAITHFUL |
| ADR-0047.R20 | R216-R220 | FAITHFUL (the EC-20 "interim" mark was dropped correctly, per R22.N4) |
| ADR-0047.R20.N1 | R219 | FAITHFUL |
| ADR-0047.R4 | R23, R24 | FAITHFUL |
| ADR-0047.R24 | R238 | FAITHFUL |
| ADR-0047.R19 | R212-R214 | FAITHFUL |
| ADR-0047.R18.N3 | R211 | FAITHFUL (the states match the `ck_credit_hold_state` DDL) |
| ADR-0047.R16 | R37-R40 | FAITHFUL |
| ADR-0074.R4 | R247 | FAITHFUL (with N1) |
| ADR-0047.R23.N2 | R237 | FAITHFUL |
| ADR-0047.R2.N6 | R19 | FAITHFUL |
| ADR-0074.R1 | R242-R244 | FAITHFUL |

Error rate: 0 of 20.

## 3. Full checks in the assignment

### Credit holds: ADR-0047.R18 and notes N1 to N5 (with ADR-0030.R6, R7 and ADR-0048.R19)

All of these are faithful: R2, R3, R201-R211, R230. Each R18 bullet has a statement:
- Exposure: R201.
- At Submit, and approval is the release: R203.
- Holds set in the same transaction: R204. The superseded "single flag" and `set_demand_hold` are gone, per N1.
- Holds updated by a consumer: R206.
- What `inventory` does: R208.
- Release: R209.
- Amendment: R3, plus the CONFLICT entry on ADR-0030.R7.

The notes:
- N1: R204, R205.
- N2: R210.
- N3: R211.
- N4: R202.
- N5: R201, R204.

The flags (rate type, delivery race, consumer window) are kept. The "EC-21/EC-63 interim" clause is dropped correctly, per R22.N4. The `credit_hold` work item row matches `work-item-kinds.csv`.

Two defects. N5 changes the rule without a Conflicts entry (sales-S1). The R22.N4 phrase "other unreleased orders held" is stated in R3 but not in R203 (note 1).

### GR/IR postings: ADR-0047.R21 and notes N1 to N3

- R221 and R222 reproduce the table of R21 row by row.
- R223 states N1 as the general rule of ADR-0021.R12. Its parts:
  - the invoice debit `round(V(I + q)) − round(V(I))` (ADR-0047.R13);
  - `purchase_cost_clearing` when the regime sends `price_difference` to an inventory account. The `transaction-keys.csv` determinant is `valuation_class`, so "for the item's valuation class" is grounded;
  - `adjust_receipt_value` writing a `price_difference` landed cost;
  - the expense alternative.
- N1's Vietnamese accounts and amounts are dropped, as the country-values rule of the compile brief requires.
- N3 replaces the `consumer_split` branch correctly.
- R224 is faithful to N2.

One defect: a later note in ADR-0021 changes the "Purchase invoice, landed cost" row, and R222 still states the old row (sales-B1).

## 4. Superseded rules, CONFLICT and FALSE-POSITIVE entries

| Entry | Judgment |
| --- | --- |
| SUPERSEDED ADR-0030.R7 by ADR-0047.R18 | Right. ADR-0047 (2026-11-15) is later than ADR-0030 (2026-11-14). Only the `PostDelivery` check point is superseded. R3 keeps the Submit check, the lock order and the concurrency clause, and states the hold instead. |
| CONFLICT ADR-0030.R6 | Right (R6.N1, ADR-0074 2026-11-21; R2 is per payer). |
| CONFLICT ADR-0030.R7 | Right. |
| CONFLICT ADR-0047.R1 | Right (R1.N1, R1.N3). |
| CONFLICT ADR-0047.R6 | Right (R29). |
| CONFLICT ADR-0047.R18.N1 | Right (R204, R205). |
| CONFLICT ADR-0047.R18 | Right. |
| CONFLICT ADR-0047.R20 | Right. |
| CONFLICT ADR-0047.R22 | Right. |
| CONFLICT ADR-0047.R23 | Right. |
| CONFLICT ADR-0047.R21.N3 | Right. |
| CONFLICT ADR-0048.R19.N1 | Right (R207). |
| CONFLICT ADR-0074.R4.N1 | Right (R247). |
| FALSE-POSITIVE ADR-0047.R1.N4 | Harmless. The note adds `gr_ir_rounding_clearing`; "reversed" describes the type. |
| (missing) ADR-0047.R18.N5 | See sales-S1. |
| (missing) ADR-0021.R12.N2 against ADR-0047.R21 | See sales-B1. |

## 5. Reverse check (10 R-numbers, `random.Random(3103).sample(sorted(R-numbers, numeric), 10)`)

The draw: R211, R204, R7, R226, R9, R201, R236, R247, R218, R220. Every clause has a source in the cited units. Nothing is invented.

R7's "decided by its localization package" applies R1.N1 together with the compile brief's country-values rule. The source still leaves the question for the author to verify, and R7 keeps that.

## 6. Design files (DDL and catalogs)

Every name the spec presents as existing was found in the design files:

| What the spec names | Where it is |
| --- | --- |
| Tables and columns: party columns, `note`, `custom_values`, `credit_note.reason` and `debit_note.reason` values, `return_reason_id`, `credit_hold` (including the interim `released_order_amount`), `customer_profile.credit_limit` and `receivable_account_id`, `demand_supply_line.hold_reasons`, `document.canceled_reason_id` and `canceled_note`, `document_line_price_step`, `partner_address` UNIQUE key | DDL |
| Error codes and check results | `DS-04-command-envelope.md` |
| `free_goods_issue` | `movement-types.csv` |
| Transaction keys | `transaction-keys.csv` |
| Authorization leaves | `authorization-areas.csv` |
| Verb levels | `authorization-verb-levels.csv` |
| Invariant and edge-case statements | `invariants.csv`, `edge-cases.csv` |

The spec says the setting keys it names are absent from `settings.csv`. That is true (see SOURCE findings).

## 7. Sections 2, 3, 5 to 8

No invented authorization area, event, error code or setting.

Events are "not stated" throughout, which is honest. The authorization of `ReleaseCreditHold` and `GetCreditExposure` is "not stated" (note 4).

## Findings

### Blocking

**sales-B1.** `sales-2.md:122`, R222, row "Purchase invoice, landed cost". Sources: ADR-0047.R21 and ADR-0021.R12.N2 (chief architect, 2026-11-21).
- **What the source says:** the later note adds the company setting `landed_cost.unplanned_cost_treatment` (core default `distribute_to_items`). Under `separate_account`, an unplanned cost invoice line (`line_kind` `landed_cost`) "posts to its own account and never reaches stock or an allocation". Until step 5 that account is determined by the key `purchase_expense` (by item group, or the entered account).
- **What the spec says:** "debit `purchase_cost_clearing`, `input_tax`", with no condition. That is wrong law for a company that chooses `separate_account`.
- **Not the compiler's alone:** no note on ADR-0047.R21 points to the change (SOURCE-5). The same row stands unqualified in `purchasing-2.md` R233 and `inventory-6.md` R1028.
- **Fix:** make the row conditional: `purchase_cost_clearing` under `distribute_to_items`, the account determined by `purchase_expense` (or the entered account) under `separate_account`. Cite ADR-0021.R12.N2 and add `CONFLICT ADR-0047.R21: ...`. Make the same change in the co-primary copies so they stay identical.

### Should-fix

**sales-S1.** `sales-2.md:308-315` (Conflicts); R201, R204. Source: ADR-0047.R18.N5 (ADR-0074, 2026-11-21).
- **What the source says:** the note moves exposure, the hold, `credit_limit` and the set of held demand rows from "the partner" of R18 to the payer (else bill-to, else sold-to). That changes which orders are held. The analogous notes ADR-0030.R6.N1 and ADR-0048.R19.N1 each got an entry.
- **What the spec says:** the statements are right, but there is no Conflicts entry. The template requires one for every superseding note.
- **Fix:** add `CONFLICT ADR-0047.R18.N5: exposure, hold, credit limit and the held demand rows are the payer's, not the order partner's; ADR-0047.R18.N5 governs (R201, R204).`

### Notes

1. `sales-2.md:44`, R203. ADR-0047.R22.N4 says "with the other unreleased orders held". R203 cites N4 but leaves that clause to R204 and R3. Separately, R3 (`sales-1.md:64`) cites ADR-0047.R22.N4 inline, but neither its `Source:` line nor the trace row names it. Add the clause to R203, and add N4 to R3's `Source:` line and trace row.
2. `sales-2.md:131`, R223. The spec says "targeting the receipt line". ADR-0021.R12 says "the matched receipt lines". The spec also says the landed cost moves the difference "into the receipt's stock value"; for a receipt of an earlier period that value is a `receipt_addition` in the posting period. The next sentence already sends that case to the ADR-0021.R6 note, so this is wording only.
3. `sales-2.md:118-119`, R222. The goods receipt and goods invoice rows do not mention the interim planned-delivery-cost accrual of the ADR-0047.R13 note of 2026-11-21. No key exists yet; it is built at step 5. A cross-reference would help.
4. `sales-2.md:26-27`, section 3. The authorization of `ReleaseCreditHold` and `GetCreditExposure` is "not stated". The verb catalog gives `Release` at `post` and `Get` at `read`. R18 asks for "its own permission", and no catalog leaf for it exists. "Not stated" is defensible.
5. `sales-1.md:231`, R40. ADR-0047.R16.N1 adds an exception to R16's re-pricing rule (copied prices). R40 states both. It is arguable whether a Conflicts entry is needed.
6. `sales-1.md:36-43`, section 3. There is no row for `Post` and `Issue` of `sales_invoice`. The sentence on generated verbs covers them.
7. `sales-1.md:72-73`, R4. The entries for posting types omit the "demand and supply" field, which is "—" in the source. Trivial.

## SOURCE findings (do not count against the spec)

- **SOURCE-1.** `edge-cases.csv` EC-20, EC-21, EC-22 and EC-63 still read "Interim, flagged", but ADR-0047.R22.N4 (2026-11-19) confirmed them. The spec discloses this at `sales-2.md:270`.
- **SOURCE-2.** The `credit_hold` comment in `DS-22-09-42-commercial-inventory.sql` (line 331) still names `inventory.contract.set_demand_hold`, superseded by ADR-0047.R18.N1.
- **SOURCE-3.** `credit_hold.partner_id` and `ix_credit_hold_company_id_partner_id` do not say whether the column holds the payer. Since ADR-0047.R18.N5 and ADR-0074.R4, the hold is the payer's.
- **SOURCE-4.** ADR-0030.R7 (lock "the partner row (class 9)") was not updated by ADR-0074, although exposure is now per payer. Take two concurrent orders of different sold-to partners with one payer: they lock different rows, so the EC-63 guarantee ("each sees the other's exposure") does not follow. The lock should name the payer's row.
- **SOURCE-5.** ADR-0021.R12.N2 (`separate_account`) changes the "Purchase invoice, landed cost" row of ADR-0047.R21 without a note on that rule. This is the root of sales-B1.
- **SOURCE-6.** `settings.csv` has no row for these keys:
  - the settings of ADR-0047.R23 and its N1: `sales.reserve_on_approval`, `sales.discount_presentation`, `inventory.purchase_receipt_tolerance_percent`, `purchasing.match.*`, `master_data.default_partner_group.*`;
  - `documents.issuance_without_delay` and `documents.e_invoice_required` (ADR-0053.R8). `authorization-areas.csv` names `documents.issuance_without_delay`.
- **SOURCE-7.** ADR-0047.R22.N4's "other unreleased orders" reuses "unreleased", which ADR-0047.R19.N1 uses for `not_approved` rows. The intended sense is orders without a credit release (R18, "approved orders without a release").
- **SOURCE-8.** No `authorization-areas.csv` leaf exists for the "own permission" of `ReleaseCreditHold` (ADR-0047.R18).
