# Review: compiled spec `agent_runs`

Spec files: `specs/agent_runs-1.md` (R1 to R47, chunk 1), `specs/agent_runs-2.md` (R201 to R257, chunk 2). Reviewer: Claude Sonnet 5.5
(a different model from the compiler), 2026-11-21. Brief: `review-brief.md`. Seed 3206, N=15.

## Verdict

**FAIL (bar 0 BLOCKING and 0 SHOULD-FIX): 0 BLOCKING, 1 SHOULD-FIX, 3 NOTE, 3 SOURCE.** The spec states the current law correctly in all 15
sampled units; the Phase 1 supersession by ADR-0078 and ADR-0055.R7 is folded in without restating old text. One normative clause of
ADR-0050.R22 is dropped (agent_runs-S1). Closing it makes the module pass.

## 1. Lint

`doc_lint.py specs/agent_runs-1.md specs/agent_runs-2.md --module agent_runs`: `LINT PASS findings=0`; units 129, rules 57, notes 71, R-numbers 99,
trace rows 129. Retention 98% and 95% (lowest ADR-0050.R18 47/51, ADR-0050.R55 33/42: dropped removed per-type setting keys and the
superseded `agent_run_stopped` key form, expected). REVIEW LIST: CONFLICT 29, FALSE-POSITIVE 0, OPEN 0. SUPERSEDED RULES: 1
(ADR-0050.R14 by ADR-0055.R7). STABLE-KEY MISMATCHES: 0.

## 2. Seeded spot check (N=15, seed 3206)

Population: 68 source IDs whose trace `Where` holds R-numbers (both files, `ref:` rows excluded).

| # | Source | R-numbers | Verdict |
| --- | --- | --- | --- |
| 1 | ADR-0078.R7.N2 | R213 | FAITHFUL |
| 2 | ADR-0050.R14 (with N1 to N8, ADR-0055.R7, ADR-0078.R5, R6) | R20-R29 | FAITHFUL (modes, effective mode, Phase 1 `off` drop, evidence, `active`, visible drops all match; supersession of the "interim" sentence correct) |
| 3 | ADR-0050.R12.N1 | R10, R11 | FAITHFUL |
| 4 | ADR-0050.R12.N2 | R10, R14 | FAITHFUL (current text from R12.N4 and N6; "until the author decides" correctly not restated) |
| 5 | ADR-0050.R14.N3 | R26 | FAITHFUL (`analysis` exception stated for Phase 1 and Phase 2 apart) |
| 6 | ADR-0029.R14.N1 | R55 | FAITHFUL |
| 7 | ADR-0078.R5 | R241-R244 | FAITHFUL (R241 to R244 together carry every clause: `shadow` refused with `validation_failed`, `agent_mode_not_declared` not reused, gateway mode `live`, assistant and `planning` never `active`, `drift_action`) |
| 8 | ADR-0050.R22.N4 | R41 | FAITHFUL |
| 9 | ADR-0050.R19 | R31-R35 | FAITHFUL (columns match DDL `agent_run_step`; `erased_at` disclosed as interim) |
| 10 | ADR-0050.R55.N2 | R225 | FAITHFUL (see agent_runs-N1 on layout) |
| 11 | ADR-0050.R20.N1 | R36 | FAITHFUL |
| 12 | ADR-0063.R16 | R238-R240 | FAITHFUL (the "partly answered" bullet correctly dropped per R16.N1) |
| 13 | ADR-0050.D0 | R1 | FAITHFUL (every clause present, the stale "shadow-mode metrics" sentence dropped) |
| 14 | ADR-0050.R37 | R220 | FAITHFUL |
| 15 | ADR-0065.R11 | R252, R253, R255, R256 | FAITHFUL (R253 "`assisted` drafts" is from ADR-0078.R6, cited) |

**Error rate: 0 of 15 defects at unit level (0%).** The one dropped clause (S1) is in a unit that is not in the sample; it was found by reading
ADR-0050.R22 whole while checking sample 8.

## 3. SUPERSEDED RULES, CONFLICT and FALSE-POSITIVE

- ADR-0050.R14 superseded by ADR-0055.R7: correct and partial. Only the "interim of ADR-0043 rule 13" sentence is replaced; R24 states ADR-0055.R7
  condition 5 and `approver_is_submitter`.
- All 29 CONFLICT entries read. Resolutions are right (later accepted source by date, then ADR number): ADR-0078 (2026-11-21 notes) over ADR-0050.R14 and
  R22 notes of 2026-11-15/16; ADR-0050.R14.N8 over N4; R22.N3 over R22.N2; R14.N6 over R14 text and N2/N3/N7; ADR-0050.R19.N2 for the key
  `agents.run_step_retention_days`; ADR-0063.R16.N1 closing the open reading. Each statement holds the superseding text.
- Missing entry: none found. The DDL comment "installation row uses the UTC day" is correctly overruled by ADR-0050.R22.N1 and is listed in the
  entries for R22 and R23.
- FALSE-POSITIVE: none.

## 4. Reverse check (seed 3206, 10 R-numbers)

R226, R31, R25, R26, R34, R14, R207, R242, R224, R232: every clause has a source in the cited units. R226 matches ADR-0050.R56 and N1 (the long
list is verbatim in substance); R224 matches the INV-210 to INV-216 text and "INV-217 to INV-219 stay free" of R55.N1; R232 matches ADR-0057.R20 with
ADR-0063.R14. Nothing invented. All backticked identifiers of both files (tables, columns, error codes, settings, work item kinds) were also
searched against the ADR units, DDL and catalogs: all found except those named in SOURCE-1.

## 5. Consistency with design files

- `agent_type_setting`, `agent_run_step`, `agent_promotion_evidence`, `agent_budget_usage` columns and enum values (`off`/`shadow`/`assisted`/`active`,
  `started_by_kind` `human`/`system`, scope kinds, `target_mode`) in the spec match `DS-05-platform.sql`.
- Settings `agents.installation_daily_max_cost`, `agents.company_daily_max_cost`, `agents.internal_reserve_share`, `assist.max_cost_per_run`,
  `agents.run_step_retention_days`, `agents.tainted_reference_reads`, `drift_action`, `wake_up_mode` match `settings.csv` (core defaults, bounds). No per-type
  keys remain in the catalog, as R40 and R209 say.
- INV-210 to INV-216 and INV-642 exist in `invariants.csv`.

## 6. Sections 2, 3, 5 to 8

Spot-read. No invented authorization area, event, error code or setting. Errors R221 equal the ADR-0050.R55 table. Work item kinds R223 equal the rule
plus its note. The `ListAgentRun` and `GetAgentRun` level `read` on leaf `agent` is attributed to ADR-0054.R8 (not re-verified here).

## Findings

### SHOULD-FIX

- **agent_runs-S1** (`agent_runs-1.md:202`, R41; source ADR-0050.R22, "Per installation and day"). DROPPED. The rule says the installation value
  "changes only through installation configuration, never by a company setting or a command, and every change is logged with the operator who made
  it". ADR-0050.R22.N2 replaces the raise path (second operator account) but does not strike this sentence. R41 keeps the operator and
  `setting_value` rows but not "never by a company setting or a command". Fix: add that clause to R41 (or R45).

### NOTE

- **agent_runs-N1** (`agent_runs-2.md:315`). The sentence about `routing_switch`, `llm_provider`, `list_export_max_rows` not being in `settings.csv` is a bare
  line after the settings table and is not tied to a R-number definition (the R225 bullet at line 159 lists them as catalog rows). Fix: fold it into R225.
- **agent_runs-N2** (`agent_runs-1.md:181`, R34). "(spec 17)" is a design-document reference, not an ADR rule; acceptable but a reader cannot trace it.
- **agent_runs-N3** (`agent_runs-1.md:208`, R42). The sentence that the version declares every per-run value as a ceiling and that a company value above it
  returns `setting_out_of_bounds` is, after the removal of the `run_max_*` keys, true only of the company cap; R42 keeps the safe half. No change needed.

### SOURCE findings (do not count against the spec)

- **SOURCE-1** ADR-0050.R55 settings list names `routing_switch`, `llm_provider` and `list_export_max_rows`; `settings.csv` has no row with these keys
  (the spec discloses this).
- **SOURCE-2** `DS-05-platform.sql` comment on `agent_budget_usage.business_date` says the installation row uses the UTC day; ADR-0050.R22.N1 says the
  business date of the company whose run reserves. Fix the comment.
- **SOURCE-3** ADR-0050.R14 is long and keeps superseded text (`GetAgentShadowEvaluation`, mode list of three, "no further mode") in the rule body next
  to notes N5 to N8; the spec folded it correctly, but the ADR itself invites misreading.
