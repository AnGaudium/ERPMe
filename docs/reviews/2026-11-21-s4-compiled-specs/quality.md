# Review: compiled spec `quality` (S4 pilot, spot check)

Spec file: `specs/quality.md` (whole, R1 to R98). Index 30d5706. Reviewer: Claude Opus 5.5 (a different model from the
compiler, Claude Fable 5.2), 2026-11-21. Brief: `review-brief.md`.

## Verdict

**PASS: 0 BLOCKING, 0 SHOULD-FIX, 4 NOTE.**

## 1. Lint

`doc_lint.py specs/quality.md --module quality`: `LINT PASS findings=0`; units 28, rules 22, notes 4, R-numbers 98, trace
rows 28. Retention 381 of 382 identifiers (100%). REVIEW LIST: 0 entries. SUPERSEDED RULES: 0. STABLE-KEY MISMATCHES: 0.

## 2. Seeded spot check (N=20, seed 2204)

Population: 22 source IDs whose trace `Where` holds R-numbers (`ref:` and `Purpose` rows excluded).
`random.Random(2204).sample(sorted(ids), 20)`. I read each rule whole in `docs/adr/0070-quality-management-core.md`,
including the inline "(review note, 2026-11-21)" amendments, plus the ADR-0075 note on rule 15.

| # | Source | R-numbers | Verdict |
| --- | --- | --- | --- |
| 1 | ADR-0070.R10 | R42-R48 | FAITHFUL |
| 2 | ADR-0070.R11 | R49-R53 | FAITHFUL |
| 3 | ADR-0070.R16 | R81-R86 | FAITHFUL (Cancel also resolves `nonconformance_open`, per the review note) |
| 4 | ADR-0070.R15 | R71-R80 | FAITHFUL (`reason_id` copy, close-at-once review notes kept) |
| 5 | ADR-0070.R18 | R93, R94 | FAITHFUL |
| 6 | ADR-0070.R8 | R32-R38 | FAITHFUL (zero-yield and in-process review notes kept) |
| 7 | ADR-0070.R13 | R62-R66 | FAITHFUL |
| 8 | ADR-0070.R6 | R15 | FAITHFUL |
| 9 | ADR-0070.R14 | R67-R70 | FAITHFUL (one minor drop, quality-N3) |
| 10 | ADR-0070.R15.N1 | R75, R76 | FAITHFUL |
| 11 | ADR-0070.R1 | R1-R6 | FAITHFUL |
| 12 | ADR-0070.R4 | R16-R23 | FAITHFUL |
| 13 | ADR-0070.R12 | R54-R61 | FAITHFUL (disposition table turned into a tight list, complete) |
| 14 | ADR-0070.R20 | R97 | FAITHFUL |
| 15 | ADR-0070.R3 | R12-R14, R98 | FAITHFUL |
| 16 | ADR-0070.R19 | R95, R96 | FAITHFUL |
| 17 | ADR-0070.R21 | R98 | FAITHFUL |
| 18 | ADR-0070.R9 | R39-R41 | FAITHFUL |
| 19 | ADR-0070.R2 | R7-R11 | FAITHFUL |
| 20 | ADR-0070.R17 | R87-R92 | FAITHFUL |

**Error rate: 0 of 20 (0%).** I also read the two units outside the sample, ADR-0070.R5 and R7, and both are faithful.

Reverse check: `random.Random(2204).sample(sorted(R-numbers, numeric), 10)` gave R7, R9, R97, R35, R25, R43, R12, R17, R55
and R47. Every clause has a source in ADR-0070, and nothing is invented.

## 3. CONFLICT, SUPERSEDED and FALSE-POSITIVE entries

None listed, and none missed. The inline review notes of 2026-11-21 in rules 4, 8, 12, 13, 15, 16 and 20 are additions
by the ADR's own author, not amendments of other text, and the spec folds them in. The "new movement type
`quality_sample`" of rule 15 is stated without "new" (R75), which agrees with ADR-0075.D0: the catalog already holds the type.

## 4. Consistency with design files

`DS-58-quality.sql`: all ten tables match, with keys and unique constraints (selection tuple, one draft per plan, `target_table,
target_id`). Columns match too: lot header, lines, executions, results (`entry_source`, `confirmed_by_user_id`,
`test_equipment_id`, `document_extraction_id`) and nonconformance (`version`, actions). `product.inspection_points`
(DS-20), `stock_status` on `return_to_supplier_line`, `scrap_line` and `internal_consumption_line`, and `consumption_kind`
`quality_sample` (DS-22-09-42) exist. Catalogs match: INV-830 to INV-834, EC-280 to EC-287, both `quality.*` settings
with direction, `documents.reason_required.scrap`/`.return` (default true), the five work item kinds, the work case kind
`nonconformance`, leaves `inspection_plan`, `inspection_lot`, `usage_decision` and `nonconformance`, role template
`quality_inspector`, and movement type `quality_sample` (offset `consumption`, 331). Sections 2, 3, 5 to 8 hold no
invented authorization area, event, error code or setting.

## 5. Findings

### NOTE

- **quality-N1**, `quality.md:1`, front matter. `Source ADRs` lists ADR-0027, ADR-0043 and ADR-0075, which appear only as
  `ref:` rows. The compile brief says the field lists the ADRs of units stated as R-numbers, which here is ADR-0070 only.
- **quality-N2**, `quality.md:612-613`, Trace. ADR-0027.R7.N1 and ADR-0043.R4.N2 are traced `ref: ADR-0027.R7` and `ref:
  ADR-0043.R4`. The compile brief asks for the unit's own ID (`ref: ADR-0027.R7.N1`). The lint accepts both forms.
- **quality-N3**, `quality.md:373-376`, R67; ADR-0070.R14. The spec drops "item data released by its own path" for
  `is_auto_accept_allowed`. R22 implies it, since the flag is on the revision, released by `ReleaseInspectionPlanRevision`.
- **quality-N4**, `quality.md:595`, section 8. The `nonconformance_open` resolution cell shows "`CloseNonconformance` or
  `CancelNonconformance`", which agrees with ADR-0070.R16. The catalog names only `CloseNonconformance` (SOURCE-1). The cell
  blends ADR and catalog; it is right on the law.

## 6. SOURCE findings (do not count against the spec)

1. In `work-item-kinds.csv`, `nonconformance_open` has `resolution_command` `CloseNonconformance` only. ADR-0070.R16 (review
   note, 2026-11-21) says `CancelNonconformance` also resolves it.
