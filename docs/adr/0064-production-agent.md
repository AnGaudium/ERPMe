# ADR-0064: Production agent

Status: accepted (2026-11-15) under ADR-0005, reviewed by Claude Fable 5.2 (builder Claude Opus 5.5) after three review rounds.
Design item: DS-57 (its plan, reservation, capture and variance part; the master-data part is [ADR-0062](0062-product-engineering-workflow.md)). Related decisions: D2, D12. Principles 2, 3, 7, 12, 13. ADR-0004, ADR-0005, ADR-0017, ADR-0023, ADR-0024, ADR-0028, ADR-0029, ADR-0032 to ADR-0037, ADR-0042, ADR-0043, ADR-0050, ADR-0051, ADR-0055, [ADR-0057](0057-document-intake-and-extraction.md), [ADR-0058](0058-configurable-workflows.md), [ADR-0059](0059-ai-tuning-and-development-of-deterministic-functions.md), [ADR-0060](0060-agent-assisted-reporting-and-analysis.md), [ADR-0062](0062-product-engineering-workflow.md); ADR-0063 (configurable policy settings, drafted in parallel); spec 03, 14.

## Decision

ADR-0051 rule 29 left the production agents to their own ADR. The production rules already fix the safety frame: people release production orders, `CompleteProductionOrder` and `ReopenProductionOrder` are proposal-bound, capture runs are tainted, and the production agent may run `ReserveProductionOrderComponent` directly (ADR-0034 rules 5, 9, 12, 17). Vendors keep planning and execution deterministic and use AI to rank and explain exceptions, to choose among computed resolutions and to capture shop-floor facts. This ADR does the same and adds the deterministic functions the design still lacks.

**Three agent types.** `production` (readiness, the reservation sweep, shortages, order exceptions, completion, standards feedback) declares `may_read_untrusted: false` and is never tainted, so it may run the sweep. `production_capture` drafts shop-floor documents from outside reports; its runs are tainted and read one production order. `production_variance` explains variances on the analysis layer of ADR-0060. Planned orders stay with the `planning` agent; the production agent works from created production orders onward.

| # | Capability | Agent type | Output | Without a person per run? |
| --- | --- | --- | --- | --- |
| C1 | Release readiness and shortage triage | `production` | explanation in a work item note; the verdict is code | yes (read-only) |
| C2 | Component reservation sweep | `production` | reservations through `ReserveProductionOrderComponent` | yes; deterministic, no LLM |
| C3 | Shortage resolution | `production` | a draft, a drafted change order or a change proposal | no |
| C4 | Order exceptions and rescheduling | `production` | a draft update or drafted change order | no |
| C5 | Technical completion and stalled orders | `production` | a change proposal for `CompleteProductionOrder`, or a note | no |
| C6 | Shop-floor capture | `production_capture` (tainted) | draft confirmations, issues and receipts; a person posts | no |
| C7 | Variance ranking and explanation | `production_variance` | an explanation of checked claims | yes (read-only) |
| C8 | Standards feedback | `production` | a work item with code-computed statistics | no |

**New deterministic functions.** A cross-order shortage list, one release readiness evaluation, exceptions and action messages on real production orders with tolerance settings, a reservation priority, a reservation transfer between orders that runs only from an approved change proposal, upward pegging from an order to its end demand, an in-period usage variance and variance drivers per category, the extraction purpose `shop_floor_report`, confirmation checks for yield, activity and duplicates, and the production views of the query layer.

**Six hard locks; everything else is a setting.** Release timing, tolerances, grace days, thresholds, candidate kinds, capture sources and the production import's auto-post and its evidence are registry settings in the shape of ADR-0063, each with a safe default that reproduces today's behavior.

### Rules

**Agent types and boundary**

1. Three agent types of `agents` (layer 5) on the runtime of ADR-0050 and the common rules of ADR-0051 rules 1–9 (decision 1 of the chief architect, 2026-11-15). No new module; they read through registered queries and write through the commands of `production`, `inventory`, `planning` and `documents`.

   | Agent type | Scope kind and subject tables | `may_read_untrusted` | Field classes | Claimable work item kinds | Leaf (capability `start_agent:<type>` at `edit`) |
   | --- | --- | --- | --- | --- | --- |
   | `production` | `subject`: `production_order`, `production_version` | false | none | `production_component_shortage`, `production_order_exception`, `production_completion_candidate`, `production_order_stalled`, `production_standard_review` | `agent_production` |
   | `production_capture` | `subject`: `production_order`, resolved from a `document_extraction` (rule 19) | true | none | `shop_floor_report_extracted` | `agent_production_capture` |
   | `production_variance` | `subject`: `analysis_question`, `production_order` | false | `cost` | none; started by schedule, event or question | `agent_production_variance` |

   - **Seeded templates:** `production_planner` holds `agent_production` and `agent_production_variance` at `edit`, `shop_floor_lead` holds `agent_production_capture`, and `chief_accountant` holds `agent_production_variance` (ADR-0054 rule 24). The owner and IT administrator get them through their `agent` level.
   - **Wake-up.** Every claimable kind is declared `wake_up: always`, and no type declares `configurable_triggers` (ADR-0050 rule 12, [ADR-0058](0058-configurable-workflows.md)'s note).
   - **Why three.** Taint and promotion evidence stay apart. A tainted capture run could never run the sweep or read other orders; a clean `production` run never reads a report's free text.

   Note ([ADR-0072](0072-costing-sheet-and-cost-component-structure.md), proposed 2026-11-18): the `production` type gains the subject table `costing_sheet`. It drafts costing sheets, site assignments, detailed components and mappings only as change proposals, and rates only from a person's stated source or `GetCostingRateSuggestion`; the model never sees a rate (ADR-0072 rule 18).
2. Boundary with planning (decision 2): planned orders, their firming and conversion stay with the `planning` agent (ADR-0051 rules 23–25; ADR-0036 rule 12). The production agent works on production orders from `CreateProductionOrder` until they are closed, and no production tool list holds a planned-order command.
3. Common to the three types:
   - **Deterministic first.** Every quantity, date and amount comes from a deterministic function or is a stated value with its source (a span or an extraction field). Every number in model text appears in the step's input (ADR-0050 rule 36).
   - **Commands.** Workflow code builds each command from a checked output, simulates it, checks the plan, then executes it with the simulated `plan_hash` (ADR-0050 rule 32). Output schemas are `<AgentType><Step>Output`, version 1.0.0.
   - **Modes.** `off` (the default) → `shadow` → `assisted`, promoted by frozen evidence (ADR-0050 rule 14). Setting every production agent type to `off` stops a running sweep at its next call boundary, because the runtime checks the effective mode before each tool call.
   - **Owner.** Runs from events and schedules act for the agent type setting's `workflow_owner_id` (ADR-0050 rule 14). No `production_owner_id` is added (decided by the architect): that column already names the accountable human per agent type.

**Hard locks**

4. Six hard locks; no setting, policy rule or decision table changes them:

   | # | Lock | Enforced by |
   | --- | --- | --- |
   | 1 | No agent releases, posts, approves, issues or sends | tool lists (ADR-0050 rule 30; INV-214, INV-730) |
   | 2 | No model-originated quantity, date, price or cost | output checks (ADR-0050 rule 36); quantities copied as stated (INV-733) |
   | 3 | A tainted capture draft is posted only by a person | ADR-0043 rule 9, floor 3; `is_approval_hold_allowed: false` (INV-732) |
   | 4 | Proposal-bound commands stay proposal-bound: completion, reopen, planned orders, master data and `TransferStockReservation` | registry (ADR-0029 rule 2; rule 24) |
   | 5 | No reservation moves from one order to another without an approved change proposal, and no released order's version or revisions change | rule 24; ADR-0034 rule 8 (INV-734) |
   | 6 | Exceptions close only when a deterministic run no longer raises them; agents never close them | the work item kinds' resolution `system` (INV-737) |

**Deterministic functions**

5. `ListComponentShortage` (module `production`, computed query, `production_order` at `read`). One row per component line of orders in `draft`, `pending_approval` or `approved` and not technically complete, rework and disassembly orders included:
   - **Quantities**, in the inventory unit: required; open requirement = max(0, required − net issued − backflushed); reserved (open and picked reservations of the line's demand line); staged (picked to the supply bin); available to promise in the issue warehouse (`GetAvailableToPromise`); short = max(0, open requirement − reserved − available to promise), the order's own view, as `has_component_shortage` uses it.
   - **Uncovered**, the cross-order view the sweep acts on, computed before any filter of the call: per (item, issue warehouse), available to promise is allocated to the unreserved open requirements of every component line of the company's approved, not technically complete orders in the reservation priority (rule 7); lines of `draft` and `pending_approval` orders then take what is left, in the same priority. Uncovered = the unreserved open requirement the allocation does not cover. A filtered call returns the same values as the unfiltered one for the rows it returns.
   - **Dates and demand:** the line's `requested_date`; the earliest date the projection covers the short quantity, from `GetProjectedAvailability`, or none; the pegged end demand and its due date (rule 8).
   - **Filters:** item, warehouse, order, requested date range, `is_short_only` (default true: short or uncovered above 0).
   - **Order of rows:** the reservation priority (rule 7).
6. `EvaluateProductionOrderRelease` (module `production`, `Evaluate` query, `production_order` at `read`) returns one verdict for an order and business date:
   - **Reasons** (closed list, each with its class):

     | Reason | Class | Source |
     | --- | --- | --- |
     | `component_short` | material | a line of the order with short above 0 (rule 5) |
     | `work_center_overloaded` | capacity | `ListWorkCenterLoad` above available hours in a bucket of the order's operations |
     | `production_version_invalid`, `revision_invalid` | master data | version and revisions not valid on the order's dates (ADR-0033 rule 5) |
     | `subledger_not_active` | accounting gate | ADR-0034 rule 15 |
     | `output_serial_missing` | master data | serial-tracked output with fewer assigned serials than G when the version requires them at release (ADR-0034 rule 16) |
     | `external_supplier_missing`, `processor_route_missing` | master data | external operations (ADR-0037 rules 2–3) |

   - **Verdict:** `blocked` when any reason of class master data or accounting gate is present; else `ready_with_shortage` when material or capacity reasons are present; else `ready`.
   - **Consistency.** The `has_component_shortage` policy input at `Submit` (ADR-0034 rule 5 note) is true exactly when this evaluation returns `component_short` for the submitted version. No release-with-shortage setting is added: a company ranks such releases through its policy table.
7. Reservation priority, `production.rank_reservation_demand` (a pure function of `production`): component lines in order of `requested_date`, then the due date of the make-to-order demand the order serves (rule 8; lines without one last), then the order's document number, then line number. The sweep (rule 15) and the shortage candidates (rule 16) use it.

    Note (author's delegation, 2026-11-19): confirmed with [ADR-0023](0023-warehouse-management.md) rule 13: production keeps this order, a demand class of its own beside first come, first served.
8. `GetProductionOrderPegging` (module `planning`, computed query, `production_order` at `read`, since its subject is a production order): upward pegging from a production order, or one of its component lines, to end demand.
   - **Allocation:** the make-to-order link first (`for_demand_supply_line_id`, ADR-0034 rule 14); then the projection's allocation of supply to demand by date, the rule `ListPegging` uses for planned orders (ADR-0024 rule 20), level by level through parent orders' component lines.
   - **Rows:** level, order or demand line, quantity pegged, need date and the days late of the order's planned end against it. The pegged quantities of a level sum to the supply they peg.
   - **Agent runs** get the numeric projection of ADR-0050 rule 28, as for `ListPegging`.
9. `GetProductionOrderUsageVariance` (module `production`, computed query, `report_production` at `read`): quantities only, at any time, for an order and an optional posting-date range (the in-period variance):
   - **Components:** target at progress = required × progress / Q, progress being the cumulative yield + scrap of the component's operation, or the net main-output receipts over G for `backflush_at_receipt` and lines without an operation (the backflush rule of ADR-0034 rule 12); against net issued + backflushed.
   - **Operations:** actual activity quantities against the standards at the confirmed quantity; actual scrap against the operation's scrap rate, by reason code.
   - **Categories:** each line names the ADR-0035 rule 15 category it feeds: `input_quantity`, `resource_usage` or `scrap`.
10. `ListProductionOrderVarianceDriver` (module `production`, computed query, `report_production` at `read`; field class `cost` on amounts): the document lines behind each variance category of a settled order and period, by category and cost component: issue lines above requirement with their `reason_code` (`input_quantity`), confirmations with scrap and reason (`scrap`), activity lines (`resource_usage`), price differences per component from the settlement lines (`input_price`), fixed quantities and setup over the received quantity (`lot_size`), and the rest (`remaining`). The contributions of a category sum to that category's row of `production_order_variance` (INV-739). Agent runs get the numeric projection of rule 13.

    Note ([ADR-0071](0071-work-orders-and-shop-floor-execution.md), proposed 2026-11-17): the `scrap` driver also lists receipts with scrap and their reason (ADR-0071 rule 4).
11. Variance ranking, `production.rank_variances` (a pure function of `production`): an order ranks when its absolute variance reaches `production.variance.rank_threshold_percent` of its target cost or, when it is not 0, `production.variance.rank_threshold_amount`; the first `production.variance.top_n` by absolute amount, ties by document number.
12. `RunProductionOrderCheck` (module `production`, verb Run, effect class `other`, an internal system job on `production_order`, daily with an explicit business date and after each sweep; ADR-0007 rule 17). For approved orders that are not technically complete it raises and closes, one open item per order and kind:
    - `production_component_shortage` while a line of the order has short or uncovered above 0 (rule 5) and its requested date lies within `production.agent.readiness_horizon_days`, in every reservation mode, including lines beyond the window in mode `scheduled`;
    - `production_completion_candidate` when net main-output receipts reach `production.completion.propose_at_percent` of G (for a disassembly order, every co-product line reaches that share of its planned quantity) and every internal operation has a final confirmation or a cumulative yield + scrap at its expected quantity;
    - `production_order_stalled` when the order is `in_progress` and has no posting for `production.order.stalled_days` working days of the production warehouse's calendar;
    - `production_standard_review` (subject the production version) while the same driver (component, operation or scrap reason) ranks on at least `production.feedback.min_orders` orders or in `production.feedback.min_periods` consecutive periods and `production.feedback.enabled` is true; it closes when the driver no longer qualifies.
13. Production views of the query layer (ADR-0050 rule 51's later views), in schema `query`, each with record scope on `production_warehouse_id` and owner scope as the document views:

    | View | Over | Partner column | Subject column | Untrusted columns | Field class columns |
    | --- | --- | --- | --- | --- | --- |
    | `production_order_overview` | header, document state, execution state, version, revisions, G, Q, dates, received quantity, pegged due date | — | `id` | — | — |
    | `production_order_component_overview` | component lines with the quantities and dates of rule 5 | — | `production_order_id` | — | — |
    | `production_order_operation_overview` | operations with scheduled dates, expected quantity, confirmed yield and scrap, activities against standards | — | `production_order_id` | — | — |
    | `shop_floor_posting_overview` | lines of issues, confirmations and receipts with state, `entry_source` and posting date | — | `production_order_id` | — | — |

    - **Subject column.** A tainted run of scope `subject` on a production order passes `is_in_taint_scope` for rows whose subject column equals its subject. Reading an order's own lines as its subject is this ADR's reading of ADR-0050 rule 27, added to the grouped question on readings of spec 03 rule 1 ([ADR-0062](0062-product-engineering-workflow.md) rule 3 reads child rows the same way).
    - **Numeric projection.** A capture draft a person posted keeps its effective taint (ADR-0029 rule 9), and the run that wrote it keeps its taint record. For agent-run callers, `shop_floor_posting_overview` and `ListProductionOrderVarianceDriver` return such rows as the numeric projection of ADR-0050 rule 28: IDs, document numbers, quantities, dates, states and codes, never free text. Such rows do not taint and are not filtered from a clean run, so `production` and `production_variance` see every posting and the drivers still sum (INV-739). This reading joins the grouped question on spec 03 rule 1.
    - **Module queries** stay with their modules: `ListWorkCenterLoad`, `GetProductionOrderStatus`, `GetAvailableToPromise`, `GetProjectedAvailability` and the queries of rules 5–10 (ADR-0050 rule 52).

**Capabilities of the `production` agent type**

14. C1 release readiness and triage:
    - **Triggers:** `ProductionOrderSubmitted`; a daily schedule over approved and draft orders whose `planned_start_date` lies within `production.agent.readiness_horizon_days`; a planner's run on an order.
    - **D1 `gather`:** `EvaluateProductionOrderRelease`, `ListComponentShortage`, `GetProductionOrderPegging`, `ListWorkCenterLoad`.
    - **D2 `rank`:** code orders the orders by the pegged demand's due date, then days late, then the reservation priority.
    - **L1 `explain`** (seat analysis): input the verdicts, reasons and ranked facts. Output `ProductionExplainOutput`: `explanation` (at most 1,200 characters), `root_cause` (a reason handle offered, or `none`). Checks: the handle was offered; every number appears in the input. The model never sets or changes a verdict.
    - **Output:** a note on the order's work item (or an `agent_task` note) with the code's verdict beside the explanation. No command.
15. C2 reservation sweep (decision 3), a workflow of `production` with no LLM step, so it carries budgets, run records and modes:
    - **Triggers:** `GoodsReceiptPosted`, `StockReservationCanceled`, `ProductionOrderCompleted`, `ProductionOrderApproved`, the receipt events of stock transfers, and a daily schedule. It runs only while `production.reservation.mode` is not `off`.
    - **Steps:** `ListComponentShortage` for approved orders (in mode `scheduled`, only lines whose requested date lies within `production.reservation.window_days` of the business date); then, in the order of rule 7, `ReserveProductionOrderComponent` per order for its unreserved open requirement, simulated then executed; the reservation contract caps each at available to promise.
    - **What it may take:** available to promise only. The reservation contract never takes stock reserved for another order or demand (`stock_reserved`, ADR-0023 rule 13), so a sweep never moves a shortage onto someone else. Moving a reservation is rule 24's proposal.
    - **Concurrency:** `ReserveProductionOrderComponent` locks the order row (ADR-0034 rule 19) and computes each line's unreserved requirement under that lock, and the reservation contract locks the stock rows it reserves from (ADR-0027 rule 10). Two sweeps racing for one receipt therefore never reserve more than the stock or a line's open requirement (INV-735; a parallel test).
    - **Scope and budget.** Orders outside the workflow owner's record scope are skipped and counted in the run's note. A run that ends on its tool-call or row budget leaves the rest to the next trigger, which starts again in the same priority.
    - **Output:** one note per order: reserved and still short, per line. No person approves a run; the run is accountable to the workflow owner.
16. C3 shortage resolution:
    - **Triggers:** `production_component_shortage`; a planner's run on an order.
    - **D1 `candidates`:** `ListShortageResolutionCandidate` (module `planning`, computed query, `production_order` at `read`) computes candidates of the kinds enabled in `production.agent.shortage_candidate_kinds`, each with its computed effect on the order's start date and on pegged demand:

      | Kind | Candidate | Output when chosen |
      | --- | --- | --- |
      | `expedite_supply` | an open supply line whose `expedite` message would cover the shortage | a note to the buyer on the planning exception; the buyer acts |
      | `stock_transfer` | a warehouse whose available to promise covers the shortage | a draft stock transfer |
      | `alternative_version` | a production version valid on the order's dates whose structure does not use the short component; orders in `draft` or `pending_approval` only | a draft update of the order (re-explosion) |
      | `reschedule` | the earliest start the projection covers, dated by `plan_production` in mode `fixed` | a draft update, or a drafted change order of the dates |
      | `partial_staging` | release with the covered operations staged; the policy's shortage rank applies | a note to the releaser |
      | `transfer_reservation` | reservations of an order of lower priority (rule 7) | a change proposal with `TransferStockReservation` (rule 24) |
      | `split_order` | a change order reducing G to the covered quantity, plus a new draft order for the rest (decision 6) | the drafted change order and the new draft |

    - **Selection per kind** (deterministic; S = the line's uncovered quantity, d0 = the order's planned start):
      - `expedite_supply`: open purchase or transfer supply lines of the item and warehouse with an `expedite` message of the latest completed planning run whose proposed date is on or before d0; one candidate per line, covering min(S, its open quantity); a message of an older run is not used.
      - `stock_transfer`: per other warehouse of the company with a transfer route to the issue warehouse and available to promise above 0; covering min(S, that available to promise); effect date = business date + the route's lead time.
      - `alternative_version`: per valid version (ADR-0033 rule 13) that does not use the item, on orders in `draft` or `pending_approval`; covers S; effect date from `plan_production` with the version.
      - `reschedule`: one candidate, the first date on which `GetProjectedAvailability` covers the open requirement, scheduled by `plan_production` in mode `fixed`; none when the projection never covers it within the horizon.
      - `partial_staging`: one candidate when the order still has an uncovered line and at least one operation has every component line uncovered 0; it names those operations, covers 0 of S and keeps d0.
      - `transfer_reservation`: donor reservations, open and unpicked, of approved orders later in the reservation priority; one candidate per donor, covering min(S, its unpicked quantity, the target's short quantity of rule 24), that short quantity as of the query; execution recomputes it under the lock (rule 24), so the two may differ; the candidate states the donor's resulting short quantity and its pegged demand.
      - `split_order`: one candidate when 0 < covered G < G, covered G = the largest quantity the covered components support (the minimum over the order's lines with required above 0 of (required − uncovered) × G / required, rounded down to the item's unit's decimal places); a fixed-quantity line does not scale with G, so it allows a split only when it is fully covered (uncovered 0), and otherwise no split is offered; lines with required 0 are skipped; the new draft takes G − covered G.
    - **Effect, order and cap.** Each candidate carries its covered quantity, the resulting start date and the days late of each pegged demand before and after. The total order is: kind in the table's order; within `transfer_reservation`, the donor's reservation priority, latest donor first; then the resulting start date, the larger covered quantity, document number and line. The returned list holds at most 7: first the best candidate of each enabled kind that has one, in kind order, so no kind is crowded out; then the remaining places filled from the other candidates in the total order. Partial cover is offered and marked.
    - **L1 `choose`** (seat analysis): output `ProductionChooseOutput`: `candidate` (a handle offered, or `none`), `reason_codes`, `explanation`. It never writes a quantity or date.
    - **Approval.** A person submits every draft; change orders and proposals follow their pools (ADR-0055); a new draft order is released by a person's `Submit`. Alternative versions come only from the version selection function's valid set (ADR-0033 rule 13). Substitute components stay after Phase 1 (decision 5; ADR-0033 rule 17).
17. C4 order exceptions and rescheduling (decision: the gap "exceptions on real production orders"):
    - **Raised by the planning run** (ADR-0024 rule 21), stored in `planning_exception` and `planning_action_message`:

      | Kind | Raised when | Key |
      | --- | --- | --- |
      | `production_order_start_overdue` (exception) | approved, `not_started`, and `planned_start_date` + `production.order.start_grace_days` is before the planning date | order |
      | `production_order_overdue` (exception) | approved, not technically complete, and `planned_end_date` + `production.order.overdue_grace_days` is before the planning date | order |
      | `expedite` (message) on the order's main-output supply line | the first need date d the order serves is earlier than its supply date by more than `planning.production_reschedule_in_tolerance_days` | supply line |
      | `postpone` (message) | the supply date is earlier than its first need by more than `planning.production_reschedule_out_tolerance_days`, within `planning.production_rescheduling_horizon_days` | supply line |
      | `cancel` (message) | a `not_started` order whose supply the projection never needs within the horizon, including a make-to-order order whose sales line was canceled | supply line |
      | `reduce` (message) | a `not_started` order whose needed quantity is below G; proposed quantity the needed quantity, never below what is posted | supply line |

    - **Work item.** One `production_order_exception` per order (module `planning`, owner `planning_owner`) lists the order's open exceptions and messages of the latest run; the consumer `planning_work_items` closes it when a run raises none. These exceptions get no `planning_exception` work item, as `capacity_overload` gets its own kind.
    - **Steps:** D1 gathers the messages, pegging and the order's status; D2 computes new dates with `plan_production` in mode `fixed`, groups related messages by pegging, and orders them bottom-up by low-level code, so a component's order is proposed before its parent's; L1 `explain` picks a candidate handle or `none`; D3 drafts the update (draft order) or change order (released order).
    - **Cancel** is never drafted: the note recommends it and a person runs `CancelProductionOrder`, which ADR-0034 rule 5 allows only before the first posting.
18. C5 technical completion and stalled orders:
    - **Triggers:** `production_completion_candidate` and `production_order_stalled` (rule 12).
    - **L1 `classify`** (seat classification): the likely state from codes and posting gaps, one of `finished`, `waiting_material`, `waiting_capacity`, `abandoned`, `unknown`, with a summary.
    - **D3:** for `finished`, a change proposal with `CompleteProductionOrder` and the order's version as `expected_version` (ADR-0034 rule 17), with open reservations, staged stock and the usage variance as evidence; otherwise a note to the shop-floor lead. A late receipt after completion goes through the person's `ReopenProductionOrder`.

**Capture agent**

19. C6 shop-floor capture (decision 7), `production_capture`:
    - **Trigger:** `shop_floor_report_extracted`, raised when an extraction of purpose `shop_floor_report` (rule 26) from an enabled source reaches `extracted` or `verified`. A person on NativeFlows's own shop-floor screen or scanner needs no agent (ADR-0061 rule 9).
    - **Scope resolver:** the extraction's `production_order_number` field must be trusted ([ADR-0057](0057-document-intake-and-extraction.md) rule 17: closed shape, resolved to exactly one production order) and the order must be in the record scope of the human the run acts for. Then the run's subject is that order. Otherwise `agent_scope_unresolved`; the item stays with a person, and the response does not say whether such an order exists elsewhere.
    - **Taint:** the run starts tainted (outside content). It reads its order and the order's lines (rule 13), its work item with the extraction as evidence, its own drafts and reference data. The company's scrap reason codes are passed as the closed list of the mapping step, a reading added to the same grouped question.
    - **D1 `resolve`:** the operation by a scanned order-and-operation barcode first, then by a trusted operation number of the order.
    - **L1 `map_report`** (seat classification): only when the operation is ambiguous, one of at most five candidate operations; maps free-text reasons to a reason code of the closed list or `none`; writes the note. Output `ProductionCaptureMapReportOutput`. It writes no quantity, lot or date.
    - **D2 `draft`:** quantities, lot and posting date are copied from the extraction's normalized values as stated, with the field IDs as evidence (INV-733). It drafts `CreateOperationConfirmation`, `CreateProductionIssue` or `CreateProductionReceipt` (`is_draft_only`) with `entry_source` `capture_agent`; the plan shows the checks of rule 22, the milestone's generated confirmations and the backflush lines (ADR-0034 rule 12), none chosen by the model.
    - **Gate:** a person posts every capture draft (hard lock 3). Text in a report that says to post or names another order changes nothing: a tainted run may run only `is_draft_only` commands and read only its order.

    Note ([ADR-0071](0071-work-orders-and-shop-floor-execution.md), proposed 2026-11-17): the capture agent may also draft time logs (`CreateOperationTimeLog`, `is_draft_only`; state `draft`) for its order; a person confirms them with `ConfirmOperationTimeLog`; it never starts, pauses or blocks a WO (ADR-0071 rules 9, 17).

    Note ([ADR-0074](0074-core-data-structure-additions.md), proposed 2026-11-19): the company's scrap reason codes passed as the closed list of the mapping step are the active reasons of kind `scrap` (ADR-0074 rule 14).

**Variance agent and standards feedback**

20. C7 `production_variance`, a workflow on the analysis layer (ADR-0060 rules 18, 19, 23):
    - **Triggers:** `ProductionCostSettlementPosted` for valued variances; a weekly schedule for in-flight usage variances (rule 9); a controller's question.
    - **Facts:** `production_variance_overview`, `GetProductionOrderUsageVariance`, `ListProductionOrderVarianceDriver`, ranked by rule 11.
    - **L1:** a narrative plan of claim template codes with fact handles; code checks and renders every number. Templates carry preconditions computed by code: a favorable claim is not offered for the `remaining` category of an order completed in a period without receipts, so a negative residual (ADR-0035 rule 10) is never called a saving.
    - **Output:** an explanation linked to orders and documents; information only; nothing posts.
21. C8 standards feedback, on `production_standard_review` (rule 12):
    - **D1:** code computes, per production version, the median and spread of actual scrap percent per operation, run time per unit and lead time over the qualifying orders.
    - **L1 `choose_standard`** (seat analysis): which standard the evidence concerns, from candidate handles, with an explanation.
    - **Output:** a note with the statistics. A change to a released revision is a new revision through [ADR-0062](0062-product-engineering-workflow.md), started by a person (no agent starts an agent, ADR-0050 rule 30); a fixed lead time of the version is a change proposal.

**Checks, commands and data**

22. Confirmation checks on `operation_confirmation` at create, update and post, for every entry source:
    - **Yield.** Base: the previous internal operation's cumulative yield, or Q for the first. Cumulative yield + scrap above base × (1 + `production.confirmation.yield_tolerance_percent` / 100) gives the check result `yield_above_tolerance` when `production.confirmation.over_tolerance_action` is `warn` (raised for the first internal operation, or for any operation while the tolerance is above 0, so it never repeats `yield_above_previous_operation`), and the error `yield_tolerance_exceeded` when it is `reject`. `yield_above_previous_operation` (ADR-0034 rule 12) is unchanged.
    - **Activity.** An actual activity quantity above its standard at the confirmed quantity × (1 + `production.confirmation.activity_tolerance_percent` / 100) gives `activity_above_standard`.
    - **Duplicate.** Another draft or posted, not reversed confirmation of the same order and operation with the same yield, scrap and scrap reason, recorded within `production.confirmation.duplicate_window_minutes`, gives `operation_confirmation_duplicate_suspected`. The window has a lower bound of 10 minutes, so the check cannot be switched off. The same photo sent twice is already one extraction ([ADR-0057](0057-document-intake-and-extraction.md) rule 15).

    Note ([ADR-0071](0071-work-orders-and-shop-floor-execution.md), proposed 2026-11-17): two confirmations with yield and scrap 0 are duplicates only when their activity quantities are equal too (ADR-0071 rule 2).
23. Settings, written as definitions of ADR-0063's settings registry, in its vocabulary: storage `setting_value`, change effect `immediate`, and area `production`, `planning` or `agents` by the key's first segment. Tightening is immediate by one person with `edit` on the leaf; loosening is accepted only from an approved change proposal; a `neutral` row is changed directly with a reason (ADR-0063's asymmetric path). A loosening of a row with `outdates` `auto_post` marks the production import's auto-post evidence outdated; `promotion` means the agent type's stored promotion evidence does not cover the looser value.

    | Key | Scope | Value type | Core default | Bounds | Direction | Leaf | Outdates |
    | --- | --- | --- | --- | --- | --- | --- | --- |
    | `production.reservation.mode` | `company` | `enum` | `on_release` | `off\|on_release\|scheduled` | `neutral` | `production_structure` | `none` |
    | `production.reservation.window_days` | `company` | `integer` | `14` | `0..180` | `neutral` | `production_structure` | `none` |
    | `production.agent.readiness_horizon_days` | `company` | `integer` | `14` | `0..90` | `neutral` | `agent_production` | `none` |
    | `production.agent.shortage_candidate_kinds` | `company` | `code_list` | `["expedite_supply", "stock_transfer", "alternative_version", "reschedule"]` | `codes` | `subset_tighter` | `agent_production` | `promotion` |
    | `planning.production_reschedule_in_tolerance_days` | `company` | `integer` | `0` | `0..30` | `lower_tighter` | `planning_run` | `none` |
    | `planning.production_reschedule_out_tolerance_days` | `company` | `integer` | `3` | `0..60` | `lower_tighter` | `planning_run` | `none` |
    | `planning.production_rescheduling_horizon_days` | `company` | `integer` | `60` | `1..365` | `neutral` | `planning_run` | `none` |
    | `production.order.start_grace_days` | `company` | `integer` | `1` | `0..30` | `neutral` | `production_structure` | `none` |
    | `production.order.overdue_grace_days` | `company` | `integer` | `0` | `0..30` | `neutral` | `production_structure` | `none` |
    | `production.order.stalled_days` | `company` | `integer` | `5` | `1..60` | `neutral` | `production_structure` | `none` |
    | `production.completion.propose_at_percent` | `company;product_category` | `percent` | `100` | `80..100` | `higher_tighter` | `production_structure` | `none` |
    | `production.confirmation.yield_tolerance_percent` | `company;product_category` | `percent` | `0` | `0..100` | `lower_tighter` | `operation_confirmation` | `auto_post` |
    | `production.confirmation.over_tolerance_action` | `company` | `enum` | `warn` | `warn\|reject` | `order:warn<reject` | `operation_confirmation` | `auto_post` |
    | `production.confirmation.activity_tolerance_percent` | `company;product_category` | `percent` | `25` | `0..500` | `lower_tighter` | `operation_confirmation` | `auto_post` |
    | `production.confirmation.duplicate_window_minutes` | `company` | `integer` | `120` | `10..1440` | `higher_tighter` | `operation_confirmation` | `auto_post` |
    | `production.capture.enabled_sources` | `company` | `code_list` | `["spreadsheet"]` | `codes` | `subset_tighter` | `agent_production_capture` | `promotion` |
    | `production.mes_import.auto_post` | `company` | `boolean` | `false` | `true\|false` | `false_tighter` | `operation_confirmation` | `none` |
    | `production.mes_import.min_evidence_drafts` | `company` | `integer` | `300` | `150..3000` | `higher_tighter` | `operation_confirmation` | `auto_post` |
    | `production.mes_import.min_unchanged_percent` | `company` | `percent` | `99` | `98..100` | `higher_tighter` | `operation_confirmation` | `auto_post` |
    | `production.mes_import.min_evidence_months` | `company` | `integer` | `2` | `1..12` | `higher_tighter` | `operation_confirmation` | `auto_post` |
    | `production.variance.rank_threshold_percent` | `company;product_category` | `percent` | `5` | `0..100` | `neutral` | `report_production` | `none` |
    | `production.variance.rank_threshold_amount` | `company` | `decimal` | `0` | `0..` | `neutral` | `report_production` | `none` |
    | `production.variance.top_n` | `company` | `integer` | `20` | `1..200` | `neutral` | `report_production` | `none` |
    | `production.feedback.enabled` | `company` | `boolean` | `false` | `true\|false` | `neutral` | `agent_production` | `none` |
    | `production.feedback.min_orders` | `company` | `integer` | `5` | `3..100` | `neutral` | `agent_production` | `none` |
    | `production.feedback.min_periods` | `company` | `integer` | `2` | `1..12` | `neutral` | `agent_production` | `none` |

    - **Code lists.** ADR-0063's `code_list` bounds are `codes`; the allowed codes are closed lists of this ADR: rule 16's seven kinds for `production.agent.shortage_candidate_kinds`, and `spreadsheet`, `photo`, `message_text` for `production.capture.enabled_sources`. A value outside them is `setting_out_of_bounds`.
    - **Product category.** A `product_category` value applies to the category of the order's main output product (for a disassembly order, of the order's item).
    - **Import evidence, rule of three.** `production.mes_import.min_evidence_drafts` is at least ⌈3 / `auto_post.max_error_rate`⌉ (ADR-0063's error ceiling: 300 at its default 1%), a declared order between the two settings; `min_unchanged_percent` is at least 100 − that rate.
    - **Today's behavior.** The defaults reproduce ADR-0034: reservation at release, yield deviations as check results only, no automatic posting of shop-floor documents. `production.variance.rank_threshold_amount` 0 means off.
    - **Reservation modes.** `off`: neither release nor the sweep reserves; people run `ReserveProductionOrderComponent`. `on_release`: release reserves up to available to promise (ADR-0034 rule 9) and the sweep fills shortfalls of released orders. `scheduled`: release reserves only lines whose requested date lies within the window, with the check result `reservation_deferred` for the others, and the sweep reserves each line as it enters the window. This answers the concern that release can hold stock months ahead.
    - **ADR-0063's registry.** The registry, `setting_value`, `UpdateCompanySetting`, the asymmetric path, the evidence marker and the catalog [settings.csv](../catalogs/settings.csv) are [ADR-0063](0063-configurable-policy-settings.md)'s. These 26 rows are appended to that catalog with this change, with `source` naming this ADR; a note on ADR-0063 rule 29 records the new count, and its lab reads the catalog's own rows instead of a fixed list.
24. `TransferStockReservation` (module `inventory`, verb Transfer, effect class `other`, `is_proposal_bound`, `stock_reservation` at `post`), the reservation transfer between orders:
    - **Payload:** the source reservation, the target demand line, the quantity, and the `expected_version` of both orders.
    - **Rules:** source and target are demand lines of production order component lines of approved orders that are not technically complete, with the same item and warehouse; the quantity is at most the source's open, unpicked quantity and at most the target line's short quantity at execution, max(0, unreserved open requirement − available to promise of the item in the target's issue warehouse), computed under the target order's lock; a lot-bound reservation keeps its lot. Otherwise `reservation_transfer_invalid`, so a transfer is refused once a goods receipt has made free stock cover the target, whether or not anything has reserved it yet. Reservations of sales orders are not transferred in Phase 1 (decided by the architect).
    - **Evidence:** the proposal shows the target's shortage and the source order's resulting short quantity and pegged demand, computed by rule 16.
    - **Database:** a trigger refuses a transferred row whose source is of another company, item, warehouse or lot, any change of `transferred_from_reservation_id` after insert, so a transfer chain has no cycle, and any change of `item_id`, `warehouse_id` or `lot_id` on a row that has or is a transfer source.
    - **Effect:** the source reservation is reduced (canceled when it reaches 0) and a new reservation for the target carries `transferred_from_reservation_id`, with the target's destination bin and release sequence. Event `StockReservationTransferred`.
    - **Only by proposal.** Like `UpdateAgentTypeSetting` setting `assisted` (ADR-0050 rule 14), the handler accepts it only from the execution of an approved change proposal and returns `proposal_required` otherwise, for people too.
25. Production import (decision 8), `ImportOperationConfirmation` (module `production`, verb Import, effect class `other`; drafting needs `operation_confirmation` at `edit`, and auto-posting needs the integration credential to hold `post` on `operation_confirmation`; actor `integration`; an integration, not an agent; on no tool list):
    - **Rows:** order number, operation number, yield, scrap, reason code, posting date and `external_reference`, unique per company (`duplicate_external_document` names the existing confirmation).
    - **Drafts first.** Each row becomes a draft confirmation with `entry_source` `production_import`, checked by rule 22.
    - **Auto-post** as `integration` only when all hold: `production.mes_import.auto_post` is true; the draft's simulated plan has no check result at all (none of `yield_above_previous_operation`, `yield_above_tolerance`, `activity_above_standard`, `operation_confirmation_duplicate_suspected`, `component_shortage` or any other) and passes the state and period checks; and a policy rule allows `post` of `operation_confirmation` for actor kind `integration`, enabled by `EnablePolicyRule` with shadow evidence (ADR-0043 rule 14). Production registers the evidence hook `GetProductionImportShadowEvaluation`: at least `production.mes_import.min_evidence_drafts` import drafts over at least `production.mes_import.min_evidence_months` calendar months, at least `production.mes_import.min_unchanged_percent` of them posted unchanged by people, and none posted to another order or operation than its row named. Confirmation-required postings add to `auto_post_unconfirmed`.
    - **Otherwise** the draft stays for a person with `production_import_review`. No LLM touches the path, so ADR-0043 rule 9, floor 5 is not engaged.

    Note ([ADR-0065](0065-deterministic-auto-post-gateway.md), 2026-11-16 (proposed)): the production import is an instance of the auto-post gateway: `production` registers a checker for `operation_confirmation` (actor `integration`) whose rules are this rule's, with `GetProductionImportShadowEvaluation` as its evidence function and `ImportOperationConfirmation` as its trigger; behavior is unchanged, and its decisions are written in the gateway's columns of `policy_decision` ([ADR-0065](0065-deterministic-auto-post-gateway.md) rule 20).
26. Extraction purpose `shop_floor_report` ([ADR-0057](0057-document-intake-and-extraction.md) rule 2), leaf `operation_confirmation`, consumer `production`:
    - **Fields:** `production_order_number` (code, resolved to one production order), `operation_number` (code, resolved on that order), `yield_quantity` (quantity), `scrap_quantity` (quantity), `scrap_reason_text` (text, never trusted), `lot_code` (code), `posting_date` (date). Required: the order number, the yield and the posting date.
    - **Rules:** `shape` per type; yield + scrap > 0; the posting date not after the business date.
    - **Risk order** on the verification screen: order number, operation, yield, scrap, date.
    - **Sources** (`production.capture.enabled_sources`): `spreadsheet` (document kind `spreadsheet`), `photo` (`image`, `pdf_image`; vision values need the seat permission of [ADR-0057](0057-document-intake-and-extraction.md) rule 21 and stay untrusted until confirmed) and `message_text` (an operator's message, document kind `email`). A mailbox may carry `document_intake_purpose` `shop_floor_report`. Voice stays later (ADR-0057 rule 29).

    Note ([ADR-0077](0077-ui-floorplans-annotations-and-embedded-agent.md), proposed 2026-11-19): Phase 1 mobile capture in the UI is photo and text, through this agent when the source `photo` is enabled; voice stays after Phase 1, and the capture intake keeps a seam to accept an audio attachment later (ADR-0077 rule 18).
27. DDL ([DS-43-54-planning-production.sql](../design/DS-43-54-planning-production.sql), [DS-22-09-42-commercial-inventory.sql](../design/DS-22-09-42-commercial-inventory.sql), [DS-36-document-intake.sql](../design/DS-36-document-intake.sql), [DS-35-crm.sql](../design/DS-35-crm.sql)):
    - `planning_exception`: kinds `production_order_start_overdue` and `production_order_overdue`; column `production_order_id` with its company key, set exactly for those kinds.
    - `operation_confirmation`: `entry_source` (`person`, `capture_agent`, `production_import`; default `person`) and `external_reference`, set exactly for `production_import`, not blank, and unique per company.
    - `stock_reservation`: `transferred_from_reservation_id`, a company key to `stock_reservation`, never the row itself, with the trigger of rule 24.
    - The purpose value `shop_floor_report` in `document_reader.purposes`, `document_extraction.purpose`, `extraction_mapping_rule.purpose` and `mailbox.document_intake_purpose`.

**Quality and catalogs**

28. Quality, budgets and promotion (ADR-0051 rules 7, 9 notes; values proposed, flagged with ADR-0051 rule 9's budgets):

    | Agent type | Golden set | Shadow agreement | Minimum cases | Shadow comparator |
    | --- | --- | --- | --- | --- |
    | `production` | 90% | 90% | 30 exceptions | the chosen candidate (kind, target order, document) against what the planner did before the item closed |
    | `production_capture` | 95% | 95% | 50 reports per source | per field, the draft's value against the value the person posted |
    | `production_variance` | ADR-0060 rule 29 | ADR-0060 rule 29 | ADR-0060 rule 29 | ADR-0060 rule 29 |

    | Agent type | LLM calls | Tool calls | Input tokens | Output tokens | Cost (USD) | Seconds | Rows read | Daily cost (USD) | Daily runs |
    | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
    | `production` | 10 | 120 | 200,000 | 10,000 | 1.00 | 600 | 10,000 | 15 | 400 |
    | `production_capture` | 6 | 30 | 80,000 | 5,000 | 0.40 | 180 | 500 | 10 | 500 |
    | `production_variance` | 14 | 40 | 140,000 | 12,000 | 0.95 | 180 | 2,000 | 10 | 100 |

    Sweep runs make no LLM call and consume only tool-call and row budgets.
29. Catalog rows:
    - **Errors** (DS-04): `yield_tolerance_exceeded` (validation), `reservation_transfer_invalid` (validation).
    - **Check results:** `yield_above_tolerance`, `activity_above_standard`, `operation_confirmation_duplicate_suspected`, `reservation_deferred`.
    - **Work item kinds:** `production_order_exception` (planning), `production_component_shortage`, `production_completion_candidate`, `production_order_stalled`, `production_standard_review`, `shop_floor_report_extracted`, `production_import_review` (production).
    - **Commands and queries:** `ListComponentShortage`, `EvaluateProductionOrderRelease`, `GetProductionOrderUsageVariance`, `ListProductionOrderVarianceDriver`, `RunProductionOrderCheck`, `ImportOperationConfirmation` (`production`); `GetProductionOrderPegging`, `ListShortageResolutionCandidate` (`planning`); `TransferStockReservation` (`inventory`). No new verb.
    - **Leaves:** `agent_production`, `agent_production_capture`, `agent_production_variance`; template levels of rule 1, and `production_planner` at `post` on `stock_reservation` so the planner can approve transfers.
    - **Invariants** INV-730 to INV-741 of the block INV-730 to INV-759 and **edge cases** EC-200 to EC-219 (section Edge cases and invariants). Production rows have no first step until the production core step is numbered.
    - **DS-17:** business event types `shop_floor_report_received` and `production_performance_imported`.
30. Decided by the architect (decision 9), each in the configurable direction with a safe default: the owner of scheduled runs is the agent type setting's workflow owner (rule 3); the sweep is a workflow without an LLM step (rule 15); cancellation is never drafted (rule 17); completion candidates for disassembly orders (rule 12); the scrap reason list as the closed list of a tainted step (rule 19); the duplicate window's lower bound (rule 22); reservation modes and window (rule 23); transfers between production orders only, capped at the target's unreserved requirement (rule 24); the reservation priority by requested date, which differs from ADR-0023 rule 13's first-come interim and is recorded with that question (rule 7); the shortage candidates' selection and cap of 7 (rule 16); the numeric projection of posted capture rows (rule 13); the import's evidence figures sized by the rule of three (rule 23); the import's auto-post behind ADR-0043 rule 14's evidence (rule 25); the purpose's fields and sources (rule 26); budgets (rule 28). Recorded as decided, not open: alternative production versions are the Phase 1 substitution path (decision 5); a split is a change order plus a new draft order (decision 6).
31. Lab check `t25_production_agent.py` ([validation lab](../reviews/2026-11-14-design-validation/README.md)): pure functions for the settings registry, its bounds and change path, the shortage list, the release verdict, the reservation priority, the sweep with racing receipts and others' reservations, reservation modes, upward pegging, exceptions and action messages with tolerances and the bottom-up order, alternative versions on recomputed dates, completion candidates, the confirmation checks, capture scope and stated quantities, the import gate, reservation transfers, variance drivers and ranking, the global halt and the tool lists; with `--load`, on the schema of `load_all.py`: the new columns, kinds and purpose values with their checks and keys.

## Options considered

| Option | For | Against |
| --- | --- | --- |
| Three agent types (chosen) | Taint and promotion evidence stay apart; the sweep runs in a clean type | Three settings and evaluations |
| One agent type with steps | One setting | A tainted capture step would taint every run of the type and stop the sweep |
| Production agent takes over planned orders | One agent for production | Duplicates the planning agent; planned orders are planning's rows |
| Sweep as a workflow without an LLM step (chosen) | Budgets, run records, modes and the global halt | Needs the agent type in `assisted` |
| Sweep as a plain system job | No agent setting | No mode ladder or run record; ADR-0034 rule 9 names the agent |
| Reservation transfer only by approved proposal (chosen) | A shortage never moves onto another order silently | Slower than a direct move |
| Release-with-shortage setting | Mirrors SAP's three options | The policy table already ranks `has_component_shortage` |
| Exceptions in `planning_exception` with their own work item kind (chosen) | One run raises and closes them; follows `capacity_overload` | Planning reads real orders through `production.contract` |
| A production-owned exception table | Owned by the module of the order | Two places for exceptions; layer 3 would need the projection |
| Capture copies stated values, a person posts (chosen) | No model number reaches stock | A person posts every capture |
| Import auto-post behind a setting and ADR-0043 evidence (chosen) | Follows the accepted auto-post path | Needs shadow evidence first |
| Import auto-post by setting alone | Simple | Bypasses ADR-0043 rule 14 |

## Consequences

- **Builders** add four production views, eight queries and commands, one system job, the import and three workflows; the safety machinery is ADR-0050's.
- **Planning** raises two exception kinds and four message kinds on production-order supply; `postpone` and `reduce`, a later slice for purchase supply (ADR-0024 rule 21), are in Phase 1 for production orders.
- **ADR-0063's catalog** gains rule 23's 26 rows; `t24_settings.py` checks each catalog row against the ADR its `source` names, so later ADRs add settings without editing its key lists.
- **Reserved items stay with the author:** no floor is added (ADR-0043 rule 9). The apply step extends four existing open questions without adding one: the grouped spec 03 readings gain (p) the capture run's reading of its order's child rows, (q) the scrap reason codes as a closed list and (r) the numeric projection of posted capture rows; the agent values gain rule 28's budgets and thresholds and rule 25's import evidence; the reservation question records rule 7's priority; the DS-52 question gets a note that reservation timing is a setting and release with shortage is ranked by policy, and stays open.
- **Second deterministic auto-post path.** ADR-0051 rule 6 names the bank cascade as the only auto-post; the production import is a second, deterministic path, not an agent's, behind the same ADR-0043 rule 14 evidence (a note on rule 6).
- **Revisit when** shadow agreement stays below 90% for a quarter, a customer needs sales-order reservations transferred, or substitute components enter Phase 1.

## Documents updated

- **This ADR** (new) and the index row in [docs/adr/README.md](README.md).
- **ADRs:** notes in ADR-0023, ADR-0024, ADR-0034, ADR-0035, ADR-0043, ADR-0050, ADR-0051 and ADR-0057.
- **DDL:** [docs/design/DS-43-54-planning-production.sql](../design/DS-43-54-planning-production.sql), [docs/design/DS-22-09-42-commercial-inventory.sql](../design/DS-22-09-42-commercial-inventory.sql), [docs/design/DS-36-document-intake.sql](../design/DS-36-document-intake.sql), [docs/design/DS-35-crm.sql](../design/DS-35-crm.sql).
- **Design files:** [docs/design/DS-04-command-envelope.md](../design/DS-04-command-envelope.md), [docs/design/DS-16-invariants-and-harness.md](../design/DS-16-invariants-and-harness.md), [docs/design/DS-17-synthetic-dataset.md](../design/DS-17-synthetic-dataset.md), [docs/design/backlog.md](../design/backlog.md).
- **Catalogs:** [work-item-kinds.csv](../catalogs/work-item-kinds.csv), [invariants.csv](../catalogs/invariants.csv), [edge-cases.csv](../catalogs/edge-cases.csv), [authorization-areas.csv](../catalogs/authorization-areas.csv), [role-template-levels.csv](../catalogs/role-template-levels.csv), [settings.csv](../catalogs/settings.csv) (26 rows; a note on ADR-0063 rule 29; `t24_settings.py` widened).
- **Glossary:** [docs/spec/00-reading-guide.md](../spec/00-reading-guide.md) (rows only).
- **The lab:** [docs/reviews/2026-11-14-design-validation/](../reviews/2026-11-14-design-validation/README.md): `lab/t25_production_agent.py` (new).
- **Open questions:** [docs/open-questions.md](../open-questions.md): no new question; the grouped spec 03 readings, the agent values, the reservation question and the DS-52 question are extended (Consequences).
- **Log:** [docs/runbook/step-log.md](../runbook/step-log.md) at acceptance.

## Edge cases and invariants

**Edge cases** (DS-17; block EC-200 to EC-219, area mostly `production`):

- **EC-200:** a goods receipt covers the target's shortage while a `transfer_reservation` proposal waits; at execution its short quantity, unreserved requirement minus the new available to promise, is 0, so the transfer fails with `reservation_transfer_invalid` although nothing has reserved the receipt yet, and the next check closes the shortage item.
- **EC-201:** two sweeps race for one receipt; no component line is over-reserved.
- **EC-202:** a sweep finds the available stock reserved for a sales order; nothing is taken.
- **EC-203:** a lateness over two levels; the component order's reschedule is proposed before the parent's, with consistent dates.
- **EC-204:** an alternative version valid on the end date but not on the recomputed start is not offered.
- **EC-205:** a reschedule-out tolerance of 3 days hides a 2-day postponement, while a 1-day lateness is still raised with the in-tolerance at 0.
- **EC-206:** a capture report names an order of a branch outside the human's scope; the run is refused unresolved and the response does not reveal the order.
- **EC-207:** a capture report with yield above the previous operation, inside and outside tolerance; warn, then reject under `reject`.
- **EC-208:** a duplicate report: the same photo sent twice is one extraction; the same numbers typed again within the window give `operation_confirmation_duplicate_suspected`.
- **EC-209:** a report's text says "post this now" and names another order; the run stays draft-only and in its order.
- **EC-210:** a capture report for a milestone operation; the earlier operations' generated confirmations are in the draft's plan, not chosen by the model.
- **EC-211:** backflush fails for missing stock in the supply bin; the draft's simulation shows `negative_stock` and C1 explains it.
- **EC-212:** a completion proposal at 97% received under a 95% setting, then a late receipt; the person reopens the order.
- **EC-213:** an order completed in a period without receipts; the variance explanation does not call the negative residual a saving.
- **EC-214:** rework and disassembly orders in the shortage list, completion candidates and variance queries.
- **EC-215:** a make-to-order order whose sales line is canceled; a `cancel` message on a `not_started` order, recommended in a note, never executed by the agent.
- **EC-216:** a policy rule tries to approve a tainted capture draft automatically; floor 3 makes it `human_post`.
- **EC-217:** every production agent type is set to `off` during a sweep; it stops at the next call boundary.
- **EC-218:** a production import with auto-post enabled: a row whose plan has no check result posts as `integration` only after the policy rule is enabled with evidence (300 drafts over 2 months, 99% posted unchanged); a row with any check result stays a draft for a person; a repeated reference is refused.
- **EC-219:** a reservation transfer outside an approved proposal is refused with `proposal_required`; through one, the source is reduced and the target gains the same quantity.

**Invariants** (DS-16; block INV-730 to INV-759, INV-730 to INV-741 taken; first step the production core step):

- **INV-730:** no tool list of a `production`, `production_capture` or `production_variance` agent type version holds a posting command, a `Submit`, `Post`, `Approve`, `Issue` or `Send` command, `StartAgentRun`, `TransferStockReservation`, `CompleteProductionOrder`, `ReopenProductionOrder`, `ImportOperationConfirmation` or a planned-order command.
- **INV-731:** every `production_capture` run was tainted from its start, has scope kind `subject` on a production order, and every row reference in its steps is that order or its lines, its work item and evidence, its own drafts or reference data.
- **INV-732:** every posted shop-floor document whose version a `production_capture` run wrote was posted by a human.
- **INV-733:** every quantity, lot and posting date on a draft written by a `production_capture` run equals the normalized value of an extraction field named in its evidence.
- **INV-734:** every reservation with `transferred_from_reservation_id` has the company, item, warehouse and lot of its source, was created by a `TransferStockReservation` executed from an approved change proposal, in the transaction that reduced its source by the same quantity, and did not exceed the target line's short quantity at execution; no reservation command of a production agent run reduced another demand line's reservation.
- **INV-735:** per production order component line, open and picked reservations never exceed the open requirement.
- **INV-736:** every `has_component_shortage` policy input recorded at `Submit` of a production order equals whether `EvaluateProductionOrderRelease` returned `component_short` for that version on that business date.
- **INV-737:** every closed `production_order_exception`, `production_component_shortage`, `production_completion_candidate`, `production_order_stalled` and `production_standard_review` work item, and every closed `planning_exception` of the production kinds, was closed by a planning run or `RunProductionOrderCheck`, never by an agent run.
- **INV-738:** every `planning_exception` of kind `production_order_start_overdue` or `production_order_overdue` names an order that was approved and not technically complete on the run's planning date, and its date plus the grace setting was before that date.
- **INV-739:** for every settled order, period and variance category, the contributions of `ListProductionOrderVarianceDriver` sum to the category's row of `production_order_variance`.
- **INV-740:** every operation confirmation posted by an `integration` actor has `entry_source` `production_import` and an `external_reference`, was posted while `production.mes_import.auto_post` was true under a policy rule enabled with evidence that met the import evidence settings in force, by a credential holding `post` on `operation_confirmation`, and had no check result in its plan at posting.
- **INV-741:** in reservation mode `scheduled`, no reservation made by a release or a sweep is for a component line whose requested date lay beyond the window on that business date.
