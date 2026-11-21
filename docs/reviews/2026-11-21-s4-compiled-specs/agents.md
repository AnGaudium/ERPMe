# Review: compiled spec `agents` (S4, 8 chunks, full review)

Spec files: `specs/agents-1.md` to `agents-8.md`. Index 30d5706. Compiled by Claude Opus 5.5; reviewer Claude Sonnet 5.5
(a different model), 2026-11-21. Brief: `review-brief.md`.

## Verdict

**FAIL: 0 BLOCKING, 5 SHOULD-FIX, 5 NOTE** (plus 4 SOURCE findings). The spec states the current law faithfully in all 25
spot-checked units and all 10 reverse-checked R-numbers; every CONFLICT resolution I read is right and ADR-0078 is applied
consistently in chunks 1 to 7. The bar is 0/0, so the module does not pass until the five SHOULD-FIX items are closed;
each is a one-sentence edit (a Phase 2 mark or a Conflicts entry), none changes a rule.

## 1. Lint

`doc_lint.py specs/agents-*.md --module agents`: `LINT PASS findings=0`; units 279, rules 145, notes 129, R-numbers 546,
trace rows 279. File sizes 11.1k to 14.0k tokens (limit 16k). Retention 84% to 100%; lowest is agents-7 (84%,
ADR-0064.R23 30/70), where the production settings are in the Settings table instead of backticks in the R-numbers
(checked R1237 to R1243 and the table: values present). REVIEW LIST: CONFLICT 84, FALSE-POSITIVE 0, OPEN 0.
SUPERSEDED RULES: 1 (ADR-0050.R14 by ADR-0055.R7). STABLE-KEY MISMATCHES: 0.

## 2. Seeded spot check (N=25, seed 3204)

Population: 276 source IDs whose trace `Where` holds R-numbers (all chunks, `ref:` rows excluded);
`random.Random(3204).sample(sorted(ids), 25)`. Each read with all notes and the later rules its Conflicts entry names.

| # | Source | R-numbers | Verdict |
| --- | --- | --- | --- |
| 1 | ADR-0050.R31.N2 | R254 | FAITHFUL |
| 2 | ADR-0050.R14.N6 | R71-R73, R77, R78 | FAITHFUL (Phase 2 shadow kept and marked) |
| 3 | ADR-0064.D0 | R1045 | FAITHFUL (the "three agent types" sentence is in R1046; section is headed Phase 2) |
| 4 | ADR-0051.R22.N2 | R651 | FAITHFUL |
| 5 | ADR-0057.R21.N1 | R829, R831 | FAITHFUL |
| 6 | ADR-0050.R14.N8 | R70, R79 | FAITHFUL |
| 7 | ADR-0051.R4.N3 | R410-R412 | FAITHFUL (R4's shadow ladder moved to R413, Phase 2) |
| 8 | ADR-0051.R9.N2 | R425 | FAITHFUL (daily USD 18 / 300 runs dropped by ADR-0078.R7) |
| 9 | ADR-0062.R17 | R1029 | FAITHFUL (interim replaced by R17.N1; section headed Phase 2) |
| 10 | ADR-0050.R15.N3 | R89 | FAITHFUL (budget panel reading from ADR-0078.R7) |
| 11 | ADR-0051.R25.N3 | R664 | FAITHFUL |
| 12 | ADR-0078.R12 | R1453-R1456 | FAITHFUL |
| 13 | ADR-0050.R55 | R440-R444 | FAITHFUL (error table, kinds, INV-210..216, settings, keys by tier) |
| 14 | ADR-0078.R9a | R1416-R1418 | FAITHFUL |
| 15 | ADR-0051.D0 | R401, R402 | FAITHFUL for the text; see agents-S1 for placement of R402 |
| 16 | ADR-0064.R19 | R1225-R1230, R1232 | FAITHFUL (+N1 R1231, N2 R1227) |
| 17 | ADR-0050.R30.N4 | R252 | FAITHFUL |
| 18 | ADR-0064.R20 | R1233, R1234 | FAITHFUL |
| 19 | ADR-0062.R20 | R1030 | FAITHFUL (daily USD 15 / 50 runs replaced by ADR-0078.R7) |
| 20 | ADR-0064.R30 | R1252, R1253 | FAITHFUL |
| 21 | ADR-0050.R55.N3 | R444 | FAITHFUL |
| 22 | ADR-0050.R6 | R21-R23 | FAITHFUL (manifest narrowing from ADR-0078.R6 cited) |
| 23 | ADR-0051.R28 | R674-R679 | FAITHFUL (data migration is Phase 2, section headed so) |
| 24 | ADR-0057.R21 | R828-R831 | FAITHFUL |
| 25 | ADR-0050.R25 | R241, R243-R247 | FAITHFUL |

Error rate: 0 defects in 25 (0%). Nine units sit in sections headed Phase 2 and are correct for that reason; none of
them restates superseded text as law.

## 3. CONFLICT, SUPERSEDED and FALSE-POSITIVE entries

Read: all 84 entries (the lint prints them). Spot-verified against the sources: ADR-0050.R14 and its notes N1 to N8,
ADR-0050.R15, R55 and N1 to N3, ADR-0051.R4, R5, R7, R9 (N2, N4, N5), R28, ADR-0051.R25.N2 and N3, ADR-0064.R1 and N2,
ADR-0062.R17, ADR-0065.R11, ADR-0077.R13 and N1, ADR-0078.R1.N1, R13 and N1. In each, the later accepted unit governs and
the statement holds the superseding text. ADR-0050.R14 "superseded by ADR-0055.R7" is a partial supersession (only the
"approve your own document" interim and the budget values); the spec keeps the rest of R14 as current law (R70 to R79),
which is right. No FALSE-POSITIVE entries; no OPEN entries. One missing entry: agents-S2.

## 4. Reverse check (10 R-numbers, seed 3204)

R50, R54, R65, R261, R677, R845, R876, R1015, R1206, R1251: every clause has a source in the cited units (ADR-0050.R9.N1
and N2, R11, R12.N2/N4/N6, R35, ADR-0051.R28, ADR-0060.R20 and R25.N2, ADR-0062.R8, ADR-0064.R15 and R29). Nothing
invented, nothing imported without a citation. R65's sentence on the quotation agent's `inbound_message_matched` is the
fold of ADR-0050.R12.N4 plus ADR-0078.R2, which the Conflicts list names.

## 5. Consistency with DDL and catalogs

- `assist_request` (the only table `agents` owns): table, purpose, state, `failure_reason` values, key and the
  same-person foreign key in agents-8 match `DS-30-ui.sql` exactly.
- `agent_type_setting.mode` DDL keeps `shadow`, as R70 says; `agent_budget_usage.scope_kind` has the four scopes
  (`company_agent_type`, `company`, `company_outside_content`, `installation`) the spec uses in R233, R234.
- `settings.csv` rows for `agents.company_daily_max_cost` (default 50), `agents.installation_daily_max_cost` (200),
  `agents.internal_reserve_share` (0.40, 0..0.9), `assist.max_cost_per_run` (0.20, 0.01..0.5), `agents.run_step_retention_days`
  and the drift, wake-up and analysis rows match; no `agents.<type>.daily_max_*` or `run_max_*` key remains.
- `work-item-kinds.csv` keys for `agent_budget_exhausted` and `agent_run_stopped` match R442.

## 6. Sections 2, 3, 5 to 8 (spot-read)

No invented authorization area, event, error code or setting found. The Settings tables list only catalog rows; the
"named but absent from `settings.csv`" sentences (`routing_switch`, `llm_provider`, `list_export_max_rows`,
`analysis_question_retention_days`) disclose catalog gaps and are honest.

## 7. ADR-0078 sweep (chunks 1 to 7): statements that still read as live Phase 1 law

Method: grep of chunks 1 to 7 for `shadow`, daily and per-type budget keys, the Phase 2 type names, the production and
advisor terms; each hit read with its section heading. Result: the budget amendment (two tiers, nine keys removed,
`company_agent_type` rows carrying the company cap, open keys by tier) is stated correctly everywhere (R79, R225 to R239,
R424 to R425, R442, R444, R820, R844). The no-live-shadow amendment is stated correctly in R70 to R79, R268, R410 to R416,
R819, R821, R838, R874 to R876, R1035 to R1036; the Phase 2 types sit in sections headed Phase 2
(chunk 3 "Customer onboarding", chunk 4 "Quotation" and "Data migration", chunk 6 "Product engineering" and "Production
agent types", chunk 7 C1 to C8 and the advisor). What is left:

Findings follow in section 8 (SHOULD-FIX agents-S1, S3, S4, S5; NOTE agents-N1, N2). The statements, listed together:

| Where | Statement | Why it reads as Phase 1 law |
| --- | --- | --- |
| agents-3.md R402 (under "Agent types of Phase 1") | what `customer_onboarding`, `quotation`, `data_migration` do | listed beside the Phase 1 types with no Phase 2 mark on the bullets |
| agents-3.md R409 | each workflow states "shadow metrics and promotion" | Phase 1 workflows state evaluation and quality-in-use, not shadow metrics |
| agents-7.md R1265 to R1268 (section "Agents and costing sheets") | the `production` agent type gains `costing_sheet`; the variance agent reads `GetCostCenterAbsorption` | the section heading carries no Phase 2 mark and follows the advisor section |
| agents-7.md R1237 to R1243 and the Settings table (section "Production agent settings") | the production agent, capture, feedback settings | no Phase 2 mark on the section or the table |
| agents-7.md Invariants and Edge cases (INV-730 to INV-741, EC-200 to EC-219, EC-216, EC-217) and agents-6.md INV-730, INV-732, INV-737, EC-216, EC-217 | agent-type invariants and cases with "first step: the production core step" | several test only Phase 2 agent types (capture INV-731 to INV-733, EC-206 to EC-211; sweep EC-201, EC-202; EC-217), but the intro does not split them from the Phase 1 core ones (INV-734, INV-735, INV-739 to INV-741 test deterministic production functions) |
| agents-1.md R60 | "Each workflow module `nativeflows.agents.workflows.<agent_type>` declares" | ADR-0078.R3 puts the declaration in `agents/agent_types/<agent_type>.py` |

Nothing found that restates a removed budget value or the removed live-shadow ladder as current law.

## 8. Findings

### BLOCKING
None.

### SHOULD-FIX

- **agents-S1** (`agents-3.md` R402; source ADR-0051.D0, ADR-0078.R1, R2). The source D0 list of "what the agent types do"
  names six types of which four are Phase 2 (`customer_onboarding`, `quotation`, `data_migration`) or planning; R402 sits
  under "Agent types of Phase 1" and does not mark the three Phase 2 bullets. Fix: add "(Phase 2)" to those three bullets
  or state in R402 that only `bank_matching`, `purchase_invoice` and `planning` of this list are Phase 1.
- **agents-S2** (`agents-1.md` R60, R63; source ADR-0050.R12 and ADR-0078.R3). R60 still says the workflow module
  `nativeflows.agents.workflows.<agent_type>` declares the elements; ADR-0078.R3 puts the one `AgentTypeDeclaration` in
  `agent_types/<agent_type>.py` (R1420 in agents-8 states it). The last sentence of R60 says the elements live in the
  declaration but does not name the changed place, and the Conflicts list has no entry. Fix: add
  `CONFLICT ADR-0050.R12: the declaration lives in agent_types/<agent_type>.py by ADR-0078.R3; the workflow module holds the steps (R60, R1420)` and name the path in R60.
- **agents-S3** (`agents-7.md` R1265 to R1268; source ADR-0072.R18, ADR-0078.R2). The section "Agents and costing sheets"
  has no Phase 2 mark, yet R1265 and R1268 give the `production` and `production_variance` types new reads. Fix: add
  "(Phase 2 agent types, ADR-0078.R2)" to the heading, as the sections around it have.
- **agents-S4** (`agents-7.md` R1237 to R1243 and Settings table; source ADR-0064.R23, ADR-0078.R2). The section
  "Production agent settings" and its table read as Phase 1 settings; the rows `production.agent.*`,
  `production.capture.enabled_sources`, `production.feedback.*`, `production.variance.*` and `production.mes_import.*` are
  used only by Phase 2 agent types or by the production core (`mes_import` is the core's deterministic import, R418).
  Fix: heading "(Phase 2 agent types; `production.mes_import.*` and `production.reservation.*` belong to the Phase 1 core)".
- **agents-S5** (`agents-7.md` Invariants/Edge cases intro; `agents-6.md` INV-730/732/737, EC-216/217; source ADR-0064.R29,
  ADR-0078.R9a). The tables give a Phase 1 look ("day", first step "the production core step") to checks of agent types that
  cannot run in Phase 1. ADR-0078.R9a excludes only six edge cases; chunk 3 and EC-227 apply the exclusion, chunk 7 does not.
  Fix: one sentence per intro naming which rows start from a Phase 2 agent type and are excluded from Phase 1 counts (INV-730
  to INV-733, INV-737, EC-200 to EC-202, EC-206 to EC-211, EC-216, EC-217), and mark the rest as core checks.

### NOTE

- **agents-N1** (`agents-3.md` R409): "shadow metrics and promotion" lists a workflow element that Phase 1 workflows do not
  state; source ADR-0051.R3 says it, so it is not wrong, but add "(Phase 2; Phase 1 states its evaluation set)".
- **agents-N2** (`agents-3.md` R420, last sentence): "In Phase 1 only the golden-set column applies, to the Phase 1 types" is
  a fair reading of ADR-0051.R7.N3, ADR-0078.R6 and R15 but no source states it in those words; cite ADR-0078.R6, R15.
- **agents-N3** (`agents-1.md` R4): "scope resolvers, shadow comparators" import clause is ADR-0050.R1 text; in Phase 1 the
  comparators run on stored output, so say "comparators".
- **agents-N4** (`agents-7.md` R1257): the error code `shadow_evidence_insufficient` is kept for active-promotion evidence
  with no live shadow in Phase 1; correct (ADR-0065.R11) but worth one clause that the code name is historical.
- **agents-N5** (`agents-3.md` R443): "INV-210 and INV-216 use the instant of INV-88" is right for INV-210 and for the
  instant in INV-216 only through `recorded_at`; reword to "the `recorded_at` instant of INV-88".

## 9. SOURCE findings (not counted against the spec)

- **SRC-1** `docs/catalogs/settings.csv`, rows `artifacts.analysis.min_verified_examples` and `...allow_synthetic_only_promotion`:
  the meaning still says "shadow evaluation"; ADR-0078.R6 and ADR-0060.R25.N2 replace it by the daily `RunAnalysisEvaluation`.
- **SRC-2** ADR-0078.R9a excludes six edge cases from Phase 1 counts, but EC-200 to EC-219 (production agents) and
  INV-730 to INV-741 also start from Phase 2 agent types; the ADR and DS-17 do not list them.
- **SRC-3** ADR-0050.R12 and ADR-0078.R3 name two different places for the declaration (`workflows.<agent_type>` and
  `agent_types/<agent_type>.py`); no note on ADR-0050.R12 says which replaces which.
- **SRC-4** `docs/catalogs/settings.csv`: `routing_switch`, `llm_provider` and `list_export_max_rows` are named by
  ADR-0050.R55 but have no row (the spec discloses this in chunks 1, 3 and 8).
