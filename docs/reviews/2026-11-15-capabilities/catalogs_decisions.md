# Architect decisions on the catalog/cross-reference review (report: catalogs_report.md)
This fix runs LAST, after fix_production, fix_commercial, fix_platform, fix_flows, fix_ledger and the DDL apply scripts; re-scan the tree at that point and fix what remains. Items already handled by earlier scripts: 1.1 revision_released (ledger F2), 2.1 INV-100..112 (production; add INV-113..115 rows if still missing), 3.1 run_on_behalf_of (platform 3), 3.3 bank_line_unmatched (platform nit 22), 3.4 document_owner (platform 5). Verify each and only fill gaps.

- 1.1 one class for trigger-held immutability: precondition 422 for revision_released, configuration_immutable, referenced_line_immutable (DS-04 direct edit).
- 1.2 add a "Loader errors" table to DS-14 with regime_setting_in_use, deductibility_rule_overlap, report_definition_in_use (+ any other loader codes found); pointer notes on ADR-0016, ADR-0049, ADR-0053 "Documents updated" are not needed if DS-14 is cited; add a single note per ADR only if the ADR says "DS-04:" for them.
- 1.3 one line in DS-04: outcome/violation enumerations are owned by their ADRs, not error codes.
- 1.4 move check-result rows to their own table in DS-04 (design doc; direct edit).
- 1.5 fix DS-04 citations (record_not_found etc.) to the ADRs that define them, or mark as envelope-level.
- 2.2 recount: DS-16 invariant count and DS-17 edge-case count and breakdown, from the catalogs at that point.
- 2.3 DS-16 group text: explain 90-99, 200-201, 206-209, 210-219, 220-239, 400-499, 500-599, production 100-115; add crm and cash to the area list.
- 2.4 correct the ADR-0054 EC sentence via note; DS-17 edge-case gap note.
- 2.5 add missing IDs to ADR-0047 r23 and ADR-0048 r20 catalog lists by note (EC-69..71, EC-72..76, EC-78 etc.); for older rows (INV-01.., EC-01..) leave as is (historical, catalog is authoritative) and say so in DS-16/DS-17 in one sentence.
- 2.6 skip (nit).
- 2.7 sort invariants.csv and edge-cases.csv by numeric code (keep header).
- 2.8 fix the t12 label.
- 4.1 bump the DS-17 log schema version (0.4.0) with history of added types (and any added by the flows fix).
- 4.3 add Raise to the glossary verb list and authorization-verb-levels (level per the verb rule; Raise is system-side, give `edit`), or state WorkItemRaised as an exception; prefer adding the verb.
- 5.1 count notes on ADR-0015 r1 and ADR-0020 r4 (final counts at that time).
- 6.1 add one note at the top of the Rules section of ADR-0028, ADR-0029, ADR-0044 (or as a note on rule 1): "rule N" citations refer to the Rules section, not the summary list.
- 6.2 qualify bare "rule N" references via notes where cheap; else skip.
- 7.1 DS-19 README: chart_template key is (code, condition).
- 7.3 enumerate edge-case areas in DS-17 rule 22.
- 8.2 design/README.md and docs README: "DS-01 to DS-57".
- 8.3 docs README layout table: list all catalog files; add reviews/ row.
- 8.4 note in backlog DS-28 row that pools and stages are ADR-0055.
- 8.5 step-log entries (2026-11-15): author decision DS-24 e-invoice provider connection is an add-on outside the core; DS-57 production agent added; and one entry for the holistic review itself (written by the coordinator at commit time, skip here).
- 8.6 fix the 14 broken relative links.
- 8.7 sort the lab README file table; 8.8 L-09 wording; 8.9 make each lab script print its total at the end if it does not, and state counts for L-12/L-14; 8.10 t05/t06 read ERPME_DOCS like t11/t12.
- 9.1-9.3 clean open-questions.md: fix "(proposed)" for ADR-0055 (also ADR-0032:90 via note); merge duplicates (keep one entry with cross-references); tick or split entries answered by accepted ADRs or author decisions; update stale decree references to the current ones only where the repo already states the replacement (Decree 254/2026, Circular 91/2026); do not delete author-raised questions, tick them with a pointer.
- 10.1 add verb Evaluate (level read) to the glossary verb list and authorization-verb-levels.csv; note on ADR-0004 that Evaluate<Noun> is a query form (EvaluateConfiguration) — do not rename.
- 10.2 split Match/Unmatch and Pack/Unpack glossary rows; add Get/List to the verb table or adjust catalogs/README sentence.
- 10.3 glossary rows for the listed DDL tables and terms (one line each).
- 10.4 cross-reference duplicate-identifier glossary rows (add "see also" rather than merging author text).
- 11.1 replace realistic Vietnamese company names in lab fixtures (t11 lines ~435, 436, 834, 840) with obviously fictional names (e.g. "Công ty TNHH Mẫu Một"), keeping the test semantics (fold, stop words, similarity) intact; rerun t11.
- 11.2 keep gmail.com test inputs (needed for the public-domain rule); add a comment.
- 11.3 bank short names in t08 -> BANK-A, BANK-B, BANK-C; rerun t08.
- 11.4 author name: leave (author's own public repo); report to the author.
- 11.5 leave (author-approved generic goal).
- 12 write `reviews/2026-11-14-design-validation/lab/load_all.py`: the combined loader recipe (stubs minus user_account and minus any stub that a DDL draft now defines; pg_trgm; document columns; all DDL files in design/ concatenated and ordered by load_ds06 logic; search_path), with a guard for trailing comments after ';'. Lab test: load everything into erpme_lab and report the table count. This loader is what the final simulation uses.

## DDL reconciliation (apply in this final step, after all apply_ddl*.py ran)
Planning/production DDL (DS-43-54, lab t16 96/96) reported ambiguities; decisions:
- cost_object (DS-06): take over UNIQUE (company_id, id, production_order_id) and the keys from DS-43-54 into DS-06 itself; drop the ALTER TABLE from DS-43-54.
- forecast tier none: n=0 writes no forecast_line rows; the check result carries details.tier=none; forecast_line.forecast_tier allows short_mean, unindexed, indexed only (adjust the check and the ADR-0024 r11 note wording if it says "stored").
- released cost estimates: partial unique index on (company_id, production_version_id, costing_date) where state released.
- hold_reasons: production component and output rows of a production order carry not_approved until the order is approved (released), like sales/purchase rows; MTO netting and planning read released rows only for demand; supply rows count when planned. Note on ADR-0024 r8.
- DS-56 header: update "production DDL not yet drafted" to point to DS-43-54.
- work center name uniqueness: code unique only is fine; note on ADR-0033 r11 that name is not unique.
- disassembly: at most one main output; rework order may have no production version (note ADR-0034 r4).
- If the commercial and platform DDL apply scripts collide on names (apply_ddl.py), they were named apply_ddl_commercial.py and apply_ddl_platform.py; apply order: planning, commercial, platform.

## Extra decisions from the flows fix (apply in the final step)
- Segregation `block` mode vs owner: the "no conflict while mode is block" check (INV-229, EnableSegregationRule, mode switch) exempts assignments of the `owner` template, which by ADR-0054 rule 12 holds every permission; the owner still falls under the runtime pair checks of ADR-0054 r19 on each document (the same person cannot do both sides of a pair on one document). Note on ADR-0054 r17 (and r20 if it restates it); add a t12 lab case: block mode can be enabled with only the owner conflicting.
- Submitting agent drafts: give `change_proposal` at `edit` (no approve) to accountant, sales_clerk and buyer, so the people who handle agent proposals in their area can submit them (bank rule proposals, onboarding, purchase mapping). Edit role-template-levels.csv rows (add if missing) and keep t12 passing (E5a must still hold: change_proposal is not on any segregation rule side; check).

## From the commercial/inventory DDL (DS-22-09-42, lab t14 83/83); decisions for the final step
- correction_of_line_id may point to a line of another table (ADR-0047 r2 wins): note on ADR-0028 r2.
- DS-56 product_configuration gets UNIQUE (company_id, id); delivery/return lines then reference it by (company_id, product_configuration_id).
- Headers not checked against document type: leave (command check), no change.
- credit_hold states interim: fine; note on ADR-0047 r18 listing held/released/cleared/lapsed as interim.
- Null-safe CHECKs: scan all DDL drafts (DS-05-platform, DS-43-54, DS-22-09-42, DS-15, DS-20, DS-35, DS-56) for CHECKs that pass on NULL unintentionally (length(btrim(x)) > 0 on nullable columns, nullable comparisons) and make them null-safe where the column is meant NOT NULL or the rule must hold.
- credit_hold.work_item_id and other work_item references: add keys to work_item (company_id, id) if DS-05-platform defines work_item.
- demand_supply_line keys to sales/purchase/request lines are added by DS-22-09-42 only (DS-43-54 must not duplicate).
- Labs share erpme_lab: final runs go sequentially (no parallel agents).

## From the platform DDL (DS-05-platform, lab t15 145/145); decisions for the final step
- 00_stubs.sql: drop the `document` stub (DS-05 defines it), the `user_account` stub (DS-15), and `material_document`/`material_document_line` (DS-22-09-42 defines them); keep system_account, account, fiscal_year, posting_period, posting_period_area_state, applied_rate, close_task, tax_code, transaction_key. Old labs that need bare stubs (t01-t08 insert bare user_account rows, t11/t14 extra stubs) keep working: give the old standard load a `00_stubs_legacy.sql` (the current file renamed) and point t01-t08/t11/t14 at it, OR keep 00_stubs.sql as is and make load_all.py strip the redefined stubs. Prefer the second (fewer lab edits).
- work_item.owner_role stores the bare template code or company_owner; `role:<template>` is catalog notation. Note on ADR-0042 r7.
- Column renames for ADR-0004 (input_tokens -> input_token_count etc., count -> denial_count, base/tax/computed_tax -> *_transaction_amount, paid_by_third_party -> is_paid_by_third_party): notes on ADR-0050 (run step/budget rule), ADR-0038 r5, ADR-0041 (tax line rule), ADR-0048 r9.
- policy_rule split into policy_rule + policy_rule_version; policy_decision stores the evaluated actor (actor_kind, actor_id, on_behalf_of_id): notes on ADR-0043 r7/r8.
- credit_hold.work_item_id key to work_item(company_id,id): add in DS-22-09-42 now that DS-05 is in design/.
- RLS written only in DS-05: add one sentence in design/README that the other DDL files describe RLS in comments and the rls_v1 pattern of DS-05 applies to every company table.
