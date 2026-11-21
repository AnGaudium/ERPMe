# Review: compiled spec `ledger` (chunks 1 to 3), full pilot review

Reviewer: Claude Opus 5.5 (compiler: Claude Fable 5.2). Date 2026-11-21. Files: `OUT/specs/ledger-1.md`, `ledger-2.md`,
`ledger-3.md` (the `golden/` copies differ only in the `Generated from index` hash, `49ab52f` against `30d5706`).
Sources: `REPO/docs/adr/` at `30d5706` (via `OUT/units.jsonl`; lint STABLE-KEY MISMATCHES 0), DS-06 DDL, catalogs.
The `ledger-part*.md` dossier parts were removed from `OUT/dossier-parts/` while I was reviewing; I read the ADR units directly.

## Verdict

**FAIL: 1 BLOCKING, 6 SHOULD-FIX** (bar: 0 and 0). The rule text of chunk 2 is of high quality. All 12 CONFLICT entries
resolve correctly. The defects are one co-primary table statement that keeps replaced text, two missed confirmations
or decisions, invariant rows that are duplicated and inconsistent across chunks, and one open question that the spec
states as a decision.

## 1. Lint

`LINT PASS findings=0`. units=235, r_numbers=179, trace_rows=235. Retention: 98% (chunk 1), 94% (chunk 2), 99% (chunk 3). Size
ratio: 0.99, 0.96 and 0.86. REVIEW LIST: CONFLICT=15, FALSE-POSITIVE=3, OPEN=0. SUPERSEDED RULES: 1 (`ADR-0026.R14` by
`ADR-0027.R10`, Where R247). My rerun of the lint gives the same output as `specs/ledger.lint.txt`.

## 2. Seeded spot check (N=30, seed 1121, over the 170 trace rows with R-numbers)

| Source | Where | Verdict |
| --- | --- | --- |
| ADR-0067.R7 | R416-R419 | FAITHFUL |
| ADR-0044.R10.N1 | R266 | FAITHFUL |
| ADR-0014.R13.N1 | R56 | FAITHFUL |
| ADR-0049.R22 | R401-R408 | FAITHFUL |
| ADR-0010.R14.N1 | R14 | FAITHFUL |
| ADR-0014.R3 | R44 | FAITHFUL |
| ADR-0041.R15.N1 | R253, R258 | FAITHFUL |
| ADR-0069.R13 | R432 | FAITHFUL |
| ADR-0010.R7 | R7 | FAITHFUL |
| ADR-0015.R12 | R73 | FAITHFUL |
| ADR-0014.R13 | R56 | FAITHFUL |
| ADR-0010.R14 | R14 | FAITHFUL |
| ADR-0025.H.N1 | R209 | FAITHFUL for the note itself ("Phase 2" now reads Phase 1). R209 has a defect from ADR-0025.R2 (B1, found in the full read) |
| ADR-0010.R3 | R3 | FAITHFUL |
| ADR-0010.R19 | R19 | FAITHFUL (open-question pointer dropped, N1) |
| ADR-0011.R13 | R33 | FAITHFUL |
| ADR-0010.R17 | R17 | FAITHFUL |
| ADR-0010.R15 | R15 | FAITHFUL |
| ADR-0015.R5 | R68 | FAITHFUL |
| ADR-0069.R12 | R429-R431 | FAITHFUL |
| ADR-0027.R19 | R265 | FAITHFUL |
| ADR-0026.R10 | R241 | FAITHFUL |
| ADR-0010.R15.N1 | R15 | FAITHFUL |
| ADR-0011.R18 | R38 | FAITHFUL (open-question pointer of .N1 dropped, N1) |
| ADR-0015.D0 | R66, heading | FAITHFUL |
| ADR-0026.R6.N2 | R235 | FAITHFUL |
| ADR-0015.R9 | R70 | FAITHFUL |
| ADR-0006.R20 | R49 | FAITHFUL |
| ADR-0015.R10 | R71 | FAITHFUL |
| ADR-0026.R9.N1 | R234, R236, R238, R239, R242 | **WRONG** (minor): the note confirms rules 2, 6, 8 and 9. The spec applies 6, 8 and 9 but keeps "(open question)" in R225, the rule 2 statement (S1) |

Spot-check error rate: **1 of 30 (3.3%)**.

## 3. Full read of chunk 2 (R201 to R267) against ADR-0025, -0026, -0027, -0035, -0037, -0041, -0044, -0048

I read every rule and note of the listed ADRs that chunk 2 traces, together with the rules they name (ADR-0014.R10 and
its notes, ADR-0032.R4, ADR-0035.R1, R3, R5, ADR-0058.R15, ADR-0049.R14, ADR-0048.R17). Every R-number from R201 to R267
is faithful except R209 (B1) and R225 (S1). R252 is right, but its Conflicts entry is missing (S2).

### CONFLICT entries and the superseded rule (all 12 in chunk 2, 3 in chunk 1)

| Entry | Verdict |
| --- | --- |
| ADR-0025.H.N1 | Right (ADR-0032.R4). |
| ADR-0025.R2 | Right on the owner. Incomplete: it does not cover the columns that ADR-0035.R1 adds (B1). |
| ADR-0025.R3 | Right (ADR-0026.R13: one item per drawdown). |
| ADR-0025.R4 | Right, see Q2 below. |
| ADR-0026.R3 | Right (closing paragraph citing ADR-0047.R6). |
| ADR-0026.R6 | Right on all four points (N1, N3, ADR-0048.R18, R9.N1). |
| ADR-0026.R8 | Right. The second "(flagged)", on write-off and discount accounting, is correctly kept in R238. |
| ADR-0026.R9 | Right. |
| ADR-0026.R11 | Right (R6.N1 covers origin reversals). |
| ADR-0026.R14 (superseded) | Right. Everything R14 lists is in ADR-0027.R10, and the R247 text holds the superseding order. |
| ADR-0027.R11 | Right (N1). |
| ADR-0041.R15 | Right (closing paragraph: `none` and the copied method; N1: `condition_failed` with reason `lapsed`). |
| Chunk 1: ADR-0010.R1.N1, ADR-0014.R7.N1, ADR-0015.R1.N1 | Right. |

FALSE-POSITIVE entries (ADR-0026.R6.N2, ADR-0044.R10.N1, ADR-0011.R18.N2) are all harmless.

### Answers to the compiler's open points

- **Q1: does "confirmed" in ADR-0026.R9.N1 remove the marks?** Yes. The note confirms rules 2, 6, 8 and 9 and names the three
  outcomes: payment on account, FX realized at clearing, revaluation released at clearing. `open-questions.md` line 26 is
  checked as answered. So the marks dropped from R234, R238 and R239 are dropped correctly. R237 rightly keeps
  "(interim, flagged; open question)": rule 7 is not among the confirmed rules, and `open-questions.md` line 138 is still
  open. The confirmation of rule 2 was not applied (S1).
- **Q2: R217, depreciation and WIP close tasks.** Correct. ADR-0035.R3 moves `cost_object` lines to area `inventory` ("Fixed assets and
  loans stay in `general`"). ADR-0035.R5 makes the production part run inside the period-end actual costing job, the
  settlement task. So no WIP close task stays in `general`, and depreciation close tasks (fixed assets) stay there.
- **Q3: `(rule 15)` in ADR-0027.R10.N2.** It is ADR-0058.R15 (the graph check). Its "One at a time" bullet cites "ADR-0027 rule
  10, class 3 note" back. R247's citation "ADR-0058" is right, and the dropped clause is rationale. Citing `ADR-0058.R15` would
  be more precise (optional). The bare "rule 15" in the note is a SOURCE finding (SRC1).
- **Q4: INV "Protects" citing the catalog `source` column.** Acceptable where the protected rule is compiled in another chunk or
  another module (compile brief: cite its source ID). Chunk 2 does this right for its own rules (INV-32 to R234, R236,
  R239, R242). The real problem is duplication and placement across chunks (S3, S4).

## 4. Reverse check (10 R-numbers, seed 1121): R10, R22, R63, R72, R409, R411, R416, R419, R423, R432

All clauses have sources except R411 (S5). R10 replaces ADR-0010.R10's "decided by DS-06 and DS-25" with "follow R53". That is
right, because ADR-0014.R10 and ADR-0048.R15 made the decision later. A Conflicts entry would make it visible (N5).

## 5. Consistency with DDL and catalogs

DS-06 matches chunk 2 on these points:
- the `open_item` columns, `ck_open_item_due_date`, the sign and settled checks, and the four partial indexes;
- the deferred foreign key on `origin_journal_line_id`;
- `payment_term`, `payment_term_line` (with the `due_date_base` values), `subledger_activation`, `fixed_asset`,
  `derivation_trace` and `opening_turnover` (unique on company, account and start date);
- the `journal_line.evidence_method` check and its values.

The catalogs also match:
- `transaction-keys.csv`: the production and subcontracting keys, with alternatives `cost_of_goods_sold;expense_other` and
  `has_regime_alternatives` true;
- `movement-types.csv`: all seven production rows;
- `system-accounts.csv`: the production cost leaves, `receivable_loan` and the control kinds of R219;
- `settings.csv`: `journal.manual_posting_to_control_accounts` (regime, false) and both `ledger.business_unit.*` keys;
- DS-04: all error codes, with `open_item_revaluation_later` marked unused.

Disagreements: the `cost_object` DDL against R209 (B1), plus SRC2 and SRC4.

## 6. Sections 2, 3, 5 to 8

The spec invents no event, error code or setting. Chunk 2 section 3 says no authorization area is stated, but the catalog has the
`ledger`-owned `open_item_matching` (S6). Invariant and edge-case rows are duplicated across chunks (S3).

## Findings

### BLOCKING

- **ledger-B1**: `ledger-2.md:74`, R209. Source `ADR-0025.R2`, read with `ADR-0035.R1` (and `ADR-0025.R8`, `ADR-0032.R4`).
  - Source: `ADR-0035.R1` (later, accepted) gives `cost_object` `kind` (`production_order` or `cost_pool`), `production_order_id` or `cost_center_id`, and `state`. DS-06 creates those columns.
  - Spec: "`fixed_asset` and `cost_object` are stub tables with only `id`, `company_id`, `code` and `name`", which keeps the text that ADR-0035.R1 replaced. The CONFLICT ADR-0025.R2 entry covers only the owner.
  - Fix: limit "stub with only ..." to `fixed_asset`, state that `cost_object` exists from the first migration with its current columns cited as `ADR-0035.R1` (owner `production`), and extend the CONFLICT ADR-0025.R2 entry.

### SHOULD-FIX

- **ledger-S1**: `ledger-2.md:123`, R225. Source `ADR-0026.R2`, `ADR-0026.R9.N1`.
  - Source: the note confirms rule 2. `open-questions.md` line 26 ("which kinds present as advances in statutory reports") is answered: keep rule 2.
  - Spec: keeps "the meaning of each kind for presentation is the regime's (open question)", and the trace of R9.N1 omits R225.
  - Fix: drop "(open question)", add R225 to the R9.N1 trace and Source, and add a CONFLICT ADR-0026.R2 entry, as for rules 6, 8 and 9.
- **ledger-S2**: `ledger-2.md:279-294` (Conflicts), R252. Source `ADR-0026.R17`, `ADR-0026.R17.N1`.
  - Source: the note turns "proposed build ... The step change is the author's decision" into "the proposed build is decided".
  - Spec: R252 applies the decision correctly, but no Conflicts entry records that a mark was dropped. The compile brief requires one, as with R9.N1.
  - Fix: add `CONFLICT ADR-0026.R17: ADR-0026.R17.N1 decides the proposed build order; R252 states it as decided`.
- **ledger-S3**: Invariants and Edge cases across the chunks (`ledger-1.md:275-296`, `ledger-2.md:260-269`, `ledger-3.md:188-228`).
  - Duplicated invariant rows:
    - INV-16 is stated in all three chunks, with Protects "R67, R73" / "ADR-0015.R4" / "ADR-0015.R4, R415";
    - INV-33 and INV-37 in chunks 1 and 2;
    - INV-97 in chunks 2 and 3;
    - INV-01, -03, -04, -05, -06 and -08 in chunks 1 and 3.
  - Other duplicates: EC-03 and EC-05 in chunks 1 and 3; the setting `journal.manual_posting_to_control_accounts` in chunks 1 and 2.
  - Three different table forms are used: no statement; a bullet list; a table with a statement.
  - Compile brief: one row per INV, in the chunk holding the rule its catalog `source` names (INV-16 belongs to chunk 1, which holds ADR-0015.R4 as R67). Chunk 3 claims to list only those that "no rule of chunks 1 and 2 names", but repeats them.
  - This matters doubly in the golden example.
  - Fix: keep one row per INV, EC and setting, in its owning chunk, in one table form (code, check point, one-line statement, Protects).
- **ledger-S4**: `ledger-2.md:266`, INV-37 row. Source `invariants.csv` INV-37 (source ADR-0030 rules 3, 5; flagged "ADR-0030 rule 4: invoice-first valuation").
  - Spec: states only the first clause. It drops "per purchase order line whose received quantity equals its invoiced quantity, net of returns and credit notes, the GR/IR balance in transaction currency is zero" and the flag, and Protects omits ADR-0030.R5.
  - Fix: state the whole catalog statement with its flag, or remove the row (chunk 1 lists INV-37).
- **ledger-S5**: `ledger-3.md:77`, R411. Source `ADR-0053.R5`, `ADR-0053.R17`.
  - Source: "Not renamed here", and ADR-0053.R17 lists neutral names for these keys as an open question.
  - Spec: "keep their names (ADR-0053.R17)", which reads as a decision.
  - Fix: "are not renamed by this rule; neutral names for them are an open question (ADR-0053.R17)".
- **ledger-S6**: `ledger-2.md:28`, section 3. Source `authorization-areas.csv` row `open_item_matching` (finance, document_type, module `ledger`, "ADR-0026 rule 9").
  - Spec: "Authorization areas are not stated by this chunk's sources".
  - Fix: name `open_item_matching` (document type under `finance`) as the area of the matching document of R239, as chunk 1 does for `general_journal` and `balance_transfer`.

### NOTE

- **ledger-N1**: Open-question pointers are dropped while the `unverified` and flagged marks are kept:
  - R38 (employee advance, ADR-0011.R18.N1; `open-questions.md` line 57 still open);
  - R19 (country chart);
  - R33 ("open questions");
  - R209 (production cost collection, now answered in part; the mapping part is kept in R218).
  - No agent would hard-code these values. For a golden example I recommend keeping "(open question)" where the entry is still unchecked.
- **ledger-N2**: `ledger-2.md:204`, R251 cites "the flagged rule on manual journals (R260)". The source cites ADR-0014.R10 (stated in chunk 1 as R53). Prefer "(ADR-0014.R10; R260)".
- **ledger-N3**: `ledger-2.md:40`. The contract line lists `open_item_settled` among the returns of `ledger.contract.write_journal_entry`. The source binds the code to reversing a document (R243), not to the contract. Say "reversal of a document (R243)".
- **ledger-N4**: Catalog counts are dropped without Conflicts entries (ADR-0025.R5 "116 accounts, 98 postable"; ADR-0035.R19 "44"/"46"; ADR-0037.R9 "46"). This is harmless, because of L4 and because R64 and R203 make the catalog authoritative.
- **ledger-N5**: `ledger-1.md:77`, R10 replaces ADR-0010.R10's deferral ("decided by DS-06 and DS-25") with "follow R53". The resolution is right; a CONFLICT ADR-0010.R10 entry would show it.
- **ledger-N6**: `ledger-1.md:157`, R36 restates "the build step is pending the author" from ADR-0011.R16. ADR-0026.R17.N1 (2026-11-19) seems to have decided it for the settlement logic (open-item core and clearing in step 1). See SRC3. Not counted, because the scope of the ADR-0011.R16 phrase is unclear.

## SOURCE findings (not counted against the spec)

- **SRC1**: ADR-0027.R10.N2 (`0027-cross-cutting-ownership.md:140`) says "(rule 15)" inside ADR-0027, where ADR-0027.R15 is about planning. It means ADR-0058 rule 15 and should say so.
- **SRC2**: ADR-0025.R2 (`0025-later-phase-seams.md:28-31`) still says `cost_object` is created "with only `id`, `company_id`, `code` and `name`", with no note pointing to ADR-0035.R1. DS-06 has the ADR-0035.R1 columns, and both stubs also carry `recorded_at`, which ADR-0025.R2 does not list.
- **SRC3**: ADR-0011.R16 says "build step pending the author" for realized FX logic. ADR-0026.R17.N1 has since decided the open-item build, including clearing, in step 1. ADR-0011.R16 needs a note. `open-questions.md` line 55 also says the runbook still names DS-10 for this logic.
- **SRC4**: `transaction-keys.csv` gives `required_control_kind` `cost_object` to `production_consumption`, `production_output` and `production_wip_transfer`. ADR-0035.R19's key table states no control kind (ADR-0037.R9 does, for its keys).
