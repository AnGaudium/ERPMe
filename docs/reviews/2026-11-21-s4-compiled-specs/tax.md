# Review: compiled spec `tax` (S4 pilot, full review, golden-example candidate)

Spec files: `specs/tax-1.md` (R1 to R80), `specs/tax-2.md` (R201 to R274). Index 30d5706. Reviewer: Claude Opus 5.5
(a different model from the compiler, Claude Fable 5.2), 2026-11-21. Brief: `review-brief.md`.

## Verdict

**FAIL: 0 BLOCKING, 5 SHOULD-FIX, 10 NOTE.** The spec states the current law correctly almost everywhere. All 20
CONFLICT resolutions are right, and the deliberate country-value deviation dropped no core law. The bar is 0/0, so the
module does not pass until the five SHOULD-FIX items are closed. Each one takes a one-sentence edit; after that it can
serve as the golden example.

## 1. Lint

`doc_lint.py specs/tax-1.md specs/tax-2.md --module tax`: `LINT PASS findings=0`; units 90, rules 46, notes 41, R-numbers
154, trace rows 90. Retention 89% in both files. The lowest retention (ADR-0080.R2, ADR-0041.R3, ADR-0053.R10, ADR-0041.R14)
comes from replaced identifiers (partner tax group columns) and dropped `l10n_vn` values. That is expected here, not a
loss. REVIEW LIST: CONFLICT 20, FALSE-POSITIVE 1, OPEN 0. SUPERSEDED RULES: 0. STABLE-KEY MISMATCHES: 0.

## 2. Seeded spot check (N=30, seed 2203)

Population: 80 source IDs whose trace `Where` holds R-numbers (both chunks; `ref:` rows excluded).
`random.Random(2203).sample(sorted(ids), 30)`. For each sampled ID I read the rule with all its notes and the governing units its Conflicts entry names.

| # | Source | R-numbers | Verdict |
| --- | --- | --- | --- |
| 1 | ADR-0053.R5 | R74-R76 | DEFECT (INVENTED generalization in R75): tax-S2 |
| 2 | ADR-0053.R3.N3 | R217 | FAITHFUL |
| 3 | ADR-0041.R3 | R26, R31, R33, R34 | FAITHFUL (partner group replaced per ADR-0080.R2 and R3.N2) |
| 4 | ADR-0041.R8 | R65, R66 | FAITHFUL (the 8% worked example is dropped; it is an `l10n_vn` value) |
| 5 | ADR-0028.R7.N2 | R243 | FAITHFUL |
| 6 | ADR-0080.R4 | R51-R53 | FAITHFUL (header equality qualified by R4.N1, R54) |
| 7 | ADR-0080.D0 | R26, R31, R42, R44, R51 | FAITHFUL |
| 8 | ADR-0041.R13.N2 | R210 | FAITHFUL |
| 9 | ADR-0041.R11.N1 | R203 | FAITHFUL |
| 10 | ADR-0041.R7 | R16, R62-R64 | FAITHFUL |
| 11 | ADR-0053.R3.N2 | R220 | FAITHFUL |
| 12 | ADR-0041.R2 | R15, R17, R20 | FAITHFUL |
| 13 | ADR-0053.R3.N1 | R217 | FAITHFUL |
| 14 | ADR-0041.R6.N1 | R60, R202 | FAITHFUL |
| 15 | ADR-0041.R12 | R201, R205, R206 | FAITHFUL (one minor clause, tax-N4) |
| 16 | ADR-0041.R9 | R67-R70 | FAITHFUL |
| 17 | ADR-0041.R5 | R55 | FAITHFUL (`tax.non_cash_payment_threshold` removed per R5.N1) |
| 18 | ADR-0080.R2 | R31, R33 | FAITHFUL |
| 19 | ADR-0080.R5 | R57, R58 | FAITHFUL (default per R5.N1) |
| 20 | ADR-0027.R8 | R1, R2, R244 | FAITHFUL (one minor drop, tax-N1) |
| 21 | ADR-0080.R6 | R7, R50 | FAITHFUL |
| 22 | ADR-0041.R20 | R72, R73 | FAITHFUL under the CONFLICT reading (SOURCE-1) |
| 23 | ADR-0041.R3.N3 | R31, R33 | FAITHFUL |
| 24 | ADR-0041.R18.N1 | R237 | FAITHFUL |
| 25 | ADR-0041.R4.N2 | R41 | FAITHFUL |
| 26 | ADR-0041.R22.N1 | R80 | FAITHFUL |
| 27 | ADR-0028.R7 | R241-R250 | FAITHFUL |
| 28 | ADR-0051.R20 | R251, R253, R254, R259-R261, R263 | FAITHFUL (importer-only scope replaced per R20.N2) |
| 29 | ADR-0057.R25 | R253, R257, R258, R262-R274 | FAITHFUL |
| 30 | ADR-0051.R20.N2 | R253, R255, R257, R258, R261-R266, R269, R271, R272 | FAITHFUL |

**Error rate: 1 of 30 (3.3%), and it is SHOULD-FIX, not BLOCKING.**

Reverse check: `random.Random(2203).sample(sorted(R-numbers, numeric), 10)` gave R258, R254, R75, R223, R15, R16, R262, R40,
R30 and R217. Eight of the ten are clean. R75 (tax-S2) and R254 (tax-S3) have defects. Nothing in them is imported from an
uncited rule.

## 3. CONFLICT, SUPERSEDED and FALSE-POSITIVE entries (all 21 read against their sources)

The later source wins every time, and every statement holds the superseding text. Entry by entry:

- **ADR-0080 over the partner tax group of ADR-0041** (ADR-0041.D0, R3, R7.N2, R20; ADR-0018.R16.N2; ADR-0041.R3.N1 via
  ADR-0074.R4.N1): right. R26, R27, R31, R33, R34, R62 and R73 read status and treatment. No `partner_tax_group`
  survives as law, and R26 says that it no longer exists. ADR-0080.R2's "everything else of rules 2 to 4 stays" holds:
  R15-R25 and R37-R41 are unchanged.
- **ADR-0041.R3 company rows**: right. N2's `is_adjustable` protection and ADR-0080.R3.N1's precedence replace
  "only for keys with a company-added group" (R34, R35). The company-added-group clause remains as the no-package-row case.
- **ADR-0053 over ADR-0041** (R1 kinds and `e_invoice_label`; R5.N1; R13.N1; R14.N1; R15.N1; R20.N1; R3.N1; R3.N2): right.
  R5 uses the neutral kinds. R13 moves `e_invoice_label` to the add-on, with the draft column staying in DS-19. R56 says the
  threshold is no core key. R208 replaces the old adjustment kinds. R211 replaces `deductible_until_due` with `conditional`.
  R229 uses `condition_failed`/`lapsed`. R217 narrows the overlap. R220 tests in the threshold's currency and drops the
  company-currency comparison and its `regime_configuration_missing`. ADR-0041.R1.N2 (`transaction_key_id`) is in R11.
- **Notes over their rules**: ADR-0018.R16.N1 (effective group, R29), ADR-0080.R5.N1 (no core default, R58; matches
  `settings.csv` core default `fail_closed`), ADR-0080.R4.N1 (manual corrected treatment, R53, R54), ADR-0041.R12.N1 (line
  per role, R205): all right.
- **ADR-0051.R20.N2 with ADR-0057.R25**: right. The quarantine (R262) replaces the flat duplicate refusal and importer-only
  confirmation of R20/R20.N1. So do key conflicts imported rather than refused (R266), confirmation by any holder for a
  mailbox record (R263), and duplicates as an outcome on the mailbox route (R257). ADR-0057 (later ADR number, same date) wins.
- **ADR-0080.R3.N1**: marked CONFLICT, but it is really a refinement: N1 turns R3's insert refusal into early feedback
  and adds the precedence. The text in R46-R48 is right (tax-N6).
- **FALSE-POSITIVE ADR-0041.R2.N2**: harmless. "No longer exists" describes a deleted row, not superseded law.
- **SUPERSEDED RULES**: none listed, none expected.

**Missing Conflicts entries**: one, for ADR-0051.R20.N1's `signature_state` enum (tax-S3). The inline amendments of
ADR-0041.R15 (`none` added, advance or payment-on-account method) are folded correctly and an entry is optional (tax-N7).

## 4. The country-value deviation (R10, R75, R221, R240) and R78

The deviation itself is not a defect: by the chief architect's decision the spec names mechanisms and parameter names but
not `l10n_vn` values. Check that no core law was dropped with the values:

- **R10** (ADR-0041.R1.N1, ADR-0053.R2): the core mechanism is all in R5, R6 and R9: kinds, `package_kind`, the
  `package_kinds.csv` columns, one core kind per package kind, no reuse of a core code, and `base_includes` selection. Only
  the mapping table, the VAT bases and the trade-remedy base question (an `l10n_vn` question) are left to the package. Nothing dropped.
- **R75** (ADR-0053.R5): nothing dropped. Core law is in R74 and R75: `other_tax` determined by tax code,
  `tax_payable_other`, no `environmental_protection_tax` key, and the environmental protection code posting through
  `other_tax`. But R75 turns the TT99 generic row into a statement about every package (tax-S2).
- **R221** (ADR-0053.R3, ADR-0041.R14, R14.N1): nothing dropped. Every core part of the projection is in R211-R220, R222
  and R227: states, transitions, `exempt`/`failing`/`lapse` semantics, advance and credit-note matching, and work items.
  The VND threshold, the per-shipment import rule, box [25] and the legal sources are package values. One parameter
  definition was shortened too far (tax-S4). That cut is unrelated to the deviation.
- **R240** (ADR-0041.R19, R19.N1): the form-code normalization rule (ADR-0004 rule 5) and the dated header are kept; only the
  `01/GTGT` example went. Nothing dropped. The same holds for R236 (boxes [37]/[38] dropped), R13 (labels `0%`, `KCT`,
  `KKKNT`), R65 (8% example), R77 (Vietnamese golden scenarios) and ADR-0041.D0's "Vietnamese content" paragraph.

**R78: yes, both remaining pointers should go.** "154 in TT99" and "the account-141 practice" are `l10n_vn` account numbers,
the very values the decision keeps out of the core. R78 already dropped the parallel "515/635 in TT99" from the Spec 07
reading, so keeping 154 and 141 is inconsistent. ADR-0053.D0 allows labelled examples in core rules, but the
2026-11-21 compile decision is the narrower and later rule for compiled specs. See tax-S1.

## 5. Findings

### SHOULD-FIX

- **tax-S1**, `tax-1.md:299`, R78; source ADR-0053.R14. The source gives the neutral readings with the TT99 account
  numbers 154 and 141. The spec keeps "(e.g. 154 in TT99)" and "the account-141 practice" but dropped "515/635 in TT99" from
  the same rule. **Fix:** write "ADR-0037 rule 8's account number is a labelled `l10n_vn` example of work in process" and
  "the advance-account practice is `l10n_vn`'s reading".
- **tax-S2**, `tax-1.md:288`, R75; source ADR-0053.R5 (and ADR-0015 rule 13). The source states the generic `other_tax`
  row only as a TT99 row of `l10n_vn`. ADR-0015 rule 13 requires that every combination resolves, not that a generic row
  exists. The spec says every package's `other_tax` accounts come "with a generic `other_tax` row". **Fix:** "every tax
  code must resolve (ADR-0015 rule 13); `l10n_vn` does so with a generic `other_tax` row, flagged package content".
- **tax-S3**, `tax-2.md:216`, R254 (with R252, R253); source ADR-0051.R20.N1 against ADR-0051.R20.N2 and ADR-0057 rule 6.
  R254 gives `signature_state` as `passed`, `failed`, `absent`. R253 (from R20.N2) uses a `signer_mismatch` record, a value
  ADR-0057 rule 6 defines (later ADR; DS-36 `document_extraction.signature_state` has it). The spec therefore contradicts
  itself and has no entry. **Fix:** list `signer_mismatch` in R254, citing ADR-0057 rule 6, and add `CONFLICT
  ADR-0051.R20.N1` (or an OPEN if the record's enum is to stay three-valued). See SOURCE-6.
- **tax-S4**, `tax-2.md:98`, R218; source ADR-0053.R3. The source defines `exempt_document_kinds` as "document kinds the
  condition never applies to". The spec names the parameter without its meaning, while every other parameter gets one.
  **Fix:** add "(document kinds the condition never applies to)".
- **tax-S5**, `tax-2.md:309-320`, section 8 (R249, R250); source ADR-0028.R7 and `work-item-kinds.csv`. The table is headed
  "Work item kinds of `tax`" but omits four `tax` rows: `e_invoice_posting_held` (the work item of R249's held delivery),
  `e_invoice_rejected` (R250's work item for the issuer), `e_invoice_date_outside_window` and `e_invoice_outage`. **Fix:**
  add the rows, at least the two R249 and R250 raise, and name them in R249 and R250. The tax dossier did not carry these
  catalog rows (pipeline note, SOURCE-9).

### NOTE

- **tax-N1**, `tax-1.md:43` and `:312`, R2 and INV-411; ADR-0027.R8, R8.N1. R2 drops "DS-33" and N1's "equal ADR-0049's
  turnover (INV-411)". Yet the Invariants line says INV-411 is "named by the ownership note of R2". Add "(INV-411, ADR-0060)"
  to R2 or reword the line.
- **tax-N2**, `tax-1.md:46`, R3; ADR-0053.D0. "specific to Vietnam" becomes "specific to one country". This matches the
  2026-11-21 decision and is acceptable; it is noted because it widens the wording of the source.
- **tax-N3**, `tax-1.md:103`, R20; ADR-0041.R2.N2 (b). The spec drops "except its deactivation fields". The tax DDL has no
  such fields, so the drop is harmless (SOURCE-7).
- **tax-N4**, `tax-2.md:58`, R206; ADR-0041.R12. The spec drops "both carry `tax_code_id`" for the `input_tax_non_deductible`
  line. R205 covers only the transaction-key line.
- **tax-N5**, `tax-2.md:243`, R263; ADR-0051.R20.N1. The spec drops "of a record whose signature did not pass". R262 implies
  it.
- **tax-N6**, `tax-1.md:347-354`. The entries for ADR-0041.R5.N1 and ADR-0041.R7.N2 are keyed on the governing note, not the
  amended rule, and the ADR-0080.R3.N1 entry is a FALSE-POSITIVE in substance. All are harmless.
- **tax-N7**, `tax-2.md:115-127`, R223 and R227; ADR-0041.R15. The rule text amends itself inline (`none` added; advance or
  payment on account). Both are folded correctly with no Conflicts entry. ADR-0041.R8 and R19 have similar spliced sentences.
- **tax-N8**, `tax-1.md:126`, R27. It cites "(ADR-0074.R4)"; the governing text is ADR-0074.R4.N1.
- **tax-N9**, `tax-1.md:129`, R28; ADR-0018.R16. The spec drops "whose basis the author verifies" (the `l10n_vn` list).
  This is acceptable under the decision.
- **tax-N10**, `tax-1.md:277`, R72. Since `partner_tax_groups.csv` is gone, R72 names no file for statuses, treatments
  and treatment rules. The CONFLICT entry says so correctly. A pointer to DS-14 would help a reader (SOURCE-1).

## 6. Consistency with design files

Checked against `DS-05-platform.sql`, `DS-20-master-data.sql`, `settings.csv`, `invariants.csv`, `edge-cases.csv`,
`work-item-kinds.csv`, `authorization-areas.csv`, `transaction-keys.csv` and `system-accounts.csv`. They match: table
keys and unique constraints (`uq_tax_rate_tax_code_id_effective_from`, `uq_tax_matrix_key`, `uq_company_tax_matrix_key`,
`uq_tax_treatment_rule_key`, `ck_tax_code_company_code`); `tax_code` enums; the `tax_rate` columns; `document_line_tax`
columns, including `item_tax_group_source` values; `tax_line_adjustment.kind` values; `initial_deductibility` values;
`document_tax_treatment.source`; the six `tax.*` settings with type, scope and default; INV-300/301/302/303/411/646/97/81;
all EC rows; the eight listed work items; leaves `tax_setup`, `tax_adjustment` and `purchase_invoice`; keys `other_tax`
and `input_tax_non_deductible`; system accounts `tax_payable_other`, `tax_payable_special_consumption` and
`tax_payable_import_export_duty`. Sections 2, 3, 5-8 hold no invented authorization area, event, error code or setting.
"Not stated" cells are honest.

## 7. SOURCE findings (do not count against the spec)

1. ADR-0041 rule 20 has no ADR-0080 note. It still names `partner_tax_groups.csv` and coverage "× applicable partner group".
   DS-14 (lines 118-119) already names `tax_treatments.csv`, `partner_tax_statuses.csv` and `tax_treatment_rules.csv`.
2. ADR-0041.R11 names `tax_line.declaring_unit`; the DDL column is `declaring_branch_id` (null = the company).
3. ADR-0053.R3.N2 names `tax_line.threshold_applied_rate_id`; `tax_line` in DS-05 has no such column.
4. ADR-0041.R13 names `deductible_delta`; the DDL has `deductible_delta_transaction_amount` and
   `deductible_delta_company_amount`, with no ADR-0004 rule 13 note like R6.N1. The DDL also adds `reversal_of_id`, marked
   "interim: not stated in ADR-0041".
5. The six keys of ADR-0041 rule 5 (`tax.rate_date_basis`, `tax.declaration_date_basis`, `tax.rounding_level`,
   `tax.stated_amount_tolerance`, `tax.apportionment`, `tax.return_period`) are missing from `settings.csv`.
6. ADR-0051.R20.N1 gives `signature_state` (`passed`, `failed`, `absent`); ADR-0057 rule 6 adds `signer_mismatch` without a
   note on ADR-0051 rule 20.
7. ADR-0041.R2.N2 (b) says "immutable except its deactivation fields", but no tax table has deactivation fields.
8. In `transaction-keys.csv`, the meaning of `input_tax_non_deductible` still reads "(cash payment above the threshold, a
   lapsed due date, ...)": regime-specific wording in a core catalog (ADR-0053).
9. Pipeline: `dossiers/tax.md` did not carry the four `tax` work-item rows of `work-item-kinds.csv` that tax-S5 names.
