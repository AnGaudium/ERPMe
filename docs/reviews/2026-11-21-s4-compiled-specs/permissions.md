# Review: compiled spec `permissions` (S4, spot check)

Spec files: `specs/permissions-1.md` to `permissions-4.md` (R1 to R710, linted together). Index 30d5706. Reviewer: Claude Sonnet 5.5
(compiler of chunks 2 and 3: Fable; chunks 1, 4 and integration: Opus). 2026-11-21. Brief: `review-brief.md`.

## Verdict

**FAIL on the bar (0 blocking, 0 should-fix): 0 BLOCKING, 2 SHOULD-FIX, 5 NOTE, 3 SOURCE.** No wrong, dropped or invented
law was found in the 20 sampled units, the 10 reverse-checked R-numbers or the R412 to R426 read. Both should-fix items are small.

## 1. Lint

`LINT PASS findings=0`; units 152, rules 73, notes 75, R-numbers 206, trace rows 152. Retention 90% (chunk 1; lowest
ADR-0017.R5 4/11, ADR-0017.R2 3/5 are the superseded template list and role-name test, so the gap is intended), 100%, 99%, 94%.
REVIEW LIST 35 entries (34 CONFLICT, 1 FALSE-POSITIVE, 0 OPEN). SUPERSEDED RULES 0. STABLE-KEY MISMATCHES 0.

## 2. Seeded spot check (N=20, seed 3207)

Population: 101 source IDs whose trace `Where` starts with R-numbers (`ref:` rows excluded).
`random.Random(3207).sample(sorted(ids), 20)`. 10 of the 20 fall in chunks 1 and 4 (6 and 4). I read each rule whole in
`docs/adr/0017-permission-envelope.md` or `0054-users-roles-and-authorizations.md` with all notes, plus ADR-0067 R16/R17,
ADR-0070 R13/R17, ADR-0063 R14 and ADR-0056/0049 where the text named them.

| # | Source | Chunk | R-numbers | Verdict |
| --- | --- | --- | --- | --- |
| 1 | ADR-0054.R24.N3 | 4 | R673, R674 | FAITHFUL (the odd "at `post` (chief accountant) or `edit`" wording is the source's) |
| 2 | ADR-0017.R3 | 1 | R4, R5 | FAITHFUL (run-token paragraph folded into R5) |
| 3 | ADR-0054.R19 | 3 | R490-R492 | FAITHFUL |
| 4 | ADR-0017.R9.N1 | 1 | R15 | FAITHFUL |
| 5 | ADR-0054.R23 | 4 | R640-R644 | FAITHFUL (command, query and verb lists complete) |
| 6 | ADR-0054.R11.N3 | 3 | R411, R412, R418-R420 | FAITHFUL (see section 3, NOTE N2) |
| 7 | ADR-0054.R7.N2 | 2 | R233 | FAITHFUL |
| 8 | ADR-0054.R5 | 2 | R207 | FAITHFUL |
| 9 | ADR-0054.R11.N2 | 3 | R413, R421 | FAITHFUL (seed replaced by N5/N9 as the Conflicts say) |
| 10 | ADR-0054.R8 | 2 | R236-R241 | FAITHFUL (verb lists identical; N1 `is_internal_only` supersedes the "declare `full`" sentence correctly) |
| 11 | ADR-0017.R7 | 1 | R11 | FAITHFUL |
| 12 | ADR-0017.R14 | 1 | R25 | FAITHFUL (simulate struck, as N1) |
| 13 | ADR-0017.R1 | 1 | R2 | FAITHFUL |
| 14 | ADR-0017.R6.N1 | 1 | R9 | FAITHFUL (narrowed to approval delegation by ADR-0054.R21.N1) |
| 15 | ADR-0054.R18 | 3 | R480-R484 | FAITHFUL (both-kinds path read as the one kind left; `block` exemption of `owner` per R17.N2) |
| 16 | ADR-0054.R7 | 2 | R232-R235 | FAITHFUL (root `quality` verified in `authorization-areas.csv` and ADR-0070 R13/R17) |
| 17 | ADR-0054.R7.N1 | 2 | R233-R235 | FAITHFUL |
| 18 | ADR-0054.R21.N1 | 4 | R620, R622 | FAITHFUL (DDL: `kind IN ('approval')`, no `delegation_role_assignment`) |
| 19 | ADR-0054.R20.N5 | 4 | R604 | FAITHFUL ("interim" dropped correctly: N5 is later) |
| 20 | ADR-0054.R4 | 2 | R221-R227 | FAITHFUL (reset-by-hand text superseded by ADR-0054.R3.N1 / ADR-0076.R7, stated in R220) |

**Error rate: 0 of 20 (0%).**

## 3. Chunk 3 R412 to R426 against ADR-0054.R11 and N1 to N10

Notes in order: N1 production review, N2 general-access / agent seed, N3 flow review, N4 catalog review, N5 simulation review,
N6 UoM, N7 final simulation, N8 ADR-0070 `quality_inspector`, N9 author's delegation (`it_administrator` no agent), N10 ADR-0077.
Every bullet of the rule (approvers, everyone, CRM, run bodies, cashier, print profiles, IT administrator, seeded
conflicts, owner rules, renamed owner rules, interim) and every note appears in R410 to R426 with the right result:

- R411/R419: all levels of N3 match (accountant `partner` `read`, payments `edit` with approval; chief accountant `partner_bank_account` `read`;
  cashier `bank_payment` `post`; `price_list` swap; purchasing manager `purchase_invoice` `edit` with approval). They agree with `role-template-levels.csv`.
- R420: N3 + N4 + N7 levels of `change_proposal` for the seven templates are right.
- R421: N5 seed (`sales_clerk`, `accountant`, `production_planner`, `owner`), `it_administrator` none (N9), `sales_manager`/`chief_accountant` do not hold: right.
  The "interim" mark is dropped because N9 (2026-11-19) confirms the seed; the Conflicts list says so. Correct.
- R422/R423: N6 and N7 complete; the "Interim, flagged" marks the notes carry are kept.
- R424: N10 complete. R425: owner rules; the four kinds exist in `work-item-kinds.csv` with `role:sales_clerk`.
- R426: states the base "Interim" bullet.
- Marks the integrator kept: R412 (`production_planner` in pool `mo`, interim), R419, R422, R423, R426. All have a source mark; none invented. The mark dropped (R421) is justified.

No DROPPED, WRONG, INVENTED or HISTORY defect in R412 to R426.

## 4. CONFLICT, SUPERSEDED and FALSE-POSITIVE entries

All 34 CONFLICT entries read: each resolution is right (later accepted source wins: ADR-0054.R21.N1 over R4/R18/ADR-0017.R6.N1/R2.N1;
ADR-0054.R11.N9 over N2/N5; ADR-0067.R16 over ADR-0017.R16 and ADR-0054.R20; ADR-0017.R19.N4/N5 over N2/N3; ADR-0079.R11 over R24; ADR-0054.R20.N5 over N1),
and each statement holds the superseding text. FALSE-POSITIVE ADR-0054.R11.N4 ("conflicts" = segregation conflicts): harmless.
SUPERSEDED RULES: none. One missing entry: see permissions-S2.

## 5. Findings

### SHOULD-FIX

**permissions-S1.** `permissions-4.md:239`, R695. Source ADR-0054.R25.N2/N3 and `edge-cases.csv` (EC-101 to EC-109, all ADR-0056, rules 9, 11, 14 and others).
The spec says "the catalog now holds `EC-101` and `EC-109` as edge cases of ADR-0056 (its rules 9, 11 and 14)", which reads as two codes and
cites three rules; the catalog holds the nine codes EC-101 to EC-109 (ADR-0056 rules 3, 4, 5, 6, 9, 10, 11, 12, 14, 17, 19). Fix: write "`EC-101` to `EC-109` as edge cases of ADR-0056".

**permissions-S2.** `permissions-4.md:181`, R662, source ADR-0054.R24 (bullet "Backlog DS-15, `on_behalf_of` and segregation for scheduled and e-mail runs").
The source says that person "never approves the run's drafts"; the spec adds "except as R608 allows" (correct law from ADR-0067.R16 for the small-company mode), but
the trace of R662 names only ADR-0054.R24 and the Conflicts section has no entry for that bullet. Fix: add `ADR-0067.R16` to R662's Source line and a CONFLICT entry for the bullet (or drop the exception clause and point to R608 only).

### NOTE

- **permissions-N1.** `permissions-3.md:80`, R412: the list of approving templates omits `quality_inspector` (quality `post` with approval, `edit` on `delegation`, ADR-0054.R11.N8; the catalog row has `can_approve`). R411 states it; harmless.
- **permissions-N2.** `permissions-3.md:101` and `:109`, R419/R420: N3's closing "Interim, flagged" follows the `change_proposal` paragraph; the spec puts the mark on R419 (the flow-review levels) and none on R420. Harmless, since R426 marks all template contents interim.
- **permissions-N3.** `permissions-3.md:98`, R418 cites R434 for "`owner` keeps every permission"; R434 states only the last-owner rule. The source rule 11 also points to rule 12. Harmless.
- **permissions-N4.** `permissions-1.md:107`, R20 names the work item kind `owner_suspended` without a citation; it is sourced (ADR-0054.R3, ADR-0042.R7, `work-item-kinds.csv`) and stated in the UI section of the same chunk.
- **permissions-N5.** `permissions-4.md:17`: the table lists the exception kind `own_document_approval`, which the DDL has and no ADR names; the rule text (R605) correctly names only the two ADR kinds. Disclosed, so not hidden.

### SOURCE findings (not counted against the spec)

- **permissions-SRC1.** ADR-0054.R25.N3 says EC-101 to EC-109 are unused; `edge-cases.csv` and ADR-0056 use all nine. Note needs a correction.
- **permissions-SRC2.** ADR-0054.R11 says every template gets `edit` on `work_queue`; the catalog gives `auditor` only `read` (via `administration` `read`), and N10 says `auditor` stays `read` everywhere. R413 repeats the ADR wording.
- **permissions-SRC3.** `DS-15-access.sql` allows the `segregation_exception` kind `own_document_approval` and marks ADR-0067 kinds "(proposed)"; ADR-0054.R20 names no such kind and ADR-0067 is accepted. Align the DDL comment and decide whether the kind is law.

## 6. Reverse check (10 R-numbers, seed 3207)

`random.Random(3207).sample(sorted(R-numbers), 10)` gave R623, R209, R456, R695, R230, R606, R403, R662, R656, R249.
Each clause has a source in the cited units, except R695 (permissions-S1) and R662 (permissions-S2). R230 (ADR-0040.R12), R456 (ADR-0054.R15.N1), R656 and R249 are faithful.

## 7. Design-file consistency

`DS-15-access.sql`: `integration_client` (unique `code`, `accountable_user_id`), `integration_token` (`token_hash` unique, one-year check),
`installation_role_assignment` (unique `user_account_id, role`), `delegation` (kind `approval` only, state, 366 days inclusive as `end_date - start_date <= 365`),
`segregation_exception` (kinds, `rule_code` set exactly for `pair`), `segregation_review` (unique company + period), `role_permission_hold` and `user_invitation` states all match
what the spec presents. Catalogs: template names, `quality_inspector`, `service_receipt`, `product_unit`/`uom_alias`, configuration and agent-leaf levels,
work item kinds, INV-222/223/228/805 statements agree with `role-template-levels.csv`, `work-item-kinds.csv`, `invariants.csv`. SOURCE items above.

## 8. Sections 2, 3, 5 to 8

Spot-read in all four chunks: no invented authorization area, event, error code or setting. Error codes of R691 equal ADR-0054.R25; settings of R693 equal the source;
"not stated" cells are used where the ADRs are silent.
