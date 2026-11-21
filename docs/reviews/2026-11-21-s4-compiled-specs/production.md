# Review: compiled spec `production` (chunks 1 to 7)

Reviewer: Claude Sonnet 5.5 (compiler: Claude Opus 5.5). Date 2026-11-21. Files: `OUT/specs/production-1.md` to `production-7.md`.
Sources: `REPO/docs/adr/`, units via `OUT/units.jsonl`, DS-43-54 and other DDL, `REPO/docs/catalogs/*.csv`.

## Verdict

**FAIL: 1 BLOCKING, 0 SHOULD-FIX** (bar: 0 and 0). The spec is of high quality: 24 of 25 spot-check units and 10 of 10
reverse-check R-numbers are faithful, every CONFLICT resolution I read is right, and every table, identifier, setting,
INV, EC and work item kind I compared exists in the DDL and catalogs with matching values. One defect: the interim values
of the costing settings (ADR-0035.R18.N2) are not stated anywhere.

## 1. Lint

`LINT PASS findings=0`. units=313, rules=182, primary_rules=150, notes=121, r_numbers=452, trace_rows=313, STABLE-KEY
MISMATCHES 0. Retention 88% to 100% per chunk (lowest chunk 6, driven by ADR-0064.R23 whose identifiers sit in the
Settings table, not in R-numbers; harmless). REVIEW LIST: CONFLICT=58, FALSE-POSITIVE=0, OPEN=0. SUPERSEDED RULES: 2
(`ADR-0033.R4`, `ADR-0035.R17`).

## 2. Seeded spot check (N=25, seed 3203, over the 259 trace rows whose Where holds R-numbers)

| Source | Where | Verdict |
| --- | --- | --- |
| ADR-0035.R1.N1 | R421 | FAITHFUL |
| ADR-0033.R8 | R45-R48, R50 | FAITHFUL (N1 and N2 folded into R46, R47; N2 checks in R834) |
| ADR-0037.R5.N1 | R647 | FAITHFUL |
| ADR-0035.R15.N3 | R602, R606 | FAITHFUL |
| ADR-0037.R9 | R663, R664 | FAITHFUL |
| ADR-0072.R19 | R1265 | FAITHFUL |
| ADR-0033.R12 | R204-R205 | FAITHFUL (N1, N2 folded) |
| ADR-0072.D0 | R1211 | FAITHFUL |
| ADR-0035.R16 | R607-R609 | FAITHFUL (N3 split between R609 and R610, both right) |
| ADR-0035.R18.N2 | R615, R617, R618 | **DROPPED** (B1) |
| ADR-0035.R6 | R442 | FAITHFUL |
| ADR-0037.R3 | R641, R642 | FAITHFUL (N1: return transit only; correct) |
| ADR-0064.R25 | R1012-R1016 | FAITHFUL (N1 in R1017, R1019) |
| ADR-0034.R3.N2 | R229 | FAITHFUL (N1 and N2 folded) |
| ADR-0064.R22.N1 | R1003 | FAITHFUL |
| ADR-0034.R4.N1 | R230, R231 | FAITHFUL |
| ADR-0071.R5 | R1050, R1051 | FAITHFUL |
| ADR-0033.R11.N2 | R201 | FAITHFUL (plant is the site of the warehouse; no `site_id`; `resource_group_id`) |
| ADR-0046.R14.N4 | R806, R807 | FAITHFUL |
| ADR-0034.R11.N1 | R249 | FAITHFUL (N2: `scrap_reason_id` replaces `reason_code`) |
| ADR-0062.R11 | R824-R826 | FAITHFUL |
| ADR-0071.R13 | R1066 | FAITHFUL (the ADR-0077 rule 22 clause is in the UI annotations, line 378 of `production-6.md`) |
| ADR-0037.R10.N1 | R665 | FAITHFUL |
| ADR-0034.R18.N1 | R430 | FAITHFUL (events and permissions in R429) |
| ADR-0033.R12.N1/N2 | R204-R205 | FAITHFUL |

Spot-check error rate: **1 of 25 (4%)**, one DROPPED, no WRONG, INVENTED or HISTORY.

## 3. Findings

### BLOCKING

**production-B1** (`production-4.md:116-122`, R615; source ADR-0035.R18.N2, also R810 and R458). The note gives the interim
value each regime package seeds until it has a basis: `production.wip_method` = `direct_material`,
`production.abnormal_cost.applies` = true, `production.abnormal_cost.tolerance_percent` = 0,
`production.normal_capacity.applies` = true, `production.co_product_split` = `cost_coefficient`,
`production.estimate_price_basis` = `actual_average`. R615 says "each with an interim value" and lists only the keys;
a grep for `cost_coefficient`, `direct_material`, `actual_average` finds them only as other things (the column, the WIP method
list R447, the price basis option list R458). The Settings section of chunk 4 says the keys are absent from
`settings.csv`, so no table holds the values either. R810 also replaces the source's literal default `actual_average` by
"the value of `production.estimate_price_basis`". Fix: list the six interim values in R615 (key, value), and restore
`actual_average` in R810.

### SHOULD-FIX

None.

### NOTES

- **production-N1** (`production-4.md` R619, source ADR-0035.R18 "Account mapping"): the TT99 mapping numbers (621, 622, 627,
  WIP to 154; TT133 sub-accounts of 154) are dropped, and "TT99 keeps 6325 under 632" (ADR-0035.R19.N1) is dropped from R622.
  They are regime package content and the spec keeps the open point and the owner (DS-19, the author, DS-41); acceptable under
  core neutrality, but say so in one clause if the compiler agrees.
- **production-N2** (`production-1.md` R13, source ADR-0032.R7): the draft wording for spec 10 and spec 11 is shortened (the
  months re-estimate, the "agents done before platform completion gains the planning and production agents" line). The
  planning part is in R12, the production agents are Phase 2. Proposal text only; no law lost.
- **production-N3** (`production-6.md` R1016): the source says the draft "stays for a person with `production_import_review`";
  the spec reads it as the work item kind, which ADR-0064.R29 and the catalog confirm. Right, no change needed.
- **production-N4**: work item kinds `shop_floor_report_extracted` and `subcontract_line_review` (catalog, module `production`)
  appear in no production chunk. The first is the trigger of the capture agent (ADR-0064.R19, R29), whose units are traced
  `ref:`/to agents; the second is not named by any ADR text (see SOURCE-2). R645 says only "creates a work item".

## 4. SUPERSEDED RULES, CONFLICT entries, FALSE-POSITIVE

- `ADR-0033.R4` (superseded by its own text): spec R29 to R32 state the rule as written; the word "superseded" in the source
  (a revision superseded by a new revision) is rendered "withdrawn" in R32. Correct, no later unit replaces it.
- `ADR-0035.R17` (superseded by ADR-0045.R2): R611 to R613 state the rule with the `by_product` price list instead of the
  `by_product_price` table. Correct; N1 folded into R614.
- CONFLICT entries read in full against sources and later rules, all right: ADR-0032.R3, R5, R7 (N2 by N3 and N4, the
  "runbook does not place the planning agent" sentence is dropped), ADR-0033.R3, R4, R6, R11 (N1, N2), R14, R17,
  ADR-0034.R9.N1, R11, R12, R13, ADR-0035.R8, R9.N1, R14, R16, R18, R19, ADR-0037.R3, ADR-0046.R14, ADR-0064.R26.N1/N2
  (N2 governs: same date, higher ADR number), R22, R25.N1, ADR-0065.R20, ADR-0072.R21. The others (ADR-0025.R2, R8,
  ADR-0033.D0, ADR-0034.R17, R21, ADR-0035.R17, ADR-0037.R8, R10, ADR-0062.R12, ADR-0064.R9, R10, ADR-0068.R14,
  ADR-0071.R2, R4, ADR-0072.R3, R10, R18) agree with the units they name; none restates superseded text as law.
- FALSE-POSITIVE: none listed.

## 5. Reverse check (10 R-numbers, seed 3203 over the 452 R-numbers)

R1252, R812, R246, R849, R810, R52, R1065, R1227, R1019, R870: every clause has a source in the cited units. R810 swaps
the literal `actual_average` for the setting (see B1); all others FAITHFUL. R52 correctly adds the lock of R50, which ADR-0033.R9
states as "the same lock".

## 6. Consistency with design files

- Every table of the Entities sections exist in the DDL (checked by script over `docs/design/*.sql`).
- Every backticked snake_case identifier in the spec (outside Trace) occurs in the ADRs, DDL or catalogs; every CamelCase
  command or query name does too; every INV, EC and PAR number exists.
- All INV and EC rows match `invariants.csv` and `edge-cases.csv` in name and statement (differences are only
  backtick formatting); all 34 `production` INV rows of the catalog are in the spec.
- Every `settings.csv` row in the spec match key, scope, default, bounds, direction, leaf and outdates.
- Work item and case kinds in the UI sections match `work-item-kinds.csv` and `work-case-kinds.csv`
  (subject, owner, due, resolution) except the two kinds of N4.
- Movement types and transaction keys (R620, R622, R663, R664) match `movement-types.csv` and `transaction-keys.csv`.
- DDL checks: `operation_confirmation.entry_source` and `external_reference` (R1025), `planning_exception` kinds and
  `production_order_id` (R1024) match.

## 7. Sections 2, 3, 5 to 8 spot-read

No invented authorization area, event, error code or setting found. Commands carry "not stated" where the source is silent.
The Proposed (not law) sections say None. The note on area (`agents` in `settings.csv` against R1004's `production`) is
stated openly in `production-6.md:369`.

## 8. SOURCE findings (do not count against the spec)

- **SOURCE-1** `settings.csv`: `production.agent.readiness_horizon_days` and `production.agent.shortage_candidate_kinds`
  have area `agents`; ADR-0064.R23 gives every key the area of its first segment. The spec states the difference.
- **SOURCE-2** `work-item-kinds.csv` row `subcontract_line_review` cites ADR-0037 rule 4, but ADR-0037.R4 says only "creates
  a work item" and no ADR text names the kind.
- **SOURCE-3** the interim values of ADR-0035.R18.N2 are not in `settings.csv` (the spec says so in chunk 4); `settings.csv`
  has no rows for the six regime keys.
- **SOURCE-4** `shop_floor_report_extracted` is catalog module `production` but ADR-0064.R19 and R29 make it the trigger of the
  agent type `production_capture`; ownership between `production` and `agents` is unclear.
