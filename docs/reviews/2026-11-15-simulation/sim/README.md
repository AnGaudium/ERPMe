# NativeFlows flow simulation (design validation; flows 1-11 on design branch ds-production HEAD bd459d4, ADR-0056 to ADR-0064)

NativeFlows is in the design phase and has no product code. This folder builds a test database from **all** design DDL,
seeds one fictional company of the DS-17 `vn_manufacturing` profile, and runs six business flows step by step as the
flows report (holistic review, Part B) and the architect decisions after it describe. Every step writes the real
design tables, runs the deterministic rule as a pure Python function, records events, audit rows and work items, and
posts through the DS-06 triggers. The trace shows, step by step, which lane acts: a **person**, an **LLM agent**, a
**deterministic function** (or system job / consumer), or the **database** (a trigger or constraint refusing a bad row).

It is simulation code, not product code. All companies, people, items and numbers are fictional; e-mail domains are
`.example`. The previous probe simulator is kept in `../sim_probe_2026-11-15/`.

## Run

On gb10:

```bash
cd docs/reviews/2026-11-15-simulation/sim
python run_all.py                # live LLM (17 calls)
./simrun.sh final_a                                             # fresh database nativeflows_sim_final_a, SIM_LLM=off (recorded fixtures)
SIM_LLM=off python run_all.py    # dry run: each LLM step uses its labelled fallback fixture
python3 compare_traces.py build/runs/runA.json build/runs/runB.json   # equal apart from the LLM text?
```

- Database `nativeflows_sim` in container `nativeflows_lab_pg` (127.0.0.1:5561, user `lab`); override with `NATIVEFLOWS_SIM_DSN`. Each run
  drops and rebuilds schemas `nativeflows` and `types`, so it is rerunnable. The session sets `nativeflows.company_id` because the
  DS-05 tables have FORCE ROW LEVEL SECURITY.
- IDs come from seeded random streams per (flow, table) and timestamps from a business clock, so a rerun writes the same
  rows; only the LLM's text can differ (and a different LLM choice changes the branch it leads to).
- LLM: Gemma 4 31B at `http://127.0.0.1:18083` (OpenAI-compatible), temperature 0, thinking off, `response_format`
  `json_object`, at least 4 s between calls (`SIM_LLM_GAP`), one retry. A failed call uses a fixture labelled
  "LLM unavailable - fallback fixture" and is never shown as a live answer. Every exchange is also stored as
  `agent_run_step` rows (`llm_request`, `llm_response`).
- Exit code 0 when every flow check and every invariant passes. `SIM_ONLY=1,2,3` runs a prefix for development.

## Current state: integrated design (branch ds-production, HEAD bd459d4), flows 1-11

The docs copy is `../base-integrated/` (`git archive ds-production`); point `NATIVEFLOWS_DOCS` at `base-integrated/docs`. The loader
now builds 339 tables, including DS-28-settings, DS-28-34-configuration-artifacts, DS-33-analysis and DS-36-document-intake.
`simrun.sh NAME` creates a fresh database `nativeflows_sim_NAME` (use a lowercase name), runs with `SIM_LLM=off`, and copies the log and
trace to `build/runs/NAME.*`.

**Fixes for the design changes since ec0c126:**
- `outbox_event` and `audit_record` now require `causation_chain_id` and `causation_depth` (ADR-0058 rule 12).
  `platform.chain_for` gives each person, transport or job command a new chain, one per command and clock instant, so the audit row
  and the events share it. Everything an agent run does inherits the run's chain. An automation action sets `P.CHAIN_OVERRIDE`
  (the event's chain, depth + 1, its rule version).
- `sim_stubs.sql` adds `open_item_collection`, which is named in ADR-0048 and ADR-0063 rule 27 but has no DDL yet.
- No other change was needed: flows 1-6 and the UoM scenario pass unchanged.

**New helpers:**
- `flows/xdesign.py` loads the validation lab's reference functions by name (`t18`-`t25`: definitions only, checks skipped; t19's
  AI table is built up to its check section).
- `xdesign.py` also loads `setting_definition` from `catalogs/settings.csv`, reads settings in force (`get_setting`), writes
  `setting_value` rows (the trigger derives the change kind) and creates person-submitted change proposals.

**The new flows** run after the timeline of flows 1-6, from 2026-11-24.

| Flow | Steps | LLM | What it shows |
| --- | --- | --- | --- |
| 7 Intake (ADR-0057, ADR-0063 r27) | 10 | 0 | Mailbox `AP` with purpose supplier_invoice. Two 4-carton orders are received. An authenticated message from Omega's domain (exactly one partner) carries an XML and a PDF. Rung 1 (`l10n_vn.e_invoice_xml`) reads the XML: fields by XPath, rule runs, trust from `extraction_field_trust`. `ImportEInvoiceRecord` runs as system for the mailbox owner. The PDF is the XML's rendering (`rendering_of_parsed_xml`). The match is per piece (positions 0-96 H87, GR/IR debit 1,000,000 = receipt credit) and the accountant books the invoice. A stranger's PDF is stored only. A second invoice 2 days later with the same gross is `duplicate_document_suspected` under the default settings; it posts with `is_payment_blocked`, and `duplicate_document_review` releases the block with a reason. |
| 8 Barcode (ADR-0061, ADR-0063 r26) | 8 | 0 | Lot-tracked ADHESIVE in KGM, bought in bags of 5/2 kg; the bag's GTIN-14 is registered by the trigger. The GS1-128 scan `(01)(17)(10)(30)` resolves via `EvaluateBarcode` and fills the receipt line as 2 x-bag, which converts to 5.000 KGM (lot with expiry). An unknown EAN-13 gives `barcode_unknown`, and scan-to-confirm gives `scan_unresolved`. A label with only (15) stores `best_before_date` and leaves expiry empty (`best_before_fills_expiry` false). |
| 9 Workflows and settings (ADR-0058, ADR-0059, ADR-0063) | 14 | 0 | WH2 opens and the purchasing manager is scoped to WH1. She drafts the decision table `po_review_route`; its tests pass and it reaches backtested. Her rule `large_po_review` pins the table, and the database refuses its draft -> backtested move while the table is not active. She submits the activation and the owner approves. A 25 M order in WH1 triggers the dispatch (system for the owner, chain depth 1, rule version on the audit row): the table routes the work item to purchasing_manager. A 30 M order in WH2 is not evaluated (`automation_scope_skip` = 1). Tightening `cash.bank_charge.min_evidence_lines` 6 -> 8 takes effect at once. Loosening `auto_post.max_error_rate` 1 -> 2 is refused directly (`proposal_required`, and `ck_setting_value_loosen` in the database); the owner's proposal is approved by the chief accountant, and execution marks `bank_receipt_auto_post` evidence outdated. |
| 10 Analysis (ADR-0060) | 8 | 3 | A question. L1 proposes a plan without a limit, which `validate` refuses (`analysis_too_broad`). L1 retries and the corrected plan validates. Code computes purchases by supplier for November and renders the key facts. L3 returns a narrative plan of claim codes; `render_narrative` renders 2 claims and drops a false `largest_value`. The database refuses free text in `narrative_plan`. |
| 11 Production agent (ADR-0064) | 23 | 2 | KIT with V1 (bolted) and V2 (bonded). MO-B (30, start 12-10) reserves at release. MO-A (100, start 12-03) gets `ready_with_shortage` from `EvaluateProductionOrderRelease`, reserves the 192 free bolts, and raises `production_component_shortage`. D1 finds candidates of the default kinds. A proposal enables `transfer_reservation` (a loosening, approved by the owner); D1 then returns 3 candidates (cap 7, best of each kind first). L1 `choose` (stub) picks the transfer, which the agent drafts as a `TransferStockReservation` change proposal; the planner submits, the owner approves, and the executor recomputes the short quantity under the lock and moves 120 (trigger guard probed). A 120-piece receipt is followed by the sweep: MO-A gets 88 first, then MO-B 32. A shop-floor sheet is extracted (rung spreadsheet), and the tainted capture run's L1 `map_report` (stub) maps the remark to `surface_defect`. D2 drafts the confirmation with yield 48 and scrap 2 from the extraction fields; posting by the run and touching MO-B are refused, and the shop floor lead posts it. After the issue of 210 bolts and 2.5 kg, the usage variance comes from code (bolts target 192, variance 18; 190,700 is 9.2% of target cost, so the order ranks). |

**Where the 17 LLM calls sit:**
- flow 1: classify, extract.
- flow 3: classify, extract ×2, choose_item, configure ×2, write_text.
- flow 4: bank read_description.
- flow 5: planning explain.
- flow 6: purchase_invoice choose_item.
- flow 10: plan ×2, narrate.
- flow 11: production choose, capture map_report.

Flows 7-9 use no model: the XML rung, the barcode parser and the workflow dispatch are code.

**Checks:** 83 flow checks (54 for flows 1-6 and 29 new) and 27 invariants. Runs `build/runs/final_a.*` and `final_b.*` on fresh
databases: all 11 flows pass, 83/83 checks, 27/27 invariants, 17 LLM calls (recorded fixtures), 195 steps, 28 journal entries, and
`compare_traces.py` finds 0 differences. `trace/trace.json` is run B.

**Design gaps found:** see `../holistic/sim_final_observations.md`:
1. `open_item_collection` has no DDL.
2. Auto-post evidence does not record the setting keys it depends on.
3. A rule cannot leave draft while the table it pins is only backtested.
4. No eligible approver for automation activations with the DS-17 role templates (the simulation gives the purchasing manager
   configuration edit).
5. The chief accountant cannot submit policy-setting loosenings.

## Schema: what is real DDL and what is stubbed

`build_schema.py` calls the repo's combined loader `docs/reviews/2026-11-14-design-validation/lab/load_all.py`
(HEAD 46ece8b): all `docs/design/*.sql` (DS-05-platform, DS-06, DS-15, DS-20, DS-22-09-42, DS-35, DS-43-54, DS-56) in one
dependency order, 291 tables, extensions in schema `nativeflows`. Without that file it falls back to the earlier recipe
(`00_stubs.sql` minus the stub tables a DDL defines, `pg_trgm`, `load_ds06.py` order).

Still stubs:
- **Lab stubs** (`00_stubs.sql`): `account`, `system_account`, `fiscal_year`, `posting_period`, `posting_period_area_state`,
  `transaction_key`, `tax_code`, `applied_rate`, `close_task` (the chart and period DDL is not drafted).
- **Simulation stubs** (`sim_stubs.sql`, not design DDL): `tax_code` columns (code, direction, key), `tax_rate`, `tax_matrix`,
  `account` names, `account_determination`, `company_setting`, `e_invoice_record` and `_line` (columns of ADR-0051 rule 20's
  note; DS-24 pending), `landed_cost` and `_line` (DS-21/22 pending).
- Filled from the package and catalogs: TT99 chart (179 postable accounts), 90 determination rows, tax codes, rates and
  matrix from `design/DS-19-vietnam-tt99/`; system accounts, transaction keys, movement types, role templates and levels,
  segregation rules from `catalogs/`.

## What runs

Execution follows the business timeline: flows 1-3, flow 4 up to the approved order, flows 5 and 6, then flow 4 continues
(production, delivery, invoice, cash). Step numbers stay 1..N per flow.

| Flow | Steps | LLM | What it shows |
| --- | --- | --- | --- |
| 1 Customer and contact | 15 | 2 | Intake (system job, sender authentication, no match) -> tainted onboarding agent: L1 classify, L2 extract with source spans -> code checks (spans, l10n_vn tax ID rule, phones, admin unit, sender added by code) -> draft change proposal (duplicate check redacted to a count) -> the database refuses an untainted version from the tainted run -> the sales manager submits -> eligibility table -> the owner approves -> executor creates partner and contacts -> duplicate consumer -> the clerk confirms the match (wakes flow 3). The injected "set our credit limit" line has no field to land in. |
| 2 Price list | 7 | 0 | The sales clerk creates a sale list: product-level entry, quantity break, a later price end-dates its predecessor (S13), the exclusion constraint refuses an overlap, option extras and rates per mm, assignment to the customer, six `find_price` lookups. |
| 3 CPQ | 23 | 7 | Decision A1: the e-mail run is tainted, classifies and extracts, resolves only partner items (none), skips L4/L5 and hands over. The sales manager writes a note in their own words and starts the untainted run: L2, code token + fuzzy ranking, L3 choose among offered handles, L4 configure in a correction loop with `evaluate_configuration` (aluminium refused for width 1600, steel accepted), priced draft (procedure only), D3 checks, L5 text whose numbers must all be draft numbers, reply draft. The agent's Submit is refused; the clerk adds 10% and submits; discount and margin rules send it to pool `sales`; the chief accountant approves (sales manager is a writer, the owner is barred by segregation); the reply is sent. |
| 4 O2C | 26 | 1 | Order from the quotation (copied prices, taint OR); the clerk's Submit is refused (no CreateItem); the owner submits: configured item, MTO planning row, credit check -> pool `sales`; cost estimate released; the sales manager approves (credit release, rows released, ABS reserved). Later: production issue (621/152 on the cost object) and receipt (155/154), delivery (6321), invoice Issue -> issuing -> stub adapter accepts -> system Post (131 x2 installments, 5112, 5111, 33311), statement import, cascade (line 1 reference with installment prefix, capped at 85 for an unknown payer account; line 3 already posted; line 2 unmatched), bank matching agent L1 and suggestion, re-run at step 2, people post the receipts and match, credit hold cleared. |
| 5 Planning | 16 | 1 | Forecast (12 weeks: unindexed tier with `forecast_history_insufficient`), regenerative run: MTO production planned order pegged to the order line, explosion, net requirements with safety stock, lot sizes and lead times, exceptions -> work items; the never-tainted planning agent: code candidates, L1 explain with a recommended handle, draft proposal; the planner submits, the purchasing manager approves; execution; Delta planned orders converted into one purchase request; the planner converts the production planned order (production order in the same transaction), releases it, the owner approves (company rule, pool `mo`), cost object opened. |
| 6 P2P | 24 | 1 | Request submitted (rule pr_standard) and approved by the chief accountant; order from the supplier list (no approval under 50 M); goods receipt (GR/IR by unit positions) by a person outside the order; `ImportEInvoiceRecord` of a structured record; tainted purchase invoice agent: partner_item codes, L1 chooses among the supplier's items for the one unknown code, draft copied from the record, mapping proposal; price difference -> `is_match_exceeded` -> pool `po`; the purchasing manager approves (the chief accountant is a writer as workflow owner); the accountant posts (GR/IR cleared, 33882 -> landed cost -> 152, `tax_condition_pending`); the mapping is approved and stored; the cashier posts the payment (segregation leaves only the cashier), which resolves the tax condition; a resent invoice is refused. |

## Checks

After each flow its own checks (48 in all); at the end 21 invariants over the whole database: INV-01, 02, 05, open items
equal their lines, control accounts equal open items, INV-20 (inventory accounts = stock values), 21, 23, 92 (GR/IR zero),
82/84 (tainted documents posted by people), 85, 86, 88 (taint inherited), 17/225 (approvers human, not writers), 224, 230,
95 (matched lines refer to posted documents), 212 (budgets), 216 (tainted chains draft-only), 93 (price steps).

## Earlier state: ADR-0056 multiple units of measure (design branch ds-uom, HEAD ec0c126)

`load_all.py` now loads 292 tables. Units come from `catalogs/units.csv` and `unit-conversions.csv` (uuid5 ids, ADR-0006
rule 4); packaging units are company units (`x-box`, `x-carton`, `x-bag`); `uom_alias` holds intake texts. Every quantity
line carries the line unit block (rule 9); lines in the inventory unit get the `identity` snapshot through `flows/uom.py`,
which implements `convert_quantity`, exactness, `round_quantity` by use, `convert_part`, part-as-source returns, order-unit
lot sizing, the proposed-unit order and `normalize_unit_text` / unit-text resolution. Planned orders carry the order unit
(ABS is now planned in boxes of 10).

**The UoM scenario** (`flows/f6_uom.py`, flow 6 steps 25-47):
- Item master (owner): BOLT-M8 in `H87`, bought in `x-carton` = 24/1 (stated, exact); SEALANT in `KGM` (3 decimals), bought
  in `x-bag` = 7/3 (stated, inexact, check result `unit_inexact`). Supplier items with `order_uom_id`, minimum and multiple;
  prices per carton (250,000), per piece (11,000) and per bag (70,000).
- Planning: 100 pieces short -> 25/6 cartons -> 5 cartons (up) -> 120 pieces, excess 20; request and order keep the carton
  snapshot; the conversion step shows the `product_uom` row, 24/1, source `product`, and the GR/IR price 1,250,000 / 120 =
  31250/3 per piece kept exact (a rounded 10,417 would drift by 40 VND).
- Receipts: 70 pieces (other unit, converts on its own: positions 0-70, GR/IR 729,167), 2 cartons (cumulative part: 48,
  positions 70-118, 500,000), 2 pieces (118-120, 20,833). E-invoice line "THÙNG" resolves by alias to `x-carton`; the agent
  drafts without an LLM call; invoice part 120, match per piece 31250/3 on both sides; GR/IR debit 1,250,000; balance 0.
- Bags: 3 bags = 7.000 kg at 30,000 per kg; receipts 2.333 / 2.334 / 2.333 (69,990 / 70,020 / 69,990); return of receipt 2
  mirrors its 2.334 (GR/IR debit 70,020 at the latest positions), T = 0.001; replacement receipt 2.334 (70,020); e-invoice
  unit text "bịch" stays `unit_text_unresolved`, the agent proposes `CreateUomAlias`, the accountant submits, the owner approves;
  the accountant then books 3 bags = 7.000 kg, 210,000; GR/IR 0, no rounding clearing (R = I).
- Checks: INV-600 to INV-605 (70 lines in 22 block tables), INV-92, stock 120 H87 / 1,250,000 and 7.000 KGM / 210,000.

**Runs on ec0c126:** dry run, then two live runs (A and B, `build/runs/runA_uom.*`, `runB_uom.*`): all six flows PASS,
54/54 flow checks, 27/27 invariants, 12 live LLM calls per run (the UoM scenario adds none), 20 journal entries with 64 lines,
`compare_traces.py` 0 differences. `trace/trace.json` is run B.

## Earlier state: after the simulation review (design HEAD 32e7b1c)

The simulator follows `holistic/sim_decisions.md`:
- workflow owners: quotation and customer_onboarding run for the **sales clerk**, bank_matching and purchase_invoice for the
  **accountant**; the sales clerk submits the onboarding proposal and the quotation, the **sales manager approves** both and
  the order; the accountant submits the agent's purchase invoice and the **chief accountant approves** it (DS-17 cast);
- the configured item, its values, its planning row and the new order version are written by `system` on behalf of the
  submitter at Submit, so the **sales clerk submits the configured order** (no CreateItem, no owner);
- bank proposals are in `match_state` `proposed` (lines 1 and 3) until a person posts or matches;
- purchase request policy amount: purchase list, else last purchase price, else zero with `is_cost_unknown`; an empty credit
  limit means no credit check; `UpdateSupplierItem` on leaf `supplier_item`; L4 dropped values fail the round; L1 skipped on
  a person's note run; an agent version's `actor_id` is the run ID; EXT-RAIL keeps t06's negative intercept;
- pr.standard: the seeded roles plus the purchasing manager (DS-17); the purchasing manager approves the request when not a
  writer, else the chief accountant.

Dry runs (`SIM_LLM=off`) after the update, on both planning branches (fallback c2 and c3): all six flows PASS, 47/47 flow
checks, 21/21 invariants (logs and traces in `build/runs/dry_c2.*`, `dry_c3.*`). The live runs on ec0c126 above supersede these dry runs.

## Results of the first build (design 46ece8b, two full live runs, run A and run B)

All six flows PASS in both runs; 48/48 flow checks and 21/21 invariants pass; 12 live LLM calls per run, no fallback;
12 journal entries, 57 lines, trial balance zero. `compare_traces.py` finds the two traces equal apart from the LLM text
(see the report of the final run below the table in `trace/trace.md`). In both runs the planning agent recommended the
lead-time parameter change (c3), so the proposal updated the supplier lead time and the planner converted the Delta
planned orders directly; with c1/c2 the executor converts and drafts the request for the approver (run 1 of the day took
that path, also PASS).

## Design findings of the first build (gaps and guesses; items 1, 2 (guards kept), 3-5, 8-17 were decided in 32e7b1c, item 6 is with the author)

1. **F1 vs DDL.** ADR-0048 rule 9 note (F1) leaves a line `proposed`; DS-05 `ck_bank_statement_line_match_state` allows only
   unmatched, matched, ignored. The simulation stores a proposal as `unmatched` with `proposed_document_id` and score.
2. **The bank agent's suggestion cannot change the cascade.** ADR-0051 rule 18 re-runs step 2 with the suggested tokens under
   step 2's own guards (whole, reference-shaped tokens of the description). Those are exactly the tokens step 2 already tried at
   import, so the re-run never finds more (trace 4.20: the payer wrote `C26TSM00000123` for `C26TSM-00000123`). Only the
   stable payer token (rule 19) has an effect. A normalized comparison (separators removed, the package's invoice-number
   pattern) is needed for the LLM step to be worth a call.
3. **No sales role can submit a configured order.** ADR-0045 rule 16 and ADR-0046 rule 11 need `CreateItem` (product edit) at
   the order's Submit; only the owner template has product edit. The simulation shows the clerk's refusal and lets the owner submit.
4. **start_agent:quotation only for the sales manager** (platform decision 12 interim). The A1 path is then started by the sales
   manager, who becomes a writer of the quotation and cannot approve it, although DS-17 adds the sales manager to `sales.standard`
   to approve quotations. Give the clerk the capability, or accept that someone else approves.
5. **Purchase-invoice workflow owner vs the DS-17 cast.** Decision 12 makes the chief accountant the workflow owner; the run acts
   for them, so ADR-0017 rule 16 excludes them from approving, while DS-17's note says the chief accountant approves. The
   simulation lets the purchasing manager (po.standard member) approve.
6. **A submitter who did not edit may approve.** ADR-0055 rule 7 condition 5 excludes writers only; `approver_is_submitter`
   applies only to agent promotion. The accountant who submitted the agent's invoice unchanged is eligible to approve it
   (trace 6.14). "A person submits, a different person approves" is not enforced for ordinary documents.
7. **Owner vs segregation.** The owner template holds both sides of price_list_vs_sales_approval, partner_vs_purchase_invoice and
   role_administration_vs_posting. Block mode exempts the owner's assignments (catalog fix), but approval condition 7 still bars
   the owner from approving quotations and orders (trace 3.20). State whether the exemption reaches approval eligibility.
8. **Policy amount of a purchase request.** DS-17's pr rules use `amount_company_min`, but a request carries no price and ADR-0043
   rule 4 defines no policy input for it. The simulation values it at the supplier's purchase list.
9. **A13 and pool pr.** When an approved planning proposal converts, the request is written for the approver; if that is the
   purchasing manager, they cannot approve the request in `pr.standard`, where DS-17 placed them.
10. **CreatePartner defaults (A12 still open).** Credit limit 20,000,000 VND, payment term SPLIT-15-45, default sale list,
    receivable 131 by determination: simulation company settings, no setting keys exist. The meaning of a null credit limit stays open.
11. **Lead-time update command.** ADR-0024 rule 23 / ADR-0051 rule 24 name "a parameter or lead-time update" but no command or
    authorization leaf; the simulation uses `UpdateSupplierItem` on node `planning`.
12. **A dropped LLM number can be replaced by a default.** In one live run the LLM answered height 550 after an aluminium violation;
    the span check dropped it and `evaluate_configuration` completed with the default height 600, which would have priced a
    different unit silently. ADR-0051 rule 15 L4 does not say a dropped value fails the round; the simulation feeds it back.
13. **L1 on a person-started note run** is not specified (ADR-0051 rule 15); skipped.
14. **Configured item on the order line.** Filling `item_id` at Submit changes the line; the simulation writes a version by the
    submitter (INV-10), which the ADRs do not state.
15. **DS-43 rejects the t06 super BOM.** `ck_bill_of_materials_component_quantity` refuses EXT-RAIL's negative intercept
    (−0.4 + 0.001 × width); re-parameterized as 0.00075 × width.
16. Name-similarity threshold for duplicates (ADR-0019 rule 19) is unnamed; 50 (token-set ratio) is used.
17. `actor_id` of an agent-written version is not specified; the agent type's ID is used.
18. Production cost settlement (ADR-0035 rule 5) is period-end and not simulated: 621 and 154 stay on the cost object.
19. Simulation choices that are not design gaps: the supplier delivers FRAME-L early (expedited); the e-invoice adapter is the
    ADR-0028 rule 12 stub; tax ID validation is the package's check digit only; unit texts map through a small stub table.

## Trace format (2.0)

`trace/trace.json` keeps every field the video pipeline reads (`seq, flow, step, title, title_vi, actor_kind, actor,
function, inputs, outputs, policy, db_effects{rows_written, journal_entries}, status, llm{...}, notes`) and adds:
- `meta.format_version`, `meta.schema` (loader, files, lab and simulation stubs), `meta.tables`, `meta.lanes`; top-level `cast`;
- per step: `lane` (`person`, `llm`, `det`, `system`, `db`), `lane_name`, `mode`, `command`, `rule`, `policy_decision`
  (outcome, rank, pool, pool selection, plan of stages, matched rules, floors, inputs, taint), `approval` (stage, conditions,
  permission), `events`, `work_items`, `deterministic` (what the deterministic layer did);
- `llm.output_schema`, `llm.seat`; journal lines gain `account_name_vi`, `transaction_key`, `cost_object`; entries gain `document`;
- flows gain `steps` and `llm_calls`; checks gain `rule`.
`actor_kind` keeps its four values (`system` and `db` lanes map to `system`/`deterministic`); database steps have functions
starting with `trg_`, `ex_` or `ck_`, which `build_site.py` already puts in the database lane. Function names changed with the
design: e.g. `L4 configure`, `EvaluateConfiguration`, `ListAllowedCommand(ApproveQuotation)`, `match_bank_line x3`.

## Files

```
sim/
  README.md            this file
  run_all.py           entry point
  build_schema.py      schema load (load_all.py, else the recipe)
  sim_stubs.sql        simulation stubs (not design DDL)
  compare_traces.py    reproducibility check
  flows/  core (DB, IDs, clock, trace, LLM gateway), platform (permissions, documents, taint, events, work items, policy,
          pools, eligibility, agent runs), ledger (posting, determination, stock), pure (configuration, pricing, GR/IR,
          match, cascade, forecast, calendars, rank_candidates, package rule stubs), md, commerce, seed, common,
          f1..f6, f6_uom, f7_intake, f8_barcode, f9_workflow_settings, f10_analysis, f11_production, xdesign (lab functions,
          settings, proposals), checks, render
  simrun.sh            fresh-database run with recorded LLM fixtures
  trace/trace.json, trace/trace.md
```
