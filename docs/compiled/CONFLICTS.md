# Compiled specs: decisions of the chief architect (S4, 2026-11-21)

Status: the compiled specs in this folder are **not yet authoritative**. The ADRs stay law until the author orders the retirement
step. This file lists the cases where the compile or the review needed a decision, and the rules every compile followed. It is
written by the chief architect (ADR-0005 delegation); the author may overturn any entry.

Where the entries are: every `CONFLICT`, `FALSE-POSITIVE` and `OPEN` entry of a spec stands in its `## Conflicts` section, one
line each, naming the governing unit. `tools/docs/doc_lint.py` prints them as its REVIEW LIST. No spec has an `OPEN` entry:
every case could be ordered by date and ADR number, so none needed the author. `tools/docs/lint_all.sh` checks every spec.

## Rules that every compile followed

1. **Later accepted source wins** (date, then ADR number). A note that confirms or replaces its rule is folded in; the old text is
   not restated as law. The history stays in the ADR.
2. **The DDL decides facts about tables.** Where a rule and the DDL differ and no later ADR explains it, the spec states the DDL
   and says so; the difference is a source finding (below), not a choice of the compiler.
3. **The core holds no country values** (the author's rule of 2026-11-21: Vietnam is out of scope). A rule that states values of a
   localization package (accounts, rates, form codes, thresholds, legal references) is compiled as the mechanism and the core keys,
   with the values named flagged package content. Method names and switches that a package seeds (for example
   `direct_material`, `cost_coefficient`, `actual_average` of ADR-0035.R18.N2) are not national values and are stated. English row
   codes of package seed files may stay, labelled package content. `TT99` and `l10n_vn` appear as the name of a package, never as
   a source of values.
4. **A mark "interim" or "flagged" stays** unless a later accepted note confirms the rule. A checked entry in
   `docs/open-questions.md` is not an ADR note: it does not remove a mark by itself.

## Decisions

| # | Case | Decision and reason |
|---|---|---|
| 1 | **Late landed cost** (ADR-0021 rule 6 note N2, the author's decision of 2026-11-21). The specs of `inventory`, `production`, `purchasing`, `sales` and `master_data` state it alike. | A late purchase cost is booked in the period of the cost document's posting date, as a value-only `receipt_addition` that takes part in the actual cost of the recording period. No locked period is recomputed. Nothing is allocated back to past consumers. The setting `landed_cost.closed_period_method` with the options `consumer_split` and `stock_coverage` no longer exists. ADR-0021 rules 7 and 8 and every note that describes the old allocation are superseded; each such unit has a `CONFLICT` entry naming ADR-0021.R6.N2. The cases (a) to (f) of that note stay interim and flagged, as the note says. The independent review of `inventory` checked 24 statements in seven chunks: 22 state the new law only, 2 said "no earlier period" for "no locked period" and a wrong period for a late invoice (fixed). |
| 2 | **Small-company approval of an agent draft** (ADR-0067.R16 of 2026-11-21 against ADR-0055.R7 and `INV-225`). | The later ADR governs. In small-company mode the human-writer part of condition 5 is lifted with a recorded exception. The agent-run part is lifted only when every run that wrote the version was started by an event or a schedule, the version has no effective taint, the approver holds the `owner` or `chief_accountant` template and is eligible for the stage, and the approval is recorded as `own_agent_draft_approval` (`INV-803`). Never lifted: a run the approver started, a tainted version, condition 6. `policy` states it so. The catalog row `INV-225` and ADR-0055.R7 predate it (source finding). |
| 3 | **Suspension of an auto-post rule**: `human_post` (ADR-0063.R10) or `require_human` (ADR-0065.R16, catalog). | ADR-0065.R16 governs: a suspension covers every enabled rule version of the document type; later candidates get `require_human` (`auto_post_evidence_mismatch`). A live `require_human` is stored as `human_only`, and the DDL forces `human_post` true for it, so the two words name one outcome at two layers. `automation`, `policy` and `cash` state it so. |
| 4 | **Agent scope** (ADR-0078, accepted 2026-11-21). | Six Phase 1 agent types; the other types are Phase 2, registered `off` with no workflow code; no live agent shadow in Phase 1 (effective mode `off`); two budget tiers; per-type daily budgets removed. Every statement of an earlier rule in `agents`, `agent_runs`, `registry`, `automation`, `configuration`, `policy` and `production` is current law or sits under a Phase 2 heading with a `CONFLICT` entry. |
| 5 | **Partner tax group** (ADR-0080.R1 over ADR-0018.R16, ADR-0019.R1, ADR-0045.R12, R13, ADR-0041). | The partner tax group no longer exists; `partner_tax_status` and `tax_treatment` replace it (DDL column `partner_tax_status_id`). `master_data`, `tax` and `localization` state it alike. |
| 6 | **Planned-exception reasons** (`planning`, ADR-0024.R21.N1 against the interim DDL check). | The ADR note's list governs; the DDL column is marked interim and holds two values no ADR names. Entered as `CONFLICT` with the reason; the DDL is to be corrected (source finding). |
| 7 | **Landed-cost posting of an unplanned cost** (ADR-0021.R12.N2 against the posting row of ADR-0047.R21). | The row is conditional on the setting `landed_cost.unplanned_cost_treatment`; `sales`, `purchasing` and `inventory` state it alike. |
| 8 | **Interim values a regime package seeds** (ADR-0035.R18.N2, six keys of `production`). | Stated, flagged (see rule 3 above): they are method switches, not legal values. |
| 9 | **`TT99` and `l10n_vn` mentions.** | Kept only as the name of the package. A spec that needed a package value to keep an identifier (the `L11` check) keeps the English seed code, labelled package content. |
| 10 | **Co-primary rules** (a rule primary in two or three modules). | Each module states it in full with identical identifiers and enum lists. Where the integrators found a difference of wording, the fuller side was kept and the difference reported; no difference of law remains known. |

## What a reader must still check

- The lint proves completeness and trace, not meaning. Meaning is covered by a seeded spot check by a different model (20 to 30
  units per reviewed module; 0 to 1 faithful-check defects per sample) and by the integrators' cross-chunk reading. Reviews:
  `reviews/` in the lab folder of the session; the numbers are in `STATE.md` of the lab.
- Six modules own no rule (`api`, `db`, `errors`, `i18n`, `ids`, `sdk`), listed in `SKIP.txt`; `process` is not compiled.
