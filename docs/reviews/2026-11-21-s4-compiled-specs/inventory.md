# Review: compiled spec `inventory` (chunks 1 to 7)

Reviewer: Claude Sonnet 5.5 (compiler: Claude Opus 5.5). Date 2026-11-21. Files: `OUT/specs/inventory-1.md` to `inventory-7.md`.
Sources: `REPO/docs/adr/`, `REPO/docs/design/*.sql`, `REPO/docs/catalogs/*.csv`, `OUT/units.jsonl`.

## Verdict

**FAIL: 0 BLOCKING, 2 SHOULD-FIX** (bar: 0 and 0). The late landed cost law (ADR-0021.R6.N2) is stated correctly and the old
law (closed mode, `consumer_split`, `stock_coverage`, the setting, forced receipt period, one-case rule) is not restated as law anywhere.
The two defects are both a sentence that departs from that law in a detail (S1, S2). Spot check error rate: 1 of 20 (5%).

## 1. Lint

`LINT PASS findings=0`; units=362, r_numbers=360, trace_rows=362; stable-key mismatches 0. Retention 96% to 100% per chunk. REVIEW LIST: CONFLICT=63,
FALSE-POSITIVE=0, OPEN=0. SUPERSEDED RULES: 2 (`ADR-0022.R10` and `ADR-0023.R10`, both by `ADR-0027.R10`).
Size: chunk 7 is ~15,366 tokens (limit 16,000, soft target 12,000); chunk 4 ~12,750 (over the soft target only).

## 2. Seeded spot check (N=20, seed 3201, over 241 source IDs with R-numbers in `Where`)

| Source | Where | Verdict |
| --- | --- | --- |
| ADR-0030.R8.N1 | R810 | FAITHFUL |
| ADR-0030.R2 | R804, R805 | FAITHFUL (incl. N1 dating rule, dates verbatim) |
| ADR-0021.R12.N1 | R417, R418 | R418 FAITHFUL; R417 has a defect (S1) |
| ADR-0021.R2 | R229 | FAITHFUL |
| ADR-0023.R6.N2 | R450, R451 | FAITHFUL |
| ADR-0075.R14 | R1276-R1279 | FAITHFUL |
| ADR-0064.R24 | R1213-R1218 | FAITHFUL (cap formula of the later rule, as the Conflicts entry for ADR-0023.R13.N1 says) |
| ADR-0024.R22.N1 | R654 | FAITHFUL |
| ADR-0061.R17.N1 | R1040 | FAITHFUL |
| ADR-0021.R1 | R228 | FAITHFUL (`mode` always `open`, `exchange_rate_difference` added by ADR-0020.R12 notes) |
| ADR-0047.R15 | R1013-R1015 | FAITHFUL |
| ADR-0020.R17.N2 | R224 | FAITHFUL (constraint names match the DDL) |
| ADR-0021.R4 | R231 | FAITHFUL |
| ADR-0006.R21 | R2 | FAITHFUL |
| ADR-0023.R7.N1 | R453, R454 | FAITHFUL (N1 and N3 applied, "if required" replaced) |
| ADR-0020.R11 | R23-R25 | FAITHFUL (R24 step order follows rule + notes N1 to N3; `price_source` values match the DDL) |
| ADR-0028.R2.N1 | R827 | FAITHFUL |
| ADR-0075.R8 | R1264 | FAITHFUL |
| ADR-0023.R18.N3 | R635 | FAITHFUL |
| ADR-0023.R24 | R645 | FAITHFUL ("Proposed" now decided by ADR-0023.R13.N3) |

Error rate: 1 defect (WRONG, S1) in 20 units = 5%.

## 3. Findings

### BLOCKING

None.

### SHOULD-FIX

**inventory-S1** `inventory-3.md:112`, R417 (source ADR-0021.R12, ADR-0021.R12.N1; also ADR-0021.R6.N2 and ADR-0020.R15.N1).
R417 says "and no earlier period is recomputed". The sources say "no locked period is recomputed" and add that a document dated in an earlier period
that is not locked makes that period's costing stale like any backdated document (R233 and R220 of this spec say so). R12.N1 itself says nothing
about recomputation. As written, R417 contradicts R233 for a price-difference document dated in an earlier unlocked period.
Fix: replace "no earlier period is recomputed" with "no locked period is recomputed (R233)".

**inventory-S2** `inventory-6.md:188`, R1029 (source ADR-0047.R21.N1, .N3; ADR-0030.R2.N1).
R1029 says "The value posts in the period of the invoice's posting date, a period that is not locked, whatever the receipt's period". ADR-0047.R21.N3 only
says the difference posts "as the ADR-0021 rule 6 note says", i.e. in the period of the posting date of the document `adjust_receipt_value` writes, and
ADR-0030.R2.N1 (R805) dates that document: the invoice's date; the latest targeted receipt's date when the invoice is earlier; the first day of the first
unlocked period when the invoice's period is locked. So the period is not always the invoice's period, and the invoice's period may be locked.
Fix: write "The value posts in the period of the posting date of that `landed_cost` document (dated as R805 says), whatever the receipt's period".

### NOTE

- **inventory-N1** `inventory-3.md:58`, R401: lists the consumers of the superseded rule 7 in a parenthesis ("sales, consumption, scrap, other issues, count shortages, transfers,
  production") and "no consumer line is written". Harmless as a negation, but it is residue of the old rule; R233 states the law without it. R401 is traced only to
  ADR-0021.R7 and .R7.N1 although its text carries the R6.N2 law (cited in the text); R401, R220, R233, R234 and R21 state the same law four times (simplifier).
- **inventory-N2** `inventory-1.md:43`, R1: "Bills of materials are Phase 1 (`ADR-0032`)" replaces "Phase 2" of ADR-0020.D0 (the rule 12 amendment does say Phase 1). No CONFLICT entry for ADR-0020.D0 (silent, right result).
- **inventory-N3** `inventory-1.md:159`, INV-21: the Statement cell adds a second sentence ("The catalog's flag ... is answered by R22") while the section says statements are those of `invariants.csv`. Move it to a Conflicts entry or R22.
- **inventory-N4** `inventory-6.md:99`, R1011: "closed-short path of R1010 (ADR-0056.R10)". The note says "(rule 10)" without naming the ADR; the closed-short path is in ADR-0047.R13. Citation looks mistaken; check which rule 10 is meant.
- **inventory-N5** `inventory-2.md:56`, R207: "quantity zero (R234)": R234 does not state the zero quantity; the source is the ADR-0020.R12 note (2). Cite R201 or the source ID.
- EC-20 and EC-21 drop the catalog's "Interim, flagged" wording; right, ADR-0047.R22.N4 confirms (R1024, R1026).

## 4. Late landed cost decision (ADR-0021 rule 6 note N2, 2026-11-21): every statement checked

Law checked against: ADR-0021.R6.N2 (posting period = period of the cost document's own posting date, not locked, `open` or `soft_locked`; no locked period
recomputed; nothing to past consumers; never forced into the receipt's period; value-only `receipt_addition` on the target's item and warehouse in that period, in that period's actual average;
(a) to (f) interim cases), R7.N1, R8.N1 (setting and both options removed), R12.N1, R16.N1, ADR-0020.R15.N1, ADR-0020.R12 note (2), ADR-0030.R2.N1, ADR-0047.R13.N3, R21.N3.
Searched all seven chunks for: closed/locked/soft-locked period, consumer split, consumer, stock coverage, closed mode, `closed_period_method`, `receipt_addition`,
late cost, current period, rerun, stale, recompute. Catalog and DDL: no `landed_cost.closed_period_method` row in `settings.csv`, no `consumer_split` or `stock_coverage` anywhere in `docs/catalogs` or `docs/design/*.sql`.

| Statement | Location | New law and nothing of the old? |
| --- | --- | --- |
| R21 (lock helper): a late cost, price difference or exchange-rate difference is a value-only `receipt_addition` in the period of the cost document's own posting date, not locked; no locked period recomputed; nothing to past consumers | inventory-1.md:121 | YES |
| R219: locked periods never recosted; backdated document in an unlocked period makes it stale | inventory-2.md:93 | YES (ADR-0020.R14, consistent with R6.N2) |
| R220: same-period raise; late cost in the posting period, not locked, `receipt_addition`; R215 if no quantity; never forced into the receipt's period | inventory-2.md:96 | YES |
| R207, R217: late addition has quantity zero, joins its posting period's receipts; no quantity base goes to R215 | inventory-2.md:56, 85 | YES (R207 cites R234 for the zero quantity, N5) |
| R233: "follows SAP", posting date's period, `inventory` state not `locked` (`open` or `soft_locked`); posts on its own date whether receipt period is same, earlier unlocked or locked; no recomputation, no past consumer, never forced; earlier unlocked period stale | inventory-2.md:161 | YES, verbatim law |
| R234: allocated amount as value-only `receipt_addition`, debit inventory key, credit source account, via stock lock helper | inventory-2.md:162 | YES |
| R235: `landed_cost_period_mismatch` only for a date earlier than a target's receipt date; a locked posting date is refused by ADR-0012 (interim, case a) | inventory-2.md:167 | YES |
| R236: interim cases (b) to (f); `mode` `open`, `closed` not written | inventory-2.md:170 | YES; `closed` appears only as "not written" |
| R237: price-difference documents are late costs, own posting period, no split range; plan shows `mode` `open` | inventory-2.md:178 | YES |
| R228: `landed_cost_allocation.mode`, every new row `open` | inventory-2.md:132 | YES |
| EC-12 row: current law stated, catalog row noted as predating the decision | inventory-2.md:196 | YES (catalog row is stale: SOURCE-3) |
| R401: no closed mode, no `consumer_split`; posting period; `receipt_addition`; no locked period recomputed; nothing to past consumers | inventory-3.md:58 | YES (consumer list residue, N1) |
| R402: no setting `landed_cost.closed_period_method`, no `consumer_split`, no `stock_coverage`; `settings.csv` has no row; result equals SAP `periodic_average`; no quantity goes to rule 13 | inventory-3.md:61 | YES (named only to say they do not exist) |
| R403: `l10n_vn` seed of the removed setting goes in the package rework; VAS acceptance stays open (DS-11 entry deferred) | inventory-3.md:64 | YES |
| R417: price difference to stock as `receipt_addition` in the posting period of the `adjust_receipt_value` document | inventory-3.md:112 | NO: "no earlier period is recomputed" (S1) |
| R418: exchange-rate difference as `receipt_addition` in the posting period | inventory-3.md:115 | YES |
| R427: landed cost after period close follows R401, closed period not recomputed (`EC-12`) | inventory-3.md:152 | YES |
| R428: earlier-unlocked case and closed-period method answered by the decision | inventory-3.md:155 | YES |
| Settings table note "`landed_cost.closed_period_method` is not a setting (R402)" | inventory-3.md:339 | YES |
| R804: `adjust_receipt_value` documents booked in own posting period, whatever state of receipt period; `receipt_addition`; no recomputation, no past consumers, `consumer_split` does not run, nothing forced back | inventory-5.md:73 | YES |
| R805: posting date of such a document (three cases, verbatim from ADR-0030.R2.N1) | inventory-5.md:76 | YES (the "first unlocked period" wording is the new rule's own, not the old rule 6 range) |
| R1029: price difference to stock, `receipt_addition`, no locked period recomputed, nothing to past consumers | inventory-6.md:188 | NO in one detail: period said to be the invoice's (S2) |
| R1205: return carries its landed cost share; share posts in the period of the cost document as `receipt_addition`; case (c) interim | inventory-7.md:82 | YES |
| R1008 (exchange-rate difference to stock, `receipt_addition` in the clearing posting's period) | inventory-6.md:88 | YES |

CONFLICT entries on this decision, all resolved correctly (superseding text held, old text not restated): ADR-0020.R15 and .R15.N1, ADR-0021.D0, .R1, .R3, .R6, .R6.N1, .R6.N2, .R7, .R7.N1, .R8, .R8.N1, .R12, .R16,
ADR-0030.R1, .R2, .R2.N1, .D0, ADR-0047.R21.N1, .R21.N3, ADR-0063.R24. The entry for ADR-0021.R6.N1 (2026-11-19 confirmation that a locked receipt period goes through consumer split) correctly says it no longer holds.
Result for the decision: **no statement states the old law; two statements (R417, R1029) misstate a detail of the new law.**

## 5. Other CONFLICT entries and superseded rules (sampled beyond the decision)

- `ADR-0022.R10` is traced `ref: ADR-0022.R10` with no restatement; right (superseded, content in `ADR-0027.R10`, R666 states the complete order). `ADR-0023.R10` held as R459, R460: the lock list is replaced by the complete order of ADR-0027.R10 (documents, period rows, task, handling unit, `stock_value`, `stock_quantity`, bins, later classes); reservation and PAR text kept. Correct.
- Checked and right: ADR-0020.R7.N3, ADR-0020.R8, ADR-0020.R10.N1, ADR-0021.R3 (N1 answers the open question), ADR-0021.R9.N1 (reversibility confirmed, R405), ADR-0023.R13.N1 (later ADR-0064.R24 cap), ADR-0023.R18, ADR-0023.R24, ADR-0030.R8.N1.
- No FALSE-POSITIVE entries; no OPEN entries.

## 6. Reverse check (10 R-numbers, seed 3201): R231, R411, R664, R811, R223, R1226, R420, R1, R7, R1011

All clauses have a source in the cited units. R231, R811, R223, R1226, R420, R411, R7 exact. R664: "carry `correction_of_id`" is stated as law (ADR-0027.R7 said "may ... the DS-09 deliverable decides"); right under ADR-0027.R7.N2 and ADR-0047.R7 (Conflicts entry exists). R1: the Phase 1 BOM wording (N2). R1011: citation (N4). Nothing invented.

## 7. Consistency with DDL and catalogs

- Every table in the "Entities and tables" sections of the seven chunks exists in a `CREATE TABLE` of `docs/design/*.sql`; the DDL file named per chunk is right. `landed_cost*` tables are "defined by rule, without DDL" (R228 chunk 2), which is true.
- All 675 backticked snake_case identifiers (error codes, enum values, columns, settings) occur in the ADRs, catalogs or DDL; CamelCase commands and `x.y` functions occur too (three `table.column` forms checked in the DDL).
- All 86 INV and EC rows: names and check points match the catalogs; INV statements match except punctuation and N3; EC descriptions match except the dropped "Interim, flagged" (EC-20, EC-21) and the EC-12 note.
- `preliminary_price` key and `price_source` values, `stock_value` key and the two `valuation_type` CHECKs match the DDL.

## 8. Sections 2, 3, 5 to 8 (spot read)

No invented authorization areas, events, error codes or settings found. Command rows state "not stated" where the sources do. Areas named (`inventory`, leaf `delivery`, `planned_order`, `human_only` for `UpdateWarehouse`, `ReleaseCreditHold`) agree with the ADRs and `authorization-areas.csv` (`delivery` is a document type of `inventory`; `planned_order` a function of `planning`). `ListItemLabel` is a leaf under `product` in ADR-0061 while the spec says "area not stated": acceptable. Settings tables carry only keys that exist in `settings.csv` or are marked as having no row.

## 9. SOURCE findings (not counted against the spec)

- **SOURCE-1** ADR-0021.R12 still carries the old text in its bullets ("split per receipt period; a receipt period that is not open is treated as closed"; "receipts in locked periods get the same treatment (rules 6-8)") with only a later note, no "superseded" mark; same for ADR-0021.R6 table, R7, R8 bodies and ADR-0021 Decision summary, Context, Options (open-questions entry "Landed-cost rebuild" lists these).
- **SOURCE-2** `catalogs/invariants.csv` INV-26 cites "ADR-0021 rules 5, 7, 14"; rule 7 is superseded (open-questions item 6). INV-21 still has the flag text "ADR-0020 rule 10: negative-stock time point" although ADR-0020.R10.N1 says it is answered.
- **SOURCE-3** `catalogs/edge-cases.csv` EC-12 (`landed_cost_after_period_lock`, source "ADR-0021 rules 6-8", events `period_locked`) still describes the pre-decision case; the spec adds the current law in the row.
- **SOURCE-4** ADR-0021.R6.N2 is called "N2" and "the rule 6 note of this date" in different places, while ADR-0021.R6 carries three notes; the translation (a) to (f) is "interim, flagged" for the step 3 spec, so R233 to R237 are law only until that spec confirms.
- **SOURCE-5** ADR-0047.R13.N1 says "(rule 10)" for the closed-short path without naming the ADR (see N4).
