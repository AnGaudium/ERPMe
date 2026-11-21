# Review: compiled spec `master_data` (chunks 1 to 8)

Reviewer: Claude Sonnet 5.5 (compiler: Claude Opus 5.5). REPO `~/Projects/NativeFlows-s4`, specs `OUT/specs/master_data-1.md` to `master_data-8.md`.

## Verdict

PASS on blocking (0 blocking). One SHOULD-FIX (master_data-S1), so the bar "0 blocking and 0 should-fix" is NOT met: the module does not pass until S1 is fixed. Spot check: 25 of 25 source units FAITHFUL (error rate 0/25); reverse check: 10 of 10 R-numbers sourced. Partner tax model: correct in all 8 chunks.

## 1. Lint

`LINT PASS findings=0`; units=562, rules=300 (173 primary), notes=248, 14 sections, 75 tables, 452 R-numbers, 562 trace rows, 562 traced units. Stable-key mismatches 0. Review list 60 entries, all CONFLICT, 0 FALSE-POSITIVE, 0 OPEN. SUPERSEDED RULES: 1 (ADR-0009.R11 by ADR-0029.R6).

Retention is 93 to 100 per chunk; the lowest rules (ADR-0056.R25 28/37, ADR-0074.R14 22/26, ADR-0018.R12 2/3, ADR-0019.R1 15/18) were read: the identifiers not found in backticks are old names (`household_business`, `recorded_at`, former column names) or catalog row lists that the spec deliberately points to. No law lost.

Mechanical checks I added (all clean):
- every backticked identifier (4+ chars) in the 8 chunks occurs somewhere under `docs/` (ADR, DDL, catalogs): 0 invented tokens;
- every table in an "Entities and tables" section has a `CREATE TABLE` in `docs/design/*.sql`: 0 missing;
- every setting row in the Settings sections (chunks 7, 8) matches `settings.csv` on area, scope and core default; every `INV-` number cited exists in `invariants.csv` except the range placeholders `INV-607`, `INV-619`, `INV-639` (stated as unused/ranges, correct);
- the authorization leaves and areas named in the Commands tables exist in `authorization-areas.csv`.

## 2. Spot check (seed 3202, N=25)

All 25 read against the whole ADR rule with its notes (and later rules named by notes). Result per source ID:

| Source ID | R-number | Verdict |
| --- | --- | --- |
| ADR-0045.R13.N4 | R411 | FAITHFUL |
| ADR-0063.R16.N1 | R1240 | FAITHFUL (ADR-0050.R27.N5 sentence checked) |
| ADR-0019.R1.N1 | R37 | FAITHFUL |
| ADR-0045.R7 | R259 | FAITHFUL (N2 folded; N1 in R260) |
| ADR-0045.R13.N2 | R414 | FAITHFUL |
| ADR-0056.R22 | R863-R865 | FAITHFUL |
| ADR-0045.R3 | R247, R248 | FAITHFUL (`not negative`, `default 0`, `ex_price_list_entry_overlap` confirmed in DDL) |
| ADR-0056.R10 | R817-R833 | FAITHFUL; worked examples dropped by design; R831 unclear, see S1 |
| ADR-0018.R10.N1 | R24 | FAITHFUL (uses `created_at`, correct per ADR-0056.R4.N1; see SOURCE-2) |
| ADR-0061.R28 | R1225 | FAITHFUL |
| ADR-0061.R6 | R1048-R1049 | FAITHFUL |
| ADR-0068.D0 | R1259, R1261 | FAITHFUL (summary; its parts live in the rules) |
| ADR-0046.R6 | R440 | FAITHFUL (adds column `effect`, which DS-56 DDL holds) |
| ADR-0046.R3 | R434-R436 | FAITHFUL (R434 states the DDL gap on `uom_id`, see SOURCE-4) |
| ADR-0080.R1 | R1461 | FAITHFUL |
| ADR-0015.R11 | R6 | FAITHFUL (N1 in R7) |
| ADR-0056.R4 | R651-R660 | FAITHFUL (`created_at` per N1) |
| ADR-0046.R19 | R621 | FAITHFUL |
| ADR-0045.R17 | R427-R429 | FAITHFUL (R429 matches DDL: mode via composite FK plus command check `option_extra_not_allowed`) |
| ADR-0019.R7 | R204 | FAITHFUL |
| ADR-0068.R21 | R1404 | FAITHFUL |
| ADR-0069.R18 | R1429 | FAITHFUL |
| ADR-0018.D0 | R10 | FAITHFUL (the "partner's tax group" sentence of the Decision rightly not carried) |
| ADR-0074.R9 | R1448 | FAITHFUL |
| ADR-0061.R5.N1 | R1046, R1047 | FAITHFUL |

Reverse check (10 R-numbers by the same seed: R243, R402, R234, R866, R261, R608, plus R7, R1049, R620, R1402; R1402 read against ADR-0068.R18): every clause traced to its cited units (ADR-0045.R1 with ADR-0017.R19.N3; ADR-0045.R11 and N1; ADR-0027.R17 with ADR-0055.R8/R18 and the catalog text of INV-82; ADR-0056.R23; ADR-0045.R8; ADR-0046.R16; ADR-0019.R3/R15; ADR-0068.R18). Nothing invented or imported uncited. R7's gloss "so that profile holds customers and suppliers without accounts" is a restatement, not new law.

## 3. Partner tax model (ADR-0080.R1 over ADR-0018.R16, ADR-0019.R1, ADR-0045.R12, R13), all chunks

Checked every occurrence (grep for `partner_tax_group`, "partner tax group", "tax group", `partner_tax_status`, `tax_treatment`, `is_tax_zone`) in chunks 1 to 8:

- Chunk 1: R31 (item tax group effective, partner status, document `tax_treatment`, matrix direction x treatment x item tax group, ADR-0080.R1 to R4) matches ADR-0018.R16.N1 and N2; the old text (partner tax group on partner and document) is not restated as law. The sentence of R16 on the open question and its interim (external-document lines only) is kept. R36 has `partner_tax_status_id`, kinds `organization`/`sole_proprietorship`/`individual` (DDL `ck_partner_kind`). Entities table lists `partner_tax_status` (DDL: exists). R10 correctly omits the superseded Decision sentence. `partner_tax_group_id` appears only inside CONFLICT entries.
- Chunk 2: R201 `is_tax_zone` on `partner_address` (DDL line 463 and ADR-0080.R3) and R204 labels use `sole_proprietorship`: correct.
- Chunk 3: R404 and R413 state `partner_tax_status`/`tax_treatment` and `CreatePartner` takes `partner_tax_status_id`; R404 keeps "owned by `tax`, reads item tax groups and tax treatments". Correct resolution (ADR-0045.R12 and R13.N1 carry no note of their own; the supersession reaches them through ADR-0018.R16.N2 and ADR-0080.R1; see SOURCE-1).
- Chunk 8: R1461 (ADR-0080.R1), `tax_treatment` table with `directions` (`sale`, `purchase`; DDL `ck_tax_treatment_directions`), `partner_tax_status_id` on `partner` (DDL line 268, company key), `is_tax_zone` on `site` (R1249, DDL line 191). R1436 and the setting reads (`tax.destination_party`, `tax.services_place_of_supply`) are consistent with ADR-0074.R4.N1 and ADR-0080.R5. ADR-0074.R4's table and ADR-0080.R2 to R6 are `ref:` (owner `tax`), so no stale text is restated.
- No chunk keeps "partner tax group" as current law. No defect found in the tax model.

## 4. SUPERSEDED RULES, CONFLICT entries, FALSE-POSITIVE

- ADR-0009.R11 superseded by ADR-0029.R6: traced `ref:` (not restated in this module); the superseded text is not stated anywhere. Harmless; resolution right (ADR-0029.R6 says it "replaces this rule's separate statement").
- CONFLICT entries read in full against sources: ADR-0018.R2/R3/R10/R11/R12/R15/R16/R17, ADR-0019.R1/R4/R5/R7, ADR-0023.R1/R3.N1, ADR-0027.R17, ADR-0045.R3/R4.N1/R5/R6/R7/R11/R12/R13/R15/R16/R17, ADR-0046.R18, ADR-0056.R4/R10/R13/R25, ADR-0074.R7.N1/R8. In each the later accepted source wins and the statement holds the superseding text (examples: R25 rounding "follows the use"; R26 and R840/R841 GS1 measure AI wins; R212 and R213 no `ConvertWarehouse`, default bin everywhere; R248 any unit the item resolves; R256 `price_list_currency_differs`; R424 `system` creates the item). No wrong resolution found.
- FALSE-POSITIVE: none listed; nothing to judge.
- Missing Conflicts entry: none needed. Two quiet reconciliations are acceptable because the statement is correct and DDL-backed: R429 (database holds mode match, command refuses variant-mode extras on non-configurable products) and R434 (DDL does not require `uom_id` for a number; stated in the text).

## 5. Findings

### SHOULD-FIX

**master_data-S1** `specs/master_data-5.md:167`, R831 (source ADR-0056.R10 with ADR-0047.R13.N3, N4). Source: on a line for an item kept in stock, the residual posts to `purchase_cost_clearing` and adds a `landed_cost` of `cost_type` `exchange_rate_difference` to the receipt lines when the setting `costing.exchange_rate_difference_to_stock` is true (core default true); false posts to `fx_gain_realized`/`fx_loss_realized` and stays out of actual cost; the clearing reads the value in force on its posting date. Spec: "to realized exchange difference on a line without stock, and on a line for an item kept in stock as the setting `costing.exchange_rate_difference_to_stock` chooses". A reader cannot tell what the setting chooses between or what the default is, so the law of the module for this posting is not stated. Fix: add one sentence with both paths and the default true, citing ADR-0047.R13.N3 and N4 (and name the setting row in chunk 5 Settings with its default).

### NOTE

- master_data-N1 `master_data-1.md:184`, R36 (ADR-0053.R7): the `l10n_vn` mapping (household business to `sole_proprietorship`, private enterprise to `organization`) is generalised to "the localization package maps its national legal forms". Acceptable for a core-neutral spec; the Vietnamese rule is package law.
- master_data-N2 `master_data-3.md:209`, R440: adds column `effect` (jsonb) not in ADR-0046.R6; it is in DS-56 DDL. Fine, shown as DDL fact.
- master_data-N3 `master_data-8.md:217`, R1438: "is the import key map of ADR-0044.R5 (there named `import_key_map`)" for source "replaces `import_key_map`, which was named and never defined". Same meaning; "replaces" is clearer.
- master_data-N4 `master_data-1.md:170`, R31 drops "The item tax group list is DS-23's (ADR-0039 rule 10)"; ownership pointer only.
- master_data-N5 R1259 (ADR-0068.D0) does not restate that Incoterms are advisory; that is ADR-0068.R20 (inventory/ledger side), not in this module's units. No action.

### SOURCE findings (do not count against the spec)

- SOURCE-1: ADR-0045.R12 and R13 (the partner command note), ADR-0019.R1, the Decision/Constraints text of ADR-0018 (lines 128 and the tax sentence of the Decision) and ADR-0041.R3 still say "partner tax group" / `partner_tax_group_id` without a note pointing to ADR-0080; ADR-0080 "Documents updated" lists only ADR-0018.R16, ADR-0041 R3 and R7, ADR-0074.R4, ADR-0063.R29. The supersession is correct but reachable only through ADR-0018.R16.N2.
- SOURCE-2: `recorded_at` as start of validity still stands in ADR-0018.R10.N1 and in the INV-603 text of ADR-0056.R25 although ADR-0056.R4.N1 says it was changed "in the INV-603 text of this ADR" (catalog and DDL already use `created_at`).
- SOURCE-3: settings named by rules but absent from `catalogs/settings.csv`: `master_data.default_partner_group.customer|supplier|employee` (ADR-0045.R13), `barcode.gs_substitute`, `barcode.sscc_reuse_months`, `barcode.prefix.<type>` (ADR-0061), `inventory.purchase_receipt_tolerance_percent` and `purchasing.match.price_tolerance_amount` (ADR-0047). The spec states each as absent (chunks 3, 5, 7).
- SOURCE-4: ADR-0046.R3 says `uom_id` is set for a number and empty for a list "(the database holds this)"; DDL `ck_variant_attribute_number` requires `uom_id` null for a list but does not require it for a number. The spec (R434) discloses it.
- SOURCE-5: INV-113 is listed in the catalog under area `production` while ADR-0046.R18 and the module spec place it with master data configuration; harmless, noted for the area index.
