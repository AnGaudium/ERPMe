# Review: compiled spec `registry`

Spec files: `specs/registry-1.md` to `specs/registry-5.md` (R-number blocks R1.., R201.., R401.., R601.., R801.. by chunk). Reviewer: Claude Sonnet 5.5 (a different model from the compiler, Claude Opus),
2026-11-21. Brief: `review-brief.md`. Seed 3205, N=20.

## Verdict

**FAIL (bar 0 BLOCKING and 0 SHOULD-FIX): 0 BLOCKING, 1 SHOULD-FIX, 3 NOTE, 4 SOURCE.** The spec states the current law correctly in 20 of 20
sampled units and 10 of 10 reverse-checked R-numbers; all 36 CONFLICT entries and both SUPERSEDED RULES resolve correctly. One definition
(R32, the request hash) keeps the base-rule wording that two later notes make incomplete. After registry-S1 the module passes.

## 1. Lint

`doc_lint.py specs/registry-[1-5].md --module registry`: `LINT PASS findings=0`; units 193, rules 89 (84 primary), notes 101, R-numbers 248,
trace rows 193. Retention 99% to 100% in every file (two missed identifiers are in ADR-0008 and ADR-0063.R28 and are in other chunks or
dropped history). Sizes 9.0k to 12.6k tokens, all under the hard limit. REVIEW LIST: CONFLICT 36, FALSE-POSITIVE 1, OPEN 0. SUPERSEDED
RULES: 2 (ADR-0008.R5 by ADR-0029.R6; ADR-0063.R29 by ADR-0079.R9). STABLE-KEY MISMATCHES: 0.

## 2. Seeded spot check (N=20, seed 3205)

Population: 169 source IDs whose trace `Where` holds R-numbers (all five files, `ref:` rows excluded).

| # | Source | R-numbers | Verdict |
| --- | --- | --- | --- |
| 1 | ADR-0058.R6 | R426 | FAITHFUL |
| 2 | ADR-0040.R8.N1 | R236 | FAITHFUL |
| 3 | ADR-0043.R9 (N1 to N3) | R258, R259, R260, R261 | FAITHFUL (ten floors; bank floor from N3; gateway exception from N2) |
| 4 | ADR-0050.R30.N2 | R420 | FAITHFUL (all of ADR-0050.R30 N1 to N6 and the rule list match R419 to R421) |
| 5 | ADR-0058.R12 | R427-R429 | FAITHFUL |
| 6 | ADR-0067.R9 | R835-R838 | FAITHFUL |
| 7 | ADR-0063.R29.N17 | R640, R646 | FAITHFUL (narrowed `assist.max_cost_per_run` bounds and removed per-type keys stated in R641, R642) |
| 8 | ADR-0008.R1.N1 | R6 | FAITHFUL |
| 9 | ADR-0008.R19.N1 | R36 | FAITHFUL |
| 10 | ADR-0031.R1 | R218-R222 | FAITHFUL (`checks` key by ADR-0040.R10 in R228) |
| 11 | ADR-0008.R11 | R24 | FAITHFUL |
| 12 | ADR-0050.R27.N4 | R413 | FAITHFUL (N5 decision applied, the author's wider wording not restated) |
| 13 | ADR-0067.R1 | R812, R813 | FAITHFUL |
| 14 | ADR-0006.R5 | R3 | FAITHFUL |
| 15 | ADR-0040.R4.N1 | R233 | FAITHFUL |
| 16 | ADR-0050.R28 | R414, R415 | FAITHFUL (the "flagged, open question" mark dropped under ADR-0063.R16.N1; "(g)" checked in `open-questions.md`) |
| 17 | ADR-0050.R26.N1 | R401 | FAITHFUL |
| 18 | ADR-0067.R13 | R846-R849 | FAITHFUL |
| 19 | ADR-0008.R13.N1 | R28, R29 | FAITHFUL (range narrowed by ADR-0008.R13.N3 to business date or the day before) |
| 20 | ADR-0063.R6.N1 | R621, R622 | FAITHFUL |

**Error rate: 0 of 20 at unit level (0%).** The one SHOULD-FIX (registry-S1) was found beside the sample, in the rule that ADR-0008.R7.N1 and
ADR-0008.R13.N2 amend (the sampled units R7.N1 and R13.N1 trace into R19, R20, R28 to R31).

## 3. SUPERSEDED RULES, CONFLICT and FALSE-POSITIVE

- ADR-0008.R5 superseded by ADR-0029.R6 (partly: only the "before a handler that posts" sentence). R15 states the checks, the policy points of
  ADR-0029.R6 and the `proposal_required` / `tool_not_allowed` order of ADR-0029.R4.N2. Correct. R206 carries the policy points with ADR-0029.R6.N2
  (`Issue` from `draft` always, from `approved` only on a changed hash or another actor kind) and R207 the `origin_run_submit_not_allowed` refusal.
- ADR-0063.R29 superseded by ADR-0079.R9 (partly: only `crm.interaction_retention_days`). R640 and R646 state the catalog as authoritative and
  the registered keys only. Correct.
- All 36 CONFLICT entries read against the sources. The resolutions follow date then ADR number and each statement holds the later text:
  ADR-0008.R7/R13/R14 (envelope fields, `as_of_date` range), ADR-0008.R2 (`tool_not_allowed` first), ADR-0008.R25 and ADR-0063.R29.N2/N14/N15
  (no per-type budget), ADR-0029.R4/R6/R10, ADR-0043.R9 with N1 to N3, ADR-0050.R25/R27/R28 with ADR-0063.R16.N1 and ADR-0050.R27.N5,
  ADR-0040.R4/R8/R12, ADR-0063.R2/R3/R5/R6, ADR-0065.R1, ADR-0067.R6/R18 with ADR-0068.R7, ADR-0063.E.N1 with ADR-0078.R9a. No wrong resolution.
- FALSE-POSITIVE ADR-0063.R2.N1: harmless. "instead of" describes a retry replacing a failed insert; the note defines the order of equal
  `effective_from` rows (R441) and replaces no text of the rule.
- Missing Conflicts entry: one (registry-S1).

## 4. Reverse check (seed 3205, 10 R-numbers)

R824, R401, R845, R227, R231, R835, R253, R259, R817, R625: every clause has a source in the cited units and nothing is imported from another
rule without a citation. All backticked identifiers of the five files that look like tables, columns, error codes, settings and work item kinds
were also searched against the ADR units, DDL and catalogs: none is missing. Leaves named in the files exist in `authorization-areas.csv`
(`operator` is the settings leaf of deployment values, as in `settings.csv`). Columns named in chunk 4 and 5 (`bank_statement_line.bank_transaction_code`,
`lot.best_before_date`, `policy_rule_version.shadow_evidence_outdated_by`, `audit_record.is_review_skipped`, `segregation_exception.kind`,
`setting_value.setup_acknowledgement_id`, `preset_code`, `preset_version`) exist in the DDL.

## 5. Consistency with design files

`setting_value` columns, scope kinds, constraints and the trigger and index names of R437 to R441 match `DS-28-settings.sql`. The seeded preset
values of R827 to R829 match ADR-0067.R6. `assist.max_cost_per_run` bounds 0.01 to 0.5, `agents.*` keys and defaults match `settings.csv`. The
spec's remark that `module_activation` has DDL but no registry rule (chunk 5) is accurate.

## 6. Sections 2, 3, 5 to 8

Spot-read in all five files. No invented authorization area, event, error code or setting. The commands of chunk 5 (`AcknowledgeCompanySetup`,
`RevokeCompanySetupAcknowledgement`, `EvaluateSettingPreset`, `ListSettingPresetItem`, `ListSettingPresetDrift`) match ADR-0067.R4 and R8 (others
not re-read). The UI annotations section of chunk 4 correctly says the chunk holds no floorplan annotation.

## Findings

### SHOULD-FIX

- **registry-S1** (`registry-1.md:170`, R32; source ADR-0008.R15 with ADR-0008.R7.N1, ADR-0008.R13.N2, ADR-0040.R9). The rule says the request hash
  covers the envelope "without `mode` and `expected_plan_hash`"; the notes make `include_canonical_plan` and `is_review_skipped` outside the hash too
  (stated in R19; DS-04 says "Not part of the request hash" for `is_review_skipped`). R32 read alone gives a wrong hash definition, and no CONFLICT entry
  names the difference. Fix: write R32 as "the envelope without `mode`, `expected_plan_hash`, `include_canonical_plan` and `is_review_skipped`" and add
  `CONFLICT ADR-0008.R15: ... ADR-0008.R13.N2 and ADR-0040.R9 govern the fields outside the hash (R19, R30, R32)`.

### NOTE

- **registry-N1** (`registry-4.md:61`, R603). The tail "or on what it set on the setup path" is the compiler's inference (a one-person company can loosen
  only `outdates: none` keys on the setup path, per ADR-0067.R9; `cash.bank_charge.auto_post_ceiling` is `outdates: auto_post` in `settings.csv`, so
  its first raise is not on the setup path). True but stated by no source; consider "or on what it set on the setup path (R604)" to keep the link.
- **registry-N2** (`registry-4.md:210`, R640). "ADR-0063 rules 7 to 27" is the rule's own range; the source's count (51) is not typed, as lint L4 asks. Fine.
- **registry-N3** (`registry-5.md:20`). The "Source finding" sentence about `module_activation` sits in the body of Entities; correct and useful, but it
  is a report to the architect, not law. Consider moving it to the compile report.

### SOURCE findings (do not count against the spec)

- **SOURCE-1** ADR-0008.R15 still lists only `mode` and `expected_plan_hash` as outside the request hash; ADR-0008.R13.N2 and ADR-0040.R9 add two more
  fields in notes elsewhere. Fold them into the rule or add a note on R15.
- **SOURCE-2** The settings-count notes of ADR-0063.R29 disagree (93 in N2, 129 in N16, 135 in N17, 51 in the rule; `settings.csv` holds 143 rows
  with the later additions). Counts in notes go stale; the catalog is authoritative.
- **SOURCE-3** ADR-0063.R29.N14 gives bounds 0.01 to 2 for `assist.max_cost_per_run`, N15 narrows to 0.50 and the catalog holds 0.5; the first note is
  left standing in the ADR.
- **SOURCE-4** ADR-0050.R55 names settings `routing_switch`, `llm_provider` and `list_export_max_rows` that `settings.csv` does not hold (seen in the
  `agent_runs` review; touches this module as owner of the settings catalog).
