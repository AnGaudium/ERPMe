# ADR-0025: Seams for production and asset subledgers

Status: accepted (2026-11-14) under ADR-0005, reviewed by Claude Fable 5.2 (builder Claude Opus 5.5). Design item: DS-41 (new). Related decisions: D5, D6. Principles 5, 6, 13. Build principles B1, B7, B8. ADR-0004, ADR-0005, ADR-0010, ADR-0012, ADR-0014, ADR-0015, ADR-0018, ADR-0020, ADR-0021, ADR-0022, ADR-0023, ADR-0024.

## Decision

Production and production costing (Phase 2), and fixed assets and loans (Phase 3), are designed in detail only when they are built (B7). They start after Phase 1 has gone live with real data (roadmap). Four things would then be costly or impossible to change:
- the journal line;
- the material document line;
- the system chart, frozen to additions only at the step 0 gate (ADR-0010 rule 9);
- the costing solver.

This ADR fixes those now, at no cost to Phase 1:
- **Dimensions.** Nullable `cost_object_id` and `fixed_asset_id` on journal lines, and `cost_object_id` on material lines, with stub tables.
- **Control kinds.** Three subledger kinds: `cost_object`, `fixed_asset` and `loan`. Each is enforced per company only from an irreversible activation that reclassifies the existing balance into the subledger, so Phase 1 accountants keep posting as today.
- **System accounts.** Production cost leaves are added. An explicit decision is recorded for every account a later subledger could need.
- **Costing solver.** It is stated over typed nodes and the period's value flows, so cost objects join later as new node and edge kinds.

Everything else for these phases is additive: new tables, movement types, transaction keys, modules and enumeration values.

### Rules

**Dimensions and stub tables**

1. `journal_line` gets two nullable dimensions (ADR-0014 rule 9: a new dimension is a nullable column added by ADR): `cost_object_id` and `fixed_asset_id`. `material_document_line` gets nullable `cost_object_id`, for consumption into a cost collector and output from it. These columns stay empty and out of command schemas until their phase.
2. Stub tables:
   - `cost_object` and `fixed_asset` are created now with only `id`, `company_id`, `code` and `name`, unique on (`company_id`, `code`), with RLS. The foreign keys therefore exist from the first migration.
   - `cost_object` is a cost collector. Its kinds and lifecycle (by order, product, process or period) are designed in Phase 2. How Vietnamese regimes collect production cost and value WIP at period end is an author question. `fixed_asset` is designed in Phase 3.
   - Both are owned by `ledger` until their phase modules exist: `production` (layer 3, Phase 2) and `assets` (layer 3, Phase 3; ADR-0022 rule 2).

**Subledger control kinds**

3. ADR-0010 gets three gated control kinds. Lines on these accounts must carry the listed dimensions once the kind is active: Refined by [ADR-0026](0026-open-item-core.md) rule 13: one `loan` item per drawdown, grouped by the contract's `reference`.

   | Control kind | System accounts | Lines must carry |
   | --- | --- | --- |
   | `cost_object` | `inventory_work_in_process`; the new `production_cost` leaves (rule 5) | `cost_object_id` |
   | `fixed_asset` | `fixed_asset_tangible`, `fixed_asset_intangible`, `fixed_asset_investment_property`, `fixed_asset_other`, `fixed_asset_accumulated_depreciation`, `construction_in_progress` | `fixed_asset_id` |
   | `loan` | `borrowing`; the new leaf `receivable_loan` (loans granted) | `partner_id` and `open_item_id` (one open item per loan contract) |

4. Activation:
   - **The command.** A gated kind is enforced for a company only after `ActivateSubledger` (`human_only`). The command is unique per (company, kind) and irreversible. It writes a `subledger_activation` row (company, `control_kind`, `effective_from`, the reclassification document).
   - **The date.** `effective_from` must be the first day of a posting period, and every earlier period must be `locked` in area `general` (ADR-0012), so no backdated line can change the balance that was reconciled.
   - **Reclassification.** Activation posts a document of type `subledger_reclassification`, which only `ActivateSubledger` creates, dated `effective_from`. For each account, it credits the undimensioned balance and debits it per asset, cost object or loan, from the opening detail the command carries. The per-dimension lines must sum to the account's balance at `effective_from`, otherwise the command is rejected. Its undimensioned lines are the single exception to the dimension rule below and to INV-70. From then on, the account equals the sum by dimension (DS-16).
   - **After activation.** Lines dated before `effective_from` on those accounts are rejected (`subledger_activation_date_not_reached`). Lines dated on or after it must carry the dimensions (`control_dimension_missing`).
   - **Before activation.** The account's **effective control kind** is `none`. The effective kind (company, system account, posting date) is read by:
     - ADR-0014 rule 10 (required columns and the flagged manual-journal rule) and its trigger;
     - ADR-0010 rule 12 (moving balances);
     - ADR-0012 rule 4 (posting area).

     The catalog value is read by account determination (ADR-0015 rules 4, 13) and INV-16.
   - **Existing kinds.** `inventory`, `receivable`, `payable` and `gr_ir` are active from company creation.
   - **Posting area.** The three gated kinds are in area `general` (ADR-0012 rule 4), as are depreciation and WIP close tasks.

**System chart rows (changed in 0.1.0, before release 1.0.0)**

5. Rows changed now:
   - **New production cost accounts.** A node `production_cost` under `expense`, with the leaves `production_cost_material`, `production_cost_labor`, `production_cost_overhead` and `production_cost_other`, control kind `cost_object` (overhead lines need a cost object once active; how overhead is allocated belongs to the cost collection question). `expense_other` no longer mentions production costs. Which operational accounts map to these leaves (for example TT99 621, 622, 627, or the period method 631) is DS-19's and the author's (spec 08: unverified).
   - **New loan account.** `receivable_loan` under `receivable`, control kind `loan`, for loans the company grants, so they have a home before the chart freezes.
   - **Control kinds set.**
     - `inventory_work_in_process`: `cost_object`;
     - the fixed asset leaves and `construction_in_progress`: `fixed_asset` (assets under construction settle into fixed assets);
     - `borrowing`: `loan`.
   - **Kept as `none`, decided.**
     - `prepaid_expense`: allocation schedules can refer to journal lines without a control kind.
     - `receivable_other` and `financial_investment_other`: loans granted now go to `receivable_loan`. If a later subledger is ever needed on these accounts, the cost is a new operational account and a balance transfer (ADR-0010 rule 12).
   - **The catalog grows** to 116 accounts, 98 of them postable. After the gate these choices could change only by a superseding ADR on a reserved rule (spec 06 rule 1), so they are made now.

**Costing solver**

6. ADR-0020 rule 12's exact solve uses typed nodes and edges:
   - **Stock nodes** are (item, valuation area) (ADR-0020 rule 2). Phase 2 adds **cost-object nodes**.
   - **Edges** are the period's value flows: transfers in Phase 1; consumption into a cost object and output from it in Phase 2.
   - **Solve order.** The solver works through the strongly connected components in topological order, each as one exact rational linear system. A singular component keeps the preliminary price for its nodes under ADR-0020 rule 13; other components are solved normally. Multi-level bills of materials, by-products and rework cycles therefore need the same solver with new node and edge kinds.
   - **Planning.** Planning (ADR-0024 rule 16) shares item and warehouse identities and, in Phase 2, the bill of materials, but not a data structure. Its graph is master-data routes and must be acyclic; the costing graph is actual flows and may have cycles.
   - **Step 3.** The step 3 algorithm spec implements this formulation, and the naive recomputation (DS-16 rule 29) uses the same nodes.
   - **WIP offsets.** Costing adjustment lines that offset to WIP through the `consumption` key carry the original line's `cost_object_id`.
7. Price control:
   - Enumeration values are text with a check (ADR-0004 rule 14), so further methods are cheap to add. The list of methods (standard, moving average, FIFO, specific identification) stays open and is an accounting choice for later.
   - The expensive constraint is ADR-0018 rule 18: `price_control` cannot change once a product has stock postings. A later ADR may allow a dated change at the start of a period after close; rule 18 is to be amended then.

**Additive later**

8. Phase 2 production adds, without touching the core:
   - **Tables:** `bill_of_materials`, and the full `cost_object`.
   - **Catalog entries:** movement types (issue to cost collector, receipt from it, by-product, disassembly), costing roles (`production_input`, `production_output`) and WIP and settlement transaction keys.
   - **Module:** `production`.

   The landed cost consumer split (ADR-0021 rule 7) and reservations (ADR-0023 rule 11) already treat production consumers and demand lines generically.
9. Planning's design is [ADR-0024](0024-planning.md). Bills of materials become one more edge type there, and one more node and edge kind here.
10. Phase 3 assets and loans add:
    - the `assets` module, depreciation runs as close tasks (ADR-0012), and `ActivateSubledger` with the asset register as opening detail;
    - loans as partner open items on `borrowing` and `receivable_loan`, activated with the contracts as opening detail.

    Whether loans are managed per contract as open items, and whether `borrowing` is then revalued per loan open item instead of at balance level (spec 05), are author questions; the Phase 3 design settles them.

## Context

- **Origin.** The author asked whether production, production costing, warehouse management and planning should enter the overall design now. On 2026-11-14 he agreed to seams instead of full designs, moved warehouse management into Phase 1 (ADR-0023) and had planning designed (ADR-0024).
- **Constraints.**
  - B1, B7, B8.
  - ADR-0010 rule 9: the chart is frozen to additions at the gate. ADR-0010 rule 12: a mapping is frozen at the first posting.
  - ADR-0014 rules 9, 10 and 17: subledgers are views over journal lines.
- **SAP practice, concepts only.** CO orders as cost collectors that carry WIP and settle; material ledger multilevel actual costing; asset accounting with reconciliation accounts and a transfer of old balances at go-live.
- **ERPMe's own answer.** The activation date with a reclassification document lets a chart that cannot change its control kinds after release still gain subledgers safely.

## Options considered

| Option | For | Against |
| --- | --- | --- |
| Seams now, detailed design per phase (chosen) | Core stable after go-live; no speculative frameworks | Reserved columns stay empty for a long time |
| Full design now | Everything known up front | Months of design; no customer to validate; rework likely |
| Nothing now | Fastest | Control kinds impossible after the gate; journal migrations of real data |
| Control kinds active from company creation | Simpler | Blocks Phase 1 accountants' journals on WIP, assets and loans |
| Leave `none` and add a subledger column to the catalog later | Additive | Two sources of truth for what an account requires; every rule would read both |
| Activation keyed by system account | Finer | More rows, and the same effect for these groups |

## Constraints that come with the decision

- **System chart:** ADR-0010 Decision paragraph and rules 5 and 9 (DS-41 may change rows in 0.x), plus system-accounts.csv.
- **Journal and periods:**
  - ADR-0012 rule 4: area `general` for the gated kinds.
  - ADR-0014 rules 9 and 10 (effective control kind), plus the DS-06 DDL (columns, stub tables, header).
- **Inventory and planning:**
  - ADR-0020 rules 3 and 12 (text amended for per-component fallback).
  - ADR-0018 rule 18 note.
  - ADR-0022 rule 2: `production`, `assets`.
  - ADR-0024 rule 16: points here.
- **DS-04:** command `ActivateSubledger` (`human_only`); errors `control_dimension_missing` (trigger-level failures map to it) and `subledger_activation_date_not_reached`.
- **DS-16:** INV-70 (a line on an account whose control kind is active for the company on its posting date carries that kind's dimensions, except the undimensioned lines of the `subledger_reclassification` document; and no line refers to another company's cost object or fixed asset). The "account equals subledger" invariants are reserved by name, one per gated kind, and added with each phase. A new subledger group: 70–79.
- **Glossary:** cost object, fixed asset, subledger activation, effective control kind, costing graph; the verb `Activate`.

## Revisit when

- An assembly customer's costing method contradicts the cost-collector or solver model.
- TT99 verification requires a price control other than periodic average in Phase 1.

## Documents updated

- **Chart and catalogs:** [docs/adr/0010-system-chart-of-accounts.md](0010-system-chart-of-accounts.md), [docs/catalogs/system-accounts.csv](../catalogs/system-accounts.csv).
- **Journal and periods:** [docs/adr/0012-posting-periods-and-closing.md](0012-posting-periods-and-closing.md), [docs/adr/0014-universal-journal.md](0014-universal-journal.md), [docs/design/DS-06-universal-journal.sql](../design/DS-06-universal-journal.sql).
- **Other ADRs:** [docs/adr/0018-product-and-item-model.md](0018-product-and-item-model.md), [docs/adr/0020-inventory-and-costing-model.md](0020-inventory-and-costing-model.md), [docs/adr/0022-repository-and-engineering-conventions.md](0022-repository-and-engineering-conventions.md), [docs/adr/0024-planning.md](0024-planning.md).
- **Invariants:** [docs/design/DS-16-invariants-and-harness.md](../design/DS-16-invariants-and-harness.md), [docs/catalogs/invariants.csv](../catalogs/invariants.csv).
- **Glossary and error codes:** [docs/spec/00-reading-guide.md](../spec/00-reading-guide.md), [docs/design/DS-04-command-envelope.md](../design/DS-04-command-envelope.md).
- **Tracking:**
  - [docs/design/backlog.md](../design/backlog.md): DS-41 row.
  - [docs/adr/README.md](README.md): index.
  - [docs/open-questions.md](../open-questions.md): manual WIP before activation; cost collection and WIP valuation under TT99 and TT133; loans per contract.
  - [docs/runbook/step-log.md](../runbook/step-log.md): entry at acceptance.
