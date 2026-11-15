# ADR-0032: Phase 1 scope: the complete core, with production

Status: accepted (2026-11-14). The scope and the production design principle (rules 1–3) are the author's decisions of 2026-11-14 (ADR-0005 item 2). The technical parts (the design items DS-51 to DS-55 and design before build) were accepted under ADR-0005, reviewed by Claude Fable 5.2 (builder Claude Opus 5.5). Design item: DS-50 (new). Related: ADR-0005, ADR-0018, ADR-0020, ADR-0022, ADR-0023, ADR-0024, ADR-0025; spec 09, 10, 11.

## Decision

On 2026-11-14 the author decided that every capability a customer cannot operate without is built in Phase 1, in full depth. The author prefers a longer build and a product people can use to a fast demo whose structure must later be reworked. On the same ground, production moves into Phase 1, so that ERPMe can be offered to manufacturers. The author also set the principle for production: a general core that is not built for one industry, learned from SAP's core, simplified, agentic-native and not copied blindly. Production costing likewise follows best practice.

| Area | Before | Now |
| --- | --- | --- |
| Production (multi-level BOM, production orders, production costing, disassembly) | Phase 2, designed only when built (ADR-0025) | Phase 1, designed in full now |
| Multi-level MRP | Not designed; planning's phase was an open question (ADR-0024) | Phase 1, as part of planning |
| Planning (ADR-0024) | Phase open | Phase 1 |
| Warehouse management and planning lists (ADR-0023, ADR-0024) | Cuts were proposed (assessment OPT-12) | No cut |
| Subcontracting | Not planned | Phase 1, with production |
| Fixed assets, loans, other candidates | Phase 3 | Unchanged until the author decides each one (open question) |

### Rules

1. **The scope rule.** A capability belongs in Phase 1 when a customer in the target segments cannot run their business without it. The target segments are trading companies and manufacturers. Inside Phase 1, "built thin" (spec 10) still applies to features whose thin form does not block operation, such as the policy rule language or a single LLM provider. It no longer applies to production.
2. **The production design principle.** The production core is general, not built for one industry. Concepts come from SAP's production planning and product costing:
   - bills of materials, routings and work centers;
   - production orders and order types for discrete and batch manufacturing;
   - cost estimates, actual costs, work in process, variances and settlement.

   Each concept is simplified to what a mid-size manufacturer needs, and each workflow is agentic-native: deterministic commands, simulation before execution, agents that propose plans, shortages and variances for humans to approve. Industry features, such as product configuration for made-to-measure products, are added as data and configuration on this core, never as a separate core.
3. **Costing by best practice.** Production costing follows best practice and Vietnamese rules together:
   - a planned cost estimate per product;
   - actual costs collected per cost collector;
   - work in process valued at period end;
   - variances analysed by category;
   - actual cost settled to stock and to cost of goods sold through the existing exact solver (ADR-0025 rule 6).

   The cost estimate is a benchmark for variances; stock stays valued at periodic actual cost (ADR-0020 rule 12). Whether standard cost becomes a valuation method stays the author's (spec 09 costing row, spec 08). Methods, normal capacity, overhead allocation and WIP valuation are accounting choices. DS-53 proposes them as flagged interims for the author (ADR-0005 item 1). Note: "best practice and Vietnamese rules together" reads "best practice; regimes configure" ([ADR-0053](0053-core-neutrality.md) rule 13).
4. **ADR-0025 is superseded in part.** Production no longer waits for Phase 2 or for "design when built". Superseded:
   - the opening sentence;
   - rule 2's "kinds and lifecycle are designed in Phase 2";
   - rule 8's "Phase 2 production adds";
   - the revisit trigger on an assembly customer.

   The seams stay and are the base of the production design: `cost_object`, the `cost_object` control kind with activation, the production cost accounts and the typed costing solver. The fixed asset and loan parts are unchanged (Phase 3).
5. **Design before build.** These new design items design production completely before the build step that implements it, and are reviewed like the others. Their feature lists are the agent's proposal under rules 2 and 3, and the author confirms them (open question).

   | Item | Content |
   | --- | --- |
   | DS-51 | Production master data: bills of materials (multi-level, alternatives, phantoms, by-products and co-products), routings, work centers, production versions, capacity calendars |
   | DS-52 | Production orders and shop floor: order types for discrete and batch work, lifecycle, staging and issue or backflush, operation confirmations, receipts, scrap, rework, disassembly; reservations and warehouse tasks for components; quality inspection on output |
   | DS-53 | Production costing (rule 3): cost estimates, cost collectors, WIP at period end, overhead allocation at normal capacity, abnormal costs, variances, solver nodes, activation of the `cost_object` subledger |
   | DS-54 | Multi-level MRP inside planning: BOM explosion with low-level codes, dependent demand, lead-time offsetting, planned production orders, a capacity check, conversion |
   | DS-55 | Subcontracting (in Vietnamese, gia công): materials sent to a processor, the processing fee, receipt of finished goods, and the customs reporting of processing types where they apply |

   The production agent workflow is added to DS-34. When the production design is done, agents run design assessment 2 of the production flow (demand → MRP → production order → material issue → output → costing → cost of goods sold) as the first assessment was run. Its reports go in `docs/reviews/<date>-production-assessment/`.

   The production agent is design item DS-57, designed before the production core step ([ADR-0051](0051-agent-workflows.md) rule 29).
6. **Synthetic data.** DS-17 adds a fictional Vietnamese manufacturing company with multi-level bills of materials, production, subcontracting and production cost closing. It is due at the gate of the production core step. The production design items add their edge cases.
7. **Author-owned documents.** The roadmap, build order, MVP scope, vision, specs and runbook are the author's documents. This ADR proposes their changes as an open question, with draft wording:
   - **Spec 09 (MVP scope):** production rows move to Phase 1, including MRP, routings, operations, shop floor and quality. "MVP is Phases 1 and 2" becomes "MVP is Phase 1".
   - **Spec 10 (roadmap):**
     - Phase 1 adds production, multi-level MRP and subcontracting, and Phase 2 "Assembly" is removed.
     - The Phase 1 gate adds, for a manufacturing customer, production cost closed for at least one period and matching an independent recomputation. The current Phase 2 gate compares with a manual spreadsheet; this change of reference is the author's (ADR-0005 item 3).
     - The pilot criteria allow a manufacturing pilot.
     - The lean-scope sentence "only what a trading business needs" covers manufacturers too.
     - The planning-phase line and "assembly (Phase 2)" in the after-Phase-1 list are removed.
     - The months are re-estimated.
   - **Spec 11 (build order):**
     - step 3's "BOM levels in Phase 2" points to the production core step;
     - a production core step after step 4, with the synthetic manufacturing company in its gate;
     - MRP is built with planning after step 5;
     - the step 10 large dataset includes the manufacturing company;
     - the step-to-phase mapping is updated;
     - the list of agents done before platform completion gains the planning and production agents.
   - **Spec 00 rule 2, spec 01, spec 05, spec 08 and spec 12:** "(Phase 2)" labels, "trading and assembly businesses", and the dataset list gain manufacturing. README and the risks file likewise.
   - **Runbook:** steps 0–4 (DS-09 "BOM levels left for Phase 2"), and go-live's list of done design items (through DS-55).
   - **Decisions for the author:**
     - whether the production core step belongs to Phase 0 or Phase 1;
     - whether it can come before step 5, given DS-52's use of warehouse tasks and reservations;
     - where subcontracting is built;
     - the target completion date for assembly-type manufacturing.
8. **Questions this decision answers:**
   - planning's phase (DS-43): Phase 1;
   - the proposed cuts of warehouse and first-slice planning features (OPT-12): no cut. Confirming the items left for later stays open;
   - production cost collection and WIP under TT99 and TT133 (DS-41): still open, but needed before DS-53 rather than Phase 2.
9. **Still open.** The author decides, one by one, which other candidates count as core for Phase 1:
   - group-currency logic (OPT-13);
   - derivation traces beyond costing (DS-45);
   - fixed assets and loans (Phase 3);
   - payroll;
   - multi-level approval.

   Note: the author asked (2026-11-15) for approval pools with several stages; they are designed in [ADR-0055](0055-approval-pools-and-stages.md) (proposed).

   Note: [ADR-0055](0055-approval-pools-and-stages.md) was accepted on 2026-11-15 (holistic review 2026-11-15, item P27).

   Note (catalog review, 2026-11-15): [ADR-0055](0055-approval-pools-and-stages.md) is accepted (2026-11-15).

## Context

The author's words, in summary: core capabilities should all be in Phase 1, because without them the product does not run. The author would rather spend more time on a usable product than save time on a demo that is hard to fix later because its structure was incomplete. For the same reason production enters Phase 1, to offer ERPMe to manufacturers. The production core is to learn from SAP, simplified and agentic-native, not industry-specific, with costing by best practice.

The agent's view, recorded for the author:
- **Structure.** The decision removes the main risk of the seams approach: production costing designed late against a core that cannot change after go-live.
- **Build order.** Keep the build in gated steps with real-scale synthetic data. Building everything before running anything carries its own risk.
- **Timing.** Manufacturers compare a running product with a design, so the build order should reach production early.
- **Estimate.** The agent estimates that production adds 4–6 months to the build.

## Options considered

| Option | For | Against |
| --- | --- | --- |
| Complete core with production in Phase 1 (decided) | One structure, designed once; manufacturers can be served | Longer build; a larger Phase 1 gate |
| Seams now, production in Phase 2 (ADR-0025) | Faster first go-live | Production costing designed after the core freezes |
| Production in Phase 1 without MRP | Smaller | Manufacturers cannot plan materials; MRP is core for them |
| An industry-specific production core | Fits one industry quickly | Every new industry is a rewrite; contradicts the author's principle |

## Constraints that come with the decision

- **ADR notes:**
  - ADR-0018 (kits and BOMs);
  - ADR-0020 (BOM levels);
  - ADR-0022 (module `production`);
  - ADR-0023 (no cut; kitting);
  - ADR-0024 (Phase 1; MRP is DS-54; its "Phase 2" labels);
  - ADR-0025 (superseded in part, rule 4).
- **Backlog:** DS-50 to DS-55; the DS-09, DS-17, DS-30, DS-31, DS-34 and DS-43 rows.
- **DS-17:** a note on the manufacturing profile.
- **Glossary:** cost object, costing graph and planned order lose their "Phase 2" labels; subcontracting is added.
- **Counts:** design items DS-01 to DS-55.
- **Open questions:**
  - author-owned document changes (rule 7);
  - production feature lists (rule 5);
  - other core candidates (rule 9);
  - the DS-43 and DS-41 questions updated.

## Revisit when

- The author changes the target segments or the go-live plan.
- The production design shows a capability that a target customer cannot do without and that is not yet listed.

## Documents updated

- **ADRs:** [docs/adr/0018-product-and-item-model.md](0018-product-and-item-model.md), [docs/adr/0020-inventory-and-costing-model.md](0020-inventory-and-costing-model.md), [docs/adr/0022-repository-and-engineering-conventions.md](0022-repository-and-engineering-conventions.md), [docs/adr/0023-warehouse-management.md](0023-warehouse-management.md), [docs/adr/0024-planning.md](0024-planning.md), [docs/adr/0025-later-phase-seams.md](0025-later-phase-seams.md): notes.
- **Design:** [docs/design/backlog.md](../design/backlog.md), [docs/design/DS-17-synthetic-dataset.md](../design/DS-17-synthetic-dataset.md).
- **Glossary:** [docs/spec/00-reading-guide.md](../spec/00-reading-guide.md).
- **Counts:** [docs/README.md](../README.md), [docs/design/README.md](../design/README.md), [docs/prompts/runbook-session.md](../prompts/runbook-session.md).
- **Open questions:** [docs/open-questions.md](../open-questions.md).
- **Index and log:** [docs/adr/README.md](README.md); [docs/runbook/step-log.md](../runbook/step-log.md).
