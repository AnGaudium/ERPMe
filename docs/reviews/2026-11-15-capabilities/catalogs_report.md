# Cross-reference and catalog integrity review — NativeFlows @ 5536f9c (ds-15-access)

Method: scripted checks over `docs/` (excluding `archive/` and `reviews/2026-11-14-design-assessment/`), plus manual reading of flagged spots. Read-only; `/tmp/rv4` on gb10 is deleted and `git status` is clean. Nothing was loaded into PostgreSQL and no lab script was run, so check 12 and the lab counts are static analysis only.

Paths are relative to `~/Projects/NativeFlows/docs/` on gb10 unless they start with `/`.

**Blocking for the simulation:** 2.1, 2.2, 3.1, 12.1–12.4. Everything else is Should-fix or Nit.

## Check 1 — error codes (DS-04: 272 rows, 271 distinct codes)

1.1 **Should-fix** — `design/DS-04-command-envelope.md:206` and `:289`. `revision_released` is listed twice with contradicting class: conflict/409 at 206, precondition/422 at 289. It is the only duplicate code in the table. Fix: delete row 289 and keep one row citing ADR-0033 rule 3 and ADR-0046 rule 4. Pick one class for trigger-held immutability and apply it to `configuration_immutable` (207, conflict/409) and `referenced_line_immutable` (275, precondition/422) as well.

1.2 **Should-fix** — loader errors are cited under "DS-04:" but exist in no catalog (neither DS-04 nor DS-14):
- `regime_setting_in_use`: `adr/0016-localization-package-structure.md:56`, `:102`; `adr/0053-core-neutrality.md:77`, `:265`
- `deductibility_rule_overlap`: `adr/0053-core-neutrality.md:77`, `:265`
- `report_definition_in_use`: `adr/0049-statutory-reporting-and-printing.md:35`, `:304`

Fix: add a "Loader errors" table to DS-14 (or a section in DS-04) and point the three ADR "Documents updated" lines at it.

1.3 **Nit** — outcome codes used as codes without a catalog:
- `adr/0049-statutory-reporting-and-printing.md:304`: `render_failed`, `render_too_large`, `render_output_invalid`
- `adr/0050-agent-runtime-and-query-layer.md:149`: `budget_exceeded`, `time_exceeded`, `output_invalid`, `provider_unavailable`, `resume_diverged`, `crashed`
- `adr/0050-agent-runtime-and-query-layer.md:271`: `replay_diverged`
- `adr/0046-product-configuration.md:93–96`, `:191`: violation codes `configuration_set_conflict`, `configuration_table_no_match`

Fix: one line in DS-04 saying these are enumerations owned by their ADR, not error codes.

1.4 **Nit** — `design/DS-04-command-envelope.md:322–363`. The 42 check-result rows sit in the middle of the error table, and errors resume at 364–392. Fix: move check results to their own table, since ADR-0040 rule 10 calls it "the check-result catalog".

1.5 **Nit** — DS-04 rows whose cited ADR never names the code: `:136` `record_not_found` (cites ADR-0006), `:144` `too_many_decimal_places` (ADR-0006), `:179` `invalid_timestamp` (ADR-0007, the code appears in no ADR), `:395` `timeout` (ADR-0008). Codes never cited outside DS-04: `malformed_request`, `unknown_command_type`, `unknown_field`, `invalid_timestamp`, `internal_error`.

No other defects found here:
- Every code in the error and check-result lists of ADR-0045..0055 exists in DS-04.
- Every `must_reject:<code>` in `edge-cases.csv` exists in DS-04.
- No class, HTTP or retryable mismatch where a code is restated (ADR-0050 rule 55 table and inline restatements compared).
- `bin_management_locked` (`adr/0023-warehouse-management.md:308`) is correctly marked removed.

## Check 2 — INV / EC

2.1 **Blocking for the sim** — production invariants are cited as defined but have no rows in `catalogs/invariants.csv`:
- INV-100..102: `adr/0033-production-master-data.md:185–189`, `:244`
- INV-103..105: `adr/0034-production-orders-and-shop-floor.md:89`, `:246–248`
- INV-106..108: `adr/0035-production-costing.md:227–229`, `:279`
- INV-109, INV-110: `adr/0036-multi-level-mrp.md:42`, `:138–139`
- INV-111, INV-112: `adr/0037-subcontracting.md:100–101`, `:154`
- INV-113..115: `adr/0046-product-configuration.md:195–197`, `:252`; `lab/t06_configuration.py:459` checks "INV-114"

DS-16:57 says only 100–108 are "reserved until the production core step is numbered"; 109–115 are not mentioned there at all. Phase 1 includes production, so 16 invariants are missing. Fix: add the 16 rows (area `production`, `first_step` set to the production core step or a placeholder) and update the DS-16 group text.

2.2 **Blocking for the sim** — stale counts:
- `design/DS-16-invariants-and-harness.md:57`: "Version 0.1.0 has 76 invariants"; the catalog has 114.
- `design/DS-17-synthetic-dataset.md:199`: "Version 0.1.0 has 71 edge cases"; the catalog has 109. The enumeration stops at EC-71 (EC-72..118 unmentioned), and the breakdown at `:200–201` ("23 from 12-testing", "eight that ADRs require") is stale.

2.3 **Should-fix** — DS-16:57 group text has gaps against the catalog:
- 90–99 are unexplained (INV-90..93 commercial, INV-94..97 cash).
- INV-220..231 access block is described only in `adr/0054-users-roles-and-authorizations.md:328`.
- INV-200 and INV-201 are unused and unexplained.
- Area `crm` is used by 6 rows (and area `cash` by 3) but the `area` column list at DS-16:50 omits `crm`.

Unused numbers that are explained elsewhere: 206–209 (ADR-0050:384), 216–219 and 232–239 (ADR-0054:328).

2.4 **Should-fix** — `adr/0054-users-roles-and-authorizations.md:337` says EC-97..109 "follow the reporting block of ADR-0049". EC-99 and EC-100 are CRM rows (ADR-0052), and EC-101..109 do not exist. DS-17 gives no group or gap text for edge cases. Fix: correct the sentence and add a gap note to DS-17 rule 22 (EC-101..109 unused; EC-119..129 free in the ADR-0054/55 block).

2.5 **Should-fix** — catalog rows whose named source ADRs never cite the code. Per-direction check: these rows name an ADR in `source`, but none of the named ADRs mentions the ID.
- INV: 01, 03, 04, 05, 06, 08, 09, 10, 11, 12, 13, 14, 15, 16, 17, 18, 20–32.
- EC: 02–07, 09–18, 23, 24, 28–31, 67, 68, 69, 70, 71, 72, 73, 74, 75, 76, 78, 83.
- Never cited anywhere outside the catalogs: INV-02, 03, 04, 05, 06, 09, 25–29; EC-01–06, 08–19, 23–25, 28–31, 72–76, 78.

EC-69..71 (ADR-0047) and EC-72..76, EC-78 (ADR-0048) are the notable ones: these new ADRs added rows without listing them in their own catalog rule. Fix: add the IDs to ADR-0047 rule 23 and ADR-0048 rule 20 by note.

2.6 **Nit** — rows where one of several source ADRs does not cite the code (ADR in brackets):
- INV-07 [0009], 40 [0009], 57 [0023], 63 [0024], 70 [0014], 80 [0013], 81 [0008], 82 [0009], 92 [0030], 97 [0041], 210 [0013, 0042], 213 [0019], 214 [0038], 215 [0029], 225 [0017], 500 [0019], 501 [0048], 502 [0019], 505 [0009]
- EC-20 [0009], 65 [0041], 66 [0041], 79 [0050], 80 [0019], 82 [0048], 86 [0030], 87 [0051], 88 [0048], 89 [0019], 90 [0019]

2.7 **Nit** — row order:
- `invariants.csv`: INV-94..97 sit after INV-301; INV-49 after INV-215; INV-400..404 after INV-505; INV-231 before INV-230.
- `edge-cases.csv`: EC-99 and EC-100 before EC-92; EC-118 before EC-117.

Fix: sort by code.

2.8 **Nit** — `lab/t12_access.py:44`. The check label says "INV-220 to INV-230 and EC-110 to EC-117"; the catalog also has INV-231 and EC-118.

No duplicate IDs or names, and no malformed IDs.

## Check 3 — work item kinds (42 rows)

3.1 **Blocking for the sim** — `catalogs/work-item-kinds.csv:23` (`agent_task`) and `:29` (`agent_run_stopped`). Owner rule `run_on_behalf_of` is defined nowhere: not in ADR-0042 rule 7 (`adr/0042-work-queue.md:61–74`), its notes, or any ADR. The string appears only in the CSV. ADR-0050:383 describes it in prose ("owner the human of the first run raising it"). Fix: add a note to ADR-0042 rule 7 defining `run_on_behalf_of` (the human the run acts for; fallback `company_owner`).

3.2 **Should-fix** — stale kind name `inbound_message` (renamed `inbound_message_matched` by ADR-0052 rule 15) with no note at the spot:
- `adr/0042-work-queue.md:158`
- `adr/0050-agent-runtime-and-query-layer.md:123`
- `adr/0051-agent-workflows.md:109`
- `adr/0019-partners-and-crm-foundation.md:58` (its note at `:60` covers only the role rename)

Fix: append rename notes.

3.3 **Should-fix** — `catalogs/work-item-kinds.csv:28`. `bank_line_unmatched` has `resolution=person` with `resolution_command=MatchBankLine`. ADR-0042 rule 1 (`:27`) allows a command only with `resolution=command`. It is the only row breaking the rule. Fix: set `command`, or clear the command.

3.4 **Nit** — `catalogs/work-item-kinds.csv:35`. `import_duplicate_suspected` uses owner rule `document_owner` on subject `import_row`, which is not a document. ADR-0042 rule 7 defines `document_owner` as "the human who created the document". Fix: widen the definition by note, or name the batch creator.

3.5 **Nit** — stale `role:sales` in body text, patched by a note nearby: `adr/0051-agent-workflows.md:233` (note 244), `adr/0052-minimal-crm.md:153` (note 158), `:208` (note 212). `approver_role` remains in the ADR-0042 rule 7 list at `:68` (note 74). Acceptable under the append-note practice; listed for completeness.

3.6 **Nit** — kinds never cited by code in any ADR, design or spec file (ADR-0042 rule 18 names them only in prose): `change_proposal_failed`, `e_invoice_posting_held`, `e_invoice_date_outside_window`, `subcontract_line_review`.

All other owner rules are defined: `buyer`, `planning_owner`, `warehouse_role`, `document_owner`, `issuer`, `rule_owner`, `company_owner`, `role:accountant`, `role:sales_clerk`, `approval_stage`, `subject_assignee`, `subject_owner`. All due rules are defined in rule 8 or its note: `same_day`, `days:n`, `required_date`, `period_end`, `subject_due_date`, `stage_due_days`. No kind cited in an ADR is missing from the CSV apart from 3.2.

## Check 4 — event types

4.1 **Should-fix** — `design/DS-17-synthetic-dataset.md:44`. The log schema is still "0.3.0 (… adds the ADR-0029 events)". Types were added afterwards with no version bump, although the same rule says a new type raises the minor version:
- ADR-0045: `price_list_published`
- ADR-0048: `cash_counted`, `currency_exchanged`, `advance_settled`
- ADR-0051: `customer_inquiry_received`
- ADR-0052: `email_received`, `interaction_recorded`, `complaint_raised`, `complaint_resolved`, `consent_given`, `consent_withdrawn`, `data_subject_erasure_requested`, `message_sent`
- ADR-0053: `invoice_corrected`

Fix: bump the version and extend the history sentence.

4.2 **Nit** — `design/DS-17-synthetic-dataset.md:63–64`. `bank_account_change_requested` is defined in the Safety row and restated in the CRM row; `quotation_requested` and `customer_inquiry_received` are restated there too. No conflict, but there are two places to maintain.

4.3 **Nit** — core event `WorkItemRaised` (`adr/0013-outbox-and-events.md:33`, `adr/0042-work-queue.md:55`, `:119`) uses "Raised", which is not an event form of any glossary verb (ADR-0004 rule 22). Fix: add `Raise` to the verb list, or state the exception.

4.4 **Nit** — there is no catalog of core (PascalCase) event types; they are derivable only from commands. 59 distinct names are cited across the ADRs.

Every `business_event_types` value in `edge-cases.csv` exists in DS-17 rule 5, and no edge case has a `first_executable_step` earlier than its events. DS-17 types used by no edge case (informational): `advance_paid`, `company_founded`, `consent_given`, `goods_consumed`, `goods_returned_to_supplier`, `goods_scrapped`, `interaction_recorded`, `partner_registered`, `price_list_published`, `product_registered`, `purchase_requested`, `sales_history_recorded`, `warehouse_opened`.

## Check 5 — transaction keys (61), movement types (21), system accounts (117)

5.1 **Should-fix** — stale counts:
- `adr/0015-account-determination.md:7`: "50 keys"; the catalog has 61. The keys of ADR-0047 (`free_goods_cost`) and ADR-0048 (`bank_charge`, `cash_surplus`, `cash_shortage`, `payment_difference_income`, `payment_difference_expense`, `bad_debt_expense`, `bad_debt_allowance`, `bad_debt_recovery`, `payable_release_income`, `currency_exchange_clearing`) were never counted.
- `adr/0020-inventory-and-costing-model.md:19`: "13 types (20 with the production types)"; the catalog has 21 (`free_goods_issue`).
- `adr/0035-production-costing.md:271` ("key count 44") and `adr/0037-subcontracting.md:140` ("key count 46") are historical.

5.2 **Nit** — keys never cited outside the catalogs: `inventory_count_shortage`, `inventory_write_down_allowance`. `retained_earnings_transfer` is cited in no ADR.

5.3 **Nit** — system accounts never cited outside catalogs and the DS-19 chart (26): `deferred_tax_asset`, `deferred_tax_liability`, `equity_other`, `financial_income`, `financial_investment`, `financial_investment_allowance`, `financial_investment_group_company`, `income_tax_expense`, `interest_expense`, `inventory_finished_goods`, `inventory_goods_in_transit`, `inventory_goods_sent`, `inventory_tools_supplies`, `inventory_write_down_allowance`, `payable_social_contribution`, `revenue_deduction`, `share_premium`, `tax_payable`, `tax_payable_corporate_income`, `tax_payable_import`, `tax_payable_personal_income`, `tax_receivable`, `tax_receivable_input`, `tax_receivable_other`, `treasury_stock`, `unearned_revenue`. Expected for a chart; no action unless the "reverse" rule is meant strictly.

Forward direction is clean:
- Every key's `required_system_accounts` exists; every movement type's `offset_transaction_key` exists.
- Every DS-19 determination key, chart `system_account`, tax-code key and unreached account exists.
- Every postable system account is mapped or listed as unreached; every key has a TT99 determination row.
- No ADR cites a key, movement type or system account that is missing from its catalog. `environmental_protection_tax` is correctly noted as dropped at `adr/0041-tax-engine.md:243`.

## Check 6 — `ADR-nnnn rule N` citations

5,278 qualified citations were resolved mechanically across docs, SQL, CSV and lab; all point to an existing rule number. 95 distinct citations from ADR-0045..0055 were read against the cited rule's text; all are plausible.

6.1 **Should-fix** — ambiguous rule numbers. Three ADRs have two numbered lists that both start at 1, so "rule 1–5" is ambiguous:
- `adr/0028-document-lifecycle-hardening.md:9–13` (summary 1–5) against `:19–50` (rules 1–5)
- `adr/0029-proposals-and-agent-safety.md:9–17` against `:25–60`
- `adr/0044-data-migration-and-export.md:8–12` against `:33–68`

Citations such as "ADR-0029 rule 3" (`adr/0050-agent-runtime-and-query-layer.md:236`, `adr/0051-agent-workflows.md:101`, `:145`) and "ADR-0028 rule 4" (`adr/0055-approval-pools-and-stages.md:118`) only make sense against the second list. Fix: turn the summary lists into bullets.

6.2 **Nit** — bare "rule N" that refers to another document: `adr/0026-open-item-core.md:117` ("rule 29" is DS-16's), `adr/0053-core-neutrality.md:155`, `:274` ("rule 18" is DS-16's), `adr/0039-vietnam-package-tt99.md:148–149` ("rule 16", "rule 17" are ADR-0010's). Fix: qualify them.

## Check 7 — CSV integrity

All 11 catalog CSVs and 12 DS-19 CSVs parse with a constant field count, snake_case headers, no duplicate header, no BOM or CRLF, balanced quotes, a final newline, and no leading or trailing spaces in cells. No duplicate keys in single-key catalogs. `role-template-levels.csv` has no duplicate (template, node) pair, and all its templates and nodes exist. Every `authorization-areas.csv` parent exists. Every command in `segregation-rules.csv` starts with a catalogued verb.

7.1 **Nit** — `design/DS-19-vietnam-tt99/regimes/tt99/chart_template.csv:128–129`. Code `4111` appears twice, distinguished only by `condition` (`legal_form=joint_stock` or not). Intended, but the key is (code, condition); say so in the DS-19 README.

7.2 **Nit** — `catalogs/work-item-kinds.csv:9–11`, `:21`. `resolution_command` holds the placeholders `Complete<Type>Posting`, `Issue<Type>`, `Approve<Type>`, which are not command names a registry check can resolve.

7.3 **Nit** — value sets used by the catalogs but enumerated in no design doc: `edge-cases.csv` areas `close`, `purchasing`, `imports`, `crm`, `cash`, `reporting`. DS-17 rule 22 leaves `area` blank.

## Check 8 — stale counts and indexes

8.1 See 2.2 (DS-16:57, DS-17:199) and 5.1.

8.2 **Should-fix** — "DS-01 to DS-55" is stale; the backlog has 57 items:
- `design/README.md:3`
- `README.md:11` (docs map, reading order item 5)

The backlog intro itself is correct: `design/backlog.md:3` says "Fifty-seven" and there are 57 rows.

8.3 **Should-fix** — `README.md:22` (docs map, layout table). `catalogs/` is described as "system accounts, transaction keys, movement types, edge cases", omitting 7 of the 11 files. `reviews/` has no row at all.

8.4 **Nit** — `design/backlog.md:40` and `adr/README.md` (ADR-0043 row). DS-28 and ADR-0043 are still titled "one-level approval" after ADR-0055. Note it in the DS-28 row; the ADR title is historical.

8.5 **Should-fix** — `runbook/step-log.md`. There is no entry for the author's 2026-11-15 decision that the e-invoice provider connection (DS-24) is an add-on (recorded only in `design/backlog.md:73` and `open-questions.md:31`), and none for adding DS-57. The order is otherwise newest-first and matches git. `:33` ("system chart 0.1.0 now 116 accounts") and `:37` ("31 edge cases") are historical and correct at their date.

8.6 **Should-fix** — broken relative links (link checker over 2,894 links found 14):
- `reviews/2026-11-14-design-validation/README.md:26, 27, 28, 50–57, 59, 60` (13 links) use `../adr/…`; from that folder it must be `../../adr/…`. Lines 49, 58 and 61 already use the right form.
- `design/DS-19-vietnam-tt99/README.md:15`: `../adr/0041-tax-engine.md` must be `../../adr/0041-tax-engine.md`.

8.7 **Nit** — `reviews/2026-11-14-design-validation/README.md`, file table. `t12_access.py` is listed before `t09`, `t10` and `t11`. `costing_solver.py`, `costing_lab2.py`, `mrp_lab.py`, `check_package.py`, `tax_lab.py` and `policy_lab.py` sit between `t03` and `t04`. `t07` and `t08` are in order. L-01..L-20 are in order with no gaps or duplicates.

8.8 **Nit** — same README: the `check_package.py` row says "`--self-test` applies eighteen broken copies", while L-09 says "twelve broken copies each fail". Add "(later eighteen)" to L-09 or drop the number.

8.9 Lab check counts, counted statically (call sites of `check(`, `expect(`, `trial(`; nothing was run):

| File | Claimed | Call sites | Verdict |
| --- | --- | --- | --- |
| t01 | 13 | 13 | matches |
| t02 | 6 | 6 | matches |
| t03 | 4 | 4 | matches |
| t07 (L-15) | 38 | 38 | matches |
| t08 (L-16) | 35 | 35 | matches |
| t09 (L-17) | 60 | 60 | matches |
| t10 (L-18) | 68 | 68 | matches |
| t12 (L-20) | 179 | 152 + 27 = 179 | matches |
| t05 (L-13) | 62 | loop-driven | not verifiable statically |
| t11 (L-19) | 163 | 40, loop-driven | not verifiable statically |
| t06 (L-14) | none stated | 42 | no claim |
| t04 (L-12) | none stated | uses `trial(` | no claim |

Fix: have each script's last line print its total and quote that; state counts for L-12 and L-14.

8.10 **Nit** — `lab/t05_master_data.py:159` and `lab/t06_configuration.py:509` default to the hard-coded path `~/Projects/NativeFlows/docs/design/…`; t11 and t12 use `NATIVEFLOWS_DOCS`. Unify.

8.11 `adr/README.md` index: all 55 ADRs are listed, and titles and status dates match each ADR's Status line. No defect.

## Check 9 — open-questions.md (190 entries, unnumbered checkboxes; "numbering" does not apply)

9.1 **Should-fix** — `open-questions.md:95` and `adr/0032-phase-1-scope-with-production.md:90` call ADR-0055 "(proposed)"; it is accepted (2026-11-15). The multi-level-approval part of line 95 is answered and should be split off and ticked.

9.2 **Should-fix** — duplicates and overlaps:
- `:26` and `:123`: the same question (book rate method, `specific` for open items and `moving_average` for cash and bank). Merge.
- `:141` and `:86` (and partly `:32`): approval that may not delay e-invoiced documents; `:86` is the ADR-0053 restatement. Close `:141` with a pointer.
- `:38` (bank-account change in a one-person company) defers to `:99`, and `:104` asks about the small-company mode again. Three entries for one decision.
- `:36`, `:40`, `:41`: tainted read scope asked three times (ADR-0029, ADR-0050, ADR-0051 readings). Group under one entry.
- `:5` and `:173` still say "Verify Decree 70/2025", while `:96` says the e-invoice rules were replaced by Decree 254/2026 and Circular 91/2026. `runbook/steps-5-9.md:80` has the same stale reference.

9.3 **Should-fix** — entries overtaken by accepted ADRs or author decisions but still unticked or stale:
- `:22`: "Needed before DS-53" — DS-53 is done (ADR-0035); only the TT99 account mapping remains.
- `:57`: "open items DS-19 to DS-40 and DS-52 to DS-55" — most are done.
- `:59`: the body still says "Interim: all later" beside "Configured products are answered". Split it.
- `:109`: the TT99 chart template and determination are done (ADR-0039, DS-19); only TT133 and US remain.
- `:21`: phrased for a Phase 1 without production ("before a company activates its WIP subledger, may the Phase 1 pilot post work in process … by manual journal"); reword under ADR-0032.
- `:17`: the phase part is answered inline; the feature-list part is open. Acceptable, but split it.

9.4 Author decisions checked:
- Bank charge account declared at setup: recorded at `:53` (ticked) and `adr/0048-cash-bank-receivables-payables.md:231`. No remaining open entry contradicts it.
- BKAV as an add-on: recorded at `:31` and `design/backlog.md:71–77`. Author-owned texts still place it in Phase 1 (`spec/06-localization.md:24`, `spec/08-l10n-vn.md:23`, `runbook/steps-5-9.md:80, 86, 100, 102`); these are already listed in `:31`. `spec/11-build-order.md:43` is already updated.
- Vietnam as an overlay: `:53`, ADR-0053. Consistent.
- Phase 1 with production: `:57–58`. See 9.3 for the stale wording.

## Check 10 — glossary (`spec/00-reading-guide.md`)

10.1 **Should-fix** — `EvaluateConfiguration` (`adr/0046-product-configuration.md:23`, `:102`, `:186`, `:191`, `:255`) is a query whose first word is neither `Get` nor `List`. `adr/0004-naming-conventions.md:94` says the registry rejects that. `Evaluate` is in neither the glossary verb list nor `catalogs/authorization-verb-levels.csv`, so ADR-0054 rule 8 gives it no level. Fix: rename it (`GetConfigurationEvaluation`), or add `Evaluate` to both lists with level `read`.

10.2 **Should-fix** — verb list and catalog disagree in form. `catalogs/README.md` says "one row per glossary verb". The glossary has 55 verb rows, with `Match, Unmatch` and `Pack, Unpack` combined; the CSV has 59 rows, split, plus `Get` and `List`, which are not in the verb table (they are defined at glossary `:330`). Fix: split the two glossary rows and add `Get`/`List` to the verb table or to the README sentence. Levels and names otherwise match.

10.3 **Should-fix** — tables in the DDL files with no glossary identifier:
- DS-15: `user_session`, `credential_reset`, `integration_token`, `installation_role_assignment`, `role_level`, `role_permission`, `role_assignment_scope`, `delegation_role_assignment`, `segregation_review`
- DS-20: `company_currency_activation`, `working_calendar_holiday`, `partner_address`, `partner_bank_account`, `product_variant_attribute`
- DS-35: `interaction_participant`, `data_subject_request_content`, `outbound_message_content`, `outbound_message_recipient`, `outbound_message_delivery_recipient`, `partner_tax_lookup`
- DS-56: `configuration_rule`, `configuration_table`, `configuration_table_column`, `configuration_table_row`, `configuration_default`, `product_configuration_value`

Terms from ADR-0045..0055 with no row: "role template" (appears only inside the Role row at `:212`), `bank_matching_rule` (`adr/0048-cash-bank-receivables-payables.md:131`), the views `system_account_turnover` and `partner_item_overview` (ADR-0050, ADR-0051), and the owner rules `run_on_behalf_of`, `subject_owner`, `subject_assignee`.

10.4 **Nit** — code identifiers that lead more than one glossary row: `import_batch` (21, 353), `policy_decision` (58, 229), `price_list` (97, 165), `work_item` (210, 370), `agent_run` (346, 352, 357), `cost_object` (88, 108), `stock_count` (129, 383), `landed_cost` (185, 188), `variant_attribute` (233, 236), `preliminary_price` (122, 124), `price_difference` (163, 189). I did not compare the definitions row by row; merge or cross-reference them. `policy_decision` is glossed as "Policy point" at `:58`, which is a different thing from the record.

No duplicate Term rows. No stale `approver_role` or `role:sales` in the glossary. The template list at `:212` equals `role-templates.csv`.

## Check 11 — public repo rule

11.1 **Should-fix** — realistic Vietnamese company names in lab fixtures; companies with these names plausibly exist:
- `lab/t11_crm.py:435`: "Công ty TNHH Thương mại Đại Phát"
- `lab/t11_crm.py:436`: "ĐẠI-PHÁT, Co. Phan"
- `lab/t11_crm.py:834`, `:840`: "Công ty TNHH An Phát", "Công ty CP An Phát Trading", "CÔNG TY TNHH AN PHÁT", "An Phú", "Bình Minh"

Fix: use obviously fictional names (for example "Công ty TNHH Mẫu Một").

11.2 **Nit** — e-mail addresses on a real domain: `lab/t11_crm.py:379`, `:393`, `:394` (`user@gmail.com`, `someone@gmail.com`). They are test inputs for the public-mail-domain rule. Keep the domain if the test needs it, but note it; the local parts are generic. `adr/0022-repository-and-engineering-conventions.md:225` has `noreply@anthropic.com` (attribution text). All other addresses use `.example` or `.test`.

11.3 **Nit** — real bank short names with made-up account numbers: `lab/t08_cash.py:44`, `:105`, `:114–122` (`VCB`, `TCB`, `ACB`; `0123456789`, `9988776655`). Use `BANK-A` and `BANK-B`.

11.4 **Nit** — the author's personal name is in the docs: `open-questions.md` (8 places, e.g. `:50`, `:53`, `:143`, `:168–170`), `design/backlog.md:73`, `design/DS-19-vietnam-tt99/settings.yaml` (1). The repository owner `AnGaudium` is in `adr/0003-build-operating-rules.md`, `runbook/README.md`, `runbook/steps-0-4.md`, `runbook/step-log.md` and `open-questions.md:111`. Git commits carry the author's name and an e-mail on a company domain. Probably intended for a public author; confirm, or replace with "the author".

11.5 **Nit** — segment hints, generic but repeated: "assembly manufacturers" and "assembly-type manufacturers" at `open-questions.md:50`, `:57`; `adr/0033-production-master-data.md:212`; `adr/0034-production-orders-and-shop-floor.md:278`; `adr/0037-subcontracting.md:11`. `open-questions.md:114` names two earlier documents about "Vietnamese manufacturing on Odoo 19". No customer name was found, and no hit for generator, cabinet, plywood, furniture or engine brands. The vendor names BKAV, MISA, Viettel, VNPT, SAP, Odoo and Dynamics appear as vendors, not customers.

## Check 12 — loading DS-06, DS-20, DS-15, DS-35, DS-56 with `lab/00_stubs.sql`

Static result: the five files can be loaded together, but not in any plain file order, and not with the stubs as they are. No lab scenario loads all five: t06 loads DS-20+DS-56+DS-06, t11 loads DS-20+DS-35+DS-06, t12 loads DS-20+DS-06+DS-15.

12.1 **Blocking for the sim** — no file order exists. The files reference each other in cycles:
- DS-06 → DS-20 (`company`, `branch`, `cost_center`, `currency`, `item`, `partner`, `project`, `warehouse`) and DS-20 → DS-06 (`payment_term`, at `design/DS-20-master-data.sql:237`, `:255`)
- DS-20 → DS-15 (`user_account`, at `:64`, `:270`) and DS-15 → DS-20 (`company`, `branch`, `partner`, `warehouse`, plus `ALTER TABLE employee_profile` at `design/DS-15-access.sql:383`)

The loader must concatenate all five files and order statements by table dependency: every CREATE TABLE in topological order first, then all other statements in concatenation order. `lab/load_ds06.py` run on the five-file concatenation produces an order with no cycle (verified, output only).

12.2 **Blocking for the sim** — `lab/00_stubs.sql:11`. The stub `CREATE TABLE user_account (id uuid PRIMARY KEY);` collides with `design/DS-15-access.sql:17`; it is the only table defined twice. The loader must drop that stub line, as t12 does at `lab/t12_access.py:62–64`.

12.3 **Blocking for the sim** — the stub `document` (`lab/00_stubs.sql:18`) lacks what DS-35 needs. Six composite foreign keys reference `document (company_id, id)`, which has no unique constraint in the stub: `design/DS-35-crm.sql:228`, `:242`, `:300`, `:312`, `:333`, `:350`. The loader must run, after the stubs and before the DDL (as `lab/t11_crm.py:41` does):

`ALTER TABLE document ADD COLUMN partner_id uuid, ADD COLUMN document_date date, ADD CONSTRAINT uq_document_company_id_id UNIQUE (company_id, id);`

For the access scenarios, `document` also needs `owner_employee_id uuid`, `created_by_user_id uuid` and `branch_id uuid` (`design/DS-15-access.sql:389–390`; `lab/t12_access.py:455`). `branch_id` is added by t12 but is not in DS-15's own list at 389–390: a small inconsistency. If the simulation uses the final-state model, it needs t11's `document_version` stub too (`lab/t11_crm.py:42–43`).

12.4 **Blocking for the sim** — `design/DS-35-crm.sql:466` uses `gin_trgm_ops`. The stubs create only `btree_gist`. The loader must run `CREATE EXTENSION IF NOT EXISTS pg_trgm;`, which needs the extension available and sufficient rights in the test database.

12.5 **Should-fix** — none of the five DDL files sets a schema or search path. The loader must run the stubs first (they drop and create schemas `nativeflows` and `types`, the five `types.*` domains and `btree_gist`) and then `SET search_path = nativeflows` in the session that runs the ordered DDL.

12.6 **Nit** — `lab/load_ds06.py` splits statements on lines ending in `;`. A trailing comment after `;` silently merges two statements (L-13 found this once). None exists now in the five DS files; `lab/00_stubs.sql:5` has one, harmless because the stubs are executed whole. Add a guard to the loader.

12.7 Everything else resolves:
- No foreign key targets a missing table.
- No composite key targets columns without a PK or UNIQUE, other than 12.3.
- No index, constraint, trigger or function name is duplicated across the five files.
- Tables that remain stub-only because they have no DDL draft: `system_account`, `account`, `fiscal_year`, `posting_period`, `posting_period_area_state`, `document`, `material_document`, `material_document_line`, `applied_rate`, `close_task`, `tax_code`, `transaction_key`.
- Tables referenced by ID without a foreign key (per file headers): `attachment`, `agent_run`, `work_item`, `approval`, `approval_procedure`, `policy_decision`, `audit_record`. A simulation that needs these must stub them.

Combined loader recipe:
1. Run `00_stubs.sql` minus the `user_account` line.
2. `CREATE EXTENSION IF NOT EXISTS pg_trgm`.
3. `ALTER TABLE document …` as in 12.3, plus the DS-15 columns and the `document_version` stub if needed.
4. Concatenate DS-20, DS-06, DS-15, DS-35 and DS-56 and pass them through `load_ds06.py`.
5. `SET search_path = nativeflows`, then execute the ordered output.
